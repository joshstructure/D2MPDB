"""Adopt only the verified D-065 native model and its bounded source records."""
from pathlib import Path
import json,hashlib,zipfile,shutil,importlib.util,csv,io,re
ROOT=Path('C:/Users/joshs/Desktop/CAD_AI');REPO=Path('C:/github/D2MPDB')
MAIN=REPO/'project_current/geometry/freecad';OUT=ROOT/'output/level-seats-20261020';REPORT=ROOT/'reports/level-seats-20261020'
EVID=MAIN/'evidence/2026-10-20-level-bearing-seats'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def prepend(p,text,heading=False):
 data=p.read_bytes();nl=b'\r\n' if b'\r\n' in data else b'\n';addition=text.replace('\n',nl.decode()).encode()
 if heading:
  first,rest=data.split(nl,1);data=first+nl+nl+addition+rest.lstrip(b'\r\n')
 else:data=addition+nl+data
 p.write_bytes(data)
qa=json.loads((REPORT/'build-v3.json').read_text());manifest=json.loads((MAIN/'manifest.json').read_text())
model=MAIN/manifest['model']['path']
assert not EVID.exists() and not (REPORT/'adoption.json').exists(),'Inspect previous adoption before retry'
assert qa['status']=='GEOMETRY_PASS_FINAL_FIT_OPEN' and qa['native_edit_restore'] and qa['cold_reopen']
assert qa['cold_reopen_validation']['geometry_status']=='PASS'
assert sha(qa['candidate'])==qa['candidate_sha256']
assert sha(model)==qa['source_sha256']==manifest['model']['sha256']
for name,h in manifest['runtime_files'].items():assert sha(MAIN/name)==h,name
modules=['runtime/freecad_tools/level_seats.py','runtime/freecad_tools/pedestal_ubars.py']
for p in (OUT/'runtime').rglob('*'):
 if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
  rel=p.relative_to(OUT)
  if rel.as_posix() not in modules:assert sha(p)==sha(MAIN/rel),str(rel)
regfile=REPO/'project_current/source_register.csv';decfile=REPO/'project_current/decisions.md'
tracker=REPO/'project_current/coherence/Coherence_Tracker.xlsx';trackerhash=sha(tracker)
decbytes=decfile.read_bytes();assert max(map(int,re.findall(rb'\| D-(\d+) \|',decbytes)))==64
tracked=[MAIN/'manifest.json',MAIN/'README.md',MAIN/'runtime/API.md',MAIN/'Open_Current_Bridge.FCMacro',MAIN/'evidence/Model-update-report.txt',regfile,decfile]
guards={p:sha(p) for p in tracked}
backup=MAIN/'archive/B4-before-level-bearing-seats-20261020.FCStd'
records=MAIN/'archive/B4-before-level-bearing-seats-record-20261020.zip'
assert not backup.exists() and not records.exists()
with zipfile.ZipFile(records,'w',zipfile.ZIP_DEFLATED) as z:
 for p in tracked:z.write(p,p.relative_to(REPO).as_posix())
 for p in (MAIN/'runtime').rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(MAIN).as_posix())
