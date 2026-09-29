"""Geometry-driven drawings and plots; no invented load distribution."""
import math
import html
from collections import defaultdict
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .model import bar_positions,BAR_DIAMETER
from .optimizer import candidate_dc,candidate_governing,DC_SCOPES

BLUE='#1f5b91';TEAL='#167b75';AMBER='#d88822';RED='#bb3e39';INK='#213649';GREY='#b8c7d1'

def theme(fig,title,height=460):
    fig.update_layout(title=dict(text=title,font=dict(size=17)),template='plotly_white',height=height,
        font=dict(family='Arial',size=12,color=INK),margin=dict(l=50,r=25,t=65,b=45),
        paper_bgcolor='#ffffff',plot_bgcolor='#ffffff',legend=dict(orientation='h',y=-.12),hoverlabel=dict(bgcolor='white'))
    return fig

def section_figure(e,region='B'):
    p=e.case['inputs'];b=p['b'];h=p['h'];fig=go.Figure();dv=BAR_DIAMETER[p['Bar_v']]
    fig.add_shape(type='rect',x0=0,y0=0,x1=b,y1=h,line=dict(color=INK,width=2),fillcolor='#f2f5f7',layer='below')
    fig.add_shape(type='rect',x0=p['C_s']+dv/2,y0=p['C_b']+dv/2,x1=b-p['C_s']-dv/2,y1=h-p['C_t']-dv/2,line=dict(color=AMBER,width=3))
    groups=defaultdict(list)
    for bar in bar_positions(e,region):
        groups[bar['kind']].append(bar);r=bar['diameter']/2
        color=TEAL if bar['kind']=='Skin' else BLUE
        fig.add_shape(type='circle',x0=bar['x']-r,y0=bar['y']-r,x1=bar['x']+r,y1=bar['y']+r,line=dict(color=color,width=1),fillcolor=color)
    for label,bars in groups.items():
        color=TEAL if label=='Skin' else BLUE
        fig.add_trace(go.Scatter(x=[v['x'] for v in bars],y=[v['y'] for v in bars],mode='markers',name=f'{label}: {len(bars)} bars',
            marker=dict(size=8,color=color,opacity=.15),text=[f"#{v['bar']} · diameter {v['diameter']:g} in" for v in bars],hovertemplate='%{text}<br>x=%{x:.2f}, y=%{y:.2f} in<extra>%{fullData.name}</extra>'))
    if p['n_'+region+'U']:
        fig.add_annotation(x=b/2,y=-4,text=f"U-leg inventory: {p['n_'+region+'U']:g} #{p['Bar_U']:g}; positions unresolved",showarrow=False,font=dict(color=RED,size=11))
    fig.update_xaxes(title='Width (in)',range=[-3,b+3],constrain='domain',zeroline=False)
    fig.update_yaxes(title='Depth from bottom (in)',range=[-6,h+3],scaleanchor='x',scaleratio=1,zeroline=False)
    title=('Pile / positive region' if region=='P' else 'Bearing region')+f' · {b:g} × {h:g} in'
    theme(fig,title,470);fig.update_layout(legend=dict(font=dict(size=10),orientation='h',y=-.2))
    return fig

def elevation_figure(e):
    p=e.case['inputs'];L=e.value('L_cap')/12;h=p['h']/12;D=p['D_pile']/12
    fig=go.Figure();fig.add_shape(type='rect',x0=0,x1=L,y0=0,y1=h,fillcolor='#e7eef4',line=dict(color=BLUE,width=2))
    centers=[e.value('E_CL')/12+j*p['S_pile'] for j in range(int(p['N_pile']))]
    for j,x in enumerate(centers,1):
        fig.add_shape(type='rect',x0=x-D/2,x1=x+D/2,y0=-1.5,y1=.1,fillcolor='#b9cbd7',line=dict(color=BLUE))
        fig.add_annotation(x=x,y=-.8,text=f'P{j}',showarrow=False)
    fig.add_trace(go.Scatter(x=centers,y=[0]*len(centers),mode='markers',name='Pile center',marker=dict(color=BLUE),hovertemplate='Center %{x:.3f} ft<extra></extra>'))
    fig.add_annotation(x=L/2,y=h+.4,text=f"Length {L:.3f} ft · {p['N_pile']:g} piles @ {p['S_pile']:g} ft · nominal end extension {e.value('E_end'):g} in",showarrow=False)
    fig.update_xaxes(title='Along cap (ft)',range=[-1,L+1],zeroline=False)
    fig.update_yaxes(title='Elevation (ft)',range=[-2,h+1],scaleanchor='x',scaleratio=1,zeroline=False)
    theme(fig,'Pile layout · pile lengths symbolic',330);fig.update_layout(showlegend=False)
    return fig

