"""Portable journal transfer and C005-only review-copy exports."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import ipywidgets as W
from lxml import etree as E

from pier_cap.blockpad_widgets import BlockpadExportPanel
from pier_cap.io import export_blockpad, validate_blockpad_source, load_case
from pier_cap.model import default_case, DEFINITIONS


def journal():
    root = E.Element('blockpad')
    E.SubElement(root, 'report', name='Other').text = 'Keep this report.'
    report = E.SubElement(root, 'report', name='PierCapDesign')
    for definition in DEFINITIONS:
        node = E.SubElement(report, 'dynexp', formula=definition['formula'])
        E.SubElement(node, 'expbody').text = definition['formula']
    return E.tostring(root)


class BlockpadExportTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.case = default_case()
        self.case['inputs']['n_N1'] = 9
        self.app = SimpleNamespace(case=self.case, export_root=Path(self.folder.name),
            search_result=None, last_export=None, message=W.HTML(), _search_filter=lambda: {})
        self.files = SimpleNamespace(upload=Mock(), download=Mock())
        with patch.dict('sys.modules', {'google.colab': SimpleNamespace(files=self.files)}):
            self.panel = BlockpadExportPanel(self.app)
        self.addCleanup(self.panel.ui.close)

    def test_native_upload_export_and_download_current_case(self):
        original = journal()
        self.files.upload.side_effect = lambda target_dir: {str(Path(target_dir) / 'Journal.bpad'): original}
        self.panel.upload.click()
        self.assertIn('JOURNAL READY', self.panel.status.value)
        self.assertEqual(self.panel.source, original)
        self.panel.export_button.click()
        output = self.panel.last_file
        self.assertTrue(output.is_file())
        self.assertIn('BLOCKPAD REVIEW COPY READY', self.panel.status.value)
        self.files.download.assert_called_once_with(str(output.resolve()))
        tree = E.parse(str(output))
        self.assertEqual(tree.find("report[@name='Other']").text, 'Keep this report.')
        self.assertIn('n_N1 = 9', [n.get('formula') for n in tree.iter('dynexp')])
        self.assertEqual(load_case(output.parent / 'selected_case.json'), self.case)
        self.assertEqual(self.panel.source, original)
        self.panel.download_button.click()
        self.assertEqual(self.files.download.call_count, 2)

    def test_missing_windows_path_explains_upload_before_creating_bundle(self):
        self.panel.path.value = r'Z:\unavailable\project.bpad'
        self.panel.export_button.click()
        self.assertIn('Upload Blockpad journal', self.panel.status.value)
        self.assertFalse(list(Path(self.folder.name).iterdir()))
        self.assertIsNone(self.panel.last_file)
        self.files.download.assert_not_called()

    def test_invalid_or_cancelled_upload_does_not_reuse_old_journal(self):
        for received in ({}, {'a.txt': journal()}, {'a.bpad': b'<wrong/>'},
                         {'a.bpad': journal(), 'b.bpad': journal()}):
            with self.subTest(files=list(received)):
                self.panel.stage('old.bpad', journal())
                self.files.upload.return_value = received
                self.panel.upload.click()
                self.assertIsNone(self.panel.source)
                self.assertFalse(self.panel.path.value)
                self.panel.export_button.click()
                self.assertIsNone(self.panel.last_file)
                self.assertFalse(list(Path(self.folder.name).iterdir()))
                self.assertFalse(self.panel.upload.disabled)

    def test_download_failure_keeps_completed_file_and_supports_retry(self):
        self.panel.stage('Journal.bpad', journal())
        self.files.download.side_effect = RuntimeError('Download disconnected')
        self.panel.export_button.click()
        self.assertTrue(self.panel.last_file.exists())
        self.assertIn('DOWNLOAD NEEDS RETRY', self.panel.status.value)
        self.assertFalse(self.panel.download_button.disabled)
        self.files.download.side_effect = None
        self.panel.download_button.click()
        self.assertEqual(self.files.download.call_count, 2)

    def test_upload_bytes_and_path_export_match_and_preserve_original(self):
        source = Path(self.folder.name) / 'journal.bpad'
        original = journal()
        source.write_bytes(original)
        a = export_blockpad(source, self.case, Path(self.folder.name) / 'a.bpad')
        b = export_blockpad(memoryview(original), self.case, Path(self.folder.name) / 'b.bpad')
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(source.read_bytes(), original)
        with self.assertRaises(ValueError):
            export_blockpad(original, self.case, b)
        malformed = E.fromstring(original)
        for node in list(malformed.find("report[@name='PierCapDesign']")):
            if node.get('formula', '').startswith('Status_layout ='):
                node.getparent().remove(node)
        with self.assertRaisesRegex(ValueError, 'Status_layout'):
            validate_blockpad_source(E.tostring(malformed))

    def test_local_path_and_both_widget_upload_protocols(self):
        with patch.dict('sys.modules', {'google.colab': None}):
            panel = BlockpadExportPanel(self.app)
        self.addCleanup(panel.ui.close)
        from tests.test_import_feedback import receive_upload
        receive_upload(panel.upload, 'Journal.bpad', journal())
        self.assertIn('JOURNAL READY', panel.status.value)
        panel.export_button.click()
        first = panel.last_file
        self.assertTrue(first.exists())
        source = Path(self.folder.name) / 'local.bpad'
        source.write_bytes(journal())
        panel.path.value = str(source)
        self.assertIsNone(panel.source)
        panel.export_button.click()
        self.assertNotEqual(first, panel.last_file)
        self.assertTrue(panel.last_file.exists())


if __name__ == '__main__':
    unittest.main()
