"""Deterministic annotation checks of a drawing view.

Every placement rule of STYLE_GUIDE.md that can be checked mechanically is a
function here, run over the structured facts the primitives of ``cad.View``
record while they draw (``texts``, ``segs``, ``leaders``, ``dims``, ``breaks``,
``clips``, ``centerlines``, ``symbols``, ``title_spec``).  ``check_view(view)``
returns ``[(rule_id, message)]``; every message starts with its rule id in
brackets and names the text or the local point (feet, view frame) it is
about.  ``cad.View.audit`` is a thin wrapper that returns ``[(message, 1)]``,
which ``build.py`` copies into the manifest (``annotation_overlaps``).

Notation: ``th`` is the view's text height (``view.th``, feet of model
space), ``k`` one paper inch in feet (``view.sf / 12``).  Thresholds are the
module constants named in the last column.

====  =============================  ==========================================  ===============
Rule  Check                          Finding when                                Constant
====  =============================  ==========================================  ===============
A1    text over linework             a linework segment (not Patterning or       INSET_TH,
                                     Symbols) runs through a text box inset      SHORT_TH
                                     0.15 th or ends inside it; a piece
                                     shorter than 0.3 th inside is ignored
A13   leader through a symbol        a leader, pointer or dimension segment      INSET_TH,
                                     runs through the box of a circled number    SHORT_TH
                                     ("circle N") or a section flag ("flag X"),
                                     the same inset and minimum piece as A1
A2    text over text                 two text boxes inset 0.15 th overlap        INSET_TH
A2    text buffer                    the edge-to-edge gap of two text boxes, or  BUFFER_TH
                                     of a text and a symbol box, is below
                                     0.4 th (not the lines of one title, not
                                     two dimension texts, not a symbol's own
                                     letter or number inside its box)
A10   acute bend                     the interior angle at a knee of a leader    BEND_MIN_DEG
                                     or pointer, or between a fan arrow and      (89 degrees)
                                     the fan landing, is below 90 degrees - 1
A10   fan direction                  a fan tip lies on the text side of the      DIRECTION_TOL_K
                                     knee (|dx| under 0.01 k is vertical, ok)
A11   leader crosses leader          two pieces of different leader calls        (proper crossing)
                                     (Leader layer, pointers, fans, parallel
                                     leaders) properly cross
A12   near-parallel arrows           two arrows of a fan leave the knee within   FAN_SPREAD_DEG
                                     5 degrees of each other (parallel
                                     leaders are exempt: they are meant to be)
A14   leader over linework           an arrow piece (not the landing) of a       LEADER_LINES_MAX
                                     leader, fan, pointer or parallel leader
                                     crosses more than 4 drawn objects of the
                                     concrete / bar levels (a double-line bar,
                                     a dot's ring or an outline counts once)
B9    pulled value clearance         the box of a pulled-out dimension value     PULLED_CLEAR_TH
                                     is under 0.5 th from a Dimension segment
                                     other than its own pointer
D3    short centerline               a centerline segment is shorter than one    CL_SHORT_FACTOR
                                     pattern length (``fdot.pattern_length``)
                                     of its level's linetype, so it would plot
                                     without its long and short dash
D12   clipped edge, no break line    a segment end cut at a view window on the   CLIP_BREAK_K,
                                     concrete / context levels lies more than    CLIP_MERGE_K
                                     0.12 k from every break line segment
                                     (cut ends within 0.2 k are one finding)
E5    title centred                  the title anchor is more than 0.05 k from   TITLE_TOL_K
                                     the centre of its subject
====  =============================  ==========================================  ===============

A finding is a candidate, not a verdict: the lead reads the list, fixes what
is wrong and justifies the rest.  The geometry helpers (``angle_deg``,
``point_seg_dist``, ``seg_seg_dist``, ``seg_box_dist``, ``box_gap``) are
public so that the checks can be unit-tested.
"""
import math

from . import cad, fdot

