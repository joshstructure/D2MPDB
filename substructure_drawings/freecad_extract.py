"""FreeCAD-side snapshot of the end bents and pier for the substructure DXF.

Run with FreeCAD 1.1 ``freecadcmd`` (never the GUI) on a *copy* of the
registered model.  The script is read-only: it opens the copy, computes
hidden-line projections and reinforcement centerlines, writes one JSON
snapshot and closes the document without saving.

Inputs are environment variables so the call works with ``freecadcmd``:

* ``SUBDWG_MODEL``   path of the FCStd copy to read
* ``SUBDWG_RUNTIME`` folder holding the model's ``freecad_tools`` controllers
* ``SUBDWG_OUT``     JSON snapshot to write

All snapshot lengths are feet.  Elevations (z) are the model's absolute
elevations (model mm / 304.8, which matches the CAD tables workbook).
"""
import hashlib
import json
import math
import os
import sys
import traceback

MODEL = os.environ["SUBDWG_MODEL"]
RUNTIME = os.environ["SUBDWG_RUNTIME"]
OUT = os.environ["SUBDWG_OUT"]
SOURCE_SHA = os.environ.get("SUBDWG_SOURCE_SHA256", "")
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import TechDraw  # noqa: E402

FT = 304.8
V = App.Vector
DEFLECTION = 0.05  # mm, discretization of non-line/circle projected curves

# ---------------------------------------------------------------- structures
# Roles map to FDOT levels in the builder.  Pile clip depth is drawing-only.
STRUCTURES = {
    "EB1": {
        "title": "END BENT 1",
        "e1": (1, 0, 0),          # sheet right in plan/elevation (looking back station)
        "plan_up": (0, 1, 0),     # plan sheet up = away from the elevation viewer
        "concrete": {
            "cap": ["BridgeCapEB1"],
            "backwall": ["BridgeBackwallEB1"],
            "cheek": ["BridgeCheekEB11", "BridgeCheekEB12"],
            "pedestal": ["BridgePedestalEB1B1", "BridgePedestalEB1B2"],
            "pad": ["BridgePadEB1S1B1", "BridgePadEB1S1B2"],
            "pile_conc": ["BridgePileEB1P1", "BridgePileEB1P2", "BridgePileEB1P3", "BridgePileEB1P4"],
        },
        "context": {
            # Front MSE wall only; the side walls run away from the bent.
            "mse": ["WallA5Mitred"],
            "landing": ["A_BridgeLandingAtReturns"],
            "beam": ["BridgeBeamS1B1", "BridgeBeamS1B2"],
            # Schematic geotechnical straps (D-045): zero-thickness faces.
            "strap": ["GeotechnicalStrapEB1S1", "GeotechnicalStrapEB1S2", "GeotechnicalStrapEB1S3",
                      "GeotechnicalStrapEB1", "GeotechnicalStrapEB1S5", "GeotechnicalStrapEB1S6",
                      "GeotechnicalStrapEB1S7"],
        },
        "bar_groups": {
            "cap": ["CageEB1Bars"],
            "backwall": ["SteelBridgeBackwallEB1Bars"],
            "cheek": ["SteelBridgeCheekEB11Bars", "SteelBridgeCheekEB12Bars"],
            "pedestal": ["PedSteelEB1B1Bars", "PedSteelEB1B2Bars"],
        },
        "wwr": ["WWRCheekEB11", "WWRCheekEB12"],
        "pile_clip_ft": 4.0,
    },
    "PIER": {
        "title": "PIER",
        "e1": (-1, 0, 0),         # looking ahead station
        "plan_up": (0, -1, 0),
        "concrete": {
            "cap": ["BridgeCapPier"],
            "pier_wall": ["BridgePierWallSolid"],
            "pedestal": ["BridgePedestalPierB1", "BridgePedestalPierB2"],
            "pad": ["BridgePadPierS1B1", "BridgePadPierS2B1", "BridgePadPierS1B2", "BridgePadPierS2B2"],
            "pile_steel": ["BridgePilePierP1", "BridgePilePierP2", "BridgePilePierP3", "BridgePilePierP4"],
        },
        "context": {
            "beam": ["BridgeBeamS1B1", "BridgeBeamS1B2", "BridgeBeamS2B1", "BridgeBeamS2B2"],
        },
        "bar_groups": {
            "cap": ["CagePierBars"],
            "pedestal": ["PedSteelPierB1Bars", "PedSteelPierB2Bars"],
        },
        "wwr": [],
        "pile_clip_ft": None,      # piles drawn to the pier-wall bottom less 2 ft
    },
    "EB2": {
        "title": "END BENT 2",
        "e1": (-1, 0, 0),         # looking ahead station
        "plan_up": (0, -1, 0),
        "concrete": {
            "cap": ["BridgeCapEB2"],
            "backwall": ["BridgeBackwallEB2"],
            "cheek": ["BridgeCheekEB21", "BridgeCheekEB22"],
            "pedestal": ["BridgePedestalEB2B1", "BridgePedestalEB2B2"],
            "pad": ["BridgePadEB2S2B1", "BridgePadEB2S2B2"],
            "pile_conc": ["BridgePileEB2P1", "BridgePileEB2P2", "BridgePileEB2P3", "BridgePileEB2P4"],
        },
        "context": {
            "mse": ["WallB1Mitred"],
            "landing": ["B_BridgeLandingAtReturns"],
            "beam": ["BridgeBeamS2B1", "BridgeBeamS2B2"],
            "strap": ["GeotechnicalStrapEB2S1", "GeotechnicalStrapEB2S2", "GeotechnicalStrapEB2S3",
                      "GeotechnicalStrapEB2", "GeotechnicalStrapEB2S5", "GeotechnicalStrapEB2S6",
                      "GeotechnicalStrapEB2S7"],
        },
        "bar_groups": {
            "cap": ["CageEB2Bars"],
            "backwall": ["SteelBridgeBackwallEB2Bars"],
            "cheek": ["SteelBridgeCheekEB21Bars", "SteelBridgeCheekEB22Bars"],
            "pedestal": ["PedSteelEB2B1Bars", "PedSteelEB2B2Bars"],
        },
        "wwr": ["WWRCheekEB21", "WWRCheekEB22"],
        "pile_clip_ft": 4.0,
    },
}
STATION = (0, -1, 0)  # stationing increases toward -Y (EB1 -> EB2)
SECTION_DEPTH_FT = 1.25  # sections show the cut face and this much beyond it
LOG = []


