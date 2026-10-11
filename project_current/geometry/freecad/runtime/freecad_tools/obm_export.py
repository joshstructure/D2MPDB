"""Repeatable B4 OBM handoff: survey-foot solids, exact 3D PGLs, annotations."""
import csv,hashlib,json,math,re,traceback,uuid,zipfile
from datetime import datetime,timezone
from pathlib import Path
import FreeCAD as App
import Part
from . import bridge,drainage_trial as dt,step_export as se
from .beam_dxf import library
from .geometry import length,result
ROOT=bridge.ROOT;UNIT=se.MM_PER_UNIT['us-ft']
PGLS=['BridgePGL','RampAPGL','RampBPGL']

def xyz(p):return (p.x/UNIT,p.y/UNIT,p.z/UNIT)

def walking_faces(shape):
    out=[]
    for face in shape.Faces:
        u0,u1,v0,v1=face.ParameterRange
        if face.normalAt((u0+u1)/2,(v0+v1)/2).z>.5:out.append(face)
    if not out:raise ValueError('Imported slab has no upward walking face')
    return out

def references(doc,path,tolerance):
    """Export native B-spline control geometry, then independently read it back."""
    ezdxf=library();dx=ezdxf.new('R2013');dx.units=21
    dx.header['$LUNITS']=2;dx.header['$LUPREC']=8;dx.header['$INSBASE']=(0.,0.,0.)
    dx.header['$MEASUREMENT']=0;dx.header['$PDMODE']=34;dx.header['$PDSIZE']=.08
    dx.appids.new('CAD_AI');space=dx.modelspace();expected={};checks=[]
    layers={'BridgePGL':'B4_PGL_BRIDGE','RampAPGL':'B4_PGL_RAMP_A','RampBPGL':'B4_PGL_RAMP_B'}
    for name,layer in layers.items():
        dx.layers.new(layer,dxfattribs={'color':1})
        for i,edge in enumerate(doc.getObject(name).Shape.Edges):
            nurbs=edge.toNurbs().Edges[0];curve=nurbs.Curve;curve.segment(nurbs.FirstParameter,nurbs.LastParameter)
            poles=[xyz(p) for p in curve.getPoles()]
            if isinstance(curve,Part.BezierCurve):knots=[0.]*(curve.Degree+1)+[1.]*(curve.Degree+1)
            elif isinstance(curve,Part.BSplineCurve):knots=[k for k,m in zip(curve.getKnots(),curve.getMultiplicities()) for _ in range(m)]
            else:raise ValueError('Unsupported PGL curve '+type(curve).__name__)
            e=space.add_rational_spline(poles,curve.getWeights(),curve.Degree,knots,dxfattribs={'layer':layer})
            e.set_xdata('CAD_AI',[(1000,name),(1070,i)])
            expected[(name,i)]=edge
    for layer in ['B4_ELEVATION_TEXT','B4_ELEVATION_LEADERS','B4_ELEVATION_POINTS']:dx.layers.new(layer,dxfattribs={'color':2})
    annotations=[o for o in doc.SlabElevations.Group if 'PointDefinitions' in o.PropertiesList]
    for o in annotations:
        if abs(o.Placement.Rotation.Angle)>1e-12:raise ValueError('Unsupported rotated elevation text '+o.Name)
        p=o.MeasuredPoint;q=o.Placement.Base
        e=space.add_mtext('\\P'.join(o.Text),dxfattribs={'layer':'B4_ELEVATION_TEXT','insert':xyz(q),'char_height':o.ViewObject.FontSize/UNIT,'attachment_point':1})
        e.set_xdata('CAD_AI',[(1000,o.Name),(1000,o.PointID)])
        e=space.add_line(xyz(p),xyz(q),dxfattribs={'layer':'B4_ELEVATION_LEADERS'});e.set_xdata('CAD_AI',[(1000,o.Name)])
        e=space.add_point(xyz(p),dxfattribs={'layer':'B4_ELEVATION_POINTS'});e.set_xdata('CAD_AI',[(1000,o.Name)])
    dx.saveas(path);back=ezdxf.readfile(path);audit=back.audit();ms=back.modelspace()
    checks.append(result('DXF_audit',not audit.has_errors,errors=len(audit.errors)))
    checks.append(result('DXF_US_survey_feet',back.units==21 and back.header['$LUNITS']==2 and tuple(back.header['$INSBASE'])==(0.,0.,0.)))
    seen=set();curve_errors=[]
    for e in ms.query('SPLINE'):
        tags=e.get_xdata('CAD_AI');key=(tags[0].value,tags[1].value);seen.add(key)
        native=expected[key];spline=e.construction_tool();knots=list(e.knots);errors=[]
        for j in range(33):
            f=j/32;p=spline.point(knots[0]+f*(knots[-1]-knots[0]));q=native.valueAt(native.FirstParameter+f*(native.LastParameter-native.FirstParameter))
            errors.append(App.Vector(p.x*UNIT,p.y*UNIT,p.z*UNIT).distanceToPoint(q))
        curve_errors.append(max(errors));checks.append(result(key[0]+f'_DXF_edge_{key[1]+1}',max(errors)<=tolerance,max_error_in=max(errors)/25.4))
    checks.append(result('all_PGL_edges_present',seen==set(expected)))
    textmap={e.get_xdata('CAD_AI')[0].value:e for e in ms.query('MTEXT')}
    leadmap={e.get_xdata('CAD_AI')[0].value:e for e in ms.query('LINE')}
    points={e.get_xdata('CAD_AI')[0].value:e for e in ms.query('POINT')}
    checks.append(result('all_elevation_annotations_present',len(textmap)==len(annotations)==len(leadmap)==len(points)))
    for o in annotations:
        t=textmap[o.Name];p=points[o.Name];lead=leadmap[o.Name]
        error=max(App.Vector(*(v*UNIT for v in p.dxf.location)).distanceToPoint(o.MeasuredPoint),App.Vector(*(v*UNIT for v in t.dxf.insert)).distanceToPoint(o.Placement.Base),App.Vector(*(v*UNIT for v in lead.dxf.start)).distanceToPoint(o.MeasuredPoint),App.Vector(*(v*UNIT for v in lead.dxf.end)).distanceToPoint(o.Placement.Base))
        checks.append(result(o.Name+'_DXF_annotation',t.text=='\\P'.join(o.Text) and error<=tolerance,max_coordinate_error_in=error/25.4))
    schedule=path.parent/'B4_Elevation_Points_US_Survey_Feet.csv'
    with schedule.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(['Point ID','X US survey ft','Y US survey ft','Z US survey ft','Original model elevation ft','Approved displayed elevation'])
        for o in annotations:writer.writerow([o.PointID,*xyz(o.MeasuredPoint),o.MeasuredPoint.z/304.8,o.Text[-1]])
    return {'checks':checks,'pgl_edges':len(expected),'annotations':len(annotations),'max_PGL_error_in':max(curve_errors)/25.4,'schedule':str(schedule)}

