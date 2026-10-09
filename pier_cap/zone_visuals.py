"""A dimension band aligned with the plan/elevation's along-cap axis."""
import html
import plotly.graph_objects as go
from .transverse import enabled
from .transverse_zones import cap_zones,zone_occupancy,occupant_text,run_last_station


def _run_lanes(runs,length):
    """Leave room for each two-line station label, including short end runs."""
    lanes=[];placed=[]
    for run in sorted(runs,key=lambda r:(r['first_in'],r['id'])):
        center=(run['first_in']+run['end_in'])/2
        half=max((run['end_in']-run['first_in'])/2,length/14)
        left,right=center-half,center+half
        lane=next((i for i,end in enumerate(lanes) if end<left),len(lanes))
        if lane==len(lanes):lanes.append(right)
        else:lanes[lane]=right
        placed.append((run,lane))
    return placed,max(2,len(lanes))


def _add_run_dimensions(fig,placed,lane_count):
    for run,lane in placed:
        first,limit,last=run['first_in'],run['end_in'],run_last_station(run)
        y=1-(lane+.8)/lane_count;rid=run['id']
        color='#bd407d' if run['kind']=='pile_u' else '#7952a3'
        detail=[rid,first,limit,last,first/12,limit/12,last/12]
        hover=('<b>Run %{customdata[0]}</b><br>First: %{customdata[1]:.6f} in / %{customdata[4]:.6f} ft'
            '<br>Entered limit: %{customdata[2]:.6f} in / %{customdata[5]:.6f} ft'
            '<br>Actual last bar: %{customdata[3]:.6f} in / %{customdata[6]:.6f} ft<extra></extra>')
        fig.add_trace(go.Scatter(x=[first/12,(first+limit)/24,limit/12],y=[y]*3,xaxis='x3',yaxis='y3',
            mode='lines+markers+text',showlegend=False,name='Run '+rid+' first / limit',legendgroup='run-dimension:'+rid,
            line=dict(color=color,width=2),marker=dict(symbol='line-ns',size=[10,0,10]),
            text=['','<b>'+html.escape(rid)+f'</b><br>{first/12:.3f}–{limit/12:.3f} ft',''],
            textposition='top center',textfont=dict(size=10,color=color),cliponaxis=False,
            meta=dict(part='cap',dimension='run_limits',run_id=rid,start_in=first,end_in=limit,last_in=last),
            customdata=[detail]*3,hovertemplate=hover))
        fig.add_trace(go.Scatter(x=[last/12],y=[y],xaxis='x3',yaxis='y3',mode='markers',showlegend=False,
            name='Run '+rid+' actual last bar',legendgroup='run-dimension:'+rid,
            marker=dict(symbol='diamond-open',size=7,color=color,line=dict(width=2)),
            meta=dict(part='cap',dimension='run_last',run_id=rid,last_in=last),customdata=[detail],hovertemplate=hover))


def add_zone_dimensions(fig,e):
    zones=cap_zones(e);occupancy=zone_occupancy(e)
    runs=e.case.get('transverse_detail',{}).get('runs',[]) if enabled(e.case) else []
    placed,lane_count=_run_lanes(runs,e.value('L_cap'))
    run_height=50+44*lane_count if runs else 0
    drawing_height=fig.layout.height-fig.layout.margin.t-fig.layout.margin.b
    plot_height=drawing_height+160+run_height
    zone_bottom=(drawing_height+run_height+25)/plot_height
    zone_top=(drawing_height+run_height+105)/plot_height
    boundaries=sorted({v for z in zones for v in (z['left'],z['right'])})
    for zone in zones:
        left,right=zone['left'],zone['right']
        if right<=left:continue
        owners=occupancy[zone['key']] if enabled(e.case) else []
        ids=[o['id'] for o in owners]
        color='#bd407d' if zone['kind']=='pile_u' else '#7952a3'
        label=zone['label'].replace('Pile ','')
        text=html.escape(label)+('<br>'+html.escape(', '.join(ids)) if ids else '')
        detail=[zone['label'],left,right,left/12,right/12,right-left,(right-left)/12,
            '<br>'.join(html.escape(occupant_text(o)) for o in owners) or 'No active bars inside this zone']
        fig.add_trace(go.Scatter(x=[left/12,(left+right)/24,right/12],y=[.23]*3,xaxis='x2',yaxis='y2',
            mode='lines+markers+text',showlegend=False,name=zone['label']+' boundaries',
            legendgroup='zone:'+zone['key'],line=dict(color=color,width=2),
            marker=dict(symbol='line-ns',size=[10,0,10]),text=['',text if len(zones)<=21 else html.escape(label),''],
            textposition='top center',textfont=dict(size=10,color=color),cliponaxis=False,
            meta=dict(part='cap',dimension='zone_'+zone['key'],zone_key=zone['key'],start_in=left,end_in=right,run_ids=ids),
            customdata=[detail]*3,
            hovertemplate='<b>%{customdata[0]} · current geometry</b><br>Start: %{customdata[1]:.6f} in / %{customdata[3]:.6f} ft'
                '<br>Stop: %{customdata[2]:.6f} in / %{customdata[4]:.6f} ft'
                '<br>Zone length: %{customdata[5]:.6f} in / %{customdata[6]:.6f} ft<br>%{customdata[7]}<extra></extra>'))
    for station in boundaries:
        fig.add_shape(name='part:cap',type='line',xref='x',yref='paper',x0=station/12,x1=station/12,y0=0,y1=zone_bottom+.23*(zone_top-zone_bottom),
            line=dict(color='#b8b0c1',width=1,dash='dot'),layer='below')
    fig.update_layout(height=fig.layout.height+160+run_height,
        yaxis=dict(domain=[0,drawing_height/plot_height]),
        yaxis2=dict(domain=[zone_bottom,zone_top],range=[0,1],visible=False,fixedrange=True,anchor='x2'),
        xaxis2=dict(matches='x',anchor='y2',side='top',range=list(fig.layout.xaxis.range),
            tickmode='array',tickvals=[v/12 for v in boundaries],
            ticktext=[f'{v/12:.3f}'.rstrip('0').rstrip('.') for v in boundaries],tickangle=-45,
            ticks='outside',tickfont=dict(size=10),showgrid=False,zeroline=False,showline=True,linecolor='#b8b0c1'))
    fig.add_annotation(name='part:cap',xref='paper',yref='paper',x=0,y=1,xanchor='left',showarrow=False,
        text='Geometry zones · ft from left cap end · hover for inches and occupied runs',
        font=dict(size=11,color='#213649'))
    if runs:
        run_bottom=(drawing_height+10)/plot_height;run_top=(drawing_height+10+44*lane_count)/plot_height
        fig.update_layout(yaxis3=dict(domain=[run_bottom,run_top],range=[0,1],visible=False,fixedrange=True,anchor='x3'),
            xaxis3=dict(matches='x',anchor='y3',range=list(fig.layout.xaxis.range),visible=False))
        _add_run_dimensions(fig,placed,lane_count)
        fig.add_annotation(name='part:cap',xref='paper',yref='paper',x=0,y=(drawing_height+run_height-10)/plot_height,
            xanchor='left',showarrow=False,text='Run first → entered limit · feet · ◇ actual last bar · hover for exact inches / feet',
            font=dict(size=11,color='#213649'))
    return fig
