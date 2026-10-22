"""'What it represents' drawings for the pier cap cheek wall design (C018).

Scenes drawn from the current case: the wall in section through its thickness on the cap end (wind, resultant, base
shear and moments at sections A and B); the wall face with its mat (spacing, cover, distribution steel); the plan of
the cap with both walls (forces delivered to the pier); the pressure chain from wind speed to the face pressure; the
cross-section with the stress block and strain (flexure), the minimum-reinforcement and crack-control comparisons; the
base shear; the verticals developed into the cap; the construction-joint interface; and the material constants.
"""
from html import escape
from calc_common.schematics import (Svg, Frame, sym, val, eq, n, make_drawer, schematic as _schematic, meaning as _meaning,
                                    INK, GREY, FAINT, HL, BLUE, TEAL, AMBER, PURPLE, CONC, STEEL, SLAB, PX)
from .model import SPEC

DW = PX - 26          # drawing width available left of the panel


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)


def _combo(name):
    if name.endswith('_III') or '_III_' in name:
        return 'Strength III'
    if name.endswith('_V'):
        return 'Strength V'
    if name.endswith('_SI'):
        return 'Service I'
    return ''


def _sec(name):
    return 'B' if name.endswith('_B') else 'A'


def _bar_stations(count, length, edge):
    """Bar centrelines evenly spaced between the two edge bars (schematic; the CAD stations are listed in the inputs)."""
    if count <= 1:
        return [length / 2]
    pitch = (length - 2 * edge) / (count - 1)
    return [edge + i * pitch for i in range(count)]


# ----------------------------------------------------------------------------- the wall in section on the cap end
def _elevation(s, e, left, top, width, height, wind=None, resultant=None, base_moment=None, panel_moment=None, shear=None,
               hl=None, bars=True):
    """Section through the wall thickness: cap end at the left, the recessed outside face toward the cap end."""
    v = e.value
    H, t, r, zr, Hb = v('H_w', 'in'), v('t_w', 'in'), v('r_rec', 'in'), v('z_rec', 'in'), v('H_B', 'in')
    xv, Lemb = v('x_v', 'in'), v('L_emb', 'in')
    cap_d, inset, cap_run = 20.0, 3.0, 26.0
    f = Frame(-inset - 30, t + cap_run + 30, -cap_d - 2, H + 10, left, top, width, height)
    col = lambda key: HL if hl == key else INK
    # cap end block and the construction joint
    s.rect(f.X(-inset), f.Y(0), f.L(t + cap_run + inset), f.L(cap_d), fill=CONC, stroke=INK)
    s.text(f.X(t + cap_run / 2 + 4), f.Y(-cap_d / 2) + 4, 'pier cap', 9, GREY)
    s.line(f.X(-inset), f.Y(0), f.X(t + cap_run + inset), f.Y(0), GREY, 0.8, '4 3')
    s.tag(f.X(t + cap_run + inset) - 2, f.Y(-cap_d) - 4, 'cap top = construction joint', GREY, 'end', 8)
    # wall with the recessed panel on the outside face
    outline = [(0, 0), (0, zr), (r, zr), (r, zr + (H - 2 * zr)), (0, zr + (H - 2 * zr)), (0, H), (t, H), (t, 0)]
    s.poly([(f.X(x), f.Y(z)) for x, z in outline], fill=CONC, stroke=INK, sw=1.2)
    s.text(f.X(t / 2) + 2, f.Y(H * 0.55), 'cheek', 9, GREY, 'middle', rotate=-90)
    if bars:
        s.line(f.X(xv), f.Y(-Lemb), f.X(xv), f.Y(H - 2.25), AMBER, 1.6)
        zs = _bar_stations(int(v('n_h')), H, 2.25)
        for z in zs:
            s.circle(f.X(xv + 0.5), f.Y(z), 2.2, fill=AMBER)
        s.tag(f.X(xv) + 5, f.Y(-Lemb) + 10, f'{sym("L_emb")} = {n(Lemb, 1)} in', AMBER, 'start', 8.5)
    # dimensions
    xd = f.X(t) + (80 if hl in ('z_rec', 'H_B', 't_B') else 54)
    s.dim(xd, f.Y(0), xd, f.Y(H), f'{sym("H_w")} = {n(H, 1)} in', col('H_w'), side=1, ext=6)
    if hl in ('z_rec', 'H_B', 't_B'):
        xd2 = f.X(t) + 22
        s.dim(xd2, f.Y(0), xd2, f.Y(zr), f'{sym("z_rec")} = {n(zr, 1)} in', col('z_rec'), side=1)
        s.dim(xd2, f.Y(zr), xd2, f.Y(H), f'{sym("H_B")} = {n(Hb, 1)} in', col('H_B'), side=1)
    yd = f.Y(H) - 16
    s.dim(f.X(0), yd, f.X(t), yd, f'{sym("t_w")} = {n(t, 1)} in', col('t_w'), side=-1, ext=6)
    if hl == 't_B':
        s.dim(f.X(r), f.Y(zr + 6), f.X(t), f.Y(zr + 6), f'{sym("t_B")} = {n(v("t_B", "in"), 2)} in', HL, side=1)
    if hl == 'r_rec' or hl == 't_B':
        s.tag(f.X(r) - 4, f.Y(H / 2) + 4, f'{sym("r_rec")} = {n(r, 2)} in', HL, 'end', 8.5)
    s.line(f.X(0) - 30, f.Y(zr), f.X(0) - 4, f.Y(zr), GREY, 0.7, '2 2')
    s.text(f.X(0) - 32, f.Y(zr) + 3, 'B', 9, PURPLE, 'end', 'bold')
    s.text(f.X(0) - 32, f.Y(0) + 3, 'A', 9, PURPLE, 'end', 'bold')
    if wind:
        s.wind(f.X(0) - 1, f.Y(H) + 4, f.Y(0) - 4, 22, 1, BLUE, 14)
        s.tag(f.X(0) - 30, f.Y(H) - 8, wind, BLUE, 'start', 8.5)
    if resultant:
        zc = v('z_c', 'in')
        s.arrow(f.X(0) - 96, f.Y(zc), f.X(0) - 30, f.Y(zc), HL, 2.4, 8)
        s.tag(f.X(0) - 96, f.Y(zc) + 14, resultant, HL, 'start')
        s.dim(f.X(0) - 110, f.Y(0), f.X(0) - 110, f.Y(zc), f'{sym("z_c")} = {n(zc, 1)} in', col('z_c'), side=-1)
    if base_moment:
        s.moment(f.X(t + 12), f.Y(0) - 14, 14, True, HL, base_moment)
    if panel_moment:
        s.moment(f.X(t + 12), f.Y(zr), 14, True, PURPLE, panel_moment)
    if shear:
        s.arrow(f.X(t / 2) - 46, f.Y(0) + 7, f.X(t / 2) + 4, f.Y(0) + 7, HL, 2.4, 8)
        s.tag(f.X(t / 2) + 8, f.Y(0) + 11, shear, HL, 'start')
    return f


