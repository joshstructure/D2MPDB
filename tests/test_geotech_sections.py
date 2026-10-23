"""Regression tests for the geotechnical sections (geotech_sections/).

Rebuild after a FreeCAD model change or a cuts.json edit (re-cuts the model
with freecadcmd and the terrain TINs of the CAD tooling):
    .venv\\Scripts\\python.exe scripts\\build_geotech_sections.py --extract
After a generator or report-template change only:
    .venv\\Scripts\\python.exe scripts\\build_geotech_sections.py
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from geotech_sections import sections  # noqa: E402

PKG = ROOT / "geotech_sections"
SNAPSHOT = PKG / "data" / "sections_snapshot.json"
OUT = PKG / "output"
MODEL = (ROOT / "project_current" / "geometry" / "freecad" /
         "B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd")
REBUILD = r"Rebuild with: .venv\Scripts\python.exe scripts\build_geotech_sections.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class GeotechSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.manifest = json.loads((OUT / sections.MANIFEST_NAME).read_text(encoding="utf-8"))

    def test_snapshot_is_from_the_registered_model_and_cuts(self):
        self.assertEqual(self.snap["model_sha256"], sha(MODEL), "The FreeCAD model changed. " + REBUILD + " --extract")
        self.assertEqual(self.snap["cuts_sha256"], sha(PKG / "cuts.json"), "cuts.json changed. " + REBUILD + " --extract")

    def test_outputs_are_current_with_snapshot_and_generator(self):
        self.assertEqual(self.manifest["snapshot_sha256"], sha(SNAPSHOT), REBUILD)
        with tempfile.TemporaryDirectory() as tmp:
            fresh = sections.write_outputs(SNAPSHOT, tmp)
            self.assertEqual(fresh["files"], self.manifest["files"], "Generator output differs. " + REBUILD)
        for name, digest in self.manifest["files"].items():
            self.assertEqual(sha(OUT / name), digest, name + " edited after the build. " + REBUILD)

    def test_stationing(self):
        self.assertEqual(self.snap["stations"], {"EB1": 1593.22, "PIER": 1700.57, "EB2": 1805.47})

    def test_sections_reach_100_ft_beyond_the_project(self):
        cuts = json.loads((PKG / "cuts.json").read_text(encoding="utf-8"))
        self.assertEqual([s["id"] for s in self.snap["sections"]], [c["id"] for c in cuts["cuts"]])
        for s in self.snap["sections"]:
            self.assertGreaterEqual(s["clearance_ft"], 100.0, s["id"])
            lo, hi = s["window"]
            self.assertAlmostEqual(lo if s["exterior"] == "east" else hi, 1700.57, places=2)
            for o in s["objects"]:
                for lp in o["loops"]:
                    for x, _ in lp["pts"]:
                        self.assertTrue(lo - 1e-6 <= x <= hi + 1e-6, (s["id"], o["name"]))

    def test_section_content(self):
        by = {s["id"]: s for s in self.snap["sections"]}
        names = lambda sid: {o["name"] for o in by[sid]["objects"]}   # noqa: E731
        self.assertTrue({"WallA1Mitred", "WallA2Mitred", "WallA4Mitred", "FootingA1"} <= names("A-1"))
        self.assertTrue({"WallB2Mitred", "WallB3Mitred", "WallB4Mitred", "WallB5Mitred"} <= names("B-1"))
        self.assertTrue({"BridgeCapEB1", "BridgeBackwallEB1", "BridgeDeckS1", "WallA5Mitred"} <= names("A-2"))
        self.assertTrue({"BridgeCapEB2", "BridgeBackwallEB2", "BridgeDeckS2", "WallB1Mitred"} <= names("B-2"))
        for sid in ("A-2", "B-2"):
            self.assertTrue(any(p["name"].startswith("BridgePileEB") for p in by[sid]["projected_piles"]), sid)
        for s in self.snap["sections"]:
            self.assertTrue(s["terrain"]["EG"], s["id"])
        self.assertTrue(by["B-1"]["terrain"]["POND"])

    def test_report_embeds_every_section(self):
        page = (OUT / sections.HTML_NAME).read_text(encoding="utf-8")
        self.assertNotIn("/*DATA*/null", page)
        for s in self.snap["sections"]:
            self.assertIn(s["title"], page)


if __name__ == "__main__":
    unittest.main()
