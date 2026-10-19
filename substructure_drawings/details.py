"""Cheek wall sections and end bent details (STYLE_GUIDE D5, D7, D8).

Four views for the end bent detail sheets, after the FDOT sample plan set
PA-PS-0037.1 (BCC Engineering, 2025):

- SECTION F-F (THROUGH CHEEK WALL): the vertical cut through a cheek wall
  1 ft in front of the FFBW, seen from the bridge side like the elevation
  (sample B1-19 SECTION J-J): the cheek wall cut with its lug, the cap end
  cut and the backwall beyond, the nearest vertical bar as a bar (double
  lines at 3/4"), the horizontal bars end-on, the welded wire reinforcement
  of the lug with its cross wires as "x" marks.
- SECTION G-G (THROUGH CHEEK WALL AND BACKWALL): the horizontal cut at mid
  backwall height seen from above in the plan frame (sample B1-19 SECTION
  H-H): cheek and backwall, the verticals end-on, the hooked cheek bar and
  the backwall horizontals in plane.
- DETAIL "A" (CONSTRUCTION JOINT) and DETAIL "B" (END BENT BACKWALL
  V-GROOVE) (sample B1-17): schematic, not from the model.

The cut planes come from the snapshot (``S["cheek_sections"]``); bars are
cut here from ``Support.bars`` (``cut_bars``).  In both sections the
dimensions sit on the outer side of the cheek wall and the callouts in the
open space on its inner side (in front of and behind the backwall), as in
SECTION J-J, so no leader crosses a dimension row (A1).
"""
import math
import re
from collections import OrderedDict

from . import bars as barlib
from . import cad, fdot
from .cad import View, clip_segment
from .views import draw_edges, edge_points, extents, mark_list, run_chain, series_text, text_w

IN = 1.0 / 12.0
WWR_DIA_IN = 0.134   # W1.4 wire


# ============================================================== helpers
def cut_bars(bars, axis, c, lo, hi, fn):
    """Cut bars by the plane ``axis`` = c (0 = x, 1 = y, 2 = z).

    Each segment crossing the plane gives an end-on dot at ``fn(point)`` with
    the bar radius (feet); segments running nearly along the plane (less
    than half their length across it) give none, as in
    ``views.Builder._section_bars``.  A bar that crosses nowhere and lies
    within [lo, hi] on ``axis`` is an in-plane shape ``[fn(p) for p in pts]``.
    Returns (dots: OrderedDict mark -> [(pt, r)], shapes: [(bar, pts2d)])."""
    lo, hi = min(lo, hi), max(lo, hi)
    dots = OrderedDict()
    shapes = []
    for b in bars:
        pts = b["pts"]
        r = b.get("dia_in", 0.0) / 24.0
        crossed = False
        for p, q in zip(pts, pts[1:]):
            a, e = p[axis] - c, q[axis] - c
            if (a < 0) == (e < 0):
                continue
            crossed = True
            L = math.dist(p, q)
            if abs(q[axis] - p[axis]) / max(L, 1e-9) < 0.5:
                continue
            t = (c - p[axis]) / (q[axis] - p[axis])
            pt = tuple(p[i] + t * (q[i] - p[i]) for i in range(3))
            dots.setdefault(b["mark"], []).append((fn(pt), r))
        if not crossed and all(lo - 1e-6 <= p[axis] <= hi + 1e-6 for p in pts):
            shapes.append((b, [fn(p) for p in pts]))
    return dots, shapes


def _nearest(shapes, axis, c, key=None):
    """The in-plane shape of each series nearest the cut (STYLE_GUIDE C3)."""
    key = key or (lambda b: b["mark"])
    best = OrderedDict()
    for b, pts in shapes:
        dist = abs(sum(p[axis] for p in b["pts"]) / len(b["pts"]) - c)
        kk = key(b)
        if kk not in best or dist < best[kk][0]:
            best[kk] = (dist, b, pts)
    return [(b, pts) for _, b, pts in best.values()]


