"""Mirrored end-face U grids. One physical path feeds checks and every view.

Coordinates are (along cap, across cap, above underside), in inches. These
local bars receive end-face credit only, never automatic flexure/shear credit.
"""
from copy import deepcopy
import math


def settings(case):
    s=deepcopy(case.get('end_face_grid', dict(version=2, enabled=False,placement_mode='manual',
        left=True, right=True, face_offset_in=0., layer_clear_in=2., perimeter_inset_in=3.,
        horizontal=dict(bar=5, count=3, spacing_in=0., return_in=7.5, bend_diameter_in=0.,hook_mode='standard'),
        vertical=dict(bar=5, count=4, spacing_in=0., return_in=7.5, bend_diameter_in=0.,hook_mode='standard'))))
    s.setdefault('placement_mode','manual')
    for direction in ('horizontal','vertical'):s[direction].setdefault('hook_mode','custom')
    return s


def enabled(case):
    return bool(case.get('end_face_grid', {}).get('enabled', False))


def validate(case):
    if 'end_face_grid' not in case:
        if case.get('schema_version') == 5:
            raise ValueError('Case version 5 requires end_face_grid.')
        return
    if case.get('schema_version') != 5:
        raise ValueError('End-face grids require case version 5; use the updated notebook.')
    s = case['end_face_grid']
    if not isinstance(s, dict) or type(s.get('version')) is not int or s['version'] not in (1,2):
        raise ValueError('Unsupported end-face grid version.')
    if s.get('placement_mode','manual') not in ('manual','aligned'):
        raise ValueError('End-bar placement must be manual or aligned.')
    if s['version']==1 and s.get('placement_mode','manual')!='manual':
        raise ValueError('Aligned end bars require end-grid version 2.')
    for key in ('enabled', 'left', 'right'):
        if type(s.get(key)) is not bool:
            raise ValueError('End-face grid '+key+' must be true or false.')
    def dimension(record, key, positive=False):
        v = record.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1000 or positive and v == 0:
            raise ValueError('End-face grid '+key+' must be a finite '+('positive' if positive else 'nonnegative')+' inch value, at most 1000.')
    for key in ('face_offset_in', 'layer_clear_in', 'perimeter_inset_in'):
        dimension(s, key)
    for direction in ('horizontal', 'vertical'):
        row = s.get(direction)
        if not isinstance(row, dict):
            raise ValueError('End-face grid needs horizontal and vertical settings.')
        if row.get('hook_mode','custom') not in ('standard','custom') or s['version']==1 and row.get('hook_mode','custom')!='custom':
            raise ValueError('Standard end hooks require end-grid version 2; use standard or custom.')
        if type(row.get('bar')) is not int or row['bar'] not in range(3, 12):
            raise ValueError('End U-bars must be #3 through #11.')
        if type(row.get('count')) is not int or not 0 <= row['count'] <= 40:
            raise ValueError('End U-bar counts must be whole numbers from 0 to 40 per end.')
        dimension(row, 'return_in', True)
        dimension(row, 'bend_diameter_in')
        dimension(row, 'spacing_in')


def minimum_bend(bar):
    from .model import BAR_DIAMETER
    return (6 if bar <= 8 else 8)*BAR_DIAMETER[bar]


