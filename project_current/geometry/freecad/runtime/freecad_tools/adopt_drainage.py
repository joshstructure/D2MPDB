"""Refresh references and per-slab corner callouts; designate the main model."""
import json,re,traceback
from datetime import datetime,timezone
import FreeCAD as App
import FreeCADGui as Gui
from . import drainage_trial as dt,bridge,mse
from .geometry import length,result
ROOT=bridge.ROOT;FT=bridge.FT;IN=bridge.IN

class RampPGLProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        o.Shape=o.Reference.Shape.childShapes()[0 if o.Side=='A' else 2].copy()
        o.MeasuredLength=o.Shape.Length
        o.Label='Ramp '+o.Side+' PGL — adopted slab tops'

def annotations(doc):return [o for o in doc.SlabElevations.Group if 'PointDefinitions' in o.PropertiesList]

def make_corner(doc,spec,index):
    o=doc.addObject('App::FeaturePython',f'RampCornerElevation{index:03d}')
    dt.ElevationProxy(o);dt.ViewProviderText(o.ViewObject)
    mse.prop(o,'App::PropertyLinkList','Sources',[doc.getObject(spec['source']),doc.DrainageTrial],'Sources')
    mse.prop(o,'App::PropertyString','PointDefinitions',json.dumps([spec]),'Sources')
    mse.prop(o,'App::PropertyString','PointID',spec['id'],'Annotation')
    mse.prop(o,'App::PropertyVector','MeasuredPoint',dt.point_from_spec(doc,spec),'Measured geometry')
    mse.prop(o,'App::PropertyLength','Elevation','0 ft','Measured geometry')
    mse.prop(o,'App::PropertyVector','TextOffset',App.Vector(),'Annotation')
    o.setEditorMode('MeasuredPoint',1);o.setEditorMode('Elevation',1)
    o.Label=spec['id']+' | '+spec['source'];o.ViewObject.DisplayMode='World'
    doc.SlabElevations.addObject(o);o.Proxy.execute(o)
    leader=doc.addObject('Part::FeaturePython',f'RampCornerLeader{index:03d}')
    mse.prop(leader,'App::PropertyLink','Annotation',o,'Source');dt.LeaderProxy(leader);bridge.initialize_display(leader)
    leader.ViewObject.LineWidth=1.;leader.ViewObject.PointSize=5.;doc.SlabElevations.addObject(leader)
    return o

def layout(doc):
    occupied=[];font=length('6 in');rows=[]
    backgrounds=[o.Shape.BoundBox for raw,o in dt.slab_map(doc).items() if raw.endswith('Slab')]+[doc.BridgeDeckS1.Shape.BoundBox,doc.BridgeDeckS2.Shape.BoundBox]
    objects=sorted(annotations(doc),key=lambda o:0 if any(s['kind']=='corner' for s in json.loads(o.PointDefinitions)) else 1)
    for o in objects:
        specs=json.loads(o.PointDefinitions);p=o.MeasuredPoint
        width=max(len(o.PointID),len(f'EL {p.z/FT:.3f} ft'))*font*.78;height=font*3.
        corner=next((s for s in specs if s['kind']=='corner'),None)
        if corner:
            bb=doc.getObject(corner['source']).Shape.BoundBox
            dx=1 if bb.Center.x>p.x else -1;dy=1 if bb.Center.y>p.y else -1
            dirs=[(dx,dy),(dx,-dy),(-dx,dy),(-dx,-dy)]
        else:dirs=[(1,1),(-1,1),(1,-1),(-1,-1)]
        chosen=None
        for radius in [1.5,3,5,8,12,18,25,35,50,70]:
            for dx,dy in dirs:
                x=p.x+dx*radius*FT-(width if dx<0 else 0);y=p.y+dy*radius*FT
                box=(x,y-height,x+width,y+font)
                if not any(box[0]<b[2] and box[2]>b[0] and box[1]<b[3] and box[3]>b[1] for b in occupied):chosen=(x,y,box);break
            if chosen:break
        if not chosen:raise ValueError('No clear annotation position: '+o.Name)
        x,y,box=chosen;occupied.append(box);o.TextOffset=App.Vector(x-p.x,y-p.y,length('12 in'))
        cx,cy=x+width/2,y-height/2
        on_slab=any(b.XMin<=cx<=b.XMax and b.YMin<=cy<=b.YMax for b in backgrounds)
        o.ViewObject.FontSize=font;o.ViewObject.TextColor=(.06,.07,.10) if on_slab else (.98,.88,.55);o.ViewObject.Visibility=True;o.Proxy.execute(o)
        rows.append({'name':o.Name,'box_mm':list(box),'leader_plan_length_ft':(App.Vector(x,y,0)-App.Vector(p.x,p.y,0)).Length/FT})
    for o in doc.SlabElevations.Group:
        if 'Annotation' in o.PropertiesList:
            o.ViewObject.LineColor=(.95,.73,.15);o.ViewObject.PointColor=(.95,.73,.15);o.ViewObject.Visibility=True
    return rows

