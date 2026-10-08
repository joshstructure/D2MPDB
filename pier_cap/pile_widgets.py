"""Pile results and minimum-tip review above the existing cap steel workbench."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import html
import json
import math
import zipfile
import ipywidgets as W
from traitlets import Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .plotly_compat import FigureWidget
from .pile_review import (import_pile_xml, elastic_profile, pile_heads, governors,
                          parse_trials, evaluate_trials, csv_text, require, validate_saved_review)
from .source_status import upload_entries, notice_html
from .widget_compat import Tab, Accordion
from .model import analysis_match
from .pile_reporting import (stress_limits, elastic_stress_checks, reported_cracking_check,
                             selected_trial_handoff, geotech_section_and_loads)


def table(rows, columns, scroll=True):
    def value(v):
        if v is None:
            return 'Unavailable'
        if isinstance(v, float):
            return f'{v:,.4g}'
        return html.escape(str(v))
    return ('<div'+(' style="overflow:auto;max-height:380px"' if scroll else '')+'><table style="border-collapse:collapse;width:100%">'
            '<tr>'+''.join('<th style="text-align:left;padding:7px;background:#eaf1f6">'+html.escape(label)+'</th>' for _, label in columns)+'</tr>'
            + ''.join('<tr>'+''.join('<td style="padding:6px;border-bottom:1px solid #dde3e8">'+value(r.get(key))+'</td>' for key, _ in columns)+'</tr>' for r in rows)+'</table></div>')


class PileSelector(W.VBox):
    """Ordinary checkbox widgets: select multiple piles without modifier keys."""
    value = Tuple()

    def __init__(self):
        self.checks = {}
        self.syncing = False
        super().__init__()
        self.observe(self._sync, names='value')

    def set_piles(self, piles):
        for control in self.checks.values():
            control.close()
        self.checks = {p: W.Checkbox(description='Pile '+p, indent=False,
                                   layout=W.Layout(width='110px')) for p in piles}
        for control in self.checks.values():
            control.observe(self._checked, names='value')
        self.children = [W.HBox(list(self.checks.values()), layout=W.Layout(flex_flow='row wrap'))]
        self.value = tuple(piles)
        self._sync()

    def _checked(self, _):
        if not self.syncing:
            self.value = tuple(p for p, w in self.checks.items() if w.value)

    def _sync(self, _=None):
        self.syncing = True
        try:
            for p, control in self.checks.items():
                control.value = p in self.value
        finally:
            self.syncing = False


def profile_limit_lines(fig, col, limits):
    """Keep limits visible even when every demand is much smaller."""
    axis = 'x' + (str(col) if col > 1 else '')
    values = [float(v) for t in fig.data if t.xaxis == axis for v in t.x if v is not None]
    for i, (value, label) in enumerate(limits):
        fig.add_vline(x=value, row=1, col=col, line_dash='dot', line_color='#ad3535',
                      exclude_empty_subplots=False)
        fig.add_annotation(x=value, y=.04 if i == 0 else .52, xref=axis, yref=f'y{col} domain',
                           text=f'{label} = {value:g}'+(' ksi' if col == 5 else ''), textangle=-90,
                           showarrow=False, xanchor='right', yanchor='bottom',
                           font=dict(color='#922626', size=10), bgcolor='rgba(255,255,255,.85)')
        values.append(value)
    if values:
        lo, hi = min(values), max(values)
        pad = max((hi-lo)*.08, .02)
        fig.update_xaxes(range=[lo-pad, hi+pad], row=1, col=col)


def profile_figure(review, combo, piles, cutoff=None, section=None):
    piles = [piles] if isinstance(piles, str) else list(piles)
    require(all(p in review['piles'] for p in piles), 'Unknown pile selection.')
    stress_rows = elastic_profile(review, section)
    fig = make_subplots(rows=1, cols=5, shared_yaxes=True, horizontal_spacing=.045,
                        subplot_titles=['Displacement', 'Moment magnitude', 'Axial', 'FBMP D/C', 'Elastic stress'])
    def add(data, key, name, color, col, pile, dash='solid', absolute=False):
        y = [r['distance_ft'] if cutoff is None else cutoff-r['vertical_ft'] for r in data]
        name = 'Pile '+pile+' · '+name
        fig.add_trace(go.Scatter(x=[abs(r[key]) if absolute and r[key] is not None else r[key] for r in data], y=y,
            name='Pile '+pile, legendgroup=pile, showlegend=col == 1 and dash == 'solid',
            mode='lines+markers', marker=dict(size=3), line=dict(color=color, width=2, dash=dash),
            customdata=[[r.get('element', ''), r.get('side', ''), r['node']] for r in data],
            hovertemplate=name+' = %{x:.4g}<br>Vertical position = %{y:.3f} ft<br>Element %{customdata[0]} %{customdata[1]} · node %{customdata[2]}<extra></extra>'), row=1, col=col)
    colors = ['#2769a6', '#d27b24', '#427e68', '#8c5bb0', '#c14456', '#00868b', '#766239', '#b14796']
    for pile in piles:
        color = colors[list(review['piles']).index(pile) % len(colors)]
        rows = [r for r in review['forces'] if r['combination'] == combo and r['pile'] == pile]
        disp = [r for r in review['displacements'] if r['combination'] == combo and r['pile'] == pile]
        stress = [r for r in stress_rows if r['combination'] == combo and r['pile'] == pile]
        add(disp, 'dx', 'DX', color, 1, pile)
        add(disp, 'dy', 'DY', color, 1, pile, 'dash')
        add(rows, 'm2', '|M2|', color, 2, pile, absolute=True)
        add(rows, 'm3', '|M3|', color, 2, pile, 'dash', absolute=True)
        add(rows, 'axial_tension_kip', 'Axial tension +', color, 3, pile)
        add(rows, 'model_dc', 'Model D/C', color, 4, pile)
        if stress:
            add(stress, 'stress_max_ksi', 'Maximum stress', color, 5, pile)
            add(stress, 'stress_min_ksi', 'Minimum stress', color, 5, pile, 'dash')
    profile_limit_lines(fig, 4, [(1, 'D/C limit')])
    if stress_rows:
        profile_limit_lines(fig, 5, stress_limits(section or review['section']))
    if not piles:
        fig.add_annotation(text='Select one or more piles above to draw the profiles.', x=.5, y=.5,
                           xref='paper', yref='paper', showarrow=False)
    elif not stress_rows:
        fig.add_annotation(text='Stress unavailable<br>See section explanation below', x=0, y=.5,
                           xref='x5 domain', yref='y5 domain', showarrow=False, font=dict(color='#a43e36'))
    fig.update_yaxes(autorange='reversed' if cutoff is None else True)
    fig.update_yaxes(title_text='Distance along pile (ft)' if cutoff is None else 'Project elevation (ft)', row=1, col=1)
    for col, unit in enumerate(['in', 'kip-ft', 'kip', 'ratio', 'ksi'], 1):
        fig.update_xaxes(title_text=unit, zeroline=True, zerolinecolor='#aab5c0', row=1, col=col)
    fig.update_layout(template='plotly_white', height=610, margin=dict(t=95, l=65, r=20, b=90),
        title=dict(text=f'{"Pile " if len(piles)==1 else "Piles "}{html.escape(", ".join(piles))} · combination {html.escape(combo)} · {html.escape(review["combinations"][combo])}', font=dict(size=17)),
        legend=dict(orientation='h', y=-.16, groupclick='togglegroup'), font=dict(family='Arial', size=11))
    return fig


def head_figure(review):
    heads = pile_heads(review)
    combos, piles = list(review['combinations']), list(review['piles'])
    lookup = {(r['combination'], r['pile']): r for r in heads}
    z = [[-lookup[c, p]['axial_tension_kip'] for p in piles] for c in combos]
    fig = go.Figure(go.Heatmap(z=z, x=['Pile '+p for p in piles],
        y=[c+' · '+review['combinations'][c] for c in combos], colorscale='RdBu', zmid=0,
        colorbar=dict(title='kip'), hovertemplate='%{y}<br>%{x}<br>Compression + / uplift − = %{z:.3f} kip<extra></extra>'))
    fig.update_layout(template='plotly_white', title='Pile-head axial forces · compression positive, uplift negative',
                      height=max(280, 150+35*len(combos)), margin=dict(l=160, r=35, t=60, b=45))
    return fig


def section_figure(section):
    s=section; w=s['width_in']; h=s['depth_in']
    fig=go.Figure()
    if s['shape']=='Circular':
        fig.add_shape(type='circle',x0=-w/2,x1=w/2,y0=-h/2,y1=h/2,line_color='#355b79',fillcolor='#dae4ed')
        if s['kind']=='steel' and s.get('shell_in',0)>0:
            t=s['shell_in']
            fig.add_shape(type='circle',x0=-w/2+t,x1=w/2-t,y0=-h/2+t,y1=h/2-t,line_color='#355b79',fillcolor='white')
    elif s['shape']=='Rectangular':
        fig.add_shape(type='rect',x0=-w/2,x1=w/2,y0=-h/2,y1=h/2,line_color='#355b79',fillcolor='#dae4ed')
    else:
        fig.add_annotation(x=0,y=0,text='Section outline unavailable for this shape',showarrow=False)
    points=[]
    for g in s.get('groups',[]):
        points.extend(g.get('points', [(g['c2'],g['c3'])] if g['bars']==1 else []))
    if points:
        fig.add_trace(go.Scatter(x=[p[0] for p in points],y=[p[1] for p in points],mode='markers',
            name='Reinforcement coordinates',marker=dict(size=8,color='#354253')))
    fig.update_xaxes(title_text='Local 2 (in)',range=[-w*.7,w*.7])
    fig.update_yaxes(title_text='Local 3 (in)',range=[-h*.7,h*.7],scaleanchor='x',scaleratio=1)
    fig.update_layout(template='plotly_white',height=350,title='Analyzed pile section · printed dimensions',
        margin=dict(l=60,r=30,t=60,b=55),showlegend=False)
    return fig


def trial_figure(result, tolerance):
    fig = make_subplots(rows=1, cols=3, subplot_titles=['Displacement', 'Change to shallower trial', 'Model D/C'])
    for group in result['groups']:
        data = sorted((r for r in result['rows'] if r['series'] == group['series']), key=lambda r: r['embedment_ft'])
        for col, key in [(1, 'displacement_in'), (2, 'delta_in'), (3, 'dc')]:
            fig.add_trace(go.Scatter(x=[r['embedment_ft'] for r in data], y=[r[key] for r in data],
                name=group['series'], legendgroup=group['series'], showlegend=col == 1, mode='lines+markers',
                customdata=[[r['trial'], r['combination'], r['pile'], str(r['converged'])] for r in data],
                hovertemplate='Embedment %{x:.3f} ft<br>Value %{y:.4g}<br>Trial %{customdata[0]} · combo %{customdata[1]} · pile %{customdata[2]}<br>Converged: %{customdata[3]}<extra></extra>'), row=1, col=col)
    for col, limit, label in [(2, tolerance, f'Δ limit = {tolerance:g} in'), (3, 1, 'D/C limit = 1')]:
        fig.add_hline(y=limit, row=1, col=col, line_dash='dot', line_color='#b74949',
                      annotation_text=label, annotation_position='top right', exclude_empty_subplots=False)
        values = [0, limit] + [v for t in fig.data if t.yaxis == f'y{col}' for v in t.y if v is not None]
        pad = max((max(values)-min(values))*.12, .01)
        fig.update_yaxes(range=[min(values)-pad, max(values)+pad], row=1, col=col)
    critical = result.get('critical_embedment_ft', result.get('accepted_embedment_ft'))
    if critical is not None:
        for col in (1, 2, 3):
            fig.add_vline(x=critical, row=1, col=col, line_dash='dash', line_color='#6a4197',
                          exclude_empty_subplots=False, **(dict(annotation_text=f'Lcrit = {critical:g} ft',
                          annotation_position='bottom right') if col == 1 else {}))
    for col in (1, 2, 3):
        fig.update_xaxes(title_text='Embedment (ft)', row=1, col=col)
    fig.update_yaxes(title_text='in', row=1, col=1)
    fig.update_yaxes(title_text='in', row=1, col=2)
    fig.update_yaxes(title_text='ratio', row=1, col=3)
    fig.update_layout(template='plotly_white', height=390, margin=dict(t=55, l=50, r=20, b=60))
    return fig


class PileReviewPanel:
    def __init__(self, app):
        self.app, self.review, self.figures = app, None, {}
        self.busy = False
        self.trial_result = None
        self.trial_error = ''
        self.notice, self.summary, self.source_match = W.HTML(), W.HTML(), W.HTML()
        self.head_output, self.profile_output, self.trial_output = W.VBox(), W.VBox(), W.VBox()
        self.section_output = W.VBox()
        self.reported, self.properties, self.handoff, self.trial_summary = W.HTML(), W.HTML(), W.HTML(), W.HTML()
        self.handoff_status = W.HTML()
        self.download_output, self.handoff_download_output = W.Output(), W.Output()
        self.handoff_refresh = W.Button(description='Update selected results', icon='refresh', disabled=True,
                                        layout=W.Layout(width='210px'))
        self.handoff_export = W.Button(description='Download geotech handoff', icon='download', disabled=True,
                                       layout=W.Layout(width='230px'))
        self.handoff_refresh.on_click(self._update_handoff)
        self.handoff_export.on_click(self._export_handoff)
        self.upload_output = W.Output(layout=W.Layout(display='none'))
        self.message = W.HTML()
        self.combo = W.Dropdown(description='Combination', layout=W.Layout(width='350px'))
        self.piles = PileSelector()
        self.all_piles = W.Button(description='All piles', layout=W.Layout(width='110px'))
        self.no_piles = W.Button(description='Clear', layout=W.Layout(width='90px'))
        self.governing_pile = W.Button(description='Highest model D/C', layout=W.Layout(width='180px'))
        self.all_piles.on_click(lambda _: setattr(self.piles, 'value', tuple(self.review['piles']) if self.review else ()))
        self.no_piles.on_click(lambda _: setattr(self.piles, 'value', ()))
        self.governing_pile.on_click(lambda _: setattr(self.piles, 'value', (self.selected_pile(),)) if self.review else None)
        self.cutoff = W.Text(description='Cutoff EL (ft)', placeholder='Optional project datum', continuous_update=False,
                             layout=W.Layout(width='320px'))
        self.export = W.Button(description='Download pile review', icon='download', disabled=True, layout=W.Layout(width='200px'))
        self.export.on_click(self._export)
        self.upload = self._uploader('Separate pile XML', '.xml,.XML', self._import)
        self.restore_upload = self._uploader('Load pile review', '.json', self._restore_file)
        self.combo.observe(self._selection_changed, names='value')
        self.piles.observe(self._selection_changed, names='value')
        self.cutoff.observe(self._selection_changed, names='value')
        self.use_override = W.Checkbox(value=False, description='Use confirmed manual elastic properties', indent=False)
        self.material = W.Dropdown(options=['steel', 'concrete'], description='Material')
        self.circular = W.Checkbox(value=True, description='Circular section (resultant bending)', indent=False)
        self.override = {k: W.FloatText(description=label, style={'description_width':'140px'}, layout=W.Layout(width='285px'))
                         for k, label in [('area_in2','Area (in²)'), ('s2_in3','S2 (in³)'), ('s3_in3','S3 (in³)'),
                                          ('fy_ksi','Steel Fy (ksi)'), ('prestress_kip','Concentric Pp (kip)')]}
        for control in [self.use_override, self.material, self.circular, *self.override.values()]:
            control.observe(self._selection_changed, names='value')
        manual = Accordion(children=[W.VBox([W.HTML('<p>Overrides change only the elastic screen. Enter properties about the model local axes. '
            'This screen assumes a homogeneous symmetric section and concentric prestress. Model forces, stresses and D/C stay tied to the original run.</p>'),
            self.use_override, self.material, self.circular, W.HBox(list(self.override.values()), layout=W.Layout(flex_flow='row wrap'))])])
        manual.set_title(0, 'Optional verified section properties'); manual.selected_index = None
        self.trial_text = W.Textarea(placeholder='trial,combination,pile,embedment_ft,displacement_in\n',
                                    layout=W.Layout(width='100%', height='150px'))
        self.trial_label = W.Text(description='Trial source', placeholder='Run/study identifier', layout=W.Layout(width='440px'))
        self.trial_upload = self._uploader('Load trial CSV', '.csv,.tsv,.txt', self._import_trials)
        self.tolerance = W.FloatText(value=.1, description='Δ limit (in)')
        self.extension = W.FloatText(value=5, description='Extension (ft)')
        self.fraction = W.FloatText(value=.2, description='Fraction')
        self.extension_mode = W.Dropdown(options=[('Fixed addition to Lcrit','fixed'),
                                                  ('Shaft/reference: lesser of fixed / percentage','lesser'),
                                                  ('Percentage of Lcrit','fraction')], value='fixed',
                                         description='Method', layout=W.Layout(width='410px'))
        self.reference = W.Text(description='Ground EL (ft)', placeholder='Required for tip elevation', continuous_update=False,
                                layout=W.Layout(width='330px'))
        self.accepted = W.Text(description='Lcrit (ft)', placeholder='Calculated from trials', disabled=True, layout=W.Layout(width='330px'))
        self.rounding = W.Checkbox(value=False, description='Round tip down / total length up to whole feet', indent=False)
        self.trial_basis = W.Text(description='Trial notes', placeholder='Optional project notes', layout=W.Layout(width='600px'))
        self.nominal_weight = W.Text(description='Weight (lb/ft)', placeholder='Nominal / supplied, optional', layout=W.Layout(width='330px'))
        self.nominal_diameter = W.Text(description='Nominal OD (in)', placeholder='Pipe geotechnical diameter', layout=W.Layout(width='330px'))
        self.toe = W.Dropdown(options=['Unknown','Open','Closed','Not applicable'],description='Pile toe')
        self.geotech_notes = W.Textarea(description='Project notes',placeholder='Scour, downdrag, driving / test criteria, resistance basis',layout=W.Layout(width='100%',height='90px'))
        for w in [self.nominal_weight,self.nominal_diameter,self.toe,self.geotech_notes]:
            w.observe(lambda _: self.refresh_handoff() if not self.busy else None,names='value')
        self.run_trials = W.Button(description='Calculate minimum tip', button_style='primary', icon='line-chart', disabled=True,
                                   layout=W.Layout(width='220px'))
        self.trial_status = W.HTML('<p>Paste trial rows above to enable Calculate minimum tip. The XML contains one solved pile length.</p>')
        self.run_trials.on_click(self._trials)
        for w in [self.trial_text, self.trial_label, self.tolerance, self.extension, self.fraction, self.extension_mode,
                  self.reference, self.rounding, self.trial_basis]:
            w.observe(self._trials_changed, names='value')
        self.trial_template = W.Button(description='Download CSV template', icon='download', layout=W.Layout(width='210px'))
        self.trial_template.on_click(self._template)
        trials = W.VBox([W.HTML('<p>Paste the five workbook columns (trial, combination, pile, embedment in ft, displacement in in), '
            'or upload the CSV template. A single solved XML does not contain the shortened-pile trial history. '
            'Each row is the governing result for that embedment. Use <b>series</b> for separate studies; combination and pile may change as governors change. '
            '<b>Lcrit is calculated automatically</b> from Δ ≤ 0.1 in (editable below). '
            '<b>Required embedment = Lcrit + 5 ft</b> by default; Lcrit itself remains unchanged. '
            '<b>Tip elevation = design ground/scour elevation − required embedment.</b> '
            'Enter Ground EL to calculate the elevation. Cutoff EL is only needed for total pile length. '
            'The 5-ft default follows January 2026 FDOT SDG 3.5.9.B.4 for driven piles; '
            'check any greater required penetration and Service-limit deflections separately.</p>'),
            W.HBox([self.trial_upload, self.trial_template]), self.trial_label, self.trial_text,
            W.HBox([self.tolerance, self.extension, self.fraction], layout=W.Layout(flex_flow='row wrap')),
            self.extension_mode, W.HBox([self.reference, self.accepted], layout=W.Layout(flex_flow='row wrap')),
            self.trial_basis, self.rounding, self.run_trials, self.trial_status, self.trial_summary, self.trial_output])
        self.tabs = Tab(children=[W.VBox([self.summary, self.head_output]),
            W.VBox([self.combo, W.HTML('<b>Compare piles</b> · check any combination of piles; colors stay the same on every plot.'),
                self.piles, W.HBox([self.all_piles, self.no_piles, self.governing_pile]),
                W.HTML('<p>Solid: DX / |M2| / maximum stress. Dashed: DY / |M3| / minimum stress. '
                       'Click a pile in the legend to hide or show its curves on every plot.</p>'), self.profile_output, self.reported]),
            W.VBox([self.section_output, self.properties, manual]), trials,
            W.VBox([W.HTML('<p>Share pile section information, minimum tip elevation and maximum factored loads in short tons. '
                'Paste trials and enter the design ground / scour elevation in Minimum tip, then update or download here. '
                'Critical embedment and minimum tip are calculated automatically.</p>'),
                W.HBox([self.nominal_weight,self.nominal_diameter,self.toe],layout=W.Layout(flex_flow='row wrap')),
                self.geotech_notes, W.HBox([self.handoff_refresh, self.handoff_export], layout=W.Layout(flex_flow='row wrap')),
                self.handoff_status, self.handoff_download_output, self.handoff])])
        for i, name in enumerate(['Pile loads', 'Profiles and stresses', 'Pile section', 'Minimum tip', 'Geotech handoff']):
            self.tabs.set_title(i, name)
        separate = Accordion(children=[W.VBox([W.HTML('<p>The shared XML upload above supplies both sections. '
            'Use this only to review a different pile analysis.</p>'), self.upload])])
        separate.set_title(0, 'Optional separate pile analysis'); separate.selected_index = None
        self.ui = W.VBox([W.HTML('<h2 style="color:#213649">1. FBMP pile review</h2><p>Review pile behavior and the minimum-tip study before selecting cap reinforcement.</p>'),
            W.HBox([self.restore_upload, self.export], layout=W.Layout(flex_flow='row wrap')), separate,
            self.upload_output, self.notice, self.source_match, self.cutoff, self.tabs, self.message, self.download_output])
        self.notice.value = notice_html('PILE RESULTS NOT LOADED', 'Upload FBMP XML once above to load pile results and preview cap inputs.')
        self.refresh_handoff()
        self.app.case_listeners.append(self.refresh_match)

    def _uploader(self, label, accept, callback):
        try:
            from google.colab import files
        except ImportError:
            control = W.FileUpload(accept=accept, multiple=False, description=label, layout=W.Layout(width='190px'))
            def changed(_):
                if not control.value:
                    return
                try:
                    entries = upload_entries(control.value)
                    require(len(entries) == 1, 'Choose one file.')
                    callback(bytes(entries[0]['content']), entries[0]['name'])
                except Exception as exc:
                    self.message.value = notice_html('FILE NOT LOADED', html.escape(str(exc))+' Previous review remains active.', 'error')
            control.observe(changed, names='value')
        else:
            control = W.Button(description=label, icon='upload', layout=W.Layout(width='190px'))
            def clicked(_):
                from IPython.display import clear_output
                control.disabled = True
                self.upload_output.layout.display = ''
                try:
                    with self.upload_output:
                        clear_output(wait=True)
                        with TemporaryDirectory(prefix='pile-review-') as folder:
                            entries = files.upload(target_dir=folder)
                        clear_output(wait=False)
                    if not entries:
                        return
                    require(len(entries) == 1, 'Choose one file.')
                    name, raw = next(iter(entries.items()))
                    callback(bytes(raw), Path(name).name)
                except Exception as exc:
                    self.message.value = notice_html('FILE NOT LOADED', html.escape(str(exc))+' Previous review remains active.', 'error')
                finally:
                    control.disabled = False
                    self.upload_output.layout.display = 'none'
            control.on_click(clicked)
        return control

    def _import(self, raw, name):
        self.set_review(import_pile_xml(raw, name))

    def set_review(self, review):
        self.review = deepcopy(review)
        self.busy = True
        try:
            self.use_override.value = False
            # Trial/datum records belong to a run; never carry them into a new run silently.
            self.trial_text.value = self.trial_label.value = self.accepted.value = self.reference.value = self.cutoff.value = self.trial_basis.value = ''
            self.nominal_weight.value = self.nominal_diameter.value = self.geotech_notes.value = ''
            self.toe.value = 'Unknown'
            self.trial_result = None; self.trial_summary.value = ''; self.trial_output.children = []
            self.run_trials.disabled = True
            self.trial_status.value = '<p>Paste trial rows above to enable Calculate minimum tip. The XML contains one solved pile length.</p>'
            self.combo.options = [(c+' · '+s, c) for c, s in review['combinations'].items()]
            self.combo.value = next((c for c, s in review['combinations'].items() if s == 'SERVICE-I'), next(iter(review['combinations'])))
            self.piles.set_piles(review['piles'])
            s = review['section']
            self.material.value = s['kind']; self.circular.value = s['circular']
            for k, w in self.override.items():
                w.value = s.get(k) or 0
        finally:
            self.busy = False
        self.export.disabled = False
        self.handoff_refresh.disabled = self.handoff_export.disabled = False
        self.handoff_status.value = ''
        self.notice.value = notice_html('PILE RESULTS LOADED',
            '<b>'+html.escape(review['filename'])+'</b> · '+str(len(review['piles']))+' piles · '+str(len(review['combinations']))+
            ' combinations · '+str(len(review['forces']))+' element ends. SHA256 '+review['sha256'][:12])
        rows = []
        for g in governors(review):
            labels = [f'comb {r["combination"]}, pile {r["pile"]}, node {r["node"]}' for r in g['records']]
            rows.append(dict(state=g['state'], metric=g['metric'], value=g['value'], governing='; '.join(labels[:4])+(' (additional ties in export)' if len(labels)>4 else '')))
        self.summary.value = table(rows, [('state','Limit state'), ('metric','Result'), ('value','Maximum'), ('governing','Governing record')])
        self._figure('heads', self.head_output, head_figure(review))
        self._figure('section', self.section_output, section_figure(s))
        labels={'kind':'Material','shape':'Shape','width_in':'Width / OD (in)','depth_in':'Depth (in)',
            'shell_in':'Shell thickness (in)','area_in2':'Area (in²)','i2_in4':'I2 (in⁴)','i3_in4':'I3 (in⁴)',
            's2_in3':'S2 (in³)','s3_in3':'S3 (in³)','modulus_ksi':'Elastic modulus (ksi)','fy_ksi':'Steel Fy (ksi)',
            'fc_ksi':'Concrete strength (ksi)','prestress_kip':'Prestress force (kip)','circular':'Circular bending model',
            'tensile_peak_ksi':'Model concrete tensile peak (ksi)','tensile_peak_strain':'Model cracking-peak strain (in/in)',
            'modeled_weight_lb_ft':'Modeled weight (lb/ft)','source':'Property source'}
        self.properties.value = table([dict(property=labels[k], value=v) for k, v in s.items() if k in labels], [('property','Property'), ('value','Model value')])
        self.properties.value += '<p>'+html.escape('; '.join(s['issues']) or 'Elastic section properties are available.')+'</p><p>Stress uses exported A and I; printed dimensions may be rounded. Individual bars and supported rectangular bar groups are drawn from the XML.</p>'
        self.message.value = ''
        self.refresh_match(); self.refresh_profiles(); self.refresh_handoff()

    def refresh_match(self):
        if self.review is None:
            return
        audit = self.app.case['analysis'].get('xml_audit', {})
        edited_forces=any(not math.isclose(self.app.case['inputs'][key],record['adopted'],abs_tol=1e-8)
            for key,record in audit.get('governing',{}).items() if key in self.app.case['inputs'] and 'adopted' in record)
        if audit.get('sha256') != self.review['sha256']:
            text = 'Pile review and cap forces use different source records. Pile results remain an independent review.'
        elif analysis_match(self.app.case) or self.app.case.get('section_study', {}).get('force_mode') == 'fixed':
            text = 'Pile and cap sources share the XML, but the current cap geometry differs or uses fixed-force sensitivity. Pile results describe the original analysis.'
        elif edited_forces:
            text = 'Pile and cap sources share the XML, but cap force inputs have been edited. Pile results describe the original analysis.'
        else:
            text = 'Pile review and cap inputs share the same analyzed XML.'
        self.source_match.value = '<p><b>'+html.escape(text)+'</b></p>'

    def _figure(self, key, container, figure):
        if key in self.figures:
            self.figures[key].close()
        widget = FigureWidget(figure)
        self.figures[key] = widget
        container.children = [widget]

    def section(self):
        s = deepcopy(self.review['section'])
        if self.use_override.value:
            s.update({k:w.value for k,w in self.override.items()})
            s.update(kind=self.material.value, circular=self.circular.value, issues=[], source='Confirmed manual elastic properties')
            if s['kind'] == 'steel':
                require(s['fy_ksi'] > 0 and math.isfinite(s['fy_ksi']), 'Enter a positive steel Fy.')
        return s

    @staticmethod
    def optional(control):
        if not control.value.strip():
            return None
        value = float(control.value)
        require(math.isfinite(value), 'Elevation / embedment must be finite.')
        return value

    def _selection_changed(self, _=None):
        if self.busy:
            return
        self.refresh_profiles()
        if _ is not None and _.get('owner') is self.cutoff:
            self._trials_changed(_)
        self.refresh_handoff()

    def selected_pile(self):
        """Governing pile for the shortcut and migration of older saved reviews."""
        rows = [r for r in self.review['forces'] if r['combination'] == self.combo.value and r['model_dc'] is not None]
        return max(rows, key=lambda r:r['model_dc'])['pile'] if rows else next(iter(self.review['piles']))

    def refresh_profiles(self):
        if self.review is None:
            return
        try:
            s = self.section()
            self._figure('profiles', self.profile_output, profile_figure(self.review, self.combo.value, self.piles.value, self.optional(self.cutoff), s))
            rows = [r for r in self.review['reported_stresses'] if r['combination'] == self.combo.value]
            concrete = s['kind'] == 'concrete'
            self.reported.value = '<h4>'+('Cracking screen' if concrete else 'Elastic yield screen')+' · selected piles</h4>'
            self.reported.value += table(elastic_stress_checks(self.review, self.combo.value, self.piles.value, s),
                [('pile','Pile'), ('stress_min_ksi','Min stress (ksi)'), ('stress_max_ksi','Max stress (ksi)'),
                 ('limit_ksi','Model tensile peak (ksi)' if concrete else 'Fy (ksi)'), ('ratio','Tension / peak' if concrete else '|Stress| / Fy'),
                 ('result','Comparison'), ('node','Governing node')])
            if self.review['section']['kind'] == 'concrete':
                self.reported.value += '<h4>FBMP concrete cracking-strain check · all piles in selected combination</h4>'
                self.reported.value += table(reported_cracking_check(self.review, self.combo.value),
                    [('pile','Governing pile'), ('segment','Segment'), ('strain','Max strain (in/in)'),
                     ('peak_strain','Model peak strain (in/in)'), ('stress_ksi','Corresponding stress (ksi)'), ('result','Comparison')])
                self.reported.value += ('<p>The red model cracking line comes from the XML concrete tensile curve. '
                    'Zero marks decompression. The elastic screen uses gross section properties; the FBMP strain comparison uses the original nonlinear run, '
                    'including any tension softening. Neither comparison establishes prior cracking history. '
                    '<b>Code service stress allowables are not supplied by this XML and are not evaluated here.</b></p>')
            self.reported.value += '<h4>FBMP reported material stress extrema · all piles in selected combination</h4>'+table(rows,
                [('description','Material / extreme'), ('stress_ksi','Stress (ksi)'), ('pile','Pile'), ('segment','Segment')])
            prof = [r for r in elastic_profile(self.review, s) if r['combination'] == self.combo.value and r['pile'] in self.piles.value]
            if prof:
                high, low = max(r['stress_max_ksi'] for r in prof), min(r['stress_min_ksi'] for r in prof)
                self.reported.value += f'<p>Selected piles elastic range: <b>{low:.4g} to {high:.4g} ksi</b>. Tension positive. '
                if s['kind'] == 'steel':
                    ratios = [r['elastic_yield_ratio'] for r in prof if r['elastic_yield_ratio'] is not None]
                    self.reported.value += f'Peak elastic stress/Fy: <b>{max(ratios):.4g}</b>.' if ratios else 'Steel Fy is unavailable.'
                else:
                    self.reported.value += 'Gross-section elastic screen with concentric prestress. '
                    self.reported.value += f'Model concrete tensile peak: {s["tensile_peak_ksi"]:.4g} ksi.' if s.get('tensile_peak_ksi') else 'Model tensile peak unavailable.'
                self.reported.value += '</p>'
            elif self.piles.value:
                self.reported.value += '<p>Elastic stress profile unavailable: '+html.escape('; '.join(s.get('issues', [])))+'</p>'
            self.reported.value += ('<p>Both element ends are retained. Moment plots show magnitudes; original signed values are in the export. '
                'Elastic stress/Fy is not an LRFD pile resistance check. XML does not report OUT cracking warnings or convergence status.</p>')
        except Exception as exc:
            self.profile_output.children = []
            self.reported.value = notice_html('PROFILE INPUT NEEDS REVIEW', html.escape(str(exc)), 'error')

    def _import_trials(self, raw, name):
        text = raw.decode('utf-8-sig')
        parse_trials(text)
        self.trial_text.value = text
        self.trial_label.value = name
        self._trials()

    def _trials_changed(self, _=None):
        if self.busy:
            return
        self.trial_result = None
        self.trial_error = ''
        self.accepted.value = ''
        self.handoff_status.value = ''
        self.trial_output.children = []
        old_figure = self.figures.pop('trials', None)
        if old_figure is not None:
            old_figure.close()
        self.trial_summary.value = ''
        self.run_trials.disabled = not bool(self.trial_text.value.strip())
        # Recalculate datum/allowance changes immediately. Editing the actual
        # trial table still requires Calculate so partial pastes are not used.
        if self.trial_text.value.strip() and _ is not None and _.get('owner') is not self.trial_text:
            self._trials()
            return
        self.trial_status.value = ('<p>Trial inputs changed. Click Calculate minimum tip to update the plots and results.</p>'
            if self.trial_text.value.strip() else '<p>Paste trial rows above to enable Calculate minimum tip. The XML contains one solved pile length.</p>')
        self.refresh_handoff()

    def _trials(self, _=None):
        self.trial_result = None
        self.accepted.value = ''
        self.trial_error = ''
        self.trial_output.children = []
        self.trial_summary.value = ''
        self.run_trials.disabled = True
        self.trial_status.value = notice_html('EVALUATING TRIALS', 'Reading the pasted table…', 'pending')
        try:
            rows = parse_trials(self.trial_text.value)
            result = evaluate_trials(rows, self.tolerance.value, self.extension.value, self.fraction.value,
                self.extension_mode.value, self.optional(self.reference), self.optional(self.cutoff), round_feet=self.rounding.value)
            self.trial_result = result
            p = result['critical_embedment_ft']
            self.accepted.value = f'{p:.3f}' if p is not None else ''
            self.trial_summary.value = '<p><b>Calculated critical embedment, Lcrit: '+(f'{p:.3f} ft' if p is not None else 'Unavailable')+'</b>.</p>'
            self.trial_summary.value += '<p>'+html.escape(result['basis'])+'</p>'
            labels = [('critical_embedment_ft','Critical embedment, Lcrit'), ('extension_ft','Added embedment'),
                      ('required_embedment_ft','Required embedment'), ('tip_elevation_ft','Minimum tip elevation'),
                      ('total_length_ft','Total pile length')]
            self.trial_summary.value += table([dict(item=label, value=result[k]) for k, label in labels], [('item','Result'), ('value','ft')])
            if p is None:
                self.trial_summary.value += '<p>No qualifying adjacent trial pair in one or more series. Add or check trial results; no minimum tip is calculated.</p>'
            else:
                self.trial_summary.value += (f'<p><b>Required embedment = {p:.3f} + '
                    f'{result["extension_ft"]:.3f} = {result["required_embedment_ft"]:.3f} ft.</b> '
                    'The added embedment is included here, not in Lcrit.</p>')
                ground = self.optional(self.reference)
                if ground is None:
                    self.trial_summary.value += '<p><b>Enter Ground EL (ft)</b> — design ground / scour elevation is required for minimum tip elevation. The added and required embedments above are already calculated.</p>'
                else:
                    raw_tip = ground-result['required_embedment_ft']
                    self.trial_summary.value += (f'<p><b>Tip elevation = {ground:.3f} − '
                        f'{result["required_embedment_ft"]:.3f} = {raw_tip:.3f} ft.</b></p>')
                    if self.rounding.value:
                        self.trial_summary.value += f'<p>Adopted whole-foot tip elevation: {result["tip_elevation_ft"]:.0f} ft (rounded downward).</p>'
                if self.extension_mode.value == 'lesser':
                    self.trial_summary.value += '<p>Lesser-of method selected (shaft/reference procedure). Choose Fixed addition to Lcrit with Extension = 5 ft for the current driven-pile default.</p>'
            if any(r['converged'] is None for r in rows):
                self.trial_summary.value += '<p>Some trial convergence results are not supplied.</p>'
            if any(r['dc'] is None for r in rows):
                self.trial_summary.value += '<p>Some trial D/C results are not supplied.</p>'
            intervals = {round(r['interval_ft'], 5) for r in result['rows'] if r['interval_ft'] is not None}
            if len(intervals)>1:
                self.trial_summary.value += '<p>Trial spacing varies. The Δ criterion depends on that spacing; inspect the plotted intervals.</p>'
            self.trial_summary.value += table(result['rows'], [('series','Series'), ('trial','Trial'), ('combination','Combo'), ('pile','Pile'),
                ('embedment_ft','Embedment (ft)'), ('next_embedment_ft','Next shallower (ft)'), ('delta_in','Δ (in)'),
                ('passes','Δ ≤ limit'), ('critical_trial','Governing Lcrit'), ('dc','D/C'), ('converged','Converged')])
            if any(not r['analysis_ok'] for r in result['rows'] if r['critical_trial']):
                self.trial_summary.value += '<p>The governing trial pair has a supplied D/C or convergence failure. Lcrit follows the displacement-change formula; these checks are reported separately.</p>'
            self._figure('trials', self.trial_output, trial_figure(result, self.tolerance.value))
            if p is None:
                missing = ', '.join(g['series'] for g in result['groups'] if g['candidate_ft'] is None)
                self.trial_status.value = notice_html('NO QUALIFYING TRIAL PAIR',
                    'Check trial results in: '+html.escape(missing)+'. No critical embedment or tip elevation can be calculated.', 'pending')
            elif self.optional(self.reference) is None:
                self.trial_status.value = notice_html('TRIALS EVALUATED — GROUND ELEVATION NEEDED',
                    'Lcrit and added embedment are calculated. Enter Ground EL (ft) to finish the minimum tip elevation.', 'pending')
            else:
                self.trial_status.value = notice_html('MINIMUM TIP CALCULATED',
                    f'{len(rows)} rows · {len(result["groups"])} series. Tip elevation = {result["tip_elevation_ft"]:.3f} ft.', 'success')
        except Exception as exc:
            self.trial_result = None
            self.trial_error = str(exc)
            self.trial_summary.value = ''
            self.trial_status.value = notice_html('TRIALS NEED REVIEW', html.escape(str(exc)), 'error')
        finally:
            self.run_trials.disabled = not bool(self.trial_text.value.strip())
        self.refresh_handoff()

    def handoff_data(self, require_selected=False):
        require(self.review is not None, 'Load pile results first.')
        section, loads = geotech_section_and_loads(self.review, self.optional(self.nominal_weight),
                                                   self.optional(self.nominal_diameter), self.toe.value)
        selected = None
        if self.trial_result and self.trial_result['accepted_embedment_ft'] is not None:
            selected = selected_trial_handoff(self.review, self.trial_result, source=self.trial_label.value,
                ground=self.optional(self.reference), cutoff=self.optional(self.cutoff),
                basis=self.trial_basis.value, notes=self.geotech_notes.value)
        if require_selected:
            require(selected is not None, 'No critical embedment meets the displacement-change limit. Check the trials in Minimum tip.')
            require(self.trial_result['tip_elevation_ft'] is not None,
                    'Enter the design ground / scour elevation in Minimum tip to calculate minimum tip elevation.')
            require(all(r['short_tons'] is not None for r in loads), 'No strength / extreme-event pile-head loads are available.')
        return dict(section=section, loads=loads, selected=selected)

    def handoff_html(self, data):
        result = self.trial_result
        tip = result['tip_elevation_ft'] if data['selected'] else None
        tip_text = f'{tip:.3f} ft' if tip is not None else 'Not calculated — enter trial results and ground / scour elevation in Minimum tip.'
        markup = '<h3>Geotechnical handoff</h3>'+table(data['section'], [('item','Pile information'), ('value','Value')], scroll=False)
        markup += '<p><b>Minimum tip elevation: '+html.escape(tip_text)+'</b></p>'
        if tip is not None:
            markup += f'<p>Design ground / scour elevation: {self.optional(self.reference):.3f} ft. '
            if result['total_length_ft'] is not None:
                markup += f'Selected total length: {result["total_length_ft"]:.3f} ft; cutoff elevation: {self.optional(self.cutoff):.3f} ft. '
            markup += '</p>'
        markup += table(data['loads'], [('load','Pile-head design load'), ('short_tons','Short tons'), ('governing','Governing record')], scroll=False)
        markup += '<p>1 short ton = 2 kip. Envelopes use strength and extreme-event combinations from the loaded XML; service and fatigue combinations are excluded.</p>'
        if self.geotech_notes.value.strip():
            markup += '<p><b>Project notes:</b> '+html.escape(self.geotech_notes.value).replace('\n','<br>')+'</p>'
        markup += '<p>Section / loads: '+html.escape(self.review['filename'])+'.</p>'
        if data['selected']:
            markup += '<p>Tip calculation: '+html.escape(self.trial_label.value.strip() or 'Pasted trials — source not named')+'. '
            markup += html.escape(result['basis'])
            if self.trial_basis.value.strip():
                markup += ' '+html.escape(self.trial_basis.value)
            markup += '</p>'
        return markup

    def refresh_handoff(self):
        if self.review is None:
            self.handoff.value = '<p>Load pile results to prepare the handoff.</p>'
            return
        try:
            self.handoff.value = self.handoff_html(self.handoff_data())
        except ValueError as exc:
            self.handoff.value = notice_html('HANDOFF INPUT NEEDS REVIEW', html.escape(str(exc)), 'error')

    def _update_handoff(self, _=None):
        self._trials()
        try:
            require(self.trial_result is not None, self.trial_error or 'Fix the trial inputs in Minimum tip.')
            self.handoff_data(require_selected=True)
            self.handoff_status.value = notice_html('HANDOFF READY', 'Section, minimum tip and factored loads are updated below.', 'success')
        except ValueError as exc:
            self.handoff_status.value = notice_html('HANDOFF NEEDS INPUT', html.escape(str(exc)), 'error')

    def save_handoff(self, folder):
        self._trials()
        require(self.trial_result is not None, self.trial_error or 'Fix the trial inputs in Minimum tip before downloading the handoff.')
        data = self.handoff_data(require_selected=True)
        folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
        self._write_handoff(folder, data)
        return folder

    def _write_handoff(self, folder, data):
        (folder/'geotech_handoff.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>Geotechnical handoff</title>'
            '<style>body{font:14px Arial;max-width:1000px;margin:30px auto;color:#203040}td,th{vertical-align:top}p{line-height:1.4}'
            '@media print{body{margin:0;font-size:11pt}tr{break-inside:avoid}}</style></head><body>'
            +self.handoff_html(data)+'</body></html>', encoding='utf-8')
        (folder/'factored_pile_loads_tons.csv').write_text(csv_text(data['loads']), encoding='utf-8-sig')
        (folder/'pile_section.csv').write_text(csv_text(data['section']), encoding='utf-8-sig')
        if data['selected']:
            for name, rows in [('selected_trial_results.csv', data['selected']['trials']), ('minimum_tip_selection.csv', data['selected']['selection'])]:
                (folder/name).write_text(csv_text(rows), encoding='utf-8-sig')

    def _export_handoff(self, _=None):
        self.handoff_export.disabled = True
        self.handoff_status.value = notice_html('PREPARING HANDOFF', 'Updating selected results…', 'pending')
        try:
            folder = self.app.export_root/datetime.now(timezone.utc).strftime('geotech-handoff-%Y%m%d-%H%M%S-%f')
            self.save_handoff(folder)
            path = folder.with_suffix('.zip')
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                for file in folder.iterdir():
                    z.write(file, file.name)
            self._download(path, self.handoff_status, self.handoff_download_output)
        except Exception as exc:
            self.handoff_status.value = notice_html('HANDOFF NOT DOWNLOADED', html.escape(str(exc)), 'error')
        finally:
            self.handoff_export.disabled = self.review is None

    def snapshot(self):
        controls = ['combo','piles','cutoff','use_override','material','circular','trial_text','trial_label','tolerance','extension','fraction',
                    'extension_mode','reference','rounding','trial_basis','nominal_weight','nominal_diameter','toe','geotech_notes']
        return dict(schema_version=3, review=deepcopy(self.review), controls={k:getattr(self,k).value for k in controls},
                    override={k:w.value for k,w in self.override.items()})

    def restore(self, state):
        require(state.get('schema_version') in (1, 2, 3) and isinstance(state.get('review'), dict), 'Unsupported pile review file.')
        state = deepcopy(state)
        # Old manually entered depths are outputs under the automatic workflow.
        # Recompute them from saved trials instead of adopting a stale value.
        if state['schema_version'] in (1, 2):
            state.get('controls', {}).pop('accepted', None)
        old_pile = state.get('controls', {}).pop('pile', None)
        if old_pile is not None:
            require(old_pile == 'auto' or old_pile in state['review']['piles'], 'Unknown selected pile.')
            state['controls']['piles'] = list(state['review']['piles']) if old_pile == 'auto' else [old_pile]
        validate_saved_review(state['review'])
        allowed=self.snapshot()['controls']
        for k,value in state.get('controls',{}).items():
            require(k in allowed, 'Unknown pile review control.')
            expected=type(allowed[k])
            if k == 'combo':
                require(value in state['review']['combinations'], 'Unknown selected combination.')
            elif k == 'piles':
                require(isinstance(value, (list, tuple)) and all(isinstance(p, str) and p in state['review']['piles'] for p in value)
                        and len(set(value)) == len(value), 'Unknown or duplicate selected piles.')
            elif expected in (float,int):
                require(type(value) in (float,int) and math.isfinite(value), f'Invalid {k}.')
            else:
                require(isinstance(value,expected),f'Invalid {k}.')
        for k,value in state.get('override',{}).items():
            require(k in self.override and type(value) in (float,int) and math.isfinite(value), 'Invalid property override.')
        self.set_review(state['review'])
        self.busy = True
        try:
            for k, value in state.get('controls', {}).items():
                require(k in self.snapshot()['controls'], 'Unknown pile review control.')
                getattr(self, k).value = tuple(value) if k == 'piles' else value
            for k, value in state.get('override', {}).items():
                self.override[k].value = value
        finally:
            self.busy = False
        self.refresh_profiles()
        if self.trial_text.value.strip():
            self._trials()
        self.refresh_handoff()

    def _restore_file(self, raw, name):
        require(len(raw)<=25_000_000, 'Review file exceeds 25 MB.')
        state = json.loads(raw.decode('utf-8-sig'))
        self.restore(state)

    def save_bundle(self, folder):
        require(self.review is not None, 'Load pile results first.')
        # Re-evaluate before export, so edited/invalid trial inputs cannot export a stale tip.
        if self.trial_text.value.strip():
            self._trials()
            require(self.trial_result is not None, 'Fix the trial inputs before exporting.')
        s = self.section()
        self.refresh_match()
        self.refresh_profiles()
        self.refresh_handoff()
        folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
        (folder/'pile_review.json').write_text(json.dumps(self.snapshot(), indent=2, allow_nan=False), encoding='utf-8')
        datasets = {'pile_heads.csv':pile_heads(self.review), 'pile_forces.csv':self.review['forces'],
                    'pile_displacements.csv':self.review['displacements'], 'pile_governors.csv':governors(self.review),
                    'reported_stresses.csv':self.review['reported_stresses'], 'reported_pile_summary.csv':self.review['reported_summary'],
                    'elastic_stresses.csv':elastic_profile(self.review, s),
                    'elastic_stress_checks.csv':elastic_stress_checks(self.review, self.combo.value, self.piles.value, s),
                    'model_cracking_check.csv':reported_cracking_check(self.review, self.combo.value)}
        if self.trial_result:
            datasets['minimum_tip_trials.csv'] = self.trial_result['rows']
            (folder/'minimum_tip_result.json').write_text(json.dumps(self.trial_result, indent=2, allow_nan=False), encoding='utf-8')
        for name, rows in datasets.items():
            (folder/name).write_text(csv_text(rows), encoding='utf-8-sig')
        self._write_handoff(folder, self.handoff_data())
        parts = [head_figure(self.review).to_html(full_html=False, include_plotlyjs=True),
                 section_figure(self.review['section']).to_html(full_html=False, include_plotlyjs=False),
                 profile_figure(self.review, self.combo.value, self.piles.value, self.optional(self.cutoff), s).to_html(full_html=False, include_plotlyjs=False)]
        if self.trial_result:
            parts.append(trial_figure(self.trial_result, self.tolerance.value).to_html(full_html=False, include_plotlyjs=False))
        (folder/'pile_review.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>Pile review</title></head><body style="font-family:Arial">'
            + '<h1>FBMP pile review</h1><p>'+html.escape(self.review['filename'])+' · '+self.review['sha256']+'</p>'
            + self.source_match.value + self.summary.value + self.properties.value + ''.join(parts) + self.reported.value
            + self.trial_summary.value + self.handoff.value + '<p>'+'<br>'.join(html.escape(n) for n in self.review['notes'])+'</p></body></html>', encoding='utf-8')
        return folder

    def _download(self, path, status=None, output=None):
        status = self.message if status is None else status
        output = self.download_output if output is None else output
        from IPython.display import clear_output, display, FileLink
        try:
            from google.colab import files
        except ImportError:
            with output:
                clear_output(wait=True)
                display(FileLink(str(path)))
            status.value = '<p>Saved: '+html.escape(str(path.resolve()))+'</p>'
        else:
            # Colab download JavaScript must be captured in a visible Output
            # widget when invoked by a widget callback.
            with output:
                clear_output(wait=True)
                files.download(str(path))
            status.value = '<p>Download prepared: '+html.escape(path.name)+'</p>'

    def _export(self, _=None):
        try:
            folder = self.app.export_root/datetime.now(timezone.utc).strftime('pile-review-%Y%m%d-%H%M%S-%f')
            self.save_bundle(folder)
            path = folder.with_suffix('.zip')
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                for file in folder.iterdir():
                    z.write(file, file.name)
            self._download(path)
        except Exception as exc:
            self.message.value = notice_html('PILE EXPORT STOPPED', html.escape(str(exc)), 'error')

    def _template(self, _=None):
        self.app.export_root.mkdir(parents=True, exist_ok=True)
        path = self.app.export_root/'minimum_tip_template.csv'
        path.write_text('trial,combination,pile,embedment_ft,displacement_in,series,dc,dx_in,dy_in,converged,iterations,tolerance_kip\n', encoding='utf-8')
        self._download(path)

    def close(self):
        for fig in self.figures.values():
            fig.close()
        self.ui.close()
