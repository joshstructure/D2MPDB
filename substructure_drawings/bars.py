"""Reinforcing bar geometry and FDOT SDM 4.3 bar marks.

SDM 4.3.C-E and 4.3.10.B (January 2026): a mark is the bar size followed by
its designation (``6A1`` = #6 bar, designation A1).  Designations are unique
within a component and may repeat between components.  A designation is a
letter alone when one bar type has that application, or a letter plus a
number (starting at 1, none skipped) when several similar bars share the
application.  The letters I, O and Q are never used.

Letters used here (one component = one support):

End bents                         Pier
  A  cap longitudinal bars          A  cap longitudinal bars
  B  cap stirrups / hoops           B  cap stirrups / hoops
  C  cap U-bars between piles       C  cap U-bars between piles
  D  backwall bars                  D  cap end U-bars
  E  cheek wall bars                E  cheek wall bars (D-059)
  F  pedestal U-bars                F  pedestal U-bars

(The pier pedestal bars were 4E1/4E2 before the pier cheek walls of D-059,
2026-10-19; E now names the cheek wall bars of both supports.)

Bars that differ only by length within a backwall vertical series share one
mark with a varying length (bar list shows each length and count), the
usual treatment for a crowned backwall top.
"""
import math
from collections import OrderedDict

from . import fdot

FORBIDDEN = set("IOQ")

FAMILIES = {
    "EB": [
        ("A", "cap_long", ["top", "bottom", "side"]),
        ("B", "cap_trans", ["hoop", "open"]),
        ("C", "cap_added", ["u"]),
        ("D", "backwall", ["vert", "horiz"]),
        ("E", "cheek", ["vert", "horiz"]),
        ("F", "pedestal", ["x", "y"]),
    ],
    "PIER": [
        ("A", "cap_long", ["top", "bottom", "side"]),
        ("B", "cap_trans", ["hoop", "open"]),
        ("C", "cap_added", ["u"]),
        ("D", "cap_end", ["horiz", "vert"]),
        ("E", "cheek", ["vert", "horiz"]),
        ("F", "pedestal", ["x", "y"]),
    ],
}
VARYING = {("EB", "backwall", "vert")}

DESCRIPTIONS = {
    ("cap_long", "top"): "CAP TOP",
    ("cap_long", "bottom"): "CAP BOTTOM",
    ("cap_long", "side"): "CAP SIDE FACES",
    ("cap_trans", "hoop"): "CAP HOOP",
    ("cap_trans", "open"): "CAP STIRRUP AT PILES",
    ("cap_added", "u"): "CAP BETWEEN PILES",
    ("backwall", "vert"): "BACKWALL VERTICAL",
    ("backwall", "horiz"): "BACKWALL HORIZONTAL",
    ("cheek", "vert"): "CHEEK WALL VERTICAL",
    ("cheek", "horiz"): "CHEEK WALL HORIZONTAL",
    ("cap_end", "horiz"): "CAP END, HORIZONTAL",
    ("cap_end", "vert"): "CAP END, VERTICAL",
    ("pedestal", "x"): "PEDESTAL, TRANSVERSE",
    ("pedestal", "y"): "PEDESTAL, LONGITUDINAL",
}


# ------------------------------------------------------------------ geometry
def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return [v / n for v in a] if n > 0 else [0.0, 0.0, 0.0]


def arc_angle(e):
    """Signed sweep (radians, positive) of an arc record from its three points."""
    c = e["c"]
    p0, pm, p1 = e["p"]
    v0, vm, v1 = _sub(p0, c), _sub(pm, c), _sub(p1, c)
    n = _unit(e["n"])
    def ang(a, b):
        return math.atan2(_dot(_cross(a, b), n), _dot(a, b))
    a_m = ang(v0, vm) % (2 * math.pi)
    a_1 = ang(v0, v1) % (2 * math.pi)
    if a_m > a_1:  # traversed the other way round
        a_1 = a_1 - 2 * math.pi
    return abs(a_1) if abs(a_1) > 1e-9 else 2 * math.pi


def arc_points(e, step_deg=5.0):
    c, r = e["c"], e["r"]
    p0, pm, p1 = e["p"]
    n = _unit(e["n"])
    x = _unit(_sub(p0, c))
    y = _cross(n, x)
    def ang(p):
        v = _sub(p, c)
        return math.atan2(_dot(v, y), _dot(v, x))
    am = ang(pm) % (2 * math.pi)
    a1 = ang(p1) % (2 * math.pi)
    if a1 < 1e-9:
        a1 = 2 * math.pi
    sweep = a1 if am <= a1 else a1 - 2 * math.pi
    nseg = max(2, int(math.ceil(abs(math.degrees(sweep)) / step_deg)))
    pts = []
    for i in range(nseg + 1):
        t = sweep * i / nseg
        pts.append([c[k] + r * (math.cos(t) * x[k] + math.sin(t) * y[k]) for k in range(3)])
    return pts


