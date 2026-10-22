"""Install the verified 1/2-in ring candidate and record its bounded adoption (D-079).

Runs with the project .venv Python (no FreeCAD). Reads the headless build record,
backs up the current model, writes the candidate bytes in place, and records the
revision in the FreeCAD README, update report, API notes, manifest, decisions and
source register. The assumptions register is re-judged by hand afterwards.
"""
from pathlib import Path
import json,re,hashlib,shutil,zipfile,os,sys
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad'
OUT=ROOT/'.validation/pier-wall-half-inch';EVID=MAIN/'evidence/2026-10-22-ring-plate-half-inch'
sys.path.insert(0,str(ROOT))
from scripts.register_update import update_rows
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def prepend(p,text,heading=False):
    b=p.read_bytes();nl=b'\r\n' if b'\r\n' in b else b'\n';addition=text.replace('\n',nl.decode()).encode()
    if heading:
        first,rest=b.split(nl,1);b=first+nl+nl+addition+rest.lstrip(b'\r\n')
    else:b=addition+nl+b
    p.write_bytes(b)

qa=json.loads((OUT/'build.json').read_text());snapshot=json.loads((OUT/'case-snapshot.json').read_text())
assert qa['status']=='VERIFIED' and qa['cold_reopen'] and qa['native_edit_restore'] and qa['ordinary_native_recompute']
assert qa['validation']['status']=='PASS' and qa['cold_reopen_validation']['status']=='PASS'
assert qa['file_preservation']['status']=='PASS' and qa['snapshot_sha256']==snapshot['sha256']
manifest=json.loads((MAIN/'manifest.json').read_text());model=MAIN/manifest['model']['path']
assert sha(model)==qa['source_sha256']==manifest['model']['sha256']
assert sha(qa['candidate'])==qa['candidate_sha256']
assert not (EVID/'adoption-summary.json').exists(),'Inspect completed adoption before retry'
for p,h in manifest['runtime_files'].items():assert sha(MAIN/p)==h,p
calc=ROOT/'project_current/pier_wall/selected_case.json';calc_hash=sha(calc);assert calc_hash==snapshot['sha256']
tracker=ROOT/'project_current/coherence/Coherence_Tracker.xlsx';tracker_hash=sha(tracker)
journal=ROOT/'journal/D2_I95_Project_Journal.bpad';journal_hash=sha(journal)
decision=ROOT/'project_current/decisions.md';decbytes=decision.read_bytes()
assert max(map(int,re.findall(rb'\| D-(\d+) \|',decbytes)))==78
register=ROOT/'project_current/source_register.csv'
tracked=[MAIN/'manifest.json',MAIN/'README.md',MAIN/'runtime/API.md',MAIN/'Open_Current_Bridge.FCMacro',
         MAIN/'evidence/Model-update-report.txt',register,decision]
guards={p:sha(p) for p in tracked}
backup=MAIN/'archive/B4-before-ring-plate-half-inch-20261022.FCStd'
records=MAIN/'archive/B4-before-ring-plate-half-inch-record-20261022.zip'
if backup.exists():assert sha(backup)==qa['source_sha256']
else:shutil.copy2(model,backup)
if not records.exists():
    with zipfile.ZipFile(records,'w',zipfile.ZIP_DEFLATED) as z:
        for p in tracked:z.write(p,p.relative_to(ROOT).as_posix())
        for rel in manifest['runtime_files']:z.write(MAIN/rel,rel)
EVID.mkdir(parents=True,exist_ok=True)
for src,dst in [(OUT/'build.json','geometry-verification.json'),(OUT/'case-snapshot.json','calculation-snapshot.json'),
    (OUT/'build_half_inch_rings.py','build_candidate.py'),(Path(__file__),'adopt_candidate.py')]:
    shutil.copy2(src,EVID/dst)
shutil.copy2(calc,EVID/'selected-case-at-transfer.json')
assert all(sha(p)==h for p,h in guards.items())
candidate_bytes=Path(qa['candidate']).read_bytes();old_bytes=backup.read_bytes()
assert sha(model)==qa['source_sha256'] and sha(backup)==qa['source_sha256']
try:
    with model.open('r+b') as f:
        f.write(candidate_bytes);f.truncate();f.flush();os.fsync(f.fileno())
    assert sha(model)==qa['candidate_sha256']
except Exception:
    with model.open('r+b') as f:f.write(old_bytes);f.truncate();f.flush();os.fsync(f.fileno())
    assert sha(model)==qa['source_sha256']
    raise
installation=dict(status='INSTALLED',method='Guarded in-place binary write with exact-byte backup',
                  backup=str(backup),old_sha256=qa['source_sha256'],new_sha256=qa['candidate_sha256'])
