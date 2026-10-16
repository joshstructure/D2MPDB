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


PREVIEW_FONTS = {"FDOT Structures": "GOTHICI.TTF", "FDOT Structures Title": "GOTHICBI.TTF",
                 "FDOT Serif": "times.ttf"}


def preview_doc(dxf_path):
    """Read the DXF for review rendering, adjusted so the ezdxf renderer shows
    it as a plotted sheet would look.

    - Lettering: the renderer ignores the oblique angle of TEXT entities and
      has no engineering font, so the styles are mapped to an italic sans
      (Century Gothic Italic; bold italic for view titles).
    - Linetypes: inside a viewport ezdxf applies the pattern after the
      transformation to paper space and multiplies it by the inverse viewport
      scale, while the DXF carries per-entity model-space scales for
      PSLTSCALE = 0 (``fdot.LTSCALE_PER_SF`` x drawing scale factor).  Each
      entity scale is divided by the square of its scale factor so the
      dashes plot at the intended paper size.
    - Everything plots black; lineweights keep their level values.
    """
    import ezdxf
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from substructure_drawings import fdot
    doc = ezdxf.readfile(dxf_path)
    for name, font in PREVIEW_FONTS.items():
        if name in doc.styles:
            st = doc.styles.get(name)
            st.dxf.font = font
            st.dxf.oblique = 0.0
            st.discard_extended_font_data()
    layer_lt = {layer.dxf.name: layer.dxf.linetype for layer in doc.layers}

    def fix(entities):
        for e in entities:
            if not e.dxf.hasattr("ltscale"):
                continue
            lt = e.dxf.get("linetype", "BYLAYER")
            if lt.upper() == "BYLAYER":
                lt = layer_lt.get(e.dxf.layer, "Continuous")
            if lt in fdot.LTSCALE_PER_SF and e.dxf.ltscale > 0:
                e.dxf.ltscale = fdot.LTSCALE_PER_SF[lt] ** 2 / e.dxf.ltscale
    fix(doc.modelspace())
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK,
                        lineweight_scaling=1.0, min_lineweight=0.6, min_dash_length=2.5e-5)
    return doc, cfg


def render_layout(doc, cfg, name, ax):
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.layouts.get(name), finalize=True)


def previews(dxf_path, folder):
    """PNG per sheet plus one review PDF (see ``preview_doc``)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    doc, cfg = preview_doc(dxf_path)
    paths = []
    tmp = folder / "review_sheets.tmp.pdf"
    with PdfPages(tmp, metadata={"CreationDate": None, "ModDate": None}) as pdf:
        for i, name in enumerate(doc.layout_names_in_taborder()):
            if name == "Model":
                continue
            fig = plt.figure(figsize=(17, 11))
            ax = fig.add_axes([0, 0, 1, 1])
            render_layout(doc, cfg, name, ax)
            ax.set_xlim(0, 17 / 12)
            ax.set_ylim(0, 11 / 12)
            p = folder / ("%02d_%s.png" % (i, name.split(" ")[0]))
            fig.savefig(p, dpi=110, facecolor="white")
            pdf.savefig(fig, facecolor="white")
            plt.close(fig)
            paths.append(p)
    try:
        os.replace(tmp, folder / "review_sheets.pdf")
    except PermissionError:  # open in a viewer: keep the new copy beside it
        os.replace(tmp, folder / "review_sheets_new.pdf")
        print("WARNING: review_sheets.pdf is open elsewhere; wrote review_sheets_new.pdf")
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