def polyline3(bar, step_deg=5.0):
    pts = []
    for e in bar["edges"]:
        seg = e["p"] if e["t"] in ("L", "P") else arc_points(e, step_deg)
        if pts and _norm(_sub(pts[-1], seg[0])) < 1e-6:
            seg = seg[1:]
        pts.extend(seg)
    return pts


def legs(bar):
    """[('L', length_in) | ('A', angle_deg, radius_in)] along the bar."""
    out = []
    for e in bar["edges"]:
        if e["t"] == "L":
            out.append(("L", _norm(_sub(e["p"][1], e["p"][0])) * 12.0))
        elif e["t"] == "A":
            out.append(("A", math.degrees(arc_angle(e)), e["r"] * 12.0))
        else:
            pts = e["p"]
            out.append(("L", sum(_norm(_sub(pts[i + 1], pts[i])) for i in range(len(pts) - 1)) * 12.0))
    return out


def centerline_length_in(bar):
    total = 0.0
    for kind, *rest in legs(bar):
        if kind == "L":
            total += rest[0]
        else:
            ang, r = rest
            total += math.radians(ang) * r
    return total


def bending_dims(bar):
    """Out-to-out leg dimensions (inches) for the bending diagram.

    Each straight leg is reported out-to-out: its straight length plus, at each
    adjacent 90-degree bend, the centerline bend radius plus half the bar
    diameter.  A leg beyond a non-90-degree bend (the 135-degree hook tails)
    is reported as its straight tail length and flagged as a hook.
    """
    d = bar["dia_in"]
    L = legs(bar)
    dims = []
    for i, item in enumerate(L):
        if item[0] != "L":
            continue
        length = item[1]
        hook = False
        for j in (i - 1, i + 1):
            if 0 <= j < len(L) and L[j][0] == "A":
                ang, r = L[j][1], L[j][2]
                if abs(ang - 90.0) < 1.0:
                    length += r + d / 2.0
                else:
                    hook = True
        dims.append({"len_in": length, "hook": hook})
    return dims


def direction_class(bar):
    """Dominant geometry: ('straight', axis) or ('plane', normal axis)."""
    pts = polyline3(bar, 15.0)
    span = [max(p[k] for p in pts) - min(p[k] for p in pts) for k in range(3)]
    if len(bar["edges"]) == 1 and bar["edges"][0]["t"] == "L":
        return "straight", max(range(3), key=lambda k: span[k])
    return "plane", min(range(3), key=lambda k: span[k])


# ------------------------------------------------------------ classification
def classify(kind, bar):
    """(family, subtype) from the native object names and labels."""
    n, lab, comp = bar["name"], bar["label"].lower(), bar["component"]
    if comp == "cap":
        if "Long" in n:
            if "top" in lab:
                return "cap_long", "top"
            if "bottom" in lab:
                return "cap_long", "bottom"
            return "cap_long", "side"
        if "Trans" in n:
            return "cap_trans", "hoop" if "hoop" in lab else "open"
        if "Added" in n:
            return "cap_added", "u"
        if "End_" in n:
            return "cap_end", "horiz" if "_H" in n else "vert"
    if comp == "backwall":
        return "backwall", "vert" if "V" in n[-3:] else "horiz"
    if comp == "cheek":
        return "cheek", "vert" if "MV" in n else "horiz"
    if comp == "pedestal":
        return "pedestal", "x" if n[-3] == "X" else "y"
    raise ValueError("Unclassified bar " + n)


def size_of(bar):
    return int(round(bar["dia_in"] * 8))


def signature(kind, fam, sub, bar):
    size = size_of(bar)
    if (kind, fam, sub) in VARYING:
        return (size, "varies")
    L = legs(bar)
    if len(L) == 1:
        return (size, ("L", int(math.floor(L[0][1] + 0.5))))
    parts = []
    for item in L:
        if item[0] == "L":
            # to 1/8" first, so a leg modelled exactly on a 1/4" boundary
            # (20 7/8") rounds the same way in every bar of the series
            parts.append(("L", float(fdot.round_in(float(fdot.round_in(item[1], 0.125)), 0.25))))
        else:
            parts.append(("A", int(round(item[1])), float(fdot.round_in(float(fdot.round_in(item[2], 0.03125)), 0.0625))))
    return (size, tuple(parts))


