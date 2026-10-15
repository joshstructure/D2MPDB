"""Editable 15 October cheek tops, deep return barriers and coping stops."""
import json
import FreeCAD as App
import Part
from . import bridge, mse, mse_revision as rev, deck_edge_details as edge

IN=25.4
FT=304.8
CONNECTIONS=(('EB1','L','A6',1),('EB1','R','A7',2),
             ('EB2','L','B6',1),('EB2','R','B7',2))


def local_shape(obj, frame):
    shape=obj.Shape.copy()
    shape.Placement=frame.inverse().multiply(shape.Placement)
    return shape


def back_station(inp):
    cap=local_shape(inp.Cap,inp.PGL.Frame).BoundBox
    return cap.XMin-inp.PGL.MSELugProjection.Value if inp.SupportID=='EB1' else cap.XMax+inp.PGL.MSELugProjection.Value


class CheekProxy(rev.CheekProxy):
    def execute(self,obj):
        super().execute(obj)
        target=obj.ReturnDetail.BaseElevation.Value
        old=obj.TopElevation.Value
        if target<=old:raise ValueError('Return base must be above the original cheek top')
        c=obj.PGL;cap=local_shape(obj.ReturnDetail.Cap,c.Frame).BoundBox
        shape=local_shape(obj,c.Frame);b=shape.BoundBox
        y=b.YMin if obj.BeamIndex==0 else b.YMax-c.EndCheekThickness.Value
        web=Part.makeBox(cap.XLength,c.EndCheekThickness.Value,target-old,App.Vector(cap.XMin,y,old))
        ly=b.YMin if obj.BeamIndex==0 else b.YMax-c.MSELugWidth.Value
        rear=cap.XMin-c.MSELugProjection.Value if obj.SupportID=='EB1' else cap.XMax
        lug=Part.makeBox(c.MSELugProjection.Value,c.MSELugWidth.Value,target-old,App.Vector(rear,ly,old))
        shape=shape.multiFuse([web,lug]).removeSplitter();shape.Placement=c.Frame
        obj.Shape=shape;obj.NetVolume=shape.Volume;obj.TopElevation=target


def miter(a,b):
    determinant=a.x*b.y-a.y*b.x
    if abs(determinant)<1e-8:raise ValueError('Return corner axes are parallel')
    return App.Vector((b.y-a.y)/determinant,(a.x-b.x)/determinant,0)


def return_rings(obj):
    inp=obj.ReturnDetail;c=inp.PGL;frame=c.Frame;inv=frame.inverse()
    q=1 if inp.SupportID=='EB1' else -1;side=obj.Side
    model=bridge.model(c);support=bridge.support_data(c)[inp.SupportID]
    datum=(support['datum']-model.start)*FT
    inside=side*(c.DeckWidth.Value/2-inp.DeckBarrier.DeckEdgeSetback.Value-8*IN)
    x=datum-q*inp.ReturnStationOffset.Value
    tangent=inv.Rotation.multVec(obj.WallBarrier.WallProfile.Tangent)
    axis=inp.WallAxisPoint
    y=lambda station:axis.y+(station-axis.x)*tangent.y/tangent.x
    back=back_station(inp);z=inp.BaseElevation.Value
    points=[App.Vector(datum,inside,z),App.Vector(x,inside,z),
            App.Vector(x,y(x),z),App.Vector(back,y(back),z)]
    n0=App.Vector(0,side,0);n1=App.Vector(q,0,0)
    n2=inv.Rotation.multVec(obj.WallBarrier.WallProfile.Normal)
    normals=[n0,miter(n0,n1),miter(n1,n2),n2]
    profile=json.loads(obj.WallBarrier.ProfileJSON)
    rings=[[p+n*(a*IN)+App.Vector(0,0,b*IN) for a,b in profile]
           for p,n in zip(points,normals)]
    return points,normals,rings


