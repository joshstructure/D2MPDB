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

# levels whose line segments are recorded in ``View.centerlines``
CENTERLINE_LAYERS = ("CL_Major", "CL_Minor", "BaseLineSurveyPGL")

# STYLE_GUIDE B11: the pointer of a pulled-out dimension value starts this many
# text heights off the text box, so it never touches a glyph (the stacked
# fractions of the FDOT font rise above the capital line)
POINTER_GAP_TH = 0.35
# STYLE_GUIDE E8: a view's subtitle (its note in parentheses) stands with its
# capital line this many text heights under the title's underline, in every
# view (the FDOT capital letters are CAP_TH text heights tall)
SUB_GAP_TH = 1.0
CAP_TH = 0.95


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
    # FDOT text styles (CADD Manual 5.12.1.1): FDOT TrueType fonts by file
    # and family, no oblique (the fonts are slanted), height 0 (variable).
    for name, (font, h, w) in fdot.TEXT_STYLES.items():
        file, family, bold = fdot.FONTS[font]
        style = doc.styles.add(name, font=file)
        style.set_extended_font_data(family, italic=False, bold=bold)
        style.dxf.oblique = 0.0
        style.dxf.width = w / h if h else 1.0
    # FDOT Structures Note-Arrow, as in the FDOT-workspace DXF export; the
    # lines and text are ByLayer (Dimension level).
    ds = doc.dimstyles.add(fdot.DIM_STYLE)
    paper = 1.0 / 12.0
    ds.dxf.dimtxsty = fdot.DIM_TEXT_STYLE
    ds.dxf.dimtxt = fdot.style_in(fdot.DIM_TEXT_STYLE) * paper
    ds.dxf.dimtfac = fdot.FRACTION
    ds.dxf.dimasz = fdot.ARROW_IN * paper
    ds.dxf.dimexo = 0.00315
    ds.dxf.dimexe = 0.00315
    ds.dxf.dimgap = 0.00315
    ds.dxf.dimtad = 1
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    ds.dxf.dimlunit = 4      # architectural
    ds.dxf.dimlfac = 12.0    # feet drawing -> inch based architectural text
    ds.dxf.dimzin = 15       # 6" and 4'-0"
    ds.dxf.dimfrac = 1       # diagonal
    ds.dxf.dimtmove = 1
    ds.dxf.dimatfit = 1
    ds.dxf.dimdec = 3
    ds.dxf.dimtofl = 1
    # Dimension text is masked (STYLE_GUIDE B2): an opaque background in the
    # drawing background colour (DIMTFILL 1 -> MTEXT bg_fill 3), so a line
    # passing under the text is blocked out and the text wins.
    ds.dxf.dimtfill = 1
    ds.dxf.dimclrd = 256
    ds.dxf.dimclre = 256
    ds.dxf.dimclrt = 256
    ds.dxf.dimlwd = -1
    ds.dxf.dimlwe = -1
    doc.header["$TEXTSTYLE"] = fdot.TEXT_STYLE
    doc.header["$DIMSTYLE"] = fdot.DIM_STYLE
    doc.header["$CELWEIGHT"] = -1
    return doc


CL_CHAR = fdot.CL_GLYPH   # FDOT font centerline character; leader(cl=True) puts one before the label


ATTACH = {"TOP_LEFT": 1, "TOP_CENTER": 2, "TOP_RIGHT": 3, "MIDDLE_LEFT": 4, "MIDDLE_CENTER": 5,
          "MIDDLE_RIGHT": 6, "BOTTOM_LEFT": 7, "BOTTOM_CENTER": 8, "BOTTOM_RIGHT": 9}


_FRAC = re.compile(r"\{\\H[0-9.]+x;\\S([^;#^/]*)[#^/]([^;]*);\}")


# Advance width of the FDOT font glyphs as a fraction of the capital height
# (measured on the installed FDOT.ttf: advance / cap height 717 em units),
# so the layout estimate of a text with quotes, parentheses and points is
# not a quarter too wide.  Unlisted characters count 0.95 (a wide capital).
_ADV = {"A": 0.904, "B": 0.997, "C": 0.925, "D": 1.084, "E": 1.006, "F": 0.947, "G": 0.902, "H": 1.137,
        "I": 0.639, "J": 0.755, "K": 1.008, "L": 0.782, "M": 1.089, "N": 0.978, "O": 0.898, "P": 0.968,
        "Q": 0.898, "R": 0.969, "S": 0.997, "T": 0.898, "U": 0.946, "V": 0.962, "W": 1.177, "X": 0.989,
        "Y": 0.835, "Z": 1.109, " ": 0.692, "'": 0.297, '"': 0.470, "(": 0.473, ")": 0.473, ".": 0.388,
        ",": 0.431, "~": 0.932, "@": 1.402, "=": 1.103, "-": 0.728, "&": 1.114, "/": 0.718, "%": 1.237,
        ":": 0.427, "#": 1.192, "+": 0.914, "¼": 1.038, "½": 1.137, "¾": 1.205,
        "℄": 0.883, "Δ": 0.940, "°": 0.466, "¡": 0.856, "": 1.0}
_ADV.update({d: 0.886 for d in "0123456789"})
_ADV.update({chr(c): 1.2 for c in range(0x183, 0x18F)})   # eighths and sixteenths glyphs


def text_extent(s, h):
    """Approximate width of single-line text in the FDOT font (per-glyph
    advances, ``_ADV``); an MTEXT stacked fraction counts as one character."""
    plain = _FRAC.sub("", s)
    for code in ("\\S", ";", "#", "{", "}"):
        plain = plain.replace(code, "")
    return h * sum(_ADV.get(c, _ADV.get(c.upper(), 0.95)) for c in plain)


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


def segments_cross(p, q, r, s, tol=1e-6):
    """Point where the segments pq and rs properly cross, else None: they must
    intersect at a point farther than ``tol`` from every one of the four end
    points (parallel, touching and T-junction pairs do not count)."""
    d1 = (q[0] - p[0], q[1] - p[1])
    d2 = (s[0] - r[0], s[1] - r[1])
    l1, l2 = math.hypot(*d1), math.hypot(*d2)
    if l1 < tol or l2 < tol:
        return None
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) <= 1e-9 * l1 * l2:
        return None
    w = (r[0] - p[0], r[1] - p[1])
    t = (w[0] * d2[1] - w[1] * d2[0]) / den
    u = (w[0] * d1[1] - w[1] * d1[0]) / den
    if not (tol / l1 < t < 1.0 - tol / l1 and tol / l2 < u < 1.0 - tol / l2):
        return None
    return (p[0] + t * d1[0], p[1] + t * d1[1])


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


