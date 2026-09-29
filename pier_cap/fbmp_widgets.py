"""One-file upload, review and apply controls for the live cap notebook."""
from copy import deepcopy
import html
import ipywidgets as W
from .fbmp import import_fbmp_xml
from .model import INPUTS


class XMLImportPanel:
    def __init__(self, app, labels):
        self.app = app
        self.labels = labels
        self.pending = None
        self.source = None
        self.filename = None
        self.base_snapshot = None
        self.upload = W.FileUpload(accept='.xml,.XML', multiple=False, description='Upload FBMP XML', layout=W.Layout(width='185px'))
        self.upload.observe(self._uploaded, names='value')
        self.refresh_button = W.Button(description='Refresh preview', disabled=True, icon='refresh')
        self.refresh_button.on_click(lambda _: self.stage(self.source, self.filename))
        self.apply_button = W.Button(description='Apply XML inputs', disabled=True, button_style='primary', icon='check')
        self.apply_button.on_click(self.apply)
        self.status = W.HTML()
        self.preview = W.HTML()
        self.ui = W.VBox([
            W.HTML('<h3 style="margin-bottom:4px">New loads from FB-MultiPier</h3>'
                   '<p>Upload the solved XML → review the geometry and loads → Apply XML inputs → rerun your steel or section search.</p>'),
            W.HBox([self.upload, self.refresh_button, self.apply_button], layout=W.Layout(flex_flow='row wrap')),
            self.status, self.preview,
        ])
        app.case_listeners.append(self._case_changed)

    def _case_changed(self):
        if self.pending is not None and self.app.case != self.base_snapshot:
            self.pending = None
            self.apply_button.disabled = True
            self.status.value = '<b>Inputs changed after preview.</b> Refresh the preview to retain your latest trial steel and settings.'
            self.preview.value = ''

    def _uploaded(self, change):
        if self.upload.value:
            entry = self.upload.value[0]
            self.stage(bytes(entry['content']), entry['name'])

    def stage(self, source, filename=None):
        self.pending = None
        self.apply_button.disabled = True
        self.preview.value = ''
        self.source, self.filename = source, filename
        self.refresh_button.disabled = source is None
        try:
            proposed = import_fbmp_xml(source, base=self.app.case, filename=filename)
            self.base_snapshot = deepcopy(self.app.case)
            self.preview.value = self._preview_html(proposed)
            self.pending = proposed
            self.apply_button.disabled = False
            self.status.value = '<b>Preview ready. Current calculation is unchanged until you click Apply XML inputs.</b>'
        except Exception as exc:
            self.status.value = '<b>XML import stopped; current case is unchanged.</b> '+html.escape(str(exc))

    def apply(self, button=None):
        if self.pending is None:
            return
        if self.app.case != self.base_snapshot:
            self._case_changed()
            return
        proposed = self.pending
        self.pending = None
        self.apply_button.disabled = True
        self.app.load(proposed)
        self.preview.value = ''
        self.status.value = ('<b>Applied '+html.escape(proposed['analysis']['id'])+'.</b> '
                             'Live drawings and checks are updated. Rerun searches for this new force case; export the JSON to save it.')

    def _preview_html(self, case):
        p, old = case['inputs'], self.app.case['inputs']
        audit = case['analysis']['xml_audit']
        def table(keys, force=False):
            rows = []
            for key in keys:
                changed = abs(p[key]-old[key]) > 1e-8
                label = self.labels.get(key,key)
                if key in ('Mu_B','MI_B'):
                    label = label.replace('bearing positive','bearing / span positive')
                unit = INPUTS[key]['unit'] or ''
                cells = (f'<td>{html.escape(label)}</td><td>{old[key]:g}</td>'
                         f'<td><b>{p[key]:g}</b> {html.escape(unit)}</td>')
                if force:
                    row = audit['governing'][key]
                    cells += (f'<td>{html.escape(row["state"])} · combo {html.escape(row["combination"])}'
                              f'<br><small>Member {html.escape(str(row["element"]))}, {html.escape(row["side"])}'
                              f' · x = {row["x_in"]/12:.3f} ft</small></td>')
                rows.append('<tr'+(' style="background:#fff5dc"' if changed else '')+'>'+cells+'</tr>')
            return ('<table class="cap-table"><tr><th>Input</th><th>Current</th><th>From XML</th>'
                    + ('<th>Controls</th>' if force else '')+'</tr>'+''.join(rows)+'</table>')
        combos = ', '.join(f'{k}: {v}' for k,v in audit['combinations'].items())
        notes = ''.join('<li>'+html.escape(note)+'</li>' for note in audit['notes'])
        outside = audit['outside_calc_maxima']
        return (
            '<div style="padding:12px;border:1px solid #bbcbd8;border-radius:6px">'
            f'<b>{html.escape(audit["filename"])}</b> · FB-MultiPier {html.escape(audit["version"])}'
            f'<p><b>{p["b"]:g} in wide × {p["h"]:g} in deep × {audit["cap_length_ft"]:.3f} ft long</b>'
            f' · {p["N_pile"]:g} piles at {p["S_pile"]:g} ft spacing<br>'
            f'Analyzed nominal extension beyond outer pile face: <b>{audit["nominal_end_extension_in"]:.2f} in</b>'
            f' ({audit["cantilever_centerline_in"]:.2f} in from pile center). This is the model dimension, not a new minimum-clearance determination.</p>'
            '<p>Highlighted rows change. Trial reinforcing and covers are retained.</p>'
            '<div style="display:flex;gap:20px;flex-wrap:wrap">'
            '<div><h4>Geometry and materials</h4>'+table(['b','h','N_pile','S_pile','D_pile','E_clear','E_detail','fc','fy','Es'])+'</div>'
            '<div><h4>Force envelopes</h4>'+table(['Mu_N','Mu_P','Mu_B','MI_N','MI_P','MI_B','Vu_G','Vu_L','Tu'],True)+'</div></div>'
            f'<p><b>Checked:</b> {audit["cap_element_count"]} cap members; signed moment/shear extrema and absolute torque match the XML cap summary. '
            f'Combinations: {html.escape(combos)}.</p>'
            '<details><summary><b>Import basis and remaining checks</b></summary><ul>'+notes+'</ul>'
            f'<p>Outside-calculation envelope magnitudes: axial {outside["axial"]:g} kip; '
            f'weak-axis moment {outside["weak_moment"]:g} kip-ft; lateral shear {outside["lateral_shear"]:g} kip.</p>'
            f'<p>SHA256: <code>{audit["sha256"]}</code>. Governing member ends and source metadata travel with the saved JSON.</p>'
            '</details></div>'
        )
