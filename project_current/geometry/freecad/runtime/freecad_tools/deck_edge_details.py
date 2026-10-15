"""Editable B4 deck edge details measured from the user-supplied working DXF.

Dimensions follow the section geometry, in feet in the unitless DXF. The
barrier inset is horizontal; groove dimensions follow the sloping soffit.
Only the two decks and four deck barriers use these opt-in controllers.
"""
import json
import math
import FreeCAD as App
import Part
from . import bridge, mse, mse_revision as rev

IN = 25.4
FT = 304.8
SOURCE_SHA256 = 'dcf8bfdb441372e08a24c903f88cd3c3d772bb1f2ccce8f0eb35859fd6d8ea07'
DECKS = ['BridgeDeckS1', 'BridgeDeckS2']
BARRIERS = [f'BarrierDeckS{i}{side}' for i in (1, 2) for side in ('L', 'R')]


def edge_tools(o, model, start, end):
    """Six analytic triangular prisms: four chamfers and two soffit V grooves."""
    c = o.PGL
    half = c.DeckWidth.Value / 2
    ch = o.EdgeChamfer.Value
    offset = o.DripGrooveOffset.Value
    width = o.DripGrooveWidth.Value
    depth = o.DripGrooveDepth.Value
    thick = c.DeckThickness.Value
    if min(ch, offset, width, depth) <= 0 or 2*ch >= thick or depth >= thick:
        raise ValueError('Invalid positive deck edge detail dimensions')
    if offset-width/2 <= ch or offset+width/2 >= half:
        raise ValueError('Drip groove conflicts with the chamfer or crown')
    x = (start-model.start)*FT
    direction = App.Vector((end-start)*FT, 0, float(model.pgl(end)-model.pgl(start))*FT)
    tools = []
    for side in (-1, 1):
        ztop = float(model.deck_top(start, side*half/FT))*FT
        zinside = float(model.deck_top(start, side*(half-IN)/FT))*FT
        slope = (zinside-ztop)/IN
        cosine = 1/math.sqrt(1+slope*slope)
        sine = slope*cosine
        zbottom = ztop-thick
        def point(u, z):
            return App.Vector(x, side*(half-u), z)
        def prism(coords):
            points = [point(u,z) for u,z in coords]
            return rev.closed_face(points).extrude(direction)
        tools.append(prism([(0,ztop), (0,ztop-ch), (ch*cosine,ztop+slope*ch*cosine)]))
        tools.append(prism([(0,zbottom), (ch*cosine,zbottom+slope*ch*cosine), (0,zbottom+ch)]))
        u1, u2 = (offset-width/2)*cosine, (offset+width/2)*cosine
        ua = offset*cosine-depth*sine
        za = zbottom+offset*sine+depth*cosine
        tools.append(prism([(u1,zbottom+slope*u1), (u2,zbottom+slope*u2), (ua,za)]))
    return tools


class DeckEdgeProxy(mse.Serializable):
    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        c = obj.PGL
        model = bridge.model(c)
        start, end = bridge.deck_limits(c, obj.SpanIndex)
        gross = bridge.shapes.deck_solid(model, start, end)
        shape = gross.cut(Part.makeCompound(edge_tools(obj,model,start,end))).removeSplitter()
        if not shape.isValid() or len(shape.Solids) != 1:
            raise ValueError('Invalid deck edge result '+obj.Name)
        obj.Shape = shape
        obj.Placement = c.Frame
        obj.NetVolume = shape.Volume
        obj.EdgeDetailRemovedVolume = gross.Volume-shape.Volume


