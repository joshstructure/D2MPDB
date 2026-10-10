"""Equally spaced end bars; bump conflicts beside the fixed longitudinal cage."""
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
    """Nearest ordered positions, retaining every nonconflicting nominal bar.

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
    obstacles=[(bar['x'],bar['y'],bar['diameter'],True) for bar in bar_positions(e,'P')]
    obstacles += [(x,y,d,False) for x,y,d in other_returns]
    for x,y,d,main in obstacles:
        fixed,along=(x,y) if horizontal else (y,x)
        # Main bars run behind the entire U path. Its projection fills lo..hi,
        # so screen bends/crosspieces as well as the two straight hook tails.
        # A lapped main/return pair may touch; no parallel clear gap is imposed.
        required=(diameter+d)/2+(0. if main else required_clear(e,max(diameter,d))+.006)
        distances=[max(lo-fixed,fixed-hi,0.)] if main else [abs(leg-fixed) for leg in (lo,hi)]
        for distance in distances:
            if distance<required:
                half=math.sqrt(required**2-distance**2)
                spans=subtract(spans,along-half,along+half)
    separation=diameter+required_clear(e,diameter)+.006
    # Lock nominal positions that already fit. Only actual conflicts move.
    domains=[[(target,target)] if any(u<=target<=v for u,v in spans) else spans for target in nominal]
    def below(domain,limit):
        candidates=[min(v,limit) for u,v in domain if u<=limit]
        return max(candidates) if candidates else None
    # Reserve enough room for later bars before choosing each nearest position.
    upper=[];limit=b
    for domain in reversed(domains):
        at=below(domain,limit)
        if at is None:return nominal,False,'Requested bars cannot fit between longitudinal bars with the required clear spacing.'
        upper.append(at);limit=at-separation
    upper.reverse();positions=[];lower=a
    for target,limit,domain in zip(nominal,upper,domains):
        available=intersect(domain,[(lower,limit)])
        if not available:return nominal,False,'Requested bars cannot fit in the end stirrup.'
        at=min((max(u,min(v,target)) for u,v in available),key=lambda x:(abs(x-target),x))
        positions.append(at);lower=at+separation
    return positions,True,'Equal nominal spacing; only conflicting end bars move to the nearest available position beside a fixed longitudinal bar. Hook-tail contact / lap is allowed; physical overlap is not.'
