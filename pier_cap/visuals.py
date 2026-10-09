"""Geometry-driven drawings and plots; no invented load distribution."""
import math
import html
from collections import defaultdict
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .model import bar_positions,BAR_DIAMETER,side_reinforcement
from .detailing import spacing_records,hook_paths,standard_hook,required_clear
from .transverse import enabled as actual_transverse
from .view_controls import bar_family,drawing_controls
from .optimizer import candidate_dc,candidate_governing,governing_check,DC_SCOPES

BLUE='#1f5b91';TEAL='#167b75';AMBER='#d88822';RED='#bb3e39';INK='#213649';GREY='#b8c7d1'
HOOP='#7952a3'
MOMENT='#2166ac';MOMENT_CAPACITY='#90bce4';SHEAR='#8250a0';SHEAR_CAPACITY='#c4a4d8'


def pile_head_help_html():
    """Small input guide; symbolic dimensions, not a proposed pile-head detail."""
    return '''<div style="max-width:336px;white-space:normal;line-height:1.4">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 336 224" role="img"
     aria-label="Pile-head section: embedment is measured from the cap underside to the pile top. Clear gap is measured from the pile top to the outside surface of the bar."
     style="display:block;width:100%;height:auto;background:#fff;border-radius:4px;font-family:Arial,sans-serif;font-size:12px">
  <rect x="10" y="30" width="316" height="136" fill="#f2f5f7" stroke="#8ea5b5"/>
  <text x="20" y="47" fill="#213649">Cap</text>
  <rect x="138" y="105" width="72" height="112" fill="#bccbd6" stroke="#213649" stroke-width="1.5"/>
  <text x="174" y="194" text-anchor="middle" fill="#213649">Pile</text>
  <circle cx="174" cy="71" r="8" fill="#1f5b91"/>
  <text x="174" y="53" text-anchor="middle" fill="#1f5b91">Bar</text>
  <g fill="none" stroke="#167b75" stroke-width="1.3">
    <path d="M174 79H249 M210 105H249" stroke-width=".8"/>
    <path d="M242 79V105 M238 85L242 79L246 85 M238 99L242 105L246 99"/>
  </g>
  <text x="252" y="89" fill="#167b75">Clear gap</text>
  <text x="252" y="103" fill="#167b75">to pile</text>
  <g fill="none" stroke="#9b6012" stroke-width="1.3">
    <path d="M95 105H138 M95 166H130" stroke-width=".8"/>
    <path d="M102 105V166 M98 111L102 105L106 111 M98 160L102 166L106 160"/>
  </g>
  <text x="20" y="139" fill="#9b6012">Embedment</text>
  <text x="16" y="185" fill="#213649">Cap underside</text>
  <path d="M65 175V166" stroke="#213649" stroke-width=".8"/>
  <text x="16" y="215" fill="#64748b" font-size="10">Schematic · not to scale</text>
</svg>
<p style="margin:4px 0"><b>Clear gap to pile:</b> minimum concrete clearance from the pile surface to the <b>outside of a longitudinal bar</b>, beside or above the pile—not to the bar center.<br>
<b>Pile embedment:</b> height of the pile top above the cap underside.</p>
<p style="margin:6px 0 0;font-size:12px"><b>Starting values: 12 in embedment; 2 in clear gap.</b> Confirm these for the project. Saved cases retain their entered values.</p>
<p style="margin:6px 0 0;font-size:12px">The 2 in gap is an adopted starting value from <a href="https://www.fdot.gov/Structures/StructuresManual/CurrentRelease" target="_blank">FDOT SDG 2026 3.11.2.F.1.c</a>, which applies to the specified laterally loaded footings with full pile bending capacity developed; it is not a universal bent-cap clearance rule. FDOT SDM Figure 12.5-3 separately accounts for pile-driving tolerance. This notebook adds that horizontal allowance separately. Check the required project detail and actual bar positions in <b>Live cage</b>.</p>
</div>'''


def check_family(check):
    if check.key.startswith('Chk_flex_'):return 'Moment / flexure',MOMENT
    if check.key.startswith(('Chk_shear_','Chk_actual_shear_')):return 'Shear',SHEAR
    if check.key.startswith('Chk_torsteel_'):return 'Shear + torsion steel',AMBER
    return 'Other checks','#86939f'


def check_color(check):
    return RED if check.ratio>1 or 'FAIL' in check.status else check_family(check)[1]

def theme(fig,title,height=460):
    fig.update_layout(title=dict(text=title,font=dict(size=17)),template='plotly_white',height=height,
        font=dict(family='Arial',size=12,color=INK),margin=dict(l=50,r=25,t=65,b=45),
        paper_bgcolor='#ffffff',plot_bgcolor='#ffffff',legend=dict(orientation='h',y=-.12),hoverlabel=dict(bgcolor='white',namelength=-1,align='left'))
    return fig

