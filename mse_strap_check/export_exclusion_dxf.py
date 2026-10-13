"""Export the accepted MSE geometry screen as editable, full-size CAD drawings.

Requires ezdxf 1.4.4 and matplotlib. Does not modify the journal or source model.
"""
from pathlib import Path
import hashlib
import json
import math
import sys
import argparse

import ezdxf
from ezdxf import bbox, units
from ezdxf.addons.drawing import matplotlib as dxf_render
from ezdxf.enums import TextEntityAlignment
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
args_parser = argparse.ArgumentParser()
args_parser.add_argument("--journal", type=Path, default=ROOT / "journal/D2_I95_Project_Journal.bpad")
args_parser.add_argument("--output", type=Path, default=ROOT / "mse_strap_check/dxf")
args = args_parser.parse_args()
OUT = args.output.resolve()
sys.path.insert(0, str(ROOT / "tasks/T009"))
from verify_module import number, engine, native, needed

OUT.mkdir(parents=True, exist_ok=True)
journal_path = args.journal.resolve()
journal = E.parse(str(journal_path))
base = E.parse(str(ROOT / "tasks/T009/base.bpad"))

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
FE = number("FrontExtent", "ft")
SE = number("SideExtent", "ft")
DT = number("DrawTop", "ft")
S = number("LayoutClear", "ft")
SIDE = number("SideClear", "ft")
ANGLE = math.radians(snapshot["frame_angle_deg"])
SELECTED_WALLS = [("A5", "A6", "A7"), ("B1", "B6", "B7")]
COLORS = {
    "PILE": ("216679", 35), "CAP": ("83919C", 25),
    "MSE_BACK_FACE": ("202E38", 40), "MSE_FRONT_FACE": ("728088", 18),
    "FRONT_LIMIT": ("B63231", 50), "SIDE_LIMIT": ("AB6321", 40),
    "FRONT_PILE_LIMIT": ("CA746B", 18), "CENTER": ("8498A3", 13),
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
    front_sign = -1 if clipped or bi == 1 else 1
    for j, (pile, (x, y)) in enumerate(zip(bent["piles"], centers), 1):
        tag = f"EB{bi}:P{j}"
        poly(m, [transform(v) for v in pile_vertices(pile["center"])], "PILE", tag)
        poly(m, [(x-H,y+front_sign*FE),(x+H,y+front_sign*FE)], "FRONT_PILE_LIMIT", tag, closed=False)
        line(m, (x-1, y), (x+1, y), "CENTER")
        line(m, (x, y-1), (x, y+1), "CENTER")
        if clipped:
            text(m, f"P{j}", x, y-.20, .37, align=TextEntityAlignment.CENTER)
    xs = [p[0] for p in centers]; ys = [p[1] for p in centers]
    front = min(ys)-FE if front_sign == -1 else max(ys)+FE
    open_end = max(ys)+DT if front_sign == -1 else min(ys)-DT
    bounds = (min(xs)-SE, front, max(xs)+SE, open_end)
    left, front, right, open_end = bounds
    poly(m, [(left,front),(right,front)], "FRONT_LIMIT", f"EB{bi}:FRONT", closed=False)
    poly(m, [(left,front),(left,open_end)], "SIDE_LIMIT", f"EB{bi}:LEFT", closed=False)
    poly(m, [(right,front),(right,open_end)], "SIDE_LIMIT", f"EB{bi}:RIGHT", closed=False)
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
    text(m, f"FRONT {number('LayoutClear'):.2f} in / SIDES {number('SideClear'):.2f} in clear", cx, 36.5, .38, "FRONT_LIMIT", TextEntityAlignment.CENTER)
    text(m, "FRONT STRAP CHECK / SPECIFIED SIDE OFFSETS", cx, 35.5, .37, "FRONT_LIMIT", TextEntityAlignment.CENTER)
    for a, b in zip(centers, centers[1:]):
        dim(m, a, b, (0, top+2.1))
    dim(m, (left, bottom), (right, bottom), (0, bottom-2.2), places=3)
    dim(m, (centers[1][0],centers[1][1]-H), (centers[1][0],centers[1][1]-FE), (centers[1][0]+1.6,0), angle=90)
    # Nominal end-pile faces to the specified side boundaries.
    dim(m, (centers[0][0]-H, centers[0][1]), (left, centers[0][1]), (0, cy-3.1))
    dim(m, (centers[3][0]+H,centers[3][1]), (right,centers[3][1]), (0,cy-3.1))
    for wid, x in zip(SELECTED_WALLS[bi-1][1:], [cx-8.5,cx+8.5]):
        text(m, f"{wid} return", x, top+.48, .32, align=TextEntityAlignment.CENTER)
    text(m, SELECTED_WALLS[bi-1][0]+" front wall", cx, cy-4.6, .34, align=TextEntityAlignment.CENTER)
    text(m, "CURRENT WALL POSITION", cx-13, 14.8, .38, "TITLE")
    text(m, "EXTRA SETBACK", cx+4.7, 14.8, .38, "TITLE")
    line(m, (cx-13, 14.35), (cx+13, 14.35))
    for row, (desc, formula) in enumerate([
        ("Front", f"Max(Bent{bi}Wall1Pile1Extra,Bent{bi}Wall1Pile2Extra,Bent{bi}Wall1Pile3Extra,Bent{bi}Wall1Pile4Extra)"),
        ("Left return / P1", f"Bent{bi}Wall2Pile1Extra"),
        ("Right return / P4", f"Bent{bi}Wall3Pile4Extra"),
    ]):
        y = 13.35-row*.9
        text(m, desc+(" / front strap" if row==0 else " / 24 in specified"), cx-13, y, .35)
        text(m, f"{number(formula):.3f} in", cx+7.0, y, .36, "FRONT_LIMIT")
    text(m, "Extra setback is a parallel-move shortfall; no wall relocation proposed.", cx-13, 10.2, .30)

def typical_panel(m):
    cx, cy = 81, 25
    text(m, "TYPICAL FRONT / SIDE LIMITS", cx, 38.6, .56, "TITLE", TextEntityAlignment.CENTER)
    text(m, "Same full-size scale as bent plans", cx, 37.5, .36, align=TextEntityAlignment.CENTER)
    poly(m, [(cx-SE,cy-FE),(cx+SE,cy-FE)], "FRONT_LIMIT", "TYPICAL:FRONT", closed=False)
    for sign in [-1,1]:
        poly(m, [(cx+sign*SE,cy-FE),(cx+sign*SE,cy+DT)], "SIDE_LIMIT", closed=False)
    rect(m, cx-H, cy-H, cx+H, cy+H, "PILE", "TYPICAL:PILE")
    text(m, "PILE", cx, cy-.15, .32, align=TextEntityAlignment.CENTER)
    dim(m, (cx-H,cy), (cx-SE,cy), (0,cy+1.3))
    dim(m, (cx+H,cy), (cx+SE,cy), (0,cy+1.3))
    dim(m, (cx,cy-H), (cx,cy-FE), (cx+.9,0), angle=90)
    dim(m, (cx-SE,cy-FE), (cx+SE,cy-FE), (0,cy-FE-2.2), places=2)
    text(m, "OPEN - no rear-wall criterion", cx, cy+DT+.6, .35, align=TextEntityAlignment.CENTER)
    text(m, f"Front: {number('LayoutClear'):.2f} in / Side: {number('SideClear'):.2f} in", cx, 35.5, .43, "FRONT_LIMIT", TextEntityAlignment.CENTER)
    text(m, f"Front calculated minimum: {number('MinClear'):.3f} in", 68, 14.8, .38, "TITLE")
    text(m, "Front rounded UP to nearest 1/4 in", 68, 13.7, .35)
    text(m, "Nominal pile width; NO placement tolerance", 68, 12.7, .35)
    text(m, "Side offset is specified; no side strap check", 68, 11.7, .35)
    text(m, "Back of facing is the wall reference.", 68, 10.2, .35)

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
    "Nominal pile width only; NO pile placement allowance. Dimensions originate at nominal pile faces. Either front skew direction may be used.",
    "FRONT: S = [h cos(alpha) + w/2 + c] / sin(alpha), rounded upward. SIDES: specified 24 in minimum; side strap feasibility is NOT evaluated.",
    "USE: Maintain the shown front/side clearances to BACK OF FACING. Front strap starts on the normal through a nominal pile center.",
    "This plan geometry screen does not establish the complete strap route, elevation clearance, connection/development or wall stability.",
    "Keep front cap-to-facing 24 in clear separately; verify battered-pile/pad clearance if piles change. Confirm vendor strap and construction gap.",
    "LAYERS: blue-green piles | gray cap | dark back of facing | red front limit | amber side limits. No rear boundary is specified.",
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

# Reopen the actual DXFs; audit layers, open limits, measured clearances and source coordinates.
checks = []
for path, pile_count in [(sheet_path,9),(overlay_path,8)]:
    reopened = ezdxf.readfile(path); audit = reopened.audit(); space = reopened.modelspace()
    assert not audit.errors and not audit.fixes
    assert reopened.units == units.FT
    limits=list(space.query('LWPOLYLINE[layer=="FRONT_PILE_LIMIT"]'))
    assert len(limits)==8 and all(not e.closed for e in limits)
    assert len(space.query('LWPOLYLINE[layer=="PILE"]'))==pile_count
    assert len(space.query('LWPOLYLINE[layer=="CAP"]'))==2
    assert len(space.query('LWPOLYLINE[layer=="MSE_BACK_FACE"]'))==6
    assert not space.query('LWPOLYLINE[layer=="TOLERANCE"]')
    dims=list(space.query('DIMENSION'))
    for d in dims: assert d.dxf.geometry in reopened.blocks and d.get_measurement()>0
    if path==overlay_path:
        tagged={e.get_xdata('D2_MSE')[0].value:e for e in space.query('LWPOLYLINE') if e.has_xdata('D2_MSE') and e.dxf.layer in ['FRONT_PILE_LIMIT','FRONT_LIMIT','SIDE_LIMIT']}
        for bi,bent in enumerate(snapshot['bents'],1):
            sign=-1 if bi==1 else 1
            for j,pile in enumerate(bent['piles'],1):
                ext=bbox.extents([tagged[f'EB{bi}:P{j}']]);center=(ext.extmin+ext.extmax)*.5
                assert math.isclose(center.x,pile['center'][0],abs_tol=1e-10)
                assert math.isclose((center.y-pile['center'][1])*sign-H,S,abs_tol=1e-10)
            for tag,x in [('LEFT',min(p['center'][0] for p in bent['piles'])-SE),('RIGHT',max(p['center'][0] for p in bent['piles'])+SE)]:
                e=tagged[f'EB{bi}:{tag}'];assert not e.closed
                assert all(math.isclose(v[0],x,abs_tol=1e-10) for v in e.get_points())
        assert len(space.query('LWPOLYLINE[layer=="FRONT_LIMIT"]'))==2
        assert len(space.query('LWPOLYLINE[layer=="SIDE_LIMIT"]'))==4
    checks.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'audit_errors':0,'audit_fixes':0,'units':'ft','entities':len(space),'native_dimensions':len(dims),'front_pile_limits':8})

