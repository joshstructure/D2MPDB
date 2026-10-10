"""Full cap cage from the shared bar geometry, with true pile-section surfaces."""
from .output_labels import numbered_figure
import html
import math
import hashlib
import json
from collections import Counter
import plotly.graph_objects as go
from .model import bar_positions
from .detailing import hook_paths
from .transverse import scheduled_bars,bar_shape,enabled
from .pile_visual import pile_appearance
from .view_controls import visibility_buttons

COLORS={'top':'#1f5b91','bottom':'#448bc1','side':'#167b75','added':'#d88822','hoop':'#7952a3','pile_u':'#bd407d'}


def box_mesh(x0,x1,y0,y1,z0,z1,**style):
    return go.Mesh3d(x=[x0,x1,x1,x0,x0,x1,x1,x0],y=[y0,y0,y1,y1,y0,y0,y1,y1],z=[z0,z0,z0,z0,z1,z1,z1,z1],
        i=[0,0,4,4,0,0,1,1,2,2,3,3],j=[1,2,5,6,1,5,2,6,3,7,0,4],k=[2,3,6,7,5,4,6,5,7,6,4,7],**style)


def circular_mesh(cx,cy,radius,z0,z1,inner_radius=None,segments=64,**style):
    """A pipe has inner/outer walls and annular ends, never a disk over its bore."""
    vertices=[];faces=[];facecolors=[];n=segments
    rings=[(radius,z0),(radius,z1)]
    if inner_radius is not None:rings.extend([(inner_radius,z0),(inner_radius,z1)])
    for radius_at,z in rings:
        vertices.extend((cx+radius_at*math.cos(2*math.pi*k/n),cy+radius_at*math.sin(2*math.pi*k/n),z) for k in range(n))
    for k in range(n):
        j=(k+1)%n
        faces.extend([(k,j,n+j),(k,n+j,n+k)])
        if inner_radius is not None:
            faces.extend([(2*n+k,3*n+k,3*n+j),(2*n+k,3*n+j,2*n+j),
                          (n+k,n+j,3*n+j),(n+k,3*n+j,3*n+k),
                          (k,2*n+j,j),(k,2*n+k,2*n+j)])
            facecolors.extend(['#7e93a5']*2+['#3b5266']*2+['#b4c1cb']*4)
    if inner_radius is None:
        vertices.extend([(cx,cy,z0),(cx,cy,z1)])
        for k in range(n):
            j=(k+1)%n;faces.extend([(2*n,j,k),(2*n+1,n+k,n+j)])
    return go.Mesh3d(x=[v[0] for v in vertices],y=[v[1] for v in vertices],z=[v[2] for v in vertices],
        i=[v[0] for v in faces],j=[v[1] for v in faces],k=[v[2] for v in faces],facecolor=facecolors or None,**style)


def _ring(cx,cy,r,z):
    return [(cx+r*math.cos(2*math.pi*k/64),cy+r*math.sin(2*math.pi*k/64),z) for k in range(65)]


def _line(points,**style):
    return go.Scatter3d(x=[p[0] if p else None for p in points],y=[p[1] if p else None for p in points],z=[p[2] if p else None for p in points],mode='lines',**style)


