"""Native B4 footing revision and verified local LandXML reference. Never saves."""
import hashlib,json,re,traceback
from datetime import datetime,timezone
from pathlib import Path
import FreeCAD as App
import Part,Mesh
import numpy as np
from . import bridge,mse
from .geometry import length,result
from .terrain_exchange import Terrain,lower_envelope,US_FOOT_M

ROOT=bridge.ROOT
WALLS=('B5','B8','B9')
JOINTS={'B5':['FootingB6Finished'],'B8':['FootingB5Finished'],'B9':['FootingB2']}
TERRAIN_NAME='ExistingTerrainB4'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def vlist(values):return [[v.x,v.y,v.z] for v in values]
def pending(doc):return [o.Name for o in doc.Objects if 'Touched' in o.State or 'Invalid' in o.State]
def file_in_root(s):
    p=(ROOT/s).resolve()
    if not p.is_relative_to(ROOT):raise ValueError('Artifact outside CAD_AI')
    return p

def native_clashes(parts):
    rows=[];shapes=[(o.Name,o.Shape.copy()) for o in parts]
    for i,(an,a) in enumerate(shapes):
        for bn,b in shapes[i+1:]:
            if not a.BoundBox.intersect(b.BoundBox):continue
            volume=abs(a.common(b).Volume)
            if volume>0:rows.append({'a':an,'b':bn,'volume_mm3':volume})
    return rows

def bridge_clashes(doc):
    rows=[];existing=[(o.Name,o.Shape.copy()) for o in doc.MSEAssembly.FinishedConcrete]
    for a in doc.BridgeGeometryChecks.Components:
        if a.ComponentKind=='WallEnvelope':continue
        shape=a.Shape.copy()
        for bn,b in existing:
            if shape.BoundBox.intersect(b.BoundBox):
                volume=abs(shape.common(b).Volume)
                if volume>0:rows.append({'a':a.Name,'b':bn,'volume_mm3':volume})
    return rows

def recompute_revision(doc):
    # This revision does not alter bridge geometry. Its legacy checker performs
    # common operations on live slab BReps, changing their internal cache flags.
    # Recompute the revised dependency graph without that checker; its complete
    # bridge/MSE overlap check is independently rerun on deep copies below.
    checker=doc.BridgeGeometryChecks
    doc.recompute([o for o in doc.Objects if o!=checker])
    checker.purgeTouched()

def restore_visibility(doc,views,exclude=()):
    # Group visibility propagates to members. Restore groups first, then every
    # individual view, changing only differing values to avoid fresh cascades.
    names=[n for n in views if n not in exclude]
    names.sort(key=lambda n:0 if doc.getObject(n).TypeId=='App::DocumentObjectGroup' else 1)
    for n in names:
        v=doc.getObject(n).ViewObject
        if v.Visibility!=views[n]:v.Visibility=views[n]

def make_terrain(doc,job,triangles,placement):
    o=doc.addObject('Mesh::Feature',TERRAIN_NAME)
    o.Label='Existing terrain — Ex_I-95_Middle (survey reference)'
    o.Mesh=Mesh.Mesh((triangles*1000).tolist())
    props={'SourceLandXML':('App::PropertyFile',str(file_in_root(job['terrain_source']))),
           'SourceSHA256':('App::PropertyString',job['terrain_source_sha256']),
           'CacheSHA256':('App::PropertyString',job['terrain_cache_sha256']),
           'PlacementVerification':('App::PropertyString',json.dumps(placement,sort_keys=True)),
           'SourceUnits':('App::PropertyString','US survey feet; model coordinates millimeters'),
           'Crop':('App::PropertyString','Original triangles intersecting model plan bounds plus 2 m'),
           'Role':('App::PropertyString','Existing-ground reference mesh; excluded from concrete quantities and OBM solid export')}
    for n,(t,value) in props.items():mse.prop(o,t,n,value,'Terrain source');o.setEditorMode(n,1)
    if App.GuiUp:
        o.ViewObject.ShapeColor=(.38,.60,.34);o.ViewObject.LineColor=(.24,.38,.22)
        o.ViewObject.Transparency=65;o.ViewObject.DisplayMode='Flat Lines' if 'Flat Lines' in o.ViewObject.listDisplayModes() else 'Shaded'
        o.ViewObject.Visibility=True
    return o

