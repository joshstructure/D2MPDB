"""One persistent, numbered card per physical transverse run."""
from copy import deepcopy
import html
import ipywidgets as W
from .transverse import empty_detail,enabled,shape_parameters,validate_detail,development_current,development_fingerprint,run_stations,end_bar_note,HOOK_ROTATIONS,hook_rotations
from .widget_compat import Accordion
from .transverse_zones import zone_runs,new_zone_run,zone_add_conflicts,occupant_text,station_range,run_last_station,run_limit_overlaps,starting_zone_detail


def _layout():return W.Layout(width='calc(100% - 4px)',min_width='0')


def _card_layout():
    return W.Layout(width='280px',min_width='280px',max_width='280px',flex='0 0 280px',padding='8px',border='1px solid #b7bec8')


def _keep_card_positions(current,desired):
    """Keep mounted cards in place when edits change their zone classification."""
    ordered=[card for card in current if card in desired]
    for index,card in enumerate(desired):
        if card not in ordered:
            following=next((other for other in desired[index+1:] if other in ordered),None)
            ordered.insert(ordered.index(following) if following is not None else len(ordered),card)
    return tuple(ordered)


class RunCard:
    """All run inputs live here; repainting never replaces an existing card."""
    def __init__(self,panel,rid):
        self.panel=panel;self.rid=rid;self.controls={};self.widgets=[]
        def add(name,widget):self.controls[name]=widget;self.widgets.append(widget);return widget
        def number(name,label,field=None,scale=1):
            compact=name in ('pitch','first_in','first_ft','end_in','end_ft')
            widget=add(name,W.FloatText(description=label,continuous_update=False,
                style={'description_width':'65px' if compact else '105px'},
                layout=W.Layout(width='124px' if compact else '224px',flex='0 0 auto')))
            widget.observe(lambda change:panel._zone_edited(rid,field or name,change,scale),names='value')
            return widget
        label=add('label',W.HTML())
        size=add('bar',W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],description='Size',style={'description_width':'65px'},layout=W.Layout(width='124px')))
        size.observe(lambda c:panel._zone_edited(rid,'bar',c),names='value')
        pitch=number('pitch','c/c in','pitch_in')
        locations=[number('first_in','First in'),number('first_ft','First ft','first_in',12),
                   number('end_in','Limit in'),number('end_ft','Limit ft','end_in',12)]
        info=add('info',W.HTML(layout=W.Layout(min_height='20px')))
        warning=add('warning',W.HTML(layout=W.Layout(min_height='32px')))
        error=add('error',W.HTML())
        view=add('view',W.Button(description=f'{rid} · details',icon='eye',layout=W.Layout(width='124px')))
        view.on_click(lambda _:panel._select_run(rid))
        kind=add('kind',W.Dropdown(options=[('Closed hoop','hoop'),('Open-bottom U','pile_u')],description='Shape',style={'description_width':'105px'},layout=W.Layout(width='224px')))
        shear=add('zone',W.Dropdown(options=[('Overall (G)','G'),('Lower-shear (L)','L')],description='Shear basis',style={'description_width':'105px'},layout=W.Layout(width='224px')))
        angle=add('end_angle',W.Dropdown(options=[('90° inward',90),('135° inward',135),('180° return',180),('Straight',0)],description='U ends',style={'description_width':'105px'},layout=W.Layout(width='224px')))
        extension=add('extension_mode',W.Dropdown(options=[('CRSI standard','standard'),('Custom','custom')],description='Hook extension',style={'description_width':'105px'},layout=W.Layout(width='250px')))
        end_bar=add('include_end_bar',W.Checkbox(description='Bar at end limit',indent=False,layout=W.Layout(width='224px')))
        end_bar.observe(lambda change:panel._zone_edited(rid,'include_end_bar',change),names='value')
        for name,widget in [('kind',kind),('zone',shear),('end_angle',angle),('extension_mode',extension)]:
            widget.observe(lambda change,field=name:panel._zone_edited(rid,field,change),names='value')
        shape=[number(name,title) for name,title in [('inside_diameter_in','Bend ID (in)'),('tail_in','Extension (in)'),
            ('end_raise_in','Raise ends (in)'),('side_inset_in','Inset legs (in)'),
            (HOOK_ROTATIONS[0],'Left rotate (°)'),(HOOK_ROTATIONS[1],'Right rotate (°)')]]
        help_text=add('help',W.HTML('<small>U-bars are open downward. Raise ends is above bottom cover; inset moves legs inward. '
            'Hook rotation turns each bend and tail about its vertical leg. Left / right refer to the transverse section. '
            '0° is inward in the section; positive turns toward increasing cap stations, negative toward decreasing stations. '
            '±90° is a trial geometry range, not a code allowance. Rotated-hook anchorage stays PENDING; '
            'verify longitudinal-bar engagement and 3D congestion. Rotation values are inactive for hoops and straight ends. '
            'CRSI standard hook extensions update with bar size and angle; Custom preserves an entered length. '
            'Extension is the straight length after the bend. Closed-stirrup hook extensions are set in LRFD regions & checks. '
            'Bend dimensions describe the drawing. Record the separate development / closure check below.</small>'))
        basis=add('development_basis',W.Textarea(description='Detail ref.',placeholder='Drawing / calculation reference',continuous_update=False,
            style={'description_width':'70px'},layout=W.Layout(width='calc(100% - 4px)',max_width='600px',height='70px')))
        confirm=add('development_confirmed',W.Checkbox(description='Development / closure checked',indent=False,layout=_layout()))
        for name,widget in [('development_basis',basis),('development_confirmed',confirm)]:
            widget.observe(lambda change,field=name:panel._zone_edited(rid,field,change),names='value')
        split=add('split',W.Button(description=f'Split {rid}',icon='columns',layout=W.Layout(width='130px')))
        split.on_click(lambda _:panel._split_run(rid))
        remove=add('remove',W.Button(description=f'Delete {rid}',icon='trash',button_style='danger',
            tooltip=f'Delete only run {rid} and its saved bars.',layout=W.Layout(width='124px')))
        remove.on_click(lambda _:panel._remove_run(rid))
        detail_fields=W.HBox([kind,shear,angle,extension,end_bar,*shape],layout=W.Layout(flex_flow='row wrap',width='100%'))
        detail_actions=W.HBox([split])
        details=W.VBox([detail_fields,help_text,basis,confirm,detail_actions],layout=W.Layout(width='100%',min_width='0'))
        advanced=add('details',Accordion(children=[details]));advanced.set_title(0,f'{rid} · shape and development');advanced.selected_index=None
        self.widgets.extend([details,detail_fields,detail_actions])
        pairs=[W.HBox(pair,layout=W.Layout(width='100%',min_width='0',flex_flow='row nowrap',overflow='visible')) for pair in ([size,pitch],locations[:2],locations[2:])]
        self.widgets.extend(pairs)
        actions=W.HBox([view,remove],layout=W.Layout(width='100%',flex_flow='row nowrap'))
        self.widgets.append(actions)
        self.feedback=add('feedback',W.HTML())
        self.ui=W.VBox([label,*pairs,info,warning,self.feedback,actions,error],layout=_card_layout())
        self.ui.add_class('cap-hoop-card')

    def sync(self,run,region,active,selected,case,overlaps=()):
        c=self.controls;shape=shape_parameters(run)
        values={**run,**shape,'pitch':run['pitch_in'],'first_ft':run['first_in']/12,'end_ft':run['end_in']/12,
                'include_end_bar':run.get('include_end_bar',False),
                'development_basis':run.get('development_basis',''),'development_confirmed':development_current(case,run)}
        for name,value in values.items():
            if name in c and hasattr(c[name],'disabled'):
                c[name].value=value;c[name].disabled=not active
        for name in HOOK_ROTATIONS:c[name].disabled=not active or run['kind']!='pile_u' or not shape['end_angle']
        c['extension_mode'].disabled=not active or run['kind']!='pile_u' or not shape['end_angle']
        c['tail_in'].disabled=not active or run['kind']!='pile_u' or shape['extension_mode']=='standard' or not shape['end_angle']
        c['development_confirmed'].disabled=not active or any(hook_rotations(run))
        stations=run_stations(run);count=len(stations);last=stations[-1]
        color='#bd407d' if run['kind']=='pile_u' else '#7952a3'
        self.ui.layout.border='1px solid '+color
        c['label'].value=f'<b style="font-size:16px;color:{color}">Run {html.escape(run["id"])}</b> · {count} {"bar" if count==1 else "bars"}<br><small>{html.escape(region)} · '+('Open-bottom U-bars' if run['kind']=='pile_u' else 'Closed hoops')+'</small>'
        c['info'].value=f'<small>Actual last: {last:g} in / {last/12:g} ft'+end_bar_note(run)+'</small>'
        ids=', '.join(o['id'] for o in overlaps)
        ranges='; '.join(o['id']+': '+station_range(o['first'],o['last']) for o in overlaps)
        c['warning'].value=('<small style="color:#9b6012" title="'+html.escape(ranges,quote=True)+'"><b>⚠ Limits overlap '+html.escape(ids)+'.</b> Edit first / limit to resolve.</small>' if overlaps else '')
        if run.get('include_end_bar',False) and len(stations)>1 and self.panel.owner.current:
            from .detailing import required_clear
            from .model import BAR_DIAMETER
            diameter=BAR_DIAMETER[run['bar']];gap=stations[-1]-stations[-2]
            if gap-diameter<required_clear(self.panel.owner.current,diameter)-1e-7:
                c['warning'].value+=f'<br><small style="color:#bb3e39"><b>⚠ Last gap {gap:g} in fails clear spacing.</b> Adjust pitch or limits.</small>'
        c['view'].button_style='info' if selected else '';c['view'].disabled=not active
        c['split'].disabled=not active or count<2;c['remove'].disabled=False
        c['error'].value=''
        from .steel_feedback import run_feedback
        self.feedback.value=run_feedback(self.panel.owner.current,run['id']) if active and self.panel.owner.current else '<small>Actual layout inactive.</small>'

    def close(self):
        for widget in self.widgets:widget.close()
        self.ui.close()


