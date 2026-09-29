from copy import deepcopy
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pier_cap.model import default_case, evaluate, set_inputs, analysis_match
from pier_cap.optimizer import SearchConfig, search, sensitivity_search
from pier_cap.sections import (SectionGrid, CostRates, SectionCache, dimension_values, run_section_study,
                               section_rows, selected_section_case, export_section_study)


SMALL = SearchConfig(main_bars=(7, 8), top_counts=(6, 8), bottom_counts=(6, 8),
                     hoop_bars=(5, 6), hoop_spacings=(6, 8), skin_bars=(5,), skin_counts=(6, 7))


class SectionStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = SectionCache()
        cls.grid = SectionGrid(widths=(44, 48, 52), depths=(42, 48, 54))
        cls.study = run_section_study(default_case(), cls.grid, SMALL, cache=cls.cache)

    def test_sensitivity_preserves_analysis_and_ordinary_search_gate(self):
        rows = section_rows(self.study)
        row = next(r for r in rows if r['matches'] and r['width_in'] != 48)
        case = selected_section_case(self.study, row['point_id'], row['candidate_id'])
        self.assertEqual(case['analysis'], default_case()['analysis'])
        self.assertIn('b', analysis_match(case))
        self.assertFalse(evaluate(case).eligible)
        self.assertEqual(case['section_study']['force_mode'], 'fixed')
        with self.assertRaises(ValueError):
            search(case, SMALL)
        with self.assertRaises(ValueError):
            sensitivity_search(set_inputs(default_case(), N_pile=5), SMALL)
        with self.assertRaises(ValueError):
            run_section_study(set_inputs(default_case(), S_pile=6), self.grid, SMALL)

    def test_original_section_reproduces_steel_search(self):
        point = next(p for p in self.study.points if (p.width, p.depth) == (48, 48))
        reference = search(default_case(), SMALL)
        self.assertEqual(point.result.candidates, reference.candidates)
        self.assertEqual(point.result.force_mode, 'fixed')
        self.assertEqual(self.study.evaluated, 9 * 64)
        self.assertTrue(self.study.exhaustive)

    def test_edge_screen_and_wide_single_hoop_rejection(self):
        screened = run_section_study(default_case(), SectionGrid(widths=(40, 44), depths=(48,)), SMALL)
        self.assertEqual(screened.minimum_width_in, 44)
        self.assertEqual(screened.points[0].state, 'GEOMETRY SCREEN')
        self.assertIsNone(screened.points[0].result)
        self.assertIsNotNone(screened.points[1].result)
        wide = next(p for p in self.study.points if (p.width, p.depth) == (52, 48))
        self.assertEqual(wide.result.passed, 0)
        self.assertGreater(wide.result.rejection_counts['Hoop spacing — global'], 0)

    def test_matched_mode_never_substitutes_fixed_forces(self):
        grid = SectionGrid(widths=(44, 48), depths=(48,), force_mode='matched')
        missing = run_section_study(default_case(), grid, SMALL)
        self.assertEqual(missing.points[0].state, 'NEEDS ANALYSIS')
        self.assertIsNone(missing.points[0].result)
        self.assertIsNotNone(missing.points[1].result)
        analyzed = set_inputs(default_case(), b=44, Mu_B=10000)
        analyzed['analysis']['geometry']['b'] = 44
        analyzed['analysis']['id'] = 'New actual analysis'
        matched = run_section_study(default_case(), grid, SMALL, analyzed_cases=[analyzed])
        self.assertEqual(matched.points[0].result.base_case['inputs']['Mu_B'], 10000)
        self.assertEqual(matched.points[0].result.passed, 0)
        self.assertFalse(analysis_match(matched.points[0].result.base_case))
        self.assertEqual(matched.points[0].result.force_mode, 'matched')
        self.assertFalse(missing.exhaustive)

    def test_conflicting_stale_or_sensitivity_cases_are_rejected(self):
        grid = SectionGrid(widths=(44,), depths=(48,), force_mode='matched')
        stale = set_inputs(default_case(), b=44)
        result = run_section_study(default_case(), grid, SMALL, analyzed_cases=[stale])
        self.assertEqual(result.points[0].state, 'INPUT / ANALYSIS ERROR')
        analyzed = deepcopy(stale)
        analyzed['analysis']['geometry']['b'] = 44
        other = set_inputs(analyzed, Vu_G=900)
        conflict = run_section_study(default_case(), grid, SMALL, analyzed_cases=[analyzed, other])
        self.assertIn('Multiple different analyses', conflict.points[0].reason)
        analyzed['section_study'] = {'force_mode': 'fixed'}
        rejected = run_section_study(default_case(), grid, SMALL, analyzed_cases=[analyzed])
        self.assertIn('not a new analyzed case', rejected.points[0].reason)
        # An explicitly supplied current-section analysis supersedes the automatic starting case.
        new_current = set_inputs(default_case(), Mu_B=10000)
        new_current['analysis']['id'] = 'Reanalyzed current section'
        supplied = run_section_study(default_case(), SectionGrid(widths=(48,), depths=(48,), force_mode='matched'),
                                     SMALL, analyzed_cases=[new_current])
        self.assertEqual(supplied.points[0].result.base_case['inputs']['Mu_B'], 10000)

    def test_cache_and_filter_cost_changes(self):
        with patch('pier_cap.sections.sensitivity_search', side_effect=AssertionError('Cache missed')):
            repeated = run_section_study(default_case(), self.grid, SMALL, cache=self.cache)
        self.assertEqual(repeated.new_evaluations, 0)
        self.assertEqual(sum(p.cache_hit for p in repeated.points), 9)
        self.assertEqual(repeated.evaluated, self.study.evaluated)
        changed = run_section_study(set_inputs(default_case(), Mu_B=500), SectionGrid(widths=(48,), depths=(48,)), SMALL, cache=self.cache)
        self.assertGreater(changed.new_evaluations, 0)
        with patch('pier_cap.sections.sensitivity_search', side_effect=AssertionError('Filter recalculated')):
            a = section_rows(self.study, .9)
            b = section_rows(self.study, .97, CostRates(500, 2, 30))
        self.assertGreaterEqual(sum(r['matches'] for r in b), sum(r['matches'] for r in a))
        self.assertIsNone(next(r for r in a if r['matches'])['estimated_cost'])

    def test_quantities_cost_and_independent_pareto_dominance(self):
        rates = CostRates(500, 2, 30)
        rows = section_rows(self.study, .9, rates)
        valid = [r for r in rows if r['matches']]
        self.assertGreater(len(valid), 1)
        for row in valid:
            b, h, length = row['width_in'] / 12, row['depth_in'] / 12, 224 / 12
            self.assertAlmostEqual(row['concrete_yd3'], b * h * length / 27)
            self.assertAlmostEqual(row['form_ft2'], length * (b + 2 * h) + 2 * b * h)
            self.assertAlmostEqual(row['estimated_cost'], 500 * row['concrete_yd3'] + 2 * row['steel_lb'] + 30 * row['form_ft2'])
            dominated = any(other['concrete_yd3'] <= row['concrete_yd3'] and other['steel_lb'] <= row['steel_lb']
                            and (other['concrete_yd3'] < row['concrete_yd3'] or other['steel_lb'] < row['steel_lb']) for other in valid)
            self.assertEqual(row['pareto'], not dominated)

    def test_budget_and_bad_ranges_are_explicit(self):
        result = run_section_study(default_case(), SectionGrid(widths=(44, 48), depths=(48,), max_total_cases=3), SMALL)
        self.assertEqual(result.evaluated, 3)
        self.assertEqual(result.points[0].state, 'PARTIAL')
        self.assertEqual(result.points[1].state, 'NOT RUN')
        self.assertFalse(result.exhaustive)
        self.assertEqual(dimension_values(44, 52, 4), (44, 48, 52))
        for args in ((0, 48, 4), (44, 50, 4), (48, 44, 4), (44, 52, 0), (True, 5, 1)):
            with self.assertRaises(ValueError):
                dimension_values(*args)
        for grid in (SectionGrid(widths=(48, 44)), SectionGrid(depths=(48, 48)), SectionGrid(force_mode='unknown')):
            with self.assertRaises(ValueError):
                run_section_study(default_case(), grid, SMALL)
        for rates in (CostRates(), CostRates(-1, 2, 3), CostRates(float('nan'), 2, 3)):
            with self.assertRaises(ValueError):
                section_rows(self.study, rates=rates)

    def test_export_preserves_sources_and_all_cages(self):
        rows = section_rows(self.study)
        row = next(r for r in rows if r['matches'] and r['width_in'] != 48)
        with tempfile.TemporaryDirectory() as folder:
            path = export_section_study(self.study, folder, selected=(row['point_id'], row['candidate_id']))
            case = json.loads((path / 'selected_case.json').read_text(encoding='utf-8'))
            self.assertEqual(case['analysis'], default_case()['analysis'])
            self.assertIn('REIMPORT', evaluate(case).status)
            manifest = json.loads((path / 'study.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['grid']['force_mode'], 'fixed')
            self.assertEqual(len(manifest['analysis_records']), 9)
            with (path / 'all_section_cages.csv').open(encoding='utf-8-sig', newline='') as f:
                cages = list(csv.DictReader(f))
            self.assertEqual(len(cages), sum(p.result.passed for p in self.study.points))
            self.assertTrue(all(r['Force mode'] == 'fixed' for r in cages))
            requests = json.loads((path / 'analysis_requests.json').read_text())
            self.assertEqual(len(requests), 9)

    def test_click_filter_apply_export_and_invalidation(self):
        from pier_cap.widgets import CapNotebook
        from pier_cap.section_widgets import SectionStudy
        app = CapNotebook()
        panel = SectionStudy(app)
        try:
            panel.study = self.study
            panel._render()
            self.assertEqual(len(panel.figures), 2)
            row = next(r for r in panel.rows if r['matches'] and r['width_in'] != 48)
            panel._map_clicked(None, SimpleNamespace(xs=[row['width_in']], ys=[row['depth_in']]), None)
            self.assertEqual(panel.section.value, row['point_id'])
            self.assertEqual(len(panel.cage.options), row['matches'])
            self.assertIn('SENSITIVITY', panel.selection_info.value)
            panel._apply(None)
            self.assertIs(panel.study, self.study)
            self.assertEqual(app.case['inputs']['b'], row['width_in'])
            self.assertEqual(app.case['analysis'], default_case()['analysis'])
            self.assertFalse(app.current.eligible)
            panel.target.value = .97
            self.assertIs(panel.study, self.study)
            panel.use_cost.value = True
            self.assertTrue(panel.apply_button.disabled)
            panel.rates[0].value = 500
            panel.metric.value = 'estimated_cost'
            self.assertFalse(panel.apply_button.disabled)
            with tempfile.TemporaryDirectory() as folder:
                app.export_root = Path(folder)
                panel._export(None)
                self.assertTrue((panel.last_export / 'sections.csv').exists())
            # Refinement halves steps but waits for the explicit Run action.
            panel._refine(None)
            self.assertEqual(panel.bounds['width'][2].value, 2)
            self.assertEqual(panel.bounds['depth'][2].value, 3)
            self.assertIsNone(panel.study)
            panel.study = self.study
            panel._render()
            app.controls['Mu_B'].value += 1
            self.assertIsNone(panel.study)
            self.assertEqual(panel.cage.options, ())
            self.assertTrue(panel.export_button.disabled)
        finally:
            panel.close()
            for figure in app.figures:
                figure.close()
            app.ui.close()


if __name__ == '__main__':
    unittest.main()
