"""Explicit transverse-rebar stations, independent of longitudinal U inventory.

Stations are inches from the left cap end. Runs retain the entered pitch;
an optional end bar fills the entered limit with a shorter final interval.
"""
import math
import hashlib
import json
from copy import deepcopy


def empty_detail():
    return {'version':1,'enabled':False,'runs':[]}


def enabled(case):
    return bool(case.get('transverse_detail',{}).get('enabled',False))


def run_regular_count(run):
    return math.floor((run['end_in']-run['first_in'])/run['pitch_in']+1e-9)+1


def run_bar_count(run):
    count=run_regular_count(run)
    last=run['first_in']+(count-1)*run['pitch_in']
    return count+int(run.get('include_end_bar',False) and run['end_in']-last>1e-7)


def run_last_station(run):
    return run['end_in'] if run.get('include_end_bar',False) else run['first_in']+(run_regular_count(run)-1)*run['pitch_in']


def run_stations(run):
    stations=[run['first_in']+i*run['pitch_in'] for i in range(run_regular_count(run))]
    if run.get('include_end_bar',False):
        if run['end_in']-stations[-1]>1e-7:stations.append(run['end_in'])
        else:stations[-1]=run['end_in']
    return stations


def end_bar_note(run):
    if not run.get('include_end_bar',False):return ''
    stations=run_stations(run)
    return f' · last gap {stations[-1]-stations[-2]:g} in' if len(stations)>1 else ' · single end bar'


def validate_detail(case):
    detail=case.get('transverse_detail')
    if detail is None:return
    if not isinstance(detail,dict) or detail.get('version') not in (1,2):
        raise ValueError('Unsupported transverse-detail version.')
    if type(detail.get('enabled')) is not bool:
        raise ValueError('Transverse-detail enabled must be true or false.')
    runs=detail.get('runs')
    if not isinstance(runs,list) or len(runs)>100:
        raise ValueError('Use at most 100 transverse-reinforcement runs.')
    identifiers=set();total=0
    for run in runs:
        if not isinstance(run,dict):raise ValueError('Each transverse run must be a record.')
        label=run.get('id')
        if not isinstance(label,str) or not label.strip() or label in identifiers:
            raise ValueError('Every transverse run needs a unique nonempty ID.')
        identifiers.add(label)
        if run.get('kind') not in ('hoop','pile_u'):
            raise ValueError(f'{label}: choose a closed hoop or pile U-bar.')
        if run.get('zone') not in ('G','L'):
            raise ValueError(f'{label}: shear check must be G or L.')
        bar=run.get('bar')
        if isinstance(bar,bool) or bar not in range(3,12):
            raise ValueError(f'{label}: use bar sizes #3 through #11.')
        for key in ('first_in','end_in','pitch_in'):
            value=run.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError(f'{label}: {key} must be a finite inch dimension.')
        if run['first_in']<0 or run['end_in']<run['first_in'] or run['pitch_in']<=0:
            raise ValueError(f'{label}: use 0 ≤ first station ≤ end limit and positive pitch.')
        if type(run.get('include_end_bar',False)) is not bool:
            raise ValueError(f'{label}: include_end_bar must be true or false.')
        if run.get('include_end_bar',False) and detail['version']<2:
            raise ValueError(f'{label}: an end-limit bar requires transverse-detail version 2.')
        count=run_bar_count(run)
        total+=count
        if total>2000:raise ValueError('The transverse layout exceeds 2,000 bars; check station units and pitch.')
        shape=run.get('shape',{})
        if not isinstance(shape,dict):raise ValueError(f'{label}: shape must be a record.')
        if isinstance(shape.get('end_angle',90),bool) or shape.get('end_angle',90) not in (0,90,135,180):raise ValueError(f'{label}: choose straight, 90°, 135° or 180° U ends.')
        for key in ('inside_diameter_in','tail_in','end_raise_in','side_inset_in'):
            if key not in shape:continue
            v=shape[key]
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1000:
                raise ValueError(f'{label}: {key} must be a finite nonnegative inch dimension, at most 1000.')
        if shape.get('inside_diameter_in',1)<=0:raise ValueError(f'{label}: inside bend diameter must be positive.')
        if type(run.get('development_confirmed',False)) is not bool:raise ValueError(f'{label}: development confirmation must be true or false.')
        if not isinstance(run.get('development_basis',''),str):raise ValueError(f'{label}: development basis must be text.')
        if run.get('development_confirmed') and not run.get('development_basis','').strip():
            raise ValueError(f'{label}: record the checked development detail / calculation before confirming it.')


