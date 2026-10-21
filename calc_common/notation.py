"""Offline MathML for the journal-calculation formulas (the backwall notation, bound to a package's symbol table).

Names may be the journal's own Unicode identifiers (α_T, ΔT_rise, φ_h); an ASCII name with a Greek base
(gamma_DC) renders the Greek letter. ``symbol()`` tags the outer element with ``data-var`` for the report cards.
"""
from html import escape
from pier_cap.engine import Q, UNITS, CONSTANTS, parse
from pier_cap.math_notation import tag, number, fenced, mathml, quantity

GREEK = {'phi': 'φ', 'gamma': 'γ', 'beta': 'β', 'theta': 'θ', 'alpha': 'α', 'eps': 'ε', 'lambda': 'λ', 'delta': 'δ',
         'mu': 'μ', 'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'eta': 'η', 'omega': 'ω', 'Gamma': 'Γ', 'Delta': 'Δ', 'Omega': 'Ω', 'pi': 'π'}


class Notation:
    def __init__(self, spec):
        self.special = {k: tuple(v) for k, v in spec.text.get('symbols', {}).items()}

    def symbol(self, name):
        parts = name.split('_')
        base, subs = parts[0], parts[1:]
        if base in self.special:
            glyph, first = self.special[base]
            subs = ([first] if first else []) + subs
        else:
            glyph = GREEK.get(base, base)
        subs = [GREEK.get(s, s) for s in subs]
        attr = f' data-var="{escape(name)}"'
        if subs:
            return f'<msub{attr}>' + tag('mi', glyph) + tag('mtext', ','.join(subs)) + '</msub>'
        return f'<mi{attr}>{escape(glyph)}</mi>'

    def expression(self, ast, engine=None, units=None, substitute=False, units_only=False, scope=()):
        kind = ast[0]

        def render(a):
            return self.expression(a, engine, units, substitute, units_only, scope)
        if kind == 'num':
            return number(ast[1])
        if kind == 'str':
            return tag('mtext', '“' + ast[1] + '”')
        if kind == 'name':
            name = ast[1]
            if name in UNITS or units_only:
                return '<mi mathvariant="normal">' + escape(name) + '</mi>'
            if name in CONSTANTS:
                return tag('mi', 'π' if name == 'pi' else name)
            if name in ('true', 'false'):
                return tag('mtext', name)
            if name in scope:
                return tag('mi', name)
            if substitute:
                return fenced(self.result(engine.get(name), engine, (units or {}).get(name)))
            return self.symbol(name)
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
        if name in ('And', 'Or'):
            return '<mrow>' + tag('mo', '∧' if name == 'And' else '∨').join(fenced(render(a)) for a in args) + '</mrow>'
        label = name.lower() if name in ('Min', 'Max', 'Sin', 'Cos', 'Tan', 'Ln', 'Exp', 'Atan', 'Asin', 'Acos', 'Floor', 'Round') else name
        return '<mrow>' + tag('mi', label) + fenced('<mo>,</mo>'.join(render(a) for a in args)) + '</mrow>'

    def unit_mathml(self, unit):
        if not unit:
            return ''
        return self.expression(parse(unit), units_only=True)

    def result(self, value, engine, unit):
        if isinstance(value, bool):
            return tag('mtext', str(value).lower())
        if not isinstance(value, Q):
            return tag('mtext', '“' + str(value) + '”')
        try:
            return quantity(value, engine, unit)
        except AssertionError:
            return quantity(value, engine, None)

    def definition_mathml(self, name, ast, engine, units, unit, block=True):
        """symbol = expression = substituted values = result, as one MathML line."""
        value = engine.get(name)
        parts = [self.symbol(name), self.expression(ast)]
        if ast[0] not in ('num', 'str') and not (ast[0] == 'bin' and ast[2][0] == 'num' and ast[3][0] == 'name' and ast[3][1] in UNITS):
            parts.append(self.expression(ast, engine, units, substitute=True))
        parts.append(self.result(value, engine, unit))
        body = tag('mo', '=').join(parts)
        return mathml('<mrow>' + body + '</mrow>', block)

    def function_mathml(self, name, params, ast, block=True):
        head = '<mrow>' + self.symbol(name) + fenced('<mo>,</mo>'.join(tag('mi', p) for p in params)) + '</mrow>'
        return mathml('<mrow>' + head + tag('mo', '=') + self.expression(ast, scope=tuple(params)) + '</mrow>', block)
