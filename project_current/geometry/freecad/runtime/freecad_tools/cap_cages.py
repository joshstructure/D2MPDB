"""Native Arch rebars driven by the pinned project cage geometry and live inputs.

No structural calculations are adopted or rerun. Analytic arcs replace drawing
chords; hoop closures use the tested concrete-beam centerline helper.
"""
import sys,json,math,hashlib,re,traceback
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
import FreeCAD as App
import Part
from . import bridge,beam
from .mse import Serializable,prop
from .geometry import result
ROOT=bridge.ROOT;IN=25.4;FT=304.8
VENDOR=ROOT/'freecad_tools/vendor_cap_20261010'
for p in [VENDOR,Path(App.getResourceDir())/'Mod/BIM',Path(App.getResourceDir())/'Mod/Draft',
          Path(App.getUserAppDataDir())/'Mod/Reinforcement']:
    if str(p) not in sys.path:sys.path.insert(0,str(p))
import ArchRebar
from pier_cap.model import geometry_evaluation,bar_positions,BAR_DIAMETER
from pier_cap.detailing import hook_paths
from pier_cap.transverse import scheduled_bars,bar_shape
from pier_cap.end_grid import geometry as end_geometry
from pier_cap.lrfd_checks import settings,closure_extension
from pier_cap.hooks import stirrup_hook_extension
WEIGHTS={3:.376,4:.668,5:1.043,6:1.502,7:2.044,8:2.670,9:3.400,10:4.303,11:5.313}
PARAMS=('Bar_N1','Bar_N2','Bar_N3','n_N1','n_N2','n_N3','Bar_P','n_P1','n_P2','Bar_B','n_B1','n_B2',
 'Bar_v','Bar_skin','n_skin','s_row','C_t','C_b','C_s','C_pile')
_CACHE={}

def live_case(o):
    case=json.loads(o.SourceCaseJSON);p=case['inputs']
    for key in PARAMS:
        value=getattr(o,key);p[key]=value.Value/IN if hasattr(value,'Value') else value
    c=o.PGL;end=o.SupportID!='Pier'
    p.update(b=c.EndCapWidth.Value/IN if end else c.PierCapWidth.Value/IN,
        h=c.EndCapDepth.Value/IN if end else c.CapDepth.Value/IN,
        D_pile=c.EndPileSize.Value/IN if end else c.PileDiameter.Value/IN,
        S_pile=(c.EndPileSpacing.Value if end else c.PileSpacing.Value)/FT,
        Pile_embed=(c.EndPileEmbedment.Value if end else c.PierPileEmbedment.Value)/IN)
    case['transverse_detail']=json.loads(o.TransverseRunsJSON)
    case['end_face_grid']=json.loads(o.EndGridJSON)
    case['added_bar_layout']=json.loads(o.AddedBarsJSON)
    return case

