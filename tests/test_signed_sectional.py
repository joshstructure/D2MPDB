"""Signed FBMP and independent LRFD arithmetic/branch/search regressions."""
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from lxml import etree as ET
from pier_cap.axial import CONVENTION, validate_axial
from pier_cap.fbmp import import_fbmp_xml
from pier_cap.io import load_case
from pier_cap.model import default_case, evaluate, upgrade_case
from pier_cap.lrfd_checks import shear_parameters, steel_at, forces, source_members
from pier_cap.section_search import section, critical_search
from pier_cap.shear import compression_flange, crack_spacing

FIXTURE=Path(__file__).parent/'fixtures/fbmp_610_cap.xml'


def simple_engine():
    c=default_case();c['inputs'].update(fc=6,b=48,h=36,Es=29000,fy=60,fpc=0)
    c['screening']['aggregate_confirmed']=True
    values={'dv':30.,'Ec':4000.}
    return SimpleNamespace(case=c,value=lambda k,*_:values[k])


def bar(y,area=5.):
    return dict(id=str(y),kind='Bottom row 1' if y<18 else 'Top row 1',additional=False,
        y=y,area=area,credited_area=area,left_in=-200.,right_in=400.,
        straight_left_in=-200.,straight_right_in=400.,required_in=20.)


def params(e,n=1.,m=100.,v=50.,area=5.,rate=1.,t=0.,**kw):
    return shear_parameters(e,dict(moment=m,vu=v,nu=n,tu=t),area,rate,900.,120.,
        compression_steel=[bar(32)],all_steel=[bar(4),bar(32)],**kw)


class SignedImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.case=import_fbmp_xml(FIXTURE)

    def test_fixture_independent_signed_extrema_and_four_examples(self):
        audit=self.case['analysis']['xml_audit']
        self.assertEqual(validate_axial(audit),'')
        for combo,elem,raw_i,expected in [('1','6',9.98,-9.98),('1','12',20.15,-20.15),
                                          ('2','8',25.58,-25.58),('1','15',-4.88,4.88)]:
            pair={r['side']:r for r in audit['end_records'] if r['combination']==combo and r['element']==elem}
            self.assertEqual(pair['I']['raw_axial'],raw_i)
            self.assertEqual(pair['J']['raw_axial'],-raw_i)
            for row in pair.values():
                self.assertEqual(row['axial'],expected)
                self.assertEqual(row['axial_convention'],CONVENTION)
                self.assertEqual(len(row['coordinates_in']),3)
        for label,value in [('max axial force',4.88),('min axial force',-25.58)]:
            self.assertEqual(audit['summary_checks'][label],dict(extracted=value,summary=value))

    def test_equilibrium_and_signed_summary_are_independent_checks(self):
        for mutation,match in [('end','axial end-force equilibrium'),('summary','max axial force')]:
            root=ET.parse(str(FIXTURE))
            if mutation=='end':root.find('.//PIER_CAP/ELEMENT/STRUCTURE_ELEMENT_I_END/AXIAL').text='100'
            else:root.find('.//STRUCTURE_PIER_CAP_MAX/MAX_ITEM[@item="max axial force"]/ITEM_VALUE').text='25.58'
            with self.assertRaisesRegex(ValueError,match):import_fbmp_xml(ET.tostring(root))

    def test_missing_axial_and_unreviewed_orientation_schema_rejected(self):
        for mutation in ('missing','unit','orientation','version'):
            root=ET.parse(str(FIXTURE));n=root.find('.//PIER_CAP/ELEMENT/STRUCTURE_ELEMENT_I_END/AXIAL')
            if mutation=='missing':n.getparent().remove(n)
            elif mutation=='unit':n.set('units','lb')
            elif mutation=='orientation':root.find('.//PIER_GEOMETRY/NODAL_COORDINATES/NODE/COORDINATES/Y').text='5'
            else:root.find('PROJECT_INFO/VERSION_NUMBER').text='6.2.0'
            with self.assertRaises(ValueError):import_fbmp_xml(ET.tostring(root))

    def test_repeat_loading_never_reverses_sign_twice(self):
        case=deepcopy(self.case)
        for _ in range(3):case=load_case(json.dumps(case).encode())
        self.assertEqual(case['analysis']['xml_audit']['end_records'],self.case['analysis']['xml_audit']['end_records'])

    def test_unversioned_legacy_axial_remains_unresolved(self):
        case=deepcopy(self.case);audit=case['analysis']['xml_audit']
        audit.pop('axial_convention');audit.pop('axial_schema_version')
        for r in audit['end_records']:r['axial']=r.pop('raw_axial')
        old=deepcopy(audit['end_records']);case=upgrade_case(case)
        self.assertIn('unresolved',case['analysis']['xml_audit']['axial_status'])
        self.assertEqual(case['analysis']['xml_audit']['end_records'],old)
        self.assertFalse(source_members(evaluate(case))[0])

    def test_explicit_raw_provenance_migrates_once_and_checks_summary(self):
        case=deepcopy(self.case);audit=case['analysis']['xml_audit']
        audit['axial_convention']='fbmp-6.1.0-raw-end';audit.pop('axial_schema_version')
        for r in audit['end_records']:r['axial']=r.pop('raw_axial')
        migrated=upgrade_case(case)
        self.assertEqual(validate_axial(migrated['analysis']['xml_audit']),'')
        self.assertEqual(upgrade_case(migrated),migrated)

    def test_reimport_preserves_cage_and_existing_mvt(self):
        c=deepcopy(self.case);c['inputs']['n_N1']=7
        new=import_fbmp_xml(FIXTURE,base=c)
        self.assertEqual(new['inputs'],c['inputs'])
        self.assertEqual(new['analysis']['xml_audit']['governing'],c['analysis']['xml_audit']['governing'])

    def test_fast_and_detailed_evaluators_use_identical_source_solution(self):
        a=evaluate(self.case);b=evaluate(self.case,fast=True)
        self.assertEqual(a.lrfd['source_notice'],b.lrfd['source_notice'])
        for group in ('N','P','B'):
            ar=max(r['ratio'] for r in a.lrfd['longitudinal'] if r['group']==group)
            br=max(r['ratio'] for r in b.lrfd['longitudinal'] if r['group']==group)
            self.assertAlmostEqual(ar,br,places=8)
        self.assertTrue(all(r['long_theta']==r['theta'] for r in b.lrfd['longitudinal']))

    def test_optimizer_preserves_axial_source_in_trials(self):
        from unittest.mock import patch
        import pier_cap.optimizer as optimizer
        config=optimizer.SearchConfig(max_cases=1)
        seen=[];original=optimizer.evaluate
        def tracked(case,**kw):
            seen.append(case['analysis'].get('xml_audit',{}).get('axial_convention'))
            return original(case,**kw)
        c=deepcopy(self.case);c['inputs'].update(Ready_pile=True,Pile_embed=0,C_pile=0)
        with patch.object(optimizer,'evaluate',side_effect=tracked):optimizer.search(c,config)
        self.assertTrue(seen)
        self.assertEqual(set(seen),{CONVENTION})

    def test_uniform_import_report_and_plot_use_shared_station_results(self):
        from pier_cap.calculation_report import Report, BY_NAME
        from pier_cap.visuals import results_figure, spacing_html, hoop_explanation_html
        e=evaluate(self.case);report=Report(e)
        self.assertFalse(report.actual)
        self.assertTrue(report.sectional)
        for name in ('cot_theta','Vc','Vr_G','T_threshold','F_long_N'):
            self.assertEqual(report.equation(BY_NAME[name]),'')
        figure=results_figure(e)
        shear=next(t for t in figure.data if t.name.startswith('Sectional shear'))
        self.assertEqual(list(shear.y),[r['shear_ratio'] for r in e.lrfd['intervals']])
        self.assertEqual(list(shear.x),[r['station_in']/12 for r in e.lrfd['intervals']])
        self.assertIn('shared concurrent station search',spacing_html(e))
        self.assertIn('larger G/L pitch',hoop_explanation_html(e))


