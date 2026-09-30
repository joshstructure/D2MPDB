"""Jupyter interface. All normal input, search and export work stays in the notebook."""
from copy import deepcopy
from pathlib import Path
import html
import json
import ipywidgets as W
import plotly.graph_objects as go
from .model import default_case,evaluate,INPUTS,GEOMETRY,formula_trace
from .optimizer import search,SearchConfig,candidate_case,filter_candidates,candidate_dc,candidate_governing,governing_check,DC_SCOPES
from .io import load_case,export_bundle,export_blockpad
from .fbmp_widgets import XMLImportPanel
from .blockpad_widgets import BlockpadExportPanel
from .widget_compat import Tab, Accordion
from .source_status import upload_entries,source_html,import_receipt,receipt_html,notice_html
from .visuals import section_figure,elevation_figure,hoop_figure,results_figure,optional_service_figure,ratios_figure,alternatives_figure,checks_html,spacing_html

LABELS={'b':'Cap width','h':'Cap depth','C_t':'Top cover','C_b':'Bottom cover','C_s':'Side cover',
 'N_pile':'Number of piles','S_pile':'Pile spacing','D_pile':'Pile width','E_clear':'Actual edge clearance','E_detail':'Extra end allowance',
 'fc':"Concrete f′c",'fy':'Steel fy','Es':'Steel modulus',
 'Bar_N1':'Top row 1 bar','Bar_N2':'Top row 2 bar','Bar_N3':'Top row 3 bar','n_N1':'Top row 1 count','n_N2':'Top row 2 count','n_N3':'Top row 3 count',
 'Bar_pos':'Bottom main bar','Bar_U':'U-leg bar','n_P1':'Pile bottom row 1','n_P2':'Pile bottom row 2','n_PU':'Pile U-leg count',
 'n_B1':'Bearing bottom row 1','n_B2':'Bearing bottom row 2','n_BU':'Bearing U-leg count',
 'Bar_v':'Closed hoop bar','n_loop':'Effective hoop loops','Bar_skin':'Skin bar','n_skin':'Skin count per side',
 's_row':'Row center spacing','s_G':'Global hoop spacing','s_L':'Low hoop spacing',
 'Mu_N':'Strength · negative','Mu_P':'Strength · pile positive','Mu_B':'Strength · bearing positive',
 'MI_N':'Service I · negative','MI_P':'Service I · pile positive','MI_B':'Service I · bearing positive',
 'Vu_G':'Global shear','Vu_L':'Low interval shear','Tu':'Torque magnitude',
 'Ready_III':'Service III loads ready','Ready_fatigue':'Fatigue loads ready','Manual_spacing':'Override bar spacing',
 'phi_f':'Flexural resistance factor','phi_v':'Shear resistance factor','gamma_e':'Exposure factor','gamma_fat':'Fatigue load factor',
 'beta_v':'Shear β','theta':'Compression angle θ','alpha_v':'Hoop angle α','fpc':'Precompression','Ao_factor':'Effective torsion area factor',
 'SP_detail_N':'Top spacing override','SP_detail_P':'Pile spacing override','SP_detail_B':'Bearing spacing override','SP_detail_skin':'Skin spacing override','S_leg_detail':'Inner leg spacing'}

GROUPS={
 'Steel': [('Top rows','Bar_N1 n_N1 Bar_N2 n_N2 Bar_N3 n_N3'),('Bottom rows','Bar_pos n_P1 n_P2 n_B1 n_B2'),('Hoops and skin','Bar_v n_loop s_G s_L Bar_skin n_skin s_row'),('U legs / spacing overrides','Bar_U n_PU n_BU Manual_spacing SP_detail_N SP_detail_P SP_detail_B SP_detail_skin S_leg_detail')],
 'Geometry':[('Section and cover','b h C_t C_b C_s'),('Pile row and cap ends','N_pile S_pile D_pile E_clear E_detail')],
 'Loads':[('Strength envelopes','Mu_N Mu_P Mu_B Vu_G Vu_L Tu'),('Service I','MI_N MI_P MI_B')],
 'Pending':[('Service III','Ready_III MIII_N MIII_P MIII_B'),('Fatigue','Ready_fatigue MDL_N MDL_P MDL_B DMLL_N DMLL_P DMLL_B')],
 'Factors':[('Materials','fc fy Es'),('Design assumptions','phi_f phi_v gamma_e gamma_fat beta_v theta alpha_v fpc Ao_factor')]
}

