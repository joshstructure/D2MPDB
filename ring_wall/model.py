"""Transparent gravity STM study. Units are inch, kip, ksi unless noted.

No concrete tension, pipe bond, cap suspension, soil support or pipe-fill area
is credited. Local 3-D node, ring attachment and compatibility remain open.
"""
from copy import deepcopy
from math import atan, ceil, cos, degrees, floor, hypot, isfinite, pi, sin

BAR = {4: (.5, .20), 5: (.625, .31), 6: (.75, .44),
       7: (.875, .60), 8: (1., .79), 9: (1.128, 1.00), 10: (1.27, 1.27)}


def default_case():
    return dict(
        title='D2 I-95 | Pier wall on welded pile rings',
        length_in=213., thickness_in=36., height_in=172.375,
        pile_count=4, pile_spacing_in=60., pile_od_in=20.,
        pile_t_effective_in=.475, placement_tolerance_in=3.,
        cover_in=3., aggregate_in=.75,
        fc_ksi=5.5, fy_ksi=60., density_kcf=.150, gamma_dc=1.25,
        additional_service_ksf=0., gamma_additional=1.75,
        phi_tie=.90, phi_concrete=.70,
        first_ring_in=6., ring_spacing_in=36., ring_count=5,
        arch_rise_in=10., arch_panels=4, tie_offset_in=2.,
        node_height_in=4., node_width_in=16.,
        grid_bar=5, auto_grid_spacing=True, grid_spacing_in=5.,
        spacing_increment_in=.5, primary_bar=5,
        primary_bars_per_face=1, hanger_bars_per_face=1,
        u_leg_in=72., coating='uncoated',
        ring_id_in=20.125, ring_od_in=23., ring_t_in=.75,
        ring_fy_ksi=50., phi_plate=.90, bearing_fraction=.50,
        transverse_bar=4, transverse_spacing_in=8.,
    )


def validate(p):
    for name, value in p.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not isfinite(value) or value < 0:
                raise ValueError(f'{name}: use a finite nonnegative value.')
    for name in ('length_in','thickness_in','height_in','pile_spacing_in',
                 'pile_od_in','pile_t_effective_in','fc_ksi','fy_ksi','density_kcf',
                 'gamma_dc','gamma_additional','ring_spacing_in','arch_rise_in',
                 'node_height_in','node_width_in','grid_spacing_in',
                 'spacing_increment_in','u_leg_in','ring_t_in','ring_fy_ksi',
                 'transverse_spacing_in'):
        if p[name] <= 0: raise ValueError(f'{name} must be positive.')
    for name in ('pile_count','ring_count','arch_panels','primary_bars_per_face',
                 'hanger_bars_per_face'):
        if type(p[name]) is not int or p[name] < 1:
            raise ValueError(f'{name} must be a positive integer.')
    if p['pile_count'] < 2 or p['arch_panels'] < 2 or p['arch_panels'] % 2:
        raise ValueError('Use at least two piles and an even number of arch panels >= 2.')
    if p['arch_panels'] > 40 or p['ring_count'] > 40 or p['pile_count'] > 20:
        raise ValueError('Study limits: 40 arch panels/rows and 20 piles.')
    for name in ('grid_bar','primary_bar','transverse_bar'):
        if p[name] not in BAR: raise ValueError(f'{name}: supported bars are #4 through #10.')
    for name in ('phi_tie','phi_concrete','phi_plate','bearing_fraction'):
        if not 0 < p[name] <= 1: raise ValueError(f'{name} must be in (0, 1].')
    if p['coating'] not in ('uncoated','epoxy','unknown'):
        raise ValueError('Coating must be uncoated, epoxy, or unknown.')
    if p['pile_od_in'] >= p['thickness_in']:
        raise ValueError('Wall must be thicker than pile OD for this two-face idealization.')
    if p['ring_id_in'] <= p['pile_od_in'] or p['ring_od_in'] <= p['ring_id_in']:
        raise ValueError('Require ring OD > ring ID > pile OD; include fabrication clearance.')
    if p['pile_t_effective_in'] >= p['pile_od_in']/2:
        raise ValueError('Effective pipe wall must be less than its radius.')
    if p['length_in'] <= (p['pile_count']-1)*p['pile_spacing_in']:
        raise ValueError('Centered pile row must fit inside the wall length.')
    last=p['first_ring_in']+(p['ring_count']-1)*p['ring_spacing_in']
    if p['first_ring_in'] <= p['ring_t_in'] or last >= p['height_in']:
        raise ValueError('Ring top elevations must lie inside the wall; first ring above plate thickness.')
    if p['fc_ksi'] > 15 or p['fy_ksi'] > 75:
        raise ValueError('This study supports normalweight concrete fc <= 15 ksi and fy <= 75 ksi.')
    if p['thickness_in'] <= 18:
        raise ValueError('This wall implementation is for thickness > 18 in (12-in S&T spacing limit).')
    if p['node_width_in'] > p['thickness_in']-p['pile_od_in']:
        raise ValueError('Equivalent node width cannot exceed t_wall - D_pile; no pipe-fill credit.')


