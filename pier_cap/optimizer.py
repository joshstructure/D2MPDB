"""Deterministic bounded enumeration. No model, AI service or network calls."""
from dataclasses import dataclass, asdict
from collections import Counter
from itertools import product
from time import perf_counter
from copy import deepcopy
import math
import random
from .model import evaluate, set_inputs, analysis_match, validate_case, sectional_checks_pass, upgrade_case

DC_SCOPES={'all':'All available checks','strength':'Strength checks only'}
OBJECTIVES=('Least steel','Simplest cage','Largest margin')

# Editing a live trial cage does not erase a completed search. Those results
# retain their original reinforcement and spacing assumptions; applying a
# candidate restores its entire saved case. All other design inputs must match.
REINFORCEMENT_INPUTS={
    'Bar_N1','Bar_N2','Bar_N3','Bar_P','Bar_B','Bar_U','Bar_v','Bar_skin',
    'n_N1','n_N2','n_N3','n_P1','n_P2','n_PU','n_B1','n_B2','n_BU','n_loop','n_skin',
    's_row','s_G','s_L','Manual_spacing','SP_detail_N','SP_detail_P','SP_detail_B',
    'SP_detail_skin','S_leg_detail',
}


def same_design_basis(a,b):
    """True when only the live reinforcement (or descriptive metadata) differs.

    This permits browsing the completed search, not reusing its metrics for the
    edited cage. Loads, analysis provenance, geometry, materials, readiness and
    the clear-spacing screen remain part of the comparison.
    """
    def basis(case):
        case=upgrade_case(case)
        return ({k:v for k,v in case['inputs'].items() if k not in REINFORCEMENT_INPUTS},
                case['analysis'],case['screening'],case['units'],case['schema_version'],case.get('transverse_detail'),case.get('added_bar_layout'))
    return basis(a)==basis(b)


def bounded_layouts(grids, limit):
    """Enumerate a complete grid, or sample its full extent reproducibly.

    A truncated Cartesian prefix can spend the entire budget on small main
    bars. Sampling without replacement gives the other choices a chance too.
    This remains a bounded search, not a guarantee of an optimum.
    """
    total=math.prod(len(g) for g in grids)
    if total <= limit:
        yield from product(*grids)
        return
    for ordinal in random.Random(0).sample(range(total),limit):
        values=[]
        for grid in reversed(grids):
            ordinal,index=divmod(ordinal,len(grid))
            values.append(grid[index])
        yield tuple(reversed(values))
STRENGTH_CHECKS={*(f'Chk_flex_{z}' for z in 'NPB'),*(f'Chk_shear_{z}' for z in 'GL'),
    *(f'Chk_torsteel_{z}' for z in 'GL'),*(f'Chk_long_{z}' for z in 'NPB')}

@dataclass(frozen=True)
class SearchConfig:
    main_bars:tuple=(6,7,8,9)
    top_counts:tuple=(4,6,8)
    bottom_counts:tuple=(4,6,8)
    hoop_bars:tuple=(4,5,6)
    hoop_spacings:tuple=(6,8,10)
    skin_bars:tuple=(4,5)
    skin_counts:tuple=tuple(range(8))
    objective:str='Least steel'
    max_cases:int=10000
    # The common-cage API means continuous bottom steel with zero added bars.
    # The notebook supplies independent domains; span_counts are ADDITIONAL.
    pile_bars:tuple=None
    span_bars:tuple=None
    pile_counts:tuple=None
    span_counts:tuple=None


def layout_grids(c):
    common_counts=(None,) if c.pile_counts is not None and c.span_counts is not None else c.bottom_counts
    independent=tuple((None,) if values is None else values for values in
                      (c.pile_bars,c.span_bars,c.pile_counts,c.span_counts))
    # A zero-side cage is identical for every unused side-bar size. Evaluate it
    # once, so extra size choices do not consume the bounded search budget.
    sides=tuple((bar,n) for bar in c.skin_bars for n in c.skin_counts
                if n or bar==c.skin_bars[0])
    return (c.main_bars,c.top_counts,common_counts,c.hoop_bars,c.hoop_spacings,sides,*independent)


