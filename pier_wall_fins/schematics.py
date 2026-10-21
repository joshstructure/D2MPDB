"""'What it represents' drawings for the pier wall hairpins and fin plates calculation (C006).

Scenes drawn from the current case: the wall in elevation with its four pipe piles, six fins and the continuous-beam
gravity model (spans, moments, reactions); the fin detail at one pile (plate, round saddle, hairpins, development
lengths); the fin root as a steel section under its shear and biaxial moments, with the LTB curve; the horizontal
out-of-plane wall strip under direct wind with its reinforced section; the face grid and cross-tie detailing; and the
status checklists.
"""
import math
import re
from html import escape
from calc_common.schematics import (Svg, Frame, sym, val, eq, n, make_drawer, schematic as _schematic, meaning as _meaning,
                                    INK, GREY, FAINT, HL, BLUE, TEAL, AMBER, PURPLE, CONC, SOIL, SLAB, STEEL, PAD, PX)
from .model import SPEC

FIN_OF = {'F1': 'R_1', 'F2': 'R_2', 'F3': 'R_3', 'F4': 'R_3', 'F5': 'R_2', 'F6': 'R_1'}


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)


def _txt(e, name):
    return str(e.engine.get(name))


# ----------------------------------------------------------------------------- wall elevation and the gravity model
def _wall(s, e, left, top, width, height, fins=True, hl_fin=None, piles=True):
    v = e.value
    Lw, Hw, Dp, Sp, ee = v('L_w', 'in'), v('H_w', 'in'), v('D_p', 'in'), v('S_p', 'in'), v('e_end', 'in')
    zs = v('z_seat', 'in')
    f = Frame(-12, Lw + 12, -14, Hw + 10, left, top, width, height)
    s.rect(f.X(0), f.Y(Hw), f.L(Lw), f.L(Hw), fill=CONC, stroke=INK)
    s.text(f.X(Lw / 2), f.Y(Hw) - 5, f'pier wall {n(Lw / 12, 2)} ft × {n(Hw / 12, 2)} ft × {n(v("t_w", "in"), 0)} in, broad face', 8.5, GREY)
    xs = [ee + i * Sp for i in range(int(v('N_p')))]
    if piles:
        for i, x in enumerate(xs, 1):
            s.rect(f.X(x - Dp / 2), f.Y(Hw - 6), f.L(Dp), f.L(Hw + 6), fill='#eef2f5', stroke=GREY, sw=0.9, dash='4 2')
            s.text(f.X(x), f.Y(-10), f'pile {i}', 8.5, GREY)
    if fins:
        xf = [v(f'x_F{i}', 'in') for i in range(1, 7)]
        for i, x in enumerate(xf, 1):
            hit = hl_fin == f'F{i}'
            s.rect(f.X(x) - 4, f.Y(zs), 8, f.L(v('h_p', 'in')), fill=HL if hit else PAD, stroke='none')
            s.circle(f.X(x), f.Y(zs), 3, fill=HL if hit else INK)
            s.text(f.X(x), f.Y(zs) - 7, f'F{i}', 8.5, HL if hit else INK, 'middle', 'bold' if hit else 'normal')
    return f, xs


def _beam_model(s, e, left, top, width, hl=None):
    """Continuous beam on six fin supports: overhang a_o, spans L_a, L_b, L_a, L_b, L_a, overhang a_o."""
    v = e.value
    Lw = v('L_w', 'in')
    xf = [v(f'x_F{i}', 'in') for i in range(1, 7)]
    k = width / Lw
    X = lambda x: left + x * k
    y = top
    s.line(X(0), y, X(Lw), y, INK, 2.2)
    s.udl(X(0) + 2, X(Lw) - 2, y - 2, 14, -1, BLUE, 14, f'{sym("w_g")} = {val(e, "w_g", 3)}')
    for i, x in enumerate(xf, 1):
        s.poly([(X(x), y + 1), (X(x) - 5, y + 10), (X(x) + 5, y + 10)], fill=INK, stroke=INK)
        rname = FIN_OF[f'F{i}']
        color = HL if hl == rname else TEAL
        s.arrow(X(x), y + 40, X(x), y + 12, color, 1.6, 6)
        s.tag(X(x), y + 52, f'{sym(rname)}', color)
    spans = [(0, xf[0], 'a_o'), (xf[0], xf[1], 'L_a'), (xf[1], xf[2], 'L_b'), (xf[2], xf[3], 'L_a'), (xf[3], xf[4], 'L_b'), (xf[4], xf[5], 'L_a'), (xf[5], Lw, 'a_o')]
    for x0, x1, lab in spans:
        s.dim(X(x0), y - 44, X(x1), y - 44, sym(lab) if lab != 'a_o' or x0 == 0 else '', HL if hl == lab else INK, side=-1, offset=8)
    return X, y


