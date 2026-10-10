"""Hand-checkable 2024 LRFD / 2026 FDOT actual-cage and applicability cases."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from pier_cap.lrfd_checks import (development_length,direct_regions,forces,member_roots,
    settings,steel_at,window_steel,source_members,torsion_threshold,shear_parameters)
from pier_cap.model import evaluate,set_inputs,formula_trace,upgrade_case
from pier_cap.transverse import suggested_detail,shear_intervals
from pier_cap.fbmp import import_fbmp_xml
from pier_cap.io import export_bundle,load_case
from pier_cap.lrfd_views import working_html
from tests.case_fixtures import default_case
from tests.test_fbmp import FIXTURE


def actual_case(xml=False):
    c=import_fbmp_xml(FIXTURE) if xml else default_case()
    c['transverse_detail']=suggested_detail(evaluate(c))
    return c


def region_fixture(sign=1):
    c=default_case();c['lrfd_checks'].update(bearing_loading='top',pile_connection='pinned',
        load_path_basis='Unit-test direct load path',continuous_splices='none')
    c['analysis']['xml_audit']={'end_records':[{'x_in':0}],
        'bearing_stations_in':[50],'pile_centers_in':[50]}
    e=SimpleNamespace(case=c,value=lambda name,*_:20.)
    inventory=[dict(id='main',kind='Top row 1' if sign<0 else 'Bottom row 1',
        additional=False,area=10.,y=c['inputs']['h']-4 if sign<0 else 4,
        left_in=-100,right_in=200,straight_left_in=-100,straight_right_in=200,required_in=12)]
    members=[dict(combo='1',element='a',state='STRENGTH-I',left=0,right=50,length=50,
        mi=0,mj=100*sign,vi=24*sign,vj=24*sign,nu=0,tu=0),
        dict(combo='1',element='b',state='STRENGTH-I',left=50,right=100,length=50,
        mi=100*sign,mj=0,vi=-24*sign,vj=-24*sign,nu=0,tu=0)]
    return e,members,inventory


class LRFDActualTests(unittest.TestCase):
    def test_tenth_edition_straight_and_hook_hand_values(self):
        # #6, fc=5.5 ksi, fy=60, cb=3.375: lambda_rc is limited to 0.3.
        d=development_length(.75,.44,60,5.5,cb=3.375,coating='uncoated')
        self.assertAlmostEqual(d['basic_in'],50.4311519530)
        self.assertAlmostEqual(d['required_in'],15.1293455859)
        h=development_length(.75,.44,60,5.5,cb=3.375,coating='uncoated',hook_radius=2.625)
        self.assertAlmostEqual(h['fh'],4.87265625)
        self.assertAlmostEqual(h['required_in'],13.0598888170)
        adverse=development_length(.75,.44,60,5.5,cb=3.375,top=True)
        self.assertAlmostEqual(adverse['required_in'],1.7*d['required_in'])
        self.assertEqual(development_length(.375,.11,20,10,cb=10,coating='uncoated')['required_in'],12)

    def test_development_credit_decreases_at_cutoff(self):
        e,m,bars=region_fixture()
        bars[0].update(left_in=0,right_in=100,straight_left_in=0,straight_right_in=100,required_in=20)
        self.assertAlmostEqual(steel_at(bars,5,e.case['inputs']['h'],'bottom')[0]['credited_area'],2.5)
        self.assertAlmostEqual(steel_at(bars,50,e.case['inputs']['h'],'bottom')[0]['credited_area'],10)
        self.assertEqual(steel_at(bars,101,e.case['inputs']['h'],'bottom'),[])

    def test_direct_loading_is_explicit_and_does_not_mean_all_pile_regions(self):
        e,m,b=region_fixture();r=direct_regions(e,m,b)
        self.assertEqual(len(r),1);self.assertTrue(r[0]['qualifies'])
        e.case['lrfd_checks']['bearing_loading']='unknown'
        self.assertFalse(direct_regions(e,m,b)[0]['qualifies'])
        e,m,b=region_fixture(-1)
        self.assertTrue(direct_regions(e,m,b)[0]['qualifies'])
        e.case['lrfd_checks']['pile_connection']='moment'
        self.assertFalse(direct_regions(e,m,b)[0]['qualifies'])
        e.case['lrfd_checks']['support_overrides']={'1':'pinned'}
        self.assertTrue(direct_regions(e,m,b)[0]['qualifies'])

    def test_exception_requires_extension_splices_record_and_no_torsion(self):
        for change in ('extension','splices','record','torsion','axial'):
            e,m,b=region_fixture()
            if change=='extension':b[0]['left_in']=45
            elif change=='splices':e.case['lrfd_checks']['continuous_splices']='present'
            elif change=='record':e.case['lrfd_checks']['load_path_basis']=''
            elif change=='torsion':m[0]['tu']=1e6
            else:m[0]['nu']=1
            self.assertFalse(direct_regions(e,m,b)[0]['qualifies'],change)

    def test_member_extremum_and_zero_moment_are_recovered(self):
        m=dict(left=0,right=120,length=120,mi=-50,mj=-50,vi=40,vj=-40,nu=0,tu=0)
        self.assertEqual(member_roots(m,'shear'),[60])
        self.assertAlmostEqual(forces(m,60)['moment'],50)
        roots=member_roots(m)
        self.assertEqual(len(roots),2)
        for x in roots:self.assertAlmostEqual(forces(m,x)['moment'],0)

    def test_fdot_window_counts_legs_and_checks_both_sides_of_events(self):
        bars=[dict(id=str(x),run='R1',station_in=x,bar=6) for x in (0,10,20,30,40)]
        # At x=20, a 20-in window contains only the station-20 stirrup
        # conservatively excluding bars exactly on its boundaries: 2 * 0.44.
        self.assertAlmostEqual(window_steel(bars,19,21,20)['area_in2'],.88)
        self.assertAlmostEqual(window_steel(bars,15,15,20)['area_in2'],1.76)
        unresolved={'R1':dict(pending=True,ratio=.5)}
        self.assertEqual(window_steel(bars,15,15,20,unresolved)['area_in2'],0)
        unresolved['R1']['pending']=False
        self.assertAlmostEqual(window_steel(bars,15,15,20,unresolved)['area_in2'],1.76)

    def test_no_reference_checks_or_unconfirmed_exception_and_shared_outputs(self):
        c=actual_case(True);before=deepcopy(c);e=evaluate(c)
        self.assertEqual(c,before)
        self.assertFalse(any(x.status=='REFERENCE' for x in e.checks))
        self.assertFalse(any(r['qualifies'] for r in e.lrfd['regions']))
        self.assertFalse(any(r['exception_applied'] for r in e.lrfd['longitudinal']))
        self.assertTrue(all(r['vs_credited_kip']==0 for r in e.lrfd['longitudinal']))
        self.assertFalse(any(c.status=='PENDING' for c in e.checks if c.key.startswith(('Chk_hoop_clear_','Chk_drawn_hoop_legs_'))))
        self.assertEqual([v['vr'] for v in shear_intervals(e)],[r['vr'] for r in e.lrfd['intervals']])
        trace={r['name']:r for r in formula_trace(e)}
        self.assertIn('Active actual-cage',trace['Chk_long_B']['note'])
        self.assertIn('FDOT',working_html(e))

    def test_changed_demands_disable_source_exemptions(self):
        c=actual_case(True);e=evaluate(c)
        self.assertTrue(source_members(e)[0])
        edited=evaluate(set_inputs(c,Mu_B=c['inputs']['Mu_B']+200))
        self.assertFalse(source_members(edited)[0])
        self.assertFalse(edited.lrfd['regions'])
        self.assertIn('differ',edited.lrfd['source_notice'])
        self.assertTrue(all(r['pending'] for r in edited.lrfd['longitudinal']))

    def test_torsion_threshold_and_shear_domain(self):
        e=evaluate(actual_case());limit=torsion_threshold(e)
        self.assertGreater(limit,torsion_threshold(e,100))
        self.assertEqual(torsion_threshold(e,1e8),0)
        act=dict(moment=10,vu=50,nu=0,tu=0)
        p=shear_parameters(e,act,5,1)
        self.assertEqual((p['beta'],p['theta']),(2,45))
        act['nu']=100
        p=shear_parameters(e,act,.001,1)
        self.assertFalse(p['valid'])

    def test_open_u_torsion_is_a_failed_calculation_above_threshold(self):
        e=evaluate(set_inputs(actual_case(),Tu=10000))
        checks={c.key:c for c in e.checks}
        self.assertEqual(checks['Status_actual_torsion'].status,'FAIL')
        self.assertTrue(any(r['torsion_ratio']>1 and not r['closed'] for r in e.lrfd['longitudinal']))

    def test_settings_export_and_reimport_retain_calculations(self):
        c=actual_case();c['lrfd_checks'].update(coating='uncoated',support_overrides={'2':'moment'})
        with tempfile.TemporaryDirectory() as root:
            out=export_bundle(c,root);saved=load_case(out/'selected_case.json')
            self.assertEqual(saved['lrfd_checks'],c['lrfd_checks'])
            data=json.loads((out/'lrfd_calculations.json').read_text(encoding='utf8'))
            self.assertEqual(data['settings'],c['lrfd_checks'])
            self.assertTrue((out/'lrfd_regions.csv').exists())
            self.assertTrue((out/'lrfd_longitudinal.csv').stat().st_size>0)
            self.assertEqual(len(data['longitudinal']),len(evaluate(saved).lrfd['longitudinal']))

    def test_controls_update_and_load_per_pile_basis(self):
        from pier_cap.widgets import CapNotebook
        app=CapNotebook(actual_case())
        try:
            self.assertEqual(app.plot_tabs.get_title(6),'LRFD regions & checks')
            app.lrfd_panel.controls['coating'].value='uncoated'
            app.lrfd_panel.piles['2'].value='moment'
            self.assertEqual(app.current.lrfd['settings']['support_overrides'],{'2':'moment'})
            new=deepcopy(app.case);new['lrfd_checks']['support_overrides']={'1':'pinned'}
            app.load(new)
            self.assertEqual(app.lrfd_panel.piles['1'].value,'pinned')
            self.assertEqual(app.lrfd_panel.piles['2'].value,'inherit')
        finally:app.close()


if __name__=='__main__':unittest.main()
