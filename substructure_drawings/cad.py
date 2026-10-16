"""DXF document setup and drawing primitives (ezdxf).

Model space is drawn at full size (1:1) in international feet.  Each sheet
owns a region of model space laid out exactly like its paper sheet at the
sheet's drawing scale, so one paper-space viewport per sheet shows it.
Annotation (text, arrows, dots, linetype scale) is sized for that scale.
"""
import math
import re

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
    # FDOT structures lettering: single-stroke engineering font slanted 15
    # degrees; titles use the same font plotted with a heavier stroke.
    for name, oblique in ((fdot.TEXT_STYLE, fdot.OBLIQUE), (fdot.TITLE_STYLE, fdot.OBLIQUE)):
        style = doc.styles.add(name, font=fdot.FONT_FILE)
        style.set_extended_font_data(fdot.FONT_FAMILY)
        style.dxf.oblique = oblique
        style.dxf.width = 1.0
    style = doc.styles.add(fdot.SERIF_STYLE, font="times.ttf")
    style.set_extended_font_data("Times New Roman")
    ds = doc.dimstyles.add(fdot.DIM_STYLE)
    paper = 1.0 / 12.0
    ds.dxf.dimtxsty = fdot.TEXT_STYLE
    ds.dxf.dimtxt = fdot.TEXT_IN * paper
    ds.dxf.dimtfac = fdot.FRACTION
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
CL_CHAR = "℄"   # marks a centerline symbol inside a cltext() label


def cl_width(s, h):
    """Width of a cltext() label."""
    return sum(1.25 * h + 0.85 * text_extent(p.strip(), h) + 0.35 * h for p in s.split(CL_CHAR))


ATTACH = {"TOP_LEFT": 1, "TOP_CENTER": 2, "TOP_RIGHT": 3, "MIDDLE_LEFT": 4, "MIDDLE_CENTER": 5,
          "MIDDLE_RIGHT": 6, "BOTTOM_LEFT": 7, "BOTTOM_CENTER": 8, "BOTTOM_RIGHT": 9}


_FRAC = re.compile(r"\{\\H[0-9.]+x;\\S([^;#^/]*)[#^/]([^;]*);\}")


def text_extent(s, h):
    """Approximate width of single-line text (engineering capitals, wide
    spacing); a stacked fraction counts as about one character."""
    plain = _FRAC.sub("@", s)
    for code in ("\\S", ";", "#", "{", "}"):
        plain = plain.replace(code, "")
    return 0.86 * h * len(plain)


