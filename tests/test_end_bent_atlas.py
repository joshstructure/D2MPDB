"""End-bent pane regression: real source values, scoped IDs and honest handoffs."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from design_atlas.build import LABELS, ROOT, category, validate
from design_atlas.end_bent import extend_end_bent
from tools.project_coherence import report_case


class EndBentAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a minimal registry snapshot of the actual selected files; no native edits or solver.
        import csv
        import hashlib
        with (ROOT / 'project_current/source_register.csv').open(encoding='utf-8-sig') as register:
            rows = {r['source_id']: r for r in csv.DictReader(register)}
        cls.base = {'schema_version': 1, 'nodes': [], 'edges': [], 'values': [], 'documents': {}, 'checks': {}, 'coverage': {'values': '', 'limits': []}}
        for key in ('EB-CASE', 'EB-REPORT', 'EB-XML'):
            path = rows[key]['path']
            source = ROOT / path
            doc = {'path': path, 'exists': source.is_file(), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None}
            cls.base['documents'][path] = doc
            cls.base['nodes'].append({'id': key, 'path': path, 'document': doc})
        for i, (a, b) in enumerate([('EB-CASE', 'EB-REPORT'), ('EB-XML', 'EB-CASE'), ('EB-XML', 'EB-REPORT')]):
            cls.base['edges'].append({'id': str(i), 'source': a, 'target': b, 'kind': 'dependency'})
        cls.case_path = rows['EB-CASE']['path']
        cls.report_path = rows['EB-REPORT']['path']
        cls.case = json.loads((ROOT / cls.case_path).read_text(encoding='utf-8-sig'))

    def build(self, data=None):
        data = copy.deepcopy(self.base if data is None else data)
        extend_end_bent(data, ROOT, LABELS, category)
        validate(data)
        return data

    def test_actual_end_bent_input_and_report_handoff(self):
        data = self.build()
        values = {v['id']: v for v in data['values']}
        value = values['EB.inputs.Vu_G']
        self.assertEqual(value['value'], self.case['inputs']['Vu_G'])
        self.assertNotEqual(value['value'], 218.96)  # Pier shear must never leak into EB1.
        self.assertEqual(value['origins']['EB-REPORT']['from_node'], 'EB-CASE')
        self.assertEqual(value['origins']['EB-CASE']['from_node'], 'EB-AUDIT')
        self.assertEqual(value['steps'][0]['evidence']['path'], self.case_path)
        self.assertEqual(value['steps'][0]['evidence']['locator'], '/analysis/xml_audit/governing/Vu_G')
        report_values = [v for v in values.values() if 'EB-REPORT' in v['node_ids']]
        self.assertEqual(len(report_values), len(self.case['inputs']) + 5 * len(self.case['transverse_detail']['runs']))
        self.assertTrue(any(e['source'] == 'EB-CASE' and e['target'] == 'EB-REPORT' and e['kind'] == 'flow' for e in data['edges']))

    def test_missing_matching_xml_stays_a_gap(self):
        data = self.build()
        registered_hash = self.base['documents'][next(n['path'] for n in self.base['nodes'] if n['id'] == 'EB-XML')]['sha256']
        matches = registered_hash == self.case['analysis']['xml_audit']['sha256']
        required = next(n for n in data['nodes'] if n['id'] == 'REQUIRED-EB-XML')
        self.assertEqual(required['status'], 'match' if matches else 'missing')
        self.assertEqual(data['checks']['end_bent_required_xml_present'], matches)
        if not matches:
            self.assertEqual(required['path'], '')
            self.assertTrue(any(e['source'] == 'EB-XML' and e['status'] == 'mismatch' for e in data['edges']))

    def test_no_cross_component_origin_paths_or_ids(self):
        data = self.build()
        for value in data['values']:
            self.assertTrue(value['id'].startswith('EB.'))
            self.assertNotIn('PIER', json.dumps(value['origins']))
            self.assertNotIn('/pier/', json.dumps(value['origins']))

    def test_report_disagreement_keeps_actual_report_values(self):
        report = report_case(ROOT / self.report_path)
        report['inputs']['Vu_G'] += 10
        with patch('design_atlas.end_bent.report_case', return_value=report):
            data = self.build()
        values = {v['id']: v for v in data['values']}
        self.assertNotIn('EB-REPORT', values['EB.inputs.Vu_G']['node_ids'])
        value = values['EB.report.inputs.Vu_G']
        self.assertEqual(value['value'], report['inputs']['Vu_G'])
        self.assertEqual(value['origins']['EB-REPORT']['kind'], 'unknown')

    def test_repeat_extension_is_idempotent(self):
        first = self.build()
        self.assertEqual(first, self.build(first))

    def test_changed_source_fails_before_combining_snapshots(self):
        data = copy.deepcopy(self.base)
        data['documents'][self.case_path]['sha256'] = 'different-revision'
        with self.assertRaisesRegex(RuntimeError, 'changed since this snapshot'):
            self.build(data)


if __name__ == '__main__':
    unittest.main()