class DeckBarrierProxy(mse.Serializable):
    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        if obj.WallProfile:
            raise ValueError('Deck barrier controller cannot be used on an MSE wall')
        c = obj.PGL
        model = bridge.model(c)
        start, end = bridge.deck_limits(c,obj.SpanIndex)
        inset = obj.DeckEdgeSetback.Value
        if inset < 0 or inset+8*IN >= c.DeckWidth.Value/2:
            raise ValueError('Invalid deck barrier inset')
        offset = obj.Side*(c.DeckWidth.Value/2-inset)
        points = [c.Frame.multVec(App.Vector((station-model.start)*FT, offset,
                  float(model.deck_top(station,offset/FT))*FT)) for station in (start,end)]
        path = Part.makeLine(*points)
        normal = c.Frame.Rotation.multVec(App.Vector(0,obj.Side,0))
        profile = [(n-8,z) for n,z in json.loads(obj.ProfileJSON)]
        shape = rev.section_sweep(path,normal,profile)
        if obj.TrimSources:
            shape = shape.cut(Part.makeCompound([s.Shape for s in obj.TrimSources])).removeSplitter()
        obj.Shape = shape
        obj.Path = Part.makeCompound([path])
        obj.NetVolume = shape.Volume
        obj.MeasuredLength = path.Length


def configure(doc):
    """Install the reviewed dimensions and rebuild only their direct features.

    Caller owns a disposable document or transaction and subsequent checks.
    This function does not save or recompute the document globally.
    """
    if not all(doc.getObject(n) for n in DECKS+BARRIERS):
        raise ValueError('Expected B4 decks and barriers are missing')
    changed = []
    for name in DECKS:
        obj = doc.getObject(name)
        for key, value in [('EdgeChamfer','0.75 in'), ('DripGrooveOffset','3 in'),
                           ('DripGrooveWidth','1 in'), ('DripGrooveDepth','0.5 in')]:
            rev.setprop(obj,'App::PropertyLength',key,value,'Deck edge details')
        rev.setprop(obj,'App::PropertyVolume','EdgeDetailRemovedVolume',0,'Deck edge details')
        rev.setprop(obj,'App::PropertyString','EdgeDetailSourceSHA256',SOURCE_SHA256,'Deck edge details')
        DeckEdgeProxy(obj)
        obj.Proxy.execute(obj)
        changed.append(name)
    mapping = json.loads(doc.MSECopingsAndBarriers.FinalDetailMapJSON)
    for name in BARRIERS:
        obj = doc.getObject(name)
        rev.setprop(obj,'App::PropertyLength','DeckEdgeSetback','1.5 in','Deck edge details')
        rev.setprop(obj,'App::PropertyString','EdgeDetailSourceSHA256',SOURCE_SHA256,'Deck edge details')
        DeckBarrierProxy(obj)
        obj.Proxy.execute(obj)
        final = doc.getObject(mapping[name])
        final.Proxy.execute(final)
        changed.extend([name,final.Name])
    return changed


def refresh(doc):
    """Refresh physical detail callouts and linked quantities without rebuilding beams."""
    changed = []
    hosts = set(DECKS+BARRIERS+[n+'Corrected' for n in BARRIERS])
    for obj in doc.SlabElevations.Group:
        if 'PointDefinitions' in obj.PropertiesList:
            specs = json.loads(obj.PointDefinitions)
            if any(s.get('source') in hosts or s.get('nominal') in hosts for s in specs):
                obj.Proxy.execute(obj)
                changed.append(obj.Name)
    for obj in doc.SlabElevations.Group:
        if 'Annotation' in obj.PropertiesList and obj.Annotation.Name in changed:
            obj.Proxy.execute(obj)
            changed.append(obj.Name)
    # All unmodified native Shapes are retained, including the cambered haunches.
    # This entry point is restricted to a clean starting document by the caller.
    for obj in doc.Objects:
        obj.purgeTouched()
    doc.BridgeConcreteSchedule.touch()
    doc.recompute([doc.BridgeConcreteSchedule])
    changed.append('BridgeConcreteSchedule')
    return changed


def physical_objects(doc):
    objects = {o.Name:o for o in doc.MSEAssembly.FinishedConcrete}
    objects.update({o.Name:o for o in doc.MSECopingsAndBarriers.FinishedDetails})
    objects.update({o.Name:o for o in doc.BridgeGeometryChecks.Components
                    if o.ComponentKind != 'WallEnvelope'})
    objects.update({o.Name:o for o in doc.Objects if 'Diameter' in o.PropertiesList
                    and 'Base' in o.PropertiesList and 'Shape' in o.PropertiesList})
    return {n:o for n,o in objects.items() if 'Shape' in o.PropertiesList and not o.Shape.isNull()}