def add_piles(fig,e):
    p=e.case['inputs'];s=pile_appearance(e.case);r=p['D_pile']/2;z0=-12;z1=p['Pile_embed']
    for i in range(int(p['N_pile'])):
        x=e.value('E_CL')+i*p['S_pile']*12;y=p['b']/2
        label=f'Pile {i+1} · {s["label"]}<br>{s["description"]}'
        common=dict(name=s['label'],legendgroup='piles',showlegend=i==0,meta=dict(part='piles',pile=i+1,shape=s['shape']),
                    hovertemplate=html.escape(label).replace('&lt;br&gt;','<br>')+'<extra></extra>')
        if s['shape']=='square':
            fig.add_trace(box_mesh(x-r,x+r,y-r,y+r,z0,z1,color='#8fa2b1',opacity=.85,**common))
        elif s['shape']=='round' or s['shape']=='pipe' and s['wall_in'] is not None:
            inner=r-s['wall_in'] if s['shape']=='pipe' else None
            fig.add_trace(circular_mesh(x,y,r,z0,z1,inner,color='#7e93a5',opacity=1,flatshading=False,**common))
            rims=_ring(x,y,r,z1)
            if inner is not None:rims+=[None]+_ring(x,y,inner,z1)
            fig.add_trace(_line(rims,name='Pile rim',legendgroup='piles',showlegend=False,meta=dict(part='piles'),
                                line=dict(color='#41596c',width=2),hoverinfo='skip'))
            if inner is not None and s['filled'] is True:
                fig.add_trace(circular_mesh(x,y,inner,z0,z1,color='#ccd3d8',opacity=1,name='Concrete infill',
                    legendgroup='piles',showlegend=False,meta=dict(part='piles'),hovertemplate='Concrete infill from pile section data<extra></extra>'))
        elif s['shape']=='pipe':
            # Unknown wall: show the known OD, without inventing an inside face.
            points=_ring(x,y,r,z0)+[None]+_ring(x,y,r,z1)
            for angle in range(0,360,90):
                xx=x+r*math.cos(math.radians(angle));yy=y+r*math.sin(math.radians(angle))
                points.extend([None,(xx,yy,z0),(xx,yy,z1)])
            fig.add_trace(_line(points,line=dict(color='#647a8d',width=3),**common))
        else:
            points=[]
            for z in (z0,z1):points.extend([None,(x-r,y-r,z),(x+r,y-r,z),(x+r,y+r,z),(x-r,y+r,z),(x-r,y-r,z)])
            for xx,yy in ((x-r,y-r),(x+r,y-r),(x+r,y+r),(x-r,y+r)):points.extend([None,(xx,yy,z0),(xx,yy,z1)])
            fig.add_trace(_line(points,line=dict(color='#a97b3a',width=2,dash='dot'),**common))
    return s


