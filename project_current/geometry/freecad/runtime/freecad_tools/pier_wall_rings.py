"""Native pier-wall reinforcement and annular plates; CAD geometry controls.

Drawing geometry only. The selected calculation is retained as an immutable
snapshot, not reevaluated or claimed applicable to the different CAD wall.
All existing concrete, piles and other reinforcement are read-only inputs.
"""
import json
import math
import FreeCAD as App
import Part
from . import bridge, cap_cages as cap, beam, design_steel as steel
from .mse import Serializable, prop

IN = 25.4
PREFIX = 'PierWallSteel'
LIMITS = ('CAD wall retained by user direction, 22 October 2026. The source calculation '
          'snapshot and its failed checks are retained, not rejudged. U bends and contact lap routing are CAD '
          'detailing assumptions; fabrication, anchorage and engineering acceptance remain open. '
          'Continuous vertical bars; the source 60-in vertical lap allowance is recorded, '
          'not a modeled splice. Ring welds are properties, not physical weld solids. '
          'Nominal pile positions only; 3-in placement envelope is not resolved.')


def stations(a, b, maximum):
    if b <= a or maximum <= 0:
        raise ValueError('Invalid reinforcement interval')
    n = max(1, math.ceil((b-a)/maximum))
    return [a+(b-a)*i/n for i in range(n+1)]


def dimensions(inp):
    bb = bridge.local_shape(inp.Host).optimalBoundingBox(False, False)
    # Wall length follows bridge-local Y; thickness follows bridge-local X.
    return dict(length=bb.YLength/IN, thickness=bb.XLength/IN, height=bb.ZLength/IN,
                center_x=(bb.XMin+bb.XMax)/2/IN, start_y=bb.YMin/IN, bottom=bb.ZMin/IN)


def layout(inp):
    d = dimensions(inp)
    L, t, H = d['length'], d['thickness'], d['height']
    db, c, pitch = cap.BAR_DIAMETER[inp.BarNumber], inp.Cover.Value/IN, inp.MaximumSpacing.Value/IN
    r = db/2
    bend = inp.InsideBendDiameter.Value/IN/2+r
    leg = inp.ULeg.Value/IN
    y = t/2-c-r
    if min(L,H) <= 2*(c+r+bend+db) or t <= 2*(c+r+bend+db) or leg <= 0:
        raise ValueError('Wall reinforcement does not fit')
    # Outer horizontals; inner verticals tangent to the horizontal layer.
    # U legs lap alongside horizontals vertically, preserving both mat planes.
    zs = stations(c+r, H-c-r, pitch)
    xs = stations(c+r+bend+db, L-c-r-bend-db, pitch)
    ys = stations(-y+bend+db, y-bend-db, pitch)
    rows = {}
    def add(ident, family, pts, segs=None):
        rows[ident] = dict(id=ident, kind='wall', bar=inp.BarNumber, diameter=db,
                          family=family, points=pts, segments=segs or [('line',0,1)])
    for f, sign in enumerate((-1,1),1):
        for i,z in enumerate(zs,1):
            add(f'F{f}H{i:02}',f'Face {f} horizontal',[(c+r,sign*y,z),(L-c-r,sign*y,z)])
        for i,x in enumerate(xs,1):
            add(f'F{f}V{i:02}',f'Face {f} vertical',[(x,sign*(y-db),c+r),(x,sign*(y-db),H-c-r)])
    for e in (0,1):
        for i,v in enumerate(ys,1):
            x = c+1.5*db if e==0 else L-c-1.5*db
            add(f'E{e+1}V{i:02}',f'End {e+1} vertical',[(x,v,c+r),(x,v,H-c-r)])
        for i,z0 in enumerate(zs,1):
            z = z0+db if i<len(zs) else z0-db
            a = c+r; b = a+bend
            s = bend/math.sqrt(2)
            pts = [(b+leg,-y,z),(b,-y,z),(b-s,-y+bend-s,z),(a,-y+bend,z),
                   (a,y-bend,z),(b-s,y-bend+s,z),(b,y,z),(b+leg,y,z)]
            if e: pts = [(L-x,v,z) for x,v,z in pts]
            add(f'E{e+1}U{i:02}',f'End {e+1} horizontal U return; {leg:g}-in contact lap legs',pts,
                [('line',0,1),('arc',1,2,3),('line',3,4),('arc',4,5,6),('line',6,7)])
    frame = inp.PGL.Frame.multiply(App.Placement(
        App.Vector(d['center_x']*IN,d['start_y']*IN,d['bottom']*IN),App.Rotation(App.Vector(0,0,1),90)))
    return rows,frame,d