def update(doc,job):
    trace=doc.CompletePGLTrace
    # Live documents can retain a pre-reload Python class, unlike reopened
    # disposable copies. Bind the tested updater explicitly before recompute.
    dt.TraceProxy(trace)
    if 'AlignBridgeEndpoints' not in trace.PropertiesList:mse.prop(trace,'App::PropertyBool','AlignBridgeEndpoints',True,'Sources')
    else:trace.AlignBridgeEndpoints=True
    trace.touch();doc.recompute([trace]);new=[]
    for o in list(annotations(doc)):
        specs=json.loads(o.PointDefinitions)
        if len(specs)>1 and all(s['kind']=='corner' for s in specs):
            first=specs[0];o.PointDefinitions=json.dumps([first]);o.PointID=first['id'];o.Label=first['id']+' | '+first['source']
            o.Sources=[doc.getObject(first['source']),doc.DrainageTrial]
            for spec in specs[1:]:new.append(make_corner(doc,spec,len(new)+1).Name)
    for rawname,slab in dt.slab_map(doc).items():
        if not rawname.endswith('Slab'):continue
        raw=doc.getObject(rawname)
        for i,p in enumerate(raw.Base.ComputedCorners):
            found=any(any(s.get('kind')=='corner' and s.get('source')==slab.Name and s.get('index')==i for s in json.loads(o.PointDefinitions)) for o in annotations(doc))
            if not found:
                spec={'kind':'corner','source':slab.Name,'surface':raw.Base.Name,'index':i,'id':slab.Name+f'-C{i+1}'}
                new.append(make_corner(doc,spec,len(new)+1).Name)
    doc.recompute();positions=layout(doc)
    pglgroup=doc.addObject('App::DocumentObjectGroup','RampPGLs');pglgroup.Label='Ramp PGLs — adopted configuration'
    for side in ['A','B']:
        o=doc.addObject('Part::FeaturePython','Ramp'+side+'PGL');RampPGLProxy(o)
        mse.prop(o,'App::PropertyLink','Reference',trace,'Sources');mse.prop(o,'App::PropertyString','Side',side,'Sources')
        mse.prop(o,'App::PropertyLength','MeasuredLength','0 ft','Measured geometry');o.setEditorMode('MeasuredLength',1)
        bridge.initialize_display(o);o.ViewObject.LineWidth=5.;o.ViewObject.LineColor=(1.,.12,.12);pglgroup.addObject(o)
    doc.BridgeAssembly.addObject(pglgroup);trace.ViewObject.Visibility=False
    designation=doc.addObject('App::FeaturePython','ModelDesignation');designation.Label='MAIN MODEL — drainage configuration adopted'
    mse.prop(designation,'App::PropertyString','Role','MAIN','Adoption')
    mse.prop(designation,'App::PropertyString','AdoptionTransaction',job['request_id'],'Adoption')
    mse.prop(designation,'App::PropertyString','PreviousDocument',job['rollback_document'],'Rollback')
    mse.prop(designation,'App::PropertyLinkList','Sources',[doc.DrainageTrial,doc.RampAPGL,doc.RampBPGL],'Adoption')
    mse.prop(designation,'App::PropertyString','KnownCoordinationIssues','12 positive bridge/MSE overlap pairs remain; adoption does not resolve them.','Checks')
    doc.DrainageTrial.Label='Adopted drainage controls — lower ends held'
    for name in dt.MODIFIED:
        o=dt.slab_map(doc)[name+'Slab'];o.Label=o.Label.replace('TRIAL ','')
    trace.Label='Complete PGL source — bridge and adopted ramps';doc.MSESlopeChecks.Label='Adopted slab slopes — curved surface audit required'
    doc.Label='B4 Pedestrian Bridge and Ramps — MAIN';doc.recompute();doc.recompute()
    return {'new_corner_annotations':new,'layout':positions}

