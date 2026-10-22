"""Install verified CAD detail and record its bounded adoption; no calc/journal edits."""
from pathlib import Path
import json,csv,io,re,hashlib,shutil,zipfile,os
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad'
OUT=ROOT/'.validation/pier-wall';EVID=MAIN/'evidence/2026-10-22-pier-wall-rings'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def prepend(p,text,heading=False):
    b=p.read_bytes();nl=b'\r\n' if b'\r\n' in b else b'\n';addition=text.replace('\n',nl.decode()).encode()
    if heading:
        first,rest=b.split(nl,1);b=first+nl+nl+addition+rest.lstrip(b'\r\n')
    else:b=addition+nl+b
    p.write_bytes(b)

qa=json.loads((OUT/'build-v2.json').read_text());render=json.loads((OUT/'native-render.json').read_text())
gui=json.loads((OUT/'gui-build.json').read_text());preservation=json.loads((OUT/'archive-preservation.json').read_text())
provenance=json.loads((OUT/'provenance-update.json').read_text())
assert gui['status']=='PASS' and preservation['status']=='PASS'
assert provenance['status']=='PASS' and provenance['details_unchanged']
assert preservation['candidate_sha256']==gui['candidate_sha256']
qa['candidate']=provenance['candidate'];qa['candidate_sha256']=provenance['candidate_sha256']
manifest=json.loads((MAIN/'manifest.json').read_text());model=MAIN/manifest['model']['path']
assert qa['status']=='VERIFIED_CAD_CALCULATION_RECONCILIATION_PENDING' and qa['cold_reopen'] and qa['native_edit_restore']
assert render['status']=='PASS' and render['ordinary_native_recompute']
assert sha(model)==qa['source_sha256']==manifest['model']['sha256']
assert sha(qa['candidate'])==qa['candidate_sha256']
assert not (EVID/'adoption-summary.json').exists(),'Inspect completed adoption before retry'
for p,h in manifest['runtime_files'].items():assert sha(MAIN/p)==h,p
tracker=ROOT/'project_current/coherence/Coherence_Tracker.xlsx';tracker_hash=sha(tracker)
calc=ROOT/'project_current/pier_wall/selected_case.json';calc_hash=sha(calc)
journal=ROOT/'journal/D2_I95_Project_Journal.bpad';journal_hash=sha(journal)
decision=ROOT/'project_current/decisions.md';decbytes=decision.read_bytes()
assert max(map(int,re.findall(rb'\| D-(\d+) \|',decbytes)))==75
register=ROOT/'project_current/source_register.csv'
tracked=[MAIN/'manifest.json',MAIN/'README.md',MAIN/'runtime/API.md',MAIN/'Open_Current_Bridge.FCMacro',
         MAIN/'evidence/Model-update-report.txt',register,decision]
guards={p:sha(p) for p in tracked}
backup=MAIN/'archive/B4-before-pier-wall-rings-20261022.FCStd'
records=MAIN/'archive/B4-before-pier-wall-rings-record-20261022.zip'
if backup.exists():assert sha(backup)==qa['source_sha256']
else:shutil.copy2(model,backup)
if not records.exists():
    with zipfile.ZipFile(records,'w',zipfile.ZIP_DEFLATED) as z:
        for p in tracked:z.write(p,p.relative_to(ROOT).as_posix())
        for rel in manifest['runtime_files']:z.write(MAIN/rel,rel)
EVID.mkdir(parents=True,exist_ok=True)
for src,dst in [(OUT/'build-v2.json','geometry-verification.json'),(OUT/'native-render.json','native-render.json'),
    (OUT/'gui-build.json','native-gui-verification.json'),(OUT/'archive-preservation.json','archive-preservation.json'),
    (OUT/'source-case.json','initial-case-snapshot.json'),(OUT/'current-source-case.json','selected-case-at-transfer.json'),
    (OUT/'provenance-update.json','provenance-update.json'),(ROOT/'.validation/update_pier_provenance.py','update_provenance.py'),
    (ROOT/'.validation/pier-wall-current-source.json','current-calculation-snapshot.json'),
    (ROOT/'.validation/pier-wall-source.json','calculation-snapshot.json'),(ROOT/'.validation/build_pier_wall.py','build_candidate.py'),
    (ROOT/'.validation/build_pier_gui.py','build_native_gui.py'),(ROOT/'.validation/verify_pier_archive.py','verify_archive.py'),
    (ROOT/'.validation/render_pier_wall.py','render_candidate.py'),(Path(__file__),'adopt_candidate.py'),
    (OUT/'Pier_Wall_Steel_Isometric.png','Pier_Wall_Steel_Isometric.png'),(OUT/'Pier_Wall_Steel_Elevation.png','Pier_Wall_Steel_Elevation.png')]:
    shutil.copy2(src,EVID/dst)
