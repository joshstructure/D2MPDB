"""Create or refresh the portable End_Bent_Backwall_Design notebook from this checkout.

The setup cell embeds end_bent_walls/ plus the shared pier_cap/ engine (formula
evaluator, MathML, widget and Plotly compatibility). Only the embedded package
and its revision change on a refresh; edited cell text is preserved.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

NOTEBOOK = 'End_Bent_Backwall_Design.ipynb'
SETUP_ID = 'e3b0a7c1'
COLAB = 'https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/' + NOTEBOOK


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
ROOT = (Path("/content") if IN_COLAB else Path.cwd()) / ("backwall-tool-" + revision[:12])
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
    if not (ROOT / "end_bent_walls").is_dir() or not requirements.is_file():
        raise RuntimeError("The embedded package is incomplete. Reopen the delivered notebook.")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-r", str(requirements)], check=True)
    # Pip does not replace classes already in memory. Require Colab's tested
    # widget protocol and a session matching the installed files.
    import ipywidgets as widget_runtime
    from importlib.metadata import version as installed_version
    loaded_widgets = widget_runtime.__version__
    installed_widgets = installed_version("ipywidgets")
    if loaded_widgets != installed_widgets or loaded_widgets != "7.7.1":
        raise RuntimeError(
            f"Widget session restart required: Python loaded ipywidgets {loaded_widgets}, "
            f"but {installed_widgets} is installed. Use Runtime → Restart session, "
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
        if module_name.split(".")[0] in ("pier_cap", "end_bent_walls"):
            del sys.modules[module_name]
    importlib.invalidate_caches()
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))
from end_bent_walls.widgets import BackwallNotebook
from end_bent_walls.model import evaluate, default_case
print(f"Ready · backwall calculation package {revision[:12]}. Run Cell 1 and Cell 2.")
'''

CELL1 = '''# @title Cell 1 · Project sources and assumptions
from copy import deepcopy
# Keep the active case, receipts, confirmations and reviews if this cell is run again.
_previous_app = globals().get("app")
_case = deepcopy(_previous_app.case) if _previous_app is not None else None
if _previous_app is not None:
    _previous_app.close()
app = BackwallNotebook(_case, export_root=ROOT / "exports")
app.display("sources");
'''

CELL2 = '''# @title Cell 2 · Backwall, cheek walls and tie-back straps
if "app" not in globals():
    print("Run Cell 1 first to load the project sources, then run this cell.")
else:
    app.display("design");
'''

INTRO = f'''# End-bent backwall, cheek walls and tie-back straps

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)]({COLAB})

Portable Colab edition for the **D2 I-95 pedestrian bridge** end bents (common End Bent 1 design, D-004). Choose **Runtime → Run all**. The calculation package is embedded in this file.

**What it does.** Earth pressure from the MSE landing fill, the pedestrian surcharge, temperature/shrinkage pad forces and the eccentric bearing loads push the end bent toward the span. Tie-back straps attached to the backwall and extending into the MSE fill resist that overturning about the pile top (D-014). The notebook:

1. reads the registered `project_current` sources (end-bent cap case, FBMP XML, FreeCAD model) and checks them against the source register;
2. builds Service I, Strength I, Strength III (two wind directions) and Strength IV overturning tables with the SDG 3.13.2.N.3 pile placement tolerance;
3. reports the **service and factored strap loads per foot of backwall** for the plans (SDM 12.3.F), with the required plan note;
4. designs the backwall for both strap states (slack: fill-face tension; engaged: span-face tension) and the cheek walls for wind;
5. screens the cap torsion that the FBMP model does not include.

**Workflow.** Cell 1 shows sources, receipts and confirmations. Cell 2 holds the inputs, drawings, overturning tables, D/C register with *Equation & values* disclosures, and exports (case JSON, Mathcad-style HTML report, checks CSV, MSE strap handoff workbook).

Decisions D-014 to D-019 (tie-back straps, pedestrian-only loading, MSE fill parameters, landing slab on the backwall, cheek walls for wind only, maximum backwall height) are recorded in `project_current/decisions.md`. See `BACKWALL_DESIGN.md` for the calculation basis and limits.
'''


def template():
    def code(source, cell_id):
        return {'cell_type': 'code', 'id': cell_id, 'metadata': {'cellView': 'form', 'jupyter': {'source_hidden': True}},
                'execution_count': None, 'outputs': [], 'source': _lines(source)}
    scroll = '''# @title Disable output scrolling
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
    return {'cells': [
        {'cell_type': 'markdown', 'id': 'c0a1b2c3', 'metadata': {}, 'source': _lines(
            f'<a href="{COLAB}" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>')},
        {'cell_type': 'markdown', 'id': 'd4e5f6a7', 'metadata': {}, 'source': _lines(INTRO)},
        code(scroll, 'a7b8c9d0'), code(SETUP, SETUP_ID), code(CELL1, 'f1a2b3c4'), code(CELL2, 'f5a6b7c8')],
        'metadata': {'colab': {'name': NOTEBOOK, 'provenance': [], 'include_colab_link': True},
                     'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                     'language_info': {'name': 'python'}, 'title': 'End-bent backwall, cheek walls and tie-back straps'},
        'nbformat': 4, 'nbformat_minor': 5}


def package_files(repo):
    return sorted([*repo.glob('end_bent_walls/*.py'), *repo.glob('end_bent_walls/data/*.json'),
                   *repo.glob('pier_cap/*.py'), *repo.glob('pier_cap/data/*.json'), repo / 'requirements-pier-cap-colab.txt'])


def build(repo):
    path = repo / NOTEBOOK
    notebook = json.loads(path.read_text(encoding='utf-8')) if path.exists() else template()
    buffer = io.BytesIO()
    files = package_files(repo)
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


if __name__ == '__main__':
    build(Path(__file__).resolve().parents[1])
