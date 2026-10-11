"""Export the observed beam's existing views as 1:1, XY, international-foot DXF.

No model save; no preference changes; no new geometry in the source document.
The pinned, pure-Python ezdxf wheel lives in tools/dxf, separate from MCP.
"""
import collections
import hashlib
import json
import math
import re
import sys
import traceback
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import Part
from . import beam, beam_hooks, beam_drawings, beam_fdot
from .geometry import bounds, length, result

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ('BeamAssemblySheet', 'BeamDetailSheet', 'BeamFdotAssemblySheet', 'BeamFdotDetailSheet')
VIEWS = ('BeamElevation', 'BeamPlan', 'BeamSection', 'BottomBarDetail', 'TopBarDetail', 'SideBarDetail', 'StirrupDetail')
KEYS = ('01_elevation', '02_plan', '03_section', '04_bottom_bar', '05_top_bar', '06_side_bar', '07_stirrup')
MM_PER_FOOT = 304.8
NS = {'s': 'http://www.w3.org/2000/svg'}
FDOT_LEVELS = {'BeamConc':2110,'BeamConc_h':2111,'Rebar':2250,'Rebar_h':2251}
LEVEL_SOURCE = 'https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/cadd/downloads/publications/caddmanualfdm/levels/fdotcaddstandardleveltable-10-25-2023.xlsx?sfvrsn=5c1b90b4_2'


def library():
    vendor = str(ROOT / 'tools/dxf/vendor')
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    import ezdxf
    if ezdxf.__version__ != '1.4.4' or not Path(ezdxf.__file__).resolve().is_relative_to(Path(vendor)):
        raise RuntimeError('Expected project-local pinned ezdxf 1.4.4')
    return ezdxf


def state(doc):
    s = beam_hooks.state(doc)
    s['brep_sha256'] = {o.Name: hashlib.sha256(o.Shape.exportBrepToString().encode()).hexdigest()
                        for o in doc.Objects if 'Shape' in o.PropertiesList and not o.Shape.isNull()}
    s['drawing_sources'] = {o.Name: [p.Name for p in o.Source] for o in doc.Objects if 'Source' in o.PropertiesList and o.Name in VIEWS}
    s['svg'] = {n: hashlib.sha256(doc.getObject(n).SvgContent.encode()).hexdigest()
                for n in ('BeamFdotAssemblySource', 'BeamFdotDetailsSource')}
    return s


def new_dxf():
    dx = library().new('R2010')
    dx.units = 2  # Autodesk INSUNITS: international feet, not US survey feet.
    dx.header['$MEASUREMENT'] = 0
    dx.header['$LUNITS'] = 2  # Decimal. Architectural/engineering styles imply inches.
    dx.header['$LUPREC'] = 8
    dx.header['$INSBASE'] = (0, 0, 0)
    dx.header['$LTSCALE'] = 1
    dx.header['$PSLTSCALE'] = 0
    dx.header['$FILLMODE'] = 1
    dx.header['$LWDISPLAY'] = False
    dx.linetypes.add('CADAI_HIDDEN', pattern=[0.125, 0.08333333333333333, -0.041666666666666664], description='Hidden, feet')
    dx.appids.add('CAD_AI')
    return dx


def level_name(material, kind):
    if material not in ('concrete','rebar'):
        raise ValueError('Unknown drawing material')
    return ('BeamConc' if material=='concrete' else 'Rebar')+('_h' if kind=='HIDDEN' else '')


def layer(dx, name, kind=None):
    if name not in FDOT_LEVELS:
        raise ValueError('Unverified FDOT layer name: '+name)
    if name not in dx.layers:
        dx.layers.add(name,color=7,linetype='CADAI_HIDDEN' if name.endswith('_h') else 'Continuous',lineweight=25)
    attrs={'layer':name}
    if kind:
        # Preserve the existing DXF presentation. Bentley level weights are
        # workspace-specific integer indices, not DXF hundredths of a millimeter.
        attrs['lineweight']={'HIDDEN':9,'OUTLINE':18,'VISIBLE':25,'CENTERLINE':40,'FILLED_ENDS':0}[kind]
    return attrs


