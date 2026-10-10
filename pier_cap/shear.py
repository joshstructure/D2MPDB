"""One sectional solution for LRFD 2024 5.7.3.4 and 5.7.3.5.

All forces are already factored, in kip; lengths in inch; moment/torque
arguments in kip-ft. No resistance factor enters the strain calculation.
"""
import math
from .axial import NUMERICAL_ZERO_KIP

CALCULATION_VERSION = 'signed-concurrent-lrfd-2024-v1'


def compression_flange(e, action, compression_steel):
    """C5.7.3.4.2 Figs 3/4 idealized axial flanges, before flange cracking.

    This is the commentary flange model, not a gross-section elastic stress
    screen. Use actual M, NOT the artificial strain-equation moment floor.
    The flange's finite tensile limit is C5.4.2.7's estimated fct. Steel and
    net concrete share the flange force at equal strain up to that limit.
    """
    p=e.case['inputs'];dv=e.value('dv');ec=e.value('Ec','ksi')
    lam=e.case['lrfd_checks']['density_factor']
    force=.5*action['nu']+action['veff']-abs(action['moment'])*12/dv
    known=compression_steel is not None
    steel=sum(b['credited_area'] for b in compression_steel or [])
    gross_steel=sum(b['area']*(.5 if abs(b['y']-p['h']/2)<1e-8 else 1.) for b in compression_steel or [])
    concrete=p['b']*p['h']/2-gross_steel
    ft=.213*lam*math.sqrt(p['fc'])
    stiffness=ec*concrete+p['Es']*steel
    stress=force*ec/stiffness if stiffness>0 else None
    threshold=ft*stiffness/ec
    cracked=(action['nu']>NUMERICAL_ZERO_KIP and stress>=ft) if known and stress is not None else None
    return dict(model='C5.7.3.4.2 Figures 3/4: axial compression-half flange',
        source='5.7.3.4.2; C5.4.2.7 (estimated splitting tensile strength)',
        force_kip=force,concrete_area_in2=concrete,developed_steel_in2=steel,
        ec_ksi=ec,es_ksi=p['Es'],stress_ksi=stress,cracking_stress_ksi=ft,
        cracking_force_kip=threshold,actual_moment_kip_in=abs(action['moment'])*12,
        cracked=cracked,resolved=known and concrete>0 and stiffness>0,
        comparison='flange concrete tensile stress >= fct AND signed Nu > numerical zero',
        assumption='Elastic axial flange to first cracking; reduced developed steel stiffness; nonprestressed rectangle')


def crack_spacing(e, steel):
    """5.7.3.4.2-7 / Fig. 3, conservative face-to-layer terminal distances.

    Iteratively remove layers unable to supply 0.003*b*sx. Including the
    concrete faces as terminal boundaries overestimates the distance to the
    compression zone; it cannot award an optimistic small sx near a cutoff.
    """
    p=e.case['inputs'];dv=e.value('dv');layers={}
    for b in steel or []:
        y=round(b['y'],8);layers[y]=layers.get(y,0.)+b['credited_area']
    while True:
        ys=sorted({0.,p['h'],*layers})
        sx=min(dv,max(b-a for a,b in zip(ys,ys[1:])))
        eligible={y:a for y,a in layers.items() if a+1e-12>=.003*p['b']*sx}
        if eligible==layers:break
        layers=eligible
    aggregate=e.case['screening']['aggregate_in']
    return dict(sx_in=sx,sxe_in=max(12.,min(80.,1.38*sx/(aggregate+.63))),
        aggregate_in=aggregate,layers=[dict(y_in=y,area_in2=a) for y,a in sorted(layers.items())],
        source='5.7.3.4.2-7 and Figure 5.7.3.4.2-3; face terminal distances conservative')


