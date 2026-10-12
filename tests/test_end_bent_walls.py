"""End-bent backwall, cheek-wall and tie-back strap calculation.

The section design reproduces the template Mathcad ("3.End Bent 1 Backwall Design",
FC 02/2025) with its own inputs; project tests pin the statics and provenance.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile
from pier_cap.engine import Engine, Q
from end_bent_walls.model import (default_case, evaluate, strap_table, COMBINATIONS, STRENGTH, material_definitions,
                                  section_definitions, unit_quantity, _d, validate_case, upgrade_case)
from end_bent_walls.reviews import record_review
from end_bent_walls import exports

ROOT = Path(__file__).resolve().parent.parent
CURRENT = ROOT / 'project_current'


def q(value, unit=None):
    return Q(float(value)) * unit_quantity(unit)


class TemplateSectionRegression(unittest.TestCase):
    """Template: 12 in backwall, 3 in cover, #5 @ 12 in, f'c 5.5 ksi, Mu 8.4254 and Ms 4.9712 kip-ft per ft."""

    @classmethod
    def setUpClass(cls):
        defs = [_d('t', 'b_s', '12 in', 'in', '')] + material_definitions() + section_definitions('t', 'FF', 't_w', 'cv', 'M_u_FF', 'M_s_FF')
        ext = {'t_w': q(12, 'in'), 'cv': q(3, 'in'), 'A_b_FF': q(.31, 'in^2'), 'd_b_FF': q(.625, 'in'), 's_FF': q(12, 'in'),
               'fc': q(5.5, 'ksi'), 'fy': q(60, 'ksi'), 'Es': q(29000, 'ksi'), 'w_cE': q(.145, 'kip/ft^3'), 'K_1': q(1), 'lambda_c': q(1),
               'phi_f': q(.9), 'phi_v': q(.9), 'gamma_e': q(1), 'fss_ratio': q(.8), 'gamma_1': q(1.6), 'gamma_3': q(.67), 'beta_v': q(2),
               'M_u_FF': q(8.42542069231792, 'kip*ft'), 'M_s_FF': q(4.9712311347203979, 'kip*ft')}
        cls.engine = Engine(defs, externals=ext)

    def value(self, name, unit=None):
        return self.engine.get(name).v / unit_quantity(unit).v

    def test_flexure_matches_mathcad(self):
        # Mathcad's Given/Find held a at the provided-steel value (0.3316 in): As = Mu / (φ fy (d - a/2)).
        mu, d, a = 8.42542069231792 * 12, self.value('d_FF', 'in'), self.value('a_FF', 'in')
        self.assertAlmostEqual(mu / (0.9 * 60 * (d - a / 2)), 0.21971089157691945, places=9)
        # The port solves the quadratic exactly, so φMn at the required area equals Mu.
        required = self.value('A_req_FF', 'in^2')
        a_req = required * 60 / (0.85 * 5.5 * 12)
        self.assertAlmostEqual(0.9 * required * 60 * (d - a_req / 2), mu, places=6)
        self.assertAlmostEqual(required, 0.2184559459, places=8)
        self.assertAlmostEqual(self.value('M_r_FF', 'kip*ft'), 11.887805815508019, places=6)
        self.assertAlmostEqual(self.value('eps_t_FF'), 0.05792109375, places=8)
        self.assertAlmostEqual(self.value('M_cr_FF', 'kip*ft'), 14.481002000248457, places=6)

    def test_crack_control_matches_mathcad(self):
        self.assertAlmostEqual(self.value('n_m'), 6.5487899353722829, places=6)
        self.assertAlmostEqual(self.value('f_ss_FF', 'ksi'), 23.554913697730086, places=5)
        self.assertAlmostEqual(self.value('beta_s_FF'), 1.5447070914696814, places=8)
        self.assertAlmostEqual(self.value('s_cr_FF', 'in'), 12.613463438666173, places=5)

    def test_shear_matches_mathcad(self):
        self.assertAlmostEqual(self.value('d_v_FF', 'in'), 8.64, places=8)
        self.assertAlmostEqual(self.value('V_c_FF', 'kip'), 15.367152868920378, places=6)
        self.assertAlmostEqual(self.value('V_r_FF', 'kip'), 13.83043758202834, places=6)


