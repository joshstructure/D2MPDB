"""Native 90-degree cheek horizontal-bar hooks into adjacent concrete.

Hooks retain the selected mat levels. The end offset is measured to the bar
centreline from the cap end face. Bend diameter and straight tail are editable
lengths, bounded by the standard main-bar hook minima (not tie-hook minima).
Geometric fit is separate from required development/connection design.
"""
import copy,json,math
import FreeCAD as App
import Part
from . import cheek_steel as cheek, cap_cages as cap, design_steel as steel
from .mse import Serializable,prop
from .geometry import bounds,length,result,pair

IN=25.4
FT=304.8
TOL=.0254
STANDARD_URL='https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/design/standardplans/2027/idx/415-001.pdf?sfvrsn=86261df5_1'

def local(shape,frame):
    s=shape.copy();s.Placement=frame.inverse().multiply(s.Placement);return s

def envelope(inp):
    shapes=[local(o.Shape,inp.CageFrame) for o in (inp.Host,inp.Cap,inp.Backwall)]
    shape=shapes[0].multiFuse(shapes[1:]).removeSplitter()
    shape.Placement=inp.CageFrame.multiply(shape.Placement)
    return shape

def bent_row(inp,straight,ends):
    row=copy.deepcopy(straight)
    db=row['diameter'];inside=inp.HookInsideDiameter.Value/IN;tail=inp.HookTailLength.Value/IN
    if row['bar']!=4:raise ValueError('This qualified hook adapter requires #4 main bars')
    if inside<6*db-1e-10 or tail<12*db-1e-10:raise ValueError('Hook below standard 6db inside bend / 12db straight tail')
    R=(inside+db)/2
    a,b,*_=cheek.web_limits(inp);a/=IN;b/=IN
    p0,p1=straight['points'];y,z=p0[1:];direction=1 if inp.Host.BeamIndex==0 else -1
    xlo=a+length(ends['start']['offset'])/IN if 'start' in ends else p0[0]
    xhi=b-length(ends['end']['offset'])/IN if 'end' in ends else p1[0]
    points=[];segments=[]
    def point(x,y):points.append((x,y,z));return len(points)-1
    if 'start' in ends:
        tip=point(xlo,y+direction*(R+tail));bend=point(xlo,y+direction*R)
        mid=point(xlo+R*(1-1/math.sqrt(2)),y+direction*R*(1-1/math.sqrt(2)))
        left=point(xlo+R,y);segments += [('line',tip,bend),('arc',bend,mid,left)]
    else:left=point(xlo,y)
    if 'end' in ends:
        right=point(xhi-R,y);mid=point(xhi-R*(1-1/math.sqrt(2)),y+direction*R*(1-1/math.sqrt(2)))
        bend=point(xhi,y+direction*R);tip=point(xhi,y+direction*(R+tail))
        segments += [('line',left,right),('arc',right,mid,bend),('line',bend,tip)]
    else:
        right=point(xhi,y);segments.append(('line',left,right))
    if points[right][0]<=points[left][0]:raise ValueError('Hooks leave no straight mat segment')
    row.update(points=points,segments=segments,hook_ends=ends,core=[points[left],points[right]],
               family='Centered horizontal; '+ ' / '.join(v['receiver_kind']+' 90deg' for v in ends.values()))
    return row

def layout(inp):
    rows=cheek.layout(inp);settings=json.loads(inp.HorizontalHooksJSON)
    for ident,ends in settings.items():
        if ident not in rows or not ident.startswith('MH'):raise ValueError('Hook references missing horizontal row')
        if set(ends)-{'start','end'} or not ends:raise ValueError('Invalid hook end selection')
        rows[ident]=bent_row(inp,rows[ident],ends)
    return rows

class InputsProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        o.CageFrame=o.PGL.Frame;o.LayoutJSON=json.dumps(layout(o))
        if o.AutoSync:steel.sync_wall(o)