def scheduled_bars(case):
    """Every physical bar station, without clipping overlaps or obstructions."""
    validate_detail(case)
    if not enabled(case):return []
    bars=[]
    for run in case['transverse_detail']['runs']:
        for i,station in enumerate(run_stations(run)):
            bars.append({'id':f'{run["id"]}-{i+1}','run':run['id'],
                         'kind':run['kind'],'bar':int(run['bar']),'zone':run['zone'],
                         'station_in':station})
    return sorted(bars,key=lambda b:(b['station_in'],b['id']))


def run_summary(case):
    bars=scheduled_bars(case)
    return [dict(deepcopy(run),count=len(group),actual_last_in=group[-1]['station_in'])
            for run in case.get('transverse_detail',{}).get('runs',[])
            if (group:=[b for b in bars if b['run']==run['id']])]


def station_issues(e):
    """Physical extents/overlaps; do not silently move entered reinforcement."""
    if not enabled(e.case):return []
    from .model import BAR_DIAMETER
    p=e.case['inputs'];bars=scheduled_bars(e.case);issues=[]
    if not bars:return ['Actual transverse layout is enabled but contains no bars.']
    for bar in bars:
        radius=BAR_DIAMETER[bar['bar']]/2;x=bar['station_in']
        if x-radius<p['C_s']-1e-8 or x+radius>e.value('L_cap')-p['C_s']+1e-8:
            issues.append(f'{bar["id"]}: transverse bar violates cap end cover at {x/12:.3f} ft.')
    for a,b in zip(bars,bars[1:]):
        gap=b['station_in']-a['station_in']-(BAR_DIAMETER[a['bar']]+BAR_DIAMETER[b['bar']])/2
        if gap<0:
            issues.append(f'{a["id"]} / {b["id"]}: transverse bars overlap; revise adjoining runs.')
    return issues


def shape_parameters(run):
    from .model import BAR_DIAMETER
    d=BAR_DIAMETER[run['bar']]
    return dict({'end_angle':90,'inside_diameter_in':6*d,'tail_in':12*d,
                 'end_raise_in':0.,'side_inset_in':0.},**run.get('shape',{}))


def development_fingerprint(case,run):
    detail={k:run[k] for k in ('kind','bar','zone','first_in','end_in','pitch_in')}
    if run.get('include_end_bar',False):detail['include_end_bar']=True
    detail['shape']=shape_parameters(run)
    # Another run can move the common longitudinal cage and change the end
    # congestion basis, even when this run's entered dimensions stay unchanged.
    cage_shapes=[{'kind':r['kind'],'bar':r['bar'],'shape':shape_parameters(r)}
                 for r in case.get('transverse_detail',{}).get('runs',[])]
    payload={'inputs':case['inputs'],'screening':case['screening'],'run':detail,'cage_shapes':cage_shapes}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def development_current(case,run):
    return bool(run.get('development_confirmed') and run.get('development_basis','').strip()
                and run.get('development_fingerprint')==development_fingerprint(case,run))


