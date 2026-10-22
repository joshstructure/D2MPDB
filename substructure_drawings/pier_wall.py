"""Pier wall sheets: the wall elevation with its reinforcement and the
annular pile ring plates, the sections through the wall and the ring plate
details (model decisions D-076 and D-079, 22 October 2026).

The pier plan and elevation sheet shows the wall broken under the cap (E7:
at 3/8" the sheet has no height for the 16 ft wall under the stirrup row),
so the wall gets its own sheets, as the cheek walls do:

- PIER WALL ELEVATION (3/8"): the whole wall under a 1 ft cap stub, the
  pipe piles hidden inside it and cut 0.6 ft under its bottom, the twenty
  ring plates hidden, the first and last bar of every run (C3), the wall
  height and the horizontal series at the left, the vertical series over
  the cap stub, the wall length under the piles and the callouts in a
  column at the right; it carries the flags of sections H-H and J-J.
- SECTION H-H (1/2"): the horizontal cut through the middle ring row seen
  from above in the plan frame: the cut wall, piles and plates, the
  verticals end-on, the nearest horizontals and the end U returns in plane,
  the vertical series under the wall, the end-face verticals and the
  thickness at the right end, the cover inside the wall (C11) and the U
  leg length over the back face.
- SECTION J-J (1/2", broken between ring rows 2 and 4, E7): the transverse
  cut through pile 2 in the section frame: the wall, the cut pipe with its
  five plates, the horizontals end-on on both faces, the nearest verticals
  in plane, the ring plate tops at the left, the horizontal series at the
  right and the thickness under the pile stub.
- ANNULAR RING PLATE (PLAN, 1-1/2") and SECTION K-K (3" = 1'-0"): one
  plate on its pile with the diameters, the plate thickness and width, the
  root gap and the AWS symbol of the two continuous fillets.

Every size comes from the model's ``PierWallSteelInputs`` (the snapshot's
``pier_wall.inputs``) and the projected solids; the bar marks are the SDM
marks of ``bars.py`` (G family).  The rule ids in comments are those of
STYLE_GUIDE.md.
"""
import math
from collections import OrderedDict

from . import fdot
from .cad import View
from .details import _bar, _clean, _nearest, _title_below, cut_bars
from .views import (IN, callouts, chain_dims, draw_edges, edge_points, extents, run_chain, series_text,
                    text_w)

CAP_STUB_FT = 1.0        # the cap drawn this far above its bottom over the wall (D12: a break line)
PILE_STUB_FT = 0.85      # the piles drawn this far under the wall bottom (their break lobes there; the
#                          circled pile numbers beside the lobes stay clear of the wall bottom line, A1)


def _split(bars):
    """The wall bars by role: face verticals, end-face verticals,
    horizontals (one list per face, back first), U returns per end."""
    out = {"vert": [], "end_vert": [], "horiz": OrderedDict(), "u": OrderedDict()}
    for b in bars:
        tag = b["name"].replace("PierWallSteel", "")
        if b["subtype"] == "vert":
            out["end_vert" if tag.startswith("E") else "vert"].append(b)
        elif b["subtype"] == "horiz":
            out["horiz"].setdefault(tag[:2], []).append(b)
        else:
            out["u"].setdefault(tag[:2], []).append(b)
    return out


def inches(x_in, step=1.0 / 16):
    """A plate or pipe size in inches only (23", 20⅛", ½"): steel sizes are
    written in inches whatever their length, unlike the concrete dimensions
    of ``fdot.ft_in``."""
    total = fdot.round_in(x_in, step)
    whole = math.floor(total)
    fr = total - whole
    fs = fdot.frac(fr) if fr else ""
    return ("%d%s\"" % (whole, fs)) if whole else ("%s\"" % (fs or "0"))


