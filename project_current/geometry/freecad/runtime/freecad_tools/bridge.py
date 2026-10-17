"""Editable, source-linked bridge components in an existing FreeCAD document.

Geometry study only. Never saves a working model. Configuration is copied from
the supplied notebook; physical bearings and user overrides are explicit.
"""
import copy
import hashlib
import json
import math
import re
import traceback
from datetime import datetime,timezone
from pathlib import Path
import FreeCAD as App
import Part
from .geometry import length,result
from .mse import prop,color,Serializable
from .bridge_layout import PhysicalBridgeModel
from . import bridge_shapes as shapes
from . import bridge_supports as supports

ROOT=Path(__file__).resolve().parent.parent
FT=304.8
IN=25.4
_CACHE={}
COLORS={'Deck':(.78,.79,.78),'Beam':(.83,.71,.44),'Haunch':(.87,.64,.36),'Pad':(.16,.2,.26),
        'Pedestal':(.53,.67,.77),'Cap':(.59,.66,.70),'Pile':(.40,.49,.56),'Wall':(.64,.70,.65),'WallEnvelope':(.64,.70,.65),
        'Backwall':(.65,.70,.72),'Cheek':(.65,.70,.72)}

def initialize_display(o):
    """Activate FreeCAD's native Part view provider for a Python feature.

    Visibility=True alone does not initialize its Coin geometry. This is the
    same Proxy=0 initialization used by FreeCAD's installed PartDesign scripts.
    """
    if not App.GuiUp:return
    if o.TypeId!='Part::FeaturePython':raise ValueError('Unexpected display target '+o.Name)
    visible=o.ViewObject.Visibility
    o.ViewObject.Proxy=0
    o.ViewObject.DisplayMode='Flat Lines'
    if hasattr(o,'ComponentKind'):
        color(o,COLORS[o.ComponentKind])
    else:
        o.ViewObject.LineColor=(.9,.1,.15);o.ViewObject.LineWidth=4.0
    o.ViewObject.Visibility=visible

def display_state(o):
    from pivy import coin
    action=coin.SoGetBoundingBoxAction(coin.SbViewportRegion(400,300))
    action.apply(o.ViewObject.RootNode)
    return {'visible':o.ViewObject.Visibility,'mode':getattr(o.ViewObject,'DisplayMode',None),
            'scene_children':o.ViewObject.RootNode.getNumChildren(),
            'render_bounds_empty':action.getBoundingBox().isEmpty()}

DIMENSIONS={
 'StartStation':'1593.22 ft','PierStation':'1700.57 ft','EndStation':'1805.47 ft',
 'StartElevation':'47.661 ft','EndElevation':'47.673 ft',
 'DeckWidth':'13 ft 7 in','DeckThickness':'6 in','BeamSpacing':'8 ft 7 in',
 'Span1Camber':'0.030455438593645807 in','Span2Camber':'0.48309541716006704 in',
 'BeamEndClearance':'3 in','BearingSetback':'9 in','PierBeamGap':'3 in',
 'PadLength':'10 in','PadWidth':'32 in','PadThickness':'2.5625 in',
 'PedestalWidth':'42 in','MinimumPedestalHeight':'6 in','PedestalChamfer':'0.75 in',
 'EndPedestalLength':'3 ft','PierPedestalLength':'4 ft',
 'EndCapWidth':'3 ft','PierCapWidth':'4 ft','CapDepth':'3 ft',
 'EndCapLength':'19 ft 3 in','PierCapLength':'19 ft 2 in','BackwallThickness':'12 in',
 'PileDiameter':'20 in','PileWallThickness':'0.625 in','PileSpacing':'5 ft','TrialPileLength':'90 ft',
 'WallLength':'18 ft 3 in','WallThickness':'3 ft','GroundElevation':'25.5264 ft','WallBurial':'1 ft'}

def ft(o,name): return getattr(o,name).Value/FT

def modeled_chamfer(c, nominal_mm):
    """Omit only nominal 3/4-in bridge chamfers under the drawing convention.

    Barriers and ramps do not call this helper. Larger geometric breaks and
    fillets stay modeled; legacy documents retain their original geometry.
    """
    if getattr(c,'OmitStandardChamfers',False) and abs(nominal_mm-.75*IN) < 1e-9:
        return 0.
    return nominal_mm

def model(o):
    cfg=json.loads(o.NotebookConfiguration)
    for k,n in [('start_sta_ft','StartStation'),('intersection_sta_ft','PierStation'),('end_sta_ft','EndStation'),
                ('start_elev_ft','StartElevation'),('end_elev_ft','EndElevation')]: cfg['profile'][k]=ft(o,n)
    cfg['spans'][0].update(start_ft=ft(o,'StartStation'),end_ft=ft(o,'PierStation'))
    cfg['spans'][1].update(start_ft=ft(o,'PierStation'),end_ft=ft(o,'EndStation'))
    cfg['pier']['station_ft']=ft(o,'PierStation')
    cfg['deck'].update(width_ft=ft(o,'DeckWidth'),thickness_ft=ft(o,'DeckThickness'))
    cfg['beams']['spacing_ft']=ft(o,'BeamSpacing')
    cfg['spans'][0]['camber_in']=o.Span1Camber.Value/IN
    cfg['spans'][1]['camber_in']=o.Span2Camber.Value/IN
    key=json.dumps(cfg,sort_keys=True)+str([ft(o,n) for n in ['BeamEndClearance','BearingSetback','PierBeamGap']])
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key]=PhysicalBridgeModel(cfg,ft(o,'BeamEndClearance'),ft(o,'BearingSetback'),ft(o,'PierBeamGap'))
    return _CACHE[key]

