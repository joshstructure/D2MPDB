"""Numerical and data-loading regressions for the self-contained geometry notebook."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'Bridge_Geometry_2 Beam_V2.ipynb'


@contextlib.contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class BridgeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
        cls.env = {}
        with working_directory(ROOT):
            for index in (3, 4, 6, 7):
                exec(''.join(cls.notebook['cells'][index]['source']), cls.env)
        cls.config = copy.deepcopy(cls.env['CONFIG'])
        cls.config['roadway']['xml_path'] = str(ROOT / 'Geometry Report.xml')
        cls.model = cls.env['BridgeModel'](cls.config)

    def tearDown(self):
        plt.close('all')

    def build(self, **pier_changes):
        config = copy.deepcopy(self.config)
        config['pier'].update(pier_changes)
        return self.env['BridgeModel'](config)

    def test_default_cutoff_and_unchanged_geometry(self):
        piles = self.model.pier['pile_elevations']
        self.assertEqual(len(piles), 4)
        np.testing.assert_allclose(piles['Cap underside (ft)'], 40.73325, rtol=0, atol=1e-8)
        np.testing.assert_allclose(piles['Pile cutoff (ft)'], 41.73325, rtol=0, atol=1e-8)
        np.testing.assert_allclose(piles['Offset (ft)'], [-7.5, -2.5, 2.5, 7.5])
        self.assertAlmostEqual(self.model.pier['length'], 19 + 2/12)
        self.assertAlmostEqual(self.model.pier['volume_ft3'], 230)
        self.assertGreater(self.model.covered_length, 200)
        self.assertFalse(self.model.full_road_coverage)

    def test_slope_and_shift_use_local_underside(self):
        model = self.build(cross_slope=.02, center_offset_ft=.25,
                           top_center_ft=43, minimum_pedestal_cl_in=None)
        piles = model.pier['pile_elevations']
        np.testing.assert_allclose(piles['Pile cutoff (ft)'], [40.85, 40.95, 41.05, 41.15], atol=1e-10)
        np.testing.assert_allclose(piles['Cap underside (ft)'], [39.85, 39.95, 40.05, 40.15], atol=1e-10)

    def test_embedment_depth_and_elevation_changes_propagate(self):
        for inches in (0, 6, 12, 24, 36):
            with self.subTest(inches=inches):
                piles = self.build(pile_embedment_in=inches).pier['pile_elevations']
                np.testing.assert_allclose(piles['Pile cutoff (ft)'], 40.73325 + inches/12, atol=1e-8)
        piles = self.build(depth_ft=4).pier['pile_elevations']
        np.testing.assert_allclose(piles['Pile cutoff (ft)'], 40.73325, atol=1e-8)
        config = copy.deepcopy(self.config)
        config['profile']['start_elev_ft'] += 2
        config['profile']['end_elev_ft'] += 2
        elevated = self.env['BridgeModel'](config)
        np.testing.assert_allclose(elevated.pier['pile_elevations']['Pile cutoff (ft)'], 43.73325, atol=1e-8)

    def test_invalid_embedment_rejected(self):
        for value in (-1, 36.01, float('nan'), float('inf'), True, [12]):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '[Ee]mbedment'):
                self.build(pile_embedment_in=value)

    def test_missing_cap_datum_never_invents_cutoff(self):
        model = self.build(top_center_ft=None, minimum_pedestal_cl_in=None)
        self.assertTrue(model.pier['missing'])
        self.assertTrue(model.pier['pile_elevations']['Pile cutoff (ft)'].isna().all())

    def test_longitudinal_and_transverse_plots_use_cutoff(self):
        figure = self.env['longitudinal_figure'](self.model, self.model.pier['station'])
        collection = next(c for c in figure.axes[0].collections if c.get_label() == 'Pile cutoff')
        np.testing.assert_allclose(collection.get_offsets()[:, 0], 1700.57)
        np.testing.assert_allclose(collection.get_offsets()[:, 1], 41.73325, atol=1e-8)
        geometry = self.env['section_geometry'](self.model, 1700.57)[0]
        piles = [c for c in geometry['components'] if c['kind'] == 'Pile']
        self.assertEqual(len(piles), 4)
        np.testing.assert_allclose([c['xy'][:, 1].max() for c in piles], 41.73325, atol=1e-8)
        end = self.env['section_geometry'](self.model, self.model.start)[0]
        self.assertFalse(any(c['kind'] == 'Pile' for c in end['components']))
        hidden = self.env['longitudinal_figure'](self.model, 1700.57, layers=('Deck',))
        self.assertFalse(any(c.get_label() == 'Pile cutoff' for c in hidden.axes[0].collections))

    def test_existing_xml_and_custom_paths_need_no_network(self):
        loader = self.env['ensure_roadway_file']
        with patch.dict(self.env, urlopen=lambda *a, **k: self.fail('Unexpected network access')):
            self.assertEqual(loader(ROOT/'Geometry Report.xml'), ROOT/'Geometry Report.xml')
            with self.assertRaises(FileNotFoundError):
                loader(ROOT/'missing-custom.xml')

    def test_fresh_runtime_download_and_reuse(self):
        payload = (ROOT/'Geometry Report.xml').read_bytes()
        calls = []
        def download(url, timeout):
            calls.append(url)
            return io.BytesIO(payload)
        with tempfile.TemporaryDirectory() as folder, working_directory(folder):
            with patch.dict(self.env, urlopen=download):
                path = self.env['ensure_roadway_file']('Geometry Report.xml')
                self.assertEqual(path.read_bytes(), payload)
                self.env['ensure_roadway_file']('Geometry Report.xml')
        self.assertEqual(calls, [self.env['ROADWAY_DATA_URL']])

    def test_failed_download_does_not_cache_html_or_partial_data(self):
        for payload in (b'<html>error</html>', b'<broken'):
            with tempfile.TemporaryDirectory() as folder, working_directory(folder):
                with patch.dict(self.env, urlopen=lambda *a, **k: io.BytesIO(payload)):
                    with self.assertRaisesRegex(RuntimeError, 'GitHub'):
                        self.env['ensure_roadway_file']('Geometry Report.xml')
                self.assertFalse(Path('Geometry Report.xml').exists())

    def test_no_drive_authentication_in_current_notebook(self):
        code = '\n'.join(''.join(c['source']) for c in self.notebook['cells'] if c['cell_type']=='code')
        self.assertNotIn('google.colab', code)
        self.assertNotIn('/content/drive', code)
        self.assertNotIn('drive.mount', code)


if __name__ == '__main__':
    unittest.main()