def _clean(edges):
    """Edge records without zero-length and duplicate entries (the snapshot
    repeats faces shared by two solids)."""
    seen, out = set(), []
    for r in edges:
        if r["t"] in ("L", "P"):
            pts = [tuple(round(c, 4) for c in p) for p in r["p"]]
            if max(math.dist(pts[0], p) for p in pts) < 1e-3:
                continue
            key = (r["role"], r["vis"], tuple(min(pts, pts[::-1])))
        else:
            key = (r["role"], r["vis"], r["t"], repr(r.get("p")), repr(r.get("c")), r.get("r"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _mark_key(m):
    g = re.match(r"^(\d+)([A-Z])(\d+)$", m)
    return (int(g.group(1)), g.group(2), int(g.group(3))) if g else (0, m, 0)


def _marks(marks):
    return mark_list(sorted(set(marks), key=_mark_key))


def _bar(v, pts, dia_in, layer="Rebar", caps=(True, True)):
    """A bar not seen end-on (STYLE_GUIDE C1) through ``View.bar``; ``caps``
    False leaves an end open where the bar is cut by the view's clip."""
    if not hasattr(v, "bar"):
        return v.pl(pts, layer)
    if all(caps) or v.sf > fdot.SCALES["1/2"]:
        return v.bar(pts, dia_in, layer)
    r = dia_in / 24.0
    left, right = cad.offset_polyline(pts, r), cad.offset_polyline(pts, -r)
    if len(left) < 2:
        return None
    v.pl(left, layer)
    v.pl(right, layer)
    if caps[0]:
        v.line(left[0], right[0], layer)
    if caps[1]:
        v.line(left[-1], right[-1], layer)


def _clip_runs(pts, box):
    """Parts of a polyline inside ``box``: [(run, first_is_real_end, last_is_real_end)]."""
    out, run = [], []
    for p, q in zip(pts, pts[1:]):
        seg = clip_segment(p, q, box)
        if seg is None:
            if len(run) > 1:
                out.append(run)
            run = []
            continue
        a, b = seg
        if run and math.dist(run[-1], a) < 1e-9:
            run.append(b)
        else:
            if len(run) > 1:
                out.append(run)
            run = [a, b]
    if len(run) > 1:
        out.append(run)
    return [(r, math.dist(r[0], pts[0]) < 1e-6, math.dist(r[-1], pts[-1]) < 1e-6) for r in out]


def _draw_bar_clipped(v, pts, dia_in, box, layer="Rebar"):
    for run, c0, c1 in _clip_runs(pts, box):
        _bar(v, run, dia_in, layer, (c0, c1))


def _xmark(v, c, size_in=0.022, layer="Rebar2"):
    """Wire seen end-on: a small "x" (sample B1-19, WWF cross wires)."""
    e = size_in * IN * v.sf
    v.line((c[0] - e, c[1] - e), (c[0] + e, c[1] + e), layer)
    v.line((c[0] - e, c[1] + e), (c[0] + e, c[1] - e), layer)


def _wwr(S, num, part):
    """Welded wire reinforcement wires of one cheek wall as bar-like records."""
    out = []
    for w in S.get("wwr", []):
        if w["group"].endswith(num) and part in w["name"]:
            out.append({"pts": barlib.polyline3(w, 10.0), "mark": "WWR", "dia_in": WWR_DIA_IN, "name": w["name"]})
    return out


def _cheek_frame(cheek):
    """(d, u_out, u_in): d is the direction (+1/-1 in u) from the outer face
    of the cheek wall toward the cap and backwall."""
    if cheek["u"] < 0:
        return 1.0, cheek["u_lo"], cheek["u_hi"]
    return -1.0, cheek["u_hi"], cheek["u_lo"]


def _box(x0, x1, y0, y1):
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _fits(v, txt, length):
    return text_w(v, txt) + 0.12 * IN * v.sf < length


def _chain(v, pts, texts, at, vertical=True, step=0.25):
    """One row of dimensions through feature points (STYLE_GUIDE B3: each
    extension line reaches its own feature), with the placement rules of
    ``views.chain_dims`` for values that do not fit (B1): beside the space
    in the free half of the neighbour or beyond the end of the row, else
    just below the row.  ``at`` is the u (vertical) or z/v (horizontal) of
    the dimension line."""
    ax = 1 if vertical else 0
    order = sorted(range(len(pts)), key=lambda i: pts[i][ax])
    if texts is not None and order != list(range(len(pts))):
        raise ValueError("chain points must be sorted")
    pts = [pts[i] for i in order]
    pad = 0.12 * IN * v.sf
    segs = []
    for i in range(len(pts) - 1):
        pa, pb = pts[i], pts[i + 1]
        L = abs(pb[ax] - pa[ax])
        if L < 1.0 / 192:
            continue
        txt = texts[i] if texts and i < len(texts) and texts[i] else fdot.ft_in(L, step)
        if text_w(v, txt) + pad > L and " @ " in txt:
            two = txt.replace(" @ ", "\\P@ ", 1)
            if text_w(v, two) + pad < L:
                txt = two
        segs.append((pa, pb, txt, L))
    fits = [text_w(v, t) + pad < L for _, _, t, L in segs]
    room = [[(L - text_w(v, t)) / 2 - pad] * 2 if f else [0.0, 0.0] for (_, _, t, L), f in zip(segs, fits)]
    n = len(segs)
    below = []
    for i, (pa, pb, txt, L) in enumerate(segs):
        out, level = None, 0
        if not fits[i]:
            need = text_w(v, txt) + (fdot.ARROW_IN + 0.1) * IN * v.sf
            if i == 0 and (n == 1 or not (fits[1] and room[1][0] > need)):
                out = -1
            elif i == n - 1 and not (fits[i - 1] and room[i - 1][1] > need):
                out = 1
            elif i + 1 < n and fits[i + 1] and room[i + 1][0] > need:
                out, room[i + 1][0] = 1, room[i + 1][0] - need
            elif i > 0 and fits[i - 1] and room[i - 1][1] > need:
                out, room[i - 1][1] = -1, room[i - 1][1] - need
            else:
                out = 0
                m, hw = (pa[ax] + pb[ax]) / 2, text_w(v, txt) / 2 + 0.6 * v.th
                while any(lv == level and lo < m + hw and m - hw < hi for lv, lo, hi in below):
                    level += 1
                below.append((level, m - hw, m + hw))
        if vertical:
            v.dim(pa, pb, pa[0] - at, 90, txt, outside=out, level=level, step=step)
        else:
            v.dim(pa, pb, at - pa[1], 0, txt, outside=out, level=level, step=step)


def _column(v, items, x_col, side):
    """Callouts in a column: items = [(tips, text, want_y)].  The texts start
    at x_col (side +1: text right of the landing, -1: left), at their wanted
    heights as far as spacing allows (as ``views.callouts``); several tips
    fan from one knee."""
    if not items:
        return
    gap = 2.1 * v.th
    order = sorted(items, key=lambda it: it[2])
    want = [it[2] for it in order]
    hs = [(1 + txt.count("\\P") * fdot.LINE_PITCH) * v.th for _, txt, _ in order]

    def spread(ys):
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + max(gap, (hs[i - 1] + hs[i]) / 2 + 0.6 * v.th))
        return ys
    ys = spread(list(want))
    shift = (sum(want) - sum(ys)) / len(ys)
    ys = spread([y + shift for y in ys])
    land = 0.14 * IN * v.sf
    al = "left" if side > 0 else "right"
    for (tips, txt, _), y in zip(order, ys):
        knee = (x_col - side * land, y)
        if len(tips) == 1:
            v.leader([tips[0], knee, (x_col, y)], txt, al)
        else:
            v.leader_fan(tips, knee, txt, al)


def _area_leader(v, tip, knee, text, align):
    """Leader to an area (the concrete of a member): no arrowhead, a small
    tilde at the tip inside the area, landing and text (sample B1-17
    "END BENT BACKWALL")."""
    k = IN * v.sf
    land = 0.12 * k
    end = (knee[0] + (land if align == "left" else -land), knee[1])
    v.pl([tip, knee, end], "Leader")
    s = 0.035 * k
    v.pl([(tip[0] - s + 2 * s * i / 12.0, tip[1] + 0.45 * s * math.sin(2 * math.pi * i / 12.0)) for i in range(13)],
         "Leader")
    h = v.th
    x = end[0] + 0.4 * h if align == "left" else end[0] - 0.4 * h
    if "\\P" in text:
        v.mtext((x, end[1] + 0.5 * h), text, h, attach=1 if align == "left" else 3)
    else:
        v.text((x, end[1]), text, h, "MIDDLE_LEFT" if align == "left" else "MIDDLE_RIGHT")


def _earth(v, x0, x1, base, height, cell_in=0.032, layer="Patterning"):
    """Earth fill as the AutoCAD EARTH pattern (a basket weave of three
    strokes per cell, alternately horizontal and vertical) turned 45 degrees,
    between x0 and x1 above ``base`` up to ``base + height(x)``; strokes
    leaving the area are dropped, which gives the ragged edge of the sample
    (B1-17 DETAIL "B").  Drawn as lines rather than a HATCH: ezdxf 1.4.4
    applies a hatch's pattern angle and scale again when the entity is
    moved (``View.place``)."""
    u = cell_in * IN * v.sf
    c45 = math.sqrt(0.5)

    def rot(p):
        return (x0 + (p[0] - p[1]) * c45, base + (p[0] + p[1]) * c45)

    def inside(p):
        return x0 <= p[0] <= x1 and base <= p[1] <= base + height(p[0])
    hmax = max(height(x0 + (x1 - x0) * i / 40.0) for i in range(41))
    span = (x1 - x0 + hmax) / c45
    n = int(span / u) + 2
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            a, b = i * u, j * u
            for f in (0.125, 0.5, 0.875):
                if (i + j) % 2 == 0:
                    p, q = (a, b + f * u), (a + u, b + f * u)
                else:
                    p, q = (a + f * u, b), (a + f * u, b + u)
                p, q = rot(p), rot(q)
                if inside(p) and inside(q):
                    v.line(p, q, layer)


def _title_below(v, x, title, sub=None, gap_in=0.18):
    """View title centred at x (the centre of the thing the view shows,
    recorded as the title's ``subject_cx`` for the E5 layout check), its top
    gap_in (paper) below everything drawn."""
    h = v.style_h(fdot.TITLE_STYLE)
    y = v.local_bbox[1] - gap_in * IN * v.sf - h
    v.title((x, y), title, sub, subject_cx=x)


def _inner_reach(edges, u_in, d, want):
    """How far into the cap the side section may run: ``want`` feet from the
    inner face of the cheek, stopped 0.2 ft short of the next vertical cap
    edge (the pile pocket), so no unexplained feature shows at the break."""
    reach = want
    for r in edges:
        if r["role"] != "cap" or not r["vis"]:
            continue
        pts = edge_points(r)
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) < 1e-4:
                off = d * (a[0] - u_in)
                if 0.25 < off < reach + 0.2:
                    reach = min(reach, off - 0.2)
    return reach


