"""Editable reference ribbons for backwall soil-reinforcement straps.

The user requested a 2-in-wide representation at the calculated trial elevation.
Projection is illustrative, with one centered ribbon per backwall. These are
zero-thickness faces, excluded from physical steel quantities and design checks.
"""
import FreeCAD as App
from . import bridge, mse, mse_revision as rev

IN=25.4
FT=304.8


class StrapProxy(mse.Serializable):
    def __init__(self,obj):obj.Proxy=self

    def execute(self,obj):
        cap=bridge.local_shape(obj.Cap).BoundBox
        wall_shape=bridge.local_shape(obj.Backwall)
        width=obj.Width.Value;length=obj.Projection.Value
        z=cap.ZMax+obj.ElevationAboveCap.Value
        if width<=0 or length<=0:raise ValueError('Strap width and projection must be positive')
        if obj.SupportID not in ('EB1','EB2'):raise ValueError('Unknown end bent')
        sign=-1 if obj.SupportID=='EB1' else 1
        # EB1 includes a landing-seat surface whose bounds extend beyond the
        # actual backwall. Attach to its unique vertical fill-side face at z.
        faces=[f for f in wall_shape.Faces if sign*f.normalAt(0,0).x>.99
               and abs(f.normalAt(0,0).z)<1e-9 and f.BoundBox.ZMin<z<f.BoundBox.ZMax]
        if len(faces)!=1:raise ValueError('Fill-side backwall face is ambiguous at strap elevation')
        face=faces[0];wall=face.BoundBox;normal=face.normalAt(0,0)
        center=face.CenterOfMass
        y=(wall.YMin+wall.YMax)/2+obj.LateralOffset.Value
        if y-width/2<wall.YMin or y+width/2>wall.YMax:raise ValueError('Strap lies outside the backwall width')
        x=center.x-(normal.y*(y-center.y)+normal.z*(z-center.z))/normal.x
        origin=App.Vector(x,y,z)
        outward=App.Vector(normal.x,normal.y,0);outward.normalize()
        transverse=App.Vector(-outward.y,outward.x,0)
        if transverse.y<0:transverse=-transverse
        a=origin-transverse*(width/2);b=origin+transverse*(width/2)
        points=[a,a+outward*length,b+outward*length,b]
        if sign<0:points.reverse()
        shape=rev.closed_face(points)
        shape.Placement=obj.PGL.Frame
        obj.Shape=shape
        obj.ConnectionElevation=z
        obj.CapTopElevation=cap.ZMax


def add(doc,width='2 in',projection='6 ft',elevation_above_cap='18 in'):
    """Create one reference ribbon at each backwall in a caller-owned transaction.

    No save, steel quantity, repeated spacing, anchorage or capacity is inferred.
    """
    if doc.getObject('BackwallGeotechnicalStraps'):
        raise ValueError('Strap representation exists; edit its native properties')
    group=doc.addObject('App::DocumentObjectGroup','BackwallGeotechnicalStraps')
    group.Label='Geotechnical backwall straps - schematic'
    doc.BridgeAssembly.addObject(group)
    added=[group.Name]
    for sid in ('EB1','EB2'):
        obj=doc.addObject('Part::FeaturePython','GeotechnicalStrap'+sid)
        obj.Label=sid+' geotechnical strap - 2 in wide, schematic'
        group.addObject(obj);added.append(obj.Name)
        props=[('App::PropertyLink','PGL',doc.BridgePGL),
            ('App::PropertyLink','Cap',doc.getObject('BridgeCap'+sid)),
            ('App::PropertyLink','Backwall',doc.getObject('BridgeBackwall'+sid)),
            ('App::PropertyString','SupportID',sid),
            ('App::PropertyLength','Width',width),
            ('App::PropertyLength','Projection',projection),
            ('App::PropertyLength','ElevationAboveCap',elevation_above_cap),
            ('App::PropertyLength','LateralOffset','0 in'),
            ('App::PropertyLength','ConnectionElevation','0 ft'),
            ('App::PropertyLength','CapTopElevation','0 ft'),
            ('App::PropertyString','ComponentKind','SchematicGeotechnicalStrap'),
            ('App::PropertyString','RepresentationBasis','User-requested 2-in-wide geotechnical strap. One centered ribbon per backwall with illustrative editable 6-ft projection into the fill. Zero modeled thickness; no inferred spacing, connection hardware or physical steel quantity.'),
            ('App::PropertyString','ElevationBasis','Selected backwall design z_strap = 1.5 ft above cap top (D-019); trial level pending MSE coordination.'),
            ('App::PropertyString','DesignStatus','Schematic representation only; strap/pullout design and connection by MSE supplier.')]
        for typ,name,value in props:rev.setprop(obj,typ,name,value,'Geotechnical strap')
        StrapProxy(obj);obj.Proxy.execute(obj)
    for obj in doc.Objects:obj.purgeTouched()
    return {'added':added,'straps':['GeotechnicalStrapEB1','GeotechnicalStrapEB2']}