# ---------------------------------------------------------------- thresholds
INSET_TH = 0.15          # text / symbol boxes are inset by this many text heights (A1, A13, A2 overlap)
SHORT_TH = 0.3           # a linework piece shorter than this inside a box is ignored (A1, A13)
BUFFER_TH = 0.4          # minimum edge-to-edge gap between annotations, text heights (A2)
BEND_MIN_DEG = 90.0 - 1.0   # smallest interior angle at a leader knee (A10)
DIRECTION_TOL_K = 0.01   # a fan tip this close (paper inches) to the knee's vertical is not "toward the text" (A10)
FAN_SPREAD_DEG = 5.0     # minimum angle between two arrows of a fan (A12): collinear arrows are the fault
LEADER_LINES_MAX = 4     # an arrow piece may cross at most this many drawing lines (A14)
PULLED_CLEAR_TH = 0.5    # pulled value to dimension line, text heights (B9)
CL_SHORT_FACTOR = 1.0    # a centerline must span this many pattern lengths (D3): one long and one short dash
CLIP_BREAK_K = 0.12      # a clipped end this close (paper inches) to a break line is broken (D12)
CLIP_MERGE_K = 0.2       # clipped ends this close (paper inches) are reported once (D12)
TITLE_TOL_K = 0.05       # title anchor to subject centre, paper inches (E5)

# levels
LINEWORK_SKIP = ("Patterning", "Symbols")         # hatch patterns; symbols drawn around their own letters
LEADER_LAYERS = ("Leader", "Dimension")           # layers whose segments may not run through a symbol (A13)
CONCRETE_PREFIXES = ("SubStrConc", "PileConc", "PileSteel", "WallConc", "WallMSEPanel", "AppSlabConc")
LEADER_LINE_EXACT = ("Rebar", "Rebar2", "BearingPadMisc")   # with the prefixes: the levels of A14
CLIP_EXACT = ("Rebar2",)                                    # with the prefixes: the levels of D12

RULES = ("A1", "A2", "A10", "A11", "A12", "A13", "A14", "B9", "D3", "D12", "E5")


# ------------------------------------------------------------------ geometry
def point_seg_dist(p, a, b):
    """Distance from point p to the segment ab (a point when a == b)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-24:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def seg_seg_dist(a, b, c, d):
    """Distance between the segments ab and cd; 0 when they touch or cross."""
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    if ((o1 > 0 > o2) or (o1 < 0 < o2)) and ((o3 > 0 > o4) or (o3 < 0 < o4)):
        return 0.0
    return min(point_seg_dist(a, c, d), point_seg_dist(b, c, d), point_seg_dist(c, a, b), point_seg_dist(d, a, b))


def seg_box_dist(p, q, box):
    """Distance from the segment pq to the box (x0, y0, x1, y1); 0 when the
    segment touches or enters the box."""
    if cad.clip_segment(p, q, box) is not None:
        return 0.0
    x0, y0, x1, y1 = box
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    ends = []
    for pt in (p, q):
        dx = max(x0 - pt[0], 0.0, pt[0] - x1)
        dy = max(y0 - pt[1], 0.0, pt[1] - y1)
        ends.append(math.hypot(dx, dy))
    return min(ends + [point_seg_dist(c, p, q) for c in corners])


def box_gap(a, b):
    """Edge-to-edge distance of two boxes (x0, y0, x1, y1); 0 when they
    overlap or touch."""
    gx = max(a[0] - b[2], b[0] - a[2], 0.0)
    gy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(gx, gy)


def angle_deg(vertex, a, b):
    """Interior angle in degrees at ``vertex`` between the rays to a and b;
    None when either ray has no length."""
    ux, uy = a[0] - vertex[0], a[1] - vertex[1]
    vx, vy = b[0] - vertex[0], b[1] - vertex[1]
    lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
    if lu < 1e-12 or lv < 1e-12:
        return None
    c = max(-1.0, min(1.0, (ux * vx + uy * vy) / (lu * lv)))
    return math.degrees(math.acos(c))


def _inset(box, m):
    return (box[0] + m, box[1] + m, box[2] - m, box[3] - m)


def _inside(inner, outer, tol=1e-9):
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol
            and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def _strictly_in(pt, box):
    return box[0] < pt[0] < box[2] and box[1] < pt[1] < box[3]


def _runs_through(p, q, box, short):
    """A segment ends inside the (already inset) box or runs through it with
    a piece longer than ``short``."""
    if _strictly_in(p, box) or _strictly_in(q, box):
        return True
    seg = cad.clip_segment(p, q, box)
    return seg is not None and math.dist(seg[0], seg[1]) > short


def _name(label):
    return str(label).replace("\\P", " / ")


def _pt(p):
    return "(%.2f, %.2f)" % (p[0], p[1])


def _leader_calls(view):
    """Call ids that are leaders: those of the records and the dimension
    pointers."""
    return {r["call"] for r in view.leaders} | set(view._pointer_calls)


# -------------------------------------------------------------------- checks
def text_over_linework(view):
    """A1: linework (not Patterning / Symbols) through a text box.  Break
    lines and pile break lobes are drawn on Symbols but are linework here
    (``view.breaks``): the pier wall note once sat on the wall's break line."""
    m, short = INSET_TH * view.th, SHORT_TH * view.th
    segs = [s for s in view.segs if s[2] not in LINEWORK_SKIP]
    segs += [(a, b, "Break", None) for a, b in view.breaks]
    out = []
    for tbox, label in view.texts:
        box = _inset(tbox, m)
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        n = sum(1 for p, q, _layer, _call in segs if _runs_through(p, q, box, short))
        if n:
            out.append(("A1", "[A1] '%s' crossed by %d line(s)" % (_name(label), n)))
    return out


