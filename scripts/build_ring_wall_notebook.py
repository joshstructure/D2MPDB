"""Build a reproducible portable Colab notebook from ring_wall/*.py.

Run from the repository root: python scripts/build_ring_wall_notebook.py
Embedded source is identical to the maintained Python package. No git clone,
pip install, token, Drive mount or network access is needed by the notebook.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
buffer=io.BytesIO()
with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for file in sorted((ROOT/'ring_wall').glob('*.py')):
        info=zipfile.ZipInfo('ring_wall/'+file.name,date_time=(2026,10,12,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,file.read_bytes())
payload=buffer.getvalue()
digest=hashlib.sha256(payload).hexdigest()
encoded=base64.b64encode(payload).decode()


def cell(kind,source):
    d=dict(cell_type=kind,metadata={},source=source.splitlines(keepends=True))
    if kind=='code':d.update(execution_count=None,outputs=[])
    return d


cells=[cell('markdown','''<a href="https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Ring_Supported_Wall_STM.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

# Ring-supported pier wall — strut-and-tie calculation

**D2 I-95 pedestrian bridge.** Choose **Runtime → Run all**. The complete calculation package is embedded in this notebook. No repository clone, credentials, uploads or installation are required.

Start with minimum reinforcement **each way, each face**, then matching end U-bars, dedicated arch ties/collectors, ring reactions, concrete/plate screens, and a ring-spacing study. Inputs appear in Colab forms and remain ordinary editable Python variables.

The report uses the cap/end-wall calculation style: blue discussion, amber inputs, green results, equation substitutions and a D/C register. The initial geometry is the earlier C006 wall study; current pier-cap material/pile data were checked separately. The default **23-in OD ring has cover/grid conflicts at 3-in pile tolerance**. An executed calculation is not a completed connection design.

**Workflow:** run setup → edit the three input cells → run calculation → review the spacing comparison → export the HTML report, case JSON, checks and ring-force CSV. After changing inputs, rerun all three input cells and everything below them. The minimum grid is not counted again as primary tie steel.
''')]
setup='''# @title 0 · Start the portable calculation
from pathlib import Path
import base64, hashlib, html, io, json, sys, zipfile
PACKAGE_SHA256 = "DIGEST"
PACKAGE = "ENCODED"
_payload = base64.b64decode(PACKAGE)
assert hashlib.sha256(_payload).hexdigest() == PACKAGE_SHA256, "Embedded package checksum failed"
ROOT = Path.cwd() / ".ring_wall_runtime" / PACKAGE_SHA256[:12]
ROOT.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(_payload)) as _z:
    for _name in _z.namelist():
        if not _name.startswith("ring_wall/") or ".." in Path(_name).parts:
            raise ValueError("Unexpected embedded package path")
    _z.extractall(ROOT)
for _key in list(sys.modules):
    if _key == "ring_wall" or _key.startswith("ring_wall."):
        del sys.modules[_key]
sys.path.insert(0, str(ROOT))
from ring_wall import default_case, analyze, render_report, export_results
from ring_wall.report import table, box, STYLE
from ring_wall.study import spacing_study
try:
    from IPython.display import HTML, Javascript, display
except ImportError:
    def show_html(value):
        print("HTML generated; available in the export folder.")
else:
    def show_html(value):
        display(HTML(value))
    try:
        import google.colab
    except ImportError:
        pass
    else:
        display(Javascript('google.colab.output.setIframeHeight(0, true, {maxHeight: 60000})'))
case = default_case()
print("Ring wall calculation ready. Source checksum:", PACKAGE_SHA256[:12])
'''.replace('DIGEST',digest).replace('ENCODED',encoded)
cells.append(cell('code',setup))
cells.append(cell('markdown','''## Inputs

Wall self-weight only unless additional downward gravity is entered. This is not a lateral-wall, collision, pile-foundation or cap-load design. Ring elevations are measured to the **top bearing surface**, from the wall bottom. Piles are centered along the wall and through its thickness. For advanced parameters (resistance factors, equivalent node width, finite-node height), edit `case` at the end of the input cells.
'''))
cells.append(cell('code','''# @title 1 · Wall, piles, materials and gravity
wall_length_in = 213.0 # @param {type:"number"}
wall_thickness_in = 36.0 # @param {type:"number"}
wall_height_in = 172.375 # @param {type:"number"}
pile_count = 4 # @param {type:"integer"}
pile_spacing_in = 60.0 # @param {type:"number"}
pile_od_in = 20.0 # @param {type:"number"}
pile_effective_wall_in = 0.475 # @param {type:"number"}
pile_tolerance_in = 3.0 # @param {type:"number"}
concrete_fc_ksi = 5.5 # @param {type:"number"}
rebar_fy_ksi = 60.0 # @param {type:"number"}
concrete_density_kcf = 0.150 # @param {type:"number"}
gamma_dc = 1.25 # @param {type:"number"}
additional_service_gravity_ksf = 0.0 # @param {type:"number"}
gamma_additional = 1.75 # @param {type:"number"}
case.update(length_in=wall_length_in, thickness_in=wall_thickness_in,
    height_in=wall_height_in, pile_count=pile_count, pile_spacing_in=pile_spacing_in,
    pile_od_in=pile_od_in, pile_t_effective_in=pile_effective_wall_in,
    placement_tolerance_in=pile_tolerance_in, fc_ksi=concrete_fc_ksi,
    fy_ksi=rebar_fy_ksi, density_kcf=concrete_density_kcf, gamma_dc=gamma_dc,
    additional_service_ksf=additional_service_gravity_ksf, gamma_additional=gamma_additional)
print("Wall and material inputs applied.")
'''))
cells.append(cell('code','''# @title 2 · Minimum grid and matching U-bars
clear_cover_in = 3.0 # @param {type:"number"}
maximum_aggregate_in = 0.75 # @param {type:"number"}
grid_bar_number = 5 # @param [4,5,6,7,8] {type:"raw"}
automatically_select_grid_spacing = True # @param {type:"boolean"}
manual_grid_spacing_in = 5.0 # @param {type:"number"}
spacing_increment_in = 0.5 # @param {type:"number"}
u_bar_straight_leg_in = 72.0 # @param {type:"number"}
bar_coating = "uncoated" # @param ["uncoated","epoxy","unknown"]
additional_primary_bar_number = 5 # @param [4,5,6,7,8] {type:"raw"}
horizontal_tie_bars_per_face = 1 # @param {type:"integer"}
collector_bars_per_face = 1 # @param {type:"integer"}
case.update(cover_in=clear_cover_in, aggregate_in=maximum_aggregate_in,
    grid_bar=grid_bar_number, auto_grid_spacing=automatically_select_grid_spacing,
    grid_spacing_in=manual_grid_spacing_in, spacing_increment_in=spacing_increment_in,
    u_leg_in=u_bar_straight_leg_in, coating=bar_coating,
    primary_bar=additional_primary_bar_number,
    primary_bars_per_face=horizontal_tie_bars_per_face,
    hanger_bars_per_face=collector_bars_per_face)
print("Grid, U-bar and additional tie inputs applied. No double-counting of grid steel.")
'''))
cells.append(cell('code','''# @title 3 · Ring spacing, section and arch geometry
first_ring_top_in = 6.0 # @param {type:"number"}
vertical_ring_spacing_ft = 3.0 # @param {type:"number"}
number_of_ring_rows = 5 # @param {type:"integer"}
ring_inside_diameter_in = 20.125 # @param {type:"number"}
ring_outside_diameter_in = 23.0 # @param {type:"number"}
ring_thickness_in = 0.75 # @param {type:"number"}
ring_steel_fy_ksi = 50.0 # @param {type:"number"}
effective_bearing_fraction = 0.50 # @param {type:"number"}
arch_rise_in = 10.0 # @param {type:"number"}
arch_segment_count = 4 # @param {type:"integer"}
tie_centroid_above_ring_in = 2.0 # @param {type:"number"}
node_height_in = 4.0 # @param {type:"number"}
equivalent_node_width_in = 16.0 # @param {type:"number"}
case.update(first_ring_in=first_ring_top_in, ring_spacing_in=vertical_ring_spacing_ft*12,
    ring_count=number_of_ring_rows, ring_id_in=ring_inside_diameter_in,
    ring_od_in=ring_outside_diameter_in, ring_t_in=ring_thickness_in,
    ring_fy_ksi=ring_steel_fy_ksi, bearing_fraction=effective_bearing_fraction,
    arch_rise_in=arch_rise_in, arch_panels=arch_segment_count,
    tie_offset_in=tie_centroid_above_ring_in, node_height_in=node_height_in,
    node_width_in=equivalent_node_width_in)
print("Ring and arch inputs applied. Bearing fraction is an assumption to investigate.")
'''))
cells.append(cell('code','''# @title 4 · Calculate and display the design report
# Clear stale results before validation: a failed rerun must not export an old case.
result = None
report_html = None
result = analyze(case)
report_html = render_report(result)
show_html(report_html)
print(result["overall"])
print("Equilibrium residuals:", result["totals"])
'''))
cells.append(cell('code','''# @title 5 · Compare rings at 2, 2½, 3, 3½ and 4 ft spacing
if result is None or result["case"] != case:
    raise RuntimeError("Calculate the current inputs first.")
spacing_results = spacing_study(case)
_rows = []
for item in spacing_results:
    if "error" in item:
        _rows.append([item["spacing_in"]/12, item["error"], "", "", "", "", ""])
    else:
        _rows.append([f'{item["spacing_in"]/12:g} ft', item["ring_count"],
            f'#{item["grid_bar"]} @ {item["grid_spacing_in"]:g} in',
            f'{item["max_ring_kip"]:.3f}',f'{item["max_tie_kip"]:.3f}',
            f'{item["minimum_angle"]:.2f}',", ".join(item["failed_checks"]) or "No equation failures; open checks remain"])
study_html = '<style>'+STYLE+'</style>'+box("discussion", "Ring-spacing comparison",
    "The top row count is selected to leave room for the entered arch. First-ring elevation, section and arch rise are held fixed. "
    "A short terminal band may control the minimum cage. This compares assumed strength allocations; it does not establish reaction sharing.")+table(
    ["Spacing","Rows","Uniform grid / face","Max ring (kip)","Max bay tie (kip)","Min angle (°)","Failed checks"], _rows)
show_html(study_html)
'''))
cells.append(cell('code','''# @title 6 · Export the current case, report and ring-force handoff
if result is None or result["case"] != case:
    raise RuntimeError("Current inputs differ from calculated results. Recalculate before export.")
EXPORT = Path.cwd() / "ring_wall_exports"
export_paths = export_results(result, EXPORT)
(EXPORT / "ring_spacing_study.json").write_text(json.dumps(spacing_results, indent=2), encoding="utf-8")
(EXPORT / "ring_spacing_study.html").write_text(study_html, encoding="utf-8")
bundle = EXPORT / "Ring_Wall_STM_Exports.zip"
with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
    for path in export_paths + [EXPORT / "ring_spacing_study.json", EXPORT / "ring_spacing_study.html"]:
        z.write(path, path.name)
print("Created:", bundle)
try:
    from google.colab import files
    import ipywidgets as widgets
except ImportError:
    print("Open the export folder for the report, case, CSV checks and connection demands.")
else:
    download = widgets.Button(description="Download calculation ZIP", layout=widgets.Layout(width="240px"))
    download.on_click(lambda _: files.download(str(bundle)))
    display(download)
'''))
cells.append(cell('markdown','''## Design basis and interpretation

- **AASHTO LRFD, 10th edition (2024):** 5.5.4.2, 5.8.2.2–5.8.2.6, 5.10.2, 5.10.3.1.1, 5.10.6, 5.10.8.2.1 and 5.10.8.4.3. Equations are identified in the report. Normalweight concrete and Grade 60 defaults.
- [FHWA-NHI-17-071](https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf): background STM examples; its older code edition does not override the 2024 equation basis.
- [FDOT Structures Manual](https://www.fdot.gov/structures/structuresmanual/currentrelease): verify governing project edition, modifications, exposure/cover, reinforcement and weld detailing.
- **Unresolved:** actual ring-row compatibility; 3-D concrete load paths, splitting and breakout; all tie/collector anchorage; local wall-end STM; welds and pipe-shell response; fatigue where applicable; lateral and other project load cases. The notebook cannot produce an overall design PASS while these remain open.

Maintained source: `ring_wall/`; builder: `scripts/build_ring_wall_notebook.py`; tests: `tests/test_ring_wall.py`. The embedded source checksum is printed at startup.
'''))
notebook=dict(cells=cells,metadata=dict(colab=dict(name='Ring_Supported_Wall_STM.ipynb',provenance=[]),
    kernelspec=dict(display_name='Python 3',language='python',name='python3'),
    language_info=dict(name='python',version='3.11')),nbformat=4,nbformat_minor=0)
path=ROOT/'Ring_Supported_Wall_STM.ipynb'
path.write_text(json.dumps(notebook,indent=1,ensure_ascii=False)+'\n',encoding='utf-8')
print(path)
print('Embedded source SHA-256:',digest)