def section_figure(e,region='B',run_id=None):
    p=e.case['inputs'];b=p['b'];h=p['h'];fig=go.Figure();dv=BAR_DIAMETER[p['Bar_v']]
    fig.add_shape(type='rect',x0=0,y0=0,x1=b,y1=h,line=dict(color=INK,width=2),fillcolor='#f2f5f7',layer='below')
    actual=actual_transverse(e.case)
    if not actual:
        # Reference geometry at a pile must never depict a bottom leg through it.
        xs=[p['C_s']+dv/2,p['C_s']+dv/2,b-p['C_s']-dv/2,b-p['C_s']-dv/2]
        ys=[p['C_b']+dv/2,h-p['C_t']-dv/2,h-p['C_t']-dv/2,p['C_b']+dv/2]
        if region=='B':xs.append(xs[0]);ys.append(ys[0])
        fig.add_trace(go.Scatter(x=xs,y=ys,mode='lines',line=dict(color=HOOP,width=3,dash='dash'),
            name='Reference shape · actual layout not set',meta=dict(part='transverse'),hoverinfo='name'))
    else:
        from .transverse_visuals import add_section
        kind='pile_u' if region=='P' else 'hoop'
        runs=[r for r in e.case['transverse_detail']['runs'] if r['kind']==kind]
        run=next((r for r in runs if r['id']==run_id),runs[0] if runs else None)
        if run:add_section(fig,e,run)
        else:fig.add_annotation(x=b/2,y=h/2,text='No '+('pile U-bar' if region=='P' else 'hoop')+' run entered',showarrow=False)
    if region=='P' and p['Ready_pile']:
        left=(b-p['D_pile'])/2;right=(b+p['D_pile'])/2
        fig.add_shape(type='rect',name='part:piles',x0=e.value('Pile_left')-p['C_pile'],x1=e.value('Pile_right')+p['C_pile'],y0=0,y1=p['Pile_embed']+p['C_pile'],line=dict(color=RED,dash='dot'),fillcolor='rgba(187,62,57,.06)',layer='below')
        fig.add_shape(type='rect',name='part:piles',x0=left,x1=right,y0=-3,y1=p['Pile_embed'],line=dict(color=INK,width=2),fillcolor='#b8c7d1',layer='below')
        fig.add_annotation(name='part:piles',x=b/2,y=p['Pile_embed']/2,text=f'Pile · {p["D_pile"]:g} in<br>embed {p["Pile_embed"]:g} in',showarrow=False,font=dict(size=10))
        fig.add_annotation(name='part:piles',x=b/2,y=-4.5,text='Dotted limit: bar clearance + pile placement allowance',showarrow=False,font=dict(size=9,color=RED))
    elif region=='P':
        fig.add_annotation(x=b/2,y=h/2,text='Pile-head dimensions pending<br>Bar clearance is not verified',showarrow=False,bgcolor='#fff3d9',font=dict(color=RED))
    groups=defaultdict(list)
    for bar in bar_positions(e,region):
        groups[bar['kind']].append(bar);r=bar['diameter']/2
        color=TEAL if bar['kind']=='Skin' else AMBER if bar.get('additional') else BLUE
        # Draw physical circles as traces so visibility controls hide the bar,
        # not merely the transparent hover target at its center.
        angles=[2*math.pi*i/32 for i in range(33)]
        fig.add_trace(go.Scatter(x=[bar['x']+r*math.cos(a) for a in angles],
            y=[bar['y']+r*math.sin(a) for a in angles],mode='lines',fill='toself',
            line=dict(color=color,width=1),fillcolor=color,name='Bar outline',
            meta=dict(part=bar_family(bar)),legendgroup=bar['kind'],showlegend=False,hoverinfo='skip'))
    for label,bars in groups.items():
        color=TEAL if label=='Skin' else AMBER if label.startswith('Added') else BLUE
        display_label='Side bars' if label=='Skin' else label+' · continuous' if label.startswith('Bottom') else label
        fig.add_trace(go.Scatter(x=[v['x'] for v in bars],y=[v['y'] for v in bars],mode='markers',name=f'{display_label}: {len(bars)} bars',legendgroup=label,meta=dict(part=bar_family(bars[0])),
            marker=dict(size=8,color=color,opacity=.15),text=[f"#{v['bar']} · diameter {v['diameter']:g} in" for v in bars],hovertemplate='%{text}<br>x=%{x:.2f}, y=%{y:.2f} in<extra>%{fullData.name}</extra>'))
    records=spacing_records(e,region,bar_positions(e,region))
    if records:
        worst=max(records,key=lambda r:r['ratio']);a=worst['a'];c=worst['b'];color=RED if worst['status']=='FAIL' else TEAL
        fig.add_trace(go.Scatter(x=[a['x'],c['x']],y=[a['y'],c['y']],mode='lines+markers',line=dict(color=color,width=3,dash='dot'),marker=dict(color=color,size=9,symbol='circle-open'),
            name=f"Governing clear: {worst['actual']:.2f} / {worst['required']:.2f} in required",meta=dict(part='clearance'),hoverinfo='name'))
        fig.add_annotation(name='part:clearance',x=0,y=1.04,xref='paper',yref='paper',xanchor='left',showarrow=False,font=dict(color=color,size=11),
            text=f"{worst['status']} · {worst['label']} clear {worst['actual']:.3f} in {'<' if worst['status']=='FAIL' else '≥'} {worst['required']:.3f} in required")
    if p['n_'+region+'U']:
        fig.add_annotation(x=b/2,y=-4,text=f"U-leg inventory: {p['n_'+region+'U']:g} #{p['Bar_U']:g}; positions unresolved",showarrow=False,font=dict(color=RED,size=11))
    fig.update_xaxes(title='Width (in)',range=[-3,b+3],constrain='domain',zeroline=False)
    fig.update_yaxes(title='Depth from bottom (in)',range=[-6,h+3],scaleanchor='x',scaleratio=1,zeroline=False)
    title=('Cross section · at pile' if region=='P' else 'Cross section · between piles')+f' · {b:g} × {h:g} in'
    theme(fig,title,520);fig.update_layout(legend=dict(font=dict(size=10),orientation='h',y=-.2),margin=dict(t=90,b=110))
    return drawing_controls(fig)


