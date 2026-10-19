"""Tiny unit-aware evaluator for the BridgeGeometry_2Beam definitions used by T014.

It reads the journal's own formulas (first definition of each name in the report),
evaluates them with lengths in inches and forces in kip, and formats results the way
the cached `expresult` texts are written ("3.751 ft", "15 ft 2.482 in", "35 ft 8 23/64 in").
It is only a cache-refresh helper: before it is trusted it must reproduce every
current cache it is asked to refresh (see build_components.py, `validate_old_state`).
"""
import math
import re

NBSP = "Â "

# unit: (factor to inch/kip base, (length, force, angle) exponents)
UNITS = {
    "in": (1.0, (1, 0, 0)), "ft": (12.0, (1, 0, 0)),
    "in^2": (1.0, (2, 0, 0)), "ft^2": (144.0, (2, 0, 0)),
    "in^3": (1.0, (3, 0, 0)), "ft^3": (1728.0, (3, 0, 0)),
    "kip": (1.0, (0, 1, 0)), "lbf": (0.001, (0, 1, 0)),
    "pcf": (0.001 / 1728.0, (-3, 1, 0)), "ksf": (1.0 / 144.0, (-2, 1, 0)), "ksi": (1.0, (-2, 1, 0)),
    "deg": (1.0, (0, 0, 1)),
}
NUMBER = r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
UNIT_ALT = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
TOKEN = re.compile(
    r"(?P<ftin>\d+(?:\.\d+)?'\s*(?:" + NUMBER + r'")?)'
    r"|(?P<num>" + NUMBER + r")(?:\s*(?P<unit>" + UNIT_ALT + r")(?![\w^]))?"
    r"|(?P<name>[^\W\d]\w*(?:\.[^\W\d]\w*)?)"
    r"|(?P<op>\*\*|[-+*/^(),])"
    r"|(?P<ws>\s+)")


class Q:
    """A number with (length, force, angle) dimensions; value in inch / kip / degree."""

    __slots__ = ("v", "d")

    def __init__(self, v, d=(0, 0, 0)):
        self.v, self.d = float(v), tuple(d)

    @classmethod
    def of(cls, v, unit=None):
        if unit is None:
            return cls(v)
        f, d = UNITS[unit]
        return cls(v * f, d)

    def _need_same(self, o):
        if self.d != o.d:
            raise ValueError(f"unit mismatch {self.d} vs {o.d}")

    def __add__(self, o):
        o = _q(o); self._need_same(o); return Q(self.v + o.v, self.d)

    __radd__ = __add__

    def __sub__(self, o):
        o = _q(o); self._need_same(o); return Q(self.v - o.v, self.d)

    def __rsub__(self, o):
        return _q(o).__sub__(self)

    def __neg__(self):
        return Q(-self.v, self.d)

    def __mul__(self, o):
        o = _q(o); return Q(self.v * o.v, tuple(a + b for a, b in zip(self.d, o.d)))

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = _q(o); return Q(self.v / o.v, tuple(a - b for a, b in zip(self.d, o.d)))

    def __rtruediv__(self, o):
        return _q(o).__truediv__(self)

    def __pow__(self, p):
        p = _q(p); assert p.d == (0, 0, 0)
        return Q(self.v ** p.v, tuple(a * p.v for a in self.d))

    def number(self):
        assert self.d == (0, 0, 0), f"not dimensionless: {self.d}"
        return self.v


def _q(x):
    return x if isinstance(x, Q) else Q(x)


def Max(*a):
    a = [_q(x) for x in a]
    for x in a[1:]:
        a[0]._need_same(x)
    return max(a, key=lambda x: x.v)


def Min(*a):
    a = [_q(x) for x in a]
    for x in a[1:]:
        a[0]._need_same(x)
    return min(a, key=lambda x: x.v)


def Abs(x):
    return Q(abs(_q(x).v), _q(x).d)


