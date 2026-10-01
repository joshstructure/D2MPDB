from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch
from pier_cap.widgets import CapNotebook
from copy import deepcopy
from pier_cap.pile_review import import_pile_xml, section_from_xml
from lxml import etree as E
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
        self.panel.combo.value='2';self.panel.piles.value=('1',)
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
        self.panel.reference.value='24.5'
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
        self.panel.combo.value='2';self.panel.piles.value=('1','3')
        self.panel.trial_text.value=(FIXTURES/'pile_minimum_tip_reference.csv').read_text()
        self.panel.reference.value='24.5'
        state=self.panel.snapshot()
        self.panel.set_review(self.review)
        self.panel.restore(state)
        self.assertEqual(self.panel.combo.value,'2');self.assertEqual(self.panel.piles.value,('1','3'))
        with TemporaryDirectory() as folder:
            self.panel.save_bundle(folder)
            saved=json.loads((Path(folder)/'pile_review.json').read_text())
            self.assertEqual(saved['review']['sha256'],self.review['sha256'])
            self.panel.restore(saved)
            self.assertEqual(self.panel.piles.value,('1','3'))
            self.assertIn('uplift_kip',(Path(folder)/'pile_heads.csv').read_text(encoding='utf-8-sig'))
            self.assertIn('Geotechnical handoff',(Path(folder)/'pile_review.html').read_text(encoding='utf-8'))
            self.panel.reference.value='bad'
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

    def test_checkboxes_overlay_selected_piles_on_every_profile_and_keep_colors(self):
        self.panel.set_review(self.review)
        self.panel.no_piles.click()
        self.assertEqual(self.panel.piles.value, ())
        self.assertIn('Select one or more', self.panel.figures['profiles'].layout.annotations[-1].text)
        self.panel.piles.checks['1'].value = True
        self.panel.piles.checks['3'].value = True
        traces = self.panel.figures['profiles'].data
        self.assertEqual(len(traces), 16)
        for axis in ('x','x2','x3','x4','x5'):
            self.assertEqual({t.legendgroup for t in traces if t.xaxis == axis}, {'1','3'})
        before = {t.legendgroup:t.line.color for t in traces}
        self.panel.piles.checks['1'].value = False
        self.assertTrue(all(t.line.color == before['3'] for t in self.panel.figures['profiles'].data))
        self.panel.all_piles.click()
        self.assertEqual(self.panel.piles.value, tuple(self.review['piles']))
        self.panel.governing_pile.click()
        self.assertEqual(self.panel.piles.value, (self.panel.selected_pile(),))

    def test_concrete_grouped_strands_produce_visible_stress_curves(self):
        concrete = deepcopy(self.review)
        concrete['section'] = section_from_xml(E.parse(str(FIXTURES/'fbmp_end_bent_section.xml')).getroot())
        self.panel.set_review(concrete)
        stress = [t for t in self.panel.figures['profiles'].data if t.xaxis == 'x5']
        self.assertEqual(len(stress), 8)
        self.assertTrue(all(len(t.x) > 0 for t in stress))
        self.assertEqual(len(self.panel.figures['section'].data[0].x), 16)
        self.assertNotIn('Elastic stress profile unavailable', self.panel.reported.value)
        self.assertIn('Model tensile peak (ksi)', self.panel.reported.value)

    def test_trial_button_paste_headers_success_failure_and_stale_result(self):
        self.assertTrue(self.panel.run_trials.disabled)
        self.assertIn('Paste trial rows', self.panel.trial_status.value)
        self.panel.trial_text.value = 'Trial\tLoad Comb\tPile\tEmbedment (ft)\tDisplacement (in)\n1\t2\t4\t50\t1\n2\t2\t4\t40\t1.01'
        self.assertFalse(self.panel.run_trials.disabled)
        self.panel.run_trials.click()
        self.assertIn('TRIALS EVALUATED', self.panel.trial_status.value)
        self.assertEqual(self.panel.trial_result['proposed_embedment_ft'], 50)
        self.assertTrue(self.panel.trial_output.children)
        self.panel.trial_text.value = '1\t2\t4\tbad\t1'
        self.assertIsNone(self.panel.trial_result)
        self.assertFalse(self.panel.trial_output.children)
        self.panel.run_trials.click()
        self.assertIn('Row 1: embedment_ft', self.panel.trial_status.value)
        self.assertIn('TRIALS NEED REVIEW', self.panel.trial_status.value)

    def test_single_upload_populates_piles_even_before_cap_apply_and_preserves_review(self):
        # The two fixtures retain complementary blocks from the same XML run.
        root = E.parse(str(FIXTURES/'fbmp_610_piles.xml')).getroot()
        cap = E.parse(str(FIXTURES/'fbmp_610_cap.xml')).getroot()
        root.find('MODEL_INFO/SUBSTRUCTURE').append(deepcopy(cap.find('.//PIER_GEOMETRY')))
        for result in root.findall('.//LOAD_CASE_RESULTS/LOAD_CASE'):
            matching = cap.find('.//LOAD_CASE_RESULTS/LOAD_CASE[@combination="'+result.get('combination')+'"]')
            result.find('TIME_STEP').append(deepcopy(matching.find('TIME_STEP/STRUCTURE_INTERNAL_FORCES')))
        root.find('.//OUTPUT_SUMMARY').append(deepcopy(cap.find('.//OUTPUT_SUMMARY/STRUCTURE_PIER_CAP_MAX')))
        self.app.xml_import.stage(E.tostring(root), 'shared.xml')
        self.assertIsNotNone(self.panel.review)
        self.assertIsNotNone(self.app.xml_import.pending)
        self.panel.cutoff.value = '40'
        self.panel.piles.value = ('2','4')
        self.app.xml_import.apply_button.click()
        self.assertEqual(self.panel.cutoff.value, '40')
        self.assertEqual(self.panel.piles.value, ('2','4'))
        self.assertIn('share the same', self.panel.source_match.value)
        self.app.xml_import.refresh_button.click()
        self.assertEqual(self.panel.cutoff.value, '40')
        # An old saved interpretation of the same file must not keep suppressing
        # stress plots when that XML is uploaded again after an importer update.
        self.panel.review['section']['issues'] = ['Old unsupported group interpretation']
        self.app.xml_import.refresh_button.click()
        self.assertEqual(self.panel.review['section']['issues'], [])
        self.assertEqual(self.panel.piles.value, ('2','4'))
        self.assertEqual(self.panel.cutoff.value, '40')

    def test_previous_single_pile_save_still_loads(self):
        self.panel.set_review(self.review)
        state = self.panel.snapshot()
        state['schema_version'] = 1
        state['controls'].pop('piles')
        state['controls']['pile'] = '3'
        self.panel.restore(state)
        self.assertEqual(self.panel.piles.value, ('3',))


if __name__=='__main__':unittest.main()
