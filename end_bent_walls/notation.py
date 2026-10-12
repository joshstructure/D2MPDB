"""Offline MathML for the end-bent wall formulas.

Reuses the C005 MathML primitives; only the symbol table differs so this
calculation's Greek letters and multi-part subscripts read like the Mathcad source.
"""
from html import escape
from pier_cap.engine import Q, UNITS, parse
from pier_cap.math_notation import tag, number, fenced, mathml, quantity

GREEK = {'phi': 'φ', 'gamma': 'γ', 'beta': 'β', 'theta': 'θ', 'alpha': 'α', 'eps': 'ε',
         'lambda': 'λ', 'delta': 'δ', 'mu': 'μ', 'rho': 'ρ', 'Gamma': 'Γ', 'Delta': 'Δ'}
SPECIAL = {'fc': ('f′', 'c'), 'fy': ('f', 'y'), 'Es': ('E', 's'), 'dT': ('Δ', 'T'),
           'K1': ('K', '1'), 'K2': ('K', '2'), 'EL': ('EL', '')}


def symbol(name):
    parts = name.split('_')
    base, subs = parts[0], parts[1:]
    if base in SPECIAL:
        glyph, first = SPECIAL[base]
        subs = ([first] if first else []) + subs
    else:
        glyph = GREEK.get(base, base)
    subs = [GREEK.get(s, s) for s in subs]
    main = tag('mi', glyph)
    return '<msub>' + main + tag('mtext', ','.join(subs)) + '</msub>' if subs else main


def expression(ast, engine=None, units=None, substitute=False, units_only=False):
    """Fully group compound operands so the displayed tree cannot change precedence."""
    kind = ast[0]

    def render(a):
        return expression(a, engine, units, substitute, units_only)
    if kind == 'num':
        return number(ast[1])
    if kind == 'str':
        return tag('mtext', ast[1])
    if kind == 'name':
        name = ast[1]
        if name in UNITS or units_only:
            return '<mi mathvariant="normal">' + escape(name) + '</mi>'
        if substitute:
            return fenced(quantity(engine.get(name), engine, (units or {}).get(name)))
        return symbol(name)
    if kind == 'unary':
        return '<mrow>' + tag('mo', '−' if ast[1] == '-' else '+') + fenced(render(ast[2])) + '</mrow>'
    if kind == 'bin':
        op, a, b = ast[1:]
        left, right = render(a), render(b)
        if op == '/':
            return '<mfrac>' + left + right + '</mfrac>'
        if op == '^':
            return '<msup>' + (fenced(left) if a[0] in ('bin', 'unary') else left) + right + '</msup>'
        additive, compare = ('+', '-'), ('<', '>', '<=', '>=', '==', '!=')
        # Left-associative sums read correctly without grouping; keep every other grouping explicit.
        if a[0] == 'bin' and (a[1] in compare or (a[1] in additive and op not in additive)):
            left = fenced(left)
        if b[0] == 'bin' and (b[1] in compare or b[1] in additive):
            right = fenced(right)
        op = {'*': '·', '-': '−', '==': '=', '!=': '≠', '<=': '≤', '>=': '≥'}.get(op, op)
        return '<mrow>' + left + tag('mo', op) + right + '</mrow>'
    name, args = ast[1:]
    if name == 'Sqrt':
        return '<msqrt>' + render(args[0]) + '</msqrt>'
    if name == 'Abs':
        return '<mrow><mo>|</mo>' + render(args[0]) + '<mo>|</mo></mrow>'
    if name == 'If':
        if substitute:
            return render(args[1] if engine.eval(args[0], {}) else args[2])
        return ('<mrow><mo>{</mo><mtable columnalign="left left"><mtr><mtd>' + render(args[1]) +
                '</mtd><mtd><mtext>if </mtext>' + render(args[0]) + '</mtd></mtr><mtr><mtd>' + render(args[2]) +
                '</mtd><mtd><mtext>otherwise</mtext></mtd></mtr></mtable></mrow>')
    label = name.lower() if name in ('Min', 'Max', 'Sin', 'Cos', 'Tan') else name
    return '<mrow>' + tag('mi', label) + fenced('<mo>,</mo>'.join(render(a) for a in args)) + '</mrow>'


def unit_mathml(unit):
    if not unit:
        return ''
    return expression(parse(unit), units_only=True)


def result_mathml(value, engine, unit):
    if isinstance(value, bool):
        return tag('mtext', str(value).lower())
    if not isinstance(value, Q):
        return tag('mtext', str(value))
    return quantity(value, engine, unit)


def definition_mathml(name, ast, engine, units, unit, block=True):
    """symbol = expression = substituted values = result, as one MathML line."""
    value = engine.get(name)
    parts = [symbol(name), expression(ast)]
    substituted = expression(ast, engine, units, substitute=True)
    # Skip a redundant substitution for a bare constant or a single reference.
    if ast[0] not in ('num',) and not (ast[0] == 'bin' and ast[2][0] == 'num' and ast[3][0] == 'name'
                                       and ast[3][1] in UNITS):
        parts.append(substituted)
    parts.append(result_mathml(value, engine, unit))
    body = tag('mo', '=').join(parts)
    return mathml('<mrow>' + body + '</mrow>', block)
