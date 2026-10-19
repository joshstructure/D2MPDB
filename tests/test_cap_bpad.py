"""The three distilled cap Blockpad documents (cap_bpad/*.bpad) are current, tied to their reports, verified and journal-ready."""
import copy
import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from pier_cap.transverse import scheduled_bars
from scripts import bpad_sheet as bs
from scripts import build_cap_bpad as bc
from scripts import build_cap_mathcad as bm
from scripts import mathcad_sheet
from tools.bpad_workflow import Journal

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'cap_bpad'
JOURNAL = ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
HOW = 'run python scripts/build_cap_bpad.py after changing a cap case, a report, the formulas or the generator'
NAMES = {'end_bent_1': ('CapDesignEndBentOne', 'End Bent 1 Cap Design.bpad'),
         'end_bent_2': ('CapDesignEndBentTwo', 'End Bent 2 Cap Design.bpad'),
         'pier': ('CapDesignPier', 'Pier Cap Design.bpad')}
KEYWORDS = ['simplified', 'general', 'flange cracked', 'torsion', 'no minimum transverse', 'beyond 0.006', 'clamped at zero',
            'moment floor', 'end-truncated']
PASS, FAIL = '✓ PASS', '⊗ FAIL'
ALL_PASS, FAILURES = '✓ All Checks Pass', '⊗ There are FAILURES'
ALLOWED_FUNCTIONS = {'If', 'And', 'Or', 'Not', 'Min', 'Max', 'Sqrt', 'Abs', 'Round', 'Floor', 'Tan', 'Sin', 'Cos', 'Atan', 'Asin',
                     'PlotLines', 'Ab', 'Db'}
UNIT = r'(?:in|ft|kip|ksi|psi|deg)'
UNIT_POWER = rf'{UNIT}(?:\^\d+)?'
UNIT_PRODUCT = rf'{UNIT_POWER}(?:\*{UNIT_POWER})*'
# a quantity literal such as "0.6 in^2/ft" or "12 kip*in": the only place a unit may be divided or multiplied bare
LITERAL = re.compile(rf'\d[\d.]*\s+{UNIT_PRODUCT}(?:/\(?{UNIT_PRODUCT}\)?)?')
DISPLAY_SUFFIX = re.compile(r'\s+to\s+[A-Za-z][A-Za-z0-9^*/ ()]*$')
CELL_ADDRESS = re.compile(r'^[A-Za-z]{1,3}[0-9]+$')
_journal_names = []


def journal_names():
    """Every top-level key and name of the stable journal (32 MB; loaded once)."""
    if not _journal_names:
        j = Journal.load(JOURNAL)
        _journal_names.append(set(j.order) | {e.get('name') for e in j.elements.values() if e.get('name')})
    return _journal_names[0]


def shape(el):
    """An element reduced to what Blockpad reads: tags, attributes and text, ignoring the indentation between elements."""
    return (el.tag, sorted(el.attrib.items()), (el.text or '').strip(), [shape(c) for c in el], (el.tail or '').strip())


def text_of(el):
    return ''.join(el.itertext())


def unix(data):
    return data.replace(b'\r\n', b'\n')