def hoop_figure(e):
    fig=go.Figure()
    for z,y,name in [('G',1,'Global'),('L',0,'Low interval')]:
        s=e.case['inputs']['s_'+z];xs=[i*s for i in range(math.floor(48/s)+1)]
        fig.add_shape(type='line',x0=0,x1=48,y0=y,y1=y,line=dict(color=GREY,width=10))
        fig.add_trace(go.Scatter(x=[v for x in xs for v in (x,x,None)],y=[v for _ in xs for v in (y-.22,y+.22,None)],mode='lines',name=f'{name}: #{e.case["inputs"]["Bar_v"]:g} @ {s:g} in',line=dict(color=AMBER,width=3),hoverinfo='name'))
    fig.update_xaxes(title='Symbolic 48 in strip; first-hoop location is not a detail',range=[-1,49]);fig.update_yaxes(tickvals=[0,1],ticktext=['Low','Global'],range=[-.5,1.5],showgrid=False)
    return theme(fig,'Hoop spacing responds to your inputs',260)

def results_figure(e):
    fig=make_subplots(rows=2,cols=2,subplot_titles=('Factored moment / resistance (kip-ft)','Service I steel stress (ksi)','Shear demand / resistance (kip)','Combined shear + torsion area (in²)'),vertical_spacing=.22,horizontal_spacing=.13)
    labels=['N · top','P · pile','B · bearing']
    for prefix,name,color in [('Mu_','Demand',BLUE),('Mr_','Resistance',TEAL)]:fig.add_trace(go.Bar(x=labels,y=[e.value(prefix+z,'kip*ft') for z in 'NPB'],name='Moment '+name,marker_color=color),row=1,col=1)
    fig.add_trace(go.Bar(x=labels,y=[e.value('fs_I_'+z,'ksi') for z in 'NPB'],name='Service I stress',marker_color=BLUE),row=1,col=2)
    fig.add_hline(y=e.value('fs_I_limit','ksi'),line_color=AMBER,line_dash='dash',annotation_text='Stress limit',row=1,col=2)
    for prefix,name,color in [('Vu_','Shear demand',BLUE),('Vr_','Shear resistance',TEAL)]:fig.add_trace(go.Bar(x=['Global','Low'],y=[e.value(prefix+z,'kip') for z in 'GL'],name=name,marker_color=color),row=2,col=1)
    fig.add_trace(go.Bar(x=['Global','Low'],y=[e.value('Acomb_'+z,'in^2') for z in 'GL'],name='Combined area required',marker_color=BLUE),row=2,col=2)
    fig.add_hline(y=e.value('Av','in^2'),line_color=AMBER,line_dash='dash',annotation_text='Area provided',row=2,col=2)
    theme(fig,'Current cage · capacity and stress response',620);fig.update_layout(barmode='group',legend=dict(font=dict(size=10),orientation='h',y=-.16))
    return fig

