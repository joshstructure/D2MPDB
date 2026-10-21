"""'What it represents' drawings for the fence wind and pier node load calculation (C002).

Scenes drawn from the current case: the hoop fence above the superstructure with its dimension chain, pressure band
and resultant; the two spans delivering half their length to the pier; the pier in transverse elevation collecting the
superstructure and fence forces at the cap reference; the direct wind on the pier faces; and the pressure chain from
wind speed to the substructure pressure.
"""
from html import escape
from calc_common.schematics import (Svg, Frame, sym, val, eq, n, make_drawer, schematic as _schematic, meaning as _meaning,
                                    INK, GREY, FAINT, HL, BLUE, TEAL, AMBER, CONC, SOIL, SLAB, PX)
from .model import SPEC


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)


def _combo(name):
    return 'Service I' if name.endswith('_SI') else 'Strength III' if name.endswith('_III') else ''


# ----------------------------------------------------------------------------- fence section
def _fence(s, e, left, top, width, height, hl=None, pressure=False):
    """Transverse section through the hoop fence above the superstructure; heights above the cap reference."""
    v = e.value
    zb, ht, R, hf, zm = v('z_base', 'ft'), v('h_tan', 'ft'), v('R_f', 'ft'), v('h_f', 'ft'), v('z_mid', 'ft')
    zs = v('z_spring', 'ft')
    dsup, zsup = v('Depth_SuperStr', 'ft'), v('Dist_windSuperCG_CapCG', 'ft')
    wd = 2 * R + 1.2
    f = Frame(-wd / 2 - 3.2, wd / 2 + 2.8, zsup - dsup / 2 - 1.5, zb + hf + 1, left, top, width, height)
    # superstructure box with the fence base on the deck
    s.rect(f.X(-wd / 2), f.Y(zsup + dsup / 2), f.L(wd), f.L(dsup), fill=SLAB, stroke=INK)
    s.text(f.X(0), f.Y(zsup) + 4, 'superstructure', 8.5, GREY)
    # hoop: legs then semicircle
    for sign in (-1, 1):
        s.line(f.X(sign * R), f.Y(zb), f.X(sign * R), f.Y(zs), INK, 1.6)
    s.path(f'M{f.X(-R):.1f},{f.Y(zs):.1f} A{f.L(R):.1f},{f.L(R):.1f} 0 0 1 {f.X(R):.1f},{f.Y(zs):.1f}', stroke=INK, sw=1.6)
    s.line(f.X(-R), f.Y(zb), f.X(R), f.Y(zb), GREY, 0.8, '3 2')
    # dimension chain on the right
    xd = f.X(R) + 16
    col = lambda key: HL if hl == key else INK
    s.dim(xd, f.Y(zb), xd, f.Y(zs), f'{sym("h_tan")} = {n(ht, 2)} ft', col('h_tan'), side=1, ext=6)
    s.dim(xd, f.Y(zs), xd, f.Y(zb + hf), f'{sym("R_f")} = {n(R, 2)} ft', col('R_f'), side=1, ext=6)
    xd2 = xd + 62
    s.dim(xd2, f.Y(zb), xd2, f.Y(zb + hf), f'{sym("h_f")} = {n(hf, 2)} ft', col('h_f'), side=1)
    xl = f.X(-R) - 18
    s.dim(xl, f.Y(zsup - dsup / 2 - 1.2), xl, f.Y(zb), f'{sym("z_base")} = {n(zb, 2)} ft', col('z_base'), side=-1, ext=6)
    s.line(f.X(-wd / 2 - 3), f.Y(zsup - dsup / 2 - 1.2), f.X(wd / 2 + 2.6), f.Y(zsup - dsup / 2 - 1.2), GREY, 0.8, '5 3')
    s.text(f.X(0), f.Y(zsup - dsup / 2 - 1.2) + 11, 'cap reference (cap centroid) ▸ heights measured from here', 8.5, GREY)
    s.line(f.X(-R) - 4, f.Y(zm), f.X(R) + 4, f.Y(zm), col('z_mid'), 0.9, '4 2')
    s.tag(f.X(R) - 2, f.Y(zm) - 4, f'{sym("z_mid")} = {n(zm, 2)} ft (band centroid)', col('z_mid'), 'end')
    if pressure:
        s.wind(f.X(-R) - 2, f.Y(zb + hf) + 3, f.Y(zb) - 3, 26, 1, BLUE, 14)
        s.tag(f.X(-R) - 30, f.Y(zb + hf) - 7, f'{sym("p_fence")} = {val(e, "p_fence", 3, "ksf")} on the band', BLUE, 'start')
    return f


