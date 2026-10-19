"""The two distilled pile Mathcad worksheets (pile_mathcad/*.xmcd) match the pile notebook model and are current."""
import base64
import copy
import gzip
import math
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from pile_design import mathcad as m
from pile_design.model import default_case, evaluate, select_psc
from scripts import build_pile_mathcad as cli
from scripts import mathcad_plot, mathcad_sheet
from scripts.mathcad_sheet import UnitError, ev, parse

ROOT = Path(__file__).resolve().parent.parent
NS = '{http://schemas.mathsoft.com/worksheet30}'
HOW = 'run python scripts/build_pile_mathcad.py after changing the pile_design package, the registered FBMP export or the generator'


def build_with_writer(e):
    """(text, info, writer of the layout) of one worksheet; the writer carries the evaluation-order log."""
    seen = {}
    document = mathcad_sheet.document

    def spy(blocks, **kw):
        seen['writer'] = mathcad_sheet.layout(blocks, kw['figures_dir'])
        return document(blocks, **kw)

    info = {}
    with mock.patch.object(m._sheet(), 'document', spy):
        text = m.build(e, repo=ROOT, info=info)
    return text, info, seen['writer']


def item_named(blocks, name):
    for block in blocks:
        for item in (block.payload if block.kind in ('eqs', 'row', 'inputs') else []):
            if item.name == name:
                return item
    raise KeyError(name)


