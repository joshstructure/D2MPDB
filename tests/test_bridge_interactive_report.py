"""Check the exported report against the notebook and its live applied model."""
import ast
import base64
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from bridge_report import report_data, render_report

ROOT = Path(__file__).resolve().parents[1]


class InteractiveReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook=json.loads((ROOT/'Bridge_Geometry_2 Beam_V2.ipynb').read_text(encoding='utf-8'))
        cls.env=dict(Path=Path,np=np)
        old=os.getcwd()
        os.chdir(ROOT)
        try:
            for index in (4,6):exec(''.join(cls.notebook['cells'][index]['source']),cls.env)
        finally:
            os.chdir(old)
        cls.env['CONFIG']['roadway']['xml_path']=str(ROOT/'Geometry Report.xml')
        tree=ast.parse(''.join(cls.notebook['cells'][7]['source']))
        selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('fib_polygon','section_geometry')]
        exec(compile(ast.Module(body=selected,type_ignores=[]),'notebook-section','exec'),cls.env)
        cls.config=copy.deepcopy(cls.env['CONFIG'])
        cls.model=cls.env['BridgeModel'](cls.config)

    def test_exported_evaluations_follow_notebook_across_profile_and_deck_modes(self):
        for profile,deck in [('brokeback','crowned'),('parabolic','uniform'),('parabolic','transition')]:
            config=copy.deepcopy(self.config)
            config['profile']['mode']=profile
            config['deck']['mode']=deck
            model=self.env['BridgeModel'](config)
            data=report_data(model,self.env['section_geometry'])
            for piece in data['pieces']:
                for t in (.13,.37,.81):
                    station=piece['start']+t*(piece['end']-piece['start'])
                    expected=model.evaluate([station])
                    for name,c in piece['fields'].items():
                        a,b,q=np.asarray(c)
                        np.testing.assert_allclose(a+t*b+t*t*q,expected[name][0],rtol=0,atol=1e-9)

    def test_support_cutoffs_and_uncovered_roadway_tail_are_preserved(self):
        data=report_data(self.model,self.env['section_geometry'])
        expected=[41.196625,41.73325,41.208625]
        for support,cutoff in zip(data['supports'],expected):
            np.testing.assert_allclose([p['Pile cutoff (ft)'] for p in support['piles']],cutoff,rtol=0,atol=1e-9)
        self.assertLess(data['road'][-1]['end'],data['end'])
        self.assertEqual(data['minimum_clearance']['status'],'Covered region only')

    def test_standalone_report_bundles_library_and_no_remote_resources(self):
        text=render_report(self.model,self.env['section_geometry'],1600.123)
        self.assertTrue(text.startswith('<!doctype html>'))
        self.assertNotIn('<script src=',text)
        self.assertIn('d3js.org v7.9.0',text)
        self.assertIn('"initial_station":1600.123',text)
        self.assertIn('bridge-station-slider',text)
        self.assertNotIn('__FRAGMENT__',text)
        self.assertNotIn('__BRIDGE_DATA__',text)

    def test_portable_cell_uses_current_dashboard_and_blocks_unapplied_changes(self):
        env=dict(self.env)
        env['CONFIG']=copy.deepcopy(self.config)
        env['MODEL']=self.model
        config=copy.deepcopy(self.config)
        config['profile']['mode']='parabolic'
        applied=env['BridgeModel'](config)
        env['CONFIG']=config
        env['dashboard']={'state':{'model':applied},'station':SimpleNamespace(value=1630.25)}
        cell=next(c for c in self.notebook['cells'] if c.get('id')=='bridge-report-export')
        with patch('IPython.display.display'),redirect_stdout(io.StringIO()):
            exec(''.join(cell['source']),env)
        self.assertEqual(env['_report_bundle']['source'],(ROOT/'bridge_report/__init__.py').read_text(encoding='utf-8'))
        for name,content in env['_BRIDGE_REPORT_ASSETS'].items():
            self.assertEqual(content,(ROOT/'bridge_report'/name).read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'report.html'
            env['export_interactive_report'](path=target)
            text=target.read_text(encoding='utf-8')
            self.assertIn(f'"model_id":"{applied.model_id}"',text)
            self.assertIn('"initial_station":1630.25',text)
            old=os.getcwd()
            os.chdir(directory)
            try:
                with redirect_stdout(io.StringIO()):
                    env['report_export']['button'].click()
                downloaded=Path(f'Bridge_Geometry_Interactive_Report_{applied.model_id}.html')
                self.assertTrue(downloaded.is_file())
                self.assertIn('"initial_station":1630.25',downloaded.read_text(encoding='utf-8'))
                self.assertFalse(env['report_export']['button'].disabled)
            finally:
                os.chdir(old)
            env['CONFIG']['profile']['start_elev_ft']+=1
            with self.assertRaisesRegex(ValueError,'Apply input changes'):
                env['export_interactive_report'](path=target)
            self.assertEqual(target.read_text(encoding='utf-8'),text)


if __name__=='__main__':
    unittest.main()
