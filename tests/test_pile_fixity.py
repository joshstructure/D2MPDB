from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from pier_cap.pile_fixity import zero_crossings, displacement_fixity, compare_minimum_tip
from pier_cap.pile_review import evaluate_trials, parse_trials, import_pile_xml
from pier_cap.widgets import CapNotebook

FIXTURES = Path(__file__).parent/'fixtures'


def profile(values, *, pile='1', combo='1', spacing=10, batter=1):
    return [dict(combination=combo, pile=pile, node=str(i+1), state='STRENGTH-I',
        distance_ft=i*spacing*batter, vertical_ft=i*spacing, dx=x, dy=0.) for i,x in enumerate(values)]


def review(rows):
    return dict(displacements=rows, piles={r['pile']:{} for r in rows},
                combinations={r['combination']:r['state'] for r in rows})


class CrossingTests(unittest.TestCase):
    def test_interpolation_second_not_last_and_signed_components(self):
        rows = profile([2,-2,-1,3,-3])
        result = displacement_fixity(review(rows), cutoff=40, ground=30)
        p = result['governors'][0]
        self.assertEqual([c['vertical_ft'] for c in p['crossings']], [5,22.5,35])
        self.assertEqual(p['second_elevation_ft'],17.5)
        self.assertEqual(p['critical_embedment_ft'],12.5)
        self.assertEqual(p['component'],'DX'); self.assertTrue(result['complete'])
        self.assertEqual(p['crossings'][1]['upper_node'],'3')

    def test_zero_nodes_plateaus_touches_and_tails(self):
        for values, expected in [([0,1,0,-1,0,1,0],[2,4]), ([1,0,0,-1,0,1],[2,4]),
                                 ([1,0,1,-1,1],[2.5,3.5]), ([1,0,0],[]), ([0,0,0],[])]:
            with self.subTest(values=values):
                self.assertEqual([c['vertical_ft'] for c in zero_crossings(profile(values,spacing=1),'dx')],expected)
        self.assertEqual(zero_crossings(profile([1,0,0,-1],spacing=1),'dx')[0]['method'],
                         'Zero-band interval; deeper end used')

    def test_noise_missing_crossings_order_and_bad_stations(self):
        data = profile([1,-1,1e-8,-1e-8,0])
        result = displacement_fixity(review(data))
        self.assertEqual(result['unresolved_count'],1); self.assertFalse(result['complete'])
        self.assertFalse(result['governors'])
        self.assertEqual(zero_crossings(list(reversed(data)),'dx'),zero_crossings(data,'dx'))
        with self.assertRaisesRegex(ValueError,'without duplicates'):zero_crossings(data+[data[-1]],'dx')
        with self.assertRaisesRegex(ValueError,'Zero band'):zero_crossings(data,'dx',-1)

    def test_deepest_across_piles_combinations_and_directions_uses_vertical_depth(self):
        rows = profile([1,-1,1],pile='1',combo='1',spacing=10,batter=2)
        rows += profile([1,-1,1],pile='2',combo='2',spacing=20,batter=1.2)
        for r in rows:
            if r['pile']=='2':r['dy'],r['dx']=r['dx'],0
        # All expected pile/combination pairs exist, with other profiles inactive.
        rows += profile([0,0,0],pile='1',combo='2')+profile([0,0,0],pile='2',combo='1')
        result=displacement_fixity(review(rows),cutoff=10,ground=0)
        p=result['governors'][0]
        self.assertEqual((p['pile'],p['combination'],p['component']),('2','2','DY'))
        self.assertEqual(p['second_vertical_ft'],30); self.assertEqual(p['second_distance_ft'],36)
        self.assertEqual(p['second_elevation_ft'],-20)
        self.assertEqual(p['critical_embedment_ft'],20)


