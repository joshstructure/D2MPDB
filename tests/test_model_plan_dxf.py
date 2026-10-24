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

from substructure_drawings import build, fdot, model_plan, sheets  # noqa: E402

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
        with tempfile.TemporaryDirectory() as tmp:
            built = model_plan.write_outputs(SNAPSHOT, tmp)
            for name, var in model_plan.VARIANTS.items():
                committed = json.loads((OUT / var["manifest"]).read_text(encoding="utf-8"))
                self.assertEqual(committed["snapshot_sha256"], sha(SNAPSHOT), REBUILD)
                self.assertEqual(committed["dxf_sha256"], sha(OUT / var["dxf"]), REBUILD)
                flat = OUT / committed["dxf_flat"]
                self.assertEqual(committed["dxf_flat_sha256"], sha(flat), REBUILD)
                dxf, manifest = built[name]
                self.assertEqual(sha(dxf), sha(OUT / var["dxf"]),
                                 "Generator output differs from the committed %s. " % var["dxf"] + REBUILD)
                self.assertEqual(sha(Path(tmp) / manifest["dxf_flat"]), sha(flat), "The flat DXF differs. " + REBUILD)

    def test_fdot_line_codes(self):
        """Dashed lines plot at FDOT's line code sizes (CADD Manual: DGN2 =
        0.08 in dash, 0.04 in gap): each DGNn pattern in paper inches with an
        entity linetype scale of one paper inch (40 ft at 1" = 40')."""
        self.assertEqual(fdot.fdot_linetype(2), [0.12, 0.08, -0.04])
        for var in model_plan.VARIANTS.values():
            doc = ezdxf.readfile(OUT / var["dxf"])
            lt = doc.linetypes.get("DGN2")
            self.assertEqual([round(t.value, 6) for t in lt.pattern_tags.tags if t.code in (40, 49)],
                             [0.12, 0.08, -0.04])
            by_layer = {lay.dxf.name: lay.dxf.linetype for lay in doc.layers}
            for e in doc.modelspace():
                t = e.dxf.get("linetype", "BYLAYER")
                t = by_layer.get(e.dxf.layer) if t.upper() == "BYLAYER" else t
                if t != "Continuous":
                    self.assertAlmostEqual(e.dxf.ltscale, 40.0, places=6, msg=str(e))

    def test_top_view_has_no_hidden_lines(self):
        doc = ezdxf.readfile(OUT / model_plan.VARIANTS["top"]["dxf"])
        hidden = {n for n in fdot.LEVELS if n.endswith("_h")}
        on_hidden = [e for e in doc.modelspace() if e.dxf.layer in hidden
                     or e.dxf.get("linetype", "BYLAYER") == fdot.HIDDEN_LINETYPE]
        self.assertEqual(on_hidden, [])
        top = json.loads((OUT / model_plan.VARIANTS["top"]["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(top["layout_warnings"], [])
        self.assertEqual(top["annotation_overlaps"], [])
        self.assertEqual(top["sheet"]["number"], "P-2")

    def test_pours_are_fused(self):
        """The model's mitred and butted pieces of one pour leave no joint
        lines (snapshot schema 2: the hidden-line pass over the pours)."""
        self.assertEqual(self.snap["schema"], 2)
        fused = [m for m in self.snap["log"] if m.startswith("pour ")]
        self.assertTrue(fused)
        self.assertFalse([m for m in fused if "not fused" in m], fused)
        seams = [m for m in self.snap["log"] if "modelling seam lines dropped" in m]
        self.assertEqual(len(seams), 1)
        self.assertGreater(int(seams[0].split()[0]), 0)

    def test_flat_dxf_has_no_dimension_entities(self):
        """B13: the flat variant for the DGN import carries the dimensions as
        lines, arrowheads and masked text on FDOT levels, ByLevel."""
        from substructure_drawings import build
        flat = ezdxf.readfile(DXF.parent / self.manifest["dxf_flat"])
        self.assertEqual(len(flat.modelspace().query("DIMENSION")), 0)
        self.assertEqual(len(self.doc.modelspace().query("DIMENSION")), self.manifest["dimensions_flattened"])
        audit = build.symbology_audit(flat)
        self.assertEqual(audit["not_on_fdot_level"], [])
        self.assertEqual(audit["not_by_level"], [])
        self.assertEqual(flat.header["$INSUNITS"], 21)

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
        hidden pad edges and the sheet border cell of the project's sheet
        model; the plan draws visible and hidden edges."""
        allowed = set(fdot.LEVELS)
        used = {e.dxf.layer for blk in self.doc.blocks if not sheets.is_border_cell(blk.name) for e in blk}
        self.assertTrue(used <= allowed, sorted(used - allowed))
        self.assertNotIn(b"Defpoints", DXF.read_bytes())
        audit = build.symbology_audit(self.doc)
        self.assertEqual(audit["not_on_fdot_level"], [])
        self.assertEqual(audit["not_by_level"], [])
        self.assertTrue(set(audit["documented_overrides"]) <=
                        {"BearingPadMisc linetype DGN2 (hidden pad edges; no FDOT hidden level)",
                         sheets.BORDER_CELL_OVERRIDE})
        self.assertEqual(self.manifest["sheet_border"], sheets.border_record())
        self.assertIn("%s %s" % (sheets.NUMBER_TITLE_BLOCK, self.manifest["sheet"]["number"]), self.doc.blocks)
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
