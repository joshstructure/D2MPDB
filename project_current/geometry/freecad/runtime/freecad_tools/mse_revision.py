"""B4 DXF 14 October 2026: editable wall interfaces, coping and barrier.

Geometry controllers only. Source reinforcement remains a separate design basis.
"""
import json, math
import numpy as np
import FreeCAD as App
import Part
from . import bridge, mse, drainage_trial as dt
from .mse import prop, Serializable
IN=25.4
FT=304.8

def setprop(o,typ,n,v,group='14 October DXF'):
    if n not in o.PropertiesList:prop(o,typ,n,v,group)
    else:setattr(o,n,v)

def closed_face(points):
    return Part.Face(Part.makePolygon(points+[points[0]]))

def section_sweep(edge,normal,profile):
    """Exact vertical section translation along a curved, planar ramp edge."""
    offsets=[normal*(a*IN)+App.Vector(0,0,b*IN) for a,b in profile]
    rails=[]
    for v in offsets:
        e=edge.copy();e.translate(v);rails.append(e)
    faces=[Part.makeRuledSurface(a,b) for a,b in zip(rails,rails[1:]+rails[:1])]
    for t in [edge.FirstParameter,edge.LastParameter]:
        p=edge.valueAt(t);faces.append(closed_face([p+v for v in offsets]))
    solid=Part.makeSolid(Part.makeShell(faces))
    if solid.Volume<0:solid.reverse()
    if not solid.isValid() or len(solid.Solids)!=1:raise ValueError('Invalid detail section sweep')
    return solid

def join_solids(solids):
    if not solids:return Part.Shape()
    if len(solids)==1:return solids[0]
    return solids[0].multiFuse(solids[1:]).removeSplitter()

def corner_point(a,b):
    denominator=a.Tangent.cross(b.Tangent).z
    if abs(denominator)<.99:raise ValueError('Mitre requires perpendicular wall axes')
    distance=(b.Start-a.Start).cross(b.Tangent).z/denominator
    p=a.Start+a.Tangent*distance;p.z=0
    return p

def corner_profiles(profile):
    return [profile.Document.getObject(n) for n in getattr(profile,'CornerProfileNames',[])]

def mitre_clip(shape,profile):
    """Intersect the native solid with the 45 degree corner ownership planes."""
    for other in corner_profiles(profile):
        vertex=corner_point(profile,other);normal=profile.Normal-other.Normal;normal.normalize()
        mid=profile.Start+profile.Tangent*(profile.TopControls[-1].x/2)
        if (mid-vertex).dot(normal)<0:normal=-normal
        along=App.Vector(-normal.y,normal.x,0);span=1e6
        origin=vertex-App.Vector(0,0,span)
        face=closed_face([origin-along*span,origin+along*span,origin+along*span+normal*span,origin-along*span+normal*span])
        # Keep the original face parameterizations between corner cuts. OCC's
        # intermediate splitter removal can make the next corner Boolean empty
        # on the stepped B6 wall despite a valid first solid.
        shape=shape.common(face.extrude(App.Vector(0,0,2*span)))
    return shape

def surface_for_interval(w,i):
    a,b=w.TopSamplePoints[i:i+2]
    p=(a+b)*.5
    choices=[s for s in w.SurfaceSources if s.Shape.BoundBox.XMin-.03<=p.x<=s.Shape.BoundBox.XMax+.03 and s.Shape.BoundBox.YMin-.03<=p.y<=s.Shape.BoundBox.YMax+.03]
    preferred=w.TopSourceNames[i]
    return next((s for s in choices if s.Name==preferred),choices[0] if len(choices)==1 else None)

