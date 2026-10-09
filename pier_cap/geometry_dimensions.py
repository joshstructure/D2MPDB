"""Exact current cap dimensions with hoverable dimension traces."""
from .output_labels import numbered_figure, numbered_tables
import html
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .model import bar_positions


def number(value):
    return f'{value:.6f}'.rstrip('0').rstrip('.')


def geometry_dimensions(e):
    p=e.case['inputs'];length=e.value('L_cap');end=e.value('E_CL');diam=p['D_pile']
    centers=[end+i*p['S_pile']*12 for i in range(int(p['N_pile']))]
    values=[('length','Overall cap length',length),('width','Cap width',p['b']),
        ('depth','Cap depth',p['h']),('pile_width','Pile width / outside diameter',diam),
        ('left_center','Left cap end → first pile center',centers[0]),
        ('right_center','Last pile center → right cap end',length-centers[-1]),
        ('left_clear','Left cap end → first pile face (nominal)',centers[0]-diam/2),
        ('right_clear','Last pile face → right cap end (nominal)',length-centers[-1]-diam/2),
        ('center_spacing','Pile center-to-center spacing',p['S_pile']*12),
        ('clear_spacing','Clear gap between pile faces',p['S_pile']*12-diam),
        ('top_cover','Top concrete cover',p['C_t']),('bottom_cover','Bottom concrete cover',p['C_b']),
        ('side_cover','Side concrete cover',p['C_s']),('embedment','Pile embedment',p['Pile_embed']),
        ('pile_gap','Required pile-to-bar clear gap',p['C_pile'])]
    return dict(values={key:dict(label=label,inches=value,feet=value/12) for key,label,value in values},
        centers=centers,length=length,diameter=diam,
        piles=[dict(label=f'P{i}',center=x,left=x-diam/2,right=x+diam/2) for i,x in enumerate(centers,1)])


