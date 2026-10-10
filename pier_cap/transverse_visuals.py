"""Views of the same explicit bar schedule used by checks and exports."""
from .output_labels import numbered_figure, numbered_tables
import html
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .transverse import scheduled_bars,run_summary,bar_shape,shape_issues,shape_parameters,development_current,end_bar_note,hook_rotations,rotation_note
from .check_details import hover_basis,service_hover

COLORS={'hoop':'#7952a3','pile_u':'#bd407d'}
NAMES={'hoop':'Closed hoop','pile_u':'U-bar · open bottom'}


@numbered_tables('hoop_schedule')
def schedule_html(e):
    rows=[]
    for r in run_summary(e.case):
        shape=shape_parameters(r);issues=shape_issues(e,r)
        status='CLASH / FIT' if issues else 'Development recorded' if development_current(e.case,r) else 'Development pending'
        if issues:status+='<ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in issues)+'</ul>'
        if any(hook_rotations(r)):status+='<br>'+html.escape(rotation_note(r))
        ends=(f'{shape["end_angle"]:g}° ends; {shape["tail_in"]:g} in hook extension ({"CRSI standard" if shape["extension_mode"]=="standard" and r["bar"]<=8 else "custom / outside standard table"}); inside bend {shape["inside_diameter_in"]:g} in' if r['kind']=='pile_u' else 'Closed outline; closure detail to be verified')
        if any(hook_rotations(r)):
            left,right=hook_rotations(r);ends+=f'; vertical-axis rotation L {left:+g}° / R {right:+g}°'
        rows.append(f'<tr><td>{html.escape(r["id"])}</td><td style="color:{COLORS[r["kind"]]}">{NAMES[r["kind"]]}</td>'
            f'<td><b>{r["count"]} × #{r["bar"]} @ {r["pitch_in"]:g} in</b>{end_bar_note(r)}</td><td>{r["first_in"]/12:.3f} → {r["actual_last_in"]/12:.3f}</td>'
            f'<td>{r["end_in"]/12:.3f}</td><td>{"Overall" if r["zone"]=="G" else "Lower-shear"}</td><td>{ends}</td><td>{status}</td></tr>')
    return ('<h4>Actual transverse steel · all stations measured from the left cap end</h4>'
        '<p><b>Purple = closed hoops. Pink = inverted U-bars, open at the bottom.</b> The pile U spans the top of the cap and has two legs beside the pile. '
        'Each end terminates independently; there is no bar crossing underneath the embedded pile. '
        'The plan looks down from above; the side elevation shows the projected hooks. Rotate the 3D view to see the opening and hook rotation.</p>'
        '<div style="max-width:100%;overflow-x:auto"><table class="cap-table" style="min-width:1100px"><tr><th>Run</th><th>Shape</th><th>Count / size / pitch</th><th>First → last (ft)</th><th>End limit (ft)</th><th>Shear basis</th><th>End geometry</th><th>Review</th></tr>'+''.join(rows)+'</table></div>'
        '<p>Regular pitch stays as entered. Generated runs shift bars near the end as needed to meet their saved minimum clear spacing; the first and last bars stay fixed. '
        'For other runs, <b>Bar at end limit</b> adds a bar in any shorter final gap. '
        'Otherwise, the last bar is the final whole pitch within the limit. Check short end gaps for clear spacing. '
        '<b>Overall (G)</b> uses the overall shear envelope. <b>Lower-shear (L)</b> assigns the separate lower shear input to that run; verify the force diagram supports it. '
        'L does not mean bottom reinforcement.</p><p>U-bars here are transverse reinforcement; they do not add to the longitudinal bottom-bar area. '
        'End bend dimensions describe the drawn steel. Development must be checked and recorded separately. '
        'Hoop closure and congestion at longitudinal hook ends still require detail review.</p>')


def add_projection(fig,e,view):
    runs={r['id']:r for r in e.case['transverse_detail']['runs']};seen=set()
    for b in scheduled_bars(e.case):
        r=runs[b['run']];shape=bar_shape(e,r);values=[pt[1 if view=='elevation' else 0] for pt in shape['points']]
        if any(hook_rotations(r)):
            xs=[(b['station_in']+pt[0])/12 for pt in shape['points_3d']]
            ys=[pt[2 if view=='elevation' else 1] for pt in shape['points_3d']]
        else:xs=[b['station_in']/12]*2;ys=[min(values),max(values)]
        label=f'{r["id"]}: {NAMES[r["kind"]]} #{r["bar"]} @ {r["pitch_in"]:g} in'+end_bar_note(r)
        fig.add_trace(go.Scatter(x=xs,y=ys,mode='lines',
            name=label,legendgroup=r['id'],meta=dict(part='transverse'),showlegend=r['id'] not in seen,line=dict(color=COLORS[r['kind']],width=3),
            hovertemplate=f'<b>{html.escape(b["id"])}</b><br>{label}<br>Leg station {b["station_in"]/12:.3f} ft from left end<br>Projected shape; see 3D view for hook orientation<extra></extra>'))
        seen.add(r['id'])


