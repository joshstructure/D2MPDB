"""Live figures and working tables; all design results come from model.analyze."""
from math import cos, pi, sin, sqrt

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .model import BAR
from .cone import geometry as cone_geometry
from .report import esc, fmt, table

BLUE, GREEN, ORANGE, PURPLE, RED = '#315d82', '#258875', '#bf6c2d', '#77539c', '#b53333'
CSS = '''<style>
.ring-workbench{font-family:Arial,sans-serif;color:#213649;position:relative;overscroll-behavior:contain}
.ring-workbench .widget-label{white-space:normal!important;text-overflow:clip!important;line-height:1.25!important;height:auto!important;text-align:left!important}
.ring-workbench .widget-tab{min-width:0;flex-shrink:0}
.ring-workbench .widget-tab-contents{padding:12px;overflow-x:auto}
.ring-workbench .widget-tab-bar{overflow-x:auto;flex-wrap:nowrap}
.ring-workbench .ring-panel-nav button{font-weight:600;border-radius:3px;margin:2px!important}
.ring-workbench .ring-dock{position:sticky;top:8px;z-index:100;height:0!important;min-height:0!important;overflow:visible!important;pointer-events:none;justify-content:flex-end}
.ring-workbench .ring-recalc{pointer-events:auto;border-radius:20px!important;font-weight:600;box-shadow:0 2px 8px #0003;margin-right:12px!important}
.ring-workbench .ring-section{border:1px solid #d4dde5;border-radius:4px;padding:8px;margin:4px 0;background:#fff8e9}
.ring-workbench .ring-table{width:100%;overflow:auto;max-height:510px}
.ring-workbench table{border-collapse:collapse;width:100%;font-size:12px;margin:8px 0;background:white}
.ring-workbench th,.ring-workbench td{border:1px solid #c9d3dc;padding:6px 8px;text-align:left;vertical-align:top}
.ring-workbench th{background:#e9eef3;position:sticky;top:0;z-index:1}
.ring-workbench .ring-note{padding:9px 12px;background:#f1f5fa;border-left:3px solid #7189a6;margin:8px 0;line-height:1.45}
.ring-workbench .ring-status{padding:9px 12px;background:#fff4d9;border-left:4px solid #a56d15;margin:6px 0;line-height:1.45}
.ring-workbench .ring-cards{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
.ring-workbench .ring-card{flex:1;min-width:150px;padding:10px;background:#eff7f1;border:1px solid #a8c4af}
.ring-workbench .ring-card b{display:block;font-size:20px;margin-top:5px}
.ring-workbench .PASS{color:#17633b;font-weight:bold}.ring-workbench .FAIL{color:#b53333;font-weight:bold}.ring-workbench .PENDING{color:#98600d;font-weight:bold}
.ring-workbench details{margin:4px 0}.ring-workbench summary{cursor:pointer;color:#245c85}
.ring-workbench .box{border:1px solid #c9d3dc;margin:8px 0}.ring-workbench .hd{padding:7px 10px;font-weight:bold;background:#dce7f3}
.ring-workbench .bd{padding:9px 11px;background:#f1f5fa;line-height:1.45}.ring-workbench .eq{padding:8px 0;line-height:1.5}
.ring-workbench .subtle,.ring-workbench .ref{color:#586777;font-size:12px}
</style>'''


def note(text, status=False):
    return f'<div class="ring-{"status" if status else "note"}">{text}</div>'


def working_table(headers, rows):
    return '<div class="ring-table">' + table(headers, rows) + '</div>'


def style(fig, title, height=390):
    fig.update_layout(template='plotly_white', title=dict(text=title, font=dict(size=16)),
                      height=height, autosize=True, margin=dict(l=65, r=25, t=65, b=70),
                      font=dict(family='Arial', size=12),
                      legend=dict(orientation='h', y=-.20), uirevision=title)
    return fig