def support_data(c):
    m=model(c)
    rows=[dict(id='EB1',station=m.start-ft(c,'BackwallThickness')+ft(c,'EndCapWidth')/2,
               width=ft(c,'EndCapWidth'),length=ft(c,'EndCapLength'),pedlength=ft(c,'EndPedestalLength'),seats=[(0,m.bearing_limits[0][0])]),
          dict(id='Pier',station=m.peak,width=ft(c,'PierCapWidth'),length=ft(c,'PierCapLength'),
               pedlength=ft(c,'PierPedestalLength'),seats=[(0,m.bearing_limits[0][1]),(1,m.bearing_limits[1][0])]),
          dict(id='EB2',station=m.end+ft(c,'BackwallThickness')-ft(c,'EndCapWidth')/2,
               width=ft(c,'EndCapWidth'),length=ft(c,'EndCapLength'),pedlength=ft(c,'EndPedestalLength'),seats=[(1,m.bearing_limits[1][1])])]
    for row in rows:
        row['depth']=ft(c,'CapDepth');row['padthickness']=ft(c,'PadThickness')
        row['pilekind']='Pipe';row['pilecount']=c.PilesPerCap;row['pilespacing']=ft(c,'PileSpacing')
        row['pedstart']=row['station']-row['pedlength']/2;row['pedend']=row['station']+row['pedlength']/2
        row['top']=min(supports.bearing_plane(m,i,b,s,ft(c,'PadLength'))(s)-ft(c,'PadThickness')
                       for i,s in row['seats'] for b in range(m.count))-ft(c,'MinimumPedestalHeight')
        row['bottom']=row['top']-ft(c,'CapDepth')
    if getattr(c,'EndBentRevision',0):
        from .end_bents import revise_supports
        revise_supports(c,m,rows)
    if getattr(c,'CurrentSourceRevision',0):
        from .current_source import revise_supports
        revise_supports(c,m,rows)
    return {r['id']:r for r in rows}

def deck_limits(c,index):
    """Physical deck ends; PGL limits remain fixed front-face datums."""
    m=model(c);row=m.spans.iloc[index]
    gap=ft(c,'DeckEndClearance') if 'DeckEndClearance' in c.PropertiesList else 0.
    return float(row.start_ft)+(gap if index==0 else 0.),float(row.end_ft)-(gap if index==1 else 0.)

class PGLProxy(Serializable):
    def __init__(self,o): o.Proxy=self
    def execute(self,o):
        m=model(o)
        o.Shape=Part.makePolygon([App.Vector((s-m.start)*FT,0,float(m.pgl(s))*FT) for s in [m.start,m.peak,m.end]])
        o.Placement=o.Frame
        o.ActualLongitudinalSlopes=[f'Span 1: {m.g1*100:.9f}%',f'Span 2: {m.g2*100:.9f}%']
        o.MinimumHaunch=m.haunch_min*FT
        o.SupportDrop=m.support_drop*FT

class ComponentProxy(Serializable):
    def __init__(self,o): o.Proxy=self
    def execute(self,o):
        c=o.PGL; m=model(c); k=o.ComponentKind
        i=o.SpanIndex; b=o.BeamIndex
        data=support_data(c)
        if k=='Deck':
            a,e=deck_limits(c,i);shape=shapes.deck_solid(m,a,e)
            o.Label=f'Deck span {i+1} — {(m.g1 if i==0 else m.g2)*100:+.9f}%; crown 2%'
        elif k=='Beam':
            a,e=m.beam_limits[i]
            shape=shapes.beam_solid(m,i,b,a,e,bottom_chamfer_in=modeled_chamfer(c,.75*IN)/IN)
            o.Label=f'FIB36 span {i+1}, beam {b+1} — net camber {float(m.spans.iloc[i].camber_in):.9f} in'
        elif k=='Haunch':
            a,e=m.beam_limits[i];shape=shapes.haunch_solid(m,i,b,a,e)
        elif k=='Pad':
            row=data[o.SupportID];span,s=row['seats'][o.SeatIndex]
            shape=supports.pad_solid(m,span,b,s,ft(c,'PadLength'),ft(c,'PadWidth'),row['padthickness'])
        elif k=='Pedestal':
            row=data[o.SupportID];a=row['pedstart'];e=row['pedend']
            shape=supports.pedestal_solid(m,b,a,e,row['top'],row['seats'],ft(c,'PadLength'),
                row['padthickness'],ft(c,'PedestalWidth'),modeled_chamfer(c,c.PedestalChamfer.Value)/FT)
        elif k=='Cap':
            row=data[o.SupportID]
            shape=supports.cap_solid(m,row['station'],row['width'],row['length'],row['top'],row['depth'])
            if row['pilekind']=='Square concrete':
                from .end_bents import cut_sockets
                shape=cut_sockets(c,m,row,shape)
            elif getattr(c,'CurrentSourceRevision',0):
                from .current_source import pier_sockets
                shape=pier_sockets(c,m,row,shape)
        elif k=='Pile':
            row=data[o.SupportID];offset=(o.PileIndex-(row['pilecount']-1)/2)*row['pilespacing']
            if row['pilekind']=='Square concrete':
                from .end_bents import square_pile
                shape=square_pile(c,m,row,offset)
            else:shape=supports.pipe_solid(m,row['station'],offset,row.get('piletop',row['bottom']),ft(c,'TrialPileLength'),ft(c,'PileDiameter'),ft(c,'PileWallThickness'))
        elif k in ['Backwall','Cheek']:
            from .end_bents import wall_shape
            shape=wall_shape(c,m,data[o.SupportID],k,o.BeamIndex)
        elif k in ['WallEnvelope','Wall']:
            row=data['Pier'];bottom=ft(c,'GroundElevation')-ft(c,'WallBurial')
            shape=Part.makeBox(ft(c,'WallThickness')*FT,ft(c,'WallLength')*FT,(row['bottom']-bottom)*FT,
                App.Vector((row['station']-m.start-ft(c,'WallThickness')/2)*FT,-ft(c,'WallLength')*FT/2,bottom*FT))
            if k=='Wall':
                bores=[Part.makeCylinder(ft(c,'PileDiameter')*FT/2,(row['bottom']-bottom)*FT,
                    App.Vector((row['station']-m.start)*FT,(j-(c.PilesPerCap-1)/2)*ft(c,'PileSpacing')*FT,bottom*FT)) for j in range(c.PilesPerCap)]
                shape=shape.cut(Part.makeCompound(bores)).removeSplitter()
        else: raise ValueError('Unsupported bridge component '+k)
        o.Shape=shape
        o.Placement=c.Frame
        o.NetVolume=shape.Volume