class ReturnProxy(rev.ReturnProxy):
    def execute(self,obj):
        points,normals,rings=return_rings(obj)
        frame=obj.PGL.Frame
        path=Part.makePolygon(points);path.transformShape(frame.toMatrix())
        obj.Path=path;obj.MeasuredLength=path.Length
        if obj.Kind=='ReturnPlinth':
            obj.Shape=Part.Shape();obj.NetVolume=0
            obj.Label=obj.SupportID+' return coping retired - barrier extends to slab'
            return
        shape=rev.join_solids([rev.ruled_profile_solid(a,b) for a,b in zip(rings,rings[1:])])
        # Continue the transverse band and outer leg over the extended landing.
        # Its exact surface clips the underside; the cheek owns its concrete.
        a,b=points[1:3];na,nb=normals[1:3]
        landing=getattr(obj,'ReturnLandingSlab',None)
        footprint=([a,b,points[3],points[3]+normals[3]*8*IN,b+nb*8*IN,a+na*8*IN]
                   if landing else [a,b,b+nb*8*IN,a+na*8*IN])
        extension=rev.closed_face(footprint).extrude(App.Vector(0,0,-24*IN))
        extension.Placement=frame
        surface=landing.ExtendedSurface if landing else obj.LandingSurface.Shape
        above=surface.Faces[0].extrude(App.Vector(0,0,100*IN))
        extension=extension.common(above)
        shape.Placement=frame
        slab=landing if landing else obj.LandingSlab
        # Keep native spline trim edges: unifying these faces can discard a
        # required boundary at the right-hand B landing/coping junction.
        shape=shape.fuse(extension).cut(obj.CheekSource.Shape.copy(),0.0).cut(slab.Shape.copy(),0.0)
        for contact in getattr(obj,'GapContactSources',[]):
            shape=shape.cut(contact.Shape.copy(),0.0)
        if not shape.isValid() or len(shape.Solids)!=1:raise ValueError('Invalid revised return '+obj.Name)
        obj.Shape=shape;obj.NetVolume=shape.Volume
        obj.ConnectionBasis='15 October: raised cheek flush with return base; transverse bottom band extends to native slab; coping stops at rear lug face; deck face follows adopted inset.'


class CopingStopProxy(mse.Serializable):
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        inp=obj.ReturnDetail;station=back_station(inp);extent=1e6
        x=station-extent if inp.SupportID=='EB1' else station
        keep=Part.makeBox(extent,2*extent,2*extent,App.Vector(x,-extent,-extent));keep.Placement=inp.PGL.Frame
        shape=obj.Base.Shape.copy().common(keep).removeSplitter()
        if not shape.Solids:shape=Part.Shape()
        if not shape.isNull() and not shape.isValid():raise ValueError('Invalid coping stop '+obj.Name)
        obj.Shape=shape;obj.NetVolume=0 if shape.isNull() else shape.Volume


class ContactProxy(mse.Serializable):
    def __init__(self,obj):
        if 'NetVolume' not in obj.PropertiesList:
            rev.setprop(obj,'App::PropertyVolume','NetVolume',0,'Quantity')
        obj.Proxy=self
    def execute(self,obj):
        shape=obj.Base.Shape.copy()
        for source in obj.ContactSources:
            if not shape.Solids:
                shape=Part.Shape()
                break
            if not source.Shape.isNull() and shape.BoundBox.intersect(source.Shape.BoundBox):
                shape=shape.cut(source.Shape.copy(),0.0).removeSplitter()
        if not shape.Solids:shape=Part.Shape()
        if not shape.isNull() and not shape.isValid():raise ValueError('Invalid return contact '+obj.Name)
        obj.Shape=shape;obj.NetVolume=0 if shape.isNull() else shape.Volume