class InputsProxy(Serializable):
    def __init__(self,o): o.Proxy=self
    def execute(self,o):
        rows,frame,d = layout(o)
        o.LayoutJSON=json.dumps(rows); o.CageFrame=frame; o.CADDimensionsJSON=json.dumps(d)
        if o.AutoSync: sync(o)


class RebarProxy(cap.RebarProxy):
    def onChanged(self,o,name):
        if name=='Host': return  # Concrete is a read-only geometric host.
        super().onChanged(o,name)


class RingProxy(Serializable):
    def __init__(self,o): o.Proxy=self
    def execute(self,o):
        i=o.Inputs; d=dimensions(i)
        pb=bridge.local_shape(o.Pile).optimalBoundingBox(False,False)
        z=d['bottom']*IN+i.FirstRingTop.Value+(o.Row-1)*i.RingSpacing.Value
        outer,inner,thick=i.RingOD.Value/2,i.RingID.Value/2,i.RingThickness.Value
        if not outer>inner>pb.XLength/2 or z-thick<=d['bottom']*IN or z>= (d['bottom']+d['height'])*IN:
            raise ValueError('Ring does not fit host/pile')
        center=App.Vector((pb.XMin+pb.XMax)/2,(pb.YMin+pb.YMax)/2,z-thick)
        o.Shape=Part.makeCylinder(outer,thick,center).cut(Part.makeCylinder(inner,thick,center))
        o.Placement=i.PGL.Frame
        o.TopAboveWallBottom=z-d['bottom']*IN
        o.NominalVolume=o.Shape.Volume
        o.NominalWeightLb=o.Shape.Volume/(304.8**3)*490


class QuantitiesProxy(steel.WallQuantitiesProxy):
    def execute(self,o):
        super().execute(o)
        o.TotalRings=len(o.Rings)
        o.RingVolume=sum(r.Shape.Volume for r in o.Rings)
        o.RingWeightLb=sum(r.NominalWeightLb for r in o.Rings)


