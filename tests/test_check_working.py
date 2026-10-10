"""Per-row working must follow current operands and the governing location."""
from copy import deepcopy
import unittest
from lxml import etree, html

from pier_cap.check_working import details_html, _actual
from pier_cap.model import evaluate, set_inputs
from pier_cap.transverse_zones import starting_zone_detail
from pier_cap.visuals import checks_html
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


def find(e, key):
    return next(c for c in e.checks if c.key == key)


class CheckWorkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = evaluate(default_case())
        case = deepcopy(cls.base.case)
        case['transverse_detail'] = starting_zone_detail(cls.base, 5, 8)
        cls.actual = evaluate(case)

    def test_every_check_closed_and_rendering_preserves_results(self):
        for e in (self.base, self.actual):
            before = [(c.key, c.ratio, c.status) for c in e.checks]
            doc = html.fromstring(checks_html(e))
            details = doc.xpath('//details')
            self.assertEqual([d.get('data-check') for d in details], [c.key for c in e.checks])
            self.assertFalse(doc.xpath('//details[@open]'))
            self.assertEqual(len(doc.xpath('//table')), 1)
            for d, c in zip(details, e.checks):
                self.assertEqual(d.xpath('./summary')[0].text_content(), 'Equation & values')
                self.assertIn(c.status, d.text_content())
                self.assertIn('Result:', d.text_content())
                self.assertTrue(d.xpath('.//math') or 'ratio =' in d.text_content() or 'Required:' in d.text_content(), c.key)
            for node in doc.xpath('//math'):
                etree.fromstring(etree.tostring(node))
            self.assertEqual(before, [(c.key, c.ratio, c.status) for c in e.checks])

    def test_flexure_discloses_demand_capacity_equation_and_current_variables(self):
        for moment, width in ((123.456, 48), (200.25, 54)):
            e = evaluate(set_inputs(default_case(), Mu_N=moment, b=width))
            c = find(e, 'Chk_flex_N')
            text = html.fromstring(details_html(e, c)).text_content()
            self.assertIn(f'{moment:.6g} kip-ft', text)
            self.assertIn(f'{e.value("Mr_N", "kip*ft"):.6g} kip-ft', text)
            self.assertIn(f'{c.ratio:.6g}', text)
            self.assertIn('Variable values', text)
            for value in ('required moment Mu', 'calculated resistance Mr', 'φ', 'Current substitution'):
                self.assertIn(value, text)

    def test_pending_invalid_and_coordinate_overrides_are_truthful(self):
        for key in ('Status_III', 'Status_fatigue'):
            text = html.fromstring(details_html(self.base, find(self.base, key))).text_content()
            self.assertIn('Values and demand are unavailable', text)
            self.assertNotIn('Current substitution', text)
        e = evaluate(set_inputs(default_case(), MI_N=5000))
        text = html.fromstring(details_html(e, find(e, 'Chk_I_N'))).text_content()
        self.assertIn('INVALID', text)
        self.assertIn('Invalid limit', text)
        text = html.fromstring(details_html(self.actual, find(self.actual, 'Chk_I_B'))).text_content()
        self.assertIn('Current drawn coordinates supply', text)
        source = html.fromstring(details_html(e, find(e, 'Status_layout'))).text_content()
        self.assertIn('current', source)
        self.assertIn('imported', source)

    def test_actual_shear_uses_matching_governing_demand_and_capacity(self):
        e = self.actual
        for c in e.checks:
            if not c.key.startswith(('Chk_actual_shear_', 'Chk_shear_')) or c.ratio == 'N/A':
                continue
            equation, operands = _actual(e, c)
            values = {name: value for name, value, unit in operands}
            dc = max(values['demand Vu']/max(values['resistance Vr'], 1e-9),
                     values['effective demand Veff']/values['φv']/values['Vn,limit = 0.25 fc b dv'])
            self.assertAlmostEqual(c.ratio, dc, msg=c.key)
            self.assertIn('ΣAv', equation)
            self.assertIn('Governing segment', values)
            text = html.fromstring(details_html(e, c)).text_content()
            self.assertNotIn('DCshear', text)
            self.assertIn(c.status, text)

    def test_minimum_steel_and_torsion_keep_their_own_governing_segments(self):
        e = self.actual
        for c in e.checks:
            if c.key.startswith('Chk_actual_min_'):
                values = {name: value for name, value, unit in _actual(e, c)[1]}
                self.assertAlmostEqual(c.ratio, values['required minimum rate']/max(values['intersected rate'], 1e-9))
        # Force different torsion and shear winners in an isolated presentation
        # fixture. A dropdown must not borrow the shear winner's torque or steel.
        e = deepcopy(e)
        row = e.lrfd['intervals'][0]
        row['tor_ratio'] = 1000
        row['torsion_required'] = True
        row['torsion_segment'] = dict(row['torsion_segment'], id='TORSION WINNER', tu=123.75,
                                     effective_rate=.001, closed=True, combined_required_rate=1.0)
        c = find(e, 'Status_actual_torsion')
        values = {name: value for name, value, unit in _actual(e, c)[1]}
        self.assertEqual(values['Governing segment'], 'TORSION WINNER')
        self.assertEqual(values['torque demand'], 123.75)
        self.assertEqual(values['provided rate'], .001)

    def test_clearance_keeps_raw_gap_and_demand_even_when_overlap_fails(self):
        e = evaluate(set_inputs(default_case(), Manual_spacing=True, SP_detail_N=.1))
        c = next(c for c in e.checks if c.working and 'actual clear gap' in dict((n, v) for n, v, u in c.working[1])
                 and dict((n, v) for n, v, u in c.working[1])['actual clear gap'] < 0)
        text = html.fromstring(details_html(e, c)).text_content()
        self.assertIn('FAIL', text)
        self.assertIn('contact / overlap fails', text)
        self.assertIn('required clear gap', text)
        self.assertIn('0.000001 in', text)

    def test_anchorage_working_includes_non_numeric_failure_gates(self):
        e = self.actual
        for c in e.checks:
            if not c.key.startswith('Status_transverse_development_'):
                continue
            values = {name: value for name, value, unit in _actual(e, c)[1]}
            expected = max(values['required bend']/values['actual bend'], values['closure ratio'],
                           values['required embedment']/max(values['available embedment'], 1e-9),
                           values['engagement flag'], values['unsupported-end flag'], values['shape flag'])
            self.assertAlmostEqual(c.ratio, expected)

    def test_live_widget_replaces_operands_after_edit(self):
        app = CapNotebook(default_case())
        self.addCleanup(app.close)
        before = app.register
        app.controls['Mu_N'].value = 123.456
        self.assertIs(app.register, before)
        doc = html.fromstring(app.register.value)
        detail = doc.xpath('//details[@data-check="Chk_flex_N"]')[0]
        self.assertIn('123.456 kip-ft', detail.text_content())
        self.assertFalse(doc.xpath('//details[@open]'))


if __name__ == '__main__':
    unittest.main()