def provenance(entity, material, kind, view, role):
    entity.set_xdata('CAD_AI',[(1000,s) for s in (material,kind,view,role)])
    return entity


def native_materials(doc, view, edges):
    """Prove material membership for the observed rectangular concrete beam.

    Concrete is the four projected box edges. Reinforcement is strictly inside
    that rectangle, independently required by physical cover validation. Refuse
    changed sources, additional concrete edges or ambiguous boundary geometry.
    """
    if view.Name not in VIEWS[:3]:
        expected={'BottomBarDetail':'BottomBarsCenterline','TopBarDetail':'TopBarsCenterline',
                  'SideBarDetail':'SideBarsLeftCenterline','StirrupDetail':'StirrupCenterline'}[view.Name]
        if [o.Name for o in view.Source]!=[expected]:
            raise ValueError('Unexpected detail source: '+view.Name)
        return ['rebar']*len(edges)
    if set(o.Name for o in view.Source)!=set(('ConcreteBeam',*beam.SETS)):
        raise ValueError('Unexpected assembly source objects')
    host=doc.ConcreteBeam
    if host.TypeId!='Part::Box' or len(host.Shape.Solids)!=1:
        raise ValueError('Material adapter requires the native concrete box')
    # Do not call projectPoint/getGeometricCenter here: in FreeCAD 1.1.3 those
    # accessors alter flags in the shared source BReps (caught by exact hashes).
    # For the supported orthographic box views, independently measured nominal
    # BRep dimensions give the same centered rectangle without that side effect.
    direction,xdir,axes={
        'BeamElevation':((0,-1,0),(1,0,0),('XLength','ZLength')),
        'BeamPlan':((0,0,1),(1,0,0),('XLength','YLength')),
        'BeamSection':((1,0,0),(0,1,0),('YLength','ZLength'))}[view.Name]
    if view.Direction.distanceToPoint(App.Vector(*direction))>1e-12 or view.XDirection.distanceToPoint(App.Vector(*xdir))>1e-12:
        raise ValueError('Material classification requires the tested orthographic directions')
    physical=bounds(host.Shape);scale=float(view.Scale)
    w,h=(getattr(physical,key)*scale for key in axes)
    box=(-w/2,-h/2,w/2,h/2)
    actual=beam_drawings.projection_box(view)
    eps=length('0.001 in')*scale
    if max(abs(a-b) for a,b in zip(actual,box))>eps:
        raise ValueError('Projected bounds do not match physical concrete')
    sides=[((box[0],box[1]),(box[0],box[3])),((box[2],box[1]),(box[2],box[3])),
           ((box[0],box[1]),(box[2],box[1])),((box[0],box[3]),(box[2],box[3]))]
    materials=[];found=[]
    for edge,kind in edges:
        points=[edge.valueAt(edge.FirstParameter),edge.valueAt(edge.LastParameter)]
        match=[]
        if isinstance(edge.Curve,(Part.Line,Part.LineSegment)):
            for index,(a,b) in enumerate(sides):
                xy=[(p.x,p.y) for p in points]
                error=min(max(math.dist(xy[0],a),math.dist(xy[1],b)),max(math.dist(xy[0],b),math.dist(xy[1],a)))
                if error<=eps:match.append(index)
        if len(match)==1:
            found.append((kind,match[0]));materials.append('concrete')
        elif match:
            raise ValueError('Ambiguous concrete boundary')
        else:
            bb=bounds(edge)
            if not (bb.XMin>box[0]+eps and bb.XMax<box[2]-eps and bb.YMin>box[1]+eps and bb.YMax<box[3]-eps):
                raise ValueError('Unclassified projection touches concrete boundary')
            materials.append('rebar')
    expected=[('VISIBLE',side) for side in range(4)]
    if view.Name!='BeamSection':
        # The back face's four edges project onto the same rectangle and are
        # reported separately by native HLR as hidden. Keep all original edges.
        expected += [('HIDDEN',side) for side in range(4)]
    if sorted(found)!=sorted(expected):
        raise ValueError('Unexpected physical concrete edge/visibility classification: '+str(found))
    return materials


