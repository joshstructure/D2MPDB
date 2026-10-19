"""Jupyter / Colab interface for the end-bent backwall, cheek-wall and tie-back calculation."""
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
from .model import (default_case, upgrade_case, validate_case, evaluate, edit_input, INPUTS, INPUT_SPEC, CONFIRMATIONS, SECTIONS,
                    COMBINATIONS, BAR_SIZES, formula_trace, strap_table, REFERENCES, SOURCES)
from .reviews import record_review, reopen, review_html
from .sources import READERS, apply_source
from . import exports, visuals

GROUPS = ['Geometry', 'Soil & surcharge', 'Bearings & superstructure', 'Tie-back', 'Wind (cheek walls)', 'Reinforcement', 'Materials & factors']
STATUS_COLORS = {'project source': '#17633b', 'decision': '#245674', 'code': '#485969', 'provisional geometry': '#805600',
                 'pending confirmation': '#a06500', 'trial': '#485969', 'differs from register': '#9d302b', 'edited in notebook': '#7a3e9d'}
UNIT_LABELS = {'kip/ft^3': 'kcf', 'kip/ft^2': 'ksf', 'kip*ft': 'kip-ft', 'in^2': 'in²'}
SOURCE_LABELS = {'EB-CASE': ('Load end-bent cap case', '.json,.JSON'), 'EB-XML': ('Load FBMP end-bent XML', '.xml,.XML'),
                 'CAD-MODEL': ('Load FreeCAD model', '.FCStd,.fcstd')}
