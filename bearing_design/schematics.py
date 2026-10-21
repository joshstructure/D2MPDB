"""'What it represents' drawings for the bearings and support details calculation (C016).

Scenes drawn from the current case: the cap-edge dimension chain of SDM Fig. 12.5-1; the pier pedestal in elevation
with the beam ends, the support length provided and the LRFD 4.7.4.4 requirement; the Type F service screening of each
bearing against its dead- and live-load allowances; the beam-end rotation stages on a level seat against the pad
limits; and the longitudinal pad movement against the shear-deflection limit.
"""
import math
from html import escape
from calc_common.schematics import (Svg, Frame, sym, val, eq, n, make_drawer, schematic as _schematic, meaning as _meaning,
                                    INK, GREY, FAINT, HL, BLUE, TEAL, AMBER, PURPLE, CONC, SOIL, SLAB, PAD, PX)
from .model import SPEC


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)


def _txt(e, name):
    return str(e.engine.get(name))


# ----------------------------------------------------------------------------- cap edge chain (SDM Fig. 12.5-1)
def cap_chain(e, name):
    v = e.value
    parts = [('Cap_cover', 'cover'), ('Fig_12_5_1_DimB', 'B'), ('BearingPad_length', 'pad'), ('Fig_12_5_1_DimD', 'D'), ('Fig_12_5_1_DimF', 'F')]
    vals = [v(k, 'in') for k, _ in parts]
    total = sum(vals)
    s = Svg(f'{name}: cap chain', title='One-sided cap dimension from the cap face to the beam-end detail (SDM Fig. 12.5-1)')
    f = Frame(-2, total + 6, -14, 10, 12, 50, PX - 40, 240)
    y0 = f.Y(0)
    # cap in section along the beam: face at x = 0
    s.rect(f.X(0), y0, f.L(total + 6), f.L(12), fill=CONC, stroke=INK)
    s.text(f.X(total / 2 + 3), f.Y(-13.2), 'pier cap (section along the beam)', 9, GREY)
    # reinforcement at cover, pad, beam end
    xc = v('Cap_cover', 'in')
    s.circle(f.X(xc), y0 + f.L(1.2), 3, fill=INK)
    s.text(f.X(xc) - 7, y0 + f.L(1.2) + 4, 'outer bar', 8.5, GREY, 'end')
    xp = xc + v('Fig_12_5_1_DimB', 'in')
    s.rect(f.X(xp), y0 - f.L(2.5), f.L(v('BearingPad_length', 'in')), f.L(2.5), fill=PAD, stroke='none')
    s.text(f.X(xp + v('BearingPad_length', 'in') / 2), y0 - f.L(2.5) - 5, 'bearing pad', 8.5, GREY)
    xb = xp + v('BearingPad_length', 'in') + v('Fig_12_5_1_DimD', 'in')
    s.rect(f.X(xb - 1.5), y0 - f.L(9), f.L(total - xb + 8), f.L(6.5), fill=SLAB, stroke=INK)
    s.text(f.X(xb + 3), y0 - f.L(5.5), 'beam end', 8.5, GREY, 'start')
    s.line(f.X(total), y0 - f.L(10), f.X(total), y0 + f.L(13), GREY, 0.8, '4 2')
    s.tag(f.X(total), y0 + f.L(13) + 10, '½ joint: beam-end separation / 2', GREY)
    # chain of dimensions
    x = 0
    colors = [INK, INK, BLUE, INK, INK]
    for i, ((key, label), width, color) in enumerate(zip(parts, vals, colors)):
        yy = y0 + f.L(3.2 if i % 2 == 0 else 6.2)
        s.dim(f.X(x), yy, f.X(x + width), yy, '', color, side=1)
        s.tag(f.X(x + width / 2), yy - 5, f'{label} = {n(width, 2)}', color)
        x += width
    s.dim(f.X(0), y0 + f.L(10), f.X(total), y0 + f.L(10), f'{sym(name)} = {n(total, 2)} in', HL, side=1, offset=6)
    rows = [f'{eq(e, "Cap_cover", 2)} + {eq(e, "Fig_12_5_1_DimB", 2)}', f'+ {eq(e, "BearingPad_length", 2)} + {eq(e, "Fig_12_5_1_DimD", 2)}',
            f'+ {eq(e, "Fig_12_5_1_DimF", 2)}', ('cover, inset, pad, pad-to-beam-end, half separation', GREY)]
    s.panel(eq(e, name, 2), rows)
    return s


