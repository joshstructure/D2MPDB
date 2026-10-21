"""Blockpad (.bpad) writer, formula emitter and independent evaluator for the distilled cap sheets.

Three parts, standard library and lxml only:

* ``bp_name`` / ``bp_formula`` / ``bp_unit``: turn the Mathcad equation-list identifiers and parse trees of
  scripts/mathcad_sheet.py (tuple trees) into Blockpad formula text.
* ``BpEngine``: an independent, dimension-aware evaluator of the Blockpad formula syntax (implicit unit
  multiplication, ``^`` right-associative, ``If/And/Or/Not/Min/Max/Sqrt/Abs/Round/Floor/Tan/Sin/Cos/Atan/Asin``,
  user functions, strings, ``to <unit>`` display suffix). It is an extension of mse_strap_check/expression_check.py.
* XML helpers that write the native elements this project has already recalculated in Blockpad (tasks/T008,
  mse_strap_check/build_check.py): paragraph / dynexp / expbody, hidden sections, tables with ``<c>`` and
  ``<textcell>`` cells, and canvases built from ``PlotLines`` plots, circles, labels and linear dimensions.

Nothing here knows about caps; scripts/build_cap_bpad.py drives it.
"""
import math
import re
from decimal import Decimal
from pathlib import Path

from lxml import etree as ET

# ----------------------------------------------------------------------------- names
UNITS = {'in', 'ft', 'kip', 'ksi', 'ksf', 'klf', 'psf', 'psi', 'deg', 'lbf'}

BP_NAME = {
    'gamma_e': 'γ_e', 'phi_f': 'φ_f', 'phi_v': 'φ_v', 'phi_a': 'φ_a', 'phi_m': 'φ_m', 'phi_n': 'φ_n',
    'lambda_c': 'λ', 'alpha_1': 'α_1', 'beta_1': 'β_1', 'beta_s': 'β_s', 'beta_g': 'β_g', 'beta': 'β',
    'theta_g': 'θ_g', 'theta': 'θ', 'eps_t': 'ε_t', 'eps_b': 'ε_b', 'eps_s': 'ε_s',
    'lam_rl': 'λ_rl', 'lam_cf': 'λ_cf', 'lam_c': 'λ_c',
}
MC_NAME = {v: k for k, v in BP_NAME.items()}


def bp_name(name):
    """Blockpad identifier of a Mathcad equation-list identifier (Unicode Greek, underscore subscripts)."""
    return BP_NAME.get(name, name)


def mc_name_of(name):
    """Reverse of bp_name for the explicit table (anything else is unchanged)."""
    return MC_NAME.get(name, name)