def development(db, area, p, top=False):
    """LRFD 10th 5.10.8.2.1: straight bar, full yield, no confinement credit.

    Fh=0, lambda_er=lambda_rc=lambda_density=1. Coating is adverse for unknown.
    Basic length = 0.17 db [fy/(1.97 fc^0.25)]^2, not the older edition formula.
    """
    basic=.17*db*(p['fy_ksi']/(1.97*p['fc_ksi']**.25))**2
    coating=1. if p['coating']=='uncoated' else 1.5
    factor=min(1.7, (1.3 if top else 1.)*coating)
    ld=max(12.,basic*factor)
    return dict(basic=basic,factor=factor,ld=ld,lap_b=1.3*ld,area=area)


def arch(w, length, rise, panels):
    """Discrete parabolic funicular polygon for uniform gravity w (kip/in).

    w*dx at interior joints, half at endpoints. Exact joint equilibrium.
    Vertically moving a tributary load to its joint requires collectors; the
    model separately designs vertical hanger steel for the FULL tributary load.
    """
    dx=length/panels
    x=[i*dx for i in range(panels+1)]
    y=[4*rise*a*(length-a)/length**2 for a in x]
    tie=w*length**2/(8*rise)
    segments=[]
    for i in range(panels):
        slope=(y[i+1]-y[i])/dx
        v=tie*slope
        segments.append(dict(i=i,x1=x[i],x2=x[i+1],y1=y[i],y2=y[i+1],
                             vertical=v,C=hypot(tie,v),angle=degrees(atan(abs(slope)))))
    joint_loads=[w*dx*(.5 if i in (0,panels) else 1.) for i in range(panels+1)]
    residuals=[]
    for i in range(panels+1):
        fx=fz=0.
        if i>0: fx+=tie; fz+=segments[i-1]['vertical']
        if i<panels: fx-=tie; fz-=segments[i]['vertical']
        if i==0: fx+=tie; fz+=w*length/2
        if i==panels: fx-=tie; fz+=w*length/2
        fz-=joint_loads[i]
        residuals.append((fx,fz))
    # Horizontal tie intersects only the end struts. Vertical ties intersect
    # internal struts; check the acute angle at all relevant intersections.
    intersections=[segments[0]['angle'],segments[-1]['angle']]
    for i in range(1,panels):
        intersections.extend([90-segments[i-1]['angle'],90-segments[i]['angle']])
    return dict(x=x,y=y,tie=tie,segments=segments,joint_loads=joint_loads,
                residual=max(hypot(*r) for r in residuals),
                minimum_angle=min(intersections),reaction=w*length/2,
                max_C=max(s['C'] for s in segments),hanger=max(joint_loads))


