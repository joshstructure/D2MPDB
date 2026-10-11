"""Refresh linked ramp curves and their native screen tessellation; no save."""
import json,math,re,traceback
from datetime import datetime,timezone
import FreeCAD as App
import FreeCADGui as Gui
import Part
from pivy import coin
from . import bridge,drainage_trial as dt,adopt_drainage as ad
from .geometry import length,result
ROOT=bridge.ROOT;IN=bridge.IN
TARGETS=['CompletePGLTrace','RampAPGL','RampBPGL']

def nodes(n):
    yield n
    if hasattr(n,'getNumChildren'):
        for i in range(n.getNumChildren()):yield from nodes(n.getChild(i))

def display_audit(o):
    ns=list(nodes(o.ViewObject.RootNode))
    coords=max([n for n in ns if isinstance(n,coin.SoCoordinate3)],key=lambda n:n.point.getNum())
    indices=max([n.getField('coordIndex') for n in ns if n.getField('coordIndex')],key=lambda f:f.getNum())
    groups=[];group=[]
    for index in indices.getValues():
        if index<0:
            if group:groups.append(group);group=[]
        else:group.append(App.Vector(*coords.point[index].getValue()))
    if group:groups.append(group)
    if len(groups)!=len(o.Shape.Edges):raise ValueError('Rendered edge mapping differs from native edges')
    rows=[]
    for edge,points in zip(o.Shape.Edges,groups):
        distances=[]
        for a,b in zip(points,points[1:]):
            for t in [0.,.25,.5,.75,1.]:
                p=a+(b-a)*t;distances.append(Part.Vertex(p).distToShape(edge)[0]/IN)
        rows.append({'vertices':len(points),'max_display_distance_in':max(distances)})
    return {'display_deviation_percent':o.ViewObject.Deviation,'angular_deflection_deg':o.ViewObject.AngularDeflection.Value,'edges':rows,'max_display_distance_in':max(r['max_display_distance_in'] for r in rows)}

def audit(doc,tolerance):
    tol=length(tolerance,True);checks=[];rows=[];offset=0
    trace=doc.CompletePGLTrace
    ends=sorted([v.Point for v in doc.BridgePGL.Shape.Vertexes],key=lambda p:doc.BridgePGL.Frame.inverse().multVec(p).x)
    for side in ['A','B']:
        obj=doc.getObject('Ramp'+side+'PGL');display=display_audit(obj)
        checks.append(result(side+'_valid_continuous_wire',obj.Shape.isValid() and len(obj.Shape.Wires)==1 and not obj.Shape.isClosed()))
        checks.append(result(side+'_linked_to_current_trace',obj.Reference==trace))
        checks.append(result(side+'_bridge_endpoint',min(v.Point.distanceToPoint(ends[0 if side=='A' else -1]) for v in obj.Shape.Vertexes)<=1e-6))
        for i,edge in enumerate(obj.Shape.Edges):
            slab=doc.getObject(trace.SegmentSlabs[offset+i]);shape=slab.Shape.copy();errors=[];grades=[]
            for j in range(21):
                u=edge.FirstParameter+(edge.LastParameter-edge.FirstParameter)*j/20
                p=edge.valueAt(u);errors.append(abs(p.z-dt.top_at(shape,p.x,p.y)))
                v=edge.tangentAt(u);grades.append(100*v.z/math.hypot(v.x,v.y))
            checks.append(result(side+f'_edge_{i+1}_on_native_top',max(errors)<=tol,max_error_in=max(errors)/IN))
            rows.append({'side':side,'edge':i+1,'slab':slab.Name,'top_error_in':max(errors)/IN,'grade_range_percent':[min(grades),max(grades)]})
        offset+=len(obj.Shape.Edges)
        checks.append(result(side+'_curved_landing_rendered_with_intermediate_vertices',display['edges'][-1]['vertices']>2))
    checks.append(result('all_native_segments_audited',offset==len(trace.SegmentSlabs)))
    checks.append(result('no_pending_objects',not any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects)))
    return {'checks':checks,'segments':rows,'display':{s:display_audit(doc.getObject('Ramp'+s+'PGL')) for s in ['A','B']}}

