"""Concurrent section evaluation and convergence-controlled station search."""
import math


def section(e, action, x, inventory, physical, dev, rate, ao, ph, closed, region=None):
    from .lrfd_checks import steel_at,shear_parameters,window_steel,settings
    p=e.case['inputs'];s=e.case.get('lrfd_checks') or settings(e.case);dv=e.value('dv')
    face='top' if action['moment']<0 else 'bottom'
    tension=steel_at(inventory,x,p['h'],face)
    compression=steel_at(inventory,x,p['h'],'bottom' if face=='top' else 'top')
    area=sum(b['credited_area'] for b in tension)
    kwargs=dict(compression_steel=compression,all_steel=tension+compression)
    # The general angle does not depend on the minimum-steel beta branch.
    # Resolve its window first, then select beta from that very window. There
    # is consequently no stale one-pass minimum-steel classification.
    general=shear_parameters(e,action,area,rate,ao,ph,force_general=True,**kwargs)
    general_length=max(1e-8,dv*general['cot'])
    w45=window_steel(physical,x,x,dv)
    simple=shear_parameters(e,action,area,min(rate,w45['area_in2']/dv),ao,ph,**kwargs)
    if simple['method']=='5.7.3.4.1':params=simple;window=w45
    else:
        window=window_steel(physical,x,x,general_length)
        params=shear_parameters(e,action,area,min(rate,window['area_in2']/general_length),ao,ph,force_general=True,**kwargs)
    # Eligibility belongs to the 45-degree candidate, even if the general
    # method's different window happens to satisfy minimum reinforcement.
    params['simplified_eligible']=simple['simplified_eligible']
    params['simplified_reason']=simple['simplified_reason']+' (45-degree transverse window)'
    effective_rate=window['area_in2']/window['length_in']
    developed=window_steel(physical,x,x,window['length_in'],dev)
    params['vs']=window['area_in2']*min(p['fy'],100.)
    params['vr']=p['phi_v']*min(params['vc']+params['vs'],params['nominal_limit']) if params['valid'] or all('aggregate size' in w for w in params['applicability_warnings']) else 0.
    params['adopted_vr']=params['vr'] if params['valid'] else None
    credit=min(developed['area_in2']*min(p['fy'],100.),action['vu']/p['phi_v'])
    shear_tension=max(0.,action['vu']/p['phi_v']-.5*credit)
    torsion_tension=.45*ph*action['tu']*12/(2*ao*p['phi_v']) if params['torsion_required'] else 0.
    phi_m=p['phi_v'] if params['torsion_required'] else p['phi_f']
    phi_n=p['phi_v'] if params['torsion_required'] else s['phi_axial']
    moment_tension=abs(action['moment'])*12/(phi_m*dv)
    axial_tension=.5*action['nu']/phi_n
    diagonal=params['cot']*math.hypot(shear_tension,torsion_tension)
    full=max(0.,moment_tension+axial_tension+diagonal)
    applies=bool(region and region['qualifies'] and not params['torsion_required'])
    cap=region['peak_moment_kip_ft']*12/(p['phi_f']*dv) if applies else full
    main=sum(b['credited_area'] for b in tension if not b['additional'] and b['kind']!='Skin')
    applies=applies and main*p['fy']+1e-8>=cap
    demand=min(full,cap) if applies else full
    capacity=area*p['fy']
    av=max(params['minimum_rate'],max(0,action['vu']/p['phi_v']-params['vc'])/(p['fy']*max(dv*params['cot'],1e-9)))
    at=action['tu']*12/(2*ao*p['phi_v']*p['fy']*max(params['cot'],1e-9)) if params['torsion_required'] else 0.
    tor=(av+2*at)/max(min(rate,effective_rate),1e-9) if params['torsion_required'] and closed else 2. if params['torsion_required'] else 0.
    return dict(**action,**params,station_in=x,face=face,steel_area_in2=area,
        general_window_length_in=general_length,window=window,effective_rate=effective_rate,
        developed_window_area_in2=developed['area_in2'],vs_credited_kip=credit,
        long_theta=params['theta'],full_tension_kip=full,required_tension_kip=demand,
        capacity_kip=capacity,ratio=demand/max(capacity,1e-9),
        shear_ratio=max(action['vu']/max(params['vr'],1e-9),params['veff']/p['phi_v']/params['nominal_limit']),
        inverse_resistance=1/max(params['vr'],1e-9),
        minimum_ratio=params['minimum_rate']/max(effective_rate,1e-9),
        moment_tension_kip=moment_tension,axial_tension_kip=axial_tension,
        shear_tension_kip=shear_tension,torsion_tension_kip=torsion_tension,diagonal_tension_kip=diagonal,
        exception_applied=applies,classification='DIRECT — flexural maximum limit' if applies else 'FULL INTERACTION',
        av_required_rate=av,at_required_rate=at,combined_required_rate=av+2*at,
        ao_in2=ao,ph_in=ph,closed=closed,torsion_ratio=tor,tor_ratio=tor,
        transverse_basis='FDOT 2026 SDG 4.1.4A: actual twin legs in centered dv cot(theta) window')


