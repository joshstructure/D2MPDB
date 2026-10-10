"""Event roots and numerical stationary points for concurrent section checks.

Small Chebyshev interpolants locate roots; independent interlaced nodes and
actual calculations at derivative roots validate each smooth piece. Failed
models subdivide locally, without a length-based station grid. Discontinuities
are split first using signed margins, window edges and independent signatures.
Every reported value is an actual section evaluation. Numerical convergence
is not a rigorous bound for arbitrary black-box functions; the supported source
uses quadratic moment, linear other actions and piecewise-linear developed As.
"""
import math
import numpy as np
from numpy.polynomial import chebyshev as C

FIELDS=('ratio','shear_ratio','minimum_ratio','torsion_ratio','inverse_resistance',
        'av_required_rate','combined_required_rate','epsilon')
TS=np.cos(np.arange(9)*math.pi/8)[::-1]
FIT=np.linalg.inv(C.chebvander(TS[::2],4))
VALIDATE=C.chebvander(TS[1::2],4)
EVENT_TOL=1e-6


def _roots(coeff):
    coeff=C.chebtrim(coeff,tol=1e-12*max(1.,float(np.max(np.abs(coeff)))))
    if len(coeff)<2:return []
    return [float(z.real) for z in C.chebroots(coeff)
            if abs(z.imag)<1e-8 and -1.<z.real<1.]


class SearchLimit(Exception):
    pass


