"""Reversible drainage alternative in a native document copy; never saves models."""
import json,math,re,traceback
from datetime import datetime,timezone
import FreeCAD as App
import FreeCADGui as Gui
import Part
import numpy as np
import Draft
from draftobjects.text import Text
from draftviewproviders.view_text import ViewProviderText
from . import mse,bridge,ramp_trace
from .geometry import length,result
ROOT=bridge.ROOT;FT=bridge.FT;IN=bridge.IN
UPPER={'A':'A_ReturnRun','B':'B_UpperRun'}
LAND={'A':'A_BridgeLanding','B':'B_BridgeLanding'}
MODIFIED=set(UPPER.values())|set(LAND.values())

def vector(p):return App.Vector(*p)
def xyz(p):return [p.x,p.y,p.z]

def top_at(shape,x,y):
    bb=shape.BoundBox
    ray=Part.makeLine(App.Vector(x,y,bb.ZMin-FT),App.Vector(x,y,bb.ZMax+FT))
    vertices=shape.common(ray).Vertexes
    if not vertices:raise ValueError(f'No physical slab at {x/FT}, {y/FT}')
    return max(v.Point.z for v in vertices)

def settings(c,side):
    b=json.loads(c.BaselineParameters)[side]
    b.setdefault('crossfall',.01)  # Early disposable trials stored the fixed 1% implicitly.
    pgl=c.PGL;m=bridge.model(pgl);station=m.start if side=='A' else m.end
    origin=pgl.Frame.multVec(App.Vector((station-m.start)*FT,0,0))
    transverse=pgl.Frame.Rotation.multVec(App.Vector(0,1,0))
    b.update(q=1 if side=='A' else -1,center=origin.x,front_center=origin.y,
             skew=transverse.y/transverse.x,low=float(m.deck_top(station,m.deck_left))*FT,
             crown=float(m.pgl(station))*FT,halfwidth=m.deck_width*FT/2 if hasattr(m,'deck_width') else pgl.DeckWidth.Value/2,
             slope=mse.grade(c.LandingSlope)/100,blend=getattr(c,side+'RunBlendLength',c.RunBlendLength).Value,
             taper=getattr(c,side+'BlendTaperFraction',.1),
             incoming=abs(m.g1 if side=='A' else m.g2))
    b['halfwidth']*=transverse.x
    b['turn']=(b['run_y0']+b['run_y1'])/2
    b['near']=b['run_y0'] if side=='A' else b['run_y1']
    b['far']=b['run_y1'] if side=='A' else b['run_y0']
    b['grade']=(plane(b,b['join'],b['turn'])-b['right_center'])/(b['end']-b['join'])
    return b

def front(b,x):return b['front_center']+b['skew']*(x-b['center'])
def plane(b,x,y):return b['low']-b['slope']*(x-b['xmin'])-b['crossfall']*b['q']*(y-front(b,b['xmin']))

def entry(b,x):
    return b['crown']-(b['crown']-b['low'])*min(1.,abs(x-b['center'])/b['halfwidth'])

def landing_height(b,x,y):
    # Cubic Hermite interpolation: incoming deck longitudinal tangent, and
    # single-plane 1% tangent at the PGL turn. No crown remains beyond the turn.
    total=b['q']*(b['turn']-front(b,x));d=b['q']*(y-front(b,x));t=d/total
    if t>=1:return plane(b,x,y)
    z0=entry(b,x);z1=plane(b,x,b['turn'])
    return ((2*t**3-3*t*t+1)*z0+(t**3-2*t*t+t)*(-b['incoming']*total)
            +(-2*t**3+3*t*t)*z1+(t**3-t*t)*(-b['crossfall']*total))

def upper_height(b,x,y):
    base=plane(b,b['join'],y)-b['grade']*(x-b['join'])
    s=(x-b['join'])/b['blend']
    if s>=1 or b['q']*(y-b['turn'])>=0:return base
    # A C1 quadratic/linear/quadratic fade limits the peak added grade.
    # Its derivative is bounded by 1/(0.9*blend), unlike a cubic smoothstep's
    # 1.5/blend peak. Long blending preserves a shallower-than-5% run at edges.
    a=b.get('taper',.1)
    if not 0<a<.5:raise ValueError('Blend taper fraction must be between zero and one half')
    weight=(1-s*s/(2*a*(1-a)) if s<a else (1-(s-a/2)/(1-a) if s<1-a else (1-s)**2/(2*a*(1-a))))
    return base+weight*(landing_height(b,b['join'],y)-plane(b,b['join'],y))

def surface_height(o,x,y):
    b=settings(o.DrainageTrial,o.TrialSide)
    return (landing_height if o.TrialRole=='Landing' else upper_height)(b,x,y)