def _resultant(s, f, e, name):
    """Fence resultant arrow at z_eff, labelled below the shaft so it clears the pressure label."""
    v = e.value
    zeff, R = v('z_eff', 'ft'), v('R_f', 'ft')
    s.arrow(f.X(-R) - 96, f.Y(zeff), f.X(-R) - 32, f.Y(zeff), HL, 2.4, 8)
    lab = {'F_fence': f'{sym("F_fence")} = {val(e, "F_fence", 2)}', 'M_fence': f'{sym("F_fence")} = {val(e, "F_fence", 2)} at {sym("z_eff")}',
           'b_M_fence': f'resultant at {sym("z_eff")}', 'F_V_fence': f'{sym("F_fence")} horizontal only'}.get(name, f'{sym("z_eff")} = {n(zeff, 2)} ft')
    s.tag(f.X(-R) - 96, f.Y(zeff) + 14, lab, HL, 'start')


def fence(e, name):
    titles = {'a_T_fence': 'Gross projected fence height seen by transverse wind', 'b_M_fence': 'First moment of the projected band about the cap reference',
              'z_eff': 'Height of the fence resultant above the cap reference', 'w_fence': 'Prescribed fence wind per foot of bridge (LRFD 13.8.2)',
              'F_fence': 'Fence force delivered to the pier', 'M_fence': 'Fence moment about the longitudinal axis at the cap reference',
              'F_V_fence': 'Vertical fence component (none in the projected-load model)', 'Check_geometry': 'Dimensions used by the fence load model'}
    s = Svg(f'{name}: fence', title=titles.get(name, name))
    hl = {'a_T_fence': 'h_f', 'b_M_fence': 'z_mid', 'z_eff': 'z_mid', 'Check_geometry': 'h_f'}.get(name)
    f = _fence(s, e, 12, 36, PX - 40, 300, hl=hl, pressure=name in ('w_fence', 'F_fence', 'M_fence', 'F_V_fence'))
    v = e.value
    zeff, zb, hf = v('z_eff', 'ft'), v('z_base', 'ft'), v('h_f', 'ft')
    R = v('R_f', 'ft')
    if name in ('z_eff', 'F_fence', 'M_fence', 'F_V_fence', 'b_M_fence'):
        _resultant(s, f, e, name)
    if name == 'M_fence':
        yc = f.Y(v('Dist_windSuperCG_CapCG', 'ft') - v('Depth_SuperStr', 'ft') / 2 - 1.2)
        s.moment(f.X(0) + 30, yc - 30, 18, True, HL, f'{sym("M_fence")} = {val(e, "M_fence", 1)}')
    rows = {'a_T_fence': [f'= {eq(e, "h_f", 2, "ft")}', ('legs plus hoop seen from the side: one solid band', GREY)],
            'b_M_fence': [f'{eq(e, "a_T_fence", 2, "ft")} × {eq(e, "z_mid", 2, "ft")}', ('area per foot × centroid height', GREY)],
            'z_eff': [f'{eq(e, "b_M_fence", 2)} / {eq(e, "a_T_fence", 2, "ft")}', f'= {sym("z_mid")} for a uniform band'],
            'w_fence': [f'{eq(e, "p_fence", 3, "ksf")} × {eq(e, "a_T_fence", 2, "ft")}', ('0.015 ksf prescribed on the fabric (LRFD 13.8.2)', GREY)],
            'F_fence': [f'{eq(e, "w_fence", 4)} × {eq(e, "L_trib", 2, "ft")}', ('half of each adjoining span reaches the pier', GREY)],
            'M_fence': [f'{eq(e, "F_fence", 2)} × {eq(e, "z_eff", 2, "ft")}', ('about the longitudinal axis at the cap reference', GREY)],
            'F_V_fence': ['0 × F_fence: the projected-load model carries no vertical fence term'],
            'Check_geometry': [f'{eq(e, "h_f", 2, "ft")}, {eq(e, "R_f", 2, "ft")}', f'{eq(e, "h_tan", 2, "ft")}, {eq(e, "z_base", 2, "ft")}',
                               f'{eq(e, "L_trib", 2, "ft")}', ('all positive (h_tan and z_base at least zero)', GREY)]}
    result = f'{sym(name)} = {escape(str(e.engine.get(name)))}' if name == 'Check_geometry' else eq(e, name, 3)
    s.panel(result, rows.get(name, []))
    if name == 'Check_geometry':
        s.status(PX, 150, str(e.engine.get(name)))
    return s


