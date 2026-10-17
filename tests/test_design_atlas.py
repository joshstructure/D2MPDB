"""Bounded lineage checks: identity gaps, unit conversions, active runs, evidence."""
import copy
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from design_atlas.build import build_data, quantity, sheet_definition, validate, ROOT, CASE, SHEET, sha


class LiteralWorksheetTests(unittest.TestCase):
    def region(self, expression):
        return ET.fromstring('<region><define><id>x</id>'+expression+'</define></region>')

    def test_feet_to_inches(self):
        region=self.region('<apply><mult/><real>3</real><id>ft</id></apply>')
        self.assertEqual(sheet_definition(region,36,'in')['status'],'match')
        self.assertEqual(sheet_definition(region,35,'in')['status'],'mismatch')

    def test_pressure_conversion(self):
        region=self.region('<apply><mult/><real>5500</real><id>psi</id></apply>')
        self.assertEqual(sheet_definition(region,5.5,'ksi')['status'],'match')

    def test_rejects_wrong_dimensions(self):
        region=self.region('<apply><mult/><real>36</real><id>kip</id></apply>')
        self.assertEqual(sheet_definition(region,36,'in')['status'],'mismatch')

    def test_does_not_guess_symbol_or_evaluate_formula(self):
        for expression in ['<id>cached_depth</id>','<apply><plus/><real>1</real><real>2</real></apply>']:
            self.assertEqual(sheet_definition(self.region(expression),3,'in')['status'],'unsupported')

    def test_moment_units(self):
        region=self.region('<apply><mult/><apply><mult/><real>26.47</real><id>kip</id></apply><id>ft</id></apply>')
        self.assertEqual(sheet_definition(region,26.47,'kip*ft')['status'],'match')


class ProjectAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before={p:sha(ROOT/p) for p in [CASE,SHEET,'project_current/source_register.csv','project_current/coherence/Coherence_Tracker.xlsx']}
        cls.data=build_data()
        cls.values={v['id']:v for v in cls.data['values']}
        cls.case=json.loads((ROOT/CASE).read_text(encoding='utf-8'))

    def test_ingestion_preserves_native_files(self):
        self.assertEqual(self.before,{p:sha(ROOT/p) for p in self.before})

    def test_required_xml_is_not_replaced_by_filename_match(self):
        nodes={n['id']:n for n in self.data['nodes']}
        expected=self.case['analysis']['xml_audit']['sha256']
        actual=nodes['PIER-XML']['document']['sha256']
        self.assertEqual(self.data['checks']['required_xml_present'],actual==expected)
        if actual!=expected:
            self.assertEqual(nodes['REQUIRED-PIER-XML']['status'],'missing')
            self.assertTrue(any(e['source']=='PIER-XML' and e['target']=='PIER-CASE' and e['status']=='mismatch' for e in self.data['edges']))

    def test_governing_value_has_exact_retained_audit_location(self):
        v=self.values['inputs.Vu_G']
        self.assertEqual(v['value'],self.case['inputs']['Vu_G'])
        self.assertEqual(v['governing'],self.case['analysis']['xml_audit']['governing']['Vu_G'])
        self.assertEqual(v['steps'][0]['evidence']['locator'],'/analysis/xml_audit/governing/Vu_G')
        self.assertIn('Retained audit only',v['steps'][0]['note'])

    def test_enabled_runs_override_dormant_scalars(self):
        runs=self.case['transverse_detail']['runs']
        self.assertEqual(self.values['active_pitch']['value'],max(r['pitch_in'] for r in runs))
        self.assertEqual(self.values['active_bar']['value'],runs[0]['bar'])
        self.assertEqual(self.values['inputs.Bar_v']['source_status'],'dormant scalar')
        self.assertEqual(self.values['active_bar']['sheet_status'],'match')
        self.assertEqual(self.values['active_pitch']['sheet_status'],'match')

    def test_worksheet_receipt_and_literal_transfers(self):
        self.assertTrue(self.data['checks']['mathcad_receipt_matches'])
        self.assertTrue(self.data['checks']['report_case_equal'])
        for key in ['h','b','fc','Mu_N','Mu_B','Vu_G','Tu']:
            self.assertEqual(self.values['inputs.'+key]['sheet_status'],'match')
            self.assertIn('region-id=',self.values['inputs.'+key]['steps'][-1]['evidence']['locator'])

    def test_no_inferred_native_or_issue_approval(self):
        nodes={n['id']:n for n in self.data['nodes']}
        self.assertFalse(nodes['PIER-MATHCAD']['native_recalculation'])
        self.assertEqual(nodes['PIER-ISSUED-PDF']['status'],'missing')
        self.assertEqual(nodes['RFQ']['status'],'unmapped')

    def test_all_values_have_resolvable_fingerprinted_evidence(self):
        validate(self.data)
        for v in self.data['values']:
            for s in v['steps']:
                self.assertEqual(len(self.data['documents'][s['evidence']['path']]['sha256']),64)

    def test_schema_rejects_dangling_sources(self):
        data=copy.deepcopy(self.data);data['edges'][0]['source']='unknown'
        with self.assertRaises(ValueError):validate(data)


if __name__=='__main__':unittest.main()
