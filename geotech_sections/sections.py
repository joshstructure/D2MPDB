"""Geotechnical sections of the B4 model: snapshot, DXF per section, hover report.

Two stages, as the substructure drawings:

* ``make_snapshot`` (extract time) turns the FreeCAD slice of
  ``freecad_section_extract.py`` into stationing, sets each section's window
  (pier centerline match line to ``clearance_ft`` beyond the outermost project
  element on the exterior side) and cuts the supplied terrain TINs along the
  same planes.  The TIN caches live with the CAD tooling (CAD_AI), so this
  stage runs only where they are; its result is the committed snapshot.
* ``write_outputs`` (no FreeCAD, no terrain caches) draws one DXF per section
  (1:1, US survey feet, x = station, y = elevation) and one self-contained
  HTML report whose sections show elevations under the cursor.

Coordinates: model frame feet (model mm / 304.8); the bridge runs along -Y and
+X is north.  Station = STA_FFBW_EB1 + (y_FFBW_EB1 - y).  Terrain triangles
are the supplied LandXML connectivity, placed by the verified rigid
registration of the CAD tooling (terrain-20261003/placement.json); no
re-triangulation or smoothing.
"""
import hashlib
import html
import json
import math
from pathlib import Path

import numpy as np

STA_EB1 = 1593.22          # FFBW End Bent 1 (plan and decisions)
US_FOOT_M = 1200.0 / 3937.0
FT_M = 0.3048
GENERATOR = "geotech_sections 1.0.0"
HTML_NAME = "B4_Geotech_Sections.html"
MANIFEST_NAME = "manifest.json"

ROLE_NAMES = {"mse": "MSE wall panel", "footing": "MSE leveling pad", "slab": "Ramp / landing slab",
              "coping": "Coping", "barrier": "Barrier", "cap": "Bent cap", "backwall": "Backwall",
              "cheek": "Cheek wall", "pier_wall": "Pier wall", "pedestal": "Pedestal", "pad": "Bearing pad",
              "deck": "Deck", "beam": "Beam", "pile": "Pile", "strap": "Backwall strap (schematic)",
              "other": "Other"}
# DXF layer, ACI color, HTML color
ROLE_STYLE = {"mse": ("CUT_MSE_WALL", 8, "#7d8590"), "footing": ("CUT_MSE_PAD", 30, "#c27a2c"),
              "slab": ("CUT_SLAB", 9, "#a9b0ba"), "coping": ("CUT_COPING", 252, "#9097a1"),
              "barrier": ("CUT_BARRIER", 251, "#b0b6bf"), "cap": ("CUT_SUBSTRUCTURE", 5, "#4f74b3"),
              "backwall": ("CUT_SUBSTRUCTURE", 5, "#4f74b3"), "cheek": ("CUT_SUBSTRUCTURE", 5, "#4f74b3"),
              "pier_wall": ("CUT_SUBSTRUCTURE", 5, "#4f74b3"), "pedestal": ("CUT_SUBSTRUCTURE", 5, "#4f74b3"),
              "pad": ("CUT_SUBSTRUCTURE", 5, "#4f74b3"), "deck": ("CUT_SUPERSTRUCTURE", 4, "#3f9aa3"),
              "beam": ("CUT_SUPERSTRUCTURE", 4, "#3f9aa3"), "pile": ("CUT_PILE", 1, "#b5524c"),
              "strap": ("CUT_STRAP", 6, "#a04fa8"), "other": ("CUT_OTHER", 7, "#888888")}
