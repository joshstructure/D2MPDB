"""Case validation, C005 calculations, D/C register and explicit cage screens."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import json
import math
from .engine import Engine, ScalarEngine, Q, parse
from .detailing import required_clear,spacing_records,hook_paths,layer_alignment
from .transverse import enabled as actual_transverse,validate_detail,transverse_checks,transverse_issues,bar_shape,run_summary
from .pile_visual import validate_pile_visual

DATA=Path(__file__).parent/'data'
DEFINITIONS=json.loads((DATA/'c005_formulas.json').read_text(encoding='utf-8'))
SPEC=json.loads((DATA/'dc_ratio_spec.json').read_text(encoding='utf-8'))
INPUTS={d['name']:d for d in DEFINITIONS if d['input']}
FORMULAS=Engine(DEFINITIONS)
FAST=ScalarEngine(DEFINITIONS)
RATIOS={k:parse(s['formula']) for k,s in SPEC.items() if s['formula']}
INPUT_UNITS={n:FORMULAS.eval(parse('1 '+d['unit']),{}) if d['unit'] else Q(1) for n,d in INPUTS.items()}
BAR_AREA={3:.11,4:.20,5:.31,6:.44,7:.60,8:.79,9:1.,10:1.27,11:1.56}
BAR_DIAMETER={3:.375,4:.5,5:.625,6:.75,7:.875,8:1.,9:1.128,10:1.27,11:1.41}
GEOMETRY=('N_pile','S_pile','D_pile','b','h','E_clear','E_detail')
PILE_GEOMETRY=('N_pile','S_pile','D_pile','E_clear','E_detail')

def default_case():
    return upgrade_case(json.loads((DATA/'default_case.json').read_text(encoding='utf-8')))

def upgrade_case(case):
    """Copy saved inputs into the continuous-plus-additional steel schema."""
    result=deepcopy(case)
    if result.get('schema_version')==1:
        p=result.get('inputs',{});units=result.get('units',{})
        if 'Bar_pos' not in p or 'Bar_pos' not in units:
            raise ValueError('Legacy case is missing Bar_pos or its units.')
        if {'Bar_P','Bar_B'} & (set(p)|set(units)):
            raise ValueError('Legacy case mixes common and independent bar definitions.')
        bar=p.pop('Bar_pos');unit=units.pop('Bar_pos')
        p.update(Bar_P=bar,Bar_B=bar);units.update(Bar_P=unit,Bar_B=unit)
        p.update(Ready_pile=False,Pile_embed=0,C_pile=0)
        units.update(Ready_pile='unitless',Pile_embed='in',C_pile='in')
        result['schema_version']=2
    if result.get('schema_version')==2:
        p=result['inputs']
        if any(p.get(n) not in BAR_AREA for n in ('Bar_P','Bar_B')):
            raise ValueError('Saved case needs supported continuous and span bar sizes before conversion.')
        if any(isinstance(p.get(n),bool) or not isinstance(p.get(n),(int,float)) or not math.isfinite(p[n]) or p[n]<0 or p[n]!=int(p[n])
               for n in ('n_P1','n_P2','n_B1','n_B2')):
            raise ValueError('Saved case needs nonnegative whole row counts before conversion.')
        former={f'n_B{k}':p[f'n_B{k}'] for k in (1,2)}
        for k in (1,2):
            missing=p[f'n_B{k}']*BAR_AREA[p['Bar_B']]-p[f'n_P{k}']*BAR_AREA[p['Bar_P']]
            p[f'n_B{k}']=max(0,math.ceil(missing/BAR_AREA[p['Bar_B']]-1e-10))
        result['schema_version']=3
        result['reinforcement_migration']={'former_span_totals':former,
            'note':'Older span counts were totals in independent regional cages. Each row now keeps the continuous Bar_P steel and adds enough Bar_B bars to meet or exceed its former span area, rounded up to whole bars (minimum zero). Review combined area, centroid and fit, especially for mixed sizes or former span totals below the continuous steel.'}
    screen=result.setdefault('screening',{})
    screen.setdefault('aggregate_in',0.75)
    screen.setdefault('aggregate_confirmed',False)
    screen.setdefault('code_basis','AASHTO LRFD BDS 5.10.3 / 5.10.2; FDOT SDM 2026 4.3.2 and 4.3.4; contract criteria govern')
    p=result.get('inputs',{})
    former={k:p.get(k,0) for k in ('n_PU','n_BU')}
    if any(former.values()) and all(type(v) in (int,float) and math.isfinite(v) and v>=0 and v==int(v) for v in former.values()):
        result['retired_u_leg_inventory']={**former,'Bar_U':p.get('Bar_U'),
            'note':f"Removed legacy longitudinal U-leg allowance: {former['n_PU']:g} pile legs and {former['n_BU']:g} span legs. Their steel area is no longer credited; review the recalculated checks. Actual transverse pile U-bar runs are unchanged."}
        p.update(n_PU=0,n_BU=0)
    from .lrfd_checks import settings
    result['lrfd_checks']=settings(result)
    return result

def set_inputs(case,**changes):
    result=upgrade_case(case)
    # Older scripts can still assign one common size explicitly.
    if 'Bar_pos' in changes:
        common=changes.pop('Bar_pos')
        changes.setdefault('Bar_P',common);changes.setdefault('Bar_B',common)
    unknown=set(changes)-set(INPUTS)
    if unknown:raise ValueError(f'Unknown inputs: {sorted(unknown)}')
    result['inputs'].update(changes)
    return result

def validate_case(case):
    validate_detail(case)
    from .lrfd_checks import validate_settings
    validate_settings(case)
    if case.get('schema_version') not in (3,4):raise ValueError('Expected case schema_version 3 or 4; load older cases through load_case().')
    from .added_steel import validate_layout
    validate_layout(case)
    expected_units={n:d['unit'] or 'unitless' for n,d in INPUTS.items()}
    if case.get('units')!=expected_units:raise ValueError('Case units differ from the input schema. Use the units in default_case.json; convert values before importing.')
    p=case.get('inputs',{})
    if set(p)!=set(INPUTS):raise ValueError(f'Input names differ. Missing: {sorted(set(INPUTS)-set(p))}; unknown: {sorted(set(p)-set(INPUTS))}')
    booleans={'Ready_III','Ready_fatigue','Ready_pile','Manual_spacing'}
    for n,v in p.items():
        if n in booleans:
            if type(v) is not bool:raise ValueError(f'{n} must be true or false.')
            continue
        if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v):raise ValueError(f'{n} must be a finite number.')
        if n.startswith('Bar_') and v not in BAR_AREA:raise ValueError(f'{n}: supported bars are #3 through #11.')
        if n.startswith('n_') or n=='N_pile':
            if v!=int(v) or not 0<=v<=200:raise ValueError(f'{n} must be an integer from 0 to 200.')
        if n not in ('fpc','MDL_N','MDL_P','MDL_B') and v<0:raise ValueError(f'{n} must be nonnegative.')
    for n in ('b','h','fc','fy','Es','C_t','C_b','C_s','s_row','s_G','s_L','D_pile','S_pile','phi_f','phi_v','beta_v','gamma_e','gamma_fat','Ao_factor'):
        if p[n]<=0:raise ValueError(f'{n} must be greater than zero.')
    if not 0<p['theta']<90 or not 0<p['alpha_v']<180:raise ValueError('Use 0 < theta < 90 and 0 < alpha_v < 180 degrees.')
    if p['N_pile']<2 or min(p['n_N1'],p['n_P1'])<2 or p['n_loop']<1:raise ValueError('At least two piles, two top and continuous bottom bars and one loop are required. Added span bars may be zero.')
    if p['b']<=2*p['C_s']+2*BAR_DIAMETER[p['Bar_v']] or p['h']<=p['C_t']+p['C_b']+2*BAR_DIAMETER[p['Bar_v']]:raise ValueError('Cover and hoops do not fit inside the cap.')
    if p['Pile_embed']>p['h']:raise ValueError('Pile embedment exceeds the cap depth.')
    clearance=case.get('screening',{}).get('minimum_clear_in')
    if isinstance(clearance,bool) or not isinstance(clearance,(int,float)) or not math.isfinite(clearance) or clearance<0:raise ValueError('Screening clear spacing must be a finite nonnegative number.')
    aggregate=case['screening'].get('aggregate_in')
    if isinstance(aggregate,bool) or not isinstance(aggregate,(int,float)) or not math.isfinite(aggregate) or aggregate<=0:raise ValueError('Maximum aggregate size must be a positive finite number in inches.')
    if type(case['screening'].get('aggregate_confirmed')) is not bool:raise ValueError('Aggregate confirmation must be true or false.')
    analysis=case.get('analysis',{})
    if not isinstance(analysis.get('id'),str) or not analysis['id'].strip():raise ValueError('An analysis case ID is required.')
    g=analysis.get('geometry',{})
    if set(g)!=set(GEOMETRY) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in g.values()):raise ValueError('Analysis geometry must record all seven geometry inputs.')
    validate_pile_visual(case)
    return case

def analysis_match(case):
    return [n for n in GEOMETRY if not math.isclose(case['inputs'][n],case['analysis']['geometry'][n],rel_tol=0,abs_tol=1e-6)]

@dataclass
class Check:
    key:str
    label:str
    status:str
    ratio:object
    basis:str
    components:tuple=()
    governing:str=''
    component_rule:str=''

@dataclass
class Evaluation:
    case:dict
    engine:object
    checks:list
    issues:list
    stale:list
    eligible:bool
    status:str
    max_dc:float
    weight_lb:float
    longitudinal_layout:object=None
    spacing_values:object=None
    lrfd:object=None

    def value(self,name,unit=None):
        v=self.engine.get(name)
        if isinstance(v,Q):
            if unit:
                u=FORMULAS.eval(parse('1 '+unit),{});v.same(u)
                return v.v/u.v
            return v.v
        return v

def bar_positions(e,region='B'):
    """P bars are continuous. B counts are ADDITIONAL bars in each bottom layer.

    Extras use Bar_B and fill the largest remaining clear intervals; existing
    continuous bars never move between sections. U bars remain unresolved.
    """
    if e.longitudinal_layout is not None:
        return [dict(v) for v in e.longitudinal_layout['bars'][region]]
    p=e.case['inputs'];b=p['b'];h=p['h'];dv=BAR_DIAMETER[p['Bar_v']]
    bars=[]
    def row(n,size,y,label,manual=None,split=False):
        n=int(n);diam=BAR_DIAMETER[size]
        if n==0:return
        x0=p['C_s']+dv+diam/2
        pitch=(b-2*x0)/max(n-1,1)
        if manual and p['Manual_spacing']:pitch=p[manual]
        xs=[b/2+(j-(n-1)/2)*pitch for j in range(n)]
        if split:
            left=(n+1)//2;right=n-left
            span=e.value('Pile_left')-p['C_pile']-diam/2-x0
            xs=[]
            for count,sign,outer in ((left,1,x0),(right,-1,b-x0)):
                step=p[manual] if manual and p['Manual_spacing'] else span/max(count-1,1)
                xs.extend(outer+sign*j*step for j in range(count))
        for x in xs:bars.append({'x':x,'y':y,'diameter':diam,'kind':label,'layer':label,'bar':int(size),'additional':False})
    for k in (1,2,3):row(p[f'n_N{k}'],p[f'Bar_N{k}'],h-e.value(f'y_N{k}'),f'Top row {k}','SP_detail_N' if k==1 else None)
    for k in (1,2):
        y=e.value(f'y_P{k}');size=p['Bar_P']
        split=p['Ready_pile'] and y-BAR_DIAMETER[size]/2<p['Pile_embed']+p['C_pile']
        label=f'Bottom row {k}'
        row(p[f'n_P{k}'],size,y,label,'SP_detail_P' if k==1 else None,split)
        if region=='B':
            extra=int(p[f'n_B{k}'])
            diameter=BAR_DIAMETER[p['Bar_B']];x0=p['C_s']+dv+diameter/2
            from .added_steel import entered_positions,legacy_spacing
            entered=entered_positions(e.case,k)
            if entered is not None:xs=entered
            elif p['Manual_spacing'] and k==1 and legacy_spacing(e.case):
                xs=[b/2+(j-(extra-1)/2)*p['SP_detail_B'] for j in range(extra)]
            else:
                existing=sorted((v for v in bars if v['layer']==label),key=lambda v:v['x'])
                edges=[(p['C_s']+dv,p['C_s']+dv)]+[(v['x']-v['diameter']/2,v['x']+v['diameter']/2) for v in existing]+[(b-p['C_s']-dv,b-p['C_s']-dv)]
                slots=[dict(left=a[1],right=c[0],n=0) for a,c in zip(edges,edges[1:])]
                for _ in range(extra):
                    slot=max(slots,key=lambda v:(v['right']-v['left']-(v['n']+1)*diameter)/(v['n']+2))
                    slot['n']+=1
                xs=[]
                for slot in slots:
                    gap=(slot['right']-slot['left']-slot['n']*diameter)/(slot['n']+1)
                    xs.extend(slot['left']+gap+diameter/2+j*(gap+diameter) for j in range(slot['n']))
            for x in xs:
                bars.append({'x':x,'y':e.value(f'y_B{k}'),'diameter':diameter,'kind':f'Added span row {k}',
                    'layer':label,'bar':int(p['Bar_B']),'additional':True})
    n=int(p['n_skin']);diam=BAR_DIAMETER[p['Bar_skin']]
    bottom=e.value('y_P1');top=h-e.value('y_N1')
    pitch=e.value('SP_skin') if p['Manual_spacing'] else (top-bottom)/(n+1)
    mid=(top+bottom)/2
    for side in (p['C_s']+dv+diam/2,b-p['C_s']-dv-diam/2):
        for j in range(n):bars.append({'x':side,'y':mid+(j-(n-1)/2)*pitch,'diameter':diam,'kind':'Skin','layer':'Skin','bar':int(p['Bar_skin']),'additional':False})
    return bars

def cage_issues(e):
    p=e.case['inputs'];issues=[];clear=e.case['screening']['minimum_clear_in'];dv=BAR_DIAMETER[p['Bar_v']]
    if not p['Ready_pile']:issues.append('Pile-head embedment and bar clearance are unconfirmed. Enter them under Geometry → Pile head before searching.')
    if p['n_PU'] or p['n_BU']:issues.append('U-leg positions/development are unresolved; drawn as an inventory only.')
    if p['n_loop']!=1:issues.append('Multiple-loop topology is unresolved; only the outer hoop is drawn.')
    for z in 'PB':
        bars=bar_positions(e,z)
        outside=any(v['x']-v['diameter']/2<p['C_s']+dv-1e-6 or v['x']+v['diameter']/2>p['b']-p['C_s']-dv+1e-6 or v['y']-v['diameter']/2<p['C_b']+dv-1e-6 or v['y']+v['diameter']/2>p['h']-p['C_t']-dv+1e-6 for v in bars)
        if outside and not actual_transverse(e.case):issues.append(f'{z} section: bars extend outside the clear interior of the hoop.')
        for r in spacing_records(e,z,bars):
            if r['status']=='FAIL':issues.append(f"{z} section {r['label']}: clear spacing {r['actual']:.2f} in < required {r['required']:.2f} in.")
        issues.extend(f'{z} section: {problem}' for problem in layer_alignment(bars))
        if z=='P' and p['Ready_pile']:
            for bar in bars:
                dx=max(e.value('Pile_left')-bar['x'],0,bar['x']-e.value('Pile_right'))
                dy=max(-bar['y'],0,bar['y']-p['Pile_embed'])
                gap=math.hypot(dx,dy)-bar['diameter']/2
                if gap+1e-8<p['C_pile']:
                    issues.append('P section: a bar intersects the pile footprint or its required clearance, including placement tolerance.')
                    break
    return issues

def steel_quantity_components(e):
    # Continuous bars plus each explicitly drawn hooked span supplement.
    p=e.case['inputs'];length=e.value('L_cap');dv=BAR_DIAMETER[p['Bar_v']]
    continuous=(e.value('As_N')+e.value('As_P')+2*e.value('As_side'))*max(0,length-2*p['C_s'])
    longitudinal=continuous
    for path in hook_paths(e,bar_positions(e,'B')):
        longitudinal+=BAR_AREA[path['bar']['bar']]*(max(0,path['straight'])+math.pi*path['radius']+2*path['tail'])
    hoop_length=2*(p['b']-2*p['C_s']-dv+p['h']-p['C_t']-p['C_b']-dv)
    count=math.ceil(max(0,length-2*p['C_s'])/min(p['s_G'],p['s_L']))+1
    transverse=count*p['n_loop']*hoop_length*BAR_AREA[p['Bar_v']]
    if actual_transverse(e.case):
        transverse=sum(r['count']*bar_shape(e,r)['length_in']*BAR_AREA[r['bar']] for r in run_summary(e.case))
    return {'continuous_in3':continuous,'additional_in3':longitudinal-continuous,
            'transverse_in3':transverse,'density_lb_ft3':490,
            'weight_lb':(longitudinal+transverse)*490/1728}


def estimate_weight(e):
    return steel_quantity_components(e)['weight_lb']


def detailing_checks(e):
    checks=[];p=e.case['inputs']
    from .added_steel import added_clearances,fit_problems
    for r in added_clearances(e,bar_positions(e,'B')):
        label='Added to added' if r['family']=='added' else 'Added to continuous'
        checks.append(Check(f"Chk_added_clear_{r['row']}_{r['family']}",f"Row {r['row']} · {label} clear spacing",r['status'],r['ratio'],
            f"Actual surface gap {r['actual']:.3f} in; required {r['required']:.3f} in. Required / actual; overlap fails. AASHTO LRFD 5.10.3 plus project minimum."))
    if e.case.get('added_bar_layout',{}).get('mode')=='spacing':
        issues=fit_problems(e,bar_positions(e,'B'))
        checks.append(Check('Chk_added_fit','Entered added-bar spacing · cover / cage fit','FAIL' if issues else 'PASS',2 if issues else 0,
            '; '.join(issues) or 'Entered center spacing and row offsets fit inside the cap cover / transverse cage envelope.'))
    for region in 'PB':
        bars=bar_positions(e,region)
        for i,r in enumerate(spacing_records(e,region,bars)):
            checks.append(Check(f'Chk_clear_{region}_{i}',f"{region} clear spacing · {r['label']}",r['status'],r['ratio'],
                f"{r['basis']}: actual {r['actual']:.3f} in; required {r['required']:.3f} in. Ratio = required / actual; contact/overlap fails. AASHTO LRFD 5.10.3 plus project minimum."))
        aligned=not layer_alignment(bars)
        checks.append(Check('Chk_alignment_'+region,region+' layer alignment','PASS' if aligned else 'FAIL',0 if aligned else 2,
            'AASHTO LRFD 5.10.3.1.3: align bars vertically for layers separated by at most 6 in.'))
        xs=sorted(b['x'] for b in bars if b['layer']=='Bottom row 1')
        pitch=max((b-a for a,b in zip(xs,xs[1:])),default=0)
        for state,enabled in [('I',True),('III',p['Ready_III'])]:
            if not enabled:continue
            limit=e.value('S'+state+'_'+region)
            checks.append(Check(f'Chk_drawn_{state}_{region}',f'{region} actual row spacing · Service {state}',
                'PASS' if limit>0 and pitch<=limit+1e-8 else 'FAIL',pitch/max(limit,1e-6),
                f'Maximum actual center spacing {pitch:.3f} in / service limit {limit:.3f} in; includes the gap across the pile.'))
        if region=='B':
            limit=e.value('s_shrink_limit')
            checks.append(Check('Chk_drawn_shrink_B','B actual row spacing · shrinkage','PASS' if pitch<=limit+1e-8 else 'FAIL',pitch/limit,
                f'Maximum actual bottom-row center spacing {pitch:.3f} in / shrinkage limit {limit:.3f} in.'))
    for z in 'GL':
        actual=p['s_'+z]-BAR_DIAMETER[p['Bar_v']];required=required_clear(e,BAR_DIAMETER[p['Bar_v']])
        checks.append(Check('Chk_hoop_clear_'+z,'Hoop minimum clear spacing · '+z,'PASS' if actual>=required else 'FAIL',required/max(actual,1e-6),
            f'Pitch minus hoop diameter: {actual:.3f} in; conservative parallel-bar minimum {required:.3f} in. Maximum hoop pitch is checked separately.'))
        across=p['b']-2*p['C_s']-BAR_DIAMETER[p['Bar_v']];limit=e.value('Sw_'+z)
        checks.append(Check('Chk_drawn_hoop_legs_'+z,'Actual outer-hoop leg spacing · '+z,'PASS' if across<=limit else 'FAIL',across/limit,
            f'Drawn outer leg centers {across:.3f} in / limit {limit:.3f} in. A spacing override does not create undrawn inner legs.'))
    paths=hook_paths(e,bar_positions(e,'B'))
    if paths:
        top=max(t['top']+t['bar']['diameter']/2 for t in paths)
        transverse_diameter=max((BAR_DIAMETER[r['bar']] for r in e.case['transverse_detail']['runs']),default=BAR_DIAMETER[p['Bar_v']]) if actual_transverse(e.case) else BAR_DIAMETER[p['Bar_v']]
        limit=p['h']-p['C_t']-transverse_diameter
        fit=min(t['straight'] for t in paths)>=0 and top<=limit+1e-8
        checks.append(Check('Chk_hook_fit','90° span hooks · fit','PASS' if fit else 'FAIL',max(top/limit,2 if min(t['straight'] for t in paths)<0 else 0),
            'General bars: inside bend diameter 6db (#3–8), 8db (#9–11); straight tail 12db. Hook turns up outside the pile clearance envelope.'))
        from .check_details import Component,explain
        explain(checks[-1],[Component('Hook height / available height',top,limit,'in'),
            Component('Straight-length fit flag',2 if min(t['straight'] for t in paths)<0 else 0,1,'flag')],
            note=f"Shortest straight portion {min(t['straight'] for t in paths):.3f} in. Negative straight length uses the existing failure flag 2; this flag is not a physical D/C.")
        continuous=bar_positions(e,'P')
        worst=0;min_gap=math.inf;req_at_worst=0
        # A hook traverses the entire vertical interval at fixed transverse x;
        # continuous bars occupy every along-cap station, so this distance is exact.
        for t in paths:
            a=t['bar']
            for b in continuous:
                dy=max(a['y']-b['y'],0,b['y']-t['top'])
                gap=math.hypot(a['x']-b['x'],dy)-(a['diameter']+b['diameter'])/2
                req=required_clear(e,max(a['diameter'],b['diameter']))
                ratio=req/max(gap,1e-6)
                if ratio>worst:worst=ratio;min_gap=gap;req_at_worst=req
        checks.append(Check('Chk_hook_cage','Span hooks · clearance to continuous cage','PASS' if min_gap+1e-8>=req_at_worst else 'FAIL',worst,
            f'Minimum hook-to-continuous-bar clear gap {min_gap:.3f} in; required {req_at_worst:.3f} in.'))
        unique=[t for t in paths if t['span']==1]
        minimum=math.inf;required=0
        for i,a in enumerate(unique):
            for b in unique[i+1:]:
                # Equal-size added bars use the same bend radius and end station.
                # Vertical tails expose clashes between hooks in different layers.
                dy=max(a['bar']['y']+a['radius']-b['top'],b['bar']['y']+b['radius']-a['top'],0)
                gap=math.hypot(a['bar']['x']-b['bar']['x'],dy)-(a['bar']['diameter']+b['bar']['diameter'])/2
                if gap<minimum:minimum=gap;required=required_clear(e,a['bar']['diameter'])
        if math.isfinite(minimum):
            checks.append(Check('Chk_hook_pairs','Added hooks · mutual tail clearance','PASS' if minimum+1e-8>=required else 'FAIL',required/max(minimum,1e-6),
                f'Clear distance between vertical hook tails {minimum:.3f} in; required {required:.3f} in.'))
        checks.append(Check('Status_hook_development','Span hook development / cutoff','PENDING','PENDING',
            'Bend dimensions alone do not establish anchorage. Verify critical section, required ldh, cutoff extension and confinement; hooks beside a pile are not assumed developed into it.'))
    checks.append(Check('Status_continuous_anchorage','Continuous bars · end anchorage / splices','PENDING','PENDING',
        'Continuous bars run between end-cover planes. End development and any required splices remain a detailing review.'))
    if not actual_transverse(e.case):
        checks.append(Check('Status_pile_hoops','Hoop zones / pile-head arrangement','PENDING','PENDING',
            'Actual layout is not enabled. Use Actual hoops and pile U-bars to enter bar sizes, first stations, end limits and pitch. Reference samples do not establish construction locations.'))
    confirmed=e.case['screening']['aggregate_confirmed']
    checks.append(Check('Status_aggregate','Aggregate size / spacing basis','PASS' if confirmed else 'PENDING','N/A' if confirmed else 'PENDING',
        f"Maximum aggregate {e.case['screening']['aggregate_in']:g} in. {e.case['screening']['code_basis']}."))
    return checks

def sectional_checks_pass(e):
    """Numerical/detail screens only; analysis provenance is a separate gate."""
    return not any('FAIL' in c.status for c in e.checks) and not e.issues

def evaluate(case=None,fast=False):
    case=upgrade_case(default_case() if case is None else case);validate_case(case)
    stale=analysis_match(case);overrides={}
    for n,v in case['inputs'].items():
        u=INPUT_UNITS[n]
        overrides[n]=v if isinstance(v,bool) else v*u.v if fast else Q(v*u.v,u.d)
    overrides['Status_layout']='REIMPORT ANALYSIS FORCES' if any(n in PILE_GEOMETRY for n in stale) else 'SOURCE PILE LAYOUT'
    overrides['Status_section']='RECHECK MODEL SELF-WEIGHT / FORCES' if any(n in ('b','h') for n in stale) else 'SOURCE SECTION'
    eng=(FAST if fast else FORMULAS).fork(overrides)
    layout=None;spacing_values={}
    if actual_transverse(case):
        from .placement import actual_layout
        trial=Evaluation(case,eng,[],[],stale,False,'',0,0)
        layout=actual_layout(trial)
        if layout is not None:
            # Fresh engine: no reference-position dependency can remain cached.
            overrides.update({n:v if fast else Q(v,(1,0,0)) for n,v in layout['values'].items()})
            eng=(FAST if fast else FORMULAS).fork(overrides)
    if layout is None and case.get('added_bar_layout',{}).get('mode') in ('auto','spacing'):
        trial=Evaluation(case,eng,[],[],stale,False,'',0,0)
        xs=sorted(b['x'] for b in bar_positions(trial,'B') if b['layer']=='Bottom row 1')
        maximum=max((b-a for a,b in zip(xs,xs[1:])),default=0.)
        spacing_values={'SP_B':maximum,'SP_B_auto':maximum}
        overrides.update({n:v if fast else Q(v,(1,0,0)) for n,v in spacing_values.items()})
        eng=(FAST if fast else FORMULAS).fork(overrides)
    eng.all()
    checks=[]
    for key,s in SPEC.items():
        ratio=eng.eval(RATIOS[key],{}) if key in RATIOS else 'N/A'
        if isinstance(ratio,Q):
            if ratio.d!=(0,0,0):raise ValueError('D/C must be dimensionless: '+key)
            ratio=ratio.v
        if isinstance(ratio,(float,int)) and not math.isfinite(ratio):raise ValueError('Nonfinite D/C: '+key)
        checks.append(Check(key,s['label'],eng.get(key),ratio,s['basis']))
    e=Evaluation(case,eng,checks,[],stale,False,'',max((c.ratio for c in checks if isinstance(c.ratio,(float,int))),default=0),0,layout,spacing_values)
    for check in checks:
        if check.key.startswith('Chk_long_'):
            region=check.key[-1]
            required=e.value('F_long_'+region,'kip')/case['inputs']['fy']
            main=e.value('As_'+region,'in^2');side=e.value('As_skin_eff','in^2')
            check.basis+=(f' Required {required:.3f} in²; credited main {main:.3f} + side {side:.3f}'
                          f' = {main+side:.3f} in²; shortfall {max(0,required-main-side):.3f} in².')
    checks.extend(detailing_checks(e))
    if layout is not None:
        checks.append(Check('Chk_actual_longitudinal_fit','Longitudinal steel inside actual hoops / U-bars',
            'PASS' if layout['fitted'] else 'FAIL',0 if layout['fitted'] else 2,
            'One common envelope of all actual runs governs continuous and added straight bars. Row counts and row spacing are retained. Actual positions feed steel centroids, effective depths and bar-spacing checks. Hook ends, development and transverse-to-pile conflicts require their separate checks.'))
    if actual_transverse(case):
        for check in checks:
            if check.key.startswith(('Chk_shear_','Chk_spacing_','Chk_torsteel_','Chk_long_','Chk_hoop_clear_','Chk_drawn_hoop_legs_','Chk_shrink_')) or check.key=='Status_overall':
                check.label+=' · uniform reference'
                check.basis+=' Uniform closed-hoop calculation only; not a capacity determination for the entered hoop/U layout.'
                check.status='REFERENCE';check.ratio='N/A'
        checks.extend(transverse_checks(e))
    from .check_details import annotate_checks
    annotate_checks(e)
    if actual_transverse(case):
        from .lrfd_checks import apply_actual_checks
        apply_actual_checks(e)
    e.max_dc=max(c.ratio for c in checks if isinstance(c.ratio,(float,int)))
    e.issues=(layout['issues'] if layout else [])+cage_issues(e)+transverse_issues(e);e.weight_lb=estimate_weight(e)
    failure=any('FAIL' in c.status for c in checks)
    e.eligible=sectional_checks_pass(e) and not stale
    if stale:e.status='REIMPORT FORCES — changed analysis geometry: '+', '.join(stale)
    elif not case['inputs']['Ready_pile']:e.status='PILE-HEAD DETAIL INPUTS PENDING'
    elif failure:e.status='CHECK FAILURES — revise the trial cage or section'
    elif e.issues:e.status='DETAILING SCREEN — review the drawn cage'
    else:e.status=eng.get('Status_overall')+' · ANCHORAGE / DETAILING PENDING'
    if actual_transverse(case):
        e.eligible=False
        if not stale and not failure and not e.issues:e.status='ACTUAL CAGE · LRFD CALCULATIONS / DETAIL REVIEW PENDING'
    return e

def formula_trace(e):
    fitted=e.longitudinal_layout['values'] if e.longitudinal_layout else {}
    fitted={**fitted,**(e.spacing_values or {})}
    trace=[{'name':d['name'],'formula':(d['name']+' = actual longitudinal layout (in)' if d['name'] in fitted else d['formula']),
             'value':e.engine.text(e.engine.get(d['name']),d['unit'],5),
             'note':('Maximum adjacent spacing in the displayed continuous-plus-added span row. '+d['caption'] if d['name'] in (e.spacing_values or {}) else
                 'Derived from the displayed bar coordinates fitted to actual hoop/U geometry; replaces the reference cover/pitch expression. '+d['caption'] if d['name'] in fitted else d['caption'])}
            for d in DEFINITIONS if '(' not in d['name']]
    if e.lrfd:
        from .lrfd_checks import REPLACED_PREFIXES,REPLACED_KEYS
        actual={c.key:c for c in e.checks}
        for row in trace:
            name=row['name']
            if name in actual and (name.startswith(REPLACED_PREFIXES) or name in REPLACED_KEYS):
                c=actual[name];row.update(formula=c.basis,value=c.status+'; D/C = '+str(c.ratio),note='Active actual-cage LRFD check; full operands in lrfd_calculations.json and the LRFD tab.')
            else:row['note']='Inherited sectional equation archive; actual-cage shear/torsion/development working is in lrfd_calculations.json. '+row['note']
    return trace


def side_reinforcement(e):
    """Explain side steel using the existing equations, without changing gates.

    The depth-triggered skin check is separate from shrinkage/temperature and
    longitudinal tension. A zero-side counterfactual keeps all other inputs.
    Its failures explain this cage, not every possible reinforcement layout.
    """
    without=e if e.case['inputs']['n_skin']==0 else evaluate(set_inputs(e.case,n_skin=0),fast=True)
    keys={'Chk_skin_area','Chk_skin_space','Chk_shrink_area','Chk_shrink_space',
          'Chk_long_N','Chk_long_P','Chk_long_B'}
    return {'depth_required':bool(e.value('Skin_required')),
            'zero_side_failures':[c for c in without.checks if c.key in keys and 'FAIL' in c.status]}