def log(msg):
    LOG.append(msg)


def r6(x):
    return round(float(x), 6)


# ------------------------------------------------------------------ frames
def rotation_to(e1, e2):
    """Rotation taking global vectors to (e1., e2., n.) with n = e1 x e2 toward viewer."""
    a, b = V(*e1), V(*e2)
    n = a.cross(b)
    m = App.Matrix(a.x, a.y, a.z, 0, b.x, b.y, b.z, 0, n.x, n.y, n.z, 0, 0, 0, 0, 1)
    return m


def to_view(shape, origin, e1, e2):
    s = shape.copy()
    s.translate(V(*origin) * -1)
    return s.transformGeometry(rotation_to(e1, e2))


def edge_record(edge, scale=1.0 / FT):
    """2D edge (z = 0 view frame, mm) -> JSON record in feet."""
    c = edge.Curve
    p0, p1 = edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)
    if isinstance(c, (Part.Line, Part.LineSegment)):
        if (p1 - p0).Length < 1e-6:
            return None
        return {"t": "L", "p": [[r6(p0.x * scale), r6(p0.y * scale)], [r6(p1.x * scale), r6(p1.y * scale)]]}
    if isinstance(c, Part.Circle) and abs(abs(c.Axis.z) - 1) < 1e-9:
        pm = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
        closed = (p1 - p0).Length < 1e-6
        return {"t": "C" if closed else "A", "c": [r6(c.Center.x * scale), r6(c.Center.y * scale)],
                "r": r6(c.Radius * scale),
                "p": [[r6(p.x * scale), r6(p.y * scale)] for p in (p0, pm, p1)]}
    pts = edge.discretize(Deflection=DEFLECTION)
    if len(pts) < 2:
        return None
    return {"t": "P", "p": [[r6(p.x * scale), r6(p.y * scale)] for p in pts]}


