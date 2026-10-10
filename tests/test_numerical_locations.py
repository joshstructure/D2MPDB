"""Numerical critical locations compared with independent fine section scans."""
from copy import deepcopy
import math
import unittest
from unittest.mock import patch
from pier_cap.numerical_locations import numerical_search,FIELDS
from pier_cap.section_search import section,critical_search,dense_search,signature
from tests.test_signed_sectional import simple_engine,bar


class NumericalLocationTests(unittest.TestCase):
    def setUp(self):
        self.e=simple_engine();self.inventory=[bar(4),bar(32)]
        self.physical=[dict(id=str(x),run='R',station_in=x,bar=6) for x in range(0,201,8)]
        self.dev={'R':dict(pending=False,ratio=.5)};self.region=None
        self.actions=lambda x:dict(moment=100-(x-53.271)**2/30,vu=80+.4*x,nu=20.,tu=0.)

    def row(self,x):
        return section(self.e,self.actions(x),x,self.inventory,self.physical,self.dev,
                       .88/8,900.,120.,True,self.region)

    def compare(self,left=40.,right=70.,converged=True):
        points,meta=numerical_search(self.row,left,right,self.physical)
        if converged:self.assertTrue(meta['converged'],meta)
        count=math.ceil((right-left)/.01)
        dense=[self.row(left+(right-left)*i/count) for i in range(count+1)]
        for field in FIELDS:
            expected=max(r.get(field) or 0. for r in dense)
            found=max(r.get(field) or 0. for r in points)
            self.assertGreaterEqual(found+2e-4*max(1.,expected),expected,field)
        # Domain and detailing classifications must also survive retention.
        def flags(r):return signature(r)[:7]+signature(r)[8:]
        self.assertTrue({flags(r) for r in dense}<={flags(r) for r in points})
        return points,meta

    def test_variable_angle_interior_controller_and_evaluation_reduction(self):
        points,meta=self.compare()
        _,reference=dense_search(self.row,40,70,self.physical)
        self.assertLess(meta['samples'],reference['samples']/3)
        x=max(points,key=lambda r:r['ratio'])['station_in']
        self.assertTrue(40<x<70)
        self.assertAlmostEqual(self.row(x)['ratio'],max(r['ratio'] for r in points))

    def test_investigated_torsion_and_changing_window(self):
        self.actions=lambda x:dict(moment=100-(x-53.271)**2/30,vu=80+.4*x,nu=20.,tu=500+2*x)
        points,_=self.compare()
        self.assertTrue(all(r['torsion_required'] for r in points))

    def test_torsion_threshold_crossing_and_zero(self):
        self.actions=lambda x:dict(moment=150.,vu=80.,nu=20.,tu=abs(15*(x-53)))
        points,_=self.compare()
        self.assertEqual({r['torsion_required'] for r in points},{True,False})

    def test_sparse_stirrups_and_unverified_development(self):
        self.physical=[dict(id=str(x),run='R',station_in=x,bar=6) for x in (0,43,75,110,160,200)]
        self.dev['R']['pending']=True
        points,_=self.compare()
        self.assertTrue(any(not r['minimum_transverse'] for r in points))
        self.assertTrue(all(r['vs_credited_kip']==0 for r in points))

    def test_partial_development_and_added_hook_cutoffs(self):
        added=deepcopy(self.inventory[0])
        added.update(id='added',additional=True,area=1.76,left_in=45.,right_in=69.,
                     straight_left_in=48.,straight_right_in=66.,required_in=15.)
        self.inventory.append(added)
        # The production caller provides these physical/development cuts.
        for a,b in zip((40.,48.,54.,57.,60.,66.),(48.,54.,57.,60.,66.,70.)):
            self.compare(a,b)

    def test_moving_window_enters_and_exits_between_original_nodes(self):
        self.actions=lambda x:dict(moment=300+10*(x-55)**2,vu=30.,nu=20.,tu=0.)
        # Right window edge peaks at about x=62.69. This bar intersects only
        # for a 0.111-in interval, between the initial validation/model nodes.
        self.physical=[dict(id='neighbor',run='R',station_in=81.49908093475136,bar=6)]
        points,meta=self.compare(55.,65.)
        self.assertEqual(meta['event_count'],2)
        self.assertEqual({bool(r['window']['bar_ids']) for r in points},{False,True})
        for root in (62.633984168,62.744881206):
            self.assertTrue(any(abs(r['station_in']-root)<1e-6 for r in points))

    def test_flange_cracking_two_crossings_with_same_endpoint_state(self):
        threshold=self.row(54)['compression_face']['cracking_force_kip']
        # Quadratic actual moment creates a narrow cracked region away from
        # the initial nine nodes; signed margin roots must discover both sides.
        center=54.327;halfwidth=.03
        self.actions=lambda x:dict(moment=20+10*(x-center)**2,vu=40.,
            nu=2*(threshold-40.+.4*(20+10*halfwidth**2)),tu=0.)
        self.assertFalse(self.row(40)['compression_face']['cracked'])
        self.assertTrue(self.row(center)['compression_face']['cracked'])
        points,_=self.compare()
        self.assertTrue(any(r['compression_face']['cracked'] for r in points))
        for root in (center-halfwidth,center+halfwidth):
            self.assertTrue(any(abs(r['station_in']-root)<1e-6 for r in points),root)

    def test_axial_sign_and_direct_demand_cap(self):
        self.actions=lambda x:dict(moment=100-(x-53.271)**2/30,vu=80+.4*x,nu=x-55.,tu=0.)
        self.region=dict(qualifies=True,peak_moment_kip_ft=300.)
        self.compare()

    def test_out_of_domain_strain_never_gains_resistance(self):
        self.inventory[0]['area']=.01
        points,_=self.compare()
        self.assertTrue(all(not r['valid'] and r['adopted_vr'] is None for r in points))

    def test_exhaustion_uses_dense_fallback_and_preserves_attempt(self):
        def exhausted(*args,**kwargs):return numerical_search(*args,**kwargs,max_samples=10)
        with patch('pier_cap.numerical_locations.numerical_search',side_effect=exhausted):
            points,meta=critical_search(self.row,40,70,self.physical)
        self.assertEqual(meta['method'],'adaptive fallback')
        self.assertTrue(meta['converged'])
        self.assertIn('budget',meta['fallback_reason'])
        self.assertFalse(meta['numerical_attempt']['converged'])
        self.assertTrue(points)

    def test_nonconvergence_and_nonfinite_are_explicit(self):
        _,meta=numerical_search(self.row,40,70,self.physical,max_levels=1)
        self.assertFalse(meta['converged'])
        def bad(x):return dict(self.row(x),ratio=float('nan'))
        _,meta=critical_search(bad,40,40.1,self.physical)
        self.assertFalse(meta['converged'])
        self.assertIn('Nonfinite',meta['fallback_reason'])


if __name__=='__main__':unittest.main()
