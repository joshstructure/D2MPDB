"""Explicit transverse spacing of added longitudinal bars; inches throughout."""
import math
from copy import deepcopy
from .detailing import required_clear


def layout_settings(case):
    if 'added_bar_layout' in case:return deepcopy(case['added_bar_layout'])
    return dict(version=1,mode='legacy' if case['inputs']['Manual_spacing'] else 'auto',
        rows={str(k):dict(pitch_in=case['inputs']['SP_detail_B'],offset_in=0.) for k in (1,2)})


def validate_layout(case):
    config=case.get('added_bar_layout')
    if config is None:
        if case.get('schema_version')==4:raise ValueError('Case version 4 requires added_bar_layout.')
        return
    if case.get('schema_version')!=4:raise ValueError('Added-bar layout requires case schema_version 4; use the updated notebook.')
    if not isinstance(config,dict) or type(config.get('version')) is not int or config.get('version')!=1 or config.get('mode') not in ('auto','spacing','legacy'):
        raise ValueError('Invalid added-bar layout version or spacing mode.')
    if not isinstance(config.get('rows'),dict) or set(config['rows'])!={'1','2'}:
        raise ValueError('Added-bar layout needs rows 1 and 2.')
    for k,row in config['rows'].items():
        if not isinstance(row,dict):raise ValueError('Invalid added-bar spacing row '+k)
        for name in ('pitch_in','offset_in'):
            value=row.get(name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError(f'Added row {k} {name} must be a finite number in inches.')
        if row['pitch_in']<=0:raise ValueError(f'Added row {k} spacing must be greater than zero.')


def entered_positions(case,row):
    config=case.get('added_bar_layout',{})
    if config.get('mode')!='spacing':return None
    p=case['inputs'];s=config['rows'][str(row)];count=int(p[f'n_B{row}'])
    return [p['b']/2+s['offset_in']+(j-(count-1)/2)*s['pitch_in'] for j in range(count)]


def legacy_spacing(case):
    return case.get('added_bar_layout',{}).get('mode','legacy')=='legacy'


def added_clearances(e,bars):
    """Separate same-row added/added and added/continuous clearance checks."""
    result=[]
    for k in (1,2):
        row=[b for b in bars if b['layer']==f'Bottom row {k}']
        extra=[b for b in row if b['additional']];continuous=[b for b in row if not b['additional']]
        for name,pairs in [('added',[(a,b) for i,a in enumerate(extra) for b in extra[i+1:]]),
                           ('continuous',[(a,b) for a in extra for b in continuous])]:
            if not pairs:continue
            candidates=[]
            for a,b in pairs:
                actual=math.hypot(a['x']-b['x'],a['y']-b['y'])-(a['diameter']+b['diameter'])/2
                required=required_clear(e,max(a['diameter'],b['diameter']))
                candidates.append(dict(row=k,family=name,actual=actual,required=required,
                    ratio=required/max(actual,1e-6),a=a,b=b,status='PASS' if actual+1e-8>=required else 'FAIL'))
            result.append(max(candidates,key=lambda r:r['ratio']))
    return result


def fit_problems(e,bars):
    """Check the entered positions without snapping bars away from a conflict."""
    if e.case.get('added_bar_layout',{}).get('mode')!='spacing':return []
    from .transverse import enabled
    from .model import BAR_DIAMETER
    from .placement import Envelope
    p=e.case['inputs'];env=Envelope(e) if enabled(e.case) else None
    issues=[]
    for bar in bars:
        if not bar['additional']:continue
        if env and env.shapes:
            spans=env.intervals(bar['y'],bar['diameter'])
        else:
            edge=p['C_s']+BAR_DIAMETER[p['Bar_v']]+bar['diameter']/2
            spans=[(edge,p['b']-edge)]
        if not any(a-1e-7<=bar['x']<=b+1e-7 for a,b in spans):
            issues.append(f"{bar['kind']}: bar at {bar['x']:.3f} in across the cap does not fit the cover / transverse cage envelope.")
    return issues
