"""Actual-cage checks, AASHTO LRFD BDS 10th edition (2024).

Units are inches, kips and ksi, except imported moments/torques (kip-ft).
The BPAD/C005 source equations are deliberately not edited. No classification
is inferred from an analysis filename, and no unconfirmed support is exempted.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import math
from .hooks import stirrup_hook_extension, CRSI_HOOK_SOURCE

CODE = 'AASHTO LRFD BDS, 10th ed. (2024)'
DEFAULTS = dict(version=2, bearing_loading='unknown', pile_connection='unknown',
    load_path_basis='', density_factor=1.0, coating='unknown', phi_axial=.9,
    hoop_closure='hooks', closure_angle=135, closure_tail_in=0., closure_lap_in=0.,
    closure_extension_mode='standard',
    closure_engages_bars=False, continuous_splices='unknown',
    shrinkage_project_spacing_in=12., support_overrides={})


def settings(case):
    saved=deepcopy(case.get('lrfd_checks', {}))
    result={**deepcopy(DEFAULTS), **saved}
    if saved.get('version',1)==1:
        result['version']=2
        # The old default was an unentered zero, not a specified zero-length hook.
        # Preserve explicitly entered nonzero dimensions as custom details.
        if 'closure_extension_mode' not in saved:
            result['closure_extension_mode']='standard' if saved.get('closure_tail_in',0)==0 else 'custom'
    return result


def closure_extension(s,bar):
    return stirrup_hook_extension(bar,s['closure_angle']) if s['closure_extension_mode']=='standard' else s['closure_tail_in']


def validate_settings(case):
    s=settings(case)
    if s['version'] not in (2,3): raise ValueError('Unsupported LRFD check settings version; use the updated notebook.')
    choices={'bearing_loading':('unknown','top','indirect'),
        'pile_connection':('unknown','pinned','moment'),
        'coating':('unknown','uncoated','epoxy'),
        'hoop_closure':('unknown','hooks','lap_pair'),
        'closure_extension_mode':('standard','custom'),
        'continuous_splices':('unknown','none','present')}
    for k,values in choices.items():
        if s[k] not in values: raise ValueError('Invalid LRFD setting: '+k)
    for k in ('density_factor','phi_axial','closure_tail_in','closure_lap_in','shrinkage_project_spacing_in'):
        v=s[k]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:
            raise ValueError('Invalid LRFD numerical setting: '+k)
    if not .75<=s['density_factor']<=1 or not 0<s['phi_axial']<=1:
        raise ValueError('Use 0.75–1 for concrete density factor and 0 < axial resistance factor ≤ 1.')
    if s['closure_angle'] not in (90,135) or type(s['closure_engages_bars']) is not bool:
        raise ValueError('Invalid hoop closure hook detail.')
    if not isinstance(s['load_path_basis'],str) or not isinstance(s['support_overrides'],dict):
        raise ValueError('LRFD load-path basis / support overrides are invalid.')
    for value in s['support_overrides'].values():
        if value not in ('unknown','pinned','moment'): raise ValueError('Invalid individual pile connection.')


def development_length(db, area, fy, fc, *, density=1., top=False, coating='unknown',
                       cb=None, hook_radius=0., node_efficiency=.45):
    """5.10.8.2.1a/b/c and 5.10.8.2.4a; no excess-steel/clamping/tie credit.

    Unknown coating uses the adverse epoxy factor, not an assumed bare bar.
    ktr=beta_t=0. Hook minima are applied to ldh, not to its straight portion.
    """
    fh=min(area*fy, db*hook_radius*node_efficiency*fc) if hook_radius else 0.
    basic=.17*db*((fy-fh/area)/(1.97*density*fc**.25))**2
    location=1.3 if top else 1.
    coat=1. if coating=='uncoated' else 1.2 if hook_radius else 1.5
    confinement=max(.3,min(1.,db/cb)) if cb and cb>0 else 1.
    straight=basic*min(1.7,location*coat)*confinement
    length=max(8*db,6.,straight+hook_radius+db/2) if hook_radius else max(12.,straight)
    return dict(db=db,area=area,fy=fy,fc=fc,density=density,fh=fh,basic_in=basic,
        location_factor=location,coating_factor=coat,confinement_factor=confinement,
        straight_in=straight,required_in=length,hook_radius=hook_radius,
        equation='5.10.8.2.4a-1/-2' if hook_radius else '5.10.8.2.1a-1/-2')


def longitudinal_inventory(e):
    from .model import bar_positions, BAR_AREA
    from .detailing import hook_paths
    p=e.case['inputs'];s=settings(e.case);bars=bar_positions(e,'B');result=[]
    paths=hook_paths(e,bars)
    for i,b in enumerate(bars):
        # Conservative nearest neighboring bar, in any longitudinal row.
        distances=[math.hypot(b['x']-q['x'],b['y']-q['y'])/2 for q in bars if q is not b]
        cb=min(b['x'],p['b']-b['x'],b['y'],p['h']-b['y'],*distances)
        segments=[t for t in paths if t['bar']==b] if b['additional'] else [None]
        for t in segments:
            d=development_length(b['diameter'],BAR_AREA[b['bar']],p['fy'],p['fc'],
                density=s['density_factor'],top=b['y']>12,coating=s['coating'],cb=cb,
                hook_radius=t['radius'] if t else 0.)
            left=t['left']-b['diameter']/2 if t else p['C_s']
            right=t['right']+b['diameter']/2 if t else e.value('L_cap')-p['C_s']
            result.append(dict(id=f'L{i+1}'+(f'-S{t["span"]}' if t else ''),kind=b['kind'],
                bar=b['bar'],x=b['x'],y=b['y'],additional=b['additional'],
                left_in=left,right_in=right,
                straight_left_in=t['left']+t['radius'] if t else left,
                straight_right_in=t['right']-t['radius'] if t else right,cb_in=cb,**d))
    return result


def steel_at(inventory,x,h,face):
    """Credit only straight longitudinal portions; reduce for both end developments.

    A proportional reduction is the conservative C5.7.3.5 development model.
    Bars at mid-depth contribute half their area to either flexural half.
    """
    selected=[]
    for b in inventory:
        if not b['straight_left_in']-1e-8<=x<=b['straight_right_in']+1e-8: continue
        side=b['y']-h/2
        if (face=='top' and side< -1e-8) or (face=='bottom' and side>1e-8): continue
        weight=.5 if abs(side)<1e-8 else 1.
        available=max(0.,min(x-b['left_in'],b['right_in']-x))
        factor=min(1.,available/b['required_in'])
        selected.append(dict(b,available_in=available,development_factor=factor,
                             credited_area=weight*b['area']*factor))
    return selected


def source_members(e):
    """Verify complete force profiles before using concurrent member actions."""
    from .force_diagrams import cap_profiles
    audit=e.case['analysis'].get('xml_audit',{})
    if not audit.get('end_records'): return [],'No member forces: global envelopes are used without direct-loading exclusions.'
    if any(k not in ('b','h') for k in e.stale): return [],'Analysis geometry changed: reimport forces; no direct-loading exclusions.'
    from .axial import validate_axial
    problem=validate_axial(audit)
    if problem:return [],problem
    changed=[k for k,r in audit.get('governing',{}).items()
             if not math.isclose(e.case['inputs'][k],r['adopted'],rel_tol=1e-9,abs_tol=1e-8)]
    if changed:return [],'Entered demands differ from the imported member forces ('+', '.join(changed)+'); scalar envelopes used without exclusions. Reimport matching forces.'
    try: cap_profiles(e.case)
    except (ValueError,KeyError,TypeError) as exc: return [],'Invalid member-force source: '+str(exc)
    for r in audit['end_records']:
        if any(not isinstance(r.get(k),(int,float)) or not math.isfinite(r.get(k))
               for k in ('x_in','moment','shear','torque','axial')):
            return [],'Nonfinite or invalid member action; reimport solved forces. No exclusions.'
    grouped=defaultdict(dict);origin=min(r['x_in'] for r in audit['end_records'])
    for r in audit['end_records']:
        if r['state'].startswith(('STRENGTH-','EXTREME')):
            grouped[(str(r['combination']),str(r['element']))][r['side']]=r
    result=[]
    for (combo,element),pair in grouped.items():
        i,j=pair['I'],pair['J'];length=j['x_in']-i['x_in']
        result.append(dict(combo=combo,element=element,state=i['state'],left=i['x_in']-origin,
            right=j['x_in']-origin,mi=i['moment'],mj=j['moment'],vi=i['shear'],vj=j['shear'],
            ni=i['axial'],nj=j['axial'],nu=max(i['axial'],j['axial']),
            ti=-i['torque'],tj=j['torque'],tu=max(abs(i['torque']),abs(j['torque'])),
            raw_axial_i=i['raw_axial'],raw_axial_j=j['raw_axial'],
            source_sha256=audit['sha256'],axial_convention=audit['axial_convention'],length=length))
    result=sorted(result,key=lambda m:(m['combo'],m['left']))
    for combo in set(m['combo'] for m in result):
        group=[m for m in result if m['combo']==combo]
        if any(abs(a['right']-b['left'])>1e-6 for a,b in zip(group,group[1:])):
            return [],'Member-force coverage has a gap or overlap; scalar envelopes used without exclusions.'
    return result,'Concurrent signed M/V/N/T by member and combination; positive Nu is tension. I = -raw AXIAL; J = +raw AXIAL.'


def torsion_threshold(e,nu=0.):
    """5.7.2.1-3/-4/-6, solid nonprestressed rectangular section, kip-ft.

    Signed tension reduces K; verified compression increases K (5.7.2.1-6).
    """
    p=e.case['inputs'];lam=(e.case.get('lrfd_checks') or settings(e.case))['density_factor']
    root=.126*lam*math.sqrt(p['fc']);area=p['b']*p['h']
    k=math.sqrt(max(0.,1-nu/area/root))
    return .25*p['phi_v']*root*area**2/(2*(p['b']+p['h']))*k/12


def forces(m,x):
    t=max(0.,min(1.,(x-m['left'])/m['length']))
    a=.5*(m['vj']-m['vi'])*m['length']/12
    b=m['mj']-m['mi']-a
    return dict(moment=a*t*t+b*t+m['mi'],vu=abs(m['vi']+(m['vj']-m['vi'])*t),
                shear=m['vi']+(m['vj']-m['vi'])*t,
                nu=m.get('ni',m['nu'])+(m.get('nj',m['nu'])-m.get('ni',m['nu']))*t,
                tu=abs(m.get('ti',m['tu'])+(m.get('tj',m['tu'])-m.get('ti',m['tu']))*t))


def member_roots(m,kind='moment'):
    from .force_diagrams import _roots
    a=.5*(m['vj']-m['vi'])*m['length']/12;b=m['mj']-m['mi']-a
    roots=_roots(a,b,m['mi']) if kind=='moment' else _roots(0,2*a,b)
    return [m['left']+t*m['length'] for t in roots if 1e-9<t<1-1e-9]


def direct_regions(e,members,inventory):
    """Same-sign moment domains, split at inflections, with explicit peak evidence.

    A qualified domain must have every controlling local maximum at a confirmed
    direct-load point or pinned support. Continuous main bars must extend from
    every such peak by max(ld, dv*cot(theta)); no span supplement is used to
    establish eligibility. Axial tension or investigated torsion disables relief.
    This is a conservative implementation boundary, not an invented code radius.
    """
    s=settings(e.case);a=e.case['analysis'].get('xml_audit',{});p=e.case['inputs']
    if not members: return []
    origin=min(r['x_in'] for r in a['end_records'])
    bearings=[x-origin for x in a.get('bearing_stations_in',[])]
    piles=[x-origin for x in a.get('pile_centers_in',[])]
    out=[]
    for combo in dict.fromkeys(m['combo'] for m in members):
        group=[m for m in members if m['combo']==combo]
        cuts=sorted({group[0]['left'],group[-1]['right'],
            *(x for m in group for x in member_roots(m)),
            *(m['left'] for m in group if abs(m['mi'])<1e-7),
            *(m['right'] for m in group if abs(m['mj'])<1e-7)})
        for left,right in zip(cuts,cuts[1:]):
            if right-left<1e-6: continue
            span=[m for m in group if m['left']<right-1e-8 and m['right']>left+1e-8]
            if not span: continue
            points=sorted({left,right,*(max(left,m['left']) for m in span),
                           *(min(right,m['right']) for m in span),
                           *(x for m in span for x in member_roots(m,'shear') if left<x<right)})
            def moment(x):
                return max((forces(m,x)['moment'] for m in span if m['left']-1e-7<=x<=m['right']+1e-7),key=abs)
            values=[abs(moment(x)) for x in points]
            peak=max(values);face='top' if moment(points[values.index(peak)])<0 else 'bottom'
            peaks=[x for k,x in enumerate(points) if values[k]>1e-6 and
                   (k==0 or values[k]>=values[k-1]-1e-7) and (k==len(points)-1 or values[k]>=values[k+1]-1e-7)]
            reasons=[];qualified=bool(peaks)
            extension=e.value('dv')/math.tan(math.radians(29))
            if not s['load_path_basis'].strip(): qualified=False;reasons.append('Load-path evidence not recorded')
            for x in peaks:
                bearing=next((i+1 for i,v in enumerate(bearings) if abs(v-x)<.08),None)
                pile=next((i+1 for i,v in enumerate(piles) if abs(v-x)<.08),None)
                connection=s['support_overrides'].get(str(pile),s['pile_connection'])
                direct=(face=='bottom' and bearing and s['bearing_loading']=='top') or (face=='top' and pile and connection=='pinned')
                reason=(f'Bearing {bearing}: {s["bearing_loading"]}' if bearing else f'Pile {pile}: {connection}' if pile else 'Peak away from a confirmed direct-load/support point')
                selected=[b for b in steel_at(inventory,x,p['h'],face) if not b['additional'] and b['kind']!='Skin']
                extended=bool(selected) and all(b['available_in']+1e-8>=max(b['required_in'],extension) for b in selected)
                if not extended: reason+='; main-bar extension insufficient for the exception'
                sufficient=sum(b['credited_area'] for b in selected)*p['fy']>=peak*12/(p['phi_f']*e.value('dv'))-1e-8
                if not sufficient:reason+='; continuous main bars do not resist the flexural maximum'
                qualified=qualified and bool(direct) and extended and sufficient
                reasons.append(f'x={x:.3f} in: '+reason)
            if any(m['nu']>1e-10 for m in span): qualified=False;reasons.append('Net axial tension: full interaction retained (conservative exception boundary)')
            if any(m['tu']>torsion_threshold(e,m['nu']) for m in span):qualified=False;reasons.append('Torsion requires 5.7.3.6.3')
            if s['continuous_splices']!='none':qualified=False;reasons.append('Unspliced continuous main bars not confirmed')
            out.append(dict(id=f'{combo}-{len(out)+1}',combination=combo,left_in=left,right_in=right,face=face,
                peak_moment_kip_ft=peak,peak_stations_in=peaks,extension_in=extension,
                classification='DIRECT — exception eligible' if qualified else 'FULL INTERACTION',
                qualifies=qualified,basis='; '.join(reasons),article='5.7.3.5 / C5.7.3.5'))
    return out


def shear_parameters(e,action,area,rate,ao=None,ph=None,**kwargs):
    from .shear import parameters
    return parameters(e,action,area,rate,ao,ph,**kwargs)


def _check(key,label,ratio,basis,*,pending=False,na=False,pending_reasons=()):
    from .model import Check
    status='NOT REQUIRED' if na else 'FAIL' if isinstance(ratio,(int,float)) and ratio>1+1e-8 else 'PENDING' if pending else 'PASS'
    if pending and pending_reasons:
        heading='Pending because:' if status=='PENDING' else 'Unresolved prerequisites:'
        basis=heading+'\n'+'\n'.join('• '+reason for reason in dict.fromkeys(pending_reasons))+'\n'+basis
    return Check(key,label,status,ratio,basis)


def _anchorage_reason(row):
    failed=row['ratio']>1+1e-8
    reason=f'{row["run"]}: anchorage / closure '+(f'fails (D/C {row["ratio"]:.3f})' if failed else 'is unconfirmed')
    details=[row['notes'].strip()] if row['notes'].strip() else []
    if failed:
        for label,actual,required in [('inside bend diameter',row['bend_in'],row['bend_required_in']),
                                     ('midheight embedment',row['embed_available_in'],row['embed_required_in'])]:
            if required/max(actual,1e-9)>1+1e-8:
                details.append(f'{label} {actual:.3f} in < required {required:.3f} in')
        # Lap-pair closure has its own required lap in the existing notes.
        if row['closure_type']=='hooks' and row['tail_ratio']>1+1e-8:
            details.append(f'hook extension {row["tail_in"]:.3f} in < required {row["tail_required_in"]:.3f} in')
        if row['bar']>8 or row['angle'] not in (90,135):
            details.append(f'#{row["bar"]} bar / {row["angle"]}° end is outside the implemented anchorage details')
    return reason+(' — '+'; '.join(details) if details else '')


def _shear_domain_reasons(p,params):
    reasons=[]
    fc_limit=10 if params['torsion_required'] else 15
    if p['fc']>fc_limit:reasons.append(f"Concrete f′c {p['fc']:g} ksi exceeds the implemented {fc_limit:g} ksi shear limit")
    if p['fy']>100:reasons.append(f"Steel fy {p['fy']:g} ksi exceeds the implemented 100 ksi shear limit")
    if (params['epsilon'] or 0)>.006+1e-12:reasons.append('Calculated longitudinal strain exceeds the implemented 0.006 limit')
    if p['fpc']!=0:reasons.append(f"Precompression fpc = {p['fpc']:g} ksi; the implemented shear calculation requires fpc = 0")
    reasons.extend(params.get('applicability_warnings',[]))
    return list(dict.fromkeys(reasons))


def window_steel(physical,left,right,length,development=None):
    """FDOT 2026 SDG 4.1.4A: minimum intersected legs as the window moves.

    The only changes occur at a bar station +/- half the window length. Examine
    both sides of each event; a bar exactly on the edge receives no credit.
    Returns the lower bound over the entire segment, not a midpoint sample.
    """
    from .model import BAR_AREA
    half=length/2
    points={left,right}
    for bar in physical:
        for x in (bar['station_in']-half,bar['station_in']+half):
            if left<=x<=right:points.update((max(left,x-1e-7),x,min(right,x+1e-7)))
    totals=[]
    for x in sorted(points):
        selected=[bar for bar in physical if abs(bar['station_in']-x)<half-1e-8]
        if development is not None:
            selected=[bar for bar in selected if not development[bar['run']]['pending'] and development[bar['run']]['ratio']<=1+1e-8]
        totals.append((sum(2*BAR_AREA[bar['bar']] for bar in selected),x,[bar['id'] for bar in selected]))
    area,x,ids=min(totals,key=lambda t:t[0])
    return dict(area_in2=area,station_in=x,bar_ids=ids,length_in=length)


def transverse_development(e):
    from .transverse import run_summary,bar_shape,shape_parameters,shape_issues,hook_rotations,rotation_note
    from .model import BAR_DIAMETER,BAR_AREA,bar_positions
    p=e.case['inputs'];s=settings(e.case);rows=[];checks=[]
    for run in run_summary(e.case):
        d=BAR_DIAMETER[run['bar']];shape=shape_parameters(run);geometry=bar_shape(e,run)
        angle=shape['end_angle'] if run['kind']=='pile_u' else s['closure_angle']
        extension=shape['tail_in'] if run['kind']=='pile_u' else closure_extension(s,run['bar'])
        tail=extension if extension is not None else 0.
        bend_min=(4 if run['bar']<=5 and p['fy']<=60 else 6 if run['bar']<=8 else 8)*d
        required_tail=(12*d if run['bar']>=6 else 6*d) if angle==90 else 6*d
        le=.44*d*p['fy']/(s['density_factor']*math.sqrt(p['fc'])) if 6<=run['bar']<=8 else 0.
        available=p['h']/2-p['C_b']-shape['end_raise_in'] if run['kind']=='pile_u' else min(p['h']/2-p['C_b'],p['h']/2-p['C_t'])
        pending=False;extra=''
        if run['kind']=='hoop' and s['hoop_closure']=='unknown': pending=True;tail_ratio=0.;extra='Closure dimensions not entered.'
        elif run['kind']=='hoop' and s['hoop_closure']=='lap_pair':
            ld=development_length(d,BAR_AREA[run['bar']],p['fy'],p['fc'],density=s['density_factor'],coating=s['coating'],top=True)['required_in']
            tail_ratio=1.3*ld/max(s['closure_lap_in'],1e-9);extra=f'5.10.8.2.6d: lap ≥ 1.3ld = {1.3*ld:.3f} in; entered {s["closure_lap_in"]:.3f} in.'
        else: tail_ratio=required_tail/max(tail,1e-9)
        extension_mode=shape['extension_mode'] if run['kind']=='pile_u' else s['closure_extension_mode']
        if run['kind']=='pile_u' or s['hoop_closure']=='hooks':
            if extension_mode=='standard':
                extra+=' '+(CRSI_HOOK_SOURCE+f'; automatic {tail:g} in.' if stirrup_hook_extension(run['bar'],angle) is not None else 'CRSI standard extension unavailable for this bar size / angle.')
            else:extra+=' Custom hook extension.'
        if run['kind']=='pile_u':
            # An end hook must actually wrap a longitudinal bar in the bend pocket.
            radius=geometry['radius'];inset=p['C_s']+d/2+shape['side_inset_in'];bottom=p['C_b']+d/2+shape['end_raise_in']
            pockets=[(inset+radius,bottom+radius),(p['b']-inset-radius,bottom+radius)]
            bars=bar_positions(e,'P')
            rotations=hook_rotations(run)
            # The planar engagement test cannot certify a rotated hook. Keep
            # that end unresolved, while retaining tests of unchanged bends.
            engages=all(rotation or any(math.hypot(b['x']-cx,b['y']-cy)+(d+b['diameter'])/2<=radius+.03 for b in bars)
                        for (cx,cy),rotation in zip(pockets,rotations))
            # Top continuous bends must enclose a bar too (5.10.8.2.6a).
            top=p['h']-p['C_t']-d/2
            engages=engages and all(any(math.hypot(b['x']-cx,b['y']-(top-radius))+(d+b['diameter'])/2<=radius+.03 for b in bars) for cx,_ in pockets)
            if not engages: extra+=' End or continuous U bend does not enclose a drawn longitudinal bar.'
            if any(rotations):pending=True;extra+=' '+rotation_note(run)
        else:
            engages=s['closure_engages_bars'] or s['hoop_closure']=='lap_pair'
            if not engages: pending=True;extra+=' Hook engagement not confirmed.'
        unsupported=run['bar']>8 or angle not in (90,135)
        ratio=max(bend_min/shape['inside_diameter_in'],tail_ratio,le/max(available,1e-9),
                  2. if run['kind']=='pile_u' and not engages else 0.,2. if unsupported else 0.)
        issues=shape_issues(e,run)
        if issues:ratio=max(2.,ratio)
        row=dict(run=run['id'],kind=run['kind'],bar=run['bar'],angle=angle,
            bend_in=shape['inside_diameter_in'],bend_required_in=bend_min,tail_in=tail,
            tail_required_in=required_tail,embed_available_in=available,embed_required_in=le,
            closure_type=s['hoop_closure'] if run['kind']=='hoop' else 'hooks',tail_ratio=tail_ratio,
            closure_required_in=1.3*ld if run['kind']=='hoop' and s['hoop_closure']=='lap_pair' else required_tail,
            closure_available_in=s['closure_lap_in'] if run['kind']=='hoop' and s['hoop_closure']=='lap_pair' else tail,
            engagement_flag=2. if run['kind']=='pile_u' and not engages else 0.,
            unsupported_flag=2. if unsupported else 0.,shape_flag=2. if issues else 0.,
            extension_mode=extension_mode,
            ratio=ratio,pending=pending,notes=extra+' '+'; '.join(issues))
        rows.append(row)
        checks.append(_check('Status_transverse_development_'+run['id'],run['id']+' calculated anchorage / closure',ratio,
            f'{CODE} 5.10.2.1/.3, 5.10.8.2.6a/b/d. Bend {shape["inside_diameter_in"]:.3f}/{bend_min:.3f} in; '
            f'hook extension {tail:.3f}/{required_tail:.3f} in; midheight embedment {available:.3f}/{le:.3f} in. '+row['notes'],pending=pending))
    return rows,checks


def _aggregate(key,label,rows,field,basis,*,pending=False,inherit_pending=True):
    if not rows:return _check(key,label,'N/A',basis+' No applicable stations.',na=True)
    worst=max(rows,key=lambda r:r[field])
    location=worst.get('id',worst.get('face',''))
    return _check(key,label,worst[field],basis+f' Governing: {location}; ratio {worst[field]:.6g}.',
                  pending=pending or inherit_pending and any(r.get('pending',False) for r in rows),
                  pending_reasons=[reason for row in rows for reason in row.get('pending_reasons',())] if key.startswith('Chk_shear_') else ())


def surface_checks(e):
    """Each exposed face/direction; open U tails are not full-width bottom bars.

    The entire face is conservatively treated as exposed. No pile-contact or
    buried-face exemption is inferred. End-face mesh must be represented by the
    actual nearest closed hoop; additional undrawn grids receive no credit.
    """
    from .model import bar_positions,BAR_AREA,BAR_DIAMETER
    from .transverse import scheduled_bars,shape_parameters
    p=e.case['inputs'];s=settings(e.case);bars=bar_positions(e,'P')
    physical=scheduled_bars(e.case);runs={r['id']:r for r in e.case['transverse_detail']['runs']}
    required=min(.60,max(.11,1.30*p['b']*p['h']/(2*(p['b']+p['h'])*min(p['fy'],75))))
    # 10th edition p. 5-183 says "not less than 18", not "not more".
    code_spacing=12. if min(p['b'],p['h'])>36 else max(18.,3*min(p['b'],p['h']))
    limit=min(code_spacing,s['shrinkage_project_spacing_in']) if s['shrinkage_project_spacing_in'] else code_spacing
    rows=[]
    def add(face,direction,area,pitch,notes):
        rows.append(dict(face=face,direction=direction,provided_in2_ft=area,required_in2_ft=required,
            spacing_in=pitch,code_spacing_in=code_spacing,adopted_spacing_in=limit,
            area_ratio=required/max(area,1e-9),spacing_ratio=pitch/limit,notes=notes))
    for face,selected,width,axis in [
        ('Top',[b for b in bars if b['kind'].startswith('Top row 1')],p['b'],'x'),
        ('Bottom',[b for b in bars if b['kind'].startswith('Bottom row 1')],p['b'],'x'),
        ('Side left',[b for b in bars if b['kind']=='Skin' and b['x']<p['b']/2],p['h'],'y'),
        ('Side right',[b for b in bars if b['kind']=='Skin' and b['x']>p['b']/2],p['h'],'y')]:
        coords=sorted(b[axis] for b in selected)
        pitch=max([2*coords[0],2*(width-coords[-1]),*(v-u for u,v in zip(coords,coords[1:]))]) if coords else width
        add(face,'Longitudinal',sum(BAR_AREA[b['bar']] for b in selected)*12/width,pitch,
            'Continuous face bars only; corner/added bars not double-counted. Twice edge distance included conservatively.')
    for face in ('Top','Bottom','Side left','Side right'):
        selected=[b for b in physical if face!='Bottom' or b['kind']=='hoop']
        gaps=[(a,b,b['station_in']-a['station_in']) for a,b in zip(selected,selected[1:])]
        if gaps:
            rate=min(BAR_AREA[min(a['bar'],b['bar'])]*12/max(gap,1e-9) for a,b,gap in gaps)
            pitch=max(2*selected[0]['station_in'],2*(e.value('L_cap')-selected[-1]['station_in']),*(g for _,_,g in gaps))
        else:rate=0.;pitch=e.value('L_cap')
        add(face,'Transverse',rate,pitch,'Actual full-face bar crossings. Open U-bars omitted on the bottom face; their short tails do not cross its full width.')
    for face,near in [('End left',physical[:1]),('End right',physical[-1:])]:
        b=near[0] if near else None;closed=b is not None and b['kind']=='hoop'
        area=BAR_AREA[b['bar']] if closed else 0.
        d=BAR_DIAMETER[b['bar']] if b else 0.
        inset=shape_parameters(runs[b['run']])['side_inset_in'] if b else 0.
        add(face,'Vertical',2*area*12/p['b'],p['b']-2*p['C_s']-d-2*inset,
            'Two side legs of the nearest actual closed hoop; no undrawn end-face mesh credited.')
        add(face,'Horizontal',2*area*12/p['h'],p['h']-p['C_t']-p['C_b']-d,
            'Top and bottom legs of the nearest actual closed hoop; no undrawn end-face mesh credited.')
    basis=f'{CODE} 5.10.6-1/-2, pp. 5-182–183. Each face and direction. '
    return rows,[_aggregate('Chk_shrink_area','Actual face shrinkage / temperature area',rows,'area_ratio',basis),
        _aggregate('Chk_shrink_space','Actual face shrinkage / temperature spacing',rows,'spacing_ratio',basis+f'Code spacing {code_spacing:g} in; adopted project spacing {limit:g} in.')]


def actual_calculations(e):
    from .model import BAR_AREA,BAR_DIAMETER
    from .transverse import scheduled_bars,shape_parameters
    from .detailing import required_clear
    p=e.case['inputs'];s=settings(e.case)
    inventory=longitudinal_inventory(e);members,notice=source_members(e)
    regions=direct_regions(e,members,inventory)
    development,checks=transverse_development(e)
    dev={r['run']:r for r in development}
    unresolved={name:_anchorage_reason(row) for name,row in dev.items() if row['pending'] or row['ratio']>1+1e-8}
    physical=scheduled_bars(e.case);runs={r['id']:r for r in e.case['transverse_detail']['runs']}
    rows=[];longitudinal=[]
    for first,last in zip(physical,physical[1:]):
        left,right=first['station_in'],last['station_in'];pitch=right-left
        size=min(first['bar'],last['bar']);av=2*BAR_AREA[size];rate=av/max(pitch,1e-9)
        anchored=all(not dev[b['run']]['pending'] and dev[b['run']]['ratio']<=1+1e-8 for b in (first,last))
        pending=not anchored or s['continuous_splices']!='none'
        base_reasons=[unresolved[name] for name in dict.fromkeys(b['run'] for b in (first,last)) if name in unresolved]
        if s['continuous_splices']=='unknown':base_reasons.append('Continuous-bar splices are unconfirmed (LRFD regions & checks → Continuous-bar splices)')
        elif s['continuous_splices']=='present':base_reasons.append('Continuous-bar splices are present and require separate review')
        if not members:base_reasons.append(notice)
        closed=first['kind']==last['kind']=='hoop'
        widths=[p['b']-2*p['C_s']-BAR_DIAMETER[b['bar']]-2*shape_parameters(runs[b['run']])['side_inset_in'] for b in (first,last)]
        heights=[p['h']-p['C_t']-p['C_b']-BAR_DIAMETER[b['bar']] for b in (first,last)]
        aoh=min(w*h for w,h in zip(widths,heights));ao=.85*max(aoh,1e-9);ph=2*(min(widths)+min(heights))
        overlap=[m for m in members if m['left']<right-1e-8 and m['right']>left+1e-8]
        if not overlap:
            overlap=[dict(combo='envelope',element='envelope',left=left,right=right,nu=0.,tu=p['Tu'])]
        interval=[]
        for m in overlap:
            lo=max(left,m['left']);hi=min(right,m['right'])
            cuts={lo,hi}
            if m['combo']!='envelope':
                cuts.update(x for x in member_roots(m) if lo<x<hi)
                cuts.update(x for x in member_roots(m,'shear') if lo<x<hi)
                cuts.update(r['left_in'] for r in regions if r['combination']==m['combo'] and lo<r['left_in']<hi)
            for b in inventory:
                cuts.update(x for x in (b['straight_left_in'],b['straight_right_in'],b['left_in']+b['required_in'],b['right_in']-b['required_in']) if lo<x<hi)
            cuts=sorted(cuts)
            for a,b in zip(cuts,cuts[1:]):
                if b-a<1e-8:continue
                from .section_search import section,critical_search
                def at(x):
                    region=next((r for r in regions if r['combination']==m['combo'] and r['left_in']-1e-8<=x<=r['right_in']+1e-8),None)
                    if m['combo']=='envelope':
                        actions=[dict(moment=-p['Mu_N'],vu=max(p['Vu_G'],p['Vu_L']),nu=0.,tu=p['Tu']),
                                 dict(moment=max(p['Mu_P'],p['Mu_B']),vu=max(p['Vu_G'],p['Vu_L']),nu=0.,tu=p['Tu'])]
                    else:actions=[forces(m,x)]
                    return [section(e,q,x,inventory,physical,dev,rate,ao,ph,closed,region) for q in actions]
                # Separate scalar diagnostic faces; never envelope forces before
                # the nonlinear strain/theta calculation.
                for action_index in range(2 if m['combo']=='envelope' else 1):
                    if m['combo']=='envelope':
                        search_info=dict(converged=False,samples=3,refinements=0,
                            reason='Unresolved concurrent axial/source data; three diagnostic locations only')
                        points=[dict(at(x)[action_index],search=search_info) for x in (a,(a+b)/2,b)]
                    else:points,search_info=critical_search(lambda x:at(x)[action_index],a,b,physical)
                    for result in points:
                        x=result['station_in'];face=result['face']
                        origin=min(r['x_in'] for r in e.case['analysis']['xml_audit']['end_records']) if members else 0.
                        near_pile=any(abs(x-(v-origin))<=p['D_pile']/2 for v in e.case['analysis'].get('xml_audit',{}).get('pile_centers_in',[]))
                        group='N' if face=='top' else 'P' if near_pile else 'B'
                        ident=f'{first["id"]}/{last["id"]} · C{m["combo"]} E{m["element"]} · x={x:.6f} in · {face}'
                        reasons=[*base_reasons,*_shear_domain_reasons(p,result)]
                        window=result['window']
                        if result['developed_window_area_in2']<window['area_in2']-1e-8:
                            names=dict.fromkeys(bar['run'] for bar in physical if bar['id'] in window['bar_ids'] and bar['run'] in unresolved)
                            reasons.append('Shear window includes reinforcement without verified anchorage: '+', '.join(names))
                            reasons.extend(unresolved[name] for name in names)
                        if not search_info['converged']:reasons.append('Station D/C search did not converge; refine the search before acceptance')
                        if not members:reasons.append('N=0 only for unresolved scalar diagnostic; signed axial data and concurrent M/V/N/T require reimport')
                        point_pending=bool(reasons) or pending or not members or not result['valid']
                        common=dict(result,id=ident,group=group,combination=m['combo'],element=m['element'],
                            state=m.get('state','unresolved'),left_in=a,right_in=b,
                            raw_axial_i=m.get('raw_axial_i'),raw_axial_j=m.get('raw_axial_j'),
                            source_sha256=m.get('source_sha256'),axial_convention=m.get('axial_convention'),
                            axial_resolved=bool(members),pending=point_pending,pending_reasons=list(dict.fromkeys(reasons)),
                            basis=notice)
                        longitudinal.append(common)
                        interval.append(dict(common,ratio=result['shear_ratio']))
        if not interval:continue
        worst=max(interval,key=lambda r:r['ratio']);tor=max(interval,key=lambda r:r['tor_ratio'])
        spacing_limit=min(q['pitch_limit'] for q in interval);across_limit=min(q['across_limit'] for q in interval)
        clear=pitch-(BAR_DIAMETER[first['bar']]+BAR_DIAMETER[last['bar']])/2
        clearance=required_clear(e,max(BAR_DIAMETER[first['bar']],BAR_DIAMETER[last['bar']]))
        minimum=max(q['minimum_rate'] for q in interval)
        row=dict(worst,id=first['id']+' → '+last['id'],left_in=left,right_in=right,pitch_in=pitch,
            av_in2=av,rate_in2_in=rate,zone=first['zone'] if first['zone']==last['zone'] else 'G/L',
            tor_ratio=tor['tor_ratio'],torsion_required=any(q['torsion_required'] for q in interval),
            combined_required_rate=tor['combined_required_rate'],at_required_rate=tor['at_required_rate'],
            av_required_rate=max(q['av_required_rate'] for q in interval),
            across_in=max(widths),pitch_limit=spacing_limit,across_limit=across_limit,
            across_ratio=max(widths)/across_limit,
            spacing_ratio=max(pitch/spacing_limit,max(widths)/across_limit,minimum/rate),
            clear_in=clear,clear_required_in=clearance,clear_ratio=clearance/max(clear,1e-9),
            minimum_rate=minimum,min_ratio=max(q['minimum_rate']/max(q['effective_rate'],1e-9) for q in interval),anchored=anchored,pending=any(q['pending'] for q in interval),
            pending_reasons=list(dict.fromkeys(reason for q in interval for reason in q['pending_reasons'])),
            vr=min(q['vr'] for q in interval),vr_governing=worst['vr'],governing_segment=worst['id'],
            minimum_segment=max(interval,key=lambda q:q['minimum_rate']/max(q['effective_rate'],1e-9)),
            torsion_segment=tor)
        rows.append(row)
        suffix=first['id']+'_'+last['id']
        checks.extend([
            _check('Chk_actual_shear_'+suffix,row['id']+' shear',row['ratio'],
                f'{CODE} 5.7.3.3/5.7.3.4; FDOT 2026 SDG 4.1.4A actual legs intersected by dv cotθ. Vc={worst["vc"]:.4f}, Vs={worst["vs"]:.4f}, Vr={worst["vr"]:.4f} kip; β={worst["beta"]:.4f}, θ={worst["theta"]:.4f}°. Governing {worst["id"]}.',pending=row['pending'],pending_reasons=row['pending_reasons']),
            _check('Chk_actual_pitch_'+suffix,row['id']+' spacing',row['spacing_ratio'],
                f'5.7.2.6: pitch {pitch:.4f}/{spacing_limit:.4f} in; 5.7.2.5: adjacent Av/s {rate:.5f}, minimum {minimum:.5f} in²/in. FDOT 2026 SDG 4.1.4C across-leg spacing {max(widths):.4f}/{across_limit:.4f} in.'),
            _check('Chk_actual_clear_'+suffix,row['id']+' clear spacing',row['clear_ratio'],
                f'5.10.3.1.1 plus project minimum: clear {clear:.4f} in; required {clearance:.4f} in.'),
            _check('Chk_actual_min_'+suffix,row['id']+' minimum shear steel',row['min_ratio'],
                f'5.7.2.5-1 / FDOT 2026 4.1.4A: actual intersected steel / dv cotθ; minimum={minimum:.6f} in²/in.')])
    for z in 'GL':
        selected=[r for r in rows if z in r['zone']]
        for prefix,label,field in [('Chk_shear_','Actual shear · ','ratio'),('Chk_spacing_','Actual transverse spacing · ','spacing_ratio'),
            ('Chk_hoop_clear_','Actual transverse clear spacing · ','clear_ratio'),('Chk_drawn_hoop_legs_','Actual transverse leg spacing · ','across_ratio')]:
            checks.append(_aggregate(prefix+z,label+z,selected,field,'Actual adjacent stations; detailed operands in interval table.',inherit_pending=prefix=='Chk_shear_'))
        tor=[r for r in selected if r['torsion_required']]
        checks.append(_aggregate('Chk_torsteel_'+z,'Actual combined shear / torsion steel · '+z,tor,'tor_ratio',
            '5.7.3.6.1/.2: Av/s + 2At/s; open U-bars are not closed torsion paths.'))
    for group in 'NPB':
        selected=[r for r in longitudinal if r['group']==group]
        checks.append(_aggregate('Chk_long_'+group,'Actual longitudinal tension · '+group,selected,'ratio',
            '5.7.3.5-1 / 5.7.3.6.3-1. Actual developed tension-half steel; detailed region/force/calculation table.'))
    faces,face_checks=surface_checks(e);checks.extend(face_checks)
    hooks=[b for b in inventory if b['additional']]
    # Full development of the hook at the midpoint is a necessary geometric gate,
    # in addition to station-by-station reduced steel and cutoff extension checks.
    hook_ratio=max((b['required_in']/max((b['right_in']-b['left_in'])/2,1e-9) for b in hooks),default=0.)
    checks.append(_check('Status_hook_development','Added bars · calculated hook development',hook_ratio,
        '10th ed. 5.10.8.2.1 and 5.10.8.2.4a; hook lengths and reduced developed steel are calculated. Cutoff/extension beyond theoretical need and hook confinement still require the detailed bar schedule.',pending=bool(hooks)))
    checks.append(_check('Status_continuous_anchorage','Continuous bars · development / splices','N/A',
        'Straight-bar ld calculated for each actual bar; local credited area reduced for both ends. Splice state: '+s['continuous_splices']+'. Unmodeled splices cannot be accepted.',pending=s['continuous_splices']!='none'))
    checks.append(_check('Status_actual_torsion','Actual torsion applicability / path',max((r['tor_ratio'] for r in rows),default=0.),
        f'5.7.2.1 zero-axial investigation threshold {torsion_threshold(e):.4f} kip-ft; reduced locally for axial tension. Required torsion uses actual closed paths and 5.7.3.6. Open U-bars receive no torsion resistance.',
        pending=any(r['pending'] and r['torsion_required'] for r in rows),na=not any(r['torsion_required'] for r in rows)))
    checks.append(_check('Status_lrfd_source','Local force / LRFD applicability','N/A',notice+
        ' Concurrent section D/C values are enveloped after calculating strain, theta and actual reinforcement. Scalar diagnostics retain unresolved axial/source status.',pending=not members))
    checks.append(_check('Status_actual_review','D-regions / owner detailing requirements','N/A',
        'Sectional calculations do not replace 5.8 D-region/strut-and-tie checks at concentrated loads, embedded piles and end regions. FDOT 2026 SDG 4.1.4A–C is included; local 3D closure/congestion remains a drawing review.',pending=True))
    checks.append(_check('Status_lrfd_regions','Direct-loading region classification','N/A',
        f'{sum(r["qualifies"] for r in regions)} of {len(regions)} same-sign moment domains eligible. Every remaining domain is analyzed by the full equation. Unknown is never treated as direct.',pending=not regions or not s['load_path_basis'].strip()))
    checks.append(_check('Status_lrfd_end_regions','Outside the transverse schedule / end anchorage','N/A',
        'Sectional interval working covers the first through last physical transverse bars. The remaining cap-end cover zones, bearing faces and concentrated-load D-regions require an end-anchorage / local load-path detail; no capacity or direct-loading exemption is extrapolated there.',pending=True))
    checks.append(_check('Status_lrfd_domain','Actual-cage calculation domain','N/A',
        'Solid rectangular nonprestressed cap, perpendicular stirrups; shear fc ≤ 15 ksi, investigated torsion fc ≤ 10 ksi, fy ≤ 100 ksi. High-grade hook confinement and nonstandard bar details require separate verification.',
        pending=p['fpc']!=0 or p['fc']>15 or p['fy']>75))
    strain=max((r['epsilon'] or 0. for r in longitudinal),default=0.)
    checks.append(_check('Status_lrfd_strain','General shear procedure strain range','N/A',
        f'5.7.3.4.2: maximum calculated general-procedure strain {strain:.6g}. No strain clipping; values above 0.006 have no adopted resistance. Simplified epsilon is not required.',pending=strain>.006+1e-12))
    checks.append(_check('Status_lrfd_search','Concurrent station search convergence','N/A',
        'Member ends, moment roots/extrema, development transitions and moving transverse-window/branch events; D/C refinement tolerance 0.0002, event tolerance 0.000001 in.',
        pending=any(not r['search']['converged'] for r in longitudinal)))
    from .shear import CALCULATION_VERSION
    return dict(code=CODE,owner_code='FDOT Structures Design Guidelines, January 2026, 4.1.4A–C',
        calculation_version=CALCULATION_VERSION,
        engine_sha256=sha256(b''.join(Path(__file__).with_name(name).read_bytes() for name in ('lrfd_checks.py','shear.py','section_search.py','axial.py'))).hexdigest(),settings=s,source_notice=notice,regions=regions,inventory=inventory,
        transverse_development=development,intervals=rows,longitudinal=longitudinal,faces=faces),checks


REPLACED_PREFIXES=('Chk_shear_','Chk_spacing_','Chk_torsteel_','Chk_long_',
    'Chk_hoop_clear_','Chk_drawn_hoop_legs_','Chk_shrink_','Chk_actual_shear_',
    'Chk_actual_pitch_','Chk_actual_clear_','Chk_actual_min_','Status_transverse_development_')
REPLACED_KEYS={'Status_overall','Status_actual_torsion','Status_actual_review',
    'Status_hook_development','Status_continuous_anchorage','Chk_drawn_shrink_B'}


def apply_actual_checks(e):
    from .transverse import enabled
    if enabled(e.case):
        data,new=cached_calculations(e)
    else:
        # A uniform search has no entered station schedule. Evaluate an explicit
        # trial grid at the larger G/L pitch with the same sectional solver.
        # Never mutate the selected case or pretend these are confirmed bars.
        from copy import copy
        from .model import BAR_DIAMETER
        trial=copy(e);trial.case=deepcopy(e.case);p=e.case['inputs']
        db=BAR_DIAMETER[p['Bar_v']];start=p['C_s']+db/2
        trial.case['transverse_detail']=dict(version=1,enabled=True,runs=[dict(
            id='Uniform'+str(i+1),kind='hoop',bar=int(p['Bar_v']),zone='G',
            first_in=start,end_in=e.value('L_cap')-start,pitch_in=max(p['s_G'],p['s_L']),
            development_confirmed=False,development_basis='') for i in range(int(p['n_loop']))])
        data,new=cached_calculations(trial)
        data['transverse_basis']='Uniform reference trial: first bar at side cover + db/2; larger G/L pitch; actual schedule/closure requires confirmation'
        for row in data['intervals']:row['zone']='GL'
        # Both scalar zone screens use the same explicitly conservative trial.
        from copy import copy as shallow_copy
        for c in list(new):
            if c.key.endswith('_G') and c.key.startswith(('Chk_shear_','Chk_spacing_','Chk_torsteel_','Chk_hoop_clear_','Chk_drawn_hoop_legs_')):
                other=shallow_copy(c);other.key=c.key[:-1]+'L';other.label=c.label[:-1]+'L'
                new=[q for q in new if q.key!=other.key]+[other]
        new.append(_check('Status_uniform_schedule','Uniform reference station placement','N/A',data['transverse_basis'],pending=True))
    e.lrfd=data
    e.checks[:]=[c for c in e.checks if not c.key.startswith(REPLACED_PREFIXES) and c.key not in REPLACED_KEYS]+new
    pending=any('PENDING' in c.status or 'CONDITIONAL' in c.status for c in e.checks)
    failed=any('FAIL' in c.status for c in e.checks)
    from .model import Check
    e.checks.append(Check('Status_overall','Actual-cage check summary','FAIL' if failed else 'PENDING' if pending else 'PASS','N/A',
        'Collects actual-cage numerical results and outstanding applicability/detailing requirements. No reference result is treated as a passed check.'))


_CALCULATION_CACHE={}


def cached_calculations(e):
    """Bounded, input-exact cache; module reload discards all prior engine data."""
    import json
    from .shear import CALCULATION_VERSION
    key=sha256(json.dumps([CALCULATION_VERSION,id(transverse_development),e.case,e.value('dv'),e.value('Ec','ksi')],
        sort_keys=True,allow_nan=False).encode()).hexdigest()
    if key not in _CALCULATION_CACHE:
        if len(_CALCULATION_CACHE)>=8:_CALCULATION_CACHE.pop(next(iter(_CALCULATION_CACHE)))
        _CALCULATION_CACHE[key]=actual_calculations(e)
    return deepcopy(_CALCULATION_CACHE[key])
