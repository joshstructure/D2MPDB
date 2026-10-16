"""Regression tests for the generated geometry CAD-table workbook (geometry_tables/).

Rebuild after any notebook, Mathcad, roadway XML or generator change:
    .venv\\Scripts\\python.exe scripts\\build_geometry_cad_tables.py
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import openpyxl  # noqa: E402
from openpyxl.utils import range_boundaries  # noqa: E402

from geometry_tables import sources, verify, workbook  # noqa: E402

REBUILD = r'Rebuild with: .venv\Scripts\python.exe scripts\build_geometry_cad_tables.py'
LIVE_CHART_TABS = ('Profile & Deck Method', 'Camber & Haunch Method', 'FGE Method', 'Bearing Seats Method',
                   'Substructure Method', 'Beam Data Method', 'Clearance Method', 'CAD FGE Method',
                   'CAD Build-Up Method', 'CAD Pedestal Elevs Method')


class GeometryCadTablesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = openpyxl.load_workbook(workbook.OUTPUT, data_only=True)
        cls.formulas = openpyxl.load_workbook(workbook.OUTPUT)
        cls.cfg, cls.model, cls.env = sources.load_notebook_model()

    def value(self, name):
        return verify.named_value(self.values, name)

    def test_workbook_is_current_with_sources_and_generator(self):
        self.assertEqual(self.value('Build_Fingerprint'), workbook.fingerprint(workbook.source_hashes()), REBUILD)

    def test_values_are_cached_and_error_free(self):
        self.assertEqual(verify.formula_errors(self.values), [])
        self.assertIsNotNone(self.value('Sup_Drop'), 'Workbook was saved without Excel recalculation. ' + REBUILD)

    def test_qc_passes(self):
        self.assertEqual(self.value('QC_Overall'), 'PASS')
        failures = [row for row in verify.qc_rows(self.values) if row[3] == 'FAIL']
        self.assertEqual(failures, [])

    def test_results_match_live_notebook_model(self):
        m = self.model
        expected = {
            'Sup_Drop': m.support_drop, 'Prof_G1': m.g1, 'Prof_G2': m.g2, 'Haunch_Min': m.haunch_min * 12,
            'Pier_Top': m.pier['top'], 'EB1_Top': m.end_bents[0]['top'], 'EB2_Top': m.end_bents[1]['top'],
            'Pier_Len': m.pier['length'], 'EB1_Len': m.end_bents[0]['length'], 'EB1_CapSta': m.end_bents[0]['station'],
            'EB2_CapSta': m.end_bents[1]['station'], 'Sp1_BrgA': m.bearing_limits[0][0], 'Sp2_BrgB': m.bearing_limits[1][1],
        }
        if np.isfinite(m.clearance_min):
            expected['Clr_Min'] = m.clearance_min
        for name, value in expected.items():
            with self.subTest(name=name):
                self.assertAlmostEqual(float(self.value(name)), float(value), delta=1e-8)

    def test_fge_table_matches_notebook_deck_top(self):
        ws = self.values['FGE']
        m = self.model
        checked = 0
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
            label = row[1].value
            if not isinstance(label, str) or not (label.startswith('CL Beam') or label.endswith('(deck edge)') or label == 'PGL'):
                continue
            offset = float(row[2].value)
            # The station row is the first "Station (ft)" row above this line.
            r = row[0].row
            while ws.cell(row=r, column=2).value != 'Station (ft)':
                r -= 1
            for c in range(5, 5 + workbook.FGE_INCREMENTS + 3):
                station = float(ws.cell(row=r, column=c).value)
                self.assertAlmostEqual(float(ws.cell(row=row[0].row, column=c).value), float(m.deck_top(station, offset)), delta=1e-9)
                checked += 1
        self.assertEqual(checked, 2 * 5 * (workbook.FGE_INCREMENTS + 3))

    def test_every_tab_is_followed_by_its_method_tab(self):
        names = self.values.sheetnames
        self.assertEqual(names[0], 'Cover')
        for name in names[1:]:
            if name.endswith(' Method'):
                ws = self.formulas[name]
                self.assertTrue(ws._images or ws._charts, f'{name} has no equations, schematics or charts')
                continue
            self.assertIn(f'{name} Method', names)
            self.assertEqual(names.index(f'{name} Method'), names.index(name) + 1)

    def _cells(self, ref):
        sheet, cells = ref.rsplit('!', 1)
        min_col, min_row, max_col, max_row = range_boundaries(cells.replace('$', ''))
        ws = self.formulas[sheet.strip("'")]
        return [ws.cell(row=r, column=c) for r in range(min_row, max_row + 1) for c in range(min_col, max_col + 1)]

    def test_method_figures_are_live_charts(self):
        """Every chart point, error bar and label reads a formula cell, so the figures recalculate with the inputs."""
        for sheet in LIVE_CHART_TABS:
            charts = self.formulas[sheet]._charts
            with self.subTest(sheet=sheet):
                self.assertTrue(charts, f'{sheet} has no live chart')
            for chart in charts:
                for series in chart.series:
                    refs = [series.xVal.numRef.f, series.yVal.numRef.f]          # points: formulas or blank (gaps)
                    if series.errBars is not None:
                        refs.append(series.errBars.plus.numRef.f)
                    for ref in refs:
                        for cell in self._cells(ref):
                            with self.subTest(sheet=sheet, cell=cell.coordinate):
                                self.assertTrue(cell.value is None or str(cell.value).startswith('='),
                                                f'{sheet}!{cell.coordinate} holds a constant {cell.value!r}')
                    name, = self._cells(series.tx.strRef.f)                          # label: text or a text formula
                    with self.subTest(sheet=sheet, cell=name.coordinate):
                        self.assertIsInstance(name.value, str)

    def test_chart_labels_follow_the_tables(self):
        labels = {c.value for row in self.values['Substructure Method'].iter_rows(min_col=16, max_col=16) for c in row}
        for tag in ('EB1', 'Pier'):
            with self.subTest(support=tag):
                self.assertIn(f"cap top {float(self.value(f'{tag}_Top')):.4f}", labels)

    def test_banners_report_inputs_in_sync(self):
        self.assertEqual(self.value('Inputs_Edited'), 0)
        for name in self.formulas.sheetnames:
            if name.endswith(' Method'):
                with self.subTest(sheet=name):
                    self.assertIn('Inputs_Edited', str(self.formulas[name]['B3'].value))
                    self.assertTrue(str(self.values[name]['B3'].value).startswith('LIVE'))

    def test_method_text_quotes_no_frozen_results(self):
        """Current values on the Method tabs are formulas; no constant text repeats a computed result."""
        m = self.model
        frozen = [f'{m.support_drop:.10f}', f'{m.g1 * 100:+.6f}', f'{m.haunch_min * 12:.6f}', f'{m.clearance_min:.4f}']
        for name in self.formulas.sheetnames:
            if not name.endswith(' Method'):
                continue
            for row in self.formulas[name].iter_rows():
                for cell in row:
                    if isinstance(cell.value, str) and not cell.value.startswith('='):
                        for text in frozen:
                            with self.subTest(sheet=name, cell=cell.coordinate):
                                self.assertNotIn(text, cell.value)

    def test_cad_tables_are_live_formulas(self):
        for sheet in ('CAD FGE', 'CAD Build-Up', 'CAD Beam Variables', 'CAD Bearing Plates', 'CAD Pedestal Elevs'):
            ws = self.formulas[sheet]
            formulas = sum(1 for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("="))
            with self.subTest(sheet=sheet):
                self.assertGreater(formulas, 20)

    def test_mathcad_reader_matches_registered_camber_basis(self):
        for basis in self.cfg['camber_basis']:
            data = sources.mathcad_beam_data(basis['span'])
            with self.subTest(span=basis['span']):
                self.assertEqual(data['source_sha256'], basis['source_sha256'])
                self.assertAlmostEqual(data['net_camber_in'], basis['net_camber_in'], places=12)
                total = data['defl_120_in'] + data['defl_dl_nc_in'] + data['defl_dl_c_in']
                self.assertAlmostEqual(total, data['net_camber_in'], places=9)
                self.assertEqual(data['strands'], 39)
                self.assertEqual([z['zone'] for z in data['stirrup_zones']], ['A1', 'A2', 'A3', 'S1', 'S2', 'S3', 'S4'])


if __name__ == '__main__':
    unittest.main()