@numbered_tables('cap_dimensions', 'pile_stations')
def dimensions_html(e):
    data=geometry_dimensions(e);p=e.case['inputs']
    def table(headers,rows):
        return '<table class="cap-table"><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr>'+''.join(
            '<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'
    rows=[[v['label'],number(v['feet']),number(v['inches'])] for v in data['values'].values()]
    piles=[[v['label'],number(v['center']/12),number(v['left']/12),number(v['right']/12)] for v in data['piles']]
    note=('Current inputs differ from analyzed geometry: '+', '.join(e.stale)+'. Force diagrams retain the imported geometry.'
          if e.stale else 'Current cap dimensions match the recorded analysis geometry.')
    return ('<h3>Current cap dimensions</h3><p>Hover a dimension line or pile marker for its value in feet and inches. '
        'The tables show values to six decimal places, with trailing zeros omitted. Stations start at the left cap end.</p>'
        '<p>'+html.escape(note)+'</p>'+table(['Dimension','Feet','Inches'],rows)+
        '<details><summary>Pile center and face stations</summary>'+table(['Pile','Center (ft)','Left face (ft)','Right face (ft)'],piles)+'</details>'
        f'<p>Nominal drawn end-to-pile-face distance = entered edge clearance {number(p["E_clear"])} in '
        f'+ pile tolerance allowance {number(e.value("Tol_pile"))} in + extra end allowance {number(p["E_detail"])} in. '
        'These are model dimensions, not surveyed clearances. Pile outlines show the width/OD envelope; '
        'the below-cap pile length is schematic. Concrete cover and required pile-to-bar gap are input dimensions; '
        'see Live cage and D/C checks for actual reinforcement clearances.</p>')


@numbered_figure('cap_dimensions')
def dimensions_figure(e):
    p=e.case['inputs'];data=geometry_dimensions(e);length=data['length']/12;width=p['b']/12
    fig=make_subplots(rows=2,cols=1,vertical_spacing=.19,row_heights=[.48,.52],
        subplot_titles=('PLAN · current pile row and cap dimensions (ft)',
                        'CROSS SECTION AT A PILE · current dimensions (in)'))
    def outline(x,y,name,row,detail,color='#213649',fill=None):
        fig.add_trace(go.Scatter(x=x,y=y,mode='lines',name=name,showlegend=False,
            line=dict(color=color,width=2),fill='toself' if fill else None,fillcolor=fill,
            text=[detail]*len(x),hovertemplate='%{text}<extra></extra>'),row=row,col=1)
    def dimension(key,label,start,end,offset,row,*,vertical=False,unit='ft',text=True):
        xs=[start,(start+end)/2,end];ys=[offset]*3
        if vertical:xs,ys=ys,xs
        value=end-start;inches=value*12 if unit=='ft' else value
        detail=f'{label}<br>{number(inches/12)} ft = {number(inches)} in'
        fig.add_trace(go.Scatter(x=xs,y=ys,mode='lines+markers+text',name=label,showlegend=False,
            cliponaxis=False,
            line=dict(color='#167b75',width=1.5),marker=dict(size=[6,5,6],symbol='circle'),
            text=['',f'{value:.3f} {unit}' if text else '',''],textposition='top center' if not vertical else 'middle left',
            customdata=[detail]*3,meta=dict(dimension=key,inches=inches,feet=inches/12),
            hovertemplate='%{customdata}<extra></extra>'),row=row,col=1)

    outline([0,length,length,0,0],[0,0,width,width,0],'Cap plan',1,
        f'Cap length {number(data["length"]/12)} ft · width {number(p["b"])} in',fill='#f1f4f7')
    for pile in data['piles']:
        a,b=pile['left']/12,pile['right']/12;y0=(p['b']-p['D_pile'])/24;y1=(p['b']+p['D_pile'])/24
        detail=(f'{pile["label"]}: center {number(pile["center"]/12)} ft / {number(pile["center"])} in from left cap end'
                f'<br>Left face {number(a)} ft · right face {number(b)} ft<br>Width / OD {number(p["D_pile"])} in')
        outline([a,b,b,a,a],[y0,y0,y1,y1,y0],pile['label']+' envelope',1,detail,color='#71889a',fill='#dce5ec')
        fig.add_trace(go.Scatter(x=[pile['center']/12],y=[width/2],mode='markers+text',
            text=[pile['label']],textposition='top center',name=pile['label'],showlegend=False,
            marker=dict(size=8,color='#213649'),customdata=[detail],
            hovertemplate='%{customdata}<extra></extra>'),row=1,col=1)
    dimension('length','Overall cap length',0,length,width+1.5,1)
    chain=[0,*[x/12 for x in data['centers']],length]
    for i,(a,b) in enumerate(zip(chain,chain[1:])):
        label=('Left end to P1 center' if i==0 else f'P{len(data["centers"])} center to right end' if i==len(chain)-2 else f'P{i} to P{i+1} center spacing')
        dimension('center_chain_'+str(i),label,a,b,width+.6,1,text=len(chain)<15)
    for i,(a,b) in enumerate(zip(data['piles'],data['piles'][1:]),1):
        dimension('clear_gap_'+str(i),f'P{i} to P{i+1} clear face gap',a['right']/12,b['left']/12,-.65,1,text=len(chain)<15)
    dimension('left_clear','Nominal left end-to-pile-face gap',0,data['piles'][0]['left']/12,-1.45,1)
    dimension('right_clear','Nominal right pile-face-to-end gap',data['piles'][-1]['right']/12,length,-1.45,1)
    dimension('plan_width','Cap width',0,width,-.75,1,vertical=True)

    b,h=p['b'],p['h'];stub=max(8,h*.25)
    outline([0,b,b,0,0],[0,0,h,h,0],'Cap cross section',2,
        f'Cap width {number(b)} in · depth {number(h)} in',fill='#f1f4f7')
    left=(b-p['D_pile'])/2;right=(b+p['D_pile'])/2
    outline([left,right,right,left,left],[-stub,-stub,p['Pile_embed'],p['Pile_embed'],-stub],
        'Pile envelope at cap',2,f'Pile width / OD {number(p["D_pile"])} in<br>Embedment {number(p["Pile_embed"])} in; below-cap length schematic',
        color='#71889a',fill='#dce5ec')
    bars=bar_positions(e,'P')
    fig.add_trace(go.Scatter(x=[v['x'] for v in bars],y=[v['y'] for v in bars],mode='markers',name='Current bar centers',
        marker=dict(size=7,color='#2166ac'),showlegend=False,
        customdata=[[v['kind'],v['bar'],v['x'],v['y'],v['diameter']] for v in bars],
        hovertemplate='%{customdata[0]} · #%{customdata[1]}<br>Across cap: %{customdata[2]:.6f} in'
            '<br>Above underside: %{customdata[3]:.6f} in<br>Diameter: %{customdata[4]:.6f} in<extra></extra>'),row=2,col=1)
    dimension('section_width','Cap cross-section width',0,b,h+7,2,unit='in')
    dimension('section_depth','Cap depth',0,h,-8,2,vertical=True,unit='in')
    dimension('pile_width','Pile width / OD',left,right,-stub-5,2,unit='in')
    if p['Pile_embed']>0:dimension('embedment','Pile embedment',0,p['Pile_embed'],b+9,2,vertical=True,unit='in')
    fig.update_layout(template='plotly_white',height=880,margin=dict(l=55,r=45,t=70,b=45),
        font=dict(family='Arial',size=11,color='#213649'),hovermode='closest',hoverlabel=dict(namelength=-1),
        title='Current cap · hover dimensions for exact values',uirevision='cap-dimensions')
    fig.update_xaxes(title_text='From left cap end (ft)',range=[-1.8,length+1],row=1,col=1)
    fig.update_yaxes(range=[-2.2,width+2.2],visible=False,row=1,col=1)
    fig.update_xaxes(title_text='Across cap (in)',range=[-24,b+20],constrain='domain',row=2,col=1)
    fig.update_yaxes(visible=False,range=[-stub-12,h+14],scaleanchor='x2',scaleratio=1,row=2,col=1)
    return fig
