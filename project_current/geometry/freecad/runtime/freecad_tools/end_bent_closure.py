"""Native low-wall copings and 4-in weather closure at both end-bent faces.

Uses the adopted project coping section and existing wall/cap geometry. The
closure and side coping tops fall together from the cap to the front coping
top. Coping undersides retain their level panel seats. Wall heights and all
prior concrete remain unchanged. Junctions are modeled as contacting faces;
sealant, reinforcement and movement-joint construction are not specified here.
"""
import json
import FreeCAD as App
import Part
from . import bridge, mse, mse_revision as rev

IN=25.4
FT=304.8
SUPPORTS={'EB1':('A5','A6','A7'),'EB2':('B1','B6','B7')}
# Adopted working-DXF section used by mse_revision.DetailProxy: 11.5-in wide,
# 17-in cap above the panel and a 6-in-wide, 13-in-deep exterior skirt.
PROFILE=[(0,-8),(0,9),(11.5,9),(11.5,-21),(5.5,-21),(5.5,-8)]


def local_bounds(obj,frame):
    shape=obj.Shape.copy()
    shape.Placement=frame.inverse().multiply(shape.Placement)
    return shape.BoundBox


def cap_station(inp):
    b=local_bounds(inp.Cap,inp.PGL.Frame)
    return b.XMax if inp.SupportID=='EB1' else b.XMin


def low_top(wall):
    values=[p.z for p,name in zip(wall.TopControls,wall.TopSourceNames) if not name]
    if not values or max(values)-min(values)>1e-7:
        raise ValueError('Expected one level exposed low-wall top: '+wall.Name)
    return values[0]


def coping_path_elevation(inp):
    profile=json.loads(inp.CopingProfileJSON)
    # The underside of the section over the panel sits on its existing top.
    bottom=min(z for n,z in profile if abs(n)<1e-9)*IN
    return low_top(inp.FrontWall)-bottom


def slab_low_elevation(inp):
    return coping_path_elevation(inp)+max(z for n,z in json.loads(inp.CopingProfileJSON))*IN


def footprint(inp):
    """Four exact intersections of existing wall inner faces and cap front."""
    front=inp.FrontWall
    corners=[rev.corner_point(front,side) for side in inp.SideWalls]
    inv=inp.PGL.Frame.inverse()
    station=cap_station(inp)
    ends=[]
    for side in inp.SideWalls:
        p=inv.multVec(side.Start);t=inv.Rotation.multVec(side.Tangent)
        if abs(t.x)<.9:raise ValueError('Side wall must run toward the cap')
        ends.append(side.Start+side.Tangent*((station-p.x)/t.x))
    return [corners[0],corners[1],ends[1],ends[0]]


def slab_z(inp,point):
    normal=inp.FrontWall.Normal
    run=(inp.FrontWall.Start-point).dot(normal)
    return slab_low_elevation(inp)+inp.DrainageSlope/100*run


def front_halfspace(inp):
    """Keep coping material on the exposed side of the cap front plane."""
    station=cap_station(inp);extent=1e6
    xmin=station if inp.SupportID=='EB1' else station-extent
    shape=Part.makeBox(extent,2*extent,2*extent,App.Vector(xmin,-extent,-extent))
    shape.Placement=inp.PGL.Frame
    return shape


