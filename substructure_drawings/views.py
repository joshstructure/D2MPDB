"""Plan, elevation, section and detail views for the bents and pier.

The views follow the formatting of FDOT structures plan sheets (sample plan
set PA-PS-0037.1, BCC Engineering, 2025):

- The elevation shows the concrete and the reinforcement together.  A bar
  series is one dimension with the count, mark and spacing in its text
  (``4~6B1 @ 9" = 2'-3"``, ``@ 9" MAX.`` where the model spacing varies);
  equal spaces read ``3 EQUAL SPA @ 4'-6" = 13'-6"``; odd end spaces are
  small separate dimensions; a value that does not fit is written beside its
  space with a short leader, never on a second row.
- Callouts sit beside the bars they name with short leaders ending in a
  horizontal landing; one callout may fan several arrows; centerlines are
  labelled with the centerline symbol by leader.
- Sections draw the concrete heavy, the bars thin: cut bars as filled dots
  at true size (SDM 4.3.7.D) and the nearest in-plane bar of each series
  within 1'-3" beyond the cut with its bends and hooks, as on the sample
  sheets; the bar layout is dimensioned in full.
- Bars not seen end-on go through ``draw_bar`` (``View.bar``): single lines
  at 3/8" (plan, elevation), double lines at the true bar width at 1/2" and
  larger (sections, cheek views, pedestal details; SDM 4.3.7.B).

Reinforcement in plan and elevation follows SDM 4.3.B/C and 4.3.1.C: only the
first and last bar of each run is drawn; stirrups use the CAD_AI symbol (a
line at the bar station with a filled dot at each end).

The rule ids in comments (A1 .. D8) are those of STYLE_GUIDE.md.
"""
import math
import re
from collections import OrderedDict

from . import bars as barlib
from . import fdot
from .cad import CL_CHAR as CL, View, text_extent
from .support import layer_for

TOL = 1.0 / 96.0  # 1/8 in, ft
IN = 1.0 / 12.0
TAN35 = math.tan(math.radians(35.0))
TAN30 = math.tan(math.radians(30.0))
DELTA = "Δ"
STRAP_LEGEND = ("REINFORCING STRAPS AND ATTACHMENTS FOR THE END BENT SHALL BE DESIGNED AND FURNISHED BY THE "
                "PROPRIETARY WALL PROVIDER. THE STRAPS SHALL BE DESIGNED TO RESIST A SERVICE LOAD OF ___ K/FT AND A "
                "FACTORED LOAD OF ___ K/FT PERPENDICULAR TO THE END BENT BACKWALL.")


# ============================================================== helpers
def draw_bar(v, pts, dia_in):
    """A bar not seen end-on (C1): ``View.bar`` draws it by the view scale,
    one line at 3/8" and double lines at the true width at 1/2" and larger;
    a plain polyline where ``View.bar`` is not available."""
    return v.bar(pts, dia_in) if hasattr(v, "bar") else v.pl(pts, "Rebar")


def _covered(a, b, segs, tol):
    """True when the segment ab lies along the union of ``segs``: both of its
    end points within ``tol`` of each covering segment's line and the
    covering segments together spanning it (it may be shorter than they)."""
    L = math.dist(a, b)
    if L <= tol:
        return True
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    ivs = []
    for p, q in segs:
        Lv = math.dist(p, q)
        if Lv < 1e-9:
            continue
        vx, vy = (q[0] - p[0]) / Lv, (q[1] - p[1]) / Lv
        if (abs((a[0] - p[0]) * vy - (a[1] - p[1]) * vx) > tol
                or abs((b[0] - p[0]) * vy - (b[1] - p[1]) * vx) > tol):
            continue
        s0 = (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
        s1 = (q[0] - a[0]) * ux + (q[1] - a[1]) * uy
        ivs.append((min(s0, s1), max(s0, s1)))
    reach = 0.0
    for lo, hi in sorted(ivs):
        if lo > reach + tol:
            break
        reach = max(reach, hi)
    return reach >= L - tol


def drop_coincident_hidden(edges, tol=0.004):
    """D1: the hidden-line projection returns hidden edges (backwall, pedestal
    and pad bottoms) lying exactly along visible edges (the cap top); a
    dashed line over a solid one tells the reader nothing.  Every hidden
    line or polyline record whose every segment lies along visible
    segments (within ``tol`` ft) is dropped; hidden geometry that reveals
    something (the cap end behind a cheek wall, hidden pad edges) stays."""
    vis = []
    for r in edges:
        if r["vis"] and r["t"] in ("L", "P"):
            pts = [tuple(p) for p in r["p"]]
            vis += list(zip(pts, pts[1:]))
    if not vis:
        return list(edges)
    out = []
    for r in edges:
        if not r["vis"] and r["t"] in ("L", "P"):
            pts = [tuple(p) for p in r["p"]]
            if all(_covered(a, b, vis, tol) for a, b in zip(pts, pts[1:])):
                continue
        out.append(r)
    return out


def cut_out(edges, z, x0, x1, tol=0.004):
    """Edge records with the horizontal pieces at level ``z`` between x0 and
    x1 removed: the keyway of a construction joint is drawn there instead
    (STYLE_GUIDE D5)."""
    out = []
    for rec in edges:
        if rec["t"] == "L" and abs(rec["p"][0][1] - z) < tol and abs(rec["p"][1][1] - z) < tol:
            a, b = sorted((rec["p"][0][0], rec["p"][1][0]))
            if b <= x0 + tol or a >= x1 - tol:
                out.append(rec)
                continue
            if a < x0 - tol:
                out.append(dict(rec, p=[[a, rec["p"][0][1]], [x0, rec["p"][0][1]]]))
            if b > x1 + tol:
                out.append(dict(rec, p=[[x1, rec["p"][0][1]], [b, rec["p"][0][1]]]))
            continue
        out.append(rec)
    return out


def draw_edges(view, edges, box=None, hidden=True, roles=None, skip_roles=()):
    edges = [r for r in edges if (hidden or r["vis"]) and (not roles or r["role"] in roles)
             and r["role"] not in skip_roles]
    if hidden:
        edges = drop_coincident_hidden(edges)
    for rec in edges:
        layer, lt = layer_for(rec)
        view.record(rec, layer, lt, box)


def horiz_end(pts, side, inset=0.05):
    """Point on the longest horizontal run of a bar (local 2D points),
    ``inset`` inside its end toward ``side`` (+1: the right end)."""
    best = None
    for a, b in zip(pts, pts[1:]):
        dx = abs(b[0] - a[0])
        if dx > 1e-6 and abs(b[1] - a[1]) <= 0.02 * dx and (best is None or dx > best[0]):
            best = (dx, a, b)
    if best is None:
        q = max(pts, key=lambda p: side * p[0])
        return (q[0] - side * inset, q[1])
    _, a, b = best
    x = max(a[0], b[0]) if side > 0 else min(a[0], b[0])
    return (x - side * inset, (a[1] + b[1]) / 2)


def leader_above(v, pts, text, align):
    """Leader whose landing lines up with the LAST line of a multi-line text,
    so the text stands above the landing (the BEGIN BRIDGE / FFBW / STA.
    block, sample B1-15)."""
    pts = list(pts)
    k = IN * v.sf
    if abs(pts[-1][1] - pts[-2][1]) > 1e-6:
        pts.append((pts[-1][0] + (0.12 * k if align == "left" else -0.12 * k), pts[-1][1]))
    v.arrowhead(pts[0], pts[1], "Leader")
    v.pl(pts, "Leader")
    end = pts[-1]
    x = end[0] + 0.4 * v.th if align == "left" else end[0] - 0.4 * v.th
    return v.mtext((x, end[1] - 0.5 * v.th), text, v.th, attach=7 if align == "left" else 9)


def edge_points(rec):
    if rec["t"] in ("L", "P", "A"):
        return [tuple(p) for p in rec["p"]]
    c, r = rec["c"], rec["r"]
    return [(c[0] + r * math.cos(a), c[1] + r * math.sin(a)) for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]


def extents(edges, roles=None):
    pts = [p for r in edges if roles is None or r["role"] in roles for p in edge_points(r)]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def z_on_edges(edges, role, u, tol=0.02):
    """Highest z of the role's visible edges at local x = u (elevation views)."""
    best = None
    for rec in edges:
        if rec["role"] != role or not rec["vis"]:
            continue
        pts = edge_points(rec)
        for a, b in zip(pts, pts[1:]):
            lo, hi = sorted((a[0], b[0]))
            if lo - tol <= u <= hi + tol:
                if abs(b[0] - a[0]) < 1e-9:
                    z = max(a[1], b[1])
                else:
                    t = (u - a[0]) / (b[0] - a[0])
                    z = a[1] + max(0.0, min(1.0, t)) * (b[1] - a[1])
                best = z if best is None else max(best, z)
    return best


def proj(bar, fn):
    return [fn(p) for p in bar["pts"]]


def series_split(us):
    """Split sorted positions into maximal runs of uniform spacing (+-1/8 in)."""
    if len(us) < 2:
        return [list(us)]
    out, cur = [], [us[0], us[1]]
    for u in us[2:]:
        if abs((u - cur[-1]) - (cur[1] - cur[0])) <= TOL:
            cur.append(u)
        else:
            out.append(cur)
            cur = [cur[-1], u]
    out.append(cur)
    return out


def mark_list(marks):
    """Marks named by one callout: 5E26/5E27, or 10E04 THRU 10E07 for three
    or more consecutive designations (FDOT sheets)."""
    marks = list(OrderedDict.fromkeys(marks))
    if len(marks) >= 3:
        parsed = [re.match(r"^(\d+)([A-Z])(\d+)$", m) for m in marks]
        if all(parsed) and len({p.group(2) for p in parsed}) == 1:
            nums = [int(p.group(3)) for p in parsed]
            if nums == list(range(nums[0], nums[0] + len(nums))):
                return "%s THRU %s" % (marks[0], marks[-1])
    return "/".join(marks)


def spaces_text(us, step=0.25):
    """'4 SPA. @ 7 3/4"' when the rounded spacing adds up, else
    '6 EQ. SPA. = 3'-8"'; one space is its plain value."""
    n = len(us) - 1
    total = us[-1] - us[0]
    if n == 1:
        return fdot.ft_in(total, step)
    s = total / n
    if abs(float(fdot.round_in(s * 12, step)) * n - total * 12) <= 1 / 16:
        return "%d SPA. @ %s" % (n, fdot.ft_in(s, step))
    return "%d EQ. SPA. = %s" % (n, fdot.ft_in(total, 0.125))


def series_text(us, mark, count=None, ef=False, step=0.25):
    """One bar series: '13~6E29 @ 4'-0" = 48'-0"' (uniform),
    '5~4E31 @ EQ. SPA. = 3'-4"' or '4~6B1 @ 9" MAX.' (model spacing varies)."""
    lab = "%d~%s%s" % (count or len(us), mark, " (EF)" if ef else "")
    sp = [b - a for a, b in zip(us, us[1:])]
    if not sp:
        return lab
    total = us[-1] - us[0]
    if max(sp) - min(sp) <= TOL:
        s = total / len(sp)
        if abs(float(fdot.round_in(s * 12, step)) * len(sp) - total * 12) <= 1 / 16:
            return "%s @ %s = %s" % (lab, fdot.ft_in(s, step), fdot.ft_in(total, 0.125))
        return "%s @ EQ. SPA. = %s" % (lab, fdot.ft_in(total, 0.125))
    return "%s @ %s MAX." % (lab, fdot.ft_in(max(sp), step))


def run_chain(runs, ends):
    """Dimension string over bar runs [(positions, text)]: each run is one
    dimension; the spaces between runs and at the ends are plain values."""
    xs, texts = [ends[0]], []
    for us, txt in runs:
        if abs(us[0] - xs[-1]) > 1e-9:
            xs.append(us[0])
            texts.append(None)
        if len(us) > 1:
            xs.append(us[-1])
            texts.append(txt)
    if abs(ends[1] - xs[-1]) > 1e-9:
        xs.append(ends[1])
        texts.append(None)
    return xs, texts


def equal_chain(pos, ends, step=0.125):
    """Spacing row of piles or beams: uniform runs of two or more spaces read
    'n EQUAL SPA @ s = total' with the end spaces as separate values."""
    xs, texts = [ends[0]], []
    for ser in series_split(sorted(pos)):
        if abs(ser[0] - xs[-1]) > 1e-9:
            xs.append(ser[0])
            texts.append(None)
        if len(ser) > 2:
            n = len(ser) - 1
            tot = ser[-1] - ser[0]
            texts.append("%d EQUAL SPA @ %s = %s" % (n, fdot.ft_in(tot / n, step), fdot.ft_in(tot, step)))
            xs.append(ser[-1])
        elif len(ser) == 2:
            xs.append(ser[-1])
            texts.append(None)
    if abs(ends[1] - xs[-1]) > 1e-9:
        xs.append(ends[1])
        texts.append(None)
    return xs, texts


def text_w(v, txt):
    return max(text_extent(x, v.th) for x in txt.split("\\P"))


def chain_dims(v, xs, texts, y_obj, y_dim, vertical=False, step=0.25):
    """One row of dimensions.  A long series text that does not fit on one
    line is broken before '@'; a value that still does not fit its space is
    written beside it with a short leader, in the free half of the
    neighbouring space or beyond the end of the row, or else just below the
    row; values are never stacked on a second row.

    ``y_obj`` is the object coordinate of the points (y of a horizontal row,
    x of a vertical one): one value for all, or a list with one per point
    of ``xs``, so each extension line runs to its own feature (B3)."""
    pad = 0.12 * IN * v.sf
    yo = list(y_obj) if isinstance(y_obj, (list, tuple)) else [y_obj] * len(xs)
    segs = []
    for i in range(len(xs) - 1):
        a, b = xs[i], xs[i + 1]
        if abs(b - a) < 1.0 / 192:   # under 1/16 in: no dimension
            continue
        txt = texts[i] if texts and i < len(texts) and texts[i] else fdot.ft_in(abs(b - a), step)
        if text_w(v, txt) + pad > abs(b - a) and " @ " in txt:
            two = txt.replace(" @ ", "\\P@ ", 1)
            if text_w(v, two) + pad < abs(b - a):
                txt = two
        segs.append((a, b, txt, yo[i], yo[i + 1]))
    fits = [text_w(v, t) + pad < abs(b - a) for a, b, t, _, _ in segs]
    room = [[(abs(b - a) - text_w(v, t)) / 2 - pad] * 2 if f else [0.0, 0.0]
            for (a, b, t, _, _), f in zip(segs, fits)]
    n = len(segs)
    # the tallest in-place text of the row, which pulled-out values must clear (B7)
    row_lines = max([t.count("\\P") + 1 for (_, _, t, _, _), f in zip(segs, fits) if f] or [1])
    outs = [None] * n
    pulled = []   # (i, mid, half width of the box) of the values pulled out beside the row
    for i, (a, b, txt, oa, ob) in enumerate(segs):
        if fits[i]:
            continue
        need = text_w(v, txt) + (fdot.ARROW_IN + 0.1) * IN * v.sf
        if i == 0 and (n == 1 or not (fits[1] and room[1][0] > need)):
            outs[i] = -1
        elif i == n - 1 and not (fits[i - 1] and room[i - 1][1] > need):
            outs[i] = 1
        elif i + 1 < n and fits[i + 1] and room[i + 1][0] > need:
            outs[i], room[i + 1][0] = 1, room[i + 1][0] - need
        elif i > 0 and fits[i - 1] and room[i - 1][1] > need:
            outs[i], room[i - 1][1] = -1, room[i - 1][1] - need
        else:
            outs[i] = 0
            pulled.append((i, (a + b) / 2, text_w(v, txt) / 2 + 0.6 * v.th))
    # B7: the values pulled out beside the row sit at one level in row order.
    # Each starts over the middle of its space; where two would overlap, the
    # earlier slides back along the row as far as its own space stays under
    # it (its pointer then drops square to the row) before the later one is
    # pushed on (a two-piece pointer once its space is no longer under it).
    shifts = {}
    if pulled:
        pulled.sort(key=lambda t: t[1])
        mg = 0.35 * v.th
        c = [m for _, m, _ in pulled]
        lo = [m - max(hw - mg, 0.0) for _, m, hw in pulled]
        hws = [hw for _, _, hw in pulled]
        for _ in range(4 * len(pulled)):
            moved = False
            for j in range(1, len(pulled)):
                need = (c[j - 1] + hws[j - 1]) - (c[j] - hws[j])
                if need <= 1e-9:
                    continue
                back = min(need, c[j - 1] - lo[j - 1])
                c[j - 1] -= back
                c[j] += need - back
                moved = True
            if not moved:
                break
        shifts = {i: ci - m for (i, m, _), ci in zip(pulled, c)}
    for i, (a, b, txt, oa, ob) in enumerate(segs):
        shift = shifts.get(i, 0.0)   # along the row axis (x of a horizontal row, y of a vertical one)
        if vertical:
            v.dim((oa, a), (ob, b), -(y_dim - oa), 90, txt, outside=outs[i], row_lines=row_lines, shift=shift)
        else:
            v.dim((a, oa), (b, ob), y_dim - oa, 0, txt, outside=outs[i], row_lines=row_lines, shift=shift)


def callouts(v, items, x_col, side, gap=None, slide=False):
    """Callouts beside the bars: items = [(tips, text)] (local coords), or
    (tips, text, y) for a label whose row should be at y (the PT. labels in
    the same column).  The texts start at x_col (side +1: text to the
    right, -1: to the left), at the height of their bars as far as spacing
    allows; several tips fan from one knee.

    ``slide`` (A3): the tips of (tips, text) items lie on horizontal bars,
    given at the bar end nearest the text column, and slide inward along
    the bars so that each leader meets its bar at 35 degrees (30 at the
    least where the bar end is far from the knee); a row too close to its
    bar for that is moved up off it and the rows above are re-spaced.  The
    leaders then never run along the bars they point to."""
    if not items:
        return
    th, k = v.th, IN * v.sf
    gap = gap or 2.1 * th
    land = 0.14 * k
    xk = x_col - side * land          # knee x
    dx_min = 0.12 * k                 # shortest horizontal run of a sliding leader
    rows = []
    for it in items:
        tips, txt = list(it[0]), it[1]
        fixed = len(it) > 2
        want = it[2] if fixed else sum(t[1] for t in tips) / len(tips)
        need = []
        if slide and not fixed:
            for t in tips:
                reach = max(dx_min, side * (xk - t[0]))
                need.append(max(0.8 * th, reach * TAN30))
        rows.append({"tips": tips, "txt": txt, "want": want, "need": need,
                     "h": (1 + txt.count("\\P") * fdot.LINE_PITCH) * th})
    rows.sort(key=lambda r: r["want"])

    def pitch(a, b):
        return max(gap, (a["h"] + b["h"]) / 2 + 0.6 * th)

    def ok(r, y):
        return all(abs(y - t[1]) >= n - 1e-9 for t, n in zip(r["tips"], r["need"]))

    def lift(r, y):
        """Lowest height at or above y where every leader of the row meets
        its bar steeply enough."""
        if ok(r, y):
            return y
        for c in sorted(t[1] + n for t, n in zip(r["tips"], r["need"])):
            if c >= y and ok(r, c):
                return c
        return max(t[1] + n for t, n in zip(r["tips"], r["need"]))

    ys = []
    if slide:
        for i, r in enumerate(rows):
            y = r["want"] if not ys else max(r["want"], ys[-1] + pitch(rows[i - 1], r))
            ys.append(lift(r, y))
    else:
        for i, r in enumerate(rows):
            ys.append(r["want"] if not ys else max(r["want"], ys[-1] + pitch(rows[i - 1], r)))
        shift = (sum(r["want"] for r in rows) - sum(ys)) / len(ys)
        ys = [y + shift for y in ys]
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + pitch(rows[i - 1], rows[i]))
    al = "left" if side > 0 else "right"
    for r, y in zip(rows, ys):
        knee = (xk, y)
        tips = r["tips"]
        if r["need"]:
            # 35 degrees for the nearest bar; the leaders of a fan spread to
            # 60 degrees for the farthest, so they part from the knee instead
            # of lining up on one line
            n = len(tips)
            rank = sorted(range(n), key=lambda i: abs(y - tips[i][1]))
            slid = list(tips)
            for j, i in enumerate(rank):
                t = tips[i]
                tan = math.tan(math.radians(35.0 + (25.0 * j / (n - 1) if n > 1 else 0.0)))
                slid[i] = (xk - side * max(dx_min, abs(y - t[1]) / tan, side * (xk - t[0])), t[1])
            tips = slid
        if len(tips) == 1:
            v.leader([tips[0], knee, (x_col, y)], r["txt"], al)
        else:
            v.leader_fan(tips, knee, r["txt"], al)


