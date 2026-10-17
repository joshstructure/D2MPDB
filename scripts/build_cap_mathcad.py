"""Build the distilled Mathcad 15 worksheets of the three cap designs (End Bent 1, End Bent 2, Pier Cap).

Each worksheet distils the latest cap design report of its cap: the same case, the same C005 formula set, and the
actual-cage LRFD checks at the stations the tool found governing. The worksheet is written from the compact equation
lists below (the shared writer is scripts/mathcad_sheet.py). Every expression is parsed once and used two ways:
emitted as Mathcad worksheet XML and evaluated here with unit checking, so each result can be compared with the cap
tool (pier_cap) before the file is written. The build stops on any mismatch, on a region that crosses a page or the right
edge of the text area, and on an evaluation order Mathcad would not follow.

    python scripts/build_cap_mathcad.py                  # write cap_mathcad/*.xmcd
    python scripts/build_cap_mathcad.py --render-figures  # redraw the PNGs first (needs Edge)
"""
import contextlib
import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pier_cap.model import evaluate, DEFINITIONS, BAR_AREA, BAR_DIAMETER  # noqa: E402
from pier_cap.transverse import scheduled_bars  # noqa: E402
from pier_cap.lrfd_checks import section_window, settings  # noqa: E402
from scripts import mathcad_sheet  # noqa: E402
from scripts.mathcad_sheet import (  # noqa: E402,F401
    BUL, D, E, EQ, FIG, H1, H2, I, INPUTS, N, P, R, ROW, S, V, Block, Item, U, check_names, document, ev, parse, run, _to)

OUT_DIR = ROOT / 'cap_mathcad'
FIGURES = OUT_DIR / 'figures'
WITH_FIGURES = True            # False builds without the two PNGs (development only)
TOL = 1e-9

CAPS = [
    dict(key='end_bent_1', label='End Bent 1', case='project_current/cap_design/end_bents/selected_case.json',
         reports='project_current/cap_design/end_bents', output='End Bent 1 Cap Design.xmcd'),
    dict(key='end_bent_2', label='End Bent 2', case='project_current/cap_design/end_bent_2/selected_case.json',
         reports='project_current/cap_design/end_bent_2', output='End Bent 2 Cap Design.xmcd'),
    dict(key='pier', label='Pier Cap', case='project_current/cap_design/pier/selected_case.json',
         reports='project_current/cap_design/pier', output='Pier Cap Design.xmcd'),
]

UNIT = {d['name']: d['unit'] for d in DEFINITIONS}          # display unit of every C005 quantity
REGIONS = 'NPB'
TAGS = ['S', 'N', 'P', 'B', 'M']                             # station k = 0..4
LABELS = ['S shear', 'N long.', 'P long.', 'B long.', 'M min Av']

@contextlib.contextmanager
def result_widths(widths):
    """Row-display widths of this module's vectors, in force only while its worksheets are laid out."""
    saved = dict(mathcad_sheet.RESULT_WIDTHS)
    mathcad_sheet.RESULT_WIDTHS.update(widths)
    try:
        yield
    finally:
        mathcad_sheet.RESULT_WIDTHS.clear()
        mathcad_sheet.RESULT_WIDTHS.update(saved)


# ----------------------------------------------------------------------------- report link
_EVALS = {}


def evaluate_cap(cap):
    if cap['key'] not in _EVALS:
        _EVALS[cap['key']] = evaluate(json.loads((ROOT / cap['case']).read_text(encoding='utf-8')))
    return _EVALS[cap['key']]


