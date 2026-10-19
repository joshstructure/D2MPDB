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
from .cad import clip_segment as cad_clip
from .support import layer_for

try:   # the Δ legend with the service and factored strap loads filled in (D6)
    from .strap_loads import legend_text
except ImportError:   # fallback: the legend without loads
    legend_text = None

TOL = 1.0 / 96.0  # 1/8 in, ft
IN = 1.0 / 12.0
TAN35 = math.tan(math.radians(35.0))
TAN30 = math.tan(math.radians(30.0))
DELTA = "Δ"
STRAP_LEGEND = ("REINFORCING STRAPS AND ATTACHMENTS FOR THE END BENT SHALL BE DESIGNED AND FURNISHED BY THE "
                "PROPRIETARY WALL PROVIDER. THE STRAPS SHALL BE DESIGNED TO RESIST A SERVICE LOAD OF ___ K/FT AND A "
                "FACTORED LOAD OF ___ K/FT PERPENDICULAR TO THE END BENT BACKWALL.")


# ============================================================== helpers
def _seg_gap(a, b, p, q):
    """Distance between the segments ab and pq (0 where they cross)."""
    from .cad import segments_cross
    if segments_cross(a, b, p, q) is not None:
        return 0.0

    def pt_seg(x, s0, s1):
        dx, dy = s1[0] - s0[0], s1[1] - s0[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((x[0] - s0[0]) * dx + (x[1] - s0[1]) * dy) / L2))
        return math.hypot(x[0] - (s0[0] + t * dx), x[1] - (s0[1] + t * dy))
    return min(pt_seg(a, p, q), pt_seg(b, p, q), pt_seg(p, a, b), pt_seg(q, a, b))


