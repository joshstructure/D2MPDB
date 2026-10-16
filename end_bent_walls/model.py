"""End-bent backwall, cheek-wall and tie-back strap calculations.

Every derived quantity is a unit-aware formula evaluated by the shared C005
engine (inch, kip, radian), so the notebook and report can show the equation,
substituted values and result. Load-combination formulas are generated from the
combination table with literal factors; the permanent-load factor for each
vertical item follows the sign of its overturning arm.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from pier_cap.engine import Engine, Q, parse
from pier_cap.model import BAR_AREA, BAR_DIAMETER

DATA = Path(__file__).parent / 'data'
INPUT_SPEC = json.loads((DATA / 'inputs.json').read_text(encoding='utf-8'))
INPUTS = {d['name']: d for d in INPUT_SPEC}
COMBINATION_DATA = json.loads((DATA / 'combinations.json').read_text(encoding='utf-8'))
COMBINATIONS = COMBINATION_DATA['combinations']
REFERENCES = json.loads((DATA / 'references.json').read_text(encoding='utf-8'))
SOURCES = json.loads((DATA / 'sources.json').read_text(encoding='utf-8'))
FORMAT = 'd2mpdb-end-bent-walls'
SCHEMA_VERSION = 2
PROJECT_EVIDENCE = json.loads((DATA / 'project_evidence.json').read_text(encoding='utf-8'))
BAR_SIZES = tuple(range(3, 12))
STRENGTH = [c for c in COMBINATIONS if c['limit'] == 'strength']
SERVICE = next(c for c in COMBINATIONS if c['limit'] == 'service')

CONFIRMATIONS = {
    'settlement': 'Geotechnical engineer confirms total settlement of the soil above the cap bottom will not exceed 2 in, so soil reinforcement may be attached to the end bent (SDG 3.13.2.N.3).',
    'strap_level': 'Strap elevation is coordinated with an MSE soil-reinforcement level (wall vendor / Specialty Engineer).',
    'exposure': 'Environment confirmed slightly or moderately aggressive for the SDG Table 1.4.2-1 covers used.',
    'geometry': 'Calculation geometry reconciled to the adopted CAD revision (D-026/D-033). Connection and fabrication acceptance remain separate.',
    'shrinkage': 'Beam shrinkage strain after bearing seating confirmed for the FIB-36 beams (LRFD 5.4.2.3.3).',
    'wind_kz': 'Strength III K_Z matches or conservatively bounds the journal wind module; its common exposure-height assumption is retained.',
    'landing': 'Landing bearing follows D-017; equivalent tributary length follows the verified D-034 slab quantities.',
    'analysis': 'Current bearing actions and common-end-bent envelope verified against both selected cap cases and matching raw analyses.',
    'cheek_connection': 'Cheek mat development, cap/lug load path and strap interfaces verified in the coordinated detail.',
}

_UNIT_ENGINE = Engine([])


def unit_quantity(unit):
    return Q(1.0) if unit in (None, 'bar') else _UNIT_ENGINE.eval(parse('1 ' + unit), {})


def default_case():
    return {
        'format': FORMAT, 'schema_version': SCHEMA_VERSION,
        'name': 'End Bent 1 backwall, cheek walls and tie-back straps (common end-bent design, D-004)',
        'inputs': {d['name']: d['value'] for d in INPUT_SPEC},
        'units': {d['name']: d['unit'] for d in INPUT_SPEC},
        'sources': {d['name']: {'source': d['source'], 'status': d['status']} for d in INPUT_SPEC},
        'confirmations': {key: PROJECT_EVIDENCE['confirmations'].get(key, {}).get('confirmed', False) for key in CONFIRMATIONS},
        'confirmation_evidence': deepcopy(PROJECT_EVIDENCE['confirmations']),
        'receipts': {},
        'reviews': {},
    }


def upgrade_case(case):
    """Fill new inputs with defaults; never invent values for a changed schema."""
    case = deepcopy(case)
    if case.get('format') != FORMAT:
        raise ValueError('This is not an end-bent backwall case. Load a file saved by this notebook.')
    if int(case.get('schema_version', 0)) > SCHEMA_VERSION:
        raise ValueError(f'This case uses schema {case["schema_version"]}; this notebook supports {SCHEMA_VERSION}. Use the newer notebook.')
    base = default_case()
    old_schema = int(case.get('schema_version', 1)) < 2
    if old_schema:
        # Existing saved designs retain their two-face steel and original loads.
        p = case.setdefault('inputs', {})
        p.setdefault('single_ck', 0)
        p.setdefault('L_load', p.get('L_cap', 212.0))
        for name in ('V_cap', 'V_bw', 'V_ck'):
            p.setdefault(name, 0.0)
        p.setdefault('dx_ck', (p.get('w_ck', 42.0) - p.get('b_cap', 42.0))/2)
        case.setdefault('confirmation_evidence', {})
        case['confirmations'] = {k: bool(case.get('confirmations', {}).get(k, False)) for k in CONFIRMATIONS}
    for key in ('inputs', 'units', 'sources', 'confirmations'):
        merged = {k: False for k in CONFIRMATIONS} if key == 'confirmations' else deepcopy(base[key])
        merged.update(case.get(key, {}))
        case[key] = merged
    case['units'] = base['units']
    case.setdefault('receipts', {})
    case.setdefault('reviews', {})
    case['schema_version'] = SCHEMA_VERSION
    reconcile_confirmations(case)
    return case


def reconcile_confirmations(case):
    """Project evidence confirms only the values actually reviewed."""
    for key, record in case.get('confirmation_evidence', {}).items():
        expected = record.get('inputs', {})
        if expected and any(case['inputs'].get(n) != value for n, value in expected.items()):
            record['stale'] = True
            case['confirmations'][key] = False


def edit_input(case, name, value):
    """Drop measured-volume overrides when a dependent dimension is edited."""
    if case['inputs'].get(name) == value:
        return
    case['inputs'][name] = value
    for volume, dimensions in {'V_cap': ('b_cap', 'h_cap', 'L_cap'),
                               'V_bw': ('t_bw', 'H_bw', 'H_bw_edge', 'L_bw'),
                               'V_ck': ('t_ck', 'w_ck', 'H_ck')}.items():
        if name in dimensions:
            case['inputs'][volume] = 0.0
            case['sources'][volume] = {'source': 'Dimension edited: measured volume cleared; geometric estimate used', 'status': 'pending confirmation'}
    reconcile_confirmations(case)


def validate_case(case):
    problems = []
    for name, spec in INPUTS.items():
        value = case['inputs'].get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            problems.append(f'{name}: enter a number')
            continue
        if spec['unit'] == 'bar' and int(value) not in BAR_SIZES:
            problems.append(f'{name}: use bar size #3 to #11')
    p = case['inputs']
    positive = ['b_cap', 'h_cap', 'L_cap', 't_bw', 'L_bw', 'H_bw', 'H_bw_edge', 't_ck', 'w_ck', 'H_ck',
                'gamma_s', 'fc', 'fy', 'Es', 'w_c', 'w_cE', 'L_pad', 'W_pad', 'G_pad', 'z_strap',
                's_FF', 's_SF', 's_HZ', 's_CK', 's_CKH', 'N_brg', 'N_pile', 'S_pile', 'D_pile']
    problems += [f'{n}: must be greater than zero' for n in positive if isinstance(p.get(n), (int, float)) and p[n] <= 0]
    if not problems:
        if p['single_ck'] not in (0, 1):
            problems.append('single_ck: use 1 for a centered mat or 0 for legacy two-face steel')
        if any(p[n] < 0 for n in ('V_cap', 'V_bw', 'V_ck')):
            problems.append('Measured concrete volumes cannot be negative')
        if p['L_load'] <= 0:
            problems.append('L_load: must be greater than zero')
        if p['L_bw'] > p['L_cap']:
            problems.append('L_bw: the backwall cannot be longer than the cap')
        if p['t_bw'] >= p['b_cap']:
            problems.append('t_bw: the backwall must be thinner than the cap width')
        if p['embed_pile'] >= p['h_cap']:
            problems.append('embed_pile: embedment must be less than the cap depth')
        if p['H_bw_edge'] > p['H_bw']:
            problems.append('H_bw_edge: the edge height cannot exceed the design (crown) height')
        if p['phi_soil'] <= p['beta_f']:
            problems.append('phi_soil: the friction angle must exceed the backfill slope')
        if 2 * p['cv_bw'] + 2 * BAR_DIAMETER[int(p['bar_FF'])] >= p['t_bw']:
            problems.append('cv_bw: covers and bars do not fit within the backwall thickness')
        if 2 * p['cv_ck'] + 2 * BAR_DIAMETER[int(p['bar_CK'])] >= p['t_ck']:
            problems.append('cv_ck: covers and bars do not fit within the cheek-wall thickness')
        if p['s_brg'] >= p['L_cap']:
            problems.append('s_brg: bearing spacing must be less than the cap length')
    if problems:
        raise ValueError('Check inputs: ' + '; '.join(problems))
    return True


def input_externals(case):
    out = {}
    for name, spec in INPUTS.items():
        out[name] = Q(float(case['inputs'][name])) * unit_quantity(spec['unit'])
    for tag in ('FF', 'SF', 'HZ', 'CK', 'CKH'):
        size = int(case['inputs']['bar_' + tag])
        out['A_b_' + tag] = Q(BAR_AREA[size]) * unit_quantity('in^2')
        out['d_b_' + tag] = Q(BAR_DIAMETER[size]) * unit_quantity('in')
    return out


EXTERNAL_UNITS = {f'A_b_{t}': 'in^2' for t in ('FF', 'SF', 'HZ', 'CK', 'CKH')}
EXTERNAL_UNITS.update({f'd_b_{t}': 'in' for t in ('FF', 'SF', 'HZ', 'CK', 'CKH')})
EXTERNAL_CAPTIONS = {f'A_b_{t}': f'Bar area, {INPUTS["bar_" + t]["caption"].lower()}' for t in ('FF', 'SF', 'HZ', 'CK', 'CKH')}
EXTERNAL_CAPTIONS.update({f'd_b_{t}': f'Bar diameter, {INPUTS["bar_" + t]["caption"].lower()}' for t in ('FF', 'SF', 'HZ', 'CK', 'CKH')})


def _d(section, name, expr, unit, caption, refs=()):
    return {'section': section, 'name': name, 'formula': f'{name} = {expr}', 'expr': expr,
            'unit': unit, 'caption': caption, 'refs': list(refs)}


SECTIONS = [
    ('geometry', '1. Geometry and overturning arms'),
    ('earth', '2. Earth pressure and surcharges'),
    ('bearing', '3. Bearing and superstructure actions'),
    ('dead', '4. Dead loads'),
    ('strap', '5. Overturning about the pile top and tie-back strap force'),
    ('bw_load', '6. Backwall demands per 1-ft strip'),
    ('materials', '7. Material and section constants'),
    ('bw_FF', '8. Backwall section · fill face vertical steel'),
    ('bw_SF', '9. Backwall section · span face vertical steel'),
    ('bw_joint', '10. Backwall shear, distribution steel and construction joint'),
    ('ck', '11. Cheek walls · wind only'),
    ('ck_sec', '12. Cheek wall section'),
    ('cap', '13. Cap supplement'),
]


def base_definitions():
    g, e, b, d = 'geometry', 'earth', 'bearing', 'dead'
    return [
        _d(g, 'b_s', '12 in', 'in', 'Design strip width'),
        _d(g, 'y_top', 'h_cap - embed_pile', 'ft', 'Cap top above the pile top'),
        _d(g, 'H_ret', 'H_bw + h_cap', 'ft', 'Retained height, cap soffit to backwall crown', ['earth_pressure']),
        _d(g, 'H_bw_avg', 'If(V_bw > 0 ft^3, V_bw/(t_bw*L_bw), (H_bw + H_bw_edge)/2)', 'ft', 'Equivalent average backwall height for self-weight (native volume when supplied)'),
        _d(g, 'y_brg', 'y_top + h_ped + t_pad', 'ft', 'Top of bearing pad above the pile top (bearing-level forces)'),
        _d(g, 'y_strap', 'y_top + z_strap', 'ft', 'Tie-back strap above the pile top'),
        _d(g, 'x_brg', 'e_brg + tol_pile', 'in', 'Bearing arm toward the span about the pile line shifted by the placement tolerance', ['soil_reinforcement']),
        _d(g, 'x_cap', 'tol_pile', 'in', 'Cap self-weight arm (cap centered on the nominal pile line)', ['soil_reinforcement']),
        _d(g, 'x_ped', 't_bw + L_ped/2 - b_cap/2 + tol_pile', 'in', 'Pedestal arm'),
        _d(g, 'x_ck', 'dx_ck + tol_pile', 'in', 'Cheek wall centroid arm, including rear and bottom lugs'),
        _d(g, 'x_bw', 't_bw/2 - b_cap/2 + tol_pile', 'in', 'Backwall and landing-slab arm (negative = behind the pile line)'),
        _d(e, 'Gamma_c', '(1 + Sqrt(Sin(phi_soil + delta_w)*Sin(phi_soil - beta_f)/(Sin(theta_w - delta_w)*Sin(theta_w + beta_f))))^2', None, 'Coulomb Γ', ['coulomb', 'fill_params']),
        _d(e, 'k_a', 'Sin(theta_w + phi_soil)^2/(Gamma_c*Sin(theta_w)^2*Sin(theta_w - delta_w))', None, 'Active earth pressure coefficient', ['coulomb']),
        _d(e, 'p_EH', 'k_a*gamma_s*H_ret', 'kip/ft^2', 'Active earth pressure at the cap soffit', ['earth_pressure']),
        _d(e, 'F_EH', '0.5*k_a*gamma_s*H_ret^2*L_load', 'kip', 'Earth pressure resultant over the full end-bent envelope', ['earth_pressure']),
        _d(e, 'y_EH', 'H_ret/3 - embed_pile', 'ft', 'EH resultant above the pile top'),
        _d(e, 'p_LS', 'k_a*q_PL', 'kip/ft^2', 'Pedestrian live-load surcharge pressure', ['surcharge', 'ped_load']),
        _d(e, 'F_LS', 'p_LS*H_ret*L_load', 'kip', 'Live-load surcharge resultant'),
        _d(e, 'y_LS', 'H_ret/2 - embed_pile', 'ft', 'LS resultant above the pile top'),
        _d(e, 'q_ES', 't_slab*w_c', 'kip/ft^2', 'Landing slab weight on the fill (earth surcharge)'),
        _d(e, 'p_ES', 'k_a*q_ES', 'kip/ft^2', 'Earth surcharge pressure', ['surcharge']),
        _d(e, 'F_ES', 'p_ES*H_ret*L_load', 'kip', 'Earth surcharge resultant'),
        _d(e, 'y_ES', 'H_ret/2 - embed_pile', 'ft', 'ES resultant above the pile top'),
        _d(b, 'A_pad', 'L_pad*W_pad', 'in^2', 'Bearing pad plan area'),
        _d(b, 'h_rt', 'n_int*t_int + 2*t_cov', 'in', 'Total elastomer thickness'),
        _d(b, 'K_pad', 'G_fac*G_pad*A_pad/h_rt', 'kip/in', 'Pad shear stiffness with upper-bound G', ['bearing_shear']),
        _d(b, 'Delta_TU', 'alpha_t*dT*L_exp', 'in', 'Thermal contraction at the end bent', ['temperature', 'thermal_coef']),
        _d(b, 'F_TU', 'N_brg*K_pad*Delta_TU', 'kip', 'Pad shear from temperature fall (toward the span)', ['bearing_shear']),
        _d(b, 'Delta_SH', 'eps_sh*L_exp', 'in', 'Beam shrinkage shortening at the end bent', ['shrinkage']),
        _d(b, 'F_SH', 'N_brg*K_pad*Delta_SH', 'kip', 'Pad shear from shrinkage (toward the span)', ['bearing_shear']),
        _d(b, 'W_DCb', 'N_brg*P_DC', 'kip', 'Superstructure DC at the bearings'),
        _d(b, 'W_PLb', 'N_brg*P_PL', 'kip', 'Pedestrian load at the bearings'),
        _d(b, 'H_WS1', 'N_brg*FY_WS1', 'kip', 'Longitudinal wind, Strength III direction 1'),
        _d(b, 'H_WS2', 'N_brg*FY_WS2', 'kip', 'Longitudinal wind, Strength III direction 2'),
        _d(b, 'H_WS3', 'N_brg*FY_WS3', 'kip', 'Longitudinal wind, Service I'),
        _d(d, 'W_cap', 'If(V_cap > 0 ft^3, V_cap, b_cap*h_cap*L_cap)*w_c', 'kip', 'Cap self-weight (native net concrete when supplied)'),
        _d(d, 'W_ped', 'N_brg*L_ped*B_ped*h_ped*w_c', 'kip', 'Pedestal weight'),
        _d(d, 'W_bw', 't_bw*H_bw_avg*L_bw*w_c', 'kip', 'Backwall weight'),
        _d(d, 'W_ck', 'If(V_ck > 0 ft^3, V_ck, 2*t_ck*w_ck*H_ck)*w_c', 'kip', 'Both cheek walls, including rear and bottom lugs'),
        _d(d, 'w_sl_DC', 'share_slab*L_slab*t_slab*w_c', 'kip/ft', 'Landing slab dead load on the backwall (gravity design only)', ['end_bent_overturning']),
        _d(d, 'w_sl_PL', 'share_slab*L_slab*q_PL', 'kip/ft', 'Landing slab pedestrian load on the backwall (gravity design only)', ['end_bent_overturning']),
    ]


HORIZONTAL_ITEMS = [  # name, force, arm, factor key, label
    ('EH', 'F_EH', 'y_EH', 'EH', 'Earth pressure EH'),
    ('ES', 'F_ES', 'y_ES', 'ES', 'Landing slab surcharge ES'),
    ('LS', 'F_LS', 'y_LS', 'LS', 'Pedestrian surcharge LS'),
    ('TU', 'F_TU', 'y_brg', 'TU', 'Temperature fall TU'),
    ('SH', 'F_SH', 'y_brg', 'SH', 'Shrinkage SH'),
]
VERTICAL_ITEMS = [
    ('DCb', 'W_DCb', 'x_brg', 'DC', 'Superstructure DC at bearings'),
    ('PLb', 'W_PLb', 'x_brg', 'PL', 'Pedestrian load at bearings'),
    ('cap', 'W_cap', 'x_cap', 'DC', 'Cap self-weight'),
    ('ped', 'W_ped', 'x_ped', 'DC', 'Pedestals'),
    ('ck', 'W_ck', 'x_ck', 'DC', 'Cheek walls'),
    ('bw', 'W_bw', 'x_bw', 'DC', 'Backwall'),
]


def _num(value):
    return f'{value:g}'


def combination_terms(combo, values):
    """Factored (factor, force, arm, label, kind) terms for one combination."""
    terms = []
    for key, force, arm, family, label in HORIZONTAL_ITEMS:
        factor = combo[family][0] if isinstance(combo[family], list) else combo[family]
        terms.append(dict(item=key, force=force, arm=arm, factor=factor, kind='H', label=label,
                          basis='maximum (overturning)' if isinstance(combo[family], list) else 'transient'))
    wind = combo.get('wind')
    if wind:
        terms.append(dict(item='WS', force='H_' + wind, arm='y_brg', factor=combo['WS'], kind='H',
                          label=f'Longitudinal wind {wind}', basis='transient, either direction'))
    for key, force, arm, family, label in VERTICAL_ITEMS:
        x = values[arm]
        if family == 'DC':
            factor = combo['DC'][0] if x > 0 else combo['DC'][1]
            basis = 'maximum (overturning arm)' if x > 0 else 'minimum (stabilizing arm)'
        else:
            factor = combo[family] if x > 0 else 0.0
            basis = 'transient on overturning arm' if x > 0 else 'live load takes no stabilizing credit'
        terms.append(dict(item=key, force=force, arm=arm, factor=factor, kind='V', label=label, basis=basis))
    if wind:
        fz = values['FZ_' + wind]
        destabilizing = fz * values['x_brg'] > 0
        terms.append(dict(item='WSV', force='FZ_' + wind, arm='x_brg', factor=combo['WS'] if destabilizing else 0.0,
                          kind='V', label=f'Vertical wind {wind}',
                          basis='overturning' if destabilizing else 'stabilizing uplift ignored'))
    return terms


def strap_definitions(values):
    s = 'strap'
    defs = []
    for c in COMBINATIONS:
        k = c['key']
        terms = combination_terms(c, values)
        h = ' + '.join(f'{_num(t["factor"])}*{t["force"]}' for t in terms if t['kind'] == 'H' and t['factor'])
        m = ' + '.join(f'{_num(t["factor"])}*{t["force"]}*{t["arm"]}' for t in terms if t['factor'])
        defs += [
            _d(s, f'H_{k}', h or '0 kip', 'kip', f'{c["label"]} · horizontal force toward the span', ['load_factors']),
            _d(s, f'M_{k}', m, 'kip*ft', f'{c["label"]} · overturning moment about the pile top', ['load_factors', 'end_bent_overturning', 'soil_reinforcement']),
            _d(s, f'e_{k}', f'M_{k}/H_{k}', 'ft', f'{c["label"]} · resultant height above the pile top'),
            _d(s, f'F_eq_{k}', f'M_{k}/y_strap', 'kip', f'{c["label"]} · strap force for moment equilibrium (pinned single pile row)'),
            _d(s, f'F_str_{k}', f'Max(H_{k}, F_eq_{k})', 'kip', f'{c["label"]} · design tie-back force'),
            _d(s, f'f_str_{k}', f'F_str_{k}/L_bw', 'kip/ft', f'{c["label"]} · tie-back load per foot of backwall', ['strap_plans']),
            _d(s, f'V_pile_{k}', f'F_eq_{k} - H_{k}', 'kip', f'{c["label"]} · horizontal force the piles supply at the pile top for equilibrium (+ toward the span)'),
        ]
    strength = ', '.join(f'f_str_{c["key"]}' for c in STRENGTH)
    defs += [
        _d(s, 'f_str_u', f'Max({strength})', 'kip/ft', 'Factored tie-back load per foot of backwall', ['strap_plans']),
        _d(s, 'f_str_s', f'f_str_{SERVICE["key"]}', 'kip/ft', 'Service tie-back load per foot of backwall', ['strap_plans']),
        _d(s, 'F_str_u', 'f_str_u*L_bw', 'kip', 'Factored tie-back force, whole end bent'),
        _d(s, 'F_str_s', 'f_str_s*L_bw', 'kip', 'Service tie-back force, whole end bent'),
    ]
    return defs


def _soil_factors(combo):
    return combo['EH'][0], combo['ES'][0], combo['LS']


def backwall_definitions():
    w = 'bw_load'
    defs = [
        _d(w, 'V_EH_bw', '0.5*k_a*gamma_s*H_bw^2*b_s', 'kip', 'Earth pressure on the backwall, 1-ft strip', ['earth_pressure']),
        _d(w, 'M_EH_bw', 'V_EH_bw*H_bw/3', 'kip*ft', 'EH moment at the construction joint'),
        _d(w, 'V_LS_bw', 'p_LS*H_bw*b_s', 'kip', 'Pedestrian surcharge on the backwall', ['surcharge']),
        _d(w, 'M_LS_bw', 'V_LS_bw*H_bw/2', 'kip*ft', 'LS moment at the construction joint'),
        _d(w, 'V_ES_bw', 'p_ES*H_bw*b_s', 'kip', 'Landing slab surcharge on the backwall', ['surcharge']),
        _d(w, 'M_ES_bw', 'V_ES_bw*H_bw/2', 'kip*ft', 'ES moment at the construction joint'),
    ]
    for c in COMBINATIONS:
        k = c['key']
        eh, es, ls = _soil_factors(c)
        defs += [
            _d(w, f'M_sl_{k}', f'{_num(eh)}*M_EH_bw + {_num(es)}*M_ES_bw + {_num(ls)}*M_LS_bw', 'kip*ft',
               f'{c["label"]} · strap slack: cantilever moment, fill-face tension', ['load_factors']),
            _d(w, f'V_sl_{k}', f'{_num(eh)}*V_EH_bw + {_num(es)}*V_ES_bw + {_num(ls)}*V_LS_bw', 'kip',
               f'{c["label"]} · strap slack: joint shear'),
            _d(w, f'M_en_{k}', f'f_str_{k}*b_s*z_strap - M_sl_{k}', 'kip*ft',
               f'{c["label"]} · strap engaged: joint moment, span-face tension'),
            _d(w, f'V_en_{k}', f'f_str_{k}*b_s - V_sl_{k}', 'kip', f'{c["label"]} · strap engaged: joint shear'),
        ]
    keys = [c['key'] for c in STRENGTH]
    s = SERVICE['key']
    defs += [
        _d(w, 'M_u_FF', 'Max(' + ', '.join(f'M_sl_{k}' for k in keys) + ')', 'kip*ft', 'Factored moment, fill face (strap slack)'),
        _d(w, 'M_s_FF', f'M_sl_{s}', 'kip*ft', 'Service I moment, fill face'),
        _d(w, 'M_u_SF', 'Max(' + ', '.join(f'M_en_{k}' for k in keys) + ', 0 kip*ft)', 'kip*ft', 'Factored moment, span face (strap engaged)'),
        _d(w, 'M_s_SF', f'Max(M_en_{s}, 0 kip*ft)', 'kip*ft', 'Service I moment, span face'),
        _d(w, 'V_u_bw', 'Max(' + ', '.join([f'V_sl_{k}' for k in keys] + [f'Abs(V_en_{k})' for k in keys]) + ')', 'kip',
           'Factored joint shear, both strap states'),
    ]
    return defs


def material_definitions():
    m = 'materials'
    return [
        _d(m, 'beta_1', 'Min(0.85, Max(0.65, 0.85 - 0.05*(fc - 4 ksi)/(1 ksi)))', None, 'Stress block factor', ['stress_block']),
        _d(m, 'E_c', '120000*K_1*(w_cE/(1 kip/ft^3))^2*(fc/(1 ksi))^0.33*(1 ksi)', 'ksi', 'Concrete modulus', ['modulus']),
        _d(m, 'n_m', 'Es/E_c', None, 'Modular ratio'),
        _d(m, 'f_r', '0.24*lambda_c*Sqrt(fc/(1 ksi))*(1 ksi)', 'ksi', 'Modulus of rupture', ['rupture']),
        _d(m, 'f_ss_lim', 'fss_ratio*fy', 'ksi', 'Service steel stress limit', ['crack_fdot']),
    ]


def section_definitions(section, x, thickness, cover, moment_u, moment_s):
    """Rectangular 1-ft strip with one layer of tension steel (LRFD 5.6 / 5.7)."""
    t, cv = thickness, cover
    depth = f'{t} - {cv} - d_b_{x}/2'
    if x == 'CK':
        depth = f'If(single_ck == 1, t_ck/2 - d_b_CKH/2, {depth})'
    return [
        _d(section, f'd_{x}', depth, 'in', 'Effective depth (weaker wind direction for the centered tangent mat)' if x == 'CK' else 'Effective depth'),
        _d(section, f'A_s_{x}', f'A_b_{x}*b_s/s_{x}', 'in^2', 'Tension steel in a 1-ft strip'),
        _d(section, f'a_{x}', f'A_s_{x}*fy/(0.85*fc*b_s)', 'in', 'Stress block depth', ['flexure']),
        _d(section, f'c_{x}', f'a_{x}/beta_1', 'in', 'Neutral axis depth', ['flexure']),
        _d(section, f'eps_t_{x}', f'0.003*(d_{x} - c_{x})/c_{x}', None, 'Net tensile strain', ['phi']),
        _d(section, f'phi_{x}', f'If(eps_t_{x} >= 0.005, phi_f, If(eps_t_{x} <= 0.002, 0.75, 0.75 + 0.15*(eps_t_{x} - 0.002)/0.003))', None, 'Flexural resistance factor', ['phi']),
        _d(section, f'M_n_{x}', f'A_s_{x}*fy*(d_{x} - a_{x}/2)', 'kip*ft', 'Nominal flexural resistance', ['flexure']),
        _d(section, f'M_r_{x}', f'phi_{x}*M_n_{x}', 'kip*ft', 'Factored flexural resistance', ['flexure', 'phi']),
        _d(section, f'A_req_{x}', f'0.85*fc*b_s*d_{x}/fy*(1 - Sqrt(Max(1 - 2*{moment_u}/(0.85*phi_f*fc*b_s*d_{x}^2), 0)))', 'in^2', 'Steel required for the factored moment', ['flexure']),
        _d(section, f'S_c_{x}', f'b_s*{t}^2/6', 'in^3', 'Section modulus', ['min_flexure']),
        _d(section, f'M_cr_{x}', f'gamma_3*gamma_1*f_r*S_c_{x}', 'kip*ft', 'Cracking moment', ['min_flexure']),
        _d(section, f'M_min_{x}', f'Min(M_cr_{x}, 1.33*{moment_u})', 'kip*ft', 'Minimum required flexural resistance', ['min_flexure']),
        _d(section, f'rho_{x}', f'A_s_{x}/(b_s*d_{x})', None, 'Reinforcement ratio'),
        _d(section, f'k_{x}', f'Sqrt(2*rho_{x}*n_m + (rho_{x}*n_m)^2) - rho_{x}*n_m', None, 'Cracked neutral axis ratio'),
        _d(section, f'j_{x}', f'1 - k_{x}/3', None, 'Lever arm ratio'),
        _d(section, f'f_ss_{x}', f'{moment_s}/(A_s_{x}*j_{x}*d_{x})', 'ksi', 'Service I steel stress', ['crack_control']),
        _d(section, f'd_c_{x}', f'{t} - d_{x}', 'in', 'Cover to the bar center'),
        _d(section, f'beta_s_{x}', f'1 + d_c_{x}/(0.7*({t} - d_c_{x}))', None, 'Flexural strain ratio', ['crack_control']),
        _d(section, f's_cr_{x}', f'If(f_ss_{x} > 0 ksi, 700*gamma_e/(beta_s_{x}*f_ss_{x}/(1 ksi))*(1 in) - 2*d_c_{x}, 99 in)', 'in', 'Crack-control spacing limit (99 in = no service tension)', ['crack_control', 'crack_fdot']),
        _d(section, f'd_v_{x}', f'Max(d_{x} - a_{x}/2, 0.9*d_{x}, 0.72*{t})', 'in', 'Effective shear depth', ['shear_depth']),
        _d(section, f'V_c_{x}', f'0.0316*beta_v*lambda_c*Sqrt(fc/(1 ksi))*(1 ksi)*b_s*d_v_{x}', 'kip', 'Concrete shear resistance', ['shear']),
        _d(section, f'V_n_{x}', f'Min(V_c_{x}, 0.25*fc*b_s*d_v_{x})', 'kip', 'Nominal shear resistance', ['shear']),
        _d(section, f'V_r_{x}', f'phi_v*V_n_{x}', 'kip', 'Factored shear resistance', ['shear']),
    ]


def joint_definitions():
    j, c, cs, cap = 'bw_joint', 'ck', 'ck_sec', 'cap'
    return [
        _d(j, 'V_r_bw', 'Min(V_r_FF, V_r_SF)', 'kip', 'Backwall factored shear resistance (weaker face)', ['shear']),
        _d(j, 's_max_bw', 'Min(1.5*t_bw, 18 in)', 'in', 'Maximum primary bar spacing', ['max_spacing']),
        _d(j, 'b_ts_bw', 'Min(H_bw, L_bw)', 'in', 'Least backwall width for distribution steel', ['temp_shrink']),
        _d(j, 'A_ts_bw', 'Min(Max(1.30*(b_ts_bw/(1 in))*(t_bw/(1 in))/(2*((b_ts_bw + t_bw)/(1 in))*(fy/(1 ksi)))*(1 in^2/ft), 0.11 in^2/ft), 0.60 in^2/ft)', 'in^2/ft', 'Shrinkage and temperature steel, each face', ['temp_shrink']),
        _d(j, 's_ts_bw', 'Min(3*t_bw, 18 in)', 'in', 'Maximum shrinkage and temperature spacing', ['temp_shrink']),
        _d(j, 'A_pr_FF', 'A_b_FF/s_FF', 'in^2/ft', 'Vertical steel provided, fill face'),
        _d(j, 'A_pr_SF', 'A_b_SF/s_SF', 'in^2/ft', 'Vertical steel provided, span face'),
        _d(j, 'A_pr_HZ', 'A_b_HZ/s_HZ', 'in^2/ft', 'Horizontal steel provided, each face'),
        _d(j, 'A_cv_bw', 'Min(d_v_FF, d_v_SF)*b_s', 'in^2', 'Interface area engaged (template basis: dv strip)', ['interface']),
        _d(j, 'A_vf_bw', 'Min(A_s_FF, A_s_SF)', 'in^2', 'Interface reinforcement crossing the joint (one face)', ['interface']),
        _d(j, 'V_ni_bw', 'Min(c_if*A_cv_bw + mu_if*A_vf_bw*fy, K1_if*fc*A_cv_bw, K2_if*A_cv_bw)', 'kip', 'Nominal interface shear resistance, Pc = 0', ['interface', 'interface_fdot']),
        _d(j, 'V_ri_bw', 'phi_v*V_ni_bw', 'kip', 'Factored interface shear resistance', ['interface']),
        _d(j, 'A_vfmin_bw', '0.05*(1 ksi)*A_cv_bw/fy', 'in^2', 'Minimum interface reinforcement', ['interface_min']),
        _d(c, 'P_Z_III', '2.56E-06*V_III^2*K_Z_III*G_w*C_D*(1 kip/ft^2)', 'kip/ft^2', 'Strength III wind pressure on the cheek walls', ['wind', 'wind_fdot']),
        _d(c, 'P_Z_SER', '2.56E-06*V_SER^2*K_Z_SER*G_w*C_D*(1 kip/ft^2)', 'kip/ft^2', 'Service I wind pressure', ['wind']),
        _d(c, 'V_u_CK', 'P_Z_III*H_ck*b_s', 'kip', 'Factored base shear, 1-ft strip (WS factor 1.0)', ['load_factors']),
        _d(c, 'M_u_CK', 'P_Z_III*H_ck^2/2*b_s', 'kip*ft', 'Factored base moment, 1-ft strip'),
        _d(c, 'M_s_CK', 'P_Z_SER*H_ck^2/2*b_s', 'kip*ft', 'Service I base moment, 1-ft strip'),
        _d(cs, 's_max_ck', 'Min(1.5*t_ck, 18 in)', 'in', 'Maximum primary bar spacing', ['max_spacing']),
        _d(cs, 'b_ts_ck', 'Min(H_ck, w_ck)', 'in', 'Least cheek-wall width for distribution steel', ['temp_shrink']),
        _d(cs, 'A_ts_ck', 'If(single_ck == 1, 2, 1)*Min(Max(1.30*(b_ts_ck/(1 in))*(t_ck/(1 in))/(2*((b_ts_ck + t_ck)/(1 in))*(fy/(1 ksi)))*(1 in^2/ft), 0.11 in^2/ft), 0.60 in^2/ft)', 'in^2/ft', 'Shrinkage and temperature steel (sum of both face requirements in one mat)', ['temp_shrink']),
        _d(cs, 's_ts_ck', 'Min(3*t_ck, 18 in)', 'in', 'Maximum shrinkage and temperature spacing', ['temp_shrink']),
        _d(cs, 'A_pr_CK', 'A_b_CK/s_CK', 'in^2/ft', 'Vertical steel provided in the mat'),
        _d(cs, 'A_pr_CKH', 'A_b_CKH/s_CKH', 'in^2/ft', 'Horizontal steel provided in the mat'),
        _d(cs, 'cover_ck_actual', 'If(single_ck == 1, (t_ck - d_b_CK - d_b_CKH)/2, cv_ck)', 'in', 'Minimum physical cover to the tangent centered mat'),
        _d(cs, 'A_cv_ck', 'd_v_CK*b_s', 'in^2', 'Interface area engaged at the cheek-wall joint', ['interface']),
        _d(cs, 'V_ni_ck', 'Min(c_if*A_cv_ck + mu_if*A_s_CK*fy, K1_if*fc*A_cv_ck, K2_if*A_cv_ck)', 'kip', 'Nominal interface shear resistance', ['interface']),
        _d(cs, 'V_ri_ck', 'phi_v*V_ni_ck', 'kip', 'Factored interface shear resistance', ['interface']),
        _d(cs, 'A_vfmin_ck', '0.05*(1 ksi)*A_cv_ck/fy', 'in^2', 'Minimum interface reinforcement', ['interface_min']),
        _d(cap, 'A_cp', 'b_cap*h_cap', 'in^2', 'Cap gross area'),
        _d(cap, 'p_cp', '2*(b_cap + h_cap)', 'in', 'Cap perimeter'),
        _d(cap, 'T_cr', '0.126*Sqrt(fc/(1 ksi))*(1 ksi)*A_cp^2/p_cp', 'kip*ft', 'Cracking torque, nonprestressed (K = 1)', ['torsion_threshold']),
        _d(cap, 'T_lim', '0.25*phi_v*T_cr', 'kip*ft', 'Torsion may be neglected below this value', ['torsion_threshold']),
        _d(cap, 'w_bw', 't_bw*H_bw_avg*w_c', 'kip/ft', 'Backwall weight per foot (not in the FBMP model)'),
        _d(cap, 't_bw_DC', '(w_bw + w_sl_DC)*(t_bw/2 - b_cap/2)', 'kip*ft/ft', 'DC torque per foot about the cap centerline (nominal)'),
        _d(cap, 't_bw_PL', 'w_sl_PL*(t_bw/2 - b_cap/2)', 'kip*ft/ft', 'PL torque per foot about the cap centerline (nominal)'),
    ]


def all_definitions(values):
    return (base_definitions() + strap_definitions(values) + backwall_definitions() + material_definitions()
            + section_definitions('bw_FF', 'FF', 't_bw', 'cv_bw', 'M_u_FF', 'M_s_FF')
            + section_definitions('bw_SF', 'SF', 't_bw', 'cv_bw', 'M_u_SF', 'M_s_SF')
            + section_definitions('ck_sec', 'CK', 't_ck', 'cv_ck', 'M_u_CK', 'M_s_CK')
            + joint_definitions())


@dataclass
class Check:
    key: str
    group: str
    label: str
    ratio: object
    status: str
    demand: str
    capacity: str
    basis: str
    refs: list
    names: list
    note: str = ''
    review: dict = None


@dataclass
class Evaluation:
    case: dict
    engine: Engine
    definitions: list
    units: dict
    terms: dict
    checks: list = field(default_factory=list)
    cap: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)

    def value(self, name, unit=None):
        q = self.engine.get(name)
        if not isinstance(q, Q):
            return q
        return q.v / unit_quantity(unit or self.units.get(name)).v

    def text(self, name, places=3, unit=None):
        unit = unit or self.units.get(name)
        number = self.value(name, unit)
        label = {'kip*ft': 'kip-ft', 'kip/ft^2': 'ksf', 'kip/ft^3': 'kcf', 'kip/ft': 'klf',
                 'in^2/ft': 'in²/ft', 'in^2': 'in²', 'in^3': 'in³', 'kip*ft/ft': 'kip-ft/ft'}.get(unit, unit or '')
        return f'{number:.{places}f} {label}'.strip()

    @property
    def strength_dc(self):
        ratios = [c.ratio for c in self.checks if isinstance(c.ratio, (int, float)) and c.group != 'Prerequisites']
        return max(ratios) if ratios else 0.0

    @property
    def status(self):
        failed = [c for c in self.checks if 'FAIL' in c.status]
        pending = [c for c in self.checks if 'PENDING' in c.status]
        if failed:
            return f'{len(failed)} check(s) FAIL · {len(pending)} pending'
        return f'All numerical checks pass · {len(pending)} pending item(s) remain' if pending else 'All checks pass'


def _status(ratio, pending=False):
    if ratio is None:
        return 'PENDING' if pending else 'INFO'
    if ratio > 1 + 1e-9:
        return 'FAIL'
    return 'PASS · PENDING INPUT' if pending else 'PASS'


def _ratio(a, b):
    return a / b if b else float('inf')


def build_checks(e):
    v, t, case = e.value, e.text, e.case
    conf = case['confirmations']
    checks = []

    def add(key, group, label, ratio, demand, capacity, basis, refs, names, pending=False, note=''):
        checks.append(Check(key, group, label, ratio, _status(ratio, pending), demand, capacity, basis, refs, names, note))

    geometry_pending = not conf['geometry']
    for x, face, state in (('FF', 'fill face', 'strap slack'), ('SF', 'span face', 'strap engaged')):
        mu = v(f'M_u_{x}')
        add(f'flex_{x}', 'Backwall', f'Flexure · {face} ({state})', _ratio(mu, v(f'M_r_{x}')),
            t(f'M_u_{x}'), t(f'M_r_{x}'), 'Mu / φMn', ['flexure', 'phi'], [f'M_u_{x}', f'd_{x}', f'A_s_{x}', f'a_{x}', f'M_n_{x}', f'M_r_{x}'], geometry_pending)
        add(f'min_{x}', 'Backwall', f'Minimum flexural steel · {face}', _ratio(v(f'M_min_{x}'), v(f'M_r_{x}')),
            t(f'M_min_{x}'), t(f'M_r_{x}'), 'min(Mcr, 1.33 Mu) / φMn', ['min_flexure'], [f'S_c_{x}', 'f_r', f'M_cr_{x}', f'M_min_{x}', f'M_r_{x}'])
        add(f'strain_{x}', 'Backwall', f'Tension-controlled section · {face}', _ratio(0.005, v(f'eps_t_{x}')),
            '0.005', f'{v(f"eps_t_{x}"):.4f}', 'εt,limit / εt (φ = 0.90 verified when ≤ 1)', ['phi'], [f'c_{x}', f'eps_t_{x}', f'phi_{x}'])
        fss = v(f'f_ss_{x}')
        stress = _ratio(fss, v('f_ss_lim'))
        spacing = _ratio(v(f's_{x}'), v(f's_cr_{x}')) if fss > 0 else 0.0
        add(f'crack_{x}', 'Backwall', f'Crack control · {face}', max(stress, spacing),
            f'{t(f"s_{x}")} · fss {t(f"f_ss_{x}")}', f'{t(f"s_cr_{x}")} · {t("f_ss_lim")}',
            'max(s / s_max, fss / 0.80 fy)', ['crack_control', 'crack_fdot'], [f'f_ss_{x}', f'beta_s_{x}', f's_cr_{x}', 'f_ss_lim'])
        add(f'spacing_{x}', 'Backwall', f'Maximum bar spacing · {face}', _ratio(v(f's_{x}'), v('s_max_bw')),
            t(f's_{x}'), t('s_max_bw'), 's / min(1.5h, 18 in)', ['max_spacing'], ['s_max_bw'])
    ts_v = max(_ratio(v('A_ts_bw'), min(v('A_pr_FF'), v('A_pr_SF'))), _ratio(max(v('s_FF'), v('s_SF')), v('s_ts_bw')))
    add('ts_vert', 'Backwall', 'Shrinkage & temperature · vertical, each face', ts_v,
        t('A_ts_bw'), f'{min(v("A_pr_FF"), v("A_pr_SF")):.3f} in²/ft', 'max(As,req / As,prov, s / s_max)', ['temp_shrink'], ['b_ts_bw', 'A_ts_bw', 'A_pr_FF', 'A_pr_SF', 's_ts_bw'])
    ts_h = max(_ratio(v('A_ts_bw'), v('A_pr_HZ')), _ratio(v('s_HZ'), v('s_ts_bw')))
    add('ts_horiz', 'Backwall', 'Shrinkage & temperature · horizontal, each face', ts_h,
        t('A_ts_bw'), t('A_pr_HZ'), 'max(As,req / As,prov, s / s_max)', ['temp_shrink'], ['A_ts_bw', 'A_pr_HZ', 's_ts_bw'])
    add('shear_bw', 'Backwall', 'Shear at the construction joint (both strap states)', _ratio(v('V_u_bw'), v('V_r_bw')),
        t('V_u_bw'), t('V_r_bw'), 'Vu / φVn', ['shear', 'shear_depth'], ['V_u_bw', 'd_v_FF', 'V_c_FF', 'V_n_FF', 'V_r_bw'])
    add('interface_bw', 'Backwall', 'Interface shear at the backwall construction joint', _ratio(v('V_u_bw'), v('V_ri_bw')),
        t('V_u_bw'), t('V_ri_bw'), 'Vu / φVni', ['interface', 'interface_fdot'], ['A_cv_bw', 'A_vf_bw', 'V_ni_bw', 'V_ri_bw'],
        note='SDG 1.15: add a plan note requiring the joint to be intentionally roughened to a 1/4 in amplitude.')
    add('interface_min_bw', 'Backwall', 'Minimum interface reinforcement', _ratio(v('A_vfmin_bw'), v('A_vf_bw')),
        t('A_vfmin_bw'), t('A_vf_bw'), 'Avf,min / Avf', ['interface_min'], ['A_vfmin_bw', 'A_vf_bw'])
    cover_req = 3.0
    add('cover_bw', 'Backwall', 'Concrete cover · backwall', _ratio(cover_req, v('cv_bw')), f'{cover_req:g} in', t('cv_bw'),
        'required / provided (exterior formed substructure, S/M)', ['cover'], ['cv_bw'], not conf['exposure'])
    add('thickness_bw', 'Backwall', 'Backwall thickness (SDM 12.6.B)', _ratio(12.0, v('t_bw')), '12 in', t('t_bw'),
        'guideline / provided', ['wall_dims'], ['t_bw'])

    mu = v('M_u_CK')
    add('flex_CK', 'Cheek walls', 'Flexure · wind (either face)', _ratio(mu, v('M_r_CK')), t('M_u_CK'), t('M_r_CK'),
        'Mu / φMn', ['flexure', 'wind'], ['P_Z_III', 'M_u_CK', 'd_CK', 'A_s_CK', 'M_r_CK'], not conf['wind_kz'])
    add('min_CK', 'Cheek walls', 'Minimum flexural steel', _ratio(v('M_min_CK'), v('M_r_CK')), t('M_min_CK'), t('M_r_CK'),
        'min(Mcr, 1.33 Mu) / φMn', ['min_flexure'], ['M_cr_CK', 'M_min_CK', 'M_r_CK'])
    add('strain_CK', 'Cheek walls', 'Tension-controlled section', _ratio(0.005, v('eps_t_CK')), '0.005', f'{v("eps_t_CK"):.4f}',
        'εt,limit / εt', ['phi'], ['eps_t_CK', 'phi_CK'])
    fss = v('f_ss_CK')
    add('crack_CK', 'Cheek walls', 'Crack control', max(_ratio(fss, v('f_ss_lim')), _ratio(v('s_CK'), v('s_cr_CK')) if fss > 0 else 0.0),
        f'{t("s_CK")} · fss {t("f_ss_CK")}', f'{t("s_cr_CK")} · {t("f_ss_lim")}', 'max(s / s_max, fss / 0.80 fy)',
        ['crack_control', 'crack_fdot'], ['P_Z_SER', 'M_s_CK', 'f_ss_CK', 's_cr_CK'])
    add('spacing_CK', 'Cheek walls', 'Maximum bar spacing', _ratio(v('s_CK'), v('s_max_ck')), t('s_CK'), t('s_max_ck'),
        's / min(1.5h, 18 in)', ['max_spacing'], ['s_max_ck'])
    add('ts_CK', 'Cheek walls', 'Shrinkage & temperature · both directions', max(_ratio(v('A_ts_ck'), min(v('A_pr_CK'), v('A_pr_CKH'))),
        _ratio(max(v('s_CK'), v('s_CKH')), v('s_ts_ck'))), t('A_ts_ck'), f'{min(v("A_pr_CK"), v("A_pr_CKH")):.3f} in²/ft',
        'max(As,req / As,prov, s / s_max)', ['temp_shrink'], ['A_ts_ck', 'A_pr_CK', 'A_pr_CKH', 's_ts_ck'])
    add('shear_CK', 'Cheek walls', 'Shear at the base', _ratio(v('V_u_CK'), v('V_r_CK')), t('V_u_CK'), t('V_r_CK'),
        'Vu / φVn', ['shear'], ['V_u_CK', 'V_r_CK'])
    add('interface_CK', 'Cheek walls', 'Interface shear at the cheek-wall joint', _ratio(v('V_u_CK'), v('V_ri_ck')),
        t('V_u_CK'), t('V_ri_ck'), 'Vu / φVni', ['interface', 'interface_fdot'], ['A_cv_ck', 'V_ni_ck', 'V_ri_ck'])
    required_ck_cover = v('cv_ck') if v('single_ck') == 1 else 2.0
    add('cover_CK', 'Cheek walls', 'Concrete cover · cheek walls', _ratio(required_ck_cover, v('cover_ck_actual')), f'{required_ck_cover:g} in', t('cover_ck_actual'),
        'required / actual cover (centered mat includes both tangent directions)', ['cover'], ['cv_ck', 'cover_ck_actual'], not conf['exposure'])
    add('interface_min_CK', 'Cheek walls', 'Minimum interface reinforcement', _ratio(v('A_vfmin_ck'), v('A_s_CK')),
        t('A_vfmin_ck'), t('A_s_CK'), 'Avf,min / As crossing the joint', ['interface_min'], ['A_vfmin_ck', 'A_s_CK'], not conf['cheek_connection'])
    add('thickness_CK', 'Cheek walls', 'Cheek wall thickness (SDM 12.6.B)', _ratio(8.0, v('t_ck')), '8 in', t('t_ck'),
        'guideline / provided', ['wall_dims'], ['t_ck'])

    governing = max(STRENGTH, key=lambda c: v(f'f_str_{c["key"]}'))
    add('strap_load', 'Tie-back straps', 'Tie-back loads for the plans (per foot of backwall)', None,
        f'Service {t("f_str_s")}', f'Factored {t("f_str_u")} ({governing["label"]})',
        'Report on the end bent sheets for the Specialty Engineer', ['strap_plans'], ['f_str_s', 'f_str_u', 'F_str_s', 'F_str_u'],
        note='Plan note (SDM 12.3.F): "The soil reinforcement attached to the backwall shall be designed by a Specialty Engineer for the service and factored loads as shown using the design criteria for permanent MSE walls. Cost of furnishing and installing the soil reinforcement is considered incidental to the cost of the end bent."')
    add('strap_height', 'Tie-back straps', 'Strap within the retained backwall height', _ratio(v('z_strap'), v('H_bw_edge')),
        t('z_strap'), t('H_bw_edge'), 'z_strap / backwall edge height', ['soil_reinforcement'], ['z_strap', 'H_bw_edge', 'y_strap'],
        not conf['strap_level'])
    add('strap_pile', 'Tie-back straps', 'Pile-head force implied by the strap location', None,
        ' / '.join(f'{c["label"]} {t("V_pile_" + c["key"], 1)}' for c in COMBINATIONS), 'Positive = piles push the cap toward the span',
        'M / y_strap − H with pinned piles; the design strap force is max(H, M / y_strap). A strap at the resultant height e makes this zero.',
        ['soil_reinforcement'], [f'e_{governing["key"]}', f'F_eq_{governing["key"]}', f'V_pile_{governing["key"]}'],
        note='This pile-head force is not in the FBMP model. Raise the strap toward the resultant height or confirm the piles carry it.')

    add('prereq_settlement', 'Prerequisites', 'Soil reinforcement may be attached (≤ 2 in settlement above the cap bottom)', None,
        'Geotechnical confirmation', 'SDG 3.13.2.N.3', CONFIRMATIONS['settlement'], ['soil_reinforcement'], [], not conf['settlement'])
    for key, label in (('strap_level', 'Strap elevation coordinated with an MSE reinforcement level'),
                       ('geometry', 'Adopted CAD geometry incorporated'),
                       ('shrinkage', 'Shrinkage strain confirmed'),
                       ('landing', 'Landing slab bearing and tributary length confirmed'),
                       ('analysis', 'Current bearing actions and common-end-bent envelope'),
                       ('cheek_connection', 'Cheek mat anchorage and cap/lug load path')):
        add('prereq_' + key, 'Prerequisites', label, None, 'Confirmation', 'Recorded in Sources & assumptions',
            CONFIRMATIONS[key], [], [], not conf[key])
    for check in checks:
        if check.group == 'Prerequisites' and check.status == 'INFO':
            check.status = 'CONFIRMED'

    t_max = e.cap['torsion_max']
    add('cap_torsion', 'Cap supplement', 'Cap torsion from walls, bearings and straps (screen)', _ratio(t_max, v('T_lim')),
        f'{t_max:.2f} kip-ft ({e.cap["torsion_combo"]})', t('T_lim'), 'Tu / 0.25 φ Tcr (torsion may be neglected when ≤ 1)',
        ['torsion_threshold'], ['A_cp', 'p_cp', 'T_cr', 'T_lim'],
        note='Not in the FBMP cap model (FBMP torque 3.18 kip-ft). Pass to the cap notebook as a supplement if the screen fails.')
    return checks


def cap_supplement(e):
    """Torsion and weak-axis bending along the cap from discrete loads vs uniform straps.

    Piles are taken as torsionally free (fixity 0.10 in FBMP), so the strap restraint
    distributed along the backwall balances the overturning moment.
    """
    v = e.value
    L = v('L_load', 'in'); Lb = v('L_bw', 'in'); s = v('s_brg', 'in'); n = int(round(v('N_brg')))
    stations = [L / 2 + (i - (n - 1) / 2) * s for i in range(n)] if n > 1 else [L / 2]
    bw0, bw1 = (L - Lb) / 2, (L + Lb) / 2
    tck = v('t_ck', 'in')
    results = {}
    for c in STRENGTH:
        k = c['key']
        terms = combination_terms(c, {**{a: v(a, 'in') for a in ('x_brg', 'x_cap', 'x_ped', 'x_ck', 'x_bw')},
                                      **{f: v(f, 'kip') for f in ('FZ_WS1', 'FZ_WS2', 'FZ_WS3')}})
        dist_t = []      # (x0, x1, torque per inch, kip-ft/in)
        point_t = []     # (x, torque kip-ft)
        dist_h = []      # (x0, x1, kip per inch)
        point_h = []
        for term in terms:
            if not term['factor']:
                continue
            force = v(term['force'], 'kip') * term['factor']
            arm = v(term['arm'], 'ft')
            if term['item'] in ('EH', 'ES', 'LS'):
                dist_t.append((0, L, force * arm / L)); dist_h.append((0, L, force / L))
            elif term['item'] in ('TU', 'SH', 'WS'):
                for x in stations:
                    point_t.append((x, force * arm / n)); point_h.append((x, force / n))
            elif term['item'] in ('DCb', 'PLb', 'ped', 'WSV'):
                for x in stations:
                    point_t.append((x, force * arm / n))
            elif term['item'] == 'cap':
                core = v('L_cap', 'in'); start = (L-core)/2
                dist_t.append((start, start+core, force * arm / core))
            elif term['item'] == 'bw':
                dist_t.append((bw0, bw1, force * arm / Lb))
            elif term['item'] == 'ck':
                point_t += [(tck / 2, force * arm / 2), (L - tck / 2, force * arm / 2)]
        moment = v(f'M_{k}', 'kip*ft'); horizontal = v(f'H_{k}', 'kip')
        dist_t.append((bw0, bw1, -moment / Lb)); dist_h.append((bw0, bw1, -horizontal / Lb))
        xs = sorted({0.0, L, bw0, bw1, *stations, tck / 2, L - tck / 2, *[i * L / 200 for i in range(201)]})
        torsion, shear, bending = [], [], []
        for x in xs:
            T = sum(w * (min(x, b) - a) for a, b, w in dist_t if x > a) + sum(p for xp, p in point_t if xp <= x + 1e-9)
            V = sum(w * (min(x, b) - a) for a, b, w in dist_h if x > a) + sum(p for xp, p in point_h if xp <= x + 1e-9)
            M = (sum(w * (min(x, b) - a) * (x - (a + min(x, b)) / 2) for a, b, w in dist_h if x > a)
                 + sum(p * (x - xp) for xp, p in point_h if xp <= x + 1e-9)) / 12
            torsion.append(T); shear.append(V); bending.append(M)
        results[k] = dict(x_in=xs, torsion=torsion, weak_shear=shear, weak_moment=bending,
                          torsion_max=max(abs(T) for T in torsion), weak_max=max(abs(M) for M in bending),
                          closure=torsion[-1], stations=stations)
    governing = max(results, key=lambda k: results[k]['torsion_max'])
    label = next(c['label'] for c in STRENGTH if c['key'] == governing)
    return dict(by_combo=results, torsion_max=results[governing]['torsion_max'], torsion_combo=label,
                weak_max=max(r['weak_max'] for r in results.values()), stations=stations, backwall=(bw0, bw1))


def wall_diagrams(e, combo_key):
    """Shear and moment up the backwall height for both strap states (1-ft strip)."""
    v = e.value
    combo = next(c for c in COMBINATIONS if c['key'] == combo_key)
    eh, es, ls = _soil_factors(combo)
    H = v('H_bw', 'ft'); ka = v('k_a'); gs = v('gamma_s', 'kip/ft^3')
    p_unif = es * v('p_ES', 'kip/ft^2') + ls * v('p_LS', 'kip/ft^2')
    f = v(f'f_str_{combo_key}', 'kip/ft'); zs = v('z_strap', 'ft')
    rows = []
    for i in range(101):
        z = H * i / 100            # height above the construction joint
        depth = H - z              # soil depth acting above this level
        V_soil = eh * 0.5 * ka * gs * depth ** 2 + p_unif * depth
        M_soil = eh * ka * gs * depth ** 3 / 6 + p_unif * depth ** 2 / 2
        strap_v = f if z < zs else 0.0
        strap_m = f * (zs - z) if z < zs else 0.0
        rows.append(dict(z=z, pressure=eh * ka * gs * depth + p_unif,
                         V_slack=V_soil, M_slack=-M_soil, V_eng=V_soil - strap_v, M_eng=strap_m - M_soil))
    return rows


def evaluate(case=None):
    case = upgrade_case(case or default_case())
    validate_case(case)
    externals = input_externals(case)
    stage = Engine(base_definitions(), externals=dict(externals))
    signs = {a: stage.get(a).v for a in ('x_brg', 'x_cap', 'x_ped', 'x_ck', 'x_bw')}
    signs.update({f: externals[f].v for f in ('FZ_WS1', 'FZ_WS2', 'FZ_WS3')})
    definitions = all_definitions(signs)
    shadowed = sorted({d['name'] for d in definitions} & set(externals))
    if shadowed:
        raise ValueError('Formula names duplicate input names: ' + ', '.join(shadowed))
    engine = Engine(definitions, externals=dict(externals))
    try:
        engine.all()
    except (ValueError, AssertionError, ZeroDivisionError, TypeError) as exc:
        raise ValueError(f'Calculation stopped: {exc}') from exc
    units = {d['name']: d['unit'] for d in INPUT_SPEC}
    units.update(EXTERNAL_UNITS)
    units.update({d['name']: d['unit'] for d in definitions})
    terms = {c['key']: combination_terms(c, signs) for c in COMBINATIONS}
    e = Evaluation(case=case, engine=engine, definitions=definitions, units=units, terms=terms)
    e.cap = cap_supplement(e)
    e.checks = build_checks(e)
    from .reviews import apply_reviews
    apply_reviews(e)
    return e


def strap_table(e, combo_key):
    """Rows of the overturning table: nominal and factored force, arm and moment."""
    rows = []
    for term in e.terms[combo_key]:
        force = e.value(term['force'], 'kip')
        arm = e.value(term['arm'], 'ft')
        rows.append(dict(term, force_kip=force, arm_ft=arm, moment=force * arm,
                         factored_force=term['factor'] * force if term['kind'] == 'H' else 0.0,
                         factored_moment=term['factor'] * force * arm))
    return rows


def formula_trace(e):
    from .notation import definition_mathml
    out = []
    for d in e.definitions:
        out.append(dict(name=d['name'], section=d['section'], caption=d['caption'], unit=d['unit'],
                        refs=d['refs'], formula=d['formula'],
                        mathml=definition_mathml(d['name'], parse(d['expr']), e.engine, e.units, d['unit'])))
    return out