def landing_face(b,xmin=None,xmax=None):
    xs=[b['xmin'] if xmin is None else xmin,b['center']-b['halfwidth'],b['center'],b['center']+b['halfwidth'],b['join'] if xmax is None else xmax]
    poles=[]
    for x in xs:
        y0=front(b,x);dy=b['turn']-y0;dy2=b['far']-b['turn'];total=abs(dy)
        z0=entry(b,x);z1=plane(b,x,b['turn']);z2=plane(b,x,b['far'])
        poles.append([App.Vector(x,y0,z0),App.Vector(x,y0+dy/3,z0-b['incoming']*total/3),
            App.Vector(x,b['turn']-dy/3,z1+b['crossfall']*total/3),App.Vector(x,b['turn'],z1),
            App.Vector(x,b['turn']+dy2/3,z1+(z2-z1)/3),App.Vector(x,b['turn']+2*dy2/3,z1+2*(z2-z1)/3),App.Vector(x,b['far'],z2)])
    surf=Part.BSplineSurface()
    surf.buildFromPolesMultsKnots(poles,[2,1,1,1,2],[4,3,4],xs,[0.,1.,2.],False,False,1,3)
    return surf.toShape()

def upper_face(b):
    # Exact bicubic patches. The blend is cubic in x and cubic in y;
    # conversion from polynomial samples to Bernstein poles is exact.
    nodes=np.array([0.,1/3,2/3,1.])
    bern=np.array([[(1-t)**3,3*t*(1-t)**2,3*t*t*(1-t),t**3] for t in nodes])
    inv=np.linalg.inv(bern)
    a=b.get('taper',.1)
    xs=[b['join'],b['join']+a*b['blend'],b['join']+(1-a)*b['blend'],b['join']+b['blend'],b['end']];ys=[b['near'],b['turn'],b['far']]
    if not all(x<y for x,y in zip(xs,xs[1:])):raise ValueError('Blend must fit strictly within the descending run')
    poles=[[None]*7 for _ in range(13)]
    for ix in range(4):
        for iy in range(2):
            xx=[xs[ix]+t*(xs[ix+1]-xs[ix]) for t in nodes]
            yy=[ys[iy]+t*(ys[iy+1]-ys[iy]) for t in nodes]
            values=np.array([[upper_height(b,x,y) for y in yy] for x in xx])
            z=inv@values@inv.T
            for i in range(4):
                for j in range(4):poles[3*ix+i][3*iy+j]=App.Vector(xx[i],yy[j],float(z[i,j]))
    surf=Part.BSplineSurface()
    surf.buildFromPolesMultsKnots(poles,[4,3,3,3,4],[4,3,4],[0.,1.,2.,3.,4.],[0.,1.,2.],False,False,3,3)
    return surf.toShape()

class ControlProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        for side in ['A','B']:
            b=settings(o,side)
            setattr(o,side+'UpperGradePercent',-100*b['grade'])
            setattr(o,side+'TieInElevation',plane(b,b['join'],b['turn']))

class SurfaceProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    surface_height=staticmethod(surface_height)
    def execute(self,o):
        b=settings(o.DrainageTrial,o.TrialSide)
        o.Shape=landing_face(b) if o.TrialRole=='Landing' else upper_face(b)
        if o.TrialRole=='Landing':xy=[(b['xmin'],front(b,b['xmin'])),(b['join'],front(b,b['join'])),(b['join'],b['far']),(b['xmin'],b['far'])]
        else:xy=[(b['join'],b['run_y0']),(b['end'],b['run_y0']),(b['end'],b['run_y1']),(b['join'],b['run_y1'])]
        o.PlanCorners=[App.Vector(x,y,0) for x,y in xy]
        o.ComputedCorners=[App.Vector(x,y,surface_height(o,x,y)) for x,y in xy]

class FillProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        top=o.Surface.Shape.copy();top.translate(App.Vector(0,0,-o.Inputs.SlabThickness.Value))
        raw=top.extrude(App.Vector(0,0,-200*FT))
        bb=raw.BoundBox
        box=Part.makeBox(bb.XLength+2*FT,bb.YLength+2*FT,200*FT,App.Vector(bb.XMin-FT,bb.YMin-FT,o.BaseElevation.Value))
        raw=raw.common(box)
        tools=[v.Shape for v in o.ConcreteSources if raw.BoundBox.intersect(v.Shape.BoundBox)]
        o.Shape=raw.cut(Part.makeCompound(tools)).removeSplitter() if tools else raw
        o.EnvelopeVolume=raw.Volume;o.RemovedConcreteVolume=raw.Volume-o.Shape.Volume

def parameter_curve(surface,p,q):
    # All stored route legs are axis aligned except the bridge plan extension.
    # Exact cubic interpolation per polynomial interval represents these
    # height functions; the tiny skew on the PGL leg is fitted adaptively.
    def val(t):
        x=p.x+(q.x-p.x)*t;y=p.y+(q.y-p.y)*t
        return App.Vector(x,y,mse.height(surface,x,y))
    def part(a,b,depth=0):
        pts=[val(a+(b-a)*t) for t in [0.,1/3,2/3,1.]]
        mat=np.array([[1,0,0,0],[8/27,12/27,6/27,1/27],[1/27,6/27,12/27,8/27],[0,0,0,1]])
        poles=np.linalg.solve(mat,np.array([xyz(v) for v in pts]))
        curve=Part.BezierCurve();curve.setPoles([vector(row) for row in poles])
        error=max(curve.value(t).distanceToPoint(val(a+(b-a)*t)) for t in [.125,.25,.5,.75,.875])
        if error>length('0.00001 in'):
            if depth>=15:raise ValueError('Trace approximation exceeded depth')
            return part(a,(a+b)/2,depth+1)+part((a+b)/2,b,depth+1)
        return [curve.toShape()]
    cuts=[0.,1.]
    if 'DrainageTrial' in surface.PropertiesList:
        b=settings(surface.DrainageTrial,surface.TrialSide)
        a=b.get('taper',.1)
        for coordinate,value in [('y',b['turn'])]+[('x',b['join']+f*b['blend']) for f in [a,1-a,1.]]:
            a=getattr(p,coordinate);d=getattr(q,coordinate)-a
            if abs(d)>1e-10:
                t=(value-a)/d
                if 0<t<1:cuts.append(t)
    cuts=sorted(set(cuts));edges=[]
    for a,b in zip(cuts,cuts[1:]):edges.extend(part(a,b))
    return edges

class TraceProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        cfg=json.loads(o.DrainageTrial.TraceRoutes);wires={};grades=[];slabs=[]
        for side,rows in cfg.items():
            edges=[]
            for r in rows:
                s=o.Document.getObject(r['surface']);p,q=vector(r['start']),vector(r['end'])
                if r.get('bridge_end'):
                    b=settings(o.DrainageTrial,side);q.y=front(b,q.x)
                    if getattr(o,'AlignBridgeEndpoints',False):
                        vertices=sorted([v.Point for v in o.PGL.Shape.Vertexes],key=lambda p:o.PGL.Frame.inverse().multVec(p).x)
                        q=vertices[0 if side=='A' else -1]
                es=parameter_curve(s,p,q);edges.extend(es)
                for e in es:
                    a,z=[v.Point for v in e.Vertexes];grades.append(100*(z.z-a.z)/math.hypot(z.x-a.x,z.y-a.y));slabs.append(r['slab'])
            wires[side]=Part.Wire(edges)
        o.Shape=Part.makeCompound([wires['A'],o.PGL.Shape.copy(),wires['B']])
        o.RampALength=wires['A'].Length;o.RampBLength=wires['B'].Length
        o.SegmentSlabs=slabs;o.SegmentGradesPercent=grades
        o.BridgeTieIns=[('Adopted: ' if getattr(o,'AlignBridgeEndpoints',False) else 'Trial: ')+'crowned landing entry matches FFBW profile; physical deck retains 3 in joint.']

def slab_map(doc):return {a.Name:b for a,b in zip(doc.MSEAssembly.NominalConcrete,doc.MSEAssembly.FinishedConcrete)}

def point_from_spec(doc,spec):
    kind=spec['kind']
    if kind=='wall_under_cheek':
        w=doc.getObject(spec['profile']);controls=[p for p,n in zip(w.TopControls,w.TopSourceNames) if not n]
        station=(min(p.x for p in controls)+max(p.x for p in controls))/2
        p=w.Start+w.Tangent*station+w.Normal*(w.Inputs.WallThickness.Value/2)
        p.z=top_at(doc.getObject(spec['source']).Shape.copy(),p.x,p.y)
        return p
    if kind in ['detail_reference','return_top']:
        if kind=='return_top':
            raw=doc.getObject(spec['nominal']);target=raw.Path.Vertexes[0 if spec['end']==0 else -1].Point
            normal=raw.PGL.Frame.Rotation.multVec(App.Vector(0,raw.Side,0)) if spec['end']==0 else raw.WallBarrier.WallProfile.Normal
            target=target+normal*(4*25.4)+App.Vector(0,0,42*25.4)
        else:
            reference=dict(spec,kind='detail',source=spec['nominal'])
            target=point_from_spec(doc,reference)
        host=doc.getObject(spec['source'])
        tops=[f for f in host.Shape.Faces if f.normalAt(sum(f.ParameterRange[:2])/2,sum(f.ParameterRange[2:])/2).z>.5]
        if not tops:raise ValueError('No physical assembled coping top')
        distance,pairs,_=Part.Vertex(target).distToShape(Part.makeCompound(tops))
        if distance>25.4:raise ValueError('Coping corner reference moved over one inch from its physical host')
        return pairs[0][1]
    if kind=='detail':
        host=doc.getObject(spec['source']);direction=App.Vector(*spec['direction'])
        tops=[f for f in host.Shape.Faces if f.normalAt(sum(f.ParameterRange[:2])/2,sum(f.ParameterRange[2:])/2).z>.5]
        points=[v.Point for f in tops for v in f.Vertexes]
        if not points:raise ValueError('No detail top face')
        extent=(min if spec['end']==0 else max)(p.dot(direction) for p in points)
        return max([p for p in points if abs(p.dot(direction)-extent)<.0254],key=lambda p:p.z)
    if kind=='corner':
        s=doc.getObject(spec['surface']);p=s.ComputedCorners[spec['index']]
        host=doc.getObject(spec['source'])
        if host.Name.endswith('BentJoint'):
            # A joint cut creates a notched boundary. Keep this original
            # corner callout on the nearest physical upper-face corner.
            tops=[f for f in host.Shape.Faces if f.normalAt(sum(f.ParameterRange[:2])/2,sum(f.ParameterRange[2:])/2).z>.5]
            corners=[v.Point for f in tops for v in f.Vertexes]
            if not corners:raise ValueError('No upper-face corners on jointed slab')
            return min(corners,key=lambda q:q.distanceToPoint(p))
        return App.Vector(p.x,p.y,top_at(doc.getObject(spec['source']).Shape.copy(),p.x,p.y))
    if kind=='deck':
        c=doc.BridgePGL;m=bridge.model(c);station=bridge.deck_limits(c,spec['span'])[spec['end']]
        p=c.Frame.multVec(App.Vector((station-m.start)*FT,spec['offset']*c.DeckWidth.Value/2,0))
    elif kind=='trial':
        b=settings(doc.DrainageTrial,spec['side']);x=b['center'] if spec['location'] in ['entry','mid','turn'] else b['join']+b['blend']
        y=front(b,x) if spec['location']=='entry' else ((front(b,x)+b['turn'])/2 if spec['location']=='mid' else b['turn'])
        p=App.Vector(x,y,0)
    else:p=vector(spec['point'])
    p.z=top_at(doc.getObject(spec['source']).Shape.copy(),p.x,p.y)
    return p

