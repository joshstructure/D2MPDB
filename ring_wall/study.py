"""Compare ring pitches without changing wall reinforcement criteria."""
from copy import deepcopy
from math import floor
from .model import analyze


def spacing_study(case,spacings=(24.,30.,36.,42.,48.)):
    result=[]
    for spacing in spacings:
        p=deepcopy(case);p['ring_spacing_in']=float(spacing)
        # Leave entered concrete cover above the top ring/weld; retain first row.
        room=p['height_in']-p['required_cover_in']-p['weld_leg_in']-p['first_ring_in']
        p['ring_count']=max(1,floor(room/spacing)+1)
        try:r=analyze(p)
        except ValueError as exc:result.append(dict(spacing_in=spacing,error=str(exc)));continue
        result.append(dict(spacing_in=spacing,ring_count=p['ring_count'],grid_spacing_in=r['grid']['spacing'],
            max_ring_kip=max(a['R'] for a in r['rings']),max_t_in=max(a['t_req'] for a in r['rings']),
            max_weld_in=max(a['weld_req'] for a in r['rings']),max_weld_dc=max(a['weld_ratio'] for a in r['rings']),
            contact_failures=sum(not a['contact_ok'] for a in r['rings']),status=r['overall']))
    return result
