"""The report must describe the same case, equations and gates as the calculator."""
import json
from copy import deepcopy
import unittest
from lxml import etree, html

from pier_cap.calculation_report import calculation_report, Report, BY_NAME, groups, SECTIONS
from pier_cap.engine import Engine, parse, Q
from pier_cap.math_notation import expression, mathml, quantity
from pier_cap.model import evaluate, set_inputs
from pier_cap.transverse import suggested_detail
from tests.case_fixtures import default_case


class MathNotationTests(unittest.TestCase):
    def test_grouping_fraction_exponent_and_escaped_strings(self):
        xml=etree.fromstring(mathml(expression(parse('(a-b)/(c+d)^2'))).encode())
        ns={'m':'http://www.w3.org/1998/Math/MathML'}
        self.assertEqual(len(xml.xpath('.//m:mfrac',namespaces=ns)),1)
        self.assertEqual(len(xml.xpath('.//m:msup',namespaces=ns)),1)
        self.assertEqual(''.join(xml.itertext()),'a−b(c+d)2')
        markup=mathml(expression(parse('"</math><script>alert(1)</script>"')))
        self.assertIn('&lt;script&gt;',markup)
        etree.fromstring(markup.encode())

    def test_substitution_uses_selected_branch_and_declared_units(self):
        engine=Engine([{'formula':'x = 24 in'}])
        ast=parse('If(x > 1 in,x,missing_variable)')
        markup=expression(ast,engine,{'x':{'unit':'ft'}},substitute=True)
        self.assertIn('<mn>2</mn>',markup)
        self.assertIn('ft',markup)
        self.assertNotIn('missing',markup)
        with self.assertRaises(AssertionError):quantity(Q(1,(1,0,0)),engine,'kip')


class CalculationReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case=default_case()
        cls.e=evaluate(cls.case)
        cls.markup=calculation_report(evaluation=cls.e,generated_at='TEST SNAPSHOT')
        cls.doc=html.fromstring(cls.markup)

    def test_all_sections_have_strategy_targets_and_unique_ids(self):
        ids=self.doc.xpath('//*[@id]/@id')
        self.assertEqual(len(ids),len(set(ids)))
        for index,s in enumerate(SECTIONS,1):
            section=self.doc.get_element_by_id(s[0])
            self.assertTrue(section.xpath('./summary')[0].text.startswith(f'{index}.'))
            self.assertIn(s[0],ids)
            self.assertTrue(self.doc.xpath(f'//a[@href="#{s[0]}"]'))
        self.assertEqual(sum(map(len,groups().values())),len(BY_NAME))

    def test_mathml_is_well_formed_and_every_equation_uses_evaluated_result(self):
        r=Report(self.e)
        for name,d in BY_NAME.items():
            markup=r.equation(d)
            if not markup:continue
            node=html.fromstring(markup)
            self.assertTrue(node.xpath('.//math'),name)
            if name.startswith(('fs_III_','fo_III_','SIII_','fmin_','Df_','FTH_','DC_fat_')):
                self.assertIn('PENDING',node.text_content())
                self.assertFalse(node.xpath('.//details'),name)
            else:
                self.assertIn(r.result(name),markup,name)
            # XML parse the original MathML without HTML's case normalization.
            import re
            for math in re.findall(r'<math\b.*?</math>',markup,re.S):
                etree.fromstring(math.encode())

    def test_complete_check_register_and_offline_figures(self):
        register=self.doc.get_element_by_id('register')
        rows=register.xpath('.//tbody/tr')
        self.assertEqual(len(rows),len(self.e.checks))
        for row,c in zip(rows,self.e.checks):
            self.assertIn(c.label,row.text_content())
            self.assertIn(c.status,row.text_content())
        self.assertFalse(self.doc.xpath('//script[@src]'))
        data=self.doc.xpath('//script[@type="application/json"]')
        self.assertGreaterEqual(len(data),8)
        for script in data:
            figure=json.loads(script.text)
            self.assertIn('data',figure)
            self.assertIn('layout',figure)
            reference=figure['layout']['meta']['reference']
            self.assertTrue(figure['layout']['title']['text'].startswith(reference+' — '))
            plot=self.doc.xpath(f'//div[@data-figure="{script.get("id")}"]')[0]
            self.assertTrue(plot.getparent().xpath('./figcaption')[0].text.startswith(reference+'.'))
        self.assertTrue(all(t.xpath('./caption') for t in self.doc.xpath('//table')))
        self.assertNotIn('SECTIONAL CHECKS PASS</span>',self.markup)

    def test_geometry_gallery_contains_all_views_and_navigation_targets(self):
        gallery=self.doc.get_element_by_id('geometry')
        expected=('dimensions','elevation','pile-section','span-section','reinforcement-plan','3d')
        self.assertEqual(len(gallery.xpath('.//figure')),len(expected))
        for key in expected:
            view=self.doc.get_element_by_id('geometry-'+key)
            plot=view.xpath('.//div[@class="plot"]')[0]
            figure=json.loads(self.doc.get_element_by_id(plot.get('data-figure')).text)
            self.assertTrue(figure['data'],key)
        self.assertTrue(self.doc.xpath('//nav[@class="toolbar"]/a[@href="#geometry"]'))
        for link in self.doc.xpath('//a[starts-with(@href,"#")]'):
            self.assertIsNotNone(self.doc.get_element_by_id(link.get('href')[1:]))
        self.assertIn('Pile center and face stations',gallery.text_content())
        self.assertIn('Print / save PDF includes all views',gallery.text_content())
        # One copy of each drawing, with links from its related calculation.
        self.assertFalse(self.doc.get_element_by_id('steel').xpath('.//figure'))
        self.assertTrue(self.doc.get_element_by_id('steel').xpath('.//a[@href="#geometry-3d"]'))

    def test_exported_geometry_uses_edited_case_and_retains_actual_cage(self):
        from pier_cap.geometry_dimensions import geometry_dimensions
        case=set_inputs(self.case,b=54,h=42,S_pile=6,Bar_N1=10,n_B1=2)
        case['transverse_detail']=suggested_detail(evaluate(case))
        case['transverse_detail']['enabled']=True
        before=deepcopy(case)
        e=evaluate(case)
        report=html.fromstring(calculation_report(evaluation=e))
        def figure(key):
            plot=report.get_element_by_id('geometry-'+key).xpath('.//div[@class="plot"]')[0]
            return json.loads(report.get_element_by_id(plot.get('data-figure')).text)
        dimensions={t['meta']['dimension']:t['meta']['inches'] for t in figure('dimensions')['data'] if t.get('meta')}
        self.assertAlmostEqual(dimensions['length'],geometry_dimensions(e)['length'])
        self.assertEqual(dimensions['section_width'],54)
        self.assertEqual(dimensions['section_depth'],42)
        self.assertEqual(dimensions['center_chain_1'],72)
        self.assertIn('differ from analyzed geometry',report.get_element_by_id('geometry-dimensions').text_content())
        from pier_cap.cage_3d import layout_3d
        # Export must preserve the entered schedule, coordinates and visibility controls.
        self.assertEqual(figure('3d')['data'],json.loads(layout_3d(e).to_json())['data'])
        self.assertEqual(case,before)

    def test_actual_geometry_replaces_reference_cover_equation(self):
        case=deepcopy(self.case)
        case['transverse_detail']=suggested_detail(evaluate(case))
        case['transverse_detail']['enabled']=True
        e=evaluate(case);r=Report(e)
        self.assertIn('y_N1',e.engine.overrides)
        markup=r.equation(BY_NAME['y_N1'])
        self.assertIn('actual longitudinal coordinates',markup)
        self.assertNotIn('Numeric substitution',markup)
        self.assertIn(r.result('y_N1'),markup)
        self.assertIn('Uniform-cage reference',r.equation(BY_NAME['Vr_G']))
        self.assertEqual(r.result('Chk_shear_G'),'<span class="badge reference">REFERENCE</span>')
        self.assertIn('CONDITIONAL',r.technical_content('shear'))

    def test_confirmed_service_and_edited_load_provenance(self):
        e=evaluate(set_inputs(self.case,Ready_III=True,MIII_N=20,MIII_P=25,MIII_B=40))
        r=Report(e)
        markup=r.equation(BY_NAME['fs_III_B'])
        self.assertIn('Numeric substitution',markup)
        self.assertNotIn('PENDING',markup)
        self.assertIn(r.result('fs_III_B'),markup)
        self.assertIn('No recorded governing combination',r.inputs([BY_NAME['Mu_B']]))

    def test_case_text_is_escaped_and_generation_does_not_mutate_inputs(self):
        case=deepcopy(self.case)
        case['name']='</title><script id="injected">bad()</script>'
        before=deepcopy(case)
        markup=calculation_report(case)
        self.assertEqual(case,before)
        self.assertNotIn('<script id="injected">',markup)
        self.assertIn('&lt;script id=',markup)


if __name__=='__main__':unittest.main()