def reinforcement_summary_html(e):
    p=e.case['inputs'];continuous=int(p['n_P1']+p['n_P2']);extra=int(p['n_B1']+p['n_B2'])
    migration=e.case.get('reinforcement_migration',{})
    note=('<p style="color:#9b6012"><b>Saved-case conversion:</b> '+html.escape(migration['note'])+'</p>') if migration else ''
    transverse_note=('Purple = actual closed hoops; pink = actual open-bottom pile U-bars. Select a run in the editor to inspect its section.<br>' if actual_transverse(e.case) else 'Purple dashed shapes / pitch samples are reference geometry; use Actual hoops and pile U-bars to set construction stations.<br>')
    return (f'<p><b>Between-pile inputs are ADDITIONAL steel.</b> '
        f'{continuous} continuous #{p["Bar_P"]:g} + {extra} added #{p["Bar_B"]:g} = <b>{continuous+extra} bottom bars in the span</b> '
        '(excluding any unresolved U-leg inventory).<br>'
        f'At piles: <b>{e.value("As_P"):.3f} in²</b>. Between piles: <b>{e.value("As_B"):.3f} in² combined</b>. '
        'Blue bars continue through the full cap; orange bars are additional span bars with 90° hooks. '
        +transverse_note+
        'Hook fit is checked; development, cutoff lengths, end anchorage and pile-head hoop arrangement remain pending.</p>'+note)


def configuration_html(e):
    """Quick inventory of the current inputs, before the live drawings."""
    from .transverse import run_summary
    p=e.case['inputs']
    top=' + '.join(f'{p["n_N"+str(i)]:g} × #{p["Bar_N"+str(i)]:g} (row {i})' for i in (1,2,3) if p['n_N'+str(i)]) or 'None'
    def rows(prefix,size):
        return ' + '.join(f'{p["n_"+prefix+str(i)]:g} × #{p[size]:g} (row {i})' for i in (1,2) if p['n_'+prefix+str(i)]) or 'None'
    entries=[('Top steel',top),('Continuous bottom',rows('P','Bar_P')),
             ('Added between piles',rows('B','Bar_B')+' per span'),
             ('Side steel',f'{p["n_skin"]:g} × #{p["Bar_skin"]:g} per side'),
             ('Pile head',f'{p["Pile_embed"]:g} in embed · {p["C_pile"]:g} in clear'+('' if p['Ready_pile'] else ' · confirm dimensions'))]
    if actual_transverse(e.case):
        runs=run_summary(e.case)
        for kind,label in [('hoop','Closed hoops'),('pile_u','Open-bottom U-bars')]:
            selected=[r for r in runs if r['kind']==kind]
            value='; '.join(f'{r["id"]}: {r["count"]} × #{r["bar"]} @ {r["pitch_in"]:g} in' for r in selected) or 'None entered'
            entries.append((label,value))
    else:
        entries.append(('Reference hoops',f'#{p["Bar_v"]:g} · overall {p["s_G"]:g} in / lower-shear {p["s_L"]:g} in pitch · actual stations not set'))
    if p['n_PU'] or p['n_BU']:
        entries.append(('Unpositioned U-leg inventory',f'At piles {p["n_PU"]:g}; between piles {p["n_BU"]:g} · #{p["Bar_U"]:g}'))
    if e.longitudinal_layout is not None:
        layout=e.longitudinal_layout
        entries.append(('Longitudinal fit','Fitted inside the common envelope of all actual hoop / U-bar runs' if layout['fitted'] else 'FIT FAILED — review the cage and failed checks below'))
        entries.append(('Steel centroid from tension face',f'Top {e.value("dc_N"):.3f} in · bottom at piles {e.value("dc_P"):.3f} in · bottom between piles {e.value("dc_B"):.3f} in'))
        entries.append(('Effective depth used in calculations',f'Top {e.value("d_N"):.3f} in · at piles {e.value("d_P"):.3f} in · between piles {e.value("d_B"):.3f} in'))
        entries.append(('Position basis',('Drawings and flexure, service, fatigue and shear-depth calculations use these fitted coordinates.' if layout['fitted'] else 'Drawings and calculations share the displayed trial coordinates; this cage has not passed the fit check.')+' Counts and sizes are unchanged; hook-end congestion and development remain separate checks.'))
    return ('<div style="padding:12px;background:#eaf1f6;border-radius:6px"><b>Current bar configuration</b>'
        +f' · {p["b"]:g} × {p["h"]:g} in cap<table style="width:100%;font-size:13px">'
        +''.join(f'<tr><td style="padding:4px 12px 4px 0;vertical-align:top"><b>{label}</b></td><td>{html.escape(value)}</td></tr>' for label,value in entries)
        +'</table></div>')


def clear_spacing_html(e):
    rows=[]
    for region in 'PB':
        for r in spacing_records(e,region,bar_positions(e,region)):
            color=RED if r['status']=='FAIL' else TEAL
            rows.append(f'<tr><td>{region} · {r["label"]}</td><td>{r["actual"]:.3f}</td><td>{r["required"]:.3f}</td><td style="color:{color}"><b>{r["status"]}</b></td></tr>')
    s=e.case['screening']
    return (f'<h4>Rebar clear spacing · surface to surface</h4><p>AASHTO LRFD BDS: same-layer minimum = max(1.5db, 1.5 × aggregate, 1.5 in); '
        f'between layers = max(db, 1 in). Larger project minimum also applies. Aggregate: {s["aggregate_in"]:g} in '
        f'({"confirmed" if s["aggregate_confirmed"] else "UNCONFIRMED assumption"}). Vertical alignment is checked separately.</p>'
        '<table class="cap-table"><tr><th>Region / bars</th><th>Actual clear (in)</th><th>Required clear (in)</th><th>Status</th></tr>'+''.join(rows)+'</table>')

