"""Simple backwall tops and minimum slab thickness at measured native points."""
import copy
import json
from pathlib import Path
import unittest
import numpy as np
from test_bridge_physical_geometry import load_model

ROOT=Path(__file__).resolve().parents[1]

class BackwallRampConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env,cls.model=load_model()
        cls.native=json.loads((ROOT/'tests/data/backwall_ramp_tops.json').read_text())

    def test_both_tops_are_two_planes_and_level_through_wall(self):
        for eb in self.model.end_bents:
            wall=next(w for w in eb['solid_geometry']['walls'] if w['kind']=='Backwall')
            profile=eb['backwall_profile']
            y=profile['Offset (ft)'].to_numpy();z=profile['Backwall top (ft)'].to_numpy()
            np.testing.assert_allclose(np.diff(z)/np.diff(y),[.02,-.02],atol=1e-12)
            self.assertEqual(len(wall['xy']),5)
            for s in np.linspace(*wall['bounds'],7):
                cut=next(c for c in self.model.support_section(float(s)) if c['id']==wall['id'])
                np.testing.assert_allclose(cut['xy'],wall['xy'],atol=1e-12)

    def test_both_connections_have_at_least_four_inches_at_native_samples(self):
        for index,sid in enumerate(('EB1','EB2')):
            eb=self.model.end_bents[index];p=eb['backwall_profile']
            thickness=[]
            for sample in self.native['walls'][sid]:
                top=float(np.interp(sample['offset_ft'],p['Offset (ft)'],p['Backwall top (ft)']))
                thickness.append((sample['slab_top_ft']-top)*12)
            self.assertGreater(len(thickness),100)
            self.assertGreaterEqual(min(thickness),4.)
            self.assertLess(max(thickness),5.)
            # The former 4-in drop is too high at the rear of both backwalls.
            self.assertLess(min(thickness)-.25,4.)

    def test_drop_changes_only_selected_wall_quantity(self):
        cfg=copy.deepcopy(self.model.cfg)
        cfg['end_bents']['start']['backwall_drop_in']+=.25
        changed=self.env['BridgeModel'](cfg)
        a,b=self.model.end_bents[0],changed.end_bents[0]
        self.assertAlmostEqual(a['wall_summary']['backwall_volume_ft3']-b['wall_summary']['backwall_volume_ft3'],(235/12)*(.25/12),places=10)
        self.assertEqual(self.model.end_bents[1]['wall_summary'],changed.end_bents[1]['wall_summary'])
        self.assertEqual(a['top'],b['top'])

if __name__=='__main__':unittest.main()
