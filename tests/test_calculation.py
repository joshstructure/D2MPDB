import json
import math
import unittest
from pier_cap.model import DATA,DEFINITIONS,default_case,evaluate,set_inputs,bar_positions,analysis_match
from pier_cap.engine import Engine,Q,parse
from pier_cap.optimizer import search,SearchConfig,candidate_case

class CalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.base=evaluate()

    def test_all_saved_source_results(self):
        reference=json.loads((DATA/'baseline_reference.json').read_text(encoding='utf-8'))
        self.assertEqual(len(DEFINITIONS),324)
        for name,expected in reference.items():
            if name not in self.base.engine.defs:continue  # Three linked journal externals are now explicit inputs.
            with self.subTest(name=name):
                v=self.base.engine.get(name)
                if isinstance(expected,dict):
                    self.assertEqual(tuple(expected['dimensions']),v.d)
                    self.assertTrue(math.isclose(v.v,expected['value'],rel_tol=1e-10,abs_tol=1e-9))
                else:self.assertEqual(v,expected)
        self.assertEqual(len(self.base.checks),35)
        self.assertAlmostEqual(self.base.max_dc,41.375/42)

    def test_independent_mechanics(self):
        fc=5.5;fy=60;b=h=48.;As=8*.79;Av=2*.31;dc=3+.625+.5;d=h-dc
        a=As*fy/(.85*fc*b);beta=.85-.05*(fc-4);c=a/beta
        dv=max(.9*d,.72*h,d-a/2);mr=.9*As*fy*(d-a/2)
        Ec=120000*.145**2*fc**.33;n=round(29000/Ec,2)
        ccr=(-n*As+math.sqrt((n*As)**2+2*b*d*n*As))/b
        Icr=b*ccr**3/3+n*As*(d-ccr)**2
        Vc=.0316*2*math.sqrt(fc)*b*dv;Vs=Av*fy*dv/8
        Tcr=.126*math.sqrt(fc)*(b*h)**2/(2*(b+h));Ao=.85*(b-6-.625)*(h-6-.625)
        At=33.83*12/.9*8/(2*Ao*fy);ph=2*(b+h-12-1.25)
        Fvt=math.sqrt((205.11/.9)**2+(.45*ph*33.83*12/(2*Ao*.9))**2)
        skinreq=min(.012*(d-30)*(d/24),As/4)
        reference={'L_cap':224,'E_end':12,'As_N':As,'As_P':As,'As_B':As,'Av':Av,'As_side':6*.31,
            'dc_N':dc,'dc_P':dc,'dc_B':dc,'a_N':a,'c_N':c,'dv':dv,'Mr_N':mr,'Mr_P':mr,'Mr_B':mr,
            'Ec':Ec,'n_mod':n,'ccr_N':ccr,'Icr_N':Icr,'Vc':Vc,'Vs_G':Vs,'Vr_G':.9*(Vc+Vs),
            'Ao':Ao,'At_G':At,'T_threshold':.25*.9*Tcr,'F_vt':Fvt,'As_skin_req':skinreq,'Ash_req':.26/12,
            'Ash_prov':.465/12,'VS_cap':(48*48*224)/(2*(48*48+48*224+48*224))}
        for z,mu,mi in [('N',169.44,148.19),('P',143.56,103.46),('B',337.61,293.7)]:
            stress=mi*12*n*(d-ccr)/Icr
            reference.update({f'DC_flex_{z}':mu*12/mr,f'fs_I_{z}':stress,f'SI_{z}':700/((1+dc/(.7*(h-dc)))*stress)-2*dc,f'F_long_{z}':mu*12/(.9*dv)+Fvt})
        self.assertEqual(len(reference),43)
        for k,v in reference.items():
            with self.subTest(name=k):self.assertTrue(math.isclose(self.base.value(k),v,rel_tol=1e-9,abs_tol=1e-8))

    def test_engineering_scenarios(self):
        scenarios=[
            ({'n_skin':10},'Av',.62),
            ({'Mu_B':2000},'Chk_flex_B','FAIL'),
            ({'Vu_G':3000},'Chk_shear_G','FAIL'),
            ({'Vu_G':0,'Vu_L':0},'Chk_shear_G','PASS'),
            ({'s_G':24},'Chk_spacing_G','FAIL'),
            ({'Tu':800},'Chk_torsteel_G','FAIL'),
            ({'N_pile':5},'L_cap',284),
            ({'S_pile':6},'L_cap',260),
            ({'S_pile':4},'Chk_piles','FAIL'),
            ({'n_N2':4,'n_N3':2,'Bar_N2':9,'Bar_N3':10},'As_N',12.86),
            ({'C_t':4},'dc_N',5.125),
            ({'n_PU':2,'Bar_U':5},'As_P',6.94),
            ({'Manual_spacing':True,'SP_detail_B':40},'Chk_I_B','FAIL'),
            ({'Ready_III':True,'MIII_B':700},'Chk_III_B','FAIL'),
            ({'Ready_fatigue':True,'DMLL_B':1000,'MDL_B':100},'Chk_fat_B','FAIL'),
            ({'Ready_fatigue':True,'MDL_B':4000,'DMLL_B':1},'Chk_fat_B','FAIL'),
            ({'n_skin':0},'Chk_skin_area','FAIL'),
            ({},'Mass_required',False),
            ({'b':72,'h':72},'Mass_required',True),
            ({'fc':12},'alpha_1',.81),
            ({'Vu_L':1000},'Chk_shear_L','FAIL'),
            ({'Ready_III':True,'Ready_fatigue':True,'MIII_N':150,'MIII_P':120,'MIII_B':300,'MDL_N':100,'MDL_P':70,'MDL_B':200,'DMLL_N':20,'DMLL_P':30,'DMLL_B':40},'Status_overall','SECTIONAL CHECKS PASS')]
        for changes,name,expected in scenarios:
            with self.subTest(changes=changes):
                e=evaluate(set_inputs(default_case(),**changes));v=e.value(name)
                if isinstance(expected,str):self.assertIn(expected,v)
                elif isinstance(expected,bool):self.assertIs(expected,v)
                else:self.assertAlmostEqual(v,expected)

    def test_floor_and_units(self):
        self.assertEqual(self.base.value('s_suggest_G'),8)
        self.assertEqual(self.base.value('s_suggest_L'),8)
        with self.assertRaises(ValueError):self.base.engine.eval(parse('Floor(8 in,1 in)'),{})
        with self.assertRaises(AssertionError):self.base.engine.eval(parse('1 in + 1 kip'),{})
        with self.assertRaises(AssertionError):self.base.value('Mu_N','in')

    def test_pending_is_not_pass(self):
        self.assertIn('PENDING',self.base.status)
        ratios={c.key:c.ratio for c in self.base.checks}
        self.assertEqual(ratios['Status_III'],'PENDING');self.assertEqual(ratios['Status_fatigue'],'PENDING')
        e=evaluate(set_inputs(default_case(),Ready_fatigue=True,MDL_B=4000,DMLL_B=1))
        self.assertFalse(e.eligible)
        self.assertEqual(next(c.ratio for c in e.checks if c.key=='Status_fatigue'),'INVALID')

    def test_geometry_provenance_gates(self):
        for name,value in [('N_pile',5),('S_pile',6),('D_pile',18),('b',50),('h',50),('E_detail',2),('E_clear',10)]:
            with self.subTest(name=name):
                case=set_inputs(default_case(),**{name:value});e=evaluate(case)
                self.assertIn(name,e.stale);self.assertFalse(e.eligible)
                with self.assertRaises(ValueError):search(case)
                case['analysis']['geometry'][name]=value
                self.assertFalse(analysis_match(case))

    def test_scalar_matches_units_across_changes(self):
        for size in (5,6,8,10):
            for count in (4,8,12):
                case=set_inputs(default_case(),Bar_N1=size,Bar_pos=size,n_N1=count,n_B1=count,n_P1=count,Ready_III=True,Ready_fatigue=True,MIII_B=300,MDL_B=200,DMLL_B=40)
                a=evaluate(case);b=evaluate(case,fast=True)
                for name in a.engine.defs:
                    v=a.value(name);w=b.value(name)
                    if isinstance(v,(int,float)) and not isinstance(v,bool):self.assertTrue(math.isclose(v,w,rel_tol=1e-9,abs_tol=1e-8),name)
                    else:self.assertEqual(v,w,name)
                self.assertEqual(a.eligible,b.eligible);self.assertAlmostEqual(a.max_dc,b.max_dc)

    def test_invalid_inputs_are_rejected(self):
        for change in ({'fc':0},{'s_G':0},{'theta':90},{'alpha_v':0},{'n_N1':1},{'n_skin':1.5},{'Bar_v':12},{'b':5},{'Mu_B':float('nan')},{'Ready_III':'false'}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):evaluate(set_inputs(default_case(),**change))

    def test_drawing_changes_and_cage_screen(self):
        count=len(bar_positions(self.base))
        e=evaluate(set_inputs(default_case(),n_N2=4))
        self.assertEqual(len(bar_positions(e)),count+4)
        self.assertGreater(e.value('As_N'),self.base.value('As_N'))
        e=evaluate(set_inputs(default_case(),n_N1=50))
        self.assertTrue(any('clear spacing' in s for s in e.issues));self.assertFalse(e.eligible)
        for change in ({'n_PU':2},{'n_loop':2}):
            self.assertFalse(evaluate(set_inputs(default_case(),**change)).eligible)

