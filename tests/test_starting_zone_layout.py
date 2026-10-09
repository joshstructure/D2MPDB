"""Zone-end bars share one regular pitch in drawings, checks and saved cases."""
from copy import deepcopy
import csv
import json
import tempfile
import unittest
from pier_cap.model import evaluate
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
            for left,right in zip(stations[:-2],stations[1:-1]):self.assertAlmostEqual(right-left,7)
            self.assertLessEqual(stations[-1]-stations[-2],7+1e-7)
            self.assertFalse(run['development_confirmed'])

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
        panel=self.app.transverse_panel;panel.generate.click()
        before=[b['station_in'] for b in scheduled_bars(self.app.case)]
        rid=next(r['id'] for r in self.app.case['transverse_detail']['runs'] if len(run_stations(r))>2)
        panel.zone_controls[rid]['split'].click()
        self.assertEqual([b['station_in'] for b in scheduled_bars(self.app.case)],before)
        panel.zone_controls[rid]['include_end_bar'].value=False
        self.assertFalse(next(r for r in self.app.case['transverse_detail']['runs'] if r['id']==rid)['include_end_bar'])

    def test_enabling_end_bar_upgrades_legacy_layout_format(self):
        panel=self.app.transverse_panel;panel.add.click()
        self.assertEqual(self.app.case['transverse_detail']['version'],1)
        rid=self.app.case['transverse_detail']['runs'][0]['id']
        panel.zone_controls[rid]['include_end_bar'].value=True
        self.assertEqual(self.app.case['transverse_detail']['version'],2)
        self.assertTrue(self.app.case['transverse_detail']['runs'][0]['include_end_bar'])


if __name__=='__main__':unittest.main()
