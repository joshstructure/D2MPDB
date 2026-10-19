"""Distilled Mathcad 15 worksheet of one pile design (End Bent 1, End Bent 2, Pier).

`build(e)` writes the worksheet XML of an Evaluation of the pile notebook model; scripts/build_pile_mathcad.py is a thin
command line around it and the notebook export button calls it too. The sheet is written from the compact equation list
of scripts/mathcad_sheet.py. Every expression is parsed once and used two ways: emitted as Mathcad worksheet XML and
evaluated here with unit checking, so `verify` can compare each result with the notebook (to 1e-9) before the file is
written. The interaction sweep of the prestressed pile is a set of range-indexed vectors (strain matrix, power-formula
stress, block geometry, Pn, Mn, phi, Pr, Mr) so Mathcad recomputes the curve; the figure of it is a picture.

    python scripts/build_pile_mathcad.py                   # write pile_mathcad/*.xmcd
    python scripts/build_pile_mathcad.py --render-figures  # redraw the PNGs first (matplotlib)
"""
import contextlib
import hashlib
import io
import math
import re
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from . import loads, sections
from .model import INPUT_SPEC, PI_DISC, PI_64

ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / 'pile_design' / 'mathcad'
TOL = 1e-9
HOW = 'run python scripts/build_pile_mathcad.py after changing the pile_design package, the registered FBMP export or the generator'
DC_TITLE = 'D/C by check (Blue = within 1.0, Red = over 1.0)'
DC_CAPTION = ('Figure {n}. Demand/capacity ratio of each distilled check (stems) against the limit (dashed line). It is a '
              'Mathcad plot of CheckGood and CheckNoGood, so it recalculates with the worksheet and a check turns red '
              'when its ratio passes 1.0.')
NOTEBOOK = 'Pile_Design.ipynb'


def _sheet():
    """The shared writer (scripts/mathcad_sheet.py); imported on first use so that `import pile_design` stays light."""
    if str(ROOT) not in sys.path:             # the checkout (or the extracted notebook package) holds scripts/
        sys.path.insert(0, str(ROOT))
    from scripts import mathcad_sheet
    return mathcad_sheet


def _dsl():
    ms = _sheet()
    return SimpleNamespace(**{n: getattr(ms, n) for n in (
        'BUL', 'D', 'E', 'EQ', 'FIG', 'H1', 'H2', 'I', 'INPUTS', 'N', 'P', 'R', 'ROW', 'S', 'V', 'Block', 'Item', 'U', 'UnitError',
        '_to', 'check_names', 'check_order', 'document', 'ev', 'layout', 'parse', 'run')})


def support_slug(support):
    return re.sub(r'[^a-z0-9]+', '_', support.lower()).strip('_')


# ----------------------------------------------------------------------------- small helpers
def num(v):
    """A number as the worksheet writes it: plain decimal, never exponent form."""
    v = float(v)
    if not math.isfinite(v):
        raise ValueError(f'{v!r} cannot be written to a worksheet')
    text = repr(v)
    if 'e' in text or 'E' in text:
        text = format(Decimal(text), 'f')
        if '.' not in text:
            text += '.0'
    return text


def _u(unit):
    return None if unit in (None, 'bar') else unit.replace('^', '**')


def with_unit(value, unit):
    unit = _u(unit)
    return num(value) + (f'*({unit})' if unit else '')


def vec(values, unit=None):
    text = 'tr(row(' + ', '.join(num(v) for v in values) + '))'
    return text + (f'*({_u(unit)})' if _u(unit) else '')


def strs(values):
    return 'tr(row(' + ', '.join('"' + str(v).replace('"', "'") + '"' for v in values) + '))'


@contextlib.contextmanager
def result_widths(widths):
    """Row-display widths of this module's vectors, in force only while its worksheet is laid out."""
    ms = _sheet()
    saved = dict(ms.RESULT_WIDTHS)
    ms.RESULT_WIDTHS.update(widths)
    try:
        yield
    finally:
        ms.RESULT_WIDTHS.clear()
        ms.RESULT_WIDTHS.update(saved)


def package_revision():
    """SHA-256 of the pile_design package (sources and data, newline-normalised), as embedded in the notebook."""
    base = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for path in sorted(list(base.glob('*.py')) + list((base / 'data').glob('*.json'))):
        h.update(path.relative_to(base).as_posix().encode())
        h.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return h.hexdigest()


def chain(base, ix, terms, group=4):
    """Hidden running-sum vectors over index `ix` (the DSL has no sum): returns (items, name of the last vector)."""
    d = _dsl()
    items, prev = [], None
    for g0 in range(0, len(terms), group):
        name = f'{base}{g0 // group + 1}'
        part = ' + '.join(terms[g0:g0 + group])
        items.append(d.V(name, ix, (f'{prev}[{ix}] + ' if prev else '') + part, show=False))
        prev = name
    return items, prev


def scalar_chain(base, terms, final, unit=None, caption='', group=4, key=False):
    """Running sum of scalar terms ending in the shown definition `final`."""
    d = _dsl()
    items, prev = [], None
    pieces = [terms[g0:g0 + group] for g0 in range(0, len(terms), group)]
    for n, part in enumerate(pieces):
        expr = (f'{prev} + ' if prev else '') + ' + '.join(part)
        if n == len(pieces) - 1:
            items.append(d.E(final, expr, unit, caption, key=key))
        else:
            prev = f'{base}{n + 1}'
            items.append(d.D(prev, expr))
    return items


# ----------------------------------------------------------------------------- the demand records
PSC_RECORDS = [('psc_axial', 'Axial'), ('psc_flex_bi', '5.6.4.5'), ('psc_flex_res', 'Resultant'), ('psc_shear', 'Shear'),
               ('psc_svc_comp', 'Svc comp.'), ('psc_svc_tens', 'Svc tens.')]
PIPE_RECORDS = [('pipe_axial', 'Axial'), ('pipe_comb', 'Combined'), ('pipe_shear', 'Shear')]


def demand_records(e):
    """(key, short label, record) of the governing records the worksheet reproduces, in table order."""
    spec = PSC_RECORDS if e.family == 'psc' else PIPE_RECORDS
    out = []
    for key, short in spec:
        rec = e.governing.get(key)
        if rec is None:
            raise ValueError('The Mathcad worksheet needs FBMP results: load the pile XML first '
                             f'(no governing record for {key}).')
        out.append((key, short, rec))
    tension = e.governing.get(f'{e.family}_tension')
    if tension is not None:
        out.append((f'{e.family}_tension', 'Tension', tension))
    return out


def context(e, rev, figs=None):
    if e.case.get('analysis') is None:
        raise ValueError('The Mathcad worksheet needs FBMP results: load the pile XML first.')
    recs = demand_records(e)
    n_str = int(e.details['option']['count']) if e.family == 'psc' else 0
    return SimpleNamespace(e=e, p=e.case['inputs'], rev=rev, key=support_slug(e.case['support']), figs=figs, recs=recs,
                           idx={key: i for i, (key, _, _) in enumerate(recs)}, n_str=n_str)


# ----------------------------------------------------------------------------- inputs
def input_blocks(ctx):
    d = _dsl()
    e, fam = ctx.e, ctx.e.family
    groups = {}
    for spec in INPUT_SPEC:
        if spec['family'] not in (fam, 'both'):
            continue
        value = ctx.p.get(spec['name'])
        if value is None:
            continue
        caption = spec['caption'] + (' [pending confirmation]' if spec['status'] == 'pending confirmation' else '')
        groups.setdefault(spec['group'], []).append(d.I(spec['name'], with_unit(value, spec['unit']), caption))
    blocks = [d.INPUTS(title, items) for title, items in groups.items()]
    if fam == 'psc':
        plan, option = e.details['plan'], e.details['option']
        items = [d.I('N_str', num(option['count']), f'strands in pattern {option["id"]}'),
                 d.I('A_str', with_unit(option['strand_area_in2'], 'in^2'), 'strand nominal area'),
                 d.I('P_jack', with_unit(option['jacking_kip'], 'kip'), 'jacking force per strand, Standard Plans'),
                 d.I('d_void', with_unit(e.value('d_void', 'in'), 'in'), 'void diameter (Index 455-030 only)'),
                 d.I('R_drive_tons', num(e.value('R_drive_tons')), 'maximum driving resistance, SDG Table 3.5.13-1, tons'),
                 d.I('M_splice', with_unit(e.value('M_splice', 'kip*ft'), 'kip*ft'), 'Spec Table 455-2 splice bending strength (INFO)')]
        blocks.append(d.INPUTS(f'Standard Plans Index {ctx.e.case["psc"]["index"]}, strand pattern {ctx.e.case["psc"]["pattern"]}', items))
    return blocks


# ----------------------------------------------------------------------------- demands
def demand_blocks(ctx, number):
    d = _dsl()
    e, recs = ctx.e, ctx.recs
    n = len(recs)
    lines = []
    for key, short, rec in recs:
        ties = f' (+{len(rec["ties"]) - 1} tied)' if len(rec['ties']) > 1 else ''
        lines.append(f'{short}: {loads.record_id(rec)}{ties}.')
    gam = [('gamma_DR_str' if rec['limit'] == 'strength' else 'gamma_DR_ser') for _, _, rec in recs]
    blocks = [
        d.H1(f'{number}. Demands from the FBMP export'),
        d.P(f'Governing records of {e.case["analysis"]["filename"]} for each check (index g). FBMP axial force is converted to '
            'compression positive. The drag load DR = DD is added to the axial force at every station (LRFD Table 3.4.1-1, '
            '10.7.3.7): gamma_DR for the limit state of the record. Downdrag is not in the Factored Design Load.'),
        d.BUL(lines),
        d.ROW(d.R('r', 0, n - 1), d.D('Rec', strs([short for _, short, _ in recs]))),
        d.EQ(d.I('P_fbmp', vec([r['P_fbmp'] for _, _, r in recs], 'kip'), 'FBMP axial force at the record, compression positive'),
             d.I('M_2', vec([r['M2'] for _, _, r in recs], 'kip*ft'), 'FBMP moment M2, signed'),
             d.I('M_3', vec([r['M3'] for _, _, r in recs], 'kip*ft'), 'FBMP moment M3, signed'),
             d.I('M_res', vec([r['M_res'] for _, _, r in recs], 'kip*ft'), 'resultant moment of the record'),
             d.I('V_res', vec([r['V_res'] for _, _, r in recs], 'kip'), 'resultant shear of the record'),
             d.I('FDL_fbmp', with_unit(e.value('FDL_fbmp', 'kip'), 'kip'), 'Factored Design Load: maximum strength head compression, FBMP (no downdrag)'),
             d.I('T_u', with_unit(e.value('T_u', 'kip'), 'kip'), 'maximum strength uplift anywhere along the pile, FBMP')),
        d.EQ(d.E('DD', 'DD_tons*2*kip', 'kip', 'downdrag (drag load DR) per pile, nominal'),
             d.E('DR_str', 'gamma_DR_str*DD', 'kip', 'drag load, strength limit states'),
             d.E('DR_ser', 'gamma_DR_ser*DD', 'kip', 'drag load, Service I'),
             d.D('gamma_g', 'tr(row(' + ', '.join(gam) + '))', 'drag-load factor of each record'),
             d.V('P_u', 'r', 'P_fbmp[r] + gamma_g[r]*DD', 'kip', 'factored axial load incl. drag load', show=False)),
        d.N('Columns, left to right: record; FBMP axial force; P_u incl. drag load; resultant moment; resultant shear.'),
        d.ROW(d.S('Rec', None, '', rows=n, width=86), d.S('P_fbmp', 'kip', rows=n, width=62), d.S('P_u', 'kip', rows=n, width=62),
              d.S('M_res', 'kip*ft', rows=n, width=62), d.S('V_res', 'kip', rows=n, width=62)),
    ]
    return blocks


