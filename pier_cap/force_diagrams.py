"""Signed cap-force profiles from verified XML member ends, on source geometry."""
from collections import defaultdict
from itertools import combinations
import html
import json
import math

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .fbmp import _moment_at
from .force_audit import state_label
from .plotly_compat import FigureWidget


MOMENT = '#2166ac'
SHEAR = '#8250a0'
TORSION = '#cc7919'


def _roots(a, b, c):
    if abs(a) < 1e-10:
        return [] if abs(b) < 1e-10 else [-c/b]
    d = b*b-4*a*c
    return [] if d < 0 else [(-b-math.sqrt(d))/(2*a), (-b+math.sqrt(d))/(2*a)]


def cap_profiles(case):
    """Retain member sides/jumps and sample recovered moment extrema exactly.

    All combinations share station samples, including envelope intersections.
    Diagrams never substitute trial geometry or edited scalar load inputs.
    """
    audit = case['analysis'].get('xml_audit', {})
    ends = audit.get('end_records', [])
    if not ends:
        raise ValueError('Upload and apply a solved FBMP XML to plot forces along the cap. Scalar workbook envelopes do not define a force diagram.')
    grouped = defaultdict(dict)
    for record in ends:
        key = (str(record['combination']), str(record['element']))
        if record['side'] in grouped[key]:
            raise ValueError('Duplicate member-end records in the saved XML audit.')
        grouped[key][record['side']] = record
    members = defaultdict(dict)
    for (combo, element), pair in grouped.items():
        if set(pair) != {'I','J'}:
            raise ValueError('Incomplete member-end records in the saved XML audit; reimport XML.')
        i,j = pair['I'],pair['J']
        length = (j['x_in']-i['x_in'])/12
        if length <= 0:
            raise ValueError('Reversed cap stations; reimport a supported XML.')
        residual = abs(j['moment']-i['moment']-(i['shear']+j['shear'])*length/2)
        bound = .02+.01*length+max(abs(i['shear']),abs(j['shear']))*.02/12
        if residual > bound:
            raise ValueError('Saved forces fail member equilibrium; reimport XML before plotting.')
        if abs(abs(i['torque'])-abs(j['torque'])) > .025:
            raise ValueError('Varying member torsion needs a verified torque distribution before plotting.')
        members[element][combo] = (i,j,length)
    combo_ids = list(dict.fromkeys(str(r['combination']) for r in ends))
    if any(set(group) != set(combo_ids) for group in members.values()):
        raise ValueError('Combinations do not contain matching cap members; reimport XML.')
    x0 = min(r['x_in'] for r in ends)
    profiles = {combo: [] for combo in combo_ids}
    for element, group in sorted(members.items(),key=lambda item:next(iter(item[1].values()))[0]['x_in']):
        i0,j0,_ = next(iter(group.values()))
        if any(abs(i['x_in']-i0['x_in']) > 1e-8 or abs(j['x_in']-j0['x_in']) > 1e-8 for i,j,_ in group.values()):
            raise ValueError('Member coordinates change between combinations.')
        stations = {n/24 for n in range(25)}
        polynomials = []
        for i,j,length in group.values():
            # M(t) = a*t² + b*t + c, following the verified import convention.
            a = -.5*(i['shear']-j['shear'])*length
            b = j['moment']-i['moment']-a
            polynomials.append((a,b,i['moment']))
            if abs(a) > 1e-10:
                stations.add(-b/(2*a))
        for p,q in combinations(polynomials,2):
            stations.update(_roots(*(u-v for u,v in zip(p,q))))
        for (i,j,_),(k,l,_) in combinations(group.values(),2):
            stations.update(_roots(0,(j['shear']-i['shear'])-(l['shear']-k['shear']),i['shear']-k['shear']))
        for x in audit.get('pile_centers_in', []):
            for offset in (-case['analysis']['geometry']['D_pile']/2,0,case['analysis']['geometry']['D_pile']/2):
                stations.add((x+offset-i0['x_in'])/(j0['x_in']-i0['x_in']))
        stations = sorted(t for t in stations if 0 <= t <= 1)
        for combo,(i,j,length) in group.items():
            for t in stations:
                end = i if t == 0 else j if t == 1 else None
                label = (f'{end["side"]}-end · raw M3 {end["raw_moment_3"]:.2f} kip-ft'
                         if end is not None else 'Recovered within member')
                profiles[combo].append(dict(x=(i['x_in']-x0)/12+t*length,
                    moment=_moment_at(i['moment'],j['moment'],i['shear'],j['shear'],length,t),
                    shear=i['shear']+(j['shear']-i['shear'])*t,
                    torque=abs(i['torque'])+(abs(j['torque'])-abs(i['torque']))*t,
                    combination=combo,state=i['state'],element=element,station=label))
            # Never draw a sloping connection across a nodal jump or missing span.
            profiles[combo].append(None)
    return profiles