def cage_complexity(changes):
    sizes={changes[key] for key in ('Bar_N1','Bar_P','Bar_v')}
    if changes['n_B1']:sizes.add(changes['Bar_B'])
    if changes['n_skin']:sizes.add(changes['Bar_skin'])
    return int(changes['n_N1']+(changes['n_P1']+changes['n_B1'])
               +2*changes['n_skin']+5*len(sizes))

@dataclass
class Candidate:
    changes:dict
    weight_lb:float
    max_dc:float
    complexity:int
    label:str
    strength_dc:float
    governing_check:str
    strength_governing_check:str
    governing_component:str=''
    strength_governing_component:str=''

@dataclass
class SearchResult:
    config:dict
    base_case:dict
    candidates:list
    total:int
    evaluated:int
    passed:int
    rejection_counts:dict
    elapsed:float
    exhaustive:bool
    force_mode:str='matched'

def candidate_dc(candidate,scope='all'):
    if scope not in DC_SCOPES:raise ValueError('Unknown D/C scope.')
    return candidate.max_dc if scope=='all' else candidate.strength_dc

def candidate_governing(candidate,scope='all'):
    if scope not in DC_SCOPES:raise ValueError('Unknown D/C scope.')
    label=candidate.governing_check if scope=='all' else candidate.strength_governing_check
    detail=candidate.governing_component if scope=='all' else candidate.strength_governing_component
    return label+(' — '+detail if detail else '')

def _rank_key(candidate,objective,scope='all'):
    dc=candidate_dc(candidate,scope)
    if objective=='Least steel':return (candidate.weight_lb,candidate.complexity,dc)
    if objective=='Simplest cage':return (candidate.complexity,candidate.weight_lb,dc)
    if objective=='Largest margin':return (dc,candidate.weight_lb,candidate.complexity)
    raise ValueError('Unknown search objective.')

def filter_candidates(result,max_dc=1.0,scope='all',objective=None):
    """Return stable zero-based candidate IDs; filter/rank without a new search.

    The complete passing population remains in result.candidates. The strength
    scope covers flexure, shear, combined shear/torsion steel and longitudinal
    steel only; every other available check must still pass for every candidate.
    """
    if isinstance(max_dc,bool) or not isinstance(max_dc,(float,int)) or not math.isfinite(max_dc) or not 0<max_dc<=1:
        raise ValueError('Maximum D/C must be a finite number greater than 0 and at most 1.')
    if scope not in DC_SCOPES:raise ValueError('Unknown D/C scope.')
    objective=objective or result.config['objective']
    if objective not in OBJECTIVES:raise ValueError('Unknown search objective.')
    indices=[i for i,c in enumerate(result.candidates) if candidate_dc(c,scope)<=max_dc+1e-12]
    return sorted(indices,key=lambda i:_rank_key(result.candidates[i],objective,scope))

def _governing(e,keys=None):
    return max((ch for ch in e.checks if isinstance(ch.ratio,(int,float)) and (keys is None or ch.key in keys)),key=lambda ch:ch.ratio)

def governing_check(e,scope='all'):
    """Report the same controlling check used by the candidate filter."""
    if scope not in DC_SCOPES:raise ValueError('Unknown D/C scope.')
    keys=STRENGTH_CHECKS|{c.key for c in e.checks if c.key.startswith('Chk_actual_shear_')}
    return _governing(e,keys if scope=='strength' else None)

def search(case,config=None,progress=None):
    return _search(case,config,progress,section_sensitivity=False)

def sensitivity_search(case,config=None,progress=None):
    """Explicit fixed-force b/h study. Never changes the source analysis record.

    A retained cage satisfies sectional screens, but may remain ineligible for
    design because its changed section has not been analyzed.
    """
    return _search(case,config,progress,section_sensitivity=True)

