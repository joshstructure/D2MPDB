"""14 October user corrections: inward panel recess, rear lugs, level returns."""
import json
import FreeCAD as App,Part
from . import mse_revision as rev,drainage_trial as dt,bridge,mse
IN=25.4;FT=304.8
CORNER_PAIRS=[('A1','A8'),('A4','A8'),('A4','A7'),('A2','A6'),('A5','A6'),('A5','A7'),('B1','B6'),('B1','B7'),('B2','B7'),('B2','B9'),('B5','B6'),('B5','B8')]

class MitreWallProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        o.Shape=rev.mitre_clip(o.Base.Shape.copy(),o.Profile)
        if o.Shape.isNull() or not o.Shape.isValid() or o.Shape.Volume<=0:raise ValueError('Invalid mitred wall '+o.Name)

def configure_mitres(doc):
    profiles=[o for o in doc.Objects if o.Name.startswith('Wall') and o.Name.endswith('Profile')]
    for w in profiles:
        key=w.Name[4:-7];others=[doc.getObject('Wall'+(b if a==key else a)+'Profile') for a,b in CORNER_PAIRS if key in [a,b]]
        rev.setprop(w,'App::PropertyStringList','CornerProfileNames',[o.Name for o in others])
    for w in profiles:
        lo=0;hi=w.TopControls[-1].x
        for other in rev.corner_profiles(w):
            point=rev.corner_point(w,other)+(w.Normal+other.Normal)*doc.MSEInputs.WallThickness.Value
            parameter=(point-w.Start).dot(w.Tangent);lo=min(lo,parameter);hi=max(hi,parameter)
        before=max(0,-lo);after=max(0,hi-w.TopControls[-1].x)
        extend_wall(w,before if before>1e-6 else 0,after if after>1e-6 else 0)

def finish_mitred_walls(doc):
    oldwalls=[o for o in doc.MSEAssembly.FinishedConcrete if o.Name.startswith('Wall')]
    nominal={};finished=[];replacements={}
    for raw in [o for o in doc.MSEAssembly.NominalConcrete if o.Name.startswith('Wall')]:
        feature=doc.addObject('Part::FeaturePython',raw.Name+'MitredSource');rev.setprop(feature,'App::PropertyLink','Base',raw);rev.setprop(feature,'App::PropertyLink','Profile',doc.getObject(raw.Name+'Profile'))
        rev.setprop(feature,'App::PropertyLinkList','CornerSources',rev.corner_profiles(feature.Profile))
        MitreWallProxy(feature);feature.Proxy.execute(feature);doc.MSEInterfaceSources.addObject(feature);nominal[raw.Name]=feature
    # Continuous side walls own the low-level T connections; the 45-degree
    # endpoint pairs above already partition their corner material exactly.
    order=sorted(nominal,key=lambda n:(0 if n in ['WallA6','WallB6','WallB9'] else 1,n))
    for name in order:
        base=nominal[name];tools=[doc.MSEEndBentJointEnvelope]
        for old in finished:
            if base.Shape.BoundBox.intersect(old.Shape.BoundBox) and base.Shape.common(old.Shape).Volume>1e-7:tools.append(old)
        final=doc.addObject('Part::FeaturePython',name+'Mitred');rev.setprop(final,'App::PropertyLink','Base',base);rev.setprop(final,'App::PropertyLinkList','ContactSources',tools);PartitionProxy(final);final.Proxy.execute(final)
        final.Label='MSE '+name[4:]+' - 45 degree mitred corners';doc.MSEInterfaceSources.addObject(final);finished.append(final)
        for old in oldwalls:
            if old.Name==name or old.Name.startswith(name+'Finished') or old.Name==name+'BentJoint':replacements[old.Name]=final
    doc.MSEAssembly.FinishedConcrete=[replacements.get(o.Name,o) for o in doc.MSEAssembly.FinishedConcrete]
    doc.BridgeGeometryChecks.ExistingConcrete=list(doc.MSEAssembly.FinishedConcrete)
    for o in doc.Objects:
        if 'ConcreteSources' in o.PropertiesList:o.ConcreteSources=[replacements.get(p.Name,p) for p in o.ConcreteSources]
    return [o.Name for o in finished]

class PartitionProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        shape=o.Base.Shape.copy()
        for tool in o.ContactSources:
            if shape.BoundBox.intersect(tool.Shape.BoundBox):
                shape=shape.cut(tool.Shape.copy(),0.0)
                if getattr(o,'RefineResult',True):shape=shape.removeSplitter()
        if shape.isNull() or not shape.isValid() or shape.Volume<=0:raise ValueError('Invalid corrected contact '+o.Name)
        o.Shape=shape

def extend_wall(w,before=0,after=0):
    """Extend a straight native profile, preserving all interior control points."""
    if before:
        w.Start=w.Start-w.Tangent*before
        for key in ['TopControls','BaseControls']:
            pts=[App.Vector(p.x+before,p.y,p.z) for p in getattr(w,key)]
            pts.insert(0,App.Vector(0,0,pts[0].z));setattr(w,key,pts)
        w.TopSourceNames=[w.TopSourceNames[0]]+list(w.TopSourceNames)
        w.TopSamplePoints=[w.TopSamplePoints[0]]+list(w.TopSamplePoints)
    if after:
        for key in ['TopControls','BaseControls']:
            pts=list(getattr(w,key));pts.append(App.Vector(pts[-1].x+after,0,pts[-1].z));setattr(w,key,pts)
        w.TopSourceNames=list(w.TopSourceNames)+[w.TopSourceNames[-1]]
        w.TopSamplePoints=list(w.TopSamplePoints)+[w.TopSamplePoints[-1]]
    w.Proxy.execute(w)

def update_layout(doc,log):
    trial=doc.DrainageTrial;old={s:dt.settings(trial,s) for s in 'AB'};params=json.loads(trial.BaselineParameters)
    for side in 'AB':params[side]['xmin']+=6*IN;params[side]['join']-=6*IN
    trial.BaselineParameters=json.dumps(params);trial.BRunBlendLength=params['B']['end']-params['B']['join']-.1*FT
    def mapped(p,side):
        p=App.Vector(p)
        for key in ['xmin','join']:
            if abs(p.x-old[side][key])<.1:p.x=params[side][key];break
        return p
    for o in doc.Objects:
        if o.Name.startswith(('A_','B_')) and o.Name.endswith('Surface'):
            for key in ['XMin','XMax']:
                if key in o.PropertiesList:
                    for bound in ['xmin','join']:
                        if abs(getattr(o,key).Value-old[o.Name[0]][bound])<.1:setattr(o,key,params[o.Name[0]][bound]);break
            if getattr(o,'Proxy',None):o.Proxy.execute(o)
    for w in [o for o in doc.Objects if o.Name.startswith('Wall') and o.Name.endswith('Profile')]:
        side=w.Name[4];start=App.Vector(w.Start);newstart=mapped(start,side)
        for key in ['TopControls','BaseControls']:
            pts=[]
            for p in getattr(w,key):
                world=start+w.Tangent*p.x;target=mapped(world,side);q=App.Vector(p);q.x=(target-newstart).dot(w.Tangent);pts.append(q)
            setattr(w,key,pts)
        w.Start=newstart;w.TopSamplePoints=[mapped(p,side) if n else p for p,n in zip(w.TopSamplePoints,w.TopSourceNames)];w.Proxy.execute(w)
    configure_mitres(doc)
    for o in doc.Objects:
        if isinstance(getattr(o,'Proxy',None),rev.DetailProxy) and o.WallProfile:rev.setprop(o,'App::PropertyLinkList','MitreSources',rev.corner_profiles(o.WallProfile))
    routes=json.loads(trial.TraceRoutes)
    for side,rows in routes.items():
        for row in rows:
            for key in ['start','end']:row[key]=list(mapped(App.Vector(*row[key]),side))
    trial.TraceRoutes=json.dumps(routes);trial.Proxy.execute(trial)
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' not in o.PropertiesList:continue
        specs=json.loads(o.PointDefinitions)
        for spec in specs:
            if spec.get('kind')=='fixed' and spec['source'].startswith(('A_','B_')):spec['point']=list(mapped(App.Vector(*spec['point']),spec['source'][0]))
        o.PointDefinitions=json.dumps(specs)
    for sid in ['EB1','EB2']:
        for j in [1,2]:o=doc.getObject(f'BridgeCheek{sid}{j}');o.Proxy.execute(o)
    doc.BridgeBackwallEB1.Proxy.execute(doc.BridgeBackwallEB1)
    rev.setprop(doc.MSEEndBentJointEnvelope,'App::PropertyLinkList','PanelProfiles',[doc.getObject('Wall'+s+str(j)+'Profile') for s in 'AB' for j in [6,7]])
    doc.MSEEndBentJointEnvelope.Proxy.execute(doc.MSEEndBentJointEnvelope)
    log('Rebuilding wall, footing, slab and detail dependency graph')
    # Explicit native recompute of the affected concrete graph. Steel and the
    # protected superstructure are outside this geometry correction.
    selected=[o for o in doc.Objects if o.Name.startswith(('Wall','Footing','A_','B_','Coping','Barrier','Plinth')) and 'Shape' in o.PropertiesList and 'Fill' not in o.Name]
    for o in doc.Objects:o.purgeTouched()
    for o in selected:o.touch()
    doc.recompute(selected)
    for o in doc.Objects:o.purgeTouched()
    return {'side_walls_moved_inward_in':6,'mitred_corner_pairs':CORNER_PAIRS,'finished_walls':finish_mitred_walls(doc)}

