"""Single centered cheek-wall mat; native paths, Arch bars and live schedules.

The two directions are tangent and symmetric about the web center plane.
The main web limits exclude the bottom and rear concrete lugs. Anchorage and
lug reinforcement are outside this explicitly requested mat revision.
"""
import json, hashlib, traceback
from pathlib import Path
from datetime import datetime, timezone
import FreeCAD as App
import Part
from . import bridge, cap_cages as cap, design_steel as steel
from .mse import Serializable, prop
from .geometry import length, bounds, result

IN=25.4; FT=304.8; TOL=.0254
HOSTS=('BridgeCheekEB11','BridgeCheekEB12','BridgeCheekEB21','BridgeCheekEB22')
BASIS='User revision 2026-10-14: single centered mat, #4 each way. Existing 12 in spacing and 2 in end cover retained. No schematic dowel tails; anchorage and lug reinforcement not detailed.'

def web_limits(inp):
    wb=bounds(bridge.local_shape(inp.Host)); cb=bounds(bridge.local_shape(inp.Cap))
    return cb.XMin,cb.XMax,wb.YMin,wb.YMax,inp.Host.WallBottomElevation.Value,inp.Host.TopElevation.Value

def layout(inp):
    if inp.Host.ComponentKind!='Cheek':raise ValueError('Cheek walls only')
    a,b,n0,n1,z0,z1=web_limits(inp); cv=inp.Cover.Value
    dv=cap.BAR_DIAMETER[inp.VerticalBar]*IN; dh=cap.BAR_DIAMETER[inp.HorizontalBar]*IN
    if cv<=0 or n1-n0<=dv+dh:raise ValueError('Mat does not fit cheek web')
    # Outer vertical / inner horizontal: entire combined mat envelope centered.
    sign=-1 if inp.Host.BeamIndex==0 else 1; mid=(n0+n1)/2
    nv=mid+sign*dh/2; nh=mid-sign*dv/2
    rows={}
    positions=[(f'MV{k:02}',x) for k,x in enumerate(steel.stations(a+cv+dv/2,b-cv-dv/2,inp.VerticalSpacing.Value),1)]
    if getattr(inp,'VerticalStationsJSON',''):
        requested=json.loads(inp.VerticalStationsJSON)
        positions=[(r['id'],a+length(r['offset'])) for r in requested]
        if not positions or len({ident for ident,x in positions})!=len(positions):raise ValueError('Unique vertical bar identities required')
        if any(not ident.startswith('MV') or not ident[2:].isdigit() or x<a+cv+dv/2-TOL or x>b-cv-dv/2+TOL for ident,x in positions):raise ValueError('Vertical station outside covered web')
        if any(v-u<dv-TOL for u,v in zip(sorted(x for _,x in positions),sorted(x for _,x in positions)[1:])):raise ValueError('Vertical bars overlap')
    for ident,x in positions:
        rows[ident]=dict(id=ident,kind='wall_vertical',bar=inp.VerticalBar,diameter=dv/IN,family='Single centered mat vertical',points=[(x/IN,nv/IN,z/IN) for z in (z0+cv+dv/2,z1-cv-dv/2)],segments=[('line',0,1)])
    for k,z in enumerate(steel.stations(z0+cv+dh/2,z1-cv-dh/2,inp.HorizontalSpacing.Value),1):
        ident=f'MH{k:02}'
        rows[ident]=dict(id=ident,kind='wall_horizontal',bar=inp.HorizontalBar,diameter=dh/IN,family='Single centered mat horizontal',points=[(x/IN,nh/IN,z/IN) for x in (a+cv+dh/2,b-cv-dh/2)],segments=[('line',0,1)])
    overrides=json.loads(getattr(inp,'HorizontalStationOverridesJSON','') or '{}')
    for ident,offset in overrides.items():
        if ident not in rows or not ident.startswith('MH'):raise ValueError('Existing horizontal bar identity required')
        z=z0+length(offset)
        if z<z0+cv+dh/2-TOL or z>z1-cv-dh/2+TOL:raise ValueError('Horizontal station outside covered web')
        rows[ident]['points']=[(x,y,z/IN) for x,y,_ in rows[ident]['points']]
    return rows

class InputsProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        o.CageFrame=o.PGL.Frame; o.LayoutJSON=json.dumps(layout(o))
        if o.AutoSync:steel.sync_wall(o)

def refresh(inp):
    inp.Proxy.execute(inp); doc=inp.Document; q=doc.getObject(inp.Prefix+'Quantities')
    for bar in q.Bars:
        bar.Base.Proxy.execute(bar.Base); bar.Proxy.execute(bar)
    q.Proxy.execute(q)
    sh=doc.getObject(inp.Prefix+'Schedule');steel.write_wall_schedule(inp,sh,q.Bars)
    # Do not recompute unrelated source geometry because a rebar changed.
    for o in doc.Objects:o.purgeTouched()
    sh.touch();doc.recompute([sh])

