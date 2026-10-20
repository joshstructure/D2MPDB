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

from fc_hlr import FT, r6, project, model_hash, bb_ft  # noqa: E402

E1, E2 = (0, -1, 0), (1, 0, 0)   # sheet right = +station (-Y), sheet up = +X, looking down (e1 x e2 = +Z)
STATION = (0, -1, 0)
# name fragments of objects that are not finished components
SKIP = ("Envelope", "Check", "Schedule", "Source", "JointTools", "Nominal")
BRIDGE_GROUPS = ["BridgeDecks", "BridgeBeams", "BridgeHaunches", "BridgeBearings", "BridgePedestals", "BridgeCaps",
                 "BridgePiles", "BridgePierWall", "BridgeEndBentWalls", "BridgeRailings",
                 "PierCheekWalls"]   # D-059: the pier cheek walls are a root group of their own
FINISHED_LISTS = [("MSEAssembly", "FinishedConcrete"), ("MSECopingsAndBarriers", "FinishedDetails")]
OTHER_GROUPS = ["EndBentWeatherClosure", "BackwallGeotechnicalStraps"]
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
    edges = project(by_role, (0.0, 0.0, 0.0), E1, E2)
    t2 = time.time()
    log("projection %.0f s (%d edges)" % (t2 - t1, len(edges)))
    snap = {
        "schema": 1, "units": "ft", "model_sha256": SOURCE_SHA or model_hash(MODEL),
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
