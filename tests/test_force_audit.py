from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from lxml import etree as E

from pier_cap.fbmp import import_fbmp_xml
from pier_cap.force_audit import strength_html, force_basis
from pier_cap.source_status import source_html
from pier_cap.io import export_blockpad, export_bundle
from pier_cap.model import default_case
from tests.test_blockpad_export import journal
from tests.test_fbmp import FIXTURE, changed


class ForceAuditTests(unittest.TestCase):
    def setUp(self):
        self.case = import_fbmp_xml(FIXTURE)

    def test_persistent_source_names_states_values_and_controllers(self):
        output = source_html(self.case)
        for text in ['Strength I','Strength III','182.10','183.15','287.44','34.16',
                     'Strength I · combo 1','Strength III · combo 2','independent maxima',
                     'not a simultaneous force vector']:
            self.assertIn(text,output)
        self.case['inputs']['Mu_B'] = 999
        self.assertIn('Edited input; imported 287.44',force_basis(self.case,'Mu_B'))
        self.assertIn('999.00',source_html(self.case))

    def test_legacy_missing_and_untrusted_audit_content(self):
        del self.case['analysis']['xml_audit']['strength_envelopes']
        self.assertIn('Reimport its XML',strength_html(self.case))
        self.assertIn('Strength I · combo 1',strength_html(self.case))
        self.assertIn('No XML limit-state breakdown',strength_html(default_case()))
        self.case['analysis']['xml_audit']['governing']['Mu_B']['combination'] = '<script>'
        self.assertNotIn('<script>',strength_html(self.case))
        self.assertIn('&lt;script&gt;',strength_html(self.case))

    def test_missing_strength_i_is_explicit_not_invented(self):
        def rename(root):
            root.find('MODEL_INFO/LOAD_COMBINATION[@number="1"]').set('limitstate','STRENGTH-V')
            root.find('.//LOAD_CASE_RESULTS/LOAD_CASE[@combination="1"]').set('limitstate','STRENGTH-V')
        case=import_fbmp_xml(changed(rename))
        self.assertIn('Strength I is NOT present',strength_html(case))
        self.assertIn('Strength V',strength_html(case))

    def test_blockpad_and_bundle_keep_state_breakdown_without_changing_equations(self):
        original = journal()
        before = deepcopy(self.case)
        with TemporaryDirectory() as folder:
            folder=Path(folder)
            target=export_blockpad(original,self.case,folder/'one.bpad')
            reexport=export_blockpad(target,self.case,folder/'two.bpad')
            tree=E.parse(str(reexport))
            for name in ['NotebookStrengthAudit','NotebookStrengthControllers','NotebookStrengthBasis']:
                self.assertEqual(len(tree.findall(f"report[@name='PierCapDesign']/*[@name='{name}']")),1)
            table=tree.find("report[@name='PierCapDesign']/table[@name='NotebookStrengthAudit']")
            text=' '.join(table.itertext())
            for value in ['Strength I','Strength III','182.10','183.15','4.75','34.16']:
                self.assertIn(value,text)
            definitions = {n.get('formula').split(' = ')[0]:n.get('formula') for n in tree.iter('dynexp')}
            original_defs = {n.get('formula').split(' = ')[0]:n.get('formula') for n in E.fromstring(original).iter('dynexp')}
            for key,value in original_defs.items():
                if key not in self.case['inputs'] and key not in ('Status_layout','Status_section'):
                    self.assertEqual(definitions[key],value)
            self.assertEqual(tree.find("report[@name='Other']").text,'Keep this report.')
            bundle=export_bundle(self.case,folder)
            self.assertIn('Strength I',(bundle/'strength_loads.csv').read_text(encoding='utf-8-sig'))
            self.assertIn('Strength III',(bundle/'strength_governing.csv').read_text(encoding='utf-8-sig'))
        self.assertEqual(self.case,before)


if __name__ == '__main__':
    unittest.main()
