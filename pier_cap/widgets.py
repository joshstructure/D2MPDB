"""Jupyter interface. All normal input, search and export work stays in the notebook."""
from copy import deepcopy
from pathlib import Path
import html
import json
import ipywidgets as W
from .plotly_compat import FigureWidget
from .live_views import LiveViews
from .model import default_case,upgrade_case,evaluate,INPUTS,GEOMETRY,formula_trace,analysis_match,sectional_checks_pass,bar_positions
from .optimizer import search,sensitivity_search,SearchConfig,candidate_case,filter_candidates,candidate_dc,candidate_governing,governing_check,DC_SCOPES,same_design_basis
from .io import export_bundle,export_blockpad
from .fbmp_widgets import XMLImportPanel
from .pile_widgets import PileReviewPanel
from .case_widgets import CaseImportPanel
from .blockpad_widgets import BlockpadExportPanel
from .widget_compat import Tab, Accordion
from .source_status import source_html,import_receipt,receipt_html,notice_html
from .force_audit import force_basis,FORCE_LABELS
from .force_diagrams import ForceDiagramPanel
from .geometry_dimensions import dimensions_figure,dimensions_html
from .transverse_widgets import TransversePanel
from .transverse import enabled as actual_transverse
from .pile_visual_widgets import PileAppearancePanel
from .cage_3d import layout_3d
from .visuals import configuration_html
from .visuals import section_figure,elevation_figure,reinforcement_plan_figure,reinforcement_summary_html,clear_spacing_html,hoop_figure,hoop_explanation_html,results_figure,optional_service_figure,ratios_figure,alternatives_figure,checks_html,spacing_html,side_steel_html

UNIT_NAMES={'in':'inches','ft':'feet','kip':'kips','kip*ft':'kip-feet','ksi':'ksi (kips per square inch)','deg':'degrees'}


def input_tooltip(name, caption=None):
    unit=INPUTS[name]['unit']
    prefix=f'Input units: {UNIT_NAMES.get(unit,unit)}. ' if unit else ''
    return prefix+(INPUTS[name]['caption'] if caption is None else caption)


LABELS={'b':'Cap width','h':'Cap depth','C_t':'Top cover','C_b':'Bottom cover','C_s':'Side cover',
 'N_pile':'Number of piles','S_pile':'Pile spacing','D_pile':'Pile width / OD','E_clear':'Actual edge clearance','E_detail':'Extra end allowance',
 'Pile_embed':'Pile embedment','C_pile':'Clear gap to pile','Ready_pile':'Pile dimensions confirmed',
 'fc':"Concrete f′c",'fy':'Steel fy','Es':'Steel modulus',
 'Bar_N1':'Top row 1 bar','Bar_N2':'Top row 2 bar','Bar_N3':'Top row 3 bar','n_N1':'Top row 1 count','n_N2':'Top row 2 count','n_N3':'Top row 3 count',
 'Bar_P':'Continuous bottom bar','Bar_B':'ADDED span bar size','Bar_U':'U-leg bar','n_P1':'Continuous row 1 count','n_P2':'Continuous row 2 count','n_PU':'Pile U-leg count',
 'n_B1':'ADDITIONAL row 1 count','n_B2':'ADDITIONAL row 2 count','n_BU':'Between-pile U legs',
 'Bar_v':'Closed hoop bar','n_loop':'Effective hoop loops','Bar_skin':'Side-face bar','n_skin':'Bars per side',
 's_row':'Row center spacing','s_G':'Overall hoop pitch (G)','s_L':'Lower-shear hoop pitch (L)',
 'Mu_N':'Envelope · negative','Mu_P':'Envelope · pile positive','Mu_B':'Envelope · bearing/span',
 'MI_N':'Service I · negative','MI_P':'Service I · pile positive','MI_B':'Service I · bearing positive',
 'Vu_G':'Overall shear (G)','Vu_L':'Lower-shear interval (L)','Tu':'Torque magnitude',
 'Ready_III':'Service III loads ready','Ready_fatigue':'Fatigue loads ready','Manual_spacing':'Override bar spacing',
 'phi_f':'Flexural resistance factor','phi_v':'Shear resistance factor','gamma_e':'Exposure factor','gamma_fat':'Fatigue load factor',
 'beta_v':'Shear β','theta':'Compression angle θ','alpha_v':'Hoop angle α','fpc':'Precompression','Ao_factor':'Effective torsion area factor',
 'SP_detail_N':'Top spacing override','SP_detail_P':'Pile spacing override','SP_detail_B':'Added row pitch override','SP_detail_skin':'Skin spacing override','S_leg_detail':'Inner leg spacing'}

GROUPS={
 'Steel': [('Top rows','Bar_N1 n_N1 Bar_N2 n_N2 Bar_N3 n_N3'),('Continuous bottom steel · at piles','Bar_P n_P1 n_P2'),('ADDITIONAL steel · between piles','Bar_B n_B1 n_B2'),('Hoops and side bars','Bar_v n_loop s_G s_L Bar_skin n_skin s_row'),('Extra U-leg inventory · unresolved','Bar_U n_PU n_BU'),('Advanced · cross-section spacing','Manual_spacing SP_detail_N SP_detail_P SP_detail_B SP_detail_skin S_leg_detail')],
 'Geometry':[('Section and cover','b h C_t C_b C_s'),('Pile row and cap ends','N_pile S_pile D_pile E_clear E_detail'),('Pile head','Pile_embed C_pile Ready_pile')],
 'Loads':[('Combined strength envelopes','Mu_N Mu_P Mu_B Vu_G Vu_L Tu'),('Service I','MI_N MI_P MI_B')],
 'Pending':[('Service III','Ready_III MIII_N MIII_P MIII_B'),('Fatigue','Ready_fatigue MDL_N MDL_P MDL_B DMLL_N DMLL_P DMLL_B')],
 'Factors':[('Materials','fc fy Es'),('Design assumptions','phi_f phi_v gamma_e gamma_fat beta_v theta alpha_v fpc Ao_factor')]
}