def validate(doc):
    checks=[]; measures=[]; rowsout=[]
    for name in HOSTS:
        inp=doc.getObject('Steel'+name+'Inputs');q=doc.getObject(inp.Prefix+'Quantities')
        checks+=steel.wall_geometry_checks(inp)
        a,b,n0,n1,z0,z1=web_limits(inp); localbars=[];vertical=[];horizontal=[]
        for bar in q.Bars:
            s=bar.Shape.copy();s.Placement=inp.CageFrame.inverse().multiply(s.Placement)
            bb=bounds(s);localbars.append(bb)
            # Actual solid cylinder axes distinguish the two single planes.
            ends=[v.Point for v in bar.Base.Shape.Vertexes]
            delta=ends[-1]-ends[0]
            if abs(delta.z)>abs(delta.x):vertical.append((bb.XMin+bb.XMax)/2)
            else:horizontal.append((bb.ZMin+bb.ZMax)/2)
            host=inp.Host.Shape.copy(); outside=abs(bar.Shape.cut(host).Volume)
            cover=min(bar.Shape.distToShape(f)[0] for f in host.Faces)
            checks.append(result(bar.Name+'_actual_host_cover',outside<=1e-7 and cover+TOL>=inp.Cover.Value,minimum_in=cover/IN,outside_mm3=outside))
            checks.append(result(bar.Name+'_inside_main_web',bb.XMin+TOL>=a+inp.Cover.Value and bb.XMax-TOL<=b-inp.Cover.Value and bb.ZMin+TOL>=z0+inp.Cover.Value and bb.ZMax-TOL<=z1-inp.Cover.Value))
            checks.append(result(bar.Name+'_number4',bar.Base.BarNumber==4 and abs(bar.Diameter.Value-IN*.5)<1e-8))
            rowsout.append(dict(wall=name,mark=bar.Mark,direction='Vertical' if abs(delta.z)>abs(delta.x) else 'Horizontal',bar=bar.Base.BarNumber,quantity=bar.Amount,length_ft=bar.TotalLength.Value/FT,weight_lb=bar.NominalWeightLb))
        lo=min(x.YMin for x in localbars);hi=max(x.YMax for x in localbars)
        planes={k:[] for k in ['vertical','horizontal']}
        for bar in q.Bars:
            k='vertical' if bar.Base.BarID.startswith('MV') else 'horizontal'
            s=bar.Shape.copy();s.Placement=inp.CageFrame.inverse().multiply(s.Placement);bb=bounds(s);planes[k].append((bb.YMin+bb.YMax)/2)
        checks.append(result(name+'_one_centered_mat',all(max(v)-min(v)<TOL for v in planes.values()) and abs((lo+hi)-(n0+n1))<TOL and abs((hi-lo)-IN)<TOL,mat_envelope_in=(hi-lo)/IN,side_cover_in=[(lo-n0)/IN,(n1-hi)/IN]))
        for k,vals,pitch in [('vertical',vertical,inp.VerticalSpacing.Value),('horizontal',horizontal,inp.HorizontalSpacing.Value)]:
            vals.sort();spacings=[(v-u)/IN for u,v in zip(vals,vals[1:])]
            checks.append(result(name+'_'+k+'_spacing',bool(spacings) and all(0<s<=pitch/IN+TOL/IN for s in spacings),spacings_in=spacings))
        sh=doc.getObject(inp.Prefix+'Schedule');r=str(sh.TotalRow)
        checks.append(result(name+'_schedule_links',sh.BarNames==[b.Name for b in q.Bars] and float(sh.get('D'+r))==q.TotalBars and abs(float(sh.get('G'+r))-q.TotalSteelLength.Value/FT)<1e-7 and abs(float(sh.get('H'+r))-q.NominalSteelWeightLb)<1e-7 and '16 in dowels' not in sh.get('A'+str(sh.TotalRow+2))))
        measures.append(dict(wall=name,vertical_bars=len(vertical),horizontal_bars=len(horizontal),total_bars=q.TotalBars,steel_length_ft=q.TotalSteelLength.Value/FT,weight_lb=q.NominalSteelWeightLb,side_cover_in=[(lo-n0)/IN,(n1-hi)/IN],mat_thickness_in=(hi-lo)/IN))
    allinputs=list(doc.WallSteelChecks.Inputs)
    detail=steel.wall_detail_checks(doc,allinputs)
    cheeknames={b.Name for n in HOSTS for b in doc.getObject('Steel'+n+'Quantities').Bars}
    clashes=[c for c in detail['clashes'] if c['a'] in cheeknames or c['b'] in cheeknames]
    checks.append(result('cheek_mat_internal_and_other_wall_cap_bar_clashes',not clashes,failures=clashes))
    invalid=[o.Name for o in doc.Objects if 'Invalid' in o.State]
    checks.append(result('no_invalid_native_objects',not invalid,objects=invalid))
    return dict(checks=checks,failures=[x for x in checks if x['status']=='FAIL'],measurements=measures,schedule=rowsout,all_wall_detailing=detail,limitations='Anchorage, development, laps, lug reinforcement and fabrication are NOT CONFIGURED. Existing backwall and cap detailing checks retain actual failures.')

