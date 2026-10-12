"""Source-backed camber, calculated support sections and downstream CAD contract."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
import numpy as np

from bridge_report import cad_geometry_data
from test_bridge_physical_geometry import load_model

ROOT=Path(__file__).resolve().parents[1]


class GeometryAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env,cls.model=load_model()
        cls.cells={c['id']:c for c in json.loads((ROOT/'Bridge_Geometry_2 Beam_V2.ipynb').read_text(encoding='utf-8'))['cells']}

    def test_default_cambers_match_registered_mathcad_results_and_hashes(self):
        basis=json.loads((ROOT/'bridge_geometry/camber_sources.json').read_text())
        self.assertEqual(self.model.cfg['camber_basis'],basis)
        ns={'m':'http://schemas.mathsoft.com/math30'}
        for span,item in zip(self.model.spans.to_dict('records'),basis):
            raw=(ROOT/item['source_file']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),item['source_sha256'])
            definitions=ET.fromstring(raw).findall('.//m:define',ns)
            node=next(d for d in definitions if d.find('m:id',ns) is not None and d.find('m:id',ns).text=='NetCamber')
            self.assertEqual(float(node.find('.//m:result/m:unitedValue/m:real',ns).text),span['camber_in'])

    def test_span_haunch_difference_is_the_camber_difference(self):
        model=self.model
        centers=[(a+b)/2 for a,b in model.bearing_limits]
        h=model.evaluate(centers)['haunch']*12
        difference=model.spans.iloc[1].camber_in-model.spans.iloc[0].camber_in
        np.testing.assert_allclose(h[0]-h[1],difference,atol=1e-10)
        cfg=copy.deepcopy(model.cfg)
        cfg['spans'][0]['camber_in']=cfg['spans'][1]['camber_in']
        equal=self.env['BridgeModel'](cfg)
        for t in (0,.17,.5,.83,1):
            haunch=equal.evaluate([a+(b-a)*t for a,b in equal.bearing_limits])['haunch']
            np.testing.assert_allclose(haunch[0],haunch[1],atol=1e-10)
        self.assertIn('override',equal.camber_summary().iloc[0]['Input basis'])

    def test_snapshot_sections_use_actual_centers_and_labels_follow_sloped_caps(self):
        env=dict(self.env)
        exec(''.join(self.cells['bridge-02']['source']),env)
        exec(''.join(self.cells['bridge-06']['source']),env)
        tree=ast.parse(''.join(self.cells['bridge-snapshots']['source']))
        assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SNAPSHOT_STATIONS' for t in n.targets))
        env['SNAPSHOT_MODEL']=self.model
        exec(compile(ast.Module(body=[assignment],type_ignores=[]),'snapshots','exec'),env)
        np.testing.assert_allclose([s for _,s in env['SNAPSHOT_STATIONS']],[1593.97,1700.57,1804.72])
        cfg=copy.deepcopy(self.model.cfg)
        cfg['pier']['cross_slope']=.01
        model=env['BridgeModel'](cfg)
        for support in model.supports:
            for delta in (0,.01):
                fig=env['section_figure'](model,support['station']+delta)
                labels=[t.get_text() for t in fig.axes[0].texts if ' top\nEL ' in t.get_text()]
                expected=[f"P{p['number']} top\nEL {p['cutoff']:.4f} ft" for p in support['solid_geometry']['piles']]
                self.assertEqual(labels,expected)
                for pile in support['solid_geometry']['piles']:
                    self.assertAlmostEqual(pile['cutoff'],pile['cap_underside']+support['pile_embedment_ft'])
                env['plt'].close(fig)
        fig=env['section_figure'](model,model.pier['station']+1)
        self.assertFalse(any(' top\nEL ' in t.get_text() for t in fig.axes[0].texts))
        env['plt'].close(fig)

    def test_cad_payload_is_traceable_and_retains_analytic_curves_and_solids(self):
        data=cad_geometry_data(self.model,self.env['section_geometry'])
        digest=data.pop('payload_sha256')
        self.assertEqual(hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),digest)
        self.assertEqual(data['configuration'],self.model.cfg)
        self.assertEqual(data['coordinates']['feet_to_mm'],304.8)
        self.assertEqual(data['geometry']['model_id'],data['model_id'])
        # Off-grid curve evaluation agrees after conversion to CAD millimeters.
        for piece in data['geometry']['pieces']:
            t=.391572
            expected=self.model.evaluate([piece['start']+t*(piece['end']-piece['start'])])
            for key,c in piece['fields'].items():
                a,b,q=np.asarray(c)
                np.testing.assert_allclose((a+b*t+q*t*t)*304.8,expected[key][0]*304.8,rtol=0,atol=1e-7)
        for support in data['geometry']['supports']:
            self.assertEqual(len(support['solid_geometry']['piles']),4)
            for pile in support['solid_geometry']['piles']:
                self.assertEqual(pile['station'],support['station'])

    def test_portable_cad_export_uses_applied_model_and_blocks_stale_inputs(self):
        env=dict(self.env);env['MODEL']=self.model
        with patch('IPython.display.display'):
            exec(''.join(self.cells['bridge-report-export']['source']),env)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'geometry.json'
            env['export_cad_geometry'](path=path)
            previous=path.read_bytes()
            self.assertEqual(json.loads(previous)['model_id'],self.model.model_id)
            env['CONFIG']=copy.deepcopy(env['CONFIG'])
            env['CONFIG']['spans'][1]['camber_in']+=.2
            with self.assertRaisesRegex(ValueError,'Apply input changes'):
                env['export_cad_geometry'](path=path)
            self.assertEqual(path.read_bytes(),previous)


if __name__=='__main__':unittest.main()