def diagram_notice(case):
    audit = case['analysis'].get('xml_audit', {})
    if not audit.get('end_records'):
        return 'Upload and apply a solved FBMP XML to see force diagrams over the analyzed cap and pile layout.'
    changed = [k for k,v in case['analysis']['geometry'].items() if not math.isclose(case['inputs'][k],v,abs_tol=1e-8)]
    changed += [k for k,r in audit.get('governing',{}).items()
                if not math.isclose(case['inputs'][k],r['adopted'],abs_tol=1e-8)]
    base = ('Diagrams show the imported analysis. Changing steel or trial dimensions does not rerun FB-MultiPier. '
            'Moment: positive = bottom tension; negative = top tension. J-end signs are converted. '
            'Shear keeps its diagram sign; torsion shows magnitude. Curves retain separate member sides at jumps. '
            'Pile lengths are schematic; horizontal stations and cap depth follow the analyzed model.')
    if changed:
        base = 'CURRENT INPUTS DIFFER FROM PLOTTED ANALYSIS: '+', '.join(changed)+'. '+base
    return base


def cap_force_figure(case, *, show_resistance=False, evaluation=None):
    profiles = cap_profiles(case)
    audit = case['analysis']['xml_audit']
    geometry = case['analysis']['geometry']
    states = {combo:next(p['state'] for p in points if p) for combo,points in profiles.items()}
    strength = [k for k,state in states.items() if state.startswith('STRENGTH-')]
    modes = [('All strength · envelope', strength)]
    modes += [(state_label(state)+' · envelope',[k for k,v in states.items() if v == state])
              for state in dict.fromkeys(states.values())]
    modes += [(f'{state_label(state)} · combo {combo}',[combo]) for combo,state in states.items()]
    fig = make_subplots(rows=4,cols=1,shared_xaxes=True,vertical_spacing=.065,
        row_heights=[.30,.24,.20,.26],subplot_titles=(
            'Moment · positive = bottom tension','Shear · signed','Torsion · magnitude','Analyzed cap, pile centers and bearings'))
    trace_groups = []
    for mi,(label, combos) in enumerate(modes):
        start = len(fig.data)
        for field,row,color,unit in [('moment',1,MOMENT,'kip-ft'),('shear',2,SHEAR,'kip'),('torque',3,TORSION,'kip-ft')]:
            kinds = ['upper','lower'] if len(combos)>1 and field != 'torque' else ['upper']
            for kind in kinds:
                x=[];y=[];custom=[]
                for records in zip(*(profiles[k] for k in combos)):
                    if records[0] is None:
                        x.append(None);y.append(None);custom.append(['','','','']);continue
                    record = (max if kind == 'upper' else min)(records,key=lambda r:r[field])
                    x.append(record['x']);y.append(record[field])
                    custom.append([state_label(record['state']),record['combination'],record['element'],record['station']])
                name = {'moment':'Moment','shear':'Shear','torque':'|T|'}[field]
                if len(combos)>1:name+=' · '+('maximum' if field == 'torque' else kind)
                fig.add_trace(go.Scatter(x=x,y=y,customdata=custom,name=name,visible=mi==0,
                    mode='lines',connectgaps=False,line=dict(color=color,width=2,dash='dash' if kind=='lower' else 'solid'),
                    hovertemplate=f'x = %{{x:.3f}} ft from left cap edge<br>{name} = %{{y:.2f}} {unit}'
                        '<br>%{customdata[0]} · combo %{customdata[1]} · member %{customdata[2]}'
                        '<br>%{customdata[3]}<extra></extra>'),row=row,col=1)
        trace_groups.append(list(range(start,len(fig.data))))
    force_count = len(fig.data)
    resistance_indices=[];resistance_note=''
    if show_resistance:
        from .model import evaluate
        from .force_resistance import resistance_traces
        try:
            traces,resistance_note=resistance_traces(evaluation if evaluation is not None else evaluate(case))
            for trace,row in traces:
                resistance_indices.append(len(fig.data))
                fig.add_trace(trace,row=row,col=1)
        except (ValueError,KeyError,TypeError,ZeroDivisionError,OverflowError) as exc:
            resistance_note='RESISTANCE OVERLAY UNAVAILABLE: '+str(exc)+'. Correct the current inputs; imported demand curves are retained.'
    x0 = min(r['x_in'] for r in audit['end_records'])
    length = (max(r['x_in'] for r in audit['end_records'])-x0)/12
    depth=geometry['h']/12
    fig.add_shape(type='rect',x0=0,x1=length,y0=0,y1=depth,fillcolor='#eef2f6',line=dict(color='#213649',width=2),row=4,col=1)
    stub = max(1.5,depth*.7)
    pile_x = [(x-x0)/12 for x in audit['pile_centers_in']]
    for i,x in enumerate(pile_x,1):
        fig.add_shape(type='rect',x0=x-geometry['D_pile']/24,x1=x+geometry['D_pile']/24,
            y0=-stub,y1=0,fillcolor='#b8c7d1',line=dict(color='#627386'),row=4,col=1)
        fig.add_annotation(x=x,y=-stub*.6,text=f'P{i}',showarrow=False,row=4,col=1)
        for row in (1,2,3):
            fig.add_vline(x=x,line=dict(color='#b8c7d1',dash='dot',width=1),row=row,col=1)
    bearing_x=[(x-x0)/12 for x in audit.get('bearing_stations_in',[])]
    fig.add_trace(go.Scatter(x=bearing_x,y=[depth]*len(bearing_x),mode='markers+text',
        text=[f'B{i}' for i in range(1,len(bearing_x)+1)],textposition='top center',
        name='Bearings',marker=dict(symbol='triangle-down',size=13,color='#213649'),
        hovertemplate='Bearing at x = %{x:.3f} ft<extra></extra>'),row=4,col=1)
    fig.add_trace(go.Scatter(x=pile_x,y=[0]*len(pile_x),mode='markers',name='Pile centers',
        marker=dict(size=7,color='#627386'),hovertemplate='Pile center x = %{x:.3f} ft<extra></extra>'),row=4,col=1)
    def title(label, is_strength):
        detail=f'Analyzed cap {geometry["b"]:g} × {geometry["h"]:g} in · {length:.3f} ft long'
        if resistance_indices:
            p=case['inputs']
            detail+=(f' · Current resistance section {p["b"]:g} × {p["h"]:g} in' if is_strength else
                     ' · Strength resistance overlay hidden for service demands')
        elif resistance_note:detail+=' · Resistance overlay unavailable; see notice'
        return f'{html.escape(label)}<br><sup>{detail}</sup>'
    buttons=[]
    for (label,combos), group in zip(modes,trace_groups):
        is_strength=bool(combos) and all(states[k].startswith('STRENGTH-') for k in combos)
        visible=[i in group if i<force_count else is_strength if i in resistance_indices else True for i in range(len(fig.data))]
        buttons.append(dict(label=label,method='update',args=[{'visible':visible},
            {'title.text':title(label,is_strength),'yaxis.autorange':True,'yaxis2.autorange':True,'yaxis3.autorange':True}]))
    for trace,visible in zip(fig.data,buttons[0]['args'][0]['visible']):trace.visible=visible
    fig.update_layout(template='plotly_white',autosize=True,width=None,height=910,margin=dict(l=65,r=20,t=140,b=90),
        title=dict(text=title(modes[0][0],bool(strength)),font=dict(size=16),y=.99),
        font=dict(family='Arial',size=11,color='#213649'),hovermode='closest',
        legend=dict(orientation='h',y=-.085,font=dict(size=10)),
        updatemenus=[dict(buttons=buttons,direction='down',x=0,y=1.13,xanchor='left',yanchor='top',showactive=True)],
        uirevision=audit.get('sha256','xml'),meta=dict(resistance_notice=resistance_note))
    if show_resistance:fig.update_layout(height=1000,margin=dict(b=145))
    for row,title_y in [(1,'M (kip-ft)'),(2,'V (kip)'),(3,'|T| (kip-ft)')]:
        fig.update_yaxes(title_text=title_y,zeroline=True,zerolinecolor='#7e8993',row=row,col=1)
    fig.update_yaxes(visible=False,range=[-stub*1.2,depth*1.6],row=4,col=1)
    fig.update_xaxes(range=[-.3,length+.3],showspikes=True,spikemode='across',spikesnap='cursor')
    fig.update_xaxes(title_text='Distance from left cap edge (ft) · pile lengths schematic',row=4,col=1)
    return fig