def project(shapes_by_role, origin, e1, e2):
    """Hidden-line projection of all shapes together; each edge tagged with a role.

    Visible/hidden comes from one HLR pass over the compound so that every
    object hides the others.  Role assignment matches each result edge to the
    per-object projections (the edge lies on that object's projected outline).
    """
    roles, shapes = [], []
    for role, items in shapes_by_role.items():
        for name, shp in items:
            roles.append((role, name))
            shapes.append(to_view(shp, origin, e1, e2))
    if not shapes:
        return []
    allres = TechDraw.projectEx(Part.makeCompound(shapes), V(0, 0, 1))
    per = []
    for shp in shapes:
        res = TechDraw.projectEx(shp, V(0, 0, 1))
        es = []
        for comp in res:
            if comp is not None and not comp.isNull():
                es.extend(comp.Edges)
        per.append(Part.makeCompound(es) if es else None)
    out = []
    groups = [(0, 1), (1, 1), (3, 1), (5, 0), (6, 0), (8, 0)]  # hard/smooth/outline visible; hidden
    for idx, vis in groups:
        comp = allres[idx]
        if comp is None or comp.isNull():
            continue
        for e in comp.Edges:
            mid = e.valueAt(0.5 * (e.FirstParameter + e.LastParameter))
            vx = Part.Vertex(mid)
            best, best_d = None, 1e9
            for k, pc in enumerate(per):
                if pc is None:
                    continue
                d = vx.distToShape(pc)[0]
                if d < best_d:
                    best, best_d = k, d
            rec = edge_record(e)
            if rec is None:
                continue
            rec["vis"] = vis
            if best is not None and best_d < 0.05:
                rec["role"], rec["obj"] = roles[best]
            else:
                rec["role"], rec["obj"] = "unknown", ""
            out.append(rec)
    return out


def clip_box(shape, xmin=None, xmax=None, ymin=None, ymax=None, zmin=None, zmax=None):
    bb = shape.BoundBox
    x0 = bb.XMin - 10 if xmin is None else xmin
    x1 = bb.XMax + 10 if xmax is None else xmax
    y0 = bb.YMin - 10 if ymin is None else ymin
    y1 = bb.YMax + 10 if ymax is None else ymax
    z0 = bb.ZMin - 10 if zmin is None else zmin
    z1 = bb.ZMax + 10 if zmax is None else zmax
    if x1 <= x0 or y1 <= y0 or z1 <= z0:
        return None
    box = Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
    res = shape.common(box)
    return res if res.Volume > 1e-3 else None


# -------------------------------------------------------------- rebar data
def centerline(rb):
    """Global centerline edges of a native rebar, validated against its solid."""
    base = rb.Base
    candidates = []
    if base is not None and hasattr(base, "Shape") and not base.Shape.isNull():
        s = base.Shape.copy()
        s.transformShape(rb.Placement.toMatrix())
        candidates.append(("placement*base", s))
        candidates.append(("base", base.Shape.copy()))
    try:
        wires, _ = rb.Proxy.getRebarData(rb)
        if wires:
            candidates.append(("rebardata", Part.makeCompound(wires)))
    except Exception:
        pass
    r = float(rb.Diameter) / 2
    # Tight box: the default OCC box is loose around curved sweep surfaces.
    sb = rb.Shape.optimalBoundingBox(True, False)
    for tag, cand in candidates:
        cb = cand.BoundBox
        # The bar solid must sit inside the centerline box grown by the radius...
        err = max(0.0, (cb.XMin - r) - sb.XMin, sb.XMax - (cb.XMax + r), (cb.YMin - r) - sb.YMin,
                  sb.YMax - (cb.YMax + r), (cb.ZMin - r) - sb.ZMin, sb.ZMax - (cb.ZMax + r))
        # ...and the centerline itself must lie inside the bar solid.
        inside = all(rb.Shape.isInside(e.valueAt(e.FirstParameter + t * (e.LastParameter - e.FirstParameter)), 0.05, True)
                     for e in cand.Edges for t in (0.0, 0.5, 1.0))
        if inside and err < 1.0:
            return tag, cand, err
    raise ValueError("No validated centerline for " + rb.Name)