# ----------------------------------------------------------------------------- spans and the tributary length
def spans(e, name):
    v = e.value
    L1, L2, Lt = v('Span_1', 'ft'), v('Span_2', 'ft'), v('L_trib', 'ft')
    titles = {'F_c_III': 'Strength III wind on the concrete superstructure delivered to the pier',
              'F_c_SI': 'Service I wind on the concrete superstructure delivered to the pier',
              'L_span_max': 'Longer span, for the simplified-method qualification', 'DC_span': 'Span against the 150 ft simplified-method limit',
              'DC_height': 'Bridge height against the 33 ft simplified-method limit', 'Check_simplified': 'LRFD 3.8.1.2.3a simplified wind components: both limits'}
    s = Svg(f'{name}: spans', title=titles.get(name, name))
    f = Frame(-8, L1 + L2 + 8, -16, 30, 12, 46, PX - 40, 150)
    yd = f.Y(0)
    s.rect(f.X(0), yd - 10, f.L(L1 + L2), 10, fill=SLAB, stroke=INK)
    for x, lab in ((0, 'EB1'), (L1, 'Pier'), (L1 + L2, 'EB2')):
        s.rect(f.X(x) - 6, yd, 12, f.L(12), fill=CONC, stroke=INK, sw=0.8)
        s.text(f.X(x), f.Y(-12) + 12, lab, 9, GREY)
    gov = 'Span_1' if L1 >= L2 else 'Span_2'
    hl_span = name in ('L_span_max', 'DC_span', 'Check_simplified')
    s.dim(f.X(0), yd - 58, f.X(L1), yd - 58, f'{sym("Span_1")} = {n(L1, 2)} ft', HL if hl_span and gov == 'Span_1' else INK, side=-1)
    s.dim(f.X(L1), yd - 58, f.X(L1 + L2), yd - 58, f'{sym("Span_2")} = {n(L2, 2)} ft', HL if hl_span and gov == 'Span_2' else INK, side=-1)
    if name in ('F_c_III', 'F_c_SI'):
        p = 'P_Z_III' if name.endswith('III') else 'P_Z_SI'
        s.rect(f.X(L1 / 2), yd - 10, f.L(Lt), 10, fill='#f6d6d3', stroke=HL)
        s.udl(f.X(L1 / 2) + 3, f.X(L1 / 2 + Lt) - 3, yd - 12, 16, -1, BLUE, 16, f'{sym(p)} × {sym("Depth_SuperStr")} per ft')
        s.dim(f.X(L1 / 2), yd + 28, f.X(L1 / 2 + Lt), yd + 28, f'{sym("L_trib")} = {n(Lt, 2)} ft', HL, side=1)
        s.force(f.X(L1), yd + 70, 0, -22, f'{sym(name)} = {val(e, name, 2)} to the pier', HL)
        rows = [f'{eq(e, p, 4, "ksf")} × {eq(e, "Depth_SuperStr", 2, "ft")}', f'× {eq(e, "L_trib", 2, "ft")}', ('pressure × exposed depth × tributary length', GREY)]
        s.panel(eq(e, name, 2), rows)
        return s
    # qualification bars
    H = v('H_bridge', 'ft')
    Ls = v('L_span_max', 'ft')
    y0 = 240
    s.text(12, y0 - 10, 'simplified-method limits (LRFD 3.8.1.2.3a)', 9.5, GREY, 'start')
    s.gauge(130, y0, 240, Ls / 150, f'{sym("L_span_max")} = {n(Ls, 2)} ft of 150 ft', HL if name in ('DC_span', 'Check_simplified') else None, '150 ft')
    s.text(122, y0 + 12, 'span', 9.5, INK, 'end')
    s.gauge(130, y0 + 56, 240, H / 33, f'{sym("H_bridge")} = {n(H, 2)} ft of 33 ft', HL if name in ('DC_height', 'Check_simplified') else None, '33 ft')
    s.text(122, y0 + 68, 'height', 9.5, INK, 'end')
    rows = {'L_span_max': [f'Max({eq(e, "Span_1", 2)}, {eq(e, "Span_2", 2)})'],
            'DC_span': [f'{eq(e, "L_span_max", 2)} / 150 ft', ('under 1.0: the span limit is met', GREY) if Ls <= 150 else ('over 1.0: span limit exceeded', HL)],
            'DC_height': [f'{eq(e, "H_bridge", 2, "ft")} / 33 ft', ('under 1.0: the height limit is met', GREY) if H <= 33 else ('over 1.0: the bridge is taller than 33 ft', HL)],
            'Check_simplified': [f'{eq(e, "L_span_max", 2)} ≤ 150 ft and', f'{eq(e, "H_bridge", 2, "ft")} ≤ 33 ft',
                                 ('both limits must hold for the simplified components', GREY)]}
    result = f'{sym(name)} = {escape(str(e.engine.get(name)))}' if name == 'Check_simplified' else eq(e, name, 3)
    s.panel(result, rows.get(name, []))
    if name == 'Check_simplified':
        s.status(PX, 160, str(e.engine.get(name)))
    return s