def top_edges(w,walking=False):
    edges=[];indices=[]
    for i,(a,b) in enumerate(zip(w.TopControls,w.TopControls[1:])):
        pa=w.Start+w.Tangent*a.x;pb=w.Start+w.Tangent*b.x
        names=w.TopSourceNames
        if b.x-a.x>1e-6 and names[i] and names[i+1]:
            s=surface_for_interval(w,i)
            if s is None:raise ValueError('Ambiguous surface interval '+w.Name+' '+str(i))
            # Native cubic curves for the revised walking edge. Source sample
            # endpoints can deliberately clamp to the end of a landing.
            qa,qb=w.TopSamplePoints[i:i+2]
            cuts=[0.,1.]
            if 'DrainageTrial' in s.PropertiesList:
                cfg=dt.settings(s.DrainageTrial,s.TrialSide)
                taper=cfg.get('taper',.1)
                for coord,val in [('y',cfg['turn'])]+[('x',cfg['join']+f*cfg['blend']) for f in [taper,1-taper,1.]]:
                    delta=getattr(qb,coord)-getattr(qa,coord)
                    if abs(delta)>1e-9:
                        t=(val-getattr(qa,coord))/delta
                        if 0<t<1:cuts.append(t)
            mat=np.array([[1,0,0,0],[8/27,12/27,6/27,1/27],[1/27,6/27,12/27,8/27],[0,0,0,1]])
            def segment(lo,hi,depth=0):
                def value(t):
                    p=pa+(pb-pa)*t;q=qa+(qb-qa)*t
                    p.z=mse.height(s,q.x,q.y)+(0 if walking else w.Inputs.WallUpstand.Value)
                    return p
                pts=[value(lo+(hi-lo)*t) for t in [0.,1/3,2/3,1.]]
                poles=np.linalg.solve(mat,np.array([list(p) for p in pts]))
                curve=Part.BezierCurve();curve.setPoles([App.Vector(*p) for p in poles])
                error=max(curve.value(t).distanceToPoint(value(lo+(hi-lo)*t)) for t in [.125,.25,.5,.75,.875])
                if error>.000254:
                    if depth>=16:raise ValueError('Wall curve tolerance exceeded')
                    return segment(lo,(lo+hi)/2,depth+1)+segment((lo+hi)/2,hi,depth+1)
                return [curve.toShape()]
            for lo,hi in zip(sorted(set(cuts)),sorted(set(cuts))[1:]):
                ee=segment(lo,hi);edges+=ee;indices += [i]*len(ee)
        elif not walking:
            zs=[]
            for j,t in [(i,a),(i+1,b)]:
                if names[j]:
                    s=w.Document.getObject(names[j]);q=w.TopSamplePoints[j]
                    zs.append(mse.height(s,q.x,q.y)+w.Inputs.WallUpstand.Value)
                else:zs.append(t.z)
            pa.z,pb.z=zs
            if pa.distanceToPoint(pb)>1e-6:edges.append(Part.makeLine(pa,pb));indices.append(i)
    return edges,indices

class WallProfileProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        edges,_=top_edges(o)
        first=edges[0].Vertexes[0].Point;last=edges[-1].Vertexes[-1].Point
        bottom=[o.Start+o.Tangent*p.x+App.Vector(0,0,p.z) for p in reversed(o.BaseControls)]
        pts=[last]+bottom+[first]
        edges += [Part.makeLine(a,b) for a,b in zip(pts,pts[1:]) if a.distanceToPoint(b)>1e-7]
        o.Shape=Part.Wire(edges)
        o.ComputedTop=[App.Vector(p.x,0,(mse.height(o.Document.getObject(n),q.x,q.y)+o.Inputs.WallUpstand.Value) if n else p.z) for p,q,n in zip(o.TopControls,o.TopSamplePoints,o.TopSourceNames)]

class CheekProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        c=o.PGL;m=bridge.model(c);r=bridge.support_data(c)[o.SupportID]
        half=c.EndCapLength.Value/2;thick=c.EndCheekThickness.Value
        outside=-half-thick if o.BeamIndex==0 else half
        x=(r['station']-m.start-r['width']/2)*FT
        bottom=r['bottom']*FT
        top=float(m.deck_top(r['datum'],m.deck_left))*FT
        main=Part.makeBox(r['width']*FT,thick,top-bottom,App.Vector(x,outside,bottom))
        # DXF bottom and back legs: six-inch projection, 5.5-inch outer width.
        ly=outside if o.BeamIndex==0 else outside+thick-c.MSELugWidth.Value
        rear=x-c.MSELugProjection.Value if o.SupportID=='EB1' else x+r['width']*FT
        foot=Part.makeBox(r['width']*FT,c.MSELugWidth.Value,c.MSELugProjection.Value,App.Vector(x,ly,bottom-c.MSELugProjection.Value))
        back=Part.makeBox(c.MSELugProjection.Value,c.MSELugWidth.Value,top-bottom+c.MSELugProjection.Value,App.Vector(rear,ly,bottom-c.MSELugProjection.Value))
        o.Shape=main.fuse(foot).fuse(back).removeSplitter();o.Placement=c.Frame;o.NetVolume=o.Shape.Volume
        o.Label=o.SupportID+' cheek '+str(o.BeamIndex+1)+' — 8 in wall, 6 in bottom/back lugs'
        setprop(o,'App::PropertyLength','TopElevation',top)
        setprop(o,'App::PropertyLength','WallBottomElevation',bottom)
        setprop(o,'App::PropertyLength','LugBottomElevation',bottom-c.MSELugProjection.Value)

class BackwallProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        c=o.PGL;m=bridge.model(c);r=bridge.support_data(c)[o.SupportID]
        rear=r['station']-r['width']/2;front=r['station']+r['width']/2
        a,b=(rear,r['datum']) if o.SupportID=='EB1' else (r['datum'],front)
        half=c.EndCapLength.Value/2;x=(a-m.start)*FT
        top=lambda y:float(m.deck_top(r['datum'],y/FT))*FT-c.EndBackwallDrop.Value
        face=closed_face([App.Vector(x,-half,r['top']*FT),App.Vector(x,half,r['top']*FT),App.Vector(x,half,top(half)),App.Vector(x,0,top(0)),App.Vector(x,-half,top(-half))])
        shape=face.extrude(App.Vector((b-a)*FT,0,0))
        shape.Placement=c.Frame
        if getattr(o,'SeatingSlabSource',None):
            shape=shape.cut(o.SeatingSlabSource.Shape).removeSplitter()
        o.Shape=shape;o.NetVolume=o.Shape.Volume

class DetailProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        if o.Kind=='Coping':profile=[(0,-8),(0,9),(11.5,9),(11.5,-21),(5.5,-21),(5.5,-8)]
        else:profile=json.loads(o.ProfileJSON)
        solids=[];paths=[]
        if o.WallProfile:
            w=o.WallProfile;edges,_=top_edges(w,True);normal=w.Normal
            offsets=[(sample-(w.Start+w.Tangent*control.x)).dot(w.Normal) for control,sample,name in zip(w.TopControls,w.TopSamplePoints,w.TopSourceNames) if name]
            reverse=bool(offsets) and min(offsets)>w.Inputs.WallThickness.Value/2
            if reverse:
                edges=[e.copy() for e in edges]
                for e in edges:e.translate(w.Normal*w.Inputs.WallThickness.Value)
                normal=-w.Normal
            # Extend to the outside of both corner profiles, then cut the
            # matching 45-degree plane through the complete section.
            width=(11.5 if o.Kind=='Coping' else 8)*IN
            endpoints=[e.valueAt(t) for e in edges for t in [e.FirstParameter,e.LastParameter]]
            if endpoints:
                first=min(endpoints,key=lambda p:p.dot(w.Tangent));last=max(endpoints,key=lambda p:p.dot(w.Tangent))
                lo,hi=first.dot(w.Tangent),last.dot(w.Tangent)
                for other in corner_profiles(w):
                    if not any(a and b for a,b in zip(other.TopSourceNames,other.TopSourceNames[1:])):continue
                    v=corner_point(w,other)+(w.Normal+other.Normal)*width
                    lo=min(lo,v.dot(w.Tangent));hi=max(hi,v.dot(w.Tangent))
                if first.dot(w.Tangent)-lo>1e-6:edges.insert(0,Part.makeLine(first-w.Tangent*(first.dot(w.Tangent)-lo),first))
                if hi-last.dot(w.Tangent)>1e-6:edges.append(Part.makeLine(last,last+w.Tangent*(hi-last.dot(w.Tangent))))
            setprop(o,'App::PropertyString','WalkingFace','Opposite extrusion face' if reverse else 'Profile face')
            for e in edges:
                base=e.copy()
                if o.Kind=='Barrier':base.translate(App.Vector(0,0,9*IN))
                solids.append(section_sweep(base,normal,profile));paths.append(base)
        else:
            c=o.PGL;m=bridge.model(c);i=o.SpanIndex;side=o.Side
            a,b=bridge.deck_limits(c,i);offset=side*c.DeckWidth.Value/2
            p=c.Frame.multVec(App.Vector((a-m.start)*FT,offset,float(m.deck_top(a,offset/FT))*FT))
            q=c.Frame.multVec(App.Vector((b-m.start)*FT,offset,float(m.deck_top(b,offset/FT))*FT))
            normal=c.Frame.Rotation.multVec(App.Vector(0,side,0));e=Part.makeLine(p,q)
            # Deck outer face is n=0; place the eight-inch barrier inward.
            prof=[(n-8,z) for n,z in profile]
            solids=[section_sweep(e,normal,prof)];paths=[e]
        shape=join_solids(solids)
        if o.WallProfile:shape=mitre_clip(shape,o.WallProfile)
        if not shape.isNull() and o.TrimSources:
            shape=shape.cut(Part.makeCompound([s.Shape for s in o.TrimSources])).removeSplitter()
        o.Shape=shape;o.Path=Part.makeCompound(paths);o.NetVolume=shape.Volume if not shape.isNull() else 0
        o.MeasuredLength=sum(e.Length for e in paths)

class BackwallSeatProxy(Serializable):
    """Rebuild the authorized backwall seat directly from the landing underside."""
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        c=o.PGL;m=bridge.model(c);r=bridge.support_data(c)[o.SupportID]
        a,b=(r['station']-r['width']/2,r['datum']) if o.SupportID=='EB1' else (r['datum'],r['station']+r['width']/2)
        prism=Part.makeBox((b-a)*FT,c.EndCapLength.Value,20*FT,App.Vector((a-m.start)*FT,-c.EndCapLength.Value/2,r['top']*FT))
        prism.Placement=c.Frame
        cfg=dt.settings(o.SeatingSurface.DrainageTrial,o.SeatingSurface.TrialSide)
        top=dt.landing_face(cfg,xmin=prism.BoundBox.XMin-IN,xmax=prism.BoundBox.XMax+IN)
        top.translate(App.Vector(0,0,-o.SeatingInputs.SlabThickness.Value))
        envelope=top.extrude(App.Vector(0,0,-20*FT))
        o.Shape=envelope.common(prism).removeSplitter();o.NetVolume=o.Shape.Volume
        o.Label=o.SupportID+' backwall - seat follows landing underside'

class SlopeProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        rows=[];passes=[]
        for side in 'AB':
            b=dt.settings(o.Document.DrainageTrial,side);face=o.Document.getObject(dt.UPPER[side]+'Surface').Shape.Faces[0]
            delta=lambda t:dt.landing_height(b,b['join'],b['near']+(b['turn']-b['near'])*t)-dt.plane(b,b['join'],b['near']+(b['turn']-b['near'])*t)
            ts=np.array([0.,1/3,2/3,1.]);poly=np.polynomial.Polynomial.fit(ts,[delta(t) for t in ts],3).convert()
            crit=[0.,1.]+[float(z.real) for z in poly.deriv().roots() if abs(z.imag)<1e-8 and 0<z.real<1]
            exact=100*(b['grade']+max(0,max(delta(t) for t in crit))/((1-b.get('taper',.1))*b['blend']))
            native=max(100*face.normalAt(u,v).x/face.normalAt(u,v).z for u in [0,1,1.5,2,2.5,3,4] for v in crit+[1.,1.5,2.])
            ok=exact<=5. and abs(native-exact)<1e-8
            rows.append({'side':side,'centerline_percent':100*b['grade'],'maximum_longitudinal_percent':native,'analytic_maximum_percent':exact,'limit_percent':5.,'status':'PASS' if ok else 'FAIL','run_ft':(b['end']-b['join'])/FT,'blend_ft':b['blend']/FT})
            passes.append(ok)
        # Retained planar descending runs, excluding landings.
        for name,axis in [('A_ApproachSurface','x'),('B_ApproachSurface','y'),('B_LowerRunSurface','x'),('B_MiddleRunSurface','x')]:
            f=o.Document.getObject(name).Shape;n=f.Faces[0].normalAt(0,0) if f.Faces else None
            if n is None:
                slab=o.Document.getObject(name[:-7]+'Slab');f=max([x for x in slab.Shape.Faces if abs(x.normalAt(0,0).z)>.5],key=lambda x:x.CenterOfMass.z);n=f.normalAt(0,0)
            g=abs(100*getattr(n,axis)/n.z)
            # Machine roundoff only; no engineering allowance above five.
            ok=g<=5+1e-10;passes.append(ok);rows.append({'surface':name,'maximum_longitudinal_percent':g,'status':'PASS' if ok else 'FAIL'})
        o.Status='PASS' if all(passes) else 'FAIL';o.MeasuredSlopes=[json.dumps(r) for r in rows]
        o.Label='Main down-ramp slopes <= 5% — '+o.Status

def add_details(doc,barrier_profile):
    group=doc.addObject('App::DocumentObjectGroup','MSECopingsAndBarriers');group.Label='DXF concrete copings and pedestrian barriers'
    objects=[]
    trim=[doc.getObject('BridgeCheek'+s+str(j)) for s in ['EB1','EB2'] for j in [1,2]]
    for w in [o for o in doc.Objects if o.Name.startswith('Wall') and o.Name.endswith('Profile')]:
        if not any(a and b and q.x-p.x>1e-6 for a,b,p,q in zip(w.TopSourceNames,w.TopSourceNames[1:],w.TopControls,w.TopControls[1:])):continue
        for kind in ['Coping','Barrier']:
            o=doc.addObject('Part::FeaturePython',kind+w.Name[4:-7]);o.Label=kind+' — MSE '+w.Name[4:-7]
            for typ,n,v in [('App::PropertyString','Kind',kind),('App::PropertyLink','WallProfile',w),('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyInteger','SpanIndex',0),('App::PropertyInteger','Side',0),('App::PropertyString','ProfileJSON',json.dumps(barrier_profile)),('App::PropertyLinkList','TrimSources',trim),('Part::PropertyPartShape','Path',Part.Shape()),('App::PropertyVolume','NetVolume',0),('App::PropertyLength','MeasuredLength','0 in')]:prop(o,typ,n,v,'DXF details')
            DetailProxy(o);group.addObject(o);o.Proxy.execute(o);objects.append(o)
    for i in [0,1]:
        for side in [-1,1]:
            o=doc.addObject('Part::FeaturePython',f'BarrierDeckS{i+1}'+('L' if side<0 else 'R'));o.Label=f'Pedestrian barrier — deck span {i+1} '+('left' if side<0 else 'right')
            for typ,n,v in [('App::PropertyString','Kind','Barrier'),('App::PropertyLink','WallProfile',None),('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyInteger','SpanIndex',i),('App::PropertyInteger','Side',side),('App::PropertyString','ProfileJSON',json.dumps(barrier_profile)),('App::PropertyLinkList','TrimSources',[]),('Part::PropertyPartShape','Path',Part.Shape()),('App::PropertyVolume','NetVolume',0),('App::PropertyLength','MeasuredLength','0 in')]:prop(o,typ,n,v,'DXF details')
            DetailProxy(o);group.addObject(o);o.Proxy.execute(o);objects.append(o)
    return objects

class JointEnvelopeProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        c=o.PGL;parts=[]
        for cheek in o.Sources:
            b=bridge.local_shape(cheek).BoundBox;cap=bridge.local_shape(cheek.Document.getObject('BridgeCap'+cheek.SupportID)).BoundBox;gap=c.MSEJointGap.Value
            # Separate the web and outside lug envelopes so the MSE panel can
            # occupy the inside recess instead of being cut to the lug's tip.
            ymin=b.YMin-6*IN-gap if cheek.BeamIndex==1 else b.YMin-gap
            ymax=b.YMax+6*IN+gap if cheek.BeamIndex==0 else b.YMax+gap
            web=Part.makeBox(cap.XLength+2*gap,ymax-ymin,b.ZMax-cap.ZMin+60*IN+gap,App.Vector(cap.XMin-gap,ymin,cap.ZMin-gap))
            sideletter='A' if cheek.SupportID=='EB1' else 'B'
            panel=o.Document.getObject('Wall'+sideletter+('6' if cheek.BeamIndex==0 else '7')+'Profile')
            edge=panel.Start.x;extent=1e6
            halfspace=Part.makeBox(extent,2*extent,2*extent,App.Vector(edge-extent if cheek.BeamIndex==0 else edge,-extent,-extent))
            halfspace.Placement=c.Frame.inverse()
            parts.append(web.common(halfspace))
            ly=b.YMin if cheek.BeamIndex==0 else b.YMax-c.MSELugWidth.Value
            rear=cap.XMin-c.MSELugProjection.Value if cheek.SupportID=='EB1' else cap.XMax
            parts.append(Part.makeBox(c.MSELugProjection.Value+2*gap,c.MSELugWidth.Value+2*gap,b.ZLength+60*IN+2*gap,App.Vector(rear-gap,ly-gap,b.ZMin-gap)))
            parts.append(Part.makeBox(cap.XLength+2*gap,c.MSELugWidth.Value+2*gap,c.MSELugProjection.Value+2*gap,App.Vector(cap.XMin-gap,ly-gap,b.ZMin-gap)))
        o.Shape=Part.makeCompound(parts);o.Placement=c.Frame

def trim_end_interfaces(doc,details):
    tool=doc.addObject('Part::FeaturePython','MSEEndBentJointEnvelope')
    prop(tool,'App::PropertyLink','PGL',doc.BridgePGL)
    prop(tool,'App::PropertyLinkList','Sources',[doc.getObject('BridgeCheek'+s+str(j)) for s in ['EB1','EB2'] for j in [1,2]])
    JointEnvelopeProxy(tool);tool.Proxy.execute(tool)
    group=doc.addObject('App::DocumentObjectGroup','MSEInterfaceSources');group.Label='Native detail sources and half-inch joint envelopes'
    group.addObject(tool)
    replacements={};finished=list(doc.MSEAssembly.FinishedConcrete)
    for old in finished+details:
        if not old.Shape.BoundBox.intersect(tool.Shape.BoundBox):continue
        if old.Shape.common(tool.Shape).Volume<=1e-6:continue
        cut=doc.addObject('Part::Cut',old.Name+'BentJoint');cut.Base=old;cut.Tool=tool;cut.Refine=True;cut.Label=old.Label+' — end-bent joint'
        for parent in list(old.InList):
            if parent.TypeId=='App::DocumentObjectGroup':parent.removeObject(old);parent.addObject(cut)
        group.addObject(old);replacements[old.Name]=cut
    doc.MSEAssembly.FinishedConcrete=[replacements.get(o.Name,o) for o in finished]
    doc.BridgeGeometryChecks.ExistingConcrete=list(doc.MSEAssembly.FinishedConcrete)
    doc.MSESlopeChecks.Slabs=[replacements.get(o.Name,o) for o in doc.MSESlopeChecks.Slabs]
    routes=json.loads(doc.DrainageTrial.TraceRoutes)
    for rows in routes.values():
        for row in rows:
            if row['slab'] in replacements:row['slab']=replacements[row['slab']].Name
    doc.DrainageTrial.TraceRoutes=json.dumps(routes)
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' not in o.PropertiesList:continue
        specs=json.loads(o.PointDefinitions)
        for spec in specs:
            if spec['source'] in replacements:spec['source']=replacements[spec['source']].Name
        o.PointDefinitions=json.dumps(specs);o.Sources=[replacements.get(s.Name,s) for s in o.Sources]
    for o in doc.Objects:o.purgeTouched()
    cuts=list(replacements.values())
    for o in cuts:o.touch()
    doc.recompute(cuts)
    return replacements,tool

