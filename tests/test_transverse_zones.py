"""Zone edits retain exact runs and use the same physical schedule as the views."""
from copy import deepcopy
import json
import unittest

from pier_cap.model import evaluate,set_inputs
from pier_cap.io import load_case
from pier_cap.transverse import suggested_detail,scheduled_bars,development_fingerprint
from pier_cap.transverse_zones import cap_zones,zone_runs,new_zone_run
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


def zoned_case():
    case=default_case();case['transverse_detail']=suggested_detail(evaluate(case))
    return case


class TransverseZoneTests(unittest.TestCase):
    def test_starter_maps_to_ordered_physical_zones_without_mutation(self):
        case=zoned_case();before=deepcopy(case)
        zones,groups,custom=zone_runs(evaluate(case))
        self.assertEqual([z['key'] for z in zones],['left','P1','S1','P2','S2','P3','S3','P4','right'])
        self.assertFalse(custom)
        self.assertEqual({r['id'] for group in groups.values() for r in group},{r['id'] for r in case['transverse_detail']['runs']})
        for run in case['transverse_detail']['runs']:
            key=next(k for k,group in groups.items() if run in group)
            for size in (3,11):
                run['bar']=size
                self.assertIn(run,zone_runs(evaluate(case))[1][key])
            run['bar']=next(r['bar'] for r in before['transverse_detail']['runs'] if r['id']==run['id'])
        self.assertEqual(case,before)

    def test_custom_crossing_run_remains_separate_and_add_does_not_overwrite_it(self):
        case=default_case();case['transverse_detail']={'version':1,'enabled':True,'runs':[
            dict(id='Custom',kind='hoop',bar=5,zone='L',first_in=4,end_in=200,pitch_in=8)]}
        before=deepcopy(case);e=evaluate(case)
        zones,groups,custom=zone_runs(e)
        self.assertEqual([r['id'] for r in custom],['Custom'])
        self.assertFalse(any(groups.values()))
        with self.assertRaisesRegex(ValueError,'custom run'):new_zone_run(e,'S1',6,7)
        self.assertEqual(case,before)

    def test_add_zone_respects_cover_neighbors_and_unique_identifier(self):
        case=zoned_case();e=evaluate(case);_,groups,_=zone_runs(e)
        removed={r['id'] for r in groups['P2']}
        case['transverse_detail']['runs']=[r for r in case['transverse_detail']['runs'] if r['id'] not in removed]
        before=deepcopy(case);e=evaluate(case)
        run=new_zone_run(e,'P2',5,6)
        self.assertEqual(run['kind'],'pile_u');self.assertEqual(run['zone'],'G')
        self.assertEqual(run['pitch_in'],6);self.assertFalse(run['development_confirmed'])
        self.assertNotIn(run['id'],[r['id'] for r in case['transverse_detail']['runs']])
        self.assertEqual(case,before)
        case['transverse_detail']['runs'].append(run)
        self.assertIn(run,zone_runs(evaluate(case))[1]['P2'])
        with self.assertRaisesRegex(ValueError,'already has a run'):new_zone_run(evaluate(case),'P2',5,6)

    def test_geometry_changes_only_regroup_runs(self):
        case=zoned_case();saved=deepcopy(case['transverse_detail'])
        changed=set_inputs(case,S_pile=6,N_pile=5)
        zones,groups,custom=zone_runs(evaluate(changed))
        self.assertEqual(len(zones),11)
        self.assertEqual(changed['transverse_detail'],saved)
        self.assertEqual(sum(map(len,groups.values()))+len(custom),len(saved['runs']))


class ZoneWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook(zoned_case())
        self.addCleanup(self.app.close)

    def test_controls_follow_elevation_and_reference_controls_are_below_zones(self):
        app=self.app;panel=app.transverse_panel
        index=app.cage.children.index(panel.ui)
        self.assertIn('SIDE ELEVATION',app.cage.children[index-1].layout.title.text)
        self.assertNotIn(panel.ui,app.ui.children)
        self.assertIn(app.hoop_reference_inputs,panel.general.children)
        for name in ('Bar_v','n_loop','s_G','s_L'):
            self.assertIn(app.controls[name],app.hoop_reference_inputs.children)

    def test_zone_size_spacing_update_current_plots_and_round_trip_exact_case(self):
        app=self.app;panel=app.transverse_panel
        _,groups,_=zone_runs(app.current);rid=groups['P2'][0]['id']
        run=next(r for r in app.case['transverse_detail']['runs'] if r['id']==rid)
        run['shape']={'end_angle':135,'inside_diameter_in':4,'tail_in':3}
        run.update(development_confirmed=True,development_basis='Checked test detail')
        run['development_fingerprint']=development_fingerprint(app.case,run)
        before=deepcopy(app.case);controls=panel.zone_controls[rid]
        panel.zone_controls[rid]['bar'].value=6
        panel.zone_controls[rid]['pitch'].value=6
        changed=next(r for r in app.case['transverse_detail']['runs'] if r['id']==rid)
        old=next(r for r in before['transverse_detail']['runs'] if r['id']==rid)
        for key in ('first_in','end_in','kind','zone','shape','development_basis'):
            self.assertEqual(changed[key],old[key])
        self.assertNotEqual(changed['bar'],old['bar'])
        self.assertEqual(changed['bar'],6);self.assertEqual(changed['pitch_in'],6)
        self.assertFalse(changed['development_confirmed']);self.assertNotIn('development_fingerprint',changed)
        self.assertIs(panel.zone_controls[rid]['pitch'],controls['pitch'])
        for run in app.case['transverse_detail']['runs']:
            if run['id']!=rid:self.assertEqual(run,next(r for r in before['transverse_detail']['runs'] if r['id']==run['id']))
        bars=[b for b in scheduled_bars(app.case) if b['run']==rid]
        elevation=app.cage.children[app.cage.children.index(panel.ui)-1]
        traces=[t for t in elevation.data if t.legendgroup==rid]
        self.assertEqual(len(traces),len(bars))
        self.assertEqual([t.x[0]*12 for t in traces],[b['station_in'] for b in bars])
        self.assertTrue(all('#6 @ 6 in' in t.name for t in traces))
        saved=load_case(json.dumps(app.case).encode())
        app.load(saved)
        self.assertEqual(app.case['transverse_detail'],saved['transverse_detail'])
        self.assertEqual(panel.zone_controls[rid]['bar'].value,6)
        self.assertEqual(panel.zone_controls[rid]['pitch'].value,6)

    def test_invalid_spacing_reverts_control_and_reports_error(self):
        app=self.app;panel=app.transverse_panel;before=deepcopy(app.case)
        rid=next(iter(panel.zone_controls));pitch=panel.zone_controls[rid]['pitch']
        original=pitch.value;pitch.value=0
        self.assertEqual(app.case,before);self.assertEqual(pitch.value,original)
        self.assertIn('Not applied',panel.status.value)
        self.assertIn('positive pitch',panel.status.value)
        self.assertIn('positive pitch',panel.zone_controls[rid]['error'].value)

    def test_empty_zone_adds_selected_size_and_pitch_without_filling_other_zones(self):
        app=self.app;app.load(default_case());panel=app.transverse_panel
        card=panel._empty_zones['P1']
        card['bar'].value=6;card['pitch'].value=7;card['button'].click()
        runs=app.case['transverse_detail']['runs']
        self.assertEqual(len(runs),1)
        self.assertEqual((runs[0]['kind'],runs[0]['bar'],runs[0]['pitch_in']),('pile_u',6,7))
        self.assertTrue(panel.active.value)
        self.assertEqual(zone_runs(app.current)[1]['P1'],runs)

    def test_disabled_layout_retains_runs_and_invalid_reference_input_is_recoverable(self):
        app=self.app;panel=app.transverse_panel;saved=deepcopy(app.case['transverse_detail']['runs'])
        panel.active.value=False
        self.assertTrue(all(c['pitch'].disabled for c in panel.zone_controls.values()))
        self.assertEqual(app.case['transverse_detail']['runs'],saved)
        app.controls['s_G'].value=0
        self.assertIsNone(app.current)
        self.assertIn(panel.ui,app.cage.children)
        app.controls['s_G'].value=9
        self.assertIsNotNone(app.current)
        self.assertEqual(panel.zone_grid.layout.display,'')


if __name__=='__main__':unittest.main()