def analyze(case=None):
    p=deepcopy(default_case() if case is None else case)
    validate(p)
    L,t,H=p['length_in'],p['thickness_in'],p['height_in']
    n,S,D=p['pile_count'],p['pile_spacing_in'],p['pile_od_in']
    end=(L-(n-1)*S)/2
    pile_x=[end+i*S for i in range(n)]
    z=[p['first_ring_in']+i*p['ring_spacing_in'] for i in range(p['ring_count'])]
    bounds=[0.]+[(a+b)/2 for a,b in zip(z[:-1],z[1:])]+[H]
    heights=[b-a for a,b in zip(bounds[:-1],bounds[1:])]
    min_depth=min(heights)
    # Evaluate both orthogonal gross sections, and conservatively use their
    # envelope in both directions. No steel is subtracted for pipe voids.
    st_L=max(.11,min(.60,1.30*t*L/(2*(t+L)*min(p['fy_ksi'],75.))))
    st_H=max(.11,min(.60,1.30*t*H/(2*(t+H)*min(p['fy_ksi'],75.))))
    st=max(st_L,st_H)
    stm=.003*t*12/2
    required=max(st,stm)
    candidates=[]
    for bar in (4,5,6,7,8):
        db,ab=BAR[bar]
        d=min_depth-p['cover_in']-db/2
        spacing_limit=min(12.,d/4)
        raw=min(spacing_limit,12*ab/required)
        step=p['spacing_increment_in']
        spacing=floor((raw+1e-10)/step)*step
        clear_req=max(1.5*db,1.5*p['aggregate_in'],1.5)
        candidates.append(dict(bar=bar,db=db,ab=ab,spacing=spacing,
                               spacing_limit=spacing_limit,d=d,
                               provided=12*ab/spacing if spacing>0 else 0,
                               feasible=spacing>0 and spacing-db>=clear_req))
    db,ab=BAR[p['grid_bar']]
    selected=next((a for a in candidates if a['bar']==p['grid_bar']),None)
    if selected is None:
        d=min_depth-p['cover_in']-db/2
        raw=min(12.,d/4,12*ab/required)
        selected=dict(spacing=floor(raw/p['spacing_increment_in'])*p['spacing_increment_in'])
    spacing=selected['spacing'] if p['auto_grid_spacing'] else p['grid_spacing_in']
    if spacing<=0: raise ValueError('No positive grid spacing fits the shallowest band; revise row layout.')
    d=min_depth-p['cover_in']-db/2
    spacing_limit=min(12.,d/4)
    provided=12*ab/spacing
    dev_h=development(db,ab,p,top=True)
    dev_v=development(db,ab,p,top=False)
    primary_db,primary_ab=BAR[p['primary_bar']]
    primary_dev_h=development(primary_db,primary_ab,p,top=True)
    primary_dev_v=development(primary_db,primary_ab,p,top=False)
    tie_capacity=p['phi_tie']*p['fy_ksi']*2*p['primary_bars_per_face']*primary_ab
    hanger_capacity=p['phi_tie']*p['fy_ksi']*2*p['hanger_bars_per_face']*primary_ab
    u_inside_bend=(6 if p['grid_bar']<=8 else 8)*db
    u_width=t-2*p['cover_in']
    end_vertical_count=ceil((t-2*p['cover_in']-db)/spacing)+1
    end_vertical_pitch=(t-2*p['cover_in']-db)/(end_vertical_count-1)
    grid=dict(bar=p['grid_bar'],db=db,area=ab,spacing=spacing,st_L=st_L,st_H=st_H,
              st=st,stm=stm,required=required,provided=provided,d=d,
              spacing_limit=spacing_limit,candidates=candidates,
              development_h=dev_h,development_v=dev_v,
              u_inside_bend=u_inside_bend,u_width=u_width,
              end_vertical_count=end_vertical_count,end_vertical_pitch=end_vertical_pitch)
    checks=[]
    def ck(key,title,demand,capacity,unit,ref,scope='CHECK',note=''):
        ratio=demand/capacity if capacity>0 else None
        checks.append(dict(id=key,title=title,demand=demand,capacity=capacity,
                           unit=unit,ratio=ratio,status='PASS' if ratio is not None and ratio<=1+1e-9 else 'FAIL',
                           ref=ref,scope=scope,note=note))
    ck('GRID-A','Grid steel, each direction / each broad face',required,provided,'in²/ft',
       'LRFD 5.10.6; 5.8.2.6')
    ck('GRID-S','Grid center spacing',spacing,spacing_limit,'in','LRFD 5.8.2.6',
       note='d = shallowest assigned band height minus cover and half bar diameter; review D-region depth.')
    ck('GRID-CLEAR','Same-layer clear distance',max(1.5*db,1.5*p['aggregate_in'],1.5),
       spacing-db,'in','LRFD 5.10.3.1.1')
    ck('U-LAP','End U-bar straight leg / Class B lap allowance',dev_h['lap_b'],p['u_leg_in'],
       'in','LRFD 5.10.8.2.1; 5.10.8.4.3','SCREEN',
       'Leg length is measured from bend tangent. Final noncontact lap geometry and stagger remain open.')
    ck('U-BEND','Minimum U-bar bend envelope across thickness',u_inside_bend+2*db,u_width,
       'in','LRFD 5.10.2','SCREEN','Rectangular U with two 90° bends; not a development check.')
    ck('NODE-TIE','Tie centroid at node mid-height',abs(p['tie_offset_in']-p['node_height_in']/2),
       1e-6,'in','Entered finite-node geometry','GEOMETRY')
    rp=p['pile_od_in']/2; ri=p['ring_id_in']/2; ro=p['ring_od_in']/2
    A=pi*(ro**2-ri**2); I=pi/4*(ro**4-ri**4); eta=p['bearing_fraction']
    tol=p['placement_tolerance_in']; cover=p['cover_in']
    edge_clear=end-ro-tol; face_clear=t/2-ro-tol
    grid_gap=t/2-cover-2*db-ro-tol
    ck('RING-END','Ring outer edge / wall-end cover',cover,edge_clear,'in','Entered cover and pile tolerance','FIT')
    ck('RING-FACE','Ring outer edge / broad-face cover',cover,face_clear,'in','Entered cover and pile tolerance','FIT')
    ck('RING-GRID','Ring clearance to innermost face-grid steel',
       max(1.,1.5*p['aggregate_in']),grid_gap,'in','Trial placement clearance','FIT',
       'Worst radial envelope; horizontal bars outside vertical bars. No credit for rebar weaving.')
    wc_service=p['density_kcf']*(t/12)/144 + p['additional_service_ksf']/144
    wc_u=p['gamma_dc']*p['density_kcf']*(t/12)/144 + p['gamma_additional']*p['additional_service_ksf']/144
    rows=[]; ring_forces=[]
    for k,(zr,lo,hi,bh) in enumerate(zip(z,bounds[:-1],bounds[1:],heights),1):
        w=wc_u*bh; ws=wc_service*bh
        a=arch(w,S,p['arch_rise_in'],p['arch_panels'])
        service=arch(ws,S,p['arch_rise_in'],p['arch_panels'])
        nu=.45  # deliberately conservative: no elevated efficiency credit for uncertain local topology
        fcu=nu*p['fc_ksi']; bw=p['node_width_in']
        # Each interior ring receives two bays. Allocate half the assumed active
        # annulus to each bay; this is a screening allocation, not a 3-D node solution.
        lb=eta*A/(2*bw)
        theta=a['segments'][0]['angle']*pi/180
        wn=lb*sin(theta)+p['node_height_in']*cos(theta)
        node_area=bw*wn
        node_capacity=p['phi_concrete']*fcu*node_area
        band_d=bh-cover-db/2
        # LRFD C5.8.2.2 shear-cracking estimate; gross regional bw=t, not an annular breakout rule.
        coefficient=max(.0632,min(.158,.2-.1*(S/2)/band_d)) if band_d>0 else 0
        vcr=coefficient*p['fc_ksi']**.5*t*max(band_d,0)
        arch_top=zr+p['tie_offset_in']+p['arch_rise_in']
        fit_top=hi-cover-wn/2
        end_W=w*end
        end_M=end_W*end/2
        # End strip is a separate cantilever/local-node demand. It is NOT silently
        # inserted into the bay arch. Ring/pile moments explicitly close equilibrium.
        end_tie=end_M/p['arch_rise_in']
        row=dict(row=k,z=zr,lo=lo,hi=hi,height=bh,w=w,ws=ws,arch=a,
                 service_arch=service,weight=w*L,service_weight=ws*L,
                 lb=lb,wn=wn,node_area=node_area,node_capacity=node_capacity,
                 vcr=vcr,arch_top=arch_top,fit_top=fit_top,
                 end_weight=end_W,end_moment=end_M,end_tie=end_tie)
        rows.append(row)
        ck(f'R{k}-T','Bay horizontal tie',a['tie'],tie_capacity,'kip','LRFD 5.8.2.4.1','STRENGTH')
        ck(f'R{k}-V','Interior vertical collector tie',a['hanger'],hanger_capacity,'kip','LRFD 5.8.2.4.1','STRENGTH',
           'Dedicated bars for full tributary column weight. Grid is not double-counted.')
        ck(f'R{k}-V-NODE','Collector at pile node / end strip',
           w*max(S/p['arch_panels'],S/(2*p['arch_panels'])+end),hanger_capacity,
           'kip','LRFD 5.8.2.4.1','STRENGTH',
           'Full joint tributary weight including overhang; anchorage into the actual support node is open.')
        ck(f'R{k}-END-T','Wall-end cantilever tie demand',end_tie,tie_capacity,'kip',
           'T = M / entered lever arm','SCREEN','End-zone topology and anchorage are not resolved by this force screen.')
        ck(f'R{k}-ANGLE','Minimum strut-to-tie angle (strictly >25°)',25.000001,a['minimum_angle'],'deg',
           'LRFD 5.8.2.2','GEOMETRY')
        ck(f'R{k}-NODE','Equivalent strut-to-node face',a['max_C'],node_capacity,'kip',
           'LRFD 5.8.2.5; nu=0.45, m=1','SCREEN','Annulus-to-planar-node mapping requires 3-D substantiation.')
        ck(f'R{k}-CRACK','Bay service shear / diagonal-cracking estimate',service['reaction'],vcr,'kip',
           'LRFD C5.8.2.2-1','SCREEN','Service estimate for assigned wall band, not local ring punching.')
        ck(f'R{k}-FIT','Arch plus finite strut half-width inside band',arch_top,fit_top,'in above wall bottom',
           'Entered node geometry','FIT')
        for j,xp in enumerate(pile_x):
            outer=j in (0,n-1)
            R=w*(S/2+end if outer else S)
            # Signed support couple on wall: opposite sides cancel globally.
            M=-end_M if j==0 else end_M if j==n-1 else 0.
            qmax=R/(eta*A)+abs(M)*ro/(eta*I)
            qmin=R/(eta*A)-abs(M)*ro/(eta*I)
            # Radial cantilever strip per inch circumference at pipe OD; ID gap
            # remains part of lever arm but carries no concrete pressure.
            m=qmax*((ro**3-ri**3)/(3*rp)-(ro**2-ri**2)/2)
            plate_capacity=p['phi_plate']*p['ring_fy_ksi']*p['ring_t_in']**2/6
            t_req=(6*m/(p['phi_plate']*p['ring_fy_ksi']))**.5
            weld_vertical=R/(2*pi*rp)+abs(M)/(pi*rp**2)
            ring=dict(row=k,pile=j+1,x=xp,z=zr,R=R,M=M,qmax=qmax,qmin=qmin,
                      m_per_in=m,plate_capacity=plate_capacity,t_req=t_req,
                      weld_vertical_per_in=weld_vertical,
                      pipe_membrane_ksi=weld_vertical/p['pile_t_effective_in'])
            ring_forces.append(ring)
            ck(f'R{k}-P{j+1}-BEAR','Annular concrete bearing pressure',qmax,p['phi_concrete']*fcu,
               'ksi','LRFD 5.8.2.5; nu=0.45, m=1','SCREEN',
               'Reduced annulus A and I; active contact must be established separately.')
            ck(f'R{k}-P{j+1}-CONTACT','No tension under assumed annular contact',
               abs(M)*ro/(eta*I),R/(eta*A),'ksi','Elastic annular pressure distribution','SCREEN')
            ck(f'R{k}-P{j+1}-PLATE','Ring radial strip elastic bending',m,plate_capacity,'kip-in/in',
               'Elastic cantilever strip; entered steel factor','SCREEN','Not a complete annular-plate/weld/shell limit-state check.')
    weight=sum(r['weight'] for r in rows)
    totalR=sum(a['R'] for a in ring_forces)
    force_error=totalR-weight
    moment_error=sum(a['R']*a['x']+a['M'] for a in ring_forces)-weight*L/2
    pending=[
        ('BASIS','Confirm wall geometry, cover, mix, exposure/coating, pile tolerance and governing FDOT/project criteria. C006 dimensions are a study snapshot; current cap uses 3-in pile tolerance.'),
        ('LOADS','Gravity/self-weight only. Confirm cap isolation, lateral wind/impact/water/soil, construction, seismic, shrinkage and all applicable combinations.'),
        ('SHARING','Mid-height tributary boundaries are an assumed strength load allocation, not a stiffness/contact solution. Establish compatibility and a credible reaction envelope for all ring rows.'),
        ('NODE-3D','Resolve actual front/back struts around the hollow pipe, active annular contact, splitting, spalling, breakout/punching and group/edge effects. No assumed concrete cone is a support.'),
        ('END-ZONE','Develop an end-strip STM or local continuum model carrying the reported cantilever moment and shear into each outer ring. The bay arch does not solve the overhang.'),
        ('ANCHORAGE','Anchor dedicated horizontal ties and collectors at the actual extended nodes; check lower-wall suspension, U-bar laps, bend bearing, congestion and transverse confinement. Available node development is not yet established.'),
        ('STEEL','Complete weld group including radial plate-root moment/prying, ring split splices, fatigue if applicable, pile-shell local bending/ovalization, effective corrosion thickness and global pile actions.'),
        ('DETAIL','Resolve ring/grid clashes and end cover at pile tolerance; detail through-thickness ties around the pipe and access for concrete placement/welding.'),
    ]
    overall='REVISE TRIAL — NOT RELEASED' if any(c['status']=='FAIL' for c in checks) else 'PRELIMINARY — OPEN CHECKS'
    return dict(case=p,grid=grid,pile_x=pile_x,end=end,rows=rows,rings=ring_forces,
                checks=checks,pending=pending,overall=overall,
                geometry=dict(ring_area=A,ring_I=I,edge_clear=edge_clear,face_clear=face_clear,
                              grid_gap=grid_gap,bounds=bounds),
                steel=dict(tie_capacity=tie_capacity,hanger_capacity=hanger_capacity,
                           primary_dev_h=primary_dev_h,primary_dev_v=primary_dev_v),
                totals=dict(service_weight=sum(a['service_weight'] for a in rows),
                            factored_weight=weight,ring_reactions=totalR,
                            force_error=force_error,moment_error=moment_error,
                            joint_error=max(r['arch']['residual'] for r in rows)))