def bar_shape(e,run):
    """Cross-section centerline paths (across cap, above underside), in inches.

    U ends are independent: there is never a segment joining them below the pile.
    Entered bend/tail dimensions describe geometry, not calculated development.
    Hoop closure is an outline; its lap/end anchorage remains a separate detail.
    """
    from .model import BAR_DIAMETER
    p=e.case['inputs'];d=BAR_DIAMETER[run['bar']];s=shape_parameters(run)
    r=(s['inside_diameter_in']+d)/2
    left=p['C_s']+d/2+s['side_inset_in'];right=p['b']-left
    top=p['h']-p['C_t']-d/2;bottom=p['C_b']+d/2+s['end_raise_in']
    def arc(x,y,a,b):
        return [(x+r*math.cos(math.radians(a+(b-a)*i/24)),y+r*math.sin(math.radians(a+(b-a)*i/24))) for i in range(25)]
    if run['kind']=='hoop':
        points=arc(left+r,bottom+r,180,270)+arc(right-r,bottom+r,270,360)+arc(right-r,top-r,0,90)+arc(left+r,top-r,90,180)
        points.append(points[0])
    else:
        angle=s['end_angle']
        if angle:
            end=arc(left+r,bottom+r,180,180+angle)
            theta=math.radians(180+angle)
            end.append((end[-1][0]-s['tail_in']*math.sin(theta),end[-1][1]+s['tail_in']*math.cos(theta)))
        else:end=[(left,bottom)]
        points=list(reversed(end))+arc(left+r,top-r,180,90)+arc(right-r,top-r,90,0)+[(p['b']-x,y) for x,y in end]
    return {'points':points,'diameter':d,'radius':r,'parameters':s,
            'length_in':sum(math.dist(a,b) for a,b in zip(points,points[1:])),
            'fit':right-left>=2*r and top-bottom>=2*r}


def suggested_detail(e):
    """Legacy whole-cap pitch grid; the workbench creates a run for each zone."""
    from .model import BAR_DIAMETER
    p=e.case['inputs'];d=BAR_DIAMETER[p['Bar_v']];L=e.value('L_cap');pitch=p['s_G']
    inset=p['D_pile']/2+e.value('Tol_pile')+p['C_pile']+d/2
    centers=[e.value('E_CL')+i*p['S_pile']*12 for i in range(int(p['N_pile']))]
    start=p['C_s']+d/2;end=L-p['C_s']-d/2
    count=math.floor((end-start)/pitch)+1
    if count>2000:raise ValueError('Starting layout exceeds 2,000 bars. Increase overall pitch first.')
    runs=[];last_key=None
    for i in range(count):
        x=start+i*pitch
        pile=next((j+1 for j,c in enumerate(centers) if abs(c-x)<inset+1e-8),None)
        key=('pile_u',pile) if pile else ('hoop',sum(x>c for c in centers))
        if key!=last_key:
            runs.append(dict(id=f'R{len(runs)+1}',kind=key[0],bar=int(p['Bar_v']),zone='G',first_in=x,end_in=x,pitch_in=pitch,
                             development_confirmed=False,development_basis=''))
        else:runs[-1]['end_in']=x
        last_key=key
    return {'version':1,'enabled':True,'runs':runs}


def _point_segment(point,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1];den=dx*dx+dy*dy
    t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/den)) if den else 0
    return math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy)


def _segment_box(a,b,left,right,top):
    """Segment intersection with a conservative pile envelope (unbounded below)."""
    low=0.;high=1.
    for origin,delta,lo,hi in ((a[0],b[0]-a[0],left,right),(a[1],b[1]-a[1],-math.inf,top)):
        if abs(delta)<1e-12:
            if not lo<=origin<=hi:return False
            continue
        t0=(lo-origin)/delta;t1=(hi-origin)/delta
        low=max(low,min(t0,t1));high=min(high,max(t0,t1))
        if low>high:return False
    return True


