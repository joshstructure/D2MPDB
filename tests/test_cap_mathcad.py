"""The three distilled cap Mathcad worksheets (cap_mathcad/*.xmcd) are current, tied to their reports and verified."""
import base64
import copy
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from scripts import build_cap_mathcad as m
from scripts import cap_mathcad_figures as figs
from scripts import mathcad_sheet
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
            self.assertEqual(len(root.findall(f'{NS}binaryContent/{NS}item')), 3)       # elevation, section, D/C chart
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
            self.assertEqual([t[2] for t in items], [v > 1.0 + 1e-9 for v in expected])
            over = [t[0] for t in items if t[2]]
            self.assertEqual(over, ['Face bar spacing (max)'] if cap['key'].startswith('end_bent') else [])
            if over:
                self.assertAlmostEqual(dict((t[0], t[1]) for t in items)['Face bar spacing (max)'], 2.9375, places=6)
            self.assertAlmostEqual(max(expected), env['DC_dist'].v, places=12)      # the chart shows the governing ratio
            self.assertEqual(any(t[2] for t in items), env['Status'] == 'FAIL')

    def test_dc_chart_png_is_deterministic_and_is_the_picture_in_the_sheet_and_in_figures(self):
        for cap, text, env, w, e in self.each():
            items = m.dc_chart_items(env, cap)
            png = m.dc_chart_png(items)
            self.assertEqual(png, m.dc_chart_png(items), 'two draws of the chart differ')
            self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual((int.from_bytes(png[16:20], 'big'), int.from_bytes(png[20:24], 'big')),
                             (1500, round(200 * (0.55 + 0.24 * len(items)))))
            root = ET.fromstring(text.encode('utf-8'))
            binary = root.findall(f'{NS}binaryContent/{NS}item')
            self.assertEqual(binary[2].get('item-id'), '3')
            self.assertEqual(base64.b64decode(binary[2].text), png, f'{cap["output"]} embeds a different chart: {HOW}')
            committed = (ROOT / 'cap_mathcad' / 'figures' / f'{cap["key"]}_dc.png').read_bytes()
            self.assertEqual(committed, png, f'figures/{cap["key"]}_dc.png is stale: {HOW}')

    def test_the_dc_chart_follows_the_status_line_and_precedes_the_notes(self):
        for cap, text, env, w, e in self.each():
            regions = ET.fromstring(text.encode('utf-8')).find(f'{NS}regions').findall(f'{NS}region')
            kind = lambda r: [c.tag.replace(NS, '') for c in r][0]
            words = lambda r: ''.join(r.itertext()).strip()
            pics = [i for i, r in enumerate(regions) if r.find(f'{NS}picture/{NS}png[@item-idref="3"]') is not None]
            self.assertEqual(len(pics), 1)
            at = pics[0]
            png = regions[at].find(f'{NS}picture/{NS}png')
            self.assertEqual(float(png.get('display-width')), 540.0)
            status = max(i for i, r in enumerate(regions) if kind(r) == 'math' and words(r).startswith('Status'))
            self.assertLess(status, at)
            self.assertTrue(all(kind(r) in ('text', 'pageBreak') for r in regions[status + 1:at]), 'only the Status caption may sit between')
            self.assertTrue(words(regions[at + 1]).startswith('Figure 3. Demand/capacity ratios'))
            self.assertIn('does not recalculate inside Mathcad', words(regions[at + 1]))
            notes = [i for i, r in enumerate(regions) if words(r).startswith(('Failing checks not recomputed', 'No tool check outside'))]
            self.assertEqual(len(notes), 1)
            self.assertGreater(notes[0], at + 1)

    def test_fig_takes_png_bytes_without_a_file(self):
        png = m.dc_chart_png([('a', 0.5, False), ('b', 1.5, True)])
        w = mathcad_sheet.layout([mathcad_sheet.FIG('no_such_file', 'caption', width=200, data=png)], ROOT / 'no_such_folder')
        self.assertEqual(w.items, [(1, png)])


if __name__ == '__main__':
    unittest.main()