def sync(inp):
    doc=inp.Document; rows=json.loads(inp.LayoutJSON); prefix=inp.Prefix
    q=doc.getObject(prefix+'Quantities')
    if q is None:return
    pg=doc.getObject(prefix+'Paths'); bg=doc.getObject(prefix+'Bars')
    wanted={prefix+k for k in rows}
    for rb in list(q.Bars):
        if rb.Name not in wanted:
            path=rb.Base.Name;doc.removeObject(rb.Name);doc.removeObject(path)
    bars=[]
    for ident,row in rows.items():
        name=prefix+ident;rb=doc.getObject(name)
        if rb is None:
            path=doc.addObject('Part::FeaturePython',name+'Path');pg.addObject(path)
            for typ,key,val in [('App::PropertyLink','Inputs',inp),('App::PropertyString','BarID',ident),
                ('App::PropertyLength','Length','0 in'),('App::PropertyLength','NominalDiameter',str(row['diameter'])+' in'),
                ('App::PropertyInteger','BarNumber',row['bar']),('App::PropertyString','Family',row['family']),
                ('App::PropertyString','QuantityBasis','')]:prop(path,typ,key,val,'Pier wall')
            cap.PathProxy(path);path.Proxy.execute(path)
            rb=beam.native_rebar(doc,name,path,path.NominalDiameter.Value,1);RebarProxy(rb)
            prop(rb,'App::PropertyLink','CageInputs',inp,'Pier wall');rb.Host=inp.Host
            rb.Mark='PW-'+ident;rb.Rounding=0
            prop(rb,'App::PropertyFloat','NominalWeightLb',0.,'Quantity')
            rb.setExpression('Diameter',path.Name+'.NominalDiameter');bg.addObject(rb)
            if App.GuiUp:path.ViewObject.Visibility=False
        rb.Label=f'Pier wall #{row["bar"]} '+row['family'];bars.append(rb)
    q.Bars=bars
    wanted={f'PierWallRingP{p}R{r}' for p in range(1,len(inp.Piles)+1) for r in range(1,inp.RingCount+1)}
    for obj in list(q.Rings):
        if obj.Name not in wanted:doc.removeObject(obj.Name)
    rings=[]
    for p,pile in enumerate(inp.Piles,1):
        for r in range(1,inp.RingCount+1):
            name=f'PierWallRingP{p}R{r}';o=doc.getObject(name)
            if o is None:
                o=doc.addObject('Part::FeaturePython',name);doc.PierWallRings.addObject(o)
                for typ,key,val in [('App::PropertyLink','Inputs',inp),('App::PropertyLink','Pile',pile),
                    ('App::PropertyInteger','Row',r),('App::PropertyLength','TopAboveWallBottom','0 in'),
                    ('App::PropertyVolume','NominalVolume',0.),('App::PropertyFloat','NominalWeightLb',0.),
                    ('App::PropertyString','WeldDetail','Two continuous 5/16-in fillets; weld solids not modeled')]:prop(o,typ,key,val,'Annular ring')
                RingProxy(o)
            o.Label=f'Annular ring P{p}-R{r}';rings.append(o)
    q.Rings=rings


def regenerate(inp):
    inp.Proxy.execute(inp);doc=inp.Document;q=doc.getObject(inp.Prefix+'Quantities')
    for rb in q.Bars:
        rb.Base.Proxy.execute(rb.Base)
        rb.Base.QuantityBasis='Analytic nominal centerline; explicit end-U lap legs; continuous verticals; no waste.'
        rb.Diameter=rb.Base.NominalDiameter.Value
        rb.Proxy.execute(rb);rb.Base.purgeTouched();rb.purgeTouched()
    for ring in q.Rings:ring.Proxy.execute(ring);ring.purgeTouched()
    q.Proxy.execute(q);q.purgeTouched();inp.purgeTouched()
    sh=doc.getObject(inp.Prefix+'Schedule')
    steel.write_wall_schedule(inp,sh,q.Bars)
    doc.recompute([sh])


