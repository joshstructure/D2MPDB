"""Pile-opening exclusions and explicit added-bottom-bar hook identification."""
from copy import deepcopy
import unittest
from types import SimpleNamespace
from lxml import html

from pier_cap import default_case, evaluate, set_inputs
from pier_cap.model import geometry_evaluation
from pier_cap.transverse_zones import starting_zone_detail
from pier_cap.lrfd_checks import surface_checks
from pier_cap.lrfd_views import working_html
from pier_cap.check_working import _actual, details_html
from pier_cap.detailing import row_spacing


def pile_case():
    c=set_inputs(default_case(),Ready_pile=True,Pile_embed=12,E_detail=3,n_B1=4,n_B2=0,Bar_B=6,n_P1=4)
    c['transverse_detail']=starting_zone_detail(geometry_evaluation(c),5,6)
    return c


class FaceCheckScopeTests(unittest.TestCase):
    def test_pile_gap_is_omitted_but_available_concrete_and_span_gaps_remain(self):
        p=dict(b=48.,Ready_pile=True,Pile_embed=12.,C_pile=2.)
        e=SimpleNamespace(case={'inputs':p},value=lambda n:{'Pile_left':14.,'Pile_right':34.}[n])
        bars=[dict(x=x,y=4.,diameter=1.) for x in (4.,10.,38.,44.)]
        self.assertEqual(row_spacing(e,bars,at_pile=True)['pitch_in'],6.)
        self.assertEqual(row_spacing(e,bars,at_pile=True,edges=True)['pitch_in'],8.)
        self.assertEqual(row_spacing(e,bars,at_pile=False)['pitch_in'],28.)
        above=[dict(b,y=16.) for b in bars]
        self.assertEqual(row_spacing(e,above,at_pile=True)['pitch_in'],28.)
        p['Ready_pile']=False
        self.assertEqual(row_spacing(e,bars,at_pile=True)['pitch_in'],28.)
        p.update(Ready_pile=True,b=80.)
        e.value=lambda n:{'Pile_left':30.,'Pile_right':50.}[n]
        wide=[dict(x=x,y=4.,diameter=1.) for x in (4.,25.,55.,76.)]
        self.assertEqual(row_spacing(e,wide,at_pile=True)['pitch_in'],21.)
        # Even with no adjacent pair, an unreinforced side strip is visible.
        self.assertGreater(row_spacing(e,wide[:1],at_pile=True)['pitch_in'],12.)

    def test_service_inputs_and_drawn_spacing_share_pile_exclusion(self):
        from pier_cap.model import bar_positions
        for mode in ('uniform','actual','failed_fit'):
            c=pile_case()
            if mode=='uniform':c['transverse_detail']['enabled']=False
            elif mode=='failed_fit':c['transverse_detail']['runs'][0]['shape']={'side_inset_in':28}
            e=evaluate(c);fast=evaluate(c,fast=True)
            bars=[b for b in bar_positions(e,'P') if b['layer']=='Bottom row 1']
            expected=row_spacing(e,bars,at_pile=True)['pitch_in']
            self.assertAlmostEqual(e.value('SP_P'),expected)
            self.assertAlmostEqual(fast.value('SP_P'),expected)
            check=next(v for v in e.checks if v.key=='Chk_drawn_I_P')
            self.assertAlmostEqual(check.ratio,expected/max(e.value('SI_P'),1e-6))
            self.assertIn('Pile embedment gap',check.basis)
            self.assertIn('Pile embedment gap',next(v for v in e.checks if v.key=='Chk_I_P').basis)

    def test_only_bottom_transverse_excluded_with_open_embedded_pile_stirrups(self):
        c=pile_case();before=deepcopy(c)
        rows,checks=surface_checks(geometry_evaluation(c))
        self.assertEqual(c,before)
        excluded=[r for r in rows if not r.get('included',True)]
        self.assertEqual([(r['face'],r['direction']) for r in excluded],[('Bottom','Transverse')])
        self.assertTrue(excluded[0]['excluded_runs'])
        self.assertIsNone(excluded[0]['area_ratio']);self.assertIsNone(excluded[0]['spacing_ratio'])
        for check,field in zip(checks,('area_ratio','spacing_ratio')):
            self.assertEqual(check.ratio,max(r[field] for r in rows if r.get('included',True)))
            self.assertIn('not a code exemption',check.basis)

    def test_closed_cage_no_embedment_and_off_pile_open_bars_keep_check(self):
        for change in ('closed','no_embedment','off_pile'):
            c=pile_case()
            if change=='no_embedment':c['inputs']['Pile_embed']=0
            elif change=='closed':
                for run in c['transverse_detail']['runs']:run['kind']='hoop'
            else:
                c['transverse_detail']['runs']=[dict(c['transverse_detail']['runs'][0],kind='pile_u')]
            rows,_=surface_checks(geometry_evaluation(c))
            bottom=next(r for r in rows if r['face']=='Bottom' and r['direction']=='Transverse')
            self.assertTrue(bottom.get('included',True),change)
            self.assertIsInstance(bottom['area_ratio'],float)
            self.assertIsInstance(bottom['spacing_ratio'],float)

    def test_register_working_and_report_share_scope_and_hook_identity(self):
        e=evaluate(pile_case());checks={c.key:c for c in e.checks}
        for key,field in [('Chk_shrink_area','area_ratio'),('Chk_shrink_space','spacing_ratio')]:
            row=max((r for r in e.lrfd['faces'] if r.get('included',True)),key=lambda r:r[field])
            values={n:v for n,v,u in _actual(e,checks[key])[1]}
            self.assertEqual(values['Governing face'],row['face']+' · '+row['direction'])
            self.assertAlmostEqual(checks[key].ratio,row[field])
        doc=html.fromstring(working_html(e));text=doc.text_content()
        self.assertIn('EXCLUDED',text)
        hook=checks['Status_hook_development'];operands={n:v for n,v,u in _actual(e,hook)[1]}
        selected=next(r for r in e.lrfd['inventory'] if r['id']==operands['Governing bar'])
        self.assertTrue(selected['additional']);self.assertEqual(selected['bar'],6)
        self.assertEqual(operands['Bar group / row'],'Added span row 1')
        self.assertEqual(operands['Span'],f'P{selected["span"]}–P{selected["span"]+1}')
        self.assertAlmostEqual(hook.ratio,selected['required_in']/((selected['right_in']-selected['left_in'])/2))
        detail=html.fromstring(details_html(e,hook)).text_content()
        for value in ('Added bottom span bars','Additional bottom longitudinal bars',selected['id'],'#6',operands['Span']):
            self.assertIn(value,hook.label+' '+detail)
        self.assertIn(hook.status,('PENDING','FAIL'))
        self.assertIn('Cutoff/extension',hook.basis)

    def test_no_added_bars_has_explicit_zero_demand(self):
        e=evaluate(set_inputs(pile_case(),n_B1=0,n_B2=0))
        hook=next(c for c in e.checks if c.key=='Status_hook_development')
        self.assertEqual(hook.ratio,0.)
        self.assertIn('No additional bottom span bars',hook.basis)
        self.assertIn('No additional bottom longitudinal bars',_actual(e,hook)[0])