def ratios_figure(e):
    checks=[c for c in e.checks if isinstance(c.ratio,(float,int))]
    fig=go.Figure(go.Bar(x=[c.ratio for c in checks],y=[c.label for c in checks],orientation='h',
        marker_color=[RED if c.ratio>1 or 'FAIL' in c.status else TEAL for c in checks],
        text=[f'{c.ratio:.3f}' for c in checks],textposition='outside',customdata=[c.basis for c in checks],hovertemplate='%{y}<br>D/C %{x:.4f}<br>%{customdata}<extra></extra>'))
    fig.add_vline(x=1,line_color=AMBER,line_dash='dash',annotation_text='D/C = 1')
    fig.update_yaxes(autorange='reversed');fig.update_xaxes(title='Demand / capacity (minimum criteria use required / provided)',range=[0,max(1.25,e.max_dc*1.15)])
    theme(fig,'All available numerical comparisons',max(700,len(checks)*28));fig.update_layout(margin=dict(l=240,r=55,t=65,b=55))
    return fig

def optional_service_figure(e):
    fig=make_subplots(rows=1,cols=2,subplot_titles=('Service III outer-bar stress (ksi)','Factored fatigue stress range (ksi)'))
    labels=['N','P','B']
    if e.case['inputs']['Ready_III']:
        fig.add_trace(go.Bar(x=labels,y=[e.value('fo_III_'+z,'ksi') for z in labels],name='Outer-bar stress',marker_color=BLUE),row=1,col=1)
        fig.add_hline(y=24,line_dash='dash',line_color=AMBER,annotation_text='24 ksi limit',row=1,col=1)
    else:fig.add_annotation(x=.22,y=.5,xref='paper',yref='paper',text='PENDING<br>Supply Service III loads',showarrow=False,font=dict(color=AMBER,size=16))
    if e.case['inputs']['Ready_fatigue']:
        for prefix,title,color in [('Df_','Stress range',BLUE),('FTH_','Fatigue threshold',TEAL)]:
            fig.add_trace(go.Bar(x=labels,y=[e.value(prefix+z,'ksi') for z in labels],name=title,marker_color=color),row=1,col=2)
    else:fig.add_annotation(x=.82,y=.5,xref='paper',yref='paper',text='PENDING<br>Confirm applicability and loads',showarrow=False,font=dict(color=AMBER,size=15))
    return theme(fig,'Optional service checks · inactive inputs do not establish a pass',350)

def alternatives_figure(result,indices=None,*,dc_scope='all',max_dc=1.0):
    fig=go.Figure()
    indices=list(range(len(result.candidates))) if indices is None else list(indices)
    candidates=[result.candidates[i] for i in indices]
    if candidates:
        fig.add_trace(go.Scatter(x=[c.weight_lb for c in candidates],y=[candidate_dc(c,dc_scope) for c in candidates],mode='markers+text' if len(candidates)<=30 else 'markers',
            text=[str(i+1) for i in indices],textposition='top center',
            marker=dict(size=10,color=[c.complexity for c in candidates],colorscale='Teal',showscale=True,colorbar=dict(title='Cage score')),
            customdata=[[i+1,c.label,c.max_dc,c.strength_dc,candidate_governing(c,dc_scope)] for i,c in zip(indices,candidates)],
            hovertemplate='Candidate #%{customdata[0]}<br>%{customdata[1]}<br>%{x:.0f} lb gross steel<br>Filter D/C %{y:.4f}<br>All checks %{customdata[2]:.4f}; strength %{customdata[3]:.4f}<br>Controls: %{customdata[4]}<extra></extra>'))
    fig.add_hline(y=1,line_dash='dash',line_color=AMBER)
    if max_dc<1:fig.add_hline(y=max_dc,line_dash='dot',line_color=BLUE,annotation_text=f'Target {max_dc:.3f}')
    fig.update_xaxes(title='Estimated gross steel (lb; hooks/laps/waste excluded)');fig.update_yaxes(title=DC_SCOPES[dc_scope]+' · D/C',range=[0,1.08])
    return theme(fig,f'All {len(indices):,} filter matches · hover for candidate IDs and controlling checks',400)