def offset_polyline(pts, d):
    """Points of the polyline ``pts`` offset by ``d`` to its left (negative
    ``d`` offsets to the right), each corner mitred: the offset lines of two
    consecutive segments are intersected.  Where the corner is so sharp that
    the mitre point lies more than 3 |d| from the vertex, the two offset end
    points are used instead (a bevel).  Repeated points are dropped; a
    polyline of fewer than two distinct points offsets to an empty list."""
    p = [tuple(pts[0])] if len(pts) else []
    for q in pts[1:]:
        if math.dist(q, p[-1]) > 1e-9:
            p.append(tuple(q))
    if len(p) < 2:
        return []
    normals = []
    for a, b in zip(p, p[1:]):
        L = math.dist(a, b)
        normals.append((-(b[1] - a[1]) / L, (b[0] - a[0]) / L))
    out = [(p[0][0] + normals[0][0] * d, p[0][1] + normals[0][1] * d)]
    for j in range(1, len(p) - 1):
        n1, n2 = normals[j - 1], normals[j]
        c = n1[0] * n2[0] + n1[1] * n2[1]
        v = p[j]
        a = (v[0] + n1[0] * d, v[1] + n1[1] * d)
        b = (v[0] + n2[0] * d, v[1] + n2[1] * d)
        if 1.0 + c > 1e-9:
            m = (v[0] + d * (n1[0] + n2[0]) / (1.0 + c), v[1] + d * (n1[1] + n2[1]) / (1.0 + c))
            if math.dist(m, v) <= 3.0 * abs(d) + 1e-12:
                if math.dist(m, out[-1]) > 1e-12:
                    out.append(m)
                continue
        out.extend([a, b])
    out.append((p[-1][0] + normals[-1][0] * d, p[-1][1] + normals[-1][1] * d))
    return out


