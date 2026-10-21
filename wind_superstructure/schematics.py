"""'What it represents' drawings for the superstructure wind calculation (C001).

Scenes, each drawn from the current case: the bridge over low ground with the exposure height and the K_Z curves;
the pressure chain from wind speed to the design pressure; the skew-angle plan with the across- and along-bridge
coefficients; the exposed superstructure depth turning pressure into line loads; the two spans feeding one repair-frame
bearing; and the deck cross-section under vertical wind with its quarter-point resultant.
"""
import math
from html import escape
from calc_common.schematics import (Svg, Frame, sym, val, eq, n, make_drawer, schematic as _schematic, meaning as _meaning,
                                    INK, GREY, FAINT, HL, BLUE, TEAL, AMBER, CONC, SOIL, SLAB, WIND, PX)
from .model import SPEC

TYPES = [('I-Girder or Box-Girder Superstructure', 1.3), ('Bridge Substructure', 1.6), ('Truss/Column/Arch - Sharp-Edged', 2.0),
         ('Truss/Column/Arch - Round', 1.0), ('Other (default)', 1.2)]
SKEWS = [('0', 1.0, 0.0), ('15', 0.88, 0.12), ('30', 0.82, 0.24), ('45', 0.66, 0.32), ('60', 0.34, 0.38)]


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)


def _kz(cat, z):
    z0, c, d = {'B': (0.9834, 6.87, 345.6), 'C': (0.0984, 7.35, 478.4), 'D': (0.0164, 7.65, 616.1)}[cat]
    return (2.5 * math.log(z / z0) + c) ** 2 / d


# ----------------------------------------------------------------------------- bridge over low ground
def _bridge_elevation(s, e, left, top, width, height, hl=None):
    """Transverse section of the bridge above low ground: z_clear, d_super, fence crown at Z, 33 ft floor."""
    v = e.value
    zc, d, Z, wd = v('z_clear', 'ft'), v('d_super', 'ft'), v('Z', 'ft'), v('w_deck', 'ft')
    f = Frame(-wd * 0.9, wd * 0.9, -2, max(Z, 33) + 3, left, top, width, height)
    s.rect(f.X(-wd * 0.9), f.Y(0), f.L(wd * 1.8), f.L(2), fill=SOIL, stroke='none')
    s.line(f.X(-wd * 0.9), f.Y(0), f.X(wd * 0.9), f.Y(0), INK, 1)
    s.text(f.X(0), f.Y(0) + 11, 'low ground', 8.5, GREY)
    # superstructure box (girders + deck), fence hoop above
    s.rect(f.X(-wd / 2), f.Y(zc + d), f.L(wd), f.L(d), fill=SLAB, stroke=INK)
    for xb in (-wd / 4, wd / 4):
        s.rect(f.X(xb - 0.9), f.Y(zc + d * 0.85), f.L(1.8), f.L(d * 0.85), fill=CONC, stroke=INK, sw=0.7)
    top_fence = Z
    r = min(wd / 2, (top_fence - zc - d) * 0.6)
    y_spring = top_fence - r
    s.line(f.X(-wd / 2 + 0.4), f.Y(zc + d), f.X(-wd / 2 + 0.4), f.Y(y_spring), INK, 1)
    s.line(f.X(wd / 2 - 0.4), f.Y(zc + d), f.X(wd / 2 - 0.4), f.Y(y_spring), INK, 1)
    s.path(f'M{f.X(-wd / 2 + 0.4):.1f},{f.Y(y_spring):.1f} A{f.L(wd / 2 - 0.4):.1f},{f.L(r):.1f} 0 0 1 {f.X(wd / 2 - 0.4):.1f},{f.Y(y_spring):.1f}', stroke=INK, sw=1)
    # dimensions on the right
    xd = f.X(wd / 2) + 18
    s.dim(xd, f.Y(0), xd, f.Y(zc), f'{sym("z_clear")} = {n(zc, 2)} ft', HL if hl == 'z_clear' else INK, side=1, ext=6)
    s.dim(xd, f.Y(zc), xd, f.Y(zc + d), f'{sym("d_super")} = {n(d, 2)} ft', HL if hl == 'd_super' else INK, side=1, ext=6)
    xz = f.X(-wd / 2) - 16
    s.dim(xz, f.Y(0), xz, f.Y(Z), f'Z = {n(Z, 2)} ft', HL if hl in ('Z', 'Z_calc') else INK, side=-1, ext=6)
    s.line(f.X(-wd * 0.9), f.Y(33), f.X(wd * 0.9), f.Y(33), AMBER, 1, '5 3')
    s.tag(f.X(wd * 0.9) + 3, f.Y(33) + 3, '33 ft floor', AMBER, 'start')
    return f


