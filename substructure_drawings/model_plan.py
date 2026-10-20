"""Plan of the whole model (bridge and ramps) as one DXF from the plan snapshot.

Usage: see ``scripts/build_model_plan_dxf.py``.  Model space holds the plan
at full size (international feet) in the plan frame of the snapshot: u
(sheet right) is the direction of stationing, End Bent 1 at the left and End
Bent 2 at the right; v (sheet up) is the model's +X.  One 11 x 17 layout
("P-1 GENERAL PLAN") shows it at 1" = 40' with the FDOT border.  Symbology,
levels and lettering follow the substructure sheets (STYLE_GUIDE.md, F).
"""
import hashlib
import json
import math
from collections import OrderedDict
from pathlib import Path

from . import build, cad, fdot
from .sheets import DRAW, Sheet
from .support import STATION_FFBW_EB1
from .views import _covered

GENERATOR_VERSION = "1.0.0"
DXF_NAME = "B4_Model_Plan.dxf"
MANIFEST_NAME = "model_plan_manifest.json"
SHEET_SCALE = "1=40"
# role -> (level of visible edges, level of hidden edges); a role whose two
# levels are one has no hidden twin in the level table and takes the hidden
# linetype as an override (build.LINETYPE_OVERRIDES)
ROLE_LEVELS = {
    "deck": ("SupstrConc", "SupstrConc_h"),
    "beam": ("BeamConc", "BeamConc_h"),
    "haunch": ("BeamConc", "BeamConc_h"),
    "barrier": ("TrafBarrierConc", "SupstrConc3_h"),      # no hidden twin of 2140: superstructure concrete misc hidden
    "coping": ("WallConc", "WallConc_h"),
    "mse": ("WallMSEPanel", "WallMSEPanel_h"),
    "closure": ("SubStrConc2", "SubStrConc2_h"),
    "slab": ("AppSlabConc", "AppSlabConc_h"),
    "cap": ("SubStrConc", "SubStrConc_h"),
    "backwall": ("SubStrConc", "SubStrConc_h"),
    "pier_wall": ("SubStrConc", "SubStrConc_h"),
    "cheek": ("SubStrConc2", "SubStrConc2_h"),
    "pedestal": ("SubStrConc2", "SubStrConc2_h"),
    "pad": ("BearingPadMisc", "BearingPadMisc"),
    "pile_conc": ("PileConc", "PileConc_h"),
    "pile_steel": ("PileSteel", "PileSteel_h"),
    "strap": ("Rebar2", "Rebar_h"),
    "pgl": ("BaseLineSurveyPGL", "BaseLineSurveyPGL"),
    "unknown": ("SubStrConc", "SubStrConc_h"),
}


def layer_for(rec):
    vis, hid = ROLE_LEVELS.get(rec["role"], ROLE_LEVELS["unknown"])
    if rec["vis"] or rec["role"] == "pgl":
        return vis, None
    if hid == vis:
        return vis, fdot.HIDDEN_LINETYPE
    return hid, None


def _key(rec):
    pts = tuple((round(p[0], 4), round(p[1], 4)) for p in rec["p"])
    if rec["t"] in ("L", "P") and pts and pts[0] > pts[-1]:
        pts = pts[::-1]
    return (rec["t"], pts, rec.get("r"))


def dedupe(edges):
    """One copy of coincident edges (a visible copy wins over a hidden one)."""
    best = OrderedDict()
    for r in edges:
        k = _key(r)
        if k not in best or (r["vis"] and not best[k]["vis"]):
            best[k] = r
    return list(best.values())


def chain_lines(recs, tol=1e-3):
    """Chain line records that share endpoints into point lists (polylines),
    in the order they connect; each record is used once."""
    segs = [(tuple(r["p"][0]), tuple(r["p"][1])) for r in recs]
    used = [False] * len(segs)
    out = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        chain = [segs[i][0], segs[i][1]]
        grew = True
        while grew:
            grew = False
            for j, (a, b) in enumerate(segs):
                if used[j]:
                    continue
                if math.dist(chain[-1], a) < tol:
                    chain.append(b)
                elif math.dist(chain[-1], b) < tol:
                    chain.append(a)
                elif math.dist(chain[0], b) < tol:
                    chain.insert(0, a)
                elif math.dist(chain[0], a) < tol:
                    chain.insert(0, b)
                else:
                    continue
                used[j] = True
                grew = True
        out.append(chain)
    return out


