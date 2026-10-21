"""Build the portable wall-steel / annular-ring notebook with pinned source bytes."""
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
buffer=io.BytesIO()
with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    files=sorted((ROOT/'ring_wall').rglob('*.py'))+[ROOT/'ring_wall/_native/PROVENANCE.json']
    files+=sorted(p for p in (ROOT/'report_cards').glob('*') if p.suffix in ('.py','.js','.css'))  # report definition cards
    sys.path.insert(0,str(ROOT))
    from report_cards import cited_page_files
    files+=[ROOT/'code_excerpts'/'excerpts.json']+cited_page_files(ROOT,scan=['ring_wall/*.py'])  # citation excerpt cards
    for file in files:
        info=zipfile.ZipInfo(file.relative_to(ROOT).as_posix(),date_time=(2026,10,21,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,file.read_bytes())
payload=buffer.getvalue();digest=hashlib.sha256(payload).hexdigest()


def cell(kind,source):
    item=dict(cell_type=kind,metadata={},source=source.splitlines(keepends=True))
    if kind=='code':item.update(execution_count=None,outputs=[],metadata={'cellView':'form','jupyter':{'source_hidden':True},'scrolled':False})
    return item


INTRO='''<a href="https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Pier_Wall_Design.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

# Pier Wall Design

Choose **Runtime → Run all**. Edit the amber input cards, inspect **Live layout** and **3D reinforcement**, then click **Recalc**. Review **Tributary loads**, **Ring & weld detail**, **Wall steel**, **D/C checks** and **Ring spacing**. Edits clear calculated results and block new exports until Recalc. Green **Calc done** means current results; each check has its own status.

Wall checks cover minimum shrinkage/temperature reinforcement, spacing, cover, lap allowances and bend fit. Ring design assigns gross concrete self-weight between pile/row midplanes and wall edges as vertical force. The ring moment follows the pile-head rotational stiffness against the rigid-wall rotation, with the radial pile tolerance applied as a pile-group reaction redistribution (D-070, 21 October 2026); the former tributary-eccentricity moment is shown for comparison only. It checks full annular compression contact, concrete bearing, plate bending/shear, two continuous top/bottom fillet welds and adjacent base metal. No STM analysis is performed.

**Report and exports** includes an offline interactive HTML report, case JSON, check and ring-load CSVs, formula-based Mathcad and Blockpad sheets, a source ZIP and a complete bundle with verification records. The HTML report groups repeated checks: each method has readable equations, a schematic and numeric-substitution dropdown for every equation, and tables covering all locations. Exports are optional; Run all does not create them. Save your case before ending the runtime. Legacy cases with zero added gravity migrate with a visible notice; former STM inputs are discarded.

Native sheets use labeled fixed scalar units and the exported layout. Re-export after changing counts, bar size/coating or automatic spacing. Formula parity is verified; native application recalculation is not implied.

The starting geometry has end-cover and grid-clearance failures; all rings keep full contact. A failed contact check (for example with an imposed wall rotation) makes its bearing/plate/weld strength checks **PENDING**. Minimum steel and local connection checks do not establish wall strength load paths, splitting/breakout, row engagement, pile stiffness or pipe-shell adequacy. These open items remain in the check register.

The package and native-sheet helpers are embedded; no clone, token or Drive mount is required. Rerunning the workbench retains the active case.
'''
SETUP='''# @title 0 · Start the portable workbench
from pathlib import Path
import base64, hashlib, importlib, io, sys, zipfile
PACKAGE_SHA256 = "DIGEST"
PACKAGE = "ENCODED"
_payload=base64.b64decode(PACKAGE)
assert hashlib.sha256(_payload).hexdigest()==PACKAGE_SHA256, "Embedded source checksum failed"
ROOT=Path.cwd()/".ring_wall_runtime"/PACKAGE_SHA256[:12]
ROOT.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(io.BytesIO(_payload)) as _archive:
    for _name in _archive.namelist():
        _target=(ROOT/_name).resolve()
        if not _name.startswith(("ring_wall/", "report_cards/", "code_excerpts/")) or not _target.is_relative_to(ROOT.resolve()):
            raise ValueError("Unexpected embedded package path")
        _contents=_archive.read(_name)
        if _target.exists() and _target.read_bytes()!=_contents:
            raise RuntimeError("An extracted source was edited. Preserve your edits before using a fresh runtime folder.")
        _target.parent.mkdir(parents=True,exist_ok=True)
        if not _target.exists():_target.write_bytes(_contents)
try:
    from google.colab import output as colab_output
except ImportError:
    IN_COLAB=False
else:
    IN_COLAB=True
    import subprocess
    subprocess.run([sys.executable,"-m","pip","install","--quiet","ipywidgets==7.7.1","plotly==5.24.1","lxml>=4.9"],check=True)
    import ipywidgets as _widgets, plotly as _plotly
    from importlib.metadata import version as _version
    if _widgets.__version__!="7.7.1" or _version("ipywidgets")!="7.7.1" or _plotly.__version__!="5.24.1" or _version("plotly")!="5.24.1":
        raise RuntimeError("Save your case, restart the session, reload this browser page and Run all. This workbench uses the cap notebook widget/chart versions.")
    _widgets.register_comm_target(get_ipython().kernel)
    colab_output.enable_custom_widget_manager()
for _key in list(sys.modules):
    if _key=="ring_wall" or _key.startswith("ring_wall."):del sys.modules[_key]
if str(ROOT) in sys.path:sys.path.remove(str(ROOT))
sys.path.insert(0,str(ROOT));importlib.invalidate_caches()
from ring_wall.widgets import RingWallNotebook
print("Wall and ring workbench ready. Source checksum:",PACKAGE_SHA256[:12])
'''.replace('DIGEST',digest).replace('ENCODED',base64.b64encode(payload).decode())
WORK='''# @title 1 · Wall steel, tributary loads, ring bearing and weld design
from copy import deepcopy
_previous_app=globals().get("app")
_case=deepcopy(_previous_app.case) if _previous_app is not None else None
_saved_export=getattr(_previous_app,"last_export",None)
if _previous_app is not None:_previous_app.close()
app=RingWallNotebook(_case,export_root=Path.cwd()/"ring_wall_exports")
if _saved_export is not None and _saved_export.is_dir():
    app.last_export=_saved_export
    app.saved_html_button.disabled=app.saved_zip_button.disabled=False
    app.export_status.value="Saved downloads refer to the previous export. Generate again for the current calculation."
app.display()
'''
BASIS='''## Design basis

AASHTO LRFD BDS 10th edition (2024): bearing 5.6.5; minimum steel 5.10.6; detailing 5.10.2, 5.10.3 and 5.10.8; welds 6.13.3 and adjacent steel shear 6.13.5; depth to fixity for the default pile free length C10.7.3.13.4. Resistance factors and required cover remain visible inputs. The project spacing cap defaults to 12 inches. Bearing uses m = 1 with no supporting-area enhancement. The ring moment basis (pile-head stiffness against wall rotation; tolerance as pile-group redistribution) is decision D-070 in `project_current/decisions.md`; the superseded tributary-eccentricity moment is tabulated for comparison.

Background: [FHWA concrete bearing](https://www.fhwa.dot.gov/engineering/geotech/nhi18024.pdf), [Caltrans AASHTO fillet-weld example](https://dot.ca.gov/-/media/dot-media/programs/engineering/documents/bridge-design-practices/202210bdpchapter62steelplategirdersa11y.pdf), and [FDOT Structures Manual](https://www.fdot.gov/Structures/StructuresManual/CurrentRelease). Wall dimensions remain an earlier project study snapshot; verify them against current geometry.

Maintained source: `ring_wall/`; builder: `scripts/build_ring_wall_notebook.py`; verification: `tests/test_ring_wall*.py`.
'''
notebook=dict(cells=[cell('markdown',INTRO),cell('code',SETUP),cell('code',WORK),cell('markdown',BASIS)],
    metadata=dict(colab=dict(name='Pier_Wall_Design.ipynb',provenance=[]),kernelspec=dict(display_name='Python 3',language='python',name='python3'),language_info=dict(name='python',version='3.11')),nbformat=4,nbformat_minor=0)
path=ROOT/'Pier_Wall_Design.ipynb'
path.write_text(json.dumps(notebook,indent=1,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
print(path);print('Embedded source SHA-256:',digest)