def exposure(e, name):
    cat = str(e.engine.get('Exp_Cat'))
    titles = {'Z_calc': 'Exposure height inserted into the K_Z equations', 'K_Z_B': 'Pressure exposure coefficient, Exposure B',
              'K_Z_C': 'Pressure exposure coefficient, Exposure C', 'K_Z_D': 'Pressure exposure coefficient, Exposure D',
              'K_Z_gov': f'Governing K_Z for exposure category {cat}'}
    s = Svg(f'{name}: exposure', title=titles.get(name, name))
    _bridge_elevation(s, e, 80, 36, 150, 300, hl='Z_calc' if name == 'Z_calc' else None)
    zc = e.value('Z_calc', 'ft')
    # K_Z curves
    zs = [33 + i * (max(zc, 60) + 20 - 33) / 40 for i in range(41)]
    series, pts = [], []
    hl_cat = name[-1] if name in ('K_Z_B', 'K_Z_C', 'K_Z_D') else cat if name == 'K_Z_gov' else None
    colors = {'B': '#9fb3c8', 'C': BLUE, 'D': TEAL}
    for c in ('B', 'C', 'D'):
        series.append(([_kz(c, z) for z in zs], zs, HL if c == hl_cat else colors[c]))
    for c in ('B', 'C', 'D'):
        pts.append((_kz(c, zc), zc, '', HL if c == hl_cat else colors[c]))
    X, Y = s.plot(330, 60, 120, 250, series, pts, xlabel='K_Z', ylabel='height, ft', x_range=(0.6, 2.0))
    s.line(X(0.6), Y(zc), X(2.0), Y(zc), HL if name == 'Z_calc' else GREY, 1, '4 2')
    s.tag(X(2.0), Y(zc) - 6, f'{sym("Z_calc")} = {n(zc, 2)} ft', HL if name == 'Z_calc' else GREY, 'end')
    legend = [(f'{sym("K_Z_" + c)} = {n(_kz(c, zc), 3)} (exposure {c})', HL if c == hl_cat else colors[c]) for c in ('B', 'C', 'D')]
    rows = {'Z_calc': [f'Z = {val(e, "Z", 2, "ft")} (fence crown above low ground)', 'floor: 33 ft (LRFD 3.8.1.2.1)',
                       ('Z ≥ 33 ft, so Z itself is used' if e.value('Z', 'ft') >= 33 else 'Z < 33 ft, so 33 ft is used', GREY)],
            'K_Z_B': [f'z₀ = 0.9834 ft, (2.5 ln(Z/z₀) + 6.87)² / 345.6', f'at {sym("Z_calc")} = {n(zc, 2)} ft'],
            'K_Z_C': [f'z₀ = 0.0984 ft, (2.5 ln(Z/z₀) + 7.35)² / 478.4', f'at {sym("Z_calc")} = {n(zc, 2)} ft'],
            'K_Z_D': [f'z₀ = 0.0164 ft, (2.5 ln(Z/z₀) + 7.65)² / 616.1', f'at {sym("Z_calc")} = {n(zc, 2)} ft'],
            'K_Z_gov': [f'Exp_Cat = {cat}: ' + ('K_Z_D' if cat == 'D' else 'K_Z_C (B is not offered by the switch)')]}
    s.panel(eq(e, name, 3 if name != 'Z_calc' else 2, 'ft' if name == 'Z_calc' else None), rows.get(name, []) + legend)
    return s


