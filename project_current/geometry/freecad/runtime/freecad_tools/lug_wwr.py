"""Editable cheek-lug welded wire reinforcement from the accepted CAD trial.

Geometry and modeled quantities only. Existing steel is never modified. Dimensions
use native unit-bearing properties; paths, Arch wires and schedules remain live.
"""
import json, math
import FreeCAD as App
import Part
from . import beam, cap_cages as cap
from .mse import Serializable, prop
IN=25.4
HOSTS=('BridgeCheekEB11','BridgeCheekEB12','BridgeCheekEB21','BridgeCheekEB22')

def inch(o,n):return getattr(o,n).Value/IN
def local_shape(o,frame):
    s=o.Shape.copy();s.Placement=frame.inverse().multiply(s.Placement);return s

def layout(o):
    frame=o.CageInputs.CageFrame;hb=local_shape(o.Host,frame).BoundBox
    cb=local_shape(o.Cap,frame).BoundBox
    width=o.CageInputs.PGL.EndCapWidth.Value/IN
    length=cap.geometry_evaluation(cap.live_case(o.CageInputs)).value('L_cap')
    mirror_x=o.CheekIndex==2;mirror_y=hb.YMax/IN<width+inch(o,'LugProjection')/2
    D=inch(o,'WireDiameter');P=inch(o,'GridSpacing');B=inch(o,'BendRadius')
    if min(D,P,B)<=0 or B<=D:raise ValueError('Positive wire/grid dimensions and bend radius greater than diameter required')
    edge=inch(o,'EdgeInset');xv=inch(o,'BottomLegX');zlo=inch(o,'BottomLowZ');zh=inch(o,'BottomHighZ')
    xend=cb.XMin/IN+inch(o,'BottomExtension');y0=edge+inch(o,'AcrossGridShift')
    def pt(x,y,z):return (length-x if mirror_x else x,width-y if mirror_y else y,z)
    rows={}
    def add(ident,family,direction,points,segments):
        rows[ident]=dict(id=ident,family=family,direction=direction,points=[pt(*p) for p in points],segments=segments)
    k=0
    while y0+k*P<=width-edge:
        y=y0+k*P
        points=[(xv,y,zlo),(xv,y,zh-B),(xv+B-B/math.sqrt(2),y,zh-B+B/math.sqrt(2)),(xv+B,y,zh),(xend,y,zh)]
        add('BottomL'+str(k+1),'bottom','bent',points,[('line',0,1),('arc',1,2,3),('line',3,4)]);k+=1
    smin=-(zh-B-zlo+math.pi*B/2);smax=xend-xv-B
    station0=cb.XMin/IN+inch(o,'AlongGridShift')-xv-B
    first=math.ceil((smin-station0)/P);last=math.floor((smax-station0)/P)
    for k in range(first,last+1):
        s=station0+k*P
        if s>=0:x,z=xv+B+s,zh-D
        elif s>=-math.pi*B/2:
            t=s/B;x,z=xv+B+(B-D)*math.sin(t),zh-B+(B-D)*math.cos(t)
        else:x,z=xv+D,zh-B+s+math.pi*B/2
        add('BottomCross'+str(k+6),'bottom','cross',[(x,edge,z),(x,width-edge,z)],[('line',0,1)])
    sx=inch(o,'SidePlaneX');start=inch(o,'OuterCheekVerticalY')-inch(o,'SideLap')
    end=width+inch(o,'LugProjection')-edge;zend=hb.ZMax/IN-edge
    for k in range(math.floor((end-inch(o,'SideGridStartY'))/P)+1):
        y=inch(o,'SideGridStartY')+k*P
        add('SideV'+str(k+1),'side','vertical',[(sx,y,zlo),(sx,y,zend)],[('line',0,1)])
    zstart=inch(o,'SideGridStartZ')
    for k in range(math.floor((zend-zstart)/P)+1):
        z=zstart+k*P
        add('SideH'+str(k+1),'side','horizontal',[(sx+D,start,z),(sx+D,end,z)],[('line',0,1)])
    return rows

class InputsProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        o.LayoutJSON=json.dumps(layout(o));o.Frame=o.CageInputs.CageFrame
        if o.AutoSync:sync(o)

class PathProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        r=json.loads(o.Inputs.LayoutJSON)[o.WireID]
        pts=[App.Vector(*(n*IN for n in p)) for p in r['points']];edges=[]
        for kind,*ii in r['segments']:
            edges.append(Part.makeLine(pts[ii[0]],pts[ii[1]]) if kind=='line' else Part.Arc(pts[ii[0]],pts[ii[1]],pts[ii[2]]).toShape())
        o.Shape=Part.Wire(edges);o.Length=o.Shape.Length;o.NominalDiameter=o.Inputs.WireDiameter

class WireProxy(cap.ArchRebar._Rebar):
    def onChanged(self,o,name):
        if name=='Host':return
        super().onChanged(o,name)
    def execute(self,o):
        super().execute(o)
        o.Placement=o.WWRInputs.Frame
        o.NominalWeightLb=o.TotalLength.Value/IN*0.014/1728*490

def sync(inp):
    doc=inp.Document;rows=json.loads(inp.LayoutJSON);paths=doc.getObject(inp.Prefix+'Paths')
    if paths is None:return
    groups={f:doc.getObject(inp.Prefix+f.title()) for f in ['bottom','side']}
    existing={o.Name:o for g in groups.values() for o in g.Group}
    wanted={inp.Prefix+key for key in rows}
    for n in set(existing)-wanted:
        p=existing[n].Base;doc.removeObject(n);doc.removeObject(p.Name)
    for ident,row in rows.items():
        name=inp.Prefix+ident;bar=doc.getObject(name)
        if bar is None:
            path=doc.addObject('Part::FeaturePython',name+'Path')
            for typ,k,v in [('App::PropertyLink','Inputs',inp),('App::PropertyString','WireID',ident),('App::PropertyLength','Length','0 in'),('App::PropertyLength','NominalDiameter','0.134 in')]:prop(path,typ,k,v,'WWR')
            PathProxy(path);path.Proxy.execute(path);paths.addObject(path)
            bar=beam.native_rebar(doc,name,path,inp.WireDiameter.Value,1);WireProxy(bar)
            prop(bar,'App::PropertyLink','WWRInputs',inp,'WWR');prop(bar,'App::PropertyString','WWRSheet',row['family'],'WWR')
            prop(bar,'App::PropertyString','WireDirection',row['direction'],'WWR');prop(bar,'App::PropertyFloat','NominalWeightLb',0.,'Quantity')
            bar.Mark='4x4 W1.4xW1.4 '+ident;bar.setExpression('Diameter',path.Name+'.NominalDiameter');groups[row['family']].addObject(bar)
        bar.Base.Proxy.execute(bar.Base);bar.Proxy.execute(bar)

class QuantitiesProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        bars=[b for i in o.Inputs for f in ['Bottom','Side'] for b in o.Document.getObject(i.Prefix+f).Group]
        o.Wires=bars;o.WireCount=len(bars);o.SheetCount=2*len(o.Inputs)
        o.TotalWireLength=sum(b.TotalLength.Value for b in bars)
        o.NominalSteelWeightLb=sum(b.NominalWeightLb for b in bars)
        o.GeometricWireVolume=sum(b.Shape.Volume for b in bars)
        rows=[]
        for inp in o.Inputs:
            for family in ['bottom','side']:
                bb=[b for b in bars if b.WWRInputs==inp and b.WWRSheet==family]
                rows.append(dict(host=inp.Host.Name,sheet=family,wires=len(bb),length_in=sum(b.TotalLength.Value/IN for b in bb),weight_lb=sum(b.NominalWeightLb for b in bb)))
        for i,row in enumerate(rows,1):
            setattr(o,'S'+str(i)+'WireCount',row['wires'])
            setattr(o,'S'+str(i)+'Length',row['length_in']*IN)
            setattr(o,'S'+str(i)+'WeightLb',row['weight_lb'])
        o.ScheduleJSON=json.dumps(rows)

