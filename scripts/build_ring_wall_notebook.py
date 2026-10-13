"""Build the portable live workbench with the maintained ring_wall package."""
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
buffer=io.BytesIO()
with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for file in sorted((ROOT/'ring_wall').glob('*.py')):
        info=zipfile.ZipInfo('ring_wall/'+file.name,date_time=(2026,10,12,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,file.read_bytes())
payload=buffer.getvalue()
digest=hashlib.sha256(payload).hexdigest()
encoded=base64.b64encode(payload).decode()


def cell(kind,source):
    item=dict(cell_type=kind,metadata={},source=source.splitlines(keepends=True))
    if kind=='code':
        item.update(execution_count=None,outputs=[])
        item['metadata']={'cellView':'form','jupyter':{'source_hidden':True},'scrolled':False}
    return item


cells=[cell('markdown','''<a href="https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Ring_Supported_Wall_STM.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

# Ring-supported pier wall — live STM workbench

Choose **Runtime → Run all** to open the starting calculation. Expand **Inputs**, edit the case, inspect the live layout, click **Recalc**, and review **Cone transfer**, **Ring forces**, **Struts & ties**, **Reinforcement**, **D/C checks** and **Ring spacing**. Zoom and hover over the plots; filter ring-force tables by row and sort the check register.

The controls follow the cap-design notebook: amber input cards, live plots, output tables, and a floating Recalc button. Edits clear calculated outputs until Recalc. Green **Calc done** means results match the inputs, not that the design passes. Rerunning the workbench preserves the active inputs.

Use the labeled panel buttons to switch views. The active panel has a blue button and its name above the content. If you have an older notebook open, save your case, reopen this published notebook, and **Run all** to load the updated workbench.

**Report and exports** is an optional panel at the bottom. **Generate calculation report** saves/downloads a standalone HTML report. **Export case + checks ZIP** includes inputs, results, report, CSV tables and the spacing study. Running the notebook does not export files. Save your case before ending the runtime, then reload `ring_wall_case.json` with **Load saved case** next time.

The package is embedded. Colab setup automatically installs the same widget/chart versions used by the cap notebook; no repository clone, Drive mount or token is needed. Local Jupyter needs ipywidgets and Plotly (Plotly 6 also needs anywidget).

The default **Broad-face cone transfer (trial)** projects an ACI-style 1.5 H:1 V breakout envelope from the rings to the two broad wall faces. The live 3-D view and tables show the transfer elevation, trial compression links and additional transverse-tie demands. The intersections create no extra reaction or span reduction; finite interior nodes, cover, tie anchorage and ring breakout resistance remain open.

This remains a **preliminary gravity study**. The default rings have end-cover and face-grid conflicts, and the raised trial node region causes arch-fit failures in rows 1–4. Minimum grid steel is not counted again as primary tie steel. Select **Original ring level** to compare the earlier support geometry.
''')]
setup='''# @title 0 · Start the portable workbench
from pathlib import Path
import base64, hashlib, importlib, io, sys, zipfile
PACKAGE_SHA256 = "DIGEST"
PACKAGE = "ENCODED"
_payload = base64.b64decode(PACKAGE)
assert hashlib.sha256(_payload).hexdigest() == PACKAGE_SHA256, "Embedded package checksum failed"
ROOT = Path.cwd() / ".ring_wall_runtime" / PACKAGE_SHA256[:12]
ROOT.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(_payload)) as _z:
    for _name in _z.namelist():
        _target = (ROOT / _name).resolve()
        if not _name.startswith("ring_wall/") or not _target.is_relative_to(ROOT.resolve()):
            raise ValueError("Unexpected embedded package path")
        _contents = _z.read(_name)
        if _target.exists() and _target.read_bytes() != _contents:
            raise RuntimeError("An extracted package file was edited. Preserve your edits before starting a fresh runtime folder.")
        _target.parent.mkdir(parents=True, exist_ok=True)
        if not _target.exists():
            _target.write_bytes(_contents)
try:
    from google.colab import output as colab_output
except ImportError:
    IN_COLAB = False
else:
    IN_COLAB = True
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "ipywidgets==7.7.1", "plotly==5.24.1"], check=True)
    import ipywidgets as _widgets
    import plotly as _plotly
    from importlib.metadata import version as _installed_version
    if _widgets.__version__ != "7.7.1" or _installed_version("ipywidgets") != "7.7.1" or _plotly.__version__ != "5.24.1" or _installed_version("plotly") != "5.24.1":
        raise RuntimeError("Save your case, use Runtime → Restart session, reload this browser page, then Run all. The live plots require the cap notebook's widget/chart versions.")
    _widgets.register_comm_target(get_ipython().kernel)
    colab_output.enable_custom_widget_manager()
for _key in list(sys.modules):
    if _key == "ring_wall" or _key.startswith("ring_wall."):
        del sys.modules[_key]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))
importlib.invalidate_caches()
from ring_wall.widgets import RingWallNotebook
print("Ring wall workbench ready. Source checksum:", PACKAGE_SHA256[:12])
'''.replace('DIGEST',digest).replace('ENCODED',encoded)
cells.append(cell('code',setup))
cells.append(cell('code','''# @title 1 · Work with live plots and output tables
from copy import deepcopy
_previous_app = globals().get("app")
_case = deepcopy(_previous_app.case) if _previous_app is not None else None
_saved_export = getattr(_previous_app, "last_export", None)
if _previous_app is not None:
    _previous_app.close()
app = RingWallNotebook(_case, export_root=Path.cwd() / "ring_wall_exports")
if _saved_export is not None and _saved_export.is_dir():
    app.last_export = _saved_export
    app.saved_html_button.disabled = app.saved_zip_button.disabled = False
    app.export_status.value = "Saved-download buttons still refer to the previous export. Generate again to save the current calculation."
app.display()
'''))
cells.append(cell('markdown','''## Design basis and interpretation

- **AASHTO LRFD, 10th edition (2024):** 5.5.4.2, 5.8.2.2–5.8.2.6, 5.10.2, 5.10.3.1.1, 5.10.6, 5.10.8.2.1 and 5.10.8.4.3. Equations and substitutions remain in the D/C register and report.
- [FHWA-NHI-17-071](https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf): background examples; its older edition does not override the 2024 equation basis.
- [FDOT Structures Manual](https://www.fdot.gov/structures/structuresmanual/currentrelease): confirm project edition, exposure/cover, reinforcement and weld detailing.
- **Unresolved:** actual row engagement/compatibility; 3-D concrete paths, splitting and breakout; all tie/collector anchorage; wall-end STM; welds, splices and pipe-shell response; applicable fatigue and additional loads. No overall design PASS is possible while these remain open.

Wall dimensions are an earlier C006 snapshot, not a fresh CAD import. Ring bearing and plate results are screens. Mid-height bands are assumed strength allocations, not a compatibility solution.

Maintained source: `ring_wall/`; builder: `scripts/build_ring_wall_notebook.py`; tests: `tests/test_ring_wall.py` and `tests/test_ring_wall_widgets.py`.
'''))
notebook=dict(cells=cells,metadata=dict(colab=dict(name='Ring_Supported_Wall_STM.ipynb',provenance=[]),
    kernelspec=dict(display_name='Python 3',language='python',name='python3'),language_info=dict(name='python',version='3.11')),
    nbformat=4,nbformat_minor=0)
path=ROOT/'Ring_Supported_Wall_STM.ipynb'
path.write_text(json.dumps(notebook,indent=1,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
print(path)
print('Embedded source SHA-256:',digest)