def layout(case):
    key=json.dumps(case,sort_keys=True)
    if key in _CACHE:return _CACHE[key]
    e=geometry_evaluation(case);p=e.case['inputs'];L=e.value('L_cap');rows=[]
    for i,b in enumerate(bar_positions(e,'P'),1):
        rows.append(dict(id=f'Long{i:02}',kind='longitudinal',bar=b['bar'],diameter=b['diameter'],family=b['kind'],
            points=[(p['C_s'],b['x'],b['y']),(L-p['C_s'],b['x'],b['y'])],segments=[('line',0,1)]))
    for i,t in enumerate(hook_paths(e,bar_positions(e,'B')),1):
        rows.append(dict(id=f'Added{i:02}',kind='added',bar=t['bar']['bar'],diameter=t['bar']['diameter'],family='Added span '+str(t['span']),
            points=[(x,t['bar']['x'],z) for x,z in t['points']],segments=[('line',0,1),('arc',1,9,17),('line',17,18),('arc',18,26,34),('line',34,35)]))
    runs={r['id']:r for r in case['transverse_detail']['runs']}
    for bar in scheduled_bars(case):
        run=runs[bar['run']];s=bar_shape(e,run);ident=re.sub('[^A-Za-z0-9]','_',bar['id'])
        row=dict(id='Trans_'+ident,kind=run['kind'],bar=run['bar'],diameter=s['diameter'],family=run['id']+' '+run['kind'],station=bar['station_in'],run=run,shape=s)
        if run['kind']=='pile_u':
            if len(s['points_3d'])!=102:raise ValueError('Unsupported U topology')
            row.update(points=[(bar['station_in']+x,y,z) for x,y,z in s['points_3d']],segments=[('line',0,1),('arc',1,13,25),('line',25,26),('arc',26,38,50),('line',50,51),('arc',51,63,75),('line',75,76),('arc',76,88,100),('line',100,101)])
        else:
            s2=settings(case)
            if s2['hoop_closure']!='hooks' or s2['closure_angle']!=135:raise ValueError('Only selected 135-degree hooked hoop supported')
            row.update(width=p['b'],height=p['h'],cover=p['C_s'],radius=s['radius'],tail=closure_extension(s2,run['bar']))
            if not p['C_s']==p['C_t']==p['C_b']:raise ValueError('Tested hoop requires equal covers')
        rows.append(row)
    for b in end_geometry(e):
        rows.append(dict(id=re.sub('[^A-Za-z0-9]','_',b['id']),kind='end_grid',bar=b['bar'],diameter=b['diameter'],family='End '+b['end']+' '+b['direction'],
            points=b['points'],segments=[('line',0,1),('arc',1,13,25),('line',25,26),('arc',26,38,50),('line',50,51)]))
    out={r['id']:r for r in rows}
    if len(out)!=len(rows):raise ValueError('Duplicate bar identities')
    if len(_CACHE)>12:_CACHE.clear()
    _CACHE[key]=out
    return out

def analytic_wire(row):
    if row['kind']=='hoop':
        # Invoke the tested example's native centerline generator unchanged.
        q=lambda x:App.Units.Quantity(str(x)+' in')
        inp=SimpleNamespace(Width=q(row['width']),Height=q(row['height']),StirrupDiameter=q(row['diameter']),
            StirrupCenterlineRadius=q(row['radius']),EffectiveStirrupCover=q(row['cover']),
            StirrupFirstDatum=q(row['station']),HookExtension=q(row['tail']))
        holder=SimpleNamespace(Inputs=inp)
        beam.StirrupPathProxy.execute(None,holder)
        return holder.Shape
    points=[App.Vector(*(v*IN for v in p)) for p in row['points']];edges=[]
    for typ,*ii in row['segments']:
        edges.append(Part.makeLine(points[ii[0]],points[ii[1]]) if typ=='line' else Part.Arc(points[ii[0]],points[ii[1]],points[ii[2]]).toShape())
    return Part.Wire(edges)

def cage_frame(o):
    c=o.PGL;row=bridge.support_data(c)[o.SupportID];m=bridge.model(c)
    origin=App.Vector((row['station']-m.start+row['width']/2)*FT,-row['length']*FT/2,row['bottom']*FT)
    return c.Frame.multiply(App.Placement(origin,App.Rotation(App.Vector(0,0,1),90)))

class InputsProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        rows=layout(live_case(o));o.LayoutJSON=json.dumps(rows);o.CageFrame=cage_frame(o)
        o.SourceBarCount=len(rows)
        if o.AutoSync:sync_bars(o,rows)

class PathProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        rows=json.loads(o.Inputs.LayoutJSON);row=rows[o.BarID]
        o.Shape=analytic_wire(row);o.Length=o.Shape.Length
        o.NominalDiameter=str(row['diameter'])+' in';o.BarNumber=row['bar'];o.Family=row['family']
        o.QuantityBasis='Exact analytic bends and straight tails; nominal diameter; no ribs, laps or waste.'
        if row['kind']=='hoop':o.QuantityBasis+=' 135-degree hook closure at top left uses tested beam-example layout; closure location is a modeling assumption.'

