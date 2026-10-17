"""Shared Mathcad 15 XMCD worksheet writer.

Used by scripts/build_backwall_mathcad.py and scripts/build_cap_mathcad.py.

A worksheet is a list of Blocks built from a compact equation list (E, D, V, R, F, S, I, INPUTS, EQ, ROW,
H1, H2, P, N, BUL, FIG). Each expression is parsed once (`parse`, a Python-AST subset) and used two ways:
emitted as Mathcad worksheet XML (`x_expr`, `layout`, `document`) and evaluated with unit checking
(`ev`, `run`) so results can be compared with an independent model before the file is written.
`layout` places regions and `check_order` verifies Mathcad's evaluation order from the layout log.

Pagination: Mathcad prints 720 pt of worksheet per Letter page and never splits a region, so `layout` writes native
hard page breaks. Every unit (a text block, a figure with its caption, one pair of INPUTS, one ROW, one EQ item with its
result row and caption) is kept whole on one page of PAGE_H points; a heading stays with the unit after it. `check_pages`
(called by `document`) asserts that no region crosses a break or the page height and returns the points used per page;
`check_width` (document(check_width=True)) asserts that no region's estimated right edge passes RIGHT.
Layout notes: V(..., show=False) writes the definition without its result row; regions of a ROW that use nothing
defined to their left share one baseline; a unit divisor stays with its units (M*in**2/ft is M*(in**2/ft)).

    blocks =[H1('1. Inputs'), INPUTS('Geometry', [I('b', '12*in', 'width')]), EQ(E('A', 'b**2', 'in**2', 'area'))]
    env = run(blocks)                                    # unit-checked values
    text = document(blocks, title=..., description=..., seed=..., figures_dir=...)
"""
import ast
import base64
import math
import re
import uuid
from html import escape
from pathlib import Path

# ----------------------------------------------------------------------------- names
GREEK = {'gamma': 'γ', 'phi': 'ϕ', 'beta': 'β', 'theta': 'θ', 'delta': 'δ', 'eps': 'ε', 'lambda': 'λ',
         'Delta': 'Δ', 'Gamma': 'Γ', 'mu': 'μ', 'rho': 'ρ', 'alpha': 'α'}
SPECIAL = {'fc': ("f'", 'c'), 'fy': ('f', 'y'), 'Es': ('E', 's'), 'dT': ('Δ', 'T')}
UNITS = {'in', 'ft', 'kip', 'ksi', 'ksf', 'klf', 'psf', 'psi', 'deg', 'lbf'}
FUNCTIONS = {'max', 'min', 'sin', 'tan', 'round'}


def mc_name(name):
    """Mathcad base name and literal subscript for an equation-list identifier."""
    if name in SPECIAL:
        return SPECIAL[name]
    if name in UNITS or name in FUNCTIONS or '_' not in name:
        return GREEK.get(name, name), ''
    base, sub = name.split('_', 1)
    return GREEK.get(base, base), sub.replace('_', '.')


# ----------------------------------------------------------------------------- expression trees
def parse(src):
    # "in" (inch) is a Python keyword; parse it under an alias outside string literals.
    parts = re.split(r'("[^"]*")', src)
    src = ''.join(p if p.startswith('"') else re.sub(r'\bin\b', 'in_', p) for p in parts)
    return _unit_fractions(_tree(ast.parse(src, mode='eval').body))


def _units_only(t):
    """A product, quotient or power of units and plain numbers."""
    if t[0] == 'id':
        return t[1] in UNITS
    if t[0] == 'num':
        return True
    return t[0] == 'bin' and t[1] in ('*', '/', '**') and _units_only(t[2]) and _units_only(t[3])


def _is_matrix(t):
    return t[0] == 'call' and (t[1] in ('row', 'col') or (t[1] == 'tr' and _is_matrix(t[2][0])))


def _unit_fractions(t):
    """Keep a unit divisor with its units: M*in**2/ft is M*(in**2/ft), so the matrix literal is never the numerator
    of a stacked fraction (which would be as tall as the matrix again)."""
    if t[0] == 'bin':
        t = (t[0], t[1], _unit_fractions(t[2]), _unit_fractions(t[3]))
        if t[1] == '/' and _units_only(t[3]):
            num = t[2]
            if _is_matrix(num):
                return ('bin', '*', num, ('bin', '/', ('num', 1.0), t[3]))
            if num[0] == 'bin' and num[1] == '*' and _units_only(num[3]) and not _units_only(num[2]) and _has_matrix(num[2]):
                return ('bin', '*', num[2], ('bin', '/', num[3], t[3]))
        return t
    if t[0] == 'neg':
        return ('neg', _unit_fractions(t[1]))
    if t[0] == 'cmp':
        return ('cmp', t[1], _unit_fractions(t[2]), _unit_fractions(t[3]))
    if t[0] in ('and', 'or'):
        return (t[0], _unit_fractions(t[1]), _unit_fractions(t[2]))
    if t[0] == 'idx':
        return ('idx', _unit_fractions(t[1]), [_unit_fractions(i) for i in t[2]])
    if t[0] == 'call':
        return ('call', t[1], [_unit_fractions(a) for a in t[2]])
    return t        # num, str, id


def _has_matrix(t):
    """A matrix literal is a factor of the product t."""
    return _is_matrix(t) or (t[0] == 'bin' and t[1] == '*' and (_has_matrix(t[2]) or _has_matrix(t[3])))


def _tree(n):
    if isinstance(n, ast.Constant):
        return ('str', n.value) if isinstance(n.value, str) else ('num', float(n.value))
    if isinstance(n, ast.Name):
        return ('id', 'in' if n.id == 'in_' else n.id)
    if isinstance(n, ast.BinOp):
        op = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.Pow: '**'}[type(n.op)]
        return ('bin', op, _tree(n.left), _tree(n.right))
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
        return ('neg', _tree(n.operand))
    if isinstance(n, ast.Compare):
        assert len(n.ops) == 1
        op = {ast.Gt: '>', ast.Lt: '<', ast.GtE: '>=', ast.LtE: '<=', ast.Eq: '=='}[type(n.ops[0])]
        return ('cmp', op, _tree(n.left), _tree(n.comparators[0]))
    if isinstance(n, ast.BoolOp) and isinstance(n.op, (ast.And, ast.Or)):
        tag = 'and' if isinstance(n.op, ast.And) else 'or'
        out = _tree(n.values[0])
        for v in n.values[1:]:
            out = (tag, out, _tree(v))
        return out
    if isinstance(n, ast.Call):
        return ('call', n.func.id, [_tree(a) for a in n.args])
    if isinstance(n, ast.Subscript):
        index = n.slice.elts if isinstance(n.slice, ast.Tuple) else [n.slice]
        return ('idx', _tree(n.value), [_tree(i) for i in index])
    raise ValueError(f'unsupported syntax: {ast.dump(n)}')


