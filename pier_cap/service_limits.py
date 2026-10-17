"""Invert the existing service checks for display; do not change their criteria.

Moments are kip-ft, lengths inches, and stresses ksi. No strength resistance
factor belongs in these cracked elastic service limits.
"""
import math
import html
from collections import defaultdict

import plotly.graph_objects as go

from .model import bar_positions
from .detailing import row_spacing, hook_paths
from .force_trace import joined_trace

STRESS_COLOR = '#bf4a00'
SPACING_COLOR = '#7a3ea1'


def service_limit(e, state, region, *, continuous_reference=False):
    """Moment at the first stress/spacing limit, including drawn row spacing.

The continuous reference also checks the full row outside pile footprints;
the pile-gap exclusion must never be carried into unreinforced span portions.
"""
    if state not in ('I', 'III') or region not in 'NPB':
        raise ValueError('Expected Service I / III and region N / P / B.')
    p = e.case['inputs']
    reason = ('Service I applicability requires fy < 75 ksi.' if state == 'I' and p['fy'] >= 75 else
              'Service III inputs / applicability are not confirmed.' if state == 'III' and not p['Ready_III'] else '')
    layer = 'Top row 1' if region == 'N' else 'Bottom row 1'
    bars = [b for b in bar_positions(e, 'B' if region == 'B' else 'P') if b['layer'] == layer]
    drawn = row_spacing(e, bars, at_pile=region != 'B')['pitch_in']
    pitch = max(e.value('SP_'+region, 'in'), drawn)
    if continuous_reference:
        pitch = max(pitch, row_spacing(e, bars)['pitch_in'])
    # fs = n M / Ss; M is converted from kip-ft to kip-in.
    centroid_rate = 12 * e.value('n_mod') / e.value('Ss_'+region, 'in^3')
    outer_rate = 12 * e.value('n_mod') * (p['h']-e.value('ccr_'+region)-e.value('do_'+region)) / e.value('Icr_'+region)
    stress_rate = centroid_rate if state == 'I' else outer_rate
    stress_limit = e.value('fs_I_limit', 'ksi') if state == 'I' else 24.
    # S_allow >= s  <=>  fs <= 700 gamma_e / [bs (s + 2 dc)].
    spacing_stress = 700*p['gamma_e'] / (e.value('bs_'+region)*(pitch+2*e.value('dc_'+region)))
    values = (centroid_rate, stress_rate, spacing_stress, stress_limit)
    if any(not math.isfinite(v) or v <= 0 for v in values):
        reason = 'No valid cracked-section service limit for this section.'
    stress_m = stress_limit/stress_rate if stress_rate > 0 else None
    spacing_m = spacing_stress/centroid_rate if centroid_rate > 0 else None
    available = not reason
    limit = min(stress_m, spacing_m) if available else None
    return dict(state=state, region=region, available=available, reason=reason,
                stress_moment=stress_m if available else None,
                spacing_moment=spacing_m if available else None, moment=limit,
                stress_limit=stress_limit, spacing_stress=spacing_stress,
                stress_rate=stress_rate, centroid_rate=centroid_rate, pitch=pitch,
                controlling=('Steel stress' if stress_m <= spacing_m else 'Crack-control spacing') if available else 'Unavailable')


def moment_segments(e, state, length):
    """(left, right, sign, limit record) with common added-bar straight extents."""
    top = service_limit(e, state, 'N', continuous_reference=True)
    base = service_limit(e, state, 'P', continuous_reference=True)
    span = service_limit(e, state, 'B')
    result = [(0., length, -1, top)]
    paths = defaultdict(list)
    for path in hook_paths(e, bar_positions(e, 'B')):
        paths[path['span']].append(path)
    intervals = []
    for group in paths.values():
        left = max(v['left']+v['radius'] for v in group)/12
        right = min(v['right']-v['radius'] for v in group)/12
        if 0 <= left < right <= length+1e-6:
            intervals.append((left, right))
    cursor = 0.
    for left, right in sorted(intervals):
        if left > cursor: result.append((cursor, left, 1, base))
        result.append((left, right, 1, span))
        cursor = right
    if cursor < length: result.append((cursor, length, 1, base))
    return result