def add_edge(msp, edge, xy, factor, attrs):
    """Preserve projected analytic curves. Reflection converts TechDraw Y-down to CAD Y-up."""
    c = edge.Curve
    if isinstance(c, (Part.Line, Part.LineSegment)):
        return msp.add_line(xy(edge.valueAt(edge.FirstParameter)), xy(edge.valueAt(edge.LastParameter)), dxfattribs=attrs)
    if isinstance(c, Part.Circle):
        center = xy(c.Center)
        if edge.isClosed():
            return msp.add_circle(center, c.Radius * factor, dxfattribs=attrs)
        p, q = xy(edge.valueAt(edge.FirstParameter)), xy(edge.valueAt(edge.LastParameter))
        a = math.degrees(math.atan2(p[1]-center[1], p[0]-center[0])) % 360
        b = math.degrees(math.atan2(q[1]-center[1], q[0]-center[0])) % 360
        # Reflection reverses orientation of a circle with original +Z normal.
        if c.Axis.z > 0:
            a, b = b, a
        return msp.add_arc(center, c.Radius * factor, a, b, dxfattribs=attrs)
    if isinstance(c, Part.Ellipse):
        major = (c.XAxis.x*c.MajorRadius*factor, -c.XAxis.y*c.MajorRadius*factor, 0)
        a, b = edge.FirstParameter, edge.LastParameter
        if c.Axis.z > 0:
            a, b = -b, -a
        # DXF allows wrapping, but limits a complete ellipse to one revolution.
        sweep = b-a
        a %= 2*math.pi
        b = a+sweep
        return msp.add_ellipse(xy(c.Center), major, c.MinorRadius/c.MajorRadius, a, b, dxfattribs=attrs)
    s = edge.toNurbs().Edges[0].Curve
    if not isinstance(s, Part.BSplineCurve):
        raise ValueError('Unsupported projected curve: '+type(c).__name__)
    s.segment(edge.FirstParameter, edge.LastParameter)
    if s.isPeriodic():
        s.setNotPeriodic()
    ent = msp.add_spline(degree=s.Degree, dxfattribs=attrs)
    ent.control_points = [xy(p) for p in s.getPoles()]
    ent.knots = [k for k, m in zip(s.getKnots(), s.getMultiplicities()) for _ in range(m)]
    if s.isRational():
        ent.weights = s.getWeights()
        ent.dxf.flags = 4
    ent.dxf.flags |= 8  # planar
    return ent


def native_view(doc, name):
    v = doc.getObject(name)
    if v.Perspective or abs(v.Rotation.Value) > 1e-12:
        raise ValueError('Adapter requires orthographic, unrotated view: '+name)
    beam_drawings.wait_projection(doc, v)
    edges = [(e, 'VISIBLE') for e in v.getVisibleEdges(False)] + [(e, 'HIDDEN') for e in v.getHiddenEdges(False)]
    if not edges:
        raise ValueError('Empty projection: '+name)
    bb = beam_drawings.projection_box(v)
    factor = 1 / float(v.Scale) / MM_PER_FOOT
    xy = lambda p: ((p.x-bb[0])*factor, (bb[3]-p.y)*factor, 0)
    dx = new_dxf()
    materials=native_materials(doc,v,edges)
    expected=[]
    for (e,kind),material in zip(edges,materials):
        target=level_name(material,kind)
        provenance(add_edge(dx.modelspace(),e,xy,factor,layer(dx,target,kind)),material,kind,name,'native-projection')
        expected.append((e,target))
    return dx, {'source': name, 'paper_scale': float(v.Scale), 'bounds_ft': [0, 0, (bb[2]-bb[0])*factor, (bb[3]-bb[1])*factor],
                'source_edges':len(edges),'material_counts':dict(collections.Counter(materials)),
                'visible_edges': sum(k=='VISIBLE' for e,k in edges), 'hidden_edges': sum(k=='HIDDEN' for e,k in edges)}, (expected, bb, factor)


