"""D-065: native level as-cast seats at the recorded existing maximum elevations.

Uniform pads stay 2.5625 in thick. Beam fit is independently measured and remains
FAIL where stock intersects an unchanged beam; no elastic compression is assumed.
"""
import json,math
import FreeCAD as App
import Part
from . import bridge,pedestal_ubars as steel
from .mse import prop,Serializable
from .geometry import length,result

FT=304.8
IN=25.4
TOL=.0254
HOSTS=tuple(f"BridgePedestal{s}B{b}" for s in ("EB1","Pier","EB2") for b in (1,2))

def field(o,typ,name,value,group="Level seat override"):
    if name not in o.PropertiesList:prop(o,typ,name,value,group)
    else:setattr(o,name,value)

def pedestal_shape(o):
    c=o.PGL;m=bridge.model(c);r=bridge.support_data(c)[o.SupportID]
    z=o.LevelSeatTopElevation.Value
    if not math.isfinite(z) or z<=r["top"]*FT:raise ValueError("Invalid level pedestal top")
    if bridge.modeled_chamfer(c,c.PedestalChamfer.Value)!=0:
        raise ValueError("Level stock helper requires the adopted square-edge convention")
    return Part.makeBox((r["pedend"]-r["pedstart"])*FT,bridge.ft(c,"PedestalWidth")*FT,z-r["top"]*FT,
        App.Vector((r["pedstart"]-m.start)*FT,(m.offsets[o.BeamIndex]-bridge.ft(c,"PedestalWidth")/2)*FT,r["top"]*FT))

def pad_shape(o):
    c=o.PGL;m=bridge.model(c);r=bridge.support_data(c)[o.SupportID]
    _,station=r["seats"][o.SeatIndex]
    host=o.LevelSeatHost
    if not host or host.Name not in HOSTS:raise ValueError("Missing level pedestal source")
    return Part.makeBox(c.PadLength.Value,c.PadWidth.Value,r["padthickness"]*FT,
        App.Vector((station-m.start)*FT-c.PadLength.Value/2,
                   m.offsets[o.BeamIndex]*FT-c.PadWidth.Value/2,host.LevelSeatTopElevation.Value))

class LevelComponentProxy(bridge.ComponentProxy):
    def execute(self,o):
        if not getattr(o,"LevelSeatEnabled",False):return super().execute(o)
        if o.ComponentKind=="Pedestal":s=pedestal_shape(o)
        elif o.ComponentKind=="Pad":s=pad_shape(o)
        else:raise ValueError("Unsupported level component")
        o.Shape=s;o.Placement=o.PGL.Frame;o.NetVolume=s.Volume

