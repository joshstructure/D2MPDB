"""Zone-end bars retain their fitted stations in drawings, checks and saved cases."""
from copy import deepcopy
import csv
import json
import tempfile
import unittest
from pier_cap.model import evaluate,BAR_DIAMETER
from pier_cap.detailing import required_clear
from pier_cap.transverse import run_stations,run_bar_count,run_last_station,scheduled_bars,validate_detail,development_fingerprint,development_current
from pier_cap.transverse_zones import cap_zones,starting_zone_detail,zone_runs
from pier_cap.widgets import CapNotebook
from pier_cap.io import load_case,export_bundle
from tests.case_fixtures import default_case


class EndBarScheduleTests(unittest.TestCase):
    def run_case(self,end,pitch=8):
        case=default_case()
        case['transverse_detail']={'version':2,'enabled':True,'runs':[
            dict(id='R1',kind='hoop',bar=5,zone='G',first_in=4,end_in=end,pitch_in=pitch,include_end_bar=True)]}
        return case,case['transverse_detail']['runs'][0]

    def test_regular_pitch_then_short_final_gap_without_duplicate_end(self):
        for end,expected in [(4,[4]),(9,[4,9]),(20,[4,12,20]),(23,[4,12,20,23])]:
            with self.subTest(end=end):
                case,run=self.run_case(end)
                self.assertEqual(run_stations(run),expected)
                self.assertEqual(run_bar_count(run),len(expected))
                self.assertEqual(run_last_station(run),end)
                self.assertEqual([b['station_in'] for b in scheduled_bars(case)],expected)
        case,run=self.run_case(23);run.pop('include_end_bar')
        case['transverse_detail']['version']=1
        validate_detail(case)
        self.assertEqual(run_stations(run),[4,12,20])
        self.assertEqual(run_last_station(run),20)

    def test_flag_is_validated_counted_and_invalidates_recorded_development(self):
        case,run=self.run_case(23)
        run.update(development_confirmed=True,development_basis='Reviewed end bar')
        run['development_fingerprint']=development_fingerprint(case,run)
        self.assertTrue(development_current(case,run))
        run['include_end_bar']=False
        self.assertFalse(development_current(case,run))
        run['include_end_bar']='yes'
        with self.assertRaisesRegex(ValueError,'include_end_bar'):validate_detail(case)
        case,run=self.run_case(4+1999*8+.1)
        with self.assertRaisesRegex(ValueError,'2,000'):validate_detail(case)
        case,run=self.run_case(23);case['transverse_detail']['version']=1
        with self.assertRaisesRegex(ValueError,'version 2'):validate_detail(case)

    def test_zone_builder_creates_both_ends_in_every_zone_with_common_settings(self):
        case=default_case();before=deepcopy(case);e=evaluate(case)
        detail=starting_zone_detail(e,6,7)
        self.assertEqual(case,before)
        case['transverse_detail']=detail;zones,groups,custom=zone_runs(evaluate(case))
        self.assertFalse(custom);self.assertEqual(len(detail['runs']),len(cap_zones(e)))
        for zone in zones:
            self.assertEqual(len(groups[zone['key']]),1)
            run=groups[zone['key']][0];stations=run_stations(run)
            self.assertEqual((run['bar'],run['pitch_in'],run['kind']),(6,7,zone['kind']))
            self.assertEqual((stations[0],stations[-1]),(run['first_in'],run['end_in']))
            self.assertGreaterEqual(stations[0],zone['left']);self.assertLessEqual(stations[-1],zone['right'])
            for left,right in zip(stations,stations[1:]):
                self.assertLessEqual(right-left,7+1e-7)
                self.assertGreaterEqual(right-left-BAR_DIAMETER[6],required_clear(e,BAR_DIAMETER[6])-1e-8)
            self.assertFalse(run['development_confirmed'])

    def test_starter_leaves_half_minimum_clearance_at_every_zone_edge(self):
        e=evaluate(default_case())
        for bar,pitch in ((5,8),(6,7),(8,6)):
            diameter=BAR_DIAMETER[bar];radius=diameter/2
            minimum=required_clear(e,diameter);offset=minimum/2+radius
            detail=starting_zone_detail(e,bar,pitch);zones=cap_zones(e)
            for z,r in zip(zones,detail['runs']):
                self.assertAlmostEqual(r['first_in'],max(e.case['inputs']['C_s']+radius,z['left']+offset))
                self.assertAlmostEqual(r['end_in'],min(e.value('L_cap')-e.case['inputs']['C_s']-radius,z['right']-offset))
            for a,b in zip(detail['runs'],detail['runs'][1:]):
                gap=run_stations(b)[0]-run_stations(a)[-1]-diameter
                self.assertAlmostEqual(gap,minimum)

    def test_pitch_changes_do_not_move_zone_end_bars(self):
        e=evaluate(default_case());zones=cap_zones(e);endpoints=[]
        for pitch in (6,8,20):
            runs=starting_zone_detail(e,5,pitch)['runs']
            endpoints.append([(r['first_in'],r['end_in']) for r in runs])
            # Default minimum clear gap is 2 in; #5 radius is 0.3125 in.
            self.assertAlmostEqual(runs[1]['first_in']-zones[1]['left'],1.3125)
            self.assertAlmostEqual(zones[1]['right']-runs[1]['end_in'],1.3125)
            self.assertTrue(all(r['pitch_in']==pitch for r in runs))
        self.assertEqual(endpoints[0],endpoints[1]);self.assertEqual(endpoints[1],endpoints[2])

    def test_project_and_aggregate_minima_control_boundary_gap(self):
        for project,aggregate,expected in ((3.,.75,3.),(1.,2.,3.),(2.2,.75,2.2)):
            case=default_case();case['screening'].update(minimum_clear_in=project,aggregate_in=aggregate)
            case['transverse_detail']=starting_zone_detail(evaluate(case),5,8)
            runs=case['transverse_detail']['runs']
            self.assertAlmostEqual(runs[2]['first_in']-runs[1]['end_in']-.625,expected)
            e=evaluate(case);checks={c.key:c for c in e.checks};bars=scheduled_bars(case)
            for a,b in zip(bars,bars[1:]):
                if a['run']!=b['run']:
                    check=checks['Chk_actual_clear_'+a['id']+'_'+b['id']]
                    self.assertEqual(check.status,'PASS');self.assertAlmostEqual(check.ratio,1.)

    def test_narrow_zone_reports_offset_problem_without_squeezing_bars(self):
        case=default_case();case['inputs']['C_s']=8
        with self.assertRaisesRegex(ValueError,'Left end: no room after minimum-clearance offsets'):
            starting_zone_detail(evaluate(case),5,8)

    def test_endpoint_bars_survive_json_export_drawings_and_short_gap_checks(self):
        case,run=self.run_case(20.25);app=CapNotebook(case);self.addCleanup(app.close)
        stations=run_stations(run)
        self.assertTrue(any(c.status=='FAIL' and c.key.startswith('Chk_actual_clear_') for c in app.current.checks))
        self.assertIn('fails clear spacing',app.transverse_panel.zone_controls['R1']['warning'].value)
        for key in ('plan','elevation','cage3d'):
            traces=[t for t in app.views.plots[key].data if t.legendgroup=='R1']
            self.assertEqual(len(traces),len(stations))
        self.assertEqual(load_case(json.dumps(app.case).encode())['transverse_detail'],case['transverse_detail'])
        with tempfile.TemporaryDirectory() as root:
            folder=export_bundle(app.case,root)
            with (folder/'transverse_bar_schedule.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual([float(r['station_in']) for r in rows],stations)

    def test_fitted_tail_keeps_endpoints_and_moves_only_required_bars(self):
        for end,pitch,minimum,expected in [
            (20.25,8,2,[4,12,17.625,20.25]),
            (21,5,3.375,[4,9,13,17,21]),
            (20,8,2,[4,12,20]),(23,8,2,[4,12,20,23]),(4,8,2,[4])]:
            case,run=self.run_case(end,pitch);case['transverse_detail']['version']=3
            run['end_min_clear_in']=minimum;validate_detail(case)
            self.assertEqual(run_stations(run),expected)
            self.assertEqual(run_bar_count(run),len(expected));self.assertEqual(run_last_station(run),end)

    def test_infeasible_tail_and_invalid_fit_metadata_are_rejected(self):
        case,run=self.run_case(14.1,5);case['transverse_detail']['version']=3
        run['end_min_clear_in']=3.375
        with self.assertRaisesRegex(ValueError,'fixed end bars cannot fit'):validate_detail(case)
        case,run=self.run_case(20.25);run['end_min_clear_in']=2
        with self.assertRaisesRegex(ValueError,'version 3'):validate_detail(case)
        case['transverse_detail']['version']=3
        for bad in (0,-1,True,float('nan'),float('inf')):
            run['end_min_clear_in']=bad
            with self.assertRaisesRegex(ValueError,'positive finite'):validate_detail(case)

    def test_generated_short_tail_passes_clearance_and_round_trips_exact_stations(self):
        case=default_case();case['transverse_detail']=starting_zone_detail(evaluate(case),5,10)
        e=evaluate(case)
        self.assertTrue(all(c.status=='PASS' for c in e.checks if c.key.startswith('Chk_actual_clear_')))
        run=case['transverse_detail']['runs'][2];stations=run_stations(run)
        self.assertAlmostEqual(stations[-1]-stations[-2]-.625,2.)
        self.assertEqual(load_case(json.dumps(case).encode())['transverse_detail'],case['transverse_detail'])
        app=CapNotebook(case);self.addCleanup(app.close)
        self.assertNotIn('fails clear spacing',app.transverse_panel.zone_controls[run['id']]['warning'].value)
        for key in ('plan','elevation','cage3d'):
            traces=[t for t in app.views.plots[key].data if t.legendgroup==run['id']]
            self.assertEqual(len(traces),len(stations))
            if key!='cage3d':self.assertEqual([t.x[0]*12 for t in traces],stations)
        with tempfile.TemporaryDirectory() as root:
            folder=export_bundle(case,root)
            with (folder/'transverse_bar_schedule.csv').open(encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual([float(r['station_in']) for r in rows],[b['station_in'] for b in scheduled_bars(case)])

    def test_end_fit_changes_invalidate_recorded_development(self):
        case,run=self.run_case(20.25);case['transverse_detail']['version']=3
        run.update(end_min_clear_in=2,development_confirmed=True,development_basis='Reviewed fitted end')
        run['development_fingerprint']=development_fingerprint(case,run)
        self.assertTrue(development_current(case,run))
        run['end_min_clear_in']=2.2
        self.assertFalse(development_current(case,run))


class StartingLayoutWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook(default_case());self.addCleanup(self.app.close)

    def test_rebuild_replaces_current_runs_and_undo_restores_them_exactly(self):
        app=self.app;panel=app.transverse_panel
        panel.start_bar.value=6;panel.start_pitch.value=7;panel.generate.click()
        self.assertIsNotNone(app.current);self.assertFalse(panel.generate.disabled)
        self.assertTrue(all((r['bar'],r['pitch_in'])==(6,7) for r in app.case['transverse_detail']['runs']))
        panel.zone_controls['R1']['end_in'].value=30
        before=deepcopy(app.case['transverse_detail'])
        panel.start_bar.value=5;panel.start_pitch.value=9;panel.generate.click()
        self.assertEqual(len(app.case['transverse_detail']['runs']),len(cap_zones(app.current)))
        self.assertTrue(all((r['bar'],r['pitch_in'])==(5,9) for r in app.case['transverse_detail']['runs']))
        self.assertEqual([panel._cards[r['id']].ui for r in app.case['transverse_detail']['runs']],list(panel.zone_grid.children))
        self.assertIn('Created',panel.status.value)
        panel.undo_start.click()
        self.assertEqual(app.case['transverse_detail'],before)
        self.assertTrue(panel.undo_start.disabled)
        panel.generate.click();self.assertFalse(panel.undo_start.disabled)
        app.load(default_case());self.assertTrue(panel.undo_start.disabled)

    def test_invalid_start_pitch_does_not_replace_existing_runs(self):
        panel=self.app.transverse_panel;panel.generate.click();before=deepcopy(self.app.case)
        for bad in (0,-1,float('nan'),float('inf')):
            panel.start_pitch.value=bad;panel.generate.click()
            self.assertEqual(self.app.case,before)
            self.assertIn('Not applied',panel.status.value)

    def test_split_preserves_short_terminal_bay_and_remains_editable(self):
        panel=self.app.transverse_panel;panel.start_pitch.value=10;panel.generate.click()
        before=[b['station_in'] for b in scheduled_bars(self.app.case)]
        rid='R3'  # Fitted penultimate bar, not just an unmodified regular run.
        panel.zone_controls[rid]['split'].click()
        self.assertEqual([b['station_in'] for b in scheduled_bars(self.app.case)],before)
        panel.zone_controls[rid]['include_end_bar'].value=False
        self.assertFalse(next(r for r in self.app.case['transverse_detail']['runs'] if r['id']==rid)['include_end_bar'])

    def test_infeasible_generation_preserves_previous_layout_and_undo_state(self):
        panel=self.app.transverse_panel;panel.generate.click();before=deepcopy(self.app.case)
        previous=deepcopy(panel._previous_detail)
        panel.start_pitch.value=4;panel.generate.click()
        self.assertEqual(self.app.case,before);self.assertEqual(panel._previous_detail,previous)
        self.assertIn('fixed end bars cannot fit',panel.status.value)

    def test_generated_run_edits_refit_the_tail_and_preserve_card(self):
        panel=self.app.transverse_panel;panel.start_pitch.value=10;panel.generate.click()
        controls=panel.zone_controls['R3'];card=panel._cards['R3']
        def current():return next(r for r in self.app.case['transverse_detail']['runs'] if r['id']=='R3')
        endpoints=(current()['first_in'],current()['end_in'])
        for field,value in [('bar',11),('pitch',9),('end_in',endpoints[1]-.25)]:
            controls[field].value=value;run=current();stations=run_stations(run)
            minimum=required_clear(self.app.current,BAR_DIAMETER[run['bar']])
            self.assertEqual(run['end_min_clear_in'],minimum)
            self.assertGreaterEqual(min(b-a for a,b in zip(stations,stations[1:]))-BAR_DIAMETER[run['bar']],minimum-1e-8)
            self.assertEqual(stations[0],endpoints[0])
            self.assertEqual(stations[-1],value if field=='end_in' else endpoints[1])
            self.assertIs(panel._cards['R3'],card)
        self.assertEqual(self.app.case['transverse_detail']['version'],3)

    def test_enabling_end_bar_upgrades_legacy_layout_format(self):
        panel=self.app.transverse_panel;panel.add.click()
        self.assertEqual(self.app.case['transverse_detail']['version'],1)
        rid=self.app.case['transverse_detail']['runs'][0]['id']
        panel.zone_controls[rid]['include_end_bar'].value=True
        self.assertEqual(self.app.case['transverse_detail']['version'],2)
        self.assertTrue(self.app.case['transverse_detail']['runs'][0]['include_end_bar'])


if __name__=='__main__':unittest.main()
