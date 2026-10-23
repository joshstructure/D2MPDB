"""Regression tests for the superstructure typical section DXF
(substructure_drawings/typical_section.py, sheet S-1).

Rebuild after a FreeCAD model change (re-reads the model with freecadcmd):
    .venv\\Scripts\\python.exe scripts\\build_typical_section_dxf.py --extract --previews
After a generator change only:
    .venv\\Scripts\\python.exe scripts\\build_typical_section_dxf.py --previews
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

from substructure_drawings import build, fdot, typical_section  # noqa: E402

PKG = ROOT / "substructure_drawings"
SNAPSHOT = PKG / "data" / "typical_section_snapshot.json"
OUT = PKG / "output"
DXF = OUT / typical_section.DXF_NAME
MODEL = (ROOT / "project_current" / "geometry" / "freecad" /
         "B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd")
REBUILD = r"Rebuild with: .venv\Scripts\python.exe scripts\build_typical_section_dxf.py --previews"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TypicalSectionDxfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((OUT / typical_section.MANIFEST_NAME).read_text(encoding="utf-8"))
        cls.snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.doc = ezdxf.readfile(DXF)

    def test_snapshot_is_from_the_registered_model(self):
        self.assertEqual(self.snap["model_sha256"], sha(MODEL), "The FreeCAD model changed. " + REBUILD.replace("--previews", "--extract --previews"))
        self.assertEqual(self.snap["schema"], 1)

    def test_outputs_are_current_with_snapshot_and_generator(self):
        self.assertEqual(self.manifest["snapshot_sha256"], sha(SNAPSHOT), REBUILD)
        self.assertEqual(self.manifest["dxf_sha256"], sha(DXF), REBUILD)
        flat = OUT / self.manifest["dxf_flat"]
        self.assertEqual(self.manifest["dxf_flat_sha256"], sha(flat), REBUILD)
        with tempfile.TemporaryDirectory() as tmp:
            dxf, manifest = typical_section.write_outputs(SNAPSHOT, tmp)
            self.assertEqual(sha(dxf), sha(DXF), "Generator output differs from the committed DXF. " + REBUILD)
            self.assertEqual(sha(Path(tmp) / manifest["dxf_flat"]), sha(flat), "The flat DXF differs. " + REBUILD)
        self.assertTrue((OUT / "B4_Typical_Section.png").exists(), "preview missing. " + REBUILD)

    def test_cut_is_at_mid_span_1_looking_ahead_station(self):
        cut = self.snap["cut"]
        self.assertAlmostEqual(cut["y_ft"], (cut["ffbw_eb1_y_ft"] + cut["pier_cl_y_ft"]) / 2, places=5)
        self.assertEqual(self.snap["frame"]["e1"], [-1, 0, 0])
        self.assertEqual(self.snap["frame"]["e2"], [0, 0, 1])
        self.assertEqual(self.manifest["section"]["station"], "16+46.89")

    def test_section_measures_the_registered_geometry(self):
        """The cut reproduces the journal Bridge Geometry - 2 Beam values."""
        f = self.manifest["section"]
        self.assertAlmostEqual(f["deck_out_to_out_ft"], 13 + 7 / 12, places=4)          # Deck_out2out 13 ft 7 in
        self.assertAlmostEqual(f["clear_between_barriers_ft"], 12.0, places=4)        # Bridge_clearWidth
        self.assertAlmostEqual(f["beam_spacing_ft"], 8 + 7 / 12, places=4)            # Beam_spacing 8 ft 7 in
        self.assertAlmostEqual(f["slab_thickness_at_pgl_ft"], 0.5, places=4)          # Thickness_slab_peak 6 in
        self.assertAlmostEqual(f["beam_depth_ft"], 3.0, places=4)                     # Beam_depth (FIB-36)
        self.assertAlmostEqual(f["barrier_height_ft"], 3.5, places=4)                 # Parapet_ht 42 in
        self.assertAlmostEqual(f["barrier_width_ft"], 8 / 12, places=4)               # Parapet_width 8 in
        self.assertAlmostEqual(f["overhang_ft"]["L"], 2.5, places=4)
        self.assertAlmostEqual(f["overhang_ft"]["R"], 2.5, places=4)
        for side in ("L", "R"):
            self.assertAlmostEqual(f["crossfall"][side], 0.02, places=3)             # Deck_crossfall
        self.assertEqual(f["drip_grooves"], 2)
        roles = self.manifest["objects_by_role"]
        self.assertEqual(len(roles["deck"]), 1)
        self.assertEqual(len(roles["beam"]), 2)
        self.assertEqual(len(roles["haunch"]), 2)
        self.assertEqual(len(roles["barrier"]), 2)
        self.assertNotIn("unknown", roles)

    def test_sheet(self):
        self.assertEqual(self.doc.header["$INSUNITS"], 21)
        sheets = [lay for lay in self.doc.layouts if lay.name != "Model"]
        self.assertEqual([lay.name for lay in sheets], [self.manifest["sheet"]["layout"]])
        self.assertEqual(self.manifest["sheet"]["number"], "S-1")
        self.assertEqual(self.manifest["sheet"]["scale"], '1/2" = 1\'-0"')
        self.assertEqual(self.manifest["layout_warnings"], [])
        self.assertEqual(self.manifest["annotation_overlaps"], [])
        texts = [e.dxf.text for e in self.doc.modelspace().query("TEXT")]
        texts += [e.text for e in self.doc.modelspace().query("MTEXT")]
        joined = "\n".join(texts)
        for s in ("TYPICAL SECTION", "(LOOKING AHEAD STATION)", "BRIDGE & PGL", "FIB-36 (TYP.)", "HAUNCH (TYP.)",
                  "PEDESTRIAN BARRIER (TYP.)", "C.I.P. DECK", "DRIP GROOVE (TYP.)", "CLEAR", "2.0%", "PGL EL. 47.929"):
            self.assertIn(s, joined, s)
        notes = "\n".join(e.text for e in sheets[0].query("MTEXT"))
        self.assertIn("MODEL CHECK: THE PEDESTRIAN FENCE ENCLOSURE", notes)
        self.assertIn("STA. 16+46.89", notes)

    def test_symbology(self):
        allowed = set(fdot.LEVELS)
        used = {e.dxf.layer for blk in self.doc.blocks for e in blk}
        self.assertTrue(used <= allowed, sorted(used - allowed))
        self.assertNotIn(b"Defpoints", DXF.read_bytes())
        audit = build.symbology_audit(self.doc)
        self.assertEqual(audit["not_on_fdot_level"], [])
        self.assertEqual(audit["not_by_level"], [])
        levels = self.manifest["levels_used"]
        for name in ("SupstrConc", "BeamConc", "TrafBarrierConc", "CL_Major", "CL_Minor", "Dimension", "Leader",
                     "TextStructures", "Symbols"):
            self.assertIn(name, levels, name)
        for name in ("SubStrConc", "Rebar"):
            self.assertNotIn(name, levels, name)

    def test_flat_dxf_has_no_dimension_entities(self):
        flat = ezdxf.readfile(OUT / self.manifest["dxf_flat"])
        self.assertEqual(len(flat.modelspace().query("DIMENSION")), 0)
        self.assertEqual(len(self.doc.modelspace().query("DIMENSION")), self.manifest["dimensions_flattened"])
        audit = build.symbology_audit(flat)
        self.assertEqual(audit["not_on_fdot_level"], [])
        self.assertEqual(audit["not_by_level"], [])

    def test_fdot_line_codes(self):
        lt = self.doc.linetypes.get("DGN2")
        self.assertEqual([round(t.value, 6) for t in lt.pattern_tags.tags if t.code in (40, 49)], [0.12, 0.08, -0.04])
        by_layer = {lay.dxf.name: lay.dxf.linetype for lay in self.doc.layers}
        for e in self.doc.modelspace():
            t = e.dxf.get("linetype", "BYLAYER")
            t = by_layer.get(e.dxf.layer) if t.upper() == "BYLAYER" else t
            if t != "Continuous":
                self.assertAlmostEqual(e.dxf.ltscale, 24.0 / 12.0, places=6, msg=str(e))   # one paper inch at 1/2" = 1'-0"


if __name__ == "__main__":
    unittest.main()
