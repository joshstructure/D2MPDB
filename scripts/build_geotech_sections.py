"""Rebuild the geotechnical section DXFs and hover report from the registered model.

    .venv\\Scripts\\python.exe scripts\\build_geotech_sections.py [--extract]

--extract   re-cut the FreeCAD model and the terrain: copy the registered FCStd
            to a temporary folder, run FreeCAD 1.1 ``freecadcmd`` on the copy
            (geotech_sections/freecad_section_extract.py, read-only), cut the
            existing-ground and Pond 14D TINs along the same planes (caches of
            the CAD tooling, CAD_AI/reports) and refresh
            geotech_sections/data/sections_snapshot.json
            Needed after a model change or an edit of geotech_sections/cuts.json.

Without --extract the outputs are rebuilt from the committed snapshot, so they
are reproducible without FreeCAD or the terrain caches.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from geotech_sections import sections  # noqa: E402
import build_substructure_dxf as bents  # noqa: E402  (the registered model, its runtime and freecadcmd)

PKG = ROOT / "geotech_sections"
CUTS = PKG / "cuts.json"
SNAPSHOT = PKG / "data" / "sections_snapshot.json"
OUT = PKG / "output"
CAD_AI = Path(os.environ.get("CAD_AI", r"C:\Users\joshs\Desktop\CAD_AI"))
TERRAIN = {
    "eg_cache": CAD_AI / "reports" / "terrain-20261003" / "terrain-cache.npz",
    "placement": CAD_AI / "reports" / "terrain-20261003" / "placement.json",
    "eg_landxml": CAD_AI / "inputs" / "terrain-20261003" / "Ex_I-95_Middle.xml",
    "pond_cache": CAD_AI / "reports" / "pond14d-sections-20261003" / "pond14d-local.npz",
    "pond_landxml": CAD_AI / "inputs" / "pond14d-sections-20261003" / "Pond 14D.xml",
}


def extract():
    digest = hashlib.sha256(bents.MODEL.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "model.FCStd"
        shutil.copy2(bents.MODEL, copy)
        raw_path = Path(tmp) / "raw.json"
        env = dict(os.environ, GEOSEC_MODEL=str(copy), GEOSEC_RUNTIME=str(bents.RUNTIME),
                   GEOSEC_CUTS=str(CUTS), GEOSEC_OUT=str(raw_path))
        subprocess.run([str(bents.FREECADCMD), str(PKG / "freecad_section_extract.py")],
                       env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        err = Path(str(raw_path) + ".error.txt")
        if err.exists():
            raise RuntimeError(err.read_text(encoding="utf-8"))
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if hashlib.sha256(bents.MODEL.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Registered model changed during extraction")
    cuts = json.loads(CUTS.read_text(encoding="utf-8"))
    snap = sections.make_snapshot(raw, cuts, digest, TERRAIN)
    snap["cuts_sha256"] = sections.sha(CUTS)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snap, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("snapshot:", SNAPSHOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true")
    a = ap.parse_args()
    if a.extract:
        extract()
    manifest = sections.write_outputs(SNAPSHOT, OUT)
    for s in manifest["sections"]:
        print("%(id)s  %(from)s to %(to)s  clearance %(clearance_ft).1f ft  elements %(elements)d  "
              "projected piles %(projected_piles)d  EG coverage %(eg_coverage).3f" % s)
    for name in manifest["files"]:
        print("output:", OUT / name)


if __name__ == "__main__":
    main()