def validate(doc):
    checks=[];seats=[];fits=[];pads=[]
    for name in HOSTS:
        o=doc.getObject(name)
        if not o:raise ValueError("Missing "+name)
        s=bridge.local_shape(o);bb=s.optimalBoundingBox(False,False)
        top=[f for f in s.Faces if f.normalAt(0,0).z>.9]
        z=[v.Point.z for f in top for v in f.Vertexes]
        expected=o.LevelSeatTopElevation.Value
        c=o.PGL;m=bridge.model(c);r=bridge.support_data(c)[o.SupportID]
        volume=(r["pedend"]-r["pedstart"])*FT*c.PedestalWidth.Value*(expected-r["top"]*FT)
        checks += [
            result(name+"_valid_single_solid",s.isValid() and len(s.Solids)==1 and s.isClosed()),
            result(name+"_single_horizontal_top",len(top)==1 and max(z)-min(z)<1e-7 and abs(max(z)-expected)<TOL),
            result(name+"_cap_contact",abs(bb.ZMin-r["top"]*FT)<TOL),
            result(name+"_footprint",abs(bb.XLength-(r["pedend"]-r["pedstart"])*FT)<TOL and abs(bb.YLength-c.PedestalWidth.Value)<TOL),
            result(name+"_volume",abs(s.Volume-volume)<=max(1e-6,volume*1e-9) and abs(o.NetVolume.Value-s.Volume)<=1e-6),
        ]
        seats.append({"name":name,"support":o.SupportID,"beam":o.BeamIndex+1,
                      "as_cast_top_ft":expected/FT,"source_max_top_ft":o.SourceMaximumTopElevation.Value/FT,
                      "source_min_top_ft":o.SourceMinimumTopElevation.Value/FT,
                      "maximum_added_stock_in":(expected-o.SourceMinimumTopElevation.Value)/IN,
                      "volume_ft3":s.Volume/FT**3,"faces":len(s.Faces)})
    for o in doc.Objects:
        if getattr(o,"ComponentKind",None)!="Pad":continue
        s=bridge.local_shape(o);bb=s.optimalBoundingBox(False,False);host=o.LevelSeatHost
        c=o.PGL;r=bridge.support_data(c)[o.SupportID]
        checks += [
            result(o.Name+"_valid_uniform_level_pad",s.isValid() and len(s.Solids)==1 and len(s.Faces)==6 and abs(bb.ZLength-r["padthickness"]*FT)<TOL),
            result(o.Name+"_plan_dimensions",abs(bb.XLength-c.PadLength.Value)<TOL and abs(bb.YLength-c.PadWidth.Value)<TOL),
            result(o.Name+"_pedestal_contact",abs(bb.ZMin-host.LevelSeatTopElevation.Value)<TOL and abs(s.common(bridge.local_shape(host)).Volume)<1e-7),
            result(o.Name+"_quantity",abs(o.NetVolume.Value-s.Volume)<1e-6),
        ]
        beam=bridge.local_shape(doc.getObject(f"BridgeBeamS{o.SpanIndex+1}B{o.BeamIndex+1}"))
        common=abs(s.common(beam).Volume)
        depths=[]
        for x in (bb.XMin,bb.Center.x,bb.XMax):
            cut=beam.section(Part.makeLine(App.Vector(x,bb.Center.y,-100000),App.Vector(x,bb.Center.y,100000)))
            zs=[v.Point.z for v in cut.Vertexes]
            if not zs:raise ValueError("Cannot independently measure beam soffit")
            depths.append((bb.ZMax-min(zs))/IN)
        fits.append(result(o.Name+"_final_beam_fit",common==0 and max(depths)<=TOL/IN,
                           common_volume_in3=common/IN**3,
                           required_lowering_at_pad_start_center_end_in=depths,
                           disposition="AS-CAST STOCK: final grinding/seat setting and bearing contact unresolved"))
        pads.append({"name":o.Name,"host":host.Name,"bottom_ft":bb.ZMin/FT,"top_ft":bb.ZMax/FT,"thickness_in":bb.ZLength/IN})
    return {"geometry_status":"PASS" if all(x["status"]=="PASS" for x in checks) else "FAIL",
            "final_beam_fit_status":"PASS" if all(x["status"]=="PASS" for x in fits) else "FAIL",
            "checks":checks,"pedestals":seats,"pads":pads,"bearing_fit_checks":fits,
            "engineering_status":"NOT VERIFIED: construction stages, final grinding plane/elevation/cover, bearing contact and combined bearing checks remain open"}

class CheckProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        report=validate(o.Document)
        o.GeometryStatus=report["geometry_status"]
        o.FinalBeamFitStatus=report["final_beam_fit_status"]
        o.ReportJSON=json.dumps(report)
        o.Label="Level seat stock — geometry "+o.GeometryStatus+"; final bearing fit "+o.FinalBeamFitStatus

