"""Pile shape control for older saved cases and manual cap inputs."""
import html
import ipywidgets as W
from .pile_visual import pile_appearance,validate_pile_visual


class PileAppearancePanel:
    def __init__(self,owner):
        self.owner=owner;self.busy=False
        style={'description_width':'145px'};layout=W.Layout(width='336px')
        self.shape=W.Dropdown(options=[('Not specified','unknown'),('Square','square'),('Round solid','round'),('Pipe / round shell','pipe')],description='3D pile shape',style=style,layout=layout)
        self.wall=W.Text(description='Pipe wall (in)',placeholder='Unknown if blank',style=style,layout=W.Layout(width='336px'))
        self.filled=W.Dropdown(options=[('Unspecified',None),('Open pipe',False),('Concrete filled',True)],description='Pipe interior',style=style,layout=W.Layout(width='336px'))
        self.apply=W.Button(description='Apply pile appearance',icon='check',layout=W.Layout(width='220px'))
        self.status=W.HTML()
        self.ui=W.VBox([W.HTML('<b>Pile shape in the 3D view</b>'),self.shape,self.wall,self.filled,self.apply,self.status,
            W.HTML('<small>XML imports supply the shape and available wall/fill data. Older cases can be specified here. '
                   'This controls appearance; existing pile-clearance checks keep their rectangular envelope. Below-cap pile length is schematic.</small>')])
        self.shape.observe(self._shape_changed,names='value');self.apply.on_click(self._apply);self.sync()

    def _shape_changed(self,_):
        pipe=self.shape.value=='pipe';self.wall.disabled=self.filled.disabled=not pipe

    def sync(self):
        self.busy=True
        try:
            v=pile_appearance(self.owner.case);self.shape.value=v['shape']
            self.wall.value='' if v['wall_in'] is None else f'{v["wall_in"]:g}';self.filled.value=v['filled']
            self._shape_changed(None)
            self.status.value=f'<p>{html.escape(v["label"])} · {html.escape(v["description"])}<br><small>{html.escape(v["source"])}</small></p>'
        finally:self.busy=False

    def _apply(self,_):
        try:
            pipe=self.shape.value=='pipe'
            value=dict(version=1,shape=self.shape.value,wall_in=float(self.wall.value) if pipe and self.wall.value.strip() else None,
                       filled=self.filled.value if pipe else None,source='User-entered pile appearance')
            validate_pile_visual(dict(self.owner.case,pile_visual=value))
            self.owner.case['pile_visual']=value;self.sync();self.owner.refresh();self.owner._notify_case_change()
        except Exception as exc:self.status.value='<p style="color:#bb3e39">'+html.escape(str(exc))+'</p>'
