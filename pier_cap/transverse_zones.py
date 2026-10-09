"""Locate transverse runs in physical cap zones without changing their stations."""
import math
from .model import BAR_DIAMETER
from .transverse import run_last_station


def station_range(first,last):
    return f'{first:g}–{last:g} in ({first/12:g}–{last/12:g} ft)'


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


def starting_zone_detail(e,bar,pitch):
    """One run per zone; split minimum allowable clearance at zone boundaries."""
    from .detailing import required_clear
    from .transverse import validate_detail
    if isinstance(bar,bool) or bar not in range(3,12):raise ValueError('Choose starting bar size #3 through #11.')
    if isinstance(pitch,bool) or not math.isfinite(pitch) or pitch<=0:raise ValueError('Starting spacing must be a positive finite inch value.')
    diameter=BAR_DIAMETER[bar];radius=diameter/2
    # Half the minimum allowable clear gap is measured to the bar surface.
    # Center offset includes the radius and is independent of regular pitch.
    offset=(diameter+required_clear(e,diameter))/2
    cover=e.case['inputs']['C_s']+radius;length=e.value('L_cap');runs=[]
    for zone in cap_zones(e):
        first=max(cover,zone['left']+offset)
        end=min(length-cover,zone['right']-offset)
        if end<first:
            raise ValueError(zone['label']+': no room after minimum-clearance offsets and cap cover. Review zone geometry, bar size and clearance requirements.')
        runs.append(dict(id=f'R{len(runs)+1}',kind=zone['kind'],bar=int(bar),zone='G',
            first_in=first,end_in=end,pitch_in=pitch,include_end_bar=True,
            development_confirmed=False,development_basis=''))
    detail=dict(version=2,enabled=True,runs=runs)
    validate_detail(dict(e.case,transverse_detail=detail))
    return detail


def zone_runs(e):
    """Group the physical bar stations, not the unused remainder of an end limit.

    A pile U run can reach a bar radius beyond the pile clearance envelope used
    by the starting grid. Use the largest supported radius only for grouping,
    so a size edit does not move its controls. Physical clearance checks still
    use each actual diameter. Hoop centers stay outside the pile envelope.
    Crossing/custom runs get their own numbered cards; none are split or moved.
    """
    zones=cap_zones(e);groups={z['key']:[] for z in zones};custom=[]
    for run in e.case.get('transverse_detail',{}).get('runs',[]):
        last=run_last_station(run)
        matches=[]
        for z in zones:
            if z['kind']!=run['kind']:continue
            allowance=max(BAR_DIAMETER.values())/2 if run['kind']=='pile_u' else 0
            left=z['left']-allowance;right=z['right']+allowance
            if z['key']=='left':left=0
            if z['key']=='right':right=e.value('L_cap')
            if left-1e-7<=run['first_in']<=last<=right+1e-7:matches.append(z)
        if len(matches)==1:groups[matches[0]['key']].append(run)
        else:custom.append(run)
    for group in groups.values():group.sort(key=lambda r:(r['first_in'],r['id']))
    return zones,groups,custom


def saved_bars(e):
    """Include retained runs when layout display is disabled, without mutating it."""
    from .transverse import scheduled_bars,empty_detail
    return scheduled_bars(dict(e.case,transverse_detail=dict(e.case.get('transverse_detail',empty_detail()),enabled=True)))


def zone_occupancy(e):
    """Exact existing stations strictly inside each zone, matching add-run checks."""
    bars=saved_bars(e);result={}
    for zone in cap_zones(e):
        owners={}
        for bar in bars:
            if zone['left']<bar['station_in']<zone['right']:
                owner=owners.setdefault(bar['run'],dict(id=bar['run'],kind=bar['kind'],stations=[]))
                owner['stations'].append(bar['station_in'])
        result[zone['key']]=list(owners.values())
    return result


def occupant_text(owner):
    stations=owner['stations'];kind='pile U-bars' if owner['kind']=='pile_u' else 'closed hoops'
    return f'{owner["id"]} ({kind}): {len(stations)} bar(s) at '+station_range(stations[0],stations[-1])


def _boundary_side(zone,assigned):
    if assigned is not None:
        if assigned['right']<=zone['left']+1e-7:return 'left'
        if assigned['left']>=zone['right']-1e-7:return 'right'
    return None


def zone_add_conflicts(e):
    """An adjoining run's bar-radius overhang constrains the edge, not the zone."""
    zones,groups,_=zone_runs(e);assigned={r['id']:z for z in zones for r in groups[z['key']]}
    occupancy=zone_occupancy(e)
    return {z['key']:[o for o in occupancy[z['key']] if _boundary_side(z,assigned.get(o['id'])) is None] for z in zones}


def run_limit_overlaps(runs):
    """Editing warnings for intersecting entered extents, not a fit calculation."""
    result={r['id']:[] for r in runs}
    for index,run in enumerate(runs):
        for other in runs[index+1:]:
            first=max(run['first_in'],other['first_in']);last=min(run['end_in'],other['end_in'])
            if first<=last+1e-7:
                result[run['id']].append(dict(id=other['id'],first=first,last=last))
                result[other['id']].append(dict(id=run['id'],first=first,last=last))
    return result


def new_zone_run(e,key,bar,pitch,*,allow_overlap=False):
    """Propose a new run inside one zone; existing runs remain untouched."""
    zones,groups,_=zone_runs(e)
    zone=next(z for z in zones if z['key']==key)
    if groups[key]:raise ValueError(zone['label']+' already has a run: '+', '.join(r['id'] for r in groups[key])+'. Edit or split its numbered card.')
    occupants=zone_add_conflicts(e)[key]
    if occupants and not allow_overlap:
        raise ValueError(zone['label']+' ['+station_range(zone['left'],zone['right'])+'] already contains bars from '+
            '; '.join(occupant_text(owner) for owner in occupants)+'. Inspect those numbered runs before adding another. Geometry changes do not move saved stations.')
    radius=BAR_DIAMETER[bar]/2;p=e.case['inputs']
    first=max(zone['left']+radius,p['C_s']+radius)
    end=min(zone['right']-radius,e.value('L_cap')-p['C_s']-radius)
    # Keep the new run clear of existing physical bars at either boundary.
    from .detailing import required_clear
    assigned={r['id']:z for z in zones for r in groups[z['key']]}
    for existing in saved_bars(e):
        gap=radius+BAR_DIAMETER[existing['bar']]/2+required_clear(e,max(2*radius,BAR_DIAMETER[existing['bar']]))
        x=existing['station_in']
        side=_boundary_side(zone,assigned.get(existing['run']))
        if x<=zone['left'] or side=='left':first=max(first,x+gap)
        elif x>=zone['right'] or side=='right':end=min(end,x-gap)
    if end<first:raise ValueError('No room for a new run in this zone with the current cover, pile clearances and adjoining bars.')
    existing={r['id'] for r in e.case.get('transverse_detail',{}).get('runs',[])};n=1
    while f'R{n}' in existing:n+=1
    return dict(id=f'R{n}',kind=zone['kind'],bar=bar,zone='G',first_in=first,end_in=end,pitch_in=pitch,
                development_confirmed=False,development_basis='')