def construct(doc,job):
    c=doc.addObject('Part::FeaturePython','BridgePGL')
    c.Label='Bridge PGL — deck centerline'
    prop(c,'App::PropertyString','NotebookConfiguration',json.dumps(job['notebook_configuration']),'Source')
    prop(c,'App::PropertyStringList','SourceFiles',[s['path'] for s in job['sources']],'Source')
    prop(c,'App::PropertyStringList','SourceHashes',[s['sha256'] for s in job['sources']],'Source')
    prop(c,'App::PropertyStringList','Assumptions',job['assumptions'],'Source')
    prop(c,'App::PropertyString','StationDatum','Profile limits are front faces of backwalls','Source')
    prop(c,'App::PropertyString','CamberStage','Net after all dead loads, 120 days; notebook quadratic between physical bearings','Source')
    for n,v in job['dimensions'].items(): prop(c,'App::PropertyLength',n,v,'Bridge dimensions')
    prop(c,'App::PropertyInteger','PilesPerCap',4,'Bridge dimensions')
    origin=App.Vector(*[length(v) for v in job['frame']['origin']])
    angle=App.Units.Quantity(job['frame']['angle']).Value
    prop(c,'App::PropertyPlacement','Frame',App.Placement(origin,App.Rotation(App.Vector(0,0,1),angle)),'Placement')
    prop(c,'App::PropertyStringList','ActualLongitudinalSlopes',[],'Results')
    prop(c,'App::PropertyLength','MinimumHaunch','0 in','Results')
    prop(c,'App::PropertyLength','SupportDrop','0 in','Results')
    for n in ['ActualLongitudinalSlopes','MinimumHaunch','SupportDrop']: c.setEditorMode(n,1)
    PGLProxy(c)
    initialize_display(c)
    assembly=doc.addObject('App::DocumentObjectGroup','BridgeAssembly');assembly.Label='PGL-controlled bridge components'
    assembly.addObject(c)
    groups={}
    for name in ['Decks','Beams','Haunches','Bearings','Pedestals','Caps','Piles','PierWall','Sources']:
        g=doc.addObject('App::DocumentObjectGroup','Bridge'+name);g.Label=name;assembly.addObject(g);groups[name]=g
    made={}
    def add(name,label,kind,group,span=0,beam=0,support='',seat=0,pile=0,links=None):
        o=doc.addObject('Part::FeaturePython',name);o.Label=label
        for n,v in [('PGL',c)]:prop(o,'App::PropertyLink',n,v,'Dependencies')
        prop(o,'App::PropertyLinkList','Sources',links or [],'Dependencies')
        prop(o,'App::PropertyString','ComponentKind',kind)
        prop(o,'App::PropertyString','SupportID',support)
        for n,v in [('SpanIndex',span),('BeamIndex',beam),('SeatIndex',seat),('PileIndex',pile)]:prop(o,'App::PropertyInteger',n,v)
        prop(o,'App::PropertyVolume','NetVolume',0,'Quantity');o.setEditorMode('NetVolume',1)
        ComponentProxy(o);initialize_display(o);groups[group].addObject(o);made[name]=o
        return o
    for i in range(2):
        deck=add(f'BridgeDeckS{i+1}',f'Deck span {i+1} — PGL, 2% crown','Deck','Decks',i)
        for b in range(2):
            beam=add(f'BridgeBeamS{i+1}B{b+1}',f'FIB36 span {i+1}, beam {b+1}','Beam','Beams',i,b)
            add(f'BridgeHaunchS{i+1}B{b+1}',f'Haunch span {i+1}, beam {b+1}','Haunch','Haunches',i,b,links=[beam,deck])
    for sid,row in support_data(c).items():
        cap=add('BridgeCap'+sid,f'{sid} cap','Cap','Caps',support=sid)
        for b in range(2):
            ped=add(f'BridgePedestal{sid}B{b+1}',f'{sid} pedestal {b+1}','Pedestal','Pedestals',beam=b,support=sid,links=[cap])
            for si,(span,station) in enumerate(row['seats']):
                beam=made[f'BridgeBeamS{span+1}B{b+1}']
                add(f'BridgePad{sid}S{span+1}B{b+1}',f'{sid} Type F pad, span {span+1}, beam {b+1}',
                    'Pad','Bearings',span,b,sid,si,links=[beam,ped])
        for j in range(4):
            add(f'BridgePile{sid}P{j+1}',f'{sid} pipe pile {j+1} — 90 ft trial length','Pile','Piles',support=sid,pile=j,links=[cap])
    nominal=add('BridgePierWallEnvelope','Pier wall nominal envelope — provisional thickness','WallEnvelope','Sources')
    piles=[made[f'BridgePilePierP{j+1}'] for j in range(4)]
    add('BridgePierWallSolid','Pier wall — 3 ft thickness provisional','Wall','PierWall',links=[nominal]+piles)
    doc.recompute()
    nominal.ViewObject.Visibility=False
    c.ViewObject.LineColor=(.9,.1,.15);c.ViewObject.LineWidth=4.0
    return c,made

def local_shape(o):
    s=o.Shape.copy();s.Placement=o.PGL.Frame.inverse().multiply(s.Placement);return s