def refresh(job):
    from .api import document,check_gui,atomic,compact
    doc=document(job['document']);check_gui(doc);length(job['tolerance'],True)
    angle=App.Units.Quantity(job['angular_deflection'])
    if angle.Unit!=App.Units.Quantity('1 deg').Unit or not 1<=angle.Value<=28.5:raise ValueError('Use supported angular display deflection in degrees')
    dev=job['display_deviation']
    if not isinstance(dev,str) or not dev.endswith(' %'):raise ValueError('Display deviation must be an explicit percentage')
    percent=float(dev[:-2])
    if not .01<=percent<=.5:raise ValueError('Display deviation outside supported limits')
    rid=job['request_id'];path=ROOT/'reports/transactions'/(rid+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['request']!=job:raise ValueError('Request ID reused')
        if old['status'] in ['PREPARED','VALIDATED']:raise ValueError('Inspect prior unknown outcome before retrying')
        return compact(old)
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Pending model objects')
    before=bridge.source_state(doc,[o.Name for o in doc.Objects]);protected=[n for n in before if n not in TARGETS]
    # Keep native wrappers: Shape.copy() normalizes BRep location tables.
    # The updater assigns new shapes, so these original wrappers remain intact.
    saved_shapes={n:doc.getObject(n).Shape for n in TARGETS}
    oldviews={n:{'Deviation':doc.getObject(n).ViewObject.Deviation,'AngularDeflection':doc.getObject(n).ViewObject.AngularDeflection.Value} for n in TARGETS}
    rec={'operation':'refresh_ramp_pgl','request':job,'transaction_id':rid,'timestamp':datetime.now(timezone.utc).isoformat(),'document':doc.Name,'status':'PREPARED','model_saved':False,'report_path':str(path),'errors':[],'checks':[],'rollback':'NOT NEEDED','before_display':{s:display_audit(doc.getObject('Ramp'+s+'PGL')) for s in ['A','B']}}
    atomic(path,rec);doc.openTransaction(rid)
    try:
        dt.TraceProxy(doc.CompletePGLTrace);doc.CompletePGLTrace.touch();doc.recompute([doc.CompletePGLTrace])
        for side in ['A','B']:
            o=doc.getObject('Ramp'+side+'PGL');ad.RampPGLProxy(o);o.touch();doc.recompute([o])
        for n in TARGETS:
            v=doc.getObject(n).ViewObject;v.Deviation=percent;v.AngularDeflection=job['angular_deflection']
        doc.recompute();Gui.updateGui()
        rec.update(audit(doc,job['tolerance']))
        rec['checks'].append(result('physical_model_and_annotations_exactly_preserved',bridge.source_state(doc,protected)=={n:before[n] for n in protected}))
        for s in ['A','B']:
            old=rec['before_display'][s];new=rec['display'][s]
            rec['checks'].append(result(s+'_display_accuracy_improved',new['max_display_distance_in']<old['max_display_distance_in']))
        if job.get('test_failure'):raise ValueError('Deliberate disposable rollback test')
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('PGL refresh check failed')
        rec['status']='VALIDATED';atomic(path,rec);doc.commitTransaction();rec['status']='PASS'
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc();doc.abortTransaction()
        for n,props in oldviews.items():
            for k,v in props.items():setattr(doc.getObject(n).ViewObject,k,v)
        # Do not regenerate the curves after abort: their original native
        # topology/location tables must be retained exactly.
        for n in TARGETS:doc.getObject(n).Shape=saved_shapes[n]
        for n in TARGETS:doc.getObject(n).purgeTouched()
        doc.recompute();Gui.updateGui()
        exact=bridge.source_state(doc,list(before))==before
        restored=all(abs(getattr(doc.getObject(n).ViewObject,k).Value-v if k=='AngularDeflection' else getattr(doc.getObject(n).ViewObject,k)-v)<1e-12 for n,p in oldviews.items() for k,v in p.items())
        pending=[o.Name for o in doc.Objects if 'Touched' in o.State or 'Invalid' in o.State]
        rec['rollback_pending_objects']=pending
        rec['rollback']='VERIFIED' if exact and restored and not pending else 'FAILED'
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','timestamp','document','status','model_saved','rollback','report_path']})+'\n')
    out=compact(rec);out.pop('segments',None)
    for key in ['before_display','display']:
        out[key]={s:{k:v for k,v in d.items() if k!='edges'} for s,d in rec.get(key,{}).items()}
    return out