def schedule(doc):
    q=doc.CheekLugWWRQuantities;q.Proxy.execute(q);s=doc.CheekLugWWRSchedule
    for i,h in enumerate(['Cheek','Sheet','WWR','Wires','Length (in)','Nominal lb'],1):s.set(chr(64+i)+'1',h)
    for r,row in enumerate(json.loads(q.ScheduleJSON),2):
        for c,v in enumerate([row['host'],row['sheet'],'4x4 W1.4xW1.4',row['wires'],row['length_in'],row['weight_lb']],1):s.set(chr(64+c)+str(r),str(v))
        s.set('D'+str(r),'=CheekLugWWRQuantities.S'+str(r-1)+'WireCount')
        s.set('E'+str(r),'=CheekLugWWRQuantities.S'+str(r-1)+'Length / (1 in)')
        s.set('F'+str(r),'=CheekLugWWRQuantities.S'+str(r-1)+'WeightLb')
    s.set('A11','TOTAL');s.set('D11','=CheekLugWWRQuantities.WireCount');s.set('E11','=CheekLugWWRQuantities.TotalWireLength / (1 in)');s.set('F11','=CheekLugWWRQuantities.NominalSteelWeightLb')
    s.set('A13','Eight separate sheets; 4 in grid, nominal 0.134 in wire; nominal weight uses W1.4 area 0.014 in^2 and 490 pcf.')
    s.set('A14','Accepted layout: bottom extension 8.875 in into cap, side lap 8.125 in past outer cheek vertical.')
    s.set('A15','Existing 14 stirrup overlaps deferred in COH-025. Anchorage/fabrication acceptance remains open.')
    s.setStyle('A1:F1','bold','add');s.setColumnWidth('A',180);s.setColumnWidth('B',90);s.setColumnWidth('C',170)
    for c in ['D','E','F']:s.setColumnWidth(c,130)

def add(doc):
    if doc.getObject('CheekLugWWR'):raise ValueError('WWR already exists')
    root=doc.addObject('App::DocumentObjectGroup','CheekLugWWR');root.Label='Cheek lug WWR - 4x4 W1.4xW1.4'
    inputs=[]
    for host in HOSTS:
        h=doc.getObject(host);sid=h.SupportID;prefix='WWR'+host.replace('Bridge','')
        group=doc.addObject('App::DocumentObjectGroup',prefix);root.addObject(group)
        inp=doc.addObject('App::FeaturePython',prefix+'Inputs');group.addObject(inp)
        for typ,k,v in [('App::PropertyLink','Host',h),('App::PropertyLink','Cap',doc.getObject('BridgeCap'+sid)),('App::PropertyLink','CageInputs',doc.getObject('Cage'+sid+'Inputs')),('App::PropertyString','Prefix',prefix),('App::PropertyInteger','CheekIndex',int(host[-1])),('App::PropertyString','LayoutJSON','{}'),('App::PropertyPlacement','Frame',App.Placement()),('App::PropertyBool','AutoSync',False)]:prop(inp,typ,k,v,'WWR')
        values={'WireDiameter':'0.134 in','GridSpacing':'4 in','BendRadius':'1 in','EdgeInset':'2.125 in','MinimumCover':'2 in','BottomLegX':'3.125 in','BottomLowZ':'-3.875 in','BottomHighZ':'2.625 in','BottomExtension':'8.875 in','AlongGridShift':'0.625 in','AcrossGridShift':'0.875 in','SidePlaneX':'2.75 in','SideLap':'8.125 in','OuterCheekVerticalY':'36.75 in','SideGridStartY':'28.75 in','SideGridStartZ':'-3.5 in','LugProjection':'6 in'}
        for k,v in values.items():prop(inp,'App::PropertyDistance' if k in ['BottomLowZ','SideGridStartZ'] else 'App::PropertyLength',k,v,'WWR dimensions')
        prop(inp,'App::PropertyString','DesignBasis','User accepted native-offset trial, 14 October 2026. WWR geometry only; bend/development/fabrication acceptance remains open.','WWR')
        InputsProxy(inp);inp.Proxy.execute(inp)
        for suffix in ['Paths','Bottom','Side']:
            g=doc.addObject('App::DocumentObjectGroup',prefix+suffix);group.addObject(g)
        sync(inp);inp.AutoSync=True;inputs.append(inp)
        for name in ['LayoutJSON','Frame','Prefix']:inp.setEditorMode(name,1)
    q=doc.addObject('App::FeaturePython','CheekLugWWRQuantities');root.addObject(q)
    for typ,k,v in [('App::PropertyLinkList','Inputs',inputs),('App::PropertyLinkList','Wires',[]),('App::PropertyInteger','WireCount',0),('App::PropertyInteger','SheetCount',0),('App::PropertyLength','TotalWireLength','0 in'),('App::PropertyFloat','NominalSteelWeightLb',0.),('App::PropertyVolume','GeometricWireVolume',0.),('App::PropertyString','ScheduleJSON','[]')]:prop(q,typ,k,v,'WWR quantities')
    for i in range(1,9):
        for typ,suffix,v in [('App::PropertyInteger','WireCount',0),('App::PropertyLength','Length','0 in'),('App::PropertyFloat','WeightLb',0.)]:prop(q,typ,'S'+str(i)+suffix,v,'WWR sheet quantities')
    QuantitiesProxy(q)
    s=doc.addObject('Spreadsheet::Sheet','CheekLugWWRSchedule');root.addObject(s);schedule(doc)
    checks=doc.addObject('App::FeaturePython','CheekLugWWRChecks');root.addObject(checks)
    prop(checks,'App::PropertyString','Status','NOT CHECKED','WWR verification');prop(checks,'App::PropertyString','ReportJSON','{}','WWR verification')
    prop(checks,'App::PropertyString','Scope','Snapshot of physical checks at adoption. Rerun lug_wwr.validate after editing. Existing stirrup clashes remain Deferred in COH-025.','WWR verification')
    return inputs

