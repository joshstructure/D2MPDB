"""B4 geotechnical section exchange: live geometry capture and terrain reference."""
import hashlib,json,re,traceback
from datetime import datetime,timezone
from pathlib import Path
import FreeCAD as App
import Mesh
import numpy as np
from . import bridge,mse
from .geometry import length,result
from .terrain_exchange import Terrain,US_FOOT_M
ROOT=bridge.ROOT

def checked_path(value):
    p=(ROOT/value).resolve()
    if not p.is_relative_to(ROOT):raise ValueError('All artifacts must remain in CAD_AI')
    return p

def capture(job):
    from .api import document,check_gui,atomic
    doc=document(job['document']);check_gui(doc)
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Pending model edits')
    dest=checked_path(job['output_directory'])
    if dest.exists():raise ValueError('Use a new geometry snapshot directory')
    before=bridge.source_state(doc,[o.Name for o in doc.Objects])
    dest.mkdir(parents=True);(dest/'brep').mkdir();parts=[];walls=[];slabs=[]
    for o in doc.MSEAssembly.FinishedConcrete:
        s=o.Shape.copy();s.exportBrep(str(dest/'brep'/(o.Name+'.brep')))
        pts=np.array([[v.Point.x,v.Point.y,v.Point.z] for v in s.Vertexes])
        parts.append({'name':o.Name,'label':o.Label,'kind':'Footing' if o.Name.startswith('Footing') else 'Wall' if o.Name.startswith('Wall') else 'Slab','bounds_mm':[pts.min(0).tolist(),pts.max(0).tolist()],'volume_mm3':s.Volume,'source_native_brep_sha256':before[o.Name]['shape'],'file_sha256':hashlib.sha256((dest/'brep'/(o.Name+'.brep')).read_bytes()).hexdigest()})
    for o in doc.Objects:
        if o.Name.startswith('Wall') and 'BaseControls' in o.PropertiesList:
            walls.append({'name':o.Name,'start':list(o.Start),'tangent':list(o.Tangent),'normal':list(o.Normal),'base':[list(p) for p in o.BaseControls],'top':[list(p) for p in o.ComputedTop]})
        if o.Name.endswith('Surface') and 'PlanCorners' in o.PropertiesList:
            slabs.append({'name':o.Name,'corners':[list(p) for p in o.PlanCorners]})
    # Supplement slab boundary stations with actual adopted drainage transition points.
    keypoints=[{'object':o.Name,'point':list(o.MeasuredPoint),'id':o.PointID} for o in doc.SlabElevations.Group if 'MeasuredPoint' in o.PropertiesList]
    checks=[result('entire_live_document_exactly_preserved',bridge.source_state(doc,list(before))==before),result('all_46_MSE_components_captured',len(parts)==46)]
    data={'document':doc.Name,'timestamp':datetime.now(timezone.utc).isoformat(),'source_file':doc.FileName,'source_state':before,'parts':parts,'walls':walls,'slabs':slabs,'keypoints':keypoints,'units':'mm','checks':checks,'model_saved':False}
    atomic(dest/'manifest.json',data)
    if any(c['status']=='FAIL' for c in checks):raise ValueError('Live geometry capture failed preservation')
    return {'status':'PASS','directory':str(dest),'components':len(parts),'checks':checks,'model_saved':False}

def add_terrain(job):
    from .api import document,check_gui,atomic,compact
    doc=document(job['document']);check_gui(doc);tol=length(job['tolerance'],True)
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Pending model edits')
    rid=job['request_id'];name=job['object_name']
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]+',name):raise ValueError('Invalid explicit name or request ID')
    report=ROOT/'reports/transactions'/(rid+'.json')
    if report.exists():raise ValueError('Inspect prior transaction before retry')
    if doc.getObject(name):raise ValueError('Terrain reference already exists')
    for key in ['source','cache','placement']:
        if hashlib.sha256(checked_path(job[key]).read_bytes()).hexdigest()!=job[key+'_sha256']:raise ValueError(key+' changed')
    data=np.load(checked_path(job['cache']));p=data['points'];f=data['faces'];terrain=Terrain(p,f)
    reg=json.loads(checked_path(job['placement']).read_text())
    if reg['scale']!=1 or reg['max_vertex_error_m']>tol/1000:raise ValueError('Unverified model placement')
    before=bridge.source_state(doc,[o.Name for o in doc.Objects]);names=set(before)
    rec={'operation':'add_verified_terrain_reference','document':doc.Name,'request':job,'transaction_id':rid,'timestamp':datetime.now(timezone.utc).isoformat(),'status':'PREPARED','checks':[],'errors':[],'rollback':'NOT NEEDED','model_saved':False,'report_path':str(report)}
    atomic(report,rec);doc.openTransaction(rid)
    try:
        o=doc.addObject('Mesh::Feature',name);o.Label=job['label'];o.Mesh=Mesh.Mesh((p[f]*1000).tolist())
        for n,t,value in [('SourceLandXML','App::PropertyFile',str(checked_path(job['source']))),('SourceSHA256','App::PropertyString',job['source_sha256']),('SurfaceName','App::PropertyString',job['surface_name']),('SourceUnits','App::PropertyString','US survey feet'),('PlacementVerification','App::PropertyString',json.dumps(reg)),('Role','App::PropertyString','Supplied Pond 14D terrain; separate from existing ground; no assumed soil layers')]:
            mse.prop(o,t,n,value,'Terrain source');o.setEditorMode(n,1)
        if App.GuiUp:
            o.ViewObject.ShapeColor=(.18,.52,.75);o.ViewObject.LineColor=(.08,.32,.52);o.ViewObject.Transparency=35;o.ViewObject.DisplayMode='Flat Lines';o.ViewObject.Visibility=True
        doc.recompute([o])
        actual=np.array([[list(v) for v in a.Points] for a in o.Mesh.Facets])/1000
        err=float(np.max(np.linalg.norm(actual-p[f],axis=2)))
        rec['checks']=[result('original_triangle_count',o.Mesh.CountFacets==len(f)),result('actual_mesh_coordinate_accuracy',err<=tol/1000,max_error_mm=err*1000),result('entire_original_model_exactly_preserved',bridge.source_state(doc,list(before))==before),result('source_triangle_connectivity',actual.shape==p[f].shape)]
        z=(p[:,2]+reg['translation_m'][2])/US_FOOT_M
        rec['terrain']={'object':name,'vertices':len(p),'triangles':len(f),'elevation_range_us_ft':[float(z.min()),float(z.max())]}
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Terrain import validation failed')
        if job.get('test_failure'):raise ValueError('Deliberate terrain rollback test')
        rec['status']='VALIDATED';atomic(report,rec);doc.commitTransaction();rec['status']='PASS'
    except Exception as exc:
        rec['status']='FAIL';rec['errors']=[str(exc)];rec['traceback']=traceback.format_exc();doc.abortTransaction()
        rec['rollback']='VERIFIED' if set(o.Name for o in doc.Objects)==names and bridge.source_state(doc,list(before))==before else 'FAILED'
    atomic(report,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','document','status','model_saved','rollback','report_path']})+'\n')
    return compact(rec)
