"""The six journal-calculation packages (C001-C004, C015, C016): engine fidelity, reports, editions, notebooks.

C006 (pier_wall_fins) was sequestered on 2026-10-22 (D-082) to sequestered/pier_wall_fins/ and is not tested.

Each package reproduces the journal module it was ported from (the module's own formulas, evaluated independently at
import, are the reference), writes a report with cards and QC blocks, exports a verified Blockpad sheet, keeps its
committed editions and notebook current, and keeps the names other journal modules read.
"""
import base64
import hashlib
import importlib
import io
import json
import re
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calc_common import bpad, notebook  # noqa: E402
from calc_common.exports import Exports  # noqa: E402
from calc_common.model import evaluate, default_case  # noqa: E402
from calc_common.report import build_report  # noqa: E402
from calc_common.schematics import schematic, meaning, package_drawer  # noqa: E402
from calc_common.spec import ALL_PASS, FAILURES  # noqa: E402
from pier_cap.engine import Q  # noqa: E402

PACKAGES = ['wind_superstructure', 'fence_wind', 'bridge_movement', 'superstructure_uplift', 'mse_wall_exclusion', 'bearing_design']
TOL = 1e-9
HOW = 'run scripts/build_journal_calc_notebooks.py, then scripts/build_journal_calc_bpads.py (and --journal)'


def spec_of(package):
    return importlib.import_module(f'{package}.model').SPEC


def unix(data):
    return data.replace(b'\r\n', b'\n')


def shape(el):
    return (el.tag, sorted(el.attrib.items()), (el.text or '').strip(), [shape(c) for c in el], (el.tail or '').strip())


class JournalFidelity(unittest.TestCase):
    """Every definition of the journal module is reproduced by the package to 1 part in 10⁹."""

    def test_every_journal_definition_is_reproduced(self):
        dropped = {'bearing_design': 11}                      # superseded status strings written into the working notes instead
        total = 0
        for package in PACKAGES:
            spec = spec_of(package)
            imp = json.loads((spec.data_dir / 'journal_import.json').read_text(encoding='utf-8'))
            e = evaluate(spec)
            ok, missing = 0, []
            for it in imp['items']:
                if it.get('kind') != 'def' or 'evaluated' not in it or 'error' in it['evaluated']:
                    continue
                ev = it['evaluated']
                try:
                    mine = e.engine.get(it['name'])
                except Exception:
                    missing.append(it['name'])
                    continue
                if 'text' in ev:
                    self.assertEqual(mine, ev['text'], it['name'])
                elif 'bool' in ev:
                    self.assertEqual(bool(mine), ev['bool'], it['name'])
                else:
                    self.assertIsInstance(mine, Q, it['name'])
                    self.assertLessEqual(abs(mine.v - ev['v']), TOL * max(1.0, abs(ev['v'])), it['name'])
                    self.assertEqual([round(d, 6) for d in mine.d], [round(d, 6) for d in ev['dims']], it['name'])
                ok += 1
            self.assertEqual(len(missing), dropped.get(package, 0), f'{package}: {missing}')
            self.assertGreater(ok, 10, package)
            total += ok
        self.assertGreater(total, 400)          # 697 with C006 before D-082; C006 held 265 definitions

    def test_published_names_and_case_name_record_the_journal(self):
        for package in PACKAGES:
            spec = spec_of(package)
            e = evaluate(spec)
            for name in spec.published:
                self.assertIn(name, e.engine.defs.keys() | set(spec.inputs), f'{package}: {name}')
            imp = json.loads((spec.data_dir / 'journal_import.json').read_text(encoding='utf-8'))
            self.assertEqual(sorted(imp['inbound_names']), sorted(spec.published), package)
            self.assertIn(imp['journal_sha256'][:12], e.case['name'])


