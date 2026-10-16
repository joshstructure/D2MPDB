"""Regression tests for the end bent and pier DXF (substructure_drawings/).

Rebuild after a FreeCAD model change (re-reads the model with freecadcmd):
    .venv\\Scripts\\python.exe scripts\\build_substructure_dxf.py --extract
After a generator change only:
    .venv\\Scripts\\python.exe scripts\\build_substructure_dxf.py
"""
import csv
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ezdxf  # noqa: E402

from substructure_drawings import bars, build, fdot, views  # noqa: E402

PKG = ROOT / "substructure_drawings"
SNAPSHOT = PKG / "data" / "model_snapshot.json"
OUT = PKG / "output"
DXF = OUT / build.DXF_NAME
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
        allowed = set(fdot.LEVELS)
        used = {e.dxf.layer for e in self.doc.modelspace()}
        for lay in self.doc.layouts:
            used |= {e.dxf.layer for e in lay}
        self.assertTrue(used <= allowed | {"0"}, sorted(used - allowed))
        for name in allowed:
            layer = self.doc.layers.get(name)
            self.assertEqual(layer.dxf.linetype, fdot.level_attrs(name)["linetype"])

    def test_units_sheets_and_viewports(self):
        self.assertEqual(self.doc.header["$INSUNITS"], 2)
        sheets = [lay for lay in self.doc.layouts if lay.name != "Model"]
        self.assertEqual(len(sheets), len(self.manifest["sheets"]))
        for lay in sheets:
            vps = [v for v in lay.viewports() if v.dxf.id > 1]
            self.assertGreaterEqual(len(vps), 1, lay.name)
        self.assertEqual(self.manifest["layout_warnings"], [])

    def test_model_checks_against_cad_tables(self):
        status = {q["check"]: q["status"] for q in self.manifest["qc"]}
        # Known open item: the CAD EB1 backwall seat is to be rebuilt from the notebook.
        self.assertEqual([k for k, v in status.items() if v != "PASS"], ["Backwall top at cap end END BENT 1"])

    def test_dimension_text_format(self):
        self.assertEqual(fdot.ft_in(4 + 0.5 / 12, mtext=False), "4'-0 1/2\"")
        self.assertEqual(fdot.ft_in(7.5 / 12, 0.25, mtext=False), "7 1/2\"")
        self.assertEqual(fdot.ft_in(0.75 / 12, mtext=False), "3/4\"")
        self.assertEqual(fdot.ft_in(19 + 7 / 12), "19'-7\"")
        self.assertEqual(fdot.elev(43.23769), "43.238")
        self.assertEqual(fdot.station(1593.22), "15+93.22")
        # small diagonal fractions tight against the whole number (STYLE_PLAN item 3)
        self.assertEqual(fdot.ft_in(4 + 0.5 / 12), "4'-0{\\H0.6x;\\S1#2;}\"")
        self.assertEqual(fdot.ft_in(0.75 / 12), "{\\H0.6x;\\S3#4;}\"")
        # bar list FT-IN without unit marks (item 18)
        self.assertEqual(fdot.ft_in_list(244, 1), "20-4")
        self.assertEqual(fdot.ft_in_list(224.75), "18-8{\\H0.6x;\\S3#4;}")

    def test_sheet_set_follows_the_fdot_sample(self):
        """Plan and elevation with the reinforcement for each support (no
        separate reinforcement sheets), its details, then the bar list."""
        sheets = self.manifest["sheets"]
        self.assertEqual([s["number"] for s in sheets], ["B4-%d" % i for i in range(1, 10)])
        self.assertEqual([s["title"] for s in sheets], [
            "END BENT 1", "END BENT 1 DETAILS (1 OF 2)", "END BENT 1 DETAILS (2 OF 2)",
            "PIER", "PIER DETAILS",
            "END BENT 2", "END BENT 2 DETAILS (1 OF 2)", "END BENT 2 DETAILS (2 OF 2)",
            "REINFORCING BAR LIST"])
        self.assertEqual(sheets[0]["scales"], ["3/8\" = 1'-0\""])
        self.assertEqual(sheets[2]["scales"], ["1/2\" = 1'-0\"", "3/4\" = 1'-0\""])

    def test_lettering_and_dimension_style(self):
        for name in (fdot.TEXT_STYLE, fdot.TITLE_STYLE):
            st = self.doc.styles.get(name)
            self.assertEqual(st.dxf.font, fdot.FONT_FILE)
            self.assertAlmostEqual(st.dxf.oblique, fdot.OBLIQUE)
        ds = self.doc.dimstyles.get(fdot.DIM_STYLE)
        self.assertAlmostEqual(ds.dxf.dimtfac, fdot.FRACTION)
        self.assertAlmostEqual(ds.dxf.dimtxt * 12, fdot.TEXT_IN)

    def test_series_and_callout_text(self):
        """One dimension per bar series with count, mark and spacing; equal
        spaces as 'n EQUAL SPA'; THRU for consecutive marks (items 4-6)."""
        self.assertEqual(views.series_text([0, 0.75, 1.5, 2.25], "6B1"), "4~6B1 @ 9\" = 2'-3\"")
        self.assertEqual(views.series_text([0, 0.75, 1.3], "6B1"), "3~6B1 @ 9\" MAX.")
        xs, texts = views.equal_chain([-6.75, -2.25, 2.25, 6.75], (-9.75, 9.75))
        self.assertEqual(xs, [-9.75, -6.75, 6.75, 9.75])
        self.assertEqual(texts, [None, "3 EQUAL SPA @ 4'-6\" = 13'-6\"", None])
        self.assertEqual(views.mark_list(["10E04", "10E05", "10E06", "10E07"]), "10E04 THRU 10E07")
        self.assertEqual(views.mark_list(["5E26", "5E27"]), "5E26/5E27")

    def test_bar_list_types_follow_index_415_001(self):
        """Straight bars are Type 1, U-bars Type 11, closed stirrups Type 4 with
        style 5 (135 degree) hooks; open stirrups with legs turned in plan
        have no standard type."""
        comp = build.Composer(self.snap)
        expected = {"STRAIGHT": ("1", "", ""), "U-BAR": ("11", "", ""), "CLOSED HOOP": ("4", "5", "5"),
                    "OPEN STIRRUP": ("", "", "")}
        for s in comp.sup.values():
            for mark, e in s.table.items():
                bar = next(b for b in s.bars if b["name"] == e["members"][0])
                typ, a, g, dims = build.Composer.bar_fields(e, bar)
                self.assertEqual((typ, a, g), expected[bars.shape_name(e)], "%s %s" % (s.title, mark))
                self.assertIn("B", dims)


if __name__ == "__main__":
    unittest.main()
