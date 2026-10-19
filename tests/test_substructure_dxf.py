"""Regression tests for the end bent and pier DXF (substructure_drawings/).

Rebuild after a FreeCAD model change (re-reads the model with freecadcmd):
    .venv\\Scripts\\python.exe scripts\\build_substructure_dxf.py --extract
After a generator change only:
    .venv\\Scripts\\python.exe scripts\\build_substructure_dxf.py
"""
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ezdxf  # noqa: E402
from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS  # noqa: E402
from fractions import Fraction  # noqa: E402

from substructure_drawings import bars, build, cad, fdot, views  # noqa: E402

PKG = ROOT / "substructure_drawings"
SNAPSHOT = PKG / "data" / "model_snapshot.json"
# the committed outputs; SUBDWG_OUT_DIR points the tests at a scratch build
# (scripts/build_substructure_dxf.py writes the committed folder)
OUT = Path(os.environ.get("SUBDWG_OUT_DIR", PKG / "output"))
DXF = OUT / build.DXF_NAME
STRAP_LOADS = PKG / "data" / "strap_loads.json"
BACKWALL_CASE = ROOT / "project_current" / "cap_design" / "backwall" / "selected_case.json"
MODEL = (ROOT / "project_current" / "geometry" / "freecad" /
         "B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd")