def add_section(fig,e,run):
    shape=bar_shape(e,run);pts=shape['points'];problems=shape_issues(e,run)
    color=COLORS[run['kind']]
    fig.add_trace(go.Scatter(x=[pt[0] for pt in pts],y=[pt[1] for pt in pts],mode='lines',
        name=f'{run["id"]}: {NAMES[run["kind"]]} #{run["bar"]}',legendgroup=run['id'],meta=dict(part='transverse'),line=dict(color=color,width=5),
        hovertemplate=f'{html.escape(run["id"])} · {NAMES[run["kind"]]} #{run["bar"]}<br>Across %{{x:.2f}} in; above underside %{{y:.2f}} in<extra></extra>'))
    if run['kind']=='pile_u':
        fig.add_trace(go.Scatter(x=[pts[0][0],pts[-1][0]],y=[pts[0][1],pts[-1][1]],mode='markers',name='Independent U ends',
            legendgroup=run['id'],meta=dict(part='transverse'),showlegend=False,marker=dict(size=9,color=color,symbol='circle-open'),hovertemplate='End of U-bar · development must be verified<extra></extra>'))
        fig.add_annotation(name='part:transverse',x=e.case['inputs']['b']/2,y=1,text='OPEN BOTTOM · no crossbar through pile',showarrow=False,bgcolor='white',font=dict(size=10,color=color))
    fig.add_annotation(name='part:transverse',x=0,y=1.12,xref='paper',yref='paper',text=html.escape(run['id'])+': '+('CLASH / FIT — see run schedule' if problems else 'Entered shape · anchorage review'),
        showarrow=False,xanchor='left',font=dict(size=11,color='#bb3e39' if problems else color))


def layout_3d(e):
    from .cage_3d import layout_3d as full_cage
    return full_cage(e)


@numbered_figure('actual_results')
def response_figure(e):
    """Actual station checks on the main plots; no uniform hoop capacity bars."""
    fig=make_subplots(rows=2,cols=2,subplot_titles=('Moment demand / resistance (kip-ft)','Service I steel stress (ksi)',
        'Actual adjacent-bar shear D/C','Torsion / anchorage review'),vertical_spacing=.24,horizontal_spacing=.14)
    for prefix,name,color in [('Mu_','Moment demand','#2166ac'),('Mr_','Moment resistance','#90bce4')]:
        fig.add_trace(go.Bar(x=['Top','At piles','Between piles'],y=[e.value(prefix+z,'kip*ft') for z in 'NPB'],name=name,marker_color=color),row=1,col=1)
    fig.add_trace(go.Bar(x=['Top','At piles','Between piles'],y=[e.value('fs_I_'+z,'ksi') for z in 'NPB'],name='Service I stress',marker_color='#167b75',
        customdata=[service_hover(e,z) for z in 'NPB'],hovertemplate='%{x}<br>Steel stress %{y:.3f} ksi<br>%{customdata}<extra></extra>'),row=1,col=2)
    fig.add_hline(y=e.value('fs_I_limit','ksi'),line_dash='dash',line_color='#d88822',row=1,col=2)
    checks=[c for c in e.checks if c.key.startswith('Chk_actual_shear_')];bars=scheduled_bars(e.case)
    fig.add_trace(go.Scatter(x=[(a['station_in']+b['station_in'])/24 for a,b in zip(bars,bars[1:])],y=[c.ratio for c in checks],
        mode='lines+markers',name='Actual shear · conditional on anchorage',marker=dict(color=['#bb3e39' if c.ratio>1 else '#7952a3' for c in checks]),
        line=dict(color='#7952a3'),text=[c.label for c in checks],customdata=[hover_basis(c) for c in checks],
        hovertemplate='%{text}<br>Interval midpoint %{x:.3f} ft<br>D/C %{y:.3f}<br>%{customdata}<extra></extra>'),row=2,col=1)
    fig.add_hline(y=1,line_dash='dash',line_color='#bb3e39',row=2,col=1)
    fig.update_xaxes(title='Along cap (ft)',row=2,col=1)
    threshold=e.value('T_threshold','kip*ft');torque=e.case['inputs']['Tu']
    if e.lrfd:
        from .lrfd_checks import torsion_threshold
        threshold=min((r['threshold_kip_ft'] for r in e.lrfd['longitudinal']),default=torsion_threshold(e))
    fig.add_annotation(x=.5,y=.5,xref='x4 domain',yref='y4 domain',showarrow=False,align='left',font=dict(size=12),
        text=f'Torque input: {torque:.2f} kip-ft<br>Investigation threshold: {threshold:.2f} kip-ft<br><br><b>Open U-bars have no closed-hoop<br>torsion capacity assigned.</b><br>Verify end development, closure<br>and local force zones.')
    fig.update_xaxes(visible=False,row=2,col=2);fig.update_yaxes(visible=False,row=2,col=2)
    fig.update_layout(title='Actual cage · shear checks conditional on anchorage',template='plotly_white',height=650,
        margin=dict(l=55,r=30,t=90,b=110),legend=dict(orientation='h',y=-.2,font=dict(size=10)),hoverlabel=dict(namelength=-1),barmode='group')
    return fig