# ----------------------------------------------------------------------------- pressure chain
def pressure(e, name):
    combo = {'P_Z_III': ('III', 'V_III', 'Strength III', True), 'P_Z_V': ('V', 'V_V', 'Strength V', False), 'P_Z_SI': ('SI', 'V_SI', 'Service I', False)}
    key, vname, label, with_kz = combo[name]
    s = Svg(f'{name}: design wind pressure', title=f'{label} horizontal wind pressure on the superstructure (LRFD Eq. 3.8.1.2.1-1)')
    v = e.value
    d, wd = v('d_super', 'ft'), v('w_deck', 'ft')
    f = Frame(-wd * 1.3, wd * 0.8, -2, d + 4, 12, 50, 230, 150)
    s.rect(f.X(-wd / 2), f.Y(d), f.L(wd), f.L(d), fill=SLAB, stroke=INK)
    for xb in (-wd / 4, wd / 4):
        s.rect(f.X(xb - 0.9), f.Y(d * 0.85), f.L(1.8), f.L(d * 0.85), fill=CONC, stroke=INK, sw=0.7)
    s.wind(f.X(-wd / 2), f.Y(d) + 4, f.Y(0) - 4, 34, 1, HL, 14, f'{sym(name)}')
    s.tag(f.X(-wd / 2) - 70, f.Y(d) - 8, f'{sym(vname)} = {n(v(vname), 0)} mph', BLUE, 'start')
    s.dim(f.X(wd / 2) + 12, f.Y(d), f.X(wd / 2) + 12, f.Y(0), f'{sym("d_super")}', INK, side=1)
    # bars of the three pressures
    items = [(f'{sym("P_Z_III")} (130 mph, K_Z)', v('P_Z_III', 'ksf')), (f'{sym("P_Z_V")} (80 mph)', v('P_Z_V', 'ksf')),
             (f'{sym("P_Z_SI")} (70 mph)', v('P_Z_SI', 'ksf'))]
    hl = ['P_Z_III', 'P_Z_V', 'P_Z_SI'].index(name)
    s.text(12, 232, 'pressure by load combination, ksf', 9.5, GREY, 'start')
    s.bars(150, 240, items, 170, hl, 4, 'ksf')
    kz = f'{eq(e, "K_Z_gov", 3)}' if with_kz else 'K_Z = 1.0 (SDG 2.4.1.C below 130 mph)'
    rows = [f'0.00000256 · V² · K_Z · G · C_D', f'{sym(vname)} = {n(v(vname), 0)} mph', kz, f'{eq(e, "G_fac", 2)}', f'{eq(e, "C_D", 2)}']
    s.panel(eq(e, name, 4, 'ksf'), rows)
    return s


def drag(e, name):
    s = Svg(f'{name}: drag coefficient', title='Drag coefficient by structure type (LRFD Table 3.8.1.2.1-2)')
    chosen = str(e.engine.get('Struct_Type'))
    y = 52
    s.text(20, y - 14, 'structure type', 9.5, GREY, 'start')
    s.text(300, y - 14, 'C_D', 9.5, GREY, 'start')
    for label, cd in TYPES:
        hit = label == chosen
        if hit:
            s.rect(14, y - 12, 330, 18, fill='#fbe9e7', stroke='none')
        s.text(20, y + 1, escape(label), 10, HL if hit else INK, 'start', 'bold' if hit else 'normal')
        s.text(300, y + 1, f'{cd:.1f}', 10, HL if hit else INK, 'start', 'bold' if hit else 'normal')
        y += 20
    # girder sketch with wind
    v = e.value
    d, wd = v('d_super', 'ft'), v('w_deck', 'ft')
    f = Frame(-wd * 1.2, wd * 0.8, -1, d + 2, 40, 180, 250, 150)
    s.rect(f.X(-wd / 2), f.Y(d), f.L(wd), f.L(d * 0.18), fill=SLAB, stroke=INK)
    for xb in (-wd / 4, wd / 4):
        s.poly([(f.X(xb - 1.2), f.Y(d * 0.82)), (f.X(xb + 1.2), f.Y(d * 0.82)), (f.X(xb + 0.5), f.Y(d * 0.7)), (f.X(xb + 0.5), f.Y(d * 0.12)),
                (f.X(xb + 1.2), f.Y(0)), (f.X(xb - 1.2), f.Y(0)), (f.X(xb - 0.5), f.Y(d * 0.12)), (f.X(xb - 0.5), f.Y(d * 0.7))], fill=CONC, stroke=INK, sw=0.7)
    s.wind(f.X(-wd / 2) - 2, f.Y(d) + 4, f.Y(0) - 4, 30, 1, BLUE, 14, 'wind')
    s.text(f.X(0), f.Y(0) + 16, 'two-beam concrete superstructure: girder/box row of the table', 8.5, GREY)
    s.panel(eq(e, name, 2), [f'Struct_Type = “{escape(chosen[:34])}”', ('selected row of the table in red', GREY)])
    return s