v=qa['validation'];cv=qa['cold_reopen_validation'];pairs=next(c['pairs'] for c in v['checks'] if c['name']=='nominal_steel_intersections')
b,a=qa['before'],qa['after']
scope=('Set the twenty pier wall annular ring plates of the CAD model to 1/2 in thick (3/4 in under D-076), '
       'matching the selected D-078 calculation case.')
summary=(f"Live input RingThickness 0.5 in; every ring solid 23-in OD x 20.125-in ID x 0.5-in thick with its bottom face raised 1/4 in. "
         f"Ring tops stay at 6, 42, 78, 114 and 150 in above the retained wall bottom; diameters, the two recorded 5/16-in fillets, "
         f"the 124 bars, the wall, the piles and all {qa['objects']-len(qa['changed_objects'])} unrelated objects are unchanged. "
         f"Ring steel {a['ring_weight_lb']:.1f} lb ({b['ring_weight_lb']:.1f} lb before, 490 pcf). The immutable case snapshot on "
         f"PierWallSteelInputs now names the D-078 case ({snapshot['sha256'][:8]}; only ring_t_in differs from the D-075 snapshot; "
         f"grid #5 at 11 in and the RING-GRID failure unchanged).")
limits=('The plates were produced by the ordinary native recompute of the thickness input (the user workflow); native edit round trip, '
        'file-level record preservation and cold reopen verified. RING-GRID and all source scope limitations remain open without '
        'rejudgment; U bends and contact lap routing remain CAD detailing assumptions; weld solids are not modeled; PW marks are '
        'instance identifiers; SDM drawing marks, drawing exports, fabrication and engineering acceptance remain pending. '
        'Existing bearing-fit and other project findings remain. No calculation, journal or tracker changes.')
adoption=dict(status='ADOPTED_CAD_RING_PLATE_HALF_INCH_RING_GRID_TOLERANCE_REMAINS_OPEN',decision='D-079',date='2026-10-22',
    scope=scope,summary=summary,limitations=limits,model_sha256=sha(model),previous_model_sha256=qa['source_sha256'],
    objects=qa['objects'],changed_objects=qa['changed_objects'],protected_existing_objects=qa['protected_objects'],
    checks_passed=len(v['checks']),cold_reopen_checks_passed=len(cv['checks']),pairs_checked=pairs,
    native_edit_restore=True,ordinary_native_recompute=True,cold_reopen=True,file_preservation=qa['file_preservation'],
    ring_thickness_in=dict(before=b['ring_thickness_in'],after=a['ring_thickness_in']),
    ring_tops_in_above_wall_bottom=sorted({round(r['top_above_wall_bottom_in'],6) for r in a['rings'].values()}),
    ring_weight_lb=dict(before=b['ring_weight_lb'],after=a['ring_weight_lb']),
    bar_count=v['bar_count'],rings=v['rings'],minimum_bar_cover_in=v['minimum_bar_cover_in'],
    reinforcement_weight_lb=v['steel_weight_lb'],
    calculation_snapshot_sha256=snapshot['sha256'],previous_calculation_snapshot_sha256=manifest.get('current_update',{}).get('calculation_snapshot_sha256','216b28ca0ef434984865c467ee6dce07100401f1c7a613304349a09a61c5cb9c'),
    source_calculation_unchanged_by_this_task=True,journal_unchanged=True,tracker_unchanged=True,installation=installation)
dump(EVID/'adoption-summary.json',adoption)
prepend(MAIN/'README.md','## D-079: 1/2-in pier wall ring plates, 22 October 2026\n\n'+scope+' '+summary+'\n\n'+
    f'Native geometry/cover and {pairs:,} intersecting-box steel pairs pass with no positive overlaps ({len(v["checks"])} checks before saving, {len(cv["checks"])} after cold reopen). '+limits+
    ' See [adoption](evidence/2026-10-22-ring-plate-half-inch/adoption-summary.json) and [verification](evidence/2026-10-22-ring-plate-half-inch/geometry-verification.json).\n\n',True)
prepend(MAIN/'evidence/Model-update-report.txt','D-079 - 1/2-IN PIER WALL RING PLATES, 22 OCTOBER 2026\n\n'+scope+'\n\n'+summary+'\n\n'+limits+'\n\n'+
    f'{len(v["checks"])} checks PASS, {pairs} candidate pairs, zero positive steel overlaps. Native edit round trip, ordinary recompute, cold reopen and {qa["protected_objects"]} protected existing objects verified. Nominal rebar {v["steel_weight_lb"]:.3f} lb (unchanged); rings {a["ring_weight_lb"]:.3f} lb (490 pcf).\n\nPREVIOUS UPDATES (historical)\n')
