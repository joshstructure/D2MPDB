"""Visible, retryable cap-case loading in Colab and ordinary Jupyter."""
from copy import deepcopy
from datetime import datetime, timezone
import html
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import ipywidgets as W
from .io import load_case
from .source_status import notice_html, upload_entries


CASE_CONTENTS = (
    'Restores saved cap force inputs, geometry, materials, reinforcement, hoop/U-bar runs, '
    'pile appearance and design settings. Cap plots and checks are recalculated. '
    'Force diagrams return when their source records are in the file. '
    'This does not restore completed steel searches or section studies. '
    'Pile profiles and minimum-tip trials are separate: use <b>Load pile review</b> '
    'in the pile panel with <b>pile_review.json</b>, or upload the solved XML for pile results.'
)


def case_signature(case):
    return json.dumps(case, sort_keys=True)


class CaseImportPanel:
    def __init__(self, app):
        self.app = app
        self.receipt = None
        self.receiving = False
        self.upload_output = W.Output(layout=W.Layout(display='none'))
        self.status = W.HTML(notice_html('READY TO LOAD CASE JSON',
            'Choose <b>selected_case.json</b> from a previous cap export. '
            'The filename and a success or error message will appear here.'))
        try:
            from google.colab import files
        except ImportError:
            self.colab_files = None
            self.upload = W.FileUpload(accept='.json,.JSON', multiple=False,
                description='Load case JSON', layout=W.Layout(width='190px'))
            self.upload.observe(self._uploaded, names='value')
            self.upload.observe(self._upload_error, names='error')
        else:
            # As with XML imports, avoid Colab FileUpload's missing binary buffers.
            self.colab_files = files
            self.upload = W.Button(description='Load case JSON', icon='upload',
                layout=W.Layout(width='190px'))
            self.upload.on_click(self._colab_uploaded)
        self.actions = W.HBox([self.upload], layout=W.Layout(flex_flow='row wrap'))
        self.ui = W.VBox([self.actions, self.upload_output, self.status,
            W.HTML('<details><summary>What does the case JSON restore?</summary><p>'
                   + CASE_CONTENTS + '</p></details>')])
        app.case_listeners.append(self._case_changed)

    def _failed(self, exc, filename=None, *, applied=False):
        self.receipt = None
        title = 'CASE APPLY DID NOT FINISH' if applied else 'CASE IMPORT FAILED'
        detail = ('<b>' + html.escape(filename) + '</b><br>') if filename else ''
        detail += html.escape(str(exc))
        detail += ('<br>Inputs may have changed, but the display did not finish updating. '
                   'Check the active source and rerun Live workbench before using the results.' if applied else
                   '<br>The current cap inputs were not changed. Select the file again to retry.')
        self.status.value = notice_html(title, detail, 'error')
        self.app.import_notice.value = self.status.value

    def _upload_error(self, change):
        if change['new']:
            self._failed(ValueError('File transfer failed: ' + str(change['new'])))

    def _uploaded(self, change):
        if self.receiving or not self.upload.value:
            return
        self.receiving = True
        self.upload.disabled = True
        try:
            entries = upload_entries(self.upload.value)
            if len(entries) != 1:
                raise ValueError('Select exactly one cap case JSON file.')
            entry = entries[0]
            self.load(entry['content'], entry['name'])
        except Exception as exc:
            self._failed(exc)
        finally:
            # Clear the selection so the same file can be selected after a retry
            # or after changing the live inputs. Support both widget protocols.
            if 'metadata' in self.upload.traits():
                self.upload.metadata = []
                self.upload.data = []
                self.upload._counter = 0
            else:
                self.upload.value = ()
            self.receiving = False
            self.upload.disabled = False

    def _colab_uploaded(self, button=None):
        from IPython.display import clear_output
        self.receipt = None
        self.upload.disabled = True
        self.status.value = notice_html('CHOOSE CASE JSON',
            'Click <b>Choose Files</b> above and select one saved cap case JSON. '
            'The current cap inputs stay in place until the file passes validation.', 'pending')
        self.upload_output.layout.display = ''
        try:
            with self.upload_output:
                clear_output(wait=True)
                with TemporaryDirectory(prefix='pier-cap-case-upload-') as folder:
                    received = self.colab_files.upload(target_dir=folder)
                clear_output(wait=False)
            if not received:
                self.status.value = notice_html('UPLOAD CANCELLED',
                    'No file was selected. The current cap inputs were not changed.')
                return
            if len(received) != 1:
                raise ValueError('Select exactly one cap case JSON file.')
            filename, content = next(iter(received.items()))
            self.load(content, Path(filename).name)
        except Exception as exc:
            self._failed(exc)
        finally:
            self.upload_output.layout.display = 'none'
            self.upload.disabled = False

    def load(self, content, filename):
        self.receipt = None
        self.status.value = notice_html('READING CASE JSON',
            '<b>' + html.escape(filename) + '</b><br>Checking saved inputs and calculating the cap…', 'pending')
        try:
            if Path(filename).suffix.lower() != '.json':
                raise ValueError('Select a cap case .json file, usually selected_case.json.')
            proposed = load_case(content)
        except Exception as exc:
            self._failed(exc, filename)
            return
        try:
            self.app.load(proposed, import_name=filename)
            if self.app.current is None:
                raise ValueError('The cap calculation could not be refreshed. See the input error below.')
        except Exception as exc:
            self._failed(exc, filename, applied=True)
            return
        self.receipt = dict(filename=filename,
            loaded_utc=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            signature=case_signature(self.app.case))
        self._case_changed()

    def restore_receipt(self, receipt):
        self.receipt = deepcopy(receipt)
        self._case_changed()

    def _case_changed(self):
        if not self.receipt:
            return
        r = self.receipt
        detail = '<b>' + html.escape(r['filename']) + '</b> · loaded ' + html.escape(r['loaded_utc'])
        if r['signature'] != case_signature(self.app.case):
            self.status.value = notice_html('CURRENT CASE DIFFERS FROM LOADED JSON', detail +
                '<br>The active case has changed since loading this file. The current inputs and active force source are shown below.', 'pending')
            return
        p = self.app.case['inputs']
        detail += ('<br>Active analysis: <b>' + html.escape(self.app.case['analysis']['id']) + '</b>'
            f'<br>Cap: <b>{p["b"]:g} × {p["h"]:g} in</b> · {p["N_pile"]:g} piles at {p["S_pile"]:g} ft'
            f'<br>Strength moments N / P / B: <b>{p["Mu_N"]:g} / {p["Mu_P"]:g} / {p["Mu_B"]:g} kip-ft</b>'
            f' · Shear G / L: <b>{p["Vu_G"]:g} / {p["Vu_L"]:g} kip</b> · Torsion: <b>{p["Tu"]:g} kip-ft</b>'
            '<br><b>Cap plots and checks recalculated.</b> No Apply button or cell rerun is needed. '
            'Saved check failures or pending items still require review.'
            '<br>Pile review and completed search/study results were not loaded from this file.')
        self.status.value = notice_html('CASE JSON LOADED SUCCESSFULLY', detail, 'success')
