"""Source-linked top-of-slab ramp centerlines extending the bridge PGL reference."""
import json,re,traceback,math
from datetime import datetime,timezone
import FreeCAD as App
import Part
from . import bridge,mse
from .geometry import length,result
ROOT=bridge.ROOT;FT=bridge.FT;IN=bridge.IN

def top_face(slab):
    shape=slab.Shape.copy()
    faces=[f for f in shape.Faces if isinstance(f.Surface,Part.Plane) and abs(f.normalAt(0,0).z)>.5]
    if not faces:raise ValueError('No planar slab top: '+slab.Name)
    return max(faces,key=lambda f:f.CenterOfMass.z)

def bounds(face):
    b=face.BoundBox
    return dict(x0=b.XMin,x1=b.XMax,y0=b.YMin,y1=b.YMax,xm=(b.XMin+b.XMax)/2,ym=(b.YMin+b.YMax)/2)

def lift(face,xy):
    n=face.normalAt(0,0);p=face.Vertexes[0].Point;x,y=xy
    return App.Vector(x,y,p.z-(n.x*(x-p.x)+n.y*(y-p.y))/n.z)

def routes(o):
    # Endpoints of the existing actual PGL geometry, sorted along its local axis.
    pgl=o.PGL;vs=[v.Point for v in pgl.Shape.Vertexes]
    vs.sort(key=lambda p:pgl.Frame.inverse().multVec(p).x)
    pa,pb=vs[0],vs[-1]
    if abs(pb.y-pa.y)<1e-8:raise ValueError('This ramp layout requires a non-horizontal PGL in plan')
    pgl_x=lambda y:pa.x+(pb.x-pa.x)*(y-pa.y)/(pb.y-pa.y)
    made={};metadata=[];joins=[];tieins=[]
    for side,slabs in [('A',list(o.RampASlabs)),('B',list(o.RampBSlabs))]:
        if len(slabs)!=(4 if side=='A' else 8):raise ValueError('Unexpected slab route count')
        faces=[top_face(s) for s in slabs];b=[bounds(f) for f in faces]
        if side=='A':
            plans=[[(b[0]['x0'],b[0]['ym']),(b[0]['x1'],b[0]['ym'])],
                [(b[1]['x0'],b[0]['ym']),(b[1]['xm'],b[0]['ym']),(b[1]['xm'],b[2]['ym']),(b[1]['x0'],b[2]['ym'])],
                [(b[2]['x1'],b[2]['ym']),(b[2]['x0'],b[2]['ym'])],
                [(b[3]['x1'],b[2]['ym']),(pgl_x(b[2]['ym']),b[2]['ym']),(pgl_x(b[3]['y0']),b[3]['y0'])]]
        else:
            plans=[[(b[0]['xm'],b[0]['y0']),(b[0]['xm'],b[0]['y1'])],
                [(b[0]['xm'],b[1]['y0']),(b[0]['xm'],b[2]['ym']),(b[1]['x0'],b[2]['ym'])],
                [(b[2]['x1'],b[2]['ym']),(b[2]['x0'],b[2]['ym'])],
                [(b[3]['x1'],b[2]['ym']),(b[3]['xm'],b[2]['ym']),(b[3]['xm'],b[4]['ym']),(b[3]['x1'],b[4]['ym'])],
                [(b[4]['x0'],b[4]['ym']),(b[4]['x1'],b[4]['ym'])],
                [(b[5]['x0'],b[4]['ym']),(b[5]['xm'],b[4]['ym']),(b[5]['xm'],b[6]['ym']),(b[5]['x0'],b[6]['ym'])],
                [(b[6]['x1'],b[6]['ym']),(b[6]['x0'],b[6]['ym'])],
                [(b[7]['x1'],b[6]['ym']),(pgl_x(b[6]['ym']),b[6]['ym']),(pgl_x(b[7]['y1']),b[7]['y1'])]]
        edges=[];last=None;side_rows=[]
        for slab,face,xy in zip(slabs,faces,plans):
            points=[lift(face,p) for p in xy]
            if last is not None:joins.append({'side':side,'slab':slab.Name,'gap_mm':last.distanceToPoint(points[0])})
            for a,z in zip(points[:-1],points[1:]):
                edges.append(Part.makeLine(a,z));side_rows.append({'side':side,'slab':slab,'face':face,'start':a,'end':z})
            last=points[-1]
        # Refuse a false continuous wire across a real slab step or gap.
        if any(j['gap_mm']>1e-6 for j in joins if j['side']==side):
            raise ValueError('Ramp slab tops are discontinuous along the proposed trace: '+side)
        made[side]=Part.Wire(edges);metadata.extend(side_rows)
        target=pa if side=='A' else pb
        tieins.append({'side':side,'plan_gap_in':math.hypot(last.x-target.x,last.y-target.y)/IN,
            'ramp_minus_bridge_PGL_in':(last.z-target.z)/IN,
            'ramp_endpoint_ft':[v/FT for v in [last.x,last.y,last.z]],
            'PGL_endpoint_ft':[v/FT for v in [target.x,target.y,target.z]]})
    return made,metadata,joins,tieins

class TraceProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        wires,metadata,joins,tieins=routes(o)
        o.Shape=Part.makeCompound([wires['A'],o.PGL.Shape.copy(),wires['B']])
        o.RampALength=wires['A'].Length;o.RampBLength=wires['B'].Length
        o.SegmentSlabs=[r['slab'].Name for r in metadata]
        o.SegmentGradesPercent=[100*(r['end'].z-r['start'].z)/math.hypot(r['end'].x-r['start'].x,r['end'].y-r['start'].y) for r in metadata]
        o.BridgeTieIns=[f"Ramp {r['side']}: plan gap {r['plan_gap_in']:.6f} in; ramp minus bridge PGL {r['ramp_minus_bridge_PGL_in']:+.6f} in" for r in tieins]

def validate(o,tolerance='0.001 in'):
    tol=length(tolerance,positive=True);wires,meta,joins,ties=routes(o);checks=[];details=[]
    children=o.Shape.childShapes()
    checks.append(result('three_reference_wires',len(children)==3 and len(o.Shape.Solids)==0 and o.Shape.isValid()))
    actual=list(children[0].Edges)+list(children[2].Edges)
    checks.append(result('all_21_ramp_segments',len(actual)==len(meta)==21))
    checks.append(result('all_12_slabs_traced',len(set(r['slab'].Name for r in meta))==12))
    for index,(edge,row) in enumerate(zip(actual,meta)):
        face=top_face(row['slab']);n=face.normalAt(0,0)
        a,z=[v.Point for v in edge.Vertexes];dx,dy,dz=z.x-a.x,z.y-a.y,z.z-a.z
        span=math.hypot(dx,dy);grade=100*dz/span
        expected=-100*(n.x*dx+n.y*dy)/(n.z*span)
        sampled=[edge.valueAt(edge.FirstParameter+(edge.LastParameter-edge.FirstParameter)*t) for t in [0,.25,.5,.75,1]]
        distances=[Part.Vertex(p).distToShape(face)[0] for p in sampled]
        common=edge.common(face).Length
        checks.append(result(f'segment_{index+1}_on_physical_top',max(distances)<=tol and abs(common-edge.Length)<=tol,max_distance_in=max(distances)/IN))
        checks.append(result(f'segment_{index+1}_physical_grade',abs(grade-expected)<=1e-7,actual_percent=grade,slab=row['slab'].Name))
        checks.append(result(f'segment_{index+1}_route_position',min(a.distanceToPoint(row['start'])+z.distanceToPoint(row['end']),z.distanceToPoint(row['start'])+a.distanceToPoint(row['end']))<=2*tol))
        details.append({'segment':index+1,'side':row['side'],'slab':row['slab'].Name,'length_ft':edge.Length/FT,'grade_percent':grade,'max_top_distance_in':max(distances)/IN})
    checks.append(result('ramp_slab_junctions_continuous',all(j['gap_mm']<=tol for j in joins)))
    center=children[1];pgl=o.PGL.Shape
    checks.append(result('existing_bridge_PGL_geometry_retained',abs(center.Length-pgl.Length)<=tol and center.distToShape(pgl)[0]<=tol and abs(center.common(pgl).Length-pgl.Length)<=tol))
    checks.append(result('source_links',all(s.Document==o.Document for s in list(o.RampASlabs)+list(o.RampBSlabs)) and o.PGL.Document==o.Document))
    checks.append(result('reference_rendered',not bridge.display_state(o)['render_bounds_empty']))
    return {'checks':checks,'segments':details,'junctions':joins,'bridge_tie_ins':ties,'lengths_ft':{'A':children[0].Length/FT,'B':children[2].Length/FT},'ramp_segments':len(actual)}