class RebarProxy(ArchRebar._Rebar):
    def onChanged(self,o,name):
        # Arch normally touches Host when linking a rebar. These native bridge
        # caps do not consume reinforcement children; their concrete geometry
        # must not be regenerated merely because a bar count changes.
        if name=='Host' and getattr(getattr(o,'Host',None),'ComponentKind',None)=='Cap':return
        super().onChanged(o,name)
    def execute(self,o):
        super().execute(o)
        o.Placement=o.CageInputs.CageFrame
        if 'NominalWeightLb' in o.PropertiesList:
            o.NominalWeightLb=o.TotalLength.Value/FT*WEIGHTS[o.Base.BarNumber]

class QuantitiesProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        rows=[];volume=0.;total=0.;weight=0.;count=0
        for rb in o.Bars:
            size=rb.Base.BarNumber;length_mm=rb.TotalLength.Value
            row=dict(object=rb.Name,mark=rb.Mark,bar=size,family=rb.Base.Family,count=rb.Amount,
                each_length_ft=rb.Length.Value/FT,total_length_ft=length_mm/FT,nominal_weight_lb=length_mm/FT*WEIGHTS[size],volume_ft3=rb.Shape.Volume/FT**3)
            rows.append(row);volume+=rb.Shape.Volume;total+=length_mm;weight+=row['nominal_weight_lb'];count+=rb.Amount
        o.TotalBars=count;o.TotalSteelLength=total;o.NominalSteelWeightLb=weight;o.NominalSteelVolume=volume
        o.CapConcreteNetVolume=o.Cap.Shape.Volume;o.ScheduleJSON=json.dumps(rows)

def sync_bars(inputs,rows=None):
    """Materialize changing counts from the live design, retaining stable bar IDs."""
    doc=inputs.Document;rows=rows or layout(live_case(inputs));prefix='Cage'+inputs.SupportID
    group=doc.getObject(prefix);paths=doc.getObject(prefix+'Paths');steel=doc.getObject(prefix+'Bars')
    q=doc.getObject(prefix+'Quantities')
    if not all([group,paths,steel,q]):return
    wanted={prefix+r for r in rows};existing={r.Name:r for r in steel.Group}
    for n in sorted(set(existing)-wanted):
        base=existing[n].Base;doc.removeObject(n);doc.removeObject(base.Name)
    bars=[]
    for ident,row in rows.items():
        n=prefix+ident;rb=doc.getObject(n)
        if rb is None:
            path=doc.addObject('Part::FeaturePython',n+'Path')
            for typ,key,val in [('App::PropertyLink','Inputs',inputs),('App::PropertyString','BarID',ident),('App::PropertyLength','Length','0 in'),
                ('App::PropertyLength','NominalDiameter',str(row['diameter'])+' in'),('App::PropertyInteger','BarNumber',row['bar']),('App::PropertyString','Family',row['family']),('App::PropertyString','QuantityBasis','')]:prop(path,typ,key,val,'Rebar path')
            PathProxy(path);paths.addObject(path);path.Proxy.execute(path)
            rb=beam.native_rebar(doc,n,path,path.NominalDiameter.Value,1)
            RebarProxy(rb);prop(rb,'App::PropertyLink','CageInputs',inputs,'Source')
            rb.Host=inputs.Cap;rb.Mark=inputs.SupportID+'-'+ident;rb.Rounding=0
            rb.setExpression('Diameter',path.Name+'.NominalDiameter')
            steel.addObject(rb)
            if App.GuiUp:
                path.ViewObject.Visibility=False;rb.ViewObject.ShapeColor=(.22,.40,.66)
        rb.Label=inputs.SupportID+' '+row['family']+' #'+str(row['bar'])+' '+ident
        if 'NominalWeightLb' not in rb.PropertiesList:
            prop(rb,'App::PropertyFloat','NominalWeightLb',0.,'Live quantities');rb.setEditorMode('NominalWeightLb',1)
        bars.append(rb)
    q.Bars=bars
    checker=doc.getObject(prefix+'Checks')
    if checker:checker.Bars=bars
    sheet=doc.getObject(prefix+'Schedule')
    if sheet and sheet.BarNames!=[b.Name for b in bars]:write_schedule(inputs,sheet,bars)