def wall(e, name):
    v = e.value
    titles = {'n_fin': 'Six fins: one inward fin at each end pile, two at each interior pile', 'e_end': 'Wall end to the outer pile centerline',
              's_fin_nom': 'Nominal hairpin-group spacing between adjacent piles', 's_pipe_nom': 'Nominal group spacing across an interior pile',
              'L_a': 'Clear span between fin force points in adjacent pile bays', 'L_b': 'Force-point spacing across an interior pipe', 'a_o': 'Wall-end overhang to the first force point',
              'W_w': 'Gross wall weight', 'w_g': 'Uniform wall gravity line load', 'M_0': 'Overhang end moment', 'K_11': 'Three-moment coefficient', 'K_12': 'Three-moment coefficient',
              'K_22': 'Three-moment coefficient', 'B_1': 'Three-moment right-hand side', 'B_2': 'Three-moment right-hand side', 'Δ_K': 'Determinant of the reduced three-moment system',
              'M_1': 'Support moment at F2 and F5', 'M_2': 'Support moment at F3 and F4', 'R_1': 'Wall reaction at F1 and F6', 'R_2': 'Wall reaction at F2 and F5', 'R_3': 'Wall reaction at F3 and F4',
              'R_max': 'Largest wall reaction', 'V_h_u': 'Factored wall load into one hairpin group', 'Chk_reactions': 'Six reactions reproduce the wall weight',
              'Chk_model': 'Validity of the symmetric four-pile, six-fin model', 'F_w_III': 'Strength III broad-face wind on the wall', 'V_conc': 'Gross concrete volume',
              'S_conc': 'Gross exterior surface', 'R_VS': 'Volume to surface ratio', 'Status_mass': 'FDOT mass-concrete screen', 'Chk_joints': 'Wall length against the 30 ft joint screen',
              'z_wall_bottom': 'Wall-bottom elevation', 'Δ_ground': 'Wall bottom relative to the terrain', 'c_pipe_end': 'Concrete end envelope at the adverse pile position', 'L_strip': 'Support-center span of a horizontal wall strip'}
    xf_m = re.match(r'^x_F(\d)$', name)
    title = titles.get(name) or (f'Wall station of force point F{xf_m.group(1)}' if xf_m else name)
    s = Svg(f'{name}: wall', title=title)
    hl_fin = f'F{xf_m.group(1)}' if xf_m else None
    f, xs = _wall(s, e, 12, 36, PX - 40, 150, hl_fin=hl_fin)
    Lw, Hw, ee, Sp, Dp = v('L_w', 'in'), v('H_w', 'in'), v('e_end', 'in'), v('S_p', 'in'), v('D_p', 'in')
    if name in ('e_end', 'c_pipe_end', 'n_fin'):
        s.dim(f.X(0), f.Y(Hw + 6), f.X(ee), f.Y(Hw + 6), f'{sym("e_end")} = {n(ee, 2)} in', HL if name != 'n_fin' else INK, side=-1, offset=8)
        if name == 'c_pipe_end':
            s.dim(f.X(0), f.Y(Hw * 0.5), f.X(ee - Dp / 2 - v('T_pos', 'in')), f.Y(Hw * 0.5), f'{sym("c_pipe_end")}', HL, side=1)
    if xf_m:
        s.dim(f.X(0), f.Y(-6), f.X(v(name, 'in')), f.Y(-6), f'{sym(name)} = {n(v(name, "in"), 2)} in', HL, side=1, offset=8)
    if name in ('s_fin_nom', 's_pipe_nom', 'L_a', 'L_b'):
        r = v('r_nom' if 'nom' in name else 'r_f', 'in')
        if name in ('s_fin_nom', 'L_a'):
            s.dim(f.X(xs[0] + r), f.Y(Hw + 6), f.X(xs[1] - r), f.Y(Hw + 6), f'{sym(name)} = {n(v(name, "in"), 2)} in', HL, side=-1, offset=8)
        else:
            s.dim(f.X(xs[1] - r), f.Y(Hw + 6), f.X(xs[1] + r), f.Y(Hw + 6), f'{sym(name)} = {n(v(name, "in"), 2)} in', HL, side=-1, offset=8)
    if name == 'F_w_III':
        s.wind(f.X(0) - 2, f.Y(Hw) + 4, f.Y(0) - 4, 24, 1, HL, 14, f'{sym("p_III")}')
    if name in ('z_wall_bottom', 'Δ_ground'):
        s.line(f.X(-12), f.Y(0), f.X(Lw + 12), f.Y(0), HL, 1.2)
        s.tag(f.X(Lw + 10), f.Y(0) + 12, f'wall bottom {val(e, "z_wall_bottom", 2, "ft")}', HL, 'end')
        s.tag(f.X(Lw + 10), f.Y(Hw) - 4 - 10, f'wall top (cap soffit) {val(e, "z_wall_top", 2, "ft")}', GREY, 'end')
    # gravity model beneath
    model_names = {'M_0', 'K_11', 'K_12', 'K_22', 'B_1', 'B_2', 'Δ_K', 'M_1', 'M_2', 'R_1', 'R_2', 'R_3', 'R_max', 'V_h_u', 'Chk_reactions', 'Chk_model', 'w_g', 'W_w', 'L_a', 'L_b', 'a_o'}
    if name in model_names or xf_m:
        governing = 'R_' + str(max((1, 2, 3), key=lambda i: v(f'R_{i}', 'kip')))
        hl = name if name in ('R_1', 'R_2', 'R_3', 'L_a', 'L_b', 'a_o') else FIN_OF.get('F' + xf_m.group(1)) if xf_m else {'R_max': governing, 'V_h_u': governing}.get(name)
        X, y = _beam_model(s, e, 40, 246, PX - 90, hl=hl)
        if name in ('M_0', 'M_1', 'M_2'):
            xf = [v(f'x_F{i}', 'in') for i in range(1, 7)]
            at = {'M_0': [xf[0], xf[5]], 'M_1': [xf[1], xf[4]], 'M_2': [xf[2], xf[3]]}[name]
            for x in at:
                s.moment(X(x), y - 48, 9, True, HL, '')
            s.tag(X(at[0]) + 14, y - 46, f'{sym(name)} = {val(e, name, 2)}', HL, 'start')
    rows = {'n_fin': [f'2·{eq(e, "N_p", 0)} − 2'],
            'e_end': [f'({eq(e, "L_w", 2, "in")} − ({eq(e, "N_p", 0)} − 1)·{eq(e, "S_p", 2, "in")}) / 2'],
            'c_pipe_end': [f'{eq(e, "e_end", 2)} − {eq(e, "D_p", 1)}/2 − {eq(e, "T_pos", 2)}', ('concrete beyond the pipe at the adverse position', GREY)],
            's_fin_nom': [f'{eq(e, "S_p", 2, "in")} − 2·{eq(e, "r_nom", 3)}'], 's_pipe_nom': [f'2·{eq(e, "r_nom", 3)}'],
            'L_a': [f'{eq(e, "S_p", 2, "in")} − 2·{eq(e, "r_f", 3)}'], 'L_b': [f'2·{eq(e, "r_f", 3)}'], 'a_o': [f'{eq(e, "e_end", 2)} + {eq(e, "r_f", 3)}'],
            'W_w': [f'{eq(e, "L_w", 2, "ft")} × {eq(e, "t_w", 0, "in")} × {eq(e, "H_w", 3, "ft")} × {eq(e, "γ_c", 0, "pcf")}', ('pile displacement not deducted', GREY)],
            'w_g': [f'{eq(e, "W_w", 2)} / {eq(e, "L_w", 2, "ft")}'],
            'M_0': [f'−{sym("w_g")}·{sym("a_o")}²/2 = −{n(v("w_g", "kip/in"), 4)} kip/in × {n(v("a_o", "in"), 2)}²/2'],
            'K_11': [f'2·({eq(e, "L_a", 2)} + {eq(e, "L_b", 2)})'], 'K_12': [f'= {eq(e, "L_b", 2)}'], 'K_22': [f'2·{eq(e, "L_b", 2)} + 3·{eq(e, "L_a", 2)}'],
            'B_1': [f'−{sym("w_g")}·({sym("L_a")}³ + {sym("L_b")}³)/4 − {sym("M_0")}·{sym("L_a")}'], 'B_2': [f'−{sym("w_g")}·({sym("L_a")}³ + {sym("L_b")}³)/4'],
            'Δ_K': [f'{eq(e, "K_11", 2)}·{eq(e, "K_22", 2)} − {eq(e, "K_12", 2)}²'],
            'M_1': [f'({sym("B_1")}·{sym("K_22")} − {sym("B_2")}·{sym("K_12")}) / {sym("Δ_K")}', ('three-moment equation, symmetric half', GREY)],
            'M_2': [f'({sym("K_11")}·{sym("B_2")} − {sym("K_12")}·{sym("B_1")}) / {sym("Δ_K")}'],
            'R_1': [f'{sym("w_g")}·{sym("a_o")} + {sym("w_g")}·{sym("L_a")}/2 + ({sym("M_1")} − {sym("M_0")})/{sym("L_a")}'],
            'R_2': [f'{sym("w_g")}·({sym("L_a")}+{sym("L_b")})/2 + ({sym("M_0")}−{sym("M_1")})/{sym("L_a")} + ({sym("M_2")}−{sym("M_1")})/{sym("L_b")}'],
            'R_3': [f'{sym("w_g")}·({sym("L_b")}+{sym("L_a")})/2 + ({sym("M_1")}−{sym("M_2")})/{sym("L_b")}'],
            'R_max': [f'Max({eq(e, "R_1", 2)}, {eq(e, "R_2", 2)}, {eq(e, "R_3", 2)})'],
            'V_h_u': [f'{eq(e, "γ_DC", 2)} × {eq(e, "R_max", 2)}', ('governing factored load into one hairpin group', GREY)],
            'Chk_reactions': [f'2·({sym("R_1")}+{sym("R_2")}+{sym("R_3")}) = {n(2 * (v("R_1", "kip") + v("R_2", "kip") + v("R_3", "kip")), 3)} kip', f'{eq(e, "W_w", 3)}'],
            'Chk_model': [f'N_p = {n(v("N_p"), 0)}, n_h = {n(v("n_h"), 0)}, α_h = {n(v("α_h"), 2)}', f'L_a, L_b > 0, a_o ≥ 0, min R = {n(min(v("R_1", "kip"), v("R_2", "kip"), v("R_3", "kip")), 2)} kip ≥ 0'],
            'F_w_III': [f'{eq(e, "p_III", 4, "ksf")} × {eq(e, "L_w", 2, "ft")} × {eq(e, "H_w", 3, "ft")}'],
            'V_conc': [f'{eq(e, "L_w", 2, "ft")} × {eq(e, "t_w", 0, "in")} × {eq(e, "H_w", 3, "ft")}'], 'S_conc': ['2·(L·t + L·H + t·H), all six faces'],
            'R_VS': [f'{eq(e, "V_conc", 1)} / {eq(e, "S_conc", 1)}'],
            'Status_mass': [f'min dimension {n(min(v("L_w", "ft"), v("t_w", "ft"), v("H_w", "ft")), 2)} ft > 3 ft?', f'{eq(e, "R_VS", 3)} > 1 ft?'],
            'Chk_joints': [f'{eq(e, "L_w", 2, "ft")} ≤ 30 ft (SDG 3.10.C)'],
            'z_wall_bottom': [f'{eq(e, "z_wall_top", 3, "ft")} − {eq(e, "H_w", 3, "ft")}'], 'Δ_ground': [f'{eq(e, "z_wall_bottom", 3, "ft")} − {eq(e, "Terrain_elev", 3, "ft")}', ('verify the intended bottom elevation', GREY)],
            'L_strip': [f'= {eq(e, "S_p", 2, "ft")}', ('support-center span of the horizontal strip', GREY)]}
    if xf_m:
        rows[name] = [f'{sym("a_o")} + spans up to F{xf_m.group(1)}', f'{sym("a_o")} = {val(e, "a_o", 2)}, {sym("L_a")} = {val(e, "L_a", 2)}, {sym("L_b")} = {val(e, "L_b", 2)}']
    text_result = name.startswith(('Chk', 'Status'))
    if text_result:
        s.panel(f'{sym(name)}', [(escape(_txt(e, name)[:52]), HL if 'FAIL' in _txt(e, name) or 'MASS' in _txt(e, name) else TEAL)] + rows.get(name, []))
        s.status(PX, 180, _txt(e, name))
    else:
        s.panel(eq(e, name, 3), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- fin detail at one pile
def _fin(s, e, left, top, width, height, hl=None):
    """Side elevation at an interior pile: pipe, fin plate, round saddle, two hairpins; heights above the wall bottom."""
    v = e.value
    Dp, ap, hp, tp = v('D_p', 'in'), v('a_p', 'in'), v('h_p', 'in'), v('t_p', 'in')
    Hw, zs, zr, Ds, dh = v('H_w', 'in'), v('z_seat', 'in'), v('z_root', 'in'), v('D_s', 'in'), v('d_h', 'in')
    x1, x2, eh, ztip, lz, ct = v('x_h1', 'in'), v('x_h2', 'in'), v('e_h', 'in'), v('z_tip', 'in'), v('l_zone', 'in'), v('c_top', 'in')
    lav = v('l_av', 'in')
    root = Dp / 2                                   # fin root plane at the pipe tangent
    col = lambda key, default=INK: HL if hl == key else default
    # broken elevation: the top region (fin, saddle, hairpin crowns) and the tail region at one scale, the leg between compressed
    z_lo, z_hi = ztip + 8, zs - hp - 6
    gap_px = 26
    k = min((height - gap_px) / ((Hw + 6 - z_hi) + z_lo + 4), width / (Dp + ap + 56))
    X = lambda x: left + (x + Dp / 2 + 10) * k
    y_top = top
    y_hi = y_top + (Hw + 6 - z_hi) * k              # pixel of z_hi (bottom of the upper region)
    y_lo = y_hi + gap_px                             # pixel of z_lo (top of the lower region)

    def Y(z):
        if z >= z_hi:
            return y_top + (Hw + 6 - z) * k
        if z <= z_lo:
            return y_lo + (z_lo - z) * k
        return y_hi + (z_hi - z) / (z_hi - z_lo) * gap_px
    L = lambda d: d * k
    # wall outline (dashed), pipe, fin; break lines across the compressed leg
    s.rect(X(-Dp / 2 - 6), Y(Hw), L(Dp + ap + 40), Y(-4) - Y(Hw), fill='none', stroke=GREY, sw=0.8, dash='4 3')
    s.text(X(root + ap + 6), Y(Hw) + 11, 'wall, concrete not shown', 8, GREY)
    s.rect(X(-Dp / 2), Y(Hw - 6), L(Dp), Y(-4) - Y(Hw - 6), fill=STEEL, stroke=INK)
    s.text(X(0), Y(Hw - 30), 'pipe', 8.5, INK, rotate=-90)
    for yy in (y_hi + 6, y_lo - 6):
        s.poly([(X(-Dp / 2 - 8), yy), (X(-Dp / 2 - 2), yy - 4), (X(-Dp / 2 + 4), yy + 4), (X(-Dp / 2 + 10), yy - 4), (X(-Dp / 2 + 16), yy + 4), (X(-Dp / 2 + 22), yy)], stroke=INK, sw=0.9, closed=False)
    s.rect(X(-Dp / 2 + 0.5), y_hi + 2, L(Dp) - 2 * 0.5 * k, gap_px - 4, fill='#fff', stroke='none')
    s.text(X(0) + 2, y_hi + gap_px / 2 + 3, 'break: leg not to scale', 7.5, GREY)
    s.rect(X(root), Y(zs), L(ap), L(hp), fill=PAD, stroke='none')
    s.text(X(root + ap / 2), Y(zs - hp / 2) + 3, 'fin plate', 8, '#fff')
    # saddle (round bar on the fin top, centred on e_h) and hairpins over it
    s.circle(X(root + eh), Y(zs + Ds / 2), L(Ds / 2), fill=STEEL, stroke=INK, sw=0.8)
    for x, key in ((x1, 'x_h1'), (x2, 'x_h2')):
        xc = root + x
        s.line(X(xc), Y(zs + Ds + dh / 2), X(xc), Y(ztip), col(key, PURPLE), 2.2)
        s.circle(X(xc), Y(zs + Ds + dh / 2), 2.8, fill=col(key, PURPLE))
    # dimensions
    xl = X(-Dp / 2) - 12
    s.dim(xl, Y(0), xl, Y(zs), f'{sym("z_seat")} = {n(zs, 1)} in', col('z_seat'), side=-1)
    xr1 = X(root + ap) + 16
    s.dim(xr1, Y(zs + Ds + dh), xr1, Y(Hw), f'{sym("c_top")} = {n(ct, 0)} in', col('c_top'), side=1)
    s.dim(xr1, Y(zs), xr1, Y(zs - hp), f'{sym("h_p")} = {n(hp, 0)}', col('h_p'), side=1)
    s.dim(X(root + x1), Y(ztip) + 10, X(root + x2), Y(ztip) + 10, f'{sym("s_h")}', col('s_h'), side=1, offset=8)
    s.dim(X(root), Y(zs - hp) + 26, X(root + ap), Y(zs - hp) + 26, f'{sym("a_p")} = {n(ap, 0)} in', col('a_p'), side=1, offset=8)
    s.dim(X(root), Y(zs - hp) + 10, X(root + eh), Y(zs - hp) + 10, f'{sym("e_h")}', col('e_h'), side=1, offset=8)
    # development: reserved zone below the seat, available tail, tip height
    xr = X(root + ap) + 70
    s.dim(xr, Y(zs), xr, Y(zs - lz), f'{sym("l_zone")} = {n(lz, 0)} in', col('l_zone', GREY), side=1)
    s.dim(xr, Y(zs - lz), xr, Y(ztip), f'{sym("l_av")} = {n(lav, 1)} in', col('l_av', TEAL), side=1)
    s.dim(xr1, Y(0), xr1, Y(ztip), f'{sym("z_tip")}', col('z_tip', GREY), side=1)
    s.line(X(-Dp / 2 - 6), Y(zr), X(root + ap + 6), Y(zr), col('z_root', GREY), 0.8, '3 2')
    if hl == 'z_root':
        s.tag(X(root + ap) + 8, Y(zr) + 4, f'{sym("z_root")} weld reference', HL, 'start')

    class _F:
        pass
    f = _F()
    f.X, f.Y, f.L = X, Y, L
    return f


FIN_TITLES = {'e_h': 'Nominal resultant of the two hairpins (equal yield)', 's_h': 'Radial spacing of the two hairpins', 'D_s': 'Round saddle diameter (6 bar diameters)',
              'z_seat': 'Top of fin and bottom of saddle above the wall bottom', 'z_root': 'Weld handoff reference at mid-height of the fin root',
              'e_actual': 'Resultant for the adverse 60/40 hairpin split', 'r_f': 'Actual resultant station from the pile centerline', 'r_nom': 'Nominal group center from the pile centerline',
              'W_p': 'Fin-plate self-weight', 'W_s': 'Round saddle self-weight', 'W_a': 'Added steel per fin assembly', 'l_db': 'Basic straight-tail development (LRFD Eq. 5.10.8.2.1a-2)',
              'l_d': 'Required straight-tail development for full yield', 'l_av': 'Available straight tail below the reserved transfer region', 'L_leg': 'Tangent-leg length to the saddle springline',
              'L_bar': 'Nominal hairpin bar length', 'DC_development': 'Development demand against the available tail', 'Chk_development': 'Available tail exceeds the full-yield requirement',
              'Chk_bend': 'Saddle diameter satisfies the #5 minimum bend', 'Chk_saddle': 'Saddle and hairpin force points fit on the fin', 'A_group': 'Tensile area of the hairpin group',
              'P_n_one': 'Nominal yield of one two-legged hairpin', 'P_r_one': 'Factored resistance of one hairpin', 'P_n_group': 'Nominal yield of both hairpins', 'P_r_group': 'Factored resistance of the group',
              'P_one_u': 'Demand on the more heavily loaded hairpin', 'DC_hairpin': 'Hairpin utilization with the 60/40 split', 'P_target': 'Full-yield development target', 'Chk_hairpin': 'Hairpin tensile resistance',
              'g_pipe': 'Gap from the shifted pipe to the innermost face grid', 'g_fins': 'Tip-to-tip clearance of opposed fins in a pile bay'}


def fin(e, name):
    v = e.value
    s = Svg(f'{name}: fin detail', title=FIN_TITLES.get(name, name))
    hl = name if name in ('e_h', 's_h', 'z_seat', 'z_root', 'l_av', 'c_top') else {'l_d': 'l_av', 'l_db': 'l_av', 'DC_development': 'l_av', 'Chk_development': 'l_av', 'L_leg': 'z_seat', 'L_bar': 'z_seat', 'D_s': 'e_h', 'Chk_bend': 'e_h', 'e_actual': 'x_h2', 'P_one_u': 'x_h2', 'DC_hairpin': 'x_h2'}.get(name)
    f = _fin(s, e, 64, 36, PX - 100, 316, hl=hl)
    Dp, ap, zs, Ds = v('D_p', 'in'), v('a_p', 'in'), v('z_seat', 'in'), v('D_s', 'in')
    root = Dp / 2
    if name in ('r_f', 'r_nom', 'e_actual'):
        r = v('r_f' if name != 'r_nom' else 'r_nom', 'in')
        s.line(f.X(0), f.Y(zs + Ds + 14), f.X(0), f.Y(zs - 20), GREY, 0.8, '4 2')
        s.dim(f.X(0), f.Y(zs + Ds + 12), f.X(r), f.Y(zs + Ds + 12), f'{sym(name if name != "e_actual" else "r_f")} = {n(r, 2)} in from pile ℄', HL, side=-1, offset=8)
    if name in ('A_group', 'P_n_one', 'P_r_one', 'P_n_group', 'P_r_group', 'P_one_u', 'DC_hairpin', 'P_target', 'Chk_hairpin', 'V_h_u'):
        for x in (v('x_h1', 'in'), v('x_h2', 'in')):
            s.arrow(f.X(root + x), f.Y(zs + Ds + 12), f.X(root + x), f.Y(zs + Ds + 3), HL, 1.8, 6)
        s.tag(f.X(root + v('x_h1', 'in')) - 10, f.Y(zs + Ds + 14), f'{sym("V_h_u")} = {val(e, "V_h_u", 2)} into the group ({n(100 * (1 - v("α_h")), 0)}/{n(100 * v("α_h"), 0)})', HL, 'end', 8.5)
    # right-hand mini panel of hairpin numbers for the resistance family
    rows = {'e_h': [f'({eq(e, "x_h1", 2)} + {eq(e, "x_h2", 2)}) / 2'], 's_h': [f'{eq(e, "x_h2", 2)} − {eq(e, "x_h1", 2)}'],
            'D_s': [f'6 × {eq(e, "d_h", 3)} (LRFD Table 5.10.2.3-1)'], 'z_seat': [f'{eq(e, "H_w", 2, "in")} − {eq(e, "c_top", 1)} − {eq(e, "D_s", 2)} − {eq(e, "d_h", 3)}'],
            'z_root': [f'{eq(e, "z_seat", 2, "in")} − {eq(e, "h_p", 1)}/2'], 'e_actual': [f'(1 − {eq(e, "α_h", 2)})·{eq(e, "x_h1", 2)} + {sym("α_h")}·{eq(e, "x_h2", 2)}'],
            'r_f': [f'{eq(e, "D_p", 1)}/2 + {eq(e, "e_actual", 3)}'], 'r_nom': [f'{eq(e, "D_p", 1)}/2 + {eq(e, "e_h", 3)}'],
            'W_p': [f'{eq(e, "a_p", 1)} × {eq(e, "h_p", 1)} × {eq(e, "t_p", 2)} × {eq(e, "γ_s", 0, "pcf")}'], 'W_s': [f'π·{eq(e, "D_s", 2)}²/4 × {eq(e, "L_s", 1)} × {eq(e, "γ_s", 0, "pcf")}'],
            'W_a': [f'{eq(e, "W_p", 4)} + {eq(e, "W_s", 4)}'],
            'l_db': [f'0.17·d_h·(f_y / (1.97·λ_c·⁴√f′c))²', f'd_h = {val(e, "d_h", 3)}, f_y = {val(e, "f_y", 0, "ksi")}, f′c = {val(e, "f_c", 1, "ksi")}'],
            'l_d': [f'Max(12 in, {eq(e, "l_db", 2)} × λ_rl·λ_cf·λ_rc = 1.0)'], 'l_av': [f'{eq(e, "z_seat", 2, "in")} − {eq(e, "l_zone", 0)} − {eq(e, "z_tip", 0)}'],
            'L_leg': [f'{eq(e, "z_seat", 2, "in")} + {eq(e, "D_s", 2)}/2 − {eq(e, "z_tip", 0)}'], 'L_bar': [f'2·{eq(e, "L_leg", 2, "in")} + π·({eq(e, "D_s", 2)} + {eq(e, "d_h", 3)})/2'],
            'DC_development': [f'{eq(e, "l_d", 2)} / {eq(e, "l_av", 2, "in")}'], 'Chk_development': [f'{eq(e, "l_av", 2, "in")} ≥ {eq(e, "l_d", 2)}'],
            'Chk_bend': [f'{eq(e, "D_s", 2)} ≥ 6 × {eq(e, "d_h", 3)}'], 'Chk_saddle': [f'0 &lt; x_h1, x_h2 &lt; a_p; L_s/2 ≥ s_h/2 + d_h', f'e_h ± L_s/2 within the fin projection'],
            'A_group': [f'2 × {eq(e, "n_h", 0)} × {eq(e, "A_h", 2)}'], 'P_n_one': [f'2 × {eq(e, "A_h", 2)} × {eq(e, "f_y", 0, "ksi")}'],
            'P_r_one': [f'{eq(e, "φ_h", 2)} × {eq(e, "P_n_one", 2)}'], 'P_n_group': [f'{eq(e, "A_group", 2)} × {eq(e, "f_y", 0, "ksi")}'],
            'P_r_group': [f'{eq(e, "φ_h", 2)} × {eq(e, "P_n_group", 2)}'], 'P_one_u': [f'{eq(e, "α_h", 2)} × {eq(e, "V_h_u", 2)}'],
            'DC_hairpin': [f'{eq(e, "P_one_u", 2)} / {eq(e, "P_r_one", 2)}'], 'P_target': [f'{eq(e, "Ω_h", 2)} × {eq(e, "P_n_group", 2)}', ('development target, not a load', GREY)],
            'Chk_hairpin': [f'{eq(e, "DC_hairpin", 3)} ≤ 1 and {eq(e, "V_h_u", 2)} ≤ {eq(e, "P_r_group", 2)}'],
            'g_pipe': [f'{eq(e, "t_w", 0)}/2 − {eq(e, "D_p", 0)}/2 − {eq(e, "T_pos", 1)} − {eq(e, "c_w", 1)} − 2·{eq(e, "d_grid", 2)}'],
            'g_fins': [f'{eq(e, "S_p", 0, "in")} − {eq(e, "D_p", 0)} − 2·{eq(e, "a_p", 0)}']}
    text_result = name.startswith('Chk')
    if text_result:
        s.panel(f'{sym(name)} = {escape(_txt(e, name))}', rows.get(name, []))
        s.status(PX, 170, _txt(e, name))
    else:
        s.panel(eq(e, name, 3), rows.get(name, []))
        if name.startswith('DC_'):
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


# ----------------------------------------------------------------------------- fin root as a steel section
def plate(e, name):
    v = e.value
    tp, hp, ap = v('t_p', 'in'), v('h_p', 'in'), v('a_p', 'in')
    m = re.match(r'^(Fz|My|Mx)_(SI|U)_F(\d)$', name)
    titles = {'V_target': 'Fin-root shear for the hairpin-yield target', 'M_y_target': 'Major-axis root moment for the yield target', 'M_x_target': 'Minor-axis root moment for the yield target',
              'V_actual': 'Governing actual factored root shear', 'M_y_actual': 'Major-axis root moment, actual reaction', 'M_x_actual': 'Minor-axis root moment, actual reaction',
              'V_d': 'Plate shear sizing demand', 'M_yd': 'Major-axis sizing moment', 'M_xd': 'Minor-axis sizing moment', 'S_y': 'Root elastic modulus, major axis', 'S_x': 'Root elastic modulus, minor axis',
              'Z_y': 'Root plastic modulus, major axis', 'M_Y': 'Major-axis yield moment', 'M_P': 'Yield-based nominal flexural resistance', 'L_buck': 'Unbraced length of the cantilever fin',
              'λ_LT': 'Rectangular-bar LTB slenderness', 'λ_p': 'Yield-region LTB threshold', 'λ_r': 'Elastic-region LTB threshold', 'M_LTB': 'LTB-limited major-axis resistance',
              'M_ry': 'Adopted major-axis resistance', 'M_rx': 'Adopted minor-axis resistance', 'A_v': 'Root shear area', 'R_vy': 'Shear-yielding resistance', 'R_vu': 'Shear-rupture resistance',
              'R_v': 'Adopted root shear resistance', 'DC_plate_shear': 'Root shear demand against resistance', 'DC_biax': 'Linear biaxial first-yield utilization', 'σ_b': 'Combined elastic normal stress at the root',
              'τ_max': 'Maximum elastic shear stress at the root', 'σ_VM': 'von Mises screen at the root', 'DC_VM': 'Combined-stress utilization', 'DC_plate': 'Largest plate utilization',
              'Chk_plate_flex': 'Biaxial flexure of the fin root', 'Chk_plate_shear': 'Root shear yielding and rupture', 'Chk_plate_VM': 'Combined-stress screen', 'Chk_root': 'Plate geometry valid inside the wall',
              'P_pile_end': 'Service wall-plus-fin reaction at an end pile', 'P_pile_int': 'Service wall-plus-fin reaction at an interior pile', 'M_pile_end': 'Service moment at an end-pile centerline',
              'M_pile_int': 'Service moment from unequal opposite fins at an interior pile'}
    title = titles.get(name) or (f'{"Service I" if m.group(2) == "SI" else "Strength"} {"vertical root force" if m.group(1) == "Fz" else "major-axis root moment" if m.group(1) == "My" else "minor-axis root moment"}, fin F{m.group(3)}' if m else name)
    s = Svg(f'{name}: fin root', title=title)
    # fin in elevation with the root section and the load
    x0, y0 = 70, 90
    k = 60 / max(ap, 1)
    s.rect(x0 - 26, y0 - 36, 26, hp * k + 72, fill=STEEL, stroke=INK)
    s.text(x0 - 13, y0 + hp * k / 2, 'pipe', 8.5, INK, rotate=-90)
    s.rect(x0, y0, ap * k, hp * k, fill=PAD, stroke='none')
    s.line(x0, y0 - 6, x0, y0 + hp * k + 6, HL, 2.2)
    s.tag(x0 + 4, y0 + hp * k + 18, f'root section {n(tp, 2)} × {n(hp, 0)} in', HL, 'start')
    target = name.endswith('target') or name in ('P_target',)
    ecc = v('e_h' if target else 'e_actual', 'in')
    force = 'P_target' if target else 'V_h_u'
    if m:
        force, ecc = FIN_OF[f'F{m.group(3)}'], v('e_actual', 'in')
    s.arrow(x0 + ecc * k, y0 - 50, x0 + ecc * k, y0 - 4, HL, 2.2, 8)
    s.tag(x0 + ecc * k + 6, y0 - 44, f'{sym(force)} = {val(e, force, 2)} at {n(ecc, 2)} in', HL, 'start')
    s.dim(x0, y0 - 12, x0 + ecc * k, y0 - 12, '', INK, side=-1)
    s.moment(x0 + ap * k + 26, y0 + hp * k / 2, 13, False, HL if 'y' in name.lower() and 'M' in name else GREY, 'M_y strong axis')
    s.text(x0, y0 + hp * k + 36, f'transverse offset e_y = {val(e, "e_y", 2)} gives the minor-axis M_x', 8.5, GREY, 'start')
    # section sketch
    sx, sy = 330, 100
    kk = 84 / max(hp, 1)
    s.rect(sx, sy, max(tp * kk, 4), hp * kk, fill=PAD, stroke=INK)
    s.dim(sx - 10, sy, sx - 10, sy + hp * kk, f'{sym("h_p")} = {n(hp, 0)}', INK, side=-1)
    s.dim(sx, sy + hp * kk + 12, sx + max(tp * kk, 4), sy + hp * kk + 12, f'{sym("t_p")} = {n(tp, 2)}', INK, side=1)
    s.text(sx + 10, sy - 10, 'root section', 8.5, GREY)
    # LTB curve
    if name in ('λ_LT', 'λ_p', 'λ_r', 'M_LTB', 'M_ry', 'L_buck', 'M_P', 'M_Y'):
        lam, lp, lr = v('λ_LT'), v('λ_p'), v('λ_r')
        MY, MP, Ep, Fy, Cb, Sy = v('M_Y', 'kip*ft'), v('M_P', 'kip*ft'), v('E_p', 'ksi'), v('F_y', 'ksi'), v('C_b'), v('S_y', 'in^3')
        xs = [lr * 1.6 * i / 60 for i in range(1, 61)]
        def mn(l):
            if l <= lp:
                return MP
            if l <= lr:
                return min(MP, Cb * (1.52 - 0.274 * l * Fy / Ep) * MY)
            return min(MP, 1.9 * Ep * Cb * Sy / l / 12)
        X, Y = s.plot(100, 252, 300, 76, [(xs, [mn(l) for l in xs], BLUE)], [(lam, mn(lam), f'{sym("λ_LT")} = {n(lam, 1)}')], xlabel='L_b·h/t² (slenderness)', ylabel='M_n, kip-ft',
                      vlines=((lp, 'λ_p'), (lr, 'λ_r')), hlines=((MY, 'M_Y'),))
    rows = {'V_target': [f'{eq(e, "P_target", 2)} + {eq(e, "γ_DC", 2)}·{eq(e, "W_a", 3)}'], 'M_y_target': [f'{sym("P_target")}·{sym("e_h")} + γ_DC·({sym("W_p")}·{sym("a_p")}/2 + {sym("W_s")}·{sym("e_h")})'],
            'M_x_target': [f'{eq(e, "P_target", 2)} × {eq(e, "e_y", 2)}'], 'V_actual': [f'{eq(e, "V_h_u", 2)} + {eq(e, "γ_DC", 2)}·{eq(e, "W_a", 3)}'],
            'M_y_actual': [f'{sym("V_h_u")}·{sym("e_actual")} + γ_DC·({sym("W_p")}·{sym("a_p")}/2 + {sym("W_s")}·{sym("e_h")})'], 'M_x_actual': [f'{eq(e, "V_h_u", 2)} × {eq(e, "e_y", 2)}'],
            'V_d': [f'Max({eq(e, "V_target", 2)}, {eq(e, "V_actual", 2)})'], 'M_yd': [f'Max({eq(e, "M_y_target", 2)}, {eq(e, "M_y_actual", 2)})'], 'M_xd': [f'Max({eq(e, "M_x_target", 3)}, {eq(e, "M_x_actual", 3)})'],
            'S_y': [f'{eq(e, "t_p", 2)} × {eq(e, "h_p", 0)}² / 6'], 'S_x': [f'{eq(e, "h_p", 0)} × {eq(e, "t_p", 2)}² / 6'], 'Z_y': [f'{eq(e, "t_p", 2)} × {eq(e, "h_p", 0)}² / 4'],
            'M_Y': [f'{eq(e, "F_y", 0, "ksi")} × {eq(e, "S_y", 2)}'], 'M_P': [f'Min({sym("F_y")}·{eq(e, "Z_y", 2)}, 1.6·{eq(e, "M_Y", 2)})'],
            'L_buck': [f'2 × {eq(e, "a_p", 1)}', ('no concrete-restraint credit', GREY)], 'λ_LT': [f'{eq(e, "L_buck", 1)} × {eq(e, "h_p", 0)} / {eq(e, "t_p", 2)}²'],
            'λ_p': [f'0.08 × {eq(e, "E_p", 0, "ksi")} / {eq(e, "F_y", 0, "ksi")}'], 'λ_r': [f'1.9 × {eq(e, "E_p", 0, "ksi")} / {eq(e, "F_y", 0, "ksi")}'],
            'M_LTB': [f'{eq(e, "λ_LT", 1)} vs {eq(e, "λ_p", 1)}, {eq(e, "λ_r", 1)}', ('yield region: M_P' if v('λ_LT') <= v('λ_p') else 'inelastic LTB region' if v('λ_LT') <= v('λ_r') else 'elastic LTB region', GREY)],
            'M_ry': [f'{eq(e, "φ_f", 2)} × Min({eq(e, "M_Y", 2)}, {eq(e, "M_LTB", 2)})'], 'M_rx': [f'{eq(e, "φ_f", 2)} × {eq(e, "F_y", 0, "ksi")} × {eq(e, "S_x", 3)}'],
            'A_v': [f'{eq(e, "t_p", 2)} × {eq(e, "h_p", 0)}'], 'R_vy': [f'{eq(e, "φ_v", 2)} × 0.58 × {eq(e, "F_y", 0, "ksi")} × {eq(e, "A_v", 1)}'],
            'R_vu': [f'{eq(e, "φ_vu", 2)} × 0.58 × {eq(e, "F_u", 0, "ksi")} × {eq(e, "A_v", 1)}'], 'R_v': [f'Min({eq(e, "R_vy", 1)}, {eq(e, "R_vu", 1)})'],
            'DC_plate_shear': [f'{eq(e, "V_d", 2)} / {eq(e, "R_v", 1)}'], 'DC_biax': [f'{eq(e, "M_yd", 2)}/{eq(e, "M_ry", 2)} + {eq(e, "M_xd", 3)}/{eq(e, "M_rx", 2)}'],
            'σ_b': [f'{eq(e, "M_yd", 2)}/{eq(e, "S_y", 1)} + {eq(e, "M_xd", 3)}/{eq(e, "S_x", 3)}'], 'τ_max': [f'1.5 × {eq(e, "V_d", 2)} / {eq(e, "A_v", 1)}'],
            'σ_VM': [f'√({eq(e, "σ_b", 2)}² + 3·{eq(e, "τ_max", 2)}²)'], 'DC_VM': [f'{eq(e, "σ_VM", 2)} / {eq(e, "F_y", 0, "ksi")}'],
            'DC_plate': [f'Max({eq(e, "DC_biax", 3)}, {eq(e, "DC_VM", 3)}, V_d/R_v = {n(v("V_d", "kip") / v("R_v", "kip"), 3)})'],
            'Chk_plate_flex': [f'{eq(e, "DC_biax", 3)} ≤ 1'], 'Chk_plate_shear': [f'{eq(e, "V_d", 2)} ≤ {eq(e, "R_v", 1)}'], 'Chk_plate_VM': [f'{eq(e, "DC_VM", 3)} ≤ 1'],
            'Chk_root': [f't_p, h_p, a_p > 0; {eq(e, "h_p", 0)} ≤ {eq(e, "z_seat", 1, "in")}'],
            'P_pile_end': [f'{eq(e, "R_1", 2)} + {eq(e, "W_a", 3)}'], 'P_pile_int': [f'{eq(e, "R_2", 2)} + {eq(e, "R_3", 2)} + 2·{eq(e, "W_a", 3)}'],
            'M_pile_end': [f'{sym("R_1")}·{sym("r_f")} + {sym("W_p")}·({sym("D_p")}/2 + {sym("a_p")}/2) + {sym("W_s")}·{sym("r_nom")}'], 'M_pile_int': [f'({eq(e, "R_3", 2)} − {eq(e, "R_2", 2)}) × {eq(e, "r_f", 3)}']}
    if m:
        kind, combo, fn = m.groups()
        r = FIN_OF[f'F{fn}']
        g = f'{eq(e, "γ_DC", 2)}·' if combo == 'U' else ''
        rows[name] = {'Fz': [f'{g}({eq(e, r, 2)} + {eq(e, "W_a", 3)})'], 'My': [f'−{g}({sym(r)}·{sym("e_actual")} + {sym("W_p")}·{sym("a_p")}/2 + {sym("W_s")}·{sym("e_h")})', ('negative sign: hogging about the strong axis', GREY)],
                      'Mx': [f'{g}{eq(e, r, 2)} × {eq(e, "e_y", 2)}']}[kind]
    text_result = name.startswith('Chk')
    if text_result:
        s.panel(f'{sym(name)} = {escape(_txt(e, name))}', rows.get(name, []))
        s.status(PX, 170, _txt(e, name))
    else:
        s.panel(eq(e, name, 3), rows.get(name, []))
        if name.startswith('DC_'):
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


# ----------------------------------------------------------------------------- out-of-plane wall strip
def strip(e, name):
    v = e.value
    Sp, ee, b, tw = v('S_p', 'in'), v('e_end', 'in'), v('b_strip', 'in'), v('t_w', 'in')
    titles = {'q_III': 'Strength III wind line load on one horizontal strip', 'q_I': 'Service I wind line load on one strip', 'M_u_strip': 'Factored strip moment envelope',
              'V_u_strip': 'Factored strip shear bound', 'M_I_strip': 'Service strip moment', 'A_strip': 'Horizontal tension steel per foot at one face', 'd_strip': 'Effective depth of the strip',
              'β_1': 'Rectangular stress-block factor', 'a_c': 'Stress-block depth', 'c_n': 'Neutral-axis depth', 'ε_t': 'Tensile strain at nominal resistance', 'M_r_strip': 'Factored flexural resistance of the strip',
              'DC_strip_flex': 'Strip moment against resistance', 'f_r': 'Modulus of rupture', 'S_g': 'Gross section modulus of the strip', 'M_cr': 'Cracking moment', 'M_min': 'Minimum-reinforcement target',
              'A_v_strip': 'Cross-tie area per spacing in the strip', 'A_v_min': 'Minimum transverse steel for the simplified shear parameters', 'd_v': 'Effective shear depth', 'V_c': 'Concrete shear contribution',
              'V_s': 'Cross-tie shear contribution', 'V_r_strip': 'Factored strip shear resistance', 'DC_strip_shear': 'Strip shear against resistance', 'f_t_gross': 'Gross-section tension at Service I',
              'E_c': 'Concrete modulus', 'n_mod': 'Modular ratio', 'c_cr': 'Cracked neutral axis', 'f_ss': 'Cracked-section steel stress', 'β_s': 'Crack-spacing strain-gradient factor', 's_crack': 'Crack-control spacing limit',
              'v_u_strip': 'Factored shear-stress parameter', 's_vmax': 'Maximum transverse spacing', 'Chk_strip_flex': 'Strip flexure and minimum reinforcement', 'Chk_strip_shear': 'Strip shear and transverse steel',
              'Chk_service': 'Service I cracked-section check', 'Status_cracking': 'Crack-control applicability'}
    s = Svg(f'{name}: wall strip', title=titles.get(name, name))
    span_family = name in ('q_III', 'q_I', 'M_u_strip', 'V_u_strip', 'M_I_strip', 'L_strip')
    # plan of the strip between pile supports (always), section at right
    L, T, Wd = 30, 90, 250
    total = 2 * ee + Sp
    k = Wd / total
    X = lambda x: L + x * k
    s.rect(X(0), T, Wd, 18, fill=CONC, stroke=INK)
    s.text(X(total / 2), T + 30, f'horizontal strip {n(b, 0)} in tall, plan; supports at the piles', 8.5, GREY)
    for x in (ee, ee + Sp):
        s.circle(X(x), T + 9, 6, fill='#eef2f5', stroke=INK)
    s.udl(X(0) + 2, X(total) - 2, T - 2, 14, -1, HL if span_family else BLUE, 14, f'{sym("q_III")} = {val(e, "q_III", 4)}')
    s.dim(X(ee), T + 46, X(ee + Sp), T + 46, f'{sym("L_strip")} = {sym("S_p")} = {n(Sp, 0)} in', HL if name in ('M_u_strip', 'V_u_strip', 'M_I_strip') else INK, side=1, offset=8)
    s.dim(X(0), T + 46, X(ee), T + 46, f'{sym("e_end")}', INK, side=1, offset=8)
    # section (wind face on the left)
    sx, sy = 310, 96
    kk = 140 / tw
    s.rect(sx, sy, tw * kk, b * kk, fill=CONC, stroke=INK)
    cw, dg = v('c_w', 'in'), v('d_grid', 'in')
    for xx in (cw + dg / 2, tw - cw - dg / 2):
        s.circle(sx + xx * kk, sy + b * kk / 2, 3.5, fill=HL if name in ('A_strip', 'd_strip', 'a_c', 'c_n', 'ε_t', 'M_r_strip', 'f_ss', 'c_cr') else INK)
    s.line(sx + (cw + dg / 2) * kk, sy + b * kk / 2, sx + (tw - cw - dg / 2) * kk, sy + b * kk / 2, PURPLE, 1.2)
    s.text(sx + tw * kk / 2, sy - 24, f'strip section {n(tw, 0)} × {n(b, 0)} in', 8.5, GREY)
    s.text(sx + tw * kk / 2, sy - 12, '#6 grid both faces, #4 cross-tie', 8.5, GREY)
    d_s = v('d_strip', 'in')
    s.dim(sx, sy + b * kk + 12, sx + d_s * kk, sy + b * kk + 12, f'{sym("d_strip")} = {n(d_s, 2)} in', HL if name in ('d_strip', 'd_v') else INK, side=1, offset=8)
    if name in ('a_c', 'c_n', 'ε_t', 'M_r_strip', 'β_1', 'DC_strip_flex'):
        ac, cn = v('a_c', 'in'), v('c_n', 'in')
        s.rect(sx, sy, max(ac * kk, 2), b * kk, fill=HL, stroke='none', op=0.4)
        s.dim(sx, sy + b * kk + 30, sx + cn * kk, sy + b * kk + 30, f'c = {n(cn, 3)} in', INK, side=1, offset=8)
        s.tag(sx + ac * kk + 4, sy + 10, f'a = {n(ac, 3)} in', HL, 'start')
    if name in ('d_v', 'V_c', 'V_s', 'V_r_strip', 'A_v_strip', 'A_v_min', 'v_u_strip', 's_vmax', 'DC_strip_shear', 'Chk_strip_shear'):
        dv = v('d_v', 'in')
        s.dim(sx, sy + b * kk + 30, sx + dv * kk, sy + b * kk + 30, f'{sym("d_v")} = {n(dv, 2)} in', HL, side=1, offset=8)
    # moment/shear diagram sketch under the plan for the demand family
    if span_family or name in ('M_cr', 'M_min', 'DC_strip_flex', 'DC_strip_shear'):
        yb = T + 100
        s.line(X(0), yb, X(total), yb, GREY, 0.8)
        pts = []
        q = 1.0
        for i in range(41):
            x = total * i / 40
            if x < ee:
                mm = -q * x ** 2 / 2
            elif x > ee + Sp:
                mm = -q * (total - x) ** 2 / 2
            else:
                xl = x - ee
                mm = q * xl * (Sp - xl) / 2 - q * ee ** 2 / 2
            pts.append((X(x), yb - mm / (q * Sp ** 2 / 8) * 28))
        s.poly(pts, stroke=BLUE, sw=1.5, closed=False)
        s.tag(X(ee + Sp / 2), yb - 34, f'envelope: Max(q·L²/8, q·e_end²/2) → {sym("M_u_strip")} = {val(e, "M_u_strip", 2)}', HL if 'M_' in name else BLUE)
    rows = {'q_III': [f'{eq(e, "γ_WS", 2)} × {eq(e, "p_III", 4, "ksf")} × {eq(e, "b_strip", 0)}'], 'q_I': [f'{eq(e, "p_I", 4, "ksf")} × {eq(e, "b_strip", 0)}'],
            'M_u_strip': [f'{eq(e, "q_III", 4)} × Max({sym("L_strip")}²/8, {sym("e_end")}²/2)', f'L = {n(Sp, 0)} in, e_end = {n(ee, 2)} in'],
            'V_u_strip': [f'{eq(e, "q_III", 4)} × Max({sym("L_strip")}, {sym("e_end")})'], 'M_I_strip': [f'{eq(e, "q_I", 4)} × Max(L²/8, e_end²/2)'],
            'A_strip': [f'{eq(e, "A_grid", 2)} × {eq(e, "b_strip", 0)} / {eq(e, "s_grid", 0)}'], 'd_strip': [f'{eq(e, "t_w", 0)} − {eq(e, "c_w", 1)} − {eq(e, "d_grid", 2)}/2'],
            'β_1': [f'0.85 − 0.05·({eq(e, "f_c", 1, "ksi")} − 4), within 0.65…0.85'], 'a_c': [f'{eq(e, "A_strip", 3)}·{sym("f_y")} / (0.85·{sym("f_c")}·{sym("b_strip")})'],
            'c_n': [f'{eq(e, "a_c", 3)} / {eq(e, "β_1", 3)}'], 'ε_t': [f'0.003·({eq(e, "d_strip", 2)} − {eq(e, "c_n", 3)}) / c'],
            'M_r_strip': [f'{eq(e, "φ_rc", 2)}·{eq(e, "A_strip", 3)}·{sym("f_y")}·(d − a/2)'], 'DC_strip_flex': [f'{eq(e, "M_u_strip", 2)} / {eq(e, "M_r_strip", 2)}'],
            'f_r': [f'0.24·{eq(e, "λ_c", 1)}·√({eq(e, "f_c", 1, "ksi")})'], 'S_g': [f'{eq(e, "b_strip", 0)} × {eq(e, "t_w", 0)}² / 6'],
            'M_cr': [f'{eq(e, "γ_3", 2)}·{eq(e, "γ_1", 1)}·{eq(e, "f_r", 3)}·{eq(e, "S_g", 0)}'], 'M_min': [f'Min(1.33·{eq(e, "M_u_strip", 2)}, {eq(e, "M_cr", 2)})'],
            'A_v_strip': [f'{eq(e, "A_tie", 2)} × {eq(e, "b_strip", 0)} / {eq(e, "s_tie", 0)}'], 'A_v_min': [f'0.0316·√f′c·b·s_tie / f_y'],
            'd_v': [f'Max(d − a/2, 0.9·d, 0.72·t_w) with d = {eq(e, "d_strip", 2)}'], 'V_c': [f'0.0316·{eq(e, "β_v", 1)}·λ_c·√f′c·b·{eq(e, "d_v", 2)}'],
            'V_s': [f'{eq(e, "A_v_strip", 2)}·{sym("f_y")}·{eq(e, "d_v", 2)} / {eq(e, "s_tie", 0)}'], 'V_r_strip': [f'0.9·Min({eq(e, "V_c", 2)} + {eq(e, "V_s", 2)}, 0.25·f′c·b·d_v)'],
            'DC_strip_shear': [f'{eq(e, "V_u_strip", 3)} / {eq(e, "V_r_strip", 2)}'], 'f_t_gross': [f'{eq(e, "M_I_strip", 3)} / {eq(e, "S_g", 0)}'],
            'E_c': [f'120000·{eq(e, "K_1", 1)}·({eq(e, "w_c_E", 0, "pcf")}/1000)²·f′c^0.33'], 'n_mod': [f'{eq(e, "E_s", 0, "ksi")} / {eq(e, "E_c", 0)}'],
            'c_cr': [f'cracked transformed section, n·A_s = {n(v("n_mod") * v("A_strip", "in^2"), 3)} in²'], 'f_ss': [f'{eq(e, "M_I_strip", 3)} / ({eq(e, "A_strip", 3)}·(d − {eq(e, "c_cr", 3)}/3))'],
            'β_s': [f'1 + d_c / (0.7·(t_w − d_c)), d_c = {n(v("c_w", "in") + v("d_grid", "in") / 2, 3)} in'], 's_crack': [f'700/({eq(e, "β_s", 3)}·{eq(e, "f_ss", 3)}) − 2·d_c (Class 1)'],
            'v_u_strip': [f'{eq(e, "V_u_strip", 3)} / ({eq(e, "φ_rc", 2)}·b·{eq(e, "d_v", 2)})'], 's_vmax': [f'{eq(e, "v_u_strip", 4)} vs 0.125·f′c = {n(0.125 * v("f_c", "ksi"), 4)} ksi'],
            'Chk_strip_flex': [f'ε_t = {val(e, "ε_t", 4)} ≥ 0.005, M_u ≤ M_r, M_min ≤ M_r'], 'Chk_strip_shear': [f'A_v ≥ A_v,min, V_u ≤ V_r, s_tie ≤ {eq(e, "s_vmax", 1)}'],
            'Chk_service': [f'{eq(e, "s_grid", 0)} ≤ {eq(e, "s_crack", 1)} and f_ss ≤ 0.8·f_y'], 'Status_cracking': [f'{eq(e, "f_t_gross", 4)} vs 0.8·{eq(e, "f_r", 3)}']}
    text_result = name.startswith(('Chk', 'Status'))
    if text_result:
        s.panel(f'{sym(name)}', [(escape(_txt(e, name)[:52]), HL if 'FAIL' in _txt(e, name) or 'required' in _txt(e, name) else TEAL)] + rows.get(name, []))
        s.status(PX, 170, _txt(e, name))
    else:
        s.panel(eq(e, name, 4 if name in ('ε_t', 'v_u_strip', 'q_III', 'q_I') else 3), rows.get(name, []))
        if name.startswith('DC_'):
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


# ----------------------------------------------------------------------------- face grid and detailing
def grid(e, name):
    v = e.value
    tw, sg, dg, cw, st = v('t_w', 'in'), v('s_grid', 'in'), v('d_grid', 'in'), v('c_w', 'in'), v('s_tie', 'in')
    titles = {'A_face': 'Distributed steel per foot, each face and direction', 'A_ST_raw': 'Shrinkage/temperature requirement from the wall height section', 'A_ST_other': 'Shrinkage/temperature requirement from the wall length section',
              'A_ST': 'Required shrinkage/temperature area per foot', 'DC_ST': 'Shrinkage/temperature steel against provided', 'ρ_grid': 'Two-face reinforcement ratio', 's_ST': 'Shrinkage/temperature maximum spacing',
              's_general': 'General maximum bar spacing', 's_clear_req': 'Minimum clear spacing', 's_clear': 'Provided clear spacing', 'l_db_grid': 'Basic development of a #6 grid bar',
              'l_d_grid': 'Top-cast grid development', 'l_lap': 'Class B tension lap', 'Chk_ST': 'Shrinkage/temperature steel and spacing', 'Chk_STMgrid': 'Disturbed-region grid ratio and 12 in ceiling',
              'Chk_spacing': 'Clear spacing and cross-tie spacing', 'Chk_fit': 'Trial layout fits the pile-position envelope'}
    s = Svg(f'{name}: face grid', title=titles.get(name, name))
    # wall section 1 ft tall with grids and ties
    sx, sy, kk = 60, 70, 160 / tw
    hgt = 24
    s.rect(sx, sy, tw * kk, hgt * kk, fill=CONC, stroke=INK)
    for xx in (cw + dg / 2, tw - cw - dg / 2):
        yy = sy + (sg / 2) * kk
        while yy < sy + hgt * kk:
            s.circle(sx + xx * kk, yy, dg * kk / 2 + 1, fill=HL if name in ('A_face', 'ρ_grid', 'DC_ST', 'A_ST', 'A_ST_raw', 'A_ST_other') else INK)
            yy += sg * kk
        s.line(sx + xx * kk, sy, sx + xx * kk, sy + hgt * kk, INK, 1.2)
    for i in range(int(hgt // st)):
        yy = sy + (st / 2 + i * st) * kk
        s.line(sx + (cw + dg) * kk, yy, sx + (tw - cw - dg) * kk, yy, PURPLE, 1.6)
    s.text(sx + tw * kk / 2, sy - 8, f'wall section: #6 @ {n(sg, 0)} in each face, #4 ties @ {n(st, 0)} in', 8.5, GREY)
    s.dim(sx, sy + hgt * kk + 12, sx + cw * kk, sy + hgt * kk + 12, f'{sym("c_w")} = {n(cw, 1)}', INK, side=1, offset=8)
    s.dim(sx + tw * kk + 14, sy + (sg / 2) * kk, sx + tw * kk + 14, sy + (1.5 * sg) * kk, f'{sym("s_grid")} = {n(sg, 0)} in', HL if name in ('s_ST', 's_general', 's_clear', 's_clear_req', 'Chk_ST', 'Chk_spacing') else INK, side=1)
    s.dim(sx, sy + hgt * kk + 30, sx + tw * kk, sy + hgt * kk + 30, f'{sym("t_w")} = {n(tw, 0)} in', INK, side=1, offset=8)
    # pile position envelope (plan hint) for the fit check
    if name in ('Chk_fit', 'g_pipe'):
        Dp, Tp = v('D_p', 'in'), v('T_pos', 'in')
        s.circle(sx + tw * kk / 2, sy + hgt * kk / 2, Dp * kk / 2, fill='none', stroke=GREY, sw=1, dash='3 2')
        s.circle(sx + tw * kk / 2 + Tp * kk, sy + hgt * kk / 2, Dp * kk / 2, fill='none', stroke=HL, sw=1)
        s.tag(sx + tw * kk / 2, sy + hgt * kk / 2 - Dp * kk / 2 - 6, f'pipe shifted {n(Tp, 1)} in: gap {sym("g_pipe")} = {val(e, "g_pipe", 2)}', HL)
    rows = {'A_face': [f'{eq(e, "A_grid", 2)} × 12 in / {eq(e, "s_grid", 0)}'],
            'A_ST_raw': [f'1.30·b·h / (2·(b + h)·f_y) with b = H_w, h = t_w'], 'A_ST_other': [f'1.30·b·h / (2·(b + h)·f_y) with b = L_w, h = t_w'],
            'A_ST': [f'within 0.11…0.60 in²: Max({eq(e, "A_ST_raw", 3)}, {eq(e, "A_ST_other", 3)})'], 'DC_ST': [f'{eq(e, "A_ST", 3)} / {eq(e, "A_face", 3)}'],
            'ρ_grid': [f'2 × {eq(e, "A_grid", 2)} / ({eq(e, "t_w", 0)} × {eq(e, "s_grid", 0)})', f'adopted minimum {eq(e, "ρ_STM", 3)} (LRFD 5.8.2.6)'],
            's_ST': [f't_w = {n(tw, 0)} in > 18 in → 12 in'], 's_general': [f'Min(1.5·{eq(e, "t_w", 0)}, 18 in)'],
            's_clear_req': [f'Max(1.5·{eq(e, "d_grid", 2)}, 1.5·{eq(e, "a_agg", 2)}, 1.5 in)'], 's_clear': [f'{eq(e, "s_grid", 0)} − {eq(e, "d_grid", 2)}'],
            'l_db_grid': [f'0.17·d_b·(f_y / (1.97·⁴√f′c))², d_b = {n(dg, 2)} in'], 'l_d_grid': [f'Max(12 in, 1.3 × {eq(e, "l_db_grid", 2)})', ('top-cast horizontal bars', GREY)],
            'l_lap': [f'1.3 × {eq(e, "l_d_grid", 2)}', ('Class B', GREY)],
            'Chk_ST': [f'{eq(e, "A_face", 3)} ≥ {eq(e, "A_ST", 3)}; s ≤ {eq(e, "s_ST", 0)}, ≤ {eq(e, "s_general", 0)}'],
            'Chk_STMgrid': [f'{eq(e, "ρ_grid", 4)} ≥ {eq(e, "ρ_STM", 3)}; s ≤ 12 in'], 'Chk_spacing': [f'{eq(e, "s_clear", 2)} ≥ {eq(e, "s_clear_req", 2)}; {eq(e, "s_tie", 0)} ≤ 12 in'],
            'Chk_fit': [f'{eq(e, "g_pipe", 2)} ≥ {eq(e, "g_place", 1)}', f'{eq(e, "c_pipe_end", 2)} ≥ {eq(e, "c_w", 1)}; {eq(e, "g_fins", 1)} > 0']}
    if name.startswith('Chk'):
        s.panel(f'{sym(name)} = {escape(_txt(e, name))}', rows.get(name, []))
        s.status(PX, 170, _txt(e, name))
    else:
        s.panel(eq(e, name, 3), rows.get(name, []))
        if name.startswith('DC_'):
            s.gauge(PX, 150, 220, v(name), n(v(name), 3))
    return s


# ----------------------------------------------------------------------------- status and constants
def status(e, name):
    s = Svg(f'{name}: status', title='Implemented numerical checks' if name == 'Status_numeric' else 'Module status (separate weld calculation remains required)')
    checks = ['Chk_reactions', 'Chk_model', 'Chk_saddle', 'Chk_hairpin', 'Chk_development', 'Chk_bend', 'Chk_plate_flex', 'Chk_plate_shear', 'Chk_plate_VM', 'Chk_root',
              'Chk_strip_flex', 'Chk_strip_shear', 'Chk_service', 'Chk_ST', 'Chk_STMgrid', 'Chk_spacing', 'Chk_fit', 'Chk_joints']
    y = 50
    for i, key in enumerate(checks):
        col_x = 20 if i < 9 else 240
        yy = y + (i % 9) * 22
        t = _txt(e, key)
        s.circle(col_x + 6, yy - 4, 4, fill=HL if 'FAIL' in t else TEAL)
        s.text(col_x + 18, yy, f'{key}: {t}', 9.5, INK, 'start')
    if name == 'Status_C006':
        yy = y + 9 * 22 + 10
        for key in ('Local_node_complete', 'Local_pipe_complete', 'Geometry_confirmed'):
            t = _txt(e, key)
            s.circle(26, yy - 4, 4, fill=TEAL if t == 'True' else AMBER)
            s.text(38, yy, f'{key}: {t}', 9.5, INK, 'start')
            yy += 20
    result = _txt(e, name)
    s.panel(f'{sym(name)}', [(escape(result[:56]), HL if 'FAIL' in result or 'REVISE' in result else AMBER if 'PENDING' in result or 'required' in result else TEAL)])
    s.status(PX, 130, result)
    return s


def constant(e, name):
    s = Svg(f'{name}: constant', title='Circle constant used by the saddle weight and hairpin length')
    s.circle(140, 190, 80, fill='none', stroke=INK, sw=1.5)
    s.line(60, 190, 220, 190, HL, 1.5)
    s.tag(140, 182, 'D', HL)
    s.text(140, 300, 'circumference / diameter = π', 10, INK)
    s.panel(f'π = {n(math.pi, 6)}', ['used in W_s = π·D_s²·L_s·γ_s/4 and L_bar'])
    return s


WALL_NAMES = ['n_fin', 'e_end', 'c_pipe_end', 's_fin_nom', 's_pipe_nom', 'L_a', 'L_b', 'a_o', 'W_w', 'w_g', 'M_0', 'K_11', 'K_12', 'K_22', 'B_1', 'B_2', 'Δ_K', 'M_1', 'M_2',
              'R_1', 'R_2', 'R_3', 'R_max', 'V_h_u', 'Chk_reactions', 'Chk_model', 'F_w_III', 'V_conc', 'S_conc', 'R_VS', 'Status_mass', 'Chk_joints', 'z_wall_bottom', 'Δ_ground', 'L_strip']
PLATE_NAMES = ['V_target', 'M_y_target', 'M_x_target', 'V_actual', 'M_y_actual', 'M_x_actual', 'V_d', 'M_yd', 'M_xd', 'S_y', 'S_x', 'Z_y', 'M_Y', 'M_P', 'L_buck', 'λ_LT', 'λ_p', 'λ_r',
               'M_LTB', 'M_ry', 'M_rx', 'A_v', 'R_vy', 'R_vu', 'R_v', 'DC_plate_shear', 'DC_biax', 'σ_b', 'τ_max', 'σ_VM', 'DC_VM', 'DC_plate', 'Chk_plate_flex', 'Chk_plate_shear',
               'Chk_plate_VM', 'Chk_root', 'P_pile_end', 'P_pile_int', 'M_pile_end', 'M_pile_int']
STRIP_NAMES = ['q_III', 'q_I', 'M_u_strip', 'V_u_strip', 'M_I_strip', 'A_strip', 'd_strip', 'β_1', 'a_c', 'c_n', 'ε_t', 'M_r_strip', 'DC_strip_flex', 'f_r', 'S_g', 'M_cr', 'M_min',
               'A_v_strip', 'A_v_min', 'd_v', 'V_c', 'V_s', 'V_r_strip', 'DC_strip_shear', 'f_t_gross', 'E_c', 'n_mod', 'c_cr', 'f_ss', 'β_s', 's_crack', 'v_u_strip', 's_vmax',
               'Chk_strip_flex', 'Chk_strip_shear', 'Chk_service', 'Status_cracking']
GRID_NAMES = ['A_face', 'A_ST_raw', 'A_ST_other', 'A_ST', 'DC_ST', 'ρ_grid', 's_ST', 's_general', 's_clear_req', 's_clear', 'l_db_grid', 'l_d_grid', 'l_lap', 'Chk_ST', 'Chk_STMgrid',
              'Chk_spacing', 'Chk_fit']

drawer = make_drawer({**{k: wall for k in WALL_NAMES}, **{k: fin for k in FIN_TITLES}, **{k: plate for k in PLATE_NAMES}, **{k: strip for k in STRIP_NAMES},
                      **{k: grid for k in GRID_NAMES}, 'Status_numeric': status, 'Status_C006': status, 'π': constant},
                     [(r'^x_F\d$', wall), (r'^(Fz|My|Mx)_(SI|U)_F\d$', plate)])
