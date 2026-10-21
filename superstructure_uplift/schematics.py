"""'What it represents' drawings for the superstructure uplift and bearing reaction calculation (C004).

Scenes drawn from the current case: the transverse section at the pier (deck, two beam lines, bearing plane, wind
line loads at their lever arms, upward wind at its eccentricity, factored dead load and the two line reactions); the
plan of the pier with its four physical bearings and the tributary lengths that turn line loads into bearing forces;
the FB-MultiPier node transfer with its residual moments; and the coherence and equilibrium checks as balances.
"""
from html import escape
from calc_common.schematics import (Svg, Frame, sym, val, eq, n, make_drawer, schematic as _schematic, meaning as _meaning,
                                    INK, GREY, FAINT, HL, BLUE, TEAL, AMBER, PURPLE, CONC, SOIL, SLAB, PX)
from .model import SPEC


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)


def _chk(e, name):
    return str(e.engine.get(name))


# ----------------------------------------------------------------------------- transverse section at the pier
def _section(s, e, left, top, width, height, loads=(), reactions=False, hl=None):
    """Deck and two beams on the bearing plane above the cap reference; loads per foot of bridge."""
    v = e.value
    b, sp, zb = v('b', 'ft'), v('s', 'ft'), v('z_b', 'ft')
    d, hc, hf = v('Depth_SuperStr', 'ft'), v('h_c', 'ft'), v('h_f', 'ft')
    ecc = v('e', 'ft')
    top_z = zb + hf + 2.5
    f = Frame(-b * 0.95, b * 0.95, -3.2, top_z, left, top, width, height)
    # cap and reference
    s.rect(f.X(-sp / 2 - 1.5), f.Y(zb - 0.7), f.L(sp + 3), f.L(zb + 2.3), fill=CONC, stroke=INK)
    s.circle(f.X(0), f.Y(0), 3.5, fill=HL)
    s.tag(f.X(0), f.Y(0) + 14, 'cap reference', HL)
    s.line(f.X(-b * 0.95), f.Y(0), f.X(b * 0.95), f.Y(0), GREY, 0.7, '4 3')
    # bearings, beams, deck
    for x in (-sp / 2, sp / 2):
        s.rect(f.X(x - 0.9), f.Y(zb), f.L(1.8), f.L(0.22), fill='#30475e', stroke='none')
        s.rect(f.X(x - 0.5), f.Y(zb + d * 0.78), f.L(1.0), f.L(d * 0.78 - 0.22), fill=CONC, stroke=INK, sw=0.8)
    s.rect(f.X(-b / 2), f.Y(zb + d), f.L(b), f.L(d * 0.22), fill=SLAB, stroke=INK)
    s.line(f.X(-b * 0.9), f.Y(zb), f.X(b * 0.9), f.Y(zb), INK, 0.8, '5 3')
    s.tag(f.X(b * 0.9), f.Y(zb) - 4, 'bearing plane', GREY, 'end')
    s.dim(f.X(-sp / 2), f.Y(-2.2), f.X(sp / 2), f.Y(-2.2), f's = {n(sp, 3)} ft between beam lines', HL if hl == 's' else INK, side=1)
    s.dim(f.X(b * 0.8), f.Y(0), f.X(b * 0.8), f.Y(zb), f'{sym("z_b")} = {n(zb, 3)} ft', HL if hl == 'z_b' else INK, side=1)
    s.text(f.X(-b / 2) + 4, f.Y(zb + d) - 5, 'windward', 8.5, GREY, 'start')
    s.text(f.X(b / 2) - 4, f.Y(zb + d) - 5, 'leeward', 8.5, GREY, 'end')
    s.text(f.X(0), f.Y(zb + d * 0.89) + 3, f'b = {n(b, 2)} ft deck', 8.5, GREY)
    col = lambda key, default=BLUE: HL if hl == key else default
    xw = f.X(-b / 2) - 6
    if 'wind' in loads:
        s.arrow(xw - 70, f.Y(zb + hc), xw, f.Y(zb + hc), col('w_c'), 2.2, 8)
        s.tag(xw - 70, f.Y(zb + hc) - 8, f'{sym("w_c_III")} = {val(e, "w_c_III", 3)}', col('w_c'), 'start')
        s.dim(f.X(-sp / 2) - 10, f.Y(zb), f.X(-sp / 2) - 10, f.Y(zb + hc), f'{sym("h_c")} = {n(hc, 3)} ft', col('h_c', INK), side=-1)
        s.arrow(xw - 70, f.Y(zb + hf), xw, f.Y(zb + hf), col('w_f'), 2.2, 8)
        s.tag(xw - 70, f.Y(zb + hf) - 8, f'{sym("w_f_III")} = {val(e, "w_f_III", 3)}', col('w_f'), 'start')
        s.dim(f.X(-sp / 2) - 40, f.Y(zb), f.X(-sp / 2) - 40, f.Y(zb + hf), f'{sym("h_f")} = {n(hf, 3)} ft', col('h_f', INK), side=-1)
        s.rect(f.X(-b / 2 + 0.3), f.Y(zb + hf + 1.2), f.L(b - 0.6), f.L(2.4), fill='none', stroke=GREY, sw=0.8, dash='3 2')
        s.text(f.X(0), f.Y(zb + hf) + 3, 'fence band', 8.5, GREY)
    if 'uplift' in loads:
        xr = f.X(-ecc)
        s.arrow(xr, f.Y(zb + 0.35), xr, f.Y(zb + d * 0.78) + 1, col('w_U'), 2.2, 8)
        s.tag(xr + 7, f.Y(zb + d * 0.45) + 4, f'{sym("w_U_III")} = {val(e, "w_U_III", 3)} up', col('w_U'), 'start')
        s.dim(f.X(0), f.Y(zb + d + 0.8), xr, f.Y(zb + d + 0.8), f'e = {n(ecc, 3)} ft', col('e', INK), side=-1, offset=8)
    if 'dead' in loads:
        s.arrow(f.X(0), f.Y(top_z - 0.3), f.X(0), f.Y(zb + d + 0.3), col('w_D', PURPLE), 2.2, 8)
        s.tag(f.X(0) + 6, f.Y(top_z - 0.3) + 10, f'{sym("w_D_III")} = {val(e, "w_D_III", 3)} down', col('w_D', PURPLE), 'start')
    if reactions:
        rw, rl = v('r_W_III', 'kip/ft'), v('r_L_III', 'kip/ft')
        for x, r, key in ((-sp / 2, rw, 'r_W'), (sp / 2, rl, 'r_L')):
            color = col(key, TEAL)
            if r >= 0:
                s.arrow(f.X(x), f.Y(zb) + 34, f.X(x), f.Y(zb) + 3, color, 2.2, 8)
            else:
                s.arrow(f.X(x), f.Y(zb) + 3, f.X(x), f.Y(zb) + 34, color, 2.2, 8)
            s.tag(f.X(x) + (-8 if x < 0 else 8), f.Y(zb) + 24, f'{sym(key + "_III")} = {n(r, 3)} klf', color, 'end' if x < 0 else 'start')
    return f


