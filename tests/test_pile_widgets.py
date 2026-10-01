from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch
from pier_cap.widgets import CapNotebook
from pier_cap.pile_review import import_pile_xml
from pier_cap.pile_widgets import profile_figure

FIXTURES=Path(__file__).parent/'fixtures'


class PileWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review=import_pile_xml(FIXTURES/'fbmp_610_piles.xml')

    def setUp(self):
        self.app=CapNotebook()
        self.panel=self.app.pile_review

    def tearDown(self):
        self.app.close()

    def test_review_is_above_steel_and_independent_source_is_explicit(self):
        self.panel.set_review(self.review)
        children=list(self.app.ui.children)
        self.assertLess(children.index(self.panel.ui),children.index(self.app.search_panel))
        self.assertIn('different source',self.panel.source_match.value)
        self.assertEqual(self.panel.combo.value,'4')
        self.panel.combo.value='2';self.panel.pile.value='1'
        self.assertIn('Pile 1',self.panel.figures['profiles'].layout.title.text)
        self.panel.cutoff.value='40'
        self.assertEqual(self.panel.figures['profiles'].data[0].y[0],40)
        self.assertAlmostEqual(self.panel.figures['profiles'].data[0].y[-1],-35)

    def test_trial_edits_clear_old_result_and_new_run_clears_trial_assumptions(self):
        self.panel.set_review(self.review)
        self.panel.trial_text.value=(FIXTURES/'pile_minimum_tip_reference.csv').read_text()
        self.panel._trials()
        self.assertAlmostEqual(self.panel.trial_result['proposed_embedment_ft'],32.74)
        self.assertIsNone(self.panel.trial_result['tip_elevation_ft'])
        self.panel.accepted.value='32.74';self.panel.reference.value='24.5'
        self.panel.trial_basis.value='Reviewed workbook trial selection'
        self.panel._trials()
        self.assertAlmostEqual(self.panel.trial_result['tip_elevation_ft'],-13.24)
        self.panel.extension.value=4
        self.assertIsNone(self.panel.trial_result)
        self.assertEqual(self.panel.trial_output.children,())
        self.panel.set_review(self.review)
        self.assertEqual(self.panel.trial_text.value,'')
        self.assertEqual(self.panel.reference.value,'')

    def test_restore_and_export_recalculate_and_retain_provenance(self):
        self.panel.set_review(self.review)
        self.panel.combo.value='2';self.panel.pile.value='3'
        self.panel.trial_text.value=(FIXTURES/'pile_minimum_tip_reference.csv').read_text()
        self.panel.accepted.value='32.74';self.panel.reference.value='24.5'
        self.panel.trial_basis.value='Engineer-selected example'
        state=self.panel.snapshot()
        self.panel.set_review(self.review)
        self.panel.restore(state)
        self.assertEqual(self.panel.combo.value,'2');self.assertEqual(self.panel.pile.value,'3')
        with TemporaryDirectory() as folder:
            self.panel.save_bundle(folder)
            saved=json.loads((Path(folder)/'pile_review.json').read_text())
            self.assertEqual(saved['review']['sha256'],self.review['sha256'])
            self.assertIn('uplift_kip',(Path(folder)/'pile_heads.csv').read_text(encoding='utf-8-sig'))
            self.assertIn('Geotechnical handoff',(Path(folder)/'pile_review.html').read_text(encoding='utf-8'))
            self.panel.accepted.value='bad'
            with self.assertRaises(ValueError):self.panel.save_bundle(Path(folder)/'invalid')

    def test_cap_type_and_cap_changes_do_not_change_pile_forces(self):
        self.panel.set_review(self.review)
        self.app.cap_type.value='End-bent pile cap'
        self.assertEqual(self.app.case['cap_type'],'End-bent pile cap')
        old=self.panel.review['forces'][0].copy()
        self.app.controls['b'].value+=4
        self.assertEqual(self.panel.review['forces'][0],old)
        self.assertIn('different source',self.panel.source_match.value)

    def test_invalid_saved_results_do_not_replace_active_review(self):
        self.panel.set_review(self.review)
        state=self.panel.snapshot()
        state['review']['forces'][0]['axial']=float('nan')
        with self.assertRaises(ValueError):self.panel.restore(state)
        self.assertEqual(self.panel.review['forces'][0]['axial'],self.review['forces'][0]['axial'])


if __name__=='__main__':unittest.main()
