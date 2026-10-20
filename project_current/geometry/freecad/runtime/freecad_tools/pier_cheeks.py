"""Editable solid pier cheek walls with shallow chamfered exterior recesses.

Reuses the adopted Arch rebar paths, quantities and schedule helpers.
Optional straight vertical development uses the verified LRFD calculator;
joint transfer and wall capacity remain separate design checks.
"""
import json,math
import FreeCAD as App
import Part
from . import bridge,cap_cages as cap,design_steel as steel,cheek_hooks as hooks,pedestal_ubars as development
from .mse import Serializable,prop
from .geometry import bounds,length,result,pair

IN=25.4;FT=304.8;TOL=.0254
HOSTS=('BridgeCheekPier1','BridgeCheekPier2')
LIMITS='Continuous centered mat behind a shallow exterior recess. Cap anchorage and structural design NOT CONFIGURED.'
DEVELOPED_LIMITS='Straight vertical development into cap evaluated to AASHTO LRFD 10th ed. 5.10.8.2.1. Joint transfer and wall structural design remain separate checks.'

def dimensions(host):
    cb=bounds(hooks.local(host.Cap.Shape,host.PGL.Frame))
    w,t,h=host.WallWidth.Value,host.Thickness.Value,host.Height.Value
    ow,oh,ob=host.RecessWidth.Value,host.RecessHeight.Value,host.RecessBottom.Value
    depth,ch=host.RecessDepth.Value,host.RecessChamfer.Value
    inset=host.CapEndInset.Value
    if min(w,t,h,ow,oh,ob)<=0 or inset<0 or ow>=w or ob+oh>=h:
        raise ValueError('Wall and recess must leave positive concrete borders')
    if not 0<ch<=depth<t or 2*ch>=min(ow,oh):raise ValueError('Recess depth/chamfer must fit solid wall')
    if w>cb.XLength+TOL or 2*(inset+t)>cb.YLength:
        raise ValueError('Wall footprint does not fit cap')
    x=(cb.XMin+cb.XMax-w)/2
    y=cb.YMin+inset if host.BeamIndex==0 else cb.YMax-inset-t
    z=cb.ZMax
    ox=x+(w-ow)/2+host.RecessOffset.Value
    if not x<ox<ox+ow<x+w:raise ValueError('Recess is outside wall')
    return dict(x=x,y=y,z=z,w=w,t=t,h=h,ox=ox,oz=z+ob,ow=ow,oh=oh,depth=depth,ch=ch)

def recess_volume(d):
    ch=d['ch'];a,b=d['ow'],d['oh']
    return a*b*ch-(a+b)*ch*ch+4*ch**3/3+(d['depth']-ch)*(a-2*ch)*(b-2*ch)

def recess_tool(host,d):
    face=d['y'] if host.BeamIndex==0 else d['y']+d['t']
    sign=1 if host.BeamIndex==0 else -1
    def wire(offset,inset):
        x,z=d['ox']+inset,d['oz']+inset;y=face+sign*offset
        w,h=d['ow']-2*inset,d['oh']-2*inset
        pts=[App.Vector(x,y,z),App.Vector(x+w,y,z),App.Vector(x+w,y,z+h),App.Vector(x,y,z+h)]
        return Part.makePolygon(pts+[pts[0]])
    wires=[wire(0,0),wire(d['ch'],d['ch'])]
    if d['depth']>d['ch']+1e-8:wires.append(wire(d['depth'],d['ch']))
    return Part.makeLoft(wires,True,True)

class WallProxy(Serializable):
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        d=dimensions(obj)
        outer=Part.makeBox(d['w'],d['t'],d['h'],App.Vector(d['x'],d['y'],d['z']))
        void=recess_tool(obj,d)
        obj.Shape=outer.cut(void).removeSplitter();obj.Placement=obj.PGL.Frame
        obj.WallBottomElevation=d['z'];obj.TopElevation=d['z']+d['h'];obj.NetVolume=obj.Shape.Volume