class TransversePanel:
    def __init__(self,owner):
        self.owner=owner;self.busy=False;self.zone_controls={};self._cards={};self._zones={};self._empty_zones={};self._inspect_buttons={};self._selected_run_id=None
        self.active=W.Checkbox(description='Use actual transverse layout',indent=False)
        self.generate=W.Button(description='Create starting layout',icon='plus',layout=W.Layout(width='210px'))
        self.generate.tooltip='One run per zone; leave half the minimum allowable clear spacing from each zone edge to the nearest bar surface, independently of Start c/c. Cap-end cover still governs.'
        p=owner.case['inputs'];self._starter_defaults=(p['Bar_v'],p['s_G']);self._previous_detail=None;self._rebuild_order=False
        self.start_bar=W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],value=int(p['Bar_v']),description='Start size',style={'description_width':'65px'},layout=W.Layout(width='142px'))
        self.start_pitch=W.FloatText(value=p['s_G'],description='Start c/c (in)',continuous_update=False,style={'description_width':'90px'},layout=W.Layout(width='166px'))
        self.undo_start=W.Button(description='Undo starting layout',icon='undo',disabled=True,layout=W.Layout(width='178px'))
        self.add=W.Button(description='Add custom run',icon='plus')
        self.status=W.HTML(layout=W.Layout(min_height='22px'));self.zone_notice=W.HTML()
        # Explicit non-shrinking flex cards work with Colab's mixed widget manager.
        # Each run is a direct child, including multiple runs in the same zone.
        self.zone_grid=W.HBox(layout=W.Layout(width='100%',min_width='0',max_width='100%',flex='0 0 auto',
            display='flex',flex_flow='row nowrap',align_items='flex-start',overflow='auto',grid_gap='8px',padding='6px',border='1px solid #b7bec8'))
        self.zone_grid.add_class('cap-hoop-track')
        self.zone_scroll=W.VBox([self.zone_grid],layout=W.Layout(width='100%',min_width='0',max_width='100%',
            flex='0 0 auto'))
        self.detail_area=W.VBox(layout=W.Layout(width='100%',min_width='0'))
        self.selected_info=W.HTML()
        self.general=Accordion(children=[owner.hoop_reference_inputs]);self.general.set_title(0,'General hoop reference inputs and spacing assumptions');self.general.selected_index=None
        self.ui=W.VBox([W.HTML('<style>.cap-hoop-track {flex-wrap:nowrap!important;overflow-x:scroll!important;overflow-y:hidden!important;overscroll-behavior-x:contain;}'
            '.cap-hoop-card {flex-shrink:0!important;}</style>'
            '<h3 style="margin:4px 0">Actual hoops and pile U-bars · by zone</h3><p style="margin:4px 0"><small>'
            'First / limit: from the <b>left cap end</b>; inches and feet are linked. '
            '<b>Details</b> opens shape / development; <b>Delete R…</b> removes that run.</small></p>'),
            W.HBox([self.active,self.start_bar,self.start_pitch,self.generate,self.undo_start,self.add],layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<small>Starting layout replaces current runs. Zone edges get half the minimum allowable clear spacing to the bar surface, independent of Start c/c. Cap-end cover still governs. Bars near each run end shift as needed to meet minimum clear spacing; first and last bars stay fixed.</small>'),
            self.status,self.zone_scroll,self.detail_area,self.zone_notice,self.general],layout=W.Layout(width='100%',min_width='0'))
        self.active.observe(self._toggle,names='value');self.generate.on_click(self._generate);self.add.on_click(self._add)
        self.undo_start.on_click(self._undo_start)
        self.sync()

    @property
    def selected_run_id(self):return self._selected_run_id

    def sync(self,*,reset_starter=False):
        prior=self.busy;self.busy=True
        try:
            if reset_starter:
                self._starter_defaults=None;self._previous_detail=None;self.undo_start.disabled=True
            detail=self.owner.case.get('transverse_detail',empty_detail());runs=detail['runs']
            self.active.value=detail['enabled'];self.generate.disabled=False
            self.generate.description='Rebuild starting layout' if runs else 'Create starting layout'
            defaults=(self.owner.case['inputs']['Bar_v'],self.owner.case['inputs']['s_G'])
            if defaults!=self._starter_defaults:
                self.start_bar.value=int(defaults[0]);self.start_pitch.value=defaults[1];self._starter_defaults=defaults
            if self._selected_run_id not in [r['id'] for r in runs]:self._selected_run_id=runs[0]['id'] if runs else None
        finally:self.busy=prior

    def _zone_box(self,key):
        if key not in self._zones:
            header=W.HTML();box=W.VBox(layout=_card_layout());box.add_class('cap-hoop-card')
            self._zones[key]=(header,box)
        return self._zones[key]

    def _empty_card(self,z,e,occupants):
        key=z['key']
        if key not in self._empty_zones:
            size=W.Dropdown(options=[(f'#{n}',n) for n in range(3,12)],value=int(e.case['inputs']['Bar_v']),description='Size',style={'description_width':'65px'},layout=W.Layout(width='124px'))
            pitch=W.FloatText(value=e.case['inputs']['s_G'],description='c/c in',continuous_update=False,style={'description_width':'65px'},layout=W.Layout(width='124px'))
            note=W.HTML('<small>No run entered. Choose size / spacing and add this zone.</small>')
            button=W.Button(description='Add zone run',icon='plus',layout=_layout());button.on_click(lambda _:self._add_zone(key))
            links=W.HBox(layout=W.Layout(flex_flow='row wrap'))
            fields=W.HBox([size,pitch],layout=W.Layout(flex_flow='row nowrap'))
            self._empty_zones[key]=dict(bar=size,pitch=pitch,note=note,button=button,links=links,fields=fields,ui=W.VBox([note,fields,button,links]))
        c=self._empty_zones[key];c['button'].disabled=z['right']<=z['left']
        c['note'].value=('<small title="'+html.escape('; '.join(occupant_text(o) for o in occupants),quote=True)+'"><b style="color:#9b6012">⚠ May overlap '+html.escape(', '.join(o['id'] for o in occupants))+'.</b><br>Inspect saved runs, or add a run and adjust its limits.</small>' if occupants else
            '<small>No run assigned. Choose size / spacing; adjoining-bar clearance is kept when adding.</small>')
        buttons=[]
        for owner in occupants:
            rid=owner['id'];button_key=(key,rid)
            if button_key not in self._inspect_buttons:
                button=W.Button(description='Inspect '+rid,icon='eye',layout=W.Layout(width='124px'))
                button.on_click(lambda _,rid=rid:self._select_run(rid));self._inspect_buttons[button_key]=button
            buttons.append(self._inspect_buttons[button_key])
        if c['links'].children!=tuple(buttons):c['links'].children=buttons
        return c['ui']

    def sync_zones(self,e):
        self.zone_scroll.layout.display='';self.zone_grid.layout.display='';self.detail_area.layout.display='';zones,groups,custom=zone_runs(e)
        runs=e.case.get('transverse_detail',empty_detail())['runs'];ids={r['id'] for r in runs};occupancy=zone_add_conflicts(e);overlaps=run_limit_overlaps(runs)
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
                for run in group:
                    card=self._cards[run['id']];card.sync(run,z['label'],enabled(e.case),run['id']==self.selected_run_id,e.case,overlaps[run['id']])
                    boxes.append(card.ui)
                if not group:
                    header,box=self._zone_box(z['key']);header.value='<b>'+html.escape(z['label'])+'</b><br><small>'+station_range(z['left'],z['right'])+'</small>'
                    children=(header,self._empty_card(z,e,occupancy[z['key']]))
                    if box.children!=children:box.children=children
                    boxes.append(box)
            boxes=tuple(boxes) if self._rebuild_order else _keep_card_positions(self.zone_grid.children,boxes)
            if self.zone_grid.children!=boxes:self.zone_grid.children=boxes
            details=tuple(self.zone_controls[r['id']]['details'] for r in runs)
            for run,detail in zip(runs,details):detail.layout.display='' if run['id']==self.selected_run_id else 'none'
            selected=next((r for r in runs if r['id']==self.selected_run_id),None)
            self.selected_info.value=('<b>'+html.escape(selected['id'])+'</b> · Actual first–last: '+station_range(selected['first_in'],run_last_station(selected))+
                f' · Entered limit: {selected["end_in"]:g} in / {selected["end_in"]/12:g} ft' if selected else '')
            if selected and overlaps[selected['id']]:
                detail='; '.join(o['id']+' at '+station_range(o['first'],o['last']) for o in overlaps[selected['id']])
                self.selected_info.value+='<br><span style="color:#9b6012"><b>⚠ Run limits overlap:</b> '+html.escape(detail)+'. Inputs remain editable; review bar spacing.</span>'
            if self.detail_area.children!=(self.selected_info,*details):self.detail_area.children=(self.selected_info,*details)
            notes=[]
            if not enabled(e.case):notes.append('Actual layout is off. Enable it to edit saved runs and draw their bars.')
            if custom:notes.append('Crossing / different-shape runs: '+', '.join(r['id'] for r in custom)+'. Occupied zone cards identify their actual bars; Inspect opens that run below.')
            notes.append('Geometry changes never move saved bar stations. Review adjoining-run spacing and the D/C checks.')
            self.zone_notice.value='<p>'+html.escape(' '.join(notes))+'</p>'
        finally:self.busy=prior

    def _zone_edited(self,rid,field,change,scale=1):
        if self.busy or self.owner.busy:return
        def perform():
            detail=deepcopy(self.owner.case['transverse_detail']);run=next(r for r in detail['runs'] if r['id']==rid)
            value=change['new']*scale if isinstance(change['new'],(int,float)) and not isinstance(change['new'],bool) else change['new']
            if field in ('end_angle','extension_mode','inside_diameter_in','tail_in','end_raise_in','side_inset_in',*HOOK_ROTATIONS):
                run['shape']=shape_parameters(run);run['shape'][field]=value
            else:run[field]=value
            if field=='bar' and 'end_min_clear_in' in run:
                from .model import BAR_DIAMETER
                from .detailing import required_clear
                run['end_min_clear_in']=required_clear(self.owner.current,BAR_DIAMETER[value])
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
            self.zone_controls[rid]['details'].selected_index=0

    def _commit(self,detail,selected=None):
        if any(any(shape_parameters(r)[key] for key in HOOK_ROTATIONS) for r in detail['runs']):detail['version']=4
        elif any('end_min_clear_in' in r for r in detail['runs']):detail['version']=max(3,detail['version'])
        elif any(r.get('include_end_bar',False) for r in detail['runs']):detail['version']=max(2,detail['version'])
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
        def perform():
            detail=starting_zone_detail(evaluate(self.owner.case),self.start_bar.value,self.start_pitch.value)
            previous=deepcopy(self.owner.case.get('transverse_detail',empty_detail()))
            self._rebuild_order=True
            try:self._commit(detail,selected=detail['runs'][0]['id'])
            finally:self._rebuild_order=False
            self._previous_detail=previous;self.undo_start.disabled=False
            self.status.value=f'<small>Created {len(detail["runs"])} zone runs · #{self.start_bar.value} @ {self.start_pitch.value:g} in regular spacing. End gaps are fitted to minimum clear spacing with the first and last bars fixed. Zone-edge offsets use half the minimum clear gap, independent of Start c/c.</small>'
        self._attempt(perform)

    def _undo_start(self,_):
        if self._previous_detail is None:return
        def perform():
            self._commit(deepcopy(self._previous_detail))
            self._previous_detail=None;self.undo_start.disabled=True
            self.status.value='<small>Previous transverse layout restored.</small>'
        self._attempt(perform)

    def _add_zone(self,key):
        def perform():
            from .model import evaluate
            e=self.owner.current or evaluate(self.owner.case);c=self._empty_zones[key]
            run=new_zone_run(e,key,c['bar'].value,c['pitch'].value,allow_overlap=True)
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
            stations=run_stations(run);count=len(stations)
            if count<2:raise ValueError('A run needs at least two bars to split.')
            other=deepcopy(run);other['id']=self._next_id(detail);other['first_in']=stations[count//2]
            run['end_in']=stations[count//2-1]
            for r in (run,other):r['development_confirmed']=False;r.pop('development_fingerprint',None)
            detail['runs'].append(other);self._commit(detail,selected=other['id'])
        self._attempt(perform)

    def close(self):
        for card in self._cards.values():card.close()
        for header,box in self._zones.values():header.close();box.close()
        for controls in self._empty_zones.values():
            for widget in controls.values():widget.close()
        for widget in self._inspect_buttons.values():widget.close()
        for widget in (self.active,self.generate,self.start_bar,self.start_pitch,self.undo_start,self.add,self.status,self.zone_notice,self.zone_grid,self.zone_scroll,self.detail_area,self.selected_info,self.general,self.ui):widget.close()