def source_state(doc,names):
    out={}
    for n in names:
        o=doc.getObject(n)
        out[n]=dict(type=o.TypeId,label=o.Label,expressions=list(getattr(o,'ExpressionEngine',[])),
            dependencies=sorted(x.Name for x in o.OutList),placement=str(getattr(o,'Placement',None)),
            # Groups expose a synthetic Shape attribute in FreeCAD 1.1. Reading
            # it creates a compound/display cache and mutates child cache flags.
            # Hash native shape properties only; group membership is independently
            # captured by dependencies and every real child BRep is still hashed.
            shape=hashlib.sha256(o.Shape.exportBrepToString().encode()).hexdigest() if 'Shape' in o.PropertiesList else None,
            visibility=o.ViewObject.Visibility if App.GuiUp else None)
    return out

def integration(c,objects,existing):
    """Measured source coordination: failures stay failures, never auto-cut MSE."""
    m=model(c);clashes=[];landings=[]
    for n,o in objects.items():
        if o.ComponentKind=='WallEnvelope':continue
        for old in existing:
            if not o.Shape.BoundBox.intersect(old.Shape.BoundBox):continue
            volume=abs(o.Shape.copy().common(old.Shape.copy()).Volume)
            if volume>0:clashes.append(dict(bridge=n,mse=old.Name,common_volume_ft3=volume/FT**3))
    names={o.Name:o for o in existing}
    plane=shapes.plane_polygon([(-100000,0,-100000),(100000,0,-100000),(100000,0,100000),(-100000,0,100000)])
    for n,end in [('A_BridgeLandingSlabFinished',False),('B_BridgeLandingSlab',True)]:
        if n not in names:continue
        shape=names[n].Shape.copy();shape.Placement=c.Frame.inverse().multiply(shape.Placement)
        sec=shape.section(plane);pts=sorted((v.Point.x/FT,v.Point.z/FT) for v in sec.Vertexes)
        x=min(x for x,z in pts) if end else max(x for x,z in pts)
        top=max(z for px,z in pts if abs(px-x)<1e-6)
        deck=local_shape(objects['BridgeDeckS2' if end else 'BridgeDeckS1'])
        deck_x=(deck.BoundBox.XMax if end else deck.BoundBox.XMin)/FT
        deck_z=float(m.pgl(m.start+deck_x))
        required_gap=ft(c,'DeckEndClearance')*12 if 'DeckEndClearance' in c.PropertiesList else 0.
        landings.append(dict(mse_slab=n,horizontal_gap_in=(x-deck_x)*(1 if end else -1)*12,
            required_deck_joint_gap_in=required_gap,deck_end_station_ft=m.start+deck_x,
            ramp_top_ft=top,bridge_PGL_top_ft=deck_z,ramp_minus_PGL_in=(top-deck_z)*12))
    checks=[result('MSE_bridge_concrete_interferences',not clashes,clashes=clashes)]
    for row in landings:
        checks.append(result(row['mse_slab']+'_connection',abs(row['horizontal_gap_in']-row['required_deck_joint_gap_in'])<=.001 and abs(row['ramp_minus_PGL_in'])<=.001,**row))
    if not existing:checks=[{'name':'MSE_bridge_integration','status':'NOT CONFIGURED'}]
    return dict(checks=checks,clashes=clashes,landings=landings)

class CheckProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        objects={c.Name:c for c in o.Components}
        qa=validate(o.PGL,objects)
        coordination=integration(o.PGL,objects,o.ExistingConcrete)
        o.GeometryStatus='FAIL' if any(c['status']=='FAIL' for c in qa['checks']) else 'PASS'
        o.CoordinationStatus=('FAIL' if any(c['status']=='FAIL' for c in coordination['checks']) else
                              'NOT CONFIGURED' if not o.ExistingConcrete else 'PASS')
        o.PhysicalCamberInches=qa['actual_cambers_in']
        o.MinimumMeasuredHaunch=qa['minimum_haunch_in']*IN
        o.LongitudinalGradesPercent=qa['longitudinal_grades_percent']
        o.ClashPairs=[r['bridge']+' / '+r['mse'] for r in coordination['clashes']]
        o.LandingConnections=[r['mse_slab']+f": gap {r['horizontal_gap_in']:.6f} in; ramp-PGL {r['ramp_minus_PGL_in']:.6f} in" for r in coordination['landings']]
        if 'DeckBackwallClearances' in o.PropertiesList:
            o.DeckBackwallClearances=[f"{r['support']}: {r['horizontal_gap_in']:.9f} in" for r in qa.get('deck_backwall_gaps',[])]
        o.Label='Bridge checks — geometry '+o.GeometryStatus+'; coordination '+o.CoordinationStatus
        self.last_qa=qa;self.last_integration=coordination

def create_checks(doc,c,objects,existing):
    o=doc.addObject('App::FeaturePython','BridgeGeometryChecks')
    prop(o,'App::PropertyLink','PGL',c,'Dependencies')
    prop(o,'App::PropertyLinkList','Components',list(objects.values()),'Dependencies')
    prop(o,'App::PropertyLinkList','ExistingConcrete',existing,'Dependencies')
    for n in ['GeometryStatus','CoordinationStatus']:prop(o,'App::PropertyString',n,'PENDING','Results')
    for n in ['PhysicalCamberInches','LongitudinalGradesPercent']:prop(o,'App::PropertyFloatList',n,[],'Results')
    prop(o,'App::PropertyLength','MinimumMeasuredHaunch','0 in','Results')
    for n in ['ClashPairs','LandingConnections']:prop(o,'App::PropertyStringList',n,[],'Results')
    for n in ['GeometryStatus','CoordinationStatus','PhysicalCamberInches','LongitudinalGradesPercent','MinimumMeasuredHaunch','ClashPairs','LandingConnections']:o.setEditorMode(n,1)
    CheckProxy(o);doc.getObject('BridgeAssembly').addObject(o);doc.recompute()
    return o

