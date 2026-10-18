"""Editable edge-based pedestal grids with a strict maximum pitch.

Station lists contain explicit unit-bearing distances from the pedestal's
local minimum face. Existing average-pitch documents retain their old behavior.
"""
import json,math
import FreeCAD as App
from . import pedestal_ubars as p,bridge
from .mse import prop as _new_property
from .geometry import length,result,bounds
IN=25.4

def prop(obj,typ,name,value,group):
    if name in obj.PropertiesList:setattr(obj,name,value)
    else:_new_property(obj,typ,name,value,group)

def configure(inp,settings):
    inp.AutoSync=False
    for key,value in [('Cover','2 in'),('CapCover','3 in'),('Spacing','6 in')]:setattr(inp,key,value)
    for key in ['LongitudinalStart','LongitudinalEnd','TransverseStart','TransverseEnd','MinimumEmbedment']:
        value=settings[key];length(value,positive=True)
        prop(inp,'App::PropertyLength','Edge'+key if key!='MinimumEmbedment' else key,value,'Edge grid')
    for key in ['XStations','YStations']:
        for value in settings[key]:length(value,positive=True)
        prop(inp,'App::PropertyStringList','Edge'+key,settings[key],'Edge grid')
    prop(inp,'App::PropertyBool','MaximumSpacingLayout',True,'Edge grid')
    prop(inp,'App::PropertyString','EdgeBasis','2026-10-17: #4 at 6 in MAXIMUM EW; 2 in pedestal / 3 in cap cover; near-face legs share cap-stirrup vertical plane. Contact permitted; no positive overlaps.','Edge grid')
    inp.AutoSync=True

def grid(inp,pb,cb):
    a=pb.XMin+inp.EdgeLongitudinalStart.Value;b=pb.XMax-inp.EdgeLongitudinalEnd.Value
    c=pb.YMin+inp.EdgeTransverseStart.Value;e=pb.YMax-inp.EdgeTransverseEnd.Value
    ys=[pb.YMin+length(v) for v in inp.EdgeXStations]
    xs=[pb.XMin+length(v) for v in inp.EdgeYStations]
    if any(len(v)<2 or v!=sorted(v) for v in (xs,ys)):raise ValueError('Edge stations must increase and include at least two bars')
    r=inp.Diameter.Value/2;cover=inp.Cover.Value;cc=inp.CapCover.Value
    if min(a,min(xs))<max(pb.XMin+cover+r,cb.XMin+cc+r)-p.TOL or max(b,max(xs))>min(pb.XMax-cover-r,cb.XMax-cc-r)+p.TOL:raise ValueError('X edge layout violates cover')
    if min(c,min(ys))<max(pb.YMin+cover+r,cb.YMin+cc+r)-p.TOL or max(e,max(ys))>min(pb.YMax-cover-r,cb.YMax-cc-r)+p.TOL:raise ValueError('Y edge layout violates cover')
    return a,b,c,e,xs,ys

def stirrup_planes(inp):
    """Read vertical straight portions of physical native stirrup paths."""
    ci=inp.CapInputs;rows=json.loads(ci.LayoutJSON);values=[]
    transform=inp.PGL.Frame.inverse().multiply(ci.CageFrame)
    for rb in inp.Document.getObject('Cage'+inp.Host.SupportID+'Quantities').Bars:
        if rows[rb.Base.BarID]['kind']!='hoop':continue
        for edge in rb.Base.Shape.Edges:
            if len(edge.Vertexes)!=2:continue
            a,b=[transform.multVec(v.Point) for v in edge.Vertexes]
            if abs(a.x-b.x)<1e-6 and abs(a.z-b.z)>IN:
                values.append(a.x)
    if not values:raise ValueError('No native vertical stirrup legs')
    return min(values),max(values)

def alignment_checks(inp):
    pb=bounds(bridge.local_shape(inp.Host));cb=bounds(bridge.local_shape(inp.Cap));planes=stirrup_planes(inp)
    relevant=[]
    if abs(pb.XMin-cb.XMin)<p.TOL:relevant.append((0,planes[0]))
    if abs(pb.XMax-cb.XMax)<p.TOL:relevant.append((1,planes[1]))
    checks=[]
    for rb in inp.Document.getObject(inp.Prefix+'Quantities').Bars:
        if not rb.Base.BarID.startswith('X'):continue
        xs=sorted({v.Point.x for e in rb.Base.Shape.Edges for v in e.Vertexes if abs(v.Point.z-min(w.Point.z for w in rb.Base.Shape.Vertexes))<p.TOL})
        for index,plane in relevant:
            actual=xs[0 if index==0 else -1]
            checks.append(result(rb.Name+'_near_face_'+str(index),abs(actual-plane)<p.TOL,actual_in=actual/IN,stirrup_plane_in=plane/IN))
    return checks

def apply(doc,settings,request_id,report_dir):
    """One reversible modeling transaction, including independent physical QA."""
    from pathlib import Path
    report_dir=Path(report_dir);report_dir.mkdir(parents=True,exist_ok=True)
    path=report_dir/(request_id+'.json')
    if path.exists():raise ValueError('Transaction already exists; inspect before retry')
    inputs=[doc.getObject(n) for n in settings]
    if len(inputs)!=6 or any(i is None for i in inputs):raise ValueError('Exactly six named existing pedestal inputs required')
    protected=[o.Name for o in doc.Objects if not o.Name.startswith('PedSteel') and o.Name not in ['PedestalSteelChecks','PedestalReinforcement']]
    before=bridge.source_state(doc,protected)
    record={'transaction_id':request_id,'status':'PREPARED','settings':settings,'protected':protected}
    def journal():path.write_text(json.dumps(record,indent=2,default=str)+'\n')
    journal();doc.openTransaction('Pedestal edge alignment and maximum spacing')
    try:
        for inp in inputs:
            configure(inp,settings[inp.Name]);p.regenerate(inp)
            p.write_schedule(inp,doc.getObject(inp.Prefix+'Schedule'),doc.getObject(inp.Prefix+'Quantities').Bars)
            doc.recompute([doc.getObject(inp.Prefix+'Schedule')])
        record['results']={i.Name:p.validate(i) for i in inputs}
        record['alignment']=[c for i in inputs for c in alignment_checks(i)]
        record['clashes']=p.clash_check(doc,inputs)
        record['protected_unchanged']=before==bridge.source_state(doc,protected)
        failures=[c for r in record['results'].values() for c in r['checks'] if c['status']!='PASS']+[c for c in record['alignment'] if c['status']!='PASS']
        record['failures']=failures
        if failures or record['clashes']['status']!='PASS' or not record['protected_unchanged']:raise ValueError('Physical checks failed; transaction aborted')
        check=doc.getObject('PedestalSteelChecks');check.Status='PASS';check.ReportJSON=json.dumps(record['clashes'])
        doc.PedestalReinforcement.Label='All pedestals - #4 U-bars at 6 in maximum each way'
        doc.commitTransaction();record['status']='APPLIED_UNSAVED'
    except Exception:
        import traceback
        record['status']='ROLLED_BACK';record['traceback']=traceback.format_exc();doc.abortTransaction()
        raise
    finally:journal()
    return record
