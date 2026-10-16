"""DXF document setup and drawing primitives (ezdxf).

Model space is drawn at full size (1:1) in international feet.  Each sheet
owns a region of model space laid out exactly like its paper sheet at the
sheet's drawing scale, so one paper-space viewport per sheet shows it.
Annotation (text, arrows, dots, linetype scale) is sized for that scale.
"""
import math

import ezdxf
from ezdxf.enums import TextEntityAlignment

from . import fdot

APPID = "D2MPDB_SUBDWG"


def new_document():
    doc = ezdxf.new("R2010", setup=False)
    doc.units = 2  # $INSUNITS feet (international), as the CAD_AI beam DXF
    doc.header["$MEASUREMENT"] = 0
    doc.header["$LUNITS"] = 4  # architectural display
    doc.header["$LUPREC"] = 3
    doc.header["$INSBASE"] = (0, 0, 0)
    doc.header["$LTSCALE"] = 1.0
    doc.header["$PSLTSCALE"] = 0
    doc.header["$CELTSCALE"] = 1.0
    doc.header["$FILLMODE"] = 1
    doc.header["$LWDISPLAY"] = 1
    doc.appids.add(APPID)
    for name, (desc, pattern) in fdot.LINETYPES.items():
        doc.linetypes.add(name, pattern=pattern, description=desc)
    for name in fdot.LEVELS:
        a = fdot.level_attrs(name)
        layer = doc.layers.add(name, color=a["color"], linetype=a["linetype"], lineweight=a["lineweight"])
        layer.description = a["description"]
        if name == "ClipBorder_dp":
            layer.dxf.plot = 0
    style = doc.styles.add(fdot.TEXT_STYLE, font="romans.shx")
    style.dxf.oblique = fdot.OBLIQUE
    style.dxf.width = 1.0
    ds = doc.dimstyles.add(fdot.DIM_STYLE)
    paper = 1.0 / 12.0
    ds.dxf.dimtxsty = fdot.TEXT_STYLE
    ds.dxf.dimtxt = fdot.TEXT_IN * paper
    ds.dxf.dimasz = fdot.ARROW_IN * paper
    ds.dxf.dimexo = 0.04 * paper
    ds.dxf.dimexe = 0.06 * paper
    ds.dxf.dimgap = 0.03 * paper
    ds.dxf.dimtad = 1
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    ds.dxf.dimlunit = 4      # architectural
    ds.dxf.dimlfac = 12.0    # feet drawing -> inch based architectural text
    ds.dxf.dimzin = 3        # 6" and 4'-0"
    ds.dxf.dimfrac = 0
    ds.dxf.dimdec = 3
    ds.dxf.dimtofl = 1
    ds.dxf.dimclrd = 256
    ds.dxf.dimclre = 256
    ds.dxf.dimclrt = 256
    # Centerline symbol drawn as geometry (a C crossed by an L), one text
    # height tall, so it shows correctly regardless of the receiving font.
    blk = doc.blocks.new(CL_BLOCK)
    blk.add_arc((0.42, 0.5), 0.42, 45, 315, dxfattribs={"layer": "0"})
    blk.add_line((0.42, 1.05), (0.42, 0.0), dxfattribs={"layer": "0"})
    blk.add_line((0.42, 0.0), (0.95, 0.0), dxfattribs={"layer": "0"})
    return doc


CL_BLOCK = "FDOT_CL_SYMBOL"


def text_extent(s, h):
    """Approximate width of single-line text (romans, capitals)."""
    plain = s
    for code in ("\\S", ";", "#"):
        plain = plain.replace(code, "")
    return 0.86 * h * len(plain)