SECTION_TITLES = {
    'h_c': 'Lever arm of the concrete superstructure wind above the bearing plane', 'h_f': 'Lever arm of the fence wind above the bearing plane',
    'w_H_III': 'Concurrent factored transverse wind per foot of bridge', 'w_U_III': 'Concurrent factored upward wind per foot',
    'w_D_III': 'Minimum factored downward dead load per foot', 'm_H_III': 'Overturning moment per foot from horizontal wind',
    'm_U_III': 'Overturning moment per foot from eccentric upward wind', 'm_OT_III': 'Combined overturning moment per foot about the bearing plane',
    'r_W_III': 'Windward beam-line reaction per foot', 'r_L_III': 'Leeward beam-line reaction per foot',
    'm_stab_III': 'Stabilizing moment per foot about the leeward bearing line', 'm_destab_III': 'Destabilizing wind moment per foot about the leeward bearing line',
    'DC_OT_III': 'Overturning demand against the stabilizing moment', 'DC_uplift_III': 'Upward wind against the minimum downward load',
    'Chk_uplift_III': 'Net vertical compression on the superstructure', 'Chk_OT_III': 'Transverse overturning about the leeward bearings',
}


def section(e, name):
    s = Svg(f'{name}: section', title=SECTION_TITLES.get(name, name))
    hl = {'h_c': 'h_c', 'h_f': 'h_f', 'w_U_III': 'w_U', 'w_D_III': 'w_D', 'm_U_III': 'e', 'r_W_III': 'r_W', 'r_L_III': 'r_L'}.get(name)
    loads = {'h_c': ('wind',), 'h_f': ('wind',), 'w_H_III': ('wind',), 'w_U_III': ('uplift',), 'w_D_III': ('dead',), 'm_H_III': ('wind',),
             'm_U_III': ('uplift',), 'm_OT_III': ('wind', 'uplift'), 'DC_uplift_III': ('uplift', 'dead'), 'Chk_uplift_III': ('uplift', 'dead')}
    loads = loads.get(name, ('wind', 'uplift', 'dead'))
    reactions = name in ('r_W_III', 'r_L_III', 'm_stab_III', 'm_destab_III', 'DC_OT_III', 'Chk_OT_III')
    f = _section(s, e, 12, 36, PX - 40, 300, loads=loads, reactions=reactions, hl=hl)
    v = e.value
    sp, zb, d = v('s', 'ft'), v('z_b', 'ft'), v('Depth_SuperStr', 'ft')
    if name in ('m_H_III', 'm_U_III', 'm_OT_III'):
        s.moment(f.X(sp / 2) + 40, f.Y(zb + d / 2), 18, True, HL, f'{sym(name)} = {val(e, name, 3)} per ft')
    if name in ('m_stab_III', 'm_destab_III', 'DC_OT_III', 'Chk_OT_III'):
        s.circle(f.X(sp / 2), f.Y(zb), 5, fill='none', stroke=HL, sw=2)
        s.tag(f.X(sp / 2) + 8, f.Y(zb) - 8, 'pivot: leeward bearing line', HL, 'start')
        s.dim(f.X(0), f.Y(zb - 1.6), f.X(sp / 2), f.Y(zb - 1.6), 's/2', INK, side=1)
    g = {'DC': f'{eq(e, "γ_DC_III", 2)}, {eq(e, "γ_DW_III", 2)}, {eq(e, "γ_WS_III", 2)}', 'eta': f'{eq(e, "η_bearing", 2)}'}
    rows = {'h_c': [f'{eq(e, "Depth_SuperStr", 2, "ft")} / 2', ('concrete wind resultant at mid-depth of the superstructure', GREY)],
            'h_f': [f'{eq(e, "Fence_CG_CapCG", 3, "ft")} − {eq(e, "BearingPlane_CapCG", 3, "ft")}', ('fence band centroid above the bearing plane', GREY)],
            'w_H_III': [f'{g["eta"]} × {eq(e, "γ_WS_III", 2)} × ({eq(e, "w_c_III", 3)} + {eq(e, "w_f_III", 3)})'],
            'w_U_III': [f'{g["eta"]} × {eq(e, "γ_WS_III", 2)} × {eq(e, "w_V_III", 3)}', ('vertical wind of C001 at its quarter-point eccentricity', GREY)],
            'w_D_III': [f'{g["eta"]} × ({eq(e, "γ_DC_III", 2)} × {eq(e, "w_DC", 3)}', f'+ {eq(e, "γ_DW_III", 2)} × {eq(e, "w_DW", 3)})', ('minimum factors: least stabilizing weight', GREY)],
            'm_H_III': [f'{g["eta"]}·{eq(e, "γ_WS_III", 2)} × ({sym("w_c_III")}·{sym("h_c")} + {sym("w_f_III")}·{sym("h_f")})',
                        f'= {n(v("w_c_III", "kip/ft"), 3)}×{n(v("h_c", "ft"), 3)} + {n(v("w_f_III", "kip/ft"), 3)}×{n(v("h_f", "ft"), 3)}'],
            'm_U_III': [f'{eq(e, "w_U_III", 3)} × {eq(e, "e", 3, "ft")}', ('upward wind acting off the centerline', GREY)],
            'm_OT_III': [f'{eq(e, "m_H_III", 3)} + {eq(e, "m_U_III", 3)}', ('both roll the deck toward the leeward line', GREY)],
            'r_W_III': [f'({sym("w_D_III")} − {sym("w_U_III")})/2 − {sym("m_OT_III")}/s', f'= ({n(v("w_D_III", "kip/ft"), 3)} − {n(v("w_U_III", "kip/ft"), 3)})/2 − {n(v("m_OT_III", "kip"), 3)}/{n(sp, 3)}',
                        ('positive = compression on the bearings', GREY)],
            'r_L_III': [f'({sym("w_D_III")} − {sym("w_U_III")})/2 + {sym("m_OT_III")}/s', f'= ({n(v("w_D_III", "kip/ft"), 3)} − {n(v("w_U_III", "kip/ft"), 3)})/2 + {n(v("m_OT_III", "kip"), 3)}/{n(sp, 3)}'],
            'm_stab_III': [f'{eq(e, "w_D_III", 3)} × s/2 = × {n(sp / 2, 3)} ft', ('factored dead load at the centerline resists rolling', GREY)],
            'm_destab_III': [f'{eq(e, "m_H_III", 3)} + {eq(e, "w_U_III", 3)} × (s/2 + e)', f'= … × ({n(sp / 2, 3)} + {n(v("e", "ft"), 3)}) ft'],
            'DC_OT_III': [f'{eq(e, "m_destab_III", 3)} / {eq(e, "m_stab_III", 3)}', ('below 1.0: the deck does not roll over the leeward bearings', GREY)],
            'DC_uplift_III': [f'{eq(e, "w_U_III", 3)} / {eq(e, "w_D_III", 3)}', ('below 1.0: net load stays downward', GREY)],
            'Chk_uplift_III': [f'{eq(e, "w_D_III", 3)} > {eq(e, "w_U_III", 3)}'],
            'Chk_OT_III': [f'{eq(e, "DC_OT_III", 3)} &lt; 1']}
    is_check = name.startswith('Chk')
    s.panel(f'{sym(name)} = {escape(_chk(e, name))}' if is_check else eq(e, name, 3), rows.get(name, []))
    if is_check:
        s.status(PX, 160, _chk(e, name))
    if name in ('DC_OT_III', 'DC_uplift_III'):
        s.gauge(PX, 150, 220, v(name), f'{n(v(name), 3)}')
    return s


