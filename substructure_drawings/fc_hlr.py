"""Hidden-line projection helpers shared by the FreeCAD-side extractors
(``freecad_extract.py`` for the bent and pier sheets, ``freecad_plan_extract.py``
for the whole-model plan).  Runs only under FreeCAD ``freecadcmd``; the
extractors put this folder on ``sys.path`` (``SUBDWG_PKG``) before importing.

All snapshot lengths are feet (model mm / 304.8).
"""
import hashlib

import FreeCAD as App
import Part
import TechDraw

FT = 304.8
V = App.Vector
DEFLECTION = 0.05  # mm, discretization of non-line/circle projected curves


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
    per, boxes = [], []
    for shp in shapes:
        res = TechDraw.projectEx(shp, V(0, 0, 1))
        es = []
        for comp in res:
            if comp is not None and not comp.isNull():
                es.extend(comp.Edges)
        pc = Part.makeCompound(es) if es else None
        per.append(pc)
        bb = pc.BoundBox if pc is not None else None
        if bb is not None:
            bb.enlarge(0.5)   # mm: only an object whose outline box holds the point can be within 0.05 mm
        boxes.append(bb)
    # candidates from the smallest outline up, so an edge shared by two
    # objects (a pile socket in a cap, a pedestal seat) goes to the smaller
    # one, which it outlines
    order = sorted(range(len(per)), key=lambda k: (boxes[k].XLength * boxes[k].YLength) if boxes[k] else 1e30)
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
            for k in order:
                pc = per[k]
                if pc is None or not boxes[k].isInside(mid):
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


def model_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bb_ft(shape):
    b = shape.BoundBox
    return [r6(v / FT) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]