def add_detail_annotations(doc,details,replacements):
    made=[]
    for index,base in enumerate(details,1):
        host=replacements.get(base.Name,base)
        if host.Shape.isNull() or host.Shape.Volume<=0:continue
        direction=base.WallProfile.Tangent if base.WallProfile else base.PGL.Frame.Rotation.multVec(App.Vector(1,0,0))
        normal=base.WallProfile.Normal if base.WallProfile else base.PGL.Frame.Rotation.multVec(App.Vector(0,base.Side,0))
        for end in [0,1]:
            name=f'DXFDetailElevation{index:02d}{end}'
            o=doc.addObject('App::FeaturePython',name);dt.ElevationProxy(o)
            spec={'kind':'detail','source':host.Name,'direction':list(direction),'end':end}
            for typ,n,v in [('App::PropertyString','PointDefinitions',json.dumps([spec])),('App::PropertyString','PointID',host.Name+('-START' if end==0 else '-END')),('App::PropertyLinkList','Sources',[host]),('App::PropertyVector','MeasuredPoint',App.Vector()),('App::PropertyLength','Elevation','0 ft'),('App::PropertyVector','TextOffset',normal*(3*FT)+direction*((-1 if end==0 else 1)*2*FT)+App.Vector(0,0,IN*6))]:setprop(o,typ,n,v,'Elevation annotation')
            o.Label=o.PointID+' top elevation';doc.SlabElevations.addObject(o);o.Proxy.execute(o)
            lead=doc.addObject('Part::FeaturePython',name+'Leader');prop(lead,'App::PropertyLink','Annotation',o);dt.LeaderProxy(lead);lead.Proxy.execute(lead);doc.SlabElevations.addObject(lead)
            made.append(o)
    return made

def ruled_profile_solid(a,b):
    """Solid between corresponding vertical section rings, including taper to zero."""
    def ring_area(r):return sum((p-r[0]).cross(q-r[0]).Length for p,q in zip(r[1:],r[2:]))
    if ring_area(a)>1e-7 and ring_area(b)>1e-7:
        solid=Part.makeLoft([closed_face(a).OuterWire,closed_face(b).OuterWire],True,True)
        if not solid.isValid() or not solid.isClosed() or len(solid.Solids)!=1:raise ValueError('Invalid return loft')
        return solid
    faces=[]
    def triangle(p,q,r):
        if (q-p).cross(r-p).Length>1e-7:faces.append(closed_face([p,q,r]))
    for ring in [a,list(reversed(b))]:
        unique=[]
        for p in ring:
            if not any(p.distanceToPoint(q)<1e-7 for q in unique):unique.append(p)
        if len(unique)>=3:
            # The barrier section is concave; a triangle fan would fill the
            # shoulder recesses and create intersecting cap faces.
            faces.append(closed_face(unique))
    for i in range(len(a)):
        j=(i+1)%len(a);triangle(a[i],b[i],b[j]);triangle(a[i],b[j],a[j])
    solid=Part.makeSolid(Part.makeShell(faces))
    if solid.Volume<0:solid.reverse()
    if not solid.isValid() or len(solid.Solids)!=1:raise ValueError('Invalid return transition solid')
    return solid

class ReturnProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        c=o.PGL;frame=c.Frame;inv=frame.inverse();q=1 if o.SupportID=='EB1' else -1;side=o.Side
        wall=o.WallBarrier.WallProfile
        edges,_=top_edges(wall,True)
        ends=[(inv.multVec(e.valueAt(t)),e,t) for e in edges for t in [e.FirstParameter,e.LastParameter]]
        end,e,t=(max(ends,key=lambda x:x[0].x) if q==1 else min(ends,key=lambda x:x[0].x))
        cap=bridge.local_shape(o.Document.getObject('BridgeCap'+o.SupportID)).BoundBox
        bound=cap.XMin-c.MSEJointGap.Value if q==1 else cap.XMax+c.MSEJointGap.Value
        if q*(end.x-bound)>0:
            lo,hi=e.FirstParameter,e.LastParameter
            increasing=inv.multVec(e.valueAt(hi)).x>inv.multVec(e.valueAt(lo)).x
            for _ in range(70):
                mid=(lo+hi)/2;xx=inv.multVec(e.valueAt(mid)).x
                if (xx<bound)==increasing:lo=mid
                else:hi=mid
            end=inv.multVec(e.valueAt((lo+hi)/2))
        m=bridge.model(c);r=bridge.support_data(c)[o.SupportID];datum=(r['datum']-m.start)*FT
        inner=side*(c.DeckWidth.Value/2-8*IN)
        p0=App.Vector(datum,inner,float(m.deck_top(r['datum'],side*c.DeckWidth.Value/2/FT))*FT)
        p1=App.Vector(datum-q*8.25*IN,inner,0)
        p2=App.Vector(datum-q*8.25*IN,end.y,0)
        p3=App.Vector(end);p3.z+=9*IN
        for p,up in [(p1,0),(p2,9*IN)]:
            world=frame.multVec(p);p.z=mse.height(o.LandingSurface,world.x,world.y)+up
        points=[p0,p1,p2,p3]
        # User correction: keep each complete return level at its coping end.
        # The deck rail may be at a different elevation across its joint.
        for p in points:p.z=p3.z
        normals=[App.Vector(0,side,0),App.Vector(q,side,0),App.Vector(q,side,0),inv.Rotation.multVec(wall.Normal)]
        if o.Kind=='Barrier':
            profile=json.loads(o.WallBarrier.ProfileJSON)
            rings=[[p+n*(x*IN)+App.Vector(0,0,z*IN) for x,z in profile] for p,n in zip(points,normals)]
            solids=[ruled_profile_solid(a,b) for a,b in zip(rings,rings[1:])]
        else:
            # Level plinth top; its underside conforms to the walking surface.
            rings=[]
            for i in [0,1,2,3]:
                p=points[i];n=normals[i]
                outer=p+n*8*IN;bottom=[]
                for v in [outer,p]:
                    world=frame.multVec(v)
                    bottom.append(App.Vector(v.x,v.y,mse.height(o.LandingSurface,world.x,world.y)-.1*IN))
                rings.append([p,outer]+bottom)
            solids=[ruled_profile_solid(a,b) for a,b in zip(rings,rings[1:])]
        shape=join_solids(solids)
        # Retain the exact source slab; conform only the added detail underside.
        shape.Placement=frame
        shape=shape.cut(o.LandingSlab.Shape).removeSplitter()
        o.Shape=shape;o.NetVolume=o.Shape.Volume
        path=Part.makePolygon(points);path.transformShape(frame.toMatrix());o.Path=path
        o.MeasuredLength=path.Length
        setprop(o,'App::PropertyString','ConnectionBasis','User correction: level square return at coping elevation; step to lower deck rail accepted; existing 3 in deck joint retained.')

def add_square_returns(doc):
    objects=[]
    for sid,sideletter,wallnames in [('EB1','A',['A6','A7']),('EB2','B',['B6','B7'])]:
        for side,wallname in zip([-1,1],wallnames):
            barrier=doc.getObject('Barrier'+wallname)
            for kind in ['ReturnPlinth','Barrier']:
                name=('Plinth' if kind=='ReturnPlinth' else 'Barrier')+'Return'+sid+('L' if side<0 else 'R')
                o=doc.addObject('Part::FeaturePython',name);o.Label=sid+' '+('left' if side<0 else 'right')+' square return '+kind.lower()
                for typ,n,v in [('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyLink','WallBarrier',barrier),('App::PropertyLink','LandingSurface',doc.getObject(sideletter+'_BridgeLandingSurface')),('App::PropertyLink','LandingSlab',dt.slab_map(doc)[sideletter+'_BridgeLandingSlab']),('App::PropertyString','SupportID',sid),('App::PropertyInteger','Side',side),('App::PropertyString','Kind',kind),('Part::PropertyPartShape','Path',Part.Shape()),('App::PropertyVolume','NetVolume',0),('App::PropertyLength','MeasuredLength','0 in')]:prop(o,typ,n,v,'Square barrier returns')
                ReturnProxy(o);o.Proxy.execute(o);doc.MSECopingsAndBarriers.addObject(o);objects.append(o)
    return objects

def finished_detail(doc,raw):
    if 'FinalDetailMapJSON' in doc.MSECopingsAndBarriers.PropertiesList:
        name=json.loads(doc.MSECopingsAndBarriers.FinalDetailMapJSON).get(raw.Name)
        if name:return doc.getObject(name)
    return doc.getObject(raw.Name+'BentJoint') or raw