# ----------------------------------------------------------------------------- skew and line loads
def skew(e, name):
    s = Svg(f'{name}: skew coefficient', title='Wind components by skew angle of attack (LRFD Table 3.8.1.2.3a-1)')
    chosen = str(e.engine.get('Skew_deg_str'))
    v = e.value
    # plan view
    x0, y0, wpl, hpl = 40, 96, 250, 66
    s.rect(x0, y0, wpl, hpl, fill=SLAB, stroke=INK)
    s.text(x0 + wpl / 2, y0 + hpl / 2 + 4, 'bridge (plan)', 9.5, GREY)
    th = float(chosen) if chosen.replace('.', '').isdigit() else 0.0
    cx, cy = x0 + wpl / 2, y0 - 14
    ang = math.radians(th)
    s.arrow(cx - 48 * math.sin(ang), cy - 48 * math.cos(ang), cx, cy, BLUE, 2.2, 8)
    s.tag(cx - 48 * math.sin(ang) - 8, cy - 48 * math.cos(ang) + 4, f'wind, skew {chosen}° from perpendicular', BLUE, 'end')
    s.arrow(cx, y0 - 10, cx, y0 + 26, HL if 'T' in name else GREY, 1.6, 7)
    s.tag(cx + 6, y0 + 20, f'{sym("C_T_gir")} across', HL if 'T' in name else GREY, 'start')
    s.arrow(cx, y0 + 46, cx + 46, y0 + 46, HL if 'L' in name else GREY, 1.6, 7)
    s.tag(cx + 50, y0 + 50, f'{sym("C_L_gir")} along', HL if 'L' in name else GREY, 'start')
    # table
    y = 200
    s.text(40, y - 14, 'skew °', 9.5, GREY, 'start')
    s.text(120, y - 14, 'girders: across', 9.5, GREY, 'start')
    s.text(240, y - 14, 'along', 9.5, GREY, 'start')
    for sk, ct, cl in SKEWS:
        hit = sk == chosen
        if hit:
            s.rect(34, y - 12, 290, 18, fill='#fbe9e7', stroke='none')
        col_t = HL if hit and 'T' in name else INK
        col_l = HL if hit and 'L' in name else INK
        s.text(40, y + 1, sk, 10, HL if hit else INK, 'start', 'bold' if hit else 'normal')
        s.text(120, y + 1, f'{ct:.2f}', 10, col_t, 'start', 'bold' if hit else 'normal')
        s.text(240, y + 1, f'{cl:.2f}', 10, col_l, 'start', 'bold' if hit else 'normal')
        y += 20
    s.panel(eq(e, name, 2), [f'Skew_deg_str = “{escape(chosen)}”', 'wind normal to the bridge: full across, no along component' if th == 0 else 'components from the table row'])
    return s