def svg_views(doc):
    """Select only tagged geometry from the already linked, checked sheet SVGs."""
    assembly = ET.fromstring(doc.BeamFdotAssemblySource.SvgContent)
    detail = ET.fromstring(doc.BeamFdotDetailsSource.SvgContent)
    # Fail stale symbolic sources rather than exporting old geometry.
    if doc.BeamFdotAssemblySource.SvgContent != beam_fdot.assembly_svg(doc) or doc.BeamFdotDetailsSource.SvgContent != beam_fdot.detail_svg(doc):
        raise ValueError('Symbolic source is stale; refresh the sheets first')
    rects = assembly.findall('s:rect', NS)
    if len(rects) != 3:
        raise ValueError('Unexpected symbolic concrete outlines')
    groups = [('elevation-rebar','elevation-stirrups'), ('plan-rebar',), ('section-stirrup', 'section-bars'),
              ('detail-BottomBars',), ('detail-TopBars',), ('detail-SideBarsLeft',), ('detail-Stirrups',)]
    output = []
    for i, ids in enumerate(groups):
        root = assembly if i < 3 else detail
        lines, dots = [], []
        for group in ids:
            matches = root.findall("s:g[@id='%s']" % group, NS)
            if len(matches) != 1:
                raise ValueError('Missing/ambiguous SVG group '+group)
            for el in matches[0]:
                if el.tag.endswith('polyline') and el.get('data-role') in ('rebar-centerline','stirrup-elevation-line'):
                    pts = [tuple(map(float, p.split(','))) for p in el.attrib['points'].split()]
                    lines.append((pts, 'CENTERLINE', el.get('data-role')))
                elif el.tag.endswith('circle') and el.get('data-role') in ('end-on', 'section-bar','stirrup-elevation-end'):
                    dots.append((float(el.get('cx')), float(el.get('cy')), float(el.get('r')),el.get('data-role')))
                else:
                    raise ValueError('Unexpected geometry in '+group)
        if i < 3:
            a = rects[i].attrib
            x,y,w,h = [float(a[k]) for k in ('x','y','width','height')]
            lines.append(([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)], 'OUTLINE','concrete-outline'))
        pts = [p for path,k,role in lines for p in path]
        pts += [(x-r,y-r) for x,y,r,role in dots]+[(x+r,y+r) for x,y,r,role in dots]
        if not pts:
            raise ValueError('Empty symbolic view')
        xmin,xmax = min(p[0] for p in pts),max(p[0] for p in pts)
        ymin,ymax = min(p[1] for p in pts),max(p[1] for p in pts)
        factor = 1 / beam_fdot.SCALE / MM_PER_FOOT
        xy = lambda p: ((p[0]-xmin)*factor, (ymax-p[1])*factor)
        dx = new_dxf()
        msp = dx.modelspace()
        for path,kind,role in lines:
            material='concrete' if kind=='OUTLINE' else 'rebar'
            attrs = layer(dx,level_name(material,kind),kind)
            if len(path)==2:
                e=msp.add_line(xy(path[0]), xy(path[1]), dxfattribs=attrs)
            else:
                e=msp.add_lwpolyline([xy(p) for p in path], dxfattribs=attrs)
            provenance(e,material,kind,KEYS[i],role)
        for x,y,r,role in dots:
            center,radius = xy((x,y)), r*factor
            attrs = layer(dx,level_name('rebar','FILLED_ENDS'),'FILLED_ENDS')
            provenance(msp.add_circle(center,radius,dxfattribs=attrs),'rebar','FILLED_ENDS',KEYS[i],role)
            hatch = msp.add_hatch(color=7, dxfattribs=attrs)
            hatch.paths.add_edge_path().add_arc(center,radius,0,360,ccw=True)
            provenance(hatch,'rebar','FILLED_ENDS',KEYS[i],role)
        output.append((dx, {'source': list(ids), 'paper_scale': beam_fdot.SCALE,
                            'bounds_ft': [0,0,(xmax-xmin)*factor,(ymax-ymin)*factor],
                            'centerline_paths':sum(k=='CENTERLINE' for p,k,r in lines), 'filled_circles':len(dots),
                            'stirrup_elevation_lines':sum(r=='stirrup-elevation-line' for p,k,r in lines),
                            'stirrup_elevation_end_circles':sum(role=='stirrup-elevation-end' for x,y,r,role in dots),
                            'symbol_radius_ft': 0.5*factor, 'svg_curve_deflection_mm':0.025,
                            'svg_coordinate_rounding_mm_max_per_axis':0.0000005/beam_fdot.SCALE}))
    return output