def names_in(t, out=None):
    out = set() if out is None else out
    if t[0] == 'id':
        out.add(t[1])
    for part in t[1:]:
        if isinstance(part, tuple):
            names_in(part, out)
        elif isinstance(part, list):
            for p in part:
                names_in(p, out)
    return out


# ----------------------------------------------------------------------------- unit-checked evaluation
class UnitError(ValueError):
    pass


class U:
    """A number with (length, force) dimensions; inch and kip are the base units."""
    __slots__ = ('v', 'd')

    def __init__(self, v, d=(0.0, 0.0)):
        self.v, self.d = float(v), (float(d[0]), float(d[1]))

    def _same(self, o, what):
        if abs(self.d[0] - o.d[0]) > 1e-9 or abs(self.d[1] - o.d[1]) > 1e-9:
            raise UnitError(f'{what}: incompatible units {self.d} and {o.d}')

    def __repr__(self):
        return f'U({self.v:g}, {self.d})'


BASE_UNITS = {'in': U(1, (1, 0)), 'ft': U(12, (1, 0)), 'kip': U(1, (0, 1)), 'ksi': U(1, (-2, 1)),
              'ksf': U(1 / 144, (-2, 1)), 'klf': U(1 / 12, (-1, 1)), 'psf': U(0.001 / 144, (-2, 1)),
              'psi': U(0.001, (-2, 1)), 'deg': U(math.pi / 180), 'lbf': U(0.001, (0, 1))}


def _arith(op, a, b):
    if isinstance(a, list) and isinstance(b, list):
        if op in '*/':
            raise UnitError('vector times or over vector is a dot product in Mathcad; index the elements instead')
        if len(a) != len(b):
            raise UnitError('vector lengths differ')
        return [_arith(op, x, y) for x, y in zip(a, b)]
    if isinstance(a, list):
        if op in '+-':
            raise UnitError('scalar added to a vector')
        return [_arith(op, x, b) for x in a]
    if isinstance(b, list):
        if op in '+-/':
            raise UnitError('vector in a scalar position')
        return [_arith(op, a, y) for y in b]
    if op == '+':
        a._same(b, '+'); return U(a.v + b.v, a.d)
    if op == '-':
        a._same(b, '-'); return U(a.v - b.v, a.d)
    if op == '*':
        return U(a.v * b.v, (a.d[0] + b.d[0], a.d[1] + b.d[1]))
    if op == '/':
        return U(a.v / b.v, (a.d[0] - b.d[0], a.d[1] - b.d[1]))
    if op == '**':
        if b.d != (0.0, 0.0):
            raise UnitError('dimensioned exponent')
        return U(a.v ** b.v, (a.d[0] * b.v, a.d[1] * b.v))
    raise ValueError(op)


def _flat(x):
    if isinstance(x, list):
        return [y for v in x for y in _flat(v)]
    if isinstance(x, dict):
        return list(x.values())
    return [x]


def ev(t, env):
    kind = t[0]
    if kind == 'num':
        return U(t[1])
    if kind == 'str':
        return t[1]
    if kind == 'id':
        if t[1] in env:
            return env[t[1]]
        if t[1] in BASE_UNITS:
            return BASE_UNITS[t[1]]
        raise NameError(f'{t[1]} is used before it is defined')
    if kind == 'bin':
        return _arith(t[1], ev(t[2], env), ev(t[3], env))
    if kind == 'neg':
        x = ev(t[1], env)
        return [U(-y.v, y.d) for y in x] if isinstance(x, list) else U(-x.v, x.d)
    if kind == 'cmp':
        a, b = ev(t[2], env), ev(t[3], env)
        a._same(b, t[1])
        return {'>': a.v > b.v, '<': a.v < b.v, '>=': a.v >= b.v, '<=': a.v <= b.v, '==': a.v == b.v}[t[1]]
    if kind == 'and':
        return bool(ev(t[1], env)) and bool(ev(t[2], env))
    if kind == 'or':
        return bool(ev(t[1], env)) or bool(ev(t[2], env))
    if kind == 'idx':
        base = ev(t[1], env)
        index = [int(round(ev(i, env).v)) for i in t[2]]
        return base[index[0]] if len(index) == 1 else base[tuple(index)]
    if kind == 'call':
        f, args = t[1], t[2]
        if f == 'IF':
            return ev(args[1], env) if ev(args[0], env) else ev(args[2], env)
        vals = [ev(a, env) for a in args]
        if f in ('row', 'col', 'tr'):
            return vals if f != 'tr' else vals[0]
        if f in ('max', 'min'):
            items = [y for v in vals for y in _flat(v)]
            for y in items[1:]:
                items[0]._same(y, f)
            pick = (max if f == 'max' else min)(items, key=lambda y: y.v)
            return U(pick.v, items[0].d)
        if f == 'sqrt':
            x = vals[0]
            return U(math.sqrt(x.v), (x.d[0] / 2, x.d[1] / 2))
        if f == 'abs':
            if isinstance(vals[0], list):
                raise UnitError('|vector| is a magnitude in Mathcad')
            return U(abs(vals[0].v), vals[0].d)
        if f == 'sin':
            if vals[0].d != (0.0, 0.0):
                raise UnitError('sin of a dimensioned value')
            return U(math.sin(vals[0].v))
        if f == 'tan':
            if vals[0].d != (0.0, 0.0):
                raise UnitError('tan of a dimensioned value')
            return U(math.tan(vals[0].v))
        if f == 'round':
            if len(vals) != 2:
                raise ValueError('round takes a value and a number of decimal places')
            if vals[0].d != (0.0, 0.0) or vals[1].d != (0.0, 0.0):
                raise UnitError('round of a dimensioned value')
            if vals[1].v != int(vals[1].v):
                raise ValueError('round: the number of decimal places must be an integer')
            return U(round(vals[0].v, int(vals[1].v)))
        if f in env and callable(env[f]):
            return env[f](*vals)
        raise NameError(f'unknown function {f}')
    raise ValueError(kind)