def geometry_audit(doc,terrain,z,tol,old_shapes,old_controls):
    checks=[];rows=[]
    for wall in WALLS:
        wp=doc.getObject('Wall'+wall+'Profile');raw=doc.getObject('Footing'+wall)
        foot=doc.getObject(raw.Name+'Finished');wraw=doc.getObject('Wall'+wall)
        measured=raw.Shape.optimalBoundingBox(False,False)
        finalbox=foot.Shape.optimalBoundingBox(False,False)
        expected_length=old_controls[wall][-1][0]-old_controls[wall][0][0]
        expected_volume=expected_length*doc.MSEInputs.FootingWidth.Value*doc.MSEInputs.FootingThickness.Value
        checks += [result(wall+'_native_parametric_sources',raw.TypeId=='Part::Extrusion' and foot.TypeId=='Part::Cut' and foot.Base==raw and raw.Base.WallProfile==wp and isinstance(wp.Proxy,mse.WallProfileProxy)),
                   result(wall+'_nominal_geometry',raw.Shape.isValid() and len(raw.Shape.Solids)==1),
                   result(wall+'_finished_geometry',foot.Shape.isValid() and len(foot.Shape.Solids)==1 and foot.Shape.Volume>0),
                   result(wall+'_full_top_level',abs(measured.ZMax-z)<=tol and abs(finalbox.ZMax-z)<=tol and all(abs(v.Point.z-z)<=tol for f in foot.Shape.Faces if f.normalAt(0,0).z>.999999 for v in f.Vertexes)),
                   result(wall+'_six_inch_thickness',abs(measured.ZLength-length('6 in'))<=tol and abs(finalbox.ZLength-length('6 in'))<=tol,measured_in=finalbox.ZLength/25.4),
                   result(wall+'_nominal_volume',abs(raw.Shape.Volume-expected_volume)<=max(.001,expected_volume*1e-10)),
                   result(wall+'_wall_top_preserved',vlist(wp.ComputedTop)==old_controls[wall+'_top']),
                   result(wall+'_wall_base_level',abs(wraw.Shape.optimalBoundingBox(False,False).ZMin-z)<=tol)]
        # Independent geometric wall/footing interface (horizontal common face).
        bottom=Part.makeCompound([f for f in wraw.Shape.copy().Faces if f.normalAt(0,0).z<-.999999])
        top=Part.makeCompound([f for f in raw.Shape.copy().Faces if f.normalAt(0,0).z>.999999])
        contact=bottom.common(top);unsupported=bottom.cut(top)
        checks.append(result(wall+'_wall_footing_contact',bottom.distToShape(top)[0]<=tol and abs(contact.Area-bottom.Area)<=max(.001,bottom.Area*1e-10) and unsupported.Area<=.001,contact_area_mm2=contact.Area,wall_base_area_mm2=bottom.Area,unsupported_area_mm2=unsupported.Area))
        # Nominal union is preserved by native junction cuts against neighboring footings.
        tools=doc.getObject(raw.Name+'JointTools').Shape
        reconstruction=foot.Shape.fuse(raw.Shape.common(tools))
        mismatch=raw.Shape.cut(reconstruction).Volume+reconstruction.cut(raw.Shape).Volume
        checks.append(result(wall+'_junction_material_preserved',abs(mismatch)<=max(.001,raw.Shape.Volume*1e-10),difference_mm3=mismatch))
        # Determine both physical wall-face terrain traces from the actual wall vertices.
        pts=np.array([[v.Point.x,v.Point.y,v.Point.z] for v in wraw.Shape.Vertexes])/1000
        start=np.array([wp.Start.x,wp.Start.y,wp.Start.z])/1000
        tangent=np.array([wp.Tangent.x,wp.Tangent.y,wp.Tangent.z]);normal=np.array([wp.Normal.x,wp.Normal.y,wp.Normal.z])
        stations=(pts-start)@tangent;offsets=(pts-start)@normal
        a=start+tangent*min(stations);b=start+tangent*max(stations)
        profiles=[terrain.line(a+normal*x,b+normal*x) for x in [min(offsets),max(offsets)]]
        ts,ground=lower_envelope(profiles);cover=(ground-measured.ZMax/1000)/US_FOOT_M
        checks.append(result(wall+'_minimum_two_survey_feet_to_top',float(min(cover))>=2,min_cover_ft=float(min(cover))))
        old=old_shapes[raw.Name];oldbox=old.optimalBoundingBox(False,False)
        checks.append(result(wall+'_plan_footprint_preserved',max(abs(getattr(measured,k)-getattr(oldbox,k)) for k in ['XMin','YMin','XMax','YMax'])<=tol))
        rows.append({'wall':wall,'old_top_levels_native_ft':sorted({p[2]/304.8 for p in old_controls[wall]}),'new_top_native_ft':measured.ZMax/304.8,'bottom_native_ft':measured.ZMin/304.8,'minimum_cover_us_ft':float(min(cover)),'maximum_cover_us_ft':float(max(cover)),'native_nominal_volume_ft3':raw.Shape.Volume/304.8**3,'finished_volume_ft3':foot.Shape.Volume/304.8**3})
    return checks,rows