def _wall_texts(s):
    """Sizes of the model's wall steel controller for notes and callouts."""
    i = s.wall_steel["inputs"]
    return {
        "bar": "#%d" % i["BarNumber"], "pitch": fdot.ft_in(i["MaximumSpacing"] / 12.0), "cover": fdot.ft_in(i["Cover"] / 12.0),
        "u_leg": fdot.ft_in(i["ULeg"] / 12.0), "ring_t": inches(i["RingThickness"]),
        "ring_od": inches(i["RingOD"]), "ring_id": inches(i["RingID"]),
        "ring_w": inches((i["RingOD"] - i["RingID"]) / 2.0), "weld": inches(i["WeldLeg"]),
        "first_top": fdot.ft_in(i["FirstRingTop"] / 12.0), "pitch_rings": fdot.ft_in(i["RingSpacing"] / 12.0),
        "n_rings": i["RingCount"], "gap": inches((i["RingID"] - 20.0) / 2.0), "gap_dia": inches(i["RingID"] - 20.0),
        "tol": fdot.ft_in(i["PlacementTolerance"] / 12.0),
    }


def marks_of(s):
    """{"vert", "horiz", "u"} -> mark of the wall bars."""
    out = {}
    for b in s.wall_bars():
        out.setdefault(b["subtype"], b["mark"])
    return out


