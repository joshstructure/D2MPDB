"""The backwall notebook's distilled Blockpad export: in-memory build, verification record, bundle and the widget button."""
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from end_bent_walls import exports
from end_bent_walls.model import default_case, evaluate

ALL_PASS, FAILURES = '✓ All Checks Pass', '⊗ There are FAILURES'
BUTTON = 'Export distilled Blockpad (.bpad)'


class DistilledBlockpadExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = evaluate()
        cls.bpad, cls.verification = exports.distilled_bpad(cls.e)

    def test_bytes_are_a_verified_native_document(self):
        root = ET.fromstring(self.bpad)
        self.assertEqual((root.tag, root.get('version')), ('document', '1.9'))
        self.assertEqual([r.get('name') for r in root.findall('report')], ['EndBentBackwallDesign'])
        entry = json.loads(self.verification.decode('utf-8'))[0]
        self.assertGreaterEqual(entry['tool_comparisons'], 240)
        self.assertIn(entry['status'], (ALL_PASS, FAILURES))
        self.assertEqual(entry['status'] == ALL_PASS, not any('FAIL' in c.status for c in self.e.checks))
        self.assertIn('values match the notebook', exports.bpad_summary(self.verification))
        self.assertIn(f'package {entry["package_revision"]}', exports.bpad_summary(self.verification))
        first = exports.distilled_bpad(self.e)
        self.assertIs(exports.distilled_bpad(self.e)[0], first[0], 'the distillation of one evaluation is reused')

    def test_export_file_writes_the_sheet_with_its_record_and_the_bundle_holds_both(self):
        with tempfile.TemporaryDirectory() as folder:
            path = exports.export_file(self.e, folder, exports.DISTILLED_BPAD)
            self.assertEqual(path.name, exports.DISTILLED_BPAD)
            self.assertEqual(path.read_bytes(), self.bpad)
            self.assertEqual((path.parent / exports.BPAD_VERIFICATION).read_bytes(), self.verification)
            files = exports.export_bundle(self.e, folder)
            names = zipfile.ZipFile(files['backwall_bundle.zip']).namelist()
            self.assertIn(exports.DISTILLED_BPAD, names)
            self.assertIn(exports.BPAD_VERIFICATION, names)

    def test_a_changed_case_is_distilled_from_its_own_values(self):
        case = default_case()
        case['inputs']['s_FF'] = 6.0
        e = evaluate(case)
        bpad, verification = exports.distilled_bpad(e)
        formulas = [d.get('formula') for d in ET.fromstring(bpad).iter('dynexp')]
        self.assertIn('s_FF = 6 in', formulas)
        self.assertNotEqual(json.loads(verification)[0]['case_sha256'], json.loads(self.verification)[0]['case_sha256'])
        self.assertEqual(exports.distilled_bpad(self.e)[0], self.bpad)   # the registered case distils the same again

    def test_notebook_button_exports_and_reports_the_verification(self):
        from end_bent_walls.widgets import BackwallNotebook
        with tempfile.TemporaryDirectory() as folder:
            app = BackwallNotebook(export_root=folder)
            try:
                button = next(b for b in app.export_buttons if b.description == BUTTON)
                self.assertFalse(button.disabled)
                button.click()
                path = app.last_files[exports.DISTILLED_BPAD]
                self.assertTrue(path.is_file())
                self.assertTrue((path.parent / exports.BPAD_VERIFICATION).is_file())
                self.assertIn('DISTILLED BLOCKPAD READY', app.export_status.value)
                self.assertIn('values match the notebook', app.export_status.value)
                app.controls['s_FF'].value = 30.0
                self.assertTrue(button.disabled, 'an edited case must be recalculated before it is exported')
            finally:
                app.close()


if __name__ == '__main__':
    unittest.main()
