"""'What it represents' drawings for the bridge temperature movement calculation (C003).

One scene serves every equation: the two-span continuous unit in elevation, fixed at the intermediate pier, with the
thermal movement arrows at Begin and End Bridge and the design-temperature scale beside it. Each equation highlights
the lengths, temperatures or arrows it uses and prints its result in the right-hand panel.
"""
from html import escape
from calc_common.schematics import (Svg, Frame, sym, val, eq, n, make_drawer, schematic as _schematic, meaning as _meaning,
                                    INK, GREY, FAINT, HL, BLUE, TEAL, AMBER, CONC, SOIL, PX)
from .model import SPEC


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)


# ----------------------------------------------------------------------------- scenes
def _unit(s, e, hl_left=False, hl_right=False, both=False, factored=False, show_lengths=False):
    """Two-span unit in elevation; returns the pixel x of Begin, Pier and End and the deck y."""
    v = e.value
    L1, L2 = v('L_left', 'ft'), v('L_right', 'ft')
    f = Frame(-6, L1 + L2 + 6, -14, 10, 12, 40, PX - 40, 190)
    y_deck = f.Y(0)
    y_ground = f.Y(-10)
    # ground band and supports rising from it to the bearings
    s.rect(f.X(-6), y_ground, f.L(L1 + L2 + 12), f.L(4), fill=SOIL, stroke='none')
    s.line(f.X(-6), y_ground, f.X(L1 + L2 + 6), y_ground, GREY, 0.8)
    for x, label, kind in ((0, 'Begin Bridge', 'exp'), (L1, 'Pier (fixed)', 'fix'), (L1 + L2, 'End Bridge', 'exp')):
        s.rect(f.X(x) - 7, y_deck + 10, 14, y_ground - y_deck - 10, fill=CONC, stroke=INK, sw=0.9)
        if kind == 'fix':
            s.poly([(f.X(x), y_deck + 1), (f.X(x) - 7, y_deck + 10), (f.X(x) + 7, y_deck + 10)], fill=INK, stroke=INK)
        else:
            s.circle(f.X(x) - 4, y_deck + 6, 2.2, fill=INK)
            s.circle(f.X(x) + 4, y_deck + 6, 2.2, fill=INK)
        s.text(f.X(x), f.Y(-14) + 11, label, 9, GREY)
    # deck
    s.rect(f.X(0), y_deck - 8, f.L(L1 + L2), 8, fill='#d7e0e8', stroke=INK, sw=1)
    s.line(f.X(L1), y_deck - 14, f.X(L1), y_deck + 2, INK, 0.8, '3 2')
    if show_lengths:
        s.dim(f.X(0), y_deck - 34, f.X(L1), y_deck - 34, f'{sym("L_left")} = {n(L1, 2)} ft', HL if hl_left else INK, side=-1)
        s.dim(f.X(L1), y_deck - 34, f.X(L1 + L2), y_deck - 34, f'{sym("L_right")} = {n(L2, 2)} ft', HL if hl_right else INK, side=-1)
    # movement arrows (exaggerated), both directions
    for x, hl, name, sign in ((0, hl_left or both, 'δ_left' + ('_TU' if factored else ''), -1),
                              (L1 + L2, hl_right or both, 'δ_right' + ('_TU' if factored else ''), 1)):
        color = HL if hl else BLUE
        s.arrow(f.X(x), y_deck - 4, f.X(x) + sign * 26, y_deck - 4, color, 2.0, 7)
        s.arrow(f.X(x), y_deck - 4, f.X(x) - sign * 26, y_deck - 4, color, 1.2, 6)
        s.tag(f.X(x) - sign * 4, y_deck - 16, f'{sym(name)} = {val(e, name, 3)}', color, 'start' if sign < 0 else 'end')
    s.text(f.X((L1 + L2) / 2), y_deck - 52, 'expansion (rise) and contraction (fall), both ' + ('factored by γ' if factored else 'unfactored'), 9, GREY)
    return f, y_deck


def _scale(s, e, hl=None):
    """Design temperature scale beside the unit: T_low, T_mean, T_high with the rise and fall brackets."""
    v = e.value
    tl, tm, th = v('T_low'), v('T_mean'), v('T_high')
    x, top, bot = 118, 258, 334
    rng = max(th - tl, 1)
    Y = lambda t: bot - (t - tl) / rng * (bot - top)
    s.line(x, top, x, bot, INK, 1.2)
    for t, lab in ((tl, 'T_low'), (tm, 'T_mean'), (th, 'T_high')):
        s.line(x - 5, Y(t), x + 5, Y(t), INK, 1.2)
        s.text(x - 9, Y(t) + 3.5, f'{sym(lab)} = {n(t, 0)}°F', 9.5, INK, 'end')
    s.dim(x + 26, Y(tm), x + 26, Y(th), f'{sym("ΔT_rise")} = {val(e, "ΔT_rise", 0)}°F', HL if hl == 'rise' else TEAL, side=1)
    s.dim(x + 26, Y(tl), x + 26, Y(tm), f'{sym("ΔT_fall")} = {val(e, "ΔT_fall", 0)}°F', HL if hl == 'fall' else TEAL, side=1)
    s.text(x + 150, Y(tm) + 4, 'concrete-only superstructure (SDG 2.7, LRFD 3.12.2)', 8.5, GREY, 'start')


