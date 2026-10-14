"""End cover applies to steel surfaces, including bar radius and turned hooks."""
from copy import deepcopy
import json
import unittest

from pier_cap.cage_3d import layout_3d
from pier_cap.io import load_case
from pier_cap.model import BAR_DIAMETER, evaluate, geometry_evaluation
from pier_cap.transverse import run_end_cover, run_last_station
from pier_cap.transverse_zones import starting_zone_detail
from pier_cap.visuals import reinforcement_plan_figure, elevation_figure
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


def end_case(cover=3.,bar=5):
    case=default_case();case['inputs']['C_s']=cover
    length=geometry_evaluation(case).value('L_cap');radius=BAR_DIAMETER[bar]/2
    case['transverse_detail']={'version':2,'enabled':True,'runs':[
        dict(id='R1',kind='hoop',bar=bar,zone='G',first_in=cover+radius,
             end_in=length-cover-radius,pitch_in=8.,include_end_bar=True)]}
    return case


class EndCoverGeometryTests(unittest.TestCase):
    def test_exact_surface_limits_and_each_end_failure(self):
        for cover,bar in ((3,4),(4,6),(4.5,11)):
            case=end_case(cover,bar);run=case['transverse_detail']['runs'][0]
            e=geometry_evaluation(case);record=run_end_cover(e,run)
            self.assertTrue(record['ok'])
            self.assertAlmostEqual(record['left_in'],cover)
            self.assertAlmostEqual(record['right_in'],cover)
            check=next(c for c in evaluate(case).checks if c.key=='Chk_actual_cover_R1')
            self.assertEqual((check.status,check.ratio),('PASS',1.))
            for field,delta in (('first_in',-.01),('end_in',.01)):
                invalid=deepcopy(case);invalid['transverse_detail']['runs'][0][field]+=delta
                check=next(c for c in evaluate(invalid).checks if c.key=='Chk_actual_cover_R1')
                self.assertEqual(check.status,'FAIL');self.assertGreater(check.ratio,1)

    def test_unused_limit_is_not_a_physical_bar(self):
        case=end_case();run=case['transverse_detail']['runs'][0]
        run.update(first_in=4.,end_in=geometry_evaluation(case).value('L_cap'),
                   pitch_in=geometry_evaluation(case).value('L_cap')-12.,include_end_bar=False)
        e=geometry_evaluation(case);record=run_end_cover(e,run)
        self.assertEqual(record['right_in'],e.value('L_cap')-run_last_station(run)-.3125)
        self.assertTrue(record['ok'])

    def test_rotated_hooks_reduce_allowable_station_range(self):
        case=end_case();run=case['transverse_detail']['runs'][0]
        run.update(kind='pile_u',end_in=run['first_in'])
        run['shape']={'hook_rotation_left_deg':-90.,'hook_rotation_right_deg':90.}
        case['transverse_detail']['version']=4
        record=run_end_cover(geometry_evaluation(case),run)
        # #5 standard 90-degree stirrup hook: centerline radius 3.5db,
        # plus 6db straight extension. Both extremal tail endpoints govern.
        reach=(6*.625+.625)/2+6*.625
        self.assertAlmostEqual(record['minimum_station_in'],3+.3125+reach)
        self.assertAlmostEqual(record['maximum_station_in'],geometry_evaluation(case).value('L_cap')-3-.3125-reach)
        self.assertFalse(record['ok'])

    def test_starter_and_longitudinal_bars_respect_changed_cover_in_all_views(self):
        for cover in (3.,4.5):
            case=default_case();case['inputs']['C_s']=cover
            case['transverse_detail']=starting_zone_detail(geometry_evaluation(case),6,8)
            e=geometry_evaluation(case);length=e.value('L_cap')
            self.assertTrue(all(run_end_cover(e,r)['ok'] for r in case['transverse_detail']['runs']))
            plan=reinforcement_plan_figure(e);elevation=elevation_figure(e)
            for fig in (plan,elevation):
                bands={s.name:s for s in fig.layout.shapes if s.name and s.name.startswith('end-cover-')}
                self.assertAlmostEqual(bands['end-cover-left'].x1*12,cover)
                self.assertAlmostEqual(bands['end-cover-right'].x0*12,length-cover)
                bars=[t for t in fig.data if t.meta and t.meta.get('part') in ('top','bottom','side')]
                self.assertTrue(bars)
                self.assertTrue(all(list(t.x)==[cover/12,(length-cover)/12] for t in bars))
            bars=[t for t in layout_3d(e).data if t.meta and t.meta.get('part') in ('top','bottom','side')]
            self.assertTrue(bars)
            self.assertTrue(all(list(t.x)==[cover,length-cover] for t in bars))


class EndCoverWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook(end_case());self.addCleanup(self.app.close)

    def test_new_encroachments_revert_both_units_and_size(self):
        app=self.app;panel=app.transverse_panel;c=panel.zone_controls['R1'];before=deepcopy(app.case)
        for field,value in (('first_in',3.),('first_ft',.25),('end_in',app.current.value('L_cap')-3.),('bar',6)):
            with self.subTest(field=field):
                c[field].value=value
                self.assertEqual(app.case,before)
                self.assertEqual(c['first_ft'].value,c['first_in'].value/12)
                self.assertIn('Not applied',c['error'].value)
                self.assertIn('cap end cover',c['error'].value)

    def test_saved_invalid_runs_remain_visible_and_can_be_repaired(self):
        case=end_case();run=case['transverse_detail']['runs'][0]
        run['first_in']=1.;run['end_in']+=2.
        loaded=load_case(json.dumps(case).encode(),calculate=False)
        self.app.load(loaded);panel=self.app.transverse_panel;c=panel.zone_controls['R1']
        self.assertEqual(self.app.case['transverse_detail'],case['transverse_detail'])
        self.assertIn('cap end cover',c['warning'].value)
        c['first_in'].value=3.3125
        self.assertEqual(self.app.case['transverse_detail']['runs'][0]['first_in'],3.3125)
        self.assertIn('cap end cover',c['warning'].value)
        c['end_in'].value=self.app.current.value('L_cap')-3.3125
        self.assertNotIn('cap end cover',c['warning'].value)

    def test_geometry_cover_change_warns_without_moving_saved_stations(self):
        app=self.app;before=deepcopy(app.case['transverse_detail'])
        app.controls['C_s'].value=4.
        self.assertEqual(app.case['transverse_detail'],before)
        self.assertIn('cap end cover',app.transverse_panel.zone_controls['R1']['warning'].value)

    def test_custom_run_cannot_be_added_past_cap(self):
        app=self.app;before=deepcopy(app.case)
        app.transverse_panel.add.click()
        self.assertEqual(app.case,before)
        self.assertIn('cap end cover',app.transverse_panel.status.value)

    def test_hook_rotation_toward_either_end_is_rejected(self):
        c=self.app.transverse_panel.zone_controls['R1'];c['kind'].value='pile_u'
        before=deepcopy(self.app.case)
        for angle in (-90.,90.):
            c['hook_rotation_left_deg'].value=angle
            self.assertEqual(self.app.case,before)
            self.assertIn('cap end cover',c['error'].value)

    def test_end_bar_or_pitch_edit_cannot_cross_the_cover_plane(self):
        case=end_case();run=case['transverse_detail']['runs'][0]
        length=geometry_evaluation(case).value('L_cap')
        run.update(first_in=4.,end_in=length,pitch_in=length-12.,include_end_bar=False)
        self.app.load(case);c=self.app.transverse_panel.zone_controls['R1'];before=deepcopy(self.app.case)
        for field,value in (('include_end_bar',True),('pitch',length-4.)):
            c[field].value=value
            self.assertEqual(self.app.case,before)
            self.assertIn('cap end cover',c['error'].value)

    def test_rebuild_repairs_cover_and_undo_restores_warned_original(self):
        case=default_case();case['transverse_detail']=starting_zone_detail(geometry_evaluation(case),5,8)
        case['transverse_detail']['runs'][0]['first_in']=1.
        self.app.load(case);before=deepcopy(self.app.case['transverse_detail']);panel=self.app.transverse_panel
        panel.generate.click()
        self.assertNotIn('cap end cover',panel.zone_controls['R1']['warning'].value)
        panel.undo_start.click()
        self.assertEqual(self.app.case['transverse_detail'],before)
        self.assertIn('cap end cover',panel.zone_controls['R1']['warning'].value)


if __name__=='__main__':unittest.main()