def validate(c,objects,check_pairs=True):
    m=model(c); checks=[]; details={}; physical={n:o for n,o in objects.items() if o.ComponentKind!='WallEnvelope'}
    expected_counts={'Deck':2,'Beam':4,'Haunch':4,'Pad':8,'Pedestal':6,'Cap':3,'Pile':12,'Wall':1}
    if getattr(c,'EndBentRevision',0):expected_counts.update(Backwall=2,Cheek=4)
    for kind,count in expected_counts.items():
        actual=sum(o.ComponentKind==kind for o in physical.values())
        checks.append(result(kind+'_count',actual==count,actual=actual,expected=count))
    local={n:local_shape(o) for n,o in physical.items()}
    tol=.0254
    for n,o in physical.items():
        s=local[n]
        checks.append(result(n+'_valid',s.isValid() and len(s.Solids)==1,solids=len(s.Solids)))
        checks.append(result(n+'_quantity',abs(o.NetVolume.Value-s.Volume)<=max(1e-6,s.Volume*1e-9)))
        checks.append(result(n+'_source_links',o.PGL==c and o.Proxy is not None))
        details[n]={'volume_ft3':s.Volume/FT**3,'kind':o.ComponentKind}
    def heights(s,x,y):
        cut=s.section(Part.makeLine(App.Vector(x,y,-100000),App.Vector(x,y,100000)))
        return sorted(set(round(v.Point.z,8) for v in cut.Vertexes))
    haunch_min=[];measured_cambers=[];measured_grades=[]
    for i,row in m.spans.iterrows():
        a,e=deck_limits(c,i)
        deck=local[f'BridgeDeckS{i+1}']; bb=deck.BoundBox
        expected_deck_volume=(e-a)*m.deck_width*m.deck_thickness*FT**3
        deck_object=objects[f'BridgeDeckS{i+1}']
        if 'EdgeChamfer' in deck_object.PropertiesList:
            # Independent section-area deduction: four chamfer triangles and
            # two V grooves. Groove width/depth follow the sloping soffit.
            removed_area=2*modeled_chamfer(c,deck_object.EdgeChamfer.Value)**2/math.sqrt(1+.02**2)
            removed_area+=deck_object.DripGrooveWidth.Value*deck_object.DripGrooveDepth.Value
            expected_deck_volume-=removed_area*(e-a)*FT
        checks.append(result(f'deck{i+1}_volume',abs(deck.Volume-expected_deck_volume)<deck.Volume*1e-8))
        measured=[]
        for s in [a+.2*(e-a),a+.8*(e-a)]:
            h=heights(deck,(s-m.start)*FT,0)
            checks.append(result(f'deck{i+1}_PGL_{s}',len(h)==2 and abs(h[-1]-float(m.pgl(s))*FT)<=tol and abs(h[-1]-h[0]-m.deck_thickness*FT)<=tol))
            measured.append(h[-1])
        actual_grade=(measured[1]-measured[0])/(.6*(e-a)*FT)
        measured_grades.append(actual_grade*100)
        expected_grade=m.g1 if i==0 else m.g2
        checks.append(result(f'deck{i+1}_actual_longitudinal_grade',abs(actual_grade-expected_grade)<=1e-9,actual_percent=actual_grade*100))
        mid=(a+e)/2
        center=heights(deck,(mid-m.start)*FT,0)[-1]
        for side in [-1,1]:
            y=side*m.deck_width/2*.9
            z=heights(deck,(mid-m.start)*FT,y*FT)[-1]
            cross=(z-center)/(abs(y)*FT)
            checks.append(result(f'deck{i+1}_actual_cross_grade_{side}',abs(cross+.02)<=1e-9,actual_percent=cross*100))
        for b,offset in enumerate(m.offsets):
            beam=local[f'BridgeBeamS{i+1}B{b+1}'];haunch=local[f'BridgeHaunchS{i+1}B{b+1}']
            start,end=m.beam_limits[i];ba,be=m.bearing_limits[i];bm=(ba+be)/2
            cuts=[shapes.section_at(beam,(s-m.start)*FT) for s in [ba,bm,be]]
            actual_camber=cuts[1].BoundBox.ZMin-(cuts[0].BoundBox.ZMin+cuts[2].BoundBox.ZMin)/2
            if b==0:measured_cambers.append(actual_camber/IN)
            checks.append(result(f'beam{i+1}_{b+1}_physical_camber',abs(actual_camber-row.camber_in*IN)<=tol,actual_in=actual_camber/IN,expected_in=float(row.camber_in)))
            checks.append(result(f'beam{i+1}_{b+1}_depth',all(abs(s.BoundBox.ZLength-36*IN)<=tol for s in cuts)))
            area=Part.Face(shapes.fib36_wire()).Area
            # Restore the two omitted right triangles independently of the
            # square-profile builder; nominal section dimensions stay fixed.
            if modeled_chamfer(c,.75*IN)==0:area+=(.75*IN)**2
            checks.append(result(f'beam{i+1}_{b+1}_physical_volume',abs(beam.Volume-area*(end-start)*FT)<=beam.Volume*1e-8))
            expected=(end-start)/6*(m.flange_area(start,b,i)+4*m.flange_area((start+end)/2,b,i)+m.flange_area(end,b,i))*FT**3
            checks.append(result(f'haunch{i+1}_{b+1}_physical_volume',abs(haunch.Volume-expected)<=haunch.Volume*1e-8))
            for station in [ba,bm,be]:
                for side in [-1,1]:
                    y=offset+side*m.flange/2
                    h=heights(haunch,(station-m.start)*FT,y*FT)
                    thickness=(h[-1]-h[0]) if len(h)==2 else -1
                    haunch_min.append(thickness)
                    expected=float(m.deck_top(station,y)-m.deck_thickness-m.evaluate([station],i)['top'][0,b])*FT
                    checks.append(result(f'haunch{i+1}_{b+1}_surface_{station}_{side}',len(h)==2 and abs(thickness-expected)<=tol,thickness_in=thickness/IN))
    checks.append(result('actual_minimum_haunch',abs(min(haunch_min)-.5*IN)<=tol,minimum_in=min(haunch_min)/IN))
    data=support_data(c);pad_gaps=[]
    for sid,row in data.items():
        cap=local['BridgeCap'+sid];bb=cap.BoundBox
        checks.append(result(sid+'_cap_dimensions',max(abs(bb.XLength-row['width']*FT),abs(bb.YLength-row['length']*FT),abs(bb.ZLength-row['depth']*FT))<=tol))
        for b in range(2):
            ped=local[f'BridgePedestal{sid}B{b+1}'];pb=ped.BoundBox
            checks.append(result(f'{sid}_pedestal{b+1}_footprint',abs(pb.XLength-row['pedlength']*FT)<=tol and abs(pb.YLength-ft(c,'PedestalWidth')*FT)<=tol and pb.XMin>=bb.XMin-tol and pb.XMax<=bb.XMax+tol))
            for span,station in row['seats']:
                pad=local[f'BridgePad{sid}S{span+1}B{b+1}'];pbb=pad.BoundBox
                z=heights(pad,(station-m.start)*FT,m.offsets[b]*FT)
                beam_z=float(m.evaluate([station],span)['bottom'][0,b])*FT
                gap=beam_z-z[-1];pad_gaps.append(gap)
                checks.append(result(f'{sid}_pad{span+1}_{b+1}_dimensions',abs(pbb.XLength-ft(c,'PadLength')*FT)<=tol and abs(pbb.YLength-ft(c,'PadWidth')*FT)<=tol and len(z)==2 and abs(z[-1]-z[0]-row['padthickness']*FT)<=tol))
                checks.append(result(f'{sid}_pad{span+1}_{b+1}_soffit_fit',gap>=-1e-7 and gap<=tol,mid_pad_gap_in=gap/IN))
        for j in range(4):
            pile=local[f'BridgePile{sid}P{j+1}'];pbb=pile.BoundBox
            if row['pilekind']=='Square concrete':
                side=ft(c,'EndPileSize');expected=side**2*ft(c,'TrialPileLength')*FT**3
                dimensions_ok=abs(pbb.XLength-side*FT)<=tol and abs(pbb.YLength-side*FT)<=tol
            else:
                expected=math.pi*((ft(c,'PileDiameter')/2)**2-(ft(c,'PileDiameter')/2-ft(c,'PileWallThickness'))**2)*ft(c,'TrialPileLength')*FT**3
                dimensions_ok=abs(pbb.XLength-ft(c,'PileDiameter')*FT)<=tol
            checks.append(result(f'{sid}_pile{j+1}_physical',abs(pbb.ZLength-ft(c,'TrialPileLength')*FT)<=tol and dimensions_ok and abs(pile.Volume-expected)<=expected*1e-8))
    clashes=[];contacts=[]
    if check_pairs:
        names=list(local)
        for i,n in enumerate(names):
            a=local[n]
            for other in names[i+1:]:
                b=local[other]
                if not a.BoundBox.intersect(b.BoundBox):continue
                overlap=abs(a.common(b).Volume)
                if overlap>0:clashes.append({'a':n,'b':other,'volume_in3':overlap/IN**3})
                elif a.distToShape(b)[0]<=tol:contacts.append([n,other])
        checks.append(result('bridge_component_interferences',len(clashes)==0,clashes=clashes))
    else: checks.append({'name':'bridge_component_interferences','status':'NOT CONFIGURED'})
    unsupported=['Structural design and code approval','Reinforcement and reinforcement cover',
         ('Final pile tip elevations' if getattr(c,'CurrentSourceRevision',0) else 'Final pile tip elevations and pier pile embedment' if getattr(c,'EndBentRevision',0) else 'Final pile tip elevations and pile embedment in caps'),'Full roadway clearance: XML has a coverage gap',
         'Construction stage deformation: selected net-camber geometry only']
    checks.extend({'name':n,'status':'NOT CONFIGURED'} for n in unsupported)
    deck_gap_rows=[]
    if 'DeckEndClearance' in c.PropertiesList:
        from .deck_gaps import measure
        gap_qa=measure(c,objects);checks.extend(gap_qa['checks']);deck_gap_rows=gap_qa['measurements']
    return dict(checks=checks,component_details=details,component_count=len(physical),clashes=clashes,
        deck_backwall_gaps=deck_gap_rows,
        contacts=contacts,maximum_pad_chord_gap_in=max(pad_gaps)/IN,
        actual_beam_lengths_ft=[b-a for a,b in m.beam_limits],bearing_stations_ft=m.bearing_limits,
        support_elevations_ft={sid:{k:row[k] for k in ['top','bottom']} for sid,row in data.items()},
        actual_cambers_in=measured_cambers,requested_cambers_in=m.spans.camber_in.to_list(),minimum_haunch_in=min(haunch_min)/IN,
        longitudinal_grades_percent=measured_grades,
        unconfigured=unsupported)