def configure(doc,elevations,source_sha,decision="D-065"):
    """Apply explicit unit-bearing top elevations to exactly six existing hosts."""
    if set(elevations)!=set(HOSTS):raise ValueError("Six explicit pedestal elevations required")
    if doc.getObject("LevelSeatOverrideChecks"):raise ValueError("Override already configured; inspect before retry")
    for name in HOSTS:
        host=doc.getObject(name)
        if host is None or host.ComponentKind!="Pedestal":raise ValueError("Invalid pedestal "+name)
        shape=bridge.local_shape(host)
        top=[f for f in shape.Faces if f.normalAt(0,0).z>.9]
        zs=[v.Point.z for f in top for v in f.Vertexes]
        elevation=length(elevations[name],positive=True)
        if abs(elevation-max(zs))>1e-7:raise ValueError("Override does not match measured source maximum")
        inp=doc.getObject(f"PedSteel{host.SupportID}B{host.BeamIndex+1}Inputs")
        # Preserve the existing reinforcement height, including its curvature
        # allowance, so future grinding does not consume its original cover.
        centre=min(zs)-(inp.Cover.Value+inp.Diameter.Value/2)/min(f.normalAt(0,0).z for f in top)
        field(inp,"App::PropertyBool","UsePreGrindingReference",True)
        field(inp,"App::PropertyLength","PreGrindingReferenceElevation",centre+inp.Cover.Value+inp.Diameter.Value/2)
        field(inp,"App::PropertyString","PreGrindingBasis",decision+": retain pre-override cage elevations; verify cover to the final ground surface.")
        for typ,key,val in [
            ("App::PropertyBool","LevelSeatEnabled",True),
            ("App::PropertyLength","LevelSeatTopElevation",elevations[name]),
            ("App::PropertyLength","SourceMaximumTopElevation",max(zs)),
            ("App::PropertyLength","SourceMinimumTopElevation",min(zs)),
            ("App::PropertyString","LevelSeatDecision",decision),
            ("App::PropertyString","LevelSeatSourceSHA256",source_sha),
            ("App::PropertyString","LevelSeatBasis","Level AS-CAST stock at prior maximum top; final fit/grinding and bearing acceptance pending."),
        ]:field(host,typ,key,val)
        for key in ("SourceMaximumTopElevation","SourceMinimumTopElevation","LevelSeatSourceSHA256"):host.setEditorMode(key,1)
        LevelComponentProxy(host);host.Proxy.execute(host)
        host.Label=f"{host.SupportID} pedestal {host.BeamIndex+1} — LEVEL AS-CAST"
        host.purgeTouched();inp.purgeTouched()
    pads=[]
    for pad in doc.Objects:
        if getattr(pad,"ComponentKind",None)!="Pad":continue
        host=doc.getObject(f"BridgePedestal{pad.SupportID}B{pad.BeamIndex+1}")
        field(pad,"App::PropertyBool","LevelSeatEnabled",True)
        field(pad,"App::PropertyLink","LevelSeatHost",host)
        field(pad,"App::PropertyString","LevelSeatBasis",decision+": uniform level pad on as-cast seat; beam fit is not yet resolved.")
        LevelComponentProxy(pad);pad.Proxy.execute(pad);pad.purgeTouched();pads.append(pad)
    check=doc.addObject("App::FeaturePython","LevelSeatOverrideChecks")
    field(check,"App::PropertyLinkList","Pedestals",[doc.getObject(n) for n in HOSTS])
    field(check,"App::PropertyLinkList","Pads",pads)
    for key in ("GeometryStatus","FinalBeamFitStatus","ReportJSON"):field(check,"App::PropertyString",key,"")
    CheckProxy(check);check.Proxy.execute(check)
    doc.BridgeAssembly.addObject(check)
    # Existing full-model fit evidence cannot retain a green status after this
    # intentional as-cast geometry change. Its normal controller still measures
    # the actual fit on future recomputes.
    doc.BridgeGeometryChecks.GeometryStatus="FAIL"
    doc.BridgeGeometryChecks.Label="Bridge checks — final bearing fit FAIL; level as-cast stock"
    return validate(doc)
