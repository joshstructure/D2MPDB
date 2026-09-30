"""Check the standalone notebook's embedded Strength/Service reporting code."""
import ast
import csv
import io
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile


NOTEBOOK = Path(__file__).resolve().parents[1] / "FBMP_Envelope_Extractor.ipynb"


def fixture(include_service=True):
    root = ET.Element("FB-MULTIPIER_MODEL_DATA")
    sub = ET.SubElement(ET.SubElement(root, "MODEL_INFO"), "SUBSTRUCTURE", number="1")
    results = ET.SubElement(sub, "LOAD_CASE_RESULTS")
    cases = [("8", "1", "STRENGTH-I", 1000)]
    if include_service:
        cases += [("11", "4", "SERVICE-I", 10), ("12", "5", "SERVICE-I", 14),
                  ("13", "6", "SERVICE-III", 20)]
    for lc, combo, limit, value in cases:
        case = ET.SubElement(results, "LOAD_CASE", number=lc, combination=combo, limitstate=limit)
        step = ET.SubElement(case, "TIME_STEP", number="1")
        group = ET.SubElement(ET.SubElement(step, "STRUCTURE_INTERNAL_FORCES"), "PIER_CAP")
        element = ET.SubElement(group, "ELEMENT", number="1", elem_number="1")
        for end, node, force in (("I", "5", -value), ("J", "6", value / 2)):
            rec = ET.SubElement(element, "STRUCTURE_ELEMENT_" + end + "_END", **{"node_" + end.lower(): node})
            for tag in ("MOMENT-2", "MOMENT-3", "SHEAR-2", "SHEAR-3", "TORQUE", "AXIAL"):
                ET.SubElement(rec, tag, units="kip" if tag.startswith("SHEAR") or tag == "AXIAL" else "kip-ft").text = str(force)
    summary = ET.SubElement(ET.SubElement(sub, "OUTPUT_SUMMARY"), "STRUCTURE_PIER_CAP_MAX")
    for extreme, value in (("min", -1000), ("max", 500)):
        item = ET.SubElement(summary, "MAX_ITEM", item=extreme + " moment about 3 axis")
        ET.SubElement(item, "ITEM_VALUE", units="kip-ft").text = str(value)
        ET.SubElement(item, "LOAD_CASE").text = "8"
        ET.SubElement(item, "COMBINATION").text = "1"
    return ET.tostring(root)


class EnvelopeNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        cls.source = "".join(notebook["cells"][1]["source"])
        cls.api = {}
        core = cls.source.split('"""Colab notebook interface.', 1)[0]
        exec(compile(core, str(NOTEBOOK), "exec"), cls.api)

    def read(self, service=True):
        return self.api["read_fbmp"](fixture(service), "fixture.xml")

    def test_service_uses_detailed_cases_even_if_native_governors_are_strength(self):
        result = self.read()
        self.assertEqual({r["Limit_state"] for r in result["native"]}, {"STRENGTH-I"})
        rows = self.api["limit_state_table"](result)
        service = [r for r in rows if r["Limit_state_family"] == "Service"]
        self.assertEqual(len(service), 10)
        for row in service:
            for prefix in ("Min", "Max", "Abs_max"):
                self.assertNotEqual(row[prefix + "_Load_case"], "8")

    def test_each_exact_service_state_and_all_components_remain_separate(self):
        rows = self.api["limit_state_table"](self.read())
        self.assertEqual(len(rows), 15)
        for state, minimum, maximum, governor in (("SERVICE-I", -14, 7, "12"), ("SERVICE-III", -20, 10, "13")):
            subset = [r for r in rows if r["Limit_state"] == state]
            self.assertEqual({r["Component"] for r in subset}, {"M2", "M3", "V2", "V3", "T"})
            for row in subset:
                self.assertEqual((row["Min"], row["Max"], row["Abs_max"]), (minimum, maximum, abs(minimum)))
                self.assertEqual(row["Abs_max_signed"], minimum)
                self.assertEqual(row["Abs_max_Load_case"], governor)
                self.assertEqual(row["Abs_max_End"], "I")

    def test_downloaded_tables_are_the_same_rows_used_for_display(self):
        result = self.read()
        rows = self.api["limit_state_table"](result)
        expected = [r for r in rows if r["Limit_state_family"] == "Service"]
        tables = self.api["export_tables"](result)
        self.assertEqual(tables["service_envelopes"], expected)
        self.assertEqual(tables["limit_state_envelope_table"], rows)
        with zipfile.ZipFile(io.BytesIO(self.api["package_results"](result))) as archive:
            actual = list(csv.DictReader(io.StringIO(archive.read("service_envelopes.csv").decode("utf-8-sig"))))
        self.assertEqual(len(actual), len(expected))
        for exported, original in zip(actual, expected):
            self.assertEqual(exported["Limit_state"], original["Limit_state"])
            for key in ("Min", "Max", "Abs_max"):
                self.assertEqual(float(exported[key]), original[key])
                self.assertEqual(exported[key + "_Load_case"], original[key + "_Load_case"])

    def test_missing_service_is_not_generated_from_strength(self):
        result = self.read(False)
        self.assertEqual(self.api["export_tables"](result)["service_envelopes"], [])
        self.assertEqual(len(self.api["limit_state_table"](result)), 5)

    def test_summary_only_cannot_create_service_envelopes(self):
        result = self.read()
        result["raw"] = []
        self.assertEqual(self.api["limit_state_table"](result), [])

    def render_table(self, result):
        context = dict(self.api)
        html, tables = [], []
        context.update(HTML=lambda text: text, display=html.append,
                       show_table=lambda rows, **kwargs: tables.append(rows))
        node = next(n for n in ast.parse(self.source).body if isinstance(n, ast.FunctionDef) and n.name == "display_limit_state_tables")
        exec(compile(ast.Module(body=[node], type_ignores=[]), "table-display", "exec"), context)
        context["display_limit_state_tables"](result, context["limit_state_table"](result))
        return "\n".join(html), tables

    def test_notebook_readout_displays_service_values_and_case_labels(self):
        html, tables = self.render_table(self.read())
        self.assertIn("<h2>Strength envelopes</h2>", html)
        self.assertIn("<h2>Service envelopes</h2>", html)
        self.assertIn("SERVICE-I: LC 11, C4", html)
        service = [r for table in tables for r in table if r["Limit state"] == "SERVICE-I"]
        self.assertEqual(len(service), 5)
        self.assertTrue(all(r["Minimum"] == -14 and r["Maximum"] == 7 for r in service))

    def test_missing_service_message_and_no_data_table(self):
        html, tables = self.render_table(self.read(False))
        self.assertIn("No service load cases were exported", html)
        self.assertTrue(all(r["Limit state"].startswith("STRENGTH") for t in tables for r in t))

    def test_single_file_launch_renders_directly_as_cell_output(self):
        context = dict(self.api)
        made = []
        context["make_app"] = lambda result: made.append(result) or "APP"
        node = next(n for n in ast.parse(self.source).body if isinstance(n, ast.FunctionDef) and n.name == "launch_fbmp")
        exec(compile(ast.Module(body=[node], type_ignores=[]), "launch", "exec"), context)
        output = context["launch_fbmp"]({"fixture.xml": fixture()})
        self.assertEqual(output["active"], "APP")
        self.assertEqual(len(made), 1)
        # No widgets dependency was supplied: this path cannot wrap tables in a widget output.


if __name__ == "__main__":
    unittest.main()