def configure(doc):
    if doc.getObject('ReturnDetailControls'):raise ValueError('Return revision already installed')
    root=doc.addObject('App::DocumentObjectGroup','ReturnDetailControls');root.Label='Return and cheek connection controls'
    doc.BridgeAssembly.addObject(root)
    mapping=json.loads(doc.MSECopingsAndBarriers.FinalDetailMapJSON);changed=[];rows=[]
    for sid,letter,wall,j in CONNECTIONS:
        bar=doc.getObject('BarrierReturn'+sid+letter)
        plinth=doc.getObject('PlinthReturn'+sid+letter)
        cheek=doc.getObject('BridgeCheek'+sid+str(j))
        inp=doc.addObject('App::FeaturePython','ReturnDetail'+sid+letter);root.addObject(inp)
        inp.Label=sid+' '+letter+' return / cheek shared dimensions'
        z=bar.Path.Vertexes[-1].Point.z
        axis=doc.BridgePGL.Frame.inverse().multVec(bar.Path.Vertexes[-1].Point)
        properties=[('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyLink','Cap',doc.getObject('BridgeCap'+sid)),
            ('App::PropertyLink','DeckBarrier',doc.getObject('BarrierDeck'+('S1' if sid=='EB1' else 'S2')+letter)),
            ('App::PropertyString','SupportID',sid),('App::PropertyLength','BaseElevation',z),
            ('App::PropertyLength','ReturnStationOffset','8.25 in'),('App::PropertyVector','WallAxisPoint',axis),
            ('App::PropertyString','CopingStopBasis','Outer face of rear lug, per user'),
            ('App::PropertyString','ElevationBasis','Exact adopted return underside elevation; shared editable control for cheek and barrier')]
        for typ,name,value in properties:rev.setprop(inp,typ,name,value,'Return connection')
        oldtop=cheek.TopElevation.Value
        rev.setprop(cheek,'App::PropertyLink','ReturnDetail',inp,'Return connection');CheekProxy(cheek);cheek.Proxy.execute(cheek)
        changed.append(cheek.Name)
        for obj in [bar,plinth]:
            rev.setprop(obj,'App::PropertyLink','ReturnDetail',inp,'Return connection')
            rev.setprop(obj,'App::PropertyLink','CheekSource',cheek,'Return connection')
            ReturnProxy(obj);obj.Proxy.execute(obj);changed.append(obj.Name)
        final=doc.getObject(mapping[bar.Name])
        if final!=bar:
            final.ContactSources=[];ContactProxy(final);final.Proxy.execute(final);changed.append(final.Name)
        pf=doc.getObject(mapping[plinth.Name])
        if pf!=plinth:
            pf.ContactSources=[];ContactProxy(pf);pf.Proxy.execute(pf);changed.append(pf.Name)
        for kind in ['Coping','Barrier']:
            raw=doc.getObject(kind+wall);old=doc.getObject(mapping[raw.Name])
            final=doc.addObject('Part::FeaturePython',raw.Name+'AtCheek')
            rev.setprop(final,'App::PropertyLink','Base',old,'Return connection')
            rev.setprop(final,'App::PropertyVolume','NetVolume',0,'Quantity')
            if kind=='Coping':
                rev.setprop(final,'App::PropertyLink','ReturnDetail',inp,'Return connection');CopingStopProxy(final)
                final.Label=raw.Label+' - stops at cheek rear lug'
            else:
                rev.setprop(final,'App::PropertyLinkList','ContactSources',[doc.getObject(mapping[bar.Name]),cheek],'Return connection');ContactProxy(final)
                final.Label=raw.Label+' - clean return interface'
            final.Proxy.execute(final)
            doc.MSECopingsAndBarriers.addObject(final)
            if App.GuiUp:
                final.ViewObject.ShapeAppearance=old.ViewObject.ShapeAppearance
                final.ViewObject.LineColor=old.ViewObject.LineColor
                final.ViewObject.Transparency=old.ViewObject.Transparency
                old.ViewObject.Visibility=False
                final.ViewObject.Visibility=not final.Shape.isNull()
            mapping[raw.Name]=final.Name;changed.append(final.Name)
        rows.append({'connection':sid+letter,'old_cheek_top_ft':oldtop/FT,'new_cheek_top_ft':z/FT,'raise_in':(z-oldtop)/IN,'coping_stop_local_in':back_station(inp)/IN})
    # EB2 right is adjacent to the B2 corner as well as the short B7 segment.
    # Give the revised return ownership of their common concrete.
    old=doc.getObject(mapping['BarrierB2'])
    final=doc.addObject('Part::FeaturePython','BarrierB2AtReturn')
    rev.setprop(final,'App::PropertyLink','Base',old,'Return connection')
    rev.setprop(final,'App::PropertyLinkList','ContactSources',[doc.BarrierReturnEB2R],'Return connection')
    ContactProxy(final);final.Proxy.execute(final)
    final.Label=old.Label+' - clean return interface'
    doc.MSECopingsAndBarriers.addObject(final)
    if App.GuiUp:
        final.ViewObject.ShapeAppearance=old.ViewObject.ShapeAppearance
        final.ViewObject.LineColor=old.ViewObject.LineColor
        old.ViewObject.Visibility=False
    mapping['BarrierB2']=final.Name;changed.append(final.Name)
    doc.MSECopingsAndBarriers.FinalDetailMapJSON=json.dumps(mapping)
    doc.MSECopingsAndBarriers.FinishedDetails=[doc.getObject(n) for n in mapping.values()]
    # Shape changes are explicit above. Do not let a broad recompute rebuild
    # all native steel, schedules and unrelated geometry before the clash review.
    for obj in doc.Objects:obj.purgeTouched()
    return {'changed':changed,'connections':rows}


