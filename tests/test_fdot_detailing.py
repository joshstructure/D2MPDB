"""Policy boundaries, actual inventory and saved exposure behavior."""
from copy import deepcopy
import json
import unittest
from lxml import html
from pier_cap.fdot_detailing import required_cover
from pier_cap.io import load_case
from pier_cap.model import evaluate, set_inputs
from pier_cap.transverse_zones import starting_zone_detail
from pier_cap.widgets import CapNotebook
from tests.case_fixtures import default_case


def checks(case, prefix):
    return [c for c in evaluate(case).checks if c.key.startswith(prefix)]


class FDOTDetailingTests(unittest.TestCase):
    def test_cover_table_boundaries_and_unknowns(self):
        for exposure in ('slight', 'moderate', 'extreme'):
            for surface, expected in [('formed', 4. if exposure == 'extreme' else 3.),
                                      ('earth_water', 4.5 if exposure == 'extreme' else 4.)]:
                self.assertEqual(required_cover(exposure, surface), expected)
                for delta, status in [(0, 'PASS'), (-.01, 'FAIL'), (.01, 'PASS')]:
                    case = set_inputs(default_case(), C_t=expected+delta)
                    case['fdot_detailing'].update(exposure=exposure, top=surface)
                    c = checks(case, 'Chk_fdot_cover_top')[0]
                    self.assertEqual(c.status, status)
                    self.assertAlmostEqual(c.ratio, expected/(expected+delta))
        for exposure, surface in [('unknown', 'formed'), ('slight', 'unknown'), ('unknown', 'unknown')]:
            self.assertIsNone(required_cover(exposure, surface))
        old = default_case(); old.pop('fdot_detailing')
        self.assertTrue(all(c.status == 'PENDING' and c.ratio == 'PENDING' for c in checks(old, 'Chk_fdot_cover_')))

    def test_bar_size_limits_do_not_credit_inactive_bars(self):
        for bar, status in [(3, 'FAIL'), (4, 'PASS'), (11, 'PASS')]:
            case = set_inputs(default_case(), Bar_skin=bar, n_skin=1)
            skin = next(c for c in checks(case, 'Chk_fdot_bar_') if c.label.endswith('Skin'))
            self.assertEqual(skin.status, status)
            self.assertEqual(skin.ratio, 'N/A')  # Policy range, not strength utilization.
        inactive = set_inputs(default_case(), Bar_skin=3, n_skin=0)
        self.assertFalse(any(c.label.endswith('Skin') for c in checks(inactive, 'Chk_fdot_bar_')))
        for bar, status in [(3, 'FAIL'), (4, 'PASS'), (6, 'PASS'), (7, 'FAIL')]:
            c = checks(set_inputs(default_case(), Bar_v=bar), 'Chk_fdot_bar_reference_hoop')[0]
            self.assertEqual(c.status, status)

    def test_actual_runs_are_checked_individually(self):
        base = evaluate(default_case()); case = deepcopy(base.case)
        case['transverse_detail'] = starting_zone_detail(base, 5, 8)
        case['inputs']['Bar_v'] = 3  # Dormant uniform reference cannot fail the actual cage.
        runs = case['transverse_detail']['runs']; runs[0]['bar'] = 7
        selected = checks(case, 'Chk_fdot_bar_run_')
        self.assertEqual(len(selected), len(runs))
        self.assertEqual(selected[0].status, 'FAIL')
        self.assertTrue(all(c.status == 'PASS' for c in selected[1:]))
        self.assertFalse(checks(case, 'Chk_fdot_bar_reference_hoop'))
        self.assertEqual(next(c for c in evaluate(case).checks if c.key == 'Status_overall').status, 'FAIL')

    def test_live_edit_and_round_trip_preserve_face_conditions(self):
        app = CapNotebook(default_case()); self.addCleanup(app.close)
        app.fdot_panel.controls['exposure'].value = 'extreme'
        app.fdot_panel.controls['top'].value = 'formed'
        self.assertEqual(next(c for c in app.current.checks if c.key == 'Chk_fdot_cover_top').status, 'FAIL')
        app.controls['C_t'].value = 4.
        self.assertEqual(next(c for c in app.current.checks if c.key == 'Chk_fdot_cover_top').status, 'PASS')
        saved = load_case(json.dumps(app.case).encode())
        self.assertEqual(saved['fdot_detailing']['exposure'], 'extreme')
        app.load(default_case()); self.assertEqual(app.fdot_panel.controls['exposure'].value, 'unknown')
        app.load(saved); self.assertEqual(app.fdot_panel.controls['top'].value, 'formed')
        doc = html.fromstring(app.register.value)
        row = doc.xpath('//details[@data-check="Chk_fdot_cover_top"]')[0]
        self.assertIn('Table 1.4.2-1', row.text_content())
        self.assertIn('4 in', row.text_content())
        self.assertTrue(row.xpath('.//math//mfrac'))
        self.assertFalse(doc.xpath('//details[@open]'))

    def test_bad_exposure_is_rejected(self):
        case = default_case(); case['fdot_detailing']['exposure'] = 'assumed'
        with self.assertRaisesRegex(ValueError, 'FDOT'):
            evaluate(case)


if __name__ == '__main__':
    unittest.main()
