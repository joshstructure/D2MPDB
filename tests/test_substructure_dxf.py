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

from substructure_drawings import bars, build, fdot  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