def inspect(doc, previous_physical=None):
    objects=edge.physical_objects(doc);changed={'BarrierB2AtReturn'}
    for sid,letter,wall,j in CONNECTIONS:
        changed.update(['BridgeCheek'+sid+str(j),'BarrierReturn'+sid+letter,'BarrierReturn'+sid+letter+'Corrected',
                        'Coping'+wall+'AtCheek','Barrier'+wall+'AtCheek'])
    overlaps=[];seen=set()
    for name in sorted(changed.intersection(objects)):
        obj=objects[name]
        for other,target in objects.items():
            if name==other:continue
            pair=tuple(sorted((name,other)))
            if pair in seen:continue
            seen.add(pair)
            # Reinforcement is intentionally contained by its own concrete host.
            if 'Diameter' in target.PropertiesList:continue
            if obj.Shape.BoundBox.intersect(target.Shape.BoundBox):
                volume=abs(obj.Shape.copy().common(target.Shape.copy()).Volume)
                if volume>0:overlaps.append({'a':pair[0],'b':pair[1],'volume_in3':volume/IN**3})
    return {'physical_objects':len(objects),'concrete_overlaps':overlaps,
            'invalid':[o.Name for o in doc.Objects if 'Invalid' in o.State],
            'steel':'Not refreshed yet; concrete prototype only'}


def refresh_dependents(doc, refresh_steel=True):
    from . import cheek_steel, lug_wwr
    changed=[]
    if refresh_steel:
        for host in cheek_steel.HOSTS:
            cheek_steel.refresh(doc.getObject('Steel'+host+'Inputs'))
        for inp in doc.CheekLugWWRQuantities.Inputs:inp.Proxy.execute(inp)
        lug_wwr.schedule(doc)
    replacements={o.Base.Name:o for o in doc.Objects
                  if type(getattr(o,'Proxy',None)).__module__==__name__
                  and type(o.Proxy).__name__ in ('CopingStopProxy','ContactProxy')
                  and o.Name.endswith(('AtCheek','AtReturn')) and o.Shape.Solids}
    removed=[]
    # B7 is entirely replaced by the longer return; its duplicate labels retire.
    for name in ['DXFDetailElevation280','DXFDetailElevation281']:
        for n in [name+'Leader',name]:
            if doc.getObject(n):doc.removeObject(n);removed.append(n)
    for obj in doc.Objects:
        if 'PointDefinitions' not in obj.PropertiesList:continue
        specs=json.loads(obj.PointDefinitions);affected=False
        for spec in specs:
            if spec['kind']=='return_top':
                spec['source']=rev.finished_detail(doc,doc.getObject(spec['nominal'])).Name
                affected=True
            elif spec['source'] in replacements:
                spec['source']=replacements[spec['source']].Name;affected=True
            elif spec['source'] in cheek_steel.HOSTS:affected=True
        if affected:
            obj.PointDefinitions=json.dumps(specs)
            names=set(s['source'] for s in specs)|{s['nominal'] for s in specs if 'nominal' in s}
            obj.Sources=[doc.getObject(n) for n in sorted(names)]
            obj.Proxy.execute(obj);changed.append(obj.Name)
            leader=doc.getObject(obj.Name+'Leader')
            if leader:leader.Proxy.execute(leader);changed.append(leader.Name)
    for obj in doc.Objects:obj.purgeTouched()
    sheets=[doc.BridgeConcreteSchedule,doc.CheekLugWWRSchedule]
    for obj in sheets:obj.touch()
    doc.recompute(sheets)
    changed.extend(o.Name for o in sheets)
    return {'changed':changed,'removed':removed}