def to_python(formula):
    """Translate a journal expression (no `to` suffix) to a Python expression over Q and V()/X()."""
    formula = re.sub(r"(?<![\w.])(\d+)\s+(\d+)/(\d+)\s*(in|ft)(?![\w^])",
                     lambda m: f"{int(m[1]) + int(m[2]) / int(m[3])!r} {m[4]}", formula)   # "2 9/16 in"
    formula = re.sub(r"(?<![\w.])(\d+)/(\d+)\s*(in|ft)(?![\w^])",
                     lambda m: f"{int(m[1]) / int(m[2])!r} {m[3]}", formula)               # "3/4 in"
    out, prev_unit_q, pos = [], False, 0
    while pos < len(formula):
        m = TOKEN.match(formula, pos)
        if not m:
            raise ValueError(f"cannot tokenize {formula!r} at {pos}: {formula[pos:pos + 20]!r}")
        pos = m.end()
        if m.group("ws"):
            continue
        if m.group("ftin"):
            feet, inch = re.match(r"(\d+(?:\.\d+)?)'\s*(" + NUMBER + r')?"?', m.group("ftin")).groups()
            out.append(f"(Q.of({feet},'ft')+Q.of({inch or 0},'in'))")
            prev_unit_q = False
        elif m.group("num"):
            if m.group("unit"):
                if prev_unit_q:
                    out.append("+")
                out.append(f"Q.of({m.group('num')},{m.group('unit')!r})")
                prev_unit_q = True
            else:
                out.append(f"Q({m.group('num')})")
                prev_unit_q = False
        elif m.group("name"):
            name = m.group("name")
            prev_unit_q = False
            if name in ("Max", "Min", "Abs"):
                out.append(name)
            elif "." in name:
                out.append(f"X({name.split('.')[0]!r},{name.split('.')[1]!r})")
            else:
                out.append(f"V({name!r})")
        else:
            op = m.group("op")
            out.append("**" if op == "^" else op)
            prev_unit_q = False
    return " ".join(out)


def split_to(rhs):
    m = re.search(r"\s+to\s+([A-Za-z^0-9 ]+?)\s*$", rhs)
    return (rhs[:m.start()], m.group(1).strip()) if m else (rhs, None)


def trim(x):
    s = f"{x:.3f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def fmt3(x):
    """3-decimal display: exact values lose trailing zeros ("10.5"), others keep them ("43.910")."""
    x = 0.0 if abs(x) < 5e-10 else x
    return trim(round(x, 3)) if abs(x - round(x, 3)) < 1e-9 else f"{x:.3f}"


def frac64(inches):
    """Inches with a nearest-1/64 fraction ("8 23/64")."""
    n = int(round(inches * 64))
    whole, rem = divmod(n, 64)
    if rem == 0:
        return f"{whole}"
    g = math.gcd(rem, 64)
    return f"{whole} {rem // g}/{64 // g}" if whole else f"{rem // g}/{64 // g}"


def feet_inches(v, fraction=False):
    sign = "-" if v < 0 else ""
    v = abs(v)
    feet = int(v // 12)
    inch = v - 12 * feet
    if round(inch, 3) >= 12.0 and not fraction:
        feet, inch = feet + 1, 0.0
    return f"{sign}{feet} ft {frac64(inch) if fraction else fmt3(inch)} in"


def fmt(q, unit=None, fraction=False):
    """Cached-result text for a Q under a `to <unit>` display (None: length shown as feet and inches)."""
    if unit == "ft in" or (unit is None and q.d == (1, 0, 0)):
        return feet_inches(q.v, fraction=(unit is None and fraction))
    if unit is None:
        return fmt3(q.number())
    f, d = UNITS[unit]
    assert d == q.d, f"display unit {unit} does not match {q.d}"
    return f"{fmt3(q.v / f)} {unit}"


class Report:
    """Evaluate the definitions of one report from {name: formula}; `values` overrides a name."""

    def __init__(self, defs, external, values=None):
        self.defs, self.external, self.values = defs, external, dict(values or {})
        self.memo = {}

    def V(self, name):
        if name in self.values:
            return self.values[name]
        if name in self.memo:
            return self.memo[name]
        if name not in self.defs:
            raise KeyError(f"undefined name {name}")
        self.memo[name] = self.eval_formula(self.defs[name])
        return self.memo[name]

    def X(self, report, name):
        return self.external[(report, name)]

    def eval_formula(self, rhs):
        expr, _ = split_to(rhs)
        env = {"Q": Q, "V": self.V, "X": self.X, "Max": Max, "Min": Min, "Abs": Abs}
        return _q(eval(to_python(expr), {"__builtins__": {}}, env))  # noqa: S307 - journal formulas only

    def text(self, name, fraction=False):
        rhs = self.defs[name]
        _, unit = split_to(rhs)
        return fmt(self.V(name), unit, fraction=fraction and unit is None)