def elevation_figure(e,*,zone_labels=True):
    p=e.case['inputs'];L=e.value('L_cap');h=p['h'];D=p['D_pile']
    fig=go.Figure()
    fig.add_shape(type='rect',x0=0,x1=L/12,y0=0,y1=h,fillcolor='#eef3f7',line=dict(color=INK,width=2),layer='below')
    centers=[e.value('E_CL')+j*p['S_pile']*12 for j in range(int(p['N_pile']))]
    for j,x in enumerate(centers,1):
        fig.add_shape(type='rect',name='part:piles',x0=(x-D/2)/12,x1=(x+D/2)/12,y0=-18,y1=p['Pile_embed'],fillcolor='#b8c7d1',line=dict(color=INK),layer='below')
        fig.add_annotation(name='part:piles',x=x/12,y=-10,text=f'P{j}',showarrow=False)
    # A short pitch illustration, deliberately not a full-cap station schedule.
    # Its center is arbitrary; actual first-hoop and zone stations are not inputs.
    dv=BAR_DIAMETER[p['Bar_v']];pitch=p['s_G']
    inset=D/2+e.value('Tol_pile')+p['C_pile']+dv/2
    left=centers[0]+inset;right=centers[1]-inset
    count=min(5,math.floor((right-left)/pitch)+1)
    if count>=2 and not actual_transverse(e.case):
        start=(left+right-(count-1)*pitch)/2
        stations=[start+i*pitch for i in range(count)]
        fig.add_trace(go.Scatter(x=[v for x in stations for v in (x/12,x/12,None)],
            y=[v for _ in stations for v in (p['C_b']+dv/2,h-p['C_t']-dv/2,None)],
            mode='lines',meta=dict(part='transverse'),name=f'Hoop sample: #{p["Bar_v"]:g} @ {pitch:g} in c/c',
            line=dict(color=HOOP,width=3,dash='dash'),
            hovertemplate=f'<b>Hoop sample · side elevation</b><br>#{p["Bar_v"]:g} @ {pitch:g} in center to center<br>Overall check (G)<br>Illustrative position; stationing pending<extra></extra>'))
        fig.add_annotation(name='part:transverse',x=(left+right)/24,y=h+2,text='Hoop sample',showarrow=False,font=dict(color=HOOP,size=10))
    if actual_transverse(e.case):
        from .transverse_visuals import add_projection
        add_projection(fig,e,'elevation')
    fig.add_shape(type='line',x0=0,x1=L/12,y0=0,y1=0,line=dict(color=INK,dash='dash'))
    continuous=bar_positions(e,'P');groups=defaultdict(list)
    for bar in continuous:groups[(bar['kind'],bar['y'],bar['bar'])].append(bar)
    seen_skin=False
    for (kind,y,size),bars in groups.items():
        fig.add_trace(go.Scatter(x=[p['C_s']/12,(L-p['C_s'])/12],y=[y,y],mode='lines',meta=dict(part=bar_family(bars[0])),
            name=f'Side bars: {int(2*p["n_skin"])} #{size} continuous' if kind=='Skin' else f'{kind}: {len(bars)} #{size} continuous',showlegend=kind!='Skin' or not seen_skin,legendgroup=kind,line=dict(color=TEAL if kind=='Skin' else BLUE,width=1 if kind=='Skin' else 2),
            hovertemplate='%{fullData.name}<br>Elevation %{y:.3f} in<extra></extra>'))
        if kind=='Skin':seen_skin=True
    paths=hook_paths(e,bar_positions(e,'B'));drawn=set()
    hook_failure=any(c.key.startswith('Chk_hook_') and 'FAIL' in c.status for c in e.checks)
    for path in paths:
        b=path['bar'];key=(path['span'],b['layer'],b['y'])
        if key in drawn:continue
        drawn.add(key)
        count=sum(t['span']==path['span'] and t['bar']['layer']==b['layer'] for t in paths)
        fig.add_trace(go.Scatter(x=[pt[0]/12 for pt in path['points']],y=[pt[1] for pt in path['points']],mode='lines',
            meta=dict(part='added'),name=f'Span {path["span"]}: {count} #{b["bar"]} added'+(' · FAIL' if hook_failure else ''),line=dict(color=RED if hook_failure else AMBER,width=3),
            hovertemplate=f'{count} added #{b["bar"]} · 90° hooks<br>Inside bend {path["inside_diameter"]:.2f} in; tail {path["tail"]:.2f} in<br>Station %{{x:.3f}} ft; elevation %{{y:.3f}} in<extra></extra>'))
    xdim=(centers[0]-D/2-5)/12
    fig.add_trace(go.Scatter(x=[xdim,xdim],y=[0,p['Pile_embed']],mode='lines+markers',line=dict(color=RED),marker=dict(symbol='line-ew',size=10),name='Pile embedment',meta=dict(part='piles'),showlegend=False))
    fig.add_annotation(name='part:piles',x=xdim,y=p['Pile_embed']/2,text=f'  Embed {p["Pile_embed"]:g} in',xanchor='right',showarrow=False,font=dict(color=RED))
    note=('FAIL: hook fit / clearance. ' if hook_failure else '')+('90° hooks outside pile envelope; development / cutoff pending.' if paths else 'No additional span bars entered; continuous bars remain throughout the cap.')
    fig.add_annotation(name='part:added',x=0,y=1.10,xref='paper',yref='paper',text=note,showarrow=False,xanchor='left',font=dict(size=11,color=RED if hook_failure else AMBER))
    fig.update_xaxes(title='Along cap (ft)',range=[-1,L/12+1],zeroline=False)
    fig.update_yaxes(title='Elevation above cap underside (in)',range=[-22,h+5],scaleanchor='x',scaleratio=1/12,zeroline=False)
    theme(fig,'SIDE ELEVATION · along the cap length',540)
    fig.add_annotation(name='part:transverse',x=0,y=1.15,xref='paper',yref='paper',xanchor='left',showarrow=False,
        text=('Each purple / pink line is an entered bar station · Open-bottom U-bars: see cross section / 3D.' if actual_transverse(e.case) else 'Dashed hoops show reference pitch only · Actual stations are not set.'),
        align='left',font=dict(size=11,color=HOOP))
    fig.update_layout(legend=dict(orientation='h',y=-.3,font=dict(size=10)),margin=dict(t=130,b=170))
    if zone_labels:
        from .zone_visuals import add_zone_dimensions
        add_zone_dimensions(fig,e)
    return drawing_controls(fig)


