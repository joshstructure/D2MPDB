"""Notebook layout, live station stepping, and repeatable output setup."""
import ast
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class NotebookWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook=json.loads((ROOT/'Bridge_Geometry_2 Beam_V2.ipynb').read_text(encoding='utf-8'))
        cls.cells={c['id']:c for c in cls.notebook['cells']}

    def test_output_setup_precedes_inputs_and_registers_only_once(self):
        ids=[c['id'] for c in self.notebook['cells']]
        self.assertLess(ids.index('bridge-output-layout'),ids.index('bridge-03'))
        class Events:
            def __init__(self):self.callbacks={'pre_run_cell':[]}
            def register(self,name,fn):self.callbacks[name].append(fn)
            def unregister(self,name,fn):self.callbacks[name].remove(fn)
        events=Events();env={}
        with patch('IPython.get_ipython',return_value=SimpleNamespace(events=events)),patch('IPython.display.display'),redirect_stdout(io.StringIO()):
            for _ in range(2):exec(''.join(self.cells['bridge-output-layout']['source']),env)
        self.assertEqual(len(events.callbacks['pre_run_cell']),1)
        self.assertTrue(all(c['metadata'].get('scrolled') is False for c in self.notebook['cells'] if c['cell_type']=='code'))

    def test_all_static_snapshot_calls_share_one_cell(self):
        render_names={'show_quantities','show_pier','show_end_bent','section_figure','longitudinal_figure','clearance_card'}
        for cell in self.notebook['cells']:
            if cell['cell_type']!='code':continue
            tree=ast.parse(''.join(cell['source']))
            # Definitions and the live dashboard have their own deferred display calls.
            body=[node for node in tree.body if not isinstance(node,(ast.FunctionDef,ast.ClassDef))]
            calls=[node.func.id for statement in body for node in ast.walk(statement)
                   if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in render_names]
            if calls:self.assertEqual(cell['id'],'bridge-snapshots')
        code=''.join(self.cells['bridge-snapshots']['source'])
        self.assertIn("dashboard['state']['model']",code)
        self.assertIn('snapshot_qc=qc_checks(SNAPSHOT_MODEL)',code)

    def test_live_widget_steps_preserve_support_at_reported_stations(self):
        env={}
        for ident in ('bridge-02','bridge-03','bridge-05','bridge-06'):
            exec(''.join(self.cells[ident]['source']),env)
        env['CONFIG']['roadway']['xml_path']=str(ROOT/'Geometry Report.xml')
        model=env['BridgeModel'](env['CONFIG'])
        seen=[]
        def section(model,station,*args):
            seen.append(env['section_geometry'](model,station)[0])
            return None
        with patch.dict(env,display=lambda *args:None,show_table=lambda *args:None,
                        longitudinal_figure=lambda *args,**kwargs:None,section_figure=section,
                        show_pier=lambda *args:None,show_end_bent=lambda *args:None,show_quantities=lambda *args:None),redirect_stdout(io.StringIO()):
            dashboard=env['make_dashboard'](env['CONFIG'],model)
            for station,name in ((1593.22,'End Bent 1'),(1700.57,'Pier'),(1805.47,'End Bent 2')):
                dashboard['station'].value=station
                dashboard['forward'].click()
                self.assertAlmostEqual(dashboard['station'].value,station+.01)
                self.assertEqual(seen[-1]['support']['name'],name)
                self.assertTrue(any(c['kind']=='Cap' for c in seen[-1]['components']))
                self.assertIn('Physical support geometry',dashboard['message'].value)
                self.assertIn('cap limits',dashboard['message'].value)
        env['plt'].close('all')


if __name__=='__main__':unittest.main()
