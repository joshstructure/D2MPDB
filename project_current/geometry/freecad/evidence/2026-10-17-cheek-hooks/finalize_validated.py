"""Finalize the checked checkpoint with exact original native-record preservation."""
from pathlib import Path
import sys,json,traceback
sys.dont_write_bytecode=True
OUT=Path(__file__).parent;sys.path.insert(0,str(OUT/'runtime'))
import FreeCAD as A
from freecad_tools import native_archive,cheek_hooks
prior=json.loads((OUT/'build-report-final-preservation-diagnostic.json').read_text())
assert not prior['cheeks']['failures'] and prior['wwr']['status']=='PASS'
assert not prior['preservation_differences'] and prior['native_tail_edit_restore_and_undersize_rejection']=='PASS'
diag=json.loads((OUT/'preservation-diagnostic.json').read_text())
assert all(set(fields)<={'shape','label'} for fields in diag.values())
fit=json.loads((OUT/'hook-fit.json').read_text());mutable={'CheekSteelChecks','WallSteelChecks','CheekLugWWRChecks'}
for w in fit['walls']:
 p='Steel'+w['host'];mutable.update(p+x for x in ('Inputs','Quantities','Schedule'))
 for ident in w['hooks']:mutable.update((p+ident,p+ident+'Path'))
report={k:v for k,v in prior.items() if k not in ('error','phase','status')}
report.update(status='PREPARED',request_id='cheek-standard-hooks-20261017-finalize-validated',checkpoint=str(OUT/'GeometryValidated.FCStd'),checkpoint_sha256=native_archive.sha(OUT/'GeometryValidated.FCStd'),preservation_repair='Restore exact original protected native records, shape resources and all view records through the established native_archive helper. The disposable checkpoint changed serialized BRep bytes during save and allocated new duplicate labels during the tail-control exercise. Cold verification requires exact protected-record equality and repeats the saved hook geometry checks.')
try:
 d=A.openDocument(str(OUT/'GeometryValidated.FCStd'))
 assert len(d.Objects)==2093 and not [o.Name for o in d.Objects if 'Invalid' in o.State]
 d.CheekSteelChecks.ReportJSON=json.dumps(report['cheeks']);d.CheekSteelChecks.Status='PASS'
 d.CheekSteelChecks.DetailingStatus='Standard #4 90deg hook geometry verified. Development / connection capacity NOT VERIFIED.'
 detail=report['cheeks']['all_wall_detailing'];d.WallSteelChecks.ReportJSON=json.dumps(detail);d.WallSteelChecks.Status='FAIL'
 for obj in (d.CheekSteelChecks,d.WallSteelChecks,d.CheekLugWWRChecks):obj.SnapshotBasis='17 October 2026: hooked cheek horizontals; actual combined concrete cover and intersections against retained wall/cap/pedestal/lug steel. Existing unrelated failures retained.'
 report['protected']=sorted(o.Name for o in d.Objects if o.Name not in mutable);report['objects']=len(d.Objects)
 for o in d.Objects:o.purgeTouched()
 d.saveAs(str(OUT/'NativeCandidate.FCStd'));A.closeDocument(d.Name)
 report['preservation']=native_archive.preserve(OUT/'Before.FCStd',OUT/'NativeCandidate.FCStd',OUT/'Hooked Bridge.FCStd',report['protected'],report['source_sha256'])
 report.update(status='PASS',model=str(OUT/'Hooked Bridge.FCStd'),sha256=native_archive.sha(OUT/'Hooked Bridge.FCStd'))
except Exception:
 report.update(status='FAIL',error=traceback.format_exc());raise
finally:
 (OUT/'build-report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k in ('status','sha256','objects','preservation','error')}),flush=True)