def bp_num(v):
    """A number as plain decimal text: never exponent notation, no trailing '.0'."""
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f'{v!r} has no Blockpad literal')
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    text = repr(v)
    if 'e' in text or 'E' in text:
        text = format(Decimal(text), 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def bp_unit(unit):
    """Blockpad display unit of a Mathcad-style unit string ('in**2/in' -> 'in^2/in'); None stays None."""
    if not unit:
        return None
    return unit.replace('**', '^').replace(' ', '').strip('()')


# ----------------------------------------------------------------------------- formula emitter
BANNED_CALLS = {'tr', 'row', 'col', 'stack', 'augment', 'last'}
FUNCTIONS = {'max': 'Max', 'min': 'Min', 'sqrt': 'Sqrt', 'abs': 'Abs', 'tan': 'Tan', 'sin': 'Sin', 'round': 'Round'}


class EmitError(ValueError):
    pass


def _pure(t):
    """(coefficient, numerator units, denominator units) of a product, quotient or power of units and plain numbers."""
    k = t[0]
    if k == 'num':
        return (t[1], [], [])
    if k == 'neg' and t[1][0] == 'num':
        return (-t[1][1], [], [])
    if k == 'id' and t[1] in UNITS:
        return (1.0, [(t[1], 1)], [])
    if k == 'bin':
        a = _pure(t[2])
        if a is None:
            return None
        b = _pure(t[3])
        if b is None:
            return None
        op = t[1]
        if op == '*':
            return (a[0] * b[0], a[1] + b[1], a[2] + b[2])
        if op == '/':
            return (a[0] / b[0], a[1] + b[2], a[2] + b[1])
        if op == '**':
            if b[1] or b[2]:
                return None
            n = b[0]
            if not (a[1] or a[2]):
                return (a[0] ** n, [], [])
            if n == int(n) and n > 0:
                return (a[0] ** n, [(u, p * int(n)) for u, p in a[1]], [(u, p * int(n)) for u, p in a[2]])
    return None


def _units_text(units):
    merged = []
    for u, p in units:
        for i, (u2, p2) in enumerate(merged):
            if u2 == u:
                merged[i] = (u, p2 + p)
                break
        else:
            merged.append((u, p))
    return [u if p == 1 else f'{u}^{p}' for u, p in merged]


def _quantity(coef, num, den):
    top, bottom = _units_text(num), _units_text(den)
    if not top:
        raise EmitError('a reciprocal unit has no Blockpad literal here')
    text = bp_num(coef) + ' ' + '*'.join(top)
    if len(bottom) == 1:
        text += '/' + bottom[0]
    elif bottom:
        text += '/(' + '*'.join(bottom) + ')'
    return text


class _Scalars:
    """Adapter: a dict {(base, index): name, ('vec', base): [names]} or a callable (base, index) -> name | None.

    `index` is an int (constant subscript), a string (the free range variable of an indexed definition) or None
    (query for the whole vector, answering a list of names)."""

    def __init__(self, source):
        self.source = source
        self.functions = set()                      # user-defined Blockpad functions a tree may call by name

    def __call__(self, base, index):
        if self.source is None:
            return None
        if callable(self.source):
            return self.source(base, index)
        if index is None:
            return self.source.get(('vec', base))
        return self.source.get((base, index))


def bp_formula(tree, scalars=None, functions=()):
    """Blockpad formula text of a Mathcad parse tree (see module docstring and scripts/mathcad_sheet.py).

    `functions` names user-defined Blockpad functions the tree may call (emitted as `Name(args)`)."""
    S = scalars if isinstance(scalars, _Scalars) else _Scalars(scalars)
    S.functions = S.functions | set(functions)
    text, _ = _emit(tree, S)
    return text


def _wrap(pair, minimum):
    text, prec = pair
    return f'({text})' if prec < minimum else text


def _flatten_logic(t, tag):
    if t[0] == tag:
        return _flatten_logic(t[1], tag) + _flatten_logic(t[2], tag)
    return [t]


def _emit(t, S):
    """(text, precedence): 0 comparison, .5 'number unit' literal, 1 additive, 2 multiplicative, 3 unary, 4 power, 5 atom."""
    k = t[0]
    if k in ('bin', 'neg', 'id'):
        q = _pure(t)
        if q is not None and (q[1] or q[2]):
            text = _quantity(*q)
            return (text, 0.5) if q[1] else (text, 2)
        if q is not None and k == 'bin' and t[1] == '**' and (t[3][0] == 'neg' or (t[3][0] == 'num' and t[3][1] < 0)):
            return bp_num(q[0]) if q[0] >= 0 else '-' + bp_num(-q[0]), 5
    if k == 'num':
        return (bp_num(t[1]), 5) if t[1] >= 0 else ('-' + bp_num(-t[1]), 3)
    if k == 'str':
        return '"' + t[1] + '"', 5
    if k == 'id':
        name = t[1]
        if name in UNITS:
            return f'(1 {name})', 5
        if S(name, None) is not None:
            raise EmitError(f'the vector {name} reached the emitter without an index')
        return bp_name(name), 5
    if k == 'neg':
        return '-' + _wrap(_emit(t[1], S), 4), 3
    if k == 'bin':
        op = t[1]
        if op in ('+', '-'):
            return f'{_wrap(_emit(t[2], S), 1)} {op} {_wrap(_emit(t[3], S), 2)}', 1
        if op in ('*', '/'):
            return f'{_wrap(_emit(t[2], S), 2)}{op}{_wrap(_emit(t[3], S), 3)}', 2
        if op == '**':
            return f'{_wrap(_emit(t[2], S), 5)}^{_wrap(_emit(t[3], S), 5)}', 4
        raise EmitError(op)
    if k == 'cmp':
        op = t[1]
        return f'{_wrap(_emit(t[2], S), 0.5)} {op} {_wrap(_emit(t[3], S), 0.5)}', 0
    if k in ('and', 'or'):
        parts = _flatten_logic(t, k)
        return ('And' if k == 'and' else 'Or') + '(' + ', '.join(_emit(p, S)[0] for p in parts) + ')', 5
    if k == 'idx':
        base, index = t[1], t[2]
        if base[0] != 'id':
            raise EmitError('only a named vector can be indexed')
        name = base[1]
        if name in ('A_bar', 'd_bar'):
            return ('Ab' if name == 'A_bar' else 'Db') + '(' + _emit(index[0], S)[0] + ')', 5
        if len(index) != 1:
            raise EmitError(f'{name}: a matrix element reached the emitter')
        i = index[0]
        if i[0] == 'num':
            key = int(i[1])
        elif i[0] == 'id':
            key = i[1]
        else:
            raise EmitError(f'{name}: subscript must be a constant or the range variable')
        scalar = S(name, key)
        if scalar is None:
            raise EmitError(f'{name}[{key}] has no scalar name')
        return scalar, 5
    if k == 'call':
        f, args = t[1], t[2]
        if f in BANNED_CALLS:
            raise EmitError(f'{f}() is handled by the builder, not the emitter')
        if f == 'IF':
            return 'If(' + ', '.join(_emit(a, S)[0] for a in args) + ')', 5
        if f in S.functions:
            return bp_name(f) + '(' + ', '.join(_emit(a, S)[0] for a in args) + ')', 5
        if f in ('max', 'min'):
            flat = []

            def collect(items):
                for a in items:
                    if a[0] == 'call' and a[1] == f:
                        collect(a[2])
                    elif a[0] == 'id' and a[1] not in UNITS and S(a[1], None) is not None:
                        flat.extend(S(a[1], None))
                    else:
                        flat.append(_emit(a, S)[0])
            collect(args)
            return FUNCTIONS[f] + '(' + ', '.join(flat) + ')', 5
        if f in FUNCTIONS:
            return FUNCTIONS[f] + '(' + ', '.join(_emit(a, S)[0] for a in args) + ')', 5
        raise EmitError(f'unknown function {f}')
    raise EmitError(k)


# ----------------------------------------------------------------------------- the Blockpad evaluator
class BpError(ValueError):
    pass


class Q:
    """A number with (length, force, angle) dimensions; inch, kip and radian are the base units."""
    __slots__ = ('v', 'd')

    def __init__(self, v, d=(0., 0., 0.)):
        self.v = float(v)
        self.d = tuple(float(x) for x in d)

    def same(self, o, what='+'):
        if not isinstance(o, Q):
            raise BpError(f'{what}: {o!r} is not a quantity')
        if any(abs(a - b) > 1e-8 for a, b in zip(self.d, o.d)):
            raise BpError(f'{what}: incompatible units {self.d} and {o.d}')
        return o

    def __repr__(self):
        return f'Q({self.v:g}, {self.d})'


class _Null:
    def __repr__(self):
        return 'null'


NULL = _Null()
NODIM = (0., 0., 0.)
UNIT_Q = {'in': Q(1, (1, 0, 0)), 'ft': Q(12, (1, 0, 0)), 'kip': Q(1, (0, 1, 0)), 'ksi': Q(1, (-2, 1, 0)),
          'ksf': Q(1 / 144, (-2, 1, 0)), 'klf': Q(1 / 12, (-1, 1, 0)), 'psf': Q(0.001 / 144, (-2, 1, 0)),
          'psi': Q(0.001, (-2, 1, 0)), 'lbf': Q(0.001, (0, 1, 0)), 'deg': Q(math.pi / 180, (0, 0, 1)),
          'pcf': Q(0.001 / 1728, (-3, 1, 0)), 'kcf': Q(1 / 1728, (-3, 1, 0)), 'rad': Q(1, (0, 0, 1)),
          'lb': Q(0.001, (0, 1, 0))}
CONSTANT_Q = {'pi': Q(math.pi)}                  # Blockpad's built-in constants read by the journal calculations
TOKEN = re.compile(r'\s*("(?:[^"\\]|\\.)*"|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_Ͱ-Ͽ][A-Za-z_0-9.Ͱ-Ͽ]*'
                   r'|<=|>=|==|!=|[()+\-*/^,<>\[\]])')
NUMBER = re.compile(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
PRECEDENCE = {'==': 5, '!=': 5, '<': 5, '>': 5, '<=': 5, '>=': 5, '+': 10, '-': 10, '*': 20, '/': 20, '^': 30}
TO_SUFFIX = re.compile(r'\s+to\s+([A-Za-z][A-Za-z0-9^*/ ()]*)\s*$')
KNOWN_FUNCTIONS = {'If', 'And', 'Or', 'Not', 'Min', 'Max', 'Sqrt', 'Abs', 'Round', 'Floor', 'Tan', 'Sin', 'Cos',
                   'Atan', 'Asin', 'Acos', 'Ln', 'Exp'}


def tokenize(s):
    tokens, pos = [], 0
    s = s.rstrip()
    while pos < len(s):
        m = TOKEN.match(s, pos)
        if not m:
            raise BpError(f'cannot read {s[pos:pos + 20]!r} in {s!r}')
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


FT_IN = re.compile(r'(?<![\w.])(\d+(?:\.\d+)?)\s+ft\s+(\d+(?:\.\d+)?)(?:\s+(\d+)/(\d+))?\s+in(?![\w^])')
FT_IN_MARKS = re.compile(r'(?<![\w.])(\d+(?:\.\d+)?)\'\s*(?:(\d+(?:\.\d+)?)(?:\s+(\d+)/(\d+))?\s*")?')
IN_MARK = re.compile(r'(?<![\w.])(\d+(?:\.\d+)?)"')
MIXED = re.compile(r'(?<![\w.])(\d+)\s+(\d+)/(\d+)\s+(in|ft|deg)(?![\w^])')


STRING_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"')


def normalise_literals(s):
    """Blockpad's feet-inches and mixed-fraction literals ('8 ft 7 in', '35 ft 8 51/64 in', '1 3/4 in', 7'1") as plain arithmetic.

    String literals are left untouched (a "0" option value is not an inch mark)."""
    strings = []

    def stash(m):
        strings.append(m.group(0))
        return f'\x00{len(strings) - 1}\x00'
    s = STRING_TOKEN.sub(stash, s)

    def ft_in(m):
        inches = m.group(2) if not m.group(3) else f'({m.group(2)} + {m.group(3)}/{m.group(4)})'
        return f'({m.group(1)} ft + {inches} in)'

    def marks(m):
        if m.group(2) is None:
            return f'({m.group(1)} ft)'
        inches = m.group(2) if not m.group(3) else f'({m.group(2)} + {m.group(3)}/{m.group(4)})'
        return f'({m.group(1)} ft + {inches} in)'
    s = FT_IN.sub(ft_in, s)
    if "'" in s:
        s = FT_IN_MARKS.sub(marks, s)
    if '"' in s:
        s = IN_MARK.sub(lambda m: f'({m.group(1)} in)', s)
    s = MIXED.sub(lambda m: f'({m.group(1)} + {m.group(2)}/{m.group(3)}) {m.group(4)}', s)
    return re.sub(r'\x00(\d+)\x00', lambda m: strings[int(m.group(1))], s)


def parse(s):
    """Parse a Blockpad expression (no leading 'name =' and no 'to <unit>' suffix)."""
    ts = tokenize(normalise_literals(s))
    if not ts:
        raise BpError('empty expression')
    idx = 0

    def need(tok):
        nonlocal idx
        if idx >= len(ts) or ts[idx] != tok:
            raise BpError(f'expected {tok!r} in {s!r}')
        idx += 1

    def expr(minp=0):
        nonlocal idx
        if idx >= len(ts):
            raise BpError(f'unexpected end of {s!r}')
        t = ts[idx]
        idx += 1
        if t in ('+', '-'):
            a = ('unary', t, expr(29))
        elif t == '(':
            a = expr()
            need(')')
        elif t.startswith('"'):
            a = ('str', t[1:-1])
        elif NUMBER.match(t):
            a = ('num', float(t))
        elif idx < len(ts) and ts[idx] == '(':
            idx += 1
            args = []
            if idx < len(ts) and ts[idx] != ')':
                while True:
                    args.append(expr())
                    if idx < len(ts) and ts[idx] == ',':
                        idx += 1
                        continue
                    break
            need(')')
            a = ('call', t, args)
        elif t in ('[', ']', ')', ',', '*', '/', '^', '<', '>', '<=', '>=', '==', '!='):
            raise BpError(f'unexpected {t!r} in {s!r}')
        else:
            a = ('name', t)
        while idx < len(ts):
            op = ts[idx]
            implicit = op in UNIT_Q
            if implicit:
                op = '*'
            p = PRECEDENCE.get(op, -1)
            if p < minp:
                break
            if not implicit:
                idx += 1
            b = expr(p if op == '^' else p + 1)
            a = ('bin', op, a, b)
        return a

    result = expr()
    if idx != len(ts):
        raise BpError(f'unread tokens {ts[idx:]} in {s!r}')
    return result


def split_to(rhs):
    """(expression, display unit or None) of 'expression to unit'."""
    m = TO_SUFFIX.search(rhs)
    if not m or '"' in rhs[m.start():]:
        return rhs, None
    return rhs[:m.start()], m.group(1).strip()


def split_definition(formula):
    """('name' | 'f(a, b)', rhs) of a definition formula, or (None, formula) for a bare expression."""
    m = re.match(r'^\s*([^\s=()"]+(?:\([^()"]*\))?)\s=\s(.*)$', formula, flags=re.S)
    if not m:
        return None, formula
    return m.group(1), m.group(2)


class BpEngine:
    """Evaluator of Blockpad formulas: definitions added with add(), evaluated lazily, units checked."""

    def __init__(self, report=None):
        self.report = report
        self.defs, self.functions, self.cache = {}, {}, {}
        self.units, self.order, self.stack = {}, [], []
        self.called = set()
        self.externals = {}                      # qualified names of other reports (journal edition): name -> value

    # -- definitions
    def add_external(self, name, value, unit=None):
        """A value owned by another report, read by its qualified name (e.g. BridgeGeometry_2Beam.EndBentCap_width)."""
        self.externals[name] = value
        if unit:
            self.units[name] = unit

    def add_function_as(self, qualified, formula):
        """A function owned by another report, called by its qualified name (CapDesignBasis.Ab(k))."""
        lhs, rhs = split_definition(formula)
        if lhs is None or '(' not in lhs:
            raise BpError(f'not a function definition: {formula!r}')
        expression, _ = split_to(rhs)
        tree = parse(expression)
        self._collect_calls(tree)
        args = lhs.split('(', 1)[1]
        self.functions[qualified] = ([a.strip() for a in args[:-1].split(',') if a.strip()], tree)

    def add(self, formula):
        lhs, rhs = split_definition(formula)
        if lhs is None:
            raise BpError(f'not a definition: {formula!r}')
        expression, unit = split_to(rhs)
        tree = parse(expression)
        self._collect_calls(tree)
        if '(' in lhs:
            name, args = lhs.split('(', 1)
            params = [a.strip() for a in args[:-1].split(',') if a.strip()]
            if name in self.functions or name in self.defs:
                raise BpError(f'{name} is defined twice')
            self.functions[name] = (params, tree)
        else:
            name = lhs
            if name in self.defs or name in self.functions:
                raise BpError(f'{name} is defined twice')
            if name in UNIT_Q or name in CONSTANT_Q or name in ('true', 'false', 'null'):
                raise BpError(f'{name} is a reserved name')
            self.defs[name] = tree
            literal = re.match(r'^-?[0-9.]+\s+([A-Za-z][A-Za-z0-9^*/]*)$', expression.strip())
            self.units[name] = unit or (literal.group(1) if literal else None)
        self.order.append(name)
        return name

    def check(self, formula):
        """Syntax check of a definition or a bare expression (raises BpError on anything unreadable)."""
        lhs, rhs = split_definition(formula)
        expression, _ = split_to(rhs)
        tree = parse(expression)
        self._collect_calls(tree)
        return tree

    def _collect_calls(self, a):
        if a[0] == 'call':
            self.called.add(a[1])
            for x in a[2]:
                self._collect_calls(x)
        elif a[0] == 'bin':
            self._collect_calls(a[2])
            self._collect_calls(a[3])
        elif a[0] == 'unary':
            self._collect_calls(a[2])

    # -- evaluation
    def _strip(self, name):
        if self.report and name.startswith(self.report + '.'):
            return name[len(self.report) + 1:]
        return name

    def get(self, name):
        if name in self.externals:
            return self.externals[name]
        name = self._strip(name)
        if name in self.cache:
            return self.cache[name]
        if name in UNIT_Q:
            return UNIT_Q[name]
        if name in CONSTANT_Q:
            return CONSTANT_Q[name]
        if name in ('true', 'false'):
            return name == 'true'
        if name == 'null':
            return NULL
        if name not in self.defs:
            raise BpError(f'{name} is not defined')
        if name in self.stack:
            raise BpError(f'circular definition: {" -> ".join(self.stack + [name])}')
        self.stack.append(name)
        try:
            value = self._eval(self.defs[name], {})
        except BpError as e:
            raise BpError(f'{name}: {e}') from None
        finally:
            self.stack.pop()
        self.cache[name] = value
        return value

    def evaluate(self, formula):
        """Value of an expression or of 'name = expression'; a trailing 'to unit' is ignored."""
        return self.evaluate_unit(formula)[0]

    def evaluate_unit(self, formula):
        lhs, rhs = split_definition(formula)
        expression, unit = split_to(rhs)
        bare = re.fullmatch(r'[^\s()"]+', expression.strip())
        value = self._eval(parse(expression), {})
        if unit is None and bare and self._strip(expression.strip()) in self.units:
            unit = self.units[self._strip(expression.strip())]
        return value, unit

    def _eval(self, a, scope):
        k = a[0]
        if k == 'num':
            return Q(a[1])
        if k == 'str':
            return a[1]
        if k == 'name':
            n = a[1]
            return scope[n] if n in scope else self.get(n)
        if k == 'unary':
            v = self._eval(a[2], scope)
            if v is NULL:
                return NULL
            if not isinstance(v, Q):
                raise BpError('unary sign of a non-number')
            return Q(-v.v, v.d) if a[1] == '-' else v
        if k == 'bin':
            op = a[1]
            x, y = self._eval(a[2], scope), self._eval(a[3], scope)
            if op in ('==', '!=', '<', '>', '<=', '>='):
                return self._compare(op, x, y)
            if x is NULL or y is NULL:
                return NULL
            if not isinstance(x, Q) or not isinstance(y, Q):
                raise BpError(f'{op} needs numbers, got {x!r} and {y!r}')
            if op == '+':
                x.same(y, '+')
                return Q(x.v + y.v, x.d)
            if op == '-':
                x.same(y, '-')
                return Q(x.v - y.v, x.d)
            if op == '*':
                return Q(x.v * y.v, tuple(p + q for p, q in zip(x.d, y.d)))
            if op == '/':
                if y.v == 0:
                    raise BpError('division by zero')
                return Q(x.v / y.v, tuple(p - q for p, q in zip(x.d, y.d)))
            if op == '^':
                if any(abs(d) > 1e-12 for d in y.d):
                    raise BpError('dimensioned exponent')
                return Q(x.v ** y.v, tuple(p * y.v for p in x.d))
            raise BpError(op)
        name, args = a[1], a[2]
        if name == 'If':
            if len(args) != 3:
                raise BpError('If takes three arguments')
            c = self._eval(args[0], scope)
            if not isinstance(c, bool):
                raise BpError(f'If condition is {c!r}, not true/false')
            return self._eval(args[1] if c else args[2], scope)
        values = [self._eval(x, scope) for x in args]
        if name in self.functions:
            params, body = self.functions[name]
            if len(params) != len(values):
                raise BpError(f'{name} takes {len(params)} arguments')
            return self._eval(body, dict(zip(params, values)))
        if name in ('Min', 'Max'):
            if not values:
                raise BpError(f'{name} of nothing')
            for v in values:
                values[0].same(v, name)
            return (min if name == 'Min' else max)(values, key=lambda q: q.v)
        if name == 'Sqrt':
            v = values[0]
            if v.v < 0:
                raise BpError('Sqrt of a negative number')
            return Q(math.sqrt(v.v), tuple(d / 2 for d in v.d))
        if name == 'Abs':
            return Q(abs(values[0].v), values[0].d)
        if name == 'Round':
            if len(values) != 2:
                raise BpError('Round takes a value and a number of decimals')
            return Q(round(values[0].v, int(values[1].v)), values[0].d)
        if name == 'Floor':
            values[0].same(values[1], 'Floor')
            return Q(math.floor(values[0].v / values[1].v) * values[1].v, values[0].d)
        if name == 'And':
            return all(self._bool(v, name) for v in values)
        if name == 'Or':
            return any(self._bool(v, name) for v in values)
        if name == 'Not':
            return not self._bool(values[0], name)
        if name in ('Tan', 'Sin', 'Cos'):
            if values[0].d != (0., 0., 1.):
                raise BpError(f'{name} needs an angle')
            return Q(getattr(math, name.lower())(values[0].v))
        if name in ('Atan', 'Asin', 'Acos'):
            if values[0].d != NODIM:
                raise BpError(f'{name} needs a plain number')
            return Q(getattr(math, name.lower())(values[0].v), (0., 0., 1.))
        if name in ('Ln', 'Exp'):
            if values[0].d != NODIM:
                raise BpError(f'{name} needs a plain number')
            return Q(math.log(values[0].v) if name == 'Ln' else math.exp(values[0].v))
        raise BpError(f'unknown function {name}')

    @staticmethod
    def _bool(v, name):
        if not isinstance(v, bool):
            raise BpError(f'{name} needs true/false, got {v!r}')
        return v

    @staticmethod
    def _compare(op, x, y):
        if isinstance(x, str) or isinstance(y, str):
            if not (isinstance(x, str) and isinstance(y, str)) or op not in ('==', '!='):
                raise BpError(f'cannot compare {x!r} {op} {y!r}')
            return (x == y) if op == '==' else (x != y)
        if isinstance(x, bool) and isinstance(y, bool) and op in ('==', '!='):
            return (x == y) if op == '==' else (x != y)
        if not isinstance(x, Q) or not isinstance(y, Q):
            raise BpError(f'cannot compare {x!r} {op} {y!r}')
        x.same(y, op)
        tol = 1e-9 * max(1.0, abs(x.v), abs(y.v))
        return {'==': abs(x.v - y.v) <= tol, '!=': abs(x.v - y.v) > tol, '<': x.v < y.v, '>': x.v > y.v,
                '<=': x.v <= y.v, '>=': x.v >= y.v}[op]

    def all(self):
        """Evaluate every variable definition; returns {name: value}."""
        for name in self.order:
            if name in self.defs:
                self.get(name)
        return {n: self.cache[n] for n in self.order if n in self.defs}

    def unresolved_calls(self):
        """Names called as functions that are neither built in nor defined."""
        return sorted(c for c in self.called if c not in KNOWN_FUNCTIONS and c not in self.functions)

    # -- display
    def unit_q(self, unit):
        return self._eval(parse('1 ' + unit), {})

    def format_value(self, value, unit=None):
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, str):
            return value
        if value is NULL:
            return 'null'
        if unit:
            u = self.unit_q(unit)
            value.same(u, f'display unit {unit}')
            return f'{value.v / u.v:.3f} {unit}'
        if value.d == NODIM:
            return f'{value.v:.3f}'
        natural = {(1., 0., 0.): 'in', (0., 1., 0.): 'kip', (-2., 1., 0.): 'ksi', (0., 0., 1.): 'deg',
                   (2., 0., 0.): 'in^2', (3., 0., 0.): 'in^3', (4., 0., 0.): 'in^4', (1., 1., 0.): 'kip*in'}.get(value.d)
        if natural is None:
            natural = '*'.join(f'{u}^{d:g}' for u, d in zip(('in', 'kip', 'rad'), value.d) if d)
        return self.format_value(value, natural)

    def display(self, name):
        name = self._strip(name)
        return self.format_value(self.get(name), self.units.get(name))

    def display_formula(self, formula):
        value, unit = self.evaluate_unit(formula)
        return self.format_value(value, unit)


# ----------------------------------------------------------------------------- live references into the project journal
class JournalError(BpError):
    pass


REPO_ROOT = Path(__file__).resolve().parent.parent


def display_path(path):
    """A journal path as it is recorded in the outputs: relative to the repository when inside it, else as given."""
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def tree_names(tree, names=None, calls=None):
    """(names, calls): the identifiers and the called function names of a parse tree from `parse`."""
    names = set() if names is None else names
    calls = set() if calls is None else calls
    k = tree[0]
    if k == 'name':
        names.add(tree[1])
    elif k == 'call':
        calls.add(tree[1])
        for a in tree[2]:
            tree_names(a, names, calls)
    elif k == 'bin':
        tree_names(tree[2], names, calls)
        tree_names(tree[3], names, calls)
    elif k == 'unary':
        tree_names(tree[2], names, calls)
    return names, calls


class JournalLinks:
    """Read-only evaluator of journal definitions, for the live references of the journal edition.

    The journal (32 MB) is parsed once. The definitions of an owner report are collected the first time one of its
    names is asked for, and only the transitive closure of the asked-for name is handed to a `BpEngine` (the evaluator
    that checks the cap sheets), so a long report costs nothing for the names that are not used. Journal formulas are
    read as the journal writes them: `PierCap_width=4ft`, `36 in to ft in`, `3/4 in`. A reference to another report
    inside a chain is resolved recursively. `override()` replaces an evaluated value (for tests of the coherence gate).
    `basis` is a slot for the CapDesignBasis edition that scripts/build_cap_bpad.py fills."""
    DEFINITION = re.compile(r'^\s*([^\s=()"<>!,]+)\s*=(?!=)\s*(.*?)\s*$', re.S)

    def __init__(self, root, source=None):
        self.root, self.source = root, source
        self.reports = {}
        for rep in root.iterfind('report'):
            name = rep.get('name')
            if name and name not in self.reports:
                self.reports[name] = rep
        self.spreadsheets = {}
        for sheet in root.iterfind('spreadsheet'):
            name = sheet.get('name')
            if name and name not in self.spreadsheets:
                self.spreadsheets[name] = sheet
        self._definitions, self._engines, self.overrides = {}, {}, {}
        self._cells = {}
        self.basis = None

    # -- spreadsheet owners (the gravity-load sheet PedBridgeWeights_2Beams): cached values, never recalculated
    CACHE_NUMBER = re.compile(r'^\s*(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-z][A-Za-z0-9^*/ ()]*)?\s*$')

    def cells(self, owner):
        """{name or A1 address: (cached text, formula)} of a spreadsheet; blank `cell` placeholders count as columns."""
        if owner not in self._cells:
            sheet = self.spreadsheets.get(owner)
            if sheet is None:
                raise JournalError(f'spreadsheet {owner} is not in the journal')
            found = {}
            for r, row in enumerate(sheet.findall('row'), 1):
                for c, cell in enumerate((x for x in row if x.tag in ('c', 'cell')), 1):
                    if cell.tag != 'c':
                        continue
                    cache = cell.find('num')
                    text = cell.find('textvalue')
                    value = (cache.text if cache is not None else text.text if text is not None else None)
                    entry = (value, cell.get('formula'))
                    col = ''
                    i = c
                    while i:
                        i, rem = divmod(i - 1, 26)
                        col = chr(65 + rem) + col
                    found[col + str(r)] = entry
                    if cell.get('name'):
                        found[cell.get('name')] = entry
            self._cells[owner] = found
        return self._cells[owner]

    def spreadsheet_value(self, owner, name):
        """The cached value of a spreadsheet cell as the evaluator's `Q` (or text): the sheet's own saved result."""
        entry = self.cells(owner).get(name)
        if entry is None or entry[0] is None:
            raise JournalError(f'{owner}.{name} has no cached value in the journal spreadsheet')
        text = entry[0].strip()
        if not self.CACHE_NUMBER.match(text) and not FT_IN.match(text):
            return text
        try:
            return self._engine(owner).evaluate(text)
        except BpError as e:
            raise JournalError(f'{owner}.{name}: cached value {text!r}: {e}') from None

    def owner_kind(self, owner):
        return 'report' if owner in self.reports else 'spreadsheet' if owner in self.spreadsheets else None

    @classmethod
    def load(cls, path):
        """Parse any journal file (the stable one or a preview); `source` records the path as given (repo-relative if inside)."""
        parser = ET.XMLParser(huge_tree=True, resolve_entities=False, no_network=True)
        return cls(ET.parse(str(path), parser).getroot(), display_path(path))

    def definitions(self, owner):
        """{name: [right-hand sides]} of the `name = ...` dynexps of an owner report (functions are not collected)."""
        if owner not in self._definitions:
            rep = self.reports.get(owner)
            if rep is None:
                raise JournalError(f'report {owner} is not in the journal')
            found = {}
            for dyn in rep.iter('dynexp'):
                formula = dyn.get('formula')
                if formula is None:
                    body = dyn.find('expbody')
                    formula = body.text if body is not None else None
                m = self.DEFINITION.match(formula) if formula else None
                if m:
                    options = found.setdefault(m.group(1), [])
                    if m.group(2) not in options:
                        options.append(m.group(2))
            for field in rep.iter('valuefield'):             # a native option/value field (C001 selectors): its text is the value
                name = field.get('name')
                text = field.findtext('textvalue')
                if name and text is not None:
                    rhs = '"' + text.replace('"', '') + '"' if not self.CACHE_NUMBER.match(text) else text
                    options = found.setdefault(name, [])
                    if rhs not in options:
                        options.append(rhs)
            self._definitions[owner] = found
        return self._definitions[owner]

    def _engine(self, owner):
        if owner not in self._engines:
            self._engines[owner] = BpEngine(report=owner)
        return self._engines[owner]

    def _load(self, owner, name):
        eng = self._engine(owner)
        if name in eng.defs:
            return
        options = self.definitions(owner).get(name)
        if not options:
            raise JournalError(f'{owner}.{name} is not defined in the journal')
        if len(options) > 1:
            raise JournalError(f'{owner}.{name} has {len(options)} different definitions: {options}')
        rhs = options[0]
        try:
            eng.add(f'{name} = {rhs}')
            names, calls = tree_names(parse(split_to(rhs)[0]))
        except BpError as e:
            raise JournalError(f'{owner}.{name} = {rhs}: {e}') from None
        for call in sorted(calls):
            if call not in KNOWN_FUNCTIONS:
                raise JournalError(f'{owner}.{name} calls {call}(), which the evaluator does not read')
        for dep in sorted(names):
            if dep in UNIT_Q or dep in CONSTANT_Q or dep in ('true', 'false', 'null'):
                continue
            if '.' in dep:                                       # another report inside the chain
                eng.add_external(dep, self.value(dep))
            else:
                self._load(owner, dep)

    def value(self, qualified):
        """The evaluated `Q` (inch, kip, radian base units) of a qualified journal name such as Owner.Name."""
        if qualified in self.overrides:
            return self.overrides[qualified]
        owner, dot, name = qualified.partition('.')
        if not dot or not name:
            raise JournalError(f'{qualified!r} is not a qualified journal name')
        if owner not in self.reports and owner in self.spreadsheets:
            return self.spreadsheet_value(owner, name)
        self._load(owner, name)
        try:
            return self._engine(owner).get(name)
        except BpError as e:
            raise JournalError(f'{qualified}: {e}') from None

    def formula(self, qualified):
        """The journal's own text of a definition, 'name = ...'."""
        owner, _, name = qualified.partition('.')
        options = self.definitions(owner).get(name)
        return f'{name} = {options[0]}' if options and len(options) == 1 else None

    def override(self, qualified, quantity):
        self.overrides[qualified] = quantity


# ----------------------------------------------------------------------------- XML helpers
TNR = 'Times New Roman'
PALETTE = {'discussion': ('#F1F5FA', '#DCE7F3', '#7189A6'),
           'input': ('#FFF8E9', '#F7E6B9', '#A78638'),
           'output': ('#EFF7F1', '#DCECE0', '#6A9075')}
INK, BLUE, TEAL, ORANGE, GREY, RED, ROSE = '#29333D', '#1766A0', '#167B75', '#C8702A', '#7B8993', '#C8372D', '#B35012'
NOTE_COLOR = '#43505C'


def new_document():
    doc = ET.Element('document', version='1.9', language='en-us')
    for lib in ('DateTime', 'Math', 'Logic', 'Lookup', 'Text', 'Scripts', 'Geometry'):
        ET.SubElement(doc, 'include', target='Library.' + lib)
    ET.SubElement(doc, 'stylerule', applytoall='True', type='AnyTableCell', valueformat='RoundedNumber(3, 3, {PriorityUnits: []})')
    ET.SubElement(doc, 'stylerule', applytoall='True', type='AnyTableCell', fontfamily=TNR, fontsize='11')
    for text, color in (('✓ PASS', '#ABDB92'), ('⊗ FAIL', '#EF3429'), ('✓ All Checks Pass', '#ABDB92'),
                        ('⊗ There are FAILURES', '#EF3429')):
        ET.SubElement(doc, 'stylerule', applytoall='True', type='AnyTableCell', condition='"' + text + '"', background=color)
    ET.SubElement(doc, 'stylerule', name='Result only', type='dynexp', showformula='False', showidentifier='False',
                  showresult='True', showsteps='false', mathlayout='off')
    return doc


def new_report(doc, name, title):
    r = ET.SubElement(doc, 'report', name=name, title=title, unit='in', pagesize='816,1056', margin='48,48,48,48',
                      bordermargin='0,0,0,0', collapsemargins='False')
    ET.SubElement(r, 'include', target='Library.Geometry')
    ET.SubElement(r, 'stylerule', type='AnyEquation', name='Required Input', texthighlight='#F7E6B9')
    return r


def para(parent, text='', **attrs):
    """A paragraph of Times New Roman 11 on one line (no inner newlines)."""
    if '\n' in text or '\r' in text:
        raise ValueError('paragraph text must not contain newlines')
    a = {'fontfamily': TNR, 'fontsize': '11', 'spacingafter': '6'}
    a.update({k: str(v) for k, v in attrs.items()})
    el = ET.SubElement(parent, 'paragraph', **a)
    if text:
        el.text = text
    return el


def heading(parent, text, page_break=False):
    extra = {'pagebreakbefore': 'break'} if page_break else {}
    return para(parent, text, fontsize='14', fontweight='bold', textcolor=BLUE, spacingbefore='8', keepwithnext='True', **extra)


def subheading(parent, text):
    return para(parent, text, fontsize='12', fontweight='bold', textcolor=BLUE, spacingbefore='6', keepwithnext='True')


def note(parent, text, size=10, **attrs):
    return para(parent, text, fontsize=str(size), textcolor=NOTE_COLOR, spacingafter=attrs.pop('spacingafter', '5'), **attrs)


def is_function_definition(formula):
    lhs, _ = split_definition(formula)
    return bool(lhs and '(' in lhs)


def equation(parent, formula, caption='', style=None, show_result=True, inline=False):
    """One definition as a native dynexp paragraph, with its caption (after a tab when `inline`, else below)."""
    func = is_function_definition(formula)
    if parent.tag == 'paragraph':
        p = parent                                   # the caller's paragraph (a table cell)
    elif inline and caption:
        p = para(parent, level='1', spacingafter='4')
    else:
        p = para(parent, spacingbefore='4', spacingafter='1', keepwithnext='True')
    attrs = dict(formula=formula, mathlayout='on', showformula='True',
                 showresult='False' if (func or not show_result) else 'True', showsteps='False')
    if style:
        attrs['style'] = style
        if style == 'Result only':
            attrs.update(showresult='True', showidentifier='False', showformula='False')
    dyn = ET.SubElement(p, 'dynexp', **attrs)
    ET.SubElement(dyn, 'expbody').text = formula
    if caption:
        if inline:
            br = ET.SubElement(p, 'break', type='tab')
            br.tail = caption
        else:
            note(parent, caption)
    return dyn


def section(parent, name, hide=True):
    return ET.SubElement(parent, 'section', name=name, capture='False', hide='true' if hide else 'false')


WORKING_NOTES = 'WorkingNotes'
WORKING_NOTES_INTRO = ('Working notes (hidden; not part of the submitted calculation): how this edition was produced, its '
                       'tool status and the open bookkeeping items.')


def working_notes(parent, name=WORKING_NOTES):
    """The hidden section that keeps the working language (provenance, status, pending items) out of the submitted text."""
    sec = section(parent, name, hide=True)
    para(sec, WORKING_NOTES_INTRO, fontsize='10', fontweight='bold', textcolor=NOTE_COLOR, spacingafter='4')
    return sec


def is_hidden(el):
    return el.tag == 'section' and (el.get('hide') or '').lower() == 'true'


def visible_text_elements(report):
    """Every paragraph, heading and table cell outside hidden sections, with its visible text."""
    def walk(node, hidden):
        if node.tag == 'section':
            hidden = hidden or is_hidden(node)
        if node.tag in ('paragraph', 'heading', 'c', 'textcell'):
            if not hidden:
                text = ' '.join(''.join(node.itertext()).split())
                if text:
                    yield node, text
            if node.tag != 'textcell':
                return
        for child in node:
            yield from walk(child, hidden)
    for child in report:
        yield from walk(child, False)


def rewrite_visible_text(report, rules):
    """Apply (old, new) text replacements to the prose outside hidden sections (text and tails; formulas untouched)."""
    def walk(node, hidden):
        if node.tag == 'section':
            hidden = hidden or is_hidden(node)
        if not hidden and node.tag not in ('dynexp', 'expbody', 'expresult'):
            for attr in ('text', 'tail'):
                text = getattr(node, attr)
                if text:
                    for old, new in rules:
                        text = text.replace(old, new)
                    setattr(node, attr, text)
        for child in node:
            walk(child, hidden)
    for child in report:
        walk(child, False)


# Working language that must not reach the visible text of a submitted calculation.
SUBMISSION_FORBIDDEN = re.compile(r'distill|notebook|\btools?\b|journal|\bD-\d{3}\b|\bT0\d{2}\b|\.py\b|\.ipynb|SHA-256|sha256'
                                  r'|pending|Codex|\btask\b|not design acceptance|working copy', re.I)


def check_submission_text(report, forbidden=SUBMISSION_FORBIDDEN):
    """Stop when the visible prose of a report still carries working language (see SUBMISSION_FORBIDDEN)."""
    bad = []
    for el, text in visible_text_elements(report):
        m = forbidden.search(text)
        if m:
            bad.append(f'  {el.tag} ({m.group(0)!r}): {text[:120]}')
    if bad:
        raise ValueError(f'working language in the visible text of {report.get("name")}:\n' + '\n'.join(bad))


def link(parent, text, address):
    p = para(parent, fontsize='9')
    ET.SubElement(p, 'link', address=address).text = text
    return p


def column_letter(i):
    return chr(ord('A') + i)


def text_cell(parent, text, font, bold=False, center=False, name=None, **attrs):
    """A multiline (textcell) table cell holding one paragraph of static text: text never clips as it does in a value cell.

    Bold goes on the paragraph (the native pattern); the background stays on the cell."""
    cell = ET.SubElement(parent, 'textcell', **({'name': name} if name else {}), **attrs)
    extra = {}
    if bold:
        extra['fontweight'] = 'bold'
    if center:
        extra['horzalign'] = 'Center'
    para(cell, text, fontsize=font, spacingafter='0', **extra)
    return cell


def table(parent, name, headers, rows, widths, palette='output', font='10'):
    """A native table. A cell is a string, ('formula', text) or ('define', formula, style).

    Text cells are multiline cells (`textcell`), so long labels wrap instead of clipping; formula cells are value cells
    (`c`), which carry the numbers and the PASS/FAIL strings the conditional colour rules act on."""
    body, head, border = PALETTE[palette]
    embed = ET.SubElement(parent, 'embed', spacingbefore='5', spacingafter='8')
    t = ET.SubElement(embed, 'table', name=name, capture='False', colwidths=', '.join(f'{i + 1}:{w}' for i, w in enumerate(widths)))
    last = column_letter(len(headers) - 1)
    n = len(rows) + 1
    ET.SubElement(t, 'stylerule', range=f'A1:{last}{n}', fontfamily=TNR, fontsize=font,
                  valueformat='RoundedNumber(3, 3, {PriorityUnits: []})',
                  border=f'Border("AllSides", "Solid", 0.6, "{border}"); Border("BetweenRows", "Solid", 0.4, "{border}");')
    ET.SubElement(t, 'stylerule', range=f'A1:{last}1', horzalign='Center', vertalign='Center')
    if len(headers) > 1:
        ET.SubElement(t, 'stylerule', range=f'B2:{last}{n}', horzalign='Center', vertalign='Center')
    for i, row in enumerate([headers] + rows):
        if len(row) != len(headers):
            raise ValueError(f'{name}: row {i} has {len(row)} cells for {len(headers)} columns')
        tr = ET.SubElement(t, 'row')
        for j, v in enumerate(row):
            attrs = {'capture': 'False', 'background': head if i == 0 else body}
            if isinstance(v, tuple) and v[0] == 'define':
                cell = ET.SubElement(tr, 'textcell', name=f'{name}R{i}C{j}', **attrs)
                p = para(cell, fontsize=font, spacingafter='2')
                dyn = ET.SubElement(p, 'dynexp', formula=v[1], mathlayout='on', showformula='True', showresult='False',
                                    showsteps='False', **({'style': v[2]} if v[2] else {}))
                ET.SubElement(dyn, 'expbody').text = v[1]
            elif isinstance(v, tuple) and v[0] == 'formula':
                if i == 0:
                    attrs['fontweight'] = 'bold'
                cell = ET.SubElement(tr, 'c', formula=v[1], **attrs)
            else:
                text_cell(tr, str(v), font, bold=(i == 0), center=(i == 0 or j > 0), name=f'{name}R{i}C{j}', **attrs)
    return t


#: The project stamp at the top of every calculation report. The standalone sheets carry it as static text; in the journal
#: edition the cells read the ProjectInfo report, whose strings must equal these (the coherence gates stop the builds otherwise).
PROJECT_STAMP = {
    'Firm': 'Parsons Transportation Group Inc',
    'Address': '1203 Governors Square Blvd, Suite 201, Tallahassee FL 32301',
    'Project': 'I-95 Capacity Improvements from South of SR 152 to South of SR 126',
    'JobNo': '',
    'DesignedBy': 'JAT',
    'DesignDate': '10/17/2026',
    'CheckedBy': 'MIK',
    'CheckDate': '',
}
STAMP_COLWIDTHS = (95, 165, 95, 165)
# (left label, left key, right label, right key) of the four rows of the project stamp; the keys are ProjectInfo names
STAMP_ROWS = (('Firm', 'Firm', 'Project', 'Project'), ('Address', 'Address', 'Job no.', 'JobNo'),
              ('Designed by', 'DesignedBy', 'Date', 'DesignDate'), ('Checked by', 'CheckedBy', 'Date', 'CheckDate'))
STAMP_KEYS = tuple(key for row in STAMP_ROWS for key in (row[1], row[3]))
PROJECT_INFO = 'ProjectInfo'


def project_stamp_table(parent, values, live=True, name='ProjectStamp'):
    """The project stamp: a 4-column discussion-palette table (Firm | value | Project | value, ...), appended to `parent`.

    `values` maps the ProjectInfo names (Firm, Address, Project, JobNo, DesignedBy, DesignDate, CheckedBy, CheckDate) to
    text. Every cell is a multiline cell, so the long project name wraps instead of clipping. With `live` each value cell
    holds a result-only reference (`dynexp formula="ProjectInfo.<Key>"`) whose cached result is the text; without it the
    cell is static text. The same inputs always give the same XML."""
    missing = [k for k in STAMP_KEYS if k not in values]
    if missing:
        raise ValueError(f'project stamp values missing: {missing}')
    body, _, border = PALETTE['discussion']
    embed = ET.SubElement(parent, 'embed', spacingbefore='5', spacingafter='8')
    t = ET.SubElement(embed, 'table', name=name, capture='False',
                      colwidths=', '.join(f'{i + 1}:{w}' for i, w in enumerate(STAMP_COLWIDTHS)))
    ET.SubElement(t, 'stylerule', range=f'A1:D{len(STAMP_ROWS)}', fontfamily=TNR, fontsize='9', vertalign='Center',
                  border=f'Border("AllSides", "Solid", 0.6, "{border}"); Border("BetweenRows", "Solid", 0.4, "{border}");')
    for i, (left_label, left_key, right_label, right_key) in enumerate(STAMP_ROWS):
        tr = ET.SubElement(t, 'row')
        for j, (label, key) in enumerate(((left_label, left_key), (right_label, right_key))):
            text_cell(tr, label, '9', bold=True, name=f'{name}R{i}C{2 * j}', capture='False', background=body)
            cell_name = f'{name}R{i}C{2 * j + 1}'
            if live:
                # a result-only definition (Stamp_Firm = ProjectInfo.Firm): the text of the owner, wrapped by the multiline cell
                cell = ET.SubElement(tr, 'textcell', name=cell_name, capture='False', background=body)
                p = para(cell, fontsize='9', spacingafter='0')
                equation(p, f'{STAMP_PREFIX}{key} = {PROJECT_INFO}.{key}', style='Result only', inline=True)
            else:
                text_cell(tr, str(values[key]), '9', name=cell_name, capture='False', background=body)
    return t


STAMP_PREFIX = 'Stamp_'                      # the live stamp definitions: Stamp_Firm = ProjectInfo.Firm, ...


def stamp_cells(table_el):
    """(label, cached value text, referenced owner or None) of the eight value cells of a project stamp table, row by row."""
    out = []
    for row in table_el.findall('row'):
        cells = list(row)
        for label, value in zip(cells[0::2], cells[1::2]):
            dyn = value.find('.//dynexp')
            if dyn is not None:
                cache = dyn.find('expresult')
                text = ((cache.text if cache is not None else '') or '').strip()
                owner = dyn.get('formula').partition('=')[2].strip()
            else:
                text, owner = ''.join(value.itertext()).strip(), value.get('formula')
            out.append((''.join(label.itertext()).strip(), text, owner))
    return out


class Canvas:
    """A native canvas (inches, y up, origin bottom-left) that also records what it draws for the preview sidecar."""

    def __init__(self, parent, name, title, width_in, height_in):
        embed = ET.SubElement(parent, 'embed', spacingbefore='4', spacingafter='5')
        self.el = ET.SubElement(embed, 'canvas', name=name, title=title, unit='in', size=f'{width_in:g} in; {height_in:g} in; scaletofit')
        ET.SubElement(self.el, 'include', target='Library.Geometry')
        self.name, self.title, self.width, self.height = name, title, width_in, height_in
        self.items = []

    @staticmethod
    def _n(v):
        return f'{v:.3f}'.rstrip('0').rstrip('.') if abs(v) >= 0.0005 else '0'

    def line(self, points, color=INK, width=1.0):
        xs = ','.join(self._n(x) for x, _ in points)
        ys = ','.join(self._n(y) for _, y in points)
        ET.SubElement(self.el, 'plot', formula=f'PlotLines([{xs}],[{ys}])', linecolor=color, linethickness=f'{width:g}')
        self.items.append({'type': 'line', 'points': [[round(x, 3), round(y, 3)] for x, y in points], 'color': color, 'width': width})

    def plot(self, xs, ys, color, width, resolved):
        """A line whose coordinates are formula text; `resolved` lists the visible (x, y) points for the preview."""
        ET.SubElement(self.el, 'plot', formula=f'PlotLines([{",".join(xs)}],[{",".join(ys)}])', linecolor=color, linethickness=f'{width:g}')
        if len(resolved) >= 2:
            self.items.append({'type': 'line', 'points': [[round(x, 3), round(y, 3)] for x, y in resolved], 'color': color, 'width': width})

    def rect(self, x0, y0, x1, y1, color=INK, width=1.0):
        self.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], color, width)

    def circle(self, cx, cy, r, fill=None, stroke=INK, width=1.0):
        attrs = dict(center=f'{self._n(cx)}, {self._n(cy)}, 0', normal='0, 0, 1', radius=self._n(r), linethickness=f'{width:g}', linecolor=stroke)
        if fill:
            attrs['fillcolor'] = fill
        ET.SubElement(self.el, 'circle', **attrs)
        self.items.append({'type': 'circle', 'cx': round(cx, 3), 'cy': round(cy, 3), 'r': round(r, 3), 'fill': fill, 'stroke': stroke, 'width': width})

    def label(self, x, y, text=None, formula=None, color=INK, size=9, bold=False, shown=None):
        """Static text, or a live value (`formula`, with `shown` the text resolved for the preview)."""
        attrs = dict(origin=f'{self._n(x)},{self._n(y)},0', dir='1,0,0', normal='0,0,1', fontfamily=TNR, fontsize=str(size), textcolor=color)
        if formula:
            attrs['formula'] = formula
        el = ET.SubElement(self.el, 'planecontainer', **attrs)
        if formula is None:
            ET.SubElement(el, 'textvalue').text = text
        self.items.append({'type': 'text', 'x': round(x, 3), 'y': round(y, 3), 'text': text if formula is None else (shown or ''),
                           'color': color, 'size': size, 'bold': False})

    def dim(self, start, end, through, formula, shown, color=BLUE, size=9, width=0.7):
        """A linear dimension from `start` to `end` drawn through the point `through`, labelled with a live value."""
        el = ET.SubElement(self.el, 'lineardim', startpoint=f'{self._n(start[0])}, {self._n(start[1])}, 0',
                           endpoint=f'{self._n(end[0])}, {self._n(end[1])}, 0',
                           pointondimline=f'{self._n(through[0])}, {self._n(through[1])}, 0', formula=formula,
                           linecolor=color, textcolor=color, linethickness=f'{width:g}', fontsize=str(size))
        self.items.append({'type': 'dim', 'x1': round(start[0], 3), 'y1': round(start[1], 3), 'x2': round(end[0], 3),
                           'y2': round(end[1], 3), 'tx': round(through[0], 3), 'ty': round(through[1], 3), 'text': shown,
                           'color': color, 'size': size})

    def sidecar(self):
        return {'width_in': self.width, 'height_in': self.height, 'title': self.title, 'items': self.items}


