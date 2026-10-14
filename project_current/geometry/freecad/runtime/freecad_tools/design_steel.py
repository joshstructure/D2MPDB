"""2026-10-12 source reconciliation: native cap and wall reinforcement only.

Wall bars reproduce Figure B8's trial steel with explicitly schematic 16-inch
dowels. No anchorage, strap layout or concrete design is inferred.
"""
from pathlib import Path
import json,hashlib,math,re,traceback,io,zipfile
from datetime import datetime,timezone
import FreeCAD as App
import Part
from . import cap_cages as cap,bridge,beam
from .mse import prop,Serializable
from .geometry import length,result,pair,bounds
from .api import atomic,compact,document,check_gui
ROOT=bridge.ROOT;IN=25.4;FT=304.8

def native_properties(obj):
    """Compare native values, never transient Python wrapper addresses."""
    out={}
    for name in obj.PropertiesList:
        if name=='Proxy':continue
        with zipfile.ZipFile(io.BytesIO(obj.dumpPropertyContent(name))) as z:
            out[name]=hashlib.sha256(b''.join(n.encode()+z.read(n) for n in sorted(z.namelist()))).hexdigest()
    return out

def stations(a,b,pitch):
    if b<a or pitch<=0:raise ValueError('Steel does not fit available dimensions')
    count=int(math.floor((b-a)/pitch));out=[a+i*pitch for i in range(count+1)]
    if b-out[-1]>1e-8:out.append(b)
    return out

def wall_layout(inp):
    wall=bridge.local_shape(inp.Host);bb=wall.BoundBox;back=inp.Host.ComponentKind=='Backwall'
    cv=inp.Cover.Value;dv=cap.BAR_DIAMETER[inp.VerticalBar]*IN;dh=cap.BAR_DIAMETER[inp.HorizontalBar]*IN
    along=('YMin','YMax') if back else ('XMin','XMax')
    normal=('XMin','XMax') if back else ('YMin','YMax')
    amin,amax=[getattr(bb,k) for k in along];nmin,nmax=[getattr(bb,k) for k in normal]
    if nmax-nmin<2*(cv+dv+dh):raise ValueError('Two wall steel mats do not fit')
    def point(a,n,z):return (n,a,z) if back else (a,n,z)
    def top(a):
        x,y,_=point(a,(nmin+nmax)/2,0)
        sec=wall.section(Part.makeLine(App.Vector(x,y,bb.ZMin-IN),App.Vector(x,y,bb.ZMax+IN)))
        if not sec.Vertexes:raise ValueError('Cannot measure actual wall top')
        return max(v.Point.z for v in sec.Vertexes)
    vpositions=stations(amin+cv+dv/2,amax-cv-dv/2,inp.VerticalSpacing.Value)
    top_min=min(top(amin+cv+dh/2),top(amax-cv-dh/2))
    hpositions=stations(bb.ZMin+cv+dh/2,top_min-cv-dh/2,inp.HorizontalSpacing.Value)
    rows={}
    for face in (0,1):
        nv=nmin+cv+dv/2 if face==0 else nmax-cv-dv/2
        nh=nmin+cv+dv+dh/2 if face==0 else nmax-cv-dv-dh/2
        for i,a in enumerate(vpositions,1):
            # The retained 2% roof needs true normal cover, not a rounded elevation.
            slope=abs((top(min(a+1,amax))-top(max(a-1,amin)))/(min(a+1,amax)-max(a-1,amin)))
            ztop=top(a)-(cv+dv/2)*math.sqrt(1+slope*slope)
            ident=f'F{face+1}V{i:02}'
            rows[ident]=dict(id=ident,kind='wall_vertical',bar=inp.VerticalBar,diameter=dv/IN,
                family=f'Face {face+1} vertical; schematic dowel',points=[tuple(v/IN for v in point(a,nv,z)) for z in (bb.ZMin-inp.SchematicEmbedment.Value,ztop)],segments=[('line',0,1)])
        for i,z in enumerate(hpositions,1):
            ident=f'F{face+1}H{i:02}'
            rows[ident]=dict(id=ident,kind='wall_horizontal',bar=inp.HorizontalBar,diameter=dh/IN,
                family=f'Face {face+1} horizontal',points=[tuple(v/IN for v in point(a,nh,z)) for a in (amin+cv+dh/2,amax-cv-dh/2)],segments=[('line',0,1)])
    return rows

class WallInputsProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        o.CageFrame=o.PGL.Frame;o.LayoutJSON=json.dumps(wall_layout(o))
        if o.AutoSync:sync_wall(o)

class WallQuantitiesProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        o.TotalBars=sum(len(b.Shape.Solids) for b in o.Bars)
        o.TotalSteelLength=sum(b.TotalLength.Value for b in o.Bars)
        o.NominalSteelWeightLb=sum(b.TotalLength.Value/FT*cap.WEIGHTS[b.Base.BarNumber] for b in o.Bars)
        o.NominalSteelVolume=sum(b.Shape.Volume for b in o.Bars)

class WallRebarProxy(cap.RebarProxy):
    def onChanged(self,o,name):
        # Wall concrete, like the bridge cap, does not consume rebar children.
        # Native Arch's Host touch would unnecessarily rebuild protected concrete.
        if name=='Host' and getattr(getattr(o,'Host',None),'ComponentKind',None) in ['Backwall','Cheek']:return
        super().onChanged(o,name)

def sync_wall(inp):
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
            for typ,k,v in [('App::PropertyLink','Inputs',inp),('App::PropertyString','BarID',ident),('App::PropertyLength','Length','0 in'),('App::PropertyLength','NominalDiameter',str(row['diameter'])+' in'),('App::PropertyInteger','BarNumber',row['bar']),('App::PropertyString','Family',row['family']),('App::PropertyString','QuantityBasis','')]:prop(path,typ,k,v,'Wall steel')
            cap.PathProxy(path);path.Proxy.execute(path)
            rb=beam.native_rebar(doc,name,path,path.NominalDiameter.Value,1);WallRebarProxy(rb)
            prop(rb,'App::PropertyLink','CageInputs',inp,'Source');rb.Host=inp.Host;rb.Mark=inp.Host.Name+'-'+ident;rb.Rounding=0
            prop(rb,'App::PropertyFloat','NominalWeightLb',0.,'Quantity')
            rb.setExpression('Diameter',path.Name+'.NominalDiameter');bg.addObject(rb)
            if App.GuiUp:path.ViewObject.Visibility=False;rb.ViewObject.ShapeColor=(.20,.43,.68)
        rb.Label=inp.Host.Label+' '+row['family']+' #'+str(row['bar']);bars.append(rb)
    q.Bars=bars
    sh=doc.getObject(prefix+'Schedule')
    if sh and sh.BarNames!=[b.Name for b in bars]:write_wall_schedule(inp,sh,bars)

def write_wall_schedule(inp,sh,bars):
    sh.clearAll()
    for col,t in zip('ABCDEFGH',['Mark','Family','US #','Count','Dia (in)','Length (ft)','Total (ft)','Weight (lb)']):sh.set(col+'1',t)
    for r,b in enumerate(bars,2):
        sh.set('A'+str(r),b.Mark);sh.set('B'+str(r),b.Base.Family)
        for col,expr in {'C':b.Base.Name+'.BarNumber','D':b.Name+'.Amount','E':b.Name+'.Diameter/(1 in)','F':b.Name+'.Length/(1 ft)','G':b.Name+'.TotalLength/(1 ft)','H':b.Name+'.NominalWeightLb'}.items():sh.set(col+str(r),'='+expr)
    r=len(bars)+2;q=inp.Prefix+'Quantities';sh.set('A'+str(r),'TOTAL')
    for col,expr in [('D',q+'.TotalBars'),('G',q+'.TotalSteelLength/(1 ft)'),('H',q+'.NominalSteelWeightLb')]:sh.set(col+str(r),'='+expr)
    sh.set('A'+str(r+2),getattr(inp,'ScheduleNote','TRIAL STEEL: 16 in dowels schematic; anchorage, laps and straps not detailed.'))
    sh.BarNames=[b.Name for b in bars];sh.TotalRow=r

