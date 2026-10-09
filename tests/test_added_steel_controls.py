"""Entered spacing stays exact, conflicts stay visible, and card checks stay current."""
from copy import deepcopy
import csv
import json
import tempfile
import unittest
from pier_cap.model import evaluate,bar_positions,set_inputs,upgrade_case
from pier_cap.added_steel import layout_settings,added_clearances
from pier_cap.io import load_case,export_bundle
from pier_cap.widgets import CapNotebook
from pier_cap.transverse_zones import starting_zone_detail
from tests.case_fixtures import default_case


def entered_case(**changes):
    case=set_inputs(default_case(),**dict(n_P1=2,n_B1=2,n_B2=2,Bar_P=8,Bar_B=8,**changes))
    case['schema_version']=4;case['added_bar_layout']=layout_settings(case)
    case['added_bar_layout'].update(mode='spacing')
    case['added_bar_layout']['rows']={'1':dict(pitch_in=8.,offset_in=0.),'2':dict(pitch_in=6.,offset_in=1.)}
    return case


class AddedSteelTests(unittest.TestCase):
    def test_exact_row_pitch_and_offset_with_and_without_actual_hoops(self):
        for actual in (False,True):
            case=entered_case()
            if actual:case['transverse_detail']=starting_zone_detail(evaluate(case),5,8)
            e=evaluate(case);p=bar_positions(e,'P');bars=bar_positions(e,'B')
            for k,expected in [(1,[20.,28.]),(2,[22.,28.])]:
                self.assertEqual([b['x'] for b in bars if b['kind']==f'Added span row {k}'],expected)
            changed=deepcopy(case);changed['added_bar_layout']['rows']['1']['pitch_in']=4
            after=evaluate(changed)
            self.assertEqual(bar_positions(after,'P'),p)
            self.assertEqual([b['x'] for b in bar_positions(after) if b['kind']=='Added span row 1'],[22.,26.])
            for name in ('As_P','As_B','Mr_P','Mr_B'):
                self.assertAlmostEqual(e.value(name),after.value(name))

    def test_collisions_and_outside_cover_remain_drawn_and_fail(self):
        case=entered_case();case['inputs']['n_B2']=0
        # Match the two continuous bar centers exactly.
        continuous=[b['x'] for b in bar_positions(evaluate(case),'P') if b['kind']=='Bottom row 1']
        case['added_bar_layout']['rows']['1']['pitch_in']=continuous[-1]-continuous[0]
        e=evaluate(case);c=next(c for c in e.checks if c.key=='Chk_added_clear_1_continuous')
        self.assertEqual(c.status,'FAIL');self.assertGreater(c.ratio,1)
        self.assertEqual([b['x'] for b in bar_positions(e) if b['additional']],continuous)
        case['added_bar_layout']['rows']['1']['pitch_in']=1
        e=evaluate(case);c=next(c for c in e.checks if c.key=='Chk_added_clear_1_added')
        self.assertEqual(c.status,'FAIL');self.assertIn('0.000 in',c.basis)
        case['added_bar_layout']['rows']['1']['offset_in']=100
        e=evaluate(case);self.assertEqual(next(c for c in e.checks if c.key=='Chk_added_fit').status,'FAIL')
        self.assertTrue(all(b['x']>e.case['inputs']['b'] for b in bar_positions(e) if b['additional']))

    def test_current_combined_spacing_used_for_service_and_fast_engine(self):
        case=entered_case();case['inputs'].update(Manual_spacing=True,SP_detail_B=100,SP_detail_P=8)
        slow=evaluate(case);fast=evaluate(case,fast=True)
        xs=sorted(b['x'] for b in bar_positions(slow) if b['layer']=='Bottom row 1')
        expected=max(b-a for a,b in zip(xs,xs[1:]))
        self.assertAlmostEqual(slow.value('SP_B'),expected)
        self.assertAlmostEqual(fast.value('SP_B'),expected)
        self.assertNotEqual(expected,100)

    def test_mixed_bar_sizes_use_surface_gaps(self):
        case=entered_case();case['inputs'].update(Bar_P=8,Bar_B=6,n_B2=0)
        e=evaluate(case);bars=bar_positions(e,'B')
        added=[b for b in bars if b['kind']=='Added span row 1']
        continuous=[b for b in bars if b['kind']=='Bottom row 1']
        result={r['family']:r for r in added_clearances(e,bars)}
        # Bars share the same bottom cover, so the different radii also offset
        # their centers vertically by 1/8 inch.
        dx=min(abs(a['x']-b['x']) for a in added for b in continuous)
        expected=(dx**2+.125**2)**.5-(1.+.75)/2
        self.assertAlmostEqual(result['continuous']['actual'],expected)
        self.assertAlmostEqual(result['added']['actual'],8.-.75)

    def test_json_round_trip_and_reject_invalid_configuration(self):
        case=entered_case();restored=load_case(json.dumps(case).encode())
        self.assertEqual(restored['added_bar_layout'],case['added_bar_layout'])
        self.assertEqual(bar_positions(evaluate(restored)),bar_positions(evaluate(case)))
        for value in (0,-1,float('nan'),True):
            invalid=deepcopy(case);invalid['added_bar_layout']['rows']['1']['pitch_in']=value
            with self.assertRaises(ValueError):evaluate(invalid)
        old=deepcopy(case);old['schema_version']=3
        with self.assertRaisesRegex(ValueError,'schema_version 4'):evaluate(old)

    def test_legacy_auto_layout_is_unchanged(self):
        old=set_inputs(default_case(),n_B1=3);new=deepcopy(old)
        new['schema_version']=4;new['added_bar_layout']=layout_settings(old)
        self.assertEqual(bar_positions(evaluate(old)),bar_positions(evaluate(new)))

    def test_retired_u_legs_have_no_credit_and_conversion_is_explicit(self):
        old=default_case();old['inputs'].update(n_PU=3,n_BU=2,Bar_U=9)
        old['transverse_detail']=starting_zone_detail(evaluate(default_case()),5,8)
        saved=deepcopy(old);e=evaluate(old)
        self.assertEqual(old,saved)
        self.assertEqual(e.case['inputs']['n_PU'],0);self.assertEqual(e.case['inputs']['n_BU'],0)
        self.assertEqual(e.case['transverse_detail'],old['transverse_detail'])
        self.assertIn('3 pile legs and 2 span legs',e.case['retired_u_leg_inventory']['note'])
        self.assertAlmostEqual(e.value('As_P'),(old['inputs']['n_P1']+old['inputs']['n_P2'])*.79)
        app=CapNotebook(old);self.addCleanup(app.close)
        for name in ('n_PU','n_BU','Bar_U'):self.assertNotIn(name,app.controls)
        self.assertIn('no longer credited',app.cage.children[0].value)

    def test_card_readouts_are_relevant_live_and_preserve_widgets(self):
        app=CapNotebook(entered_case());self.addCleanup(app.close)
        cards=dict(app.steel_readouts);plots=dict(app.views.plots)
        before=cards['added'].value
        app.controls['n_B1'].value=4
        self.assertNotEqual(cards['added'].value,before)
        self.assertEqual(app.steel_readouts,cards)
        self.assertEqual(app.views.plots,plots)
        for key,code in [('top','N'),('continuous','P'),('added','B')]:
            ratio=next(c.ratio for c in app.current.checks if c.key=='Chk_flex_'+code)
            self.assertIn(f'{ratio:.3f}',cards[key].value)
        self.assertNotIn('flexure',cards['side'].value.lower())
        self.assertIn('Skin area',cards['side'].value)
        self.assertIn('added–continuous',cards['added'].value)
        app.added_steel.rows[1]['pitch_in'].value=.5
        self.assertIn('FAIL',cards['added'].value)
        self.assertFalse(app.added_steel.rows[1]['pitch_in'].disabled)
        app.controls['b'].value=0
        self.assertTrue(all('unavailable' in w.value for w in cards.values()))
        app.controls['b'].value=48
        self.assertIsNotNone(app.current)

    def test_export_contains_settings_positions_and_separate_clearance_checks(self):
        case=entered_case()
        with tempfile.TemporaryDirectory() as folder:
            root=export_bundle(case,folder)
            restored=load_case(root/'selected_case.json')
            self.assertEqual(restored['added_bar_layout'],case['added_bar_layout'])
            with (root/'longitudinal_bar_positions.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            self.assertEqual([float(r['Across cap (in)']) for r in rows if r['Layer']=='Added span row 1'],[20.,28.])
            self.assertIn('Added to continuous',(root/'checks.csv').read_text(encoding='utf-8-sig'))
            self.assertIn('Row 1: 8 in c/c',(root/'reinforcement_detail.html').read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