def drop_coincident_hidden_fast(edges, tol=0.004, cell=4.0):
    """``views.drop_coincident_hidden`` (D1) with a grid index over the
    visible segments, for the thousands of edges of the whole plan."""
    grid = {}

    def cells(a, b):
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        for i in range(int((x0 - tol) // cell), int((x1 + tol) // cell) + 1):
            for j in range(int((y0 - tol) // cell), int((y1 + tol) // cell) + 1):
                yield (i, j)

    for r in edges:
        if r["vis"] and r["t"] in ("L", "P"):
            pts = [tuple(p) for p in r["p"]]
            for a, b in zip(pts, pts[1:]):
                for c in cells(a, b):
                    grid.setdefault(c, []).append((a, b))
    out = []
    for r in edges:
        if not r["vis"] and r["t"] in ("L", "P"):
            pts = [tuple(p) for p in r["p"]]
            covered = True
            for a, b in zip(pts, pts[1:]):
                cand = {s for c in cells(a, b) for s in grid.get(c, [])}
                if not _covered(a, b, list(cand), tol):
                    covered = False
                    break
            if covered:
                continue
        out.append(r)
    return out


class PlanComposer:
    def __init__(self, snap, info=build.INFO):
        self.snap = snap
        self.info = dict(info)
        self.info["stamp"] = ["%s  (%s %s)" % (DXF_NAME, "substructure_drawings.model_plan", GENERATOR_VERSION),
                              "FREECAD MODEL SHA-256 %s" % snap["model_sha256"][:16].upper()]
        self.doc = cad.new_document()
        self.warnings = []
        self.overlaps = []

    # plan frame: u = -y (station), v = x
    @staticmethod
    def u(y):
        return -y

    def build(self):
        snap = self.snap
        sh = Sheet(self.doc, 0, "P-1", "GENERAL PLAN", self.info)
        zone = sh.zone(DRAW, SHEET_SCALE)
        v = cad.View(self.doc, zone, "MODEL PLAN")
        th, k = v.th, v.sf / 12.0   # k: one paper inch in feet
        edges = drop_coincident_hidden_fast(dedupe(snap["edges"]))
        # the model's PGL comes as a chain of short line edges; drawn as
        # single lines each would restart the dash pattern (D3): chain them
        # into polylines first
        # (the model's PGL object also holds short transverse datum lines at
        # the supports and bearings; the plan draws its own FFBW and pier
        # centerlines, so only the pieces running along the bridge are kept)
        pgl = [r for r in edges if r["role"] == "pgl" and r["t"] in ("L", "P")
               and abs(r["p"][-1][0] - r["p"][0][0]) > abs(r["p"][-1][1] - r["p"][0][1])]
        rest = [r for r in edges if r["role"] != "pgl"]
        lines = [{"p": [r["p"][i], r["p"][i + 1]]} for r in pgl for i in range(len(r["p"]) - 1)]
        for chain in chain_lines(lines):
            v.pl(chain, layer_for(pgl[0])[0])
        for rec in rest:
            layer, lt = layer_for(rec)
            v.record(rec, layer, lt)
        ex = extents(edges)
        sup = snap["supports"]
        # the lines the plan is stationed from: FFBW of the end bents, CL of
        # the pier, across the cap and 10 ft beyond each end, each with its
        # station below the bridge (open space, A1)
        ffbw1 = sup["EB1"]["ffbw_y_ft"]
        labels = []
        # (the end bent labels read inward, toward the pier: the ramps' walls
        # run past the end bents on their outer sides, A1)
        for key, attach, dx in (("EB1", 1, 0.05), ("PIER", 2, 0.0), ("EB2", 3, -0.05)):
            s = sup[key]
            y = s.get("ffbw_y_ft", s.get("cl_y_ft"))
            cb = s["cap_bb_ft"]
            u = self.u(y)
            # 20 ft beyond the cap each way: two dash patterns at 1" = 40' (D3)
            v0, v1 = cb[0] - 20.0, cb[3] + 20.0
            v.line((u, v0), (u, v1), "CL_Major")
            sta = fdot.station(STATION_FFBW_EB1 + (ffbw1 - y))
            name = ("FFBW " + s["title"]) if key != "PIER" else (cad.CL_CHAR + " " + s["title"])
            v.mtext((u + dx * k, v0 - 0.12 * k), "%s\\PSTA. %s" % (name, sta), attach=attach)
            labels.append({"support": key, "station": sta, "u_ft": round(u, 4)})
        # the PGL through the bridge (the model's PGL object when it has a
        # shape, else the caps' centre line), labelled above the deck
        if "pgl" not in snap["roles"]:
            x = snap["pgl_x_ft"]
            u0, u1 = self.u(sup["EB1"]["ffbw_y_ft"]) - 12.0, self.u(sup["EB2"]["ffbw_y_ft"]) + 12.0
            v.line((u0, x), (u1, x), "BaseLineSurveyPGL")
        x = snap["pgl_x_ft"]
        um = (self.u(sup["EB1"]["ffbw_y_ft"]) + self.u(sup["PIER"]["cl_y_ft"])) / 2
        deck_top = max(b[3] for n, b in ((n, o["bb_ft"]) for n, o in snap["objects"].items() if o["role"] == "deck")) \
            if any(o["role"] == "deck" for o in snap["objects"].values()) else x + 10.0
        v.leader([(um, x), (um + 0.1 * k, deck_top + 0.2 * k), (um + 0.22 * k, deck_top + 0.2 * k)], "PGL", "left")
        # direction of stationing, title and ramp names in the open space
        # below the bridge (the ramps run away from it on the other side),
        # under the station labels (A2)
        cap_lo = min(sup[k2]["cap_bb_ft"][0] for k2 in sup)
        y_lab = cap_lo - 20.0 - 0.12 * k - (1 + fdot.LINE_PITCH) * th   # bottom of the two-line labels
        v.stationing_arrow((um - 0.6 * k, y_lab - 0.45 * k), (1.0, 0.0))
        v.title((um + 0.6 * k, y_lab - 1.1 * k), "PLAN", "(SCALE %s)" % fdot.scale_label(SHEET_SCALE),
                subject_cx=um + 0.6 * k)
        for ramp, letter in (("A", "A"), ("B", "B")):
            walls = [o["bb_ft"] for n, o in snap["objects"].items() if o["role"] == "mse" and n.startswith("Wall" + letter)]
            if not walls:
                continue
            # the ramp name along its longest run, between that run's walls
            run = max(walls, key=lambda b: (b[3] - b[0]) + (b[4] - b[1]))
            if (run[3] - run[0]) >= (run[4] - run[1]):   # a wall along x: a run across the sheet (v)
                uu = self.u((run[1] + run[4]) / 2)
                side = 1.0 if uu < self.u(ffbw1) else -1.0   # toward the bridge side of the wall
                v.text((uu + side * 6.5, (run[0] + run[3]) / 2), "RAMP " + letter, None, "MIDDLE_CENTER", 90.0)
            else:
                xm = (run[0] + run[3]) / 2
                v.text((self.u((run[1] + run[4]) / 2), xm - 6.5), "RAMP " + letter, None, "MIDDLE_CENTER")
        # sheet: the plan at the left of the window, the notes at the right
        pw = (v.local_bbox[2] - v.local_bbox[0]) / v.sf * 12.0
        v.place(v.local_bbox[0], v.local_bbox[3], DRAW[0] + 0.25, DRAW[3] - 0.15)
        comp = build.Composer.__new__(build.Composer)
        comp.warnings, comp.__dict__["placed"] = self.warnings, {}
        comp.check(sh, v)
        self.overlaps = comp.__dict__.get("annotation_overlaps", [])
        xn = DRAW[0] + 0.25 + pw + 0.4
        notes = [
            "PLAN OF THE REGISTERED FREECAD MODEL (SHA-256 %s), LOOKING DOWN, WITH STATIONING INCREASING LEFT TO "
            "RIGHT; MODEL SPACE IS AT FULL SIZE IN FEET." % snap["model_sha256"][:16].upper(),
            "THE FINISHED COMPONENTS OF THE MODEL ARE DRAWN: DECKS, BEAMS, HAUNCHES, BEARINGS, PEDESTALS, CAPS, "
            "PILES, PIER WALL, END BENT WALLS, WEATHER CLOSURES, MSE WALL PANELS, COPINGS, BARRIERS, RETURNS, "
            "WALKING SLABS AND THE SCHEMATIC SOIL REINFORCING STRAPS. HIDDEN LINES SHOW WHAT LIES UNDER THE DECK "
            "AND THE SLABS.",
            "NOT SHOWN: REINFORCEMENT, WWR, MSE WALL LEVELING FOOTINGS, FILL ENVELOPES AND MODEL SOURCES, CHECKS "
            "AND SCHEDULES.",
            "STATIONS ARE FROM FFBW END BENT 1 = %s (SELECTED GEOMETRY CAD TABLES, D-041); THE PIER WALL IS "
            "PROVISIONAL." % fdot.station(STATION_FFBW_EB1),
            "THIS PLAN IS GENERATED FOR REVIEW OF THE MODEL AND IS NOT A CONTRACT DRAWING.",
        ]
        wn = DRAW[2] - 0.1 - xn
        bottom = sh.notes_bottom(DRAW[3] - 0.2, notes, wn)
        sh.notes(xn, DRAW[3] - 0.2, "NOTES:", notes, width_in=wn)
        comp.check_block(sh, "notes", (xn, bottom, xn + wn, DRAW[3] - 0.2))
        sh.border()
        sh.group_zones()   # E9: the plan in a labelled model-space group (one zone)
        sh.add_viewports()
        if "Layout1" in self.doc.layouts:   # ezdxf's default layout: the sheet is the only layout
            self.doc.layouts.delete("Layout1")
        build.dimension_blocks_by_level(self.doc)
        self.sheet, self.view, self.labels, self.extents = sh, v, labels, ex
        return self.doc


def extents(edges):
    xs, ys = [], []
    for r in edges:
        for p in r["p"]:
            xs.append(p[0])
            ys.append(p[1])
    return (min(xs), min(ys), max(xs), max(ys))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_outputs(snapshot_path, out_dir):
    import ezdxf
    keep = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        return _write_outputs(snapshot_path, out_dir)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = keep


def _write_outputs(snapshot_path, out_dir):
    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    comp = PlanComposer(snap)
    doc = comp.build()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dxf_path = out_dir / DXF_NAME
    doc.classes.add_required_classes(doc.dxfversion)
    doc.classes.classes = OrderedDict(sorted(doc.classes.classes.items()))
    doc.saveas(dxf_path)
    flat_path = out_dir / build.flat_name(DXF_NAME)
    n_flat = build.write_flat(dxf_path, flat_path)
    layers = {}
    for e in doc.modelspace():
        layers[e.dxf.layer] = layers.get(e.dxf.layer, 0) + 1
    manifest = {
        "generator": "substructure_drawings.model_plan", "version": GENERATOR_VERSION,
        "dxf": DXF_NAME, "dxf_sha256": sha256(dxf_path),
        "dxf_flat": build.flat_name(DXF_NAME), "dxf_flat_sha256": sha256(flat_path), "dimensions_flattened": n_flat,
        "snapshot_sha256": sha256(snapshot_path), "model_sha256": snap["model_sha256"],
        "units": "US survey feet ($INSUNITS=21; the model's feet, for the DGN import); model space 1:1 in the plan frame",
        "frame": snap["frame"],
        "plan_extents_ft": {"u": [round(comp.extents[0], 3), round(comp.extents[2], 3)],
                            "v": [round(comp.extents[1], 3), round(comp.extents[3], 3)]},
        "sheet": {"number": "P-1", "title": "GENERAL PLAN", "layout": comp.sheet.layout.name,
                  "scale": fdot.scale_label(SHEET_SCALE)},
        "stations": comp.labels,
        "objects_by_role": snap["roles"],
        "skipped_objects": snap["skipped"],
        "levels_used": dict(sorted(layers.items())),
        "level_source": fdot.LEVEL_TABLE,
        "cadd_manual": fdot.CADD_MANUAL,
        "symbology_audit": build.symbology_audit(doc),
        "layout_warnings": comp.warnings,
        "annotation_overlaps": comp.overlaps,
        "extraction_log": snap.get("log", []),
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return dxf_path, manifest
