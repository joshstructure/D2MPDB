"""Service plot limits meet the existing checks exactly, with honest gates."""
from copy import deepcopy
import unittest

from pier_cap.model import evaluate, set_inputs, bar_positions
from pier_cap.detailing import row_spacing
from pier_cap.engine import parse
from pier_cap.service_limits import service_limit, moment_segments, moment_hover, add_stress_limits
from pier_cap.force_diagrams import cap_force_figure
from pier_cap.fbmp import import_fbmp_xml
from tests.test_fbmp import FIXTURE
from tests.case_fixtures import default_case
from plotly.subplots import make_subplots


class ServiceLimitsTests(unittest.TestCase):
    def test_inverted_limits_satisfy_original_equations_and_cross_at_one(self):
        case=set_inputs(default_case(),Ready_III=True,n_B1=2)
        e=evaluate(case)
        for state in ('I','III'):
            for z in 'NPB':
                r=service_limit(e,state,z)
                self.assertTrue(r['available'])
                # Independent forward evaluations of the stored formula set.
                for factor in (.999,1.,1.001):
                    key='MI_'+z if state=='I' else 'MIII_'+z
                    eng=e.engine.fork({**e.engine.overrides,key:e.engine.eval(parse(f'{factor*r["spacing_moment"]:.14g} kip*ft'),{})})
                    spacing=eng.get('S'+state+'_'+z).v
                    self.assertAlmostEqual(spacing,700*case['inputs']['gamma_e']/(e.value('bs_'+z)*factor*r['spacing_stress'])-2*e.value('dc_'+z),places=7)
                    self.assertEqual(spacing<r['pitch'],factor>1) if factor!=1 else self.assertAlmostEqual(spacing,r['pitch'],places=7)
                key='MI_'+z if state=='I' else 'MIII_'+z
                eng=e.engine.fork({**e.engine.overrides,key:e.engine.eval(parse(f'{r["stress_moment"]:.14g} kip*ft'),{})})
                self.assertAlmostEqual(eng.get(('fs_I_' if state=='I' else 'fo_III_')+z).v,r['stress_limit'],places=7)

    def test_zero_demand_does_not_remove_capacity_and_pending_is_not_zero(self):
        e=evaluate(set_inputs(default_case(),MI_N=0,MI_P=0,MI_B=0))
        for z in 'NPB':
            r=service_limit(e,'I',z)
            self.assertGreater(r['moment'],0)
            self.assertIn('(0.0%)',moment_hover([(0,1,1,r)],.5,0))
            self.assertIsNone(service_limit(e,'III',z)['moment'])
        high=evaluate(set_inputs(default_case(),fy=75))
        self.assertFalse(service_limit(high,'I','N')['available'])
        self.assertIn('fy < 75',service_limit(high,'I','N')['reason'])

    def test_pile_gap_exclusion_does_not_leak_into_span_reference(self):
        from pier_cap.model import default_case as start
        e=evaluate(set_inputs(start(),Ready_pile=True,n_B1=0))
        local=service_limit(e,'I','P')
        full=service_limit(e,'I','P',continuous_reference=True)
        bars=[b for b in bar_positions(e,'P') if b['layer']=='Bottom row 1']
        self.assertAlmostEqual(full['pitch'],max(e.value('SP_P'),row_spacing(e,bars)['pitch_in']))
        self.assertGreaterEqual(full['pitch'],local['pitch'])
        self.assertLessEqual(full['moment'],local['moment'])

    def test_service_iii_spacing_is_converted_to_outer_stress_basis(self):
        e=evaluate(set_inputs(default_case(),Ready_III=True,n_N2=3))
        r=service_limit(e,'III','N')
        self.assertNotAlmostEqual(r['stress_rate'],r['centroid_rate'])
        fig=make_subplots(rows=1,cols=2)
        add_stress_limits(fig,e,'III',list('NPB'),row=1,col=1)
        spacing=next(t for t in fig.data if t.meta['capacity']=='spacing_moment')
        self.assertAlmostEqual(spacing.y[0],r['spacing_stress']*r['stress_rate']/r['centroid_rate'])

    def test_negative_positive_steps_and_boundary_margin(self):
        e=evaluate(set_inputs(default_case(),n_B1=2))
        rows=moment_segments(e,'I',e.value('L_cap','ft'))
        self.assertEqual(rows[0][2],-1)
        self.assertTrue(any(r['region']=='B' for _,_,_,r in rows))
        for a,b,sign,r in rows:
            text=moment_hover(rows,(a+b)/2,sign*r['moment'])
            self.assertIn('(100.0%)',text)
            self.assertIn('Remaining moment: 0.00',text)
        b_rows=[row for row in rows if row[3]['region']=='B']
        x=b_rows[0][0]
        adjacent=[r['moment'] for a,b,s,r in rows if s==1 and a<=x<=b]
        self.assertIn(f'Moment limit: {min(adjacent):.2f}',moment_hover(rows,x,1))

    def test_state_selector_and_export_keep_service_iii_separate(self):
        case=import_fbmp_xml(FIXTURE)
        # A separately identified Service III analysis is required for its mode.
        audit=case['analysis']['xml_audit'];ends=[]
        for r in audit['end_records']:
            if r['state']=='SERVICE-I':ends.append(dict(r,state='SERVICE-III',combination='S3-'+str(r['combination'])))
        audit['end_records']+=ends
        case=set_inputs(case,Ready_III=True)
        fig=cap_force_figure(case,show_resistance=True)
        for button in fig.layout.updatemenus[0].buttons:
            for i,t in enumerate(fig.data):
                if (t.meta or {}).get('role')=='service_limit':
                    expected=button.label.startswith(t.meta['state'].replace('SERVICE-','Service ')+' ·')
                    self.assertEqual(button.args[0]['visible'][i],expected)
        service_demand=[t for t in fig.data if t.name.startswith('Moment demand') and t.customdata and t.customdata[0][0]=='Service III']
        self.assertTrue(service_demand)
        self.assertIn('moment utilization',service_demand[0].customdata[0][4])
        case['inputs']['Ready_III']=False
        fig=cap_force_figure(case,show_resistance=True)
        self.assertFalse(any((t.meta or {}).get('state')=='SERVICE-III' for t in fig.data))
        mismatch=cap_force_figure(set_inputs(case,S_pile=7),show_resistance=True)
        self.assertFalse(any((t.meta or {}).get('role')=='service_limit' for t in mismatch.data))


if __name__=='__main__':unittest.main()