class CopingProxy(mse.Serializable):
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        inp=obj.Inputs;w=obj.WallProfile
        if abs(low_top(w)-low_top(inp.FrontWall))>1e-7:
            raise ValueError('Low MSE wall tops do not share the coping seat')
        profile=json.loads(inp.CopingProfileJSON)
        width=max(n for n,z in profile)*IN
        controls=[p.x for p,name in zip(w.TopControls,w.TopSourceNames) if not name]
        lo,hi=min(controls),max(controls)
        for other in obj.CornerSources:
            p=rev.corner_point(w,other)+(w.Normal+other.Normal)*width
            t=(p-w.Start).dot(w.Tangent)
            lo=min(lo,t);hi=max(hi,t)
        a=w.Start+w.Tangent*lo;b=w.Start+w.Tangent*hi
        a.z=b.z=coping_path_elevation(inp)
        path=Part.makeLine(a,b)
        if w==inp.FrontWall:
            shape=rev.section_sweep(path,w.Normal,profile)
        else:
            # Keep the panel-bearing recess and exterior skirt level. Only the
            # two top vertices rise with the closure plane, deepening the cap.
            # The small corner extension beyond the front wall remains level
            # so it joins the front coping with no step at the mitre.
            corner=rev.corner_point(w,inp.FrontWall)
            cut=(corner-w.Start).dot(w.Tangent)
            stations=sorted(set([lo,hi]+([cut] if lo<cut<hi else [])))
            rings=[];top=max(z for n,z in profile)
            for station in stations:
                center=w.Start+w.Tangent*station;ring=[]
                for offset,height in profile:
                    p=center+w.Normal*offset*IN
                    p.z=(max(slab_low_elevation(inp),slab_z(inp,p)) if height==top
                         else coping_path_elevation(inp)+height*IN)
                    ring.append(p)
                rings.append(ring)
            shape=rev.join_solids([rev.ruled_profile_solid(p,q) for p,q in zip(rings,rings[1:])])
        shape=rev.mitre_clip(shape,w).common(front_halfspace(inp)).removeSplitter()
        if not shape.isValid() or len(shape.Solids)!=1:
            raise ValueError('Invalid new coping '+obj.Name)
        obj.Shape=shape
        obj.Path=path.common(front_halfspace(inp))
        obj.NetVolume=shape.Volume
        obj.PanelTopElevation=low_top(w)
        obj.CopingTopElevation=shape.BoundBox.ZMax


class SlabProxy(mse.Serializable):
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        inp=obj.Inputs
        if inp.SlabThickness.Value<=0 or inp.DrainageSlope<=0:
            raise ValueError('Positive slab thickness and outward fall are required')
        points=footprint(inp)
        for p in points:p.z=slab_z(inp,p)
        face=rev.closed_face(points)
        shape=face.extrude(App.Vector(0,0,-inp.SlabThickness.Value))
        if shape.Volume<0:shape.reverse()
        if not shape.isValid() or len(shape.Solids)!=1:
            raise ValueError('Invalid closure slab '+obj.Name)
        cap=local_bounds(inp.Cap,inp.PGL.Frame)
        if min(p.z for p in points[2:])-inp.SlabThickness.Value<cap.ZMin or max(p.z for p in points[2:])>cap.ZMax:
            raise ValueError('Slab thickness must meet the vertical cap face')
        obj.Shape=shape
        obj.NetVolume=shape.Volume
        obj.TopSurface=face
        obj.LowTopElevation=slab_low_elevation(inp)
        obj.CapTopElevations=[p.z for p in points[2:]]


