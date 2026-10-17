"""Every report equation and check disclosure has an offline, current sketch."""
import re
from copy import deepcopy
import unittest
from lxml import etree,html

from pier_cap.model import evaluate,set_inputs
from pier_cap.calculation_report import Report,BY_NAME
from pier_cap.check_working import details_html
from pier_cap.equation_schematics import family,schematic_html
from tests.case_fixtures import default_case


class EquationSchematicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.e=evaluate(default_case())

    def test_every_published_equation_and_check_has_accessible_valid_svg(self):
        for e in (self.e,evaluate(set_inputs(default_case(),n_B1=2,Ready_pile=True))):
            before=deepcopy(e.case)
            report=Report(e)
            content=[report.equation(d) for d in BY_NAME.values()]
            content += [details_html(e,c) for c in e.checks]
            for markup in filter(None,content):
                doc=html.fromstring(markup)
                self.assertTrue(doc.xpath('.//details//svg') or doc.xpath('./div//svg'))
                for svg in re.findall(r'<svg\b.*?</svg>',markup,re.S):
                    root=etree.fromstring(svg.encode())
                    self.assertEqual(root.get('role'),'img')
                    self.assertTrue(root.get('aria-label'))
                    self.assertFalse(root.xpath('.//@href'))
            self.assertEqual(before,e.case)

    def test_sketch_updates_operands_and_keeps_pending_loads_unadopted(self):
        a=schematic_html(self.e,'Mn_N')
        e=evaluate(set_inputs(default_case(),b=54,h=48,Ready_III=False,MIII_N=9999))
        b=schematic_html(e,'Mn_N')
        self.assertNotEqual(a,b)
        self.assertIn(f'{e.value("Mn_N","kip*ft"):.5g}',html.fromstring(b).text_content())
        pending=Report(e).equation(BY_NAME['fo_III_N'])
        self.assertIn('PENDING',pending)
        self.assertNotIn('9999',pending)
        self.assertNotIn('Numeric substitution',pending)

    def test_concepts_distinguish_gross_cracking_strength_and_detailing(self):
        for key,kind in [('Mcr','gross'),('Mn_N','flexure'),('Icr_B','cracked'),('SI_P','spacing'),
                         ('FTH_N','fatigue'),('Vc','shear'),('Tcr','torsion'),('y_N1','section'),
                         ('V_cap','quantity'),('Status_continuous_anchorage','development')]:
            doc=html.fromstring(schematic_html(self.e,key,pending=key=='FTH_N'))
            self.assertEqual(doc.get('data-concept'),kind)
        malicious=schematic_html(self.e,'<script>alert(1)</script>',caption='<img src=x onerror=alert(1)>')
        self.assertFalse(html.fromstring(malicious).xpath('.//script | .//img'))

    def test_family_routing(self):
        for key,kind in [('beta_1','flexure'),('alpha_1','flexure'),('P_pitch_left','spacing'),('P_center_gap','spacing'),
                         ('Pile_left','spacing'),('SP_P_auto','spacing'),('tstress','gross'),('K_limit','gross'),
                         ('As_skin_eff','longitudinal'),('SP_skin','face'),('Sw_G','legs'),('S_leg','legs'),
                         ('Chk_drawn_hoop_legs_G','legs'),('Chk_actual_end','shear'),('Vs_G','shear'),('Vc','shear'),
                         ('Chk_hook_fit','development'),('Mcr','gross'),('Mn_N','flexure'),('Icr_B','cracked'),
                         ('SI_P','spacing'),('FTH_N','fatigue'),('Tcr','torsion'),('y_N1','section'),
                         ('V_cap','quantity'),('Status_continuous_anchorage','development'),('Chk_geometry','gate')]:
            self.assertEqual(family(key),kind,key)

    def test_sketches_label_their_parameters(self):
        for name,labels in [('L_cap',('D_pile','E_CL','E_end = E_clear + Tol_pile + E_detail')),
                            ('y_N2',('s_row','y1 = cover + hoop')),('d_P',('dc',)),('a_B',('C = α1 fc a b',)),
                            ('c_N',('c = a / β1',)),('Icr_B',('n As (transformed)','fc')),('fs_I_P',('fs = M n / Ss',)),
                            ('Mcr',('yt = h/2; Ig = b h³/12',)),('P_center_gap',('P_center_gap','P_split')),
                            ('Sw_G',('S_leg','Sw')),('Tcr',('Ag = b h',)),('Aoh',('x_h','y_h')),('F_long_N',('dv',)),
                            ('As_skin_P',('d/2',)),('Ash_hoop',('Rate per face',)),('V_cap',('h',)),
                            ('Chk_alignment_P',('align vertically',)),('Chk_hook_fit',('hook height','Inside bend 6db'))]:
            text=html.fromstring(schematic_html(self.e,name)).text_content()
            for label in labels:self.assertIn(label,text,name)

    def test_check_components_feed_the_sketch(self):
        check=[c for c in self.e.checks if c.key=='Chk_min_N'][0]
        self.assertTrue(check.components)
        self.assertIn('Cracking-moment criterion · actual',html.fromstring(details_html(self.e,check)).text_content())
        e=evaluate(set_inputs(default_case(),n_B1=2))
        hook=[c for c in e.checks if c.key=='Chk_hook_fit'][0]
        self.assertIn('Hook height / available height · limit',html.fromstring(details_html(e,hook)).text_content())

    def test_eight_operand_rows(self):
        text=html.fromstring(schematic_html(self.e,'dc_N')).text_content()
        self.assertIn('n_N3',text)
        self.assertIn('Bar_N3',text)


if __name__=='__main__':unittest.main()