# ----------------------------------------------------------------------------- Mathcad XML
ML = 'http://schemas.mathsoft.com/math30'
OPS = {'+': 'plus', '-': 'minus', '*': 'mult', '/': 'div', '**': 'pow'}
CMP = {'>': 'greaterThan', '<': 'lessThan', '>=': 'greaterOrEqual', '<=': 'lessOrEqual', '==': 'equal'}


def _real(v):
    text = repr(float(v))
    return text[:-2] if text.endswith('.0') else text


def x_id(name):
    base, sub = mc_name(name)
    sub_attr = f' subscript="{escape(sub, quote=True)}"' if sub else ''
    return f'<ml:id xml:space="preserve"{sub_attr}>{escape(base)}</ml:id>'


def _atomic(t):
    return t[0] in ('num', 'id', 'idx', 'call', 'str') and not (t[0] == 'call' and t[1] == 'tr')


def _wrap(t, parent, side):
    """Parentheses Mathcad needs to display the tree as it evaluates."""
    xml = x_expr(t)
    need = False
    if t[0] == 'bin' and t[1] in '+-':
        need = parent in ('*', 'neg', '**') or (parent == '-' and side == 'right') or (parent == '+' and side == 'right')
    elif t[0] == 'neg':
        need = parent in ('*', '**') or (parent in '+-' and side == 'right')
    elif t[0] == 'bin' and t[1] in '*/':
        need = parent == '**' and side == 'left'
    elif parent == '**' and side == 'left' and not _atomic(t):
        need = True
    elif t[0] == 'num' and t[1] < 0:
        need = parent in ('*', '**')
    return f'<ml:parens>{xml}</ml:parens>' if need else xml


def x_expr(t):
    kind = t[0]
    if kind == 'num':
        if t[1] < 0:
            return f'<ml:apply><ml:neg/><ml:real>{_real(-t[1])}</ml:real></ml:apply>'
        return f'<ml:real>{_real(t[1])}</ml:real>'
    if kind == 'str':
        return f'<ml:str xml:space="preserve">{escape(t[1])}</ml:str>'
    if kind == 'id':
        return x_id(t[1])
    if kind == 'bin':
        op = t[1]
        if op == '/':
            return f'<ml:apply><ml:div/>{x_expr(t[2])}{x_expr(t[3])}</ml:apply>'
        if op == '**':
            return f'<ml:apply><ml:pow/>{_wrap(t[2], "**", "left")}{x_expr(t[3])}</ml:apply>'
        return f'<ml:apply><ml:{OPS[op]}/>{_wrap(t[2], op, "left")}{_wrap(t[3], op, "right")}</ml:apply>'
    if kind == 'neg':
        return f'<ml:apply><ml:neg/>{_wrap(t[1], "neg", "right")}</ml:apply>'
    if kind == 'cmp':
        return f'<ml:apply><ml:{CMP[t[1]]}/>{x_expr(t[2])}{x_expr(t[3])}</ml:apply>'
    if kind == 'and':
        return f'<ml:apply><ml:and/><ml:parens>{x_expr(t[1])}</ml:parens><ml:parens>{x_expr(t[2])}</ml:parens></ml:apply>'
    if kind == 'or':
        return f'<ml:apply><ml:or/><ml:parens>{x_expr(t[1])}</ml:parens><ml:parens>{x_expr(t[2])}</ml:parens></ml:apply>'
    if kind == 'idx':
        index = t[2]
        inner = x_expr(index[0]) if len(index) == 1 else '<ml:sequence>' + ''.join(x_expr(i) for i in index) + '</ml:sequence>'
        return f'<ml:apply><ml:indexer/>{x_expr(t[1])}{inner}</ml:apply>'
    if kind == 'call':
        f, args = t[1], t[2]
        if f == 'sqrt':
            return f'<ml:apply><ml:sqrt/>{x_expr(args[0])}</ml:apply>'
        if f == 'abs':
            return f'<ml:apply><ml:absval/>{x_expr(args[0])}</ml:apply>'
        if f == 'tr':
            return f'<ml:apply><ml:transpose/>{_wrap(args[0], "**", "left")}</ml:apply>'
        if f in ('row', 'col'):
            rows, cols = (1, len(args)) if f == 'row' else (len(args), 1)
            return f'<ml:matrix rows="{rows}" cols="{cols}">' + ''.join(x_expr(a) for a in args) + '</ml:matrix>'
        name = 'if' if f == 'IF' else f
        head = f'<ml:id xml:space="preserve">{escape(name)}</ml:id>' if name in ('if', 'max', 'min', 'sin', 'tan', 'round') else x_id(name)
        body = x_expr(args[0]) if len(args) == 1 else '<ml:sequence>' + ''.join(x_expr(a) for a in args) + '</ml:sequence>'
        return f'<ml:apply>{head}{body}</ml:apply>'
    raise ValueError(kind)


# ----------------------------------------------------------------------------- size estimates (points)
CW = 5.7


def size(t):
    """(width, ascent, descent) of a rendered expression, deliberately generous."""
    kind = t[0]
    if kind == 'num':
        return len(_real(abs(t[1]))) * CW + (7 if t[1] < 0 else 0), 9, 3
    if kind == 'str':
        return len(t[1]) * 5.3 + 12, 9, 3
    if kind == 'id':
        base, sub = mc_name(t[1])
        return len(base) * CW + len(sub) * CW * 0.8 + 2, 9, 6 if sub else 3
    if kind == 'bin':
        a, b = size(t[2]), size(t[3])
        if t[1] == '/':
            return max(a[0], b[0]) + 8, a[1] + a[2] + 3, b[1] + b[2] + 3
        if t[1] == '**':
            return a[0] + b[0] * 0.8 + 4, max(a[1], b[1] * 0.8 + 6), a[2]
        extra = 16 if t[1] in '+-' else 7
        w = a[0] + b[0] + extra + (10 if t[1] in '*-' and t[3][0] in ('bin', 'neg') else 0)
        return w, max(a[1], b[1]), max(a[2], b[2])
    if kind == 'neg':
        a = size(t[1]); return a[0] + 9, a[1], a[2]
    if kind == 'cmp':
        a, b = size(t[2]), size(t[3]); return a[0] + b[0] + 16, max(a[1], b[1]), max(a[2], b[2])
    if kind in ('and', 'or'):
        a, b = size(t[1]), size(t[2]); return a[0] + b[0] + 34, max(a[1], b[1]), max(a[2], b[2])
    if kind == 'idx':
        a = size(t[1]); w = sum(size(i)[0] for i in t[2]) * 0.8 + 6 * (len(t[2]) - 1)
        return a[0] + w + 3, a[1], max(a[2], 7)
    if kind == 'call':
        f, args = t[1], t[2]
        sizes = [size(a) for a in args]
        if f in ('row', 'col'):
            if f == 'row':
                return sum(s[0] for s in sizes) + 12 * len(args) + 12, 10, 5
            h = 15 * len(args)
            return max(s[0] for s in sizes) + 18, h / 2 + 3, h / 2 + 3
        if f == 'tr':
            return sizes[0][0] + 9, sizes[0][1] + 3, sizes[0][2]
        if f == 'sqrt':
            return sizes[0][0] + 14, sizes[0][1] + 4, sizes[0][2]
        if f == 'abs':
            return sizes[0][0] + 8, sizes[0][1] + 1, sizes[0][2] + 1
        name = 'if' if f == 'IF' else f
        w = len(mc_name(name)[0]) * CW + 12 + sum(s[0] for s in sizes) + 8 * (len(args) - 1)
        return w, max(s[1] for s in sizes), max(s[2] for s in sizes)
    raise ValueError(kind)