def create(doc,source,case_hash,source_path):
    if doc.getObject(PREFIX):raise ValueError('Pier wall steel already exists; edit its inputs')
    group=doc.addObject('App::DocumentObjectGroup',PREFIX);group.Label='Pier wall - reinforcement and annular rings'
    doc.BridgeAssembly.addObject(group)
    for tail in ('Paths','Bars'):
        o=doc.addObject('App::DocumentObjectGroup',PREFIX+tail);group.addObject(o)
    group.addObject(doc.addObject('App::DocumentObjectGroup','PierWallRings'))
    inp=doc.addObject('App::FeaturePython',PREFIX+'Inputs');group.addObject(inp)
    p=source['case']
    values=[('App::PropertyString','Prefix',PREFIX),('App::PropertyLink','Host',doc.BridgePierWallSolid),
      ('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyLinkList','Piles',[doc.getObject(f'BridgePilePierP{k}') for k in range(1,5)]),
      ('App::PropertyPlacement','CageFrame',doc.BridgePGL.Frame),('App::PropertyString','LayoutJSON','{}'),
      ('App::PropertyString','CADDimensionsJSON','{}'),('App::PropertyBool','AutoSync',False),
      ('App::PropertyInteger','BarNumber',p['grid_bar']),('App::PropertyInteger','RingCount',p['ring_count']),
      ('App::PropertyString','SourceCaseJSON',json.dumps(p)),('App::PropertyString','SourceCaseSHA256',case_hash),
      ('App::PropertyString','SourcePath',source_path),('App::PropertyString','SourceFailuresJSON',json.dumps(source['failed_checks'])),
      ('App::PropertyString','Limitations',LIMITS),('App::PropertyString','ScheduleNote',LIMITS),
      ('App::PropertyString','EngineeringStatus','CALCULATION RECONCILIATION PENDING'),
      ('App::PropertyString','MarkStatus','PW identifiers are CAD instance identifiers; drawing SDM marks pending')]
    for name,value in dict(Cover=p['cover_in'],MaximumSpacing=source['grid']['spacing'],ULeg=p['u_leg_in'],
        VerticalLapAllowance=p['vertical_lap_in'],InsideBendDiameter=6*source['grid']['db'],
        FirstRingTop=p['first_ring_in'],RingSpacing=p['ring_spacing_in'],RingOD=p['ring_od_in'],
        RingID=p['ring_id_in'],RingThickness=p['ring_t_in'],WeldLeg=p['weld_leg_in'],
        PlacementTolerance=p['placement_tolerance_in']).items():values.append(('App::PropertyLength',name,str(value)+' in'))
    for typ,key,val in values:prop(inp,typ,key,val,'Pier wall design transfer')
    InputsProxy(inp);inp.Proxy.execute(inp)
    q=doc.addObject('App::FeaturePython',PREFIX+'Quantities');group.addObject(q)
    for typ,key,val in [('App::PropertyLinkList','Bars',[]),('App::PropertyLinkList','Rings',[]),
      ('App::PropertyInteger','TotalBars',0),('App::PropertyLength','TotalSteelLength','0 in'),
      ('App::PropertyFloat','NominalSteelWeightLb',0.),('App::PropertyVolume','NominalSteelVolume',0.),
      ('App::PropertyInteger','TotalRings',0),('App::PropertyVolume','RingVolume',0.),('App::PropertyFloat','RingWeightLb',0.)]:prop(q,typ,key,val,'Live quantities')
    QuantitiesProxy(q)
    sh=doc.addObject('Spreadsheet::Sheet',PREFIX+'Schedule');group.addObject(sh)
    prop(sh,'App::PropertyStringList','BarNames',[]);prop(sh,'App::PropertyInteger','TotalRow',0)
    inp.AutoSync=True;regenerate(inp)
    return inp


