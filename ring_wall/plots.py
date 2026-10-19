"""Cap-style live wall, cage, tributary and connection views."""
from math import ceil, cos, pi, sin
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .model import geometry, steel_layout
from .output import STYLE, check_details, esc, fmt, table

BLUE,GREEN,ORANGE,RED='#315d82','#258875','#c87b30','#b53333'
_scoped=re.sub(r'([^{}]+)\{([^{}]*)\}',lambda m:','.join('.ring-workbench' if s.strip()=='body' else '.ring-workbench '+s.strip() for s in m[1].split(','))+'{'+m[2]+'}',STYLE.split('@media print')[0])
CSS='<style>'+_scoped+'''.ring-workbench{position:relative;overscroll-behavior:contain;margin:0;padding:0;max-width:none}.ring-workbench .widget-label{white-space:normal!important;text-overflow:clip!important;text-align:left!important;height:auto!important}.ring-workbench .ring-section{padding:10px;background:#fff8e9;border:1px solid #d4dde5;margin:5px 0;border-radius:4px}.ring-workbench .ring-dock{position:sticky;top:8px;z-index:100;height:0!important;min-height:0!important;overflow:visible!important;pointer-events:none;justify-content:flex-end}.ring-workbench .ring-recalc{pointer-events:auto;border-radius:20px!important;font-weight:600;box-shadow:0 2px 8px #0003;margin-right:12px!important}.ring-workbench .ring-table{overflow:auto;max-height:560px}.ring-workbench .ring-panel-nav button{margin:2px!important;font-weight:600}</style>'''
def note(text,status=False):return '<div class="ring-'+('status' if status else 'note')+'">'+text+'</div>'
def working_table(headers,rows):return '<div class="ring-table">'+table(headers,rows)+'</div>'
def style(fig,title,height=480):
    fig.update_layout(template='plotly_white',title=dict(text=title,font=dict(size=17)),height=height,autosize=True,
        margin=dict(l=65,r=35,t=75,b=90),font=dict(family='Arial',size=12),legend=dict(orientation='h',y=-.15),uirevision=title)
    return fig