def entity_points(e, count=9):
    typ = e.dxftype()
    if typ == 'LINE':
        return [e.dxf.start, e.dxf.end]
    if typ == 'CIRCLE':
        return list(e.vertices([360*i/(count-1) for i in range(count)]))
    if typ == 'ARC':
        return list(e.vertices(e.angles(count)))
    if typ == 'ELLIPSE':
        return list(e.vertices(e.params(count)))
    if typ == 'SPLINE':
        return list(e.construction_tool().approximate(count-1))
    if typ == 'LWPOLYLINE':
        return list(e.vertices_in_wcs())
    if typ == 'HATCH':
        return [e.dxf.elevation]
    raise ValueError('Unsupported DXF entity '+typ)


def audit_file(path, info, original=None, tolerance_mm=0.0254):
    dx = library().readfile(path)
    audit = dx.audit()
    ents = list(dx.modelspace())
    checks = [result('dxf_audit', not audit.errors and not audit.fixes, errors=len(audit.errors), repairs=len(audit.fixes)),
              result('units_feet', dx.units == 2 and dx.header['$LUNITS']==2 and tuple(dx.header['$INSBASE'])==(0,0,0)),
              result('flat_modelspace_only', all(abs(p.z)<1e-12 for e in ents for p in entity_points(e)) and len(dx.paperspace())==0),
              result('entity_count', len(ents)==info['entity_count'], count=len(ents))]
    materials=collections.Counter();roles=collections.Counter();layer_ok=True
    for e in ents:
        values=[tag.value for tag in e.get_xdata('CAD_AI') if tag.code==1000]
        if len(values)!=4:
            raise ValueError('Missing material/view provenance')
        material,kind,view,role=values
        materials[material]+=1;roles[role]+=1
        layer_ok &= e.dxf.layer==level_name(material,kind)
        layer_ok &= dx.layers.get(e.dxf.layer).dxf.linetype==('CADAI_HIDDEN' if kind=='HIDDEN' else 'Continuous')
    checks.append(result('fdot_material_layers',bool(layer_ok),material_entity_counts=dict(materials),populated_layers=sorted(set(e.dxf.layer for e in ents))))
    if 'material_counts' in info:
        checks.append(result('material_counts_match_source',dict(materials)==info['material_counts']))
    if 'stirrup_elevation_lines' in info:
        getrole=lambda e:[tag.value for tag in e.get_xdata('CAD_AI') if tag.code==1000][-1]
        lines=[e for e in ents if getrole(e)=='stirrup-elevation-line']
        circles=[e for e in ents if getrole(e)=='stirrup-elevation-end' and e.dxftype()=='CIRCLE']
        hatches=[e for e in ents if getrole(e)=='stirrup-elevation-end' and e.dxftype()=='HATCH']
        okay=len(lines)==info['stirrup_elevation_lines'] and len(circles)==len(hatches)==info['stirrup_elevation_end_circles']==2*len(lines)
        for e in lines:
            okay &= e.dxftype()=='LINE' and abs(e.dxf.start.x-e.dxf.end.x)<1e-12 and abs(e.dxf.start.y-e.dxf.end.y)>0
            okay &= all(sum(c.dxf.center.distance(p)<1e-12 for c in circles)==1 for p in (e.dxf.start,e.dxf.end))
        checks.append(result('symbolic_stirrup_straight_lines_and_ends',bool(okay),lines=len(lines),end_circles=len(circles),end_fills=len(hatches)))
    if 'filled_circles' in info:
        hatches = [e for e in ents if e.dxftype()=='HATCH']
        circles = [e for e in ents if e.dxftype()=='CIRCLE']
        fill_ok = len(hatches)==len(circles)==info['filled_circles']
        for h,c in zip(hatches,circles):
            fill_ok &= h.dxf.solid_fill==1 and len(h.paths)==1 and len(h.paths[0].edges)==1
            if fill_ok:
                a = h.paths[0].edges[0]
                fill_ok &= abs(a.radius-c.dxf.radius)<1e-12 and math.dist(a.center,tuple(c.dxf.center)[:2])<1e-12 and a.start_angle==0 and a.end_angle==360
        checks.append(result('filled_circle_boundaries', bool(fill_ok), circles=len(circles), solid_hatches=len(hatches)))
    if original:
        edges,bb,factor = original
        if len(ents)!=len(edges):
            checks.append(result('projection_geometry',False,reason='Edge count changed'))
        else:
            worst = 0.0
            endpoint_error = 0.0
            for entity,(edge,kind) in zip(ents,edges):
                if entity.dxf.layer!=kind:
                    raise ValueError('Source material/visibility layer mismatch')
                points = entity_points(entity)
                for p in points:
                    q = App.Vector(p.x/factor+bb[0],bb[3]-p.y/factor,0)
                    error = edge.distToShape(Part.Vertex(q))[0] * factor*MM_PER_FOOT
                    worst = max(worst,error)
                if not edge.isClosed():
                    a,b = (edge.valueAt(t) for t in (edge.FirstParameter,edge.LastParameter))
                    ends = [App.Vector(p.x/factor+bb[0],bb[3]-p.y/factor,0) for p in (points[0],points[-1])]
                    endpoint_error = max(endpoint_error,min(max(ends[0].distanceToPoint(a),ends[1].distanceToPoint(b)),
                                                           max(ends[0].distanceToPoint(b),ends[1].distanceToPoint(a)))*factor*MM_PER_FOOT)
            checks.append(result('projection_geometry',max(worst,endpoint_error)<=tolerance_mm,max_sample_error_mm=worst,
                                 endpoint_error_mm=endpoint_error,samples_per_curve=9,tolerance_mm=tolerance_mm))
    info['entity_types'] = dict(collections.Counter(e.dxftype() for e in ents))
    info['layers'] = dict(collections.Counter(e.dxf.layer for e in ents))
    info['material_entity_counts']=dict(materials)
    info['geometry_roles']=dict(roles)
    info['sha256'] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    info['checks'] = checks
    if any(c['status']=='FAIL' for c in checks):
        raise ValueError('DXF audit failed: '+str(path)+' '+json.dumps(checks))
    return dx