EG_STYLE = ("EXISTING_GROUND", 3, "#4d7f2a")
POND_STYLE = ("POND_14D_PROPOSED", 150, "#2f78c4")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def station_text(sta):
    sta = round(sta, 2)
    return "%d+%05.2f" % (int(sta // 100), sta - 100 * int(sta // 100))


def r3(x):
    return round(float(x), 3)


# ------------------------------------------------------------------ geometry
def clip_polygon(pts, lo, hi):
    """Sutherland-Hodgman clip of a closed polygon to lo <= x <= hi."""
    def half(poly, keep, edge):
        out = []
        for i, p in enumerate(poly):
            q = poly[i - 1]
            pin, qin = keep(p[0]), keep(q[0])
            if pin != qin:
                t = (edge - q[0]) / (p[0] - q[0])
                out.append([edge, q[1] + t * (p[1] - q[1])])
            if pin:
                out.append(p)
        return out
    poly = [list(p) for p in pts]
    if len(poly) > 1 and poly[0] == poly[-1]:
        poly = poly[:-1]
    poly = half(poly, lambda x: x >= lo, lo)
    if poly:
        poly = half(poly, lambda x: x <= hi, hi)
    return poly if len(poly) >= 3 else []


def clip_polyline(pts, lo, hi):
    """Pieces of an open polyline inside lo <= x <= hi."""
    pieces, cur = [], []
    for a, b in zip(pts, pts[1:]):
        (xa, za), (xb, zb) = a, b
        if xa == xb:
            seg = [a, b] if lo <= xa <= hi else None
        else:
            ta, tb = sorted(((lo - xa) / (xb - xa), (hi - xa) / (xb - xa)))
            t0, t1 = max(0.0, ta), min(1.0, tb)
            seg = None if t0 > t1 else [[xa + t0 * (xb - xa), za + t0 * (zb - za)],
                                        [xa + t1 * (xb - xa), za + t1 * (zb - za)]]
        if seg is None:
            if len(cur) > 1:
                pieces.append(cur)
            cur = []
            continue
        if not cur or cur[-1] != seg[0]:
            if len(cur) > 1:
                pieces.append(cur)
            cur = [seg[0]]
        cur.append(seg[1])
    if len(cur) > 1:
        pieces.append(cur)
    return pieces


def tin_profile(tri, x0, ylo, yhi, gap=0.01):
    """Profile of a TIN (triangles n x 3 x 3, feet) on the plane x = x0.

    Exact plane/triangle intersection of the supplied triangles; pieces break
    where the TIN has no triangle (a coverage gap).  Returns pieces of (y, z)
    with y increasing.
    """
    xs = tri[:, :, 0]
    keep = (xs.min(1) <= x0) & (xs.max(1) >= x0) & (tri[:, :, 1].max(1) >= ylo) & (tri[:, :, 1].min(1) <= yhi)
    segs = []
    for t in tri[keep]:
        pts = []
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            da, db = a[0] - x0, b[0] - x0
            if da == 0:
                pts.append((a[1], a[2]))
            if da * db < 0:
                s = da / (da - db)
                pts.append((a[1] + s * (b[1] - a[1]), a[2] + s * (b[2] - a[2])))
        if len(pts) < 2:
            continue
        pts.sort()
        (y1, z1), (y2, z2) = pts[0], pts[-1]
        if y2 - y1 < 1e-6:
            continue
        segs.append((y1, z1, y2, z2))
    segs.sort()
    pieces = []
    for y1, z1, y2, z2 in segs:
        if pieces and y1 <= pieces[-1][-1][0] + gap:
            cur = pieces[-1]
            if y2 <= cur[-1][0] + 1e-6:
                continue   # overlapping duplicate coverage
            if y1 < cur[-1][0]:   # partial overlap: continue from the current end
                z1 = z1 + (z2 - z1) * (cur[-1][0] - y1) / (y2 - y1)
                y1 = cur[-1][0]
            if abs(y1 - cur[-1][0]) > 1e-6 or abs(z1 - cur[-1][1]) > 1e-6:
                cur.append([y1, z1])
            cur.append([y2, z2])
        else:
            pieces.append([[y1, z1], [y2, z2]])
    out = []
    for p in pieces:
        for q in clip_polyline(p, ylo, yhi):
            out.append(q)
    return out


# ------------------------------------------------------------------ snapshot
def make_snapshot(raw, cuts, model_sha256, terrain):
    """terrain: dict with eg_cache, placement, pond_cache, eg_landxml, pond_landxml paths."""
    ffbw = raw["supports"]["EB1"]["ffbw_y_ft"]
    sta = lambda y: STA_EB1 + (ffbw - y)   # noqa: E731
    sta_pier = sta(raw["supports"]["PIER"]["cl_y_ft"])
    reg = json.loads(Path(terrain["placement"]).read_text(encoding="utf-8"))
    R, T = np.array(reg["rotation"]), np.array(reg["translation_m"])
    eg = np.load(terrain["eg_cache"])
    egp = (eg["points"] * US_FOOT_M - T) @ R / FT_M          # model feet
    # broad phase: a corridor around all cut planes (no re-triangulation)
    xs = [s["x_ft"] for s in raw["sections"]]
    f = eg["faces"]
    near = np.flatnonzero((np.abs(egp[:, 0] - np.mean(xs)) < 400) & (np.abs(egp[:, 1] + 100) < 1200))
    mask = np.zeros(len(egp), bool)
    mask[near] = True
    egtri = egp[f[mask[f].any(1)]]
    pond = np.load(terrain["pond_cache"])
    pondtri = pond["points"][pond["faces"]] / FT_M
    objects = raw["objects"]
    out = []
    for c, s in zip(cuts["cuts"], raw["sections"]):
        assert c["id"] == s["id"]
        west = c["exterior"] == "west"
        loops = []
        for o in s["objects"]:
            for w in o["wires"]:
                loops.append((o["name"], w["closed"], [[sta(y), z] for y, z in w["yz"]]))
        side = [p[0] for _, _, pts in loops for p in pts if (p[0] < sta_pier if west else p[0] > sta_pier)]
        pond_full = tin_profile(pondtri, s["x_ft"], -2000, 2000)
        pond_sta = [sta(y) for piece in pond_full for y, _ in piece]
        pond_side = [v for v in pond_sta if (v < sta_pier if west else v > sta_pier)]
        step = cuts["round_ends_to_ft"]
        if west:
            outer = min(side + pond_side)
            lo, hi = math.floor((outer - cuts["clearance_ft"]) / step) * step, sta_pier
        else:
            outer = max(side + pond_side)
            lo, hi = sta_pier, math.ceil((outer + cuts["clearance_ft"]) / step) * step
        # sections
        cut_objs = {}
        for name, closed, pts in loops:
            pieces = [clip_polygon(pts, lo, hi)] if closed else clip_polyline(pts, lo, hi)
            for p in pieces:
                if p:
                    cut_objs.setdefault(name, []).append({"closed": closed, "pts": [[r3(a), r3(b)] for a, b in p]})
        objs = [{"name": n, "role": objects[n]["role"], "label": objects[n]["label"], "loops": ls}
                for n, ls in sorted(cut_objs.items())]
        # piles beside the plane, projected (all piles of a bent share a station)
        projected = []
        for n, o in sorted(objects.items()):
            if o["role"] != "pile" or n in cut_objs:
                continue
            x0, y0, z0, x1, y1, z1 = o["bb_ft"]
            a, b = sorted((sta(y0), sta(y1)))
            if abs((x0 + x1) / 2 - s["x_ft"]) <= cuts["projected_pile_band_ft"] and b > lo and a < hi:
                projected.append({"name": n, "label": o["label"], "sta": [r3(max(a, lo)), r3(min(b, hi))],
                                  "z": [r3(z0), r3(z1)], "offset_ft": r3((x0 + x1) / 2 - s["x_ft"])})
        # terrain: y window of the section (station decreases with y)
        ylo, yhi = ffbw - (hi - STA_EB1), ffbw - (lo - STA_EB1)
        surf = {}
        for key, tri in (("EG", egtri), ("POND", pondtri)):
            pieces = tin_profile(tri, s["x_ft"], ylo, yhi)
            surf[key] = [[[r3(sta(y)), r3(z)] for y, z in reversed(p)] for p in reversed(pieces)]
        covered = sum(p[-1][0] - p[0][0] for p in surf["EG"])
        out.append({"id": c["id"], "title": c["title"], "offset_ft": c["offset_ft"], "x_ft": s["x_ft"],
                    "exterior": c["exterior"], "window": [r3(lo), r3(hi)],
                    "outermost_element_sta": r3(outer),
                    "clearance_ft": r3((outer - lo) if west else (hi - outer)),
                    "objects": objs, "projected_piles": projected, "terrain": surf,
                    "eg_coverage": r3(covered / (hi - lo))})
    sources = {k: {"path": str(v), "sha256": sha(v)} for k, v in sorted(terrain.items())}
    return {"schema": 1, "units": "ft (model feet; elevations as the model and surveys)",
            "model_sha256": model_sha256, "generator": GENERATOR, "terrain_sources": sources,
            "placement": {k: reg[k] for k in ("yaw_degrees", "translation_m", "max_vertex_error_m")},
            "pgl_x_ft": raw["pgl_x_ft"], "stations": {"EB1": STA_EB1, "PIER": r3(sta_pier),
                                                     "EB2": r3(sta(raw["supports"]["EB2"]["ffbw_y_ft"]))},
            "cuts_note": cuts["note"], "sections": out, "extract_log": raw["log"]}


# ------------------------------------------------------------------ queries
def extents(sec):
    zs = [p[1] for o in sec["objects"] for lp in o["loops"] for p in lp["pts"]]
    zs += [p[1] for k in sec["terrain"] for piece in sec["terrain"][k] for p in piece]
    zs += [z for pp in sec["projected_piles"] for z in pp["z"]]
    return math.floor((min(zs) - 3) / 5) * 5, math.ceil((max(zs) + 3) / 5) * 5


def object_summary(o):
    pts = [p for lp in o["loops"] for p in lp["pts"]]
    xs, zs = [p[0] for p in pts], [p[1] for p in pts]
    return {"name": o["name"], "role": o["role"], "sta": [min(xs), max(xs)], "top": max(zs), "bottom": min(zs)}


def survey_limits(sec):
    """Stations where the existing-ground survey ends inside the section window."""
    lo, hi = sec["window"]
    eg = sec["terrain"]["EG"]
    starts = [p[0] for p in eg]
    finishes = [p[-1] for p in eg]
    joined = lambda s: (any(abs(a[0] - s) < 0.01 for a in starts)   # noqa: E731
                        and any(abs(b[0] - s) < 0.01 for b in finishes))
    return [list(p) for p in sorted(map(tuple, starts + finishes))
            if lo + 0.5 < p[0] < hi - 0.5 and not joined(p[0])]


def element_table(sec):
    rows = [object_summary(o) for o in sec["objects"]]
    for pp in sec["projected_piles"]:
        rows.append({"name": pp["name"] + " (projected %+.1f ft)" % pp["offset_ft"], "role": "pile",
                     "sta": pp["sta"], "top": pp["z"][1], "bottom": pp["z"][0]})
    rows.sort(key=lambda r: (r["sta"][0], r["name"]))
    return rows


# ------------------------------------------------------------------ DXF
def write_dxf(sec, snap, path):
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 21   # US survey feet
    msp = doc.modelspace()
    layers = {"GRID": 253, "GRID_TEXT": 8, "TEXT": 7, "MATCHLINE": 1, "PILE_PROJECTED": 1, "TITLE": 7,
              EG_STYLE[0]: EG_STYLE[1], POND_STYLE[0]: POND_STYLE[1]}
    for st in ROLE_STYLE.values():
        layers[st[0]] = st[1]
        layers[st[0] + "_HATCH"] = st[1]
    for name, color in sorted(layers.items()):
        doc.layers.add(name, color=color)
    doc.layers.get("PILE_PROJECTED").dxf.linetype = "DASHED"
    lo, hi = sec["window"]
    zlo, zhi = extents(sec)

    def text(s, x, y, h, layer="TEXT", align=TextEntityAlignment.LEFT, rot=0):
        t = msp.add_text(s, height=h, rotation=rot, dxfattribs={"layer": layer, "style": "OpenSans"})
        t.set_placement((x, y), align=align)
        return t
    # grid: elevations every 5 ft, stations every 20 ft
    for z in range(int(zlo), int(zhi) + 1, 5):
        msp.add_line((lo, z), (hi, z), dxfattribs={"layer": "GRID"})
        text("%d" % z, lo - 1.5, z, 1.0, "GRID_TEXT", TextEntityAlignment.MIDDLE_RIGHT)
        text("%d" % z, hi + 1.5, z, 1.0, "GRID_TEXT", TextEntityAlignment.MIDDLE_LEFT)
    s0 = math.ceil(lo / 20) * 20
    for s in [lo] + list(range(int(s0), int(hi) + 1, 20)) + [hi]:
        msp.add_line((s, zlo), (s, zhi), dxfattribs={"layer": "GRID"})
        text(station_text(s), s, zlo - 1.5, 1.0, "GRID_TEXT", TextEntityAlignment.TOP_CENTER, 0)
    # terrain
    for key, style in (("EG", EG_STYLE), ("POND", POND_STYLE)):
        for piece in sec["terrain"][key]:
            msp.add_lwpolyline(piece, dxfattribs={"layer": style[0]})
    # cut elements
    for o in sec["objects"]:
        layer = ROLE_STYLE[o["role"]][0]
        for lp in o["loops"]:
            msp.add_lwpolyline(lp["pts"], close=lp["closed"], dxfattribs={"layer": layer})
            if lp["closed"] and o["role"] != "strap":
                h = msp.add_hatch(dxfattribs={"layer": layer + "_HATCH"})
                h.set_pattern_fill("ANSI31", scale=0.5)
                h.paths.add_polyline_path(lp["pts"], is_closed=True)
    for pp in sec["projected_piles"]:
        (a, b), (z0, z1) = pp["sta"], pp["z"]
        msp.add_lwpolyline([(a, z0), (b, z0), (b, z1), (a, z1)], close=True, dxfattribs={"layer": "PILE_PROJECTED"})
    # labels: element names and the elevations a geotechnical engineer looks for
    done = set()
    for r in element_table(sec):
        mid = (r["sta"][0] + r["sta"][1]) / 2
        if r["role"] == "footing":
            text("%s BOT. EL. %.2f" % (r["name"].replace("Finished", ""), r["bottom"]), mid, r["bottom"] - 1.2, 0.8,
                 align=TextEntityAlignment.TOP_CENTER)
        elif r["role"] == "mse":
            text("%s TOP EL. %.2f" % (r["name"].replace("Mitred", ""), r["top"]), mid, r["top"] - 1.0, 0.8,
                 align=TextEntityAlignment.TOP_RIGHT, rot=90)
        elif r["role"] == "pile":
            key = (round(r["sta"][0], 1), round(r["bottom"], 2))
            if key not in done:
                done.add(key)
                text("PILE TIP EL. %.2f" % r["bottom"], mid, r["bottom"] - 1.2, 0.8,
                     align=TextEntityAlignment.TOP_CENTER)
        elif r["role"] in ("cap",):
            text("%s BOT. EL. %.2f" % (r["name"].replace("Bridge", ""), r["bottom"]), mid, r["bottom"] - 1.2, 0.8,
                 align=TextEntityAlignment.TOP_CENTER)
    # where the existing-ground survey stops short of the window
    for s, z in survey_limits(sec):
        msp.add_line((s, z - 3), (s, z + 6), dxfattribs={"layer": EG_STYLE[0]})
        text("LIMIT OF EXISTING-GROUND SURVEY", s - 0.4, z + 7, 0.8, EG_STYLE[0], TextEntityAlignment.BOTTOM_LEFT, 90)
    # match line at the pier centerline
    pier = snap["stations"]["PIER"]
    if lo - 1e-6 <= pier <= hi + 1e-6:
        msp.add_line((pier, zlo), (pier, zhi), dxfattribs={"layer": "MATCHLINE"})
        # rotated 90 degrees the text body lies on -x of a BOTTOM anchor, +x of a TOP one
        text("CL PIER  STA. %s  (MATCH LINE)" % station_text(pier), pier + (-0.5 if pier >= hi else 0.5), zlo + 2,
             1.0, "MATCHLINE", TextEntityAlignment.BOTTOM_LEFT if pier >= hi else TextEntityAlignment.TOP_LEFT, 90)
    for key, label in (("EB1", "FFBW END BENT 1"), ("EB2", "FFBW END BENT 2")):
        s = snap["stations"][key]
        if lo < s < hi:
            msp.add_line((s, zhi - 8), (s, zhi), dxfattribs={"layer": "TEXT"})
            text("%s STA. %s" % (label, station_text(s)), s + 1, zhi - 1, 1.0, align=TextEntityAlignment.TOP_LEFT)
    # title and notes
    y = zhi + 12
    text(sec["title"], lo, y, 2.5, "TITLE")
    notes = ["VERTICAL PLANE PARALLEL TO STATIONING, %s FT %s OF THE BRIDGE PGL (MODEL X = %.3f FT)." % (
                 ("%.1f" % abs(sec["offset_ft"])), "NORTH" if sec["offset_ft"] >= 0 else "SOUTH", sec["x_ft"]),
             "STA. %s TO STA. %s; %.1f FT BEYOND THE OUTERMOST PROJECT ELEMENT ON THE %s END." % (
                 station_text(lo), station_text(hi), sec["clearance_ft"], sec["exterior"].upper()),
             "HORIZONTAL AND VERTICAL SCALE 1:1, US SURVEY FEET. X = STATION (FT), Y = ELEVATION (FT).",
             "EXISTING GROUND: Ex_I-95_Middle SURVEY TIN, SURVEYED FROM STA. %s TO STA. %s ON THIS PLANE. "
             "POND 14D: SUPPLIED PROPOSED POND TIN." % (station_text(sec["terrain"]["EG"][0][0][0]),
                                                       station_text(sec["terrain"]["EG"][-1][-1][0])),
             "STRUCTURE: REGISTERED FREECAD MODEL SHA-256 %s. NO SOIL LAYERS OR WATER TABLE." %
             snap["model_sha256"][:16].upper(),
             "PRELIMINARY - NOT FOR CONSTRUCTION - GENERATED FROM THE CURRENT FREECAD MODEL."]
    for i, n in enumerate(notes):
        text(n, lo, y - 3.2 - 1.6 * i, 1.0, "TITLE")
    # element table below the section
    rows = element_table(sec)
    y = zlo - 6
    text("ELEMENTS CUT BY THE SECTION", lo, y, 1.4, "TITLE")
    cols = [0, 40, 70, 90, 110, 125]
    heads = ["ELEMENT", "TYPE", "FROM STA.", "TO STA.", "TOP EL.", "BOTTOM EL."]
    y -= 2.5
    for cx, hd in zip(cols, heads):
        text(hd, lo + cx, y, 0.9, "TITLE")
    for r in rows:
        y -= 1.5
        vals = [r["name"], ROLE_NAMES[r["role"]], station_text(r["sta"][0]), station_text(r["sta"][1]),
                "%.2f" % r["top"], "%.2f" % r["bottom"]]
        for cx, v in zip(cols, vals):
            text(v, lo + cx, y, 0.8)
    from collections import OrderedDict
    doc.classes.add_required_classes(doc.dxfversion)
    doc.classes.classes = OrderedDict(sorted(doc.classes.classes.items()))
    doc.saveas(path)


# ------------------------------------------------------------------ HTML
def html_data(snap):
    secs = []
    for sec in snap["sections"]:
        zlo, zhi = extents(sec)
        secs.append({"id": sec["id"], "title": sec["title"], "offset": sec["offset_ft"], "window": sec["window"],
                     "z": [zlo, zhi], "clearance": sec["clearance_ft"], "exterior": sec["exterior"],
                     "eg": sec["terrain"]["EG"], "pond": sec["terrain"]["POND"],
                     "objects": [{"n": o["name"], "r": o["role"], "l": [lp["pts"] for lp in o["loops"]],
                                  "c": [lp["closed"] for lp in o["loops"]]} for o in sec["objects"]],
                     "piles": sec["projected_piles"], "table": element_table(sec),
                     "limits": survey_limits(sec)})
    return {"sections": secs, "stations": snap["stations"],
            "roles": {k: {"name": ROLE_NAMES[k], "color": v[2]} for k, v in ROLE_STYLE.items()},
            "eg_color": EG_STYLE[2], "pond_color": POND_STYLE[2], "model": snap["model_sha256"][:16]}


def write_html(snap, path):
    template = (Path(__file__).parent / "report_template.html").read_text(encoding="utf-8")
    data = json.dumps(html_data(snap), separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    src = "".join("<li><b>%s</b> %s</li>" % (html.escape(k), html.escape(Path(v["path"]).name))
                  for k, v in snap["terrain_sources"].items() if k.endswith("landxml"))
    page = template.replace("/*DATA*/null", data).replace("<!--SOURCES-->", src) \
        .replace("<!--MODEL-->", html.escape(snap["model_sha256"][:16].upper()))
    Path(path).write_text(page, encoding="utf-8", newline="\n")


def dxf_name(sec):
    return "B4_Geotech_Section_%s.dxf" % sec["id"]


def write_outputs(snapshot_path, out_dir):
    import ezdxf
    keep = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        for sec in snap["sections"]:
            p = out_dir / dxf_name(sec)
            write_dxf(sec, snap, p)
            files[p.name] = sha(p)
        hp = out_dir / HTML_NAME
        write_html(snap, hp)
        files[hp.name] = sha(hp)
        manifest = {"generator": GENERATOR, "snapshot_sha256": sha(snapshot_path), "model_sha256": snap["model_sha256"],
                    "files": files,
                    "sections": [{"id": s["id"], "offset_ft": s["offset_ft"], "from": station_text(s["window"][0]),
                                  "to": station_text(s["window"][1]), "clearance_ft": s["clearance_ft"],
                                  "eg_coverage": s["eg_coverage"],
                                  "eg_survey_limits": [station_text(p[0]) for p in survey_limits(s)],
                                  "elements": len(s["objects"]),
                                  "projected_piles": len(s["projected_piles"])} for s in snap["sections"]]}
        (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = keep