# ----------------------------------------------------------------------------- plan with the physical bearings
def _plan(s, e, left, top, width, height, hl_bearings=(), hl_row=None, show_trib=True):
    """Plan of the pier: beam lines at ±s/2, bearing rows at ±k, deck strip with the tributary lengths."""
    v = e.value
    sp, k, b = v('s', 'ft'), v('k', 'ft'), v('b', 'ft')
    l1, l2 = v('l_1', 'ft'), v('l_2', 'ft')
    half = 8.0                                             # ft of deck shown either side of the pier (broken beyond)
    f = Frame(-half - 1, half + 1, -b * 0.62, b * 0.62, left, top, width, height)
    # deck strip (plan, broken at both ends) and the pier cap
    s.rect(f.X(-half), f.Y(b / 2), f.L(2 * half), f.L(b), fill=SLAB, stroke='none')
    for yy in (b / 2, -b / 2):
        s.line(f.X(-half), f.Y(yy), f.X(half), f.Y(yy), INK, 0.8)
    for xx in (-half, half):
        pts = [(f.X(xx), f.Y(b / 2))]
        steps = 8
        for i in range(1, steps + 1):
            pts.append((f.X(xx) + (5 if i % 2 else -5), f.Y(b / 2 - b * i / steps)))
        s.poly(pts, stroke=INK, sw=0.9, closed=False)
    s.rect(f.X(-k - 1.2), f.Y(sp / 2 + 1.4), f.L(2 * k + 2.4), f.L(sp + 2.8), fill=CONC, stroke=INK, op=0.9)
    for y in (-sp / 2, sp / 2):
        s.line(f.X(-half), f.Y(y), f.X(half), f.Y(y), GREY, 0.8, '6 3')
    s.text(f.X(-half) + 8, f.Y(-sp / 2) - 5, 'windward beam line', 8, GREY, 'start')
    s.text(f.X(-half) + 8, f.Y(sp / 2) + 12, 'leeward beam line', 8, GREY, 'start')
    s.line(f.X(0), f.Y(b * 0.6), f.X(0), f.Y(-b * 0.6), INK, 0.8, '4 2')
    s.tag(f.X(0), f.Y(b * 0.6) - 3, 'pier ℄', GREY)
    pads = {'W1': (-k, -sp / 2), 'L1': (-k, sp / 2), 'W2': (k, -sp / 2), 'L2': (k, sp / 2)}
    for key, (x, y) in pads.items():
        hit = key in hl_bearings or (hl_row and key.endswith(hl_row))
        s.rect(f.X(x) - 9, f.Y(y) - 6, 18, 12, fill='#f6d6d3' if hit else '#30475e', stroke=HL if hit else INK, sw=1.4 if hit else 0.8)
        s.tag(f.X(x) + (-13 if x < 0 else 13), f.Y(y) + 4, key, HL if hit else INK, 'end' if x < 0 else 'start')
    s.dim(f.X(-k), f.Y(-sp / 2 - 1.6), f.X(k), f.Y(-sp / 2 - 1.6), f'2k = 2 × {n(k, 3)} ft', INK, side=1, offset=8)
    s.dim(f.X(half * 0.6), f.Y(-sp / 2), f.X(half * 0.6), f.Y(sp / 2), f's = {n(sp, 3)} ft', INK, side=1)
    if show_trib:
        s.rect(f.X(-half), f.Y(b / 2), f.L(half), f.L(b), fill='#f6d6d3', stroke='none', op=0.45)
        s.rect(f.X(0), f.Y(b / 2), f.L(half), f.L(b), fill='#dbe9f5', stroke='none', op=0.6)
        s.arrow(f.X(-1), f.Y(b * 0.42), f.X(-half) + 10, f.Y(b * 0.42), INK, 1.2, 6)
        s.tag(f.X(-half * 0.55), f.Y(b * 0.42) - 6, f'{sym("l_1")} = {n(l1, 3)} ft to mid-Span 1', INK)
        s.arrow(f.X(1), f.Y(b * 0.42), f.X(half) - 10, f.Y(b * 0.42), INK, 1.2, 6)
        s.tag(f.X(half * 0.55), f.Y(b * 0.42) - 6, f'{sym("l_2")} = {n(l2, 3)} ft to mid-Span 2', INK)
    s.text(f.X(-half) + 8, f.Y(-b / 2) + 12, '← Span 1 (broken, not to scale)', 8.5, GREY, 'start')
    s.text(f.X(half) - 8, f.Y(-b / 2) + 12, 'Span 2 →', 8.5, GREY, 'end')
    return f