def add(job):
    from .api import atomic,compact,check_gui
    name=job['document'];rid=job['request_id'];path=ROOT/'reports/transactions'/(rid+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    if path.exists():
        old=json.loads(path.read_text())
        if old['request']!=job:raise ValueError('Request ID reused for another job')
        if old['status'] in ['PREPARED','VALIDATED']:raise RuntimeError('Unknown prior outcome; inspect target state')
        return compact(old)
    for value in job['dimensions'].values():length(value,positive=True)
    for s in job['sources']:
        if hashlib.sha256(Path(s['path']).read_bytes()).hexdigest()!=s['sha256']:raise ValueError('Source changed: '+s['path'])
    prior=App.ActiveDocument.Name if App.ActiveDocument else None
    if job.get('disposable'):
        if name in App.listDocuments():raise ValueError('Disposable document already exists')
        doc=App.newDocument(name)
    else:doc=App.getDocument(name)
    check_gui(doc)
    if doc.getObject('BridgeAssembly'):raise ValueError('Bridge already exists; use an explicit update job')
    before_names=[o.Name for o in doc.Objects];before=source_state(doc,before_names)
    rec=dict(timestamp=datetime.now(timezone.utc).isoformat(),operation='add_pgl_bridge',request=job,
        transaction_id=rid,document=name,status='PREPARED',report_path=str(path),checks=[],
        warnings=job['assumptions'],model_saved=False,errors=[],rollback='NOT NEEDED')
    atomic(path,rec)
    doc.openTransaction(rid)
    try:
        c,objects=construct(doc,job)
        existing=list(doc.getObject('MSEAssembly').FinishedConcrete) if doc.getObject('MSEAssembly') else []
        checker=create_checks(doc,c,objects,existing)
        rec.update(checker.Proxy.last_qa)
        rec['checks'].append(result('existing_objects_preserved',source_state(doc,before_names)==before))
        if any(ch['status']=='FAIL' for ch in rec['checks']):raise ValueError('Physical geometry verification failed')
        coordination=checker.Proxy.last_integration
        rec['coordination']=coordination
        rec['checks'].extend(coordination['checks'])
        # This operation creates a coordination model from conflicting supplied
        # sources. Valid bridge geometry is retained; interface FAIL is explicit
        # in the live model and transaction, not waived or reported as PASS.
        rec['status']='VALIDATED';atomic(path,rec)
        doc.commitTransaction()
        rec['geometry_status']='PASS'
        rec['coordination_status']=checker.CoordinationStatus
        rec['status']='BUILT — COORDINATION FAIL' if checker.CoordinationStatus=='FAIL' else 'PASS WITH PROVISIONAL FOUNDATIONS'
        rec['added_objects']=[o.Name for o in doc.Objects if o.Name not in before_names]
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc()
        doc.abortTransaction();doc.recompute()
        rec['rollback']='VERIFIED' if source_state(doc,before_names)==before and sorted(o.Name for o in doc.Objects)==sorted(before_names) else 'FAILED'
    finally:
        if job.get('disposable'):
            App.closeDocument(name)
            if prior:App.setActiveDocument(prior)
            rec['disposable_closed']=True
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({k:rec[k] for k in ['timestamp','operation','transaction_id','document','status','report_path','model_saved','rollback']})+'\n')
    out=compact(rec)
    for key in ['component_details','contacts','added_objects']:out.pop(key,None)
    return out

