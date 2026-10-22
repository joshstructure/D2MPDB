"""Pier cap cheek wall design (C018, pier_cheek_wall): independent mechanics, the CAD steel case, report, editions, notebook."""
import base64
import hashlib
import io
import json
import math
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calc_common import bpad, notebook  # noqa: E402
from calc_common.exports import Exports  # noqa: E402
from calc_common.model import default_case, evaluate  # noqa: E402
from calc_common.report import build_report  # noqa: E402
from calc_common.schematics import schematic, meaning, package_drawer  # noqa: E402
from calc_common.spec import ALL_PASS  # noqa: E402
from pier_cheek_wall.model import SPEC  # noqa: E402

HOW = 'run scripts/build_pier_cheek_wall.py'


def unix(data):
    return data.replace(b'\r\n', b'\n')


class Mechanics(unittest.TestCase):
    """Hand arithmetic of the CAD case against the engine."""

    def setUp(self):
        self.e = evaluate(SPEC)
        self.v = self.e.value

    def test_wind_pressure_chain_matches_c001_and_c002(self):
        v = self.v
        q = 2.56e-6 * 130 ** 2 * 1.01971744991174 * 0.85
        self.assertAlmostEqual(v('q_III', 'ksf'), q, places=9)
        self.assertAlmostEqual(v('P_III', 'ksf'), q * 1.6, places=9)
        self.assertAlmostEqual(v('P_SI', 'ksf'), 2.56e-6 * 70 ** 2 * 0.85 * 1.6, places=9)
        self.assertAlmostEqual(v('P_V', 'ksf'), 2.56e-6 * 80 ** 2 * 0.85 * 1.6, places=9)
        self.assertAlmostEqual(v('P_str', 'ksf'), v('P_III', 'ksf'))
        # the +1.9 kip transverse and +0.5 kip longitudinal of the 19 October load review (D-062)
        self.assertAlmostEqual(v('F_T_III_both', 'kip'), 2 * 16 * q * 1.6, places=9)
        self.assertAlmostEqual(v('F_L_III_both', 'kip'), 2 * 4 * q * 1.6, places=9)
        self.assertAlmostEqual(v('F_T_III_both', 'kip'), 1.92, places=2)

    def test_cantilever_demands(self):
        v = self.v
        P = v('P_III', 'ksf')
        self.assertAlmostEqual(v('V_u', 'kip'), P * 4 * 4)
        self.assertAlmostEqual(v('M_u_A', 'kip*ft'), P * 4 * 4 ** 2 / 2)
        self.assertAlmostEqual(v('M_u_B', 'kip*ft'), P * 4 * 3.25 ** 2 / 2)
        self.assertAlmostEqual(v('M_T_III', 'kip*ft'), v('F_T_III', 'kip') * 2.0)

    def test_section_a_flexure_by_hand(self):
        v = self.v
        As, fy, fc, b = 1.2, 60.0, 5.5, 48.0
        a = As * fy / (0.85 * fc * b)
        d = 5.125
        self.assertAlmostEqual(v('d_A', 'in'), d)
        self.assertAlmostEqual(v('a_A', 'in'), a)
        self.assertAlmostEqual(v('M_r_A', 'kip*ft'), 0.9 * As * fy * (d - a / 2) / 12)
        fr = 0.24 * math.sqrt(fc)
        self.assertAlmostEqual(v('M_cr_A', 'kip*ft'), 0.67 * 1.6 * fr * b * 12 ** 2 / 6 / 12)
        self.assertAlmostEqual(v('M_min_A', 'kip*ft'), 1.33 * v('M_u_A', 'kip*ft'))
        self.assertEqual(v('phi_A'), 0.9)
        # section B: recess off the compression face
        self.assertAlmostEqual(v('d_B', 'in'), 5.125 - 0.75)
        self.assertAlmostEqual(v('S_c_B', 'in^3'), b * 11.25 ** 2 / 6)
        # crack control does not apply: service tension far below 0.8 fr
        self.assertLess(v('f_ct_A', 'ksi'), 0.8 * fr)
        self.assertEqual(v('s_cr_A', 'in'), 99.0)

    def test_shear_and_interface_by_hand(self):
        v = self.v
        dv = max(5.125 - v('a_A', 'in') / 2, 0.9 * 5.125, 0.72 * 12)
        self.assertAlmostEqual(v('d_v_A', 'in'), 8.64)
        self.assertAlmostEqual(v('V_r_A', 'kip'), 0.9 * 0.0316 * 2 * math.sqrt(5.5) * 48 * dv)
        Acv = 48 * 12
        self.assertAlmostEqual(v('V_ni', 'kip'), min(0.075 * Acv + 0.6 * 1.2 * 60, 0.2 * 5.5 * Acv, 0.8 * Acv))
        self.assertAlmostEqual(v('A_vf_min', 'in^2'), 0.05 * Acv / 60)

    def test_development_is_the_twelve_inch_floor_and_full_yield_just_exceeds_it(self):
        v = self.v
        ldb = 2.4 * 0.5 * 60 / math.sqrt(5.5)
        self.assertAlmostEqual(v('l_db', 'in'), ldb)
        self.assertEqual(v('lambda_rc'), 0.4)                         # d_b / c_b = 0.154, floored at 0.4
        self.assertAlmostEqual(v('l_d_full', 'in'), 0.4 * ldb)
        self.assertGreater(v('l_d_full', 'in'), 12.0)                 # 12.28 in without the excess-steel credit
        self.assertEqual(v('l_d', 'in'), 12.0)
        self.assertAlmostEqual(v('DC_develop'), 1.0)

    def test_distribution_steel_and_detailing(self):
        v = self.v
        self.assertAlmostEqual(v('A_ts_face', 'in^2/ft'), max(1.30 * 48 * 12 / (2 * 60 * 60), 0.11))
        self.assertAlmostEqual(v('A_ts_mat', 'in^2/ft'), 0.22)
        self.assertAlmostEqual(v('A_pr_v', 'in^2/ft'), 6 * 0.2 / 4)
        self.assertAlmostEqual(v('A_pr_h', 'in^2/ft'), 6 * 0.2 / 4)
        self.assertEqual(v('s_max_pri', 'in'), 18.0)
        self.assertAlmostEqual(v('s_clr_prov', 'in'), 2.5)
        self.assertAlmostEqual(v('s_clr_min', 'in'), 1.5)

    def test_cad_steel_passes_every_numerical_check(self):
        e = self.e
        failed = [c.key for c in e.checks if 'FAIL' in c.status]
        self.assertEqual(failed, [])
        pending = sorted(c.key for c in e.checks if 'PENDING' in c.status)
        self.assertEqual(pending, ['temp_h', 'temp_v'])               # the one-mat convention awaits confirmation
        self.assertAlmostEqual(e.strength_dc, 1.0)                    # development and cover sit exactly at their limits
        at_limit = sorted(c.key for c in e.checks if isinstance(c.ratio, float) and abs(c.ratio - 1.0) < 1e-9)
        self.assertEqual(at_limit, ['cover', 'develop'])
        self.assertEqual(e.blockpad_status, ALL_PASS)
        case = default_case(SPEC)
        case['confirmations']['single_mat'] = True
        self.assertEqual([c.key for c in evaluate(SPEC, case).checks if 'PENDING' in c.status], [])

    def test_a_shorter_embedment_or_a_thinner_cover_fails(self):
        case = default_case(SPEC)
        case['inputs']['L_emb'] = 11.0
        e = evaluate(SPEC, case)
        self.assertIn('FAIL', next(c for c in e.checks if c.key == 'develop').status)
        case = default_case(SPEC)
        case['inputs']['c_edge'] = 1.5
        e = evaluate(SPEC, case)
        self.assertIn('FAIL', next(c for c in e.checks if c.key == 'cover').status)

    def test_wind_from_the_other_wall_is_the_lighter_case(self):
        """The right wall's centred mat (5.75 in) has the larger effective depth; the left wall governs."""
        case = default_case(SPEC)
        case['inputs']['x_v'] = 5.75
        e = evaluate(SPEC, case)
        self.assertGreater(e.value('d_A', 'in'), self.v('d_A', 'in'))
        self.assertLess(e.value('DC_flex_A'), self.v('DC_flex_A'))