def layout(inp):
    d=dimensions(inp.Host);cv=inp.Cover.Value
    dv=cap.BAR_DIAMETER[inp.VerticalBar]*IN;dh=cap.BAR_DIAMETER[inp.HorizontalBar]*IN
    sign=-1 if inp.Host.BeamIndex==0 else 1
    offset=getattr(inp,'MatOffset',App.Units.Quantity('0 in')).Value
    nv=d['y']+d['t']/2+sign*dh/2+offset;nh=d['y']+d['t']/2-sign*dv/2+offset
    if (d['t']-dv-dh)/2-abs(offset)-d['depth']<cv:raise ValueError('Mat violates recessed face cover')
    xs=steel.stations(d['x']+cv+dv/2,d['x']+d['w']-cv-dv/2,inp.VerticalSpacing.Value)
    zs=steel.stations(d['z']+cv+dh/2,d['z']+d['h']-cv-dh/2,inp.HorizontalSpacing.Value)
    rows={}
    def add(ident,kind,bar,diameter,points,family):
        if App.Vector(*points[0]).distanceToPoint(App.Vector(*points[1]))<=0:raise ValueError('Non-positive bar length')
        rows[ident]=dict(id=ident,kind=kind,bar=bar,diameter=diameter/IN,
                        family=family,points=[tuple(v/IN for v in p) for p in points],segments=[('line',0,1)])
    shifts=json.loads(getattr(inp,'VerticalStationOffsetsJSON','{}'))
    if set(shifts)-{f'MV{i:02}' for i in range(1,len(xs)+1)}:raise ValueError('Unknown vertical station offset')
    xs=[x+length(shifts.get(f'MV{i:02}','0 in')) for i,x in enumerate(xs,1)]
    if min(xs)<d['x']+cv+dv/2-TOL or max(xs)>d['x']+d['w']-cv-dv/2+TOL:raise ValueError('Vertical station outside wall cover')
    if any(b-a<dv+TOL or b-a>inp.VerticalSpacing.Value+TOL for a,b in zip(xs,xs[1:])):raise ValueError('Vertical stations violate spacing')
    for i,x in enumerate(xs,1):
        lo,hi=d['z']+cv+dv/2,d['z']+d['h']-cv-dv/2
        add(f'MV{i:02}','wall_vertical',inp.VerticalBar,dv,[(x,nv,lo),(x,nv,hi)],'Continuous centered vertical')
    for i,z in enumerate(zs,1):
        lo,hi=d['x']+cv+dh/2,d['x']+d['w']-cv-dh/2
        add(f'MH{i:02}','wall_horizontal',inp.HorizontalBar,dh,[(lo,nh,z),(hi,nh,z)],'Continuous centered horizontal')
    if getattr(inp,'DevelopIntoCap',False):
        calc=development_info(inp,rows)
        for ident,detail in calc['by_bar'].items():
            row=rows[ident];row['points'][0]=(row['points'][0][0],row['points'][0][1],d['z']/IN-detail['provided_in'])
            row.update(required_development_in=detail['required_in'],provided_embedment_in=detail['provided_in'])
    return rows

def development_info(inp,rows):
    cb=bounds(hooks.local(inp.Cap.Shape,inp.PGL.Frame));rows={k:r for k,r in rows.items() if r['kind']=='wall_vertical'}
    if len(rows)<2:raise ValueError('Development requires measured vertical spacing')
    increment=inp.EmbedmentIncrement.Value/IN
    if increment<=0:raise ValueError('Embedment increment must be positive')
    details={}
    for ident,row in rows.items():
        x,y,_=row['points'][0];db=row['diameter'];rad=db/2
        side=min(x-cb.XMin/IN,cb.XMax/IN-x,y-cb.YMin/IN,cb.YMax/IN-y)
        if side-rad+TOL/IN<inp.CapCover.Value/IN:raise ValueError('Developed bar violates cap side cover: '+ident)
        gap=min(math.hypot(x-r['points'][0][0],y-r['points'][0][1]) for k,r in rows.items() if k!=ident)
        calc=development.development(db,inp.YieldStrength.getValueAs('ksi').Value,inp.ConcreteStrength.getValueAs('ksi').Value,min(side,gap/2),inp.DensityFactor,inp.Coating)
        provided=math.ceil((calc['required_in']-1e-10)/increment)*increment
        if cb.ZLength/IN-provided+TOL/IN<inp.CapCover.Value/IN:raise ValueError('Development does not fit cap bottom cover')
        calc.update(provided_in=provided,minimum_side_center_cover_in=side,nearest_developed_bar_centers_in=gap)
        details[ident]=calc
    return dict(by_bar=details,required_in=max(v['required_in'] for v in details.values()),provided_in=max(v['provided_in'] for v in details.values()),basis=DEVELOPED_LIMITS)

