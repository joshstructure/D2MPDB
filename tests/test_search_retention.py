"""Manual cage experiments must not discard the completed search population."""
from copy import deepcopy
import json
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pier_cap.model import set_inputs
from pier_cap.optimizer import REINFORCEMENT_INPUTS,SearchConfig,search,same_design_basis
from pier_cap.sections import SectionGrid,run_section_study
from pier_cap.section_widgets import SectionStudy
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


CHOICES=SearchConfig(main_bars=(7,8),top_counts=(6,8),bottom_counts=(6,8),
    hoop_bars=(5,),hoop_spacings=(6,8),skin_bars=(5,),skin_counts=(6,7))


class SearchRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=search(default_case(),CHOICES)
        cls.study_result=run_section_study(default_case(),
            SectionGrid(widths=(48,),depths=(36,48)),CHOICES)

    def setUp(self):
        self.folder=TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.app=CapNotebook(default_case(),export_root=self.folder.name)
        self.addCleanup(self.app.close)
        self.panel=SectionStudy(self.app);self.addCleanup(self.panel.close)
        self.app.search_result=self.result;self.app._render_candidates()
        self.panel.study=self.study_result;self.panel._render()

    def test_bar_edits_preserve_population_filters_page_selection_and_plots(self):
        self.app.next_page.click()
        self.app.candidates.value=self.app.candidates.options[-1][1]
        self.panel.cage.value=self.panel.cage.options[-1][1]
        saved=(self.app.page.value,self.app.candidates.value,self.app.dc_limit.value,
               self.app.dc_scope.value,tuple(self.app.filtered_indices),
               self.panel.section.value,self.panel.cage.value,self.panel.target.value)
        plot=self.app.alternative_figure;plots=list(self.panel.figures)
        before=deepcopy(self.result.base_case)
        with (patch('pier_cap.widgets.search',side_effect=AssertionError('Unexpected rerun')),
              patch('pier_cap.section_widgets.run_section_study',side_effect=AssertionError('Unexpected rerun'))):
            self.app.controls['n_skin'].value=0
            self.app.controls['Bar_P'].value=7
            self.app.controls['n_N2'].value=2
        self.assertIs(self.app.search_result,self.result)
        self.assertIs(self.panel.study,self.study_result)
        self.assertIs(self.app.alternative_figure,plot)
        self.assertEqual(self.panel.figures,plots)
        self.assertEqual(saved,(self.app.page.value,self.app.candidates.value,self.app.dc_limit.value,
            self.app.dc_scope.value,tuple(self.app.filtered_indices),
            self.panel.section.value,self.panel.cage.value,self.panel.target.value))
        self.assertEqual(self.result.base_case,before)
        self.assertIn('RETAINED',self.app.search_notice.value)
        self.assertIn('RETAINED',self.panel.notice.value)
        self.assertEqual(self.app.current.case['inputs']['n_skin'],0)
        self.app.apply_button.click()
        for name,value in self.result.candidates[saved[1]].changes.items():
            self.assertEqual(self.app.case['inputs'][name],value)
        self.assertIs(self.panel.study,self.study_result)

    def test_invalid_trial_bar_entry_can_be_replaced_by_retained_candidate(self):
        self.app.controls['s_G'].value=0
        self.assertIsNone(self.app.current)
        self.assertIs(self.app.search_result,self.result)
        self.assertIs(self.panel.study,self.study_result)
        self.assertFalse(self.app.apply_button.disabled)
        self.app.apply_button.click()
        self.assertIsNotNone(self.app.current)
        self.assertTrue(self.app.current.eligible)

    def test_study_selection_remains_after_loading_a_different_section_and_editing_bars(self):
        self.panel.section.value=0
        self.assertEqual(self.study_result.points[0].depth,36)
        chosen=self.panel.cage.value
        self.panel.apply_button.click()
        self.assertEqual(self.app.case['inputs']['h'],36)
        self.app.controls['n_skin'].value=0
        self.assertIs(self.panel.study,self.study_result)
        self.assertEqual(self.panel.cage.value,chosen)
        self.panel.apply_button.click()
        self.assertEqual(self.app.case['inputs']['n_skin'],
                         self.study_result.points[0].result.candidates[chosen].changes['n_skin'])
        self.assertEqual(self.app.case['analysis'],self.study_result.base_case['analysis'])

    def test_load_or_material_change_still_invalidates_both_searches(self):
        for name,value in (('Mu_B',500),('fy',70),('C_pile',2),('fc',0)):
            with self.subTest(name=name):
                self.app.load(default_case())
                self.app.search_result=self.result;self.app._render_candidates()
                self.panel.study=self.study_result;self.panel._render()
                self.app.controls[name].value=value
                self.assertIsNone(self.app.search_result)
                self.assertIsNone(self.panel.study)
                self.assertTrue(self.app.apply_button.disabled)
                self.assertTrue(self.panel.apply_button.disabled)
                self.app.controls['n_skin'].value=0
                self.assertIsNone(self.panel.study)

    def test_export_distinguishes_edited_cage_from_completed_search_basis(self):
        self.app.controls['n_skin'].value=0
        self.app.controls['S_leg_detail'].value=30
        self.app._export(None)
        out=self.app.last_export
        self.assertIsNotNone(out,self.app.message.value)
        selected=json.loads((out/'selected_case.json').read_text(encoding='utf-8'))
        basis=json.loads((out/'search_base_case.json').read_text(encoding='utf-8'))
        self.assertEqual(selected,self.app.case)
        self.assertEqual(basis,self.result.base_case)
        self.assertNotEqual(selected['inputs']['n_skin'],basis['inputs']['n_skin'])
        manifest=json.loads((out/'review.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['search']['base_case_file'],'search_base_case.json')


class SearchBasisTests(unittest.TestCase):
    def test_only_reinforcement_inputs_are_exempt_from_invalidation(self):
        case=default_case()
        for name,value in case['inputs'].items():
            with self.subTest(name=name):
                changed=set_inputs(case,**{name:not value if isinstance(value,bool) else value+1})
                self.assertEqual(same_design_basis(case,changed),name in REINFORCEMENT_INPUTS)
        for key in ('analysis','screening','units'):
            changed=deepcopy(case);changed[key]['changed']=True
            self.assertFalse(same_design_basis(case,changed))


if __name__=='__main__':
    unittest.main()