api=MAIN/'runtime/API.md';ab=api.read_bytes();nl=b'\r\n' if b'\r\n' in ab else b'\n'
addition=('\n\n## 1/2-in pier wall ring plates (D-079)\n\n'
          'No controller change. `PierWallSteelInputs.RingThickness` reads 0.5 in; the twenty `PierWallRingP*R*` solids follow it through '
          'the ordinary native recompute (ring tops fixed by `FirstRingTop` and `RingSpacing`, so a thickness change moves only the bottom '
          'face). `SourceCaseJSON`, `SourceCaseSHA256`, `SourceFailuresJSON`, `SourcePath` and `EngineeringStatus` name the D-078 case. '
          +limits+'\n')
api.write_bytes(ab+addition.replace('\n',nl.decode()).encode())
manifest['previous_update']=manifest['current_update']
manifest['current_update']=dict(date='2026-10-22',decision='D-079',scope=scope,summary='evidence/2026-10-22-ring-plate-half-inch/adoption-summary.json',
                                previous_model_sha256=qa['source_sha256'],calculation_snapshot_sha256=snapshot['sha256'],follow_up=limits)
manifest['model'].update(sha256=sha(model),bytes=model.stat().st_size,objects=qa['objects'])
manifest['updated_on']='2026-10-22'
manifest['known_review_status']='D-079: 1/2-in ring plates PASS; source RING-GRID tolerance failure remains. '+limits+' Prior: '+manifest['known_review_status']
manifest['runtime_changes'].append('D-079: no controller change; ring plate thickness input set to the selected D-078 case (1/2 in) through the native recompute; provenance strings updated.')
for rel in ['runtime/API.md']:manifest['runtime_files'][rel]=sha(MAIN/rel)
for p in (backup,records):manifest['archive_files'][p.relative_to(MAIN).as_posix()]=sha(p)
for p in [*EVID.iterdir(),MAIN/'evidence/Model-update-report.txt']:manifest['evidence_files'][p.relative_to(MAIN).as_posix()]=sha(p)
dump(MAIN/'manifest.json',manifest)
nl=b'\r\n' if b'\r\n' in decbytes else b'\n';anchor=nl+nl+b'The current journal';assert anchor in decbytes
row=('| D-079 | 2026-10-22 | Set the CAD model pier wall annular ring plates to 1/2 in thick, matching the selected D-078 case; D-076 had placed them at 3/4 in. | '
     'Follows the user\'s D-078 selection of the 1/2-in plate (the 3/4-in plate was not strength-governed; 7/16 in is the thinnest standard plate with every check at or under 0.95 of its limit). '
     'The CAD model (CAD-MODEL) and the ring wall case (PIER-WALL-CASE) disagreed on plate thickness since D-078; this closes that gap. '
     +summary+' '+limits+f' {len(v["checks"])} geometry/cover/link/spacing/intersection checks PASS before saving and {len(cv["checks"])} after cold reopen; '
     f'{qa["protected_objects"]} existing objects preserved. See [CAD adoption](geometry/freecad/evidence/2026-10-22-ring-plate-half-inch/adoption-summary.json). |')
decision.write_bytes(decbytes.replace(anchor,nl+row.encode()+anchor,1))
note='D-079: '+scope+' '+summary+' '+limits+' Prior:'
rows=json.loads(json.dumps({sid:dict(sha256=sha(MAIN/'manifest.json' if sid=='CAD-RUNTIME' else MAIN/'evidence/Model-update-report.txt') if sid!='CAD-MODEL' else sha(model),
                                      registered_on='2026-10-22',notes=note) for sid in ('CAD-MODEL','CAD-RUNTIME','CAD-REPORT')}))
from scripts.register_update import read_rows
current=read_rows()
rows['CAD-MODEL']['scope']=current['CAD-MODEL']['scope']+'; D-079 1/2-in ring plates matching the D-078 case'
rows['CAD-MODEL']['status']='Current - pier wall steel with 1/2-in rings; ring-grid tolerance and bearing fit unresolved'
update_rows(rows,prepend_notes=True)
assert sha(tracker)==tracker_hash and sha(calc)==calc_hash and sha(journal)==journal_hash
paths=sorted({p.relative_to(ROOT).as_posix() for p in [model,backup,records,*tracked,*EVID.iterdir()]})
dump(OUT/'adoption.json',dict(status=adoption['status'],commit_paths=paths))
(OUT/'commit-paths.txt').write_text('\n'.join(paths)+'\n')
print(json.dumps({k:v for k,v in adoption.items() if k not in ('file_preservation',)},indent=2))
