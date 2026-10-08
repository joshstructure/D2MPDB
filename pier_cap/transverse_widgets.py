"""Editable physical bar runs; serialized with the case, independent of U inventory."""
from copy import deepcopy
import html
import math
import ipywidgets as W
from .transverse import empty_detail,enabled,shape_parameters,suggested_detail,validate_detail,run_summary,development_current,development_fingerprint
from .widget_compat import Accordion
from .transverse_zones import zone_runs,new_zone_run


class TransversePanel:
    def __init__(self,owner):
        self.owner=owner;self.busy=False;self.zone_controls={};self._zone_key=None;self._zone_widgets=[]
        self.active=W.Checkbox(description='Use actual transverse layout',indent=False)
        self.generate=W.Button(description='Create starting layout',icon='plus',layout=W.Layout(width='210px'))
        self.select=W.Dropdown(options=[],description='Edit run',layout=W.Layout(width='430px'))
        self.add=W.Button(description='Add run',icon='plus');self.remove=W.Button(description='Remove run',icon='minus')
        self.apply=W.Button(description='Apply bar run',button_style='primary',icon='check')
        self.kind=W.Dropdown(options=[('Closed hoop (between piles)','hoop'),('U-bar, OPEN BOTTOM (at pile)','pile_u')],description='Bar shape',style={'description_width':'110px'},layout=W.Layout(width='390px'))
        self.bar=W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],description='Bar size')
        self.zone=W.Dropdown(options=[('Overall shear (G)','G'),('Lower-shear (L)','L')],description='Shear basis')
        self.fields={}
        for key,label,value in [('first_in','First bar (in)',0),('first','First bar (ft)',0),
            ('end_in','Last-bar limit (in)',0),('end','Last-bar limit (ft)',0),('pitch','Pitch (in)',9),
            ('inside_diameter_in','Inside bend diameter (in)',4.5),('tail_in','Straight end tail (in)',9),
            ('end_raise_in','Raise U ends (in)',0),('side_inset_in','Inset legs from cover (in)',0)]:
            self.fields[key]=W.FloatText(value=value,description=label,continuous_update=False,style={'description_width':'180px'},layout=W.Layout(width='300px'))
        self.angle=W.Dropdown(options=[('90° inward hooks',90),('135° inward hooks',135),('180° return hooks',180),('Straight legs, no end hook',0)],description='U ends',style={'description_width':'110px'},layout=W.Layout(width='390px'))
        self.confirm=W.Checkbox(description='Development / closure checked for this run',indent=False)
        self.basis=W.Textarea(description='Checked detail',placeholder='Drawing / calculation reference and development basis',style={'description_width':'110px'},layout=W.Layout(width='620px',height='60px'))
        self.status=W.HTML();self.count=W.HTML()
        self.editor=W.VBox([W.HBox([self.kind,self.bar,self.zone],layout=W.Layout(flex_flow='row wrap')),
            W.HBox([self.fields[n] for n in ('first_in','first')],layout=W.Layout(flex_flow='row wrap')),
            W.HBox([self.fields[n] for n in ('end_in','end','pitch')],layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<small>Locations are measured from the left end of the cap. Inch and foot fields are linked. '
                   'The last-bar limit bounds the run; the actual last bar stays on the entered spacing.</small>'),
            W.HTML('<p><b>U shape:</b> top across the cap, two legs down beside the pile, bottom open. '
                   'Raise ends is measured above the bottom-cover position. Inset moves both legs inward from the side-cover position. '
                   'End tails point inward independently and are checked for pile clashes. All dimensions are actual inches.</p>'),
            self.angle,W.HBox([self.fields[n] for n in ('inside_diameter_in','tail_in','end_raise_in','side_inset_in')],layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<small>Bend and tail values define the drawing. They do not calculate or certify development length. '
                   'Hoops use a closed outline; their closure detail must be checked separately. Change the size and bend dimensions together.</small>'),
            self.confirm,self.basis,self.apply,self.count])
        self.zone_grid=W.GridBox(layout=W.Layout(width='100%',grid_template_columns='repeat(auto-fit, minmax(215px, 1fr))',grid_gap='10px'))
        self.zone_notice=W.HTML()
        self.general=Accordion(children=[W.VBox([
            W.HTML('<p>Use the run editor for custom limits, multiple runs per zone, shear basis, bend dimensions and development records. '
                   'Changing a zone size preserves explicitly entered bend and tail dimensions; review their fit.</p>'),
            W.HBox([self.select,self.add,self.remove],layout=W.Layout(flex_flow='row wrap')),self.editor]),self.owner.hoop_reference_inputs])
        self.general.set_title(0,'General hoop / U-bar details and exact run limits')
        self.general.set_title(1,'Uniform-cage reference inputs and spacing assumptions')
        self.general.selected_index=None
        self.ui=W.VBox([W.HTML('<h3>Actual hoops and pile U-bars · by zone</h3><p>Zones follow the elevation from left to right. '
            'Change a run’s size, spacing or locations to update the drawing and checks immediately; press Enter or leave a number field to apply it. '
            'Locations are measured from the <b>left end of the cap</b>. Edit inches or feet; the paired field updates automatically. '
            'The <b>last-bar limit</b> bounds the run; the actual last bar stays on the entered spacing and is shown below each run. '
            '<b>Create starting layout</b> fills the cap using the reference overall pitch. '
            'Bend dimensions and development records are below.</p>'),
            W.HBox([self.active,self.generate],layout=W.Layout(flex_flow='row wrap')),
            self.zone_grid,self.zone_notice,self.status,self.general],layout=W.Layout(width='100%',min_width='0'))
        self.active.observe(self._toggle,names='value');self.select.observe(self._selected,names='value')
        self.generate.on_click(self._generate);self.add.on_click(self._add);self.remove.on_click(self._remove);self.apply.on_click(self._apply)
        for field in [self.kind,self.bar,self.zone,self.angle,*self.fields.values()]:field.observe(self._edited,names='value')
        for name,other in [('first_in','first'),('first','first_in'),('end_in','end'),('end','end_in')]:
            self.fields[name].observe(lambda change,target=other:self._link_location(change,target),names='value')
        self.sync()

    @property
    def selected_run_id(self):return self.select.value

    def sync(self):
        self.busy=True
        try:
            detail=self.owner.case.get('transverse_detail',empty_detail());runs=detail['runs'];old=self.select.value
            self.active.value=detail['enabled'];self.select.options=[(f'{r["id"]} · {"open-bottom U" if r["kind"]=="pile_u" else "hoop"} · #{r["bar"]}',r['id']) for r in runs]
            self.select.value=old if old in [r['id'] for r in runs] else (runs[0]['id'] if runs else None)
            self.generate.disabled=bool(runs);self.editor.layout.display='' if runs else 'none';self.remove.disabled=not runs
            if runs:self._fill()
        finally:self.busy=False

    def sync_zones(self,e):
        """Reuse controls during redraws so editing a zone retains keyboard focus."""
        self.zone_grid.layout.display=''
        zones,groups,custom=zone_runs(e)
        key=tuple((z['key'],tuple(r['id'] for r in groups[z['key']])) for z in zones)
        prior_busy=self.busy;self.busy=True
        try:
            if key!=self._zone_key:
                self.zone_grid.children=[]
                for widget in self._zone_widgets:widget.close()
                self._zone_widgets=[];self.zone_controls={};self._zone_headers={};self._empty_zones={}
                cards=[]
                for z in zones:
                    header=W.HTML();self._zone_headers[z['key']]=header;children=[header]
                    for run in groups[z['key']]:
                        label=W.HTML();size=W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],description='Size',
                            style={'description_width':'65px'},layout=W.Layout(width='calc(100% - 4px)',min_width='0'))
                        pitch=W.FloatText(description='c/c (in)',continuous_update=False,
                            style={'description_width':'65px'},layout=W.Layout(width='calc(100% - 4px)',min_width='0'))
                        info=W.HTML();error=W.HTML()
                        controls=dict(bar=size,pitch=pitch,info=info,label=label,error=error)
                        locations=[]
                        for name,title,field,scale in [('first_in','First (in)','first_in',1),('first_ft','First (ft)','first_in',12),
                            ('end_in','Last limit (in)','end_in',1),('end_ft','Last limit (ft)','end_in',12)]:
                            widget=W.FloatText(description=title,continuous_update=False,style={'description_width':'95px'},
                                layout=W.Layout(width='calc(100% - 4px)',min_width='0'))
                            controls[name]=widget;locations.append(widget)
                            widget.observe(lambda change,rid=run['id'],name=field,factor=scale:self._zone_edited(rid,name,change,factor),names='value')
                        self.zone_controls[run['id']]=controls
                        for field,widget in [('bar',size),('pitch_in',pitch)]:
                            widget.observe(lambda change,rid=run['id'],name=field:self._zone_edited(rid,name,change),names='value')
                        children.extend([label,size,pitch,*locations,info,error])
                    if not groups[z['key']]:
                        size=W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],value=int(e.case['inputs']['Bar_v']),description='Size',
                            style={'description_width':'65px'},layout=W.Layout(width='calc(100% - 4px)',min_width='0'))
                        pitch=W.FloatText(value=e.case['inputs']['s_G'],description='c/c (in)',continuous_update=False,
                            style={'description_width':'65px'},layout=W.Layout(width='calc(100% - 4px)',min_width='0'))
                        empty=W.HTML();button=W.Button(description='Add zone run',icon='plus',layout=W.Layout(width='calc(100% - 4px)',min_width='0'))
                        button.on_click(lambda _,key=z['key']:self._add_zone(key))
                        self._empty_zones[z['key']]=dict(note=empty,bar=size,pitch=pitch,button=button)
                        children.extend([empty,size,pitch,button])
                    card=W.VBox(children,layout=W.Layout(border='1px solid '+('#bd407d' if z['kind']=='pile_u' else '#7952a3'),padding='8px',min_width='0'))
                    self._zone_widgets.extend([*children,card]);cards.append(card)
                self.zone_grid.children=cards;self._zone_key=key
            active=enabled(e.case)
            for z in zones:
                color='#bd407d' if z['kind']=='pile_u' else '#7952a3'
                self._zone_headers[z['key']].value=(f'<b style="color:{color}">{html.escape(z["label"])}</b><br><small>'+
                    ('Open-bottom U-bars' if z['kind']=='pile_u' else 'Closed hoops')+'</small>')
                for run in groups[z['key']]:
                    c=self.zone_controls[run['id']];c['bar'].value=run['bar'];c['pitch'].value=run['pitch_in']
                    c['first_in'].value=run['first_in'];c['first_ft'].value=run['first_in']/12
                    c['end_in'].value=run['end_in'];c['end_ft'].value=run['end_in']/12
                    for name in ('bar','pitch','first_in','first_ft','end_in','end_ft'):c[name].disabled=not active
                    count=math.floor((run['end_in']-run['first_in'])/run['pitch_in']+1e-9)+1
                    last=run['first_in']+(count-1)*run['pitch_in']
                    c['label'].value='<small>Run '+html.escape(run['id'])+'</small>'
                    c['info'].value=f'<small>{count} {"bar" if count==1 else "bars"}<br>Actual last: {last:g} in / {last/12:g} ft</small>'
                    c['error'].value=''
                if z['key'] in self._empty_zones:
                    c=self._empty_zones[z['key']]
                    c['note'].value='<small>No entered run. Set size / spacing, then add this zone to edit its first and last locations.</small>'
                    c['button'].disabled=z['right']<=z['left']
            notes=[]
            if not active:notes.append('Actual layout is off. Enable it to edit saved zone runs and draw their bars.')
            if custom:notes.append('Custom / crossing runs retained in the general editor: '+', '.join(r['id'] for r in custom)+'.')
            notes.append('Zone labels follow the current pile layout. Saved bar stations do not move when geometry changes. Review adjoining-run spacing and the D/C checks.')
            self.zone_notice.value='<p>'+html.escape(' '.join(notes))+'</p>'
        finally:self.busy=prior_busy

    def _zone_edited(self,run_id,field,change,scale=1):
        if self.busy or self.owner.busy:return
        def perform():
            detail=deepcopy(self.owner.case['transverse_detail'])
            run=next(r for r in detail['runs'] if r['id']==run_id)
            run[field]=change['new']*scale;run['development_confirmed']=False;run.pop('development_fingerprint',None)
            self._commit(detail)
        applied=self._attempt(perform)
        if self.owner.current:self.sync_zones(self.owner.current)
        if not applied and run_id in self.zone_controls:self.zone_controls[run_id]['error'].value=self.status.value

    def _add_zone(self,key):
        def perform():
            from .model import evaluate
            e=evaluate(self.owner.case);c=self._empty_zones[key]
            run=new_zone_run(e,key,c['bar'].value,c['pitch'].value)
            detail=deepcopy(self.owner.case.get('transverse_detail',empty_detail()))
            detail['enabled']=True;detail['runs'].append(run)
            self._commit(detail)
        if not self._attempt(perform) and key in self._empty_zones:self._empty_zones[key]['note'].value=self.status.value

    def close(self):
        for widget in self._zone_widgets:widget.close()
        self.ui.close()

    def _fill(self):
        run=next(r for r in self.owner.case['transverse_detail']['runs'] if r['id']==self.select.value)
        self.kind.value=run['kind'];self.bar.value=run['bar'];self.zone.value=run['zone']
        self.fields['first_in'].value=run['first_in'];self.fields['first'].value=run['first_in']/12
        self.fields['end_in'].value=run['end_in'];self.fields['end'].value=run['end_in']/12;self.fields['pitch'].value=run['pitch_in']
        shape=shape_parameters(run);self.angle.value=shape['end_angle']
        for n in ('inside_diameter_in','tail_in','end_raise_in','side_inset_in'):self.fields[n].value=shape[n]
        self.confirm.value=development_current(self.owner.case,run);self.basis.value=run.get('development_basis','')
        s=next((r for r in run_summary(self.owner.case) if r['id']==run['id']),None)
        self.count.value=(f'<b>Applied run: {s["count"]} bars. First {s["first_in"]:g} in / {s["first_in"]/12:g} ft; '
            f'actual last {s["actual_last_in"]:g} in / {s["actual_last_in"]/12:g} ft; exact pitch {s["pitch_in"]:g} in.</b>' if s else '<b>Layout is disabled. Runs remain saved.</b>')

    def _commit(self,detail):
        case=deepcopy(self.owner.case);case['transverse_detail']=detail
        validate_detail(case)
        self.owner.case=case;self.sync();self.owner._update_search_basis();self.owner.refresh();self.owner._notify_case_change()
        self.status.value='<p>Layout applied. The live views and export now use these exact stations.</p>' if detail['enabled'] else '<p>Actual layout disabled; its saved runs are retained.</p>'

    def _attempt(self,callback):
        try:callback();return True
        except Exception as exc:
            self.status.value='<p style="color:#bb3e39"><b>Not applied:</b> '+html.escape(str(exc))+'</p>'
            return False

    def _toggle(self,change):
        if self.busy or self.owner.busy:return
        detail=deepcopy(self.owner.case.get('transverse_detail',empty_detail()));detail['enabled']=change['new']
        self._attempt(lambda:self._commit(detail))

    def _generate(self,_):
        from .model import evaluate
        self._attempt(lambda:self._commit(suggested_detail(evaluate(self.owner.case))))

    def _selected(self,change):
        if self.busy or not self.select.value:return
        self.busy=True
        try:self._fill()
        finally:self.busy=False
        if self.owner.current:self.owner.refresh()

    def _edited(self,change):
        if not self.busy:self.confirm.value=False

    def _link_location(self,change,target):
        if self.busy:return
        self.busy=True
        try:self.fields[target].value=change['new']/12 if target in ('first','end') else change['new']*12
        finally:self.busy=False

    def _add(self,_):
        def perform():
            detail=deepcopy(self.owner.case.get('transverse_detail',empty_detail()));existing={r['id'] for r in detail['runs']};n=1
            while f'R{n}' in existing:n+=1
            p=self.owner.case['inputs'];first=max((r['end_in']+r['pitch_in'] for r in detail['runs']),default=p['C_s']+1)
            detail['runs'].append(dict(id=f'R{n}',kind='pile_u',bar=int(p['Bar_v']),zone='G',first_in=first,end_in=first,pitch_in=p['s_G']))
            self._commit(detail);self.select.value=f'R{n}'
        self._attempt(perform)

    def _remove(self,_):
        detail=deepcopy(self.owner.case['transverse_detail']);detail['runs']=[r for r in detail['runs'] if r['id']!=self.select.value]
        self._attempt(lambda:self._commit(detail))

    def _apply(self,_):
        detail=deepcopy(self.owner.case['transverse_detail'])
        run=next(r for r in detail['runs'] if r['id']==self.select.value)
        run.update(kind=self.kind.value,bar=self.bar.value,zone=self.zone.value,first_in=self.fields['first_in'].value,
            end_in=self.fields['end_in'].value,pitch_in=self.fields['pitch'].value,development_confirmed=self.confirm.value,development_basis=self.basis.value)
        run['shape']={n:self.fields[n].value for n in ('inside_diameter_in','tail_in','end_raise_in','side_inset_in')};run['shape']['end_angle']=self.angle.value
        if run['development_confirmed']:run['development_fingerprint']=development_fingerprint(dict(self.owner.case,transverse_detail=detail),run)
        else:run.pop('development_fingerprint',None)
        self._attempt(lambda:self._commit(detail))
