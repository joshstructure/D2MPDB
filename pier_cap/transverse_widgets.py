"""One persistent, numbered card per physical transverse run."""
from copy import deepcopy
import html
import math
import ipywidgets as W
from .transverse import empty_detail,enabled,shape_parameters,suggested_detail,validate_detail,development_current,development_fingerprint
from .widget_compat import Accordion
from .transverse_zones import zone_runs,new_zone_run


def _layout():return W.Layout(width='calc(100% - 4px)',min_width='0')


class RunCard:
    """All run inputs live here; repainting never replaces an existing card."""
    def __init__(self,panel,rid):
        self.panel=panel;self.rid=rid;self.controls={};self.widgets=[]
        def add(name,widget):self.controls[name]=widget;self.widgets.append(widget);return widget
        def number(name,label,field=None,scale=1):
            widget=add(name,W.FloatText(description=label,continuous_update=False,
                style={'description_width':'105px'},layout=_layout()))
            widget.observe(lambda change:panel._zone_edited(rid,field or name,change,scale),names='value')
            return widget
        label=add('label',W.HTML())
        size=add('bar',W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],description='Size',style={'description_width':'105px'},layout=_layout()))
        size.observe(lambda c:panel._zone_edited(rid,'bar',c),names='value')
        pitch=number('pitch','c/c (in)','pitch_in')
        locations=[number('first_in','First (in)'),number('first_ft','First (ft)','first_in',12),
                   number('end_in','Last limit (in)'),number('end_ft','Last limit (ft)','end_in',12)]
        info=add('info',W.HTML(layout=W.Layout(min_height='42px')))
        error=add('error',W.HTML(layout=W.Layout(min_height='24px')))
        view=add('view',W.Button(description=f'View {rid} section',icon='eye',layout=_layout()))
        view.on_click(lambda _:panel._select_run(rid))
        kind=add('kind',W.Dropdown(options=[('Closed hoop','hoop'),('Open-bottom U','pile_u')],description='Shape',style={'description_width':'105px'},layout=_layout()))
        shear=add('zone',W.Dropdown(options=[('Overall (G)','G'),('Lower-shear (L)','L')],description='Shear basis',style={'description_width':'105px'},layout=_layout()))
        angle=add('end_angle',W.Dropdown(options=[('90° inward',90),('135° inward',135),('180° return',180),('Straight',0)],description='U ends',style={'description_width':'105px'},layout=_layout()))
        for name,widget in [('kind',kind),('zone',shear),('end_angle',angle)]:
            widget.observe(lambda change,field=name:panel._zone_edited(rid,field,change),names='value')
        shape=[number(name,title) for name,title in [('inside_diameter_in','Bend ID (in)'),('tail_in','End tail (in)'),
            ('end_raise_in','Raise ends (in)'),('side_inset_in','Inset legs (in)')]]
        help_text=add('help',W.HTML('<small>U-bars are open downward. Raise ends is above bottom cover; inset moves legs inward. '
            'Bend and tail dimensions describe the drawing. Record the separate development / closure check below.</small>'))
        basis=add('development_basis',W.Textarea(description='Detail ref.',placeholder='Drawing / calculation reference',continuous_update=False,
            style={'description_width':'70px'},layout=W.Layout(width='calc(100% - 4px)',height='70px')))
        confirm=add('development_confirmed',W.Checkbox(description='Development / closure checked',indent=False,layout=_layout()))
        for name,widget in [('development_basis',basis),('development_confirmed',confirm)]:
            widget.observe(lambda change,field=name:panel._zone_edited(rid,field,change),names='value')
        split=add('split',W.Button(description=f'Split {rid}',icon='columns',layout=_layout()))
        split.on_click(lambda _:panel._split_run(rid))
        remove=add('remove',W.Button(description=f'Remove {rid}',icon='trash',layout=_layout()))
        remove.on_click(lambda _:panel._remove_run(rid))
        details=W.VBox([kind,shear,angle,*shape,help_text,basis,confirm,split,remove])
        advanced=add('details',Accordion(children=[details]));advanced.set_title(0,f'{rid} · shape and development');advanced.selected_index=None
        self.widgets.append(details)
        self.ui=W.VBox([label,size,pitch,*locations,info,view,advanced,error],layout=W.Layout(min_width='0'))

    def sync(self,run,region,active,selected,case):
        c=self.controls;shape=shape_parameters(run)
        values={**run,**shape,'pitch':run['pitch_in'],'first_ft':run['first_in']/12,'end_ft':run['end_in']/12,
                'development_basis':run.get('development_basis',''),'development_confirmed':development_current(case,run)}
        for name,value in values.items():
            if name in c and hasattr(c[name],'disabled'):
                c[name].value=value;c[name].disabled=not active
        count=math.floor((run['end_in']-run['first_in'])/run['pitch_in']+1e-9)+1
        last=run['first_in']+(count-1)*run['pitch_in']
        color='#bd407d' if run['kind']=='pile_u' else '#7952a3'
        c['label'].value=f'<b style="font-size:16px;color:{color}">Run {html.escape(run["id"])}</b><br><small>{html.escape(region)} · '+('Open-bottom U-bars' if run['kind']=='pile_u' else 'Closed hoops')+'</small>'
        c['info'].value=f'<small>{count} {"bar" if count==1 else "bars"}<br>Actual last: {last:g} in / {last/12:g} ft</small>'
        c['view'].button_style='info' if selected else '';c['view'].disabled=not active
        c['split'].disabled=not active or count<2;c['remove'].disabled=not active
        c['error'].value=''

    def close(self):
        for widget in self.widgets:widget.close()
        self.ui.close()


