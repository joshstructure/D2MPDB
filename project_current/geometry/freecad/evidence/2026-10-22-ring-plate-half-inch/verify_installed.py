"""Cold reopen of the installed model: ring plate thickness, tops and provenance."""
from pathlib import Path
import sys,json,os,traceback
sys.dont_write_bytecode=True
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad';OUT=ROOT/'.validation/pier-wall-half-inch'
sys.path.insert(0,str(MAIN/'runtime'))
import FreeCAD as App
from freecad_tools import native_archive,pier_wall_rings as pw
IN=pw.IN;doc=None;out={}
try:
    manifest=json.loads((MAIN/'manifest.json').read_text());model=MAIN/manifest['model']['path']
    out['model_sha256']=native_archive.sha(model);assert out['model_sha256']==manifest['model']['sha256']
    doc=App.openDocument(str(model));inp=doc.PierWallSteelInputs;q=doc.PierWallSteelQuantities
    assert abs(inp.RingThickness.Value-0.5*IN)<1e-9 and json.loads(inp.SourceCaseJSON)['ring_t_in']==0.5
    assert inp.SourceCaseSHA256=='2cc93e91477c162f91bb67465249621e427ee52a72a5b52d2fb6979206aaca10'
    d=pw.dimensions(inp);tops=set();thick=set()
    for r in q.Rings:
        s=r.Shape.copy();s.Placement=inp.PGL.Frame.inverse().multiply(s.Placement);b=s.optimalBoundingBox(False,False)
        tops.add(round((b.ZMax-d['bottom']*IN)/IN,6));thick.add(round(b.ZLength/IN,6))
    out.update(objects=len(doc.Objects),rings=len(q.Rings),ring_tops_in=sorted(tops),ring_thickness_in=sorted(thick),
               ring_weight_lb=q.RingWeightLb,bars=q.TotalBars,validation=pw.validate(inp,False)['status'],
               source_path=inp.SourcePath,engineering_status=inp.EngineeringStatus,status='PASS')
    assert out['validation']=='PASS' and thick=={0.5} and tops=={6.,42.,78.,114.,150.}
except Exception:out.update(status='FAIL',error=traceback.format_exc())
finally:
    if doc:App.closeDocument(doc.Name)
    (OUT/'installed-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
sys.stdout.flush();os._exit(0 if out.get('status')=='PASS' else 1)
