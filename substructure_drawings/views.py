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
  within 1'-3" beyond the cut as a single line with its bends and hooks, as
  on the sample sheets; the bar layout is dimensioned in full.

Reinforcement in plan and elevation follows SDM 4.3.B/C and 4.3.1.C: only the
first and last bar of each run is drawn; stirrups use the CAD_AI symbol (a
line at the bar station with a filled dot at each end).
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


# ============================================================== helpers
def draw_edges(view, edges, box=None, hidden=True, roles=None, skip_roles=()):
    for rec in edges:
        if not hidden and not rec["vis"]:
            continue
        if roles and rec["role"] not in roles:
            continue
        if rec["role"] in skip_roles:
            continue
        layer, lt = layer_for(rec)
        view.record(rec, layer, lt, box)


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
    row; values are never stacked on a second row."""
    pad = 0.12 * IN * v.sf
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
        segs.append((a, b, txt))
    fits = [text_w(v, t) + pad < abs(b - a) for a, b, t in segs]
    room = [[(abs(b - a) - text_w(v, t)) / 2 - pad] * 2 if f else [0.0, 0.0] for (a, b, t), f in zip(segs, fits)]
    n = len(segs)
    below = []   # (level, lo, hi) of values written below the row
    for i, (a, b, txt) in enumerate(segs):
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
                m, hw = (a + b) / 2, text_w(v, txt) / 2 + 0.6 * v.th
                while any(lv == level and lo < m + hw and m - hw < hi for lv, lo, hi in below):
                    level += 1
                below.append((level, m - hw, m + hw))
        if vertical:
            v.dim((y_obj, a), (y_obj, b), -(y_dim - y_obj), 90, txt, outside=out, level=level)
        else:
            v.dim((a, y_obj), (b, y_obj), y_dim - y_obj, 0, txt, outside=out, level=level)


def callouts(v, items, x_col, side, gap=None):
    """Callouts beside the bars: items = [(tips, text)] (local coords).  The
    texts start at x_col (side +1: text to the right, -1: to the left), at the
    height of their bars as far as spacing allows; several tips fan from one
    knee."""
    if not items:
        return
    gap = gap or 2.1 * v.th
    order = sorted(items, key=lambda it: sum(t[1] for t in it[0]) / len(it[0]))
    want = [sum(t[1] for t in it[0]) / len(it[0]) for it in order]
    hs = [(1 + txt.count("\\P") * fdot.LINE_PITCH) * v.th for _, txt in order]
    ys = []
    for i, y in enumerate(want):
        if ys:
            y = max(y, ys[-1] + max(gap, (hs[i - 1] + hs[i]) / 2 + 0.6 * v.th))
        ys.append(y)
    shift = (sum(want) - sum(ys)) / len(ys)
    ys = [y + shift for y in ys]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + max(gap, (hs[i - 1] + hs[i]) / 2 + 0.6 * v.th))
    land = 0.14 * IN * v.sf
    for (tips, txt), y in zip(order, ys):
        knee = (x_col - side * land, y)
        al = "left" if side > 0 else "right"
        if len(tips) == 1:
            v.leader([tips[0], knee, (x_col, y)], txt, al)
        else:
            v.leader_fan(tips, knee, txt, al)


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
    def plan(self, zone):
        s = self.s
        S = s.S
        v = View(self.doc, zone, s.key + " PLAN")
        draw_edges(v, S["plan"])
        th, k = v.th, IN * v.sf
        u0, u1 = s.cap_u
        uL, uR = s.outer_u
        vf, vb = s.cap_v
        ex = extents(S["plan"])
        v_top, v_bot = ex[3], ex[1]
        beam_ext = 1.25
        v_span_lo = min(vf, min(b["v"] for b in s.bearings)) - beam_ext
        v_span_hi = max(vb, max(b["v"] for b in s.bearings)) + (beam_ext if s.kind == "PIER" else 0)
        y_lo, y_hi = min(v_bot, v_span_lo), max(v_top, v_span_hi)
        # PGL
        v.line((0, y_lo - 0.3), (0, y_hi + 0.45), "BaseLineSurveyPGL")
        v.text((0.25 * th, y_hi + 0.45), "PGL", None, "BOTTOM_LEFT")
        # centerlines, labelled by leaders at the right end
        v_cl = s.piles[0]["v"] if s.kind == "EB" else 0.0
        ext = 0.25 * k
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
        for i, (yy, txt) in enumerate(labels):
            d = 0.0 if len(labels) == 3 and i == 1 else (-1.0 if i == 0 else 1.0)
            knee = (xt + 0.22 * k, yy + d * 0.22 * k)
            v.leader([(xt, yy), knee, (knee[0] + 0.12 * k, knee[1])], txt, "left", cl=True)
        # beam centerlines from each bearing toward its span, leader labels
        for b in s.bearings:
            d = self.span_side(b)
            end = v_span_lo if d < 0 else v_span_hi
            for bl in s.beam_lines:
                v.line((bl["u"], b["v"]), (bl["u"], end), "CL_Minor")
                tip = (bl["u"], end - d * 0.15)
                v.leader([tip, (bl["u"] + 0.2 * k, end + d * 0.12 * k)], "BEAM " + s.beam_id(b["span"], bl["line"]),
                         "left", cl=True)
        # complementary skew angle (SDM 2.14): 90 degrees, typical
        b0 = s.bearings[0]
        bl0 = s.beam_lines[0]
        d0 = self.span_side(b0)
        v.arc((bl0["u"], b0["v"]), 0.45, 270 if d0 < 0 else 0, 360 if d0 < 0 else 90, "Dimension")
        tip = (bl0["u"] + 0.45 * math.cos(math.radians(-45 * d0 * -1 if d0 > 0 else -45)),
               b0["v"] + 0.45 * math.sin(math.radians(45 if d0 > 0 else -45)))
        v.leader([tip, (bl0["u"] + 0.35 * k, b0["v"] + d0 * 0.3 * k)], "90°00'00\" (TYP.)", "left")
        # FFBW and the station of the PGL crossing
        if s.kind == "EB":
            what = "BEGIN BRIDGE" if s.key == "EB1" else "END BRIDGE"
            txt = "%s\\PFFBW %s\\PSTA. %s" % (what, s.title, fdot.station(s.station(s.ffbw_y)))
            v.leader([(0, s.ffbw_v), (-0.25 * k, vf - 0.2 * k)], txt, "right")
            v.leader([(u0 + 1.0, s.ffbw_v), (u0 + 1.0 + 0.2 * k, vb + 0.25 * k)], "FFBW", "left")
        else:
            knee = (-0.25 * k, vb + 0.3 * k)
            v.leader([(0, 0), knee, (knee[0] - 0.12 * k, knee[1])], "PIER", "right", cl=True)
            v.text((knee[0] - 0.12 * k - 0.4 * th, knee[1] - 1.6 * th), "STA. %s" % fdot.station(s.station(s.y0)),
                   None, "MIDDLE_RIGHT")
        # ---------------------------------------------------- dimensions
        y1 = y_hi + 0.4 * k
        y2 = y1 + 0.28 * k
        if s.kind == "EB":
            chain_dims(v, [uL, u0, 0.0, u1, uR], None, v_top, y1, step=0.125)
            v.dim((uL, v_top), (uR, v_top), y2 - v_top)
        else:
            chain_dims(v, [u0, 0.0, u1], None, vb, y1, step=0.125)
            v.dim((u0, vb), (u1, vb), y2 - vb)
        sp = "*"
        self.legend[sp] = "DIMENSIONS MEASURED ALONG " + ("FFBW" if s.kind == "EB" else CL + " PIER")
        yb1 = y_lo - 0.35 * k
        yb2 = yb1 - 0.28 * k
        xs, texts = equal_chain([bl["u"] for bl in s.beam_lines], (u0, u1))
        chain_dims(v, xs, texts, vf, yb1, step=0.125)
        v.row_label(uL - 0.1 * k, yb1, "BEAM SPACING " + sp)
        xs, texts = equal_chain([p["u"] for p in s.piles], (u0, u1))
        chain_dims(v, xs, texts, vf, yb2, step=0.125)
        v.row_label(uL - 0.1 * k, yb2, "PILE SPACING " + sp)
        # transverse dimensions on the left
        xl1 = uL - 0.45 * k
        xl2 = xl1 - 0.3 * k
        if s.kind == "EB":
            ys = sorted({round(vf, 6), round(vb, 6), round(s.ffbw_v, 6), round(s.bearings[0]["v"], 6), round(v_cl, 6)})
            chain_dims(v, ys, None, uL, xl1, vertical=True, step=0.125)
            cv = extents(S["plan"], ("cheek",))
            chain_dims(v, sorted({round(cv[1], 6), round(vf, 6), round(vb, 6), round(cv[3], 6)}), None, uL, xl2,
                       vertical=True, step=0.125)
            for c, lab in zip(s.cheeks, ("D", "E")):
                look = (1, 0) if c["side"] == "left" else (-1, 0)
                xc = (c["u_lo"] - 0.3 * k) if c["side"] == "left" else (c["u_hi"] + 0.3 * k)
                v.section_cut((xc, cv[1] - 0.15 * k), (xc, cv[3] + 0.15 * k), lab, look)
        else:
            ys = sorted({round(vf, 6), round(vb, 6), 0.0} | {round(b["v"], 6) for b in s.bearings})
            chain_dims(v, ys, None, uL, xl1, vertical=True, step=0.125)
            v.dim((uL, vf), (uL, vb), -(xl2 - uL), 90)
            # end view D-D looks along +X (global), i.e. toward -u in this plan
            look = (1, 0) if s.e1 > 0 else (-1, 0)
            xc = (uL - 0.12 * k) if look[0] > 0 else (uR + 0.12 * k)
            v.section_cut((xc, vf - 0.15 * k), (xc, vb + 0.15 * k), "D", look)
        # direction of stationing (stations increase toward -Y), upper right
        sd = -s.up
        L = 1.5
        xa = uR + 1.75 * k
        ym = y1 - L * k / 2   # upper right: level with the top dimensions
        v.stationing_arrow((xa, ym - sd * L * k / 2), (0, sd), L)
        v.title((0, yb2 - 0.42 * k), "PLAN")
        return v

    # ------------------------------------------------------- elevation
    def _broken(self, v, edges, z_break):
        """Broken view: the band z_lo..z_hi is removed and the part below is
        raised to leave ``gap``; nothing below z_clip is drawn."""
        z_hi, z_lo, gap, z_clip = z_break
        shift = (z_hi - z_lo) - gap
        v.xform = lambda p: (p[0], p[1] + shift) if p[1] <= z_lo + 1e-9 else p
        for rec in edges:
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

    def elevation(self, zone, z_break=None, pile_show=1.0):
        """Elevation with the concrete and the reinforcement (FDOT sheets)."""
        s = self.s
        S = s.S
        v = View(self.doc, zone, s.key + " ELEVATION")
        th, k = v.th, IN * v.sf
        z_pile = s.cap_bot - pile_show if not z_break else z_break[3]
        if z_break:
            self._broken(v, S["elev"], z_break)
        else:
            for rec in S["elev"]:
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
            v.circled_number((p["u"] + w / 2 + 0.16 * k, zp + 0.1 * k), p["no"])
        v.xform = keep
        if z_break:
            self._break_lines(v, z_break, s.wall_u[0] - 0.5, s.wall_u[1] + 0.5)
        z_top = extents(S["elev"])[3]
        z_pgl = (max(t[1] for t in s.backwall_top) + 0.48 * k) if s.kind == "EB" else s.cap_top + 0.9
        v.line((0, s.cap_bot - 0.3), (0, z_pgl), "BaseLineSurveyPGL")
        v.text((0.25 * th, z_pgl), "PGL", None, "BOTTOM_LEFT")
        # elevation points (values in the table of elevations)
        z_tops = z_top - 0.05
        for letter, desc, u, z in self.elev_points:
            side = 1 if u >= 0 else -1
            if "BACKWALL AT END" in desc or "BOTTOM OF CAP" in desc:
                side = -side  # point these inward, clear of the cheek labels
            q = T((u, z))
            al = "left" if side > 0 else "right"
            if "PGL" in desc:   # low and to the right, under the section flags
                v.leader([q, (q[0] + 0.35 * k, q[1] + 0.12 * k)], "PT. " + letter, "left")
            elif z >= z_tops:
                v.leader([q, (q[0] + side * 0.22 * k, q[1] + 0.12 * k)], "PT. " + letter, al)
            elif z >= s.cap_top - 0.01:
                v.leader([q, (q[0] + side * 0.25 * k, q[1] + 0.25 * k)], "PT. " + letter, al)
            elif z < s.cap_bot - 0.01:   # cheek lug bottom: nearly level, clear of the pile labels
                v.leader([q, (q[0] + side * 0.25 * k, q[1] - 0.08 * k)], "PT. " + letter, al)
            else:
                v.leader([q, (q[0] + side * 0.25 * k, q[1] - 0.25 * k)], "PT. " + letter, al)
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
        # pile embedment at the pile left of the PGL, horizontal text below the cap
        p = max((q for q in s.piles if q["u"] < 0), key=lambda q: q["u"])
        xe = p["u"] + p["width"] / 2
        txt = fdot.ft_in(p["top"] - s.cap_bot) + " (MIN.) (TYP.)"
        v.dim((xe, s.cap_bot), (xe, p["top"]), -0.15 * k, 90, txt, horizontal=True,
              loc=(xe + 0.25 * k + text_w(v, txt) / 2, s.cap_bot - 0.12 * k))
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
        self._section_marks(v, T, zp, z_up)
        yt = min(zp - 0.3 * k, z_row - 0.3 * k if z_row is not None else zp)
        v.title((0, yt - 0.3 * k), "ELEVATION",
                "(LOOKING BACK STATION)" if s.key == "EB1" else "(LOOKING AHEAD STATION)")
        self.legend_at = (x2 - 0.1 * k, yt - 0.1 * k)
        return v

    def draw_legend(self, v):
        """Footnote symbol legend at the lower left of the elevation."""
        if self.legend:
            v.legend(self.legend_at, list(self.legend.items()))

    def _section_marks(self, v, T, zp, z_up=None):
        """Section flags above the view (under a dimension row at z_up) and
        just below the pile cut-offs."""
        s = self.s
        k = IN * v.sf
        look = (1, 0) if s.e1 > 0 else (-1, 0)
        z_lo = zp - 0.17 * k   # below the pile breaks
        z_hi = ((max(t[1] for t in s.backwall_top) + 0.45 * k) if s.kind == "EB" else z_up - 0.08 * k)
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
        right = []   # callouts beside the right end of the cap
        below = []   # callouts below the cap
        # longitudinal cap bars: one line per distinct level
        for sub in ("top", "side", "bottom"):
            bs = s.bars_of(family="cap_long", subtype=sub)
            if not bs:
                continue
            levels = OrderedDict()
            for b in bs:
                levels.setdefault(round(b["pts"][0][2], 3), []).append(b)
            for z, grp in levels.items():
                v.pl(proj(grp[0], fn), "Rebar")
            mark = bs[0]["mark"]
            ut = u1 - 0.55
            if sub == "side":
                faces = len({round(b["pts"][0][1], 2) for b in bs})
                txt = "%d~%s (EF)" % (len(bs) // max(faces, 1), mark)
                tips = [(ut - 0.25 * i, z) for i, z in enumerate(sorted(levels))]
            else:
                txt = "%d~%s" % (len(bs), mark)
                tips = [(ut, list(levels)[0])]
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
        if s.kind == "EB":
            z_row, z_up = zp - 0.52 * k, None
            chain_dims(v, xs, texts, s.cap_bot, z_row)
        else:
            z_row = None
            zt = max(z for _, _, _, z in self.elev_points) if self.elev_points else s.cap_top
            z_up = max(zt, s.cap_top + 0.6) + 0.45 * k
            chain_dims(v, xs, texts, s.cap_top, z_up)
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
                v.pl(proj(b, fn), "Rebar")
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
                v.pl(proj(b, fn), "Rebar")
            hor = s.bars_of(family="backwall", subtype="horiz")
            hface = sorted(hor, key=lambda b: abs(b["pts"][0][1] - face))
            hf = [b for b in hor if abs(b["pts"][0][1] - hface[0]["pts"][0][1]) < 0.05]
            for b in hf:
                v.pl(proj(b, fn), "Rebar")
            hz = sorted(b["pts"][0][2] for b in hf)
            right.append(([(u1 - 0.55, hz[len(hz) // 2])], "%d~%s (EF)" % (len(hf), hf[0]["mark"])))
            bw_u = sorted(s.u(x) for x in (s.backwall_bb[0], s.backwall_bb[3]))
            z_bw = max(t[1] for t in s.backwall_top)
            zc = max(c["top"] for c in s.cheeks)
            xs, texts = run_chain([(us, series_text(us, front[0]["mark"], ef=True))], bw_u)
            chain_dims(v, xs, texts, z_bw, zc + 0.4 * k)
        callouts(v, right, ends[1] + 0.2 * k, 1)
        if below:
            zb = s.cap_bot - 0.42 * k
            for tips, txt in below:
                tx = max(t[0] for t in tips) + 0.06 * k
                knee = (tx, zb)
                if len(tips) == 1:
                    v.leader([tips[0], knee, (tx + 0.1 * k, zb)], txt, "left")
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
        cs = s.cap_s
        ccl = (cs[0] + cs[1]) / 2
        pile_show = 1.25 if s.kind == "EB" else 0.6
        z_lo = s.cap_bot - pile_show
        # context: the MSE wall in front, a stub of the landing slab on the backwall
        if s.key == "EB1":
            xr = (cs[0] - 0.15, cs[1] + 2.75)
        elif s.key == "EB2":
            xr = (cs[0] - 2.75, cs[1] + 0.15)
        else:
            xr = (cs[0] - 0.35, cs[1] + 0.35)
        tops = [p[1] for r in sec["edges"] if r["vis"] for p in edge_points(r) if xr[0] <= p[0] <= xr[1]]
        z_hi = max(tops) + 0.05
        # bearing labels: EB within the backwall height; pier just above the
        # cap or pedestals, under the dimensions
        z_bl = (max(t[1] for t in s.backwall_top) - 0.6) if s.kind == "EB" else max(s.cap_top + 0.45, max(tops) + 0.1)
        if s.kind == "PIER":
            z_hi = max(z_hi, z_bl + 0.1 * k)
        box = (xr[0], z_lo, xr[1], z_hi)
        draw_edges(v, sec["edges"], box=box, hidden=False)
        # back (backwall or left) side bs and front side fs (+1 right, -1 left)
        fs = -1 if s.key == "EB2" else 1
        x_front, x_back = (cs[1], cs[0]) if fs > 0 else (cs[0], cs[1])
        # piles: curved break; context: breaks at the clipped ends
        piles = [r for r in sec["edges"] if r["role"] in ("pile_conc", "pile_steel") and r["vis"]]
        if piles and extents(piles)[1] > z_lo + 0.01:   # no visible pile reaching the cut-off
            piles = []
        if piles:
            pe = extents(piles)
            kind = "pipe" if piles[0]["role"] == "pile_steel" else "square"
            v.pile_break((pe[0] + pe[2]) / 2, z_lo, pe[2] - pe[0], kind,
                         "PileSteel" if kind == "pipe" else "PileConc")
        mse = [r for r in sec["edges"] if r["role"] == "mse" and r["vis"]]
        if mse:
            me = extents(mse)
            v.break_line((me[0] - 0.08 * k, z_lo), (me[2] + 0.08 * k, z_lo))
        land = [r for r in sec["edges"] if r["role"] == "landing" and r["vis"]]
        if land:
            le = extents(land)
            xb = box[0] if s.key == "EB1" else box[2]
            v.break_line((xb, le[1] - 0.06 * k), (xb, le[3] + 0.06 * k))
        # centerlines
        v.line((ccl, z_lo - 0.3 * k), (ccl, s.cap_top + 0.5), "CL_Major")
        v.leader([(ccl, z_lo - 0.18 * k), (ccl + fs * 0.3 * k, z_lo - 0.18 * k)], self.cl_name(),
                 "left" if fs > 0 else "right", cl=True)
        for i, b in enumerate(s.bearings):
            v.line((b["s"], s.cap_top - 0.2), (b["s"], z_bl + 0.15), "CL_Minor")
            bf = fs if s.kind == "EB" else (1 if b["s"] > ccl else -1)
            v.leader([(b["s"], z_bl), (b["s"] + bf * 0.3 * k, z_bl)], "BEARING", "left" if bf > 0 else "right",
                     cl=True)
        # reinforcement
        dots, shapes = self._section_bars(xc, depth)
        for mark, pts in dots.items():
            for p, rad in pts:
                v.dot(p, rad)
        for bar, pts in shapes:
            v.pl(pts, "Rebar")
        # callouts beside the front face
        items = []
        cap_dots = {m: [p for p, _ in pts] for m, pts in dots.items()}
        bottom_z = None
        for mark, ps in cap_dots.items():
            e = s.table[mark]
            if e["family"] == "cap_long":
                near = sorted(ps, key=lambda p: -fs * p[0])
                if e["subtype"] == "side":
                    col = [p for p in ps if abs(p[0] - near[0][0]) < 0.02]
                    items.append((sorted(col, key=lambda p: p[1]), "%d~%s (EF)" % (len(col), mark)))
                elif e["subtype"] == "bottom":
                    bottom_z = min(p[1] for p in ps)
                    grp = [p for p in ps if fs * (p[0] - ccl) > 0]
                    items.append((grp, "%d~%s" % (len(ps), mark)))
                else:
                    items.append(([near[0]], "%d~%s" % (len(ps), mark)))
            elif e["family"] == "cap_added":   # inside the cap, fanned up to a knee beside the group
                tips = sorted(ps, key=lambda p: -fs * p[0])
                far = tips[-1]
                knee = (far[0] - fs * 0.15 * k, far[1] + 0.32 * k)
                v.leader_fan(tips, knee, "%d~%s" % (len(ps), mark), "right" if fs > 0 else "left")
            elif e["family"] == "pedestal":
                near = max(ps, key=lambda p: fs * p[0])
                items.append(([near], "%d~%s" % (len(ps), mark)))
        hoop = None
        for bar, pts in shapes:
            fam = bar["family"]
            if fam == "cap_trans":
                hoop = (bar, pts)
                zm = s.cap_bot + 0.62 * (s.cap_top - s.cap_bot)
                tip = (max((q[0] for q in pts), key=lambda x: fs * x), zm)
                items.append(([tip], bar["mark"]))
            elif fam == "pedestal":
                top = max(pts, key=lambda p: (p[1], fs * p[0]))
                items.append(([top], bar["mark"]))
        callouts(v, items, x_front + fs * 0.25 * k, fs)
        # backwall: horizontals cut (dots), verticals in plane
        if s.kind == "EB":
            vb = [(bar, pts) for bar, pts in shapes if bar["family"] == "backwall"]
            if vb:   # the front-face vertical, labelled toward the FFBW side
                bar, pts = max(vb, key=lambda t: fs * t[1][0][0])
                zq = s.cap_top + 2.9
                v.leader([(pts[0][0], zq), (s.ffbw_s + fs * 0.3 * k, zq + 0.12 * k)], "%s (EF)" % bar["mark"],
                         "left" if fs > 0 else "right")
            v.leader([(s.ffbw_s, s.cap_top + 2.0), (s.ffbw_s + fs * 0.3 * k, s.cap_top + 2.0)], "FFBW",
                     "left" if fs > 0 else "right")
            if land:   # the slab stub over the backwall, labelled outside the back face
                xq = (box[0] + 0.08) if s.key == "EB1" else (box[2] - 0.08)
                ztop = max(p[1] for r in land for p in edge_points(r) if abs(p[0] - xq) < 0.5)
                v.leader([(xq, ztop), (xq - fs * 0.12 * k, ztop + 0.14 * k)], "LANDING SLAB",
                         "right" if fs > 0 else "left")
            if mse:
                face = me[0] if fs > 0 else me[2]
                v.leader([(face, z_lo + 0.3), (face - fs * 0.25 * k, z_lo + 0.3)], "FRONT FACE OF\\PMSE WALL",
                         "right" if fs > 0 else "left")
        if piles and tag == "at_pile":   # described on the back side, clear of the MSE wall
            pe = extents(piles)
            side_x = pe[0] if fs > 0 else pe[2]
            desc = ("18\" SQUARE\\PPRESTRESSED\\PCONCRETE PILE" if piles[0]["role"] == "pile_conc"
                    else "20\" Ø STEEL\\PPIPE PILE")
            zq = min(z_lo + 0.25 * pile_show, s.cap_bot - 0.55 * k)   # below the bottom bar row
            v.leader([(side_x, zq), (side_x - fs * 0.2 * k, zq)], desc, "right" if fs > 0 else "left")
        # ------------------------------------------------ dimensions
        dot_all = [p for ps in cap_dots.values() for p in ps]
        lowz = min(p[1] for p in dot_all if p[1] < s.cap_bot + 0.6)
        bot = sorted({round(p[0], 4) for p in dot_all if abs(p[1] - lowz) < 0.06})
        yb1 = s.cap_bot - 0.3 * k
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
        # above: overall and the splits at the backwall face, bearings and centerline
        zt0 = (max(p[1] for r in sec["edges"] if r["vis"] and r["role"] == "backwall" for p in edge_points(r))
               if s.kind == "EB" else max(tops))
        yt1 = z_hi + 0.35 * k
        yt2 = yt1 + 0.3 * k
        xs = {round(cs[0], 6), round(cs[1], 6), round(ccl, 6)} | {round(b["s"], 6) for b in s.bearings}
        if s.kind == "EB":
            xs |= {round(s.ffbw_s, 6)}
        chain_dims(v, sorted(xs), None, zt0, yt1, step=0.125)
        v.dim((cs[0], zt0), (cs[1], zt0), yt2 - zt0)
        # back side: bar layout up the face (and the backwall), then heights
        lv = []
        for mark, ps in cap_dots.items():
            e = s.table[mark]
            if e["family"] == "cap_long":
                lv += [p[1] for p in ps]
        lv = sorted(set(round(z, 4) for z in lv))
        zs = [s.cap_bot, lv[0], lv[-1], s.cap_top]
        texts = [None, spaces_text(lv), None]
        if s.kind == "EB":
            hz = sorted({round(p[1], 4) for m, ps in cap_dots.items() if s.table[m]["family"] == "backwall"
                         for p in ps})
            z_bw = zt0
            if hz:
                mark = [m for m in cap_dots if s.table[m]["family"] == "backwall"][0]
                zs += [hz[0], hz[-1], z_bw]
                texts += [None, series_text(hz, mark, ef=True), None]
            else:
                zs += [z_bw]
                texts += [None]
        xl1 = x_back - fs * 0.35 * k
        xl2 = xl1 - fs * 0.3 * k
        chain_dims(v, zs, texts, x_back, xl1, vertical=True)
        hz2 = [s.cap_bot, s.cap_top] + ([zt0] if s.kind == "EB" else [])
        chain_dims(v, hz2, None, x_back, xl2, vertical=True, step=0.125)
        # cover by a small dimension at the front face
        if hoop:
            bar, pts = hoop
            r = bar["dia_in"] / 24.0
            leg = max((p[0] for p in pts), key=lambda x: fs * x) + fs * r
            zc = s.cap_bot + 0.3 * (s.cap_top - s.cap_bot)
            cov = abs(x_front - leg)
            v.dim((leg, zc), (x_front, zc), 0.0, 0.0,
                  "%s COVER\\P(TYP., U.N.O.)" % fdot.ft_in(cov, 0.25), outside=1 if fs > 0 else -1)
        yt = min(yb1 - 0.3 * k, z_lo - 0.4 * k)
        v.title(((box[0] + box[2]) / 2, yt - 0.3 * k), "SECTION %s-%s" % (letter, letter), subtitle)
        return v

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
    def cheek_view(self, zone, cheek, letter, wwr_note=2):
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
            v.pl(proj(b, fn), "Rebar")
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
        v.dim((inner, z0), (inner, s.cap_bot), -(xl - inner), 90, fdot.ft_in(s.cap_bot - z0) + "\\PLUG",
              outside=-1)
        # labels inside the wall face (clear of the shaded WWR band), as on the sample sheets
        wx = [fn(p)[0] for b in w if "Side" in b["name"] for p in barlib.polyline3(b, 10.0)]
        band = (min(wx), max(wx)) if wx else (x0, x0)
        right = (band[0] + band[1]) / 2 < (x0 + x1) / 2      # free face right of the band
        al, d = ("left", 1) if right else ("right", -1)
        xin = band[1] + 0.06 * k if right else band[0] - 0.06 * k
        zm = (s.cap_bot + z1) / 2
        v.leader([((band[0] + band[1]) / 2, zm - 0.6), (xin + d * 0.15 * k, zm - 0.6 - 0.15 * k)],
                 "SHADED AREA SHOWS\\PLIMITS OF WWR\\P(SEE NOTE %d)" % wwr_note, al)
        v.leader([(xin + d * 0.1, s.cap_bot + 0.6), (xin + d * 0.3 * k, s.cap_bot + 0.6 + 0.15 * k)],
                 "END BENT CAP", al)
        um = xs_v[0] if right else xs_v[-1]          # a drawn (first or last) vertical bar
        v.leader([(um, zm + 0.9), (um + d * 0.2 * k, zm + 0.9 + 0.15 * k)], mv, al)
        hz = zs_h[-1]                                 # the top (drawn) horizontal bar
        v.leader([(xin + d * 0.1, hz), (xin + d * 0.3 * k, hz - 0.2 * k)], mh, al)
        v.title(((x0 + x1) / 2, yb - 0.3 * k - 0.45 * k), "VIEW %s-%s" % (letter, letter),
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
            v.pl(proj(x, s.P_plan), "Rebar")
        # centerlines by leaders
        v.line((ped["u"], box[1] - 0.2 * k), (ped["u"], box[3] + 0.1 * k), "CL_Minor")
        v.leader([(ped["u"], box[1] - 0.12 * k), (ped["u"] + 0.3 * k, box[1] - 0.12 * k)], "BEAM", "left", cl=True)
        v_cl = s.piles[0]["v"] if s.kind == "EB" else 0.0
        v.line((box[0] - 0.1 * k, v_cl), (box[2] + 0.1 * k, v_cl), "CL_Major")
        lab_x = box[2] + 0.1 * k
        v.leader([(lab_x - 0.05 * k, v_cl), (lab_x + 0.15 * k, v_cl + 0.18 * k)], "CAP" if s.kind == "EB" else "PIER",
                 "left", cl=True)
        for br in s.bearings:
            if vv[0] - 0.01 < br["v"] < vv[1] + 0.01:
                v.line((uu[0] - 0.2, br["v"]), (box[2] + 0.1 * k, br["v"]), "CL_Minor")
                v.leader([(lab_x - 0.05 * k, br["v"]), (lab_x + 0.15 * k, br["v"] - 0.18 * k)], "BEARING", "left",
                         cl=True)
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
            v.dim((lastu + r, zq), (uu[1], zq), 0.0, 0.0, "%s MIN.\\PCOVER" % fdot.ft_in(cov, 0.25), outside=1)
        yt = box[1] - 0.42 * k
        v.title(((box[0] + box[2]) / 2, yt), "PEDESTAL PLAN")
        lines = ["(BEAM LINE %d SHOWN. PEDESTAL BAR SPACING MAY BE SLIGHTLY" % ped["line"],
                 "ADJUSTED TO CLEAR CONFLICTS WITH MAIN CAP REINFORCEMENT)"]
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
        box = (uu[0] - 0.35, lo - 0.15, uu[1] + 0.35, ztop + 0.5)
        for rec in S["elev"]:
            if rec["role"] in ("pedestal", "cap") and rec["vis"]:
                layer, lt = layer_for(rec)
                v.record(rec, layer, lt, box)
        for x in pbars:
            v.pl(proj(x, s.P_elev), "Rebar")
        v.break_line((box[0], box[1]), (box[2], box[1]))
        for xv in (box[0], box[2]):
            v.break_line((xv, box[1]), (xv, s.cap_top + 0.04 * k))
        # construction joint at the cap top (pedestal cast on the cap)
        v.line((uu[0], s.cap_top), (uu[1], s.cap_top), "SubStrConc2_h")
        W = uu[1] - uu[0]
        v.leader([(uu[0] + 0.62 * W, s.cap_top), (uu[0] + 0.55 * W, ztop + 0.78 * k)], "CONST. JOINT", "left")
        v.leader([(uu[0] + 0.8 * W, ztop), (uu[0] + 0.72 * W, ztop + 0.52 * k)],
                 "TOP OF PEDESTAL\\P(SEE TABLE FOR\\PELEVATIONS)", "left")
        v.leader([(uu[1] - 0.02, ztop - 0.02), (uu[1] + 0.12 * k, ztop + 0.12 * k)], "¾\" X ¾\"\\PCHAMFER (TYP.)",
                 "left")
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
        v.dim((outer, zc), (uu[1], zc), 0.0, 0.0, "%s\\PCOVER" % fdot.ft_in(uu[1] - outer, 0.25), outside=1)
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
        v.line((ccl, zcd - 0.2 * k), (ccl, s.cap_top + 1.4), "CL_Major")
        v.xform = keep
        v.leader([(ccl, s.cap_top + 1.2), (ccl + 0.3 * k, s.cap_top + 1.2 + 0.15 * k)], self.cl_name(), "left",
                 cl=True)
        v.dim((cs[0], s.cap_top), (cs[1], s.cap_top), 0.35 * k + 0.6, step=0.125)
        if s.kind == "PIER":
            ws = (-s.wall_bb[4], -s.wall_bb[1])
            v.dim(T((ws[0], s.wall_bot)), T((ws[1], s.wall_bot)), -0.35 * k, step=0.125)
            for b in s.bearings:
                v.line((b["s"], s.cap_top - 0.2), (b["s"], s.cap_top + 0.9), "CL_Minor")
        v.title((ccl, zcd - 0.6 * k), "VIEW %s-%s" % (letter, letter), "(END VIEW)")
        return v
