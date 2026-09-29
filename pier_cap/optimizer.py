"""Deterministic bounded enumeration. No model, AI service or network calls."""
from dataclasses import dataclass, asdict
from collections import Counter
from itertools import product
from time import perf_counter
from .model import evaluate, set_inputs, analysis_match, validate_case

@dataclass(frozen=True)
class SearchConfig:
    main_bars:tuple=(6,7,8,9)
    top_counts:tuple=(4,6,8)
    bottom_counts:tuple=(4,6,8)
    hoop_bars:tuple=(4,5,6)
    hoop_spacings:tuple=(6,8,10)
    skin_bars:tuple=(4,5)
    skin_counts:tuple=(5,6,7)
    objective:str='Least steel'
    max_cases:int=10000
    keep:int=20

@dataclass
class Candidate:
    changes:dict
    weight_lb:float
    max_dc:float
    complexity:int
    label:str

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

def search(case,config=None,progress=None):
    c=config or SearchConfig();validate_case(case)
    if analysis_match(case):raise ValueError('Geometry has changed. Import a matching analysis case before searching steel.')
    if c.objective not in ('Least steel','Simplest cage','Largest margin'):raise ValueError('Unknown search objective.')
    if not isinstance(c.max_cases,int) or not 1<=c.max_cases<=100000:raise ValueError('Search limit must be 1–100,000 cases.')
    if not 1<=c.keep<=100:raise ValueError('Keep 1–100 candidates.')
    grids=(c.main_bars,c.top_counts,c.bottom_counts,c.hoop_bars,c.hoop_spacings,c.skin_bars,c.skin_counts)
    if any(not g for g in grids):raise ValueError('Select at least one value in every search list.')
    total=1
    for g in grids:total*=len(g)
    start=perf_counter();good=[];rejected=Counter();count=0
    for bar,top,bottom,hoop,spacing,skin,nskin in product(*grids):
        if count>=c.max_cases:break
        count+=1
        changes={'Bar_N1':bar,'Bar_N2':bar,'Bar_N3':bar,'Bar_pos':bar,
            'n_N1':top,'n_N2':0,'n_N3':0,'n_P1':bottom,'n_B1':bottom,'n_P2':0,'n_B2':0,
            'n_PU':0,'n_BU':0,'Bar_v':hoop,'n_loop':1,'s_G':spacing,'s_L':spacing,
            'Bar_skin':skin,'n_skin':nskin,'Manual_spacing':False}
        try:
            e=evaluate(set_inputs(case,**changes),fast=True)
            if e.eligible:
                complexity=int(top+bottom+2*nskin+len({bar,hoop,skin})*5)
                label=f'{top} #{bar} top / {bottom} #{bar} bottom · #{hoop} @ {spacing:g} in · {nskin} #{skin}/side'
                good.append(Candidate(changes,e.weight_lb,e.max_dc,complexity,label))
            else:
                for ch in e.checks:
                    if 'FAIL' in ch.status:rejected[ch.label]+=1
                if e.issues:rejected['Cage fit / unresolved topology']+=1
        except (ValueError,ZeroDivisionError,OverflowError) as exc:
            # A malformed configuration is a rejected candidate, never a hidden pass.
            rejected['Invalid calculation / input']+=1
        if progress and (count%100==0 or count==min(total,c.max_cases)):progress(count,min(total,c.max_cases))
    key={'Least steel':lambda r:(r.weight_lb,r.complexity,r.max_dc),
         'Simplest cage':lambda r:(r.complexity,r.weight_lb,r.max_dc),
         'Largest margin':lambda r:(r.max_dc,r.weight_lb,r.complexity)}[c.objective]
    good.sort(key=key)
    finalists=good[:c.keep]
    # Recheck every returned candidate with dimensions, including every D/C guard.
    for candidate in finalists:
        checked=evaluate(set_inputs(case,**candidate.changes))
        if not checked.eligible:raise RuntimeError('Scalar finalist failed the unit-aware recheck.')
        if abs(candidate.max_dc-checked.max_dc)>1e-9:raise RuntimeError('Scalar and unit-aware D/C results differ.')
    return SearchResult(asdict(c),case,finalists,total,count,len(good),dict(rejected),perf_counter()-start,count==total)

def candidate_case(result,index=0):
    return set_inputs(result.base_case,**result.candidates[index].changes)