class ReturnLandingProxy(mse.Serializable):
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        from types import SimpleNamespace
        from . import drainage_trial as dt
        surface=obj.LandingSurface
        settings=dt.settings(surface.DrainageTrial,surface.TrialSide)
        # Continue the exact native crowned/transition surface across the small
        # side gaps. Existing surface geometry and drainage inputs stay intact.
        top=dt.landing_face(settings,settings['xmin']-16*IN,settings['join']+16*IN)
        obj.ExtendedSurface=top
        slab=top.extrude(App.Vector(0,0,-obj.Thickness.Value))
        additions=[]
        for inp,wall,cheek,side in zip(obj.ReturnInputs,obj.WallBarriers,obj.Cheeks,[-1,1]):
            control=SimpleNamespace(ReturnDetail=inp,PGL=inp.PGL,Side=side,WallBarrier=wall)
            points,normals,_=return_rings(control)
            a,b,c=points[1:];na,nb,nc=normals[1:]
            outline=[a,b,c,c+nc*8*IN,b+nb*8*IN,a+na*8*IN]
            outline=[App.Vector(v.x,v.y,0) for v in outline]
            prism=rev.closed_face(outline).extrude(App.Vector(0,0,1000*IN));prism.Placement=inp.PGL.Frame
            addition=slab.common(prism).cut(cheek.Shape.copy(),0.0).removeSplitter()
            additions.append(addition)
        shape=obj.Base.Shape.copy().multiFuse(additions).removeSplitter()
        # Join the continuous slab before cutting neighboring concrete. Cutting
        # individual patches first creates coincident spline slivers at the join.
        for contact in getattr(obj,'ContactSources',[]):
            if contact.Shape.Solids:shape=shape.cut(contact.Shape.copy(),0.0).removeSplitter()
        if not shape.isValid() or len(shape.Solids)!=1:raise ValueError('Invalid continued landing '+obj.Name)
        obj.Shape=shape;obj.NetVolume=shape.Volume