def configure(inp,settings):
    prop(inp,'App::PropertyLink','Backwall',inp.Document.getObject('BridgeBackwall'+inp.Host.SupportID),'Horizontal hooks')
    prop(inp,'App::PropertyLength','HookInsideDiameter','3 in','Horizontal hooks')
    prop(inp,'App::PropertyLength','HookTailLength','6 in','Horizontal hooks')
    prop(inp,'App::PropertyString','HorizontalHooksJSON',json.dumps(settings),'Horizontal hooks')
    prop(inp,'App::PropertyString','HookStandard',STANDARD_URL+'; #4 main bar, Style 3: 3 in inside diameter, 6 in tangent tail, 8 in out-to-out hook.','Horizontal hooks')
    prop(inp,'App::PropertyString','HookDesignStatus','Geometry only. Required development length, joint transfer and connection design NOT VERIFIED.','Horizontal hooks')
    InputsProxy(inp)

def refresh(inp):
    """Rebuild only changed analytic paths; retain unchanged native bar BReps."""
    previous=json.loads(inp.LayoutJSON)
    inp.Proxy.execute(inp)
    current=json.loads(inp.LayoutJSON);doc=inp.Document
    q=doc.getObject(inp.Prefix+'Quantities')
    for bar in q.Bars:
        ident=bar.Base.BarID
        if previous.get(ident)!=current[ident]:
            bar.Base.Proxy.execute(bar.Base);bar.Proxy.execute(bar)
    q.Proxy.execute(q)
    sh=doc.getObject(inp.Prefix+'Schedule');steel.write_wall_schedule(inp,sh,q.Bars)
    for o in doc.Objects:o.purgeTouched()
    sh.touch();doc.recompute([sh])

def swept(row,frame):
    wire=cap.analytic_wire(row);edge=wire.Edges[0]
    profile=Part.Wire([Part.makeCircle(row['diameter']*IN/2,edge.valueAt(edge.FirstParameter),edge.tangentAt(edge.FirstParameter))])
    s=wire.makePipeShell([profile],True,False);s.Placement=frame
    return s

def solid_cover(shape,host,frame=None,minimum=2*IN):
    if frame is not None:shape=local(shape,frame);host=local(host,frame)
    outside=abs(shape.cut(host).Volume)
    cover=min(shape.distToShape(face)[0] for face in host.Faces)
    return result('union_concrete_cover',outside<=1e-7 and cover+TOL>=minimum,cover_in=cover/IN,required_in=minimum/IN,outside_mm3=outside)

def steel_objects(doc):
    return [o for o in doc.Objects if 'Shape' in o.PropertiesList and
            all(k in o.PropertiesList for k in ('Diameter','Amount','Base'))]

def collisions(shape,objects,exclude,frame=None):
    failures=[];nearest=None
    bb=shape.BoundBox
    for obj in objects:
        if obj.Name==exclude:continue
        other=obj.Shape.copy();ob=other.BoundBox
        if any(getattr(bb,k+'Min')>getattr(ob,k+'Max')+IN or getattr(ob,k+'Min')>getattr(bb,k+'Max')+IN for k in 'XYZ'):continue
        c=pair(local(shape,frame),local(other,frame),0.,TOL) if frame is not None else pair(shape.copy(),other,0.,TOL)
        if nearest is None or c['distance_in']<nearest['distance_in']:nearest=dict(other=obj.Name,**c)
        if c['status']=='FAIL':failures.append(dict(other=obj.Name,**c))
    return failures,nearest

