"""Physical station grouping, actionable occupancy, and aligned zone dimensions."""
from copy import deepcopy
import unittest
from pier_cap.model import evaluate,set_inputs
from pier_cap.transverse import scheduled_bars
from pier_cap.transverse_zones import cap_zones,zone_runs,new_zone_run,zone_add_conflicts,zone_occupancy
from pier_cap.visuals import elevation_figure,reinforcement_plan_figure
from pier_cap.widgets import CapNotebook
from tests.test_transverse_zones import zoned_case


class ZoneBoundaryTests(unittest.TestCase):
    def test_unused_end_limit_does_not_turn_a_pile_run_into_a_crossing_run(self):
        case=zoned_case();before=scheduled_bars(case)
        rid=zone_runs(evaluate(case))[1]['P2'][0]['id']
        run=next(r for r in case['transverse_detail']['runs'] if r['id']==rid)
        run['end_in']=99  # Last actual station stays 91.3125, inside P2.
        zones,groups,custom=zone_runs(evaluate(case))
        self.assertIn(run,groups['P2']);self.assertNotIn(run,custom)
        self.assertEqual(scheduled_bars(case),before)
        self.assertEqual(run['end_in'],99)

    def test_every_removed_starting_zone_can_be_refilled_without_false_custom_warning(self):
        original=zoned_case();zones,groups,_=zone_runs(evaluate(original))
        for zone in zones:
            with self.subTest(zone=zone['key']):
                case=deepcopy(original);remove={r['id'] for r in groups[zone['key']]}
                case['transverse_detail']['runs']=[r for r in case['transverse_detail']['runs'] if r['id'] not in remove]
                before=deepcopy(case);e=evaluate(case)
                self.assertFalse(zone_add_conflicts(e)[zone['key']])
                run=new_zone_run(e,zone['key'],5,8)
                self.assertEqual(case,before)
                if zone['key']=='S1':
                    self.assertEqual(zone_occupancy(e)['S1'][0]['id'],'R2')
                    self.assertAlmostEqual(run['first_in'],37.9375)  # 2 in project clear gap + two bar radii.
                if zone['key']=='S3':self.assertAlmostEqual(run['first_in'],157.9375)

    def test_changed_pile_spacing_names_real_blockers_and_preserves_stations(self):
        case=set_inputs(zoned_case(),S_pile=6);before=deepcopy(case);e=evaluate(case)
        blockers=zone_add_conflicts(e)
        self.assertEqual([o['id'] for o in blockers['P2']],['R4','R5'])
        self.assertEqual(blockers['P2'][0]['stations'],[83.3125,91.3125])
        with self.assertRaises(ValueError) as caught:new_zone_run(e,'P2',5,8)
        for text in ('Pile P2','R4','R5','83.3125','99.3125','Geometry changes do not move saved stations'):
            self.assertIn(text,str(caught.exception))
        self.assertEqual(case,before)

    def test_occupied_zone_shows_run_ids_and_inspect_opens_that_run(self):
        app=CapNotebook(set_inputs(zoned_case(),S_pile=6));self.addCleanup(app.close)
        panel=app.transverse_panel;card=panel._empty_zones['P2'];before=deepcopy(app.case)
        self.assertFalse(card['button'].disabled)
        self.assertFalse(card['bar'].disabled);self.assertFalse(card['pitch'].disabled)
        self.assertNotEqual(card['button'].layout.display,'none')
        for text in ('R4','R5','83.3125','99.3125'):self.assertIn(text,card['note'].value)
        panel._inspect_buttons[('P2','R4')].click()
        self.assertEqual(panel.selected_run_id,'R4')
        self.assertEqual(panel.zone_controls['R4']['details'].selected_index,0)
        self.assertIn('75.3125',panel.selected_info.value)
        self.assertEqual(app.case,before)

    def test_occupied_zone_can_be_added_and_edited_with_overlap_warnings(self):
        app=CapNotebook(set_inputs(zoned_case(),S_pile=6));self.addCleanup(app.close)
        before=deepcopy(app.case['transverse_detail']['runs']);panel=app.transverse_panel
        panel._empty_zones['P2']['button'].click()
        self.assertIsNotNone(app.current)
        runs=app.case['transverse_detail']['runs'];added=runs[-1]
        self.assertEqual(runs[:-1],before)
        controls=panel.zone_controls[added['id']]
        self.assertIn('Limits overlap',controls['warning'].value)
        for name in ('bar','pitch','first_in','end_in'):self.assertFalse(controls[name].disabled)
        controls['end_in'].value=controls['first_in'].value
        self.assertEqual(app.case['transverse_detail']['runs'][-1]['end_in'],added['first_in'])
        self.assertIs(panel.zone_controls[added['id']],controls)

    def test_run_dimensions_refresh_even_when_limit_does_not_add_a_bar(self):
        app=CapNotebook(zoned_case());self.addCleanup(app.close)
        panel=app.transverse_panel;rid='R4';figures={key:app.views.plots[key] for key in ('plan','elevation')}
        before=scheduled_bars(app.case);original=panel.zone_controls[rid]['end_in'].value
        panel.zone_controls[rid]['end_in'].value=original+.125
        self.assertEqual(scheduled_bars(app.case),before)
        for key,figure in figures.items():
            self.assertIs(app.views.plots[key],figure)
            limits=next(t for t in figure.data if (t.meta or {}).get('dimension')=='run_limits' and t.meta['run_id']==rid)
            last=next(t for t in figure.data if (t.meta or {}).get('dimension')=='run_last' and t.meta['run_id']==rid)
            self.assertEqual(limits.meta['end_in'],original+.125)
            self.assertEqual(limits.x[-1],(original+.125)/12)
            self.assertEqual(limits.customdata[0][2],original+.125)
            self.assertEqual(last.x[0]*12,max(b['station_in'] for b in before if b['run']==rid))
            self.assertEqual(figure.layout.xaxis3.matches,'x')
        panel.zone_controls[rid]['first_ft'].value+=.01
        for figure in figures.values():
            limits=next(t for t in figure.data if (t.meta or {}).get('dimension')=='run_limits' and t.meta['run_id']==rid)
            self.assertAlmostEqual(limits.meta['start_in'],panel.zone_controls[rid]['first_in'].value)

    def test_both_drawings_dimension_current_zones_in_inches_and_feet(self):
        case=set_inputs(zoned_case(),S_pile=6);e=evaluate(case);before=deepcopy(case)
        zones={z['key']:z for z in cap_zones(e)}
        for figure in (elevation_figure(e),reinforcement_plan_figure(e)):
            traces={t.meta['zone_key']:t for t in figure.data if (t.meta or {}).get('zone_key')}
            self.assertEqual(set(traces),set(zones))
            for key,zone in zones.items():
                trace=traces[key]
                self.assertEqual(trace.meta['start_in'],zone['left'])
                self.assertEqual(trace.meta['end_in'],zone['right'])
                self.assertEqual(trace.x[0],zone['left']/12)
                self.assertEqual(trace.x[-1],zone['right']/12)
                self.assertEqual(list(trace.customdata[0][1:5]),[zone['left'],zone['right'],zone['left']/12,zone['right']/12])
                self.assertEqual((trace.xaxis,trace.yaxis),('x2','y2'))
            self.assertEqual(traces['P2'].meta['run_ids'],['R4','R5'])
            self.assertEqual(figure.layout.xaxis2.matches,'x')
        self.assertEqual(case,before)


if __name__=='__main__':unittest.main()
