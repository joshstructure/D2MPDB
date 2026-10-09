"""Second signed displacement crossings and comparison of minimum-tip criteria.

Crossings are interpolated from the imported nodal results, not extrapolated.
They are a profile criterion, not a replacement for the shortened-pile study.
"""
from copy import deepcopy
import math
import re
from .pile_review import require


def zero_crossings(rows, component, zero_band=1e-6):
    """Count sign reversals once; touches and a zero tail are not crossings."""
    require(math.isfinite(zero_band) and zero_band >= 0, 'Zero band must be nonnegative and finite.')
    data = sorted(rows, key=lambda r: r['distance_ft'])
    require(all(b['distance_ft'] > a['distance_ft'] and b['vertical_ft'] > a['vertical_ft']
                for a, b in zip(data, data[1:])), 'Pile profile stations must increase from head to tip without duplicates.')
    crossings, previous, zero_rows = [], None, []
    for row in data:
        value = row[component]
        require(math.isfinite(value), 'Displacements must be finite.')
        if abs(value) <= zero_band:
            if previous is not None: zero_rows.append(row)
            continue
        if previous is not None and previous[component]*value < 0:
            if zero_rows:
                # The exact crossing inside a near-zero interval is unresolved.
                # Use its deeper end, retain the bracket, and label this choice.
                point = zero_rows[-1]
                distance, vertical = point['distance_ft'], point['vertical_ft']
                method = 'Zero-band interval; deeper end used' if len(zero_rows)>1 else 'Zero-band node'
            else:
                ratio = abs(previous[component])/(abs(previous[component])+abs(value))
                distance = previous['distance_ft']+ratio*(row['distance_ft']-previous['distance_ft'])
                vertical = previous['vertical_ft']+ratio*(row['vertical_ft']-previous['vertical_ft'])
                method = 'Linear interpolation'
            crossings.append(dict(number=len(crossings)+1, distance_ft=distance, vertical_ft=vertical,
                upper_node=previous['node'], lower_node=row['node'], method=method))
        previous, zero_rows = row, []
    return crossings


def wind_combination_scope(review):
    """Use nonzero XML WS/WL factors, never limit-state names or deflections."""
    factors = review.get('combination_factors', {}) if review else {}
    rows = []
    for combo, state in (review['combinations'].items() if review else []):
        values = factors.get(combo)
        wind = {key: value for key,value in (values or {}).items()
                if re.fullmatch(r'(WS|WL)\d*', key.upper()) and value != 0}
        included = bool(wind) if values else None
        rows.append(dict(combination=combo, state=state, included=included, wind_factors=wind,
            wind_factor_label=', '.join(f'{k} = {v:g}' for k,v in wind.items()) or ('None' if values else 'Unknown'),
            scope_label='Included — wind' if included else 'Excluded — no wind' if included is False else 'Unknown — reload XML',
            basis='Nonzero WS/WL load factor in XML' if included else 'No nonzero WS/WL load factor in XML' if included is False
                  else 'Saved review lacks load factors. Reload the original XML to identify wind combinations.'))
    return rows


