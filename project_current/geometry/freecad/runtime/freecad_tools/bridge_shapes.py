"""Exact section and quadratic longitudinal BReps for the PGL bridge adapter."""
import math
import FreeCAD as App
import Part

IN = 25.4
FT = 304.8


def fib36_wire():
    """FDOT 450-036 section: 48 x 36 in, 38-in bottom flange, 7-in web.

    Radius 15 in is tangent to the web and the lower flange slope. The
    intersection of those tangents is (3.5,14.5) inches above bottom.
    Top breaks and the two 3/4-in bottom chamfers follow sheet 1.
    Local cross-section lies in the YZ plane at X=0.
    """
    v = lambda p: App.Vector(0, p[0]*IN, p[1]*IN)
    center_z = (224.5 + 15*math.sqrt(1186))/31
    tangent = (18.5-225/math.sqrt(1186), center_z-465/math.sqrt(1186))
    mid_angle = (math.pi + math.atan2(tangent[1]-center_z, tangent[0]-18.5) + 2*math.pi)/2
    mid = (18.5+15*math.cos(mid_angle), center_z+15*math.sin(mid_angle))
    path = [(-24,36),(24,36),(24,32.5),(7,31),(3.5,27.5),(3.5,center_z)]
    edges = [Part.makeLine(v(a),v(b)) for a,b in zip(path[:-1],path[1:])]
    edges.append(Part.Arc(v(path[-1]),v(mid),v(tangent)).toShape())
    tail = [tangent,(19,7),(19,.75),(18.25,0),(-18.25,0),(-19,.75),(-19,7),(-tangent[0],tangent[1])]
    edges.extend(Part.makeLine(v(a),v(b)) for a,b in zip(tail[:-1],tail[1:]))
    edges.append(Part.Arc(v(tail[-1]),v((-mid[0],mid[1])),v((-3.5,center_z))).toShape())
    tail = [(-3.5,center_z),(-3.5,27.5),(-7,31),(-24,32.5),(-24,36)]
    edges.extend(Part.makeLine(v(a),v(b)) for a,b in zip(tail[:-1],tail[1:]))
    return Part.Wire(edges)


def quadratic_solid(profile, start_mm, end_mm, z_start_mm, z_mid_mm, z_end_mm, offset_mm=0):
    """Translate a section along X with exact quadratic vertical rise.

    This is a tensor-product B-spline boundary, preserving vertical sections
    and rational circular fillets. It does not rotate sections along a spine.
    """
    xs=[start_mm,(start_mm+end_mm)/2,end_mm]
    zs=[z_start_mm,2*z_mid_mm-(z_start_mm+z_end_mm)/2,z_end_mm]
    faces=[]
    for edge in profile.Edges:
        curve=edge.toNurbs().Edges[0].Curve
        poles=[[App.Vector(xs[j],p.y+offset_mm,p.z+zs[j]) for j in range(3)] for p in curve.getPoles()]
        weights=[[w,w,w] for w in curve.getWeights()]
        surface=Part.BSplineSurface()
        surface.buildFromPolesMultsKnots(poles,curve.getMultiplicities(),[3,3],curve.getKnots(),[0.,1.],False,False,curve.Degree,2,weights)
        faces.append(surface.toShape())
    for x,z in [(start_mm,z_start_mm),(end_mm,z_end_mm)]:
        cap=profile.copy()
        cap.translate(App.Vector(x,offset_mm,z))
        faces.append(Part.Face(cap))
    shell=Part.makeShell(faces)
    shell.sewShape()
    solid=Part.makeSolid(shell)
    if solid.Volume<0:
        solid.reverse()
    return solid


def plane_polygon(points):
    pts=[App.Vector(*p) for p in points]
    return Part.Face(Part.makePolygon(pts+[pts[0]]))


def section_at(shape, station_mm, half_width_mm=5000, bottom_mm=-100000, top_mm=100000):
    plane=plane_polygon([(station_mm,-half_width_mm,bottom_mm),(station_mm,half_width_mm,bottom_mm),
                         (station_mm,half_width_mm,top_mm),(station_mm,-half_width_mm,top_mm)])
    return shape.section(plane)


