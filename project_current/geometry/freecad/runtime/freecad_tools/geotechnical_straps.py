"""Editable reference ribbons for backwall soil-reinforcement straps.

The user requested a 2-in-wide representation at the calculated trial elevation.
Projection is illustrative. The corrected report layout contains seven ribbons
per backwall. These are zero-thickness reference faces, excluded from physical
steel quantities and design checks.
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
            ('App::PropertyDistance','LateralOffset','0 in'),
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


def match_report_layout(doc,offsets,source_sha256):
    """Apply seven dimensioned offsets transcribed from selected Figure B2.

    Keep the existing central reference Names, width, elevation and projection.
    Caller owns the transaction, independent validation and save decision.
    """
    if len(offsets)!=7:raise ValueError('Figure B2 shows seven straps per backwall')
    values=[App.Units.Quantity(value) for value in offsets]
    if abs(values[3].Value)>1e-9:raise ValueError('Central strap must remain centered')
    if any(a.Value>=b.Value for a,b in zip(values,values[1:])):raise ValueError('Strap offsets must increase')
    group=doc.getObject('BackwallGeotechnicalStraps')
    if not group:raise ValueError('Existing geotechnical strap group is required')
    if any(doc.getObject('GeotechnicalStrap'+sid+'S'+str(i)) for sid in ('EB1','EB2') for i in (1,2,3,5,6,7)):
        raise ValueError('Seven-strap layout exists; edit native controls instead')
    rev.setprop(group,'App::PropertyInteger','CountPerBackwall',7,'Report layout')
    rev.setprop(group,'App::PropertyString','LayoutSource','Selected Backwall Design 10-16.html, Figure B2; schematic layout by the Specialty Engineer.','Report layout')
    rev.setprop(group,'App::PropertyString','SourceReportSHA256',source_sha256,'Report layout')
    basis='Figure B2 schematic: seven evenly spaced 2-in-wide reference ribbons per backwall. Retained illustrative 6-ft projection. Zero thickness and no physical steel quantity; final layout/connection design by MSE supplier.'
    props=['PGL','Cap','Backwall','SupportID','Width','Projection','ElevationAboveCap','LateralOffset',
           'ConnectionElevation','CapTopElevation','ComponentKind','RepresentationBasis','ElevationBasis','DesignStatus']
    added=[];straps=[]
    for sid in ('EB1','EB2'):
        central=doc.getObject('GeotechnicalStrap'+sid)
        if not central or not isinstance(central.Proxy,StrapProxy):raise ValueError('Expected original editable strap')
        # FreeCAD Length clamps negative values; the lateral coordinate must
        # use its signed Distance property so both halves of the wall are shown.
        if central.getTypeIdOfProperty('LateralOffset')=='App::PropertyLength':
            if any(name=='LateralOffset' for name,expression in central.ExpressionEngine):
                raise ValueError('Review an existing lateral-offset expression before migration')
            old_offset=central.LateralOffset
            central.removeProperty('LateralOffset')
            rev.setprop(central,'App::PropertyDistance','LateralOffset',old_offset,'Geotechnical strap')
        for i,value in enumerate(values,1):
            if i==4:obj=central
            else:
                obj=doc.addObject('Part::FeaturePython','GeotechnicalStrap'+sid+'S'+str(i))
                for name in props:rev.setprop(obj,central.getTypeIdOfProperty(name),name,getattr(central,name),'Geotechnical strap')
                StrapProxy(obj);group.addObject(obj);added.append(obj.Name)
            obj.Label=sid+' geotechnical strap '+str(i)+' of 7 - 2 in wide, schematic'
            obj.LateralOffset=value
            obj.RepresentationBasis=basis
            rev.setprop(obj,'App::PropertyInteger','StrapIndex',i,'Report layout')
            obj.Proxy.execute(obj);straps.append(obj.Name)
    for obj in doc.Objects:obj.purgeTouched()
    return {'added':added,'straps':straps,'changed_existing':[group.Name,'GeotechnicalStrapEB1','GeotechnicalStrapEB2']}