# ====================================================================
class Builder:
    """Draws the views of one support."""

    def __init__(self, sup, doc):
        self.s = sup
        self.doc = doc
        self.notes = []
        self.legend = OrderedDict()
        self.elev_points = sup.elevation_points()
        if sup.kind == "EB":
            crown = z_on_edges(sup.S["elev"], "backwall", 0.0)
            self.elev_points = [(l, d, (0.0 if "PGL" in d else u), (crown if "PGL" in d and crown else z))
                                for l, d, u, z in self.elev_points]

    def span_side(self, bearing):
        """Unit plan direction (v) from the cap toward the span of a bearing."""
        s = self.s
        if s.kind == "EB":
            return -1.0  # span (bridge) side is toward the bottom of the bent plan
        return -1.0 if bearing["v"] < 0 else 1.0

    def cl_name(self):
        return ("CAP & %s PILES" % CL) if self.s.kind == "EB" else ("PIER & %s PILES" % CL)

    # ------------------------------------------------------------ plan
    def plan_points(self):
        """Plan positions of the lettered elevation points that have one (A4):
        cheek wall tops at the cheek centre, backwall top at the ends and at
        the PGL on the FFBW, cap top at the ends on the cap centreline.  The
        bottoms of cap, cheek lug and pier wall have none."""
        s = self.s
        out = []
        v_cl = s.piles[0]["v"] if s.kind == "EB" else 0.0
        v_ch = None
        if s.kind == "EB":
            cv = extents(s.S["plan"], ("cheek",))
            v_ch = (cv[1] + cv[3]) / 2
        for letter, desc, u, z in self.elev_points:
            if desc.startswith("TOP OF CHEEK WALL"):
                c = min(s.cheeks, key=lambda c: abs(c["u"] - u))
                out.append((letter, desc, (c["u"], v_ch)))
            elif desc.startswith("TOP OF BACKWALL AT PGL"):
                out.append((letter, desc, (0.0, s.ffbw_v)))
            elif desc.startswith("TOP OF BACKWALL AT END"):
                out.append((letter, desc, (u, s.ffbw_v)))
            elif desc.startswith("TOP OF CAP AT END"):
                out.append((letter, desc, (u, v_cl)))
        return out

    def plan(self, zone):
        """Plan (sample B1-15): above the plan the PT. labels, FFBW and the
        BEGIN BRIDGE / FFBW / STA. block right of the PGL with its leader to
        the FFBW/PGL crossing, then the dimension rows; below the cap the
        skew angle and the CL BEAM labels between the beam lines, then the
        beam and pile spacing rows; the centerline labels at the right end
        and the direction of stationing beyond them."""
        s = self.s
        S = s.S
        v = View(self.doc, zone, s.key + " PLAN")
        draw_edges(v, S["plan"])
        th, k = v.th, IN * v.sf
        eb = s.kind == "EB"
        u0, u1 = s.cap_u
        uL, uR = s.outer_u
        vf, vb = s.cap_v
        ex = extents(S["plan"])
        v_top, v_bot = ex[3], ex[1]
        v_cl = s.piles[0]["v"] if eb else 0.0
        # context around the bent (D-044/D-045): the weather closure slab and
        # copings in front of the cap and beside/behind the cheeks, and the
        # soil reinforcing straps as 6" stubs out of the back face (their
        # layout is called out above the plan); visible edges, clipped
        ctx = [r for r in S.get("plan_context", []) if r["vis"]]
        # (the slab fully and the start of the front coping, 2.2 ft in front of
        # the cap; the side copings beside the cheeks; 4" stubs of the copings
        # behind the cheeks and of the straps, under the label rows: sheet room)
        ctx_boxes = {"closure": (uL - 1.5, vf - 1.5, uR + 1.5, vb + 0.3),
                     "coping": (uL - 1.5, vf - 1.5, uR + 1.5, vb + 0.3),
                     "strap": (uL, vb - 0.01, uR, vb + 0.3)}
        cx_lo = v_bot
        for role, cb in ctx_boxes.items():
            recs = [r for r in ctx if r["role"] == role]
            if recs:
                draw_edges(v, recs, box=cb, hidden=False)
                cx_lo = min(cx_lo, max(extents(recs)[1], cb[1]))
        v_bot = min(v_bot, cx_lo)
        # bands beside the cap: row a nearer the cap (PT. labels, skew angle),
        # row b (beam labels); the beam centerlines end just beyond row b,
        # where the spacing rows begin (A1, A2)
        row_a, row_b, beam_ext = 0.15 * k, 0.33 * k, 0.45 * k
        sides = {self.span_side(b) for b in s.bearings}
        v_span_lo = min(vf, min(b["v"] for b in s.bearings)) - (beam_ext if -1 in sides else 0.0)
        v_span_hi = max(vb, max(b["v"] for b in s.bearings)) + (beam_ext if 1 in sides else 0.0)
        y_lo, y_hi = min(v_bot, v_span_lo), max(v_top, v_span_hi)
        ext = 0.25 * k
        if ctx:
            # labels of the closure slab and the front coping, right of the cap
            # end below the cap (the centerline labels are above, in the cap)
            clos = [r for r in ctx if r["role"] == "closure"]
            cops = [r for r in ctx if r["role"] == "coping" and extents([r])[3] < vf]
            for recs, txt, dv in ((clos, "4\" CLOSURE SLAB", 0.0), (cops, "COPING", 0.0)):
                if not recs:
                    continue
                ce = extents(recs)
                vm = (ce[1] + ce[3]) / 2
                tip = (u1 - 0.8, vm)
                knee = (uR + 0.2 * k, vm - 0.1 * k)
                v.leader([tip, knee, (knee[0] + 0.12 * k, knee[1])], txt, "left")
        # -------------------------------------------- centerlines and beams
        v.line((uL - ext, v_cl), (uR + ext, v_cl), "CL_Major")
        for p in s.piles:
            h = p["width"] / 2 + 0.3
            v.line((p["u"], p["v"] - h), (p["u"], p["v"] + h), "CL_Minor")
        labels = [(v_cl, self.cl_name())]
        for b in s.bearings:
            v.line((uL - ext, b["v"]), (uR + ext, b["v"]), "CL_Minor")
            labels.append((b["v"], "BEARING"))
        labels.sort(key=lambda t: t[0])
        xt = uR + 0.5 * ext
        x_lab = xt   # right end of the centerline label texts
        for i, (yy, txt) in enumerate(labels):
            d = 0.0 if len(labels) == 3 and i == 1 else (-1.0 if i == 0 else 1.0)
            knee = (xt + 0.22 * k, yy + d * 0.22 * k)
            v.leader([(xt, yy), knee, (knee[0] + 0.12 * k, knee[1])], txt, "left", cl=True)
            x_lab = max(x_lab, knee[0] + 0.12 * k + 0.4 * th + text_extent(CL + " " + txt, th))
        # beam centerlines toward their spans; CL BEAM labels between the beam
        # lines in row b, each leader turned toward the PGL (sample B1-15)
        for b in s.bearings:
            d = self.span_side(b)
            end = v_span_lo if d < 0 else v_span_hi
            face = vf if d < 0 else vb
            for bl in s.beam_lines:
                v.line((bl["u"], b["v"]), (bl["u"], end), "CL_Minor")
                g = -1 if bl["u"] > 0 else 1
                tip = (bl["u"], face + d * 0.1 * k)
                knee = (bl["u"] + g * 0.12 * k, face + d * row_b)
                v.leader([tip, knee, (knee[0] + g * 0.12 * k, knee[1])], "BEAM " + s.beam_id(b["span"], bl["line"]),
                         "left" if g > 0 else "right", cl=True)
        # complementary skew angle (SDM 2.14): 90 degrees, typical; the arc in
        # the quadrant facing the PGL, the label in row a toward the PGL (A1)
        b0, bl0 = s.bearings[0], s.beam_lines[0]
        d0 = self.span_side(b0)
        g = -1 if bl0["u"] > 0 else 1
        lo, hi = sorted((0.0 if g > 0 else 180.0, 270.0 if d0 < 0 else 90.0))
        if hi - lo > 180:
            lo, hi = hi, lo + 360.0
        c0 = (bl0["u"], b0["v"])
        v.arc(c0, 0.45, lo, hi, "Dimension")
        am = math.radians((lo + hi) / 2)
        tip = (c0[0] + 0.45 * math.cos(am), c0[1] + 0.45 * math.sin(am))
        knee = (tip[0] + g * 0.12 * k, (vf if d0 < 0 else vb) + d0 * row_a)
        v.leader([tip, knee, (knee[0] + g * 0.12 * k, knee[1])], "90°00'00\" (TYP.)", "left" if g > 0 else "right")
        # ------------------------------------------- above the plan (A2, A4)
        # row r1 just above the backwall (EB) or the beam line ends (pier):
        # PT. labels, FFBW, the bottom line of the station block; row r2 the
        # cheek wall PT. labels
        y_r1 = (vb + 0.2 * k) if eb else (y_hi + 0.2 * k)
        y_r2 = y_r1 + 0.17 * k
        if eb:
            what = "BEGIN BRIDGE" if s.key == "EB1" else "END BRIDGE"
            block = "%s\\PFFBW %s\\PSTA. %s" % (what, s.title, fdot.station(s.station(s.ffbw_y)))
            cross = (0.0, s.ffbw_v)
            uf = u0 + 0.85 * k
            v.leader([(uf, s.ffbw_v), (uf + 0.15 * k, y_r1), (uf + 0.27 * k, y_r1)], "FFBW", "left")
        else:
            block = "%s PIER\\PSTA. %s" % (CL, fdot.station(s.station(s.y0)))
            cross = (0.0, 0.0)
        knee = (0.22 * k, y_r1)
        leader_above(v, [cross, knee, (knee[0] + 0.12 * k, y_r1)], block, "left")
        y_pgl = y_r1 + block.count("\\P") * fdot.LINE_PITCH * th + 0.5 * th   # top of the block
        for letter, desc, q in self.plan_points():
            g = 1 if q[0] < 0 else -1          # inward, toward the PGL
            if "AT PGL" in desc:
                g, knee = -1, (-0.22 * k, y_r1)
            elif "BACKWALL AT END" in desc:
                knee = (q[0] + g * 0.25 * k, y_r1)
            elif "CHEEK WALL" in desc:
                # the leader leaves the cheek through its inner face below the
                # cheek top, clear of the extension line there (B3)
                knee = ((u0 if g > 0 else u1) + g * 0.12 * k, y_r2)
            elif eb:                           # cap top at the ends: below the cap
                knee = (q[0] + g * 0.2 * k, vf - row_a)
            else:                              # pier: above the cap
                knee = (q[0] + g * 0.2 * k, vb + row_a)
            v.leader([q, knee, (knee[0] + g * 0.12 * k, knee[1])], "PT. " + letter, "left" if g > 0 else "right")
        # the soil reinforcing straps (D-045): count and spacing from the model
        # strap references, called out in row r3 left of the PGL (A1, A2)
        st = sorted(s.u((c["bb_ft"][0] + c["bb_ft"][3]) / 2) for c in S["context"].values() if c["role"] == "strap")
        if st and eb:
            us = sorted(st)
            txt = series_text(us, DELTA + " REINF. STRAPS", step=0.0625).split(" = ")[0]
            # from the strap nearest the PGL on its left, in row r3, the text
            # running left between the extension lines at the PGL and at the
            # cap end (A1)
            u_s = max(u for u in us if u < -0.5) if any(u < -0.5 for u in us) else us[0]
            knee = (u_s - 0.12 * k, y_r2 + 0.17 * k)
            v.leader([(u_s, vb + 0.25), knee, (knee[0] - 0.12 * k, knee[1])], txt, "right")
        # PGL (A1: kept out of the spacing rows below the beam lines)
        v.line((0, y_lo), (0, y_pgl), "BaseLineSurveyPGL")
        v.text((-0.4 * th, y_pgl - 0.6 * th), "PGL", None, "MIDDLE_RIGHT")
        # ---------------------------------------------------- dimensions
        # B3: the points of each row sit on the features dimensioned
        y1 = y_pgl + 0.12 * k
        y2 = y1 + 0.28 * k
        if eb:
            chain_dims(v, [uL, u0, 0.0, u1, uR], None, [v_top, v_top, y_pgl, v_top, v_top], y1, step=0.125)
            v.dim((uL, v_top), (uR, v_top), y2 - v_top)
        else:
            chain_dims(v, [u0, 0.0, u1], None, [vb, y_pgl, vb], y1, step=0.125)
            v.dim((u0, vb), (u1, vb), y2 - vb)
        sp = "*"
        self.legend[sp] = "DIMENSIONS MEASURED ALONG " + ("FFBW" if eb else CL + " PIER")
        # the spacing rows start just below the beam centerlines, and below a
        # transverse value pulled out beyond the cap face (pier: 1'-1½")
        if eb:
            ys_t = sorted({round(vf, 6), round(vb, 6), round(s.ffbw_v, 6), round(s.bearings[0]["v"], 6),
                           round(v_cl, 6)})
        else:
            ys_t = sorted({round(vf, 6), round(vb, 6), 0.0} | {round(b["v"], 6) for b in s.bearings})
        tw0 = text_w(v, fdot.ft_in(ys_t[1] - ys_t[0], 0.125))
        low_t = ys_t[0] - ((fdot.ARROW_IN + 0.06) * k + tw0) if tw0 + 0.12 * k > ys_t[1] - ys_t[0] else ys_t[0]
        yb1 = min(y_lo - 0.22 * k, low_t - 0.2 * k)   # the row's text band clears the lowest linework (A1)
        yb2 = yb1 - 0.28 * k
        # pile spacing first (its extension lines come from inside the cap and
        # would cross the beam spacing texts), beam spacing below it (A1)
        pile_end = [(p["u"], p["v"] - (p["width"] / 2 + 0.3)) for p in s.piles]
        xs, texts = equal_chain([p["u"] for p in s.piles], (u0, u1))
        yo = [next((e for u, e in pile_end if abs(x - u) < 1e-6), vf) for x in xs]
        chain_dims(v, xs, texts, yo, yb1, step=0.125)
        v.row_label(uL - 0.1 * k, yb1, "PILE SPACING " + sp)
        beam_us = [bl["u"] for bl in s.beam_lines]
        xs, texts = equal_chain(beam_us, (u0, u1))
        yo = [v_span_lo if any(abs(x - u) < 1e-6 for u in beam_us) else vf for x in xs]
        chain_dims(v, xs, texts, yo, yb2, step=0.125)
        v.row_label(uL - 0.1 * k, yb2, "BEAM SPACING " + sp)
        # transverse dimensions on the left; centerlines measured from their ends
        xl1 = uL - 0.45 * k
        xl2 = xl1 - 0.6 * k    # B8: room for values pulled out of the first column
        cl_vs = [v_cl] + [b["v"] for b in s.bearings]
        xo = [uL - ext if any(abs(y - c) < 1e-5 for c in cl_vs) else uL for y in ys_t]
        chain_dims(v, ys_t, None, xo, xl1, vertical=True, step=0.125)
        if eb:
            cv = extents(S["plan"], ("cheek",))
            chain_dims(v, sorted({round(cv[1], 6), round(vf, 6), round(vb, 6), round(cv[3], 6)}), None, uL, xl2,
                       vertical=True, step=0.125)
            # section flags clear of the extension lines at the cheek ends and
            # at the outer cheek faces (the wedge reaches 0.36" from the tick)
            for c, lab in zip(s.cheeks, ("D", "E")):
                look = (1, 0) if c["side"] == "left" else (-1, 0)
                xc = (c["u_lo"] - 0.4 * k) if c["side"] == "left" else (c["u_hi"] + 0.4 * k)
                v.section_cut((xc, cv[1] - 0.3 * k), (xc, cv[3] + 0.3 * k), lab, look)
        else:
            v.dim((uL, vf), (uL, vb), -(xl2 - uL), 90)
            # end view D-D looks along +X (global), i.e. toward -u in this plan
            look = (1, 0) if s.e1 > 0 else (-1, 0)
            xc = (uL - 0.4 * k) if look[0] > 0 else (uR + 0.4 * k)   # the wedge clear of the cap end
            v.section_cut((xc, vf - 0.15 * k), (xc, vb + 0.15 * k), "D", look)
        # direction of stationing (stations increase toward -Y), right of the
        # centerline labels and vertically centred on the plan (A5, A7); its
        # text stands left of the arrow line
        sd = -s.up
        L = 1.5
        xa = x_lab + 0.35 * k + 1.45 * th
        ym = (v_top + v_bot) / 2
        v.stationing_arrow((xa, ym - sd * L * k / 2), (0, sd), L)
        v.title((0, yb2 - 0.38 * k), "PLAN")
        return v

    # ------------------------------------------------------- elevation
    def _broken(self, v, edges, z_break):
        """Broken view: the band z_lo..z_hi is removed and the part below is
        raised to leave ``gap``; nothing below z_clip is drawn."""
        z_hi, z_lo, gap, z_clip = z_break
        shift = (z_hi - z_lo) - gap
        v.xform = lambda p: (p[0], p[1] + shift) if p[1] <= z_lo + 1e-9 else p
        for rec in drop_coincident_hidden(edges):
            layer, lt = layer_for(rec)
            v.record(rec, layer, lt, (-1e4, z_hi, 1e4, 1e4))
            v.record(rec, layer, lt, (-1e4, z_clip, 1e4, z_lo))

    @staticmethod
    def _break_lines(v, z_break, x0, x1):
        """Break symbols at both edges of the removed band, in drawn position."""
        z_hi, z_lo, gap, _ = z_break
        keep, v.xform = v.xform, None
        v.break_line((x0, z_hi), (x1, z_hi))
        v.break_line((x0, z_hi - gap), (x1, z_hi - gap))
        v.xform = keep

    def elevation(self, zone, z_break=None, pile_show=0.7):
        """Elevation with the concrete and the reinforcement (FDOT sheets).
        ``pile_show`` (unbroken views): pile length drawn below the cap, enough
        for the embedment value between the cap and the pile numbers."""
        s = self.s
        S = s.S
        v = View(self.doc, zone, s.key + " ELEVATION")
        th, k = v.th, IN * v.sf
        z_pile = s.cap_bot - pile_show if not z_break else z_break[3]
        if z_break:
            self._broken(v, S["elev"], z_break)
        else:
            for rec in drop_coincident_hidden(S["elev"]):
                layer, lt = layer_for(rec)
                v.record(rec, layer, lt, (-1e4, z_pile, 1e4, 1e4))
        T = v.xform or (lambda p: p)
        u0, u1 = s.cap_u
        uL, uR = s.outer_u
        zp = T((0, z_pile))[1]
        keep, v.xform = v.xform, None
        # piles: curved break, centerline through, circled number beside the bottom
        for p in s.piles:
            w = p["width"]
            v.pile_break(p["u"], zp, w, p["shape"], "PileSteel" if p["shape"] == "pipe" else "PileConc")
            v.line((p["u"], s.cap_bot + 0.6), (p["u"], zp - 0.12 * k), "CL_Minor")
            if z_break:   # pier: beside the pile bottom (the end bent numbers go under the stirrup row)
                v.circled_number((p["u"] + w / 2 + 0.16 * k, zp + 0.1 * k), p["no"])
        v.xform = keep
        if z_break:
            self._break_lines(v, z_break, s.wall_u[0] - 0.5, s.wall_u[1] + 0.5)
        z_top = extents(S["elev"])[3]
        z_pgl = (max(t[1] for t in s.backwall_top) + 0.48 * k) if s.kind == "EB" else s.cap_top + 0.9
        # the PGL stops at the cap bottom, leaving the space below the cap to
        # the pile embedment value (A1)
        v.line((0, s.cap_bot), (0, z_pgl), "BaseLineSurveyPGL")
        v.text((0.25 * th, z_pgl), "PGL", None, "BOTTOM_LEFT")
        # elevation points (values in the table of elevations); the labels
        # right of the right end join the bar callouts there (one column)
        z_tops = z_top - 0.05
        self._right_pts = []
        for letter, desc, u, z in self.elev_points:
            side = 1 if u >= 0 else -1
            # backwall ends and cap bottoms point inward, clear of the cheek
            # labels; the end bent's right cap bottom points outward, clear of
            # the circled pile number (A8)
            # (the pier has no cheek labels: its cap bottoms point outward, off
            # the hidden pile lines inside the wall, A1)
            inward = "BACKWALL AT END" in desc or ("BOTTOM OF CAP" in desc and s.kind == "EB" and side < 0)
            if inward:
                side = -side
            q = T((u, z))
            al = "left" if side > 0 else "right"
            if "PGL" in desc:   # low and to the right, under the section flags
                v.leader([q, (q[0] + 0.35 * k, q[1] + 0.12 * k)], "PT. " + letter, "left")
                continue
            if z >= z_tops:
                dx, dz = 0.22 * k, 0.12 * k
            elif z >= s.cap_top - 0.01:
                dx, dz = 0.25 * k, 0.25 * k
            elif z < s.cap_bot - 0.01:   # cheek lug bottom: nearly level, clear of the pile labels
                dx, dz = 0.25 * k, -0.08 * k
            else:
                # cap bottom: a short run, so an inward label stops before the
                # hidden pile lines (A1)
                dx, dz = (0.15 * k if inward else 0.25 * k), -0.25 * k
            if side > 0 and not inward and z >= s.cap_bot - 1.0:
                self._right_pts.append(([q], "PT. " + letter, q[1] + dz))
                continue
            v.leader([q, (q[0] + side * dx, q[1] + dz)], "PT. " + letter, al)
        # vertical dimensions on the left
        x1 = uL - 0.85 * k
        x2 = x1 - 0.3 * k
        if s.kind == "EB":
            c = s.cheeks[0]
            zs = sorted({round(c["bot"], 6), round(s.cap_bot, 6), round(s.cap_top, 6),
                         round(s.backwall_top[0][1], 6), round(c["top"], 6)})
            chain_dims(v, zs, None, uL, x1, vertical=True, step=0.125)
            v.dim((uL, zs[0]), (uL, zs[-1]), -(x2 - uL), 90)
        else:
            v.dim((uL, s.cap_bot), (uL, s.cap_top), -(x1 - uL), 90)
            if z_break:
                pa = T((s.wall_u[0], s.wall_bot))
                keep, v.xform = v.xform, None
                v.dim(pa, (s.wall_u[0], s.wall_top), -(x1 - s.wall_u[0]), 90, fdot.ft_in(s.wall_top - s.wall_bot))
                v.xform = keep
                pu = sorted(q["u"] for q in s.piles)
                pm = (pu[0] + pu[1]) / 2   # between the two left (hidden) piles
                v.mtext((pm, (s.wall_top + pa[1]) / 2), "PIER WALL\\P3'-0\" THICK\\P(PROVISIONAL)", attach=5)
        p = max(s.piles, key=lambda q: q["u"])
        xe = p["u"] + p["width"] / 2
        desc = ("18\" SQUARE PRESTRESSED\\PCONCRETE PILE (TYP.)" if p["shape"] == "square"
                else "20\" %s STEEL PIPE PILE (TYP.)" % "Ø")
        zd = zp + 0.3 * k   # above the circled pile number
        keep, v.xform = v.xform, None
        v.leader([(xe, zd), (uR + 0.3 * k, zp - 0.12 * k)], desc, "left")
        v.xform = keep
        # reinforcement, dimensioned with one string per bar run
        z_row, z_up = self._elev_steel(v, T, zp)
        # pile embedment (B4, B1): a vertical dimension inside the pile left of
        # the PGL, 0.3 ft right of its centre, from the cap bottom to the pile
        # top; the value below the cap in the bay to the right (between the
        # cap and the pile numbers, between the stirrup row's extension
        # lines), with its line to the dimension
        piles = sorted(s.piles, key=lambda q: q["u"])
        p = max((q for q in piles if q["u"] < 0), key=lambda q: q["u"])
        nxt = min((q for q in piles if q["u"] > p["u"]), key=lambda q: q["u"])
        txt = fdot.ft_in(p["top"] - s.cap_bot) + " (MIN.) (TYP.)"
        # B7: the value in the open space between the two piles at the pile
        # cut-off level (the stirrup extension lines fill the space under the
        # cap), with its two-piece pointer to the dimension inside the pile
        if z_row is not None:
            # end bent: the pile numbers under the stirrup row, 0.5 ft off the
            # piles on the side away from the section flag letters (which sit
            # on the viewing side of their ticks), so the circle at the pile
            # with the flag clears its letter (A1);
            # the dimension in the last pile near its outer face and the value
            # (two lines) in the band between the pile cut-offs and the row's
            # run texts, in the first stirrup run space outboard of the pile
            # wide enough for it, its landing clear of the extension line and
            # the angled piece passing the row's texts above them (B7)
            off = -0.5 if s.e1 > 0 else 0.5
            for q in s.piles:
                v.circled_number((q["u"] + off, z_row - 0.22 * k), q["no"])
            p = max(s.piles, key=lambda q: q["u"])
            xd = p["u"] + 0.55
            txt = fdot.ft_in(p["top"] - s.cap_bot) + "\\P(MIN.)"
            bw = text_w(v, txt) + 0.4 * th
            land, mgn = 0.12 * k, 0.1 * k
            gap = next(((a, b) for a, b in zip(self._ext_below, self._ext_below[1:])
                        if a >= p["u"] + p["width"] / 2 - 0.01 and b - a >= bw + land + 2 * mgn), None)
            if gap:
                z_mid = (zp + z_row + (1.4 + 1.67) * th) / 2   # between the pile bottoms and the run texts
                loc = (gap[0] + mgn + land + bw / 2, z_mid)
            else:
                txt = fdot.ft_in(p["top"] - s.cap_bot) + " (MIN.) (TYP.)"
                loc = (p["u"] + 2.0, z_row - 0.42 * k)
        else:
            xd = p["u"] + 0.3
            # pier (stirrup row above the cap): between the two piles under the cap
            xm = (p["u"] + p["width"] / 2 + nxt["u"] - nxt["width"] / 2) / 2
            loc = (xm, s.cap_bot - 0.06 * k - 0.7 * th)
        v.dim((xd, s.cap_bot), (xd, p["top"]), 0.0, 90, txt, horizontal=True, loc=loc)
        self._section_marks(v, T, zp, z_up, z_row)
        # (the bottom section flags sit under the row (end bent) or the pile
        # breaks (pier), the title under them)
        yt = min(zp - 0.42 * k, z_row - 0.55 * k if z_row is not None else zp)
        v.title((0, yt - 0.2 * k), "ELEVATION",
                "(LOOKING BACK STATION)" if s.key == "EB1" else "(LOOKING AHEAD STATION)")
        self.legend_at = (x2 - 0.1 * k, yt - 0.1 * k)
        return v

    def draw_legend(self, v):
        """Footnote symbol legend at the lower left of the elevation (one-line
        items; the Δ strap item is a paragraph printed with the details)."""
        items = [(sym, txt) for sym, txt in self.legend.items() if sym != DELTA]
        if items:
            v.legend(self.legend_at, items)

    def _section_marks(self, v, T, zp, z_up=None, z_row=None):
        """Section flags above the view (end bent: above the backwall; pier:
        above the stirrup row at z_up) and below it (end bent: under the
        stirrup row at z_row; pier: just below the pile cut-offs)."""
        s = self.s
        k = IN * v.sf
        look = (1, 0) if s.e1 > 0 else (-1, 0)
        # bottom flags: end bent under the stirrup row (its extension lines
        # fill the band beside the piles; A1), pier below the pile breaks
        # (the letter beside the pile clear of the break's lobes, A1)
        z_lo = (z_row - 0.4 * k) if (s.kind == "EB" and z_row is not None) else (zp - 0.3 * k)
        # pier: above the stirrup row over the cap (its extension lines fill the
        # band below the row; A1)
        z_hi = ((max(t[1] for t in s.backwall_top) + 0.45 * k) if s.kind == "EB" else z_up + 0.6 * k)
        keep, v.xform = v.xform, None
        for tag, lab in (("between_piles", "A"), ("at_pile", "B"), ("at_beam", "C")):
            uc = s.u(s.S["sections"][tag]["x_global_ft"])
            v.section_cut((uc, z_lo), (uc, z_hi), lab, look)
        v.xform = keep

    def _elev_steel(self, v, T, zp):
        """Bars in the elevation: first and last bar of each run (SDM 4.3.B),
        stirrups as lines with end dots; returns the z of a dimension row
        drawn below the view (or None)."""
        s = self.s
        th, k = v.th, IN * v.sf
        fn = s.P_elev
        dot_r = fdot.DOT_IN / 2 * k
        u0, u1 = s.cap_u
        ends = s.outer_u
        right = []   # callouts beside the right end of the cap (tips at the bar ends, A3)
        below = []   # callouts below the cap
        # longitudinal cap bars: one line per distinct level
        for sub in ("top", "side", "bottom"):
            bs = s.bars_of(family="cap_long", subtype=sub)
            if not bs:
                continue
            levels = OrderedDict()
            for b in bs:
                levels.setdefault(round(b["pts"][0][2], 3), []).append(b)
            ends_at = []
            for z, grp in levels.items():
                pts = proj(grp[0], fn)
                draw_bar(v, pts, grp[0]["dia_in"])
                ends_at.append(horiz_end(pts, 1))
            mark = bs[0]["mark"]
            if sub == "side":
                faces = len({round(b["pts"][0][1], 2) for b in bs})
                txt = "%d~%s (EF)" % (len(bs) // max(faces, 1), mark)
                tips = sorted(ends_at, key=lambda t: t[1])
            else:
                txt = "%d~%s" % (len(bs), mark)
                tips = [ends_at[0]]
            right.append((tips, txt))
        # stirrups: first and last bar of each run (line + end dots)
        groups = s.transverse_groups()
        for g in groups:
            us = g["u"]
            for u in sorted({us[0], us[-1]}):
                b = g["bars"][us.index(u)]
                zs = [p[2] for p in b["pts"]]
                a, c = (u, min(zs)), (u, max(zs))
                v.line(a, c, "Rebar")
                v.dot(a, dot_r)
                v.dot(c, dot_r)
        runs = [(g["u"], series_text(g["u"], g["mark"])) for g in groups]
        xs, texts = run_chain(runs, ends)
        ext_below = []   # extension lines crossing the band below the cap
        if s.kind == "EB":
            # (the band between the pile cut-offs and the row's two-line run
            # texts holds the pile embedment value, B7)
            z_row, z_up = zp - 0.57 * k, None
            chain_dims(v, xs, texts, s.cap_bot, z_row)
            ext_below = sorted(xs)
        else:
            z_row = None
            zt = max(z for _, _, _, z in self.elev_points) if self.elev_points else s.cap_top
            z_up = max(zt, s.cap_top + 0.6) + 0.45 * k
            chain_dims(v, xs, texts, s.cap_top, z_up)
        self._ext_below = ext_below
        self.notes.append("STIRRUP SPACING IS DIMENSIONED TO BAR CENTERLINES.")
        # U-bars between piles and cap end U-bars (one per location)
        seen = set()
        for fam in ("cap_added", "cap_end"):
            for b in s.bars_of(family=fam):
                key = tuple(round(c, 2) for c in (min(p[0] for p in b["pts"]), max(p[0] for p in b["pts"]),
                                                  min(p[2] for p in b["pts"])))
                if key in seen:
                    continue
                seen.add(key)
                draw_bar(v, proj(b, fn), b["dia_in"])
        uadd = s.bars_of(family="cap_added")
        if uadd:
            locs = sorted({round(s.u(min(p[0] for p in b["pts"])), 2) for b in uadd})
            per = len(uadd) // max(len(locs), 1)
            # the bay right of the PGL: tip on the bottom leg near its left end
            b = min(uadd, key=lambda x: abs(s.u(sum(p[0] for p in x["pts"]) / len(x["pts"])) - 0.6 * u1))
            pts = proj(b, fn)
            lowz = min(q[1] for q in pts)
            tip = (min(q[0] for q in pts) + 0.12, lowz)
            below.append(([tip], "%d~%s (TYP.)" % (per, b["mark"])))
        ends_b = s.bars_of(family="cap_end")
        if ends_b:
            marks = list(OrderedDict.fromkeys(b["mark"] for b in ends_b))
            txt = " & ".join("%d~%s" % (len([b for b in ends_b if b["mark"] == m]) // 2, m) for m in marks)
            tips = []
            for m in marks:
                b = max((b for b in ends_b if b["mark"] == m), key=lambda x: sum(s.u(p[0]) for p in x["pts"]))
                pts = proj(b, fn)
                tips.append(max(pts, key=lambda q: (round(q[0], 2), -q[1])) if m == marks[0] else pts[len(pts) // 2])
            below.append((tips, txt + " (EA. END)"))
        # backwall: front-face verticals (first, last) and horizontals
        if s.kind == "EB":
            vert = s.bars_of(family="backwall", subtype="vert")
            face = min(vert, key=lambda b: abs(b["pts"][0][1] - s.ffbw_y))["pts"][0][1]
            front = sorted((b for b in vert if abs(b["pts"][0][1] - face) < 0.05), key=lambda b: s.u(b["pts"][0][0]))
            us = [s.u(b["pts"][0][0]) for b in front]
            for b in (front[0], front[-1]):
                draw_bar(v, proj(b, fn), b["dia_in"])
            hor = s.bars_of(family="backwall", subtype="horiz")
            hface = sorted(hor, key=lambda b: abs(b["pts"][0][1] - face))
            hf = sorted((b for b in hor if abs(b["pts"][0][1] - hface[0]["pts"][0][1]) < 0.05),
                        key=lambda b: b["pts"][0][2])
            for b in hf:
                draw_bar(v, proj(b, fn), b["dia_in"])
            right.append(([horiz_end(proj(hf[len(hf) // 2], fn), 1)], "%d~%s (EF)" % (len(hf), hf[0]["mark"])))
            bw_u = sorted(s.u(x) for x in (s.backwall_bb[0], s.backwall_bb[3]))
            z_bw = max(t[1] for t in s.backwall_top)
            zc = max(c["top"] for c in s.cheeks)
            xs, texts = run_chain([(us, series_text(us, front[0]["mark"], ef=True))], bw_u)
            chain_dims(v, xs, texts, z_bw, zc + 0.4 * k)
        # one column right of the right end: the bar callouts with leaders
        # meeting the bars at an angle (A3) and the PT. labels of that end
        callouts(v, right + getattr(self, "_right_pts", []), ends[1] + 0.2 * k, 1, slide=True)
        if below:
            # just below the cap, above the pile numbers (A8); each text in a
            # gap between the extension lines of the stirrup row (A1)
            zb = s.cap_bot - 0.25 * k
            for tips, txt in below:
                tw = text_w(v, txt)
                land = (0.1 if len(tips) == 1 else 0.16) * k
                pref = max(t[0] for t in tips) + 0.06 * k + land + 0.4 * th
                x_txt = None
                for a, b in zip(ext_below, ext_below[1:]):
                    lo, hi = a + 0.02 * k, b - 0.02 * k - tw
                    if hi >= lo:
                        x = min(max(pref, lo), hi)
                        if x_txt is None or abs(x - pref) < abs(x_txt - pref):
                            x_txt = x
                x_txt = pref if x_txt is None else x_txt
                tx = x_txt - 0.4 * th - land
                knee = (tx, zb)
                if len(tips) == 1:
                    v.leader([tips[0], knee, (x_txt - 0.4 * th, zb)], txt, "left")
                else:
                    v.leader_fan(tips, knee, txt, "left")
                zb -= 2.2 * th
        return z_row, z_up

    # ----------------------------------------------------------- sections
    def section(self, zone, tag, letter, subtitle):
        s = self.s
        S = s.S
        sec = S["sections"][tag]
        xc = sec["x_global_ft"]
        depth = S["section_depth_ft"]
        v = View(self.doc, zone, "%s SECTION %s" % (s.key, letter))
        th, k = v.th, IN * v.sf
        eb = s.kind == "EB"
        cs = s.cap_s
        ccl = (cs[0] + cs[1]) / 2
        pile_show = 1.0 if eb else 0.6
        z_lo = s.cap_bot - pile_show
        # context: the MSE wall in front; no landing or approach slab (D4);
        # the soil reinforcing strap is drawn on its own below (D6)
        if s.key == "EB1":
            xr = (cs[0] - 0.15, cs[1] + 2.4)   # the closure slab and the start of the coping (sheet room)
        elif s.key == "EB2":
            xr = (cs[0] - 2.4, cs[1] + 0.15)
        else:
            xr = (cs[0] - 0.35, cs[1] + 0.35)
        edges = [r for r in sec["edges"] if r["role"] not in ("landing", "strap")]
        straps = [r for r in sec["edges"] if r["role"] == "strap" and r["vis"]] if eb else []
        # back (backwall or left) side and front side fs (+1 right, -1 left)
        fs = -1 if s.key == "EB2" else 1
        x_front, x_back = (cs[1], cs[0]) if fs > 0 else (cs[0], cs[1])
        # D5: the keyed construction joint at the cap/backwall interface (the
        # key of DETAIL "A": 4" wide at the middle third of the backwall, 1/2"
        # bevels, 1 1/2" into the cap) drawn in place of the straight joint
        key = None
        if eb:
            k0, k1 = x_back + fs * 4 * IN, x_back + fs * 8 * IN
            edges = cut_out(edges, s.cap_top, min(k0, k1), max(k0, k1))
            key = [(k0, s.cap_top), (k0 + fs * 0.5 * IN, s.cap_top - 1.5 * IN),
                   (k1 - fs * 0.5 * IN, s.cap_top - 1.5 * IN), (k1, s.cap_top)]
        # the room above the backwall stays as with the slab stub (not drawn),
        # so the sections keep their place beside the pedestal details
        tops = [p[1] for r in sec["edges"] if r["vis"] and r["role"] != "strap"
                for p in edge_points(r) if xr[0] <= p[0] <= xr[1]]
        z_hi = max(tops) + 0.05
        # bearing labels: EB within the backwall height; pier just above the
        # cap or pedestals, under the dimensions
        z_bl = (max(t[1] for t in s.backwall_top) - 0.6) if eb else max(s.cap_top + 0.45, max(tops) + 0.1)
        if not eb:
            # pier: the bearing label above the two dimension rows over the
            # cap, the bearing lines ending under it (A1)
            z_bl = z_hi + 0.35 * k + 0.3 * k + 0.3 * k
        box = (xr[0], z_lo, xr[1], z_hi)
        draw_edges(v, edges, box=box, hidden=False)
        if key:
            v.pl(key, "SubStrConc")
        al_f = "left" if fs > 0 else "right"     # texts on the front side
        # the end bent weather closure (D-044): the rain closure slab between
        # the front coping and the cap face, and the coping on the MSE wall
        clos = [r for r in edges if r["role"] == "closure" and r["vis"]]
        if clos:
            ce = extents(clos)
            # label above the slab, in the open space between the cap face and
            # the coping top (A1)
            tip = (x_front + fs * 1.6, ce[3])   # near the coping end of the slab, clear of the bar callouts
            knee = (tip[0] - fs * 0.1 * k, ce[3] + 0.3 * k)
            v.leader([tip, knee, (knee[0] + fs * 0.12 * k, knee[1])], "4\" CLOSURE SLAB", al_f)
        cop = [r for r in edges if r["role"] == "coping" and r["vis"]]
        if cop:
            pe_c = extents(cop)
            xi = pe_c[0] if fs > 0 else pe_c[2]    # the coping's inner face, under the slab
            # the label in the gap under the slab (no width added, clear of the
            # slab label above; A1)
            tip = (xi, pe_c[3] - 0.6)
            knee = (tip[0] - fs * 0.2 * k, tip[1] + 0.05 * k)
            v.leader([tip, knee, (knee[0] - fs * 0.12 * k, knee[1])], "COPING", "right" if fs > 0 else "left")
        # piles: a break only where a pile body is cut by the window bottom
        # (D2): visible pile edges in the window spanning its bottom
        piles = [r for r in edges if r["role"] in ("pile_conc", "pile_steel") and r["vis"]
                 and any(box[0] - 0.01 <= p[0] <= box[2] + 0.01 and p[1] >= z_lo - 0.01 for p in edge_points(r))]
        if piles:
            pe = extents(piles)
            if not (pe[1] <= z_lo + 0.01 and pe[3] > z_lo + 0.05):
                piles = []
        if piles:
            kind = "pipe" if piles[0]["role"] == "pile_steel" else "square"
            v.pile_break((pe[0] + pe[2]) / 2, z_lo, pe[2] - pe[0], kind,
                         "PileSteel" if kind == "pipe" else "PileConc")
        mse = [r for r in edges if r["role"] == "mse" and r["vis"]]
        if mse:
            me = extents(mse)
            v.break_line((me[0] - 0.08 * k, z_lo), (me[2] + 0.08 * k, z_lo))
        # centerlines
        z_ccl = s.cap_top + 0.5          # top of the drawn cap centerline
        z_bct = z_bl + 0.15 if eb else z_bl - 0.2   # top of the drawn bearing centerlines
        # the bottom bar row (below the pile where one is cut) and the
        # centerline label under it, clear of the values pulled out below the row
        yb1 = (z_lo - 0.25 * k) if piles else (s.cap_bot - 0.45 * k)
        z_cll = (z_lo - 0.52 * k) if piles else min(z_lo - 0.3 * k, yb1 - 0.45 * k)
        # the cap centerline, broken through the bottom row's text band (the
        # middle value straddles the centerline; A1)
        v.line((ccl, yb1 + 0.35 * k), (ccl, z_ccl), "CL_Major")
        v.line((ccl, z_cll - 0.12 * k), (ccl, yb1 - 0.03 * k), "CL_Major")
        v.leader([(ccl, z_cll), (ccl + fs * 0.3 * k, z_cll)], self.cl_name(), al_f, cl=True)
        for i, b in enumerate(s.bearings):
            v.line((b["s"], s.cap_top - 0.2), (b["s"], z_bct), "CL_Minor")
        if eb:
            b = s.bearings[0]
            v.leader([(b["s"], z_bl), (b["s"] + fs * 0.3 * k, z_bl)], "BEARING", al_f, cl=True)
        else:
            # pier: one fan from both bearing lines above the dimension rows,
            # the text inside the cap width (A1, sheet room)
            v.leader_fan([(b["s"], z_bct) for b in s.bearings], (ccl + 0.15 * k, z_bl), CL + " BEARING (TYP.)", "left")
        # reinforcement; in-plane bars on one line get daylight (C4)
        dots, shapes = self._section_bars(xc, depth)
        shapes = self._daylight(v, shapes, ccl)
        for mark, pts in dots.items():
            for p, rad in pts:
                v.dot(p, rad)
        for rb, pts in shapes:
            draw_bar(v, pts, rb["dia_in"])
        # callouts beside the front face
        items = []
        cap_dots = {m: [p for p, _ in pts] for m, pts in dots.items()}
        for mark, ps in cap_dots.items():
            e = s.table[mark]
            if e["family"] == "cap_long":
                near = sorted(ps, key=lambda p: -fs * p[0])
                if e["subtype"] == "side":
                    col = [p for p in ps if abs(p[0] - near[0][0]) < 0.02]
                    items.append((sorted(col, key=lambda p: p[1]), "%d~%s (EF)" % (len(col), mark)))
                elif e["subtype"] == "bottom":
                    grp = [p for p in ps if fs * (p[0] - ccl) > 0]
                    items.append((grp, "%d~%s" % (len(ps), mark)))
                else:
                    items.append(([near[0]], "%d~%s" % (len(ps), mark)))
            elif e["family"] == "cap_added":   # inside the cap, fanned up to a knee beside the group
                tips = sorted(ps, key=lambda p: -fs * p[0])
                far = tips[-1]
                # the knee above the dots near the back face, the text running
                # toward the centerline through the open interior (A1)
                knee = (x_back + fs * 0.45, far[1] + 0.35 * k)
                v.leader_fan(tips, knee, "%d~%s" % (len(ps), mark), "left" if fs > 0 else "right")
            elif e["family"] == "pedestal":
                near = max(ps, key=lambda p: fs * p[0])
                items.append(([near], "%d~%s" % (len(ps), mark)))
        hoop = None
        for rb, pts in shapes:
            fam = rb["family"]
            if fam == "cap_trans":
                hoop = (rb, pts)
                zm = s.cap_bot + 0.62 * (s.cap_top - s.cap_bot)
                tip = (max((q[0] for q in pts), key=lambda x: fs * x), zm)
                items.append(([tip], rb["mark"]))
            elif fam == "pedestal":
                top = max(pts, key=lambda p: (p[1], fs * p[0]))
                items.append(([top], rb["mark"]))
        callouts(v, items, x_front + fs * 0.25 * k, fs)
        # backwall: horizontals cut (dots), verticals in plane.  On the bridge
        # side the cap and bearing centerlines and the extension lines (B3)
        # divide the space above the cap into strips; each label keeps to one
        # (A1): FFBW between the FFBW and the cap centerline, the others
        # between the bearing centerline and the cap front face
        bw = [(rb, pts) for rb, pts in shapes if rb["family"] == "backwall"]
        if eb:
            xbr = s.bearings[0]["s"]
            if bw:   # the front-face vertical, labelled toward the FFBW side
                rb, pts = max(bw, key=lambda t: fs * t[1][0][0])
                zq = s.cap_top + 2.9
                xk = xbr + fs * 0.08 * k
                v.leader([(pts[0][0], zq), (xk, zq + 0.12 * k), (xk + fs * 0.1 * k, zq + 0.12 * k)],
                         "%s (EF)" % rb["mark"], al_f)
            v.leader([(s.ffbw_s, s.cap_top + 2.0), (s.ffbw_s + fs * 0.1 * k, s.cap_top + 2.0)], "FFBW", al_f)
            # D5: the cap/backwall construction joint at mid thickness of the backwall
            zj = s.cap_top + 1.15
            v.leader([((x_back + s.ffbw_s) / 2, s.cap_top), (xbr - fs * 0.12 * k, zj), (xbr + fs * 0.02 * k, zj)],
                     "CONST. JOINT\\P(SEE DETAIL \"A\")", al_f)
            # B5: embedment of the backwall verticals below the joint, beside
            # the FFBW on the bridge side, from the cap top to the bar end
            if bw:
                rb, pts = max(bw, key=lambda t: fs * t[1][0][0])
                low = min((p for _, ps in bw for p in ps), key=lambda p: p[1])
                emb = s.cap_top - low[1]
                if emb > 1.0 / 96:
                    # dimension line (its text right of it) between the FFBW and
                    # the cap centerline, clear of other in-plane bars (the
                    # pedestal U-bar legs in Section C-C)
                    strip = sorted((s.ffbw_s, ccl))
                    legs = [a[0] for rb2, ps in shapes if rb2["family"] != "backwall" for a, b in zip(ps, ps[1:])
                            if abs(a[0] - b[0]) < 1e-3 and min(a[1], b[1]) < s.cap_top and max(a[1], b[1]) > low[1]]

                    def free(x):
                        lo, hi = x - 0.04, x + 0.15 * k + 0.04
                        return strip[0] < lo and hi < strip[1] and all(not (lo - 0.03 < xl < hi + 0.03) for xl in legs)
                    xd = next((s.ffbw_s + fs * d * k for d in (0.2, 0.35, 0.12, 0.45, 0.6)
                               if free(s.ffbw_s + fs * d * k)), s.ffbw_s + fs * 0.2 * k)
                    txt = fdot.ft_in(emb, 0.25) + " (MIN.)"
                    end = min(pts, key=lambda p: p[1])
                    # B7: the value horizontal in the band between the hoop top
                    # leg and the bar ends, beyond the cap centerline (open
                    # space inside the cap), with its two-piece pointer
                    xt = ccl + fs * (0.1 * k + text_w(v, txt) / 2)
                    v.dim((xd, s.cap_top), (end[0], end[1]), 0.0, 90, txt, horizontal=True,
                          loc=(xt, s.cap_top - max(0.8, emb * 0.6)))
            # the wall face label only where the wall shows below the coping;
            # the text toward the cap, under the closure slab (no width added)
            cop_bot = min(extents(cop)[1], extents(cop)[3]) if cop else z_hi
            if mse and cop_bot > z_lo + 0.2:
                face = me[0] if fs > 0 else me[2]
                zf = (z_lo + cop_bot) / 2
                v.leader([(face, zf), (face - fs * 0.3 * k, zf)], "FRONT FACE OF\\PMSE WALL",
                         "right" if fs > 0 else "left")
            # D6: the soil reinforcing strap (model reference D-045) out of the
            # back face, kept inside the first back dimension row, with its
            # height above the cap top; the label (and the Δ legend) once per
            # sheet: Sections A-A and C-C (B-B sits beside A-A)
            if straps:
                se = extents(straps)
                zst = (se[1] + se[3]) / 2
                x0s = se[2] if fs > 0 else se[0]
                Ls = min(1.5, 0.29 * k, abs(se[2] - se[0]))
                # the strap out of the back face plus a representative 6"
                # embedment into the backwall (the connection is the wall
                # provider's; the model carries the strap only outside)
                v.line((x0s + fs * 0.5, zst), (x0s - fs * Ls, zst), "Rebar2")
                xsd = x_back - fs * 0.15 * k
                v.dim((x_back, s.cap_top), (xsd, zst), fs * 0.15 * k, 90, fdot.ft_in(zst - s.cap_top, 0.25))
                if tag != "at_pile":
                    # the label above the backwall top corner on the back side,
                    # between the back face and the first dimension column (A1,
                    # and no width added to the view)
                    tip = (x_back - fs * 0.22 * k, zst)
                    z_bw = max(t[1] for t in s.backwall_top)
                    knee = (x_back - fs * 0.35 * k, z_bw + 0.5 * k)   # two text lines hang below the knee
                    v.leader([tip, knee, (knee[0] - fs * 0.12 * k, knee[1])], DELTA + " REINF.\\PSTRAP",
                             "right" if fs > 0 else "left")
                self.legend[DELTA] = STRAP_LEGEND
        if piles and tag == "at_pile":   # described on the back side, clear of the MSE wall
            side_x = pe[0] if fs > 0 else pe[2]
            desc = ("18\" SQUARE\\PPRESTRESSED\\PCONCRETE PILE" if piles[0]["role"] == "pile_conc"
                    else "20\" Ø STEEL\\PPIPE PILE")
            # the label on the front side beyond the cap face at the pile stub's
            # level (the bottom row's extension lines fill the space under the
            # cap; A1)
            side_x = pe[2] if fs > 0 else pe[0]
            v.leader([(side_x, z_lo + 0.25), (x_front + fs * 0.3 * k, z_lo + 0.25 - 0.1 * k)], desc, al_f)
        # ------------------------------------------------ dimensions
        dot_all = [p for ps in cap_dots.values() for p in ps]
        lowz = min(p[1] for p in dot_all if p[1] < s.cap_bot + 0.6)
        bot = sorted({round(p[0], 4) for p in dot_all if abs(p[1] - lowz) < 0.06})
        # the bottom row (yb1, set with the centerline above) clears a two-line
        # text under the cap; with a pile cut by the window it goes below the
        # pile (its texts would cross the pile)
        # bottom bar layout; uniform interior runs read 'n SPA. @ s'
        chain = [cs[0]]
        texts = []
        for ser in series_split(bot):
            if abs(ser[0] - chain[-1]) > 1e-9:
                chain.append(ser[0])
                texts.append(None)
            if len(ser) > 1:
                chain.append(ser[-1])
                texts.append(spaces_text(ser) if len(ser) > 2 else None)
        chain.append(cs[1])
        texts.append(None)
        chain_dims(v, chain, texts, s.cap_bot, yb1)
        # above: overall and the splits at the backwall face, bearings and
        # centerline, each extension line reaching its feature (B3): the cap
        # faces at the cap top (the back face and the FFBW at the backwall
        # top), the centerlines at the top of their drawn lines
        zt0 = (max(p[1] for r in edges if r["vis"] and r["role"] == "backwall" for p in edge_points(r))
               if eb else max(tops))
        yt1 = z_hi + 0.35 * k
        yt2 = yt1 + 0.3 * k
        feat = {round(cs[0], 6): s.cap_top, round(cs[1], 6): s.cap_top}
        if eb:
            feat[round(x_back, 6)] = zt0
            feat[round(s.ffbw_s, 6)] = zt0
        for b in s.bearings:
            feat.setdefault(round(b["s"], 6), z_bct)
        feat.setdefault(round(ccl, 6), z_ccl)
        xs = sorted(feat)
        chain_dims(v, xs, None, [feat[x] for x in xs], yt1, step=0.125)
        v.dim((xs[0], feat[xs[0]]), (xs[-1], feat[xs[-1]]), yt2 - feat[xs[0]])
        # back side: bar layout up the face (and the backwall), then heights
        lv = []
        for mark, ps in cap_dots.items():
            e = s.table[mark]
            if e["family"] == "cap_long":
                lv += [p[1] for p in ps]
        lv = sorted(set(round(z, 4) for z in lv))
        zs = [s.cap_bot, lv[0], lv[-1], s.cap_top]
        texts = [None, spaces_text(lv), None]
        if eb:
            hz = sorted({round(p[1], 4) for m, ps in cap_dots.items() if s.table[m]["family"] == "backwall"
                         for p in ps})
            z_bw = zt0
            if hz:
                mark = [m for m in cap_dots if s.table[m]["family"] == "backwall"][0]
                txt = series_text(hz, mark, ef=True)
                if straps:   # two lines, clear of the strap leader below it
                    txt = txt.replace(" @ ", "\\P@ ", 1)
                zs += [hz[0], hz[-1], z_bw]
                texts += [None, txt, None]
            else:
                zs += [z_bw]
                texts += [None]
        # B8: 0.45" between columns leaves room for a two-line rotated series
        # text; the first column clears the strap dimension at the back face
        # (the pier has no two-line series text on this side: closer columns)
        xl1 = x_back - fs * (0.45 if eb else 0.35) * k
        xl2 = xl1 - fs * (0.45 if eb else 0.3) * k
        chain_dims(v, zs, texts, x_back, xl1, vertical=True)
        hz2 = [s.cap_bot, s.cap_top] + ([zt0] if eb else [])
        chain_dims(v, hz2, None, x_back, xl2, vertical=True, step=0.125)
        # cover by a small dimension at the front face
        if hoop:
            rb, pts = hoop
            r = rb["dia_in"] / 24.0
            leg = max((p[0] for p in pts), key=lambda x: fs * x) + fs * r
            zc = s.cap_bot + 0.3 * (s.cap_top - s.cap_bot)
            cov = abs(x_front - leg)
            # B7: the value beyond the cap face at the cap bottom (under the
            # closure slab, below the bottom-bar callout), two-piece pointer
            txt = "%s COVER\\P(TYP., U.N.O.)" % fdot.ft_in(cov, 0.25)
            loc = (x_front + fs * (0.25 * k + text_w(v, txt) / 2), s.cap_bot + 0.05)
            v.dim((leg, zc), (x_front, zc), 0.0, 0.0, txt, loc=loc)
        yt = min(yb1 - 0.3 * k, z_cll - 0.08 * k)
        v.title(((box[0] + box[2]) / 2, yt - 0.3 * k), "SECTION %s-%s" % (letter, letter), subtitle)
        return v

    def _daylight(self, v, shapes, ccl):
        """C4: an in-plane bar drawn along another (a backwall vertical over a
        hoop leg: collinear segments overlapping more than 0.1 ft) is moved
        off it, the shorter of the two, toward the cap centreline (vertical
        segments) or mid-depth (horizontal ones), i.e. away from the nearest
        face, so that both bar ends show: 0.03" of daylight on paper between
        the lines, between the outlines where bars are drawn double (C1)."""
        s = self.s
        gap = 0.03 * IN * v.sf
        double = hasattr(v, "bar") and v.sf <= fdot.SCALES["1/2"] + 1e-9
        zmid = (s.cap_top + s.cap_bot) / 2
        out = [[rb, list(pts)] for rb, pts in shapes]

        def length(pts):
            return sum(math.dist(a, c) for a, c in zip(pts, pts[1:]))

        def overlap(p1, p2):
            """(axis, coordinate in p1, coordinate in p2) of the first pair of
            collinear segments overlapping more than 0.1 ft; axis 0 for
            vertical segments (same x), 1 for horizontal ones (same z)."""
            for a, b in zip(p1, p1[1:]):
                for c, d in zip(p2, p2[1:]):
                    for ax in (0, 1):
                        o = 1 - ax
                        if abs(a[ax] - b[ax]) > 1e-3 or abs(c[ax] - d[ax]) > 1e-3 or abs(a[ax] - c[ax]) > 0.01:
                            continue
                        lo = max(min(a[o], b[o]), min(c[o], d[o]))
                        hi = min(max(a[o], b[o]), max(c[o], d[o]))
                        if hi - lo > 0.1:
                            return ax, (a[ax] + b[ax]) / 2, (c[ax] + d[ax]) / 2
            return None

        for _ in range(3):
            moved = False
            for i in range(len(out)):
                for j in range(i + 1, len(out)):
                    sh, ot = (out[i], out[j]) if length(out[i][1]) <= length(out[j][1]) else (out[j], out[i])
                    hit = overlap(sh[1], ot[1])
                    if hit is None:
                        continue
                    ax, c_sh, c_ot = hit
                    dirn = 1.0 if (ccl if ax == 0 else zmid) > c_ot else -1.0
                    sep = gap + ((sh[0]["dia_in"] + ot[0]["dia_in"]) / 24.0 if double else 0.0)
                    delta = c_ot + dirn * sep - c_sh
                    sh[1] = [(p[0] + delta, p[1]) if ax == 0 else (p[0], p[1] + delta) for p in sh[1]]
                    moved = True
            if not moved:
                break
        return [(rb, pts) for rb, pts in out]

    def _section_bars(self, xc, depth):
        """End-on dots where bars cross the cut, plus the nearest bar of each
        in-plane family (and face) lying within ``depth`` beyond it."""
        dots = OrderedDict()
        nearest = OrderedDict()
        for b in self.s.bars:
            pts = b["pts"]
            r = b["dia_in"] / 24.0
            if b["transverse"]:
                dist = b["x_station"] - xc
                if -1e-6 <= dist <= depth:
                    face = round(sum(p[1] for p in pts) / len(pts), 1) if b["family"] == "backwall" else None
                    # one cap stirrup (hoop or open) per section: the nearest
                    key = (b["family"], None if b["family"] == "cap_trans" else b["subtype"], face)
                    if key not in nearest or dist < nearest[key][0]:
                        nearest[key] = (dist, b)
                continue
            for p, q in zip(pts, pts[1:]):
                if (p[0] - xc) * (q[0] - xc) < 0:
                    L = math.dist(p, q)
                    if abs(q[0] - p[0]) / max(L, 1e-9) < 0.5:
                        continue
                    t = (xc - p[0]) / (q[0] - p[0])
                    pt = (p[1] + t * (q[1] - p[1]), p[2] + t * (q[2] - p[2]))
                    dots.setdefault(b["mark"], []).append(((-pt[0], pt[1]), r))
        shapes = [(b, [self.s.P_sec(p) for p in b["pts"]]) for _, b in nearest.values()]
        return dots, shapes

    # -------------------------------------------------------- cheek views
    def cheek_view(self, zone, cheek, letter, wwr_note=2, cuts=None):
        """Outside view of a cheek wall with its bars.  ``cuts`` (D8, from
        details.cheek_cut_marks) places the flags of the cheek wall sections
        in this view's frame (x = sgn * (y - y0), z):
        {"side": {"x": x, "look": (lx, 0), "letter": "F"},
         "top": {"z": z, "look": (0, -1), "letter": "G"}}; "letter" is
        optional (F and G)."""
        s = self.s
        S = s.S
        cv = S["cheek_views"][cheek["name"]]
        v = View(self.doc, zone, "%s VIEW %s" % (s.key, letter))
        th, k = v.th, IN * v.sf
        draw_edges(v, cv["edges"])
        sgn = -1 if cv["side"] == "left" else 1

        def fn(p):
            return (sgn * (p[1] - s.y0), p[2])
        num = cheek["name"][-2:]
        bars = [b for b in s.bars if b["family"] == "cheek" and b["group"].endswith(num + "Bars")]
        verts = sorted((b for b in bars if b["subtype"] == "vert"), key=lambda b: fn(b["pts"][0])[0])
        hors = sorted((b for b in bars if b["subtype"] == "horiz"), key=lambda b: b["pts"][0][2])
        xs_v = [fn(b["pts"][0])[0] for b in verts]
        zs_h = [b["pts"][0][2] for b in hors]
        x0, z0, x1, z1 = extents(cv["edges"], ("cheek",))
        # WWR limits: light diagonal hatch, about 0.1 in apart on paper
        w = [b for b in S["wwr"] if b["group"].endswith(num)]
        for part in ("Bottom", "Side"):
            ws = [b for b in w if part in b["name"]]
            if not ws:
                continue
            pts = [fn(p) for b in ws for p in barlib.polyline3(b, 10.0)]
            a = (min(p[0] for p in pts), min(p[1] for p in pts))
            c = (max(p[0] for p in pts), max(p[1] for p in pts))
            if c[0] - a[0] < 0.08:
                c = (a[0] + 0.08, c[1])
            if c[1] - a[1] < 0.08:
                c = (c[0], a[1] + 0.08)
            ring = [a, (c[0], a[1]), c, (a[0], c[1])]
            v.hatch_poly(ring, scale=0.1 * k / 0.125)
            v.pl(ring, "Rebar2", closed=True)
        for b in (verts[0], verts[-1], hors[0], hors[-1]):
            draw_bar(v, proj(b, fn), b["dia_in"])
        mv, mh = verts[0]["mark"], hors[0]["mark"]
        # bottom: vertical bar series, overall width
        yb = z0 - 0.4 * k
        xs, texts = run_chain([(xs_v, series_text(xs_v, mv))], (x0, x1))
        chain_dims(v, xs, texts, z0, yb)
        v.dim((x0, z0), (x1, z0), yb - 0.3 * k - z0, step=0.125)
        # outer side: horizontal bar series, overall height, lug
        out = x1 if sgn > 0 else x0
        xr = out + sgn * 0.4 * k
        xs, texts = run_chain([(zs_h, series_text(zs_h, mh))], (z0, z1))
        chain_dims(v, xs, texts, out, xr, vertical=True)
        v.dim((out, z0), (out, z1), -(xr + sgn * 0.3 * k - out), 90, step=0.125)
        inner = x0 if sgn > 0 else x1
        xl = inner - sgn * 0.3 * k
        # the lug value beside its column at the lug's mid height (B7), clear
        # of the bottom row's pulled-out values
        v.dim((inner, z0), (inner, s.cap_bot), -(xl - inner), 90, fdot.ft_in(s.cap_bot - z0) + "\\PLUG",
              loc=(xl - sgn * 0.3 * k, (z0 + s.cap_bot) / 2))
        # labels inside the wall face (clear of the shaded WWR band), as on the sample sheets
        wx = [fn(p)[0] for b in w if "Side" in b["name"] for p in barlib.polyline3(b, 10.0)]
        band = (min(wx), max(wx)) if wx else (x0, x0)
        right = (band[0] + band[1]) / 2 < (x0 + x1) / 2      # free face right of the band
        al, d = ("left", 1) if right else ("right", -1)
        xin = band[1] + 0.06 * k if right else band[0] - 0.06 * k
        zm = (s.cap_bot + z1) / 2
        # labels outside the inner face (the side away from the dimension
        # columns, beyond the lug column; A1: not over the bars, the lug or
        # the dimensions), as on sample sheet B1-19
        d_in = -sgn
        al_in = "left" if d_in > 0 else "right"
        x_edge = inner + d_in * 0.5 * k
        v.leader([((band[0] + band[1]) / 2, zm - 0.6), (x_edge, zm - 0.6 - 0.25 * k)],
                 "SHADED AREA\\PSHOWS LIMITS\\POF WWR\\P(SEE NOTE %d)" % wwr_note, al_in)
        v.leader([(inner - d_in * 0.15, s.cap_bot + 0.6), (x_edge, s.cap_bot + 0.6 + 0.15 * k)], "END BENT CAP", al_in)
        um = xs_v[0] if right else xs_v[-1]          # a drawn (first or last) vertical bar
        v.leader([(um, zm + 0.9), (um + d * 0.2 * k, zm + 0.9 + 0.15 * k)], mv, al)
        hz = zs_h[-1]                                 # the top (drawn) horizontal bar
        v.leader([(xin + d * 0.1, hz), (xin + d * 0.3 * k, hz - 0.2 * k)], mh, al)
        # D8: flags of the cheek wall sections (vertical cut F-F at the top and
        # bottom, horizontal cut G-G at both sides, looking down)
        if cuts:
            m = 0.25 * k   # the flags' ticks end at the concrete outline
            far = 1.05 * k   # beyond the two dimension columns (A1: flags never on a dimension)
            if cuts.get("side"):
                c = cuts["side"]
                v.section_cut((c["x"], z0 - far), (c["x"], z1 + m), c.get("letter", "F"), tuple(c["look"]))
            if cuts.get("top"):
                c = cuts["top"]
                xo, xi = out + sgn * far, inner - sgn * m
                v.section_cut((min(xo, xi), c["z"]), (max(xo, xi), c["z"]), c.get("letter", "G"),
                              tuple(c.get("look", (0, -1))))
        drop = 0.6 * k if cuts and cuts.get("side") else 0.0   # below the bottom F-F flag
        v.title(((x0 + x1) / 2, yb - 0.3 * k - 0.45 * k - drop), "VIEW %s-%s" % (letter, letter),
                "(%s CHEEK WALL)" % ("LEFT" if cheek["u"] < 0 else "RIGHT"))
        return v

    # --------------------------------------------------------- pedestals
    def _ped_bars(self, ped):
        num = ped["name"][-2:]
        return [x for x in self.s.bars if x["family"] == "pedestal" and x["group"].endswith(num + "Bars")]

    def pedestal_plan(self, zone, ped):
        """Pedestal plan: cap edges and pedestal outline (no bearing pad),
        bars as lines, spacing strings from the bar centroids, covers and
        centerlines by leaders (FDOT sheets)."""
        s = self.s
        S = s.S
        b = ped["bb"]
        uu = sorted((s.u(b[0]), s.u(b[3])))
        vv = sorted((s.v(b[1]), s.v(b[4])))
        v = View(self.doc, zone, "%s PEDESTAL PLAN %d" % (s.key, ped["line"]))
        th, k = v.th, IN * v.sf
        m = 0.25
        box = (uu[0] - m, s.cap_v[0], uu[1] + m, s.cap_v[1])
        for rec in S["plan"]:
            if rec["role"] in ("pedestal", "cap", "backwall") and rec["vis"]:
                layer, lt = layer_for(rec)
                v.record(rec, layer, lt, box)
        for xv in (box[0], box[2]):
            v.break_line((xv, box[1] - 0.06 * k), (xv, box[3] + 0.06 * k))
        pbars = self._ped_bars(ped)
        for x in pbars:
            draw_bar(v, proj(x, s.P_plan), x["dia_in"])
        # centerlines by leaders
        v.line((ped["u"], box[1] - 0.2 * k), (ped["u"], box[3] + 0.1 * k), "CL_Minor")
        v.leader([(ped["u"], box[1] - 0.12 * k), (ped["u"] + 0.3 * k, box[1] - 0.12 * k)], "BEAM", "left", cl=True)
        v_cl = s.piles[0]["v"] if s.kind == "EB" else 0.0
        v.line((box[0] - 0.1 * k, v_cl), (box[2] + 0.1 * k, v_cl), "CL_Major")
        lab_x = box[2] + 0.1 * k
        x_lab = lab_x   # right end of the centerline label texts
        cl_lab = "CAP" if s.kind == "EB" else "PIER"
        v.leader([(lab_x - 0.05 * k, v_cl), (lab_x + 0.15 * k, v_cl + 0.18 * k)], cl_lab, "left", cl=True)
        x_lab = max(x_lab, lab_x + 0.27 * k + 0.4 * th + text_extent(CL + " " + cl_lab, th))
        for br in s.bearings:
            if vv[0] - 0.01 < br["v"] < vv[1] + 0.01:
                v.line((uu[0] - 0.2, br["v"]), (box[2] + 0.1 * k, br["v"]), "CL_Minor")
                v.leader([(lab_x - 0.05 * k, br["v"]), (lab_x + 0.15 * k, br["v"] - 0.18 * k)], "BEARING", "left",
                         cl=True)
                x_lab = max(x_lab, lab_x + 0.27 * k + 0.4 * th + text_extent(CL + " BEARING", th))
        # direction of stationing beyond the centerline labels, vertically
        # centred on the view (A5, sample B1-17); its text left of the line
        sd = -s.up
        L = 1.5
        ym = (box[1] + box[3]) / 2
        v.stationing_arrow((x_lab + 0.35 * k + 1.45 * th, ym - sd * L * k / 2), (0, sd), L)
        # spacing strings from bar centroids along the spacing axis
        xb = [x for x in pbars if x["subtype"] == "x"]     # constant u, spaced along u
        yb = [x for x in pbars if x["subtype"] == "y"]     # constant v, spaced along v
        cen = lambda x, f: sum(f(p) for p in x["pts"]) / len(x["pts"])  # noqa: E731
        y1 = max(vv[1], s.cap_v[1]) + 0.3 * k
        if xb:
            us = sorted(cen(x, lambda p: s.u(p[0])) for x in xb)
            marks = mark_list(sorted({x["mark"] for x in xb}))
            xs, texts = run_chain([(us, series_text(us, marks, len(xb)))], uu)
            chain_dims(v, xs, texts, vv[1], y1)
        v.dim((uu[0], vv[1]), (uu[1], vv[1]), y1 + 0.27 * k - vv[1], step=0.125)
        x1 = box[0] - 0.3 * k
        if yb:
            ys = sorted(cen(x, lambda p: s.v(p[1])) for x in yb)
            marks = mark_list(sorted({x["mark"] for x in yb}))
            xs, texts = run_chain([(ys, series_text(ys, marks, len(yb)))], vv)
            chain_dims(v, xs, texts, uu[0], x1, vertical=True)
        v.dim((uu[0], vv[0]), (uu[0], vv[1]), -(x1 - 0.27 * k - uu[0]), 90, step=0.125)
        # minimum side cover to the bar outside, by leader
        if xb:
            r = xb[0]["dia_in"] / 24.0
            lastu = max(max(s.u(p[0]) for p in x["pts"]) for x in xb)
            cov = uu[1] - (lastu + r)
            zq = vv[0] + 0.3 * (vv[1] - vv[0])
            # B7: the value in open space beyond the break line, under the
            # centerline labels, with a two-piece pointer
            txt = "%s MIN.\\PCOVER" % fdot.ft_in(cov, 0.25)
            # the text beyond the break line, in the widest gap between the
            # centerline labels there (A1)
            lab_vs = sorted([v_cl + 0.18 * k] + [br["v"] - 0.18 * k for br in s.bearings
                                                 if vv[0] - 0.01 < br["v"] < vv[1] + 0.01])
            edges_v = [vv[0] - 0.2 * k] + lab_vs + [vv[1] + 0.2 * k]
            a, c = max(zip(edges_v, edges_v[1:]), key=lambda t: t[1] - t[0])
            v.dim((lastu + r, zq), (uu[1], zq), 0.0, 0.0, txt,
                  loc=(box[2] + 0.15 * k + text_w(v, txt) / 2, (a + c) / 2))
        yt = box[1] - 0.42 * k
        v.title(((box[0] + box[2]) / 2, yt), "PEDESTAL PLAN")
        lines = ["(BEAM LINE %d SHOWN; BAR SPACING MAY BE ADJUSTED TO CLEAR THE CAP REINFORCEMENT)" % ped["line"]]
        for i, d in enumerate(lines):
            v.text(((box[0] + box[2]) / 2, yt - (1.85 + 1.6 * i) * th), d, None, "BOTTOM_CENTER")
        return v

    def pedestal_marks_note(self, ped):
        """Note naming the bar marks that differ at the other pedestals."""
        s = self.s
        parts = []
        for sub in ("x", "y"):
            here = sorted({x["mark"] for x in self._ped_bars(ped) if x["subtype"] == sub})
            for other in s.pedestals:
                if other is ped:
                    continue
                there = sorted({x["mark"] for x in self._ped_bars(other) if x["subtype"] == sub})
                if there != here:
                    parts.append("%s IN PLACE OF %s AT BEAM LINE %d" % ("/".join(there), "/".join(here), other["line"]))
        if not parts:
            return "PEDESTALS AT THE OTHER BEAM LINES ARE SIMILAR."
        return "PEDESTALS AT THE OTHER BEAM LINES ARE SIMILAR: %s." % "; ".join(parts)

    def pedestal_elevation(self, zone, ped):
        """Pedestal elevation: U-bars into the cap, construction joint, top of
        pedestal, chamfer, covers and embedment (FDOT sheets)."""
        s = self.s
        S = s.S
        b = ped["bb"]
        uu = sorted((s.u(b[0]), s.u(b[3])))
        ztop = max(p[2] for p in ped["top_vertices"])
        zlow = min(p[2] for p in ped["top_vertices"])
        pbars = self._ped_bars(ped)
        lo = min(p[2] for x in pbars for p in x["pts"])
        hi = max(p[2] for x in pbars for p in x["pts"])
        v = View(self.doc, zone, "%s PEDESTAL ELEVATION %d" % (s.key, ped["line"]))
        th, k = v.th, IN * v.sf
        box = (uu[0] - 0.7, lo - 0.15, uu[1] + 0.7, ztop + 0.5)   # the break lines beyond the dimension columns (A1)
        for rec in S["elev"]:
            if rec["role"] in ("pedestal", "cap") and rec["vis"]:
                layer, lt = layer_for(rec)
                v.record(rec, layer, lt, box)
        for x in pbars:
            draw_bar(v, proj(x, s.P_elev), x["dia_in"])
        v.break_line((box[0], box[1]), (box[2], box[1]))
        for xv in (box[0], box[2]):
            v.break_line((xv, box[1]), (xv, s.cap_top + 0.04 * k))
        # construction joint at the cap top (pedestal cast on the cap): the cap
        # top line itself, named by the leader (D5); no hidden line over it (D1)
        W = uu[1] - uu[0]
        v.leader([(uu[0] + 0.62 * W, s.cap_top), (uu[0] + 0.55 * W, ztop + 0.78 * k)], "CONST. JOINT", "left")
        v.leader([(uu[0] + 0.8 * W, ztop), (uu[0] + 0.72 * W, ztop + 0.52 * k)],
                 "TOP OF PEDESTAL\\P(SEE TABLE FOR\\PELEVATIONS)", "left")
        # chamfer callout only when the model's pedestal top is chamfered
        # (D-044 omitted the nominal 3/4" chamfers: 4 top corners, no callout)
        if len(ped["top_vertices"]) > 4:
            v.leader([(uu[1] - 0.02, ztop - 0.02), (uu[1] + 0.12 * k, ztop + 0.12 * k)],
                     "¾\" X ¾\"\\PCHAMFER (TYP.)", "left")
        # marks
        xb = [x for x in pbars if x["subtype"] == "x"]
        yb = [x for x in pbars if x["subtype"] == "y"]
        if yb:
            pts = proj(yb[0], s.P_elev)
            top = max(pts, key=lambda p: (p[1], -p[0]))
            v.leader([(uu[0] + 0.3, top[1]), (uu[0] - 0.25 * k, top[1] + 0.3 * k)],
                     mark_list(sorted({x["mark"] for x in yb})), "right")
        if xb:
            x = max(xb, key=lambda x: s.u(x["pts"][0][0]))
            uq = s.u(x["pts"][0][0])
            v.leader([(uq, lo + 0.25), (uq + 0.3 * k, lo - 0.05)], x["mark"] + " (TYP.)", "left")
        # embedment, height, covers
        xl = uu[0] - 0.3 * k
        v.dim((uu[0], lo), (uu[0], s.cap_top), -(xl - uu[0]), 90, fdot.ft_in(s.cap_top - lo, 0.25) + "\\P(MIN.)")
        v.dim((uu[0], s.cap_top), (uu[0], zlow), -(xl - uu[0]), 90, fdot.ft_in(zlow - s.cap_top, 0.25) + " (MIN.)",
              outside=1)
        r = pbars[0]["dia_in"] / 24.0
        um = uu[0] + 0.45 * (uu[1] - uu[0])
        zt_here = ztop
        v.dim((um, hi + r), (um, zt_here), 0.0, 90, "%s\\PCOVER" % fdot.ft_in(zt_here - hi - r, 0.25), outside=1)
        outer = max(max(s.u(p[0]) for p in x["pts"]) for x in pbars) + r
        zc = s.cap_top - 0.35
        # B7: the value in open space beyond the cap break, with a two-piece pointer
        txt = "%s\\PCOVER" % fdot.ft_in(uu[1] - outer, 0.25)
        v.dim((outer, zc), (uu[1], zc), 0.0, 0.0, txt,
              loc=(box[2] + 0.15 * k + text_w(v, txt) / 2, zc + 0.3 * k))
        v.title(((box[0] + box[2]) / 2, box[1] - 0.45 * k), "PEDESTAL ELEVATION")
        return v

    # ----------------------------------------------------------- end view
    def end_view(self, zone, letter, z_break=None):
        s = self.s
        S = s.S
        v = View(self.doc, zone, "%s VIEW %s" % (s.key, letter))
        k = IN * v.sf
        if z_break:
            self._broken(v, S["end_view"]["edges"], z_break)
            ex = extents(S["end_view"]["edges"])
            self._break_lines(v, z_break, ex[0] - 0.4, ex[2] + 0.4)
        else:
            draw_edges(v, S["end_view"]["edges"])
        T = v.xform or (lambda p: p)
        cs = s.cap_s
        ccl = (cs[0] + cs[1]) / 2
        zc = z_break[3] if z_break else S["pile_clip_z_ft"]
        keep, v.xform = v.xform, None
        zcd = T((0, zc))[1]
        # the centerline, broken through the wall-width text band at the bottom
        # (A1); its label above the cap-width dimension row
        y_wd = T((0, s.wall_bot))[1] - 0.35 * k if s.kind == "PIER" else None
        y_cw = s.cap_top + 0.6 + 0.35 * k   # the cap-width dimension row above the pedestals
        if y_wd is not None:
            v.line((ccl, zcd - 0.2 * k), (ccl, y_wd - 0.03 * k), "CL_Major")
            v.line((ccl, y_wd + 0.32 * k), (ccl, y_cw - 0.03 * k), "CL_Major")
        else:
            v.line((ccl, zcd - 0.2 * k), (ccl, y_cw - 0.03 * k), "CL_Major")
        v.line((ccl, y_cw + 0.32 * k), (ccl, s.cap_top + 2.0), "CL_Major")
        v.xform = keep
        v.leader([(ccl, s.cap_top + 1.85), (ccl + 0.3 * k, s.cap_top + 1.85 + 0.15 * k)], self.cl_name(), "left",
                 cl=True)
        v.dim((cs[0], s.cap_top), (cs[1], s.cap_top), 0.35 * k + 0.6, step=0.125)
        if s.kind == "PIER":
            ws = (-s.wall_bb[4], -s.wall_bb[1])
            v.dim(T((ws[0], s.wall_bot)), T((ws[1], s.wall_bot)), -0.35 * k, step=0.125)
            for b in s.bearings:
                v.line((b["s"], s.cap_top - 0.2), (b["s"], s.cap_top + 0.9), "CL_Minor")
        v.title((ccl, zcd - 0.6 * k), "VIEW %s-%s" % (letter, letter), "(END VIEW)")
        return v
