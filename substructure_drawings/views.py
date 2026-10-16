"""Plan, elevation, section and detail views for the bents and pier.

Reinforcement follows SDM 4.3: in plan and elevation views only the first
and last bar of each series is drawn and the series is called out as
``count~mark`` with its spacing dimensioned (SDM 4.3.B/C, 4.3.1.C); every
bar is drawn in sections, end-on bars as filled circles (4.3.7.D) and bars
in the section plane as double lines at 3/4 in scale (4.3.7.B).  Stirrups in
elevation use the established CAD_AI symbolic form: one line at the bar
station with a filled dot at each end.
"""
import math
from collections import OrderedDict

from . import bars as barlib
from . import fdot
from .cad import View, text_extent
from .cad import text_extent as cad_text_w
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


def offset_outline(pts, r):
    """Closed outline of a polyline bar of radius r (double-line bar)."""
    clean = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, clean[-1]) > 1e-6:
            clean.append(p)
    if len(clean) < 2:
        return None
    n = len(clean)
    ns = []
    for i in range(n):
        a, b = clean[max(i - 1, 0)], clean[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        ns.append((-dy / L, dx / L))
    left = [(p[0] + q[0] * r, p[1] + q[1] * r) for p, q in zip(clean, ns)]
    right = [(p[0] - q[0] * r, p[1] - q[1] * r) for p, q in zip(clean, ns)]
    return left + right[::-1]


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


def spa_text(n_spaces, s_ft, step=0.25):
    if n_spaces == 1:
        return fdot.ft_in(s_ft, step)
    return "%d SPA. @ %s" % (n_spaces, fdot.ft_in(s_ft, step))


def series_chain(positions, ends, mark=None):
    """Dimension string positions/texts for a bar series between two ends."""
    chain, texts = [ends[0]], []
    for ser in series_split(sorted(positions)):
        a, b = ser[0], ser[-1]
        if abs(chain[-1] - a) > 1e-9:
            chain.append(a)
            texts.append(None)
        if abs(b - a) > 1e-9:
            chain.append(b)
            texts.append(spa_text(len(ser) - 1, (b - a) / (len(ser) - 1)) if len(ser) > 2 else None)
    if abs(chain[-1] - ends[1]) > 1e-9:
        chain.append(ends[1])
        texts.append(None)
    return chain, texts


def stack_labels(view, items, x_col, side, min_gap=None):
    """Leader callouts in a column; items = [(tip, text)] (local coords).

    side = -1 puts the column to the left (text right-aligned), +1 to the right.
    """
    if not items:
        return
    gap = min_gap or 2.0 * view.th
    items = sorted(items, key=lambda it: it[0][1])
    ys = []
    for tip, _ in items:
        y = tip[1]
        if ys and y < ys[-1] + gap:
            y = ys[-1] + gap
        ys.append(y)
    shift = (sum(t[0][1] for t in items) - sum(ys)) / len(ys)
    ys = [y + shift for y in ys]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + gap)
    for (tip, txt), y in zip(items, ys):
        knee = (x_col - side * 0.8 * view.th, y)
        view.leader([tip, knee, (x_col, y)], txt, "left" if side > 0 else "right")


def chain_dims(v, xs, texts, y_obj, y_dim, vertical=False):
    """Dimension string; texts too long for their space are lifted with a leader."""
    lift = 0
    for i in range(len(xs) - 1):
        a, b = xs[i], xs[i + 1]
        if abs(b - a) < 1e-6:
            continue
        txt = texts[i] if texts and i < len(texts) and texts[i] else fdot.ft_in(abs(b - a), 0.25)
        fits = text_extent(txt, v.th) < abs(b - a) * 0.9
        if vertical:
            v.dim((y_obj, a), (y_obj, b), -(y_dim - y_obj), 90, txt, outside=None if fits else (lift % 2 + 1))
        else:
            v.dim((a, y_obj), (b, y_obj), y_dim - y_obj, 0, txt, outside=None if fits else (lift % 3 + 1))
        if not fits:
            lift += 1


