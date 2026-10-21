"""Jupyter / Colab interface of a journal calculation (the backwall notebook layout, driven by the package data)."""
from copy import deepcopy
from datetime import datetime, timezone
from functools import partial
import html
from pathlib import Path
from tempfile import TemporaryDirectory

import ipywidgets as W
from pier_cap.plotly_compat import FigureWidget
from pier_cap.recalc_control import RecalcControl
from pier_cap.source_status import notice_html, upload_entries
from pier_cap.widget_compat import Tab, Accordion

from .model import default_case, upgrade_case, validate_case, evaluate, formula_trace, UNIT_LABELS, evaluate_expression
from .reviews import record_review, reopen, review_html
from .exports import Exports
from . import figures as fig

STATUS_COLORS = {'project source': '#17633b', 'decision': '#245674', 'code': '#485969', 'provisional geometry': '#805600',
                 'pending confirmation': '#a06500', 'trial': '#485969', 'journal': '#245674', 'model': '#17633b',
                 'differs from register': '#9d302b', 'edited in notebook': '#7a3e9d'}
STYLE = '''<style>
.ebw-input .widget-label{white-space:normal!important;line-height:1.2!important;height:auto!important}
.ebw-table{border-collapse:collapse;width:100%;font:12px Arial}.ebw-table td,.ebw-table th{padding:6px 8px;border-bottom:1px solid #dce5ec;text-align:left;vertical-align:top}
.ebw-table th{background:#e7eef4;position:sticky;top:0}.ebw-num{text-align:right;font-variant-numeric:tabular-nums}
.ebw-eq{overflow-x:auto;padding:4px 0}.ebw-eq math{font-size:14px}.ebw-cap{color:#485969;font-size:12px;margin:8px 0 0}
.ebw-review{margin:4px 0;padding:4px 6px;background:#fff3d6;border-left:3px solid #805600;font-size:11px}
details.ebw>summary{cursor:pointer;color:#245c85;font-size:12px}
.ebw-fig svg{max-width:100%;height:auto;border:1px solid #dce5ec;background:#fff}.ebw-fig .canvas-title{font:12px Arial;color:#485969}
.ebw-prose{font:13px Arial;margin:4px 0}.ebw-prose table{font:12px Arial;border-collapse:collapse}.ebw-prose td{padding:3px 6px;border-bottom:1px solid #eef2f5}
</style>'''


def _tooltip(control, text):
    for attr in ('tooltip', 'description_tooltip'):
        if attr in control.keys:
            setattr(control, attr, text)


class UploadControl:
    """Colab's native chooser, or ipywidgets FileUpload elsewhere; calls back with (content, filename)."""

    def __init__(self, label, accept, callback, width='240px'):
        self.callback = callback
        self.output = W.Output(layout=W.Layout(display='none'))
        try:
            from google.colab import files
        except ImportError:
            self.files = None
            self.button = W.FileUpload(accept=accept, multiple=False, description=label, layout=W.Layout(width=width))
            self.button.observe(self._uploaded, names='value')
        else:
            self.files = files
            self.button = W.Button(description=label, icon='upload', layout=W.Layout(width=width))
            self.button.on_click(self._colab)

    def _uploaded(self, change):
        if not self.button.value:
            return
        try:
            entries = upload_entries(self.button.value)
            if len(entries) == 1:
                self.callback(bytes(entries[0]['content']), entries[0]['name'])
        finally:
            if 'metadata' in self.button.traits():
                self.button.metadata = []; self.button.data = []; self.button._counter = 0
            else:
                self.button.value = ()

    def _colab(self, _=None):
        from IPython.display import clear_output
        self.output.layout.display = ''
        try:
            with self.output:
                clear_output(wait=True)
                with TemporaryDirectory(prefix='calc-upload-') as folder:
                    received = self.files.upload(target_dir=folder)
                clear_output(wait=False)
            if received:
                name, content = next(iter(received.items()))
                self.callback(content, Path(name).name)
        finally:
            self.output.layout.display = 'none'