def _search(case,config,progress,section_sensitivity):
    c=config or SearchConfig();case=upgrade_case(case);validate_case(case)
    if case.get('transverse_detail',{}).get('enabled'):
        raise ValueError('Steel search generates uniform closed-hoop cages. Disable the actual transverse layout to search a reference cage; your entered runs remain saved. Re-enable and review those runs afterward.')
    if not case['inputs']['Ready_pile']:
        raise ValueError('Confirm pile-head embedment and bar clearance under Geometry → Pile head before searching.')
    stale=analysis_match(case)
    if stale and (not section_sensitivity or set(stale)-{'b','h'}):
        raise ValueError('Geometry has changed. Import a matching analysis case before searching steel. Fixed-force section studies allow only width/depth differences.')
    def accepted(e):return sectional_checks_pass(e) if section_sensitivity else e.eligible
    if c.objective not in OBJECTIVES:raise ValueError('Unknown search objective.')
    if not isinstance(c.max_cases,int) or not 1<=c.max_cases<=100000:raise ValueError('Search limit must be 1–100,000 cases.')
    grids=layout_grids(c)
    if any(not g for g in grids):raise ValueError('Select at least one value in every search list.')
    total=1
    for g in grids:total*=len(g)
    # The saved force audit is immutable provenance, not a calculation input.
    # Avoid copying hundreds of XML records twice per trial cage.
    trial_base=deepcopy(case)
    for key in ('xml_audit','workbook_audit'):
        trial_base['analysis'].pop(key,None)
    start=perf_counter();good=[];rejected=Counter();count=0
    for bar,top,bottom,hoop,spacing,side,pbar,bbar,pcount,bcount in bounded_layouts(grids,c.max_cases):
        count+=1
        skin,nskin=side
        pbar=bar if pbar is None else pbar;bbar=bar if bbar is None else bbar
        pcount=bottom if pcount is None else pcount;bcount=0 if bcount is None else bcount
        changes={'Bar_N1':bar,'Bar_N2':bar,'Bar_N3':bar,'Bar_P':pbar,'Bar_B':bbar,
            'n_N1':top,'n_N2':0,'n_N3':0,'n_P1':pcount,'n_B1':bcount,'n_P2':0,'n_B2':0,
            'n_PU':0,'n_BU':0,'Bar_v':hoop,'n_loop':1,'s_G':spacing,'s_L':spacing,
            'Bar_skin':skin,'n_skin':nskin,'Manual_spacing':False}
        try:
            e=evaluate(set_inputs(trial_base,**changes),fast=True)
            if accepted(e):
                complexity=cage_complexity(changes)
                side_label=f'{nskin} #{skin}/side' if nskin else 'no side bars'
                label=f'{top} #{bar} top / pile continuous {pcount} #{pbar} / between +{bcount} #{bbar} · #{hoop} @ {spacing:g} in · {side_label}'
                overall=_governing(e);strength=_governing(e,STRENGTH_CHECKS)
                good.append(Candidate(changes,e.weight_lb,e.max_dc,complexity,label,strength.ratio,overall.label,strength.label,
                    overall.governing,strength.governing))
            else:
                for ch in e.checks:
                    if 'FAIL' in ch.status:rejected[ch.label]+=1
                if e.issues:rejected['Cage fit / unresolved topology']+=1
        except (ValueError,ZeroDivisionError,OverflowError) as exc:
            # A malformed configuration is a rejected candidate, never a hidden pass.
            rejected['Invalid calculation / input']+=1
        if progress and (count%100==0 or count==min(total,c.max_cases)):progress(count,min(total,c.max_cases))
    good.sort(key=lambda candidate:_rank_key(candidate,c.objective))
    # Retain and unit-check every passing candidate; paging is presentation only.
    for candidate in good:
        checked=evaluate(set_inputs(case,**candidate.changes))
        if not accepted(checked):raise RuntimeError('Scalar candidate failed the unit-aware recheck.')
        if abs(candidate.max_dc-checked.max_dc)>1e-9 or abs(candidate.strength_dc-_governing(checked,STRENGTH_CHECKS).ratio)>1e-9:
            raise RuntimeError('Scalar and unit-aware D/C results differ.')
    return SearchResult(asdict(c),deepcopy(case),good,total,count,len(good),dict(rejected),perf_counter()-start,count==total,'fixed' if section_sensitivity else 'matched')

def candidate_case(result,index=0):
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(result.candidates):raise IndexError('Candidate ID is outside this search.')
    return set_inputs(result.base_case,**result.candidates[index].changes)