def shape_issues(e,run):
    from .model import bar_positions
    shape=bar_shape(e,run);p=e.case['inputs'];pts=shape['points'];d=shape['diameter'];issues=[]
    if not shape['fit']:issues.append('Bends do not fit within the entered width / depth.')
    if any(x-d/2<p['C_s']-1e-8 or x+d/2>p['b']-p['C_s']+1e-8 or y-d/2<p['C_b']-1e-8 or y+d/2>p['h']-p['C_t']+1e-8 for x,y in pts):
        issues.append('Bar or end tail violates cap cover.')
    bars=[b for b in scheduled_bars(e.case) if b['run']==run['id']]
    inset=p['D_pile']/2+e.value('Tol_pile')+p['C_pile']+d/2
    centers=[e.value('E_CL')+i*p['S_pile']*12 for i in range(int(p['N_pile']))]
    at_pile=any(abs(b['station_in']-c)<=inset for b in bars for c in centers)
    # Exact line intersection and conservative allowance for discretized arcs.
    chord_allowance=shape['radius']*(1-math.cos(math.pi/48))+1e-8
    if at_pile and p['Pile_embed']>0:
        left=e.value('Pile_left')-p['C_pile']-d/2;right=e.value('Pile_right')+p['C_pile']+d/2
        if any(_segment_box(a,b,left-chord_allowance,right+chord_allowance,p['Pile_embed']+p['C_pile']+d/2+chord_allowance) for a,b in zip(pts,pts[1:])):
            issues.append('Bar intersects embedded pile / clearance envelope. Keep the bottom open and shorten, raise or relocate the ends.')
    # Contact with cage bars is normal; physical overlap is not. Added hooked
    # longitudinal bars need the separate 3D congestion review noted in the UI.
    region='P' if at_pile else 'B'
    clashes=[]
    for bar in bar_positions(e,region):
        gap=min(_point_segment((bar['x'],bar['y']),a,b) for a,b in zip(pts,pts[1:]))-(d+bar['diameter'])/2
        if gap<-.03:clashes.append(bar['kind'])
    if clashes:issues.append('Physical overlap with longitudinal bars: '+', '.join(sorted(set(clashes)))+'.')
    if run['kind']=='pile_u':
        a=pts[0];b=pts[-1]
        if a[0]+d/2>=b[0]-d/2:issues.append('U end tails meet or cross; the bottom opening is lost.')
    return issues


def transverse_issues(e):
    if not enabled(e.case):return []
    issues=station_issues(e)
    for run in e.case['transverse_detail']['runs']:
        issues.extend(run['id']+': '+s for s in shape_issues(e,run))
    return issues


def shear_intervals(e):
    """Existing conditional shear calculation, shared by checks and diagrams."""
    from .model import BAR_AREA
    if not enabled(e.case):return []
    p=e.case['inputs'];bars=scheduled_bars(e.case);intervals=[]
    for a,b in zip(bars,bars[1:]):
        pitch=b['station_in']-a['station_in'];size=min(a['bar'],b['bar'])
        zone=max((a['zone'],b['zone']),key=lambda z:p['Vu_'+z]);vu=p['Vu_'+zone]
        area=2*BAR_AREA[size]
        vs=area*p['fy']*e.value('dv')*e.value('cot_theta')/max(pitch,1e-6)
        vr=p['phi_v']*min(e.value('Vc','kip')+vs,e.value('Vn_limit','kip'))
        ratio=max(vu/max(vr,1e-6),vu/p['phi_v']/max(e.value('Vn_limit','kip'),1e-6))
        intervals.append(dict(a=a,b=b,pitch=pitch,zone=zone,vu=vu,area=area,vr=vr,ratio=ratio))
    return intervals


