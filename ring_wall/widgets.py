"""Cap-style notebook workbench: edit, inspect, recalculate, then export."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

import ipywidgets as W
from IPython.display import display

from .model import BAR, analyze, default_case, validate
from .report import cone_section, esc, export_results, plan, STYLE
from .cone import geometry as cone_geometry
from .study import spacing_study
from .ui_support import Accordion, FigureWidget, Tab, update_figure
from . import views as V


GROUPS = {
    'Wall & loads': [
        ('Wall and piles', [('length_in','Wall length (in)'),('thickness_in','Wall thickness (in)'),('height_in','Wall height (in)'),
                            ('pile_count','Pile count'),('pile_spacing_in','Pile centers (in)'),('pile_od_in','Pile OD (in)'),
                            ('pile_t_effective_in','Effective pipe wall (in)'),('placement_tolerance_in','Pile tolerance (in)')]),
        ('Materials and gravity', [('fc_ksi','Concrete f′c (ksi)'),('fy_ksi','Rebar fy (ksi)'),('density_kcf','Concrete weight (kcf)'),
                                   ('gamma_dc','Self-weight factor'),('additional_service_ksf','Added service gravity (ksf)'),('gamma_additional','Added gravity factor')])],
    'Reinforcement': [
        ('Minimum grid and matching end U-bars', [('cover_in','Clear cover (in)'),('aggregate_in','Max aggregate (in)'),('grid_bar','Grid / U-bar size'),
                                                 ('auto_grid_spacing','Select grid spacing automatically'),('grid_spacing_in','Manual grid pitch (in)'),
                                                 ('spacing_increment_in','Pitch increment (in)'),('u_leg_in','U-bar straight leg (in)'),('coating','Bar coating')]),
        ('Additional ties and collectors', [('primary_bar','Primary bar size'),('primary_bars_per_face','Tie bars per face'),('hanger_bars_per_face','Collector bars per face'),
                                           ('transverse_bar','Transverse bar size'),('transverse_spacing_in','Transverse pitch (in)')])],
    'Rings & STM': [
        ('Support / transfer model', [('support_model','STM support model'),('cone_slope_hv','Cone spread (H:1 V)')]),
        ('Ring layout and steel', [('first_ring_in','First ring top (in)'),('ring_spacing_in','Vertical ring pitch (in)'),('ring_count','Ring rows'),
                                   ('ring_id_in','Ring ID (in)'),('ring_od_in','Ring OD (in)'),('ring_t_in','Ring thickness (in)'),('ring_fy_ksi','Ring steel fy (ksi)')]),
        ('Arch and equivalent node', [('arch_rise_in','Arch rise (in)'),('arch_panels','Arch segments (even)'),('tie_offset_in','Tie above node base (in)'),
                                     ('node_height_in','Node height (in)'),('node_width_in','Equivalent node width (in)'),('bearing_fraction','Effective bearing fraction')])],
    'Factors': [('Resistance factors', [('phi_tie','Tie resistance factor'),('phi_concrete','Concrete resistance factor'),('phi_plate','Plate screening factor')])],
}


class RingWallNotebook:
    def __init__(self, case=None, export_root='ring_wall_exports'):
        self.case=deepcopy(default_case() if case is None else case)
        self.case.setdefault('support_model','ring_centers');self.case.setdefault('cone_slope_hv',1.5)
        self.export_root=Path(export_root)
        self.current=None; self.study=None; self.dirty=True; self.busy=False
        self.last_export=None; self.figures={}; self.controls={}
        self.status=W.HTML(); self.metrics=W.HTML(); self.export_status=W.HTML(); self.download_output=W.HTML();self.download_area=W.Output()
        self.recalc_button=W.Button(description='Recalc',button_style='danger',icon='refresh',layout=W.Layout(width='158px',height='36px'))
        self.recalc_button.add_class('ring-recalc'); self.recalc_button.on_click(self._recalc_clicked)
        self.title=W.Text(value=self.case['title'],description='Case title',layout=W.Layout(width='95%'))
        self.controls['title']=self.title
        self.title.observe(lambda c:self._changed('title',c),names='value')
        self.input_tabs=self._inputs()
        self.input_panel=Accordion(children=[self.input_tabs]);self.input_panel.set_title(0,'Inputs · wall, reinforcement, rings and factors');self.input_panel.selected_index=None
        self.row_filter=W.Dropdown(options=[('All rows',0)],value=0,description='Ring row')
        self.row_filter.observe(self._row_changed,names='value')
        self.check_view=W.Dropdown(options=[('All checks','all'),('Largest D/C first','dc'),('Failures first','fail_first'),('Failures only','fail'),('Pending only','pending')],
                                   value='all',description='View',layout=W.Layout(width='280px'))
        self.check_view.observe(self._checks_changed,names='value')
        self.layout_panel=W.VBox(); self.rings_panel=W.VBox(); self.forces_panel=W.VBox()
        self.steel_panel=W.HTML(); self.checks_panel=W.HTML(); self.spacing_panel=W.VBox()
        self.cone_panel=W.VBox();self.cone_values=W.HTML()
        self.ring_values=W.HTML(); self.force_values=W.HTML(); self.spacing_values=W.HTML()
        self.plot_tabs=Tab(children=[self.layout_panel,self.cone_panel,W.VBox([self.row_filter,self.rings_panel]),self.forces_panel,
                                    self.steel_panel,W.VBox([self.check_view,self.checks_panel]),self.spacing_panel])
        for i,title in enumerate(['Live layout','Cone transfer','Ring forces','Struts & ties','Reinforcement','D/C checks','Ring spacing']):
            self.plot_tabs.set_title(i,title)
        self.plot_tabs.observe(self._tab_changed,names='selected_index')
        self.report_button=W.Button(description='Generate calculation report',icon='file-text-o',button_style='info',layout=W.Layout(width='250px'))
        self.bundle_button=W.Button(description='Export case + checks ZIP',icon='download',button_style='success',layout=W.Layout(width='240px'))
        self.report_button.on_click(lambda _:self._export_clicked('html'))
        self.bundle_button.on_click(lambda _:self._export_clicked('zip'))
        self.saved_html_button=W.Button(description='Download saved HTML report',icon='download',disabled=True,layout=W.Layout(width='250px'))
        self.saved_zip_button=W.Button(description='Download saved ZIP',icon='download',disabled=True,layout=W.Layout(width='240px'))
        self.saved_html_button.on_click(lambda _:self._download_clicked('html'))
        self.saved_zip_button.on_click(lambda _:self._download_clicked('zip'))
        self.upload=W.FileUpload(accept='.json',multiple=False,description='Load saved case')
        self.upload.observe(self._uploaded,names='value')
        self.load_status=W.HTML()
        export_box=W.VBox([W.HTML(V.note('Work in the tabs above. Generate a report only when ready. Exports require current calculated results. '
                                        'Saved-download buttons refer to the most recent successful export, even after inputs change.')),
                           W.HBox([self.report_button,self.bundle_button],layout=W.Layout(flex_flow='row wrap')),
                           W.HBox([self.saved_html_button,self.saved_zip_button],layout=W.Layout(flex_flow='row wrap')),
                           self.export_status,self.download_output,self.download_area])
        self.export_panel=Accordion(children=[export_box]); self.export_panel.set_title(0,'Report and exports'); self.export_panel.selected_index=None
        dock=W.Box([self.recalc_button],layout=W.Layout(width='100%')); dock.add_class('ring-dock')
        intro=W.HTML('<h2 style="padding-right:170px;margin:6px 0">Ring-supported wall · STM workbench</h2>'
                     '<p>Edit inputs and inspect the live layout. Click <b>Recalc</b> to update the plots and output tables. '
                     'Green <b>Calc done</b> means results are current; it does not mean the design passes.</p>')
        self.ui=W.VBox([W.HTML(V.CSS),dock,intro,self.title,self.upload,self.load_status,self.input_panel,self.status,self.metrics,self.plot_tabs,self.export_panel],
                       layout=W.Layout(width='100%',min_width='0',max_height='900px',overflow='auto'))
        self.ui.add_class('ring-workbench')
        self._refresh_inputs()
        self.recalculate()

    def _inputs(self):
        tabs=[]
        for group,sections in GROUPS.items():
            cards=[]
            for title,fields in sections:
                controls=[]
                for key,label in fields:
                    value=self.case[key]
                    if isinstance(value,bool): widget=W.Checkbox(value=value,indent=False)
                    elif key.endswith('_bar'): widget=W.Dropdown(options=[(f'#{n}',n) for n in BAR],value=value)
                    elif key=='coating': widget=W.Dropdown(options=['uncoated','epoxy','unknown'],value=value)
                    elif key=='support_model': widget=W.Dropdown(options=[('Broad-face cone transfer (trial)','face_transfer'),('Original ring level','ring_centers')],value=value)
                    elif isinstance(value,int): widget=W.IntText(value=value)
                    else: widget=W.FloatText(value=value,step=.25)
                    widget.description=label;widget.style.description_width='190px'
                    widget.layout=W.Layout(width='310px',max_width='100%',height='auto',min_height='30px')
                    widget.observe(lambda c,k=key:self._changed(k,c),names='value')
                    self.controls[key]=widget;controls.append(widget)
                card=W.VBox([W.HTML('<b>'+title+'</b>'),W.HBox(controls,layout=W.Layout(flex_flow='row wrap',grid_gap='6px',width='100%'))])
                card.add_class('ring-section');cards.append(card)
            tabs.append(W.VBox(cards))
        result=Tab(children=tabs)
        for i,title in enumerate(GROUPS):result.set_title(i,title)
        return result

    def _refresh_inputs(self):
        self.controls['grid_spacing_in'].disabled=self.case['auto_grid_spacing']

    def _state(self, state):
        label,color,disabled={'dirty':('Recalc','danger',False),'done':('Calc done','success',True),
                              'running':('Calculating…','warning',True),'error':('Retry calc','danger',False),
                              'invalid':('Check inputs','danger',True)}[state]
        self.recalc_button.description=label;self.recalc_button.button_style=color;self.recalc_button.disabled=disabled
        self.report_button.disabled=self.bundle_button.disabled=(state!='done')

    def _figure(self, name, fresh):
        if name not in self.figures:self.figures[name]=FigureWidget(fresh)
        else:update_figure(self.figures[name],fresh)
        return self.figures[name]

    def _live_layout(self):
        fig=self._figure('layout',V.layout_figure(self.case))
        self.layout_panel.children=(fig,W.HTML(V.note('Current input geometry. The paths are equivalent 2-D representations; real concrete paths around hollow piles remain open. '
                                                                     'Dashed red is the ring plus pile-placement tolerance. The U-bar is schematic.')))
        cone=cone_geometry(self.case)
        self.cone_values.value=V.note(f'Current envelope: {cone["slope_hv"]:g} H:1 V ({cone["angle_deg"]:.2f}° from horizontal). '
                                     f'First broad-face contact: {cone["face_rise_in"]:.3f} in above the ring. '
                                     'Recalc for transfer-force tables. Surface nodes are reference locations; interior node geometry, cover and anchorage remain open.',status=True)
        self.cone_panel.children=(self._figure('cone',V.cone_figure(self.case)),self.cone_values)

    def _invalidate(self):
        self.current=None;self.study=None;self.dirty=True;self.metrics.value=''
        stale=V.note('Results need Recalc for the current inputs.',status=True)
        for panel in (self.rings_panel,self.forces_panel,self.spacing_panel):panel.children=(W.HTML(stale),)
        for panel in (self.ring_values,self.force_values,self.spacing_values,self.steel_panel,self.checks_panel,self.cone_values):panel.value=stale
        self.row_filter.disabled=self.check_view.disabled=True
        self._state('dirty')
        if self.last_export:self.export_status.value=V.note('Inputs changed. Saved downloads still contain the previous export. Recalc, then generate again for the current case.',status=True)

    def _changed(self,key,change):
        if self.busy:return
        self.case[key]=change['new'];self._refresh_inputs();self._invalidate()
        try:
            validate(self.case);self._live_layout()
        except (ValueError,TypeError,KeyError) as exc:
            self.status.value=V.note('<b>Check inputs:</b> '+esc(exc),status=True)
            self.layout_panel.children=(W.HTML(self.status.value),);self.cone_panel.children=(W.HTML(self.status.value),);self._state('invalid')
        else:self.status.value=V.note('<b>Recalc needed.</b> The drawing shows current inputs. Calculated outputs are cleared until Recalc.',status=True)

    def _has_current(self):
        return not self.dirty and self.current is not None and self.current['case']==self.case

    def recalculate(self):
        if self.busy:return
        self._invalidate();self.busy=True;self._state('running')
        try:
            result=analyze(self.case)
            study=spacing_study(result['case'])
            self._live_layout()
            reactions=self._figure('reactions',V.reaction_figure(result))
            forces=self._figure('forces',V.force_figure(result))
            spacing=self._figure('spacing',V.spacing_figure(study))
            self.current=result;self.study=study;self.dirty=False
            self.row_filter.options=[('All rows',0)]+[(f'Row {a["row"]} · {a["z"]:g} in',a['row']) for a in result['rows']]
            self.row_filter.value=0;self.row_filter.disabled=self.check_view.disabled=False
            self.ring_values.value=V.ring_table(result)
            self.force_values.value=V.force_table(result)
            self.spacing_values.value=V.spacing_table(study)
            self.rings_panel.children=(reactions,self.ring_values,W.HTML(V.note('Bearing, plate and weld-line demands are screens and force handoffs. Weld, splice, pipe-shell and 3-D concrete design remain open.')))
            self.forces_panel.children=(forces,self.force_values,W.HTML(V.working_table(['Equilibrium check','Residual'],[
                ['Force',f'{result["totals"]["force_error"]:.3e} kip'],['Moment',f'{result["totals"]["moment_error"]:.3e} kip-in'],['Arch joint',f'{result["totals"]["joint_error"]:.3e} kip']])))
            self.steel_panel.value=V.steel_table(result)+plan(result)
            self.cone_values.value=cone_section(result)
            self.checks_panel.value=V.checks_table(result,self.check_view.value)
            self.spacing_panel.children=(W.HTML(V.note('Top row counts leave room for the entered arch. The first ring, section and rise stay fixed. '
                'Each option recalculates its grid; a short terminal band can govern. This is a strength allocation study, not proof of row engagement.')),
                                         spacing,self.spacing_values)
            self.metrics.value=V.summary(result)
            self.status.value=V.note('<b>'+esc(result['overall'])+'</b> · Calculated outputs match the current inputs. Individual PASS results apply only to their named checks.',status=True)
            self._state('done')
        except Exception as exc:
            self._invalidate();self.status.value=V.note('<b>Calculation stopped:</b> '+esc(exc),status=True);self._state('error')
            raise
        finally:self.busy=False
        return self.current

    def _recalc_clicked(self,_):
        try:self.recalculate()
        except Exception:pass  # The failure and stale-output state are already visible.

    def _row_changed(self,_):
        if self._has_current():self.ring_values.value=V.ring_table(self.current,self.row_filter.value)

    def _checks_changed(self,_):
        if self._has_current():self.checks_panel.value=V.checks_table(self.current,self.check_view.value)

    def _tab_changed(self,_):
        for figure in self.figures.values():
            figure.layout.autosize=False;figure.layout.autosize=True

    def load_case(self,case):
        if isinstance(case,dict):
            case=deepcopy(case)
            case.setdefault('support_model','ring_centers');case.setdefault('cone_slope_hv',1.5)
        if not isinstance(case,dict) or set(case)!=set(default_case()):
            raise ValueError('Load a ring_wall_case.json with the complete ring-wall inputs.')
        validate(case)
        # Validate widget values before changing the active case (JSON booleans,
        # counts and supported selectors must retain their intended types).
        for key,control in self.controls.items():
            if type(case[key]) is not type(default_case()[key]) and not (type(default_case()[key]) is float and type(case[key]) in (int,float)):
                raise ValueError(f'{key}: unsupported input type.')
        self.busy=True
        try:
            self.case=deepcopy(case)
            for key,control in self.controls.items():control.value=case[key]
        finally:self.busy=False
        self._changed('title',{'new':self.case['title']})

    def _uploaded(self,change):
        try:
            value=change['new'];item=next(iter(value.values())) if isinstance(value,dict) else value[0]
            self.load_case(json.loads(bytes(item['content']).decode('utf-8-sig')))
            self.load_status.value=V.note('Saved case loaded. Inspect the drawing and click Recalc.')
        except Exception as exc:self.load_status.value=V.note('Case was not loaded: '+esc(exc),status=True)

    def export(self):
        if self.busy or not self._has_current():
            raise RuntimeError('Current inputs differ from calculated results. Recalc before export.')
        folder=self.export_root/datetime.now(timezone.utc).strftime('ring-wall-%Y%m%d-%H%M%S-%f')
        folder.mkdir(parents=True,exist_ok=False)
        paths=export_results(self.current,folder)
        study_json=folder/'ring_spacing_study.json';study_json.write_text(json.dumps(self.study,indent=2,allow_nan=False),encoding='utf-8')
        study_html=folder/'ring_spacing_study.html'
        study_html.write_text('<!doctype html><html><head><meta charset="utf-8"><title>Ring-spacing comparison</title><style>'+STYLE+'</style></head><body>'
                              '<h1>Ring-spacing comparison</h1><p>Assumed strength allocation; compatibility and connection checks remain open.</p>'+V.spacing_table(self.study)+'</body></html>',encoding='utf-8')
        bundle=folder/'Ring_Wall_STM_Exports.zip'
        with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in paths+[study_json,study_html]:archive.write(path,path.name)
        self.last_export=folder.resolve()
        self.saved_html_button.disabled=self.saved_zip_button.disabled=False
        self.export_status.value=V.note('Export saved from the current calculation. Use the download buttons to save a copy on your computer.')
        return self.last_export

    def _export_clicked(self,kind):
        try:self.export()
        except Exception as exc:self.export_status.value=V.note('Export stopped: '+esc(exc),status=True)
        else:self._download_clicked(kind)

    def _download_clicked(self,kind):
        try:self.download(kind)
        except Exception as exc:self.export_status.value=V.note('Export saved; download needs retry: '+esc(exc),status=True)

    def download(self,kind):
        if self.last_export is None:raise RuntimeError('Generate an export first.')
        name,mime={'html':('ring_wall_report.html','text/html'),'zip':('Ring_Wall_STM_Exports.zip','application/zip')}[kind]
        path=self.last_export/name
        try:from google.colab import files
        except ImportError:
            payload=base64.b64encode(path.read_bytes()).decode('ascii')
            self.download_output.value=f'<a download="{name}" href="data:{mime};base64,{payload}">Download {name}</a>'
        else:
            with self.download_area:files.download(str(path))
        self.export_status.value=V.note('Saved export: <b>'+esc(self.last_export.name)+'</b>. '+
                                       ('These are previous inputs; Recalc and generate again for the current case. ' if not self._has_current() else '')+
                                       'Check your browser Downloads list after saving the file.')
        return path

    def display(self):
        for figure in self.figures.values():figure.prepare_display()
        display(self.ui)

    def close(self):
        seen=set()
        def close(widget):
            if id(widget) in seen:return
            seen.add(id(widget))
            for child in getattr(widget,'children',()):close(child)
            widget.close()
        close(self.ui)
        for widget in self.figures.values():close(widget)
