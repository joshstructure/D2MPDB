"""FreeCAD-side snapshot of the whole model for the plan DXF (``model_plan.py``).

Run with FreeCAD 1.1 ``freecadcmd`` (never the GUI) on a *copy* of the
registered model.  Read-only: opens the copy, projects every finished
component of the model looking down (hidden lines included), writes one JSON
snapshot and closes the document without saving.

Inputs are environment variables so the call works with ``freecadcmd``:

* ``SUBDWG_MODEL``   path of the FCStd copy to read
* ``SUBDWG_RUNTIME`` folder holding the model's ``freecad_tools`` controllers
* ``SUBDWG_PKG``     the ``substructure_drawings`` folder (``fc_hlr`` helpers)
* ``SUBDWG_OUT``     JSON snapshot to write

What is drawn is what the model itself calls finished:

* the bridge assembly groups (decks, beams, haunches, bearings, pedestals,
  caps, piles, pier wall, end bent backwalls and cheek walls, deck barriers)
  and the pier cheek walls group (D-059),
* ``MSEAssembly.FinishedConcrete`` (the mitred MSE wall panels and the walking
  slabs; the leveling footings are left out, they lie under the walls),
* ``MSECopingsAndBarriers.FinishedDetails`` (copings, barriers, plinths and
  returns, the corrected object where one exists),
* the end bent weather closure (rain closure slabs and closure copings) and
  the schematic geotechnical straps (D-045).

Reinforcement, WWR, envelopes, sources, checks and schedules are left out.
The view frame: sheet right = direction of stationing (global -Y, End Bent
1 at the left, End Bent 2 at the right), sheet up = global +X, looking
down; the projected coordinates are feet, u = -y and v = x of the model.
"""
import json
import math
import os
import sys
import time
import traceback
from collections import OrderedDict

MODEL = os.environ["SUBDWG_MODEL"]
RUNTIME = os.environ["SUBDWG_RUNTIME"]
OUT = os.environ["SUBDWG_OUT"]
SOURCE_SHA = os.environ.get("SUBDWG_SOURCE_SHA256", "")
for folder in (RUNTIME, os.environ.get("SUBDWG_PKG", "")):
    if folder and folder not in sys.path:
        sys.path.insert(0, folder)

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402

from fc_hlr import DEFLECTION, FT, r6, project, model_hash, bb_ft  # noqa: E402

E1, E2 = (0, -1, 0), (1, 0, 0)   # sheet right = +station (-Y), sheet up = +X, looking down (e1 x e2 = +Z)
STATION = (0, -1, 0)
# name fragments of objects that are not finished components
SKIP = ("Envelope", "Check", "Schedule", "Source", "JointTools", "Nominal")
BRIDGE_GROUPS = ["BridgeDecks", "BridgeBeams", "BridgeHaunches", "BridgeBearings", "BridgePedestals", "BridgeCaps",
                 "BridgePiles", "BridgePierWall", "BridgeEndBentWalls", "BridgeRailings",
                 "PierCheekWalls"]   # D-059: the pier cheek walls are a root group of their own
FINISHED_LISTS = [("MSEAssembly", "FinishedConcrete"), ("MSECopingsAndBarriers", "FinishedDetails")]
OTHER_GROUPS = ["EndBentWeatherClosure", "BackwallGeotechnicalStraps"]
# two faces meeting within this angle are one surface split by the model
# (seam_edges); the model's grade breaks between ramp runs and landings are
# 2.3 and 3.3 degrees, its corner and landing pieces meet within 0.6 degrees
SEAM_DEG = 1.0
# role by object name (first match), then by words in the name
ROLE_PREFIXES = [("BridgeBackwall", "backwall"), ("BridgeCheek", "cheek"), ("BridgePilePier", "pile_steel"),
                 ("BridgePile", "pile_conc"), ("BridgePierWall", "pier_wall"), ("BridgeCap", "cap"),
                 ("BridgePedestal", "pedestal"), ("BridgePad", "pad"), ("BridgeDeck", "deck"),
                 ("BridgeBeam", "beam"), ("BridgeHaunch", "haunch"), ("ClosureSlab", "closure"),
                 ("ClosureCoping", "coping"), ("Coping", "coping"), ("Barrier", "barrier"), ("Plinth", "barrier"),
                 ("Wall", "mse"), ("Footing", "footing"), ("GeotechnicalStrap", "strap")]