def _pos_key(bar):
    """Order the members of a family so that the marks equal the FreeCAD Mark
    properties (rule C7, D-042).

    Bars are numbered bottom-up: by the lowest z of the bar's edge points,
    then by beam line (line 1, offset -, has the larger model x), then by y.
    Numbering from the bottom does not depend on which way round a support is
    modelled (end bent 2 is built from the far end, so its first edge points
    are at the other end of the cheek wall bars).  Pedestal bars are the
    exception: the pedestals of a pier sit at different elevations, so their
    z is no sequence, and they are numbered by beam line first (x, then y,
    then z), as the model does."""
    zmin = round(min(p[2] for e in bar["edges"] for p in e["p"]), 3)
    p = bar["edges"][0]["p"][0]
    x, y = -round(p[0], 3), round(p[1], 3)
    if bar.get("family") == "pedestal":
        return (x, y, zmin)
    return (zmin, x, y)


def assign_marks(kind, bars):
    """Annotate bars in place with family/subtype/size/des/mark; return the mark table."""
    for b in bars:
        b["family"], b["subtype"] = classify(kind, b)
        b["size"] = size_of(b)
    table = OrderedDict()
    for letter, fam, subs in FAMILIES[kind]:
        assert letter not in FORBIDDEN
        sigs = OrderedDict()
        for sub in subs:
            members = sorted((b for b in bars if b["family"] == fam and b["subtype"] == sub), key=_pos_key)
            for b in members:
                sigs.setdefault((sub, signature(kind, fam, sub, b)), []).append(b)
        if not sigs:
            continue
        single = len(sigs) == 1
        for i, ((sub, sig), members) in enumerate(sigs.items(), start=1):
            des = letter if single else "%s%d" % (letter, i)
            size = members[0]["size"]
            mark = "%d%s" % (size, des)
            lengths = OrderedDict()
            for b in sorted(members, key=lambda b: b["length_in"]):
                lengths.setdefault(int(math.floor(b["length_in"] + 0.5)), []).append(b["name"])
            table[mark] = {
                "mark": mark, "size": size, "des": des, "family": fam, "subtype": sub,
                "description": DESCRIPTIONS[(fam, sub)], "count": len(members),
                "varies": (kind, fam, sub) in VARYING,
                "lengths_in": {str(k): len(v) for k, v in lengths.items()},
                "shape": "STRAIGHT" if len(legs(members[0])) == 1 else None,
                "bend_dims": bending_dims(members[0]),
                "legs": legs(members[0]),
                "members": [b["name"] for b in members],
                "component": members[0]["component"],
            }
            for b in members:
                b["des"], b["mark"] = des, mark
    for b in bars:
        if "mark" not in b:
            raise ValueError("Bar without mark: " + b["name"])
    return table


# FDOT Standard Plans Index 415-001 (FY 2026-27), Bar Bending Details (Steel):
# hook dimension "A or G", out-to-out, in inches, by bar size (reference: the
# 135 degree stirrup hooks of the closed hoops are style 5; the other 90
# degree legs of this model are dimensioned legs, Types 10 and 11, not hooks).
STD_HOOK_90 = {3: 6.0, 4: 8.0, 5: 10.0, 6: 12.0, 7: 14.0, 8: 16.0, 9: 19.0, 10: 22.0, 11: 24.0}
STIRRUP_HOOK_90 = {3: 4.0, 4: 4.5, 5: 6.0, 6: 12.0, 7: 14.0, 8: 16.0}
STIRRUP_HOOK_135 = {3: 4.0, 4: 4.5, 5: 5.5, 6: 8.0, 7: 9.0, 8: 10.5}


def shape_name(entry):
    """Shape of a bar for the bar list (Standard Plans Index 415-001 types).

    STRAIGHT is Type 1.  One 90 degree bend makes an L-BAR (Type 10: B the
    long leg, C the short), two on the same side a U-BAR (Type 11: B the
    base, C and D the legs), whatever the legs' lengths: a 90 degree end
    leg is a dimensioned leg, not a hook (engineer's bar-list review
    2026-10-19: "C should be an 11", "E1 and E4 are type 10s", "E3 is type
    11"; Types 17 and 18 are for hooked straight bars and this model has
    none).  A 135 degree bend is a CLOSED HOOP (Type 4); four 90 degree
    bends make an OPEN STIRRUP (Type 5: closed top, legs, feet turned in at
    the open end); anything else is BENT."""
    L = entry["legs"]
    if len(L) == 1:
        return "STRAIGHT"
    angles = [round(x[1]) for x in L if x[0] == "A"]
    if 135 in angles:
        return "CLOSED HOOP"
    if len(angles) == 4:
        return "OPEN STIRRUP"
    kinds = [x[0] for x in L]
    if angles == [90] and kinds == ["L", "A", "L"]:
        return "L-BAR"
    if len(angles) == 2:
        return "U-BAR"
    return "BENT"