# ----------------------------------------------------------------------------- minimum support length N
def support(e, name):
    v = e.value
    Lp, hp = v('Pedestal_length_pier', 'in'), v('Pedestal_ht', 'in')
    gap, off = v('Pier_beamEndGap', 'in'), v('PierCL_beamEnd', 'in')
    Nprov, Nreq = v('PedN_Nprov', 'in'), v('PedN_Nreq', 'in')
    titles = {'PedN_H': 'Pier height H for the empirical support length', 'PedN_N1': 'Empirical minimum support length from Span 1 (LRFD Eq. 4.7.4.4-1)',
              'PedN_N2': 'Empirical minimum support length from Span 2 (LRFD Eq. 4.7.4.4-1)', 'PedN_Nreq': 'Governing required support length',
              'PedN_Nprov': 'Support length provided from the beam end to the pedestal edge', 'PedN_margin': 'Support-length margin',
              'DC_PedN': 'Required against provided support length', 'Check_PedN': 'Minimum support length check (LRFD 4.7.4.4)'}
    s = Svg(f'{name}: support length', title=titles.get(name, name))
    if name == 'PedN_H':
        H = v('PedN_H', 'ft')
        Hc = v('CapTop_aboveTerrain', 'ft')
        f = Frame(-9, 9, -2, H + 4, 150, 40, 160, 300)
        s.rect(f.X(-9), f.Y(0), f.L(18), f.L(2), fill=SOIL, stroke='none')
        s.line(f.X(-9), f.Y(0), f.X(9), f.Y(0), INK, 1)
        s.text(f.X(8.8), f.Y(0) + 11, 'terrain datum', 8.5, GREY, 'end')
        s.rect(f.X(-2), f.Y(Hc - 3), f.L(4), f.L(Hc - 3), fill=CONC, stroke=INK)
        s.rect(f.X(-2.5), f.Y(Hc), f.L(5), f.L(3), fill=CONC, stroke=INK)
        s.rect(f.X(-1.8), f.Y(H), f.L(3.6), f.L(H - Hc), fill='#eef2f5', stroke=INK, sw=0.8)
        s.text(f.X(0) + 36, f.Y(H) + 4, 'pedestal top', 8.5, GREY, 'start')
        s.dim(f.X(-5), f.Y(0), f.X(-5), f.Y(Hc), f'{sym("CapTop_aboveTerrain")} = {n(Hc, 2)} ft', INK, side=-1, ext=6)
        s.dim(f.X(5), f.Y(0), f.X(5), f.Y(H), f'H = {n(H, 2)} ft', HL, side=1, ext=6)
        s.panel(eq(e, name, 2, 'ft'), [f'{eq(e, "CapTop_aboveTerrain", 2, "ft")} + {eq(e, "Pedestal_ht", 2, "in")}', ('terrain datum to the top of the pedestal', GREY)])
        return s
    # pedestal elevation along the bridge
    f = Frame(-Lp / 2 - 10, Lp / 2 + 10, -hp - 10, 24, 12, 40, PX - 40, 260)
    y_top = f.Y(0)
    s.rect(f.X(-Lp / 2 - 10), f.Y(-hp), f.L(Lp + 20), f.L(10), fill=CONC, stroke=INK)
    s.text(f.X(-Lp / 2 - 8), f.Y(-hp - 6) + 4, 'pier cap', 9, GREY, 'start')
    s.rect(f.X(-Lp / 2), y_top, f.L(Lp), f.L(hp), fill='#eef2f5', stroke=INK)
    s.text(f.X(0), y_top + f.L(hp / 2) + 4, f'pedestal {n(Lp / 12, 2)} ft long', 9, GREY)
    s.line(f.X(0), f.Y(22), f.X(0), f.Y(-hp - 10), INK, 0.8, '4 2')
    s.tag(f.X(0), f.Y(22) - 3, 'pier ℄', GREY)
    pad_t = 2.56
    for sign, lab in ((-1, 'Span 1 beam'), (1, 'Span 2 beam')):
        x_end = sign * off
        x_far = sign * (Lp / 2 + 9)
        s.rect(f.X(min(x_end, x_far)), f.Y(pad_t + 16), f.L(abs(x_far - x_end)), f.L(16), fill=SLAB, stroke=INK)
        s.text(f.X(sign * (Lp / 2 + 2)), f.Y(pad_t + 8) + 4, lab, 8.5, GREY)
        s.rect(f.X(min(x_end + sign * 3, x_far)), f.Y(pad_t), f.L(abs(x_far - x_end) - 3), f.L(pad_t), fill=PAD, stroke='none')
    s.dim(f.X(-off), f.Y(pad_t + 18), f.X(off), f.Y(pad_t + 18), f'gap {n(gap, 1)} in', GREY, side=-1, offset=8)
    hl_prov = name in ('PedN_Nprov', 'PedN_margin', 'DC_PedN', 'Check_PedN')
    s.dim(f.X(off), f.Y(-hp - 12), f.X(Lp / 2), f.Y(-hp - 12), f'{sym("PedN_Nprov")} = {n(Nprov, 2)} in', HL if hl_prov else INK, side=1)
    s.rect(f.X(off), y_top, f.L(Nreq), f.L(hp), fill='#f6d6d3', stroke=HL, sw=1.2, op=0.8)
    s.dim(f.X(off), f.Y(-hp - 2), f.X(off + Nreq), f.Y(-hp - 2), f'{sym("PedN_Nreq")} = {n(Nreq, 2)} in', HL if name in ('PedN_N1', 'PedN_N2', 'PedN_Nreq') else INK, side=1, offset=8)
    s.text(f.X(0), f.Y(-hp - 22), 'beam end to the outside edge of the full-length pedestal; required N shaded', 8.5, GREY)
    rows = {'PedN_N1': [f'(8 + 0.02·L + 0.08·H)·(1 + 0.000125·S²)', f'L = {eq(e, "PedN_L1", 2)}, H = {eq(e, "PedN_H", 2, "ft")}', f'S = {eq(e, "PedN_S", 1)}'],
            'PedN_N2': [f'(8 + 0.02·L + 0.08·H)·(1 + 0.000125·S²)', f'L = {eq(e, "PedN_L2", 2)}, H = {eq(e, "PedN_H", 2, "ft")}', f'S = {eq(e, "PedN_S", 1)}'],
            'PedN_Nreq': [f'Max({eq(e, "PedN_N1", 2)}, {eq(e, "PedN_N2", 2)})'],
            'PedN_Nprov': [f'{eq(e, "Pedestal_length_pier", 2, "in")} / 2 − {eq(e, "PierCL_beamEnd", 2)}'],
            'PedN_margin': [f'{eq(e, "PedN_Nprov", 2)} − {eq(e, "PedN_Nreq", 2)}'],
            'DC_PedN': [f'{eq(e, "PedN_Nreq", 2)} / {eq(e, "PedN_Nprov", 2)}'],
            'Check_PedN': [f'{eq(e, "PedN_Nprov", 2)} ≥ {eq(e, "PedN_Nreq", 2)}']}
    if name == 'Check_PedN':
        s.panel(f'{sym(name)} = {escape(_txt(e, name))}', rows[name])
        s.status(PX, 150, _txt(e, name))
    else:
        s.panel(eq(e, name, 2), rows.get(name, []))
        if name == 'DC_PedN':
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


