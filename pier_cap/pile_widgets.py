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
from .pile_review import (import_pile_xml, elastic_profile, pile_heads, governors,
                          parse_trials, evaluate_trials, csv_text, require, validate_saved_review)
from .source_status import upload_entries, notice_html
from .widget_compat import Tab, Accordion
from .model import analysis_match


def table(rows, columns):
    def value(v):
        if v is None:
            return 'Unavailable'
        if isinstance(v, float):
            return f'{v:,.4g}'
        return html.escape(str(v))
    return ('<div style="overflow:auto;max-height:380px"><table style="border-collapse:collapse;width:100%">'
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
    fig.add_vline(x=1, line_dash='dash', line_color='#ba4343', row=1, col=4)
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
    fig.add_hline(y=tolerance, row=1, col=2, line_dash='dash', line_color='#b74949')
    fig.add_hline(y=1, row=1, col=3, line_dash='dash', line_color='#b74949')
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
        self.notice, self.summary, self.source_match = W.HTML(), W.HTML(), W.HTML()
        self.head_output, self.profile_output, self.trial_output = W.VBox(), W.VBox(), W.VBox()
        self.section_output = W.VBox()
        self.reported, self.properties, self.handoff, self.trial_summary = W.HTML(), W.HTML(), W.HTML(), W.HTML()
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
        self.cutoff = W.Text(description='Cutoff EL (ft)', placeholder='Optional project datum', layout=W.Layout(width='320px'))
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
        self.extension_mode = W.Dropdown(options=[('Fixed extension','fixed'), ('Lesser of extension / fraction','lesser')],
                                         description='Method', layout=W.Layout(width='360px'))
        self.reference = W.Text(description='Ground EL (ft)', placeholder='Design ground/scour datum', layout=W.Layout(width='330px'))
        self.accepted = W.Text(description='Critical (ft)', placeholder='Selected critical embedment', layout=W.Layout(width='330px'))
        self.rounding = W.Checkbox(value=False, description='Round tip down / total length up to whole feet', indent=False)
        self.trial_basis = W.Text(description='Basis', placeholder='Project criteria / engineering selection', layout=W.Layout(width='600px'))
        self.nominal_weight = W.Text(description='Weight (lb/ft)', placeholder='Nominal / supplied, optional', layout=W.Layout(width='330px'))
        self.nominal_diameter = W.Text(description='Nominal OD (in)', placeholder='Pipe geotechnical diameter', layout=W.Layout(width='330px'))
        self.toe = W.Dropdown(options=['Unknown','Open','Closed','Not applicable'],description='Pile toe')
        self.geotech_notes = W.Textarea(description='Project notes',placeholder='Scour, downdrag, driving / test criteria, resistance basis',layout=W.Layout(width='100%',height='90px'))
        for w in [self.nominal_weight,self.nominal_diameter,self.toe,self.geotech_notes]:
            w.observe(lambda _: self.refresh_handoff() if not self.busy else None,names='value')
        self.run_trials = W.Button(description='Evaluate trials', button_style='primary', icon='line-chart', disabled=True)
        self.trial_status = W.HTML('<p>Paste trial rows above to enable Evaluate trials. The XML contains one solved pile length.</p>')
        self.run_trials.on_click(self._trials)
        for w in [self.trial_text, self.trial_label, self.tolerance, self.extension, self.fraction, self.extension_mode,
                  self.reference, self.accepted, self.rounding, self.trial_basis]:
            w.observe(self._trials_changed, names='value')
        self.trial_template = W.Button(description='Download CSV template', icon='download', layout=W.Layout(width='210px'))
        self.trial_template.on_click(self._template)
        trials = W.VBox([W.HTML('<p>Paste the five workbook columns (trial, combination, pile, embedment in ft, displacement in in), '
            'or upload the CSV template. A single solved XML does not contain the shortened-pile trial history. '
            'Each row is the governing result for that embedment. Use <b>series</b> for separate studies; combination and pile may change as governors change.</p>'),
            W.HBox([self.trial_upload, self.trial_template]), self.trial_label, self.trial_text,
            W.HBox([self.tolerance, self.extension, self.fraction], layout=W.Layout(flex_flow='row wrap')),
            self.extension_mode, W.HBox([self.reference, self.accepted], layout=W.Layout(flex_flow='row wrap')),
            self.trial_basis, self.rounding, self.run_trials, self.trial_status, self.trial_output, self.trial_summary])
        self.tabs = Tab(children=[W.VBox([self.summary, self.head_output]),
            W.VBox([self.combo, W.HTML('<b>Compare piles</b> · check any combination of piles; colors stay the same on every plot.'),
                self.piles, W.HBox([self.all_piles, self.no_piles, self.governing_pile]),
                W.HTML('<p>Solid: DX / |M2| / maximum stress. Dashed: DY / |M3| / minimum stress. '
                       'Click a pile in the legend to hide or show its curves on every plot.</p>'), self.profile_output, self.reported]),
            W.VBox([self.section_output, self.properties, manual]), trials,
            W.VBox([W.HTML('<p>Optional project information for the geotechnical handoff. These entries do not change analyzed stiffness or forces.</p>'),
                W.HBox([self.nominal_weight,self.nominal_diameter,self.toe],layout=W.Layout(flex_flow='row wrap')),self.geotech_notes,self.handoff])])
        for i, name in enumerate(['Pile loads', 'Profiles and stresses', 'Pile section', 'Minimum tip', 'Geotech handoff']):
            self.tabs.set_title(i, name)
        separate = Accordion(children=[W.VBox([W.HTML('<p>The shared XML upload above supplies both sections. '
            'Use this only to review a different pile analysis.</p>'), self.upload])])
        separate.set_title(0, 'Optional separate pile analysis'); separate.selected_index = None
        self.ui = W.VBox([W.HTML('<h2 style="color:#213649">1. FBMP pile review</h2><p>Review pile behavior and the minimum-tip study before selecting cap reinforcement.</p>'),
            W.HBox([self.restore_upload, self.export], layout=W.Layout(flex_flow='row wrap')), separate,
            self.upload_output, self.notice, self.source_match, self.cutoff, self.tabs, self.message])
        self.notice.value = notice_html('PILE RESULTS NOT LOADED', 'Upload FBMP XML once above to load pile results and preview cap inputs.')
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
            self.trial_status.value = '<p>Paste trial rows above to enable Evaluate trials. The XML contains one solved pile length.</p>'
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
            'tensile_peak_ksi':'Model concrete tensile peak (ksi)','modeled_weight_lb_ft':'Modeled weight (lb/ft)','source':'Property source'}
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
        widget = go.FigureWidget(figure)
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
            self._trials_changed()
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
            self.reported.value = '<h4>FBMP reported material stress extrema · all piles in selected combination</h4>'+table(rows,
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
        self.trial_output.children = []
        old_figure = self.figures.pop('trials', None)
        if old_figure is not None:
            old_figure.close()
        self.trial_summary.value = ''
        self.run_trials.disabled = not bool(self.trial_text.value.strip())
        self.trial_status.value = ('<p>Trial inputs changed. Click Evaluate trials to update the plots and results.</p>'
            if self.trial_text.value.strip() else '<p>Paste trial rows above to enable Evaluate trials. The XML contains one solved pile length.</p>')
        self.refresh_handoff()

    def _trials(self, _=None):
        self.trial_result = None
        self.trial_output.children = []
        self.trial_summary.value = ''
        self.run_trials.disabled = True
        self.trial_status.value = notice_html('EVALUATING TRIALS', 'Reading the pasted table…', 'pending')
        try:
            rows = parse_trials(self.trial_text.value)
            accepted = self.optional(self.accepted)
            require(accepted is None or bool(self.trial_basis.value.strip()), 'Record the basis for the selected critical embedment.')
            result = evaluate_trials(rows, self.tolerance.value, self.extension.value, self.fraction.value,
                self.extension_mode.value, self.optional(self.reference), self.optional(self.cutoff), accepted, self.rounding.value)
            self.trial_result = result
            p = result['proposed_embedment_ft']
            self.trial_summary.value = '<p><b>Displacement-change candidate: '+(f'{p:.3f} ft' if p is not None else 'Unavailable')+'</b>. '
            self.trial_summary.value += 'The candidate follows the stable sequence from the deepest trial. Select the engineering critical embedment to calculate an adopted tip; a small Δ alone does not establish stability.</p>'
            self.trial_summary.value += table([dict(item=k, value=result[k]) for k in ['accepted_embedment_ft','extension_ft','required_embedment_ft','tip_elevation_ft','total_length_ft']], [('item','Result'), ('value','ft')])
            if any(r['converged'] is None for r in rows):
                self.trial_summary.value += '<p>Some trial convergence results are not supplied.</p>'
            if any(r['dc'] is None for r in rows):
                self.trial_summary.value += '<p>Some trial D/C results are not supplied.</p>'
            intervals = {round(r['interval_ft'], 5) for r in result['rows'] if r['interval_ft'] is not None}
            if len(intervals)>1:
                self.trial_summary.value += '<p>Trial spacing varies. The Δ criterion depends on that spacing; inspect the plotted intervals.</p>'
            self.trial_summary.value += table(result['rows'], [('series','Series'), ('trial','Trial'), ('combination','Combo'), ('pile','Pile'),
                ('embedment_ft','Embedment (ft)'), ('interval_ft','Step (ft)'), ('delta_in','Δ (in)'), ('stable_from_deepest','Stable sequence')])
            self._figure('trials', self.trial_output, trial_figure(result, self.tolerance.value))
            self.trial_status.value = notice_html('TRIALS EVALUATED',
                f'{len(rows)} rows · {len(result["groups"])} series. Plots and calculations are below.', 'success')
        except Exception as exc:
            self.trial_result = None
            self.trial_summary.value = ''
            self.trial_status.value = notice_html('TRIALS NEED REVIEW', html.escape(str(exc)), 'error')
        finally:
            self.run_trials.disabled = not bool(self.trial_text.value.strip())
        self.refresh_handoff()

    def refresh_handoff(self):
        if self.review is None:
            self.handoff.value = '<p>Load pile results to prepare the handoff.</p>'
            return
        s = self.review['section']
        rows = [dict(item='Analyzed section', value=f'{s["shape"]} {s["width_in"]:g} × {s["depth_in"]:g} in, {s["kind"]}'),
                dict(item='Analysis area (in²)', value=s['area_in2']), dict(item='Elastic modulus (ksi)', value=s['modulus_ksi']),
                dict(item='EA (kip)', value=s['area_in2']*s['modulus_ksi']), dict(item='I2 / I3 (in⁴)',value=f'{s["i2_in4"]:g} / {s["i3_in4"]:g}'),
                dict(item='Modeled weight (lb/ft)',value=s['modeled_weight_lb_ft']),
                dict(item='Analyzed pile lengths (ft)',value='; '.join(f'P{p}: {v["length_ft"]:.3f}' for p,v in self.review['piles'].items()))]
        for g in governors(self.review):
            if g['metric'] in ('Head compression (kip)', 'Head uplift (kip)', 'Any-depth compression (kip)'):
                rows.append(dict(item=g['state']+' · '+g['metric'], value=g['value']))
        try:
            weight,diameter=self.optional(self.nominal_weight),self.optional(self.nominal_diameter)
            require(weight is None or weight>0,'Nominal weight must be positive or blank.')
            require(diameter is None or diameter>0,'Nominal diameter must be positive or blank.')
            rows.extend([dict(item='Supplied nominal weight (lb/ft)',value=weight),
                dict(item='Supplied nominal OD (in)',value=diameter),dict(item='Pile toe condition',value=self.toe.value),
                dict(item='Nominal weight / analyzed area (lb/ft³)',value=weight*144/s['area_in2'] if weight is not None else None),
                dict(item='Project notes',value=self.geotech_notes.value or 'Not supplied')])
        except ValueError as exc:
            rows.append(dict(item='Geotechnical input error',value=str(exc)))
        self.handoff.value = '<h4>Geotechnical handoff</h4>'+table(rows, [('item','Item'), ('value','Value')])
        if self.trial_result:
            self.handoff.value += table([dict(item=k, value=self.trial_result[k]) for k in ['accepted_embedment_ft','required_embedment_ft','tip_elevation_ft','total_length_ft']], [('item','Selected trial result'), ('value','ft')])
        else:
            self.handoff.value += '<p>Minimum-tip study: no current evaluated result.</p>'
        self.handoff.value += ('<p>Compression and uplift are factored combination demands. 1 short ton = 2 kip. '
            'Nominal geotechnical resistance, Davisson capacity curves, downdrag/scour conditions, nominal steel weight, toe condition and driving criteria require separate project inputs. '
            'Modeled weight is not assumed to be nominal pile weight.</p>')

    def snapshot(self):
        controls = ['combo','piles','cutoff','use_override','material','circular','trial_text','trial_label','tolerance','extension','fraction',
                    'extension_mode','reference','accepted','rounding','trial_basis','nominal_weight','nominal_diameter','toe','geotech_notes']
        return dict(schema_version=2, review=deepcopy(self.review), controls={k:getattr(self,k).value for k in controls},
                    override={k:w.value for k,w in self.override.items()})

    def restore(self, state):
        require(state.get('schema_version') in (1, 2) and isinstance(state.get('review'), dict), 'Unsupported pile review file.')
        state = deepcopy(state)
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
                    'elastic_stresses.csv':elastic_profile(self.review, s)}
        if self.trial_result:
            datasets['minimum_tip_trials.csv'] = self.trial_result['rows']
            (folder/'minimum_tip_result.json').write_text(json.dumps(self.trial_result, indent=2, allow_nan=False), encoding='utf-8')
        for name, rows in datasets.items():
            (folder/name).write_text(csv_text(rows), encoding='utf-8-sig')
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

    def _download(self, path):
        try:
            from google.colab import files
        except ImportError:
            self.message.value = '<p>Saved: '+html.escape(str(path.resolve()))+'</p>'
        else:
            files.download(str(path))
            self.message.value = '<p>Download prepared: '+html.escape(path.name)+'</p>'

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
