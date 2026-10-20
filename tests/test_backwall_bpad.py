"""The distilled backwall Blockpad document (end_bent_walls/End Bent Backwall Design.bpad) is current, verified and journal-ready."""
import copy
import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from end_bent_walls.model import INPUTS, edit_input, evaluate
from scripts import bpad_sheet as bs
from scripts import build_backwall_bpad as bb
from scripts import build_backwall_mathcad as bm
from scripts import mathcad_sheet
from tools.bpad_workflow import Journal

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'end_bent_walls'
SIDE = OUT / 'bpad'
JOURNAL = ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
HOW = 'run python scripts/build_backwall_bpad.py after changing the notebook, the formulas or the generator'
NAME, FILENAME = 'EndBentBackwallDesign', 'End Bent Backwall Design.bpad'
PASS, FAIL = '✓ PASS', '⊗ FAIL'
ALL_PASS, FAILURES = '✓ All Checks Pass', '⊗ There are FAILURES'
ALLOWED_FUNCTIONS = {'If', 'And', 'Or', 'Not', 'Min', 'Max', 'Sqrt', 'Abs', 'Round', 'Floor', 'Tan', 'Sin', 'Cos', 'Atan', 'Asin',
                     'PlotLines', 'Ab', 'Db', 'L_core', 'L_w', 'N_b', 'N_c', 'T_c_STRI', 'T_c_STRIII1', 'T_c_STRIII2', 'T_c_STRIV'}
UNIT = r'(?:in|ft|kip|ksi|psi|deg)'
UNIT_POWER = rf'{UNIT}(?:\^\d+)?'
UNIT_PRODUCT = rf'{UNIT_POWER}(?:\*{UNIT_POWER})*'
# a quantity literal such as "0.6 in^2/ft" or "12 kip*in": the only place a unit may be divided or multiplied bare
LITERAL = re.compile(rf'\d[\d.]*\s+{UNIT_PRODUCT}(?:/\(?{UNIT_PRODUCT}\)?)?')
DISPLAY_SUFFIX = re.compile(r'\s+to\s+[A-Za-z][A-Za-z0-9^*/ ()]*$')
CELL_ADDRESS = re.compile(r'^[A-Za-z]{1,3}[0-9]+$')
MEMBERS = ('FF', 'SF', 'CK')
# Summary check -> the notebook check keys whose largest ratio it holds
NOTEBOOK_KEYS = {
    'V_bw': ('shear_bw',), 'Vi_bw': ('interface_bw',), 'Avf': ('interface_min_bw',), 'ts_v': ('ts_vert',), 'ts_h': ('ts_horiz',),
    'V_ck': ('shear_CK',), 'Vi_ck': ('interface_CK',), 'ts_ck': ('ts_CK',), 'cov': ('cover_bw', 'cover_CK'),
    'thk': ('thickness_bw', 'thickness_CK'), 'strap': ('strap_height',), 'T': ('cap_torsion',),
}
MEMBER_KEYS = {'flex': 'flex', 'min': 'min', 'eps': 'strain', 'crk': 'crack', 'sp': 'spacing'}
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


def engine_of(data):
    """A fresh evaluator filled from the dynexp formulas of the written file, as Blockpad would read them."""
    eng = bs.BpEngine(report=NAME)
    for dyn in ET.fromstring(data).find('report').iter('dynexp'):
        eng.add(dyn.get('formula'))
    eng.all()
    return eng