class ElevationProxy(Text):
    def execute(self,o):
        specs=json.loads(o.PointDefinitions);p=point_from_spec(o.Document,specs[0])
        o.MeasuredPoint=p;o.Elevation=p.z
        o.Text=[o.PointID,f'EL {p.z/FT:.3f} ft']
        o.Placement=App.Placement(p+o.TextOffset,App.Rotation())

class LeaderProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        p=o.Annotation.MeasuredPoint;q=o.Annotation.Placement.Base
        o.Shape=Part.makeCompound([Part.Vertex(p),Part.makeLine(p,q)])

def add_annotations(doc):
    group=doc.addObject('App::DocumentObjectGroup','SlabElevations');group.Label='Slab corner and key-point elevations — feet'
    specs=[];count=0
    for rawname,slab in slab_map(doc).items():
        if not rawname.endswith('Slab'):continue
        count+=1;s=doc.getObject(rawname).Base
        for i in range(4):specs.append({'kind':'corner','surface':s.Name,'source':slab.Name,'index':i,'id':f'R{count:02d}-C{i+1}'})
    for span in range(2):
        for end in [0,1]:
            for offset in [-1,0,1]:specs.append({'kind':'deck','source':f'BridgeDeckS{span+1}','span':span,'end':end,'offset':offset,'id':f'D{span+1}-'+('E' if end else 'S')+{-1:'L',0:'CL',1:'R'}[offset]})
    # Every centerline change in direction / slab boundary, plus crown blend
    # midpoints and upper-run blend endpoints, gets an explicit elevation.
    for side,rows in json.loads(doc.DrainageTrial.TraceRoutes).items():
        for i,r in enumerate(rows):
            if r.get('bridge_end'):continue
            specs.append({'kind':'fixed','source':r['slab'],'point':r['end'],'id':f'{side}-P{i+1:02d}'})
        for where in ['entry','mid','turn','fade']:
            name=UPPER[side] if where=='fade' else LAND[side]
            specs.append({'kind':'trial','source':slab_map(doc)[name+'Slab'].Name,'side':side,'location':where,'id':side+'-'+where.upper()})
    points={}
    for spec in specs:
        p=point_from_spec(doc,spec);key=tuple(round(v,5) for v in xyz(p))
        points.setdefault(key,[]).append(spec)
    occupied=[];annotations=[];font=length('8 in')
    for i,specs in enumerate(points.values()):
        point=point_from_spec(doc,specs[0]);pid='/'.join(s['id'] for s in specs)
        o=doc.addObject('App::FeaturePython',f'SlabElevation{i+1:03d}');ElevationProxy(o);ViewProviderText(o.ViewObject)
        mse.prop(o,'App::PropertyLinkList','Sources',list({doc.getObject(s['source']) for s in specs})+[doc.DrainageTrial],'Sources')
        mse.prop(o,'App::PropertyString','PointDefinitions',json.dumps(specs),'Sources')
        mse.prop(o,'App::PropertyString','PointID',pid,'Annotation')
        mse.prop(o,'App::PropertyVector','MeasuredPoint',point,'Measured geometry')
        mse.prop(o,'App::PropertyLength','Elevation','0 ft','Measured geometry')
        mse.prop(o,'App::PropertyVector','TextOffset',App.Vector(),'Annotation')
        o.setEditorMode('MeasuredPoint',1);o.setEditorMode('Elevation',1)
        width=max(len(pid),len(f'EL {point.z/FT:.3f} ft'))*font*.78;height=font*3.
        selected=None
        # Conservative plan text rectangles avoid crowding; leaders remain
        # anchored at actual top vertices, never at displaced text positions.
        for radius in [3,6,10,15,22,30,42,60]:
            for dx,dy in [(1,1),(-1,1),(1,-1),(-1,-1),(0,1),(0,-1),(1,0),(-1,0)]:
                x=point.x+dx*radius*FT-(width if dx<0 else 0);y=point.y+dy*radius*FT
                box=(x,y-height,x+width,y+font)
                if not any(box[0]<b[2] and box[2]>b[0] and box[1]<b[3] and box[3]>b[1] for b in occupied):selected=(x,y,box);break
            if selected:break
        if not selected:raise ValueError('Cannot place elevation label without overlap')
        x,y,box=selected;occupied.append(box);o.TextOffset=App.Vector(x-point.x,y-point.y,length('9 in'))
        o.Label=pid+' | '+', '.join(sorted(set(s['source'] for s in specs)))
        o.ViewObject.FontSize=font;o.ViewObject.DisplayMode='World';o.ViewObject.TextColor=(.1,.12,.22)
        group.addObject(o);o.Proxy.execute(o);annotations.append(o)
        lead=doc.addObject('Part::FeaturePython',f'SlabElevationLeader{i+1:03d}')
        mse.prop(lead,'App::PropertyLink','Annotation',o,'Source');LeaderProxy(lead);bridge.initialize_display(lead)
        lead.ViewObject.LineColor=(.18,.28,.4);lead.ViewObject.LineWidth=1.;lead.ViewObject.PointSize=5.
        group.addObject(lead)
    doc.recompute()
    return annotations

