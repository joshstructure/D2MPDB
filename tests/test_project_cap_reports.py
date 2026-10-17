"""The registered project cap reports carry the corrected schematics and their saved cases."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('export_project_cap_reports', ROOT / 'scripts' / 'export_project_cap_reports.py')
export = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = export
spec.loader.exec_module(export)


def figure(name, concept, text='', extra=''):
    return (f'<figure class="equation-schematic" data-equation="{name}" data-concept="{concept}">'
            f'<svg role="img" aria-label="sketch"><text>{text}</text></svg>{extra}</figure>')


class SchematicChecks(unittest.TestCase):
    def good(self):
        names = {**export.CONCEPTS}
        parts = [figure(n, c, ' '.join(export.LABELS.get(n, ()))) for n, c in names.items()]
        parts += [figure(n, 'flexure', ' '.join(v)) for n, v in export.LABELS.items() if n not in names]
        return ''.join(parts)

    def test_corrected_set_has_no_problems(self):
        self.assertEqual(export.schematic_problems(self.good()), [])

    def test_report_without_sketches_is_flagged(self):
        self.assertEqual(export.schematic_problems('<html></html>'), ['no equation schematics'])

    def test_wrong_concept_missing_parameter_and_unsafe_markup_are_flagged(self):
        markup = self.good().replace('data-equation="S_leg" data-concept="legs"', 'data-equation="S_leg" data-concept="shear"')
        markup = markup.replace('D_pile', 'D').replace('</svg></figure>', '</svg><script></script></figure>', 1)
        problems = export.schematic_problems(markup)
        self.assertTrue(any('S_leg' in p and 'shear' in p for p in problems))
        self.assertTrue(any('L_cap' in p and 'D_pile' in p for p in problems))
        self.assertTrue(any('script' in p for p in problems))


class RegisteredReports(unittest.TestCase):
    def test_registered_reports_carry_corrected_schematics_and_exact_saved_case(self):
        self.assertEqual(export.check(), [])


if __name__ == '__main__':
    unittest.main()