def build_wall(doc,host,source):
    prefix='Steel'+host.Name;group=doc.addObject('App::DocumentObjectGroup',prefix);doc.WallReinforcement.addObject(group)
    for tail in ['Paths','Bars']:group.addObject(doc.addObject('App::DocumentObjectGroup',prefix+tail))
    inp=doc.addObject('App::FeaturePython',prefix+'Inputs');group.addObject(inp)
    for typ,k,v in [('App::PropertyString','Prefix',prefix),('App::PropertyLink','Host',host),('App::PropertyLink','PGL',doc.BridgePGL),('App::PropertyLink','Cap',doc.getObject('BridgeCap'+host.SupportID)),('App::PropertyPlacement','CageFrame',doc.BridgePGL.Frame),('App::PropertyString','LayoutJSON','{}'),('App::PropertyBool','AutoSync',False),('App::PropertyInteger','VerticalBar',source['vertical_bar']),('App::PropertyInteger','HorizontalBar',source['horizontal_bar']),('App::PropertyLength','VerticalSpacing',source['vertical_spacing']),('App::PropertyLength','HorizontalSpacing',source['horizontal_spacing']),('App::PropertyLength','Cover',source['backwall_cover' if host.ComponentKind=='Backwall' else 'cheek_cover']),('App::PropertyLength','SchematicEmbedment',source['schematic_embedment']),('App::PropertyString','SourceReport',source['source_report']),('App::PropertyString','SourceSHA256',source['source_sha256']),('App::PropertyString','Limitations',source['basis'])]:prop(inp,typ,k,v,'Wall steel')
    WallInputsProxy(inp);inp.Proxy.execute(inp)
    q=doc.addObject('App::FeaturePython',prefix+'Quantities');group.addObject(q)
    for typ,k,v in [('App::PropertyLinkList','Bars',[]),('App::PropertyInteger','TotalBars',0),('App::PropertyLength','TotalSteelLength','0 in'),('App::PropertyFloat','NominalSteelWeightLb',0.),('App::PropertyVolume','NominalSteelVolume',0.)]:prop(q,typ,k,v,'Live quantities')
    WallQuantitiesProxy(q);sync_wall(inp);inp.AutoSync=True
    sh=doc.addObject('Spreadsheet::Sheet',prefix+'Schedule');group.addObject(sh)
    prop(sh,'App::PropertyStringList','BarNames',[]);prop(sh,'App::PropertyInteger','TotalRow',0);write_wall_schedule(inp,sh,q.Bars)
    return inp

def wall_geometry_checks(inp):
    q=inp.Document.getObject(inp.Prefix+'Quantities');checks=[];rows=json.loads(inp.LayoutJSON);total=0;weight=0
    for b in q.Bars:
        s=b.Shape.copy();d=b.Diameter.Value;L=b.Base.Shape.Length
        radii=[f.Surface.Radius for f in s.Faces if isinstance(f.Surface,Part.Cylinder)]
        vol=math.pi*d*d/4*L
        checks.append(result(b.Name+'_physical_geometry',s.isValid() and len(s.Solids)==1 and bool(radii) and all(abs(2*r-d)<=.0254 for r in radii) and abs(s.Volume-vol)<=max(1e-5,vol*1e-8)))
        samples=[e.valueAt((e.FirstParameter+e.LastParameter)/2) for e in b.Base.Shape.Edges]
        checks.append(result(b.Name+'_links_and_placement',b.Host==inp.Host and b.Base.Inputs==inp and b.CageInputs==inp and abs(b.TotalLength.Value-L)<=.0254 and all(s.isInside(inp.CageFrame.multVec(p),.0254,True) for p in samples)))
        total+=L;weight+=L/FT*cap.WEIGHTS[b.Base.BarNumber]
    checks.append(result(inp.Prefix+'_live_totals',len(q.Bars)==len(rows)==q.TotalBars and abs(total-q.TotalSteelLength.Value)<.0254 and abs(weight-q.NominalSteelWeightLb)<1e-7))
    return checks