def quadratic_polygon_solid(start_points, mid_points, end_points):
    """Loft corresponding polygon vertices using exact quadratic trajectories.

    Sections are ordered open point lists. Endpoint polygons must be planar.
    A straight top and cambered bottom can therefore enclose a true haunch,
    without faceting its longitudinal surfaces or altering the PGL.
    """
    if len(start_points) != len(mid_points) or len(start_points) != len(end_points):
        raise ValueError('Corresponding section polygons require equal vertex counts')
    tracks = []
    for a,m,b in zip(start_points,mid_points,end_points):
        a,m,b = App.Vector(*a),App.Vector(*m),App.Vector(*b)
        tracks.append([a,2*m-(a+b)/2,b])
    faces = []
    for i in range(len(tracks)):
        surface=Part.BSplineSurface()
        surface.buildFromPolesMultsKnots([tracks[i],tracks[(i+1)%len(tracks)]],
            [2,2],[3,3],[0.,1.],[0.,1.],False,False,1,2)
        faces.append(surface.toShape())
    faces.extend([plane_polygon(start_points),plane_polygon(end_points)])
    shell=Part.makeShell(faces)
    shell.sewShape()
    solid=Part.makeSolid(shell)
    if solid.Volume < 0: solid.reverse()
    return solid


def deck_solid(model, start_ft, end_ft):
    """One linear PGL interval of a vertically measured crowned deck."""
    if model.profile_mode != 'brokeback' or model.deck_mode != 'crowned':
        raise ValueError('Deck helper tested only for linear PGL intervals and a crown')
    if start_ft < model.peak < end_ft:
        raise ValueError('Split deck at the PGL grade break')
    offsets=sorted(set([model.deck_left,0.,model.deck_right]))
    top=[((start_ft-model.start)*FT,y*FT,float(model.deck_top(start_ft,y))*FT) for y in offsets]
    bottom=[(x,y,z-model.deck_thickness*FT) for x,y,z in reversed(top)]
    face=plane_polygon(top+bottom)
    return face.extrude(App.Vector((end_ft-start_ft)*FT,0,float(model.pgl(end_ft)-model.pgl(start_ft))*FT))


def beam_solid(model, span_index, beam_index, start_ft=None, end_ft=None):
    """Exact FIB36 on the notebook's cambered soffit, optionally trimmed."""
    if abs(model.depth-3)>1e-10 or abs(model.flange-4)>1e-10:
        raise ValueError('Only the verified FIB36 section is supported')
    row=model.spans.iloc[span_index]
    a=float(row.start_ft) if start_ft is None else start_ft
    b=float(row.end_ft) if end_ft is None else end_ft
    z=model.evaluate([a,(a+b)/2,b],span_index)['bottom'][:,beam_index]*FT
    return quadratic_solid(fib36_wire(),(a-model.start)*FT,(b-model.start)*FT,*z,
                           offset_mm=model.offsets[beam_index]*FT)


def haunch_solid(model, span_index, beam_index, start_ft=None, end_ft=None):
    """Quadratic beam flange to exact underside of the sloping deck."""
    row=model.spans.iloc[span_index]
    a=float(row.start_ft) if start_ft is None else start_ft
    b=float(row.end_ft) if end_ft is None else end_ft
    if a < model.peak < b: raise ValueError('Split haunch at PGL grade break')
    left,right=model.offsets[beam_index]-model.flange/2,model.offsets[beam_index]+model.flange/2
    if left < 0 < right: raise ValueError('Haunch crossing deck crown needs a split profile')
    sections=[]
    for s in [a,(a+b)/2,b]:
        x=(s-model.start)*FT
        bottom=float(model.evaluate([s],span_index)['top'][0,beam_index])*FT
        sections.append([(x,left*FT,bottom),(x,right*FT,bottom),
            (x,right*FT,float(model.deck_top(s,right)-model.deck_thickness)*FT),
            (x,left*FT,float(model.deck_top(s,left)-model.deck_thickness)*FT)])
    return quadratic_polygon_solid(*sections)