def leader_through_symbol(view):
    """A13: a leader, pointer or dimension segment through the box of a
    circled number or a section flag."""
    m, short = INSET_TH * view.th, SHORT_TH * view.th
    calls = _leader_calls(view)
    pointers = set(view._pointer_calls)
    segs = [s for s in view.segs if s[2] in LEADER_LAYERS or s[3] in calls]
    out = []
    for sbox, label in view.symbols:
        box = _inset(sbox, m)
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        kinds = []
        for p, q, layer, call in segs:
            if _runs_through(p, q, box, short):
                kind = "pointer" if call in pointers else ("dimension line" if layer == "Dimension" else "leader")
                if kind not in kinds:
                    kinds.append(kind)
        if kinds:
            out.append(("A13", "[A13] %s through %s" % ("/".join(kinds), label)))
    return out


def text_clearance(view):
    """A2: text over text (inset boxes overlap), and the buffer: a gap under
    0.4 th between two texts or between a text and a symbol."""
    th = view.th
    m, buf = INSET_TH * th, BUFFER_TH * th
    texts = view.texts
    title_idx = set(view.title_spec["text_idx"]) if view.title_spec else set()
    dim_boxes = {d["box"] for d in view.dims}
    out = []
    for i, (a, la) in enumerate(texts):
        for j in range(i + 1, len(texts)):
            b, lb = texts[j]
            if a[0] - buf >= b[2] or b[0] - buf >= a[2] or a[1] - buf >= b[3] or b[1] - buf >= a[3]:
                continue   # farther apart than the buffer
            if a[0] + m < b[2] - m and b[0] + m < a[2] - m and a[1] + m < b[3] - m and b[1] + m < a[3] - m:
                out.append(("A2", "[A2] '%s' over text '%s'" % (_name(la), _name(lb))))
            elif box_gap(a, b) < buf:
                if i in title_idx and j in title_idx:
                    continue
                if a in dim_boxes and b in dim_boxes:
                    continue
                out.append(("A2", "[A2] '%s' within %g th of '%s'" % (_name(la), BUFFER_TH, _name(lb))))
    for sbox, slabel in view.symbols:
        # a flag's box is the bounding box of an L with its wedge, mostly
        # empty at the corners: it is inset by half a text height for the
        # buffer; a circled number's box is the circle itself and stays
        fb = sbox
        if slabel.startswith("flag"):
            f = 0.5 * th
            fb = (sbox[0] + f, sbox[1] + f, sbox[2] - f, sbox[3] - f)
            if fb[2] <= fb[0] or fb[3] <= fb[1]:
                continue
        for tbox, tlabel in texts:
            if _inside(tbox, sbox):
                continue   # the symbol's own letter or number
            if box_gap(tbox, fb) < buf:
                out.append(("A2", "[A2] '%s' within %g th of '%s'" % (_name(tlabel), BUFFER_TH, slabel)))
    return out


def acute_bends(view):
    """A10: the interior angle at every knee of a leader or pointer, and
    between each arrow and the landing of a fan, is square or obtuse."""
    out = []
    for r in view.leaders:
        pts = r["pts"]
        bad = []
        if r["kind"] in ("leader", "pointer") and len(pts) >= 3:
            for i in range(1, len(pts) - 1):
                a = angle_deg(pts[i], pts[i - 1], pts[i + 1])
                if a is not None and a < BEND_MIN_DEG:
                    bad.append((pts[i], a))
        elif r["kind"] == "fan":
            for t in r["tips"]:
                a = angle_deg(r["knee"], t, r["end"])
                if a is not None and a < BEND_MIN_DEG:
                    bad.append((r["knee"], a))
        if bad:
            at, a = min(bad, key=lambda x: x[1])
            out.append(("A10", "[A10] acute bend at knee %s of '%s' (%.0f deg)" % (_pt(at), _name(r["text"]), a)))
    return out