assert all(sha(p)==h for p,h in guards.items())
# Windows denied renaming over the existing file, while opening it read/write
# is permitted. Use the authorized file's write handle, with exact-byte backup,
# preflight hashes, flush and verification; no permissions or attributes change.
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
installation=dict(status='INSTALLED',method='Guarded in-place binary write; atomic rename denied by Windows',
                  backup=str(backup),old_sha256=qa['source_sha256'],new_sha256=qa['candidate_sha256'])
temporary=model.with_name(model.name+'.design-update-tmp')
if temporary.exists():
    assert sha(temporary)==qa['source_sha256']
    temporary.unlink()
opener=MAIN/'Open_Current_Bridge.FCMacro';b=opener.read_bytes()
assert b'cheek_hooks, pier_cheeks, level_seats' in b
opener.write_bytes(b.replace(b'cheek_hooks, pier_cheeks, level_seats',b'cheek_hooks, pier_cheeks, level_seats, pier_wall_rings',1))
scope='Retain existing CAD wall (219 x 36 x 194.862478917107 in) and add the selected calculation reinforcement and annular-ring details.'
summary=('124 native #5 bars at 11 in maximum each way, both broad faces, including 38 end U returns with '
         '72-in straight lap legs and eight end-face verticals; 3-in cover. Twenty annular plates, 23-in OD x '
         '20.125-in ID x 0.75-in thick, centered on the four existing piles. Five ring tops per pile at '
         '6, 42, 78, 114 and 150 in above the retained wall bottom. Two 5/16-in fillets recorded as properties; '
         'weld solids not modeled. Live inputs, analytic paths, native Arch bars and quantities/schedule.')
limits=('The user separately reconciled the calculation geometry under D-075 during this CAD task. The final model '
        'references that selected 22 October case; its dimensions match the retained CAD within 0.001 in and its '
        'bar/ring details are unchanged from the initial snapshot. RING-GRID and all source scope limitations '
        'remain open without rejudgment; the superseded RING-END failure is retained in the initial snapshot only. '
        'U bends (6db inside diameter) and contact lap routing are CAD detailing assumptions. Vertical bars are continuous; '
        'the 60-in vertical lap allowance is recorded, not a modeled splice. PW marks are instance identifiers; '
        'SDM drawing marks, drawing exports, fabrication and engineering acceptance remain pending. '
        'Existing bearing-fit and other project findings remain. No calculation, journal or tracker changes.')
v=qa['validation']
adoption=dict(status='ADOPTED_CAD_RING_GRID_TOLERANCE_REMAINS_OPEN',decision='D-076',date='2026-10-22',scope=scope,
    summary=summary,limitations=limits,model_sha256=sha(model),previous_model_sha256=qa['source_sha256'],
    objects=qa['objects'],protected_existing_objects=qa['protected_objects'],checks_passed=len(v['checks']),
    pairs_checked=next(c['pairs'] for c in v['checks'] if c['name']=='nominal_steel_intersections'),
    native_edit_restore=True,ordinary_native_recompute=True,cold_reopen=True,
    bar_count=v['bar_count'],rings=v['rings'],minimum_bar_cover_in=v['minimum_bar_cover_in'],
    reinforcement_length_ft=v['steel_length_ft'],reinforcement_weight_lb=v['steel_weight_lb'],ring_weight_lb=v['ring_weight_lb'],
    calculation_snapshot_sha256=provenance['current_case_sha256'],initial_calculation_snapshot_sha256=v['source_case_sha256'],source_calculation_unchanged_by_this_task=True,
    journal_unchanged=True,tracker_unchanged=True,installation=installation)
dump(EVID/'adoption-summary.json',adoption)
prepend(MAIN/'README.md','## D-076: pier wall reinforcement and annular rings, 22 October 2026\n\n'+scope+' '+summary+'\n\n'+
    'Native geometry/cover and 1,620 intersecting-box steel pairs pass with no positive overlaps; native edits, ordinary recompute and cold reopen verified. All 2,188 unrelated objects are preserved. '+limits+
    ' See [adoption](evidence/2026-10-22-pier-wall-rings/adoption-summary.json) and [native preview](evidence/2026-10-22-pier-wall-rings/Pier_Wall_Steel_Isometric.png).\n\n',True)
prepend(MAIN/'evidence/Model-update-report.txt','D-076 - PIER WALL REINFORCEMENT AND ANNULAR RINGS, 22 OCTOBER 2026\n\n'+scope+'\n\n'+summary+'\n\n'+limits+'\n\n'+
    f'{len(v["checks"])} checks PASS, 1620 candidate pairs, zero positive steel overlaps. Native edits and ordinary recompute, cold reopen and 2188 protected existing objects verified. Nominal rebar {v["steel_weight_lb"]:.3f} lb; rings {v["ring_weight_lb"]:.3f} lb (490 pcf).\n\nPREVIOUS UPDATES (historical)\n')