def unit_length(e, name):
    s = Svg(f'{name}: continuous unit length', title='Two-span continuous unit between expansion ends')
    _unit(s, e, show_lengths=True)
    f, y = _unit_frame(e)
    s.dim(f.X(0), y + 30, f.X(e.value('L_left', 'ft') + e.value('L_right', 'ft')), y + 30, f'{sym("L_unit")} = {val(e, "L_unit", 2)}', HL, side=1)
    _scale(s, e)
    s.panel(eq(e, name, 2), [f'{eq(e, "L_left", 2)} (Span 1)', f'{eq(e, "L_right", 2)} (Span 2)', ('whole unit moves relative to the fixed pier', GREY)])
    return s


def _unit_frame(e):
    v = e.value
    L1, L2 = v('L_left', 'ft'), v('L_right', 'ft')
    f = Frame(-6, L1 + L2 + 6, -14, 10, 12, 40, PX - 40, 190)
    return f, f.Y(0)


def alpha(e, name):
    s = Svg(f'{name}: coefficient of thermal expansion', title='Thermal strain of normal-weight concrete')
    x0, y0, w = 40, 90, 300
    s.rect(x0, y0, w, 26, fill=CONC, stroke=INK)
    s.rect(x0, y0 + 60, w, 26, fill=CONC, stroke=INK, dash='4 2')
    dx = 34
    s.rect(x0 + w, y0 + 60, dx, 26, fill='#f6d6d3', stroke=HL)
    s.dim(x0, y0 + 46, x0 + w, y0 + 46, 'L at T_mean', INK, side=-1)
    s.dim(x0 + w, y0 + 100, x0 + w + dx, y0 + 100, f'{sym("α_T")}·ΔT·L', HL, side=1)
    s.text(x0, y0 + 135, 'per °F: strain of 6×10⁻⁶ for every degree of temperature change', 9.5, GREY, 'start')
    s.text(x0, y0 + 150, f'for 1 ft over {val(e, "ΔT_rise", 0)}°F: {n(e.value("α_T") * e.value("ΔT_rise") * 12, 5)} in', 9.5, INK, 'start')
    s.arrow(x0 + w / 2, y0 + 30, x0 + w / 2, y0 + 56, BLUE, 1.2, 6)
    s.tag(x0 + w / 2 + 8, y0 + 46, 'heat by ΔT', BLUE, 'start')
    s.panel(f'{sym(name)} = {n(e.value(name), 7)} /°F', [('LRFD 5.4.2.2: 6.0×10⁻⁶ /°F normal-weight concrete', GREY),
                                                        'strain = α·ΔT, movement = α·ΔT·L'])
    return s


def temperature(e, name):
    which = 'rise' if 'rise' in name else 'fall'
    s = Svg(f'{name}: temperature {which}', title=f'Design temperature {which} from the mean construction temperature')
    _unit(s, e)
    _scale(s, e, hl=which)
    rows = [f'{eq(e, "T_high", 0)}°F', f'{eq(e, "T_mean", 0)}°F', f'{eq(e, "T_low", 0)}°F',
            ('symmetric: the same 35°F governs rise and fall', GREY)]
    s.panel(f'{sym(name)} = {val(e, name, 0)}°F', rows)
    return s


def movement(e, name):
    factored = name.endswith('_TU')
    base = name[:-3] if factored else name
    side = 'left' if 'left' in base else 'right' if 'right' in base else None
    both = base in ('δ_end_to_end',)
    s = Svg(f'{name}: thermal movement', title=('Factored TU movement envelope' if factored else 'Unfactored thermal movement') + ' at the expansion ends')
    f, y = _unit(s, e, hl_left=side == 'left' or base == 'δ_end_max', hl_right=side == 'right' or base == 'δ_end_max',
                 both=both, factored=factored, show_lengths=True)
    if both:
        s.dim(f.X(0) - 26, y + 30, f.X(e.value('L_left', 'ft') + e.value('L_right', 'ft')) + 26, y + 30,
              f'{sym(name)} = {val(e, name, 3)} total change of length', HL, side=1)
    _scale(s, e, hl='rise')
    rows = []
    if side:
        L = 'L_left' if side == 'left' else 'L_right'
        rows += [f'{sym("α_T")} · {sym("ΔT_rise")} · {sym(L)}', f'= {n(e.value("α_T"), 7)} × {val(e, "ΔT_rise", 0)}°F × {val(e, L, 2)}']
    if base == 'δ_end_max':
        rows += [f'{eq(e, "δ_left_TU" if factored else "δ_left", 3)}', f'{eq(e, "δ_right_TU" if factored else "δ_right", 3)}', ('larger end governs the joint / bearing detailing', GREY)]
    if both:
        rows += [f'{eq(e, "δ_left", 3)} + {eq(e, "δ_right", 3)}', ('relative change between the two ends', GREY)]
    if factored:
        rows += [f'{eq(e, "γ_TU", 2)} (SDG 6.3 / LRFD 3.4.1 TU, deformations)', f'× {eq(e, base, 3)}']
    s.panel(eq(e, name, 3), rows)
    return s


drawer = make_drawer({'L_unit': unit_length, 'α_T': alpha, 'ΔT_rise': temperature, 'ΔT_fall': temperature},
                     [(r'^δ_', movement)])