def canvas(parent, name, title, height_in, width_in=6.5):
    return Canvas(parent, name, title, width_in, height_in)


# ----------------------------------------------------------------------------- caches
CACHE_TAGS = ('expresult', 'num', 'bool', 'textvalue', 'error')


def _strip_cache(el):
    for child in list(el):
        if child.tag in CACHE_TAGS:
            el.remove(child)


def write_caches(report, engine, qualified_prefix=None):
    """Write the display caches Blockpad would show, from the independent engine (mirrors tasks/T008/verify_module.py)."""
    if qualified_prefix:
        engine.report = qualified_prefix.rstrip('.')
    count = 0
    for el in report.iter('dynexp'):
        formula = el.get('formula')
        if not formula or el.get('showresult') == 'False' or is_function_definition(formula):
            continue
        lhs, rhs = split_definition(formula)
        _strip_cache(el)
        if lhs is not None:
            engine.get(lhs)
            # a result-only definition shows the value alone (Blockpad caches it without the "= ", as the journal shows)
            prefix = '' if el.get('style') == 'Result only' else ' = '
            ET.SubElement(el, 'expresult').text = prefix + engine.display(lhs)
        else:
            ET.SubElement(el, 'expresult').text = engine.display_formula(formula)
        count += 1
    for el in report.iter('c', 'planecontainer', 'lineardim'):
        formula = el.get('formula')
        if not formula:
            continue
        value, unit = engine.evaluate_unit(formula)
        shown = engine.format_value(value, unit)
        _strip_cache(el)
        tag = 'bool' if isinstance(value, bool) else 'num' if isinstance(value, Q) else 'textvalue'
        ET.SubElement(el, tag).text = shown
        count += 1
    return count


def serialize(root, declaration=True):
    return ET.tostring(root, encoding='utf-8', xml_declaration=declaration, pretty_print=True)