def write_schedule(inp,sheet,bars):
    sheet.clearAll()
    headers=['Mark','Family','US #','Count','Dia (in)','Each length (ft)','Total length (ft)','Nominal weight (lb)']
    for col,title in zip('ABCDEFGH',headers):sheet.set(col+'1',title)
    for i,rb in enumerate(bars,2):
        sheet.set('A'+str(i),rb.Mark);sheet.set('B'+str(i),rb.Base.Family)
        expressions={'C':rb.Base.Name+'.BarNumber','D':rb.Name+'.Amount','E':rb.Name+'.Diameter / (1 in)',
            'F':rb.Name+'.Length / (1 ft)','G':rb.Name+'.TotalLength / (1 ft)','H':rb.Name+'.NominalWeightLb'}
        for col,expr in expressions.items():sheet.set(col+str(i),'='+expr)
    end=len(bars)+2;q='Cage'+inp.SupportID+'Quantities';sheet.set('A'+str(end),'TOTAL')
    for col,expr in [('D',q+'.TotalBars'),('G',q+'.TotalSteelLength / (1 ft)'),('H',q+'.NominalSteelWeightLb')]:sheet.set(col+str(end),'='+expr)
    sheet.set('A'+str(end+2),'Modeled centerline lengths; nominal weights; no laps/waste. See cage check results.')
    for col,width in zip('ABCDEFGH',[160,160,60,65,85,135,135,150]):sheet.setColumnWidth(col,width)
    sheet.setStyle('A1:H1','bold','add');sheet.setBackground('A1:H1',(.85,.9,.95))
    sheet.setStyle('A'+str(end)+':H'+str(end),'bold','add')
    sheet.BarNames=[b.Name for b in bars];sheet.TotalRow=end

class ChecksProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        geometry=geometry_checks(o.Inputs);detail=clearance_checks(o.Inputs)
        self.last=dict(geometry=geometry,detailing=detail)
        o.GeometryStatus='FAIL' if any(c['status']=='FAIL' for c in geometry['checks']) else 'PASS'
        o.DetailingStatus='FAIL' if any(c['status']=='FAIL' for c in detail['checks']) else 'PASS'
        o.ReportJSON=json.dumps(self.last)
        o.Failures=[r['name'] for r in geometry['checks']+detail['checks'] if r['status']=='FAIL']
        o.Label=o.Inputs.SupportID+' cage checks - geometry '+o.GeometryStatus+'; detailing '+o.DetailingStatus