def layout_figure(p):
    """Preview the entered geometry without evaluating strength or reactions."""
    length, height, width = p['length_in'], p['height_in'], p['thickness_in']
    end = (length - (p['pile_count']-1)*p['pile_spacing_in'])/2
    piles = [end+i*p['pile_spacing_in'] for i in range(p['pile_count'])]
    rings = [p['first_ring_in']+i*p['ring_spacing_in'] for i in range(p['ring_count'])]
    cone=cone_geometry(p);rise=cone['face_rise_in'] if cone['enabled'] else 0.
    fig = make_subplots(rows=1, cols=2, column_widths=[.63,.37], horizontal_spacing=.12,
                        subplot_titles=['Wall elevation', 'Plan at the end pile'])

    def path(name, paths, color, col=1, dash=None, fill=None):
        x, y = [], []
        for points in paths:
            x.extend([a for a,b in points]+[None]); y.extend([b for a,b in points]+[None])
        fig.add_trace(go.Scatter(x=x,y=y,name=name,mode='lines',line=dict(color=color,width=2,dash=dash),
                                fill=fill,hovertemplate=name+'<br>x %{x:.2f} in<br>z / y %{y:.2f} in<extra></extra>'),row=1,col=col)

    def rect(x0,y0,x1,y1): return [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
    path('Wall', [rect(0,0,length,height)], BLUE)
    path('Hollow piles', [rect(x-p['pile_od_in']/2,0,x+p['pile_od_in']/2,height) for x in piles], '#8796a5')
    path('Rings', [rect(x-p['ring_od_in']/2,z-p['ring_t_in'],x+p['ring_od_in']/2,z) for x in piles for z in rings], BLUE)
    arches, ties = [], []
    for z in rings:
        for x in piles[:-1]:
            span=p['pile_spacing_in']; base=z+rise+p['tie_offset_in']
            arches.append([(x+span*i/p['arch_panels'],base+4*p['arch_rise_in']*(i/p['arch_panels'])*(1-i/p['arch_panels'])) for i in range(p['arch_panels']+1)])
            ties.append([(x,base),(x+span,base)])
    path('Compression path', arches, GREEN)
    path('Ring-to-node links (projection)', [[(x,z),(x,z+rise+p['tie_offset_in'])] for x in piles for z in rings], GREEN)
    path('ADDED ties', ties, ORANGE)
    path('Band limits', [[(0,(a+b)/2),(length,(a+b)/2)] for a,b in zip(rings[:-1],rings[1:])], '#aebac6',dash='dot')
    xmax=min(length,end+p['ring_od_in']/2+p['placement_tolerance_in']+8)
    path('Wall plan', [rect(0,-width/2,xmax,width/2)], BLUE,col=2)
    for name,radius,color,dash in [('Pipe OD',p['pile_od_in']/2,'#8796a5',None),
                                  ('Ring OD',p['ring_od_in']/2,BLUE,None),
                                  ('Ring + tolerance',p['ring_od_in']/2+p['placement_tolerance_in'],RED,'dash')]:
        path(name,[[(end+radius*cos(i*pi/60),radius*sin(i*pi/60)) for i in range(121)]],color,col=2,dash=dash)
    db=BAR[p['grid_bar']][0]; y=width/2-p['cover_in']-db/2; x=p['cover_in']+db/2
    path('Face grid / end U', [[(xmax,-y),(x,-y),(x,y),(xmax,y)]], ORANGE,col=2)
    fig.update_xaxes(title_text='Along wall (in)',row=1,col=1)
    fig.update_yaxes(title_text='Above wall bottom (in)',scaleanchor='x',scaleratio=1,row=1,col=1)
    fig.update_xaxes(title_text='Along wall (in)',row=1,col=2)
    fig.update_yaxes(title_text='Across wall (in)',scaleanchor='x2',scaleratio=1,row=1,col=2)
    return style(fig,'Live geometry · current inputs',480)


def cone_figure(p):
    """Outer pile / lowest ring, with the envelope clipped at the wall faces."""
    cone=cone_geometry(p);ro=p['ring_od_in']/2;ri=p['ring_id_in']/2;rp=p['pile_od_in']/2
    half=p['thickness_in']/2;z0=p['first_ring_in'];h=cone['face_rise_in'];s=cone['slope_hv']
    xp=(p['length_in']-(p['pile_count']-1)*p['pile_spacing_in'])/2
    top=min(p['height_in'],z0+h+p['tie_offset_in']+4)
    xmin=0.;xmax=min(p['length_in'],xp+half+5)
    angles=[i*2*pi/72 for i in range(73)]
    fig=go.Figure()
    radii=[ro+s*(top-z0)*i/20 for i in range(21)]
    xx=[];yy=[];zz=[]
    for radius in radii:
        xs=[];ys=[];zs=[]
        for angle in angles:
            x=xp+radius*cos(angle);y=radius*sin(angle)
            inside=xmin<=x<=xmax and abs(y)<=half
            xs.append(x if inside else None);ys.append(y if inside else None)
            zs.append(z0+(radius-ro)/s if inside else None)
        xx.append(xs);yy.append(ys);zz.append(zs)
    fig.add_trace(go.Surface(x=xx,y=yy,z=zz,name='Breakout envelope',colorscale=[[0,GREEN],[1,GREEN]],
                             opacity=.35,showscale=False,hovertemplate='Envelope<br>x %{x:.2f} in<br>y %{y:.2f} in<br>z %{z:.2f} in<extra></extra>'))
    fig.add_trace(go.Surface(x=[[xp+r*cos(a) for a in angles] for r in (ri,ro)],
                             y=[[r*sin(a) for a in angles] for r in (ri,ro)],z=[[z0]*len(angles)]*2,
                             colorscale=[[0,BLUE],[1,BLUE]],showscale=False,name='Ring top',hoverinfo='name'))
    fig.add_trace(go.Surface(x=[[xp+rp*cos(a) for a in angles]]*2,y=[[rp*sin(a) for a in angles]]*2,
                             z=[[max(0,z0-3)]*len(angles),[top]*len(angles)],colorscale=[[0,'#8796a5'],[1,'#8796a5']],
                             opacity=.3,showscale=False,name='Hollow pipe boundary',hoverinfo='name'))
    for side in (-1,1):
        fig.add_trace(go.Surface(x=[[xmin,xmax],[xmin,xmax]],y=[[side*half]*2]*2,z=[[max(0,z0-3)]*2,[top]*2],
                                 colorscale=[[0,'#b3c5d4'],[1,'#b3c5d4']],opacity=.12,showscale=False,name='Broad wall face',hoverinfo='name'))
    contact=z0+h;node=contact+p['tie_offset_in']
    fig.add_trace(go.Scatter3d(x=[xp,xp],y=[-half,half],z=[contact]*2,mode='markers',marker=dict(size=5,color=GREEN),
                               name='First face contact',hovertemplate='First face contact<br>z %{z:.3f} in<extra></extra>'))
    fig.add_trace(go.Scatter3d(x=[xp,xp,None,xp,xp],y=[-ro,-half,None,ro,half],z=[z0,node,None,z0,node],
                               mode='lines',line=dict(color=GREEN,width=7),name='Trial transfer struts'))
    fig.add_trace(go.Scatter3d(x=[xp,xp],y=[-half,half],z=[node,node],mode='lines',
                               line=dict(color=ORANGE,width=5,dash='dash'),name='Transverse tie resultant',
                               hovertemplate='Tie force resultant only.<br>Detail routing around hollow pipe.<extra></extra>'))
    fig.add_trace(go.Scatter3d(x=[xp,xp],y=[-half,half],z=[node,node],mode='markers',marker=dict(size=5,color=ORANGE,symbol='diamond'),
                               name='Trial face-node references',hovertemplate='Trial node reference<br>z %{z:.3f} in<br>Finite interior node/cover unresolved<extra></extra>'))
    cx=[];cy=[];cz=[]
    for side in (-1,1):
        for branch in (-1,1):
            for i in range(41):
                z=contact+max(0,top-contact)*i/40;radius=ro+s*(z-z0)
                x=xp+branch*sqrt(max(0,radius**2-half**2))
                cx.append(x if xmin<=x<=xmax else None);cy.append(side*half);cz.append(z)
            cx.append(None);cy.append(None);cz.append(None)
    fig.add_trace(go.Scatter3d(x=cx,y=cy,z=cz,mode='lines',line=dict(color=RED,width=4),name='Envelope / face intersection'))
    fig.update_layout(scene=dict(xaxis_title='Along wall (in)',yaxis_title='Across wall (in)',zaxis_title='Above bottom (in)',
                                 aspectmode='data',camera=dict(eye=dict(x=1.5,y=-1.8,z=1.2))))
    return style(fig,'Ring 1 / pile 1 · breakout envelope and trial transfer',500)


def reaction_figure(r):
    labels=[f'P{j+1}' for j in range(r['case']['pile_count'])]
    matrix=[[a['R'] for a in r['rings'] if a['row']==row['row']] for row in r['rows']]
    fig=go.Figure(go.Heatmap(x=labels,y=[f'R{a["row"]} · {a["z"]:g} in' for a in r['rows']],
                             z=matrix,texttemplate='%{z:.3f}',colorscale='Blues',
                             colorbar=dict(title='kip'),hovertemplate='%{y}<br>%{x}<br>Reaction %{z:.4f} kip<extra></extra>'))
    fig.update_xaxes(title='Pile');fig.update_yaxes(title='Ring row / elevation')
    return style(fig,'Factored ring reactions · assumed tributary allocation')


def force_figure(r):
    x=[f'R{a["row"]}' for a in r['rows']]
    fig=go.Figure()
    for label,key,color in [('Horizontal tie','tie',ORANGE),('Collector','hanger',PURPLE),('Maximum strut','max_C',GREEN)]:
        fig.add_trace(go.Bar(x=x,y=[a['arch'][key] for a in r['rows']],name=label,marker_color=color,
                             hovertemplate='%{x}<br>'+label+' %{y:.3f} kip<extra></extra>'))
    for label,key,color in [('Tie steel capacity','tie_capacity',ORANGE),('Collector steel capacity','hanger_capacity',PURPLE)]:
        fig.add_trace(go.Scatter(x=x,y=[r['steel'][key]]*len(x),name=label,mode='lines',line=dict(color=color,dash='dash')))
    fig.update_layout(barmode='group');fig.update_yaxes(title='Force (kip)')
    return style(fig,'Bay struts, dedicated ties and collectors')


def spacing_figure(study):
    items=[a for a in study if 'error' not in a]
    fig=go.Figure()
    for name,key,color in [('Maximum ring reaction','max_ring_kip',BLUE),('Maximum bay tie','max_tie_kip',ORANGE)]:
        fig.add_trace(go.Scatter(x=[a['spacing_in']/12 for a in items],y=[a[key] for a in items],
                                mode='lines+markers',name=name,line=dict(color=color),
                                hovertemplate='%{x:g} ft<br>%{y:.3f} kip<extra>'+name+'</extra>'))
    fig.update_xaxes(title='Vertical ring spacing (ft)');fig.update_yaxes(title='Factored force (kip)')
    return style(fig,'Ring-spacing comparison · same section and arch rise')


def summary(r):
    cards=[('Service gravity',f'{r["totals"]["service_weight"]:.3f} kip'),
           ('Factored gravity',f'{r["totals"]["factored_weight"]:.3f} kip'),
           ('Grid · each way, each face',f'#{r["grid"]["bar"]} @ {r["grid"]["spacing"]:g} in'),
           ('Failed / open checks',f'{sum(c["status"]=="FAIL" for c in r["checks"])} / {len(r["pending"])}')]
    return '<div class="ring-cards">'+''.join(f'<div class="ring-card">{a}<b>{b}</b></div>' for a,b in cards)+'</div>'


def ring_table(r, row=0):
    return working_table(['Row / pile','Elevation (in)','Ru (kip)','Mu (kip-in)','qmax (ksi)','qmin (ksi)','Plate treq (in)','Root m (kip-in/in)','Weld v (kip/in)'],[
        [f'{a["row"]} / {a["pile"]}',fmt(a['z']),fmt(a['R']),fmt(a['M']),fmt(a['qmax']),fmt(a['qmin']),fmt(a['t_req']),fmt(a['m_per_in']),fmt(a['weld_vertical_per_in'])]
        for a in r['rings'] if not row or a['row']==row])


def force_table(r):
    return working_table(['Row','Band bottom / top (in)','Weight (kip)','Tie (kip)','Strut max (kip)','Collector (kip)','Angle min (°)','Bay reaction (kip)'],[
        [a['row'],f'{a["lo"]:.3f} / {a["hi"]:.3f}',fmt(a['weight']),fmt(a['arch']['tie']),fmt(a['arch']['max_C']),fmt(a['arch']['hanger']),fmt(a['arch']['minimum_angle']),fmt(a['arch']['reaction'])] for a in r['rows']])


def steel_table(r):
    g,p=r['grid'],r['case']
    return working_table(['Reinforcement / check','Required / limit','Provided / trial'],[
        ['Uniform face grid, each way',f'{g["required"]:.3f} in²/ft per face',f'#{g["bar"]} @ {g["spacing"]:g} in · {g["provided"]:.3f} in²/ft per face'],
        ['Grid center spacing',f'≤ {g["spacing_limit"]:.3f} in',f'{g["spacing"]:g} in'],
        ['Both wall-end U-bars','Match horizontal grid',f'#{g["bar"]} @ {g["spacing"]:g} in vertically'],
        ['U-bar straight legs',f'Class B lap allowance {g["development_h"]["lap_b"]:.3f} in',f'{p["u_leg_in"]:g} in'],
        ['Narrow end-face vertical bars','Match vertical grid maximum pitch',f'{g["end_vertical_count"]} × #{g["bar"]} per end · {g["end_vertical_pitch"]:.3f} in pitch'],
        ['ADDED horizontal ties',f'{max(a["arch"]["tie"] for a in r["rows"]):.3f} kip max / bay',f'{p["primary_bars_per_face"]} × #{p["primary_bar"]} per face · {r["steel"]["tie_capacity"]:.3f} kip'],
        ['ADDED vertical collectors',f'{max(a["arch"]["hanger"] for a in r["rows"]):.3f} kip max / joint',f'{p["hanger_bars_per_face"]} × #{p["primary_bar"]} per face · {r["steel"]["hanger_capacity"]:.3f} kip'],
    ])+note('Grid steel is not counted again as primary tie steel. Primary-tie/collector anchorage and complete connection design remain open.')


def checks_table(r, view='all'):
    checks=list(r['checks'])
    if view=='fail': checks=[c for c in checks if c['status']=='FAIL']
    elif view=='dc': checks.sort(key=lambda c:c['ratio'] if c['ratio'] is not None else float('inf'),reverse=True)
    elif view=='fail_first': checks.sort(key=lambda c:c['status']!='FAIL')
    rows=[]
    if view!='pending':
        for c in checks:
            details=(f'<details><summary>Equation &amp; values</summary><p>{esc(c["ref"])}</p>'
                     f'<p>D/C = {c["demand"]:.6g} / {c["capacity"]:.6g} = {fmt(c["ratio"],4)}.</p>'
                     f'<p>{esc(c["note"])} Nonpositive available dimensions fail the check.</p></details>')
            rows.append([esc(c['id']),esc(c['scope']),esc(c['title'])+details,
                         f'{fmt(c["demand"],4)} {esc(c["unit"])}',f'{fmt(c["capacity"],4)} {esc(c["unit"])}',fmt(c['ratio']),f'<span class="{c["status"]}">{c["status"]}</span>'])
    if view!='fail':
        rows.extend([[esc(a),'OPEN',esc(b),'—','—','—','<span class="PENDING">PENDING</span>'] for a,b in r['pending']])
    return working_table(['ID','Scope','Check / basis','Demand','Resistance / limit','D/C','Result'],rows) if rows else note('No checks match this view. Open design items remain in Pending only.')


def spacing_table(study):
    rows=[]
    for a in study:
        if 'error' in a: rows.append([f'{a["spacing_in"]/12:g} ft',esc(a['error']),'—','—','—','—'])
        else: rows.append([f'{a["spacing_in"]/12:g} ft',a['ring_count'],f'#{a["grid_bar"]} @ {a["grid_spacing_in"]:g} in',fmt(a['max_ring_kip']),fmt(a['max_tie_kip']),esc(', '.join(a['failed_checks']) or 'No equation failures; open checks remain')])
    return working_table(['Spacing','Rows','Grid / face','Max ring (kip)','Max tie (kip)','Failed checks'],rows)
