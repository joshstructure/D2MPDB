"""Verify displayed arithmetic against calculated values, including edited cases."""
from copy import deepcopy
import math
import re
import unittest

from ring_wall.equations import check_steps, number
from ring_wall.model import analyze, default_case
from ring_wall.report import check_details, render_report
from ring_wall.views import checks_table


def displayed_arithmetic(text):
    """Evaluate only the generated numeric substitutions, not the formula names."""
    expression=text.removeprefix('governing segment: ').split(' because ')[0]
    expression=re.sub(r'\|([^|]+)\|',r'abs(\1)',expression)
    expression=re.sub(r'(sin|cos)\(([-\d.]+)°\)',r'\1(radians(\2))',expression)
    expression=re.sub(r'√([\d.]+)',r'sqrt(\1)',expression).replace('√[','sqrt(')
    for old,new in [('×','*'),('−','-'),('π','pi'),('²','**2'),('³','**3'),('⁴','**4'),('^','**'),('[','('),(']',')')]:
        expression=expression.replace(old,new)
    return eval(expression,{'__builtins__':{}},dict(abs=abs,min=min,max=max,floor=math.floor,
                sqrt=math.sqrt,sin=math.sin,cos=math.cos,radians=math.radians,atan=math.atan,pi=math.pi))


class RingWallEquationTests(unittest.TestCase):
    def test_every_displayed_scalar_substitution_matches_the_calculated_result(self):
        cases=[default_case()]
        manual=default_case();manual.update(grid_bar=9,auto_grid_spacing=False,grid_spacing_in=7.,
            coating='epoxy',ring_t_in=1.,arch_panels=8,density_kcf=.175,additional_service_ksf=.03)
        cases.append(manual)
        original=default_case();original.update(support_model='ring_centers',ring_count=4,ring_spacing_in=40.,
            pile_count=3,primary_bars_per_face=2,hanger_bars_per_face=3,primary_bar=6)
        cases.append(original)
        for case in cases:
            r=analyze(case)
            for check in r['checks']:
                steps=check_steps(r,check)
                self.assertEqual([a['value'] for a in steps[-2:]],[check['demand'],check['capacity']])
                for item in steps:
                    with self.subTest(check=check['id'],step=item['label'],model=case['support_model']):
                        self.assertTrue(item['formula']);self.assertTrue(item['unit'])
                        if isinstance(item['value'],list):continue  # Angle-vector display; scalar minimum is checked below.
                        value=displayed_arithmetic(item['substitution'])
                        self.assertAlmostEqual(value,item['value'],delta=max(1e-6,abs(item['value'])*1e-6))

    def test_notebook_and_report_include_the_same_complete_derivations(self):
        r=analyze();original=deepcopy(r)
        notebook=checks_table(r);report=render_report(r)
        for check in r['checks']:
            details=check_details(r,check)
            self.assertIn(details,notebook);self.assertIn(details,report)
            self.assertIn('check-formula',details);self.assertIn('check-values',details)
        self.assertEqual(r,original)
        self.assertIn('0.003 × 36 × 12 / 2',notebook)
        self.assertIn('0.648 in²/ft',notebook)
        self.assertIn('m_root = q_max',notebook)

    def test_negative_dimensions_and_strict_angle_threshold_are_explicit(self):
        r=analyze();checks={a['id']:a for a in r['checks']}
        details=check_details(r,checks['RING-GRID'])
        self.assertIn('− 2 × 0.625',details)
        self.assertIn('-0.75 in',details)
        self.assertIn('D/C is undefined',details)
        self.assertIn('25.000001 deg',check_details(r,checks['R1-ANGLE']))
        self.assertEqual(number(1e-6),'1e-06')
        checks['RING-GRID']['note']='<script>not markup</script>'
        self.assertNotIn('<script>',check_details(r,checks['RING-GRID']))

    def test_recalculated_values_replace_previous_substitutions(self):
        p=default_case();p['density_kcf']=.3;p['ring_t_in']=1.
        r=analyze(p);checks={a['id']:a for a in r['checks']}
        steps=check_steps(r,checks['R2-P2-PLATE'])
        self.assertIn('0.3 × (36/12)',steps[1]['substitution'])
        self.assertEqual(steps[-1]['substitution'],'0.9 × 50 × 1²/6')
        self.assertAlmostEqual(displayed_arithmetic(steps[-2]['substitution']),checks['R2-P2-PLATE']['demand'],places=7)
        with self.assertRaises(ValueError):check_steps(r,dict(checks['GRID-A'],id='UNIMPLEMENTED'))


if __name__=='__main__':unittest.main()