def edge3(e):
    c = e.Curve
    p0, p1 = e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)
    f = 1.0 / FT
    if isinstance(c, (Part.Line, Part.LineSegment)):
        return {"t": "L", "p": [[r6(p0.x * f), r6(p0.y * f), r6(p0.z * f)], [r6(p1.x * f), r6(p1.y * f), r6(p1.z * f)]]}
    if isinstance(c, Part.Circle):
        pm = e.valueAt(0.5 * (e.FirstParameter + e.LastParameter))
        return {"t": "A", "c": [r6(c.Center.x * f), r6(c.Center.y * f), r6(c.Center.z * f)], "r": r6(c.Radius * f),
                "n": [r6(c.Axis.x), r6(c.Axis.y), r6(c.Axis.z)],
                "p": [[r6(p.x * f), r6(p.y * f), r6(p.z * f)] for p in (p0, pm, p1)]}
    pts = e.discretize(Deflection=DEFLECTION)
    return {"t": "P", "p": [[r6(p.x * f), r6(p.y * f), r6(p.z * f)] for p in pts]}


def ordered_edges(shape):
    """Edges of a single open wire in path order (Part sorts them for us)."""
    if len(shape.Wires) == 1:
        return shape.Wires[0].OrderedEdges
    try:
        return Part.Wire(Part.__sortEdges__(shape.Edges)).OrderedEdges
    except Exception:
        return shape.Edges


def bar_record(rb, component, group):
    tag, cl, err = centerline(rb)
    edges = [edge3(e) for e in ordered_edges(cl)]
    return {
        "name": rb.Name, "label": rb.Label, "component": component, "group": group,
        "mark_model": str(getattr(rb, "Mark", "")),
        "dia_in": r6(float(rb.Diameter) / 25.4),
        "amount": int(rb.Amount),
        "length_in": r6(float(rb.Length) / 25.4) if "Length" in rb.PropertiesList else None,
        "centerline_source": tag, "bbox_err_mm": r6(err),
        "edges": edges,
    }