def elevation(e, name):
    v = e.value
    combo = _combo(name)
    titles = {'t_B': 'Net thickness behind the recessed panel', 'H_B': 'Lever arm of the wind above the panel bottom (section B)',
              'A_face': 'Broad face exposed to wind across the bridge', 'A_edge': 'Edge exposed to wind along the bridge',
              'z_c': 'Resultant of the uniform face pressure at mid-height', 'W_wall': 'Self-weight of one wall (neglected in the checks)',
              'w_u': 'Factored wind line load up the wall', 'w_s': 'Service I wind line load up the wall',
              'V_u': 'Factored shear at the construction joint', 'M_u_A': 'Factored moment at section A, the cap top',
              'M_u_B': 'Factored moment at section B, the panel bottom', 'M_s_A': 'Service I moment at section A',
              'M_s_B': 'Service I moment at section B', 'F_T_III': f'{combo}: wind on one wall face', 'F_T_SI': f'{combo}: wind on one wall face',
              'M_T_III': f'{combo}: moment of the wall wind about the cap top', 'M_T_SI': f'{combo}: moment of the wall wind about the cap top'}
    s = Svg(f'{name}: wall section', title=titles.get(name, name))
    hl = {'t_B': 't_B', 'H_B': 'H_B', 'z_c': 'z_c', 'A_face': 'H_w', 'A_edge': 'H_w', 'W_wall': 'H_w'}.get(name)
    is_u = name in ('w_u', 'V_u', 'M_u_A', 'M_u_B')
    p = 'P_str' if is_u else 'P_ser' if name in ('w_s', 'M_s_A', 'M_s_B') else 'P_III' if name.endswith('III') else 'P_SI' if name.endswith('SI') else None
    wind = f'{sym(p)} = {val(e, p, 4)}' if p else None
    kw = {}
    if name in ('z_c', 'F_T_III', 'F_T_SI', 'M_T_III', 'M_T_SI'):
        fname = 'F_T_III' if name in ('z_c', 'F_T_III', 'M_T_III') else 'F_T_SI'
        kw['resultant'] = f'{sym(fname)} = {val(e, fname, 3)}'
    if name in ('M_u_A', 'M_s_A', 'M_T_III', 'M_T_SI'):
        kw['base_moment'] = eq(e, name, 3)
    if name in ('M_u_B', 'M_s_B'):
        kw['panel_moment'] = eq(e, name, 3)
    if name == 'V_u':
        kw['shear'] = eq(e, name, 3)
    _elevation(s, e, 12, 30, DW, 318, wind=wind, hl=hl, **kw)
    H, w, t = v('H_w', 'in'), v('w_w', 'in'), v('t_w', 'in')
    rows = {'t_B': [f'{eq(e, "t_w", 2)} − {eq(e, "r_rec", 2)}', ('the chamfer at the panel edge is ignored', GREY)],
            'H_B': [f'{eq(e, "H_w", 1)} − {eq(e, "z_rec", 1)}', ('wind above the panel bottom loads section B', GREY)],
            'A_face': [f'{eq(e, "H_w", 1)} × {eq(e, "w_w", 1)}', ('the face seen across the bridge; the cap top is its lower edge', GREY)],
            'A_edge': [f'{eq(e, "H_w", 1)} × {eq(e, "t_w", 1)}', ('the edge seen along the bridge', GREY)],
            'z_c': [f'{eq(e, "H_w", 1)} / 2', ('uniform pressure: resultant at mid-height', GREY)],
            'W_wall': [f'{eq(e, "w_c", 3)} × {n(H, 0)} × {n(w, 0)} × {n(t, 0)} in³', ('gross prism; compression left out of every check', GREY)],
            'w_u': [f'{eq(e, "P_str", 4)} × {eq(e, "w_w", 1)}', ('the whole 48 in width acts with its six verticals', GREY)],
            'w_s': [f'{eq(e, "P_ser", 4)} × {eq(e, "w_w", 1)}'],
            'V_u': [f'{eq(e, "w_u", 4)} × {eq(e, "H_w", 1)}', ('all of the face wind reaches the joint as shear', GREY)],
            'M_u_A': [f'{eq(e, "w_u", 4)} × {eq(e, "H_w", 1)}² / 2', ('cantilever fixed at the cap top', GREY)],
            'M_u_B': [f'{eq(e, "w_u", 4)} × {eq(e, "H_B", 1)}² / 2', ('the wind above the panel bottom', GREY)],
            'M_s_A': [f'{eq(e, "w_s", 4)} × {eq(e, "H_w", 1)}² / 2'],
            'M_s_B': [f'{eq(e, "w_s", 4)} × {eq(e, "H_B", 1)}² / 2'],
            'F_T_III': [f'{eq(e, "P_III", 4)} × {eq(e, "A_face", 1)}', ('per wall; a pier node load', GREY)],
            'F_T_SI': [f'{eq(e, "P_SI", 4)} × {eq(e, "A_face", 1)}', ('per wall; a pier node load', GREY)],
            'M_T_III': [f'{eq(e, "F_T_III", 3)} × {eq(e, "z_c", 1)}', ('carried by the cap end, outside this calculation', GREY)],
            'M_T_SI': [f'{eq(e, "F_T_SI", 3)} × {eq(e, "z_c", 1)}']}
    places = 4 if name in ('w_u', 'w_s') else 3
    s.panel(eq(e, name, places), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- the wall face with its mat
def _face(s, e, left, top, width, height, hl=None, show_spacing=True, show_cover=False):
    v = e.value
    H, w, zr = v('H_w', 'in'), v('w_w', 'in'), v('z_rec', 'in')
    nv, nh = int(v('n_v')), int(v('n_h'))
    dbv, dbh, ce = v('d_b_v', 'in'), v('d_b_h', 'in'), v('c_edge', 'in')
    f = Frame(-14, w + 40, -12, H + 14, left, top, width, height)
    s.rect(f.X(-14), f.Y(0), f.L(w + 54), f.L(12), fill=CONC, stroke=INK)
    s.text(f.X(w + 38), f.Y(-6) + 4, 'cap', 8.5, GREY, 'end')
    s.rect(f.X(0), f.Y(H), f.L(w), f.L(H), fill=CONC, stroke=INK, sw=1.2)
    s.rect(f.X(zr), f.Y(H - zr), f.L(w - 2 * zr), f.L(H - 2 * zr), fill='#d8dfe6', stroke=GREY, sw=0.8, dash='3 2')
    s.text(f.X(w / 2), f.Y(H / 2) + 3, 'recessed panel', 8, GREY)
    xs = _bar_stations(nv, w, ce + dbv / 2)
    zs = _bar_stations(nh, H, ce + dbh / 2)
    col_v = HL if hl in ('v', 'both') else AMBER
    col_h = HL if hl in ('h', 'both') else AMBER
    for x in xs:
        s.line(f.X(x), f.Y(-v('L_emb', 'in')), f.X(x), f.Y(H - ce - dbv / 2), col_v, 1.5)
    for z in zs:
        s.line(f.X(ce + dbh / 2), f.Y(z), f.X(w - ce - dbh / 2), f.Y(z), col_h, 1.3)
    if show_spacing:
        xd = f.X(w) + 16
        s.dim(xd, f.Y(zs[0]), xd, f.Y(zs[1]) if nh > 1 else f.Y(H), f'{sym("s_h")} ≤ {n(v("s_h", "in"), 1)} in', col_h, side=1)
        yd = f.Y(-12) + 14
        s.dim(f.X(xs[0]), yd, f.X(xs[1]) if nv > 1 else f.X(w), yd, f'{sym("s_v")} ≤ {n(v("s_v", "in"), 1)} in', col_v, side=1, offset=12)
    if show_cover:
        s.dim(f.X(w - ce), f.Y(H) - 8, f.X(w), f.Y(H) - 8, f'{sym("c_edge")} = {n(ce, 2)} in', HL, side=-1)
    s.dim(f.X(0), f.Y(H) - 30, f.X(w), f.Y(H) - 30, f'{sym("w_w")} = {n(w, 1)} in', INK, side=-1)
    s.dim(f.X(w) + 44, f.Y(0), f.X(w) + 44, f.Y(H), f'{sym("H_w")} = {n(H, 1)} in', INK, side=1, ext=0)
    return f


def face(e, name):
    v = e.value
    titles = {'A_s': 'The verticals crossing the base and the panel section', 'A_pr_v': 'Vertical steel per foot of wall width',
              'A_pr_h': 'Horizontal steel per foot of wall height', 'b_ts': 'Least width for the shrinkage and temperature equation',
              'A_ts_face': 'Shrinkage and temperature steel required on each face', 'A_ts_mat': 'Both face requirements in the one centred mat',
              's_max_pri': 'Maximum spacing of the primary (vertical) steel', 's_max_ts': 'Maximum spacing of the horizontals',
              's_clr_min': 'Minimum clear spacing between bars', 's_clr_v': 'Smallest clear spacing between verticals',
              's_clr_h': 'Smallest clear spacing between horizontals', 's_clr_prov': 'Smallest clear spacing in the mat',
              'DC_temp_v': 'Shrinkage and temperature steel, vertical', 'DC_temp_h': 'Shrinkage and temperature steel, horizontal',
              'DC_space_v': 'Largest vertical spacing against the limit', 'DC_space_h': 'Largest horizontal spacing against the limit',
              'DC_clear': 'Minimum clear spacing against the smallest provided', 'DC_cover': 'Required cover against the smallest provided',
              'DC_thick': 'Minimum thickness against the wall thickness'}
    s = Svg(f'{name}: wall face', title=titles.get(name, name))
    hl = 'v' if name in ('A_s', 'A_pr_v', 'DC_temp_v', 's_max_pri', 'DC_space_v', 's_clr_v') else \
         'h' if name in ('A_pr_h', 'DC_temp_h', 's_max_ts', 'DC_space_h', 's_clr_h') else 'both' if name in ('s_clr_min', 's_clr_prov', 'DC_clear') else None
    _face(s, e, 12, 30, 262, 318, hl=hl, show_cover=name == 'DC_cover')
    x0, y0 = 292, 60
    nv, nh = int(v('n_v')), int(v('n_h'))
    if name in ('A_ts_face', 'A_ts_mat', 'A_pr_v', 'A_pr_h', 'DC_temp_v', 'DC_temp_h', 'b_ts'):
        items = [(f'{sym("A_ts_face")} each face', v('A_ts_face', 'in^2/ft'), None), (f'{sym("A_ts_mat")} one mat', v('A_ts_mat', 'in^2/ft'), None),
                 (f'{sym("A_pr_v")} vertical', v('A_pr_v', 'in^2/ft'), TEAL), (f'{sym("A_pr_h")} horizontal', v('A_pr_h', 'in^2/ft'), TEAL)]
        hi = {'A_ts_face': 0, 'A_ts_mat': 1, 'DC_temp_v': 1, 'DC_temp_h': 1, 'A_pr_v': 2, 'A_pr_h': 3}.get(name)
        s.text(x0, y0 - 14, 'steel per foot (in²/ft)', 9, GREY, 'start')
        s.bars(x0 + 78, y0, items, width=48, highlight=hi, places=3)
    elif name in ('s_max_pri', 's_max_ts', 'DC_space_v', 'DC_space_h'):
        s.text(x0, y0 - 14, 'spacing against its limit', 9, GREY, 'start')
        s.gauge(x0, y0, 120, v('DC_space_v'), f'{sym("s_v")} = {n(v("s_v", "in"), 1)} of {n(v("s_max_pri", "in"), 1)} in', HL if name in ('s_max_pri', 'DC_space_v') else None)
        s.gauge(x0, y0 + 56, 120, v('DC_space_h'), f'{sym("s_h")} = {n(v("s_h", "in"), 1)} of {n(v("s_max_ts", "in"), 1)} in', HL if name in ('s_max_ts', 'DC_space_h') else None)
    elif name in ('s_clr_min', 's_clr_v', 's_clr_h', 's_clr_prov', 'DC_clear'):
        s.text(x0, y0 - 14, 'clear spacing (in)', 9, GREY, 'start')
        items = [('minimum', v('s_clr_min', 'in'), None), ('verticals', v('s_clr_v', 'in'), TEAL), ('horizontals', v('s_clr_h', 'in'), TEAL)]
        hi = {'s_clr_min': 0, 's_clr_v': 1, 's_clr_h': 2, 's_clr_prov': 1 if v('s_clr_v', 'in') <= v('s_clr_h', 'in') else 2, 'DC_clear': 0}.get(name)
        s.bars(x0 + 66, y0, items, width=60, highlight=hi, places=2, unit='in')
    elif name == 'DC_cover':
        s.gauge(x0, y0, 120, v('DC_cover'), f'{n(v("cv_req", "in"), 2)} in required of {n(v("c_edge", "in"), 2)} in provided')
    elif name == 'DC_thick':
        s.gauge(x0, y0, 120, v('DC_thick'), f'{n(v("t_min", "in"), 1)} in minimum of {n(v("t_w", "in"), 1)} in')
    rows = {'A_s': [f'{nv} × {eq(e, "A_b_v", 2)}', ('all six verticals cross sections A and B', GREY)],
            'A_pr_v': [f'{nv} × {eq(e, "A_b_v", 2)} / {eq(e, "w_w", 1)}'],
            'A_pr_h': [f'{nh} × {eq(e, "A_b_h", 2)} / {eq(e, "H_w", 1)}'],
            'b_ts': [f'Min({eq(e, "H_w", 1)}, {eq(e, "w_w", 1)})'],
            'A_ts_face': [f'1.30 b h / (2 (b + h) fy)', f'b = {eq(e, "b_ts", 1)}, h = {eq(e, "t_w", 1)}', ('between 0.11 and 0.60 in²/ft', GREY)],
            'A_ts_mat': [f'2 × {eq(e, "A_ts_face", 3)}', ('both faces carried by the one centred mat', GREY)],
            's_max_pri': [f'Min(1.5 × {eq(e, "t_w", 1)}, 18 in)'],
            's_max_ts': [f'Min(3 × {eq(e, "t_w", 1)}, 18 in)'],
            's_clr_min': [f'Max(1.5 {sym("d_b_v")}, 1.5 {sym("d_agg")}, 1.5 in)', f'{eq(e, "d_b_v", 3)}, {eq(e, "d_agg", 2)}'],
            's_clr_v': [f'{eq(e, "s_v_min", 2)} − {eq(e, "d_b_v", 3)}', ('the two outer verticals at the side faces', GREY)],
            's_clr_h': [f'{eq(e, "s_h_min", 2)} − {eq(e, "d_b_h", 3)}', ('the two top horizontals', GREY)],
            's_clr_prov': [f'Min({eq(e, "s_clr_v", 2)}, {eq(e, "s_clr_h", 2)})'],
            'DC_temp_v': [f'{eq(e, "A_ts_mat", 3)} / {eq(e, "A_pr_v", 3)}'], 'DC_temp_h': [f'{eq(e, "A_ts_mat", 3)} / {eq(e, "A_pr_h", 3)}'],
            'DC_space_v': [f'{eq(e, "s_v", 1)} / {eq(e, "s_max_pri", 1)}'], 'DC_space_h': [f'{eq(e, "s_h", 1)} / {eq(e, "s_max_ts", 1)}'],
            'DC_clear': [f'{eq(e, "s_clr_min", 2)} / {eq(e, "s_clr_prov", 2)}'], 'DC_cover': [f'{eq(e, "cv_req", 2)} / {eq(e, "c_edge", 2)}'],
            'DC_thick': [f'{eq(e, "t_min", 1)} / {eq(e, "t_w", 1)}']}
    s.panel(eq(e, name, 3), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- plan of the cap with both walls
def plan(e, name):
    v = e.value
    combo = _combo(name)
    longitudinal = name.startswith('F_L')
    both = name.endswith('_both')
    titles = {'F_L_III': f'{combo}: wind along the bridge on one wall edge', 'F_L_SI': f'{combo}: wind along the bridge on one wall edge',
              'F_T_III_both': f'{combo}: transverse wind on both walls, a pier load', 'F_L_III_both': f'{combo}: longitudinal wind on both wall edges, a pier load'}
    s = Svg(f'{name}: cap plan', title=titles.get(name, name))
    w, t = v('w_w', 'in'), v('t_w', 'in')
    L = 230.0            # cap length drawn to scale with the walls (schematic; not an input)
    f = Frame(-40, L + 40, -w, 2 * w, 12, 60, DW, 250)
    s.rect(f.X(0), f.Y(w), f.L(L), f.L(w), fill=SLAB, stroke=INK)
    s.text(f.X(L / 2), f.Y(w / 2) + 4, 'pier cap (plan)', 9.5, GREY)
    walls = [(3.0, 3.0 + t), (L - 3.0 - t, L - 3.0)]
    for x0, x1 in walls:
        s.rect(f.X(x0), f.Y(w), f.L(x1 - x0), f.L(w), fill=CONC, stroke=INK, sw=1.2)
    s.text(f.X(walls[0][1]) + 6, f.Y(w) - 6, 'cheek wall', 8.5, INK, 'start')
    s.line(f.X(L / 2), f.Y(-w * 0.9), f.X(L / 2), f.Y(2 * w * 0.95), GREY, 0.8, '5 3')
    s.text(f.X(L / 2) + 4, f.Y(2 * w * 0.95) + 10, 'bridge axis', 8.5, GREY, 'start')
    p = 'P_III' if 'III' in name else 'P_SI'
    if longitudinal:
        for x0, x1 in walls:
            s.udl(f.X(x0) + 2, f.X(x1) - 2, f.Y(w), 26, -1, BLUE, 8)
        s.tag(f.X(walls[0][0]) - 4, f.Y(w) - 34, f'{sym(p)} on the {n(t, 0)} in edges', BLUE, 'start', 8.5)
        fname = 'F_L_III' if 'III' in name else 'F_L_SI'
        for x0, x1 in walls:
            s.force(f.X((x0 + x1) / 2), f.Y(w / 2) - 2, 0, 44, '', HL)
        s.tag(f.X(walls[1][0]) - 8, f.Y(w / 2) - 48, f'{sym(fname)} = {val(e, fname, 3)} per wall', HL, 'end')
    else:
        for x0, x1 in walls:
            s.wind(f.X(x0), f.Y(w) + 3, f.Y(0) - 3, 24, 1, BLUE, 12)
        s.tag(f.X(walls[0][0]) - 28, f.Y(0) + 14, f'{sym(p)} on the faces', BLUE, 'start', 8.5)
        for x0, x1 in walls:
            s.force(f.X(x0) - 2, f.Y(w / 2), -56, 0, '', HL)
        s.tag(f.X(walls[1][0]) - 60, f.Y(w / 2) - 10, f'{sym("F_T_III")} = {val(e, "F_T_III", 3)} per wall', HL, 'end')
    rows = {'F_L_III': [f'{eq(e, "P_III", 4)} × {eq(e, "A_edge", 1)}', ('strong-axis bending of the wall; a pier load only', GREY)],
            'F_L_SI': [f'{eq(e, "P_SI", 4)} × {eq(e, "A_edge", 1)}', ('a pier load only', GREY)],
            'F_T_III_both': [f'2 × {eq(e, "F_T_III", 3)}', ('both walls at the same height above the cap top', GREY)],
            'F_L_III_both': [f'2 × {eq(e, "F_L_III", 3)}', ('both wall edges', GREY)]}
    s.panel(eq(e, name, 3), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- pressure chain
def pressure(e, name):
    v = e.value
    combo = _combo(name) or 'Strength III'
    suffix = 'III' if name in ('P_str', 'DC_govern') else 'SI' if name == 'P_ser' else name.split('_')[-1]
    s = Svg(f'{name}: wind pressure', title={'P_str': 'Governing factored strength pressure', 'P_ser': 'Factored Service I pressure',
                                             'DC_govern': 'Strength V against Strength III'}.get(name, f'{combo}: pressure on the wall face (LRFD Eq. 3.8.1.2.1-1, C_D = 1.6)'))
    vname, kz = f'V_{suffix}', f'K_Z_{suffix}'
    x, y = 20, 70
    steps = [(f'{sym(vname)} = {n(v(vname), 0)} mph', BLUE), (f'{sym(kz)} = {n(v(kz), 4)}', INK), (f'{sym("G_f")} = {n(v("G_f"), 2)}', INK),
             (f'{sym("q_" + suffix)} = {val(e, "q_" + suffix, 4)}', HL if name.startswith('q_') else TEAL),
             (f'× {sym("C_D")} = {n(v("C_D"), 1)}', INK), (f'{sym("P_" + suffix)} = {val(e, "P_" + suffix, 4)}', HL if name.startswith('P_') and name not in ('P_str', 'P_ser') else TEAL)]
    for i, (markup, color) in enumerate(steps):
        yy = y + i * 30
        s.rect(x, yy - 14, 160, 22, fill='#fff', stroke=color, sw=1.3, rx=4)
        s.text(x + 8, yy + 1, markup, 10, color, 'start', 'bold' if color == HL else 'normal')
        if i < len(steps) - 1:
            s.arrow(x + 80, yy + 9, x + 80, yy + 15, GREY, 1, 4)
    s.text(x, y + 190, 'q = 0.00000256 · V² · K_Z · G', 9, GREY, 'start')
    s.text(x, y + 204, 'P = q · C_D, C_D = 1.6 (substructure)', 9, GREY, 'start')
    if name in ('P_str', 'P_ser', 'DC_govern'):
        x0, y0 = 220, 70
        s.text(x0, y0 - 14, 'face pressure by limit state (ksf) · γ_WS = 1.0 in each', 9, GREY, 'start')
        items = [('Strength III', v('P_III', 'ksf'), HL if name != 'P_ser' else None), ('Strength V', v('P_V', 'ksf'), AMBER if name == 'DC_govern' else None),
                 ('Service I', v('P_SI', 'ksf'), HL if name == 'P_ser' else None)]
        s.bars(x0 + 70, y0, items, width=120, places=4, unit='ksf')
    else:
        _elevation(s, e, 210, 36, 250, 300, wind=f'{sym("P_" + suffix)}', bars=False)
    rows = {'q': [f'0.00000256 × {n(v(vname), 0)}² × {n(v(kz), 4)} × {n(v("G_f"), 2)}', ('gust factor included; drag coefficient next', GREY)],
            'P': [f'{eq(e, "q_" + suffix, 4)} × {eq(e, "C_D", 1)}', ('the full pressure normal to the broad face', GREY)],
            'P_str': [f'Max({sym("gamma_WS_III")} {eq(e, "P_III", 4)}, {sym("gamma_WS_V")} {eq(e, "P_V", 4)})', ('LRFD Table 3.4.1-1: WS = 1.0 in both', GREY)],
            'P_ser': [f'{eq(e, "gamma_WS_SI", 2)} × {eq(e, "P_SI", 4)}', ('crack control at Service I', GREY)],
            'DC_govern': [f'{eq(e, "P_V", 4)} / {eq(e, "P_III", 4)}', ('below 1: Strength III is the design pressure', GREY)]}
    key = name if name in rows else 'q' if name.startswith('q_') else 'P'
    s.panel(eq(e, name, 4), rows[key])
    return s


# ----------------------------------------------------------------------------- the cross-section: flexure
def _section(s, e, sec, left, top, width, height, hl=None):
    """Horizontal section through the wall: thickness across, the single bar row, compression on the governing face."""
    v = e.value
    t, r, xv = v('t_w', 'in'), v('r_rec', 'in'), v('x_v', 'in')
    tB = v('t_B', 'in')
    d, a, c = v(f'd_{sec}', 'in'), v(f'a_{sec}', 'in'), v(f'c_{sec}', 'in')
    rec = r if sec == 'B' else 0.0
    # governing direction: compression on the face nearer the bar
    outer_comp = (xv - rec) <= (t - xv)
    f = Frame(-30, t + 30, -34, 60, left, top, width, height)
    depth = 40.0   # the drawn slice of the wall width
    s.rect(f.X(rec), f.Y(depth), f.L(t - rec), f.L(depth), fill=CONC, stroke=INK, sw=1.2)
    if rec:
        s.rect(f.X(0), f.Y(depth), f.L(rec), f.L(depth), fill='#fff', stroke=GREY, sw=0.8, dash='3 2')
        s.tag(f.X(rec / 2), f.Y(depth) - 6, 'recess', GREY, 'middle', 8)
    s.circle(f.X(xv), f.Y(depth / 2), 4, fill=AMBER)
    s.tag(f.X(xv), f.Y(depth / 2) + 16, f'{sym("x_v")} = {n(xv, 3)} in', AMBER, 'middle', 8.5)
    xc = rec if outer_comp else t                     # compression face
    sign = 1 if outer_comp else -1
    s.rect(f.X(xc) if outer_comp else f.X(t - a), f.Y(depth), f.L(a), f.L(depth), fill='#c7d6e5', stroke='none', op=0.9)
    s.line(f.X(xc + sign * c), f.Y(depth) - 6, f.X(xc + sign * c), f.Y(0) + 6, GREY, 0.8, '3 2')
    col = lambda key: HL if hl == key else INK
    yd = f.Y(0) + 18
    s.dim(f.X(xc), yd, f.X(xv), yd, f'{sym("d_" + sec)} = {n(d, 3)} in', col('d'), side=1, ext=4)
    yd2 = f.Y(depth) - 12
    s.dim(f.X(xc), yd2, f.X(xc + sign * a), yd2, f'{sym("a_" + sec)} = {n(a, 3)} in', col('a'), side=-1)
    s.tag(f.X(xc + sign * c) + 4 * sign, f.Y(0) + 3, f'{sym("c_" + sec)} = {n(c, 3)} in', col('c'), 'start' if sign > 0 else 'end', 8.5)
    s.wind(f.X(t) + 1 if outer_comp else f.X(rec) - 1, f.Y(depth) + 4, f.Y(0) - 4, 18, -1 if outer_comp else 1, BLUE, 12)
    s.tag(f.X(t / 2), f.Y(-10), 'compression on the ' + ('recessed face' if (outer_comp and rec) else 'outside face' if outer_comp else 'inside face')
          + ' · tension on the far face', GREY, 'middle', 8.5)
    s.text(f.X(t / 2), f.Y(-24), 'wind from the side that puts the bar nearest the compression face', 8, GREY)
    # strain diagram at the right
    xs = f.X(t) + 56
    y_top, y_bot = f.Y(depth), f.Y(0)
    s.line(xs, y_top - 4, xs, y_bot + 4, GREY, 0.8)
    s.text(xs, y_top - 8, 'strain', 8.5, GREY)
    eps = v(f'eps_t_{sec}')
    yc = y_top + (y_bot - y_top) * (c / t)
    s.poly([(xs, y_top), (xs - 26, y_top), (xs + 26 * min(eps / 0.003, 4), y_top + (y_bot - y_top) * (d / t)), (xs, y_top + (y_bot - y_top) * (d / t))],
           fill='#e7eef5', stroke=INK, sw=0.8)
    s.tag(xs - 28, y_top + 4, '0.003', INK, 'end', 8)
    s.tag(xs + 26 * min(eps / 0.003, 4) + 4, y_top + (y_bot - y_top) * (d / t) + 3, f'{sym("eps_t_" + sec)} = {n(eps, 4)}', col('eps'), 'start', 8.5)
    return f


def section(e, name):
    v = e.value
    sec = _sec(name)
    base = name[:-2]
    titles = {'d': f'Effective depth at section {sec} for the weaker wind direction', 'a': 'Stress block depth', 'c': 'Neutral axis depth',
              'eps_t': 'Net tensile strain in the verticals', 'phi': 'Flexural resistance factor from the strain', 'M_n': f'Nominal flexural resistance at section {sec}',
              'M_r': f'Factored flexural resistance at section {sec}', 'rho': 'Reinforcement ratio', 'k': 'Cracked neutral axis ratio', 'j': 'Lever arm ratio',
              'f_ss': 'Service I steel stress on the cracked section', 'd_c': 'Tension face to the bar centre', 'beta_s': 'Flexural strain ratio',
              'DC_fss': 'Service I steel stress against the SDG limit', 'DC_flex': f'Flexure at section {sec}'}
    s = Svg(f'{name}: section {sec}', title=titles.get(base, name))
    hl = {'d': 'd', 'd_c': 'd', 'a': 'a', 'c': 'c', 'eps_t': 'eps'}.get(base)
    _section(s, e, sec, 12, 40, DW, 300, hl=hl)
    t = v('t_B', 'in') if sec == 'B' else v('t_w', 'in')
    rows = {'d': [f'Min({eq(e, "t_w", 1)} − {eq(e, "x_v", 3)}, {sym("x_v")}' + (f' − {eq(e, "r_rec", 2)})' if sec == 'B' else ')'),
                  ('the lesser bar distance to a face', GREY)],
            'a': [f'{eq(e, "A_s", 2)} × {eq(e, "fy", 0)} / (0.85 × {eq(e, "fc", 1)} × {eq(e, "w_w", 0)})'],
            'c': [f'{eq(e, "a_" + sec, 3)} / {eq(e, "beta_1", 3)}'],
            'eps_t': [f'0.003 × ({eq(e, "d_" + sec, 3)} − {eq(e, "c_" + sec, 3)}) / {sym("c_" + sec)}', ('tension controlled above 0.005', GREY)],
            'phi': [f'{eq(e, "eps_t_" + sec, 4)} ≥ 0.005 → {sym("phi_f")}', ('linear between 0.75 at 0.002 and φf at 0.005', GREY)],
            'M_n': [f'{eq(e, "A_s", 2)} × {eq(e, "fy", 0)} × ({eq(e, "d_" + sec, 3)} − {sym("a_" + sec)}/2)'],
            'M_r': [f'{eq(e, "phi_" + sec, 2)} × {eq(e, "M_n_" + sec, 3)}'],
            'rho': [f'{eq(e, "A_s", 2)} / ({eq(e, "w_w", 0)} × {eq(e, "d_" + sec, 3)})'],
            'k': [f'√(2ρn + (ρn)²) − ρn', f'{eq(e, "rho_" + sec, 4)}, {eq(e, "n_m", 3)}'],
            'j': [f'1 − {eq(e, "k_" + sec, 4)} / 3'],
            'f_ss': [f'{eq(e, "M_s_" + sec, 3)} / ({eq(e, "A_s", 2)} × {eq(e, "j_" + sec, 4)} × {eq(e, "d_" + sec, 3)})', ('cracked-section steel stress', GREY)],
            'd_c': [f'{n(t, 2)} in − {eq(e, "d_" + sec, 3)}', ('from the tension face to the bar centre', GREY)],
            'beta_s': [f'1 + {eq(e, "d_c_" + sec, 3)} / (0.7 × ({n(t, 2)} in − {sym("d_c_" + sec)}))'],
            'DC_fss': [f'{eq(e, "f_ss_" + sec, 3)} / {eq(e, "f_ss_lim", 1)}', ('SDG 3.10.F: fss ≤ 0.80 fy', GREY)],
            'DC_flex': [f'{eq(e, "M_u_" + sec, 3)} / {eq(e, "M_r_" + sec, 3)}']}
    places = 4 if base in ('eps_t', 'rho', 'k', 'j') else 3
    s.panel(eq(e, name, places), rows.get(base, []))
    if base == 'DC_flex':
        s.gauge(PX, 250, 200, v(name), f'{n(v(name), 3)}')
    return s


def minflex(e, name):
    v = e.value
    sec = _sec(name)
    base = name[:-2]
    titles = {'S_c': f'Section modulus at section {sec}', 'M_cr': f'Cracking moment at section {sec}', 'M_min': f'Minimum required flexural resistance at section {sec}',
              'A_req': f'Steel the minimum design moment requires at section {sec}', 'DC_minflex': f'Minimum flexural resistance at section {sec}'}
    s = Svg(f'{name}: minimum reinforcement', title=titles.get(base, name))
    t = v('t_B', 'in') if sec == 'B' else v('t_w', 'in')
    # small section with S_c
    f = Frame(-6, t + 6, -4, 44, 20, 50, 110, 170)
    s.rect(f.X(0), f.Y(40), f.L(t), f.L(40), fill=CONC, stroke=INK)
    s.dim(f.X(0), f.Y(0) + 14, f.X(t), f.Y(0) + 14, f'{n(t, 2)} in', INK, side=1)
    s.text(f.X(t / 2), f.Y(44), f'{sym("S_c_" + sec)} = {n(v("S_c_" + sec, "in^3"), 0)} in³', 8.5, INK)
    x0, y0 = 160, 70
    s.text(x0 + 10, y0 - 14, 'moments (kip-ft)', 9, GREY, 'start')
    items = [(f'{sym("M_cr_" + sec)}', v(f'M_cr_{sec}', 'kip*ft'), None), (f'1.33 {sym("M_u_" + sec)}', 1.33 * v(f'M_u_{sec}', 'kip*ft'), None),
             (f'{sym("M_min_" + sec)}', v(f'M_min_{sec}', 'kip*ft'), HL), (f'{sym("M_r_" + sec)}', v(f'M_r_{sec}', 'kip*ft'), TEAL), (f'{sym("M_u_" + sec)}', v(f'M_u_{sec}', 'kip*ft'), BLUE)]
    s.bars(x0 + 70, y0, items, width=130, places=2, unit='kip-ft')
    s.text(x0, y0 + 136, 'Mr must reach the lesser of Mcr and 1.33 Mu (LRFD 5.6.3.3)', 9, GREY, 'start')
    if base == 'A_req':
        s.text(x0, y0 + 156, f'{sym("A_req_" + sec)} = {val(e, "A_req_" + sec, 3)} against {sym("A_s")} = {val(e, "A_s", 2)} provided', 9.5, HL, 'start')
    if base == 'DC_minflex':
        s.gauge(x0, y0 + 170, 200, v(name), f'{n(v(name), 3)}')
    rows = {'S_c': [f'{eq(e, "w_w", 0)} × ({n(t, 2)} in)² / 6'],
            'M_cr': [f'{eq(e, "gamma_3", 2)} × {eq(e, "gamma_1", 1)} × {eq(e, "f_r", 3)} × {eq(e, "S_c_" + sec, 0)}', ('gross section with the modulus of rupture', GREY)],
            'M_min': [f'Min({eq(e, "M_cr_" + sec, 2)}, 1.33 × {eq(e, "M_u_" + sec, 3)})', ('1.33 Mu governs: wind is far below cracking', GREY)],
            'A_req': [f'steel for {eq(e, "M_min_" + sec, 3)} at d = {val(e, "d_" + sec, 3)}', ('closed-form rectangular section', GREY)],
            'DC_minflex': [f'{eq(e, "M_min_" + sec, 3)} / {eq(e, "M_r_" + sec, 3)}']}
    s.panel(eq(e, name, 3), rows.get(base, []))
    return s


def crack(e, name):
    v = e.value
    sec = _sec(name)
    base = name[:-2]
    titles = {'f_ct': f'Service I tension on the gross section {sec} against 0.8 fr', 's_cr': f'Crack-control spacing limit at section {sec}',
              'DC_crack': f'Vertical spacing against the crack-control limit at section {sec}'}
    s = Svg(f'{name}: crack control', title=titles.get(base, name))
    fct, fr = v(f'f_ct_{sec}', 'ksi'), v('f_r', 'ksi')
    x0, y0 = 30, 70
    s.text(x0, y0 - 14, 'service tension on the gross section against the 0.8 fr trigger (ksi)', 9, GREY, 'start')
    s.gauge(x0, y0, 220, fct / (0.8 * fr), f'{sym("f_ct_" + sec)} = {n(fct, 4)} ksi', HL if base == 'f_ct' else None, f'0.8 fr = {n(0.8 * fr, 3)}')
    applies = fct > 0.8 * fr
    s.text(x0, y0 + 50, 'below the trigger: the section is uncracked at Service I and LRFD 5.6.7 does not apply' if not applies
           else 'above the trigger: the LRFD 5.6.7 spacing limit applies', 9.5, TEAL if not applies else HL, 'start')
    y1 = y0 + 90
    s.text(x0, y1 - 14, 'vertical bar spacing against the limit (in)', 9, GREY, 'start')
    s.gauge(x0, y1, 220, v(f'DC_crack_{sec}'), f'{sym("s_v")} = {n(v("s_v", "in"), 1)} of {sym("s_cr_" + sec)} = {n(v("s_cr_" + sec, "in"), 1)} in',
            HL if base in ('s_cr', 'DC_crack') else None)
    s.text(x0, y1 + 56, 's = 700 γe / (βs fss) − 2 dc where it applies; 99 in records that it does not', 9, GREY, 'start')
    s.text(x0, y1 + 72, f'{sym("f_ss_" + sec)} = {val(e, "f_ss_" + sec, 3)}, {sym("beta_s_" + sec)} = {val(e, "beta_s_" + sec, 3)}, {sym("d_c_" + sec)} = {val(e, "d_c_" + sec, 3)}', 9, INK, 'start')
    rows = {'f_ct': [f'{eq(e, "M_s_" + sec, 3)} / {eq(e, "S_c_" + sec, 0)}', ('uncracked extreme-fibre tension', GREY)],
            's_cr': [f'{sym("f_ct_" + sec)} ≤ 0.8 {sym("f_r")} → 99 in' if not applies else f'700 {sym("gamma_e")} / ({sym("beta_s_" + sec)} {sym("f_ss_" + sec)}) − 2 {sym("d_c_" + sec)}'],
            'DC_crack': [f'{eq(e, "s_v", 1)} / {eq(e, "s_cr_" + sec, 1)}']}
    s.panel(eq(e, name, 4 if base == 'f_ct' else 3), rows.get(base, []))
    return s


# ----------------------------------------------------------------------------- base shear
def shear(e, name):
    v = e.value
    titles = {'d_v_A': 'Effective shear depth', 'V_c_A': 'Concrete shear resistance, whole wall', 'V_n_A': 'Nominal shear resistance',
              'V_r_A': 'Factored shear resistance', 'DC_shear_A': 'Shear at the cap top'}
    s = Svg(f'{name}: base shear', title=titles.get(name, name))
    _elevation(s, e, 12, 30, 230, 318, wind=f'{sym("P_str")}', shear=f'{sym("V_u")} = {val(e, "V_u", 3)}', bars=False)
    x0, y0 = 260, 70
    s.text(x0, y0 - 14, 'shear (kip)', 9, GREY, 'start')
    items = [(f'{sym("V_u")}', v('V_u', 'kip'), BLUE), (f'{sym("V_c_A")}', v('V_c_A', 'kip'), None), (f'{sym("V_n_A")}', v('V_n_A', 'kip'), None), (f'{sym("V_r_A")}', v('V_r_A', 'kip'), TEAL)]
    hi = {'V_c_A': 1, 'V_n_A': 2, 'V_r_A': 3}.get(name)
    s.bars(x0 + 40, y0, items, width=110, highlight=hi, places=2, unit='kip')
    s.text(x0, y0 + 120, f'{sym("d_v_A")} = {val(e, "d_v_A", 2)} (0.72 h governs); β = {n(v("beta_v"), 1)}', 9.5, HL if name == 'd_v_A' else INK, 'start')
    if name == 'DC_shear_A':
        s.gauge(x0, y0 + 150, 180, v(name), f'{n(v(name), 3)}')
    rows = {'d_v_A': [f'Max({sym("d_A")} − {sym("a_A")}/2, 0.9 {sym("d_A")}, 0.72 {sym("t_w")})', f'{eq(e, "d_A", 3)}, {eq(e, "t_w", 1)}'],
            'V_c_A': [f'0.0316 × {eq(e, "beta_v", 1)} × {eq(e, "lambda_c", 1)} × √{n(v("fc", "ksi"), 1)} × {eq(e, "w_w", 0)} × {eq(e, "d_v_A", 2)}', ('no transverse steel; thickness below 16 in', GREY)],
            'V_n_A': [f'Min({eq(e, "V_c_A", 2)}, 0.25 fc bv dv)'],
            'V_r_A': [f'{eq(e, "phi_v", 2)} × {eq(e, "V_n_A", 2)}'],
            'DC_shear_A': [f'{eq(e, "V_u", 3)} / {eq(e, "V_r_A", 2)}']}
    s.panel(eq(e, name, 3), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- development into the cap
def development(e, name):
    v = e.value
    titles = {'l_db': 'Basic tension development length', 'lambda_rc': 'Confinement factor from the cover in the cap', 'lambda_er': 'Excess reinforcement factor',
              'l_d_full': 'Straight development for full yield, no excess-steel credit', 'l_d': 'Required straight development (12 in floor)',
              'DC_develop': 'Required against provided embedment'}
    s = Svg(f'{name}: development', title=titles.get(name, name))
    Lemb, cb, xv = v('L_emb', 'in'), v('c_b_cap', 'in'), v('x_v', 'in')
    ld, ldf, ldb = v('l_d', 'in'), v('l_d_full', 'in'), v('l_db', 'in')
    # cap end in section with the embedded vertical (looking along the cap: the side face at the left)
    f = Frame(-8, 40, -28, 22, 20, 40, 190, 300)
    s.rect(f.X(0), f.Y(0), f.L(40), f.L(26), fill=CONC, stroke=INK)
    s.rect(f.X(0), f.Y(20), f.L(40), f.L(20), fill=CONC, stroke=INK, sw=0.8)
    s.line(f.X(0), f.Y(0), f.X(40), f.Y(0), GREY, 0.8, '4 3')
    s.text(f.X(20), f.Y(-24) + 4, 'cap', 9, GREY)
    s.text(f.X(20), f.Y(12) + 4, 'wall', 9, GREY)
    s.line(f.X(cb), f.Y(-Lemb), f.X(cb), f.Y(18), AMBER, 2)
    s.dim(f.X(cb) + 14, f.Y(0), f.X(cb) + 14, f.Y(-Lemb), f'{sym("L_emb")} = {n(Lemb, 1)} in', HL if name == 'DC_develop' else INK, side=1)
    s.dim(f.X(0), f.Y(-Lemb) - 12, f.X(cb), f.Y(-Lemb) - 12, f'{sym("c_b_cap")} = {n(cb, 2)} in', HL if name == 'lambda_rc' else INK, side=1)
    s.text(f.X(0) + 2, f.Y(-27) + 4, 'cap side face', 8, GREY, 'start')
    x0, y0 = 230, 70
    s.text(x0, y0 - 14, 'development length (in)', 9, GREY, 'start')
    items = [(f'{sym("l_db")}', ldb, None), (f'{sym("l_d_full")}', ldf, AMBER), (f'{sym("l_d")}', ld, HL), (f'{sym("L_emb")}', Lemb, TEAL)]
    hi = {'l_db': 0, 'l_d_full': 1, 'l_d': 2}.get(name)
    s.bars(x0 + 44, y0, items, width=130, highlight=hi, places=2, unit='in')
    s.text(x0, y0 + 112, f'{sym("lambda_rc")} = {n(v("lambda_rc"), 3)} (0.4 floor) · {sym("lambda_er")} = {n(v("lambda_er"), 3)}', 9.5, INK, 'start')
    s.text(x0, y0 + 128, f'{sym("A_req_A")} = {val(e, "A_req_A", 3)} of {sym("A_s")} = {val(e, "A_s", 2)}', 9, GREY, 'start')
    if name == 'DC_develop':
        s.gauge(x0, y0 + 160, 180, v(name), f'{n(v(name), 3)}')
        s.text(x0, y0 + 206, 'the embedment equals the 12 in minimum exactly', 9, GREY, 'start')
    rows = {'l_db': [f'2.4 × {eq(e, "d_b_v", 3)} × {n(v("fy", "ksi"), 0)} / √{n(v("fc", "ksi"), 1)}', ('LRFD Eq. 5.10.8.2.1a-2', GREY)],
            'lambda_rc': [f'Max(0.4, Min(1, {eq(e, "d_b_v", 3)} / {eq(e, "c_b_cap", 2)}))', ('no transverse reinforcement credited', GREY)],
            'lambda_er': [f'Min(1, {eq(e, "A_req_A", 3)} / {eq(e, "A_s", 2)})', ('steel the minimum design moment requires', GREY)],
            'l_d_full': [f'{eq(e, "l_db", 2)} × {n(v("lambda_rl"), 1)} × {n(v("lambda_cf"), 1)} × {eq(e, "lambda_rc", 2)} / {n(v("lambda_lw"), 1)}', ('without λer: just above the 12 in embedment', AMBER)],
            'l_d': [f'Max(12 in, {eq(e, "l_d_full", 2)} × {eq(e, "lambda_er", 3)})', ('the 12 in minimum governs', GREY)],
            'DC_develop': [f'{eq(e, "l_d", 2)} / {eq(e, "L_emb", 1)}']}
    s.panel(eq(e, name, 3), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- interface shear at the joint
def interface(e, name):
    v = e.value
    titles = {'A_cv': 'Interface area at the construction joint', 'A_vf': 'Reinforcement crossing the joint', 'V_ni': 'Nominal interface shear resistance',
              'V_ri': 'Factored interface shear resistance', 'A_vf_min': 'Minimum interface reinforcement', 'DC_interface': 'Interface shear at the joint',
              'DC_interface_min': 'Minimum interface reinforcement against the verticals'}
    s = Svg(f'{name}: construction joint', title=titles.get(name, name))
    w, t = v('w_w', 'in'), v('t_w', 'in')
    nv = int(v('n_v'))
    f = Frame(-6, t + 70, -6, w + 6, 20, 40, 170, 300)
    s.rect(f.X(0), f.Y(w), f.L(t), f.L(w), fill=CONC, stroke=INK, sw=1.2)
    s.hatch(f.X(0), f.Y(w), f.L(t), f.L(w), GREY, 9)
    for y in _bar_stations(nv, w, v('c_edge', 'in') + v('d_b_v', 'in') / 2):
        s.circle(f.X(v('x_v', 'in')), f.Y(y), 3.2, fill=AMBER)
    s.text(f.X(t / 2), f.Y(w) - 8, 'joint plane (plan)', 8.5, GREY)
    s.dim(f.X(0), f.Y(0) + 14, f.X(t), f.Y(0) + 14, f'{n(t, 0)} in', INK, side=1)
    s.dim(f.X(t) + 14, f.Y(0), f.X(t) + 14, f.Y(w), f'{n(w, 0)} in', INK, side=1)
    s.arrow(f.X(t) + 60, f.Y(w / 2) + 40, f.X(t) + 60, f.Y(w / 2) - 10, HL, 2.2, 8)
    s.tag(f.X(t) + 64, f.Y(w / 2) + 20, f'{sym("V_u")} = {val(e, "V_u", 3)}', HL, 'start')
    x0, y0 = 214, 70
    s.text(x0, y0 - 14, 'interface resistance limits (kip)', 9, GREY, 'start')
    c, mu = v('c_if', 'ksi'), v('mu_if')
    Acv, Avf, fy = v('A_cv', 'in^2'), v('A_vf', 'in^2'), v('fy', 'ksi')
    items = [('c Acv + μ Avf fy', c * Acv + mu * Avf * fy, None), ('K1 fc Acv', v('K1_if') * v('fc', 'ksi') * Acv, None), ('K2 Acv', v('K2_if', 'ksi') * Acv, None),
             (f'{sym("V_ri")} = φ Vni', v('V_ri', 'kip'), TEAL), (f'{sym("V_u")}', v('V_u', 'kip'), BLUE)]
    s.bars(x0 + 90, y0, items, width=78, places=1, unit='kip')
    s.text(x0, y0 + 136, f'{sym("A_vf")} = {val(e, "A_vf", 2)} provided · {sym("A_vf_min")} = {val(e, "A_vf_min", 2)}', 9.5, HL if name in ('A_vf_min', 'DC_interface_min') else INK, 'start')
    if name.startswith('DC_'):
        s.gauge(x0, y0 + 160, 180, v(name), f'{n(v(name), 3)}')
    rows = {'A_cv': [f'{eq(e, "w_w", 0)} × {eq(e, "t_w", 0)}', ('the whole wall footprint on the cap top', GREY)],
            'A_vf': [f'= {eq(e, "A_s", 2)}', ('the six verticals cross the joint', GREY)],
            'V_ni': [f'Min({n(c, 3)} × {n(Acv, 0)} + {n(mu, 1)} × {n(Avf, 2)} × {n(fy, 0)}, K1 fc Acv, K2 Acv)', ('clean joint not roughened; Pc = 0', GREY)],
            'V_ri': [f'{eq(e, "phi_v", 2)} × {eq(e, "V_ni", 2)}'],
            'A_vf_min': [f'0.05 × {eq(e, "A_cv", 0)} / {eq(e, "fy", 0)}'],
            'DC_interface': [f'{eq(e, "V_u", 3)} / {eq(e, "V_ri", 2)}'],
            'DC_interface_min': [f'{eq(e, "A_vf_min", 2)} / {eq(e, "A_vf", 2)}']}
    s.panel(eq(e, name, 3), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- material constants and bars
def materials(e, name):
    v = e.value
    titles = {'beta_1': 'Stress block factor from the concrete strength', 'E_c': 'Concrete modulus', 'n_m': 'Modular ratio', 'f_r': 'Modulus of rupture',
              'f_ss_lim': 'Service steel stress limit', 'd_b_v': 'Vertical bar diameter', 'A_b_v': 'Vertical bar area', 'd_b_h': 'Horizontal bar diameter',
              'A_b_h': 'Horizontal bar area'}
    s = Svg(f'{name}: materials', title=titles.get(name, name))
    x, y = 24, 70
    hl = lambda key: HL if name == key else INK
    steps = [(f'f′c = {n(v("fc", "ksi"), 1)} ksi · fy = {n(v("fy", "ksi"), 0)} ksi · Es = {n(v("Es", "ksi"), 0)} ksi', INK),
             (f'{sym("beta_1")} = {n(v("beta_1"), 3)}', hl('beta_1')), (f'{sym("E_c")} = {val(e, "E_c", 0)}', hl('E_c')), (f'{sym("n_m")} = {n(v("n_m"), 3)}', hl('n_m')),
             (f'{sym("f_r")} = {val(e, "f_r", 3)}', hl('f_r')), (f'{sym("f_ss_lim")} = {val(e, "f_ss_lim", 1)}', hl('f_ss_lim'))]
    for i, (markup, color) in enumerate(steps):
        yy = y + i * 30
        s.rect(x, yy - 14, 270, 22, fill='#fff', stroke=color, sw=1.3, rx=4)
        s.text(x + 8, yy + 1, markup, 10, color, 'start', 'bold' if color == HL else 'normal')
    # bars
    bx, by = 340, 110
    for i, (tag, dname, aname) in enumerate((('vertical', 'd_b_v', 'A_b_v'), ('horizontal', 'd_b_h', 'A_b_h'))):
        r = max(6, 22 * v(dname, 'in'))
        cy = by + i * 90
        s.circle(bx, cy, r, fill=STEEL, stroke=HL if name in (dname, aname) else INK, sw=1.4)
        s.text(bx + 36, cy - 6, f'{tag} {escape(str(e.engine.get("bar_v" if i == 0 else "bar_h")))}', 10, INK, 'start')
        s.text(bx + 36, cy + 8, f'{sym(dname)} = {val(e, dname, 3)}', 9.5, HL if name == dname else INK, 'start')
        s.text(bx + 36, cy + 22, f'{sym(aname)} = {val(e, aname, 2)}', 9.5, HL if name == aname else INK, 'start')
    rows = {'beta_1': [f'0.85 − 0.05 (f′c − 4) between 0.65 and 0.85'],
            'E_c': [f'120000 × {eq(e, "K_1", 1)} × {eq(e, "w_cE", 4)}² × {n(v("fc", "ksi"), 1)}^0.33'],
            'n_m': [f'{eq(e, "Es", 0)} / {eq(e, "E_c", 0)}'],
            'f_r': [f'0.24 × {eq(e, "lambda_c", 1)} × √{n(v("fc", "ksi"), 1)}'],
            'f_ss_lim': [f'{eq(e, "fss_ratio", 2)} × {eq(e, "fy", 0)}', ('SDG 3.10.F', GREY)],
            'd_b_v': [f'{escape(str(e.engine.get("bar_v")))} bar'], 'A_b_v': [f'{escape(str(e.engine.get("bar_v")))} bar'],
            'd_b_h': [f'{escape(str(e.engine.get("bar_h")))} bar'], 'A_b_h': [f'{escape(str(e.engine.get("bar_h")))} bar']}
    s.panel(eq(e, name, 3), rows.get(name, []))
    return s


drawer = make_drawer({'t_B': elevation, 'H_B': elevation, 'A_face': elevation, 'A_edge': elevation, 'z_c': elevation, 'W_wall': elevation,
                      'w_u': elevation, 'V_u': elevation, 'M_u_A': elevation, 'M_u_B': elevation, 'w_s': elevation, 'M_s_A': elevation, 'M_s_B': elevation,
                      'F_T_III': elevation, 'F_T_SI': elevation, 'M_T_III': elevation, 'M_T_SI': elevation,
                      'F_L_III': plan, 'F_L_SI': plan, 'F_T_III_both': plan, 'F_L_III_both': plan,
                      'P_str': pressure, 'P_ser': pressure, 'DC_govern': pressure,
                      'A_s': face, 'b_ts': face, 'A_ts_face': face, 'A_ts_mat': face, 'A_pr_v': face, 'A_pr_h': face, 's_max_pri': face, 's_max_ts': face,
                      's_clr_min': face, 's_clr_v': face, 's_clr_h': face, 's_clr_prov': face, 'DC_temp_v': face, 'DC_temp_h': face, 'DC_space_v': face,
                      'DC_space_h': face, 'DC_clear': face, 'DC_cover': face, 'DC_thick': face,
                      'd_v_A': shear, 'V_c_A': shear, 'V_n_A': shear, 'V_r_A': shear, 'DC_shear_A': shear,
                      'l_db': development, 'lambda_rc': development, 'lambda_er': development, 'l_d_full': development, 'l_d': development, 'DC_develop': development,
                      'A_cv': interface, 'A_vf': interface, 'V_ni': interface, 'V_ri': interface, 'A_vf_min': interface, 'DC_interface': interface, 'DC_interface_min': interface,
                      'beta_1': materials, 'E_c': materials, 'n_m': materials, 'f_r': materials, 'f_ss_lim': materials, 'd_b_v': materials, 'A_b_v': materials,
                      'd_b_h': materials, 'A_b_h': materials},
                     [(r'^(q|P)_(III|V|SI)$', pressure),
                      (r'^(S_c|M_cr|M_min|A_req|DC_minflex)_(A|B)$', minflex),
                      (r'^(f_ct|s_cr|DC_crack)_(A|B)$', crack),
                      (r'^(d|a|c|eps_t|phi|M_n|M_r|rho|k|j|f_ss|d_c|beta_s|DC_fss|DC_flex)_(A|B)$', section)])
