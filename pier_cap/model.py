"""Case validation, C005 calculations, D/C register and explicit cage screens."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import json
import math
from .engine import Engine, ScalarEngine, Q, parse

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
    return json.loads((DATA/'default_case.json').read_text(encoding='utf-8'))

def upgrade_case(case):
    """Copy saved common-bar inputs into the independent positive-region schema."""
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
    if case.get('schema_version')!=2:raise ValueError('Expected case schema_version 2; load older cases through load_case().')
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
    if p['N_pile']<2 or min(p['n_N1'],p['n_P1'],p['n_B1'])<2 or p['n_loop']<1:raise ValueError('At least two piles, two bars in each outer row and one loop are required.')
    if p['b']<=2*p['C_s']+2*BAR_DIAMETER[p['Bar_v']] or p['h']<=p['C_t']+p['C_b']+2*BAR_DIAMETER[p['Bar_v']]:raise ValueError('Cover and hoops do not fit inside the cap.')
    if p['Pile_embed']>p['h']:raise ValueError('Pile embedment exceeds the cap depth.')
    clearance=case.get('screening',{}).get('minimum_clear_in')
    if isinstance(clearance,bool) or not isinstance(clearance,(int,float)) or not math.isfinite(clearance) or clearance<0:raise ValueError('Screening clear spacing must be a finite nonnegative number.')
    analysis=case.get('analysis',{})
    if not isinstance(analysis.get('id'),str) or not analysis['id'].strip():raise ValueError('An analysis case ID is required.')
    g=analysis.get('geometry',{})
    if set(g)!=set(GEOMETRY) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in g.values()):raise ValueError('Analysis geometry must record all seven geometry inputs.')
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

    def value(self,name,unit=None):
        v=self.engine.get(name)
        if isinstance(v,Q):
            if unit:
                u=FORMULAS.eval(parse('1 '+unit),{});v.same(u)
                return v.v/u.v
            return v.v
        return v

def bar_positions(e,region='B'):
    """Actual row counts/diameters. U bars have no invented developed positions."""
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
        for x in xs:bars.append({'x':x,'y':y,'diameter':diam,'kind':label,'bar':int(size)})
    for k in (1,2,3):row(p[f'n_N{k}'],p[f'Bar_N{k}'],h-e.value(f'y_N{k}'),f'Top row {k}','SP_detail_N' if k==1 else None)
    for k in (1,2):
        y=e.value(f'y_{region}{k}');size=p[f'Bar_{region}']
        split=region=='P' and p['Ready_pile'] and y-BAR_DIAMETER[size]/2<p['Pile_embed']+p['C_pile']
        row(p[f'n_{region}{k}'],size,y,f'Bottom row {k}',f'SP_detail_{region}' if k==1 else None,split)
    n=int(p['n_skin']);diam=BAR_DIAMETER[p['Bar_skin']]
    bottom=e.value(f'y_{region}1');top=h-e.value('y_N1')
    pitch=e.value('SP_skin') if p['Manual_spacing'] else (top-bottom)/(n+1)
    mid=(top+bottom)/2
    for side in (p['C_s']+dv+diam/2,b-p['C_s']-dv-diam/2):
        for j in range(n):bars.append({'x':side,'y':mid+(j-(n-1)/2)*pitch,'diameter':diam,'kind':'Skin','bar':int(p['Bar_skin'])})
    return bars

def cage_issues(e):
    p=e.case['inputs'];issues=[];clear=e.case['screening']['minimum_clear_in'];dv=BAR_DIAMETER[p['Bar_v']]
    if not p['Ready_pile']:issues.append('Pile-head embedment and bar clearance are unconfirmed. Enter them under Geometry → Pile head before searching.')
    if p['n_PU'] or p['n_BU']:issues.append('U-leg positions/development are unresolved; drawn as an inventory only.')
    if p['n_loop']!=1:issues.append('Multiple-loop topology is unresolved; only the outer hoop is drawn.')
    for z in 'PB':
        bars=bar_positions(e,z)
        outside=any(v['x']-v['diameter']/2<p['C_s']+dv-1e-6 or v['x']+v['diameter']/2>p['b']-p['C_s']-dv+1e-6 or v['y']-v['diameter']/2<p['C_b']+dv-1e-6 or v['y']+v['diameter']/2>p['h']-p['C_t']-dv+1e-6 for v in bars)
        if outside:issues.append(f'{z} section: bars extend outside the clear interior of the hoop.')
        minimum=min((math.hypot(a['x']-b['x'],a['y']-b['y'])-(a['diameter']+b['diameter'])/2 for i,a in enumerate(bars) for b in bars[i+1:]),default=math.inf)
        if minimum+1e-8<clear:issues.append(f'{z} section: minimum drawn clear spacing {minimum:.2f} in < trial screen {clear:g} in.')
        if z=='P' and p['Ready_pile']:
            for bar in bars:
                dx=max(e.value('Pile_left')-bar['x'],0,bar['x']-e.value('Pile_right'))
                dy=max(-bar['y'],0,bar['y']-p['Pile_embed'])
                gap=math.hypot(dx,dy)-bar['diameter']/2
                if gap+1e-8<p['C_pile']:
                    issues.append('P section: a bar intersects the pile footprint or its required clearance, including placement tolerance.')
                    break
    return issues

def estimate_weight(e):
    # Equal-size positive cages share the larger count. Different sizes count
    # both full-length sets until regional cutoff lengths are supplied.
    # Gross lengths only: no hooks, laps, bends, anchorage, waste or regional cutoffs.
    p=e.case['inputs'];length=e.value('L_cap');dv=BAR_DIAMETER[p['Bar_v']]
    bottom=max(e.value('As_P'),e.value('As_B')) if p['Bar_P']==p['Bar_B'] else e.value('As_P')+e.value('As_B')
    longitudinal=(e.value('As_N')+bottom+2*e.value('As_side'))*length
    hoop_length=2*(p['b']-2*p['C_s']-dv+p['h']-p['C_t']-p['C_b']-dv)
    count=math.ceil(max(0,length-2*p['C_s'])/min(p['s_G'],p['s_L']))+1
    return (longitudinal+count*p['n_loop']*hoop_length*BAR_AREA[p['Bar_v']])*490/1728

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
    eng.all()
    checks=[]
    for key,s in SPEC.items():
        ratio=eng.eval(RATIOS[key],{}) if key in RATIOS else 'N/A'
        if isinstance(ratio,Q):
            if ratio.d!=(0,0,0):raise ValueError('D/C must be dimensionless: '+key)
            ratio=ratio.v
        if isinstance(ratio,(float,int)) and not math.isfinite(ratio):raise ValueError('Nonfinite D/C: '+key)
        checks.append(Check(key,s['label'],eng.get(key),ratio,s['basis']))
    e=Evaluation(case,eng,checks,[],stale,False,'',max((c.ratio for c in checks if isinstance(c.ratio,(float,int))),default=0),0)
    e.issues=cage_issues(e);e.weight_lb=estimate_weight(e)
    failure=any('FAIL' in c.status for c in checks)
    e.eligible=sectional_checks_pass(e) and not stale
    if stale:e.status='REIMPORT FORCES — changed analysis geometry: '+', '.join(stale)
    elif not case['inputs']['Ready_pile']:e.status='PILE-HEAD DETAIL INPUTS PENDING'
    elif failure:e.status='CHECK FAILURES — revise the trial cage or section'
    elif e.issues:e.status='DETAILING SCREEN — review the drawn cage'
    else:e.status=eng.get('Status_overall')
    return e

def formula_trace(e):
    return [{'name':d['name'],'formula':d['formula'],'value':e.engine.text(e.engine.get(d['name']),d['unit'],5),'note':d['caption']} for d in DEFINITIONS if '(' not in d['name']]


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