def configure_development(doc,source,settings,source_hash):
    """Opt in on existing native walls; no document save or hidden cage edits."""
    for name in HOSTS:
        host=doc.getObject(name);inp=doc.getObject('Steel'+name+'Inputs');cfg=settings[name]
        for typ,key,value in [
          ('App::PropertyBool','DevelopIntoCap',True),('App::PropertyLength','CapCover',str(source['inputs']['C_s'])+' in'),
          ('App::PropertyDistance','MatOffset',cfg['mat_offset']),('App::PropertyString','VerticalStationOffsetsJSON',json.dumps(cfg['vertical_offsets'])),
          ('App::PropertyLength','EmbedmentIncrement','1 in'),('App::PropertyPressure','ConcreteStrength',str(source['inputs']['fc'])+' ksi'),
          ('App::PropertyPressure','YieldStrength',str(source['inputs']['fy'])+' ksi'),('App::PropertyFloat','DensityFactor',source['lrfd_checks']['density_factor']),
          ('App::PropertyString','Coating',source['lrfd_checks']['coating']),('App::PropertyString','DevelopmentJSON','{}'),
          ('App::PropertyLength','RequiredDevelopment','0 in'),('App::PropertyLength','ProvidedEmbedment','0 in'),
          ('App::PropertyString','DevelopmentSourceSHA256',source_hash),('App::PropertyString','VerticalMark','4E1'),('App::PropertyString','HorizontalMark','4E2')]:prop(inp,typ,key,value,'Cap development')
        inp.ScheduleNote=DEVELOPED_LIMITS;inp.Limitations=DEVELOPED_LIMITS
        inp.MatConfiguration='One tangent #4 mat, maximum 10 in spacing. Editable offset clears cap steel. Verticals are straight and developed below the cap top.'
        host.DetailingStatus=DEVELOPED_LIMITS
    refresh(doc,rebuild_hosts=False)

class InputsProxy(Serializable):
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        obj.CageFrame=obj.PGL.Frame;rows=layout(obj);obj.LayoutJSON=json.dumps(rows)
        if getattr(obj,'DevelopIntoCap',False):
            calc=development_info(obj,rows);obj.DevelopmentJSON=json.dumps(calc)
            obj.RequiredDevelopment=str(calc['required_in'])+' in';obj.ProvidedEmbedment=str(calc['provided_in'])+' in'
        if obj.AutoSync:
            q=obj.Document.getObject(obj.Prefix+'Quantities')
            # Existing bars already depend on these analytic rows. Re-link only
            # when the set changes; reassigning duplicate labels renumbers them.
            if q is None or [b.Name for b in q.Bars]!=[obj.Prefix+k for k in rows]:steel.sync_wall(obj)

def refresh(doc,rebuild_hosts=True):
    for name in HOSTS:
        host=doc.getObject(name)
        if rebuild_hosts:host.Proxy.execute(host)
        else:host.purgeTouched()
        inp=doc.getObject('Steel'+name+'Inputs')
        hooks.refresh(inp)
        q=doc.getObject(inp.Prefix+'Quantities')
        # Preserve adopted marks across regeneration; configured mats use SDM marks.
        for rb in q.Bars:
            if 'VerticalMark' in inp.PropertiesList:rb.Mark=inp.VerticalMark if rb.Base.BarID.startswith('MV') else inp.HorizontalMark
        steel.write_wall_schedule(inp,doc.getObject(inp.Prefix+'Schedule'),q.Bars)
        if getattr(inp,'DevelopIntoCap',False):
            sh=doc.getObject(inp.Prefix+'Schedule')
            sh.set('I1','Ld required (in)');sh.set('J1','Cap embed (in)')
            for i,rb in enumerate(q.Bars,2):
                if rb.Base.BarID.startswith('MV'):
                    sh.set('I'+str(i),'='+inp.Name+'.RequiredDevelopment/(1 in)');sh.set('J'+str(i),'='+inp.Name+'.ProvidedEmbedment/(1 in)')
    for obj in doc.Objects:obj.purgeTouched()
    schedules=[doc.getObject('Steel'+n+'Schedule') for n in HOSTS]
    for sh in schedules:sh.touch()
    doc.recompute(schedules)