def coordinate_details(doc):
    """Native linked cuts partition corner material and conform to walking slabs."""
    raw=[o for o in doc.Objects if isinstance(getattr(o,'Proxy',None),(DetailProxy,ReturnProxy))]
    walking=list(doc.MSESlopeChecks.Slabs)+[doc.BridgeDeckS1,doc.BridgeDeckS2]
    sources=doc.addObject('App::DocumentObjectGroup','MSEDetailSources');sources.Label='Editable detail sources and contact tools'
    finished=[];mapping={};replacements={};rows=[]
    for base in raw:
        old=doc.getObject(base.Name+'BentJoint') or base
        tools=[]
        for prior in walking+finished:
            if old.Shape.BoundBox.intersect(prior.Shape.BoundBox) and old.Shape.common(prior.Shape).Volume>1e-7:tools.append(prior)
        if tools:
            tool=doc.addObject('Part::Compound',base.Name+'ContactTools');tool.Links=tools;sources.addObject(tool)
            tool.Shape=Part.makeCompound([o.Shape for o in tools])
            final=doc.addObject('Part::Cut',base.Name+'Coordinated');final.Base=old;final.Tool=tool;final.Refine=True;final.Label=old.Label+' - coordinated contacts'
            for o in doc.Objects:o.purgeTouched()
            tool.touch();final.touch();doc.recompute([tool,final])
            for parent in list(old.InList):
                if parent.TypeId=='App::DocumentObjectGroup':parent.removeObject(old)
            sources.addObject(old);doc.MSECopingsAndBarriers.addObject(final);replacements[old.Name]=final
            if final.Shape.isNull() or not final.Shape.isValid() or final.Shape.Volume<=0:raise ValueError('Invalid coordinated detail '+base.Name)
            rows.append({'detail':base.Name,'finished':final.Name,'removed_in3':(old.Shape.Volume-final.Shape.Volume)/IN**3,'tools':[o.Name for o in tools]})
        else:final=old
        mapping[base.Name]=final.Name;finished.append(final)
    setprop(doc.MSECopingsAndBarriers,'App::PropertyString','FinalDetailMapJSON',json.dumps(mapping))
    setprop(doc.MSECopingsAndBarriers,'App::PropertyLinkList','FinishedDetails',finished)
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' not in o.PropertiesList:continue
        specs=json.loads(o.PointDefinitions)
        for spec in specs:
            if spec['source'] in replacements:spec['source']=replacements[spec['source']].Name
        o.PointDefinitions=json.dumps(specs);o.Sources=[replacements.get(p.Name,p) for p in o.Sources]
        o.Proxy.execute(o)
    for o in doc.SlabElevations.Group:
        if 'Annotation' in o.PropertiesList:o.Proxy.execute(o)
    for o in doc.Objects:o.purgeTouched()
    return rows

class ContactPartitionProxy:
    """Source-linked exact Boolean for coplanar contact seams."""
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        # Copies avoid shared topology/tolerance mutation in the native Cut
        # implementation. Zero additional fuzzy tolerance matches the audited
        # exact-shape Boolean and retains the full source precision.
        shape=obj.Base.Shape.copy().cut(obj.Tool.Shape.copy(),0.0).removeSplitter()
        if shape.isNull() or not shape.isValid() or shape.Volume<=0:raise ValueError('Invalid contact partition '+obj.Name)
        obj.Shape=shape

def refine_contact_partitions(doc,pairs):
    """Resolve residual compound-tool seams with direct native linked cuts."""
    mapping=json.loads(doc.MSECopingsAndBarriers.FinalDetailMapJSON);replacements={};rows=[]
    for base_name,tool_name in pairs:
        base=doc.getObject(base_name);old=finished_detail(doc,base);tool=doc.getObject(tool_name)
        final=doc.addObject('Part::FeaturePython',base_name+'ContactFinal')
        setprop(final,'App::PropertyLink','Base',old);setprop(final,'App::PropertyLink','Tool',tool);ContactPartitionProxy(final)
        final.Label=base.Label+' - finished contact'
        for o in doc.Objects:o.purgeTouched()
        final.Proxy.execute(final)
        if final.Shape.isNull() or not final.Shape.isValid() or final.Shape.Volume<=0:raise ValueError('Invalid direct contact cut '+base_name)
        residual=final.Shape.common(tool.Shape).Volume/IN**3
        if residual>1e-7:raise ValueError('Unresolved direct contact '+base_name+': '+str(residual))
        for parent in list(old.InList):
            if parent.TypeId=='App::DocumentObjectGroup':parent.removeObject(old)
        doc.MSEDetailSources.addObject(old);doc.MSECopingsAndBarriers.addObject(final)
        mapping[base_name]=final.Name;replacements[old.Name]=final
        rows.append({'base':base_name,'tool':tool_name,'final':final.Name,'residual_in3':residual})
    doc.MSECopingsAndBarriers.FinalDetailMapJSON=json.dumps(mapping)
    doc.MSECopingsAndBarriers.FinishedDetails=[doc.getObject(n) for n in mapping.values()]
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' not in o.PropertiesList:continue
        specs=json.loads(o.PointDefinitions)
        for spec in specs:
            if spec['source'] in replacements:spec['source']=replacements[spec['source']].Name
        o.PointDefinitions=json.dumps(specs);o.Sources=[replacements.get(p.Name,p) for p in o.Sources];o.Proxy.execute(o)
    for o in doc.SlabElevations.Group:
        if 'Annotation' in o.PropertiesList:o.Proxy.execute(o)
    for o in doc.Objects:o.purgeTouched()
    return rows