def wall_detail_checks(doc,inputs):
    covers=[];clashes=[];checked=0;allbars=[]
    # Nominal BRep interferences are checked against wall and cap bars together.
    for sid in ['EB1','Pier','EB2']:allbars+=list(doc.getObject('Cage'+sid+'Quantities').Bars)
    newbars=[]
    for inp in inputs:
        local=bridge.local_shape(inp.Host);bb=local.BoundBox;back=inp.Host.ComponentKind=='Backwall';cv=inp.Cover.Value
        host=inp.Host.Shape.copy().fuse(inp.Cap.Shape.copy())
        rows=json.loads(inp.LayoutJSON)
        for b in doc.getObject(inp.Prefix+'Quantities').Bars:
            newbars.append(b);s=b.Shape.copy();outside=abs(s.cut(host.copy()).Volume)
            sl=s.copy();sl.Placement=inp.CageFrame.inverse().multiply(sl.Placement);sb=bounds(sl)
            margins=[sb.XMin-bb.XMin,bb.XMax-sb.XMax,sb.YMin-bb.YMin,bb.YMax-sb.YMax]
            # The top is measured against the actual sloped face independently.
            topfaces=[f for f in local.Faces if f.normalAt(0,0).z>.5]
            topdist=min(sl.distToShape(f)[0] for f in topfaces)
            margins.append(topdist)
            if rows[b.Base.BarID]['kind']=='wall_horizontal':margins.append(sb.ZMin-bb.ZMin)
            covers.append(result(b.Name+'_wall_cover',outside<=1e-7 and min(margins)+.0254>=cv,minimum_in=min(margins)/IN,required_in=cv/IN,outside_in3=outside/IN**3))
    newnames={b.Name for b in newbars};items=[(b.Name,b.Shape.copy(),bounds(b.Shape)) for b in allbars+newbars]
    for i,(an,a,ab) in enumerate(items):
        for bn,b,bb in items[i+1:]:
            if an not in newnames and bn not in newnames:continue
            checked+=1
            if any(getattr(ab,k+'Min')>getattr(bb,k+'Max')+.0254 or getattr(bb,k+'Min')>getattr(ab,k+'Max')+.0254 for k in 'XYZ'):continue
            chk=pair(a.copy(),b.copy(),0.,.0254)
            if chk['status']=='FAIL':chk.update(a=an,b=bn);clashes.append(chk)
    fails=[r for r in covers if r['status']=='FAIL']
    return dict(checks=[result('wall_steel_cover',not fails,failures=fails),result('wall_to_wall_and_cap_steel_clashes',not clashes,failures=clashes,checked=checked),dict(name='wall_development_laps_straps_and_fabrication',status='NOT CONFIGURED',basis='Source Figure B8 dowels schematic; no approved detail supplied.')],covers=covers,clashes=clashes)