def update(doc,job):
    out=Path(job['output']);out.mkdir(exist_ok=True);recpath=out/'transaction.json'
    if recpath.exists():raise ValueError('Inspect prior recorded transaction; no blind retry')
    if not doc.FileName or Path(doc.FileName).resolve()!=Path(job['disposable_copy']).resolve():raise ValueError('Explicit disposable file copy required')
    for k in ['vertical_spacing','horizontal_spacing','cover']:length(job[k],positive=True)
    rec=dict(transaction_id=job['request_id'],status='PREPARED',timestamp=datetime.now(timezone.utc).isoformat(),request=job)
    recpath.write_text(json.dumps(rec,indent=2))
    try:
        for name in HOSTS:
            inp=doc.getObject('Steel'+name+'Inputs');inp.AutoSync=False
            prior={k:str(getattr(inp,k)) for k in ['VerticalBar','HorizontalBar','VerticalSpacing','HorizontalSpacing','Cover','SchematicEmbedment','SourceReport','SourceSHA256','Limitations']}
            prop(inp,'App::PropertyString','PreviousSteelBasisJSON',json.dumps(prior),'Revision')
            prop(inp,'App::PropertyString','ScheduleNote','SINGLE CENTERED MAT: #4 each way; 12 in typical/max spacing; 2 in end cover. Anchorage and lug reinforcement not detailed.','Revision')
            prop(inp,'App::PropertyString','MatConfiguration','Single mat; outer vertical and inner horizontal tangent; combined envelope centered in 8 in web.','Revision')
            inp.VerticalBar=4;inp.HorizontalBar=4
            inp.VerticalSpacing=job['vertical_spacing'];inp.HorizontalSpacing=job['horizontal_spacing'];inp.Cover=job['cover'];inp.SchematicEmbedment='0 in'
            inp.SourceReport='User instruction 2026-10-14';inp.SourceSHA256=hashlib.sha256(BASIS.encode()).hexdigest();inp.Limitations=BASIS
            InputsProxy(inp);inp.AutoSync=True;refresh(inp)
        # Prove the new input controller genuinely resynchronizes native counts.
        inp=doc.getObject('Steel'+HOSTS[0]+'Inputs');old=inp.VerticalSpacing;start=len(doc.getObject(inp.Prefix+'Quantities').Bars)
        inp.VerticalSpacing='6 in';refresh(inp);changed=len(doc.getObject(inp.Prefix+'Quantities').Bars)
        inp.VerticalSpacing=old;refresh(inp);restored=len(doc.getObject(inp.Prefix+'Quantities').Bars)
        if not changed>start or restored!=start:raise ValueError('Native count regeneration failed')
        rec['parametric_regeneration']={'status':'PASS','baseline_bars':start,'six_inch_vertical_bars':changed,'restored_bars':restored}
        report=validate(doc);rec['validation']=report
        doc.WallSteelChecks.ReportJSON=json.dumps(report['all_wall_detailing'])
        doc.WallSteelChecks.Status='FAIL' if any(c['status']=='FAIL' for c in report['all_wall_detailing']['checks']) else 'PASS'
        doc.WallSteelChecks.SnapshotBasis='14 October 2026: rerun after centered cheek-mat revision against actual current wall and cap bars. Use design_steel.wall_detail_checks to refresh.'
        check=doc.addObject('App::FeaturePython','CheekSteelChecks');doc.WallReinforcement.addObject(check)
        for typ,k,v in [('App::PropertyString','Status','FAIL' if report['failures'] else 'PASS'),('App::PropertyString','ReportJSON',json.dumps(report)),('App::PropertyLinkList','Inputs',[doc.getObject('Steel'+n+'Inputs') for n in HOSTS]),('App::PropertyString','SnapshotBasis','Dated physical solid, cover, clearance and schedule checks; rerun cheek_steel.validate after editing.'),('App::PropertyString','DetailingStatus','Anchorage / development / laps / lug reinforcement: NOT CONFIGURED')]:prop(check,typ,k,v,'Validation snapshot')
        if report['failures']:raise ValueError('Current cheek mat geometry validation failed')
        for o in doc.Objects:o.purgeTouched()
        rec['status']='VALIDATED'
    except Exception:
        rec['status']='FAIL';rec['traceback']=traceback.format_exc();raise
    finally:
        recpath.write_text(json.dumps(rec,indent=2))
        with (out/'change-journal.jsonl').open('a') as f:f.write(json.dumps({k:rec[k] for k in ['transaction_id','status','timestamp']})+'\n')
    return rec