class BackwallBpad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        out = Path(cls.tmp.name)
        seen = {}
        verify = bm.verify

        def spy(blocks, e, tol=1e-9):                    # keep the Mathcad environment the Blockpad build compares with
            seen['env'] = verify(blocks, e, tol)
            return seen['env']

        with mock.patch.object(bm, 'verify', spy):
            cls.sheet, cls.eng, cls.meta = bb.build()
        cls.entry = bb.write_outputs(cls.sheet, cls.eng, cls.meta, out_dir=out, side_dir=out / 'bpad')
        cls.menv = seen['env']
        cls.e = evaluate()
        cls.data = (out / FILENAME).read_bytes()
        cls.fragment = (out / 'bpad' / 'fragments' / f'{NAME}.xml').read_bytes()
        cls.sidecar = (out / 'bpad' / 'preview' / f'{NAME}.canvases.json').read_bytes()
        cls.verification = (out / 'bpad' / 'verification.json').read_bytes()

    @staticmethod
    def report_of(data):
        return ET.fromstring(data).find('report')

    def test_committed_files_equal_a_fresh_build(self):
        committed = (OUT / FILENAME).read_bytes()
        self.assertEqual(committed, self.data, f'end_bent_walls/{FILENAME} is stale: {HOW}')
        fragment = SIDE / 'fragments' / f'{NAME}.xml'
        self.assertEqual(unix(fragment.read_bytes()), unix(self.fragment), f'{fragment.name} is stale: {HOW}')
        sidecar = SIDE / 'preview' / f'{NAME}.canvases.json'
        self.assertEqual(unix(sidecar.read_bytes()), unix(self.sidecar), f'{sidecar.name} is stale: {HOW}')
        # the fragment is the report element of the document; it is indented as a root, so compare the trees
        journal = Journal(self.data)
        part = ET.fromstring(journal.part(f'report:{NAME}'))
        self.assertEqual(shape(part), shape(ET.fromstring(self.fragment)), f'{fragment.name} differs from the report in the document')
        self.assertEqual(shape(part), shape(ET.fromstring(fragment.read_bytes())), f'{fragment.name} is stale: {HOW}')
        listed = json.loads((SIDE / 'verification.json').read_text(encoding='utf-8'))
        mine = [dict(self.entry, bpad_file=f'end_bent_walls/{FILENAME}')]
        self.assertEqual(listed, mine, f'end_bent_walls/bpad/verification.json is stale: {HOW}')
        self.assertEqual(json.loads(self.verification.decode('utf-8')), json.loads(json.dumps([self.entry])))
        self.assertEqual(self.entry['bpad_sha256'], bb.hashlib.sha256(committed).hexdigest())

    def test_the_build_is_tied_to_the_notebook_case(self):
        paragraphs = [text_of(p) for p in self.report_of(self.data).iter('paragraph')]
        self.assertTrue(any(self.meta['case_sha256'] in t and self.meta['revision'] in t for t in paragraphs),
                        'the provenance paragraph does not name the package revision and the case hash')
        self.assertEqual(self.meta['case_sha256'], bb.hashlib.sha256(
            json.dumps(self.e.case, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
        self.assertEqual(self.meta['revision'], bm.notebook_revision())

    def test_verification_was_substantial(self):
        self.assertGreaterEqual(self.entry['tool_comparisons'], 240)
        self.assertGreaterEqual(self.entry['mathcad_values_compared'], 200)
        self.assertEqual(self.entry['report_name'], NAME)
        self.assertEqual(self.entry['status'], self.eng.get('Status'))
        self.assertGreater(self.entry['definitions'], 400)
        self.assertEqual(self.entry['functions'], 10)

    def test_a_wrong_equation_is_caught(self):
        original, changed = bm.sheet, []

        def wrong(rev):
            blocks = original(rev)
            for blk in blocks:
                if blk.kind in ('eqs', 'row'):
                    for i, item in enumerate(blk.payload):
                        if item.name == 'V_c':
                            bad = copy.copy(item)
                            bad.expr = item.expr.replace('0.0316', '0.0317')
                            bad.tree = mathcad_sheet.parse(bad.expr)
                            blk.payload[i] = bad
                            changed.append(item.name)
            return blocks

        with mock.patch.object(bm, 'sheet', wrong):
            with self.assertRaisesRegex(AssertionError, 'differ'):
                bb.build(mathcad_compare=False)
        self.assertEqual(changed, ['V_c'])
        self.assertIs(bm.sheet, original)

    def test_xml_is_native_and_journal_compatible(self):
        taken = journal_names()
        key = f'report:{NAME}'
        # The journal holds this name only once T017 is promoted; then the journal edition (not the standalone sheet) owns it.
        self.assertEqual(NAME in taken, key in taken)
        if key in taken:
            journal = Journal.load(JOURNAL)
            edition = ET.fromstring((SIDE / 'journal' / f'{NAME}.xml').read_bytes())
            self.assertEqual(shape(ET.fromstring(journal.part(key))), shape(edition),
                             'the journal holds a different EndBentBackwallDesign than end_bent_walls/bpad/journal/: prepare a journal task')
        self.assertIsNone(CELL_ADDRESS.match(NAME), 'a report name that looks like a cell address')
        for source, data in (('fresh build', self.data), ('committed file', (OUT / FILENAME).read_bytes())):
            with self.subTest(source=source):
                self.assertNotIn(b'<!--', data)
                root = ET.fromstring(data)
                self.assertEqual((root.tag, root.get('version')), ('document', '1.9'))
                self.assertEqual(len(root.findall('report')), 1)
                journal = Journal(data)
                self.assertEqual([k for k in journal.order if k.startswith('report:')], [key])
                self.assertEqual(journal.order[-1], key)
                rep = root.find('report')
                self.assertEqual(rep.get('name'), NAME)
                self.assertEqual(rep.get('title'), bb.TITLE)
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
        names = [el.get('name') for el in self.report_of(self.data).iter() if el.tag in ('table', 'canvas', 'textcell', 'section')]
        self.assertEqual(len(names), len(set(names)))
        eng = engine_of(self.data)
        for name in set(eng.defs) | set(eng.functions):
            self.assertIsNone(CELL_ADDRESS.match(name), f'{name} looks like a cell address')
            self.assertNotIn(name, names)

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

    def test_every_amber_input_equals_the_notebook_input(self):
        eng = engine_of(self.data)
        seen = {}
        by_bp = {bs.bp_name(n): n for n in INPUTS}
        for dyn in self.report_of(self.data).iter('dynexp'):
            if dyn.get('style') != 'Required Input':
                continue
            lhs, _ = bs.split_definition(dyn.get('formula'))
            if lhs not in by_bp:
                self.assertTrue(lhs.startswith('γ_'), f'unexpected amber definition {lhs}')   # the load factor table
                continue
            name = by_bp[lhs]
            spec = INPUTS[name]
            unit = None if spec['unit'] in (None, 'bar') else spec['unit']
            q = eng.get(lhs)
            if unit is None:
                self.assertEqual(q.d, bs.NODIM)
                mine = q.v
            else:
                u = eng.unit_q(bs.bp_unit(unit))
                q.same(u)
                mine = q.v / u.v
            want = float(self.e.case['inputs'][name])
            self.assertAlmostEqual(mine, want, delta=1e-12 * max(abs(want), 1e-12), msg=name)
            seen[name] = mine
        self.assertEqual(set(INPUTS) - set(seen), {'N_pile', 'S_pile', 'D_pile'})
        # the load factors are the notebook's combination table
        from end_bent_walls.model import COMBINATIONS
        for tag, combo in zip(bb.KEYS, COMBINATIONS):
            self.assertEqual(eng.get(f'γ_EH_{tag}').v, combo['EH'][0])
            self.assertEqual(eng.get(f'γ_DCmax_{tag}').v, combo['DC'][0])
            self.assertEqual(eng.get(f'γ_DCmin_{tag}').v, combo['DC'][1])
            self.assertEqual(eng.get(f'γ_LS_{tag}').v, combo['LS'])
            self.assertEqual(eng.get(f'γ_PL_{tag}').v, combo['PL'])
            self.assertEqual(eng.get(f'γ_TU_{tag}').v, combo['TU'])

    def expected_checks(self):
        """(ratio name, Chk name, notebook keys) of every check of Section 12, in order."""
        out = []
        for base, key in MEMBER_KEYS.items():
            for m in MEMBERS:
                out.append((f'DC_{base}_{m}', f'Chk_{base}_{m}', (f'{key}_{m}',)))
        for base, keys in NOTEBOOK_KEYS.items():
            out.append((f'DC_{base}', f'Chk_{base}', keys))
        return out

    def test_summary_checks_agree_with_the_notebook(self):
        eng = engine_of(self.data)
        ratio = {c.key: c.ratio for c in self.e.checks}
        expected = self.expected_checks()
        self.assertEqual(len(expected), 27)
        status = eng.get('Status')
        self.assertIn(status, (ALL_PASS, FAILURES))
        self.assertEqual(status == ALL_PASS, self.menv['Status'] == 'PASS')
        self.assertEqual(status, self.entry['status'])
        self.assertEqual(status == ALL_PASS, not [c for c in self.e.checks if 'FAIL' in c.status])
        chk = {n for n in eng.defs if n.startswith('Chk_')}
        self.assertEqual(chk, {c for _, c, _ in expected})
        self.assertTrue(all(eng.get(n) in (PASS, FAIL) for n in chk))
        failing = set()
        for dc, name, keys in expected:
            want = max(ratio[k] for k in keys)
            self.assertAlmostEqual(eng.get(dc).v, want, delta=1e-9 * max(abs(want), 1e-6), msg=dc)
            if want > 1 + 1e-9:
                failing.add(name)
        self.assertEqual({n for n in chk if eng.get(n) == FAIL}, failing)
        self.assertEqual(status == FAILURES, bool(failing))
        # the summary table lists every check, with its result, and the overall row
        table = next(t for t in self.report_of(self.data).iter('table') if t.get('name') == 'Summary')
        formulas = [c.get('formula') for c in table.iter('c') if c.get('formula')]
        self.assertEqual(formulas, [x for dc, name, _ in expected for x in (dc, name)] + ['DC_max', 'Status'])
        # Figure 3: one blue and one red stem per check, in order
        canvas = next(c for c in self.report_of(self.data).iter('canvas') if c.get('name') == 'DCChart')
        stems = {bs.BLUE: [], bs.RED: []}
        for plot in canvas.iter('plot'):
            m = re.search(r'If\((\S+) (<=|>) 1,', plot.get('formula'))
            if m:
                want = bs.BLUE if m.group(2) == '<=' else bs.RED
                self.assertEqual(plot.get('linecolor'), want)
                self.assertTrue(m.group(1).startswith(NAME + '.'), f'{m.group(1)} is not qualified with {NAME}')
                stems[want].append(m.group(1)[len(NAME) + 1:])
        self.assertEqual(stems[bs.BLUE], [dc for dc, _, _ in expected])
        self.assertEqual(stems[bs.RED], [dc for dc, _, _ in expected])
        ratios = [eng.get(dc).v for dc, _, _ in expected]
        self.assertGreaterEqual(eng.get('DC_ymax').v, max(1.2, 1.1 * max(ratios)) - 1e-12)

    def test_preview_sidecar_matches_the_canvases(self):
        sidecar = json.loads(self.sidecar.decode('utf-8'))
        canvases = list(self.report_of(self.data).iter('canvas'))
        self.assertEqual(len(canvases), 3)                       # Figure 1, Figure 2, Figure 3
        self.assertEqual(sorted(sidecar), sorted(c.get('name') for c in canvases))
        for canvas in canvases:
            entry = sidecar[canvas.get('name')]
            width, height = (float(v) for v in re.match(r'([\d.]+) in; ([\d.]+) in', canvas.get('size')).groups())
            self.assertEqual((entry['width_in'], entry['height_in']), (width, height))
            self.assertEqual(entry['title'], canvas.get('title'))
            self.assertTrue(entry['items'], f'{canvas.get("name")} has no preview items')
        # the live dimensions of the figures name the sheet's own definitions
        eng = engine_of(self.data)
        dims = [d for c in canvases for d in c.iter('lineardim')]
        self.assertGreaterEqual(len(dims), 12)
        for d in dims:
            self.assertTrue(d.get('formula').startswith(NAME + '.'))
            eng.evaluate(d.get('formula'))

    def test_distill_follows_a_modified_case(self):
        case = copy.deepcopy(self.e.case)
        edit_input(case, 's_FF', 6.0)
        edit_input(case, 'H_bw', 4.5)
        changed = evaluate(case)
        data, vjson = bb.distill(changed)
        self.assertIsInstance(data, bytes)
        root = ET.fromstring(data)
        self.assertEqual(root.find('report').get('name'), NAME)
        eng = engine_of(data)
        self.assertAlmostEqual(eng.get('s_FF').v, 6.0, places=12)               # inches
        self.assertAlmostEqual(eng.get('H_bw').v, 4.5 * 12, places=9)
        self.assertNotAlmostEqual(eng.get('s_FF').v, self.eng.get('s_FF').v)
        entry = json.loads(vjson.decode('utf-8'))[0]
        self.assertNotIn('bpad_file', entry)
        self.assertEqual(entry['status'], eng.get('Status'))
        self.assertIsNone(entry['mathcad_values_compared'])
        self.assertGreaterEqual(entry['tool_comparisons'], 240)
        self.assertEqual(entry['case_sha256'], bb.hashlib.sha256(json.dumps(changed.case, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
        self.assertNotEqual(entry['case_sha256'], self.entry['case_sha256'])
        self.assertEqual(entry['package_revision'], 'working copy')
        self.assertEqual(entry['bpad_sha256'], bb.hashlib.sha256(data).hexdigest())
        self.assertTrue(any(bb.NOTEBOOK_PROVENANCE in text_of(p) for p in root.find('report').iter('paragraph')))
        # the status of the modified case follows the notebook's checks
        failed = [c.key for c in changed.checks if 'FAIL' in c.status]
        self.assertEqual(eng.get('Status') == ALL_PASS, not failed)
        # the distilled bytes are the same for the same case, and the file system is untouched by distill
        again, _ = bb.distill(changed)
        self.assertEqual(again, data)


BG = 'BridgeGeometry_2Beam'
JOURNAL_OUT = SIDE / 'journal'
ROW_KEYS = ['input', 'owner', 'journal_value', 'case_value', 'status', 'note']
EXPECTED_REFERENCES = sorted((bs.bp_name(mc), owner) for mc, (owner, _) in bb.JOURNAL_REFS.items())


class BackwallBpadJournal(unittest.TestCase):
    """The journal edition: the inputs the journal owns are live references, a coherence gate compares them with the case."""

    @classmethod
    def setUpClass(cls):
        if not JOURNAL.is_file():
            raise unittest.SkipTest('journal/D2_I95_Project_Journal.bpad is not in this checkout')
        cls.links = bs.JournalLinks.load(JOURNAL)
        try:                                      # the owners arrive with journal tasks T014 (Materials, ProjectInfo) and T016 (the drop)
            cls.links.value(f'{BG}.EndBent_backwallDrop')
        except bs.BpError as ex:
            raise unittest.SkipTest(f'journal task T016 (BridgeGeometry_2Beam.EndBent_backwallDrop) is not promoted yet: {ex}') from None
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        out = Path(cls.tmp.name)
        cls.sheet, cls.eng, cls.meta = bb.build(journal=cls.links)
        cls.entry = bb.write_journal_outputs(cls.links, cls.sheet, cls.eng, cls.meta, out_dir=out)
        cls.fresh = out / 'journal'
        cls.e = evaluate()

    def test_committed_journal_edition_equals_a_fresh_build(self):
        names = sorted(p.relative_to(self.fresh).as_posix() for p in self.fresh.rglob('*') if p.is_file())
        self.assertEqual(names, sorted([f'{NAME}.xml', 'coherence.json', 'verification.json', bb.REVIEW_FILE, f'preview/{NAME}.canvases.json']))
        for name in names:
            committed = JOURNAL_OUT / name
            self.assertTrue(committed.is_file(), f'end_bent_walls/bpad/journal/{name} is missing: {HOW} --journal')
            if name == 'verification.json':
                mine = json.loads((self.fresh / name).read_text(encoding='utf-8'))
                theirs = json.loads(committed.read_text(encoding='utf-8'))
                self.assertEqual(theirs[0]['fragment'], f'end_bent_walls/bpad/journal/{NAME}.xml')
                self.assertEqual(theirs[0]['review_document'], f'end_bent_walls/bpad/journal/{bb.REVIEW_FILE}')
                for entry in mine + theirs:                 # the paths depend on where the build was written
                    for key in ('journal_file', 'fragment', 'review_document'):
                        entry.pop(key, None)
                self.assertEqual(theirs, mine, f'end_bent_walls/bpad/journal/{name} is stale: {HOW} --journal')
                continue
            self.assertEqual(unix(committed.read_bytes()), unix((self.fresh / name).read_bytes()),
                             f'end_bent_walls/bpad/journal/{name} is stale: {HOW} --journal')

    def test_coherence_rows_are_the_reference_mapping_plus_the_kept_literal_and_the_drop(self):
        coherence = json.loads((JOURNAL_OUT / 'coherence.json').read_text(encoding='utf-8'))
        self.assertEqual(list(coherence), [NAME])
        rows = coherence[NAME]
        self.assertTrue(all(list(r) == ROW_KEYS for r in rows))
        self.assertEqual(rows, self.meta['journal']['rows'])
        references = sorted((r['input'], r['owner']) for r in rows if r['status'] == 'reference')
        self.assertEqual(references, EXPECTED_REFERENCES)
        self.assertGreaterEqual(len(references), 20)
        for r in rows:
            if r['status'] in ('reference', 'reference_context'):
                self.assertAlmostEqual(r['journal_value'], r['case_value'], delta=1e-9 * max(abs(r['case_value']), 1e-12), msg=r['input'])
                self.assertTrue(r['note'].startswith(bb.REFERENCE_CAPTION))
        kept = [r for r in rows if r['status'] == 'literal_incoherent_journal']
        self.assertEqual([(r['input'], r['owner'], r['journal_value'], r['case_value']) for r in kept],
                         [('s_brg', f'{BG}.Beam_spacing', 103.0, 102.99)])
        drop = [r for r in rows if r['status'] == 'reference_context']
        self.assertEqual([(r['input'], r['owner'], r['journal_value'], r['case_value']) for r in drop],
                         [(bb.DROP_NAME, f'{BG}.EndBent_backwallDrop', 4.25, 4.25)])
        by_input = {r['input']: r for r in rows}
        self.assertEqual((by_input['L_load']['journal_value'], by_input['L_cap']['journal_value'], by_input['fc']['journal_value']), (251.0, 235.0, 5.5))
        self.assertAlmostEqual(by_input['L_exp']['journal_value'], 107.35, places=9)

    def test_every_referenced_owner_is_defined_once_in_the_journal(self):
        journal = Journal.load(JOURNAL)
        for row in json.loads((JOURNAL_OUT / 'coherence.json').read_text(encoding='utf-8'))[NAME]:
            owner, _, name = row['owner'].partition('.')
            report = journal.elements[f'report:{owner}']
            found = [d for d in report.iter('dynexp') if re.match(rf'\s*{re.escape(name)}\s*=(?!=)', d.get('formula') or '')]
            self.assertEqual(len(found), 1, f'{row["owner"]} is not defined exactly once in the journal')

    def test_fragment_holds_live_references_and_the_stamp_and_no_literal_for_them(self):
        rep = ET.fromstring((JOURNAL_OUT / f'{NAME}.xml').read_bytes())
        self.assertEqual((rep.tag, rep.get('name')), ('report', NAME))
        defs = {}
        for dyn in rep.iter('dynexp'):
            lhs, rhs = bs.split_definition(dyn.get('formula'))
            defs[lhs] = (rhs, dyn.get('style'))
        for mc, (owner, unit) in bb.JOURNAL_REFS.items():
            name = bs.bp_name(mc)
            self.assertEqual(defs[name], (owner + (f' to {unit}' if unit else ''), None), name)
        self.assertEqual(defs[bb.DROP_NAME], (f'{BG}.EndBent_backwallDrop to in', None))
        self.assertEqual(defs['s_brg'], ('102.99 in', 'Required Input'))
        amber = {n for n, (_, style) in defs.items() if style == 'Required Input'}
        self.assertFalse(amber & {bs.bp_name(mc) for mc in bb.JOURNAL_REFS})
        first = next(el for el in rep if el.tag not in ('include', 'stylerule'))
        table = first.find('table')
        self.assertEqual((first.tag, table.get('name')), ('embed', 'ProjectStamp'))
        self.assertEqual([owner for _, _, owner in bs.stamp_cells(table)], [f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS])
        self.assertEqual([d.get('formula') for d in table.iter('dynexp')], [f'{bs.STAMP_PREFIX}{k} = {bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS])
        self.assertEqual({c.tag for row in table.findall('row') for c in row}, {'textcell'})
        self.assertFalse(bs.SUBMISSION_FORBIDDEN.search(' '.join(t for _, t in bs.visible_text_elements(rep))), 'working language in the visible text')
        # every qualified reference names one of the three journal owners and resolves in the journal
        owners = {m.group(1) for el in rep.iter() for m in re.finditer(r'(?<![\w.])([A-Za-z_]\w*)\.[A-Za-z_]\w*', el.get('formula') or '')}
        self.assertEqual(owners, {BG, 'Materials', bs.PROJECT_INFO, NAME})
        for el in rep.iter():
            for owner, name in re.findall(r'(?<![\w.])(BridgeGeometry_2Beam|Materials|ProjectInfo)\.([A-Za-z_]\w*)', el.get('formula') or ''):
                self.links.value(f'{owner}.{name}')
        # the standalone sheet is not touched by the journal edition: it still holds the literals
        standalone = ET.fromstring((SIDE / 'fragments' / f'{NAME}.xml').read_bytes())
        literal = {bs.split_definition(d.get('formula'))[0]: d.get('style') for d in standalone.iter('dynexp')}
        self.assertEqual(literal.get('b_cap'), 'Required Input')
        self.assertNotIn(bb.DROP_NAME, literal)

    def test_the_gate_stops_on_a_journal_value_that_differs_from_the_case(self):
        links = bs.JournalLinks.load(JOURNAL)
        links.override(f'{BG}.EndBentCap_width', bs.BpEngine().evaluate('43 in'))
        with self.assertRaisesRegex(bb.BuildError, r'b_cap: the case holds 42 in but the journal owner BridgeGeometry_2Beam\.EndBentCap_width holds 43 in'):
            bb.build(mathcad_compare=False, journal=links)
        links = bs.JournalLinks.load(JOURNAL)
        links.override(f'{BG}.EndBent_backwallDrop', bs.BpEngine().evaluate('4 in'))
        with self.assertRaisesRegex(bb.BuildError, r'drop_bw: the journal .* holds 4 in but the measured CAD model'):
            bb.build(mathcad_compare=False, journal=links)

    def test_journal_values_are_live_in_the_evaluation(self):
        self.assertAlmostEqual(self.eng.get('b_cap').v, 42.0, places=12)                   # inches, from the journal external
        self.assertAlmostEqual(self.eng.get('L_exp').v, 107.35 * 12, places=6)
        self.assertAlmostEqual(self.eng.get(bb.DROP_NAME).v, 4.25, places=12)
        self.assertEqual(self.entry['status'], self.eng.get('Status'))
        self.assertEqual(self.entry['journal_references'], len(bb.JOURNAL_REFS))
        self.assertEqual(self.entry['literals_kept'], ['s_brg'])
        self.assertEqual(self.entry['context_references'], [bb.DROP_NAME])
        self.assertGreaterEqual(self.entry['tool_comparisons'], 240)
        self.assertGreaterEqual(self.entry['mathcad_values_compared'], 200)
        self.assertEqual(self.entry['project_stamp']['owner'], bs.PROJECT_INFO)


if __name__ == '__main__':
    unittest.main()