# ----------------------------------------------------------------------------- the worksheet
# Result widths (pt) for row displays of named string vectors; generators may add entries.
RESULT_WIDTHS = {'Combo': 330, 'Member': 330}


class Item:
    def __init__(self, kind, name=None, expr=None, unit=None, caption='', index=None, params=None, show=True, key=False,
                 rows=None, width=None):
        self.kind, self.name, self.expr, self.unit, self.caption = kind, name, expr, unit, caption
        self.index, self.params, self.show, self.key = index, params, show, key
        self.rows, self.width = rows, width      # layout hints: result matrix rows, region width (pt)
        self.tree = parse(expr) if expr is not None and kind != 'range' else None




def I(name, expr, caption):                      # input (highlighted)
    return Item('input', name, expr, caption=caption)


def E(name, expr, unit=None, caption='', key=False):   # define and show the result
    return Item('eq', name, expr, unit, caption, key=key)


def D(name, expr, caption=''):                   # define without a result (vectors, labels)
    return Item('def', name, expr, caption=caption)


def V(name, index, expr, unit=None, caption='', key=False, show=True):
    """Element-wise definition over a range; show=True (default, single range variable) adds its result as a row."""
    return Item('idef', name, expr, unit, caption, index=index, key=key, show=show)


def R(name, lo, hi, caption=''):
    return Item('range', name, f'{lo}..{hi}', caption=caption, index=(lo, hi))


def F(name, params, expr, caption=''):
    return Item('fdef', name, expr, caption=caption, params=params)


def S(expr, unit=None, caption='', key=False, rows=None, width=None):   # show a result (vectors as a row)
    return Item('show', None, expr, unit, caption, key=key, rows=rows, width=width)


class Block:
    def __init__(self, kind, payload, **opts):
        self.kind, self.payload, self.opts = kind, payload, opts


def H1(text): return Block('h1', text)
def H2(text): return Block('h2', text)
def P(text): return Block('p', text)
def N(text): return Block('note', text)
def BUL(items): return Block('bullets', items)
def FIG(name, caption, width=540, data=None):
    """A picture with its caption: PNG `data` bytes when given, else the file figures_dir/<name>.png."""
    return Block('fig', name, caption=caption, width=width, data=data)
def INPUTS(title, items): return Block('inputs', items, title=title)
def EQ(*items): return Block('eqs', list(items))
def ROW(*items): return Block('row', list(items))


# ----------------------------------------------------------------------------- evaluating a worksheet
def run(blocks):
    """Evaluate every definition in worksheet order; returns the environment."""
    env = {}
    for block in blocks:
        items = block.payload if block.kind in ('eqs', 'row', 'inputs') else []
        for item in items:
            if item.kind == 'range':
                lo, hi = item.index
                env[item.name] = list(range(lo, hi + 1))
            elif item.kind in ('input', 'eq', 'def'):
                env[item.name] = ev(item.tree, env)
            elif item.kind == 'idef':
                index = item.index if isinstance(item.index, tuple) else (item.index,)
                if len(index) == 1:
                    values = {}
                    for i in env[index[0]]:
                        values[i] = ev(item.tree, {**env, index[0]: U(i)})
                    first = next(iter(values.values()))
                    size_ = max(values) + 1
                    env[item.name] = [values.get(i, U(0, first.d)) for i in range(size_)]
                else:
                    a, b = index
                    env[item.name] = {(i, k): ev(item.tree, {**env, a: U(i), b: U(k)}) for i in env[a] for k in env[b]}
            elif item.kind == 'fdef':
                env[item.name] = _function(item, env)
            elif item.kind == 'show':
                ev(item.tree, env)
    return env


def _function(item, env):
    def call(*args):
        local = dict(env)
        local.update(zip(item.params, args))
        return ev(item.tree, local)
    return call


def _to(value, unit):
    u = BASE_UNITS['in'] if unit is None else ev(parse(unit), {})
    if unit is None:
        return value.v
    value._same(u, f'display unit {unit}')
    return value.v / u.v


def check_names(blocks):
    seen = {}
    for block in blocks:
        for item in (block.payload if block.kind in ('eqs', 'row', 'inputs') else []):
            if item.name:
                key = mc_name(item.name)
                if key in seen and seen[key] != item.name:
                    raise ValueError(f'{item.name} and {seen[key]} display as the same Mathcad name')
                seen[key] = item.name


# ----------------------------------------------------------------------------- worksheet XML
LEFT, RIGHT = 18, 590
HL_INPUT, HL_KEY = '#ffff80', '#ccffcc'


ORDER_GAP = 5.0     # points by which a right-hand region sits below its left-hand neighbour
BUILTINS = UNITS | FUNCTIONS | {'IF', 'row', 'col', 'tr', 'sqrt', 'abs'}


def uses_in(t, out=None):
    """Variables and user functions an expression refers to."""
    out = set() if out is None else out
    if t[0] == 'id':
        out.add(t[1])
    if t[0] == 'call' and t[1] not in BUILTINS:
        out.add(t[1])
    for part in t[1:]:
        if isinstance(part, tuple):
            uses_in(part, out)
        elif isinstance(part, list):
            for p in part:
                uses_in(p, out)
    return out


def defines_of(item):
    return {item.name} if item.kind in ('input', 'eq', 'def', 'idef', 'range', 'fdef') else set()