def numerical_search(evaluate,left,right,physical,*,tolerance=2e-4,max_levels=7,max_samples=2048):
    from .section_search import signature
    if not right>left:raise ValueError('Critical-location interval must have positive length')
    if max_samples<2:raise ValueError('Critical-location budget must allow both endpoints')
    cache={};vectors={};retained={};events=set();failures=[]
    deepest=0;pieces=0;worst_error=0.;event_passes=0

    def at(x):
        x=float(max(left,min(right,x)))
        if x not in cache:
            if len(cache)>=max_samples:raise SearchLimit('Critical-location evaluation budget exhausted')
            cache[x]=evaluate(x)
            row=cache[x]
            if not all(math.isfinite(row.get(f) or 0.) for f in FIELDS):
                raise SearchLimit('Nonfinite section calculation')
        return cache[x]

    def mark(x,why):
        x=float(max(left,min(right,x)));at(x)
        retained.setdefault(x,set()).add(why)

    def vector(x):
        if x not in vectors:
            r=at(x);half=r['general_window_length_in']/2
            vectors[x]={**r.get('search_margins',{}),
                        'window:left':x-half,'window:right':x+half}
        return vectors[x]

    def root(a,b,key,target):
        # Safeguarded secant on actual margins, not the polynomial surrogate.
        fa=vector(a)[key]-target;fb=vector(b)[key]-target
        if fa==0:return a
        if fb==0:return b
        for iteration in range(64):
            if b-a<1e-10:break
            x=(a*fb-b*fa)/(fb-fa) if fb!=fa else (a+b)/2
            if not a<x<b or iteration%5==4:x=(a+b)/2
            fx=vector(x)[key]-target
            if fx==0:return x
            # Certify a very accurate secant guess with actual opposite signs
            # within the event tolerance, rather than halving a long bracket.
            if abs(fx)<1e-9:
                da=max(a,x-1e-9);db=min(b,x+1e-9)
                if (vector(da)[key]-target)*(vector(db)[key]-target)<=0:return x
            if (fa<0)==(fx<0):a,fa=x,fx
            else:b,fb=x,fx
        if b-a>EVENT_TOL:raise SearchLimit('Critical-location root did not converge')
        return (a+b)/2

    def branch_root(a,b):
        initial=signature(at(a))
        for _ in range(64):
            if b-a<1e-10:break
            mid=(a+b)/2
            if signature(at(mid))==initial:a=mid
            else:b=mid
        return (a+b)/2

    def split(lo,hi,locations,depth):
        nonlocal event_passes
        merged=[]
        for x in sorted(locations):
            if lo+2*EVENT_TOL<x<hi-2*EVENT_TOL and (not merged or x-merged[-1]>1e-8):merged.append(x)
        if not merged:return False
        event_passes+=1
        if event_passes>128:raise SearchLimit('Critical-location transition budget exhausted')
        start=lo
        for i,x in enumerate(merged):
            gap=min(x-start,(merged[i+1] if i+1<len(merged) else hi)-x)
            eps=min(2*EVENT_TOL,gap/4)
            a,b=x-eps,x+eps;events.add(x)
            mark(a,'before transition');mark(x,'transition');mark(b,'after transition')
            if a>start:solve(start,a,depth)
            start=b
        if start<hi:solve(start,hi,depth)
        return True

    def solve(lo,hi,depth):
        nonlocal deepest,pieces,worst_error
        deepest=max(deepest,depth)
        mid=(lo+hi)/2;half=(hi-lo)/2
        # Five model nodes plus four independent validation nodes. Their
        # count depends on smoothness, not on the segment's length in inches.
        xs=[float(mid+half*t) for t in TS]
        rows=[at(x) for x in xs]
        keys=sorted(set.intersection(*(set(vector(x)) for x in xs)))
        values=np.array([[vector(x)[k] for k in keys] for x in xs])
        objective=np.array([[r.get(f) or 0. for f in FIELDS] for r in rows])
        if not np.all(np.isfinite(values)) or not np.all(np.isfinite(objective)):
            raise SearchLimit('Nonfinite section calculation')
        ecoef=FIT@values[::2];ocoef=FIT@objective[::2]
        event_errors=np.max(np.abs(VALIDATE@ecoef-values[1::2]),axis=0)
        candidates=set()
        for k,key in enumerate(keys):
            coef=ecoef[:,k]
            # Match window_steel's strict 1e-8-in edge exclusion, including
            # shallow/tangent crossings where it changes x by more than 1e-6.
            targets=[b['station_in']+(-1e-8 if key=='window:left' else 1e-8)
                     for b in physical] if key.startswith('window:') else [0.]
            # |T_k(t)| <= 1 over the model interval: discard unreachable
            # thresholds without solving a derivative polynomial for every
            # inactive layer margin. Independent error checks still apply.
            radius=sum(abs(c) for c in coef[1:])+event_errors[k]+1e-10
            targets=[t for t in targets if abs(t-coef[0])<=radius]
            if not targets:continue
            extrema=_roots(C.chebder(coef))
            bounds=C.chebval([-1.,1.,*extrema],coef)
            for target in targets:
                if target<min(bounds)-event_errors[k]-1e-10 or target>max(bounds)+event_errors[k]+1e-10:continue
                if max(abs(v-target) for v in values[:,k])<1e-12:continue
                shifted=coef.copy();shifted[0]-=target;guesses=_roots(shifted)
                # Extrema expose two crossings inside a bracket even if the
                # original node classifications agree at its two ends.
                probes=sorted({*xs,*(float(mid+half*t) for t in guesses+extrema)})
                vals=[vector(x).get(key,math.nan)-target for x in probes]
                for a,b,fa,fb in zip(probes,probes[1:],vals,vals[1:]):
                    if fa*fb<0:candidates.add(root(a,b,key,target))
                for t in guesses:
                    x=float(mid+half*t)
                    if abs(vector(x).get(key,math.inf)-target)<1e-10:candidates.add(x)
        # Independent classification checks catch unmodeled branch changes.
        for a,b,ra,rb in zip(xs,xs[1:],rows,rows[1:]):
            if signature(ra)!=signature(rb) and not any(a<=x<=b for x in candidates):
                candidates.add(branch_root(a,b))
        if split(lo,hi,candidates,depth):return
        event_scale=np.maximum(1.,np.max(np.abs(values),axis=0))
        out_scale=np.maximum(1.,np.max(np.abs(objective),axis=0))
        err_events=float(np.max(event_errors/event_scale))
        err=float(np.max(np.abs(VALIDATE@ocoef-objective[1::2])/out_scale))
        stable=len({signature(r) for r in rows})==1
        for k,field in enumerate(FIELDS):
            for t in _roots(C.chebder(ocoef[:,k])):
                x=float(mid+half*t);r=at(x)
                err=max(err,abs((r.get(field) or 0.)-C.chebval(t,ocoef[:,k]))/out_scale[k])
                stable=stable and signature(r)==signature(rows[0])
        good=stable and max(err,err_events)<=tolerance/4 and max_levels>=2
        if good:
            pieces+=1;worst_error=max(worst_error,err);return
        if depth+1>=max_levels or hi-lo<4*EVENT_TOL:
            failures.append((lo,hi,'Critical-location model did not converge'));return
        solve(lo,mid,depth+1);solve(mid,hi,depth+1)

    try:
        mark(left,'interval start');mark(right,'interval end')
        eps=min(2*EVENT_TOL,(right-left)/8);lo,hi=left+eps,right-eps
        mark(lo,'inside interval start');mark(hi,'inside interval end')
        middle=at((left+right)/2);dv=middle['dv_in']
        fixed={b['station_in']+sign*dv/2 for b in physical for sign in (-1,1)
               if lo+2*EVENT_TOL<b['station_in']+sign*dv/2<hi-2*EVENT_TOL
               and min(at(left)['nu'],at(right)['nu'])<=1e-10}
        if not split(lo,hi,fixed,0):solve(lo,hi,0)
    except SearchLimit as exc:failures.append((left,right,str(exc)))
    for field in FIELDS:
        x=max(cache,key=lambda x:cache[x].get(field) or 0.)
        retained.setdefault(x,set()).add('controls '+field)
    branches={signature(cache[x]):x for x in retained}
    for x,r in cache.items():branches.setdefault(signature(r),x)
    for x in branches.values():retained.setdefault(x,set()).add('branch representative')
    meta=dict(method='numerical critical locations',converged=not failures,samples=len(cache),
        retained_stations=len(retained),refinements=deepest,smooth_pieces=pieces,
        relative_dc_tolerance=tolerance,max_model_error=worst_error,
        event_tolerance_in=EVENT_TOL,event_count=len(events),unresolved_intervals=failures)
    return [dict(cache[x],search=meta,station_reason='; '.join(sorted(retained[x])))
            for x in sorted(retained)],meta
