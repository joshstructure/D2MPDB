"""Steel inputs for mirrored U grids at either or both cap ends."""
from copy import deepcopy
from html import escape
import ipywidgets as W
from .end_grid import settings, validate, geometry


class EndGridPanel:
    def __init__(self,owner):
        self.owner=owner;self.busy=False;self.controls={};self.rows={}
        for key,label in [('enabled','Enable hooked end-face grid'),('left','Left end'),('right','Right end')]:
            self.controls[key]=W.Checkbox(description=label,indent=False,layout=W.Layout(width='240px'))
        self.controls['placement_mode']=W.Dropdown(options=[('Entered perimeter inset','manual'),('Equal spacing · bump conflicts','aligned')],
            description='Placement',style={'description_width':'90px'},layout=W.Layout(width='440px'))
        self.notice=W.HTML();self.readout=W.HTML()
        common=[]
        for key,label in [('face_offset_in','Extra end cover (in)'),('layer_clear_in','H/V layer clear (in)'),('perimeter_inset_in','Perimeter inset (in)')]:
            self.controls[key]=self.number(label);common.append(self.controls[key])
        families=[]
        for direction,title in [('horizontal','Horizontal across end width'),('vertical','Vertical across end depth')]:
            row={}
            row['bar']=W.Dropdown(options=[('#'+str(n),n) for n in range(3,12)],description='Bar size',layout=W.Layout(width='210px'))
            row['count']=W.BoundedIntText(min=0,max=40,description='Count / end',layout=W.Layout(width='235px'),continuous_update=False)
            row['hook_mode']=W.Dropdown(options=[('Standard 90° · automatic','standard'),('Custom dimensions','custom')],
                description='End hooks',layout=W.Layout(width='300px'))
            for key,label in [('spacing_in','c/c (in; 0=auto)'),('return_in','Straight return (in)'),('bend_diameter_in','Inside bend (in; 0=std)')]:
                row[key]=self.number(label)
            self.rows[direction]=row
            families.append(W.VBox([W.HTML('<b>'+title+'</b>'),W.HBox(list(row.values()),layout=W.Layout(flex_flow='row wrap'))]))
        for w in [*self.controls.values(),*(w for r in self.rows.values() for w in r.values())]:
            w.observe(self.changed,names='value')
        self.ui=W.VBox([W.HTML('<b>End-face hooked bar grids</b>'),W.HBox([self.controls[k] for k in ('enabled','left','right')],layout=W.Layout(flex_flow='row wrap')),
            self.controls['placement_mode'],*families,W.HBox(common,layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<small>Both ends share these settings and mirror inward. Counts are added U crosspieces per end. Auto spacing distributes them inside the perimeter; entered spacing centers the group. '
                   'Returns are straight lengths after the 90° bends. Horizontal crosspieces are the outer layer. Extra end cover is added to side/end cover; perimeter inset is added to side/top/bottom cover. '
                   'Standard 90° uses the general-bar minimum bend and a 12db straight tail at each end. These dimensions do not establish development length. '
                   'Equal spacing starts with evenly distributed bars inside the end stirrup and moves only conflicts beside the fixed longitudinal bars. Hook tails may touch or lap longitudinal bars; physical overlap fails. Other end-grid bars retain clear spacing. Entered spacing and perimeter inset are inactive in this mode; actual drawn spacings govern. '
                   'Geometry is a trial until fit, anchorage and pile clearance are reviewed.</small>'),self.notice,self.readout],
            layout=W.Layout(width='100%',padding='8px',border='1px solid #c4cdd6'))
        self.sync()

    @staticmethod
    def number(label):
        return W.FloatText(description=label,step=.25,continuous_update=False,style={'description_width':'165px'},layout=W.Layout(width='275px'))

    def sync(self):
        self.busy=True
        try:
            s=settings(self.owner.case)
            for k,w in self.controls.items(): w.value=s[k]
            for direction,row in self.rows.items():
                for k,w in row.items(): w.value=s[direction][k]
            self.hook_controls()
        finally:self.busy=False

    def hook_controls(self):
        from .model import BAR_DIAMETER
        from .end_grid import minimum_bend
        for row in self.rows.values():
            standard=row['hook_mode'].value=='standard'
            for key in ('return_in','bend_diameter_in'):row[key].disabled=standard
            if standard:
                row['return_in'].value=12*BAR_DIAMETER[row['bar'].value]
                row['bend_diameter_in'].value=minimum_bend(row['bar'].value)
        self.controls['perimeter_inset_in'].disabled=self.controls['placement_mode'].value=='aligned'
        for row in self.rows.values():row['spacing_in'].disabled=self.controls['placement_mode'].value=='aligned'

    def changed(self,_):
        if self.busy or self.owner.busy:return
        self.busy=True
        try:self.hook_controls()
        finally:self.busy=False
        candidate=deepcopy(self.owner.case);candidate['schema_version']=5
        candidate['end_face_grid']=dict(version=2,**{k:w.value for k,w in self.controls.items()},
            **{direction:{k:w.value for k,w in row.items()} for direction,row in self.rows.items()})
        try:validate(candidate)
        except ValueError as exc:
            self.notice.value='<span style="color:#bb3e39">Not applied: '+escape(str(exc))+'</span>';return
        self.notice.value='';self.owner.case=candidate
        self.owner._update_search_basis();self.owner.refresh();self.owner._notify_case_change()

    def refresh(self,e):
        bars=geometry(e)
        values=[]
        for direction in ('horizontal','vertical'):
            group=[b for b in bars if b['direction']==direction]
            if group:
                b=group[0];one=[v for v in group if v['end']==b['end']]
                gaps=[v['coordinate_in']-u['coordinate_in'] for u,v in zip(one,one[1:])]
                pitch=f'{min(gaps):.3f}–{max(gaps):.3f}' if gaps else 'single bar'
                values.append(f'{direction.title()}: actual c/c {pitch} in; max stagger {max(abs(v["shift_in"]) for v in group):.3f} in; hook tail {b["return_in"]:g} in')
                if not b['placement_ok']:values.append('FIT FAILED: '+b['placement_note'])
        self.readout.value='<small>'+escape(' · '.join(values))+'</small>'

    def close(self):
        for w in [*self.controls.values(),*(w for r in self.rows.values() for w in r.values()),self.notice,self.readout,self.ui]:w.close()
