"""Native two-way pedestal U-bars with LRFD 10th-edition straight leg development.

New adapter: file-copy preparation only. Existing shapes and controls are protected.
Dimensions are millimetres internally; inputs require explicit units. No save of
an authoritative/open working model occurs here.
"""
import json,math,hashlib,traceback,shutil
from pathlib import Path
import FreeCAD as App
import Part
from . import bridge,cap_cages as cap,beam,design_steel,native_archive
from .mse import prop,Serializable
from .geometry import length,result,bounds
IN=25.4
FT=304.8
TOL=.0254

def centered(a,b,pitch):
    if b<a or pitch<=0:raise ValueError('Grid does not fit')
    n=int(math.floor((b-a)/pitch+1e-10))+1
    start=(a+b-(n-1)*pitch)/2
    return [start+i*pitch for i in range(n)]

def development(db,fy,fc,cb,density=1.,coating='uncoated'):
    """LRFD 2024 5.10.8.2.1a-c. Vertical legs; no ktr, clamping or excess steel credit."""
    if coating!='uncoated' or not (0<fc<=15 and 0<fy<=75 and .75<=density<=1 and cb>0):
        raise ValueError('Unsupported LRFD material/detail basis')
    basic=.17*db*(fy/(1.97*density*fc**.25))**2
    confinement=max(.3,min(1.,db/cb))
    return dict(basic_in=basic,cb_in=cb,confinement_factor=confinement,
                required_in=max(12.,basic*confinement),location_factor=1.,coating_factor=1.,
                density_factor=density,excess_steel_factor=1.,ktr=0.,beta_t=0.,Fh=0.,
                equation='AASHTO LRFD 10th edition (2024), 5.10.8.2.1a-1/-2 and 5.10.8.2.1c-1/-2')

