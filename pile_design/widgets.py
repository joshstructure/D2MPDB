"""Jupyter / Colab interface for the pile analysis and design calculation."""
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
from .model import (default_case, upgrade_case, validate_case, evaluate, edit_input, select_psc, reconcile_confirmations, INPUT_SPEC, INPUTS,
                    CONFIRMATIONS, PIPE_ONLY, SECTIONS, PRESETS, STANDARD_PLANS, REFERENCES, formula_trace)
from .reviews import record_review, reopen, review_html
from .sources import apply_source
from . import exports, visuals

STATUS_COLORS = {'project source': '#17633b', 'decision': '#245674', 'code': '#485969', 'provisional geometry': '#805600',
                 'pending confirmation': '#a06500', 'trial': '#485969', 'differs from register': '#9d302b', 'edited in notebook': '#7a3e9d'}
FAMILY_OPTIONS = [('Square prestressed concrete (FDOT Standard Plans Index 455)', 'psc'), ('Steel pipe (ASTM A252 Gr 3 / API 5L)', 'pipe')]
STYLE = '''<style>
.pdn-input .widget-label{white-space:normal!important;line-height:1.2!important;height:auto!important}
.ebw-table{border-collapse:collapse;width:100%;font:12px Arial}.ebw-table td,.ebw-table th{padding:6px 8px;border-bottom:1px solid #dce5ec;text-align:left;vertical-align:top}
.ebw-table th{background:#e7eef4;position:sticky;top:0}.ebw-num{text-align:right;font-variant-numeric:tabular-nums}
.ebw-eq{overflow-x:auto;padding:4px 0}.ebw-eq math{font-size:14px}.ebw-cap{color:#485969;font-size:12px;margin:8px 0 0}
.ebw-review{margin:4px 0;padding:4px 6px;background:#fff3d6;border-left:3px solid #805600;font-size:11px}
details.ebw>summary{cursor:pointer;color:#245c85;font-size:12px}
</style>'''
REPORT_VIEWS = [('Governing records', 'governing'), ('Pile-head records', 'heads'), ('All strength records (first 400)', 'strength'),
                ('All service records (first 400)', 'service')]

PSC_NAMES = {
    'section': ['A_g', 'I_g', 'S_g', 'A_ps', 'f_pj', 'f_pe', 'P_e', 'f_pc_eff', 'beta_1', 'E_c', 'k_c', 'eps_pe', 'eps_ce'],
    'interaction': ['P_o', 'P_n_max', 'P_r_max', 'P_bi_lim', 'DC_bi', 'DC_rs', 'M_r_P0', 'M_splice'],
    'shear': ['b_v', 'd_v', 'V_u_sh', 'M_u_sh', 'P_u_sh', 'A_ps_t', 'd_e', 'eps_s', 'beta_v', 'theta_v', 'A_v', 'A_v_min', 'V_c', 'V_s', 'V_n', 'V_r'],
    'tension': ['T_u', 'P_n_t', 'P_r_t', 'P_t_yield', 'DC_t'],
    'service': ['sig_c', 'sig_c_lim', 'sig_t', 'f_t_net', 'f_t_lim', 'f_pc_eff', 'f_pc_min', 'D_min'],
}
PIPE_NAMES = {
    'section': ['t_des', 'D_i', 'A_g', 'I_g', 'S_g', 'Z_p', 'r_g', 'D_t', 'lam_r', 'lam_p', 'lam_nc'],
    'interaction': ['A_eff', 'P_o', 'E_soil', 'L_fix', 'KL', 'KL_r', 'P_e', 'Pe_Po', 'P_n', 'P_r_axial', 'P_r_comb', 'M_p', 'M_n', 'M_r',
                    'P_abs', 'P_rc', 'Pu_Pr', 'DC_comb'],
    'shear': ['L_v', 'F_cr1', 'F_cr2', 'F_cr', 'V_u_sh', 'V_n', 'V_r'],
    'tension': ['T_u', 'P_r_t', 'DC_t'],
}


def _tooltip(control, text):
    for attr in ('tooltip', 'description_tooltip'):
        if attr in control.keys:
            setattr(control, attr, text)


def _parse_optional(text):
    """Blank or N/A means the value is not applicable (None); otherwise a number."""
    cleaned = (text or '').strip().lower()
    if cleaned in ('', 'n/a', 'na', 'none', '-'):
        return None
    return float(cleaned)


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
                self.button.metadata = []
                self.button.data = []
                self.button._counter = 0
            else:
                self.button.value = ()

    def _colab(self, _=None):
        from IPython.display import clear_output
        self.output.layout.display = ''
        try:
            with self.output:
                clear_output(wait=True)
                with TemporaryDirectory(prefix='pile-upload-') as folder:
                    received = self.files.upload(target_dir=folder)
                clear_output(wait=False)
            if received:
                name, content = next(iter(received.items()))
                self.callback(content, Path(name).name)
        finally:
            self.output.layout.display = 'none'


