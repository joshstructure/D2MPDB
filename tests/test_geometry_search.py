"""Width/depth experiments must support search, apply, export and reload."""
from copy import deepcopy
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pier_cap.io import load_case, export_bundle
from pier_cap.model import analysis_match, evaluate, sectional_checks_pass
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


def small_search(app):
    choices=dict(main_bars=(8,),top_counts=(8,),pile_bars=(8,),span_bars=(8,),
                 pile_counts=(8,),span_counts=(8,),hoop_bars=(5,),hoop_spacings=(8,),
                 skin_bars=(5,),skin_counts=(6,7))
    for name, values in choices.items():
        app.search_lists[name].value=values


class GeometrySearchTests(unittest.TestCase):
    def setUp(self):
        self.folder=TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app=CapNotebook(default_case(),export_root=self.folder.name)
        self.addCleanup(self.app.close)
        small_search(self.app)

    def test_width_and_depth_edits_search_with_original_forces(self):
        original=deepcopy(self.app.case)
        for key,value in [('b',44),('h',54)]:
            with self.subTest(dimension=key):
                self.app.load(original)
                self.app.controls[key].value=value
                self.assertIn('TRIAL CAP SIZE',self.app.search_force_notice.value)
                self.assertIn('TRIAL CAP SIZE',self.app.banner.value)
                # The strict matched-analysis API must not be called here.
                with patch('pier_cap.widgets.search',side_effect=AssertionError('Strict search used for trial size')):
                    self.app.run_button.click()
                result=self.app.search_result
                self.assertIsNotNone(result,self.app.search_text.value)
                self.assertEqual(result.force_mode,'fixed')
                self.assertGreater(result.passed,0)
                self.assertIn('unchanged forces',self.app.search_text.value)
                self.assertFalse(self.app.run_button.disabled)
                self.assertEqual(self.app.case['analysis'],original['analysis'])
                for force in ('Mu_N','Mu_P','Mu_B','Vu_G','Vu_L','Tu','MI_N','MI_P','MI_B'):
                    self.assertEqual(self.app.case['inputs'][force],original['inputs'][force])
                self.app.apply_button.click()
                self.assertEqual(self.app.case['inputs'][key],value)
                self.assertEqual(self.app.case['analysis'],original['analysis'])
                self.assertTrue(sectional_checks_pass(self.app.current))
                self.assertFalse(self.app.current.eligible)
                self.assertEqual(analysis_match(self.app.case),[key])

    def test_fixed_force_search_can_filter_export_reload_and_search_again(self):
        original=deepcopy(self.app.case['analysis'])
        self.app.controls['b'].value=44
        self.app.run_button.click()
        self.assertIsNotNone(self.app.search_result,self.app.search_text.value)
        self.app.dc_limit.value=.95
        self.app.dc_limit.value=1
        self.app.apply_button.click()
        self.app._export(None)
        self.assertIsNotNone(self.app.last_export,self.app.message.value)
        folder=self.app.last_export
        manifest=json.loads((folder/'review.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['search']['force_mode'],'fixed')
        self.assertEqual(manifest['stale_geometry'],['b'])
        self.assertIn('not reanalyzed',manifest['search']['basis'])
        self.assertIn('Analyzed section: 48 x 48', (folder/'trial_geometry.txt').read_text(encoding='utf-8'))
        for name in ('alternatives.csv','filtered_alternatives.csv'):
            with (folder/name).open(encoding='utf-8-sig',newline='') as source:
                rows=list(csv.DictReader(source))
            self.assertTrue(rows)
            self.assertTrue(all(r['Force basis']=='Fixed forces — width/depth trial' for r in rows))
        restored=load_case(folder/'selected_case.json')
        self.assertEqual(restored['analysis'],original)
        self.assertEqual(restored['inputs']['b'],44)
        self.assertFalse(evaluate(restored).eligible)
        self.app.load(restored)
        self.app.run_button.click()
        self.assertEqual(self.app.search_result.force_mode,'fixed')
        self.assertGreater(self.app.search_result.passed,0)

    def test_return_to_analyzed_dimensions_restores_matched_search(self):
        self.app.controls['b'].value=44
        self.app.run_button.click()
        self.app.controls['b'].value=48
        self.assertIsNone(self.app.search_result)
        self.assertEqual(self.app.search_force_notice.value,'')
        with patch('pier_cap.widgets.sensitivity_search',side_effect=AssertionError('Unexpected trial search')):
            self.app.run_button.click()
        self.assertEqual(self.app.search_result.force_mode,'matched')
        self.app.apply_button.click()
        self.assertTrue(self.app.current.eligible)

    def test_no_passing_cages_is_a_completed_search_not_a_geometry_error(self):
        self.app.controls['b'].value=52
        self.app.run_button.click()
        self.assertIsNotNone(self.app.search_result,self.app.search_text.value)
        self.assertEqual(self.app.search_result.passed,0)
        self.assertIn('No passing cages',self.app.search_text.value)
        self.assertNotIn('Search stopped',self.app.search_text.value)
        self.assertFalse(self.app.run_button.disabled)

    def test_pile_layout_and_missing_pile_head_inputs_keep_specific_feedback(self):
        self.app.controls['b'].value=44
        self.app.controls['N_pile'].value=5
        self.app.run_button.click()
        self.assertIsNone(self.app.search_result)
        self.assertIn('PILE LAYOUT / CAP ENDS',self.app.search_force_notice.value)
        self.assertIn('matching analysis',self.app.search_text.value)
        self.assertFalse(self.app.run_button.disabled)
        self.app.controls['N_pile'].value=4
        self.app.controls['Ready_pile'].value=False
        self.app.run_button.click()
        self.assertIsNone(self.app.search_result)
        self.assertIn('Confirm pile-head',self.app.search_text.value)
        self.assertFalse(self.app.run_button.disabled)

    def test_export_rejects_a_search_from_different_geometry_or_loads(self):
        self.app.controls['b'].value=44
        self.app.run_button.click()
        result=self.app.search_result
        changed=deepcopy(self.app.case)
        changed['inputs']['Mu_B']+=10
        with self.assertRaisesRegex(ValueError,'no longer match'):
            export_bundle(changed,self.folder.name,result)


if __name__=='__main__':
    unittest.main()