def reinforcement_plan_figure(e,*,zone_labels=True):
    p=e.case['inputs'];L=e.value('L_cap');fig=go.Figure()
    fig.add_shape(type='rect',x0=0,x1=L/12,y0=0,y1=p['b'],line=dict(color=INK),fillcolor='#f2f5f7',layer='below')
    for i in range(int(p['N_pile'])):
        c=e.value('E_CL')+i*p['S_pile']*12
        fig.add_shape(type='rect',name='part:piles',x0=(c-p['D_pile']/2)/12,x1=(c+p['D_pile']/2)/12,y0=(p['b']-p['D_pile'])/2,y1=(p['b']+p['D_pile'])/2,line=dict(color=GREY),fillcolor='#d2dde5',layer='below')
    seen=set()
    for b in bar_positions(e,'P'):
        key=b['kind'];part=bar_family(b);show=key not in seen;seen.add(key)
        fig.add_trace(go.Scatter(x=[p['C_s']/12,(L-p['C_s'])/12],y=[b['x'],b['x']],mode='lines',
            name=('Side bars' if part=='side' else key)+' continuous',legendgroup=key,showlegend=show,meta=dict(part=part),
            line=dict(color=TEAL if part=='side' else BLUE,width=2,dash='dot' if part=='top' else 'solid'),
            hovertemplate=f'{key} · #{b["bar"]}<br>Across cap {b["x"]:.3f} in<br>Elevation {b["y"]:.3f} in<extra></extra>'))
    seen=set()
    for t in hook_paths(e,bar_positions(e,'B')):
        b=t['bar'];key=b['layer'];show=key not in seen;seen.add(key)
        fig.add_trace(go.Scatter(x=[t['left']/12,t['right']/12],y=[b['x'],b['x']],mode='lines+markers',name=key+' added / hooks up',legendgroup='extra'+key,showlegend=show,meta=dict(part='added'),
            marker=dict(symbol='triangle-up',size=6),line=dict(color=AMBER,width=2),hovertemplate=f'Added #{b["bar"]}<br>Across cap {b["x"]:.3f} in<extra></extra>'))
    if actual_transverse(e.case):
        from .transverse_visuals import add_projection
        add_projection(fig,e,'plan')
    fig.update_xaxes(title='Along cap (ft)',range=[-1,L/12+1]);fig.update_yaxes(title='Across cap (in)',range=[-3,p['b']+3],scaleanchor='x',scaleratio=1/12)
    theme(fig,'PLAN VIEW · steel viewed from above (layers overlap)',430)
    fig.update_layout(legend=dict(y=-.35,font=dict(size=10)),margin=dict(b=110))
    if zone_labels:
        from .zone_visuals import add_zone_dimensions
        add_zone_dimensions(fig,e)
    return drawing_controls(fig)


def hoop_explanation_html(e):
    if actual_transverse(e.case):
        from .transverse_visuals import schedule_html
        return schedule_html(e)
    p=e.case['inputs']
    same=math.isclose(p['Vu_G'],p['Vu_L'],abs_tol=1e-8,rel_tol=0)
    rows=''.join(f'<tr><td>{label}</td><td>{p["Vu_"+z]:.2f} kip</td>'
        f'<td><b>#{p["Bar_v"]:g} @ {p["s_"+z]:g} in c/c</b></td>'
        f'<td>{p["s_"+z]-BAR_DIAMETER[p["Bar_v"]]:.3f} in</td></tr>'
        for z,label in [('G','Overall (G; formerly Global)'),('L','Lower-shear interval (L)')])
    return ('<h4>How to read the hoops</h4><p><b>Overall (G)</b> uses the overall cap shear envelope. '
        '<b>Lower-shear interval (L)</b> is a separate check for a region with a justified smaller shear demand. '
        'The L label refers to shear demand, not a lower elevation or bottom reinforcement.</p>'
        +('<p><b>Both shear inputs are identical in this case.</b> The XML importer copies overall shear into L until a lower-shear interval is established.</p>' if same else
          '<p>The two shear inputs differ. The location and extent of the lower-shear interval still need to be established separately.</p>')
        +'<table class="cap-table"><tr><th>Check</th><th>Shear input</th><th>Hoop size / pitch</th><th>Clear gap</th></tr>'+rows+'</table>'
        '<p><b>#6 @ 9 in</b>, for example, means a No. 6 bar at 9-inch center-to-center spacing; it does not mean six hoops. '
        'The side-elevation samples show successive hoops edge-on. The cross section shows the shape of one hoop.</p>'
        '<p><b>Why stationing is pending:</b> this case has not enabled its actual transverse layout. '
        'Use <b>Actual hoops and pile U-bars → Create starting layout</b>, then edit the first bar, end limit, pitch and end geometry for each run. '
        'These reference samples illustrate spacing only.</p>')