def layout(inp):
    ped=bridge.local_shape(inp.Host);pb=bounds(ped);cshape=bridge.local_shape(inp.Cap);cb=bounds(cshape)
    d=inp.Diameter.Value;r=d/2;cover=inp.Cover.Value;cc=inp.CapCover.Value;pitch=inp.Spacing.Value
    if abs(d-.5*IN)>1e-9:raise ValueError('This adapter supports #4 only')
    # The end-bent pedestal is flush with one cap edge. Cap cover therefore
    # controls that leg and the crossing bars, even though pedestal cover is 2 in.
    xmin=max(pb.XMin+cover+r,cb.XMin+cc+r)
    xmax=min(pb.XMax-cover-r,cb.XMax-cc-r)
    ymin=pb.YMin+cover+r;ymax=pb.YMax-cover-r
    nx=len(centered(xmin,xmax,pitch))-inp.XGridCountReduction
    if nx<2:raise ValueError('At least two crossing U-bars are required')
    xpos=[(xmin+xmax-(nx-1)*pitch)/2+i*pitch+inp.XGridOffset.Value for i in range(nx)]
    ypos=[y+inp.YGridOffset.Value for y in centered(ymin,ymax,pitch)]
    if min(xpos)<xmin-TOL or max(xpos)>xmax+TOL or min(ypos)<ymin-TOL or max(ypos)>ymax+TOL:
        raise ValueError('Grid phase violates cover')
    xmin+=inp.LongitudinalReturnInset.Value;xmax-=inp.LongitudinalReturnInset.Value
    # Inset transverse returns to separate perpendicular vertical legs at corners.
    # Horizontal grid pitches stay exactly 6 in; this is not a spacing reduction.
    yl=pb.YMin+inp.TransverseReturnCover.Value+r
    yr=pb.YMax-inp.TransverseReturnCover.Value-r
    topfaces=[f for f in ped.Faces if f.normalAt(0,0).z>.9]
    if not topfaces:raise ValueError('Pedestal top faces unavailable')
    ztop=min(v.Point.z for f in topfaces for v in f.Vertexes)-(cover+r)/min(f.normalAt(0,0).z for f in topfaces)
    rad=(inp.InsideBendDiameter.Value+d)/2
    lower=ztop-d-inp.LayerClearance.Value
    if lower-rad<pb.ZMin-TOL:raise ValueError('Lower bend intrudes into cap development region')
    if min(xmax-xmin,yr-yl)<2*rad:raise ValueError('Bends do not fit')
    plans=[]
    for i,y in enumerate(ypos,1):plans.append(dict(id=f'X{i:02}',direction='X',a=xmin,b=xmax,t=y,z=ztop))
    for i,x in enumerate(xpos,1):plans.append(dict(id=f'Y{i:02}',direction='Y',a=yl,b=yr,t=x,z=lower))
    # User-authorized local adjustments: retain end stations / mean grid pitch.
    # Native signed distances keep the location editable without static solids.
    for p in plans:
        station=getattr(inp,p['id']+'StationAdjustment',App.Units.Quantity('0 in')).Value
        span=getattr(inp,p['id']+'SpanAdjustment',App.Units.Quantity('0 in')).Value
        if max(abs(station),abs(span))>IN+TOL:raise ValueError('Local adjustment exceeds the one-inch search envelope')
        p['t']+=station;p['a']+=span;p['b']+=span
    for direction in 'XY':
        positions=[p['t'] for p in plans if p['direction']==direction]
        intervals=[b-a for a,b in zip(positions,positions[1:])]
        if abs(sum(intervals)/len(intervals)-pitch)>TOL or any(abs(v-pitch)>IN+TOL for v in intervals):
            raise ValueError('Adjusted grid must average the specified spacing; individual intervals may vary by at most one inch')
    def point(p,u,z):return (u,p['t'],z) if p['direction']=='X' else (p['t'],u,z)
    legs=[point(p,u,pb.ZMin) for p in plans for u in (p['a'],p['b'])]
    nearest=min(math.hypot(a[0]-b[0],a[1]-b[1]) for i,a in enumerate(legs) for b in legs[i+1:])
    # c_b is conservatively bounded by BOTH pedestal and cap side surfaces and
    # the nearest developed pedestal leg. No cap-tie area or load clamping credit.
    side=min(min(x-pb.XMin,pb.XMax-x,y-pb.YMin,pb.YMax-y,
                 x-cb.XMin,cb.XMax-x,y-cb.YMin,cb.YMax-y) for x,y,z in legs)
    calc=development(d/IN,inp.YieldStrength.getValueAs('ksi').Value,
        inp.ConcreteStrength.getValueAs('ksi').Value,min(side,nearest/2)/IN,inp.DensityFactor,inp.Coating)
    embed=math.ceil((calc['required_in']-1e-10)/inp.EmbedmentIncrement.Value*IN)*inp.EmbedmentIncrement.Value
    calc.update(provided_in=embed/IN,minimum_leg_centers_in=nearest/IN,
                minimum_side_center_cover_in=side/IN,bar_count=len(plans))
    bottom=pb.ZMin-embed
    if bottom<cb.ZMin+cc-TOL:raise ValueError('Required development does not fit cap bottom cover')
    rows={}
    for p in plans:
        a,b,z=p['a'],p['b'],p['z'];q=math.sqrt(.5)
        uz=[(a,bottom),(a,z-rad),(a+rad*(1-q),z-rad*(1-q)),(a+rad,z),
            (b-rad,z),(b-rad*(1-q),z-rad*(1-q)),(b,z-rad),(b,bottom)]
        rows[p['id']]=dict(id=p['id'],kind='pedestal_u',bar=4,diameter=d/IN,
            family=p['direction']+' U-bars @ '+str(round(pitch/IN,6))+' in average',direction=p['direction'],station=p['t']/IN,
            points=[tuple(v/IN for v in point(p,u,h)) for u,h in uz],
            segments=[('line',0,1),('arc',1,2,3),('line',3,4),('arc',4,5,6),('line',6,7)])
    return rows,calc

class InputsProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        rows,calc=layout(o);o.LayoutJSON=json.dumps(rows);o.DevelopmentJSON=json.dumps(calc)
        o.CageFrame=o.PGL.Frame;o.RequiredDevelopment=str(calc['required_in'])+' in'
        o.ProvidedEmbedment=str(calc['provided_in'])+' in'
        if o.AutoSync:sync(o)

class RebarProxy(cap.RebarProxy):
    def onChanged(self,o,name):
        if name=='Host' and getattr(getattr(o,'Host',None),'ComponentKind',None)=='Pedestal':return
        super().onChanged(o,name)

def write_schedule(inp,sh,bars):
    sh.clearAll()
    for col,t in zip('ABCDEFGHIJ',['Mark','Direction','US #','Count','Dia (in)','Length (ft)','Total (ft)','Weight (lb)','Ld req (in)','Cap embed (in)']):sh.set(col+'1',t)
    for row,b in enumerate(bars,2):
        sh.set('A'+str(row),b.Mark);sh.set('B'+str(row),b.Base.Family)
        for col,expr in {'C':b.Base.Name+'.BarNumber','D':b.Name+'.Amount','E':b.Name+'.Diameter/(1 in)','F':b.Name+'.Length/(1 ft)','G':b.Name+'.TotalLength/(1 ft)','H':b.Name+'.NominalWeightLb','I':inp.Name+'.RequiredDevelopment/(1 in)','J':inp.Name+'.ProvidedEmbedment/(1 in)'}.items():sh.set(col+str(row),'='+expr)
    row=len(bars)+2;q=inp.Prefix+'Quantities';sh.set('A'+str(row),'TOTAL')
    for col,expr in [('D',q+'.TotalBars'),('G',q+'.TotalSteelLength/(1 ft)'),('H',q+'.NominalSteelWeightLb')]:sh.set(col+str(row),'='+expr)
    sh.set('A'+str(row+2),'#4 at specified average spacing EW; local shifts avoid clashes. 2 in pedestal cover; 3 in cap cover. Development below cap top.')
    sh.set('A'+str(row+3),'LRFD 10th ed. 5.10.8.2.1. Uncoated Grade 60; normal weight; no tie/clamping/excess-steel credit.')
    sh.BarNames=[b.Name for b in bars];sh.TotalRow=row

def sync(inp):
    doc=inp.Document;prefix=inp.Prefix;rows=json.loads(inp.LayoutJSON)
    q=doc.getObject(prefix+'Quantities');pg=doc.getObject(prefix+'Paths');bg=doc.getObject(prefix+'Bars')
    if q is None:return
    wanted={prefix+k for k in rows}
    for b in list(q.Bars):
        if b.Name not in wanted:
            base=b.Base.Name;doc.removeObject(b.Name);doc.removeObject(base)
    bars=[]
    for ident,row in rows.items():
        name=prefix+ident;rb=doc.getObject(name)
        if rb is None:
            path=doc.addObject('Part::FeaturePython',name+'Path');pg.addObject(path)
            for typ,k,v in [('App::PropertyLink','Inputs',inp),('App::PropertyString','BarID',ident),('App::PropertyLength','Length','0 in'),('App::PropertyLength','NominalDiameter','0.5 in'),('App::PropertyInteger','BarNumber',4),('App::PropertyString','Family',row['family']),('App::PropertyString','QuantityBasis','')]:prop(path,typ,k,v,'Pedestal steel')
            cap.PathProxy(path);path.Proxy.execute(path)
            rb=beam.native_rebar(doc,name,path,path.NominalDiameter.Value,1);RebarProxy(rb)
            prop(rb,'App::PropertyLink','CageInputs',inp,'Source');rb.Host=inp.Host;rb.Mark=inp.Host.Name+'-'+ident;rb.Rounding=0
            prop(rb,'App::PropertyFloat','NominalWeightLb',0.,'Quantity');rb.setExpression('Diameter',path.Name+'.NominalDiameter');bg.addObject(rb)
            if App.GuiUp:path.ViewObject.Visibility=False;rb.ViewObject.ShapeColor=(.15,.65,.35)
        rb.Label=inp.Host.Label+' '+row['family'];bars.append(rb)
    q.Bars=bars
    sh=doc.getObject(prefix+'Schedule')
    if sh and sh.BarNames!=[b.Name for b in bars]:write_schedule(inp,sh,bars)

