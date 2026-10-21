"""Portable Colab notebook of a journal calculation (the backwall notebook pattern, driven by the package data).

The setup cell embeds the package (`<calc>/*.py`, `<calc>/data/*`), the shared `calc_common/` and `pier_cap/` code, the
report cards with the cited excerpt images, and the Blockpad writer the distilled export imports. Only the embedded
package and its revision change on a refresh; edited cell text is preserved.
"""
import base64
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

COLAB_BASE = 'https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/'
SETUP_ID = 'e3b0a7c1'
EMBEDDED_SCRIPTS = ('__init__.py', 'bpad_sheet.py', 'bpad_preview.py')


def _lines(text):
    return text.strip('\n').splitlines(keepends=True)


SETUP = '''# @title Start the portable tool
from pathlib import Path
import base64, hashlib, importlib, io, os, subprocess, sys, zipfile
try:
    from google.colab import output as colab_output
except ImportError:
    IN_COLAB = False
else:
    IN_COLAB = True
revision = "0"
PACKAGE = "AA=="
_package_bytes = base64.b64decode(PACKAGE)
if hashlib.sha256(_package_bytes).hexdigest() != revision:
    raise RuntimeError("Embedded calculation package is damaged.")
ROOT = (Path("/content") if IN_COLAB else Path.cwd()) / ("{tool_prefix}" + revision[:12])
ROOT.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(_package_bytes)) as _package:
    for _name in _package.namelist():
        _target = (ROOT / _name).resolve()
        if not _target.is_relative_to(ROOT.resolve()):
            raise RuntimeError("Invalid embedded package path.")
        _contents = _package.read(_name)
        if _target.exists() and _target.read_bytes() != _contents:
            raise RuntimeError("An extracted calculation file was edited. Preserve your edits and exports before using a fresh notebook folder.")
        _target.parent.mkdir(parents=True, exist_ok=True)
        if not _target.exists():
            _target.write_bytes(_contents)
if IN_COLAB:
    requirements = ROOT / "requirements-pier-cap-colab.txt"
    if not (ROOT / "{package}").is_dir() or not requirements.is_file():
        raise RuntimeError("The embedded package is incomplete. Reopen the delivered notebook.")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-r", str(requirements)], check=True)
    import ipywidgets as widget_runtime
    from importlib.metadata import version as installed_version
    loaded_widgets = widget_runtime.__version__
    installed_widgets = installed_version("ipywidgets")
    if loaded_widgets != installed_widgets or loaded_widgets != "7.7.1":
        raise RuntimeError(
            f"Widget session restart required: Python loaded ipywidgets {{loaded_widgets}}, "
            f"but {{installed_widgets}} is installed. Use Runtime → Restart session, "
            "then reload this browser page and Run all. Save any existing case before restarting."
        )
    import plotly as plot_runtime
    if plot_runtime.__version__ != "5.24.1" or installed_version("plotly") != "5.24.1":
        raise RuntimeError(
            "Chart session restart required. Save your case, use Runtime → Restart session, "
            "reload this browser page, then Run all. Colab needs Plotly 5.24.1 for live chart widgets."
        )
    widget_runtime.register_comm_target(get_ipython().kernel)
    colab_output.enable_custom_widget_manager()
    os.chdir(ROOT)
    for module_name in list(sys.modules):
        if module_name.split(".")[0] in ("pier_cap", "calc_common", "{package}", "scripts", "report_cards"):
            del sys.modules[module_name]
    importlib.invalidate_caches()
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))
from {package}.widgets import Notebook
from {package}.model import evaluate, default_case
print(f"Ready · {title} package {{revision[:12]}}. Run Cell 1 and Cell 2.")
'''

CELL1 = '''# @title Cell 1 · Project sources and assumptions
from copy import deepcopy
# Keep the active case, confirmations and reviews if this cell is run again.
_previous_app = globals().get("app")
_case = deepcopy(_previous_app.case) if _previous_app is not None else None
if _previous_app is not None:
    _previous_app.close()
app = Notebook(_case, export_root=ROOT / "exports")
app.display("sources");
'''

CELL2 = '''# @title Cell 2 · {title}
if "app" not in globals():
    print("Run Cell 1 first to load the project sources, then run this cell.")
else:
    app.display("design");
'''

SCROLL = '''# @title Disable output scrolling
from IPython.display import Javascript, display
from IPython import get_ipython

def disable_colab_scrolling(*_):
    display(Javascript('google.colab.output.setIframeHeight(0, true, {maxHeight: 10000})'))

_scroll_events = get_ipython().events
for _callback in list(_scroll_events.callbacks.get('pre_run_cell', [])):
    if getattr(_callback, '__name__', '') == 'disable_colab_scrolling':
        _scroll_events.unregister('pre_run_cell', _callback)
_scroll_events.register('pre_run_cell', disable_colab_scrolling)
print("Output scrolling disabled for future cell executions.")
'''