def hoop_figure(e):
    if actual_transverse(e.case):
        from .transverse_visuals import layout_3d
        return layout_3d(e)
    p=e.case['inputs'];dv=BAR_DIAMETER[p['Bar_v']]
    same=all(math.isclose(p[n+'G'],p[n+'L'],abs_tol=1e-8,rel_tol=0) for n in ('s_','Vu_'))
    samples=[('G','Overall + lower-shear checks · same inputs')] if same else [('G','Overall check (G)'),('L','Lower-shear interval check (L)')]
    nr=len(samples)+1
    titles=[name+'<br>SIDE ELEVATION SAMPLE' for _,name in samples]+['CROSS SECTION · one hoop viewed end-on']
    fig=make_subplots(rows=nr,cols=1,subplot_titles=titles,vertical_spacing=.19 if same else .14)
    x0=p['C_s']+dv/2;x1=p['b']-x0;y0=p['C_b']+dv/2;y1=p['h']-p['C_t']-dv/2
    for row,(z,name) in enumerate(samples,1):
        s=p['s_'+z];limit=e.value('s_allow_'+z);clear=s-dv;minimum=required_clear(e,dv)
        color=RED if s>limit or clear<minimum else HOOP
        length=max(48,2*s);xs=[i*s for i in range(min(12,math.floor(length/s))+1)]
        fig.add_shape(type='rect',x0=0,x1=length,y0=0,y1=p['h'],fillcolor='#eef3f7',line=dict(color=GREY),layer='below',row=row,col=1)
        fig.add_trace(go.Scatter(x=[v for x in xs for v in (x,x,None)],y=[v for _ in xs for v in (y0,y1,None)],
            mode='lines',name=f'{name}: #{p["Bar_v"]:g} @ {s:g} in c/c',line=dict(color=color,width=4),showlegend=False,
            hovertemplate=f'<b>#{p["Bar_v"]:g} @ {s:g} in c/c</b><br>{name}<br>Clear gap {clear:.3f} in<br>Illustrative sample; not cap stations<extra></extra>'),row=row,col=1)
        fig.add_annotation(x=length/2,y=p['h']+6,text=f'<b>#{p["Bar_v"]:g} @ {s:g} in c/c</b> · {clear:.3f} in clear',showarrow=False,font=dict(color=color,size=12),row=row,col=1)
        fig.add_trace(go.Scatter(x=[0,s],y=[y1/2,y1/2],mode='lines+markers',line=dict(color=INK),marker=dict(symbol='line-ns',size=12),
            showlegend=False,hovertemplate=f'Pitch: {s:g} in center to center<extra></extra>'),row=row,col=1)
        fig.add_annotation(x=length/2,y=-9,text=f'Max pitch {limit:.2f} in · min clear gap {minimum:.2f} in',showarrow=False,font=dict(size=11),row=row,col=1)
        fig.update_xaxes(title='Distance along illustrative sample (in)',range=[-3,length+3],row=row,col=1)
        fig.update_yaxes(title='Above underside (in)',range=[-12,p['h']+13],row=row,col=1)
    fig.add_shape(type='rect',x0=0,x1=p['b'],y0=0,y1=p['h'],fillcolor='#eef3f7',line=dict(color=INK),layer='below',row=nr,col=1)
    fig.add_trace(go.Scatter(x=[x0,x1,x1,x0,x0],y=[y0,y0,y1,y1,y0],mode='lines',line=dict(color=HOOP,width=4),showlegend=False,
        hovertemplate=f'One #{p["Bar_v"]:g} outer hoop<br>Nominal cross-section outline<extra></extra>'),row=nr,col=1)
    actual=x1-x0;limit=min(e.value('Sw_G'),e.value('Sw_L'))
    fig.add_annotation(x=p['b']/2,y=p['h']/2,text=f'Across-cap leg centers<br><b>{actual:.3f} in</b><br>Allowed ≤ {limit:.3f} in',showarrow=False,font=dict(color=RED if actual>limit else INK),row=nr,col=1)
    fig.update_xaxes(title='Across cap (in)',range=[-3,p['b']+3],constrain='domain',row=nr,col=1)
    fig.update_yaxes(title='Above underside (in)',range=[-3,p['h']+3],scaleanchor=f'x{nr}',scaleratio=1,row=nr,col=1)
    theme(fig,'HOOPS · side elevation sample and cross section',780 if same else 1080)
    fig.update_layout(showlegend=False,margin=dict(l=65,r=35,t=100,b=65),hovermode='closest')
    return fig


