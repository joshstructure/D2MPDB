"""Export the accepted MSE geometry screen as editable, full-size CAD drawings.

Requires ezdxf 1.4.4 and matplotlib. Does not modify the journal or source model.
"""
from pathlib import Path
import hashlib
import json
import math
import sys

import ezdxf
from ezdxf import bbox, units
from ezdxf.addons.drawing import matplotlib as dxf_render
from ezdxf.enums import TextEntityAlignment
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "mse_strap_check/dxf"
sys.path.insert(0, str(ROOT / "tasks/T008"))
from verify_module import number, engine, native, needed

OUT.mkdir(exist_ok=True)
journal_path = ROOT / "journal/D2_I95_Project_Journal.bpad"
journal = E.parse(str(journal_path))
base = E.parse(str(ROOT / "tasks/T008/base.bpad"))

def upstream_formulas(tree):
    return {e.get("formula").split(" = ")[0]: e.get("formula")
            for e in tree.find("report[@name='BridgeGeometry_2Beam']").iter("dynexp")
            if e.get("formula", "").split(" = ")[0] in needed}

# Refuse to export stale task values if the accepted journal or CAD source moved.
assert upstream_formulas(journal) == upstream_formulas(base)
assert engine.get("InputsValid") is True
native_check = native(journal_path)
snapshot = json.loads((ROOT / "mse_strap_check/layout_snapshot.json").read_text())
model_path = ROOT / snapshot["model_path"]
assert hashlib.sha256(model_path.read_bytes()).hexdigest() == snapshot["model_sha256"]
wallmap = {w["id"]: w for w in snapshot["walls"]}
H = number("Half", "ft")
BH = number("BoxHalf", "ft")
S = number("LayoutClear", "ft")
T = number("Tolerance", "ft")
ANGLE = math.radians(snapshot["frame_angle_deg"])
SELECTED_WALLS = [("A5", "A6", "A7"), ("B1", "B6", "B7")]
COLORS = {
    "PILE": ("216679", 35), "CAP": ("83919C", 25),
    "MSE_BACK_FACE": ("202E38", 40), "MSE_FRONT_FACE": ("728088", 18),
    "NO_MSE_PILE_BOX": ("CA746B", 18), "NO_MSE_ROW_BOX": ("B63231", 50),
    "TOLERANCE": ("AE9638", 18), "CENTER": ("8498A3", 13),
    "DIMENSIONS": ("17669C", 18), "TEXT": ("203B4A", 18),
    "TITLE": ("17669C", 30), "BORDER": ("A8B9C4", 13),
}

def document(title):
    doc = ezdxf.new("R2013", setup=True)
    doc.units = units.FT
    doc.header["$INSUNITS"] = units.FT
    doc.header["$MEASUREMENT"] = 0
    doc.header["$LUNITS"] = 2
    doc.header["$LUPREC"] = 6
    doc.header["$INSBASE"] = (0, 0, 0)
    doc.styles.new("MSE_TEXT", dxfattribs={"font": "Arial.ttf"})
    for name, (color, weight) in COLORS.items():
        doc.layers.new(name, dxfattribs={"color": 7, "true_color": int(color, 16), "lineweight": weight})
    doc.layers.get("TOLERANCE").dxf.linetype = "DASHED"
    doc.layers.get("CENTER").dxf.linetype = "CENTER"
    doc.appids.new("D2_MSE")
    doc.ezdxf_metadata()["Drawing"] = title
    doc.ezdxf_metadata()["Source journal SHA256"] = native_check["sha256"]
    doc.ezdxf_metadata()["Source CAD SHA256"] = snapshot["model_sha256"]
    doc.ezdxf_metadata()["Units"] = "Feet; plotted dimensions in inches"
    return doc

def poly(m, points, layer, tag=None, closed=True):
    e = m.add_lwpolyline(points, close=closed, dxfattribs={"layer": layer})
    if tag:
        e.set_xdata("D2_MSE", [(1000, tag)])
    return e

def rect(m, x1, y1, x2, y2, layer, tag=None):
    return poly(m, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], layer, tag)