REBUILD = r"Rebuild with: .venv\Scripts\python.exe scripts\build_substructure_dxf.py"
MARK = re.compile(r"^(\d{1,2})([A-HJ-NPR-Z])(\d*)$")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SubstructureDxfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
        cls.snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.doc = ezdxf.readfile(DXF)

    def test_snapshot_is_from_the_registered_model(self):
        self.assertEqual(self.snap["model_sha256"], sha(MODEL),
                         "The FreeCAD model changed. " + REBUILD + " --extract")

    def test_outputs_are_current_with_snapshot_and_generator(self):
        """A rebuild in a temporary folder is byte-identical to the committed DXF."""
        self.assertEqual(self.manifest["snapshot_sha256"], sha(SNAPSHOT), REBUILD)
        self.assertEqual(self.manifest["dxf_sha256"], sha(DXF), REBUILD)
        with tempfile.TemporaryDirectory() as tmp:
            dxf, manifest = build.write_outputs(SNAPSHOT, tmp)
            self.assertEqual(sha(dxf), sha(DXF), "Generator output differs from the committed DXF. " + REBUILD)
            self.assertEqual((Path(tmp) / "bar_mark_register.csv").read_bytes(),
                             (OUT / "bar_mark_register.csv").read_bytes(), REBUILD)

    def test_every_snapshot_bar_has_an_sdm_mark(self):
        for key, S in self.snap["structures"].items():
            kind = "PIER" if key == "PIER" else "EB"
            sbars = [dict(b) for b in S["bars"]]
            table = bars.assign_marks(kind, sbars)
            self.assertEqual(sum(e["count"] for e in table.values()), len(sbars))
            by_letter = {}
            for mark, e in table.items():
                m = MARK.match(mark)
                self.assertIsNotNone(m, "%s %s is not size+designation" % (key, mark))
                size, letter, num = m.groups()
                self.assertEqual(int(size), e["size"])
                self.assertNotIn(letter, "IOQ")
                by_letter.setdefault(letter, []).append(num)
            for letter, nums in by_letter.items():
                if nums == [""]:
                    continue  # unique application: letter alone (SDM 4.3.D)
                self.assertEqual(sorted(int(n) for n in nums), list(range(1, len(nums) + 1)),
                                 "%s %s numbers must start at 1 without gaps" % (key, letter))

    def test_model_marks_are_the_sdm_marks(self):
        """D-042: the FreeCAD Mark of every bar equals its SDM mark (rerun
        substructure_drawings/freecad_marks.py after a cage regeneration)."""
        for key, S in self.snap["structures"].items():
            kind = "PIER" if key == "PIER" else "EB"
            sbars = [dict(b) for b in S["bars"]]
            bars.assign_marks(kind, sbars)
            stale = [(b["name"], b["mark_model"], b["mark"]) for b in sbars if b["mark_model"] != b["mark"]]
            self.assertEqual(stale, [], "%s model marks differ from SDM marks" % key)

    def test_register_covers_every_bar_once(self):
        with (OUT / "bar_mark_register.csv").open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        names = [r["native_object"] for r in rows]
        expected = [b["name"] for S in self.snap["structures"].values() for b in S["bars"]]
        self.assertEqual(sorted(names), sorted(expected))
        for r in rows:
            self.assertTrue(r["mark"].startswith(r["size"]))

    def test_only_fdot_levels_are_used(self):
        """CADD Manual 5.10.1.3: no user levels; layer 0 and Defpoints carry
        no entities (also inside blocks), and the file has no Defpoints layer
        (ezdxf adds an empty one when reading)."""
        allowed = set(fdot.LEVELS)
        used = {e.dxf.layer for blk in self.doc.blocks for e in blk}
        self.assertTrue(used <= allowed, sorted(used - allowed))
        self.assertTrue({layer.dxf.name for layer in self.doc.layers} <= allowed | {"0", "Defpoints"})
        self.assertNotIn(b"Defpoints", DXF.read_bytes())
        self.assertEqual(self.doc.layers.get("ClipBorder_dp").dxf.plot, 0)
        for name in allowed:
            layer = self.doc.layers.get(name)
            self.assertEqual(layer.dxf.linetype, fdot.level_attrs(name)["linetype"])

    def test_every_entity_is_by_level(self):
        """Color, lineweight and linetype ByLayer for every entity in model
        space, the layouts and all blocks; the one documented exception is the
        hidden linetype on BearingPadMisc (no hidden twin in the level table)."""
        audit = build.symbology_audit(self.doc)
        self.assertEqual(audit["not_on_fdot_level"], [])
        self.assertEqual(audit["not_by_level"], [])
        self.assertEqual(set(audit["documented_overrides"]),
                         {"BearingPadMisc linetype DGN2 (hidden pad edges; no FDOT hidden level)"})
        self.assertEqual(self.manifest["symbology_audit"]["not_by_level"], [])
        self.assertEqual(self.manifest["symbology_audit"]["not_on_fdot_level"], [])
        self.assertNotIn("FDOT_CL_SYMBOL", self.doc.blocks)

    def test_lineweights_follow_the_cadd_manual(self):
        """CADD Manual 5.10 Line Weight Symbology (PDF p. 50): MS weight ->
        Autodesk mm; each layer has the weight of its level."""
        mm = {0: 0.09, 1: 0.15, 2: 0.20, 3: 0.30, 4: 0.35, 5: 0.40, 6: 0.53, 7: 0.60, 8: 0.70, 9: 0.80,
              10: 0.90, 11: 0.90, 12: 1.00, 13: 1.06, 14: 1.20, 15: 1.20, 16: 1.40, 17: 1.40, 18: 1.40}
        mm.update({w: 2.11 for w in range(19, 31)})
        self.assertEqual(fdot.BENTLEY_WEIGHT_TO_LW, {w: round(v * 100) for w, v in mm.items()})
        self.assertTrue(set(fdot.BENTLEY_WEIGHT_TO_LW.values()) <= set(VALID_DXF_LINEWEIGHTS))
        for name, (number, desc, color, style, weight) in fdot.LEVELS.items():
            layer = self.doc.layers.get(name)
            self.assertEqual(layer.dxf.lineweight, round(mm[weight] * 100), name)
            self.assertEqual(layer.dxf.color, fdot.BENTLEY_TO_ACI[color], name)
        self.assertEqual(self.doc.header["$LWDISPLAY"], 1)

    def test_linetype_names_follow_the_cadd_manual(self):
        """CADD Manual 5.10.3.2 (PDF p. 49): Bentley line style n = Autodesk
        linetype DGNn."""
        self.assertEqual(fdot.STYLE_TO_LINETYPE, {0: "Continuous", 2: "DGN2", 4: "DGN4", 6: "DGN6", 7: "DGN7"})
        names = {lt.dxf.name for lt in self.doc.linetypes}
        self.assertTrue({"DGN2", "DGN4", "DGN6", "DGN7"} <= names)
        self.assertFalse([n for n in names if n.startswith("DGN Style")])
        for name, (_, _, _, style, _) in fdot.LEVELS.items():
            self.assertEqual(self.doc.layers.get(name).dxf.linetype, "Continuous" if style == 0 else "DGN%d" % style)

    def test_units_sheets_and_viewports(self):
        self.assertEqual(self.doc.header["$INSUNITS"], 2)
        sheets = [lay for lay in self.doc.layouts if lay.name != "Model"]
        self.assertEqual(len(sheets), len(self.manifest["sheets"]))
        for lay in sheets:
            vps = [v for v in lay.viewports() if v.dxf.id > 1]
            self.assertGreaterEqual(len(vps), 1, lay.name)
        self.assertEqual(self.manifest["layout_warnings"], [])

    def test_model_checks_against_cad_tables(self):
        """Every cross-check of the model against the selected CAD tables
        passes (D-053 rebuilt both backwall tops in the model and the
        workbook: the End Bent 1 seat no longer differs)."""
        status = {q["check"]: q["status"] for q in self.manifest["qc"]}
        self.assertEqual([k for k, v in status.items() if v != "PASS"], [])
        self.assertEqual(len(status), 9)

    def test_dimension_text_format(self):
        self.assertEqual(fdot.ft_in(4 + 0.5 / 12, mtext=False), "4'-0 1/2\"")
        self.assertEqual(fdot.ft_in(7.5 / 12, 0.25, mtext=False), "7 1/2\"")
        self.assertEqual(fdot.ft_in(0.75 / 12, mtext=False), "3/4\"")
        self.assertEqual(fdot.ft_in(19 + 7 / 12), "19'-7\"")
        self.assertEqual(fdot.elev(43.23769), "43.238")
        self.assertEqual(fdot.station(1593.22), "15+93.22")
        # FDOT font fraction characters tight against the whole number
        self.assertEqual(fdot.ft_in(4 + 0.5 / 12), "4'-0½\"")
        self.assertEqual(fdot.ft_in(0.75 / 12), "¾\"")
        self.assertEqual(fdot.ft_in(2 + 5.875 / 12), "2'-5Ɔ\"")
        # bar list FT-IN without unit marks (STYLE_GUIDE B6; STYLE_PLAN item 18)
        self.assertEqual(fdot.ft_in_list(244, 1), "20-4")
        self.assertEqual(fdot.ft_in_list(224.75), "18-8¾")

    def test_fdot_font_characters(self):
        """CADD Manual 5.12 FDOT Special Symbols (PDF p. 54), as rendered by
        the installed FDOT fonts: U+00A1 centerline, U+00BC-00BE quarters,
        U+0183-0186 eighths, U+0187-018E sixteenths; FDOT_FONT_GLYPHS off
        gives U+2104 and MTEXT stacks for a workstation without the fonts."""
        F = Fraction
        expected = {F(1, 4): "¼", F(1, 2): "½", F(3, 4): "¾",
                    F(1, 8): "ƃ", F(3, 8): "Ƅ", F(5, 8): "ƅ", F(7, 8): "Ɔ"}
        expected.update({F(n, 16): chr(0x187 + i) for i, n in enumerate((1, 3, 5, 7, 9, 11, 13, 15))})
        self.assertEqual(fdot.FRACTION_GLYPHS, expected)
        self.assertEqual(fdot.CL_GLYPH, "¡")
        texts = [e.dxf.text for e in self.doc.modelspace().query("TEXT")]
        self.assertIn("¡ BEARING", texts)
        self.assertIn("¡ CAP & ¡ PILES", texts)
        dims = [e.text for blk in self.doc.blocks if blk.name.startswith("*D") for e in blk.query("MTEXT")]
        self.assertTrue(any("½" in s for s in dims))
        self.assertFalse(any("\\S" in s for s in dims + texts))
        try:
            fdot.FDOT_FONT_GLYPHS = False
            self.assertEqual(fdot.ft_in(4 + 0.5 / 12), "4'-0{\\H0.7x;\\S1#2;}\"")
            self.assertEqual(fdot.ft_in_list(224.75), "18-8{\\H0.7x;\\S3#4;}")
            self.assertEqual(fdot.font_text("¡ BEARING"), "℄ BEARING")
        finally:
            fdot.FDOT_FONT_GLYPHS = True

    def test_source_glyphs_are_not_mojibake(self):
        """The generator sources carry non-ASCII literals (Δ, °, Ø, fractions,
        the ¡ centerline glyph) as UTF-8.  A rewrite in another encoding
        turns them into two-character sequences (Î” for Δ, Â° for °) that
        reach the DXF; this happened once (2026-10-19) and is caught here,
        in the sources and in the drawing text."""
        bad = re.compile("[ÂÃÎ][\u0080-¿–-›˜]")
        for path in sorted(PKG.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(bad.search(text), "%s holds mojibake" % path.name)
        texts = [e.dxf.text for e in self.doc.modelspace().query("TEXT")]
        texts += [e.text for e in self.doc.modelspace().query("MTEXT")]
        joined = "\n".join(texts)
        for glyph in ("Δ", "°", "Ø"):
            self.assertIn(glyph, joined, glyph)
        self.assertIsNone(bad.search(joined))

    def test_sheet_set_follows_the_fdot_sample(self):
        """Plan and elevation with the reinforcement for each support (no
        separate reinforcement sheets), its details (STYLE_GUIDE E1: three
        details sheets per end bent), then the bar list."""
        sheets = self.manifest["sheets"]
        self.assertEqual([s["number"] for s in sheets], ["B4-%d" % i for i in range(1, 13)])
        self.assertEqual([s["title"] for s in sheets], [
            "END BENT 1", "END BENT 1 DETAILS (1 OF 3)", "END BENT 1 DETAILS (2 OF 3)",
            "END BENT 1 DETAILS (3 OF 3)",
            "PIER", "PIER DETAILS (1 OF 2)", "PIER DETAILS (2 OF 2)",
            "END BENT 2", "END BENT 2 DETAILS (1 OF 3)", "END BENT 2 DETAILS (2 OF 3)",
            "END BENT 2 DETAILS (3 OF 3)",
            "REINFORCING BAR LIST"])
        self.assertEqual(sheets[0]["scales"], ["3/8\" = 1'-0\""])
        self.assertEqual(sheets[2]["scales"], ["3/8\" = 1'-0\"", "3/4\" = 1'-0\""])
        self.assertEqual(sheets[1]["scales"], ["3/4\" = 1'-0\"", "1\" = 1'-0\"", "1-1/2\" = 1'-0\""])
        # the cheek wall sections at 3/4", detail "B" at 1", detail "A" at 1 1/2"
        self.assertEqual(sheets[3]["scales"], ["3/4\" = 1'-0\""])
        self.assertEqual(sheets[3]["scales"], sheets[10]["scales"])
        self.assertEqual(sheets[1]["scales"], sheets[8]["scales"])
        self.assertEqual(sheets[5]["scales"], ["3/4\" = 1'-0\""])
        self.assertEqual(sheets[6]["scales"], ["3/4\" = 1'-0\""])

    def test_cross_references_name_the_sheets_that_carry_the_views(self):
        """Plan-sheet note 3 and the details notes point at the right sheets
        (the note used to say the pedestal details are on the (2 OF 2) sheet);
        the strap legend (D6) is given once per bent, on its (1 OF 3) sheet
        (markup 2026-10-19), and the plan sheet and the (2 OF 3) sheet, which
        also draw the strap symbol, refer to it."""
        texts = {}
        for lay in self.doc.layouts:
            if lay.name != "Model":
                texts[lay.name.split(" ")[0]] = [e.dxf.text if e.dxftype() == "TEXT" else e.text
                                                 for e in lay.query("TEXT MTEXT")]
        for first, nums in (("B4-1", ("B4-2", "B4-3", "B4-4")), ("B4-8", ("B4-9", "B4-10", "B4-11"))):
            self.assertTrue(any(
                "FOR SECTIONS A-A AND B-B AND DETAILS \"A\" AND \"B\", SEE SHEET %s. FOR SECTION C-C AND VIEWS D-D "
                "AND E-E, SEE SHEET %s. FOR SECTIONS F-F AND G-G AND PEDESTAL DETAILS, SEE SHEET %s." % nums in t
                for t in texts[first]), first)
        self.assertTrue(any("SEE VIEW D-D, SHEET B4-3" in t for t in texts["B4-4"]))
        self.assertTrue(any("SEE VIEW D-D, SHEET B4-10" in t for t in texts["B4-11"]))
        # the pier: sections on (1 OF 2), pedestal details on (2 OF 2)
        self.assertTrue(any("FOR SECTIONS A-A, B-B AND C-C, SEE SHEET B4-6. FOR PEDESTAL DETAILS, SEE SHEET B4-7." in t
                            for t in texts["B4-5"]))
        self.assertTrue(any("FOR PEDESTAL DETAILS, SEE SHEET B4-7." in t for t in texts["B4-6"]))
        self.assertTrue(any("SEE SHEET B4-6." in t for t in texts["B4-7"]))
        # the LEGEND is on B4-2 and B4-9 only, once per bent
        for number in ("B4-2", "B4-9"):
            self.assertIn("LEGEND:", texts[number], number)
            self.assertTrue(any("PROPRIETARY WALL PROVIDER" in t for t in texts[number]), number)
        for number in sorted(texts):
            if number not in ("B4-2", "B4-9"):
                self.assertNotIn("LEGEND:", texts[number], number)
                self.assertFalse(any("PROPRIETARY WALL PROVIDER" in t for t in texts[number]), number)
                self.assertFalse(any("SPECIALTY ENGINEER" in t for t in texts[number]), number)
        # the other sheets that show the strap refer to the legend sheet
        for number, legend_sheet, wording in (
                ("B4-1", "B4-2", "FOR THE SOIL REINFORCEMENT (Δ) LEGEND, SEE SHEET %s."),
                ("B4-8", "B4-9", "FOR THE SOIL REINFORCEMENT (Δ) LEGEND, SEE SHEET %s."),
                ("B4-3", "B4-2", "FOR THE Δ REINFORCING STRAP LEGEND, SEE SHEET %s."),
                ("B4-10", "B4-9", "FOR THE Δ REINFORCING STRAP LEGEND, SEE SHEET %s.")):
            self.assertTrue(any(wording % legend_sheet in t for t in texts[number]), number)

    def test_strap_legend_is_current_with_the_backwall_case(self):
        """C1/D6: the Δ legend carries the strap loads of the selected
        backwall case (scripts/export_strap_loads.py evaluates the case and
        writes data/strap_loads.json); the loads are in the manifest and the
        drawing."""
        rebuild = r"Rebuild with: scripts\export_strap_loads.py then scripts\build_substructure_dxf.py"
        loads = json.loads(STRAP_LOADS.read_text(encoding="utf-8"))
        self.assertEqual(loads["case_sha256"], sha(BACKWALL_CASE), rebuild)
        self.assertEqual(self.manifest["strap_loads"], loads, rebuild)
        texts = [e.dxf.text for e in self.doc.modelspace().query("TEXT")]
        texts += [e.text for e in self.doc.modelspace().query("MTEXT")]
        for lay in self.doc.layouts:
            if lay.name != "Model":
                texts += [e.dxf.text if e.dxftype() == "TEXT" else e.text for e in lay.query("TEXT MTEXT")]
        service = "SERVICE LOAD OF %.2f K/FT" % loads["service_kip_ft"]
        factored = "FACTORED LOAD OF %.2f K/FT (%s)" % (loads["factored_kip_ft"], loads["governing"].upper())
        self.assertTrue(any(service in t for t in texts), service + ". " + rebuild)
        self.assertTrue(any(factored in t for t in texts), factored + ". " + rebuild)
        self.assertFalse(any("___ K/FT" in t for t in texts), "a blank load is left in the legend")
        from substructure_drawings import strap_loads
        self.assertEqual(strap_loads.load(), loads)
        self.assertIn(service + " AND A " + factored + " PERPENDICULAR TO THE END BENT BACKWALL.",
                      strap_loads.legend_text())

    def test_titles_of_a_row_go_down_to_the_lowest_baseline(self):
        """E5 (markup 2026-10-19, "line titles up vertically"): the titles of
        the views of a row share the lowest title baseline; the move is in
        local feet (paper inches x scale factor / 12)."""
        class Zone:
            model_origin = (100.0, 200.0)

        class FakeView:
            def __init__(self, y, oy, sf=16.0):
                self.sheet, self.sf, self.oy, self.moved = Zone(), sf, oy, 0.0
                self.title_spec = {"x": 0.0, "y": y, "title": "T", "sub": None, "subject_cx": 0.0}

            def move_title(self, dy):
                self.moved += dy
        comp = build.Composer.__new__(build.Composer)
        high, low, none = FakeView(-3.0, 210.0), FakeView(-5.0, 210.0), FakeView(0.0, 0.0)
        del none.title_spec
        self.assertAlmostEqual(comp.title_baseline(high), 5.25)      # (-3 + 210 - 200) ft x 12 / 16
        self.assertAlmostEqual(comp.title_baseline(low), 3.75)
        self.assertIsNone(comp.title_baseline(none))
        comp.align_titles([high, low, none])
        self.assertAlmostEqual(high.moved, -2.0)                     # 1.5 in down = 2 ft local
        self.assertEqual(low.moved, 0.0)
        self.assertEqual(none.__dict__.get("moved"), 0.0)

    def test_annotation_checks_are_clean(self):
        """A1: the annotation checks (rules A1, A2, A3, A10, A11, A12, A13,
        A14, A21, B9, B11, B12, D3, D12, D13, D15, E5 of STYLE_GUIDE.md;
        ``anno_check.RULES``) run on every view and find nothing; E5 (a
        title centred on its subject) is a layout check."""
        self.assertEqual(self.manifest["annotation_overlaps"], [])
        self.assertEqual(self.manifest["layout_warnings"], [])
        rules = self.manifest["anno_rules_checked"]
        for rule in ("A1", "A2", "A3", "A10", "A11", "A12", "A13", "A14", "A21", "B9", "B11", "B12",
                     "D3", "D12", "D13", "D15", "E5"):
            self.assertIn(rule, rules, rule)

    def test_dimension_blocks_have_no_zero_length_lines_and_masked_text(self):
        """Rules F and B2: ezdxf's zero-length lines in the dimension blocks
        (point markers, the "circles" of the B4-5 markup) are removed, and
        every dimension text has the drawing background fill (MTEXT bg_fill 3)."""
        dims = list(self.doc.modelspace().query("DIMENSION"))
        self.assertGreater(len(dims), 100)
        texts = 0
        for dim in dims:
            for e in self.doc.blocks.get(dim.dxf.geometry):
                if e.dxftype() == "LINE":
                    self.assertGreater((e.dxf.end - e.dxf.start).magnitude, 1e-9, dim.dxf.geometry)
                elif e.dxftype() == "MTEXT":
                    texts += 1
                    self.assertEqual(e.dxf.get("bg_fill", 0), 3, dim.dxf.geometry)
        self.assertGreater(texts, 100)

    def test_centerline_linetypes_are_dashes_not_dots(self):
        """Rule D3: DGN4 and DGN7 are long dash, short dash with no element
        shorter than 0.005 ft (a dot), plotted at 0.25 (minor) and 0.35
        (major) x the scale factor so a short centerline still shows its
        dashes (one pattern 0.34 in and 0.63 in on paper)."""
        for style in (4, 7):
            pattern = fdot.LINETYPE_PATTERNS[style]       # total length, then the elements
            self.assertFalse([v for v in pattern if 0 < abs(v) < 0.005], pattern)
            dashes = [v for v in pattern[1:] if v > 0]
            self.assertEqual(len(dashes), 2, pattern)
            self.assertGreater(dashes[0], dashes[1])
            self.assertAlmostEqual(pattern[0], sum(abs(v) for v in pattern[1:]), places=9)
            self.assertIn("DGN%d" % style, self.doc.linetypes)
        self.assertEqual(fdot.LTSCALE_PER_SF["DGN4"], 0.25)
        self.assertEqual(fdot.LTSCALE_PER_SF["DGN7"], 0.35)
        self.assertAlmostEqual(fdot.pattern_length("DGN4", 32.0) / 32.0 * 12.0, 0.1125 * 0.25 * 12, places=9)

    def test_offset_polyline_mitres_corners_to_the_left_and_right(self):
        """C4/B3: ``cad.offset_polyline`` offsets to the left for a positive
        distance and to the right for a negative one, mitring the corner."""
        pts = [(0, 0), (1, 0), (1, 1)]
        for got, want in zip(cad.offset_polyline(pts, 0.1), [(0, 0.1), (0.9, 0.1), (0.9, 1)]):
            self.assertAlmostEqual(got[0], want[0], places=9)
            self.assertAlmostEqual(got[1], want[1], places=9)
        right = cad.offset_polyline(pts, -0.1)
        self.assertEqual(len(right), 3)
        for got, want in zip(right, [(0, -0.1), (1.1, -0.1), (1.1, 1)]):
            self.assertAlmostEqual(got[0], want[0], places=9)
            self.assertAlmostEqual(got[1], want[1], places=9)

    def test_coincident_hidden_edges_are_dropped(self):
        """D1: a hidden line lying along a visible line tells the reader
        nothing and is dropped; a hidden line that does not coincide stays."""
        visible = {"t": "L", "vis": True, "role": "cap", "p": [[0, 0], [10, 0]]}
        on_top = {"t": "L", "vis": False, "role": "backwall", "p": [[2, 0], [5, 0]]}
        apart = {"t": "L", "vis": False, "role": "backwall", "p": [[2, 0.5], [5, 0.5]]}
        out = views.drop_coincident_hidden([visible, on_top, apart])
        self.assertEqual(out, [visible, apart])
        # a hidden polyline is dropped only when every segment is covered
        mixed = {"t": "P", "vis": False, "role": "pad", "p": [[2, 0], [5, 0], [5, 1]]}
        self.assertIn(mixed, views.drop_coincident_hidden([visible, mixed]))

    def test_bar_list_uses_the_standard_plans_note_and_no_bending_diagram(self):
        """C6: open stirrups are standard bars with field bent hooks: the
        bar list note says so and the custom bending diagram is gone."""
        paper = [e for blk in self.doc.blocks if blk.name.upper().startswith("*PAPER_SPACE")
                 for e in blk.query("TEXT MTEXT")]
        texts = [e.dxf.text if e.dxftype() == "TEXT" else e.text for e in paper]
        self.assertTrue(any("FIELD BEND OPEN STIRRUP HOOKS AS REQUIRED TO CLEAR PILE HEAD LOCATION" in t
                            for t in texts))
        self.assertFalse(any("OPEN STIRRUP (NOT TO SCALE)" in t for t in texts))

    def test_text_styles_follow_the_cadd_manual(self):
        """CADD Manual 5.12.1.1 (PDF pp. 52-53): FDOT text style names, fonts
        and heights; the FDOT TrueType font by file and family (bold flag for
        FDOT Bold), no oblique (the fonts are slanted), width = width/height.
        Every text is in one of these styles at its height (model space: times
        a sheet scale factor), except the border-cell lettering in FDOT
        Imprint; MTEXT has the three-quarter-height line gap (5.12.1.2)."""
        manual = {  # style: (font, height ft, width ft)
            "FDOT Structures": ("FDOT", 0.0063, 0.0063),
            "FDOT Structures Annotation": ("FDOT", 0.0063, 0.0063),
            "FDOT Structures Views_SectionArrow": ("FDOT Bold", 0.008, 0.008),
            "FDOT Structures Initials": ("FDOT", 0.0058, 0.0058),
            "FDOT (Small)": ("FDOT", 0.005833, 0.005833),
            "FDOT (Medium)": ("FDOT", 0.008333, 0.008333),
            "FDOT (Large)": ("FDOT", 0.010417, 0.010417),
            "FDOT Bold (Medium)": ("FDOT Bold", 0.008333, 0.008333),
            "FDOT Bold (Large)": ("FDOT Bold", 0.010417, 0.010417),
            "FDOT Mono (Small)": ("FDOT Mono", 0.006, 0.006),
            "FDOT_SHEET_DESCRIPTION": ("FDOT Imprint Bold", 0.010417, 0.010417),
            "FDOT_SHEET_COUNTY": ("FDOT Bold", 0.005833, 0.005833),
            "FDOT_SHEET_FPID": ("FDOT Bold", 0.005833, 0.005833),
            "FDOT_SHEET_SR": ("FDOT Bold", 0.005833, 0.005833),
            "FDOT_SHEET_REVISION_DATE": ("FDOT Mono", 0.005, 0.004),
            "FDOT_SHEET_REVISION_DESCRIPTION": ("FDOT Mono", 0.005, 0.004),
        }
        fonts = {"FDOT": ("FDOT.ttf", "FDOT", False), "FDOT Bold": ("FDOTBold.ttf", "FDOT", True),
                 "FDOT Mono": ("FDOTMono.ttf", "FDOT Mono", False),
                 "FDOT Imprint": ("FDOTImprint.ttf", "FDOT Imprint", False),
                 "FDOT Imprint Bold": ("FDOTImprintBold.ttf", "FDOT Imprint Bold", True)}
        for name, (font, h, w) in dict(manual, **{"FDOT Imprint": ("FDOT Imprint", None, None)}).items():
            self.assertEqual(fdot.TEXT_STYLES[name], (font, h, w), name)
            st = self.doc.styles.get(name)
            file, family, bold = fonts[font]
            self.assertEqual(st.dxf.font, file, name)
            self.assertEqual(st.get_extended_font_data(), (family, False, bold), name)
            self.assertEqual(st.dxf.oblique, 0.0, name)
            self.assertEqual(st.dxf.height, 0.0, name)
            self.assertAlmostEqual(st.dxf.width, w / h if h else 1.0, msg=name)
        self.assertEqual(set(fdot.TEXT_STYLES), {s.dxf.name for s in self.doc.styles} - {"Standard"})
        scales = set(fdot.SCALES.values())
        for blk in self.doc.blocks:
            paper = blk.name.upper().startswith("*PAPER_SPACE")
            for e in blk.query("TEXT MTEXT"):
                name = e.dxf.style
                h = e.dxf.height if e.dxftype() == "TEXT" else e.dxf.char_height
                self.assertIn(name, fdot.TEXT_STYLES)
                if e.dxftype() == "TEXT":
                    self.assertEqual(e.dxf.get("oblique", 0.0), 0.0)
                elif not blk.name.startswith("*D"):
                    self.assertAlmostEqual(e.dxf.line_spacing_factor, 1.05)
                if name == fdot.BORDER_STYLE:
                    self.assertTrue(paper)
                    continue
                k = h / fdot.TEXT_STYLES[name][1]
                if paper:
                    self.assertAlmostEqual(k, 1.0, msg="%s %s %r" % (blk.name, name, h))
                else:
                    self.assertTrue(any(abs(k - s) < 1e-6 for s in scales), "%s %s %r" % (blk.name, name, h))

    def test_dimension_style_is_fdot_structures_note_arrow(self):
        """FDOT Structures Note-Arrow as in the FDOT-workspace DXF export
        (SYMBOLOGY_PLAN A6), with ByLayer dimension and extension lines."""
        ds = self.doc.dimstyles.get("FDOT Structures Note-Arrow")
        expected = {"dimtxsty": "FDOT Structures Annotation", "dimtxt": 0.0063, "dimasz": 0.006508,
                    "dimexo": 0.00315, "dimexe": 0.00315, "dimgap": 0.00315, "dimlunit": 4, "dimlfac": 12.0,
                    "dimzin": 15, "dimfrac": 1, "dimtad": 1, "dimtih": 0, "dimtoh": 0, "dimtfac": 0.7,
                    "dimtmove": 1, "dimatfit": 1, "dimlwd": -1, "dimlwe": -1,
                    "dimclrd": 256, "dimclre": 256, "dimclrt": 256}
        for k, v in expected.items():
            if isinstance(v, float):
                self.assertAlmostEqual(ds.dxf.get(k), v, places=6, msg=k)
            else:
                self.assertEqual(ds.dxf.get(k), v, k)
        self.assertEqual(self.doc.header["$DIMSTYLE"], "FDOT Structures Note-Arrow")
        self.assertEqual(self.doc.header["$TEXTSTYLE"], "FDOT Structures")
        self.assertEqual({d.dxf.dimstyle for d in self.doc.modelspace().query("DIMENSION")},
                         {"FDOT Structures Note-Arrow"})

    def test_source_provenance(self):
        self.assertEqual(self.manifest["level_source"]["sha256"],
                         "8d2ac22a556721927c11af15c3d9ea73f5b809806a100cd4b982b4328b735d50")
        self.assertIn("625-050-001", self.manifest["cadd_manual"]["source"])

    def test_series_and_callout_text(self):
        """One dimension per bar series with count, mark and spacing; equal
        spaces as 'n EQUAL SPA'; THRU for consecutive marks (STYLE_GUIDE B6
        and C5; STYLE_PLAN items 4-6)."""
        self.assertEqual(views.series_text([0, 0.75, 1.5, 2.25], "6B1"), "4~6B1 @ 9\" = 2'-3\"")
        self.assertEqual(views.series_text([0, 0.75, 1.3], "6B1"), "3~6B1 @ 9\" MAX.")
        xs, texts = views.equal_chain([-6.75, -2.25, 2.25, 6.75], (-9.75, 9.75))
        self.assertEqual(xs, [-9.75, -6.75, 6.75, 9.75])
        self.assertEqual(texts, [None, "3 EQUAL SPA @ 4'-6\" = 13'-6\"", None])
        self.assertEqual(views.mark_list(["10E04", "10E05", "10E06", "10E07"]), "10E04 THRU 10E07")
        self.assertEqual(views.mark_list(["5E26", "5E27"]), "5E26/5E27")

    def test_bar_list_types_follow_index_415_001(self):
        """Straight bars are Type 1, bars with one 90 degree leg Type 10 (B
        the long leg, C the short), U-bars Type 11 (B base, C and D legs)
        whatever the legs' lengths, closed stirrups Type 4 with style 5 (135
        degree) hooks; open stirrups are Type 5 (closed top C, legs B, feet D
        and E turned in, no hooks).  No bar carries a 90 degree hook style
        (engineer's review 2026-10-19).  Every bar has a type."""
        comp = build.Composer(self.snap)
        expected = {"STRAIGHT": ("1", "", ""), "L-BAR": ("10", "", ""),
                    "U-BAR": ("11", "", ""), "CLOSED HOOP": ("4", "5", "5"), "OPEN STIRRUP": ("5", "", "")}
        letters = {"1": {"B"}, "10": {"B", "C"}, "11": {"B", "C", "D"}, "4": {"B", "C"},
                   "5": {"B", "C", "D", "E"}}
        for s in comp.sup.values():
            for mark, e in s.table.items():
                bar = next(b for b in s.bars if b["name"] == e["members"][0])
                typ, a, g, dims = build.Composer.bar_fields(e, bar)
                self.assertEqual((typ, a, g), expected[bars.shape_name(e)], "%s %s" % (s.title, mark))
                self.assertNotEqual(typ, "", "%s %s has no bar type" % (s.title, mark))
                self.assertEqual(set(dims), letters[typ], "%s %s bend letters" % (s.title, mark))
                if typ == "5":   # the open stirrup's two feet are alike and shorter than its legs
                    self.assertEqual(dims["D"], dims["E"], "%s %s" % (s.title, mark))
        # the engineer's assignments, mark by mark
        for key, want in (("EB1", {"5C": "11", "4E3": "11", "4E4": "10", "6B2": "5", "6B1": "4", "4F1": "11"}),
                          ("PIER", {"5C": "11", "5D1": "11", "5D2": "11", "5B2": "5", "5B1": "4", "4E1": "11"})):
            s = comp.sup[key]
            for mark, typ in want.items():
                e = s.table[mark]
                bar = next(b for b in s.bars if b["name"] == e["members"][0])
                self.assertEqual(build.Composer.bar_fields(e, bar)[0], typ, "%s %s" % (key, mark))


if __name__ == "__main__":
    unittest.main()