# ----------------------------------------------------------------------------- pier in transverse elevation
def _pier(s, e, left, top, width, height, super_wind=None, fence_wind=None, pier_wind=False, totals=None):
    """Pier wall and cap with the superstructure and fence above; forces at their heights above the cap reference."""
    v = e.value
    Hp, Wc = v('PierCap_ht_toTop', 'ft'), v('PierCap_width', 'ft')
    cap_h = 3.0
    zref = Hp - cap_h / 2                      # cap reference above terrain (cap centroid)
    dsup, zsup = v('Depth_SuperStr', 'ft'), v('Dist_windSuperCG_CapCG', 'ft')
    zb, hf = v('z_base', 'ft'), v('h_f', 'ft')
    top_z = zref + zb + hf + 1
    wsup = 13.6
    f = Frame(-wsup, wsup * 0.9, -2, top_z, left, top, width, height)
    s.rect(f.X(-wsup), f.Y(0), f.L(wsup * 1.9), f.L(2), fill=SOIL, stroke='none')
    s.line(f.X(-wsup), f.Y(0), f.X(wsup * 0.9), f.Y(0), INK, 1)
    s.text(f.X(wsup * 0.9) - 2, f.Y(0) + 11, 'terrain', 8.5, GREY, 'end')
    # wall (transverse face, width PierCap_width) and cap
    s.rect(f.X(-Wc / 2), f.Y(Hp - cap_h), f.L(Wc), f.L(Hp - cap_h), fill=CONC, stroke=INK)
    s.rect(f.X(-Wc / 2 - 0.5), f.Y(Hp), f.L(Wc + 1), f.L(cap_h), fill=CONC, stroke=INK)
    s.circle(f.X(0), f.Y(zref), 3.5, fill=HL)
    s.tag(f.X(0) + 7, f.Y(zref) + 4, 'cap reference', HL, 'start')
    # superstructure and fence band
    s.rect(f.X(-wsup / 2), f.Y(zref + zsup + dsup / 2), f.L(wsup), f.L(dsup), fill=SLAB, stroke=INK)
    s.rect(f.X(-wsup / 2 + 0.5), f.Y(zref + zb + hf), f.L(wsup - 1), f.L(hf), fill='#eef3f7', stroke=INK, sw=0.8, dash='3 2')
    s.text(f.X(0), f.Y(zref + zb + hf / 2) + 4, 'fence band (projected)', 8.5, GREY)
    xd = f.X(wsup / 2) + 14
    if super_wind:
        s.wind(f.X(-wsup / 2), f.Y(zref + zsup + dsup / 2) + 3, f.Y(zref + zsup - dsup / 2) - 3, 26, 1, BLUE, 14)
        s.arrow(f.X(-wsup / 2) - 90, f.Y(zref + zsup), f.X(-wsup / 2) - 30, f.Y(zref + zsup), super_wind[1], 2.4, 8)
        s.tag(f.X(-wsup / 2) - 90, f.Y(zref + zsup) - 9, super_wind[0], super_wind[1], 'start')
        s.dim(xd + 12, f.Y(zref), xd + 12, f.Y(zref + zsup), f'{sym("Dist_windSuperCG_CapCG")} = {n(zsup, 2)} ft', super_wind[1], side=1, ext=6)
    if fence_wind:
        zeff = v('z_eff', 'ft')
        s.wind(f.X(-wsup / 2 + 0.5), f.Y(zref + zb + hf) + 3, f.Y(zref + zb) - 3, 22, 1, BLUE, 14)
        s.arrow(f.X(-wsup / 2) - 90, f.Y(zref + zeff), f.X(-wsup / 2) - 26, f.Y(zref + zeff), fence_wind[1], 2.4, 8)
        s.tag(f.X(-wsup / 2) - 90, f.Y(zref + zeff) - 9, fence_wind[0], fence_wind[1], 'start')
        s.dim(xd, f.Y(zref), xd, f.Y(zref + zeff), '', fence_wind[1], side=1)
        s.tag(xd + 6, f.Y(zref + zeff) + 4, f'{sym("z_eff")} = {n(zeff, 2)} ft', fence_wind[1], 'start')
    if pier_wind:
        s.wind(f.X(-Wc / 2), f.Y(Hp) + 3, f.Y(0) - 3, 22, 1, HL, 16)
        s.tag(f.X(-Wc / 2) - 26, f.Y(Hp / 2) + 4, f'{sym("p_sub_III" if pier_wind == "III" else "p_sub_SI")}', HL, 'end')
        s.dim(xd, f.Y(0), xd, f.Y(Hp), f'{sym("PierCap_ht_toTop")} = {n(Hp, 2)} ft', HL, side=1, ext=6)
        s.dim(f.X(-Wc / 2), f.Y(Hp) - 14, f.X(Wc / 2), f.Y(Hp) - 14, f'{sym("PierCap_width")} = {n(Wc, 2)} ft', HL, side=-1)
    if totals:
        s.arrow(f.X(0) - 60, f.Y(zref) + 16, f.X(0) - 6, f.Y(zref) + 16, HL, 2.6, 9)
        s.tag(f.X(0) - 60, f.Y(zref) + 30, totals[0], HL, 'start')
        s.moment(f.X(Wc / 2) + 44, f.Y(zref) + 56, 16, True, HL, totals[1])
    return f


