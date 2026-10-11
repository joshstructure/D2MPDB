"""Algebraic controlling stations for the constant-angle, no-torsion branch.

Between force, bar-development and transverse-window boundaries, M is quadratic,
V/N and developed As are linear, and theta=45 degrees. Longitudinal utilization
is therefore a piecewise quadratic divided by a linear polynomial. Its interior
extrema are the real roots of D' C - D C'. Other utilizations are linear or
constant. The formulas here are constructed from the source and bar geometry;
they are not polynomial fits. Unsupported branches return None so the existing
convergence-controlled search remains authoritative there.
"""
import math
from numpy.polynomial import Polynomial as P

FIELDS=('ratio','shear_ratio','minimum_ratio','torsion_ratio','inverse_resistance')


def _roots(poly,lo,hi):
    # Only roundoff in a cancelled leading coefficient is removed.
    coeff=list(poly.coef)
    while len(coeff)>1 and abs(coeff[-1])<1e-14*max(1.,max(abs(c) for c in coeff)):
        coeff.pop()
    if len(coeff)<2:return []
    return [float(z.real) for z in P(coeff).roots()
            if abs(z.imag)<1e-8 and lo<float(z.real)<hi]


def _area(inventory,origin,mid,h,face,*,main=False):
    """Exact linear As on a piece bounded by every development transition."""
    area=P([0.])
    for b in inventory:
        if main and (b['additional'] or b['kind']=='Skin'):continue
        if not b['straight_left_in']<=mid<=b['straight_right_in']:continue
        side=b['y']-h/2
        if (face=='top' and side<-1e-8) or (face=='bottom' and side>1e-8):continue
        ld=b['required_in'];weight=.5 if abs(side)<1e-8 else 1.
        branches=(P([1.]),P([(origin-b['left_in'])/ld,1/ld]),
                  P([(b['right_in']-origin)/ld,-1/ld]))
        factor=min(branches,key=lambda q:q(mid-origin))
        if factor(mid-origin)>0:area+=weight*b['area']*factor
    return area