def write_file(dx, path, info, original=None, tolerance_mm=0.0254):
    info['filename'] = str(path.name)
    info['entity_count'] = len(dx.modelspace())
    # Header extents are advisory. Geometry itself carries the actual scale.
    if 'bounds_ft' in info:
        b = info['bounds_ft']
        dx.modelspace().dxf.extmin = (b[0],b[1],0)
        dx.modelspace().dxf.extmax = (b[2],b[3],0)
        dx.set_modelspace_vport(height=max(b[3]-b[1],1)*1.15, center=((b[0]+b[2])/2,(b[1]+b[3])/2))
    dx.saveas(path)
    return audit_file(path,info,original,tolerance_mm)


def preview(dx,path):
    from ezdxf.addons.drawing import RenderContext, Frontend, layout, svg
    from ezdxf.addons.drawing.config import Configuration, ColorPolicy, BackgroundPolicy
    backend = svg.SVGBackend()
    config = Configuration(color_policy=ColorPolicy.BLACK,background_policy=BackgroundPolicy.WHITE)
    Frontend(RenderContext(dx),backend,config=config).draw_layout(dx.modelspace(),finalize=True)
    content = backend.get_string(layout.Page(420,297,margins=layout.Margins.all(10)))
    path.write_text(content,encoding='utf-8')
    from PySide import QtCore,QtGui,QtSvg
    renderer=QtSvg.QSvgRenderer(QtCore.QByteArray(content.encode()))
    image=QtGui.QImage(1680,1188,QtGui.QImage.Format_ARGB32)
    image.fill(QtGui.QColor('white'))
    painter=QtGui.QPainter(image);renderer.render(painter);painter.end()
    if not image.save(str(path.with_suffix('.png'))):
        raise RuntimeError('Preview render failed')