def validate_annotations(doc):
    checks=[];rows=[];coverage=[]
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' not in o.PropertiesList:continue
        specs=json.loads(o.PointDefinitions);p=o.MeasuredPoint
        errors=[point_from_spec(doc,s).distanceToPoint(p) for s in specs]
        checks.append(result(o.Name+'_native_elevation_and_label',max(errors)<=length('0.001 in') and o.Text[1]==f'EL {p.z/FT:.3f} ft' and o.Elevation.Value==p.z,max_point_error_in=max(errors)/IN,expected_text=f'EL {p.z/FT:.3f} ft',actual_text=o.Text[1],elevation_storage_error_mm=o.Elevation.Value-p.z))
        checks.append(result(o.Name+'_rendered',not bridge.display_state(o)['render_bounds_empty']))
        coverage.extend(s for s in specs if s['kind'] in ['corner','deck'])
        rows.append({'id':o.PointID,'sources':[s['source'] for s in specs],'point_ft':[v/FT for v in xyz(p)],'text':o.Text[1]})
    checks.append(result('all_48_ramp_corners_and_12_deck_corner_crown_points',len(coverage)==60,count=len(coverage)))
    return {'checks':checks,'annotations':rows,'annotation_count':len(rows)}

def clash_rows(doc):
    rows=[];concrete=list(doc.MSEAssembly.FinishedConcrete)
    for a in doc.BridgeGeometryChecks.Components:
        if a.ComponentKind=='WallEnvelope':continue
        sa=a.Shape.copy()
        for b in concrete:
            if sa.BoundBox.intersect(b.Shape.BoundBox):
                volume=sa.common(b.Shape.copy()).Volume
                if volume>0:rows.append({'a':a.Name,'b':b.Name,'volume_ft3':volume/FT**3})
    return rows

class BridgeCheckProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        qa=bridge.validate(o.PGL,{c.Name:c for c in o.Components})
        clashes=clash_rows(o.Document)
        o.GeometryStatus='FAIL' if any(c['status']=='FAIL' for c in qa['checks']) else 'PASS'
        o.CoordinationStatus='FAIL' if clashes else 'NOT CONFIGURED — run trial interface audit'
        o.ClashPairs=[r['a']+' / '+r['b'] for r in clashes]
        o.LandingConnections=['Curved landing: audited by drainage_trial.validate; original plane-only connection check is superseded.']
        o.Label='Bridge checks — geometry '+o.GeometryStatus+'; coordination '+o.CoordinationStatus