class ShearArithmeticTests(unittest.TestCase):
    def test_compression_zero_and_numerical_noise_use_simplified(self):
        e=simple_engine()
        for n in (-25.,0.,1e-12):
            q=params(e,n=n)
            self.assertEqual((q['beta'],q['theta'],round(q['cot'],12)),(2.,45.,1.))
            self.assertIsNone(q['epsilon'])
            self.assertIsNotNone(q['epsilon_diagnostic'])

    def test_genuine_small_tension_is_general_without_doubling(self):
        for n in (1e-8,.001,4.88):
            q=params(simple_engine(),n=n)
            self.assertEqual(q['method'],'5.7.3.4.2')
            self.assertFalse(q['compression_face']['cracked'])
            self.assertEqual(q['strain_multiplier'],1)
            self.assertAlmostEqual(q['epsilon_base'],(100*12/30+.5*n+50 if 100*12>=50*30 else 100+.5*n)/(29000*5))

    def test_finite_flange_cracking_threshold_and_actual_moment(self):
        e=simple_engine();action=dict(moment=0.,nu=1000.,veff=20.)
        q=compression_flange(e,action,[bar(32)])
        ft=.213*math.sqrt(6);net=48*36/2-5
        threshold=ft*(net+29000/4000*5)
        self.assertAlmostEqual(q['cracking_force_kip'],threshold)
        for offset,expected in [(-.001,False),(.001,True)]:
            n=2*(threshold-20)+offset
            r=params(e,n=n,m=0,v=20)
            self.assertEqual(r['compression_face']['cracked'],expected)
            self.assertEqual(r['strain_multiplier'],2 if expected else 1)
            self.assertAlmostEqual(r['epsilon'],r['epsilon_base']*(2 if expected else 1))
            self.assertEqual(r['compression_face']['actual_moment_kip_in'],0)
            self.assertEqual(r['m_for_epsilon_kip_in'],600)

    def test_strain_point_zero_zero_two_hand_values(self):
        e=simple_engine();q=params(e,n=20,m=0,v=140,area=5)
        self.assertAlmostEqual(q['epsilon'],.002)
        self.assertAlmostEqual(q['beta'],1.92)
        self.assertAlmostEqual(q['theta'],36)
        self.assertAlmostEqual(q['cot'],1.3763819204711736)

    def test_negative_strain_explicit_zero_option_and_no_clipping(self):
        e=simple_engine();q=params(e,n=-5000,rate=0)
        self.assertLess(q['epsilon_base'],0)
        self.assertEqual(q['epsilon'],0)
        self.assertEqual(q['theta'],29)
        self.assertIn('zero permitted',q['negative_strain_treatment'])
        q=params(e,n=1,area=.01)
        self.assertGreater(q['epsilon'],.006)
        self.assertFalse(q['valid']);self.assertEqual(q['vr'],0)
        self.assertAlmostEqual(q['theta'],29+3500*q['epsilon'])

    def test_no_minimum_beta_uses_developed_distributed_layers(self):
        e=simple_engine();layers=[bar(y,2) for y in (4,12,20,28,32)]
        s=crack_spacing(e,layers)
        self.assertEqual(s['sx_in'],8)
        self.assertEqual(s['sxe_in'],12)
        for b in layers:b['credited_area']=.01
        self.assertEqual(crack_spacing(e,layers)['sx_in'],30)
        q=params(e,n=0,rate=0)
        self.assertEqual(q['method'],'5.7.3.4.2')
        self.assertFalse(q['minimum_transverse'])
        self.assertAlmostEqual(q['beta'],4.8/(1+750*q['epsilon'])*51/(39+q['sxe_in']))

    def test_depth_exception_does_not_override_axial_tension(self):
        e=simple_engine();e.case['inputs']['h']=15
        self.assertEqual(params(e,n=0,rate=0)['method'],'5.7.3.4.1')
        self.assertEqual(params(e,n=.001,rate=0)['method'],'5.7.3.4.2')
        e.case['screening']['aggregate_confirmed']=False
        self.assertTrue(params(e,n=0,rate=0)['valid'])
        self.assertFalse(params(e,n=.001,rate=0)['valid'])

    def test_torsion_effective_force_floor_and_no_resistance_factor_in_strain(self):
        e=simple_engine();q=params(e,n=2,m=0,v=30,t=1000)
        effective=math.hypot(30,.9*120*1000*12/(2*900))
        self.assertAlmostEqual(q['veff'],effective)
        self.assertAlmostEqual(q['m_for_epsilon_kip_in'],30*30)
        self.assertAlmostEqual(q['epsilon_base'],(30+effective+1)/(29000*5))
        e.case['inputs']['phi_v']=.6
        self.assertEqual(params(e,n=2,m=0,v=30,t=1000)['epsilon_base'],q['epsilon_base'])

    def test_missing_compression_half_is_specific_unresolved_input(self):
        e=simple_engine();q=shear_parameters(e,dict(moment=0,vu=0,nu=1000,tu=0),5,1)
        self.assertFalse(q['valid'])
        self.assertIn('Compression-half', '; '.join(q['applicability_warnings']))


