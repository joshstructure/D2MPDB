"""The three distilled cap Mathcad worksheets (cap_mathcad/*.xmcd) are current, tied to their reports and verified."""
import base64
import copy
import gzip
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from scripts import build_cap_mathcad as m
from scripts import cap_mathcad_figures as figs
from scripts import mathcad_plot, mathcad_sheet
from scripts.mathcad_sheet import D, EQ, R, ROW, U, V, run
from pier_cap.transverse import scheduled_bars

ROOT = Path(__file__).resolve().parent.parent
NS = '{http://schemas.mathsoft.com/worksheet30}'
HOW = 'run python scripts/build_cap_mathcad.py after changing a cap case, a report, the formulas or the generator'
KEYWORDS = ['simplified', 'general', 'flange cracked', 'torsion', 'no minimum transverse', 'beyond 0.006', 'clamped at zero',
            'moment floor', 'end-truncated']


class CapMathcad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built, seen, document = {}, {}, m.document

        def spy(blocks, **kw):                      # keep the writer of each build for the layout checks
            seen['writer'] = mathcad_sheet.layout(blocks, kw['figures_dir'])
            return document(blocks, **kw)

        with mock.patch.object(m, 'document', spy):
            for cap in m.CAPS:
                text, env = m.build(cap)
                cls.built[cap['key']] = (text, env, seen['writer'], m._EVALS[cap['key']])

    def each(self):
        for cap in m.CAPS:
            with self.subTest(cap=cap['key']):
                yield (cap, *self.built[cap['key']])

    def test_committed_worksheets_equal_a_fresh_build(self):
        for cap, text, env, w, e in self.each():
            committed = (ROOT / 'cap_mathcad' / cap['output']).read_text(encoding='utf-8')
            self.assertEqual(committed.replace('\r\n', '\n'), text.replace('\r\n', '\n'), f'{cap["output"]} is stale: {HOW}')

    def test_each_build_is_tied_to_its_latest_report(self):
        for cap, text, env, w, e in self.each():
            folder = ROOT / cap['reports']
            name = env['__meta__']['report']
            self.assertTrue((folder / name).is_file(), f'{name} is not in {cap["reports"]}')
            rep = m.report_link(cap, e)
            self.assertEqual(rep['file'], name)
            html = (folder / name).read_bytes().decode('utf-8', errors='replace')
            printed_case = re.search(r'Case SHA-256 \(canonical JSON\):\s*([0-9a-f]{64})', html).group(1)
            printed_formula = re.search(r'Formula definition SHA-256:\s*([0-9a-f]{64})', html).group(1)
            self.assertEqual((printed_case, printed_formula), (m.case_sha256(e), m.formula_sha256()))
            dated = [tuple(map(int, d.groups())) for p in folder.glob('*Cap Design*.html')
                     for d in [re.search(r'(\d{1,2})-(\d{1,2})\.html$', p.name)] if d]
            self.assertEqual(max(dated), tuple(map(int, re.search(r'(\d{1,2})-(\d{1,2})\.html$', name).groups())),
                             f'a newer report than {name} exists but does not match the case: export it again, then {HOW}')
            self.assertIn(name, text)
            self.assertIn(rep['case_sha'][:12], text)

    def test_verification_was_substantial_and_reached_every_branch(self):
        listed = sorted(m.branches_reached([]))
        for word in KEYWORDS:
            self.assertTrue(any(word in b for b in listed), f'no listed branch mentions {word!r}')
        for cap, text, env, w, e in self.each():
            meta = env['__meta__']
            self.assertGreaterEqual(meta['comparisons'], 800)
            self.assertEqual(meta['branches'], listed)
            rows = m.governing_stations(e)
            cover = [r for _, r in m.coverage_stations(e, rows) + m.synthetic_stations(e, scheduled_bars(e.case))]
            missed = [b for b, hit in m.branches_reached(rows + cover).items() if not hit]
            self.assertEqual(missed, [], 'branches no verified row reaches')

    def test_a_wrong_station_equation_is_caught(self):
        groups, changed = m.station_equation_groups, []

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

        with mock.patch.object(m, 'station_equation_groups', wrong):
            with self.assertRaisesRegex(AssertionError, 'differ from the tool'):
                m.build(m.CAPS[0])
        self.assertEqual(changed, ['V_c'] * len(changed))
        self.assertTrue(changed)
        self.assertIs(m.station_equation_groups, groups)

    def test_xml_is_well_formed_within_the_page_and_in_evaluation_order(self):
        for cap, text, env, w, e in self.each():
            root = ET.fromstring(text.encode('utf-8'))
            self.assertEqual(len(root.findall(f'{NS}binaryContent/{NS}item')), 3)       # elevation, section, D/C plot
            regions = root.find(f'{NS}regions').findall(f'{NS}region')
            geom = lambda r: [float(r.get(k)) for k in ('left', 'top', 'width', 'height')]
            breaks = sorted(geom(r)[1] for r in regions if r.find(f'{NS}pageBreak') is not None)
            tops = [0.0] + [b + mathcad_sheet.PAGE_BREAK_H for b in breaks]
            self.assertEqual(len(tops), env['__meta__']['pages'])
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

    def test_the_figures_draw_the_stations_the_worksheet_uses(self):
        for cap, text, env, w, e in self.each():
            drawn = figs.governing_stations(e)
            self.assertEqual([t['tag'] for t in drawn], list(m.TAGS[:4]))
            rows = m.governing_stations(e)
            for k, (t, row) in enumerate(zip(drawn, rows)):
                self.assertAlmostEqual(t['x_in'], env['x_st'][k].v, places=6)
                self.assertAlmostEqual(t['x_in'], row['station_in'], places=9)
                self.assertIn(f'x = {t["x_in"]:.3f} in', text)
            self.assertEqual([r['id'] for r in rows], env['__meta__']['stations'])

    def test_dc_chart_items_are_the_verified_ratios_and_mark_exactly_those_over_one(self):
        table = [('Flexure', 'DC_flex'), ('Minimum steel', 'DC_min'), ('Strain', 'DC_eps'), ('Service I', 'DC_I')]
        labels = [f'{name} {x}' for name, _ in table for x in 'NPB']
        labels += ['Shear (S)', 'Long. tension N', 'Long. tension P', 'Long. tension B', 'Min. transverse steel (M)',
                   'Transverse spacing', 'Face steel area (max)', 'Face bar spacing (max)', 'Hook development']
        for cap, text, env, w, e in self.each():
            items = m.dc_chart_items(env, cap)
            self.assertEqual([t[0] for t in items], labels)                       # sheet order, hook present on all three caps
            expected = [env[name][i].v for _, name in table for i in range(3)]
            expected += [env[name].v for name in ('DC_shear', 'DC_LN', 'DC_LP', 'DC_LB', 'DC_minAv', 'DC_sp', 'DC_tamax',
                                                  'DC_tsmax', 'DC_hk')]
            self.assertEqual([t[1] for t in items], expected)
            self.assertEqual([t[2] for t in items], [v > 1.0 for v in expected])
            self.assertEqual([y.v for y in env['DC_all']], expected)                # what Figure 3 plots
            over = [t[0] for t in items if t[2]]
            self.assertEqual(over, ['Face bar spacing (max)'] if cap['key'].startswith('end_bent') else [])
            if over:
                self.assertAlmostEqual(dict((t[0], t[1]) for t in items)['Face bar spacing (max)'], 2.9375, places=6)
            self.assertAlmostEqual(max(expected), env['DC_dist'].v, places=12)      # the chart shows the governing ratio
            self.assertEqual(any(t[2] for t in items), env['Status'] == 'FAIL')

    def test_the_dc_plot_is_the_patched_psbeam_plot_of_this_sheets_variables(self):
        base = mathcad_plot.tree_nodes(mathcad_plot.template())
        shape = lambda nodes: [(node, op, parent, zeros) for node, op, flags, parent, leaf, zeros in nodes]
        for cap, text, env, w, e in self.each():
            root = ET.fromstring(text.encode('utf-8'))
            plots = [r for r in root.find(f'{NS}regions').findall(f'{NS}region') if r.find(f'{NS}plot') is not None]
            self.assertEqual(len(plots), 1)
            plot = plots[0].find(f'{NS}plot')
            self.assertEqual(plot.get('disable-calc'), 'false')
            self.assertEqual([float(plots[0].get(k)) for k in ('width', 'height')], [mathcad_plot.WIDTH_PT, mathcad_plot.HEIGHT_PT])
            item = next(i for i in root.findall(f'{NS}binaryContent/{NS}item') if i.get('item-id') == plot.get('item-idref'))
            self.assertEqual(item.get('content-encoding'), 'gzip')
            stored = base64.b64decode(item.text)
            self.assertEqual(stored[:10], b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff')      # the header Mathcad writes
            blob = gzip.decompress(stored)
            n = len(env['DC_all'])
            self.assertEqual(n, len(m.dc_chart_items(env)))
            self.assertEqual(blob, mathcad_plot.patched(n, title=m.DC_TITLE, over_label='D/C over 1.0',
                                                         within_label='D/C within 1.0'), f'{cap["output"]} has a stale plot: {HOW}')
            nodes = mathcad_plot.tree_nodes(blob)
            self.assertEqual(shape(nodes), shape(base))                  # same tree: node ids, operators, parents, closings
            changed = {a[0]: b[4] for a, b in zip(base, nodes) if a != b}
            self.assertEqual(changed, {0x0b: ('name', 'ymax'), 0x0d: ('number', '0'), 0x1b: ('name', 'ymax'),
                                       0x1f: ('name', 'Limit'), 0x24: ('number', str(n + 1))})
            names = {leaf[1] for *_, leaf, _ in nodes if leaf and leaf[0] == 'name'}
            self.assertEqual(names, set(mathcad_plot.USES))
            self.assertTrue(all(name in env for name in names), 'the plot refers to a variable the sheet does not define')
            self.assertEqual(env['Limit'].v, 1.0)
            strings = mathcad_plot.strings(blob)
            for label in (m.DC_TITLE, 'D/C over 1.0', 'D/C within 1.0'):
                self.assertIn(label, strings)
            self.assertFalse(any('Check#' in s or 'Summary of 30' in s for s in strings))
        self.assertEqual(sorted(p.name for p in (ROOT / 'cap_mathcad' / 'figures').glob('*_dc.png')), [],
                         'the static D/C chart pictures were replaced by the live plot')

    def test_the_plot_template_is_checked_before_it_is_patched(self):
        good = mathcad_plot.TEMPLATE.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'template.bin'
            bad.write_bytes(good[:-1] + bytes([good[-1] ^ 1]))
            with mock.patch.object(mathcad_plot, 'TEMPLATE', bad):
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    mathcad_plot.patched(21, title='t', over_label='a', within_label='b')
        with self.assertRaises(ValueError):
            mathcad_plot.patched(21, title='x' * 256, over_label='a', within_label='b')

    def test_the_dc_plot_follows_its_data_and_the_status_line_and_precedes_the_notes(self):
        for cap, text, env, w, e in self.each():
            regions = ET.fromstring(text.encode('utf-8')).find(f'{NS}regions').findall(f'{NS}region')
            kind = lambda r: [c.tag.replace(NS, '') for c in r][0]
            words = lambda r: ''.join(r.itertext()).strip()
            plots = [i for i, r in enumerate(regions) if kind(r) == 'plot']
            self.assertEqual(len(plots), 1)
            at = plots[0]
            status = max(i for i, r in enumerate(regions) if kind(r) == 'math' and words(r).startswith('Status'))
            data = [i for i, r in enumerate(regions) if kind(r) == 'math' and words(r).startswith(('CheckGood', 'CheckNoGood'))]
            self.assertEqual(len(data), 2)
            self.assertTrue(all(status < i < at for i in data))
            caption = words(regions[at + 1])
            self.assertTrue(caption.startswith('Figure 3. Demand/capacity ratio of each distilled check'))
            self.assertIn('recalculates with the worksheet', caption)
            n = len(env['DC_all'])
            key = words(regions[at + 2])
            self.assertTrue(key.startswith('Check numbers: 1–3 flexure (N, P, B); 4–6 minimum steel (N, P, B);'), key)
            self.assertTrue(key.endswith(f'; {n} hook development.'), key)
            notes = [i for i, r in enumerate(regions) if words(r).startswith(('Failing checks not recomputed', 'No tool check outside'))]
            self.assertEqual(len(notes), 1)
            self.assertGreater(notes[0], at + 2)

    def test_the_plot_data_follow_the_ratios_when_they_change(self):
        """Recalculate the Figure 3 definitions on made-up ratios, as Mathcad does after an edit."""
        checks = m.dc_checks(True, True)
        n = sum(rows for _, rows, _ in checks)

        def recalculate(ratios):
            it, defs = iter(ratios), []
            for name, rows, _ in checks:
                values = [next(it) for _ in range(rows)]
                defs.append(D(name, 'col(' + ', '.join(map(repr, values)) + ')' if rows == 3 else repr(values[0])))
            blocks = [EQ(*defs)] + m.dc_plot_blocks(True, True)
            mathcad_sheet.check_order(mathcad_sheet.layout(blocks, ROOT).log)
            return run(blocks)

        for over in ({2}, {0, 13, n - 1}, set()):
            ratios = [round(0.05 * (j + 1), 2) for j in range(n)]
            ratios = [1.25 + j / 100 if j in over else min(r, 1.0) for j, r in enumerate(ratios)]
            env = recalculate(ratios)
            m.check_plot_data(env)
            red = [j for j in range(n) if env['CheckNoGood'][j, 0].v > 0]
            blue = [j for j in range(n) if env['CheckGood'][j, 0].v > 0]
            self.assertEqual(red, sorted(over))
            self.assertEqual(sorted(red + blue), list(range(n)))
            self.assertEqual([env['CheckNoGood'][j, 1].v for j in red], [ratios[j] for j in red])
            self.assertAlmostEqual(env['ymax'].v, max(1.2, 1.1 * max(ratios)), places=12)
            if n - 1 not in over:                                          # exactly 1.0 stays blue: the limit is "≤ 1"
                self.assertEqual(ratios[n - 1], 1.0)
                self.assertIn(n - 1, blue)
        env['CheckGood'][0, 1] = U(0.5)
        with self.assertRaisesRegex(AssertionError, 'misplace check 1'):
            m.check_plot_data(env)

    def test_writer_stack_augment_last_and_a_computed_range(self):
        rng = R('i', 0, 'last(b)')
        blocks = [EQ(D('a', 'col(1, 2)'), D('b', 'stack(a, 3)')), ROW(rng),
                  EQ(V('c', 'i', 'b[i]*2', show=False), D('M', 'augment(b, c)'))]
        env = run(blocks)
        self.assertEqual([y.v for y in env['b']], [1, 2, 3])
        self.assertEqual(env['i'], [0, 1, 2])
        self.assertEqual((env['M'][2, 0].v, env['M'][2, 1].v), (3, 6))
        self.assertEqual(mathcad_sheet.uses_of(rng), {'b'})
        self.assertIn('<ml:range><ml:real>0</ml:real><ml:apply><ml:id xml:space="preserve">last</ml:id>'
                      '<ml:id xml:space="preserve">b</ml:id></ml:apply></ml:range>', mathcad_sheet.Writer._inner(rng))
        with self.assertRaises(mathcad_sheet.UnitError):
            run([EQ(D('b', 'stack(1*in, 2)'))])
        with self.assertRaises(mathcad_sheet.UnitError):
            run([EQ(D('a', 'col(1, 2)'), D('M', 'augment(a, col(1, 2, 3))'))])

    def test_fig_takes_png_bytes_without_a_file(self):
        png = (ROOT / 'cap_mathcad' / 'figures' / 'pier_section.png').read_bytes()
        w = mathcad_sheet.layout([mathcad_sheet.FIG('no_such_file', 'caption', width=200, data=png)], ROOT / 'no_such_folder')
        self.assertEqual(w.items, [(1, png)])


if __name__ == '__main__':
    unittest.main()