class CapBpad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        out, cls.built, seen = Path(cls.tmp.name), {}, {}
        mathcad_build = bm.build

        def spy(cap):                                # keep the Mathcad environment the Blockpad build compares with
            text, env = mathcad_build(cap)
            seen['env'] = env
            return text, env

        with mock.patch.object(bc, 'OUT_DIR', out), mock.patch.object(bm, 'build', spy):
            for cap in bm.CAPS:
                sheet, eng, meta, filename, ctx = bc.build_cap(cap, True)
                entry = bc.write_outputs(sheet, eng, meta, filename, ctx, cap)
                name = sheet.name
                cls.built[cap['key']] = dict(
                    name=name, filename=filename, entry=entry, ctx=ctx, menv=seen['env'],
                    data=(out / filename).read_bytes(), fragment=(out / 'fragments' / f'{name}.xml').read_bytes(),
                    sidecar=(out / 'preview' / f'{name}.canvases.json').read_bytes())

    def each(self):
        for cap in bm.CAPS:
            with self.subTest(cap=cap['key']):
                yield (cap, self.built[cap['key']])

    @staticmethod
    def report_of(data):
        return ET.fromstring(data).find('report')

    @staticmethod
    def engine(data, name):
        """A fresh evaluator filled from the dynexp formulas of the written file, as Blockpad would read them."""
        eng = bs.BpEngine(report=name)
        for dyn in ET.fromstring(data).find('report').iter('dynexp'):
            eng.add(dyn.get('formula'))
        eng.all()
        return eng

    @staticmethod
    def expected_checks(ctx):
        """(ratio name, Chk name) of every check of Section 12, with the regions N, P, B expanded."""
        out = []
        for name, rows, _ in bm.dc_checks(bool(ctx.e.value('Skin_required')), ctx.hook is not None):
            if rows == 3:
                out += [(f'{name}_{t}', f'Chk_{name[3:]}_{t}') for t in bm.REGIONS]
            else:
                out.append((name, f'Chk_{name[3:]}'))
        return out

    def test_committed_sheets_equal_a_fresh_build(self):
        for cap, b in self.each():
            committed = (OUT / b['filename']).read_bytes()
            self.assertEqual(committed, b['data'], f'cap_bpad/{b["filename"]} is stale: {HOW}')
            fragment = OUT / 'fragments' / f'{b["name"]}.xml'
            self.assertEqual(unix(fragment.read_bytes()), unix(b['fragment']), f'{fragment.name} is stale: {HOW}')
            sidecar = OUT / 'preview' / f'{b["name"]}.canvases.json'
            self.assertEqual(unix(sidecar.read_bytes()), unix(b['sidecar']), f'{sidecar.name} is stale: {HOW}')
            # the fragment is the report element of the document; it is indented as a root, so compare the trees
            journal = Journal(b['data'])
            part = ET.fromstring(journal.part(f'report:{b["name"]}'))
            self.assertEqual(shape(part), shape(ET.fromstring(b['fragment'])), f'{fragment.name} differs from the report in the document')
            self.assertEqual(shape(part), shape(ET.fromstring(fragment.read_bytes())), f'{fragment.name} is stale: {HOW}')
        listed = {e['report_name']: e for e in json.loads((OUT / 'verification.json').read_text(encoding='utf-8'))}
        self.assertEqual(sorted(listed), sorted(n for n, _ in NAMES.values()))
        for cap, b in self.each():
            self.assertEqual(listed[b['name']], b['entry'], f'cap_bpad/verification.json is stale: {HOW}')

    def test_each_build_is_tied_to_its_latest_report(self):
        for cap, b in self.each():
            folder = ROOT / cap['reports']
            name = b['entry']['report_file']
            self.assertTrue((folder / name).is_file(), f'{name} is not in {cap["reports"]}')
            link = bm.report_link(cap, b['ctx'].e)
            self.assertEqual(link['file'], name)
            html = (folder / name).read_bytes().decode('utf-8', errors='replace')
            printed_case = re.search(r'Case SHA-256 \(canonical JSON\):\s*([0-9a-f]{64})', html).group(1)
            printed_formula = re.search(r'Formula definition SHA-256:\s*([0-9a-f]{64})', html).group(1)
            self.assertEqual((printed_case, printed_formula), (bm.case_sha256(b['ctx'].e), bm.formula_sha256()))
            self.assertEqual((b['entry']['case_sha256'], b['entry']['formula_sha256']), (printed_case, printed_formula))
            dated = [tuple(map(int, d.groups())) for p in folder.glob('*Cap Design*.html')
                     for d in [re.search(r'(\d{1,2})-(\d{1,2})\.html$', p.name)] if d]
            self.assertEqual(max(dated), tuple(map(int, re.search(r'(\d{1,2})-(\d{1,2})\.html$', name).groups())),
                             f'a newer report than {name} exists but does not match the case: export it again, then {HOW}')
            paragraphs = [text_of(p) for p in self.report_of(b['data']).iter('paragraph')]
            self.assertTrue(any(name in t and link['case_sha'][:12] in t for t in paragraphs),
                            'the provenance paragraph does not name the report and the case hash')

    def test_verification_was_substantial_and_reached_every_branch(self):
        listed = sorted(bm.branches_reached([]))
        for word in KEYWORDS:
            self.assertTrue(any(word in b for b in listed), f'no listed branch mentions {word!r}')
        for cap, b in self.each():
            entry, e = b['entry'], b['ctx'].e
            self.assertGreaterEqual(entry['tool_comparisons'], 800)
            self.assertEqual(entry['tool_comparisons'], entry['sheet_comparisons'] + entry['coverage_comparisons'])
            self.assertGreaterEqual(entry['mathcad_values_compared'], 500)
            self.assertEqual(entry['branches_reached'], listed)
            rows = bm.governing_stations(e)
            cover = [r for _, r in bm.coverage_stations(e, rows) + bm.synthetic_stations(e, scheduled_bars(e.case))]
            missed = [n for n, hit in bm.branches_reached(rows + cover).items() if not hit]
            self.assertEqual(missed, [], 'branches no verified row reaches')

    def test_a_wrong_station_equation_is_caught(self):
        groups, changed = bm.station_equation_groups, []

        def wrong():
            out = groups()
            for _, items in out:
                for i, item in enumerate(items):
                    if item.name == 'V_c':
                        bad = copy.copy(item)
                        bad.expr = item.expr.replace('0.0316', '0.0317')
                        bad.tree = mathcad_sheet.parse(bad.expr)
                        items[i] = bad
                        changed.append(item.name)
            return out

        with mock.patch.object(bm, 'station_equation_groups', wrong):
            with self.assertRaisesRegex(AssertionError, 'differ from the tool'):
                bc.build_cap(bm.CAPS[0], mathcad_compare=False)
        self.assertEqual(changed, ['V_c'] * len(changed))
        self.assertTrue(changed)
        self.assertIs(bm.station_equation_groups, groups)

    def test_xml_is_native_and_journal_compatible(self):
        taken = journal_names()
        for cap, b in self.each():
            key = f'report:{b["name"]}'
            self.assertEqual((b['name'], b['filename']), NAMES[cap['key']])
            # The journal holds these names only once T012 is promoted; then the journal edition owns the comparison.
            self.assertEqual(b['name'] in taken, key in taken)
            self.assertIsNone(CELL_ADDRESS.match(b['name']), 'a report name that looks like a cell address')
            for source, data in (('fresh build', b['data']), ('committed file', (OUT / b['filename']).read_bytes())):
                with self.subTest(source=source):
                    self.assertNotIn(b'<!--', data)
                    root = ET.fromstring(data)
                    self.assertEqual((root.tag, root.get('version')), ('document', '1.9'))
                    journal = Journal(data)
                    self.assertEqual([k for k in journal.order if k.startswith('report:')], [key])
                    self.assertEqual(journal.order[-1], key)
                    rep = root.find('report')
                    self.assertEqual(rep.get('name'), b['name'])
                    # no XML comments anywhere (ElementTree drops them unless asked to keep them)
                    kept = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
                    kept.feed(data)
                    self.assertFalse([el for el in kept.close().iter() if not isinstance(el.tag, str)])
                    for el in rep.iter():
                        formula = el.get('formula')
                        if formula:
                            self.check_formula(formula)
                    for p in rep.iter('paragraph'):             # indentation between elements is not paragraph text
                        pieces = [p.text] + [x for node in p.iter() for x in ((node.text,) if node is p else (node.text, node.tail))]
                        self.assertFalse([x for x in pieces if x and x.strip() and re.search(r'[\r\n]', x)],
                                         f'a paragraph holds a newline: {text_of(p)[:60]!r}')

    def check_formula(self, formula):
        self.assertNotRegex(formula, r'[\r\n]')
        bare = re.sub(r'"[^"]*"', '""', formula)
        self.assertIsNone(re.search(r'(?<![\w.])\d+(?:\.\d+)?[eE][+-]?\d+', bare), f'exponent notation in {formula!r}')   # a number, not a name
        bare = LITERAL.sub('0', DISPLAY_SUFFIX.sub('', bare))
        self.assertIsNone(re.search(rf'/\s*{UNIT}\b', bare), f'bare-unit division in {formula!r}')
        self.assertIsNone(re.search(rf'\*\s*{UNIT}\b', bare), f'bare-unit multiplication in {formula!r}')
        lhs = re.match(r'\s*([^\s=()"]+)\(', formula)               # a user function defined by this formula, e.g. Ab(k) = ...
        for fn in re.findall(r'(?<![\w.])([^\W\d][\w.]*)\(', bare):
            fn = fn.split('.')[-1]
            self.assertTrue(fn in ALLOWED_FUNCTIONS or (lhs and lhs.group(1) == fn), f'function {fn} in {formula!r}')

    def test_summary_checks_agree_with_the_mathcad_sheet(self):
        for cap, b in self.each():
            name, ctx, menv = b['name'], b['ctx'], b['menv']
            eng = self.engine(b['data'], name)
            expected = self.expected_checks(ctx)
            items = bm.dc_chart_items(menv, cap)
            self.assertEqual(len(items), len(expected))
            # Status
            status = eng.get('Status')
            self.assertIn(status, (ALL_PASS, FAILURES))
            self.assertEqual(status == ALL_PASS, menv['Status'] == 'PASS')
            self.assertEqual(status, b['entry']['status'])
            # the failing Chk names are the Mathcad ratios over 1
            chk = {n for n in eng.defs if n.startswith('Chk_')}
            self.assertEqual(chk, {c for _, c in expected})
            self.assertTrue(all(eng.get(n) in (PASS, FAIL) for n in chk))
            failing = {n for n in chk if eng.get(n) == FAIL}
            self.assertEqual(failing, {c for (_, c), (_, _, over) in zip(expected, items) if over})
            self.assertEqual(status == FAILURES, bool(failing))
            for (dc, _), (_, value, _) in zip(expected, items):
                self.assertAlmostEqual(eng.get(dc).v, value, delta=1e-9 * max(abs(value), 1e-6))
            # Figure 3: one blue and one red stem per check, in order
            canvas = next(c for c in self.report_of(b['data']).iter('canvas') if c.get('name') == 'DCChart')
            stems = {bs.BLUE: [], bs.RED: []}
            for plot in canvas.iter('plot'):
                m = re.search(r'If\((\S+) (<=|>) 1,', plot.get('formula'))
                if m:
                    want = bs.BLUE if m.group(2) == '<=' else bs.RED
                    self.assertEqual(plot.get('linecolor'), want)
                    self.assertTrue(m.group(1).startswith(name + '.'), f'{m.group(1)} is not qualified with {name}')
                    stems[want].append(m.group(1)[len(name) + 1:])
            self.assertEqual(stems[bs.BLUE], [dc for dc, _ in expected])
            self.assertEqual(stems[bs.RED], [dc for dc, _ in expected])
            ratios = [eng.get(dc).v for dc, _ in expected]
            self.assertGreaterEqual(eng.get('DC_ymax').v, max(1.2, 1.1 * max(ratios)) - 1e-12)

    def test_preview_sidecar_matches_the_canvases(self):
        for cap, b in self.each():
            sidecar = json.loads(b['sidecar'].decode('utf-8'))
            canvases = list(self.report_of(b['data']).iter('canvas'))
            self.assertEqual(len(canvases), 3)                       # Figure 1, Figure 2, Figure 3
            self.assertEqual(sorted(sidecar), sorted(c.get('name') for c in canvases))
            for canvas in canvases:
                entry = sidecar[canvas.get('name')]
                width, height = (float(v) for v in re.match(r'([\d.]+) in; ([\d.]+) in', canvas.get('size')).groups())
                self.assertEqual((entry['width_in'], entry['height_in']), (width, height))
                self.assertEqual(entry['title'], canvas.get('title'))
                self.assertTrue(entry['items'], f'{canvas.get("name")} has no preview items')


