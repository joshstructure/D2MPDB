"""Rebuild the superstructure typical section DXF from the registered FreeCAD model.

    .venv\\Scripts\\python.exe scripts\\build_typical_section_dxf.py [--extract] [--previews]

--extract   re-read the FreeCAD model: copy the registered FCStd to a temporary
            folder and run FreeCAD 1.1 ``freecadcmd`` on the copy
            (substructure_drawings/freecad_typical_section_extract.py, read-only)
            to refresh substructure_drawings/data/typical_section_snapshot.json
--previews  also render the sheet to substructure_drawings/output/B4_Typical_Section.png

Without --extract the DXF is rebuilt from the committed snapshot, so the
output is reproducible without FreeCAD.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from substructure_drawings import typical_section  # noqa: E402
import build_model_plan_dxf as plan  # noqa: E402  (the preview renderer)
import build_substructure_dxf as bents  # noqa: E402  (the model path and freecadcmd)

SNAPSHOT = ROOT / "substructure_drawings" / "data" / "typical_section_snapshot.json"
OUT = ROOT / "substructure_drawings" / "output"


def extract():
    digest = hashlib.sha256(bents.MODEL.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "model.FCStd"
        shutil.copy2(bents.MODEL, copy)
        out = Path(tmp) / "snapshot.json"
        env = dict(os.environ, SUBDWG_MODEL=str(copy), SUBDWG_RUNTIME=str(bents.RUNTIME),
                   SUBDWG_PKG=str(ROOT / "substructure_drawings"), SUBDWG_OUT=str(out),
                   SUBDWG_SOURCE_SHA256=digest)
        subprocess.run([str(bents.FREECADCMD), str(ROOT / "substructure_drawings" / "freecad_typical_section_extract.py")],
                       env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        err = Path(str(out) + ".error.txt")
        if err.exists():
            raise RuntimeError(err.read_text(encoding="utf-8"))
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out, SNAPSHOT)
    if hashlib.sha256(bents.MODEL.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Registered model changed during extraction")
    print("snapshot:", SNAPSHOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--previews", action="store_true")
    a = ap.parse_args()
    if a.extract:
        extract()
    dxf, manifest = typical_section.write_outputs(SNAPSHOT, OUT)
    print("dxf:", dxf)
    print("flat dxf (for the DGN import, %d dimensions exploded):" % manifest["dimensions_flattened"],
          OUT / manifest["dxf_flat"])
    for key, val in manifest["section"].items():
        print("section %-28s %s" % (key, val))
    for w in manifest["layout_warnings"]:
        print("WARNING:", w)
    for w in manifest["annotation_overlaps"]:
        print("NOTE (annotation check):", w)
    audit = manifest["symbology_audit"]
    for w in audit["not_on_fdot_level"] + audit["not_by_level"]:
        print("WARNING (symbology):", w)
    for line in manifest["extraction_log"]:
        print("extract:", line)
    if a.previews:
        print("preview:", plan.preview(dxf, dxf.with_suffix(".png")))


if __name__ == "__main__":
    main()