class TransversePanel:
    def __init__(self,owner):
        self.owner=owner;self.busy=False;self.zone_controls={};self._cards={};self._zones={};self._empty_zones={};self._selected_run_id=None
        self.active=W.Checkbox(description='Use actual transverse layout',indent=False)
        self.generate=W.Button(description='Create starting layout',icon='plus',layout=W.Layout(width='210px'))
        self.add=W.Button(description='Add custom run',icon='plus')
        self.status=W.HTML(layout=W.Layout(min_height='32px'));self.zone_notice=W.HTML()
        self.zone_grid=W.GridBox(layout=W.Layout(width='100%',grid_template_columns='repeat(auto-fit, minmax(255px, 1fr))',grid_gap='10px'))
        self.general=Accordion(children=[owner.hoop_reference_inputs]);self.general.set_title(0,'General hoop reference inputs and spacing assumptions');self.general.selected_index=None
        self.ui=W.VBox([W.HTML('<h3>Actual hoops and pile U-bars · by zone</h3><p><b>Run numbers match the elevation labels and plot legends.</b> '
            'Each run is edited only in its card. Changes apply on Enter or leaving the field. '
            'Locations are from the <b>left cap end</b>; inches and feet are linked. The last-bar limit keeps the entered pitch; the actual last bar is shown below. '
            'Use <b>View run section</b> to inspect that shape above. Expand its card for bends, shear basis and development records.</p>'),
            W.HBox([self.active,self.generate,self.add],layout=W.Layout(flex_flow='row wrap')),self.zone_grid,self.zone_notice,self.status,self.general],layout=W.Layout(width='100%',min_width='0'))
        self.active.observe(self._toggle,names='value');self.generate.on_click(self._generate);self.add.on_click(self._add)
        self.sync()

    @property
    def selected_run_id(self):return self._selected_run_id

    def sync(self):
        prior=self.busy;self.busy=True
        try:
            detail=self.owner.case.get('transverse_detail',empty_detail());runs=detail['runs']
            self.active.value=detail['enabled'];self.generate.disabled=bool(runs)
            if self._selected_run_id not in [r['id'] for r in runs]:self._selected_run_id=runs[0]['id'] if runs else None
        finally:self.busy=prior

    def _zone_box(self,key):
        if key not in self._zones:
            header=W.HTML();box=W.VBox(layout=W.Layout(border='1px solid #b7bec8',padding='8px',min_width='0'))
            self._zones[key]=(header,box)
        return self._zones[key]

    def _empty_card(self,z,e):
        key=z['key']
        if key not in self._empty_zones:
            size=W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],value=int(e.case['inputs']['Bar_v']),description='Size',layout=_layout())
            pitch=W.FloatText(value=e.case['inputs']['s_G'],description='c/c (in)',continuous_update=False,layout=_layout())
            note=W.HTML('<small>No run entered. Choose size / spacing and add this zone.</small>')
            button=W.Button(description='Add zone run',icon='plus',layout=_layout());button.on_click(lambda _:self._add_zone(key))
            self._empty_zones[key]=dict(bar=size,pitch=pitch,note=note,button=button,ui=W.VBox([note,size,pitch,button]))
        c=self._empty_zones[key];c['button'].disabled=z['right']<=z['left']
        return c['ui']

    def sync_zones(self,e):
        self.zone_grid.layout.display='';zones,groups,custom=zone_runs(e)
        runs=e.case.get('transverse_detail',empty_detail())['runs'];ids={r['id'] for r in runs}
        prior=self.busy;self.busy=True
        try:
            for rid in set(self._cards)-ids:
                self._cards.pop(rid).close();self.zone_controls.pop(rid)
            for run in runs:
                rid=run['id']
                if rid not in self._cards:
                    self._cards[rid]=RunCard(self,rid);self.zone_controls[rid]=self._cards[rid].controls
            boxes=[]
            regions=[(z,groups[z['key']]) for z in zones]
            if custom:regions.append((dict(key='custom',label='Custom / crossing runs',kind='hoop'),custom))
            for z,group in regions:
                header,box=self._zone_box(z['key']);numbers=', '.join(r['id'] for r in group)
                header.value='<b>'+html.escape(z['label'])+('</b> · <b>'+html.escape(numbers) if numbers else '')+'</b>'
                box.layout.border='1px solid '+('#bd407d' if z['kind']=='pile_u' else '#7952a3')
                children=[header]
                for run in group:
                    card=self._cards[run['id']];card.sync(run,z['label'],enabled(e.case),run['id']==self.selected_run_id,e.case)
                    children.append(card.ui)
                if not group:children.append(self._empty_card(z,e))
                if box.children!=tuple(children):box.children=children
                boxes.append(box)
            if self.zone_grid.children!=tuple(boxes):self.zone_grid.children=boxes
            notes=[]
            if not enabled(e.case):notes.append('Actual layout is off. Enable it to edit saved runs and draw their bars.')
            if custom:notes.append('Runs crossing zone boundaries keep their numbered cards in Custom / crossing runs.')
            notes.append('Geometry changes never move saved bar stations. Review adjoining-run spacing and the D/C checks.')
            self.zone_notice.value='<p>'+html.escape(' '.join(notes))+'</p>'
        finally:self.busy=prior

    def _zone_edited(self,rid,field,change,scale=1):
        if self.busy or self.owner.busy:return
        def perform():
            detail=deepcopy(self.owner.case['transverse_detail']);run=next(r for r in detail['runs'] if r['id']==rid)
            value=change['new']*scale if isinstance(change['new'],(int,float)) and not isinstance(change['new'],bool) else change['new']
            if field in ('end_angle','inside_diameter_in','tail_in','end_raise_in','side_inset_in'):
                run['shape']=shape_parameters(run);run['shape'][field]=value
            else:run[field]=value
            if field=='development_confirmed' and value:
                run['development_fingerprint']=development_fingerprint(dict(self.owner.case,transverse_detail=detail),run)
            else:run['development_confirmed']=False;run.pop('development_fingerprint',None)
            self._commit(detail,selected=rid)
        if not self._attempt(perform):
            if self.owner.current:self.sync_zones(self.owner.current)
            if rid in self.zone_controls:self.zone_controls[rid]['error'].value=self.status.value

    def _select_run(self,rid):
        self._selected_run_id=rid
        if self.owner.current:
            self.sync_zones(self.owner.current);self.owner.refresh_sections()

    def _commit(self,detail,selected=None):
        case=deepcopy(self.owner.case);case['transverse_detail']=detail;validate_detail(case)
        self.owner.case=case
        if selected:self._selected_run_id=selected
        self.sync();self.owner._update_search_basis();self.owner.refresh();self.owner._notify_case_change()
        self.status.value='<p>Layout applied. Views and exports use these stations.</p>' if detail['enabled'] else '<p>Actual layout disabled; saved runs retained.</p>'

    def _attempt(self,callback):
        try:callback();return True
        except Exception as exc:
            self.status.value='<p style="color:#bb3e39"><b>Not applied:</b> '+html.escape(str(exc))+'</p>';return False

    def _toggle(self,change):
        if self.busy or self.owner.busy:return
        detail=deepcopy(self.owner.case.get('transverse_detail',empty_detail()));detail['enabled']=change['new']
        self._attempt(lambda:self._commit(detail))

    def _generate(self,_):
        from .model import evaluate
        self._attempt(lambda:self._commit(suggested_detail(evaluate(self.owner.case))))

    def _add_zone(self,key):
        def perform():
            from .model import evaluate
            e=self.owner.current or evaluate(self.owner.case);c=self._empty_zones[key]
            run=new_zone_run(e,key,c['bar'].value,c['pitch'].value)
            detail=deepcopy(self.owner.case.get('transverse_detail',empty_detail()));detail['enabled']=True;detail['runs'].append(run)
            self._commit(detail,selected=run['id'])
        if not self._attempt(perform):self._empty_zones[key]['note'].value=self.status.value

    @staticmethod
    def _next_id(detail):
        ids={r['id'] for r in detail['runs']};n=1
        while f'R{n}' in ids:n+=1
        return f'R{n}'

    def _add(self,_):
        def perform():
            from .model import BAR_DIAMETER
            detail=deepcopy(self.owner.case.get('transverse_detail',empty_detail()));p=self.owner.case['inputs'];rid=self._next_id(detail)
            first=max((r['end_in']+r['pitch_in'] for r in detail['runs']),default=p['C_s']+BAR_DIAMETER[p['Bar_v']]/2)
            detail['runs'].append(dict(id=rid,kind='hoop',bar=int(p['Bar_v']),zone='G',first_in=first,end_in=first,pitch_in=p['s_G']))
            detail['enabled']=True;self._commit(detail,selected=rid)
        self._attempt(perform)

    def _remove_run(self,rid):
        detail=deepcopy(self.owner.case['transverse_detail']);detail['runs']=[r for r in detail['runs'] if r['id']!=rid]
        self._attempt(lambda:self._commit(detail))

    def _split_run(self,rid):
        def perform():
            detail=deepcopy(self.owner.case['transverse_detail']);run=next(r for r in detail['runs'] if r['id']==rid)
            count=math.floor((run['end_in']-run['first_in'])/run['pitch_in']+1e-9)+1
            if count<2:raise ValueError('A run needs at least two bars to split.')
            other=deepcopy(run);other['id']=self._next_id(detail);other['first_in']=run['first_in']+(count//2)*run['pitch_in']
            run['end_in']=other['first_in']-run['pitch_in']
            for r in (run,other):r['development_confirmed']=False;r.pop('development_fingerprint',None)
            detail['runs'].append(other);self._commit(detail,selected=other['id'])
        self._attempt(perform)

    def close(self):
        for card in self._cards.values():card.close()
        for header,box in self._zones.values():header.close();box.close()
        for controls in self._empty_zones.values():
            for widget in controls.values():widget.close()
        for widget in (self.active,self.generate,self.add,self.status,self.zone_notice,self.zone_grid,self.general,self.ui):widget.close()
