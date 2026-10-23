"""FreeCAD-side cut of the whole model for the geotechnical sections.

Run with FreeCAD 1.1 ``freecadcmd`` (never the GUI) on a *copy* of the
registered model.  Read-only: opens the copy, slices every finished component
(MSE leveling footings and piles included) with the vertical planes of
``cuts.json``, writes one JSON file and closes the document without saving.

Inputs are environment variables so the call works with ``freecadcmd``:

* ``GEOSEC_MODEL``   path of the FCStd copy to read
* ``GEOSEC_RUNTIME`` folder holding the model's ``freecad_tools`` controllers
* ``GEOSEC_CUTS``    the cut definitions (``cuts.json``)
* ``GEOSEC_OUT``     JSON file to write

Each cut plane is model X = PGL X + offset (the bridge runs along -Y, model
+X is north).  Slice wires are discretized and written as (y, z) feet of the
model; ``sections.py`` turns y into stationing and adds the terrain.
"""
import json
import os
import sys
import traceback
from collections import OrderedDict

MODEL = os.environ["GEOSEC_MODEL"]
RUNTIME = os.environ["GEOSEC_RUNTIME"]
CUTS = os.environ["GEOSEC_CUTS"]
OUT = os.environ["GEOSEC_OUT"]
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)

import FreeCAD as App  # noqa: E402

FT = 304.8
DEFLECTION = 1.0  # mm, discretization of curved slice edges
SKIP = ("Envelope", "Check", "Schedule", "Source", "JointTools", "Nominal")
BRIDGE_GROUPS = ["BridgeDecks", "BridgeBeams", "BridgeHaunches", "BridgeBearings", "BridgePedestals", "BridgeCaps",
                 "BridgePiles", "BridgePierWall", "BridgeEndBentWalls", "BridgeRailings", "PierCheekWalls"]
FINISHED_LISTS = [("MSEAssembly", "FinishedConcrete"), ("MSECopingsAndBarriers", "FinishedDetails")]
OTHER_GROUPS = ["EndBentWeatherClosure", "BackwallGeotechnicalStraps"]
ROLE_PREFIXES = [("BridgeBackwall", "backwall"), ("BridgeCheek", "cheek"), ("BridgePilePier", "pile"),
                 ("BridgePile", "pile"), ("BridgePierWall", "pier_wall"), ("BridgeCap", "cap"),
                 ("BridgePedestal", "pedestal"), ("BridgePad", "pad"), ("BridgeDeck", "deck"),
                 ("BridgeBeam", "beam"), ("BridgeHaunch", "beam"), ("PierCheek", "cheek"),
                 ("ClosureSlab", "slab"), ("ClosureCoping", "coping"), ("Coping", "coping"),
                 ("Barrier", "barrier"), ("Plinth", "barrier"), ("Wall", "mse"), ("Footing", "footing"),
                 ("GeotechnicalStrap", "strap")]
LOG = []


def r4(x):
    return round(float(x), 4)


def role_of(name):
    for prefix, role in ROLE_PREFIXES:
        if name.startswith(prefix):
            return role
    if any(w in name for w in ("Slab", "Landing", "Run", "Approach")):
        return "slab"
    return "other"


def members(obj):
    for o in obj.Group:
        if o.TypeId == "App::DocumentObjectGroup":
            for x in members(o):
                yield x
        else:
            yield o