def checks_html(e):
    rows=[]
    for c in e.checks:
        ratio=f'{c.ratio:.3f}' if isinstance(c.ratio,(int,float)) else str(c.ratio)
        color=RED if 'FAIL' in c.status else AMBER if 'PENDING' in c.status or 'PROVISIONAL' in c.status else TEAL
        rows.append(f'<tr><td>{html.escape(c.label)}</td><td style="color:{color}">{html.escape(c.status)}</td><td><b>{ratio}</b></td><td>{html.escape(c.basis)}</td></tr>')
    extra='<p><b>Additional notebook gates:</b> '+html.escape('; '.join(e.issues) if e.issues else 'Drawn cage passes the entered trial clear-spacing screen.')+'</p><p><b>Combined notebook status:</b> '+html.escape(e.status)+'</p>'
    return '<style>.cap-table{border-collapse:collapse;width:100%;font:12px Arial}.cap-table td,.cap-table th{padding:8px;border-bottom:1px solid #dce5ec;text-align:left}.cap-table th{background:#e7eef4;position:sticky;top:0}</style><table class="cap-table"><thead><tr><th>Check</th><th>Status</th><th>D/C</th><th>Ratio basis</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'+extra

def snapshot(e):
    """Static notebook output that also renders in GitHub's notebook preview."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle,Rectangle
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained');fig.patch.set_facecolor('#f7f9fc')
    ax=axes[0,0];p=e.case['inputs'];dv=BAR_DIAMETER[p['Bar_v']]
    ax.add_patch(Rectangle((0,0),p['b'],p['h'],facecolor='#edf2f6',edgecolor=INK,lw=2))
    ax.add_patch(Rectangle((p['C_s']+dv/2,p['C_b']+dv/2),p['b']-2*p['C_s']-dv,p['h']-p['C_t']-p['C_b']-dv,fill=False,edgecolor=AMBER,lw=2))
    for b in bar_positions(e):ax.add_patch(Circle((b['x'],b['y']),b['diameter']/2,color=TEAL if b['kind']=='Skin' else BLUE))
    ax.set(xlim=(-3,p['b']+3),ylim=(-3,p['h']+3),aspect='equal',title='Bearing section · actual counts and bar diameters',xlabel='Width (in)',ylabel='Depth (in)')
    ax=axes[0,1];length=e.value('L_cap')/12;depth=p['h']/12
    ax.add_patch(Rectangle((0,0),length,depth,facecolor='#edf2f6',edgecolor=BLUE,lw=2))
    for i in range(int(p['N_pile'])):
        x=e.value('E_CL')/12+i*p['S_pile'];ax.add_patch(Rectangle((x-p['D_pile']/24,-1.5),p['D_pile']/12,1.5,color=GREY))
    ax.set(xlim=(-1,length+1),ylim=(-2,depth+1),aspect='equal',title=f'Pile layout · {length:.3f} ft cap length',xlabel='Along cap (ft)')
    ax=axes[1,0];labels=list('NPB');xs=list(range(3))
    ax.bar([x-.18 for x in xs],[e.value('Mu_'+z,'kip*ft') for z in labels],width=.36,color=BLUE,label='Demand')
    ax.bar([x+.18 for x in xs],[e.value('Mr_'+z,'kip*ft') for z in labels],width=.36,color=TEAL,label='Resistance')
    ax.set(xticks=xs,xticklabels=labels,ylabel='kip-ft',title='Flexural strength');ax.legend(frameon=False)
    ax=axes[1,1];ch=sorted((c for c in e.checks if isinstance(c.ratio,(int,float))),key=lambda c:c.ratio,reverse=True)[:7]
    ax.barh([c.label.replace(' — ',' / ') for c in ch],[c.ratio for c in ch],color=TEAL);ax.invert_yaxis();ax.axvline(1,color=AMBER,ls='--');ax.set(xlim=(0,max(1.15,e.max_dc*1.1)),title='Seven largest available D/C ratios',xlabel='D/C')
    for ax in axes.flat:ax.spines[['top','right']].set_visible(False)
    fig.suptitle('C005 · Pier-cap design explorer\n'+e.status,fontsize=14,color=INK)
    return fig