def geometry(e):
    if hasattr(e, '_end_grid_geometry'):
        return e._end_grid_geometry
    from .model import BAR_DIAMETER
    s = settings(e.case); p = e.case['inputs']; length = e.value('L_cap'); result = []
    if not s['enabled']:
        return []
    dh = BAR_DIAMETER[s['horizontal']['bar']]
    for end in ('left', 'right'):
        if not s[end]:
            continue
        other_returns=[]
        for direction in ('horizontal', 'vertical'):
            row = s[direction]; d = BAR_DIAMETER[row['bar']]
            standard=row['hook_mode']=='standard'
            inside = minimum_bend(row['bar']) if standard else row['bend_diameter_in'] or minimum_bend(row['bar'])
            tail=12*d if standard else row['return_in']
            radius = (inside+d)/2
            plane = p['C_s']+s['face_offset_in']+d/2
            if direction == 'vertical' and s['horizontal']['count']:
                plane += dh+s['layer_clear_in']
            x0 = p['C_s']+d/2+s['perimeter_inset_in']; x1 = p['b']-x0
            y0 = p['C_b']+d/2+s['perimeter_inset_in']; y1 = p['h']-p['C_t']-d/2-s['perimeter_inset_in']
            if s['placement_mode']=='aligned':
                from .end_grid_alignment import bounds
                x0,x1,y0,y1=bounds(e,d)
            lo, hi = (x0, x1) if direction == 'horizontal' else (y0, y1)
            a, b = (y0, y1) if direction == 'horizontal' else (x0, x1)
            # Interior grid bars complement the perimeter hoop. Keeping their
            # return legs off the four corners avoids coincident H/V returns.
            pitch = row['spacing_in'] or (b-a)/(row['count']+1)
            nominal=[(a+b)/2+(i-(row['count']-1)/2)*pitch for i in range(row['count'])]
            positions=nominal;placement_ok=True;placement_note='Entered perimeter inset and spacing.'
            if s['placement_mode']=='aligned' and nominal:
                from .end_grid_alignment import stagger
                positions,placement_ok,placement_note=stagger(e,end,direction,d,lo,hi,a,b,nominal,other_returns)
            for i,at in enumerate(positions):
                path = [(radius+tail, lo), (radius, lo)]
                path += [(radius+radius*math.cos(t), lo+radius+radius*math.sin(t))
                         for t in [math.radians(-90-j*90/24) for j in range(1, 25)]]
                path += [(0., hi-radius)]
                path += [(radius+radius*math.cos(t), hi-radius+radius*math.sin(t))
                         for t in [math.radians(180-j*90/24) for j in range(1, 25)]]
                path += [(radius+tail, hi)]
                points = []
                for inward, transverse in path:
                    station = plane+inward if end == 'left' else length-plane-inward
                    x, y = (transverse, at) if direction == 'horizontal' else (at, transverse)
                    points.append((station, x, y))
                fit = placement_ok and hi-lo >= 2*radius and b > a and all(
                    p['C_s']+d/2-1e-8 <= st <= length-p['C_s']-d/2+1e-8 and
                    p['C_s']+d/2-1e-8 <= x <= p['b']-p['C_s']-d/2+1e-8 and
                    p['C_b']+d/2-1e-8 <= y <= p['h']-p['C_t']-d/2+1e-8 for st, x, y in points)
                result.append(dict(id=f'End-{end}-{direction[0].upper()}{i+1}', end=end,
                    direction=direction, bar=row['bar'], diameter=d, coordinate_in=at,
                    plane_in=plane if end == 'left' else length-plane, pitch_in=pitch,
                    return_in=tail, inside_diameter_in=inside, radius_in=radius,
                    hook_mode=row['hook_mode'],placement_mode=s['placement_mode'],placement_ok=placement_ok,
                    nominal_coordinate_in=nominal[i],shift_in=at-nominal[i],placement_note=placement_note,
                    length_in=2*tail+max(0., hi-lo-2*radius)+math.pi*radius,
                    fit=fit, points=points))
                other_returns.extend([(points[0][1],points[0][2],d),(points[-1][1],points[-1][2],d)])
    e._end_grid_geometry = result
    return result


def weight(e):
    from .model import BAR_AREA
    return sum(r['length_in']*BAR_AREA[r['bar']]*490/1728 for r in geometry(e))


def _distances(a, b, c, d):
    """Exact distances between one segment and arrays of straight segments."""
    import numpy as np
    u = b-a; v = d-c; w = a-c
    uu = u@u; vv = np.einsum('ij,ij->i', v, v)
    uv = v@u; uw = w@u; vw = np.einsum('ij,ij->i', v, w)
    def point_segment(point, starts, vectors, lengths):
        t = np.clip(np.einsum('ij,ij->i', point-starts, vectors)/np.maximum(lengths, 1e-20), 0, 1)
        return np.linalg.norm(point-starts-t[:, None]*vectors, axis=1)
    distances = np.minimum(point_segment(a, c, v, vv), point_segment(b, c, v, vv))
    for ends in (c, d):
        t = np.clip((ends-a)@u/max(uu, 1e-20), 0, 1)
        distances = np.minimum(distances, np.linalg.norm(ends-a-t[:, None]*u, axis=1))
    denom = uu*vv-uv*uv
    safe = np.where(denom > 1e-16, denom, 1.)
    s = (uv*vw-vv*uw)/safe; t = (uu*vw-uv*uw)/safe
    inside = (denom > 1e-16) & (s >= 0) & (s <= 1) & (t >= 0) & (t <= 1)
    lines = np.linalg.norm(w+s[:, None]*u-t[:, None]*v, axis=1)
    return np.where(inside, np.minimum(distances, lines), distances)


