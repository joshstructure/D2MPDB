from pathlib import Path
import sys,os,json,traceback,hashlib
sys.dont_write_bytecode=True
ROOT=Path('C:/Users/joshs/Desktop/CAD_AI')
MAIN=Path('C:/github/D2MPDB/project_current/geometry/freecad')
OUT=ROOT/'output/level-seats-20261020';REPORT=ROOT/'reports/level-seats-20261020'
sys.path.insert(0,str(OUT/'runtime'))
import FreeCAD as App
from freecad_tools import level_seats as ls,bridge,native_archive,pedestal_ubars as steel
version=sys.argv[1] if len(sys.argv)>1 else 'v1'
journal=REPORT/('build-'+version+'.json');assert not journal.exists(),'Inspect previous build before retry'
baseline=json.loads((REPORT/'baseline.json').read_text())
source=Path(baseline['source'])
record=dict(status='PREPARED',source=str(source),source_sha256=native_archive.sha(source))
assert record['source_sha256']==baseline['source_sha256']
elevations={r['name']:format(r['top_max_ft'],'.17g')+' ft' for r in baseline['pedestals']}
def save():journal.write_text(json.dumps(record,indent=2)+'\n')
save();doc=None
try:
 doc=App.openDocument(str(source));original=[o.Name for o in doc.Objects]
 inputnames=baseline['pedestal_cages']
 affected=set(ls.HOSTS)|set(inputnames)|{r['name'] for r in baseline['pads']}|{'BridgeAssembly','BridgeGeometryChecks'}
 protected=[n for n in original if n not in affected];before=bridge.source_state(doc,protected)
 marks={o.Name:o.Mark for o in doc.Objects if 'Mark' in o.PropertiesList}
 cages=[doc.getObject(n) for n in inputnames]
 bars=[b for inp in cages for b in doc.getObject(inp.Prefix+'Quantities').Bars]
 originalbars={b.Name:b.Shape.copy() for b in bars}
 beforelayout={i.Name:steel.layout(i)[0] for i in cages}
 doc.openTransaction('D-065 level as-cast pedestal tops and pads')
 record['validation']=ls.configure(doc,elevations,record['source_sha256'])
 save()
 assert record['validation']['geometry_status']=='PASS'
 assert before==bridge.source_state(doc,protected),'Unrelated native geometry changed'
 assert marks=={n:doc.getObject(n).Mark for n in marks}
 # Independent cage geometry/cover check; inherited tension failures stay explicit.
 record['steel_checks']={i.Name:steel.validate(i) for i in cages}
 failures=[c for r in record['steel_checks'].values() for c in r['checks'] if c['status']=='FAIL']
 record['inherited_development_findings']=failures
 assert all(c.get('category')=='development' for c in failures),failures
 # Surface replacement can change kernel-derived bounds by roundoff. Record
 # every numerical difference; reject movement above 1e-8 inch, then check the
 # actual regenerated solids independently below.
 layout_differences=[]
 def compare(a,b,path=''):
  if isinstance(a,dict):
   assert a.keys()==b.keys(),path
   for k in a:compare(a[k],b[k],path+'/'+str(k))
  elif isinstance(a,(list,tuple)):
   assert len(a)==len(b),path
   for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
  elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
   if a!=b:layout_differences.append(dict(path=path,before=a,after=b,delta=b-a))
  else:assert a==b,path
 compare(beforelayout,{i.Name:steel.layout(i)[0] for i in cages})
 record['layout_roundoff_differences']=layout_differences;save()
 # The derived tension length amplifies the kernel bound roundoff; this does
 # not affect the specified 12-in embedment or any path coordinate.
 assert all(abs(d['delta'])<(1e-6 if d['path'].endswith('/required_development_in') else 1e-8)
            for d in layout_differences),'Regeneration would move reinforcement'
 record['steel_bars_preserved']=len(bars)
 # Exercise ordinary native dependencies in this disposable document, restore,
 # then preserve original records/resources when packaging the final candidate.
 for o in doc.Objects:o.purgeTouched()
 h=doc.getObject(ls.HOSTS[0]);z=h.LevelSeatTopElevation.Value
 pad=doc.BridgePadEB1S1B1
 h.LevelSeatTopElevation=z+ls.IN/8
 doc.recompute()
 assert abs(bridge.local_shape(h).BoundBox.ZMax-z-ls.IN/8)<ls.TOL
 assert abs(bridge.local_shape(pad).BoundBox.ZMin-z-ls.IN/8)<ls.TOL,'Pad did not follow its native host'
 h.LevelSeatTopElevation=z;doc.recompute()
 for inp in cages:steel.regenerate(inp)
 for n,s in originalbars.items():
  t=doc.getObject(n).Shape
  assert abs(t.cut(s).Volume)<1e-6 and abs(s.cut(t).Volume)<1e-6,n
 assert marks=={n:doc.getObject(n).Mark for n in marks},'Bar marks changed'
 record['native_edit_restore']=True
 record['regenerated_steel_geometry_preserved']=True
 record['validation']=ls.validate(doc)
 assert record['validation']['geometry_status']=='PASS'
 doc.LevelSeatOverrideChecks.Proxy.execute(doc.LevelSeatOverrideChecks)
 record['protected_objects']=len(protected);record['objects']=len(doc.Objects)
 doc.commitTransaction()
 for o in doc.Objects:o.purgeTouched()
 raw=REPORT/('NativeCandidate-'+version+'.FCStd')
 candidate=OUT/('B4 - Level bearing seats - '+version+'.FCStd')
 doc.saveAs(str(raw))
 record['archive']=native_archive.preserve(source,raw,candidate,protected,record['source_sha256'])
 App.closeDocument(doc.Name);doc=App.openDocument(str(candidate))
 assert before==bridge.source_state(doc,protected),'Cold reopen changed protected native objects'
 assert marks=={n:doc.getObject(n).Mark for n in marks}
 reopened=ls.validate(doc);record['cold_reopen_validation']=reopened
 assert reopened['geometry_status']=='PASS'
 assert all(type(doc.getObject(n).Proxy).__name__=='LevelComponentProxy' for n in ls.HOSTS)
 assert doc.LevelSeatOverrideChecks.FinalBeamFitStatus==reopened['final_beam_fit_status']
 record.update(status='GEOMETRY_PASS_FINAL_FIT_OPEN',candidate=str(candidate),candidate_sha256=native_archive.sha(candidate),cold_reopen=True,source_unchanged=native_archive.sha(source)==record['source_sha256'])
 assert record['source_unchanged'];save()
 print(json.dumps({k:record[k] for k in ['status','objects','protected_objects','steel_bars_preserved','native_edit_restore','candidate_sha256']},indent=2),flush=True)
 print(json.dumps(reopened['bearing_fit_checks'],indent=2),flush=True);code=0
except Exception:
 record.update(status='FAIL',error=traceback.format_exc());save();traceback.print_exc();code=1
finally:
 if doc:App.closeDocument(doc.Name)
sys.stdout.flush();sys.stderr.flush();os._exit(code)