def close_return_voids(doc):
    """Continue both 4-inch landings beneath all four outer return corners."""
    if doc.getObject('A_BridgeLandingAtReturns'):raise ValueError('Gap closure already installed')
    changed=[];replacements={}
    for sid,side in [('EB1','A'),('EB2','B')]:
        bars=[doc.getObject('BarrierReturn'+sid+l) for l in ['L','R']]
        old=bars[0].LandingSlab
        slab=doc.addObject('Part::FeaturePython',side+'_BridgeLandingAtReturns')
        for typ,name,value in [('App::PropertyLink','Base',old),('App::PropertyLink','LandingSurface',bars[0].LandingSurface),
            ('App::PropertyLinkList','ReturnInputs',[b.ReturnDetail for b in bars]),
            ('App::PropertyLinkList','WallBarriers',[b.WallBarrier for b in bars]),
            ('App::PropertyLinkList','Cheeks',[b.CheekSource for b in bars]),
            ('App::PropertyLength','Thickness','4 in'),('Part::PropertyPartShape','ExtendedSurface',Part.Shape()),
            ('App::PropertyVolume','NetVolume',0)]:rev.setprop(slab,typ,name,value,'Return gap closure')
        slab.setExpression('Thickness','MSEInputs.SlabThickness')
        ReturnLandingProxy(slab);slab.Proxy.execute(slab)
        slab.Label=side+' landing slab - continued beneath returns'
        for parent in list(old.InList):
            if parent.TypeId=='App::DocumentObjectGroup':parent.addObject(slab);changed.append(parent.Name)
        replacements[old.Name]=slab;changed.append(slab.Name)
        if App.GuiUp:
            slab.ViewObject.ShapeAppearance=old.ViewObject.ShapeAppearance
            slab.ViewObject.LineColor=old.ViewObject.LineColor
            old.ViewObject.Visibility=False
        for bar in bars:
            rev.setprop(bar,'App::PropertyLink','ReturnLandingSlab',slab,'Return gap closure')
            ReturnProxy(bar);bar.Proxy.execute(bar);changed.append(bar.Name)
            final=rev.finished_detail(doc,bar)
            if final!=bar:final.Proxy.execute(final);changed.append(final.Name)
    for owner,prop in [(doc.MSEAssembly,'FinishedConcrete'),(doc.BridgeGeometryChecks,'ExistingConcrete'),(doc.MSESlopeChecks,'Slabs')]:
        setattr(owner,prop,[replacements.get(o.Name,o) for o in getattr(owner,prop)]);changed.append(owner.Name)
    routes=json.loads(doc.DrainageTrial.TraceRoutes)
    for rows in routes.values():
        for row in rows:
            if row['slab'] in replacements:row['slab']=replacements[row['slab']].Name
    doc.DrainageTrial.TraceRoutes=json.dumps(routes);changed.append('DrainageTrial')
    for obj in doc.Objects:
        if 'PointDefinitions' not in obj.PropertiesList:continue
        specs=json.loads(obj.PointDefinitions)
        if any(s['source'] in replacements for s in specs):
            for spec in specs:
                if spec['source'] in replacements:spec['source']=replacements[spec['source']].Name
            obj.PointDefinitions=json.dumps(specs);obj.Sources=[replacements.get(o.Name,o) for o in obj.Sources]
            obj.Proxy.execute(obj);changed.append(obj.Name)
            leader=doc.getObject(obj.Name+'Leader')
            if leader:leader.Proxy.execute(leader);changed.append(leader.Name)
    changed.extend(refine_void_contacts(doc))
    for obj in doc.Objects:obj.purgeTouched()
    return {'changed':sorted(set(changed)),'replacements':{k:v.Name for k,v in replacements.items()}}


def refine_void_contacts(doc):
    """Existing walls, coping and neighboring slab own the shared concrete."""
    changed=[]
    trims={'A':['WallA6Mitred','WallA7Mitred','CopingA6AtCheek'],
           'B':['WallB2Mitred','WallB6Mitred','WallB7Mitred','B_UpperRunSlabBentJoint','CopingB2BentJoint']}
    for side,names in trims.items():
        obj=doc.getObject(side+'_BridgeLandingAtReturns')
        rev.setprop(obj,'App::PropertyLinkList','ContactSources',[doc.getObject(n) for n in names],'Return gap closure')
        ReturnLandingProxy(obj);obj.Proxy.execute(obj);changed.append(obj.Name)
    for sid,l,w,j in CONNECTIONS:
        bar=doc.getObject('BarrierReturn'+sid+l)
        names={'EB1L':['CopingA6AtCheek'],'EB1R':['WallA7Mitred'],'EB2R':['CopingB2BentJoint']}.get(sid+l,[])
        rev.setprop(bar,'App::PropertyLinkList','GapContactSources',[doc.getObject(n) for n in names],'Return gap closure')
        ReturnProxy(bar);bar.Proxy.execute(bar);changed.append(bar.Name)
        final=rev.finished_detail(doc,bar)
        if final!=bar:final.Proxy.execute(final);changed.append(final.Name)
    for name in ['BarrierA6AtCheek','BarrierA7AtCheek','BarrierB6AtCheek','BarrierB7AtCheek','BarrierB2AtReturn']:
        obj=doc.getObject(name);ContactProxy(obj);obj.Proxy.execute(obj);changed.append(name)
    return changed
