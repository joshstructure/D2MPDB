"""Align hooked end bars with the outer longitudinal surfaces and stagger tails."""
import math
from .placement import subtract,capsule_slice,intersect


def bounds(e,diameter):
    from .model import bar_positions
    bars=bar_positions(e,'P');r=diameter/2
    if not bars:raise ValueError('Aligned end bars need a longitudinal cage.')
    return (min(b['x']-b['diameter']/2 for b in bars)+r,
            max(b['x']+b['diameter']/2 for b in bars)-r,
            min(b['y']-b['diameter']/2 for b in bars)+r,
            max(b['y']+b['diameter']/2 for b in bars)-r)


def stagger(e,end,direction,diameter,lo,hi,a,b,nominal,other_returns=()):
    """Nearest ordered positions within exact 1D clearance intervals.

    Keep the longitudinal cage fixed. If the requested count cannot fit, retain
    the nominal trial and return a failure instead of omitting requested bars.
    """
    from .model import bar_positions
    from .transverse import scheduled_bars,bar_shape
    from .detailing import required_clear
    horizontal=direction=='horizontal'
    spans=[(a,b)]
    physical=scheduled_bars(e.case)
    near=(physical[0] if end=='left' else physical[-1]) if physical else None
    if near is None or near['kind']!='hoop':
        return nominal,False,'Alignment requires an actual closed end stirrup.'
    run=next(r for r in e.case['transverse_detail']['runs'] if r['id']==near['run'])
    shape=bar_shape(e,run)
    if not shape['fit']:return nominal,False,'End stirrup does not fit.'
    # Match surfaces, including rounded stirrup corners, not just centerlines.
    q=(shape['diameter']+diameter)/2+1e-5
    pts=shape['points']
    varying=1 if horizontal else 0
    spans=intersect(spans,[(min(p[varying] for p in pts)+q,max(p[varying] for p in pts)-q)])
    for fixed in (lo,hi):
        for u,v in zip(pts,pts[1:]):
            u,v=((u[1],u[0]),(v[1],v[0])) if horizontal else (u,v)
            cut=capsule_slice(u,v,fixed,q)
            if cut:spans=subtract(spans,*cut)
    obstacles=[(bar['x'],bar['y'],bar['diameter']) for bar in bar_positions(e,'P')]
    obstacles+=list(other_returns)
    for x,y,d in obstacles:
        fixed,along=(x,y) if horizontal else (y,x)
        # Leave room for the collision screen's 0.005-in chord allowance.
        required=(diameter+d)/2+required_clear(e,max(diameter,d))+.006
        for leg in (lo,hi):
            distance=abs(leg-fixed)
            if distance<required:
                half=math.sqrt(required**2-distance**2)
                spans=subtract(spans,along-half,along+half)
    separation=diameter+required_clear(e,diameter)+.006
    def below(limit):
        candidates=[min(v,limit) for u,v in spans if u<=limit]
        return max(candidates) if candidates else None
    # Reserve enough room for later bars before choosing each nearest position.
    upper=[];limit=b
    for _ in nominal:
        at=below(limit)
        if at is None:return nominal,False,'Requested bars cannot fit between longitudinal bars with the required clear spacing.'
        upper.append(at);limit=at-separation
    upper.reverse();positions=[];lower=a
    for target,limit in zip(nominal,upper):
        available=intersect(spans,[(lower,limit)])
        if not available:return nominal,False,'Requested bars cannot fit in the end stirrup.'
        at=min((max(u,min(v,target)) for u,v in available),key=lambda x:(abs(x-target),x))
        positions.append(at);lower=at+separation
    return positions,True,'Outside tail surfaces align with the longitudinal cage; crosspieces stagger to clear fixed longitudinal bars.'
