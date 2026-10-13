"""Exercise real workbench controls, stale-state gates, plots and saved exports."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from ring_wall.model import analyze, default_case
from ring_wall.widgets import RingWallNotebook

ROOT=Path(__file__).resolve().parents[1]


class RingWallWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT,prefix='.ring-wall-test-')
        self.app=RingWallNotebook(export_root=Path(self.temp.name)/'exports')

    def tearDown(self):
        self.app.close();self.temp.cleanup()

    def test_initial_results_are_live_and_run_does_not_export(self):
        app=self.app
        self.assertEqual(app.current,analyze())
        self.assertFalse(app.export_root.exists())
        self.assertEqual(app.recalc_button.description,'Calc done')
        self.assertIn('REVISE TRIAL',app.status.value)
        self.assertIn('RING-GRID',app.checks_panel.value)
        self.assertIn('NODE-3D',app.checks_panel.value)
        z=app.figures['reactions'].data[0].z
        self.assertAlmostEqual(sum(sum(row) for row in z),app.current['totals']['factored_weight'])
        self.assertEqual(list(app.figures['forces'].data[0].y),[r['arch']['tie'] for r in app.current['rows']])
        self.assertIn('0.744',app.steel_panel.value)

    def test_edits_refresh_layout_clear_results_and_recalc_updates_tables(self):
        app=self.app;figure=app.figures['layout'];before=list(figure.data[2].y)
        original_force=app.current['totals']['factored_weight']
        app.controls['ring_spacing_in'].value=34.
        self.assertIs(app.figures['layout'],figure)
        self.assertNotEqual(list(figure.data[2].y),before)
        self.assertIsNone(app.current);self.assertTrue(app.dirty)
        self.assertTrue(app.report_button.disabled)
        self.assertNotIn('143.421',app.metrics.value)
        self.assertIn('need Recalc',app.ring_values.value)
        with self.assertRaises(RuntimeError):app.export()
        app.controls['density_kcf'].value=.30
        app.recalc_button.click()
        self.assertFalse(app.dirty)
        self.assertAlmostEqual(app.current['totals']['factored_weight'],2*original_force)
        self.assertIn('286.843',app.metrics.value)
        self.assertFalse(app.report_button.disabled)

    def test_invalid_input_and_calculation_error_do_not_leave_old_outputs(self):
        app=self.app
        app.controls['ring_count'].value=100
        self.assertIsNone(app.current)
        self.assertEqual(app.recalc_button.description,'Check inputs')
        self.assertIn('Study limits',app.status.value)
        app.controls['ring_count'].value=5
        with patch('ring_wall.widgets.analyze',side_effect=ValueError('Trial calculation failed')):
            app.recalc_button.click()
        self.assertIsNone(app.current);self.assertTrue(app.bundle_button.disabled)
        self.assertEqual(app.recalc_button.description,'Retry calc')
        self.assertIn('Trial calculation failed',app.status.value)
        app.recalc_button.click();self.assertIsNotNone(app.current)

    def test_filters_preserve_complete_results_and_pending_checks(self):
        app=self.app;baseline=deepcopy(app.current)
        app.row_filter.value=2
        self.assertIn('<td>2 / 1</td>',app.ring_values.value)
        self.assertNotIn('<td>1 / 1</td>',app.ring_values.value)
        app.check_view.value='fail'
        self.assertIn('RING-END',app.checks_panel.value)
        self.assertNotIn('>PASS<',app.checks_panel.value)
        app.check_view.value='pending'
        self.assertIn('SHARING',app.checks_panel.value)
        self.assertNotIn('RING-END',app.checks_panel.value)
        app.check_view.value='dc'
        self.assertIn('Equation &amp; values',app.checks_panel.value)
        self.assertIn('PENDING',app.checks_panel.value)
        self.assertEqual(app.current,baseline)

    def test_export_buttons_use_current_case_and_keep_previous_downloads(self):
        app=self.app
        with patch.object(app,'download') as download:
            app.report_button.click()
            download.assert_called_once_with('html')
        first=app.last_export
        report=(first/'ring_wall_report.html').read_bytes()
        with zipfile.ZipFile(first/'Ring_Wall_STM_Exports.zip') as z:
            self.assertEqual(len(z.namelist()),7)
            self.assertEqual(json.loads(z.read('ring_wall_case.json')),app.case)
        app.controls['ring_t_in'].value=1.
        self.assertFalse(app.saved_html_button.disabled)
        with patch.object(app,'download') as download:
            app.saved_html_button.click();download.assert_called_once_with('html')
        with self.assertRaises(RuntimeError):app.export()
        app.recalc_button.click()
        with patch.object(app,'download') as download:
            app.bundle_button.click();download.assert_called_once_with('zip')
        self.assertNotEqual(app.last_export,first)
        self.assertEqual((first/'ring_wall_report.html').read_bytes(),report)
        self.assertEqual(json.loads((app.last_export/'ring_wall_case.json').read_text())['ring_t_in'],1.)
        # Direct/programmatic input changes are also guarded.
        app.case['ring_t_in']=1.25
        with self.assertRaises(RuntimeError):app.export()

    def test_load_case_is_atomic_and_requires_recalc(self):
        app=self.app;previous=deepcopy(app.case)
        bad=deepcopy(previous);bad['coating']='invalid'
        with self.assertRaises(ValueError):app.load_case(bad)
        self.assertEqual(app.case,previous)
        p=default_case();p.update(ring_t_in=1.,auto_grid_spacing=False,grid_spacing_in=6.)
        app.load_case(p)
        self.assertEqual(app.controls['ring_t_in'].value,1.)
        self.assertFalse(app.controls['grid_spacing_in'].disabled)
        self.assertIsNone(app.current)
        app.recalc_button.click();self.assertEqual(app.current['case'],p)

    def test_changed_layout_topology_keeps_live_figures_usable(self):
        app=self.app;figures=dict(app.figures)
        app.controls['ring_count'].value=4
        app.controls['pile_count'].value=3
        app.controls['arch_panels'].value=6
        app.recalc_button.click()
        self.assertEqual(len(app.figures['reactions'].data[0].z),4)
        self.assertEqual(len(app.figures['reactions'].data[0].z[0]),3)
        for key,figure in figures.items():self.assertIs(app.figures[key],figure)
        self.assertEqual(app.current,analyze(app.case))

    def test_cone_controls_update_plot_and_keep_legacy_case_geometry(self):
        app=self.app
        before=list(app.figures['cone'].data[5].z)
        app.controls['cone_slope_hv'].value=1.
        self.assertNotEqual(list(app.figures['cone'].data[5].z),before)
        app.recalc_button.click()
        self.assertAlmostEqual(app.current['cone']['face_rise_in'],6.5)
        self.assertIn('Additional As,req',app.cone_values.value)
        # Old saved cases have no support-model fields; preserve their old meaning.
        legacy=default_case();legacy.pop('support_model');legacy.pop('cone_slope_hv')
        app.load_case(legacy);app.recalc_button.click()
        self.assertEqual(app.case['support_model'],'ring_centers')
        self.assertFalse(app.current['cone']['enabled'])
        self.assertIn('Original pile-center',app.cone_values.value)


if __name__=='__main__':unittest.main()
