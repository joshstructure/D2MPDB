"""Parametric ring-spacing comparison using the same calculation model."""
from copy import deepcopy
from math import floor
from .model import analyze
from .cone import geometry as cone_geometry


def spacing_study(case,spacings=(24.,30.,36.,42.,48.)):
    result=[]
    for s in spacings:
        p=deepcopy(case)
        p['ring_spacing_in']=float(s)
        # Leave physical room for the entered arch above the highest ring.
        cone=cone_geometry(p)
        room=p['height_in']-p['cover_in']-p['tie_offset_in']-p['arch_rise_in']-p['first_ring_in']-(cone['face_rise_in'] if cone['enabled'] else 0.)
        p['ring_count']=max(1,floor(room/s)+1)
        try:
            r=analyze(p)
        except ValueError as e:
            result.append(dict(spacing_in=s,error=str(e)))
            continue
        result.append(dict(spacing_in=s,ring_count=p['ring_count'],
            top_ring_in=r['rows'][-1]['z'],grid_bar=r['grid']['bar'],
            grid_spacing_in=r['grid']['spacing'],max_ring_kip=max(a['R'] for a in r['rings']),
            max_tie_kip=max(a['arch']['tie'] for a in r['rows']),
            minimum_angle=min(a['arch']['minimum_angle'] for a in r['rows']),
            failed_checks=[a['id'] for a in r['checks'] if a['status']=='FAIL'],
            status=r['overall']))
    return result