class ReportAndSchematics(unittest.TestCase):
    def test_report_carries_cards_qc_blocks_tables_and_every_section(self):
        e = evaluate(SPEC)
        html = build_report(SPEC, e)
        self.assertIn('type="application/report-cards+json"', html)
        self.assertIn('data-var=', html)
        equations = html.count('<div class="eq">')
        self.assertEqual(len(re.findall(r'<div class="eq">.*?</div>\s*<details class="qc">', html, re.S)), equations)
        for section in SPEC.sections:
            self.assertIn(f'id="section-{section["key"]}"', html, section['key'])
        for table in SPEC.tables:
            self.assertIn(table['title'], html, table['name'])
        self.assertIn('LRFD 3.8.1.2.3b', html)
        drawer = package_drawer(SPEC)
        self.assertIsNotNone(drawer)
        for d in e.definitions:
            self.assertIsNotNone(drawer(d['name']), f'{d["name"]} falls back to the generic term diagram')
            svg, label = schematic(SPEC, e, d['name'])
            self.assertTrue(svg.startswith('<svg') and label, d['name'])
            ET.fromstring(svg)
            self.assertTrue(meaning(SPEC, d['name']), d['name'])

    def test_exports_round_trip(self):
        x = Exports(SPEC)
        e = evaluate(SPEC)
        case = x.load_case(x.case_json(e.case).encode('utf-8'))
        self.assertEqual(case['inputs'], e.case['inputs'])
        self.assertIn('status', x.checks_csv(e))
        with self.assertRaises(ValueError):
            x.load_case(json.dumps({'format': 'other'}).encode())

    def test_committed_report_folder_describes_the_current_package(self):
        e = evaluate(SPEC)
        folder = SPEC.dir / 'report'
        case = json.loads((folder / 'cheek_case.json').read_text(encoding='utf-8'))
        self.assertEqual(case['inputs'], e.case['inputs'], HOW)
        csv = (folder / 'cheek_checks.csv').read_bytes()
        self.assertEqual(unix(csv), unix(Exports(SPEC).checks_csv(e).encode('utf-8')), HOW)


