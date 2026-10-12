"""XML elevation sources, datum conversion, and propagation to saved/exported results."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lxml import etree as E
from openpyxl import load_workbook

from pier_cap.pile_review import import_pile_xml, review_elevations, validate_saved_review
from pier_cap.widgets import CapNotebook


FIXTURE = Path(__file__).parent / 'fixtures' / 'fbmp_610_piles.xml'


def soil_xml(ground='21.50', *, unit='ft', extra=''):
    root = E.fromstring(FIXTURE.read_bytes())
    root.find('.//PILE_GROUP').append(E.fromstring(
        '<SOIL_INPUT_DATA><AXIAL>'
        '<LAYER number="2" soilset="1"><TOP><ELEV units="ft">-20</ELEV></TOP></LAYER>'
        f'<LAYER number="1" soilset="1"><TOP><ELEV units="{unit}">{ground}</ELEV></TOP>'
        '<ELEV_PIEZO units="ft">18</ELEV_PIEZO></LAYER>' + extra +
        '</AXIAL><LATERAL><LAYER number="1" soilset="1"><TOP>'
        '<ELEV units="ft">99</ELEV></TOP></LAYER></LATERAL></SOIL_INPUT_DATA>'))
    return E.tostring(root)


class XmlElevationTests(unittest.TestCase):
    def test_first_axial_layer_and_pile_head_define_defaults(self):
        review = import_pile_xml(soil_xml())
        self.assertEqual(review['soil_top_elevations_ft'], {'1': 21.5})
        self.assertEqual(review_elevations(review),
                         dict(cutoff_ft=41.4175, ground_ft=21.5, issues=[]))
        restored = json.loads(json.dumps(review))
        validate_saved_review(restored)
        self.assertEqual(review_elevations(restored), review_elevations(review))

    def test_negative_and_zero_datums_keep_sign_and_units(self):
        for ground, z, cutoff in [('-2.5', 24, -2), ('0', 0, 0)]:
            review = import_pile_xml(soil_xml(ground))
            for pile in review['piles'].values():
                pile['head_xyz_in'] = [0, 0, z]
            values = review_elevations(review)
            self.assertEqual(values['ground_ft'], float(ground))
            self.assertEqual(values['cutoff_ft'], cutoff)

    def test_missing_ground_and_legacy_reviews_still_recover_cutoff(self):
        review = import_pile_xml(FIXTURE)
        review.pop('soil_top_elevations_ft')
        validate_saved_review(review)
        values = review_elevations(review)
        self.assertEqual(values['cutoff_ft'], 41.4175)
        self.assertIsNone(values['ground_ft'])
        self.assertIn('Top soil-layer elevation is unavailable', values['issues'][0])

    def test_multiple_soil_sets_or_heads_need_a_common_elevation(self):
        for ground in ('21.50', '24.50'):
            extra = f'<LAYER number="1" soilset="2"><TOP><ELEV units="ft">{ground}</ELEV></TOP></LAYER>'
            review = import_pile_xml(soil_xml(extra=extra))
            values = review_elevations(review)
            self.assertEqual(values['ground_ft'], 21.5 if ground == '21.50' else None)
            self.assertEqual(bool(values['issues']), ground != '21.50')
        review['piles']['1']['head_xyz_in'] = [0, 0, -480]
        values = review_elevations(review)
        self.assertIsNone(values['cutoff_ft'])
        self.assertIn('Pile heads have different elevations', values['issues'][0])

    def test_invalid_soil_sources_are_rejected(self):
        for raw in (soil_xml(unit='in'), soil_xml('NaN'),
                    soil_xml(extra='<LAYER number="1" soilset="1"/>'),
                    soil_xml(extra='<LAYER number="2" soilset="2"/>'),
                    soil_xml(extra='<LAYER number="1"/>'),
                    soil_xml().replace(b'<ELEV units="ft">21.50</ELEV>', b'')):
            with self.subTest(raw=raw[-100:]), self.assertRaises(ValueError):
                import_pile_xml(raw)

    def test_invalid_saved_elevation_metadata_is_rejected(self):
        review = import_pile_xml(soil_xml())
        for invalid in ({'1': float('nan')}, {'1': True}, {'1': '21.5'}, []):
            bad = deepcopy(review)
            bad['soil_top_elevations_ft'] = invalid
            with self.assertRaisesRegex(ValueError, 'top-soil elevations'):
                validate_saved_review(bad)
        review['piles']['1']['head_xyz_in'] = [0, 0, float('inf')]
        with self.assertRaisesRegex(ValueError, 'pile-head coordinates'):
            validate_saved_review(review)


class ElevationWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app = CapNotebook()
        self.addCleanup(self.app.close)
        self.panel = self.app.pile_review
        self.raw = soil_xml()
        self.panel._import(self.raw, 'MinimumTip.xml')

    def test_imported_elevations_feed_plot_trials_and_excel(self):
        p = self.panel
        self.assertEqual(float(p.reference.value), 21.5)
        self.assertEqual(float(p.cutoff.value), 41.4175)
        self.assertAlmostEqual(p.figures['profiles'].data[0].y[0], 41.4175)
        p.trial_text.value = '1,2,4,20,1\n2,2,4,15,1.01'
        p.trial_label.value = 'Pier 2'
        p.run_trials.click()
        self.assertEqual(p.trial_result['tip_elevation_ft'], -3.5)
        tip = 41.4175 - p.fixity_result['governors'][0]['second_vertical_ft'] - 5
        self.assertAlmostEqual(p.minimum_tip_result['tip_elevation_ft'], tip)
        with TemporaryDirectory() as folder:
            p.save_handoff(folder)
            workbook = load_workbook(Path(folder) / 'Pier 2.xlsx')
            self.addCleanup(workbook.close)
            self.assertEqual(workbook.active['A1'].value, 'Pier 2')
            row = next(r for r in workbook.active.values if r[0] == 'Second zero crossing')
            self.assertAlmostEqual(row[1], 21.5 - tip)
            self.assertAlmostEqual(row[2], tip)

    def test_override_restore_reset_and_same_file_reload(self):
        p = self.panel
        p.cutoff.value = '40'
        p.reference.value = '20'
        p.trial_text.value = '1,2,4,20,1\n2,2,4,15,1.01'
        p.trial_label.value = 'Saved trial'
        saved = p.snapshot()
        p.restore(json.loads(json.dumps(saved)))
        self.assertEqual((p.cutoff.value, p.reference.value), ('40', '20'))
        self.assertIn('current field differs', p.elevation_source.value)
        p.use_xml_elevations.click()
        self.assertEqual((float(p.cutoff.value), float(p.reference.value)), (41.4175, 21.5))
        self.assertNotIn('current field differs', p.elevation_source.value)
        self.assertEqual(p.trial_text.value, saved['controls']['trial_text'])
        p.restore(saved)
        p._import(self.raw, 'MinimumTip.xml')
        self.assertEqual((float(p.cutoff.value), float(p.reference.value)), (41.4175, 21.5))
        self.assertEqual(p.trial_label.value, 'Saved trial')
        self.assertEqual(p.trial_text.value, saved['controls']['trial_text'])
        before = p.snapshot()
        with self.assertRaises(ValueError):
            p._import(soil_xml(unit='in'), 'Invalid.xml')
        self.assertEqual(p.snapshot(), before)
        p._import(soil_xml('24.5'), 'NextStudy.xml')
        self.assertEqual((float(p.cutoff.value), float(p.reference.value)), (41.4175, 24.5))
        self.assertEqual((p.trial_label.value, p.trial_text.value), ('', ''))


if __name__ == '__main__':
    unittest.main()