def _row(name):
    return '1' if name.endswith('1_III') else '2' if name.endswith('2_III') else None


PLAN_TITLES = {'l_P': 'Tributary length of the pier: half of each adjoining span', 'R_min_III': 'Smallest bearing compression of the four physical bearings',
               'T_req_III': 'Tensile restraint a bearing would need', 'Chk_contact_III': 'Contact kept at every bearing', 'H_P_III': 'Total transverse wind at the pier',
               'M_L_total_III': 'Total roll moment at the cap reference', 'ΔN_minus_III': 'Change of the negative-transverse node load from wind',
               'ΔN_plus_III': 'Change of the positive-transverse node load from wind'}


def plan(e, name):
    v = e.value
    row = _row(name)
    base = name[:-5] if row else name
    titles = {'R_W': 'Windward bearing compression', 'R_L': 'Leeward bearing compression', 'H_': 'Transverse wind delivered by the span end',
              'U_': 'Upward wind delivered by the span end', 'D_': 'Factored downward load delivered by the span end', 'H_pad': 'Horizontal wind on one bearing'}
    title = PLAN_TITLES.get(name) or next((t + f', Span {row} end' for k, t in titles.items() if base.startswith(k)), name)
    s = Svg(f'{name}: plan', title=title)
    hl = []
    if row:
        if base == 'R_W':
            hl = ['W' + row]
        elif base == 'R_L':
            hl = ['L' + row]
    if name in ('R_min_III', 'T_req_III', 'Chk_contact_III'):
        rmin = v('R_min_III', 'kip')
        hl = [k for k in ('W1', 'L1', 'W2', 'L2') if abs(v('R_' + k + '_III', 'kip') - rmin) < 1e-9]
    f = _plan(s, e, 12, 40, PX - 40, 262, hl_bearings=hl, hl_row=row if base in ('H_', 'U_', 'D_', 'H_pad') else None)
    sp, k = v('s', 'ft'), v('k', 'ft')
    # bearing force table at the bottom
    y = 336
    s.text(12, y, 'bearing compressions, kip (Strength III):', 9, GREY, 'start')
    xs = 220
    for key in ('W1', 'L1', 'W2', 'L2'):
        val_k = v('R_' + key + '_III', 'kip')
        color = HL if key in hl else INK
        s.text(xs, y, f'{key} = {n(val_k, 2)}', 9.5, color, 'start', 'bold' if key in hl else 'normal')
        xs += 60
    rows = []
    if base in ('R_W', 'R_L'):
        rows = [f'{eq(e, ("r_W_III" if base == "R_W" else "r_L_III"), 3)} × {eq(e, "l_" + row, 3)}', ('line reaction per foot × tributary length of this end', GREY)]
    elif base in ('H_', 'U_', 'D_'):
        src = {'H_': 'w_H_III', 'U_': 'w_U_III', 'D_': 'w_D_III'}[base]
        rows = [f'{eq(e, src, 3)} × {eq(e, "l_" + row, 3)}']
    elif base == 'H_pad':
        rows = [f'{eq(e, "H_" + row + "_III", 2)} / Beam_count = {n(v("Beam_count"), 0)}', ('shared equally by the two bearings of this row', GREY)]
    elif name == 'l_P':
        rows = [f'{eq(e, "l_1", 3)} + {eq(e, "l_2", 3)}']
    elif name == 'R_min_III':
        rows = [f'Min({sym("R_W1_III")}, {sym("R_L1_III")}, {sym("R_W2_III")}, {sym("R_L2_III")})', ('the windward Span 1 bearing carries the least', GREY) if hl == ['W1'] else ('smallest of the four', GREY)]
    elif name == 'T_req_III':
        rows = [f'Max(0, −{eq(e, "R_min_III", 2)})', ('zero while every bearing stays in compression', GREY)]
    elif name == 'Chk_contact_III':
        rows = [f'{eq(e, "R_min_III", 2)} > 0']
    elif name == 'H_P_III':
        rows = [f'{eq(e, "H_1_III", 2)} + {eq(e, "H_2_III", 2)}']
    elif name == 'M_L_total_III':
        rows = [f'{eq(e, "m_OT_III", 3)} × {eq(e, "l_P", 2)}', f'+ {eq(e, "H_P_III", 2)} × {eq(e, "z_b", 3, "ft")}', ('roll from the deck plus the wind shear carried down to the cap reference', GREY)]
    elif name.startswith('ΔN'):
        sign = '−' if 'minus' in name else '+'
        rows = [f'−{sym("w_U_III")}·{sym("l_P")}/2 {sign} {sym("m_OT_III")}·{sym("l_P")}/s', f'= −{n(v("w_U_III", "kip/ft"), 3)}×{n(v("l_P", "ft"), 2)}/2 {sign} {n(v("m_OT_III", "kip"), 3)}×{n(v("l_P", "ft"), 2)}/{n(sp, 3)}',
                ('wind-only change of the beam-line node load', GREY)]
    is_check = name.startswith('Chk')
    s.panel(f'{sym(name)} = {escape(_chk(e, name))}' if is_check else eq(e, name, 3), rows)
    if is_check:
        s.status(PX, 160, _chk(e, name))
    return s