def uses_of(item):
    if item.kind == 'range':
        return set()
    names = uses_in(item.tree) - BUILTINS
    if item.kind == 'fdef':
        names -= set(item.params)
    if item.kind == 'idef':
        names |= set(item.index if isinstance(item.index, tuple) else (item.index,))
    return names


def check_order(log):
    """Every region must follow the regions it depends on, ordered by top edge or by baseline."""
    problems = []
    for key in ('top', 'align'):
        defined = set()
        for region in sorted(log, key=lambda r: (round(r[key], 3), r['left'])):
            missing = region['uses'] - defined
            if missing:
                problems.append(f'by {key}: {region["label"]} is evaluated before {sorted(missing)}')
            defined |= region['defines']
    if problems:
        raise AssertionError('Mathcad evaluation order:\n  ' + '\n  '.join(problems))


PAGE_H = 690.0          # worksheet height used per page: Mathcad prints 720 pt (792 less 36 + 36 margins) and never splits a region
PAGE_BREAK_H = 6.0      # height of a hard page-break region
MIN_PAGE_FILL = 40.0    # a page holding less than this gets a unit that does not fit anyway
HEADING_RESERVE = 70.0  # room a trailing heading asks for when nothing follows it


class Writer:
    """Places regions on a single column of pages; units that do not fit the rest of a page start the next one."""

    def __init__(self):
        self.regions, self.items, self.y, self.next_id, self.log = [], [], 18.0, 1, []
        self.page_top = 0.0
        self.breaks = []        # top of every hard page break
        self.placed = []        # every text, math and picture region: label, kind, left, top, width, height

    def _region(self, left, top, width, height, body, highlight=None, border=False, align_y=None, kind='math', label=''):
        rid = self.next_id; self.next_id += 1
        bg = highlight or 'inherit'
        self.regions.append(
            f'<region region-id="{rid}" left="{left:.2f}" top="{top:.2f}" width="{width:.2f}" height="{height:.2f}" '
            f'align-x="{left:.2f}" align-y="{(align_y if align_y is not None else top + 10):.2f}" show-border="{str(border).lower()}" '
            f'show-highlight="{str(bool(highlight)).lower()}" is-protected="true" z-order="0" background-color="{bg}" tag="">\n'
            f'{body}\n</region>')
        self.placed.append(dict(kind=kind, label=label, left=left, top=top, width=width, height=height))

    # pages
    def mark(self):
        return (len(self.regions), len(self.items), len(self.log), len(self.placed), len(self.breaks), self.next_id,
                self.y, self.page_top)

    def rewind(self, mark):
        n_regions, n_items, n_log, n_placed, n_breaks, self.next_id, self.y, self.page_top = mark
        del self.regions[n_regions:], self.items[n_items:], self.log[n_log:], self.placed[n_placed:], self.breaks[n_breaks:]

    def page_break(self):
        """Hard page break at the cursor; the cursor moves to the top of the new page."""
        top = self.y - 3
        rid = self.next_id; self.next_id += 1
        self.regions.append(
            f'<region region-id="{rid}" left="0" top="{top:.2f}" width="6000" height="{PAGE_BREAK_H:g}" align-x="0" '
            f'align-y="{top:.2f}" show-border="false" show-highlight="false" is-protected="true" z-order="0" '
            f'background-color="inherit" tag="">\n<pageBreak/>\n</region>')
        self.breaks.append(top)
        self.page_top = top + PAGE_BREAK_H
        self.y = self.page_top + 6

    def place(self, units, reserve=0.0):
        """Place a group of units (callables that write at the cursor) on one page.

        The group is written, its height measured, and written again after a page break when it does not fit
        what is left of the page (a page that holds almost nothing keeps it regardless)."""
        mark, start = self.mark(), self.y
        for unit in units:
            unit()
        height = self.y - start + reserve
        if start + height > self.page_top + PAGE_H and start - self.page_top > MIN_PAGE_FILL:
            self.rewind(mark)
            self.page_break()
            for unit in units:
                unit()

    def page_fills(self):
        """Height used on each page (points below the page top)."""
        tops = [0.0] + [b + PAGE_BREAK_H for b in self.breaks]
        fills = [0.0] * len(tops)
        for r in self.placed:
            page = max(i for i, t in enumerate(tops) if r['top'] >= t - 0.01)
            fills[page] = max(fills[page], r['top'] + r['height'] - tops[page])
        return fills

    def check_pages(self):
        """No region crosses a page break or the page height (a region taller than a page excepted); returns page fills."""
        tops = [0.0] + [b + PAGE_BREAK_H for b in self.breaks]
        problems = []
        for r in self.placed:
            top, bottom = r['top'], r['top'] + r['height']
            page = max(i for i, t in enumerate(tops) if top >= t - 0.01)
            if any(top < b < bottom for b in self.breaks):
                problems.append(f'{r["kind"]} {r["label"]!r} at {top:.0f} crosses a page break')
            elif bottom - tops[page] > PAGE_H + 0.01 and r['height'] <= PAGE_H:
                problems.append(f'{r["kind"]} {r["label"]!r} at {top:.0f} ends {bottom - tops[page]:.0f} pt down page {page + 1} (limit {PAGE_H:g})')
        if problems:
            raise AssertionError('Page layout:\n  ' + '\n  '.join(problems))
        return self.page_fills()

    def check_width(self, limit=None):
        """No region reaches past the right edge of the text area."""
        limit = RIGHT if limit is None else limit
        wide = [f'{r["kind"]} {r["label"]!r} at {r["top"]:.0f}: right edge {r["left"] + r["width"]:.0f}'
                for r in self.placed if r['left'] + r['width'] > limit + 0.01]
        if wide:
            raise AssertionError(f'Regions wider than the text area (right edge {limit:g}):\n  ' + '\n  '.join(wide))

    # text
    @staticmethod
    def text_height(paragraphs, font=10.0, line=13.0, width=None, left=LEFT):
        width = width or (RIGHT - left)
        per_line = max(10, int(width / (font * 0.56)))
        return sum(max(1, math.ceil(len(t) / per_line)) for t in paragraphs) * line + 4

    def text(self, paragraphs, style='Normal', left=LEFT, width=None, top=None, font=10.0, line=13.0):
        width = width or (RIGHT - left)
        height = self.text_height(paragraphs, font, line, width)
        body = ''.join(f'<p style="{style}" margin-left="inherit" margin-right="inherit" text-indent="inherit" '
                       f'text-align="inherit" list-style-type="inherit" tabs="inherit">{escape(t)}</p>' for t in paragraphs)
        top = self.y if top is None else top
        self._region(left, top, width, height,
                     f'<text use-page-width="false" push-down="false" lock-width="true">{body}</text>', align_y=top + line - 3,
                     kind='text', label=paragraphs[0][:40])
        return height

    def block_text(self, paragraphs, style='Normal', gap=6, **kw):
        h = self.text(paragraphs, style, **kw)
        self.y += h + gap

    # math
    def measure(self, item):
        """(width, height, anchor) of a math region; anchor = baseline below the region top."""
        if item.kind == 'range':
            w, asc, desc = len(item.name) * CW + 60, 9, 4
        elif item.kind == 'fdef':
            w0, asc, desc = size(item.tree)
            w = w0 + len(item.name) * CW + 40 + 12 * len(item.params)
        elif item.kind == 'show':
            w0, asc, desc = size(item.tree)
            w = w0 + 20 + self._result_width(item)
        else:
            lw = size(('id', item.name))[0] + (14 if item.kind == 'idef' else 0)
            w0, asc, desc = size(item.tree)
            w = lw + 18 + w0 + (20 + self._result_width(item) if item.kind == 'eq' else 0)
        if item.rows:                      # a column result is centred on the expression baseline
            asc = max(asc, item.rows * 7.5 + 3)
            desc = max(desc, item.rows * 7.5 + 3)
        width = item.width if item.width else w * 1.08 + 6
        return width, max(16.0, asc + desc + 5), asc + 2

    @staticmethod
    def _inner(item):
        if item.kind == 'range':
            lo, hi = item.index
            return (f'<ml:define xmlns:ml="{ML}">{x_id(item.name)}<ml:range><ml:real>{lo}</ml:real>'
                    f'<ml:real>{hi}</ml:real></ml:range></ml:define>')
        if item.kind == 'fdef':
            head = (f'<ml:function>{x_id(item.name)}<ml:boundVars>' + ''.join(x_id(p) for p in item.params)
                    + '</ml:boundVars></ml:function>')
            return f'<ml:define xmlns:ml="{ML}">{head}{x_expr(item.tree)}</ml:define>'
        if item.kind == 'show':
            return (f'<ml:eval placeholderMultiplicationStyle="default" xmlns:ml="{ML}">{x_expr(item.tree)}'
                    f'{Writer._override(item.unit)}</ml:eval>')
        lhs = x_id(item.name)
        if item.kind == 'idef':
            index = item.index if isinstance(item.index, tuple) else (item.index,)
            idx = x_id(index[0]) if len(index) == 1 else '<ml:sequence>' + ''.join(x_id(i) for i in index) + '</ml:sequence>'
            lhs = f'<ml:apply><ml:indexer/>{lhs}{idx}</ml:apply>'
        rhs = x_expr(item.tree)
        if item.kind == 'eq':
            rhs = f'<ml:eval placeholderMultiplicationStyle="default">{rhs}{Writer._override(item.unit)}</ml:eval>'
        return f'<ml:define xmlns:ml="{ML}">{lhs}{rhs}</ml:define>'

    def math(self, item, left, top):
        """Write one math region; returns (width, height, anchor)."""
        w, height, anchor = self.measure(item)
        highlight = HL_INPUT if item.kind == 'input' else (HL_KEY if item.key else None)
        precision = ('<resultFormat numeric-only="false"><decimal precision="3" show-trailing-zeros="true" radix="dec" '
                     'complex-threshold="10" zero-threshold="15" imaginary-value="i"/><matrix display-style="auto" '
                     'expand-nested-arrays="false"/><unit format-units="true" simplify-units="true" fractional-unit-exponent="false"/>'
                     '</resultFormat>') if item.kind in ('eq', 'show') else ''
        body = f'<math optimize="false" disable-calc="false">{self._inner(item)}{precision}</math>'
        self._region(left, top, w, height, body, highlight=highlight, border=item.key, align_y=top + anchor,
                     kind='math', label=item.name or item.expr)
        self.log.append(dict(top=top, align=top + anchor, left=left, defines=defines_of(item), uses=uses_of(item),
                             label=item.name or item.expr))
        return w, height, anchor

    def right_of(self, prev_top, prev_anchor, item):
        """Top for a region placed to the right of another so that both its top edge and its
        baseline lie lower: Mathcad then evaluates it afterwards whichever reference it uses."""
        return prev_top + max(ORDER_GAP, prev_anchor - self.measure(item)[2] + ORDER_GAP)

    @staticmethod
    def _override(unit):
        return f'<ml:unitOverride>{x_expr(parse(unit))}</ml:unitOverride>' if unit else ''

    @staticmethod
    def _result_width(item):
        tree = item.tree
        if tree[0] == 'call' and tree[1] == 'tr':
            inner = tree[2][0]
            if inner[0] == 'id' and inner[1] in RESULT_WIDTHS:
                return RESULT_WIDTHS[inner[1]]
            return 5 * 52 + 50
        if item.name == 'Status':
            return 200
        return 90 + (len(item.unit) * 5 if item.unit else 0)

    def caption(self, text, left, top, width):
        """Small note beside a region; returns the height it occupies."""
        if text and width > 60:
            return self.text([text], 'Note', left=left, width=width, top=top + 2, font=9, line=11) + 2
        return 0.0

    # units: each writes one piece at the cursor and moves it down
    def row(self, items):
        """Regions side by side. Those that use nothing defined earlier in the row share one baseline; a region
        that uses a definition to its left sits lower than it (top edge and baseline), so Mathcad evaluates it after."""
        y0 = self.y
        anchors = [self.measure(item)[2] for item in items]
        base = max(anchors)
        x, bottom, where = LEFT, y0, {}                      # where: name -> (top, anchor) of the region defining it
        for item, anchor0 in zip(items, anchors):
            top = y0 + base - anchor0
            for name in uses_of(item) & where.keys():
                top = max(top, self.right_of(*where[name], item))
            mw, mh, anchor = self.math(item, x, top)
            for name in defines_of(item):
                where[name] = (top, anchor)
            bottom = max(bottom, top + mh); x += mw + 18
        self.y = bottom + 8

    def equation(self, item):
        """One definition with its result row (element-wise definitions) and caption."""
        if item.kind == 'idef' and isinstance(item.index, str) and item.show:
            show = Item('show', None, f'tr({item.name})', item.unit)
            mw, mh, ma = self.math(item, LEFT, self.y)
            sw_est = (size(show.tree)[0] + 20 + self._result_width(show)) * 1.08 + 6
            if LEFT + mw + 16 + sw_est <= RIGHT:
                left, top = LEFT + mw + 16, self.right_of(self.y, ma, show)
            else:                       # result row on its own line, indented
                left, top = LEFT + 36, self.y + mh + 3
            sw, sh, _ = self.math(show, left, top)
            room = RIGHT - (left + sw + 8)
            bottom = max(top + sh, self.y + mh)
            if item.caption and room >= 110:
                bottom = max(bottom, top + self.caption(item.caption, left + sw + 8, top, room))
            elif item.caption:
                bottom += self.caption(item.caption, LEFT + 36, bottom - 1, RIGHT - LEFT - 36)
            self.y = max(self.y + mh, bottom) + 6
            return
        left = LEFT
        mw, mh, _ = self.math(item, left, self.y)
        room = RIGHT - (left + mw + 10)
        if item.caption and room >= 120:
            ch = self.caption(item.caption, left + mw + 10, self.y, room)
            self.y += max(mh, ch) + 6
        elif item.caption:
            self.y += mh + 1
            self.y += self.caption(item.caption, LEFT + 24, self.y - 2, RIGHT - LEFT - 24) + 4
        else:
            self.y += mh + 6

    def input_pair(self, pair, last=False):
        half = (RIGHT - LEFT) / 2
        heights = []
        for col, item in enumerate(pair):
            left = LEFT + col * half
            mw, mh, _ = self.math(item, left, self.y)
            ch = self.caption(item.caption, left + max(mw, 92) + 6, self.y, half - max(mw, 92) - 10)
            heights.append(max(mh, ch))
        self.y += max(heights) + 4 + (6 if last else 0)

    def figure(self, name, caption, width, figures_dir, data=None):
        if data is None:
            data = (Path(figures_dir) / f'{name}.png').read_bytes()
        px_w, px_h = _png_size(data)
        height = width * px_h / px_w
        item_id = len(self.items) + 1
        self.items.append((item_id, data))
        self._region((LEFT + RIGHT - width) / 2, self.y, width + 2, height + 2,
                     f'<picture><png item-idref="{item_id}" display-width="{width:.2f}" display-height="{height:.2f}"/></picture>',
                     align_y=self.y, kind='picture', label=name)
        self.y += height + 8
        self.block_text([caption], 'Note', font=9, line=11.5, gap=8)