def line_load(e, name):
    v = e.value
    across = name in ('w_T_III', 'w_T0_III')
    coef = 'C_T_gir' if name == 'w_T_III' else 'C_L_gir' if name == 'w_L_III' else None
    titles = {'w_T_III': 'Strength III across-bridge wind line load', 'w_L_III': 'Strength III along-bridge wind line load',
              'w_T0_III': 'Perpendicular concrete wind line load, companion to vertical wind'}
    s = Svg(f'{name}: line load', title=titles[name])
    d, wd = v('d_super', 'ft'), v('w_deck', 'ft')
    f = Frame(-wd * 1.1, wd * 0.9, -3, d + 3, 12, 40, 250, 190)
    s.rect(f.X(-wd / 2), f.Y(d), f.L(wd), f.L(d), fill=SLAB, stroke=INK)
    for xb in (-wd / 4, wd / 4):
        s.rect(f.X(xb - 0.9), f.Y(d * 0.85), f.L(1.8), f.L(d * 0.85), fill=CONC, stroke=INK, sw=0.7)
    s.wind(f.X(-wd / 2), f.Y(d) + 4, f.Y(0) - 4, 36, 1, BLUE, 14)
    s.tag(f.X(-wd / 2) - 40, f.Y(d) - 8, f'{sym("P_Z_III")} = {val(e, "P_Z_III", 4, "ksf")}', BLUE, 'start')
    s.dim(f.X(wd / 2) + 14, f.Y(d), f.X(wd / 2) + 14, f.Y(0), f'{sym("d_super")} = {n(d, 2)} ft', INK, side=1, ext=6)
    yr = f.Y(d / 2)
    if across:
        s.arrow(f.X(wd / 2) + 118, yr, f.X(wd / 2) + 186, yr, HL, 2.4, 8)
        s.tag(f.X(wd / 2) + 118, yr - 10, f'{sym(name)} per ft', HL, 'start')
    else:
        s.circle(f.X(wd / 2) + 136, yr, 8, fill='#fff', stroke=HL, sw=2)
        s.circle(f.X(wd / 2) + 136, yr, 2.4, fill=HL)
        s.tag(f.X(wd / 2) + 118, yr - 12, f'{sym(name)} along the bridge', HL, 'start')
        s.tag(f.X(wd / 2) + 118, yr + 22, '(into the page)', GREY, 'start')
    s.text(f.X(0), f.Y(0) + 24, 'pressure × exposed depth = force per unit length of bridge', 9, GREY)
    rows = [f'{eq(e, "P_Z_III", 4, "ksf")}', f'{eq(e, "d_super", 2, "ft")}']
    if coef:
        rows.append(f'{eq(e, coef, 2)} (skew {escape(str(e.engine.get("Skew_deg_str")))}°)')
    else:
        rows.append('no skew coefficient: full perpendicular pressure')
    s.panel(eq(e, name, 4), rows)
    return s


# ----------------------------------------------------------------------------- spans and the repair frame
def spans(e, name):
    v = e.value
    L1, L2 = v('Span_1', 'ft'), v('Span_2', 'ft')
    s = Svg(f'{name}: spans', title='Two spans of the unit' + (' and the wind carried to one repair-frame bearing' if name == 'W_Frame' else ''))
    f = Frame(-8, L1 + L2 + 8, -16, 22, 12, 40, PX - 40, 170)
    yd = f.Y(0)
    s.rect(f.X(0), yd - 8, f.L(L1 + L2), 8, fill=SLAB, stroke=INK)
    for x, lab in ((0, 'EB1'), (L1, 'Pier'), (L1 + L2, 'EB2')):
        s.rect(f.X(x) - 6, yd, 12, f.L(12), fill=CONC, stroke=INK, sw=0.8)
        s.text(f.X(x), f.Y(-12) + 12, lab, 9, GREY)
    gov = 'Span_1' if L1 >= L2 else 'Span_2'
    s.dim(f.X(0), yd - 56, f.X(L1), yd - 56, f'{sym("Span_1")} = {n(L1, 2)} ft', HL if gov == 'Span_1' else INK, side=-1)
    s.dim(f.X(L1), yd - 56, f.X(L1 + L2), yd - 56, f'{sym("Span_2")} = {n(L2, 2)} ft', HL if gov == 'Span_2' else INK, side=-1)
    if name == 'W_Frame':
        Ls = v('L_span', 'ft')
        xa = 0 if gov == 'Span_1' else L1
        s.udl(f.X(xa) + 4, f.X(xa + Ls) - 4, yd - 10, 16, -1, BLUE, 16, f'{sym("w_T_III")} = {val(e, "w_T_III", 4)}')
        s.rect(f.X(xa), yd - 8, f.L(Ls / 2), 8, fill='#f6d6d3', stroke=HL)
        s.dim(f.X(xa), yd + 50, f.X(xa + Ls / 2), yd + 50, f'{sym("L_span")}/2 to this end', HL, side=1)
        s.text(f.X(0), yd + 80, f'half the span’s wind, split between {n(v("Beam_count"), 0)} beams = one bearing', 9, GREY, 'start')
        rows = [f'{eq(e, "w_T_III", 4)} × {eq(e, "L_span", 2)} / 2', f'÷ Beam_count = {n(v("Beam_count"), 0)}', ('repair-frame load split, one bearing', GREY)]
    else:
        rows = [f'{eq(e, "Span_1", 2)}', f'{eq(e, "Span_2", 2)}', ('longer span governs the 150 ft simplified-method limit', GREY)]
    s.panel(eq(e, name, 3), rows)
    return s


