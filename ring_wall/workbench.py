"""Cap-style manual Recalc workbench with current-result export gates."""
import base64
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import ipywidgets as W
from IPython.display import display
from .model import BAR,analyze,default_case,upgrade_case,validate
from .output import esc,export_results
from .study import spacing_study
from .ui_support import Accordion,FigureWidget,PanelTabs,update_figure
from . import plots as V

GROUPS={
 'Wall & loads':[
  ('Geometry',[('length_in','Wall length (in)'),('thickness_in','Wall thickness (in)'),('height_in','Wall height (in)'),('pile_count','Pile count'),('pile_spacing_in','Pile pitch (in)'),('pile_od_in','Pile OD (in)'),('placement_tolerance_in','Radial pile tolerance (in)')]),
  ('Concrete self-weight',[('fc_ksi','Concrete f′c (ksi)'),('density_kcf','Concrete density (kcf)'),('gamma_dc','Self-weight factor')]),
  ('Pile stiffness · ring moment basis (D-070)',[('pile_e_ksi','Pipe E (ksi)'),('pile_free_length_in','Wall bottom to fixity (in)'),('pile_axial_length_in','Axial spring length (in)'),('imposed_rotation_rad','Imposed wall rotation (rad)')])],
 'Wall steel':[
  ('Minimum grid · each way / each face',[('fy_ksi','Rebar fy (ksi)'),('grid_bar','Grid / U-bar size'),('auto_grid_spacing','Select pitch automatically'),('grid_spacing_in','Manual grid pitch (in)'),('spacing_increment_in','Auto pitch increment (in)'),('project_max_spacing_in','Project max pitch (in)')]),
  ('Detailing',[('cover_in','Provided cover (in)'),('required_cover_in','Required cover (in)'),('aggregate_in','Aggregate size (in)'),('u_leg_in','U straight lap leg (in)'),('vertical_lap_in','Vertical lap (in)'),('coating','Bar coating')])],
 'Rings & welds':[
  ('Annular rings',[('first_ring_in','First ring top (in)'),('ring_spacing_in','Vertical ring pitch (in)'),('ring_count','Ring rows'),('ring_id_in','Ring ID (in)'),('ring_od_in','Ring OD (in)'),('ring_t_in','Ring thickness (in)'),('ring_fy_ksi','Ring Fy (ksi)'),('ring_fu_ksi','Ring Fu (ksi)')]),
  ('Continuous fillets above and below each plate',[('weld_leg_in','Fillet leg size (in)'),('weld_fexx_ksi','Weld FEXX (ksi)'),('pile_t_effective_in','Effective pipe wall (in)'),('pile_fy_ksi','Pipe Fy (ksi)'),('pile_fu_ksi','Pipe Fu (ksi)')])],
 'Factors':[('Resistance factors',[('phi_concrete','Concrete bearing φ'),('phi_plate','Plate flexure φ'),('phi_weld','Weld metal φ'),('phi_shear_yield','Shear yielding φ'),('phi_shear_rupture','Shear rupture φ')])]}
EXPORTS={'html':('ring_wall_report.html','text/html'),'zip':('Ring_Wall_Design_Exports.zip','application/zip'),
 'case':('ring_wall_case.json','application/json'),'checks':('ring_wall_checks.csv','text/csv'),
 'rings':('ring_wall_ring_forces.csv','text/csv'),'mathcad':('ring_wall_design.xmcd','application/xml'),
 'blockpad':('Ring Supported Wall Design.bpad','application/octet-stream'),'source':('ring_wall_source.zip','application/zip')}


