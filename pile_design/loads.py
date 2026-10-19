"""Pile demand records from an FB-MultiPier export, with the downdrag drag load DR.

Axial force is reported compression-positive (FBMP is tension-positive). Structural
demands add the drag load per LRFD Table 3.4.1-1 (gamma_DR = 1.10 at the strength limit
states, 1.00 at Service I; 3.11.8, 10.7.1.6.2, 10.7.3.7): P_u = P_fbmp + gamma_DR * DD. The
drag load is applied at every station, which is conservative below the neutral plane.
The Factored Design Load of the Pile Data Table is the strength head compression
without DD (SDM 11.4 column I); downdrag is column J.
"""
import math

ROUND = 6


def limit_of(state):
    """'strength', 'service' or 'extreme' from the FBMP limit-state label."""
    s = (state or '').upper()
    if s.startswith('STRENGTH'):
        return 'strength'
    if s.startswith('SERVICE'):
        return 'service'
    return 'extreme' if s.startswith('EXTREME') else 'other'


def wind_combinations(review):
    """Combination numbers whose WS or WL factor is nonzero (wind scope, as pile_review)."""
    out = set()
    for number, factors in (review.get('combination_factors') or {}).items():
        if any(k[:2] in ('WS', 'WL') and abs(v) > 0 for k, v in factors.items()):
            out.add(number)
    return out


def gamma_for(limit, gamma_str, gamma_ser):
    return gamma_str if limit == 'strength' else gamma_ser if limit == 'service' else gamma_ser


def demands_from_xml(review, DD_kip, gamma_str=1.10, gamma_ser=1.00):
    """One record per (combination, pile, element end): the station records of the export."""
    wind = wind_combinations(review)
    records = []
    for r in review['forces']:
        pile = review['piles'][r['pile']]
        head_el = -pile['head_xyz_in'][2] / 12.0
        limit = limit_of(r['state'])
        gamma = gamma_for(limit, gamma_str, gamma_ser)
        p_fbmp = -r['axial_tension_kip']
        m_res = math.hypot(r['m2'], r['m3'])
        records.append(dict(
            combination=r['combination'], state=r['state'], limit=limit, wind=r['combination'] in wind,
            pile=r['pile'], local_element=r['local_element'], side=r['side'],
            head=r['local_element'] == 1 and r['side'] == 'I',
            distance_ft=round(r['distance_ft'], ROUND), elevation_ft=round(head_el - r['vertical_ft'], ROUND),
            P_fbmp=round(p_fbmp, ROUND), V2=r['v2'], V3=r['v3'], M2=r['m2'], M3=r['m3'],
            V_res=round(math.hypot(r['v2'], r['v3']), ROUND), M_res=round(m_res, ROUND),
            P_u=round(p_fbmp + gamma * DD_kip, ROUND), M_u=round(m_res, ROUND), gamma_DR=gamma,
            torque=r['torque'], model_dc=r['model_dc']))
    return records


def restate(records, DD_kip, gamma_str=1.10, gamma_ser=1.00):
    """Recompute P_u of saved records for the current DD and gamma_DR (no XML needed)."""
    out = []
    for r in records:
        gamma = gamma_for(r['limit'], gamma_str, gamma_ser)
        out.append(dict(r, gamma_DR=gamma, P_u=round(r['P_fbmp'] + gamma * DD_kip, ROUND)))
    return out


def record_id(r):
    return f"combo {r['combination']} {r['state']} · pile {r['pile']} · element {r['local_element']}{r['side']} · EL {r['elevation_ft']:.2f} ft"


def head_envelope(records):
    """Per limit-state label: maximum head compression, maximum head uplift and concurrent moments."""
    heads = [r for r in records if r['head']]
    envelope = {}
    for state in dict.fromkeys(r['state'] for r in heads):
        rows = [r for r in heads if r['state'] == state]
        comp = max(rows, key=lambda r: r['P_fbmp'])
        up = min(rows, key=lambda r: r['P_fbmp'])
        envelope[state] = dict(
            limit=rows[0]['limit'], max_compression_kip=max(comp['P_fbmp'], 0.0), compression_record=comp,
            concurrent_M_res=comp['M_res'], max_uplift_kip=max(-up['P_fbmp'], 0.0), uplift_record=up,
            concurrent_M_res_uplift=up['M_res'], max_M_res=max(r['M_res'] for r in rows),
            max_V_res=max(r['V_res'] for r in rows))
    return envelope


def fdl_and_tension(records):
    """Factored Design Load (strength head compression without DD, kip) and head uplift (kip)."""
    heads = [r for r in records if r['head'] and r['limit'] == 'strength']
    if not heads:
        return dict(FDL_kip=0.0, FDL_record=None, T_kip=0.0, T_record=None)
    comp = max(heads, key=lambda r: r['P_fbmp'])
    up = min(heads, key=lambda r: r['P_fbmp'])
    return dict(FDL_kip=max(comp['P_fbmp'], 0.0), FDL_record=comp, T_kip=max(-up['P_fbmp'], 0.0), T_record=up if up['P_fbmp'] < 0 else None)


def max_tension(records, limit='strength'):
    """Largest net uplift (kip) at any station and its record; the drag load does not relieve it."""
    rows = [r for r in records if r['limit'] == limit]
    if not rows:
        return 0.0, None
    worst = min(rows, key=lambda r: r['P_fbmp'])
    return (max(-worst['P_fbmp'], 0.0), worst if worst['P_fbmp'] < 0 else None)


def model_dc_max(records, limit=None):
    values = [(r['model_dc'], r) for r in records if r['model_dc'] is not None and (limit is None or r['limit'] == limit)]
    if not values:
        return None, None
    return max(values, key=lambda v: v[0])


def governing(records, dc_function, tol=1e-9):
    """The record with the largest D/C from dc_function(record), keeping ties.

    Returns dict(record, dc, ties) or None when no record has a finite ratio. Adjacent elements share a
    node, so a tie list is normal; every tied record is retained."""
    best, ties, scored = None, [], []
    for r in records:
        dc = dc_function(r)
        if dc is None or not math.isfinite(dc):
            continue
        scored.append((dc, r))
    if not scored:
        return None
    top = max(dc for dc, _ in scored)
    ties = [r for dc, r in scored if dc >= top - tol * max(1.0, abs(top))]
    best = ties[0]
    return dict(record=best, dc=top, ties=ties)
