"""The three distilled pile Blockpad documents (pile_bpad/*.bpad) are current, tied to the notebook, verified and journal-ready."""
import copy
import hashlib
import json
import math
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest import mock

from pile_design import bpad, exports
from pile_design import mathcad as pm
from pile_design.model import default_case, evaluate, select_psc
from scripts import bpad_sheet as bs
from scripts import build_pile_bpad as cli
from scripts.mathcad_sheet import parse
from tools.bpad_workflow import Journal

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'pile_bpad'
JOURNAL = ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
HOW = 'run python scripts/build_pile_bpad.py after changing the pile_design package, the registered FBMP export or the generator'
NAMES = {'End Bent 1': ('PileDesignEndBentOne', 'End Bent 1 Pile Design.bpad'),
         'End Bent 2': ('PileDesignEndBentTwo', 'End Bent 2 Pile Design.bpad'),
         'Pier': ('PileDesignPier', 'Pier Pile Design.bpad')}
TITLES = {'End Bent 1': 'C011 - End Bent 1 Pile Design', 'End Bent 2': 'C012 - End Bent 2 Pile Design',
          'Pier': 'C013 - Pier Pile Design'}
PASS, FAIL = '✓ PASS', '⊗ FAIL'
ALL_PASS, FAILURES = '✓ All Checks Pass', '⊗ There are FAILURES'
ALLOWED_FUNCTIONS = {'If', 'And', 'Or', 'Not', 'Min', 'Max', 'Sqrt', 'Abs', 'Round', 'Floor', 'Tan', 'Sin', 'Cos', 'Atan', 'Asin', 'PlotLines'}
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


def item_named(blocks, name):
    for block in blocks:
        for item in (block.payload if block.kind in ('eqs', 'row', 'inputs') else []):
            if item.name == name:
                return item
    raise KeyError(name)


def engine(data, name):
    """A fresh evaluator filled from the dynexp formulas of the written file, as Blockpad would read them."""
    eng = bs.BpEngine(report=name)
    for dyn in ET.fromstring(data).find('report').iter('dynexp'):
        eng.add(dyn.get('formula'))
    eng.all()
    return eng