def create(doc,settings):
    if any(doc.getObject(n) for n in HOSTS) or doc.getObject('PierCheekWalls'):
        raise ValueError('Pier cheeks already exist; inspect instead of repeating creation')
    for k in ['thickness','width','height','inset','recess_width','recess_height','recess_bottom','recess_depth','recess_chamfer']:
        length(settings[k],positive=True)
    group=doc.addObject('App::DocumentObjectGroup','PierCheekWalls');group.Label='Pier cheek walls - solid recessed panels'
    # A new root group avoids changing existing native assembly memberships.
    for side,name in enumerate(HOSTS):
        host=doc.addObject('Part::FeaturePython',name);host.Label='Pier cheek '+('left' if side==0 else 'right')+' - solid with recessed panel';group.addObject(host)
        for typ,k,v in [
          ('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyLink','Cap',doc.BridgeCapPier),
          ('App::PropertyString','ComponentKind','Cheek'),('App::PropertyString','SupportID','Pier'),('App::PropertyInteger','BeamIndex',side),
          ('App::PropertyLength','Thickness',settings['thickness']),('App::PropertyLength','WallWidth',settings['width']),
          ('App::PropertyLength','Height',settings['height']),('App::PropertyLength','CapEndInset',settings['inset']),
          ('App::PropertyLength','RecessWidth',settings['recess_width']),('App::PropertyLength','RecessHeight',settings['recess_height']),
          ('App::PropertyLength','RecessBottom',settings['recess_bottom']),('App::PropertyLength','RecessOffset','0 in'),
          ('App::PropertyLength','RecessDepth',settings['recess_depth']),('App::PropertyLength','RecessChamfer',settings['recess_chamfer']),
          ('App::PropertyLength','WallBottomElevation','0 in'),('App::PropertyLength','TopElevation','0 in'),
          ('App::PropertyVolume','NetVolume',0.),('App::PropertyString','SourceDetail',settings['source_detail']),
          ('App::PropertyString','RecessBasis','Solid wall. Centered 30 x 30 in exterior panel, 3/4 in recess with 3/4 x 3/4 in perimeter chamfer. Opposite face remains flat.'),
          ('App::PropertyString','DetailingStatus',LIMITS)]:prop(host,typ,k,v,'Pier cheek')
        WallProxy(host);host.Proxy.execute(host)
        source=dict(vertical_bar=4,horizontal_bar=4,vertical_spacing='10 in',horizontal_spacing='10 in',
                    cheek_cover='2 in',schematic_embedment='0 in',source_report='Adopted end-bent cheek mat; current user instruction',
                    source_sha256=settings['reference_sha256'],basis=LIMITS)
        inp=steel.build_wall(doc,host,source)
        prop(inp,'App::PropertyLink','ReferenceMat',doc.SteelBridgeCheekEB11Inputs,'Source')
        prop(inp,'App::PropertyString','ScheduleNote',LIMITS,'Review')
        prop(inp,'App::PropertyString','MatConfiguration','One centered continuous mat. Tangent directions; maximum 10 in spacing. Bars continue behind the shallow recess.','Review')
        InputsProxy(inp)
    refresh(doc)
    return [doc.getObject(n) for n in HOSTS]

