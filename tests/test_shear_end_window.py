"""Hand-counted end windows and independent station scans for rate truncation."""
import unittest

from pier_cap.lrfd_checks import section_window,window_steel,forces
from pier_cap.section_search import section,critical_search
from tests.test_signed_sectional import simple_engine,bar


class EndWindowTests(unittest.TestCase):
    def setUp(self):
        self.e=simple_engine()
        value=self.e.value
        self.e.value=lambda k,*args:198. if k=='L_cap' else value(k,*args)
        self.inventory=[bar(4),bar(32)]
        self.physical=[dict(id=str(x),station_in=x,bar=4,run='R') for x in range(3,198,6)]
        self.dev={'R':dict(pending=False,ratio=.5)}

    def row(self,x,nu=-10.,tu=0.):
        return section(self.e,dict(moment=100.,vu=80.,nu=nu,tu=tu),x,self.inventory,
                       self.physical,self.dev,.4/6,900.,120.,True)

    def test_concrete_bounds_include_end_cover_and_both_ends(self):
        for x,bounds in ((12.,(0.,36.)),(108.,(84.,120.)),(60.,(36.,84.)),
                         (0.,(0.,24.)),(120.,(96.,120.))):
            with self.subTest(x=x):
                w=section_window(self.physical,x,48.,120.)
                self.assertEqual((w['left_in'],w['right_in']),bounds)
                self.assertEqual(w['available_length_in'],bounds[1]-bounds[0])
                self.assertEqual(w['length_in'],48.)
                self.assertEqual(w['bar_ids'],window_steel(self.physical,x,x,48.)['bar_ids'])

    def test_window_longer_than_beam_and_empty_steel(self):
        w=section_window([],10.,48.,20.)
        self.assertEqual(w['available_length_in'],20.)
        self.assertEqual((w['area_in2'],w['bar_ids']),(0,[]))
        self.assertEqual(section_window([],50.,30.,20.)['available_length_in'],0.)

    def test_end_rate_and_simplified_eligibility_use_available_length(self):
        # Three twin-leg #4 stirrups = 1.2 in², in 18 in of concrete.
        # 1.2/30 fails the 0.061924 minimum; 1.2/18 passes it.
        for x in (3.,195.):
            with self.subTest(x=x):
                r=self.row(x);w=r['window']
                self.assertEqual(r['method'],'5.7.3.4.1')
                self.assertEqual(len(w['bar_ids']),3)
                self.assertAlmostEqual(w['area_in2'],1.2)
                self.assertEqual(w['length_in'],30.)
                self.assertEqual(w['available_length_in'],18.)
                self.assertAlmostEqual(r['effective_rate'],1.2/18)
                self.assertLess(1.2/30,r['minimum_rate'])
                self.assertTrue(r['minimum_transverse'])
                self.assertTrue(r['simplified_eligible'])
                self.assertAlmostEqual(r['minimum_ratio'],r['minimum_rate']/(1.2/18))
                # The nominal window still counts all three anchored stirrups.
                self.assertAlmostEqual(r['developed_window_area_in2'],1.2)
                self.assertAlmostEqual(r['vs'],72.)
                self.assertAlmostEqual(r['vs_credited_kip'],72.)

    def test_interior_denominator_keeps_full_length(self):
        r=self.row(99.)
        self.assertEqual(r['window']['available_length_in'],r['window']['length_in'])
        self.assertAlmostEqual(r['effective_rate'],r['window']['area_in2']/r['window']['length_in'])

    def test_general_angle_and_torsion_use_same_truncated_rate(self):
        for tu in (0.,1000.):
            with self.subTest(tu=tu):
                r=self.row(3.,nu=20.,tu=tu);w=r['window']
                nominal=30*r['cot']
                self.assertEqual(r['method'],'5.7.3.4.2')
                self.assertAlmostEqual(w['length_in'],nominal)
                self.assertAlmostEqual(w['available_length_in'],3+nominal/2)
                self.assertAlmostEqual(r['effective_rate'],w['area_in2']/(3+nominal/2))
                self.assertEqual(r['minimum_transverse'],min(.4/6,r['effective_rate'])+1e-12>=r['minimum_rate'])
                self.assertAlmostEqual(r['vs'],w['area_in2']*60)
                self.assertAlmostEqual(r['developed_window_area_in2'],w['area_in2'])
                if r['torsion_required']:
                    self.assertAlmostEqual(r['torsion_ratio'],r['combined_required_rate']/min(.4/6,r['effective_rate']))

    def test_no_stirrups_does_not_gain_credit_from_truncation(self):
        self.physical=[]
        r=self.row(3.,nu=20.)
        self.assertEqual(r['effective_rate'],0.)
        self.assertFalse(r['minimum_transverse'])
        self.assertEqual(r['vs'],0.)
        self.assertGreater(r['minimum_ratio'],1.)

    def test_end_search_matches_independent_dense_stations(self):
        # Use ample steel to isolate the end-transition and bar-count events.
        for b in self.physical:b['bar']=6
        for left,right in ((3.,30.),(168.,195.)):
            for nu in (-10.,20.):
                with self.subTest(left=left,nu=nu):
                    m=dict(left=0.,right=198.,length=198.,mi=0.,mj=100.,vi=80.,vj=80.,
                           ni=nu,nj=nu,nu=nu,ti=0.,tj=0.,tu=0.)
                    def at(x):
                        return section(self.e,forces(m,x),x,self.inventory,self.physical,
                                       self.dev,.88/6,900.,120.,True)
                    context=dict(e=self.e,m=m,inventory=self.inventory,dev=self.dev,rate=.88/6,region=None)
                    points,meta=critical_search(at,left,right,self.physical,algebraic_context=context)
                    self.assertEqual(meta['method'],'numerical critical locations')
                    self.assertTrue(meta['converged'],meta)
                    dense=[at(left+(right-left)*i/1350) for i in range(1351)]
                    for field in ('minimum_ratio','shear_ratio','ratio','torsion_ratio'):
                        expected=max(r[field] for r in dense)
                        self.assertGreaterEqual(max(r[field] for r in points)+2e-4*max(1.,expected),expected,field)


if __name__=='__main__':unittest.main()
