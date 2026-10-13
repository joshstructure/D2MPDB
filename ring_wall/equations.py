"""Check-specific calculation traces for the notebook and report.

These explain the existing model; they do not perform a second strength design.
Check results and available intermediate results are read from analyze().
"""
from .model import BAR


def number(value):
    if isinstance(value, (list, tuple)):
        return '['+', '.join(number(v) for v in value)+']'
    return f'{value:.9g}'


def step(label, formula, substitution, value, unit):
    return dict(label=label, formula=formula, substitution=substitution,
                value=value, unit=unit)


def check_steps(r, check):
    """Symbolic equations, numeric substitutions and results for one check."""
    p, g, geo = r['case'], r['grid'], r['geometry']
    key = check['id']; n = number
    t, L, H = p['thickness_in'], p['length_in'], p['height_in']
    cover, db, ab, s = p['cover_in'], g['db'], g['area'], g['spacing']
    fy, fc = p['fy_ksi'], p['fc_ksi']
    S, rise, panels = p['pile_spacing_in'], p['arch_rise_in'], p['arch_panels']
    ro, ri, rp = p['ring_od_in']/2, p['ring_id_in']/2, p['pile_od_in']/2
    eta, tol, end = p['bearing_fraction'], p['placement_tolerance_in'], r['end']
    out = []

    def add(label, formula, substitution, value, unit):
        out.append(step(label, formula, substitution, value, unit))

    def finish(d_formula, d_values, c_formula, c_values):
        add('Demand', d_formula, d_values, check['demand'], check['unit'])
        add('Resistance / limit', c_formula, c_values, check['capacity'], check['unit'])
        return out

    if key == 'GRID-A':
        for label, dim, result in [('L', L, g['st_L']), ('H', H, g['st_H'])]:
            add('Shrinkage / temperature, '+label+' section',
                f'A_ST,{label} = max(0.11, min(0.60, 1.30 t {label} / [2(t + {label}) min(f_y, 75)]))',
                f'max(0.11, min(0.60, 1.30 × {n(t)} × {n(dim)} / [2 × ({n(t)} + {n(dim)}) × min({n(fy)}, 75)]))',
                result, 'in²/ft per face')
        add('STM minimum, each face', 'A_STM = 0.003 t × 12 / 2',
            f'0.003 × {n(t)} × 12 / 2', g['stm'], 'in²/ft per face')
        return finish('A_req = max(A_ST,L, A_ST,H, A_STM)',
                      f'max({n(g["st_L"])}, {n(g["st_H"])}, {n(g["stm"])})',
                      'A_prov = 12 A_b / s', f'12 × {n(ab)} / {n(s)}')
    if key == 'GRID-S':
        hmin = min(a['height'] for a in r['rows'])
        add('Effective depth of shallowest assigned band', 'd = min(h_j) − c − d_b/2',
            f'{n(hmin)} − {n(cover)} − {n(db)}/2', g['d'], 'in')
        if p['auto_grid_spacing']:
            inc = p['spacing_increment_in']
            formula = 's = Δs × floor(min(12, d/4, 12 A_b/A_req) / Δs)'
            values = f'{n(inc)} × floor(min(12, {n(g["d"])}/4, 12 × {n(ab)}/{n(g["required"])}) / {n(inc)})'
        else:
            formula, values = 's = entered manual grid spacing', n(p['grid_spacing_in'])
        return finish(formula, values, 's_max = min(12, d/4)', f'min(12, {n(g["d"])}/4)')
    if key == 'GRID-CLEAR':
        return finish('a_req = max(1.5 d_b, 1.5 d_agg, 1.5)',
                      f'max(1.5 × {n(db)}, 1.5 × {n(p["aggregate_in"])}, 1.5)',
                      'a_prov = s − d_b', f'{n(s)} − {n(db)}')
    if key == 'U-LAP':
        dev = g['development_h']; coat = 1. if p['coating'] == 'uncoated' else 1.5
        add('Basic development (normalweight; full yield)', 'ℓ_db = 0.17 d_b [f_y/(1.97 f′_c^0.25)]²',
            f'0.17 × {n(db)} × [{n(fy)}/(1.97 × {n(fc)}^0.25)]²', dev['basic'], 'in')
        add('Top-bar and coating product; confinement factor = 1', 'F = min(1.7, 1.3 F_coat)',
            f'min(1.7, 1.3 × {n(coat)})', dev['factor'], 'dimensionless')
        add('Development length', 'ℓ_d = max(12, ℓ_db F)',
            f'max(12, {n(dev["basic"])} × {n(dev["factor"])})', dev['ld'], 'in')
        return finish('ℓ_ClassB = 1.3 ℓ_d', f'1.3 × {n(dev["ld"])}',
                      'ℓ_available = entered U-bar straight leg', n(p['u_leg_in']))
    if key == 'U-BEND':
        bend = 6 if p['grid_bar'] <= 8 else 8
        add('Inside bend diameter (selected bar #'+str(p['grid_bar'])+')', 'D_inside = k_b d_b; k_b = 6 for #4–#8, 8 for #9–#10',
            f'{bend} × {n(db)}', g['u_inside_bend'], 'in')
        return finish('b_bend = D_inside + 2 d_b', f'{n(g["u_inside_bend"])} + 2 × {n(db)}',
                      'b_available = t − 2 c', f'{n(t)} − 2 × {n(cover)}')
    if key == 'NODE-TIE':
        return finish('δ = |tie offset − h_node/2|',
                      f'|{n(p["tie_offset_in"])} − {n(p["node_height_in"])}/2|',
                      'δ_max = numerical alignment tolerance', '0.000001')
    if key in ('RING-END', 'RING-FACE', 'RING-GRID', 'CONE-ENCLOSED'):
        add('Ring outer radius', 'r_o = OD_ring/2', f'{n(p["ring_od_in"])}/2', ro, 'in')
        if key == 'RING-END':
            add('Centered end-pile distance', 'e = [L − (N_piles − 1) S]/2',
                f'[{n(L)} − ({p["pile_count"]} − 1) × {n(S)}]/2', end, 'in')
            return finish('c_req = entered clear cover', n(cover), 'c_end = e − r_o − tolerance',
                          f'{n(end)} − {n(ro)} − {n(tol)}')
        if key == 'RING-FACE':
            return finish('c_req = entered clear cover', n(cover), 'c_face = t/2 − r_o − tolerance',
                          f'{n(t)}/2 − {n(ro)} − {n(tol)}')
        if key == 'RING-GRID':
            return finish('a_req = max(1, 1.5 d_agg)', f'max(1, 1.5 × {n(p["aggregate_in"])})',
                          'a_grid = t/2 − c − 2 d_b − r_o − tolerance',
                          f'{n(t)}/2 − {n(cover)} − 2 × {n(db)} − {n(ro)} − {n(tol)}')
        return finish('r_required = r_o + 0.000001', f'{n(ro)} + 0.000001',
                      'r_available = t/2', f'{n(t)}/2')

    # All remaining checks are specific to a ring row, optionally a pile.
    parts = key.split('-')
    if not parts[0].startswith('R') or not parts[0][1:].isdigit():
        raise ValueError('No equation trace for check '+key)
    row = next(a for a in r['rows'] if a['row'] == int(parts[0][1:]))
    a = row['arch']; bh = row['height']; w = row['w']; kind = '-'.join(parts[1:])

    def load(service=False):
        add('Assigned band height', 'h_j = z_upper − z_lower',
            f'{n(row["hi"])} − {n(row["lo"])}', bh, 'in')
        if service:
            add('Service line load', 'w_s = [γ_c (t/12) + q_add] h_j/144',
                f'[{n(p["density_kcf"])} × ({n(t)}/12) + {n(p["additional_service_ksf"])}] × {n(bh)}/144', row['ws'], 'kip/in')
        else:
            add('Factored line load', 'w_u = [γ_DC γ_c (t/12) + γ_add q_add] h_j/144',
                f'[{n(p["gamma_dc"])} × {n(p["density_kcf"])} × ({n(t)}/12) + {n(p["gamma_additional"])} × {n(p["additional_service_ksf"])}] × {n(bh)}/144', w, 'kip/in')

    def tie_capacity(collector=False):
        count = p['hanger_bars_per_face'] if collector else p['primary_bars_per_face']
        area = BAR[p['primary_bar']][1]
        add('Dedicated steel in both faces; grid excluded', 'A_st = 2 n_bars,face A_b',
            f'2 × {count} × {n(area)}', 2*count*area, 'in²')
        return ('φP_n = φ_t f_y A_st', f'{n(p["phi_tie"])} × {n(fy)} × {n(2*count*area)}')

    def annulus():
        add('Ring outer radius', 'r_o = OD_ring/2', f'{n(p["ring_od_in"])}/2', ro, 'in')
        add('Ring inner radius', 'r_i = ID_ring/2', f'{n(p["ring_id_in"])}/2', ri, 'in')
        add('Annular area', 'A = π (r_o² − r_i²)', f'π × ({n(ro)}² − {n(ri)}²)', geo['ring_area'], 'in²')
        add('Annular second moment', 'I = π (r_o⁴ − r_i⁴)/4', f'π × ({n(ro)}⁴ − {n(ri)}⁴)/4', geo['ring_I'], 'in⁴')

    def node_geometry():
        annulus()
        bw, hn = p['node_width_in'], p['node_height_in']
        seg = a['segments'][0]; theta = seg['angle']
        add('End-strut angle from horizontal', 'θ = atan(|Δy/Δx|) × 180/π',
            f'atan(|{n(seg["y2"]-seg["y1"])}/{n(seg["x2"]-seg["x1"])}|) × 180/π', theta, 'deg')
        add('Assumed bearing length per adjacent bay', 'ℓ_b = η A/(2 b_eq)',
            f'{n(eta)} × {n(geo["ring_area"])}/(2 × {n(bw)})', row['lb'], 'in')
        add('Equivalent strut width', 'w_n = ℓ_b sin(θ) + h_node cos(θ)',
            f'{n(row["lb"])} × sin({n(theta)}°) + {n(hn)} × cos({n(theta)}°)', row['wn'], 'in')

    if kind in ('T', 'V', 'V-NODE', 'END-T'):
        load()
        capacity = tie_capacity(kind in ('V', 'V-NODE'))
        if kind == 'T':
            return finish('T = w_u S²/(8 h_arch)', f'{n(w)} × {n(S)}²/(8 × {n(rise)})', *capacity)
        if kind == 'V':
            return finish('V_collector = w_u Δx = w_u S/N_panels', f'{n(w)} × {n(S)}/{panels}', *capacity)
        if kind == 'V-NODE':
            return finish('V_node = w_u max(S/N_panels, S/(2 N_panels) + e)',
                          f'{n(w)} × max({n(S)}/{panels}, {n(S)}/(2 × {panels}) + {n(end)})', *capacity)
        add('End-strip moment magnitude', '|M_end| = w_u e²/2', f'{n(w)} × {n(end)}²/2', row['end_moment'], 'kip-in')
        return finish('T_end = |M_end|/h_arch', f'{n(row["end_moment"])}/{n(rise)}', *capacity)
    if kind == 'ANGLE':
        dx = S/panels
        dy = [b['y2']-b['y1'] for b in a['segments']]
        angles = [b['angle'] for b in a['segments']]
        intersections = [angles[0], angles[-1]]
        for i in range(1, panels):
            intersections.extend([90-angles[i-1], 90-angles[i]])
        add('All segment angles from horizontal', 'θ_i = atan(|Δy_i/Δx|) × 180/π',
            f'atan(|{n(dy)}/{n(dx)}|) × 180/π', angles, 'deg')
        return finish('θ_required = 25° + numerical strictness allowance', '25 + 0.000001',
                      'θ_min = min(end angles θ, interior collector angles 90° − θ)',
                      'min('+', '.join(n(x) for x in intersections)+')')
    if kind == 'NODE':
        load(); node_geometry()
        seg = max(a['segments'], key=lambda x:x['C'])
        add('Bay tie thrust', 'T = w_u S²/(8 h_arch)', f'{n(w)} × {n(S)}²/(8 × {n(rise)})', a['tie'], 'kip')
        add('Equivalent node area', 'A_node = b_eq w_n', f'{n(p["node_width_in"])} × {n(row["wn"])}', row['node_area'], 'in²')
        return finish('C_max = max_i √[T² + (T Δy_i/Δx)²]',
                      f'governing segment: √[{n(a["tie"])}² + ({n(a["tie"])} × {n(seg["y2"]-seg["y1"])}/{n(S/panels)})²]',
                      'φP_n,node = φ_c (1 × 0.45 f′_c) A_node',
                      f'{n(p["phi_concrete"])} × 1 × 0.45 × {n(fc)} × {n(row["node_area"])}')
    if kind == 'CRACK':
        load(service=True)
        d = bh-cover-db/2
        coef = max(.0632, min(.158, .2-.1*(S/2)/d)) if d > 0 else 0.
        add('Effective band depth', 'd = h_j − c − d_b/2', f'{n(bh)} − {n(cover)} − {n(db)}/2', d, 'in')
        add('Diagonal-cracking coefficient', 'k = max(0.0632, min(0.158, 0.2 − 0.1 (S/2)/d)); k = 0 if d ≤ 0',
            f'max(0.0632, min(0.158, 0.2 − 0.1 × ({n(S)}/2)/{n(d)}))' if d > 0 else '0 because d ≤ 0', coef, 'coefficient for ksi/in units')
        return finish('V_service = w_s S/2', f'{n(row["ws"])} × {n(S)}/2',
                      'V_cr = k √f′_c × t × max(d, 0)', f'{n(coef)} × √{n(fc)} × {n(t)} × max({n(d)}, 0)')
    if kind == 'FIT':
        node_geometry()
        if r['cone']['enabled']:
            add('Cone rise to broad faces', 'h_face = max(0, (t/2 − r_o)/s_cone)',
                f'max(0, ({n(t)}/2 − {n(ro)})/{n(p["cone_slope_hv"])} )', r['cone']['face_rise_in'], 'in')
        else:
            add('Original ring-level model', 'h_face = 0', '0', 0., 'in')
        add('Trial node-region base', 'z_base = z_ring + h_face',
            f'{n(row["z"])} + {n(row["node_base_z"]-row["z"])}', row['node_base_z'], 'in above wall bottom')
        return finish('z_arch,top = z_base + tie offset + h_arch',
                      f'{n(row["node_base_z"])} + {n(p["tie_offset_in"])} + {n(rise)}',
                      'z_limit = z_band,upper − c − w_n/2',
                      f'{n(row["hi"])} − {n(cover)} − {n(row["wn"])}/2')
    if len(parts) == 3 and parts[1].startswith('P'):
        ring = next(b for b in r['rings'] if b['row'] == row['row'] and b['pile'] == int(parts[1][1:]))
        kind = parts[2]; load(); annulus()
        outer = ring['pile'] in (1, p['pile_count'])
        add('Ring vertical reaction', 'R = w_u (S/2 + e)' if outer else 'R = w_u S',
            f'{n(w)} × ({n(S)}/2 + {n(end)})' if outer else f'{n(w)} × {n(S)}', ring['R'], 'kip')
        sign = '−' if ring['pile'] == 1 else '+'
        add('Signed support couple on wall', 'M = ±w_u e²/2 (end pile)' if outer else 'M = 0 (interior pile)',
            f'{sign}{n(w)} × {n(end)}²/2' if outer else '0', ring['M'], 'kip-in')
        direct = f'{n(ring["R"])}/({n(eta)} × {n(geo["ring_area"])})'
        moment = f'|{n(ring["M"])}| × {n(ro)}/({n(eta)} × {n(geo["ring_I"])})'
        q_formula = 'q_max = R/(η A) + |M| r_o/(η I)'
        if kind == 'BEAR':
            return finish(q_formula, direct+' + '+moment, 'q_R = φ_c × 0.45 f′_c',
                          f'{n(p["phi_concrete"])} × 0.45 × {n(fc)}')
        if kind == 'CONTACT':
            add('Minimum contact pressure; must be nonnegative', 'q_min = R/(η A) − |M| r_o/(η I)',
                direct+' − '+moment, ring['qmin'], 'ksi')
            return finish('q_M = |M| r_o/(η I)', moment, 'q_R = R/(η A)', direct)
        if kind == 'PLATE':
            add('Maximum annular pressure', q_formula, direct+' + '+moment, ring['qmax'], 'ksi')
            add('Pipe outer radius', 'r_p = OD_pile/2', f'{n(p["pile_od_in"])}/2', rp, 'in')
            return finish('m_root = q_max [(r_o³ − r_i³)/(3 r_p) − (r_o² − r_i²)/2]',
                          f'{n(ring["qmax"])} × [({n(ro)}³ − {n(ri)}³)/(3 × {n(rp)}) − ({n(ro)}² − {n(ri)}²)/2]',
                          'φm_y = φ_plate F_y t_ring²/6',
                          f'{n(p["phi_plate"])} × {n(p["ring_fy_ksi"])} × {n(p["ring_t_in"])}²/6')
    raise ValueError('No equation trace for check '+key)