def fan_direction(view):
    """A10: the arrows of a fan leave the text, toward the bars."""
    tol = DIRECTION_TOL_K * view.sf / 12.0
    out = []
    for r in view.leaders:
        if r["kind"] != "fan":
            continue
        side = 1.0 if r["align"] == "left" else -1.0   # the side of the knee the text is on
        knee = r["knee"]
        if any((t[0] - knee[0]) * side > tol for t in r["tips"]):
            out.append(("A10", "[A10] fan arrow leaves toward its text '%s' at %s" % (_name(r["text"]), _pt(knee))))
    return out


def leader_crossings(view):
    """A11: two pieces of different leader calls properly cross (the Leader
    layer, the dimension pointers, fans and parallel leaders)."""
    names = {r["call"]: _name(r["text"]) for r in view.leaders}
    calls = _leader_calls(view)
    lead = [(p, q, call) for p, q, layer, call in view.segs if layer == "Leader" or call in calls]
    out, seen = [], set()   # overlapping pieces of one fan cross another leader at one place: report it once
    for i, (p, q, call) in enumerate(lead):
        for r, s, other in lead[i + 1:]:
            if call == other:
                continue
            x = cad.segments_cross(p, q, r, s)
            if x is None:
                continue
            key = (min(call, other), max(call, other), round(x[0], 2), round(x[1], 2))
            if key in seen:
                continue
            seen.add(key)
            out.append(("A11", "[A11] leader of '%s' crosses leader of '%s' near %s"
                        % (names.get(call, "(drawn line)"), names.get(other, "(drawn line)"), _pt(x))))
    return out


def fan_spread(view):
    """A12: two arrows of a fan leave the knee within 12 degrees of each
    other (the arrows of parallel leaders are meant to be parallel)."""
    out = []
    for r in view.leaders:
        if r["kind"] != "fan":
            continue
        knee = r["knee"]
        angs = [math.atan2(t[1] - knee[1], t[0] - knee[0]) for t in r["tips"] if math.dist(t, knee) > 1e-9]
        worst = None
        for i in range(len(angs)):
            for j in range(i + 1, len(angs)):
                d = abs(math.degrees(angs[i] - angs[j])) % 360.0
                d = min(d, 360.0 - d)
                if d < FAN_SPREAD_DEG and (worst is None or d < worst):
                    worst = d
        if worst is not None:
            out.append(("A12", "[A12] arrows of '%s' within %g° (%.0f°)"
                        % (_name(r["text"]), FAN_SPREAD_DEG, worst)))
    return out


def _is_drawing_level(layer):
    """The visible concrete / bar levels (hidden "_h" twins are not counted:
    a hidden edge under a leader is already behind another line)."""
    return (layer.startswith(CONCRETE_PREFIXES) or layer in LEADER_LINE_EXACT) and not layer.endswith("_h")


