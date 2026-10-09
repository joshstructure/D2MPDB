"""Locate transverse runs in physical cap zones without changing their stations."""
from .model import BAR_DIAMETER


def cap_zones(e):
    p=e.case['inputs'];length=e.value('L_cap')
    half=p['D_pile']/2+e.value('Tol_pile')+p['C_pile']
    centers=[e.value('E_CL')+i*p['S_pile']*12 for i in range(int(p['N_pile']))]
    zones=[]
    def add(key,label,kind,left,right):
        zones.append(dict(key=key,label=label,kind=kind,left=max(0,left),right=min(length,right)))
    add('left','Left end','hoop',0,centers[0]-half)
    for i,center in enumerate(centers,1):
        add(f'P{i}',f'Pile P{i}','pile_u',center-half,center+half)
        if i<len(centers):add(f'S{i}',f'P{i}–P{i+1}','hoop',center+half,centers[i]-half)
    add('right','Right end','hoop',centers[-1]+half,length)
    return zones


def zone_runs(e):
    """Only group a run when its complete entered extent fits one physical zone.

    A pile U run can reach a bar radius beyond the pile clearance envelope used
    by the starting grid. Use the largest supported radius only for grouping,
    so a size edit does not move its controls. Physical clearance checks still
    use each actual diameter. Hoop centers stay outside the pile envelope.
    Crossing/custom runs get their own numbered cards; none are split or moved.
    """
    zones=cap_zones(e);groups={z['key']:[] for z in zones};custom=[]
    for run in e.case.get('transverse_detail',{}).get('runs',[]):
        matches=[]
        for z in zones:
            if z['kind']!=run['kind']:continue
            allowance=max(BAR_DIAMETER.values())/2 if run['kind']=='pile_u' else 0
            left=z['left']-allowance;right=z['right']+allowance
            if z['key']=='left':left=0
            if z['key']=='right':right=e.value('L_cap')
            if left-1e-7<=run['first_in']<=run['end_in']<=right+1e-7:matches.append(z)
        if len(matches)==1:groups[matches[0]['key']].append(run)
        else:custom.append(run)
    for group in groups.values():group.sort(key=lambda r:(r['first_in'],r['id']))
    return zones,groups,custom


def new_zone_run(e,key,bar,pitch):
    """Propose a new run inside one zone; existing runs remain untouched."""
    zones,groups,_=zone_runs(e)
    zone=next(z for z in zones if z['key']==key)
    if groups[key]:raise ValueError('This zone already has a run. Edit or split its numbered card.')
    radius=BAR_DIAMETER[bar]/2;p=e.case['inputs']
    first=max(zone['left']+radius,p['C_s']+radius)
    end=min(zone['right']-radius,e.value('L_cap')-p['C_s']-radius)
    # Keep the new run clear of existing physical bars at either boundary.
    from .transverse import scheduled_bars,empty_detail
    from .detailing import required_clear
    for existing in scheduled_bars(dict(e.case,transverse_detail=dict(e.case.get('transverse_detail',empty_detail()),enabled=True))):
        gap=radius+BAR_DIAMETER[existing['bar']]/2+required_clear(e,max(2*radius,BAR_DIAMETER[existing['bar']]))
        x=existing['station_in']
        if x<=zone['left']:first=max(first,x+gap)
        elif x>=zone['right']:end=min(end,x-gap)
        else:raise ValueError('A custom run already places bars in this zone. Review its limits in the Custom / crossing runs cards.')
    if end<first:raise ValueError('No room for a new run in this zone with the current cover, pile clearances and adjoining bars.')
    existing={r['id'] for r in e.case.get('transverse_detail',{}).get('runs',[])};n=1
    while f'R{n}' in existing:n+=1
    return dict(id=f'R{n}',kind=zone['kind'],bar=bar,zone='G',first_in=first,end_in=end,pitch_in=pitch,
                development_confirmed=False,development_basis='')