def line(m, p1, p2, layer="BORDER"):
    return m.add_line(p1, p2, dxfattribs={"layer": layer})

def text(m, label, x, y, height=.36, layer="TEXT", align=TextEntityAlignment.LEFT):
    return m.add_text(label, dxfattribs={"height": height, "layer": layer, "style": "MSE_TEXT"}).set_placement((x, y), align=align)

def dim(m, p1, p2, base_point, angle=0, places=2):
    d = m.add_linear_dim(base=base_point, p1=p1, p2=p2, angle=angle,
                         dimstyle="EZDXF", dxfattribs={"layer": "DIMENSIONS"},
                         override={"dimtxt": .36, "dimasz": .20, "dimgap": .13,
                                   "dimexo": .10, "dimexe": .16, "dimlfac": 12,
                                   "dimdec": places, "dimzin": 0, "dimpost": "<> in",
                                   "dimtad": 1, "dimclrd": 0, "dimclre": 0,
                                   "dimclrt": 0, "dimtxsty": "MSE_TEXT"})
    d.render()
    return d.dimension

def pile_vertices(center):
    half = number("PileSize", "ft") / 2
    c, s = math.cos(ANGLE), math.sin(ANGLE)
    return [(center[0]+c*x-s*y, center[1]+s*x+c*y)
            for x, y in [(-half, -half), (half, -half), (half, half), (-half, half)]]

def bent_geometry(m, bi, transform, clipped=False):
    bent = snapshot["bents"][bi-1]
    assert math.isclose(bent["cap_length"], number("CapLength", "ft"))
    assert math.isclose(bent["cap_width"], number("CapWidth", "ft"))
    centers = [transform(p["center"]) for p in bent["piles"]]
    for j, (pile, (x, y)) in enumerate(zip(bent["piles"], centers), 1):
        tag = f"EB{bi}:P{j}"
        poly(m, [transform(v) for v in pile_vertices(pile["center"])], "PILE", tag)
        rect(m, x-BH, y-BH, x+BH, y+BH, "NO_MSE_PILE_BOX", tag)
        line(m, (x-1, y), (x+1, y), "CENTER")
        line(m, (x, y-1), (x, y+1), "CENTER")
        if clipped:
            text(m, f"P{j}", x, y-.20, .37, align=TextEntityAlignment.CENTER)
    xs = [p[0] for p in centers]; ys = [p[1] for p in centers]
    bounds = (min(xs)-BH, min(ys)-BH, max(xs)+BH, max(ys)+BH)
    rect(m, *bounds, "NO_MSE_ROW_BOX", f"EB{bi}:ROW")
    poly(m, [transform(p) for p in bent["cap"]], "CAP", f"EB{bi}:CAP")
    for wid in SELECTED_WALLS[bi-1]:
        w = wallmap[wid]
        a, z = transform(w["start"]), transform(w["end"])
        if clipped:
            # Drawing crop only. Full, untrimmed segments remain in the overlay DXF.
            a = (a[0], min(bounds[3]+1, max(bounds[1]-.4, a[1])))
            z = (z[0], min(bounds[3]+1, max(bounds[1]-.4, z[1])))
        poly(m, [a, z], "MSE_BACK_FACE", wid, closed=False)
        delta = [snapshot["wall_thickness_ft"]*v for v in w["outward"]]
        fa = transform([w["start"][i]+delta[i] for i in range(2)])
        fz = transform([w["end"][i]+delta[i] for i in range(2)])
        if clipped:
            fa = (fa[0], min(bounds[3]+1, max(bounds[1]-.4, fa[1])))
            fz = (fz[0], min(bounds[3]+1, max(bounds[1]-.4, fz[1])))
        poly(m, [fa, fz], "MSE_FRONT_FACE", wid, closed=False)
        if clipped and abs(a[1]-z[1])>1:
            for xx in [a[0], fa[0]]:
                line(m, (xx-.20, bounds[3]+.85), (xx+.20, bounds[3]+1.15), "MSE_BACK_FACE")
    return bounds, centers