# ----------------------------------------------------------------------------- Type F service screening
def type_f(e, name):
    v = e.value
    bearing = name[-2:] if name[-2:] in ('B1', 'B2', 'B3', 'B4') else None
    titles = {'LL_atBearing': 'Largest service pedestrian reaction at the pier bearings', 'DL_BearingPad': 'Largest service dead reaction at a pad',
              'Type_F_LL_max': 'Type F service live-load limit for the skew', 'Type_F_DL_base': 'Type F base service dead-load limit for the skew',
              'Type_F_Max': 'Type F dead-load allowance with the largest live reaction', 'Check_TypeF_skew': 'Skew within the standard Type F range'}
    title = titles.get(name) or {'Type_F_DL': f'Bearing {bearing} service dead load', 'Type_F_DLallow': f'Bearing {bearing} dead-load allowance',
                                 'DC_TypeF': f'Bearing {bearing} dead load against its allowance', 'Check_TypeF': f'Bearing {bearing} Type F screening'}[name[:-3]]
    s = Svg(f'{name}: Type F', title=title + ' (SDM Table 12.5-1 style limits)')
    skew = v('PedN_S')
    # limits table
    y = 56
    s.text(20, y - 14, 'skew', 9.5, GREY, 'start')
    s.text(90, y - 14, 'LL max', 9.5, GREY, 'start')
    s.text(160, y - 14, 'DL base', 9.5, GREY, 'start')
    for lo, hi, ll, dl in ((0, 5, 150, 290), (5, 30, 120, 139)):
        hit = lo < abs(skew) <= hi or (lo == 0 and abs(skew) <= hi)
        if hit:
            s.rect(14, y - 12, 220, 18, fill='#fbe9e7', stroke='none')
        s.text(20, y + 1, f'≤ {hi}°', 10, HL if hit else INK, 'start', 'bold' if hit else 'normal')
        s.text(90, y + 1, f'{ll} kip', 10, HL if hit else INK, 'start', 'bold' if hit else 'normal')
        s.text(160, y + 1, f'{dl} kip', 10, HL if hit else INK, 'start', 'bold' if hit else 'normal')
        y += 20
    s.text(20, y + 4, f'skew = {n(skew, 1)}°; allowance = DL base + 1.75·(LL max − LL)', 9, GREY, 'start')
    # bars per bearing: DL vs allowance, LL vs limit
    y0 = 140
    s.text(20, y0 - 10, 'service reactions by bearing, kip', 9.5, GREY, 'start')
    llmax = v('Type_F_LL_max', 'kip')
    top = max(v('Type_F_DLallow_' + b, 'kip') for b in ('B1', 'B2', 'B3', 'B4'))
    for i, b in enumerate(('B1', 'B2', 'B3', 'B4')):
        yy = y0 + i * 48
        dl, al, ll = v('Type_F_DL_' + b, 'kip'), v('Type_F_DLallow_' + b, 'kip'), v('PL_' + b, 'kip')
        hit = bearing == b or name in ('LL_atBearing', 'DL_BearingPad', 'Type_F_Max')
        s.text(16, yy + 11, b, 10, HL if bearing == b else INK, 'start', 'bold')
        kx = 300 / top
        s.rect(44, yy, al * kx, 14, fill='#f3f6f8', stroke=FAINT)
        s.rect(44, yy, dl * kx, 14, fill=HL if (hit and 'DL' in name or name.startswith('DC') or name.startswith('Check_TypeF_B')) and bearing in (b, None) else '#9fb3c8', stroke='none')
        s.text(50 + al * kx, yy + 11, f'DL {n(dl, 1)} of {n(al, 1)}', 9, INK, 'start')
        s.rect(44, yy + 18, llmax * kx, 10, fill='#f3f6f8', stroke=FAINT)
        s.rect(44, yy + 18, ll * kx, 10, fill=TEAL if ('LL' in name or name.startswith('Check_TypeF_B')) and bearing in (b, None) else '#b7cfd9', stroke='none')
        s.text(50 + llmax * kx, yy + 27, f'LL {n(ll, 1)} of {n(llmax, 0)}', 9, INK, 'start')
    rows = {'LL_atBearing': [f'Max({", ".join(f"PL_{b} = {n(v("PL_" + b, "kip"), 2)}" for b in ("B1", "B2", "B3", "B4"))})'],
            'DL_BearingPad': [f'Max(DC_super + DW at B1 … B4)', f'B1 {n(v("DC_super_B1", "kip") + v("DW_B1", "kip"), 2)}, B3 {n(v("DC_super_B3", "kip") + v("DW_B3", "kip"), 2)} kip'],
            'Type_F_LL_max': [f'|S| = {n(abs(skew), 1)}° ≤ 5°: 150 kip' if abs(skew) <= 5 else f'|S| = {n(abs(skew), 1)}° ≤ 30°: 120 kip'],
            'Type_F_DL_base': [f'|S| = {n(abs(skew), 1)}° ≤ 5°: 290 kip' if abs(skew) <= 5 else f'|S| = {n(abs(skew), 1)}° ≤ 30°: 139 kip'],
            'Type_F_Max': [f'{eq(e, "Type_F_DL_base", 0)} + 1.75·({eq(e, "Type_F_LL_max", 0)} − {eq(e, "LL_atBearing", 2)})'],
            'Check_TypeF_skew': [f'|{eq(e, "PedN_S", 1)}| ≤ 30°']}
    if bearing:
        rows = {'Type_F_DL': [f'{eq(e, "DC_super_" + bearing, 2)} + {eq(e, "DW_" + bearing, 2)}'],
                'Type_F_DLallow': [f'{eq(e, "Type_F_DL_base", 0)} + 1.75·({eq(e, "Type_F_LL_max", 0)} − {eq(e, "PL_" + bearing, 2)})'],
                'DC_TypeF': [f'{eq(e, "Type_F_DL_" + bearing, 2)} / {eq(e, "Type_F_DLallow_" + bearing, 2)}'],
                'Check_TypeF': [f'skew {_txt(e, "Check_TypeF_skew")}', f'{eq(e, "PL_" + bearing, 2)} ≤ {eq(e, "Type_F_LL_max", 0)}',
                                f'{eq(e, "Type_F_DL_" + bearing, 2)} ≤ {eq(e, "Type_F_DLallow_" + bearing, 2)}']}[name[:-3]]
    if name.startswith('Check'):
        s.panel(f'{sym(name)} = {escape(_txt(e, name))}', rows)
        s.status(PX, 180, _txt(e, name))
    else:
        s.panel(eq(e, name, 2), rows)
        if name.startswith('DC_'):
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