def build(doc,host,parameters):
    prefix='PedSteel'+host.SupportID+'B'+str(host.BeamIndex+1)
    if doc.getObject(prefix):raise ValueError('Pedestal reinforcement already exists')
    group=doc.addObject('App::DocumentObjectGroup',prefix);group.Label=host.Label+' #4 U-bar grid';doc.PedestalReinforcement.addObject(group)
    for tail in ['Paths','Bars']:group.addObject(doc.addObject('App::DocumentObjectGroup',prefix+tail))
    inp=doc.addObject('App::FeaturePython',prefix+'Inputs');group.addObject(inp);inp.Label=host.Label+' editable reinforcement controls'
    source=json.loads(doc.getObject('Cage'+host.SupportID+'Inputs').SourceCaseJSON)
    fitted=parameters['placements'][inp.Name]
    for k,key in [('XGridOffset','x_grid_offset_in'),('YGridOffset','y_grid_offset_in'),('LongitudinalReturnInset','longitudinal_return_inset_in')]:
        prop(inp,'App::PropertyDistance' if k.endswith('Offset') else 'App::PropertyLength',k,str(fitted[key])+' in','Pedestal steel')
        if abs(getattr(inp,k).Value-fitted[key]*IN)>1e-9:raise ValueError('Signed placement input was not retained: '+k)
    prop(inp,'App::PropertyInteger','XGridCountReduction',fitted['x_grid_count_reduction'],'Pedestal steel')
    for typ,k,v in [('App::PropertyString','Prefix',prefix),('App::PropertyLink','Host',host),('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyLink','Cap',doc.getObject('BridgeCap'+host.SupportID)),('App::PropertyLink','CapInputs',doc.getObject('Cage'+host.SupportID+'Inputs')),('App::PropertyPlacement','CageFrame',doc.BridgePGL.Frame),('App::PropertyString','LayoutJSON','{}'),('App::PropertyString','DevelopmentJSON','{}'),('App::PropertyBool','AutoSync',False),('App::PropertyLength','Diameter','0.5 in'),('App::PropertyLength','Spacing',parameters['spacing']),('App::PropertyLength','Cover',parameters['cover']),('App::PropertyLength','CapCover',parameters['cap_cover']),('App::PropertyLength','InsideBendDiameter',parameters['inside_bend_diameter']),('App::PropertyLength','LayerClearance',parameters['layer_clearance']),('App::PropertyLength','TransverseReturnCover',parameters['transverse_return_cover']),('App::PropertyLength','EmbedmentIncrement',parameters['embedment_increment']),('App::PropertyPressure','ConcreteStrength',str(source['inputs']['fc'])+' ksi'),('App::PropertyPressure','YieldStrength',str(source['inputs']['fy'])+' ksi'),('App::PropertyFloat','DensityFactor',source['lrfd_checks']['density_factor']),('App::PropertyString','Coating',source['lrfd_checks']['coating']),('App::PropertyLength','RequiredDevelopment','0 in'),('App::PropertyLength','ProvidedEmbedment','0 in'),('App::PropertyString','DesignBasis','LRFD 10th ed. 5.10.8.2.1; FDOT 2026 SDG Table 1.4.2-1. Parameters bound to source at creation; rerun checks after edits.')]:prop(inp,typ,k,v,'Pedestal steel')
    inp.TransverseReturnCover=str(fitted['transverse_return_cover_in'])+' in'
    for ident,adjustment in fitted.get('bar_adjustments',{}).items():
        for key,suffix in [('station','StationAdjustment'),('span','SpanAdjustment')]:
            value=adjustment[key];length(value)
            prop(inp,'App::PropertyDistance',ident+suffix,value,'Local clash adjustments')
    InputsProxy(inp);inp.Proxy.execute(inp)
    q=doc.addObject('App::FeaturePython',prefix+'Quantities');group.addObject(q)
    for typ,k,v in [('App::PropertyLinkList','Bars',[]),('App::PropertyInteger','TotalBars',0),('App::PropertyLength','TotalSteelLength','0 in'),('App::PropertyFloat','NominalSteelWeightLb',0.),('App::PropertyVolume','NominalSteelVolume',0.)]:prop(q,typ,k,v,'Live quantities')
    design_steel.WallQuantitiesProxy(q);sync(inp);inp.AutoSync=True
    sh=doc.addObject('Spreadsheet::Sheet',prefix+'Schedule');sh.Label=host.Label+' LIVE U-bar schedule';group.addObject(sh)
    prop(sh,'App::PropertyStringList','BarNames',[]);prop(sh,'App::PropertyInteger','TotalRow',0);write_schedule(inp,sh,q.Bars)
    return inp