# -------------------------------------------------------------- 2D geometry
def bulge_from_3pts(p0, pm, p1):
    """Bulge of the arc p0 -> p1 passing through pm (2D)."""
    ax, ay = p1[0] - p0[0], p1[1] - p0[1]
    cross = ax * (pm[1] - p0[1]) - ay * (pm[0] - p0[0])
    chord = math.hypot(ax, ay)
    if chord < 1e-12:
        return 0.0
    # sagitta from pm to chord, positive when pm is left of p0->p1 (clockwise arc)
    h = -cross / chord
    return 2.0 * h / chord


def clip_segment(p, q, box):
    """Liang-Barsky clip of segment pq to box (xmin, ymin, xmax, ymax)."""
    x0, y0, x1, y1 = box
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pk) < 1e-15:
            if qk < 0:
                return None
        else:
            t = qk / pk
            if pk < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    if t0 > t1:
        return None
    return (p[0] + t0 * dx, p[1] + t0 * dy), (p[0] + t1 * dx, p[1] + t1 * dy)


def arc_pts(c, r, p0, pm, p1, step_deg=4.0, full=False):
    a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
    if full:
        return [(c[0] + r * math.cos(a0 + 2 * math.pi * i / 90), c[1] + r * math.sin(a0 + 2 * math.pi * i / 90)) for i in range(91)]
    am = math.atan2(pm[1] - c[1], pm[0] - c[0])
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    d1 = (am - a0) % (2 * math.pi)
    d2 = (a1 - a0) % (2 * math.pi)
    sweep = d2 if d1 <= d2 else d2 - 2 * math.pi
    n = max(2, int(abs(math.degrees(sweep)) / step_deg) + 1)
    return [(c[0] + r * math.cos(a0 + sweep * i / n), c[1] + r * math.sin(a0 + sweep * i / n)) for i in range(n + 1)]


def record_paths(rec):
    """Snapshot 2D edge record -> list of ('line', pts) / ('arc', ...) items."""
    t = rec["t"]
    if t == "L":
        return [("pl", [tuple(rec["p"][0]), tuple(rec["p"][1])], [0.0])]
    if t == "P":
        return [("pl", [tuple(p) for p in rec["p"]], [0.0] * (len(rec["p"]) - 1))]
    if t == "A":
        p0, pm, p1 = (tuple(p) for p in rec["p"])
        return [("pl", [p0, p1], [bulge_from_3pts(p0, pm, p1)])]
    if t == "C":
        return [("circle", tuple(rec["c"]), rec["r"])]
    raise ValueError(t)


def discretize_pl(pts, bulges, step_deg=4.0):
    """Polyline with bulges -> plain point list."""
    out = [pts[0]]
    for i in range(len(pts) - 1):
        p, q, b = pts[i], pts[i + 1], bulges[i] if i < len(bulges) else 0.0
        if abs(b) < 1e-9:
            out.append(q)
            continue
        theta = 4 * math.atan(b)  # signed sweep, positive counter-clockwise
        chord = math.dist(p, q)
        r = chord / (2 * math.sin(theta / 2))
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        ux, uy = (q[0] - p[0]) / chord, (q[1] - p[1]) / chord
        d = r * math.cos(theta / 2)  # center left of p->q for a positive bulge
        cx, cy = mx - uy * d, my + ux * d
        R = abs(r)
        a0 = math.atan2(p[1] - cy, p[0] - cx)
        n = max(2, int(abs(math.degrees(theta)) / step_deg) + 1)
        for k in range(1, n + 1):
            a = a0 + theta * k / n
            out.append((cx + R * math.cos(a), cy + R * math.sin(a)))
        out[-1] = q
    return out