def final_report(document_name,transaction_id=None):
    """Read-only geometry audit of the delivered bridge and existing ramp grades."""
    from . import mse
    doc=App.getDocument(document_name);c=doc.getObject('BridgePGL')
    revision=bool(getattr(c,'EndBentRevision',0))
    transaction_id=transaction_id or getattr(c,'DeckGapTransaction',None) or ('end-bents-production-20261002-v1' if revision else 'bridge-production-20261001-v1')
    objects={o.Name:o for o in doc.getObject('BridgeGeometryChecks').Components}
    qa=validate(c,objects)
    revision_qa={}
    if revision:
        from .end_bents import validate_revision
        revision_qa=validate_revision(doc);qa['checks'].extend(revision_qa['checks'])
    coordination=integration(c,objects,list(doc.MSEAssembly.FinishedConcrete))
    ramp_qa=mse.validate(doc,json.loads((ROOT/'jobs/mse-ramps.json').read_text()))
    all_checks=qa['checks']+coordination['checks']
    status='FAIL — bridge-to-MSE coordination' if any(r['status']=='FAIL' for r in coordination['checks']) else 'PASS'
    if any(r['status']=='FAIL' for r in qa['checks']):status='FAIL — bridge geometry'
    if any(r['status']=='FAIL' for r in ramp_qa['checks']):status='FAIL — MSE geometry'
    out=dict(document=document_name,status=status,geometry=qa,coordination=coordination,
        mse_slopes=ramp_qa['slopes'],mse_slope_annotation_checks=ramp_qa['source_slope_annotations'],
        mse_check_counts={s:sum(r['status']==s for r in ramp_qa['checks']) for s in ['PASS','FAIL','NOT CONFIGURED']},
        bridge_check_counts={s:sum(r['status']==s for r in all_checks) for s in ['PASS','FAIL','NOT CONFIGURED']},
        assumptions=list(c.Assumptions),working_model_saved=False,
        end_bent_revision=revision_qa,transaction_id=transaction_id,timestamp=datetime.now(timezone.utc).isoformat())
    report_dir=ROOT/('reports/deck-gap-20261002' if 'DeckEndClearance' in c.PropertiesList else 'reports/end-bent-20261002/revised' if revision else 'reports/bridge')
    report_dir.mkdir(parents=True,exist_ok=True)
    path=report_dir/'final-geometry-checks.json'
    path.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8')
    text=[
        'B4 BRIDGE COMPONENT MODEL — CHECK REPORT',
        'Open FreeCAD document: '+document_name,
        'Status: '+status,
        str(qa['component_count'])+' separate editable components; working model was not saved.',
        'Components: 2 deck segments, 4 FIB36 beams, 4 haunches, 8 bearing pads,',
        ('6 pedestals, 3 caps, 8 square concrete end piles, 4 pier pipe piles, 1 pier wall, 2 backwalls and 4 cheek walls.' if revision else '6 pedestals, 3 caps, 12 pipe piles, and 1 pier wall.'),
        '', 'MEASURED PHYSICAL GEOMETRY',
        'Camber stage: net camber after all dead loads at 120 days.',
        'Camber model: notebook quadratic, anchored to physical bearing centerlines.',
        f"Measured cambers: {qa['actual_cambers_in'][0]:.12f} in / {qa['actual_cambers_in'][1]:.12f} in.",
        f"Measured longitudinal grades: {qa['longitudinal_grades_percent'][0]:+.9f}% / {qa['longitudinal_grades_percent'][1]:+.9f}%.",
        'Measured deck crown: 2% on each side; deck thickness: 6 in vertically.',
        f"Minimum measured flange-edge haunch: {qa['minimum_haunch_in']:.9f} in.",
        f"Physical beam lengths: {qa['actual_beam_lengths_ft'][0]:.6f} ft / {qa['actual_beam_lengths_ft'][1]:.6f} ft.",
        'Internal bridge component clashes: '+str(len(qa['clashes'])),
        'Existing ramp geometry retained; all 12 walking surfaces and 24 DXF slope annotations checked.',
        'Bridge checks: '+str(out['bridge_check_counts']),
        'Existing MSE checks: '+str(out['mse_check_counts']),
        '', 'COORDINATION FAILURES — NOT WAIVED']
    for row in coordination['landings']:
        text.append(f"{row['mse_slab']}: actual horizontal deck gap {row['horizontal_gap_in']:.6f} in (requested joint {row['required_deck_joint_gap_in']:.6f} in); ramp minus deck-end PGL elevation {row['ramp_minus_PGL_in']:+.6f} in.")
    for row in coordination['clashes']:
        text.append(f"{row['bridge']} intersects {row['mse']}: {row['common_volume_ft3']:.9f} cubic feet.")
    if qa.get('deck_backwall_gaps'):
        text+=['','MEASURED DECK-TO-BACKWALL JOINTS',
            'Decks shortened inward; front faces of backwalls and original PGL/support datums retained.']
        for row in qa['deck_backwall_gaps']:
            text.append(f"{row['support']}: FFBW station {row['FFBW_station_ft']:.6f} ft; deck-end station {row['deck_end_station_ft']:.6f} ft; horizontal gap {row['horizontal_gap_in']:.9f} in; closest solid separation {row['solid_distance_in']:.9f} in.")
    if revision:
        text+=['','END-BENT REVISION',
            'Caps: 19 ft 3 in -> 17 ft 6 in transverse; 36 in -> 42 in deep; 3 ft longitudinal width retained.',
            'End piles: 20 in OD steel pipes -> 18 in square concrete; 60 in -> 54 in centers; 12 in embedment.',
            'End pedestals: 3 ft -> 2 ft longitudinal length; 42 in width retained.',
            'End pads: 2.5625 in -> 2.91 in vertical thickness from drawn geometry.',
            'Backwalls are 12 in thick and 4 in below PGL at centerline, with 2% crown.',
            'Cheek walls are 8 in thick; full 3 ft longitudinal extent is inferred.',
            'All pile lengths remain provisional at 90 ft.',
            'Cap top / underside elevations (ft): '+str(qa['support_elevations_ft'])]
        for row in revision_qa['pedestal_height_differences']:
            text.append(f"{row['support']} pedestal {row['beam']}: physically measured center height {row['seat_height_in']:.9f} in; difference from drawn nominal 6 in {row['difference_in']:+.9f} in.")
    text+=['','BASIS AND PROVISIONAL ITEMS']+list(c.Assumptions)+['','NOT CONFIGURED']+qa['unconfigured']
    text+=['','Live controls: BridgePGL. Live result object: BridgeGeometryChecks.',
           'Transaction: '+transaction_id,'Detailed report: '+str(path)]
    report=report_dir/'Bridge-model-check-report.txt'
    report.write_text('\n'.join(text)+'\n',encoding='utf-8')
    return {'status':status,'bridge_checks':out['bridge_check_counts'],'mse_checks':out['mse_check_counts'],
            'report':str(report),'detailed_report':str(path),'working_model_saved':False}

