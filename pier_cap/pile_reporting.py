"""Stress comparisons and a concise handoff of calculated minimum-tip results."""
import math
from .pile_review import elastic_profile, pile_heads, require


def stress_limits(section):
    """Model thresholds, not inferred code service allowables."""
    if section['kind'] == 'steel':
        fy = section.get('fy_ksi')
        return [(-fy, '−Fy'), (fy, '+Fy')] if fy and fy > 0 else []
    peak = section.get('tensile_peak_ksi')
    return [(0, 'Decompression')] + ([(peak, 'Model cracking peak')] if peak else [])


def elastic_stress_checks(review, combination, piles, section=None):
    section = section or review['section']
    concrete = section['kind'] == 'concrete'
    limit = section.get('tensile_peak_ksi' if concrete else 'fy_ksi')
    profile = elastic_profile(review, section)
    checks = []
    for pile in piles:
        rows = [r for r in profile if r['combination'] == combination and r['pile'] == pile]
        if not rows:
            continue
        high = max(rows, key=lambda r: r['stress_max_ksi'])
        low = min(rows, key=lambda r: r['stress_min_ksi'])
        governing = high if concrete or high['stress_max_ksi'] >= abs(low['stress_min_ksi']) else low
        demand = max(0, high['stress_max_ksi']) if concrete else max(abs(high['stress_max_ksi']), abs(low['stress_min_ksi']))
        ratio = demand/limit if limit else None
        if concrete and high['stress_max_ksi'] <= 0:
            status = 'Entire elastic range in compression'
        elif ratio is None:
            status = 'Limit unavailable'
        elif concrete:
            status = 'At / above model cracking peak' if ratio >= 1 else 'Tension below model cracking peak'
        else:
            status = 'Above Fy' if ratio > 1 else 'Within ±Fy'
        checks.append(dict(pile=pile, stress_min_ksi=low['stress_min_ksi'], stress_max_ksi=high['stress_max_ksi'],
                           limit_ksi=limit, ratio=ratio, result=status, node=governing['node'],
                           element=governing['element'], side=governing['side']))
    return checks


def reported_cracking_check(review, combination):
    """Use peak strain, so tensile softening cannot masquerade as uncracked."""
    if review['section']['kind'] != 'concrete':
        return []
    peak = review['section'].get('tensile_peak_strain')
    rows = [r for r in review['reported_stresses']
            if r['combination'] == combination and r['description'] == 'max stress in concrete']
    if not rows:
        return [dict(result='Concrete strain extrema unavailable; reload XML.')]
    checks = []
    for r in rows:
        strain = r.get('strain')
        if strain is None:
            status = 'Strain unavailable; reload XML.'
        elif strain <= 0:
            status = 'Entire reported concrete range in compression'
        elif peak is None:
            status = 'Tensile strain present; model cracking strain unavailable'
        elif strain >= peak:
            status = 'Model cracking strain reached / exceeded'
        else:
            status = 'Tension below model cracking strain'
        checks.append(dict(combination=combination, pile=r['pile'], segment=r['segment'],
                           strain=strain, peak_strain=peak, stress_ksi=r['stress_ksi'], result=status))
    return checks


def geotech_section_and_loads(review, nominal_weight=None, nominal_diameter=None, toe='Unknown'):
    s = review['section']
    size = (f'{s["width_in"]:g}-in diameter' if s['circular'] else
            f'{s["width_in"]:g} × {s["depth_in"]:g} in')
    section = [dict(item='Pile section', value=f'{size} · {s["shape"]} · {s["kind"]}'),
               dict(item='Number of piles', value=len(review['piles']))]
    if s.get('shell_in'):
        section.append(dict(item='Wall thickness (in)', value=s['shell_in']))
    strength = ('Concrete strength f′c (ksi)', s.get('fc_ksi')) if s['kind'] == 'concrete' else ('Steel Fy (ksi)', s.get('fy_ksi'))
    section.append(dict(item=strength[0], value=strength[1]))
    for label, value in [('Supplied nominal weight (lb/ft)', nominal_weight), ('Supplied nominal OD (in)', nominal_diameter)]:
        require(value is None or (math.isfinite(value) and value > 0), label+' must be positive or blank.')
        if value is not None:
            section.append(dict(item=label, value=value))
    if toe != 'Unknown':
        section.append(dict(item='Pile toe', value=toe))
    # Keep the exact combination provenance. Service and fatigue cases are not
    # silently promoted to foundation strength-design demands.
    heads = [r for r in pile_heads(review) if r['state'].startswith(('STRENGTH', 'EXTREME'))]
    loads = []
    for label, key in [('Maximum factored compression', 'compression_kip'), ('Maximum factored uplift', 'uplift_kip')]:
        value = max((r[key] for r in heads), default=None)
        ties = [r for r in heads if math.isclose(r[key], value, rel_tol=0, abs_tol=1e-9)] if value is not None and value > 0 else []
        loads.append(dict(load=label, short_tons=value/2 if value is not None else None,
                          governing='; '.join(f'Pile {r["pile"]} · combo {r["combination"]} · {r["state"]}' for r in ties)
                          or ('None — no demand' if value == 0 else 'No strength / extreme-event results')))
    return section, loads