def layout(blocks, figures_dir):
    """Write every block; headings stay with the unit that follows them, and no unit is split across a page."""
    w = Writer()
    group = []

    def add(unit, heading=False):
        group.append(unit)
        if not heading:
            w.place(list(group))
            group.clear()

    def text_unit(paragraphs, style, pre=0.0, **kw):
        def unit():
            w.y += pre
            w.block_text(paragraphs, style, **kw)
        return unit

    for block in blocks:
        kind = block.kind
        if kind == 'title':
            add(text_unit([block.payload], 'Title', font=16, line=22, gap=8))
        elif kind == 'h1':
            add(text_unit([block.payload], 'Heading 1', pre=10, font=13, line=18, gap=6), heading=True)
        elif kind == 'h2':
            add(text_unit([block.payload], 'Heading 2', pre=4, font=11, line=15, gap=4), heading=True)
        elif kind == 'p':
            add(text_unit([block.payload], 'Normal', gap=6))
        elif kind == 'note':
            add(text_unit([block.payload], 'Note', font=9, line=11.5, gap=6))
        elif kind == 'bullets':
            add(text_unit(['• ' + t for t in block.payload], 'List', gap=8))
        elif kind == 'fig':
            add(lambda b=block: w.figure(b.payload, b.opts['caption'], b.opts['width'], figures_dir, b.opts.get('data')))
        elif kind == 'inputs':
            add(text_unit([block.opts['title']], 'Heading 2', font=11, line=15, gap=3), heading=True)
            items = block.payload
            for n in range(0, len(items), 2):
                add(lambda pair=items[n:n + 2], last=n + 2 >= len(items): w.input_pair(pair, last))
        elif kind == 'row':
            add(lambda items=block.payload: w.row(items))
        elif kind == 'eqs':
            for item in block.payload:
                add(lambda item=item: w.equation(item))
    if group:
        w.place(group, reserve=HEADING_RESERVE)
    return w