def algebraic_search(e,m,left,right,inventory,physical,dev,rate,region,evaluate):
    """Return actual section results at algebraic candidates, or None.

    Eligibility is established over the interval: N is linear; T squared minus
    the investigation threshold squared is convex for N <= numerical zero, so
    its maximum is at an endpoint. Every 45-degree window change is a boundary.
    The existing evaluator independently confirms each resulting smooth piece.
    """
    from .axial import NUMERICAL_ZERO_KIP
    from .lrfd_checks import forces,torsion_threshold,window_steel,settings
    p=e.case['inputs'];dv=e.value('dv');s=settings(e.case)
    ends=[forces(m,x) for x in (left,right)]
    if p['fpc']!=0 or any(q['nu']>NUMERICAL_ZERO_KIP or q['tu']>torsion_threshold(e,q['nu']) for q in ends):return None
    origin=left;t=P([(origin-m['left'])/m['length'],1/m['length']])
    ma=.5*(m['vj']-m['vi'])*m['length']/12
    moment=P([m['mi']])+(m['mj']-m['mi']-ma)*t+ma*t*t
    shear=P([m['vi']])+(m['vj']-m['vi'])*t
    axial=P([m.get('ni',m['nu'])])+(m.get('nj',m['nu'])-m.get('ni',m['nu']))*t
    cuts={left,right}
    for q in (moment,shear):cuts.update(origin+x for x in _roots(q,0.,right-left))
    for b in inventory:
        cuts.update(x for x in (b['straight_left_in'],b['straight_right_in'],
            b['left_in'],b['right_in'],b['left_in']+b['required_in'],
            b['right_in']-b['required_in'],(b['left_in']+b['right_in'])/2) if left<x<right)
    cuts.update(b['station_in']+sign*dv/2 for b in physical for sign in (-1,1)
                if left<b['station_in']+sign*dv/2<right)
    cuts=sorted(cuts)
    minimum=.0316*s['density_factor']*math.sqrt(p['fc'])*p['b']/min(p['fy'],100.)
    # Certify the entire fixed-window branch before doing section evaluations.
    # A general-procedure interval goes straight to the established fallback.
    if p['h']>=16 and any(min(rate,window_steel(physical,(a+b)/2,(a+b)/2,dv)['area_in2']/dv)+1e-12<minimum
                         for a,b in zip(cuts,cuts[1:]) if b-a>=1e-10):return None
    cache={};candidates={};piece_count=0
    def at(x):
        if x not in cache:cache[x]=evaluate(x)
        return cache[x]
    def keep(x,reason):
        x=float(max(left,min(right,x)));at(x)
        candidates.setdefault(x,set()).add(reason)
    def boundary(x,a,b,reason):
        keep(x,reason)
        if x>a:keep(x-min(2e-6,(x-a)/4),'before '+reason)
        if x<b:keep(x+min(2e-6,(b-x)/4),'after '+reason)
    for i,x in enumerate(cuts):
        boundary(x,cuts[i-1] if i else x,cuts[i+1] if i+1<len(cuts) else x,'physical / force boundary')
    for a,b in zip(cuts,cuts[1:]):
        if b-a<1e-10:continue
        mid=(a+b)/2;q=at(mid)
        # A fixed 45-degree window has constant area on this open piece.
        if q['method']!='5.7.3.4.1' or q['torsion_required']:return None
        face='top' if moment(mid-origin)<0 else 'bottom'
        area=_area(inventory,origin,mid,p['h'],face)
        main=_area(inventory,origin,mid,p['h'],face,main=True)
        abs_m=moment*(-1 if face=='top' else 1)
        abs_v=shear*(-1 if shear(mid-origin)<0 else 1)
        developed=window_steel(physical,mid,mid,dv,dev)['area_in2']*min(p['fy'],100.)
        cap=region['peak_moment_kip_ft']*12/(p['phi_f']*dv) if region and region['qualifies'] else None
        subcuts={a,b}
        polys=[abs_v/p['phi_v']-developed,area*p['fy']-1e-9]
        if cap is not None:polys.append(main*p['fy']-cap)
        for poly in polys:subcuts.update(origin+x for x in _roots(poly,a-origin,b-origin))
        subcuts=sorted(subcuts)
        for u,v in zip(subcuts,subcuts[1:]):
            z=(u+v)/2-origin
            diagonal=abs_v/(2*p['phi_v']) if abs_v(z)/p['phi_v']<=developed else abs_v/p['phi_v']-.5*developed
            full=abs_m*12/(p['phi_f']*dv)+.5*axial/s['phi_axial']+diagonal
            active_cap=cap if cap is not None and main(z)*p['fy']+1e-8>=cap else None
            changes={u,v,*(origin+x for x in _roots(full,u-origin,v-origin))}
            if active_cap is not None:changes.update(origin+x for x in _roots(full-active_cap,u-origin,v-origin))
            changes=sorted(changes)
            for x in changes:boundary(x,a,b,'demand / capacity branch')
            for u1,v1 in zip(changes,changes[1:]):
                z1=(u1+v1)/2-origin
                demand=P([0.]) if full(z1)<0 else P([active_cap]) if active_cap is not None and full(z1)>active_cap else full
                capacity=area*p['fy'] if area(z1)*p['fy']>1e-9 else P([1e-9])
                derivative=demand.deriv()*capacity-demand*capacity.deriv()
                for x in _roots(derivative,u1-origin,v1-origin):keep(origin+x,'stationary longitudinal D/C')
                # Check independently constructed formulas against the actual
                # evaluator at interior points. Any disagreement uses fallback.
                for fraction in (.38196601125,.61803398875):
                    x=u1+(v1-u1)*fraction;r=at(x);z2=x-origin
                    predicted=demand(z2)/capacity(z2)
                    if (r['method']!='5.7.3.4.1' or r['torsion_required'] or
                        not math.isclose(predicted,r['ratio'],rel_tol=1e-9,abs_tol=1e-9) or
                        not math.isclose(area(z2),r['steel_area_in2'],rel_tol=1e-10,abs_tol=1e-10)):
                        return None
                piece_count+=1
    for field in FIELDS:keep(max(cache,key=lambda x:cache[x][field]),'controls '+field)
    meta=dict(method='algebraic critical locations',converged=True,samples=len(cache),
        retained_stations=len(candidates),refinements=0,smooth_pieces=piece_count,
        event_count=max(0,len(cuts)-2),event_tolerance_in=1e-6,
        basis='Exact quadratic/linear demand and developed-area polynomials; roots of D\u2032C - DC\u2032; actual section values at boundaries and roots')
    return [dict(at(x),search=meta,station_reason='; '.join(sorted(candidates[x]))) for x in sorted(candidates)],meta