def attach_review_and_schedules(doc):
    created=[]
    for sid in ('EB1','Pier','EB2'):
        prefix='Cage'+sid;inp=doc.getObject(prefix+'Inputs');group=doc.getObject(prefix);bars=doc.getObject(prefix+'Quantities').Bars
        sheet=doc.addObject('Spreadsheet::Sheet',prefix+'Schedule');sheet.Label=sid+' LIVE bar schedule'
        prop(sheet,'App::PropertyStringList','BarNames',[],'Schedule');prop(sheet,'App::PropertyInteger','TotalRow',0,'Schedule')
        write_schedule(inp,sheet,bars);group.addObject(sheet);created.append(sheet)
        check=doc.addObject('App::FeaturePython',prefix+'Checks');group.addObject(check)
        for typ,n,v in [('App::PropertyLink','Inputs',inp),('App::PropertyLinkList','Bars',bars),('App::PropertyLinkList','Piles',[doc.getObject(f'BridgePile{sid}P{j+1}') for j in range(4)]),
            ('App::PropertyString','GeometryStatus','PENDING'),('App::PropertyString','DetailingStatus','PENDING'),('App::PropertyString','ReportJSON','{}'),('App::PropertyStringList','Failures',[])]:prop(check,typ,n,v,'Live checks')
        ChecksProxy(check);created.append(check)
    sheet=doc.addObject('Spreadsheet::Sheet','BridgeConcreteSchedule');sheet.Label='LIVE bridge component quantities'
    headers=['Object','Component','Net volume (ft3)','Net volume (yd3)']
    for col,title in zip('ABCD',headers):sheet.set(col+'1',title)
    for row,o in enumerate(doc.BridgeGeometryChecks.Components,2):
        sheet.set('A'+str(row),o.Name);sheet.set('B'+str(row),o.ComponentKind)
        sheet.set('C'+str(row),'='+o.Name+'.NetVolume / (1 ft^3)');sheet.set('D'+str(row),'='+o.Name+'.NetVolume / (1 yd^3)')
    for col,width in zip('ABCD',[230,150,145,145]):sheet.setColumnWidth(col,width)
    sheet.setStyle('A1:D1','bold','add');doc.BridgeAssembly.addObject(sheet);created.append(sheet)
    doc.recompute(created)
    return created