def bent_panel(m, bi, cx):
    cy = 25
    bent = snapshot["bents"][bi-1]
    flip = 1 if bi == 1 else -1
    transform = lambda p: (cx+p[0]-bent["center"][0], cy+flip*(p[1]-bent["center"][1]))
    bounds, centers = bent_geometry(m, bi, transform, clipped=True)
    left, bottom, right, top = bounds
    text(m, f"END BENT {bi}", cx, 38.6, .65, "TITLE", TextEntityAlignment.CENTER)
    text(m, "Local plan | +Y into approach", cx, 37.5, .36, align=TextEntityAlignment.CENTER)
    text(m, "51.75 in from EACH nominal projected pile face", cx, 36.5, .38, "NO_MSE_ROW_BOX", TextEntityAlignment.CENTER)
    text(m, "BACK OF FACING EXCLUDED FROM RED AREA", cx, 35.5, .37, "NO_MSE_ROW_BOX", TextEntityAlignment.CENTER)
    for a, b in zip(centers, centers[1:]):
        dim(m, a, b, (0, top+2.1))
    dim(m, (left, bottom), (right, bottom), (0, bottom-2.2), places=3)
    dim(m, (right, bottom), (right, top), (right+1.7, 0), angle=90, places=3)
    # Nominal projected P1 face to its outer exclusion boundary.
    dim(m, (centers[0][0]-H, centers[0][1]), (left, centers[0][1]), (0, cy-3.1))
    for wid, x in zip(SELECTED_WALLS[bi-1][1:], [cx-10.0, cx+9.1]):
        text(m, f"{wid} return", x, top+.48, .32, align=TextEntityAlignment.CENTER)
    text(m, SELECTED_WALLS[bi-1][0]+" front wall", cx, cy-4.2, .34, align=TextEntityAlignment.CENTER)
    text(m, "CURRENT WALL POSITION", cx-13, 14.8, .38, "TITLE")
    text(m, "EXTRA SETBACK", cx+4.7, 14.8, .38, "TITLE")
    line(m, (cx-13, 14.35), (cx+13, 14.35))
    for row, (desc, formula) in enumerate([
        ("Front", f"Max(Bent{bi}Wall1Pile1Extra,Bent{bi}Wall1Pile2Extra,Bent{bi}Wall1Pile3Extra,Bent{bi}Wall1Pile4Extra)"),
        ("Left return / P1", f"Bent{bi}Wall2Pile1Extra"),
        ("Right return / P4", f"Bent{bi}Wall3Pile4Extra"),
    ]):
        y = 13.35-row*.9
        text(m, desc+" - inside exclusion box", cx-13, y, .35)
        text(m, f"{number(formula):.3f} in", cx+7.0, y, .36, "NO_MSE_ROW_BOX")
    text(m, "Extra setback is a parallel-move shortfall; no wall relocation proposed.", cx-13, 10.2, .30)

def typical_panel(m):
    cx, cy = 81, 25
    text(m, "TYPICAL PILE BOX", cx, 38.6, .65, "TITLE", TextEntityAlignment.CENTER)
    text(m, "Same full-size scale as bent plans", cx, 37.5, .36, align=TextEntityAlignment.CENTER)
    rect(m, cx-BH, cy-BH, cx+BH, cy+BH, "NO_MSE_ROW_BOX", "TYPICAL:BOX")
    rect(m, cx-H, cy-H, cx+H, cy+H, "PILE", "TYPICAL:PILE")
    rect(m, cx-H-T, cy-H-T, cx+H+T, cy+H+T, "TOLERANCE")
    text(m, "PILE", cx, cy-.15, .32, align=TextEntityAlignment.CENTER)
    dim(m, (cx-H, cy+H), (cx-BH, cy+H), (0, cy+2.0))
    dim(m, (cx+H, cy-H), (cx+BH, cy-H), (0, cy-2.0))
    dim(m, (cx+H, cy+H), (cx+H, cy+BH), (cx+2.0, 0), angle=90)
    dim(m, (cx-H, cy-H), (cx-H, cy-BH), (cx-2.0, 0), angle=90)
    dim(m, (cx-BH, cy-BH), (cx+BH, cy-BH), (0, cy-BH-2.2), places=3)
    dim(m, (cx+BH, cy-BH), (cx+BH, cy+BH), (cx+BH+2.0, 0), angle=90, places=3)
    text(m, "51.75 in = 4 ft 3-3/4 in CLEAR", cx, 35.5, .43, "NO_MSE_ROW_BOX", TextEntityAlignment.CENTER)
    text(m, "Calculated minimum: 51.649 in", 68, 14.8, .38, "TITLE")
    text(m, "Adopted: rounded UP to nearest 1/4 in", 68, 13.7, .35)
    text(m, "3 in pile placement envelope already included", 68, 12.7, .35)
    text(m, "Dashed gold outline = placement envelope", 68, 11.7, .35)
    text(m, "Do not add the placement allowance again.", 68, 10.2, .35)