# ----------------------------------------------------------------------------- FB-MultiPier node transfer
def nodes(e, name):
    v = e.value
    titles = {'N_minus_III': 'Collected negative-transverse pier-node load', 'N_plus_III': 'Collected positive-transverse pier-node load',
              'M_L_res_III': 'Residual roll moment between the bearing plane and the cap reference', 'M_T_res_III': 'Residual pitch moment from collecting the two bearing rows',
              'M_V_res_III': 'Residual yaw moment from unequal span wind'}
    s = Svg(f'{name}: nodes', title=titles.get(name, name))
    sp, zb, k = v('s', 'ft'), v('z_b', 'ft'), v('k', 'ft')
    if name in ('N_minus_III', 'N_plus_III', 'M_L_res_III'):
        f = _section(s, e, 12, 36, 300, 300)
        for x, key in ((-sp / 2, 'N_minus_III'), (sp / 2, 'N_plus_III')):
            color = HL if key == name else TEAL
            s.circle(f.X(x), f.Y(0), 5, fill='#fff', stroke=color, sw=2)
            s.arrow(f.X(x), f.Y(0) + 46, f.X(x), f.Y(0) + 8, color, 2.2, 8)
            s.tag(f.X(x), f.Y(0) + 60, f'{sym(key)} = {val(e, key, 2)}', color)
        s.text(f.X(-sp / 2), f.Y(0) + 74, 'node −T', 8.5, GREY)
        s.text(f.X(sp / 2), f.Y(0) + 74, 'node +T', 8.5, GREY)
        hp = HL if name == 'M_L_res_III' else BLUE
        s.arrow(f.X(-sp / 2) - 80, f.Y(zb), f.X(-sp / 2) - 14, f.Y(zb), hp, 2.2, 8)
        s.tag(f.X(-sp / 2) - 80, f.Y(zb) - 8, f'{sym("H_P_III")} = {val(e, "H_P_III", 2)}', hp, 'start')
        if name == 'M_L_res_III':
            s.moment(f.X(sp / 2) + 46, f.Y(zb / 2), 16, True, HL, f'{sym(name)} = {val(e, name, 2)}')
    else:
        f = _plan(s, e, 12, 40, PX - 40, 290, show_trib=False)
        if name == 'M_T_res_III':
            for x, row in ((-k, '1'), (k, '2')):
                net = v('D_' + row + '_III', 'kip') - v('U_' + row + '_III', 'kip')
                s.tag(f.X(x) + (-28 if row == '1' else 28), f.Y(0) + 4, f'row {row}: D−U = {n(net, 2)} kip', PURPLE, 'end' if row == '1' else 'start')
            s.moment(f.X(k) + 46, f.Y(0), 16, True, HL, f'{sym(name)} = {val(e, name, 2)} (pitch)')
        else:
            for x, row in ((-k, '1'), (k, '2')):
                s.arrow(f.X(x) + (-60 if row == '1' else 60), f.Y(-sp / 2) - 26, f.X(x) + (-60 if row == '1' else 60), f.Y(-sp / 2) - 2, BLUE, 2, 7)
                s.tag(f.X(x) + (-66 if row == '1' else 66), f.Y(-sp / 2) - 30, f'{sym("H_" + row + "_III")} = {val(e, "H_" + row + "_III", 2)}', BLUE, 'end' if row == '1' else 'start')
            s.moment(f.X(k) + 46, f.Y(0), 16, True, HL, f'{sym(name)} = {val(e, name, 2)} (yaw)')
    rows = {'N_minus_III': [f'{eq(e, "R_W1_III", 2)} + {eq(e, "R_W2_III", 2)}', f'+ {eq(e, "η_bearing", 2)}·{eq(e, "γ_DC_III", 2)}·{eq(e, "DC_sub", 2)}/2', ('both windward bearings plus half the below-bearing weight', GREY)],
            'N_plus_III': [f'{eq(e, "R_L1_III", 2)} + {eq(e, "R_L2_III", 2)}', f'+ {eq(e, "η_bearing", 2)}·{eq(e, "γ_DC_III", 2)}·{eq(e, "DC_sub", 2)}/2', ('both leeward bearings plus half the below-bearing weight', GREY)],
            'M_L_res_III': [f'{eq(e, "H_P_III", 2)} × {eq(e, "z_b", 3, "ft")}', ('shear at the bearing plane carried down to the cap reference', GREY)],
            'M_T_res_III': [f'k × ((D₁ − U₁) − (D₂ − U₂))', f'= {n(k, 3)} ft × ({n(v("D_1_III", "kip") - v("U_1_III", "kip"), 2)} − {n(v("D_2_III", "kip") - v("U_2_III", "kip"), 2)}) kip', ('zero when the two rows carry equal net load', GREY)],
            'M_V_res_III': [f'k × ({eq(e, "H_1_III", 2)} − {eq(e, "H_2_III", 2)})', f'k = {n(k, 3)} ft', ('unequal span wind twists the cap about the vertical axis', GREY)]}
    s.panel(eq(e, name, 2), rows.get(name, []))
    return s