def collision_review(e):
    """Drawn steel interference screen; no undocumented cage movement."""
    import numpy as np
    from .model import bar_positions, BAR_DIAMETER
    from .transverse import scheduled_bars, bar_shape
    from .detailing import hook_paths, required_clear
    if hasattr(e, '_end_grid_collisions'):
        return e._end_grid_collisions
    grid = geometry(e); segments = []; owner_ids = []; diameters = []; parallel = []
    def add_path(label, points, diameter, longitudinal=False):
        for a, b in zip(points, points[1:]):
            if math.dist(a, b) > 1e-10:
                segments.append((a, b)); owner_ids.append(label); diameters.append(diameter)
                parallel.append(longitudinal or abs(b[0]-a[0]) > 1e-8 and math.hypot(b[1]-a[1],b[2]-a[2]) < 1e-8)
    length = e.value('L_cap'); p = e.case['inputs']
    for i, bar in enumerate(bar_positions(e, 'P')):
        add_path(f'{bar["kind"]} {i+1}', [(p['C_s'], bar['x'], bar['y']), (length-p['C_s'], bar['x'], bar['y'])], bar['diameter'], True)
    runs = {r['id']: r for r in e.case.get('transverse_detail', {}).get('runs', [])}
    for bar in scheduled_bars(e.case):
        shape = bar_shape(e, runs[bar['run']])
        add_path(bar['id'], [(bar['station_in']+v[0], v[1], v[2]) for v in shape['points_3d']], BAR_DIAMETER[bar['bar']])
    for i, hook in enumerate(hook_paths(e, bar_positions(e, 'B'))):
        # Added bars lie in vertical longitudinal planes.
        add_path('Added hook '+str(i+1), [(x, hook['bar']['x'], y) for x, y in hook['points']], hook['bar']['diameter'])
    records = []
    for bar in grid:
        if segments:
            arrays = np.asarray(segments); starts = arrays[:, 0]; ends = arrays[:, 1]
            lower=np.minimum(starts,ends);upper=np.maximum(starts,ends)
            ds = np.asarray(diameters); longs = np.asarray(parallel)
            pair_clear = np.asarray([required_clear(e, max(bar['diameter'], diameter)) for diameter in diameters])
            worst = None
            for a, b in zip(np.asarray(bar['points']), np.asarray(bar['points'])[1:]):
                # Only parallel return/main bars need the parallel clear gap.
                is_return = abs(b[0]-a[0]) > 1e-8 and np.linalg.norm((b-a)[1:]) < 1e-8
                required = np.where(longs & is_return, pair_clear, 0.)
                # Polyline bend sagitta is bounded by r*(1-cos(pi/96)).
                # Bounding-box distance is a lower bound on segment distance.
                # Discard only pairs that cannot beat the current worst margin.
                delta=np.maximum(0,np.maximum(lower-np.maximum(a,b),np.minimum(a,b)-upper))
                bound=np.sqrt(np.einsum('ij,ij->i',delta,delta))-(bar['diameter']+ds)/2-.005-required
                indices=np.flatnonzero(bound < (worst['margin_in'] if worst else math.inf))
                if not len(indices):continue
                clear = _distances(a, b, starts[indices], ends[indices])-(bar['diameter']+ds[indices])/2-.005
                margin = clear-required[indices]
                k=int(np.argmin(margin));j=int(indices[k])
                if worst is None or margin[k] < worst['margin_in']:
                    worst = dict(bar=bar['id'], other=owner_ids[j], clear_in=float(clear[k]),
                                 required_in=float(required[j]), margin_in=float(margin[k]))
            if worst: records.append(worst)
        add_path(bar['id'], bar['points'], bar['diameter'])
    e._end_grid_collisions = records
    return records


def pile_conflicts(e):
    """Conservative square pile envelope, including placement and clear gap."""
    p=e.case['inputs'];hits=[]
    if not p['Ready_pile']:return hits
    def intersects(a,b,lo,hi):
        first,last=0.,1.
        for x,y,l,h in zip(a,b,lo,hi):
            if abs(y-x)<1e-12:
                if x<l or x>h:return False
            else:
                t0,t1=sorted(((l-x)/(y-x),(h-x)/(y-x)))
                first=max(first,t0);last=min(last,t1)
                if first>last:return False
        return True
    for bar in geometry(e):
        gap=p['C_pile']+bar['diameter']/2
        half=p['D_pile']/2+e.value('Tol_pile')+gap
        for i in range(int(p['N_pile'])):
            station=e.value('E_CL')+i*p['S_pile']*12
            lo=(station-half,p['b']/2-half,-1000.)
            hi=(station+half,p['b']/2+half,p['Pile_embed']+gap)
            if any(intersects(a,b,lo,hi) for a,b in zip(bar['points'],bar['points'][1:])):
                hits.append(f'{bar["id"]} / pile {i+1}')
    return hits