def regenerate(inp):
    inp.Proxy.execute(inp);doc=inp.Document;q=doc.getObject(inp.Prefix+'Quantities')
    for rb in q.Bars:
        rb.Base.Proxy.execute(rb.Base);rb.Proxy.execute(rb)
        rb.Base.purgeTouched();rb.purgeTouched()
    q.Proxy.execute(q)
    inp.purgeTouched();q.purgeTouched()
    doc.recompute([doc.getObject(inp.Prefix+'Schedule')])

def validate(inp):
    doc=inp.Document;q=doc.getObject(inp.Prefix+'Quantities');checks=[]
    ped=bridge.local_shape(inp.Host);cp=bridge.local_shape(inp.Cap);pb=bounds(ped);cb=bounds(cp)
    envelope=ped.fuse(cp).removeSplitter();rows=json.loads(inp.LayoutJSON);calc=json.loads(inp.DevelopmentJSON)
    sides=[f for f in ped.Faces if abs(f.normalAt(0,0).z)<.9 and f.normalAt(0,0).z>-.5]
    roof=[f for f in ped.Faces if f.normalAt(0,0).z>.5]
    legs=[];total=0.;cover_results=[];physical_stations={'X':[],'Y':[]}
    for rb in q.Bars:
        local=rb.Shape.copy();local.Placement=inp.CageFrame.inverse().multiply(local.Placement)
        bb=bounds(local);path=rb.Base.Shape;d=rb.Diameter.Value;vol=math.pi*d*d/4*path.Length
        radii=[f.Surface.Radius for f in local.Faces if isinstance(f.Surface,Part.Cylinder)]
        checks.append(result(rb.Name+'_physical_bar',local.isValid() and len(local.Solids)==1 and len(path.Edges)==5 and bool(radii) and all(abs(2*r-d)<TOL for r in radii) and abs(local.Volume-vol)<=max(1e-5,vol*1e-7)))
        row=rows[rb.Base.BarID]
        ends=[]
        for edge in path.Edges:
            pts=[v.Point for v in edge.Vertexes]
            if len(pts)==2 and abs(pts[0].x-pts[1].x)<1e-7 and abs(pts[0].y-pts[1].y)<1e-7:
                ends.append(min(pts,key=lambda p:p.z))
        if len(ends)!=2:raise ValueError('Expected two physical vertical leg edges')
        p0,p7=ends
        direction='X' if abs(p0.y-p7.y)<1e-7 else 'Y'
        physical_stations[direction].append((p0.y if direction=='X' else p0.x)/IN)
        embed=pb.ZMin-bb.ZMin
        checks.append(result(rb.Name+'_physical_embedment',abs(embed-inp.ProvidedEmbedment.Value)<TOL and embed+TOL>=inp.RequiredDevelopment.Value,provided_in=embed/IN))
        # BRep distance to real pedestal sides/roof includes chamfers and slopes.
        pedcover=min(local.distToShape(f)[0] for f in sides+roof)
        capcover=min(bb.XMin-cb.XMin,cb.XMax-bb.XMax,bb.YMin-cb.YMin,cb.YMax-bb.YMax,bb.ZMin-cb.ZMin)
        outside=abs(local.cut(envelope).Volume)
        ok=pedcover+TOL>=inp.Cover.Value and capcover+TOL>=inp.CapCover.Value and outside<=1e-5
        checks.append(result(rb.Name+'_cover_containment',ok,pedestal_cover_in=pedcover/IN,cap_cover_in=capcover/IN,outside_mm3=outside))
        cover_results.append((pedcover/IN,capcover/IN));legs.extend([p0,p7]);total+=path.Length
        checks.append(result(rb.Name+'_editable_links',rb.Host==inp.Host and rb.CageInputs==inp and rb.Base.Inputs==inp and abs(rb.TotalLength.Value-path.Length)<TOL))
    spacing_results={}
    for direction in 'XY':
        stations=sorted(physical_stations[direction])
        intervals=[b-a for a,b in zip(stations,stations[1:])]
        average=sum(intervals)/len(intervals)
        spacing_results[direction]=dict(intervals_in=intervals,average_in=average,minimum_in=min(intervals),maximum_in=max(intervals))
        checks.append(result(inp.Prefix+'_'+direction+'_physical_average_pitch',len(stations)>=2 and abs(average*IN-inp.Spacing.Value)<TOL and all(abs(v*IN-inp.Spacing.Value)<=IN+TOL for v in intervals),**spacing_results[direction]))
    nearest=min(math.hypot(a.x-b.x,a.y-b.y) for i,a in enumerate(legs) for b in legs[i+1:])/IN
    checks.append(result(inp.Prefix+'_development_spacing',abs(nearest-calc['minimum_leg_centers_in'])<TOL/IN))
    checks.append(result(inp.Prefix+'_live_quantity',q.TotalBars==len(rows)==len(q.Bars) and abs(q.TotalSteelLength.Value-total)<TOL))
    sh=doc.getObject(inp.Prefix+'Schedule')
    checks.append(result(inp.Prefix+'_live_schedule',float(sh.get('D'+str(sh.TotalRow)))==q.TotalBars and abs(float(sh.get('G'+str(sh.TotalRow)))-total/FT)<1e-7))
    return dict(checks=checks,calculation=calc,spacing=spacing_results,minimum_pedestal_cover_in=min(v[0] for v in cover_results),minimum_cap_cover_in=min(v[1] for v in cover_results),bars=q.TotalBars,weight_lb=q.NominalSteelWeightLb)