# ----------------------------------------------------------------------------- balances and status
def balance(e, name):
    v = e.value
    titles = {'Chk_config': 'Supported beam and node configuration', 'Chk_tributary': 'Tributary length agrees with the source',
              'Chk_horizontal': 'Horizontal set agrees with C002', 'Chk_force': 'Vertical equilibrium of the physical bearings',
              'Chk_roll': 'Roll equilibrium of the physical bearings', 'Chk_transfer': 'Node roll plus residual equals the applied moment',
              'Check_model': 'All coherence and equilibrium checks', 'Status_transfer': 'Release condition of the pier load transfer',
              'Uplift_restraint': 'Uplift-restraint demand'}
    s = Svg(f'{name}: balance', title=titles.get(name, name))
    sp, zb = v('s', 'ft'), v('z_b', 'ft')
    lines = []
    if name == 'Chk_config':
        lines = [(f'Beam_count = {n(v("Beam_count"), 0)} (must be 2)', True), (f'BearingNodeCount = {n(v("BearingNodeCount"), 0)} = 2 × Beam_count', True),
                 (f's = {n(sp, 3)} ft > 0, b = {n(v("b", "ft"), 2)} ft ≥ s', True), (f'l₁ = {n(v("l_1", "ft"), 2)} ft, l₂ = {n(v("l_2", "ft"), 2)} ft > 0', True),
                 (f'h_c = {n(v("h_c", "ft"), 3)} ft, h_f = {n(v("h_f", "ft"), 3)} ft > 0', True)]
    elif name == 'Chk_tributary':
        lines = [(f'l_P = {n(v("l_P", "ft"), 3)} ft (this module)', True), (f'Pier_tributaryLength = {n(v("Pier_tributaryLength", "ft"), 3)} ft (Bridge Geometry)', True)]
    elif name == 'Chk_horizontal':
        lines = [(f'w_H·l_P = {n(v("w_H_III", "kip/ft") * v("l_P", "ft"), 3)} kip', True), (f'η·γ_WS·F_cap_T (C002) = {n(v("η_bearing") * v("γ_WS_III") * v("F_cap_T_III", "kip"), 3)} kip', True),
                 (f'(m_H + w_H·z_b)·l_P = {n((v("m_H_III", "kip") + v("w_H_III", "kip/ft") * zb) * v("l_P", "ft"), 2)} kip-ft', True),
                 (f'η·γ_WS·M_cap_L (C002) = {n(v("η_bearing") * v("γ_WS_III") * v("M_cap_L_III", "kip*ft"), 2)} kip-ft', True)]
    elif name == 'Chk_force':
        for row in ('1', '2'):
            lines += [(f'row {row}: R_W + R_L = {n(v("R_W" + row + "_III", "kip") + v("R_L" + row + "_III", "kip"), 3)} kip', True),
                      (f'row {row}: D − U = {n(v("D_" + row + "_III", "kip") - v("U_" + row + "_III", "kip"), 3)} kip', True)]
    elif name == 'Chk_roll':
        for row in ('1', '2'):
            lines += [(f'row {row}: (R_L − R_W)·s/2 = {n((v("R_L" + row + "_III", "kip") - v("R_W" + row + "_III", "kip")) * sp / 2, 3)} kip-ft', True),
                      (f'row {row}: m_OT·l = {n(v("m_OT_III", "kip") * v("l_" + row, "ft"), 3)} kip-ft', True)]
    elif name == 'Chk_transfer':
        lines = [(f'(N₊ − N₋)·s/2 = {n((v("N_plus_III", "kip") - v("N_minus_III", "kip")) * sp / 2, 3)} kip-ft', True),
                 (f'+ M_L,res = {n(v("M_L_res_III", "kip*ft"), 3)} kip-ft', True), (f'M_L,total = {n(v("M_L_total_III", "kip*ft"), 3)} kip-ft', True)]
    elif name in ('Check_model', 'Status_transfer'):
        for key in ('Chk_config', 'Chk_tributary', 'Chk_gravity', 'Chk_horizontal', 'Chk_force', 'Chk_roll', 'Chk_transfer', 'Chk_datum'):
            lines.append((f'{key}: {_chk(e, key)}', 'FAIL' not in _chk(e, key)))
    elif name == 'Uplift_restraint':
        lines = [(f'Chk_contact: {_chk(e, "Chk_contact_III")}', 'FAIL' not in _chk(e, 'Chk_contact_III')), (f'R_min = {n(v("R_min_III", "kip"), 2)} kip', True),
                 (f'T_req = {n(v("T_req_III", "kip"), 2)} kip', True)]
    y = 56
    for text, ok in lines:
        s.circle(26, y - 4, 4, fill=TEAL if ok else HL)
        s.text(38, y, escape(text), 10, INK, 'start')
        y += 20
    s.text(20, y + 10, 'tolerance 1e-6 on every balance' if name.startswith('Chk') and name not in ('Chk_config',) else '', 9, GREY, 'start')
    result = _chk(e, name)
    s.panel(f'{sym(name)}', [(escape(result[:60]), HL if 'FAIL' in result or 'LOSS' in result else TEAL)])
    s.status(PX, 130, result)
    return s


drawer = make_drawer({**{k: section for k in SECTION_TITLES}, 'l_P': plan, 'R_min_III': plan, 'T_req_III': plan, 'Chk_contact_III': plan,
                      'H_P_III': plan, 'M_L_total_III': plan, 'ΔN_minus_III': plan, 'ΔN_plus_III': plan,
                      'N_minus_III': nodes, 'N_plus_III': nodes, 'M_L_res_III': nodes, 'M_T_res_III': nodes, 'M_V_res_III': nodes,
                      'Chk_config': balance, 'Chk_tributary': balance, 'Chk_horizontal': balance, 'Chk_force': balance, 'Chk_roll': balance,
                      'Chk_transfer': balance, 'Check_model': balance, 'Status_transfer': balance, 'Uplift_restraint': balance},
                     [(r'^(R_W|R_L|H_|U_|D_|H_pad)\d_III$', plan)])