def selected_trial_handoff(review, result, *, source='', ground=None, cutoff=None, basis='', notes=''):
    """Only exact trial matches supply analysis results; never interpolate them."""
    require(result is not None, 'Calculate the trials in Minimum tip first, or click Update selected results here.')
    accepted = result['accepted_embedment_ft']
    require(accepted is not None, 'No critical embedment meets the displacement-change limit. Check the trial results.')
    selection = [dict(item=label, value=value) for label, value in [
        ('Trial source', source.strip() or 'Pasted trials — source not named'),
        ('Calculated critical embedment (ft)', accepted),
        ('Added embedment (ft)', result['extension_ft']),
        ('Required embedment below design ground / scour (ft)', result['required_embedment_ft']),
        ('Design ground / scour elevation (ft)', ground),
        ('Cutoff elevation (ft)', cutoff),
        ('Adopted minimum tip elevation (ft)', result['tip_elevation_ft']),
        ('Selected total pile length (ft)', result['total_length_ft']),
        ('Calculation basis', result['basis']),
        ('Project notes for trial study', basis.strip() or 'None')]]
    if 'controlling_criterion' in result:
        selection.extend(dict(item=label, value=value) for label, value in [
            ('Controlling minimum-tip criterion', result['controlling_criterion']),
            ('Both criteria fully evaluated', result['comparison_complete']),
            ('Zero-band tolerance (in)', result['fixity']['zero_band_in']),
            ('Profiles without second crossing', result['fixity']['unresolved_count'])])
        for candidate in result['candidates']:
            selection.extend(dict(item=candidate['criterion']+' · '+key, value=candidate[key])
                for key in ('critical_embedment_ft','extension_ft','required_embedment_ft','raw_tip_elevation_ft','source','status'))
    trials = []
    for group in result['groups']:
        match = next((r for r in result['rows'] if r['series'] == group['series'] and
                      math.isclose(r['embedment_ft'], accepted, rel_tol=0, abs_tol=1e-6)), None)
        # Same columns for matched and unmatched series, including missing D/C
        # and convergence; these must never turn into a zero or a PASS.
        row = {k: None for k in ('series', 'trial', 'combination', 'pile', 'embedment_ft',
                                 'displacement_in', 'delta_in', 'dc', 'converged', 'status')}
        row.update(series=group['series'], embedment_ft=accepted)
        if match is None:
            row['status'] = 'No analyzed trial at selected embedment; results not interpolated'
        else:
            row.update({k: match.get(k) for k in row if k != 'status'})
            flags = []
            if match['converged'] is False:
                flags.append('Did not converge')
            elif match['converged'] is None:
                flags.append('Convergence not supplied')
            if match['dc'] is None:
                flags.append('D/C not supplied')
            elif match['dc'] > 1:
                flags.append('D/C exceeds 1')
            if not match['passes']:
                flags.append('Displacement-change limit not met at this trial')
            if not match.get('analysis_ok', True) and match['converged'] is not False and (match['dc'] is None or match['dc'] <= 1):
                flags.append('Next shallower trial has a supplied D/C / convergence failure')
            row['status'] = '; '.join(flags) or 'Within supplied trial criteria'
        trials.append(row)
    return dict(selection=selection, trials=trials, notes=notes.strip(),
                xml_reference=review['filename'], xml_sha256=review['sha256'])