def clash_check(doc,inputs):
    new=[b for inp in inputs for b in doc.getObject(inp.Prefix+'Quantities').Bars]
    old=[o for o in doc.Objects if hasattr(o,'CageInputs') and o not in new]
    piles=[o for o in doc.Objects if getattr(o,'ComponentKind',None)=='Pile']
    shapes={o.Name:o.Shape.copy() for o in new+old+piles}
    boxes={name:bounds(shape) for name,shape in shapes.items()}
    overlaps=[];near=[];tested=0
    def check(a,b,minimum,kind):
        nonlocal tested
        ba=boxes[a.Name];bb=boxes[b.Name]
        gap=max(bb.XMin-ba.XMax,ba.XMin-bb.XMax,bb.YMin-ba.YMax,ba.YMin-bb.YMax,bb.ZMin-ba.ZMax,ba.ZMin-bb.ZMax)
        if gap>minimum+TOL:return
        sa=shapes[a.Name].copy();sb=shapes[b.Name].copy()
        tested+=1;v=abs(sa.common(sb).Volume);dist=sa.distToShape(sb)[0]
        data=dict(a=a.Name,b=b.Name,kind=kind,common_volume_in3=v/IN**3,clearance_in=dist/IN,required_in=minimum/IN)
        if v>0:overlaps.append(data)
        elif dist+TOL<minimum:near.append(data)
    for i,a in enumerate(new):
        for b in new[i+1:]:check(a,b,0.,'pedestal-grid')
        for b in old:check(a,b,0.,'existing-steel')
        for b in piles:check(a,b,IN,'pile')
    return dict(status='FAIL' if overlaps or near else 'PASS',tested_pairs=tested,overlaps=overlaps,clearance_failures=near,
        scope='All new nominal bars against each other, all existing bars and all piles. Pile clearance 1 in. Bar-bar overlap check; general aggregate/concreting clearance NOT CONFIGURED.')