# ----------------------------------------------------------------------------- rotations on a level seat
def _span(name):
    return '2' if name.endswith('_2') else '1' if name.endswith('_1') else None


def rotation(e, name):
    v = e.value
    sp = _span(name)
    titles = {'BP_grade': 'Profile grade of the span at the pier', 'BP_angle': 'Profile angle at a level seat', 'BP_bare120': '120-day bare-beam rotation at the pier',
              'BP_nc120': '120-day rotation with noncomposite dead load', 'BP_full120': '120-day rotation with all static dead load',
              'BP_full240': '240-day rotation with all static dead load', 'BP_bare240': '240-day bare-beam rotation', 'BP_release_full': 'Release rotation with all static dead load',
              'BP_static_max': 'Absolute static rotation envelope', 'BP_live_pier': 'Cyclic pedestrian rotation at the pier',
              'BP_opposite': 'Cyclic rotation opposes the static rotation'}
    base = name[:-2] if sp else name
    full = {'BP_static_max': 'Governing static rotation at the four pier bearings', 'BP_cyclic_max': 'Governing cyclic rotation magnitude',
            'BP_static_ratio': 'Static rotation against the pad limit', 'BP_cyclic_ratio': 'Cyclic rotation against the pad limit',
            'BP_transverse_difference': 'Transverse height difference across the pad', 'BP_rotation_check': 'Level-seat rotation screen'}
    title = full.get(name) or (titles.get(base, name) + (f', Span {sp}' if sp else ''))
    s = Svg(f'{name}: rotation', title=title)
    # beam end on the level seat (sketch) with the sign convention
    x0, y0 = 30, 70
    s.rect(x0, y0 + 60, 150, 16, fill='#eef2f5', stroke=INK)
    s.text(x0 + 75, y0 + 90, 'level pedestal top (slope 0)', 8.5, GREY)
    s.rect(x0 + 20, y0 + 52, 110, 8, fill=PAD, stroke='none')
    ang = v('BP_angle_' + (sp or '1'), 'rad')
    rot = v('BP_full240_' + (sp or '1'), 'rad') if base not in ('BP_grade', 'BP_angle') else ang
    tilt = max(-0.08, min(0.08, rot * 12))
    cx, cy = x0 + 75, y0 + 52
    pts = [(-70, -34), (70, -34), (70, 0), (-70, 0)]
    cos, sin = math.cos(tilt), math.sin(tilt)
    s.poly([(cx + px * cos - py * sin, cy + px * sin + py * cos) for px, py in pts], fill=SLAB, stroke=INK)
    s.line(cx - 90, cy, cx + 90, cy, GREY, 0.8, '4 2')
    s.text(x0 - 14, y0 - 2, f'beam end on the pier, Span {sp or "1"} (rotation ×12)', 8.5, GREY, 'start')
    s.tag(cx + 92, cy + (14 if tilt >= 0 else -8), f'{n(rot, 5)} rad', HL, 'start')
    # stage chart
    sp_c = sp or '1'
    stages = ['release', '120 d', '240 d']
    full_s = [v('BP_release_full_' + sp_c, 'rad'), v('BP_full120_' + sp_c, 'rad'), v('BP_full240_' + sp_c, 'rad')]
    bare = [v('BP_bare120_' + sp_c, 'rad'), v('BP_bare240_' + sp_c, 'rad')]
    nc = v('BP_nc120_' + sp_c, 'rad')
    live = v('BP_live_pier_' + sp_c, 'rad')
    lim_s, lim_c = v('BP_static_limit', 'rad'), v('BP_cyclic_limit', 'rad')
    L, T, Wd, Hd = 236, 62, 156, 200
    ys = full_s + bare + [nc, live, lim_s, -lim_s, lim_c, -lim_c]
    y0r, y1r = min(ys) * 1.15, max(ys) * 1.15
    X = lambda i: L + 20 + i * (Wd - 40) / 2
    Y = lambda y: T + Hd - (y - y0r) / (y1r - y0r) * Hd
    s.line(L, T, L, T + Hd, INK)
    s.line(L, Y(0), L + Wd, Y(0), GREY, 0.8)
    for i, st in enumerate(stages):
        s.text(X(i), T + Hd + 14, st, 9, GREY)
    for yv, lab, color in ((lim_s, f'+{sym("BP_static_limit")} = {n(lim_s, 4)}', AMBER), (-lim_s, f'−{n(lim_s, 4)}', AMBER), (lim_c, f'cyclic ±{n(lim_c, 3)}', TEAL), (-lim_c, '', TEAL)):
        s.line(L, Y(yv), L + Wd, Y(yv), color, 1, '5 3')
        if lab:
            s.tag(L + Wd, Y(yv) - 4, lab, color, 'end')
    hl_key = base
    def series(points, color, key, label):
        s.poly([(X(i), Y(yv)) for i, yv in points], stroke=HL if hl_key == key else color, sw=2, closed=False)
        for i, yv in points:
            s.circle(X(i), Y(yv), 3.5, fill=HL if hl_key == key else color)
        s.tag(X(points[-1][0]) + 6, Y(points[-1][1]) + 4, label, HL if hl_key == key else color, 'start')
    series([(0, full_s[0]), (1, full_s[1]), (2, full_s[2])], BLUE, 'BP_full', 'all static DL')
    series([(1, bare[0]), (2, bare[1])], '#9fb3c8', 'BP_bare', 'bare beam')
    series([(1, nc)], PURPLE, 'BP_nc120', '+ NC DL')
    s.arrow(X(2) + 40, Y(0), X(2) + 40, Y(live), HL if base == 'BP_live_pier' else TEAL, 1.6, 6)
    s.tag(X(2) + 46, Y(live) + 4, f'live {n(live, 5)}', HL if base == 'BP_live_pier' else TEAL, 'start')
    for key in ('BP_full120', 'BP_full240', 'BP_release_full', 'BP_bare120', 'BP_bare240'):
        if base == key:
            idx = {'BP_release_full': 0, 'BP_full120': 1, 'BP_bare120': 1, 'BP_full240': 2, 'BP_bare240': 2}[key]
            yv = v(name, 'rad')
            s.circle(X(idx), Y(yv), 7, fill='none', stroke=HL, sw=2)
    s.text(L + Wd / 2, T - 10, 'signed rotation at the pier bearing, rad', 8.5, GREY)
    g = {'1': ('PGL_start_elev', 'PGL_pier_elev', 'PedN_L1'), '2': ('PGL_pier_elev', 'PGL_end_elev', 'PedN_L2')}
    rows = {'BP_grade': [f'({eq(e, g[sp_c][1], 3, "ft")} − {eq(e, g[sp_c][0], 3, "ft")}) / {eq(e, g[sp_c][2], 2)}'] if sp else [],
            'BP_angle': [f'atan({eq(e, "BP_grade_" + sp_c, 6)})', ('a level seat sees the full profile angle', GREY)],
            'BP_bare120': [f'{sym("BP_angle_" + sp_c)} ∓ {sym("BP_day120_" + sp_c)}', f'camber slope at 120 d: {val(e, "BP_day120_" + sp_c, 4, "deg")}'],
            'BP_nc120': [f'… ∓ ({sym("BP_day120_" + sp_c)} + {sym("BP_nc_" + sp_c)})', f'noncomposite DL rotation {val(e, "BP_nc_" + sp_c, 4, "deg")}'],
            'BP_full120': [f'… ∓ ({sym("BP_day120_" + sp_c)} + {sym("BP_nc_" + sp_c)} + {sym("BP_comp_" + sp_c)})', f'composite DL rotation {val(e, "BP_comp_" + sp_c, 4, "deg")}'],
            'BP_full240': [f'… ∓ ({sym("BP_day240_" + sp_c)} + {sym("BP_nc_" + sp_c)} + {sym("BP_comp_" + sp_c)})'],
            'BP_bare240': [f'{sym("BP_angle_" + sp_c)} ∓ {sym("BP_day240_" + sp_c)}'],
            'BP_release_full': [f'… ∓ ({sym("BP_release_" + sp_c)} + {sym("BP_nc_" + sp_c)} + {sym("BP_comp_" + sp_c)})'],
            'BP_static_max': ([f'Max(|{eq(e, "BP_bare240_" + sp_c, 5)}|, |{eq(e, "BP_release_full_" + sp_c, 5)}|)'] if sp else
                              [f'Max({eq(e, "BP_static_max_1", 5)}, {eq(e, "BP_static_max_2", 5)})']),
            'BP_live_pier': [f'{"−" if sp_c == "1" else ""}{eq(e, "BP_live_" + sp_c, 5, "rad")}', ('sign flipped to the pier-side convention', GREY)],
            'BP_opposite': [f'{eq(e, "BP_full120_" + sp_c, 5)} × live ≤ 0', f'{eq(e, "BP_full240_" + sp_c, 5)} × live ≤ 0'],
            'BP_cyclic_max': [f'Max(|{eq(e, "BP_live_pier_1", 5)}|, |{eq(e, "BP_live_pier_2", 5)}|)'],
            'BP_static_ratio': [f'{eq(e, "BP_static_max", 5)} / {eq(e, "BP_static_limit", 4)}'],
            'BP_cyclic_ratio': [f'{eq(e, "BP_cyclic_max", 5)} / {eq(e, "BP_cyclic_limit", 4)}'],
            'BP_transverse_difference': [f'|{eq(e, "BP_transverse_slope", 3)}| × {eq(e, "Bearing_pad_width", 1)}', ('SDG detailing trigger 1/8 in', GREY)],
            'BP_rotation_check': [f'static ratio {val(e, "BP_static_ratio", 3)} ≤ 1, cyclic ratio {val(e, "BP_cyclic_ratio", 3)} ≤ 1',
                                  f'opposite: {_txt(e, "BP_opposite_1")}, {_txt(e, "BP_opposite_2")}', f'transverse Δ {val(e, "BP_transverse_difference", 3)} ≤ 1/8 in']}
    key = base if sp else name
    text_result = name in ('BP_rotation_check',) or base == 'BP_opposite'
    if text_result:
        s.panel(f'{sym(name)} = {escape(_txt(e, name))}', rows.get(key, []))
        s.status(PX, 180, _txt(e, name))
    else:
        s.panel(eq(e, name, 5 if name not in ('BP_transverse_difference',) else 3), rows.get(key, []))
        if name in ('BP_static_ratio', 'BP_cyclic_ratio'):
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