def superstructure_moment(e, name):
    c = 'III' if name.endswith('III') else 'SI'
    label = _combo(name)
    s = Svg(f'{name}: pier', title=f'{label}: concrete superstructure wind acting above the cap reference')
    _pier(s, e, 12, 36, PX - 40, 300, super_wind=(f'{sym("F_c_" + c)} = {val(e, "F_c_" + c, 2)}', HL))
    s.panel(eq(e, name, 2), [f'{eq(e, "F_c_" + c, 2)} × {eq(e, "Dist_windSuperCG_CapCG", 2, "ft")}',
                             ('moment about the longitudinal axis through the cap reference', GREY)])
    return s


def cap_totals(e, name):
    c = 'III' if name.endswith('III') else 'SI'
    label = _combo(name)
    kind = 'force' if name.startswith('F_cap_T') else 'moment' if name.startswith('M_cap_L') else 'balance'
    titles = {'force': f'{label}: total across-bridge force at the cap reference', 'moment': f'{label}: total moment about the longitudinal axis at the cap reference',
              'balance': 'Resultant and cap-reference totals reproduce their parts'}
    s = Svg(f'{name}: cap totals', title=titles[kind])
    totals = (f'{sym("F_cap_T_" + c)} = {val(e, "F_cap_T_" + c, 2)}', f'{sym("M_cap_L_" + c)} = {val(e, "M_cap_L_" + c, 1)}')
    _pier(s, e, 12, 36, PX - 40, 300, super_wind=(f'{sym("F_c_" + c)} = {val(e, "F_c_" + c, 2)}', BLUE),
          fence_wind=(f'{sym("F_fence")} = {val(e, "F_fence", 2)}', TEAL), totals=totals)
    if kind == 'force':
        rows = [f'{eq(e, "F_c_" + c, 2)} + {eq(e, "F_fence", 2)}', ('concrete superstructure plus fence, same direction', GREY)]
        s.panel(eq(e, name, 2), rows)
    elif kind == 'moment':
        rows = [f'{eq(e, "M_c_" + c, 1)} + {eq(e, "M_fence", 1)}', ('each force × its height above the cap reference', GREY)]
        s.panel(eq(e, name, 1), rows)
    else:
        rows = [f'{sym("M_fence")} − {sym("F_fence")}·{sym("z_eff")} ≈ 0', f'{sym("F_cap_T_III")} − {sym("F_c_III")} − {sym("F_fence")} ≈ 0',
                f'{sym("M_cap_L_III")} − {sym("M_c_III")} − {sym("M_fence")} ≈ 0', ('tolerance 1e-6', GREY)]
        s.panel(f'{sym(name)} = {escape(str(e.engine.get(name)))}', rows)
        s.status(PX, 170, str(e.engine.get(name)))
    return s


