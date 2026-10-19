"""Distilled Blockpad export of the cap notebook's current case (pier_cap/bpad_distill.py, pier_cap/bpad_export.py)."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
import ipywidgets as W

from pier_cap.bpad_distill import cap_key, distill_cap, readiness
from pier_cap.bpad_export import DistilledBpadPanel, package_revision
from pier_cap.io import load_case
from pier_cap.model import default_case, evaluate
from scripts import build_cap_mathcad as bm

ROOT = Path(__file__).resolve().parent.parent
CASE_PATH = ROOT / 'project_current' / 'cap_design' / 'pier' / 'selected_case.json'


def ready_for(app):
    if app.dirty or app.calculating:
        return ('RECALC NEEDED', 'Click Recalc to update the cap checks before exporting.')
    reason = readiness(app.case)
    return ('CASE NOT READY', reason) if reason else None


class DistillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.case = load_case(CASE_PATH)
        cls.result = distill_cap(cls.case, cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def app(self, **kw):
        values = dict(case=self.case, export_root=Path(self.tmp.name), search_result=None, _search_filter=lambda: {},
                      dirty=False, calculating=False, message=W.HTML())
        values.update(kw)
        return SimpleNamespace(**values)

    def test_files_and_verification_entry(self):
        r, case = self.result, self.case
        bpad, folder = r['bpad'], r['folder']
        self.assertTrue(bpad.is_file())
        self.assertEqual(bpad.name, 'Pier Cap Design.bpad')
        self.assertEqual(bpad.parent, folder / 'blockpad')
        self.assertTrue((folder / 'selected_case.json').is_file())
        self.assertTrue((folder / 'calculation_report.html').is_file())
        verification = json.loads(r['verification'].read_text(encoding='utf-8'))
        self.assertEqual(verification, [r['entry']])
        entry = r['entry']
        self.assertEqual(entry['report_name'], 'CapDesignPier')
        self.assertGreaterEqual(entry['tool_comparisons'], 800)
        self.assertGreater(entry['coverage_comparisons'], 0)
        self.assertIsNone(entry['mathcad_values_compared'])
        self.assertIn(entry['status'], ('✓ All Checks Pass', '⊗ There are FAILURES'))
        self.assertTrue(entry['report_file'].endswith('calculation_report.html'))
        self.assertEqual(entry['case_sha256'], bm.case_sha256(evaluate(case)))
        self.assertEqual(entry['bpad_file'], 'blockpad/Pier Cap Design.bpad')
        self.assertIn(str(entry['tool_comparisons']), r['summary'])

    def test_document_xml_and_sidecars(self):
        bpad = self.result['bpad']
        root = ET.parse(bpad).getroot()
        self.assertEqual(root.tag, 'document')
        self.assertEqual(root.get('version'), '1.9')
        reports = root.findall('report')
        self.assertEqual([r.get('name') for r in reports], ['CapDesignPier'])
        text = ' '.join(''.join(p.itertext()) for p in reports[0].iter('paragraph'))
        self.assertIn('calculation_report.html', text)
        self.assertIn(self.result['entry']['case_sha256'][:12], text)
        self.assertIn('exported from the cap notebook', text)
        self.assertTrue((bpad.parent / 'fragments' / 'CapDesignPier.xml').is_file())
        self.assertTrue((bpad.parent / 'preview' / 'CapDesignPier.canvases.json').is_file())

    def test_cap_key(self):
        case = default_case()
        case['name'] = 'End Bent 1_Fixed — XML analysis'
        self.assertEqual(cap_key(case), 'end_bent_1')
        case = default_case()
        case['name'] = 'bland'
        case['analysis'].setdefault('xml_audit', {})['filename'] = 'End Bent 2_Fixed.XML'
        self.assertEqual(cap_key(case), 'end_bent_2')
        case = default_case()
        case['name'] = 'Pier_Fixed'
        self.assertEqual(cap_key(case), 'pier')
        self.assertEqual(cap_key(default_case()), 'notebook')

    def test_readiness(self):
        reason = readiness(default_case())
        self.assertIsInstance(reason, str)
        self.assertTrue(reason)
        self.assertIsNone(readiness(self.case))

    def test_colab_panel_export_and_download(self):
        files = SimpleNamespace(upload=Mock(), download=Mock())
        calls = []
        with patch.dict('sys.modules', {'google.colab': SimpleNamespace(files=files)}):
            panel = DistilledBpadPanel(self.app(), lambda a: calls.append(a) or self.result, hint='x', ready=ready_for)
        self.addCleanup(panel.ui.close)
        self.assertTrue(panel.download_button.disabled)
        panel.export_button.click()
        self.assertEqual(len(calls), 1)
        self.assertIn('DISTILLED BLOCKPAD READY', panel.status.value)
        self.assertIn('Pier Cap Design.bpad', panel.status.value)
        files.download.assert_called_once_with(str(self.result['bpad'].resolve()))
        self.assertFalse(panel.download_button.disabled)
        self.assertEqual(panel.last_result, self.result)
        panel.download_button.click()
        self.assertEqual(files.download.call_count, 2)

    def test_panel_waits_for_recalc(self):
        stub = Mock(return_value=self.result)
        panel = DistilledBpadPanel(self.app(dirty=True), stub, hint='x', ready=ready_for)
        self.addCleanup(panel.ui.close)
        panel.export_button.click()
        stub.assert_not_called()
        self.assertIn('RECALC NEEDED', panel.status.value)
        self.assertTrue(panel.download_button.disabled)

    def test_panel_reports_a_stopped_build(self):
        stub = Mock(side_effect=ValueError('boom'))
        panel = DistilledBpadPanel(self.app(), stub, hint='x', ready=ready_for)
        self.addCleanup(panel.ui.close)
        panel.export_button.click()
        self.assertIn('DISTILLED EXPORT STOPPED', panel.status.value)
        self.assertIn('boom', panel.status.value)
        self.assertTrue(panel.download_button.disabled)
        self.assertFalse(panel.export_button.disabled)

    def test_jupyter_panel_embeds_a_data_link(self):
        with patch.dict('sys.modules', {'google.colab': None}):
            panel = DistilledBpadPanel(self.app(), lambda a: self.result, hint='x', ready=ready_for)
        self.addCleanup(panel.ui.close)
        self.assertIsNone(panel.colab_files)
        # Outside a kernel the Output widget captures nothing, so intercept what the panel displays.
        with patch('IPython.display.display') as display:
            panel.export_button.click()
        self.assertIn('DISTILLED BLOCKPAD READY', panel.status.value)
        self.assertEqual(display.call_count, 1)
        link = display.call_args.args[0].data
        self.assertIn('href="data:application/octet-stream;base64,', link)
        self.assertIn('download="Pier Cap Design.bpad"', link)


class PackageRevisionTests(unittest.TestCase):
    def test_checkout_revision_is_twelve_hex_characters(self):
        revision = package_revision()
        self.assertRegex(revision, r'^[0-9a-f]{12}$')

    def test_extracted_folder_and_working_copy(self):
        with TemporaryDirectory() as tmp:
            extracted = Path(tmp) / 'cap-pile-tool-abcdef012345'
            (extracted / 'pier_cap').mkdir(parents=True)
            self.assertEqual(package_revision(extracted / 'pier_cap'), 'abcdef012345')
            bare = Path(tmp) / 'bare'
            (bare / 'pier_cap').mkdir(parents=True)
            self.assertEqual(package_revision(bare / 'pier_cap'), 'working copy')


if __name__ == '__main__':
    unittest.main()