def validate(doc):
    checks=[];measurements=[];schedule=[];objects=steel_objects(doc);details=[]
    for name in cheek.HOSTS:
        inp=doc.getObject('Steel'+name+'Inputs');q=doc.getObject(inp.Prefix+'Quantities')
        checks+=steel.wall_geometry_checks(inp)
        host=envelope(inp);rows=json.loads(inp.LayoutJSON);straight=cheek.layout(inp)
        a,b,n0,n1,z0,z1=cheek.web_limits(inp);levels=[];vertical=[];hook_count=0
        for bar in q.Bars:
            ident=bar.Base.BarID;row=rows[ident];shape=bar.Shape.copy()
            c=solid_cover(shape,host,inp.CageFrame,inp.Cover.Value);c['name']=bar.Name+'_assembly_cover';checks.append(c)
            hooks=row.get('hook_ends',{});hook_count+=len(hooks)
            ls=local(bar.Base.Shape,App.Placement())
            arcs=[e for e in ls.Edges if isinstance(e.Curve,Part.Circle)]
            radius=(inp.HookInsideDiameter.Value+bar.Diameter.Value)/2
            checks.append(result(bar.Name+'_standard_hook_bends',inp.HookInsideDiameter.Value>=6*bar.Diameter.Value-TOL and len(arcs)==len(hooks) and all(abs(e.Curve.Radius-radius)<TOL and abs(e.Length/e.Curve.Radius-math.pi/2)<1e-8 for e in arcs),hooks=len(hooks)))
            if ident.startswith('MH'):
                levels.append(row['points'][0][2]*IN)
                expected=straight[ident]['points'][0]
                core=row.get('core',row['points'])
                checks.append(result(bar.Name+'_retained_mat_plane_and_level',all(abs(p[1]-expected[1])<1e-8 and abs(p[2]-expected[2])<1e-8 for p in core)))
                for end,spec in hooks.items():
                    edge=ls.Edges[0 if end=='start' else -1]
                    checks.append(result(bar.Name+'_'+end+'_straight_tail',isinstance(edge.Curve,Part.Line) and abs(edge.Length-inp.HookTailLength.Value)<TOL and edge.Length>=12*bar.Diameter.Value-TOL,length_in=edge.Length/IN))
                    receiver=doc.getObject(spec['receiver'])
                    receiver_local=local(receiver.Shape,inp.CageFrame)
                    embedded=edge.common(receiver_local).Length/IN
                    checks.append(result(bar.Name+'_'+end+'_enters_'+receiver.Name,embedded>0,length_in=embedded))
                    if spec['receiver_kind']=='cap':
                        rb=bounds(receiver_local);tb=bounds(edge);radius=bar.Diameter.Value/2
                        cover=min(tb.XMin-rb.XMin,rb.XMax-tb.XMax,tb.ZMin-rb.ZMin,rb.ZMax-tb.ZMax)-radius
                        checks.append(result(bar.Name+'_'+end+'_cap_end_top_bottom_cover',cover+TOL>=3*IN,cover_in=cover/IN,required_in=3))
            else:vertical.append(row['points'][0][0]*IN)
            clash,nearest=collisions(shape,objects,bar.Name,inp.CageFrame)
            checks.append(result(bar.Name+'_steel_intersections',not clash,failures=clash,nearest=nearest))
            schedule.append(dict(bar=bar.Name,mark=bar.Mark,hooks=len(hooks),length_ft=bar.TotalLength.Value/FT))
        for kind,stations,pitch in [('horizontal',levels,inp.HorizontalSpacing.Value),('vertical',vertical,inp.VerticalSpacing.Value)]:
            spaces=[v-u for u,v in zip(sorted(stations),sorted(stations)[1:])]
            checks.append(result(name+'_'+kind+'_spacing',bool(spaces) and all(0<s<=pitch+TOL for s in spaces),spaces_in=[s/IN for s in spaces]))
        sh=doc.getObject(inp.Prefix+'Schedule');r=str(sh.TotalRow)
        checks.append(result(name+'_schedule_links',sh.BarNames==[b.Name for b in q.Bars] and float(sh.get('D'+r))==q.TotalBars and abs(float(sh.get('G'+r))-q.TotalSteelLength.Value/FT)<1e-7 and all(sh.getContents('A'+str(k+2)).removeprefix("'")==bar.Mark for k,bar in enumerate(q.Bars))))
        measurements.append(dict(wall=name,bars=q.TotalBars,hooked_bars=sum(bool(r.get('hook_ends')) for r in rows.values()),hooks=hook_count,length_ft=q.TotalSteelLength.Value/FT,weight_lb=q.NominalSteelWeightLb))
    checks.append(result('no_invalid_native_objects',not [o.Name for o in doc.Objects if 'Invalid' in o.State]))
    return dict(checks=checks,failures=[c for c in checks if c['status']=='FAIL'],measurements=measurements,schedule=schedule,
                limitations='Standard hook geometry and affected nominal-solid intersections only. Development, joint transfer and connection capacity NOT VERIFIED.')
