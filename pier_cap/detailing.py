"""Shared physical cage geometry and explicit detailing checks (inches).

Spacing basis: AASHTO LRFD 5.10.3.1.1 / 5.10.3.1.3. Project edition
and aggregate confirmation remain separate from numerical screening.
"""
import math
from collections import defaultdict


def required_clear(e, diameter, *, multilayer=False):
    s=e.case['screening']
    # Keep the user's larger construction minimum; it cannot waive code minima.
    code=max(1.,diameter) if multilayer else max(1.5,1.5*diameter,1.5*s['aggregate_in'])
    return max(s['minimum_clear_in'],code)


def row_spacing(e,bars,*,at_pile=False,edges=False):
    """Maximum spacing in available concrete, omitting an embedded-pile gap.

    Only rows interrupted by the known pile/placement/clearance envelope split.
    Above the head and between piles the complete row remains checked. Isolated
    bars use twice their strip-edge distances so missing side steel is visible.
    """
    p=e.case['inputs'];width=p['b'];intervals=[(0.,width)];excluded=None
    if (at_pile and bars and p['Ready_pile'] and p['Pile_embed']>0 and
            all(b['y']-b['diameter']/2<p['Pile_embed']+p['C_pile'] for b in bars)):
        left=max(0.,e.value('Pile_left')-p['C_pile'])
        right=min(width,e.value('Pile_right')+p['C_pile'])
        if left<right:
            excluded=(left,right)
            intervals=[(a,b) for a,b in ((0.,left),(right,width)) if b>a]
    pitches=[]
    for left,right in intervals:
        coords=sorted(b['x'] for b in bars if excluded is None or left<=b['x']<=right)
        pitches.extend(b-a for a,b in zip(coords,coords[1:]))
        if edges or excluded is not None and len(coords)<2:
            pitches.extend((2*(coords[0]-left),2*(right-coords[-1])) if coords else [right-left])
    return dict(pitch_in=max(pitches,default=0.),excluded_pile_interval_in=excluded,
        basis=('Pile embedment gap '+f'{excluded[0]:.3f}–{excluded[1]:.3f} in across the cap excluded; '
               'spacing checked separately in the concrete strips beside it.' if excluded else 'Full row spacing; no pile embedment gap excluded.'))


def spacing_records(e, region, bars):
    """Governing surface clearance per row pair; no center-distance shortcut."""
    rows=defaultdict(list)
    for bar in bars:
        # Mixed-size continuous and added bars share the same nominal bottom layer.
        rows[bar['layer']].append(bar)
    records=[]
    keys=list(rows)
    for i,ka in enumerate(keys):
        for kb in keys[i:]:
            aa=rows[ka];bb=rows[kb]
            vertical=ka!=kb and ka!='Skin' and kb!='Skin'
            pairs=[(a,b) for ia,a in enumerate(aa) for ib,b in enumerate(bb)
                   if ka!=kb or ib>ia]
            if not pairs:continue
            candidates=[]
            for a,b in pairs:
                # Vertical layer separation is checked vertically, not diagonally.
                distance=abs(a['y']-b['y']) if vertical else math.hypot(a['x']-b['x'],a['y']-b['y'])
                actual=distance-(a['diameter']+b['diameter'])/2
                required=required_clear(e,max(a['diameter'],b['diameter']),multilayer=vertical)
                ratio=required/max(actual,1e-6)
                candidates.append((ratio,actual,required,a,b))
            ratio,actual,required,a,b=max(candidates,key=lambda v:v[0])
            records.append(dict(region=region,label=ka if ka==kb else ka+' / '+kb,
                actual=actual,required=required,ratio=ratio,a=a,b=b,
                status='FAIL' if actual+1e-8<required else 'PASS',
                basis='Vertical layer clearance' if vertical else 'Parallel-bar surface clearance'))
    return records


def standard_hook(size, diameter):
    """90 degree general reinforcing hook, not a stirrup/tie hook."""
    inside=(6 if size<=8 else 8)*diameter
    return {'inside_diameter':inside,'radius':(inside+diameter)/2,'tail':12*diameter}


def hook_paths(e, bars):
    """Span supplements turn up before the pile exclusion envelope.

    A drawn standard bend does not establish development from a critical section.
    Coordinates are along-cap station / elevation; transverse x is retained.
    """
    p=e.case['inputs'];paths=[]
    centers=[e.value('E_CL')+j*p['S_pile']*12 for j in range(int(p['N_pile']))]
    for bar in bars:
        if not bar.get('additional'):continue
        d=bar['diameter'];hook=standard_hook(bar['bar'],d);r=hook['radius'];y=bar['y']
        # Placement tolerance and required pile gap apply along the cap as well.
        setback=p['D_pile']/2+e.value('Tol_pile')+p['C_pile']+d/2
        for j,(c0,c1) in enumerate(zip(centers,centers[1:]),1):
            left=c0+setback;right=c1-setback
            points=[(left,y+r+hook['tail']),(left,y+r)]
            for k in range(1,17):
                t=math.pi+k*math.pi/32
                points.append((left+r+r*math.cos(t),y+r+r*math.sin(t)))
            points.append((right-r,y))
            for k in range(1,17):
                t=-math.pi/2+k*math.pi/32
                points.append((right-r+r*math.cos(t),y+r+r*math.sin(t)))
            points.append((right,y+r+hook['tail']))
            paths.append(dict(bar=bar,span=j,points=points,left=left,right=right,
                straight=right-left-2*r,top=y+r+hook['tail'],**hook))
    return paths


def layer_alignment(bars):
    """Bars in nearby upper layers must lie above bars in the lower layer."""
    problems=[]
    for family in ('Top','Bottom'):
        layers=defaultdict(list)
        for b in bars:
            if b['layer'].startswith(family):layers[b['layer']].append(b)
        ordered=sorted(layers.values(),key=lambda row:min(b['y'] for b in row))
        for low,high in zip(ordered,ordered[1:]):
            gap=min(b['y']-b['diameter']/2 for b in high)-max(b['y']+b['diameter']/2 for b in low)
            if gap<=6+1e-8 and any(not any(abs(a['x']-b['x'])<1e-6 for a in low) for b in high):
                problems.append('Upper bars are not directly above lower bars where layer clearance is at most 6 in.')
    return problems
