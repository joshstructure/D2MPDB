"""Create or refresh the portable Pile_Design notebook from this checkout.

The setup cell embeds pile_design/ plus the shared pier_cap/ engine (formula evaluator,
MathML, FBMP reader, widget and Plotly compatibility) and the Mathcad writer
(scripts/mathcad_sheet.py, scripts/mathcad_plot.py and the plot template) and the Blockpad writer
(scripts/bpad_sheet.py). Only the
embedded package and its revision change on a refresh; edited cell text is preserved.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

NOTEBOOK = 'Pile_Design.ipynb'
SETUP_ID = 'b7c2d9e4'
EMBEDDED_XML = ('EB-XML', 'EB2-XML', 'PIER-XML')      # registered fixed-run exports (project_current/fbmp/...)
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
ROOT = (Path("/content") if IN_COLAB else Path.cwd()) / ("pile-tool-" + revision[:12])
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
    if not (ROOT / "pile_design").is_dir() or not requirements.is_file():
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
# Reload after a re-run with a new package: drop the cached modules (scripts is a namespace package).
for module_name in list(sys.modules):
    if module_name.split(".")[0] in ("pier_cap", "pile_design", "scripts"):
        del sys.modules[module_name]
importlib.invalidate_caches()
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))
from pile_design.widgets import PileNotebook
from pile_design.model import evaluate, default_case
print(f"Ready · pile calculation package {revision[:12]}. Run Cell 1 and Cell 2.")
'''

CELL1 = '''# @title Cell 1 · Project sources and assumptions
from copy import deepcopy
# The registered FBMP exports are embedded and loaded for each support preset; upload a newer XML here to replace them.
# Keep the active case, receipts, confirmations and reviews if this cell is run again.
_previous_app = globals().get("app")
_case = deepcopy(_previous_app.case) if _previous_app is not None else None
if _previous_app is not None:
    _previous_app.close()
app = PileNotebook(_case, export_root=ROOT / "exports")
app.display("sources");
'''

CELL2 = '''# @title Cell 2 · Pile analysis and design
if "app" not in globals():
    print("Run Cell 1 first to load the project sources, then run this cell.")
else:
    app.display("design");
'''

INTRO = f'''# Pile analysis and design

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)]({COLAB})

Portable Colab edition for the piles of the **D2 I-95 pedestrian bridge**: End Bent 1, End Bent 2 and the Pier. Choose **Runtime → Run all**. The calculation package is embedded in this file.

**What it does.** The pile forces come from the FB-MultiPier (FBMP) XML exports. The notebook adds the downdrag as a drag load, checks the pile section for every FBMP record and reports the geotechnical Nominal Bearing Resistance and the Pile Data Table. It:

1. reads the FBMP pile XML (the embedded registered exports from `project_current/fbmp/`, or an upload) and compares its SHA-256 with the source register — every XML-derived input is re-read from the file, never hard-coded;
2. adds the **downdrag** (18 tons per end-bent pile from the geotechnical engineer, none at the pier) as the drag load DR: γ<sub>DR</sub> = 1.10 at the strength limit states and 1.00 at Service I for the structural demands (LRFD Table 3.4.1-1, 10.7.3.7), excluded from the Factored Design Load, and added to the Nominal Bearing Resistance by SDG Eq. 3-1;
3. designs **two pile families**: square prestressed concrete piles with the FDOT Standard Plans Index 455 strand patterns (strain-compatibility interaction curve, LRFD 5.6.4.5 biaxial check, shear by the 5.7.3.4.2 general procedure, tension, Service I stresses) and noncomposite steel pipe piles (LRFD 6.9.4.1 axial, 6.12.2.2.3 flexure, 6.9.2.2.1 interaction, shear and tension, depth to fixity from C10.7.3.13.4);
4. compares the required Nominal Bearing Resistance with SDG Table 3.5.13-1 and builds the **SDM 11.4 Pile Data Table** (columns A to Q, rounded per SDG 3.5.15.D, "N/A" where not applicable);
5. lists every check in a D/C register with an *Equation & values* disclosure, code references and recorded reviews.

**Workflow.** Cell 1 holds the support preset, the FBMP and cap-case uploads and the confirmations. Cell 2 holds the pile family and Standard Plans option, the inputs, the section, demand, interaction, shear and service, Pile Data Table, check and equation tabs, and the exports: case JSON, calculation report (HTML with MathML equations and Plotly figures), checks CSV, Pile Data Table workbook, a distilled Mathcad 15 worksheet and a bundle ZIP.

The three registered fixed-run FBMP exports (End Bent 1, End Bent 2, Pier) are embedded in this notebook and loaded for each support preset, so the project loads are available without an upload. When a newer FBMP run is registered, upload its XML in Cell 1 to replace the embedded one; the receipt shows whether the file matches the source register. Design basis: AASHTO LRFD Bridge Design Specifications 10th edition (2024), FDOT Structures Design Guidelines and Structures Detailing Manual January 2026, Standard Plans FY 2026-27 Index 455. Composite concrete-filled pipe, drivability and driving stresses, scour and the minimum tip elevation (geotechnical handoff) are outside this tool and appear as pending prerequisites. See `PILE_DESIGN.md` for the calculation basis and limits.
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
        {'cell_type': 'markdown', 'id': 'c5a1b2c3', 'metadata': {}, 'source': _lines(
            f'<a href="{COLAB}" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>')},
        {'cell_type': 'markdown', 'id': 'd6e5f6a7', 'metadata': {}, 'source': _lines(INTRO)},
        code(scroll, 'a8b8c9d0'), code(SETUP, SETUP_ID), code(CELL1, 'f2a2b3c4'), code(CELL2, 'f6a6b7c8')],
        'metadata': {'colab': {'name': NOTEBOOK, 'provenance': [], 'include_colab_link': True},
                     'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                     'language_info': {'name': 'python'}, 'title': 'Pile analysis and design'},
        'nbformat': 4, 'nbformat_minor': 5}


def cited_pages(repo):
    """Excerpt page images for the provisions this calculation cites, so Colab-built reports show them in the citation cards."""
    import sys
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    try:
        from report_cards import cited_page_files
    except ImportError:
        return []
    return cited_page_files(repo, references=['pile_design/data/references.json'], scan=['pile_design/*.py'])


def package_files(repo):
    files = [*repo.glob('pile_design/*.py'), *repo.glob('pile_design/data/*.json'), *repo.glob('pile_design/mathcad/*.png'),
             *repo.glob('pier_cap/*.py'), *repo.glob('pier_cap/data/*.json'),
             *repo.glob('report_cards/*.py'), *repo.glob('report_cards/*.js'), *repo.glob('report_cards/*.css'),
             *repo.glob('code_excerpts/excerpts.json'), *cited_pages(repo),
             repo / 'scripts' / 'mathcad_sheet.py', repo / 'scripts' / 'mathcad_plot.py', repo / 'scripts' / 'bpad_sheet.py',
             repo / 'cap_mathcad' / 'templates' / 'psbeam_check_summary_plot.bin', repo / 'cap_mathcad' / 'templates' / 'psbeam_check_summary_plot.json',
             repo / 'requirements-pier-cap-colab.txt']
    registered = registered_exports(repo)
    files += list(registered)
    missing = [f.relative_to(repo).as_posix() for f in files if not f.is_file()]
    if missing:
        raise FileNotFoundError('Portable package files are missing: ' + ', '.join(missing))
    for file, expected in registered.items():
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'{file.relative_to(repo).as_posix()} does not match the registered SHA-256 in pile_design/data/sources.json '
                             f'(file {actual[:16]}..., register {expected[:16]}...). Register the new export (source_register.csv, sources.json) before embedding it.')
    return sorted(files)


def registered_exports(repo):
    """{path: registered sha256} of the fixed-run FBMP exports embedded so the Colab presets carry the project loads."""
    sources = json.loads((repo / 'pile_design' / 'data' / 'sources.json').read_text(encoding='utf-8'))['sources']
    return {repo / sources[sid]['path']: sources[sid]['sha256'] for sid in EMBEDDED_XML}


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