class PileMathcad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e, cls.built = {}, {}
        for support in cli.SUPPORTS:
            cls.e[support] = cli.evaluation(support)
            cls.built[support] = build_with_writer(cls.e[support])

    def each(self):
        for support in cli.SUPPORTS:
            with self.subTest(support=support):
                yield (support, self.e[support], *self.built[support])

    # ------------------------------------------------------------------ equations and inputs
    def test_every_worksheet_equation_matches_the_notebook(self):
        floor = {'psc': 150, 'pipe': 60}
        for support, e, text, info, w in self.each():
            blocks = m.sheet(e, m.package_revision())
            env = m.verify(blocks, e)
            n = len(m.comparisons(env, e))
            self.assertGreaterEqual(n, floor[e.family], f'{support}: only {n} comparisons')
            self.assertEqual(info['comparisons'], n)
        self.assertGreaterEqual(self.built['End Bent 1'][1]['comparisons'], 2000)     # every point of both sweeps is compared

    def test_every_notebook_definition_and_external_is_in_the_sheet(self):
        for support, e, text, info, w in self.each():
            env = info['env']
            names = [d['name'] for d in e.definitions] + list(e.external_meta)
            self.assertEqual([n for n in names if n not in env], [])

    def test_inputs_equal_the_notebook_inputs(self):
        for support, e, text, info, w in self.each():
            blocks = m.sheet(e, m.package_revision())
            env = m.check_inputs(blocks, e)
            spec = {s['name'] for s in m.INPUT_SPEC if s['family'] in (e.family, 'both')}
            optional = {n for n in spec if e.case['inputs'].get(n) is None}
            self.assertEqual(spec - optional - set(env), set())
            if e.family == 'psc':
                self.assertEqual(env['N_str'].v, e.details['option']['count'])

    def test_a_wrong_input_or_equation_is_caught(self):
        e = self.e['End Bent 1']
        blocks = m.sheet(e, m.package_revision())
        bad = item_named(blocks, 'fc')
        bad.expr, bad.tree = '6.0*(ksi)', parse('6.0*(ksi)')
        with self.assertRaises(AssertionError):
            m.check_inputs(blocks, e)
        blocks = m.sheet(e, m.package_revision())
        item = item_named(blocks, 'V_c')
        item.expr = item.expr.replace('0.0316', '0.0317')
        item.tree = parse(item.expr)
        with self.assertRaisesRegex(AssertionError, 'differ from the notebook'):
            m.verify(blocks, e)
        blocks = m.sheet(e, m.package_revision())
        item = item_named(blocks, 'g_p_x')                    # the power formula of the strand stress, inside the sweep
        item.expr = item.expr.replace('0.025', '0.026')
        item.tree = parse(item.expr)
        with self.assertRaisesRegex(AssertionError, 'differ from the notebook'):
            m.verify(blocks, e)

    def test_hand_values_of_the_standard_pile(self):
        env = self.built['End Bent 1'][1]['env']
        aps = 12 * 0.217
        fpe = 35 / 0.217 * 0.8
        self.assertAlmostEqual(env['A_ps'].v, aps, places=9)
        self.assertAlmostEqual(env['P_e'].v, aps * fpe, places=6)                    # 336.0 kip
        self.assertAlmostEqual(env['P_e'].v, 336.0, places=6)
        fc = self.e['End Bent 1'].case['inputs']['fc']
        pn_max = 0.85 * (0.85 * fc * (324 - aps) - aps * (fpe - 28500 * 0.003))
        self.assertAlmostEqual(env['P_n_max'].v, pn_max, places=6)
        self.assertAlmostEqual(env['P_r_max'].v, 0.75 * pn_max, places=6)
        # pure bending of the 18 in pile is within 15 % of the Spec Table 455-2 splice strength (sanity, not a check)
        mr0 = mathcad_sheet._to(env['M_r_P0'], 'kip*ft')
        self.assertLess(abs(mr0 - 245.0) / 245.0, 0.20)
        pipe = self.built['Pier'][1]['env']
        self.assertAlmostEqual(pipe['A_g'].v, math.pi / 4 * (20 ** 2 - 19.04 ** 2), places=9)
        self.assertAlmostEqual(pipe['D_t'].v, 20 / 0.48, places=9)

    # ------------------------------------------------------------------ the files
    def test_committed_worksheets_equal_a_fresh_build(self):
        for support, e, text, info, w in self.each():
            committed = (ROOT / 'pile_mathcad' / cli.output_name(support)).read_text(encoding='utf-8')
            self.assertNotIn('\r', committed)
            self.assertEqual(committed, text, f'{cli.output_name(support)} is stale: {HOW}')

    def test_committed_figures_equal_a_fresh_drawing(self):
        import matplotlib.image as mpimg
        import io
        for support, e, text, info, w in self.each():
            for name, data in zip(m.figure_names(e), m.figures(e).values()):
                fresh = mpimg.imread(io.BytesIO(data))
                committed = mpimg.imread(ROOT / 'pile_design' / 'mathcad' / f'{name}.png')
                self.assertEqual(fresh.shape, committed.shape, f'{name}.png is stale: {HOW} --render-figures')
                self.assertLess(float(abs(fresh - committed).mean()), 2e-3, f'{name}.png is stale: {HOW} --render-figures')

    def test_the_notebook_export_route_builds_the_same_worksheet(self):
        for support, e, text, info, w in self.each():
            fresh = m.build(e)                                   # figures drawn in memory, no checkout needed
            strip = lambda s: s.split('<binaryContent>')[0]
            self.assertEqual(strip(fresh), strip(text))
            self.assertEqual(len(ET.fromstring(fresh.encode('utf-8')).findall(f'{NS}binaryContent/{NS}item')), 3)

    def test_title_description_and_binary_items(self):
        for support, e, text, info, w in self.each():
            root = ET.fromstring(text.encode('utf-8'))
            title = root.find(f'{NS}metadata/{NS}userData/{NS}title').text
            self.assertEqual(title, f'{support} Pile Design')
            self.assertLessEqual(len(title), 54)
            description = root.find(f'{NS}metadata/{NS}userData/{NS}description').text
            a = e.case['analysis']
            for part in ('pile_design/mathcad.py', m.package_revision()[:12], a['filename'], a['sha256']):
                self.assertIn(part, description)
            self.assertEqual(len(root.findall(f'{NS}binaryContent/{NS}item')), 3)       # section, interaction, D/C plot

    def test_xml_is_well_formed_within_the_page_and_in_evaluation_order(self):
        for support, e, text, info, w in self.each():
            root = ET.fromstring(text.encode('utf-8'))
            regions = root.find(f'{NS}regions').findall(f'{NS}region')
            geom = lambda r: [float(r.get(k)) for k in ('left', 'top', 'width', 'height')]
            breaks = sorted(geom(r)[1] for r in regions if r.find(f'{NS}pageBreak') is not None)
            tops = [0.0] + [b + mathcad_sheet.PAGE_BREAK_H for b in breaks]
            self.assertEqual(len(tops), len(info['page_fills']))
            for r in regions:
                if r.find(f'{NS}pageBreak') is not None:
                    continue
                left, top, width, height = geom(r)
                bottom = top + height
                self.assertLessEqual(left + width, mathcad_sheet.RIGHT + 0.01, f'region {r.get("region-id")} is too wide')
                self.assertFalse(any(top < b < bottom for b in breaks), f'region {r.get("region-id")} crosses a page break')
                page = max(i for i, t in enumerate(tops) if top >= t - 0.01)
                if height <= mathcad_sheet.PAGE_H:
                    self.assertLessEqual(bottom - tops[page], mathcad_sheet.PAGE_H + 0.01, f'region {r.get("region-id")} is too low')
            mathcad_sheet.check_order(w.log)
            w.check_pages()
            w.check_width()
            self.assertTrue(all(0 < f <= mathcad_sheet.PAGE_H for f in info['page_fills']))

    def test_results_beside_equations_follow_them_in_mathcad_order(self):
        for support, e, text, info, w in self.each():
            beside = [r for r in w.log if r['label'].startswith('tr(') and r['left'] > mathcad_sheet.LEFT + 1]
            self.assertIsInstance(beside, list)
        bad = [dict(top=0, align=20, left=18, defines={'d'}, uses=set(), label='d'),
               dict(top=1, align=13, left=200, defines=set(), uses={'d'}, label='tr(d)')]
        with self.assertRaisesRegex(AssertionError, 'by align'):
            mathcad_sheet.check_order(bad)

    # ------------------------------------------------------------------ the D/C plot
    def test_the_dc_plot_is_the_patched_psbeam_plot_of_this_sheets_variables(self):
        base = mathcad_plot.tree_nodes(mathcad_plot.template())
        shape = lambda nodes: [(node, op, parent, zeros) for node, op, flags, parent, leaf, zeros in nodes]
        for support, e, text, info, w in self.each():
            env = info['env']
            root = ET.fromstring(text.encode('utf-8'))
            plots = [r for r in root.find(f'{NS}regions').findall(f'{NS}region') if r.find(f'{NS}plot') is not None]
            self.assertEqual(len(plots), 1)
            plot = plots[0].find(f'{NS}plot')
            self.assertEqual([float(plots[0].get(k)) for k in ('width', 'height')], [mathcad_plot.WIDTH_PT, mathcad_plot.HEIGHT_PT])
            item = next(i for i in root.findall(f'{NS}binaryContent/{NS}item') if i.get('item-id') == plot.get('item-idref'))
            blob = gzip.decompress(base64.b64decode(item.text))
            n = len(env['DC_all'])
            self.assertEqual(n, len(m.summary_checks(e)))
            self.assertEqual(blob, mathcad_plot.patched(n, title=m.DC_TITLE, over_label='D/C over 1.0', within_label='D/C within 1.0'),
                             f'{support} has a stale plot: {HOW}')
            self.assertEqual(shape(mathcad_plot.tree_nodes(blob)), shape(base))
            names = {leaf[1] for *_, leaf, _ in mathcad_plot.tree_nodes(blob) if leaf and leaf[0] == 'name'}
            self.assertEqual(names, set(mathcad_plot.USES))
            self.assertTrue(all(name in env for name in names))
            self.assertLessEqual(len(m.DC_TITLE), mathcad_plot.TITLE_MAX)

    def test_the_dc_plot_traces_split_at_the_limit(self):
        # the preset pile passes everything: every check is in the blue trace and parked at -1 in the red one
        for support, e, text, info, w in self.each():
            env = info['env']
            m.check_plot_data(env, e)
            values = [y.v for y in env['DC_all']]
            self.assertEqual(values, [env[name].v for name, _, _ in m.summary_checks(e)])
            self.assertEqual(max(values), env['DC_max'].v)
            self.assertEqual(env['Limit'].v, 1.0)
            for j in range(len(values)):
                self.assertEqual((env['CheckGood'][j, 0].v, env['CheckGood'][j, 1].v), (j + 1, values[j]))
                self.assertEqual((env['CheckNoGood'][j, 0].v, env['CheckNoGood'][j, 1].v), (-1, 0))
        # a pile that is too weak: the failing checks swap to the red trace
        case = default_case('End Bent 1')
        select_psc(case, '455-024', '16~0.6')
        e = evaluate(case)
        info = {}
        m.build(e, info=info)
        env = info['env']
        values = [y.v for y in env['DC_all']]
        over = [j for j, v in enumerate(values) if v > 1.0]
        self.assertTrue(over)
        self.assertEqual(env['Status'], 'FAIL')
        for j, v in enumerate(values):
            shown, parked = (env['CheckNoGood'], env['CheckGood']) if j in over else (env['CheckGood'], env['CheckNoGood'])
            self.assertEqual((shown[j, 0].v, shown[j, 1].v), (j + 1, v))
            self.assertEqual((parked[j, 0].v, parked[j, 1].v), (-1, 0))
        self.assertGreaterEqual(env['ymax'].v, 1.1 * max(values))

    # ------------------------------------------------------------------ units
    def test_vector_products_and_unit_errors_are_rejected_like_mathcad(self):
        env = {'a': [mathcad_sheet.U(1), mathcad_sheet.U(2)], 'b': [mathcad_sheet.U(3), mathcad_sheet.U(4)]}
        with self.assertRaises(UnitError):
            ev(parse('a*b'), env)
        with self.assertRaises(UnitError):
            ev(parse('1*in + 1*kip'), {})
        with self.assertRaises(UnitError):
            ev(parse('stack(1*kip, 2*kip)'), {})
        # the pile sheet itself: a vector product spliced into an equation is refused when the sheet is run
        e = self.e['End Bent 1']
        blocks = m.sheet(e, m.package_revision())
        item = item_named(blocks, 'F_ps_x')
        item.expr, item.tree = 'F_ps_x*F_ps_x', parse('F_ps_x*F_ps_x')
        with self.assertRaises((UnitError, NameError)):
            mathcad_sheet.run(blocks)

    # ------------------------------------------------------------------ branches
    def test_other_cases_also_verify(self):
        """Branches the preset piles do not take: Eq. 5.6.4.5-1, a bending axis parallel to a face, other strand patterns, clay."""
        def build(case):
            e = evaluate(case)
            info = {}
            m.build(e, info=info)
            return e, info

        case = default_case('End Bent 1')
        case['inputs']['DD_tons'] = 40.0
        e, info = build(case)
        self.assertEqual(e.details['branch'], 'eq1')
        self.assertIn('P_rxy', info['env'])

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
            e, info = build(case)
            self.assertAlmostEqual(e.value('alpha_rs', 'deg'), 45.0 if mode == 'both' else 0.0, places=6)

        for index, pattern in (('455-014', '8~0.6'), ('455-018', '24~3/8'), ('455-024', '16~0.6')):
            case = default_case('End Bent 1')
            select_psc(case, index, pattern)
            build(case)

        case = default_case('Pier')
        case['inputs'].update(soil_type=1, S_u=2.0, t_corr=0.06, Fy=60.0, DD_tons=10.0)
        build(case)

    def test_cases_the_sheet_cannot_distill_are_refused(self):
        case = default_case('End Bent 1')
        case['analysis'] = None
        with self.assertRaisesRegex(ValueError, 'FBMP'):
            m.build(evaluate(case))
        case = default_case('End Bent 1')
        select_psc(case, '455-030', '20~0.6')
        with self.assertRaisesRegex(ValueError, 'hollow'):
            m.build(evaluate(case))


class Readme(unittest.TestCase):
    def test_the_readme_states_the_static_picture_and_the_rebuild_command(self):
        text = (ROOT / 'pile_mathcad' / 'README.md').read_text(encoding='utf-8')
        self.assertIn('static picture', text)
        self.assertIn('live vectors', text)
        self.assertIn('scripts\\build_pile_mathcad.py', text)
        self.assertIn('not opened them in Mathcad', text.replace('has not opened them', 'not opened them'))


class SharedWriterUnchanged(unittest.TestCase):
    """The pile sheets use the shared writer as it is: its own suites still pass (run tests.test_cap_mathcad and the MathcadEdition tests)."""

    def test_the_writer_still_serves_the_other_sheets(self):
        self.assertEqual(mathcad_sheet.PAGE_H, 690.0)
        self.assertIn('stack', mathcad_sheet.FUNCTIONS)
        self.assertNotIn('sum', mathcad_sheet.FUNCTIONS)       # the pile sheet restructures instead of extending the DSL


if __name__ == '__main__':
    unittest.main()