def update(job):
    from .api import document,check_gui,preflight,atomic,compact
    doc=document(job['document']);check_gui(doc)
    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.updateGui();check_gui(doc)
    if job['targets']!=['Wall'+w+'Profile' for w in WALLS]:raise ValueError('This tested adapter updates B5, B8 and B9 together')
    if job['minimum_cover']!='2 us-ft' or job['footing_thickness']!='6 in':raise ValueError('Unsupported cover or thickness')
    tol=length(job['tolerance'],True);requested=length(job['top_elevation'])
    if abs(doc.MSEInputs.FootingThickness.Value-length(job['footing_thickness']))>tol:raise ValueError('Unexpected footing thickness')
    rid=job['request_id']
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    path=ROOT/'reports/transactions'/(rid+'.json')
    if path.exists():
        old=json.loads(path.read_text())
        if old['request']!=job:raise ValueError('Request ID reused for a different job')
        if old['status'] in ['PREPARED','VALIDATED']:raise ValueError('Inspect unknown prior outcome before retry')
        return compact(old)
    if pending(doc):raise ValueError('Resolve pending model objects: '+str(pending(doc)))
    for w in WALLS:
        o=doc.getObject('Wall'+w+'Profile');preflight(o,{'BaseControls':None})
        if not isinstance(o.Proxy,mse.WallProfileProxy):raise ValueError('Native wall proxy unavailable: '+o.Name)
        for suffix in ['Finished','JointTools']:
            if doc.getObject('Footing'+w+suffix):raise ValueError('Footing revision already exists')
    if doc.getObject(TERRAIN_NAME):raise ValueError('Terrain reference already exists')
    z=max(p.z for p in doc.WallB5Profile.BaseControls)
    if abs(z-requested)>tol:raise ValueError('Requested top must match existing full-precision upper B5 bench')
    for key in ['terrain_cache','terrain_source','placement']:
        if sha(file_in_root(job[key]))!=job[key+'_sha256']:raise ValueError(key+' hash changed')
    triangles=np.load(file_in_root(job['terrain_cache']))['triangles'];placement=json.loads(file_in_root(job['placement']).read_text())
    terrain=Terrain(triangles.reshape(-1,3),np.arange(len(triangles)*3).reshape(-1,3))
    if not np.isfinite(triangles).all() or placement['max_vertex_error_m']>tol/1000 or placement['scale']!=1:raise ValueError('Unverified terrain reference')
    before=bridge.source_state(doc,[o.Name for o in doc.Objects]);oldnames=set(before)
    old_shapes={o.Name:o.Shape for o in doc.Objects if 'Shape' in o.PropertiesList}
    old_controls={w:vlist(doc.getObject('Wall'+w+'Profile').BaseControls) for w in WALLS}
    old_controls.update({w+'_top':vlist(doc.getObject('Wall'+w+'Profile').ComputedTop) for w in WALLS})
    oldviews={o.Name:o.ViewObject.Visibility for o in doc.Objects} if App.GuiUp else {}
    # Only the dependency closure, explicit assembly links and relevant groups may change.
    allowed=set(job['targets'])|{'RampBSources','RampBFootings','MSEAssembly','BridgeGeometryChecks'}
    for n in job['targets']:allowed.update(o.Name for o in doc.getObject(n).InListRecursive)
    protected=[n for n in before if n not in allowed]
    oldbridge=bridge_clashes(doc);oldmse=native_clashes(doc.MSEAssembly.FinishedConcrete)
    if oldmse:raise ValueError('Unexpected pre-existing MSE clashes; inspect before update')
    rec={'operation':job['operation'],'request':job,'document':doc.Name,'transaction_id':rid,'timestamp':datetime.now(timezone.utc).isoformat(),'status':'PREPARED','model_saved':False,'report_path':str(path),'checks':[],'errors':[],'rollback':'NOT NEEDED','old_controls_mm':old_controls,'baseline_bridge_clashes':oldbridge,'terrain_triangles':len(triangles),'warnings':['Existing bridge/MSE clashes remain FAIL.','Other walls and their reported terrain-cover deficiencies are unchanged.','Terrain is an existing-ground reference mesh, not a design surface.']}
    atomic(path,rec);doc.openTransaction(rid)
    try:
        for w in WALLS:
            o=doc.getObject('Wall'+w+'Profile');o.BaseControls=[App.Vector(p.x,p.y,z) for p in [o.BaseControls[0],o.BaseControls[-1]]]
        recompute_revision(doc)
        new={}
        for w in WALLS:
            raw=doc.getObject('Footing'+w);tool=doc.addObject('Part::Compound',raw.Name+'JointTools')
            tool.Links=[doc.getObject(n) for n in JOINTS[w]]
            final=doc.addObject('Part::Cut',raw.Name+'Finished');final.Base=raw;final.Tool=tool;final.Refine=True;final.Label=raw.Label
            doc.RampBFootings.removeObject(raw);doc.RampBSources.addObject(raw);doc.RampBSources.addObject(tool);doc.RampBFootings.addObject(final)
            new[raw.Name]=final;recompute_revision(doc)
            if App.GuiUp:
                final.ViewObject.ShapeColor=raw.ViewObject.ShapeColor;final.ViewObject.LineColor=raw.ViewObject.LineColor;final.ViewObject.DisplayMode='Flat Lines';final.ViewObject.Visibility=oldviews[raw.Name]
                raw.ViewObject.Visibility=False;tool.ViewObject.Visibility=False
        # Replace finished-component references, retaining nominal sources and all native cuts.
        for o in doc.Objects:
            for prop in ['FinishedConcrete','ExistingConcrete','ConcreteSources']:
                if prop in o.PropertiesList:
                    previous=getattr(o,prop)
                    if any(x.Name in new for x in previous):setattr(o,prop,[new.get(x.Name,x) for x in previous])
        doc.WallB8JointTools.Links=[new.get(x.Name,x) for x in doc.WallB8JointTools.Links]
        ref=make_terrain(doc,job,triangles,placement);recompute_revision(doc)
        if App.GuiUp:restore_visibility(doc,oldviews,{'Footing'+w for w in WALLS})
        checks,rows=geometry_audit(doc,terrain,z,tol,old_shapes,old_controls);rec['checks']+=checks;rec['footings']=rows
        actual=np.array([[list(p) for p in f.Points] for f in ref.Mesh.Facets])
        mesh_error=float(np.max(np.linalg.norm(actual-triangles*1000,axis=2))) if actual.shape==triangles.shape else float('inf')
        rec['checks'].append(result('terrain_original_facets_and_coordinates',actual.shape==triangles.shape and mesh_error<=tol,maximum_coordinate_error_mm=mesh_error,facets=ref.Mesh.CountFacets))
        after=bridge.source_state(doc,protected);diff=[n for n in protected if after[n]!=before[n]]
        rec['checks'].append(result('unrelated_geometry_links_expressions_and_annotations_exact',not diff,differences=diff))
        rec['checks'].append(result('no_pending_or_invalid_objects',not pending(doc),objects=pending(doc)))
        clashes=native_clashes(doc.MSEAssembly.FinishedConcrete);rec['mse_clashes']=clashes
        rec['checks'].append(result('MSE_finished_concrete_no_overlaps',not clashes,clashes=clashes))
        nowbridge=bridge_clashes(doc);rec['bridge_clashes']=nowbridge
        rec['checks'].append(result('bridge_clash_set_and_volumes_unchanged',oldbridge==nowbridge))
        doc.BridgeGeometryChecks.ClashPairs=[r['a']+' / '+r['b'] for r in nowbridge]
        doc.BridgeGeometryChecks.CoordinationStatus='FAIL' if nowbridge else doc.BridgeGeometryChecks.CoordinationStatus
        doc.BridgeGeometryChecks.purgeTouched()
        rec['checks'].append(result('existing_object_identity_preserved',oldnames.issubset(o.Name for o in doc.Objects)))
        rec['checks'].append(result('component_count_preserved',len(doc.MSEAssembly.FinishedConcrete)==46))
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Footing/terrain validation failed')
        if job.get('test_failure'):raise ValueError('Deliberate disposable rollback test')
        rec['checks'].append({'name':'existing_bridge_MSE_coordination','status':'FAIL' if nowbridge else 'PASS','clash_count':len(nowbridge),'scope':'Pre-existing and unchanged; no structural approval'})
        rec['status']='VALIDATED';atomic(path,rec);doc.commitTransaction();rec['status']='UPDATED — EXISTING COORDINATION FAIL' if nowbridge else 'PASS';rec['geometry_status']='PASS'
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc();doc.abortTransaction()
        # Restore original wrappers, avoiding BRep copy/location normalization.
        for n,s in old_shapes.items():
            o=doc.getObject(n)
            if o.Shape.exportBrepToString()!=s.exportBrepToString():o.Shape=s
        if App.GuiUp:restore_visibility(doc,oldviews)
        for o in doc.Objects:o.purgeTouched()
        exact=bridge.source_state(doc,list(before))==before
        controls=all(vlist(doc.getObject('Wall'+w+'Profile').BaseControls)==old_controls[w] and vlist(doc.getObject('Wall'+w+'Profile').ComputedTop)==old_controls[w+'_top'] for w in WALLS)
        rec['rollback']='VERIFIED' if exact and controls and set(o.Name for o in doc.Objects)==oldnames and not pending(doc) else 'FAILED'
        rec['rollback_differences']=[n for n,v in bridge.source_state(doc,list(before)).items() if v!=before[n]]
        rec['rollback_detail']={n:{k:[before[n][k],v[k]] for k in v if before[n][k]!=v[k]} for n,v in bridge.source_state(doc,list(before)).items() if v!=before[n]}
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','timestamp','document','status','model_saved','rollback','report_path']})+'\n')
    out=compact(rec)
    for k in ['old_controls_mm','baseline_bridge_clashes','bridge_clashes']:out.pop(k,None)
    return out