# --------------------------------------------------------------------- main
def model_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run():
    doc = App.openDocument(MODEL)
    snap = {"schema": 2, "units": "ft", "model_sha256": SOURCE_SHA or model_hash(MODEL),
            "station_direction": list(STATION), "structures": {}, "log": LOG}
    for key, cfg in STRUCTURES.items():
        S = {"title": cfg["title"], "e1": list(cfg["e1"]), "plan_up": list(cfg["plan_up"])}
        get = doc.getObject
        conc = {role: [(n, get(n).Shape) for n in names] for role, names in cfg["concrete"].items()}
        cap = get(cfg["concrete"]["cap"][0]).Shape.BoundBox
        cap_bottom = cap.ZMin
        # Origin: cap core center in plan (PGL is centered on the caps), z = 0.
        origin = ((cap.XMin + cap.XMax) / 2, (cap.YMin + cap.YMax) / 2, 0.0)
        S["origin_ft"] = [r6(v / FT) for v in origin]
        S["cap_bb_ft"] = [r6(v / FT) for v in (cap.XMin, cap.YMin, cap.ZMin, cap.XMax, cap.YMax, cap.ZMax)]
        # Drawing clip of piles (and pier wall context).
        clip_z = None
        if cfg["pile_clip_ft"] is not None:
            clip_z = cap_bottom - cfg["pile_clip_ft"] * FT
        else:
            wall = get(cfg["concrete"]["pier_wall"][0]).Shape.BoundBox
            clip_z = wall.ZMin - 2.0 * FT
        S["pile_clip_z_ft"] = r6(clip_z / FT)
        for role in ("pile_conc", "pile_steel"):
            if role in conc:
                conc[role] = [(n, clip_box(s, zmin=clip_z)) for n, s in conc[role]]
        meta = {}
        for role, items in conc.items():
            for n, s in items:
                shp = get(n).Shape
                b = shp.BoundBox
                verts = sorted({(r6(p.X / FT), r6(p.Y / FT), r6(p.Z / FT)) for p in shp.Vertexes})
                meta[n] = {"role": role, "label": get(n).Label,
                           "bb_ft": [r6(v / FT) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)],
                           "vertices_ft": [list(v) for v in verts] if len(verts) <= 2000 else []}
        S["concrete"] = meta
        ctx = {}
        for role, names in cfg["context"].items():
            for n in names:
                o = get(n)
                if o is None:
                    log("missing context " + n)
                    continue
                b = o.Shape.BoundBox
                ctx[n] = {"role": role, "label": o.Label,
                          "bb_ft": [r6(v / FT) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]}
        S["context"] = ctx

        e1 = cfg["e1"]
        up = cfg["plan_up"]
        # ---- plan (looking down): substructure concrete only
        S["plan"] = project(conc, origin, e1, up)
        # ---- elevation (looking along plan_up, z up)
        S["elev"] = project(conc, origin, e1, (0, 0, 1))
        # ---- transverse sections, sheet right = station, viewer looking +X
        sx = (cap.XMin + cap.XMax) / 2
        piles = cfg["concrete"].get("pile_conc") or cfg["concrete"].get("pile_steel")
        pile_x = sorted(((get(n).Shape.BoundBox.XMin + get(n).Shape.BoundBox.XMax) / 2) for n in piles)
        peds = cfg["concrete"]["pedestal"]
        ped_x = sorted(((get(n).Shape.BoundBox.XMin + get(n).Shape.BoundBox.XMax) / 2) for n in peds)
        cuts = {"between_piles": sx, "at_pile": pile_x[1], "at_beam": ped_x[0]}
        S["pile_x_ft"] = [r6(x / FT) for x in pile_x]
        S["ped_x_ft"] = [r6(x / FT) for x in ped_x]
        sec_ctx = dict(conc)
        for role, names in cfg["context"].items():
            if role == "beam":
                continue
            sec_ctx[role] = [(n, get(n).Shape) for n in names if get(n) is not None]
        # Context is clipped near the bent so sections stay local.
        ymin, ymax = cap.YMin - 6 * FT, cap.YMax + 6 * FT
        for role in ("mse", "landing"):
            if role in sec_ctx:
                sec_ctx[role] = [(n, clip_box(s, ymin=ymin, ymax=ymax, zmin=clip_z)) for n, s in sec_ctx[role]]
                sec_ctx[role] = [(n, s) for n, s in sec_ctx[role] if s is not None]
        S["sections"] = {}
        S["section_depth_ft"] = SECTION_DEPTH_FT
        for tag, x in cuts.items():
            # Cut face plus what lies within SECTION_DEPTH_FT beyond it.
            keep = Part.makeBox(SECTION_DEPTH_FT * FT, 400000.0, 400000.0, V(x, -200000.0, -200000.0))
            parts = {}
            for role, items in sec_ctx.items():
                if role == "strap":
                    continue
                lst = []
                for n, s in items:
                    if s is None:
                        continue
                    c = s.common(keep)
                    if c.Volume > 1e-3:
                        lst.append((n, c))
                if lst:
                    parts[role] = lst
            # Geotechnical straps are zero-thickness reference faces (D-045),
            # seen edge-on in a section: the strap nearest the cut (one lying
            # in the slab if there is one) is projected whole, so each
            # section shows one strap at its elevation.
            straps = [(n, s) for n, s in sec_ctx.get("strap", []) if s is not None]
            if straps:
                def strap_dist(item, x=x):
                    b = item[1].BoundBox
                    if b.XMin <= x + SECTION_DEPTH_FT * FT and b.XMax >= x:
                        return 0.0
                    return min(abs(b.XMin - x), abs(b.XMax - x))
                parts["strap"] = [min(straps, key=strap_dist)]
            S["sections"][tag] = {"x_ft": r6((x - origin[0]) / FT), "x_global_ft": r6(x / FT),
                                  "edges": project(parts, (x, 0, 0), STATION, (0, 0, 1))}
        # ---- end view of the whole support, looking +X (sheet right = station)
        S["end_view"] = {"edges": project(conc, (cap.XMin, 0, 0), STATION, (0, 0, 1))}
        # ---- cheek views (end bents): looking +X at the left cheek / -X at right
        if "cheek" in cfg["concrete"]:
            S["cheek_views"] = {}
            for n in cfg["concrete"]["cheek"]:
                cb = get(n).Shape.BoundBox
                left = cb.XMax <= cap.XMin + 1.0
                parts = {"cheek": [(n, get(n).Shape)]}
                # Include the cap/backwall ends within 1 ft of the cheek for context.
                for role in ("cap", "backwall"):
                    items = []
                    for m, s in conc[role]:
                        c = clip_box(s, xmax=cap.XMin + FT) if left else clip_box(s, xmin=cap.XMax - FT)
                        if c is not None:
                            items.append((m, c))
                    parts[role] = items
                # Looking at the outside face: left cheek seen from -X (sheet right = station)
                e1v = STATION if left else tuple(-v for v in STATION)
                S["cheek_views"][n] = {"side": "left" if left else "right",
                                       "edges": project(parts, (cb.XMin if left else cb.XMax, origin[1], 0), e1v, (0, 0, 1))}
        # ---- cheek wall sections (end bents), after sample sheet B1-19
        # (Sections J-J and H-H): a vertical cut through the cheek wall 1 ft
        # in front of the FFBW, seen as the elevation is seen (coordinates
        # (u, z) of the elevation frame), and a horizontal cut at mid
        # backwall height seen from above (coordinates (u, v) of the plan
        # frame).  Each shows the cut face and SECTION_DEPTH_FT beyond it,
        # within 3 ft of the cheek.
        if "cheek" in cfg["concrete"]:
            S["cheek_sections"] = {}
            bw = get(cfg["concrete"]["backwall"][0]).Shape.BoundBox
            ffbw_y = bw.YMin if e1[0] > 0 else bw.YMax   # backwall face toward the bridge
            y_cut = ffbw_y - e1[0] * FT
            y_far = y_cut + e1[0] * SECTION_DEPTH_FT * FT   # beyond the cut, away from the viewer
            z_cut = cap.ZMax + 0.5 * (bw.ZMax - cap.ZMax)
            for n in cfg["concrete"]["cheek"]:
                cb = get(n).Shape.BoundBox
                left = cb.XMax <= cap.XMin + 1.0
                xr = (cb.XMin - 3 * FT, cb.XMax + 3 * FT)
                side_parts, top_parts = {}, {}
                for role in ("cheek", "cap", "backwall"):
                    for m, s in conc[role]:
                        c = clip_box(s, xmin=xr[0], xmax=xr[1], ymin=min(y_cut, y_far), ymax=max(y_cut, y_far))
                        if c is not None:
                            side_parts.setdefault(role, []).append((m, c))
                        c = clip_box(s, xmin=xr[0], xmax=xr[1], zmin=z_cut - SECTION_DEPTH_FT * FT, zmax=z_cut)
                        if c is not None:
                            top_parts.setdefault(role, []).append((m, c))
                S["cheek_sections"][n] = {
                    "side": "left" if left else "right",
                    "y_cut_ft": r6(y_cut / FT), "z_cut_ft": r6(z_cut / FT),
                    "side_edges": project(side_parts, (origin[0], y_cut, 0), e1, (0, 0, 1)),
                    "top_edges": project(top_parts, (origin[0], origin[1], z_cut), e1, up),
                }
        # ---- reinforcement
        bars = []
        for comp, groups in cfg["bar_groups"].items():
            for g in groups:
                grp = get(g)
                if grp is None:
                    log("missing bar group " + g)
                    continue
                for rb in grp.Group:
                    if "Diameter" not in rb.PropertiesList:
                        continue
                    try:
                        bars.append(bar_record(rb, comp, g))
                    except Exception as exc:
                        log("bar %s: %s" % (rb.Name, exc))
        S["bars"] = bars
        wwr = []
        for g in cfg["wwr"]:
            grp = get(g)
            if grp is None:
                continue
            stack = list(grp.Group)
            while stack:
                o = stack.pop(0)
                if hasattr(o, "Group") and o.TypeId == "App::DocumentObjectGroup":
                    if o.Name.endswith("Paths"):
                        continue
                    stack.extend(o.Group)
                    continue
                if "Diameter" in o.PropertiesList:
                    try:
                        rec = bar_record(o, "wwr", g)
                        wwr.append(rec)
                    except Exception as exc:
                        log("wwr %s: %s" % (o.Name, exc))
        S["wwr"] = wwr
        snap["structures"][key] = S
        log("%s: %d plan, %d elev edges, %d bars, %d wwr" % (key, len(S["plan"]), len(S["elev"]), len(bars), len(wwr)))
    App.closeDocument(doc.Name)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=1, sort_keys=True)


try:
    run()
except Exception:
    with open(OUT + ".error.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
        f.write("\n".join(LOG))
    raise