class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.result=search(default_case())
    def test_default_search(self):
        r=self.result
        self.assertEqual(r.total,1944);self.assertEqual(r.evaluated,1944);self.assertTrue(r.exhaustive)
        self.assertGreater(r.passed,0);self.assertEqual(len(r.candidates),20)
        self.assertEqual([c.weight_lb for c in r.candidates],sorted(c.weight_lb for c in r.candidates))
        for i,c in enumerate(r.candidates):
            e=evaluate(candidate_case(r,i));self.assertTrue(e.eligible);self.assertIn('PENDING',e.status)
        self.assertEqual(default_case()['inputs']['n_N1'],8)
    def test_budget_and_determinism(self):
        c=SearchConfig(max_cases=20)
        a=search(default_case(),c);b=search(default_case(),c)
        self.assertFalse(a.exhaustive);self.assertEqual(a.evaluated,20)
        self.assertEqual(a.candidates,b.candidates);self.assertEqual(a.rejection_counts,b.rejection_counts)
    def test_empty_or_failed_domain(self):
        with self.assertRaises(ValueError):search(default_case(),SearchConfig(main_bars=()))
        case=set_inputs(default_case(),Mu_B=10000)
        r=search(case,SearchConfig(max_cases=15));self.assertEqual(r.passed,0);self.assertEqual(r.candidates,[])
    def test_other_objectives(self):
        for objective in ('Simplest cage','Largest margin'):
            r=search(default_case(),SearchConfig(main_bars=(8,),top_counts=(6,8),bottom_counts=(6,8),objective=objective))
            values=[c.complexity if objective=='Simplest cage' else c.max_dc for c in r.candidates]
            self.assertEqual(values,sorted(values));self.assertGreater(len(values),0)

if __name__=='__main__':unittest.main()