def _line_key(a, b):
    """Key of the infinite line through a and b (unit direction up to sign,
    signed offset), rounded, so collinear segments (the pedestal top and
    the pad bottom on it, the legs of a run of identical bars) count as
    one drawn line."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return (round(a[0], 3), round(a[1], 3), 0.0)
    ux, uy = dx / L, dy / L
    if uy < 0 or (abs(uy) < 1e-9 and ux < 0):
        ux, uy = -ux, -uy
    c = -uy * a[0] + ux * a[1]
    return (round(ux, 3), round(uy, 3), round(c, 3))


def leader_over_linework(view):
    """A14: an arrow piece of a leader (not its landing) that crosses more
    than four drawn lines of the concrete / bar levels (one object once,
    collinear pieces once)."""
    recs = {r["call"]: r for r in view.leaders}
    target = [(s[0], s[1], (min(s[0][0], s[1][0]), min(s[0][1], s[1][1]), max(s[0][0], s[1][0]), max(s[0][1], s[1][1])),
               s[3]) for s in view.segs if _is_drawing_level(s[2])]
    pieces = {}
    for p, q, _layer, call in view.segs:
        if call in recs:
            pieces.setdefault(call, []).append((p, q))
    out = []
    for call, segs in pieces.items():
        r = recs[call]
        knee, end = r["knee"], r["end"]
        arrows = [(p, q) for p, q in segs
                  if not ((math.dist(p, knee) < 1e-9 and math.dist(q, end) < 1e-9)
                          or (math.dist(q, knee) < 1e-9 and math.dist(p, end) < 1e-9))]
        worst = 0
        for p, q in arrows or segs:
            x0, y0, x1, y1 = min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])
            # one drawn object (a double-line bar, a dot's ring, an outline
            # polyline) counts once however many of its segments the piece
            # crosses: distinct drawing calls
            hit, lines = set(), set()
            for a, b, (u0, v0, u1, v1), call in target:
                if u1 < x0 or u0 > x1 or v1 < y0 or v0 > y1:
                    continue
                if cad.segments_cross(p, q, a, b) is not None:
                    key = _line_key(a, b)
                    if key in lines:
                        continue
                    lines.add(key)
                    hit.add(call)
            worst = max(worst, len(hit))
        if worst > LEADER_LINES_MAX:
            out.append(("A14", "[A14] leader of '%s' crosses %d drawing lines" % (_name(r["text"]), worst)))
    return out


def pulled_clearance(view):
    """B9: a pulled-out dimension value keeps 0.5 th from every dimension
    line, its own included, but for its own pointer."""
    clear = PULLED_CLEAR_TH * view.th
    dimsegs = [(p, q, call) for p, q, layer, call in view.segs if layer == "Dimension"]
    out = []
    for d in view.dims:
        if not d["pulled"]:
            continue
        own = d.get("ptr_call")
        box = d["box"]
        for p, q, call in dimsegs:
            if own is not None and call == own:
                continue
            if seg_box_dist(p, q, box) < clear * (1.0 - 1e-6):   # a value placed at the gap exactly passes
                out.append(("B9", "[B9] pulled value '%s' within %g th of a dimension line"
                            % (_name(d["text"]), PULLED_CLEAR_TH)))
                break
    return out


def short_centerlines(view):
    """D3: a centerline segment too short to show its dashes."""
    out = []
    for rec in view.centerlines:
        p, q, layer = rec[0], rec[1], rec[2]
        lt = fdot.level_attrs(layer)["linetype"]
        if lt == "Continuous":
            continue
        need = CL_SHORT_FACTOR * fdot.pattern_length(lt, view.sf)
        L = rec[3] if len(rec) > 3 else math.dist(p, q)
        if L < need:
            mid = ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)
            out.append(("D3", "[D3] centerline at %s too short to show its dashes (%.2f in)"
                        % (_pt(mid), L / view.sf * 12.0)))
    return out


def clipped_without_break(view):
    """D12: a segment end cut at a view window on the concrete / context
    levels with no break line within 0.12 k."""
    k = view.sf / 12.0
    near, merge = CLIP_BREAK_K * k, CLIP_MERGE_K * k
    bare = []
    for x, y, layer in view.clips:
        if not (layer.startswith(CONCRETE_PREFIXES) or layer in CLIP_EXACT):
            continue
        if any(point_seg_dist((x, y), a, b) <= near for a, b in view.breaks):
            continue
        bare.append((x, y, layer))
    groups = []   # [x, y, layers, count]: cut ends within 0.2 k of the group's first are one finding
    for x, y, layer in sorted(bare, key=lambda c: (round(c[0], 3), round(c[1], 3))):
        for g in groups:
            if math.dist((x, y), (g[0], g[1])) < merge:
                g[3] += 1
                if layer not in g[2]:
                    g[2].append(layer)
                break
        else:
            groups.append([x, y, [layer], 1])
    out = []
    for x, y, layers, n in groups:
        msg = "[D12] clipped edge at %s on %s has no break line" % (_pt((x, y)), ", ".join(layers))
        if n > 1:
            msg += " (%d cut ends)" % n
        out.append(("D12", msg))
    return out


def title_centred(view):
    """E5: the title sits on the centre of its subject."""
    spec = view.title_spec
    if not spec or spec.get("subject_cx") is None:
        return []
    k = view.sf / 12.0
    off = abs(spec["x"] - spec["subject_cx"])
    if off > TITLE_TOL_K * k:
        return [("E5", "[E5] title '%s' off the subject centre by %.2f in" % (_name(spec["title"]), off / k))]
    return []


CHECKS = (text_over_linework, leader_through_symbol, text_clearance, acute_bends, fan_direction,
          leader_crossings, fan_spread, leader_over_linework, pulled_clearance, short_centerlines,
          clipped_without_break, title_centred)


def check_view(view):
    """Every annotation check on one view: [(rule_id, message)], the message
    starting with "[rule_id]"."""
    out = []
    for check in CHECKS:
        out.extend(check(view))
    return out