def rect(x0,y0,x1,y1):return [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
def circle(x,y,r):return [(x+r*cos(i*pi/48),y+r*sin(i*pi/48)) for i in range(97)]
def path(fig,name,paths,color,row=1,col=1,dash=None,width=2):
    xx=[];yy=[]
    for points in paths:xx.extend([v[0] for v in points]+[None]);yy.extend([v[1] for v in points]+[None])
    fig.add_trace(go.Scatter(x=xx,y=yy,name=name,mode='lines',line=dict(color=color,width=width,dash=dash),hovertemplate=name+'<br>%{x:.2f}, %{y:.2f} in<extra></extra>'),row=row,col=col)


def bar_positions(length,cover,db,spacing):
    low=cover+db/2;high=length-low;n=max(1,ceil((high-low)/spacing))
    return [low+(high-low)*i/n for i in range(n+1)]


def layout_figure(p):
    g=geometry(p);s=steel_layout(p);L,H,t=p['length_in'],p['height_in'],p['thickness_in']
    fig=make_subplots(rows=1,cols=2,column_widths=[.66,.34],horizontal_spacing=.11,subplot_titles=['Elevation · tributary boundaries','Plan · ring and face mats'])
    path(fig,'Wall',[rect(0,0,L,H)],BLUE)
    path(fig,'Pipe piles',[rect(x-p['pile_od_in']/2,-8,x+p['pile_od_in']/2,H+8) for x in g['pile_x']],'#9ba9b6')
    path(fig,'Annular rings',[rect(x-p['ring_od_in']/2,z-p['ring_t_in'],x+p['ring_od_in']/2,z) for x in g['pile_x'] for z in g['ring_z']],BLUE,width=3)
    path(fig,'Tributary boundaries',[[(x,0),(x,H)] for x in g['x_bounds'][1:-1]]+[[(0,z),(L,z)] for z in g['z_bounds'][1:-1]],'#7499ae',dash='dot')
    path(fig,'Horizontal grid',[[(p['cover_in'],z),(L-p['cover_in'],z)] for z in bar_positions(H,p['cover_in'],s['db'],s['spacing'])],ORANGE,width=1)
    path(fig,'Vertical grid',[[(x,p['cover_in']),(x,H-p['cover_in'])] for x in bar_positions(L,p['cover_in'],s['db'],s['spacing'])],GREEN,width=1)
    path(fig,'Wall plan',[rect(0,-t/2,L,t/2)],BLUE,col=2)
    path(fig,'Ring plan',[circle(x,0,p['ring_od_in']/2) for x in g['pile_x']],BLUE,col=2)
    path(fig,'Pile OD',[circle(x,0,p['pile_od_in']/2) for x in g['pile_x']],'#9ba9b6',col=2)
    path(fig,'Pile tolerance',[circle(x,0,p['ring_od_in']/2+p['placement_tolerance_in']) for x in g['pile_x']],RED,col=2,dash='dash')
    y=t/2-p['cover_in']-s['db']/2
    path(fig,'Face mats / end returns',[[(L-p['cover_in'],-y),(p['cover_in'],-y),(p['cover_in'],y),(L-p['cover_in'],y)],[(L-p['cover_in'],-y),(L-p['cover_in'],y)]],ORANGE,col=2)
    fig.update_xaxes(title_text='Along wall (in)');fig.update_yaxes(title_text='Elevation (in)',scaleanchor='x',row=1,col=1)
    fig.update_yaxes(title_text='Across wall (in)',scaleanchor='x2',row=1,col=2)
    fig.add_annotation(text=f'L = {L:g} in · H = {H:g} in · t = {t:g} in<br>Rings @ {p["ring_spacing_in"]:g} in · piles @ {p["pile_spacing_in"]:g} in',xref='paper',yref='paper',x=.5,y=1.16,showarrow=False)
    return style(fig,'Wall layout · current inputs',590)


def cage_figure(p):
    g=geometry(p);s=steel_layout(p);L,H,t=p['length_in'],p['height_in'],p['thickness_in'];c=p['cover_in'];db=s['db']
    fig=go.Figure()
    xx=[0,L,L,0,0,L,L,0];yy=[-t/2,-t/2,t/2,t/2]*2;zz=[0]*4+[H]*4
    fig.add_trace(go.Mesh3d(x=xx,y=yy,z=zz,i=[0,0,4,4,0,0,1,1,2,2,3,3],j=[1,2,5,6,1,5,2,6,3,7,0,4],k=[2,3,6,7,5,4,6,5,7,6,4,7],opacity=.08,color=BLUE,name='Concrete',hoverinfo='skip',showlegend=True))
    def lines(name,paths,color,width=3):
        xx=[];yy=[];zz=[]
        for pts in paths:
            xx.extend([a for a,b,c in pts]+[None]);yy.extend([b for a,b,c in pts]+[None]);zz.extend([c for a,b,c in pts]+[None])
        fig.add_trace(go.Scatter3d(x=xx,y=yy,z=zz,mode='lines',name=name,line=dict(color=color,width=width),hovertemplate=name+'<br>x %{x:.2f} · y %{y:.2f} · z %{z:.2f} in<extra></extra>'))
    lines('Pipe piles',[[(x+dx,y,z) for dx,y in circle(0,0,p['pile_od_in']/2)] for x in g['pile_x'] for z in (0,H)]+
          [[(x+p['pile_od_in']/2*cos(a),p['pile_od_in']/2*sin(a),z) for z in (0,H)] for x in g['pile_x'] for a in (0,pi/2,pi,3*pi/2)],'#899cab',3)
    # Merge the annular plate surfaces into one mesh, keeping trace count stable on edits.
    vx=[];vy=[];vz=[];ii=[];jj=[];kk=[]
    for x in g['pile_x']:
        for z in g['ring_z']:
            for k in range(48):
                base=len(vx);a=2*pi*k/48;b=2*pi*(k+1)/48
                for rr,aa in ((p['ring_id_in']/2,a),(p['ring_od_in']/2,a),(p['ring_od_in']/2,b),(p['ring_id_in']/2,b)):
                    vx.append(x+rr*cos(aa));vy.append(rr*sin(aa));vz.append(z)
                ii.extend([base,base]);jj.extend([base+1,base+2]);kk.extend([base+2,base+3])
    fig.add_trace(go.Mesh3d(x=vx,y=vy,z=vz,i=ii,j=jj,k=kk,color=BLUE,opacity=.85,name='Annular bearing plates',showlegend=True,hovertemplate='Annular plate<br>z %{z:.2f} in<extra></extra>'))
    ys=[-t/2+c+db/2,t/2-c-db/2];yvs=[-t/2+c+1.5*db,t/2-c-1.5*db]
    zs=bar_positions(H,c,db,s['spacing']);xs=bar_positions(L,c,db,s['spacing'])
    lines(f'Horizontal #{s["bar"]} grid',[[ (c,y,z),(L-c,y,z)] for y in ys for z in zs],ORANGE,3)
    lines(f'Vertical #{s["bar"]} grid',[[ (x,y,c),(x,y,H-c)] for y in yvs for x in xs],GREEN,3)
    lines('Matching end U returns',[[(c,ys[0],z),(c,ys[1],z)] for z in zs]+[[(L-c,ys[0],z),(L-c,ys[1],z)] for z in zs],ORANGE,4)
    end_ys=[y-t/2 for y in bar_positions(t,c,db,s['spacing'])]
    lines('End-face vertical bars',[[(x,y,c),(x,y,H-c)] for x in (c+db/2,L-c-db/2) for y in end_ys],GREEN,3)
    fig.update_layout(scene=dict(xaxis_title='Along wall (in)',yaxis_title='Across wall (in)',zaxis_title='Elevation (in)',aspectmode='data',camera=dict(eye=dict(x=1.65,y=-2.2,z=1.3))),
        updatemenus=[dict(type='buttons',direction='right',x=0,y=1.04,buttons=[dict(label=label,method='relayout',args=[{'scene.camera.eye':eye}]) for label,eye in [('Isometric',dict(x=1.65,y=-2.2,z=1.3)),('Front',dict(x=0,y=-2.8,z=.1)),('End',dict(x=2.8,y=0,z=.1)),('Plan',dict(x=0,y=0,z=2.8))]])])
    return style(fig,f'Wall cage · #{s["bar"]} at {s["spacing"]:g} in maximum · each face',660)


def connection_figure(r):
    p=r['case'];ring=max(r['rings'],key=lambda a:a['qmax']);rp=p['pile_od_in']/2;ri=p['ring_id_in']/2;ro=p['ring_od_in']/2;w=p['weld_leg_in'];t=p['ring_t_in']
    fig=make_subplots(rows=1,cols=2,horizontal_spacing=.13,subplot_titles=['Radial section at pipe face','Governing ring · elastic contact trial'])
    path(fig,'Pipe shell',[rect(rp-p['pile_t_effective_in'],-t-1.3,rp,1.3)],'#899cab',width=3)
    path(fig,'Ring plate',[rect(ri,-t,ro,0)],BLUE,width=4)
    path(fig,'Continuous top + bottom fillets',[[(rp,0),(rp,w),(rp+w,0),(rp,0)],[(rp,-t),(rp,-t-w),(rp+w,-t),(rp,-t)]],ORANGE,width=3)
    rb=max(ri,rp+w)
    for i in range(7):
        x=rb+(ro-rb)*i/6
        fig.add_annotation(x=x,y=.03,ax=x,ay=.7,xref='x',yref='y',axref='x',ayref='y',showarrow=True,arrowcolor=GREEN,arrowhead=2,text='')
    fig.add_annotation(x=(rb+ro)/2,y=.95,text='q max',showarrow=False,font=dict(color=GREEN))
    fig.add_annotation(x=rp,y=-t-1.05,text=f't = {t:g} in · weld leg = {w:g} in<br>radial root gap = {ri-rp:g} in',showarrow=False,xanchor='left')
    angles=list(range(361));q0=ring['R']/next(n['value'] for n in r['nodes'] if n['name']=='bearing_area');qm=ring['qmax']-q0
    fig.add_trace(go.Scatter(x=angles,y=[q0+qm*cos(a*pi/180) for a in angles],name='Outer-edge pressure',line=dict(color=BLUE),hovertemplate='%{x:.0f}°<br>%{y:.4f} ksi<extra></extra>'),row=1,col=2)
    fig.add_trace(go.Scatter(x=[0,360],y=[0,0],name='Compression boundary',line=dict(color=RED,dash='dash')),row=1,col=2)
    fig.update_xaxes(title_text='Radius from pile center (in)',row=1,col=1);fig.update_yaxes(title_text='Relative to plate top (in)',scaleanchor='x',row=1,col=1)
    fig.update_xaxes(title_text='Around ring (degrees)',row=1,col=2);fig.update_yaxes(title_text='Pressure (ksi)',row=1,col=2)
    return style(fig,f'Connection · R{ring["row"]}/P{ring["pile"]} · '+('full compression' if ring['contact_ok'] else 'FULL CONTACT FAILS — local strengths pending'),500)


def reaction_figure(r):
    p=r['case'];rings=r['rings'];z=[[a['R'] for a in rings if a['row']==k] for k in range(1,p['ring_count']+1)]
    fig=go.Figure(go.Heatmap(x=list(range(1,p['pile_count']+1)),y=list(range(1,p['ring_count']+1)),z=z,colorscale='Blues',colorbar=dict(title='kip'),hovertemplate='Pile %{x}<br>Ring row %{y}<br>%{z:.3f} kip<extra></extra>'))
    fig.update_xaxes(title_text='Pile number',dtick=1);fig.update_yaxes(title_text='Ring row (bottom to top)',dtick=1)
    return style(fig,'Factored wall self-weight assigned to each ring',430)


def spacing_figure(study):
    good=[a for a in study if 'error' not in a];fig=go.Figure()
    for key,label,color in [('max_ring_kip','Maximum ring load (kip)',BLUE),('max_weld_dc','Maximum trial weld D/C',ORANGE)]:
        fig.add_trace(go.Scatter(x=[a['spacing_in'] for a in good],y=[a[key] for a in good],name=label,mode='lines+markers',line=dict(color=color),yaxis='y2' if 'dc' in key else 'y'))
    fig.update_layout(yaxis2=dict(overlaying='y',side='right',title='Trial weld D/C'))
    fig.update_xaxes(title_text='Vertical ring spacing (in)');fig.update_yaxes(title_text='Maximum ring load (kip)')
    return style(fig,'Ring spacing study · contact and fit gates remain controlling',420)


def summary(r):
    items=[('Service concrete weight',fmt(r['totals']['service_weight'])+' kip'),('Factored concrete weight',fmt(r['totals']['factored_weight'])+' kip'),('Maximum ring load',fmt(max(a['R'] for a in r['rings']))+' kip'),('Face reinforcement',f'#{r["grid"]["bar"]} @ {r["grid"]["spacing"]:g} in')]
    return '<div class="ring-cards">'+''.join('<div class="ring-card">'+a+'<b>'+b+'</b></div>' for a,b in items)+'</div>'


def ring_table(r,row=0):
    return working_table(['Row / pile','Trib. width × height (in)','Concrete (ft³)','Service / factored (kip)','e design (in)','q min / max (ksi)','Plate t required (in)','Weld leg required (in)','Contact'],[
        [f'{a["row"]} / {a["pile"]}',fmt(a['width'])+' × '+fmt(a['height']),fmt(a['volume_ft3']),fmt(a['service'])+' / '+fmt(a['R']),fmt(a['e_design']),fmt(a['qmin'])+' / '+fmt(a['qmax']),fmt(a['t_req']),fmt(a['weld_req']),
         'OK' if a['contact_ok'] else '<b class="FAIL">FAIL · strength values trial only</b>'] for a in r['rings'] if not row or row==a['row']])


def steel_table(r):
    s=r['grid'];p=r['case']
    return note(f'Selected: #{s["bar"]} at {s["spacing"]:g} in maximum, each way / each broad face, with matching end returns. Review steel and detailing checks before adoption. '
        'Horizontal bars are outside vertical bars. Drawings show centerlines; U bends and lap routing require final detailing.')+working_table(['Item','Required / limit','Provided'],[
        ['Minimum area per direction / face',fmt(s['required'])+' in²/ft',fmt(s['provided'])+' in²/ft'],
        ['Grid center pitch',fmt(s['spacing_limit'])+' in',fmt(s['spacing'])+' in'],
        ['Horizontal Class B lap / U leg',fmt(s['development_h']['lap_b'])+' in',fmt(p['u_leg_in'])+' in'],
        ['Vertical Class B lap',fmt(s['development_v']['lap_b'])+' in',fmt(p['vertical_lap_in'])+' in']])


def checks_table(r,view='all'):
    rows=list(r['checks'])
    if view=='fail':rows=[c for c in rows if c['status']=='FAIL']
    elif view=='pending':rows=[c for c in rows if c['status']=='PENDING']
    elif view=='fail_first':rows.sort(key=lambda c:(c['status']!='FAIL',c['status']!='PENDING'))
    elif view=='dc':rows.sort(key=lambda c:-(c['ratio'] if c['ratio'] is not None else -1))
    text=working_table(['Check','Demand','Capacity','D/C','Status','Equation and basis'],[[esc(c['id'])+'<br>'+esc(c['title']),fmt(c['demand'])+' '+esc(c['unit']),fmt(c['capacity']),fmt(c['ratio']),'<b class="'+c['status']+'">'+c['status']+'</b>',check_details(r,c)] for c in rows])
    if view!='fail':text+=working_table(['Open item','Scope / prerequisite'],[[esc(k),esc(v)] for k,v in r['pending']])
    return text


def spacing_table(study):
    return working_table(['Pitch (in)','Rows','Max ring (kip)','Max trial plate t (in)','Max trial weld leg (in)','Failed contact rings','Status'],[
        [fmt(a['spacing_in']),a.get('ring_count','—'),fmt(a.get('max_ring_kip')),fmt(a.get('max_t_in')),fmt(a.get('max_weld_in')),a.get('contact_failures','—'),esc(a.get('status',a.get('error','')))] for a in study])
