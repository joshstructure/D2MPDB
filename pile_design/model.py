"""Pile analysis and design: prestressed concrete square piles and steel pipe piles.

Closed-form quantities are unit-aware formulas evaluated by the shared C005 engine (inch,
kip, radian) so the report can show each equation with substituted values. The numerical
results (strain-compatibility interaction curve, governing FBMP records) enter the engine as
externals and the closed forms continue from them. Structural demands are the FBMP pile
forces plus the drag load DR (LRFD Table 3.4.1-1); the geotechnical bearing resistance
follows SDG Eq. 3-1 with the downdrag added nominally.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from pier_cap.engine import Engine, Q, parse
from . import loads, sections

DATA = Path(__file__).parent / 'data'
INPUT_SPEC = json.loads((DATA / 'inputs.json').read_text(encoding='utf-8'))
INPUTS = {d['name']: d for d in INPUT_SPEC}
REFERENCES = json.loads((DATA / 'references.json').read_text(encoding='utf-8'))
SOURCES = json.loads((DATA / 'sources.json').read_text(encoding='utf-8'))
PRESETS = json.loads((DATA / 'presets.json').read_text(encoding='utf-8'))
STANDARD_PLANS = json.loads((DATA / 'standard_plans.json').read_text(encoding='utf-8'))
FORMAT = 'd2mpdb-pile-design'
SCHEMA_VERSION = 1
FAMILIES = ('psc', 'pipe')

CONFIRMATIONS = {
    'exposure': 'Environment classification confirmed for the SDG 1.4 covers, the Table 3.5.1-1 minimum size and the LRFD 5.9.2.3.2b tension limit used.',
    'head_connection': 'Pile-to-cap moment and uplift transfer with 12 in embedment verified in the coordinated detail (SDG 3.5.1.C, SDM 11.6).',
    'steel_grade': 'Steel pipe grade and Fy reconciled: Spec 962 Table 962-11 A252 Gr 3 (45 ksi) against the Fy of the FBMP pile material.',
    'corrosion': 'Corrosion allowance and wall loss confirmed for the environment (LRFD 10.7.5, 5.12.9.5.2).',
    'downdrag_source': 'Downdrag of 18 tons per end-bent pile documented by the geotechnical engineer of record (neutral plane, scourable layers).',
    'analysis_current': 'FBMP export matches the selected cap case and the final rerun (COH-013, COH-028).',
    'min_tip': 'Minimum tip elevation received from the geotechnical handoff (SDG 3.5.9).',
    'scour': 'Scour resistance and scour elevations received from the hydraulics and geotechnical engineers.',
    'drivability': 'Drivability and driving stresses evaluated (LRFD 10.7.8, FDOT Specification 455); not computed here.',
}
PIPE_ONLY = ('steel_grade', 'corrosion')

DATA_TABLE_COLUMNS = [
    ('A', 'Pier / Bent'), ('B', 'Pile Size & Type'), ('C', 'Nominal Bearing Resistance (tons)'), ('D', 'Tension Resistance (tons)'),
    ('E', 'Minimum Tip Elevation (ft)'), ('F', 'Test Pile Length / Pile Order Length (ft)'), ('G', 'Required Jet Elevation (ft)'),
    ('H', 'Required Preform Elevation (ft)'), ('I', 'Factored Design Load (tons)'), ('J', 'Downdrag (tons)'),
    ('K', 'Total Scour Resistance (tons)'), ('L', 'Net Scour Resistance (tons)'), ('M', '100-Year Scour Elevation (ft)'),
    ('N', 'Design Scour Elevation (temporary bridges)'), ('O', 'Long-Term Scour Elevation (ft)'), ('P', 'Resistance Factor'),
    ('Q', 'Pile Cut-Off Elevation (ft)')]

_UNIT_ENGINE = Engine([])


def unit_quantity(unit):
    return Q(1.0) if unit in (None, 'bar') else _UNIT_ENGINE.eval(parse('1 ' + unit), {})


# ----------------------------------------------------------------------------- case
def _base_case(support):
    if support not in PRESETS:
        raise ValueError(f'Unknown support {support!r}; choose {", ".join(PRESETS)}.')
    preset = PRESETS[support]
    inputs = {d['name']: d['value'] for d in INPUT_SPEC}
    inputs.update(preset.get('inputs', {}))
    sources = {d['name']: {'source': d['source'], 'status': d['status']} for d in INPUT_SPEC}
    for name, text in preset.get('sources', {}).items():
        sources[name] = {'source': text, 'status': 'pending confirmation'}
    return {
        'format': FORMAT, 'schema_version': SCHEMA_VERSION, 'name': preset['name'], 'support': support,
        'family': preset['family'], 'inputs': inputs, 'units': {d['name']: d['unit'] for d in INPUT_SPEC},
        'sources': sources, 'psc': deepcopy(preset['psc']), 'analysis': None,
        'confirmations': {k: False for k in CONFIRMATIONS}, 'confirmation_evidence': {}, 'receipts': {}, 'reviews': {}}


def default_case(support='End Bent 1', load_xml=True):
    """Preset case. The registered FBMP export is read from project_current when the file is present."""
    case = _base_case(support)
    select_psc(case, case['psc']['index'], case['psc']['pattern'], keep_diameter=case['family'] == 'pipe')
    if load_xml:
        from .sources import apply_source, registered_path
        path = registered_path(PRESETS[support]['xml'])
        if path.exists():
            apply_source(case, PRESETS[support]['xml'], path.read_bytes(), path.name)
    return case

def select_psc(case, index, pattern=None, keep_diameter=False):
    """Choose the Standard Plans index and strand pattern; sets the pile size and spiral from the index."""
    if index not in STANDARD_PLANS['indexes']:
        raise ValueError(f'Unknown Standard Plans index {index!r}.')
    plan = STANDARD_PLANS['indexes'][index]
    ids = [o['id'] for o in plan['options']]
    pattern = pattern or ids[0]
    if pattern not in ids:
        raise ValueError(f'Index {index} has no pattern {pattern!r}; choose {", ".join(ids)}.')
    case['psc'] = {'index': index, 'pattern': pattern}
    if not keep_diameter:
        case['inputs']['D_pile'] = float(plan['size_in'])
        case['sources']['D_pile'] = {'source': f'Standard Plans Index {index}', 'status': 'project source'}
    case['inputs']['spiral_wire_area'] = plan['spiral_area_in2']
    case['inputs']['spiral_pitch'] = plan['spiral_pitch_in']
    case['sources']['spiral_wire_area'] = {'source': f'Standard Plans Index {index} {plan["spiral_wire"]}: {plan["spiral_note"]}', 'status': 'code'}
    return case


def plan_option(case):
    plan = STANDARD_PLANS['indexes'][case['psc']['index']]
    option = next(o for o in plan['options'] if o['id'] == case['psc']['pattern'])
    return plan, option


def upgrade_case(case):
    """Fill new inputs with defaults; never invent values for a changed schema."""
    case = deepcopy(case)
    if case.get('format') != FORMAT:
        raise ValueError('This is not a pile design case. Load a file saved by this notebook.')
    if int(case.get('schema_version', 0)) > SCHEMA_VERSION:
        raise ValueError(f'This case uses schema {case["schema_version"]}; this notebook supports {SCHEMA_VERSION}. Use the newer notebook.')
    support = case.get('support') if case.get('support') in PRESETS else 'End Bent 1'
    base = _base_case(support)
    case.setdefault('support', support)
    case.setdefault('family', base['family'])
    case.setdefault('psc', deepcopy(base['psc']))
    case.setdefault('analysis', None)
    for key in ('inputs', 'units', 'sources'):
        merged = deepcopy(base[key])
        merged.update(case.get(key, {}))
        case[key] = merged
    merged = {k: False for k in CONFIRMATIONS}
    merged.update(case.get('confirmations', {}))
    case['confirmations'] = {k: bool(v) for k, v in merged.items() if k in CONFIRMATIONS}
    case['units'] = base['units']
    for key in ('receipts', 'reviews', 'confirmation_evidence'):
        case.setdefault(key, {})
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
    """Set an input; keep derived defaults (length above ground, Lv) and the pipe diameter in step."""
    p = case['inputs']
    if p.get(name) == value:
        return
    before = None
    if p.get('EL_cutoff') is not None and p.get('EL_ground') is not None:
        before = p['EL_cutoff'] - p['EL_ground']
    old_lu = p.get('L_unsupported')
    p[name] = value
    if case.get('family') == 'pipe' and name in ('D_pile', 'D_out'):
        p['D_pile'] = p['D_out'] = value
    if name in ('EL_cutoff', 'EL_ground') and before is not None and old_lu is not None and abs(old_lu - before) < 1e-6:
        p['L_unsupported'] = round(p['EL_cutoff'] - p['EL_ground'], 6)
        if p.get('L_v') is not None and abs(p['L_v'] - old_lu) < 1e-6:
            p['L_v'] = p['L_unsupported']
    reconcile_confirmations(case)


def validate_case(case):
    problems = []
    for name, spec in INPUTS.items():
        value = case['inputs'].get(name)
        if value is None and spec.get('optional'):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            problems.append(f'{name}: enter a number')
    if case.get('family') not in FAMILIES:
        problems.append('family: choose psc or pipe')
    p = case['inputs']
    if not problems:
        positive = ['D_pile', 'N_pile', 'S_pile', 'embed_cap', 'phi_geo', 'K_eff', 'n_h', 'S_u', 'min_size_policy', 'lambda_c']
        family = case['family']
        if family == 'psc':
            positive += ['fc', 'w_c', 'K_1', 'f_pu', 'f_py', 'E_p', 'd_edge', 'spiral_wire_area', 'spiral_pitch', 'f_y_spiral', 'a_g', 'phi_v', 'phi_c', 'phi_t', 'n_sweep']
        else:
            positive += ['D_out', 't_wall', 'Fy', 'E_s', 'phi_c_axial', 'phi_c_comb', 'phi_f', 'phi_v_steel', 'phi_y', 'L_v']
        problems += [f'{n}: must be greater than zero' for n in positive if p[n] <= 0]
        for n in ('DD_tons', 'R_scour_net_tons', 'R_scour_total_tons', 'gamma_DR_str', 'gamma_DR_ser', 't_corr', 'loss_frac'):
            if p[n] < 0:
                problems.append(f'{n}: cannot be negative')
        if int(p['N_pile']) != p['N_pile']:
            problems.append('N_pile: use a whole number')
        if p['soil_type'] not in (0, 1):
            problems.append('soil_type: use 0 for sand or 1 for clay')
        if p['environment'] not in (1, 2, 3):
            problems.append('environment: use 1, 2 or 3')
        if p['loss_frac'] >= 1:
            problems.append('loss_frac: must be below 1')
        if family == 'psc':
            plan = STANDARD_PLANS['indexes'].get(case.get('psc', {}).get('index'))
            if not plan:
                problems.append('psc.index: choose a Standard Plans index (455-014, -018, -024, -030)')
            else:
                if case['psc'].get('pattern') not in [o['id'] for o in plan['options']]:
                    problems.append(f'psc.pattern: not an option of Index {case["psc"]["index"]}')
                if abs(p['D_pile'] - plan['size_in']) > 1e-6:
                    problems.append(f'D_pile: Index {case["psc"]["index"]} is a {plan["size_in"]:g} in pile; use select_psc to change size')
                elif p['d_edge'] >= p['D_pile'] / 2:
                    problems.append('d_edge: must be less than half the pile size')
        else:
            if abs(p['D_pile'] - p['D_out']) > 1e-9:
                problems.append('D_pile and D_out: the pipe outside diameter must match')
            if p['t_corr'] >= p['t_wall'] or 2 * (p['t_wall'] - p['t_corr']) >= p['D_out']:
                problems.append('t_wall and t_corr: wall thickness after corrosion must be positive and less than D/2')
    if problems:
        raise ValueError('Check inputs: ' + '; '.join(problems))
    return True


# ----------------------------------------------------------------------------- definitions
def _d(section, name, expr, unit, caption, refs=()):
    return {'section': section, 'name': name, 'formula': f'{name} = {expr}', 'expr': expr,
            'unit': unit, 'caption': caption, 'refs': list(refs)}


SECTIONS = [
    ('geometry', '1. Pile layout and downdrag'),
    ('psc_mat', '2. Concrete and prestress'),
    ('psc_axial', '3. Axial resistance'),
    ('psc_flex', '4. Combined axial load and biaxial flexure'),
    ('psc_tension', '5. Tension'),
    ('psc_shear', '6. Shear'),
    ('psc_service', '7. Service I stresses'),
    ('pipe_sec', '2. Pipe section'),
    ('pipe_axial', '3. Axial compression'),
    ('pipe_flex', '4. Flexure'),
    ('pipe_comb', '5. Combined axial load and flexure'),
    ('pipe_tension', '6. Tension'),
    ('pipe_shear', '7. Shear'),
    ('geotech', '8. Geotechnical resistance and Pile Data Table'),
]

PI_DISC = '0.785398163397448'     # pi/4
PI_64 = '0.0490873852123405'      # pi/64


def common_definitions(family):
    g, t = 'geometry', 'geotech'
    d = [
        _d(g, 'S_min', '3*D_pile', 'in', 'Minimum center-to-center pile spacing, 3.0 diameters', ['pile_spacing']),
        _d(g, 's_over_D', 'S_pile/D_pile', None, 'Provided spacing in pile diameters', ['pile_spacing']),
        _d(g, 'DD', 'DD_tons*2 kip', 'kip', 'Downdrag (drag load DR) per pile, nominal', ['drag_load', 'downdrag_plans']),
        _d(g, 'DR_str', 'gamma_DR_str*DD', 'kip', 'Factored drag load, strength limit states (structural)', ['drag_load']),
        _d(g, 'DR_ser', 'gamma_DR_ser*DD', 'kip', 'Drag load, Service I', ['drag_load']),
        _d(t, 'FDL_tons', 'FDL_fbmp/(2 kip)', None, 'Factored Design Load, tons (strength head compression, without DD)', ['data_table']),
        _d(t, 'R_scour_net', 'R_scour_net_tons*2 kip', 'kip', 'Net scour resistance', ['nbr']),
        _d(t, 'R_n_req', '(FDL_fbmp + R_scour_net + DD)/phi_geo', 'kip', 'Required nominal bearing resistance, Eq. 3-1', ['nbr', 'phi_geo']),
        _d(t, 'NBR_tons', 'R_n_req/(2 kip)', None, 'Required nominal bearing resistance, tons', ['nbr']),
    ]
    if family == 'psc':
        d.append(_d(t, 'R_drive_max', 'R_drive_tons*2 kip', 'kip', 'Maximum pile driving resistance, Table 3.5.13-1', ['driving_max']))
    return d


def psc_definitions(branch):
    m, a, f, tn, s, sv = 'psc_mat', 'psc_axial', 'psc_flex', 'psc_tension', 'psc_shear', 'psc_service'
    root_fc = 'Sqrt(fc/(1 ksi))*(1 ksi)'
    d = [
        _d(m, 'A_ps', 'N_str*A_str', 'in^2', 'Prestressing steel area', ['std_plans']),
        _d(m, 'f_pj', 'P_jack/A_str', 'ksi', 'Jacking stress per strand', ['std_plans']),
        _d(m, 'f_pe', 'f_pj*(1 - loss_frac)', 'ksi', 'Effective prestress after losses', ['prestress_min']),
        _d(m, 'P_e', 'A_ps*f_pe', 'kip', 'Effective prestress force', ['prestress_min']),
        _d(m, 'A_g', f'D_pile^2 - {PI_DISC}*d_void^2', 'in^2', 'Gross area (chamfers ignored; void subtracted)'),
        _d(m, 'I_g', f'D_pile^4/12 - {PI_64}*d_void^4', 'in^4', 'Gross moment of inertia'),
        _d(m, 'S_g', 'I_g/(D_pile/2)', 'in^3', 'Section modulus'),
        _d(m, 'f_pc_eff', 'P_e/A_g', 'ksi', 'Effective uniform prestress on the gross area', ['prestress_min', 'prestress_fdot']),
        _d(m, 'beta_1', 'Min(0.85, Max(0.65, 0.85 - 0.05*(fc - 4 ksi)/(1 ksi)))', None, 'Stress block factor', ['stress_block']),
        _d(m, 'E_c', '120000*K_1*(w_c/(1 kip/ft^3))^2*(fc/(1 ksi))^0.33*(1 ksi)', 'ksi', 'Concrete modulus', ['modulus']),
        _d(m, 'eps_cu', '0.003', None, 'Concrete crushing strain', ['strain_compat']),
        _d(m, 'k_c', 'Min(0.85, Max(0.75, 0.85 - 0.02*Max(fc - 10 ksi, 0 ksi)/(1 ksi)))', None, 'Ratio of maximum concrete stress to f\'c', ['psc_axial']),
        _d(m, 'eps_pe', 'f_pe/E_p', None, 'Effective prestrain', ['strain_compat']),
        _d(m, 'eps_ce', 'f_pc_eff/E_c', None, 'Concrete decompression strain', ['strain_compat']),
        _d(a, 'P_o', 'k_c*fc*(A_g - A_ps) - A_ps*(f_pe - E_p*eps_cu)', 'kip', 'Axial resistance at zero eccentricity', ['biaxial', 'psc_axial']),
        _d(a, 'P_n_max', '0.85*P_o', 'kip', 'Maximum nominal axial resistance, spiral', ['psc_axial']),
        _d(a, 'P_r_max', 'phi_c*P_n_max', 'kip', 'Maximum factored axial resistance', ['psc_axial', 'phi_psc']),
        _d(a, 'P_bi_lim', '0.10*phi_c*fc*A_g', 'kip', 'Axial load limit between Eqs. 5.6.4.5-1 and -3', ['biaxial']),
    ]
    if branch == 'eq1':
        d += [
            _d(f, 'e_y', 'M_ux_bi/P_u_bi', 'in', 'Eccentricity from the moment about the x axis', ['biaxial']),
            _d(f, 'e_x', 'M_uy_bi/P_u_bi', 'in', 'Eccentricity from the moment about the y axis', ['biaxial']),
            _d(f, 'P_rxy', '1/(1/P_rx + 1/P_ry - 1/(phi_c*P_o))', 'kip', 'Factored axial resistance in biaxial flexure, Eq. 5.6.4.5-1', ['biaxial']),
            _d(f, 'DC_bi', 'P_u_bi/P_rxy', None, 'Demand / capacity, Eq. 5.6.4.5-1', ['biaxial']),
        ]
    else:
        d.append(_d(f, 'DC_bi', 'M_ux_bi/M_rx + M_uy_bi/M_ry', None, 'Demand / capacity, Eq. 5.6.4.5-3', ['biaxial']))
    d += [
        _d(f, 'DC_rs', 'If(M_u_rs > 0.001 kip*ft, M_u_rs/M_r_rs, P_u_rs/P_r_rs)', None,
           'Demand / capacity on the resultant bending axis (ray through the demand)', ['strain_compat']),
        _d(tn, 'P_n_t', 'A_ps*Min(f_py, f_pe + 60 ksi)', 'kip', 'Nominal tension resistance, Eq. 5.8.2.4.1-1 (fy = 60 ksi, no nonprestressed steel)', ['tension_psc']),
        _d(tn, 'P_r_t', 'phi_t*P_n_t', 'kip', 'Factored tension resistance', ['tension_psc', 'phi_psc']),
        _d(tn, 'P_t_yield', 'A_ps*f_py', 'kip', 'Strand yield limit Aps fpy (upper bound)', ['tension_psc']),
        _d(tn, 'DC_t', 'T_u/P_r_t', None, 'Demand / capacity, tension', ['tension_psc']),
        _d(s, 'b_v', 'D_pile - d_void', 'in', 'Effective web width', ['shear_depth']),
        _d(s, 'd_v', 'Max(0.9*d_e, 0.72*D_pile)', 'in', 'Effective shear depth', ['shear_depth']),
        _d(s, 'M_u_v', 'Max(M_u_sh, V_u_sh*d_v)', 'kip*ft', 'Moment not less than Vu dv', ['shear_psc']),
        _d(s, 'N_u', '-P_u_sh', 'kip', 'Axial force, tension positive', ['shear_psc']),
        _d(s, 'f_po', '0.7*f_pu', 'ksi', 'Locked-in strand stress parameter', ['shear_psc']),
        _d(s, 'F_long', 'M_u_v/d_v + 0.5*N_u + V_u_sh - A_ps_t*f_po', 'kip', 'Longitudinal force demand in the numerator of Eq. 5.7.3.4.2-4', ['shear_psc']),
        _d(s, 'eps_s0', 'F_long/(E_p*A_ps_t)', None, 'Longitudinal strain, Eq. 5.7.3.4.2-4', ['shear_psc']),
        _d(s, 'A_ct', 'A_g/2', 'in^2', 'Concrete on the flexural tension side', ['shear_psc']),
        _d(s, 'eps_s1', 'F_long/(E_p*A_ps_t + E_c*A_ct)', None, 'Strain with Ec Act in the denominator (when eps_s0 is negative)', ['shear_psc']),
        _d(s, 'eps_s', 'Max(If(eps_s0 < 0, eps_s1, eps_s0), -0.0004)', None, 'Longitudinal strain used (not less than -0.40E-3)', ['shear_psc']),
        _d(s, 's_x', 'd_v', 'in', 'Crack spacing parameter (no longitudinal crack-control steel)', ['shear_psc']),
        _d(s, 's_xe', 'Min(80 in, Max(12 in, s_x*1.38/((a_g + 0.63 in)/(1 in))))', 'in', 'Equivalent crack spacing, Eq. 5.7.3.4.2-7', ['shear_psc']),
        _d(s, 'A_v', '2*spiral_wire_area', 'in^2', 'Spiral area crossing the shear plane (two legs)', ['shear_psc']),
        _d(s, 'A_v_min', f'0.0316*lambda_c*{root_fc}*b_v*spiral_pitch/f_y_spiral', 'in^2', 'Minimum transverse reinforcement', ['av_min']),
        _d(s, 'beta_v', 'If(A_v >= A_v_min, 4.8/(1 + 750*eps_s), 4.8/(1 + 750*eps_s)*51/(39 + s_xe/(1 in)))', None,
           'Shear parameter beta, Eq. 5.7.3.4.2-1 or -2', ['shear_psc']),
        _d(s, 'theta_v', '(29 + 3500*eps_s)*deg', 'deg', 'Crack angle, Eq. 5.7.3.4.2-3', ['shear_psc']),
        _d(s, 'V_c', f'0.0316*beta_v*lambda_c*{root_fc}*b_v*d_v', 'kip', 'Concrete shear resistance', ['shear_psc']),
        _d(s, 'V_s', 'A_v*f_y_spiral*d_v/(Tan(theta_v)*spiral_pitch)', 'kip', 'Spiral shear resistance', ['shear_psc']),
        _d(s, 'V_n', 'Min(V_c + V_s, 0.25*fc*b_v*d_v)', 'kip', 'Nominal shear resistance', ['shear_psc']),
        _d(s, 'V_r', 'phi_v*V_n', 'kip', 'Factored shear resistance', ['shear_psc', 'phi_psc']),
        _d(sv, 'sig_c', 'f_pc_eff + P_sc/A_g + (Abs(Mx_sc) + Abs(My_sc))/S_g', 'ksi', 'Corner compression, Service I after losses', ['service_comp']),
        _d(sv, 'sig_c_lim', '0.6*fc', 'ksi', 'Compression limit 0.60 phi_w f\'c (solid, phi_w = 1)', ['service_comp']),
        _d(sv, 'sig_t', 'f_pc_eff + P_st/A_g - (Abs(Mx_st) + Abs(My_st))/S_g', 'ksi', 'Corner stress on the tension side, Service I (negative = tension)', ['service_tens']),
        _d(sv, 'f_t_net', 'Max(-sig_t, 0 ksi)', 'ksi', 'Net tensile stress', ['service_tens']),
        _d(sv, 'f_t_lim', f'If(environment == 3, Min(0.3 ksi, 0.0948*lambda_c*{root_fc}), Min(0.6 ksi, 0.19*lambda_c*{root_fc}))', 'ksi',
           'Tensile stress limit (0.0948 for Extremely Aggressive)', ['service_tens']),
        _d(sv, 'f_pc_min', '0.7 ksi', 'ksi', 'Minimum uniform prestress after losses', ['prestress_min']),
        _d(sv, 'D_min', 'If(environment == 3, Max(min_size_policy, 18 in), min_size_policy)', 'in', 'Minimum square pile size', ['min_pile_size']),
    ]
    return d


def pipe_definitions():
    sec, ax, fl, cb, tn, sh = 'pipe_sec', 'pipe_axial', 'pipe_flex', 'pipe_comb', 'pipe_tension', 'pipe_shear'
    return [
        _d(sec, 't_des', 't_wall - t_corr', 'in', 'Design wall thickness after corrosion allowance', ['corrosion']),
        _d(sec, 'D_i', 'D_out - 2*t_des', 'in', 'Inside diameter'),
        _d(sec, 'A_g', f'{PI_DISC}*(D_out^2 - D_i^2)', 'in^2', 'Gross area'),
        _d(sec, 'I_g', f'{PI_64}*(D_out^4 - D_i^4)', 'in^4', 'Moment of inertia'),
        _d(sec, 'S_g', 'I_g/(D_out/2)', 'in^3', 'Elastic section modulus'),
        _d(sec, 'Z_p', '(D_out^3 - D_i^3)/6', 'in^3', 'Plastic section modulus'),
        _d(sec, 'r_g', 'Sqrt(I_g/A_g)', 'in', 'Radius of gyration'),
        _d(sec, 'D_t', 'D_out/t_des', None, 'Diameter-to-thickness ratio', ['pipe_local']),
        _d(ax, 'lam_r', '0.11*E_s/Fy', None, 'Nonslender limit 0.11 E/Fy', ['pipe_local']),
        _d(ax, 'A_eff', 'If(D_t <= lam_r, A_g, (0.038*E_s/(Fy*D_t) + 2/3)*A_g)', 'in^2', 'Effective area', ['pipe_local']),
        _d(ax, 'P_o', 'Fy*A_eff', 'kip', 'Squash load', ['pipe_axial']),
        _d(ax, 'E_soil', '0.465*(S_u/(1 kip/ft^2))*(1 ksi)', 'ksi', 'Clay soil modulus 0.465 Su', ['fixity']),
        _d(ax, 'L_fix', 'If(soil_type == 1, 1.4*(E_s*I_g/E_soil)^0.25, 1.8*(E_s*I_g/n_h)^0.2)', 'ft', 'Depth to fixity below ground', ['fixity']),
        _d(ax, 'KL', 'K_eff*(L_unsupported + L_fix)', 'ft', 'Effective length', ['fixity']),
        _d(ax, 'KL_r', 'KL/r_g', None, 'Slenderness ratio KL/r', ['slenderness']),
        _d(ax, 'P_e', '9.869604401089358*E_s*A_g/KL_r^2', 'kip', 'Elastic buckling load', ['pipe_axial']),
        _d(ax, 'Pe_Po', 'P_e/P_o', None, 'Pe / Po', ['pipe_axial']),
        _d(ax, 'P_n', 'If(Pe_Po >= 0.44, 0.658^(P_o/P_e)*P_o, 0.877*P_e)', 'kip', 'Nominal axial resistance', ['pipe_axial']),
        _d(ax, 'P_r_axial', 'phi_c_axial*P_n', 'kip', 'Factored axial resistance', ['pipe_axial', 'pipe_phi']),
        _d(ax, 'P_r_comb', 'phi_c_comb*P_n', 'kip', 'Factored axial resistance, combined loading', ['pipe_axial', 'pipe_phi']),
        _d(fl, 'lam_p', '0.07*E_s/Fy', None, 'Compact limit 0.07 E/Fy', ['pipe_flexure']),
        _d(fl, 'lam_nc', '0.31*E_s/Fy', None, 'Noncompact limit 0.31 E/Fy', ['pipe_flexure']),
        _d(fl, 'M_p', 'Fy*Z_p', 'kip*ft', 'Plastic moment', ['pipe_flexure']),
        _d(fl, 'M_n', 'If(D_t <= lam_p, M_p, Min(M_p, If(D_t <= lam_nc, (0.021*E_s/D_t + Fy)*S_g, 0.33*E_s/D_t*S_g)))', 'kip*ft', 'Nominal flexural resistance', ['pipe_flexure']),
        _d(fl, 'M_r', 'phi_f*M_n', 'kip*ft', 'Factored flexural resistance', ['pipe_flexure', 'pipe_phi']),
        _d(tn, 'P_r_t', 'phi_y*Fy*A_g', 'kip', 'Factored tension resistance, yielding of the gross section', ['pipe_tension']),
        _d(tn, 'DC_t', 'T_u/P_r_t', None, 'Demand / capacity, tension', ['pipe_tension']),
        _d(cb, 'P_abs', 'Abs(P_u_comb)', 'kip', 'Magnitude of the axial force', ['pipe_interaction']),
        _d(cb, 'P_rc', 'If(P_u_comb >= 0 kip, P_r_comb, P_r_t)', 'kip', 'Matching axial resistance (compression, or tension for net uplift)', ['pipe_interaction']),
        _d(cb, 'Pu_Pr', 'P_abs/P_rc', None, 'Pu / Pr', ['pipe_interaction']),
        _d(cb, 'DC_comb', 'If(Pu_Pr >= 0.2, Pu_Pr + 8/9*M_u_comb/M_r, Pu_Pr/2 + M_u_comb/M_r)', None, 'Interaction, Eq. 6.9.2.2.1-1 or -2', ['pipe_interaction']),
        _d(sh, 'F_cr1', '1.6*E_s/(Sqrt(L_v/D_out)*D_t^1.25)', 'ksi', 'Shear buckling stress, Eq. 6.12.1.2.3b-2', ['pipe_shear']),
        _d(sh, 'F_cr2', '0.78*E_s/D_t^1.5', 'ksi', 'Shear buckling stress, Eq. 6.12.1.2.3b-3', ['pipe_shear']),
        _d(sh, 'F_cr', 'Min(Max(F_cr1, F_cr2), 0.58*Fy)', 'ksi', 'Flexural shear buckling resistance', ['pipe_shear']),
        _d(sh, 'V_n', '0.5*F_cr*A_g', 'kip', 'Nominal shear resistance', ['pipe_shear']),
        _d(sh, 'V_r', 'phi_v_steel*V_n', 'kip', 'Factored shear resistance', ['pipe_shear', 'pipe_phi']),
    ]


def all_definitions(family, branch='eq3'):
    return common_definitions(family) + (psc_definitions(branch) if family == 'psc' else pipe_definitions())


# ----------------------------------------------------------------------------- evaluation objects
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
    checks: list = field(default_factory=list)
    records: list = field(default_factory=list)
    governing: dict = field(default_factory=dict)
    curve: dict = field(default_factory=dict)
    data_table: dict = field(default_factory=dict)
    externals: dict = field(default_factory=dict)
    external_meta: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    @property
    def family(self):
        return self.case['family']

    def value(self, name, unit=None):
        q = self.engine.get(name)
        if not isinstance(q, Q):
            return q
        return q.v / unit_quantity(unit or self.units.get(name)).v

    def text(self, name, places=3, unit=None):
        unit = unit or self.units.get(name)
        number = self.value(name, unit)
        label = {'kip*ft': 'kip-ft', 'kip/ft^2': 'ksf', 'kip/ft^3': 'kcf', 'kip/ft': 'klf', 'in^2': 'in²', 'in^3': 'in³',
                 'in^4': 'in⁴', 'ksi/ft': 'ksi/ft'}.get(unit, unit or '')
        return f'{number:.{places}f} {label}'.strip()

    @property
    def strength_dc(self):
        """Largest ratio among the structural checks (STRUCTURAL_CHECKS only)."""
        ratios = [c.ratio for c in self.checks if c.key in STRUCTURAL_CHECKS and isinstance(c.ratio, (int, float))]
        return max(ratios) if ratios else 0.0

    @property
    def max_ratio(self):
        """Largest numerical ratio over all checks, policy and geotechnical included."""
        ratios = [c.ratio for c in self.checks if isinstance(c.ratio, (int, float)) and c.group != 'Prerequisites']
        return max(ratios) if ratios else 0.0

    @property
    def status(self):
        failed = [c for c in self.checks if 'FAIL' in c.status]
        pending = [c for c in self.checks if 'PENDING' in c.status]
        worst = f'largest ratio {self.max_ratio:.2f}'
        if failed:
            return f'{len(failed)} check(s) FAIL · {len(pending)} pending · {worst}'
        if pending:
            return f'All numerical checks pass ({worst}) · {len(pending)} pending item(s) remain'
        return f'All checks pass ({worst})'


STRUCTURAL_CHECKS = ('psc_axial', 'psc_flex_bi', 'psc_flex_res', 'psc_shear', 'psc_tension', 'psc_svc_comp', 'psc_svc_tens',
                     'pipe_axial', 'pipe_comb', 'pipe_shear', 'pipe_tension', 'pipe_klr')


def _status(ratio, pending=False):
    if ratio is None:
        return 'PENDING' if pending else 'INFO'
    if ratio > 1 + 1e-9:
        return 'FAIL'
    return 'PASS · PENDING INPUT' if pending else 'PASS'


def _ratio(a, b):
    return a / b if b else float('inf')


def _ceil(x):
    return int(math.ceil(x - 1e-9))


def _floor(x):
    return int(math.floor(x + 1e-9))


# ----------------------------------------------------------------------------- numerical layer
def input_externals(case):
    out = {}
    for name, spec in INPUTS.items():
        value = case['inputs'].get(name)
        if value is None:
            continue
        out[name] = Q(float(value)) * unit_quantity(spec['unit'])
    return out


def _ext(store, meta, name, value, unit, caption):
    store[name] = Q(float(value)) * unit_quantity(unit)
    meta[name] = (unit, caption)


class _Psc:
    """Section, interaction curve and per-record demand/capacity for the prestressed pile."""

    def __init__(self, case):
        p = case['inputs']
        self.plan, self.option = plan_option(case)
        self.D = p['D_pile']
        self.d_void = float(self.plan['void_in'])
        self.fpe = self.option['jacking_kip'] / self.option['strand_area_in2'] * (1.0 - p['loss_frac'])
        self.layout = sections.strand_layout(self.D, self.option['count'], p['d_edge'])
        self.sec = sections.psc_section(self.D, self.layout, p['fc'], self.fpe, p['E_p'], p['w_c'], p['K_1'], self.d_void,
                                        p['f_pu'], p['f_py'], Aps_each=self.option['strand_area_in2'])
        self.p = p
        self.n = int(p['n_sweep'])
        self.phi_Po = p['phi_c'] * self.sec['Po']
        self.P_limit = 0.10 * p['phi_c'] * p['fc'] * self.sec['Ag']
        self.Pr_max = p['phi_c'] * self.sec['Pn_max']
        self.curve0 = self.curve(0.0)
        self._side = {}
        self.Av = 2.0 * p['spiral_wire_area']
        self.bv = self.D - self.d_void

    _cache = None

    def curve(self, angle):
        key = round(angle, 9)
        if self._cache is None:
            self._cache = {}
        if key not in self._cache:
            self._cache[key] = sections.psc_interaction(self.sec, angle=angle, n_points=self.n,
                                                        phi_c=self.p['phi_c'], phi_t=self.p['phi_t'])
        return self._cache[key]

    @staticmethod
    def angle_of(r):
        """Bending-axis angle of the resultant moment, folded into 0..45 degrees (the square is symmetric)."""
        a = math.atan2(abs(r['M3']), abs(r['M2']))
        return min(a, math.pi / 2 - a)

    def curve_for(self, r, exact=False):
        a = self.angle_of(r)
        if not exact:
            a = math.radians(round(math.degrees(a) * 2.0) / 2.0)
        return self.curve(a), a

    def axial_dc(self, r):
        return r['P_u'] / self.Pr_max if r['P_u'] > 0 else 0.0

    def bi_dc(self, r):
        return sections.psc_biaxial_dc(self.curve0, r['P_u'], r['M2'], r['M3'], self.phi_Po, self.P_limit)['ratio']

    def res_dc(self, r, exact=False):
        curve, _ = self.curve_for(r, exact)
        return sections.ray_capacity(curve, r['P_u'], r['M_res'])[0]

    def shear(self, r, exact=True):
        a = self.angle_of(r)
        if not exact:
            a = math.radians(round(math.degrees(a) * 2.0) / 2.0)
        key = round(a, 9)
        if key not in self._side:
            self._side[key] = sections.psc_tension_side(self.sec, a)
        Aps_t, d_e = self._side[key]
        p = self.p
        out = sections.psc_shear(r['V_res'], r['M_res'] * 12.0, r['P_u'], self.D, self.bv, Aps_t, d_e, self.sec['Ag'], self.sec['Ec'],
                                 p['fc'], self.Av, p['spiral_pitch'], p['f_y_spiral'], p['a_g'], p['f_pu'], p['E_p'], p['lambda_c'], p['phi_v'])
        out.update(Aps_t=Aps_t, d_e=d_e, angle=a)
        return out

    def service(self, r):
        return sections.psc_service_stress(r['P_u'], r['M2'], r['M3'], self.sec['f_pc'], self.sec['Ag'], self.sec['S'])


class _Pipe:
    def __init__(self, case):
        p = case['inputs']
        self.p = p
        self.t = p['t_wall'] - p['t_corr']
        self.sec = sections.pipe_section(p['D_out'], self.t)
        Iw_ft4 = self.sec['I'] / 12.0 ** 4
        self.L_fix = sections.depth_to_fixity(p['E_s'], Iw_ft4, int(p['soil_type']), p['n_h'], p['S_u'])
        self.KL = p['K_eff'] * (p['L_unsupported'] + self.L_fix) * 12.0
        self.axial = sections.pipe_axial(self.sec, p['Fy'], p['E_s'], self.KL, p['phi_c_axial'], p['phi_c_comb'])
        self.flex = sections.pipe_flexure(self.sec, p['Fy'], p['E_s'], p['phi_f'])
        self.Pr_t = sections.pipe_tension(p['Fy'], self.sec['A'], p['phi_y'])
        self.shear = sections.pipe_shear(self.sec, p['Fy'], p['E_s'], p['L_v'] * 12.0, p['phi_v_steel'])

    def axial_dc(self, r):
        return r['P_u'] / self.axial['Pr_axial'] if r['P_u'] > 0 else 0.0

    def comb(self, r):
        Pr = self.axial['Pr_comb'] if r['P_u'] >= 0 else self.Pr_t
        return sections.pipe_interaction_dc(r['P_u'], Pr, r['M_res'], self.flex['Mr'])

    def comb_dc(self, r):
        return self.comb(r)['ratio']

    def shear_dc(self, r):
        return r['V_res'] / self.shear['Vr']


def _rid(r):
    return None if r is None else loads.record_id(r)


def _gov_record(g):
    """Governing record with its D/C and ties attached (a copy)."""
    if g is None:
        return None
    return dict(g['record'], dc=g['dc'], ties=[dict(pile=t['pile'], combination=t['combination'], local_element=t['local_element'], side=t['side'])
                                               for t in g['ties']])


def evaluate(case=None):
    case = upgrade_case(case or default_case())
    validate_case(case)
    p, family = case['inputs'], case['family']
    DD_kip = 2.0 * p['DD_tons']
    analysis = case.get('analysis')
    records = loads.restate(analysis['records'], DD_kip, p['gamma_DR_str'], p['gamma_DR_ser']) if analysis else []
    strength = [r for r in records if r['limit'] == 'strength']
    service = [r for r in records if r['limit'] == 'service']
    zero = dict(P_u=0.0, P_fbmp=0.0, M_res=0.0, V_res=0.0, M2=0.0, M3=0.0)

    externals = input_externals(case)
    meta = {}
    governing, details = {}, {}

    fd = loads.fdl_and_tension(records)
    T_kip, T_record = loads.max_tension(records, 'strength')
    _ext(externals, meta, 'FDL_fbmp', fd['FDL_kip'], 'kip', 'Factored Design Load: maximum strength head compression, FBMP (no downdrag)')
    _ext(externals, meta, 'T_u', T_kip, 'kip', 'Maximum strength uplift, FBMP (drag load does not relieve uplift)')
    def axial_governing(model_obj):
        """Largest P_u / Pr; e.governing[...]['dc'] is that ratio, consistent with the check."""
        gp = loads.governing(strength, lambda r: model_obj.axial_dc(r) if r['P_u'] > 0 else None)
        governing[f'{family}_axial'] = _gov_record(gp)
        _ext(externals, meta, 'P_u_axial', gp['record']['P_u'] if gp else 0.0, 'kip', 'Largest factored compression P_u = FBMP + gamma_DR DD')
    curve, branch = {}, 'eq3'

    if family == 'psc':
        plan, option = plan_option(case)
        ps = _Psc(case)
        axial_governing(ps)
        _ext(externals, meta, 'N_str', option['count'], None, 'Strands in the Standard Plans pattern')
        _ext(externals, meta, 'A_str', option['strand_area_in2'], 'in^2', 'Strand nominal area')
        _ext(externals, meta, 'P_jack', option['jacking_kip'], 'kip', 'Jacking force per strand, Standard Plans')
        _ext(externals, meta, 'd_void', ps.d_void, 'in', 'Void diameter (Index 455-030 only)')
        _ext(externals, meta, 'R_drive_tons', STANDARD_PLANS['max_driving_resistance_tons'][str(int(plan['size_in']))], None,
             'Maximum driving resistance, SDG Table 3.5.13-1 (tons)')
        g_bi = loads.governing(strength, ps.bi_dc)
        quick = [(ps.res_dc(r), r) for r in strength]          # curves at 0.5 degree angle steps
        lead = max((dc for dc, _ in quick if math.isfinite(dc)), default=0.0)
        candidates = [r for dc, r in quick if dc >= 0.97 * lead]
        g_rs = loads.governing(candidates, lambda r: ps.res_dc(r, True))   # refine at the exact angle
        g_sh = loads.governing(strength, lambda r: ps.shear(r, False)['ratio'])
        g_sc = loads.governing(service, lambda r: ps.service(r)[0] / (0.6 * p['fc']))
        g_st = loads.governing(service, lambda r: max(-ps.service(r)[1], 0.0) / sections.service_tension_limit(p['fc'], p['environment'] == 3, p['lambda_c']))
        governing.update(psc_flex_bi=_gov_record(g_bi), psc_flex_res=_gov_record(g_rs), psc_shear=_gov_record(g_sh),
                         psc_svc_comp=_gov_record(g_sc), psc_svc_tens=_gov_record(g_st))
        bi = g_bi['record'] if g_bi else zero
        rs = g_rs['record'] if g_rs else zero
        sh = g_sh['record'] if g_sh else zero
        sc = g_sc['record'] if g_sc else zero
        st = g_st['record'] if g_st else zero
        bidc = sections.psc_biaxial_dc(ps.curve0, bi['P_u'], bi['M2'], bi['M3'], ps.phi_Po, ps.P_limit)
        branch = 'eq1' if bidc['method'] == '5.6.4.5-1' else 'eq3'
        _ext(externals, meta, 'P_u_bi', bi['P_u'], 'kip', 'Governing record (5.6.4.5): factored axial load')
        _ext(externals, meta, 'M_ux_bi', abs(bi['M2']), 'kip*ft', 'Governing record (5.6.4.5): moment about the x axis')
        _ext(externals, meta, 'M_uy_bi', abs(bi['M3']), 'kip*ft', 'Governing record (5.6.4.5): moment about the y axis')
        if branch == 'eq1':
            _ext(externals, meta, 'P_rx', bidc['Prx'], 'kip', 'Axial resistance at ey from the interaction curve')
            _ext(externals, meta, 'P_ry', bidc['Pry'], 'kip', 'Axial resistance at ex from the interaction curve')
        else:
            _ext(externals, meta, 'M_rx', bidc['Mrx'], 'kip*ft', 'Uniaxial factored moment resistance about x, pure flexure (P = 0) of the interaction curve')
            _ext(externals, meta, 'M_ry', bidc['Mry'], 'kip*ft', 'Uniaxial factored moment resistance about y, pure flexure (P = 0) of the interaction curve')
        rs_curve, rs_angle = ps.curve_for(rs, exact=True)
        ratio_rs, Pc, Mc = sections.ray_capacity(rs_curve, rs['P_u'], rs['M_res'])
        _ext(externals, meta, 'P_u_rs', rs['P_u'], 'kip', 'Governing record (resultant axis): factored axial load')
        _ext(externals, meta, 'M_u_rs', rs['M_res'], 'kip*ft', 'Governing record (resultant axis): resultant moment')
        _ext(externals, meta, 'alpha_rs', math.degrees(rs_angle), 'deg', 'Bending-axis angle of the resultant moment (folded to 0-45 deg)')
        _ext(externals, meta, 'P_r_rs', Pc, 'kip', 'Axial resistance where the demand ray meets the curve')
        _ext(externals, meta, 'M_r_rs', Mc, 'kip*ft', 'Moment resistance where the demand ray meets the curve')
        shd = ps.shear(sh)
        _ext(externals, meta, 'V_u_sh', sh['V_res'], 'kip', 'Governing shear record: resultant shear')
        _ext(externals, meta, 'M_u_sh', sh['M_res'], 'kip*ft', 'Governing shear record: concurrent resultant moment')
        _ext(externals, meta, 'P_u_sh', sh['P_u'], 'kip', 'Governing shear record: factored axial load')
        _ext(externals, meta, 'A_ps_t', shd['Aps_t'], 'in^2', 'Prestressing on the flexural tension half depth')
        _ext(externals, meta, 'd_e', shd['d_e'], 'in', 'Depth from the compression fiber to the tension-side strand centroid')
        for name, rec, tag in (('sc', sc, 'compression'), ('st', st, 'tension')):
            _ext(externals, meta, f'P_{name}', rec['P_u'], 'kip', f'Governing Service I record ({tag} stress): axial load')
            _ext(externals, meta, f'Mx_{name}', rec['M2'], 'kip*ft', f'Governing Service I record ({tag} stress): moment M2')
            _ext(externals, meta, f'My_{name}', rec['M3'], 'kip*ft', f'Governing Service I record ({tag} stress): moment M3')
        M_r_P0 = sections.moment_capacity_at_axial(ps.curve0, 0.0)
        _ext(externals, meta, 'M_r_P0', M_r_P0, 'kip*ft', 'Factored moment resistance at zero axial load from the interaction curve')
        splice = STANDARD_PLANS['splice_moment_kip_ft'].get(str(int(plan['size_in'])))
        _ext(externals, meta, 'M_splice', splice or 0.0, 'kip*ft', 'Spec Table 455-2 mechanical splice bending strength')
        curve = dict(ps.curve0)
        curve['resultant'] = rs_curve
        curve['resultant_angle_deg'] = math.degrees(rs_angle)
        details.update(section=ps.sec, layout=ps.layout, biaxial=bidc, shear=shd, plan=plan, option=option, ratio_rs=ratio_rs,
                       Pc_rs=Pc, Mc_rs=Mc, M_r_P0=M_r_P0, M_splice=splice, branch=branch, P_limit=ps.P_limit, phi_Po=ps.phi_Po)
        gt = loads.governing(strength, lambda r: max(-r['P_fbmp'], 0.0) / (p['phi_t'] * ps.sec['Aps'] * min(p['f_py'], ps.fpe + 60.0)) if r['P_fbmp'] < 0 else None)
    else:
        pp = _Pipe(case)
        axial_governing(pp)
        g_cb = loads.governing(strength, pp.comb_dc)
        g_sh = loads.governing(strength, pp.shear_dc)
        governing.update(pipe_comb=_gov_record(g_cb), pipe_shear=_gov_record(g_sh))
        cb = g_cb['record'] if g_cb else zero
        sh = g_sh['record'] if g_sh else zero
        _ext(externals, meta, 'P_u_comb', cb['P_u'], 'kip', 'Governing combined record: factored axial load (compression +)')
        _ext(externals, meta, 'M_u_comb', cb['M_res'], 'kip*ft', 'Governing combined record: resultant moment')
        _ext(externals, meta, 'V_u_sh', sh['V_res'], 'kip', 'Governing shear record: resultant shear')
        details.update(pipe=pp.sec, axial=pp.axial, flex=pp.flex, shear=pp.shear, Pr_t=pp.Pr_t, L_fix=pp.L_fix, comb=pp.comb(cb) if g_cb else None)
        gt = loads.governing(strength, lambda r: max(-r['P_fbmp'], 0.0) / pp.Pr_t if r['P_fbmp'] < 0 else None)
    governing[f'{family}_tension'] = _gov_record(gt)
    details['uplift_record'] = T_record
    details['uplift_kip'] = T_kip

    definitions = all_definitions(family, branch)
    shadowed = sorted({d['name'] for d in definitions} & set(externals))
    if shadowed:
        raise ValueError('Formula names duplicate input names: ' + ', '.join(shadowed))
    engine = Engine(definitions, externals=dict(externals))
    try:
        engine.all()
    except (ValueError, AssertionError, ZeroDivisionError, TypeError) as exc:
        raise ValueError(f'Calculation stopped: {exc}') from exc
    units = {d['name']: d['unit'] for d in INPUT_SPEC}
    units.update({name: unit for name, (unit, _) in meta.items()})
    units.update({d['name']: d['unit'] for d in definitions})
    e = Evaluation(case=case, engine=engine, definitions=definitions, units=units, records=records, governing=governing,
                   curve=curve, externals=externals, external_meta=meta, details=details)
    e.details['analysis_available'] = bool(analysis)
    e.details['strength_records'] = len(strength)
    e.details['service_records'] = len(service)
    e.details['fdl'] = fd
    e.details['envelope'] = loads.head_envelope(records)
    e.details['model_dc'] = loads.model_dc_max(records)
    e.checks = build_checks(e)
    e.data_table = data_table(e)
    from .reviews import apply_reviews
    apply_reviews(e)
    return e


# ----------------------------------------------------------------------------- checks
def build_checks(e):
    v, t, case = e.value, e.text, e.case
    p, conf, family = case['inputs'], case['confirmations'], case['family']
    checks = []
    have = e.details['analysis_available'] and e.details['strength_records'] > 0
    have_service = e.details['service_records'] > 0
    dd = p['DD_tons'] > 0

    def add(key, group, label, ratio, demand, capacity, basis, refs, names, pending=False, note=''):
        checks.append(Check(key, group, label, ratio, _status(ratio, pending), demand, capacity, basis, refs, names, note))

    def rec_note(key):
        g = e.governing.get(key)
        return '' if not g else f'Governing record: {loads.record_id(g)}' + (f' (+{len(g["ties"]) - 1} tied)' if len(g['ties']) > 1 else '') + '.'

    no_data = 'No FBMP results are loaded: upload the pile XML in Cell 1.'
    exposure_pending = not conf['exposure']
    dd_pending = dd and not conf['downdrag_source']
    gp = e.governing

    if family == 'psc':
        grp = 'Prestressed pile'
        d = e.details
        r_ax = _ratio(v('P_u_axial'), v('P_r_max')) if have else None
        add('psc_axial', grp, 'Axial compression · maximum Pu / φPn,max', r_ax, t('P_u_axial'), t('P_r_max'),
            'Pu / φ Pn,max (spiral, Eq. 5.6.4.4-2)', ['psc_axial', 'phi_psc', 'drag_load'],
            ['A_ps', 'f_pe', 'P_o', 'P_n_max', 'P_r_max', 'P_u_axial'], dd_pending, rec_note(f'{family}_axial') if have else no_data)
        bi = d['biaxial']
        add('psc_flex_bi', grp, f'Axial + biaxial flexure · LRFD Eq. {bi["method"]}',
            bi['ratio'] if have else None, f'Pu {v("P_u_bi"):.1f} kip · Mux {v("M_ux_bi"):.1f} · Muy {v("M_uy_bi"):.1f} kip-ft',
            (f'Prxy {v("P_rxy"):.1f} kip (Prx {v("P_rx"):.1f}, Pry {v("P_ry"):.1f})' if d['branch'] == 'eq1' else f'Mrx = Mry = {v("M_rx"):.1f} kip-ft (P = 0)'),
            'Pu / Prxy (Eq. 5.6.4.5-1) when Pu ≥ 0.10 φ f\'c Ag; else Mux/Mrx + Muy/Mry (Eq. 5.6.4.5-3) with Mrx = Mry the uniaxial φMn at P = 0 (conservative). The refined value is the resultant-axis check below; the larger governs.', ['biaxial', 'strain_compat', 'phi_psc'],
            ['P_bi_lim', 'DC_bi'] + (['e_y', 'e_x', 'P_rxy'] if d['branch'] == 'eq1' else []), dd_pending, rec_note('psc_flex_bi') if have else no_data)
        add('psc_flex_res', grp, 'Axial + flexure · resultant bending axis (strain compatibility)', v('DC_rs') if have else None,
            f'Pu {v("P_u_rs"):.1f} kip · Mu {v("M_u_rs"):.1f} kip-ft at {v("alpha_rs", "deg"):.1f}°', f'Pr {v("P_r_rs"):.1f} kip · Mr {v("M_r_rs"):.1f} kip-ft on the curve',
            'Strain compatibility at the demand angle: ray from the origin to the φ-curve of the resultant bending axis (Mr at Pu); |demand| / |capacity|. Refined value; the larger of this and the 5.6.4.5 route governs.', ['strain_compat', 'biaxial', 'phi_psc'],
            ['alpha_rs', 'P_r_rs', 'M_r_rs', 'DC_rs'], dd_pending, rec_note('psc_flex_res') if have else no_data)
        sh = d['shear']
        add('psc_shear', grp, 'Shear · general procedure', _ratio(v('V_u_sh'), v('V_r')) if have else None, t('V_u_sh'), t('V_r'),
            'Vu / φVn (Eqs. 5.7.3.3-1, 5.7.3.4.2-1 to -4, -7)', ['shear_psc', 'shear_depth', 'av_min', 'phi_psc'],
            ['b_v', 'd_v', 'eps_s', 'beta_v', 'theta_v', 'V_c', 'V_s', 'V_n', 'V_r'], dd_pending,
            (rec_note('psc_shear') + (' ' if have else '') + ('Av ≥ Av,min.' if sh['Av_ok'] else 'Av < Av,min: Eq. 5.7.3.4.2-2 with sxe governs β.')) if have else no_data)
        add('psc_tension', grp, 'Tension · maximum strength uplift', _ratio(v('T_u'), v('P_r_t')) if have else None, t('T_u'), t('P_r_t'),
            'Tu / φPn,t, Pn,t = Aps min(fpy, fpe + 60 ksi) (Eqs. 5.6.6.1-1, 5.8.2.4.1-1)', ['tension_psc', 'phi_psc'], ['P_n_t', 'P_r_t', 'P_t_yield'], not conf['head_connection'] and v('T_u') > 0,
            ((rec_note(f'{family}_tension') + ' ') if gp.get(f'{family}_tension') else 'No uplift in the FBMP strength combinations. ') +
            'The pile-to-cap connection for uplift is the separate head_connection item (SDM 11.6.2: mechanical connection).' if have else no_data)
        sig_c, sig_lim = v('sig_c'), v('sig_c_lim')
        add('psc_svc_comp', grp, 'Service I concrete compression (0.60 f\'c)', _ratio(sig_c, sig_lim) if have_service else None,
            f'{sig_c:.3f} ksi', f'{sig_lim:.3f} ksi', 'σmax / 0.60 f\'c, all loads after losses', ['service_comp'], ['f_pc_eff', 'sig_c', 'sig_c_lim'], False,
            rec_note('psc_svc_comp') if have_service else no_data)
        add('psc_svc_tens', grp, 'Service I concrete tension', _ratio(v('f_t_net'), v('f_t_lim')) if have_service else None,
            f'{v("f_t_net"):.3f} ksi', f'{v("f_t_lim"):.3f} ksi', 'net tension / (0.19 √f\'c ≤ 0.6 ksi; 0.0948 √f\'c ≤ 0.3 ksi Extremely Aggressive)',
            ['service_tens'], ['sig_t', 'f_t_net', 'f_t_lim'], exposure_pending, rec_note('psc_svc_tens') if have_service else no_data)
        add('psc_prestress', grp, 'Effective prestress ≥ 0.7 ksi after losses', _ratio(v('f_pc_min'), v('f_pc_eff')), t('f_pc_min'), t('f_pc_eff'),
            '0.7 ksi / fpc,eff', ['prestress_min'], ['P_e', 'f_pc_eff', 'f_pc_min'])
        add('psc_prestress_fdot', grp, 'Effective prestress vs FDOT basis of 1.0 ksi', None, t('f_pc_eff'), '1.000 ksi',
            'Standard piles are designed for about 1000 psi after losses', ['prestress_fdot'], ['f_pc_eff'],
            note=f'{t("f_pc_eff")} on the gross area; FBMP prestress {e.case["analysis"]["section"]["prestress_kip"]:.1f} kip.' if e.case.get('analysis') else '')
        add('psc_fc_driving', grp, "Concrete strength ≥ 5.0 ksi for driving", _ratio(5.0, p['fc']), '5.0 ksi', t('fc'), "5.0 ksi / f'c", ['prestress_min'], [])
        add('psc_min_size', grp, 'Minimum square pile size (Table 3.5.1-1)', _ratio(v('D_min'), p['D_pile']), t('D_min'), t('D_pile'),
            'required / provided', ['min_pile_size'], ['D_min'], exposure_pending)
        add('spacing', grp, 'Pile spacing ≥ 3.0 diameters (SDG 3.5.4)', _ratio(v('S_min'), v('S_pile', 'in')), t('S_min'), f'{v("S_pile", "in"):.1f} in',
            '3 D / S', ['pile_spacing'], ['S_min', 's_over_D'])
        if p['embed_cap'] >= 48:
            add('psc_head', grp, 'Pile-to-cap moment transfer (48 in embedment)', _ratio(48.0, p['embed_cap']), '48 in', t('embed_cap'),
                'required / provided embedment', ['head_connection'], [])
        else:
            head_m = max((x['max_M_res'] for x in e.details['envelope'].values()), default=0.0)
            add('psc_head', grp, 'Pile-to-cap moment transfer (embedment below 48 in)', None, f'FBMP head moment {head_m:.1f} kip-ft',
                f'{p["embed_cap"]:g} in embedment', 'SDG 3.5.1.C: 48 in develops the full bending capacity', ['head_connection'], [], not conf['head_connection'],
                'Report the FBMP head moment to the cap/pile connection detail; this check stays PENDING until the connection is verified.')
        add('psc_splice', grp, 'Mechanical splice bending strength vs pile φMn at P = 0 (INFO)', None,
            f'Table 455-2 {v("M_splice"):.0f} kip-ft' if v('M_splice') else 'Not tabulated', f'φMn {v("M_r_P0"):.1f} kip-ft',
            'A splice must develop the pile; not a check on the pile itself', ['splice'], ['M_r_P0'])
    else:
        grp = 'Steel pipe pile'
        d = e.details
        ax, fx, shr = d['axial'], d['flex'], d['shear']
        add('pipe_slender', grp, f'Local buckling class · {"slender" if ax["slender"] else "nonslender"} (D/t vs 0.11 E/Fy)', _ratio(v('D_t'), 0.45 * p['E_s'] / p['Fy']),
            f'D/t {v("D_t"):.2f}', f'0.11E/Fy {v("lam_r"):.2f} · limit 0.45E/Fy {0.45 * p["E_s"] / p["Fy"]:.1f}', 'D/t / (0.45 E/Fy)', ['pipe_local'], ['t_des', 'D_t', 'lam_r', 'A_eff'], not conf['steel_grade'] or not conf['corrosion'])
        add('pipe_klr', grp, 'Slenderness KL/r ≤ 120', _ratio(v('KL_r'), 120.0), f'{v("KL_r"):.1f}', '120', 'KL/r / 120', ['slenderness', 'fixity'], ['L_fix', 'KL', 'KL_r'], not conf['steel_grade'])
        add('pipe_axial', grp, 'Axial compression · maximum Pu / φc Pn', _ratio(v('P_u_axial'), v('P_r_axial')) if have else None, t('P_u_axial'), t('P_r_axial'),
            'Pu / φc Pn (Eqs. 6.9.4.1.1-1, -2)', ['pipe_axial', 'pipe_phi', 'fixity', 'drag_load'], ['P_o', 'P_e', 'Pe_Po', 'P_n', 'P_r_axial'],
            not conf['steel_grade'] or dd_pending, (rec_note(f'{family}_axial') + f' Branch: {ax["branch"]}.') if have else no_data)
        cb = d['comb']
        add('pipe_comb', grp, 'Combined axial load and flexure · Eq. 6.9.2.2.1' + (f' ({cb["branch"][-2:]})' if cb else ''), v('DC_comb') if have else None,
            f'Pu {v("P_u_comb"):.1f} kip · Mu {v("M_u_comb"):.1f} kip-ft', f'Pr {v("P_rc"):.1f} kip · Mr {v("M_r"):.1f} kip-ft',
            'Pu/Pr + 8/9 M/Mr (Pu/Pr ≥ 0.2); Pu/2Pr + M/Mr otherwise; resultant moment', ['pipe_interaction', 'pipe_phi'],
            ['P_abs', 'P_rc', 'Pu_Pr', 'M_r', 'DC_comb'], not conf['steel_grade'] or dd_pending,
            (rec_note('pipe_comb') + ' Second-order effects come from the FBMP P-delta analysis; the LRFD column check uses K(Lu + Lf).') if have else no_data)
        add('pipe_flex_class', grp, f'Flexure class · {fx["cls"]}', None, f'D/t {v("D_t"):.2f}', f'compact limit 0.07E/Fy {v("lam_p"):.2f}',
            'Mn = Mp for compact; reduced otherwise', ['pipe_flexure'], ['lam_p', 'lam_nc', 'M_p', 'M_n'], note=f'Mp {v("M_p"):.1f} kip-ft; Mn {v("M_n"):.1f} kip-ft.')
        add('pipe_shear', grp, 'Shear · round tube', _ratio(v('V_u_sh'), v('V_r')) if have else None, t('V_u_sh'), t('V_r'), 'Vu / φVn',
            ['pipe_shear', 'pipe_phi'], ['F_cr1', 'F_cr2', 'F_cr', 'V_n', 'V_r'], not conf['steel_grade'], rec_note('pipe_shear') if have else no_data)
        add('pipe_tension', grp, 'Tension · maximum strength uplift', _ratio(v('T_u'), v('P_r_t')) if have else None, t('T_u'), t('P_r_t'),
            'Tu / φy Fy Ag (Eq. 6.8.2.1-1)', ['pipe_tension', 'pipe_phi'], ['P_r_t', 'DC_t'], (not conf['steel_grade']) or (not conf['head_connection'] and v('T_u') > 0),
            ((rec_note(f'{family}_tension') + ' ') if gp.get(f'{family}_tension') else 'No uplift in the FBMP strength combinations. ') +
            'The pile-to-cap uplift connection (shear studs, SDM 11.6.2.B) is the separate head_connection item.' if have else no_data)
        add('spacing', grp, 'Pile spacing ≥ 3.0 diameters (SDG 3.5.4)', _ratio(v('S_min'), v('S_pile', 'in')), t('S_min'), f'{v("S_pile", "in"):.1f} in', '3 D / S',
            ['pile_spacing'], ['S_min', 's_over_D'])
    dc_value, dc_record = e.details['model_dc']
    add('fbmp_dc', 'Reference', 'FB-MultiPier model D/C (INFO, not a LRFD check)', None,
        f'{dc_value:.2f} maximum' if dc_value is not None else 'Not exported', 'FBMP interaction', 'Reported by the FBMP analysis for comparison with the notebook ratios',
        ['fbmp_model'], [], note=f'At {loads.record_id(dc_record)}.' if dc_record else '')

    if family == 'psc':
        add('nbr', 'Geotechnical', 'Required nominal bearing resistance vs Table 3.5.13-1', _ratio(v('NBR_tons'), v('R_drive_tons')) if have else None,
            f'{v("NBR_tons"):.1f} tons', f'{v("R_drive_tons"):.0f} tons', 'Rn,required / maximum driving resistance', ['nbr', 'driving_max', 'phi_geo'],
            ['FDL_tons', 'R_scour_net', 'DD', 'R_n_req', 'NBR_tons', 'R_drive_max'], False, no_data if not have else 'Rn = (FDL + net scour + downdrag) / φ, Eq. 3-1.')
    else:
        add('nbr', 'Geotechnical', 'Required nominal bearing resistance (no Table 3.5.13-1 limit for steel pipe)', None,
            f'{v("NBR_tons"):.1f} tons', 'No table value', 'Rn = (FDL + net scour + downdrag) / φ', ['nbr', 'phi_geo'], ['FDL_tons', 'R_scour_net', 'DD', 'R_n_req', 'NBR_tons'],
            note='Table 3.5.13-1 covers prestressed concrete piles; confirm the driving limit with the geotechnical engineer.')
    missing = [n for n in ('EL_min_tip', 'L_test_pile', 'EL_scour_100', 'EL_scour_LT') if p.get(n) is None]
    add('data_table', 'Geotechnical', 'Pile Data Table completeness (SDM 11.4)', None, 'Columns filled from this analysis',
        f'N/A: {", ".join(missing)}' if missing else 'All columns provided', 'Round loads up, tips down, lengths up, cutoff to 0.1 ft; N/A where not applicable',
        ['data_table', 'min_tip'], [], not (conf['min_tip'] and conf['scour']) and bool(missing),
        'Minimum tip, scour and test-pile entries stay N/A until the geotechnical handoff supplies them.')
    add('downdrag_plans', 'Geotechnical', 'Downdrag shown on the plans', None, t('DD'), 'Pile Data Table column J',
        'Downdrag = ultimate skin friction above the neutral point plus dynamic resistance above it minus live load', ['downdrag_plans', 'drag_load'], ['DD', 'DR_str', 'DR_ser'],
        note=f'DR enters the structural demand with γ = {p["gamma_DR_str"]:g} (strength) / {p["gamma_DR_ser"]:g} (Service I) and is excluded from the Factored Design Load.')
    add('phi_geo', 'Geotechnical', 'Geotechnical resistance factor φ (Table 3.5.7-1)', None, f'{p["phi_geo"]:.2f}', 'Default 0.75 for Pile Data Tables',
        'SDG footnote 7', ['phi_geo'], [])

    items = [('exposure', 'Environment classification'), ('head_connection', 'Pile-to-cap connection (12 in embedment)'),
             ('downdrag_source', 'Downdrag source documented'), ('analysis_current', 'FBMP export current'),
             ('min_tip', 'Minimum tip elevation'), ('scour', 'Scour resistance and elevations'), ('drivability', 'Drivability')]
    if family == 'pipe':
        items = [('steel_grade', 'Steel grade and Fy reconciled'), ('corrosion', 'Corrosion allowance')] + items
    prereq_refs = {'exposure': ['exposure'], 'head_connection': ['head_connection'], 'steel_grade': ['steel_grade'], 'corrosion': ['corrosion'],
                   'downdrag_source': ['downdrag_plans'], 'analysis_current': ['fbmp_model'], 'min_tip': ['min_tip'], 'scour': ['nbr'],
                   'drivability': ['drivability']}
    for key, label in items:
        add('prereq_' + key, 'Prerequisites', label, None, 'Confirmation', CONFIRMATIONS[key], 'Recorded in Sources & assumptions',
            prereq_refs[key], [], not conf[key])
    for check in checks:
        if check.group == 'Prerequisites' and check.status == 'INFO':
            check.status = 'CONFIRMED'
    return checks


# ----------------------------------------------------------------------------- Pile Data Table
def data_table(e):
    """SDM 11.4 Pile Data Table row, rounded per SDG 3.5.15.D; 'N/A' where not applicable."""
    p, v = e.case['inputs'], e.value
    NA = 'N/A'
    fd = e.details['fdl']
    ton = lambda kip: kip / 2.0
    size = f'{p["D_pile"]:g}"'
    kind = f'{size} Sq. Prestr. Conc.' if e.family == 'psc' else f'{p["D_out"]:g}" Ø Pipe'
    # Column D: strength uplift at the pile head only; the structural tension check uses every station
    tension = ton(fd['T_kip'])
    dd = p['DD_tons']
    scour_total, scour_net = p['R_scour_total_tons'], p['R_scour_net_tons']
    tip = None if p.get('EL_min_tip') is None else _floor(p['EL_min_tip'])
    test = None if p.get('L_test_pile') is None else _ceil(p['L_test_pile'])
    order = None if tip is None else _ceil(p['EL_cutoff'] - tip)
    if test is None and order is None:
        length = NA
    else:
        length = f'{test if test is not None else NA} / {order if order is not None else NA}'
    opt = lambda x: NA if x is None else round(float(x), 1)
    row = {
        'A': e.case['support'], 'B': kind,
        'C': _ceil(v('NBR_tons')) if e.details['fdl']['FDL_record'] else NA,
        'D': _ceil(tension) if tension > 1e-9 else NA,
        'E': NA if tip is None else tip, 'F': length, 'G': NA, 'H': NA,
        'I': _ceil(ton(fd['FDL_kip'])) if fd['FDL_record'] else NA,
        'J': _ceil(dd) if dd > 0 else NA,
        'K': _ceil(scour_total) if scour_total > 0 else NA, 'L': _ceil(scour_net) if scour_net > 0 else NA,
        'M': opt(p.get('EL_scour_100')), 'N': NA, 'O': opt(p.get('EL_scour_LT')),
        'P': round(p['phi_geo'], 2), 'Q': round(p['EL_cutoff'], 1)}
    return {header: row[letter] for letter, header in DATA_TABLE_COLUMNS}


def formula_trace(e):
    from .notation import definition_mathml
    out = []
    for d in e.definitions:
        out.append(dict(name=d['name'], section=d['section'], caption=d['caption'], unit=d['unit'], refs=d['refs'], formula=d['formula'],
                        mathml=definition_mathml(d['name'], parse(d['expr']), e.engine, e.units, d['unit'])))
    return out
