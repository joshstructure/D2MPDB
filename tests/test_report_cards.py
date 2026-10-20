"""Definition/citation cards in the calculation reports, and the code-excerpt store they embed."""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import report_cards  # noqa: E402
from scripts import build_code_excerpts as excerpts  # noqa: E402

STORE = ROOT / 'code_excerpts'


class ExcerptStore(unittest.TestCase):
    def test_store_is_current(self):
        library, overrides = excerpts.load_config()
        found = excerpts.collect_pieces(library)
        ok, message = excerpts.status(library, overrides, found)
        self.assertTrue(ok, f'code_excerpts is stale ({message}); run scripts/build_code_excerpts.py')

    def test_every_cited_piece_has_an_entry_with_images_or_a_reason(self):
        library, _ = excerpts.load_config()
        store = json.loads((STORE / 'excerpts.json').read_text(encoding='utf-8'))
        for piece in excerpts.collect_pieces(library):
            entry = store['cites'].get(piece)
            self.assertIsNotNone(entry, piece)
            self.assertTrue(entry['pages'] or entry['missing'], piece)
            for page in entry['pages']:
                for key in ('crop', 'full'):
                    self.assertTrue((STORE / page[key]).is_file(), f'{piece}: {page[key]}')
                self.assertTrue(page['label'])

    def test_backwall_and_pile_citations_resolve_to_code_pages(self):
        store = json.loads((STORE / 'excerpts.json').read_text(encoding='utf-8'))
        for piece, printed in (('SDM 12.3.F', '12-3'), ('SDG 3.13.2.N.3', '3-63'), ('LRFD 3.4.1, Tables 3.4.1-1 and 3.4.1-2', '3-16'),
                               ('LRFD 5.6.4.4, Eqs. 5.6.4.4-1 and -2', '5-51'), ('AASHTO Guide Spec. Pedestrian Bridges 3.1', '2')):
            pages = [p['printed'] for p in store['cites'][piece]['pages']]
            self.assertIn(printed, pages, piece)

    def test_piece_parsing_and_prose_canonical_form(self):
        self.assertEqual(excerpts.Builder.parse('3.4.1, Tables 3.4.1-1 and 3.4.1-2'), (['3.4.1'], ['3.4.1-1', '3.4.1-2'], []))
        self.assertEqual(excerpts.Builder.parse('5.6.3.2, Eqs. 5.6.3.2.2-1 and 5.6.3.2.3-1'), (['5.6.3.2'], [], ['5.6.3.2.2-1', '5.6.3.2.3-1']))
        self.assertEqual(excerpts.Builder.parse('3.11.5.3, Eqs. 3.11.5.3-1 and -2'), (['3.11.5.3'], [], ['3.11.5.3-1', '3.11.5.3-2']))
        self.assertEqual(excerpts.Builder.parse('3.13.2.I.1 and Table 2.2-1'), (['3.13.2.I.1'], ['2.2-1'], []))
        text = 'per LRFD Article 5.7.3.3 and SDG Table 1.4.2-1; see LRFD Eqs. 5.7.3.4.2-1 and SDM 12.3.F again (LRFD 5.7.3.3).'
        self.assertEqual(report_cards.prose_pieces(text), ['LRFD 5.7.3.3', 'SDG Table 1.4.2-1', 'LRFD Eq. 5.7.3.4.2-1', 'SDM 12.3.F'])
        refs = {'a': {'code': 'SDG', 'article': '2.7.1, Table 2.7.1-1; LRFD 3.12.2', 'governs': 'x'}}
        self.assertEqual(report_cards.pieces(refs), ['SDG 2.7.1, Table 2.7.1-1', 'LRFD 3.12.2'])


class CardAssets(unittest.TestCase):
    def test_script_parses_and_versions_agree(self):
        css, js = report_cards.assets()
        self.assertIn(f"CARDS_VERSION = '{report_cards.CARDS_VERSION}'", js)
        self.assertIn('.var-pop', css)
        node = shutil.which('node')
        if node:
            result = subprocess.run([node, '--check', str(ROOT / 'report_cards' / 'cards.js')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_cards_without_a_store_still_render(self):
        html = report_cards.cards_html(None)
        self.assertIn('id="report-cards-script"', html)
        self.assertNotIn('<script id="cite-data"', html)
        self.assertIsNone(report_cards.cite_data({}, store=ROOT / 'nonexistent'))

    def test_cite_data_embeds_crops_once_per_page(self):
        refs = {'strap_plans': {'code': 'SDM', 'article': '12.3.F', 'governs': 'Plan note'},
                'load_factors': {'code': 'LRFD', 'article': '3.4.1, Tables 3.4.1-1 and 3.4.1-2', 'governs': 'Load factors'}}
        data = report_cards.cite_data(refs, extra_pieces=['LRFD 5.7.3.3'])
        self.assertEqual(set(data['cites']), {'SDM 12.3.F', 'LRFD 3.4.1, Tables 3.4.1-1 and 3.4.1-2', 'LRFD 5.7.3.3'})
        card = data['cites']['SDM 12.3.F']
        self.assertEqual(card['governs'], ['Plan note'])
        self.assertTrue(card['pages'][0]['crop'].startswith('data:image/png;base64,'))
        self.assertIn(card['pages'][0]['full'], data['pages'])
        self.assertIsNone(card['pages'][0]['pdf'])
        with_pdf = report_cards.cite_data(refs, pdf_dir='References')
        self.assertEqual(with_pdf['cites']['SDM 12.3.F']['pages'][0]['pdf'], 'References/SDM 12.3.F (SDM p. 12-3).pdf')


class ReportsCarryCards(unittest.TestCase):
    def test_backwall_report(self):
        from end_bent_walls.model import evaluate
        from end_bent_walls.report import build_report
        html = build_report(evaluate())
        self.assertIn('id="report-cards-script"', html)
        self.assertIn('<msub data-var="F_str_STRI">', html)
        data = json.loads(html.split('<script id="cite-data" type="application/report-cards+json">', 1)[1].split('</script>', 1)[0].replace('<\\/', '</'))
        for piece in ('SDM 12.3.F', 'SDG 3.13.2.N.3', 'LRFD 5.6.3.2, Eqs. 5.6.3.2.2-1 and 5.6.3.2.3-1'):
            self.assertIn(piece, data['cites'])
        self.assertTrue(data['cites']['SDM 12.3.F']['pages'][0]['crop'].startswith('data:image/png'))

    def test_pile_report(self):
        from pile_design.model import default_case, evaluate
        from pile_design.report import build_report
        html = build_report(evaluate(default_case('End Bent 1', load_xml=False)))
        self.assertIn('id="report-cards-script"', html)
        self.assertIn(' data-var="', html)
        data = json.loads(html.split('<script id="cite-data" type="application/report-cards+json">', 1)[1].split('</script>', 1)[0].replace('<\\/', '</'))
        self.assertIn('LRFD 5.6.4.4, Eqs. 5.6.4.4-1 and -2', data['cites'])

    def test_cap_report(self):
        from tests.case_fixtures import default_case
        from pier_cap.calculation_report import calculation_report
        html = calculation_report(default_case())
        self.assertIn('id="report-cards-script"', html)
        self.assertIn(' data-var="', html)
        data = json.loads(html.split('<script id="cite-data" type="application/report-cards+json">', 1)[1].split('</script>', 1)[0].replace('<\\/', '</'))
        self.assertTrue(any(k.startswith('LRFD 5.') for k in data['cites']), sorted(data['cites']))


if __name__ == '__main__':
    unittest.main()
