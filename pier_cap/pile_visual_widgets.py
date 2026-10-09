"""Pile shape control for older saved cases and manual cap inputs."""
import html
import ipywidgets as W
from .pile_visual import pile_appearance,validate_pile_visual


class PileAppearancePanel:
    def __init__(self,owner):
        self.owner=owner;self.busy=False
        style={'description_width':'105px'};layout=W.Layout(width='270px',max_width='calc(100% - 4px)')
        self.shape=W.Dropdown(options=[('Not specified','unknown'),('Square','square'),('Round solid','round'),('Pipe / round shell','pipe')],description='3D pile shape',style=style,layout=layout)
        self.wall=W.Text(description='Pipe wall (in)',placeholder='Unknown',style=style,layout=W.Layout(width='210px'))
        self.filled=W.Dropdown(options=[('Unspecified',None),('Open pipe',False),('Concrete filled',True)],description='Pipe interior',style=style,layout=W.Layout(width='250px'))
        self.apply=W.Button(description='Apply pile appearance',icon='check',layout=W.Layout(width='220px'))
        self.status=W.HTML()
        self.shape.tooltip='Appearance only; pile-clearance checks retain their rectangular envelope. Below-cap length is schematic.'
        self.wall.tooltip='Pipe wall thickness in inches. Leave blank if unknown.'
        self.ui=W.VBox([W.HTML('<b>Pile shape in the 3D view</b>'),
            W.HBox([self.shape,self.wall,self.filled,self.apply],layout=W.Layout(width='100%',flex_flow='row wrap')),self.status],
            layout=W.Layout(width='100%',min_width='0',flex='0 0 auto',padding='8px',border='1px solid #c4cdd6'))
        self.shape.observe(self._shape_changed,names='value');self.apply.on_click(self._apply);self.sync()

    def _shape_changed(self,_):
        pipe=self.shape.value=='pipe';self.wall.disabled=self.filled.disabled=not pipe

    def sync(self):
        self.busy=True
        try:
            v=pile_appearance(self.owner.case);self.shape.value=v['shape']
            self.wall.value='' if v['wall_in'] is None else f'{v["wall_in"]:g}';self.filled.value=v['filled']
            self._shape_changed(None)
            self.status.value=f'<small>{html.escape(v["label"])} · {html.escape(v["source"])}</small>'
        finally:self.busy=False

    def _apply(self,_):
        try:
            pipe=self.shape.value=='pipe'
            value=dict(version=1,shape=self.shape.value,wall_in=float(self.wall.value) if pipe and self.wall.value.strip() else None,
                       filled=self.filled.value if pipe else None,source='User-entered pile appearance')
            validate_pile_visual(dict(self.owner.case,pile_visual=value))
            self.owner.case['pile_visual']=value;self.sync();self.owner.refresh();self.owner._notify_case_change()
        except Exception as exc:self.status.value='<p style="color:#bb3e39">'+html.escape(str(exc))+'</p>'