def _lug_u(edges, u_out, d, level, axis):
    """Inner face of the narrow lug at the end ``level`` of the cheek wall."""
    us = [p[0] for r in edges if r["role"] == "cheek" for p in edge_points(r) if abs(p[axis] - level) < 0.01]
    return max(us, key=lambda u: d * (u - u_out)) if us else None


def _cheek_bars(s, cheek):
    num = cheek["name"][-2:]
    return [x for x in s.bars if x["family"] == "cheek" and x["group"].endswith(num + "Bars")], num


# ============================================================== SECTION F-F
def cheek_section_side(b, zone, cheek, letter, wwr_note=2):
    """SECTION F-F (THROUGH CHEEK WALL), the vertical cut y = y_cut (1 ft in
    front of the FFBW) seen from the bridge side in the elevation frame
    (sample B1-19 SECTION J-J).  Scale: the zone's (3/4" = 1'-0")."""
    s = b.s
    S = s.S
    sec = S["cheek_sections"][cheek["name"]]
    depth = S["section_depth_ft"]
    v = View(b.doc, zone, "%s SECTION %s" % (s.key, letter))
    th, k = v.th, IN * v.sf
    d, u_out, u_in = _cheek_frame(cheek)

    def X(off):
        return u_in + d * off
    al_in = "left" if d > 0 else "right"   # text alignment of callouts on the inner side
    edges = _clean(sec["side_edges"])
    z_bot, z_top = cheek["bot"], cheek["top"]
    reach = _inner_reach(edges, u_in, d, 2.5)
    box = _box(u_out - d * 0.3, X(reach), z_bot - 0.3, z_top + 0.35 * k)
    draw_edges(v, edges, box=box, hidden=False)
    zs = [p[1] for r in edges if r["vis"] and r["role"] in ("cap", "backwall") for p in edge_points(r)
          if d * (p[0] - X(reach)) <= 1e-6]
    if zs:
        v.break_line((X(reach), min(zs) - 0.06 * k), (X(reach), max(zs) + 0.06 * k))
    lug_u = _lug_u(edges, u_out, d, z_bot, 1)
    # ------------------------------------------------------------ bars
    cb, num = _cheek_bars(s, cheek)
    y_cut = sec["y_cut_ft"]
    sd = 1.0 if s.e1 > 0 else -1.0          # the slab beyond the cut, toward the backwall
    dots, shapes = cut_bars(cb, 1, y_cut, y_cut, y_cut + sd * depth, s.P_elev)
    shapes = _nearest(shapes, 1, y_cut)
    for mark, ps in dots.items():
        for p, r in ps:
            v.dot(p, r)
    for bar, pts in shapes:
        _bar(v, pts, bar["dia_in"])
    # welded wire reinforcement in the lug: nearest wire in plane, cross wires "x"
    wires = _wwr(S, num, "Bottom")
    wdots, wshapes = cut_bars(wires, 1, y_cut, y_cut, y_cut + sd * depth, s.P_elev)
    wshapes = _nearest(wshapes, 1, y_cut, key=lambda w: "L")
    for w, pts in wshapes:
        for run, _, _ in _clip_runs(pts, box):
            v.pl(run, "Rebar2")
    bar_dots = [(p, r) for ps in dots.values() for p, r in ps]
    xe = 0.022 * k
    for ps in wdots.values():
        for p, _ in ps:
            if all(math.dist(p, q) > r + xe for q, r in bar_dots):
                _xmark(v, p)
    # ------------------------------------------------------ dimensions
    rows = OrderedDict()
    for mark, ps in dots.items():
        for p, r in ps:
            rows.setdefault(round(p[1], 4), []).append((p, r, mark))
    rows = OrderedDict(sorted(rows.items()))
    feat = {}
    for z, ds in rows.items():
        p, r, _ = min(ds, key=lambda t: d * (t[0][0] - u_out))
        feat[z] = (p[0] - d * r, p[1])           # outer edge of the outermost dot
    zr = list(rows)
    runs = []
    for grp in ([z for z in zr if z < s.cap_top], [z for z in zr if z >= s.cap_top]):
        if grp:
            runs.append((grp, series_text(grp, _marks(m for z in grp for _, _, m in rows[z]))))
    x1 = u_out - d * 0.35 * k
    # second column: vertical dimension texts sit on the -u side of their
    # lines, so on a right cheek both columns' texts share the channel
    # between the lines; widen it there to keep them apart (A2)
    x2 = x1 - d * (0.3 if d > 0 else 0.45) * k
    if runs:
        xs, texts = run_chain(runs, (z_bot, z_top))
        for i in range(len(xs) - 1):
            if xs[i] + 0.02 < s.cap_top < xs[i + 1] - 0.02 and texts[i] is None:
                xs.insert(i + 1, s.cap_top)
                texts.insert(i, None)
                break
        pts = []
        for z in xs:
            if abs(z - z_bot) < 1e-9 or abs(z - z_top) < 1e-9:
                pts.append((u_out, z))
            elif abs(z - s.cap_top) < 1e-9:
                pts.append((u_in, z))            # the cap top meets the cheek wall at its inner face
            else:
                pts.append(feat.get(round(z, 4), (u_out, z)))
        _chain(v, pts, texts, x1, vertical=True)
    v.dim((u_out, z_bot), (u_out, z_top), u_out - x2, 90, step=0.125)
    # top: the wall thickness.  (No clear-cover value to the bar mat: markup
    # 2026-10-19 round 4, "Remove this clear spacing anno since the project
    # has a required clear spacing and these bars are in a mat centered in
    # the wall with plenty of space"; C11)
    yt1 = z_top + 0.3 * k
    v.dim((u_out, z_top), (u_in, z_top), yt1 - z_top, 0, step=0.125)
    # bottom: lug thickness
    if lug_u is not None and abs(lug_u - u_out) > 0.05:
        lw = abs(lug_u - u_out)
        txt = fdot.ft_in(lw, 0.125)
        v.dim((u_out, z_bot), (lug_u, z_bot), -0.3 * k, 0, txt, outside=None if _fits(v, txt, lw) else -d)
    # the cap: height at the break, named on the dimension (sample: 4'-6" END BENT CAP)
    # (the value on the -u side of the line as ezdxf writes it, the name on
    # the +u side: a two-line dimension text would sit on the line)
    xb = X(reach)
    xd = xb + d * 0.45 * k
    v.dim((xb, s.cap_bot), (xb, s.cap_top), -d * 0.45 * k, 90, step=0.125)
    # the value sits on the outer side of its line (cad.View.dim puts the
    # text of a right-hand column on the right, B8); the name on the other side
    v.text((xd - d * 0.45 * th, (s.cap_bot + s.cap_top) / 2), "END BENT CAP", None,
           "BOTTOM_CENTER" if d > 0 else "TOP_CENTER", rot=90.0)
    # ------------------------------------------------------- callouts
    x_col = u_in + d * 0.45 * k
    land = 0.14 * k
    items = []
    groups = []
    for z, ds in rows.items():
        ms = tuple(sorted({m for _, _, m in ds}, key=_mark_key))
        tip = max((p for p, _, _ in ds), key=lambda p: d * p[0])
        if groups and groups[-1][0] == ms:
            groups[-1][1].append(tip)
        else:
            groups.append((ms, [tip]))
    for ms, tips in groups:
        want = sum(t[1] for t in tips) / len(tips)
        if len(tips) == 1:
            want += 0.22 * k      # angled leader, clear of a wire running through the dot
        items.append((tips, "/".join(ms), want))
    for bar, pts in shapes:      # vertical bars: tip in the highest gap between the row groups
        r = bar["dia_in"] / 24.0
        zlo, zhi = min(p[1] for p in pts) + 0.1, max(p[1] for p in pts) - 0.1
        spans = sorted((min(t[1] for t in tips), max(t[1] for t in tips)) for _, tips in groups)
        gaps = [(a[1], c[0]) for a, c in zip(spans, spans[1:])
                if c[0] - a[1] > 0.3 and not (a[1] - 0.15 < s.cap_top < c[0] + 0.15)]
        gaps = [(max(a, zlo), min(c, zhi)) for a, c in gaps if min(c, zhi) - max(a, zlo) > 0.3]
        a, c = gaps[-1] if gaps else (zlo, zhi)
        # keep the arrowhead clear of the corners where the cap and backwall
        # lines meet the cheek wall
        corners = [p[1] for rec in edges if rec["vis"] and rec["role"] in ("cap", "backwall")
                   for p in edge_points(rec) if abs(p[0] - u_in) < 0.01]
        zt = a + 0.5 * (c - a)
        for f in (0.3, 0.4, 0.5, 0.6):
            if all(abs(a + f * (c - a) - zc) > 0.12 for zc in corners):
                zt = a + f * (c - a)
                break
        ub = max(p[0] for p in pts) if d > 0 else min(p[0] for p in pts)
        tip = (ub + d * r, zt)
        dx = abs(x_col - d * land - tip[0])
        items.append(([tip], bar["mark"], zt + dx * math.tan(math.radians(30))))
    _column(v, items, x_col, d)
    # WWR: leader from the wire in the cap down to a note below the cap
    for w, pts in wshapes:
        legs = [(p, q) for p, q in zip(pts, pts[1:]) if abs(q[1] - p[1]) < 1e-3 and abs(q[0] - p[0]) > 0.05]
        if not legs:
            continue
        zl = legs[0][0][1]
        # tip on the wire inside the cap, between two cross wires
        on = sorted([p[0] for ps in wdots.values() for p, _ in ps if abs(p[1] - zl) < 0.03] +
                    [legs[0][0][0], legs[-1][1][0]])
        mids = [(a + c) / 2 for a, c in zip(on, on[1:]) if abs(c - a) > 0.15 and d * ((a + c) / 2 - u_in) > 0.1]
        um = min(mids, key=lambda m: abs(m - X(0.55))) if mids else X(0.55)
        tip = (um, zl)
        knee = (um + d * 0.32 * k, s.cap_bot - 0.35 * k)
        v.leader([tip, knee, (knee[0] + d * 0.12 * k, knee[1])], "WWR (SEE NOTE %d)" % wwr_note, al_in)
        break
    # centred on the cheek wall, the thing the section is named for (E5)
    _title_below(v, (u_out + u_in) / 2, "SECTION %s-%s" % (letter, letter), "(THROUGH CHEEK WALL)")
    return v