# Render the reopened DXF, including its generated CAD dimension blocks.
dxf_render.qsave(ezdxf.readfile(sheet_path).modelspace(), OUT / "Dimensioned plan preview.png",
                 bg="#ffffff", dpi=170, size_inches=(24, 12))
record = {"journal": str(journal_path.relative_to(ROOT)), "journal_sha256": native_check["sha256"],
          "module": "MSEWallExclusion", "source_model": snapshot["model_path"],
          "source_model_sha256": snapshot["model_sha256"], "export_date": "2026-10-13",
          "front_clear_in": number("LayoutClear"), "front_exact_minimum_in": number("MinClear"),
          "side_clear_in": number("SideClear"), "alpha_deg": number(chr(945),"deg"),
          "pile_tolerance_included":False,"rear_wall_evaluated":False,"side_straps_evaluated":False,
          "native_journal_values_compared": native_check["native_table_and_dimension_values_compared"],
          "checked": ["DXF reopen/audit and feet units", "all eight front limits at source CAD XY coordinates",
                      "four side limits at specified nominal pile-face offsets", "open boundaries without rear limits",
                      "two caps, eight piles and six current wall back faces", "native dimension blocks"], "files": checks}
(OUT/"verification.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
(OUT/"Read me.txt").write_text(
    "MSE FRONT / SIDE CLEARANCE - 13 OCTOBER 2026 - T009\n\n"
    "Supersedes the previous four-sided, 51.75-inch exclusion boxes.\n"
    "Front wall: alpha=15 degrees, 2-inch strap, zero edge gap, nominal pile width.\n"
    "Pile placement tolerance is excluded. Computed front clear is 37.452 inches;\n"
    "adopted front clear is 37.50 inches after upward quarter-inch rounding.\n"
    "Side walls: specified 24.00-inch minimum from nominal end-pile faces.\n"
    "Side strap feasibility and rear walls are NOT evaluated.\n"
    "All wall clearances are to BACK OF FACING. Front cap clearance is separate.\n\n"
    "Dimensioned.dxf: translated side-by-side plans; EB2 Y is mirrored so approach\n"
    "is upward. Return walls are cropped at break strokes. Dimensions are editable.\n"
    "CAD Coordinate Overlay.dxf: original saved model-local XY, feet, Z=0.\n"
    "The overlay includes untrimmed current walls, piles, caps and open front/side limits.\n"
    "This is not a survey/georeferenced coordinate claim. Insert at 0,0,0 with scale 1\n"
    "and rotation 0 in the same feet frame; use scale 12 for an inch-unit drawing.\n"
    "Both DXFs use feet; dimension text displays inches.\n\n"
    "These are nominal geometry and specified layout checks. Vendor details, actual\n"
    "pile positions, full reinforcement routing, elevation, pad clearance and wall\n"
    "stability remain separate. Current walls have not been relocated.\n"
    "Source: accepted MSEWallExclusion journal module; see verification.json.\n",
    encoding="utf-8")
print(json.dumps(record,indent=2))