# ----------------------------------------------------------------------------- vertical wind
def vertical(e, name):
    v = e.value
    wd, d, ev = v('w_deck', 'ft'), v('d_super', 'ft'), v('e_V', 'ft')
    titles = {'α_V': 'Quarter-point location of the vertical wind resultant', 'e_V': 'Eccentricity of the vertical wind resultant',
              'w_V_III': 'Upward vertical wind line load (LRFD 3.8.2)', 'm_V_III': 'Overturning moment per unit length from vertical wind'}
    s = Svg(f'{name}: vertical wind', title=titles[name])
    f = Frame(-wd * 0.8, wd * 0.8, -d - 11, 7, 12, 40, PX - 40, 290)
    s.rect(f.X(-wd / 2), f.Y(0), f.L(wd), f.L(d * 0.2), fill=SLAB, stroke=INK)
    for xb in (-wd / 4, wd / 4):
        s.rect(f.X(xb - 0.9), f.Y(-d * 0.2), f.L(1.8), f.L(d * 0.8), fill=CONC, stroke=INK, sw=0.7)
    s.udl(f.X(-wd / 2) + 3, f.X(wd / 2) - 3, f.Y(-d), 22, 1, BLUE, 16, f'{sym("p_V_III")} = {val(e, "p_V_III", 3, "ksf")} upward')
    s.line(f.X(0), f.Y(2.5), f.X(0), f.Y(-d - 3), GREY, 0.8, '4 2')
    s.tag(f.X(0), f.Y(2.5) - 4, 'deck ℄', GREY)
    xr = f.X(-ev)
    hl_w = HL if name in ('w_V_III', 'm_V_III') else INK
    s.arrow(xr, f.Y(-d) - 6, xr, f.Y(0.2), hl_w, 2.4, 8)
    s.tag(xr - 10, f.Y(-d * 0.55), f'{sym("w_V_III")} = {val(e, "w_V_III", 4)}', hl_w, 'end')
    s.dim(f.X(0), f.Y(4), xr, f.Y(4), f'{sym("e_V")} = {n(ev, 3)} ft', HL if name in ('e_V', 'α_V') else INK, side=-1)
    s.dim(f.X(-wd / 2), f.Y(-d - 9.5), f.X(wd / 2), f.Y(-d - 9.5), f'{sym("w_deck")} = {n(wd, 2)} ft', INK, side=1)
    s.dim(f.X(-wd / 2), f.Y(-d - 6), f.X(-wd / 4), f.Y(-d - 6), f'{sym("α_V")}·{sym("w_deck")} = {sym("w_deck")}/4', HL if name == 'α_V' else GREY, side=1)
    s.text(f.X(-wd / 2) - 6, f.Y(-d - 1.5), 'windward', 8.5, GREY, 'end')
    if name == 'm_V_III':
        s.moment(f.X(wd / 2) + 34, f.Y(-d * 0.35), 20, True, HL, f'{sym("m_V_III")} = {val(e, "m_V_III", 3)} per ft')
    rows = {'α_V': ['LRFD 3.8.2: resultant at the windward quarter point', f'{sym("e_V")} = {sym("α_V")} · {sym("w_deck")}'],
            'e_V': [f'{eq(e, "α_V", 2)} × {eq(e, "w_deck", 2, "ft")}'],
            'w_V_III': [f'{eq(e, "p_V_III", 3, "ksf")} × {eq(e, "w_deck", 2, "ft")}', ('0.020 ksf upward on the full deck width', GREY)],
            'm_V_III': [f'{eq(e, "w_V_III", 4)} × {eq(e, "e_V", 3, "ft")}', ('moment about the deck centerline per ft of bridge', GREY)]}
    s.panel(eq(e, name, 4 if name != 'α_V' else 2), rows[name])
    return s


drawer = make_drawer({'Z_calc': exposure, 'K_Z_B': exposure, 'K_Z_C': exposure, 'K_Z_D': exposure, 'K_Z_gov': exposure,
                      'P_Z_III': pressure, 'P_Z_V': pressure, 'P_Z_SI': pressure, 'C_D': drag,
                      'C_T_gir': skew, 'C_L_gir': skew, 'w_T_III': line_load, 'w_L_III': line_load, 'w_T0_III': line_load,
                      'L_span': spans, 'W_Frame': spans, 'α_V': vertical, 'e_V': vertical, 'w_V_III': vertical, 'm_V_III': vertical})
