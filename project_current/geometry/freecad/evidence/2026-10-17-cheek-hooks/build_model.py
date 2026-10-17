"""Apply and verify the scoped hook edit on a disposable file copy."""
from pathlib import Path
import sys,json,hashlib,traceback
sys.dont_write_bytecode=True
OUT=Path(__file__).parent;sys.path.insert(0,str(OUT/'runtime'))
import FreeCAD as App
from freecad_tools import cheek_hooks as hooks,cheek_steel as cheek,design_steel as steel,bridge,lug_wwr,native_archive
from freecad_tools.mse import prop
source=OUT/'Before.FCStd';record=OUT/'build-report.json'
if record.exists():raise ValueError('Inspect existing transaction before retrying')
fit=json.loads((OUT/'hook-fit.json').read_text());assert fit['status']=='COMPLETE'
report=dict(status='PREPARED',request_id='cheek-standard-hooks-20261017-v5',source_sha256=native_archive.sha(source),changes=[],standard=hooks.STANDARD_URL)
def save(phase):
 report['phase']=phase;record.write_text(json.dumps(report,indent=2));print(phase,flush=True)
try:
 save('Open disposable source')
 d=App.openDocument(str(source));assert not any('Invalid' in o.State or 'Touched' in o.State for o in d.Objects)
 for obj in (d.CheekSteelChecks,d.WallSteelChecks,d.CheekLugWWRChecks):
  if 'SnapshotBasis' not in obj.PropertiesList:prop(obj,'App::PropertyString','SnapshotBasis','','Validation snapshot')
 names=[o.Name for o in d.Objects];before=bridge.source_state(d,names)
 mutable={'CheekSteelChecks','WallSteelChecks','CheekLugWWRChecks'}
 for w in fit['walls']:
  prefix='Steel'+w['host'];mutable.update(prefix+s for s in ('Inputs','Quantities','Schedule'))
  for ident in w['hooks']:mutable.update((prefix+ident,prefix+ident+'Path'))
 protected=set(names)-mutable
 # Preserve the pre-update validation snapshots as evidence, not current claims.
 report['prior_checks']={n:dict(status=d.getObject(n).Status,report=json.loads(d.getObject(n).ReportJSON)) for n in ('CheekSteelChecks','WallSteelChecks','CheekLugWWRChecks')}
 for w in fit['walls']:
  inp=d.getObject('Steel'+w['host']+'Inputs');q=d.getObject(inp.Prefix+'Quantities')
  old=dict(length_ft=q.TotalSteelLength.Value/304.8,weight_lb=q.NominalSteelWeightLb,bars=q.TotalBars)
  hooks.configure(inp,w['hooks'])
  prop(inp,'App::PropertyString','HookFitExceptionsJSON',json.dumps([t for t in w['trials'] if t['end'] not in w['hooks'].get(t['id'],{})]),'Horizontal hooks')
  inp.ScheduleNote='Centered #4 mat at 10 in maximum. 90deg standard main-bar hooks where fitted: 3 in inside bend / 6 in straight tail. 4E2 straight, 4E3 two cap hooks, 4E4 one backwall hook, 4E5 one cap hook if present. See HookFitExceptionsJSON for straight ends. Development / connection capacity not verified.'
  inp.Limitations='Selected mat size/count/levels retained. User 17 October 2026: hook horizontal steel into backwall/cap where cover and retained reinforcement permit. Native solid geometry is verified; required development, joint transfer and connection capacity remain unverified.'
  inp.CoordinationBasis+=' 17 October: standard inward horizontal end hooks; local end positions coordinated around retained cap hoops. Existing row elevations retained.'
  hooks.refresh(inp)
  for ident,ends in w['hooks'].items():d.getObject(inp.Prefix+ident).Mark='4E3' if len(ends)==2 else ('4E4' if next(iter(ends.values()))['receiver_kind']=='backwall' else '4E5')
  steel.write_wall_schedule(inp,d.getObject(inp.Prefix+'Schedule'),q.Bars)
  report['changes'].append(dict(wall=w['host'],before=old,hooks=w['hooks']))
 for o in d.Objects:o.purgeTouched()
 sheets=[d.getObject('Steel'+h+'Schedule') for h in cheek.HOSTS]
 for o in sheets:o.touch()
 d.recompute(sheets)
 renamed=[n for n in protected if d.getObject(n).Label!=before[n]['label']]
 for n in renamed:d.getObject(n).Label='RestoreHooks_'+n
 for n in renamed:d.getObject(n).Label=before[n]['label']
 save('Measure native hooked bars, cover, schedules and affected steel intersections')
 report['cheeks']=cheek.validate(d)
 assert not report['cheeks']['failures'],report['cheeks']['failures']
 save('Validate retained lug mesh against revised horizontal bars')
 report['wwr']=lug_wwr.validate(d);assert report['wwr']['status']=='PASS'
 report['preservation_differences']=[n for n,v in bridge.source_state(d,protected).items() if v!=before[n]]
 assert not report['preservation_differences'],report['preservation_differences']
 save('Exercise editable hook tail and reject undersized standard hook')
 inp=d.getObject('Steel'+cheek.HOSTS[0]+'Inputs');ident=next(iter(json.loads(inp.HorizontalHooksJSON)))
 bar=d.getObject(inp.Prefix+ident);oldlength=bar.TotalLength.Value;tail=inp.HookTailLength.Value
 inp.HookTailLength='6.25 in';hooks.refresh(inp)
 assert abs(bar.TotalLength.Value-oldlength-len(json.loads(inp.HorizontalHooksJSON)[ident])*.25*25.4)<.0254
 inp.HookTailLength='6 in';hooks.refresh(inp)
 assert abs(bar.TotalLength.Value-oldlength)<.0254
 inp.HookTailLength='5.5 in'
 rejected=False
 try:hooks.layout(inp)
 except ValueError:rejected=True
 finally:inp.HookTailLength='6 in'
 assert rejected
 report['native_tail_edit_restore_and_undersize_rejection']='PASS'
 # Restore schedules after regeneration; native marks are retained by sync_wall.
 for h in cheek.HOSTS:
  inp=d.getObject('Steel'+h+'Inputs');steel.write_wall_schedule(inp,d.getObject(inp.Prefix+'Schedule'),d.getObject(inp.Prefix+'Quantities').Bars)
 for o in d.Objects:o.purgeTouched()
 for o in sheets:o.touch()
 d.recompute(sheets)
 for o in d.Objects:o.purgeTouched()
 detail=report['cheeks']['all_wall_detailing']
 d.CheekSteelChecks.ReportJSON=json.dumps(report['cheeks']);d.CheekSteelChecks.Status='PASS'
 d.CheekSteelChecks.DetailingStatus='Standard #4 90deg hook geometry verified. Development / connection capacity NOT VERIFIED.'
 d.WallSteelChecks.ReportJSON=json.dumps(detail);d.WallSteelChecks.Status='FAIL' if any(c['status']=='FAIL' for c in detail['checks']) else 'PASS'
 for obj in (d.CheekSteelChecks,d.WallSteelChecks,d.CheekLugWWRChecks):obj.SnapshotBasis='17 October 2026: hooked cheek horizontals; actual combined concrete cover and intersections against retained wall/cap/pedestal/lug steel. Rerun cheek_steel.validate after edits. Existing unrelated failures retained.'
 renamed=[n for n in protected if d.getObject(n).Label!=before[n]['label']]
 for n in renamed:d.getObject(n).Label='RestoreHooksFinal_'+n
 for n in renamed:d.getObject(n).Label=before[n]['label']
 after=bridge.source_state(d,protected);assert all(before[n]==after[n] for n in protected)
 assert not [o.Name for o in d.Objects if 'Invalid' in o.State]
 report['protected']=sorted(protected);report['objects']=len(d.Objects)
 for o in d.Objects:o.purgeTouched()
 d.saveAs(str(OUT/'NativeCandidate.FCStd'));App.closeDocument(d.Name)
 report['preservation']=native_archive.preserve(source,OUT/'NativeCandidate.FCStd',OUT/'Hooked Bridge.FCStd',protected,report['source_sha256'])
 report.update(status='PASS',model=str(OUT/'Hooked Bridge.FCStd'),sha256=native_archive.sha(OUT/'Hooked Bridge.FCStd'))
 save('Complete')
except Exception:
 report.update(status='FAIL',error=traceback.format_exc());save('Failed');raise
