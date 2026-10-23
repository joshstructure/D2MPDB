"""FreeCAD-side cut of the superstructure for the typical section sheet
(``typical_section.py``).

Run with FreeCAD 1.1 ``freecadcmd`` (never the GUI) on a *copy* of the
registered model.  Read-only: opens the copy, slices the finished
superstructure components of Span 1 (deck, haunches, beams and the deck
barriers) with the vertical plane normal to the stationing at mid-span,
writes one JSON snapshot and closes the document without saving.

Inputs are environment variables so the call works with ``freecadcmd``:

* ``SUBDWG_MODEL``   path of the FCStd copy to read
* ``SUBDWG_RUNTIME`` folder holding the model's ``freecad_tools`` controllers
* ``SUBDWG_PKG``     the ``substructure_drawings`` folder (``fc_hlr`` helpers)
* ``SUBDWG_OUT``     JSON snapshot to write

The bridge runs along -Y (stationing increases toward -Y) and +X is north.
The section looks ahead station (SDM 2.8.B), so sheet right is -X and sheet
up is +Z: the wires are written as (u, z) feet with u = -x.  The cut plane
is Y = y_cut, midway between the FFBW of End Bent 1 and the pier centreline.
"""
import json
import os
import sys
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

from fc_hlr import FT, r6, model_hash, bb_ft  # noqa: E402

DEFLECTION = 0.2    # mm, discretization of curved slice edges (the drip grooves and chamfers are straight)
SKIP = ("Envelope", "Check", "Schedule", "Source", "JointTools", "Nominal")
GROUPS = ["BridgeDecks", "BridgeHaunches", "BridgeBeams", "BridgeRailings"]
ROLE_PREFIXES = [("BridgeDeck", "deck"), ("BridgeHaunch", "haunch"), ("BridgeBeam", "beam"), ("Barrier", "barrier")]
LOG = []


def log(msg):
    LOG.append(msg)


def role_of(name):
    for prefix, role in ROLE_PREFIXES:
        if name.startswith(prefix):
            return role
    return "unknown"


def members(obj):
    for o in obj.Group:
        if o.TypeId == "App::DocumentObjectGroup":
            for x in members(o):
                yield x
        else:
            yield o


def wires_at(shape, y_mm):
    """Slice wires of ``shape`` with the plane Y = y_mm, as (u, z) feet, u = -x."""
    bb = shape.BoundBox
    if not (bb.YMin - 1e-6 <= y_mm <= bb.YMax + 1e-6):
        return []
    out = []
    for w in shape.slice(App.Vector(0, 1, 0), y_mm):
        pts = w.discretize(Deflection=DEFLECTION)
        if len(pts) < 2:
            continue
        uz = [[r6(-p.x / FT), r6(p.z / FT)] for p in pts]
        # drop repeated points (a closed wire's last point repeats its first)
        clean = [uz[0]]
        for p in uz[1:]:
            if abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
                clean.append(p)
        if w.isClosed() and len(clean) > 2 and abs(clean[0][0] - clean[-1][0]) < 1e-9 \
                and abs(clean[0][1] - clean[-1][1]) < 1e-9:
            clean.pop()
        out.append({"closed": bool(w.isClosed()), "pts": clean})
    return out


def run():
    doc = App.openDocument(MODEL)
    get = doc.getObject
    chosen = OrderedDict()
    for g in GROUPS:
        grp = get(g)
        if grp is None:
            log("missing group " + g)
            continue
        for o in members(grp):
            n = o.Name
            if n in chosen or any(s in n for s in SKIP) or "Shape" not in o.PropertiesList:
                continue
            try:
                shp = o.Shape
            except Exception as exc:   # noqa: BLE001
                log("%s: no shape (%s)" % (n, exc))
                continue
            if shp is None or shp.isNull() or not shp.Solids:
                continue
            chosen[n] = o
    log("%d superstructure objects selected" % len(chosen))
    bw1 = get("BridgeBackwallEB1").Shape.BoundBox
    pier = get("BridgeCapPier").Shape.BoundBox
    cap1, cap2 = get("BridgeCapEB1").Shape.BoundBox, get("BridgeCapEB2").Shape.BoundBox
    ffbw_y = bw1.YMin
    pier_y = (pier.YMin + pier.YMax) / 2
    y_cut = (ffbw_y + pier_y) / 2            # mid-span 1 (mm)
    pgl_x = ((cap1.XMin + cap1.XMax) / 2 + (cap2.XMin + cap2.XMax) / 2) / 2
    objects = OrderedDict()
    for n, o in chosen.items():
        ws = wires_at(o.Shape, y_cut)
        if not ws:
            continue
        objects[n] = {"role": role_of(n), "label": o.Label, "bb_ft": bb_ft(o.Shape), "wires": ws}
    log("%d objects cut at Y = %.3f ft" % (len(objects), y_cut / FT))
    App.closeDocument(doc.Name)
    snap = {
        "schema": 1, "units": "ft", "model_sha256": SOURCE_SHA or model_hash(MODEL),
        "frame": {"e1": [-1, 0, 0], "e2": [0, 0, 1],
                  "note": "u = -x, z of the model, feet; looking ahead station (sheet right = -X, south)"},
        "cut": {"y_ft": r6(y_cut / FT), "ffbw_eb1_y_ft": r6(ffbw_y / FT), "pier_cl_y_ft": r6(pier_y / FT),
                "where": "mid-span 1, midway between FFBW End Bent 1 and the pier centreline"},
        "pgl_u_ft": r6(-pgl_x / FT),
        "objects": objects,
        "log": LOG,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=1, sort_keys=True)


try:
    run()
except Exception:
    with open(OUT + ".error.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
        f.write("\n".join(LOG))
    raise