def displacement_fixity(review, cutoff=None, ground=None, zero_band=1e-6):
    require(math.isfinite(zero_band) and zero_band >= 0, 'Zero band must be nonnegative and finite.')
    for value in (cutoff, ground):
        require(value is None or math.isfinite(value), 'Elevations must be finite.')
    profiles = []
    scope = wind_combination_scope(review)
    wind = [s['combination'] for s in scope if s['included'] is True]
    excluded = [s['combination'] for s in scope if s['included'] is False]
    unknown = [s['combination'] for s in scope if s['included'] is None]
    if review:
        grouped = {}
        for row in review['displacements']:
            grouped.setdefault((row['combination'], row['pile']), []).append(row)
        for combo in review['combinations']:
            included = combo in wind
            scope_label = next(s['scope_label'] for s in scope if s['combination']==combo)
            for pile in review['piles']:
                rows = grouped.get((combo, pile), [])
                for component in ('dx', 'dy'):
                    crossings = zero_crossings(rows, component, zero_band) if included else []
                    active = any(abs(r[component]) > zero_band for r in rows)
                    second = crossings[1] if len(crossings)>1 else None
                    first = crossings[0] if crossings else None
                    elevation = cutoff-second['vertical_ft'] if cutoff is not None and second else None
                    issue = ('No profile records' if not rows else
                             f'Only {len(crossings)} crossing'+('s' if len(crossings)!=1 else '')+' found; two required'
                             if active and not second else '')
                    if not included: issue = ''
                    profiles.append(dict(combination=combo, state=review['combinations'][combo], pile=pile,
                        included_in_fixity=included, scope_label=scope_label,
                        component=component.upper(), active=active, crossings=crossings, crossing_count=len(crossings),
                        first_vertical_ft=first['vertical_ft'] if first else None,
                        first_elevation_ft=cutoff-first['vertical_ft'] if cutoff is not None and first else None,
                        second_distance_ft=second['distance_ft'] if second else None,
                        second_vertical_ft=second['vertical_ft'] if second else None,
                        second_elevation_ft=elevation,
                        critical_embedment_ft=ground-elevation if ground is not None and elevation is not None else None,
                        review_reason=issue,
                        status=(scope_label if not included else 'Second crossing found' if second else 'Fewer than two crossings' if active else
                                'No profile records' if not rows else 'Within zero band; not governing')))
    found = [p for p in profiles if p['second_vertical_ft'] is not None]
    deepest = max((p['second_vertical_ft'] for p in found), default=None)
    governors = [p for p in found if math.isclose(p['second_vertical_ft'], deepest, abs_tol=1e-8, rel_tol=0)]
    unresolved = [p for p in profiles if p['review_reason']]
    return dict(profiles=profiles, governors=governors, unresolved_count=len(unresolved), zero_band_in=zero_band,
                combination_scope=scope, wind_combinations=wind, excluded_combinations=excluded, unknown_combinations=unknown,
                applicable=bool(wind) if not unknown and review else True if wind else None,
                complete=bool(review) and not unknown and (not wind or (bool(governors) and not unresolved)),
                cutoff_elevation_ft=cutoff, ground_elevation_ft=ground,
                source_filename=review.get('filename') if review else None, source_sha256=review.get('sha256') if review else None)


def governor_label(profile):
    return f"Pile {profile['pile']} · combination {profile['combination']} ({profile['state']}) · {profile['component']}"


