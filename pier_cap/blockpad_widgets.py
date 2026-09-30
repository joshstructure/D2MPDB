"""Upload a journal and export a new C005 review copy in Jupyter or Colab."""
import html
from pathlib import Path
from tempfile import TemporaryDirectory
import ipywidgets as W

from .io import validate_blockpad_source, export_blockpad, export_bundle
from .source_status import upload_entries, notice_html


class BlockpadExportPanel:
    def __init__(self, app):
        self.app = app
        self.source = None
        self.filename = None
        self.last_file = None
        self.updating = False
        self.transfer = W.Output(layout=W.Layout(display='none'))
        self.download_output = W.Output()
        self.status = W.HTML(notice_html('SELECT BLOCKPAD JOURNAL',
            'Upload your existing C005 Live Design .bpad journal, then export a new review copy.'))
        self.path = W.Text(placeholder='Optional: path on the computer running this notebook',
                           description='Runtime path', layout=W.Layout(width='95%'))
        self.path.observe(self._path_changed, names='value')
        try:
            from google.colab import files
        except ImportError:
            self.colab_files = None
            self.upload = W.FileUpload(accept='.bpad', multiple=False, description='Upload Blockpad journal',
                                       layout=W.Layout(width='230px'))
            self.upload.observe(self._uploaded, names='value')
        else:
            self.colab_files = files
            self.upload = W.Button(description='Upload Blockpad journal', icon='upload', layout=W.Layout(width='230px'))
            self.upload.on_click(self._colab_uploaded)
        self.export_button = W.Button(description='Export a Blockpad review copy', icon='copy', layout=W.Layout(width='260px'))
        self.export_button.on_click(self.export)
        self.download_button = W.Button(description='Download last .bpad copy', icon='download', disabled=True,
                                        layout=W.Layout(width='240px'))
        self.download_button.on_click(self.download)
        hint = ('Colab runs on a remote computer. Windows paths such as C:\\Users\\... are not available here. '
                'Use Upload Blockpad journal, then Choose Files. A successful export starts a download.'
                if self.colab_files else 'Upload a journal, or enter a source path accessible to this notebook.')
        self.ui = W.VBox([W.HTML('<h4>Blockpad review copy</h4><p>' + hint + '</p>'),
            self.upload, self.transfer, self.path,
            W.HBox([self.export_button, self.download_button], layout=W.Layout(flex_flow='row wrap')),
            self.status, self.download_output])

    def _notice(self, title, detail, kind='info'):
        self.status.value = notice_html(title, detail, kind)
        self.app.message.value = self.status.value

    def _clear_source(self):
        self.source = self.filename = None
        self.last_file = None
        self.download_button.disabled = True
        self.download_output.clear_output()

    def _path_changed(self, change):
        if self.updating:
            return
        self._clear_source()
        self._notice('SOURCE PATH SELECTED',
            'The path must exist on the computer running this notebook. In Colab, upload the journal from your computer.')

    def stage(self, filename, content):
        self._clear_source()
        self.updating = True
        try:
            self.path.value = ''
        finally:
            self.updating = False
        try:
            filename = Path(filename).name
            if Path(filename).suffix.lower() != '.bpad':
                raise ValueError('Select one .bpad journal file.')
            content = bytes(content)
            validate_blockpad_source(content)
            self.source, self.filename = content, filename
            self._notice('JOURNAL READY', html.escape(filename) +
                ' contains the C005 module. Export will use the current main calculator inputs. '
                'To export a study candidate, first load that selected case into the calculator.', 'success')
        except Exception as exc:
            self._notice('JOURNAL UPLOAD FAILED', html.escape(str(exc)), 'error')

    def _uploaded(self, change):
        self._clear_source()
        self.path.value = ''
        try:
            entries = upload_entries(self.upload.value)
            if len(entries) != 1:
                raise ValueError('Select exactly one .bpad journal.')
            self.stage(entries[0]['name'], entries[0]['content'])
        except Exception as exc:
            self._notice('JOURNAL UPLOAD FAILED', html.escape(str(exc)), 'error')

    def _colab_uploaded(self, _=None):
        from IPython.display import clear_output
        self._clear_source()
        self.path.value = ''
        self.upload.disabled = self.export_button.disabled = True
        self.transfer.layout.display = ''
        self._notice('CHOOSE BLOCKPAD JOURNAL', 'Click <b>Choose Files</b> and select your existing .bpad journal.', 'pending')
        try:
            with self.transfer:
                clear_output(wait=True)
                with TemporaryDirectory(prefix='pier-cap-bpad-') as folder:
                    received = self.colab_files.upload(target_dir=folder)
                clear_output(wait=False)
            if not received:
                self._notice('UPLOAD CANCELLED', 'No journal is selected. Upload one before exporting.')
            elif len(received) != 1:
                raise ValueError('Select exactly one .bpad journal.')
            else:
                self.stage(*next(iter(received.items())))
        except Exception as exc:
            self._notice('JOURNAL UPLOAD FAILED', html.escape(str(exc)), 'error')
        finally:
            self.transfer.layout.display = 'none'
            self.upload.disabled = self.export_button.disabled = False

    def export(self, _=None):
        self.last_file = None
        self.download_button.disabled = True
        self.download_output.clear_output()
        self.export_button.disabled = True
        try:
            source = self.source if self.source is not None else self.path.value.strip()
            if not source:
                raise ValueError('Upload your .bpad journal first, or enter a path accessible to this notebook.')
            validate_blockpad_source(source)
            self.app.last_export = export_bundle(self.app.case, self.app.export_root, self.app.search_result,
                                                 search_filter=self.app._search_filter())
            name = 'C005 - Notebook Review - ' + self.app.last_export.name.removeprefix('case-') + '.bpad'
            self.last_file = export_blockpad(source, self.app.case, self.app.last_export / name)
            self.download_button.disabled = False
            self._notice('BLOCKPAD REVIEW COPY READY', html.escape(name) +
                '<br>Open and recalculate this copy in Blockpad. Other project sections and the original journal are preserved. '
                'This is a review copy, not a design release.', 'success')
        except Exception as exc:
            self._notice('BLOCKPAD EXPORT STOPPED', html.escape(str(exc)), 'error')
        finally:
            self.export_button.disabled = False
        if self.last_file is not None:
            self.download()

    def download(self, _=None):
        if self.last_file is None:
            return
        from IPython.display import clear_output, display, FileLink
        try:
            with self.download_output:
                clear_output(wait=True)
                if self.colab_files:
                    self.colab_files.download(str(self.last_file.resolve()))
                else:
                    display(FileLink(str(self.last_file)))
        except Exception as exc:
            self._notice('REVIEW COPY SAVED — DOWNLOAD NEEDS RETRY',
                html.escape(str(exc)) + '<br>Click Download last .bpad copy to retry. '
                'The file is also saved at ' + html.escape(str(self.last_file.resolve())), 'pending')