# ----------------------------------------------------------------------------- common (geometry, geotechnical)
def common_geometry(ctx):
    d = _dsl()
    return [d.EQ(d.E('S_min', '3*D_pile', 'in', 'minimum center-to-center spacing, 3.0 diameters (SDG 3.5.4)'),
                 d.E('s_over_D', 'S_pile/D_pile', None, 'provided spacing in pile diameters'),
                 d.E('DC_sp', 'S_min/S_pile', None, 'spacing D/C'))]


def geotech_blocks(ctx, number):
    d, fam = _dsl(), ctx.e.family
    items = [d.E('FDL_tons', 'FDL_fbmp/(2*kip)', None, 'Factored Design Load, tons (strength head compression, without downdrag)'),
             d.E('R_scour_net', 'R_scour_net_tons*2*kip', 'kip', 'net scour resistance'),
             d.E('R_n_req', '(FDL_fbmp + R_scour_net + DD)/phi_geo', 'kip', 'required nominal bearing resistance, SDG Eq. 3-1'),
             d.E('NBR_tons', 'R_n_req/(2*kip)', None, 'required nominal bearing resistance, tons (Pile Data Table column C)', key=True)]
    if fam == 'psc':
        items += [d.E('R_drive_max', 'R_drive_tons*2*kip', 'kip', 'maximum pile driving resistance, SDG Table 3.5.13-1'),
                  d.E('DC_nbr', 'NBR_tons/R_drive_tons', None, 'bearing resistance D/C against Table 3.5.13-1')]
    return [d.H1(f'{number}. Geotechnical resistance (SDG 3.5.13)'),
            d.P('SDG Eq. 3-1: Rn >= (Factored Design Load + Net Scour Resistance + Downdrag) / phi. The downdrag enters nominally; the '
                'minimum tip elevation, scour and test-pile length of the Pile Data Table come from the geotechnical handoff.'),
            d.EQ(*items)]


# ----------------------------------------------------------------------------- prestressed pile
def psc_section_blocks(ctx, number):
    d = _dsl()
    return [
        d.H1(f'{number}. Section and prestress'),
        d.FIG(f'{ctx.key}_section', 'Figure 1. Pile cross-section: strand pattern of the Standard Plans option and the bending axes of the '
                                    'governing resultant and shear records.', width=330, data=ctx.figs['section'] if ctx.figs else None),
        d.EQ(d.E('A_ps', 'N_str*A_str', 'in**2', 'prestressing steel area'),
             d.E('f_pj', 'P_jack/A_str', 'ksi', 'jacking stress per strand'),
             d.E('f_pe', 'f_pj*(1 - loss_frac)', 'ksi', 'effective prestress after losses'),
             d.E('P_e', 'A_ps*f_pe', 'kip', 'effective prestress force'),
             d.E('A_g', f'D_pile**2 - {PI_DISC}*d_void**2', 'in**2', 'gross area (chamfers ignored)'),
             d.E('I_g', f'D_pile**4/12 - {PI_64}*d_void**4', 'in**4', 'gross moment of inertia'),
             d.E('S_g', 'I_g/(D_pile/2)', 'in**3', 'section modulus'),
             d.E('f_pc_eff', 'P_e/A_g', 'ksi', 'effective uniform prestress on the gross area'),
             d.E('beta_1', 'min(0.85, max(0.65, 0.85 - 0.05*(fc - 4*ksi)/ksi))', None, 'stress block factor, 5.6.2.2'),
             d.E('E_c', '120000*K_1*(w_c/(kip/ft**3))**2*(fc/ksi)**0.33*ksi', 'ksi', 'concrete modulus, 5.4.2.4-1'),
             d.E('eps_cu', '0.003', None, 'concrete crushing strain'),
             d.E('k_c', 'min(0.85, max(0.75, 0.85 - 0.02*max(fc - 10*ksi, 0*ksi)/ksi))', None, "ratio of maximum concrete stress to f'c"),
             d.E('eps_pe', 'f_pe/E_p', None, 'effective prestrain'),
             d.E('eps_ce', 'f_pc_eff/E_c', None, 'concrete decompression strain')),
        d.H2('Strand coordinates (one strand at each corner, equal spacing between, concentric)'),
        d.EQ(d.E('k_row', 'N_str/4 + 1', None, 'strands on each face'),
             d.E('p_st', '(D_pile - 2*d_edge)/(k_row - 1)', 'in', 'strand pitch'),
             d.E('h_st', 'D_pile/2 - d_edge', 'in', 'strand distance from the centroid, each face')),
        d.ROW(d.R('n', 0, 'N_str - 1')),
        d.EQ(d.V('b_st', 'n', 'IF(n < k_row, 0, IF(n < 2*k_row, k_row, IF(n < 3*k_row - 2, 2*k_row - 1, 3*k_row - 3)))', None,
                 'first strand index of the face the strand is on', show=False),
             d.V('j_st', 'n', 'n - b_st[n]', None, 'position along the face', show=False),
             d.V('x_st', 'n', 'IF(n < 2*k_row, -h_st + j_st[n]*p_st, IF(n < 3*k_row - 2, -h_st, h_st))', 'in', 'strand x', show=False),
             d.V('y_st', 'n', 'IF(n < k_row, -h_st, IF(n < 2*k_row, h_st, -h_st + j_st[n]*p_st))', 'in', 'strand y', show=False)),
        d.N('The strand coordinates x_st, y_st (index s) are vectors; they are not displayed here. Figure 1 draws them.'),
    ]


def psc_axial_blocks(ctx, number):
    d = _dsl()
    return [
        d.H1(f'{number}. Axial resistance (LRFD 5.6.4.4, 5.5.4.2)'),
        d.EQ(d.E('P_u_axial', f'P_u[{ctx.idx["psc_axial"]}]', 'kip', 'largest factored compression incl. drag load'),
             d.E('P_o', 'k_c*fc*(A_g - A_ps) - A_ps*(f_pe - E_p*eps_cu)', 'kip', 'axial resistance at zero eccentricity, 5.6.4.4-2', key=True),
             d.E('P_n_max', '0.85*P_o', 'kip', 'maximum nominal axial resistance (spiral)'),
             d.E('P_r_max', 'phi_c*P_n_max', 'kip', 'maximum factored axial resistance', key=True),
             d.E('phi_Po', 'phi_c*P_o', 'kip', 'phi Po, used in Eq. 5.6.4.5-1'),
             d.E('P_bi_lim', '0.10*phi_c*fc*A_g', 'kip', 'axial load limit between Eqs. 5.6.4.5-1 and -3'),
             d.E('P_t_yield', 'A_ps*f_py', 'kip', 'strand yield limit Aps fpy (upper bound of tension, 5.6.6.1)'),
             d.E('DC_axial', 'P_u_axial/P_r_max', None, 'axial compression D/C, largest Pu / phi Pn,max')),
    ]


def geometry_items(geo, theta):
    """Bending-axis geometry of the section about an axis at angle `theta` (an expression)."""
    d = _dsl()
    t = f'_{geo}'
    return [
        d.EQ(d.E(f'sn{t}', f'sin({theta})', None, 'sin of the bending-axis angle'),
             d.E(f'cs{t}', f'sin({theta} + 90*deg)', None, 'cos of the bending-axis angle'),
             d.E(f'H{t}', f'D_pile*(sn{t} + cs{t})', 'in', 'depth of the section normal to the bending axis'),
             d.E(f's_max{t}', f'H{t}/2', 'in', 'centroid to the extreme compression fiber'),
             d.E(f't1{t}', f'D_pile*sn{t}', 'in', 'depth at which the compressed width stops growing'),
             d.E(f't2{t}', f'D_pile*cs{t}', 'in', 'depth at which the compressed width starts to shrink'),
             d.E(f'q{t}', f'sn{t}*cs{t}', None, 'sin x cos of the angle'),
             d.V(f's_st{t}', 'n', f'-sn{t}*x_st[n] + cs{t}*y_st[n]', 'in', 'strand coordinate toward the compression face', show=False),
             d.V(f'd_st{t}', 'n', f's_max{t} - s_st{t}[n]', 'in', 'strand depth from the extreme compression fiber', show=False),
             d.E(f'd_t{t}', f'max(d_st{t})', 'in', 'depth of the extreme tension strand')),
    ]


def sweep_items(ctx, tag, geo, ix, general, c_items):
    """Vectors of the interaction sweep over `ix` (strain compatibility, LRFD C5.6.2.1): block, strains, forces, phi, Pr, Mr."""
    d = _dsl()
    t, g = f'_{tag}', f'_{geo}'
    a = f'a{t}[{ix}]'
    items = list(c_items)
    items.append(d.V(f'a{t}', ix, f'min(beta_1*c{t}[{ix}], H{g})', 'in', 'compression block depth a = beta1 c, not beyond the section', show=False))
    if general:
        items += [
            d.V(f'A_b{t}', ix, f'(min({a}, t1{g})**2 + 2*t1{g}*max({a} - t1{g}, 0*in) - max({a} - t2{g}, 0*in)**2)/(2*q{g})', 'in**2',
                'compressed area', show=False),
            d.V(f'J_p{t}', ix, f'min({a}, t1{g})**3/3 + t1{g}*(max({a}, t1{g})**2 - t1{g}**2)/2', 'in**3', 'first moment, rising width', show=False),
            d.V(f'J_q{t}', ix, f'(max({a}, t2{g})**3 - t2{g}**3)/3 - t2{g}*(max({a}, t2{g})**2 - t2{g}**2)/2', 'in**3',
                'first moment, falling width', show=False),
            d.V(f'J_b{t}', ix, f'(J_p{t}[{ix}] - J_q{t}[{ix}])/q{g}', 'in**3', 'integral of depth times width over the block', show=False)]
    else:
        items += [d.V(f'A_b{t}', ix, f'D_pile*{a}', 'in**2', 'compressed area', show=False),
                  d.V(f'J_b{t}', ix, f'D_pile*{a}**2/2', 'in**3', 'integral of depth times width over the block', show=False)]
    e_ = f'eps_p{t}[{ix}, n]'
    items += [
        d.V(f'eps_p{t}', (ix, 'n'), f'eps_pe + eps_ce + eps_cu*(d_st{g}[n] - c{t}[{ix}])/c{t}[{ix}]', None, 'strand strain', show=False),
        d.V(f'g_p{t}', (ix, 'n'), f'0.025 + 0.975/(1 + (118*{e_})**10)**0.1', None, 'power-formula factor', show=False),
        d.V(f'f_p{t}', (ix, 'n'), f'IF({e_} > 0, min(E_p*{e_}*g_p{t}[{ix}, n], f_pu), E_p*{e_})', 'ksi',
            'strand stress, PCI power formula (tension) or Ep eps (compression)', show=False)]
    n_str = ctx.n_str
    chain_f, last_f = chain(f'S_f{t}', ix, [f'f_p{t}[{ix}, {s}]' for s in range(n_str)])
    chain_m, last_m = chain(f'S_m{t}', ix, [f'f_p{t}[{ix}, {s}]*s_st{g}[{s}]' for s in range(n_str)])
    items += chain_f + chain_m
    items += [
        d.V(f'F_ps{t}', ix, f'A_str*{last_f}[{ix}]', 'kip', 'strand force, tension positive', show=False),
        d.V(f'M_ps{t}', ix, f'A_str*{last_m}[{ix}]', 'kip*ft', 'moment of the strand forces about the centroid', show=False),
        d.V(f'P_n{t}', ix, f'min(max(0.85*fc*A_b{t}[{ix}] - F_ps{t}[{ix}], -P_t_yield), P_n_max)', 'kip', 'nominal axial resistance', show=False),
        d.V(f'M_n{t}', ix, f'0.85*fc*(s_max{g}*A_b{t}[{ix}] - J_b{t}[{ix}]) - M_ps{t}[{ix}]', 'kip*ft', 'nominal moment', show=False),
        d.V(f'eps_t{t}', ix, f'eps_cu*(d_t{g} - c{t}[{ix}])/c{t}[{ix}]', None, 'net tensile strain', show=False),
        d.V(f'phi{t}', ix, f'min(max(phi_c + (phi_t - phi_c)*(eps_t{t}[{ix}] - 0.002)/0.003, phi_c), phi_t)', None, 'resistance factor, 5.5.4.2', show=False),
        d.V(f'P_r{t}', ix, f'phi{t}[{ix}]*P_n{t}[{ix}]', 'kip', 'factored axial resistance', show=False),
        d.V(f'M_r{t}', ix, f'phi{t}[{ix}]*M_n{t}[{ix}]', 'kip*ft', 'factored moment resistance', show=False)]
    return items


