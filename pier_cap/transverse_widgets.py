"""Editable physical bar runs; serialized with the case, independent of U inventory."""
from copy import deepcopy
import html
import ipywidgets as W
from .transverse import empty_detail,enabled,shape_parameters,suggested_detail,validate_detail,run_summary,development_current,development_fingerprint


class TransversePanel:
    def __init__(self,owner):
        self.owner=owner;self.busy=False
        self.active=W.Checkbox(description='Use actual transverse layout',indent=False)
        self.generate=W.Button(description='Create starting layout',icon='plus',layout=W.Layout(width='210px'))
        self.select=W.Dropdown(options=[],description='Edit run',layout=W.Layout(width='430px'))
        self.add=W.Button(description='Add run',icon='plus');self.remove=W.Button(description='Remove run',icon='minus')
        self.apply=W.Button(description='Apply bar run',button_style='primary',icon='check')
        self.kind=W.Dropdown(options=[('Closed hoop (between piles)','hoop'),('U-bar, OPEN BOTTOM (at pile)','pile_u')],description='Bar shape',style={'description_width':'110px'},layout=W.Layout(width='390px'))
        self.bar=W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],description='Bar size')
        self.zone=W.Dropdown(options=[('Overall shear (G)','G'),('Lower-shear (L)','L')],description='Shear basis')
        self.fields={}
        for key,label,value in [('first','First bar (ft)',0),('end','Run end limit (ft)',0),('pitch','Pitch (in)',9),
            ('inside_diameter_in','Inside bend diameter (in)',4.5),('tail_in','Straight end tail (in)',9),
            ('end_raise_in','Raise U ends (in)',0),('side_inset_in','Inset legs from cover (in)',0)]:
            self.fields[key]=W.FloatText(value=value,description=label,style={'description_width':'180px'},layout=W.Layout(width='300px'))
        self.angle=W.Dropdown(options=[('90° inward hooks',90),('135° inward hooks',135),('180° return hooks',180),('Straight legs, no end hook',0)],description='U ends',style={'description_width':'110px'},layout=W.Layout(width='390px'))
        self.confirm=W.Checkbox(description='Development / closure checked for this run',indent=False)
        self.basis=W.Textarea(description='Checked detail',placeholder='Drawing / calculation reference and development basis',style={'description_width':'110px'},layout=W.Layout(width='620px',height='60px'))
        self.status=W.HTML();self.count=W.HTML()
        self.editor=W.VBox([W.HBox([self.kind,self.bar,self.zone],layout=W.Layout(flex_flow='row wrap')),
            W.HBox([self.fields[n] for n in ('first','end','pitch')],layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<p><b>U shape:</b> top across the cap, two legs down beside the pile, bottom open. '
                   'Raise ends is measured above the bottom-cover position. Inset moves both legs inward from the side-cover position. '
                   'End tails point inward independently and are checked for pile clashes. All dimensions are actual inches.</p>'),
            self.angle,W.HBox([self.fields[n] for n in ('inside_diameter_in','tail_in','end_raise_in','side_inset_in')],layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<small>Bend and tail values define the drawing. They do not calculate or certify development length. '
                   'Hoops use a closed outline; their closure detail must be checked separately. Change the size and bend dimensions together.</small>'),
            self.confirm,self.basis,self.apply,self.count])
        self.ui=W.VBox([W.HTML('<h3>Actual hoops and pile U-bars</h3><p>Set the bar shape, size and exact stations here. '
            '<b>Create starting layout</b> uses the current overall pitch, with closed hoops clear of the piles and open-bottom U-bars over the pile zones. '
            'It creates editable dimensions; development is initially unconfirmed. Saved cases retain every run.</p>'),
            W.HBox([self.active,self.generate],layout=W.Layout(flex_flow='row wrap')),
            W.HBox([self.select,self.add,self.remove],layout=W.Layout(flex_flow='row wrap')),self.editor,self.status])
        self.active.observe(self._toggle,names='value');self.select.observe(self._selected,names='value')
        self.generate.on_click(self._generate);self.add.on_click(self._add);self.remove.on_click(self._remove);self.apply.on_click(self._apply)
        for field in [self.kind,self.bar,self.zone,self.angle,*self.fields.values()]:field.observe(self._edited,names='value')
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

    def _fill(self):
        run=next(r for r in self.owner.case['transverse_detail']['runs'] if r['id']==self.select.value)
        self.kind.value=run['kind'];self.bar.value=run['bar'];self.zone.value=run['zone']
        self.fields['first'].value=run['first_in']/12;self.fields['end'].value=run['end_in']/12;self.fields['pitch'].value=run['pitch_in']
        shape=shape_parameters(run);self.angle.value=shape['end_angle']
        for n in ('inside_diameter_in','tail_in','end_raise_in','side_inset_in'):self.fields[n].value=shape[n]
        self.confirm.value=development_current(self.owner.case,run);self.basis.value=run.get('development_basis','')
        s=next((r for r in run_summary(self.owner.case) if r['id']==run['id']),None)
        self.count.value=(f'<b>Applied run: {s["count"]} bars. First {s["first_in"]/12:.3f} ft; last {s["actual_last_in"]/12:.3f} ft; exact pitch {s["pitch_in"]:g} in.</b>' if s else '<b>Layout is disabled. Runs remain saved.</b>')

    def _commit(self,detail):
        case=deepcopy(self.owner.case);case['transverse_detail']=detail
        validate_detail(case)
        self.owner.case=case;self.sync();self.owner._update_search_basis();self.owner.refresh();self.owner._notify_case_change()
        self.status.value='<p>Layout applied. The live views and export now use these exact stations.</p>' if detail['enabled'] else '<p>Actual layout disabled; its saved runs are retained.</p>'

    def _attempt(self,callback):
        try:callback()
        except Exception as exc:self.status.value='<p style="color:#bb3e39"><b>Not applied:</b> '+html.escape(str(exc))+'</p>'

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
        run.update(kind=self.kind.value,bar=self.bar.value,zone=self.zone.value,first_in=self.fields['first'].value*12,
            end_in=self.fields['end'].value*12,pitch_in=self.fields['pitch'].value,development_confirmed=self.confirm.value,development_basis=self.basis.value)
        run['shape']={n:self.fields[n].value for n in ('inside_diameter_in','tail_in','end_raise_in','side_inset_in')};run['shape']['end_angle']=self.angle.value
        if run['development_confirmed']:run['development_fingerprint']=development_fingerprint(dict(self.owner.case,transverse_detail=detail),run)
        else:run.pop('development_fingerprint',None)
        self._attempt(lambda:self._commit(detail))