@numbered_figure('cap_3d')
def layout_3d(e):
    fig=go.Figure();p=e.case['inputs'];L=e.value('L_cap')
    continuous=bar_positions(e,'P');extra=hook_paths(e,bar_positions(e,'B'))
    family=lambda b:'side' if b['kind']=='Skin' else 'top' if b['kind'].startswith('Top') else 'bottom'
    counts=Counter(family(b) for b in continuous);counts['added']=len(extra);seen=set()
    names={'top':'Top steel','bottom':'Continuous bottom','side':'Side bars','added':'Added span bars + hooks'}
    for index,b in enumerate(continuous,1):
        group=family(b);title=f'{names[group]} · {counts[group]} bars'
        points=[(p['C_s'],b['x'],b['y']),(L-p['C_s'],b['x'],b['y'])]
        fig.add_trace(_line(points,name=title,legendgroup=group,showlegend=group not in seen,
            meta=dict(part=group,bar=b['bar'],bar_index=index),line=dict(color=COLORS[group],width=4),
            hovertemplate=f'{html.escape(b["kind"])} · #{b["bar"]}<br>Diameter {b["diameter"]:g} in<br>Across {b["x"]:.3f} in; elevation {b["y"]:.3f} in<br>Along cap %{{x:.3f}} in<extra></extra>'))
        seen.add(group)
    for index,t in enumerate(extra,1):
        b=t['bar'];points=[(x,b['x'],z) for x,z in t['points']]
        fig.add_trace(_line(points,name=f'{names["added"]} · {len(extra)} bars',legendgroup='added',showlegend=index==1,
            meta=dict(part='added',bar=b['bar'],span=t['span']),line=dict(color=COLORS['added'],width=5),
            hovertemplate=f'Span {t["span"]} · added #{b["bar"]}<br>Across {b["x"]:.3f} in<br>90° hooks; inside bend {t["inside_diameter"]:g} in; tail {t["tail"]:g} in<br>Along %{{x:.3f}} in; elevation %{{z:.3f}} in<extra></extra>'))
    runs={r['id']:r for r in e.case.get('transverse_detail',{}).get('runs',[])};seen=set()
    for bar in scheduled_bars(e.case):
        run=runs[bar['run']];shape=bar_shape(e,run);points=[(bar['station_in']+x,y,z) for x,y,z in shape['points_3d']]
        name='Closed hoop' if run['kind']=='hoop' else 'U-bar · open bottom'
        fig.add_trace(_line(points,name=f'{run["id"]}: {name} #{run["bar"]}',legendgroup=run['id'],showlegend=run['id'] not in seen,
            meta=dict(part='transverse',kind=run['kind'],bar=run['bar'],id=bar['id']),line=dict(color=COLORS[run['kind']],width=5),
            hovertemplate=f'{html.escape(bar["id"])} · #{bar["bar"]}<br>Leg station {bar["station_in"]/12:.3f} ft<br>Along %{{x:.2f}} in; across %{{y:.2f}} in; elevation %{{z:.2f}} in<extra></extra>'))
        seen.add(run['id'])
    # Match the explicitly illustrative between-pile sample in the 2D elevation.
    # This does not enter bars in the case or change quantities/checks.
    if not enabled(e.case):
        from .model import BAR_DIAMETER
        d=BAR_DIAMETER[p['Bar_v']];pitch=p['s_G']
        inset=p['D_pile']/2+e.value('Tol_pile')+p['C_pile']+d/2
        left=e.value('E_CL')+inset;right=e.value('E_CL')+p['S_pile']*12-inset
        count=min(5,math.floor((right-left)/pitch)+1)
        if count>=2:
            start=(left+right-(count-1)*pitch)/2
            shape=bar_shape(e,dict(kind='hoop',bar=int(p['Bar_v'])))
            for i in range(count):
                station=start+i*pitch
                fig.add_trace(_line([(station,y,z) for y,z in shape['points']],
                    name=f'Reference hoop sample · #{p["Bar_v"]:g} @ {pitch:g} in',legendgroup='reference-hoops',showlegend=i==0,
                    meta=dict(part='transverse',reference=True),line=dict(color=COLORS['hoop'],width=5,dash='dash'),
                    hovertemplate=f'Reference hoop · #{p["Bar_v"]:g} @ {pitch:g} in<br>Illustrative position only; actual stations not set<extra></extra>'))
    # An outline avoids transparent concrete faces obscuring the internal bars.
    outline=[]
    for z in (0,p['h']):outline.extend([None,(0,0,z),(L,0,z),(L,p['b'],z),(0,p['b'],z),(0,0,z)])
    for x,y in ((0,0),(L,0),(L,p['b']),(0,p['b'])):outline.extend([None,(x,y,0),(x,y,p['h'])])
    fig.add_trace(_line(outline,name='Concrete cap outline',line=dict(color='#a9bac7',width=2),legendgroup='cap',
                        meta=dict(part='cap'),showlegend=True,hoverinfo='skip'))
    appearance=add_piles(fig,e)
    buttons=visibility_buttons(fig)
    note='Click legend groups to hide/show steel. Drag to rotate; scroll to zoom.'
    if not enabled(e.case):note+='<br>Dashed hoops are a spacing sample only. Create / enable actual runs above for the full layout.'
    elif not scheduled_bars(e.case):note+='<br>No actual bars entered. Add a run in Actual hoops and pile U-bars.'
    if p['n_PU'] or p['n_BU']:note+='<br>Legacy U-leg inventory has no assigned positions and is not drawn.'
    pile_note=appearance['label']+' · '+appearance['description']
    # Fix true inch proportions when groups are hidden, including Piles only.
    extents=(L+8,p['b']+8,p['h']+18);scale=math.prod(extents)**(1/3)
    fig.update_layout(title=dict(text='3D CAGE · reinforcement and pile heads',font=dict(size=17),x=.015,y=.98,yanchor='top'),height=770,template='plotly_white',
        margin=dict(l=0,r=0,t=145,b=160,autoexpand=False),legend=dict(orientation='h',y=-.08,font=dict(size=10),groupclick='togglegroup'),
        hoverlabel=dict(namelength=-1),uirevision=hashlib.sha256(json.dumps({'inputs':p,'runs':e.case.get('transverse_detail'),'pile':appearance},sort_keys=True).encode()).hexdigest(),
        updatemenus=[dict(type='buttons',direction='right',active=0,x=0,y=1.18,xanchor='left',yanchor='top',buttons=buttons,font=dict(size=11))],
        annotations=[dict(x=0,y=1.08,xref='paper',yref='paper',text=html.escape(pile_note),showarrow=False,xanchor='left',font=dict(size=10)),
                     dict(x=0,y=-.01,xref='paper',yref='paper',text=note,showarrow=False,xanchor='left',font=dict(size=10))],
        scene=dict(xaxis=dict(title='Along cap (in)',range=[-4,L+4]),yaxis=dict(title='Across cap (in)',range=[-4,p['b']+4]),
                   zaxis=dict(title='Above underside (in)',range=[-14,p['h']+4]),aspectmode='manual',
                   aspectratio=dict(zip(('x','y','z'),(v/scale for v in extents))),
                   camera=dict(eye=dict(x=1.55,y=-2.2,z=1.4))))
    return fig