def ext_items(tag):
    """Sweep with the pure-compression and pure-tension points added, and its segments."""
    d = _dsl()
    t = f'_{tag}'
    return [
        d.EQ(d.D(f'P_ext{t}', f'stack(col(P_r_pc), P_r{t}, col(P_r_pt))', 'sweep with its end points'),
             d.D(f'M_ext{t}', f'stack(col(0*kip*ft), M_r{t}, col(0*kip*ft))', 'sweep with its end points'),
             d.V(f'dP{t}', 'q', f'P_ext{t}[q + 1] - P_ext{t}[q]', 'kip', 'segment axial step', show=False),
             d.V(f'dM{t}', 'q', f'M_ext{t}[q + 1] - M_ext{t}[q]', 'kip*ft', 'segment moment step', show=False),
             d.V(f'P_lo{t}', 'q', f'min(P_ext{t}[q], P_ext{t}[q + 1])', 'kip', 'segment axial low', show=False),
             d.V(f'P_hi{t}', 'q', f'max(P_ext{t}[q], P_ext{t}[q + 1])', 'kip', 'segment axial high', show=False))]


def moment_at_items(tag, key, p_expr, out, caption):
    """Mr at the axial load p_expr: the largest interpolated Mr over the segments that span it (sections.moment_capacity_at_axial)."""
    d = _dsl()
    t = f'_{tag}'
    return [d.EQ(
        d.D(f'P_ref_{key}', p_expr),
        d.V(f'M_i_{key}', 'q', f'IF(dP{t}[q] == 0*kip, max(0*kip*ft, dM{t}[q]), (P_ref_{key} - P_ext{t}[q])/dP{t}[q]*dM{t}[q])', 'kip*ft',
            'moment gained along the segment', show=False),
        d.V(f'w_{key}', 'q', f'IF(P_ref_{key} >= P_lo{t}[q] - 10**-12*kip and P_ref_{key} <= P_hi{t}[q] + 10**-12*kip, 1, 0)', None,
            'segment spans that axial load (1)', show=False),
        d.V(f'M_s_{key}', 'q', f'w_{key}[q]*(M_ext{t}[q] + M_i_{key}[q])', 'kip*ft', 'Mr on the segment at that axial load', show=False),
        d.E(out, f'max(M_s_{key})', 'kip*ft', caption))]


def ray_items(tag, key, p_expr, m_expr, out_p, out_m, caption):
    """Point of the phi-curve on the ray through the demand (sections.ray_capacity)."""
    d = _dsl()
    t = f'_{tag}'
    items = [
        d.V(f'g_{key}', 'u', f'M_ext{t}[u]*({p_expr}) - P_ext{t}[u]*({m_expr})', None, 'moment shortfall of each curve point against the ray', show=False),
        d.V(f'k_{key}u', 'u', f'IF(g_{key}[u] >= 0*kip*kip*ft, u, n_sweep + 1)', None, 'curve point beyond the ray', show=False),
        d.E(f'k_{key}', f'min(k_{key}u)', None, f'first curve point beyond the ray ({caption})'),
        d.E(f'kk_{key}', f'max(k_{key}, 1)', None, 'upper end of the interpolated segment'),
        d.E(f'gh_{key}', f'g_{key}[kk_{key}]', None, 'shortfall, upper end'),
        d.E(f'gl_{key}', f'g_{key}[kk_{key} - 1]', None, 'shortfall, lower end'),
        d.E(f't_{key}', f'IF(gh_{key} == gl_{key}, 0, -gl_{key}/(gh_{key} - gl_{key}))', None, 'interpolation fraction'),
        d.D(f'Pl_{key}', f'P_ext{t}[kk_{key} - 1]'), d.D(f'Ph_{key}', f'P_ext{t}[kk_{key}]'),
        d.E(out_p, f'IF(k_{key} == 0, P_ext{t}[0], Pl_{key} + t_{key}*(Ph_{key} - Pl_{key}))', 'kip',
            'axial resistance where the ray meets the curve')]
    if out_m:
        items.insert(-1, d.D(f'Ml_{key}', f'M_ext{t}[kk_{key} - 1]'))
        items.insert(-1, d.D(f'Mh_{key}', f'M_ext{t}[kk_{key}]'))
        items.append(d.E(out_m, f'IF(k_{key} == 0, M_ext{t}[0], Ml_{key} + t_{key}*(Mh_{key} - Ml_{key}))', 'kip*ft',
                         'moment resistance where the ray meets the curve'))
    return [d.EQ(*items)]


