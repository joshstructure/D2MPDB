"""A saved runtime file is distinct from a browser download."""
import base64
import re
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import zipfile

from pier_cap.io import load_case
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


class CaseDownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.app=CapNotebook(default_case(),export_root=self.directory.name)

    def tearDown(self):
        self.app.close()
        self.directory.cleanup()

    def test_colab_export_downloads_json_and_retry_keeps_exported_snapshot(self):
        app=self.app;download=Mock();app.case_download_files=SimpleNamespace(download=download)
        self.assertIn(app.case_download_output,app.export_panel.children)
        self.assertTrue(app.case_json_button.disabled)
        app.case_export_button.click()
        folder=app.case_export_folder
        download.assert_called_once_with(str(folder/'selected_case.json'))
        saved=load_case(folder/'selected_case.json')
        self.assertEqual(saved,app.case)
        self.assertFalse(app.case_json_button.disabled)
        self.assertIn('Browser download requested',app.case_export_status.value)
        self.assertIn('completion is not confirmed',app.case_export_status.value)
        app.controls['Mu_B'].value+=1
        # Other exports may change last_export; retry must retain this JSON.
        app.last_export=Path(self.directory.name)/'another-export'
        app.case_json_button.click()
        self.assertEqual(download.call_args.args,(str(folder/'selected_case.json'),))
        self.assertEqual(load_case(folder/'selected_case.json'),saved)
        self.assertNotEqual(saved,app.case)
        app.case_export_button.click()
        self.assertNotEqual(app.case_export_folder,folder)
        self.assertEqual(load_case(app.case_export_folder/'selected_case.json'),app.case)

    def test_download_failure_keeps_file_and_retry_without_reexport(self):
        app=self.app;download=Mock(side_effect=RuntimeError('Browser unavailable'))
        app.case_download_files=SimpleNamespace(download=download)
        app._export(None)
        folder=app.case_export_folder
        self.assertTrue((folder/'selected_case.json').exists())
        self.assertIn('CASE SAVED',app.case_export_status.value)
        self.assertIn('DOWNLOAD NEEDS RETRY',app.case_export_status.value)
        self.assertFalse(app.case_json_button.disabled)
        download.side_effect=None
        app.case_json_button.click()
        self.assertEqual(app.case_export_folder,folder)
        self.assertIn('Browser download requested',app.case_export_status.value)
        with patch('pier_cap.widgets.export_bundle',side_effect=ValueError('Invalid new case')):
            app._export(None)
        self.assertIn('previous successful export',app.case_export_status.value)
        self.assertEqual(app.case_export_folder,folder)
        self.assertFalse(app.case_export_button.disabled)

    def test_zip_download_includes_nested_review_and_loadable_case(self):
        app=self.app;download=Mock();app.case_download_files=SimpleNamespace(download=download)
        app._export(None);folder=app.case_export_folder
        nested=folder/'pile_review';nested.mkdir();(nested/'review.json').write_text('{"pile":1}',encoding='utf-8')
        app.case_zip_button.click()
        zipped=folder.with_suffix('.zip')
        self.assertEqual(download.call_args.args,(str(zipped),))
        with zipfile.ZipFile(zipped) as archive:
            self.assertEqual(load_case(archive.read(folder.name+'/selected_case.json')),app.case)
            self.assertIn(folder.name+'/checks.csv',archive.namelist())
            self.assertIn(folder.name+'/pile_review/review.json',archive.namelist())

    def test_jupyter_link_contains_exported_bytes_even_outside_server_root(self):
        app=self.app;app.case_download_files=None
        with patch('IPython.display.display') as display:
            app._export(None)
        markup=display.call_args.args[0].data
        self.assertIn('download="selected_case.json"',markup)
        payload=re.search('base64,([^\"]+)',markup)[1]
        self.assertEqual(base64.b64decode(payload),(app.case_export_folder/'selected_case.json').read_bytes())
        self.assertIn('Click the download link',app.case_export_status.value)

    def test_report_button_generates_current_snapshot_and_saved_download_retries(self):
        app=self.app;download=Mock();app.case_download_files=SimpleNamespace(download=download)
        self.assertTrue(app.case_html_button.disabled)
        app.case_report_button.click()
        folder=app.case_export_folder
        report=folder/'calculation_report.html'
        self.assertTrue(report.is_file())
        download.assert_called_once_with(str(report))
        snapshot=report.read_bytes()
        app.controls['Mu_B'].value+=1
        app.case_html_button.click()
        self.assertEqual(download.call_args.args,(str(report),))
        self.assertEqual(report.read_bytes(),snapshot)
        app.case_report_button.click()
        self.assertNotEqual(app.case_export_folder,folder)
        self.assertEqual(load_case(app.case_export_folder/'selected_case.json'),app.case)
        self.assertNotEqual((app.case_export_folder/'calculation_report.html').read_bytes(),snapshot)
        self.assertFalse(app.case_report_button.disabled)


if __name__=='__main__':unittest.main()
