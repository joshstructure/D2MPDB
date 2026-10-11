"""Live geometry stays usable while calculation results are explicitly stale."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from lxml import html
from pier_cap.widgets import CapNotebook
from pier_cap.visuals import checks_html
from pier_cap.model import evaluate
from tests.test_end_grid import case


class ManualCalculationTests(unittest.TestCase):
    def setUp(self):
        self.app=CapNotebook(case());self.addCleanup(self.app.close)

    def test_edits_tabs_starting_layout_and_json_load_do_not_run_full_checks(self):
        app=self.app;chart=app.cage_3d_widget
        with patch('pier_cap.widgets.evaluate',side_effect=AssertionError('automatic calculation')) as full, \
             patch('pier_cap.model.evaluate',side_effect=AssertionError('hidden calculation')) as hidden, \
             patch('pier_cap.section_widgets.evaluate',side_effect=AssertionError('study listener calculation')) as study_calc, \
             patch('pier_cap.io.evaluate',side_effect=AssertionError('import calculation')) as imported:
            from pier_cap.section_widgets import SectionStudy
            study=SectionStudy(app);self.addCleanup(study.close)
            app.controls['n_N1'].value+=1
            app.end_grid.rows['horizontal']['count'].value=5
            from tests.case_fixtures import default_case
            app.load(default_case())
            app.transverse_panel.generate.click()
            self.assertNotIn('Not applied',app.transverse_panel.status.value)
            for index in range(7):app.plot_tabs.selected_index=index
            app.check_view.value='dc_descending'
            app.case_import.load(json.dumps(app.case).encode(),'selected_case.json')
            self.assertIn('LOADED SUCCESSFULLY',app.case_import.status.value)
            full.assert_not_called();hidden.assert_not_called();imported.assert_not_called();study_calc.assert_not_called()
        self.assertIs(chart,app.cage_3d_widget)
        self.assertEqual(app.recalc_button.description,'Recalc');self.assertTrue(app.dirty)
        self.assertFalse(app.calculating);self.assertEqual(app.current.checks,[])
        self.assertIn('Recalc',app.register.value);self.assertEqual(app.metrics.value,'')
        self.assertTrue(app.case_report_button.disabled)
        self.assertTrue(all('Recalc' in w.value for w in app.steel_readouts.values()))

    def test_one_click_calculates_latest_case_and_next_edit_retires_all_results(self):
        app=self.app;app.check_view.value='dc_descending'
        app.end_grid.rows['horizontal']['count'].value=5
        expected=deepcopy(app.case)
        with patch.object(app.refresh_driver,'calculate',wraps=app.refresh_driver.calculate) as full:
            app.recalc_button.click();app.recalc_button.click()
            full.assert_called_once_with(expected)
        self.assertEqual(app.recalc_button.description,'Calc done');self.assertFalse(app.dirty)
        self.assertFalse(app.case_report_button.disabled)
        self.assertEqual([(c.key,c.ratio,c.status) for c in app.current.checks],
                         [(c.key,c.ratio,c.status) for c in evaluate(expected).checks])
        self.assertIn('Largest numerical',app.register.value)
        app.plot_tabs.selected_index=1
        app.controls['n_N1'].value+=1
        for index in (1,2,3,4,6):app.plot_tabs.selected_index=index
        self.assertTrue(app.dirty);self.assertEqual(app.recalc_button.description,'Recalc')
        self.assertEqual(app.check_view.value,'dc_descending')
        self.assertIn('Recalc',app.results.children[0].value)
        self.assertNotIn('data-check=',app.register.value)
        self.assertIn('Recalc',app.lrfd_panel.result.value)
        app.recalc_button.click();self.assertIn('Largest numerical',app.register.value)

    def test_running_error_retry_and_invalid_input_states(self):
        app=self.app;chart=app.cage_3d_widget
        def fail(c):
            self.assertEqual(app.recalc_button.description,'Calculating…')
            self.assertTrue(app.recalc_button.disabled)
            app.recalc_button.click()
            raise ValueError('test calculation error')
        with patch.object(app.refresh_driver,'calculate',side_effect=fail) as full:
            app.recalc_button.click();full.assert_called_once()
        self.assertEqual(app.recalc_button.description,'Retry calc')
        self.assertTrue(app.dirty);self.assertIn('test calculation error',app.banner.value)
        self.assertIs(chart,app.cage_3d_widget);self.assertIsNotNone(app.current)
        app.recalc_button.click();self.assertEqual(app.recalc_button.description,'Calc done')
        width=app.controls['b'].value;app.controls['b'].value=0
        self.assertEqual(app.recalc_button.description,'Check inputs');self.assertIsNone(app.current)
        with patch.object(app.refresh_driver,'calculate') as full:
            app.recalc_button.click();full.assert_not_called()
        app.controls['b'].value=width
        self.assertEqual(app.recalc_button.description,'Recalc')
        self.assertIs(chart,app.cage_3d_widget)

    def test_export_handlers_cannot_export_unchecked_draft(self):
        app=self.app
        with patch('pier_cap.widgets.export_bundle') as export,patch('pier_cap.blockpad_widgets.export_bundle') as bpad:
            app._export(None);app.blockpad_export.export()
            export.assert_not_called();bpad.assert_not_called()
        self.assertIn('RECALC NEEDED',app.case_export_status.value)

    def test_imported_force_view_shows_demands_without_hidden_resistance_calculation(self):
        from pier_cap.fbmp import import_fbmp_xml
        with patch('pier_cap.model.evaluate',side_effect=AssertionError('hidden calculation')) as full:
            imported=import_fbmp_xml('tests/fixtures/fbmp_610_cap.xml')
            self.app.load(imported,import_name='cap.xml')
            self.app.plot_tabs.selected_index=4
            self.assertIsNotNone(self.app.force_diagrams.figure)
            self.assertFalse(any((t.meta or {}).get('role') for t in self.app.force_diagrams.figure.data))
            self.assertIn('Recalc needed',self.app.force_diagrams.resistance_notice.value)
            full.assert_not_called()


class CheckSortTests(unittest.TestCase):
    def test_descending_uses_full_precision_retains_ties_and_places_nonnumeric_last(self):
        checks=[SimpleNamespace(label=label,ratio=ratio,status=status,basis='',governing='')
                for label,ratio,status in [('pending','PENDING','PENDING'),('low',.4,'PASS'),
                    ('tie first',1.23441,'FAIL'),('higher',1.23449,'FAIL'),
                    ('tie second',1.23441,'FAIL'),('excluded','EXCLUDED','EXCLUDED')]]
        e=SimpleNamespace(checks=checks,issues=[],status='PENDING')
        with patch('pier_cap.check_working.details_html',return_value='<details>Equation</details>'):
            doc=html.fromstring(checks_html(e,view='dc_descending'))
        self.assertEqual(doc.xpath('//tbody/tr/td[1]/text()'),
                         ['higher','tie first','tie second','low','pending','excluded'])
        self.assertEqual(len(doc.xpath('//details')),6)
        self.assertEqual(e.checks,checks);self.assertEqual(e.checks[0].label,'pending')
        self.assertIn('Combined notebook status',doc.text_content())