class TipComparisonTests(unittest.TestCase):
    def setUp(self):
        self.fixity=displacement_fixity(review(profile([1,-1,1],spacing=20)),cutoff=10,ground=0)

    def compare(self, depth, **kwargs):
        trials=evaluate_trials(parse_trials(f'1,1,1,{depth},1\n2,1,1,{depth-5},1.01'),reference_elevation=0,cutoff_elevation=10)
        return compare_minimum_tip(trials,self.fixity,ground=0,cutoff=10,**kwargs)

    def test_either_criterion_can_control_and_ties_are_named(self):
        for depth,label,tip in [(10,'Second zero crossing',-25),(30,'Displacement-change trials',-35),
                                (20,'Displacement-change trials + Second zero crossing (tie)',-25)]:
            result=self.compare(depth)
            self.assertEqual(result['controlling_criterion'],label)
            self.assertEqual(result['tip_elevation_ft'],tip); self.assertTrue(result['comparison_complete'])
        self.assertEqual(self.compare(10,add_fixity_allowance=False)['tip_elevation_ft'],-20)

    def test_missing_data_never_becomes_zero_or_complete(self):
        f=displacement_fixity(review(profile([1,-1,0])),cutoff=10,ground=0)
        result=compare_minimum_tip(None,f,ground=0,cutoff=10)
        self.assertIsNone(result['tip_elevation_ft']);self.assertFalse(result['comparison_complete'])
        result=compare_minimum_tip(None,self.fixity,ground=0,cutoff=10)
        self.assertEqual(result['tip_elevation_ft'],-25);self.assertFalse(result['comparison_complete'])
        f=displacement_fixity(review(profile([1,-1,1],spacing=20)),ground=0)
        self.assertIsNone(compare_minimum_tip(None,f,ground=0)['tip_elevation_ft'])

    def test_fraction_and_rounding_use_same_datum(self):
        f=displacement_fixity(review(profile([1,-1,1],spacing=20)),cutoff=10.25,ground=-.5)
        result=compare_minimum_tip(None,f,ground=-.5,cutoff=10.25,mode='fraction',fraction=.2,round_feet=True)
        self.assertAlmostEqual(result['required_embedment_ft'],19.25*1.2)
        self.assertEqual(result['tip_elevation_ft'],-24);self.assertEqual(result['total_length_ft'],35)


class FixityWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook();self.panel=self.app.pile_review
        data=import_pile_xml(FIXTURES/'fbmp_610_piles.xml')
        for r in data['displacements']:
            r['dx']=r['dy']=r['lateral_in']=0.
            if r['pile']=='3' and r['combination']=='2':
                z=r['vertical_ft'];r['dy']=5-z if z<=25 else z-45
                r['lateral_in']=abs(r['dy'])
        self.panel.set_review(data)
        self.panel.cutoff.value='40';self.panel.reference.value='30'
        self.panel.trial_text.value='1,2,3,20,1\n2,2,3,15,1.01';self.panel.run_trials.click()

    def tearDown(self):self.app.close()

    def test_plot_selection_does_not_change_governor_and_edits_update_every_view(self):
        p=self.panel;r=p.minimum_tip_result
        self.assertEqual(r['tip_elevation_ft'],-10);self.assertTrue(r['comparison_complete'])
        self.assertIn('Second zero crossing',p.minimum_tip_summary.value)
        self.assertIn('Pile 3',p.fixity_summary.value)
        p.combo.value='2';p.piles.value=('3',)
        markers=[t for t in p.figures['profiles'].data if t.meta and t.meta.get('part')=='fixity']
        self.assertEqual([t.y[0] for t in markers],[35,-5])
        self.assertTrue(any(s.y0==-10 for s in p.figures['profiles'].layout.shapes if s.yref=='y'))
        p.piles.value=('1',)
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-10)
        p.fixity_allowance.value=False
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-5)
        self.assertIn('-5.000 ft',p.handoff.value)
        p.cutoff.value='41'
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-4)

    def test_saved_review_and_exports_keep_criterion_and_coordinates(self):
        p=self.panel;p.fixity_allowance.value=False
        state=p.snapshot();p.restore(state)
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-5)
        with TemporaryDirectory() as folder:
            p.save_bundle(folder);folder=Path(folder)
            result=json.loads((folder/'minimum_tip_result.json').read_text())
            self.assertEqual(result['controlling_criterion'],'Second zero crossing')
            self.assertEqual(result['tip_elevation_ft'],-5)
            self.assertIn('Second zero crossing',(folder/'geotech_handoff.html').read_text(encoding='utf-8'))
            self.assertTrue((folder/'pile_zero_crossings.csv').exists())
            self.assertTrue((folder/'minimum_tip_criteria.csv').exists())

    def test_profile_only_and_invalid_inputs_clear_stale_result(self):
        p=self.panel;p.zero_band.value=-1
        self.assertIsNone(p.minimum_tip_result)
        self.assertIn('MINIMUM TIP INPUT NEEDS REVIEW',p.trial_status.value)
        p.zero_band.value=1e-6
        self.assertTrue(p.minimum_tip_result['comparison_complete'])
        p.trial_text.value='';p.run_trials.click()
        self.assertEqual(p.minimum_tip_result['tip_elevation_ft'],-10)
        self.assertFalse(p.minimum_tip_result['comparison_complete'])
        p.zero_band.value=-1
        self.assertIsNone(p.minimum_tip_result)
        self.assertIn('Zero band',p.minimum_tip_summary.value)
        self.assertNotIn('-10.000 ft',p.handoff.value)

    def test_invalid_saved_zero_band_does_not_replace_active_review(self):
        p=self.panel;before=p.snapshot();state=deepcopy(before)
        state['controls']['zero_band']=-1
        with self.assertRaisesRegex(ValueError,'Zero band'):p.restore(state)
        self.assertEqual(p.snapshot(),before)


if __name__=='__main__':unittest.main()
