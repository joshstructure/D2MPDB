"""Pile design: hand checks, interaction curve, section classes, demands from the FBMP export, case handling.

Expected numbers are recomputed here with independent arithmetic, not by calling the package.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

import numpy as np

from pile_design import loads, model, sections, sources

ROOT = Path(__file__).resolve().parents[1]
EB_XML = ROOT / 'project_current' / 'fbmp' / 'end_bents' / 'End Bent 1_Fixed.XML'
PIER_XML = ROOT / 'project_current' / 'fbmp' / 'pier' / 'Pier_Fixed.XML'
needs_xml = unittest.skipUnless(EB_XML.exists() and PIER_XML.exists(), 'registered FBMP exports not present')


def raw_pile_forces(path):
    """(combination, limitstate, pile, element, side, axial) straight from the XML, tension positive."""
    out = []
    for lc in ET.parse(path).getroot().iter('LOAD_CASE'):
        if lc.get('combination') is None:
            continue
        for pile in lc.findall('.//PILE_INTERNAL_FORCES/PILE'):
            for el in pile.findall('ELEMENT'):
                for side in ('I', 'J'):
                    end = el.find(f'PILE_ELEMENT_{side}_END')
                    ax = float(end.find('AXIAL').text) * (1 if side == 'I' else -1)
                    out.append((lc.get('combination'), lc.get('limitstate'), pile.get('number'), int(el.get('number')), side, ax))
    return out


def pc_case(fc=6.0):
    case = model.default_case('End Bent 1')
    model.edit_input(case, 'fc', fc)
    return case


class PrestressedHandChecks(unittest.TestCase):
    """18 in pile, 12 x 0.6 in strands, losses 0.20 (spec section 5, item 3)."""

    @classmethod
    def setUpClass(cls):
        cls.e = model.evaluate(pc_case(6.0))

    def test_prestress(self):
        e = self.e
        aps = 12 * 0.217
        pe = 12 * 35 * (1 - 0.20)
        self.assertAlmostEqual(e.value('A_ps'), aps, places=9)
        self.assertAlmostEqual(aps, 2.604, places=9)
        self.assertAlmostEqual(e.value('P_e'), 336.0, places=6)
        self.assertAlmostEqual(e.value('f_pc_eff'), 336.0 / 324.0, places=9)
        self.assertAlmostEqual(e.value('f_pc_eff'), 1.0370, places=4)
        fpe = 35 / 0.217 * 0.8
        self.assertAlmostEqual(e.value('f_pe'), fpe, places=9)
        self.assertAlmostEqual(fpe, 129.03, places=2)
        self.assertAlmostEqual(pe, aps * fpe, places=9)

    def test_axial_cap(self):
        aps, fpe = 2.604, 35 / 0.217 * 0.8
        pn_max = 0.85 * (0.85 * 6.0 * (324 - aps) - aps * (fpe - 28500 * 0.003))
        self.assertAlmostEqual(pn_max, 1296.9, delta=0.05)
        self.assertAlmostEqual(self.e.value('P_n_max'), pn_max, places=6)
        self.assertAlmostEqual(self.e.value('P_r_max'), 0.75 * pn_max, places=6)
        self.assertAlmostEqual(0.75 * pn_max, 972.7, delta=0.05)
        self.assertAlmostEqual(self.e.curve['Pr'][0], 0.75 * pn_max, places=6)

    def test_concrete_constants(self):
        e = self.e
        self.assertAlmostEqual(e.value('beta_1'), 0.85 - 0.05 * 2.0, places=12)
        self.assertAlmostEqual(e.value('E_c'), 120000 * 1.0 * 0.150 ** 2 * 6.0 ** 0.33, places=6)

    def test_tension(self):
        aps, fpe = 2.604, 35 / 0.217 * 0.8
        expected = 1.0 * aps * min(243.0, fpe + 60.0)         # LRFD 5.6.6.1 with Pn from Eq. 5.8.2.4.1-1
        self.assertAlmostEqual(self.e.value('P_r_t'), expected, places=6)
        self.assertAlmostEqual(expected, 492.24, delta=0.01)
        self.assertLess(self.e.value('P_r_t'), self.e.value('P_t_yield'))

    def test_splice_value_and_pure_bending(self):
        c = self.e.curve
        # Mn where Pn crosses zero, by linear interpolation of the nominal curve
        Pr, Mr = c['Pr'], c['Mr']
        k = int(np.nonzero(Pr <= 0)[0][0])
        t = (0 - Pr[k - 1]) / (Pr[k] - Pr[k - 1])
        mr0 = Mr[k - 1] + t * (Mr[k] - Mr[k - 1])           # factored resistance where Pn crosses zero
        self.assertLess(abs(mr0 - 245.0) / 245.0, 0.15, mr0)
        self.assertLess(abs(self.e.value('M_r_P0') - 245.0) / 245.0, 0.15)
        self.assertEqual(self.e.value('M_splice'), 245.0)


class PrestressedDefault(unittest.TestCase):
    @needs_xml
    def test_default_fc_is_xml_value_and_prestress_unchanged(self):
        e = model.evaluate(model.default_case('End Bent 1'))
        self.assertEqual(e.case['inputs']['fc'], 6.5)
        self.assertAlmostEqual(e.value('P_e'), 336.0, places=6)
        aps, fpe = 2.604, 35 / 0.217 * 0.8
        expected = 0.85 * (0.85 * 6.5 * (324 - aps) - aps * (fpe - 85.5))
        self.assertAlmostEqual(e.value('P_n_max'), expected, places=6)
        self.assertAlmostEqual(e.value('beta_1'), 0.85 - 0.05 * 2.5, places=12)


class InteractionCurve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lay = sections.strand_layout(18.0, 12, 3.5)
        cls.fpe = 35 / 0.217 * 0.8
        cls.sec = sections.psc_section(18.0, lay, 6.0, cls.fpe, Aps_each=0.217)
        cls.curve = sections.psc_interaction(cls.sec)

    def test_end_points_and_monotonic(self):
        c = self.curve
        self.assertAlmostEqual(c['Pr'][0], 0.75 * c['Pn_max'], places=9)
        self.assertEqual(c['Mr'][0], 0.0)
        self.assertAlmostEqual(c['Pn'][-1], -2.604 * 243.0, places=6)
        self.assertEqual(c['Mr'][-1], 0.0)
        self.assertTrue(np.all(np.diff(c['Pn']) <= 1e-9))
        self.assertTrue(np.all(np.diff(c['Pr']) <= 1e-6))
        self.assertTrue(np.all(c['Pn'] <= c['Pn_max'] + 1e-9))
        self.assertGreater(c['Mr'].max(), 250.0)

    def test_phi_transitions(self):
        c = self.curve
        self.assertEqual(c['phi'][0], 0.75)
        self.assertEqual(c['phi'][-1], 1.0)
        self.assertTrue(np.all(np.diff(c['phi']) >= -1e-12))
        mid = c['phi'][(c['eps_t'] > 0.002) & (c['eps_t'] < 0.005)]
        self.assertTrue(len(mid) and mid.min() > 0.75 and mid.max() < 1.0)
        for et, ph in zip(c['eps_t'][1:-1], c['phi'][1:-1]):
            self.assertAlmostEqual(ph, min(1.0, max(0.75, 0.75 + 0.25 * (et - 0.002) / 0.003)), places=12)

    def test_pure_bending_near_splice_value(self):
        c = self.curve
        mr0 = sections.moment_capacity_at_axial(c, 0.0)
        self.assertLess(abs(mr0 - 245.0) / 245.0, 0.15, mr0)

    def test_capacity_at_eccentricity_is_on_curve(self):
        c = self.curve
        for e_in in (0.5, 3.0, 8.0, 20.0, 60.0):
            P, M = sections.capacity_at_eccentricity(c, e_in)
            self.assertAlmostEqual(M, P * e_in / 12.0, places=7)
            on = False
            for i in range(len(c['Pr']) - 1):
                p0, m0, p1, m1 = c['Pr'][i], c['Mr'][i], c['Pr'][i + 1], c['Mr'][i + 1]
                cross = (p1 - p0) * (M - m0) - (m1 - m0) * (P - p0)
                if abs(cross) < 1e-6 and min(p0, p1) - 1e-9 <= P <= max(p0, p1) + 1e-9:
                    on = True
                    break
            self.assertTrue(on, e_in)
        P0, M0 = sections.capacity_at_eccentricity(c, 0.0)
        self.assertAlmostEqual(P0, c['Pr'][0], places=9)
        self.assertEqual(M0, 0.0)

    def test_diagonal_axis_and_symmetry(self):
        quarter = sections.psc_interaction(self.sec, angle=math.pi / 2)
        for key in ('Pn', 'Mn'):
            np.testing.assert_allclose(quarter[key], self.curve[key], atol=1e-6)
        diagonal = sections.psc_interaction(self.sec, angle=math.pi / 4)
        self.assertLess(sections.moment_capacity_at_axial(diagonal, 100.0), sections.moment_capacity_at_axial(self.curve, 100.0))
        np.testing.assert_allclose(sections.psc_interaction(self.sec, angle=math.pi / 4)['Mn'],
                                   sections.psc_interaction(self.sec, angle=-math.pi / 4)['Mn'], atol=1e-6)

    def test_biaxial_branch_selection(self):
        c = self.curve
        phiPo = 0.75 * self.sec['Po']
        limit = 0.10 * 0.75 * 6.0 * 324
        above = sections.psc_biaxial_dc(c, 200.0, 40.0, 30.0, phiPo, limit)
        below = sections.psc_biaxial_dc(c, 100.0, 40.0, 30.0, phiPo, limit)
        self.assertEqual(above['method'], '5.6.4.5-1')
        self.assertEqual(below['method'], '5.6.4.5-3')
        prx, _ = sections.capacity_at_eccentricity(c, 40.0 * 12 / 200.0)
        pry, _ = sections.capacity_at_eccentricity(c, 30.0 * 12 / 200.0)
        prxy = 1 / (1 / prx + 1 / pry - 1 / phiPo)
        self.assertAlmostEqual(above['Prxy'], prxy, places=9)
        self.assertAlmostEqual(above['ratio'], 200.0 / prxy, places=9)
        mr = sections.moment_capacity_at_axial(c, 0.0)                  # pure-flexure point of the phi-curve
        self.assertAlmostEqual(below['ratio'], 70.0 / mr, places=9)
        self.assertGreater(mr, sections.moment_capacity_at_axial(c, 100.0) * 0.9)
        # exactly at the limit uses Eq. 5.6.4.5-1
        self.assertEqual(sections.psc_biaxial_dc(c, limit, 10.0, 10.0, phiPo, limit)['method'], '5.6.4.5-1')

    def test_strand_layout_patterns(self):
        plans = model.STANDARD_PLANS['indexes']
        for index, plan in plans.items():
            for option in plan['options']:
                pts = sections.strand_layout(plan['size_in'], option['count'], 3.5)
                self.assertEqual(len(pts), option['count'], (index, option['id']))
                half = plan['size_in'] / 2 - 3.5
                xs = {round(abs(x), 6) for x, _ in pts} | {round(abs(y), 6) for _, y in pts}
                self.assertIn(round(half, 6), xs)
                for corner in ((half, half), (-half, half), (half, -half), (-half, -half)):
                    self.assertTrue(any(abs(x - corner[0]) < 1e-6 and abs(y - corner[1]) < 1e-6 for x, y in pts))
                self.assertAlmostEqual(sum(x for x, _ in pts), 0.0, places=6)
                self.assertAlmostEqual(sum(y for _, y in pts), 0.0, places=6)
        with self.assertRaises(ValueError):
            sections.strand_layout(18, 10, 3.5)


class PrestressedShear(unittest.TestCase):
    @needs_xml
    def test_general_procedure_independent(self):
        e = model.evaluate(model.default_case('End Bent 1'))
        Vu, Mu, Pu = e.value('V_u_sh'), e.value('M_u_sh', 'kip*ft') * 12.0, e.value('P_u_sh')
        D, fc, Ep, fpu = 18.0, 6.5, 28500.0, 270.0
        Ec = 120000 * 0.150 ** 2 * fc ** 0.33
        # tension half depth for the governing record's bending axis, from the perimeter strand grid
        a = e.details['shear']['angle']
        g = [-5.5, -5.5 / 3, 5.5 / 3, 5.5]
        pts = [(x, y) for x in g for y in g if x in (-5.5, 5.5) or y in (-5.5, 5.5)]
        self.assertEqual(len(pts), 12)
        s_all = [-math.sin(a) * x + math.cos(a) * y for x, y in pts]
        s_max = 9.0 * (abs(math.sin(a)) + abs(math.cos(a)))
        tension = [s for s in s_all if s < -1e-9]
        d_e = s_max - sum(tension) / len(tension)
        Aps_t = len(tension) * 0.217
        self.assertAlmostEqual(e.value('A_ps_t'), Aps_t, places=9)
        self.assertAlmostEqual(e.value('d_e'), d_e, places=6)
        dv = max(0.9 * d_e, 0.72 * 18.0)
        Mv = max(Mu, Vu * dv)
        num = Mv / dv + 0.5 * (-Pu) + Vu - Aps_t * 0.7 * fpu
        eps = num / (Ep * Aps_t)
        if eps < 0:
            eps = num / (Ep * Aps_t + Ec * 18 * 18 / 2)
        eps = max(eps, -0.0004)
        avmin = 0.0316 * math.sqrt(fc) * 18.0 * 6.0 / 70.0
        av = 2 * 0.034
        sxe = min(80.0, max(12.0, dv * 1.38 / (0.75 + 0.63)))
        beta = 4.8 / (1 + 750 * eps) if av >= avmin else 4.8 / (1 + 750 * eps) * 51 / (39 + sxe)
        theta = 29 + 3500 * eps
        Vc = 0.0316 * beta * math.sqrt(fc) * 18.0 * dv
        Vs = av * 70.0 * dv / math.tan(math.radians(theta)) / 6.0
        Vn = min(Vc + Vs, 0.25 * fc * 18.0 * dv)
        self.assertAlmostEqual(e.value('eps_s'), eps, places=12)
        self.assertAlmostEqual(e.value('beta_v'), beta, places=9)
        self.assertAlmostEqual(e.value('theta_v', 'deg'), theta, places=9)
        self.assertAlmostEqual(e.value('V_r'), 0.9 * Vn, places=6)
        self.assertLess(avmin, 0.2)

    def test_negative_strain_rules(self):
        kw = dict(D=18.0, bv=18.0, Aps_t=1.302, d_e=13.28, Ag=324.0, Ec=5000.0, fc=6.0, Av=0.068, s=6.0, fy=70.0, a_g=0.75)
        # huge compression: eps_s limited to -0.40E-3 even though the Ec Act term gives a smaller magnitude
        out = sections.psc_shear(Vu=5.0, Mu=0.0, Pu=2000.0, **kw)
        self.assertLess(out['eps_s0'], 0)
        self.assertGreaterEqual(out['eps_s'], -0.0004)
        # positive strain: no Ec Act term
        high = sections.psc_shear(Vu=60.0, Mu=200.0 * 12, Pu=-300.0, **kw)
        self.assertGreater(high['eps_s0'], 0)
        self.assertEqual(high['eps_s'], high['eps_s0'])
        # Av below the minimum uses Eq. 5.7.3.4.2-2
        weak = dict(kw, Av=0.01)
        a = sections.psc_shear(Vu=20.0, Mu=1200.0, Pu=100.0, **weak)
        self.assertFalse(a['Av_ok'])
        self.assertAlmostEqual(a['beta'], 4.8 / (1 + 750 * a['eps_s']) * 51 / (39 + a['sxe']), places=12)


class ServiceStress(unittest.TestCase):
    def test_corner_stress_and_limits(self):
        smax, smin = sections.psc_service_stress(100.0, 30.0, 40.0, 1.037, 324.0, 972.0)
        flex = 70.0 * 12 / 972.0
        self.assertAlmostEqual(smax, 1.037 + 100 / 324 + flex, places=12)
        self.assertAlmostEqual(smin, 1.037 + 100 / 324 - flex, places=12)
        self.assertAlmostEqual(sections.service_tension_limit(6.5, False), 0.19 * math.sqrt(6.5), places=12)
        self.assertAlmostEqual(sections.service_tension_limit(6.5, True), 0.0948 * math.sqrt(6.5), places=12)
        self.assertEqual(sections.service_tension_limit(40.0, False), 0.6)
        self.assertEqual(sections.service_tension_limit(40.0, True), 0.3)


class PipeSection(unittest.TestCase):
    def test_properties_and_classes(self):
        p = sections.pipe_section(20.0, 0.48)
        Di = 19.04
        self.assertAlmostEqual(p['A'], math.pi / 4 * (400 - Di ** 2), places=9)
        self.assertAlmostEqual(p['A'], 29.44, delta=0.01)
        self.assertAlmostEqual(p['I'], math.pi / 64 * (20 ** 4 - Di ** 4), places=6)
        self.assertAlmostEqual(p['I'], 1402.8, delta=0.5)
        self.assertAlmostEqual(p['Z'], (8000 - Di ** 3) / 6, places=9)
        self.assertAlmostEqual(p['D_t'], 41.6667, places=3)
        self.assertLess(p['D_t'], 0.11 * 29000 / 45)
        self.assertAlmostEqual(0.11 * 29000 / 45, 70.889, places=3)
        f = sections.pipe_flexure(p, 45.0, 29000.0)
        self.assertEqual(f['cls'], 'compact')
        self.assertAlmostEqual(f['Mp'], 45.0 * p['Z'] / 12.0, places=9)
        self.assertEqual(f['Mn'], f['Mp'])
        self.assertAlmostEqual(0.07 * 29000 / 45, 45.11, places=2)
        # synthetic noncompact and slender tubes
        nc = sections.pipe_section(20.0, 0.30)
        fn = sections.pipe_flexure(nc, 45.0, 29000.0)
        self.assertEqual(fn['cls'], 'noncompact')
        self.assertAlmostEqual(fn['Mn'], min(45.0 * nc['Z'] / 12, (0.021 * 29000 / nc['D_t'] + 45.0) * nc['S'] / 12), places=9)
        sl = sections.pipe_section(20.0, 0.09)
        fs = sections.pipe_flexure(sl, 45.0, 29000.0)
        self.assertEqual(fs['cls'], 'slender')
        self.assertAlmostEqual(fs['Mn'], 0.33 * 29000 / sl['D_t'] * sl['S'] / 12, places=9)
        self.assertTrue(fs['within_limit'])
        self.assertFalse(sections.pipe_flexure(sections.pipe_section(20.0, 0.05), 45.0, 29000.0)['within_limit'])

    def test_column_curve_branches(self):
        p = sections.pipe_section(20.0, 0.48)
        r = math.sqrt(p['I'] / p['A'])
        Po = 45.0 * p['A']
        short = sections.pipe_axial(p, 45.0, 29000.0, 240.0)
        Pe = math.pi ** 2 * 29000.0 * p['A'] / (240.0 / r) ** 2
        self.assertGreaterEqual(Pe / Po, 0.44)
        self.assertEqual(short['branch'], 'inelastic (0.658)')
        self.assertAlmostEqual(short['Pn'], 0.658 ** (Po / Pe) * Po, places=6)
        self.assertAlmostEqual(short['Pr_axial'], 0.70 * short['Pn'], places=9)
        self.assertAlmostEqual(short['Pr_comb'], 0.80 * short['Pn'], places=9)
        long = sections.pipe_axial(p, 45.0, 29000.0, 1200.0)        # synthetic long unsupported length
        Pe2 = math.pi ** 2 * 29000.0 * p['A'] / (1200.0 / r) ** 2
        self.assertLess(Pe2 / Po, 0.44)
        self.assertEqual(long['branch'], 'elastic (0.877 Pe)')
        self.assertAlmostEqual(long['Pn'], 0.877 * Pe2, places=6)
        self.assertFalse(short['slender'])
        slender = sections.pipe_axial(sections.pipe_section(20.0, 0.20), 45.0, 29000.0, 240.0)
        self.assertTrue(slender['slender'])
        thin = sections.pipe_section(20.0, 0.20)
        self.assertAlmostEqual(slender['Aeff'], (0.038 * 29000 / (45 * 100.0) + 2 / 3) * thin['A'], places=9)

    def test_interaction_equation_branches(self):
        low = sections.pipe_interaction_dc(100.0, 1000.0, 200.0, 700.0)
        self.assertEqual(low['branch'], '6.9.2.2.1-2')
        self.assertAlmostEqual(low['ratio'], 100 / 2000 + 200 / 700, places=12)
        high = sections.pipe_interaction_dc(500.0, 1000.0, 200.0, 700.0)
        self.assertEqual(high['branch'], '6.9.2.2.1-1')
        self.assertAlmostEqual(high['ratio'], 0.5 + 8 / 9 * 200 / 700, places=12)
        edge = sections.pipe_interaction_dc(200.0, 1000.0, 200.0, 700.0)       # exactly 0.2 uses Eq. -1
        self.assertEqual(edge['branch'], '6.9.2.2.1-1')

    def test_shear_tension_and_fixity(self):
        p = sections.pipe_section(20.0, 0.48)
        s = sections.pipe_shear(p, 45.0, 29000.0, 15.0 * 12)
        f1 = 1.60 * 29000 / (math.sqrt(180 / 20) * (20 / 0.48) ** 1.25)
        f2 = 0.78 * 29000 / (20 / 0.48) ** 1.5
        self.assertAlmostEqual(s['Fcr'], min(max(f1, f2), 0.58 * 45), places=9)
        self.assertAlmostEqual(s['Vn'], 0.5 * s['Fcr'] * p['A'], places=9)
        self.assertAlmostEqual(sections.pipe_tension(45.0, p['A']), 0.95 * 45 * p['A'], places=9)
        Iw = p['I'] / 12 ** 4
        self.assertAlmostEqual(sections.depth_to_fixity(29000, Iw, 'sand', nh=0.556), 1.8 * (29000 * Iw / 0.556) ** 0.2, places=9)
        self.assertAlmostEqual(sections.depth_to_fixity(29000, Iw, 'clay', Su=1.0), 1.4 * (29000 * Iw / (0.465 * 1.0)) ** 0.25, places=9)


@needs_xml
class DemandsFromXml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = model.default_case('End Bent 1')
        cls.records = cls.case['analysis']['records']
        cls.raw = raw_pile_forces(EB_XML)

    def test_head_compression_and_drag_load(self):
        rec = [r for r in self.records if r['combination'] == '1' and r['pile'] == '1' and r['head']]
        self.assertEqual(len(rec), 1)
        raw = next(a for c, s, p, el, side, a in self.raw if (c, p, el, side) == ('1', '1', 1, 'I'))
        self.assertAlmostEqual(rec[0]['P_fbmp'], -raw, places=9)
        self.assertTrue(80.0 < rec[0]['P_fbmp'] < 110.0)          # FBMP head compression is about 95 kip
        restated = loads.restate(self.records, 36.0, 1.10, 1.00)
        r1 = next(r for r in restated if r['combination'] == '1' and r['pile'] == '1' and r['head'])
        self.assertAlmostEqual(r1['P_u'], -raw + 1.10 * 36.0, places=9)
        for r in restated:
            self.assertAlmostEqual(r['P_u'] - r['P_fbmp'], 1.10 * 36.0 if r['limit'] == 'strength' else 1.00 * 36.0, places=5)

    def test_service_uses_unit_factor_and_all_records_present(self):
        limits = {r['limit'] for r in self.records}
        self.assertEqual(limits, {'strength', 'service'})
        self.assertEqual(len(self.records), len(self.raw))
        self.assertEqual(sorted({r['combination'] for r in self.records}), ['1', '2', '3', '4'])
        for r in self.records:
            if r['limit'] == 'service':
                self.assertEqual(r['gamma_DR'], 1.00)
            elif r['limit'] == 'strength':
                self.assertEqual(r['gamma_DR'], 1.10)
            self.assertAlmostEqual(r['M_res'], math.hypot(r['M2'], r['M3']), places=5)
        self.assertTrue(any(r['wind'] for r in self.records) and not all(r['wind'] for r in self.records))

    def test_fdl_excludes_downdrag(self):
        strength_heads = [-a for c, s, p, el, side, a in self.raw if s.startswith('STRENGTH') and el == 1 and side == 'I']
        e = model.evaluate(self.case)
        self.assertAlmostEqual(e.details['fdl']['FDL_kip'], max(strength_heads), places=9)
        self.assertAlmostEqual(e.value('FDL_fbmp'), max(strength_heads), places=9)
        self.assertAlmostEqual(e.value('DD'), 36.0, places=9)
        self.assertAlmostEqual(e.value('R_n_req'), (max(strength_heads) + 0.0 + 36.0) / 0.75, places=9)
        self.assertEqual(e.data_table['Factored Design Load (tons)'], math.ceil(max(strength_heads) / 2 - 1e-9))
        self.assertEqual(e.data_table['Downdrag (tons)'], 18)

    def test_governing_retains_ties(self):
        recs = [dict(id=i, v=1.0) for i in range(3)] + [dict(id=9, v=0.5)]
        g = loads.governing(recs, lambda r: r['v'])
        self.assertEqual(len(g['ties']), 3)
        self.assertEqual(g['dc'], 1.0)
        self.assertIsNone(loads.governing([], lambda r: 1.0))
        g = loads.governing(recs, lambda r: None if r['id'] != 9 else 0.5)
        self.assertEqual(g['record']['id'], 9)

    def test_head_envelope(self):
        env = loads.head_envelope(model.evaluate(self.case).records)
        self.assertEqual(set(env), {'STRENGTH-I', 'STRENGTH-III', 'SERVICE-I'})
        self.assertGreater(env['STRENGTH-III']['max_compression_kip'], 80.0)
        self.assertEqual(env['STRENGTH-I']['max_uplift_kip'], 0.0)


@needs_xml
class DefaultCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evals = {s: model.evaluate(model.default_case(s)) for s in ('End Bent 1', 'End Bent 2', 'Pier')}

    def test_no_numerical_failures(self):
        for support, e in self.evals.items():
            failed = [(c.key, c.ratio) for c in e.checks if 'FAIL' in c.status]
            self.assertEqual(failed, [], support)
            numeric = [c for c in e.checks if isinstance(c.ratio, (int, float))]
            self.assertTrue(numeric)
            self.assertTrue(all(math.isfinite(c.ratio) for c in numeric))
            self.assertIn('pending', e.status)

    def test_end_bent_checks(self):
        e = self.evals['End Bent 1']
        keys = {c.key for c in e.checks}
        for key in ('psc_axial', 'psc_flex_bi', 'psc_flex_res', 'psc_shear', 'psc_tension', 'psc_svc_comp', 'psc_svc_tens', 'psc_prestress',
                    'psc_min_size', 'spacing', 'psc_head', 'psc_splice', 'fbmp_dc', 'nbr', 'data_table'):
            self.assertIn(key, keys)
        by = {c.key: c for c in e.checks}
        self.assertEqual(by['psc_head'].status, 'PENDING')
        self.assertEqual(by['psc_tension'].ratio, 0.0)
        self.assertGreater(by['psc_flex_bi'].ratio, 0.0)
        for key in ('psc_axial', 'psc_flex_bi', 'psc_flex_res', 'psc_shear', 'psc_svc_comp', 'psc_svc_tens'):
            self.assertIsNotNone(e.governing.get(key), key)
        self.assertTrue(e.curve['Pr'].size > 100 and 'resultant' in e.curve)
        self.assertEqual(len(e.data_table), 17)

    def test_pier_reports_tension_and_fbmp_dc(self):
        e = self.evals['Pier']
        by = {c.key: c for c in e.checks}
        self.assertTrue(10.0 < e.value('T_u') < 13.0)
        self.assertAlmostEqual(e.value('P_r_t'), 0.95 * 45.0 * 29.44, delta=0.5)
        self.assertAlmostEqual(by['pipe_tension'].ratio, e.value('T_u') / e.value('P_r_t'), places=12)
        self.assertGreater(by['pipe_tension'].ratio, 0.0)
        self.assertIn('0.', by['fbmp_dc'].demand)
        self.assertIsNotNone(by['pipe_comb'].ratio)
        self.assertEqual(e.data_table['Pile Size & Type'], '20" Ø Pipe')
        head_up = e.details['fdl']['T_kip']                          # head-only uplift: none at the pier head
        self.assertEqual(head_up, 0.0)
        self.assertEqual(e.data_table['Tension Resistance (tons)'], 'N/A')
        self.assertGreater(by['pipe_tension'].ratio, 0.0)             # the structural check still sees the uplift at depth
        structural = [c.ratio for c in e.checks if c.key in model.STRUCTURAL_CHECKS and c.ratio is not None]
        self.assertEqual(e.strength_dc, max(structural))
        self.assertLess(e.strength_dc, 1.0)
        self.assertGreaterEqual(e.max_ratio, e.strength_dc)
        self.assertEqual(e.max_ratio, 1.0)                           # pile spacing is exactly 3.0 diameters
        self.assertEqual(e.data_table['Downdrag (tons)'], 'N/A')

    def test_engine_matches_numerical_routines(self):
        e = self.evals['End Bent 1']
        d = e.details
        self.assertAlmostEqual(e.value('V_r'), d['shear']['Vr'], places=9)
        self.assertAlmostEqual(e.value('DC_bi'), d['biaxial']['ratio'], places=9)
        self.assertAlmostEqual(e.value('DC_rs'), d['ratio_rs'], places=9)
        p = self.evals['Pier']
        self.assertAlmostEqual(p.value('P_n'), p.details['axial']['Pn'], places=7)
        self.assertAlmostEqual(p.value('M_n'), p.details['flex']['Mn'], places=7)
        self.assertAlmostEqual(p.value('V_r'), p.details['shear']['Vr'], places=7)
        self.assertAlmostEqual(p.value('DC_comb'), p.details['comb']['ratio'], places=9)
        self.assertAlmostEqual(p.value('L_fix'), p.details['L_fix'], places=9)

    def test_references_and_names_exist(self):
        for e in self.evals.values():
            names = set(e.engine.defs) | set(e.externals)
            for c in e.checks:
                self.assertTrue(c.refs or c.group in ('Reference',), c.key)
                for r in c.refs:
                    self.assertIn(r, model.REFERENCES, (c.key, r))
                for n in c.names:
                    self.assertIn(n, names, (c.key, n))
            for d in e.definitions:
                for r in d['refs']:
                    self.assertIn(r, model.REFERENCES, (d['name'], r))
            self.assertTrue(model.formula_trace(e))

    def test_end_bent_two_uses_its_own_export(self):
        a = self.evals['End Bent 2'].case['analysis']
        self.assertEqual(a['registered_id'], 'EB2-XML')
        self.assertTrue(a['matches_register'])
        self.assertEqual(self.evals['End Bent 1'].case['analysis']['registered_id'], 'EB-XML')
        self.assertEqual(self.evals['Pier'].case['analysis']['registered_id'], 'PIER-XML')

    def test_heads_and_ground(self):
        eb = self.evals['End Bent 1'].case['inputs']
        self.assertAlmostEqual(eb['EL_cutoff'], 494.85 / 12, places=4)
        self.assertAlmostEqual(eb['EL_ground'], 24.01, places=2)
        self.assertAlmostEqual(self.evals['Pier'].case['inputs']['EL_cutoff'], 501.26 / 12, places=4)
        self.assertEqual(self.evals['Pier'].case['inputs']['D_pile'], self.evals['Pier'].case['inputs']['D_out'])


class DataTableRounding(unittest.TestCase):
    @needs_xml
    def test_rounding_rules(self):
        case = model.default_case('End Bent 1')
        for name, value in dict(EL_min_tip=12.7, L_test_pile=80.2, EL_scour_100=5.55, EL_scour_LT=-3.04, R_scour_total_tons=3.1,
                                R_scour_net_tons=2.2, DD_tons=17.2).items():
            model.edit_input(case, name, value)
        e = model.evaluate(case)
        t = e.data_table
        self.assertEqual(t['Minimum Tip Elevation (ft)'], 12)                         # rounded down
        self.assertEqual(t['Test Pile Length / Pile Order Length (ft)'], f'81 / {math.ceil(case["inputs"]["EL_cutoff"] - 12)}')
        self.assertEqual(t['Pile Cut-Off Elevation (ft)'], 41.2)                       # nearest tenth
        self.assertEqual(t['Downdrag (tons)'], 18)                                      # 17.2 rounded up
        self.assertEqual(t['Total Scour Resistance (tons)'], 4)
        self.assertEqual(t['Net Scour Resistance (tons)'], 3)
        self.assertEqual(t['100-Year Scour Elevation (ft)'], round(5.55, 1))
        self.assertEqual(t['Long-Term Scour Elevation (ft)'], -3.0)
        self.assertEqual(t['Resistance Factor'], 0.75)
        fdl = e.details['fdl']['FDL_kip'] / 2
        self.assertEqual(t['Nominal Bearing Resistance (tons)'], math.ceil((fdl + 2.2 + 17.2) / 0.75 - 1e-9))
        self.assertEqual(t['Factored Design Load (tons)'], math.ceil(fdl - 1e-9))

    @needs_xml
    def test_missing_entries_are_na(self):
        t = model.evaluate(model.default_case('End Bent 1')).data_table
        for key in ('Minimum Tip Elevation (ft)', 'Test Pile Length / Pile Order Length (ft)', 'Required Jet Elevation (ft)',
                    'Required Preform Elevation (ft)', 'Total Scour Resistance (tons)', 'Net Scour Resistance (tons)',
                    '100-Year Scour Elevation (ft)', 'Design Scour Elevation (temporary bridges)', 'Long-Term Scour Elevation (ft)',
                    'Tension Resistance (tons)'):
            self.assertEqual(t[key], 'N/A', key)
        self.assertEqual([h for _, h in model.DATA_TABLE_COLUMNS][:2], ['Pier / Bent', 'Pile Size & Type'])
        self.assertEqual([l for l, _ in model.DATA_TABLE_COLUMNS], list('ABCDEFGHIJKLMNOPQ'))
        self.assertEqual(list(t), [h for _, h in model.DATA_TABLE_COLUMNS])


class CaseHandling(unittest.TestCase):
    def test_json_round_trip(self):
        case = model.default_case('End Bent 1')
        text = json.dumps(case)
        back = json.loads(text)
        e1, e2 = model.evaluate(case), model.evaluate(back)
        self.assertEqual([(c.key, c.ratio, c.status) for c in e1.checks], [(c.key, c.ratio, c.status) for c in e2.checks])
        self.assertEqual(e1.data_table, e2.data_table)
        self.assertEqual(back['format'], model.FORMAT)

    def test_saved_case_needs_no_xml(self):
        case = model.default_case('Pier')
        saved = json.loads(json.dumps(case))
        if saved['analysis'] is None:
            self.skipTest('registered export not present')
        original = sources.registered_path
        sources.registered_path = lambda sid: Path('does-not-exist') / sid
        try:
            e = model.evaluate(saved)
        finally:
            sources.registered_path = original
        self.assertGreater(len(e.records), 500)

    def test_without_results_checks_are_pending_not_errors(self):
        case = model.default_case('Pier', load_xml=False)
        e = model.evaluate(case)
        by = {c.key: c for c in e.checks}
        self.assertIsNone(by['pipe_comb'].ratio)
        self.assertEqual(e.records, [])
        self.assertEqual(by['pipe_klr'].status.split(' ')[0], 'PASS')

    def test_unknown_format_refused(self):
        with self.assertRaises(ValueError):
            model.upgrade_case({'format': 'd2mpdb-end-bent-walls', 'schema_version': 2})
        with self.assertRaises(ValueError):
            model.upgrade_case({'schema_version': 1})
        case = model.default_case('Pier', load_xml=False)
        case['schema_version'] = model.SCHEMA_VERSION + 1
        with self.assertRaises(ValueError):
            model.upgrade_case(case)

    def test_validation(self):
        case = model.default_case('End Bent 1', load_xml=False)
        bad = copy.deepcopy(case)
        bad['inputs']['fc'] = 'x'
        with self.assertRaises(ValueError):
            model.validate_case(bad)
        bad = copy.deepcopy(case)
        bad['inputs']['D_pile'] = 20.0                      # index 455-018 is an 18 in pile
        with self.assertRaises(ValueError):
            model.validate_case(bad)
        bad = copy.deepcopy(case)
        bad['psc']['pattern'] = '99~0.6'
        with self.assertRaises(ValueError):
            model.validate_case(bad)
        ok = copy.deepcopy(case)
        ok['inputs']['EL_min_tip'] = None
        self.assertTrue(model.validate_case(ok))

    def test_edit_input_syncs_pipe_diameter_and_derived_lengths(self):
        case = model.default_case('Pier', load_xml=False)
        model.edit_input(case, 'D_out', 24.0)
        self.assertEqual(case['inputs']['D_pile'], 24.0)
        before = case['inputs']['L_unsupported']
        model.edit_input(case, 'EL_ground', case['inputs']['EL_ground'] - 1.0)
        self.assertAlmostEqual(case['inputs']['L_unsupported'], before + 1.0, places=6)
        self.assertAlmostEqual(case['inputs']['L_v'], before + 1.0, places=6)

    def test_select_psc_changes_size_and_spiral(self):
        case = model.default_case('End Bent 1', load_xml=False)
        model.select_psc(case, '455-030', '24~1/2S')
        self.assertEqual(case['inputs']['D_pile'], 30.0)
        self.assertEqual(case['inputs']['spiral_wire_area'], 0.040)
        e = model.evaluate(case)
        self.assertAlmostEqual(e.value('A_g'), 900 - math.pi / 4 * 18 ** 2, places=9)
        self.assertGreater(e.value('P_r_max'), 1500.0)
        with self.assertRaises(ValueError):
            model.select_psc(case, '455-018', '99~x')

    def test_standard_plans_data(self):
        plans = model.STANDARD_PLANS['indexes']
        o = {o['id']: o for o in plans['455-018']['options']}
        self.assertEqual((o['12~0.6']['jacking_kip'], o['12~0.6']['strand_area_in2']), (35, 0.217))
        self.assertEqual(o['16~1/2']['jacking_kip'], 26)
        self.assertEqual(o['12~1/2S']['strand_area_in2'], 0.167)
        self.assertEqual({k: v['size_in'] for k, v in plans.items()}, {'455-014': 14, '455-018': 18, '455-024': 24, '455-030': 30})
        self.assertEqual(model.STANDARD_PLANS['max_driving_resistance_tons']['18'], 300)
        self.assertEqual(model.STANDARD_PLANS['splice_moment_kip_ft'], {'18': 245, '24': 600, '30': 950})
        self.assertEqual(plans['455-030']['spiral_wire'], 'W4.0')


@needs_xml
class SourceReceipts(unittest.TestCase):
    def test_registered_hashes_come_from_the_register(self):
        import csv
        with open(ROOT / 'project_current' / 'source_register.csv', encoding='utf-8-sig') as f:
            register = {r['source_id']: r['sha256'] for r in csv.DictReader(f)}
        for sid, entry in model.SOURCES['sources'].items():
            self.assertEqual(entry['sha256'], register[sid], sid)

    def test_receipt_names_the_match_or_flags_a_new_upload(self):
        content = EB_XML.read_bytes()
        case = model.default_case('End Bent 1', load_xml=False)
        updates, receipt = sources.apply_source(case, 'FBMP-XML', content, EB_XML.name)
        self.assertEqual(receipt['registered_id'], 'EB-XML')
        self.assertTrue(receipt['matches_register'])
        self.assertEqual(receipt['sha256'], hashlib.sha256(content).hexdigest())
        self.assertTrue(any('prestress' in n for n in receipt['notes']))
        self.assertEqual(case['analysis']['piles'], 4)
        self.assertEqual(updates['N_pile'], 4)
        self.assertAlmostEqual(updates['S_pile'], 4.5, places=6)
        modified = content + b'\n<!-- modified copy -->\n'
        other = model.default_case('End Bent 1', load_xml=False)
        _, receipt2 = sources.apply_source(other, 'FBMP-XML', modified, 'copy.XML')
        self.assertIsNone(receipt2['registered_id'])
        self.assertFalse(receipt2['matches_register'])
        self.assertTrue(any('not a registered export' in n.lower() for n in receipt2['notes']))
        self.assertEqual(other['sources']['EL_cutoff']['status'], 'differs from register')

    def test_pier_xml_sets_pipe_family_and_keeps_design_fy(self):
        case = model.default_case('Pier', load_xml=False)
        _, receipt = sources.apply_source(case, 'PIER-XML', PIER_XML.read_bytes(), PIER_XML.name)
        self.assertEqual(case['family'], 'pipe')
        self.assertEqual(case['inputs']['D_out'], 20.0)
        self.assertEqual(case['inputs']['t_wall'], 0.48)
        self.assertEqual(case['inputs']['Fy'], 45.0)
        self.assertTrue(any('60' in n and 'Fy' in n for n in receipt['notes']))


if __name__ == '__main__':
    unittest.main()
