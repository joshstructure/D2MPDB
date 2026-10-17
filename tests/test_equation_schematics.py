"""Every report equation and check disclosure has an offline, current sketch."""
import re
from copy import deepcopy
import unittest
from lxml import etree,html

from pier_cap.model import evaluate,set_inputs
from pier_cap.calculation_report import Report,BY_NAME
from pier_cap.check_working import details_html
from pier_cap.equation_schematics import schematic_html
from tests.case_fixtures import default_case


class EquationSchematicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.e=evaluate(default_case())

    def test_every_published_equation_and_check_has_accessible_valid_svg(self):
        before=deepcopy(self.e.case)
        report=Report(self.e)
        content=[report.equation(d) for d in BY_NAME.values()]
        content += [details_html(self.e,c) for c in self.e.checks]
        for markup in filter(None,content):
            doc=html.fromstring(markup)
            self.assertTrue(doc.xpath('.//details//svg') or doc.xpath('./div//svg'))
            for svg in re.findall(r'<svg\b.*?</svg>',markup,re.S):
                root=etree.fromstring(svg.encode())
                self.assertEqual(root.get('role'),'img')
                self.assertTrue(root.get('aria-label'))
                self.assertFalse(root.xpath('.//@href'))
        self.assertEqual(before,self.e.case)

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


if __name__=='__main__':unittest.main()