def select(doc):
    """name -> object: what the model calls finished (as the plan DXF), plus footings."""
    get = doc.getObject
    chosen = OrderedDict()

    def take(o):
        n = o.Name
        if n in chosen or any(s in n for s in SKIP) or "Shape" not in o.PropertiesList \
                or "Diameter" in o.PropertiesList:
            return
        try:
            shp = o.Shape
        except Exception:   # noqa: BLE001
            return
        if shp is None or shp.isNull() or not (shp.Solids or shp.Faces):
            return
        chosen[n] = o

    for g in BRIDGE_GROUPS + OTHER_GROUPS:
        grp = get(g)
        if grp is None:
            LOG.append("missing group " + g)
            continue
        for o in members(grp):
            take(o)
    for holder, prop in FINISHED_LISTS:
        h = get(holder)
        if h is None or prop not in h.PropertiesList:
            LOG.append("missing list %s.%s" % (holder, prop))
            continue
        sources = {}
        if "FinalDetailMapJSON" in h.PropertiesList:
            sources = {fin: src for src, fin in json.loads(h.FinalDetailMapJSON).items()}
        for o in getattr(h, prop):
            take(o)
            if o.Name in chosen or o.Name not in sources:
                continue
            for cand in (sources[o.Name] + "BentJoint", sources[o.Name] + "Corrected", sources[o.Name]):
                src = get(cand)
                if src is not None:
                    take(src)
                    if cand in chosen:
                        LOG.append("%s has no valid shape; %s is cut in its place" % (o.Name, cand))
                        break
    return chosen


def wires_at(shape, x_mm):
    """Slice wires of a shape with the plane X = x_mm, as (y, z) feet."""
    bb = shape.BoundBox
    if not (bb.XMin - 1e-6 <= x_mm <= bb.XMax + 1e-6):
        return []
    out = []
    for w in shape.slice(App.Vector(1, 0, 0), x_mm):
        pts = w.discretize(Deflection=DEFLECTION)
        if len(pts) < 2:
            continue
        out.append({"closed": bool(w.isClosed()), "yz": [[r4(p.y / FT), r4(p.z / FT)] for p in pts]})
    return out


def run():
    cuts = json.load(open(CUTS, encoding="utf-8"))
    doc = App.openDocument(MODEL)
    get = doc.getObject
    chosen = select(doc)
    LOG.append("%d objects selected" % len(chosen))
    cap1, cap2 = get("BridgeCapEB1").Shape.BoundBox, get("BridgeCapEB2").Shape.BoundBox
    pgl_x = ((cap1.XMin + cap1.XMax) / 2 + (cap2.XMin + cap2.XMax) / 2) / 2
    pier = get("BridgeCapPier").Shape.BoundBox
    supports = {"EB1": {"ffbw_y_ft": r4(get("BridgeBackwallEB1").Shape.BoundBox.YMin / FT)},
                "PIER": {"cl_y_ft": r4((pier.YMin + pier.YMax) / 2 / FT)},
                "EB2": {"ffbw_y_ft": r4(get("BridgeBackwallEB2").Shape.BoundBox.YMax / FT)}}
    objects = {n: {"role": role_of(n), "label": o.Label, "bb_ft": [r4(v / FT) for v in (
        o.Shape.BoundBox.XMin, o.Shape.BoundBox.YMin, o.Shape.BoundBox.ZMin,
        o.Shape.BoundBox.XMax, o.Shape.BoundBox.YMax, o.Shape.BoundBox.ZMax)]} for n, o in chosen.items()}
    sections = []
    for c in cuts["cuts"]:
        x_mm = pgl_x + c["offset_ft"] * FT
        cut = []
        for n, o in chosen.items():
            ws = wires_at(o.Shape, x_mm)
            bb = o.Shape.BoundBox
            if not ws and bb.XMin + 1.0 < x_mm < bb.XMax - 1.0:
                # a plane through a model edge (the deck crown on the PGL) can
                # slice to nothing; take the plane 0.5 mm north instead
                ws = wires_at(o.Shape, x_mm + 0.5)
                LOG.append("%s: %s sliced 0.5 mm north of the plane" % (c["id"], n))
            if ws:
                cut.append({"name": n, "wires": ws})
        sections.append({"id": c["id"], "x_ft": r4(x_mm / FT), "objects": cut})
        LOG.append("%s: %d objects cut" % (c["id"], len(cut)))
    App.closeDocument(doc.Name)
    snap = {"schema": 1, "units": "ft", "pgl_x_ft": r4(pgl_x / FT), "supports": supports,
            "objects": objects, "sections": sections, "log": LOG}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=1, sort_keys=True)


try:
    run()
except Exception:
    with open(OUT + ".error.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
        f.write("\n".join(LOG))
    raise