def overlaps(doc):
    """Positive-volume physical intersections touching the six changed final objects."""
    rows = []
    mapping = json.loads(doc.MSECopingsAndBarriers.FinalDetailMapJSON)
    names = DECKS+[mapping[n] for n in BARRIERS]
    objects = physical_objects(doc)
    visited = set()
    for name in names:
        a = objects[name]
        for other,b in objects.items():
            pair = tuple(sorted((name,other)))
            if name == other or pair in visited:
                continue
            visited.add(pair)
            if a.Shape.BoundBox.intersect(b.Shape.BoundBox):
                v = abs(a.Shape.copy().common(b.Shape.copy()).Volume)
                if v > 0:
                    rows.append({'a':pair[0], 'b':pair[1], 'volume_in3':v/IN**3})
    return rows


def measure(doc):
    """Independent physical cross-section and volume measurements."""
    result = {'decks':[], 'barriers':[]}
    c = doc.BridgePGL
    model = bridge.model(c)
    for name in DECKS:
        obj = doc.getObject(name)
        start,end = bridge.deck_limits(c,obj.SpanIndex)
        mid = (start+end)/2
        x = (mid-model.start)*FT
        half = c.DeckWidth.Value/2
        z = float(model.pgl(mid))*FT
        plane = rev.closed_face([App.Vector(x,-half-IN,z+IN),App.Vector(x,half+IN,z+IN),
                                  App.Vector(x,half+IN,z-20*IN),App.Vector(x,-half-IN,z-20*IN)])
        shape = bridge.local_shape(obj)
        points = [v.Point for v in shape.section(plane).Vertexes]
        # Every corner of the analytic cutters must appear in the final physical
        # section except the removed virtual square deck-edge corners.
        tools = edge_tools(obj,model,mid,end)
        expected = []
        for i,tool in enumerate(tools):
            vertices = [v.Point for v in tool.Vertexes if abs(v.Point.x-x)<1e-6]
            if i % 3 != 2:
                vertices = [p for p in vertices if not (abs(abs(p.y)-half)<1e-6 and
                            min(abs(p.z-(z-.02*half)),abs(p.z-(z-.02*half-c.DeckThickness.Value)))<1e-6)]
            expected.extend(vertices)
        error = max(min(p.distanceToPoint(q) for q in points) for p in expected)
        cosine = 1/math.sqrt(1+.02**2)
        removed = (2*obj.EdgeChamfer.Value**2*cosine+
                   obj.DripGrooveWidth.Value*obj.DripGrooveDepth.Value)*(end-start)*FT
        gross = (end-start)*FT*c.DeckWidth.Value*c.DeckThickness.Value
        row = {'name':name,'valid':shape.isValid(),'solids':len(shape.Solids),
               'section_vertex_error_in':error/IN,
               'removed_volume_in3':(gross-shape.Volume)/IN**3,
               'expected_removed_volume_in3':removed/IN**3,
               'section_points_in':[[p.y/IN,(p.z-z)/IN] for p in points]}
        row['pass'] = row['valid'] and row['solids']==1 and error<=.001*IN and abs(gross-shape.Volume-removed)<shape.Volume*1e-8
        result['decks'].append(row)
    mapping = json.loads(doc.MSECopingsAndBarriers.FinalDetailMapJSON)
    for name in BARRIERS:
        raw = doc.getObject(name)
        final = doc.getObject(mapping[name])
        shape = final.Shape.copy()
        shape.Placement = c.Frame.inverse().multiply(shape.Placement)
        box = shape.BoundBox
        outside = abs(box.YMin if raw.Side<0 else box.YMax)
        row = {'name':final.Name,'outside_setback_in':(c.DeckWidth.Value/2-outside)/IN,
               'valid':shape.isValid(),'solids':len(shape.Solids)}
        row['pass'] = row['valid'] and row['solids']==1 and abs(row['outside_setback_in']-raw.DeckEdgeSetback.Value/IN)<=.001
        result['barriers'].append(row)
    result['clear_width_in'] = (c.DeckWidth.Value-2*(doc.getObject(BARRIERS[0]).DeckEdgeSetback.Value+8*IN))/IN
    result['pass'] = all(r['pass'] for r in result['decks']+result['barriers'])
    return result