class View:
    """A view drawn into model space.

    Local coordinates are feet at full size.  ``place(lx, ly, px, py)`` sets the
    model location so local (lx, ly) lands on paper point (px, py) inches of
    the owning sheet.  ``xform`` optionally maps local points (used for broken
    views); annotation helpers apply it too.
    """

    def __init__(self, doc, zone, name):
        self.doc, self.sheet, self.name = doc, zone, name
        self.msp = doc.modelspace()
        self.sf = zone.sf
        self.ox = self.oy = 0.0
        self.xform = None
        self.ents = []
        self.th = fdot.TEXT_IN / 12.0 * self.sf
        self.local_bbox = [math.inf, math.inf, -math.inf, -math.inf]

    # placement --------------------------------------------------------
    def place(self, lx, ly, px, py):
        mx, my = self.sheet.paper_to_model(px, py)
        dx, dy = mx - lx - self.ox, my - ly - self.oy
        for e in self.ents:
            e.translate(dx, dy, 0)
        self.ox += dx
        self.oy += dy

    def T(self, p):
        if self.xform is not None:
            p = self.xform(p)
        return (p[0] + self.ox, p[1] + self.oy)

    def _track(self, pts):
        for p in pts:
            q = self.xform(p) if self.xform is not None else p
            b = self.local_bbox
            b[0], b[1] = min(b[0], q[0]), min(b[1], q[1])
            b[2], b[3] = max(b[2], q[0]), max(b[3], q[1])

    def _add(self, e, layer, ltype=None):
        e.dxf.layer = layer
        lt = ltype or fdot.level_attrs(layer)["linetype"]
        if ltype:
            e.dxf.linetype = ltype
        if lt in fdot.LTSCALE_PER_SF:
            e.dxf.ltscale = fdot.LTSCALE_PER_SF[lt] * self.sf
        self.ents.append(e)
        return e

    # geometry -----------------------------------------------------------
    def line(self, p, q, layer, ltype=None):
        self._track([p, q])
        return self._add(self.msp.add_line(self.T(p), self.T(q)), layer, ltype)

    def pl(self, pts, layer, bulges=None, closed=False, ltype=None, width=None):
        pts = list(pts)
        if len(pts) < 2:
            return None
        self._track(pts)
        if self.xform is not None and bulges and any(abs(b) > 1e-9 for b in bulges):
            pts = discretize_pl(pts, bulges)
            bulges = None
        data = []
        for i, p in enumerate(pts):
            tp = self.T(p)
            b = bulges[i] if bulges and i < len(bulges) else 0.0
            data.append((tp[0], tp[1], 0, 0, b))
        e = self.msp.add_lwpolyline(data, format="xyseb", close=closed)
        if width:
            e.dxf.const_width = width
        return self._add(e, layer, ltype)

    def circle(self, c, r, layer, ltype=None):
        self._track([(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)])
        return self._add(self.msp.add_circle(self.T(c), r), layer, ltype)

    def arc(self, c, r, a0, a1, layer, ltype=None):
        self._track([(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)])
        return self._add(self.msp.add_arc(self.T(c), r, a0, a1), layer, ltype)

    def dot(self, c, r, layer="Rebar"):
        """Filled circle: CIRCLE boundary plus a solid HATCH (SDM 4.3.7.D)."""
        self.circle(c, r, layer)
        h = self.msp.add_hatch(color=256)
        h.set_solid_fill(color=256)
        tc = self.T(c)
        path = h.paths.add_edge_path()
        path.add_arc(tc, r, 0, 360)
        return self._add(h, layer)

    def hatch_poly(self, pts, layer="Patterning", pattern="ANSI31", scale=None):
        self._track(pts)
        h = self.msp.add_hatch(color=256)
        h.set_pattern_fill(pattern, scale=scale or 0.03 * self.sf, color=256)
        h.paths.add_polyline_path([self.T(p) for p in pts], is_closed=True)
        return self._add(h, layer)

    def record(self, rec, layer, ltype=None, box=None):
        """Draw a snapshot edge record, optionally clipped to a local box."""
        for item in record_paths(rec):
            if item[0] == "circle":
                c, r = item[1], item[2]
                if box is None or (box[0] <= c[0] - r and c[0] + r <= box[2] and box[1] <= c[1] - r and c[1] + r <= box[3]):
                    self.circle(c, r, layer, ltype)
                else:
                    pts = [(c[0] + r * math.cos(2 * math.pi * k / 72), c[1] + r * math.sin(2 * math.pi * k / 72)) for k in range(73)]
                    self._clipped(pts, layer, ltype, box)
                continue
            _, pts, bulges = item
            if box is None or all(box[0] - 1e-9 <= p[0] <= box[2] + 1e-9 and box[1] - 1e-9 <= p[1] <= box[3] + 1e-9 for p in pts) and not any(abs(b) > 1e-9 for b in bulges):
                self.pl(pts, layer, bulges, ltype=ltype)
            else:
                self._clipped(discretize_pl(pts, bulges), layer, ltype, box)

    def _clipped(self, pts, layer, ltype, box):
        run = []
        for i in range(len(pts) - 1):
            seg = clip_segment(pts[i], pts[i + 1], box) if box else (pts[i], pts[i + 1])
            if seg is None:
                if len(run) > 1:
                    self.pl(run, layer, ltype=ltype)
                run = []
                continue
            a, b = seg
            if run and math.dist(run[-1], a) < 1e-9:
                run.append(b)
            else:
                if len(run) > 1:
                    self.pl(run, layer, ltype=ltype)
                run = [a, b]
        if len(run) > 1:
            self.pl(run, layer, ltype=ltype)

    # annotation --------------------------------------------------------
    def _track_box(self, p, w, hgt, ax, ay, rot=0.0):
        """Track a text box of size w x hgt anchored at fraction (ax, ay) of it."""
        c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = []
        for fx, fy in ((0, 0), (1, 0), (1, 1), (0, 1)):
            dx, dy = (fx - ax) * w, (fy - ay) * hgt
            pts.append((p[0] + dx * c - dy * s_, p[1] + dx * s_ + dy * c))
        self._track(pts)

    def text(self, p, s, h=None, align="BOTTOM_LEFT", rot=0.0, layer="TextStructures"):
        h = h or self.th
        vert, horiz = align.split("_")
        ax = {"LEFT": 0.0, "CENTER": 0.5, "RIGHT": 1.0}[horiz]
        ay = {"BOTTOM": 0.0, "MIDDLE": 0.5, "TOP": 1.0}[vert]
        self._track_box(p, text_extent(s, h), h, ax, ay, rot)
        e = self.msp.add_text(s, height=h, rotation=rot, dxfattribs={"style": fdot.TEXT_STYLE, "oblique": fdot.OBLIQUE})
        e.set_placement(self.T(p), align=TextEntityAlignment[align])
        return self._add(e, layer)

    def cltext(self, p, s, h=None, rot=0.0, valign="MIDDLE"):
        """Centerline label: drawn CL symbol then text, left aligned at p."""
        h = h or self.th
        c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        oy = {"BOTTOM": 0.0, "MIDDLE": -0.5, "TOP": -1.0}[valign] * h
        ins = (p[0] - oy * s_, p[1] + oy * c)
        self._track([ins])
        e = self.msp.add_blockref(CL_BLOCK, self.T(ins), dxfattribs={"xscale": h, "yscale": h, "rotation": rot})
        self._add(e, "TextStructures")
        q = (p[0] + 1.25 * h * c, p[1] + 1.25 * h * s_)
        return self.text(q, s, h, valign + "_LEFT", rot)

    def mtext(self, p, s, h=None, attach=7, rot=0.0, layer="TextStructures", width=None):
        h = h or self.th
        lines = s.split("\\P")
        w = width or max(text_extent(x, h) for x in lines)
        hgt = h * (1.0 + 1.67 * (len(lines) - 1))
        ax = {1: 0, 2: 0.5, 3: 1, 4: 0, 5: 0.5, 6: 1, 7: 0, 8: 0.5, 9: 1}[attach]
        ay = {1: 1, 2: 1, 3: 1, 4: 0.5, 5: 0.5, 6: 0.5, 7: 0, 8: 0, 9: 0}[attach]
        self._track_box(p, w, hgt, ax, ay, rot)
        e = self.msp.add_mtext(s, dxfattribs={"style": fdot.TEXT_STYLE, "char_height": h,
                                              "attachment_point": attach, "rotation": rot})
        if width:
            e.dxf.width = width
        e.dxf.insert = self.T(p)
        return self._add(e, layer)

    def dim(self, p1, p2, offset, angle=0.0, text=None, step=0.125, layer="Dimension", outside=None):
        """Linear dimension between local points; ``offset`` is the signed distance
        of the dimension line from p1 measured perpendicular to the dimension
        direction (angle 0 = horizontal, 90 = vertical).  ``outside`` (1, 2, 3)
        lifts the text clear of a tight space at that level, with a leader."""
        a = math.radians(angle)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        base = (p1[0] + nx * offset, p1[1] + ny * offset)
        meas = abs((p2[0] - p1[0]) * ux + (p2[1] - p1[1]) * uy)
        if text is None:
            text = fdot.ft_in(meas, step)
        # dimension line midpoint
        t1 = (p1[0] - base[0]) * ux + (p1[1] - base[1]) * uy
        t2 = (p2[0] - base[0]) * ux + (p2[1] - base[1]) * uy
        mid = (base[0] + ux * (t1 + t2) / 2, base[1] + uy * (t1 + t2) / 2)
        sgn = 1.0 if offset >= 0 else -1.0
        tw = text_extent(text, self.th)
        override = {"dimscale": self.sf}
        kw = {}
        if outside:
            lift = (0.9 + 1.4 * (outside - 1)) * self.th
            loc = (mid[0] + nx * sgn * lift, mid[1] + ny * sgn * lift)
            kw["location"] = self.T(loc)
            override["dimtmove"] = 1
            self._track_box(loc, tw, self.th, 0.5, 0.0, angle)
        else:
            self._track_box(mid, tw, self.th * 1.4, 0.5, 0.0 if sgn > 0 else 1.0, angle)
        self._track([p1, p2, base])
        d = self.msp.add_linear_dim(base=self.T(base), p1=self.T(p1), p2=self.T(p2), angle=angle,
                                    dimstyle=fdot.DIM_STYLE, text=text, override=override,
                                    dxfattribs={"layer": layer}, **kw)
        d.render()
        self.ents.append(d.dimension)
        return meas

    def leader(self, pts, text, align="left", h=None, circle_tip=None, mtext=True, layer="Leader", cl=False):
        """Leader with arrowhead at pts[0]; text at the last point (SDM 2.16.E).

        ``circle_tip`` (radius, local ft) draws a small circle at the tip instead
        of an arrow, used for bars shown end-on.
        """
        h = h or self.th
        self._track(pts)
        tip, nxt = pts[0], pts[1]
        if circle_tip:
            self.circle(tip, circle_tip, layer)
            dx, dy = nxt[0] - tip[0], nxt[1] - tip[1]
            L = math.hypot(dx, dy) or 1.0
            pts = [(tip[0] + dx / L * circle_tip, tip[1] + dy / L * circle_tip)] + list(pts[1:])
        else:
            self.arrowhead(tip, nxt, layer)
        self.pl(pts, layer)
        end = pts[-1]
        gap = 0.4 * h
        if align == "left":
            p, att = (end[0] + gap, end[1]), 4
        else:
            p, att = (end[0] - gap, end[1]), 6
        if cl:
            if align != "left":
                p = (p[0] - text_extent(text, h) - 1.25 * h, p[1])
            return self.cltext(p, text, h)
        if mtext:
            return self.mtext(p, text, h, attach=att)
        return self.text(p, text, h, "MIDDLE_LEFT" if align == "left" else "MIDDLE_RIGHT")

    def arrowhead(self, tip, toward, layer="Leader", size_in=None):
        size = (size_in or fdot.ARROW_IN) / 12.0 * self.sf
        dx, dy = toward[0] - tip[0], toward[1] - tip[1]
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        w = size / 6.0
        b = (tip[0] + ux * size, tip[1] + uy * size)
        pts = [tip, (b[0] - uy * w, b[1] + ux * w), (b[0] + uy * w, b[1] - ux * w)]
        self._track(pts)
        s = self.msp.add_solid([self.T(pts[0]), self.T(pts[1]), self.T(pts[2]), self.T(pts[2])])
        return self._add(s, layer)

    def title(self, p, title, sub=None):
        """Underlined view title centered at p (SDM view title convention)."""
        h = fdot.TITLE_IN / 12.0 * self.sf
        self.text(p, title, h, "BOTTOM_CENTER")
        w = text_extent(title, h)
        self.line((p[0] - w / 2, p[1] - 0.25 * h), (p[0] + w / 2, p[1] - 0.25 * h), "TextStructures")
        if sub:
            self.text((p[0], p[1] - 1.9 * h), sub, self.th, "BOTTOM_CENTER")

    def section_cut(self, p_from, p_to, label, look):
        """Section cut line with arrows; ``look`` is the unit viewing direction (local)."""
        L = 0.45 / 12 * self.sf
        for p in (p_from, p_to):
            self.pl([p, (p[0] + look[0] * L, p[1] + look[1] * L)], "Symbols")
            self.arrowhead((p[0] + look[0] * L, p[1] + look[1] * L), p, "Symbols", 0.12)
        dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
        D = math.hypot(dx, dy) or 1.0
        ext = 0.18 / 12 * self.sf
        self.line(p_from, (p_from[0] - dx / D * ext, p_from[1] - dy / D * ext), "Symbols")
        self.line(p_to, (p_to[0] + dx / D * ext, p_to[1] + dy / D * ext), "Symbols")
        h = 0.11 / 12 * self.sf
        for p in (p_from, p_to):
            q = (p[0] + look[0] * L * 1.6, p[1] + look[1] * L * 1.6)
            self.text(q, label, h, "MIDDLE_CENTER")

    def break_line(self, p, q, layer="Symbols"):
        """Straight break line with a zig-zag at mid length."""
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        z = 0.08 / 12 * self.sf
        m = (p[0] + dx / 2, p[1] + dy / 2)
        pts = [p, (m[0] - ux * z, m[1] - uy * z), (m[0] - ux * z / 2 + nx * z, m[1] - uy * z / 2 + ny * z),
               (m[0] + ux * z / 2 - nx * z, m[1] + uy * z / 2 - ny * z), (m[0] + ux * z, m[1] + uy * z), q]
        self.pl(pts, layer)

    def elev_callout(self, p, text, side=1, rise=None):
        """SDM Fig 2.11.1-2 style elevation callout: tick + leader + EL. text."""
        h = self.th
        rise = rise if rise is not None else 2.5 * h
        tip = p
        knee = (p[0] + side * 0.6 * rise, p[1] + rise)
        end = (knee[0] + side * 1.5 * h, knee[1])
        self.arrowhead(tip, knee, "Leader")
        self.pl([tip, knee, end], "Leader")
        return self.text((end[0] + side * 0.4 * h, end[1]), text, h, "MIDDLE_LEFT" if side > 0 else "MIDDLE_RIGHT")

    def stationing_arrow(self, p, direction, length_in=1.1):
        L = length_in / 12 * self.sf
        q = (p[0] + direction[0] * L, p[1] + direction[1] * L)
        self.line(p, q, "Symbols")
        self.arrowhead(q, p, "Symbols", 0.16)
        ang = math.degrees(math.atan2(direction[1], direction[0]))
        rot = ang if -90 < ang <= 90 else ang + 180
        mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        off = 0.6 * self.th
        self.text((mid[0] - direction[1] * off, mid[1] + direction[0] * off), "DIRECTION OF STATIONING", None,
                  "BOTTOM_CENTER", rot)