def intro_markdown(spec):
    colab = COLAB_BASE + spec.notebook
    parts = [f'# {spec.full_title}', '', f'[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)]({colab})', '',
             f'Portable Colab edition for the **D2 I-95 pedestrian bridge**: the journal calculation {spec.cnumber} as a notebook. '
             'Choose **Runtime → Run all**. The calculation package is embedded in this file.', '']
    parts += [p for p in spec.text.get('intro', [])]
    parts += ['', '**Workflow.** Cell 1 shows the inputs with their journal module or code provision and loads a saved case. Cell 2 holds the '
              'inputs, results, the journal figures, the D/C register with *Equation & values* disclosures, the equations and the exports '
              '(case JSON, calculation report, checks CSV, distilled Blockpad .bpad with its verification record, full bundle).']
    return '\n'.join(parts) + '\n'


def template(spec):
    colab = COLAB_BASE + spec.notebook

    def code(source, cell_id):
        return {'cell_type': 'code', 'id': cell_id, 'metadata': {'cellView': 'form', 'jupyter': {'source_hidden': True}},
                'execution_count': None, 'outputs': [], 'source': _lines(source)}
    setup = SETUP.format(tool_prefix=spec.tool_prefix, package=spec.package, title=spec.title)
    return {'cells': [
        {'cell_type': 'markdown', 'id': 'c0a1b2c3', 'metadata': {}, 'source': _lines(
            f'<a href="{colab}" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>')},
        {'cell_type': 'markdown', 'id': 'd4e5f6a7', 'metadata': {}, 'source': _lines(intro_markdown(spec))},
        code(SCROLL, 'a7b8c9d0'), code(setup, SETUP_ID), code(CELL1, 'f1a2b3c4'), code(CELL2.format(title=spec.title), 'f5a6b7c8')],
        'metadata': {'colab': {'name': spec.notebook, 'provenance': [], 'include_colab_link': True},
                     'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                     'language_info': {'name': 'python'}, 'title': spec.full_title},
        'nbformat': 4, 'nbformat_minor': 5}


def cited_pages(spec, repo):
    import sys
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    try:
        from report_cards import cited_page_files
    except ImportError:
        return []
    return cited_page_files(repo, references=[f'{spec.package}/data/references.json'], scan=[f'{spec.package}/*.py'])


def package_files(spec, repo):
    repo = Path(repo)
    return sorted([*repo.glob(f'{spec.package}/*.py'), *repo.glob(f'{spec.package}/data/*.json'), *repo.glob(f'{spec.package}/data/*.xml'),
                   *repo.glob('calc_common/*.py'), *repo.glob('pier_cap/*.py'), *repo.glob('pier_cap/data/*.json'),
                   repo / 'requirements-pier-cap-colab.txt',
                   *repo.glob('report_cards/*.py'), *repo.glob('report_cards/*.js'), *repo.glob('report_cards/*.css'),
                   *repo.glob('code_excerpts/excerpts.json'), *cited_pages(spec, repo),
                   *[repo / 'scripts' / name for name in EMBEDDED_SCRIPTS if (repo / 'scripts' / name).is_file()]])


def build(spec, repo):
    repo = Path(repo)
    path = repo / spec.notebook
    notebook = json.loads(path.read_text(encoding='utf-8')) if path.exists() else template(spec)
    buffer = io.BytesIO()
    files = package_files(spec, repo)
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as package:
        for file in files:
            entry = zipfile.ZipInfo(file.relative_to(repo).as_posix(), date_time=(2026, 10, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(entry, file.read_bytes())
    raw = buffer.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    setup = next(c for c in notebook['cells'] if c.get('id') == SETUP_ID)
    source, revisions = re.subn(r'^revision = "[a-f0-9]+"$', f'revision = "{digest}"', ''.join(setup['source']), flags=re.M)
    source, packages = re.subn(r'^PACKAGE = "[A-Za-z0-9+/=]+"$', 'PACKAGE = "' + base64.b64encode(raw).decode() + '"', source, flags=re.M)
    if revisions != 1 or packages != 1:
        raise ValueError('Expected exactly one package and revision in the portable setup cell.')
    setup['source'] = source.splitlines(keepends=True)
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            cell['outputs'] = []
            cell['execution_count'] = None
    notebook['metadata'].pop('widgets', None)
    path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Updated {path.name}: {len(files)} supporting files, package {digest[:12]}')
    return digest


def embedded_revision(spec, repo):
    path = Path(repo) / spec.notebook
    if not path.is_file():
        return None
    notebook = json.loads(path.read_text(encoding='utf-8'))
    setup = next(c for c in notebook['cells'] if c.get('id') == SETUP_ID)
    m = re.search(r'^revision = "([a-f0-9]+)"$', ''.join(setup['source']), flags=re.M)
    return m.group(1) if m else None