JOURNAL_OUT = OUT / 'journal'
BG = 'BridgeGeometry_2Beam'
EXPECTED_REFERENCES = {                       # Section 2 order: input, owner (the reference mapping of the journal edition)
    'CapDesignEndBentOne': [('b', f'{BG}.EndBentCap_width'), ('h', f'{BG}.EndBentCap_depth'), ('C_t', f'{BG}.EndBent_coverTop'),
                            ('C_b', f'{BG}.EndBent_coverBottom'), ('C_s', f'{BG}.EndBent_coverSide'), ('fc', 'FBMPEndBent.EBSteel_fc'),
                            ('fy', 'FBMPEndBent.EBSteel_fy'), ('Es', 'FBMPEndBent.EBSteel_Es'), ('φ_f', 'CapDesignBasis.φ_f'),
                            ('φ_v', 'CapDesignBasis.φ_v'), ('γ_e', 'CapDesignBasis.γ_e'), ('λ', 'CapDesignBasis.λ'),
                            ('φ_a', 'CapDesignBasis.φ_a'), ('s_proj', 'CapDesignBasis.s_proj')],
    'CapDesignPier': [('b', f'{BG}.PierCap_width'), ('h', f'{BG}.PierCap_ht'), ('C_t', 'PierCapDesign.C_t'), ('C_b', 'PierCapDesign.C_b'),
                      ('C_s', 'PierCapDesign.C_s'), ('fc', 'PierCapDesign.fc'), ('fy', 'PierCapDesign.fy'), ('Es', 'PierCapDesign.Es'),
                      ('φ_f', 'CapDesignBasis.φ_f'), ('φ_v', 'CapDesignBasis.φ_v'), ('γ_e', 'CapDesignBasis.γ_e'),
                      ('λ', 'CapDesignBasis.λ'), ('φ_a', 'CapDesignBasis.φ_a'), ('L_cap', f'{BG}.PierCap_length'),
                      ('s_proj', 'CapDesignBasis.s_proj')],
}
EXPECTED_REFERENCES['CapDesignEndBentTwo'] = EXPECTED_REFERENCES['CapDesignEndBentOne']
ROW_KEYS = ['input', 'owner', 'journal_value', 'case_value', 'status', 'note']
REVIEW = 'Cap Design - Journal Edition (review).bpad'
BASIS_USES = re.compile(r'CapDesignBasis\.(\w+)')