def sample_table(ctx, tag, number_title):
    """A short table of the sweep (every step-th point)."""
    d = _dsl()
    t = f'_{tag}'
    n = int(ctx.p['n_sweep'])
    step = max(1, (n - 1) // 8)
    last = (n - 1) // step
    return [
        d.H2(number_title),
        d.ROW(d.R('p', 0, last)),
        d.EQ(d.V('c_tab', 'p', f'c{t}[{step}*p]', 'in', 'neutral-axis depth', show=False),
             d.V('eps_tab', 'p', f'eps_t{t}[{step}*p]', None, 'net tensile strain', show=False),
             d.V('phi_tab', 'p', f'phi{t}[{step}*p]', None, 'resistance factor', show=False),
             d.V('Pr_tab', 'p', f'P_r{t}[{step}*p]', 'kip', 'factored axial resistance', show=False),
             d.V('Mr_tab', 'p', f'M_r{t}[{step}*p]', 'kip*ft', 'factored moment resistance', show=False)),
        d.N(f'Columns, left to right: c; net tensile strain; phi; Pr; Mr (every {step}th of the {n} sweep points).'),
        d.ROW(d.S('c_tab', 'in', rows=last + 1, width=62), d.S('eps_tab', None, rows=last + 1, width=62), d.S('phi_tab', None, rows=last + 1, width=62),
              d.S('Pr_tab', 'kip', rows=last + 1, width=62), d.S('Mr_tab', 'kip*ft', rows=last + 1, width=62)),
    ]


def bending_axis_of(rec):
    """Bending-axis angle of the resultant moment folded into 0..45 degrees (model._Psc.angle_of)."""
    a = math.atan2(abs(rec['M3']), abs(rec['M2']))
    return min(a, math.pi / 2 - a)


def ray_bracket(curve, P, M):
    """(k, t) of sections.ray_capacity: first point beyond the ray and the interpolation fraction."""
    Pr, Mr = curve['Pr'], curve['Mr']
    g = Mr * P - Pr * abs(M)
    idx = [i for i, v in enumerate(g) if v >= 0]
    k = idx[0] if idx else len(g) - 1
    kk = max(k, 1)
    t = -g[kk - 1] / (g[kk] - g[kk - 1]) if g[kk] != g[kk - 1] else 0.0
    return k, float(t)


def gov_depth(curve, P, M):
    """Neutral-axis depth c_gov of the point where the demand ray meets the interpolated phi-curve."""
    k, t = ray_bracket(curve, P, M)
    kk = max(k, 1)
    c = curve['c'][1:-1]
    n = len(c)
    ia, ib = max(kk - 2, 0), min(kk - 1, n - 1)
    return float(c[ia] + t * (c[ib] - c[ia]))


def moment_expression(e):
    """How the notebook finds Mrx = Mry for Eq. 5.6.4.5-3: the expression in sheet names, matched against the engine."""
    bi, curve = e.details['biaxial'], e.curve
    Pu = e.value('P_u_bi', 'kip')
    M0 = sections.moment_capacity_at_axial(curve, 0.0)
    Mu = sections.moment_capacity_at_axial(curve, Pu)
    candidates = [('M_r_P0', M0), ('IF(P_u_bi < 0*kip, min(M_r_P0, M_cap_u), M_r_P0)', min(M0, Mu) if Pu < 0 else M0), ('M_cap_u', Mu)]
    target = e.value('M_rx', 'kip*ft')
    for expr, value in candidates:
        if abs(value - target) <= 1e-9 * max(1.0, abs(target)):
            return expr
    raise ValueError('pile_design/mathcad.py does not reproduce how the notebook now finds Mrx for Eq. 5.6.4.5-3; update moment_expression')


def psc_resistance_blocks(ctx, number):
    """Section 'Interaction by strain compatibility' through the resultant-axis check."""
    d = _dsl()
    e, p = ctx.e, ctx.p
    idx = ctx.idx
    branch = e.details['branch']
    rs = ctx.recs[idx['psc_flex_res']][2]
    if rs['M_res'] < 1e-6:
        raise ValueError('The Mathcad worksheet needs a resultant-axis record with a moment (the demand ray is undefined at M = 0).')
    alpha = bending_axis_of(rs)
    general = math.degrees(alpha) > 1e-9
    blocks = [
        d.H1(f'{number}. Interaction by strain compatibility (LRFD 5.6.4.5, C5.6.2.1, 5.5.4.2)'),
        d.BUL(['Strain is linear with the extreme compression fiber at eps_cu = 0.003 and a neutral-axis depth c swept geometrically from 4H '
               'to 0.02H (H = depth of the section normal to the bending axis). Strand strain = eps_pe + eps_ce + eps_cu (d - c)/c.',
               'Strand stress: PCI power formula for Grade 270 low-relaxation strand in tension, Ep eps in compression (no correction for '
               'displaced concrete). Concrete: rectangular block a = beta1 c on the compressed part of the square (chamfers ignored).',
               'Pn is held between -Aps fpy and Pn,max; phi runs from 0.75 to 1.00 as the net tensile strain goes from 0.002 to 0.005. '
               'The pure-compression and pure-tension points are scalars; the sweep vectors hold the 121 points between them.',
               'Figure 2 is a picture; the points behind it are the live vectors of this section (Mathcad recomputes them).']),
        d.ROW(d.R('i', 0, 'n_sweep - 1'), d.R('u', 0, 'n_sweep + 1'), d.R('q', 0, 'n_sweep')),
        d.H2('End points of the curve'),
        d.EQ(d.E('P_r_pc', 'phi_c*P_n_max', 'kip', 'pure compression: phi Pn,max (Mr = 0)'),
             d.E('P_n_pt', '-P_t_yield', 'kip', 'pure tension: Pn = -Aps fpy (Mr = 0)'),
             d.E('P_r_pt', '-phi_t*P_t_yield', 'kip', 'pure tension: phi Pn, phi = tension-controlled')),
        d.H2('Bending about an axis parallel to a face (angle 0)'),
        *geometry_items('x', '0*deg'),
        d.EQ(*sweep_items(ctx, 'x', 'x', 'i', False, [d.V('c_x', 'i', '4*H_x*0.005**(i/(n_sweep - 1))', 'in', 'neutral-axis depth', show=False)])),
        *sample_table(ctx, 'x', 'Sample of the sweep (axis parallel to a face)'),
        d.FIG(f'{ctx.key}_interaction', 'Figure 2. Interaction diagram: factored curves for bending parallel to a face and about the governing '
                                        'resultant axis, with the governing demand points. The picture is static; its points are the live vectors '
                                        'of Sections 7 to 9.', width=470, data=ctx.figs['interaction'] if ctx.figs else None),
        *ext_items('x'),
        *moment_at_items('x', '0', '0*kip', 'M_r_P0', 'factored moment resistance at zero axial load (splice comparison; Eq. 5.6.4.5-3)'),
        d.EQ(d.E('DC_splice', 'M_splice/M_r_P0', None, 'Table 455-2 splice strength / pile phi Mn (INFO)')),
    ]
    blocks += [d.H1(f'{number + 1}. Combined axial load and biaxial flexure (LRFD 5.6.4.5)'),
               d.P(f'Governing record (index 1): Pu = {e.value("P_u_bi", "kip"):.2f} kip against 0.10 phi f\'c Ag = {e.value("P_bi_lim", "kip"):.2f} kip, '
                   f'so Eq. {"5.6.4.5-1" if branch == "eq1" else "5.6.4.5-3"} applies.'),
               d.EQ(d.E('P_u_bi', f'P_u[{idx["psc_flex_bi"]}]', 'kip', 'factored axial load of the record'),
                    d.E('M_ux_bi', f'abs(M_2[{idx["psc_flex_bi"]}])', 'kip*ft', 'moment about the x axis'),
                    d.E('M_uy_bi', f'abs(M_3[{idx["psc_flex_bi"]}])', 'kip*ft', 'moment about the y axis'))]
    if branch == 'eq1':
        blocks += [d.EQ(d.E('e_y', 'M_ux_bi/P_u_bi', 'in', 'eccentricity from the moment about the x axis'),
                        d.E('e_x', 'M_uy_bi/P_u_bi', 'in', 'eccentricity from the moment about the y axis')),
                   *ray_items('x', 'ey', '1*kip', 'e_y*kip', 'P_rx', None, 'e_y'),
                   *ray_items('x', 'ex', '1*kip', 'e_x*kip', 'P_ry', None, 'e_x'),
                   d.EQ(d.E('P_rxy', '1/(1/P_rx + 1/P_ry - 1/phi_Po)', 'kip', 'factored axial resistance in biaxial flexure, Eq. 5.6.4.5-1'),
                        d.E('DC_bi', 'P_u_bi/P_rxy', None, 'D/C, Eq. 5.6.4.5-1', key=True))]
    else:
        expr = moment_expression(e)
        if 'M_cap_u' in expr:
            blocks += moment_at_items('x', 'u', 'P_u_bi', 'M_cap_u', 'factored moment resistance at the record\'s axial load')
        blocks += [d.EQ(d.E('M_rx', expr, 'kip*ft', 'uniaxial factored moment resistance about x: pure flexure (P = 0), conservative', key=True),
                        d.E('M_ry', 'M_rx', 'kip*ft', 'about y (square section)'),
                        d.E('DC_bi', 'M_ux_bi/M_rx + M_uy_bi/M_ry', None, 'D/C, Eq. 5.6.4.5-3', key=True))]
    # resultant bending axis
    blocks += [
        d.H1(f'{number + 2}. Resultant bending axis (strain compatibility at the demand angle)'),
        d.P('The demand moment is resisted about the axis of the resultant moment. The curve is swept again with the section rotated by the '
            'folded angle alpha (0 to 45 degrees, the square being symmetric); the demand ray from the origin meets the phi-curve at '
            '(Pr, Mr) and D/C = Mu / Mr along the ray. The angle is the notebook\'s; tan(alpha) = M_min / M_max proves it.'),
        d.EQ(d.E('P_u_rs', f'P_u[{idx["psc_flex_res"]}]', 'kip', 'factored axial load of the record'),
             d.E('M_u_rs', f'M_res[{idx["psc_flex_res"]}]', 'kip*ft', 'resultant moment of the record'),
             d.I('alpha_rs', with_unit(e.value('alpha_rs', 'deg'), 'deg'), 'bending-axis angle of the resultant moment, from the notebook (folded to 0-45 deg)'),
             d.E('tan_rs', 'tan(alpha_rs)', None, 'tan alpha'),
             d.E('r_rs', f'min(abs(M_2[{idx["psc_flex_res"]}]), abs(M_3[{idx["psc_flex_res"]}]))/max(abs(M_2[{idx["psc_flex_res"]}]), '
                         f'abs(M_3[{idx["psc_flex_res"]}]))', None, 'M_min / M_max of the record (equals tan alpha)')),
        *geometry_items('r', 'alpha_rs'),
        d.EQ(*sweep_items(ctx, 'r', 'r', 'i', general, [d.V('c_r', 'i', '4*H_r*0.005**(i/(n_sweep - 1))', 'in', 'neutral-axis depth', show=False)])),
        *ext_items('r'),
        *ray_items('r', 'rs', 'P_u_rs', 'M_u_rs', 'P_r_rs', 'M_r_rs', 'resultant axis'),
        d.EQ(d.E('lam_rs', '(P_u_rs*P_r_rs/kip**2 + M_u_rs*M_r_rs/(kip*ft)**2)/((P_u_rs/kip)**2 + (M_u_rs/(kip*ft))**2)', None,
                 'projection of the capacity point on the ray'),
             d.E('DC_ray', '1/lam_rs', None, '|demand| / |capacity| along the ray'),
             d.E('DC_rs', 'IF(M_u_rs > 0.001*kip*ft, M_u_rs/M_r_rs, P_u_rs/P_r_rs)', None, 'D/C, resultant bending axis', key=True)),
    ]
    # check at the notebook's solved neutral-axis depth
    curve_r = e.curve['resultant']
    c_gov = gov_depth(curve_r, rs['P_u'], rs['M_res'])
    blocks += [
        d.H2('Check at the notebook\'s solved neutral-axis depth'),
        d.P('The ray meets the sweep between two neighbouring points; the neutral-axis depth there is interpolated. The worksheet takes the '
            'notebook\'s depth c_gov as an input, finds the same depth from its own vectors, and evaluates the section exactly at c_gov '
            '(no interpolation between sweep points).'),
        d.EQ(d.I('c_gov', with_unit(c_gov, 'in'), 'neutral-axis depth where the demand ray meets the resultant-axis curve, from the notebook'),
             d.E('c_live', 'c_r[max(kk_rs - 2, 0)] + t_rs*(c_r[min(kk_rs - 1, n_sweep - 1)] - c_r[max(kk_rs - 2, 0)])', 'in',
                 'the same depth from the worksheet\'s own vectors')),
        d.ROW(d.R('v', 0, 0)),
        d.EQ(*sweep_items(ctx, 'p', 'r', 'v', general, [d.V('c_p', 'v', 'c_gov', 'in', 'neutral-axis depth', show=False)])),
        d.EQ(d.E('P_n_cg', 'P_n_p[0]', 'kip', 'Pn at c_gov'), d.E('M_n_cg', 'M_n_p[0]', 'kip*ft', 'Mn at c_gov'),
             d.E('eps_t_cg', 'eps_t_p[0]', None, 'net tensile strain at c_gov'), d.E('phi_cg', 'phi_p[0]', None, 'phi at c_gov'),
             d.E('P_r_cg', 'P_r_p[0]', 'kip', 'Pr at c_gov', key=True), d.E('M_r_cg', 'M_r_p[0]', 'kip*ft', 'Mr at c_gov', key=True),
             d.E('lam_cg', '(P_u_rs*P_r_cg/kip**2 + M_u_rs*M_r_cg/(kip*ft)**2)/((P_u_rs/kip)**2 + (M_u_rs/(kip*ft))**2)', None,
                 'projection of the point on the ray'),
             d.E('DC_cg', '1/lam_cg', None, 'D/C at c_gov (no interpolation between sweep points)')),
    ]
    return blocks, c_gov


def psc_tension_shear_service(ctx, number):
    d = _dsl()
    e, idx = ctx.e, ctx.idx
    sh = ctx.recs[idx['psc_shear']][2]
    alpha_sh = bending_axis_of(sh)
    n_str = ctx.n_str
    root_fc = 'sqrt(fc/ksi)*ksi'
    blocks = [
        d.H1(f'{number}. Tension (LRFD 5.6.6.1, 5.8.2.4.1-1)'),
        d.EQ(d.E('P_n_t', 'A_ps*min(f_py, f_pe + 60*ksi)', 'kip', 'nominal tension resistance (fy = 60 ksi, no nonprestressed steel)'),
             d.E('P_r_t', 'phi_t*P_n_t', 'kip', 'factored tension resistance', key=True),
             d.E('DC_t', 'T_u/P_r_t', None, 'tension D/C, maximum strength uplift')),
        d.H1(f'{number + 1}. Shear: general procedure (LRFD 5.7.3.3, 5.7.3.4.2)'),
        d.P(f'Governing shear record (index {idx["psc_shear"]}). Aps and de are those of the half depth on the flexural tension side '
            'of the resultant bending axis (angle alpha_sh from the notebook). Spiral legs crossing the shear plane: two.'),
        d.EQ(d.E('V_u_sh', f'V_res[{idx["psc_shear"]}]', 'kip', 'resultant shear'),
             d.E('M_u_sh', f'M_res[{idx["psc_shear"]}]', 'kip*ft', 'concurrent resultant moment'),
             d.E('P_u_sh', f'P_u[{idx["psc_shear"]}]', 'kip', 'factored axial load'),
             d.I('alpha_sh', with_unit(math.degrees(alpha_sh), 'deg'), 'bending-axis angle of the shear record, from the notebook (folded to 0-45 deg)'),
             d.E('tan_sh', 'tan(alpha_sh)', None, 'tan alpha'),
             d.E('r_sh', f'min(abs(M_2[{idx["psc_shear"]}]), abs(M_3[{idx["psc_shear"]}]))/max(abs(M_2[{idx["psc_shear"]}]), '
                         f'abs(M_3[{idx["psc_shear"]}]))', None, 'M_min / M_max of the record (equals tan alpha)'),
             d.E('sn_h', 'sin(alpha_sh)', None, 'sin alpha'), d.E('cs_h', 'sin(alpha_sh + 90*deg)', None, 'cos alpha'),
             d.E('s_max_h', 'D_pile*(sn_h + cs_h)/2', 'in', 'centroid to the extreme compression fiber'),
             d.V('s_sh', 'n', '-sn_h*x_st[n] + cs_h*y_st[n]', 'in', 'strand coordinate toward the compression face', show=False),
             d.V('m_sh', 'n', 'IF(s_sh[n] < -10**-9*in, 1, 0)', None, 'strand on the flexural tension half depth (1)', show=False),
             d.V('w_sh', 'n', 'm_sh[n]*s_sh[n]', 'in', 'its coordinate', show=False)),
        *[d.EQ(*scalar_chain('n_t', [f'm_sh[{s}]' for s in range(n_str)], 'n_tens', None, 'strands on the tension half')),
          d.EQ(*scalar_chain('w_t', [f'w_sh[{s}]' for s in range(n_str)], 'w_tens', 'in', 'sum of their coordinates'))],
        d.EQ(d.E('A_ps_t', 'A_str*n_tens', 'in**2', 'prestressing on the flexural tension half depth'),
             d.E('d_e', 's_max_h - w_tens/n_tens', 'in', 'depth from the compression fiber to that steel')),
        d.EQ(d.E('b_v', 'D_pile - d_void', 'in', 'effective web width'),
             d.E('d_v', 'max(0.9*d_e, 0.72*D_pile)', 'in', 'effective shear depth, 5.7.2.8'),
             d.E('M_u_v', 'max(M_u_sh, V_u_sh*d_v)', 'kip*ft', 'moment not less than Vu dv'),
             d.E('N_u', '-P_u_sh', 'kip', 'axial force, tension positive'),
             d.E('f_po', '0.7*f_pu', 'ksi', 'locked-in strand stress parameter'),
             d.E('F_long', 'M_u_v/d_v + 0.5*N_u + V_u_sh - A_ps_t*f_po', 'kip', 'numerator of Eq. 5.7.3.4.2-4'),
             d.E('eps_s0', 'F_long/(E_p*A_ps_t)', None, 'longitudinal strain, Eq. 5.7.3.4.2-4'),
             d.E('A_ct', 'A_g/2', 'in**2', 'concrete on the flexural tension side'),
             d.E('eps_s1', 'F_long/(E_p*A_ps_t + E_c*A_ct)', None, 'strain with Ec Act added (negative eps_s0)'),
             d.E('eps_s', 'max(IF(eps_s0 < 0, eps_s1, eps_s0), -0.0004)', None, 'longitudinal strain used (not below -0.40E-3)'),
             d.E('s_x', 'd_v', 'in', 'crack spacing parameter'),
             d.E('s_xe', 'min(80*in, max(12*in, s_x*1.38/((a_g + 0.63*in)/in)))', 'in', 'equivalent crack spacing, Eq. 5.7.3.4.2-7'),
             d.E('A_v', '2*spiral_wire_area', 'in**2', 'spiral area crossing the shear plane (two legs)'),
             d.E('A_v_min', f'0.0316*lambda_c*{root_fc}*b_v*spiral_pitch/f_y_spiral', 'in**2', 'minimum transverse reinforcement, 5.7.2.5'),
             d.E('beta_v', 'IF(A_v >= A_v_min, 4.8/(1 + 750*eps_s), 4.8/(1 + 750*eps_s)*51/(39 + s_xe/in))', None,
                 'beta, Eq. 5.7.3.4.2-1 (Av >= Av,min) or -2'),
             d.E('theta_v', '(29 + 3500*eps_s)*deg', 'deg', 'crack angle, Eq. 5.7.3.4.2-3'),
             d.E('V_c', f'0.0316*beta_v*lambda_c*{root_fc}*b_v*d_v', 'kip', 'concrete shear resistance'),
             d.E('V_s', 'A_v*f_y_spiral*d_v/(tan(theta_v)*spiral_pitch)', 'kip', 'spiral shear resistance'),
             d.E('V_n', 'min(V_c + V_s, 0.25*fc*b_v*d_v)', 'kip', 'nominal shear resistance'),
             d.E('V_r', 'phi_v*V_n', 'kip', 'factored shear resistance', key=True),
             d.E('DC_shear', 'V_u_sh/V_r', None, 'shear D/C')),
        d.H1(f'{number + 2}. Service I stresses (LRFD 5.9.2.3.2)'),
        d.EQ(d.E('P_sc', f'P_u[{idx["psc_svc_comp"]}]', 'kip', 'axial load, compression-stress record'),
             d.E('Mx_sc', f'M_2[{idx["psc_svc_comp"]}]', 'kip*ft', 'moment M2'), d.E('My_sc', f'M_3[{idx["psc_svc_comp"]}]', 'kip*ft', 'moment M3'),
             d.E('sig_c', 'f_pc_eff + P_sc/A_g + (abs(Mx_sc) + abs(My_sc))/S_g', 'ksi', 'corner compression after losses'),
             d.E('sig_c_lim', '0.6*fc', 'ksi', "compression limit 0.60 phi_w f'c (solid)"),
             d.E('DC_svc_c', 'sig_c/sig_c_lim', None, 'Service I compression D/C'),
             d.E('P_st', f'P_u[{idx["psc_svc_tens"]}]', 'kip', 'axial load, tension-stress record'),
             d.E('Mx_st', f'M_2[{idx["psc_svc_tens"]}]', 'kip*ft', 'moment M2'), d.E('My_st', f'M_3[{idx["psc_svc_tens"]}]', 'kip*ft', 'moment M3'),
             d.E('sig_t', 'f_pc_eff + P_st/A_g - (abs(Mx_st) + abs(My_st))/S_g', 'ksi', 'corner stress on the tension side (negative = tension)'),
             d.E('f_t_net', 'max(-sig_t, 0*ksi)', 'ksi', 'net tensile stress'),
             d.D('f_t_sev', f'min(0.3*ksi, 0.0948*lambda_c*{root_fc})', 'severe corrosive limit'), d.D('f_t_mod', f'min(0.6*ksi, 0.19*lambda_c*{root_fc})', 'moderate limit'),
             d.E('f_t_lim', 'IF(environment == 3, f_t_sev, f_t_mod)', 'ksi',
                 'tension limit: 0.19 sqrt(f\'c) up to 0.6 ksi (0.0948, 0.3 ksi in Extremely Aggressive environments)'),
             d.E('DC_svc_t', 'f_t_net/f_t_lim', None, 'Service I tension D/C')),
        d.H1(f'{number + 3}. Prestress, driving strength, minimum size'),
        d.EQ(d.E('f_pc_min', '0.7*ksi', 'ksi', 'minimum uniform prestress after losses, 5.12.9.4.3'),
             d.E('DC_pre', 'f_pc_min/f_pc_eff', None, 'effective prestress D/C'),
             d.E('DC_fc', '5*ksi/fc', None, "driving strength 5.0 ksi / f'c, 5.12.9.4"),
             d.E('D_min', 'IF(environment == 3, max(min_size_policy, 18*in), min_size_policy)', 'in', 'minimum square pile size, SDG Table 3.5.1-1'),
             d.E('DC_size', 'D_min/D_pile', None, 'minimum size D/C')),
        d.N('Pile-to-cap moment transfer (SDG 3.5.1.C) needs 48 in of embedment for the full bending capacity; the embedment here is '
            f'{ctx.p["embed_cap"]:g} in, so the connection stays a PENDING item of the notebook.'),
    ]
    return blocks, alpha_sh


# ----------------------------------------------------------------------------- steel pipe
def pipe_blocks(ctx, number):
    d = _dsl()
    e, idx = ctx.e, ctx.idx
    blocks = [
        d.H1(f'{number}. Pipe section'),
        d.FIG(f'{ctx.key}_section', 'Figure 1. Pipe cross-section: outside diameter and design wall thickness after the corrosion allowance.',
              width=300, data=ctx.figs['section'] if ctx.figs else None),
        d.EQ(d.E('t_des', 't_wall - t_corr', 'in', 'design wall thickness after corrosion allowance'),
             d.E('D_i', 'D_out - 2*t_des', 'in', 'inside diameter'),
             d.E('A_g', f'{PI_DISC}*(D_out**2 - D_i**2)', 'in**2', 'gross area'),
             d.E('I_g', f'{PI_64}*(D_out**4 - D_i**4)', 'in**4', 'moment of inertia'),
             d.E('S_g', 'I_g/(D_out/2)', 'in**3', 'elastic section modulus'),
             d.E('Z_p', '(D_out**3 - D_i**3)/6', 'in**3', 'plastic section modulus'),
             d.E('r_g', 'sqrt(I_g/A_g)', 'in', 'radius of gyration'),
             d.E('D_t', 'D_out/t_des', None, 'diameter-to-thickness ratio')),
        d.H1(f'{number + 1}. Axial compression (LRFD 6.9.4.1, 6.9.4.2.2c, 10.7.3.13.4)'),
        d.P('Fully embedded piles take no buckling reduction beyond the effective length K (Lu + Lf), Lf the depth to fixity (C10.7.3.13.4). '
            'The FBMP P-delta analysis is the preferred second-order check; this is the LRFD column check.'),
        d.EQ(d.E('lam_r', '0.11*E_s/Fy', None, 'nonslender limit 0.11 E/Fy'),
             d.E('A_eff', 'IF(D_t <= lam_r, A_g, (0.038*E_s/(Fy*D_t) + 2/3)*A_g)', 'in**2', 'effective area'),
             d.E('P_o', 'Fy*A_eff', 'kip', 'squash load'),
             d.E('E_soil', '0.465*(S_u/(kip/ft**2))*ksi', 'ksi', 'clay soil modulus 0.465 Su (used for clay only)'),
             d.E('L_fix', 'IF(soil_type == 1, 1.4*(E_s*I_g/E_soil)**0.25, 1.8*(E_s*I_g/n_h)**0.2)', 'ft', 'depth to fixity below ground'),
             d.E('KL', 'K_eff*(L_unsupported + L_fix)', 'ft', 'effective length'),
             d.E('KL_r', 'KL/r_g', None, 'slenderness ratio'),
             d.E('P_e', '9.869604401089358*E_s*A_g/KL_r**2', 'kip', 'elastic buckling load'),
             d.E('Pe_Po', 'P_e/P_o', None, 'Pe / Po'),
             d.E('P_n', 'IF(Pe_Po >= 0.44, 0.658**(P_o/P_e)*P_o, 0.877*P_e)', 'kip', 'nominal axial resistance, 6.9.4.1.1'),
             d.E('P_r_axial', 'phi_c_axial*P_n', 'kip', 'factored axial resistance', key=True),
             d.E('P_r_comb', 'phi_c_comb*P_n', 'kip', 'factored axial resistance, combined loading'),
             d.E('P_u_axial', f'P_u[{idx["pipe_axial"]}]', 'kip', 'largest factored compression incl. drag load'),
             d.E('DC_slender', 'D_t/(0.45*E_s/Fy)', None, 'D/t against the 0.45 E/Fy limit'),
             d.E('DC_klr', 'KL_r/120', None, 'KL/r against 120, 6.9.3'),
             d.E('DC_axial', 'P_u_axial/P_r_axial', None, 'axial compression D/C')),
        d.H1(f'{number + 2}. Flexure (LRFD 6.12.2.2.3)'),
        d.EQ(d.E('lam_p', '0.07*E_s/Fy', None, 'compact limit 0.07 E/Fy'),
             d.E('lam_nc', '0.31*E_s/Fy', None, 'noncompact limit 0.31 E/Fy'),
             d.E('M_p', 'Fy*Z_p', 'kip*ft', 'plastic moment'),
             d.D('M_nc', '(0.021*E_s/D_t + Fy)*S_g', 'noncompact: (0.021 E/(D/t) + Fy) S'),
             d.D('M_sl', '0.33*E_s/D_t*S_g', 'slender: 0.33 E/(D/t) S'),
             d.E('M_n', 'IF(D_t <= lam_p, M_p, min(M_p, IF(D_t <= lam_nc, M_nc, M_sl)))', 'kip*ft', 'nominal flexural resistance'),
             d.E('M_r', 'phi_f*M_n', 'kip*ft', 'factored flexural resistance', key=True)),
        d.H1(f'{number + 3}. Combined axial load and flexure (LRFD 6.9.2.2.1) and tension (6.8.2.1)'),
        d.P(f'Governing combined record (index {idx["pipe_comb"]}). The resultant moment is checked against Mr (axisymmetric section). '
            'A net uplift uses the tension resistance in place of the compression resistance.'),
        d.EQ(d.E('P_u_comb', f'P_u[{idx["pipe_comb"]}]', 'kip', 'factored axial load, compression positive'),
             d.E('M_u_comb', f'M_res[{idx["pipe_comb"]}]', 'kip*ft', 'resultant moment'),
             d.E('P_r_t', 'phi_y*Fy*A_g', 'kip', 'factored tension resistance, yielding of the gross section', key=True),
             d.E('DC_t', 'T_u/P_r_t', None, 'tension D/C, maximum strength uplift'),
             d.E('P_abs', 'abs(P_u_comb)', 'kip', 'magnitude of the axial force'),
             d.E('P_rc', 'IF(P_u_comb >= 0*kip, P_r_comb, P_r_t)', 'kip', 'matching axial resistance'),
             d.E('Pu_Pr', 'P_abs/P_rc', None, 'Pu / Pr'),
             d.E('DC_comb', 'IF(Pu_Pr >= 0.2, Pu_Pr + 8/9*M_u_comb/M_r, Pu_Pr/2 + M_u_comb/M_r)', None,
                 'interaction, Eq. 6.9.2.2.1-1 (Pu/Pr >= 0.2) or -2', key=True)),
        d.FIG(f'{ctx.key}_interaction', 'Figure 2. Combined axial load and flexure: the bilinear envelope of LRFD 6.9.2.2.1 (compression and tension) '
                                        'with the governing records. The picture is static; the equations above are live.', width=470,
              data=ctx.figs['interaction'] if ctx.figs else None),
        d.H1(f'{number + 4}. Shear (LRFD 6.12.1.2.3b)'),
        d.EQ(d.E('V_u_sh', f'V_res[{idx["pipe_shear"]}]', 'kip', 'resultant shear of the governing record'),
             d.E('F_cr1', '1.6*E_s/(sqrt(L_v/D_out)*D_t**1.25)', 'ksi', 'shear buckling stress, Eq. 6.12.1.2.3b-2'),
             d.E('F_cr2', '0.78*E_s/D_t**1.5', 'ksi', 'shear buckling stress, Eq. 6.12.1.2.3b-3'),
             d.E('F_cr', 'min(max(F_cr1, F_cr2), 0.58*Fy)', 'ksi', 'flexural shear buckling resistance'),
             d.E('V_n', '0.5*F_cr*A_g', 'kip', 'nominal shear resistance'),
             d.E('V_r', 'phi_v_steel*V_n', 'kip', 'factored shear resistance', key=True),
             d.E('DC_shear', 'V_u_sh/V_r', None, 'shear D/C')),
    ]
    return blocks


# ----------------------------------------------------------------------------- summary, plot, notes
def summary_checks(e):
    """(sheet ratio name, check key, text) in plot order."""
    if e.family == 'psc':
        return [('DC_axial', 'psc_axial', 'axial compression'), ('DC_bi', 'psc_flex_bi', 'axial + biaxial flexure, 5.6.4.5'),
                ('DC_rs', 'psc_flex_res', 'axial + flexure, resultant axis'), ('DC_shear', 'psc_shear', 'shear'),
                ('DC_t', 'psc_tension', 'tension'), ('DC_svc_c', 'psc_svc_comp', 'Service I compression'),
                ('DC_svc_t', 'psc_svc_tens', 'Service I tension'), ('DC_pre', 'psc_prestress', 'effective prestress'),
                ('DC_fc', 'psc_fc_driving', 'driving strength'), ('DC_size', 'psc_min_size', 'minimum size'),
                ('DC_sp', 'spacing', 'pile spacing'), ('DC_nbr', 'nbr', 'bearing resistance vs Table 3.5.13-1')]
    return [('DC_slender', 'pipe_slender', 'local buckling D/t'), ('DC_klr', 'pipe_klr', 'KL/r'), ('DC_axial', 'pipe_axial', 'axial compression'),
            ('DC_comb', 'pipe_comb', 'axial + flexure, 6.9.2.2.1'), ('DC_shear', 'pipe_shear', 'shear'), ('DC_t', 'pipe_tension', 'tension'),
            ('DC_sp', 'spacing', 'pile spacing')]


def pending_note(e):
    pend = [c for c in e.checks if 'PENDING' in c.status]
    if not pend:
        return 'No item is pending.'
    labels = []
    for c in pend:
        label = c.label.strip()
        if label not in labels:
            labels.append(label)
    return f'The notebook lists {len(pend)} PENDING items; the distilled ratios below do not close them: ' + '; '.join(labels) + '.'


def max_items(names):
    d = _dsl()
    items, prev = [], None
    pieces = [names[g0:g0 + 5] for g0 in range(0, len(names), 5)]
    for n, part in enumerate(pieces):
        expr = 'max(' + (f'{prev}, ' if prev else '') + ', '.join(part) + ')'
        if n == len(pieces) - 1:
            items.append(d.E('DC_max', expr, None, 'largest of the distilled ratios', key=True))
        else:
            prev = f'DC_m{n + 1}'
            items.append(d.D(prev, expr))
    return items


def summary_blocks(ctx, number, fig_number):
    d = _dsl()
    _sheet()
    from scripts import mathcad_plot
    e = ctx.e
    checks = summary_checks(e)
    n = len(checks)
    names = [c[0] for c in checks]
    key = '; '.join(f'{i + 1} {text}' for i, (_, _, text) in enumerate(checks))
    dc_model, rec = e.details['model_dc']
    fbmp = (f'FB-MultiPier reports a largest model D/C of {dc_model:.2f}' + (f' at {loads.record_id(rec)}' if rec else '') + '.') if dc_model is not None else ''
    blocks = [
        d.H1(f'{number}. Summary of checks'),
        d.EQ(*[d.S(name, None, text) for name, _, text in checks],
             *max_items(names),
             d.E('Status', 'IF(DC_max <= 1 + 10**-9, "PASS", "FAIL")', None, 'distilled numerical checks only', key=True)),
        d.P(f'Figure {fig_number} data: every distilled ratio in check order, split at the limit. A check on the other side of the limit is parked '
            'at check number -1, outside the plot.'),
        d.EQ(d.D('DC_all', 'col(' + ', '.join(names) + ')', 'distilled ratios in check order')),
        d.ROW(d.D('Limit', '1'), d.R('j', 0, 'last(DC_all)'), d.D('ymax', 'max(1.2, 1.1*max(DC_all))')),
        d.ROW(d.V('x_ok', 'j', 'IF(DC_all[j] <= Limit, j + 1, -1)', show=False), d.V('y_ok', 'j', 'IF(DC_all[j] <= Limit, DC_all[j], 0)', show=False)),
        d.ROW(d.V('x_ng', 'j', 'IF(DC_all[j] > Limit, j + 1, -1)', show=False), d.V('y_ng', 'j', 'IF(DC_all[j] > Limit, DC_all[j], 0)', show=False)),
        d.ROW(d.D('CheckGood', 'augment(x_ok, y_ok)'), d.D('CheckNoGood', 'augment(x_ng, y_ng)')),
        mathcad_plot.plot_block(n, DC_CAPTION.format(n=fig_number), title=DC_TITLE, over_label='D/C over 1.0', within_label='D/C within 1.0'),
        d.N('Check numbers: ' + key + '.'),
        d.N(pending_note(e)),
        d.N(fbmp + ' The distilled Status covers the recomputed numerical checks only; it is not design acceptance.'),
    ]
    return blocks


def basis_blocks(ctx):
    d = _dsl()
    e, p = ctx.e, ctx.p
    a = e.case['analysis']
    fam = e.family
    registered = (f'registered export {a["registered_id"]}' if a.get('registered_id') and a.get('matches_register')
                  else 'not a registered export (new upload)')
    plan = (f'Standard Plans Index {e.case["psc"]["index"]} ({p["D_pile"]:g} in square), strand pattern {e.case["psc"]["pattern"]}, spiral '
            f'{p["spiral_wire_area"]:g} in² wire at {p["spiral_pitch"]:g} in') if fam == 'psc' else (
        f'ASTM A252 / API 5L pipe {p["D_out"]:g} in x {p["t_wall"]:g} in wall, Fy = {p["Fy"]:g} ksi (noncomposite)')
    codes = ('AASHTO LRFD Bridge Design Specifications, 10th edition (2024): 5.6.4.4, 5.6.4.5, 5.6.6.1, 5.7.3.3, 5.7.3.4.2, 5.9.2.3.2, 5.12.9.4; '
             'FDOT Structures Design Guidelines (SDG) 3.5 and Structures Detailing Manual (SDM) 11.4, January 2026; Standard Plans Index 455.'
             if fam == 'psc' else
             'AASHTO LRFD Bridge Design Specifications, 10th edition (2024): 6.5.4.2, 6.8.2.1, 6.9.2.2.1, 6.9.4.1, 6.12.1.2.3b, 6.12.2.2.3, 10.7.3.13; '
             'FDOT Structures Design Guidelines (SDG) 3.5 and Structures Detailing Manual (SDM) 11.4, January 2026; Specification 455-8.2 (Table 962-11).')
    bullets = [
        f'FBMP source: {a["filename"]}, SHA-256 {a["sha256"]} ({registered}). {p["N_pile"]:g} piles at {p["S_pile"]:g} ft; cutoff elevation '
        f'{p["EL_cutoff"]:g} ft, ground {p["EL_ground"]:g} ft.',
        f'Pile: {plan}.',
        f'Downdrag {p["DD_tons"]:g} tons per pile is a drag load DR: gamma_DR = {p["gamma_DR_str"]:g} (strength) and {p["gamma_DR_ser"]:g} (Service I) in the '
        'structural demands (LRFD Table 3.4.1-1, 10.7.3.7); it is excluded from the Factored Design Load and added nominally to the required '
        f'bearing resistance (SDG Eq. 3-1, phi = {p["phi_geo"]:g}).',
        'Every worksheet equation is parsed once and evaluated by the generator with unit checking; the build compares each result with the '
        'notebook before the file is written. Governing records, the notebook angles and the neutral-axis depth c_gov are inputs read from the notebook.',
    ]
    if fam == 'psc':
        bullets.append('The interaction curve is swept live (vectors); the biaxial route of LRFD 5.6.4.5 and the strain-compatibility check about the '
                       'resultant axis are both evaluated, and the larger ratio governs.')
    else:
        bullets.append('Second-order effects come from the FBMP P-delta analysis; the LRFD column check here uses K(Lu + Lf). Composite (filled) '
                       'pipe is out of scope.')
    return [
        d.Block('title', f'{e.case["support"]} Pile Design'),
        d.P('Project: D2 I-95 Pedestrian Bridge.'),
        d.P(f'Distilled from the pile design notebook (package {ctx.rev[:12]}), case "{e.case["name"]}". Same inputs, equations and load '
            'combinations as the notebook; results should match its exported report.'),
        d.P(f'Codes: {codes}'),
        d.P(f'Status: {e.status}. Inputs are highlighted yellow; values for the plans are boxed.'),
        d.H1('1. Design basis'),
        d.BUL(bullets),
        d.H1('2. Inputs'),
        *input_blocks(ctx),
    ]


def sheet(e, rev, figs=None):
    """The block list of the worksheet of an Evaluation (prestressed pile or steel pipe, by the case family)."""
    d = _dsl()
    if e.family == 'psc' and e.value('d_void', 'in') > 0:
        raise ValueError('The Mathcad worksheet does not cover hollow piles (Index 455-030 void).')
    ctx = context(e, rev, figs)
    blocks = basis_blocks(ctx)
    if e.family == 'psc':
        blocks += demand_blocks(ctx, 3)
        blocks += [d.H1('4. Pile spacing'), *common_geometry(ctx)]
        blocks += psc_section_blocks(ctx, 5)
        blocks += psc_axial_blocks(ctx, 6)
        res, c_gov = psc_resistance_blocks(ctx, 7)
        blocks += res
        tail, _ = psc_tension_shear_service(ctx, 10)
        blocks += tail
        blocks += geotech_blocks(ctx, 14)
        blocks += summary_blocks(ctx, 15, 3)
    else:
        blocks += demand_blocks(ctx, 3)
        blocks += [d.H1('4. Pile spacing'), *common_geometry(ctx)]
        blocks += pipe_blocks(ctx, 5)
        blocks += geotech_blocks(ctx, 10)
        blocks += summary_blocks(ctx, 11, 3)
    return blocks


# ----------------------------------------------------------------------------- verification against the notebook
def _mc(env, name, unit):
    return _dsl()._to(env[name], _u(unit))


def _sweep_comparisons(out, env, tag, curve):
    n = len(curve['c']) - 2
    for key, name, unit in (('c', 'c', 'in'), ('Pn', 'P_n', 'kip'), ('Mn', 'M_n', 'kip*ft'), ('eps_t', 'eps_t', None),
                            ('phi', 'phi', None), ('Pr', 'P_r', 'kip'), ('Mr', 'M_r', 'kip*ft')):
        vector = env[f'{name}_{tag}']
        assert len(vector) == n, (name, tag, len(vector), n)
        for i in range(n):
            out.append((f'{name}_{tag}[{i}]', _dsl()._to(vector[i], _u(unit)), float(curve[key][i + 1])))


def comparisons(env, e):
    """(label, worksheet value, notebook value) for every quantity both calculations hold."""
    d = _dsl()
    out = []
    names = [x['name'] for x in e.definitions]
    missing = [n for n in names + list(e.external_meta) if n not in env]
    if missing:
        raise AssertionError(f'notebook quantities missing from the worksheet: {sorted(missing)}')
    for n in names + list(e.external_meta):
        unit = e.units.get(n)
        out.append((n, d._to(env[n], _u(unit)), float(e.value(n, unit))))
    ratio = {c.key: c.ratio for c in e.checks}
    for name, key, _ in summary_checks(e):
        out.append((f'{name} vs check {key}', env[name].v, float(ratio[key])))
    numeric = [env[name].v for name, _, _ in summary_checks(e)]
    out.append(('DC_max', env['DC_max'].v, max(numeric)))
    out.append(('Status', 1.0 if env['Status'] == 'PASS' else 0.0, 1.0 if max(numeric) <= 1 + 1e-9 else 0.0))
    recs = demand_records(e)
    for g, (key, short, rec) in enumerate(recs):
        for name, field, unit in (('P_fbmp', 'P_fbmp', 'kip'), ('M_2', 'M2', 'kip*ft'), ('M_3', 'M3', 'kip*ft'), ('M_res', 'M_res', 'kip*ft'),
                                  ('V_res', 'V_res', 'kip'), ('P_u', 'P_u', 'kip')):
            out.append((f'{name}[{g}] {short}', d._to(env[name][g], _u(unit)), float(rec[field])))
    if e.family == 'psc':
        out += psc_comparisons(env, e)
    return out


def psc_comparisons(env, e):
    d = _dsl()
    out = []
    ps_sec = e.details['section']
    n = len(e.curve['c']) - 2
    _sweep_comparisons(out, env, 'x', e.curve)
    _sweep_comparisons(out, env, 'r', e.curve['resultant'])
    out.append(('P_n_pt', d._to(env['P_n_pt'], 'kip'), float(e.curve['Pn'][-1])))
    out.append(('P_r_pt', d._to(env['P_r_pt'], 'kip'), float(e.curve['Pr'][-1])))
    out.append(('P_r_pc', d._to(env['P_r_pc'], 'kip'), float(e.curve['Pr'][0])))
    # extended vectors are the curve arrays, end points included
    for tag, curve in (('x', e.curve), ('r', e.curve['resultant'])):
        for i in range(n + 2):
            out.append((f'P_ext_{tag}[{i}]', d._to(env[f'P_ext_{tag}'][i], 'kip'), float(curve['Pr'][i])))
            out.append((f'M_ext_{tag}[{i}]', d._to(env[f'M_ext_{tag}'][i], 'kip*ft'), float(curve['Mr'][i])))
    # strand layout: same set of centres as sections.strand_layout
    mine = sorted(((round(env['y_st'][s].v, 6), round(env['x_st'][s].v, 6)) for s in range(len(env['x_st']))))
    theirs = sorted((round(y, 6), round(x, 6)) for x, y in e.details['layout'])
    assert len(mine) == len(theirs)
    for k, ((ym, xm), (yt, xt)) in enumerate(zip(mine, theirs)):
        out.append((f'strand {k} y', ym, yt))
        out.append((f'strand {k} x', xm, xt))
    # depths of the strands at the two angles
    for geo, curve in (('x', e.curve), ('r', e.curve['resultant'])):
        out.append((f'd_t_{geo}', d._to(env[f'd_t_{geo}'], 'in'), float(curve['d_t'])))
    # resultant-axis check: bracket, interpolation, exact point
    rs = demand_records(e)[0:3][2][2]
    k, t = ray_bracket(e.curve['resultant'], rs['P_u'], rs['M_res'])
    out.append(('k_rs', env['k_rs'].v, float(k)))
    out.append(('t_rs', env['t_rs'].v, t))
    out.append(('DC_ray', env['DC_ray'].v, float(e.details['ratio_rs'])))
    out.append(('tan alpha_rs', env['tan_rs'].v, env['r_rs'].v))
    out.append(('tan alpha_sh', env['tan_sh'].v, env['r_sh'].v))
    out.append(('c_live', d._to(env['c_live'], 'in'), d._to(env['c_gov'], 'in')))
    out.append(('DC_bi vs 5.6.4.5', env['DC_bi'].v, float(e.details['biaxial']['ratio'])))
    # exact evaluation at c_gov, an independent call of the notebook's own routine
    import numpy as np
    exact = sections.psc_interaction(ps_sec, c_values=np.array([d._to(env['c_gov'], 'in')]), angle=math.radians(e.value('alpha_rs', 'deg')),
                                     phi_c=e.case['inputs']['phi_c'], phi_t=e.case['inputs']['phi_t'])
    for key, name, unit in (('Pn', 'P_n_cg', 'kip'), ('Mn', 'M_n_cg', 'kip*ft'), ('eps_t', 'eps_t_cg', None), ('phi', 'phi_cg', None),
                            ('Pr', 'P_r_cg', 'kip'), ('Mr', 'M_r_cg', 'kip*ft')):
        out.append((name, d._to(env[name], _u(unit)), float(exact[key][1])))
    if 'M_cap_u' in env:
        out.append(('M_cap_u', d._to(env['M_cap_u'], 'kip*ft'), float(sections.moment_capacity_at_axial(e.curve, e.value('P_u_bi', 'kip')))))
    return out


def approximations(env, e):
    """(label, worksheet value, notebook value, relative tolerance): quantities that differ by design (no interpolation)."""
    if e.family != 'psc':
        return []
    return [('DC at c_gov (exact) vs the interpolated resultant-axis D/C', env['DC_cg'].v, float(e.value('DC_rs')), 0.02)]


def check_display_units(blocks, env):
    """Every displayed unit is dimensionally compatible with the value it is shown in (else Mathcad would flag the result)."""
    d = _dsl()
    for block in blocks:
        for item in (block.payload if block.kind in ('eqs', 'row', 'inputs') else []):
            if not item.unit or item.kind not in ('eq', 'idef', 'show'):
                continue
            value = d.ev(item.tree, env) if item.kind == 'show' else env[item.name]
            for v in (list(value.values()) if isinstance(value, dict) else value if isinstance(value, list) else [value]):
                d._to(v, _u(item.unit))


def check_plot_data(env, e):
    """Figure data: DC_all holds the Section summary ratios in check order and each check sits in the trace of its side of the limit."""
    values = [y.v for y in env['DC_all']]
    expected = [env[name].v for name, _, _ in summary_checks(e)]
    if values != expected:
        raise AssertionError('DC_all is not the summary ratios in check order')
    for j, v in enumerate(values):
        shown, parked = (env['CheckNoGood'], env['CheckGood']) if v > env['Limit'].v else (env['CheckGood'], env['CheckNoGood'])
        if (shown[j, 0].v, shown[j, 1].v) != (j + 1, v) or (parked[j, 0].v, parked[j, 1].v) != (-1, 0):
            raise AssertionError(f'the plot traces misplace check {j + 1}')
    if not env['ymax'].v >= max(1.2, 1.1 * max(values)):
        raise AssertionError('the plot y range does not reach the largest ratio')


def verify(blocks, e, tol=TOL):
    """Run the worksheet and compare every quantity with the notebook; returns the environment."""
    d = _dsl()
    env = d.run(blocks)
    bad = [(n, a, b) for n, a, b in comparisons(env, e) if not abs(a - b) <= tol * max(1.0, abs(b))]
    if bad:
        raise AssertionError('Mathcad equations differ from the notebook:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b in bad[:40]) +
                             (f'\n  ... {len(bad) - 40} more' if len(bad) > 40 else ''))
    loose = [(n, a, b, r) for n, a, b, r in approximations(env, e) if not abs(a - b) <= r * max(1.0, abs(b))]
    if loose:
        raise AssertionError('Mathcad equations differ from the notebook beyond their tolerance:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b, _ in loose))
    check_display_units(blocks, env)
    check_plot_data(env, e)
    return env


def check_inputs(blocks, e):
    """Every worksheet input equals the notebook input (or Standard Plans value) after unit conversion; none is missing."""
    d = _dsl()
    env, seen = {}, set()
    spec_by = {s['name']: s for s in INPUT_SPEC}
    for block in blocks:
        for item in (block.payload if block.kind in ('inputs', 'eqs', 'row') else []):
            if item.kind != 'input':
                continue
            env[item.name] = d.ev(item.tree, env)
            spec = spec_by.get(item.name)
            if spec is None:
                continue
            unit = _u(spec['unit'])
            mine = d._to(env[item.name], unit) if unit else env[item.name].v
            want = e.case['inputs'][item.name]
            assert abs(mine - want) <= 1e-12 * max(1.0, abs(want)), (item.name, mine, want)
            seen.add(item.name)
    wanted = {s['name'] for s in INPUT_SPEC if s['family'] in (e.family, 'both') and e.case['inputs'].get(s['name']) is not None}
    absent = wanted - seen
    assert not absent, f'notebook inputs missing from the worksheet: {sorted(absent)}'
    return env


# ----------------------------------------------------------------------------- figures
DPI = 150


def _plt():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.linewidth': 0.8, 'figure.facecolor': 'white'})
    return plt


def _png(plt, fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=DPI, metadata={'Software': None})
    plt.close(fig)
    return buf.getvalue()


def _section_psc(e, recs):
    plt = _plt()
    from matplotlib.patches import Circle, Rectangle
    p, plan, option = e.case['inputs'], e.details['plan'], e.details['option']
    D = p['D_pile']
    fig, ax = plt.subplots(figsize=(4.4, 4.5))
    ax.add_patch(Rectangle((-D / 2, -D / 2), D, D, fc='#e9eef2', ec='black', lw=1.4))
    cover = 3.0
    ax.add_patch(Rectangle((-D / 2 + cover, -D / 2 + cover), D - 2 * cover, D - 2 * cover, fc='none', ec='#7a8a99', lw=0.8, ls='--'))
    r = math.sqrt(option['strand_area_in2'] / math.pi)
    for x, y in e.details['layout']:
        ax.add_patch(Circle((x, y), r * 1.6, fc='#c0392b', ec='#7b241c', lw=0.6))
    ax.axhline(0, color='#aab4bd', lw=0.6)
    ax.axvline(0, color='#aab4bd', lw=0.6)
    reach = D / 2 * 1.32
    for key, color, label in (('psc_flex_res', '#1f6f3f', 'resultant moment'), ('psc_shear', '#2057a0', 'shear record')):
        rec = next((r_ for k, _, r_ in recs if k == key), None)
        if rec is None:
            continue
        a = bending_axis_of(rec)
        ax.plot([-reach * math.cos(a), reach * math.cos(a)], [-reach * math.sin(a), reach * math.sin(a)], color=color, lw=1.1, ls='-.',
                label=f'bending axis, {label}: {math.degrees(a):.1f}°')
        ax.annotate('', xy=(-math.sin(a) * D * 0.62, math.cos(a) * D * 0.62), xytext=(-math.sin(a) * D * 0.42, math.cos(a) * D * 0.42),
                    arrowprops=dict(arrowstyle='->', color=color, lw=1.2))
    ax.annotate('', xy=(-D / 2, -D / 2 - 2.9), xytext=(D / 2, -D / 2 - 2.9), arrowprops=dict(arrowstyle='<->', lw=0.8))
    ax.text(0, -D / 2 - 3.2, f'D = {D:g} in', ha='center', va='top')
    ax.annotate('', xy=(-D / 2, -D / 2 - 0.9), xytext=(-D / 2 + p['d_edge'], -D / 2 - 0.9), arrowprops=dict(arrowstyle='<->', lw=0.7))
    ax.text(-D / 2 + p['d_edge'] / 2, -D / 2 - 1.1, f'{p["d_edge"]:g} in', ha='center', va='top', fontsize=7.5)
    ax.set_xlim(-D / 2 - 3.0, D / 2 + 3.0)
    ax.set_ylim(-D / 2 - 5.0, D / 2 + 3.0)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(f'{D:g} in square pile, {option["count"]} strands ({e.case["psc"]["index"]}, {e.case["psc"]["pattern"]})', fontsize=9.5)
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.12), fontsize=7.5, frameon=False)
    fig.tight_layout()
    return _png(plt, fig)


