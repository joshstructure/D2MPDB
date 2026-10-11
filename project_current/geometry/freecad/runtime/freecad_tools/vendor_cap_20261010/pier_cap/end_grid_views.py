"""End U-bar projections from the same 3D paths used by the face checks."""
from html import escape
import plotly.graph_objects as go
from .end_grid import geometry, settings, enabled
from .output_labels import numbered_figure

COLORS = {'horizontal':'#c14f12', 'vertical':'#3c8553'}


def add_projection(fig, e, view, *, end=None, row=None, col=None, both_axes_ft=False):
    seen = set()
    for bar in geometry(e):
        if end and bar['end'] != end: continue
        points = bar['points']; direction = bar['direction']; group = 'end_'+bar['end']+'_'+direction
        projected = view == 'section'
        label = f'{bar["end"].title()} end · {direction} hooked bar · #{bar["bar"]}'
        if projected: label += ' · projected from end'
        hover = (f'{bar["id"]} · #{bar["bar"]}<br>Return after bend {bar["return_in"]:g} in'
                 f'<br>Inside bend diameter {bar["inside_diameter_in"]:g} in'
                 f'<br>End-face crosspiece station {bar["plane_in"]:.3f} in'
                 f'<br>Nominal grid c/c {bar["pitch_in"]:.3f} in; stagger {bar["shift_in"]:+.3f} in'+
                 f'<br>{escape(bar["placement_note"])}'+
                 ('<br>End-face projection; not reinforcement at this pile/span section' if projected else ''))
        meta=dict(part='end_grid',id=bar['id'],end=bar['end'],direction=direction,bar=bar['bar'],projection=view)
        shared=dict(name=label,legendgroup=group,showlegend=group not in seen,meta=meta,
                    hovertemplate=hover+'<extra></extra>')
        if view == '3d':
            trace=go.Scatter3d(x=[v[0] for v in points],y=[v[1] for v in points],z=[v[2] for v in points],
                mode='lines',line=dict(color=COLORS[direction],width=6),**shared)
        else:
            xs=[v[1] if view in ('section','end') else v[0]/12 for v in points]
            ys=[v[1]/(12 if both_axes_ft else 1) if view=='plan' else v[2] for v in points]
            trace=go.Scatter(x=xs,y=ys,mode='lines',
                line=dict(color=COLORS[direction],width=1.5 if projected else 3,dash='dot' if projected else 'solid'),
                opacity=.5 if projected else 1.,**shared)
        fig.add_trace(trace,**(dict(row=row,col=col) if row else {}));seen.add(group)
    return fig


@numbered_figure(lambda e,end='left': 'end_grid_'+end)
def end_figure(e,end='left'):
    from .model import bar_positions
    from .transverse import scheduled_bars, bar_shape
    from .view_controls import drawing_controls
    p=e.case['inputs'];fig=go.Figure();bars=geometry(e)
    fig.add_shape(type='rect',x0=0,x1=p['b'],y0=0,y1=p['h'],fillcolor='#f2f5f7',line=dict(color='#213649',width=2),layer='below')
    physical=scheduled_bars(e.case)
    near=(physical[0] if end=='left' else physical[-1]) if physical else None
    if near:
        run=next(r for r in e.case['transverse_detail']['runs'] if r['id']==near['run'])
        outline=bar_shape(e,run)['points']
        fig.add_trace(go.Scatter(x=[v[0] for v in outline],y=[v[1] for v in outline],mode='lines',
            name='Nearest '+('closed hoop' if run['kind']=='hoop' else 'open pile U'),meta=dict(part='transverse'),
            line=dict(color='#7952a3',width=3),hovertemplate=f'{near["id"]} · station {near["station_in"]:.3f} in<extra></extra>'))
    main=bar_positions(e,'P')
    fig.add_trace(go.Scatter(x=[b['x'] for b in main],y=[b['y'] for b in main],mode='markers',
        name='Longitudinal bars behind end grid',meta=dict(part='top'),marker=dict(color='#1f5b91',size=7),
        hovertemplate='Longitudinal bars run into the cap; not end-face crosspieces<extra></extra>'))
    add_projection(fig,e,'end',end=end)
    if not any(b['end']==end for b in bars):
        fig.add_annotation(x=p['b']/2,y=p['h']/2,text='End grid not enabled at this end',showarrow=False)
    fig.update_layout(template='plotly_white',height=560,title=f'{end.title()} end-face grid · looking along cap · {p["b"]:g} × {p["h"]:g} in',
        margin=dict(l=50,r=25,t=80,b=120),legend=dict(orientation='h',y=-.18,font=dict(size=10)))
    fig.update_xaxes(title='Across cap (in)',range=[-3,p['b']+3],constrain='domain')
    fig.update_yaxes(title='Above cap underside (in)',range=[-3,p['h']+3],scaleanchor='x',scaleratio=1)
    return drawing_controls(fig)


def summary_html(e):
    if not enabled(e.case): return ''
    bars=geometry(e);s=settings(e.case)
    lines=[]
    for end in ('left','right'):
        for direction in ('horizontal','vertical'):
            group=[b for b in bars if b['end']==end and b['direction']==direction]
            if group:
                b=group[0]
                gaps=[v['coordinate_in']-u['coordinate_in'] for u,v in zip(group,group[1:])]
                pitch=f'{min(gaps):.3f}–{max(gaps):.3f} in actual c/c' if gaps else 'single bar'
                lines.append(f'{end.title()} {direction}: {len(group)} × #{b["bar"]}, {pitch}, '
                             f'{b["return_in"]:g} in straight hook tails, {b["inside_diameter_in"]:g} in inside bend; {b["hook_mode"]} hooks')
    return '<p><b>End-face U grids:</b> '+escape('; '.join(lines) or 'No bars entered')+'.<br>'+\
        'Orange = horizontal crosspieces; green = vertical crosspieces. Return legs point into the cap. '+\
        'Dotted overlays on pile/span sections are projections from the ends, not full-length steel. '+\
        'Anchorage and pile-clearance review remains pending.</p>'
