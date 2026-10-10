"""Bundled checks disclose their current controlling operands on every surface."""
import csv
import tempfile
import unittest
from unittest.mock import patch
from lxml import html

from pier_cap.model import evaluate,set_inputs
from pier_cap.check_details import service_hover
from pier_cap.steel_feedback import feedback
from pier_cap.visuals import ratios_figure,results_figure,checks_html
from pier_cap.calculation_report import calculation_report
from pier_cap.io import export_bundle
from pier_cap.optimizer import search,SearchConfig,candidate_governing
from pier_cap.transverse_zones import starting_zone_detail
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


def find(e,key):return next(c for c in e.checks if c.key==key)


class CheckDetailsTests(unittest.TestCase):
    def test_service_stress_spacing_and_exact_tie(self):
        base=default_case();e=evaluate(base)
        c=find(e,'Chk_I_N');stress=e.value('fs_I_N')/e.value('fs_I_limit')
        self.assertEqual(c.governing,'Steel stress');self.assertAlmostEqual(c.ratio,stress)
        self.assertEqual([p.label for p in c.components],['Steel stress','Bar spacing'])
        self.assertIn('ksi',c.basis);self.assertIn('in =',c.basis)
        spaced=evaluate(set_inputs(base,Manual_spacing=True,SP_detail_N=30))
        c=find(spaced,'Chk_I_N')
        self.assertEqual(c.governing,'Bar spacing')
        self.assertAlmostEqual(c.ratio,30/spaced.value('SI_N'))
        tie=evaluate(set_inputs(base,Manual_spacing=True,SP_detail_N=stress*e.value('SI_N')))
        self.assertEqual(find(tie,'Chk_I_N').governing,'Steel stress + Bar spacing (tie)')

    def test_decomposition_matches_existing_ratios_without_changing_results(self):
        cases=[default_case(),set_inputs(default_case(),Vu_G=3000,Tu=800,s_G=24),
            set_inputs(default_case(),Ready_III=True,Ready_fatigue=True,MIII_N=150,MIII_P=120,MIII_B=300,
                       MDL_N=100,MDL_P=70,MDL_B=200,DMLL_N=20,DMLL_P=30,DMLL_B=40),
            set_inputs(default_case(),n_B1=3)]
        actual=default_case();actual['transverse_detail']=starting_zone_detail(evaluate(actual),5,8);cases.append(actual)
        for case in cases:
            e=evaluate(case);fast=evaluate(case,fast=True)
            with patch('pier_cap.check_details.annotate_checks',side_effect=lambda e:e):plain=evaluate(case)
            self.assertEqual([(c.key,c.ratio,c.status) for c in e.checks],[(c.key,c.ratio,c.status) for c in plain.checks])
            self.assertEqual(e.eligible,plain.eligible);self.assertEqual(e.max_dc,plain.max_dc)
            for c in e.checks:
                if c.components and isinstance(c.ratio,(int,float)):
                    expected=(min if c.component_rule=='min' else max)(v.ratio for v in c.components)
                    self.assertAlmostEqual(c.ratio,expected,msg=c.key)
                    other=find(fast,c.key)
                    self.assertEqual(c.governing,other.governing)
                    for a,b in zip(c.components,other.components):
                        self.assertAlmostEqual(a.actual,b.actual);self.assertAlmostEqual(a.limit,b.limit)
        for key in ('Chk_shear_G','Chk_spacing_G','Chk_torsteel_G','Chk_min_N','Chk_skin_area',
                    'Chk_skin_space','Chk_shrink_area','Chk_shrink_space'):
            self.assertTrue(find(evaluate(default_case()),key).components,key)

    def test_pending_reference_invalid_and_applicability_are_not_hidden(self):
        base=evaluate(default_case())
        for key in ('Status_III','Status_fatigue'):
            self.assertFalse(find(base,key).components);self.assertFalse(find(base,key).governing)
        invalid=evaluate(set_inputs(default_case(),MI_N=5000,Ready_III=True,MIII_B=5000,
                                    Ready_fatigue=True,MDL_B=4000,DMLL_B=1))
        for key in ('Chk_I_N','Status_III','Status_fatigue'):
            check=find(invalid,key)
            self.assertEqual(check.ratio,'INVALID');self.assertIn('Invalid limit:',check.governing)
        self.assertIn('INVALID',service_hover(invalid,'N'))
        high_grade=evaluate(set_inputs(default_case(),fy=75))
        self.assertIn('Applicability gate FAIL',find(high_grade,'Chk_I_N').basis)
        actual=default_case();actual['transverse_detail']=starting_zone_detail(base,5,8)
        calculated=find(evaluate(actual),'Chk_spacing_G')
        self.assertIsInstance(calculated.ratio,(int,float))
        self.assertNotEqual(calculated.status,'REFERENCE')

    def test_html_plot_report_and_csv_share_current_details(self):
        case=set_inputs(default_case(),Manual_spacing=True,SP_detail_N=30);e=evaluate(case)
        c=find(e,'Chk_I_N');figure=ratios_figure(e)
        index=list(figure.data[0].y).index(c.label);tip=figure.data[0].customdata[index][0]
        for text in ('Controls: Bar spacing','Steel stress:','Bar spacing:','<br>'):
            self.assertIn(text,tip)
        self.assertIn('Controls: Bar spacing',checks_html(e))
        self.assertIn('Controls: Bar spacing',feedback(e)['top'])
        self.assertIn('Controls: Bar spacing',calculation_report(case,evaluation=e))
        for actual in (False,True):
            if actual:case['transverse_detail']=starting_zone_detail(e,5,8)
            current=evaluate(case);stress=next(t for t in results_figure(current).data if t.name=='Service I stress')
            self.assertIn('Steel stress:',stress.customdata[0]);self.assertIn('Bar spacing:',stress.customdata[0])
        with tempfile.TemporaryDirectory() as folder:
            root=export_bundle(case,folder)
            with (root/'checks.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            self.assertTrue(any('Controls:' in str(r) and 'Steel stress:' in str(r) for r in rows))

    def test_drawn_spacing_winner_retains_stress_comparison(self):
        case=set_inputs(default_case(),n_B1=2,Manual_spacing=True,SP_detail_B=1,SP_detail_P=30)
        e=evaluate(case);drawn=find(e,'Chk_drawn_I_B');section=find(e,'Chk_I_B')
        self.assertGreater(drawn.ratio,section.ratio)
        markup=feedback(e)['added'];doc=html.fromstring(markup)
        tip=next(v for v in doc.xpath('//@title') if 'Compared readouts' in v and 'Service I' in v)
        self.assertIn('Steel stress:',tip);self.assertIn('Bar spacing:',tip)
        self.assertIn('Actual drawn bar spacing',markup)

    def test_live_edits_replace_controlling_text_in_place(self):
        app=CapNotebook(default_case());self.addCleanup(app.close)
        app.plot_tabs.selected_index=1
        readout=app.steel_readouts['top'];plots=dict(app.views.plots)
        self.assertIn('Controls: Steel stress',readout.value)
        app.controls['Manual_spacing'].value=True;app.controls['SP_detail_N'].value=30
        self.assertIn('Controls: Bar spacing',readout.value)
        self.assertEqual(plots,app.views.plots);self.assertIs(readout,app.steel_readouts['top'])
        self.assertIn('Controls: Bar spacing',app.register.value)

    def test_candidate_hover_identifies_nested_component(self):
        result=search(default_case(),SearchConfig(main_bars=(8,),top_counts=(8,),bottom_counts=(8,),
            hoop_bars=(5,),hoop_spacings=(8,),skin_bars=(5,),skin_counts=(6,)))
        self.assertEqual(len(result.candidates),1)
        self.assertIn('Across-cap leg spacing',candidate_governing(result.candidates[0]))


if __name__=='__main__':unittest.main()
