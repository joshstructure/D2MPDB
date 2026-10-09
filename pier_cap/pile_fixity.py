"""Second signed displacement crossings and comparison of minimum-tip criteria.

Crossings are interpolated from the imported nodal results, not extrapolated.
They are a profile criterion, not a replacement for the shortened-pile study.
"""
from copy import deepcopy
import math
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


def displacement_fixity(review, cutoff=None, ground=None, zero_band=1e-6):
    require(math.isfinite(zero_band) and zero_band >= 0, 'Zero band must be nonnegative and finite.')
    for value in (cutoff, ground):
        require(value is None or math.isfinite(value), 'Elevations must be finite.')
    profiles = []
    if review:
        grouped = {}
        for row in review['displacements']:
            grouped.setdefault((row['combination'], row['pile']), []).append(row)
        for combo in review['combinations']:
            for pile in review['piles']:
                rows = grouped.get((combo, pile), [])
                for component in ('dx', 'dy'):
                    crossings = zero_crossings(rows, component, zero_band)
                    active = any(abs(r[component]) > zero_band for r in rows)
                    second = crossings[1] if len(crossings)>1 else None
                    elevation = cutoff-second['vertical_ft'] if cutoff is not None and second else None
                    profiles.append(dict(combination=combo, state=review['combinations'][combo], pile=pile,
                        component=component.upper(), active=active, crossings=crossings, crossing_count=len(crossings),
                        second_distance_ft=second['distance_ft'] if second else None,
                        second_vertical_ft=second['vertical_ft'] if second else None,
                        second_elevation_ft=elevation,
                        critical_embedment_ft=ground-elevation if ground is not None and elevation is not None else None,
                        status=('Second crossing found' if second else 'Fewer than two crossings' if active else
                                'No profile records' if not rows else 'Within zero band; not governing')))
    found = [p for p in profiles if p['second_vertical_ft'] is not None]
    deepest = max((p['second_vertical_ft'] for p in found), default=None)
    governors = [p for p in found if math.isclose(p['second_vertical_ft'], deepest, abs_tol=1e-8, rel_tol=0)]
    unresolved = [p for p in profiles if (p['active'] and p['crossing_count']<2) or p['status']=='No profile records']
    return dict(profiles=profiles, governors=governors, unresolved_count=len(unresolved), zero_band_in=zero_band,
                complete=bool(governors) and not unresolved, cutoff_elevation_ft=cutoff, ground_elevation_ft=ground)


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
        extension_ft=trials['extension_ft'] if trials else None,
        required_embedment_ft=trials['required_embedment_ft'] if trials else None,
        raw_tip_elevation_ft=ground-trials['required_embedment_ft'] if ground is not None and trials and trials['required_embedment_ft'] is not None else None,
        source='; '.join(g['series'] for g in trials['groups'] if g['candidate_ft']==trial_critical) if trials else '',
        status='Available' if trial_critical is not None else 'No qualifying trial pair' if trials else 'Trials not calculated'))
    governors = fixity['governors']
    profile = governors[0] if governors else None
    critical = profile['critical_embedment_ft'] if profile else None
    status = 'Available'
    if not profile: status = 'Second crossing unavailable'
    elif cutoff is None or ground is None:
        missing = (['Pile cutoff EL (ft)'] if cutoff is None else []) + (['Ground EL (ft)'] if ground is None else [])
        status = 'Enter '+' and '.join(missing)+' at the top of Minimum tip'
    elif critical <= 0: status = 'Second crossing is not below design ground / scour'
    added = required = tip = None
    if status == 'Available':
        added = (extension if mode=='fixed' else fraction*critical if mode=='fraction' else min(extension, fraction*critical)) if add_fixity_allowance else 0.
        required = critical+added
        tip = ground-required
    candidates.append(dict(criterion='Second zero crossing', critical_embedment_ft=critical, extension_ft=added,
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
    complete = len(available)==2 and fixity['complete'] and raw_tip is not None
    label = ' + '.join(c['criterion'] for c in controlling) + (' (tie)' if len(controlling)>1 else '')
    base = deepcopy(trials) if trials else dict(rows=[], groups=[])
    base.update(candidates=candidates, controlling_criterion=label or 'Unavailable', comparison_complete=complete,
        critical_embedment_ft=controlling[0]['critical_embedment_ft'] if controlling else None,
        accepted_embedment_ft=controlling[0]['critical_embedment_ft'] if controlling else None,
        extension_ft=controlling[0]['extension_ft'] if controlling else None,
        required_embedment_ft=maximum, raw_tip_elevation_ft=raw_tip, tip_elevation_ft=tip, total_length_ft=length,
        fixity=fixity, add_fixity_allowance=add_fixity_allowance,
        basis='Deeper required tip from displacement-change trials and the deepest second signed DX/DY zero crossing across all imported piles and combinations. '
              +('The selected allowance applies to both criteria.' if add_fixity_allowance else 'No allowance is added to the crossing criterion.')
              +(' Comparison is incomplete; shown tip uses available criteria only.' if not complete else ''))
    return base
