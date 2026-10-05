"""Saved run preservation is opt-in and does not claim a new execution."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts.build_portable_notebook import build


class PortableBuildTests(unittest.TestCase):
    def fixture(self, root):
        (root/'pier_cap').mkdir()
        (root/'pier_cap'/'demo.py').write_text('VALUE = 1\n',encoding='utf-8')
        (root/'requirements-pier-cap-colab.txt').write_text('',encoding='utf-8')
        notebook={'cells':[
            {'cell_type':'code','id':'a1e54f80','metadata':{},
             'source':['revision = "abcdef"\n','PACKAGE = "AA=="\n'],
             'execution_count':14,'outputs':[{'output_type':'stream','name':'stdout','text':['Saved result\n']}]},
            {'cell_type':'markdown','metadata':{'saved_run_annotation':True},'source':['Saved run note']}
        ],'metadata':{'widgets':{'saved':'state'}}}
        path=root/'Cap_and_Pile_Design.ipynb'
        path.write_text(json.dumps(notebook,indent=2),encoding='utf-8')
        return path,notebook

    def test_preserve_retains_outputs_widgets_execution_and_format(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,original=self.fixture(root)
            build(root,preserve_outputs=True)
            actual=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(actual['metadata']['widgets'],original['metadata']['widgets'])
            self.assertEqual(actual['cells'][0]['outputs'],original['cells'][0]['outputs'])
            self.assertEqual(actual['cells'][0]['execution_count'],14)
            self.assertEqual(actual['cells'][1],original['cells'][1])
            self.assertTrue(path.read_text(encoding='utf-8').startswith('{\n  "cells":'))
            self.assertNotEqual(actual['cells'][0]['source'],original['cells'][0]['source'])

    def test_clean_build_drops_run_notes_along_with_saved_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,_=self.fixture(root)
            build(root)
            actual=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(len(actual['cells']),1)
            self.assertEqual(actual['cells'][0]['outputs'],[])
            self.assertIsNone(actual['cells'][0]['execution_count'])
            self.assertNotIn('widgets',actual['metadata'])