class ReportsAndChecks(unittest.TestCase):
    def test_report_carries_cards_qc_blocks_and_every_section(self):
        for package in PACKAGES:
            spec = spec_of(package)
            e = evaluate(spec)
            html = build_report(spec, e)
            self.assertIn('type="application/report-cards+json"', html, package)
            self.assertIn('data-var=', html)
            equations = html.count('<div class="eq">')
            self.assertEqual(len(re.findall(r'<div class="eq">.*?</div>\s*<details class="qc">', html, re.S)), equations, package)
            for section in spec.sections:
                self.assertIn(f'id="section-{section["key"]}"', html, f'{package}: {section["key"]}')
            drawer = package_drawer(spec)
            self.assertIsNotNone(drawer, f'{package}: no schematics module')
            for d in e.definitions:
                if 'function' in d:
                    continue
                self.assertIsNotNone(drawer(d['name']), f'{package}: {d["name"]} falls back to the generic term diagram')
                svg, label = schematic(spec, e, d['name'])
                self.assertTrue(svg.startswith('<svg') and label, f'{package}: {d["name"]}')
                ET.fromstring(svg)
                self.assertTrue(meaning(spec, d['name']), f'{package}: {d["name"]}')

    def test_checks_follow_the_journal_flags(self):
        for package in PACKAGES:
            spec = spec_of(package)
            e = evaluate(spec)
            for c in e.checks:
                if c.flag:
                    text = str(e.engine.get(c.flag))
                    spec_check = next(x for x in spec.checks if x['key'] == c.key)
                    if text in spec_check.get('fail_values', ['⊗ FAIL', 'FAIL']):
                        self.assertIn('FAIL', c.status, f'{package}: {c.key}')
                    elif text in spec_check.get('pass_values', ['✓ PASS', 'PASS']):
                        self.assertIn('PASS', c.status, f'{package}: {c.key}')
            self.assertEqual(e.blockpad_status, FAILURES if any('FAIL' in c.status for c in e.checks) else ALL_PASS)

    def test_mse_side_walls_sit_at_the_knife_edge_the_journal_records(self):
        spec = spec_of('mse_wall_exclusion')
        e = evaluate(spec)
        failing = sorted(c.key for c in e.checks if 'FAIL' in c.status)
        self.assertEqual(failing, ['b1w3', 'b2w2'])
        for key in ('b1w3', 'b2w2'):
            c = next(x for x in e.checks if x.key == key)
            self.assertAlmostEqual(c.ratio, 1.0, delta=1e-4)         # 0.0002 in short of 24 in in the saved model coordinates

    def test_exports_round_trip(self):
        for package in PACKAGES:
            spec = spec_of(package)
            x = Exports(spec)
            e = evaluate(spec)
            case = x.load_case(x.case_json(e.case).encode('utf-8'))
            self.assertEqual(case['inputs'], e.case['inputs'])
            self.assertIn('status', x.checks_csv(e) if e.checks else 'status')
            with self.assertRaises(ValueError):
                x.load_case(json.dumps({'format': 'other'}).encode())


class BlockpadEditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.built = {}
        for package in PACKAGES:
            spec = spec_of(package)
            e = evaluate(spec)
            revision = notebook.embedded_revision(spec, ROOT) or 'working copy'
            sheet, eng, meta = bpad.build(spec, e, revision=revision)
            out = Path(cls.tmp.name) / package
            entry = bpad.write_outputs(spec, sheet, eng, meta, out_dir=out)
            cls.built[package] = (spec, e, sheet, eng, meta, entry, out)

    def test_committed_standalone_sheets_equal_a_fresh_build(self):
        for package, (spec, e, sheet, eng, meta, entry, out) in self.built.items():
            committed = (spec.dir / spec.bpad_file).read_bytes()
            self.assertEqual(committed, (out / spec.bpad_file).read_bytes(), f'{package}/{spec.bpad_file} is stale: {HOW}')
            fragment = spec.dir / 'bpad' / 'fragments' / f'{spec.name}.xml'
            self.assertEqual(unix(fragment.read_bytes()), unix((out / 'bpad' / 'fragments' / f'{spec.name}.xml').read_bytes()), f'{package}: fragment stale: {HOW}')
            listed = json.loads((spec.dir / 'bpad' / 'verification.json').read_text(encoding='utf-8'))
            mine = [dict(entry, bpad_file=f'{package}/{spec.bpad_file}')]
            self.assertEqual(listed, mine, f'{package}: verification.json is stale: {HOW}')
            self.assertEqual(entry['package_revision'], notebook.embedded_revision(spec, ROOT), f'{package}: notebook and sheet revisions differ: {HOW}')

    def test_verification_was_substantial_and_the_sheet_is_native(self):
        for package, (spec, e, sheet, eng, meta, entry, out) in self.built.items():
            n_defs = sum(1 for d in e.definitions if 'function' not in d)
            self.assertGreaterEqual(entry['tool_comparisons'], n_defs + len(sheet.input_names))
            self.assertEqual(entry['status'], e.blockpad_status)
            root = ET.fromstring((out / spec.bpad_file).read_bytes())
            self.assertEqual((root.tag, root.get('version')), ('document', '1.9'))
            rep = root.find('report')
            self.assertEqual(rep.get('name'), spec.name)
            self.assertEqual(rep.get('title'), spec.full_title)
            names = [el.get('name') for el in rep.iter() if el.tag in ('table', 'canvas', 'section') and el.get('name')]
            self.assertEqual(len(names), len(set(names)), package)
            self.assertEqual([s.get('name') for s in rep.iter('section') if s.get('name') == 'WorkingNotes'], ['WorkingNotes'])
            for name in spec.published:
                self.assertIn(name, eng.defs, f'{package}: {name}')

    def test_a_wrong_equation_is_caught(self):
        spec, e = self.built['bridge_movement'][:2]
        d = next(x for x in e.definitions if x['name'] == 'δ_left')
        original = d['formula']
        d['formula'] = original.replace('L_left', '1.001*L_left')      # the sheet text changes; the notebook value does not
        try:
            with self.assertRaisesRegex(AssertionError, 'differ'):
                bpad.build(spec, e)
        finally:
            d['formula'] = original

    def test_distill_follows_a_modified_case(self):
        spec = spec_of('bridge_movement')
        case = default_case(spec)
        case['inputs']['T_high'] = 110.0
        e = evaluate(spec, case)
        data, verification = Exports(spec).distilled_bpad(e)
        formulas = [d.get('formula') for d in ET.fromstring(data).iter('dynexp')]
        self.assertIn('T_high = 110', formulas)
        self.assertEqual(json.loads(verification)[0]['status'], ALL_PASS)


class JournalEditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts import bpad_sheet as bs
        cls.links = bs.JournalLinks.load(ROOT / 'journal' / 'D2_I95_Project_Journal.bpad')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)

    def test_committed_journal_editions_equal_a_fresh_build_and_carry_live_references(self):
        for package in PACKAGES:
            spec = spec_of(package)
            e = evaluate(spec)
            revision = notebook.embedded_revision(spec, ROOT) or 'working copy'
            sheet, eng, meta = bpad.build(spec, e, revision=revision, journal=self.links)
            out = Path(self.tmp.name) / package
            entry = bpad.write_journal_outputs(spec, self.links, sheet, eng, meta, out_dir=out)
            committed = spec.dir / 'bpad' / 'journal'
            self.assertEqual(shape(ET.fromstring((committed / f'{spec.name}.xml').read_bytes())),
                             shape(ET.fromstring((out / 'journal' / f'{spec.name}.xml').read_bytes())), f'{package}: journal fragment stale: {HOW} --journal')
            listed = json.loads((committed / 'verification.json').read_text(encoding='utf-8'))[0]
            self.assertEqual(listed['fragment_sha256'], hashlib.sha256((committed / f'{spec.name}.xml').read_bytes()).hexdigest(), package)
            self.assertEqual(listed['journal_references'], entry['journal_references'])
            refs = {d['name']: d['journal'] for d in spec.input_spec if d.get('journal')}
            defs = {}
            for dyn in ET.fromstring((committed / f'{spec.name}.xml').read_bytes()).iter('dynexp'):
                lhs, _, rhs = dyn.get('formula').partition(' = ')
                defs[lhs] = rhs
            for name, owner in refs.items():
                self.assertTrue(defs.get(name, '').startswith(owner), f'{package}: {name} is not the live reference {owner}')
            rows = json.loads((committed / 'coherence.json').read_text(encoding='utf-8'))[spec.name]
            self.assertEqual(sorted(r['input'] for r in rows if r['status'] == 'reference'), sorted(refs), package)

    def test_the_gate_stops_on_a_journal_value_that_differs_from_the_case(self):
        from scripts import bpad_sheet as bs
        spec = spec_of('bridge_movement')
        e = evaluate(spec)
        self.links.override('BridgeGeometry_2Beam.Span_1', bs.Q(108 * 12, (1, 0, 0)))
        try:
            with self.assertRaisesRegex(AssertionError, 'coherence gate'):
                bpad.build(spec, e, journal=self.links)
        finally:
            self.links.overrides.clear()


class PortableNotebooks(unittest.TestCase):
    def test_embedded_packages_are_current_and_intact(self):
        for package in PACKAGES:
            spec = spec_of(package)
            path = ROOT / spec.notebook
            self.assertTrue(path.is_file(), f'{spec.notebook} missing: {HOW}')
            nb = json.loads(path.read_text(encoding='utf-8'))
            source = ''.join(next(c for c in nb['cells'] if c.get('id') == notebook.SETUP_ID)['source'])
            revision = source.split('revision = "', 1)[1].split('"', 1)[0]
            package_bytes = base64.b64decode(source.split('PACKAGE = "', 1)[1].split('"', 1)[0])
            self.assertEqual(hashlib.sha256(package_bytes).hexdigest(), revision)
            embedded = zipfile.ZipFile(io.BytesIO(package_bytes))
            for file in notebook.package_files(spec, ROOT):
                name = file.relative_to(ROOT).as_posix()
                self.assertEqual(embedded.read(name).replace(b'\r\n', b'\n'), file.read_bytes().replace(b'\r\n', b'\n'), f'{name} changed; {HOW}')
            self.assertTrue(all(c['outputs'] == [] for c in nb['cells'] if c['cell_type'] == 'code'))
            self.assertIn(f'from {package}.widgets import Notebook', source)


if __name__ == '__main__':
    unittest.main()