class CapNotebook:
    def __init__(self,case=None,export_root='exports'):
        self.case=upgrade_case(case or default_case());self.export_root=Path(export_root)
        self.controls={};self.busy=False;self.search_result=None;self.current=None;self.figures=[];self.last_export=None
        self.browsing=False;self.filtered_indices=[];self.alternative_figure=None;self.cage_3d_widget=None
        self.views=LiveViews();self._view_geometry=None;self._aux_geometry={};self._aux_basis={}
        self.case_listeners=[]
        self.import_receipt=None;self.import_notice=W.HTML()
        self.banner=W.HTML(layout=W.Layout(height='130px',overflow='auto'));self.metrics=W.HTML();self.message=W.HTML()
        self.cage=W.VBox(layout=W.Layout(width='100%',min_width='0'));self.results=W.VBox();self.dimensions=W.VBox();self.register=W.HTML();self.trace=W.HTML()
        self.clearance=W.BoundedFloatText(value=self.case['screening']['minimum_clear_in'],min=0,max=12,step=.25,description='Project min clear (in)',style={'description_width':'120px'},layout=W.Layout(width='260px'))
        self.aggregate=W.BoundedFloatText(value=self.case['screening']['aggregate_in'],min=.125,max=6,step=.125,description='Max aggregate (in)',style={'description_width':'170px'},layout=W.Layout(width='300px'))
        self.aggregate_confirmed=W.Checkbox(value=self.case['screening']['aggregate_confirmed'],description='Aggregate size confirmed',indent=False)
        for control in (self.clearance,self.aggregate,self.aggregate_confirmed):control.observe(self._changed,names='value')
        self.pile_appearance=PileAppearancePanel(self)
        self.input_tabs=self._inputs()
        self.transverse_panel=TransversePanel(self)
        self.force_diagrams=ForceDiagramPanel()
        self.plot_tabs=Tab(children=[self.cage,self.results,W.VBox([self.register],layout=W.Layout(max_height='850px',overflow='auto')),W.VBox([self.trace],layout=W.Layout(max_height='750px',overflow='auto')),self.force_diagrams.ui,self.dimensions],layout=W.Layout(width='100%',min_width='0',flex='0 0 auto'))
        for i,title in enumerate(['Live cage','Plots','D/C checks','Equations','Force diagrams','Dimensions']):self.plot_tabs.set_title(i,title)
        self.input_panel=W.VBox([W.HTML('<h3>Cap inputs · steel, geometry, loads and factors</h3>'),self.input_tabs],
            layout=W.Layout(width='100%',min_width='0',flex='0 0 auto'))
        self.input_panel.add_class('cap-section-inputs')
        self.workbench=W.VBox([self.plot_tabs],layout=W.Layout(width='100%',min_width='0'))
        self.plot_tabs.observe(self._plot_tab_changed,names='selected_index')
        self.case_import=CaseImportPanel(self)
        self.upload=self.case_import.upload
        reset=W.Button(description='Reset starting case',icon='undo');reset.on_click(lambda _:self.load(default_case()))
        self.case_import.actions.children=(*self.case_import.actions.children,reset)
        self.source_label=W.HTML()
        self.source_id=W.Text(description='Analysis ID',placeholder='Name of the new force analysis run',layout=W.Layout(width='430px'))
        self.source_confirm=W.Checkbox(value=False,description='I have supplied forces for the current geometry',indent=False,layout=W.Layout(width='420px'))
        stamp=W.Button(description='Record analyzed geometry',icon='check');stamp.on_click(self._stamp)
        source=Accordion(children=[W.VBox([self.source_id,self.source_confirm,stamp,W.HTML('<small>Use after entering fresh analysis forces. Changing geometry alone does not rerun FB-MultiPier.</small>')])]);source.set_title(0,'Record a manually updated analysis case');source.selected_index=None
        self.search_panel=self._search_panel();self.export_panel=self._export_panel()
        self.pile_review=PileReviewPanel(self)
        self.xml_import=XMLImportPanel(self,LABELS)
        self.cap_type=W.Dropdown(options=['Pier pile cap','End-bent pile cap'],value=self.case.get('cap_type','Pier pile cap'),description='Cap type',layout=W.Layout(width='330px'))
        self.cap_type.observe(self._cap_type_changed,names='value')
        self.ui=W.VBox([W.HTML('<style>.cap-input .widget-label{white-space:normal!important;text-overflow:clip!important;line-height:1.25!important;height:auto!important;text-align:left!important;align-self:center}</style><h2 style="color:#213649;margin-bottom:4px">Cap and pile design explorer</h2><p>Review the FBMP pile results → inspect the cap cage and checks → search practical steel → export a review case.</p>'),
            self.cap_type,W.HTML('<p>Shared sectional workflow for pier and end-bent caps supported directly on a single pile row. The cap type labels the case; it does not add loads or change the design method. Backwall/wingwall, earth-pressure load generation, footing/column caps and strut-and-tie design are outside this calculation.</p>'),
            self.case_import.ui,self.xml_import.ui,self.import_notice,self.pile_review.ui,
            W.HTML('<h2 style="color:#213649">2. Cap reinforcement and steel optimization</h2>'),self.source_label,source,self.banner,self.metrics,
            self.workbench,
            self.search_panel,self.export_panel,self.message],layout=W.Layout(width='100%'))
        self.refresh()

    def _plot_tab_changed(self,change):
        self._refresh_auxiliary_view(change['new'])
        # Every plot now occupies the full row; inputs live under the sections.
        figure=self.force_diagrams.figure
        if change['new']==4 and figure is not None:
            figure.layout.autosize=False
            figure.layout.autosize=True

    def _cap_type_changed(self,change):
        if not self.busy:
            self.case['cap_type']=change['new']
            self.case_import._case_changed()

    def _inputs(self):
        tabs=[]
        for group,sections in GROUPS.items():
            panels=[]
            for title,names in sections:
                rows=[]
                for n in names.split():
                    meta=INPUTS[n];value=self.case['inputs'][n]
                    if isinstance(value,bool):control=W.Checkbox(value=value,indent=False,layout=W.Layout(width='110px'))
                    elif n.startswith('Bar_'):control=W.Dropdown(options=[(f'#{i}',i) for i in range(3,12)],value=int(value),layout=W.Layout(width='105px'))
                    elif n.startswith('n_') or n=='N_pile':control=W.BoundedIntText(value=int(value),min=0,max=200,layout=W.Layout(width='105px'))
                    else:control=W.FloatText(value=value,step=.25,layout=W.Layout(width='105px'))
                    control.tooltip=input_tooltip(n);control.observe(self._changed,names='value');self.controls[n]=control
                    label=LABELS.get(n,n.replace('_',' '))
                    unit=meta['unit'] or ('unitless' if isinstance(control,W.FloatText) else '')
                    control.description=label+(f' ({unit.replace("*","-")})' if unit else '')
                    control.style.description_width='140px' if group=='Geometry' else '180px'
                    control.layout.width='216px' if group=='Geometry' else '260px';control.layout.max_width='calc(100% - 4px)'
                    control.layout.min_height='30px';control.layout.height='auto';control.add_class('cap-input')
                    rows.append(control)
                if title=='Hoops and side bars':
                    self.hoop_reference_inputs=W.VBox([W.HTML('<p><b>Uniform-cage reference inputs.</b> G = overall shear check; L = lower-shear interval check, not the bottom of the cap. These reference pitches seed the starting layout; later edits to them do not move your entered bars. The reference hoop diameter also locates the longitudinal cage; actual shape conflicts are checked separately.</p>'),
                        *rows[:4],self.clearance,self.aggregate,self.aggregate_confirmed,W.HTML('<small>The larger of the code minimum and project minimum governs. Confirm aggregate from the mix design. All actual run inputs, including end geometry, are in the numbered cards above.</small>')])
                    rows=rows[4:]
                if title=='Extra U-leg inventory · unresolved':rows.insert(0,W.HTML('<p><b>These are NOT the transverse pile U-bars.</b> Use the zone controls below the reinforcement elevation for those. These legacy counts add longitudinal tension area but have no resolved position or development. A nonzero count triggers an issue. Do not enter span-bar end hooks here either. Zero means no separate legacy inventory.</p>'))
                if title=='Advanced · cross-section spacing':rows.insert(0,W.HTML('<p>Override the automatic spacing of longitudinal bars <b>within the cross section</b>. The checkbox activates top, continuous-bottom, added-row and side-bar spacing overrides. It does not add bars or change along-cap hoop pitch. <b>Inner leg spacing</b> is used separately when effective hoop loops exceed one; multiple-loop positions remain unresolved.</p>'))
                if title=='ADDITIONAL steel · between piles':rows.insert(0,W.HTML('<p><b>These counts are ADDITIONAL, not totals.</b> Continuous bottom bars stay in place. Total span steel = continuous bars + these added bars. Enter 0 for no added bars. The bar size here applies only to the added steel. Standard 90° hooks are drawn at the span ends; anchorage remains a separate check.</p>'))
                if title=='Continuous bottom steel · at piles':rows.insert(0,W.HTML('<p>These bottom bars continue through every pile and span to the cap end-cover planes. Their transverse positions stay fixed. End anchorage and splices require review.</p>'))
                caption='Side bars and row spacing' if title=='Hoops and side bars' else title
                content=[W.HBox(rows,layout=W.Layout(width='100%',flex_flow='row wrap',grid_gap='8px'))] if group=='Geometry' else rows
                layout=(W.Layout(width='100%',min_width='0',flex='0 0 auto',padding='8px',border='1px solid #c4cdd6') if group=='Geometry' else
                    W.Layout(flex='1 1 280px',min_width='280px',max_width='360px',padding='8px',border='1px solid #c4cdd6'))
                card=W.VBox([W.HTML('<b>'+html.escape(caption)+'</b>'),*content],layout=layout)
                card.add_class('cap-input-card');panels.append(card)
            if group=='Geometry':panels.append(self.pile_appearance.ui)
            tabs.append(W.HBox(panels,layout=W.Layout(width='100%',min_width='0',flex_flow='row wrap',align_items='flex-start',grid_gap='8px')))
        tab=Tab(children=tabs,layout=W.Layout(flex='0 0 auto',width='100%',min_width='0'))
        for i,name in enumerate(GROUPS):tab.set_title(i,name)
        return tab

    def _changed(self,change):
        if self.busy:return
        self.case['inputs']={n:w.value for n,w in self.controls.items()}
        self.case['screening']['minimum_clear_in']=self.clearance.value
        self.case['screening']['aggregate_in']=self.aggregate.value
        self.case['screening']['aggregate_confirmed']=self.aggregate_confirmed.value
        self.transverse_panel.sync()
        self._update_search_basis()
        self.refresh()
        self._notify_case_change()

    def _notify_case_change(self):
        for callback in self.case_listeners:callback()

    def refresh(self):
        self.source_label.value=source_html(self.case)
        self._refresh_search_force_notice()
        for key in FORCE_LABELS:
            self.controls[key].tooltip=input_tooltip(key,force_basis(self.case,key))
        self.import_notice.value=receipt_html(self.import_receipt,self.case)
        try:e=evaluate(self.case)
        except Exception as exc:
            self._aux_basis.clear()
            self.force_diagrams.refresh(self.case)
            self.current=None;self.banner.value=f'<div style="padding:14px;background:#ffe9e7;color:#9d302b"><b>INPUT ERROR</b><br>{html.escape(str(exc))}</div>'
            self.transverse_panel.zone_grid.layout.display='none'
            self.transverse_panel.zone_scroll.layout.display='none'
            self.transverse_panel.detail_area.layout.display='none'
            self.transverse_panel.zone_notice.value='<p>Correct the input error above to restore zone controls and drawings. General inputs remain available below.</p>'
            self.metrics.value='';self.cage.children=[self.input_panel,self.transverse_panel.ui];self.results.children=[];self.dimensions.children=[];self.register.value='';self.trace.value='';return
        self.current=e
        self.transverse_panel.sync_zones(e)
        self.force_diagrams.refresh(self.case,evaluation=e)
        self.pile_appearance.sync()
        trial_section=self._search_force_mode()=='fixed'
        color='#fff3d9' if e.eligible or (trial_section and sectional_checks_pass(e)) else '#ffe9e7'
        status='TRIAL CAP SIZE — checks use current forces; changed self-weight and stiffness are not reanalyzed' if trial_section else e.status
        extra='<br>'.join(html.escape(s) for s in e.issues)
        self.banner.value=f'<div style="padding:12px;background:{color};border-radius:6px"><b>{html.escape(status)}</b>{"<br>"+extra if extra else ""}<br><small>Sectional calculation only. D-regions, anchorage, pile heads, applicability and final detail review remain open.</small></div>'
        strength=governing_check(e,'strength');overall=governing_check(e)
        items=[('Strength D/C',f'{strength.ratio:.3f}'),('All-check utilization',f'{e.max_dc:.3f}'),('Gross steel estimate',f'{e.weight_lb:,.0f} lb'),('Top steel area',f'{e.value("As_N"):.2f} in²'),('Top Service I stress',f'{e.value("fs_I_N"):.2f} ksi'),('Cap length',f'{e.value("L_cap")/12:.3f} ft'),('Nominal end extension',f'{e.value("E_end"):g} in')]
        metrics='<div style="display:flex;flex-wrap:wrap;gap:10px;margin:12px 0">'+''.join(f'<div style="padding:10px 18px;background:#eaf1f6;border-radius:5px"><small>{k}</small><br><b style="font-size:23px;color:#1f5b91">{v}</b></div>' for k,v in items)+'</div>'
        metrics+=f'<p><b>Controls strength:</b> {html.escape(strength.label)}. <b>Controls all checks:</b> {html.escape(overall.label)}.<br><small>All-check utilization also includes spacing and minimum/detailing limits. It does not measure a single reserve against increased load.</small></p>'
        if overall.key in ('Chk_spacing_G','Chk_spacing_L'):
            zone=overall.key[-1];s=e.value('S_leg');limit=e.value('Sw_'+zone)
            metrics+=f'<p><b>Across-cap hoop legs:</b> {s:.3f} in / {limit:.3f} in allowed = <b>{s/limit:.4f}</b>. Adding main bars or reducing along-cap hoop spacing leaves this across-cap distance unchanged.</p>'
        self.metrics.value=metrics
        geometry=tuple((n,self.case['inputs'][n]) for n in (*GEOMETRY,'C_t','C_b','C_s','Pile_embed','C_pile'))
        same_geometry=geometry==self._view_geometry;self._view_geometry=geometry
        def fw(key,factory,**kwargs):return self.views.figure(key,factory,preserve_view=same_geometry,**kwargs)
        txt=self.views.text
        self.cage_3d_widget=fw('cage3d',lambda:layout_3d(e))
        self.refresh_sections(preserve_view=same_geometry)
        footer=('Every transverse station is drawn. Pink U-bars are open downward; the section shows the selected run of that shape, or the first run of that shape. Bend / tail fit and pile conflicts are screened; development, closure and 3D congestion at longitudinal hook ends require review.' if actual_transverse(self.case) else 'Dashed transverse shapes are reference illustrations. Set actual hoops and open-bottom U-bars in the zone controls below the elevation.')
        self.views.mount(self.cage,[txt('configuration',configuration_html(e)+reinforcement_summary_html(e)),txt('side',side_steel_html(e)),self.cage_3d_widget,self.views.plots['sectionB'],self.views.plots['sectionP'],self.input_panel,fw('plan',lambda:reinforcement_plan_figure(e)),fw('elevation',lambda:elevation_figure(e,zone_labels=True)),self.transverse_panel.ui,txt('hoop',hoop_explanation_html(e)),
            *([fw('reference_hoop',lambda:hoop_figure(e))] if not actual_transverse(self.case) else []),txt('clearance',clear_spacing_html(e)),txt('footer','<small>'+footer+' Pile lengths below the cap are schematic. The 3D cage uses bar centerlines; displayed line thickness is for visibility.</small>')])
        self._refresh_auxiliary_view(self.plot_tabs.selected_index)
        self.figures=list(self.views.plots.values())
        self.register.value=checks_html(e)
        rows=''.join(f'<tr><td>{html.escape(t["name"])}</td><td>{html.escape(t["formula"])}</td><td>{html.escape(str(t["value"]))}</td></tr>' for t in formula_trace(e))
        self.trace.value=('<p><b>Actual transverse layout:</b> this equation table retains the uniform closed-hoop reference. The D/C tab separately lists checks at actual adjacent stations. Open U-bars receive no closed-hoop torsion credit.</p>' if actual_transverse(self.case) else '')+'<p>Live equations use independent pile and between-pile reinforcement.</p><table class="cap-table"><tr><th>Name</th><th>Equation</th><th>Value</th></tr>'+rows+'</table>'

    def refresh_sections(self,*,preserve_view=True):
        """Inspect a run using the current calculation; no full-case redraw."""
        if self.current is None:return
        for region in ('B','P'):
            self.views.figure('section'+region,lambda:section_figure(self.current,region,self.transverse_panel.selected_run_id),preserve_view=preserve_view)

    def _refresh_auxiliary_view(self,index):
        """Render hidden plots on entry using the latest evaluated case."""
        if self.current is None or index not in (1,5):return
        e=self.current
        basis=json.dumps(e.case,sort_keys=True)
        if self._aux_basis.get(index)==basis:return
        geometry=tuple((n,e.case['inputs'][n]) for n in (*GEOMETRY,'C_t','C_b','C_s','Pile_embed','C_pile'))
        preserve=geometry==self._aux_geometry.get(index)
        def fw(key,factory,**kwargs):return self.views.figure(key,factory,preserve_view=preserve,**kwargs)
        txt=self.views.text
        if index==5:
            dimension_basis=json.dumps({'geometry':geometry,'bars':bar_positions(e,'P')},sort_keys=True)
            self.views.mount(self.dimensions,[fw('dimensions',lambda:dimensions_figure(e),basis=dimension_basis),txt('dimensions',dimensions_html(e))])
        else:
            self.views.mount(self.results,[fw('results',lambda:results_figure(e)),txt('spacing',spacing_html(e)),fw('service',lambda:optional_service_figure(e)),fw('ratios',lambda:ratios_figure(e)),txt('results_note','<small>These plots compare imported force envelopes and sectional capacities. They are not a continuous moment/shear diagram or a rerun of FB-MultiPier.</small>')])
        self._aux_geometry[index]=geometry;self._aux_basis[index]=basis
        self.figures=list(self.views.plots.values())

    def load(self,case,*,import_name=None):
        case=upgrade_case(case);evaluate(case);self.busy=True
        try:
            self.case=deepcopy(case)
            self.import_receipt=import_receipt(case,import_name) if import_name else None
            for n,w in self.controls.items():w.value=case['inputs'][n]
            self.clearance.value=case['screening']['minimum_clear_in']
            self.aggregate.value=case['screening']['aggregate_in']
            self.aggregate_confirmed.value=case['screening']['aggregate_confirmed']
            self.cap_type.value=case.get('cap_type','Pier pile cap')
            self.transverse_panel.sync()
            self.pile_appearance.sync()
        finally:self.busy=False
        self._update_search_basis()
        self.refresh()
        if import_name and case['analysis'].get('xml_audit',{}).get('end_records'):
            self.plot_tabs.selected_index=4
        self._notify_case_change()

    def _stamp(self,button):
        if not self.source_confirm.value or not self.source_id.value.strip():
            self.message.value='Enter the analysis ID and confirm that the entered forces were analyzed for the current geometry.';return
        self.case['analysis']={'id':self.source_id.value.strip(),'geometry':{k:self.case['inputs'][k] for k in GEOMETRY},'notes':'User recorded a manually updated force analysis in the notebook.'}
        self.case.pop('section_study',None)
        self.source_confirm.value=False;self._clear_search();self.refresh()
        self._notify_case_change()

    def _search_panel(self):
        self.search_lists={}
        configs=[('main_bars','Top bars',(5,6,7,8,9,10,11),(6,7,8,9)),('top_counts','Top counts',(4,5,6,7,8,9,10,12),(4,6,8)),('pile_bars','Pile bars',(3,4,5,6,7,8,9,10,11),(6,7,8,9)),('pile_counts','Pile counts',(2,3,4,5,6,7,8,9,10,12),(4,6,8)),('span_bars','ADDED span bars',(3,4,5,6,7,8,9,10,11),(6,7,8,9)),('span_counts','ADDED span counts',(0,1,2,3,4,5,6,7,8,9,10,12),(0,2,4)),('hoop_bars','Hoop bars',(3,4,5,6,7),(4,5,6)),('hoop_spacings','Spacing (in)',(4,5,6,7,8,9,10,12),(6,8,10)),('skin_bars','Side bars',(3,4,5,6),(4,5)),('skin_counts','Bars / side',tuple(range(11)),SearchConfig().skin_counts)]
        boxes=[]
        for name,label,options,value in configs:
            if name.endswith('_bars'):
                options=[(f'#{v}',v) for v in options]
                hint='US reinforcing bar size designation (#), not a length.'
            elif name=='hoop_spacings':
                options=[(f'{v:g} in',v) for v in options]
                hint='Hoop spacing in inches.'
            else:hint='Number of bars (count).'
            w=W.SelectMultiple(options=options,value=value,rows=5,tooltip=hint,layout=W.Layout(width='112px'));self.search_lists[name]=w;boxes.append(W.VBox([W.HTML('<b>'+label+'</b>'),w]))
        self.objective=W.Dropdown(options=['Least steel','Simplest cage','Largest margin'],description='Rank by',layout=W.Layout(width='260px'))
        self.limit=W.BoundedIntText(value=10000,min=1,max=100000,description='Case limit',layout=W.Layout(width='230px'))
        self.dc_limit=W.BoundedFloatText(value=1.0,min=.01,max=1.0,step=.05,description='Max D/C',layout=W.Layout(width='210px'))
        self.dc_scope=W.Dropdown(options=[(DC_SCOPES[key],key) for key in ('strength','all')],value='strength',description='Apply target to',style={'description_width':'100px'},layout=W.Layout(width='310px'))
        self.page_size=W.Dropdown(options=[20,50,100],value=20,description='Per page',layout=W.Layout(width='170px'))
        self.page=W.BoundedIntText(value=1,min=1,max=1,description='Page',disabled=True,layout=W.Layout(width='150px'))
        self.previous_page=W.Button(description='Previous',icon='chevron-left',disabled=True,layout=W.Layout(width='110px'))
        self.next_page=W.Button(description='Next',icon='chevron-right',disabled=True,layout=W.Layout(width='90px'))
        self.previous_page.on_click(lambda _:setattr(self.page,'value',max(1,self.page.value-1)))
        self.next_page.on_click(lambda _:setattr(self.page,'value',min(self.page.max,self.page.value+1)))
        for control in (self.objective,self.dc_limit,self.dc_scope,self.page_size):control.observe(self._filter_changed,names='value')
        self.page.observe(self._page_changed,names='value')
        self.run_button=W.Button(description='Search steel layouts',button_style='primary',icon='search');self.run_button.on_click(self._run_search)
        self.search_force_notice=W.HTML()
        self.progress=W.IntProgress(min=0,max=1,value=0,description='Search')
        self.search_status=W.HTML(layout=W.Layout(min_width='240px',flex='1 1 300px'))
        self.search_text=W.HTML();self.search_notice=W.HTML();self.candidates=W.Dropdown(options=[],description='Alternative',layout=W.Layout(width='90%'),style={'description_width':'80px'})
        self.apply_button=W.Button(description='Apply selected layout',disabled=True,icon='check');self.apply_button.on_click(self._apply)
        self.alternative_output=W.VBox()
        return W.VBox([W.HTML('<h3>Search practical steel</h3><p>Search top steel, continuous bottom steel and ADDITIONAL between-pile steel with independent sizes and counts. Span counts add to the continuous count; zero means no extra bars. One row per group, one closed hoop and uniform hoop spacing; multirow arrangements remain manual inputs. Hold Ctrl/Cmd to select several choices.</p>'),
            W.HBox(boxes,layout=W.Layout(flex_flow='row wrap',grid_gap='10px')),self.search_force_notice,
            W.HBox([self.limit,self.run_button,self.progress,self.search_status],layout=W.Layout(flex_flow='row wrap',align_items='center')),
            W.HTML('<h4>Browse every passing layout</h4><p>These are reinforcement layouts for the current force case. <b>Strength checks only</b> is the default margin target: set <b>Max D/C</b> to 0.90 to seek reserve in those checks. Filtering, ranking and paging reuse the completed search.</p>'),
            W.HBox([self.dc_limit,self.dc_scope,self.objective],layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<small><b>All available checks</b> includes spacing, minimum steel, strain and service checks. <b>Strength checks only</b> targets flexure, shear, combined shear/torsion steel and longitudinal steel; all other available checks must still pass. Missing Service III/fatigue checks stay pending. Largest margin ranks the selected D/C scope.</small>'),
            self.search_notice,self.search_text,W.HBox([self.previous_page,self.page,self.next_page,self.page_size],layout=W.Layout(flex_flow='row wrap')),self.candidates,self.apply_button,self.alternative_output,
            W.HTML('<small>Gross steel counts continuous bars once and adds each drawn span bar including its two hook bends and tails. End anchorage, laps, hoop bends and waste are not priced. Cage score = longitudinal bar count + 5 × distinct bar sizes. Search results are conditional candidates, not finalized designs.</small>')])

    def _close_alternative_plot(self):
        if self.alternative_figure is not None:self.alternative_figure.close();self.alternative_figure=None
        self.alternative_output.children=[]

    def _search_force_mode(self):
        changed=analysis_match(self.case)
        return 'fixed' if changed and set(changed)<={'b','h'} else 'matched'

    def _refresh_search_force_notice(self):
        changed=analysis_match(self.case)
        if self._search_force_mode()=='fixed':
            p=self.case['inputs'];g=self.case['analysis']['geometry']
            self.search_force_notice.value=notice_html('TRIAL CAP SIZE · FORCES UNCHANGED',
                f'Analyzed section: {g["b"]:g} × {g["h"]:g} in. Trial section: {p["b"]:g} × {p["h"]:g} in. '
                'Search steel layouts will check the new size using the current load envelopes. '
                'Self-weight and stiffness changes need an updated FBMP analysis for the final size.','pending')
        elif changed:
            labels=', '.join(LABELS.get(k,k) for k in changed)
            self.search_force_notice.value=notice_html('PILE LAYOUT / CAP ENDS NEED MATCHING FORCES',
                html.escape(labels)+': these changes need a matching analysis before steel search. '
                'Width and depth changes alone can be explored with the current forces.','pending')
        else:
            self.search_force_notice.value=''

    def _clear_search(self,message=''):
        self.search_notice.value=''
        self.search_status.value='';self.progress.bar_style='';self.progress.value=0
        self.search_result=None;self.filtered_indices=[];self.candidates.options=[];self.apply_button.disabled=True
        self.page.value=1;self.page.max=1;self.page.disabled=True
        self.previous_page.disabled=True;self.next_page.disabled=True;self.search_text.value=message
        self._close_alternative_plot()

    def _update_search_basis(self):
        if self.search_result is not None and same_design_basis(self.search_result.base_case,self.case):
            self.search_notice.value=notice_html('COMPLETED SEARCH RETAINED',
                'Live reinforcement edits do not change the saved candidates or their checks. '
                'Filters and selections are kept. Apply a layout to restore its saved reinforcement and spacing.','success')
        else:
            self._clear_search('Design inputs changed. Run the search to refresh alternatives.')

    def _filter_changed(self,change):
        if not self.browsing and self.search_result is not None:self._render_candidates(reset_page=True)

    def _page_changed(self,change):
        if not self.browsing and self.search_result is not None:self._render_candidates()

    def _search_filter(self):
        return {'max_dc':self.dc_limit.value,'scope':self.dc_scope.value,'objective':self.objective.value}

    def _render_candidates(self,reset_page=False):
        result=self.search_result
        if result is None:return
        options=self._search_filter();scope=options['scope'];target=options['max_dc']
        indices=filter_candidates(result,**options);self.filtered_indices=indices
        size=self.page_size.value;pages=max(1,(len(indices)+size-1)//size)
        old_selected=self.candidates.value;self.browsing=True
        try:
            self.page.max=pages;self.page.value=1 if reset_page else min(self.page.value,pages)
            self.page.disabled=not indices
            start=(self.page.value-1)*size;shown=indices[start:start+size]
            self.candidates.options=[(f'#{i+1}. {result.candidates[i].label} · {result.candidates[i].weight_lb:.0f} lb · filter D/C {candidate_dc(result.candidates[i],scope):.3f}',i) for i in shown]
            if shown:self.candidates.value=old_selected if old_selected in shown else shown[0]
            self.previous_page.disabled=self.page.value<=1;self.next_page.disabled=self.page.value>=pages
            self.apply_button.disabled=not shown
        finally:self.browsing=False
        extent=f'Showing {start+1:,}–{start+len(shown):,} of {len(indices):,} matches · page {self.page.value} of {pages}.' if shown else 'No layouts match this D/C filter.'
        completeness='All listed combinations evaluated.' if result.exhaustive else 'Case limit reached: a reproducible sample across the full selected range was evaluated. Other combinations remain untested.'
        self.search_text.value=f'<p><b>{result.passed:,} layouts pass the available checks and cage screen.</b> {len(indices):,} meet <b>{DC_SCOPES[scope]} ≤ {target:.3f}</b>. {extent}<br>{result.evaluated:,} / {result.total:,} combinations evaluated. {completeness} {result.elapsed:.1f} seconds. Every passing layout is retained and unit-checked. Candidate IDs stay fixed within this search.</p>'
        if result.force_mode=='fixed':
            self.search_text.value='<p><b>Trial cap size using unchanged forces.</b> These layouts pass sectional checks at the trial width/depth; the original analyzed geometry remains recorded.</p>'+self.search_text.value
        strength_count=sum(c.strength_dc<=target+1e-12 for c in result.candidates)
        all_count=sum(c.max_dc<=target+1e-12 for c in result.candidates)
        self.search_text.value+=f'<p>At target {target:.3f}: <b>{strength_count:,} strength matches</b> · <b>{all_count:,} all-check matches</b>. The all-check target also tightens spacing and minimum/detailing criteria.</p>'
        zero_count=sum(result.candidates[i].changes['n_skin']==0 for i in indices)
        self.search_text.value+=f'<p><b>{zero_count:,} matching layouts without side bars.</b> Least steel ranks total main, side and hoop weight. A depth-based skin exemption does not waive shrinkage/temperature or longitudinal-tension checks.</p>'
        if not shown and result.candidates:
            best=min(result.candidates,key=lambda c:candidate_dc(c,scope))
            self.search_text.value+=f'<p><b>Best available {DC_SCOPES[scope].lower()} D/C: {candidate_dc(best,scope):.6f}</b> · controlling check: {html.escape(candidate_governing(best,scope))}. No layout in the evaluated choices meets {target:.3f} for this scope.</p>'
            if scope=='all':self.search_text.value+='<p>Spacing or minimum/detailing checks may set this floor. Adding main bars alone may not lower it. Strength-only filtering is a separate target; it does not mean every D/C is below your limit.</p>'
        if not result.candidates:
            common='; '.join(f'{html.escape(k)} ({v:,})' for k,v in sorted(result.rejection_counts.items(),key=lambda item:-item[1])[:3])
            self.search_text.value+=f'<p><b>No passing cages in the evaluated layouts.</b> Most frequent failures: {common}. '+('Increase the case limit or narrow the selected ranges; untested layouts may still pass.' if not result.exhaustive else 'Revise the listed steel choices or review the governing checks.')+'</p>'
            self._close_alternative_plot()
            return
        rows=''.join(f'<tr><td>{rank}</td><td>#{i+1}</td><td>{html.escape(c.label)}</td><td>{c.weight_lb:.0f}</td><td>{candidate_dc(c,scope):.4f}</td><td>{c.strength_dc:.4f}</td><td>{c.max_dc:.4f}</td><td>{html.escape(candidate_governing(c,scope))}</td></tr>' for rank,(i,c) in enumerate(((i,result.candidates[i]) for i in shown),start+1))
        rejects='; '.join(f'{html.escape(k)}: {v}' for k,v in sorted(result.rejection_counts.items(),key=lambda t:-t[1])[:8])
        self._close_alternative_plot()
        self.alternative_figure=FigureWidget(alternatives_figure(result,indices,dc_scope=scope,max_dc=target))
        self.alternative_output.children=[W.HTML('<table class="cap-table"><tr><th>Filtered rank</th><th>Candidate ID</th><th>Layout</th><th>Gross lb</th><th>Filter ratio</th><th>Strength D/C</th><th>All-check utilization</th><th>Controls filter</th></tr>'+rows+'</table>'),self.alternative_figure,W.HTML('<small>Rejection counts overlap: '+rejects+'</small>')]

    def _run_search(self,button):
        self.run_button.disabled=True;self._clear_search('Searching and checking all passing layouts…')
        self.progress.max=1;self.search_status.value='Checking inputs and searching…';self.progress.bar_style='info'
        try:
            config=SearchConfig(**{n:tuple(w.value) for n,w in self.search_lists.items()},objective=self.objective.value,max_cases=self.limit.value)
            def update(n,total):self.progress.max=total;self.progress.value=n
            run=sensitivity_search if self._search_force_mode()=='fixed' else search
            result=run(self.case,config,update);self.search_result=result
            self._render_candidates(reset_page=True)
            self.progress.bar_style='success' if result.passed else 'warning'
            self.search_status.value=f'<b>Search complete:</b> {result.evaluated:,} evaluated; {result.passed:,} passing layouts.'
            if not result.passed:
                common='; '.join(f'{html.escape(k)} ({v:,})' for k,v in sorted(result.rejection_counts.items(),key=lambda item:-item[1])[:3])
                self.search_status.value+='<br>No passing cages. Most frequent failures: '+common
        except Exception as exc:
            self.progress.bar_style='danger'
            self.search_status.value='<span role="alert" style="color:#9d302b"><b>Search stopped:</b> '+html.escape(str(exc) or type(exc).__name__)+'</span>'
            self.search_text.value=self.search_status.value
        finally:self.run_button.disabled=False

    def _apply(self,button):
        if self.search_result is None or self.candidates.value is None:return
        if not same_design_basis(self.search_result.base_case,self.case):
            self._update_search_basis();return
        result=self.search_result;index=self.candidates.value;chosen=candidate_case(result,index)
        if 'cap_type' in self.case:chosen['cap_type']=self.case['cap_type']
        if 'pile_visual' in self.case:chosen['pile_visual']=deepcopy(self.case['pile_visual'])
        self.busy=True
        try:
            self.case=chosen
            for n,w in self.controls.items():w.value=chosen['inputs'][n]
            self.transverse_panel.sync()
            self.pile_appearance.sync()
        finally:self.busy=False
        self.refresh();self._update_search_basis();self.message.value=f'Applied candidate #{index+1}. Live drawings and checks now show that layout.'
        self._notify_case_change()

    def _export_panel(self):
        self.blockpad_export=BlockpadExportPanel(self)
        self.bpad_path=self.blockpad_export.path
        self.case_export_folder=None
        self.case_download_files=self.blockpad_export.colab_files
        self.case_download_output=W.Output()
        self.case_export_status=W.HTML()
        self.case_export_button=W.Button(description='Export case + checks',icon='download',button_style='success',layout=W.Layout(width='210px'))
        self.case_export_button.on_click(self._export)
        self.case_report_button=W.Button(description='Generate calculation report',icon='file-text-o',button_style='info',layout=W.Layout(width='250px'))
        self.case_report_button.on_click(lambda _:self._export(None,download_kind='html'))
        self.case_html_button=W.Button(description='Download saved HTML report',icon='download',disabled=True,layout=W.Layout(width='250px'))
        self.case_html_button.on_click(lambda _:self._download_case_export('html'))
        self.case_json_button=W.Button(description='Download saved JSON',icon='download',disabled=True,layout=W.Layout(width='210px'))
        self.case_zip_button=W.Button(description='Download full bundle ZIP',icon='download',disabled=True,layout=W.Layout(width='230px'))
        self.case_json_button.on_click(lambda _:self._download_case_export('json'))
        self.case_zip_button.on_click(lambda _:self._download_case_export('zip'))
        location=('Colab first saves a temporary runtime copy, then starts a browser download of <b>selected_case.json</b>. '
                  'A /content/ path is on Colab, not your computer or Google Drive. Download the file before ending the runtime.'
                  if self.case_download_files else
                  'Export saves a copy on the computer running this notebook and shows a JSON download link below. '
                  'Use that link to save a copy on the computer where your browser is open.')
        return W.VBox([W.HTML('<h3>Save / reuse a selected case</h3><p><b>selected_case.json</b> is the file to load next time. '
            'The full bundle also includes the calculation report, checks, drawings, equation trace and search alternatives.</p>'
            '<p><b>Generate calculation report</b> evaluates the current inputs and downloads a standalone HTML report with '
            'mathematical equations, results, numeric substitutions, and collapsible calculation sections. '
            'Use <b>Geometry plots</b> at the top of the report for the dimensioned plan, elevation, pile and between-pile sections, '
            'reinforcement plan, 3D cage, and exact dimension tables. '
            'Open the downloaded file in Chrome or Edge. Use <b>Expand all</b>, <b>Collapse all</b>, or <b>Print / save PDF</b> in the report. '
            'Equations and plots are embedded for offline use. The report covers the cap calculation; loaded pile-analysis reviews remain in the full bundle.</p><p>'+location+'</p>'
            '<p><b>Choose where to save:</b> your browser controls the download folder. In Chrome, open Settings → Downloads '
            'and enable <b>Ask where to save each file before downloading</b>. Otherwise, check the browser’s Downloads list '
            'for the actual location. The notebook cannot select a folder on your other computer.</p>'
            '<p>Download buttons use the <b>most recent successful export</b>. Export again after changing inputs.</p>'),
            W.HBox([self.case_export_button,self.case_json_button,self.case_zip_button],layout=W.Layout(flex_flow='row wrap')),
            W.HBox([self.case_report_button,self.case_html_button],layout=W.Layout(flex_flow='row wrap')),
            self.case_export_status,self.case_download_output,self.blockpad_export.ui])

    def _case_export_notice(self,title,detail,kind='info'):
        self.case_export_status.value=notice_html(title,detail,kind)
        self.message.value=self.case_export_status.value

    def _download_case_export(self,kind='json'):
        if self.case_export_folder is None:return
        from IPython.display import clear_output,display,HTML
        import base64
        import zipfile
        folder=self.case_export_folder
        try:
            if kind=='zip':
                path=folder.with_suffix('.zip')
                with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
                    for file in sorted(folder.rglob('*')):
                        if file.is_file():archive.write(file,file.relative_to(folder.parent))
                mime='application/zip'
            elif kind=='html':
                path=folder/'calculation_report.html';mime='text/html'
            else:
                path=folder/'selected_case.json';mime='application/json'
            with self.case_download_output:
                clear_output(wait=True)
                if self.case_download_files:
                    self.case_download_files.download(str(path.resolve()))
                    detail='Browser download requested for <b>'+html.escape(path.name)+'</b>. Check your browser’s Downloads list; completion is not confirmed by the notebook.'
                else:
                    # An absolute FileLink can point outside Jupyter's served root.
                    # Embed the exported bytes so this works from another computer too.
                    payload=base64.b64encode(path.read_bytes()).decode('ascii')
                    display(HTML(f'<a download="{html.escape(path.name,quote=True)}" href="data:{mime};base64,{payload}">Download {html.escape(path.name)}</a>'))
                    detail='Click the download link below to save <b>'+html.escape(path.name)+'</b> on this computer.'
            self._case_export_notice('CASE EXPORT READY',detail+'<br>Copy on the notebook runtime: <code>'+html.escape(str(path.resolve()))+'</code>','success')
        except Exception as exc:
            self._case_export_notice('CASE SAVED — DOWNLOAD NEEDS RETRY',html.escape(str(exc))+
                '<br>Use the saved JSON, HTML report or full bundle download button to retry. Runtime folder: <code>'+html.escape(str(folder.resolve()))+'</code>','pending')

    def _export(self,button,download_kind='json'):
        self.case_export_button.disabled=self.case_report_button.disabled=True
        try:
            folder=export_bundle(self.case,self.export_root,self.search_result,search_filter=self._search_filter())
            if self.pile_review.review is not None:
                self.pile_review.save_bundle(folder/'pile_review')
            self.last_export=self.case_export_folder=folder.resolve()
            self.case_json_button.disabled=self.case_zip_button.disabled=self.case_html_button.disabled=False
            self._download_case_export(download_kind)
        except Exception as exc:
            previous=('<br>Download buttons still refer to the previous successful export: <code>'+html.escape(str(self.case_export_folder))+'</code>') if self.case_export_folder else ''
            self._case_export_notice('EXPORT STOPPED',html.escape(str(exc))+previous,'error')
        finally:self.case_export_button.disabled=self.case_report_button.disabled=False

    def _export_bpad(self,button):
        self.blockpad_export.export(button)

    def display(self):
        from IPython.display import display
        for figure in [*self.figures,self.force_diagrams.figure]:
            if figure is not None:figure.prepare_display()
        display(self.ui)
        return self

    def close(self):
        self.pile_review.close()
        self.force_diagrams.close()
        self.transverse_panel.close()
        self.views.close()
        self._close_alternative_plot()
        self.case_listeners.clear()
        self.ui.close()