def update(job):
    doc=document(job['document']);check_gui(doc);rid=job['request_id']
    # This adapter is qualified only for a disposable file-copy workflow. Its
    # live document undo test failed; never use it on an authoritative/open model.
    if job.get('disposable_file_only') is not True or not doc.FileName or not Path(doc.FileName).resolve().is_relative_to((ROOT/'reports').resolve()):
        raise ValueError('Use only an explicitly marked disposable file copy under the project reports folder; live undo is not qualified')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    path=ROOT/'reports/transactions'/(rid+'.json')
    if path.exists():raise ValueError('Inspect recorded transaction before retry')
    length(job['tolerance'],positive=True)
    if length(job['tolerance'])!=.0254:raise ValueError('Use the fixed 0.001 in comparison tolerance')
    if doc.getObject('WallReinforcement'):raise ValueError('Wall steel exists; use a separately tested later revision')
    for k in ['vertical_spacing','horizontal_spacing','backwall_cover','cheek_cover','schematic_embedment']:length(job['walls'][k],positive=True)
    cases={}
    for sid,src in job['cases'].items():
        raw=Path(src['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=src['sha256']:raise ValueError('Source case changed')
        cases[sid]=(raw,json.loads(raw))
        inp=doc.getObject('Cage'+sid+'Inputs');old=cap.live_case(inp)
        for k in ['b','h','D_pile','S_pile','Pile_embed']:
            scale=FT if k=='S_pile' else IN
            if abs(cases[sid][1]['inputs'][k]-old['inputs'][k])*scale>.0254:raise ValueError('Source requests prohibited concrete change: '+sid+' '+k)
    before=bridge.source_state(doc,[o.Name for o in doc.Objects]);oldproxies={o.Name:o.Proxy for o in doc.Objects if 'Proxy' in o.PropertiesList}
    native_shapes={o.Name:o.dumpPropertyContent('Shape') for o in doc.Objects if 'Shape' in o.PropertiesList}
    old_layouts={s:json.loads(doc.getObject('Cage'+s+'Inputs').LayoutJSON) for s in cases}
    pgl_before=native_properties(doc.BridgePGL)
    protected=[n for n in before if not n.startswith('Cage') and n!='BridgeAssembly']
    mesh_before={o.Name:hashlib.sha256(str((o.Mesh.Topology,o.Placement)).encode()).hexdigest() for o in doc.Objects if 'Mesh' in o.PropertiesList}
    rec=dict(operation=job['operation'],document=doc.Name,request=job,transaction_id=rid,timestamp=datetime.now(timezone.utc).isoformat(),report_path=str(path),status='PREPARED',model_saved=False,checks=[],errors=[],rollback='NOT NEEDED',warnings=[job['walls']['basis']])
    atomic(path,rec);doc.openTransaction(rid)
    try:
        rec['old_cages']={s:cap.geometry_checks(doc.getObject('Cage'+s+'Inputs'))['totals'] for s in cases}
        for sid,(raw,case) in cases.items():
            inp=doc.getObject('Cage'+sid+'Inputs');inp.AutoSync=False
            inp.SourceCaseJSON=raw.decode('utf-8');inp.SourceSHA256=job['cases'][sid]['sha256'];inp.SourcePath=job['cases'][sid]['case_relative']
            for k in cap.PARAMS:setattr(inp,k,int(case['inputs'][k]) if k.startswith(('Bar_','n_')) else str(case['inputs'][k])+' in')
            inp.TransverseRunsJSON=json.dumps(case['transverse_detail']);inp.EndGridJSON=json.dumps(case['end_face_grid']);inp.AddedBarsJSON=json.dumps(case['added_bar_layout'])
            inp.AutoSync=True;inp.Proxy.execute(inp)
        group=doc.addObject('App::DocumentObjectGroup','WallReinforcement');group.Label='Backwall and cheek-wall trial reinforcement';doc.BridgeAssembly.addObject(group)
        inputs=[build_wall(doc,o,job['walls']) for o in doc.BridgeGeometryChecks.Components if o.ComponentKind in ['Backwall','Cheek']]
        # Recompute steel and schedules only. Preserve untouched native BReps.
        for o in doc.Objects:
            if o.Name in before and not o.Name.startswith('Cage'):o.purgeTouched()
        affected=[o for o in doc.Objects if o.Name.startswith(('Cage','SteelBridge'))]
        for _ in range(2):doc.recompute(affected)
        # Retain exact native geometry for bars whose analytic source rows did
        # not change. Restoring the native property also retains OCCT cache flags;
        # proxies, expressions and links stay editable. Changed rows are excluded.
        stable=[]
        for sid in cases:
            inp=doc.getObject('Cage'+sid+'Inputs');new_layout=json.loads(inp.LayoutJSON)
            for bar in doc.getObject('Cage'+sid+'Quantities').Bars:
                ident=bar.Base.BarID
                if old_layouts[sid].get(ident)==new_layout.get(ident):
                    for obj in [bar.Base,bar]:
                        obj.restorePropertyContent('Shape',native_shapes[obj.Name]);obj.purgeTouched();stable.append(obj.Name)
        rec['retained_unchanged_native_shapes']=stable
        rec['cages']={s:cap.geometry_checks(doc.getObject('Cage'+s+'Inputs')) for s in cases}
        for data in rec['cages'].values():rec['checks']+=data['checks']
        for inp in inputs:rec['checks']+=wall_geometry_checks(inp)
        for prefix in ['Cage'+s for s in cases]+[i.Prefix for i in inputs]:
            q=doc.getObject(prefix+'Quantities');sh=doc.getObject(prefix+'Schedule');r=str(sh.TotalRow)
            rec['checks'].append(result(prefix+'_schedule_link',float(sh.get('D'+r))==q.TotalBars and abs(float(sh.get('G'+r))-q.TotalSteelLength.Value/FT)<1e-7 and abs(float(sh.get('H'+r))-q.NominalSteelWeightLb)<1e-7))
        after=bridge.source_state(doc,protected)
        rec['preservation_differences']=[n for n in protected if after[n]!=before[n]]
        rec['checks'].append(result('existing_concrete_ramps_placements_links_preserved',not rec['preservation_differences']))
        pgl_after=native_properties(doc.BridgePGL)
        rec['pgl_differences']={k:[v,pgl_after[k]] for k,v in pgl_before.items() if v!=pgl_after[k]}
        rec['checks'].append(result('all_bridge_controls_preserved',not rec['pgl_differences']))
        rec['checks'].append(result('terrain_meshes_preserved',mesh_before=={o.Name:hashlib.sha256(str((o.Mesh.Topology,o.Placement)).encode()).hexdigest() for o in doc.Objects if 'Mesh' in o.PropertiesList}))
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Geometry, quantity or preservation validation failed')
        if job.get('test_failure'):raise ValueError('Deliberate source-update rollback test')
        rec['detailing']={s:json.loads(doc.getObject('Cage'+s+'Checks').ReportJSON)['detailing'] for s in cases}
        for detail in rec['detailing'].values():rec['checks']+=detail['checks']
        rec['wall_detailing']=wall_detail_checks(doc,inputs);rec['checks']+=rec['wall_detailing']['checks']
        check=doc.addObject('App::FeaturePython','WallSteelChecks');group.addObject(check)
        for typ,k,v in [('App::PropertyString','Status','FAIL' if any(c['status']=='FAIL' for c in rec['wall_detailing']['checks']) else 'PASS'),('App::PropertyString','ReportJSON',json.dumps(rec['wall_detailing'])),('App::PropertyLinkList','Inputs',inputs)]:prop(check,typ,k,v,'Validation snapshot')
        prop(check,'App::PropertyString','SnapshotBasis','Dated update check; rerun design_steel.wall_detail_checks after any subsequent wall steel edit.','Validation snapshot')
        rec['walls']={i.Host.Name:dict(bars=doc.getObject(i.Prefix+'Quantities').TotalBars,length_ft=doc.getObject(i.Prefix+'Quantities').TotalSteelLength.Value/FT,weight_lb=doc.getObject(i.Prefix+'Quantities').NominalSteelWeightLb) for i in inputs}
        for o in doc.Objects:
            if o.TypeId=='App::DocumentObjectGroup':o.purgeTouched()
        invalid=[o.Name for o in doc.Objects if 'Invalid' in o.State]
        rec['checks'].append(result('no_invalid_objects',not invalid,objects=invalid))
        if invalid:raise ValueError('Invalid native object after update')
        rec['status']='VALIDATED';atomic(path,rec);doc.commitTransaction();rec['status']='UPDATED - DETAILING REVIEW REQUIRED'
    except Exception as exc:
        rec.update(status='FAIL',errors=[str(exc)],traceback=traceback.format_exc());doc.abortTransaction()
        for n in set(o.Name for o in doc.Objects)-set(before):doc.removeObject(n)
        for n,p in oldproxies.items():
            if doc.getObject(n):doc.getObject(n).Proxy=p
        for n,raw in native_shapes.items():doc.getObject(n).restorePropertyContent('Shape',raw)
        for o in doc.Objects:o.purgeTouched()
        restored=bridge.source_state(doc,list(before))
        rec['rollback_differences']={n:{k:[v,restored[n][k]] for k,v in before[n].items() if v!=restored[n][k]} for n in before if before[n]!=restored[n]};rec['rollback']='VERIFIED' if restored==before else 'FAILED'
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','document','status','report_path','rollback']})+'\n')
    return {k:rec.get(k) for k in ['status','transaction_id','report_path','errors','rollback','walls','preservation_differences']}