def _section_pipe(e):
    plt = _plt()
    from matplotlib.patches import Circle
    p = e.case['inputs']
    D, t = p['D_out'], p['t_wall'] - p['t_corr']
    fig, ax = plt.subplots(figsize=(4.0, 4.0))
    ax.add_patch(Circle((0, 0), D / 2, fc='#c9d3dc', ec='black', lw=1.4))
    ax.add_patch(Circle((0, 0), D / 2 - t, fc='white', ec='black', lw=1.0))
    ax.annotate('', xy=(-D / 2, -D / 2 - 1.4), xytext=(D / 2, -D / 2 - 1.4), arrowprops=dict(arrowstyle='<->', lw=0.8))
    ax.text(0, -D / 2 - 2.2, f'D = {D:g} in', ha='center', va='top')
    ax.annotate(f't = {t:g} in', xy=(D / 2 * 0.7071, D / 2 * 0.7071), xytext=(D / 2 + 1.2, D / 2 + 1.0), fontsize=8.5,
                arrowprops=dict(arrowstyle='-', lw=0.7))
    ax.set_xlim(-D / 2 - 3, D / 2 + 6)
    ax.set_ylim(-D / 2 - 4, D / 2 + 3)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(f'{D:g} in x {t:g} in steel pipe pile, Fy = {p["Fy"]:g} ksi', fontsize=9.5)
    fig.tight_layout()
    return _png(plt, fig)