def validate(doc):
    checks=[];measurements=[];allsteel=hooks.steel_objects(doc);pairs=[];seen=set()
    frame=doc.BridgePGL.Frame
    steelcache=[]
    for obj in allsteel:
        s=hooks.local(obj.Shape,frame);steelcache.append((obj.Name,s,s.BoundBox))
    concretecache=[]
    for obj in doc.Objects:
        if 'Shape' not in obj.PropertiesList or 'ComponentKind' not in obj.PropertiesList:continue
        if obj.ComponentKind not in ['Cap','Pedestal','Beam','Deck','Haunch','Pad','Backwall','Cheek','Wall']:continue
        if obj.Shape.isNull():continue
        s=hooks.local(obj.Shape,frame);concretecache.append((obj.Name,s,s.BoundBox))
    print('VALIDATION CACHE READY',len(steelcache),'bars',flush=True)
    for name in HOSTS:
        host=doc.getObject(name);d=dimensions(host);shape=hooks.local(host.Shape,host.PGL.Frame)
        bb=bounds(shape);inp=doc.getObject('Steel'+name+'Inputs');q=doc.getObject(inp.Prefix+'Quantities')
        expected=d['w']*d['h']*d['t']-recess_volume(d)
        checks.append(result(name+'_valid_solid',shape.isValid() and len(shape.Solids)==1))
        checks.append(result(name+'_outline_and_volume',max(abs(bb.XLength-d['w']),abs(bb.YLength-d['t']),abs(bb.ZLength-d['h']))<TOL and abs(shape.Volume-expected)<1e-5,volume_ft3=shape.Volume/FT**3))
        cx,cz=d['ox']+d['ow']/2,d['oz']+d['oh']/2
        line=Part.makeLine(App.Vector(cx,d['y']-IN,cz),App.Vector(cx,d['y']+d['t']+IN,cz))
        ys=sorted(v.Point.y for v in shape.section(line).Vertexes)
        checks.append(result(name+'_solid_panel_thickness',len(ys)==2 and abs(ys[-1]-ys[0]-(d['t']-d['depth']))<TOL,remaining_in=(ys[-1]-ys[0])/IN if len(ys)==2 else None))
        fy=d['y']+d['depth'] if host.BeamIndex==0 else d['y']+d['t']-d['depth']
        floors=[f for f in shape.Faces if all(abs(v.Point.y-fy)<TOL for v in f.Vertexes)]
        checks.append(result(name+'_recess_floor',len(floors)==1 and abs(bounds(floors[0]).XLength-(d['ow']-2*d['ch']))<TOL and abs(bounds(floors[0]).ZLength-(d['oh']-2*d['ch']))<TOL))
        chamfers=[f for f in shape.Faces if abs(abs(f.normalAt(0,0).y)-1/math.sqrt(2))<1e-8]
        checks.append(result(name+'_four_45_degree_chamfers',len(chamfers)==4))
        capshape=hooks.local(host.Cap.Shape,host.PGL.Frame)
        checks.append(result(name+'_sits_on_cap',shape.common(capshape).Volume==0 and shape.distToShape(capshape)[0]<TOL and abs(bb.ZMin-bounds(capshape).ZMax)<TOL))
        # Finished structural concrete only; hidden reference envelopes excluded.
        conflicts=[]
        for othername,other,ob in concretecache:
            if othername==name:continue
            if any(getattr(bb,k+'Min')>getattr(ob,k+'Max')+TOL or getattr(ob,k+'Min')>getattr(bb,k+'Max')+TOL for k in 'XYZ'):continue
            vol=abs(shape.common(other).Volume)
            if vol>0:conflicts.append(dict(other=othername,volume_mm3=vol))
        checks.append(result(name+'_concrete_intersections',not conflicts,conflicts=conflicts))
        checks+=steel.wall_geometry_checks(inp)
        developed=getattr(inp,'DevelopIntoCap',False)
        coverhost=shape.fuse(capshape).removeSplitter() if developed else shape
        calc=development_info(inp,json.loads(inp.LayoutJSON)) if developed else None
        capfaces=[f for f in capshape.Faces if not all(abs(v.Point.z-bounds(capshape).ZMax)<TOL for v in f.Vertexes)]
        covers=[];locals=[];vertical=[];horizontal=[]
        for rb in q.Bars:
            s=hooks.local(rb.Shape,inp.CageFrame);rbb=bounds(s);locals.append(rbb)
            cv=hooks.solid_cover(s,coverhost,minimum=inp.Cover.Value)
            checks.append(dict(cv,name=rb.Name+'_cover'));covers.append(cv['cover_in'])
            if developed and rb.Base.BarID.startswith('MV'):
                embedded=bounds(capshape).ZMax-rbb.ZMin;detail=calc['by_bar'][rb.Base.BarID]
                segment=s.common(capshape);sidecover=min(segment.distToShape(f)[0] for f in capfaces)
                checks.append(result(rb.Name+'_cap_cover',sidecover+TOL>=inp.CapCover.Value,cover_in=sidecover/IN,required_in=inp.CapCover.Value/IN))
                checks.append(result(rb.Name+'_straight_development',embedded+TOL>=detail['required_in']*IN and abs(embedded-detail['provided_in']*IN)<TOL,required_in=detail['required_in'],provided_in=embedded/IN,cb_in=detail['cb_in']))
                checks.append(result(rb.Name+'_crosses_joint',rbb.ZMin<d['z'] and rbb.ZMax>d['z'] and len(rb.Base.Shape.Edges)==1))
            target=vertical if rb.Base.BarID.startswith('MV') else horizontal
            target.append((rbb.XMin+rbb.XMax)/2 if target is vertical else (rbb.ZMin+rbb.ZMax)/2)
            for othername,os,ob in steelcache:
                key=tuple(sorted((rb.Name,othername)))
                if othername==rb.Name or key in seen:continue
                seen.add(key)
                if any(getattr(rbb,k+'Min')>getattr(ob,k+'Max')+IN or getattr(ob,k+'Min')>getattr(rbb,k+'Max')+IN for k in 'XYZ'):continue
                p=pair(s,os,0.,TOL)
                pairs.append(dict(a=rb.Name,b=othername,status=p['status'],failures=[] if p['status']=='PASS' else [p]))
        for direction,values,pitch in [('vertical',vertical,inp.VerticalSpacing.Value),('horizontal',horizontal,inp.HorizontalSpacing.Value)]:
            vals=sorted(set(round(v,7) for v in values));spacing=[b-a for a,b in zip(vals,vals[1:])]
            checks.append(result(name+'_'+direction+'_max_spacing',bool(spacing) and max(spacing)<=pitch+TOL,maximum_in=max(spacing)/IN))
        lo=min(v.YMin for v in locals);hi=max(v.YMax for v in locals)
        offset=getattr(inp,'MatOffset',App.Units.Quantity('0 in')).Value
        checks.append(result(name+'_tangent_mat_position',abs((lo+hi)/2-(d['y']+d['t']/2+offset))<TOL and abs(hi-lo-IN)<TOL,offset_in=offset/IN,face_cover_in=[(lo-d['y'])/IN,(d['y']+d['t']-hi)/IN]))
        sh=doc.getObject(inp.Prefix+'Schedule')
        checks.append(result(name+'_schedule',sh.BarNames==[b.Name for b in q.Bars] and float(sh.get('D'+str(sh.TotalRow)))==q.TotalBars and abs(float(sh.get('G'+str(sh.TotalRow)))-q.TotalSteelLength.Value/FT)<1e-7))
        continuous=True
        for r in json.loads(inp.LayoutJSON).values():
            verticalrow=r['kind']=='wall_vertical';actual=(r['points'][1][2]-r['points'][0][2] if verticalrow else r['points'][1][0]-r['points'][0][0])*IN
            expected=d['h']-inp.Cover.Value-r['diameter']*IN/2+r['provided_embedment_in']*IN if developed and verticalrow else (d['h'] if verticalrow else d['w'])-2*inp.Cover.Value-r['diameter']*IN
            continuous=continuous and len(r['points'])==2 and abs(actual-expected)<TOL
        checks.append(result(name+'_continuous_mat',continuous))
        if developed:
            checks.append(result(name+'_development_metadata',json.loads(inp.DevelopmentJSON)==calc and abs(inp.RequiredDevelopment.Value-calc['required_in']*IN)<TOL and abs(inp.ProvidedEmbedment.Value-calc['provided_in']*IN)<TOL))
            checks.append(result(name+'_development_schedule',all(abs(float(sh.get(('I' if col=='required_in' else 'J')+str(i)))-calc[col])<1e-7 for i,b in enumerate(q.Bars,2) if b.Base.BarID.startswith('MV') for col in ('required_in','provided_in'))))
        measurements.append(dict(wall=name,bars=q.TotalBars,concrete_ft3=shape.Volume/FT**3,steel_length_ft=q.TotalSteelLength.Value/FT,steel_weight_lb=q.NominalSteelWeightLb,minimum_cover_in=min(covers),recess_in=[d['ow']/IN,d['oh']/IN,d['depth']/IN],chamfer_in=d['ch']/IN,remaining_panel_in=(ys[-1]-ys[0])/IN,borders_in=[(d['ox']-d['x'])/IN,(d['oz']-d['z'])/IN],top_elevation_ft=(d['z']+d['h'])/FT))
        print(name,'validated',q.TotalBars,'bars',flush=True)
    clashes=[p for p in pairs if p['status']=='FAIL']
    checks.append(result('new_pier_steel_intersections',not clashes,checked_pairs=len(pairs),clashes=clashes))
    return dict(checks=checks,failures=[c for c in checks if c['status']=='FAIL'],measurements=measurements,limitations=DEVELOPED_LIMITS if all(getattr(doc.getObject('Steel'+n+'Inputs'),'DevelopIntoCap',False) for n in HOSTS) else LIMITS)