def _png_size(data):
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')


SETTINGS = r'''<settings>
<presentation>
<textRendering>
<textStyles>
<textStyle name="Normal"><blockAttr margin-left="0" margin-right="0" text-indent="inherit" text-align="left" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Arial" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false" line-through="false" vertical-align="baseline"/></textStyle>
<textStyle name="Heading 1"><blockAttr margin-left="0" margin-right="0" text-indent="inherit" text-align="left" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Arial" font-charset="0" font-size="13" font-weight="bold" font-style="normal" underline="false" line-through="false" vertical-align="baseline" color="#000080"/></textStyle>
<textStyle name="Heading 2"><blockAttr margin-left="0" margin-right="0" text-indent="inherit" text-align="left" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Arial" font-charset="0" font-size="11" font-weight="bold" font-style="normal" underline="false" line-through="false" vertical-align="baseline"/></textStyle>
<textStyle name="Heading 3"><blockAttr margin-left="0" margin-right="0" text-indent="inherit" text-align="left" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Arial" font-charset="0" font-size="10" font-weight="bold" font-style="normal" underline="false" line-through="false" vertical-align="baseline"/></textStyle>
<textStyle name="Paragraph"><blockAttr margin-left="0" margin-right="0" text-indent="21" text-align="left" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Arial" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false" line-through="false" vertical-align="baseline"/></textStyle>
<textStyle name="List"><blockAttr margin-left="14.25" margin-right="0" text-indent="-14.25" text-align="left" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Arial" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false" line-through="false" vertical-align="baseline"/></textStyle>
<textStyle name="Indent"><blockAttr margin-left="108" margin-right="0" text-indent="inherit" text-align="left" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Arial" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false" line-through="false" vertical-align="baseline"/></textStyle>
<textStyle name="Title"><blockAttr margin-left="0" margin-right="0" text-indent="inherit" text-align="center" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Times New Roman" font-charset="0" font-size="16" font-weight="bold" font-style="normal" underline="false" line-through="false" vertical-align="baseline" color="#000080"/></textStyle>
<textStyle name="Subtitle" base-style="Title"><blockAttr margin-left="0" margin-right="0" text-indent="inherit" text-align="center" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Times New Roman" font-charset="0" font-size="13" font-weight="normal" font-style="normal" underline="false" line-through="false" vertical-align="baseline"/></textStyle>
<textStyle name="Note" base-style="Normal"><blockAttr margin-left="0" margin-right="0" text-indent="0" text-align="left" list-style-type="inherit" tabs="inherit"/><inlineAttr font-family="Arial" font-charset="0" font-size="9" font-weight="normal" font-style="normal" underline="false" line-through="false" vertical-align="baseline" color="#404040"/></textStyle>
</textStyles>
</textRendering>
<mathRendering equation-color="#000">
<operators multiplication="narrow-dot" derivative="derivative" literal-subscript="large" definition="colon-equal" global-definition="triple-equal" local-definition="left-arrow" equality="bold-equal" symbolic-evaluation="right-arrow"/>
<mathStyles>
<mathStyle name="Variables" font-family="Times New Roman" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false"/>
<mathStyle name="Constants" font-family="Times New Roman" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false"/>
<mathStyle name="User 1" font-family="Arial" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false"/>
<mathStyle name="User 2" font-family="Courier New" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false"/>
<mathStyle name="User 3" font-family="Arial" font-charset="0" font-size="10" font-weight="bold" font-style="normal" underline="false"/>
<mathStyle name="User 4" font-family="Times New Roman" font-charset="0" font-size="10" font-weight="normal" font-style="italic" underline="false"/>
<mathStyle name="User 5" font-family="Times New Roman" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false"/>
<mathStyle name="User 6" font-family="Arial" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false"/>
<mathStyle name="User 7" font-family="Times New Roman" font-charset="0" font-size="10" font-weight="normal" font-style="normal" underline="false"/>
<mathStyle name="Math Text Font" font-family="Times New Roman" font-charset="0" font-size="14" font-weight="normal" font-style="normal" underline="false"/>
</mathStyles>
<dimensionNames mass="mass" length="length" time="time" current="current" thermodynamic-temperature="temperature" luminous-intensity="luminosity" amount-of-substance="substance" display="false"/>
<symbolics derivation-steps-style="vertical-insert" show-comments="false" evaluate-in-place="false"/>
<results numeric-only="false">
<decimal precision="3" show-trailing-zeros="true" radix="dec" complex-threshold="10" zero-threshold="15" imaginary-value="i"/>
<matrix display-style="auto" expand-nested-arrays="false"/>
<unit format-units="true" simplify-units="true" fractional-unit-exponent="false"/>
</results>
</mathRendering>
<pageModel show-page-frame="false" show-header-frame="false" show-footer-frame="false" header-footer-start-page="1" paper-code="1" orientation="portrait" print-single-page-width="true" page-width="612" page-height="792">
<margins left="18" right="18" top="36" bottom="36"/>
<header use-full-page-width="false"/>
<footer use-full-page-width="false"><center>{\rtf1\ansi\ansicpg1252\deff0\deflang1033{\fonttbl{\f0\fnil\fcharset0 Arial;}}
\viewkind4\uc1\pard\qc\fs18\{n\}\par
}</center></footer>
</pageModel>
<colorModel background-color="#fff" default-highlight-color="#ffff80"/>
<language math="en" UI="en"/>
</presentation>
<calculation>
<builtInVariables array-origin="0" convergence-tolerance="0.001" constraint-tolerance="0.001" random-seed="1" prn-precision="4" prn-col-width="8"/>
<calculationBehavior automatic-recalculation="true" matrix-strict-singularity-check="false" optimize-expressions="false" exact-boolean="true" strings-use-origin="false" zero-over-zero="error">
<compatibility multiple-assignment="MC12" local-assignment="MC11"/>
</calculationBehavior>
<units>
<currentUnitSystem name="us" customized="false"/>
</units>
</calculation>
<editor view-annotations="false" view-regions="false">
<ruler is-visible="false" ruler-unit="in"/>
<grid granularity-x="6" granularity-y="6"/>
</editor>
<fileFormat image-type="image/png" image-quality="75" save-numeric-results="true" exclude-large-results="false" save-text-images="false" screen-dpi="96"/>
<miscellaneous>
<handbook handbook-region-tag-ub="1" can-delete-original-handbook-regions="true" can-delete-user-regions="true" can-print="true" can-copy="true" can-save="true" file-permission-mask="4294967295"/>
</miscellaneous>
</settings>'''


