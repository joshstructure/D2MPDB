"""Regression tests for the whole-model plan DXF (substructure_drawings/model_plan.py).

Rebuild after a FreeCAD model change (re-reads the model with freecadcmd):
    .venv\\Scripts\\python.exe scripts\\build_model_plan_dxf.py --extract
After a generator change only:
    .venv\\Scripts\\python.exe scripts\\build_model_plan_dxf.py
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ezdxf  # noqa: E402

from substructure_drawings import build, fdot, model_plan  # noqa: E402

PKG = ROOT / "substructure_drawings"
SNAPSHOT = PKG / "data" / "model_plan_snapshot.json"
OUT = PKG / "output"
DXF = OUT / model_plan.DXF_NAME
MODEL = (ROOT / "project_current" / "geometry" / "freecad" /
         "B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd")
REBUILD = r"Rebuild with: .venv\Scripts\python.exe scripts\build_model_plan_dxf.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ModelPlanDxfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((OUT / model_plan.MANIFEST_NAME).read_text(encoding="utf-8"))
        cls.snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.doc = ezdxf.readfile(DXF)

    def test_snapshot_is_from_the_registered_model(self):
        self.assertEqual(self.snap["model_sha256"], sha(MODEL),
                         "The FreeCAD model changed. " + REBUILD + " --extract")

    def test_outputs_are_current_with_snapshot_and_generator(self):
        self.assertEqual(self.manifest["snapshot_sha256"], sha(SNAPSHOT), REBUILD)
        self.assertEqual(self.manifest["dxf_sha256"], sha(DXF), REBUILD)
        with tempfile.TemporaryDirectory() as tmp:
            dxf, manifest = model_plan.write_outputs(SNAPSHOT, tmp)
            self.assertEqual(sha(dxf), sha(DXF), "Generator output differs from the committed DXF. " + REBUILD)

    def test_frame_runs_from_end_bent_1_to_end_bent_2(self):
        """Sheet right is the direction of stationing (End Bent 1 at the left),
        sheet up the model's +X, looking down."""
        self.assertEqual(self.snap["frame"]["e1"], [0, -1, 0])
        self.assertEqual(self.snap["frame"]["e2"], [1, 0, 0])
        u = {s["support"]: s["u_ft"] for s in self.manifest["stations"]}
        self.assertLess(u["EB1"], u["PIER"])
        self.assertLess(u["PIER"], u["EB2"])
        self.assertEqual([s["station"] for s in self.manifest["stations"]], ["15+93.22", "17+00.57", "18+05.47"])

    def test_finished_components_are_drawn(self):
        roles = self.snap["roles"]
        for role in ("deck", "beam", "haunch", "pad", "pedestal", "cap", "pile_conc", "pile_steel", "pier_wall",
                     "backwall", "cheek", "barrier", "coping", "mse", "closure", "slab", "strap"):
            self.assertIn(role, roles, role)
        self.assertEqual(len(roles["deck"]), 2)
        self.assertEqual(len(roles["pile_conc"]) + len(roles["pile_steel"]), 12)
        self.assertEqual(len(roles["mse"]), 17)
        self.assertNotIn("unknown", roles)
        names = {n for ns in roles.values() for n in ns}
        self.assertFalse([n for n in names if "Footing" in n or "Envelope" in n or "Source" in n])
        for n in ("CopingA6AtCheek", "CopingB2BentJoint", "BarrierDeckS1LCorrected", "WallA1Mitred",
                  "A_ReturnRunSlabFinished", "ClosureSlabEB1", "GeotechnicalStrapEB1"):
            self.assertIn(n, names, n)
        for n in ("CopingA6", "CopingB2", "BarrierDeckS1L", "WallA1", "A_ReturnRunSlab"):
            self.assertNotIn(n, names, n)

    def test_symbology(self):
        """FDOT levels only, everything ByLevel apart from the documented
        hidden pad edges; the plan draws visible and hidden edges."""
        allowed = set(fdot.LEVELS)
        used = {e.dxf.layer for blk in self.doc.blocks for e in blk}
        self.assertTrue(used <= allowed, sorted(used - allowed))
        self.assertNotIn(b"Defpoints", DXF.read_bytes())
        audit = build.symbology_audit(self.doc)
        self.assertEqual(audit["not_on_fdot_level"], [])
        self.assertEqual(audit["not_by_level"], [])
        self.assertTrue(set(audit["documented_overrides"]) <=
                        {"BearingPadMisc linetype DGN2 (hidden pad edges; no FDOT hidden level)"})
        levels = self.manifest["levels_used"]
        for name in ("SupstrConc", "BeamConc_h", "WallMSEPanel", "WallConc", "TrafBarrierConc", "AppSlabConc",
                     "SubStrConc", "PileConc_h", "BaseLineSurveyPGL", "CL_Major"):
            self.assertIn(name, levels, name)

    def test_sheet(self):
        self.assertEqual(self.doc.header["$INSUNITS"], 21)   # US survey feet, the DGN's master units (E9)
        sheets = [lay for lay in self.doc.layouts if lay.name != "Model"]
        self.assertEqual([lay.name for lay in sheets], [self.manifest["sheet"]["layout"]])
        self.assertGreaterEqual(len([v for v in sheets[0].viewports() if v.dxf.id > 1]), 1)
        self.assertEqual(self.manifest["layout_warnings"], [])
        self.assertEqual(self.manifest["annotation_overlaps"], [])
        self.assertEqual(self.manifest["sheet"]["scale"], '1" = 40\'')
        texts = [e.dxf.text for e in self.doc.modelspace().query("TEXT")]
        texts += [e.text for e in self.doc.modelspace().query("MTEXT")]
        joined = "\n".join(texts)
        for s in ("FFBW END BENT 1", "STA. 15+93.22", "PIER", "STA. 17+00.57", "FFBW END BENT 2", "STA. 18+05.47",
                  "DIRECTION OF STATIONING", "PLAN", "PGL", "RAMP A", "RAMP B"):
            self.assertIn(s, joined, s)


if __name__ == "__main__":
    unittest.main()
