"""Case transfer, visible feedback, and preservation on rejected uploads."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pier_cap.io import load_case
from pier_cap.model import evaluate
from pier_cap.transverse import suggested_detail
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case, import_fbmp_xml
from tests.test_import_feedback import receive_upload


ROOT = Path(__file__).resolve().parent.parent


class CaseImportTests(unittest.TestCase):
    def setUp(self):
        self.app = CapNotebook(default_case())
        self.addCleanup(self.app.close)
        self.panel = self.app.case_import

    def test_loader_status_is_next_to_upload_and_full_case_refreshes(self):
        panel, app = self.panel, self.app
        self.assertIn(panel.ui, app.ui.children)
        self.assertIn(app.upload, panel.actions.children)
        self.assertIn(panel.status, panel.ui.children)
        self.assertIn('READY TO LOAD', panel.status.value)
        before_metrics, before_register = app.metrics.value, app.register.value
        case = import_fbmp_xml(ROOT/'tests/fixtures/fbmp_610_cap.xml')
        case['inputs'].update(Bar_N1=9, n_N1=6, MI_N=123, Ready_III=True, MIII_N=99)
        case['transverse_detail'] = suggested_detail(evaluate(case))
        receive_upload(app.upload, 'my <cap>.json', json.dumps(case).encode())
        self.assertEqual(app.case, case)
        self.assertEqual(app.current.case, case)
        for name, control in app.controls.items():
            self.assertEqual(control.value, case['inputs'][name], name)
        self.assertNotEqual(app.metrics.value, before_metrics)
        self.assertNotEqual(app.register.value, before_register)
        self.assertIn('6 × #9', app.cage.children[0].value)
        self.assertIsNone(app.pile_review.review)
        for text in ('LOADED SUCCESSFULLY', 'my &lt;cap&gt;.json', 'UTC', '183.15',
                     'Cap plots and checks recalculated', 'were not loaded from this file'):
            self.assertIn(text, panel.status.value)
        app.controls['Bar_N1'].value = 8
        self.assertIn('DIFFERS FROM LOADED JSON', panel.status.value)
        self.assertNotIn('LOADED SUCCESSFULLY', panel.status.value)
        # A second selection of exactly the same bytes must restore the file.
        receive_upload(app.upload, 'my <cap>.json', json.dumps(case).encode())
        self.assertEqual(app.case, case)
        self.assertIn('LOADED SUCCESSFULLY', panel.status.value)
        self.assertFalse(app.upload.value)

    def test_rejected_files_leave_case_and_results_unchanged(self):
        before = deepcopy(self.app.case)
        current, metrics = self.app.current, self.app.metrics.value
        wrong_units = deepcopy(before)
        wrong_units['units']['fc'] = 'psi'
        unsupported = deepcopy(before)
        unsupported['schema_version'] = 99
        cases = [
            ('broken.json', b'{broken', 'line 1, column 2'),
            ('array.json', b'[]', 'selected_case.json'),
            ('review.json', b'{"status":"PASS"}', 'not a saved cap case'),
            ('pile_review.json', b'{"review":{},"controls":{}}', 'Load pile review'),
            ('case.txt', json.dumps(before).encode(), '.json file'),
            ('units.json', json.dumps(wrong_units).encode(), 'units differ'),
            ('future.json', json.dumps(unsupported).encode(), 'schema_version'),
            ('binary.json', b'\xff', 'not UTF-8 JSON'),
        ]
        for filename, content, expected in cases:
            with self.subTest(filename=filename):
                receive_upload(self.app.upload, filename, content)
                self.assertIn('CASE IMPORT FAILED', self.panel.status.value)
                self.assertIn(expected, self.panel.status.value)
                self.assertIn('were not changed', self.panel.status.value)
                self.assertEqual(self.app.case, before)
                self.assertIs(self.app.current, current)
                self.assertEqual(self.app.metrics.value, metrics)
                self.assertFalse(self.app.upload.disabled)

    def test_render_failure_does_not_claim_success_or_unchanged_inputs(self):
        def interrupted(case, **kwargs):
            self.app.case = case
            raise RuntimeError('Display <disconnected>')
        with patch.object(self.app, 'load', side_effect=interrupted):
            self.panel.load(json.dumps(default_case()).encode(), 'case.json')
        self.assertIn('CASE APPLY DID NOT FINISH', self.panel.status.value)
        self.assertIn('Display &lt;disconnected&gt;', self.panel.status.value)
        self.assertIn('Inputs may have changed', self.panel.status.value)
        self.assertNotIn('LOADED SUCCESSFULLY', self.panel.status.value)
        self.assertNotIn('were not changed', self.panel.status.value)

    def test_transfer_error_is_visible_and_can_be_retried(self):
        self.app.upload.error = 'Connection interrupted'
        self.assertIn('File transfer failed: Connection interrupted', self.panel.status.value)
        receive_upload(self.app.upload, 'case.json', json.dumps(default_case()).encode())
        self.assertIn('LOADED SUCCESSFULLY', self.panel.status.value)

    def test_receipt_survives_workbench_cell_rerun(self):
        self.panel.load(json.dumps(default_case()).encode(), 'saved.json')
        old = self.app
        nb = json.loads((ROOT/'Cap_and_Pile_Design.ipynb').read_text(encoding='utf-8'))
        context = dict(app=old, case=default_case(), ROOT=ROOT)
        with patch.object(CapNotebook, 'display'):
            exec(''.join(next(c for c in nb['cells'] if c.get('id') == '7447e4cc')['source']), context)
        self.addCleanup(context['app'].close)
        self.assertEqual(context['app'].case_import.receipt, self.panel.receipt)
        self.assertIn('saved.json', context['app'].case_import.status.value)
        self.assertIn('LOADED SUCCESSFULLY', context['app'].case_import.status.value)


class ColabCaseImportTests(unittest.TestCase):
    def setUp(self):
        self.files = SimpleNamespace(upload=Mock())
        with patch.dict('sys.modules', {'google.colab': SimpleNamespace(files=self.files)}):
            self.app = CapNotebook(default_case())
        self.addCleanup(self.app.close)
        self.panel = self.app.case_import

    def test_native_upload_refreshes_and_reselects_same_file(self):
        case = default_case()
        case['inputs']['Mu_N'] = 321
        def transfer(target_dir):
            self.assertTrue(self.app.upload.disabled)
            self.assertIn('CHOOSE CASE JSON', self.panel.status.value)
            return {str(Path(target_dir)/'selected_case.json'): json.dumps(case).encode()}
        self.files.upload.side_effect = transfer
        for _ in range(2):
            self.app.upload.click()
            self.assertEqual(self.app.case, case)
            self.assertEqual(self.app.controls['Mu_N'].value, 321)
            self.assertIn('LOADED SUCCESSFULLY', self.panel.status.value)
            self.assertIn('321', self.panel.status.value)
            self.assertFalse(self.app.upload.disabled)
            self.assertEqual(self.panel.upload_output.layout.display, 'none')
        self.assertEqual(self.files.upload.call_count, 2)

    def test_cancel_multiple_files_and_transfer_failure_are_visible(self):
        before = deepcopy(self.app.case)
        for received, expected in [({}, 'UPLOAD CANCELLED'),
                ({'a.json': b'{}', 'b.json': b'{}'}, 'exactly one'),
                ({'broken.json': b'{}'}, 'not a saved cap case')]:
            with self.subTest(expected=expected):
                self.files.upload.return_value = received
                self.app.upload.click()
                self.assertIn(expected, self.panel.status.value)
                self.assertEqual(self.app.case, before)
                self.assertFalse(self.app.upload.disabled)
        self.files.upload.side_effect = RuntimeError('Transfer disconnected')
        self.app.upload.click()
        self.assertIn('Transfer disconnected', self.panel.status.value)
        self.assertEqual(self.app.case, before)
        self.assertFalse(self.app.upload.disabled)


class CaseFileFormatTests(unittest.TestCase):
    def test_non_case_json_has_actionable_errors(self):
        for data in (None, [], 10, {'schema_version': 3}, {'inputs': []}):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'selected_case.json'):
                load_case(json.dumps(data).encode())