class ProjectCalculation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = evaluate()

    def test_service_overturning_hand_sum(self):
        e = self.e
        self.assertAlmostEqual(e.value('k_a'), 1 / 3, places=12)
        self.assertAlmostEqual(e.value('F_EH'), 0.5 / 3 * 0.115 * 7.083 ** 2 * 212 / 12, places=6)
        hand = (e.value('F_EH') * e.value('y_EH', 'ft') + (e.value('F_ES') + e.value('F_LS')) * e.value('y_LS', 'ft')
                + (e.value('F_TU') + e.value('F_SH') + 2 * 1.63) * e.value('y_brg', 'ft')
                + 2 * (92.07 + 28.98) * 0.5 + e.value('W_cap') * 0.25 + e.value('W_ped') * 0.75 + e.value('W_ck') * 0.25 - e.value('W_bw') * 1.0)
        self.assertAlmostEqual(e.value('M_SERI'), hand, places=6)

    def test_combination_totals_equal_their_tables(self):
        for c in COMBINATIONS:
            rows = strap_table(self.e, c['key'])
            self.assertAlmostEqual(sum(r['factored_moment'] for r in rows), self.e.value('M_' + c['key']), places=6)
            self.assertAlmostEqual(sum(r['factored_force'] for r in rows), self.e.value('H_' + c['key']), places=6)

    def test_strap_force_is_the_larger_of_horizontal_and_moment_equilibrium(self):
        for c in COMBINATIONS:
            k = c['key']
            expected = max(self.e.value('H_' + k), self.e.value('M_' + k) / self.e.value('y_strap', 'ft'))
            self.assertAlmostEqual(self.e.value('F_str_' + k), expected, places=6)
            self.assertAlmostEqual(self.e.value('f_str_' + k, 'kip/ft'), expected / (196 / 12), places=6)
        self.assertAlmostEqual(self.e.value('f_str_u'), max(self.e.value('f_str_' + c['key']) for c in STRENGTH), places=9)

    def test_vertical_live_and_uplift_take_no_stabilizing_credit(self):
        terms = {t['item']: t for t in self.e.terms['STRIII1']}
        self.assertEqual(terms['WSV']['factor'], 0.0)
        self.assertEqual(terms['bw']['factor'], 0.9)
        self.assertEqual(terms['DCb']['factor'], 1.25)

    def test_cap_torsion_closes_and_screens(self):
        for result in self.e.cap['by_combo'].values():
            self.assertAlmostEqual(result['closure'], 0.0, places=6)
        self.assertLess(self.e.cap['torsion_max'], self.e.value('T_lim'))

    def test_registered_defaults_pass_numerical_checks(self):
        failed = [c.label for c in self.e.checks if 'FAIL' in c.status]
        self.assertEqual(failed, [])
        pending = {c.key for c in self.e.checks if c.status == 'PENDING'}
        self.assertIn('prereq_settlement', pending)

    def test_pile_tolerance_and_strap_location(self):
        case = default_case()
        case['inputs']['tol_pile'] = 0.0
        self.assertLess(evaluate(case).value('M_STRI'), self.e.value('M_STRI'))
        case = default_case()
        case['inputs']['z_strap'] = self.e.value('e_STRI', 'ft') - self.e.value('y_top', 'ft')
        at_resultant = evaluate(case)
        self.assertAlmostEqual(at_resultant.value('V_pile_STRI'), 0.0, places=6)
        self.assertAlmostEqual(at_resultant.value('F_str_STRI'), at_resultant.value('H_STRI'), places=6)

    def test_engaged_strap_reverses_the_backwall_moment(self):
        e = self.e
        expected = e.value('f_str_STRI', 'kip/ft') * 1.5 - e.value('M_sl_STRI')
        self.assertAlmostEqual(e.value('M_en_STRI'), expected, places=6)
        self.assertGreater(e.value('M_u_SF'), e.value('M_u_FF'))

    def test_invalid_geometry_is_rejected(self):
        case = default_case()
        case['inputs']['L_bw'] = 300.0
        with self.assertRaisesRegex(ValueError, 'L_bw'):
            validate_case(case)