def export(job):
    from .api import document,check_gui,atomic,compact
    doc=document(job['document']);check_gui(doc);tol=length(job.get('tolerance','0.001 in'),True)
    if job.get('units','us-ft')!='us-ft':raise ValueError('This B4 handoff requires US survey feet')
    for name in ['MSEAssembly','BridgeGeometryChecks','SlabElevations','CompletePGLTrace','DrainageTrial']+PGLS:
        if doc.getObject(name) is None:raise ValueError('Required B4 object missing: '+name)
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Resolve pending model objects before export')
    rid=job.get('request_id','obm-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    if not re.fullmatch('[A-Za-z0-9_-]{8,75}',rid):raise ValueError('Invalid request ID')
    report=ROOT/'reports/transactions'/(rid+'.json')
    if report.exists():
        old=json.loads(report.read_text(encoding='utf-8'))
        if old['request']!=job:raise ValueError('Request ID reused')
        if old['status']=='PREPARED':raise ValueError('Inspect unfinished export before retrying')
        return compact(old)
    dest=(ROOT/job.get('output_directory','exports/B4-OBM-'+rid)).resolve()
    if not dest.is_relative_to(ROOT) or dest.exists():raise ValueError('Use a new project output directory')
    before=se.state(doc);oldactive=App.ActiveDocument.Name if App.ActiveDocument else None
    objects=list(doc.MSEAssembly.FinishedConcrete)+[o for o in doc.BridgeGeometryChecks.Components if o.ComponentKind!='WallEnvelope']
    if len({o.Name for o in objects})!=len(objects):raise ValueError('Duplicate export targets')
    rec={'operation':'export_obm_package','request':job,'transaction_id':rid,'timestamp':datetime.now(timezone.utc).isoformat(),'document':doc.Name,'status':'PREPARED','model_saved':False,'report_path':str(report),'checks':[],'errors':[],'package_directory':str(dest)}
    atomic(report,rec)
    try:
        stepjob={'operation':'export_step','document':doc.Name,'request_id':rid+'-step','writer':'native_units','units':'us-ft','tolerance':job.get('tolerance','0.001 in'),'output_directory':str(dest.relative_to(ROOT)),'files':[{'filename':'B4_Main_Solids_US_Survey_Feet.stp','targets':[o.Name for o in objects],'footing_thicknesses':{o.Name:'6 in' for o in objects if o.Name.startswith('Footing')}}]}
        sr=se.export(stepjob)
        step_record=json.loads((ROOT/'reports/transactions'/(rid+'-step.json')).read_text(encoding='utf-8'))
        rec['checks'].extend(step_record['checks']);rec['step_transaction']=sr['transaction_id']
        if sr['status']!='PASS':raise ValueError('Solid export failed; see '+sr['report_path'])
        step=dest/'B4_Main_Solids_US_Survey_Feet.stp';loaded=Part.read(str(step))
        mapping={}
        for row in step_record['files'][0]['mapping']:mapping.setdefault(row['object'],[]).append(loaded.Solids[row['STEP_solid_index']])
        product_names=set(re.findall(r"PRODUCT\(\s*'([^']+)'",step.read_text(encoding='utf-8')))
        rec['checks'].append(result('STEP_all_components_named',all(o.Name in product_names for o in objects)))
        # Independently measure imported slab tops along every actual ramp PGL,
        # including curved landing legs and the revised upper-run grades.
        parts=doc.CompletePGLTrace.Shape.childShapes();edges=list(parts[0].Edges)+list(parts[2].Edges);errors=[]
        for i,(edge,name) in enumerate(zip(edges,doc.CompletePGLTrace.SegmentSlabs)):
            shape=Part.makeCompound(mapping[name]);faces=walking_faces(shape);differences=[]
            for j in range(21):
                p=edge.valueAt(edge.FirstParameter+(edge.LastParameter-edge.FirstParameter)*j/20)
                # Direct distance to the physical upward face avoids OCCT's
                # spurious vertical-ray intersection at an internal spline knot.
                differences.append(min(Part.Vertex(p).distToShape(face)[0] for face in faces))
            errors.extend(differences);rec['checks'].append(result('STEP_ramp_PGL_top_'+str(i+1),max(differences)<=tol,max_error_in=max(differences)/25.4))
        rec['checks'].append(result('STEP_all_ramp_PGL_segments_checked',len(edges)==len(doc.CompletePGLTrace.SegmentSlabs)))
        for name in dt.MODIFIED:
            surf=doc.getObject(name+'Surface');native=dt.slab_map(doc)[name+'Slab'];shape=Part.makeCompound(mapping[native.Name]);face=surf.Shape.Faces[0];u0,u1,v0,v1=face.ParameterRange;diff=[]
            for u in [.1,.3,.5,.7,.9]:
                for v in [.1,.3,.5,.7,.9]:
                    p=face.valueAt(u0+u*(u1-u0),v0+v*(v1-v0));diff.append(abs(dt.top_at(shape,p.x,p.y)-dt.top_at(native.Shape.copy(),p.x,p.y)))
            rec['checks'].append(result(native.Name+'_STEP_curved_top_grid',max(diff)<=tol,max_error_in=max(diff)/25.4))
        ref=references(doc,dest/'B4_PGLs_and_Elevations_US_Survey_Feet.dxf',tol);rec['checks'].extend(ref.pop('checks'));rec.update(ref)
        components=[{'name':o.Name,'label':o.Label,'solids':len(o.Shape.Solids),'bounds_us_survey_ft':[x/UNIT for x in se.box(o.Shape)],'source_color':list(o.ViewObject.ShapeColor[:3])} for o in objects]
        rec.update(components=len(objects),solids=len(loaded.Solids),max_STEP_PGL_top_error_in=max(errors)/25.4,units='US survey feet',coordinate_frame='Current local FreeCAD model frame; no project survey translation or rotation applied.',coordination='Existing 12 bridge/MSE overlaps remain; export does not resolve them.',warnings=['Imported components are ordinary CAD solids. Native OBM bridge parametrics are not exported.','Component names are preserved. Source colors are recorded in the manifest; solid color styling is not carried by this writer.','Schematic fill, duplicate construction shapes and hidden wall envelope are excluded.'])
        rec['checks'].append(result('entire_source_model_preserved',se.state(doc)==before))
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('OBM package validation failed')
        guide='''B4 — BENTLEY OBM HANDOFF\n\n1. Open the intended 3D DGN model. Its Master Unit must be US Survey Feet, as confirmed for this project.\n2. Use File > Import and choose STEP AP203/AP214 (.stp). Select B4_Main_Solids_US_Survey_Feet.stp. Import at 1:1 using the declared file units. No additional 12x, 25.4x or 304.8x scale is required.\n3. Open/reference B4_PGLs_and_Elevations_US_Survey_Feet.dxf using Design Center units, or explicitly US Survey Feet. Keep the same origin, rotation and 1:1 scale as the solids. Layers separate bridge PGL, both ramp PGLs, elevation text, leaders and points.\n4. Check one 6-inch MSE footing: its thickness must measure 0.499999 US survey feet. An 18-inch square end-bent pile must measure 1.499997 US survey feet across each side.\n5. Save the receiving DGN after checking placement and dimensions.\n\nBoth exports retain the current LOCAL model coordinates. No project survey translation or rotation was applied. Apply any required project placement equally to both files. STEP preserves named ordinary CAD solid components; colors are listed in the manifest. It does not create native OBM bridge definitions. Approved annotation text is retained; the CSV supplies exact physical coordinates in US survey feet.\n\nThe package includes 84 elevation callouts and exact spline PGLs, not the screen's coarse line segments. Existing 12 bridge/MSE overlaps remain. Source FreeCAD geometry was unchanged and its file was not saved by export. Bentley import has not been run here.\n\nBentley import reference (related CONNECT platform): https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0098809\nBentley DWG/DXF unit options: https://bentleysystems.service-now.com/community?id=kb_article&sysparm_article=KB0108217\n'''
        (dest/'OBM_Import_Instructions.txt').write_text(guide,encoding='utf-8')
        files=[step,dest/'B4_PGLs_and_Elevations_US_Survey_Feet.dxf',Path(ref['schedule']),dest/'OBM_Import_Instructions.txt']
        rec['files']=[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
        manifest={'transaction_id':rid,'units':'us-ft','mm_per_unit':UNIT,'coordinate_frame':rec['coordinate_frame'],'components':components,'files':rec['files'],'known_coordination':rec['coordination'],'warnings':rec['warnings']}
        atomic(dest/'manifest.json',manifest);files.append(dest/'manifest.json')
        rec['status']='PASS';atomic(report,rec);atomic(dest/'Verification.json',rec);files.append(dest/'Verification.json')
        archive=dest.with_suffix('.zip')
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
            for p in files:z.write(p,p.name)
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:raise ValueError('Package ZIP verification failed')
        rec['zip_path']=str(archive)
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc();rec['source_preserved_after_error']=se.state(doc)==before
    finally:
        if oldactive and oldactive in App.listDocuments():App.setActiveDocument(oldactive)
    atomic(report,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','timestamp','document','status','model_saved','report_path']})+'\n')
    out=compact(rec);return out
