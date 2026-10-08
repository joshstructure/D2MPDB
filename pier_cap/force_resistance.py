"""Overlay existing sectional resistances without inventing local analysis."""
from collections import defaultdict
import html
import math
import plotly.graph_objects as go

from .detailing import hook_paths
from .model import PILE_GEOMETRY, bar_positions
from .transverse import enabled, shear_intervals


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
        x=[];y=[];notes=[]
        for left,right,value,detail in segments:
            if not (0<=left<right<=length+1e-6):continue
            x.extend([left,right,None]);y.extend([sign*value,sign*value,None])
            notes.extend([html.escape(detail),html.escape(detail),''])
        if not x:return
        traces.append((go.Scatter(x=x,y=y,customdata=notes,name=name,
            mode='lines',connectgaps=False,legendgroup=key,showlegend=legend,
            line=dict(color=color,width=2.5,dash='dot' if kind=='threshold' else 'longdash'),
            meta=dict(role=kind,capacity=key,basis=basis),
            hovertemplate=f'{html.escape(name)}<br>x = %{{x:.3f}} ft<br>%{{y:.2f}} {unit}'
                '<br>%{customdata}<extra></extra>'),row))

    sectional='Factored sectional resistance; development, cutoffs and other checks remain separate.'
    add('Mr_N','M− resistance · top steel',1,[(0,length,e.value('Mr_N','kip*ft'),sectional)],
        '#16804a','kip-ft',sign=-1,basis=sectional)
    add('Mr_P','M+ resistance · continuous bottom',1,[(0,length,e.value('Mr_P','kip*ft'),sectional)],
        '#16804a','kip-ft',basis=sectional)
    spans=defaultdict(list)
    for path in hook_paths(e,bar_positions(e,'B')):
        spans[path['span']].append(path)
    added=[]
    for span,paths in sorted(spans.items()):
        left=max(v['left']+v['radius'] for v in paths)/12
        right=min(v['right']-v['radius'] for v in paths)/12
        added.append((left,right,e.value('Mr_B','kip*ft'),
            f'Span {span}: continuous + all added bars, common straight portion only. '
            'Development is not established by the drawn hook; bends/ends use the continuous-bottom reference.'))
    add('Mr_B','M+ resistance · continuous + added',1,added,'#008b8b','kip-ft',
        basis='Sectional value only within the common straight portions of the drawn added bars; development pending.')

    note=(f'CURRENT CONFIGURATION: {p["b"]:g} × {p["h"]:g} in. Dashed lines are factored sectional resistances, '
          'shown for strength demands only. M− uses top steel; M+ shows the continuous-bottom reference and '
          'the continuous-plus-added value only over the common straight portions of the drawn span bars. '
          'Development, cutoffs, cage fit and the other D/C checks still apply. ')
    if enabled(case):
        segments=[(v['a']['station_in']/12,v['b']['station_in']/12,v['vr'],
            f'{v["a"]["id"]} → {v["b"]["id"]}: {v["pitch"]:.3f} in pitch; '
            f'weaker two-leg area {v["area"]:.3f} in². Anchorage and local force zones remain conditional.')
            for v in shear_intervals(e)]
        key='Vr_actual';name='Shear resistance · actual intervals (conditional)'
        basis='Existing actual-interval shear check; developed vertical legs and local force-zone review required.'
        note+=('Shear follows the actual adjacent hoop/U-bar intervals and the weaker two-leg area. '
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
        add(key,name,2,segments,'#9b3f89','kip',sign=sign,legend=sign==1,basis=basis)
    threshold='Investigation threshold only; this is not torsional resistance or a combined shear/torsion check.'
    add('T_threshold','Torsion investigation threshold · not resistance',3,
        [(0,length,e.value('T_threshold','kip*ft'),threshold)],'#967000','kip-ft',kind='threshold',basis=threshold)
    note+='Torsion shows only its investigation threshold, not a torsional resistance. Open U-bars receive no closed-hoop torsion credit. '
    if any(not math.isclose(p[k],g[k],rel_tol=0,abs_tol=1e-6) for k in ('b','h')):
        note+='TRIAL SECTION: resistance uses the current size while demand retains the analyzed size and forces. '
    return traces,note
