"""Bounded lineage checks: identity gaps, unit conversions, active runs, evidence."""
import copy
import csv
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from design_atlas.build import build_data, quantity, sheet_definition, validate, ROOT, CASE, SHEET, RECEIPT, sha
from design_atlas.origins import classify
from design_atlas.journal import cell_text, stored_value


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
        cls.before={p:sha(ROOT/p) for p in [CASE,SHEET,'journal/D2_I95_Project_Journal.bpad','project_current/source_register.csv','project_current/coherence/Coherence_Tracker.xlsx'] if (ROOT/p).is_file()}
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
        if (ROOT/SHEET).is_file():
            self.assertEqual(self.values['active_bar']['sheet_status'],'match')
            self.assertEqual(self.values['active_pitch']['sheet_status'],'match')
        else:
            self.assertEqual(self.values['active_bar']['sheet_status'],'not mapped')

    def test_worksheet_receipt_and_literal_transfers(self):
        if not (ROOT/SHEET).is_file():
            self.assertFalse(self.data['checks']['mathcad_receipt_matches'])
            self.assertEqual(next(n for n in self.data['nodes'] if n['id']=='PIER-MATHCAD')['status'],'missing')
            return
        receipt=next(r for r in json.loads((ROOT/RECEIPT).read_text(encoding='utf-8-sig')) if r['label']=='Pier Cap')
        receipt_matches=receipt['case_sha256']==sha(ROOT/CASE) and receipt['output_sha256']==sha(ROOT/SHEET)
        self.assertEqual(self.data['checks']['mathcad_receipt_matches'],receipt_matches)
        for key in ['h','b','fc','Mu_N','Mu_B','Vu_G','Tu']:
            value=self.values['inputs.'+key]
            proof=value['steps'][-1]['evidence']
            literal=sheet_definition(ET.fromstring(proof['excerpt']),self.case['inputs'][key],value['unit'])
            self.assertEqual(value['sheet_status'],literal['status'])
            self.assertEqual(value['sheet_receipt_status'],'match' if receipt_matches else 'mismatch')
            self.assertIn('region-id=',proof['locator'])

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

    def test_origins_are_relative_to_selected_node(self):
        v=self.values['inputs.Vu_G']
        self.assertEqual(v['origins']['PIER-CASE']['kind'],'received')
        self.assertEqual(v['origins']['PIER-CASE']['from_node'],'PIER-AUDIT')
        self.assertEqual(v['origins']['PIER-AUDIT']['kind'],'derived')
        self.assertEqual(v['origins']['REQUIRED-PIER-XML']['kind'],'unknown')
        if (ROOT/SHEET).is_file():
            if self.data['checks']['mathcad_receipt_matches'] and v['sheet_status']=='match':
                self.assertEqual(v['origins']['PIER-MATHCAD']['from_node'],'PIER-CASE')
                self.assertEqual(v['origins']['PIER-MATHCAD']['kind'],'received')
            else:
                self.assertNotIn('from_node',v['origins']['PIER-MATHCAD'])
                self.assertEqual(v['origins']['PIER-MATHCAD']['kind'],'unknown')

    def test_retained_clearance_is_not_mislabeled_as_received_geometry(self):
        self.assertEqual(self.values['inputs.h']['origins']['PIER-CASE']['kind'],'received')
        for key in ['E_clear','E_detail','C_t','phi_f','Bar_v']:
            origin=self.values['inputs.'+key]['origins']['PIER-CASE']
            self.assertEqual(origin['kind'],'defined')
            self.assertNotIn('from_node',origin)
        self.assertEqual(self.values['inputs.Vu_L']['origins']['PIER-CASE']['kind'],'derived')

    def test_unlinked_value_does_not_imply_local_origin(self):
        self.assertEqual(self.values['inputs.fc']['origins']['PIER-CASE']['kind'],'unknown')
        if (ROOT/SHEET).is_file():
            value=self.values['inputs.fc']
            expected='received' if self.data['checks']['mathcad_receipt_matches'] and value['sheet_status']=='match' else 'unknown'
            self.assertEqual(value['origins']['PIER-MATHCAD']['kind'],expected)

    def test_selected_xml_label_follows_actual_identity(self):
        value=self.values['prior.pile_head_z']
        matches=self.data['checks']['required_xml_present']
        self.assertEqual(value['label'],('Selected' if matches else 'Prior')+' XML pile-head Z')
        if matches:
            self.assertNotIn('does not match',value['steps'][0]['note'])

    def test_broken_handoff_is_not_classified_as_received(self):
        v=copy.deepcopy(self.values['inputs.Vu_G'])
        v['audit_agrees']=False
        roles=classify(v,self.case,False,False)
        self.assertEqual(roles['PIER-CASE']['kind'],'unknown')
        self.assertEqual(roles['PIER-REPORT']['kind'],'unknown')
        if 'PIER-MATHCAD' in roles:
            self.assertEqual(roles['PIER-MATHCAD']['kind'],'unknown')

    def test_worksheet_formulas_are_never_presented_as_evaluated_results(self):
        formulas=[v for v in self.data['values'] if v.get('value_kind')=='expression' and 'PIER-MATHCAD' in v['node_ids']]
        self.assertEqual(len(formulas),4 if (ROOT/SHEET).is_file() else 0)
        for v in formulas:
            self.assertEqual(v['value'],'Not evaluated')
            self.assertEqual(v['origins']['PIER-MATHCAD']['kind'],'derived')
            self.assertIn(':=',v['expression'])
            self.assertIn('region-id=',v['steps'][0]['evidence']['locator'])

    def test_journal_feeds_both_fbmp_entry_modules_and_runs(self):
        nodes={n['id']:n for n in self.data['nodes']}
        edges={(e['source'],e['target']):e for e in self.data['edges']}
        for module,target in [('JOURNAL-PIER-ENTRY','REQUIRED-PIER-XML'),('JOURNAL-EB-ENTRY','EB-XML'),('JOURNAL-EB-ENTRY','EB2-XML')]:
            self.assertIn(('JOURNAL',module),edges)
            self.assertEqual(nodes[module]['path'],nodes['JOURNAL']['path'])
            self.assertEqual(edges[module,target]['status'],'recorded')
            self.assertIn('not verified',edges[module,target]['basis'])

    def test_journal_context_is_not_presented_as_the_same_analysis_result(self):
        value=self.values['inputs.Mu_N']
        self.assertIn('JOURNAL',value['upstream_context']['node_ids'])
        self.assertNotIn('JOURNAL',value['node_ids'])
        self.assertNotIn('JOURNAL',value['origins'])
        self.assertIn('not the same quantity',value['upstream_context']['detail'])

    def test_journal_node_load_uses_saved_cache_and_exact_cell_evidence(self):
        value=self.values['journal.FBMPPier.FE_NodeEntry_DC_PL_W1_W3.r2.c6']
        journal=ET.parse(ROOT/'journal/D2_I95_Project_Journal.bpad').getroot()
        cell=journal.find("./report[@name='FBMPPier']/.//table[@name='FE_NodeEntry_DC_PL_W1_W3']/row[2]/c[6]")
        self.assertEqual(value['value'],float(cell.findtext('num')))
        self.assertEqual(value['expression'],cell.get('formula'))
        self.assertEqual(value['unit'],'kip')
        self.assertIn('/row[2]/c[6]',value['steps'][0]['evidence']['locator'])
        self.assertIn('without native recalculation',value['note'])
        self.assertNotIn('PIER-XML',value['node_ids'])
        self.assertEqual(self.values['journal.FBMPEndBent.EBNodeMap.r2.c2']['value'],15)
        self.assertEqual(self.values['journal.FBMPEndBent.EBNodeMap.r3.c2']['value'],34)

    def test_historical_mapping_is_not_substituted_for_live_entry_coordinates(self):
        entry=self.values['journal.FBMPPier.FEPositionMap.r4.c4']
        mapping=self.values['journal.FBMPPier.PierSourceBearingMap.r4.c5']
        self.assertEqual(entry['value'],'0 ft 10.5 in')
        self.assertEqual(mapping['value'],10.14)
        self.assertIn('historical',mapping['note'])

    def test_selected_report_evidence_follows_current_register(self):
        with (ROOT/'project_current/source_register.csv').open(encoding='utf-8-sig') as handle:
            selected=next(r for r in csv.DictReader(handle) if r['source_id']=='PIER-REPORT')['path']
        report_steps=[s for v in self.data['values'] for s in v['steps'] if s['node']=='PIER-REPORT']
        self.assertTrue(report_steps)
        self.assertTrue(all(s['evidence']['path']==selected for s in report_steps))

    def test_missing_journal_cache_is_not_evaluated(self):
        self.assertIsNone(cell_text(ET.fromstring('<c formula="1+2"/>')))
        self.assertEqual(stored_value(None),(None,''))
        self.assertEqual(stored_value('-0 ft 10.5 in'),('-0 ft 10.5 in',''))

    def test_schema_rejects_dangling_sources(self):
        data=copy.deepcopy(self.data);data['edges'][0]['source']='unknown'
        with self.assertRaises(ValueError):validate(data)


if __name__=='__main__':unittest.main()
