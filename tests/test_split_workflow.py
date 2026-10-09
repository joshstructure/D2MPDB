"""Independent analysis sources and a once-only internal geotech margin."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from pier_cap.widgets import CapNotebook
from pier_cap.pile_review import import_pile_xml
from pier_cap.pile_reporting import geotech_section_and_loads

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT/'tests/fixtures'


class ReactionMarginTests(unittest.TestCase):
    def setUp(self):
        self.review = import_pile_xml(FIXTURES/'fbmp_610_piles.xml')
        for row in self.review['forces']:
            row['axial_tension_kip'] = -100
        # Distinct head compression and uplift, with much larger non-head/service forces.
        for row in self.review['forces']:
            if row['state'] == 'SERVICE-I':
                row['axial_tension_kip'] = -10000
            elif row['local_element'] == 1 and row['side'] == 'I' and row['pile'] == '1':
                row['axial_tension_kip'] = 20
            elif row['local_element'] > 1:
                row['axial_tension_kip'] = -99999

    def test_default_custom_zero_margin_and_no_mutation(self):
        original = deepcopy(self.review)
        for margin, compression, uplift in [(5,105,21),(12.5,112.5,22.5),(0,100,20),(5,105,21)]:
            for _ in range(2):
                loads = geotech_section_and_loads(self.review,margin_percent=margin)[1]
                self.assertEqual([r['raw_kip'] for r in loads],[100,20])
                self.assertEqual([r['handoff_kip'] for r in loads],[compression,uplift])
                self.assertEqual([r['short_tons'] for r in loads],[compression/2,uplift/2])
                self.assertTrue(all(r['source_xml']==self.review['filename'] for r in loads))
        self.assertEqual(self.review,original)
        self.assertEqual(geotech_section_and_loads(self.review)[1][0]['handoff_kip'],105)

    def test_invalid_margin_missing_and_zero_loads(self):
        for value in [-1,float('nan'),float('inf'),True,'5']:
            with self.assertRaises(ValueError):
                geotech_section_and_loads(self.review,margin_percent=value)
        for row in self.review['forces']:
            row['axial_tension_kip']=0
        self.assertEqual([r['short_tons'] for r in geotech_section_and_loads(self.review)[1]],[0,0])
        for row in self.review['forces']:
            row['state']='SERVICE-I'
        self.assertEqual([r['short_tons'] for r in geotech_section_and_loads(self.review)[1]],[None,None])


class SplitNotebookTests(unittest.TestCase):
    def setUp(self):
        self.app = CapNotebook()
        self.addCleanup(lambda:self.app.close())
        self.p = self.app.pile_review
        self.p._import((FIXTURES/'fbmp_610_piles.xml').read_bytes(),'MinimumTip.xml')
        self.p.trial_text.value='1,2,4,50,1\n2,2,4,40,1.01'
        self.p.reference.value='24.5';self.p.cutoff.value='40'
        self.p.trial_label.value='Lateral trial study'
        self.p._trials()

    def fixed(self):
        self.app.xml_import.stage((FIXTURES/'fbmp_610_cap.xml').read_bytes(),'FixedDepth.xml')
        self.assertIsNotNone(self.app.xml_import.pending,self.app.xml_import.status.value)
        self.app.xml_import.apply()

    def test_both_upload_orders_keep_sources_and_handoff_independent(self):
        before=self.p.snapshot()
        self.fixed()
        self.assertEqual(self.p.snapshot(),before)
        cap=deepcopy(self.app.case)
        self.p._import((FIXTURES/'fbmp_610_piles.xml').read_bytes(),'MinimumTip.xml')
        self.assertEqual(self.app.case,cap)
        self.assertEqual(self.p.snapshot(),before)
        self.assertIn('as intended',self.p.source_match.value)
        self.assertTrue(all(r['source_xml']=='MinimumTip.xml' for r in self.p.handoff_data()['loads']))
        self.app.xml_import.stage(b'<broken','invalid.xml')
        self.assertEqual(self.app.case,cap)
        self.assertEqual(self.p.snapshot(),before)
        # A new study clears only its trial/datum inputs; cap design stays intact.
        self.p._import((FIXTURES/'fbmp_610_piles.xml').read_bytes()+b'\n','NextStudy.xml')
        self.assertEqual(self.p.cutoff.value,'')
        self.assertEqual(self.app.case,cap)

    def test_margin_exports_once_without_changing_cap_or_minimum_tip(self):
        self.fixed()
        cap=deepcopy(self.app.case);review=deepcopy(self.p.review)
        tip=deepcopy(self.p.minimum_tip_result)
        raw=self.p.handoff_data()['loads'][0]['raw_short_tons']
        self.p.reaction_margin.value=7.5
        for _ in range(2):
            with TemporaryDirectory() as directory:
                self.p.save_handoff(directory)
                rows=list(csv.DictReader(io.StringIO((Path(directory)/'factored_pile_loads_tons.csv').read_text(encoding='utf-8-sig'))))
                self.assertAlmostEqual(float(rows[0]['short_tons']),raw*1.075)
                self.assertEqual(float(rows[0]['raw_short_tons']),raw)
                self.assertEqual(float(rows[0]['margin_percent']),7.5)
                self.assertEqual(rows[0]['source_xml'],'MinimumTip.xml')
                html=(Path(directory)/'geotech_handoff.html').read_text(encoding='utf-8')
                self.assertIn('original × 1.075',html)
                self.assertIn('MinimumTip.xml',html)
                self.assertNotIn('FixedDepth.xml',html)
        self.assertEqual(self.app.case,cap);self.assertEqual(self.p.review,review)
        self.assertEqual(self.p.minimum_tip_result,tip)
        self.p.reaction_margin.value=-1
        self.assertIn('HANDOFF INPUT NEEDS REVIEW',self.p.handoff.value)
        with TemporaryDirectory() as directory,self.assertRaises(ValueError):self.p.save_handoff(directory)

    def test_combined_save_restore_and_invalid_load_are_safe(self):
        self.fixed();self.p.reaction_margin.value=8
        state=self.app.notebook_snapshot()
        with TemporaryDirectory() as directory:
            self.app.export_root=Path(directory)
            with patch.object(self.p,'_download') as download:
                self.app.save_both.click()
                saved=json.loads(download.call_args.args[0].read_text())
            self.assertEqual(saved,state)
        self.p.reaction_margin.value=0
        self.app.controls['Mu_B'].value+=10
        self.app.case_import.load(json.dumps(state).encode(),'notebook_state.json')
        self.assertEqual(self.app.notebook_snapshot(),state)
        self.assertIn('also restored',self.app.case_import.status.value)
        invalid=deepcopy(state);invalid['minimum_tip']['controls']['reaction_margin']=-5
        self.app.case_import.load(json.dumps(invalid).encode(),'bad.json')
        self.assertIn('IMPORT FAILED',self.app.case_import.status.value)
        self.assertEqual(self.app.notebook_snapshot(),state)
        # Old pile reviews acquire the explicit new project default.
        legacy=deepcopy(state['minimum_tip']);legacy['schema_version']=4
        legacy['controls'].pop('reaction_margin')
        self.p.restore(legacy)
        self.assertEqual(self.p.reaction_margin.value,5)

    def test_notebook_cells_preserve_both_sources_and_displayed_cap(self):
        self.fixed();self.p.reaction_margin.value=9
        original=self.app.notebook_snapshot();old_cap_ui=self.app.cap_ui
        nb=json.loads((ROOT/'Cap_and_Pile_Design.ipynb').read_text(encoding='utf-8'))
        context=dict(app=self.app,case=deepcopy(self.app.case),ROOT=ROOT)
        with patch.object(CapNotebook,'display') as display:
            exec(''.join(next(c for c in nb['cells'] if c.get('id')=='7447e4cc')['source']),context)
            display.assert_called_with('minimum_tip')
            self.app=context['app'];self.p=self.app.pile_review
            self.assertIs(self.app.cap_ui,old_cap_ui)
            exec(''.join(next(c for c in nb['cells'] if c.get('id')=='fixed-depth-cap')['source']),context)
            display.assert_called_with('cap')
        self.assertEqual(self.app.notebook_snapshot(),original)


if __name__=='__main__':unittest.main()