LOG = []


def log(msg):
    LOG.append(msg)


def pour_of(name, source):
    """The pour an object is cast in with its neighbours, or None for an
    object that stands alone.  The model builds a ramp's copings and barriers,
    its wall panels, its walking slabs and each end bent's weather closure
    from separate mitred or butted pieces that are cast (or, for the panels,
    read) as one: their butt and mitre faces are modelling joints, not joints
    of the structure, and the plan draws no line there (2026-10-23 markup,
    "remove any lines that are simply a function of modeling face joints").
    The bridge's own pieces (spans, caps, walls) meet at real joints and stay
    apart."""
    if source.startswith("MSECopingsAndBarriers"):
        if "EB1" in name:
            return "copings and barriers A"
        if "EB2" in name:
            return "copings and barriers B"
        for p in ("Coping", "Barrier"):
            if name.startswith(p) and name[len(p):len(p) + 1] in ("A", "B"):
                return "copings and barriers " + name[len(p)]
    if source.startswith("MSEAssembly"):
        if name.startswith("Wall") and name[4:5] in ("A", "B"):
            return "wall panels " + name[4]
        if name[:2] in ("A_", "B_"):
            return "walking slabs " + name[0]
    if source == "EndBentWeatherClosure":
        if name.endswith("EB1") or name.startswith("ClosureCopingA"):
            return "weather closure EB1"
        if name.endswith("EB2") or name.startswith("ClosureCopingB"):
            return "weather closure EB2"
    return None


def refined(shape):
    try:
        out = shape.removeSplitter()
        return out if out.isValid() else shape
    except Exception:   # noqa: BLE001
        return shape


def pour_shapes(chosen):
    """The shapes the hidden-line pass sees: each pour (``pour_of``) fused
    into one solid with its coplanar faces merged, every other object refined
    (its split faces merged).  Only coplanar seams go: a step, a slope change
    or an edge of the structure stays an edge.  A pour that does not fuse to a
    valid shape is drawn piece by piece (logged).  Returns [(shape, names of
    the objects in it)]."""
    pours, out = OrderedDict(), []
    for n, (role, o, source) in chosen.items():
        if role == "pgl":
            out.append((o.Shape, {n}))
            continue
        key = pour_of(n, source)
        if key is None:
            out.append((refined(o.Shape), {n}))
        else:
            pours.setdefault(key, []).append((n, o.Shape))
    for key, items in pours.items():
        shapes = [s for _n, s in items]
        try:
            fused = shapes[0].multiFuse(shapes[1:]) if len(shapes) > 1 else shapes[0]
            fused = fused.removeSplitter()
            if not fused.isValid() or fused.isNull():
                raise ValueError("invalid fused shape")
            out.append((fused, {n for n, _s in items}))
            log("pour %s: %d pieces fused (%s)" % (key, len(items), ", ".join(n for n, _s in items)))
        except Exception as exc:   # noqa: BLE001
            out.extend((refined(s), {n}) for n, s in items)
            log("pour %s: not fused (%s); drawn piece by piece" % (key, exc))
    return out


def seam_edges(shape):
    """Edges of ``shape`` between two faces that meet within SEAM_DEG: the
    faces the model happens to be split into (segment joints, mitres, a
    landing piece against a run at the same grade).  ``removeSplitter``
    leaves many of them (exactly coplanar faces it does not unify), so they
    are found here and their lines dropped from the plan.  A real edge (a
    step, a corner, a grade break of 2 degrees or more between a ramp run and
    its landing) has faces meeting at a larger angle and stays."""
    out = []
    for e in shape.Edges:
        if e.Length < 1e-3:
            continue
        faces = shape.ancestorsOfType(e, Part.Face)
        if len(faces) != 2 or faces[0].isSame(faces[1]):
            continue
        m = e.valueAt(0.5 * (e.FirstParameter + e.LastParameter))
        try:
            ns = [f.normalAt(*f.Surface.parameter(m)) for f in faces]
        except Exception:   # noqa: BLE001
            continue
        if math.degrees(ns[0].getAngle(ns[1])) < SEAM_DEG:
            out.append(e)
    return out