def longitudinal(e, name):
    c = 'III' if name.endswith('III') else 'SI'
    label = _combo(name)
    is_force = name.startswith('F_cap_L')
    s = Svg(f'{name}: longitudinal component', title=f'{label}: simultaneous along-bridge component, 25 % of the transverse set (LRFD 3.8.1.2.3a)')
    # plan view of the pier cap with the two components
    x0, y0 = 60, 120
    s.rect(x0, y0, 300, 40, fill=SLAB, stroke=INK)
    s.text(x0 + 150, y0 + 24, 'pier cap (plan)', 9.5, GREY)
    s.rect(x0 + 130, y0 - 60, 40, 160, fill='none', stroke=GREY, sw=0.8, dash='4 2')
    s.text(x0 + 150, y0 - 66, 'bridge axis', 8.5, GREY)
    cx, cy = x0 + 150, y0 + 20
    s.arrow(cx - 116, cy, cx - 24, cy, BLUE if is_force else GREY, 2.2, 8)
    s.tag(x0, y0 - 10, f'{sym("F_cap_T_" + c)} = {val(e, "F_cap_T_" + c, 2)} (100 %, across)', BLUE if is_force else GREY, 'start')
    s.arrow(cx, cy + 90, cx, cy + 28, HL if is_force else GREY, 2.2, 8)
    s.tag(cx + 8, cy + 86, f'{sym("F_cap_L_" + c)} = {val(e, "F_cap_L_" + c, 2)} (25 %, along)', HL if is_force else GREY, 'start')
    if not is_force:
        s.moment(cx + 110, cy, 18, True, HL, f'{sym("M_cap_T_" + c)} = {val(e, "M_cap_T_" + c, 1)}')
        s.text(x0, y0 + 150, '25 % of the superstructure moment plus 25 % of the fence force at its band centroid z_mid', 9, GREY, 'start')
    if is_force:
        rows = [f'0.25 × {eq(e, "F_cap_T_" + c, 2)}', ('simplified method: along-bridge force is a quarter of the across-bridge force', GREY)]
        s.panel(eq(e, name, 2), rows)
    else:
        rows = [f'0.25 × {eq(e, "M_c_" + c, 1)}', f'+ 0.25 × {eq(e, "F_fence", 2)} × {eq(e, "z_mid", 2, "ft")}',
                ('about the transverse axis at the cap reference', GREY)]
        s.panel(eq(e, name, 1), rows)
    return s


# ----------------------------------------------------------------------------- direct wind on the pier
def pier_pressure(e, name):
    v = e.value
    c = 'III' if name.endswith('III') else 'SI'
    label = _combo(name)
    s = Svg(f'{name}: substructure pressure', title=f'{label}: wind pressure directly on the pier (LRFD Eq. 3.8.1.2.1-1, substructure C_D)')
    vname, kz = ('V_III', 'K_Z_III') if c == 'III' else ('V_SI', 'K_Z_SI')
    # chain boxes
    x, y = 20, 80
    steps = [(f'{sym(vname)} = {n(v(vname), 0)} mph', BLUE), (f'{sym(kz)} = {n(v(kz), 3)}', INK), (f'{sym("G_f")} = {n(v("G_f"), 2)}', INK),
             (f'{sym("q_" + c)} = {val(e, "q_" + c, 4, "ksf")}', HL if name.startswith('q_') else TEAL),
             (f'× {sym("C_sub")} = {n(v("C_sub"), 1)}', INK), (f'{sym("p_sub_" + c)} = {val(e, "p_sub_" + c, 4, "ksf")}', HL if name.startswith('p_sub') else TEAL)]
    for i, (markup, color) in enumerate(steps):
        yy = y + i * 30
        s.rect(x, yy - 14, 150, 22, fill='#fff', stroke=color, sw=1.3, rx=4)
        s.text(x + 8, yy + 1, markup, 10, color, 'start', 'bold' if color == HL else 'normal')
        if i < len(steps) - 1:
            s.arrow(x + 75, yy + 9, x + 75, yy + 15, GREY, 1, 4)
    s.text(x, y + 190, 'q = 0.00000256 · V² · K_Z · G', 9, GREY, 'start')
    s.text(x, y + 204, 'p_sub = q · C_D, C_D = 1.6 (substructure)', 9, GREY, 'start')
    _pier(s, e, 200, 36, 250, 300, pier_wind=c)
    rows = {'q': [f'0.00000256 × {n(v(vname), 0)}² × {n(v(kz), 3)} × {n(v("G_f"), 2)}', ('before the drag coefficient', GREY)],
            'p': [f'{eq(e, "q_" + c, 4, "ksf")} × {eq(e, "C_sub", 1)}', ('acts on the transverse and broad pier faces', GREY)]}
    s.panel(eq(e, name, 4, 'ksf'), rows['q' if name.startswith('q_') else 'p'])
    return s