def parameters(e, action, area, rate, ao=None, ph=None, *, compression_steel=None,
               all_steel=None, force_general=False, minimum_branch=None):
    from .lrfd_checks import torsion_threshold,settings
    p=e.case['inputs'];s=e.case.get('lrfd_checks') or settings(e.case);dv=e.value('dv');fc=p['fc']
    vu=action['vu'];nu=action['nu'];warnings=[]
    minimum=.0316*s['density_factor']*math.sqrt(fc)*p['b']/min(p['fy'],100.)
    threshold=torsion_threshold(e,nu)
    torsion=action['tu']>threshold
    if torsion and not (ao and ph):warnings.append('Torsion requires actual closed-path Ao and ph')
    veff=math.hypot(vu,.9*ph*action['tu']*12/(2*ao)) if torsion and ao and ph else vu
    # Eq. 4's shear term uses Veff (Eq. 5). The separately printed Mu
    # definition/floor remains |Vu - Vp|*dv; Vp=0 in this supported scope.
    moment_floor=vu*dv
    m_epsilon=max(abs(action['moment'])*12,moment_floor)
    numerator=m_epsilon/dv+.5*nu+veff
    base=numerator/(p['Es']*area) if area>0 else None
    adequate=rate+1e-12>=minimum if minimum_branch is None else minimum_branch
    eligible=nu<=NUMERICAL_ZERO_KIP and p['fpc']==0 and (adequate or p['h']<16.)
    reasons=[]
    if nu>NUMERICAL_ZERO_KIP:reasons.append('Net axial tension: ordinary simplified provision unavailable')
    if p['fpc']!=0:reasons.append('Prestress outside supported nonprestressed scope')
    if not adequate and p['h']>=16:reasons.append('Depth >= 16 in and less than minimum transverse reinforcement')
    simplified=eligible and not force_general
    crack=compression_flange(e,dict(action,veff=veff),compression_steel)
    if nu<=NUMERICAL_ZERO_KIP:
        crack['cracked']=False  # Axial-tension adjustment cannot be invoked by flexure alone.
    multiplier=2 if crack['cracked'] else 1
    negative=base is not None and base<0
    epsilon=None if simplified else max(0.,base or 0.)*multiplier
    if not simplified and area<=0:warnings.append('No developed steel on the flexural tension half')
    if not simplified and nu>NUMERICAL_ZERO_KIP and not crack['resolved']:
        warnings.append('Compression-half developed reinforcement required for the flange cracking check')
    if epsilon is not None and epsilon>.006+1e-12:warnings.append('Calculated strain exceeds 0.006; no admissible resistance adopted')
    if fc>(10 if torsion else 15):warnings.append('Concrete strength outside implemented shear/torsion domain')
    if p['fy']>100 or p['fpc']!=0:warnings.append('Steel grade/prestress outside implemented domain')
    spacing=crack_spacing(e,all_steel)
    if not simplified and not adequate and not e.case['screening'].get('aggregate_confirmed'):
        warnings.append('Confirm maximum aggregate size for the no-minimum-reinforcement beta calculation')
    if simplified:beta=2.;theta=45.
    else:
        beta=4.8/(1+750*epsilon)*(1 if adequate else 51/(39+spacing['sxe_in']))
        theta=29+3500*epsilon
    # Out-of-domain arithmetic is visible but never treated as resistance.
    cot=1/math.tan(math.radians(theta)) if 0<theta<90 else 0.
    vc=.0316*s['density_factor']*beta*math.sqrt(fc)*p['b']*dv
    vs=rate*min(p['fy'],100.)*dv*cot
    limit=.25*fc*p['b']*dv
    valid=not warnings
    diagnostic_vr=p['phi_v']*min(vc+vs,limit)
    vr=diagnostic_vr if valid or all('aggregate size' in w for w in warnings) else 0.
    stress=veff/(p['phi_v']*p['b']*dv)
    pitch=min(.8*dv,24.) if stress<.125*fc else min(.4*dv,12.)
    owner=vu/(p['phi_v']*p['b']*dv)
    across=42. if owner<=.08*math.sqrt(fc) else min(dv,24.) if owner<=.16*math.sqrt(fc) else min(.5*dv,12.)
    return dict(beta=beta,theta=theta,cot=cot,epsilon=epsilon,epsilon_base=base,
        epsilon_diagnostic=base if simplified else None,strain_multiplier=multiplier,
        negative_strain_treatment='zero permitted by 5.7.3.4.2' if negative else 'not needed',
        compression_face=crack,m_for_epsilon_kip_in=m_epsilon,moment_floor_kip_in=moment_floor,
        dv_in=dv,es_ksi=p['Es'],as_effective_in2=area,minimum_transverse=adequate,
        simplified_eligible=eligible,simplified_reason='; '.join(reasons) or 'Nonprestressed, no axial tension, transverse/depth criterion satisfied',
        vc=vc,vs=vs,vr=vr,adopted_vr=vr if valid else None,
        nominal_limit=limit,minimum_rate=minimum,pitch_limit=pitch,across_limit=across,
        method='5.7.3.4.1' if simplified else '5.7.3.4.2',valid=valid,
        torsion_required=torsion,threshold_kip_ft=threshold,veff=veff,
        applicability_warnings=warnings,**spacing)
