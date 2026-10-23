"""Rebuild the whole-model plan DXF from the registered FreeCAD model.

    .venv\\Scripts\\python.exe scripts\\build_model_plan_dxf.py [--extract] [--previews]

--extract   re-read the FreeCAD model: copy the registered FCStd to a temporary
            folder and run FreeCAD 1.1 ``freecadcmd`` on the copy
            (substructure_drawings/freecad_plan_extract.py, read-only) to
            refresh substructure_drawings/data/model_plan_snapshot.json
--previews  also render the sheets to substructure_drawings/output/B4_Model_Plan.png
            and B4_Model_Plan_Top.png (the visible-line top view)

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

from substructure_drawings import model_plan  # noqa: E402
import build_substructure_dxf as bents  # noqa: E402  (the model path, fonts and the preview renderer)

SNAPSHOT = ROOT / "substructure_drawings" / "data" / "model_plan_snapshot.json"
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
        subprocess.run([str(bents.FREECADCMD), str(ROOT / "substructure_drawings" / "freecad_plan_extract.py")],
                       env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        err = Path(str(out) + ".error.txt")
        if err.exists():
            raise RuntimeError(err.read_text(encoding="utf-8"))
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out, SNAPSHOT)
    if hashlib.sha256(bents.MODEL.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Registered model changed during extraction")
    print("snapshot:", SNAPSHOT)


def preview(dxf_path, png_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    doc, cfg = bents.preview_doc(dxf_path)
    name = [n for n in doc.layout_names_in_taborder() if n != "Model"][0]
    fig = plt.figure(figsize=(17, 11))
    ax = fig.add_axes([0, 0, 1, 1])
    bents.render_layout(doc, cfg, name, ax)
    ax.set_xlim(0, 17 / 12)
    ax.set_ylim(0, 11 / 12)
    fig.savefig(png_path, dpi=150, facecolor="white")
    plt.close(fig)
    return png_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--previews", action="store_true")
    a = ap.parse_args()
    if a.extract:
        extract()
    for dxf, manifest in model_plan.write_outputs(SNAPSHOT, OUT).values():
        print("dxf:", dxf)
        print("flat dxf (for the DGN import, %d dimensions exploded):" % manifest["dimensions_flattened"],
              OUT / manifest["dxf_flat"])
        for w in manifest["layout_warnings"]:
            print("WARNING:", w)
        for w in manifest["annotation_overlaps"]:
            print("NOTE (annotation check):", w)
        audit = manifest["symbology_audit"]
        for w in audit["not_on_fdot_level"] + audit["not_by_level"]:
            print("WARNING (symbology):", w)
        if a.previews:
            print("preview:", preview(dxf, dxf.with_suffix(".png")))
    for line in manifest["extraction_log"]:
        print("extract:", line)


if __name__ == "__main__":
    main()
