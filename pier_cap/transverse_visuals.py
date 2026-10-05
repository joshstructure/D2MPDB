"""Views of the same explicit bar schedule used by checks and exports."""
import html
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .transverse import scheduled_bars,run_summary,bar_shape,shape_issues,shape_parameters,development_current

COLORS={'hoop':'#7952a3','pile_u':'#bd407d'}
NAMES={'hoop':'Closed hoop','pile_u':'U-bar · open bottom'}


def schedule_html(e):
    rows=[]
    for r in run_summary(e.case):
        shape=shape_parameters(r);issues=shape_issues(e,r)
        status='CLASH / FIT' if issues else 'Development recorded' if development_current(e.case,r) else 'Development pending'
        if issues:status+='<ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in issues)+'</ul>'
        ends=(f'{shape["end_angle"]:g}° ends; {shape["tail_in"]:g} in straight tail; inside bend {shape["inside_diameter_in"]:g} in' if r['kind']=='pile_u' else 'Closed outline; closure detail to be verified')
        rows.append(f'<tr><td>{html.escape(r["id"])}</td><td style="color:{COLORS[r["kind"]]}">{NAMES[r["kind"]]}</td>'
            f'<td><b>{r["count"]} × #{r["bar"]} @ {r["pitch_in"]:g} in</b></td><td>{r["first_in"]/12:.3f} → {r["actual_last_in"]/12:.3f}</td>'
            f'<td>{r["end_in"]/12:.3f}</td><td>{"Overall" if r["zone"]=="G" else "Lower-shear"}</td><td>{ends}</td><td>{status}</td></tr>')
    return ('<h4>Actual transverse steel · all stations measured from the left cap end</h4>'
        '<p><b>Purple = closed hoops. Pink = inverted U-bars, open at the bottom.</b> The pile U spans the top of the cap and has two legs beside the pile. '
        'Each end terminates independently; there is no bar crossing underneath the embedded pile. '
        'The plan looks down from above; the side elevation shows the bars edge-on. Rotate the 3D view to see the opening.</p>'
        '<div style="max-width:100%;overflow-x:auto"><table class="cap-table" style="min-width:1100px"><tr><th>Run</th><th>Shape</th><th>Count / size / pitch</th><th>First → last (ft)</th><th>End limit (ft)</th><th>Shear basis</th><th>End geometry</th><th>Review</th></tr>'+''.join(rows)+'</table></div>'
        '<p>Pitch stays exactly as entered. The last bar is the final whole pitch within the end limit; the limit is not an extra bar. '
        '<b>Overall (G)</b> uses the overall shear envelope. <b>Lower-shear (L)</b> assigns the separate lower shear input to that run; verify the force diagram supports it. '
        'L does not mean bottom reinforcement.</p><p>U-bars here are transverse reinforcement; they do not add to the longitudinal bottom-bar area. '
        'End bend dimensions describe the drawn steel. Development must be checked and recorded separately. '
        'Hoop closure and congestion at longitudinal hook ends still require detail review.</p>')


def add_projection(fig,e,view):
    runs={r['id']:r for r in e.case['transverse_detail']['runs']};seen=set()
    for b in scheduled_bars(e.case):
        r=runs[b['run']];shape=bar_shape(e,r);values=[pt[1 if view=='elevation' else 0] for pt in shape['points']]
        label=f'{r["id"]}: {NAMES[r["kind"]]} #{r["bar"]} @ {r["pitch_in"]:g} in'
        fig.add_trace(go.Scatter(x=[b['station_in']/12]*2,y=[min(values),max(values)],mode='lines',
            name=label,legendgroup=r['id'],showlegend=r['id'] not in seen,line=dict(color=COLORS[r['kind']],width=3),
            hovertemplate=f'<b>{html.escape(b["id"])}</b><br>{label}<br>Station {b["station_in"]/12:.3f} ft from left end<br>Shown edge-on; see transverse section for shape<extra></extra>'))
        seen.add(r['id'])


def add_section(fig,e,run):
    shape=bar_shape(e,run);pts=shape['points'];problems=shape_issues(e,run)
    color=COLORS[run['kind']]
    fig.add_trace(go.Scatter(x=[pt[0] for pt in pts],y=[pt[1] for pt in pts],mode='lines',
        name=f'{run["id"]}: {NAMES[run["kind"]]} #{run["bar"]}',line=dict(color=color,width=5),
        hovertemplate=f'{html.escape(run["id"])} · {NAMES[run["kind"]]} #{run["bar"]}<br>Across %{{x:.2f}} in; above underside %{{y:.2f}} in<extra></extra>'))
    if run['kind']=='pile_u':
        fig.add_trace(go.Scatter(x=[pts[0][0],pts[-1][0]],y=[pts[0][1],pts[-1][1]],mode='markers',name='Independent U ends',
            marker=dict(size=9,color=color,symbol='circle-open'),hovertemplate='End of U-bar · development must be verified<extra></extra>'))
        fig.add_annotation(x=e.case['inputs']['b']/2,y=1,text='OPEN BOTTOM · no crossbar through pile',showarrow=False,bgcolor='white',font=dict(size=10,color=color))
    fig.add_annotation(x=0,y=1.12,xref='paper',yref='paper',text=html.escape(run['id'])+': '+('CLASH / FIT — see run schedule' if problems else 'Entered shape · anchorage review'),
        showarrow=False,xanchor='left',font=dict(size=11,color='#bb3e39' if problems else color))


