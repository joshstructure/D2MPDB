"""Overlay existing sectional resistances without inventing local analysis."""
from collections import defaultdict
import html
import math
import plotly.graph_objects as go

from .detailing import hook_paths
from .model import PILE_GEOMETRY, bar_positions
from .transverse import enabled, shear_intervals
from .force_trace import joined_trace,RESISTANCE,THRESHOLD


def resistance_traces(e):
    """Return (trace, subplot row) pairs and a plain-text explanation.

    Coordinates share the analyzed cap's left edge only when pile layout and
    ends still match. Width/depth trials retain their original analysis forces.
    """
    case=e.case;p=case['inputs'];g=case['analysis']['geometry']
    moved=[k for k in PILE_GEOMETRY if not math.isclose(p[k],g[k],rel_tol=0,abs_tol=1e-6)]
    if moved:
        return [], ('RESISTANCE OVERLAY UNAVAILABLE: pile layout or cap ends differ from the plotted analysis ('
                    +', '.join(moved)+'). Apply matching analysis before overlaying station-based resistances.')
    ends=case['analysis']['xml_audit']['end_records']
    length=(max(r['x_in'] for r in ends)-min(r['x_in'] for r in ends))/12
    traces=[]

    def add(key,name,row,segments,color,unit,*,sign=1,legend=True,kind='resistance',basis=''):
        points=[]
        for left,right,value,detail in segments:
            if not (0<=left<right<=length+1e-6):continue
            points.extend([(left,sign*value,html.escape(detail)),(right,sign*value,html.escape(detail)),None])
        x,y,notes=joined_trace(points)
        if not x:return
        traces.append((go.Scatter(x=x,y=y,customdata=notes,name=name,
            mode='lines',connectgaps=False,legendgroup=key,showlegend=legend,
            line=dict(color=color,width=2.5 if kind=='threshold' else 3.5,dash='solid',shape='linear',simplify=False),
            meta=dict(role=kind,capacity=key,basis=basis),
            hovertemplate=f'{html.escape(name)}<br>x = %{{x:.3f}} ft<br>%{{y:.2f}} {unit}'
                '<br>%{customdata}<extra></extra>'),row))

    sectional='Factored sectional resistance; development, cutoffs and other checks remain separate.'
    add('Mr_N','M− resistance · top steel',1,[(0,length,e.value('Mr_N','kip*ft'),sectional)],
        RESISTANCE,'kip-ft',sign=-1,basis=sectional)
    spans=defaultdict(list)
    for path in hook_paths(e,bar_positions(e,'B')):
        spans[path['span']].append(path)
    added=[]
    for span,paths in sorted(spans.items()):
        left=max(v['left']+v['radius'] for v in paths)/12
        right=min(v['right']-v['radius'] for v in paths)/12
        if 0<=left<right<=length+1e-6:
            added.append((left,right,e.value('Mr_B','kip*ft'),
                f'Span {span}: continuous + all added bars, common straight portion only. '
                'Development is not established by the drawn hook; bends/ends use the continuous-bottom reference.'))
    # One positive resistance outline: retain the existing continuous-bottom
    # value between supplemented spans, then step at each span's exact limits.
    positive=[];cursor=0.;baseline=e.value('Mr_P','kip*ft')
    base_note='Continuous bottom steel only at this station. '+sectional
    for left,right,value,detail in sorted(added):
        if left>cursor:positive.append((cursor,left,baseline,base_note))
        positive.append((left,right,value,detail));cursor=right
    if cursor<length:positive.append((cursor,length,baseline,base_note))
    add('Mr_B' if added else 'Mr_P','M+ resistance · current steel',1,positive,RESISTANCE,'kip-ft',
        basis='Continuous-bottom sectional value with the combined value over the common straight portions of added span bars; development pending.')

    note=(f'CURRENT CONFIGURATION: {p["b"]:g} × {p["h"]:g} in. Solid orange lines are factored sectional resistances, '
          'shown for strength demands only. M− uses top steel; M+ shows the continuous-bottom reference and '
          'steps to the continuous-plus-added value only over the common straight portions of the drawn span bars. '
          'Development, cutoffs, cage fit and the other D/C checks still apply. ')
    if enabled(case):
        segments=[(v['a']['station_in']/12,v['b']['station_in']/12,v['vr'],
            f'{v["a"]["id"]} → {v["b"]["id"]}: {v["pitch"]:.3f} in pitch; '
            f'LRFD / FDOT 2026 intersected-leg calculation. Check the LRFD tab for anchorage and applicability status.')
            for v in shear_intervals(e)]
        key='Vr_actual';name='Shear resistance · actual intervals (conditional)'
        basis='Minimum actual LRFD / FDOT 2026 resistance over each interval; unresolved anchorage remains conditional.'
        note+=('Shear follows the actual LRFD / FDOT 2026 intersected-leg results over each interval. '
               'No resistance is extended beyond the first/last bar or across invalid intervals; anchorage and force-zone review remain conditional. ')
        if not any(0<=a<b<=length+1e-6 for a,b,_,_ in segments):
            note+='No valid adjacent transverse intervals are available, so no shear resistance is drawn. '
    else:
        value=min(e.value('Vr_G','kip'),e.value('Vr_L','kip'))
        key='Vr_uniform';name='Shear resistance · lower of G/L (uniform reference)'
        basis='Conservative lower of the existing G/L uniform-cage resistances; G/L have no assigned station extents.'
        segments=[(0,length,value,basis)]
        note+='Uniform shear uses the lower of G/L because their station extents are not defined. '
    for sign in (1,-1):
        add(key,name,2,segments,RESISTANCE,'kip',sign=sign,legend=sign==1,basis=basis)
    threshold='Investigation threshold only; this is not torsional resistance or a combined shear/torsion check.'
    threshold_value=e.value('T_threshold','kip*ft')
    if e.lrfd:
        from .lrfd_checks import torsion_threshold
        threshold_value=min((r['threshold_kip_ft'] for r in e.lrfd['longitudinal']),default=torsion_threshold(e))
        threshold+=' Actual-cage display uses the minimum axial-adjusted threshold across analyzed segments.'
    add('T_threshold','Torsion investigation threshold · not resistance',3,
        [(0,length,threshold_value,threshold)],THRESHOLD,'kip-ft',kind='threshold',basis=threshold)
    note+='Torsion shows only its investigation threshold, not a torsional resistance. Open U-bars receive no closed-hoop torsion credit. '
    if any(not math.isclose(p[k],g[k],rel_tol=0,abs_tol=1e-6) for k in ('b','h')):
        note+='TRIAL SECTION: resistance uses the current size while demand retains the analyzed size and forces. '
    return traces,note