def _interaction_psc(e, recs):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    c0, cr = e.curve, e.curve['resultant']
    ax.plot(c0['Mn'], c0['Pn'], color='#9aa7b2', lw=1, ls='--', label='nominal, axis parallel to a face')
    ax.plot(c0['Mr'], c0['Pr'], color='#1f4e8c', lw=1.8, label='factored, axis parallel to a face')
    ax.plot(cr['Mr'], cr['Pr'], color='#1f6f3f', lw=1.5, label=f'factored, resultant axis ({e.curve["resultant_angle_deg"]:.1f}°)')
    ax.axhline(e.value('P_r_max', 'kip'), color='#b03a2e', lw=0.8, ls=':', label='φPn,max')
    for key, marker, color, label in (('psc_axial', 'o', '#6c3483', 'largest compression'), ('psc_flex_bi', 's', '#c0392b', '5.6.4.5 record'),
                                       ('psc_flex_res', 'D', '#117a65', 'resultant-axis record')):
        rec = next((r_ for k, _, r_ in recs if k == key), None)
        if rec is not None:
            ax.plot(rec['M_res'], rec['P_u'], marker=marker, color=color, ms=7, ls='none', label=f'{label}: Pu {rec["P_u"]:.0f} kip, Mu {rec["M_res"]:.0f} kip-ft')
    ax.axhline(0, color='black', lw=0.6)
    ax.set_xlabel('Moment, kip-ft')
    ax.set_ylabel('Axial load, kip (compression +)')
    ax.set_xlim(left=0)
    ax.grid(True, color='#e3e8ec', lw=0.6)
    ax.legend(fontsize=7.2, loc='lower right', frameon=True)
    ax.set_title('Interaction diagram (picture; the points are the live vectors of the worksheet)', fontsize=9)
    fig.tight_layout()
    return _png(plt, fig)


