"""PGL-derived nominal pads, pedestals, caps and provisional foundation shapes."""
import FreeCAD as App
import Part
from .bridge_shapes import FT,plane_polygon

def bearing_plane(model,span,beam,station,pad_length_ft):
    a,b=station-pad_length_ft/2,station+pad_length_ft/2
    za,zb=[float(z) for z in model.evaluate([a,b],span)['bottom'][:,beam]]
    slope=(zb-za)/(b-a)
    return lambda s: za+(s-a)*slope

def pad_solid(model,span,beam,station,length_ft,width_ft,thickness_ft):
    top=bearing_plane(model,span,beam,station,length_ft)
    a,b=station-length_ft/2,station+length_ft/2
    y=model.offsets[beam]-width_ft/2
    pts=[((a-model.start)*FT,y*FT,top(a)*FT),((b-model.start)*FT,y*FT,top(b)*FT),
         ((b-model.start)*FT,y*FT,(top(b)-thickness_ft)*FT),
         ((a-model.start)*FT,y*FT,(top(a)-thickness_ft)*FT)]
    return plane_polygon(pts).extrude(App.Vector(0,width_ft*FT,0))

def pedestal_solid(model,beam,start_ft,end_ft,cap_top_ft,seats,pad_length_ft,pad_thickness_ft,width_ft,chamfer_ft):
    """Flat bearing seats and a planar transition between opposed pier seats.

    The pad tops chord the beam soffit over 10 in. They have no nominal
    interference and a sub-tolerance central gap; no elastic analysis implied.
    Pedestal bottom is level; top bevels run along transverse outer edges.
    """
    planes=[bearing_plane(model,span,beam,s,pad_length_ft) for span,s in seats]
    if len(seats)==1:
        cuts=[start_ft,end_ft]; tops=[planes[0](s)-pad_thickness_ft for s in cuts]
    else:
        l=seats[0][1]+pad_length_ft/2; r=seats[1][1]-pad_length_ft/2
        cuts=[start_ft,l,r,end_ft]
        tops=[planes[0](cuts[0])-pad_thickness_ft,planes[0](l)-pad_thickness_ft,
              planes[1](r)-pad_thickness_ft,planes[1](cuts[3])-pad_thickness_ft]
    cy=model.offsets[beam]; solids=[]
    for a,b,za,zb in zip(cuts[:-1],cuts[1:],tops[:-1],tops[1:]):
        wires=[]
        for s,z in [(a,za),(b,zb)]:
            x=(s-model.start)*FT
            points=[(x,(cy-width_ft/2)*FT,cap_top_ft*FT),(x,(cy+width_ft/2)*FT,cap_top_ft*FT),
                (x,(cy+width_ft/2)*FT,(z-chamfer_ft)*FT),(x,(cy+width_ft/2-chamfer_ft)*FT,z*FT),
                (x,(cy-width_ft/2+chamfer_ft)*FT,z*FT),(x,(cy-width_ft/2)*FT,(z-chamfer_ft)*FT)]
            wires.append(plane_polygon(points).OuterWire)
        solids.append(Part.makeLoft(wires,True,True))
    return solids[0] if len(solids)==1 else solids[0].multiFuse(solids[1:]).removeSplitter()

def cap_solid(model,station,width_ft,length_ft,top_ft,depth_ft):
    return Part.makeBox(width_ft*FT,length_ft*FT,depth_ft*FT,
        App.Vector((station-model.start-width_ft/2)*FT,-length_ft*FT/2,(top_ft-depth_ft)*FT))

def pipe_solid(model,station,offset_ft,top_ft,length_ft,diameter_ft,wall_ft):
    base=App.Vector((station-model.start)*FT,offset_ft*FT,(top_ft-length_ft)*FT)
    outer=Part.makeCylinder(diameter_ft*FT/2,length_ft*FT,base)
    inner=Part.makeCylinder((diameter_ft/2-wall_ft)*FT,length_ft*FT,base)
    return outer.cut(inner)