def signature(r):
    return (r['method'],r['minimum_transverse'],r['compression_face']['cracked'],r['sx_in'],
        r['torsion_required'],r['valid'],r['face'],tuple(r['window']['bar_ids']))


def critical_search(evaluate, left, right, physical, *, tolerance=2e-4, max_levels=7):
    """Refined concurrent D/C envelopes with explicit moving-window events.

    Caller splits at all moment extrema/zeros, member ends and development
    transitions. Start with <=0.5 in spacing; require at least two refinements
    (<=0.125 in) and two successive envelope agreements. Track four independent
    D/C objectives, not force envelopes. Bracket branch/window events and retain
    both sides to 1e-6 in. Nonconvergence is a prerequisite, never a PASS.
    """
    cache={};fields=('ratio','shear_ratio','minimum_ratio','torsion_ratio','inverse_resistance')
    def at(x):
        x=max(left,min(right,x))
        if x not in cache:cache[x]=evaluate(x)
        return cache[x]
    def bisect(lo,hi,fun):
        flo=fun(at(lo));fhi=fun(at(hi))
        if flo*fhi>0:return None
        for _ in range(36):
            mid=(lo+hi)/2;fm=fun(at(mid))
            if hi-lo<1e-6:break
            if flo*fm<=0:hi=mid
            else:lo=mid;flo=fm
        x=(lo+hi)/2
        for dx in (-2e-6,0,2e-6):at(x+dx)
        return x
    n=max(2,math.ceil((right-left)/.5));previous=None;stable=0;converged=False
    event_points=set();max_change=None
    for level in range(max_levels):
        points=[left+(right-left)*i/n for i in range(n+1)]
        for x in points:at(x)
        # Locate actual 45-degree and calculated-angle window entries/exits.
        # Only nearby bars can cross within each subinterval.
        if level==0:
            for lo,hi in zip(points,points[1:]):
                a,b=at(lo),at(hi)
                for bar in physical:
                    station=bar['station_in']
                    for sign in (-1,1):
                        def fun(r,station=station,sign=sign):
                            return r['station_in']+sign*r['general_window_length_in']/2-station
                        if fun(a)*fun(b)<=0:
                            root=bisect(lo,hi,fun)
                            if root is not None:event_points.add(root)
                    for sign in (-1,1):
                        root=station+sign*a['dv_in']/2
                        if lo<=root<=hi:
                            event_points.add(root)
                            for dx in (-2e-6,0,2e-6):at(root+dx)
        # Branch changes can move the window discontinuously (cracking, minimum
        # steel, simplified eligibility, torsion threshold, applicability).
        for lo,hi in zip(points,points[1:]):
            if signature(at(lo))==signature(at(hi)):continue
            stack=[(lo,hi)]
            while stack:
                a,b=stack.pop()
                if b-a<1e-6:
                    event_points.update((a,b));continue
                m=(a+b)/2;at(m)
                if signature(at(a))!=signature(at(m)):stack.append((a,m))
                if signature(at(m))!=signature(at(b)):stack.append((m,b))
        maxima=[max(r[f] for r in cache.values()) for f in fields]
        if previous is not None:
            max_change=max(abs(a-b)/max(1,abs(a)) for a,b in zip(maxima,previous))
            stable=stable+1 if max_change<=tolerance else 0
        if level>=2 and stable>=2:converged=True;break
        previous=maxima;n*=2
    # Polish interior candidates inside the final grid brackets. Golden search
    # is local only; the refined full-span sweep supplies independent brackets.
    for field in fields:
        for i in range(1,len(points)-1):
            if at(points[i])[field]<=max(at(points[i-1])[field],at(points[i+1])[field]):continue
            lo,hi=points[i-1],points[i+1]
            for _ in range(24):
                a=hi-(hi-lo)*.61803398875;b=lo+(hi-lo)*.61803398875
                if at(a)[field]<at(b)[field]:lo=a
                else:hi=b
            at((lo+hi)/2)
    retained={left,right}
    for field in fields:retained.add(max(cache,key=lambda x:cache[x][field]))
    # One trace per distinct branch, plus both sides of all resolved events.
    by_branch={}
    for x,r in cache.items():by_branch.setdefault(signature(r),x)
    retained.update(by_branch.values());retained.update(event_points)
    meta=dict(converged=converged,samples=len(cache),refinements=level,
        final_spacing_in=(right-left)/n,relative_dc_tolerance=tolerance,
        last_relative_change=max_change,event_tolerance_in=1e-6,event_count=len(event_points))
    return [dict(at(x),search=meta) for x in sorted(retained)],meta