def layout_3d(e):
    fig=go.Figure();p=e.case['inputs'];L=e.value('L_cap');runs={r['id']:r for r in e.case['transverse_detail']['runs']};seen=set()
    for bar in scheduled_bars(e.case):
        run=runs[bar['run']];pts=bar_shape(e,run)['points']
        fig.add_trace(go.Scatter3d(x=[bar['station_in']]*len(pts),y=[pt[0] for pt in pts],z=[pt[1] for pt in pts],mode='lines',
            name=f'{run["id"]}: {NAMES[run["kind"]]} #{run["bar"]}',legendgroup=run['id'],showlegend=run['id'] not in seen,
            line=dict(color=COLORS[run['kind']],width=5),hovertemplate=f'{html.escape(bar["id"])} · #{bar["bar"]}<br>Station {bar["station_in"]/12:.3f} ft<br>Across %{{y:.2f}} in; elevation %{{z:.2f}} in<extra></extra>'))
        seen.add(run['id'])
    def box(x0,x1,y0,y1,z0,z1,name,color,opacity):
        fig.add_trace(go.Mesh3d(x=[x0,x1,x1,x0,x0,x1,x1,x0],y=[y0,y0,y1,y1,y0,y0,y1,y1],z=[z0,z0,z0,z0,z1,z1,z1,z1],
            i=[0,0,4,4,0,0,1,1,2,2,3,3],j=[1,2,5,6,1,5,2,6,3,7,0,4],k=[2,3,6,7,5,4,6,5,7,6,4,7],
            color=color,opacity=opacity,name=name,showlegend=False,hoverinfo='name'))
    box(0,L,0,p['b'],0,p['h'],'Cap','#bdcbd5',.08)
    for i in range(int(p['N_pile'])):
        x=e.value('E_CL')+i*p['S_pile']*12;d=p['D_pile']/2
        box(x-d,x+d,p['b']/2-d,p['b']/2+d,-12,p['Pile_embed'],f'Pile {i+1}','#72899b',.6)
    fig.update_layout(title='3D VIEW · hoops and open-bottom U-bars',height=580,template='plotly_white',
        margin=dict(l=0,r=0,t=60,b=20),legend=dict(orientation='h',y=-.04,font=dict(size=10)),hoverlabel=dict(namelength=-1),
        scene=dict(xaxis_title='Along cap (in)',yaxis_title='Across cap (in)',zaxis_title='Above underside (in)',aspectmode='data',
                   camera=dict(eye=dict(x=1.3,y=-1.8,z=.9))))
    return fig


def response_figure(e):
    """Actual station checks on the main plots; no uniform hoop capacity bars."""
    fig=make_subplots(rows=2,cols=2,subplot_titles=('Moment demand / resistance (kip-ft)','Service I steel stress (ksi)',
        'Actual adjacent-bar shear D/C','Torsion / anchorage review'),vertical_spacing=.24,horizontal_spacing=.14)
    for prefix,name,color in [('Mu_','Moment demand','#2166ac'),('Mr_','Moment resistance','#90bce4')]:
        fig.add_trace(go.Bar(x=['Top','At piles','Between piles'],y=[e.value(prefix+z,'kip*ft') for z in 'NPB'],name=name,marker_color=color),row=1,col=1)
    fig.add_trace(go.Bar(x=['Top','At piles','Between piles'],y=[e.value('fs_I_'+z,'ksi') for z in 'NPB'],name='Service I stress',marker_color='#167b75'),row=1,col=2)
    fig.add_hline(y=e.value('fs_I_limit','ksi'),line_dash='dash',line_color='#d88822',row=1,col=2)
    checks=[c for c in e.checks if c.key.startswith('Chk_actual_shear_')];bars=scheduled_bars(e.case)
    fig.add_trace(go.Scatter(x=[(a['station_in']+b['station_in'])/24 for a,b in zip(bars,bars[1:])],y=[c.ratio for c in checks],
        mode='lines+markers',name='Actual shear · conditional on anchorage',marker=dict(color=['#bb3e39' if c.ratio>1 else '#7952a3' for c in checks]),
        line=dict(color='#7952a3'),text=[c.label for c in checks],
        hovertemplate='%{text}<br>Interval midpoint %{x:.3f} ft<br>D/C %{y:.3f}<br>Requires developed legs and verified force zone<extra></extra>'),row=2,col=1)
    fig.add_hline(y=1,line_dash='dash',line_color='#bb3e39',row=2,col=1)
    fig.update_xaxes(title='Along cap (ft)',row=2,col=1)
    threshold=e.value('T_threshold','kip*ft');torque=e.case['inputs']['Tu']
    fig.add_annotation(x=.5,y=.5,xref='x4 domain',yref='y4 domain',showarrow=False,align='left',font=dict(size=12),
        text=f'Torque input: {torque:.2f} kip-ft<br>Investigation threshold: {threshold:.2f} kip-ft<br><br><b>Open U-bars have no closed-hoop<br>torsion capacity assigned.</b><br>Verify end development, closure<br>and local force zones.')
    fig.update_xaxes(visible=False,row=2,col=2);fig.update_yaxes(visible=False,row=2,col=2)
    fig.update_layout(title='Actual cage · shear checks conditional on anchorage',template='plotly_white',height=650,
        margin=dict(l=55,r=30,t=90,b=110),legend=dict(orientation='h',y=-.2,font=dict(size=10)),hoverlabel=dict(namelength=-1),barmode='group')
    return fig