# ============================================================== SECTION G-G
def cheek_section_top(b, zone, cheek, letter, wwr_note=2):
    """SECTION G-G (THROUGH CHEEK WALL AND BACKWALL), the horizontal cut
    z = z_cut (mid backwall height) seen from above in the plan frame
    (sample B1-19 SECTION H-H).  Scale: the zone's (3/4" = 1'-0")."""
    s = b.s
    S = s.S
    sec = S["cheek_sections"][cheek["name"]]
    depth = S["section_depth_ft"]
    v = View(b.doc, zone, "%s SECTION %s" % (s.key, letter))
    th, k = v.th, IN * v.sf
    d, u_out, u_in = _cheek_frame(cheek)

    def X(off):
        return u_in + d * off
    al_in = "left" if d > 0 else "right"
    edges = _clean(sec["top_edges"])
    # monolithic cheek wall and backwall (markup 2026-10-17, "remove the joint
    # here and show it monolithic"): no line on the cheek's inner face within
    # the backwall thickness
    be0 = extents(edges, ("backwall",)) if any(r["role"] == "backwall" for r in edges) else None
    if be0:
        lo_v, hi_v = min(be0[1], be0[3]), max(be0[1], be0[3])
        # (markup 2026-10-19 round 3, "Remove this interface line to make
        # appear monolithic": the cheek's inner face is one edge from the
        # cheek top to the lug, longer than the backwall, so dropping only
        # edges wholly inside the backwall left it; the part within the
        # backwall thickness is cut out of any face edge, D10)

        def _cut_joint(r):
            """The edge with the stretch v in [lo_v, hi_v] on the cheek's
            inner face removed: [] (gone), [r] (untouched) or the pieces."""
            if r["t"] not in ("L", "P") or len(r["p"]) != 2:
                return [r]
            (a, b) = r["p"]
            if not (abs(a[0] - u_in) < 0.01 and abs(b[0] - u_in) < 0.01):
                return [r]
            v0, v1 = sorted((a[1], b[1]))
            if v1 <= lo_v + 0.01 or v0 >= hi_v - 0.01:
                return [r]
            out = []
            if v0 < lo_v - 0.01:
                out.append(dict(r, p=[[a[0], v0] + list(a[2:]), [a[0], lo_v] + list(a[2:])]))
            if v1 > hi_v + 0.01:
                out.append(dict(r, p=[[a[0], hi_v] + list(a[2:]), [a[0], v1] + list(a[2:])]))
            return out
        edges = [piece for r in edges for piece in _cut_joint(r)]
    reach = 2.99        # the snapshot clips the backwall 3 ft from the cheek: break just inside
    vs = [p[1] for r in edges for p in edge_points(r)]
    box = _box(u_out - d * 0.3, X(reach), min(vs) - 1.0, max(vs) + 1.0)
    draw_edges(v, edges, box=box, hidden=False)
    ce = extents(edges, ("cheek",))
    be = extents(edges, ("backwall",))
    v_ffbw = s.ffbw_v
    v_bb = be[3] if abs(be[1] - v_ffbw) < abs(be[3] - v_ffbw) else be[1]
    fs = -1.0 if v_ffbw < v_bb else 1.0         # toward the bridge (front) in v
    v_front, v_back = (ce[1], ce[3]) if fs < 0 else (ce[3], ce[1])
    v.break_line((X(reach), v_ffbw + fs * 0.06 * k), (X(reach), v_bb - fs * 0.06 * k))
    lug_u = _lug_u(edges, u_out, d, v_back, 1)
    # ------------------------------------------------------------ bars
    cb, num = _cheek_bars(s, cheek)
    z_cut = sec["z_cut_ft"]
    ulo, uhi = box[0], box[2]

    def inside(pts):
        return any(ulo - 0.5 <= s.u(p[0]) <= uhi + 0.5 for p in pts)
    bw = [x for x in s.bars if x["family"] == "backwall" and inside(x["pts"])]
    dots, shapes = cut_bars(cb + bw, 2, z_cut, z_cut - depth, z_cut, s.P_plan)
    shapes = _nearest(shapes, 2, z_cut, key=lambda x: (x["mark"], round(s.P_plan(x["pts"][0])[1], 2)
                                                         if x["family"] == "backwall" else None))
    for mark in list(dots):
        dots[mark] = [(p, r) for p, r in dots[mark] if ulo <= p[0] <= uhi]
        for p, r in dots[mark]:
            v.dot(p, r)
    for bar, pts in shapes:
        _draw_bar_clipped(v, pts, bar["dia_in"], box)
    wires = _wwr(S, num, "Side")
    wdots, wshapes = cut_bars(wires, 2, z_cut, z_cut - depth, z_cut, s.P_plan)
    wshapes = _nearest(wshapes, 2, z_cut, key=lambda w: "H")
    for w, pts in wshapes:
        for run, _, _ in _clip_runs(pts, box):
            v.pl(run, "Rebar2")
    bar_dots = [(p, r) for ps in dots.values() for p, r in ps]
    xe = 0.022 * k
    for ps in wdots.values():
        for p, _ in ps:
            if all(math.dist(p, q) > r + xe for q, r in bar_dots):
                _xmark(v, p)
    cheek_marks = {x["mark"] for x in cb}
    cdots = [(p, r, m) for m, ps in dots.items() if m in cheek_marks for p, r in ps]
    bdots = [(p, r, m) for m, ps in dots.items() if m not in cheek_marks for p, r in ps]
    cshape = [(bar, pts) for bar, pts in shapes if bar["family"] == "cheek"]
    bshape = [(bar, pts) for bar, pts in shapes if bar["family"] == "backwall"]
    # ------------------------------------------------------ dimensions
    x1 = u_out - d * 0.35 * k
    x2 = x1 - d * 0.3 * k
    pts = [(u_out, v_front), (u_in, v_ffbw), ((lug_u if lug_u is not None else u_out), v_bb), (u_out, v_back)]
    pts.sort(key=lambda p: p[1])
    _chain(v, pts, None, x1, vertical=True, step=0.125)
    v.dim((u_out, v_front), (u_out, v_back), u_out - x2, 90, step=0.125)
    # the wall thickness beyond the front face.  (No clear-cover value to
    # the bar mat: markup 2026-10-19 round 4, "Remove this clear spacing anno
    # since the project has a required clear spacing and these bars are in
    # a mat centered in the wall with plenty of space"; C11)
    yb1 = v_front + fs * 0.42 * k
    v.dim((u_out, v_front), (u_in, v_front), yb1 - v_front, 0, step=0.125)
    if lug_u is not None and abs(lug_u - u_out) > 0.05:
        lw = abs(lug_u - u_out)
        txt = fdot.ft_in(lw, 0.125)
        v.dim((u_out, v_back), (lug_u, v_back), -fs * 0.3 * k, 0, txt, outside=None if _fits(v, txt, lw) else -d)
    # ------------------------------------------------------- callouts
    land = 0.14 * k
    # column A (in front of the backwall, near the cheek): the cheek bars
    xa = u_in + d * 0.45 * k
    ra1 = v_ffbw + fs * 0.8 * k
    ra2 = ra1 + fs * 0.38 * k
    for bar, pp in cshape:     # the in-plane cheek bar (4E4 with its hook into the backwall): tip on its leg
        r = bar["dia_in"] / 24.0
        segs = sorted(zip(pp, pp[1:]), key=lambda t: -abs(t[1][1] - t[0][1]))
        a, c = segs[0]
        ul = a[0] + d * r
        lo_v, hi_v = sorted((a[1], c[1]))
        dx = abs(xa - d * land - ul)
        vt = ra1 - fs * dx / math.tan(math.radians(55))
        vt = max(lo_v + 0.1, min(hi_v - 0.1, vt))
        for p, rr, _ in cdots:   # keep the arrowhead off the end-on bars beside the leg
            if abs(p[1] - vt) < 0.12:
                vt = p[1] - fs * 0.15
        v.leader([(ul, vt), (xa - d * land, ra1), (xa, ra1)], bar["mark"], al_in)
        break
    if cdots:
        front = [(p, m) for p, _, m in cdots if fs * (p[1] - v_ffbw) > 0.1]
        near = [p for p, _ in front if abs(p[1] - ra2) <= 1.0] or [p for p, _ in front][:1]
        if near:
            v.leader_fan(near, (xa - d * land, ra2), _marks(m for _, m in front), al_in)
    # column B (in front of the backwall, further in): FFBW and the backwall bars
    xb = u_in + d * 1.25 * k
    rb = [v_ffbw + fs * (0.35 * k + i * 2.3 * th) for i in range(3)]
    items = []
    if bdots:
        face = min(bdots, key=lambda t: abs(t[0][1] - v_ffbw))[0][1]
        fdots = [t for t in bdots if abs(t[0][1] - face) < 0.05]
        p, r, m = min(fdots, key=lambda t: abs(d * (t[0][0] - u_in) - 1.3))
        items.append((d * (p[0] - u_in), [p], "%s (EF)" % m))
    if bshape:   # tip on the front-face bar, between the end-on verticals
        bar, pp = min(bshape, key=lambda t: abs(t[1][0][1] - v_ffbw))
        offs = sorted(d * (p[0] - u_in) for p in pp)
        lo_o, hi_o = max(offs[0], 0.0), min(offs[-1], reach)
        off = min(max(0.75, lo_o + 0.15), hi_o - 0.15)
        items.append((off, [(X(off), pp[0][1])], "%s (EF)" % bar["mark"]))
    items.append((0.5, [(X(0.5), v_ffbw)], "FFBW"))
    items.sort(key=lambda t: -t[0])          # nearest the column on the top row: no crossings
    for (_, tips, txt), y in zip(items, rb):
        v.leader([tips[0], (xb - d * land, y), (xb, y)], txt, al_in)
    # WWR in the lug: leader up behind the backwall
    for w, pp in wshapes:
        segs = [(a, c) for a, c in zip(pp, pp[1:]) if abs(c[1] - a[1]) > 0.05]
        if not segs:
            continue
        # tip on a cross wire in the lug (clear of the backwall back face), else on the wire
        tip = (segs[0][0][0], (v_bb + v_back) / 2)
        lug = [p for ps in wdots.values() for p, _ in ps
               if min(v_bb, v_back) + 0.1 < p[1] < max(v_bb, v_back) - 0.05]
        knee = (X(0.35), v_back - fs * 0.3 * k)
        if lug:   # the arrowhead just touches the "x"
            c = min(lug, key=lambda p: abs(p[1] - (v_bb + v_back) / 2))
            L = math.dist(c, knee)
            tip = (c[0] + (knee[0] - c[0]) / L * 1.3 * xe, c[1] + (knee[1] - c[1]) / L * 1.3 * xe)
        v.leader([tip, knee, (knee[0] + d * 0.12 * k, knee[1])], "WWR (SEE NOTE %d)" % wwr_note, al_in)
        break
    _title_below(v, (u_out + u_in) / 2, "SECTION %s-%s" % (letter, letter), "(THROUGH CHEEK WALL AND BACKWALL)")
    return v