def add(doc,thickness='4 in',slope='2 %'):
    """Add the linked detail to a disposable model or caller-owned transaction.

    Does not save. Caller verifies all original records and new physical joints.
    """
    if doc.getObject('EndBentWeatherClosure'):
        raise ValueError('Closure already exists; inspect instead of repeating')
    t=App.Units.Quantity(thickness).Value
    g=mse.grade(slope)
    if abs(t-4*IN)>1e-9 or abs(g-2)>1e-9:
        raise ValueError('This revision is authorized for 4 in thickness and 2% slope')
    group=doc.addObject('App::DocumentObjectGroup','EndBentWeatherClosure')
    group.Label='End-bent MSE copings and rain closure slabs'
    doc.BridgeAssembly.addObject(group)
    added=[group.Name];physical=[]
    for sid,wallids in SUPPORTS.items():
        part=doc.addObject('App::DocumentObjectGroup','Closure'+sid)
        part.Label=sid+' low-wall coping and 2% closure';group.addObject(part);added.append(part.Name)
        inp=doc.addObject('App::FeaturePython','Closure'+sid+'Inputs')
        inp.Label=sid+' closure dimensions and source links';part.addObject(inp);added.append(inp.Name)
        properties=[('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyLink','Cap',doc.getObject('BridgeCap'+sid)),
            ('App::PropertyLink','FrontWall',doc.getObject('Wall'+wallids[0]+'Profile')),
            ('App::PropertyLinkList','SideWalls',[doc.getObject('Wall'+w+'Profile') for w in wallids[1:]]),
            ('App::PropertyString','SupportID',sid),('App::PropertyLength','SlabThickness',thickness),
            ('App::PropertyFloat','DrainageSlope',g),('App::PropertyString','CopingProfileJSON',json.dumps(PROFILE)),
            ('App::PropertyString','ConnectionBasis','User direction: slab top coincides with front coping top and rises 2% to cap face; side coping tops coincide with the sloped slab. Existing panel heights and level coping seats retained.'),
            ('App::PropertyString','JointBasis','Face contacts represent the requested rain closure. Sealant, movement-joint and reinforcement details are not specified.')]
        for typ,name,value in properties:rev.setprop(inp,typ,name,value,'Weather closure')
        for wallid in wallids:
            obj=doc.addObject('Part::FeaturePython','ClosureCoping'+wallid)
            obj.Label=sid+' coping on low MSE '+wallid;part.addObject(obj)
            w=doc.getObject('Wall'+wallid+'Profile')
            for typ,name,value in [('App::PropertyLink','Inputs',inp),('App::PropertyLink','WallProfile',w),
                ('App::PropertyLinkList','CornerSources',[p for p in [inp.FrontWall]+list(inp.SideWalls) if p!=w and p in rev.corner_profiles(w)]),
                ('App::PropertyString','ComponentKind','ClosureCoping'),('Part::PropertyPartShape','Path',Part.Shape()),
                ('App::PropertyVolume','NetVolume',0),('App::PropertyLength','PanelTopElevation','0 ft'),
                ('App::PropertyLength','CopingTopElevation','0 ft')]:rev.setprop(obj,typ,name,value,'Weather closure')
            CopingProxy(obj);obj.Proxy.execute(obj);physical.append(obj);added.append(obj.Name)
        obj=doc.addObject('Part::FeaturePython','ClosureSlab'+sid)
        obj.Label=sid+' rain closure slab - 4 in, 2% fall toward coping';part.addObject(obj)
        for typ,name,value in [('App::PropertyLink','Inputs',inp),('App::PropertyString','ComponentKind','ClosureSlab'),
            ('App::PropertyVolume','NetVolume',0),('Part::PropertyPartShape','TopSurface',Part.Shape()),
            ('App::PropertyLength','LowTopElevation','0 ft'),('App::PropertyFloatList','CapTopElevations',[])]:rev.setprop(obj,typ,name,value,'Weather closure')
        SlabProxy(obj);obj.Proxy.execute(obj);physical.append(obj);added.append(obj.Name)
    sheet=doc.addObject('Spreadsheet::Sheet','EndBentClosureSchedule')
    sheet.Label='End-bent closure concrete quantities';group.addObject(sheet);added.append(sheet.Name)
    for col,value in [('A','Component'),('B','Volume (ft^3)'),('C','Volume (yd^3)')]:sheet.set(col+'1',value)
    for row,obj in enumerate(physical,2):
        sheet.set('A'+str(row),obj.Label)
        sheet.set('B'+str(row),'='+obj.Name+'.NetVolume / (1 ft)^3')
        sheet.set('C'+str(row),'=B'+str(row)+'/27')
    row=len(physical)+2;sheet.set('A'+str(row),'Total')
    sheet.set('B'+str(row),'=sum(B2:B'+str(row-1)+')');sheet.set('C'+str(row),'=B'+str(row)+'/27')
    for obj in doc.Objects:obj.purgeTouched()
    sheet.touch();doc.recompute([sheet])
    for obj in doc.Objects:obj.purgeTouched()
    return dict(added=added,physical=[o.Name for o in physical],schedule=sheet.Name)