def results_figure(e):
    if actual_transverse(e.case):
        from .transverse_visuals import response_figure
        return response_figure(e)
    fig=make_subplots(rows=2,cols=2,subplot_titles=('Factored moment / resistance (kip-ft)','Service I steel stress (ksi)','Shear demand / resistance (kip)','Combined shear + torsion area (in²)'),vertical_spacing=.22,horizontal_spacing=.13)
    labels=['N · top','P · pile','B · between piles']
    for prefix,name,color in [('Mu_','Demand',MOMENT),('Mr_','Resistance',MOMENT_CAPACITY)]:fig.add_trace(go.Bar(x=labels,y=[e.value(prefix+z,'kip*ft') for z in 'NPB'],name='Moment '+name,marker_color=color),row=1,col=1)
    fig.add_trace(go.Bar(x=labels,y=[e.value('fs_I_'+z,'ksi') for z in 'NPB'],name='Service I stress',marker_color=TEAL),row=1,col=2)
    fig.add_hline(y=e.value('fs_I_limit','ksi'),line_color=AMBER,line_dash='dash',annotation_text='Stress limit',row=1,col=2)
    for prefix,name,color in [('Vu_','Shear demand',SHEAR),('Vr_','Shear resistance',SHEAR_CAPACITY)]:fig.add_trace(go.Bar(x=['Overall (G)','Lower-shear (L)'],y=[e.value(prefix+z,'kip') for z in 'GL'],name=name,marker_color=color),row=2,col=1)
    fig.add_trace(go.Bar(x=['Overall (G)','Lower-shear (L)'],y=[e.value('Acomb_'+z,'in^2') for z in 'GL'],name='Combined area required',marker_color=AMBER),row=2,col=2)
    fig.add_hline(y=e.value('Av','in^2'),line_color=INK,line_dash='dash',annotation_text='Area provided',row=2,col=2)
    theme(fig,('UNIFORM-CAGE REFERENCE · actual U/hoop checks are in D/C checks' if actual_transverse(e.case) else 'Current cage · capacity and stress response'),620);fig.update_layout(barmode='group',legend=dict(font=dict(size=10),orientation='h',y=-.16))
    return fig

def side_steel_html(e):
    info=side_reinforcement(e);p=e.case['inputs']
    supplied=f'{p["n_skin"]:g} #{p["Bar_skin"]:g} per side' if p['n_skin'] else 'no side bars'
    rule='required' if info['depth_required'] else 'not required'
    failures=info['zero_side_failures']
    outcome=('fails '+', '.join(html.escape(c.label) for c in failures)+'.' if failures else
             'passes the side-steel-related checks; other checks and cage fit still apply.')
    return (f'<p><b>Side-face reinforcement: {supplied}.</b> Depth-based skin rule: <b>{rule}</b>.<br>'
            'These bars also count toward shrinkage/temperature and longitudinal-tension checks, '
            'but are not included in flexural resistance.<br>'
            f'<b>Zero side bars, other inputs unchanged:</b> {outcome}</p>')


def spacing_html(e):
    if actual_transverse(e.case):
        from .transverse import scheduled_bars
        bars=scheduled_bars(e.case)
        pitches=[b['station_in']-a['station_in'] for a,b in zip(bars,bars[1:])]
        return ('<p><b>Actual transverse spacing:</b> '+(f'{len(bars)} bars; largest adjacent pitch {max(pitches):.3f} in, including transitions between runs.' if pitches else 'Enter at least two bars to check adjacent spacing.')+
            ' Every adjacent interval is checked in the D/C tab using the weaker two-leg area and larger adjacent shear demand. End development and force-zone applicability remain review items.</p>')
    """Expose the two independent ratios hidden in each combined spacing check."""
    rows=[]
    for zone,label in [('G','Overall (G)'),('L','Lower-shear interval (L)')]:
        along=e.value('s_'+zone);along_limit=e.value('s_allow_'+zone)
        across=e.value('S_leg');across_limit=e.value('Sw_'+zone)
        for direction,actual,limit in [('Along cap',along,along_limit),('Across cap between legs',across,across_limit)]:
            rows.append(f'<tr><td>{label}</td><td>{direction}</td><td>{actual:.3f}</td><td>{limit:.3f}</td><td>{actual/limit:.4f}</td></tr>')
    return '<h4>Hoop spacing · two different directions</h4><p>Each hoop-spacing check uses the larger of these two ratios. Along-cap hoop spacing and across-cap leg spacing are independent dimensions.</p><table class="cap-table"><tr><th>Zone</th><th>Direction</th><th>Actual (in)</th><th>Allowed (in)</th><th>Spacing utilization</th></tr>'+''.join(rows)+'</table>'

def ratios_figure(e):
    checks=[c for c in e.checks if isinstance(c.ratio,(float,int))]
    fig=go.Figure(go.Bar(x=[c.ratio for c in checks],y=[c.label for c in checks],orientation='h',
        marker_color=[check_color(c) for c in checks],showlegend=False,
        text=[f'{c.ratio:.3f}' for c in checks],textposition='outside',customdata=[[c.basis,c.status] for c in checks],hovertemplate='%{y}<br>Check ratio %{x:.4f}<br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>'))
    families=dict(check_family(c) for c in checks)
    if any(check_color(c)==RED for c in checks):families['Failed check']=RED
    for name,color in families.items():
        fig.add_trace(go.Scatter(x=[None],y=[None],mode='markers',marker=dict(color=color,size=10,symbol='square'),name=name,hoverinfo='skip'))
    fig.add_vline(x=1,line_color=AMBER,line_dash='dash',annotation_text='Check limit = 1')
    fig.update_yaxes(autorange='reversed');fig.update_xaxes(title='Check utilization · strength, minimum steel, spacing and service',range=[0,max(1.25,e.max_dc*1.15)])
    theme(fig,'All available numerical comparisons',max(750,len(checks)*28+60));fig.update_layout(margin=dict(l=240,r=55,t=65,b=100),legend=dict(y=-.08,orientation='h',font=dict(size=10)))
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
    fig.update_xaxes(title='Estimated steel (lb; span hooks included, laps/waste excluded)');fig.update_yaxes(title='Strength D/C' if dc_scope=='strength' else 'All-check utilization (includes detailing)',range=[0,1.08])
    return theme(fig,f'All {len(indices):,} filter matches · hover for candidate IDs and controlling checks',400)