def repartition_details(doc,log):
    oldmap=json.loads(doc.MSECopingsAndBarriers.FinalDetailMapJSON)
    raw=[o for o in doc.Objects if isinstance(getattr(o,'Proxy',None),(rev.DetailProxy,rev.ReturnProxy))]
    sources=doc.MSEDetailSources;finished=[];mapping={};rows=[]
    walking=list(doc.MSESlopeChecks.Slabs)+[doc.BridgeDeckS1,doc.BridgeDeckS2]
    for base in raw:
        old=doc.getObject(base.Name+'BentJoint') or base;tools=[]
        for prior in walking+finished:
            if old.Shape.BoundBox.intersect(prior.Shape.BoundBox) and old.Shape.common(prior.Shape.copy()).Volume>1e-7:tools.append(prior)
        if tools:
            final=doc.addObject('Part::FeaturePython',base.Name+'Corrected')
            rev.setprop(final,'App::PropertyLink','Base',old);rev.setprop(final,'App::PropertyLinkList','ContactSources',tools);PartitionProxy(final);final.Proxy.execute(final)
            final.Label=base.Label+' - finished mitred contacts';doc.MSECopingsAndBarriers.addObject(final)
        else:final=old
        mapping[base.Name]=final.Name;finished.append(final)
        rows.append({'nominal':base.Name,'finished':final.Name,'tools':[o.Name for o in tools]})
    replacements={oldname:doc.getObject(mapping[name]) for name,oldname in oldmap.items()}
    doc.MSECopingsAndBarriers.FinalDetailMapJSON=json.dumps(mapping);doc.MSECopingsAndBarriers.FinishedDetails=finished
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' not in o.PropertiesList:continue
        specs=json.loads(o.PointDefinitions)
        for spec in specs:
            if spec['source'] in replacements:spec['source']=replacements[spec['source']].Name
        o.PointDefinitions=json.dumps(specs);o.Sources=[replacements.get(p.Name,p) for p in o.Sources]
    log('Regenerating elevation callouts from finished coping and barrier tops')
    barrier_hosts=[rev.finished_detail(doc,o) for o in raw if o.Kind=='Barrier']
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' not in o.PropertiesList:continue
        spec=json.loads(o.PointDefinitions)[0]
        if spec['kind'] in ['return_top','detail_reference']:
            nominal=doc.getObject(spec['nominal']);end=spec['end'];p=nominal.Path.Vertexes[0 if end==0 else -1].Point
            if spec['kind']=='return_top':
                n=nominal.PGL.Frame.Rotation.multVec(App.Vector(0,nominal.Side,0)) if end==0 else nominal.WallBarrier.WallProfile.Normal
                target=p+n*4*IN+App.Vector(0,0,42*IN);hosts=barrier_hosts
            else:
                target=dt.point_from_spec(doc,dict(spec,kind='detail',source=nominal.Name))
                hosts=[rev.finished_detail(doc,r) for r in raw if r.Kind==nominal.Kind]
            choices=[]
            for host in hosts:
                tops=[f for f in host.Shape.Faces if f.normalAt(sum(f.ParameterRange[:2])/2,sum(f.ParameterRange[2:])/2).z>.5]
                if tops:choices.append((Part.Vertex(target).distToShape(Part.makeCompound(tops))[0],host))
            distance,host=min(choices,key=lambda p:p[0])
            if distance>(.0254 if spec['kind']=='return_top' else IN):raise ValueError('Missing physical detail top '+nominal.Name)
            spec['source']=host.Name;o.PointDefinitions=json.dumps([spec]);o.Sources=[host,nominal]
        o.Proxy.execute(o)
    for o in doc.SlabElevations.Group:
        if 'Annotation' in o.PropertiesList:o.Proxy.execute(o)
    for o in [doc.CompletePGLTrace,doc.RampAPGL,doc.RampBPGL]:o.Proxy.execute(o)
    return rows