# ================================================================ elevation
def wall_elevation(b, zone, letters=("H", "J"), ring_sheet=None):
    s = b.s
    W = s.wall_steel
    v = View(b.doc, zone, "%s WALL ELEVATION" % s.key)
    th, k = v.th, IN * v.sf
    fn = s.P_elev
    uL, uR = s.wall_u
    z_bot, z_top = s.wall_bot, s.wall_top
    stub_top = s.cap_bot + CAP_STUB_FT
    z_pile = z_bot - PILE_STUB_FT
    cu = s.cap_u
    # the wall, the cap stub, the hidden piles and plates (hidden lines on the
    # _h levels; the hidden pile outlines run on under the wall bottom where
    # the piles show).  The window top stands a hair under the stub's cut
    # face, so the cut face's own top edge is not drawn along the break
    # line (its zigzag would then cross a "whole" edge, D15) and the stub's
    # end faces and the piles embedded in the cap end at the break (D12)
    box = (cu[0] - 0.3, z_pile, cu[1] + 0.3, stub_top - 0.002)
    draw_edges(v, _clean(W["elev"]), box=box)
    v.break_line((cu[0] - 0.06 * k, stub_top), (cu[1] + 0.06 * k, stub_top))
    circles = []
    for p in s.piles:
        v.pile_break(p["u"], z_pile, p["width"], "pipe", "PileSteel")
        v.line((p["u"], z_top - 0.3), (p["u"], z_pile - 0.12 * k), "CL_Minor")
        circles.append((p["u"] - p["width"] / 2 - 0.16 * k, z_pile + 0.2 * k))
        v.circled_number(circles[-1], p["no"])
    # ------------------------------------------------------------ steel
    parts = _split(s.wall_bars())
    mk = marks_of(s)
    nudge = 0.03 * k   # C4: daylight between a U leg and the horizontal it laps
    # face verticals: the first and last of the run (C3); the series over the cap stub
    us = sorted({round(s.u(x["x_station"]), 4) for x in parts["vert"]})
    for u in (us[0], us[-1]):
        bar = next(x for x in parts["vert"] if abs(s.u(x["x_station"]) - u) < 1e-3)
        zs = [p[2] for p in bar["pts"]]
        v.line((u, min(zs)), (u, max(zs)), "Rebar")
    # end-face verticals: one line at each end (they stand in the wall thickness)
    ends = sorted({round(s.u(x["x_station"]), 4) for x in parts["end_vert"]})
    for u in ends:
        bar = next(x for x in parts["end_vert"] if abs(s.u(x["x_station"]) - u) < 1e-3)
        zs = [p[2] for p in bar["pts"]]
        v.line((u, min(zs)), (u, max(zs)), "Rebar")
    # horizontals: the bottom and top bar (both faces lie on one line)
    face = next(iter(parts["horiz"].values()))
    zs_h = sorted(round(x["pts"][0][2], 4) for x in face)
    for z in (zs_h[0], zs_h[-1]):
        bar = next(x for x in face if abs(x["pts"][0][2] - z) < 1e-3)
        pts = [fn(p) for p in bar["pts"]]
        v.line(pts[0], pts[-1], "Rebar")
    u_bar = sorted((fn(face[0]["pts"][0])[0], fn(face[0]["pts"][-1])[0]))
    # end U returns: the bottom and top one at each end, their legs seen as
    # one line along the horizontals they lap (C4: nudged for daylight)
    u_tips = []
    for end, lst in parts["u"].items():
        zs_u = sorted(lst, key=lambda x: x["pts"][0][2])
        for bar in (zs_u[0], zs_u[-1]):
            pts = [fn(p) for p in bar["pts"]]
            xs = sorted(q[0] for q in pts)
            z = pts[0][1] + (nudge if bar is zs_u[-1] else -nudge)
            v.line((xs[0], z), (xs[-1], z), "Rebar")
            if bar is zs_u[-1]:
                u_tips.append(((xs[0] + xs[-1]) / 2, z, xs))
    # ------------------------------------------------------- dimensions
    # the vertical series over the cap stub (B3: the extension lines rise
    # from the stub's break, as on the pier elevation)
    xs, texts = run_chain([(us, series_text(us, mk["vert"], count=len(us), ef=True))], (uL, uR))
    z_up = stub_top + 0.45 * k
    chain_dims(v, xs, texts, stub_top, z_up)
    # the left column: the horizontal series (each extension line to its
    # bar end, B3) and the wall height beyond it
    x1 = uL - 0.5 * k
    x2 = x1 - 0.45 * k
    zc, tc = run_chain([(zs_h, series_text(zs_h, mk["horiz"], count=len(zs_h), ef=True))], (z_bot, z_top))
    yo = [uL if (abs(z - z_bot) < 1e-6 or abs(z - z_top) < 1e-6) else u_bar[0] for z in zc]
    chain_dims(v, zc, tc, yo, x1, vertical=True)
    v.dim((uL, z_bot), (uL, z_top), -(x2 - uL), 90, step=0.125)
    # the wall length under the piles (A16: the pile numbers in their own band)
    y_len = z_pile - 0.65 * k
    v.dim((uL, z_bot), (uR, z_bot), y_len - z_bot, 0, step=0.125)
    # ---------------------------------------------------------- flags
    sec = W["section_plan"]
    z_cut = sec["z_cut_ft"]
    v.section_cut((x2 - 0.5 * k, z_cut), (uR + 0.45 * k, z_cut), letters[0], (0.0, -1.0))
    pj = next((p for p in s.piles if p["name"] == W["section_x"]["pile"]), s.piles[0])
    v.section_cut((pj["u"], z_pile - 0.45 * k), (pj["u"], z_up + 0.55 * k), letters[1], (-1.0, 0.0))
    # --------------------------------------------------------- callouts
    t = _wall_texts(s)
    p4 = max(s.piles, key=lambda q: q["u"])
    # (the rows stand at their tips' heights, so every leader runs nearly
    # level and none crosses the H flag at the cut height, A13: the ring
    # named is the one in row 2, under the cut through row 3)
    ring = next((r for r in s.rings if r["pile_no"] == p4["no"] and r["row"] == 2), s.rings[-1])
    u_e = ends[-1]
    sheet_ref = ("\\PSEE SHEET %s" % ring_sheet) if ring_sheet else ""
    # (rows at their tips' heights: level leaders to the pile face, the ring
    # edge, the end vertical and into the cap stub (A3, D15: a leader into
    # the stub from above it would cross the stub's break line); the U
    # return's leader slides along its leg to meet it at 35 degrees, A3)
    z_ring = (ring["top_ft"] + ring["bot_ft"]) / 2
    z_e = z_bot + 0.7 * (z_top - z_bot)
    u_leg = max(u_tips, key=lambda q: q[0])
    items = [
        ([(p4["u"] + p4["width"] / 2, z_pile + 0.15 * k)], "20\" %s STEEL PIPE\\PPILE (TYP.)" % "Ø", z_pile + 0.15 * k),
        ([(ring["u"] + ring["od_ft"] / 2, z_ring)], "%s ANNULAR RING\\PPLATES, %d PER PILE%s" % (t["ring_t"], t["n_rings"], sheet_ref), z_ring),
        ([(u_e, z_e)], "%d~%s EA. END\\P(END FACE)" % (len(parts["end_vert"]) // 2, mk["vert"]), z_e),
        ([(max(u_leg[2]), u_leg[1])], "%s (EF) END U RETURN\\P(TYP. EA. END)" % mk["u"]),
        ([(uR + 0.25, s.cap_bot + 0.5)], "PIER CAP", s.cap_bot + 0.5, {"area": True}),
    ]
    callouts(v, items, uR + 1.0 * k, 1, slide=True)
    v.title((0.0, y_len - 0.45 * k), "PIER WALL ELEVATION", "(LOOKING AHEAD STATION)", subject_cx=0.0)
    return v


# ============================================================== section H-H
def section_plan(b, zone, letter, ring_sheet=None):
    s = b.s
    W = s.wall_steel
    sec = W["section_plan"]
    depth = s.S["section_depth_ft"]
    v = View(b.doc, zone, "%s SECTION %s" % (s.key, letter))
    th, k = v.th, IN * v.sf
    fn = s.P_plan
    uL, uR = s.wall_u
    vf = sorted((s.v(s.wall_bb[1]), s.v(s.wall_bb[4])))   # the wall faces, front (low v) and back
    edges = _clean(sec["edges"])
    draw_edges(v, edges, hidden=False)
    # ------------------------------------------------------------ bars
    z_cut = sec["z_cut_ft"]
    dots, shapes = cut_bars(s.wall_bars(), 2, z_cut, z_cut - depth, z_cut, fn)
    shapes = _nearest(shapes, 2, z_cut, key=lambda x: (x["mark"], x["name"].replace("PierWallSteel", "")[:2]))
    for mark, ps in dots.items():
        for p, r in ps:
            v.dot(p, r)
    for bar, pts in shapes:
        _bar(v, pts, bar["dia_in"])
    parts = _split(s.wall_bars())
    mk = marks_of(s)
    t = _wall_texts(s)
    # ------------------------------------------------------- dimensions
    # under the front face: the vertical series, the wall length below it
    us = sorted({round(s.u(x["x_station"]), 4) for x in parts["vert"]})
    xs, texts = run_chain([(us, series_text(us, mk["vert"], count=len(us), ef=True))], (uL, uR))
    y1 = vf[0] - 0.5 * k
    chain_dims(v, xs, texts, vf[0], y1)
    y2 = y1 - 0.4 * k
    v.dim((uL, vf[0]), (uR, vf[0]), y2 - vf[0], 0, step=0.125)
    # the right end: the thickness (the end-face verticals are equally
    # spaced across it; their callout says so)
    u_e = max(round(s.u(x["x_station"]), 4) for x in parts["end_vert"])
    x2 = uR + 0.5 * k
    v.dim((uR, vf[0]), (uR, vf[1]), -(x2 - uR), 90, step=0.125)
    # the cover, inside the wall at the front face (C11: to the outermost
    # bar, where it matters), its value in the clear band between the mats
    # (between piles 1 and 2, off the ring plates)
    front = [(bar, pts) for bar, pts in shapes if bar["subtype"] == "horiz" and abs(pts[0][1] - vf[0]) < abs(pts[0][1] - vf[1])]
    if front:
        bar, pts = front[0]
        edge = pts[0][1] - bar["dia_in"] / 24.0
        pu = sorted(p["u"] for p in s.piles)
        u_c = (pu[0] + pu[1]) / 2 if len(pu) > 1 else uL + 4.5
        v.dim((u_c, vf[0]), (u_c, edge), 0.0, 90, "%s CLR" % t["cover"], horizontal=True,
              loc=(u_c, (vf[0] + vf[1]) / 2))
    # the U leg over the back face at the left end: the straight leg is the
    # bar's first (or last) piece, from its end to the start of the bend
    u_bars_all = [x for lst in parts["u"].values() for x in lst]
    bar = min((x for x in u_bars_all if abs(x["pts"][0][2] - z_cut) < 1.0),
              key=lambda x: min(fn(p)[0] for p in x["pts"]))
    pts = [fn(p) for p in bar["pts"]]
    a0, a1 = (pts[0], pts[1]) if abs(pts[0][1] - vf[1]) < abs(pts[-1][1] - vf[1]) else (pts[-1], pts[-2])
    v.dim((min(a0[0], a1[0]), vf[1]), (max(a0[0], a1[0]), vf[1]), 0.5 * k, 0, fdot.ft_in(abs(a1[0] - a0[0]), 0.25))
    # ------------------------------------------------------ pile numbers
    for p in s.piles:
        v.circled_number((p["u"], y2 - 0.42 * k), p["no"])
    # --------------------------------------------------------- callouts
    # (the pile and plate outlines are drawn as polylines of the cut, so a
    # tip on them stands on a drawn line, A27)
    p4 = max(s.piles, key=lambda q: q["u"])
    ring = next(r for r in s.rings if r["pile_no"] == p4["no"])
    r_ring = ring["od_ft"] / 2
    back_bar = next(((bar, pts) for bar, pts in shapes if bar["subtype"] == "horiz" and (bar, pts) not in front), None)
    # the end U return at the right end (the one nearest the cut), its base
    # across the thickness a cover in from the wall end
    u_bars = [x for lst in parts["u"].values() for x in lst]
    ubar = max((x for x in u_bars if abs(x["pts"][0][2] - z_cut) < 1.0), key=lambda x: max(fn(p)[0] for p in x["pts"]), default=None)
    base = None
    if ubar is not None:
        upts = [fn(p) for p in ubar["pts"]]
        u_base = max(upts, key=lambda q: q[0])[0]
        base = (u_base, (vf[0] + vf[1]) / 2)
    ends_dots = sorted((p for p, _ in dots.get(mk["vert"], []) if abs(p[0] - u_e) < 0.02), key=lambda p: p[1])
    sheet_ref = ("\\PSEE SHEET %s" % ring_sheet) if ring_sheet else ""
    items = [
        ([(p4["u"] + p4["width"] / 2 * math.cos(math.radians(45)), p4["v"] + p4["width"] / 2 * math.sin(math.radians(45)))],
         "20\" %s STEEL PIPE PILE (TYP.)" % "Ø"),
        ([(ring["u"] + r_ring * math.cos(math.radians(-30)), ring["v"] + r_ring * math.sin(math.radians(-30)))],
         "%s ANNULAR RING PLATE (TYP.),\\P%s O.D. x %s I.D.%s" % (t["ring_t"], t["ring_od"], t["ring_id"], sheet_ref)),
    ]
    if base:
        items.append(([base], "%s (EF) END U RETURN (TYP.),\\P%s CONTACT LAP LEGS" % (mk["u"], t["u_leg"])))
    if ends_dots:
        items.append(([ends_dots[len(ends_dots) // 2]], "%d~%s EA. END, EQ. SPA." % (len(ends_dots), mk["vert"])))
    callouts(v, items, x2 + 0.6 * k, 1, spread=(vf[0] - 0.15 * k, vf[1] + 0.35 * k))
    # the horizontals, called out from above the wall in the middle bay
    # (where no U leg laps them; the U legs lie on the horizontals' lines
    # for their lap length, C10)
    if back_bar:
        bar, pts = back_bar
        r = bar["dia_in"] / 24.0
        tip = (0.6, pts[0][1] + r)
        knee = (tip[0] + 0.25 * k, vf[1] + 0.45 * k)
        v.leader([tip, knee, (knee[0] + 0.12 * k, knee[1])], "%s (EF)" % mk["horiz"], "left")
    _title_below(v, (uL + uR) / 2, "SECTION %s-%s" % (letter, letter),
                 "(HORIZONTAL SECTION THROUGH PIER WALL AT RING ROW %d)" % sec["row"])
    return v


# ============================================================== section J-J
def section_x(b, zone, letter, ring_sheet=None):
    s = b.s
    W = s.wall_steel
    sec = W["section_x"]
    depth = s.S["section_depth_ft"]
    v = View(b.doc, zone, "%s SECTION %s" % (s.key, letter))
    th, k = v.th, IN * v.sf
    fn = s.P_sec
    s0, s1 = s.wall_s
    z_bot, z_top = s.wall_bot, s.wall_top
    stub_top = s.cap_bot + CAP_STUB_FT
    z_clip = z_bot - PILE_STUB_FT
    rows = s.ring_rows()
    # E7: the band between ring rows 2 and 4 is removed (the wall is 16 ft
    # tall; drawn whole it would not fit the sheet with the cap and pile stubs)
    r_lo, r_hi = rows[1], rows[-2]
    z_break = (r_hi[2] - 0.45, r_lo[1] + 0.45, 0.6, z_clip)
    edges = [r for r in _clean(sec["edges"]) if r["vis"]]
    cs = s.cap_s
    xr = (cs[0] - 0.3, cs[1] + 0.3)
    # the cap stub over the wall, the wall, the cut pile with its plates
    b._broken(v, [dict(r) for r in edges if all(xr[0] - 0.01 <= p[0] <= xr[1] + 0.01 for p in edge_points(r))], z_break)
    T = v.xform
    b._break_lines(v, z_break, s0 - 0.4, s1 + 0.4)
    keep, v.xform = v.xform, None
    v.break_line((xr[0] - 0.06 * k, stub_top), (xr[1] + 0.06 * k, stub_top))
    pile = next(p for p in s.piles if p["name"] == sec["pile"])
    zcd = T((0, z_clip))[1]
    v.pile_break(pile["s"], zcd, pile["width"], "pipe", "PileSteel")
    v.xform = keep
    # ------------------------------------------------------------ bars
    x_cut = sec["x_global_ft"]
    dots, shapes = cut_bars(s.wall_bars(), 0, x_cut, x_cut, x_cut + depth, fn)
    shapes = _nearest(shapes, 0, x_cut, key=lambda x: (x["mark"], round(x["pts"][0][1], 1)))
    z_lo, z_hi = z_break[1], z_break[0]
    face_dots = OrderedDict()
    for mark, ps in dots.items():
        for p, r in ps:
            if z_lo < p[1] < z_hi:
                continue   # in the removed band
            v.dot(p, r)
            face_dots.setdefault(round(p[0], 3), []).append((p, r, mark))
    verts = []
    for bar, pts in shapes:
        if bar["subtype"] != "vert":
            continue
        lo = [q for q in pts if q[1] <= z_lo + 1e-6]
        hi = [q for q in pts if q[1] >= z_hi - 1e-6]
        a, c = min(pts, key=lambda q: q[1]), max(pts, key=lambda q: q[1])
        _bar(v, [a, (a[0], z_lo)], bar["dia_in"], caps=(True, False))
        _bar(v, [(c[0], z_hi), c], bar["dia_in"], caps=(False, True))
        verts.append((bar, a, c))
    mk = marks_of(s)
    t = _wall_texts(s)
    # ------------------------------------------------------- dimensions
    # (the annotation helpers apply the view's break transform to their
    # points; a dimension's value is measured on the true points, so a row
    # spanning the break reads the true length)
    # the left columns: the horizontal series (both faces alike; the
    # extension lines to the outer edge of the dots), the ring plate tops
    # from the wall bottom beyond it.  Both columns stand on the left so no
    # callout leader from the right crosses their rotated texts (A23).
    left = min(face_dots, key=lambda x: x)
    r_h = face_dots[left][0][1]
    zs_all = sorted(p[1] for p, _ in dots[mk["horiz"]] if abs(p[0] - left) < 1e-3)
    x1 = s0 - 0.5 * k
    # (the series alone, first to last bar: its end spaces are the cover,
    # dimensioned at the face; pulled out they stood on the ring chain's
    # extension lines, B9)
    chain_dims(v, [zs_all[0], zs_all[-1]], [series_text(zs_all, mk["horiz"], count=len(zs_all), ef=True)], left - r_h, x1,
               vertical=True)
    x2 = x1 - 0.85 * k   # (the series' pulled end values stand between the two columns, B9)
    tops = [r[1] for r in rows]
    n = len(tops) - 1
    zc2 = [z_bot, tops[0], tops[-1], z_top]
    tc2 = [None, "%d SPA @ %s = %s" % (n, fdot.ft_in((tops[-1] - tops[0]) / n, 0.125), fdot.ft_in(tops[-1] - tops[0], 0.125)), None]
    chain_dims(v, zc2, tc2, s0, x2, vertical=True, step=0.125)
    # the thickness under the pile stub
    v.dim((s0, z_bot), (s1, z_bot), -(PILE_STUB_FT + 0.45 * k), 0, step=0.125)
    # the cover at the bottom of the wall, inside it (C11), its value pulled
    # out beyond the right face (the space between the mats holds the pile)
    right = max(face_dots, key=lambda x: x)
    zs_r = sorted(p[1] for p, _, _ in face_dots[right])
    z_c = (zs_r[0] + zs_r[1]) / 2 if len(zs_r) > 1 else z_bot + 0.45
    v.dim((right + r_h, z_c), (s1, z_c), 0.0, 0, "%s CLR" % t["cover"], outside=1)
    # --------------------------------------------------------- callouts
    # in the DRAWN frame (the rows are spread over the drawn height; a row
    # placed in the removed band would land on the break)
    keep, v.xform = v.xform, None
    r_top = rows[-1]
    ring_edge = pile["s"] + s.rings[0]["od_ft"] / 2
    sheet_ref = ("\\PSEE SHEET %s" % ring_sheet) if ring_sheet else ""
    items = [
        ([T((pile["s"] + pile["width"] / 2, z_bot - 0.3))], "20\" %s STEEL PIPE PILE" % "Ø"),
        ([T((ring_edge, (r_top[1] + r_top[2]) / 2))],
         "%s x %s ANNULAR RING\\PPLATES (TYP. OF %d)%s" % (t["ring_t"], t["ring_w"], len(rows), sheet_ref)),
        ([(s1 + 0.6, s.cap_bot + 0.5)], "PIER CAP", None, {"area": True}),
    ]
    if verts:
        bar, a, c = max(verts, key=lambda q: q[1][0])
        items.append(([(c[0], z_hi + 0.35 * (c[1] - z_hi))], "%s (EF)" % mk["vert"]))
    hi_dots = [p for p, _, _ in face_dots[right] if p[1] > z_hi]
    if hi_dots:
        p = sorted(hi_dots, key=lambda q: q[1])[len(hi_dots) // 2]
        items.append(([(p[0] + r_h, p[1])], "%s (EF)" % mk["horiz"]))
    callouts(v, items, s1 + 0.8 * k, 1, spread=(zcd + 0.1 * k, stub_top + 0.3 * k))
    _title_below(v, (s0 + s1) / 2, "SECTION %s-%s" % (letter, letter), "(THROUGH PIER WALL AT PILE %d)" % pile["no"])
    v.xform = keep
    return v


# ======================================================= ring plate details
def _pile_radii(s):
    """Outer and inner radius (feet) of the pipe pile from the cut pile in
    the horizontal section (the two circles of the cut)."""
    sec = s.wall_steel["section_plan"]
    ring = s.rings[0]
    c = (s.u(ring["center_ft"][0]), s.v(ring["center_ft"][1]))
    radii = set()
    for r in sec["edges"]:
        if r["role"] != "pile_steel" or not r["vis"]:
            continue
        for p in edge_points(r):
            d = math.dist(p, c)
            if d < 1.2:
                radii.add(round(d, 3))
    outer = max(s.piles, key=lambda p: p["width"])["width"] / 2
    inner = min((r for r in radii if r < outer - 0.01), default=outer - 0.475 / 12.0)
    return outer, inner


def ring_plan(b, zone, letter="K"):
    s = b.s
    v = View(b.doc, zone, "%s RING PLAN" % s.key)
    th, k = v.th, IN * v.sf
    t = _wall_texts(s)
    r_po, r_pi = _pile_radii(s)
    r_o, r_i = s.rings[0]["od_ft"] / 2, s.rings[0]["id_ft"] / 2
    # (a circle is recorded for the checks as an octagon, so the callout
    # tips stand on its vertices, at multiples of 45 degrees: A27)
    for r in (r_po, r_pi):
        v.circle((0.0, 0.0), r, "PileSteel")
    for r in (r_o, r_i):
        v.circle((0.0, 0.0), r, "PileSteel")
    # the diameters at the left (the inner one nearer the plate, B7); the
    # cut K-K vertical through the centre, looking at the right half
    x1 = -r_o - 0.45 * k
    x2 = x1 - 0.45 * k
    v.dim((0.0, -r_i), (0.0, r_i), -x1, 90, "%s I.D." % t["ring_id"])
    v.dim((0.0, -r_o), (0.0, r_o), -x2, 90, "%s O.D." % t["ring_od"])
    v.section_cut((0.0, -r_o - 0.55 * k), (0.0, r_o + 0.55 * k), letter, (1.0, 0.0))
    a = math.radians(45)
    items = [([(r_po * math.cos(a), r_po * math.sin(a))], "20\" %s STEEL PIPE PILE" % "Ø"),
             ([(r_o * math.cos(-a), r_o * math.sin(-a))], "%s ANNULAR RING PLATE\\P(%d PER PILE)" % (t["ring_t"], t["n_rings"]))]
    callouts(v, items, r_o + 0.9 * k, 1, spread=(-r_o * 0.7, r_o * 0.7))
    _title_below(v, 0.0, "ANNULAR RING PLATE", "(PLAN)")
    return v


def weld_symbol(v, tips, ref, size_text, all_around=True):
    """AWS fillet weld symbol: the arrow(s) from the reference line's end
    to the joint(s), the reference line to the left of it, the fillet
    triangle under the line (arrow side) with its size at its left, the
    weld-all-around circle at the junction (the fillets are continuous
    round the pipe).  ``ref`` is the junction point (local)."""
    k = IN * v.sf
    th = v.th
    L = 0.75 * k
    x0 = ref[0] - L
    v._begin_call()
    for tip in tips:
        v.arrowhead(tip, ref, "Leader")
        v.line(tip, ref, "Leader")
    v.line((x0, ref[1]), ref, "Leader")
    if all_around:   # (inside the call: its octagon is the symbol's own, A11)
        v.circle(ref, 0.045 * k, "Leader")
    v._end_call()
    a = 0.14 * k   # the fillet triangle's leg
    xt = x0 + 0.42 * k
    v.pl([(xt, ref[1]), (xt, ref[1] - a), (xt + a, ref[1]), (xt, ref[1])], "Leader")
    v.text((xt - 0.4 * th, ref[1] - a / 2), size_text, None, "MIDDLE_RIGHT")


def ring_section(b, zone, letter="K"):
    s = b.s
    v = View(b.doc, zone, "%s SECTION %s" % (s.key, letter))
    th, k = v.th, IN * v.sf
    t = _wall_texts(s)
    i = s.wall_steel["inputs"]
    r_po, r_pi = _pile_radii(s)
    r_o, r_i = i["RingOD"] / 24.0, i["RingID"] / 24.0
    tp = i["RingThickness"] / 12.0
    w = i["WeldLeg"] / 12.0
    H = 0.5   # the pipe drawn 6 in above and below the plate, broken
    # the pipe wall (cut), the plate (cut), the two fillets
    for x in (r_po, r_pi):
        v.line((x, -H), (x, H), "PileSteel")
    v.break_line((r_pi - 0.08 * k, H), (r_po + 0.08 * k, H))
    v.break_line((r_pi - 0.08 * k, -H), (r_po + 0.08 * k, -H))
    v.pl([(r_i, 0.0), (r_o, 0.0), (r_o, -tp), (r_i, -tp)], "PileSteel", closed=True)
    top = [(r_po, 0.0), (r_po, w), (r_po + w, 0.0)]
    bot = [(r_po, -tp), (r_po, -tp - w), (r_po + w, -tp)]
    for tri in (top, bot):
        v.pl(tri + [tri[0]], "PileSteel")
    # dimensions: the plate thickness at its edge, its width under the bottom fillet
    v.dim((r_o, 0.0), (r_o, -tp), -0.4 * k, 90, t["ring_t"])
    v.dim((r_i, -tp), (r_o, -tp), -(w + 0.45 * k), 0, t["ring_w"])
    # the fillets: one symbol, two arrows (top and bottom of the plate), all around
    ref = (r_po - 0.55 * k, 0.75 * k)
    weld_symbol(v, [(r_po, w * 0.5), (r_po, -tp - w * 0.5)], ref, t["weld"])
    v.text((ref[0] - 0.75 * k - 0.4 * th, ref[1] + 0.3 * th), "(2 CONTINUOUS FILLETS,", None, "BOTTOM_RIGHT")
    v.text((ref[0] - 0.75 * k - 0.4 * th, ref[1] - 0.3 * th - th), "TYP. EACH PLATE)", None, "BOTTOM_RIGHT")
    items = [([(r_i, -tp / 2)], "%s ROOT GAP:\\PRING I.D. = PILE O.D. + %s" % (t["gap"], t["gap_dia"])),
             ([(r_po, -H + 0.35 * (H - tp))], "20\" %s STEEL PIPE PILE" % "Ø")]
    callouts(v, items, r_o + 0.9 * k, 1, spread=(-H - 0.2 * k, -tp - 0.1 * k))
    _title_below(v, (r_pi + r_o) / 2, "SECTION %s-%s" % (letter, letter), "(THROUGH ANNULAR RING PLATE)")
    return v