def present(document_name):
    """Show the completed assembly without modifying geometry or saving."""
    import FreeCADGui as Gui
    App.setActiveDocument(document_name)
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()

def repair_display(document_name,request_id):
    """Repair rendering only; preserve all geometry, links and visibility."""
    from .api import atomic,check_gui
    path=ROOT/'reports/transactions'/(request_id+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',request_id):raise ValueError('Invalid request ID')
    if path.exists():raise ValueError('Prior display operation exists; inspect before repeating')
    doc=App.getDocument(document_name);check_gui(doc)
    targets=[doc.BridgePGL]+list(doc.BridgeGeometryChecks.Components)
    before=source_state(doc,[o.Name for o in doc.Objects])
    rec={'operation':'repair_bridge_display','transaction_id':request_id,'document':document_name,
         'timestamp':datetime.now(timezone.utc).isoformat(),'status':'PREPARED','report_path':str(path),
         'before':{o.Name:display_state(o) for o in targets},'model_saved':False}
    atomic(path,rec);doc.openTransaction(request_id)
    try:
        for o in targets:initialize_display(o)
        doc.recompute()
        rec['after']={o.Name:display_state(o) for o in targets}
        rec['geometry_and_sources_unchanged']=source_state(doc,list(before))==before
        physical=[o for o in targets if getattr(o,'ComponentKind','') not in ['','WallEnvelope']]
        rec['visible_components']=sum(o.ViewObject.Visibility and not rec['after'][o.Name]['render_bounds_empty'] for o in physical)
        if not rec['geometry_and_sources_unchanged'] or rec['visible_components']!=40:
            raise ValueError('Rendering repair verification failed')
        doc.commitTransaction();rec['status']='PASS'
        present(document_name)
    except Exception:
        doc.abortTransaction();rec['status']='FAIL';rec['traceback']=traceback.format_exc()
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({k:rec[k] for k in ['timestamp','operation','transaction_id','document','status','report_path','model_saved']})+'\n')
    return {k:v for k,v in rec.items() if k not in ['before','after','traceback']}
