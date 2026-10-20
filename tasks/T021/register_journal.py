"""Reconcile the promoted journal hash and actual D-065 implementation status."""
from pathlib import Path
import hashlib,json,csv,io
ROOT=Path(__file__).resolve().parents[2];TASK=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
v=json.loads((TASK/'verification.json').read_text())
r=json.loads((ROOT/'workflow/completed/T021.json').read_text())
actual=sha(ROOT/'journal/D2_I95_Project_Journal.bpad')
assert actual==r['journal_sha256']==v['candidate_sha256']
for rel,h in v['protected_files_sha256'].items():assert sha(ROOT/rel)==h,rel
model=ROOT/'project_current/geometry/freecad/B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd'
assert sha(model)==v['CAD_candidate_sha256']
reg=ROOT/'project_current/source_register.csv';raw=reg.read_bytes();lines=raw.decode('utf-8-sig').splitlines(keepends=True)
fields=next(csv.reader([lines[0]]));changed=0
for i,line in enumerate(lines[1:],1):
 row=dict(zip(fields,next(csv.reader([line]))))
 if row['source_id']!='JOURNAL':continue
 assert row['sha256']==v['base_sha256']
 row.update(sha256=actual,registered_on='2026-10-20',status='Current - D-065 all-support as-cast override; final bearing fit unresolved')
 row['notes']='D-065 / T021: under Bearing Pads, adopt all six level as-cast pedestal tops at their individual prior maxima (EB1 43.74578111249233 ft; Pier 44.26686320063029 ft; EB2 43.75994652287092 ft). Eight level uniform 2.5625-in pads modeled; 84 pedestal bars retain prior elevations. CAD implemented and native geometry/edit/reopen verified. D-064 superseded. Final pad/beam fit FAIL in undeformed geometry; grinding/seat setting, cover/contact, construction stages and final bearing checks remain open. Notebook, B4 geometry table and drawings pending reconciliation. All prior calculations/caches preserved; no native journal recalculation or engineering acceptance claimed. See tasks/T021/verification.json. Historical basis: '+row['notes']
 buf=io.StringIO(newline='');csv.writer(buf,quoting=csv.QUOTE_ALL,lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[f] for f in fields]);lines[i]=buf.getvalue();changed+=1
assert changed==1
after=(b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+''.join(lines).encode()
before_rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
after_rows=list(csv.DictReader(io.StringIO(after.decode('utf-8-sig'))))
assert [r for r in before_rows if r['source_id']!='JOURNAL']==[r for r in after_rows if r['source_id']!='JOURNAL']
reg.write_bytes(after)
(TASK/'adoption.json').write_text(json.dumps(dict(decision='D-065',task='T021',date='2026-10-20',
 journal_sha256=actual,CAD_model_sha256=sha(model),source_register_before_sha256=hashlib.sha256(raw).hexdigest(),
 source_register_after_sha256=sha(reg),protected_files_sha256=v['protected_files_sha256'],status='IMPLEMENTED_AS_CAST_FINAL_FIT_OPEN'),indent=2)+'\n')
print(json.dumps(dict(journal_sha256=actual,CAD_model_sha256=sha(model),status='registered')))