class BlockpadEdition(unittest.TestCase):
    def test_committed_standalone_sheet_equals_a_fresh_build(self):
        e = evaluate(SPEC)
        revision = notebook.embedded_revision(SPEC, ROOT) or 'working copy'
        sheet, eng, meta = bpad.build(SPEC, e, revision=revision)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / SPEC.package
            entry = bpad.write_outputs(SPEC, sheet, eng, meta, out_dir=out)
            self.assertEqual((SPEC.dir / SPEC.bpad_file).read_bytes(), (out / SPEC.bpad_file).read_bytes(), f'{SPEC.bpad_file} is stale: {HOW}')
            fragment = SPEC.dir / 'bpad' / 'fragments' / f'{SPEC.name}.xml'
            self.assertEqual(unix(fragment.read_bytes()), unix((out / 'bpad' / 'fragments' / f'{SPEC.name}.xml').read_bytes()), f'fragment stale: {HOW}')
            listed = json.loads((SPEC.dir / 'bpad' / 'verification.json').read_text(encoding='utf-8'))
            self.assertEqual(listed, [dict(entry, bpad_file=f'{SPEC.package}/{SPEC.bpad_file}')], f'verification.json is stale: {HOW}')
        self.assertEqual(entry['package_revision'], notebook.embedded_revision(SPEC, ROOT), f'notebook and sheet revisions differ: {HOW}')
        n_defs = sum(1 for d in e.definitions if 'function' not in d)
        self.assertGreaterEqual(entry['tool_comparisons'], n_defs + len(sheet.input_names))
        self.assertEqual(entry['status'], ALL_PASS)
        root = ET.fromstring((SPEC.dir / SPEC.bpad_file).read_bytes())
        self.assertEqual((root.tag, root.get('version')), ('document', '1.9'))
        self.assertEqual(root.find('report').get('title'), SPEC.full_title)


class PortableNotebook(unittest.TestCase):
    def test_embedded_package_is_current_and_intact(self):
        path = ROOT / SPEC.notebook
        self.assertTrue(path.is_file(), f'{SPEC.notebook} missing: {HOW}')
        nb = json.loads(path.read_text(encoding='utf-8'))
        source = ''.join(next(c for c in nb['cells'] if c.get('id') == notebook.SETUP_ID)['source'])
        revision = source.split('revision = "', 1)[1].split('"', 1)[0]
        package_bytes = base64.b64decode(source.split('PACKAGE = "', 1)[1].split('"', 1)[0])
        self.assertEqual(hashlib.sha256(package_bytes).hexdigest(), revision)
        embedded = zipfile.ZipFile(io.BytesIO(package_bytes))
        for file in notebook.package_files(SPEC, ROOT):
            name = file.relative_to(ROOT).as_posix()
            self.assertEqual(unix(embedded.read(name)), unix(file.read_bytes()), f'{name} changed; {HOW}')
        self.assertTrue(all(c['outputs'] == [] for c in nb['cells'] if c['cell_type'] == 'code'))
        self.assertIn('from pier_cheek_wall.widgets import Notebook', source)
        self.assertTrue(any(n.startswith('code_excerpts/pages/') for n in embedded.namelist()))


if __name__ == '__main__':
    unittest.main()