def prepare_file(source,out,parameters,request_id):
    source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    recpath=out/'transaction.json'
    if recpath.exists():raise ValueError('Existing transaction: inspect before retry')
    for k,v in parameters.items():
        if k!='placements':length(v,positive=True)
    sha=native_archive.sha(source);working=out/'Working.FCStd';raw=out/'NativeCandidate.FCStd';candidate=out/'B4 - Pedestal U-bars.FCStd'
    rec=dict(transaction_id=request_id,status='PREPARED',source=str(source),source_sha256=sha,parameters=parameters)
    def journal():recpath.write_text(json.dumps(rec,indent=2,default=float)+'\n')
    journal();shutil.copy2(source,working);doc=App.openDocument(str(working))
    try:
        before=bridge.source_state(doc,[o.Name for o in doc.Objects]);rec['before_state']=before
        group=doc.addObject('App::DocumentObjectGroup','PedestalReinforcement');group.Label='All pedestals - #4 U-bars at 6 in each way'
        hosts=[doc.getObject('BridgePedestal'+sid+'B'+str(b)) for sid in ['EB1','Pier','EB2'] for b in [1,2]]
        if any(o is None for o in hosts):raise ValueError('Missing pedestal')
        inputs=[]
        for host in hosts:
            inputs.append(build(doc,host,parameters));rec['phase']='built '+host.Name;journal()
        for inp in inputs:
            regenerate(inp);rec['phase']='regenerated '+inp.Name;journal()
        rec['results']={}
        for inp in inputs:
            rec['results'][inp.Host.Name]=validate(inp);rec['phase']='checked '+inp.Name;journal()
        if any(c['status']=='FAIL' for r in rec['results'].values() for c in r['checks']):raise ValueError('Pedestal geometry, cover or quantity check failed')
        # Preserve every prior native object; the new group is top-level so no
        # original group membership, input, geometry, expression or view is edited.
        after=bridge.source_state(doc,list(before))
        if after!=before:raise ValueError('Protected native source state changed')
        rec['clash_check']=clash_check(doc,inputs)
        checkobj=doc.addObject('App::FeaturePython','PedestalSteelChecks');group.addObject(checkobj)
        prop(checkobj,'App::PropertyString','Status',rec['clash_check']['status'])
        prop(checkobj,'App::PropertyString','ReportJSON',json.dumps(rec['clash_check']))
        prop(checkobj,'App::PropertyString','Basis','Dated physical check. Rerun pedestal_ubars.validate and clash_check after edits; not a live acceptance flag.')
        doc.saveAs(str(raw))
        rec['archive']=native_archive.preserve(source,raw,candidate,list(before),sha)
        rec.update(status='CANDIDATE_WITH_CLASHES' if rec['clash_check']['status']=='FAIL' else 'CANDIDATE_READY',candidate=str(candidate),candidate_sha256=native_archive.sha(candidate),original_unchanged=native_archive.sha(source)==sha)
    except Exception:rec.update(status='FAIL',traceback=traceback.format_exc())
    finally:App.closeDocument(doc.Name);journal()
    return rec
