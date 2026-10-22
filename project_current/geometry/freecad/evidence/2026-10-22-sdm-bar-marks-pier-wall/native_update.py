"""D-083 native step (run with freecadcmd): write the SDM bar marks of the pier
wall reinforcement (PW- controller identifiers -> 5G1 verticals, 5G2
horizontals, 5G3 end U returns) on a disposable copy, and record on the pier
wall inputs that the drawing marks are written.

As the D-042 and D-060 jobs (CAD_AI/reports/sdm-bar-marks-20261016 and
sdm-bar-marks-pier-cheeks-20261019): never opens or saves the registered model
itself.  Output: NativeSaved.FCStd (a native save of the disposable copy, used
only as the source of the changed property records), mark-changes.json and
native-update.json.
"""
from pathlib import Path
import sys, json, hashlib, shutil, traceback
sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = Path('C:/github/D2MPDB')
BASE = REPO/'project_current/geometry/freecad'
MAIN = BASE/'B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd'
sys.path.insert(0, str(BASE/'runtime'))
sys.path.insert(0, str(REPO))
import FreeCAD as App
from freecad_tools import cap_cages, mse, bridge, drainage_trial, adopt_drainage, current_source, design_steel, pedestal_ubars, pedestal_edges, pedestal_contact, backwall_extensions, backwall_top, mse_revision, mse_corrections, mse_wall_tops, cheek_steel, lug_wwr, deck_edge_details, return_cheek_details, standard_chamfers, end_bent_closure, geotechnical_straps, cheek_hooks, pier_cheeks, level_seats, pier_wall_rings  # noqa: F401,E501
from substructure_drawings import freecad_marks
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
log = {'status': 'PREPARED'}
try:
    manifest = json.loads((REPO/'substructure_drawings/output/manifest.json').read_text(encoding='utf-8'))
    assert sha(MAIN) == manifest['model_sha256'], 'The DXF register was not generated from the registered model'
    assert not (OUT/'NativeSaved.FCStd').exists(), 'Inspect the prior run before retrying'
    if not (OUT/'Before.FCStd').exists():
        shutil.copy2(MAIN, OUT/'Before.FCStd')
    assert sha(OUT/'Before.FCStd') == manifest['model_sha256']
    shutil.copy2(OUT/'Before.FCStd', OUT/'Disposable.FCStd')
    register = freecad_marks.load_register()
    wall = sorted(n for n in register if n.startswith('PierWallSteel'))
    assert len(wall) == 124, len(wall)
    doc = App.openDocument(str(OUT/'Disposable.FCStd'))
    needed = list(register) + ['CageEB1Quantities', 'CagePierQuantities', 'CageEB2Quantities', 'PierWallSteelInputs', 'PierWallSteelQuantities']
    missing = [n for n in needed if doc.getObject(n) is None or doc.getObject(n).Proxy is None]
    assert not missing, ('Controllers did not restore', missing[:10])
    unrestored = sorted(o.Name for o in doc.Objects if 'Proxy' in o.PropertiesList and o.Proxy is None)
    invalid_before = sorted(o.Name for o in doc.Objects if 'Invalid' in o.State)
    touched_before = sorted(o.Name for o in doc.Objects if 'Touched' in o.State)
    names = [o.Name for o in doc.Objects]
    before = bridge.source_state(doc, names)
    inp = doc.getObject('PierWallSteelInputs')
    status_before = inp.MarkStatus
    labels_before = {n: doc.getObject(n).Label for n in wall}
    record = freecad_marks.apply(doc, register)
    failures = freecad_marks.verify(doc, register)
    assert not failures, failures[:10]
    after = bridge.source_state(doc, names)
    geometry_changed = sorted(n for n in names if before[n] != after[n])
    assert not geometry_changed, geometry_changed[:10]
    assert not record['pending_objects_after'], record['pending_objects_after'][:10]
    assert {c['object'] for c in record['changes']} == set(wall), 'Only the 124 pier wall bars were expected to change'
    assert all(doc.getObject(n).Label == labels_before[n] for n in wall), 'Bar labels moved'
    assert record['mark_status'] and record['mark_status']['object'] == 'PierWallSteelInputs'
    probe = doc.getObject(record['schedules'][0])
    log.update(status='PASS', before_sha256=sha(OUT/'Before.FCStd'), objects=len(names),
               invalid_before=invalid_before, touched_before=touched_before, proxies_not_restored=unrestored,
               invalid_after=sorted(o.Name for o in doc.Objects if 'Invalid' in o.State),
               source_state_unchanged=True, labels_unchanged=True, verify_failures=failures,
               mark_status_before=status_before, mark_status_after=inp.MarkStatus,
               marks_after={m: sum(1 for n in wall if doc.getObject(n).Mark == m) for m in ('5G1', '5G2', '5G3')},
               probe_cell=dict(sheet=probe.Name, content=probe.getContents('A2'), value=str(probe.get('A2'))),
               **{k: v for k, v in record.items() if k != 'changes'})
    doc.saveAs(str(OUT/'NativeSaved.FCStd'))
    log['native_saved_sha256'] = sha(OUT/'NativeSaved.FCStd')
    (OUT/'mark-changes.json').write_text(json.dumps(record['changes'], indent=1) + '\n')
    App.closeDocument(doc.Name)
except Exception:
    log['status'] = 'FAIL'
    log['traceback'] = traceback.format_exc()
(OUT/'native-update.json').write_text(json.dumps(log, indent=2) + '\n')
print(json.dumps({k: v for k, v in log.items() if k != 'traceback'}, indent=2))
if log['status'] != 'PASS':
    print(log.get('traceback', ''))