def checks_html(e):
    rows=[]
    for c in e.checks:
        ratio=f'{c.ratio:.3f}' if isinstance(c.ratio,(int,float)) else str(c.ratio)
        color=RED if 'FAIL' in c.status else AMBER if 'PENDING' in c.status or 'PROVISIONAL' in c.status else TEAL
        rows.append(f'<tr><td>{html.escape(c.label)}</td><td style="color:{color}">{html.escape(c.status)}</td><td><b>{ratio}</b></td><td>{html.escape(c.basis)}</td></tr>')
    extra='<p><b>Additional notebook gates:</b> '+html.escape('; '.join(e.issues) if e.issues else 'Drawn cage passes the available numerical spacing and fit checks; pending checks remain listed above.')+'</p><p><b>Combined notebook status:</b> '+html.escape(e.status)+'</p>'
    return '<style>.cap-table{border-collapse:collapse;width:100%;font:12px Arial}.cap-table td,.cap-table th{padding:8px;border-bottom:1px solid #dce5ec;text-align:left}.cap-table th{background:#e7eef4;position:sticky;top:0}</style><p>Strength rows show D/C; maximum-spacing rows show actual / allowed; minimum-clearance rows show required / actual, and minimum-steel rows show required / provided. See each ratio basis.</p><table class="cap-table"><thead><tr><th>Check</th><th>Status</th><th>Check ratio</th><th>Ratio basis</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'+extra

def snapshot(e):
    """Static notebook output that also renders in GitHub's notebook preview."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle,Rectangle
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained');fig.patch.set_facecolor('#f7f9fc')
    ax=axes[0,0];p=e.case['inputs'];dv=BAR_DIAMETER[p['Bar_v']]
    ax.add_patch(Rectangle((0,0),p['b'],p['h'],facecolor='#edf2f6',edgecolor=INK,lw=2))
    shape_label='Reference transverse shape'
    if actual_transverse(e.case):
        from .transverse import bar_shape
        runs=e.case['transverse_detail']['runs']
        run=next((r for r in runs if r['kind']=='hoop'),runs[0] if runs else None)
        if run:
            pts=bar_shape(e,run)['points'];ax.plot([v[0] for v in pts],[v[1] for v in pts],color=HOOP,lw=2)
            shape_label='Actual '+run['id']+' · '+('closed hoop' if run['kind']=='hoop' else 'open-bottom U')
        else:shape_label='No actual transverse run entered'
    else:ax.add_patch(Rectangle((p['C_s']+dv/2,p['C_b']+dv/2),p['b']-2*p['C_s']-dv,p['h']-p['C_t']-p['C_b']-dv,fill=False,edgecolor=AMBER,lw=2))
    for b in bar_positions(e):ax.add_patch(Circle((b['x'],b['y']),b['diameter']/2,color=TEAL if b['kind']=='Skin' else BLUE))
    ax.set(xlim=(-3,p['b']+3),ylim=(-3,p['h']+3),aspect='equal',title='Between-pile section · '+shape_label,xlabel='Width (in)',ylabel='Depth (in)')
    ax=axes[0,1];length=e.value('L_cap')/12;depth=p['h']/12
    ax.add_patch(Rectangle((0,0),length,depth,facecolor='#edf2f6',edgecolor=BLUE,lw=2))
    for i in range(int(p['N_pile'])):
        x=e.value('E_CL')/12+i*p['S_pile'];ax.add_patch(Rectangle((x-p['D_pile']/24,-1.5),p['D_pile']/12,1.5+p['Pile_embed']/12,color=GREY))
    ax.set(xlim=(-1,length+1),ylim=(-2,depth+1),aspect='equal',title=f'Pile layout · {length:.3f} ft cap length',xlabel='Along cap (ft)')
    ax=axes[1,0];labels=list('NPB');xs=list(range(3))
    ax.bar([x-.18 for x in xs],[e.value('Mu_'+z,'kip*ft') for z in labels],width=.36,color=MOMENT,label='Demand')
    ax.bar([x+.18 for x in xs],[e.value('Mr_'+z,'kip*ft') for z in labels],width=.36,color=MOMENT_CAPACITY,label='Resistance')
    ax.set(xticks=xs,xticklabels=labels,ylabel='kip-ft',title='Flexural strength');ax.legend(frameon=False)
    ax=axes[1,1];ch=sorted((c for c in e.checks if isinstance(c.ratio,(int,float))),key=lambda c:c.ratio,reverse=True)[:7]
    ax.barh([c.label.replace(' — ',' / ') for c in ch],[c.ratio for c in ch],color=[check_color(c) for c in ch]);ax.invert_yaxis();ax.axvline(1,color=AMBER,ls='--');ax.set(xlim=(0,max(1.15,e.max_dc*1.1)),title='Seven largest check ratios (includes detailing)',xlabel='Check utilization')
    for ax in axes.flat:ax.spines[['top','right']].set_visible(False)
    strength=governing_check(e,'strength')
    fig.suptitle(f'C005 · Strength D/C {strength.ratio:.3f} | All-check utilization {e.max_dc:.3f}\n'+e.status,fontsize=14,color=INK)
    return fig
