"""Regression tests for the Bridge Development Report (bdr/).

Rebuild after any registered source, facts.json or generator change:
    .venv\\Scripts\\python.exe scripts\\build_bdr.py
The committed HTML is byte-identical to a fresh build (no clock times); the manifest
records the SHA-256 of every project file the report reads.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bdr import build, sources  # noqa: E402

OUT = sources.PKG / "output"
REBUILD = r"Rebuild with: .venv\Scripts\python.exe scripts\build_bdr.py"
REQUIRED_HEADINGS = [
    "Executive summary", "1. Introduction and project description", "2. Design criteria", "3. Site and existing conditions",
    "4. Roadway and bridge geometry", "5. Structure type selection", "6. Superstructure", "7. Substructure", "8. Foundations",
    "9. Retaining walls", "10. Temporary traffic control, constructability and construction time",
    "11. Bicycle and pedestrian facilities and ADA access", "12. Aesthetics", "13. Quantities, unit costs and cost estimate",
    "14. 30% Structures Plans", "15. Conclusions and recommendations", "Appendix A. General plan",
    "Appendix B. Typical section and elevation", "Appendix C. Preliminary substructure sheets", "Appendix D. Geotechnical sections",
    "Appendix E. Design calculations index", "Appendix F. Source register", "Appendix G. BDR submittal checklist",
    "Appendix H. Open items, assumptions and decisions",
]


class BdrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((OUT / build.MANIFEST_NAME).read_text(encoding="utf-8"))
        cls.html = (OUT / build.HTML_NAME).read_text(encoding="utf-8")
        cls.data = json.loads((OUT / build.DATA_NAME).read_text(encoding="utf-8"))

    def test_manifest_sources_are_current(self):
        for sid, rec in self.manifest["sources"].items():
            path = ROOT / rec["path"]
            self.assertTrue(path.exists(), f"{sid}: {rec['path']} missing")
            self.assertEqual(sources.sha256(path), rec["sha256"], f"{sid} ({rec['path']}) changed. {REBUILD}")
        self.assertEqual(set(self.manifest["sources"]), set(sources.SOURCES), "SOURCES changed. " + REBUILD)

    def test_committed_outputs_equal_a_fresh_build(self):
        for name, digest in self.manifest["outputs"].items():
            self.assertEqual(sources.sha256(OUT / name), digest, f"{name} edited after the build. {REBUILD}")
        with tempfile.TemporaryDirectory() as tmp:
            fresh = build.build(Path(tmp))
        self.assertEqual(fresh["outputs"], self.manifest["outputs"], "Generator output differs. " + REBUILD)

    def test_report_follows_the_fdm_outline(self):
        for heading in REQUIRED_HEADINGS:
            self.assertTrue(f">{heading}" in self.html, f"heading missing: {heading}")
        self.assertTrue("Bridge Development Report" in self.html)
        self.assertTrue("FDM 121.9" in self.html)

    def test_report_states_the_registered_configuration(self):
        d = self.data["derived"]
        self.assertAlmostEqual(d["span1"] + d["span2"], d["total"], places=6)
        self.assertTrue(f'{d["total"]:,.2f} ft' in self.html)
        self.assertTrue("FIB-36" in self.html)
        for support in ("EB1", "EB2", "PIER"):
            row = self.data["pile_tables"][support]["row"]
            self.assertTrue(str(row[2]) in self.html, f"{support} nominal bearing resistance missing")
        self.assertEqual(len(self.data["calc_modules"]), 16)
        self.assertEqual(self.data["calc_modules"][0]["number"], "C001")
        self.assertEqual(self.data["calc_modules"][-1]["number"], "C018")

    def test_every_flagged_item_is_listed_in_the_open_items_appendix(self):
        items = self.data["open_items"]
        self.assertEqual(self.manifest["open_items"], len(items))
        appendix = self.html.split("H.1 Items flagged in this report", 1)[1]
        for item in items:
            self.assertTrue(item["text"][:60].replace("'", "&#x27;") in appendix, item["text"][:60])
        # No unsupported statement masquerades as a fact: every FDM item the record lacks is flagged.
        facts = json.loads(sources.SOURCES["FACTS"].read_text(encoding="utf-8"))
        missing = [k for k, v in facts["bdr_items"].items() if v["status"] == "to be supplied"]
        self.assertGreaterEqual(len(items), len(missing))

    def test_figures_are_embedded(self):
        self.assertGreaterEqual(self.html.count("<svg"), 3)             # typical section and elevation, each twice
        self.assertGreaterEqual(self.html.count("data:image/png;base64,"), 17)   # P-1 and the 16 substructure sheets

    def test_no_placeholders_leak(self):
        text = re.sub(r"<style>.*?</style>", " ", self.html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        for leak in (">None<", " None ", ": None", "nan ", "{", "}"):
            self.assertFalse(leak in text, f"placeholder leaked: {leak!r}")


if __name__ == "__main__":
    unittest.main()