def validate(doc,toltext):
    tol=length(toltext,True);checks=[];rows=[];ann=annotations(doc);total=0
    for rawname,slab in dt.slab_map(doc).items():
        if not rawname.endswith('Slab'):continue
        shape=slab.Shape.copy();corners=[]
        for v in shape.Vertexes:
            p=v.Point
            if abs(p.z-dt.top_at(shape,p.x,p.y))<=tol and not any(p.distanceToPoint(q)<tol for q in corners):corners.append(p)
        own=[o for o in ann if any(s.get('kind')=='corner' and s['source']==slab.Name for s in json.loads(o.PointDefinitions))]
        maxdist=max(min(p.distanceToPoint(o.MeasuredPoint) for o in own) for p in corners)
        checks.append(result(slab.Name+'_every_physical_corner_has_own_callout',len(own)==len(corners)==4 and maxdist<=tol,physical_corners=len(corners),own_labels=len(own),max_error_in=maxdist/IN));total+=len(corners)
    checks.append(result('all_48_ramp_corners_individually_annotated',total==48))
    aq=dt.validate_annotations(doc);checks.extend(aq['checks'])
    ends=sorted([v.Point for v in doc.BridgePGL.Shape.Vertexes],key=lambda p:doc.BridgePGL.Frame.inverse().multVec(p).x)
    for side in ['A','B']:
        o=doc.getObject('Ramp'+side+'PGL');target=ends[0 if side=='A' else -1];gap=min(v.Point.distanceToPoint(target) for v in o.Shape.Vertexes)
        checks.append(result(side+'_PGL_exact_bridge_endpoint',gap<=1e-6,gap_in=gap/IN))
        checks.append(result(side+'_PGL_one_valid_open_wire',o.Shape.isValid() and len(o.Shape.Wires)==1 and not o.Shape.isClosed() and len(o.Shape.Solids)==0))
        checks.append(result(side+'_PGL_visible',o.ViewObject.Visibility and not bridge.display_state(o)['render_bounds_empty']))
        rows.append({'side':side,'length_ft':o.Shape.Length/FT,'edges':len(o.Shape.Edges),'bridge_endpoint_gap_in':gap/IN})
    checks.append(result('no_pending_objects',not [o.Name for o in doc.Objects if 'Touched' in o.State or 'Invalid' in o.State]))
    return {'checks':checks,'pgls':rows,'annotation_count':len(ann),'annotations':aq['annotations']}

def adopt(job):
    from .api import document,check_gui,atomic,compact
    doc=document(job['document']);previous=document(job['rollback_document']);check_gui(doc)
    rid=job['request_id'];path=ROOT/'reports/transactions'/(rid+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['request']!=job:raise ValueError('Request ID reused')
        if old['status'] in ['PREPARED','VALIDATED']:raise ValueError('Inspect prior unknown outcome')
        return compact(old)
    length(job['tolerance'],True)
    if doc.getObject('ModelDesignation'):raise ValueError('Document already adopted')
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Pending objects must be resolved first')
    before=bridge.source_state(doc,[o.Name for o in doc.Objects]);previous_state=bridge.source_state(previous,[o.Name for o in previous.Objects])
    label=doc.Label;oldlabel=previous.Label
    physical=[o.Name for o in doc.MSEAssembly.FinishedConcrete]+[o.Name for o in doc.BridgeGeometryChecks.Components]+['BridgePGL']
    rec={'request':job,'operation':'adopt_drainage','transaction_id':rid,'timestamp':datetime.now(timezone.utc).isoformat(),'document':doc.Name,'status':'PREPARED','report_path':str(path),'model_saved':False,'checks':[],'errors':[],'rollback':'NOT NEEDED'}
    atomic(path,rec);doc.openTransaction(rid)
    try:
        rec.update(update(doc,job));rec.update(validate(doc,job['tolerance']))
        full=dt.validate(doc,job['tolerance']);rec['checks'].extend(full.pop('checks'));rec.update(full)
        after=bridge.source_state(doc,physical)
        changed=[n for n in physical if any(before[n][k]!=after[n][k] for k in ['shape','placement','expressions','dependencies'])]
        rec['checks'].append(result('all_existing_physical_geometry_exactly_preserved',not changed,changed=changed))
        rec['checks'].append(result('previous_configuration_exactly_preserved',bridge.source_state(previous,list(previous_state))==previous_state))
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Adoption check failed')
        rec['status']='VALIDATED';atomic(path,rec);doc.commitTransaction()
        if job.get('promote_previous_label',True):previous.Label='B4 previous configuration — rollback'
        rec['status']='ADOPTED MAIN — EXISTING COORDINATION FAIL';rec['previous_label']=oldlabel
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc();doc.abortTransaction();doc.Label=label;previous.Label=oldlabel;doc.recompute()
        rec['rollback']='VERIFIED' if bridge.source_state(doc,list(before))==before and bridge.source_state(previous,list(previous_state))==previous_state else 'FAILED'
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','timestamp','document','status','model_saved','rollback']})+'\n')
    out=compact(rec)
    for key in ['layout','annotations','clashes','MSE_clashes']:out.pop(key,None)
    return out