class ConcurrentSearchTests(unittest.TestCase):
    def setUp(self):
        self.e=simple_engine();self.inventory=[bar(4),bar(32)]
        self.physical=[dict(id=str(x),run='R',station_in=x,bar=6) for x in range(0,201,8)]
        self.dev={'R':dict(pending=False,ratio=.5)}

    def row(self,x,n=20,m=None):
        action=dict(moment=100-(x-53.271)**2/30 if m is None else m,vu=80+.4*x,nu=n,tu=0)
        return section(self.e,action,x,self.inventory,self.physical,self.dev,.88/8,900,120,True)

    def test_same_theta_window_vs_credit_and_actual_longitudinal_moment(self):
        q=self.row(60,m=0)
        self.assertEqual(q['long_theta'],q['theta'])
        self.assertAlmostEqual(q['window']['length_in'],30*q['cot'])
        self.assertEqual(q['moment_tension_kip'],0)
        self.assertGreater(q['m_for_epsilon_kip_in'],0)
        self.assertLessEqual(q['vs_credited_kip'],q['vu']/self.e.case['inputs']['phi_v'])
        self.assertAlmostEqual(q['full_tension_kip'],max(0,q['moment_tension_kip']+q['axial_tension_kip']+q['diagonal_tension_kip']))
        self.assertEqual(q['minimum_transverse'],min(.88/8,q['effective_rate'])>=q['minimum_rate'])

    def test_theta_changes_actual_intersected_bars(self):
        a=self.row(60,n=-10);b=self.row(60,n=20)
        self.assertNotEqual(a['theta'],b['theta'])
        self.assertNotEqual(a['window']['bar_ids'],b['window']['bar_ids'])

    def test_general_window_minimum_does_not_relabel_45_degree_eligibility(self):
        bars=[dict(id=str(i),run='R',station_in=x,bar=6) for i,x in enumerate((40,40,80,80))]
        q=section(self.e,dict(moment=100,vu=80,nu=-10,tu=0),60,self.inventory,bars,self.dev,.88/8,900,120,True)
        self.assertEqual(q['method'],'5.7.3.4.2')
        self.assertTrue(q['minimum_transverse'])
        self.assertFalse(q['simplified_eligible'])
        self.assertIn('less than minimum transverse',q['simplified_reason'])
        self.assertIn('45-degree',q['simplified_reason'])

    def test_development_and_moment_sign_change_tension_side(self):
        self.inventory[0].update(left_in=40,required_in=40)
        a=self.row(50,m=100);b=self.row(50,m=-100)
        self.assertAlmostEqual(a['steel_area_in2'],1.25)
        self.assertAlmostEqual(b['steel_area_in2'],5)
        self.assertGreater(a['epsilon_base'],b['epsilon_base'])

    def test_interior_and_branch_events_match_independent_dense_scan(self):
        points,meta=critical_search(self.row,40,70,self.physical)
        dense=[self.row(40+i*.01) for i in range(3001)]
        self.assertTrue(meta['converged'])
        self.assertGreater(meta['samples'],3)
        self.assertGreater(meta['event_count'],0)
        for field in ('ratio','shear_ratio','minimum_ratio'):
            found=max(r[field] for r in points);reference=max(r[field] for r in dense)
            self.assertGreaterEqual(found+2e-4*max(1,reference),reference)
        winner=max(points,key=lambda r:r['ratio'])
        self.assertGreater(winner['station_in'],40)
        self.assertLess(winner['station_in'],70)

    def test_nonconvergence_is_explicit(self):
        _,meta=critical_search(self.row,40,70,self.physical,max_levels=1)
        self.assertFalse(meta['converged'])

    def test_forces_interpolate_signed_concurrent_n_and_t(self):
        m=dict(left=0,right=120,length=120,mi=0,mj=100,vi=10,vj=10,
            nu=5,ni=-5,nj=5,tu=10,ti=-10,tj=10)
        q=forces(m,60)
        self.assertEqual(q['nu'],0);self.assertEqual(q['tu'],0)


if __name__=='__main__':unittest.main()