def pointer_segment(mid, c, w, h, rot_deg):
    """Segment from ``mid`` to the nearest edge of a text box (the pull-out
    line of a dimension whose value does not fit, STYLE_GUIDE B1).  The box
    is w x h centred on ``c`` and rotated by ``rot_deg``.  The segment from
    ``mid`` toward the box centre is clipped against the box (rotated into
    the text frame) and ends where it enters the box.  Returns None when
    ``mid`` lies inside the box or coincides with the text location."""
    a = math.radians(rot_deg)
    ca, sa = math.cos(a), math.sin(a)
    dx, dy = mid[0] - c[0], mid[1] - c[1]
    lm = (dx * ca + dy * sa, -dx * sa + dy * ca)   # mid in the text frame
    box = (-w / 2.0, -h / 2.0, w / 2.0, h / 2.0)
    if box[0] < lm[0] < box[2] and box[1] < lm[1] < box[3]:
        return None
    seg = clip_segment(lm, (0.0, 0.0), box)
    if seg is None:
        return None
    e = seg[0]
    entry = (c[0] + e[0] * ca - e[1] * sa, c[1] + e[0] * sa + e[1] * ca)
    if math.dist(entry, mid) < 1e-9:
        return None
    return mid, entry


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
        self.th = self.style_h(fdot.TEXT_STYLE)
        self.local_bbox = [math.inf, math.inf, -math.inf, -math.inf]
        self.boxes = []   # local boxes of every primitive and text, for overlap checks
        self.texts = []   # (local box, string) of every text, for the annotation audit (A1)
        self.segs = []    # (p, q, layer, call) local linework segments, for the annotation audit
        # ``call`` is the id of the drawing call a segment came from: a leader,
        # a fan or a dimension pointer carries one id for all its pieces, any
        # other primitive a fresh id of its own; the audit uses it to tell a
        # leader crossing another leader from a leader's own pieces (A6)
        self._ncall = 0
        self._call = None            # id of the leader / fan / pointer being drawn, else None
        self._pointer_calls = set()  # call ids of dimension pointers (leaders on the Dimension layer)
        # Structured facts for the deterministic annotation checks
        # (``anno_check``), all in the same local frame as ``texts`` / ``segs``
        # (the view's ``xform`` applied):
        #   leaders: one dict per leader / fan / pointer / parallel-leader call:
        #     {"kind": "leader"|"fan"|"pointer"|"parallel", "call": call id,
        #      "pts": main piece polyline (tip first; a pointer text side
        #      first; a fan [knee, end]), "tips": [(x, y), ...],
        #      "knee": (x, y), "end": (x, y) landing end, "text": str,
        #      "align": "left"|"right", "box": text box (x0, y0, x1, y1)}
        #   dims: one dict per ``dim()`` call: {"p1", "p2", "f1", "f2" (the
        #     dimension line's ends), "mid", "text", "box", "pulled": bool,
        #     "angle", "ptr_call": call id of its pointer or None}
        #   breaks: (p, q) segments of break lines and pile break lobes
        #   clips: (x, y, layer) ends where ``_clipped`` cut a segment
        #   centerlines: (p, q, layer) segments on the centerline levels
        #   symbols: (box, label) of circled numbers ("circle N") and section
        #     flags ("flag X") that annotations keep clear of
        #   title_spec: set by ``title()`` (see there)
        #   free_labels: (space box, text box) of a label centred in the open
        #     space given to it (``free_label``; STYLE_GUIDE A25)
        #   dots: (centre, radius) of the end-on bar dots (``dot``), lines a
        #     tip may stand on (A27); arcs: (centre, r, a0, a1, layer) of
        #     ``arc`` (the skew angle's arc carries a tip)
        self.leaders = []
        self.dims = []
        self.breaks = []
        self.small_breaks = []   # the (p, q) segments of ``views.small_break`` (context stubs; A24 exempts them)
        self.clips = []
        self.centerlines = []
        self.symbols = []
        self.title_spec = None
        self.free_labels = []
        self.dots = []
        self.arcs = []

    def style_h(self, style):
        """Model-space text height of an FDOT text style at the view scale."""
        return fdot.TEXT_STYLES[style][1] * self.sf

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

    def _call_id(self):
        """Id stamped on the segments of one drawing call: the leader, fan or
        pointer being drawn (``_begin_call``), else a fresh id."""
        if self._call is not None:
            return self._call
        self._ncall += 1
        return self._ncall

    def _begin_call(self, pointer=False):
        """Start a leader / fan / pointer: every segment drawn until
        ``_end_call`` carries one call id."""
        self._ncall += 1
        self._call = self._ncall
        if pointer:
            self._pointer_calls.add(self._call)

    def _end_call(self):
        self._call = None

    def _seg(self, p, q, layer, call=None):
        if self.xform is not None:
            p, q = self.xform(p), self.xform(q)
        self.segs.append((p, q, layer, call if call is not None else self._call_id()))

    def _X(self, p):
        """A local point in the view's recorded frame (``xform`` applied), the
        frame of ``segs``, ``texts`` and the annotation records."""
        p = self.xform(p) if self.xform is not None else p
        return (p[0], p[1])

    def _note_centerline(self, a, b, layer, length=None):
        """Record a centerline piece for the D3 check: ``length`` is the
        plotted length the dash pattern runs along (a polyline with linetype
        generation on carries its pattern across its vertices, so the whole
        polyline is one piece)."""
        if layer in CENTERLINE_LAYERS:
            pa, pb = self._X(a), self._X(b)
            self.centerlines.append((pa, pb, layer, math.dist(pa, pb) if length is None else length))

    def _note_break(self, pts):
        """Record the segments of a break line / break lobe polyline."""
        q = [self._X(p) for p in pts]
        self.breaks.extend(zip(q, q[1:]))

    def _note_leader(self, kind, call, pts, tips, knee, end, align, tail=None):
        """Record a leader-like call whose text was just drawn (the last entry
        of ``texts``) in ``self.leaders``; points are in local frame."""
        box, label = self.texts[-1] if tail is None else tail
        rec = {"kind": kind, "call": call, "pts": [self._X(p) for p in pts], "tips": [self._X(t) for t in tips],
               "knee": self._X(knee), "end": self._X(end), "text": label, "align": align, "box": box}
        self.leaders.append(rec)
        return rec

    def audit(self):
        """Annotation checks of the view (STYLE_GUIDE A1, A2, A3, A10-A14, B9,
        B11, B12, D3, D12, D13, E5): a thin wrapper around ``anno_check.check_view``, which holds
        every rule and threshold.  Returns [(message, 1)], each message
        starting with its rule id in brackets, e.g. "[A10] acute bend at knee
        (12.31, 43.80) of '4F2'"."""
        from . import anno_check   # (imported here: anno_check imports this module)
        return [(message, 1) for _rule, message in anno_check.check_view(self)]

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
        self._seg(p, q, layer, self._call_id())
        self._note_centerline(p, q, layer)
        return self._add(self.msp.add_line(self.T(p), self.T(q)), layer, ltype)

    def pl(self, pts, layer, bulges=None, closed=False, ltype=None, width=None):
        pts = list(pts)
        if len(pts) < 2:
            return None
        self._track(pts)
        call = self._call_id()
        for a, b in zip(pts, pts[1:] + ([pts[0]] if closed else [])):
            self._seg(a, b, layer, call)
        if layer in CENTERLINE_LAYERS:
            # one piece: the dash pattern runs along the whole polyline (D3)
            self._note_centerline(pts[0], pts[-1], layer,
                                  sum(math.dist(self._X(a), self._X(b)) for a, b in zip(pts, pts[1:])))
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
        if layer in CENTERLINE_LAYERS:
            # linetype generation across the vertices (a dashed polyline
            # otherwise restarts its pattern at every vertex and short pieces
            # plot solid, D3)
            e.dxf.flags |= 128
        return self._add(e, layer, ltype)

    def bar(self, pts, dia_in, layer="Rebar"):
        """A bar not seen end-on, along the centreline ``pts`` (local 2D
        points, no bulges), drawn by scale (SDM 4.3.7.B, STYLE_GUIDE C1): a
        single unbroken line at scales smaller than 1/2" = 1'-0" (the 3/8"
        plan and elevation), and double unbroken lines at the true bar width
        at 1/2" = 1'-0" and larger: the centreline offset by the bar radius to
        each side with mitred corners (``offset_polyline``) and a semicircular
        cap across each end, bulging away from the bar (round bar ends, as the
        FDOT sheets draw them).  Returns the entities drawn."""
        pts = list(pts)
        if len(pts) < 2:
            return []
        if self.sf > fdot.SCALES["1/2"]:
            e = self.pl(pts, layer)
            return [e] if e is not None else []
        r = dia_in / 24.0   # bar radius, feet
        left, right = offset_polyline(pts, r), offset_polyline(pts, -r)
        if len(left) < 2:
            return []
        # one drawing call for the whole bar (both outlines and the caps), so
        # the checks count a bar crossed by a leader once (A14)
        self._ncall += 1
        keep, self._call = self._call, self._ncall
        try:
            out = [self.pl(left, layer), self.pl(right, layer)]
            # direction leaving the bar at each end (the first / last offset
            # piece runs parallel to the bar's first / last piece): backward
            # from the first point, forward past the last
            ends = ((left[0], right[0], (left[0][0] - left[1][0], left[0][1] - left[1][1])),
                    (left[-1], right[-1], (left[-1][0] - left[-2][0], left[-1][1] - left[-2][1])))
            for a, b, away in ends:
                out.append(self._cap(a, b, away, layer))
        finally:
            self._call = keep
        return out

    def _cap(self, a, b, outward, layer):
        """Semicircle from ``a`` to ``b`` (a bar end, ``a`` / ``b`` on the two
        offset lines) bulging toward ``outward`` (any length): a two-point
        polyline with bulge magnitude 1.  A positive bulge arcs to the RIGHT of
        the direction of travel a -> b (counter-clockwise arc), a negative one
        to the left."""
        t = (b[0] - a[0], b[1] - a[1])
        if math.hypot(*outward) < 1e-12:
            return self.line(a, b, layer)   # no direction to bulge toward
        outward_is_left = t[0] * outward[1] - t[1] * outward[0] > 0
        return self.pl([a, b], layer, bulges=[-1.0 if outward_is_left else 1.0])

    def circle(self, c, r, layer, ltype=None):
        self._track([(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)])
        if r > 0.5 * self.th:   # audit: an octagon for circles larger than a dot
            ring = [(c[0] + r * math.cos(i * math.pi / 4), c[1] + r * math.sin(i * math.pi / 4)) for i in range(9)]
            call = self._call_id()
            for a, b in zip(ring, ring[1:]):
                self._seg(a, b, layer, call)
        return self._add(self.msp.add_circle(self.T(c), r), layer, ltype)

    def arc(self, c, r, a0, a1, layer, ltype=None):
        self._track([(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)])
        self.arcs.append((self._X(c), r, a0, a1, layer))
        return self._add(self.msp.add_arc(self.T(c), r, a0, a1), layer, ltype)

    def dot(self, c, r, layer="Rebar"):
        """Filled circle: CIRCLE boundary plus a solid HATCH (SDM 4.3.7.D)."""
        self.dots.append((self._X(c), r))
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
            if box:
                self._note_clips(pts[i], pts[i + 1], a, b, layer)
            if run and math.dist(run[-1], a) < 1e-9:
                run.append(b)
            else:
                if len(run) > 1:
                    self.pl(run, layer, ltype=ltype)
                run = [a, b]
        if len(run) > 1:
            self.pl(run, layer, ltype=ltype)

    def _note_clips(self, p, q, a, b, layer):
        """Record in ``clips`` the ends of the clipped segment ab where the
        original segment pq was CUT at the box (the segment went on beyond
        it); an end that is the original end, even one lying on the box
        edge, is no clip, and neither is a mere touch of the edge."""
        if math.dist(a, b) < 1e-9:
            return
        for cut, orig in ((a, p), (b, q)):
            if math.dist(cut, orig) > 1e-9:
                x, y = self._X(cut)
                self.clips.append((x, y, layer))

    # annotation --------------------------------------------------------
    def _track_box(self, p, w, hgt, ax, ay, rot=0.0, label=None):
        """Track a text box of size w x hgt anchored at fraction (ax, ay) of it;
        with ``label`` the box is also kept for the annotation audit."""
        c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        pts = []
        for fx, fy in ((0, 0), (1, 0), (1, 1), (0, 1)):
            dx, dy = (fx - ax) * w, (fy - ay) * hgt
            pts.append((p[0] + dx * c - dy * s_, p[1] + dx * s_ + dy * c))
        self._track(pts)
        if label is not None:
            qs = [self.xform(q) if self.xform is not None else q for q in pts]
            self.texts.append(((min(q[0] for q in qs), min(q[1] for q in qs),
                                max(q[0] for q in qs), max(q[1] for q in qs)), label))

    def text(self, p, s, h=None, align="BOTTOM_LEFT", rot=0.0, layer="TextStructures", style=None):
        """Single-line text in an FDOT text style (default FDOT Structures,
        height from the style unless ``h`` is given); text with a stacked
        fraction (FDOT_FONT_GLYPHS off) goes to MTEXT."""
        style = style or fdot.TEXT_STYLE
        h = h or self.style_h(style)
        s = fdot.font_text(s)
        if "\\S" in s:
            return self.mtext(p, s, h, ATTACH[align], rot, layer, style=style)
        vert, horiz = align.split("_")
        ax = {"LEFT": 0.0, "CENTER": 0.5, "RIGHT": 1.0}[horiz]
        ay = {"BOTTOM": 0.0, "MIDDLE": 0.5, "TOP": 1.0}[vert]
        self._track_box(p, text_extent(s, h), h, ax, ay, rot, label=s)
        e = self.msp.add_text(s, height=h, rotation=rot, dxfattribs={"style": style})
        e.set_placement(self.T(p), align=TextEntityAlignment[align])
        return self._add(e, layer)

    def mtext(self, p, s, h=None, attach=7, rot=0.0, layer="TextStructures", width=None, style=None):
        """MTEXT with the FDOT line spacing (fdot.LINE_PITCH)."""
        style = style or fdot.TEXT_STYLE
        h = h or self.style_h(style)
        s = fdot.font_text(s)
        lines = s.split("\\P")
        w = width or max(text_extent(x, h) for x in lines)
        hgt = h * (1.0 + fdot.LINE_PITCH * (len(lines) - 1))
        ax = {1: 0, 2: 0.5, 3: 1, 4: 0, 5: 0.5, 6: 1, 7: 0, 8: 0.5, 9: 1}[attach]
        ay = {1: 1, 2: 1, 3: 1, 4: 0.5, 5: 0.5, 6: 0.5, 7: 0, 8: 0, 9: 0}[attach]
        self._track_box(p, w, hgt, ax, ay, rot, label=s)
        e = self.msp.add_mtext(s, dxfattribs={"style": style, "char_height": h, "attachment_point": attach,
                                              "rotation": rot, "line_spacing_factor": fdot.MTEXT_LINE_SPACING})
        if width:
            e.dxf.width = width
        e.dxf.insert = self.T(p)
        return self._add(e, layer)

    def dim(self, p1, p2, offset, angle=0.0, text=None, step=0.125, layer="Dimension", outside=None, level=0,
            horizontal=False, loc=None, row_lines=1, shift=0.0):
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
        text = fdot.font_text(text if text is not None else fdot.ft_in(meas, step))
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
        # Text side (STYLE_GUIDE B8): a vertical dimension column right of the
        # points it measures carries its text on the outer (right) side, so
        # the text never sits between the column and the object.
        side = 1.0
        if abs(angle - 90.0) < 1e-9 and sgn < 0:
            override["dimtad"] = 4
            side = -1.0
        kw = {}
        pulled = None   # text location when the value is pulled out of its space (B1)
        rot = 0.0 if horizontal else angle
        # audit: the extension lines and the dimension line as linework
        f1 = (base[0] + ux * t1, base[1] + uy * t1)
        f2 = (base[0] + ux * t2, base[1] + uy * t2)
        self._seg(p1, f1, layer)
        self._seg(p2, f2, layer)
        self._seg(f1, f2, layer)
        if loc is not None:
            kw["location"] = self.T(loc)
            override["dimtmove"] = 1
            self._track_box(loc, tw, th_box, 0.5, 0.5, rot, label=text)
            pulled = loc
        elif outside is not None:
            arrow = (fdot.ARROW_IN + 0.06) / 12 * self.sf
            along = 0.0
            # Clear gap between the text box's near edge and its own dimension
            # line (review markup 2026-10-17: pulled-out dim text sat on the
            # line): 1.2 text heights for a vertical dimension, whichever
            # way it is pulled out; horizontal: 1.0 below / above the row, and
            # 0.25 beside the line's extension beyond an end.
            vertical = abs(angle - 90.0) < 1e-9
            if outside:
                lo, hi = sorted((t1, t2))
                end = hi if outside > 0 else lo
                along = end - (t1 + t2) / 2 + outside * (arrow + tw / 2)
                gap = (1.2 if vertical else 0.5) * self.th   # B9: never under half a text height from the line
                lift = side * (gap + th_box / 2)
            else:
                # B7: pulled out on the side AWAY from the object (never between
                # its own extension lines): beyond the row's in-place texts when
                # they sit on that side, else just past the dimension line;
                # ``shift`` moves it along the row (values pulled out of
                # neighbouring spaces are staggered along the row, not stacked)
                along = shift
                same_side = (side * sgn) > 0
                # ``row_lines``: the tallest in-place text of the row (lines),
                # which a value pulled out on the same side must clear
                beyond = (0.9 + 1.4 + 1.67 * (max(row_lines, 1) - 1)) * self.th
                clear = (1.2 if vertical else 1.0) * self.th + th_box / 2
                # on the same side the present "beyond" lift stands, unless
                # the value is taller than the row's texts and would not
                # keep its gap (a vertical column is always on the same side)
                lift = sgn * ((max(beyond, clear) if same_side else clear) + 1.6 * level * self.th)
            loc = (mid[0] + ux * along + nx * lift, mid[1] + uy * along + ny * lift)
            kw["location"] = self.T(loc)
            override["dimtmove"] = 1
            self._track_box(loc, tw, th_box, 0.5, 0.5, angle, label=text)
            pulled = loc
        elif len(lines) > 1:
            # A two-line text in place: ezdxf centres the text box on a point
            # (text height / 2 + gap) off the line, so the second line lands
            # on the dimension line.  Give the box an explicit centre instead,
            # 0.2 text heights clear of the line, on the side the text would
            # take.  ezdxf puts dimtad 1 ("above") on the +normal side,
            # n = (-sin a, cos a), for every angle (probed: a vertical
            # dimension has it on the -x side, left of the line, whichever
            # side of the points the line is on) and dimtad 4 on the -normal
            # side, which is ``side``.
            ca, sa = abs(math.cos(math.radians(rot - angle))), abs(math.sin(math.radians(rot - angle)))
            off = side * (0.2 * self.th + (th_box * ca + tw * sa) / 2)
            loc = (mid[0] + nx * off, mid[1] + ny * off)
            kw["location"] = self.T(loc)
            override["dimtmove"] = 1
            self._track_box(loc, tw, th_box, 0.5, 0.5, rot, label=text)
        else:
            self._track_box(mid, tw, th_box, 0.5, 0.0 if side > 0 else 1.0, angle, label=text)
        self._track([p1, p2, base])
        text_box = self.texts[-1][0]   # the value's box, whichever branch placed it (inset 0)
        d = self.msp.add_linear_dim(base=self.T(base), p1=self.T(p1), p2=self.T(p2), angle=angle,
                                    dimstyle=fdot.DIM_STYLE, text=text, override=override,
                                    dxfattribs={"layer": layer}, **kw)
        d.render()
        self.ents.append(d.dimension)
        ptr_call = None
        if pulled is not None:
            # B1: a two-piece pointer (no arrowhead) from the pulled-out text to
            # the dimension line midpoint: a short landing along the text's
            # baseline, then the angled piece, so the reader sees which
            # dimension the value belongs to.
            pts = self.pointer(mid, pulled, tw + 0.4 * self.th, th_box, rot)
            if pts is not None:
                self._begin_call(pointer=True)   # one call id: the audit counts it as a leader (A6)
                ptr_call = self._call
                self.pl(pts, layer)   # tracks its points, ByLayer, into self.ents
                self._end_call()
                # record: text side first; the knee is the bend (the end of
                # the landing), "end" the pointer's first point, 0.35 th off
                # the text box (POINTER_GAP_TH, checked by B11)
                cx = (text_box[0] + text_box[2]) / 2.0
                self._note_leader("pointer", ptr_call, pts, [mid], pts[1] if len(pts) > 2 else pts[0], pts[0],
                                  "left" if cx >= self._X(pts[0])[0] else "right", tail=(text_box, text))
        self.dims.append({"p1": self._X(p1), "p2": self._X(p2), "f1": self._X(f1), "f2": self._X(f2),
                          "mid": self._X(mid), "text": text, "box": text_box, "pulled": pulled is not None,
                          "angle": angle, "ptr_call": ptr_call})
        return meas

    def pointer(self, mid, c, w, h, rot_deg):
        """Points of the pointer from a pulled-out text (box w x h centred at
        ``c``, rotated ``rot_deg``) to ``mid`` (STYLE_GUIDE B1): where the
        dimension lies under (over) the text, one piece square to the
        baseline from the point of the box edge over it; otherwise from the
        middle of the box side facing ``mid`` along the baseline a landing
        of 0.12", then straight to ``mid``.  None when ``mid`` lies inside
        the box.

        STYLE_GUIDE B11: the pointer stops ``POINTER_GAP_TH`` (0.35) text
        heights short of the text so it never touches a glyph; the stacked
        fractions rise above the capital line.  The first point is pulled back
        from the box along the piece's own direction (the box normal for the
        square piece, the baseline for the landing) and the landing length is
        measured from it."""
        a = math.radians(rot_deg)
        dx, dy = math.cos(a), math.sin(a)      # baseline direction
        rel = (mid[0] - c[0], mid[1] - c[1])
        along = rel[0] * dx + rel[1] * dy
        across = -rel[0] * dy + rel[1] * dx
        if abs(along) <= w / 2 and abs(across) <= h / 2:
            return None
        margin = 0.3 * self.th
        gap = POINTER_GAP_TH * self.th
        if abs(along) <= w / 2 - margin:
            # the dimension is under (over) the value: one piece square to
            # the baseline from the box edge facing it (``gap`` off it), over
            # the dimension
            t = 1.0 if across >= 0 else -1.0
            off = h / 2 + gap
            start = (c[0] + dx * along - dy * t * off, c[1] + dy * along + dx * t * off)
            return [start, mid]
        s = 1.0 if along >= 0 else -1.0
        start = (c[0] + dx * s * (w / 2 + gap), c[1] + dy * s * (w / 2 + gap))
        land = 0.12 / 12.0 * self.sf
        if abs(across) < 1e-9 or abs(along) - w / 2 - gap < land:
            # beside its own line, or too near the side for a landing: one piece
            return [start, mid]
        end = (start[0] + dx * s * land, start[1] + dy * s * land)
        return [start, end, mid]

    def _landing(self, pts, align):
        """Leader points ending in a short horizontal landing (FDOT leaders);
        ``align`` 'left' puts the text right of the landing.

        Bend rule (review markup 2026-10-17: leaders bend 90 degrees or
        obtuse, never cut under the text): the angled piece that arrives at
        the knee never runs back toward the text side, which would be an acute
        interior angle with the arrow under the text.  Where the point before
        the knee lies on the text side of it, the knee moves to that point's x
        so the piece is vertical (a 90 degree bend), and the landing end moves
        with it, keeping the landing's length, so the text follows."""
        pts = list(pts)
        if align is None:
            align = "left" if pts[-1][0] >= pts[-2][0] else "right"
        if abs(pts[-1][1] - pts[-2][1]) > 1e-6:
            land = 0.12 / 12 * self.sf
            pts.append((pts[-1][0] + (land if align == "left" else -land), pts[-1][1]))
        if len(pts) >= 3 and abs(pts[-1][1] - pts[-2][1]) <= 1e-6:
            p, knee, end = pts[-3], pts[-2], pts[-1]
            t = 1.0 if align == "left" else -1.0     # text side of the landing end
            if (p[0] - knee[0]) * t > 0.01 * self.sf / 12.0 and abs(p[1] - knee[1]) > 1e-6:
                dx = p[0] - knee[0]
                pts[-2] = (p[0], knee[1])
                pts[-1] = (end[0] + dx, end[1])
        return pts, align

    def _leader_text(self, end, text, align, h, cl=False):
        """Text after a landing; the landing lines up with the first text line.
        ``cl`` puts the FDOT centerline character before the label
        (¡ BEARING); further ones inside the text are written as CL_CHAR
        (¡ CAP & ¡ PILES)."""
        gap = 0.4 * h
        x = end[0] + gap if align == "left" else end[0] - gap
        if cl:
            text = CL_CHAR + " " + text
        if "\\P" in text:
            return self.mtext((x, end[1] + 0.5 * h), text, h, attach=1 if align == "left" else 3)
        return self.text((x, end[1]), text, h, "MIDDLE_LEFT" if align == "left" else "MIDDLE_RIGHT")

    def leader(self, pts, text, align=None, h=None, layer="Leader", cl=False, area=False):
        """Leader (SDM 2.16.E, FDOT sheets): filled arrowhead at pts[0], thin
        line through pts, a short horizontal landing, then the text.
        ``area`` (STYLE_GUIDE A27): a leader naming an AREA (the closure slab
        and coping of the plan, the WWR hatch of the cheek views) ends inside
        it with a small tilde instead of an arrowhead, as the FDOT sample's
        "END BENT BACKWALL" (B1-17); an arrowhead always points at a drawn
        line."""
        h = h or self.th
        pts, align = self._landing(pts, align)   # includes the bend rule
        self._track(pts)
        self._begin_call()
        call = self._call
        if area:
            s = 0.035 / 12 * self.sf
            tip = pts[0]
            self.pl([(tip[0] - s + 2 * s * i / 12.0, tip[1] + 0.45 * s * math.sin(2 * math.pi * i / 12.0))
                     for i in range(13)], layer)
        else:
            self.arrowhead(pts[0], pts[1], layer)
        self.pl(pts, layer)
        self._end_call()
        e = self._leader_text(pts[-1], text, align, h, cl)
        self._note_leader("area" if area else "leader", call, pts, [pts[0]], pts[-2], pts[-1], align)
        return e

    def free_label(self, box, tip, text, h=None, layer="Leader"):
        """A label centred in the open space ``box`` (local frame, (x0, y0,
        x1, y1)) that is its own, with a two-piece leader to ``tip``
        (STYLE_GUIDE A25, markup 2026-10-20: "If the red box here represents
        the available space move the anno more toward the cg of the box.
        That way everything is more clear ... give annotations as much space
        as possible so they are equidistant from each other whilst also trying
        to maintain a kind of row column order").  The text's centre is the
        box's centre; the landing leaves the text on the tip's side and the
        angled piece runs from the landing end to the tip.  Records (box,
        text box) in ``free_labels`` for the check."""
        h = h or self.th
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        w = text_extent(fdot.font_text(text), h)
        side = 1.0 if tip[0] >= cx else -1.0           # the tip's side of the text
        land = 0.12 / 12 * self.sf
        end = (cx + side * (w / 2 + 0.4 * h), cy)      # landing end at the text
        knee = (end[0] + side * land, cy)
        align = "right" if side > 0 else "left"
        self.leader([tip, knee, end], text, align, h, layer)
        self.free_labels.append((tuple(box), self.texts[-1][0]))

    def leader_fan(self, tips, knee, text, align=None, h=None, layer="Leader"):
        """One callout for several bars: an arrow from each tip to a common
        knee, then the landing and the text (FDOT sheets, e.g. 6E15 (EF)).
        The arrows leave the text toward the bars: when the tips lie on the
        text side of the knee, ``align`` is flipped so the text sits on the
        other side, whatever the caller passed."""
        h = h or self.th
        k = self.sf / 12.0
        mean_x = sum(t[0] for t in tips) / len(tips)
        if align is None:
            align = "left" if knee[0] >= mean_x else "right"
        text_side = 1.0 if align == "left" else -1.0
        if (mean_x - knee[0]) * text_side > 0.05 * k:
            align = "right" if align == "left" else "left"
            text_side = -text_side
        # A10: no arrow runs back under the text; the knee sits beyond the
        # last tip on the text side, so every arrow leaves vertically or
        # away from the text (the landing and the text move with it)
        far = max(t[0] * text_side for t in tips)
        if far > knee[0] * text_side - 0.02 * k:
            knee = ((far + 0.08 * k) * text_side, knee[1])
        land = 0.16 / 12 * self.sf
        end = (knee[0] + (land if align == "left" else -land), knee[1])
        self._begin_call()
        call = self._call
        for t in tips:
            self.arrowhead(t, knee, layer)
            self.line(t, knee, layer)
        self.line(knee, end, layer)
        self._end_call()
        self._track(list(tips) + [knee, end])
        e = self._leader_text(end, text, align, h)
        self._note_leader("fan", call, [knee, end], list(tips), knee, end, align)
        return e

    def parallel_leaders(self, tips, x_join, y_text, text, align="left", layer="Leader"):
        """Several lines called out by one label (STYLE_GUIDE A12): from each
        tip ``(x_i, y_i)`` a horizontal piece to ``(x_join, y_i)`` with an
        arrowhead at the tip, one vertical connector at ``x_join`` from the
        lowest to the highest ``y_i`` (and to ``y_text`` when that lies
        outside), one landing of 0.16" from ``(x_join, y_text)`` toward the
        text, and the text after it.  The leaders lie in one plane and touch
        the text at one point only (markup 2026-10-19).  ``align`` "left"
        puts the text to the right of the landing.  All pieces carry one call
        id; recorded as kind "parallel" (its ``pts`` run from the first tip
        over the connector to the landing end).  Returns the text entity."""
        h = self.th
        tips = list(tips)
        land = 0.16 / 12.0 * self.sf
        end = (x_join + (land if align == "left" else -land), y_text)
        ys = [t[1] for t in tips] + [y_text]
        lo, hi = min(ys), max(ys)
        self._begin_call()
        call = self._call
        for t in tips:
            if abs(x_join - t[0]) > 1e-9:
                self.arrowhead(t, (x_join, t[1]), layer)
                self.line(t, (x_join, t[1]), layer)
        if hi - lo > 1e-9:
            self.line((x_join, lo), (x_join, hi), layer)
        self.line((x_join, y_text), end, layer)
        self._end_call()
        self._track(tips + [(x_join, lo), (x_join, hi), end])
        e = self._leader_text(end, text, align, h)
        pts = [tips[0], (x_join, tips[0][1]), (x_join, y_text), end]
        pts = [p for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > 1e-9]
        self._note_leader("parallel", call, pts, tips, (x_join, y_text), end, align)
        return e

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

    def title(self, p, title, sub=None, subject_cx=None):
        """View title centered at p in FDOT Bold (Large), underlined, with the
        subtitle in parentheses below at the normal text size (FDOT sheets).
        The subtitle is the ONE layout of a view's title and its note
        (STYLE_GUIDE E8, markup 2026-10-20 "More space between title underline
        and notes.  Create a consistent layout to be used for all titles and
        notes"): its capital line stands ``SUB_GAP_TH`` text heights under the
        underline, whatever the view; a subtitle is never placed by hand.
        ``subject_cx`` is the x (local feet) the title should be centred on
        (the centre of the thing it names, STYLE_GUIDE E5).  Sets
        ``self.title_spec``: {"x", "y" (the title's anchor p), "title", "sub",
        "subject_cx", "underline_y", "sub_box" (the subtitle's text box, local
        frame, or None), "ents" (the entities drawn), "text_idx" (their
        indices in ``texts``)} plus the index ranges "seg_idx" / "box_idx" of
        the ``segs`` / ``boxes`` entries ``move_title`` shifts."""
        n_ent, n_txt, n_seg, n_box = len(self.ents), len(self.texts), len(self.segs), len(self.boxes)
        h = self.style_h(fdot.TITLE_STYLE)
        self.text(p, title, None, "BOTTOM_CENTER", style=fdot.TITLE_STYLE)
        w = text_extent(title, h) * 1.07   # the bold face runs about 7 % wider
        y_ul = p[1] - 0.22 * h
        self.line((p[0] - w / 2, y_ul), (p[0] + w / 2, y_ul), "TextStructures")
        sub_box = None
        if sub:
            # the subtitle's capital line (0.95 th tall) SUB_GAP_TH under the underline
            self.text((p[0], y_ul - (SUB_GAP_TH + CAP_TH) * self.th), sub, None, "BOTTOM_CENTER")
            sub_box = self.texts[-1][0]
        self.title_spec = {"x": p[0], "y": p[1], "title": title, "sub": sub, "subject_cx": subject_cx,
                           "underline_y": y_ul, "sub_box": sub_box,
                           "ents": self.ents[n_ent:], "text_idx": list(range(n_txt, len(self.texts))),
                           "seg_idx": list(range(n_seg, len(self.segs))),
                           "box_idx": list(range(n_box, len(self.boxes)))}

    def move_title(self, dy):
        """Move the title (``title_spec``) by ``dy`` local feet: its entities
        (already placed or not: model units equal local feet), the title
        entries of ``texts`` and ``segs``, ``title_spec["y"]``, and the view's
        extent (the moved boxes are appended to ``boxes``, the old ones stay)."""
        spec = self.title_spec
        if not spec or not dy:
            return
        for e in spec["ents"]:
            e.translate(0, dy, 0)
        for i in spec["text_idx"]:
            (x0, y0, x1, y1), label = self.texts[i]
            self.texts[i] = ((x0, y0 + dy, x1, y1 + dy), label)
        for i in spec["seg_idx"]:
            p, q, layer, call = self.segs[i]
            self.segs[i] = ((p[0], p[1] + dy), (q[0], q[1] + dy), layer, call)
        spec["y"] += dy
        spec["underline_y"] += dy
        if spec.get("sub_box"):
            x0, y0, x1, y1 = spec["sub_box"]
            spec["sub_box"] = (x0, y0 + dy, x1, y1 + dy)
        spec["dy"] = spec.get("dy", 0.0) + dy    # total shift: the boxes of the first drawing stay in ``boxes``
        b = self.local_bbox
        for i in spec["box_idx"]:
            x0, y0, x1, y1 = self.boxes[i]
            y0, y1 = y0 + spec["dy"], y1 + spec["dy"]
            self.boxes.append((x0, y0, x1, y1))
            b[0], b[1] = min(b[0], x0), min(b[1], y0)
            b[2], b[3] = max(b[2], x1), max(b[3], y1)

    def section_cut(self, p_from, p_to, label, look):
        """FDOT section cut symbol (the "L" flag, STYLE_GUIDE A6) at both ends
        of the cut: a heavy tick from the end of the cut inward along the cut
        and a short heavy base from the same corner toward the viewing
        direction ``look`` (local unit vector), together an L drawn as a
        polyline 0.014" wide (ByLevel weight); a solid wedge OUTSIDE the L
        (beyond the base, away from the letter), thick at the corner and
        tapering in the viewing direction; and the letter (FDOT Structures
        Views_SectionArrow) inside the L beside the tick.  The cut line
        itself is not drawn."""
        dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
        D = math.hypot(dx, dy) or 1.0
        u = (dx / D, dy / D)
        k = self.sf / 12.0
        tick, base, flag, thick = 0.25 * k, 0.09 * k, 0.27 * k, 0.05 * k
        h = self.style_h(fdot.LETTER_STYLE)
        for p, inward in ((p_from, u), (p_to, (-u[0], -u[1]))):
            q = (p[0] + inward[0] * tick, p[1] + inward[1] * tick)
            b = (p[0] + look[0] * base, p[1] + look[1] * base)
            self.pl([q, p, b], "Symbols", width=0.014 * k)
            # the wedge starts at the end of the base (sample sheets), thick
            # there and tapering outward in the viewing direction
            tri = [b, (b[0] + look[0] * flag, b[1] + look[1] * flag),
                   (b[0] - inward[0] * thick, b[1] - inward[1] * thick)]
            self._track(tri)
            s = self.msp.add_solid([self.T(tri[0]), self.T(tri[1]), self.T(tri[2]), self.T(tri[2])])
            self._add(s, "Symbols")
            c = (p[0] + inward[0] * (thick + 0.55 * h) + look[0] * 0.55 * flag,
                 p[1] + inward[1] * (thick + 0.55 * h) + look[1] * 0.55 * flag)
            self.text(c, label, None, "MIDDLE_CENTER", style=fdot.LETTER_STYLE)
            # the flag as a keep-clear box: the L, its wedge and its letter
            qs = [self._X(x) for x in [q, p, b] + tri]
            lx0, ly0, lx1, ly1 = self.texts[-1][0]
            self.symbols.append(((min([x[0] for x in qs] + [lx0]), min([x[1] for x in qs] + [ly0]),
                                  max([x[0] for x in qs] + [lx1]), max([x[1] for x in qs] + [ly1])),
                                 "flag %s" % label))

    def pile_break(self, u, z, width, kind, layer):
        """Curved break at the cut bottom of a pile in elevation: the round
        member break (one full lobe, one lower half lobe) for pipe piles and
        an S-curve for square piles."""
        r = width / 4.0
        e = min(0.3 * r, 0.06 / 12 * self.sf)
        lobe = lambda c, a0, a1: [(c + r * math.cos(math.radians(a)), z + e * math.sin(math.radians(a)))  # noqa: E731
                                  for a in range(a0, a1 + 1, 10)]
        if kind == "pipe":
            lobes = [lobe(u - r, 0, 360), lobe(u + r, 180, 360)]
        else:
            lobes = [lobe(u - r, 180, 360)[::-1] + lobe(u + r, 0, 180)[::-1]]
        for pts in lobes:
            self.pl(pts, layer)
            self._note_break(pts)

    def circled_number(self, c, n):
        """Circled pile/column number (FDOT sheets); the circle is also
        recorded in ``symbols`` ("circle N") for the clearance checks."""
        r = 0.085 / 12 * self.sf
        self.circle(c, r, "Symbols")
        self.text(c, str(n), None, "MIDDLE_CENTER")
        qs = [self._X(p) for p in ((c[0] - r, c[1] - r), (c[0] + r, c[1] + r), (c[0] - r, c[1] + r), (c[0] + r, c[1] - r))]
        self.symbols.append(((min(q[0] for q in qs), min(q[1] for q in qs),
                              max(q[0] for q in qs), max(q[1] for q in qs)), "circle %s" % n))

    def row_label(self, x_end, y, label):
        """Label at the left end of a dimension row, underlined at the
        dimension line level (e.g. BEAM SPACING *)."""
        gap = 0.08 / 12 * self.sf
        w = text_extent(label, self.th)
        self.text((x_end - gap, y + 0.35 * self.th), label, None, "BOTTOM_RIGHT")
        self.line((x_end - gap - w - 0.6 * self.th, y), (x_end - 0.3 * gap, y), "Dimension")

    def legend(self, p, items, h=None):
        """Footnote symbol legend, symbol column then text (FDOT sheets)."""
        h = h or self.th
        for i, (sym, txt) in enumerate(items):
            y = p[1] - i * 2.0 * h
            self.text((p[0], y), sym, h, "BOTTOM_LEFT")
            self.text((p[0] + 0.32 / 12 * self.sf, y), txt, h, "BOTTOM_LEFT")

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
        self._note_break(pts)

    def elev_callout(self, p, text, side=1, rise=None):
        """SDM Fig 2.11.1-2 style elevation callout: tick + leader + EL. text."""
        h = self.th
        rise = rise if rise is not None else 2.5 * h
        tip = p
        knee = (p[0] + side * 0.6 * rise, p[1] + rise)
        end = (knee[0] + side * 1.5 * h, knee[1])
        self._begin_call()
        call = self._call
        self.arrowhead(tip, knee, "Leader")
        self.pl([tip, knee, end], "Leader")
        self._end_call()
        e = self.text((end[0] + side * 0.4 * h, end[1]), text, h, "MIDDLE_LEFT" if side > 0 else "MIDDLE_RIGHT")
        self._note_leader("leader", call, [tip, knee, end], [tip], knee, end, "left" if side > 0 else "right")
        return e

    def stationing_arrow(self, p, direction, length_in=1.7):
        """DIRECTION OF STATIONING: a long thin line ending in a slender solid
        half arrowhead, the text written along the line (FDOT sheets)."""
        k = self.sf / 12.0
        la, wa = 0.3 * k, 0.07 * k
        label = "DIRECTION OF STATIONING"
        # the line is long enough for the text to sit along its plain part,
        # clear of the arrowhead (STYLE_GUIDE A5); the wedge is on the other side
        L = max(length_in / 12 * self.sf, text_extent(label, self.th) + la + 0.3 * k)
        q = (p[0] + direction[0] * L, p[1] + direction[1] * L)
        self.line(p, q, "Symbols")
        ang = math.degrees(math.atan2(direction[1], direction[0]))
        rot = ang if -90 < ang <= 90 else ang + 180
        # text side: the normal that is "up" for the reading direction
        r = math.radians(rot)
        nx, ny = -math.sin(r), math.cos(r)
        b = (q[0] - direction[0] * la, q[1] - direction[1] * la)
        tri = [q, b, (b[0] - nx * wa, b[1] - ny * wa)]
        self._track(tri)
        s = self.msp.add_solid([self.T(tri[0]), self.T(tri[1]), self.T(tri[2]), self.T(tri[2])])
        self._add(s, "Symbols")
        mid = ((p[0] + b[0]) / 2, (p[1] + b[1]) / 2)
        off = 0.45 * self.th
        self.text((mid[0] + nx * off, mid[1] + ny * off), label, None, "BOTTOM_CENTER", rot)