# ----------------------------------------------------------------------------- longitudinal movement
def movement(e, name):
    v = e.value
    titles = {'BP_thermal': 'Thermal movement bound at one pad over the whole bridge length', 'BP_creep': 'Creep and shrinkage shortening from 120 to 240 days',
              'BP_movement': 'Longitudinal movement bound at the pad', 'BP_movement_ratio': 'Movement against the pad shear-deflection limit',
              'BP_movement_check': 'Thermal and creep movement screen', 'BP_type_check': 'Pad selection and orientation used by the check',
              'BP_level_seat_result': 'Conditional disposition of the level seats'}
    s = Svg(f'{name}: movement', title=titles.get(name, name))
    th, cr, mv, lim = v('BP_thermal', 'in'), v('BP_creep', 'in'), v('BP_movement', 'in'), v('Bearing_pad_shearLimit', 'in')
    t = v('Bearing_pad_thickness', 'in')
    # deformed pad sketch
    x0, y0, wp, hp = 60, 80, 150, 40
    s.rect(x0 - 30, y0 + hp, wp + 60, 14, fill='#eef2f5', stroke=INK)
    s.text(x0 + wp / 2, y0 + hp + 26, 'pedestal', 8.5, GREY)
    dx = 60 * min(mv / max(lim, 1e-6), 1.5)
    s.poly([(x0, y0 + hp), (x0 + wp, y0 + hp), (x0 + wp + dx, y0), (x0 + dx, y0)], fill=PAD, stroke='none', op=0.9)
    s.rect(x0 + dx - 10, y0 - 14, wp + 20, 14, fill=SLAB, stroke=INK)
    s.text(x0 + dx + wp / 2, y0 - 18, 'beam', 8.5, GREY)
    s.dim(x0, y0 - 24, x0 + dx, y0 - 24, f'Δ = {n(mv, 3)} in', HL if name in ('BP_movement', 'BP_movement_ratio', 'BP_movement_check') else INK, side=-1)
    s.dim(x0 + wp + 40, y0, x0 + wp + 40, y0 + hp, f't = {n(t, 4)} in', INK, side=1)
    s.text(x0 - 30, y0 + hp + 50, f'pad shear deflection limit {sym("Bearing_pad_shearLimit")} = {n(lim, 2)} in (Type F, G = {n(v("Bearing_pad_G", "psi"), 0)} psi)', 9, GREY, 'start')
    # bars
    yb = 190
    hl = {'BP_thermal': 0, 'BP_creep': 1, 'BP_movement': 2}.get(name, 2)
    s.bars(150, yb, [(f'{sym("BP_thermal")} thermal', th), (f'{sym("BP_creep")} creep + shrinkage', cr), (f'{sym("BP_movement")} total', mv), ('shear limit', lim, AMBER)], 200, hl, 3, 'in')
    rows = {'BP_thermal': [f'{eq(e, "α_T", 7)} × 0.65 × ({eq(e, "T_high", 0)} − {eq(e, "T_low", 0)})°F', f'× {eq(e, "TotalSpan", 2, "ft")}', ('entire bridge length at one pad: conservative bound', GREY)],
            'BP_creep': [f'|{eq(e, "BP_bottom240_1", 3)} − {eq(e, "BP_bottom120_1", 3)}|', f'+ |{eq(e, "BP_bottom240_2", 3)} − {eq(e, "BP_bottom120_2", 3)}|'],
            'BP_movement': [f'{eq(e, "BP_thermal", 3)} + {eq(e, "BP_creep", 3)}'],
            'BP_movement_ratio': [f'{eq(e, "BP_movement", 3)} / {eq(e, "Bearing_pad_shearLimit", 2)}'],
            'BP_movement_check': [f'ratio {val(e, "BP_movement_ratio", 3)} ≤ 1', ('wind or other lateral shear is additional', GREY)],
            'BP_type_check': [f'type {escape(_txt(e, "Bearing_pad_type"))}, G = {val(e, "Bearing_pad_G", 0, "psi")}', f'{val(e, "BearingPad_length", 0)} × {val(e, "Bearing_pad_width", 0)} × {val(e, "Bearing_pad_thickness", 4)}',
                              f'{n(v("Bearing_pad_count"), 0)} pads, buildup {val(e, "Bearing_supportBuildup", 0)}'],
            'BP_level_seat_result': [f'type {_txt(e, "BP_type_check")}, rotation {_txt(e, "BP_rotation_check")}', f'movement {_txt(e, "BP_movement_check")}',
                                     f'Type F B1–B4: {", ".join(_txt(e, "Check_TypeF_" + b) for b in ("B1", "B2", "B3", "B4"))}']}
    if name in ('BP_movement_check', 'BP_type_check', 'BP_level_seat_result'):
        s.panel(f'{sym(name)}', [(escape(_txt(e, name)[:58]), HL if 'FAIL' in _txt(e, name) else TEAL)] + rows.get(name, []))
        s.status(PX, 170, _txt(e, name))
    else:
        s.panel(eq(e, name, 3), rows.get(name, []))
        if name == 'BP_movement_ratio':
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


drawer = make_drawer({'Cap_width_min': cap_chain, 'BP_thermal': movement, 'BP_creep': movement, 'BP_movement': movement, 'BP_movement_ratio': movement,
                      'BP_movement_check': movement, 'BP_type_check': movement, 'BP_level_seat_result': movement},
                     [(r'^(PedN_|DC_PedN|Check_PedN)', support), (r'^(LL_atBearing|DL_BearingPad|Type_F_|Check_TypeF|DC_TypeF)', type_f), (r'^BP_', rotation)])