def document(blocks, *, title, description, seed, figures_dir, check_width=False):
    """The worksheet XML. Raises when the evaluation order is wrong, when a region crosses a page, or (check_width)
    when a region reaches past the right edge of the text area."""
    w = layout(blocks, figures_dir)
    check_order(w.log)
    w.check_pages()
    if check_width:
        w.check_width()
    ids = [str(uuid.UUID(int=(seed + n) % (1 << 128), version=4)).upper() for n in range(3)]
    binary = ''.join(f'<item item-id="{n}">{_b64(data)}</item>\n' for n, data in w.items)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<worksheet version="3.0.3" xmlns="http://schemas.mathsoft.com/worksheet30" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ws="http://schemas.mathsoft.com/worksheet30" '
        'xmlns:ml="http://schemas.mathsoft.com/math30" xmlns:u="http://schemas.mathsoft.com/units10" '
        'xmlns:p="http://schemas.mathsoft.com/provenance10">\n'
        '<pointReleaseData/>\n'
        '<metadata>\n<generator>Mathcad Professional 14.1</generator>\n<userData>\n'
        f'<title>{escape(title)}</title>\n'
        f'<description>{escape(description)}</description>\n'
        '<author>D2MPDB</author>\n<company/>\n<keywords/>\n<revisedBy/>\n</userData>\n'
        f'<identityInfo>\n<revision>1</revision>\n<documentID>{ids[0]}</documentID>\n<versionID>{ids[1]}</versionID>\n'
        '<parentVersionID>00000000-0000-0000-0000-000000000000</parentVersionID>\n'
        '<branchID>00000000-0000-0000-0000-000000000000</branchID>\n</identityInfo>\n</metadata>\n'
        f'{SETTINGS}\n<regions>\n' + '\n'.join(w.regions) + '\n</regions>\n'
        f'<binaryContent>\n{binary}</binaryContent>\n</worksheet>\n')


def _b64(data):
    text = base64.b64encode(data).decode('ascii')
    return '\n'.join(text[i:i + 76] for i in range(0, len(text), 76))