def case_sha256(e):
    return hashlib.sha256(json.dumps(e.case, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def formula_sha256():
    return hashlib.sha256(json.dumps(DEFINITIONS, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def notebook_revision():
    nb = json.loads((ROOT / 'Cap_and_Pile_Design.ipynb').read_text(encoding='utf-8'))
    for cell in nb['cells']:
        m = re.search(r'revision = "([0-9a-f]{64})"', ''.join(cell.get('source', [])))
        if m:
            return m.group(1)[:12]
    raise ValueError('Cap_and_Pile_Design.ipynb has no package revision')


def report_link(cap, e):
    """Newest report of the cap folder whose printed case and formula hashes both match the evaluated case."""
    case_sha, formula_sha = case_sha256(e), formula_sha256()
    dated = []
    for path in (ROOT / cap['reports']).glob('*Cap Design*.html'):
        m = re.search(r'(\d{1,2})-(\d{1,2})\.html$', path.name)
        if m:
            dated.append(((int(m.group(1)), int(m.group(2))), path.name, path))
    for _, _, path in sorted(dated, reverse=True):
        text = path.read_bytes().decode('utf-8', errors='replace')
        c = re.search(r'Case SHA-256 \(canonical JSON\):\s*([0-9a-f]{64})', text)
        f = re.search(r'Formula definition SHA-256:\s*([0-9a-f]{64})', text)
        if c and f and c.group(1) == case_sha and f.group(1) == formula_sha:
            g = re.search(r'Generated:\s*([0-9T:+\-.Z]+)', text)
            return dict(file=path.name, stamp=g.group(1) if g else 'unstamped', case_sha=case_sha, formula_sha=formula_sha)
    raise ValueError(f'{cap["label"]}: no report in {cap["reports"]} prints the evaluated case hash {case_sha[:12]} '
                     f'and formula hash {formula_sha[:12]}; export the report again')


# ----------------------------------------------------------------------------- stations
def interval_of(e, row):
    """The interval row (carrying Av/s) that a station row belongs to."""
    prefix = row['id'].split(' · ')[0].replace('/', ' → ')
    return next(r for r in e.lrfd['intervals'] if r['id'] == prefix)


def governing_stations(e):
    """Station rows k = 0..4: S shear, N, P, B longitudinal tension, M minimum transverse steel."""
    L = e.lrfd
    rows = [max(L['intervals'], key=lambda r: r['ratio'])]
    for group in REGIONS:
        rows.append(max((r for r in L['longitudinal'] if r['group'] == group), key=lambda r: r['ratio']))
    rows.append(max(L['intervals'], key=lambda r: r['min_ratio'])['minimum_segment'])
    return rows


def coverage_stations(e, shown):
    """Extra longitudinal rows that exercise the branches the governing stations do not: (tag, row) pairs.

    One row (the largest shear D/C) per distinct combination of method, flange cracking, minimum-transverse state,
    torsion, face and end-truncated window; the governing general-method rows are always included.
    """
    L = e.lrfd['longitudinal']
    shown_ids = {r['id'] for r in shown}

    def signature(r):
        w = r['window']
        return (r['method'], r['compression_face']['cracked'], r['minimum_transverse'], r['torsion_required'],
                r['face'], w['available_length_in'] < w['length_in'] - 1e-9, r['nu'] > 1e-10)

    best = {}
    for r in L:
        sig = signature(r)
        if sig not in best or r['shear_ratio'] > best[sig]['shear_ratio']:
            best[sig] = r
    picks = []
    general = [r for r in L if r['method'] == '5.7.3.4.2']
    if general:
        picks.append(('general, largest tension D/C', max(general, key=lambda r: r['ratio'])))
        picks.append(('general, largest shear D/C', max(general, key=lambda r: r['shear_ratio'])))
        picks.append(('general, largest strain', max(general, key=lambda r: r['epsilon'] or 0.)))
    for key, label in (('cracked', 'flange cracked'), ('minimum', 'no minimum steel'), ('torsion', 'torsion required')):
        hits = [r for r in L if (r['compression_face']['cracked'] is True if key == 'cracked' else
                                 r['minimum_transverse'] is False if key == 'minimum' else r['torsion_required'])]
        if hits:
            picks.append((label, max(hits, key=lambda r: r['shear_ratio'])))
    for sig, r in sorted(best.items(), key=lambda kv: str(kv[0])):
        picks.append((f'{"general" if sig[0] == "5.7.3.4.2" else "simplified"}, {sig[4]}'
                      f'{", cracked" if sig[1] else ""}{"" if sig[2] else ", no minimum steel"}'
                      f'{", torsion" if sig[3] else ""}{", end-truncated window" if sig[5] else ""}', r))
    out, seen = [], set()
    for label, r in picks:
        if r['id'] in seen or r['id'] in shown_ids:
            continue
        seen.add(r['id'])
        out.append((label, r))
    return out


# Actions fed through the tool's own section() so that branches no station of these caps reaches are still exercised:
# (label, station: 'mid' of the first hoop pair after mid-length or 'end' just inside the first hoop, action in kip and kip-ft)
SYNTHETIC = [
    ('tension cracks the flange', 'mid', dict(moment=-60., vu=250., nu=900., tu=0.)),
    ('torsion with tension', 'mid', dict(moment=-60., vu=120., nu=300., tu=400.)),
    ('torsion with compression', 'mid', dict(moment=150., vu=100., nu=-50., tu=300.)),
    ('V d_v above the moment', 'mid', dict(moment=5., vu=180., nu=40., tu=0.)),
    ('strain beyond 0.006', 'end', dict(moment=600., vu=60., nu=60., tu=0.)),
    ('compression: strain clamped at zero', 'mid', dict(moment=80., vu=60., nu=-400., tu=0.)),
]
THIN_RATE = 0.01          # in²/in: an adjacent interval with less than the minimum transverse steel


def synthetic_stations(e, physical):
    """(label, row) pairs from SYNTHETIC at the adjacent interval's own A_v/s and at THIN_RATE."""
    from pier_cap.transverse import shape_parameters
    from pier_cap.section_search import section
    p = e.case['inputs']
    runs = {r['id']: r for r in e.case['transverse_detail']['runs']}
    dev = {r['run']: r for r in e.lrfd['transverse_development']}
    mid = next(i for i in range(len(physical) // 2, len(physical) - 1) if physical[i]['kind'] == physical[i + 1]['kind'] == 'hoop')
    out = []
    for label, where, action in SYNTHETIC:
        i = mid if where == 'mid' else 0
        first, last = physical[i], physical[i + 1]
        x = first['station_in'] + (0.3 if where == 'mid' else 0.1)
        pitch = last['station_in'] - first['station_in']
        own_rate = 2 * BAR_AREA[min(first['bar'], last['bar'])] / pitch
        widths = [p['b'] - 2 * p['C_s'] - BAR_DIAMETER[b['bar']] - 2 * shape_parameters(runs[b['run']])['side_inset_in'] for b in (first, last)]
        heights = [p['h'] - p['C_t'] - p['C_b'] - BAR_DIAMETER[b['bar']] for b in (first, last)]
        ao = .85 * max(min(w * h for w, h in zip(widths, heights)), 1e-9)
        ph = 2 * (min(widths) + min(heights))
        closed = first['kind'] == last['kind'] == 'hoop'
        for rate, suffix in ((own_rate, ''), (THIN_RATE, ', thin hoops')):
            row = section(e, dict(action), x, e.lrfd['inventory'], physical, dev, rate, ao, ph, closed, None)
            row.pop('search_margins', None)
            row.update(id=f'{first["id"]}/{last["id"]} · synthetic {label}{suffix}', adjacent_rate=rate)
            out.append((f'synthetic: {label}{suffix}', row))
    return out


def branches_reached(rows):
    """Which branches of the station equations a set of tool rows exercises."""
    return {
        'simplified (β = 2, θ = 45°)': any(r['method'] == '5.7.3.4.1' for r in rows),
        'general method': any(r['method'] == '5.7.3.4.2' for r in rows),
        'flange cracked (ε doubled)': any(r['compression_face']['cracked'] is True for r in rows),
        'torsion investigated': any(r['torsion_required'] for r in rows),
        'torsion in the simplified method': any(r['torsion_required'] and r['method'] == '5.7.3.4.1' for r in rows),
        'no minimum transverse steel': any(r['minimum_transverse'] is False for r in rows),
        'strain beyond 0.006 (no resistance)': any((r['epsilon'] or 0.) > 0.006 for r in rows),
        'strain clamped at zero': any(r['epsilon_base'] is not None and r['epsilon_base'] < 0 for r in rows),
        'moment floor V d_v': any(r['moment_floor_kip_in'] > abs(r['moment']) * 12 for r in rows),
        'end-truncated window': any(r['window']['available_length_in'] < r['window']['length_in'] - 1e-9 for r in rows),
    }


def num(v, strict=True):
    """A number as the worksheet writes it: plain decimal, never exponent form (throwaway coverage blocks may be lax)."""
    text = repr(v) if isinstance(v, int) else repr(float(v))
    if strict and 'e' in text:
        raise ValueError(f'{v!r} would be written in exponent form; scale or round it')
    return text


ZERO_BELOW = {'M_st': 1e-9, 'N_st': 1e-11, 'T_st': 1e-6}     # numerical dust that cannot change a result or a branch
# Significant digits of the station vectors (default 10: relative error 5e-11). r_adj only decides the minimum-steel flags,
# never a continuous result, and its long decimals would run off the page.
SIGNIFICANT = {'r_adj': 8}

# name, display unit, caption; the row value comes from station_values
STATION_INPUTS = [
    ('x_st', 'in', 'station from the left cap end'),
    ('M_st', 'kip*ft', 'moment, signed (negative: top in tension)'),
    ('V_st', 'kip', 'shear'),
    ('N_st', 'kip', 'axial force (positive: tension)'),
    ('T_st', 'kip*ft', 'torque'),
    ('A_st', 'in**2', 'developed tension-half steel credited here (C5.7.3.5)'),
    ('A_dw', 'in**2', 'developed steel intersected by the shear window'),
    ('A_w45', 'in**2', 'hoop steel in the 45° window of length d_v'),
    ('L_w45', 'in', 'that window inside the cap'),
    ('A_wg', 'in**2', 'hoop steel in the window d_v cot θ'),
    ('L_wg', 'in', 'that window inside the cap'),
    ('r_adj', 'in**2/in', 'adjacent interval A_v/s'),
    ('A_cs', 'in**2', 'developed steel, compression half'),
    ('A_cc', 'in**2', 'concrete area, compression half'),
    ('s_xe', 'in', 'crack spacing parameter s_xe, 5.7.3.4.2-7'),
    ('A_o', 'in**2', 'torsion area A_o'),
    ('p_h', 'in', 'torsion perimeter p_h'),
]


def station_values(e, rows, physical, dv, l_cap):
    """Numbers of the station input vectors (each a list over the stations) read from the tool's rows."""
    out = {name: [] for name, _, _ in STATION_INPUTS}
    for row in rows:
        x = row['station_in']
        w45 = section_window(physical, x, dv, l_cap)
        wg = section_window(physical, x, row['general_window_length_in'], l_cap)
        rate = row['adjacent_rate'] if 'adjacent_rate' in row else interval_of(e, row)['rate_in2_in']
        cf = row['compression_face']
        values = dict(x_st=x, M_st=row['moment'], V_st=row['vu'], N_st=row['nu'], T_st=row['tu'], A_st=row['steel_area_in2'],
                      A_dw=row['developed_window_area_in2'], A_w45=w45['area_in2'], L_w45=w45['available_length_in'],
                      A_wg=wg['area_in2'], L_wg=wg['available_length_in'], r_adj=rate,
                      A_cs=cf['developed_steel_in2'], A_cc=cf['concrete_area_in2'], s_xe=row['sxe_in'],
                      A_o=row['ao_in2'], p_h=row['ph_in'])
        for name, v in values.items():
            v = float(v)
            if abs(v) < ZERO_BELOW.get(name, 0.0):
                v = 0.0
            out[name].append(float(f'{v:.{SIGNIFICANT.get(name, 10)}g}') + 0.0)
    return out


def vector_expr(values, unit, strict=True):
    return 'tr(row(' + ', '.join(num(v, strict) for v in values) + '))*' + unit


def station_input_items(values, strict=True):
    return [I(name, vector_expr(values[name], unit, strict), caption) for name, unit, caption in STATION_INPUTS]


def station_equation_groups():
    """The station equations; the same Items serve the worksheet and the branch-coverage run."""
    k = 'k'
    return [
        ('8.2 Torsion screen, longitudinal strain and cracking of the compression-half flange', [
            E('A_vmin', '0.0316*lambda_c*sqrt(fc/ksi)*ksi*b/min(fy, 100*ksi)', 'in**2/in', 'minimum transverse steel, 5.7.2.5-1'),
            E('f_ct', '0.213*lambda_c*sqrt(fc/ksi)*ksi', 'ksi', 'flange cracking stress, C5.4.2.7'),
            V('T_th', k, '0.25*phi_v*0.126*lambda_c*sqrt(fc/ksi)*ksi*(b*h)**2/(2*(b + h))'
                         '*sqrt(max(0, 1 - N_st[k]/(b*h)/(0.126*lambda_c*sqrt(fc/ksi)*ksi)))', 'kip*ft', 'torsion threshold, 5.7.2.1'),
            V('tor', k, 'IF(T_st[k] > T_th[k], 1, 0)', None, 'torsion investigated (1)'),
            V('V_ef', k, 'IF(tor[k] > 0, sqrt(V_st[k]**2 + (0.9*p_h[k]*T_st[k]/(2*A_o[k]))**2), V_st[k])', 'kip',
              'effective shear, 5.7.3.4.2-5'),
            V('M_e', k, 'max(abs(M_st[k]), V_st[k]*d_v)', 'kip*ft', 'moment for ε: not less than V d_v'),
            V('eps_b', k, '(M_e[k]/d_v + 0.5*N_st[k] + V_ef[k])/(Es*A_st[k])', None, 'longitudinal strain, 5.7.3.4.2-4'),
            V('ok45', 'k', 'IF(min(r_adj[k], A_w45[k]/L_w45[k]) >= A_vmin, 1, 0)', None, 'minimum steel in the 45° window (1)', show=False),
            V('okg', 'k', 'IF(min(r_adj[k], A_wg[k]/L_wg[k]) >= A_vmin, 1, 0)', None, 'minimum steel in the d_v cot θ window (1)', show=False),
            V('simp', k, 'IF(N_st[k] <= 10**-10*kip and (ok45[k] > 0 or h < 16*in), 1, 0)', None,
              'simplified β = 2, θ = 45° eligible (1), 5.7.3.4.1'),
            V('F_fl', k, '0.5*N_st[k] + V_ef[k] - abs(M_st[k])/d_v', 'kip', 'compression-half flange force, C5.7.3.4.2'),
            V('f_fl', k, 'F_fl[k]*E_c/(E_c*A_cc[k] + Es*A_cs[k])', 'ksi', 'flange tensile stress'),
            V('crk', k, 'IF(N_st[k] > 10**-10*kip and f_fl[k] >= f_ct, 1, 0)', None, 'flange cracked: ε doubles (1)'),
            V('eps_s', k, 'max(0, eps_b[k])*IF(crk[k] > 0, 2, 1)', None, 'strain ε_s'),
        ]),
        ('8.3 Shear resistance (LRFD 5.7.3.3, 5.7.3.4; FDOT SDG 4.1.4A intersected legs)', [
            V('beta_g', k, '4.8/(1 + 750*eps_s[k])*IF(okg[k] > 0, 1, 51/(39 + s_xe[k]/in))', None, 'general β, 5.7.3.4.2-1/-2'),
            V('theta_g', k, '(29 + 3500*eps_s[k])*deg', 'deg', 'general θ, 5.7.3.4.2-3'),
            V('cot_g', 'k', 'IF(theta_g[k] < 90*deg, 1/tan(theta_g[k]), 0)', None, 'cot θ, general (0 beyond 90°)', show=False),
            V('l_g', k, 'max(d_v*cot_g[k], 10**-8*in)', 'in', 'general window length d_v cot θ'),
            V('beta', k, 'IF(simp[k] > 0, 2, beta_g[k])', None, 'β used'),
            V('theta', k, 'IF(simp[k] > 0, 45*deg, theta_g[k])', 'deg', 'θ used'),
            V('cot_t', 'k', 'IF(theta[k] < 90*deg, 1/tan(theta[k]), 0)', None, 'cot θ used (0 beyond 90°)', show=False),
            V('okd', k, 'IF(simp[k] > 0 or eps_s[k] <= 0.006, 1, 0)', None, 'ε_s within 0.006 (1)'),
            V('V_c', k, '0.0316*lambda_c*beta[k]*sqrt(fc/ksi)*ksi*b*d_v', 'kip', 'concrete shear, 5.7.3.3-3'),
            V('A_w', k, 'IF(simp[k] > 0, A_w45[k], A_wg[k])', 'in**2', 'hoop steel in the window used'),
            V('L_w', k, 'IF(simp[k] > 0, L_w45[k], L_wg[k])', 'in', 'window inside the cap'),
            V('V_s', k, 'A_w[k]*min(fy, 100*ksi)', 'kip', 'hoop shear resistance'),
            E('V_lim', '0.25*fc*b*d_v', 'kip', 'upper limit 0.25 f′c b d_v'),
            V('V_r', k, 'IF(okd[k] > 0, phi_v*min(V_c[k] + V_s[k], V_lim), 0*kip)', 'kip', 'factored shear resistance'),
            V('DC_V', k, 'max(V_st[k]/max(V_r[k], 10**-9*kip), V_ef[k]/phi_v/V_lim)', None, 'shear D/C'),
            V('r_eff', k, 'A_w[k]/L_w[k]', 'in**2/in', 'intersected A_v/s in the window'),
            V('DC_Av', k, 'A_vmin/max(r_eff[k], 10**-9*in**2/in)', None, 'minimum transverse steel D/C'),
        ]),
        ('8.4 Longitudinal tension (LRFD 5.7.3.5-1, 5.7.3.6.3)', [
            V('V_cr', k, 'min(A_dw[k]*min(fy, 100*ksi), V_st[k]/phi_v)', 'kip', 'hoop credit, developed steel'),
            V('F_sh', k, 'max(0*kip, V_st[k]/phi_v - 0.5*V_cr[k])', 'kip', 'shear part'),
            V('F_to', k, 'IF(tor[k] > 0, 0.45*p_h[k]*T_st[k]/(2*A_o[k]*phi_v), 0*kip)', 'kip', 'torsion part'),
            V('phi_m', 'k', 'IF(tor[k] > 0, phi_v, phi_f)', None, 'φ on the moment term', show=False),
            V('phi_n', 'k', 'IF(tor[k] > 0, phi_v, phi_a)', None, 'φ on the axial term', show=False),
            V('F_mo', k, 'abs(M_st[k])/(phi_m[k]*d_v)', 'kip', 'moment term'),
            V('F_ax', k, '0.5*N_st[k]/phi_n[k]', 'kip', 'axial term'),
            V('F_di', k, 'cot_t[k]*sqrt(F_sh[k]**2 + F_to[k]**2)', 'kip', 'diagonal term'),
            V('F_req', k, 'max(0*kip, F_mo[k] + F_ax[k] + F_di[k])', 'kip', 'required tension'),
            V('F_cap', k, 'A_st[k]*fy', 'kip', 'tension capacity A_s f_y'),
            V('DC_L', k, 'F_req[k]/F_cap[k]', None, 'longitudinal tension D/C'),
        ]),
    ]


def coverage_blocks(values, count):
    """Throwaway blocks: the same station Items for `count` extra rows (never written to the worksheet)."""
    blocks = [ROW(R('k', 0, count - 1)), EQ(*station_input_items(values, strict=False))]
    for _, items in station_equation_groups():
        blocks.append(EQ(*items))
    return blocks


# ----------------------------------------------------------------------------- inputs
def input_values(e):
    p, s = e.case['inputs'], settings(e.case)
    values = {name: p[name] for name in ('b', 'h', 'C_t', 'C_b', 'C_s', 'fc', 'fy', 'Es', 'phi_f', 'phi_v', 'gamma_e',
                                           'Mu_N', 'Mu_P', 'Mu_B', 'MI_N', 'MI_P', 'MI_B',
                                           'Bar_N1', 'n_N1', 'Bar_N2', 'n_N2', 'Bar_N3', 'n_N3', 'Bar_P', 'n_P1', 'n_P2',
                                           'Bar_B', 'n_B1', 'n_B2', 'Bar_v', 'n_loop', 'Bar_skin', 'n_skin')}
    values.update(lambda_c=s['density_factor'], phi_a=s['phi_axial'], s_proj=s['shrinkage_project_spacing_in'],
                  L_cap=e.value('L_cap', 'in'))
    for name in ('y_N1', 'y_N2', 'y_N3', 'y_P1', 'y_P2', 'y_B1', 'y_B2', 'SP_N', 'SP_P', 'SP_B', 'SP_skin'):
        values[name] = e.value(name, 'in')
    return values


INPUT_GROUPS = [
    ('Geometry and materials', [
        ('b', 'in', 'cap width'), ('h', 'in', 'cap depth'), ('C_t', 'in', 'top clear cover to the hoop'),
        ('C_b', 'in', 'bottom clear cover to the hoop'), ('C_s', 'in', 'side clear cover to the hoop'),
        ('fc', 'ksi', 'concrete strength'), ('fy', 'ksi', 'steel yield strength'), ('Es', 'ksi', 'steel modulus'),
        ('phi_f', None, 'flexure φ'), ('phi_v', None, 'shear φ'), ('gamma_e', None, 'crack-control exposure factor'),
        ('lambda_c', None, 'density factor'), ('phi_a', None, 'axial φ, 5.7.3.5'),
        ('L_cap', 'in', 'cap length (C005)'), ('s_proj', 'in', 'project spacing limit, face steel')]),
    ('Actions (C005 inputs from the analysis envelope)', [
        ('Mu_N', 'kip*ft', 'Strength moment, N'), ('MI_N', 'kip*ft', 'Service I moment, N'),
        ('Mu_P', 'kip*ft', 'Strength moment, P'), ('MI_P', 'kip*ft', 'Service I moment, P'),
        ('Mu_B', 'kip*ft', 'Strength moment, B'), ('MI_B', 'kip*ft', 'Service I moment, B')]),
    ('Reinforcement', [
        ('Bar_N1', None, 'top row 1 bar'), ('n_N1', None, 'top row 1 count'), ('Bar_N2', None, 'top row 2 bar'),
        ('n_N2', None, 'top row 2 count'), ('Bar_N3', None, 'top row 3 bar'), ('n_N3', None, 'top row 3 count'),
        ('Bar_P', None, 'continuous bottom bar'), ('n_P1', None, 'bottom row 1 count'), ('n_P2', None, 'bottom row 2 count'),
        ('Bar_B', None, 'added span bar'), ('n_B1', None, 'added bars, row 1'), ('n_B2', None, 'added bars, row 2'),
        ('Bar_v', None, 'hoop bar'), ('n_loop', None, 'hoop loops'), ('Bar_skin', None, 'skin bar'),
        ('n_skin', None, 'skin bars per side')]),
    ('Fitted actual-cage coordinates (replace the reference cover formulas of the report)', [
        ('y_N1', 'in', 'top row 1 from the top face'), ('y_N2', 'in', 'top row 2 from the top face'),
        ('y_N3', 'in', 'top row 3 from the top face'), ('y_P1', 'in', 'bottom row 1 from the bottom face'),
        ('y_P2', 'in', 'bottom row 2 from the bottom face'), ('y_B1', 'in', 'added row 1 from the bottom face'),
        ('y_B2', 'in', 'added row 2 from the bottom face'), ('SP_N', 'in', 'top bar spacing, fitted'),
        ('SP_P', 'in', 'bottom bar spacing at piles, fitted'), ('SP_B', 'in', 'bottom bar spacing, fitted'),
        ('SP_skin', 'in', 'skin bar spacing, fitted')]),
]
INPUT_UNITS = {name: unit for _, group in INPUT_GROUPS for name, unit, _ in group}


def input_blocks(values):
    blocks = []
    for title, group in INPUT_GROUPS:
        items = [I(name, num(values[name]) + (f'*({unit})' if unit else ''), caption) for name, unit, caption in group]
        blocks.append(INPUTS(title, items))
    return blocks


def check_display_units(blocks, env):
    """Every displayed unit is dimensionally compatible with the value it is shown in (else Mathcad would flag the result)."""
    for block in blocks:
        for item in (block.payload if block.kind in ('eqs', 'row', 'inputs') else []):
            if not item.unit or item.kind not in ('eq', 'idef', 'show'):
                continue
            value = ev(item.tree, env) if item.kind == 'show' else env[item.name]
            for v in (value if isinstance(value, list) else [value]):
                _to(v, item.unit.replace('^', '**'))


def check_inputs(blocks, values):
    """Every worksheet input equals the tool input after unit conversion."""
    env, seen = {}, set()
    for block in blocks:
        if block.kind == 'inputs':
            for item in block.payload:
                env[item.name] = ev(item.tree, env)
                if item.name not in INPUT_UNITS:         # interval and hook data are compared through their results
                    continue
                unit = INPUT_UNITS[item.name]
                mine = _to(env[item.name], unit.replace('^', '**')) if unit else env[item.name].v
                assert abs(mine - values[item.name]) <= 1e-12 * max(1.0, abs(values[item.name])), \
                    (item.name, mine, values[item.name])
                seen.add(item.name)
    missing = set(INPUT_UNITS) - seen
    assert not missing, f'inputs missing from the worksheet: {sorted(missing)}'


# ----------------------------------------------------------------------------- the worksheet
def sheet_head(ctx):
    """Title through Section 7 (shear depth)."""
    e, rep, key = ctx.e, ctx.report, ctx.cap['key']
    xml = e.case['analysis']['xml_audit']
    blocks = [
        Block('title', f'{ctx.cap["label"]} — Distilled Cap Design Calculation'),
        P('Project: D2 I-95 Pedestrian Bridge.'),
        P(f'Distilled from {rep["file"]} (generated {rep["stamp"]}); same case (canonical SHA-256 {rep["case_sha"][:12]}) and '
          f'C005 formula set ({rep["formula_sha"][:12]}) as the report; FBMP {xml["filename"]} ({xml["sha256"][:12]}); '
          f'cap notebook package {ctx.revision}.'),
        P('Codes: AASHTO LRFD Bridge Design Specifications, 10th edition (2024); FDOT Structures Design Guidelines, January 2026, '
          '4.1.4A–C; inherited C005 sectional relations.'),
        P(f'Tool status: {e.status}. Inputs are highlighted yellow; key results are boxed.'),

        H1('1. Scope'),
        BUL(['Computed here: sectional flexure, minimum steel, strain and Service I crack control in regions N (top steel), P (bottom '
             'steel at the piles) and B (bottom steel with the added span bars); the shear depth; actual-cage shear, longitudinal '
             'tension, torsion screen and minimum transverse steel at the governing stations found by the tool\'s station search; '
             'the governing transverse spacing; face shrinkage and temperature steel; skin steel; and the governing hook development.',
             'Taken from the tool and not recomputed: the station search itself, the intersected-leg window areas and the developed '
             '(credited) steel areas (shown as inputs), the detailing and geometry flags, transverse anchorage, the end grid and the '
             'D-regions.',
             'Service III (D-007) and fatigue remain pending.']),

        H1('2. Inputs'),
        *input_blocks(ctx.values),
        EQ(D('A_bar', 'tr(row(0, 0, 0, 0.11, 0.20, 0.31, 0.44, 0.60, 0.79, 1.00, 1.27, 1.56))*in**2', 'bar area; index = bar number'),
           D('d_bar', 'tr(row(0, 0, 0, 0.375, 0.500, 0.625, 0.750, 0.875, 1.000, 1.128, 1.270, 1.410))*in',
             'bar diameter; index = bar number')),
    ]
    if WITH_FIGURES:
        blocks += [
            H1('3. Figures'),
            FIG(f'{key}_elevation', 'Figure 1. Cap elevation: piles, bearings, transverse runs, added span bars and the governing '
                                    'stations S (shear) and N, P, B (longitudinal tension) used in Section 8.', width=460),
            FIG(f'{key}_section', 'Figure 2. Cross-section between piles: continuous top (N) and bottom (P) steel, added span bars (B), '
                                  'skin bars and the hoop.', width=350),
        ]
    blocks += [
        H1('4. Steel areas and effective depths (C005)'),
        EQ(E('d_vbar', 'd_bar[Bar_v]', 'in', 'hoop bar diameter'),
           E('As_N', 'n_N1*A_bar[Bar_N1] + n_N2*A_bar[Bar_N2] + n_N3*A_bar[Bar_N3]', 'in**2', 'top steel, N'),
           E('As_P', '(n_P1 + n_P2)*A_bar[Bar_P]', 'in**2', 'bottom steel at the piles, P'),
           E('As_B', 'As_P + (n_B1 + n_B2)*A_bar[Bar_B]', 'in**2', 'bottom steel with the added span bars, B'),
           E('Av', '2*n_loop*A_bar[Bar_v]', 'in**2', 'hoop area per set'),
           E('As_side', 'n_skin*A_bar[Bar_skin]', 'in**2', 'skin steel, one side'),
           E('dc_N', '(n_N1*A_bar[Bar_N1]*y_N1 + n_N2*A_bar[Bar_N2]*y_N2 + n_N3*A_bar[Bar_N3]*y_N3)/max(As_N, 10**-6*in**2)',
             'in', 'centroid of N from the top face'),
           E('dc_P', '(n_P1*A_bar[Bar_P]*y_P1 + n_P2*A_bar[Bar_P]*y_P2)/max(As_P, 10**-6*in**2)', 'in',
             'centroid of P from the bottom face'),
           E('dc_B', '(As_P*dc_P + n_B1*A_bar[Bar_B]*y_B1 + n_B2*A_bar[Bar_B]*y_B2)/max(As_B, 10**-6*in**2)', 'in',
             'centroid of B from the bottom face')),
        P('Regions r: 0 = N (top steel), 1 = P (bottom steel at piles), 2 = B (bottom steel between piles, added bars).'),
        ROW(R('r', 0, 2), D('Region', 'tr(row("N top", "P bottom at piles", "B bottom between piles"))')),
        ROW(D('A_s', 'tr(row(As_N, As_P, As_B))'), D('d_c', 'tr(row(dc_N, dc_P, dc_B))')),
        ROW(D('M_u', 'tr(row(Mu_N, Mu_P, Mu_B))'), D('M_I', 'tr(row(MI_N, MI_P, MI_B))')),
        ROW(D('S_p', 'tr(row(SP_N, SP_P, SP_B))')),
        EQ(V('d', 'r', 'h - d_c[r]', 'in', 'effective depth')),

        H1('5. Flexure and minimum reinforcement (LRFD 5.6.3, 5.6.7)'),
        EQ(E('alpha_1', 'max(0.75, 0.85 - 0.02*max(fc/ksi - 10, 0))', None, 'stress block factor α1'),
           E('beta_1', 'max(0.65, 0.85 - 0.05*max(fc/ksi - 4, 0))', None, 'stress block factor β1'),
           E('f_r', '0.24*sqrt(fc/ksi)*ksi', 'ksi', 'modulus of rupture'),
           E('I_g', 'b*h**3/12', 'in**4', 'gross moment of inertia'),
           E('y_t', 'h/2', 'in', 'centroid to the tension face'),
           E('M_cr', 'f_r*I_g/y_t', 'kip*ft', 'cracking moment'),
           E('M_crm', '1.6*0.67*M_cr', 'kip*ft', 'minimum-steel target, 1.6 · 0.67 M_cr'),
           V('a', 'r', 'A_s[r]*fy/(alpha_1*fc*b)', 'in', 'stress block depth'),
           V('c', 'r', 'a[r]/beta_1', 'in', 'neutral axis depth'),
           V('M_n', 'r', 'A_s[r]*fy*(d[r] - a[r]/2)', 'kip*ft', 'nominal moment'),
           V('M_r', 'r', 'phi_f*M_n[r]', 'kip*ft', 'factored resistance'),
           V('A_req', 'r', 'M_u[r]/(phi_f*fy*(d[r] - a[r]/2))', 'in**2', 'steel required for M_u'),
           V('M_min', 'r', 'min(M_crm, 1.33*M_u[r])', 'kip*ft', 'minimum factored resistance'),
           V('eps_t', 'r', '0.003*(d[r] - c[r])/max(c[r], 10**-6*in)', None, 'net tensile strain'),
           V('DC_flex', 'r', 'M_u[r]/M_r[r]', None, 'flexure, M_u / M_r'),
           V('DC_min', 'r', 'M_min[r]/M_r[r]', None, 'minimum steel, M_min / M_r'),
           V('DC_eps', 'r', '0.005/eps_t[r]', None, 'tension-controlled, 0.005 / ε_t')),

        H1('6. Service I crack control (LRFD 5.6.7)'),
        EQ(E('E_c', '120000*0.145**2*(fc/ksi)**0.33*ksi', 'ksi', 'concrete modulus (C005)'),
           E('n_m', 'round(Es/E_c, 2)', None, 'modular ratio, two decimals'),
           E('f_slim', '0.8*fy', 'ksi', 'service steel stress limit'),
           V('nA', 'r', 'n_m*A_s[r]', 'in**2', 'transformed steel'),
           V('c_cr', 'r', '(-nA[r] + sqrt(nA[r]**2 + 2*b*d[r]*nA[r]))/b', 'in', 'cracked neutral axis'),
           V('I_cr', 'r', 'b*c_cr[r]**3/3 + nA[r]*(d[r] - c_cr[r])**2', 'in**4', 'cracked moment of inertia'),
           V('S_s', 'r', 'I_cr[r]/(d[r] - c_cr[r])', 'in**3', 'section modulus to the steel'),
           V('beta_s', 'r', '1 + d_c[r]/(0.7*(h - d_c[r]))', None, 'β_s'),
           V('f_sI', 'r', 'M_I[r]*n_m/S_s[r]', 'ksi', 'Service I steel stress'),
           V('s_I', 'r', 'IF(f_sI[r] > 0*ksi, 700*gamma_e/(beta_s[r]*f_sI[r]/ksi)*in - 2*d_c[r], 1000000*in)', 'in',
             'allowable bar spacing, 5.6.7-1'),
           V('DC_I', 'r', 'max(f_sI[r]/f_slim, S_p[r]/s_I[r])', None, 'larger of stress / limit and spacing / allowable')),
        N('Service III is not applicable (D-007); fatigue is pending (no confirmed fatigue loads).'),

        H1('7. Shear depth'),
        EQ(E('d_min', 'min(d[0], d[1], d[2])', 'in', 'least effective depth'),
           E('d_va', 'min(d[0] - a[0]/2, d[1] - a[1]/2, d[2] - a[2]/2)', 'in', 'least d - a/2'),
           E('d_v', 'max(0.9*d_min, 0.72*h, d_va)', 'in', 'effective shear depth (C005)', key=True)),
    ]
    return blocks


def echo_lines(ctx, rows):
    lines = []
    for tag, label, row in zip(TAGS, LABELS, rows):
        iv = row['id'].split(' · ')[0]
        lines.append(f'{label}: {iv} · C{row["combination"]} E{row["element"]} · {row["state"]} · x = {row["station_in"]:.3f} in · {row["face"]} face')
    return lines


def sheet_stations(ctx, rows, values):
    """Section 8: the actual-cage section checks at the five governing stations."""
    blocks = [
        H1('8. Actual-cage section checks at the governing stations'),
        P('Stations k: 0 = S, the shear-governing point; 1, 2, 3 = N, P, B, the longitudinal-tension points of each region; '
          '4 = M, the least minimum transverse steel. Each line gives the interval, combination C, element E, load state, '
          'station and tension face; the equations recompute every check there.'),
        BUL(echo_lines(ctx, rows)),
        ROW(R('k', 0, 4), D('St', 'tr(row(' + ', '.join(f'"{t}"' for t in LABELS) + '))')),
        H2('8.1 Station inputs (from the tool)'),
        EQ(*station_input_items(values)),
    ]
    for title, items in station_equation_groups():
        blocks += [H2(title), EQ(*items)]
    blocks += [
        H2('8.5 Station results'),
        N('Columns, left to right: station; V_r; shear D/C; required tension; tension capacity; tension D/C.'),
        ROW(S('St', None, '', rows=5, width=84), S('V_r', 'kip', rows=5, width=72), S('DC_V', None, rows=5, width=62),
            S('F_req', 'kip', rows=5, width=72), S('F_cap', 'kip', rows=5, width=72), S('DC_L', None, rows=5, width=62)),
    ]
    return blocks


def sheet_tail(ctx, spacing, faces, hook):
    e = ctx.e
    skin_required = bool(e.value('Skin_required'))
    n = len(faces['rows'])
    blocks = [
        H1('9. Transverse spacing at the governing interval'),
        P(f'Governing interval {spacing["interval"]["id"]}; V_u and V_eff are the largest at its search stations.'),
        INPUTS('Interval data (from the tool)', [
            I('s_iv', spacing['s_iv'], 'hoop pitch'), I('w_iv', spacing['w_iv'], 'across-leg spacing'),
            I('r_iv', spacing['r_iv'], 'A_v/s of the interval'), I('V_ivmax', spacing['V_ivmax'], 'largest V_u'),
            I('Vef_ivmax', spacing['Vef_ivmax'], 'largest V_eff')]),
        EQ(E('v_iv', 'Vef_ivmax/(phi_v*b*d_v)', 'ksi', 'shear stress, V_eff'),
           E('s_lim', 'IF(v_iv < 0.125*fc, min(0.8*d_v, 24*in), min(0.4*d_v, 12*in))', 'in', 'maximum spacing, 5.7.2.6'),
           E('v_o', 'V_ivmax/(phi_v*b*d_v)', 'ksi', 'shear stress, V_u'),
           E('v_o1', '0.08*sqrt(fc/ksi)*ksi', 'ksi', 'stress below which the across-leg limit is 42 in'),
           E('v_o2', '0.16*sqrt(fc/ksi)*ksi', 'ksi', 'stress below which the limit is d_v or 24 in'),
           E('w_mid', 'IF(v_o <= v_o2, min(d_v, 24*in), min(0.5*d_v, 12*in))', 'in', 'limit above the 42 in range'),
           E('w_lim', 'IF(v_o <= v_o1, 42*in, w_mid)', 'in', 'across-leg limit, SDG 4.1.4C'),

           E('DC_sp', 'max(s_iv/s_lim, w_iv/w_lim, A_vmin/r_iv)', None, 'pitch, across-leg spacing and minimum steel')),

        H1('10. Face shrinkage and temperature steel, and skin steel'),
        EQ(E('A_tr0', '1.30*b*h/(2*(b + h)*min(fy, 75*ksi))*ksi*in/ft', 'in**2/ft', '5.10.6-1 (b, h in inches, f_y in ksi)'),
           E('A_tr', 'min(max(A_tr0, 0.11*in**2/ft), 0.60*in**2/ft)', 'in**2/ft', 'required steel per face, 0.11 to 0.60'),
           E('s_code', 'IF(min(b, h) > 36*in, 12*in, max(18*in, 3*min(b, h)))', 'in', 'code spacing limit'),
           E('s_tlim', 'min(s_code, s_proj)', 'in', 'adopted spacing limit')),
        P(f'Faces and directions that the tool checks ({n}); index f.'),
        ROW(R('f', 0, n - 1)),
        ROW(D('Face', faces['Face']), I('A_tp', faces['A_tp'], ''), I('s_tp', faces['s_tp'], '')),
        EQ(V('DC_ta', 'f', 'A_tr/A_tp[f]', show=False), V('DC_ts', 'f', 's_tp[f]/s_tlim', show=False)),
        N('Columns, left to right: face and direction; provided steel; bar spacing; steel D/C; spacing D/C.'),
        ROW(S('Face', None, '', rows=n, width=118), S('A_tp', 'in**2/ft', rows=n, width=86), S('s_tp', 'in', rows=n, width=62),
            S('DC_ta', None, rows=n, width=62), S('DC_ts', None, rows=n, width=62)),
    ]
    if faces['excluded']:
        blocks.append(N('Not checked: ' + ' '.join(faces['excluded'])))
    if skin_required:
        blocks += [
            EQ(E('Skin_req', 'IF(max(d[0], d[1], d[2]) >= 3*ft, 1, 0)', None, 'skin steel required (1): d ≥ 3 ft, 5.6.7'),
               E('d_pmax', 'max(d[1], d[2])', 'in', 'larger positive-region depth'),
               E('As_skN', 'IF(Skin_req > 0, max(0*in**2, min(0.012*(d[0]/in - 30)*(in**2/ft)*(d[0]/2), As_N/4)), 0*in**2)',
                 'in**2', 'skin steel required, N'),
               E('As_skP', 'IF(Skin_req > 0, max(0*in**2, min(0.012*(d_pmax/in - 30)*(in**2/ft)*(d_pmax/2), max(As_P, As_B)/4)), '
                           '0*in**2)', 'in**2', 'skin steel required, P and B'),
               E('As_skq', 'max(As_skN, As_skP)', 'in**2', 'required, one half-side'),
               E('As_skh', 'As_side/2', 'in**2', 'provided, one half-side'),
               E('s_sk', 'min(d_min/6, 12*in)', 'in', 'maximum skin-bar spacing'),
               E('DC_sk_a', 'As_skq/As_skh', None, 'skin steel area D/C'),
               E('DC_sk_s', 'SP_skin/s_sk', None, 'skin bar spacing D/C')),
        ]
    else:
        dmax = max(e.value(f'd_{x}', 'in') for x in REGIONS)
        blocks += [
            EQ(E('Skin_req', 'IF(max(d[0], d[1], d[2]) >= 3*ft, 1, 0)', None, 'skin steel required (1): d ≥ 3 ft, 5.6.7'),
               E('s_sk', 'min(d_min/6, 12*in)', 'in', 'maximum skin-bar spacing, if required')),
            N(f'Skin steel not required (largest effective depth {dmax:.2f} in < 36 in).'),
        ]

    blocks.append(H1('11. Hook development of the governing added span bar'))
    if hook:
        blocks += [
            P(f'Bar {hook["id"]} (#{hook["bar"]}, {hook["kind"]}): largest hook length over half its span, 5.10.8.2.4a.'),
            INPUTS('Bar data (from the tool)', [
                I('d_bh', hook['d_bh'], 'bar diameter'), I('A_bh', hook['A_bh'], 'bar area'), I('r_h', hook['r_h'], 'hook bend radius'),
                I('c_bh', hook['c_bh'], 'cover or half spacing, c_b'), I('lam_rl', hook['lam_rl'], 'location factor'),
                I('lam_cf', hook['lam_cf'], 'coating factor'), I('L_bh', hook['L_bh'], 'bar length between its hooks')]),
            EQ(E('f_h', 'min(A_bh*fy, d_bh*r_h*0.45*fc)', 'kip', 'bar force at the hook node'),
               E('l_db', '0.17*d_bh*((fy - f_h/A_bh)/ksi/(1.97*lambda_c*(fc/ksi)**0.25))**2', 'in', 'basic length, 5.10.8.2.4a-1'),
               E('lam_c', 'max(0.3, min(1, d_bh/c_bh))', None, 'confinement factor'),
               E('l_ds', 'l_db*min(1.7, lam_rl*lam_cf)*lam_c', 'in', 'straight part'),
               E('l_dh', 'max(8*d_bh, 6*in, l_ds + r_h + d_bh/2)', 'in', 'required hook development'),
               E('DC_hk', 'l_dh/(L_bh/2)', None, 'required / half the bar length')),
        ]
    else:
        blocks.append(N('No added span bars: hook development does not apply.'))

    summary = [S('tr(Region)', None, 'demand / capacity; 1.0 or less passes; rows by region'),
               S('tr(DC_flex)', None, 'flexure'), S('tr(DC_min)', None, 'minimum steel'),
               S('tr(DC_eps)', None, 'tension-controlled strain'), S('tr(DC_I)', None, 'Service I crack control'),
               E('DC_shear', 'DC_V[0]', None, 'shear at S'), E('DC_LN', 'DC_L[1]', None, 'longitudinal tension at N'),
               E('DC_LP', 'DC_L[2]', None, 'longitudinal tension at P'), E('DC_LB', 'DC_L[3]', None, 'longitudinal tension at B'),
               E('DC_minAv', 'DC_Av[4]', None, 'minimum transverse steel at M'),
               E('DC_tamax', 'max(DC_ta)', None, 'face steel area, largest'), E('DC_tsmax', 'max(DC_ts)', None, 'face bar spacing, largest')]
    face_names = ['DC_tamax', 'DC_tsmax']
    if skin_required:
        summary += [E('DC_skin', 'max(DC_sk_a, DC_sk_s)', None, 'skin steel')]
        face_names.append('DC_skin')
    if hook:
        face_names.append('DC_hk')
    summary += [E('DC_sect', 'max(DC_flex, DC_min, DC_eps, DC_I, DC_shear, DC_LN, DC_LP, DC_LB)', None, 'flexure, Service I, shear, tension'),
                E('DC_det', 'max(DC_minAv, DC_sp, ' + ', '.join(face_names) + ')', None, 'transverse steel and spacing, faces' + (', skin' if skin_required else '') + (', hook' if hook else '')),
                E('DC_dist', 'max(DC_sect, DC_det)', None, 'largest of the distilled ratios', key=True),
                E('Status', 'IF(DC_dist <= 1, "PASS", "FAIL")', None, 'distilled numerical checks only', key=True)]
    blocks += [H1('12. Summary of checks'), EQ(*summary)]
    blocks += [N(text) for text in summary_notes(e)]
    return blocks


# ----------------------------------------------------------------------------- tool facts for the sheet
def spacing_data(e):
    L = e.lrfd
    iv = max(L['intervals'], key=lambda r: r['spacing_ratio'])
    prefix = iv['id'].replace(' → ', '/')
    rows = [r for r in L['longitudinal'] if r['id'].split(' · ')[0] == prefix]
    unitnum = lambda v, unit: num(v) + '*' + unit
    return dict(interval=iv, rows=rows,
                s_iv=unitnum(iv['pitch_in'], 'in'), w_iv=unitnum(iv['across_in'], 'in'), r_iv=unitnum(iv['rate_in2_in'], '(in**2/in)'),
                V_ivmax=unitnum(max(r['vu'] for r in rows), 'kip'), Vef_ivmax=unitnum(max(r['veff'] for r in rows), 'kip'))


FACE_SHORT = {'Longitudinal': 'long.', 'Transverse': 'trans.', 'Vertical': 'vert.', 'Horizontal': 'horiz.'}


def face_data(e):
    all_rows = e.lrfd['faces']
    rows = [r for r in all_rows if r.get('included', True) is not False]
    excluded = []
    for r in all_rows:
        if r.get('included', True) is False:
            first = r['notes'].split('. ')[0].rstrip('.')
            excluded.append(f'{r["face"]} {r["direction"].lower()} face: {first[0].lower()}{first[1:]}.')
    col = lambda vals, unit: 'col(' + ', '.join(num(float(f'{v:.10g}')) for v in vals) + ')*' + unit      # tall: eleven rows do not fit a line
    labels = [f'{r["face"]} {FACE_SHORT[r["direction"]]}' for r in rows]
    return dict(rows=rows, excluded=excluded, Face='col(' + ', '.join(f'"{t}"' for t in labels) + ')',
                A_tp=col([r['provided_in2_ft'] for r in rows], 'in**2/ft'), s_tp=col([r['spacing_in'] for r in rows], 'in'))


def hook_data(e):
    hooks = [b for b in e.lrfd['inventory'] if b['additional']]
    if not hooks:
        return None
    b = max(hooks, key=lambda b: b['required_in'] / ((b['right_in'] - b['left_in']) / 2))
    unitnum = lambda v, unit=None: num(v) + ('*' + unit if unit else '')
    assert b['cb_in'] > 0, 'confinement factor needs c_b'
    return dict(raw=b, id=b['id'], bar=b['bar'], kind=b['kind'], d_bh=unitnum(b['db'], 'in'), A_bh=unitnum(b['area'], 'in**2'),
                r_h=unitnum(b['hook_radius'], 'in'), c_bh=unitnum(b['cb_in'], 'in'), lam_rl=unitnum(b['location_factor']),
                lam_cf=unitnum(b['coating_factor']), L_bh=unitnum(b['right_in'] - b['left_in'], 'in'))


DISTILLED = ('Chk_flex_', 'Chk_min_', 'Chk_strain_', 'Chk_I_', 'Chk_long_', 'Chk_shear_', 'Chk_spacing_', 'Chk_skin_',
             'Chk_shrink_', 'Chk_actual_', 'Status_hook_development')
PENDING_FAMILIES = [
    ('Service III and fatigue', lambda k: k in ('Status_III', 'Status_fatigue')),
    ('FDOT covers', lambda k: k.startswith('Chk_fdot_cover')),
    ('D-regions, end regions and the end grid',
     lambda k: k in ('Status_actual_review', 'Status_lrfd_regions', 'Status_lrfd_end_regions', 'Status_end_grid_anchorage')),
    ('actual-cage prerequisites behind the distilled checks (anchorage and closure, splices, load path)',
     lambda k: k.startswith(('Chk_actual_', 'Chk_shear_', 'Chk_long_', 'Chk_spacing_', 'Chk_torsteel_', 'Chk_shrink_',
                             'Chk_hoop_clear_', 'Chk_drawn_hoop_legs_', 'Status_hook_development',
                             'Status_transverse_development_', 'Status_actual_torsion'))),
]


def summary_notes(e):
    """Notes drawn from the tool's check register (what the worksheet does not recompute)."""
    checks = e.checks
    failed = [c for c in checks if 'FAIL' in c.status and not c.key.startswith(DISTILLED) and c.key != 'Status_overall']
    groups = {}
    for c in failed:
        groups.setdefault(re.sub(r'R\d+', 'R*', c.key), []).append(c)
    parts = []
    for group in groups.values():
        first = group[0]
        label = first.label.strip()
        if len(group) > 1:
            runs = ', '.join(re.search(r'R\d+', c.key).group(0) for c in group)
            label = re.sub(r'R\d+', runs, label, count=1)
        text = first.basis.splitlines()[0].strip()
        parts.append(f'{label}: {text}')
    notes = []
    if parts:
        notes.append('Failing checks not recomputed here (tool): ' + ' '.join(p if p.endswith('.') else p + '.' for p in parts))
    else:
        notes.append('No tool check outside the distilled set fails.')
    mine = []
    for c in checks:
        if 'FAIL' in c.status and c.key.startswith(DISTILLED):
            where = re.search(r'Governing: (.*?);? ratio', c.basis)
            mine.append(f'{c.label.strip()}: D/C {c.ratio:.3f}' + (f', {where.group(1)}' if where else '') + '.')
    if mine:
        notes[0] += ' Recomputed here and failing (tool): ' + ' '.join(mine)
    pending = [c for c in checks if 'PENDING' in c.status or 'CONDITIONAL' in c.status]
    claimed, counts = set(), []
    for name, test in PENDING_FAMILIES:
        hits = [c for c in pending if c.key not in claimed and test(c.key)]
        claimed.update(c.key for c in hits)
        if hits:
            counts.append(f'{len(hits)} {name}')
    rest = [c for c in pending if c.key not in claimed]
    if rest:
        counts.append(f'{len(rest)} other')
    notes.append(f'The tool reports {len(pending)} PENDING items: ' + '; '.join(counts) + '.')
    flags = [c for c in checks if 'PASS' in c.status and 'FAIL' not in c.status and not c.key.startswith(DISTILLED)
             and not c.key.startswith('Status_')]
    notes.append(f'Detailing and geometry flags: {len(flags)} pass, as reported by the tool.')
    return notes


# ----------------------------------------------------------------------------- verification against the tool
def comparisons(env, ctx):
    """(label, worksheet value, tool value) for every quantity both calculations hold."""
    e = ctx.e
    out = []

    def tool(name):
        return e.value(name, UNIT[name])

    def mc(value, name):
        unit = UNIT[name]
        return _to(value, None if unit is None else unit.replace('^', '**'))

    for mc_name, name in (('alpha_1', 'alpha_1'), ('beta_1', 'beta_1'), ('f_r', 'fr'), ('I_g', 'Ig'), ('M_cr', 'Mcr'),
                          ('M_crm', 'Mmin_cr'), ('E_c', 'Ec'), ('n_m', 'n_mod'), ('f_slim', 'fs_I_limit'), ('d_v', 'dv'),
                          ('d_vbar', 'd_vbar'), ('Av', 'Av'), ('As_side', 'As_side')):
        out.append((mc_name, mc(env[mc_name], name), tool(name)))
    for n in BAR_AREA:                                           # the bar tables of the worksheet are the tool's
        out.append((f'A_bar[{n}]', _to(env['A_bar'][n], 'in**2'), BAR_AREA[n]))
        out.append((f'd_bar[{n}]', _to(env['d_bar'][n], 'in'), BAR_DIAMETER[n]))
    for i, x in enumerate(REGIONS):
        for mc_name, name in (('A_s', f'As_{x}'), ('d_c', f'dc_{x}'), ('d', f'd_{x}'), ('a', f'a_{x}'), ('c', f'c_{x}'),
                              ('M_n', f'Mn_{x}'), ('M_r', f'Mr_{x}'), ('A_req', f'Asreq_{x}'), ('M_min', f'Mmin_{x}'),
                              ('eps_t', f'eps_t_{x}'), ('nA', f'nAs_{x}'), ('c_cr', f'ccr_{x}'), ('I_cr', f'Icr_{x}'),
                              ('S_s', f'Ss_{x}'), ('beta_s', f'bs_{x}'), ('f_sI', f'fs_I_{x}'), ('s_I', f'SI_{x}')):
            out.append((f'{mc_name}[{i}] {x}', mc(env[mc_name][i], name), tool(name)))
    ratio = {c.key: c.ratio for c in e.checks}
    for i, x in enumerate(REGIONS):
        for mc_name, key in (('DC_flex', 'Chk_flex_'), ('DC_min', 'Chk_min_'), ('DC_eps', 'Chk_strain_'), ('DC_I', 'Chk_I_')):
            out.append((f'{mc_name}[{i}] {x}', env[mc_name][i].v, ratio[key + x]))

    rows = ctx.rows
    out += station_comparisons(env, ctx, rows, TAGS, ratio_rows=(1, 2, 3))
    iv = interval_of(e, rows[4])
    out.append(('DC_Av[4] vs interval min_ratio', env['DC_Av'][4].v, iv['min_ratio']))
    for k in (1, 2, 3):
        out.append((f'DC_L[{k}] vs check {TAGS[k]}', env['DC_L'][k].v, ratio['Chk_long_' + REGIONS[k - 1]]))
    zones = [ratio[k] for k in ('Chk_shear_G', 'Chk_shear_L') if isinstance(ratio.get(k), (int, float))]
    out.append(('DC_V[0] vs shear checks', env['DC_V'][0].v, max(zones)))

    sp = ctx.spacing['interval']
    for mc_name, key, unit in (('s_lim', 'pitch_limit', 'in'), ('w_lim', 'across_limit', 'in')):
        out.append((mc_name, _to(env[mc_name], unit), sp[key]))
    out.append(('DC_sp', env['DC_sp'].v, sp['spacing_ratio']))

    face_rows = ctx.faces['rows']
    out.append(('A_tr', _to(env['A_tr'], 'in**2/ft'), face_rows[0]['required_in2_ft']))
    out.append(('s_code', _to(env['s_code'], 'in'), face_rows[0]['code_spacing_in']))
    out.append(('s_tlim', _to(env['s_tlim'], 'in'), face_rows[0]['adopted_spacing_in']))
    for f, r in enumerate(face_rows):
        out.append((f'DC_ta[{f}] {r["face"]} {r["direction"]}', env['DC_ta'][f].v, r['area_ratio']))
        out.append((f'DC_ts[{f}] {r["face"]} {r["direction"]}', env['DC_ts'][f].v, r['spacing_ratio']))
    out.append(('Skin_req', env['Skin_req'].v, float(bool(e.value('Skin_required')))))
    out.append(('s_sk', _to(env['s_sk'], 'in'), tool('s_skin_limit')))
    if bool(e.value('Skin_required')):
        out += [('As_skq', _to(env['As_skq'], 'in**2'), tool('As_skin_req')), ('As_skh', _to(env['As_skh'], 'in**2'), tool('As_skin_half')),
                ('DC_sk_a', env['DC_sk_a'].v, ratio['Chk_skin_area']), ('DC_sk_s', env['DC_sk_s'].v, ratio['Chk_skin_space'])]

    if ctx.hook:
        b = ctx.hook['raw']
        for mc_name, key, unit in (('f_h', 'fh', 'kip'), ('l_db', 'basic_in', 'in'), ('lam_c', 'confinement_factor', None),
                                   ('l_ds', 'straight_in', 'in'), ('l_dh', 'required_in', 'in')):
            out.append((mc_name, _to(env[mc_name], unit), b[key]))
        out.append(('DC_hk', env['DC_hk'].v, ratio['Status_hook_development']))
    return out


def station_comparisons(env, ctx, rows, tags, ratio_rows, prefix=''):
    """Station quantities against the tool's own row (the same Items serve the worksheet and the coverage rows).

    ratio_rows: indexes of rows from the longitudinal list, whose `ratio` is the tension D/C (an interval-list row
    carries the shear D/C there instead)."""
    out = []
    for k, (tag, row) in enumerate(zip(tags, rows)):
        cf = row['compression_face']
        interval_row = 'rate_in2_in' in row

        def add(name, mine, theirs):
            out.append((f'{prefix}{name}[{k}] {tag}', mine, theirs))

        g = lambda name, unit=None: _to(env[name][k], unit)
        add('T_th', g('T_th', 'kip*ft'), row['threshold_kip_ft'])
        add('tor', g('tor'), float(bool(row['torsion_required'])))
        add('V_ef', g('V_ef', 'kip'), row['veff'])
        add('M_e', g('M_e', 'kip*in'), row['m_for_epsilon_kip_in'])
        if row['epsilon_base'] is not None:
            add('eps_b', g('eps_b'), row['epsilon_base'])
        if row['epsilon'] is not None:
            add('eps_s', g('eps_s'), row['epsilon'])
        add('simp', g('simp'), float(row['method'] == '5.7.3.4.1'))
        add('F_fl', g('F_fl', 'kip'), cf['force_kip'])
        if cf['stress_ksi'] is not None:
            add('f_fl', g('f_fl', 'ksi'), cf['stress_ksi'])
        add('crk', g('crk'), float(cf['cracked'] is True))
        add('l_g', g('l_g', 'in'), row['general_window_length_in'])
        add('beta', g('beta'), row['beta'])
        add('theta', g('theta', 'deg'), row['theta'])
        add('A_w', g('A_w', 'in**2'), row['window']['area_in2'])
        add('L_w', g('L_w', 'in'), row['window']['available_length_in'])
        add('V_c', g('V_c', 'kip'), row['vc'])
        add('V_s', g('V_s', 'kip'), row['vs'])
        add('V_r', g('V_r', 'kip'), row['vr_governing'] if interval_row else row['vr'])
        add('DC_V', g('DC_V'), row['shear_ratio'])
        add('r_eff', g('r_eff', 'in**2/in'), row['effective_rate'])
        add('A_vmin', _to(env['A_vmin'], 'in**2/in'), row['minimum_rate'])
        add('DC_Av', g('DC_Av'), row['minimum_ratio'])
        add('V_cr', g('V_cr', 'kip'), row['vs_credited_kip'])
        add('F_sh', g('F_sh', 'kip'), row['shear_tension_kip'])
        add('F_to', g('F_to', 'kip'), row['torsion_tension_kip'])
        add('F_mo', g('F_mo', 'kip'), row['moment_tension_kip'])
        add('F_ax', g('F_ax', 'kip'), row['axial_tension_kip'])
        add('F_di', g('F_di', 'kip'), row['diagonal_tension_kip'])
        add('F_req', g('F_req', 'kip'), row['required_tension_kip'])
        add('F_cap', g('F_cap', 'kip'), row['capacity_kip'])
        add('DC_L', g('DC_L'), row['required_tension_kip'] / max(row['capacity_kip'], 1e-9))
        if k in ratio_rows:                              # rows of the longitudinal list: ratio = required / capacity
            add('DC_L vs row ratio', g('DC_L'), row['ratio'])
    return out


def compare(items, what):
    bad = [(n, a, b) for n, a, b in items if not abs(a - b) <= TOL * max(abs(b), 1e-6)]
    if bad:
        raise AssertionError(f'{what}: Mathcad equations differ from the tool:\n' +
                             '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b in bad[:40]) +
                             (f'\n  ... {len(bad) - 40} more' if len(bad) > 40 else ''))


def check_stations(e, rows):
    p = e.case['inputs']
    if p['fpc'] != 0:
        raise ValueError('prestress (fpc) is outside the distilled shear calculation')
    if p['fc'] > 10 or p['fy'] > 100:
        raise ValueError('the distilled shear calculation covers f′c up to 10 ksi (the torsion limit) and fy up to 100 ksi')
    if not settings(e.case)['shrinkage_project_spacing_in']:
        raise ValueError('a zero project spacing limit for face steel is not distilled')
    for tag, row in zip(TAGS, rows):
        if row['exception_applied']:
            raise ValueError(f'station {tag} {row["id"]}: the direct-region exception applies; it is not distilled')
    try:
        from scripts import cap_mathcad_figures as figs
    except Exception:                                   # the figure module is optional for the numbers
        return
    drawn = figs.governing_stations(e)
    for t, row in zip(drawn, rows[:4]):
        assert abs(t['x_in'] - row['station_in']) < 1e-9, (t, row['id'])


# ----------------------------------------------------------------------------- build
def build_all(cap):
    if WITH_FIGURES:
        for name in ('elevation', 'section'):
            if not (FIGURES / f'{cap["key"]}_{name}.png').exists():
                raise FileNotFoundError(f'cap_mathcad/figures/{cap["key"]}_{name}.png is missing; run with --render-figures')
    e = evaluate_cap(cap)
    rep = report_link(cap, e)
    rev = notebook_revision()
    rows = governing_stations(e)
    check_stations(e, rows)
    physical = scheduled_bars(e.case)
    dv, l_cap = e.value('dv', 'in'), e.value('L_cap', 'in')
    values = station_values(e, rows, physical, dv, l_cap)
    ctx = SimpleNamespace(cap=cap, e=e, report=rep, revision=rev, values=input_values(e), rows=rows,
                          spacing=spacing_data(e), faces=face_data(e), hook=hook_data(e))
    head = sheet_head(ctx)
    stations = sheet_stations(ctx, rows, values)
    tail = sheet_tail(ctx, ctx.spacing, ctx.faces, ctx.hook)
    blocks = head + stations + tail
    # result widths (pt) for the row display of each vector: about six digits and the unit per element
    widths = dict(Region=300, St=420)
    for block in blocks:
        for item in (block.payload if block.kind in ('eqs', 'row', 'inputs') else []):
            if item.kind == 'idef' and isinstance(item.index, str):
                unit_chars = len(re.sub(r'\*\*(\d)', 'x', item.unit).replace('*', 'x')) if item.unit else 0
                widths[item.name] = (3 if item.index == 'r' else 5) * (36 + 4.6 * unit_chars) + 20
    check_names(blocks)
    check_inputs(blocks, ctx.values)
    env = run(blocks)
    check_display_units(blocks, env)
    shown = comparisons(env, ctx)
    compare(shown, 'worksheet')

    # branch coverage: other rows of the tool's own station search, then synthetic actions through its section()
    real, synthetic = coverage_stations(e, rows), synthetic_stations(e, physical)
    cover = real + synthetic
    cover_rows = [r for _, r in cover]
    for r in rows + cover_rows:
        if r['exception_applied']:
            raise ValueError(f'{r["id"]}: the direct-region exception applies; it is not distilled')
    unreached = [name for name, hit in branches_reached(rows + cover_rows).items() if not hit]
    if unreached:
        raise AssertionError('branch coverage does not reach: ' + ', '.join(unreached))
    cover_values = station_values(e, cover_rows, physical, dv, l_cap)
    cover_env = run(head + coverage_blocks(cover_values, len(cover_rows)))
    extra = station_comparisons(cover_env, ctx, cover_rows, [label for label, _ in cover],
                                ratio_rows=range(len(cover_rows)), prefix='coverage ')
    compare(extra, 'branch coverage')
    with result_widths(widths):
        text = document(blocks, title=f'{cap["label"]} Cap Design (distilled)',
                        description=f'Written by scripts/build_cap_mathcad.py from {rep["file"]} (case {rep["case_sha"][:12]})',
                        seed=int(rep['case_sha'][:12], 16), figures_dir=FIGURES, check_width=True)
        fills = mathcad_sheet.layout(blocks, FIGURES).check_pages()
    meta = dict(report=rep['file'], comparisons=len(shown) + len(extra), shown=len(shown), coverage=len(extra),
                coverage_real=len(real), coverage_synthetic=len(synthetic),
                coverage_rows=[(label, r['id']) for label, r in cover], stations=[r['id'] for r in rows], pages=len(fills), page_fills=[round(f) for f in fills],
                branches=sorted(branches_reached(rows + cover_rows)))
    env['__meta__'] = meta
    return text, env


def build(cap):
    """(xmcd text, environment) of one cap (a CAPS entry or its key); the '__meta__' entry of the environment describes the build."""
    key = cap if isinstance(cap, str) else cap['key']
    return build_all(next(c for c in CAPS if c['key'] == key))


def main():
    if '--render-figures' in sys.argv:
        from scripts import cap_mathcad_figures
        cap_mathcad_figures.main()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for cap in CAPS:
        text, env = build(cap)
        meta = env['__meta__']
        (OUT_DIR / cap['output']).write_text(text, encoding='utf-8', newline='\n')
        print(f'Wrote cap_mathcad/{cap["output"]}: {len(text) // 1024} KB; {meta["comparisons"]} values match the tool '
              f'({meta["coverage"]} from {meta["coverage_real"]} + {meta["coverage_synthetic"]} branch-coverage rows); '
              f'report {meta["report"]}; {meta["pages"]} pages, fullest {max(meta["page_fills"])} of {mathcad_sheet.PAGE_H:g} pt')


if __name__ == '__main__':
    main()