sheet = document("MSE Wall Exclusion - Both End Bents - Dimensioned")
m = sheet.modelspace()
rect(m, -1, -.5, 97, 45, "BORDER")
text(m, "D2 I-95 PEDESTRIAN BRIDGE  /  MSE WALL EXCLUSION", 1, 42.5, .8, "TITLE")
text(m, "13 OCT 2026 | From journal module MSEWallExclusion | Model space: 1 unit = 1 ft | Dimensions: inches", 1, 40.9, .38)
line(m, (-1, 40), (97, 40))
line(m, (32, 9), (32, 40)); line(m, (65, 9), (65, 40)); line(m, (-1, 9), (97, 9))
bent_panel(m, 1, 15)
bent_panel(m, 2, 48)
typical_panel(m)
notes = [
    "BASIS: 18 in square piles; 54 in spacing; 2 in trial strap; 15 deg maximum plan skew; 0 in added strap-edge gap.",
    "Boxes use the journal's 3 in pile placement allowance in both plan directions. Dimensions originate at nominal projected pile faces.",
    "S = t + [(h+t) cos(alpha) + w/2 + c] / sin(alpha). Red outer row box conservatively encloses all four overlapping individual boxes.",
    "USE: Back of facing stays outside red boxes for an axis-parallel wall with its strap anchor on the wall normal through a pile center.",
    "This plan geometry screen does not establish the complete strap route, elevation clearance, connection/development or wall stability.",
    "Keep front cap-to-facing 24 in clear separately; verify battered-pile/pad clearance if piles change. Confirm vendor strap and construction gap.",
    "LAYERS: blue-green piles | gray cap | dark back of facing | pale front face | thin red individual boxes | heavy red enclosing row box.",
    "These two bent views are translated; EB2 is mirrored in Y for presentation. Companion overlay DXF retains the saved CAD model's XY feet.",
]
for i, label in enumerate(notes):
    text(m, label, 1, 7.8-i*.90, .35)
sheet.set_modelspace_vport(height=49, center=(48, 22))
sheet_path = OUT / "MSE Wall Exclusion - Both End Bents - Dimensioned.dxf"
sheet.saveas(sheet_path)

overlay = document("MSE Wall Exclusion - CAD Coordinate Overlay")
for bi in (1, 2):
    bent_geometry(overlay.modelspace(), bi, lambda p: tuple(p), clipped=False)
overlay.set_modelspace_vport(height=240, center=(-93.64, -102.05))
overlay_path = OUT / "MSE Wall Exclusion - CAD Coordinate Overlay.dxf"
overlay.saveas(overlay_path)