api=MAIN/'runtime/API.md';b=api.read_bytes();nl=b'\r\n' if b'\r\n' in b else b'\n'
addition=('\n\n## Pier wall reinforcement and annular rings (D-076)\n\n'
          '`pier_wall_rings.create(doc, source, case_hash, source_path)` installs a new PierWallSteel group on the retained BridgePierWallSolid. '
          'The source includes the immutable case, engine-selected grid and failed check rows. CAD wall dimensions and actual linked pile centers '
          'control placement. `PierWallSteelInputs` owns bar size, cover, maximum spacing, U leg/bend, ring count/spacing/dimensions and source provenance. '
          '`regenerate(inputs)` updates native analytic paths, Arch bars, plates and live schedule; existing concrete/piles are read-only. '
          '`validate(inputs)` checks actual solid volumes, cover, links, physical station spacing, ring positions and steel intersections. '
          'The source case and failed checks remain explicit properties. No native solver or structural design is performed. '
          'Ring elevations are plate TOPS measured from the retained CAD wall bottom. Five rows are retained; no extra row is inferred for the taller wall. '
          'Nominal rebar lengths include explicit U laps, no vertical splices or waste. '+limits+'\n')
api.write_bytes(b+addition.replace('\n',nl.decode()).encode())
manifest['previous_update']=manifest['current_update']
manifest['current_update']=dict(date='2026-10-22',decision='D-076',scope=scope,summary='evidence/2026-10-22-pier-wall-rings/adoption-summary.json',previous_model_sha256=qa['source_sha256'],follow_up=limits)
manifest['model'].update(sha256=sha(model),bytes=model.stat().st_size,objects=qa['objects'])
manifest['updated_on']='2026-10-22';manifest['known_review_status']='D-076: nominal CAD geometry PASS; source RING-GRID tolerance failure remains. '+limits+' Prior: '+manifest['known_review_status']
manifest['runtime_changes'].append('D-076: pier_wall_rings native steel/ring controllers; existing geometry retained; immutable calculation snapshot updated to the separately selected D-075 case without changing details.')
manifest['opener_sha256']=sha(opener)
for rel in ['runtime/freecad_tools/pier_wall_rings.py','runtime/API.md']:manifest['runtime_files'][rel]=sha(MAIN/rel)
for p in (backup,records):manifest['archive_files'][p.relative_to(MAIN).as_posix()]=sha(p)
for p in [*EVID.iterdir(),MAIN/'evidence/Model-update-report.txt']:manifest['evidence_files'][p.relative_to(MAIN).as_posix()]=sha(p)
dump(MAIN/'manifest.json',manifest)
nl=b'\r\n' if b'\r\n' in decbytes else b'\n';anchor=nl+nl+b'The current journal';assert anchor in decbytes
row='| D-076 | 2026-10-22 | Add pier wall steel and annular rings to the CAD model; retain existing CAD wall geometry. | User direction: retain the CAD wall; user updated design calculations to match separately under D-075. '+summary+' '+limits+' Geometry and native regeneration/reopen verified; 2188 existing objects preserved. See [CAD adoption](geometry/freecad/evidence/2026-10-22-pier-wall-rings/adoption-summary.json). |'
decision.write_bytes(decbytes.replace(anchor,nl+row.encode()+anchor,1))
raw=register.read_bytes();lines=raw.decode('utf-8-sig').splitlines(keepends=True);fields=next(csv.reader([lines[0]]))
for i,line in enumerate(lines[1:],1):
    row=dict(zip(fields,next(csv.reader([line]))));sid=row['source_id']
    if sid not in ('CAD-MODEL','CAD-RUNTIME','CAD-REPORT'):continue
    target=model if sid=='CAD-MODEL' else MAIN/'manifest.json' if sid=='CAD-RUNTIME' else MAIN/'evidence/Model-update-report.txt'
    row.update(sha256=sha(target),registered_on='2026-10-22')
    row['notes']='D-076: '+scope+' '+summary+' '+limits+' Prior: '+row['notes']
    if sid=='CAD-MODEL':
        row['scope']+='; D-076 pier wall reinforcement and annular rings; CAD wall geometry retained'
        row['status']='Current - pier wall steel/rings; ring-grid tolerance and bearing fit unresolved'
    buf=io.StringIO(newline='');csv.writer(buf,quoting=csv.QUOTE_ALL,lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[f] for f in fields]);lines[i]=buf.getvalue()
register.write_bytes((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+''.join(lines).encode())
assert sha(tracker)==tracker_hash and sha(calc)==calc_hash and sha(journal)==journal_hash
paths=sorted({p.relative_to(ROOT).as_posix() for p in [model,backup,records,*tracked,*EVID.iterdir(),MAIN/'runtime/freecad_tools/pier_wall_rings.py']})
dump(OUT/'adoption.json',dict(status=adoption['status'],commit_paths=paths))
(OUT/'commit-paths.txt').write_text('\n'.join(paths)+'\n')
print(json.dumps(adoption,indent=2))