# ====================================================================
class Builder:
    """Draws the views of one support."""

    def __init__(self, sup, doc):
        self.s = sup
        self.doc = doc
        self.notes = []
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

    # ------------------------------------------------------------ plan
    def plan(self, zone):
        s = self.s
        S = s.S
        v = View(self.doc, zone, s.key + " PLAN")
        draw_edges(v, S["plan"])
        th = v.th
        u0, u1 = s.cap_u
        uL, uR = s.outer_u
        vf, vb = s.cap_v
        ex = extents(S["plan"])
        v_top, v_bot = ex[3], ex[1]
        beam_ext = 1.25
        v_span_lo = min(vf, min(b["v"] for b in s.bearings)) - beam_ext
        v_span_hi = max(vb, max(b["v"] for b in s.bearings)) + (beam_ext if s.kind == "PIER" else 0)
        y_lo = min(v_bot, v_span_lo)
        y_hi = max(v_top, v_span_hi)
        # PGL
        v.line((0, y_lo - 0.4), (0, y_hi + 0.7), "BaseLineSurveyPGL")
        v.text((0.25 * th, y_hi + 0.7), "PGL", None, "BOTTOM_LEFT")
        # cap / pier centerline (labels on the right, dims on the left)
        v_cl = s.piles[0]["v"] if s.kind == "EB" else 0.0
        v.line((uL - 0.8, v_cl), (uR + 0.8, v_cl), "CL_Major")
        v.cltext((uR + 0.9, v_cl), "CAP & PILES" if s.kind == "EB" else "PIER")
        for p in s.piles:
            h = p["width"] / 2 + 0.3
            v.line((p["u"], p["v"] - h), (p["u"], p["v"] + h), "CL_Minor")
        for b in s.bearings:
            v.line((uL - 0.8, b["v"]), (uR + 0.8, b["v"]), "CL_Minor")
            dy = (-1.4 if b["v"] < v_cl else 1.4) * th if s.kind == "PIER" else -1.4 * th
            v.cltext((uR + 0.9, b["v"] + dy * 0.0 + (dy if abs(b["v"] - v_cl) < 3 * th else 0)), "BEARING")
        # beam centerlines from each bearing toward its span
        for b in s.bearings:
            d = self.span_side(b)
            end = v_span_lo if d < 0 else v_span_hi
            for bl in s.beam_lines:
                v.line((bl["u"], b["v"]), (bl["u"], end), "CL_Minor")
                v.cltext((bl["u"] + 0.3 * th, end + d * 0.3 * th), "BEAM " + s.beam_id(b["span"], bl["line"]),
                         valign="TOP" if d < 0 else "BOTTOM")
        # complementary skew angle (SDM 2.14): 90 degrees, typical
        b0 = s.bearings[0]
        bl0 = s.beam_lines[-1]
        d0 = self.span_side(b0)
        tip = (bl0["u"] + 0.18, b0["v"] + d0 * 0.18)
        v.arc((bl0["u"], b0["v"]), 0.45, 270 if d0 < 0 else 0, 360 if d0 < 0 else 90, "Dimension")
        v.leader([tip, (bl0["u"] + 1.3, b0["v"] + d0 * 0.95)], "90°00'00\" (TYP.)")
        # FFBW and station of the station line crossing
        if s.kind == "EB":
            what = "BEGIN BRIDGE" if s.key == "EB1" else "END BRIDGE"
            txt = "%s\\PFFBW %s\\PSTA. %s" % (what, s.title, fdot.station(s.station(s.ffbw_y)))
            v.leader([(0, s.ffbw_v), (-2.2, y_hi + 1.3), (-2.6, y_hi + 1.3)], txt, "right")
            v.leader([(u0 + 1.5, s.ffbw_v), (u0 + 0.9, y_hi + 0.6)], "FFBW", "right")
        else:
            knee = (-2.2, y_hi + 1.3)
            v.leader([(0, 0), knee, (-2.6, knee[1])], "PIER", "right", cl=True)
            v.text((-2.6 - 0.4 * th, knee[1] - 1.6 * th), "STA. %s" % fdot.station(s.station(s.y0)), None, "MIDDLE_RIGHT")
        # ---------------------------------------------------- dimensions
        y1 = y_hi + 0.6 * IN * v.sf
        y2 = y1 + 0.375 * IN * v.sf
        if s.kind == "EB":
            chain_dims(v, [uL, u0, u1, uR], None, v_top, y1)
            v.dim((uL, v_top), (uR, v_top), y2 - v_top)
        else:
            v.dim((u0, vb), (u1, vb), y1 - vb)
        yb = y_lo - 0.55 * IN * v.sf
        xs = sorted([u0, u1, 0.0] + [bl["u"] for bl in s.beam_lines])
        chain_dims(v, xs, None, vf, yb)
        v.text((uL - 0.5 * th, yb + 0.3 * th), "BEAM SPACING *", None, "BOTTOM_RIGHT")
        yb2 = yb - 0.4 * IN * v.sf
        xs = sorted([u0, u1] + [p["u"] for p in s.piles])
        chain_dims(v, xs, None, vf, yb2)
        v.text((uL - 0.5 * th, yb2 + 0.3 * th), "PILE SPACING *", None, "BOTTOM_RIGHT")
        yb = yb2
        # transverse dims on the left
        xl1 = uL - 0.6 * IN * v.sf
        xl2 = xl1 - 0.375 * IN * v.sf
        if s.kind == "EB":
            ys = sorted({round(vf, 6), round(vb, 6), round(s.ffbw_v, 6), round(s.bearings[0]["v"], 6), round(v_cl, 6)})
        else:
            ys = sorted({round(vf, 6), round(vb, 6), 0.0} | {round(b["v"], 6) for b in s.bearings})
        chain_dims(v, ys, None, uL, xl1, vertical=True)
        v.dim((uL, vf), (uL, vb), -(xl2 - uL), 90)
        if s.kind == "EB":
            # cheek walls with lugs
            cv = extents(S["plan"], ("cheek",))
            c = s.cheeks[-1]
            xr = uR + 0.6 * IN * v.sf
            chain_dims(v, sorted({round(cv[1], 6), round(vf, 6), round(vb, 6), round(cv[3], 6)}), None, c["u_hi"], xr, vertical=True)
            for c, lab in zip(s.cheeks, ("D", "E")):
                look = (1, 0) if c["side"] == "left" else (-1, 0)
                xc = (c["u_lo"] - 0.35) if c["side"] == "left" else (c["u_hi"] + 0.35)
                v.section_cut((xc, vf - 0.3), (xc, cv[3] + 0.3), lab, look)
        else:
            # end view D-D looks along +X (global), i.e. toward -u in this plan
            look = (1, 0) if s.e1 > 0 else (-1, 0)
            xc = (uL - 0.5) if look[0] > 0 else (uR + 0.5)
            v.section_cut((xc, vf - 0.3), (xc, vb + 0.3), "D", look)
        # direction of stationing (stations increase toward -Y), below-right of the plan
        sd = -s.up
        L = 0.9 * IN * v.sf
        y0 = vf - 0.8 if sd < 0 else vf - 0.8 - L
        v.stationing_arrow((uR + 1.6, y0), (0, sd), 0.9)
        v.title((0, yb - 0.5 * IN * v.sf), "PLAN")
        self.notes.append("* DIMENSIONS MEASURED ALONG %s." % ("FFBW" if s.kind == "EB" else "CL PIER"))
        return v

    # ------------------------------------------------------- elevation
    def _broken(self, v, edges, z_break, extra_box=None):
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

    def elevation(self, zone, z_break=None, pile_show=1.5):
        """Concrete elevation with layout dimensions and elevation points."""
        s = self.s
        S = s.S
        v = View(self.doc, zone, s.key + " ELEVATION")
        th = v.th
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
        # piles: break symbols, numbers, centerlines
        for p in s.piles:
            w = p["width"] / 2
            v.break_line((p["u"] - w - 0.2, z_pile), (p["u"] + w + 0.2, z_pile))
            pc = (p["u"], z_pile - 0.55)
            v.circle(pc, 0.09 * IN * v.sf, "Symbols")
            v.text(pc, str(p["no"]), None, "MIDDLE_CENTER")
            v.line((p["u"], s.cap_bot + 0.5), (p["u"], z_pile + 0.25), "CL_Minor")
        if z_break:
            self._break_lines(v, z_break, s.wall_u[0] - 0.5, s.wall_u[1] + 0.5)
        ex = extents(S["elev"])
        z_top = ex[3]
        z_pgl = (max(t[1] for t in s.backwall_top) if s.kind == "EB" else s.cap_top) + 0.9
        v.line((0, s.cap_bot - 0.4), (0, z_pgl), "BaseLineSurveyPGL")
        v.text((0.25 * th, z_pgl), "PGL", None, "BOTTOM_LEFT")
        for bl in s.beam_lines:
            ids = "/".join(s.beam_id(b["span"], bl["line"]) for b in s.bearings)
            if s.kind == "EB":
                v.line((bl["u"], s.cap_top - 0.3), (bl["u"], s.cap_top + 1.9), "CL_Minor")
                v.cltext((bl["u"] - 0.25 * th, s.cap_top + 1.95), "BEAM " + ids, rot=90.0, valign="BOTTOM")
            else:
                top = s.cap_top + 1.3
                v.line((bl["u"], s.cap_top - 0.3), (bl["u"], top), "CL_Minor")
                txt = "BEAM " + ids
                v.cltext((bl["u"] - (cad_text_w(txt, th) + 1.25 * th) / 2, top + 0.4 * th), txt, valign="BOTTOM")
        # elevation points (values in the table of elevations)
        z_tops = z_top - 0.05
        for letter, desc, u, z in self.elev_points:
            side = 1 if u >= 0 else -1
            if "BACKWALL AT END" in desc or "BOTTOM OF CAP" in desc:
                side = -side  # point these inward, clear of the cheek labels
            q = T((u, z))
            al = "left" if side > 0 else "right"
            if "PGL" in desc:
                v.leader([q, (q[0] + 0.8, q[1] + 0.45)], "PT. " + letter)
            elif z >= z_tops:
                v.leader([q, (q[0] + side * 0.8, q[1] - 0.1)], "PT. " + letter, al)
            elif z >= s.cap_top - 0.01:
                v.leader([q, (q[0] + side * 0.9, q[1] + 0.6)], "PT. " + letter, al)
            else:
                v.leader([q, (q[0] + side * 0.9, q[1] - 0.8)], "PT. " + letter, al)
        # vertical dimensions on the left
        x1 = uL - 0.6 * IN * v.sf
        x2 = x1 - 0.375 * IN * v.sf
        if s.kind == "EB":
            c = s.cheeks[0]
            zs = sorted({round(c["bot"], 6), round(s.cap_bot, 6), round(s.cap_top, 6),
                         round(s.backwall_top[0][1], 6), round(c["top"], 6)})
            chain_dims(v, zs, None, uL, x1, vertical=True)
            v.dim((uL, zs[0]), (uL, zs[-1]), -(x2 - uL), 90)
        else:
            v.dim((uL, s.cap_bot), (uL, s.cap_top), -(x1 - uL), 90)
            if z_break:
                pa = T((s.wall_u[0], s.wall_bot))
                keep, v.xform = v.xform, None
                v.dim(pa, (s.wall_u[0], s.wall_top), -(x1 - s.wall_u[0]), 90, fdot.ft_in(s.wall_top - s.wall_bot))
                v.xform = keep
                v.mtext((s.wall_u[0] + 0.7, (s.wall_top + pa[1]) / 2),
                        "PIER WALL\\P3'-0\" THICK\\P(PROVISIONAL)", attach=4)
        # pile embedment and pile description
        p = s.piles[-1]
        xe = p["u"] + p["width"] / 2
        v.dim((xe, s.cap_bot), (xe, p["top"]), -(uR + 0.6 * IN * v.sf - xe), 90)
        desc = ("18\" SQUARE\\PPRESTRESSED\\PCONCRETE PILE\\P(TYP.)" if p["shape"] == "square"
                else "20\" Ø STEEL\\PPIPE PILE\\P(TYP.)")
        v.leader([(xe, T((0, z_pile + 0.6))[1]), (uR + 0.7, T((0, z_pile + 0.1))[1])], desc)
        # section cuts
        self._section_marks(v, T)
        yb = T((0, z_pile))[1] - 0.55 - 0.15 * IN * v.sf
        v.title((0, yb - 0.3 * IN * v.sf), "ELEVATION",
                "(LOOKING BACK STATION)" if s.key == "EB1" else "(LOOKING AHEAD STATION)")
        return v

    def _section_marks(self, v, T):
        s = self.s
        look = (1, 0) if s.e1 > 0 else (-1, 0)
        z_lo = s.cap_bot - 0.9
        z_hi = (max(t[1] for t in s.backwall_top) + 0.4) if s.kind == "EB" else s.cap_top + 1.0
        for tag, lab in (("between_piles", "A"), ("at_pile", "B"), ("at_beam", "C")):
            uc = s.u(s.S["sections"][tag]["x_global_ft"])
            v.section_cut(T((uc, z_lo)), T((uc, z_hi)), lab, look)

    # ------------------------------------------------ reinforcement elevation
    def reinforcement_elevation(self, zone):
        s = self.s
        S = s.S
        v = View(self.doc, zone, s.key + " REINFORCEMENT ELEVATION")
        th = v.th
        z_pile = s.cap_bot - 1.25
        top_lim = s.cap_top + 1.2 if s.kind == "PIER" else 1e4
        for rec in S["elev"]:
            if rec["role"] in ("pier_wall",):
                continue
            layer, lt = layer_for(rec)
            v.record(rec, layer, lt, (-1e4, z_pile, 1e4, top_lim))
        if s.kind == "PIER":
            for rec in S["elev"]:
                if rec["role"] == "pier_wall" and rec["vis"]:
                    layer, lt = layer_for(rec)
                    v.record(rec, layer, lt, (-1e4, z_pile, 1e4, s.cap_bot + 0.01))
        for p in s.piles:
            w = p["width"] / 2
            v.break_line((p["u"] - w - 0.2, z_pile), (p["u"] + w + 0.2, z_pile))
            pc = (p["u"], z_pile - 0.45)
            v.circle(pc, 0.09 * IN * v.sf, "Symbols")
            v.text(pc, str(p["no"]), None, "MIDDLE_CENTER")
        if s.kind == "PIER":
            v.break_line((s.wall_u[0] - 0.4, z_pile), (s.wall_u[1] + 0.4, z_pile))
        v.line((0, z_pile - 0.2), (0, (max(t[1] for t in s.backwall_top) if s.kind == "EB" else s.cap_top) + 0.5),
               "BaseLineSurveyPGL")
        self._elev_steel(v)
        self._section_marks(v, lambda p: p)
        z_ttl = z_pile - 0.45 - 1.0 * IN * v.sf
        v.title((0, z_ttl), "ELEVATION - REINFORCEMENT",
                "(LOOKING BACK STATION)" if s.key == "EB1" else "(LOOKING AHEAD STATION)")
        return v

    def _elev_steel(self, v):
        s = self.s
        th = v.th
        fn = s.P_elev
        dot_r = fdot.DOT_IN / 24 * v.sf
        callouts = []
        u0, u1 = s.cap_u
        ends = s.outer_u
        # longitudinal cap bars: one line per distinct level
        for sub in ("top", "bottom", "side"):
            bs = s.bars_of(family="cap_long", subtype=sub)
            if not bs:
                continue
            levels = OrderedDict()
            for b in bs:
                levels.setdefault(round(b["pts"][0][2], 3), []).append(b)
            for z, grp in levels.items():
                v.pl(proj(grp[0], fn), "Rebar")
            mark = bs[0]["mark"]
            if sub == "side":
                faces = len({round(b["pts"][0][1], 2) for b in bs})
                txt = "%d~%s (EF)" % (len(bs) // max(faces, 1), mark)
                z = sorted(levels)[len(levels) // 2]
                tip = (u0 + 0.86 * (u1 - u0), z)
            else:
                txt = "%d~%s" % (len(bs), mark)
                z = list(levels)[0]
                tip = (u0 + 0.93 * (u1 - u0), z)
            callouts.append((tip, txt))
        # stirrups: first/last bar of each uniform series (line + end dots)
        groups = s.transverse_groups()
        allu = []
        for g in groups:
            us = g["u"]
            allu += us
            for ser in series_split(us):
                for u in (ser[0], ser[-1]):
                    b = g["bars"][us.index(u)]
                    zs = [p[2] for p in b["pts"]]
                    a, c = (u, min(zs)), (u, max(zs))
                    v.line(a, c, "Rebar")
                    v.dot(a, dot_r)
                    v.dot(c, dot_r)
        z_top = (max(t[1] for t in s.backwall_top) if s.kind == "EB" else s.cap_top)
        z1 = z_top + 0.6 * IN * v.sf
        z2 = z1 + 0.95 * IN * v.sf
        chain, texts = series_chain(allu, ends)
        chain_dims(v, chain, texts, s.cap_top, z1)
        for g in groups:
            us = g["u"]
            txt = "%d~%s" % (len(us), g["mark"])
            if us[-1] - us[0] > text_extent(txt, th) * 1.05:
                v.dim((us[0], s.cap_top), (us[-1], s.cap_top), z2 - s.cap_top, 0, txt)
            else:
                v.text(((us[0] + us[-1]) / 2, z2 + 0.3 * th), txt, None, "BOTTOM_CENTER")
        v.text((ends[0] - 0.5 * th, z2 + 0.3 * th), "CAP STIRRUPS *", None, "BOTTOM_RIGHT")
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
            for mark in OrderedDict((b["mark"], 1) for b in s.bars_of(family=fam)):
                bs = s.bars_of(mark=mark)
                pts = proj(bs[-1], fn)
                tip = pts[len(pts) // 2]
                locs = len({round(min(p[0] for p in x["pts"]), 2) for x in bs})
                txt = "%d~%s" % (len(bs), mark)
                if fam == "cap_added":
                    txt += " (%d EA. BAY)" % (len(bs) // max(locs, 1))
                else:
                    txt += " (%d EA. END)" % (len(bs) // 2)
                callouts.append((tip, txt))
        # backwall
        if s.kind == "EB":
            vert = s.bars_of(family="backwall", subtype="vert")
            face = min(vert, key=lambda b: abs(b["pts"][0][1] - s.ffbw_y))["pts"][0][1]
            front = sorted((b for b in vert if abs(b["pts"][0][1] - face) < 0.05), key=lambda b: s.u(b["pts"][0][0]))
            us = [s.u(b["pts"][0][0]) for b in front]
            for b in (front[0], front[-1]):
                v.pl(proj(b, fn), "Rebar")
            zt = max(p[2] for p in front[-1]["pts"])
            callouts.append(((us[-1], zt - 0.5), "%d~%s (EF)" % (len(front), front[0]["mark"])))
            hor = s.bars_of(family="backwall", subtype="horiz")
            hface = sorted(hor, key=lambda b: abs(b["pts"][0][1] - face))
            hf = [b for b in hor if abs(b["pts"][0][1] - hface[0]["pts"][0][1]) < 0.05]
            for b in hf:
                v.pl(proj(b, fn), "Rebar")
            hz = sorted(b["pts"][0][2] for b in hf)
            callouts.append(((u0 + 0.8 * (u1 - u0), hz[len(hz) // 2]), "%d~%s (EF)" % (len(hf), hf[0]["mark"])))
            # backwall vertical spacing and horizontal bar spacing
            z3 = z2 + 0.95 * IN * v.sf
            bw_u = sorted(s.u(x) for x in (s.backwall_bb[0], s.backwall_bb[3]))
            chain, texts = series_chain(us, bw_u)
            texts = [(t.replace("SPA.", "SPA.") if t else t) for t in texts]
            chain_dims(v, chain, texts, z_top, z3)
            v.text((ends[0] - 0.5 * th, z3 + 0.3 * th), "BACKWALL VERTICALS", None, "BOTTOM_RIGHT")
            xr = ends[1] + 0.6 * IN * v.sf
            chain, texts = series_chain(hz, (s.cap_top, s.backwall_top[-1][1]))
            chain_dims(v, chain, texts, ends[1], xr, vertical=True)
        stack_labels(v, callouts, ends[1] + (1.9 if s.kind == "EB" else 1.0), 1)
        self.notes.append("* STIRRUP DIMENSIONS ARE TO BAR CENTERLINES.")

    # ----------------------------------------------------------- sections
    def section(self, zone, tag, letter, subtitle):
        s = self.s
        S = s.S
        sec = S["sections"][tag]
        xc = sec["x_global_ft"]
        depth = S["section_depth_ft"]
        v = View(self.doc, zone, "%s SECTION %s" % (s.key, letter))
        th = v.th
        cs = s.cap_s
        z_lo = s.cap_bot - 1.0
        if s.key == "EB1":
            xr = (cs[0] - 1.0, cs[1] + 2.75)
        elif s.key == "EB2":
            xr = (cs[0] - 2.75, cs[1] + 1.0)
        else:
            xr = (cs[0] - 0.35, cs[1] + 0.35)
        tops = [p[1] for r in sec["edges"] if r["vis"] for p in edge_points(r) if xr[0] <= p[0] <= xr[1]]
        z_hi = max(tops) + 0.25
        box = (xr[0], z_lo, xr[1], z_hi)
        draw_edges(v, sec["edges"], box=box, hidden=False)
        v.break_line((box[0] + 0.15, z_lo), (box[2] - 0.15, z_lo))
        ccl = (cs[0] + cs[1]) / 2
        v.line((ccl, z_lo - 0.25), (ccl, s.cap_top + 0.8), "CL_Major")
        v.cltext((ccl - 0.25 * th, s.cap_top + 0.85), "CAP & PILES" if s.kind == "EB" else "PIER", rot=90, valign="BOTTOM")
        for b in s.bearings:
            v.line((b["s"], s.cap_top - 0.2), (b["s"], s.cap_top + 1.3), "CL_Minor")
            v.cltext((b["s"] - 0.25 * th, s.cap_top + 1.35), "BEARING", rot=90, valign="BOTTOM")
        # reinforcement
        dots, shapes = self._section_bars(xc, depth)
        for mark, pts in dots.items():
            for p, rad in pts:
                v.dot(p, rad)
        for bar, pts in shapes:
            outline = offset_outline(pts, bar["dia_in"] / 24.0)
            if outline:
                v.pl(outline, "Rebar", closed=True)
        labels_l, labels_r = [], []
        mid = ccl
        for mark, pts in dots.items():
            e = s.table[mark]
            ps = [p for p, _ in pts]
            if e["subtype"] == "side" or e["family"] == "backwall":
                tip = min(ps, key=lambda p: p[0]) if s.key != "EB2" else max(ps, key=lambda p: p[0])
                txt = "%d~%s (EF)" % (max(1, len(ps) // 2), mark)
            else:
                tip = min(ps, key=lambda p: (p[0], p[1])) if s.key != "EB2" else max(ps, key=lambda p: (p[0], -p[1]))
                txt = "%d~%s" % (len(ps), mark) if len(ps) > 1 else mark
            (labels_l if tip[0] <= mid else labels_r).append((tip, txt))
        seen = set()
        for bar, pts in shapes:
            mark = bar["mark"]
            if mark in seen:
                continue
            seen.add(mark)
            tip = pts[len(pts) // 3]
            txt = mark + (" (EF)" if bar["family"] == "backwall" else "")
            (labels_l if tip[0] <= mid else labels_r).append((tip, txt))
        # context labels join the stacks so that no callouts overlap
        if s.kind == "EB":
            fill = labels_l if s.key == "EB1" else labels_r
            span = labels_r if s.key == "EB1" else labels_l
            fill.append(((s.ffbw_s, s.cap_top + 2.2), "FFBW"))
            mse = [p[0] for r in sec["edges"] if r["role"] == "mse" and r["vis"] for p in edge_points(r)
                   if box[0] <= p[0] <= box[2]]
            if mse:
                face = max(mse) if s.key == "EB1" else min(mse)
                span.append(((face, z_lo + 0.35), "MSE WALL\\PFRONT FACE"))
            land = [p for r in sec["edges"] if r["role"] == "landing" and r["vis"] for p in edge_points(r)
                    if box[0] <= p[0] <= box[2]]
            if land:
                xq = (box[0] + 0.4) if s.key == "EB1" else (box[2] - 0.4)
                near = [p for p in land if abs(p[0] - xq) < 0.7] or land
                fill.append(((xq, max(p[1] for p in near)), "LANDING SLAB"))
        stack_labels(v, labels_l, box[0] - 0.15, -1)
        stack_labels(v, labels_r, box[2] + 0.15, 1)
        # dimensions
        y1 = z_lo - 0.55 * IN * v.sf
        y2 = y1 - 0.375 * IN * v.sf
        xs = {round(cs[0], 6), round(cs[1], 6), round(ccl, 6)} | {round(b["s"], 6) for b in s.bearings}
        if s.kind == "EB":
            xs |= {round(s.ffbw_s, 6)}
        chain_dims(v, sorted(xs), None, s.cap_bot, y1)
        v.dim((cs[0], s.cap_bot), (cs[1], s.cap_bot), y2 - s.cap_bot)
        right = s.key != "EB2"
        xface = cs[1] if right else cs[0]
        off = 0.45 * IN * v.sf
        v.dim((xface, s.cap_bot), (xface, s.cap_top), -off if right else off, 90)
        cov = self._cover(shapes)
        if cov:
            v.text(((box[0] + box[2]) / 2, y2 - 1.3 * th), "%s COVER TO STIRRUPS (TYP., U.N.O.)" %
                   fdot.ft_in(cov / 12.0, 0.25, mtext=False), None, "TOP_CENTER")
        v.title(((box[0] + box[2]) / 2, y2 - 0.6 * IN * v.sf), "SECTION %s-%s" % (letter, letter), subtitle)
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

    def _cover(self, shapes):
        lows = [min(p[1] for p in pts) - bar["dia_in"] / 24.0 for bar, pts in shapes if bar["family"] == "cap_trans"]
        if not lows:
            return None
        return round((min(lows) - self.s.cap_bot) * 12.0 * 4) / 4.0

    # -------------------------------------------------------- cheek views
    def cheek_view(self, zone, cheek, letter):
        s = self.s
        S = s.S
        cv = S["cheek_views"][cheek["name"]]
        v = View(self.doc, zone, "%s VIEW %s" % (s.key, letter))
        th = v.th
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
        # WWR limits (shaded, drawn first so the bars plot over them)
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
            v.hatch_poly(ring, scale=0.09 * v.sf)
            v.pl(ring, "Rebar2", closed=True)
        for b in (verts[0], verts[-1], hors[0], hors[-1]):
            v.pl(proj(b, fn), "Rebar")
        # dims: vertical bars along the bottom, horizontal bars up the side
        yb = z0 - 0.55 * IN * v.sf
        chain, texts = series_chain(xs_v, (x0, x1))
        chain_dims(v, chain, texts, z0, yb)
        v.dim((x0, z0), (x1, z0), yb - 0.375 * IN * v.sf - z0)
        out = x1 if sgn > 0 else x0
        xr = (x1 + 0.55 * IN * v.sf) if sgn > 0 else (x0 - 0.55 * IN * v.sf)
        chain, texts = series_chain(zs_h, (z0, z1))
        chain_dims(v, chain, texts, out, xr, vertical=True)
        v.dim((out, z0), (out, z1), -((xr + (0.375 if sgn > 0 else -0.375) * IN * v.sf) - out), 90)
        mv, mh = verts[0]["mark"], hors[0]["mark"]
        sp_v = max(b - a for a, b in zip(xs_v, xs_v[1:]))
        sp_h = max(b - a for a, b in zip(zs_h, zs_h[1:]))
        side = -sgn
        xcol = (x0 - 0.5) if side < 0 else (x1 + 0.5)
        items = [((xs_v[0] if side < 0 else xs_v[-1], z0 + 0.62 * (z1 - z0)), "%d~%s @ %s MAX." % (len(verts), mv, fdot.ft_in(sp_v, 0.25))),
                 (((x0 + x1) / 2, zs_h[-1]), "%d~%s @ %s MAX." % (len(hors), mh, fdot.ft_in(sp_h, 0.25)))]
        stack_labels(v, items, xcol, side)
        v.leader([((x0 + x1) / 2, z0 + 0.12), (xcol, z0 - 0.3)], "WWR 4x4-W1.4xW1.4\\P(SHADED AREA\\PSHOWS LIMITS)",
                 "right" if side < 0 else "left")
        v.leader([((x0 + x1) / 2 + 0.4 * sgn, s.cap_bot + 1.0), (xcol, s.cap_bot + 1.6)], "END BENT CAP",
                 "right" if side < 0 else "left")
        v.title(((x0 + x1) / 2, yb - 0.375 * IN * v.sf - 0.7 * IN * v.sf), "VIEW %s-%s" % (letter, letter),
                "(%s CHEEK WALL)" % ("LEFT" if cheek["u"] < 0 else "RIGHT"))
        return v

    # --------------------------------------------------------- pedestals
    def pedestal_plan(self, zone, ped):
        s = self.s
        S = s.S
        b = ped["bb"]
        uu = sorted((s.u(b[0]), s.u(b[3])))
        vv = sorted((s.v(b[1]), s.v(b[4])))
        m = 0.7
        box = (uu[0] - m, vv[0] - m, uu[1] + m, vv[1] + m)
        v = View(self.doc, zone, "%s PEDESTAL PLAN %d" % (s.key, ped["line"]))
        for rec in S["plan"]:
            if rec["role"] in ("pedestal", "pad", "cap", "backwall") and rec["vis"]:
                layer, lt = layer_for(rec)
                v.record(rec, layer, lt, box)
        num = ped["name"][-2:]
        pbars = [x for x in s.bars if x["family"] == "pedestal" and x["group"].endswith(num + "Bars")]
        for x in pbars:
            v.pl(proj(x, s.P_plan), "Rebar")
        th = v.th
        v.line((ped["u"], box[1]), (ped["u"], box[3]), "CL_Minor")
        v.cltext((ped["u"] + 0.25 * th, box[3]), "BEAM", rot=90, valign="TOP")
        for br in s.bearings:
            if box[1] < br["v"] < box[3]:
                v.line((box[0], br["v"]), (box[2], br["v"]), "CL_Minor")
                v.cltext((box[2] + 0.2 * th, br["v"]), "BEARING")
        y1 = vv[1] + 0.55 * IN * v.sf
        v.dim((uu[0], vv[1]), (uu[1], vv[1]), y1 - vv[1])
        x1 = uu[0] - 0.55 * IN * v.sf
        v.dim((uu[0], vv[0]), (uu[0], vv[1]), -(x1 - uu[0]), 90)
        items, differ = [], []
        for sub in ("x", "y"):
            bs = [x for x in pbars if x["subtype"] == sub]
            if not bs:
                continue
            by_line = OrderedDict()
            for other in s.pedestals:
                n2 = other["name"][-2:]
                by_line[other["line"]] = sorted({x["mark"] for x in s.bars if x["family"] == "pedestal"
                                                 and x["subtype"] == sub and x["group"].endswith(n2 + "Bars")})
            marks = list(OrderedDict.fromkeys(m for ms in by_line.values() for m in ms))
            if len(marks) > 1:
                differ.append(", ".join("%s AT BEAM LINE %d" % ("/".join(ms), ln) for ln, ms in by_line.items()))
            pos = sorted(s.v(x["pts"][0][1]) for x in bs) if sub == "x" else sorted(s.u(x["x_station"]) for x in bs)
            sp = (pos[-1] - pos[0]) / max(len(pos) - 1, 1)
            pts = proj(bs[-1], s.P_plan)
            items.append((pts[len(pts) // 3], "%d~%s @ %s±" % (len(bs), "/".join(marks), fdot.ft_in(sp, 0.25))))
        stack_labels(v, items, box[2] + 0.4, 1)
        yt = box[1] - 0.55 * IN * v.sf
        v.title(((box[0] + box[2]) / 2, yt), "PEDESTAL PLAN", "(TYPICAL, BEAM LINE %d SHOWN)" % ped["line"])
        for i, d in enumerate(differ):
            v.text(((box[0] + box[2]) / 2, yt - (4.2 + 1.6 * i) * v.th), d, None, "BOTTOM_CENTER")
        return v

    def pedestal_elevation(self, zone, ped):
        s = self.s
        S = s.S
        b = ped["bb"]
        uu = sorted((s.u(b[0]), s.u(b[3])))
        ztop = max(p[2] for p in ped["top_vertices"])
        num = ped["name"][-2:]
        pbars = [x for x in s.bars if x["family"] == "pedestal" and x["group"].endswith(num + "Bars")]
        lo = min(p[2] for x in pbars for p in x["pts"])
        box = (uu[0] - 0.7, lo - 0.4, uu[1] + 0.7, ztop + 0.5)
        v = View(self.doc, zone, "%s PEDESTAL ELEVATION %d" % (s.key, ped["line"]))
        for rec in S["elev"]:
            if rec["role"] in ("pedestal", "pad", "cap") and rec["vis"]:
                layer, lt = layer_for(rec)
                v.record(rec, layer, lt, box)
        for x in pbars:
            v.pl(proj(x, s.P_elev), "Rebar")
        v.break_line((box[0], box[1]), (box[2], box[1]))
        v.line((ped["u"], box[1]), (ped["u"], box[3] + 0.3), "CL_Minor")
        v.dim((uu[1], s.cap_top), (uu[1], ztop), -(0.55 * IN * v.sf), 90)
        v.dim((uu[0], lo), (uu[0], s.cap_top), 0.55 * IN * v.sf, 90, fdot.ft_in(s.cap_top - lo, 0.25))
        v.leader([(uu[0] + 0.15, ztop), (uu[0] - 0.4, ztop + 0.45)], "¾\" CHAMFER (TYP.)", "right")
        v.leader([(uu[1] - 0.3, s.cap_top), (uu[1] + 0.5, s.cap_top + 0.5)], "CONST. JOINT", "left")
        v.title(((box[0] + box[2]) / 2, box[1] - 0.55 * IN * v.sf), "PEDESTAL ELEVATION", "(BEAM LINE %d)" % ped["line"])
        return v

    # ----------------------------------------------------------- end view
    def end_view(self, zone, letter, z_break=None):
        s = self.s
        S = s.S
        v = View(self.doc, zone, "%s VIEW %s" % (s.key, letter))
        if z_break:
            self._broken(v, S["end_view"]["edges"], z_break)
            ex = extents(S["end_view"]["edges"])
            self._break_lines(v, z_break, ex[0] - 0.4, ex[2] + 0.4)
        else:
            draw_edges(v, S["end_view"]["edges"])
        T = v.xform or (lambda p: p)
        th = v.th
        cs = s.cap_s
        ccl = (cs[0] + cs[1]) / 2
        zc = z_break[3] if z_break else S["pile_clip_z_ft"]
        v.line(T((ccl, zc - 0.3)), (ccl, s.cap_top + 1.4), "CL_Major")
        v.cltext((ccl + 0.25 * th, s.cap_top + 1.45), "PIER & PILES", valign="BOTTOM")
        v.dim((cs[0], s.cap_top), (cs[1], s.cap_top), 0.55 * IN * v.sf + 0.4)
        if s.kind == "PIER":
            ws = (-s.wall_bb[4], -s.wall_bb[1])
            yb = T((0, s.wall_bot))[1]
            v.dim(T((ws[0], s.wall_bot)), T((ws[1], s.wall_bot)), -0.55 * IN * v.sf)
            for b in s.bearings:
                v.line((b["s"], s.cap_top - 0.2), (b["s"], s.cap_top + 0.9), "CL_Minor")
        v.title((ccl, T((0, zc))[1] - 0.75 * IN * v.sf - 0.4), "VIEW %s-%s" % (letter, letter), "(END VIEW)")
        return v