# Reopen the actual DXFs, audit their structure, and measure every keyed box.
checks = []
for path, expected_boxes in [(sheet_path, 9), (overlay_path, 8)]:
    reopened = ezdxf.readfile(path)
    audit = reopened.audit()
    assert not audit.errors and not audit.fixes, (path, audit.errors, audit.fixes)
    space = reopened.modelspace()
    assert reopened.units == units.FT
    boxes = list(space.query('LWPOLYLINE[layer=="NO_MSE_PILE_BOX"]'))
    assert len(boxes) == 8
    for box in boxes:
        ext = bbox.extents([box])
        assert math.isclose(ext.size.x, 2*BH, abs_tol=1e-10)
        assert math.isclose(ext.size.y, 2*BH, abs_tol=1e-10)
        assert box.closed
    assert len(space.query('LWPOLYLINE[layer=="PILE"]')) == expected_boxes
    assert len(space.query('LWPOLYLINE[layer=="CAP"]')) == 2
    assert len(space.query('LWPOLYLINE[layer=="MSE_BACK_FACE"]')) == 6
    dims = list(space.query("DIMENSION"))
    for d in dims:
        assert d.dxf.geometry in reopened.blocks and d.get_measurement()>0
    if path == overlay_path:
        tagged = {e.get_xdata("D2_MSE")[0].value: e for e in boxes}
        for bi, bent in enumerate(snapshot["bents"], 1):
            for j, pile in enumerate(bent["piles"], 1):
                ext = bbox.extents([tagged[f"EB{bi}:P{j}"]])
                center = (ext.extmin+ext.extmax)*.5
                assert math.isclose(center.x, pile["center"][0], abs_tol=1e-10)
                assert math.isclose(center.y, pile["center"][1], abs_tol=1e-10)
    checks.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "audit_errors": 0, "audit_fixes": 0, "units": "ft", "entities": len(space),
                   "native_dimensions": len(dims), "individual_pile_boxes": 8})

# Render the reopened DXF, including its generated CAD dimension blocks.
dxf_render.qsave(ezdxf.readfile(sheet_path).modelspace(), OUT / "Dimensioned plan preview.png",
                 bg="#ffffff", dpi=170, size_inches=(24, 12))
record = {"journal": str(journal_path.relative_to(ROOT)), "journal_sha256": native_check["sha256"],
          "module": "MSEWallExclusion", "source_model": snapshot["model_path"],
          "source_model_sha256": snapshot["model_sha256"], "export_date": "2026-10-13",
          "clearance_in": number("LayoutClear"), "exact_minimum_in": number("MinClear"),
          "individual_box_side_in": number("BoxSide"), "placement_allowance_in": number("Tolerance"),
          "native_journal_values_compared": native_check["native_table_and_dimension_values_compared"],
          "checked": ["DXF reopen and audit", "feet insertion units", "all eight box sides",
                      "eight overlay centers at source CAD XY coordinates", "two caps and six walls",
                      "all native dimensions have rendered blocks and positive measured distances"], "files": checks}
(OUT / "verification.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
(OUT / "Read me.txt").write_text(
    "MSE WALL EXCLUSION - 13 OCTOBER 2026\n\n"
    "Dimensioned.dxf: editable full-size plans for both end bents plus a typical pile box.\n"
    "All geometry is in feet (1 CAD unit = 1 ft); dimension text reports inches.\n"
    "Views are translated side by side. EB2 Y is reversed to show the approach upward.\n"
    "Return walls are cropped and marked with break strokes in this review drawing.\n\n"
    "CAD Coordinate Overlay.dxf: the same eight pile boxes, row boxes, pile profiles,\n"
    "caps and six untrimmed MSE walls at the saved FreeCAD model's original XY feet.\n"
    "Z = 0. This is model-local XY, not a survey/georeferenced coordinate claim.\n"
    "Insert at 0,0,0 with scale 1 and rotation 0 into a drawing using the same feet frame.\n"
    "If the destination drawing uses inches, scale the overlay by 12.\n\n"
    "Current result: 51.75 in from every nominal projected pile face.\n"
    "Includes the journal's 3 in coordinate placement allowance; do not add it again.\n"
    "Trial inputs: 2 in strap, 15 deg plan skew, zero added edge gap.\n"
    "Boundary references the BACK OF FACING. All six checked current wall faces\n"
    "intersect the conservative row exclusion boxes. DXFs do not relocate the walls.\n"
    "This is a bounded geometry screen. Vendor dimensions, full routing, elevation,\n"
    "development, pad clearance and wall stability remain separate.\n\n"
    "Source: journal/D2_I95_Project_Journal.bpad, MSEWallExclusion module.\n"
    "verification.json records exact source hashes, dimensions and file audit results.\n",
    encoding="utf-8")
print(json.dumps(record, indent=2))