def build(doc,sid,source):
    raw=Path(source['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('Case source changed')
    case=json.loads(raw);prefix='Cage'+sid
    group=doc.addObject('App::DocumentObjectGroup',prefix);group.Label=sid+' reinforcement - current selected case'
    doc.BridgeAssembly.addObject(group)
    for tail in ('Paths','Bars'):
        ob=doc.addObject('App::DocumentObjectGroup',prefix+tail);group.addObject(ob)
    inp=doc.addObject('App::FeaturePython',prefix+'Inputs');group.addObject(inp)
    values=[('App::PropertyLink','Cap',doc.getObject('BridgeCap'+sid)),('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyString','SupportID',sid),
        ('App::PropertyString','SourceCaseJSON',raw.decode('utf-8')),('App::PropertyString','SourceSHA256',source['sha256']),('App::PropertyString','SourcePath',source['path']),
        ('App::PropertyString','TransverseRunsJSON',json.dumps(case['transverse_detail'])),('App::PropertyString','EndGridJSON',json.dumps(case['end_face_grid'])),
        ('App::PropertyString','AddedBarsJSON',json.dumps(case['added_bar_layout'])),('App::PropertyString','LayoutJSON','{}'),('App::PropertyInteger','SourceBarCount',0),
        ('App::PropertyPlacement','CageFrame',App.Placement()),('App::PropertyBool','AutoSync',False),
        ('App::PropertyString','Limitations','Source field-bent rotations retained. Exact steel geometry is not anchorage or fabrication approval. Hoop closure location assumed at top left using tested beam example; check physical clashes. Native Arch Amount can make additional copies; live schedule counts every copy.')]
    for typ,n,v in values:prop(inp,typ,n,v,'Cage sources')
    for key in PARAMS:
        v=case['inputs'][key];integer=key.startswith(('Bar_','n_'))
        prop(inp,'App::PropertyInteger' if integer else 'App::PropertyLength',key,int(v) if integer else str(v)+' in','Editable cage inputs')
    for n in ['SourceCaseJSON','SourceSHA256','SourcePath','LayoutJSON','SourceBarCount','CageFrame','AutoSync']:inp.setEditorMode(n,1)
    InputsProxy(inp);inp.Proxy.execute(inp)
    q=doc.addObject('App::FeaturePython',prefix+'Quantities');group.addObject(q)
    for typ,n,v in [('App::PropertyLink','Cap',inp.Cap),('App::PropertyLinkList','Bars',[]),('App::PropertyInteger','TotalBars',0),
        ('App::PropertyLength','TotalSteelLength','0 in'),('App::PropertyFloat','NominalSteelWeightLb',0.),('App::PropertyVolume','NominalSteelVolume',0.),
        ('App::PropertyVolume','CapConcreteNetVolume',0.),('App::PropertyString','ScheduleJSON','[]')]:prop(q,typ,n,v,'Live quantities');q.setEditorMode(n,1)
    QuantitiesProxy(q);sync_bars(inp);inp.AutoSync=True;inp.touch()
    return inp

def geometry_checks(inp):
    q=inp.Document.getObject('Cage'+inp.SupportID+'Quantities');checks=[];length_sum=0;count=0;weight=0;rows=[]
    for rb in q.Bars:
        s=rb.Shape.copy();d=rb.Diameter.Value;L=rb.Base.Shape.Length*rb.Amount
        cs=[f.Surface.Radius for f in s.Faces if isinstance(f.Surface,Part.Cylinder)]
        checks.append(result(rb.Name+'_native_geometry',getattr(rb.Proxy,'Type',None)=='Rebar' and s.isValid() and len(s.Solids)==rb.Amount,solids=len(s.Solids),expected=rb.Amount))
        checks.append(result(rb.Name+'_nominal_diameter',bool(cs) and all(abs(2*r-d)<=.0254 for r in cs)))
        expected=math.pi*d*d/4*L
        checks.append(result(rb.Name+'_independent_volume_length',abs(s.Volume-expected)<=max(1e-5,expected*1e-8),measured_length_ft=s.Volume/(math.pi*d*d/4)/FT,path_length_ft=L/FT))
        checks.append(result(rb.Name+'_live_links',rb.Host==inp.Cap and rb.Base.Inputs==inp and rb.CageInputs==inp and abs(rb.TotalLength.Value-L)<=.0254,reported_length=rb.TotalLength.Value,expected_length=L))
        samples=[e.valueAt((e.FirstParameter+e.LastParameter)/2) for e in rb.Base.Shape.Edges]
        checks.append(result(rb.Name+'_physical_source_placement',all(s.isInside(inp.CageFrame.multVec(p),.0254,True) for p in samples)))
        length_sum+=L;count+=len(s.Solids);weight+=L/FT*WEIGHTS[rb.Base.BarNumber]
        rows.append(dict(name=rb.Name,kind=json.loads(inp.LayoutJSON)[rb.Base.BarID]['kind'],bar=rb.Base.BarNumber,volume_ft3=s.Volume/FT**3,length_ft=L/FT))
    checks.append(result(inp.SupportID+'_live_totals',count==q.TotalBars and abs(length_sum-q.TotalSteelLength.Value)<=.0254 and abs(weight-q.NominalSteelWeightLb)<=1e-7,physical_bars=count,length_ft=length_sum/FT,weight_lb=weight))
    checks.append(result(inp.SupportID+'_source_count',len(q.Bars)==inp.SourceBarCount and count==inp.SourceBarCount,source_count=inp.SourceBarCount,physical_count=count))
    return dict(checks=checks,bars=rows,totals=dict(count=count,length_ft=length_sum/FT,weight_lb=weight,net_cap_ft3=q.CapConcreteNetVolume.Value/FT**3))

def clearance_checks(inp):
    """Independent nominal BRep checks. Every measured positive overlap fails."""
    from .geometry import pair,bounds
    q=inp.Document.getObject('Cage'+inp.SupportID+'Quantities');case=live_case(inp);p=case['inputs']
    L=geometry_evaluation(case).value('L_cap')*IN;W=p['b']*IN;H=p['h']*IN;tol=.0254
    shapes=[];covers=[];pile_pairs=[];pair_failures=[];checked=0
    cap=inp.Cap.Shape.copy();cap.Placement=inp.CageFrame.inverse().multiply(cap.Placement)
    piles=[]
    for j in range(4):
        ob=inp.Document.getObject(f'BridgePile{inp.SupportID}P{j+1}');s=ob.Shape.copy()
        s.Placement=inp.CageFrame.inverse().multiply(s.Placement);piles.append((ob.Name,s))
    layout_rows=json.loads(inp.LayoutJSON)
    for rb in q.Bars:
        s=rb.Shape.copy();s.Placement=inp.CageFrame.inverse().multiply(s.Placement);bb=bounds(s)
        margins=[bb.XMin,L-bb.XMax,bb.YMin,W-bb.YMax,bb.ZMin,H-bb.ZMax]
        required=[p['C_s']*IN]*4+[p['C_b']*IN,p['C_t']*IN]
        outside=abs(s.cut(cap.copy()).Volume)
        covers.append(result(rb.Name+'_cap_cover',all(a+tol>=b for a,b in zip(margins,required)) and outside<=1e-7,
            minimum_in=min(margins)/IN,faces_in=[x/IN for x in margins],outside_concrete_in3=outside/IN**3))
        shapes.append((rb.Name,s,bb,layout_rows[rb.Base.BarID]['kind']))
        for pn,ps in piles:
            chk=pair(s.copy(),ps.copy(),p['C_pile']*IN,tol);chk.update(a=rb.Name,b=pn);pile_pairs.append(chk)
    for i,(an,a,ab,ak) in enumerate(shapes):
        for bn,b,bb,bk in shapes[i+1:]:
            checked+=1
            minimum=case['screening']['minimum_clear_in']*IN if ak in ('longitudinal','added') and bk in ('longitudinal','added') else 0.
            lower=math.sqrt(sum(max(0,getattr(ab,ax+'Min')-getattr(bb,ax+'Max'),getattr(bb,ax+'Min')-getattr(ab,ax+'Max'))**2 for ax in 'XYZ'))
            if lower>minimum+tol:continue
            chk=pair(a.copy(),b.copy(),minimum,tol)
            if chk['status']=='FAIL':chk.update(a=an,b=bn);pair_failures.append(chk)
    cover_fails=[r for r in covers if r['status']=='FAIL'];pile_fails=[r for r in pile_pairs if r['status']=='FAIL']
    # Reproduce the selected report's separately identified placement-envelope
    # screen. It is not substituted for the nominal BRep pile check above.
    from pier_cap.end_grid import pile_conflicts
    envelope_conflicts=pile_conflicts(geometry_evaluation(case))
    checks=[result(inp.SupportID+'_all_bar_cover',not cover_fails,failures=cover_fails,checked=len(covers)),
        result(inp.SupportID+'_bar_to_pile_clearance',not pile_fails,failures=pile_fails,checked=len(pile_pairs)),
        result(inp.SupportID+'_all_bar_pairs',not pair_failures,failures=pair_failures,checked=checked,
               policy='2 in minimum between longitudinal/added bars; ties and end-grid contact allowed, positive overlap never allowed.'),
        result(inp.SupportID+'_source_end_grid_pile_tolerance_envelope',not envelope_conflicts,conflicts=envelope_conflicts,
         basis='Selected source conservative pile-placement envelope screen; nominal BRep clearance is checked separately.'),
        {'name':inp.SupportID+'_anchorage_and_fabrication','status':'NOT CONFIGURED',
         'basis':'No anchorage, structural or fabrication approval.'}]
    return dict(checks=checks,cover=covers,pile_pairs=pile_pairs,bar_pair_failures=pair_failures,checked_bar_pairs=checked)

def add(job):
    from .api import document,check_gui,atomic,compact
    doc=document(job['document']);check_gui(doc);rid=job['request_id'];report=ROOT/'reports/transactions'/(rid+'.json')
    if report.exists():raise ValueError('Inspect existing cage transaction before retry')
    if any(doc.getObject('Cage'+s) for s in ('EB1','Pier','EB2')):raise ValueError('Cages already present')
    before=bridge.source_state(doc,[o.Name for o in doc.Objects]);names=set(before)
    native_shapes={o.Name:o.Shape for o in doc.Objects if 'Shape' in o.PropertiesList}
    rec=dict(operation='add_current_source_cap_cages',transaction_id=rid,document=doc.Name,request=job,report_path=str(report),status='PREPARED',model_saved=False,checks=[],errors=[],rollback='NOT NEEDED')
    atomic(report,rec);doc.openTransaction(rid)
    try:
        inputs=[build(doc,s,job['cases']['pier' if s=='Pier' else 'end_bents']) for s in ('EB1','Pier','EB2')]
        for o in doc.Objects:
            if o.Name in names:o.purgeTouched()
        doc.recompute([o for o in doc.Objects if o.Name not in names]);doc.recompute([o for o in doc.Objects if o.Name not in names])
        doc.recompute([doc.BridgeAssembly])
        rec['cages']={i.SupportID:geometry_checks(i) for i in inputs}
        for qa in rec['cages'].values():rec['checks']+=qa['checks']
        # Group membership is the only authorized change to existing objects.
        protected=[n for n in names if n!='BridgeAssembly']
        after=bridge.source_state(doc,protected)
        rec['preservation_differences']={n:{k:[v,after[n][k]] for k,v in before[n].items() if v!=after[n][k]} for n in protected if before[n]!=after[n]}
        rec['checks'].append(result('existing_model_geometry_and_controls_preserved',not rec['preservation_differences']))
        pending=[o.Name for o in doc.Objects if 'Touched' in o.State or 'Invalid' in o.State]
        rec['checks'].append(result('no_pending_or_invalid_objects',not pending,objects=pending))
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Cage generation or quantity validation failed')
        if job.get('test_failure'):raise ValueError('Deliberate cage rollback test')
        attach_review_and_schedules(doc)
        rec['detailing']={sid:doc.getObject('Cage'+sid+'Checks').Proxy.last['detailing'] for sid in ('EB1','Pier','EB2')}
        for qa in rec['detailing'].values():rec['checks']+=qa['checks']
        for sid in ('EB1','Pier','EB2'):
            sh=doc.getObject('Cage'+sid+'Schedule');q=doc.getObject('Cage'+sid+'Quantities');row=str(sh.TotalRow)
            rec['checks'].append(result(sid+'_live_schedule_totals',float(sh.get('D'+row))==q.TotalBars and abs(float(sh.get('G'+row))-q.TotalSteelLength.Value/FT)<=1e-7 and abs(float(sh.get('H'+row))-q.NominalSteelWeightLb)<=1e-7))
        for o in doc.Objects:
            if o.TypeId=='App::DocumentObjectGroup':o.purgeTouched()
        rec['status']='VALIDATED';atomic(report,rec);doc.commitTransaction();rec['status']='BUILT - CLEARANCE REVIEW REQUIRED'
    except Exception as exc:
        rec.update(status='FAIL',errors=[str(exc)],traceback=traceback.format_exc());doc.abortTransaction()
        for n in set(o.Name for o in doc.Objects)-names:doc.removeObject(n)
        for n,shape in native_shapes.items():
            if doc.getObject(n).Shape.exportBrepToString()!=shape.exportBrepToString():doc.getObject(n).Shape=shape
        for o in doc.Objects:o.purgeTouched()
        after=bridge.source_state(doc,list(before))
        rec['rollback_differences']={n:{k:[v,after[n][k]] for k,v in before[n].items() if v!=after[n][k]} for n in before if before[n]!=after[n]}
        rec['rollback']='VERIFIED' if after==before else 'FAILED'
    atomic(report,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ('operation','transaction_id','document','status','report_path','rollback')})+'\n')
    out=compact(rec)
    for key in ('cages','detailing'):out.pop(key,None)
    out['checks']=[{k:v for k,v in row.items() if k not in ('failures','details')} for row in out.get('checks',[])]
    return out