def add(job):
    from .api import document,check_gui,atomic,compact
    rid=job['request_id'];path=ROOT/'reports/transactions'/(rid+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    if path.exists():
        r=json.loads(path.read_text(encoding='utf-8'))
        if r['request']!=job:raise ValueError('Request ID reused for a different job')
        if r['status'] in ['PREPARED','VALIDATED']:raise RuntimeError('Inspect the unknown previous outcome before retry')
        return compact(r)
    doc=document(job['document']);check_gui(doc);length(job['tolerance'],positive=True)
    if doc.getObject(job['name']):raise ValueError('Trace already exists; do not duplicate')
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Resolve existing pending recomputes first')
    sources={side:[doc.getObject(n) for n in job['slabs'][side]] for side in ['A','B']}
    if any(o is None or 'Shape' not in o.PropertiesList for side in sources.values() for o in side):raise ValueError('An explicit slab source is missing')
    if doc.getObject(job['pgl']) is None:raise ValueError('PGL Name missing')
    all_before=bridge.source_state(doc,[o.Name for o in doc.Objects]);protected=[n for n in all_before if n!='BridgeAssembly']
    members=list(doc.BridgeAssembly.Group)
    rec={'operation':'add_ramp_pgl_trace','request':job,'transaction_id':rid,'document':doc.Name,
        'timestamp':datetime.now(timezone.utc).isoformat(),'status':'PREPARED','report_path':str(path),'model_saved':False,
        'checks':[],'errors':[],'rollback':'NOT NEEDED',
        'warnings':['Square centerline turns through landings; final landing legs align with bridge PGL in plan.','Existing bridge tie-in gaps/elevation differences are retained; no artificial connecting segments.']}
    atomic(path,rec);doc.openTransaction(rid)
    try:
        o=doc.addObject('Part::FeaturePython',job['name']);o.Label='Complete PGL — bridge and both ramp slab centerlines'
        mse.prop(o,'App::PropertyLink','PGL',doc.getObject(job['pgl']),'Sources')
        for side in ['A','B']:mse.prop(o,'App::PropertyLinkList','Ramp'+side+'Slabs',sources[side],'Sources')
        for n in ['RampALength','RampBLength']:mse.prop(o,'App::PropertyLength',n,'0 ft','Measured trace')
        for n in ['SegmentSlabs','BridgeTieIns']:mse.prop(o,'App::PropertyStringList',n,[],'Measured trace')
        mse.prop(o,'App::PropertyFloatList','SegmentGradesPercent',[],'Measured trace')
        mse.prop(o,'App::PropertyString','RoutingBasis','Ramp lane centerlines; square turns through landing centers; final legs on bridge PGL plan extension; actual top BRep elevations.','Sources')
        for n in ['RampALength','RampBLength','SegmentSlabs','BridgeTieIns','SegmentGradesPercent']:o.setEditorMode(n,1)
        TraceProxy(o);bridge.initialize_display(o);doc.BridgeAssembly.addObject(o);doc.recompute([o]);doc.recompute()
        qa=validate(o,job['tolerance']);rec.update(qa)
        after=bridge.source_state(doc,protected)
        rec['preservation_differences']={n:{k:[v,after[n][k]] for k,v in all_before[n].items() if v!=after[n][k]} for n in protected if all_before[n]!=after[n]}
        rec['checks'].append(result('all_existing_native_geometry_preserved',not rec['preservation_differences']))
        rec['checks'].append(result('assembly_membership_preserved',list(doc.BridgeAssembly.Group)==members+[o]))
        rec['checks'].append(result('no_pending_recomputes',not any('Touched' in x.State or 'Invalid' in x.State for x in doc.Objects)))
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Ramp PGL trace check failed')
        rec['status']='VALIDATED';atomic(path,rec);doc.commitTransaction()
        rec['status']='PASS — EXISTING BRIDGE TIE-IN DISCREPANCIES RETAINED';rec['object']=o.Name
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc();doc.abortTransaction();doc.recompute()
        rec['rollback']='VERIFIED' if set(x.Name for x in doc.Objects)==set(all_before) and bridge.source_state(doc,list(all_before))==all_before else 'FAILED'
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({k:rec[k] for k in ['timestamp','operation','transaction_id','document','status','report_path','model_saved','rollback']})+'\n')
    out=compact(rec);out.pop('segments',None);out.pop('junctions',None);return out