def near(a,b):
    x,y=a.BoundBox,b.BoundBox
    return not(x.XMax<y.XMin or y.XMax<x.XMin or x.YMax<y.YMin or y.YMax<x.YMin or x.ZMax<y.ZMin or y.ZMax<x.ZMin)

def validate(doc):
    q=doc.CheekLugWWRQuantities;q.Proxy.execute(q);results=[]
    for sid in ['EB1','EB2']:
        frame=doc.getObject('Cage'+sid+'Inputs').CageFrame
        wires=[b for b in q.Wires if b.WWRInputs.CageInputs.SupportID==sid]
        oldsteel=[o for o in doc.Objects if all(hasattr(o,k) for k in ['Diameter','Amount','Base']) and not hasattr(o,'WWRInputs')]
        old=[(o.Name,local_shape(o,frame)) for o in oldsteel]
        hosts=[local_shape(doc.getObject(n),frame) for n in ['BridgeCap'+sid,'BridgeCheek'+sid+'1','BridgeCheek'+sid+'2']]
        envelope=hosts[0].fuse(hosts[1]).fuse(hosts[2]).removeSplitter()
        pile=[(o.Name,local_shape(o,frame)) for o in doc.Objects if o.Name.startswith('BridgePile'+sid) and hasattr(o,'Shape')]
        local={b.Name:local_shape(b,frame) for b in wires};covers=[];pairs=[];intended=0;clashes=[]
        for b in wires:
            s=local[b.Name];cover=min(s.distToShape(f)[0]/IN for f in envelope.Faces);outside=s.cut(envelope).Volume/IN**3
            covers.append(dict(wire=b.Name,minimum_cover_in=cover,outside_volume_in3=outside,status='PASS' if cover>=2 and outside==0 else 'FAIL'))
            for n,t in old+pile:
                if not near(s,t):continue
                volume=s.common(t).Volume/IN**3;c=dict(a=b.Name,b=n,common_volume_in3=volume);pairs.append(c)
                if volume>0:clashes.append(c)
        for i,a in enumerate(wires):
            for b in wires[i+1:]:
                s,t=local[a.Name],local[b.Name]
                if not near(s,t):continue
                if a.WWRInputs==b.WWRInputs and a.WWRSheet==b.WWRSheet and a.WireDirection!=b.WireDirection:intended+=1;continue
                volume=s.common(t).Volume/IN**3
                if volume>0:clashes.append(dict(a=a.Name,b=b.Name,common_volume_in3=volume))
        results.append(dict(support=sid,wires=len(wires),cover_checks=covers,physical_candidate_pairs=pairs,clashes=clashes,intended_welded_crossings=intended))
    report=dict(status='PASS' if all(not r['clashes'] and all(c['status']=='PASS' for c in r['cover_checks']) for r in results) else 'FAIL',results=results,scope='New WWR geometry only. Existing steel clashes and other findings remain unresolved.')
    doc.CheekLugWWRChecks.Status=report['status'];doc.CheekLugWWRChecks.ReportJSON=json.dumps(report)
    return report