def pier_force(e, name):
    v = e.value
    c = 'III' if name.endswith('III') else 'SI'
    label = _combo(name)
    transverse = '_T_' in name
    s = Svg(f'{name}: direct pier wind', title=f'{label}: wind force directly on the pier’s ' + ('transverse projected face' if transverse else 'broad wall face'))
    if transverse:
        _pier(s, e, 12, 36, 250, 300, pier_wind=c)
        Hp, Wc = v('PierCap_ht_toTop', 'ft'), v('PierCap_width', 'ft')
        s.text(270, 120, 'projected face:', 9.5, GREY, 'start')
        s.text(270, 138, f'{n(Hp, 2)} ft × {n(Wc, 2)} ft = {n(Hp * Wc, 1)} ft²', 10, INK, 'start')
        rows = [f'{eq(e, "p_sub_" + c, 4, "ksf")}', f'× {eq(e, "PierCap_ht_toTop", 2, "ft")} × {eq(e, "PierCap_width", 2, "ft")}', ('wind across the bridge on the narrow pier face', GREY)]
    else:
        # broad face: wall length × height, wind along the bridge
        A = v('Pier_wall_area', 'ft^2')
        Hp = v('PierCap_ht_toTop', 'ft')
        Lw = A / Hp
        f = Frame(-Lw * 0.75, Lw * 0.75, -2, Hp + 3, 12, 40, 300, 280)
        s.rect(f.X(-Lw * 0.75), f.Y(0), f.L(Lw * 1.5), f.L(2), fill=SOIL, stroke='none')
        s.rect(f.X(-Lw / 2), f.Y(Hp), f.L(Lw), f.L(Hp), fill=CONC, stroke=INK)
        s.text(f.X(0), f.Y(Hp / 2) + 4, f'broad face {sym("Pier_wall_area")} = {n(A, 1)} ft²', 9.5, INK)
        s.wind(f.X(-Lw / 2), f.Y(Hp) + 4, f.Y(0) - 4, 26, 1, HL, 16, f'{sym("p_sub_" + c)}')
        s.text(f.X(0), f.Y(0) + 24, 'wind along the bridge, normal to the wall', 9, GREY)
        rows = [f'{eq(e, "p_sub_" + c, 4, "ksf")} × {eq(e, "Pier_wall_area", 1, "ft^2")}', ('wind along the bridge on the broad wall face', GREY)]
    s.panel(eq(e, name, 2), rows)
    return s


drawer = make_drawer({'a_T_fence': fence, 'b_M_fence': fence, 'z_eff': fence, 'w_fence': fence, 'F_fence': fence, 'M_fence': fence,
                      'F_V_fence': fence, 'Check_geometry': fence,
                      'F_c_III': spans, 'F_c_SI': spans, 'L_span_max': spans, 'DC_span': spans, 'DC_height': spans, 'Check_simplified': spans,
                      'M_c_III': superstructure_moment, 'M_c_SI': superstructure_moment,
                      'F_cap_T_III': cap_totals, 'F_cap_T_SI': cap_totals, 'M_cap_L_III': cap_totals, 'M_cap_L_SI': cap_totals, 'Check_balance': cap_totals,
                      'F_cap_L_III': longitudinal, 'F_cap_L_SI': longitudinal, 'M_cap_T_III': longitudinal, 'M_cap_T_SI': longitudinal,
                      'q_III': pier_pressure, 'q_SI': pier_pressure, 'p_sub_III': pier_pressure, 'p_sub_SI': pier_pressure},
                     [(r'^F_wall_', pier_force)])