class SlopeProxy(mse.Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        rows=[];bad=[]
        for slab in o.Slabs:
            raw=next(a for a,b in zip(o.Document.MSEAssembly.NominalConcrete,o.Document.MSEAssembly.FinishedConcrete) if b==slab)
            s=raw.Base
            if 'DrainageTrial' in s.PropertiesList:
                rows.append(s.Name+': TRIAL curved transition; exact field measured in drainage trial audit')
            else:
                face=ramp_trace.top_face(slab);n=face.normalAt(0,0);gx=-100*n.x/n.z;gy=-100*n.y/n.z
                ok=abs(gx-s.GradeX)<1e-7 and abs(gy-s.GradeY)<1e-7
                if not ok:bad.append(s.Name)
                rows.append(f'{s.Name}: {gx:+.8f}% X, {gy:+.8f}% Y — '+('PASS' if ok else 'FAIL'))
        o.MeasuredSlopes=rows;o.Status='FAIL: '+','.join(bad) if bad else 'PLANAR GRADES PASS; FOUR TRIAL SURFACES REQUIRE CURVED AUDIT'
        o.Label='Trial slope checks — see curved surface audit'

def baseline_parameters(doc):
    rows={}
    for side in ['A','B']:
        s=doc.getObject(UPPER[side]+'Surface');land=doc.getObject(LAND[side]+'Surface')
        rows[side]={'xmin':land.XMin.Value,'join':s.XMin.Value,'end':s.XMax.Value,'run_y0':s.YMin.Value,'run_y1':s.YMax.Value,
            'right_center':mse.height(s,s.XMax.Value,(s.YMin.Value+s.YMax.Value)/2),'original_grade':s.GradeX,
            'crossfall':abs(s.GradeY)/100,
            'original_landing_front':land.YMin.Value if side=='A' else land.YMax.Value}
    _,meta,_,_=ramp_trace.routes(doc.CompletePGLTrace);routes={'A':[],'B':[]}
    for r in meta:
        raw=next(a for a,b in zip(doc.MSEAssembly.NominalConcrete,doc.MSEAssembly.FinishedConcrete) if b==r['slab'])
        routes[r['side']].append({'surface':raw.Base.Name,'slab':r['slab'].Name,'start':xyz(r['start']),'end':xyz(r['end'])})
    for side in routes:routes[side][-1]['bridge_end']=True
    return rows,routes

def configure(doc,job):
    rows,routes=baseline_parameters(doc)
    c=doc.addObject('App::FeaturePython','DrainageTrial');c.Label='Drainage trial — entrances held; editable controls'
    mse.prop(c,'App::PropertyLink','PGL',doc.BridgePGL,'Sources')
    mse.prop(c,'App::PropertyString','BaselineParameters',json.dumps(rows),'Sources')
    mse.prop(c,'App::PropertyString','TraceRoutes',json.dumps(routes),'Sources')
    mse.prop(c,'App::PropertyString','LandingSlope',job['landing_slope'],'Drainage')
    mse.prop(c,'App::PropertyLength','RunBlendLength',job['run_blend_length'],'Drainage')
    mse.prop(c,'App::PropertyString','Rollback','Original document '+job['source_document']+' is unchanged. Close this trial without saving to discard.','Review')
    for side in ['A','B']:
        mse.prop(c,'App::PropertyFloat',side+'UpperGradePercent',0,'Measured controls')
        mse.prop(c,'App::PropertyLength',side+'TieInElevation','0 ft','Measured controls')
        c.setEditorMode(side+'UpperGradePercent',1);c.setEditorMode(side+'TieInElevation',1)
    ControlProxy(c);doc.recompute([c])
    for side in ['A','B']:
        upper=doc.getObject(UPPER[side]+'Surface')
        upper.setExpression('GradeX','DrainageTrial.'+side+'UpperGradePercent')
        for role,name in [('Landing',LAND[side]),('UpperRun',UPPER[side])]:
            s=doc.getObject(name+'Surface')
            mse.prop(s,'App::PropertyLink','DrainageTrial',c,'Trial sources')
            mse.prop(s,'App::PropertyString','TrialSide',side,'Trial sources')
            mse.prop(s,'App::PropertyString','TrialRole',role,'Trial sources')
            SurfaceProxy(s);s.touch()
            FillProxy(doc.getObject(name+'Fill'));doc.getObject(name+'Fill').touch()
    mse.prop(doc.CompletePGLTrace,'App::PropertyLink','DrainageTrial',c,'Sources')
    TraceProxy(doc.CompletePGLTrace)
    doc.CompletePGLTrace.RoutingBasis='Trial curved surfaces; exact polynomial segments except tiny plan skew fitted within 0.00001 in.'
    BridgeCheckProxy(doc.BridgeGeometryChecks);SlopeProxy(doc.MSESlopeChecks)
    doc.recompute()
    for name in MODIFIED:
        raw=doc.getObject(name+'Slab');finished=slab_map(doc)[raw.Name]
        side=name[0]
        finished.Label=name.replace('_',' ')+' — TRIAL '+(f'{-settings(c,side)["grade"]*100:.6f}% PGL; variable crossfall' if name==UPPER[side] else 'crown to 1% plane')
        mse.color(finished,(.42,.78,.85))
    doc.recompute()
    return c

def validate(doc,tolerance='0.001 in'):
    tol=length(tolerance,True);checks=[];field=[];ties=[];mapping=slab_map(doc)
    for rawname,slab in mapping.items():
        if not rawname.endswith('Slab'):continue
        raw=doc.getObject(rawname);s=raw.Base;shape=slab.Shape.copy()
        checks.append(result(rawname+'_valid_solid',shape.isValid() and len(shape.Solids)==1 and shape.Volume>0))
        for i,p in enumerate(s.ComputedCorners):
            measured=top_at(shape,p.x,p.y)
            checks.append(result(rawname+f'_corner_{i+1}',abs(measured-p.z)<=tol,elevation_ft=measured/FT))
        if s.Name[:-7] not in MODIFIED:
            face=ramp_trace.top_face(slab);n=face.normalAt(0,0)
            checks.append(result(rawname+'_retained_slopes',abs(-n.x/n.z*100-s.GradeX)<1e-7 and abs(-n.y/n.z*100-s.GradeY)<1e-7))
    for side in ['A','B']:
        b=settings(doc.DrainageTrial,side);ls=doc.getObject(LAND[side]+'Surface');rs=doc.getObject(UPPER[side]+'Surface')
        landing=mapping[LAND[side]+'Slab'].Shape.copy();upper=mapping[UPPER[side]+'Slab'].Shape.copy()
        differences=[];downhill=[];grades=[];thickness=[]
        for i in range(13):
            x=b['xmin']+(b['join']-b['xmin'])*i/12
            vals=[]
            for j in range(17):
                y=front(b,x)+(b['far']-front(b,x))*j/16
                z=top_at(landing,x,y);differences.append(abs(z-landing_height(b,x,y)));vals.append(z)
            downhill.extend([a-z for a,z in zip(vals,vals[1:])])
        checks.append(result(side+'_cubic_landing_matches_physical_top',max(differences)<=tol,max_error_in=max(differences)/IN))
        checks.append(result(side+'_all_sampled_landing_paths_fall_away_from_bridge',min(downhill)>0,min_fall_in=min(downhill)/IN))
        # The crown is gone at the turn; native elevations there and in the
        # single-plane remainder give independent orthogonal 1% grades.
        for y in [b['turn'],(b['turn']+b['far'])/2,b['far']]:
            za=top_at(landing,b['xmin'],y);zb=top_at(landing,b['join'],y)
            grades.append((zb-za)/(b['join']-b['xmin'])*100)
        checks.append(result(side+'_landing_toward_ramp_one_percent',max(abs(g+100*b['slope']) for g in grades)<1e-7,grades_percent=grades))
        # Compare physical normals immediately before/after the crown fade
        # boundary. No planar-face approximation is used for the transition.
        normal_errors=[]
        face=ls.Shape.Faces[0]
        for fraction in [.05,.25,.45,.55,.75,.95]:
            u=b['xmin']+(b['join']-b['xmin'])*fraction
            normal_errors.append(face.normalAt(u,1-1e-9).distanceToPoint(face.normalAt(u,1+1e-9)))
        checks.append(result(side+'_crown_fade_tangent_continuous',max(normal_errors)<1e-7,max_normal_difference=max(normal_errors)))
        seam=[]
        for j in range(17):
            y=b['near']+(b['far']-b['near'])*j/16
            seam.append(abs(top_at(landing,b['join'],y)-top_at(upper,b['join'],y)))
        checks.append(result(side+'_landing_upper_run_continuous',max(seam)<=tol,max_step_in=max(seam)/IN))
        vals=[top_at(upper,b['join']+(b['end']-b['join'])*i/16,b['turn']) for i in range(17)]
        g=[(z-a)/((b['end']-b['join'])/16)*100 for a,z in zip(vals,vals[1:])]
        checks.append(result(side+'_actual_upper_PGL_grade',max(abs(x+100*b['grade']) for x in g)<1e-7,grade_percent=-100*b['grade'],old_percent=b['original_grade']))
        checks.append(result(side+'_lower_end_elevation_held',abs(vals[-1]-b['right_center'])<=tol,elevation_ft=vals[-1]/FT))
        native_grades=[]
        upper_face_native=rs.Shape.Faces[0]
        for u in [0.,1.,1.5,2.,2.5,3.,4.]:
            for v in [0.,.2,.5,.8,1.,1.5,2.]:
                n=upper_face_native.normalAt(u,v);native_grades.append(-100*n.x/n.z)
        checks.append(result(side+'_upper_longitudinal_grades_including_edges_under_five_percent',min(native_grades)>=-5.,grade_range_percent=[min(native_grades),max(native_grades)]))
        # Tangents and vertical thickness from the nominal physical extrusion.
        ranges={'longitudinal_percent':[],'crossfall_percent':[]}
        for s in [ls,rs]:
            raw=doc.getObject(s.Name[:-7]+'Slab').Shape.copy()
            run_grades=[]
            for u in [.001,.5,1.,1.5,2.,2.5,3.,3.5,3.999] if s==rs else [b['xmin']+(b['join']-b['xmin'])*f for f in [.05,.25,.45,.55,.75,.95]]:
                for v in [.1,.4,.8,1.,1.2,1.6,1.9]:
                    face=s.Shape.Faces[0];p=face.valueAt(u,v);n=face.normalAt(u,v)
                    ranges['longitudinal_percent'].append(-100*n.x/n.z)
                    ranges['crossfall_percent'].append(-100*n.y/n.z*b['q'])
                    if s==rs:run_grades.append(-100*n.x/n.z)
                    ray=Part.makeLine(App.Vector(p.x,p.y,p.z-FT),App.Vector(p.x,p.y,p.z+FT));section=raw.common(ray)
                    zs=[z.Point.z for z in section.Vertexes]
                    thickness.append(abs(max(zs)-min(zs)-doc.MSEInputs.SlabThickness.Value))
                    differences.append(abs(top_at(raw,p.x,p.y)-p.z))
            if s==rs:checks.append(result(side+'_sampled_upper_longitudinal_grades_under_five_percent',min(run_grades)>=-5.,grade_range_percent=[min(run_grades),max(run_grades)]))
        checks.append(result(side+'_four_inch_vertical_thickness',max(thickness)<=tol,max_error_in=max(thickness)/IN))
        checks.append(result(side+'_physical_surface_does_not_reverse_away_from_bridge',max(ranges['crossfall_percent'])<0,max_grade_percent=max(ranges['crossfall_percent'])))
        field.append({'side':side,'upper_grade_percent':-100*b['grade'],'landing_slope_percent':-100*b['slope'],
            'longitudinal_range_percent':[min(ranges['longitudinal_percent']),max(ranges['longitudinal_percent'])],
            'crossfall_away_range_percent':[min(ranges['crossfall_percent']),max(ranges['crossfall_percent'])],
            'landing_extension_in':abs(front(b,b['center'])-b['original_landing_front'])/IN})
        c=doc.BridgePGL;m=bridge.model(c);idx=0 if side=='A' else 1
        station=bridge.deck_limits(c,idx)[0 if side=='A' else 1]
        deck=doc.getObject('BridgeDeckS'+str(idx+1)).Shape.copy()
        errors=[];falls=[];gap=[]
        for offset in [-c.DeckWidth.Value/2,0,c.DeckWidth.Value/2]:
            dp=c.Frame.multVec(App.Vector((station-m.start)*FT,offset,0));lp=c.Frame.multVec(App.Vector((0 if side=='A' else m.end-m.start)*FT,offset,0))
            dz=top_at(deck,dp.x,dp.y);lz=top_at(landing,lp.x,lp.y)
            expected=float(m.deck_top(m.start if side=='A' else m.end,offset/FT))*FT
            errors.append(abs(lz-expected));falls.append(dz-lz);gap.append(math.hypot(dp.x-lp.x,dp.y-lp.y)/IN)
        checks.append(result(side+'_landing_matches_crowned_FFBW_profile',max(errors)<=tol,max_error_in=max(errors)/IN))
        checks.append(result(side+'_three_inch_joint_retained',max(abs(x-3) for x in gap)*IN<=tol,gaps_in=gap))
        checks.append(result(side+'_deck_to_landing_is_downhill',min(falls)>0,falls_in=[x/IN for x in falls]))
        ties.append({'side':side,'gaps_in':gap,'deck_minus_landing_in':[x/IN for x in falls]})
    checks.append(result('no_invalid_or_touched_objects',not [o.Name for o in doc.Objects if 'Touched' in o.State or 'Invalid' in o.State]))
    trace=doc.CompletePGLTrace;parts=trace.Shape.childShapes();edges=list(parts[0].Edges)+list(parts[2].Edges)
    errors=[]
    for e,name in zip(edges,trace.SegmentSlabs):
        shape=doc.getObject(name).Shape.copy()
        for fraction in [0,.25,.5,.75,1.]:
            p=e.valueAt(e.FirstParameter+fraction*(e.LastParameter-e.FirstParameter))
            errors.append(abs(p.z-top_at(shape,p.x,p.y)))
    checks.append(result('updated_PGL_trace_follows_native_slab_tops',len(edges)==len(trace.SegmentSlabs) and max(errors)<=tol,max_error_in=max(errors)/IN))
    clashes=clash_rows(doc)
    coordination=[result('bridge_to_MSE_no_positive_overlaps',not clashes,clashes=clashes)]
    internal=[];concrete=list(doc.MSEAssembly.FinishedConcrete)
    for i,a in enumerate(concrete):
        for b in concrete[i+1:]:
            if a.Shape.BoundBox.intersect(b.Shape.BoundBox):
                volume=a.Shape.copy().common(b.Shape.copy()).Volume
                if volume>0:internal.append({'a':a.Name,'b':b.Name,'volume_ft3':volume/FT**3})
    coordination.append(result('finished_MSE_no_positive_overlaps',not internal,clashes=internal))
    return {'checks':checks,'surface_fields':field,'bridge_joints':ties,'coordination_checks':coordination,'clashes':clashes,'MSE_clashes':internal}

def create(job):
    from .api import document,check_gui,atomic,compact
    source=document(job['source_document']);check_gui(source)
    rid=job['request_id'];path=ROOT/'reports/transactions'/(rid+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['request']!=job:raise ValueError('Request ID reused')
        if old['status'] in ['PREPARED','VALIDATED']:raise ValueError('Inspect unknown outcome')
        return compact(old)
    if job['document'] in App.listDocuments():raise ValueError('Trial document already exists')
    length(job['tolerance'],True);length(job['run_blend_length'],True);mse.grade(job['landing_slope'])
    before=bridge.source_state(source,[o.Name for o in source.Objects]);prior=App.ActiveDocument.Name
    rec={'request':job,'operation':'create_drainage_trial','transaction_id':rid,'timestamp':datetime.now(timezone.utc).isoformat(),'status':'PREPARED','report_path':str(path),'source_document':source.Name,'document':job['document'],'model_saved':False,'checks':[],'errors':[]}
    atomic(path,rec);doc=None
    try:
        doc=App.newDocument(job['document']);doc.Label='B4 — drainage transition TRIAL (original unchanged)';doc.UndoMode=1
        doc.copyObject(source.Objects,True);doc.UnitSystem=source.UnitSystem;doc.recompute()
        if set(o.Name for o in doc.Objects)!=set(before):raise ValueError('Native copy changed object identities')
        if any(x.Document!=doc for o in doc.Objects for x in o.OutList):raise ValueError('Native copy has external dependencies')
        configure(doc,job)
        add_annotations(doc)
        qa=validate(doc,job['tolerance']);rec.update(qa)
        annotation_qa=validate_annotations(doc);rec['checks'].extend(annotation_qa.pop('checks'));rec.update(annotation_qa)
        rec['checks'].append(result('original_document_exactly_preserved',bridge.source_state(source,list(before))==before and set(o.Name for o in source.Objects)==set(before)))
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Trial geometry check failed')
        rec['status']='TRIAL BUILT — COORDINATION FAIL' if any(c['status']=='FAIL' for c in rec['coordination_checks']) else 'TRIAL BUILT'
        rec['rollback']='Original document retained unchanged; discard trial document to roll back.'
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc()
        if doc:App.closeDocument(doc.Name)
        App.setActiveDocument(prior)
        rec['rollback']='VERIFIED' if bridge.source_state(source,list(before))==before else 'FAILED'
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','timestamp','status','document','model_saved','rollback']})+'\n')
    return compact(rec)
