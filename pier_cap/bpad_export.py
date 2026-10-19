"""Shared helpers for exporting distilled Blockpad (.bpad) sheets from the cap and backwall notebooks."""
import base64
import html
import json
import re
from pathlib import Path
import ipywidgets as W

from .source_status import notice_html


def package_revision(package_dir=None, prefixes=('cap-pile-tool-', 'backwall-tool-'),
                     notebooks=('Cap_and_Pile_Design.ipynb', 'End_Bent_Backwall_Design.ipynb')):
    """Twelve-character revision of the package this code runs from.

    The portable notebooks extract their package into a folder named <prefix><12 hex characters>; in a checkout the
    revision is read from the notebook's setup cell; otherwise 'working copy'."""
    root = Path(package_dir or Path(__file__).resolve().parent).resolve().parent
    for prefix in prefixes:
        if root.name.startswith(prefix):
            return root.name[len(prefix):]
    for name in notebooks:
        path = root / name
        if not path.is_file():
            continue
        try:
            notebook = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        for cell in notebook.get('cells', []):
            if cell.get('cell_type') != 'code':
                continue
            found = re.search(r'revision = "([0-9a-f]{64})"', ''.join(cell.get('source', [])))
            if found:
                return found.group(1)[:12]
    return 'working copy'


class DistilledBpadPanel:
    """Export button + download for one distilled .bpad sheet; `distill(app)` builds it, `ready(app)` gates it."""

    def __init__(self, app, distill, *, hint, ready=None, title='Distilled Blockpad sheet'):
        self.app = app
        self.distill = distill
        self.ready = ready
        self.last_file = None
        self.last_result = None
        try:
            from google.colab import files
        except ImportError:
            self.colab_files = None
        else:
            self.colab_files = files
        self.export_button = W.Button(description='Export distilled Blockpad (.bpad)', icon='copy', layout=W.Layout(width='280px'))
        self.export_button.on_click(self.export)
        self.download_button = W.Button(description='Download last distilled .bpad', icon='download', disabled=True,
                                        layout=W.Layout(width='250px'))
        self.download_button.on_click(self.download)
        self.status = W.HTML()
        self.download_output = W.Output()
        self.ui = W.VBox([W.HTML(f'<h4>{title}</h4><p>{hint}</p>'),
            W.HBox([self.export_button, self.download_button], layout=W.Layout(flex_flow='row wrap')),
            self.status, self.download_output])

    def _notice(self, title, detail, kind='info'):
        self.status.value = notice_html(title, detail, kind)
        message = getattr(self.app, 'message', None)
        if message is not None:
            message.value = self.status.value

    def export(self, _=None):
        if self.ready is not None:
            blocked = self.ready(self.app)
            if blocked:
                self._notice(blocked[0], html.escape(blocked[1]), 'pending')
                return
        self.last_file = None
        self.last_result = None
        self.download_button.disabled = True
        self.download_output.clear_output()
        self.export_button.disabled = True
        try:
            result = self.distill(self.app)
            self.last_result = result
            self.last_file = Path(result['bpad'])
            self.download_button.disabled = False
            self._notice('DISTILLED BLOCKPAD READY', html.escape(self.last_file.name) + '<br>' + html.escape(result['summary']) +
                '<br>Open and recalculate the sheet in Blockpad. It distils the numerical checks only; it is not design acceptance.',
                'success')
        except Exception as exc:
            self._notice('DISTILLED EXPORT STOPPED', html.escape(str(exc)), 'error')
        finally:
            self.export_button.disabled = False
        if self.last_file is not None:
            self.download()

    def download(self, _=None):
        if self.last_file is None:
            return
        from IPython.display import clear_output, display, HTML
        path = self.last_file
        try:
            with self.download_output:
                clear_output(wait=True)
                if self.colab_files:
                    self.colab_files.download(str(path.resolve()))
                else:
                    # An absolute FileLink can point outside Jupyter's served root; embed the bytes instead.
                    payload = base64.b64encode(path.read_bytes()).decode('ascii')
                    name = html.escape(path.name, quote=True)
                    display(HTML(f'<a download="{name}" href="data:application/octet-stream;base64,{payload}">Download {name}</a>'))
        except Exception as exc:
            self._notice('DISTILLED SHEET SAVED — DOWNLOAD NEEDS RETRY',
                html.escape(str(exc)) + '<br>Click Download last distilled .bpad to retry. '
                'The file is also saved at ' + html.escape(str(path.resolve())), 'pending')
