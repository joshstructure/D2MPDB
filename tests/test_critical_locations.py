"""Algebraic candidates checked against independent dense section evaluations."""
from copy import deepcopy
import unittest
from pier_cap.critical_locations import algebraic_search
from pier_cap.lrfd_checks import forces
from pier_cap.section_search import section,critical_search,dense_search
from tests.test_signed_sectional import simple_engine,bar


class AlgebraicLocationTests(unittest.TestCase):
    def setUp(self):
        self.e=simple_engine()
        self.e.case['lrfd_checks']['phi_axial']=.9
        self.inventory=[bar(4),bar(32)]
        self.physical=[dict(id=str(x),run='R',station_in=x,bar=6) for x in range(0,201,8)]
        self.dev={'R':dict(pending=False,ratio=.5)}
        self.member=dict(left=40.,right=70.,length=30.,mi=100.,mj=125.,vi=80.,vj=-20.,
                         ni=-10.,nj=-10.,nu=-10.,ti=0.,tj=0.,tu=0.)
        self.region=None

    def row(self,x):
        return section(self.e,forces(self.member,x),x,self.inventory,self.physical,self.dev,
                       .88/8,900,120,True,self.region)

    def solve(self):
        return algebraic_search(self.e,self.member,40,70,self.inventory,self.physical,
                                self.dev,.88/8,self.region,self.row)

    def assert_dense(self):
        result=self.solve();self.assertIsNotNone(result)
        points,meta=result
        dense=[self.row(40+i*.01) for i in range(3001)]
        for field in ('ratio','shear_ratio','minimum_ratio','torsion_ratio','inverse_resistance'):
            actual=max(r[field] for r in points);reference=max(r[field] for r in dense)
            self.assertGreaterEqual(actual+1e-8*max(1,reference),reference,field)
        self.assertTrue(meta['converged'])
        return points,meta

    def test_quadratic_linear_ratio_interior_controller(self):
        self.inventory[0].update(left_in=-10.,right_in=160.,required_in=100.)
        points,meta=self.assert_dense()
        roots=[r for r in points if 'stationary longitudinal' in r['station_reason']]
        self.assertTrue(roots)
        for r in roots:
            x=r['station_in'];h=1e-4
            self.assertAlmostEqual((self.row(x+h)['ratio']-self.row(x-h)['ratio'])/(2*h),0.,places=7)
        _,old=dense_search(self.row,40,70,self.physical)
        self.assertLess(meta['samples'],old['samples']/2)

    def test_hook_cutoffs_and_overlapping_development_zones(self):
        added=deepcopy(self.inventory[0])
        added.update(id='added',additional=True,area=1.76,left_in=52.,right_in=68.,
                     straight_left_in=55.,straight_right_in=65.,required_in=12.)
        self.inventory.append(added)
        points,_=self.assert_dense()
        for x in (55.,60.,65.):
            self.assertTrue(any(abs(r['station_in']-x)<1e-10 for r in points))
            self.assertTrue(any(x-3e-6<r['station_in']<x for r in points))
            self.assertTrue(any(x<r['station_in']<x+3e-6 for r in points))

    def test_direct_limit_and_developed_vs_credit(self):
        self.region=dict(qualifies=True,peak_moment_kip_ft=110.)
        self.dev['R']['pending']=True
        self.assert_dense()

    def test_developed_shear_credit_saturates_inside_segment(self):
        self.dev['unanchored']=dict(pending=True,ratio=2.)
        for b in self.physical:
            if b['station_in']!=48:b['run']='unanchored'
        points,_=self.assert_dense()
        expected=40+(80-.88*60*self.e.case['inputs']['phi_v'])/100*30
        self.assertTrue(any(abs(r['station_in']-expected)<1e-8 for r in points))

    def test_inconsistent_context_uses_fallback(self):
        def inconsistent(x):
            r=self.row(x);r['ratio']+=.02
            return r
        self.assertIsNone(algebraic_search(self.e,self.member,40,70,self.inventory,self.physical,
                                           self.dev,.88/8,self.region,inconsistent))

    def test_integrated_selector_and_fallback(self):
        context=dict(e=self.e,m=self.member,inventory=self.inventory,dev=self.dev,rate=.88/8,region=None)
        _,meta=critical_search(self.row,40,70,self.physical,algebraic_context=context)
        self.assertEqual(meta['method'],'algebraic critical locations')
        self.member.update(ni=20.,nj=20.)
        _,meta=critical_search(self.row,40,70,self.physical,algebraic_context=context)
        self.assertEqual(meta['method'],'numerical critical locations')
        self.assertTrue(meta['converged'])

    def test_axial_tension_torsion_and_general_branch_use_existing_search(self):
        for update in (dict(ni=20.,nj=20.),dict(ti=1000.,tj=1000.)):
            previous=deepcopy(self.member);self.member.update(update)
            self.assertIsNone(self.solve());self.member=previous
        self.physical=[dict(id='sparse',run='R',station_in=0.,bar=6)]
        self.assertIsNone(self.solve())

    def test_axial_sign_change_cannot_be_certified_from_midpoint(self):
        self.member.update(ni=-100.,nj=1.)
        self.assertIsNone(self.solve())

    def test_both_moment_signs_and_force_zeros(self):
        self.member.update(mi=-30.,mj=30.,vi=-10.,vj=30.)
        self.assert_dense()


if __name__=='__main__':unittest.main()