def seam_segments(hlr):
    """[(object names, [2D seam segments in feet, plan frame])] of the seams
    of each shape the hidden-line pass sees."""
    out = []
    for shape, names in hlr:
        segs = []
        for e in seam_edges(shape):
            pts = [(-p.y / FT, p.x / FT) for p in e.discretize(Deflection=DEFLECTION)]   # u = -y, v = x
            segs.extend(zip(pts, pts[1:]))
        if segs:
            out.append((names, segs))
    return out


def _dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L2 = ax * ax + ay * ay
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L2))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def drop_seams(edges, seams, tol=0.003):
    """The projected edges less those that lie along a seam (every point
    within ``tol`` ft, about 1 mm) of the shape their object belongs to."""
    by_name = {}
    for names, segs in seams:
        for n in names:
            by_name[n] = segs
    out, dropped = [], 0
    for r in edges:
        segs = by_name.get(r.get("obj"))
        if segs and r["t"] in ("L", "P"):
            pts = r["p"]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            near = [s for s in segs if min(s[0][0], s[1][0]) - tol <= max(xs) and max(s[0][0], s[1][0]) + tol >= min(xs)
                    and min(s[0][1], s[1][1]) - tol <= max(ys) and max(s[0][1], s[1][1]) + tol >= min(ys)]
            probe = list(pts) + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(pts, pts[1:])]
            if near and all(min(_dist(p, a, b) for a, b in near) < tol for p in probe):
                dropped += 1
                continue
        out.append(r)
    log("%d modelling seam lines dropped (faces meeting within %.1f degrees)" % (dropped, SEAM_DEG))
    return out


def role_of(name):
    for prefix, role in ROLE_PREFIXES:
        if name.startswith(prefix):
            return role
    if any(w in name for w in ("Slab", "Landing", "Run", "Approach")):
        return "slab"
    return "unknown"


def members(obj):
    """Leaf objects of a group, recursively."""
    for o in obj.Group:
        if o.TypeId == "App::DocumentObjectGroup":
            for x in members(o):
                yield x
        else:
            yield o