def transverse_checks(e):
    """Detail screens, plus conditional two-leg shear at actual adjacent spacing.

    Uses existing sectional shear equations. Never assigns closed-hoop torsion
    resistance to a U, or adds a transverse U to longitudinal flexural area.
    """
    from .model import Check,BAR_AREA,BAR_DIAMETER
    from .detailing import required_clear
    from .check_details import Component,explain
    if not enabled(e.case):return []
    p=e.case['inputs'];bars=scheduled_bars(e.case);checks=[]
    runs={r['id']:r for r in e.case['transverse_detail']['runs']}
    for run in runs.values():
        confirmed=development_current(e.case,run)
        checks.append(Check('Status_transverse_development_'+run['id'],run['id']+' end development / closure',
            'RECORDED' if confirmed else 'PENDING','N/A',
            ('User-recorded check: '+run['development_basis']) if confirmed else 'Enter bend / tail dimensions and record the checked development calculation. Geometry alone does not establish anchorage.'))
    for interval in shear_intervals(e):
        a,b=interval['a'],interval['b']
        pitch,zone,vu,area,vr,ratio=(interval[k] for k in ('pitch','zone','vu','area','vr','ratio'))
        name=a['id']+' → '+b['id'];key=a['id']+'_'+b['id']
        checks.append(Check('Chk_actual_shear_'+key,name+' shear (anchorage conditional)','FAIL' if ratio>1 else 'CONDITIONAL',ratio,
            f'Actual interval {pitch:.3f} in; weaker vertical two-leg area {area:.3f} in²; larger adjacent shear {vu:.3f} kip; Vr {vr:.3f} kip. Requires developed legs, appropriate local shear model and force-zone review. No U-bar torsion credit.'))
        explain(checks[-1],[Component('Shear resistance',vu,max(vr,1e-6),'kip'),
            Component('Section upper bound',vu/p['phi_v'],max(e.value('Vn_limit'),1e-6),'kip')])
        across=max(p['b']-2*p['C_s']-BAR_DIAMETER[item['bar']]-2*shape_parameters(runs[item['run']])['side_inset_in'] for item in (a,b))
        spacing=max(pitch/e.value('s_code_'+zone),across/e.value('Sw_'+zone))
        checks.append(Check('Chk_actual_pitch_'+key,name+' maximum spacing','PASS' if spacing<=1 else 'FAIL',spacing,
            'Actual adjacent pitch and wider adjacent outer-leg separation / sectional code spacing limits. Actual strength and minimum area rate are checked separately.'))
        explain(checks[-1],[Component('Along-cap bar spacing',pitch,e.value('s_code_'+zone),'in'),
            Component('Across-cap leg spacing',across,e.value('Sw_'+zone),'in')])
        clear=pitch-(BAR_DIAMETER[a['bar']]+BAR_DIAMETER[b['bar']])/2
        req=required_clear(e,max(BAR_DIAMETER[a['bar']],BAR_DIAMETER[b['bar']]))
        clear_ratio=1. if math.isclose(clear,req,rel_tol=0,abs_tol=1e-8) else req/max(clear,1e-6)
        checks.append(Check('Chk_actual_clear_'+key,name+' clear spacing','PASS' if clear_ratio<=1 else 'FAIL',clear_ratio,f'Actual {clear:.3f} in; required {req:.3f} in.'))
        rate=area/max(pitch,1e-6);minimum=e.value('Av_min_rate')
        checks.append(Check('Chk_actual_min_'+key,name+' minimum shear steel','PASS' if rate>=minimum else 'FAIL',minimum/rate,'Two weaker legs / actual adjacent pitch; existing sectional minimum rate.'))
    if bars:
        # A deliberately conservative end screen; end-zone design still reviewed.
        edge=max(bars[0]['station_in'],e.value('L_cap')-bars[-1]['station_in'])
        limit=min(e.value('s_code_G'),e.value('s_code_L'))/2
        checks.append(Check('Chk_actual_end','First / last transverse bar end coverage','PASS' if edge<=limit else 'FAIL',edge/limit,f'Max end distance {edge:.3f} in / half the tighter sectional pitch limit {limit:.3f} in. Conservative screening rule, not an end-region design.'))
        explain(checks[-1],[Component('Left cap end',bars[0]['station_in'],limit,'in'),
            Component('Right cap end',e.value('L_cap')-bars[-1]['station_in'],limit,'in')])
    has_u=any(r['kind']=='pile_u' for r in runs.values())
    required=p['Tu']>e.value('T_threshold','kip*ft')
    checks.append(Check('Status_actual_torsion','Actual transverse torsion path','PENDING' if required else 'BELOW THRESHOLD','N/A',
        ('Open-bottom U-bars do not form closed torsion hoops. Resolve the torsion path at pile zones.' if has_u else 'Verify closed-hoop end anchorage, enclosure and local torsion demand.') if required else 'Input torque is below the existing investigation threshold. No closed-hoop torsion resistance is assigned to U-bars.'))
    checks.append(Check('Status_actual_review','Actual layout · force zones / anchorage / congestion','PENDING','N/A',
        'Actual bars are drawn and counted. Conditional shear checks use entered G/L demands; verify zone applicability, end-region behavior, hoop closure, U development and 3D congestion with longitudinal hook ends. Uniform-cage equations remain reference results.'))
    return checks
