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


FONT_DIRS = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
             Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"]
# Stand-ins for a machine without the FDOT fonts (Windows font files).
FONT_SUBSTITUTES = {"FDOT.ttf": "GOTHICI.TTF", "FDOTBold.ttf": "GOTHICBI.TTF", "FDOTImprint.ttf": "times.ttf",
                    "FDOTImprintBold.ttf": "timesbd.ttf", "FDOTMono.ttf": "consola.ttf"}


def installed_fdot_fonts():
    """(family, bold) -> file of the FDOT TrueType fonts installed on this
    machine, registered with ezdxf's font manager.  The drawing add-on draws
    text as glyph outlines from ezdxf's own font cache, which is built once
    and does not see fonts installed later."""
    from ezdxf.fonts import fonts
    from ezdxf.fonts.font_manager import get_ttf_font_face
    found = {}
    for folder in FONT_DIRS:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("FDOT*.ttf")):
            face = get_ttf_font_face(path)
            if not fonts.font_manager.has_font(path.name):
                fonts.font_manager._font_cache.add_entry(path, face)
            found.setdefault((face.family.lower(), "bold" in face.style.lower()), path.name)
    return found


def plain_glyphs(doc):
    """Without the FDOT fonts: the centerline character as CL, fraction
    characters as plain (TEXT) or stacked (MTEXT) fractions."""
    from substructure_drawings import fdot
    for blk in doc.blocks:
        for e in blk:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            s = e.dxf.text if e.dxftype() == "TEXT" else e.text
            s = s.replace(fdot.CL_GLYPH, "CL")
            for fr, g in fdot.FRACTION_GLYPHS.items():
                s = s.replace(g, (" %s" % fdot._FRACTION_TEXT[fr]) if e.dxftype() == "TEXT" else
                              "{\\H%gx;\\S%d#%d;}" % (fdot.FRACTION, fr.numerator, fr.denominator))
            if e.dxftype() == "TEXT":
                e.dxf.text = s
            else:
                e.text = s


def preview_doc(dxf_path):
    """Read the DXF for review rendering, adjusted so the ezdxf renderer shows
    it as a plotted sheet would look.

    - Lettering: each text style's font is resolved by the family and bold
      flag of its extended font data among the installed FDOT fonts (ezdxf's
      own family match ignores the bold flag).  Where an FDOT font is not
      installed, the style uses a stand-in (FONT_SUBSTITUTES) and the FDOT
      font characters are replaced by plain text (``plain_glyphs``).
    - Linetypes: inside a viewport ezdxf applies the pattern after the
      transformation to paper space and multiplies it by the inverse viewport
      scale, while the DXF carries per-entity model-space scales for
      PSLTSCALE = 0 (``fdot.LTSCALE_PER_SF`` x drawing scale factor).  Each
      entity scale is divided by the square of its scale factor so the
      dashes plot at the intended paper size.
    - Everything plots black at the level lineweights (CADD Manual 5.10:
      0.09 mm for annotation, 0.15 mm reinforcement, 0.30 mm concrete), true
      size on the 17 x 11 PDF page.  The matplotlib backend takes the
      lineweight in mm as a width in points, so it is scaled mm -> pt, and
      the minimum width (pt) stays below 0.09 mm.
    """
    import ezdxf
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from substructure_drawings import fdot
    doc = ezdxf.readfile(dxf_path)
    installed = installed_fdot_fonts()
    missing = False
    for st in doc.styles:
        family, italic, bold = st.get_extended_font_data()
        if not family.startswith("FDOT"):
            continue
        file = installed.get((family.lower(), bold))
        if file is None:
            missing = True
            file = FONT_SUBSTITUTES[st.dxf.font]
        st.dxf.font = file
        st.discard_extended_font_data()
    if missing:
        plain_glyphs(doc)
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
                        lineweight_scaling=72.0 / 25.4, min_lineweight=0.25, min_dash_length=2.5e-5)
    return doc, cfg


def render_layout(doc, cfg, name, ax):
    """Draw a layout into ``ax`` and keep the caller's figure size (by
    default the backend shrinks the figure to matplotlib's default height,
    which drew the absolute line widths too heavy for the sheet)."""
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    Frontend(RenderContext(doc), MatplotlibBackend(ax, adjust_figure=False), config=cfg).draw_layout(
        doc.layouts.get(name), finalize=True)


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
    audit = manifest["symbology_audit"]
    for w in audit["not_on_fdot_level"] + audit["not_by_level"]:
        print("WARNING (symbology):", w)
    for q in manifest["qc"]:
        print("QC %-8s %s model %s ref %s" % (q["status"], q["check"], q["model"], q["reference"]))
    if a.previews:
        for p in previews(dxf, OUT / "previews"):
            print("preview:", p)


if __name__ == "__main__":
    main()
