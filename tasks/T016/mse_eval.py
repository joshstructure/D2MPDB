"""Unit-aware evaluator for the MSEWallExclusion definitions (T016 cache refresh).

The module's formulas are plain arithmetic over lengths, angles, numbers and strings with
Abs/Min/Max/Floor/Sin/Cos/If/And and comparisons. Blockpad displays a length in the unit the
expression carries: inches when every operand is in inches, feet when feet only, and feet-and-
inches once feet and inches are combined ("3 ft 1.182 in"). This evaluator carries that display
tag with every value and formats cached results the way the journal stores them. It is only a
cache-refresh helper: build_components.py requires it to reproduce every current cached result
and table cell of the module before any refreshed value is written.
"""
import math
import re

NBSP = " "
NUMBER = r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
TOKEN = re.compile(
    r"(?P<str>\"[^\"]*\")"
    r"|(?P<num>" + NUMBER + r")(?:\s*(?P<unit>in|ft|deg)(?![\w^]))?"
    r"|(?P<name>[^\W\d][\w]*(?:\.[^\W\d]\w*)?)"
    r"|(?P<op>==|<=|>=|<|>|[-+*/^(),])"
    r"|(?P<ws>\s+)")
TO_IN = {"in": 1.0, "ft": 12.0}


class Q:
    """A length (inches), angle (degrees), number or string with a display tag."""

    __slots__ = ("v", "kind", "tag")

    def __init__(self, v, kind="num", tag=None):
        self.v, self.kind, self.tag = v, kind, tag      # kind: num | len | ang | str ; tag: in | ft | ftin

    @staticmethod
    def length(v, unit):
        return Q(v * TO_IN[unit], "len", unit)

    def _len_tag(self, o):
        if self.tag == o.tag:
            return self.tag
        return "ftin"

    def __add__(self, o):
        if self.kind == "len" and o.kind == "len":
            return Q(self.v + o.v, "len", self._len_tag(o))
        assert self.kind == o.kind == "num", f"add {self.kind} + {o.kind}"
        return Q(self.v + o.v)

    def __sub__(self, o):
        if self.kind == "len" and o.kind == "len":
            return Q(self.v - o.v, "len", self._len_tag(o))
        assert self.kind == o.kind == "num", f"sub {self.kind} - {o.kind}"
        return Q(self.v - o.v)

    def __neg__(self):
        return Q(-self.v, self.kind, self.tag)

    def __mul__(self, o):
        if self.kind == "num" and o.kind == "num":
            return Q(self.v * o.v)
        if self.kind == "num" and o.kind in ("len", "ang"):
            return Q(self.v * o.v, o.kind, o.tag)
        if o.kind == "num" and self.kind in ("len", "ang"):
            return Q(self.v * o.v, self.kind, self.tag)
        raise ValueError(f"mul {self.kind} * {o.kind}")

    def __truediv__(self, o):
        if o.kind == "num":
            return Q(self.v / o.v, self.kind, self.tag)
        if self.kind == o.kind == "len":
            return Q(self.v / o.v)
        raise ValueError(f"div {self.kind} / {o.kind}")

    def _cmp(self, o):
        assert self.kind == o.kind, f"compare {self.kind} with {o.kind}"
        return self.v, o.v

    def __lt__(self, o): a, b = self._cmp(o); return a < b
    def __le__(self, o): a, b = self._cmp(o); return a <= b
    def __gt__(self, o): a, b = self._cmp(o); return a > b
    def __ge__(self, o): a, b = self._cmp(o); return a >= b

    def __eq__(self, o):
        if isinstance(o, Q):
            a, b = self._cmp(o)
            return a == b
        return NotImplemented

    __hash__ = None


def Abs(x):
    return Q(abs(x.v), x.kind, x.tag)


def Max(*a):
    best = a[0]
    for x in a[1:]:
        if x.v > best.v:
            best = x
    return best


def Min(*a):
    best = a[0]
    for x in a[1:]:
        if x.v < best.v:
            best = x
    return best


def Floor(x, step):
    assert x.kind == "num" and step.kind == "num"
    return Q(math.floor(x.v / step.v) * step.v)


def Sin(x):
    assert x.kind == "ang"
    return Q(math.sin(math.radians(x.v)))


def Cos(x):
    assert x.kind == "ang"
    return Q(math.cos(math.radians(x.v)))


def If(c, a, b):
    return a if c else b