class PileNotebook:
    def __init__(self, case=None, export_root='exports'):
        self.case = upgrade_case(case or default_case())
        self.export_root = Path(export_root)
        self.e = None
        self.busy = False
        self.controls = {}
        self.control_specs = {}
        self.last_files = {}
        self._pending_action = None
        self.message = W.HTML()
        self._build_sources()
        self._build_design()
        self.refresh_sources()
        self._sync_controls()
        self.recalculate()

    # ---------------------------------------------------------------- sources
    def _build_sources(self):
        self.xml_status = W.HTML()
        self.cap_status = W.HTML()
        self.xml_upload = UploadControl('Load FBMP pile XML', '.xml,.XML', partial(self._load_source, 'FBMP-XML'))
        self.cap_upload = UploadControl('Load cap case JSON', '.json,.JSON', partial(self._load_source, 'EB-CASE'))
        self.case_status = W.HTML()
        self.case_upload = UploadControl('Load pile case JSON', '.json,.JSON', self._load_case)
        self.preset_dd = W.Dropdown(options=list(PRESETS), value=self.case['support'], description='Support', layout=W.Layout(width='260px'))
        preset_btn = W.Button(description='Load preset', icon='download', layout=W.Layout(width='160px'),
                              tooltip='Replace every input with the registered preset for the chosen support')
        preset_btn.on_click(self._ask_preset)
        reset = W.Button(description='Reset to registered defaults', icon='undo', layout=W.Layout(width='240px'))
        reset.on_click(self._ask_reset)
        self.ask_text = W.HTML()
        self.ask_yes = W.Button(description='Confirm', button_style='danger', icon='check', layout=W.Layout(width='130px'))
        self.ask_no = W.Button(description='Cancel', icon='times', layout=W.Layout(width='130px'))
        self.ask_yes.on_click(self._ask_yes)
        self.ask_no.on_click(self._ask_no)
        self.ask_box = W.VBox([self.ask_text, W.HBox([self.ask_yes, self.ask_no], layout=W.Layout(grid_gap='8px'))], layout=W.Layout(display='none'))
        self.confirm, self.confirm_notes, self.confirm_rows = {}, {}, {}
        for key, text in CONFIRMATIONS.items():
            box = W.Checkbox(value=bool(self.case['confirmations'].get(key)), description=text, indent=False, layout=W.Layout(width='100%'))
            box.observe(partial(self._confirmed, key), names='value')
            self.confirm[key] = box
            self.confirm_notes[key] = W.HTML()
            self.confirm_rows[key] = W.VBox([box, self.confirm_notes[key]])
        self.sources_table = W.HTML(layout=W.Layout(max_height='520px', overflow='auto'))
        cards = [
            W.VBox([W.HTML('<b>FB-MultiPier pile export (XML)</b><br><small>Pile forces, section and soil tops. Re-read on every upload; the registered exports (EB-XML, EB2-XML, PIER-XML from '
                           '<code>project_current/fbmp/</code>) are embedded and loaded with each preset.</small>'), self.xml_upload.button, self.xml_upload.output, self.xml_status],
                    layout=W.Layout(flex='1 1 340px', min_width='300px', padding='8px', border='1px solid #c4cdd6')),
            W.VBox([W.HTML('<b>Saved cap case (optional)</b><br><small>Pile count, spacing, size and embedment from '
                           '<code>project_current/cap_design/&lt;support&gt;/selected_case.json</code>.</small>'), self.cap_upload.button, self.cap_upload.output, self.cap_status],
                    layout=W.Layout(flex='1 1 340px', min_width='300px', padding='8px', border='1px solid #c4cdd6'))]
        details = Accordion(children=[self.sources_table])
        details.set_title(0, 'Every input · value, source and status')
        details.selected_index = None
        self.sources_ui = W.VBox([
            W.HTML(STYLE + '<h2 style="color:#213649;margin-bottom:4px">1. Project sources and assumptions</h2>'
                   '<p>Choose the support to analyze (End Bent 1, End Bent 2 or Pier). The registered FB-MultiPier export for each support is embedded and loaded with its preset; '
                   'upload a newer XML below to replace it. An uploaded file is compared by SHA-256 with the source register; a different file is reported, never silently adopted. '
                   'Downdrag of 18 tons per end-bent pile (geotechnical engineer, 2026-10-19) is added as a drag load.</p>'),
            W.HBox([self.preset_dd, preset_btn, reset], layout=W.Layout(flex_flow='row wrap', grid_gap='8px')), self.ask_box,
            W.HBox(cards, layout=W.Layout(width='100%', flex_flow='row wrap', grid_gap='8px')),
            W.HBox([self.case_upload.button], layout=W.Layout(flex_flow='row wrap', grid_gap='8px')), self.case_upload.output, self.case_status,
            W.HTML('<h3>Confirmations</h3><p>Checked items carry dated project evidence below. Unconfirmed items remain <b>PENDING</b>. '
                   'Editing a reviewed value reopens its confirmation. Source consistency does not close the connection, driving or geotechnical review.</p>'),
            W.VBox(list(self.confirm_rows.values())), details])

    def _ask(self, text, action):
        self._pending_action = action
        self.ask_text.value = notice_html('CONFIRM', text, 'pending')
        self.ask_box.layout.display = ''

    def _ask_preset(self, _=None):
        support = self.preset_dd.value
        self._ask(f'Replace every input, source, confirmation and review with the registered preset for <b>{html.escape(support)}</b>? '
                  'Unsaved edits in this notebook are lost; export the case first to keep them.', lambda: self.load(default_case(support), f'preset {support}'))

    def _ask_reset(self, _=None):
        support = self.case['support']
        self._ask(f'Reset <b>{html.escape(support)}</b> to its registered defaults? Edits, confirmations and reviews are discarded.',
                  lambda: self.load(default_case(support), 'registered defaults'))

    def _ask_yes(self, _=None):
        action, self._pending_action = self._pending_action, None
        self.ask_box.layout.display = 'none'
        if action:
            action()

    def _ask_no(self, _=None):
        self._pending_action = None
        self.ask_box.layout.display = 'none'

    def _load_source(self, sid, content, filename):
        status = self.xml_status if sid == 'FBMP-XML' else self.cap_status
        try:
            trial = deepcopy(self.case)
            apply_source(trial, sid, content, filename)
        except Exception as exc:
            status.value = notice_html('SOURCE NOT APPLIED', html.escape(f'{filename}: {exc}'), 'error')
            return
        if sid == 'FBMP-XML':
            keep = trial['analysis']['sha256']
            for key in [k for k, r in trial['receipts'].items() if not k.endswith('CASE') and r['sha256'] != keep]:
                del trial['receipts'][key]
        self.case = trial
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
        self.busy = True
        try:
            self.preset_dd.value = self.case['support']
        finally:
            self.busy = False
        self._sync_controls()
        self.case_status.value = notice_html('CASE LOADED', f'<b>{html.escape(label)}</b> · {datetime.now(timezone.utc):%H:%M:%S UTC}. '
                                             'Inputs, sources, confirmations and reviews restored.', 'success')
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

    @staticmethod
    def _receipt_html(r):
        kind = 'success' if r['matches_register'] else 'pending'
        title = (f'MATCHES SOURCE REGISTER · {r["source_id"]}' if r['matches_register'] else 'DIFFERS FROM SOURCE REGISTER')
        notes = ''.join(f'<br>• {html.escape(n)}' for n in r.get('notes', []))
        return notice_html(title, f'<b>{html.escape(r["filename"])}</b> · {html.escape(r["loaded_utc"])}<br>'
                                  f'SHA-256 <code>{r["sha256"][:16]}…</code><br>Applied: {html.escape(", ".join(r.get("applied", [])))}{notes}', kind)

    def refresh_sources(self):
        self.busy = True
        try:
            for key, box in self.confirm.items():
                box.value = bool(self.case['confirmations'].get(key))
                evidence = self.case.get('confirmation_evidence', {}).get(key, {})
                self.confirm_notes[key].value = '<div style="margin:0 12px 10px;color:#485969;font-size:12px">' + (
                    '<b>Needs review after input changes. </b>' if evidence.get('stale') else '') + html.escape(
                    evidence.get('note', 'No project evidence recorded in this saved case.')) + '</div>'
                self.confirm_rows[key].layout.display = 'none' if key in PIPE_ONLY and self.case['family'] != 'pipe' else ''
        finally:
            self.busy = False
        receipts = self.case.get('receipts', {})
        analysis = self.case.get('analysis')
        if not analysis:
            self.xml_status.value = notice_html('NO FBMP RESULTS LOADED', 'The pile demand records come from the FB-MultiPier XML. Upload the export for this support; '
                                                'until then the checks that need demands are reported as pending.', 'pending')
        else:
            receipt = next((r for r in receipts.values() if r['sha256'] == analysis['sha256']), None)
            summary = (f'<br>{analysis["piles"]} piles · {len(analysis["records"])} records · combinations: '
                       + html.escape(', '.join(f'{k} {v}' for k, v in analysis['combinations'].items())))
            self.xml_status.value = (self._receipt_html(receipt).replace('</div>', summary + '</div>') if receipt else
                                     notice_html('FBMP RESULTS LOADED', f'<b>{html.escape(analysis["filename"])}</b> · SHA-256 <code>{analysis["sha256"][:16]}…</code>' + summary))
        cap = [r for k, r in receipts.items() if k.endswith('CASE')]
        self.cap_status.value = self._receipt_html(cap[-1]) if cap else notice_html('NO CAP CASE LOADED', 'Pile count, spacing and size come from the FBMP export.')
        rows = []
        family = self.case['family']
        for spec in INPUT_SPEC:
            name = spec['name']
            src = self.case['sources'][name]
            color = STATUS_COLORS.get(src['status'], '#485969')
            active = spec['family'] in ('both', family)
            unit = visuals.unit_label(spec['unit'])
            value = visuals.input_text(name, self.case['inputs'].get(name))
            style = '' if active else ' style="opacity:.45"'
            rows.append(f'<tr{style}><td>{html.escape(spec["group"])}</td><td>{html.escape(spec["caption"])}{"" if active else " (not used by this family)"}</td>'
                        f'<td class="ebw-num">{html.escape(value)} {html.escape(unit)}</td>'
                        f'<td>{html.escape(src["source"])}</td><td style="color:{color};font-weight:600">{html.escape(src["status"])}</td></tr>')
        self.sources_table.value = (STYLE + '<table class="ebw-table"><tr><th>Group</th><th>Input</th><th>Value</th><th>Source / basis</th><th>Status</th></tr>'
                                    + ''.join(rows) + '</table>')

    # ----------------------------------------------------------------- design
    def _build_design(self):
        self.recalc = RecalcControl(self.recalculate)
        self.banner = W.HTML()
        self.family_dd = W.Dropdown(options=FAMILY_OPTIONS, value=self.case['family'], description='Pile family', layout=W.Layout(width='520px'))
        self.family_dd.style.description_width = '90px'
        self.family_dd.observe(self._family_changed, names='value')
        self.index_dd = W.Dropdown(options=[(f'{k} · {v["size_in"]:g} in square', k) for k, v in STANDARD_PLANS['indexes'].items()],
                                   value=self.case['psc']['index'], description='Standard Plans', layout=W.Layout(width='320px'))
        self.index_dd.style.description_width = '110px'
        self.pattern_dd = W.Dropdown(options=self._pattern_options(self.case['psc']['index']), value=self.case['psc']['pattern'],
                                     description='Strand pattern', layout=W.Layout(width='400px'))
        self.pattern_dd.style.description_width = '100px'
        self.index_dd.observe(self._index_changed, names='value')
        self.pattern_dd.observe(self._pattern_changed, names='value')
        self.psc_row = W.HBox([self.index_dd, self.pattern_dd], layout=W.Layout(flex_flow='row wrap', grid_gap='8px'))
        self.family_info = W.HTML()
        self.input_tabs = Tab(children=[], layout=W.Layout(width='100%'))
        self.input_boxes = self._inputs()
        self.boxes = {name: W.VBox(layout=W.Layout(width='100%', min_width='0')) for name in
                      ('section', 'demands', 'interaction', 'shear', 'table', 'checks', 'equations', 'exports')}
        self.record_view = W.Dropdown(options=REPORT_VIEWS, value='governing', description='Records', layout=W.Layout(width='360px'))
        self.record_view.observe(lambda _: self._render_demands(), names='value')
        self.check_view = W.Dropdown(options=[('All checks', 'all'), ('Largest ratio first', 'ratio'), ('Failures first', 'failures'),
                                              ('Pending only', 'pending'), ('Reviewed checks', 'reviewed')], value='all', description='View',
                                     layout=W.Layout(width='280px'))
        self.check_view.observe(lambda _: self._render_checks(), names='value')
        self._build_review_panel()
        self._build_export_panel()
        titles = ['Section', 'Demands', 'Interaction', 'Shear & service', 'Pile Data Table', 'D/C checks', 'Equations', 'Exports']
        self.result_tabs = Tab(children=[self.boxes[k] for k in ('section', 'demands', 'interaction', 'shear', 'table', 'checks', 'equations', 'exports')],
                               layout=W.Layout(width='100%', min_width='0'))
        for i, t in enumerate(titles):
            self.result_tabs.set_title(i, t)
        header = W.HTML(STYLE + '<h2 style="color:#213649;margin-bottom:4px;padding-right:170px">2. Pile analysis and design</h2>'
                        '<p>Choose the pile family and, for prestressed concrete, the Standard Plans option. Edit inputs in the cards, then click <b>Recalc</b> at the top right. '
                        'Results, figures, the check register and exports always describe the last completed Recalc.</p>')
        inputs = W.VBox([W.HTML('<h3>Inputs</h3>'), self.family_dd, self.psc_row, self.family_info, self.input_tabs], layout=W.Layout(width='100%'))
        self.design_ui = self.recalc.wrap([header, self.banner, inputs, self.result_tabs, self.message])

    @staticmethod
    def _pattern_options(index):
        return [(f'{o["label"]} · jack {o["jacking_kip"]:g} kip/strand', o['id']) for o in STANDARD_PLANS['indexes'][index]['options']]

    @staticmethod
    def _option_pairs(spec, current):
        """Dropdown (label, value) pairs from an input's `options` map; a value outside the map is kept as 'custom'."""
        integer = isinstance(spec['value'], int) and not isinstance(spec['value'], bool)
        pairs = []
        for key, label in spec['options'].items():
            value = int(key) if integer else float(key)
            pairs.append((label if integer else f'{key} · {label}', value))
        if current is not None and all(abs(current - v) > 1e-9 for _, v in pairs):
            pairs.append((f'{current:g} (custom)', current))
        return pairs

    def _control(self, spec):
        name, unit = spec['name'], spec['unit']
        value = self.case['inputs'].get(name)
        if spec.get('options'):
            pairs = self._option_pairs(spec, value)
            control = W.Dropdown(options=pairs, value=value if value is not None else pairs[0][1])
        elif spec.get('optional'):
            control = W.Text(value='' if value is None else f'{value:g}', placeholder='blank = N/A', continuous_update=False)
        elif isinstance(spec['value'], int) and not isinstance(spec['value'], bool):
            lo, hi = (1, 50) if name == 'N_pile' else (21, 401)
            control = W.BoundedIntText(value=int(value), min=lo, max=hi)
        else:
            control = W.FloatText(value=float(value), step=0.25)
        label = spec['caption'] + (f' ({visuals.unit_label(unit)})' if unit not in (None, 'bar') else '')
        control.description = label
        control.style.description_width = '250px'
        control.layout = W.Layout(width='400px', max_width='calc(100% - 4px)', min_height='30px', height='auto')
        control.add_class('pdn-input')
        _tooltip(control, f'{name} · {spec["source"]} ({spec["status"]})')
        control.observe(partial(self._changed, name), names='value')
        return control

    def _inputs(self):
        """Build every input control once, grouped; _apply_family shows the groups and fields of the chosen family."""
        groups = list(dict.fromkeys(s['group'] for s in INPUT_SPEC))
        self.group_boxes = {}
        self.group_members = {}
        for group in groups:
            controls = []
            self.group_members[group] = []
            for spec in (s for s in INPUT_SPEC if s['group'] == group):
                control = self._control(spec)
                self.controls[spec['name']] = control
                self.control_specs[spec['name']] = spec
                self.group_members[group].append((spec, control))
                controls.append(control)
            self.group_boxes[group] = W.HBox(controls, layout=W.Layout(width='100%', flex_flow='row wrap', grid_gap='4px 16px', padding='8px',
                                                                        border='1px solid #c4cdd6'))
        return self.group_boxes

    def _apply_family(self):
        """Show the input tabs and fields of the selected family; D_pile follows the Standard Plans index or D_out."""
        family = self.case['family']
        visible = []
        for group, box in self.group_boxes.items():
            used = False
            for spec, control in self.group_members[group]:
                show = spec['family'] in ('both', family)
                control.layout.display = '' if show else 'none'
                used = used or show
            if used:
                visible.append(group)
        shown = [self.group_boxes[g] for g in visible]
        if list(self.input_tabs.children) != shown:
            self.input_tabs.children = shown
            for i, g in enumerate(visible):
                self.input_tabs.set_title(i, g)
        self.controls['D_pile'].disabled = True
        self.controls['D_pile'].description = ('Pile size (set by the Standard Plans index)' if family == 'psc' else 'Pile size (follows the pipe outside diameter)')
        self.psc_row.layout.display = '' if family == 'psc' else 'none'
        analysis = self.case.get('analysis')
        p = self.case['inputs']
        if family == 'psc':
            plan = STANDARD_PLANS['indexes'][self.case['psc']['index']]
            option = next(o for o in plan['options'] if o['id'] == self.case['psc']['pattern'])
            info = (f'Index {self.case["psc"]["index"]}: {plan["size_in"]:g} in square · spiral {plan["spiral_wire"]} ({plan["spiral_note"]}) · dowels {plan["dowels"]}'
                    f'{f" · {plan["void_in"]:g} in void" if plan["void_in"] else ""}<br>Pattern {option["label"]}: {option["count"]} strands × {option["strand_area_in2"]:g} in² '
                    f'= {option["count"] * option["strand_area_in2"]:.3f} in², jacking {option["jacking_kip"]:g} kip per strand.')
        else:
            t_des = p['t_wall'] - p['t_corr']
            info = (f'Pipe {p["D_out"]:g} in × {p["t_wall"]:g} in wall (design {t_des:g} in): D/t = {p["D_out"] / t_des:.2f} '
                    f'(nonslender below 0.11E/Fy = {0.11 * p["E_s"] / p["Fy"]:.1f}). Noncomposite; no concrete fill.')
        if analysis and analysis.get('family') != family:
            info += (f'<br><b>What-if:</b> the loaded FBMP forces were analyzed with a {"prestressed concrete" if analysis["family"] == "psc" else "steel pipe"} section; '
                     'they are reused for this family without a new analysis.')
        self.family_info.value = f'<div style="font-size:12px;color:#485969;margin:4px 0">{info}</div>'

    def _sync_controls(self):
        self.busy = True
        try:
            p = self.case['inputs']
            for name, control in self.controls.items():
                value = p.get(name)
                spec = self.control_specs[name]
                if isinstance(control, W.Dropdown):
                    control.options = self._option_pairs(spec, value)
                    control.value = value
                elif isinstance(control, W.Text):
                    control.value = '' if value is None else f'{value:g}'
                    control.layout.border = ''
                elif isinstance(control, W.BoundedIntText):
                    control.value = int(value)
                else:
                    control.value = float(value)
            self.family_dd.value = self.case['family']
            self.index_dd.value = self.case['psc']['index']
            self.pattern_dd.options = self._pattern_options(self.case['psc']['index'])
            self.pattern_dd.value = self.case['psc']['pattern']
            self._apply_family()
        finally:
            self.busy = False

    def _after_structure_edit(self):
        self._sync_controls()
        self.refresh_sources()
        self._mark_dirty()

    def _family_changed(self, change):
        if self.busy:
            return
        case, p = self.case, self.case['inputs']
        case['family'] = change['new']
        if change['new'] == 'pipe':
            p['D_pile'] = p['D_out']
            case['sources']['D_pile'] = {'source': 'Pipe outside diameter D_out', 'status': 'edited in notebook'}
        else:
            select_psc(case, case['psc']['index'], case['psc']['pattern'])
        reconcile_confirmations(case)
        self._after_structure_edit()

    def _index_changed(self, change):
        if self.busy:
            return
        select_psc(self.case, change['new'])
        reconcile_confirmations(self.case)
        self._after_structure_edit()

    def _pattern_changed(self, change):
        if self.busy:
            return
        select_psc(self.case, self.case['psc']['index'], change['new'])
        self._after_structure_edit()

    def _changed(self, name, change):
        if self.busy:
            return
        control, new = self.controls[name], change['new']
        if isinstance(control, W.Text):
            try:
                new = _parse_optional(new)
            except ValueError:
                control.layout.border = '2px solid #bb3e39'
                self.banner.value = notice_html('CHECK INPUTS', html.escape(f'{INPUTS[name]["caption"]}: enter a number, or leave blank for N/A.'), 'error')
                self.recalc.set_state('invalid')
                return
            control.layout.border = ''
        old = self.case['inputs'].get(name)
        edit_input(self.case, name, new)
        self._sync_controls()
        src = self.case['sources'][name]
        if src['status'] != 'edited in notebook':
            was = 'N/A' if old is None else f'{old:g}'
            src['source'] = f'Edited in notebook (was {was}: {src["source"]})'
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
                                        'Inputs, sources or confirmations changed. Click <b>Recalc</b> to update figures, checks and exports.', 'pending')
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

    @staticmethod
    def _status(status):
        color = '#bb3e39' if 'FAIL' in status else '#a06500' if 'PENDING' in status else '#17633b' if 'PASS' in status else '#245674'
        return f'<b style="color:{color}">{html.escape(status)}</b>'

    def _banner_html(self):
        e = self.e
        v, p = e.value, e.case['inputs']
        failed = [c for c in e.checks if 'FAIL' in c.status]
        pending = [c for c in e.checks if 'PENDING' in c.status]
        kind = 'error' if failed else 'pending' if pending else 'success'
        g, m = visuals.structural_governing_check(e), visuals.max_ratio_check(e)
        strength_dc = getattr(e, 'strength_dc', 0.0)
        max_ratio = getattr(e, 'max_ratio', strength_dc)
        lines = []
        if not e.records:
            lines.append('<b>No FBMP results are loaded</b>: upload the pile XML in Cell 1. Section properties and the demand-independent checks are shown.')
        lines.append(f'Governing structural D/C <b>{strength_dc:.3f}</b>' + (f' · {html.escape(g.label)}' if g else '')
                     + f' · largest ratio of any check <b>{max_ratio:.3f}</b>' + (f' · {html.escape(m.label)}' if m else '') + '.')
        nbr = f'Nominal Bearing Resistance (SDG Eq. 3-1): <b>{v("NBR_tons"):.1f} tons</b> required'
        if e.family == 'psc':
            nbr += f' against the Table 3.5.13-1 maximum of <b>{v("R_drive_tons"):.0f} tons</b> ({v("NBR_tons") / v("R_drive_tons"):.2f}).'
        else:
            nbr += ' (Table 3.5.13-1 gives no steel pipe limit).'
        lines.append(nbr)
        lines.append(f'Downdrag used: <b>{p["DD_tons"]:g} tons</b> per pile = {v("DD"):.1f} kip; structural drag load {v("DR_str"):.1f} kip at the strength limit states '
                     f'(γ {p["gamma_DR_str"]:g}), {v("DR_ser"):.1f} kip at Service I; not part of the Factored Design Load ({v("FDL_tons"):.1f} tons).')
        return notice_html('CALC DONE · ' + e.status.upper(), '<br>'.join(lines), kind)

    def _render_all(self):
        self.banner.value = self._banner_html()
        self._render_section()
        self._render_demands()
        self._render_interaction()
        self._render_shear()
        self._render_table()
        self._render_checks()
        self._render_equations()
        self._refresh_review_options()

    def _names(self, key):
        return (PSC_NAMES if self.e.family == 'psc' else PIPE_NAMES).get(key, [])

    def _qtable(self, names):
        return visuals.quantity_table_html(self.e, names)

    def _render_section(self):
        e = self.e
        if e.family == 'psc':
            plan, option = e.details['plan'], e.details['option']
            layout = ', '.join(f'({x:.2f}, {y:.2f})' for x, y in e.details['layout'])
            extra = (f'<p><b>Standard Plans Index {e.case["psc"]["index"]}</b> (FY 2026-27): {plan["size_in"]:g} in square, spiral {plan["spiral_wire"]} — {html.escape(plan["spiral_note"])}; '
                     f'dowels {html.escape(plan["dowels"])}. Pattern {html.escape(option["label"])}: {option["count"]} strands × {option["strand_area_in2"]:g} in², '
                     f'jacking {option["jacking_kip"]:g} kip. {html.escape(" ".join(plan.get("notes", [])))}</p>'
                     f'<details class="ebw"><summary>Strand coordinates (in, from the pile centroid)</summary><p>{html.escape(layout)}</p></details>')
        else:
            extra = '<p>Noncomposite steel pipe pile. The FBMP section properties are compared with the closed-form values in the inputs table of Cell 1.</p>'
        self._replace(self.boxes['section'], [self._figure(visuals.section_figure(e)), self._figure(visuals.elevation_figure(e)),
                                              W.HTML(STYLE + extra + self._qtable(self._names('section')))])

    def _records_for_view(self):
        e, view = self.e, self.record_view.value
        if view == 'heads':
            return [r for r in e.records if r['head']]
        if view == 'strength':
            return [r for r in e.records if r['limit'] == 'strength'][:400]
        if view == 'service':
            return [r for r in e.records if r['limit'] == 'service'][:400]
        return None

    def _render_demands(self):
        if self.e is None:
            return
        e, p = self.e, self.e.case['inputs']
        if not e.records:
            self._replace(self.boxes['demands'], [W.HTML(notice_html('NO FBMP RESULTS LOADED', 'Upload the pile XML in Cell 1, then Recalc.', 'pending'))])
            return
        top = (STYLE + f'<p>P<sub>u</sub> = P<sub>FBMP</sub> + γ<sub>DR</sub>·DD (compression positive). DD = {e.value("DD"):.1f} kip, γ<sub>DR</sub> = {p["gamma_DR_str"]:g} (strength) / '
               f'{p["gamma_DR_ser"]:g} (Service I), applied at every station (conservative below the neutral plane; LRFD Table 3.4.1-1, 10.7.3.7). '
               f'FBMP source: <b>{html.escape(e.case["analysis"]["filename"])}</b> · {e.details["strength_records"]} strength and {e.details["service_records"]} service records.</p>')
        records = self._records_for_view()
        table = visuals.governing_table_html(e) if records is None else visuals.records_table_html(records)
        env = e.details['envelope']
        head_rows = ''.join(
            f'<tr><td>{html.escape(state)}</td><td class="ebw-num">{x["max_compression_kip"]:.1f}</td><td class="ebw-num">{x["concurrent_M_res"]:.1f}</td>'
            f'<td class="ebw-num">{x["max_uplift_kip"]:.1f}</td><td class="ebw-num">{x["max_M_res"]:.1f}</td><td class="ebw-num">{x["max_V_res"]:.2f}</td></tr>' for state, x in env.items())
        head = ('<h4>Pile-head envelope by limit state (FBMP, before drag load)</h4><table class="ebw-table"><tr><th>Limit state</th><th>Max compression (kip)</th>'
                '<th>Concurrent M<sub>res</sub> (kip-ft)</th><th>Max uplift (kip)</th><th>Max M<sub>res</sub> (kip-ft)</th><th>Max V<sub>res</sub> (kip)</th></tr>' + head_rows + '</table>')
        self._replace(self.boxes['demands'], [W.HTML(top + head), self._figure(visuals.demand_profile_figure(e)),
                                              W.HTML(STYLE + '<h4>Envelope by combination</h4>' + visuals.combination_envelope_html(e)), self.record_view,
                                              W.HTML(STYLE + table, layout=W.Layout(max_height='600px', overflow='auto'))])

    def _render_interaction(self):
        e = self.e
        children = [self._figure(visuals.interaction_figure(e))]
        if e.family == 'psc':
            from .report import curve_table_html
            bi = e.details['biaxial']
            note = (f'<p>LRFD 5.6.4.5 route: Eq. {bi["method"]}, ratio <b>{bi["ratio"]:.3f}</b>. Resultant-axis route (strain-compatibility curve at {e.value("alpha_rs", "deg"):.1f}° '
                    f'from a face): ratio <b>{e.value("DC_rs"):.3f}</b>. The larger governs the check register. Pure compression is limited to φPn,max; φ varies between the '
                    'compression- and tension-controlled values (LRFD 5.5.4.2).</p>')
            tables = (curve_table_html(e.curve, 'Interaction curve, bending parallel to a face')
                      + curve_table_html(e.curve['resultant'], f'Interaction curve, axis at {e.curve["resultant_angle_deg"]:.1f}° (governing resultant)'))
            children.append(W.HTML(STYLE + note + self._qtable(self._names('interaction')) + tables.replace('<details>', '<details class="ebw">')))
        else:
            children.append(W.HTML(STYLE + '<p>Combined axial load and flexure by LRFD Eq. 6.9.2.2.1-1 / -2 with the resultant moment; the axial resistance for combined loading uses '
                                   'φc = ' + f'{e.case["inputs"]["phi_c_comb"]:g}' + '. Fixity depth follows LRFD C10.7.3.13.4.</p>' + self._qtable(self._names('interaction'))))
        self._replace(self.boxes['interaction'], children)

    def _render_shear(self):
        e = self.e
        if e.family == 'psc':
            html_ = (STYLE + '<h4>Shear · LRFD 5.7.3.4.2 general procedure (governing record)</h4>' + self._qtable(self._names('shear'))
                     + '<h4>Tension</h4>' + self._qtable(self._names('tension')) + '<h4>Service I stresses</h4>' + self._qtable(self._names('service')))
        else:
            html_ = (STYLE + '<h4>Shear · LRFD 6.12.1.2.3b round tube (governing record)</h4>' + self._qtable(self._names('shear'))
                     + '<h4>Tension · LRFD 6.8.2.1</h4>' + self._qtable(self._names('tension'))
                     + '<p>Service I concrete stress limits apply to prestressed concrete piles only.</p>')
        self._replace(self.boxes['shear'], [W.HTML(html_)])

    def _render_table(self):
        e = self.e
        note = ('<p>SDM 11.4 Pile Data Table for this support, rounded per SDG 3.5.15.D (loads up, tips down, lengths up, cut-off to 0.1 ft). '
                '“N/A” marks entries that are not applicable or not yet received from the geotechnical engineer. Column I excludes the downdrag (column J). '
                'Run each support (End Bent 1, End Bent 2, Pier) and export its table; the workbook holds this support’s row and a Basis sheet.</p>')
        basis = ''.join(f'<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td></tr>' for a, b in exports._basis_rows(e))
        self._replace(self.boxes['table'], [W.HTML(STYLE + note + visuals.data_table_html(e)),
                                            W.HTML(STYLE + '<details class="ebw"><summary>Basis</summary><table class="ebw-table"><tr><th>Item</th><th>Basis</th></tr>' + basis + '</table></details>')])

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
        for i, (key, heading) in enumerate(SECTIONS):
            items = [t for t in trace if t['section'] == key]
            if not items:
                continue
            body = ''.join(f'<p class="ebw-cap">{html.escape(t["caption"])}</p><div class="ebw-eq">{t["mathml"]}</div>' for t in items)
            parts.append(f'<details class="ebw"{" open" if not parts else ""}><summary><b>{html.escape(heading)}</b> · {len(items)} equations</summary>{body}</details>')
        self._replace(self.boxes['equations'], [W.HTML(STYLE + ''.join(parts), layout=W.Layout(max_height='900px', overflow='auto'))])

    # -------------------------------------------------------------- reviews
    def _build_review_panel(self):
        self.review_check = W.Dropdown(description='Check', layout=W.Layout(width='520px'))
        self.review_reason = W.Text(description='Reason', placeholder='Closure note or override justification', layout=W.Layout(width='520px'))
        self.review_by = W.Text(description='Reviewer', placeholder='Initials (optional)', layout=W.Layout(width='260px'))
        buttons = []
        for label, action in (('Close as passed', 'close'), ('Override as passed', 'override'), ('Reopen check', 'reopen')):
            b = W.Button(description=label, layout=W.Layout(width='170px'))
            b.on_click(partial(self._review, action))
            buttons.append(b)
        self.review_status = W.HTML()
        panel = W.VBox([W.HBox([self.review_check, self.review_by], layout=W.Layout(flex_flow='row wrap')), self.review_reason,
                        W.HBox(buttons), self.review_status])
        self.review_ui = Accordion(children=[panel])
        self.review_ui.set_title(0, 'Record a closure or override')
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
        self.export_status = W.HTML()
        self.download_output = W.Output()
        specs = [('Case JSON', exports.CASE), ('Calculation report', exports.REPORT), ('Checks CSV', exports.CHECKS),
                 ('Pile Data Table (xlsx)', exports.TABLE), ('Distilled Mathcad (.xmcd)', exports.MATHCAD),
                 ('Export distilled Blockpad (.bpad)', exports.BPAD), ('Full bundle ZIP', exports.BUNDLE)]
        self.export_buttons = []
        for label, name in specs:
            b = W.Button(description=label, icon='copy' if name == exports.BPAD else 'download', layout=W.Layout(width='230px'))
            b.on_click(partial(self._export, name))
            self.export_buttons.append(b)
        self.boxes['exports'].children = [
            W.HTML('<p>Exports use the last completed Recalc. Each click writes a timestamped folder under <code>exports/</code> and downloads the file. '
                   'The Mathcad worksheet is the distilled calculation of this support (the same generator that writes <code>pile_mathcad/</code>). '
                   'The Blockpad export writes the matching distilled <code>.bpad</code> (the generator behind <code>pile_bpad/</code>) with its <code>verification.json</code>; '
                   'it has not been recalculated in Blockpad. '
                   'In Colab, <code>/content</code> is temporary runtime storage; keep the downloaded copies.</p>'),
            W.HBox(self.export_buttons, layout=W.Layout(flex_flow='row wrap', grid_gap='6px')), self.export_status, self.download_output]

    def _export(self, name, _=None):
        if self.e is None:
            return
        try:
            path = exports.export_file(self.e, self.export_root, name)
        except Exception as exc:
            self.export_status.value = notice_html('DISTILLED EXPORT STOPPED' if name == exports.BPAD else 'EXPORT FAILED', html.escape(str(exc)), 'error')
            return
        self.last_files[name] = path
        self.export_status.value = notice_html('DISTILLED BLOCKPAD READY' if name == exports.BPAD else 'EXPORT WRITTEN',
                                               f'<code>{html.escape(str(path.resolve()))}</code>', 'success')
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
        for box in self.boxes.values():
            for child in box.children:
                if isinstance(child, FigureWidget):
                    child.close()
        for widget in (self.sources_ui, self.design_ui):
            widget.close()
