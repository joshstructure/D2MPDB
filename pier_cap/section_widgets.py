"""Interactive geometry study attached to the notebook's existing live calculator."""
from copy import deepcopy
import html
import ipywidgets as W
from .widget_compat import Accordion
import plotly.graph_objects as go

from .model import evaluate
from .optimizer import SearchConfig
from .io import load_case
from .source_status import source_html,upload_entries,notice_html
from .sections import (SectionGrid, CostRates, SectionCache, dimension_values, run_section_study,
                       section_rows, selected_section_case, export_section_study, comparison_costs, cost_gap, ranked_cost_rows)
from .section_visuals import (section_heatmap, section_pareto, section_cost_chart, cost_summary_html,
                              cost_table_html, highlight_section, METRICS, COST_METRICS, study_label)
from .visuals import section_figure, results_figure, checks_html, spacing_html


class SectionStudy:
    def __init__(self, app):
        self.app = app
        self.study = None
        self.rows = []
        self.cache = SectionCache()
        self.library = {}
        self.source_status = W.HTML()
        self.width_screen = W.HTML()
        self.rendering = self.applying = False
        self.figures = []
        self.preview_figures = []
        self.last_export = None
        self.bounds = {}
        dimension_controls = []
        for axis, title, values in [('width', 'Width (in)', (44, 52, 4)), ('depth', 'Depth (in)', (36, 60, 6))]:
            controls = [W.FloatText(value=value, description=label, layout=W.Layout(width='180px'), style={'description_width': '50px'})
                        for label, value in zip(('From', 'To', 'Step'), values)]
            self.bounds[axis] = controls
            dimension_controls.append(W.HBox([W.HTML(f'<b>{title}</b>', layout=W.Layout(width='100px')), *controls], layout=W.Layout(flex_flow='row wrap')))
        self.mode = W.Dropdown(options=[('Sensitivity · fixed forces', 'fixed'), ('Only analysis-matched cases', 'matched')],
                               value='fixed', description='Forces', layout=W.Layout(width='350px'))
        self.min_width = W.FloatText(value=0, description='Project min width (in)', style={'description_width': '155px'}, layout=W.Layout(width='270px'))
        self.min_depth = W.FloatText(value=0, description='Project min depth (in)', style={'description_width': '155px'}, layout=W.Layout(width='270px'))
        self.budget = W.BoundedIntText(value=100000, min=1, max=500000, description='Total case budget', style={'description_width': '135px'}, layout=W.Layout(width='270px'))
        self.target = W.BoundedFloatText(value=.9, min=.01, max=1, step=.05, description='Strength D/C ≤', style={'description_width': '125px'}, layout=W.Layout(width='245px'))
        self.metric = W.Dropdown(options=[(v, k) for k, v in METRICS.items()], value='steel_lb', description='Map color', layout=W.Layout(width='385px'))
        self.cell_labels = W.Dropdown(options=[('Concrete + steel quantities', 'quantities'), ('Concrete / steel / forms costs', 'costs'), ('Hover only', 'none')],
                                      value='quantities', description='Cell labels', layout=W.Layout(width='385px'))
        self.use_cost = W.Checkbox(value=False, description='Use my comparison unit rates', indent=False, layout=W.Layout(width='300px'))
        self.rates = [W.FloatText(value=0, description=label, style={'description_width': '140px'}, layout=W.Layout(width='255px'))
                      for label in ('Concrete / yd³', 'Steel / lb', 'Forms / ft²')]
        self.cost_controls = W.VBox([self.use_cost, W.HBox(self.rates, layout=W.Layout(flex_flow='row wrap')),
                                    W.HTML('<small>Use one currency consistently. No prices are assumed. Zero excludes an item. Quantities are gross: steel excludes hooks/laps/waste; forms include sides, ends and soffit. The material frontier does not include formwork or labor tradeoffs.</small>')])
        self.upload = W.FileUpload(accept='.json', multiple=True, description='Add analyzed cases')
        self.upload.observe(self._uploaded, names='value')
        clear_library = W.Button(description='Clear analysis library')
        clear_library.on_click(self._clear_library)
        self.library_note = W.HTML('Current source case is available at its own section. No additional analysis cases loaded.')
        library_panel = Accordion(children=[W.VBox([W.HBox([self.upload, clear_library]), self.library_note,
                                  W.HTML('<small>Upload saved case JSON files containing actual forces and their matching geometry. Other project inputs must agree. A study export with fixed forces is not a new analysis. Distinct analyses at the same section are reported as a conflict.</small>')])])
        library_panel.set_title(0, 'Optional: analysis library for different sections')
        library_panel.selected_index = None
        self.run_button = W.Button(description='Run section study', button_style='primary', icon='search')
        self.run_button.on_click(self._run)
        self.progress = W.IntProgress(value=0, max=1, description='Sections')
        self.notice = W.HTML()
        self.summary = W.HTML()
        self.cost_summary = W.HTML()
        self.cheapest_button = W.Button(description='Select cheapest section + cage', icon='check', disabled=True, layout=W.Layout(width='280px'))
        self.cheapest_button.on_click(self._select_cheapest)
        self.cost_table = W.HTML()
        self.cost_details = Accordion(children=[self.cost_table])
        self.cost_details.set_title(0, 'All sections ranked by estimated cost')
        self.cost_details.selected_index = None
        self.cost_details.layout.display = 'none'
        self.material_details = Accordion(children=[])
        self.material_details.layout.display = 'none'
        self.charts = W.HBox(layout=W.Layout(flex_flow='row wrap'))
        self.section = W.Dropdown(options=[], description='Section', layout=W.Layout(width='500px'))
        self.cage = W.Dropdown(options=[], description='Cage', layout=W.Layout(width='95%'))
        self.section.observe(self._section_changed, names='value')
        self.cage.observe(self._cage_changed, names='value')
        self.selection_info = W.HTML()
        self.preview = W.VBox()
        self.apply_button = W.Button(description='Load selected case into calculator', icon='arrow-up', disabled=True, layout=W.Layout(width='295px'))
        self.apply_button.on_click(self._apply)
        self.refine_button = W.Button(description='Refine around this section', icon='search-plus', disabled=True, layout=W.Layout(width='230px'))
        self.refine_button.on_click(self._refine)
        self.export_button = W.Button(description='Export section study', icon='download', disabled=True)
        self.export_button.on_click(self._export)
        self.ui = W.VBox([
            W.HTML('<h2>Cap section & steel study</h2><p>Search width and depth around the reinforcement choices in the main calculator. Click a heatmap cell or cost bar to explore that section and every cage meeting your strength target.</p>'
                   '<p><b>Fixed-force sensitivity:</b> forces stay unchanged as geometry varies; self-weight and stiffness effects are not reanalyzed. <b>Analysis-matched mode:</b> only supplied matching force cases are evaluated. All results remain subject to pending checks and the source calculation scope.</p>'),
            *dimension_controls, W.HBox([self.min_width, self.min_depth, self.budget], layout=W.Layout(flex_flow='row wrap')),
            self.width_screen,
            W.HTML('<small>Enter any larger bearing/project minimums above. Zero means no additional project minimum. The search retains the single-outer-hoop family; wider caps may need a different cage topology.</small>'),
            self.source_status, self.mode, library_panel, W.HBox([self.run_button, self.progress]), self.notice,
            W.HBox([self.target, self.metric, self.cell_labels], layout=W.Layout(flex_flow='row wrap')), self.cost_controls,
            self.summary, self.cost_summary, self.cheapest_button, self.charts, self.cost_details, self.material_details,
            self.section, self.cage, self.selection_info,
            W.HBox([self.apply_button, self.refine_button, self.export_button], layout=W.Layout(flex_flow='row wrap')), self.preview,
        ])
        for control in [*(w for group in self.bounds.values() for w in group), self.mode, self.min_width, self.min_depth, self.budget]:
            control.observe(self._grid_changed, names='value')
        for control in [self.target, self.metric, self.cell_labels, self.use_cost, *self.rates]:
            control.observe(self._view_changed, names='value')
        for control in [*self.app.search_lists.values(), self.app.limit]:
            control.observe(self._grid_changed, names='value')
        self.app.case_listeners.append(self.invalidate)
        self._refresh_source()

    def _refresh_source(self):
        note = ('The next fixed-force study uses these inputs at every trial section. Library uploads do not replace them.'
                if self.mode.value == 'fixed' else
                'Analysis-matched mode also uses the separate saved cases in the analysis library at their matching sections.')
        self.source_status.value = source_html(self.app.case,'FORCE SOURCE FOR SECTION STUDY',note)
        p = self.app.case['inputs']
        tolerance = evaluate(self.app.case).value('Tol_pile')
        width = max(self.min_width.value, p['D_pile'] + 2 * (p['E_clear'] + tolerance))
        self.width_screen.value = (
            f'<p><b>Transverse width screen: {width:g} in.</b> '
            f'Maximum of project minimum {self.min_width.value:g} in and '
            f'pile {p["D_pile"]:g} + 2 × (adopted clearance {p["E_clear"]:g} + location tolerance {tolerance:g}) in.'
            f'<br>Extra longitudinal end allowance {p["E_detail"]:g} in affects cap length only; '
            'it is not added to the side clearance.</p>')

    def rebind(self, app):
        """Keep an already displayed study attached when its workbench cell reruns."""
        if self.app is app:
            return
        if self.invalidate in self.app.case_listeners:
            self.app.case_listeners.remove(self.invalidate)
        for control in [*self.app.search_lists.values(), self.app.limit]:
            control.unobserve(self._grid_changed,names='value')
        self.app = app
        self.app.case_listeners.append(self.invalidate)
        for control in [*app.search_lists.values(), app.limit]:
            control.observe(self._grid_changed,names='value')
        self.invalidate()

    def _close_preview(self):
        for figure in self.preview_figures:
            figure.close()
        self.preview_figures = []
        self.preview.children = []

    def invalidate(self):
        self._refresh_source()
        if self.applying:
            return
        self.study = None
        self.rows = []
        for figure in self.figures:
            figure.close()
        self.figures = []
        self.charts.children = []
        self.rendering = True
        try:
            self.section.options = []
            self.cage.options = []
        finally:
            self.rendering = False
        self.apply_button.disabled = self.export_button.disabled = self.refine_button.disabled = True
        self.summary.value = self.selection_info.value = ''
        self._clear_cost_view()
        self._close_preview()
        self.notice.value = notice_html('SECTION STUDY NEEDS A NEW RUN',
            'Inputs changed. Previous plots and cage selections were cleared. Check the force source above, then click <b>Run section study</b>.','pending')

    def _grid_changed(self, change):
        if not self.rendering:
            self.invalidate()

    def _view_changed(self, change):
        if self.rendering:
            return
        if change['owner'] is self.use_cost:
            self.rendering = True
            try:
                if self.use_cost.value:
                    self.metric.value = 'cost_premium_pct'
                else:
                    if self.metric.value in COST_METRICS:
                        self.metric.value = 'steel_lb'
                    if self.cell_labels.value == 'costs':
                        self.cell_labels.value = 'quantities'
            finally:
                self.rendering = False
        if self.study is not None:
            self._render()

    def _clear_cost_view(self):
        self.cost_summary.value = self.cost_table.value = ''
        self.cheapest_button.disabled = True
        self.cheapest_button.layout.display = 'none'
        self.cost_details.layout.display = self.material_details.layout.display = 'none'
        self.material_details.children = []

    def _rates(self):
        if not self.use_cost.value:return None
        try:return CostRates(*(w.value for w in self.rates)).validate()
        except ValueError:return None

    def _uploaded(self, change):
        if not self.upload.value:
            return
        try:
            loaded = {entry['name']: load_case(entry['content']) for entry in upload_entries(self.upload.value)}
            self.library.update(loaded)
            self.invalidate()
            self.library_note.value = notice_html('ANALYSIS CASES ADDED TO LIBRARY',
                '<b>Loaded:</b> ' + ', '.join(html.escape(name) for name in self.library)+
                '<br>This does not replace the main calculator loads. Select <b>Only analysis-matched cases</b> to use this library.','success')
        except Exception as exc:
            self.library_note.value = '<b>Import stopped:</b> ' + html.escape(str(exc))

    def _clear_library(self, _):
        self.library.clear()
        self.upload.value = ()
        self.library_note.value = 'No additional analysis cases loaded. Current source case remains available at its own section.'
        self.invalidate()

    def _run(self, _):
        self.invalidate()
        self.run_button.disabled = True
        try:
            grid = SectionGrid(widths=dimension_values(*(w.value for w in self.bounds['width'])),
                               depths=dimension_values(*(w.value for w in self.bounds['depth'])),
                               force_mode=self.mode.value, max_total_cases=self.budget.value,
                               minimum_width_in=self.min_width.value, minimum_depth_in=self.min_depth.value)
            steel = SearchConfig(**{n: tuple(w.value) for n, w in self.app.search_lists.items()}, max_cases=self.app.limit.value)
            self.notice.value = 'Searching each section using the main calculator’s current steel choices…'
            def progress(done, sections, evaluated, total):
                self.progress.max = sections
                self.progress.value = done
                self.notice.value = f'{done} / {sections} sections processed · {evaluated:,} candidate evaluations accounted for.'
            self.study = run_section_study(deepcopy(self.app.case), grid, steel, analyzed_cases=list(self.library.values()),
                                           cache=self.cache, progress=progress)
            self.notice.value = f'Study completed in {self.study.elapsed:.1f} s. {self.study.new_evaluations:,} new evaluations; {sum(p.cache_hit for p in self.study.points)} section searches reused.'
            if self.study.evaluated == 0:
                reasons = '<br>'.join(html.escape(reason) for reason in dict.fromkeys(p.reason for p in self.study.points))
                self.notice.value = notice_html('NO STEEL CANDIDATES EVALUATED',
                    'Every section was skipped before the steel search. ' + reasons +
                    '<br>Review the width/depth ranges, project minimums and force mode above.', 'pending')
            self._render()
        except Exception as exc:
            self.notice.value = '<b>Study stopped:</b> ' + html.escape(str(exc))
        finally:
            self.run_button.disabled = False

    def _render(self):
        try:
            rates = self._rates()
            metric=self.metric.value if rates or self.metric.value not in COST_METRICS else 'steel_lb'
            labels=self.cell_labels.value if rates or self.cell_labels.value!='costs' else 'quantities'
            self.rows = section_rows(self.study, self.target.value, rates)
            for figure in self.figures:
                figure.close()
            heat = go.FigureWidget(section_heatmap(self.study, self.rows, metric, labels))
            pareto = go.FigureWidget(section_pareto(self.study, self.rows))
            heat.data[0].on_click(self._map_clicked)
            heat.data[1].on_click(self._map_clicked)
            for trace in pareto.data:
                trace.on_click(self._pareto_clicked)
            self._clear_cost_view()
            if rates:
                costs = go.FigureWidget(section_cost_chart(self.study, self.rows, self.section.value))
                for trace in costs.data:
                    trace.on_click(self._pareto_clicked)
                self.figures = [heat, costs, pareto]
                self.cost_summary.value = cost_summary_html(self.study, self.rows, rates)
                self.cost_table.value = cost_table_html(self.rows)
                self.cheapest_button.disabled = not bool(ranked_cost_rows(self.rows))
                self.cheapest_button.layout.display = ''
                self.cost_details.layout.display = self.material_details.layout.display = ''
                self.material_details.children = [pareto]
                self.material_details.set_title(0, 'Material tradeoff plot · quantities, not total cost')
                self.material_details.selected_index = None
            else:
                self.figures = [heat, pareto]
                self.cost_summary.value = ('<p><b>Cost comparison needs rates.</b> Showing material quantities and all available cages. Enter nonnegative rates with at least one positive value; no new search is needed.</p>' if self.use_cost.value else
                    '<p>Optional: enter comparison rates to rank sections by cost.</p>')
            self.charts.children = [W.VBox([f], layout=W.Layout(flex='1 1 600px', min_width='600px')) for f in self.figures[:2]]
            matches = [r for r in self.rows if r['matches']]
            screened = sum(p.state == 'GEOMETRY SCREEN' for p in self.study.points)
            if screened == len(self.study.points):
                complete = 'All sections excluded by geometry limits; no reinforcement search was performed.'
            else:
                complete = ('All eligible sections fully searched within the listed steel choices.' if self.study.exhaustive else
                            'Incomplete coverage: inspect partial searches, missing analysis or untested/error points.')
                if screened:
                    complete += f' {screened} sections excluded by geometry limits.'
            self.summary.value = f'<p><b>{study_label(self.study)}</b><br>{len(matches)} / {len(self.rows)} sections have cages at strength D/C ≤ {self.target.value:.3f}. '
            self.summary.value += f'{self.study.evaluated:,} / {self.study.total:,} possible combinations evaluated; geometry screens can exclude whole sections. {complete}<br>'
            self.summary.value += f'Adopted minimum width screen: {self.study.minimum_width_in:g} in. Each colored point uses its lightest matching cage. The frontier covers the explored points, not every possible design.</p>'
            if matches:
                metric = 'estimated_cost' if rates else metric
                best = min(matches, key=lambda r: (r[metric], r['steel_lb']))
                if not rates:
                    self.summary.value += f'<p><b>Lowest {html.escape(METRICS[metric].lower())} in this view:</b> {best["width_in"]:g} × {best["depth_in"]:g} in · {best[metric]:,.3f}. '
                    self.summary.value += 'This is a comparison candidate; pending service/fatigue and load-transfer/detail reviews remain.</p>'
            old = self.section.value
            old_cage = self.cage.value
            self.rendering = True
            try:
                ordered = ranked_cost_rows(self.rows) + [r for r in self.rows if r['estimated_cost'] is None] if rates else self.rows
                self.section.options = [(self._section_label(r), r['point_id']) for r in ordered]
                self.section.value = old if old is not None and 0 <= old < len(self.rows) else (best['point_id'] if matches else 0)
            finally:
                self.rendering = False
            self.export_button.disabled = False
            self.refine_button.disabled = False
            self._select_section(old_cage if self.section.value == old else None)
        except Exception as exc:
            self.rows = []
            for figure in self.figures:
                figure.close()
            self.figures = []
            self.charts.children = []
            self.summary.value = '<b>View needs input:</b> ' + html.escape(str(exc))
            self._clear_cost_view()
            self.selection_info.value = ''
            self.apply_button.disabled = self.export_button.disabled = self.refine_button.disabled = True
            self._close_preview()

    @staticmethod
    def _section_label(row):
        label = f'{row["width_in"]:g} × {row["depth_in"]:g} in · {row["matches"]} cages'
        if row['estimated_cost'] is not None:
            gap = 'lowest cost' if row['lowest_cost'] else f'+{row["cost_premium_pct"]:.1f}%' if row['cost_premium_pct'] is not None else 'above zero baseline'
            label = f'#{row["cost_rank"]} · ' + label + f' · {row["estimated_cost"]:,.2f} ({gap})'
        return label + ' · ' + row['state']

    def _select_cheapest(self, _):
        if self.cheapest_button.disabled:
            return
        best = ranked_cost_rows(self.rows)[0]
        self.section.value = best['point_id']
        self.cage.value = best['candidate_id']

    def _map_clicked(self, trace, points, selector):
        if not points.xs or not points.ys:
            return
        for row in self.rows:
            if row['width_in'] == points.xs[0] and row['depth_in'] == points.ys[0]:
                self.section.value = row['point_id']
                break

    def _pareto_clicked(self, trace, points, selector):
        if points.point_inds:
            self.section.value = int(trace.customdata[points.point_inds[0]])

    def _section_changed(self, change):
        if not self.rendering:
            self._select_section()

    def _select_section(self, preserve_cage=None):
        if self.study is None or self.section.value is None or not self.rows:
            return
        row = self.rows[self.section.value]
        point = self.study.points[self.section.value]
        self.rendering = True
        try:
            self.cage.options = [(f'#{i+1} · {point.result.candidates[i].label} · {point.result.candidates[i].weight_lb:,.0f} lb · strength {point.result.candidates[i].strength_dc:.3f}', i) for i in row['candidate_ids']]
            self.cage.value = preserve_cage if preserve_cage in row['candidate_ids'] else row['candidate_ids'][0] if row['candidate_ids'] else None
        finally:
            self.rendering = False
        if self.figures:
            highlight_section(self.figures[0], self.study, self.rows, row['point_id'])
            if self.use_cost.value and len(self.figures) == 3:
                # Rebuild only this inexpensive chart to include a selected section outside the leading ten.
                cost_figure = go.FigureWidget(section_cost_chart(self.study, self.rows, row['point_id']))
                for trace in cost_figure.data:
                    trace.on_click(self._pareto_clicked)
                self.figures[1].close()
                self.figures[1] = cost_figure
                self.charts.children[1].children = [cost_figure]
        self._preview()

    def _cage_changed(self, change):
        if not self.rendering:
            self._preview()

    def _preview(self):
        self._close_preview()
        self.apply_button.disabled = True
        if self.study is None or self.section.value is None or not self.rows:
            return
        row = self.rows[self.section.value]
        point = self.study.points[self.section.value]
        if self.cage.value is None:
            rejected = '; '.join(f'{html.escape(k)}: {v}' for k, v in sorted(point.result.rejection_counts.items(), key=lambda pair: -pair[1])[:5]) if point.result else ''
            self.selection_info.value = f'<p><b>No selectable cage at this point.</b> {html.escape(point.reason)}<br>{rejected}</p>'
            return
        case = selected_section_case(self.study, self.section.value, self.cage.value)
        e = evaluate(case)
        candidate = point.result.candidates[self.cage.value]
        self.selection_info.value = f'<p><b>{study_label(self.study)}</b> · {point.width:g} × {point.depth:g} in · all {row["matches"]} matching cages are selectable.<br>'
        self.selection_info.value += f'Chosen cage: {candidate.weight_lb:,.0f} lb gross steel · {row["concrete_yd3"]:.3f} yd³ concrete · {row["form_ft2"]:.1f} ft² forms · strength D/C {candidate.strength_dc:.4f} · all-check utilization {candidate.max_dc:.4f}.<br>'
        rates = self._rates()
        if rates:
            parts = comparison_costs(row['concrete_yd3'], candidate.weight_lb, row['form_ft2'], rates)
            best = ranked_cost_rows(self.rows)[0]
            extra, percent = cost_gap(parts['estimated_cost'], best['estimated_cost'])
            comparison = 'Matches the lowest explored cost.' if extra == 0 else f'Adds {extra:,.2f}' + (f' ({percent:.1f}%)' if percent is not None else '') + ' versus the cheapest explored section/cage.'
            self.selection_info.value += f'<b>Chosen-cage cost: {parts["estimated_cost"]:,.2f} per cap.</b> {comparison}<br>'
            self.selection_info.value += f'Concrete {parts["concrete_cost"]:,.2f} + steel {parts["steel_cost"]:,.2f} + forms {parts["form_cost"]:,.2f}. '
            self.selection_info.value += 'The map and ranking use each section’s lightest matching cage; this summary uses your selected cage.<br>'
        source = case['analysis']
        self.selection_info.value += f'Source analysis: {html.escape(source["id"])} · source section {source["geometry"]["b"]:g} × {source["geometry"]["h"]:g} in.<br><b>{html.escape(e.status)}</b></p>'
        if self.study.grid['force_mode'] == 'matched':
            self.selection_info.value += '<small>Reusing forces over trial reinforcement assumes the analysis stiffness model permits it; geometry matching alone does not verify that assumption.</small>'
        for figure in (section_figure(e, 'B'), results_figure(e)):
            self.preview_figures.append(go.FigureWidget(figure))
        self.preview.children = [*self.preview_figures, W.HTML(spacing_html(e)),
                                 W.VBox([W.HTML(checks_html(e))], layout=W.Layout(max_height='420px', overflow='auto'))]
        self.apply_button.disabled = False

    def _apply(self, _):
        if self.apply_button.disabled:
            return
        case = selected_section_case(self.study, self.section.value, self.cage.value)
        self.applying = True
        try:
            self.app.load(case)
        finally:
            self.applying = False
        self.notice.value = 'Selected case loaded into the main calculator above. The original force-source geometry is retained. Changed fixed-force sections remain flagged for reanalysis.'

    def _refine(self, _):
        if self.refine_button.disabled or self.section.value is None:
            return
        point = self.study.points[self.section.value]
        self.rendering = True
        try:
            for name, value in [('width', point.width), ('depth', point.depth)]:
                lower, upper, step = self.bounds[name]
                start, stop, increment = lower.value, upper.value, step.value
                lower.value = max(start, value - increment)
                upper.value = min(stop, value + increment)
                step.value = increment / 2
        finally:
            self.rendering = False
        self.invalidate()
        self.notice.value = 'Ranges narrowed around the selected section and steps halved. Press Run section study to evaluate the finer grid; matching cached calculations will be reused.'

    def _export(self, _):
        if self.export_button.disabled:
            return
        try:
            selected = (self.section.value, self.cage.value) if self.cage.value is not None else None
            self.last_export = export_section_study(self.study, self.app.export_root, target=self.target.value, rates=self._rates(), selected=selected)
            self.notice.value = '<b>Saved section study:</b> ' + html.escape(str(self.last_export.resolve()))
        except Exception as exc:
            self.notice.value = '<b>Export stopped:</b> ' + html.escape(str(exc))

    def close(self):
        if self.invalidate in self.app.case_listeners:
            self.app.case_listeners.remove(self.invalidate)
        for control in [*self.app.search_lists.values(), self.app.limit]:
            control.unobserve(self._grid_changed, names='value')
        self.invalidate()
        self.ui.close()

    def display(self):
        from IPython.display import display
        display(self.ui)
        return self
