import json
from pathlib import Path
import tempfile
import unittest
from lxml import etree as E
from pier_cap.model import default_case,evaluate,DEFINITIONS,bar_positions
from pier_cap.io import load_case,write_case,export_bundle,export_blockpad

class IOTests(unittest.TestCase):
    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            case=default_case();p=write_case(case,Path(folder)/'case.json')
            self.assertEqual(load_case(p),case);self.assertEqual(load_case(p.read_bytes()),case)
            with self.assertRaises(FileExistsError):write_case(case,p)
            output=export_bundle(case,folder)
            self.assertEqual(load_case(output/'selected_case.json'),case)
            self.assertIn('PENDING',(output/'checks.csv').read_text(encoding='utf-8-sig'))
            self.assertTrue((output/'formula_trace.json').exists())

    def test_malformed_json_rejected(self):
        for mutate in (lambda c:c['inputs'].update({'foreign_formula':'execute()'}),lambda c:c['inputs'].pop('Mu_B'),lambda c:c.update({'schema_version':2}),lambda c:c['analysis'].pop('geometry'),lambda c:c['units'].update({'fc':'psi'})):
            case=default_case();mutate(case)
            with self.assertRaises(ValueError):load_case(json.dumps(case).encode())

    def test_blockpad_copy_preserves_other_sections(self):
        with tempfile.TemporaryDirectory() as folder:
            root=E.Element('blockpad');other=E.SubElement(root,'report',name='Other');other.text='Preserve this exact report.'
            report=E.SubElement(root,'report',name='PierCapDesign')
            for d in DEFINITIONS:
                node=E.SubElement(report,'dynexp',formula=d['formula']);E.SubElement(node,'expbody').text=d['formula']
            source=Path(folder)/'source.bpad';source.write_bytes(E.tostring(root));before=source.read_bytes()
            case=default_case();case['inputs']['n_N1']=6
            output=export_blockpad(source,case,Path(folder)/'review.bpad')
            self.assertEqual(before,source.read_bytes());tree=E.parse(str(output))
            self.assertEqual(E.tostring(other),E.tostring(tree.find("report[@name='Other']")))
            formulas=[n.get('formula') for n in tree.iter('dynexp')]
            self.assertIn('n_N1 = 6',formulas)
            self.assertTrue(any('E_detail' in f for f in formulas if f.startswith('Status_layout =')))
            with self.assertRaises(ValueError):export_blockpad(source,case,output)

class WidgetTests(unittest.TestCase):
    def test_controls_recalculate_and_invalid_values_clear_results(self):
        from pier_cap.widgets import CapNotebook
        app=CapNotebook()
        try:
            before=len(bar_positions(app.current));app.controls['n_N2'].value=4
            self.assertEqual(len(bar_positions(app.current)),before+4)
            self.assertAlmostEqual(app.current.value('As_N'),9.48)
            app.controls['N_pile'].value=5
            self.assertIn('REIMPORT',app.current.status);self.assertFalse(app.current.eligible)
            app.controls['s_G'].value=0
            self.assertIsNone(app.current);self.assertIn('INPUT ERROR',app.banner.value);self.assertEqual(len(app.cage.children),0)
            app.load(default_case());self.assertTrue(app.current.eligible)
        finally:
            for f in app.figures:f.close()
            app.ui.close()

    def test_search_apply_export_widget_workflow(self):
        from pier_cap.widgets import CapNotebook
        with tempfile.TemporaryDirectory() as folder:
            app=CapNotebook(export_root=folder)
            try:
                app.search_lists['main_bars'].value=(8,)
                app.search_lists['top_counts'].value=(8,)
                app.search_lists['bottom_counts'].value=(8,)
                app.search_lists['hoop_bars'].value=(5,)
                app.search_lists['hoop_spacings'].value=(8,)
                app.search_lists['skin_bars'].value=(5,)
                app.search_lists['skin_counts'].value=(6,)
                app._run_search(None)
                self.assertEqual(app.search_result.passed,1)
                self.assertFalse(app.apply_button.disabled)
                app._apply(None);self.assertTrue(app.current.eligible)
                app._export(None);self.assertEqual(load_case(app.last_export/'selected_case.json'),app.case)
                self.assertTrue((app.last_export/'alternatives.csv').exists())
                app.controls['Mu_B'].value=500
                self.assertIsNone(app.search_result);self.assertTrue(app.apply_button.disabled)
            finally:
                for f in app.figures:f.close()
                app.ui.close()

if __name__=='__main__':unittest.main()