def And(*a):
    return all(a)


def to_python(expr):
    out, pos = [], 0
    while pos < len(expr):
        m = TOKEN.match(expr, pos)
        if not m:
            raise ValueError(f"cannot tokenize {expr!r} at {pos}: {expr[pos:pos + 20]!r}")
        pos = m.end()
        if m.group("ws"):
            continue
        if m.group("str"):
            out.append(f"Q({m.group('str')},'str')")
        elif m.group("num"):
            unit = m.group("unit")
            if unit == "deg":
                out.append(f"Q({m.group('num')},'ang','deg')")
            elif unit:
                out.append(f"Q.length({m.group('num')},{unit!r})")
            else:
                out.append(f"Q({m.group('num')})")
        elif m.group("name"):
            name = m.group("name")
            if name in ("Abs", "Max", "Min", "Floor", "Sin", "Cos", "If", "And"):
                out.append(name)
            elif "." in name:
                r, n = name.split(".")
                out.append(f"X({r!r},{n!r})")
            else:
                out.append(f"V({name!r})")
        else:
            op = m.group("op")
            out.append("**" if op == "^" else op)
    return " ".join(out)


def split_to(rhs):
    m = re.search(r"\s+to\s+(in|ft|deg)\s*$", rhs)
    return (rhs[:m.start()], m.group(1)) if m else (rhs, None)


def sig_decimals(x):
    """RoundedNumber(3, 3): three decimals, but never fewer than three significant digits."""
    if x == 0:
        return 3
    return max(3, 2 - math.floor(math.log10(abs(x))))


def fmt_num(x):
    x = 0.0 if abs(x) < 5e-13 else x
    d = sig_decimals(x)
    s = f"{x:.{d}f}"
    if abs(x - round(x, d)) < 1e-12:                # exactly representable at that precision: trim zeros
        s = s.rstrip("0").rstrip(".") if "." in s else s
    return s


def fmt(q):
    if q.kind == "str":
        return q.v
    if q.kind == "num":
        return fmt_num(q.v)
    if q.kind == "ang":
        return f"{fmt_num(q.v)} deg"
    if q.tag == "in":
        return f"{fmt_num(q.v)} in"
    if q.tag == "ft":
        return f"{fmt_num(q.v / 12)} ft"
    sign = "-" if q.v < 0 else ""
    v = abs(q.v)
    feet = int(v // 12)
    inch = v - 12 * feet
    if round(inch, 3) >= 12.0:
        feet, inch = feet + 1, 0.0
    # the inch part of a feet-and-inches display is rounded and its trailing zeros dropped ("8 ft 10 in")
    s = f"{inch:.{sig_decimals(inch)}f}".rstrip("0").rstrip(".")
    return f"{sign}{feet} ft {s or '0'} in"


def cell_text(q, unit):
    """Table cell `num` text for `<expr> to <unit>`: the full-precision value as Blockpad stores it."""
    if unit == "deg":
        assert q.kind == "ang"
        v = q.v
    else:
        assert q.kind == "len"
        v = q.v / TO_IN[unit]
    s = repr(v)
    if s.endswith(".0"):
        s = s[:-2]
    return f"{s} {unit}"


class Report:
    def __init__(self, defs, external):
        self.defs, self.external, self.memo = defs, external, {}

    def V(self, name):
        if name not in self.memo:
            if name not in self.defs:
                raise KeyError(name)
            self.memo[name] = self.eval_formula(self.defs[name])
        return self.memo[name]

    def X(self, report, name):
        return self.external[(report, name)]

    def eval_formula(self, rhs):
        expr, unit = split_to(rhs)
        env = {"Q": Q, "V": self.V, "X": self.X, "Abs": Abs, "Max": Max, "Min": Min, "Floor": Floor,
               "Sin": Sin, "Cos": Cos, "If": If, "And": And}
        q = eval(to_python(expr), {"__builtins__": {}}, env)  # noqa: S307 - journal formulas only
        if isinstance(q, bool):
            q = Q("True" if q else "False", "str")
        if unit == "deg":
            assert q.kind == "ang"
        elif unit:
            q = Q(q.v, "len", unit)
        return q

    def text(self, name):
        return fmt(self.V(name))

    def cell(self, formula):
        expr, unit = split_to(formula)
        q = self.eval_formula(expr)
        return cell_text(q, unit) if unit else fmt(q)