class PileBpad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e, cls.built = {}, {}
        for support in cli.SUPPORTS:
            cls.e[support] = cli.evaluation(support)
            cls.built[support] = bpad.build_outputs(cls.e[support])

    def each(self):
        for support in cli.SUPPORTS:
            with self.subTest(support=support):
                yield (support, self.e[support], self.built[support])

    # ------------------------------------------------------------------ the files
    def test_committed_sheets_equal_a_fresh_build(self):
        listed = []
        for support, e, b in self.each():
            name, filename = NAMES[support]
            self.assertEqual((b['report_name'], b['filename']), (name, filename))
            self.assertEqual((OUT / filename).read_bytes(), b['document'], f'pile_bpad/{filename} is stale: {HOW}')
            fragment = OUT / 'fragments' / f'{name}.xml'
            self.assertEqual(unix(fragment.read_bytes()), unix(b['fragment']), f'{fragment.name} is stale: {HOW}')
            sidecar = OUT / 'preview' / f'{name}.canvases.json'
            self.assertEqual(unix(sidecar.read_bytes()), cli.sidecar_text(b['sidecar']).encode('utf-8'), f'{sidecar.name} is stale: {HOW}')
            journal = Journal(b['document'])
            part = ET.fromstring(journal.part(f'report:{name}'))
            self.assertEqual(shape(part), shape(ET.fromstring(b['fragment'])), f'{fragment.name} differs from the report in the document')
            self.assertEqual(shape(part), shape(ET.fromstring(fragment.read_bytes())), f'{fragment.name} is stale: {HOW}')
            listed.append(b['verification'])
        committed = (OUT / 'verification.json').read_text(encoding='utf-8')
        self.assertEqual(unix(committed.encode('utf-8')), cli.verification_text(listed).encode('utf-8'), f'pile_bpad/verification.json is stale: {HOW}')

    def test_each_build_is_tied_to_the_package_and_the_registered_fbmp_export(self):
        sources = json.loads((ROOT / 'pile_design' / 'data' / 'sources.json').read_text(encoding='utf-8'))['sources']
        presets = json.loads((ROOT / 'pile_design' / 'data' / 'presets.json').read_text(encoding='utf-8'))
        for support, e, b in self.each():
            v = b['verification']
            self.assertEqual(v['package_revision'], pm.package_revision(), f'the package changed: {HOW}')
            registered = sources[presets[support]['xml']]
            self.assertEqual(v['fbmp_sha256'], registered['sha256'])
            self.assertEqual(v['fbmp_file'], Path(registered['path']).name)
            self.assertTrue((ROOT / registered['path']).is_file())
            self.assertEqual(v['support'], support)
            self.assertEqual(v['family'], e.family)
            self.assertEqual(v['bpad_sha256'], hashlib.sha256(b['document']).hexdigest())
            paragraphs = [text_of(p) for p in ET.fromstring(b['document']).find('report').iter('paragraph')]
            self.assertTrue(any(pm.package_revision()[:12] in t for t in paragraphs), 'the provenance paragraph does not name the package')
            self.assertTrue(any(v['fbmp_file'] in t and v['fbmp_sha256'] in t for t in paragraphs), 'the basis does not name the FBMP file and hash')

    def test_verification_was_substantial(self):
        floor = {'psc': 150, 'pipe': 60}
        for support, e, b in self.each():
            v = b['verification']
            self.assertGreaterEqual(v['tool_comparisons'], floor[e.family], f'{support}: only {v["tool_comparisons"]} comparisons')
            self.assertGreaterEqual(v['mathcad_values_compared'], 40)
            self.assertGreaterEqual(v['data_table_comparisons'], 5)
            self.assertEqual(v['status'], ALL_PASS)
        self.assertEqual(self.built['End Bent 1']['verification']['values_from_notebook'], ['M_r_P0', 'P_r_rs', 'M_r_rs'])
        self.assertEqual(self.built['Pier']['verification']['values_from_notebook'], [])
        self.assertEqual(self.built['End Bent 1']['verification']['approximate_comparisons'], 1)

    def test_every_notebook_definition_and_external_is_in_the_sheet(self):
        for support, e, b in self.each():
            eng = engine(b['document'], b['report_name'])
            mc = pm.sheet(e, pm.package_revision())
            env = pm.verify(mc, e)
            names = [d['name'] for d in e.definitions] + list(e.external_meta)
            self.assertEqual([n for n in names if bs.bp_name(n) not in eng.defs], [])
            for name in names:                                # the Blockpad value equals the notebook value
                unit = e.units.get(name)
                q = eng.get(bs.bp_name(name))
                if unit is None or unit == 'bar':
                    mine = q.v
                else:
                    mine = q.v / eng.unit_q(bs.bp_unit(unit)).v
                want = float(e.value(name, unit))
                self.assertAlmostEqual(mine, want, delta=1e-9 * max(abs(want), 1e-6), msg=f'{support} {name}')

    def test_a_wrong_equation_or_input_stops_the_build(self):
        e = self.e['End Bent 1']
        sheet = pm.sheet

        def wrong(replace, name):
            def build(*args, **kwargs):
                blocks = sheet(*args, **kwargs)
                item = item_named(blocks, name)
                item.expr = replace(item.expr)
                item.tree = parse(item.expr)
                return blocks
            return build

        with mock.patch.object(pm, 'sheet', wrong(lambda s: s.replace('0.0316', '0.0317'), 'V_c')):
            with self.assertRaisesRegex(AssertionError, 'differ from the notebook'):
                bpad.build_outputs(e, mathcad_compare=False)
        with mock.patch.object(pm, 'sheet', wrong(lambda s: '6.0*(ksi)', 'fc')):
            with self.assertRaisesRegex(AssertionError, 'differ from the notebook'):
                bpad.build_outputs(e, mathcad_compare=False)
        with mock.patch.object(pm, 'sheet', wrong(lambda s: s.replace('0.025', '0.026'), 'g_p_p')):      # inside the check at c_gov
            with self.assertRaisesRegex(AssertionError, 'differ from the notebook'):
                bpad.build_outputs(e, mathcad_compare=False)
        pier = self.e['Pier']
        with mock.patch.object(pm, 'sheet', wrong(lambda s: s.replace('0.658', '0.659'), 'P_n')):
            with self.assertRaisesRegex(AssertionError, 'differ from the notebook'):
                bpad.build_outputs(pier, mathcad_compare=False)
        self.assertIs(pm.sheet, sheet)

    def test_the_notebook_export_route_builds_the_same_document(self):
        for support, e, b in self.each():
            info = {}
            data = bpad.build(e, info=info)
            self.assertEqual(data, b['document'])
            self.assertEqual(data, (OUT / NAMES[support][1]).read_bytes())
            self.assertEqual(info['verification'], b['verification'])
            self.assertEqual(bpad.build(e, repo=ROOT), data)

    # ------------------------------------------------------------------ the XML
    def test_xml_is_native_and_journal_compatible(self):
        taken = journal_names()
        for support, e, b in self.each():
            name = b['report_name']
            key = f'report:{name}'
            # The journal holds these names only once T015 is promoted; then the journal edition owns the comparison.
            self.assertEqual(name in taken, key in taken)
            if key in taken:
                fragment = ET.fromstring((OUT / 'fragments' / f'{name}.xml').read_bytes())
                self.assertEqual(shape(ET.fromstring(Journal.load(JOURNAL).part(key))), shape(fragment),
                                 f'journal report {name} differs from its fragment: rebuild and promote a new task')
            self.assertIsNone(CELL_ADDRESS.match(name), 'a report name that looks like a cell address')
            for source, data in (('fresh build', b['document']), ('committed file', (OUT / NAMES[support][1]).read_bytes())):
                with self.subTest(source=source):
                    self.assertNotIn(b'<!--', data)
                    root = ET.fromstring(data)
                    self.assertEqual((root.tag, root.get('version')), ('document', '1.9'))
                    journal = Journal(data)
                    self.assertEqual([k for k in journal.order if k.startswith('report:')], [key])
                    self.assertEqual(journal.order[-1], key)
                    rep = root.find('report')
                    self.assertEqual((rep.get('name'), rep.get('title')), (name, TITLES[support]))
                    kept = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
                    kept.feed(data)
                    self.assertFalse([el for el in kept.close().iter() if not isinstance(el.tag, str)])
                    for el in rep.iter():
                        formula = el.get('formula')
                        if formula:
                            self.check_formula(formula)
                    for p in rep.iter('paragraph'):
                        pieces = [p.text] + [x for node in p.iter() for x in ((node.text,) if node is p else (node.text, node.tail))]
                        self.assertFalse([x for x in pieces if x and x.strip() and re.search(r'[\r\n]', x)], f'a paragraph holds a newline: {text_of(p)[:60]!r}')
                    # no sweep vectors: no definition has a free index, and the names are not cell addresses or units
                    eng = bs.BpEngine(report=name)
                    for dyn in rep.iter('dynexp'):
                        self.assertEqual(dyn.find('expbody').text, dyn.get('formula'))
                        eng.add(dyn.get('formula'))
                    self.assertEqual(eng.unresolved_calls(), [])
                    for n in eng.defs:
                        self.assertIsNone(CELL_ADDRESS.match(n), f'{n} looks like a cell address')
                        self.assertNotIn(n, bs.UNITS)

    def check_formula(self, formula):
        self.assertNotRegex(formula, r'[\r\n]')
        bare = re.sub(r'"[^"]*"', '""', formula)
        self.assertIsNone(re.search(r'(?<![\w.])\d+(?:\.\d+)?[eE][+-]?\d+', bare), f'exponent notation in {formula!r}')
        bare = LITERAL.sub('0', DISPLAY_SUFFIX.sub('', bare))
        self.assertIsNone(re.search(rf'/\s*{UNIT}\b', bare), f'bare-unit division in {formula!r}')
        self.assertIsNone(re.search(rf'\*\s*{UNIT}\b', bare), f'bare-unit multiplication in {formula!r}')
        for fn in re.findall(r'(?<![\w.])([^\W\d][\w.]*)\(', bare):
            self.assertIn(fn.split('.')[-1], ALLOWED_FUNCTIONS, f'function {fn} in {formula!r}')

    # ------------------------------------------------------------------ results
    def stems(self, data, name):
        canvas = next(c for c in ET.fromstring(data).find('report').iter('canvas') if c.get('name') == 'DCChart')
        stems = {bs.BLUE: [], bs.RED: []}
        for plot in canvas.iter('plot'):
            m = re.search(r'If\((\S+) (<=|>) 1,', plot.get('formula'))
            if m:
                want = bs.BLUE if m.group(2) == '<=' else bs.RED
                self.assertEqual(plot.get('linecolor'), want)
                self.assertTrue(m.group(1).startswith(name + '.'), f'{m.group(1)} is not qualified with {name}')
                stems[want].append(m.group(1)[len(name) + 1:])
        return stems

    def check_summary(self, e, data, name):
        eng = engine(data, name)
        checks = pm.summary_checks(e)
        ratio = {c.key: c.ratio for c in e.checks}
        status = eng.get('Status')
        self.assertIn(status, (ALL_PASS, FAILURES))
        failing_nb = {name_ for name_, key, _ in checks if ratio[key] > 1 + 1e-9}
        self.assertEqual(status == FAILURES, bool(failing_nb))
        chk = {n for n in eng.defs if n.startswith('Chk_')}
        self.assertEqual(chk, {'Chk_' + dc[3:] for dc, _, _ in checks})
        self.assertTrue(all(eng.get(n) in (PASS, FAIL) for n in chk))
        self.assertEqual({n for n in chk if eng.get(n) == FAIL}, {'Chk_' + dc[3:] for dc in failing_nb})
        for dc, key, _ in checks:
            self.assertAlmostEqual(eng.get(dc).v, float(ratio[key]), delta=1e-9 * max(abs(ratio[key]), 1e-6), msg=dc)
        names = [dc for dc, _, _ in checks]
        stems = self.stems(data, name)
        self.assertEqual(stems[bs.BLUE], names)
        self.assertEqual(stems[bs.RED], names)
        ratios = [eng.get(n).v for n in names]
        self.assertGreaterEqual(eng.get('DC_ymax').v, max(1.2, 1.1 * max(ratios)) - 1e-12)
        self.assertAlmostEqual(eng.get('DC_max').v, max(ratios), places=12)
        return status

    def test_summary_checks_agree_with_the_notebook(self):
        for support, e, b in self.each():
            status = self.check_summary(e, b['document'], b['report_name'])
            self.assertEqual(status, b['verification']['status'])
            self.assertEqual(status, ALL_PASS)

    def test_a_failing_pile_reads_failures_and_the_failing_checks_are_red(self):
        case = default_case('End Bent 1')
        select_psc(case, '455-024', '16~0.6')
        e = evaluate(case)
        out = bpad.build_outputs(e)
        self.assertEqual(out['verification']['status'], FAILURES)
        self.assertEqual(self.check_summary(e, out['document'], out['report_name']), FAILURES)
        self.assertTrue(any(c.ratio is not None and c.ratio > 1 for c in e.checks))

    def test_preview_sidecar_matches_the_canvases(self):
        for support, e, b in self.each():
            canvases = list(ET.fromstring(b['document']).find('report').iter('canvas'))
            self.assertEqual(len(canvases), 3)                       # Figure 1, Figure 2, Figure 3
            self.assertEqual(sorted(b['sidecar']), sorted(c.get('name') for c in canvases))
            self.assertEqual(sorted(b['sidecar']), ['DCChart', 'Figure1Section', 'Figure2Interaction'])
            for canvas in canvases:
                entry = b['sidecar'][canvas.get('name')]
                width, height = (float(v) for v in re.match(r'([\d.]+) in; ([\d.]+) in', canvas.get('size')).groups())
                self.assertEqual((entry['width_in'], entry['height_in']), (width, height))
                self.assertEqual(entry['title'], canvas.get('title'))
                self.assertTrue(entry['items'], f'{canvas.get("name")} has no preview items')
            # the nominal curve of Figure 2 is a dashed native line; the sidecar says so
            fig2 = next(c for c in canvases if c.get('name') == 'Figure2Interaction')
            if e.family == 'psc':
                self.assertTrue([el for el in fig2 if el.tag == 'lines' and el.get('linepattern') == 'Dashes'])
                self.assertTrue(any(i.get('dash') for i in b['sidecar']['Figure2Interaction']['items']))
                # 121 sweep points plus the two end points
                longest = max(len(i['points']) for i in b['sidecar']['Figure2Interaction']['items'] if i['type'] == 'line')
                self.assertEqual(longest, len(e.curve['Mr']))
            # every live point of the figure is a formula of the sheet's own names
            for plot in fig2.iter('plot'):
                self.assertTrue(plot.get('formula').startswith('PlotLines(['))

    def test_the_interaction_figure_keeps_the_demand_points_live(self):
        for support, e, b in self.each():
            fig2 = next(c for c in ET.fromstring(b['document']).find('report').iter('canvas') if c.get('name') == 'Figure2Interaction')
            live = [p.get('formula') for p in fig2.iter('plot') if b['report_name'] + '.' in p.get('formula')]
            self.assertTrue(any('.P_u_1/' in f for f in live), 'the first record is not a live point')
            self.assertTrue(any('.P_r_max/' in f for f in live) if e.family == 'psc' else any('.P_r_comb/' in f for f in live))

    def test_the_sweep_is_not_written_as_formulas(self):
        eng = engine(self.built['End Bent 1']['document'], 'PileDesignEndBentOne')
        for name in ('c_x', 'c_r', 'P_ext_x', 'M_r_x', 'M_r_r', 'P_r_x', 'dP_x', 'k_rs', 'c_live'):
            self.assertNotIn(name, eng.defs)
        for name in ('c_gov', 'M_r_P0', 'P_r_rs', 'M_r_rs', 'P_r_cg', 'M_r_cg', 'DC_cg', 'DC_bi', 'DC_rs', 'DC_ray', 'DC_max'):
            self.assertIn(name, eng.defs)
        for k in range(1, 13):
            for base in ('x_st', 'y_st', 'eps_p_cg', 'f_p_cg'):
                self.assertIn(f'{base}_{k}', eng.defs)
        self.assertNotIn('x_st_13', eng.defs)
        rep = ET.fromstring(self.built['End Bent 1']['document']).find('report')
        amber = {d.get('formula').split(' = ')[0] for d in rep.iter('dynexp') if d.get('style') == 'Required Input'}
        self.assertTrue({'c_gov', 'M_r_P0', 'P_r_rs', 'M_r_rs', 'alpha_rs', 'alpha_sh', 'fc', 'N_str'} <= amber)

    # ------------------------------------------------------------------ other cases
    def test_other_cases_also_verify(self):
        """Branches the preset piles do not take: Eq. 5.6.4.5-1, a bending axis parallel to a face, other strand patterns, clay."""
        def build(case):
            e = evaluate(case)
            return e, bpad.build_outputs(e)

        case = default_case('End Bent 1')
        case['inputs']['DD_tons'] = 40.0
        e, out = build(case)
        self.assertEqual(e.details['branch'], 'eq1')
        self.assertEqual(out['verification']['values_from_notebook'], ['M_r_P0', 'P_rx', 'P_ry', 'P_r_rs', 'M_r_rs'])
        self.assertIn('P_rxy', engine(out['document'], out['report_name']).defs)
        for mode in ('M2', 'M3', 'both'):
            case = default_case('End Bent 1')
            for r in case['analysis']['records']:
                if mode == 'M2':
                    r['M2'] = 0.0
                elif mode == 'M3':
                    r['M3'] = 0.0
                else:
                    r['M2'] = math.copysign(abs(r['M3']), r['M2'] or 1.0)
                r['M_res'] = r['M_u'] = round(math.hypot(r['M2'], r['M3']), 6)
            e, out = build(case)
            self.assertAlmostEqual(e.value('alpha_rs', 'deg'), 45.0 if mode == 'both' else 0.0, places=6)
        for index, pattern in (('455-014', '8~0.6'), ('455-018', '24~3/8'), ('455-024', '16~0.6')):
            case = default_case('End Bent 1')
            select_psc(case, index, pattern)
            e, out = build(case)
            eng = engine(out['document'], out['report_name'])
            n = e.details['option']['count']
            self.assertIn(f'x_st_{n}', eng.defs)
            self.assertNotIn(f'x_st_{n + 1}', eng.defs)
        case = default_case('Pier')
        case['inputs'].update(soil_type=1, S_u=2.0, t_corr=0.06, Fy=60.0, DD_tons=10.0)
        build(case)

    def test_cases_the_sheet_cannot_distill_are_refused(self):
        case = default_case('End Bent 1')
        case['analysis'] = None
        with self.assertRaisesRegex(ValueError, 'FBMP'):
            bpad.build(evaluate(case))
        case = default_case('End Bent 1')
        select_psc(case, '455-030', '20~0.6')
        with self.assertRaisesRegex(ValueError, 'hollow'):
            bpad.build(evaluate(case))

    # ------------------------------------------------------------------ the notebook export
    def test_the_export_writes_the_named_document_and_its_verification(self):
        e = self.e['End Bent 2']
        with tempfile.TemporaryDirectory() as root:
            path = exports.export_file(e, root, exports.BPAD)
            self.assertEqual(path.name, 'End Bent 2 Pile Design.bpad')
            self.assertEqual(path.read_bytes(), (OUT / path.name).read_bytes())
            record = json.loads((path.parent / exports.VERIFICATION).read_text(encoding='utf-8'))
            self.assertEqual(record, self.built['End Bent 2']['verification'])
            bundle = exports.export_bundle(e, root)
            names = zipfile.ZipFile(bundle[exports.BUNDLE]).namelist()
            self.assertIn('End Bent 2 Pile Design.bpad', names)
            self.assertIn(exports.VERIFICATION, names)
            self.assertNotIn(exports.BPAD, names)
            self.assertNotIn(exports.BPAD_NOTE, names)

    def test_a_missing_generator_is_reported_and_the_bundle_says_so(self):
        e = self.e['Pier']
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.dict(sys.modules, {'pile_design.bpad': None}):
                with self.assertRaises(exports.BpadUnavailable) as raised:
                    exports.export_file(e, root, exports.BPAD)
                self.assertIn('Blockpad generator not available', str(raised.exception))
                bundle = exports.export_bundle(e, root)
            names = zipfile.ZipFile(bundle[exports.BUNDLE]).namelist()
            self.assertIn(exports.BPAD_NOTE, names)
            self.assertNotIn('Pier Pile Design.bpad', names)
            fake = mock.Mock()                                    # a stand-in Mathcad module (as the notebook tests use) is not a module
            with mock.patch.dict(sys.modules, {'pile_design.mathcad': fake}):
                with self.assertRaises(exports.BpadUnavailable):
                    exports.bpad_outputs(e)

    def test_an_unlisted_support_gets_the_generic_name(self):
        e = copy.copy(self.e['Pier'])
        e.case = dict(e.case, support='Other support')
        self.assertEqual(bpad.report_info(e)[0], 'PileDesignNotebook')
        self.assertEqual(bpad.report_info(e)[2], 'Pile Design.bpad')


class Readme(unittest.TestCase):
    def test_the_readme_states_the_limits_and_the_rebuild_command(self):
        text = (OUT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('scripts\\build_pile_bpad.py', text)
        self.assertIn('picture', text)
        self.assertIn('Nothing here has been opened in Blockpad', text)
        for name, _ in NAMES.values():
            self.assertIn(name, text)

    def test_the_preview_folder_ignores_the_renderings(self):
        self.assertEqual((OUT / 'preview' / '.gitignore').read_bytes(), (ROOT / 'cap_bpad' / 'preview' / '.gitignore').read_bytes())


if __name__ == '__main__':
    unittest.main()