STYLE = '''<style>
.ebw-input .widget-label{white-space:normal!important;line-height:1.2!important;height:auto!important}
.ebw-table{border-collapse:collapse;width:100%;font:12px Arial}.ebw-table td,.ebw-table th{padding:6px 8px;border-bottom:1px solid #dce5ec;text-align:left;vertical-align:top}
.ebw-table th{background:#e7eef4;position:sticky;top:0}.ebw-num{text-align:right;font-variant-numeric:tabular-nums}
.ebw-eq{overflow-x:auto;padding:4px 0}.ebw-eq math{font-size:14px}.ebw-cap{color:#485969;font-size:12px;margin:8px 0 0}
.ebw-review{margin:4px 0;padding:4px 6px;background:#fff3d6;border-left:3px solid #805600;font-size:11px}
details.ebw>summary{cursor:pointer;color:#245c85;font-size:12px}
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
                with TemporaryDirectory(prefix='backwall-upload-') as folder:
                    received = self.files.upload(target_dir=folder)
                clear_output(wait=False)
            if received:
                name, content = next(iter(received.items()))
                self.callback(content, Path(name).name)
        finally:
            self.output.layout.display = 'none'


class BackwallNotebook:
    def __init__(self, case=None, export_root='exports'):
        self.case = upgrade_case(case or default_case())
        self.export_root = Path(export_root)
        self.e = None; self.busy = False; self.controls = {}; self.last_files = {}
        self.message = W.HTML()
        self._build_sources()
        self._build_design()
        self.refresh_sources()
        self.recalculate()

    # ---------------------------------------------------------------- sources
    def _build_sources(self):
        self.source_status = {sid: W.HTML() for sid in READERS}
        self.uploads = {sid: UploadControl(label, accept, partial(self._load_source, sid)) for sid, (label, accept) in SOURCE_LABELS.items()}
        self.case_status = W.HTML()
        self.case_upload = UploadControl('Load backwall case JSON', '.json,.JSON', self._load_case)
        reset = W.Button(description='Reset to registered defaults', icon='undo', layout=W.Layout(width='240px'))
        reset.on_click(lambda _: self.load(default_case(), 'registered defaults'))
        self.confirm = {}
        self.confirm_notes = {}
        for key, text in CONFIRMATIONS.items():
            box = W.Checkbox(value=bool(self.case['confirmations'][key]), description=text, indent=False, layout=W.Layout(width='100%'))
            box.observe(partial(self._confirmed, key), names='value')
            self.confirm[key] = box
            self.confirm_notes[key] = W.HTML()
        self.sources_table = W.HTML(layout=W.Layout(max_height='520px', overflow='auto'))
        cards = []
        for sid, upload in self.uploads.items():
            registered = SOURCES['sources'][sid]
            cards.append(W.VBox([W.HTML(f'<b>{html.escape(registered["label"])}</b><br><small><code>{html.escape(registered["path"])}</code></small>'),
                                 upload.button, upload.output, self.source_status[sid]],
                                layout=W.Layout(flex='1 1 300px', min_width='280px', padding='8px', border='1px solid #c4cdd6')))
        details = Accordion(children=[self.sources_table]); details.set_title(0, 'Every input · value, source and status'); details.selected_index = None
        self.sources_ui = W.VBox([
            W.HTML(STYLE + '<h2 style="color:#213649;margin-bottom:4px">1. Project sources and assumptions</h2>'
                   '<p>The notebook starts from the registered <b>project_current</b> values embedded below. Upload a registered file to '
                   're-read it and compare its SHA-256 with the source register; a different file is reported, never silently adopted. '
                   'Decisions D-014 to D-019 record the tie-back, loading, soil, landing-slab, cheek-wall and height choices.</p>'),
            W.HBox(cards, layout=W.Layout(width='100%', flex_flow='row wrap', grid_gap='8px')),
            W.HBox([self.case_upload.button, reset], layout=W.Layout(flex_flow='row wrap', grid_gap='8px')), self.case_upload.output, self.case_status,
            W.HTML('<h3>Confirmations</h3><p>Checked items carry dated project evidence below. Unconfirmed items remain <b>PENDING</b>. '
                   'Editing a reviewed value reopens its confirmation. Source consistency does not close connection or fabrication review.</p>'),
            W.VBox([W.VBox([box, self.confirm_notes[key]]) for key, box in self.confirm.items()]), details])

    def _load_source(self, sid, content, filename):
        try:
            updates, receipt = apply_source(self.case, sid, content, filename)
        except Exception as exc:
            self.source_status[sid].value = notice_html('SOURCE NOT APPLIED', html.escape(f'{filename}: {exc}'), 'error')
            return
        self._sync_controls()
        self.refresh_sources()
        self._mark_dirty()

    def _load_case(self, content, filename):
        try:
            self.load(exports.load_case(content), filename)
        except Exception as exc:
            self.case_status.value = notice_html('CASE NOT LOADED', html.escape(f'{filename}: {exc}'), 'error')

    def load(self, case, label):
        self.case = upgrade_case(case)
        self._sync_controls()
        for key, box in self.confirm.items():
            self.busy = True; box.value = bool(self.case['confirmations'][key]); self.busy = False
        self.case_status.value = notice_html('CASE LOADED', f'<b>{html.escape(label)}</b> · {datetime.now(timezone.utc):%H:%M:%S UTC}. Inputs, sources, confirmations and reviews restored.', 'success')
        self.refresh_sources()
        self.recalculate()

    def _confirmed(self, key, change):
        if self.busy:
            return
        self.case['confirmations'][key] = bool(change['new'])
        record = self.case.setdefault('confirmation_evidence', {}).setdefault(key, {})
        if change['new']:
            record['note'] = 'Manually confirmed in this notebook. Previous evidence: ' + record.get('note', '')
            record['inputs'] = {n: self.case['inputs'][n] for n in record.get('inputs', {})}
            record['stale'] = False
        self.refresh_sources()
        self._mark_dirty()

    def refresh_sources(self):
        self.busy = True
        try:
            for key, box in self.confirm.items():
                box.value = bool(self.case['confirmations'][key])
                evidence = self.case.get('confirmation_evidence', {}).get(key, {})
                self.confirm_notes[key].value = '<div style="margin:0 12px 10px;color:#485969;font-size:12px">' + (
                    '<b>Needs review after input changes. </b>' if evidence.get('stale') else '') + html.escape(evidence.get('note', 'No project evidence recorded in this saved case.')) + '</div>'
        finally:
            self.busy = False
        receipts = self.case.get('receipts', {})
        for sid, widget in self.source_status.items():
            r = receipts.get(sid)
            if not r:
                widget.value = notice_html('USING REGISTERED DEFAULTS', 'No file uploaded in this case. Embedded values follow the registered source.')
                continue
            kind = 'success' if r['matches_register'] else 'pending'
            title = 'MATCHES SOURCE REGISTER' if r['matches_register'] else 'DIFFERS FROM SOURCE REGISTER'
            notes = ''.join(f'<br>• {html.escape(n)}' for n in r['notes'])
            widget.value = notice_html(title, f'<b>{html.escape(r["filename"])}</b> · {html.escape(r["loaded_utc"])}<br>'
                                       f'SHA-256 <code>{r["sha256"][:16]}…</code><br>Applied: {html.escape(", ".join(r["applied"]))}{notes}', kind)
        rows = []
        for spec in INPUT_SPEC:
            name = spec['name']; src = self.case['sources'][name]
            color = STATUS_COLORS.get(src['status'], '#485969')
            unit = UNIT_LABELS.get(spec['unit'], spec['unit'] or '')
            value = self.case['inputs'][name]
            value = f'#{int(value)}' if spec['unit'] == 'bar' else f'{value:g}'
            rows.append(f'<tr><td>{html.escape(spec["group"])}</td><td>{html.escape(spec["caption"])}</td><td class="ebw-num">{value} {html.escape(unit if unit != "bar" else "")}</td>'
                        f'<td>{html.escape(src["source"])}</td><td style="color:{color};font-weight:600">{html.escape(src["status"])}</td></tr>')
        self.sources_table.value = (STYLE + '<table class="ebw-table"><tr><th>Group</th><th>Input</th><th>Value</th><th>Source / basis</th><th>Status</th></tr>'
                                    + ''.join(rows) + '</table>')

    # ----------------------------------------------------------------- design
    def _build_design(self):
        self.recalc = RecalcControl(self.recalculate)
        self.banner = W.HTML()
        self.input_tabs = self._inputs()
        self.boxes = {name: W.VBox(layout=W.Layout(width='100%', min_width='0')) for name in
                      ('drawings', 'strap', 'backwall', 'cheek', 'cap', 'checks', 'equations', 'exports')}
        self.strap_combo = W.Dropdown(options=[(c['label'], c['key']) for c in COMBINATIONS], value='STRI', description='Combination',
                                      layout=W.Layout(width='320px'))
        self.strap_combo.observe(lambda _: self._render_strap(), names='value')
        self.check_view = W.Dropdown(options=[('All checks', 'all'), ('Largest ratio first', 'ratio'), ('Failures first', 'failures'),
                                              ('Pending only', 'pending'), ('Reviewed checks', 'reviewed')], value='all', description='View',
                                     layout=W.Layout(width='280px'))
        self.check_view.observe(lambda _: self._render_checks(), names='value')
        self._build_review_panel()
        self._build_export_panel()
        titles = ['Section & plan', 'Tie-back strap', 'Backwall', 'Cheek walls', 'Cap supplement', 'D/C checks', 'Equations', 'Exports']
        self.result_tabs = Tab(children=[self.boxes[k] for k in ('drawings', 'strap', 'backwall', 'cheek', 'cap', 'checks', 'equations', 'exports')],
                               layout=W.Layout(width='100%', min_width='0'))
        for i, t in enumerate(titles):
            self.result_tabs.set_title(i, t)
        header = W.HTML(STYLE + '<h2 style="color:#213649;margin-bottom:4px;padding-right:170px">2. Backwall, cheek walls and tie-back straps</h2>'
                        '<p>Edit inputs in the cards, then click <b>Recalc</b> at the top right. Results, drawings, the check register and exports '
                        'always describe the last completed Recalc.</p>')
        inputs = W.VBox([W.HTML('<h3>Inputs</h3>'), self.input_tabs], layout=W.Layout(width='100%'))
        self.design_ui = self.recalc.wrap([header, self.banner, inputs, self.result_tabs, self.message])

    def _inputs(self):
        tabs = []
        for group in GROUPS:
            controls = []
            for spec in (s for s in INPUT_SPEC if s['group'] == group):
                name, unit = spec['name'], spec['unit']
                value = self.case['inputs'][name]
                if name == 'single_ck':
                    control = W.Dropdown(options=[('Single centered mat', 1), ('Legacy steel at both faces', 0)], value=int(value))
                elif unit == 'bar':
                    control = W.Dropdown(options=[(f'#{b}', b) for b in BAR_SIZES], value=int(value))
                elif isinstance(value, int) and unit is None and name in ('n_int', 'N_brg', 'N_pile'):
                    control = W.BoundedIntText(value=int(value), min=1, max=50)
                else:
                    control = W.FloatText(value=float(value), step=0.25)
                label = spec['caption'] + (f' ({UNIT_LABELS.get(unit, unit)})' if unit not in (None, 'bar') else '')
                control.description = label
                control.style.description_width = '250px'
                control.layout = W.Layout(width='400px', max_width='calc(100% - 4px)', min_height='30px', height='auto')
                control.add_class('ebw-input')
                _tooltip(control, f'{name} · {spec["source"]} ({spec["status"]})')
                control.observe(partial(self._changed, name), names='value')
                self.controls[name] = control
                controls.append(control)
            tabs.append(W.HBox(controls, layout=W.Layout(width='100%', flex_flow='row wrap', grid_gap='4px 16px', padding='8px',
                                                          border='1px solid #c4cdd6')))
        tab = Tab(children=tabs, layout=W.Layout(width='100%'))
        for i, g in enumerate(GROUPS):
            tab.set_title(i, g)
        return tab

    def _sync_controls(self):
        self.busy = True
        try:
            for name, control in self.controls.items():
                value = self.case['inputs'][name]
                control.value = int(value) if isinstance(control, (W.Dropdown, W.BoundedIntText)) else float(value)
        finally:
            self.busy = False

    def _changed(self, name, change):
        if self.busy:
            return
        old = self.case['inputs'][name]
        edit_input(self.case, name, change['new'])
        self._sync_controls()
        src = self.case['sources'][name]
        if src['status'] != 'edited in notebook':
            src['source'] = f'Edited in notebook (was {old:g}: {src["source"]})'
            src['status'] = 'edited in notebook'
        self.refresh_sources()
        self._mark_dirty()

    def _mark_dirty(self):
        try:
            validate_case(self.case)
        except ValueError as exc:
            self.recalc.set_state('invalid')
            self.banner.value = notice_html('CHECK INPUTS', html.escape(str(exc)), 'error')
            return
        self.recalc.set_state('dirty')
        self.banner.value = notice_html('RESULTS OUT OF DATE · RECALC NEEDED',
                                        'Inputs, sources or confirmations changed. Click <b>Recalc</b> to update drawings, checks and exports.', 'pending')
        for button in self.export_buttons:
            button.disabled = True

    def recalculate(self, _=None):
        self.recalc.set_state('running')
        try:
            self.e = evaluate(self.case)
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
    def _figure(self, fig):
        widget = FigureWidget(fig)
        widget.prepare_display()
        return widget

    @staticmethod
    def _replace(box, children):
        """Swap a result panel's contents and close the replaced chart widgets."""
        old = [c for c in box.children if isinstance(c, FigureWidget)]
        box.children = children
        for widget in old:
            if widget not in children:
                widget.close()

    def _render_all(self):
        e = self.e
        failed = [c for c in e.checks if 'FAIL' in c.status]
        pending = [c for c in e.checks if 'PENDING' in c.status]
        kind = 'error' if failed else 'pending' if pending else 'success'
        worst = max(COMBINATIONS, key=lambda c: e.value('V_pile_' + c['key']))
        self.banner.value = notice_html(
            'CALC DONE · ' + e.status.upper(),
            f'Tie-back load per foot of backwall: <b>service {e.value("f_str_s"):.2f} kip/ft · factored {e.value("f_str_u"):.2f} kip/ft</b> '
            f'(strap {e.value("z_strap", "ft"):.2f} ft above the cap top).<br>'
            f'Largest numerical check ratio: <b>{e.strength_dc:.3f}</b> · backwall fill / span face φMn {e.value("M_r_FF"):.2f} / {e.value("M_r_SF"):.2f} kip-ft per ft · '
            f'cap torsion screen {e.cap["torsion_max"]:.1f} / {e.value("T_lim"):.1f} kip-ft.<br>'
            + (f'Pile-head force for equilibrium up to <b>{e.value("V_pile_" + worst["key"]):.1f} kip</b> ({html.escape(worst["label"])}); '
               'raise the strap toward the resultant to reduce it.' if e.value('V_pile_' + worst['key']) > 0.5 else 'Strap at or above the resultant height.'), kind)
        self._replace(self.boxes['drawings'], [self._figure(visuals.section_figure(e)), self._figure(visuals.plan_figure(e)),
                                           self._figure(visuals.reinforcement_figure(e))])
        self._render_strap()
        self._replace(self.boxes['backwall'], [self._figure(visuals.backwall_figure(e)), W.HTML(self._group_table('Backwall'))])
        self._replace(self.boxes['cheek'], [self._figure(visuals.cheek_figure(e)), W.HTML(self._group_table('Cheek walls'))])
        cap = W.HTML(STYLE + f'<p>Torsion and weak-axis bending are not in the FBMP cap model. Maximum strength torsion '
                     f'<b>{e.cap["torsion_max"]:.2f} kip-ft</b> ({html.escape(e.cap["torsion_combo"])}) vs 0.25 φ Tcr = {e.value("T_lim"):.2f} kip-ft; '
                     f'maximum weak-axis moment {e.cap["weak_max"]:.2f} kip-ft. Added gravity load on the cap: backwall {e.value("w_bw"):.3f} klf, '
                     f'landing slab DC {e.value("w_sl_DC"):.3f} klf and PL {e.value("w_sl_PL"):.3f} klf at {abs(e.value("t_bw", "in") / 2 - e.value("b_cap", "in") / 2):.1f} in '
                     'behind the cap centerline.</p>')
        self._replace(self.boxes['cap'], [self._figure(visuals.cap_figure(e)), cap])
        self._render_checks()
        self._render_equations()
        self._refresh_review_options()

    def _render_strap(self):
        if self.e is None:
            return
        e, key = self.e, self.strap_combo.value
        rows = ''.join(
            f'<tr><td>{html.escape(r["label"])}</td><td>{"H" if r["kind"] == "H" else "V"}</td><td class="ebw-num">{r["force_kip"]:.2f}</td>'
            f'<td class="ebw-num">{r["arm_ft"]:.3f}</td><td class="ebw-num">{r["factor"]:g}</td><td class="ebw-num">{r["factored_moment"]:.2f}</td>'
            f'<td>{html.escape(r["basis"])}</td></tr>' for r in strap_table(e, key))
        table = (STYLE + '<table class="ebw-table"><tr><th>Load</th><th>Dir.</th><th>Force (kip)</th><th>Arm (ft)</th><th>γ</th><th>γ·M (kip-ft)</th><th>Factor basis</th></tr>'
                 + rows + f'<tr><th colspan="2">Totals</th><th class="ebw-num">H = {e.value("H_" + key):.2f}</th><th class="ebw-num">e = {e.value("e_" + key, "ft"):.3f}</th>'
                 f'<th></th><th class="ebw-num">M = {e.value("M_" + key):.2f}</th><th>F = max(H, M/y) = {e.value("F_str_" + key):.2f} kip → '
                 f'{e.value("f_str_" + key):.3f} kip/ft; pile force {e.value("V_pile_" + key):.2f} kip</th></tr></table>'
                 f'<p><b>Plans (SDM 12.3.F):</b> service {e.value("f_str_s"):.2f} kip/ft, factored {e.value("f_str_u"):.2f} kip/ft along the backwall. '
                 f'Plan note: <i>{html.escape(exports.PLAN_NOTE)}</i></p>')
        self._replace(self.boxes['strap'], [self.strap_combo, self._figure(visuals.waterfall_figure(e, key)), W.HTML(table),
                                        self._figure(visuals.strap_figure(e))])

    def _group_table(self, group):
        rows = ''.join(f'<tr><td>{html.escape(c.label)}</td><td>{html.escape(c.demand)}</td><td>{html.escape(c.capacity)}</td>'
                       f'<td class="ebw-num">{"" if c.ratio is None else f"{c.ratio:.3f}"}</td><td>{self._status(c.status)}</td></tr>'
                       for c in self.e.checks if c.group == group)
        return STYLE + '<table class="ebw-table"><tr><th>Check</th><th>Demand</th><th>Capacity / limit</th><th>Ratio</th><th>Status</th></tr>' + rows + '</table>'

    @staticmethod
    def _status(status):
        color = '#bb3e39' if 'FAIL' in status else '#a06500' if 'PENDING' in status else '#17633b' if 'PASS' in status else '#245674'
        return f'<b style="color:{color}">{html.escape(status)}</b>'

    def _render_checks(self):
        if self.e is None:
            return
        e, view = self.e, self.check_view.value
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
            refs = '; '.join(f'{REFERENCES[k]["code"]} {REFERENCES[k]["article"]} — {REFERENCES[k]["governs"]}' for k in c.refs if k in REFERENCES)
            eqs = ''.join(f'<div class="ebw-eq">{trace[n]["mathml"]}</div>' for n in c.names if n in trace)
            body = (f'<p><b>Basis:</b> {html.escape(c.basis)}</p>' + (f'<p><b>Code:</b> {html.escape(refs)}</p>' if refs else '') + eqs
                    + (f'<p><i>{html.escape(c.note)}</i></p>' if c.note else ''))
            rows.append(f'<tr><td>{html.escape(c.group)}</td><td>{html.escape(c.label)}{review_html(c)}<details class="ebw"><summary>Equation &amp; values</summary>{body}</details></td>'
                        f'<td>{html.escape(c.demand)}</td><td>{html.escape(c.capacity)}</td><td class="ebw-num">{"" if c.ratio is None else f"{c.ratio:.3f}"}</td>'
                        f'<td>{self._status(c.status)}</td></tr>')
        register = (STYLE + f'<p><b>{html.escape(e.status)}</b> · showing {len(checks)} of {len(e.checks)}</p><table class="ebw-table"><tr><th>Group</th><th>Check</th>'
                    '<th>Demand / required</th><th>Capacity / limit</th><th>Ratio</th><th>Status</th></tr>' + ''.join(rows) + '</table>')
        self._replace(self.boxes['checks'], [self._figure(visuals.ratios_figure(e)), self.review_ui, self.check_view,
                                         W.HTML(register, layout=W.Layout(max_height='900px', overflow='auto'))])

    def _render_equations(self):
        e = self.e
        trace = formula_trace(e)
        parts = []
        for key, heading in SECTIONS:
            items = [t for t in trace if t['section'] == key]
            body = ''.join(f'<p class="ebw-cap">{html.escape(t["caption"])}</p><div class="ebw-eq">{t["mathml"]}</div>' for t in items)
            parts.append(f'<details class="ebw"{" open" if key == "earth" else ""}><summary><b>{html.escape(heading)}</b> · {len(items)} equations</summary>{body}</details>')
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
        panel = W.VBox([W.HBox([self.review_check, self.review_by], layout=W.Layout(flex_flow='row wrap')), self.review_reason,
                        W.HBox(buttons), self.review_status])
        self.review_ui = Accordion(children=[panel]); self.review_ui.set_title(0, 'Record a closure or override')
        self.review_ui.selected_index = None

    def _refresh_review_options(self):
        self.review_check.options = [(f'{c.group} · {c.label} [{c.status}]', c.key) for c in self.e.checks]

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
        self.export_status = W.HTML(); self.download_output = W.Output()
        specs = [('Case JSON', 'backwall_case.json'), ('Calculation report', 'backwall_calculation_report.html'),
                 ('Checks CSV', 'backwall_checks.csv'), ('MSE strap handoff (xlsx)', 'backwall_strap_handoff.xlsx'),
                 ('Export distilled Blockpad (.bpad)', exports.DISTILLED_BPAD), ('Full bundle ZIP', 'backwall_bundle.zip')]
        self.export_buttons = []
        for label, name in specs:
            b = W.Button(description=label, icon='copy' if name == exports.DISTILLED_BPAD else 'download',
                         layout=W.Layout(width='270px' if name == exports.DISTILLED_BPAD else '230px'))
            b.on_click(partial(self._export, name)); self.export_buttons.append(b)
        self.boxes['exports'].children = [
            W.HTML('<p>Exports use the last completed Recalc. Each click writes a timestamped folder under <code>exports/</code> and downloads the file. '
                   'In Colab, <code>/content</code> is temporary runtime storage; keep the downloaded copies.</p>'
                   '<p><b>Export distilled Blockpad (.bpad)</b> writes a standalone Blockpad document of the current case (the same distilled '
                   'sheet as <code>end_bent_walls/End Bent Backwall Design.bpad</code>: equations shown once, collapsed sections, live figures), '
                   'verified against this notebook before it is written; its verification record is saved beside it and in the bundle. '
                   'Open and recalculate the sheet in Blockpad. It distils the numerical checks only; it is not design acceptance.</p>'),
            W.HBox(self.export_buttons, layout=W.Layout(flex_flow='row wrap', grid_gap='6px')), self.export_status, self.download_output]

    def _export(self, name, _=None):
        if self.e is None:
            return
        try:
            path = exports.export_file(self.e, self.export_root, name)
        except Exception as exc:
            self.export_status.value = notice_html('EXPORT FAILED', html.escape(str(exc)), 'error')
            return
        self.last_files[name] = path
        detail = f'<code>{html.escape(str(path.resolve()))}</code>'
        if name == exports.DISTILLED_BPAD:
            verification = path.parent / exports.BPAD_VERIFICATION
            detail = (html.escape(exports.bpad_summary(verification.read_bytes())) + '<br>' + detail +
                      f'<br>Verification record: <code>{html.escape(str(verification.resolve()))}</code>')
        self.export_status.value = notice_html('DISTILLED BLOCKPAD READY' if name == exports.DISTILLED_BPAD else 'EXPORT WRITTEN', detail, 'success')
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