class CalcNotebook:
    def __init__(self, spec, case=None, export_root='exports'):
        self.spec = spec
        self.exports = Exports(spec)
        self.case = upgrade_case(spec, case or default_case(spec))
        self.export_root = Path(export_root)
        self.e = None; self.busy = False; self.controls = {}; self.last_files = {}
        self.message = W.HTML()
        self._build_sources()
        self._build_design()
        self.refresh_sources()
        self.recalculate()

    # ---------------------------------------------------------------- sources
    def _build_sources(self):
        spec = self.spec
        self.case_status = W.HTML()
        self.case_upload = UploadControl('Load case JSON', '.json,.JSON', self._load_case)
        reset = W.Button(description='Reset to journal values', icon='undo', layout=W.Layout(width='240px'))
        reset.on_click(lambda _: self.load(default_case(spec), 'journal values'))
        self.confirm, self.confirm_notes = {}, {}
        for key, item in spec.text.get('confirmations', {}).items():
            box = W.Checkbox(value=bool(self.case['confirmations'].get(key)), description=item['text'], indent=False, layout=W.Layout(width='100%'))
            box.observe(partial(self._confirmed, key), names='value')
            self.confirm[key] = box
        self.sources_table = W.HTML(layout=W.Layout(max_height='520px', overflow='auto'))
        details = Accordion(children=[self.sources_table]); details.set_title(0, 'Every input · value, source and status'); details.selected_index = None
        sources = ''.join(f'<li><b>{html.escape(s["label"])}</b> · <code>{html.escape(s.get("path", ""))}</code></li>' for s in spec.sources.get('sources', {}).values())
        self.sources_ui = W.VBox([
            W.HTML(STYLE + f'<h2 style="color:#213649;margin-bottom:4px">1. Project sources and assumptions</h2>'
                   f'<p>{html.escape(spec.text.get("sources_intro", "The notebook starts from the values the project journal holds for this calculation; every input names the journal module or the provision it comes from. Edit an input in Cell 2 to study a change; the journal edition of the Blockpad export is tied to the journal values."))}</p>'
                   + (f'<ul>{sources}</ul>' if sources else '')),
            W.HBox([self.case_upload.button, reset], layout=W.Layout(flex_flow='row wrap', grid_gap='8px')), self.case_upload.output, self.case_status]
            + ([W.HTML('<h3>Confirmations</h3>'), W.VBox(list(self.confirm.values()))] if self.confirm else []) + [details])

    def _load_case(self, content, filename):
        try:
            self.load(self.exports.load_case(content), filename)
        except Exception as exc:
            self.case_status.value = notice_html('CASE NOT LOADED', html.escape(f'{filename}: {exc}'), 'error')

    def load(self, case, label):
        self.case = upgrade_case(self.spec, case)
        self._sync_controls()
        for key, box in self.confirm.items():
            self.busy = True; box.value = bool(self.case['confirmations'].get(key)); self.busy = False
        self.case_status.value = notice_html('CASE LOADED', f'<b>{html.escape(label)}</b> · {datetime.now(timezone.utc):%H:%M:%S UTC}. Inputs, sources and reviews restored.', 'success')
        self.refresh_sources()
        self.recalculate()

    def _confirmed(self, key, change):
        if self.busy:
            return
        self.case['confirmations'][key] = bool(change['new'])
        self._mark_dirty()

    def refresh_sources(self):
        rows = []
        for spec in self.spec.input_spec:
            name = spec['name']; src = self.case['sources'][name]
            color = STATUS_COLORS.get(src['status'], '#485969')
            unit = UNIT_LABELS.get(spec.get('unit'), spec.get('unit') or '')
            value = self.case['inputs'][name]
            shown = f'{value:g}' if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
            rows.append(f'<tr><td>{html.escape(spec.get("group", ""))}</td><td>{html.escape(spec["caption"])}</td><td class="ebw-num">{html.escape(shown)} {html.escape(unit)}</td>'
                        f'<td>{html.escape(src["source"])}</td><td style="color:{color};font-weight:600">{html.escape(src["status"])}</td></tr>')
        self.sources_table.value = (STYLE + '<table class="ebw-table"><tr><th>Group</th><th>Input</th><th>Value</th><th>Source / basis</th><th>Status</th></tr>'
                                    + ''.join(rows) + '</table>')

    # ----------------------------------------------------------------- design
    def _build_design(self):
        spec = self.spec
        self.recalc = RecalcControl(self.recalculate)
        self.banner = W.HTML()
        self.input_tabs = self._inputs()
        self.boxes = {name: W.VBox(layout=W.Layout(width='100%', min_width='0')) for name in ('results', 'figures', 'checks', 'equations', 'exports')}
        self.check_view = W.Dropdown(options=[('All checks', 'all'), ('Largest ratio first', 'ratio'), ('Failures first', 'failures'),
                                              ('Pending only', 'pending'), ('Reviewed checks', 'reviewed')], value='all', description='View',
                                     layout=W.Layout(width='280px'))
        self.check_view.observe(lambda _: self._render_checks(), names='value')
        self._build_review_panel()
        self._build_export_panel()
        titles = ['Results', 'Figures', 'D/C checks', 'Equations', 'Exports']
        self.result_tabs = Tab(children=[self.boxes[k] for k in ('results', 'figures', 'checks', 'equations', 'exports')], layout=W.Layout(width='100%', min_width='0'))
        for i, t in enumerate(titles):
            self.result_tabs.set_title(i, t)
        header = W.HTML(STYLE + f'<h2 style="color:#213649;margin-bottom:4px;padding-right:170px">2. {html.escape(spec.title)}</h2>'
                        '<p>Edit inputs in the cards, then click <b>Recalc</b> at the top right. Results, figures, the check register and exports '
                        'always describe the last completed Recalc.</p>')
        inputs = W.VBox([W.HTML('<h3>Inputs</h3>'), self.input_tabs], layout=W.Layout(width='100%'))
        self.design_ui = self.recalc.wrap([header, self.banner, inputs, self.result_tabs, self.message])

    def _inputs(self):
        spec = self.spec
        tabs, groups = [], spec.input_groups()
        for group in groups:
            controls = []
            for d in (s for s in spec.input_spec if s.get('group') == group):
                name, unit, kind = d['name'], d.get('unit'), d.get('kind', 'number')
                value = self.case['inputs'][name]
                if kind == 'option':
                    control = W.Dropdown(options=[(o, o) for o in d['options']], value=value)
                elif kind == 'text':
                    control = W.Text(value=str(value))
                elif kind == 'bool':
                    control = W.Dropdown(options=[('true', True), ('false', False)], value=bool(value))
                elif d.get('integer'):
                    control = W.BoundedIntText(value=int(value), min=d.get('min', 0), max=d.get('max', 1000))
                else:
                    control = W.FloatText(value=float(value), step=d.get('step', 0.25))
                label = d['caption'] + (f' ({UNIT_LABELS.get(unit, unit)})' if unit else '')
                control.description = label
                control.style.description_width = '250px'
                control.layout = W.Layout(width='420px', max_width='calc(100% - 4px)', min_height='30px', height='auto')
                control.add_class('ebw-input')
                _tooltip(control, f'{name} · {d["source"]} ({d["status"]})')
                control.observe(partial(self._changed, name), names='value')
                self.controls[name] = control
                controls.append(control)
            tabs.append(W.HBox(controls, layout=W.Layout(width='100%', flex_flow='row wrap', grid_gap='4px 16px', padding='8px', border='1px solid #c4cdd6')))
        tab = Tab(children=tabs, layout=W.Layout(width='100%'))
        for i, g in enumerate(groups):
            tab.set_title(i, g or 'Inputs')
        return tab

    def _sync_controls(self):
        self.busy = True
        try:
            for name, control in self.controls.items():
                value = self.case['inputs'][name]
                kind = self.spec.inputs[name].get('kind', 'number')
                if kind == 'number':
                    control.value = int(value) if isinstance(control, W.BoundedIntText) else float(value)
                else:
                    control.value = value
        finally:
            self.busy = False

    def _changed(self, name, change):
        if self.busy:
            return
        old = self.case['inputs'][name]
        if old == change['new']:
            return
        self.case['inputs'][name] = change['new']
        src = self.case['sources'][name]
        if src['status'] != 'edited in notebook':
            shown = f'{old:g}' if isinstance(old, (int, float)) and not isinstance(old, bool) else str(old)
            src['source'] = f'Edited in notebook (was {shown}: {src["source"]})'
            src['status'] = 'edited in notebook'
        self.refresh_sources()
        self._mark_dirty()

    def _mark_dirty(self):
        try:
            validate_case(self.spec, self.case)
        except ValueError as exc:
            self.recalc.set_state('invalid')
            self.banner.value = notice_html('CHECK INPUTS', html.escape(str(exc)), 'error')
            return
        self.recalc.set_state('dirty')
        self.banner.value = notice_html('RESULTS OUT OF DATE · RECALC NEEDED', 'Inputs or confirmations changed. Click <b>Recalc</b> to update results, checks and exports.', 'pending')
        for button in self.export_buttons:
            button.disabled = True

    def recalculate(self, _=None):
        self.recalc.set_state('running')
        try:
            self.e = evaluate(self.spec, self.case)
            self.case = deepcopy(self.e.case)
            self.refresh_sources()
        except Exception as exc:
            self.recalc.set_state('error')
            self.banner.value = notice_html('CALCULATION STOPPED', html.escape(str(exc)), 'error')
            return
        self._render_all()
        self.recalc.set_state('done')
        for button in self.export_buttons:
            button.disabled = False

    # ---------------------------------------------------------------- results
    def _figure(self, figure):
        widget = FigureWidget(figure)
        widget.prepare_display()
        return widget

    @staticmethod
    def _replace(box, children):
        old = [c for c in box.children if isinstance(c, FigureWidget)]
        box.children = children
        for widget in old:
            if widget not in children:
                widget.close()

    def _render_all(self):
        e, spec = self.e, self.spec
        failed = [c for c in e.checks if 'FAIL' in c.status]
        pending = [c for c in e.checks if 'PENDING' in c.status]
        kind = 'error' if failed else 'pending' if pending else 'success'
        key = ' · '.join(f'{r["label"]} <b>{html.escape(e.text(r["name"], r.get("places", 3), r.get("unit")) if r["name"] in e.units else str(e.engine.get(r["name"])))}</b>'
                         for r in spec.text.get('key_results', [])[:4])
        self.banner.value = notice_html('CALC DONE · ' + e.status.upper(), (key + '<br>' if key else '')
                                        + f'Largest numerical check ratio: <b>{e.strength_dc:.3f}</b>.', kind)
        from .report import ReportBuilder
        rb = ReportBuilder(spec, e)
        tables = ''.join(rb.table_html(t) for t in spec.tables)
        self._replace(self.boxes['results'], [W.HTML(STYLE + rb.summary_html() + tables, layout=W.Layout(max_height='900px', overflow='auto'))])
        figures = []
        for section in spec.sections:
            for b in section.get('blocks', []):
                if b['kind'] == 'canvas':
                    figures.append(f'<div class="ebw-fig">{rb.block_html(b)}</div>')
        ratios = fig.ratios_figure(e)
        self._replace(self.boxes['figures'], ([self._figure(ratios)] if ratios else []) + [W.HTML(STYLE + ''.join(figures))])
        self._render_checks()
        self._render_equations()
        self._refresh_review_options()

    @staticmethod
    def _status(status):
        color = '#bb3e39' if 'FAIL' in status else '#a06500' if 'PENDING' in status else '#17633b' if 'PASS' in status else '#245674'
        return f'<b style="color:{color}">{html.escape(status)}</b>'

    def _render_checks(self):
        if self.e is None:
            return
        e, view, spec = self.e, self.check_view.value, self.spec
        checks = list(e.checks)
        if view == 'ratio':
            checks.sort(key=lambda c: (0, -c.ratio) if isinstance(c.ratio, (int, float)) else (1, 0))
        elif view == 'failures':
            checks.sort(key=lambda c: 'FAIL' not in c.status)
        elif view == 'pending':
            checks = [c for c in checks if 'PENDING' in c.status]
        elif view == 'reviewed':
            checks = [c for c in checks if c.review]
        trace = {t['name']: t for t in formula_trace(e)}
        rows = []
        for c in checks:
            refs = '; '.join(f'{spec.references[k]["code"]} {spec.references[k]["article"]} — {spec.references[k]["governs"]}' for k in c.refs if k in spec.references)
            eqs = ''.join(f'<div class="ebw-eq">{trace[n]["mathml"]}</div>' for n in c.names if n in trace)
            body = (f'<p><b>Basis:</b> {html.escape(c.basis)}</p>' + (f'<p><b>Code:</b> {html.escape(refs)}</p>' if refs else '') + eqs
                    + (f'<p><i>{html.escape(c.note)}</i></p>' if c.note else ''))
            rows.append(f'<tr><td>{html.escape(c.group)}</td><td>{html.escape(c.label)}{review_html(c)}<details class="ebw"><summary>Equation &amp; values</summary>{body}</details></td>'
                        f'<td>{html.escape(c.demand)}</td><td>{html.escape(c.capacity)}</td><td class="ebw-num">{"" if c.ratio is None else f"{c.ratio:.3f}"}</td>'
                        f'<td>{self._status(c.status)}</td></tr>')
        register = (STYLE + f'<p><b>{html.escape(e.status)}</b> · showing {len(checks)} of {len(e.checks)}</p><table class="ebw-table"><tr><th>Group</th><th>Check</th>'
                    '<th>Demand / required</th><th>Capacity / limit</th><th>Ratio</th><th>Status</th></tr>' + ''.join(rows) + '</table>')
        ratios = fig.ratios_figure(e)
        self._replace(self.boxes['checks'], ([self._figure(ratios)] if ratios else []) + [self.review_ui, self.check_view,
                                                                                           W.HTML(register, layout=W.Layout(max_height='900px', overflow='auto'))])

    def _render_equations(self):
        e, spec = self.e, self.spec
        trace = formula_trace(e)
        parts = []
        for i, section in enumerate(spec.sections):
            items = [t for t in trace if t['section'] == section['key']]
            body = ''.join(f'<p class="ebw-cap">{html.escape(t["caption"])}</p><div class="ebw-eq">{t["mathml"]}</div>' for t in items)
            parts.append(f'<details class="ebw"{" open" if i == 0 else ""}><summary><b>{html.escape(section["title"])}</b> · {len(items)} equations</summary>{body}</details>')
        self._replace(self.boxes['equations'], [W.HTML(STYLE + ''.join(parts), layout=W.Layout(max_height='900px', overflow='auto'))])

    # -------------------------------------------------------------- reviews
    def _build_review_panel(self):
        self.review_check = W.Dropdown(description='Check', layout=W.Layout(width='520px'))
        self.review_reason = W.Text(description='Reason', placeholder='Closure note or override justification', layout=W.Layout(width='520px'))
        self.review_by = W.Text(description='Reviewer', placeholder='Initials (optional)', layout=W.Layout(width='260px'))
        buttons = []
        for label, action in (('Close as passed', 'close'), ('Override as passed', 'override'), ('Reopen check', 'reopen')):
            b = W.Button(description=label, layout=W.Layout(width='170px'))
            b.on_click(partial(self._review, action)); buttons.append(b)
        self.review_status = W.HTML()
        panel = W.VBox([W.HBox([self.review_check, self.review_by], layout=W.Layout(flex_flow='row wrap')), self.review_reason, W.HBox(buttons), self.review_status])
        self.review_ui = Accordion(children=[panel]); self.review_ui.set_title(0, 'Record a closure or override')
        self.review_ui.selected_index = None

    def _refresh_review_options(self):
        self.review_check.options = [(f'{c.group} · {c.label} [{c.status}]', c.key) for c in self.e.checks] or [('(no checks)', None)]

    def _review(self, action, _=None):
        key = self.review_check.value
        check = next((c for c in self.e.checks if c.key == key), None)
        try:
            if action == 'reopen':
                reopen(self.case, key)
            else:
                record_review(self.case, check, action, self.review_reason.value, self.review_by.value)
        except Exception as exc:
            self.review_status.value = notice_html('REVIEW NOT RECORDED', html.escape(str(exc)), 'error')
            return
        self.review_status.value = notice_html('REVIEW UPDATED', html.escape(f'{action} · {check.label if check else key}'), 'success')
        self.review_reason.value = ''
        self.recalculate()

    # -------------------------------------------------------------- exports
    def _build_export_panel(self):
        x = self.exports
        self.export_status = W.HTML(); self.download_output = W.Output()
        specs = [('Case JSON', x.CASE), ('Calculation report', x.REPORT), ('Checks CSV', x.CHECKS),
                 ('Export distilled Blockpad (.bpad)', x.DISTILLED_BPAD), ('Full bundle ZIP', x.BUNDLE)]
        self.export_buttons = []
        for label, name in specs:
            b = W.Button(description=label, icon='copy' if name == x.DISTILLED_BPAD else 'download',
                         layout=W.Layout(width='270px' if name == x.DISTILLED_BPAD else '230px'))
            b.on_click(partial(self._export, name)); self.export_buttons.append(b)
        self.boxes['exports'].children = [
            W.HTML('<p>Exports use the last completed Recalc. Each click writes a timestamped folder under <code>exports/</code> and downloads the file. '
                   'In Colab, <code>/content</code> is temporary runtime storage; keep the downloaded copies.</p>'
                   f'<p><b>Export distilled Blockpad (.bpad)</b> writes a standalone Blockpad document of the current case (the same distilled sheet as '
                   f'<code>{html.escape(self.spec.package)}/{html.escape(x.DISTILLED_BPAD)}</code>: equations shown once, the journal figures as live canvases), '
                   'verified against this notebook before it is written; its verification record is saved beside it and in the bundle. '
                   'Open and recalculate the sheet in Blockpad. It distils the numerical checks only; it is not design acceptance.</p>'),
            W.HBox(self.export_buttons, layout=W.Layout(flex_flow='row wrap', grid_gap='6px')), self.export_status, self.download_output]

    def _export(self, name, _=None):
        if self.e is None:
            return
        x = self.exports
        try:
            path = x.export_file(self.e, self.export_root, name)
        except Exception as exc:
            self.export_status.value = notice_html('EXPORT FAILED', html.escape(str(exc)), 'error')
            return
        self.last_files[name] = path
        detail = f'<code>{html.escape(str(path.resolve()))}</code>'
        if name == x.DISTILLED_BPAD:
            verification = path.parent / x.BPAD_VERIFICATION
            detail = (html.escape(x.bpad_summary(verification.read_bytes())) + '<br>' + detail
                      + f'<br>Verification record: <code>{html.escape(str(verification.resolve()))}</code>')
        self.export_status.value = notice_html('DISTILLED BLOCKPAD READY' if name == x.DISTILLED_BPAD else 'EXPORT WRITTEN', detail, 'success')
        with self.download_output:
            from IPython.display import clear_output, display, FileLink
            clear_output()
            try:
                from google.colab import files as colab_files
            except ImportError:
                display(FileLink(str(path)))
            else:
                colab_files.download(str(path.resolve()))

    def display(self, which='design'):
        from IPython.display import display
        display(self.sources_ui if which == 'sources' else self.design_ui)

    def close(self):
        for widget in (self.sources_ui, self.design_ui):
            widget.close()
