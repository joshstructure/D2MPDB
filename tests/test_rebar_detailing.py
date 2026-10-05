"""Independent geometry, continuity, spacing boundaries and migration checks."""
from copy import deepcopy
import math
import unittest
from pier_cap.model import default_case,set_inputs,evaluate,bar_positions,upgrade_case,BAR_AREA,BAR_DIAMETER
from pier_cap.detailing import required_clear,spacing_records,standard_hook,hook_paths
from pier_cap.visuals import elevation_figure,hoop_figure,hoop_explanation_html,section_figure,reinforcement_summary_html
from pier_cap.optimizer import search,SearchConfig
from pier_cap.widgets import CapNotebook,LABELS


def case(**changes):
    c=set_inputs(default_case(),**(dict(Ready_pile=True,Pile_embed=12,C_pile=1.5,n_P1=4,n_B1=4,n_skin=7)|changes))
    c['screening']['aggregate_confirmed']=True
    return c


def check(e,key):return next(c for c in e.checks if c.key==key)


class RebarDetailingTests(unittest.TestCase):
    def test_combined_area_centroid_and_continuity_for_different_sizes(self):
        e=evaluate(case(Bar_P=9,Bar_B=7,n_P2=2,n_B2=2))
        expected_p=6*1.0;expected_added=6*.60
        self.assertAlmostEqual(e.value('As_P'),expected_p)
        self.assertAlmostEqual(e.value('As_B'),expected_p+expected_added)
        yp=3+.625+1.128/2;yb=3+.625+.875/2
        expected_dc=(1.0*(4*yp+2*(yp+4))+.60*(4*yb+2*(yb+4)))/(expected_p+expected_added)
        self.assertAlmostEqual(e.value('dc_B'),expected_dc)
        pp=bar_positions(e,'P');bb=bar_positions(e,'B')
        self.assertEqual(pp,[b for b in bb if not b['additional']])
        self.assertEqual(sum(b['additional'] for b in bb),6)
        self.assertAlmostEqual(sum(BAR_AREA[b['bar']] for b in bb if b['layer'].startswith('Bottom')),e.value('As_B'))

    def test_old_total_counts_migrate_once_without_mutating_source(self):
        old=case();old['schema_version']=2;old['inputs'].update(n_P1=4,n_B1=8,n_P2=2,n_B2=1)
        original=deepcopy(old);new=upgrade_case(old)
        self.assertEqual(old,original);self.assertEqual(new['inputs']['n_B1'],4)
        self.assertEqual(new['inputs']['n_B2'],0)
        self.assertEqual(new,upgrade_case(new));self.assertEqual(new['analysis'],old['analysis'])
        self.assertIn('Saved-case conversion',reinforcement_summary_html(evaluate(new)))
        old['inputs'].update(Bar_P=6,Bar_B=11,n_P1=4,n_B1=8)
        new=upgrade_case(old)
        actual=4*.44+new['inputs']['n_B1']*1.56
        self.assertGreaterEqual(actual,8*1.56)
        self.assertLess(actual,9*1.56)

    def test_minimum_cannot_be_waived_and_large_aggregate_controls(self):
        c=case();c['screening']['minimum_clear_in']=0;c['screening']['aggregate_in']=.5
        e=evaluate(c)
        self.assertAlmostEqual(required_clear(e,1.41),2.115)
        self.assertEqual(required_clear(e,.5),1.5)
        c['screening']['aggregate_in']=2
        self.assertEqual(required_clear(evaluate(c),.5),3)
        self.assertEqual(required_clear(e,1.41,multilayer=True),1.41)

    def test_exact_horizontal_boundary_and_overlap_failures(self):
        c=case(n_N1=2,Bar_N1=8,Manual_spacing=True,SP_detail_N=2.5)
        c['screening']['minimum_clear_in']=0
        e=evaluate(c);r=next(r for r in spacing_records(e,'P',bar_positions(e,'P')) if r['label']=='Top row 1')
        self.assertEqual(r['actual'],1.5);self.assertEqual(r['status'],'PASS')
        c=set_inputs(c,SP_detail_N=2.499)
        r=next(r for r in spacing_records(evaluate(c),'P',bar_positions(evaluate(c),'P')) if r['label']=='Top row 1')
        self.assertEqual(r['status'],'FAIL')
        clash=evaluate(set_inputs(c,SP_detail_N=0))
        self.assertTrue(any('clear spacing' in issue for issue in clash.issues))
        self.assertFalse(clash.eligible)

    def test_layer_distance_is_vertical_and_alignment_is_independent(self):
        e=evaluate(case(n_N2=7,Bar_N2=11,s_row=2))
        self.assertEqual(check(e,'Chk_alignment_P').status,'FAIL')
        r=next(r for r in spacing_records(e,'P',bar_positions(e,'P')) if r['label']=='Top row 1 / Top row 2')
        self.assertAlmostEqual(r['actual'],2-(1+1.41)/2)
        self.assertEqual(r['status'],'FAIL')

    def test_hooks_have_real_bends_tails_and_pile_setback(self):
        e=evaluate(case());paths=hook_paths(e,bar_positions(e,'B'))
        self.assertEqual(len(paths),12)
        t=paths[0]
        self.assertEqual(t['inside_diameter'],6);self.assertEqual(t['tail'],12)
        self.assertEqual(t['radius'],3.5)
        self.assertAlmostEqual(t['left']-e.value('E_CL')-10-.5,3+1.5)
        self.assertAlmostEqual(t['top'],4.125+3.5+12)
        self.assertEqual(standard_hook(11,1.41)['inside_diameter'],8*1.41)
        self.assertEqual(check(e,'Status_hook_development').status,'PENDING')
        self.assertEqual(check(evaluate(case(h=18)),'Chk_hook_fit').status,'FAIL')
        crowded=evaluate(case(n_B1=16))
        self.assertFalse(crowded.eligible)
        self.assertEqual(check(crowded,'Chk_hook_cage').status,'FAIL')

    def test_added_hooks_in_aligned_layers_cannot_overlap_silently(self):
        e=evaluate(case(n_P2=4,n_B2=4,s_row=4))
        self.assertEqual(check(e,'Chk_hook_pairs').status,'FAIL')
        self.assertFalse(e.eligible)

    def test_hoop_minimum_maximum_and_manual_leg_override(self):
        e=evaluate(case(s_G=1))
        self.assertEqual(check(e,'Chk_hoop_clear_G').status,'FAIL')
        e=evaluate(case(b=60,Manual_spacing=True,S_leg_detail=10))
        self.assertEqual(check(e,'Chk_drawn_hoop_legs_G').status,'FAIL')
        self.assertEqual(check(e,'Status_pile_hoops').status,'PENDING')

    def test_embedment_and_drawn_counts_follow_inputs(self):
        for embed in (0,6,18):
            e=evaluate(case(Pile_embed=embed));fig=elevation_figure(e)
            piles=[s for s in fig.layout.shapes if s.type=='rect' and s.y0==-18]
            self.assertEqual(len(piles),4);self.assertTrue(all(s.y1==embed for s in piles))
        e=evaluate(case());f=section_figure(e,'B')
        self.assertEqual(len(next(t for t in f.data if t.name.startswith('Bottom row 1')).x),4)
        self.assertEqual(len(next(t for t in f.data if t.name.startswith('Added span row 1')).x),4)
        text=' '.join(a.text for a in hoop_figure(e).layout.annotations)
        self.assertIn('7.375 in clear',text);self.assertIn('41.375',text)

    def test_inputs_search_and_aggregate_invalidation(self):
        app=CapNotebook(case())
        try:
            self.assertIn('ADDITIONAL',LABELS['n_B1']);self.assertIn(0,app.search_lists['span_counts'].options)
            self.assertIn('4 continuous #8 + 4 added #8',app.cage.children[0].value)
            config=SearchConfig(main_bars=(8,),top_counts=(8,),pile_bars=(8,),pile_counts=(4,),span_bars=(8,),span_counts=(0,4,16),hoop_bars=(5,),hoop_spacings=(8,),skin_bars=(5,),skin_counts=(7,))
            result=search(app.case,config)
            self.assertEqual([c.changes['n_B1'] for c in result.candidates],[4])
            app.search_result=result;app.aggregate.value=1
            self.assertIsNone(app.search_result)
        finally:app.close()

    def test_elevation_hoop_sample_uses_pitch_without_claiming_full_stationing(self):
        e=evaluate(case(Bar_v=6,s_G=9,s_L=12))
        f=elevation_figure(e)
        trace=next(t for t in f.data if t.name.startswith('Hoop sample:'))
        stations=list(trace.x[::3])
        self.assertGreaterEqual(len(stations),2)
        self.assertTrue(all(abs((b-a)*12-9)<1e-8 for a,b in zip(stations,stations[1:])))
        self.assertGreater(stations[0]*12,e.value('E_CL')+10)
        self.assertLess(stations[-1]*12,e.value('E_CL')+60-10)
        self.assertEqual(trace.line.dash,'dash')
        self.assertIn('Illustrative position',trace.hovertemplate)
        self.assertIn('SIDE ELEVATION',f.layout.title.text)
        self.assertEqual(check(e,'Status_pile_hoops').status,'PENDING')

    def test_identical_hoop_checks_share_sample_but_different_checks_do_not(self):
        e=evaluate(case(Bar_v=6,s_G=9,s_L=9,Vu_G=218.27,Vu_L=218.27))
        f=hoop_figure(e)
        text=' '.join(a.text for a in f.layout.annotations)
        self.assertIn('#6 @ 9 in c/c',text)
        self.assertIn('8.250 in clear',text)
        self.assertIn('same inputs',text)
        self.assertEqual(f.layout.yaxis2.scaleanchor,'x2')
        self.assertIn('#6 @ 9 in c/c',f.data[0].hovertemplate)
        self.assertIn('<extra></extra>',f.data[0].hovertemplate)
        help=hoop_explanation_html(e)
        self.assertIn('Both shear inputs are identical',help)
        self.assertIn('Create starting layout',help)
        self.assertIn('has not enabled its actual transverse layout',help)
        for changes in ({'Vu_L':100},{'s_L':12}):
            different=hoop_figure(evaluate(set_inputs(e.case,**changes)))
            self.assertEqual(different.layout.yaxis3.scaleanchor,'x3')
            self.assertNotIn('same inputs',' '.join(a.text for a in different.layout.annotations))

    def test_scalar_and_unit_results_and_aggregate_validation(self):
        c=case(Bar_P=9,Bar_B=7);a=evaluate(c);b=evaluate(c,fast=True)
        self.assertAlmostEqual(a.max_dc,b.max_dc);self.assertAlmostEqual(a.value('Mr_B'),b.value('Mr_B'))
        for value in (0,-1,True,float('nan')):
            bad=deepcopy(c);bad['screening']['aggregate_in']=value
            with self.assertRaises(ValueError):evaluate(bad)


if __name__=='__main__':unittest.main()