def _interaction_pipe(e, recs):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    Pr, Mr, Pt = e.value('P_r_comb', 'kip'), e.value('M_r', 'kip*ft'), e.value('P_r_t', 'kip')
    ax.plot([0, 0.8 * 8 / 9 * Mr, Mr], [Pr, 0.2 * Pr, 0], color='#1f4e8c', lw=1.8, label='6.9.2.2.1 envelope, compression')
    ax.plot([0, 0.8 * 8 / 9 * Mr, Mr], [-Pt, -0.2 * Pt, 0], color='#2c7fb8', lw=1.8, label='6.9.2.2.1 envelope, tension')
    for key, marker, color, label in (('pipe_axial', 'o', '#6c3483', 'largest compression'), ('pipe_comb', 's', '#c0392b', 'combined record'),
                                       ('pipe_tension', 'v', '#117a65', 'uplift record')):
        rec = next((r_ for k, _, r_ in recs if k == key), None)
        if rec is not None:
            ax.plot(rec['M_res'], rec['P_u'], marker=marker, color=color, ms=7, ls='none', label=f'{label}: Pu {rec["P_u"]:.0f} kip, Mu {rec["M_res"]:.0f} kip-ft')
    ax.axhline(0, color='black', lw=0.6)
    ax.set_xlabel('Resultant moment, kip-ft')
    ax.set_ylabel('Axial load, kip (compression +)')
    ax.set_xlim(left=0)
    ax.grid(True, color='#e3e8ec', lw=0.6)
    ax.legend(fontsize=7.2, loc='upper right', frameon=True)
    ax.set_title('Combined axial load and flexure, LRFD 6.9.2.2.1', fontsize=9)
    fig.tight_layout()
    return _png(plt, fig)