class ForceDiagramPanel:
    """Keep the selected force view while the user changes reinforcement."""
    def __init__(self):
        import ipywidgets as W
        self.notice=W.HTML()
        self.show_resistance=W.Checkbox(value=False,description='Show current resistances',indent=False,
            layout=W.Layout(width='260px'))
        self.show_resistance.observe(self._toggle_resistance,names='value')
        self.resistance_notice=W.HTML()
        self.output=W.VBox(layout=W.Layout(width='100%',min_width='0',align_items='stretch'))
        self.ui=W.VBox([self.show_resistance,self.notice,self.resistance_notice,self.output],
            layout=W.Layout(width='100%',min_width='0',align_items='stretch',max_height='1250px',overflow='auto'))
        self.figure=None
        self._key=None
        self._resistance_key=None
        self._case=None

    def _toggle_resistance(self,change):
        if self._case is not None:self.refresh(self._case)

    def refresh(self,case,evaluation=None):
        self._case=case
        audit=case['analysis'].get('xml_audit',{})
        self.notice.value='<p>'+html.escape(diagram_notice(case))+'</p>'
        key=(audit.get('sha256'),id(audit.get('end_records')))
        self.show_resistance.disabled=not bool(audit.get('end_records'))
        resistance_key=json.dumps({k:v for k,v in case.items() if k!='analysis'},sort_keys=True) if self.show_resistance.value else None
        if key == self._key and resistance_key == self._resistance_key and (self.figure is not None or not audit.get('end_records')):return
        same_source=key == self._key
        if not audit.get('end_records'):
            if self.figure is not None:self.figure.close()
            self.figure=None;self.output.children=[];self.resistance_notice.value=''
            self._key=key;self._resistance_key=resistance_key
            return
        try:
            fresh=cap_force_figure(case,show_resistance=self.show_resistance.value,evaluation=evaluation)
            self.resistance_notice.value='<p>'+html.escape(fresh.layout.meta['resistance_notice'])+'</p>' if self.show_resistance.value else ''
            if self.figure is None:self.figure=FigureWidget(fresh)
            else:
                active=(self.figure.layout.updatemenus[0].active or 0) if same_source else 0
                active=max(0,min(active,len(fresh.layout.updatemenus[0].buttons)-1))
                button=fresh.layout.updatemenus[0].buttons[active]
                for trace,visible in zip(fresh.data,button.args[0]['visible']):trace.visible=visible
                fresh.update_layout(button.args[1]);fresh.layout.updatemenus[0].active=active
                if same_source:
                    for axis in ('xaxis','xaxis2','xaxis3','xaxis4'):
                        fresh.layout[axis].range=self.figure.layout[axis].range
                with self.figure.batch_update():
                    self.figure.data=[]
                    self.figure.add_traces(fresh.data)
                    self.figure.layout=fresh.layout
            self.output.children=[self.figure]
            self._key=key;self._resistance_key=resistance_key
        except (ValueError,KeyError,TypeError) as exc:
            if self.figure is not None:self.figure.close()
            self.figure=None;self.output.children=[];self.resistance_notice.value=''
            self.notice.value='<p><b>Force diagram unavailable:</b> '+html.escape(str(exc))+'</p>'

    def close(self):
        if self.figure is not None:self.figure.close()
        self.ui.close()