def service_traces(e, length):
    traces = []
    segments = {state: moment_segments(e, state, length) for state in ('I', 'III')}
    for state, rows in segments.items():
        for key, label, color in [('stress_moment', 'steel-stress limit', STRESS_COLOR),
                                  ('spacing_moment', 'crack-spacing limit', SPACING_COLOR)]:
            for sign in (-1, 1):
                points = []
                for left, right, direction, r in rows:
                    if direction != sign or not r['available']: continue
                    note = (f'Region {r["region"]}; checked pitch {r["pitch"]:.3f} in. '
                            f'First limit: {r["moment"]:.2f} kip-ft ({r["controlling"]}). '
                            'Sectional reference; development and detailing checks remain separate.')
                    points.extend([(left, sign*r[key], note), (right, sign*r[key], note), None])
                x, y, notes = joined_trace(points)
                if x:
                    name = f'Service {state} {label}'
                    traces.append((go.Scatter(x=x, y=y, customdata=notes, mode='lines', name=name,
                        legendgroup=f'service-{state}-{key}', showlegend=sign == -1,
                        line=dict(color=color, width=3, dash='dash' if key == 'spacing_moment' else 'solid', simplify=False),
                        meta=dict(role='service_limit', state='SERVICE-'+state, capacity=key),
                        hovertemplate=name+'<br>x = %{x:.3f} ft<br>%{y:.2f} kip-ft<br>%{customdata}<extra></extra>'), 1))
    notes = ('Service I / III moment limits invert the existing cracked-section stress and spacing checks. '
             'The nearer-to-zero line governs. Service moment utilization is |M| / first moment limit; '
             'it is not the nonlinear spacing D/C. Continuous-only portions conservatively retain the full-row spacing '
             'outside piles; added bars are credited only over their common straight extents. '
             'Development, cutoffs and applicability remain separate. '
             'No service shear or torsion limit is defined in this calculator; those two panels show demands only.')
    for state, rows in segments.items():
        reasons = list(dict.fromkeys(r['reason'] for _, _, _, r in rows if r['reason']))
        if reasons: notes += f' Service {state} overlay unavailable: '+ ' '.join(reasons)
    return traces, segments, notes


def moment_hover(rows, x, moment):
    sign = -1 if moment < 0 else 1
    candidates = [r for a, b, s, r in rows if s == sign and a-1e-9 <= x <= b+1e-9]
    active = [r for r in candidates if r['available']]
    if not active:
        return 'Service limit unavailable: '+html.escape(next((r['reason'] for r in candidates), 'no matched section'))
    r = min(active, key=lambda r:r['moment'])  # conservative at a step boundary
    ratio = abs(moment)/r['moment']
    margin = r['moment']-abs(moment)
    return (f'Service moment utilization: {ratio:.3f} ({ratio:.1%})<br>'
            f'Moment limit: {r["moment"]:.2f} kip-ft · {r["controlling"]}<br>'
            f'Remaining moment: {margin:.2f} kip-ft ({1-ratio:.1%})<br>'
            'Sectional comparison; see applicability / development checks')


def add_stress_limits(fig, e, state, labels, *, row, col):
    """Stress axes also show spacing's equivalent stress, in the SAME basis."""
    rows = [service_limit(e, state, z) for z in 'NPB']
    if not all(r['available'] for r in rows):
        fig.add_annotation(x=.5, y=.95, xref=f'x{((row-1)*2+col) if (row-1)*2+col>1 else ""} domain',
            yref=f'y{((row-1)*2+col) if (row-1)*2+col>1 else ""} domain', showarrow=False,
            text=html.escape(rows[0]['reason']), font=dict(color=STRESS_COLOR, size=10))
        return
    for field, name, color in [('stress_moment', 'steel-stress limit', STRESS_COLOR),
                                ('spacing_moment', 'crack-spacing equivalent stress', SPACING_COLOR)]:
        values = [r[field]*r['stress_rate'] for r in rows]
        notes = []
        for z, r in zip('NPB', rows):
            demand = e.value(('MI_' if state == 'I' else 'MIII_')+z, 'kip*ft')
            notes.append(moment_hover([(0, 1, 1, r)], .5, demand))
        fig.add_trace(go.Scatter(x=labels, y=values, mode='lines+markers',
            name=f'Service {state} {name}', customdata=notes,
            line=dict(color=color, width=2, dash='dash' if field == 'spacing_moment' else 'solid'),
            meta=dict(role='service_limit', state='SERVICE-'+state, capacity=field),
            hovertemplate='%{x}<br>Limit %{y:.3f} ksi<br>%{customdata}<extra></extra>'), row=row, col=col)