def figures(e):
    """PNG bytes of the worksheet figures: {'section': ..., 'interaction': ...} (matplotlib, no browser needed)."""
    recs = demand_records(e)
    if e.family == 'psc':
        return {'section': _section_psc(e, recs), 'interaction': _interaction_psc(e, recs)}
    return {'section': _section_pipe(e), 'interaction': _interaction_pipe(e, recs)}


def figure_names(e):
    return [f'{support_slug(e.case["support"])}_{name}' for name in ('section', 'interaction')]


def render_figures(e, folder=None):
    folder = Path(folder or FIGURES)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for name, data in zip(figure_names(e), figures(e).values()):
        path = folder / f'{name}.png'
        path.write_bytes(data)
        out.append(path)
    return out


# ----------------------------------------------------------------------------- build
def values_note(env, e):
    parts = [f'{text} {env[name].v:.3f}' for name, _, text in summary_checks(e)]
    return 'Notebook values for comparison, D/C: ' + '; '.join(parts) + f'; largest {env["DC_max"].v:.3f}.'


def build(e, repo=None, info=None):
    """Worksheet XML text of an Evaluation.

    repo=None draws the two figures in memory (notebook export; no browser needed). repo=<checkout> reads the committed PNGs of
    pile_design/mathcad instead (the command line, so the committed files and a rebuild agree). `info`, when given, receives
    page_fills, the number of exact and approximate comparisons and the figure names."""
    d = _dsl()
    rev = package_revision()
    if repo is None:
        figs, folder = figures(e), FIGURES
    else:
        figs, folder = None, Path(repo) / 'pile_design' / 'mathcad'
        for name in figure_names(e):
            if not (folder / f'{name}.png').is_file():
                raise FileNotFoundError(f'pile_design/mathcad/{name}.png is missing; run scripts/build_pile_mathcad.py --render-figures')
    blocks = sheet(e, rev, figs)
    d.check_names(blocks)
    check_inputs(blocks, e)
    env = verify(blocks, e)
    blocks.append(d.N(values_note(env, e)))
    a = e.case['analysis']
    with result_widths({'Rec': 300}):
        text = d.document(blocks, title=f'{e.case["support"]} Pile Design',
                          description=f'Written by pile_design/mathcad.py (scripts/build_pile_mathcad.py) from the pile_design package {rev[:12]}; '
                                      f'FBMP {a["filename"]} (SHA-256 {a["sha256"]})',
                          seed=int(rev[:12], 16), figures_dir=folder, check_width=True)
        fills = d.layout(blocks, folder).check_pages()
    if info is not None:
        info.update(page_fills=[round(f) for f in fills], comparisons=len(comparisons(env, e)), approximations=len(approximations(env, e)),
                    figures=figure_names(e), env=env, blocks=blocks)
    return text