def queue_package_previews(directory):
    """Render saved DXFs on the GUI event loop, outside the short MCP request.

    Poll preview-status.json; never repeat a QUEUED/RUNNING request. No models
    are read or changed. Verify the package hashes before rendering.
    """
    from .api import atomic
    from PySide import QtCore
    folder=Path(directory).resolve()
    if not folder.is_relative_to(ROOT):
        raise ValueError('Preview output must stay inside CAD_AI')
    status=folder/'preview-status.json'
    if status.exists():
        return json.loads(status.read_text(encoding='utf-8'))
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    files=[f for f in manifest['files'] if f['view']=='all_views']
    if len(files)!=2:
        raise ValueError('Expected two combined view sets')
    for f in files:
        if hashlib.sha256((folder/f['filename']).read_bytes()).hexdigest()!=f['sha256']:
            raise ValueError('DXF changed after export: '+f['filename'])
    rec={'status':'QUEUED','outputs':[],'errors':[],'models_accessed':False}
    atomic(status,rec)
    def render():
        try:
            rec['status']='RUNNING';atomic(status,rec)
            for f in files:
                rec['current']=f['category'];atomic(status,rec)
                path=folder/(f['category']+'_preview.svg')
                preview(library().readfile(folder/f['filename']),path)
                rec['outputs'].append(str(path.with_suffix('.png')));atomic(status,rec)
            rec['status']='PASS'
        except Exception as exc:
            rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc()
        atomic(status,rec)
    QtCore.QTimer.singleShot(0,render)
    return dict(rec)