scope='All six pedestal tops level at their own previous maximum elevations; eight uniform 2.5625-in pads level on the tops. D-065 supersedes D-064.'
limits='As-cast stock only: all eight pads intersect the unchanged beams in undeformed geometry; final bearing fit FAIL. Final seat/grinding elevations, cover, contact, construction stages and bearing acceptance remain open. Notebook, B4 geometry table and drawings pending reconciliation. T019 is a conditional pier check, not end-bent approval; all prior analysis/combined-load limitations and D-047 steel disposition remain.'
record=dict(status='PREPARED',decision='D-065',date='2026-10-20',old_model_sha256=sha(model),new_model_sha256=qa['candidate_sha256'],scope=scope,tracker_sha256=trackerhash)
dump(REPORT/'adoption.json',record)
assert all(sha(p)==h for p,h in guards.items())
for module in modules:shutil.copy2(OUT/module,MAIN/module)
opener=MAIN/'Open_Current_Bridge.FCMacro';b=opener.read_bytes()
assert b'cheek_hooks, pier_cheeks' in b
opener.write_bytes(b.replace(b'cheek_hooks, pier_cheeks',b'cheek_hooks, pier_cheeks, level_seats',1))
spec=importlib.util.spec_from_file_location('file_install',ROOT/'freecad_tools/file_install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
record['installation']=installer.install(qa['candidate'],model,backup,qa['source_sha256'],qa['candidate_sha256'])
EVID.mkdir(parents=True)
for src,dst in [(REPORT/'baseline.json',EVID/'source-elevations.json'),(REPORT/'build-v3.json',EVID/'geometry-verification.json'),
 (ROOT/'tools/build_level_seats_20261020.py',EVID/'build_candidate.py'),(Path(__file__),EVID/'adopt_candidate.py')]:shutil.copy2(src,dst)
summary=dict(status='ADOPTED_AS_CAST_GEOMETRY_FINAL_FIT_OPEN',decision='D-065',date='2026-10-20',model=model.name,
 model_sha256=sha(model),previous_model_sha256=qa['source_sha256'],objects=qa['objects'],protected_existing_objects=qa['protected_objects'],
 scope=scope,pedestals=qa['cold_reopen_validation']['pedestals'],pads=qa['cold_reopen_validation']['pads'],
 physical_geometry_checks_passed=len(qa['cold_reopen_validation']['checks']),bearing_fit_checks=qa['cold_reopen_validation']['bearing_fit_checks'],
 final_bearing_fit_status='FAIL',native_edit_restore=True,cold_reopen=True,steel_bars_preserved=84,
 regenerated_steel_geometry_preserved=True,adopted_marks_preserved=True,
 inherited_development_findings=qa['inherited_development_findings'],scope_limits=limits,
 backups=[p.relative_to(MAIN).as_posix() for p in (backup,records)])
dump(EVID/'adoption-summary.json',summary)
text='D-065 - LEVEL AS-CAST BEARING SEATS, 20 OCTOBER 2026\n\n'+scope+'\n\nTop elevations, existing model datum: EB1 43.74578111249233 ft; Pier 44.26686320063029 ft; EB2 43.75994652287092 ft. Both pedestals at each support share that value. Each pedestal is one solid with a single horizontal top face. Pads are level, 10 x 32 x 2.5625 in. All 84 pedestal bars and their adopted marks stay at prior elevations, with a native pre-grinding reference for regeneration.\n\n62 physical geometry checks pass; native elevation edit/restore, cage regeneration and cold reopen verified. 2166 unrelated native objects are preserved. All beam, deck, cap and other existing geometry is unchanged. Maximum sampled rigid fit differences: EB1 0.1240295 in, Pier 0.0460508 in, EB2 0.1572338 in. These are not prescribed grinding depths or elastic pad response.\n\n'+limits+'\n\nPREVIOUS UPDATES (historical)\n'
prepend(MAIN/'evidence/Model-update-report.txt',text)
prepend(MAIN/'README.md','## D-065: level as-cast seats, 20 October 2026\n\n'+scope+' Elevations: EB1 **43.74578111249233 ft**, Pier **44.26686320063029 ft**, EB2 **43.75994652287092 ft**. All 84 pedestal bars and their marks stay at prior elevations. Native geometry, edit/regeneration and cold reopen verified. '+limits+' See [adoption](evidence/2026-10-20-level-bearing-seats/adoption-summary.json).\n\n',True)
api=MAIN/'runtime/API.md';data=api.read_bytes();nl=b'\r\n' if b'\r\n' in data else b'\n'
addition='\n\n## Level as-cast bearing seats (D-065)\n\n`level_seats.configure(doc, elevations, source_sha)` requires all six explicit unit-bearing prior maximum elevations and attaches native `LevelComponentProxy` controllers to existing pedestals/pads. `LevelSeatTopElevation` is the fixed adopted absolute plane; pads follow `LevelSeatHost`. PGL/profile changes require rechecking these overrides. `PreGrindingReferenceElevation` on each existing cage retains the prior steel height during ordinary regeneration. Existing marks and schedules remain linked. `level_seats.validate(doc)` independently measures solid validity, single level tops, dimensions/volume, cap and pad contact, and actual pad/beam solid intersections plus vertical section differences. `LevelSeatOverrideChecks` exposes geometry PASS separately from final beam fit FAIL. No compression, taper, automatic grinding depth or final engineering acceptance is assumed. Helpers do not save. Use the paired model and runtime; open with `Open_Current_Bridge.FCMacro` after restarting any session that has old controllers loaded.\n'
api.write_bytes(data+addition.replace('\n',nl.decode()).encode())
manifest['previous_update']=manifest['current_update']
manifest['current_update']=dict(date='2026-10-20',decision='D-065',scope=scope,summary='evidence/2026-10-20-level-bearing-seats/adoption-summary.json',previous_model_sha256=qa['source_sha256'],follow_up=limits)
manifest['model'].update(sha256=sha(model),bytes=model.stat().st_size,objects=qa['objects'])
manifest['updated_on']='2026-10-20'
manifest['known_review_status']='D-065: level as-cast geometry PASS; final pad/beam fit FAIL at all eight pads. '+limits+' Prior recorded review status: '+manifest['known_review_status']
manifest['runtime_changes'].append('D-065: native level_seats host/pad dependencies and fixed pre-grinding cage elevation reference; independent rigid-fit failures remain visible.')
manifest['opener_sha256']=sha(opener)
for name in [*modules,'runtime/API.md']:manifest['runtime_files'][name]=sha(MAIN/name)
for p in (backup,records):manifest['archive_files'][p.relative_to(MAIN).as_posix()]=sha(p)
for p in [*EVID.iterdir(),MAIN/'evidence/Model-update-report.txt']:manifest['evidence_files'][p.relative_to(MAIN).as_posix()]=sha(p)
dump(MAIN/'manifest.json',manifest)
nl=b'\r\n' if b'\r\n' in decbytes else b'\n';anchor=nl+nl+b'The current journal';assert anchor in decbytes
row='| D-065 | 2026-10-20 | Level as-cast bearing seats at every support, at each pedestal maximum; supersedes D-064. | User direction. Six native pedestal tops are horizontal at EB1 43.74578111249233 ft, Pier 44.26686320063029 ft and EB2 43.75994652287092 ft; eight uniform 2.5625-in pads are level on those tops. All 84 pedestal bars retain prior elevations and marks. 62 geometry checks, native edit/regeneration and saved-file reopen verified; 2166 other objects preserved. T021 records the override under Bearing Pads. '+limits+' See [CAD adoption](geometry/freecad/evidence/2026-10-20-level-bearing-seats/adoption-summary.json) and [journal verification](../tasks/T021/verification.json). |'
decfile.write_bytes(decbytes.replace(anchor,nl+row.encode()+anchor,1))
assert sha(regfile)==guards[regfile];raw=regfile.read_bytes();lines=raw.decode('utf-8-sig').splitlines(keepends=True);fields=next(csv.reader([lines[0]]))
for i,line in enumerate(lines[1:],1):
 row=dict(zip(fields,next(csv.reader([line]))));sid=row['source_id']
 if sid not in ('CAD-MODEL','CAD-RUNTIME','CAD-REPORT'):continue
 target=model if sid=='CAD-MODEL' else MAIN/'manifest.json' if sid=='CAD-RUNTIME' else MAIN/'evidence/Model-update-report.txt'
 row.update(sha256=sha(target),registered_on='2026-10-20')
 row['notes']='D-065: '+scope+' '+limits+' Geometry/native edit/cold reopen verified; prior evidence: '+row['notes']
 if sid=='CAD-MODEL':
  row['scope']+='; D-065 all-support level as-cast bearing seats'
  row['status']='Current - level as-cast seats; final bearing fit unresolved'
 buf=io.StringIO(newline='');csv.writer(buf,quoting=csv.QUOTE_ALL,lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[f] for f in fields]);lines[i]=buf.getvalue()
regfile.write_bytes((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+''.join(lines).encode())
assert sha(tracker)==trackerhash
paths=sorted({p.relative_to(REPO).as_posix() for p in [model,*[MAIN/m for m in modules],backup,records,*tracked,*EVID.iterdir()]})
record.update(status=summary['status'],commit_paths=paths,tracker_preserved=True)
dump(REPORT/'adoption.json',record)
(REPORT/'commit-paths.txt').write_text('\n'.join(paths)+'\n')
print(json.dumps(dict(status=record['status'],decision='D-065',model_sha256=sha(model),objects=qa['objects'],tracked_files=len(paths))))