def compare_minimum_tip(trials, fixity, *, ground=None, cutoff=None, extension=5, fraction=.2,
                        mode='fixed', add_fixity_allowance=True, round_feet=False):
    """Compare candidates in one vertical datum and round only after selection."""
    for value in (extension, fraction):
        require(math.isfinite(value) and value >= 0, 'Minimum-tip allowances must be finite and nonnegative.')
    require(mode in ('fixed', 'fraction', 'lesser'), 'Choose fixed, percentage, or the lesser extension.')
    for value in (ground, cutoff):
        require(value is None or math.isfinite(value), 'Elevations must be finite.')
    candidates = []
    trial_critical = trials.get('critical_embedment_ft') if trials else None
    candidates.append(dict(criterion='Displacement-change trials', critical_embedment_ft=trial_critical,
        critical_elevation_ft=ground-trial_critical if ground is not None and trial_critical is not None else None,
        extension_ft=trials['extension_ft'] if trials else None,
        required_embedment_ft=trials['required_embedment_ft'] if trials else None,
        raw_tip_elevation_ft=ground-trials['required_embedment_ft'] if ground is not None and trials and trials['required_embedment_ft'] is not None else None,
        source='; '.join(g['series'] for g in trials['groups'] if g['candidate_ft']==trial_critical) if trials else '',
        status='Available' if trial_critical is not None else 'No qualifying trial pair' if trials else 'Trials not calculated'))
    governors = fixity['governors']
    profile = governors[0] if governors else None
    critical = profile['critical_embedment_ft'] if profile else None
    status = 'Available'
    if fixity['applicable'] is False: status = 'Not applicable — no wind combinations'
    elif not profile: status = 'Wind factors unknown — reload XML' if fixity['unknown_combinations'] else 'Second crossing unavailable in wind combinations'
    elif cutoff is None or ground is None:
        missing = (['Pile cutoff EL (ft)'] if cutoff is None else []) + (['Ground EL (ft)'] if ground is None else [])
        status = 'Enter '+' and '.join(missing)+' at the top of Minimum tip'
    elif critical <= 0: status = 'Second crossing is not below design ground / scour'
    added = required = tip = None
    if status == 'Available':
        added = (extension if mode=='fixed' else fraction*critical if mode=='fraction' else min(extension, fraction*critical)) if add_fixity_allowance else 0.
        required = critical+added
        tip = ground-required
        if fixity['unresolved_count']:
            status = f'Crossing available; {fixity["unresolved_count"]} other profiles need review'
    candidates.append(dict(criterion='Second zero crossing', critical_embedment_ft=critical, extension_ft=added,
        critical_elevation_ft=profile['second_elevation_ft'] if profile else None,
        required_embedment_ft=required, raw_tip_elevation_ft=tip,
        source='; '.join(governor_label(p) for p in governors), status=status))
    available = [c for c in candidates if c['required_embedment_ft'] is not None]
    maximum = max((c['required_embedment_ft'] for c in available), default=None)
    controlling = [c for c in available if math.isclose(c['required_embedment_ft'], maximum, rel_tol=0, abs_tol=1e-8)]
    for candidate in candidates: candidate['controls'] = candidate in controlling
    raw_tip = ground-maximum if maximum is not None and ground is not None else None
    tip = math.floor(raw_tip) if round_feet and raw_tip is not None else raw_tip
    length = cutoff-tip if cutoff is not None and tip is not None else None
    require(length is None or length > 0, 'Cutoff elevation must be above the required tip.')
    if round_feet and length is not None: length = math.ceil(length)
    complete = (len(available)==2 or (fixity['applicable'] is False and trial_critical is not None)) and fixity['complete'] and raw_tip is not None
    issues = []
    if ground is None: issues.append('Enter Ground EL (ft) at the top of Minimum tip.')
    if cutoff is None and fixity['applicable'] is not False: issues.append('Enter Pile cutoff EL (ft) at the top of Minimum tip; plotted depths alone are not project elevations.')
    if not trials:
        issues.append('Displacement-change trials are not calculated. Paste the trial rows and click Calculate minimum tip.')
    elif trial_critical is None:
        names = ', '.join(g['series'] for g in trials['groups'] if g['candidate_ft'] is None)
        issues.append('No qualifying displacement-change trial pair in: '+names+'.')
    if not fixity['profiles']:
        issues.append('Load pile displacement results to evaluate second zero crossings.')
    elif not governors and fixity['wind_combinations']:
        issues.append('No active wind profile has two resolved zero crossings; a first-crossing marker alone does not provide the second-crossing criterion.')
    if fixity['unknown_combinations']:
        issues.append('Wind load factors are unavailable for combinations '+', '.join(fixity['unknown_combinations'])+'. Reload the original XML; limit-state names alone do not identify wind loading.')
    if fixity['unresolved_count']:
        issues.append(f'{fixity["unresolved_count"]} profiles need review; see the pile, combination and direction listed in Table 7 — Profiles needing review. '
                      'Crossings found on other profiles remain available.')
    if critical is not None and critical <= 0:
        issues.append('The deepest second crossing is not below design ground / scour; check the elevations and profile.')
    label = ' + '.join(c['criterion'] for c in controlling) + (' (tie)' if len(controlling)>1 else '')
    base = deepcopy(trials) if trials else dict(rows=[], groups=[])
    base.update(candidates=candidates, controlling_criterion=label or 'Unavailable', comparison_complete=complete,
        comparison_issues=issues,
        critical_embedment_ft=controlling[0]['critical_embedment_ft'] if controlling else None,
        accepted_embedment_ft=controlling[0]['critical_embedment_ft'] if controlling else None,
        extension_ft=controlling[0]['extension_ft'] if controlling else None,
        required_embedment_ft=maximum, raw_tip_elevation_ft=raw_tip, tip_elevation_ft=tip, total_length_ft=length,
        fixity=fixity, add_fixity_allowance=add_fixity_allowance,
        basis='Deeper required tip from displacement-change trials and the deepest second signed DX/DY zero crossing across all piles in wind combinations (nonzero XML WS/WL load factors). '
              +('No wind combinations are present; the crossing criterion is not applicable. ' if fixity['applicable'] is False else '')
              +('The selected allowance applies to both criteria.' if add_fixity_allowance else 'No allowance is added to the crossing criterion.')
              +(' Comparison is incomplete; shown tip uses available criteria only.' if not complete else ''))
    return base