class SourcesAndExports(unittest.TestCase):
    def test_registered_sources_match_and_supply_inputs(self):
        from end_bent_walls.sources import read_end_bent_case, read_fbmp_xml, read_freecad
        path = CURRENT / 'cap_design/end_bents/selected_case.json'
        updates, _, receipt = read_end_bent_case(path.read_bytes(), path.name)
        self.assertTrue(receipt['matches_register'])
        self.assertEqual((updates['b_cap'], updates['h_cap'], updates['embed_pile']), (42.0, 36.0, 12.0))
        path = CURRENT / 'fbmp/end_bents/End Bent 1_Fixed.XML'
        updates, _, receipt = read_fbmp_xml(path.read_bytes(), path.name)
        self.assertTrue(receipt['matches_register'])
        self.assertEqual((updates['P_DC'], updates['P_PL'], updates['FY_WS1']), (92.07, 28.98, 3.29))
        self.assertTrue(any('node 4' in note for note in receipt['notes']))
        path = next((CURRENT / 'geometry/freecad').glob('*.FCStd'))
        updates, _, receipt = read_freecad(path.read_bytes(), path.name)
        self.assertTrue(receipt['matches_register'])
        self.assertAlmostEqual(updates['H_bw'], 4.083, places=3)
        self.assertEqual((updates['L_bw'], updates['t_slab']), (196.0, 4.0))

    def test_case_json_round_trip_and_stale_review(self):
        e = evaluate()
        check = next(c for c in e.checks if c.key == 'cap_torsion')
        case = record_review(e.case, check, 'close', 'Screen passes')
        reloaded = exports.load_case(exports.case_json(case).encode('utf-8'))
        self.assertEqual(reloaded['inputs'], case['inputs'])
        self.assertEqual(next(c for c in evaluate(reloaded).checks if c.key == 'cap_torsion').status, 'PASS · CLOSED')
        reloaded['inputs']['P_DC'] = 120.0
        changed = next(c for c in evaluate(reloaded).checks if c.key == 'cap_torsion')
        self.assertTrue(changed.review['stale'])
        self.assertNotIn('CLOSED', changed.status)

    def test_failed_check_cannot_be_closed(self):
        case = default_case()
        case['inputs']['s_FF'] = 30.0
        e = evaluate(case)
        failed = next(c for c in e.checks if c.key == 'spacing_FF')
        self.assertIn('FAIL', failed.status)
        with self.assertRaisesRegex(ValueError, 'override'):
            record_review(e.case, failed, 'close', 'no')

    def test_handoff_and_report(self):
        from openpyxl import load_workbook
        e = evaluate()
        sheet = load_workbook(io.BytesIO(exports.handoff_xlsx(e)))['Tie-back loads']
        self.assertAlmostEqual(sheet['B5'].value, round(e.value('f_str_s'), 3))
        self.assertAlmostEqual(sheet['C5'].value, round(e.value('f_str_u'), 3))
        from end_bent_walls.report import build_report
        text = build_report(e)
        self.assertIn('SDM 12.3.F', text)
        self.assertGreater(text.count('<math'), 250)
        self.assertNotIn('<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"><mrow></mrow>', text)

    def test_unknown_case_format_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'not an end-bent backwall case'):
            upgrade_case({'inputs': {}})


class PortableNotebook(unittest.TestCase):
    def test_embedded_package_is_current_and_intact(self):
        from scripts.build_backwall_notebook import NOTEBOOK, SETUP_ID, package_files
        notebook = json.loads((ROOT / NOTEBOOK).read_text(encoding='utf-8'))
        source = ''.join(next(c for c in notebook['cells'] if c.get('id') == SETUP_ID)['source'])
        revision = source.split('revision = "', 1)[1].split('"', 1)[0]
        package = base64.b64decode(source.split('PACKAGE = "', 1)[1].split('"', 1)[0])
        self.assertEqual(hashlib.sha256(package).hexdigest(), revision)
        embedded = zipfile.ZipFile(io.BytesIO(package))
        for file in package_files(ROOT):
            name = file.relative_to(ROOT).as_posix()
            # Checkouts may convert line endings; compare content, not the platform newline.
            self.assertEqual(embedded.read(name).replace(b'\r\n', b'\n'), file.read_bytes().replace(b'\r\n', b'\n'),
                             f'{name} changed; run scripts/build_backwall_notebook.py')
        self.assertTrue(all(c['outputs'] == [] for c in notebook['cells'] if c['cell_type'] == 'code'))


if __name__ == '__main__':
    unittest.main()