# ============================================================ section flags
def cheek_cut_marks(b, cheek):
    """Where F-F and G-G cut the cheek wall, in the frame of the cheek view
    (``views.Builder.cheek_view`` maps a point p to (sgn * (p[1] - y0), p[2]),
    sgn -1 for a left cheek view): the vertical cut at x looking toward the
    slab beyond it (toward the backwall), the horizontal cut at z looking
    down."""
    s = b.s
    S = s.S
    sec = S["cheek_sections"][cheek["name"]]
    sgn = -1.0 if S["cheek_views"][cheek["name"]]["side"] == "left" else 1.0
    slab = 1.0 if s.e1 > 0 else -1.0
    return {"side": {"x": sgn * (sec["y_cut_ft"] - s.y0), "look": (sgn * slab, 0.0)},
            "top": {"z": sec["z_cut_ft"], "look": (0.0, -1.0)}}


# ================================================================ DETAIL A
def detail_construction_joint(b, zone):
    """DETAIL "A" (CONSTRUCTION JOINT), schematic (sample B1-17): the foot of
    the backwall (1'-0") on the cap, the back faces flush as in the model,
    the keyed joint (4" key in the middle third, 1/2" bevels, 1 1/2" deep),
    break lines at the cut edges.  Scale: the zone's (1 1/2" = 1'-0")."""
    v = View(b.doc, zone, "%s DETAIL A" % b.s.key)
    k = IN * v.sf
    W = 1.0
    k0, k1, off, kd = 4 * IN, 8 * IN, 0.5 * IN, 1.5 * IN
    Hw, Hc, ext = 0.6, 0.45, 0.8
    xr = W + ext
    e = 0.06 * k
    v.pl([(0, Hw), (0, -Hc)], "SubStrConc")                    # back face of backwall and cap
    v.pl([(W, Hw), (W, 0), (xr, 0)], "SubStrConc")             # front face, top of cap
    v.pl([(0, 0), (k0, 0), (k0 + off, -kd), (k1 - off, -kd), (k1, 0), (W, 0)], "SubStrConc")   # joint and key (cut, solid)
    v.break_line((-e, Hw), (W + e, Hw))
    v.break_line((xr, e), (xr, -Hc - e))
    v.break_line((-e, -Hc), (xr + e, -Hc))
    y1 = Hw + 0.3 * k
    y2 = y1 + 0.27 * k
    y3 = y2 + 0.27 * k
    v.dim((k0, 0), (k0 + off, -kd), y1, 0, outside=-1)
    v.dim((k1 - off, -kd), (k1, 0), y1 + kd, 0, outside=1)
    _chain(v, [(0, Hw), (k0, 0), (k1, 0), (W, Hw)], None, y2, vertical=False, step=0.125)
    v.dim((0, Hw), (W, Hw), y3 - Hw, 0)
    xd = W + 0.35
    v.dim((k1 - off, -kd), (xd, 0), (k1 - off) - xd, 90, outside=1)
    _title_below(v, xr / 2, 'DETAIL "A"', "(CONSTRUCTION JOINT)")
    return v