class RingWallNotebook:
    def __init__(self,case=None,export_root='ring_wall_exports'):
        self.case,self.migration=upgrade_case(case);self.export_root=Path(export_root)
        self.current=None;self.study=None;self.dirty=True;self.busy=False;self.last_export=None;self.figures={};self.controls={}
        self.status=W.HTML();self.metrics=W.HTML();self.export_status=W.HTML();self.download_output=W.HTML();self.download_area=W.Output();self.load_status=W.HTML()
        self.recalc_button=W.Button(description='Recalc',button_style='danger',icon='refresh',layout=W.Layout(width='150px',height='36px'))
        self.recalc_button.add_class('ring-recalc');self.recalc_button.on_click(lambda _:self._recalc_clicked())
        self.title=W.Text(value=self.case['title'],description='Case title',layout=W.Layout(width='95%'));self.controls['title']=self.title
        self.title.observe(lambda c:self._changed('title',c),names='value')
        self.input_tabs=self._inputs();self.input_panel=Accordion(children=[self.input_tabs]);self.input_panel.set_title(0,'Inputs · wall, steel, rings and welds');self.input_panel.selected_index=None
        self.row_filter=W.Dropdown(options=[('All rows',0)],value=0,description='Ring row');self.row_filter.observe(lambda _:self._row_changed(),names='value')
        self.check_view=W.Dropdown(options=[('All checks','all'),('Largest D/C first','dc'),('Failures first','fail_first'),('Failures only','fail'),('Pending only','pending')],description='View',layout=W.Layout(width='280px'))
        self.check_view.observe(lambda _:self._checks_changed(),names='value')
        self.layout_panel=W.VBox();self.cage_panel=W.VBox();self.rings_panel=W.VBox();self.connection_panel=W.VBox();self.spacing_panel=W.VBox()
        self.steel_panel=W.HTML();self.checks_panel=W.HTML();self.ring_values=W.HTML();self.spacing_values=W.HTML()
        self.plot_tabs=PanelTabs([self.layout_panel,self.cage_panel,W.VBox([self.row_filter,self.rings_panel]),self.connection_panel,self.steel_panel,W.VBox([self.check_view,self.checks_panel]),self.spacing_panel],
            ['Live layout','3D reinforcement','Tributary loads','Ring & weld detail','Wall steel','D/C checks','Ring spacing'])
        self.plot_tabs.observe(self._tab_changed,names='selected_index')
        self.export_buttons={}
        for kind,label in [('html','Generate calculation report'),('case','Save case JSON'),('checks','Checks CSV'),('rings','Ring loads CSV'),('mathcad','Export Mathcad (.xmcd)'),('blockpad','Export Blockpad (.bpad)'),('source','Calculation source ZIP'),('zip','Full export bundle ZIP')]:
            b=W.Button(description=label,icon='download',layout=W.Layout(width='240px'));b.on_click(lambda _,k=kind:self._export_clicked(k));self.export_buttons[kind]=b
        self.report_button=self.export_buttons['html'];self.bundle_button=self.export_buttons['zip']
        self.saved_html_button=W.Button(description='Download saved HTML report',disabled=True,layout=W.Layout(width='250px'))
        self.saved_zip_button=W.Button(description='Download saved ZIP',disabled=True,layout=W.Layout(width='240px'))
        self.saved_html_button.on_click(lambda _:self._download_clicked('html'));self.saved_zip_button.on_click(lambda _:self._download_clicked('zip'))
        export_box=W.VBox([W.HTML(V.note('Exports use the current completed Recalc. The HTML report explains each check family once, with readable equations, individual schematic/substitution dropdowns and tables for all locations. '
            'Native sheets contain formulas for the exported layout, with a verification record in the full ZIP. Source ZIP preserves the calculation code. '
            'Regenerate native sheets after changing layout counts, bar size/coating or automatic spacing.')),
            W.HBox(list(self.export_buttons.values()),layout=W.Layout(flex_flow='row wrap',grid_gap='6px')),
            W.HBox([self.saved_html_button,self.saved_zip_button],layout=W.Layout(flex_flow='row wrap')),self.export_status,self.download_output,self.download_area])
        self.export_panel=Accordion(children=[export_box]);self.export_panel.set_title(0,'Report and exports');self.export_panel.selected_index=None
        self.upload=W.FileUpload(accept='.json',multiple=False,description='Load saved case');self.upload.observe(self._uploaded,names='value')
        dock=W.Box([self.recalc_button],layout=W.Layout(width='100%'));dock.add_class('ring-dock')
        self.ui=W.VBox([W.HTML(V.CSS),dock,W.HTML('<h2 style="padding-right:165px">Pier Wall Design</h2><p>Edit inputs, inspect the drawings, then click <b>Recalc</b>. Green means current results; each check has its own status.</p>'),
            self.title,self.upload,self.load_status,self.input_panel,self.status,self.metrics,self.plot_tabs,self.export_panel],layout=W.Layout(width='100%',min_width='0',max_height='950px',overflow='auto'))
        self.ui.add_class('ring-workbench');self._refresh_inputs();self.recalculate()
        if self.migration:self.load_status.value=V.note(esc(' '.join(self.migration)),True)

    def _inputs(self):
        tabs=[]
        for group,sections in GROUPS.items():
            cards=[]
            for title,fields in sections:
                controls=[]
                for key,label in fields:
                    value=self.case[key]
                    if type(value) is bool:w=W.Checkbox(value=value,indent=False)
                    elif key=='grid_bar':w=W.Dropdown(options=[(f'#{n}',n) for n in BAR],value=value)
                    elif key=='coating':w=W.Dropdown(options=['uncoated','epoxy','unknown'],value=value)
                    elif type(value) is int:w=W.IntText(value=value)
                    else:w=W.FloatText(value=value,step=.0625 if key=='weld_leg_in' else .0001 if key.endswith('_rad') else .25)
                    w.description=label;w.style.description_width='180px';w.layout=W.Layout(width='320px',max_width='100%',height='auto',min_height='32px')
                    w.observe(lambda c,k=key:self._changed(k,c),names='value');self.controls[key]=w;controls.append(w)
                card=W.VBox([W.HTML('<b>'+title+'</b>'),W.HBox(controls,layout=W.Layout(flex_flow='row wrap',grid_gap='6px'))]);card.add_class('ring-section');cards.append(card)
            tabs.append(W.VBox(cards))
        return PanelTabs(tabs,list(GROUPS))

    def _refresh_inputs(self):self.controls['grid_spacing_in'].disabled=self.case['auto_grid_spacing']
    def _state(self,state):
        label,color,disabled={'dirty':('Recalc','danger',False),'done':('Calc done','success',True),'running':('Calculating…','warning',True),'error':('Retry calc','danger',False),'invalid':('Check inputs','danger',True)}[state]
        self.recalc_button.description=label;self.recalc_button.button_style=color;self.recalc_button.disabled=disabled
        for b in self.export_buttons.values():b.disabled=state!='done'
    def _figure(self,name,fresh):
        if name not in self.figures:self.figures[name]=FigureWidget(fresh)
        else:update_figure(self.figures[name],fresh)
        return self.figures[name]
    def _live_layout(self):
        self.layout_panel.children=(self._figure('layout',V.layout_figure(self.case)),W.HTML(V.note('Current input geometry. Blue dotted lines bound the assigned tributary cells. Red dashed plan outlines include pile tolerance.')))
        self.cage_panel.children=(self._figure('cage',V.cage_figure(self.case)),W.HTML(V.note('Rotate, zoom, or select a standard view. Use the legend to hide concrete, rings or a bar family. Centerline schematic; final bends, laps and anchorage routing require detailing.')))
    def _invalidate(self):
        self.current=None;self.study=None;self.dirty=True;self.metrics.value=''
        stale=V.note('Results need Recalc for the current inputs.',True)
        for panel in (self.rings_panel,self.connection_panel,self.spacing_panel):panel.children=(W.HTML(stale),)
        for panel in (self.ring_values,self.spacing_values,self.steel_panel,self.checks_panel):panel.value=stale
        self.row_filter.disabled=self.check_view.disabled=True;self._state('dirty')
        if self.last_export:self.export_status.value=V.note('Inputs changed. Saved downloads retain the previous export. Recalc and export again for the current case.',True)
    def _changed(self,key,change):
        if self.busy:return
        self.case[key]=change['new'];self._refresh_inputs();self._invalidate()
        try:validate(self.case);self._live_layout()
        except (ValueError,TypeError,KeyError) as exc:
            self.status.value=V.note('Check inputs: '+esc(exc),True);self.layout_panel.children=(W.HTML(self.status.value),);self.cage_panel.children=(W.HTML(self.status.value),);self._state('invalid')
        else:self.status.value=V.note('Recalc needed. Drawings show current inputs; calculated results are cleared.',True)
    def _has_current(self):return not self.dirty and self.current is not None and self.current['case']==self.case
    def recalculate(self):
        if self.busy:return
        self._invalidate();self.busy=True;self._state('running')
        try:
            r=analyze(self.case);study=spacing_study(self.case);self._live_layout()
            reaction=self._figure('reactions',V.reaction_figure(r));connection=self._figure('connection',V.connection_figure(r));spacing=self._figure('spacing',V.spacing_figure(study))
            self.current=r;self.study=study;self.dirty=False
            self.row_filter.options=[('All rows',0)]+[(f'Row {a["row"]} · {a["z"]:g} in',a['row']) for a in r['rows']];self.row_filter.value=0
            self.row_filter.disabled=self.check_view.disabled=False
            self.ring_values.value=V.ring_table(r);self.rings_panel.children=(reaction,self.ring_values,W.HTML(V.note(f'Force residual: {r["totals"]["force_error"]:.2e} kip; nominal moment residual: {r["totals"]["moment_error"]:.2e} kip-in. '
                f'Wall rotation {r["totals"]["wall_rotation"]:.3g} rad gives a pile-head moment of {r["totals"]["pile_head_moment"]:.4g} kip-in, shared by the ring rows as M ring = {r["totals"]["ring_moment"]:.4g} kip-in; ΔR is the tolerance redistribution (D-070). Full contact needs e eq ≤ {r["totals"]["kern_limit"]:.4g} in.')))
            self.connection_panel.children=(connection,W.HTML(V.note('Peak annular pressure loads a radial cantilever strip. Each fillet takes half the strip shear plus the radial force from the plate-root moment couple. Loss of full contact makes affected local strength checks PENDING.')))
            self.steel_panel.value=V.steel_table(r);self.checks_panel.value=V.checks_table(r,self.check_view.value)
            self.spacing_values.value=V.spacing_table(study);self.spacing_panel.children=(spacing,self.spacing_values,W.HTML(V.note('First ring is fixed; rows fit below top cover. Minimum wall steel is independent of ring pitch. Trial sizes cannot be adopted where contact or fit fails.')))
            self.metrics.value=V.summary(r);self.status.value=V.note(esc(r['overall'])+' · Results match current inputs.',True);self._state('done')
        except Exception as exc:
            self._invalidate();self.status.value=V.note('Calculation stopped: '+esc(exc),True);self._state('error');raise
        finally:self.busy=False
        return self.current
    def _recalc_clicked(self):
        try:self.recalculate()
        except Exception:pass
    def _row_changed(self):
        if self._has_current():self.ring_values.value=V.ring_table(self.current,self.row_filter.value)
    def _checks_changed(self):
        if self._has_current():self.checks_panel.value=V.checks_table(self.current,self.check_view.value)
    def _tab_changed(self,change):
        name={0:'layout',1:'cage',2:'reactions',3:'connection',6:'spacing'}.get(change['new']);fig=self.figures.get(name)
        if fig is not None:fig.layout.autosize=False;fig.layout.autosize=True
    def load_case(self,case):
        p,notes=upgrade_case(case);self.busy=True
        try:
            self.case=p;self.migration=notes
            for key,w in self.controls.items():w.value=p[key]
        finally:self.busy=False
        self._changed('title',{'new':p['title']})
        self.load_status.value=V.note(esc(' '.join(notes) or 'Case loaded. Inspect drawings and click Recalc.'))
    def _uploaded(self,change):
        try:
            value=change['new'];item=next(iter(value.values())) if isinstance(value,dict) else value[0]
            self.load_case(json.loads(bytes(item['content']).decode('utf-8-sig')))
        except Exception as exc:self.load_status.value=V.note('Case not loaded: '+esc(exc),True)
    def export(self):
        if self.busy or not self._has_current():raise RuntimeError('Current inputs differ from results. Recalc before export.')
        folder=self.export_root/datetime.now(timezone.utc).strftime('ring-wall-%Y%m%d-%H%M%S-%f')
        export_results(self.current,folder);self.last_export=folder.resolve()
        self.saved_html_button.disabled=self.saved_zip_button.disabled=False
        self.export_status.value=V.note('Current calculation exported. Formula parity checked for Mathcad and Blockpad; native application recalculation not performed.')
        return self.last_export
    def _export_clicked(self,kind):
        try:self.export();self.download(kind)
        except Exception as exc:self.export_status.value=V.note('Export stopped: '+esc(exc),True)
    def _download_clicked(self,kind):
        try:self.download(kind)
        except Exception as exc:self.export_status.value=V.note('Download needs retry: '+esc(exc),True)
    def download(self,kind):
        if self.last_export is None:raise RuntimeError('Generate an export first.')
        name,mime=EXPORTS[kind];path=self.last_export/name
        try:from google.colab import files
        except ImportError:self.download_output.value='<a download="'+name+'" href="data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()+'">Download '+esc(name)+'</a>'
        else:
            with self.download_area:files.download(str(path))
        if not self._has_current():self.export_status.value=V.note('Saved download contains previous inputs. Recalc and generate again for current inputs.',True)
        return path
    def display(self):
        for fig in self.figures.values():fig.prepare_display()
        display(self.ui)
    def close(self):
        seen=set()
        def close(w):
            if id(w) in seen:return
            seen.add(id(w))
            for child in getattr(w,'children',()):close(child)
            for child in getattr(w,'panels',()):close(child)
            w.close()
        close(self.ui)
        for w in self.figures.values():close(w)