def boxes_cross(mine, theirs):
    """Number of crossing or overlapping pairs between two box lists (paper
    inches); boxes that only touch do not count."""
    if not mine or not theirs:
        return 0
    bb = lambda bs: (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))  # noqa: E731
    A, B = bb(mine), bb(theirs)
    near = lambda b, o: b[0] <= o[2] and o[0] <= b[2] and b[1] <= o[3] and o[1] <= b[3]  # noqa: E731
    mine = [b for b in mine if near(b, B)]
    theirs = [b for b in theirs if near(b, A)]
    n = 0
    for p in mine:
        for q in theirs:
            ox = min(p[2], q[2]) - max(p[0], q[0])
            oy = min(p[3], q[3]) - max(p[1], q[1])
            if ox >= 0 and oy >= 0 and (ox > 0.01 or oy > 0.01):
                n += 1
    return n


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
        self.boxes = []   # local boxes of every primitive and text, for overlap checks

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
        qs = [self.xform(p) if self.xform is not None else p for p in pts]
        b = self.local_bbox
        for q in qs:
            b[0], b[1] = min(b[0], q[0]), min(b[1], q[1])
            b[2], b[3] = max(b[2], q[0]), max(b[3], q[1])
        if qs:
            self.boxes.append((min(q[0] for q in qs), min(q[1] for q in qs),
                               max(q[0] for q in qs), max(q[1] for q in qs)))

    def paper_boxes(self):
        """Paper-inch boxes of the view's primitives and texts (large area
        boxes, i.e. closed outlines and hatches, are left out)."""
        k = 12.0 / self.sf
        mo = self.sheet.model_origin
        out = []
        for x0, y0, x1, y1 in self.boxes:
            a = ((x0 + self.ox - mo[0]) * k, (y0 + self.oy - mo[1]) * k)
            c = ((x1 + self.ox - mo[0]) * k, (y1 + self.oy - mo[1]) * k)
            if (c[0] - a[0]) * (c[1] - a[1]) <= 1.0:
                out.append((a[0], a[1], c[0], c[1]))
        return out

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

    def text(self, p, s, h=None, align="BOTTOM_LEFT", rot=0.0, layer="TextStructures", style=None, lw=None):
        """Single-line text; text with a stacked fraction goes to MTEXT."""
        h = h or self.th
        if "\\S" in s:
            return self.mtext(p, s, h, ATTACH[align], rot, layer)
        vert, horiz = align.split("_")
        ax = {"LEFT": 0.0, "CENTER": 0.5, "RIGHT": 1.0}[horiz]
        ay = {"BOTTOM": 0.0, "MIDDLE": 0.5, "TOP": 1.0}[vert]
        self._track_box(p, text_extent(s, h), h, ax, ay, rot)
        e = self.msp.add_text(s, height=h, rotation=rot,
                              dxfattribs={"style": style or fdot.TEXT_STYLE, "oblique": fdot.OBLIQUE})
        e.set_placement(self.T(p), align=TextEntityAlignment[align])
        if lw:
            e.dxf.lineweight = lw
        return self._add(e, layer)

    def cltext(self, p, s, h=None, rot=0.0, valign="MIDDLE"):
        """Centerline label, left aligned at p: drawn CL symbol then text.
        Further CL symbols inside the text are written as CL_CHAR
        (e.g. 'CAP & ℄ PILES')."""
        h = h or self.th
        c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        oy = {"BOTTOM": 0.0, "MIDDLE": -0.5, "TOP": -1.0}[valign] * h
        x, e = 0.0, None
        for part in s.split(CL_CHAR):
            ins = (p[0] + x * c - oy * s_, p[1] + x * s_ + oy * c)
            self._track([ins])
            blk = self.msp.add_blockref(CL_BLOCK, self.T(ins), dxfattribs={"xscale": h, "yscale": h, "rotation": rot})
            self._add(blk, "TextStructures")
            x += 1.25 * h
            part = part.strip()
            if part:
                e = self.text((p[0] + x * c, p[1] + x * s_), part, h, valign + "_LEFT", rot)
                x += 0.85 * text_extent(part, h) + 0.35 * h   # text_extent errs wide for safety
        return e

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

    def dim(self, p1, p2, offset, angle=0.0, text=None, step=0.125, layer="Dimension", outside=None, level=0,
            horizontal=False, loc=None):
        """Linear dimension between local points; ``offset`` is the signed distance
        of the dimension line from p1 measured perpendicular to the dimension
        direction (angle 0 = horizontal, 90 = vertical).

        ``outside`` places text that does not fit its space beside it with a
        short leader (FDOT practice, never a second row): -1 beyond the low
        end, +1 beyond the high end (along the dimension direction), 0 just
        below the line under the middle (``level`` staggers several such
        values).  ``horizontal`` keeps the text horizontal; ``loc`` gives
        the text position (local) explicitly."""
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
        lines = text.split("\\P")
        tw = max(text_extent(x, self.th) for x in lines)
        th_box = self.th * (1.4 + 1.67 * (len(lines) - 1))
        override = {"dimscale": self.sf}
        if horizontal:
            override["dimtih"] = 1
            override["dimtoh"] = 1
        kw = {}
        if loc is not None:
            kw["location"] = self.T(loc)
            override["dimtmove"] = 1
            self._track_box(loc, tw, th_box, 0.5, 0.5, 0.0 if horizontal else angle)
        elif outside is not None:
            arrow = (fdot.ARROW_IN + 0.06) / 12 * self.sf
            along = 0.0
            if outside:
                lo, hi = sorted((t1, t2))
                end = hi if outside > 0 else lo
                along = end - (t1 + t2) / 2 + outside * (arrow + tw / 2)
                lift = 0.9 * self.th
            else:
                # below the line, opposite the side where the text sits (+n)
                lift = -(1.5 + 1.6 * level) * self.th * sgn
            loc = (mid[0] + ux * along + nx * sgn * lift, mid[1] + uy * along + ny * sgn * lift)
            kw["location"] = self.T(loc)
            override["dimtmove"] = 1
            self._track_box(loc, tw, th_box, 0.5, 0.5, angle)
        else:
            self._track_box(mid, tw, th_box, 0.5, 0.0 if sgn > 0 else 1.0, angle)
        self._track([p1, p2, base])
        d = self.msp.add_linear_dim(base=self.T(base), p1=self.T(p1), p2=self.T(p2), angle=angle,
                                    dimstyle=fdot.DIM_STYLE, text=text, override=override,
                                    dxfattribs={"layer": layer}, **kw)
        d.render()
        self.ents.append(d.dimension)
        return meas

    def _landing(self, pts, align):
        """Leader points ending in a short horizontal landing (FDOT leaders);
        ``align`` 'left' puts the text right of the landing."""
        pts = list(pts)
        if align is None:
            align = "left" if pts[-1][0] >= pts[-2][0] else "right"
        if abs(pts[-1][1] - pts[-2][1]) > 1e-6:
            land = 0.12 / 12 * self.sf
            pts.append((pts[-1][0] + (land if align == "left" else -land), pts[-1][1]))
        return pts, align

    def _leader_text(self, end, text, align, h, cl=False):
        """Text after a landing; the landing lines up with the first text line."""
        gap = 0.4 * h
        x = end[0] + gap if align == "left" else end[0] - gap
        if cl:
            if align != "left":
                x -= cl_width(text, h)
            return self.cltext((x, end[1]), text, h)
        if "\\P" in text:
            return self.mtext((x, end[1] + 0.5 * h), text, h, attach=1 if align == "left" else 3)
        return self.text((x, end[1]), text, h, "MIDDLE_LEFT" if align == "left" else "MIDDLE_RIGHT")

    def leader(self, pts, text, align=None, h=None, layer="Leader", cl=False):
        """Leader (SDM 2.16.E, FDOT sheets): filled arrowhead at pts[0], thin
        line through pts, a short horizontal landing, then the text."""
        h = h or self.th
        pts, align = self._landing(pts, align)
        self._track(pts)
        self.arrowhead(pts[0], pts[1], layer)
        self.pl(pts, layer)
        return self._leader_text(pts[-1], text, align, h, cl)

    def leader_fan(self, tips, knee, text, align=None, h=None, layer="Leader"):
        """One callout for several bars: an arrow from each tip to a common
        knee, then the landing and the text (FDOT sheets, e.g. 6E15 (EF))."""
        h = h or self.th
        if align is None:
            align = "left" if knee[0] >= sum(t[0] for t in tips) / len(tips) else "right"
        land = 0.16 / 12 * self.sf
        end = (knee[0] + (land if align == "left" else -land), knee[1])
        for t in tips:
            self.arrowhead(t, knee, layer)
            self.line(t, knee, layer)
        self.line(knee, end, layer)
        self._track(list(tips) + [knee, end])
        return self._leader_text(end, text, align, h)

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
        """View title centered at p: heavier, underlined, with the subtitle in
        parentheses below at the normal text size (FDOT sheets)."""
        h = fdot.TITLE_IN / 12.0 * self.sf
        self.text(p, title, h, "BOTTOM_CENTER", style=fdot.TITLE_STYLE, lw=fdot.TITLE_LW)
        w = text_extent(title, h)
        ln = self.line((p[0] - w / 2, p[1] - 0.22 * h), (p[0] + w / 2, p[1] - 0.22 * h), "TextStructures")
        ln.dxf.lineweight = fdot.TITLE_LW
        if sub:
            self.text((p[0], p[1] - 0.4 * h - 1.45 * self.th), sub, self.th, "BOTTOM_CENTER")

    def section_cut(self, p_from, p_to, label, look):
        """FDOT section cut symbol at both ends of the cut: a short heavy line
        along the cut, a solid triangular flag at its outer end pointing in
        the viewing direction ``look`` (local unit vector), and the letter
        beside the line under the flag.  The cut line itself is not drawn."""
        dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
        D = math.hypot(dx, dy) or 1.0
        u = (dx / D, dy / D)
        k = self.sf / 12.0
        tick, flag, thick = 0.25 * k, 0.27 * k, 0.05 * k
        h = 0.12 * k
        for p, inward in ((p_from, u), (p_to, (-u[0], -u[1]))):
            q = (p[0] + inward[0] * tick, p[1] + inward[1] * tick)
            self.line(p, q, "Symbols").dxf.lineweight = fdot.TITLE_LW
            tri = [p, (p[0] + look[0] * flag, p[1] + look[1] * flag),
                   (p[0] + inward[0] * thick, p[1] + inward[1] * thick)]
            self._track(tri)
            s = self.msp.add_solid([self.T(tri[0]), self.T(tri[1]), self.T(tri[2]), self.T(tri[2])])
            self._add(s, "Symbols")
            c = (p[0] + inward[0] * (thick + 0.55 * h) + look[0] * 0.55 * flag,
                 p[1] + inward[1] * (thick + 0.55 * h) + look[1] * 0.55 * flag)
            self.text(c, label, h, "MIDDLE_CENTER")

    def pile_break(self, u, z, width, kind, layer):
        """Curved break at the cut bottom of a pile in elevation: the round
        member break (one full lobe, one lower half lobe) for pipe piles and
        an S-curve for square piles."""
        r = width / 4.0
        e = min(0.3 * r, 0.06 / 12 * self.sf)
        lobe = lambda c, a0, a1: [(c + r * math.cos(math.radians(a)), z + e * math.sin(math.radians(a)))  # noqa: E731
                                  for a in range(a0, a1 + 1, 10)]
        if kind == "pipe":
            self.pl(lobe(u - r, 0, 360), layer)
            self.pl(lobe(u + r, 180, 360), layer)
        else:
            self.pl(lobe(u - r, 180, 360)[::-1] + lobe(u + r, 0, 180)[::-1], layer)

    def circled_number(self, c, n):
        """Circled pile/column number (FDOT sheets)."""
        self.circle(c, 0.085 / 12 * self.sf, "Symbols")
        self.text(c, str(n), None, "MIDDLE_CENTER")

    def row_label(self, x_end, y, label):
        """Label at the left end of a dimension row, underlined at the
        dimension line level (e.g. BEAM SPACING *)."""
        gap = 0.08 / 12 * self.sf
        w = text_extent(label, self.th)
        self.text((x_end - gap, y + 0.35 * self.th), label, None, "BOTTOM_RIGHT")
        self.line((x_end - gap - w - 0.6 * self.th, y), (x_end - 0.3 * gap, y), "Dimension")

    def legend(self, p, items, h=None):
        """Footnote symbol legend, symbol column then text (FDOT sheets);
        a CL_CHAR in the text is drawn as the centerline symbol."""
        h = h or self.th
        for i, (sym, txt) in enumerate(items):
            y = p[1] - i * 2.0 * h
            self.text((p[0], y), sym, h, "BOTTOM_LEFT")
            x = p[0] + 0.32 / 12 * self.sf
            if CL_CHAR in txt:
                head, tail = txt.split(CL_CHAR, 1)
                self.text((x, y), head, h, "BOTTOM_LEFT")
                self.cltext((x + text_extent(head, h), y), tail, h, valign="BOTTOM")
            else:
                self.text((x, y), txt, h, "BOTTOM_LEFT")

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

    def stationing_arrow(self, p, direction, length_in=1.7):
        """DIRECTION OF STATIONING: a long thin line ending in a slender solid
        half arrowhead, the text written along the line (FDOT sheets)."""
        L = length_in / 12 * self.sf
        q = (p[0] + direction[0] * L, p[1] + direction[1] * L)
        self.line(p, q, "Symbols")
        ang = math.degrees(math.atan2(direction[1], direction[0]))
        rot = ang if -90 < ang <= 90 else ang + 180
        # text side: the normal that is "up" for the reading direction
        r = math.radians(rot)
        nx, ny = -math.sin(r), math.cos(r)
        k = self.sf / 12.0
        la, wa = 0.3 * k, 0.07 * k
        b = (q[0] - direction[0] * la, q[1] - direction[1] * la)
        tri = [q, b, (b[0] + nx * wa, b[1] + ny * wa)]
        self._track(tri)
        s = self.msp.add_solid([self.T(tri[0]), self.T(tri[1]), self.T(tri[2]), self.T(tri[2])])
        self._add(s, "Symbols")
        mid = ((p[0] + b[0]) / 2, (p[1] + b[1]) / 2)
        off = 0.45 * self.th
        self.text((mid[0] + nx * off, mid[1] + ny * off), "DIRECTION OF STATIONING", None, "BOTTOM_CENTER", rot)