# ================================================================ DETAIL B
def detail_geotextile(b, zone, note=3):
    """DETAIL "B" (END BENT BACKWALL V-GROOVE), schematic (sample B1-17): a
    3'-0" plan segment of the backwall, 3/4" V-grooves in both faces, the
    1'-0" geotextile fabric strip on the back face over the groove and the
    fill behind it.  V-grooves are not in the CAD model (STYLE_GUIDE D7).
    The fabric is drawn on WallMSEPanel: the FDOT level table has no level
    for geotextile fabric, and the MSE wall level is the nearest (fill-side
    wall component).  Scale: the zone's (1" = 1'-0")."""
    v = View(b.doc, zone, "%s DETAIL B" % b.s.key)
    k = IN * v.sf
    L, T = 3.0, 1.0
    xm = L / 2
    gw, gd = 0.75 * IN, 0.375 * IN
    v.pl([(0, T), (xm - gw / 2, T), (xm, T - gd), (xm + gw / 2, T), (L, T)], "SubStrConc")   # back face
    v.pl([(0, 0), (xm - gw / 2, 0), (xm, gd), (xm + gw / 2, 0), (L, 0)], "SubStrConc")       # FFBW
    e = 0.06 * k
    for x in (0.0, L):
        v.break_line((x, -e), (x, T + e))
    fo = 0.014 * k
    v.pl([(xm - 0.5, T + fo), (xm + 0.5, T + fo)], "WallMSEPanel")
    # fill behind the backwall beside the fabric: two low mounds of earth
    for x0, x1 in ((0.12, xm - 0.62), (xm + 0.62, L - 0.12)):
        def top(x, x0=x0, x1=x1):
            t = (x - x0) / (x1 - x0)
            return 0.19 * math.sin(math.pi * t) ** 0.7 * (1 + 0.15 * math.sin(5.3 * math.pi * t))
        _earth(v, x0, x1, T + 0.01 * k, top)
    # labels
    _area_leader(v, (xm - 0.40, 0.42 * T), (xm - 0.68, T + 0.6), "END BENT\\PBACKWALL", "right")
    # (the label stays within the 3'-0" segment, so the detail fits the
    # narrower details column of the End Bent 2 sheet)
    v.leader([(xm + 0.25, T + fo), (xm + 0.38, T + 0.6), (xm + 0.5, T + 0.6)],
             "GEOTEXTILE FABRIC\\P(SEE NOTE %d)" % note, "left")
    v.leader([(xm - gw / 4, gd / 2), (xm - 0.3, -0.42), (xm - 0.42, -0.42)], "¾\" V-GROOVE (EF)", "right")
    v.leader([(xm + 0.62, 0), (xm + 0.72, -0.42), (xm + 0.84, -0.42)], "FFBW", "left")
    _title_below(v, xm, 'DETAIL "B"', "(END BENT BACKWALL V-GROOVE)")
    return v