def validate(inp,check_pairs=True):
    """Independent native-solid geometry, cover, links and interference checks."""
    doc=inp.Document;q=doc.getObject(inp.Prefix+'Quantities');d=dimensions(inp);checks=[]
    def check(name,ok,**kw):checks.append(dict(name=name,status='PASS' if ok else 'FAIL',**kw))
    local=[];vol=0.;total=0.;cover_min=1e9
    for rb in q.Bars:
        s=rb.Shape.copy();s.Placement=inp.CageFrame.inverse().multiply(s.Placement)
        b=s.optimalBoundingBox(False,False);dia=rb.Diameter.Value
        cover=min(b.XMin,d['length']*IN-b.XMax,b.YMin+d['thickness']*IN/2,
                  d['thickness']*IN/2-b.YMax,b.ZMin,d['height']*IN-b.ZMax)/IN
        cover_min=min(cover_min,cover)
        check(rb.Name+'_solid',s.isValid() and len(s.Solids)==1 and
              abs(s.Volume-math.pi*dia**2/4*rb.Base.Shape.Length)<max(1e-5,s.Volume*1e-7))
        check(rb.Name+'_cover',cover>=inp.Cover.Value/IN-1e-6,minimum_in=cover)
        check(rb.Name+'_native_links',rb.Base.Inputs==inp and rb.Host==inp.Host and rb.CageInputs==inp
              and abs(rb.Length.Value-rb.Base.Shape.Length)<1e-6)
        local.append((rb.Name,rb.Shape.copy()));vol+=s.Volume;total+=rb.Length.Value
    ring_volume=0.
    for r in q.Rings:
        s=r.Shape.copy();s.Placement=inp.PGL.Frame.inverse().multiply(s.Placement)
        b=s.optimalBoundingBox(False,False);pb=bridge.local_shape(r.Pile).optimalBoundingBox(False,False)
        expected=math.pi/4*(inp.RingOD.Value**2-inp.RingID.Value**2)*inp.RingThickness.Value
        check(r.Name+'_solid',s.isValid() and len(s.Solids)==1 and abs(s.Volume-expected)<expected*1e-9)
        check(r.Name+'_position',abs((b.XMin+b.XMax-pb.XMin-pb.XMax)/2)<1e-6 and
              abs((b.YMin+b.YMax-pb.YMin-pb.YMax)/2)<1e-6 and
              abs(b.ZMax-(d['bottom']*IN+inp.FirstRingTop.Value+(r.Row-1)*inp.RingSpacing.Value))<1e-6)
        check(r.Name+'_plate_dimensions',abs(b.XLength-inp.RingOD.Value)<1e-6 and
              abs(b.YLength-inp.RingOD.Value)<1e-6 and abs(b.ZLength-inp.RingThickness.Value)<1e-6)
        local.append((r.Name,r.Shape.copy()));ring_volume+=s.Volume
    check('live_quantities',q.TotalBars==len(q.Bars) and q.TotalRings==len(q.Rings) and
          abs(q.TotalSteelLength.Value-total)<1e-6 and abs(q.RingVolume.Value-ring_volume)<1e-5)
    # Independent physical center stations, not merely a second layout invocation.
    for family,axis in [('Face 1 horizontal','z'),('Face 1 vertical','x'),('End 1 vertical','y')]:
        positions=[]
        for rb in q.Bars:
            if rb.Base.Family==family:positions.append(getattr(rb.Base.Shape.Vertexes[0].Point,axis)/IN)
        positions.sort();gap=max(b-a for a,b in zip(positions,positions[1:]))
        check(family+'_spacing',gap<=inp.MaximumSpacing.Value/IN+1e-8,maximum_in=gap)
    clashes=[];pairs=0
    if check_pairs:
        existing=[]
        for o in doc.Objects:
            if o.Name.startswith(('PierWallSteel','PierWallRing')):continue
            if 'Shape' in o.PropertiesList and ('Diameter' in o.PropertiesList or o.Name.startswith('BridgePile')):
                existing.append((o.Name,o.Shape.copy()))
        for i,(name,s) in enumerate(local):
            for other,t in local[i+1:]+existing:
                if not s.BoundBox.intersect(t.BoundBox):continue
                pairs+=1;overlap=abs(s.common(t).Volume)/IN**3
                if overlap>1e-7:clashes.append(dict(first=name,second=other,overlap_in3=overlap))
        check('nominal_steel_intersections',not clashes,pairs=pairs,clashes=clashes)
    return dict(status='PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL',checks=checks,
                bar_count=len(q.Bars),rings=len(q.Rings),minimum_bar_cover_in=cover_min,
                steel_length_ft=total/304.8,steel_weight_lb=q.NominalSteelWeightLb,
                ring_weight_lb=q.RingWeightLb,cad_dimensions=d,source_case_sha256=inp.SourceCaseSHA256,
                engineering_status=inp.EngineeringStatus,limitations=inp.Limitations)
