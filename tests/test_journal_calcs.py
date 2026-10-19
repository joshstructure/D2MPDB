"""Native journal evidence, safe extraction, scoped input links and missing caches."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from design_atlas.journal_calcs import extract_calculations, literal
from design_atlas.build import build_data, ROOT, validate


class JournalCalculationTests(unittest.TestCase):
    def extract(self, xml):
        with patch('design_atlas.journal_calcs.ET.parse', return_value=ET.ElementTree(ET.fromstring(xml))):
            def proof(path, locator, value, note=''):
                return {'path': path, 'locator': locator, 'excerpt': value, 'note': note}
            modules, values, edges = extract_calculations(Path('.'), 'journal.bpad', proof, [])
        return modules, {v['id']: v for v in values}, edges

    def test_literals_are_read_but_arithmetic_is_not_evaluated(self):
        _, values, _ = self.extract('''<document><report name="Calc" title="Calculation">
          <dynexp formula="x = 39.12 kip*ft"/>
          <dynexp formula="y = 2*x"/>
          <dynexp formula="z = 2*x"><expresult> = 99 kip*ft</expresult></dynexp>
          <dynexp formula='flag = "PASS"'/>
        </report></document>''')
        self.assertEqual((values['journal.Calc.x']['value'], values['journal.Calc.x']['unit']), (39.12, 'kip*ft'))
        self.assertEqual(values['journal.Calc.y']['value'], 'Not evaluated')
        self.assertEqual(values['journal.Calc.z']['value'], 99)  # saved cache, not 78.24
        self.assertEqual(values['journal.Calc.y']['inputs'][0]['value_id'], 'journal.Calc.x')
        self.assertEqual(values['journal.Calc.flag']['value'], 'PASS')
        for formula in ['1+2', '1/3', 'Max(1,2)', '3 ft to in', 'NaN', '1e999']:
            self.assertIsNone(literal(formula))

    def test_scoped_direct_reference_keeps_each_modules_own_value(self):
        _, values, edges = self.extract('''<document>
          <report name="Basis" title="Basis"><dynexp formula="φ = 0.9"/><dynexp formula="h = 3 ft"/></report>
          <report name="Cap" title="Cap"><dynexp formula="h = Basis.h to in"><expresult> = 35 in</expresult></dynexp>
            <dynexp formula="area = Basis.h * h"/></report>
        </document>''')
        value = values['journal.Cap.h']
        self.assertEqual(value['value'], 35)
        self.assertEqual(value['origins']['JOURNAL-CALC-Cap']['kind'], 'received')
        self.assertEqual(value['inputs'][0]['value_id'], 'journal.Basis.h')
        self.assertEqual([s['value'] for s in value['steps']], [3, 35])
        self.assertEqual(value['node_ids'], ['JOURNAL-CALC-Cap', 'JOURNAL'])
        self.assertEqual(values['journal.Cap.area']['origins']['JOURNAL-CALC-Cap']['kind'], 'derived')
        self.assertIn(('JOURNAL-CALC-Basis', 'JOURNAL-CALC-Cap'), edges)
        self.assertEqual(values['journal.Basis.φ']['value'], 0.9)

    def test_duplicate_missing_and_archived_definitions_never_resolve(self):
        modules, values, _ = self.extract('''<document>
          <report name="Old" title="Archive - Old"><dynexp formula="x = 8"/></report>
          <report name="Basis"><dynexp formula="x = 1"/><dynexp formula="x = 2"/></report>
          <report name="Cap"><dynexp formula="a = Basis.x"/><dynexp formula="b = Old.x"/>
            <dynexp formula="c = Missing.x"/><dynexp formula='message = "Basis.x is text"'/></report>
        </document>''')
        self.assertNotIn('Old', [m['module'] for m in modules])
        self.assertIn('journal.Basis.x.definition1', values)
        self.assertIn('journal.Basis.x.definition2', values)
        for symbol in ['a', 'b', 'c']:
            value = values['journal.Cap.' + symbol]
            self.assertEqual(value['inputs'][0]['status'], 'unresolved')
            self.assertNotIn('value_id', value['inputs'][0])
            self.assertNotEqual(value['origins']['JOURNAL-CALC-Cap']['kind'], 'received')
        self.assertEqual(values['journal.Cap.message']['inputs'], [])

    def test_function_arguments_are_not_mistaken_for_module_inputs(self):
        _, values, _ = self.extract('''<document><report name="Basis">
          <dynexp formula="x = 4"/><dynexp formula="k = 2"/>
          <dynexp formula="f(x) = x*k"/>
        </report></document>''')
        value = values['journal.Basis.f']
        self.assertEqual(value['value'], 'Not evaluated')
        self.assertEqual([i['reference'] for i in value['inputs']], ['k'])

    def test_spreadsheet_addresses_count_blank_cells_and_preserve_ranges(self):
        _, values, _ = self.extract('''<document><spreadsheet name="Loads">
          <row><cell/><c><textvalue>Weight</textvalue></c><c><num>8 kip</num></c></row>
          <row><cell/><c formula="$C$1*2"><num>15 kip</num></c><c formula="Sum(A1:C1)"/></row>
        </spreadsheet></document>''')
        self.assertEqual(values['journal.Loads.C1']['value'], 8)
        self.assertEqual(values['journal.Loads.B2']['inputs'][0]['value_id'], 'journal.Loads.C1')
        self.assertEqual(values['journal.Loads.B2']['value'], 15)
        self.assertEqual(values['journal.Loads.C2']['inputs'][0]['reference'], 'A1:C1')
        self.assertEqual(values['journal.Loads.C2']['inputs'][0]['status'], 'unresolved')
        self.assertNotIn('journal.Loads.A1', values)


class CurrentJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build_data()
        cls.values = {v['id']: v for v in cls.data['values']}
        cls.xml = ET.parse(ROOT / 'journal/D2_I95_Project_Journal.bpad').getroot()

    def test_actual_cap_modules_have_parameters_and_native_links(self):
        nodes = {n['id']: n for n in self.data['nodes']}
        for name in ['CapDesignPier', 'CapDesignEndBentOne', 'CapDesignEndBentTwo']:
            self.assertGreater(nodes['JOURNAL-CALC-' + name]['value_count'], 100)
            width = self.values['journal.' + name + '.b']
            self.assertEqual(width['inputs'][0]['node'], 'JOURNAL-CALC-BridgeGeometry_2Beam')
            material = self.values['journal.' + name + '.fc']
            self.assertEqual(material['inputs'][0]['value_id'], 'journal.Materials.Substructure_fc')
            self.assertEqual(material['origins']['JOURNAL-CALC-' + name]['kind'], 'received')
        self.assertEqual(self.values['journal.CapDesignPier.Mu_N']['value'], 39.12)
        self.assertEqual(self.values['journal.CapDesignPier.Mu_N']['origins']['JOURNAL-CALC-CapDesignPier']['kind'], 'defined')
        self.assertNotIn('PIER-REPORT', self.values['journal.CapDesignPier.Mu_N']['node_ids'])

    def test_every_extracted_definition_has_a_unique_resolvable_exact_location(self):
        values = [v for v in self.data['values'] if v['id'].startswith('journal.') and 'primary_node' in v]
        locations = []
        for value in values:
            proof = value['steps'][-1]['evidence']
            location = proof['locator'].replace('/document/', './', 1)
            item = self.xml.find(location)
            self.assertIsNotNone(item, location)
            self.assertEqual(ET.tostring(item, encoding='unicode').strip(), proof['excerpt'])
            locations.append(location)
        self.assertEqual(len(locations), len(set(locations)))

    def test_graph_rejects_dangling_input_value(self):
        data = json.loads(json.dumps(self.data))
        value = next(v for v in data['values'] if v.get('inputs'))
        value['inputs'][0]['value_id'] = 'missing.value'
        with self.assertRaisesRegex(ValueError, 'formula input value'):
            validate(data)


if __name__ == '__main__':
    unittest.main()
