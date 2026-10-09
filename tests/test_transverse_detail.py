"""Physical topology, conservative reporting, UI edits and portable export."""
from copy import deepcopy
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest

from pier_cap.model import evaluate,set_inputs
from pier_cap.transverse import bar_shape,suggested_detail,scheduled_bars,shape_issues,transverse_checks,development_current,development_fingerprint
from pier_cap.transverse_visuals import layout_3d
from pier_cap.visuals import section_figure,elevation_figure,reinforcement_plan_figure,hoop_explanation_html,results_figure
from pier_cap.io import export_bundle,load_case,export_blockpad
from pier_cap.optimizer import search,same_design_basis,governing_check
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


def explicit_case():
    case=default_case();case['inputs'].update(Pile_embed=12,Ready_pile=True)
    e=evaluate(case);case['transverse_detail']=suggested_detail(e)
    return case


class TransverseDetailTests(unittest.TestCase):
    def test_u_is_continuous_over_top_with_independent_bottom_ends(self):
        case=explicit_case();e=evaluate(case)
        run=next(r for r in case['transverse_detail']['runs'] if r['kind']=='pile_u')
        run['shape']={'end_angle':0}
        shape=bar_shape(e,run);pts=shape['points'];middle=case['inputs']['b']/2
        self.assertNotEqual(pts[0],pts[-1])
        self.assertLess(pts[0][0],middle);self.assertGreater(pts[-1][0],middle)
        self.assertLess(pts[0][1],case['inputs']['Pile_embed'])
        # Every segment spanning the centerline is above the embedded pile.
        crossings=[(a,b) for a,b in zip(pts,pts[1:]) if min(a[0],b[0])<middle<max(a[0],b[0])]
        self.assertEqual(len(crossings),1)
        self.assertGreater(min(crossings[0][0][1],crossings[0][1][1]),case['inputs']['Pile_embed'])
        self.assertFalse(any('embedded pile' in s for s in shape_issues(e,run)))

    def test_closed_hoop_at_pile_is_reported_and_too_long_tails_clash(self):
        case=explicit_case();e=evaluate(case)
        run=deepcopy(next(r for r in case['transverse_detail']['runs'] if r['kind']=='pile_u'))
        run['kind']='hoop'
        self.assertTrue(any('embedded pile' in s for s in shape_issues(e,run)))
        run['kind']='pile_u';run['shape']={'end_angle':90,'tail_in':20}
        self.assertTrue(any('embedded pile' in s for s in shape_issues(e,run)))

    def test_starter_respects_pile_zones_without_claiming_development(self):
        case=explicit_case();e=evaluate(case);bars=scheduled_bars(case)
        self.assertTrue(any(b['kind']=='hoop' for b in bars));self.assertTrue(any(b['kind']=='pile_u' for b in bars))
        for r in case['transverse_detail']['runs']:
            self.assertFalse(r['development_confirmed'])
            if r['kind']=='hoop':self.assertFalse(any('embedded pile' in s for s in shape_issues(e,r)))
        self.assertTrue(all(math.isclose(b['station_in']-a['station_in'],case['inputs']['s_G']) for a,b in zip(bars,bars[1:])))

    def test_u_never_adds_flexural_area_or_gets_closed_torsion_credit(self):
        case=explicit_case();active=evaluate(case);ref=deepcopy(case);ref['transverse_detail']['enabled']=False;old=evaluate(ref)
        for name in ('As_P','As_B','As_N'):self.assertEqual(active.value(name),old.value(name))
        self.assertFalse(active.eligible)
        self.assertTrue(all(c.status=='REFERENCE' and c.ratio=='N/A' for c in active.checks if c.key.startswith('Chk_torsteel_')))
        self.assertNotIn('Status_pile_hoops',[c.key for c in active.checks])
        self.assertIn('open',next(c.basis for c in evaluate(set_inputs(case,Tu=1e5)).checks if c.key=='Status_actual_torsion').lower())

    def test_actual_interval_shear_responds_to_selected_bar_area(self):
        case=explicit_case();e=evaluate(case)
        base=[c.ratio for c in e.checks if c.key.startswith('Chk_actual_shear_')]
        for r in case['transverse_detail']['runs']:r['bar']=3
        smaller=[c.ratio for c in evaluate(case).checks if c.key.startswith('Chk_actual_shear_')]
        self.assertEqual(len(base),len(smaller));self.assertTrue(any(b>a for a,b in zip(base,smaller)))
        self.assertTrue(all(b>=a for a,b in zip(base,smaller)))

    def test_vertical_actual_legs_ignore_reference_inclination(self):
        case=explicit_case()
        ratios=lambda c:[x.ratio for x in evaluate(c).checks if x.key.startswith('Chk_actual_shear_')]
        self.assertEqual(ratios(case),ratios(set_inputs(case,alpha_v=30)))

    def test_actual_plot_uses_actual_interval_checks(self):
        e=evaluate(explicit_case());figure=results_figure(e)
        trace=next(t for t in figure.data if t.name.startswith('Actual shear'))
        self.assertEqual(list(trace.y),[c.ratio for c in e.checks if c.key.startswith('Chk_actual_shear_')])
        self.assertFalse(any(t.name=='Shear resistance' for t in figure.data))

    def test_geometry_count_is_identical_in_every_projection_and_export(self):
        case=explicit_case();e=evaluate(case);bars=scheduled_bars(case)
        for fig in (elevation_figure(e),reinforcement_plan_figure(e),layout_3d(e)):
            traces=[t for t in fig.data if t.legendgroup and t.legendgroup.startswith('R')]
            self.assertEqual(len(traces),len(bars))
        self.assertIn('Actual transverse steel',hoop_explanation_html(e))
        self.assertNotIn('Why stationing is pending',hoop_explanation_html(e))
        with tempfile.TemporaryDirectory() as root:
            folder=export_bundle(case,root)
            self.assertEqual(load_case(folder/'selected_case.json')['transverse_detail'],case['transverse_detail'])
            with (folder/'transverse_bar_schedule.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),len(bars))
            self.assertEqual([float(r['station_in']) for r in rows],[r['station_in'] for r in bars])
            self.assertIn('UNIFORM-CAGE REFERENCE ONLY',(folder/'blockpad_inputs.txt').read_text())

    def test_search_and_blockpad_cannot_silently_drop_actual_detail(self):
        case=explicit_case()
        with self.assertRaisesRegex(ValueError,'uniform'):search(case)
        with self.assertRaisesRegex(ValueError,'cannot represent'):export_blockpad('unused',case,'unused')
        other=deepcopy(case);other['transverse_detail']['runs'][0]['pitch_in']+=1
        self.assertFalse(same_design_basis(case,other))

    def test_recorded_development_becomes_pending_after_geometry_or_bar_edit(self):
        case=explicit_case();run=case['transverse_detail']['runs'][0]
        run.update(development_confirmed=True,development_basis='Reviewed detail A')
        run['development_fingerprint']=development_fingerprint(case,run)
        self.assertTrue(development_current(case,run))
        run['bar']=3;self.assertFalse(development_current(case,run))
        run['development_fingerprint']=development_fingerprint(case,run)
        case['inputs']['b']+=1;self.assertFalse(development_current(case,run))

    def test_widget_generate_edit_and_load_keep_exact_run(self):
        app=CapNotebook(default_case())
        try:
            panel=app.transverse_panel;panel.generate.click()
            self.assertTrue(app.case['transverse_detail']['enabled'])
            self.assertIsNotNone(app.current)
            self.assertTrue(panel.generate.disabled)
            run=next(r for r in app.case['transverse_detail']['runs'] if r['kind']=='pile_u')
            card=panel.zone_controls[run['id']];card['bar'].value=5;card['end_angle'].value=180
            card['pitch'].value=7;card['tail_in'].value=4
            applied=next(r for r in app.case['transverse_detail']['runs'] if r['id']==run['id'])
            self.assertEqual(applied['bar'],5);self.assertEqual(applied['pitch_in'],7)
            self.assertEqual(applied['shape']['end_angle'],180)
            saved=deepcopy(app.case);app.load(default_case());self.assertFalse(panel.active.value)
            app.load(saved);self.assertTrue(panel.active.value)
            self.assertEqual(app.case['transverse_detail'],saved['transverse_detail'])
            panel.active.value=False;self.assertEqual(app.case['transverse_detail']['runs'],saved['transverse_detail']['runs'])
        finally:app.close()


if __name__=='__main__':unittest.main()