def checks(e):
    from .model import Check
    from .check_working import record
    from .detailing import required_clear
    if not enabled(e.case):
        return []
    bars = geometry(e); result = []; s = settings(e.case)
    def flag(key, label, ok, basis, values):
        c = Check(key, label, 'PASS' if ok else 'FAIL', 0. if ok else 2., basis)
        record(c, 'Detail screen: flag 0 when satisfied, otherwise 2; not a strength ratio.', values)
        result.append(c)
    valid = bool(bars) and all(b['fit'] for b in bars)
    flag('Chk_end_grid_fit', 'End-face U grid · cover and shape fit', valid,
         'Checks drawn centerlines plus bar radius against entered cover and bend space. Aligned placement explicitly staggers end bars around the fixed longitudinal cage. '+
         ' '.join(dict.fromkeys(b['placement_note'] for b in bars)),
         [('drawn bars', len(bars), ''), ('bars fitting cover / bends', sum(b['fit'] for b in bars), '')])
    for direction in ('horizontal', 'vertical'):
        selected = [b for b in bars if b['direction'] == direction]
        if not selected: continue
        b = selected[0]; minimum = minimum_bend(b['bar'])
        flag('Chk_end_grid_bend_'+direction, 'End U bend · '+direction, b['inside_diameter_in'] >= minimum-1e-8,
             'LRFD 5.10.2.1 standard general-bar bend diameter; these are local end bars, not shear stirrups.',
             [('inside bend diameter', b['inside_diameter_in'], 'in'), ('minimum', minimum, 'in')])
        if s[direction]['count'] > 1:
            coords=sorted(r['coordinate_in'] for r in selected if r['end']==b['end'])
            clear = min(v-u for u,v in zip(coords,coords[1:]))-b['diameter']; minimum_clear = required_clear(e, b['diameter'])
            flag('Chk_end_grid_clear_'+direction, 'End U parallel spacing · '+direction, clear >= minimum_clear-1e-8,
                 'LRFD 5.10.3.1.1 and entered project minimum clear spacing, using drawn parallel bars.',
                 [('actual clear', clear, 'in'), ('required clear', minimum_clear, 'in')])
    collisions = collision_review(e)
    if collisions:
        worst = min(collisions, key=lambda r:r['margin_in'])
        flag('Chk_end_grid_collision', 'End U grid · drawn steel interference', worst['margin_in'] >= -.01,
             '3D centerline segment distances including bends, actual hoops / pile U-bars, continuous bars, added hooks, and the other end-grid bars. Crossing-bar contact is allowed; parallel main/return bars require clear spacing. Bend approximation allowance 0.005 in. Full fabrication and pile tolerance review remains separate.',
             [('end bar', worst['bar'], ''), ('other bar', worst['other'], ''), ('clear gap', worst['clear_in'], 'in'), ('required clear', worst['required_in'], 'in')])
    if e.case['inputs']['Ready_pile']:
        conflicts=pile_conflicts(e)
        flag('Chk_end_grid_piles','End U grid · pile envelope clearance',not conflicts,
             'Conservative square pile envelope includes the current horizontal placement allowance, pile embedment and required clear gap, enlarged by bar radius. Review shape-specific and fabrication tolerances separately.',
             [('conflicts', '; '.join(conflicts) or 'None', '')])
    result.append(Check('Status_end_grid_anchorage', 'End-face U grid · anchorage and pile clearance', 'PENDING', 'N/A',
        'Standard 90° hooks use a 12db straight tail and the general-bar minimum bend diameter; custom tails are entered lengths after the bend. Standard hook dimensions alone do not establish development. Verify required hooked development, lap or anchorage into the cap, pile-envelope clearances and fabrication tolerances (LRFD 5.10.8). End-face area/spacing credits describe the drawing, not verified anchorage. End bars receive no automatic longitudinal-strength, shear or torsion credit.'))
    return result