def finish_revised_interfaces(doc):
    """Conform the newly moved upper slab and rebuild the A8 footing contact."""
    replaced={}
    for oldname,basename,toolname,newname in [
        ('B_UpperRunSlab','B_UpperRunSlab','MSEEndBentJointEnvelope','B_UpperRunSlabBentJoint'),
        ('FootingA8Finished','FootingA8','FootingA8JointTools','FootingA8Corrected')]:
        old=doc.getObject(oldname);base=doc.getObject(basename);tool=doc.getObject(toolname)
        final=doc.addObject('Part::FeaturePython',newname)
        rev.setprop(final,'App::PropertyLink','Base',base);rev.setprop(final,'App::PropertyLinkList','ContactSources',[tool]);PartitionProxy(final);final.Proxy.execute(final)
        final.Label=old.Label+' - corrected native contact';replaced[oldname]=final
        # Replace consumers, preserving the nominal concrete and the new source.
        for parent in list(old.InList):
            if parent==final:continue
            if parent.TypeId=='App::DocumentObjectGroup':parent.removeObject(old);parent.addObject(final);continue
            for key in parent.PropertiesList:
                if parent==doc.MSEAssembly and key=='NominalConcrete':continue
                typ=parent.getTypeIdOfProperty(key)
                if typ=='App::PropertyLink' and getattr(parent,key)==old:setattr(parent,key,final)
                elif typ=='App::PropertyLinkList' and old in getattr(parent,key):setattr(parent,key,[final if p==old else p for p in getattr(parent,key)])
        if oldname!=basename:doc.removeObject(oldname)
        else:doc.MSEInterfaceSources.addObject(old)
    routes=json.loads(doc.DrainageTrial.TraceRoutes)
    for rows in routes.values():
        for row in rows:
            if row['slab'] in replaced:row['slab']=replaced[row['slab']].Name
    doc.DrainageTrial.TraceRoutes=json.dumps(routes)
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' not in o.PropertiesList:continue
        specs=json.loads(o.PointDefinitions)
        for s in specs:
            if s['source'] in replaced:s['source']=replaced[s['source']].Name
        o.PointDefinitions=json.dumps(specs);o.Proxy.execute(o)
    # This superseded return contact has no physical consumers after repartition.
    obsolete=doc.getObject('BarrierReturnEB2RContactFinal')
    if obsolete:
        if any(p.TypeId!='App::DocumentObjectGroup' for p in obsolete.InList):raise ValueError('Superseded contact still has consumers')
        doc.removeObject(obsolete.Name)
    for o in [doc.CompletePGLTrace,doc.RampAPGL,doc.RampBPGL]:o.Proxy.execute(o)
    for o in doc.SlabElevations.Group:
        if 'Annotation' in o.PropertiesList:o.Proxy.execute(o)
    return {a:b.Name for a,b in replaced.items()}
