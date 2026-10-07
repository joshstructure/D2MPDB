"""Offline MathML presentation of the calculation engine's own expression trees.

This module formats expressions; it does not implement engineering equations.
"""
from html import escape
import math
from .engine import Q, UNITS, parse


def tag(kind, text):
    return f'<{kind}>{escape(str(text))}</{kind}>'


def number(value):
    if not math.isfinite(value):
        return tag('mtext', str(value))
    text = f'{value:.6g}'
    if 'e' in text:
        base, exponent = text.split('e')
        return '<mrow>'+tag('mn', base)+'<mo>×</mo><msup><mn>10</mn>'+tag('mn', int(exponent))+'</msup></mrow>'
    return tag('mn', text)


def symbol(name):
    greek = {'phi':'φ', 'gamma':'γ', 'beta':'β', 'theta':'θ', 'alpha':'α', 'eps':'ε'}
    special = {'fc':"f′", 'fy':'f', 'Es':'E', 'Mu':'M', 'MI':'M', 'MIII':'M',
               'As':'A', 'Av':'A', 'Mn':'M', 'Mr':'M', 'dc':'d', 'fs':'f', 'fo':'f',
               'ccr':'c', 'Icr':'I', 'Ig':'I', 'nAs':'nA', 'Ss':'S', 'bs':'β',
               'yt':'y', 'fr':'f', 'fpc':'f', 'dv':'d', 'Vu':'V', 'Vs':'V', 'Vr':'V', 'Vc':'V'}
    subs = {'fc':'c', 'fy':'y', 'Es':'s', 'Mu':'u', 'MI':'I', 'MIII':'III', 'As':'s',
            'Av':'v', 'Mn':'n', 'Mr':'r', 'dc':'c', 'fs':'s', 'fo':'o', 'ccr':'cr',
            'Icr':'cr', 'Ig':'g', 'nAs':'s', 'Ss':'s', 'bs':'s', 'yt':'t', 'fr':'r',
            'fpc':'pc', 'dv':'v', 'Vu':'u', 'Vs':'s', 'Vr':'r', 'Vc':'c'}
    parts = name.split('_')
    base = parts[0]
    suffix = ([subs[base]] if base in subs else [])+parts[1:]
    main = tag('mi', greek.get(base, special.get(base, base)))
    return '<msub>'+main+tag('mtext', ','.join(suffix))+'</msub>' if suffix else main


def fenced(body):
    return '<mrow><mo>(</mo>'+body+'<mo>)</mo></mrow>'


def quantity(value, engine, unit=None):
    if isinstance(value, bool):
        return tag('mtext', str(value).lower())
    if not isinstance(value, Q):
        return tag('mtext', value)
    if unit:
        scale = engine.eval(parse('1 '+unit), {})
        value.same(scale)
        magnitude = value.v/scale.v
        units = expression(parse(unit), units_only=True)
    else:
        magnitude = value.v
        powers = []
        for label, power in zip(('in', 'kip', 'rad'), value.d):
            if abs(power)<1e-10: continue
            term = tag('mi', label).replace('<mi>', '<mi mathvariant="normal">')
            powers.append(term if power == 1 else '<msup>'+term+number(power)+'</msup>')
        units = '<mo>·</mo>'.join(powers)
    return '<mrow>'+number(magnitude)+('<mspace width="0.3em"/>'+units if units else '')+'</mrow>'


def expression(ast, engine=None, definitions=None, substitute=False, units_only=False):
    """Fully group compound operands so the displayed tree cannot change precedence."""
    kind = ast[0]
    def render(a): return expression(a, engine, definitions, substitute, units_only)
    if kind=='num': return number(ast[1])
    if kind=='str': return tag('mtext', ast[1])
    if kind=='name':
        name = ast[1]
        if name in UNITS or units_only:
            return '<mi mathvariant="normal">'+escape(name)+'</mi>'
        if name in ('true', 'false'): return tag('mtext', name)
        if substitute:
            unit = (definitions or {}).get(name, {}).get('unit')
            return fenced(quantity(engine.get(name), engine, unit))
        return symbol(name)
    if kind=='unary': return '<mrow>'+tag('mo', '−' if ast[1]=='-' else '+')+fenced(render(ast[2]))+'</mrow>'
    if kind=='bin':
        op, a, b = ast[1:]
        left, right = render(a), render(b)
        if op=='/': return '<mfrac>'+left+right+'</mfrac>'
        if op=='^': return '<msup>'+(fenced(left) if a[0] in ('bin','unary') else left)+right+'</msup>'
        if a[0]=='bin' and a[1] in ('+', '-', '<', '>', '<=', '>=', '==', '!='): left=fenced(left)
        if b[0]=='bin' and b[1] in ('+', '-', '<', '>', '<=', '>=', '==', '!='): right=fenced(right)
        op={'*':'·', '-':'−', '==':'=', '!=':'≠', '<=':'≤', '>=':'≥'}.get(op, op)
        return '<mrow>'+left+tag('mo', op)+right+'</mrow>'
    name, args = ast[1:]
    if name=='Sqrt': return '<msqrt>'+render(args[0])+'</msqrt>'
    if name=='Abs': return '<mrow><mo>|</mo>'+render(args[0])+'<mo>|</mo></mrow>'
    if name=='If':
        # Piecewise notation preserves even the inactive branch without evaluating it.
        # Numeric substitution only follows the active branch, matching Engine.eval.
        if substitute: return render(args[1] if engine.eval(args[0], {}) else args[2])
        return ('<mrow><mo>{</mo><mtable columnalign="left left"><mtr><mtd>'+render(args[1])+
                '</mtd><mtd><mtext>if </mtext>'+render(args[0])+'</mtd></mtr><mtr><mtd>'+render(args[2])+
                '</mtd><mtd><mtext>otherwise</mtext></mtd></mtr></mtable></mrow>')
    if name in ('And','Or'):
        return '<mrow>'+tag('mo', '∧' if name=='And' else '∨').join(fenced(render(a)) for a in args)+'</mrow>'
    return '<mrow>'+tag('mi', name.lower() if name in ('Min','Max','Sin','Cos','Tan') else name)+fenced('<mo>,</mo>'.join(render(a) for a in args))+'</mrow>'


def mathml(body, block=False):
    return '<math xmlns="http://www.w3.org/1998/Math/MathML" display="'+('block' if block else 'inline')+'">'+body+'</math>'