class CapNotebook:
    def __init__(self,case=None,export_root='exports'):
        self.case=deepcopy(case or default_case());self.export_root=Path(export_root)
        self.controls={};self.busy=False;self.search_result=None;self.current=None;self.figures=[];self.last_export=None
        self.browsing=False;self.filtered_indices=[];self.alternative_figure=None
        self.case_listeners=[]
        self.import_receipt=None;self.import_notice=W.HTML()
        self.banner=W.HTML();self.metrics=W.HTML();self.message=W.HTML()
        self.cage=W.VBox(layout=W.Layout(max_height='820px',overflow='auto'));self.results=W.VBox(layout=W.Layout(max_height='820px',overflow='auto'));self.register=W.HTML();self.trace=W.HTML()
        self.clearance=W.BoundedFloatText(value=self.case['screening']['minimum_clear_in'],min=0,max=12,step=.25,description='Trial clear (in)',style={'description_width':'120px'},layout=W.Layout(width='260px'))
        self.clearance.observe(self._changed,names='value')
        self.input_tabs=self._inputs()
        self.plot_tabs=Tab(children=[self.cage,self.results,W.VBox([self.register],layout=W.Layout(max_height='850px',overflow='auto')),W.VBox([self.trace],layout=W.Layout(max_height='750px',overflow='auto'))],layout=W.Layout(flex='1 1 650px',min_width='560px'))
        for i,title in enumerate(['Live cage','Plots','Pass / D/C register','Equation trace']):self.plot_tabs.set_title(i,title)
        self.upload=W.FileUpload(accept='.json',multiple=False,description='Load case JSON')
        self.upload.observe(self._uploaded,names='value')
        reset=W.Button(description='Reset starting case',icon='undo');reset.on_click(lambda _:self.load(default_case()))
        self.source_label=W.HTML()
        self.source_id=W.Text(description='Analysis ID',placeholder='Name of the new force analysis run',layout=W.Layout(width='430px'))
        self.source_confirm=W.Checkbox(value=False,description='I have supplied forces for the current geometry',indent=False,layout=W.Layout(width='420px'))
        stamp=W.Button(description='Record analyzed geometry',icon='check');stamp.on_click(self._stamp)
        source=Accordion(children=[W.VBox([self.source_id,self.source_confirm,stamp,W.HTML('<small>Use after entering fresh analysis forces. Changing geometry alone does not rerun FB-MultiPier.</small>')])]);source.set_title(0,'Record a manually updated analysis case');source.selected_index=None
        self.search_panel=self._search_panel();self.export_panel=self._export_panel()
        self.xml_import=XMLImportPanel(self,LABELS)
        self.ui=W.VBox([W.HTML('<h2 style="color:#213649;margin-bottom:4px">Pier-cap design explorer</h2><p>Change an input → inspect the cage and checks → search practical steel → export a review case.</p>'),
            W.HBox([self.upload,reset]),self.xml_import.ui,self.import_notice,self.source_label,source,self.banner,self.metrics,
            W.HBox([self.input_tabs,self.plot_tabs],layout=W.Layout(display='flex',flex_flow='row wrap',align_items='flex-start',grid_gap='16px')),
            self.search_panel,self.export_panel,self.message],layout=W.Layout(width='100%'))
        self.refresh()

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
                    control.tooltip=meta['caption'];control.observe(self._changed,names='value');self.controls[n]=control
                    label=LABELS.get(n,n.replace('_',' '));unit=meta['unit'] or ''
                    control.description=label;control.style.description_width='174px';control.layout.width='285px'
                    rows.append(W.HBox([control,W.HTML(html.escape(unit),layout=W.Layout(width='53px'))]))
                if title=='Hoops and skin':rows.extend([self.clearance,W.HTML('<small>Clear-spacing screen is a trial assumption. Confirm code/aggregate/detailing requirements.</small>')])
                panels.append(W.VBox(rows))
            accordion=Accordion(children=panels)
            for i,(title,_) in enumerate(sections):accordion.set_title(i,title)
            accordion.selected_index=0;tabs.append(accordion)
        tab=Tab(children=tabs,layout=W.Layout(flex='0 0 360px',width='360px'))
        for i,name in enumerate(GROUPS):tab.set_title(i,name)
        return tab

    def _changed(self,change):
        if self.busy:return
        self.case['inputs']={n:w.value for n,w in self.controls.items()}
        self.case['screening']['minimum_clear_in']=self.clearance.value
        self._clear_search('Inputs changed. Run the search to refresh alternatives.')
        self.refresh()
        self._notify_case_change()

    def _notify_case_change(self):
        for callback in self.case_listeners:callback()

    def refresh(self):
        self.source_label.value=source_html(self.case)
        self.import_notice.value=receipt_html(self.import_receipt,self.case)
        try:e=evaluate(self.case)
        except Exception as exc:
            self.current=None;self.banner.value=f'<div style="padding:14px;background:#ffe9e7;color:#9d302b"><b>INPUT ERROR</b><br>{html.escape(str(exc))}</div>'
            self.metrics.value='';self.cage.children=[];self.results.children=[];self.register.value='';self.trace.value='';return
        self.current=e;color='#fff3d9' if e.eligible else '#ffe9e7'
        extra='<br>'.join(html.escape(s) for s in e.issues)
        self.banner.value=f'<div style="padding:12px;background:{color};border-radius:6px"><b>{html.escape(e.status)}</b>{"<br>"+extra if extra else ""}<br><small>Sectional calculation only. D-regions, anchorage, pile heads, applicability and final detail review remain open.</small></div>'
        strength=governing_check(e,'strength');overall=governing_check(e)
        items=[('Strength D/C',f'{strength.ratio:.3f}'),('All-check utilization',f'{e.max_dc:.3f}'),('Gross steel estimate',f'{e.weight_lb:,.0f} lb'),('Top steel area',f'{e.value("As_N"):.2f} in²'),('Top Service I stress',f'{e.value("fs_I_N"):.2f} ksi'),('Cap length',f'{e.value("L_cap")/12:.3f} ft'),('Nominal end extension',f'{e.value("E_end"):g} in')]
        self.metrics.value='<div style="display:flex;flex-wrap:wrap;gap:10px;margin:12px 0">'+''.join(f'<div style="padding:10px 18px;background:#eaf1f6;border-radius:5px"><small>{k}</small><br><b style="font-size:23px;color:#1f5b91">{v}</b></div>' for k,v in items)+'</div>'
        self.metrics.value+=f'<p><b>Controls strength:</b> {html.escape(strength.label)}. <b>Controls all checks:</b> {html.escape(overall.label)}.<br><small>All-check utilization also includes spacing and minimum/detailing limits. It does not measure a single reserve against increased load.</small></p>'
        if overall.key in ('Chk_spacing_G','Chk_spacing_L'):
            zone=overall.key[-1];s=e.value('S_leg');limit=e.value('Sw_'+zone)
            self.metrics.value+=f'<p><b>Across-cap hoop legs:</b> {s:.3f} in / {limit:.3f} in allowed = <b>{s/limit:.4f}</b>. Adding main bars or reducing along-cap hoop spacing leaves this across-cap distance unchanged.</p>'
        for old in self.figures:old.close()
        self.figures=[]
        def fw(fig):
            widget=go.FigureWidget(fig);self.figures.append(widget);widget.layout.autosize=True;return widget
        self.cage.children=[fw(section_figure(e,'B')),fw(section_figure(e,'P')),fw(elevation_figure(e)),fw(hoop_figure(e)),W.HTML('<small>Bar circles follow row counts, diameters and calculated positions. U legs are an inventory until their positions are defined. Only the outer hoop is drawn. Pile lengths and first hoop positions are symbolic.</small>')]
        self.results.children=[fw(results_figure(e)),W.HTML(spacing_html(e)),fw(optional_service_figure(e)),fw(ratios_figure(e)),W.HTML('<small>These plots compare imported force envelopes and sectional capacities. They are not a continuous moment/shear diagram or a rerun of FB-MultiPier.</small>')]
        self.register.value=checks_html(e)
        rows=''.join(f'<tr><td>{html.escape(t["name"])}</td><td>{html.escape(t["formula"])}</td><td>{html.escape(str(t["value"]))}</td></tr>' for t in formula_trace(e))
        self.trace.value='<p>324 source definitions, including five helper functions. Live results below use explicit units.</p><table class="cap-table"><tr><th>Name</th><th>Equation</th><th>Value</th></tr>'+rows+'</table>'

    def load(self,case,*,import_name=None):
        evaluate(case);self.busy=True
        try:
            self.case=deepcopy(case)
            self.import_receipt=import_receipt(case,import_name) if import_name else None
            for n,w in self.controls.items():w.value=case['inputs'][n]
            self.clearance.value=case['screening']['minimum_clear_in']
        finally:self.busy=False
        self._clear_search()
        self.refresh()
        self._notify_case_change()

    def _uploaded(self,change):
        if not self.upload.value:return
        try:
            self.import_receipt=None
            self.import_notice.value=notice_html('READING CASE FILE','Checking the uploaded inputs…','pending')
            entry=upload_entries(self.upload.value)[0]
            self.load(load_case(entry['content']),import_name=entry['name'])
            self.message.value='<b>Case loaded.</b>'
        except Exception as exc:
            self.import_notice.value=notice_html('CASE IMPORT FAILED',html.escape(str(exc))+'<br>Review the active force source below.','error')

    def _stamp(self,button):
        if not self.source_confirm.value or not self.source_id.value.strip():
            self.message.value='Enter the analysis ID and confirm that the entered forces were analyzed for the current geometry.';return
        self.case['analysis']={'id':self.source_id.value.strip(),'geometry':{k:self.case['inputs'][k] for k in GEOMETRY},'notes':'User recorded a manually updated force analysis in the notebook.'}
        self.case.pop('section_study',None)
        self.source_confirm.value=False;self._clear_search();self.refresh()
        self._notify_case_change()

    def _search_panel(self):
        self.search_lists={}
        configs=[('main_bars','Main bars',(5,6,7,8,9,10,11),(6,7,8,9)),('top_counts','Top counts',(4,5,6,7,8,9,10,12),(4,6,8)),('bottom_counts','Bottom counts',(4,5,6,7,8,9,10,12),(4,6,8)),('hoop_bars','Hoop bars',(3,4,5,6,7),(4,5,6)),('hoop_spacings','Spacing (in)',(4,5,6,7,8,9,10,12),(6,8,10)),('skin_bars','Skin bars',(3,4,5,6),(4,5)),('skin_counts','Skin / side',(4,5,6,7,8,9,10),(5,6,7))]
        boxes=[]
        for name,label,options,value in configs:
            w=W.SelectMultiple(options=options,value=value,rows=5,layout=W.Layout(width='112px'));self.search_lists[name]=w;boxes.append(W.VBox([W.HTML('<b>'+label+'</b>'),w]))
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
        self.progress=W.IntProgress(min=0,max=1,value=0,description='Search')
        self.search_text=W.HTML();self.candidates=W.Dropdown(options=[],description='Alternative',layout=W.Layout(width='90%'),style={'description_width':'80px'})
        self.apply_button=W.Button(description='Apply selected layout',disabled=True,icon='check');self.apply_button.on_click(self._apply)
        self.alternative_output=W.VBox()
        return W.VBox([W.HTML('<h3>Search practical steel</h3><p>Bounded enumeration: one continuous top row and bottom row, a common main bar size, one closed hoop and uniform spacing. Pile and bearing bottom cages match. Multirow / U-leg arrangements can be explored manually above. Hold Ctrl/Cmd to select several choices.</p>'),
            W.HBox(boxes,layout=W.Layout(flex_flow='row wrap',grid_gap='10px')),W.HBox([self.limit,self.run_button,self.progress],layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<h4>Browse every passing layout</h4><p>These are reinforcement layouts for the current force case. <b>Strength checks only</b> is the default margin target: set <b>Max D/C</b> to 0.90 to seek reserve in those checks. Filtering, ranking and paging reuse the completed search.</p>'),
            W.HBox([self.dc_limit,self.dc_scope,self.objective],layout=W.Layout(flex_flow='row wrap')),
            W.HTML('<small><b>All available checks</b> includes spacing, minimum steel, strain and service checks. <b>Strength checks only</b> targets flexure, shear, combined shear/torsion steel and longitudinal steel; all other available checks must still pass. Missing Service III/fatigue checks stay pending. Largest margin ranks the selected D/C scope.</small>'),
            self.search_text,W.HBox([self.previous_page,self.page,self.next_page,self.page_size],layout=W.Layout(flex_flow='row wrap')),self.candidates,self.apply_button,self.alternative_output,
            W.HTML('<small>Gross steel is a comparison estimate: full-length main/skin bars and hoops, excluding hooks, laps, anchorage and waste. Cage score = longitudinal bar count + 5 × distinct bar sizes. Search results are conditional candidates, not finalized designs.</small>')])

    def _close_alternative_plot(self):
        if self.alternative_figure is not None:self.alternative_figure.close();self.alternative_figure=None
        self.alternative_output.children=[]

    def _clear_search(self,message=''):
        self.search_result=None;self.filtered_indices=[];self.candidates.options=[];self.apply_button.disabled=True
        self.page.value=1;self.page.max=1;self.page.disabled=True
        self.previous_page.disabled=True;self.next_page.disabled=True;self.search_text.value=message
        self._close_alternative_plot()

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
            if old_selected in shown:self.candidates.value=old_selected
            self.previous_page.disabled=self.page.value<=1;self.next_page.disabled=self.page.value>=pages
            self.apply_button.disabled=not shown
        finally:self.browsing=False
        extent=f'Showing {start+1:,}–{start+len(shown):,} of {len(indices):,} matches · page {self.page.value} of {pages}.' if shown else 'No layouts match this D/C filter.'
        completeness='All listed combinations evaluated.' if result.exhaustive else 'Case limit reached; remaining combinations were not evaluated.'
        self.search_text.value=f'<p><b>{result.passed:,} layouts pass the available checks and cage screen.</b> {len(indices):,} meet <b>{DC_SCOPES[scope]} ≤ {target:.3f}</b>. {extent}<br>{result.evaluated:,} / {result.total:,} combinations evaluated. {completeness} {result.elapsed:.1f} seconds. Every passing layout is retained and unit-checked. Candidate IDs stay fixed within this search.</p>'
        strength_count=sum(c.strength_dc<=target+1e-12 for c in result.candidates)
        all_count=sum(c.max_dc<=target+1e-12 for c in result.candidates)
        self.search_text.value+=f'<p>At target {target:.3f}: <b>{strength_count:,} strength matches</b> · <b>{all_count:,} all-check matches</b>. The all-check target also tightens spacing and minimum/detailing criteria.</p>'
        if not shown and result.candidates:
            best=min(result.candidates,key=lambda c:candidate_dc(c,scope))
            self.search_text.value+=f'<p><b>Best available {DC_SCOPES[scope].lower()} D/C: {candidate_dc(best,scope):.6f}</b> · controlling check: {html.escape(candidate_governing(best,scope))}. No layout in the evaluated choices meets {target:.3f} for this scope.</p>'
            if scope=='all':self.search_text.value+='<p>Spacing or minimum/detailing checks may set this floor. Adding main bars alone may not lower it. Strength-only filtering is a separate target; it does not mean every D/C is below your limit.</p>'
        rows=''.join(f'<tr><td>{rank}</td><td>#{i+1}</td><td>{html.escape(c.label)}</td><td>{c.weight_lb:.0f}</td><td>{candidate_dc(c,scope):.4f}</td><td>{c.strength_dc:.4f}</td><td>{c.max_dc:.4f}</td><td>{html.escape(candidate_governing(c,scope))}</td></tr>' for rank,(i,c) in enumerate(((i,result.candidates[i]) for i in shown),start+1))
        rejects='; '.join(f'{html.escape(k)}: {v}' for k,v in sorted(result.rejection_counts.items(),key=lambda t:-t[1])[:8])
        self._close_alternative_plot()
        self.alternative_figure=go.FigureWidget(alternatives_figure(result,indices,dc_scope=scope,max_dc=target))
        self.alternative_output.children=[W.HTML('<table class="cap-table"><tr><th>Filtered rank</th><th>Candidate ID</th><th>Layout</th><th>Gross lb</th><th>Filter ratio</th><th>Strength D/C</th><th>All-check utilization</th><th>Controls filter</th></tr>'+rows+'</table>'),self.alternative_figure,W.HTML('<small>Rejection counts overlap: '+rejects+'</small>')]

    def _run_search(self,button):
        self.run_button.disabled=True;self._clear_search('Searching and checking all passing layouts…')
        try:
            config=SearchConfig(**{n:tuple(w.value) for n,w in self.search_lists.items()},objective=self.objective.value,max_cases=self.limit.value)
            def update(n,total):self.progress.max=total;self.progress.value=n
            result=search(self.case,config,update);self.search_result=result
            self._render_candidates(reset_page=True)
        except Exception as exc:self.search_text.value='<b>Search stopped:</b> '+html.escape(str(exc))
        finally:self.run_button.disabled=False

    def _apply(self,button):
        if self.search_result is None or self.candidates.value is None:return
        result=self.search_result;index=self.candidates.value;chosen=candidate_case(result,index)
        self.busy=True
        try:
            self.case=chosen
            for n,w in self.controls.items():w.value=chosen['inputs'][n]
        finally:self.busy=False
        self.refresh();self.message.value=f'Applied candidate #{index+1}. Live drawings and checks now show that layout.'
        self._notify_case_change()

    def _export_panel(self):
        export=W.Button(description='Export current case + checks',icon='download',button_style='success');export.on_click(self._export)
        self.blockpad_export=BlockpadExportPanel(self)
        self.bpad_path=self.blockpad_export.path
        return W.VBox([W.HTML('<h3>Save / reuse a selected case</h3><p>The JSON bundle is the single file to load next time. Exports include the D/C register, equation trace, Blockpad input assignments, all passing search alternatives and all current filter matches (every page). Saved cases retain force-source geometry so stale forces stay visible.</p>'),export,self.blockpad_export.ui])

    def _export(self,button):
        try:
            self.last_export=export_bundle(self.case,self.export_root,self.search_result,search_filter=self._search_filter())
            self.message.value='<b>Saved review bundle:</b> '+html.escape(str(self.last_export.resolve()))
        except Exception as exc:self.message.value='<b>Export stopped:</b> '+html.escape(str(exc))

    def _export_bpad(self,button):
        self.blockpad_export.export(button)

    def display(self):
        from IPython.display import display
        display(self.ui)
        return self

    def close(self):
        for figure in self.figures:figure.close()
        self._close_alternative_plot()
        self.case_listeners.clear()
        self.ui.close()