class CapBpadJournal(unittest.TestCase):
    """The journal edition: shared inputs are live references, a coherence gate compares them with the cap case."""

    @classmethod
    def setUpClass(cls):
        if not JOURNAL.is_file():
            raise unittest.SkipTest('journal/D2_I95_Project_Journal.bpad is not in this checkout')
        cls.links = bs.JournalLinks.load(JOURNAL)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        out, results, cls.built = Path(cls.tmp.name), [], {}
        with mock.patch.object(bc, 'OUT_DIR', out):
            for cap in bm.CAPS:
                sheet, eng, meta, filename, ctx = bc.build_cap(cap, True, journal=cls.links)
                results.append((sheet, eng, meta, filename, ctx, cap))
                cls.built[cap['key']] = dict(name=sheet.name, sheet=sheet, meta=meta, ctx=ctx)
            bc.write_journal_outputs(cls.links, results)
        cls.fresh = out / 'journal'
        cls.committed = JOURNAL_OUT

    def reports(self):
        for cap in bm.CAPS:
            with self.subTest(cap=cap['key']):
                yield cap, self.built[cap['key']]

    @staticmethod
    def formulas(rep):
        return [el.get('formula') for el in rep.iter() if el.get('formula')]

    @staticmethod
    def definitions(rep):
        out = {}
        for dyn in rep.iter('dynexp'):
            lhs, rhs = bs.split_definition(dyn.get('formula'))
            out[lhs] = rhs
        return out

    def fragment(self, name, folder=None):
        return ET.fromstring(((folder or self.committed) / f'{name}.xml').read_bytes())

    def test_committed_journal_edition_equals_a_fresh_build(self):
        names = sorted(p.relative_to(self.fresh).as_posix() for p in self.fresh.rglob('*') if p.is_file())
        self.assertEqual(names, sorted(['CapDesignBasis.xml', 'CapDesignEndBentOne.xml', 'CapDesignEndBentTwo.xml', 'CapDesignPier.xml',
                                        'coherence.json', 'verification.json', REVIEW, 'preview/CapDesignEndBentOne.canvases.json',
                                        'preview/CapDesignEndBentTwo.canvases.json', 'preview/CapDesignPier.canvases.json']))
        for name in names:
            committed = self.committed / name
            self.assertTrue(committed.is_file(), f'cap_bpad/journal/{name} is missing: {HOW} --journal')
            self.assertEqual(unix(committed.read_bytes()), unix((self.fresh / name).read_bytes()), f'cap_bpad/journal/{name} is stale: {HOW} --journal')

    def test_coherence_rows_are_exactly_the_reference_mapping(self):
        coherence = json.loads((self.committed / 'coherence.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(coherence), sorted(n for n, _ in NAMES.values()))
        incoherent = []
        for cap, b in self.reports():
            rows = coherence[b['name']]
            self.assertTrue(all(list(r) == ROW_KEYS for r in rows))
            expected = EXPECTED_REFERENCES[b['name']]
            by_input = {r['input']: r for r in rows}
            references = [(r['input'], r['owner']) for r in rows if r['status'] == 'reference']
            self.assertEqual(sorted(references), sorted(expected))
            for r in rows:
                if r['status'] == 'reference':
                    self.assertAlmostEqual(r['journal_value'], r['case_value'], delta=1e-9 * abs(r['case_value']))
                    self.assertTrue(r['note'].startswith('shared journal value'))
                else:
                    incoherent.append((b['name'], r['input']))
                    self.assertEqual(r['status'], 'literal_incoherent_journal')
                    self.assertEqual((r['owner'], r['journal_value'], r['case_value']), (f'{BG}.EndBentCap_length', 212.0, 251.0))
                    self.assertIn('235 in cap + two 8 in cheeks', r['note'])
                    self.assertIn('still holds 17 ft 8 in', r['note'])
            if b['name'] == 'CapDesignPier':
                self.assertEqual(by_input['L_cap']['status'], 'reference')
                self.assertEqual((by_input['L_cap']['journal_value'], by_input['b']['journal_value']), (230.0, 48.0))
            self.assertEqual(len(rows), len(expected) + (0 if b['name'] == 'CapDesignPier' else 1))
        self.assertEqual(incoherent, [('CapDesignEndBentOne', 'L_cap'), ('CapDesignEndBentTwo', 'L_cap')])
        for cap, b in self.reports():                                   # the rows the build computed are the rows written
            self.assertEqual(b['meta']['journal']['rows'], coherence[b['name']])

    def test_every_referenced_owner_exists_in_the_journal(self):
        journal = Journal.load(JOURNAL)
        for cap, b in self.reports():
            for row in json.loads((self.committed / 'coherence.json').read_text(encoding='utf-8'))[b['name']]:
                owner, _, name = row['owner'].partition('.')
                if owner == 'CapDesignBasis':
                    continue
                report = journal.elements[f'report:{owner}']
                found = [d for d in report.iter('dynexp') if re.match(rf'\s*{re.escape(name)}\s*=(?!=)', d.get('formula') or '')]
                self.assertTrue(found, f'{row["owner"]} is not defined in the journal')
                self.assertEqual(len(found), 1, f'{row["owner"]} is defined more than once')

    def test_the_basis_report_defines_everything_the_caps_use(self):
        basis = self.fragment('CapDesignBasis')
        defined = {bs.split_definition(d.get('formula'))[0].split('(')[0] for d in basis.iter('dynexp')}
        self.assertEqual(defined, {'φ_f', 'φ_v', 'φ_a', 'γ_e', 'λ', 's_proj', 'Ab', 'Db'})
        used = set()
        for cap, b in self.reports():
            rep = self.fragment(b['name'])
            for formula in self.formulas(rep):
                used.update(BASIS_USES.findall(formula))
        self.assertEqual(used, defined)
        amber = [d.get('style') for d in basis.iter('dynexp') if '(' not in d.get('formula').split('=')[0]]
        self.assertEqual(amber, ['Required Input'] * 6)
        text = ' '.join(text_of(p) for p in basis.iter('paragraph'))
        for word in ('CapDesignEndBentOne', 'CapDesignEndBentTwo', 'CapDesignPier', 'D-003', 'LRFD', 'FDOT Structures Design Guidelines'):
            self.assertIn(word, text)
        self.assertNotIn('Review copy', text)                          # the banner is in the review document only

    def test_cap_reports_have_no_local_bar_tables_and_no_literals_for_references(self):
        for cap, b in self.reports():
            rep = self.fragment(b['name'])
            defs = self.definitions(rep)
            self.assertFalse([d for d in defs if d.split('(')[0] in ('Ab', 'Db')])
            for formula in self.formulas(rep):
                self.assertIsNone(re.search(r'(?<![\w.])(Ab|Db)\(', formula), f'unqualified bar table call in {formula!r}')
            for name, owner in EXPECTED_REFERENCES[b['name']]:
                self.assertRegex(defs[name], rf'^{re.escape(owner)}( to (in|ksi))?$', f'{name} is not a reference')
                self.assertNotRegex(defs[name], r'^[\d.]+')
            if b['name'] != 'CapDesignPier':
                self.assertEqual(defs['L_cap'], '251 in')
            for formula in self.formulas(rep):
                self.check_formula(formula)
            self.assertIn('Shared geometry, materials and factors are live references to the journal; the owner is named beside each.',
                          [text_of(p) for p in rep.iter('paragraph')])

    check_formula = CapBpad.check_formula

    def test_a_journal_value_that_disagrees_stops_the_build(self):
        links = bs.JournalLinks.load(JOURNAL)
        links.override(f'{BG}.EndBentCap_width', bs.Q(43, (1., 0., 0.)))
        with self.assertRaisesRegex(bc.BuildError, 'EndBentCap_width') as caught:
            bc.build_cap(bm.CAPS[0], mathcad_compare=False, journal=links)
        message = str(caught.exception)
        self.assertIn('42', message)
        self.assertIn('43', message)
        self.assertIn('End Bent 1', message)
        # the pier does not read that name
        links = bs.JournalLinks.load(JOURNAL)
        links.override('PierCapDesign.fc', bs.Q(6, (-2., 1., 0.)))
        with self.assertRaisesRegex(bc.BuildError, 'PierCapDesign.fc'):
            bc.build_cap(bm.CAPS[2], mathcad_compare=False, journal=links)

    def test_a_kept_literal_that_now_agrees_must_become_a_reference(self):
        links = bs.JournalLinks.load(JOURNAL)
        links.override(f'{BG}.EndBentCap_length', bs.Q(251, (1., 0., 0.)))
        with self.assertRaisesRegex(bc.BuildError, 'KEEP_LITERAL'):
            bc.build_cap(bm.CAPS[0], mathcad_compare=False, journal=links)

    def test_a_basis_factor_that_disagrees_with_the_case_stops_the_build(self):
        links = bs.JournalLinks.load(JOURNAL)
        changed = [(mc, 0.85 if mc == 'phi_f' else v, u, c) for mc, v, u, c in bc.BASIS_CONSTANTS]
        with mock.patch.object(bc, 'BASIS_CONSTANTS', changed):
            with self.assertRaisesRegex(bc.BuildError, 'φ_f'):
                bc.build_cap(bm.CAPS[0], mathcad_compare=False, journal=links)

    def test_tool_comparisons_equal_the_standalone_edition(self):
        standalone = {e['report_name']: e for e in json.loads((OUT / 'verification.json').read_text(encoding='utf-8'))}
        listed = json.loads((self.committed / 'verification.json').read_text(encoding='utf-8'))
        self.assertEqual([e['report_name'] for e in listed['reports']], [n for n, _ in NAMES.values()])
        for cap, b in self.reports():
            mine, theirs = b['meta'], standalone[b['name']]
            self.assertEqual((mine['comparisons'], mine['shown'], mine['coverage'], mine['coverage_real'], mine['coverage_synthetic'],
                              mine['mathcad_values'], mine['status'], mine['branches']),
                             (theirs['tool_comparisons'], theirs['sheet_comparisons'], theirs['coverage_comparisons'],
                              theirs['coverage_rows_real'], theirs['coverage_rows_synthetic'], theirs['mathcad_values_compared'],
                              theirs['status'], theirs['branches_reached']))
            entry = next(e for e in listed['reports'] if e['report_name'] == b['name'])
            for key in ('tool_comparisons', 'sheet_comparisons', 'coverage_comparisons', 'mathcad_values_compared', 'status', 'case_sha256'):
                self.assertEqual(entry[key], theirs[key], key)
            self.assertEqual(entry['functions'], 0)                    # the bar tables are read from CapDesignBasis
        self.assertEqual(listed['basis']['functions'], ['Ab', 'Db'])
        self.assertEqual(listed['basis']['read_by'], [n for n, _ in NAMES.values()])

    def test_review_document_and_fragments_are_journal_compatible(self):
        taken = journal_names()
        data = (self.committed / REVIEW).read_bytes()
        self.assertNotIn(b'<!--', data)
        journal = Journal(data)
        self.assertEqual([k for k in journal.order if k.startswith('report:')],
                         ['report:CapDesignBasis'] + [f'report:{n}' for n, _ in NAMES.values()])
        root = ET.fromstring(data)
        basis_text = ' '.join(text_of(p) for p in root.find('report').iter('paragraph'))
        self.assertIn('Review copy', basis_text)
        self.assertIn('BridgeGeometry_2Beam, FBMPEndBent and PierCapDesign', basis_text)
        for report in root.findall('report')[1:]:
            self.assertNotIn('Review copy', ' '.join(text_of(p) for p in report.iter('paragraph')))
        for name in ['CapDesignBasis'] + [n for n, _ in NAMES.values()]:
            fragment = self.committed / f'{name}.xml'
            part = ET.fromstring(Journal(data).part(f'report:{name}'))
            fragment_tree = ET.fromstring(fragment.read_bytes())
            self.assertEqual(fragment_tree.get('name'), name)
            if name != 'CapDesignBasis':
                self.assertEqual(shape(part), shape(fragment_tree), f'{fragment.name} differs from the review document')
            self.assertNotIn(b'<!--', fragment.read_bytes())
            # Tied to the report by the case and formula hashes only: a pier_cap edit must not force a journal task.
            self.assertNotIn(b'cap notebook package', fragment.read_bytes())
            if name in taken:                 # promoted (T012): the journal's report must be the committed fragment
                journal_part = Journal.load(JOURNAL).part(f'report:{name}')
                self.assertEqual(shape(ET.fromstring(journal_part)), shape(fragment_tree),
                                 f'journal report {name} differs from {fragment.name}: rebuild and promote a new task')

    def test_json_sidecars_match_the_canvases(self):
        for cap, b in self.reports():
            sidecar = json.loads((self.committed / 'preview' / f'{b["name"]}.canvases.json').read_text(encoding='utf-8'))
            canvases = list(self.fragment(b['name']).iter('canvas'))
            self.assertEqual(sorted(sidecar), sorted(c.get('name') for c in canvases))


if __name__ == '__main__':
    unittest.main()