def run():
    t0 = time.time()
    doc = App.openDocument(MODEL)
    get = doc.getObject
    chosen = OrderedDict()   # name -> (role, object, source)
    skipped = []

    def take(o, source):
        n = o.Name
        if n in chosen:
            return
        if any(s in n for s in SKIP) or "Shape" not in o.PropertiesList or "Diameter" in o.PropertiesList:
            skipped.append(n)
            return
        try:
            shp = o.Shape
        except Exception as exc:   # noqa: BLE001
            log("%s: no shape (%s)" % (n, exc))
            return
        if shp is None or shp.isNull() or not (shp.Solids or shp.Faces):
            skipped.append(n)
            return
        role = role_of(n)
        if role == "footing":
            skipped.append(n)
            return
        chosen[n] = (role, o, source)

    for g in BRIDGE_GROUPS + OTHER_GROUPS:
        grp = get(g)
        if grp is None:
            log("missing group " + g)
            continue
        for o in members(grp):
            take(o, g)
    for holder, prop in FINISHED_LISTS:
        h = get(holder)
        if h is None or prop not in h.PropertiesList:
            log("missing list %s.%s" % (holder, prop))
            continue
        # a finished detail without a valid shape (CopingB7AtCheek in the
        # D-048 model) falls back to the source it was made from, which the
        # detail map names (FinalDetailMapJSON: source -> finished)
        sources = {}
        if "FinalDetailMapJSON" in h.PropertiesList:
            try:
                sources = {fin: src for src, fin in json.loads(h.FinalDetailMapJSON).items()}
            except ValueError:
                sources = {}
        for o in getattr(h, prop):
            take(o, holder + "." + prop)
            if o.Name in chosen or o.Name not in sources or sources[o.Name] == o.Name:
                continue
            # the nearest stand-in: the source cut at the end bent joint, the
            # corrected source, else the nominal source itself
            for cand in (sources[o.Name] + "BentJoint", sources[o.Name] + "Corrected", sources[o.Name]):
                src = get(cand)
                if src is None:
                    continue
                take(src, "%s.%s (stands in for %s, which has no valid shape)" % (holder, prop, o.Name))
                if cand in chosen:
                    log("%s has no valid shape; %s is drawn in its place" % (o.Name, cand))
                    break
    pgl = get("BridgePGL")
    if pgl is not None and "Shape" in pgl.PropertiesList and not pgl.Shape.isNull() and pgl.Shape.Edges:
        chosen["BridgePGL"] = ("pgl", pgl, "BridgeAssembly")
    log("%d objects chosen, %d skipped" % (len(chosen), len(skipped)))

    objects = {}
    by_role = OrderedDict()
    for n, (role, o, source) in chosen.items():
        objects[n] = {"role": role, "label": o.Label, "visible": bool(o.Visibility), "source": source,
                      "bb_ft": bb_ft(o.Shape)}
        by_role.setdefault(role, []).append((n, o.Shape))
    # supports: the lines the plan is stationed from (feet, global)
    supports = {}
    bw1, bw2, pier = get("BridgeBackwallEB1").Shape.BoundBox, get("BridgeBackwallEB2").Shape.BoundBox, \
        get("BridgeCapPier").Shape.BoundBox
    cap1, cap2 = get("BridgeCapEB1").Shape.BoundBox, get("BridgeCapEB2").Shape.BoundBox
    supports["EB1"] = {"title": "END BENT 1", "ffbw_y_ft": r6(bw1.YMin / FT), "cap_bb_ft": bb_ft(get("BridgeCapEB1").Shape)}
    supports["PIER"] = {"title": "PIER", "cl_y_ft": r6((pier.YMin + pier.YMax) / 2 / FT),
                        "cap_bb_ft": bb_ft(get("BridgeCapPier").Shape)}
    supports["EB2"] = {"title": "END BENT 2", "ffbw_y_ft": r6(bw2.YMax / FT), "cap_bb_ft": bb_ft(get("BridgeCapEB2").Shape)}
    pgl_x = ((cap1.XMin + cap1.XMax) / 2 + (cap2.XMin + cap2.XMax) / 2) / 2
    t1 = time.time()
    hlr = pour_shapes(chosen)
    seams = seam_segments(hlr)
    t1b = time.time()
    log("pours and seams %.0f s" % (t1b - t1))
    edges = drop_seams(project(by_role, (0.0, 0.0, 0.0), E1, E2, hlr_shapes=[s for s, _n in hlr]), seams)
    t2 = time.time()
    log("projection %.0f s (%d edges)" % (t2 - t1, len(edges)))
    snap = {
        # schema 2: the hidden-line pass runs over the pours (pour_shapes), seams merged
        "schema": 2, "units": "ft", "model_sha256": SOURCE_SHA or model_hash(MODEL),
        "station_direction": list(STATION),
        "frame": {"origin_ft": [0.0, 0.0, 0.0], "e1": list(E1), "e2": list(E2),
                  "note": "u = -y (increasing station), v = x of the model, feet; looking down"},
        "pgl_x_ft": r6(pgl_x / FT),
        "supports": supports,
        "objects": objects,
        "skipped": sorted(set(skipped)),
        "roles": {r: [n for n, _ in items] for r, items in by_role.items()},
        "edges": edges,
        "log": LOG,
    }
    App.closeDocument(doc.Name)
    log("total %.0f s" % (time.time() - t0))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=1, sort_keys=True)


try:
    run()
except Exception:
    with open(OUT + ".error.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
        f.write("\n".join(LOG))
    raise
