"""Real widget callbacks, stale-result gates and plot topology."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ring_wall.model import analyze,default_case
from ring_wall.widgets import RingWallNotebook
from ring_wall.ui_support import PanelTabs


class RingWallWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1],prefix='.ring-wall-test-');self.app=RingWallNotebook(export_root=Path(self.temp.name)/'exports')
    def tearDown(self):self.app.close();self.temp.cleanup()
    def test_initial_live_outputs_do_not_export(self):
        a=self.app;self.assertEqual(a.current,analyze());self.assertFalse(a.export_root.exists())
        self.assertEqual(a.recalc_button.description,'Calc done');self.assertIn('LIMITED SCOPE',a.status.value)
        self.assertAlmostEqual(sum(sum(z) for z in a.figures['reactions'].data[0].z),a.current['totals']['factored_weight'])
        self.assertNotIn('arch_rise_in',a.controls);self.assertIn('weld_leg_in',a.controls)
        self.assertIn('#5 at 11',a.steel_panel.value)
    def test_navigation_mounts_one_panel_preserves_calculation(self):
        a=self.app;r=a.current
        for tabs in (a.plot_tabs,a.input_tabs):
            self.assertIsInstance(tabs,PanelTabs)
            for i in list(range(len(tabs.panels)))+[0,2,1]:
                tabs.buttons[i].click();self.assertEqual(tabs.content.children,(tabs.panels[i],));self.assertIs(a.current,r)
    def test_edit_updates_drawings_and_invalidates_all_outputs(self):
        a=self.app;fig=a.figures['layout'];ys=list(fig.data[2].y);original=a.current['totals']['factored_weight']
        a.controls['ring_spacing_in'].value=34.;self.assertIs(fig,a.figures['layout']);self.assertNotEqual(ys,list(fig.data[2].y))
        self.assertIsNone(a.current);self.assertTrue(all(b.disabled for b in a.export_buttons.values()))
        self.assertIn('need Recalc',a.ring_values.value)
        with self.assertRaises(RuntimeError):a.export()
        a.controls['density_kcf'].value=.30;a.recalc_button.click()
        self.assertAlmostEqual(a.current['totals']['factored_weight'],2*original);self.assertFalse(a.report_button.disabled)
    def test_invalid_and_failed_calc_do_not_retain_results(self):
        a=self.app;a.controls['ring_count'].value=100;self.assertIsNone(a.current);self.assertEqual(a.recalc_button.description,'Check inputs')
        a.controls['ring_count'].value=5
        with patch('ring_wall.workbench.analyze',side_effect=ValueError('test calculation failure')):a.recalc_button.click()
        self.assertIsNone(a.current);self.assertEqual(a.recalc_button.description,'Retry calc');self.assertTrue(a.bundle_button.disabled)
        a.recalc_button.click();self.assertIsNotNone(a.current)
    def test_filtering_preserves_complete_results(self):
        a=self.app;r=deepcopy(a.current);a.row_filter.value=2
        self.assertIn('<td>2 / 1</td>',a.ring_values.value);self.assertNotIn('<td>1 / 1</td>',a.ring_values.value)
        a.check_view.value='fail';self.assertIn('RING-END',a.checks_panel.value);self.assertNotIn('>PASS<',a.checks_panel.value)
        a.check_view.value='pending';self.assertIn('SHARING',a.checks_panel.value);self.assertIn('R1-P1-WELD',a.checks_panel.value)
        self.assertEqual(a.current,r)
    def test_export_keeps_previous_downloads_and_blocks_direct_changes(self):
        a=self.app
        with patch.object(a,'download') as download:a.report_button.click();download.assert_called_once_with('html')
        first=a.last_export;data=(first/'ring_wall_report.html').read_bytes();a.controls['ring_t_in'].value=1.
        self.assertFalse(a.saved_html_button.disabled)
        with patch.object(a,'download') as download:a.saved_html_button.click();download.assert_called_once_with('html')
        with self.assertRaises(RuntimeError):a.export()
        a.recalc_button.click()
        with patch.object(a,'download') as download:a.bundle_button.click();download.assert_called_once_with('zip')
        self.assertNotEqual(a.last_export,first);self.assertEqual((first/'ring_wall_report.html').read_bytes(),data)
        a.case['weld_leg_in']=.5
        with self.assertRaises(RuntimeError):a.export()
    def test_load_case_is_atomic_and_requires_recalc(self):
        a=self.app;before=deepcopy(a.case)
        with self.assertRaises(ValueError):a.load_case(before|dict(coating='invalid'))
        self.assertEqual(a.case,before);p=default_case()|dict(auto_grid_spacing=False,grid_spacing_in=6.,ring_t_in=1.)
        a.load_case(p);self.assertIsNone(a.current);self.assertFalse(a.controls['grid_spacing_in'].disabled)
        a.recalc_button.click();self.assertEqual(a.current['case'],p)
    def test_changed_topology_reuses_live_figures(self):
        a=self.app;figures=dict(a.figures);a.controls['ring_count'].value=4;a.controls['pile_count'].value=3;a.recalc_button.click()
        self.assertEqual(len(a.figures['reactions'].data[0].z),4);self.assertEqual(len(a.figures['reactions'].data[0].z[0]),3)
        for key,fig in figures.items():self.assertIs(a.figures[key],fig)
        self.assertEqual(a.current,analyze(a.case))
    def test_legacy_case_migration_visible(self):
        p=default_case();p.pop('schema_version');p.update(support_model='face_transfer',bearing_fraction=.5)
        self.app.load_case(p);self.assertIn('Legacy case migrated',self.app.load_status.value);self.assertNotIn('support_model',self.app.case)


if __name__=='__main__':unittest.main()
