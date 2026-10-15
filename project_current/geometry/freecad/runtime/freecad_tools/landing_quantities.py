"""Verified volume reporting for the two curved bridge landing slabs.

Measurement only: never changes a shape or its triangulation. FreeCAD's default
Volume property is unreliable on these trimmed, multi-span spline surfaces.
"""
import hashlib
import json
import math
import FreeCAD as App
import Part

LANDINGS=('A_BridgeLandingAtReturns','B_BridgeLandingAtReturns')
# Tighten the engine requests further than the required reported error. The
# vertical-plane formulation avoids cancellation between horizontal moments.
INTEGRATION_LEVELS=((1e-12,1e-8),(1e-14,1e-10))
MAX_RELATIVE_CHANGE=1e-9


def measure(shape):
    """Require closed valid solids and agreement of two precise integrations."""
    if shape.isNull() or not shape.isValid() or not shape.Solids or not shape.isClosed():
        raise ValueError('Volume requires a valid closed solid')
    import OCC
    from OCC.Core.BRepTools import breptools
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.gp import gp_Pln,gp_Pnt,gp_Dir
    if OCC.VERSION.split('.')[:3] != Part.OCC_VERSION.split('.')[:3]:
        raise RuntimeError('PythonOCC and FreeCAD kernel versions must match')
    brep=shape.exportBrepToString()
    # Serialize in memory instead of sharing ownership of a C++ shape pointer.
    native=breptools.ReadFromString(brep)
    plane=gp_Pln(gp_Pnt(0,0,shape.BoundBox.ZMin),gp_Dir(0,0,1))
    samples=[]
    for epsilon,required_error in INTEGRATION_LEVELS:
        props=GProp_GProps()
        error=brepgprop.VolumePropertiesGK(native,props,plane,epsilon,True,True,False,False,False)
        value=props.Mass()
        if not math.isfinite(value) or value<=0 or not math.isfinite(error) or not 0<=error<=required_error:
            raise ValueError('Curved-solid volume integration did not converge')
        samples.append({'integration_request':epsilon,'required_relative_error':required_error,'reported_relative_error':error,'volume_mm3':value})
    value=samples[-1]['volume_mm3']
    change=abs(value-samples[0]['volume_mm3'])
    if change>max(1e-3,abs(value)*MAX_RELATIVE_CHANGE):
        raise ValueError('Successive curved-solid volume calculations disagree')
    return {'status':'VERIFIED','volume_mm3':value,'raw_kernel_volume_mm3':shape.Volume,
            'relative_change':change/value,'samples':samples,
            'method':'Adaptive vertical integration with spline spans',
            'shape_sha256':hashlib.sha256(brep.encode()).hexdigest(),
            'kernel_version':Part.OCC_VERSION,'pythonocc_version':OCC.VERSION}


def update(obj):
    """Refresh quantity metadata after a native landing shape is generated."""
    properties=[('App::PropertyString','VolumeMethod'),('App::PropertyString','VolumeStatus'),
                ('App::PropertyString','VolumeCheckJSON')]
    for typ,name in properties:
        if name not in obj.PropertiesList:obj.addProperty(typ,name,'Quantity')
        obj.setEditorMode(name,2 if name=='VolumeCheckJSON' else 1)
    obj.setEditorMode('NetVolume',1)
    obj.VolumeStatus='Needs review'
    result=measure(obj.Shape)
    obj.NetVolume=result['volume_mm3']
    obj.VolumeMethod=result['method']
    obj.VolumeCheckJSON=json.dumps(result,sort_keys=True)
    obj.VolumeStatus='Verified'
    return result


def refresh(doc):
    """Update the two existing landings in one reversible metadata transaction."""
    objects=[doc.getObject(n) for n in LANDINGS]
    if any(o is None for o in objects):raise ValueError('Both finished bridge landings are required')
    before={o.Name:o.Shape.exportBrepToString() for o in objects}
    old={o.Name:o.NetVolume.Value for o in objects}
    doc.openTransaction('Verify curved landing quantities')
    try:
        results={o.Name:update(o) for o in objects}
        if any(o.Shape.exportBrepToString()!=before[o.Name] for o in objects):
            raise ValueError('Quantity update changed geometry')
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    return {'status':'PASS','document':doc.Name,'old_net_volume_mm3':old,'landings':results,
            'geometry_unchanged':True,'saved':False}
