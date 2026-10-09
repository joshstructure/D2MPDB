"""A dimension band aligned with the plan/elevation's along-cap axis."""
import html
import plotly.graph_objects as go
from .transverse import enabled
from .transverse_zones import cap_zones,zone_occupancy,occupant_text


def add_zone_dimensions(fig,e):
    zones=cap_zones(e);occupancy=zone_occupancy(e)
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
        fig.add_shape(name='part:cap',type='line',xref='x',yref='paper',x0=station/12,x1=station/12,y0=0,y1=.695,
            line=dict(color='#b8b0c1',width=1,dash='dot'),layer='below')
    fig.update_layout(height=fig.layout.height+160,
        yaxis=dict(domain=[0,.59]),
        yaxis2=dict(domain=[.65,.84],range=[0,1],visible=False,fixedrange=True,anchor='x2'),
        xaxis2=dict(matches='x',anchor='y2',side='top',range=list(fig.layout.xaxis.range),
            tickmode='array',tickvals=[v/12 for v in boundaries],
            ticktext=[f'{v/12:.3f}'.rstrip('0').rstrip('.') for v in boundaries],tickangle=-45,
            ticks='outside',tickfont=dict(size=10),showgrid=False,zeroline=False,showline=True,linecolor='#b8b0c1'))
    fig.add_annotation(name='part:cap',xref='paper',yref='paper',x=0,y=.985,xanchor='left',showarrow=False,
        text='Zone start / stop · ft from left cap end · hover for exact inches and occupied runs',
        font=dict(size=11,color='#213649'))
    return fig
