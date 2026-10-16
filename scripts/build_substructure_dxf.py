"""Rebuild the end bent and pier DXF from the registered FreeCAD model.

    .venv\\Scripts\\python.exe scripts\\build_substructure_dxf.py [--extract] [--previews]

--extract   re-read the FreeCAD model: copy the registered FCStd to a temporary
            folder and run FreeCAD 1.1 ``freecadcmd`` on the copy
            (substructure_drawings/freecad_extract.py, read-only) to refresh
            substructure_drawings/data/model_snapshot.json
--previews  also render each sheet to PNG (substructure_drawings/output/previews)

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

from substructure_drawings import build  # noqa: E402

MODEL_DIR = ROOT / "project_current" / "geometry" / "freecad"
MODEL = MODEL_DIR / "B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd"
RUNTIME = MODEL_DIR / "runtime"
SNAPSHOT = ROOT / "substructure_drawings" / "data" / "model_snapshot.json"
OUT = ROOT / "substructure_drawings" / "output"
FREECADCMD = Path(os.environ.get("FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"))


def extract():
    digest = hashlib.sha256(MODEL.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "model.FCStd"
        shutil.copy2(MODEL, copy)
        out = Path(tmp) / "snapshot.json"
        env = dict(os.environ, SUBDWG_MODEL=str(copy), SUBDWG_RUNTIME=str(RUNTIME),
                   SUBDWG_OUT=str(out), SUBDWG_SOURCE_SHA256=digest)
        subprocess.run([str(FREECADCMD), str(ROOT / "substructure_drawings" / "freecad_extract.py")],
                       env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        err = Path(str(out) + ".error.txt")
        if err.exists():
            raise RuntimeError(err.read_text(encoding="utf-8"))
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out, SNAPSHOT)
    if hashlib.sha256(MODEL.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Registered model changed during extraction")
    print("snapshot:", SNAPSHOT)


def previews(dxf_path, folder):
    """PNG per sheet plus one review PDF.  The ezdxf renderer does not draw
    linetypes, so hidden levels (*_h) are shown in grey instead of dashed."""
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration, ColorPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    doc = ezdxf.readfile(dxf_path)
    for layer in doc.layers:
        layer.color = 8 if layer.dxf.name.endswith("_h") else 7
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR,
                        lineweight_scaling=0.6)
    paths = []
    with PdfPages(folder / "review_sheets.pdf") as pdf:
        for i, name in enumerate(doc.layout_names_in_taborder()):
            if name == "Model":
                continue
            layout = doc.layouts.get(name)
            fig = plt.figure(figsize=(17, 11))
            ax = fig.add_axes([0, 0, 1, 1])
            Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(layout, finalize=True)
            ax.set_xlim(0, 17 / 12)
            ax.set_ylim(0, 11 / 12)
            p = folder / ("%02d_%s.png" % (i, name.split(" ")[0]))
            fig.savefig(p, dpi=110, facecolor="white")
            pdf.savefig(fig, facecolor="white")
            plt.close(fig)
            paths.append(p)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--previews", action="store_true")
    a = ap.parse_args()
    if a.extract:
        extract()
    dxf, manifest = build.write_outputs(SNAPSHOT, OUT)
    print("dxf:", dxf)
    for w in manifest["layout_warnings"]:
        print("WARNING:", w)
    for q in manifest["qc"]:
        print("QC %-8s %s model %s ref %s" % (q["status"], q["check"], q["model"], q["reference"]))
    if a.previews:
        for p in previews(dxf, OUT / "previews"):
            print("preview:", p)


if __name__ == "__main__":
    main()
