"""Independent spacing controls for the two added longitudinal-bar rows."""
from copy import deepcopy
import html
import ipywidgets as W
from .added_steel import layout_settings,validate_layout


class AddedSteelPanel:
    def __init__(self,owner):
        self.owner=owner;self.busy=False
        self.mode=W.Dropdown(options=[('Automatic gap filling','auto'),('Entered center spacing','spacing'),('Saved legacy spacing','legacy')],
            description='Layout',style={'description_width':'72px'},layout=W.Layout(width='270px'))
        self.rows={};children=[self.mode]
        for k in (1,2):
            controls={}
            for name,label in [('pitch_in',f'Row {k} c/c (in)'),('offset_in',f'Row {k} shift (in)')]:
                control=W.FloatText(step=.25,description=label,continuous_update=False,
                    style={'description_width':'130px'},layout=W.Layout(width='235px'))
                control.tooltip=('Center-to-center distance across cap width; entered exactly.' if name=='pitch_in' else 'Shift the row from cap center: positive toward the right; negative toward the left.')
                control.observe(self.changed,names='value');controls[name]=control;children.append(control)
            self.rows[k]=controls
        self.notice=W.HTML();children.append(W.HTML('<small>Spacing is across the cap width. Shift = offset from cap center. Conflicts stay visible for correction.</small>'));children.append(self.notice)
        self.ui=W.VBox(children);self.mode.observe(self.changed,names='value');self.sync()

    def sync(self):
        self.busy=True
        try:
            settings=layout_settings(self.owner.case)
            self.mode.options=[('Automatic gap filling','auto'),('Entered center spacing','spacing')]+([('Saved legacy spacing','legacy')] if settings['mode']=='legacy' else [])
            self.mode.value=settings['mode']
            for k,controls in self.rows.items():
                for name,control in controls.items():
                    control.value=settings['rows'][str(k)][name];control.disabled=settings['mode']!='spacing'
        finally:self.busy=False

    def changed(self,change):
        if self.busy or self.owner.busy:return
        candidate=deepcopy(self.owner.case)
        candidate['schema_version']=max(4,candidate['schema_version'])
        candidate['added_bar_layout']=dict(version=1,mode=self.mode.value,
            rows={str(k):{name:control.value for name,control in controls.items()} for k,controls in self.rows.items()})
        try:validate_layout(candidate)
        except ValueError as exc:
            self.notice.value='<span style="color:#bb3e39">Not applied: '+html.escape(str(exc))+'</span>';return
        self.owner.case=candidate;self.notice.value='';self.sync()
        self.owner._update_search_basis();self.owner.refresh();self.owner._notify_case_change()

    def close(self):
        for controls in self.rows.values():
            for control in controls.values():control.close()
        self.mode.close();self.notice.close();self.ui.close()