def export(job):
    from .api import document, atomic, compact, check_gui
    if job.get('units')!='ft' or tuple(job.get('targets',[]))!=TARGETS:
        raise ValueError('Explicit targets must be all four beam sheets, and units must be ft')
    doc = document(job.get('document'))
    tol = length(job.get('tolerance','0.001 in'),positive=True)
    rid = job.get('request_id',uuid.uuid4().hex)
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',rid):
        raise ValueError('Invalid request_id')
    report_path = ROOT/'reports/transactions'/(rid+'.json')
    if report_path.exists():
        prior = json.loads(report_path.read_text(encoding='utf-8'))
        if prior['request']!=job:
            raise ValueError('request_id already used for another job')
        if prior['status']=='PREPARED':
            raise RuntimeError('Interrupted export; inspect existing files before retry')
        return compact(prior)
    folder = Path(job.get('output_directory', ROOT/'exports'/doc.Name/rid)).resolve()
    if not folder.is_relative_to(ROOT) or folder==ROOT or folder.exists():
        raise ValueError('Output must be a new directory inside CAD_AI')
    rec = {'timestamp':datetime.now(timezone.utc).isoformat(),'operation':'export_beam_dxf','document':doc.Name,
           'transaction_id':rid,'request':job,'status':'PREPARED','report_path':str(report_path),'output_directory':str(folder),
           'units':'international feet (1 ft = 304.8 mm)','scale':'1:1','model_saved':False,'checks':[],'errors':[],
           'warnings':['OBM import not tested in Bentley. Set DXF units to Feet and verify the 8 ft concrete length.',
                       'DXFs are export snapshots. R-02 source bar details are centerline views already.',
                       'Symbolic circles preserve the sheet symbol size, not physical bar diameter; curves retain the existing SVG tessellation.',
                       'Exact FDOT 2D level names are used. Apply the receiving FDOT workspace level symbology in OBM; DXF and Bentley color/weight indices are not equivalent.',
                       'Symbolic elevation stirrups are straight line/dot symbols at nominal stations; section and bar detail retain actual centerline shapes.'], 'files':[]}
    atomic(report_path,rec)
    before = None
    try:
        check_gui(doc)
        for n in TARGETS+VIEWS:
            if doc.getObject(n) is None:
                raise ValueError('Missing required object '+n)
        before = state(doc)
        rec['source_state_before']=before
        doc.recompute()
        # Full existing physical checks stay enabled for this export operation.
        source_checks,_ = beam.validate(doc,tol)
        rec['checks'].extend(source_checks)
        if any(c['status']=='FAIL' for c in source_checks):
            raise ValueError('Source validation failed; see report')
        symbolic = svg_views(doc)
        folder.mkdir(parents=True)
        layout_rows = []
        for category in ('full_geometry','representational'):
            dest = folder/category;dest.mkdir()
            combined = new_dxf()
            # Each pair on a row, with a 2 ft gap. Lower-left view origins recorded.
            y=0.0
            row_height=0.0
            x=0.0
            for i,(key,name) in enumerate(zip(KEYS,VIEWS)):
                if i%2==0:
                    if i:
                        y += row_height+2
                    x=0.0;row_height=0.0
                if category=='full_geometry':
                    dx,info,original = native_view(doc,name)
                else:
                    dx,info = symbolic[i];original=None
                info.update({'category':category,'view':key})
                saved = write_file(dx,dest/(key+'.dxf'),info,original,tol)
                rec['files'].append(info)
                rec['checks'].extend(dict(c,name=category+'/'+key+'/'+c['name']) for c in info['checks'])
                for ent in saved.modelspace():
                    copy=ent.copy()
                    layer(combined,copy.dxf.layer)
                    copy.translate(x,y,0)
                    combined.modelspace().add_entity(copy)
                info['combined_origin_ft']=[x,y,0]
                b=info['bounds_ft'];width=b[2]-b[0];height=b[3]-b[1]
                row_height=max(row_height,height);x+=width+2
                layout_rows.append({'category':category,'view':key,'origin_ft':info['combined_origin_ft']})
            ci={'category':category,'view':'all_views','component_count':7}
            combined=write_file(combined,folder/(category+'_all_views_ft.dxf'),ci,tolerance_mm=tol)
            rec['files'].append(ci)
            rec['checks'].extend(dict(c,name=category+'/combined/'+c['name']) for c in ci['checks'])
            if job.get('include_previews',False):
                preview(combined,folder/(category+'_preview.svg'))
        rec['checks'].append(result('original_model_and_sources_unchanged',state(doc)==before))
        if any(c['status']=='FAIL' for c in rec['checks']):
            raise ValueError('Export checks failed')
        manifest = {'document':doc.Name,'units':rec['units'],'scale':'1:1','coordinate_plane':'XY, Z=0',
                    'format':'ASCII DXF R2010/AC1024','individual_origin':'lower-left of exported geometry',
                    'annotations':'No dimensions, text, leaders, title blocks, schedules or sheet borders',
                    'fdot_levels':FDOT_LEVELS,'level_source':LEVEL_SOURCE,
                    'combined_layers':'Exact FDOT names without view prefixes; view identity in CAD_AI XDATA and manifest offsets',
                    'files':rec['files'],'warnings':rec['warnings'],'combined_layout':layout_rows}
        atomic(folder/'manifest.json',manifest)
        rec['manifest']=str(folder/'manifest.json')
        rec['status']='PASS'
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc()
        if before is not None:
            after=state(doc)
            rec['checks'].append(result('original_model_and_sources_unchanged_after_failure',after==before))
            if after!=before:
                rec['preservation_differences']={k:{'before':before.get(k),'after':after.get(k)} for k in set(before)|set(after) if before.get(k)!=after.get(k)}
    atomic(report_path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:
        small=compact(rec);small.pop('files',None);small.pop('source_state_before',None);small.pop('preservation_differences',None);f.write(json.dumps(small)+'\n')
    summary=compact(rec);summary.pop('files',None);summary.pop('source_state_before',None);summary.pop('preservation_differences',None)
    summary['dxf_count']=len(rec['files'])
    return summary