def small_break(v, p, q, zk=0.05):
    """A break line like ``View.break_line`` (straight line, zig-zag at mid
    length, drawn on Symbols and noted for the checks) with a smaller zig-zag:
    ``zk`` paper inches half-width and amplitude instead of 0.08.  Round 6
    (markup "Do a bunch of small breaklines at the straps not one giant
    one", D12): one break per strap stub puts the zig-zags between the label
    rows above the plan, so each one is kept low (the 0.08 in zig-zag of the
    standard symbol reached the PT. B and STA. texts, A1)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    z = zk / 12.0 * v.sf
    m = (p[0] + dx / 2, p[1] + dy / 2)
    pts = [p, (m[0] - ux * z, m[1] - uy * z), (m[0] - ux * z / 2 + nx * z, m[1] - uy * z / 2 + ny * z),
           (m[0] + ux * z / 2 - nx * z, m[1] + uy * z / 2 - ny * z), (m[0] + ux * z, m[1] + uy * z), q]
    v.pl(pts, "Symbols")
    v._note_break(pts)


def draw_bar(v, pts, dia_in):
    """A bar not seen end-on (C1): ``View.bar`` draws it by the view scale,
    one line at 3/8" and double lines at the true width at 1/2" and larger;
    a plain polyline where ``View.bar`` is not available."""
    return v.bar(pts, dia_in) if hasattr(v, "bar") else v.pl(pts, "Rebar")


def draw_bar3(v, bar, fn):
    """A bar of the model projected through ``fn`` (3-D point -> view 2-D point)
    with its legs and hooks seen end-on drawn as dots (B13; markups "The bar
    ends at the bends here have odd shapes instead of smooth semi-circles" and
    "appears to show multiple clashing bars that don't occur in the model").
    Projecting the whole polyline draws a leg or hook that runs along the
    viewing direction as a short notched stub, over the bars behind it.  Here
    a segment is end-on when its projected length is less than 0.35 of its
    true length; consecutive in-plane segments form a run drawn by
    ``draw_bar`` (runs shorter than the bar diameter are dropped), and each
    maximal end-on run is one filled dot of the true bar size (SDM 4.3.7.D,
    C2) at its projected mean point.

    V13 (markup "What are these circles, the pedestal bars don't have two legs
    on one end?"): a run next to an end-on run starts (ends) AT the dot's
    centre.  Its points within 4 bar diameters of the dot centre (the
    projected bend) are dropped and the dot centre takes their place, so the
    bend never shows beside the dot as a second leg.

    V21 (markup "Where are these extra dots coming from?"): the model's bar
    polylines (``bars.polyline3``) carry a joint segment of about 0.0005-0.001
    ft where a bend arc meets a straight leg (the FreeCAD arc end and line
    start do not match).  Its projected length is always under 0.35 of its
    true length, so it used to become its own filled dot (a second row of dots
    about 1.75" from the leg dots) and split the following run.  A segment
    shorter than 1e-3 ft is skipped; the tiny gap it leaves in the next run
    is nothing."""
    pts = bar["pts"]
    dia = bar["dia_in"]
    seq = []   # [kind, points] in bar order: "run" (in-plane) or "dot" (end-on)
    for p, q in zip(pts, pts[1:]):
        L3 = math.dist(p, q)
        if L3 < 1e-3:   # V21: the arc/line joint sliver of the model's polylines
            continue
        a, b = fn(p), fn(q)
        kind = "dot" if math.dist(a, b) < 0.35 * L3 else "run"
        if seq and seq[-1][0] == kind:
            seq[-1][1].append(b)
        else:
            seq.append([kind, [a, b]])
    centre = {i: (sum(p[0] for p in s[1]) / len(s[1]), sum(p[1] for p in s[1]) / len(s[1]))
              for i, s in enumerate(seq) if s[0] == "dot"}
    reach = 4.0 * dia / 12.0
    for i, (kind, run) in enumerate(seq):
        if kind != "run":
            continue
        run = list(run)
        c0, c1 = centre.get(i - 1), centre.get(i + 1)
        if c0 is not None:
            while run and math.dist(run[0], c0) < reach:
                run.pop(0)
            run.insert(0, c0)
        if c1 is not None:
            while len(run) > (1 if c0 is not None else 0) and math.dist(run[-1], c1) < reach:
                run.pop()
            run.append(c1)
        run = [p for j, p in enumerate(run) if j == 0 or math.dist(p, run[j - 1]) > 1e-9]
        if len(run) > 1 and sum(math.dist(a, b) for a, b in zip(run, run[1:])) >= dia / 12.0:
            draw_bar(v, run, dia)
    for c in centre.values():
        v.dot(c, dia / 24.0)


def _seg_dist(p, a, b):
    """Distance from point p to the segment ab."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def _seg_seg_dist(p1, p2, p3, p4):
    """Distance between the segments p1p2 and p3p4 (0 where they cross)."""
    if _segs_cross(p1, p2, p3, p4):
        return 0.0
    return min(_seg_dist(p1, p3, p4), _seg_dist(p2, p3, p4), _seg_dist(p3, p1, p2), _seg_dist(p4, p1, p2))


def _segs_cross(p1, p2, p3, p4):
    """True when the segments p1p2 and p3p4 cross (touching ends do not)."""
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = side(p3, p4, p1), side(p3, p4, p2)
    d3, d4 = side(p1, p2, p3), side(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


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
    (STYLE_GUIDE D5, markup "the horizontal line be removed to indicate a
    shear key").  The snapshot stores the cap top and the foot of the backwall
    as "P" (polyline) records as well as "L" (line) records, so both are cut:
    a record whose segment at ``z`` crosses the key is split around it (each
    run of kept segments is one record again)."""
    out = []
    for rec in edges:
        if rec["t"] not in ("L", "P"):
            out.append(rec)
            continue
        pts = [tuple(p) for p in rec["p"]]
        pieces, cut = [], False   # kept segments (a, b), in drawing order
        for a, b in zip(pts, pts[1:]):
            lo, hi = sorted((a[0], b[0]))
            if not (abs(a[1] - z) < tol and abs(b[1] - z) < tol) or hi <= x0 + tol or lo >= x1 - tol:
                pieces.append((a, b))
                continue
            cut = True
            keep = []
            if lo < x0 - tol:
                keep.append(((lo, a[1]), (x0, a[1])))
            if hi > x1 + tol:
                keep.append(((x1, a[1]), (hi, a[1])))
            pieces += keep if a[0] <= b[0] else [(q, p) for p, q in reversed(keep)]
        if not cut:
            out.append(rec)
            continue
        run = []
        for a, b in pieces:
            if run and math.dist(run[-1], a) < 1e-9:
                run.append(b)
                continue
            if len(run) > 1:
                out.append(dict(rec, t="L" if len(run) == 2 else "P", p=[list(q) for q in run]))
            run = [a, b]
        if len(run) > 1:
            out.append(dict(rec, t="L" if len(run) == 2 else "P", p=[list(q) for q in run]))
    return out


def vline_gapped(v, x, z0, z1, gaps, layer):
    """V19: a vertical centerline at ``x`` from ``z0`` to ``z1`` broken at
    ``gaps`` ((lo, hi) heights: where a leader or a text band crosses it).
    Overlapping or touching gaps are merged, and a piece left shorter than one
    dash pattern of the level's linetype (``fdot.pattern_length``) is dropped,
    because a stub shorter than its pattern plots solid."""
    pat = fdot.pattern_length(fdot.level_attrs(layer)["linetype"], v.sf)
    merged = []
    for a, b in sorted((max(g0, z0), min(g1, z1)) for g0, g1 in gaps if g1 > z0 and g0 < z1):
        if merged and a <= merged[-1][1] + 1e-9:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    pieces, cur = [], z0
    for a, b in merged:
        if a > cur:
            pieces.append((cur, a))
        cur = max(cur, b)
    if cur < z1:
        pieces.append((cur, z1))
    for a, b in pieces:
        if b - a >= pat - 1e-9:
            v.line((x, a), (x, b), layer)


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


def _pack_rows(wants, pitches, bands, step=0.02):
    """Row heights for rows sorted by ``wants`` (ascending): consecutive rows at
    least ``pitches[i]`` apart (pitch between row i and i + 1), no row centre
    inside any open interval of ``bands`` (per row: ``bands[i]`` is a list of
    (lo, hi) centre intervals), and the sum of squared distances to ``wants``
    least (dynamic programming over a grid of ``step`` feet).  None when no
    arrangement exists."""
    n = len(wants)
    span = sum(pitches) + 3.0 * max(pitches or [1.0]) + sum(hi - lo for bb in bands for lo, hi in bb)
    y0 = min(wants) - span
    G = int((max(wants) + span - y0) / step) + 1
    inf = float("inf")
    cost = [[inf] * G for _ in range(n)]
    back = [[-1] * G for _ in range(n)]
    ok = [[not any(lo + 1e-9 < y0 + g * step < hi - 1e-9 for lo, hi in bands[i]) for g in range(G)] for i in range(n)]
    for g in range(G):
        if ok[0][g]:
            cost[0][g] = (y0 + g * step - wants[0]) ** 2
    for i in range(1, n):
        lag = int(math.ceil(pitches[i - 1] / step - 1e-9))
        best, arg = inf, -1
        for g in range(G):
            gp = g - lag
            if gp >= 0 and cost[i - 1][gp] < best:
                best, arg = cost[i - 1][gp], gp
            if ok[i][g] and best < inf:
                cost[i][g] = best + (y0 + g * step - wants[i]) ** 2
                back[i][g] = arg
    g = min(range(G), key=lambda j: cost[n - 1][j])
    if cost[n - 1][g] == inf:
        return None
    out = [0.0] * n
    for i in range(n - 1, -1, -1):
        out[i] = y0 + g * step
        g = back[i][g]
    return out


def callouts(v, items, x_col, side, gap=None, slide=False, spread=None, avoid=None, even=None):
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
    leaders then never run along the bars they point to.  A tip given as
    (x, None) lies at the height of its row (a horizontal leader).  Returns
    the rows placed, in order of height: (height of the first text line,
    number of text lines, heights of the leader tips).

    ``spread=(z_lo, z_hi)`` (V7, markup "spread these annos out vertically
    with more of an equal space distribution ... more row and column like"):
    the rows go at EQUAL pitch across the band, in the order of their
    ``want`` values (the values themselves are ignored); where the pitch
    would be under the minimum the ordinary packing is used.  ``avoid`` is a
    list of (lo, hi) bands (feet, y) that no row's text box may touch (the
    section flags of the plan, V2): the rows are packed round them with
    least movement from their wanted heights.  ``even`` (V7): in ``slide``
    mode, when two consecutive gaps between rows differ by more than
    ``even`` times, the rows are spread at equal pitch between the first and
    the last (all the way, or 3/4, 1/2, 1/4 of the way from their bar
    heights: the first that makes no more leaders cross each other (A11) and
    no more leaders run over more than four drawing lines (A14) than the rows
    at their bars do)."""
    if not items:
        return []
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

    def layout(r, y):
        """(tips, knee) of the row r at height y: a tip given as (x, None)
        lies at the row's own height (a horizontal leader); with ``slide``
        the tips of a bar row slide along their bars."""
        knee = (xk, y)
        tips = [(t[0], y) if t[1] is None else t for t in r["tips"]]
        if r["need"]:
            # the tips stay at the bar ends (a tip slid inward along its bar
            # would cross the bars above it on its way in, A14); the row's
            # height (``lift``) keeps every leader 30 degrees or more off its
            # bar (A3), and the natural spread of the angles to a column of
            # bar ends keeps the arrows apart (A12)
            tips = [(xk - side * max(dx_min, side * (xk - t[0])), t[1]) for t in tips]
        return tips, knee

    def pieces(r, y):
        """The leader pieces of row r at height y as they are drawn: the
        arrows of a fan or of a single leader.  (A column of bar ends is a
        fan too, its arrows splayed from the knee: markup 2026-10-19 round 3
        follow-up, "splay out the leaders for the bars because too geometric
        makes it look like there's some construction on the drawing";
        parallel leaders are for centerlines only, A18.)"""
        tips, knee = layout(r, y)
        return [(t, knee) for t in tips]

    def crossings(ys_):
        """Number of pairs of leader pieces of different rows that properly
        cross at these row heights."""
        segs = []
        for i, (r, y) in enumerate(zip(rows, ys_)):
            segs += [(a, b, i) for a, b in pieces(r, y)]
        n = 0
        for a in range(len(segs)):
            for b in range(a + 1, len(segs)):
                if segs[a][2] != segs[b][2] and _segs_cross(segs[a][0], segs[a][1], segs[b][0], segs[b][1]):
                    n += 1
        return n

    def long_leaders(ys_):
        """Number of leaders (rows) that cross more than four segments of the
        concrete and bar levels (the A14 check) at these row heights."""
        from . import anno_check
        from .cad import segments_cross
        target = [(sg[0], sg[1]) for sg in v.segs if anno_check._is_drawing_level(sg[2])]
        n = 0
        for r, y in zip(rows, ys_):
            worst = max(sum(1 for a, b in target if segments_cross(p, q, a, b) is not None) for p, q in pieces(r, y))
            n += worst > anno_check.LEADER_LINES_MAX
        return n

    def settle(i, r, y):
        """The row's height given a wanted y: the lowest bar row is reached
        from below (never above its bar), the others are lifted to their
        steepness."""
        if i == first_bar:
            return min(y, min(t[1] - n for t, n in zip(r["tips"], r["need"])))
        return lift(r, y)

    ys = []
    first_bar = next((i for i, r in enumerate(rows) if r["need"]), None) if slide else None
    if slide:
        for i, r in enumerate(rows):
            if i == first_bar:
                # the lowest bar row (the bottom bars) is reached from BELOW:
                # its row sits under the bar by the steepness it needs, so its
                # leader descends and never crosses the leaders of the rows
                # above it (A11; the side bars' parallel leaders run level
                # from the bar ends just above); the rows under it (fixed
                # PT. rows) keep their pitch
                y = min(t[1] - n for t, n in zip(r["tips"], r["need"]))
                ys.append(y if not ys else max(y, ys[-1] + pitch(rows[i - 1], r)))
                continue
            y = r["want"] if not ys else max(r["want"], ys[-1] + pitch(rows[i - 1], r))
            ys.append(lift(r, y))
        if even and len(ys) > 2:
            gaps = [b - a for a, b in zip(ys, ys[1:])]
            if any(max(a, b) > even * max(min(a, b), 1e-9) for a, b in zip(gaps, gaps[1:])):
                eq = [ys[0] + (ys[-1] - ys[0]) * i / (len(ys) - 1) for i in range(len(ys))]
                base_x = crossings(ys)
                # the even rows (all the way, then three quarters, a half, a
                # quarter of the way from the rows at their bars), the first
                # that brings no more leaders across each other than the rows
                # at their bars have (A11); the lowest bar row stays below its bar
                for f in (1.0, 0.75, 0.5, 0.25):
                    mix = [a + f * (b - a) for a, b in zip(ys, eq)]
                    if not all(b - a >= pitch(rows[i], rows[i + 1]) - 1e-9 for i, (a, b) in enumerate(zip(mix, mix[1:]))):
                        continue
                    cand = [settle(i, r, y) for i, (r, y) in enumerate(zip(rows, mix))]
                    for i in range(1, len(cand)):
                        cand[i] = max(cand[i], cand[i - 1] + pitch(rows[i - 1], rows[i]))
                    if (crossings(cand) <= base_x and long_leaders(cand) <= long_leaders(ys)
                            and (first_bar is None or cand[first_bar] <= ys[first_bar] + 1e-9)):
                        ys = cand
                        break
    else:
        for i, r in enumerate(rows):
            ys.append(r["want"] if not ys else max(r["want"], ys[-1] + pitch(rows[i - 1], r)))
        shift = (sum(r["want"] for r in rows) - sum(ys)) / len(ys)
        ys = [y + shift for y in ys]
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + pitch(rows[i - 1], rows[i]))
        if spread and len(rows) > 1:
            lo, hi = spread
            eq = [lo + (hi - lo) * i / (len(rows) - 1) for i in range(len(rows))]
            if all(b - a >= pitch(rows[i], rows[i + 1]) - 1e-9 for i, (a, b) in enumerate(zip(eq, eq[1:]))):
                ys = eq
        elif avoid:
            bands = [[(a - r["h"] / 2, b + r["h"] / 2) for a, b in avoid] for r in rows]
            packed = _pack_rows([r["want"] for r in rows], [pitch(rows[i], rows[i + 1]) for i in range(len(rows) - 1)],
                                bands)
            if packed is not None:
                ys = packed
    al = "left" if side > 0 else "right"
    for r, y in zip(rows, ys):
        tips, knee = layout(r, y)
        if len(tips) == 1:
            v.leader([tips[0], knee, (x_col, y)], r["txt"], al)
        else:
            # several bars (a column of side-bar ends included): a fan with
            # splayed arrows (A18 follow-up; A12 keeps them 5 degrees apart)
            v.leader_fan(tips, knee, r["txt"], al)
    # the rows placed: (height of the first text line, number of text lines,
    # the heights of the leader tips)
    return [(y, r["txt"].count("\\P") + 1, [t[1] for t in layout(r, y)[0]]) for r, y in zip(rows, ys)]


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
        # V1 / D12 (markup "Add breaklines for elements that are broken"): a
        # break line wherever the plan clips an element of the context.  The
        # objects whose box crosses a clip line of ``ctx_boxes`` (the strap
        # stubs and the coping stubs behind the backwall, the closure slab and
        # the side copings in front of the cap) get a break line along that
        # clip, over the u-range of the objects cut, 0.1 k beyond them; the u
        # clips (none cut at present: the copings end at the cheek faces)
        # get vertical ones over the drawn v-range.  Only where an element
        # is cut, so EB only.
        if ctx:
            cut = {"back": [], "front": [], "left": [], "right": []}
            for o in S.get("context", {}).values():
                if o["role"] not in ctx_boxes:
                    continue
                cb = ctx_boxes[o["role"]]
                bb = o["bb_ft"]
                ou, ov = sorted((s.u(bb[0]), s.u(bb[3]))), sorted((s.v(bb[1]), s.v(bb[4])))
                if ov[1] < cb[1] or ov[0] > cb[3] or ou[1] < cb[0] or ou[0] > cb[2]:
                    continue    # wholly outside the drawn window: nothing drawn, nothing cut
                if ov[0] < cb[3] - TOL and ov[1] > cb[3] + TOL:
                    cut["back"].append((max(ou[0], cb[0]), min(ou[1], cb[2])))
                if ov[0] < cb[1] - TOL and ov[1] > cb[1] + TOL:
                    cut["front"].append((max(ou[0], cb[0]), min(ou[1], cb[2])))
                if ou[0] < cb[0] - TOL:
                    cut["left"].append((max(ov[0], cb[1]), min(ov[1], cb[3])))
                if ou[1] > cb[2] + TOL:
                    cut["right"].append((max(ov[0], cb[1]), min(ov[1], cb[3])))
            # round 6 (markup "Do a bunch of small breaklines at the straps
            # not one giant one", rule D12): one break line per group of cut
            # objects, not one across the whole bent: the (lo, hi) intervals
            # of a side that overlap or lie within 0.1 k of each other are
            # merged (sorted by lo, swept), and each merged interval gets its
            # own short break line, 0.08 k beyond each end
            def _merged(iv):
                out = []
                for a, b in sorted(iv):
                    if out and a <= out[-1][1] + 0.1 * k:
                        out[-1][1] = max(out[-1][1], b)
                    else:
                        out.append([a, b])
                return out
            for a, b in _merged(cut["back"]):
                small_break(v, (a - 0.08 * k, vb + 0.3), (b + 0.08 * k, vb + 0.3))
            for a, b in _merged(cut["front"]):
                small_break(v, (a - 0.08 * k, vf - 1.5), (b + 0.08 * k, vf - 1.5))
            for key, xb in (("left", uL - 1.5), ("right", uR + 1.5)):
                for a, b in _merged(cut[key]):
                    small_break(v, (xb, a - 0.08 * k), (xb, b + 0.08 * k))
        # bands beside the cap: row a nearer the cap (PT. labels, skew angle),
        # row b (beam labels); the beam centerlines end just beyond row b,
        # where the spacing rows begin (A1, A2).  V3 / D3 (markup "All
        # centerlines should be dashed"): the beam centerlines hold at least
        # one dash pattern (the check's threshold is one pattern): from the
        # bearing line to 0.45 k past the cap face they are 1.0 in at 3/8"
        # against 0.34 in of the pattern, so the 0.6 k of the first round
        # (which does not fit the sheet height together with the lower flags
        # of the elevation) is not needed
        row_a, row_b, beam_ext = 0.15 * k, 0.33 * k, 0.45 * k
        sides = {self.span_side(b) for b in s.bearings}
        v_span_lo = min(vf, min(b["v"] for b in s.bearings)) - (beam_ext if -1 in sides else 0.0)
        v_span_hi = max(vb, max(b["v"] for b in s.bearings)) + (beam_ext if 1 in sides else 0.0)
        y_lo, y_hi = min(v_bot, v_span_lo), max(v_top, v_span_hi)
        ext = 0.25 * k
        # V2 (markups "Pull these out into space and minimize leader line
        # overlaps with drawings", "Plenty of space to move these off to the
        # right outside the drawing", "Too close to other stuff, there is
        # plenty of space"): every label of the right end is one column right
        # of the cheek and of the section flags, texts to the right at
        # x_col = uR + 0.65 k; (tips, text, wanted height) are collected here
        # and set by ``callouts`` once the flags are drawn
        x_col = uR + 0.65 * k
        right = []
        if ctx:
            # the closure slab and the side coping in front of the cap, each
            # tip at the middle of the drawn part of its object: the slab
            # 0.8 ft inside the cap end, the coping strip beside it (the
            # front coping lies beyond the clip: nothing there to point at)
            for n, o in S.get("context", {}).items():
                bb = o["bb_ft"]
                ou, ov = sorted((s.u(bb[0]), s.u(bb[3]))), sorted((s.v(bb[1]), s.v(bb[4])))
                cb = ctx_boxes[o["role"]] if o["role"] in ctx_boxes else None
                if cb is None or ou[1] < 0 or ov[0] >= vf - TOL:
                    continue
                lo, hi = max(ov[0], cb[1]), min(ov[1], vf)    # the part in front of the cap face
                if hi - lo < 0.5:
                    continue
                # (the rows of these two go under the flags, set below; the
                # slab's tip in the upper part of the drawn slab, the coping's
                # in the lower part of its strip, so the two leaders do not cross)
                if o["role"] == "closure":
                    right.append(([(u1 - 0.8, hi - 0.3 * (hi - lo))], "4\" CLOSURE SLAB", lo))
                elif o["role"] == "coping" and ou[0] > 0:
                    right.append(([((max(ou[0], 0.0) + min(ou[1], uR)) / 2, lo + 0.17 * (hi - lo))], "COPING", lo - 0.6))
        # -------------------------------------------- centerlines and beams
        v.line((uL - ext, v_cl), (uR + ext, v_cl), "CL_Major")
        pile_h = 0.45   # V3 / D3 (markup "All centerlines should be dashed"): pile centerlines 0.45 ft past the pile
        for p in s.piles:
            h = p["width"] / 2 + pile_h
            v.line((p["u"], p["v"] - h), (p["u"], p["v"] + h), "CL_Minor")
        labels = [(v_cl, self.cl_name())]
        # round 6 (A21, "Adjust so the leader ends are not so close to each
        # other"): the end bent's bearing line lies 3" from the cap centerline,
        # so the two labels' tips at one x stood 0.09" apart; the bearing line
        # runs 0.3 k further past the cap end and carries its tip out there
        ext_b = ext + (0.3 * k if eb else 0.0)
        for b in s.bearings:
            v.line((uL - ext, b["v"]), (uR + ext_b, b["v"]), "CL_Minor")
            labels.append((b["v"], "BEARING"))
        labels.sort(key=lambda t: t[0])
        xt = uR + 0.5 * ext
        cl_wants = []
        for i, (yy, txt) in enumerate(labels):
            d = 0.0 if len(labels) == 3 and i == 1 else (-1.0 if i == 0 else 1.0)
            w = yy + d * 0.22 * k
            if not eb:
                # pier: four rows (two bearings, the pier centerline, PT. B)
                # between the two flags: the bearing rows 0.2 ft off their
                # lines, the pier centerline row 0.3 ft under its line, PT. B
                # above it (its leader rises off the same line as the pier's
                # falls)
                w = yy + (-0.2 if i == 0 else (-0.3 if len(labels) == 3 and i == 1 else 0.2))
            cl_wants.append(w)
            tip_x = (uR + ext_b - 0.1 * k) if (eb and txt == "BEARING") else xt
            right.append(([(tip_x, yy)], CL + " " + txt, w))
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
            if q[0] > 1e-6 and "AT PGL" not in desc:
                # V2: the right end's labels join the column (the leader
                # tips stay where they were: the cheek top on the cheek, the
                # backwall end on the FFBW, the cap end on the cap
                # centerline); the heights wanted keep the rows in the order
                # that lets the leaders run without crossing
                top = max(cl_wants)
                if "CHEEK WALL" in desc:
                    want = top + 0.6
                elif "BACKWALL AT END" in desc:
                    want = top + 1.3
                elif not eb:   # pier: between the pier centerline row and the upper bearing row
                    want = sorted(cl_wants)[len(cl_wants) // 2] + 0.7
                else:       # cap end on the cap centerline: the row under the centerline rows, so its
                    want = min(cl_wants) - 0.6   # leader leaves the line at an angle, not along it
                right.append(([q], "PT. " + letter, want))
                continue
            if "AT PGL" in desc:
                g, knee = -1, (-0.22 * k, y_r1)
            elif "BACKWALL AT END" in desc:
                knee = (q[0] + g * 0.25 * k, y_r1)
            elif "CHEEK WALL" in desc:
                # the leader leaves the cheek through its inner face below the
                # cheek top, clear of the extension line there (B3)
                # (row r3 above the strap callout of row r2: the two labels
                # stacked, not one line: "PT. A 7~Δ REINF. STRAPS" read as one
                # annotation, A2)
                knee = ((u0 if g > 0 else u1) + g * 0.12 * k, y_r2 + 0.17 * k)
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
            # V6 (markup "Move this slightly so it doesn't look like it's an
            # anno about the dim line"): from the strap stub nearest the PGL on
            # its left, in row r2 (0.17 k lower than before: the text no longer
            # sits against the 9'-9 1/2" dimension row, B9), the text running
            # left between the PT. B knee and the PGL (A1)
            u_s = max(u for u in us if u < -0.5) if any(u < -0.5 for u in us) else us[0]
            knee = (u_s - 0.12 * k, y_r2)
            v.leader([(u_s, vb + 0.25), knee, (knee[0] - 0.12 * k, knee[1])], txt, "right")
        # PGL (A1: kept out of the spacing rows below the beam lines)
        v.line((0, y_lo), (0, y_pgl), "BaseLineSurveyPGL")
        v.text((-0.4 * th, y_pgl - 0.6 * th), "PGL", None, "MIDDLE_RIGHT")
        # ---------------------------------------------------- dimensions
        # B3: the points of each row sit on the features dimensioned
        y1 = max(y_pgl + 0.12 * k, (y_r2 + 0.27 * k) if eb else 0.0)   # (EB: the PT. A row r3 keeps 0.1 k from the row)
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
        yb1 = min(y_lo - 0.2 * k, low_t - 0.2 * k)   # the row's text band clears the lowest linework (A1)
        yb2 = yb1 - 0.28 * k
        # pile spacing first (its extension lines come from inside the cap and
        # would cross the beam spacing texts), beam spacing below it (A1)
        pile_end = [(p["u"], p["v"] - (p["width"] / 2 + pile_h)) for p in s.piles]
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
        # V2: the right end's column of labels, now that the flags are drawn:
        # rows at least 2.1 th apart, none within 0.3 k of a flag box (the
        # text column starts 0.25 k beyond a flag, so a row keeps the rest of
        # the 0.3 k vertically)
        flags = [bx for bx, lab in v.symbols if lab.startswith("flag") and (bx[0] + bx[2]) / 2 > 0]
        avoid = []
        for bx in flags:
            dx = max(0.0, x_col - bx[2])
            dv = math.sqrt(max(0.0, (0.3 * k) ** 2 - dx * dx))
            avoid.append((bx[1] - dv, bx[3] + dv))
        if flags:
            # the slab and coping labels under the lowest flag: their leaders
            # run down and out, below the flag's wedge (A13)
            under = min(bx[1] for bx in flags) - 0.9
            right = [(t, tx, (under if tx.startswith("4\"") else under - 0.6 if tx == "COPING" else w))
                     for t, tx, w in right]
        callouts(v, right, x_col, 1, avoid=avoid)
        x_lab = x_col + 0.4 * th + max(text_extent(t[1], th) for t in right)   # right end of the column's texts
        # direction of stationing (stations increase toward -Y), right of the
        # column of labels and vertically centred on the plan (A5, A7); its
        # text stands left of the arrow line
        sd = -s.up
        L = 1.5
        xa = x_lab + 0.35 * k + 1.45 * th
        ym = (v_top + v_bot) / 2
        v.stationing_arrow((xa, ym - sd * L * k / 2), (0, sd), L)
        v.title((0, yb2 - 0.2 * k), "PLAN", subject_cx=0.0)
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

    def elevation(self, zone, z_break=None, pile_show=0.55):
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
            # (the cheek lugs reach 0.5 ft under the cap: they are drawn whole,
            # D12; only the piles are cut at the window bottom, where their
            # break lobes are)
            for rec in drop_coincident_hidden(S["elev"]):
                layer, lt = layer_for(rec)
                v.record(rec, layer, lt, (-1e4, -1e4 if rec["role"] == "cheek" else z_pile, 1e4, 1e4))
        T = v.xform or (lambda p: p)
        u0, u1 = s.cap_u
        uL, uR = s.outer_u
        zp = T((0, z_pile))[1]
        keep, v.xform = v.xform, None
        # piles: curved break, centerline through, circled number beside the bottom
        circles = []   # centres of the circled pile numbers beside the pile bottoms (pier), for B8
        for p in s.piles:
            w = p["width"]
            v.pile_break(p["u"], zp, w, p["shape"], "PileSteel" if p["shape"] == "pipe" else "PileConc")
            v.line((p["u"], s.cap_bot + 0.6), (p["u"], zp - 0.12 * k), "CL_Minor")
            if z_break:   # pier: beside the pile bottom (the end bent numbers go under the stirrup row)
                circles.append((p["u"] + w / 2 + 0.16 * k, zp + 0.1 * k))
                v.circled_number(circles[-1], p["no"])
        v.xform = keep
        if z_break:
            self._break_lines(v, z_break, s.wall_u[0] - 0.5, s.wall_u[1] + 0.5)
        z_top = extents(S["elev"])[3]
        z_pgl = (max(t[1] for t in s.backwall_top) + 0.48 * k) if s.kind == "EB" else s.cap_top + 0.9
        # the PGL stops at the cap bottom, leaving the space below the cap to
        # the pile embedment value (A1)
        v.line((0, s.cap_bot), (0, z_pgl), "BaseLineSurveyPGL")
        # (the label on the side of the PGL that the section A flag's base and
        # wedge do not reach, A2: the flag extends toward the viewing direction)
        look_a = 1 if s.e1 > 0 else -1
        v.text((-look_a * 0.25 * th, z_pgl), "PGL", None, "BOTTOM_RIGHT" if look_a > 0 else "BOTTOM_LEFT")
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
                dx, dz = 0.25 * k, -0.15 * k
                if s.kind == "EB" and s.cheeks:
                    # V5 (markup "Shift to add more space": PT. K touched the
                    # cheek lug and PT. H): the knee 0.35 k out from the lug's
                    # bottom corner and 0.15 k below the lug bottom, so the
                    # label stands clear of the lug outline and the leader
                    # leaves the lug bottom at an angle, not along it
                    c = min(s.cheeks, key=lambda c: abs(c["u"] - u))
                    kx = (c["u_lo"] - 0.35 * k) if side < 0 else (c["u_hi"] + 0.35 * k)
                    dx = max(0.25 * k, side * (kx - q[0]))
            else:
                # cap bottom: a short run, so an inward label stops before the
                # hidden pile lines (A1)
                dx, dz = (0.15 * k if inward else 0.25 * k), -0.25 * k
            if side > 0 and not inward and z >= s.cap_bot - 1.0:
                self._right_pts.append(([q], "PT. " + letter, q[1] + dz))
                continue
            # B8 (markup "No need for the annotation leaders to be so close to
            # the circled number. There's plenty of space."): a label whose knee
            # would fall within 0.3 k of a circled pile number moves up and out
            if any(math.dist((q[0] + side * dx, q[1] + dz), c) < 0.3 * k for c in circles):
                dx, dz = 0.35 * k, 0.25 * k
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
                # A1: the note is centred in the wall band above the removed
                # band (wall top to the upper break line), in drawn position;
                # centred on the whole drawn wall it sat on the break line
                keep, v.xform = v.xform, None
                v.mtext((pm, (s.wall_top + z_break[0]) / 2), "PIER WALL\\P3'-0\" THICK\\P(PROVISIONAL)", attach=5)
                v.xform = keep
        p = max(s.piles, key=lambda q: q["u"])
        xe = p["u"] + p["width"] / 2
        desc = ("18\" SQUARE PRESTRESSED\\PCONCRETE PILE (TYP.)" if p["shape"] == "square"
                else "20\" %s STEEL PIPE PILE (TYP.)" % "Ø")
        # B8: the tip on the last pile's right face just above the pile bottom,
        # the knee 0.55 k beyond the cap end and 0.35 k under the pile bottom,
        # the text to the right; the tip drops until the leader clears every
        # circled pile number by 0.15 k
        if circles:
            knee = (uR + 0.55 * k, zp - 0.35 * k)
            zd = zp + 0.12 * k
            while zd > zp - 0.2 * k and any(_seg_dist(c, (xe, zd), knee) < 0.15 * k for c in circles):
                zd -= 0.02 * k
        else:
            # end bent: no circled numbers beside the piles.  The tip stands on
            # the pile's outer face 0.35 ft above the cap bottom, above the place
            # where the pointer of the embedment value leaves the pile (the
            # value's pointer then never crosses this leader, which runs on
            # above the value's text; B7, "leaders cross leaders")
            zd = s.cap_bot + 0.35
            # (V5: the knee under the PT. L row of the right column by 2.4 text
            # heights, so the two-line description neither meets that label
            # nor crosses its leader)
            z_pl = min([w for _t, _x, w in self._right_pts if w < s.cap_bot] or [zp])
            knee = (uR + 0.3 * k, min(zp - 0.12 * k, z_pl - 2.4 * th))
        keep, v.xform = v.xform, None
        v.leader([(xe, zd), knee], desc, "left")
        v.xform = keep
        desc_leg = ((xe, zd), knee)   # the pile description's leader: the embedment value keeps off it (A1)
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
            # V4 (markup "All these leaders are overlapping the text": the
            # pulled 2 1/4" / 3 1/4" values under the stirrup row sat at the
            # height of the circles and their pointers ran through them): the
            # circles under the row, below the pulled values (V8 follow-up:
            # 0.5 k under the row, not 0.6 k: the value bottoms stand 0.19 k
            # under the row, so the circles' tops still clear them by 0.2 k;
            # see the title note below)
            for q in s.piles:
                v.circled_number((q["u"] + off, z_row - 0.5 * k), q["no"])
            p = max(s.piles, key=lambda q: q["u"])
            xd = p["u"] + 0.55
            txt = fdot.ft_in(p["top"] - s.cap_bot) + "\\P(MIN.)"
            bw = text_w(v, txt) + 0.4 * th
            land, mgn = 0.12 * k, 0.1 * k
            wide = [(a, b) for a, b in zip(self._ext_below, self._ext_below[1:]) if b - a >= bw + land + 2 * mgn]
            out_gaps = [g for g in wide if g[0] >= p["u"] + p["width"] / 2 - 0.01]
            # (the space just inboard of the last pile when the pile description's
            # leader runs through the outboard spaces)
            in_gaps = sorted((g for g in wide if g[1] <= p["u"] - p["width"] / 2 + 0.01), key=lambda g: -g[0])
            z_mid = (zp + z_row + (1.4 + 1.67) * th) / 2   # between the pile bottoms and the run texts
            hh = 0.5 * (1.4 + 1.67) * th + 0.3 * th

            def clear_of_desc(g):
                """True when the pile description's leader (drawn above) stays
                off the value's text box in this space (A1)."""
                box = (g[0] + mgn + land - 0.3 * th, z_mid - hh, g[0] + mgn + land + bw + 0.3 * th, z_mid + hh)
                return (cad_clip(desc_leg[0], desc_leg[1], box) is None
                        and all(b[0] > box[2] or b[2] < box[0] or b[1] > box[3] or b[3] < box[1]
                                for b in self._below_boxes))
            gap = next((g for g in out_gaps if clear_of_desc(g)), None)
            if gap is None:   # the leader runs through the outboard spaces: the value inboard of the last pile
                gap = next((g for g in in_gaps if clear_of_desc(g)), out_gaps[0] if out_gaps else None)
            if gap:
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
        # breaks (pier), the title under them: the end bent flags' bottoms at
        # z_row - 0.6 k, so ``yt`` 0.05 k under them)
        # V8 (markup "Shift up a bit to create space between drawing and title":
        # the section flags under the pile numbers nearly touched the title):
        # the title anchors 0.25 k lower under ``yt`` (0.2 k before), so it
        # stands 0.36 k clear of the lowest annotation (E6, at least 0.3 k).
        # The end bent sheets have no height to give (plan, elevation and the
        # 0.1 in between them fill the window), so the room is made inside
        # the elevation: the flags under the row stand at z_row - 0.6 k (0.85
        # k before) and the pile circles at z_row - 0.5 k (0.6 k), each still
        # 2 text heights or more clear of the pulled values above them.
        # (the pier sheet's stack is just as full: its title 0.2 k lower than
        # before, still 0.38 k under the flags)
        yt = min(zp - 0.42 * k, z_row - 0.65 * k if z_row is not None else zp)
        v.title((0, yt - (0.45 if z_row is not None else 0.4) * k), "ELEVATION",
                "(LOOKING BACK STATION)" if s.key == "EB1" else "(LOOKING AHEAD STATION)", subject_cx=0.0)
        # round 6 (markup "Shift note down to make space between it and the
        # number": the footnote sat right under the circled pile number 4;
        # rule A2): 0.3 k under ``yt`` (0.1 k before); the title is centred
        # and the footnote at the left, so they do not meet
        self.legend_at = (x2 - 0.1 * k, yt - 0.3 * k)
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
        # (V4/V8: the end bent flags at z_row - 0.6 k, beside the pile numbers
        # at z_row - 0.5 k: a flag's tick rises 0.25 k from there, so its top
        # stands 0.16 k under the pulled values; the letters clear the circles
        # by A8's 0.5 ft offset)
        z_lo = (z_row - 0.6 * k) if (s.kind == "EB" and z_row is not None) else (zp - 0.3 * k)
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
        self._below_boxes = []   # boxes of the callouts under the cap (the embedment value keeps off them)
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
            below.append(([tip], "%d~%s\\P(TYP.)" % (per, b["mark"])))   # V5: two lines
        ends_b = s.bars_of(family="cap_end")
        end_call = None   # the cap end U-bar callout, drawn after the PT. column (B9)
        if ends_b:
            marks = list(OrderedDict.fromkeys(b["mark"] for b in ends_b))
            txt = " & ".join("%d~%s" % (len([b for b in ends_b if b["mark"] == m]) // 2, m) for m in marks)
            # B9 (markup "The leaders here have too much overlap with drawing
            # items and it's hard to see what they point to. Reposition the
            # annotation to minimize overlap and have wider distances between
            # the separate leaders"): the callout under the cap's right end,
            # its knee 0.3 k beyond the end and 0.55 k under the cap bottom
            # (below the "PT. D" row), one tip per mark on the lower leg of the
            # U-bar nearest the end, tips apart and no leader crossing the
            # "PT. D" leader
            # A14 / A11 (round 2): one tip, at the outer base corner of the
            # end U-bar nearest the cap end, reached from under the cap end
            # (the leader crosses the cap bottom line only, below the bottom
            # bars and clear of the side-bar callout and "PT. D"); the text
            # names both marks
            b = max(ends_b, key=lambda x: (round(sum(s.u(p[0]) for p in x["pts"]) / len(x["pts"]), 1),
                                            -min(p[2] for p in x["pts"])))
            pts = proj(b, fn)
            zmin = min(q[1] for q in pts)
            xl = [q[0] for q in pts if q[1] < zmin + 0.02]
            end_call = ((max(xl) - 0.15, zmin), txt + " (EA. END)")
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
            chain_dims(v, xs, texts, z_bw, zc + 0.3 * k)   # (0.3 k over the cheek tops: sheet height)
        # one column right of the right end: the bar callouts with leaders
        # meeting the bars at an angle (A3) and the PT. labels of that end
        # V5 (the rows keep 0.3 k from the cheek lug outline) and V7 (markup
        # "spread these annos out vertically with more of an equal space
        # distribution"): the column starts 0.3 k beyond the cap end, and
        # where two consecutive gaps of the rows differ by more than 2.5 times
        # the rows are spread at equal pitch
        callouts(v, right + getattr(self, "_right_pts", []), ends[1] + 0.3 * k, 1, slide=True, even=2.5)
        if end_call:
            # under the cap end, below the "PT. D" row: knee 0.3 k beyond the
            # end and 0.55 k under the cap bottom, the leader rising into the
            # cap through its bottom line to the U-bar base
            tip, txt = end_call
            v.leader([tip, (ends[1] + 0.3 * k, s.cap_bot - 0.55 * k)], txt, "left")
        if below:
            # just below the cap, above the pile numbers (A8); each text in a
            # gap between the extension lines of the stirrup row (A1)
            # V5 (markup "Hard to see leader make 2 lines of text for fit",
            # B4-8: the one-line "3~5C (TYP.)" sat in a gap two spaces right
            # of its tip, so the leader ran vertically along the stirrup
            # legs; rules A3, A1): the text in two lines, in the FIRST gap
            # between the extension lines at or right of the tip (0.2 k) that
            # holds it (the landing clear of the extension line), and the
            # angled piece leaving the tip at 30 to 60 degrees from the
            # vertical, so it never runs along a bar.  The two-line box (its
            # centre 0.3 k under the cap bottom) stands 0.4 th above the top
            # of the stirrup row's two-line run texts.
            hb = 0.5 * (1.4 + 1.67) * th      # half height of the registered two-line box
            zc = s.cap_bot - 0.3 * k          # centre of the two-line box
            # (the row's two-line run texts stand ABOVE their dimension line:
            # from 0.2 th over it up to 0.2 + 1.4 + 1.67 th)
            run_top = (z_row + 0.2 * th + (1.4 + 1.67) * th) if z_row is not None else None
            if z_row is not None and zc - hb < run_top + 0.4 * th:
                zc = s.cap_bot - 0.26 * k     # V5: no room under the cap for the first choice
            for tips, txt in below:
                tw = text_w(v, txt)
                land = (0.1 if len(tips) == 1 else 0.16) * k
                zb = zc + 0.5 * (1.0 + fdot.LINE_PITCH * txt.count("\\P")) * th - 0.5 * th   # landing level: first line's middle
                tip = max(tips, key=lambda t: t[0])
                dz = tip[1] - zb
                # the knee at 30 to 60 degrees from the vertical off the (last) tip, 0.2 k right of it at least
                kx_lo = tip[0] + max(0.2 * k, dz * TAN30)
                kx_hi = tip[0] + max(0.2 * k, dz * math.tan(math.radians(60.0)))
                pref = kx_lo + land + 0.4 * th    # text start for the shallowest knee
                x_txt = None
                for a, b in zip(ext_below, ext_below[1:]):
                    lo = max(a + 0.02 * k + land + 0.4 * th, pref)
                    hi = min(b - 0.02 * k - tw, kx_hi + land + 0.4 * th)
                    if hi >= lo:
                        x_txt = lo
                        break
                if x_txt is None:   # no gap holds it (pier: no stirrup row below): beside the tip
                    x_txt = pref
                tx = x_txt - 0.4 * th - land
                knee = (tx, zb)
                self._below_boxes.append((x_txt, zc - hb, x_txt + tw, zc + hb))
                if len(tips) == 1:
                    v.leader([tips[0], knee, (x_txt - 0.4 * th, zb)], txt, "left")
                else:
                    v.leader_fan(tips, knee, txt, "left")
                zc -= 2 * hb + 0.4 * th
        return z_row, z_up

    # ----------------------------------------------------------- sections
    def section(self, zone, tag, letter, subtitle):
        s = self.s
        S = s.S
        sec = S["sections"][tag]
        xc = sec["x_global_ft"]
        depth = S["section_depth_ft"]
        self._fan_rows = []   # heights of the fan callouts drawn inside the cap (the cover value keeps off them)
        v = View(self.doc, zone, "%s SECTION %s" % (s.key, letter))
        th, k = v.th, IN * v.sf
        eb = s.kind == "EB"
        cs = s.cap_s
        ccl = (cs[0] + cs[1]) / 2
        pile_show = 0.6   # (V19: the stub the centerline label points to is a full dash pattern long, so the pile stub is shorter)
        z_lo = s.cap_bot - pile_show
        # context: the MSE wall in front; no landing or approach slab (D4);
        # the soil reinforcing strap is drawn on its own below (D6)
        # B3 (markup "make these details smaller to fit the MSE walls ... without
        # the weird cutoffs or do a breakline at the 4" closure slab and leave
        # the details the same size"): the end bent sections show the cap, the
        # backwall and the start of the closure slab only, with a break line
        # through the slab 1.2 ft beyond the cap face; no coping, no MSE wall
        # (D4).  The pier sections are unchanged.
        slab_len = 1.2                      # closure slab drawn beyond the cap face
        if s.key == "EB1":
            xr = (cs[0] - 0.15, cs[1] + slab_len + 0.1)
        elif s.key == "EB2":
            xr = (cs[0] - slab_len - 0.1, cs[1] + 0.15)
        else:
            xr = (cs[0] - 0.35, cs[1] + 0.35)
        skip_roles = ("landing", "strap") + (("coping", "mse") if eb else ())
        # back (backwall or left) side and front side fs (+1 right, -1 left)
        fs = -1 if s.key == "EB2" else 1
        x_front, x_back = (cs[1], cs[0]) if fs > 0 else (cs[0], cs[1])
        edges = [r for r in sec["edges"] if r["role"] not in skip_roles]
        # V2 (markup "Where are the tops of the backwalls?", Sections A-A, B-B
        # and C-C of End Bent 1, C-C of End Bent 2; rules D4, D13, D14): the
        # extractor tags the backwall's top edge "landing" where the landing
        # slab sits on it (its outline shares the edge) and "landing" edges
        # are not drawn (D4), so the two faces of the cut backwall rose to the
        # top with no edge joining them.  The model's backwall top is two
        # planes sloping along the bent to the crown and LEVEL across the
        # wall thickness (both faces share the same z at the ends and at the
        # crown; markup round 3 follow-up "Check the model for all the
        # backwalls, there should be a slope ... across the thickness":
        # there is none, a MODEL CHECK note says so).  Beyond the cut the
        # top rises toward the crown, so the face edges of the section carry
        # the silhouette of that rise (up to 0.025 ft above the cut), which
        # read as a sloped top.  D14: a section shows the cut outline only:
        # the top of the cut backwall is the FFBW top edge of the model at
        # the cut (``s.backwall_top`` interpolated at the cut's u), the face
        # edges are trimmed to it and one level line joins them.
        if eb:
            u_cut = s.u(xc)
            top = s.backwall_top
            z_cut = None
            for (ua, za), (ub, zb) in zip(top, top[1:]):
                if min(ua, ub) - 1e-6 <= u_cut <= max(ua, ub) + 1e-6 and abs(ub - ua) > 1e-9:
                    z_cut = za + (zb - za) * (u_cut - ua) / (ub - ua)
                    break
            if z_cut is not None:
                trimmed = []
                for r in edges:
                    if r["role"] != "backwall" or not r["vis"] or r["t"] not in ("L", "P"):
                        trimmed.append(r)
                        continue
                    pts = [list(p) for p in r["p"]]
                    if all(p[1] <= z_cut + 1e-6 for p in pts):
                        trimmed.append(r)
                        continue
                    if all(p[1] >= z_cut - 1e-6 for p in pts):
                        continue   # wholly above the cut top: the silhouette beyond the cut
                    # a two-point face edge crossing the cut top: keep the part below
                    if len(pts) == 2:
                        lo, hi = sorted(pts, key=lambda p: p[1])
                        t = (z_cut - lo[1]) / (hi[1] - lo[1])
                        cut_pt = [lo[0] + t * (hi[0] - lo[0]), z_cut] + list(lo[2:])
                        trimmed.append(dict(r, p=[lo, cut_pt]))
                    else:
                        trimmed.append(dict(r, p=[p for p in pts if p[1] <= z_cut + 1e-6]))
                edges = trimmed
                bw_vis = [r for r in edges if r["role"] == "backwall" and r["vis"] and r["t"] in ("L", "P")]
                top_a, top_b = (x_back, z_cut), (s.ffbw_s, z_cut)
                joined = any(any(
                    (math.dist(a[:2], top_a) <= 0.005 and math.dist(b[:2], top_b) <= 0.005)
                    or (math.dist(a[:2], top_b) <= 0.005 and math.dist(b[:2], top_a) <= 0.005)
                    for a, b in zip(r["p"], r["p"][1:])) for r in bw_vis)
                if not joined and bw_vis:
                    edges.append(dict(bw_vis[0], t="L", p=[list(top_a), list(top_b)], vis=1, role="backwall"))
        straps = [r for r in sec["edges"] if r["role"] == "strap" and r["vis"]] if eb else []
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
        skip_top = ("strap",) + (("coping", "mse") if eb else ())
        tops = [p[1] for r in sec["edges"] if r["vis"] and r["role"] not in skip_top
                for p in edge_points(r) if xr[0] <= p[0] <= xr[1]]
        # V18 (the pier's C-C with the pedestal on top was 0.54 in taller than
        # A-A and B-B, so their titles did not line up): the top is the tallest
        # of the visible tops of ALL the sections of the support, each within
        # the same window, so the dimension rows, bearing leaders and centerline
        # tops of A-A, B-B and C-C stand at one height
        tops_all = [p[1] for sx in S["sections"].values() if isinstance(sx, dict) and "edges" in sx
                    for r in sx["edges"] if r["vis"] and r["role"] not in skip_top
                    for p in edge_points(r) if xr[0] <= p[0] <= xr[1]]
        z_hi = max(tops_all or tops) + 0.05
        # first dimension row above the section and the second (the pier's
        # bearing leaders run between the section and the first row, B10)
        yt1 = z_hi + 0.35 * k
        yt2 = yt1 + 0.3 * k
        box = (xr[0], z_lo, xr[1], z_hi)
        # B3: the closure slab is clipped 1.2 ft beyond the cap face
        dbox = box
        if eb:
            x_slab = x_front + fs * slab_len
            dbox = (xr[0], z_lo, x_slab, z_hi) if fs > 0 else (x_slab, z_lo, xr[1], z_hi)
        draw_edges(v, edges, box=dbox, hidden=False)
        if key:
            # B2 (markup "construction joint shape should be dashed"): the
            # keyway profile is the dashed construction joint, not a solid line
            v.pl(key, "SubStrConc_h")
        al_f = "left" if fs > 0 else "right"     # texts on the front side
        # the end bent weather closure (D-044): the rain closure slab between
        # the cap face and the break
        clos = [r for r in edges if r["role"] == "closure" and r["vis"]]
        if clos:
            ce = extents(clos)
            # label above the slab 0.6 ft beyond the cap face, in the open
            # space above it (A1)
            # (two lines, hanging from the landing: the one-line label would
            # run into the neighbouring section's dimension column, and the
            # side-bar callout row above it is lifted clear, below)
            # (V4 follow-up: the cover value in two lines no longer reaches as
            # far right as the one-line text did, so this label is now the
            # section's rightmost text and its row-mate's left dimension
            # column ran into it (B4-2/B4-9 "draws over"); the tip 0.3 ft
            # beyond the face keeps the label inside the slab's break)
            tip = (x_front + fs * 0.3, ce[3])
            knee = (tip[0] - fs * 0.1 * k, ce[3] + 0.3 * k)
            v.leader([tip, knee, (knee[0] + fs * 0.12 * k, knee[1])], "4\" CLOSURE\\PSLAB", al_f)
            # B3: the break line through the slab (markup "do a breakline at
            # the 4" closure slab")
            v.break_line((x_slab, ce[1] - 0.06 * k), (x_slab, ce[3] + 0.06 * k))
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
        # B11 (markup "we need a breakline at 1 for the pier wall"): the pier
        # wall stub cut by the window bottom gets a break line across it where
        # no pile is cut there (D2: a break only where something is broken)
        if not eb:
            wall = [p for r in edges if r["role"] == "pier_wall" and r["vis"] for p in edge_points(r)]
            if wall:
                wl = max(min(p[0] for p in wall), box[0])
                wr = min(max(p[0] for p in wall), box[2])
                if piles:
                    # D12: where a pile is cut inside the wall stub (Section B-B)
                    # its own break lobes are there; the wall's break line
                    # runs either side of them, to the wall faces
                    for xa, xb in ((wl - 0.08 * k, pe[0] - 0.08 * k), (pe[2] + 0.08 * k, wr + 0.08 * k)):
                        if xb - xa > 0.1 * k:
                            v.break_line((xa, z_lo), (xb, z_lo))
                else:
                    v.break_line((wl - 0.08 * k, z_lo), (wr + 0.08 * k, z_lo))
        # centerlines
        z_ccl = s.cap_top + 0.5          # top of the drawn cap centerline
        if eb:
            # V7: the four labels of the backwall's bridge side stand in one
            # column, rows at equal pitch from just under the backwall top to
            # just over the cap top; the CL BEARING row is the top one, so the
            # bearing centerline runs a little above it
            z_hi_row = max(t[1] for t in s.backwall_top) - 0.35 * k
            z_lo_row = s.cap_top + 0.45 * k
            z_bct = z_hi_row + 0.12 * k  # top of the drawn bearing centerline
        else:
            # B10: the bearing centerlines run up to just over the upper of
            # the two parallel bearing leaders (y_a), under the first row
            # (V19: the farther bearing's leader is the upper one, so the
            # nearer bearing's centerline ends under it with no gap that would
            # leave a stub shorter than a dash pattern, and the leaders'
            # rows are 0.16 k apart)
            y_a = yt1 - 0.15 * k
            y_b = y_a - 0.16 * k
            z_bct = y_a + 0.1 * k
        # the bottom bar row (below the pile where one is cut) and the
        # centerline label under it, clear of the values pulled out below the row
        if piles:
            yb1, z_cll = z_lo - 0.25 * k, z_lo - 0.52 * k
        elif eb:
            yb1 = s.cap_bot - 0.45 * k
            z_cll = min(z_lo - 0.3 * k, yb1 - 0.45 * k)
        else:
            # B11 (markup "shift the dims down ... too close to the pier wall
            # edges"): the pier's bottom bar row sits well under the break
            yb1 = z_lo - 0.3 * k
            z_cll = yb1 - 0.45 * k
        # the cap centerline, broken through the bottom row's text band (the
        # middle value straddles the centerline; A1) and, on the pier, through
        # each bearing leader that crosses it (B10: "cross the other
        # centerline in a dash area so it's clear they are distinct")
        gaps = []
        if not eb:
            # the leaders come from the right of the section: one crosses the
            # cap centerline when its bearing lies left of it (the farther
            # bearing, smaller s, has the upper leader y_a)
            # (V22: one leader at y_a for both bearings)
            gaps = [(y_a - 0.06 * k, y_a + 0.06 * k)] if min(b["s"] for b in s.bearings) < ccl - 1e-6 else []
        # V19 (a stub shorter than its dash pattern plots solid): adjacent gaps
        # are merged and no piece shorter than one pattern is left; the stub
        # under the bottom row that the centerline label points to is made a
        # full pattern long (the label drops to suit)
        pat_major = fdot.pattern_length(fdot.level_attrs("CL_Major")["linetype"], v.sf)
        z_cll = min(z_cll, yb1 + 0.09 * k - 1.05 * pat_major)
        vline_gapped(v, ccl, yb1 + 0.35 * k, z_ccl, gaps, "CL_Major")
        v.line((ccl, z_cll - 0.12 * k), (ccl, yb1 - 0.03 * k), "CL_Major")
        v.leader([(ccl, z_cll), (ccl + fs * 0.3 * k, z_cll)], self.cl_name(), al_f, cl=True)
        if eb:
            for b in s.bearings:
                v.line((b["s"], s.cap_top - 0.2), (b["s"], z_bct), "CL_Minor")
            # (the CL BEARING label is the top row of the backwall column, below)
        else:
            self._pier_bearing_leaders(v, s.bearings, cs[1] + 0.3 * k, y_a, y_b, z_bct, ccl)
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
        self._bottom_pair = None    # (near dot, far dot) of a bottom-bar group split by a pile (round 6)
        cap_dots = {m: [p for p, _ in pts] for m, pts in dots.items()}
        for mark, ps in cap_dots.items():
            e = s.table[mark]
            if e["family"] == "cap_long":
                near = sorted(ps, key=lambda p: -fs * p[0])
                if e["subtype"] == "side":
                    col = [p for p in ps if abs(p[0] - near[0][0]) < 0.02]
                    col = sorted(col, key=lambda p: p[1])
                    if clos:
                        # the closure slab label stands on the slab right under
                        # this row, so the row sits 0.55 k above the slab top
                        # (A1: the label's leader must not cross its text)
                        items.append((col, "%d~%s (EF)" % (len(col), mark),
                                      max(sum(p[1] for p in col) / len(col), extents(clos)[3] + 0.55 * k)))
                    else:
                        items.append((col, "%d~%s (EF)" % (len(col), mark)))
                elif e["subtype"] == "bottom":
                    # V9 (markup "Don't do these kind of almost parallel
                    # leaders"): one tip, on the bottom bar nearest the text
                    # (the outermost dot on the text side), no fan
                    # round 6 (markup "Do a double arrow leader and say 2~9A2
                    # (EF)", rule A12): where a pile is cut in the window and
                    # the bars lie on both sides of it (the pier's B-B: two at
                    # each side of the pile), the callout counts the bars of
                    # the near (front) side only, "2~9A2 (EF)", its leader
                    # runs through the near dot to the far dot of that group
                    # with a second arrowhead (drawn after the callouts)
                    near_group = []
                    if piles:
                        if (any(p[0] < pe[0] for p in ps) and any(p[0] > pe[2] for p in ps)):
                            near_group = sorted((p for p in ps if fs * (p[0] - ccl) > 0),
                                                key=lambda p: -fs * p[0])
                    if near_group:
                        items.append(([near_group[0]], "%d~%s (EF)" % (len(near_group), mark)))
                        self._bottom_pair = (near_group[0], near_group[-1])
                    else:
                        items.append(([near[0]], "%d~%s" % (len(ps), mark)))
                else:
                    items.append(([near[0]], "%d~%s" % (len(ps), mark)))
            elif e["family"] == "cap_added":   # inside the cap, fanned up to a knee beside the group
                tips = sorted(ps, key=lambda p: -fs * p[0])
                # the knee beyond the frontmost dot (A10: every arrow leaves
                # the text away from it), the text running toward the front
                # face at a height midway between the two lowest side bars of
                # that face, so it ends clear of their dots and of the
                # side-bar fan (A2, A11)
                front_side = sorted(p[1] for m2, ps2 in cap_dots.items()
                                    if s.table[m2]["family"] == "cap_long" and s.table[m2]["subtype"] == "side"
                                    for p in ps2 if fs * (p[0] - ccl) > 0)
                zk = ((front_side[0] + front_side[1]) / 2 if len(front_side) >= 2
                      else max(p[1] for p in tips) + 0.4 * k)
                knee = (tips[0][0] + fs * 0.08 * k, zk)
                self._fan_rows.append(zk)
                v.leader_fan(tips, knee, "%d~%s" % (len(ps), mark), "left" if fs > 0 else "right")
            elif e["family"] == "pedestal":
                near = max(ps, key=lambda p: fs * p[0])
                items.append(([near], "%d~%s" % (len(ps), mark)))
        hoop = None
        # highest side-bar dot on the front face (the "4~6A3 (EF)" fan)
        side_z = None
        for m, ps in cap_dots.items():
            if s.table[m]["family"] == "cap_long" and s.table[m]["subtype"] == "side":
                xn = max(ps, key=lambda p: fs * p[0])[0]
                side_z = max([p[1] for p in ps if abs(p[0] - xn) < 0.02] + ([side_z] if side_z is not None else []))
        for rb, pts in shapes:
            fam = rb["family"]
            if fam == "cap_trans":
                hoop = (rb, pts)
                # B4 (markup "Leaders unnecessarily cross other leaders"): the
                # hoop callout's tip on the outer leg above the top side bar,
                # so its leader does not cross the side-bar fan below it
                zm = s.cap_bot + 0.62 * (s.cap_top - s.cap_bot)
                if side_z is not None:
                    zm = min(side_z + 0.25, max(q[1] for q in pts) - 0.25)
                tip = (max((q[0] for q in pts), key=lambda x: fs * x), zm)
                items.append(([tip], rb["mark"]))
            elif fam == "pedestal":
                # round 6 (markup "Adjust so the leader ends are not so close
                # to each other. There are other parts of the steel we can
                # point to to spread the leaders out", Section C-C; rule A11):
                # the "4F1" tip sat on the top bend of the in-plane U-bar,
                # where the nearest dot of "5~4F2" also lies.  The tip moves
                # along the bar's top run to the point 0.7 ft inboard of the
                # run's front end (between the second and third dot from the
                # front), and the callout is given a row above the dots' row
                # so its leader comes from above (3.2 th over the run: at 2.4
                # th the leader ran 11 degrees off the pedestal top and
                # crossed its top corner)
                z_max = max(p[1] for p in pts)
                run = [p for p in pts if p[1] > z_max - 0.01]
                front_end_x = max((p[0] for p in run), key=lambda x: fs * x)
                tip = (front_end_x - fs * 0.7, z_max)
                items.append(([tip], rb["mark"], z_max + 3.2 * th))
        # V3 (markups "Move to make the leader cross less drawing items" and
        # "Adjust so leader doesnt cross so many drawing items", B4-10 and
        # B4-3; rules A14, A11): in Section C-C the pedestal stands on the
        # cap between the label column and the backwall.  The joint callout
        # stays in the backwall column (follow-up markups "Don't call out the
        # construction joint at the pedestals", "Put the construction joint
        # anno like this": its row between the 5D1 and FFBW rows, the leader
        # level to just before the FFBW face and then down to the keyway, so
        # it crosses no pedestal bar; see ``ped_here`` below)
        ped_here = eb and (any(rb["family"] == "pedestal" for rb, _ in shapes)
                           or any(s.table[m]["family"] == "pedestal" for m in cap_dots))
        rows_front = callouts(v, items, x_front + fs * 0.25 * k, fs)
        if self._bottom_pair:
            # round 6 ("Do a double arrow leader", A12/A18): the bottom bars
            # split by the pile: the leader goes on through the near dot to
            # the far dot of the near group, with an arrowhead there too
            a, b = self._bottom_pair
            v.line(a, b, "Leader")
            v.arrowhead(b, a, "Leader")
        # backwall: horizontals cut (dots), verticals in plane.  On the bridge
        # side the cap and bearing centerlines and the extension lines (B3)
        # divide the space above the cap into strips; each label keeps to one
        # (A1): FFBW between the FFBW and the cap centerline, the others
        # between the bearing centerline and the cap front face
        bw = [(rb, pts) for rb, pts in shapes if rb["family"] == "backwall"]
        if eb:
            xbr = s.bearings[0]["s"]
            # V7 (markup "There is plenty of space here to spread these annos
            # out vertically with more of an equal space distribution. Get
            # better at organizing annos so they are more row and column
            # like"): CL BEARING, 5D1 (EF), FFBW and CONST. JOINT in one column,
            # texts at x_col = xbr + 0.4 k, rows at equal pitch between
            # z_hi_row (CL BEARING on top) and z_lo_row (CONST. JOINT at the
            # bottom).  The first three leaders are horizontal, tips on their
            # object at the row's height (the bearing centerline, the
            # front-face vertical, the FFBW); the joint's leader is angled
            # from the keyway at mid thickness of the backwall (D5), its knee
            # beyond the tip, so the bend is obtuse
            col_items = [([(xbr, None)], CL + " BEARING", 3.0)]
            if bw:   # the front-face vertical, labelled toward the FFBW side
                rb, pts = max(bw, key=lambda t: fs * t[1][0][0])
                lab = "%s (EF)" % rb["mark"]
                if rb.get("dist", 0.0) > 0.25 + 1e-6:
                    # V14: the bar of the section plane is the nearest one
                    # within 1'-3" beyond the cut; more than 3" behind it, say so
                    lab += "\\P(%s BEYOND CUT)" % fdot.ft_in(rb["dist"], 0.25)
                col_items.append(([(pts[0][0], None)], lab, 2.0))
            col_items.append(([(s.ffbw_s, None)], "FFBW", 1.0))
            # the joint's tip ON the joint line (markup 2026-10-19 round 3
            # follow-up: "it should point to the line where the two concrete
            # surfaces interface"): the corner where the straight joint piece
            # meets the keyway on the FFBW side (D5); the joint row is the
            # bottom row, except with a pedestal in the cut (C-C), where it
            # is drawn by hand below between the 5D1 and FFBW rows
            x_key = x_back + fs * 8 * IN
            cj_txt = "CONST. JOINT\\P(SEE DETAIL \"A\")"
            if not ped_here:
                col_items.append(([(x_key, s.cap_top)], cj_txt, 0.0))
            # (deviation from the 0.4 k beyond the bearing centerline: there the
            # texts run across the extension lines of the dimension rows at the
            # cap front face, A1; the column stands on the cap callouts' column,
            # 0.25 k beyond the front face, one column for all the labels.  The
            # bottom row stays 2.4 text heights above any callout row that
            # stands over the cap top (the pedestal bars of section C-C))
            over = [y for y, _n, _tz in rows_front if y > s.cap_top - 0.3]
            if over:
                # (the two-line CONST. JOINT hangs 1.75 text heights below its
                # row; with a pedestal (V3) the bottom row is the one-line FFBW)
                z_lo_row = max(z_lo_row, max(over) + (2.4 if ped_here else 3.4) * th)
            # V2b (A3, Sections C-C: the horizontal FFBW leader lay 0.02 ft
            # over the top line of the bearing pad along the pad's whole
            # width): the bottom row keeps 0.08 k off every horizontal
            # concrete line above the cap top between the FFBW and the front
            # face; the rows spread from there
            x_lo, x_hi = sorted((s.ffbw_s, x_front))
            hz_lines = []   # (lowest z, highest z) of the nearly level lines (within 6 degrees: A3's "parallel")
            for r in edges:
                if r["vis"]:
                    pl_ = edge_points(r)
                    hz_lines += [(min(a[1], b[1]), max(a[1], b[1])) for a, b in zip(pl_, pl_[1:])
                                 if abs(a[1] - b[1]) <= 0.105 * abs(a[0] - b[0]) and min(a[1], b[1]) > s.cap_top + 0.01
                                 and min(max(a[0], b[0]), x_hi) - max(min(a[0], b[0]), x_lo) > 0.01]
            for _ in range(20):
                hit = [z1 for z0, z1 in hz_lines if z0 - 0.08 * k < z_lo_row < z1 + 0.08 * k]
                if not hit:
                    break
                z_lo_row = max(hit) + 0.081 * k
            x_col = x_front + fs * 0.25 * k
            if ped_here:
                # Section C-C: four rows at equal pitch, FFBW, CONST. JOINT,
                # 5D1, CL BEARING from the bottom; the joint's leader runs
                # level from its text to 0.1 ft before the FFBW face and then
                # down to the key corner, so the angled piece lies within the
                # backwall (it crosses the FFBW line and the face bar only,
                # never the pedestal, A14) and stays above the FFBW leader
                # (A11; the engineer's sketch)
                n_rows = len(col_items) + 1
                pitch_rows = (z_hi_row - z_lo_row) / (n_rows - 1)
                fixed = []
                for i, it in enumerate(sorted(col_items, key=lambda it: it[2])):
                    fixed.append((it[0], it[1], z_lo_row + pitch_rows * (i if i == 0 else i + 1)))
                callouts(v, fixed, x_col, fs)
                y_cj = z_lo_row + pitch_rows
                v.leader([(x_key, s.cap_top), (s.ffbw_s + fs * 0.1, y_cj), (x_col, y_cj)], cj_txt,
                         "left" if fs > 0 else "right")
            else:
                callouts(v, col_items, x_col, fs, spread=(z_lo_row, z_hi_row))
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
                        # V2c (B12: the dimension line stood 0.044 k from the 6B1
                        # hoop leg): 0.08 k clear of every vertical leg
                        return (strip[0] < lo and hi < strip[1] and all(not (lo - 0.03 < xl < hi + 0.03) for xl in legs)
                                and all(abs(xl - x) >= 0.08 * k for xl in legs))
                    xd = next((s.ffbw_s + fs * d * k for d in (0.2, 0.35, 0.12, 0.45, 0.6, 0.75, 0.9)
                               if free(s.ffbw_s + fs * d * k)), s.ffbw_s + fs * 0.2 * k)
                    txt = fdot.ft_in(emb, 0.25) + " (MIN.)"
                    end = min(pts, key=lambda p: p[1])
                    # B7: the value horizontal in the band between the hoop top
                    # leg and the bar ends, beyond the cap centerline (open
                    # space inside the cap), with its two-piece pointer
                    xt = ccl + fs * (0.1 * k + text_w(v, txt) / 2)
                    v.dim((xd, s.cap_top), (end[0], end[1]), 0.0, 90, txt, horizontal=True,
                          loc=(xt, s.cap_top - max(0.8, emb * 0.6)))
            # (B3: no coping and no MSE wall in the end bent sections, so no
            # "FRONT FACE OF MSE WALL" label)
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
                # provider's; the model carries the strap only outside); B1
                # (markup "Add a circle to indicate strap anchorage within
                # the concrete"): a circle of radius 0.03 k at the embedded
                # end, the strap line stopping at its near edge
                r_an = 0.03 * k
                v.line((x0s - fs * Ls, zst), (x0s + fs * (0.5 - r_an), zst), "Rebar2")
                v.circle((x0s + fs * 0.5, zst), r_an, "Rebar2")
                xsd = x_back - fs * 0.15 * k
                v.dim((x_back, s.cap_top), (xsd, zst), fs * 0.15 * k, 90, fdot.ft_in(zst - s.cap_top, 0.25))
                if tag != "at_pile":
                    # round 6 (markup "Move to a better spot", End Bent 2's
                    # Section C-C: the label above the backwall-top corner sat
                    # on the dimension columns' top; the engineer's sketch puts
                    # it beyond the columns, just under the strap's level;
                    # rules A1, A14): the tip at the strap's free end, the
                    # angled piece down and outward past the back-side
                    # dimension columns xl1/xl2 (the same values as set with
                    # the columns below; the end bents' spacing) to 0.5 k
                    # under the strap's level, which passes under the rotated
                    # series text of the first column and clear of the
                    # strap dimension text at ``xsd``; the text runs away from
                    # the section
                    xl2_s = x_back - fs * 0.45 * k - fs * 0.45 * k
                    v.leader([(x0s - fs * Ls, zst), (xl2_s - fs * 0.25 * k, zst - 0.5 * k)],
                             DELTA + " REINF.\\PSTRAP", "right" if fs > 0 else "left")
                self.legend[DELTA] = legend_text() if legend_text is not None else STRAP_LEGEND
        pile_label = None
        if piles and tag == "at_pile":   # described on the back side, clear of the MSE wall
            side_x = pe[0] if fs > 0 else pe[2]
            desc = ("18\" SQUARE\\PPRESTRESSED\\PCONCRETE PILE" if piles[0]["role"] == "pile_conc"
                    else "20\" Ø STEEL\\PPIPE PILE")
            # the label on the front side beyond the cap face at the pile stub's
            # level (the bottom row's extension lines fill the space under the
            # cap; A1).  Markup 2026-10-19 round 3 follow-up ("Slide this down
            # ... to make room for the overlapping annos between the
            # details"): the text as low as the band over the bottom row's
            # pulled values allows, its first line 0.2 k under the tip
            side_x = pe[2] if fs > 0 else pe[0]
            # round 6 (markup "Move to a better spot", End Bent 2's Section
            # B-B: the three-line label beside the pile stub stood between the
            # section and the legend of the details column; rules A14, A2):
            # the label goes under the section on the front side, in the row
            # of the centerline label: the tip on the pile's front face just
            # above its break, the end of the angled piece 0.2 k beyond the
            # cap face at ``z_cll``, the text running away from the cap (the
            # centerline label's text ends about at the face, so the two do
            # not meet); it is drawn after the bottom dimension row (below),
            # whose pulled-out values and their pointers the angled piece
            # must not cross (A11)
            pile_label = (desc, side_x)
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
        if pile_label:
            # round 6 (A11): the angled piece of the pile label runs from the
            # pile's front face down across the bottom dimension row; where
            # the row has a value pulled out beside the pile (End Bents: the
            # "3"" with its pointer) the piece started just above the break
            # crossed that pointer (End Bent 2's ran along it 0.05 in off).
            # The tip moves up the face (0.08 k above the break, then in
            # steps of 0.02 k, always 0.12 k under the cap) to the first
            # height where the piece keeps 0.12 k from every leader and
            # pointer already drawn, else the height with the widest gap:
            # the steeper piece passes between the pointers of the values
            from . import anno_check
            desc, side_x = pile_label
            lab_end = (x_front + fs * 0.2 * k, z_cll)
            lead_calls = anno_check._leader_calls(v)
            lead_segs = [(p, q) for p, q, layer, call in v.segs if layer == "Leader" or call in lead_calls]
            best = (-1.0, z_lo + 0.08 * k)
            dz = 0.08
            while z_lo + dz * k <= s.cap_bot - 0.12 * k:
                tz = z_lo + dz * k
                a, b = v._X((side_x, tz)), v._X(lab_end)
                gap = min((_seg_gap(a, b, p, q) for p, q in lead_segs), default=1e9)
                if gap >= 0.12 * k:
                    best = (gap, tz)
                    break
                if gap > best[0]:
                    best = (gap, tz)
                dz += 0.02
            v.leader([(side_x, best[1]), lab_end], desc, al_f)
        # above: overall and the splits at the backwall face, bearings and
        # centerline, each extension line reaching its feature (B3): the cap
        # faces at the cap top (the back face and the FFBW at the backwall
        # top), the centerlines at the top of their drawn lines
        zt0 = (max(p[1] for r in edges if r["vis"] and r["role"] == "backwall" for p in edge_points(r))
               if eb else max(tops))
        feat ={round(cs[0], 6): s.cap_top, round(cs[1], 6): s.cap_top}
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
            cov = abs(x_front - leg)
            # B7: the value beyond the cap face, two-piece pointer.  B12
            # (markup "There's no need for these annotations to cross;
            # reposition by bringing the text up and the dim down slightly on
            # the cover anno"): the dimension and its value sit above the
            # bottom-bar callout (4~9A2 / 4~8A2) at one height, so the pointer
            # runs along the dimension and never crosses that leader; the
            # dimension stays clear of the bar dots on the face.
            h_cap = s.cap_top - s.cap_bot
            levels = sorted({p[1] for ps in cap_dots.values() for p in ps})
            # V4 (markup "Overlapping put in 2 lines of text for fit", B4-9:
            # the one-line 3" COVER (TYP., U.N.O.) beside the cap face reached
            # into the vertical connector of the 4~6A3 (EF) parallel leaders;
            # rules A2, A1): the value is always in two lines, as in the pier
            # sections; the height search below sizes its box by ``lines``
            txt = "%s COVER\\P(TYP., U.N.O.)" % fdot.ft_in(cov, 0.25)
            tw = text_w(v, txt)
            # V8 (markup "Overlap": the 3" COVER text and the start of the 4~8A2
            # leader sat on one another): the dimension and its value share one
            # height zc, the value outside the cap at (x_front + 0.25 k + tw/2,
            # zc), so the pointer is one straight horizontal piece.  The wanted
            # height is 0.42 of the cap height over the bottom (the gap between
            # the lowest side-bar dot and the side-bar callout row); the height
            # nearest to it where the value's text box keeps 2.1 text heights
            # from every callout row beside the face, off the bar levels of the
            # face (the dimension line would run on into a dot) and off the
            # closure slab and its label (the text stays off the concrete).
            # The end bents' wanted height (1.26 ft over the bottom) falls in
            # the closure slab (1.04 to 1.42 ft), where the nearest clear
            # height is the band under the slab.
            lines = txt.count("\\P") + 1
            hc = 0.5 * th * (1.4 + 1.67 * (lines - 1))         # half the value's text box
            m = 0.6 * th
            banned = []
            for y, n, tz in rows_front + [(zf, 1, []) for zf in getattr(self, "_fan_rows", [])]:
                banned.append((y - 0.5 * th - (n - 1) * fdot.LINE_PITCH * th - hc - m, y + 0.5 * th + hc + m))
                if tz:   # the heights the row's leaders span (the pointer would cross them, A11)
                    banned.append((min(tz + [y]) - 0.05, max(tz + [y]) + 0.05))
            for z in levels:
                banned.append((z - 0.08, z + 0.08))
            if eb and clos:
                ce = extents(clos)
                banned.append((ce[1] - hc - m, ce[3] + hc + m))
                zl = ce[3] + 0.3 * k       # the "4" CLOSURE SLAB" label: two lines hanging from this height
                banned.append((zl - 0.5 * th - fdot.LINE_PITCH * th - hc - m, zl + 0.5 * th + hc + m))
            zc = s.cap_bot + 0.42 * h_cap
            feas = [s.cap_bot + 0.15 + 0.01 * i for i in range(int((h_cap - 0.5) / 0.01) + 1)]
            feas = [z for z in feas if not any(lo < z < hi for lo, hi in banned)]
            if not feas:
                # V4: no height left for the two-line box in the usual band:
                # widen the search to 0.1 ft off the cap bottom and top
                wide = [s.cap_bot + 0.1 + 0.01 * i for i in range(int((h_cap - 0.2) / 0.01) + 1)]
                feas = [z for z in wide if not any(lo < z < hi for lo, hi in banned)]
            if feas:
                zc = min(feas, key=lambda z: abs(z - zc))
            v.dim((leg, zc), (x_front, zc), 0.0, 0.0, txt, loc=(x_front + fs * (0.25 * k + tw / 2), zc))
        yt = min(yb1 - 0.3 * k, z_cll - 0.08 * k)
        v.title((ccl, yt - 0.3 * k), "SECTION %s-%s" % (letter, letter), subtitle, subject_cx=ccl)
        return v

    def _pier_bearing_leaders(self, v, bearings, xe, y_a, y_b, z_bct, ccl):
        """B10 (markup "This is ugly. Do a set of parallel leaders where you
        have an arrow per line and make sure the leaders cross the other
        centerline in a dash area so it's clear they are distinct. Then put
        the text at 1."): the pier sections' bearing centerlines and their two
        parallel horizontal leaders (``View.parallel_leaders``: one vertical
        connector, one landing, the text once; V11) from the right of the
        section.  V19: the farther bearing (smaller s) has the upper line y_a,
        the nearer the lower line y_b, so the nearer bearing's centerline ends
        just over its own leader and the upper leader passes above it: no
        crossing, no gap, no stub shorter than a dash pattern (the cap
        centerline, which the upper leader crosses, is gapped by the caller)."""
        s = self.s
        k = IN * v.sf
        near, far = max(bearings, key=lambda b: b["s"]), min(bearings, key=lambda b: b["s"])
        z_lo = s.cap_top - 0.2
        v.line((far["s"], z_lo), (far["s"], z_bct), "CL_Minor")
        # V22 (markup 2026-10-19 round 3 follow-up, "Put the CL leader two
        # arrows on the same line"): ONE level leader at y_a from the text to
        # the farther bearing's centerline, with a second arrowhead where it
        # crosses the nearer one; the nearer centerline ends at that
        # arrowhead (its tip on the line's end), the farther one runs on above
        # the leader (A13: the label points at the extended centerline)
        if near is not far:
            v.line((near["s"], z_lo), (near["s"], y_a), "CL_Minor")
        v.leader([(far["s"], y_a), (xe, y_a)], CL + " BEARING\\P(TYP.)", "left")   # two lines: sheet room
        if near is not far:
            v.arrowhead((near["s"], y_a), (xe, y_a), "Leader")

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
        if double:
            # V14 / C10 (markups "I don't think these bars are actually here in
            # the model. When we show full width we have to show the actual
            # locations", "These appear to show clashes but I don't believe
            # there are clashes in the model"): at the scales where bars are
            # drawn double (C1) every bar is drawn exactly where the model has
            # it, tangent bars included (the backwall verticals 5D1 and
            # horizontals 4D2 are tangent, the pedestal legs touch the cap top
            # bars): the C4 nudge is for single lines only
            return [(rb, list(pts)) for rb, pts in shapes]
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
        # V14: each in-plane bar carries its offset from the cut (``dist``, ft,
        # beyond the cut) so the callout can say how far behind the cut it lies
        shapes = [(dict(b, dist=d), [self.s.P_sec(p) for p in b["pts"]]) for d, b in nearest.values()]
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
            draw_bar3(v, b, fn)   # B13: hooks and legs seen end-on are dots, not notched stubs
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
        # B5 (markup "Minimize the leaders crossing line work if you can just
        # shift the annotations a bit"): the WWR leader is one horizontal piece
        # from the band's edge nearest the label (tip 0.1 k inside the hatch)
        # out to the label column, so it crosses nothing but the wall face
        z_sh = zm - 0.6
        x_tip = band[1] - 0.1 * k if d_in > 0 else band[0] + 0.1 * k
        txt_sh = "SHADED AREA\\PSHOWS LIMITS\\POF WWR\\P(SEE NOTE %d)" % wwr_note
        v.leader([(x_tip, z_sh), (x_edge, z_sh)], txt_sh, al_in)
        # END BENT CAP at least 2.5 text heights clear of the four-line text above
        z_cap = s.cap_bot + 0.6 + 0.15 * k
        z_cap = min(z_cap, z_sh + 0.5 * th - (1 + 3 * fdot.LINE_PITCH) * th - 3.0 * th)
        v.leader([(inner - d_in * 0.15, s.cap_bot + 0.6), (x_edge, z_cap)], "END BENT CAP", al_in)
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
        # V15 / D12 (markup rule "anything the view clips gets a break line"):
        # the cap and backwall are drawn only 1 ft beyond the cheek (the
        # extractor clips them); a stub that stands out beside the cheek's
        # outline gets a vertical break line at its clipped end, over its
        # height.  In views D-D / E-E the stubs run away from the viewer (the
        # model's clip lies along the line of sight, under the cheek), so
        # nothing stands out sideways at present and no line is drawn
        for role in ("cap", "backwall"):
            rec = [r for r in cv["edges"] if r["role"] == role]
            if not rec:
                continue
            ex = extents(rec)
            for xe, out in ((ex[0], ex[0] < x0 - 1e-3), (ex[2], ex[2] > x1 + 1e-3)):
                if out:
                    v.break_line((xe, ex[1] - 0.06 * k), (xe, ex[3] + 0.06 * k))
        drop = 0.6 * k if cuts and cuts.get("side") else 0.0   # below the bottom F-F flag
        v.title(((x0 + x1) / 2, yb - 0.3 * k - 0.45 * k - drop), "VIEW %s-%s" % (letter, letter),
                "(%s CHEEK WALL)" % ("LEFT" if cheek["u"] < 0 else "RIGHT"), subject_cx=(x0 + x1) / 2)
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
            draw_bar3(v, x, s.P_plan)   # B13: legs seen end-on are dots, in-plane runs smooth bars
        # centerlines by leaders
        v.line((ped["u"], box[1] - 0.2 * k), (ped["u"], box[3] + 0.1 * k), "CL_Minor")
        v.leader([(ped["u"], box[1] - 0.12 * k), (ped["u"] + 0.3 * k, box[1] - 0.12 * k)], "BEAM", "left", cl=True)
        v_cl = s.piles[0]["v"] if s.kind == "EB" else 0.0
        v.line((box[0] - 0.1 * k, v_cl), (box[2] + 0.1 * k, v_cl), "CL_Major")
        lab_x = box[2] + 0.1 * k
        cl_lab = "CAP" if s.kind == "EB" else "PIER"
        # V20 (the CL PIER label too close to CL BEARING, A2): the
        # centerline labels are rows of one column, each leader from its line
        # end, the rows packed by ``callouts`` at least 2.1 th apart from
        # their offsets of 0.18 k off the lines
        cl_items = [([(lab_x - 0.05 * k, v_cl)], CL + " " + cl_lab, v_cl + 0.18 * k)]
        for br in s.bearings:
            if vv[0] - 0.01 < br["v"] < vv[1] + 0.01:
                v.line((uu[0] - 0.2, br["v"]), (box[2] + 0.1 * k, br["v"]), "CL_Minor")
                cl_items.append(([(lab_x - 0.05 * k, br["v"])], CL + " BEARING", br["v"] - 0.18 * k))
        cl_rows = callouts(v, cl_items, lab_x + 0.29 * k, 1)
        x_lab = lab_x + 0.29 * k + 0.4 * th + max(text_extent(it[1], th) for it in cl_items)   # right end of the labels
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
            # V12 (markup "Why all the way up here for the text and not here?
            # Look at how drawing items get crossed"): the dimension and its
            # value share one height zq, in the widest gap between the
            # centerline label rows within 0.12 H of the pedestal's ends, the
            # value beyond the break line at (box[2] + 0.15 k + tw/2, zq), so
            # the pointer is one horizontal piece that no leader crosses (A11)
            txt = "%s MIN.\\PCOVER" % fdot.ft_in(cov, 0.25)
            H = vv[1] - vv[0]
            lab_vs = sorted(y for y, _n, _tz in cl_rows)
            lo_q, hi_q = vv[0] + 0.12 * H, vv[1] - 0.12 * H
            # V6 (markup "Dont put a dim so close to a parallel line if there
            # is plenty of space", B4-7; rule B12): the dimension line stands
            # in the widest free band, free of the centerline label rows, the
            # horizontal bars (4E2 / 4F2: the v of every "y" bar) and the
            # horizontal pedestal-role records of the plan (the pier's
            # top-surface breaks at v = +-0.458), each a closed band of
            # +-0.08 k, so it ends at least 0.08 k from every parallel line
            # (the label rows keep the two-line value clear of their texts and
            # leaders: half its height, 0.4 th and half a label line, A2)
            # (each row from its leader tip to its text row, the leaders being
            # drawn there)
            lab_m = (0.5 * (1 + fdot.LINE_PITCH) + 0.4) * th
            obst = [(min(tz + [y]) - lab_m, max(tz + [y]) + lab_m) for y, _n, tz in cl_rows]
            obst += [(cen(x, lambda p: s.v(p[1])) - 0.08 * k, cen(x, lambda p: s.v(p[1])) + 0.08 * k) for x in yb]
            for rec in S["plan"]:
                if (rec["role"] == "pedestal" and rec["vis"] and rec["t"] in ("L", "P") and len(rec["p"]) == 2
                        and abs(rec["p"][0][1] - rec["p"][1][1]) < 0.005
                        and max(rec["p"][0][0], rec["p"][1][0]) > box[0] and min(rec["p"][0][0], rec["p"][1][0]) < box[2]):
                    vh = (rec["p"][0][1] + rec["p"][1][1]) / 2
                    obst.append((vh - 0.08 * k, vh + 0.08 * k))
            free, cur = [], lo_q   # the free bands between lo_q and hi_q
            for o0, o1 in sorted(obst):
                if o1 < cur:
                    continue
                if o0 > cur:
                    free.append((cur, min(o0, hi_q)))
                cur = max(cur, o1)
                if cur >= hi_q:
                    break
            if cur < hi_q:
                free.append((cur, hi_q))
            free = [(a, c) for a, c in free if c > a]
            if free:
                a, c = max(free, key=lambda t: t[1] - t[0])
            else:   # no free band: the old choice (the widest between the label rows)
                edges_v = [lo_q] + [y for y in lab_vs if lo_q < y < hi_q] + [hi_q]
                a, c = max(zip(edges_v, edges_v[1:]), key=lambda t: t[1] - t[0])
            zq = (a + c) / 2
            v.dim((lastu + r, zq), (uu[1], zq), 0.0, 0.0, txt,
                  loc=(box[2] + 0.15 * k + text_w(v, txt) / 2, zq))
        yt = box[1] - 0.42 * k
        v.title(((uu[0] + uu[1]) / 2, yt), "PEDESTAL PLAN", subject_cx=(uu[0] + uu[1]) / 2)
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

    def cage_clash_note(self):
        """Model finding (markup B4-10 Section G-G, "multiple clashing bars that
        don't occur in the model"; C9): backwall end verticals that stand inside
        a cheek wall beside its verticals.  For each cheek wall the backwall
        verticals (family "backwall", subtype "vert") whose x lies within the
        cheek's x-range are compared in plan with the cheek's verticals
        (family "cheek", subtype "vert"); when any pair is closer than 2.5" c/c
        the note of the closest pair is returned (a MODEL CHECK item of the
        sheet notes), else None."""
        s = self.s
        if s.kind != "EB":
            return None
        bw = s.bars_of(family="backwall", subtype="vert")
        best = None
        for c in s.cheeks:
            lo, hi = sorted((s.S["concrete"][c["name"]]["bb_ft"][0], s.S["concrete"][c["name"]]["bb_ft"][3]))
            num = c["name"][-2:]
            ch = [b for b in s.bars_of(family="cheek", subtype="vert") if b["group"].endswith(num + "Bars")]
            for b in bw:
                if not lo <= b["pts"][0][0] <= hi or not ch:
                    continue
                for cb in ch:
                    d = math.dist(b["pts"][0][:2], cb["pts"][0][:2])
                    if best is None or d < best[0]:
                        best = (d, b, cb)
        if best is None or best[0] * 12.0 >= 2.5:
            return None
        d, b, cb = best
        return ("MODEL CHECK (REMOVE BEFORE ISSUE): BACKWALL END VERTICALS %s LIE WITHIN THE CHEEK WALL %s FROM THE "
                "%s VERTICALS (%s, %s); RECONCILE THE CAGES."
                % (b["mark"], fdot.ft_in(d, 0.125), cb["mark"], b["name"].upper(), cb["name"].upper()))

    def bar_overlap_note(self):
        """Model finding (markup 2026-10-19, Section G-G: "I'm seeing doubled
        bars here.  Do they exist in the model?"; C9): two backwall verticals
        of one face closer than a bar diameter, centre to centre.  The model's
        run of 21 bars at 1'-0" from one end bar lands 3/8" short of the
        other end bar's offset, where a closing bar stands as well, on both
        faces of both backwalls.  Returns the note for the closest pair, or
        None."""
        s = self.s
        if s.kind != "EB":
            return None
        vert = [b for b in s.bars if b["family"] == "backwall" and b["subtype"] == "vert"]
        best = None
        for i, a in enumerate(vert):
            for b in vert[i + 1:]:
                if abs(a["pts"][0][1] - b["pts"][0][1]) > 0.01:
                    continue   # not the same face
                d = abs(s.u(a["pts"][0][0]) - s.u(b["pts"][0][0]))
                if d < (a["dia_in"] + b["dia_in"]) / 24.0 and (best is None or d < best[0]):
                    best = (d, a, b)
        if best is None:
            return None
        d, a, b = best
        side = "LEFT" if s.u(a["pts"][0][0]) < 0 else "RIGHT"
        return ("MODEL CHECK (REMOVE BEFORE ISSUE): BACKWALL VERTICALS %s %s AND %s STAND %s APART, CENTRE TO CENTRE "
                "(OVERLAPPING), NEAR THE %s CHEEK WALL ON BOTH FACES: THE RUN AT 1'-0\" FROM THE OTHER END BAR LANDS "
                "%s SHORT OF ITS END BAR; RECONCILE THE LAYOUT."
                % (a["mark"], a["name"].upper(), b["name"].upper(), fdot.ft_in(d, 0.125), side,
                   fdot.ft_in(d, 0.125)))

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
        v = View(self.doc, zone, "%s PEDESTAL ELEVATION %d" % (s.key, ped["line"]))
        th, k = v.th, IN * v.sf
        # (B6: the cap stub is wider on the left, so the break line is clear of
        # the dimension column texts.)  V10 (markup "No need to overlap the
        # drawings so much, there is plenty of drawing space. Move the break
        # line if needed and shift these annos out into the space"): the cap
        # stub reaches 1.1 ft past the pedestal on the right too, so the
        # 2" COVER and 4F1 labels stand beyond the break line, off the drawing
        box = (uu[0] - 1.1, lo - 0.15, uu[1] + 1.1, ztop + 0.5)   # the break lines beyond the dimension columns (A1)
        for rec in S["elev"]:
            if rec["role"] in ("pedestal", "cap") and rec["vis"]:
                layer, lt = layer_for(rec)
                v.record(rec, layer, lt, box)
        # (bars that project onto an identical line in this view, the legs and
        # runs of the bars spaced along the viewing direction, are drawn once:
        # coincident duplicates only add up the lines a leader seems to cross, A14)
        drawn = set()
        for x in pbars:
            key = tuple((round(q[0], 3), round(q[1], 3)) for q in proj(x, s.P_elev))
            if key in drawn:
                continue
            drawn.add(key)
            draw_bar3(v, x, s.P_elev)   # B13: the bars seen end-on are dots, in-plane legs smooth bars
        v.break_line((box[0], box[1]), (box[2], box[1]))
        for xv in (box[0], box[2]):
            v.break_line((xv, box[1]), (xv, s.cap_top + 0.04 * k))
        # the cap top under the pedestal is a construction joint, but it is not
        # called out here (markup 2026-10-19 round 3 follow-up, "Don't call out
        # the construction joint at the pedestals"): the sheet note says the
        # pedestals are cast on the cap and the cap top is a construction joint
        # (D5).  No chamfer callout either (follow-up "Don't call out 3/4
        # chamfers. This will go in the General Notes later"; D11).
        W = uu[1] - uu[0]
        v.leader([(uu[0] + 0.8 * W, ztop), (uu[0] + 0.8 * W, ztop + 0.52 * k)],
                 "TOP OF PEDESTAL\\P(SEE TABLE FOR\\PELEVATIONS)", "left")
        # marks
        xb = [x for x in pbars if x["subtype"] == "x"]
        yb = [x for x in pbars if x["subtype"] == "y"]
        if yb:
            # round 7 (markup 2026-10-19, "4F2 has a ton of space available:
            # shift right and point at the bar midway between the other bars.
            # No need to be so close to the corner and to the other bars";
            # A21): the tip on the top of the in-plane bar's run midway
            # between the second and third end-on bar from the left, the knee
            # straight above it over the pedestal top, the text to the right
            # (clear of "TOP OF PEDESTAL", whose leader stands at 0.8 W)
            pts = proj(yb[0], s.P_elev)
            z_max = max(p[1] for p in pts)
            run = sorted(p[0] for p in pts if p[1] > z_max - 0.01)
            us = sorted(s.u(x["pts"][0][0]) for x in xb)
            x_tip = (us[1] + us[2]) / 2 if len(us) >= 3 else (run[0] + run[-1]) / 2
            x_tip = min(max(x_tip, run[0] + 0.1), run[-1] - 0.1)
            v.leader([(x_tip, z_max + yb[0]["dia_in"] / 24.0), (x_tip, ztop + 0.45 * k)],
                     mark_list(sorted({x["mark"] for x in yb})), "left")
        if xb:
            x = max(xb, key=lambda x: s.u(x["pts"][0][0]))
            uq = s.u(x["pts"][0][0])
            # V10: the text beyond the break line at the leg's height less
            # 0.25 k, the knee 0.1 k past the line, the tip on the last 4F1 leg
            v.leader([(uq, lo + 0.25), (box[2] + 0.1 * k, lo + 0.25 - 0.25 * k)], x["mark"] + " (TYP.)", "left")
        # embedment, height, covers
        xl = uu[0] - 0.3 * k
        v.dim((uu[0], lo), (uu[0], s.cap_top), -(xl - uu[0]), 90, fdot.ft_in(s.cap_top - lo, 0.25) + "\\P(MIN.)")
        v.dim((uu[0], s.cap_top), (uu[0], zlow), -(xl - uu[0]), 90, fdot.ft_in(zlow - s.cap_top, 0.25) + " (MIN.)",
              outside=1)
        r = pbars[0]["dia_in"] / 24.0
        # V7 (markup "Remove. Only detail cover to the outermost bar", B4-4):
        # the cover from the pedestal top down to the bars (the 2 1/4" COVER
        # dimension) is not drawn, only the side cover to the outermost leg
        # below (all pedestal elevations, the pier's too)
        outer = max(max(s.u(p[0]) for p in x["pts"]) for x in pbars) + r
        # round 6 (markup "Call out the cover where it matters", rule C11
        # amended: a cover is dimensioned at the face it is measured from,
        # inside the element whose cover it is): the dimension sat in the cap
        # under the pedestal, where the leg is embedded and the cover means
        # nothing; it is now in the pedestal, 1.44" above the cap top (the
        # clear part of the legs under the 4F2 top bar), from the outer leg
        # face to the pedestal's side face
        zc = s.cap_top + 0.12
        # B7: the value in open space beyond the cap break, with a two-piece
        # pointer; centred 0.2 k above the dimension, under TOP OF PEDESTAL (A2)
        txt = "%s\\PCOVER" % fdot.ft_in(uu[1] - outer, 0.25)
        v.dim((outer, zc), (uu[1], zc), 0.0, 0.0, txt,
              loc=(box[2] + 0.15 * k + text_w(v, txt) / 2, zc + 0.2 * k))
        v.title(((uu[0] + uu[1]) / 2, box[1] - 0.45 * k), "PEDESTAL ELEVATION", subject_cx=(uu[0] + uu[1]) / 2)
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
        # D12: the piles are cut at the window bottom, so their break lobes (the
        # piles of one end view overlap: one break for the group)
        pil = [r for r in S["end_view"]["edges"] if r["role"] in ("pile_steel", "pile_conc") and r["vis"]]
        if pil:
            pe = extents(pil)
            if pe[1] <= zc + 0.01 and pe[3] > zc + 0.05:
                kind = "pipe" if pil[0]["role"] == "pile_steel" else "square"
                v.pile_break((pe[0] + pe[2]) / 2, zcd, pe[2] - pe[0], kind, "PileSteel" if kind == "pipe" else "PileConc")
        # the centerline, broken through the wall-width text band at the bottom
        # (A1); its label above the cap-width dimension row
        y_wd = T((0, s.wall_bot))[1] - 0.35 * k if s.kind == "PIER" else None
        y_cw = s.cap_top + 0.6 + 0.35 * k   # the cap-width dimension row above the pedestals
        # B7 (markup "Extend the centerline and point to it because this looks
        # like we are pointing to the dim text"): one continuous piece above the
        # cap-width dimension row, the leader's tip at its top end.  V19 (a stub
        # shorter than its dash pattern plots solid): the piece above the row is
        # a full pattern long, and the centerline is one run of pieces broken at
        # the two dimension text bands: a piece left shorter than a pattern (the
        # one under the wall-width band) is dropped
        pat_major = fdot.pattern_length(fdot.level_attrs("CL_Major")["linetype"], v.sf)
        z_cl_top = max(y_cw + 0.77 * k, y_cw + 0.32 * k + 1.05 * pat_major)
        bands = [(y_cw - 0.03 * k, y_cw + 0.32 * k)] + ([(y_wd - 0.03 * k, y_wd + 0.32 * k)] if y_wd is not None else [])
        vline_gapped(v, ccl, zcd - 0.2 * k, z_cl_top, bands, "CL_Major")
        v.xform = keep
        v.leader([(ccl, z_cl_top), (ccl + 0.3 * k, z_cl_top + 0.15 * k)], self.cl_name(), "left", cl=True)
        v.dim((cs[0], s.cap_top), (cs[1], s.cap_top), 0.35 * k + 0.6, step=0.125)
        if s.kind == "PIER":
            ws = (-s.wall_bb[4], -s.wall_bb[1])
            v.dim(T((ws[0], s.wall_bot)), T((ws[1], s.wall_bot)), -0.35 * k, step=0.125)
            for b in s.bearings:
                v.line((b["s"], s.cap_top - 0.2), (b["s"], s.cap_top + 0.9), "CL_Minor")
        v.title((ccl, zcd - 0.6 * k), "VIEW %s-%s" % (letter, letter), "(END VIEW)", subject_cx=ccl)
        return v
