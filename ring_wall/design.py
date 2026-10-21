"""Wall minimum steel and annular pile-ring gravity design; inch, kip, ksi.

Midplane tributaries allocate vertical force only. Ring moments come from the
pile-head rotational stiffness against the rigid-wall rotation, with the placement
tolerance applied as a rigid-body pile-group redistribution (D-070, 21 October 2026).
The former tributary-eccentricity moment is kept in the ledger for comparison only.
The equation ledger drives the disclosures and independently checked native sheets.
"""
from copy import deepcopy
from math import floor, isfinite, pi, sqrt

BAR = {4: (.5,.20), 5: (.625,.31), 6: (.75,.44), 7: (.875,.60), 8: (1.,.79), 9: (1.128,1.), 10: (1.27,1.27)}
LEGACY = {'arch_rise_in','arch_panels','tie_offset_in','node_height_in','node_width_in','primary_bar',
 'primary_bars_per_face','hanger_bars_per_face','transverse_bar','transverse_spacing_in','support_model',
 'cone_slope_hv','phi_tie','bearing_fraction','additional_service_ksf','gamma_additional'}


SCHEMA=3
# Schema 3 (D-070): pile stiffness inputs for the compatibility ring moment.
# Defaults follow the pier pile case: 20-in pipe, 16.3 in exposed below the wall plus
# 110.7 in sand depth to fixity (LRFD C10.7.3.13.4); tip elevation pending, so the axial
# spring length is a stated 600-in allowance (softer spring = larger rotation = conservative moment).
STIFFNESS_DEFAULTS=dict(pile_e_ksi=29000.,pile_free_length_in=127.,pile_axial_length_in=600.,imposed_rotation_rad=0.)
ZERO_ALLOWED={'placement_tolerance_in','imposed_rotation_rad'}
D070_NOTE='Ring moment basis D-070: the ring moment now follows pile-head stiffness against wall rotation, with the tolerance as a pile-group redistribution. Pile stiffness inputs use visible defaults from the pier pile case. Review and Recalc.'


def default_case():
    return dict(schema_version=SCHEMA,title='D2 I-95 | Wall steel and welded pile rings',
        length_in=213.,thickness_in=36.,height_in=172.375,pile_count=4,pile_spacing_in=60.,pile_od_in=20.,
        pile_t_effective_in=.475,pile_fy_ksi=50.,pile_fu_ksi=65.,placement_tolerance_in=3.,**STIFFNESS_DEFAULTS,
        cover_in=3.,required_cover_in=3.,aggregate_in=.75,fc_ksi=5.5,fy_ksi=60.,density_kcf=.150,gamma_dc=1.25,
        first_ring_in=6.,ring_spacing_in=36.,ring_count=5,grid_bar=5,auto_grid_spacing=True,grid_spacing_in=6.,
        spacing_increment_in=.5,project_max_spacing_in=12.,u_leg_in=72.,vertical_lap_in=60.,coating='uncoated',
        ring_id_in=20.125,ring_od_in=23.,ring_t_in=.75,ring_fy_ksi=50.,ring_fu_ksi=65.,weld_leg_in=.3125,
        weld_fexx_ksi=70.,phi_concrete=.70,phi_plate=1.,phi_weld=.80,phi_shear_yield=1.,phi_shear_rupture=.80)


def upgrade_case(case=None):
    if case is None: return default_case(),[]
    if not isinstance(case,dict): raise ValueError('Load a ring-wall case JSON object.')
    p=deepcopy(case);notes=[]
    if 'schema_version' not in p:
        if not {'length_in','height_in','ring_count','pile_count','grid_bar'} <= set(p):
            raise ValueError('Not a recognized ring-wall case.')
        if p.get('additional_service_ksf',0):
            raise ValueError('Legacy case has added gravity. This revision uses concrete self-weight only; resolve that load before migration.')
        notes=['Legacy case migrated: geometry/materials retained; STM/cone and reduced-contact inputs removed. New weld/detail inputs use visible defaults. Review and Recalc.',D070_NOTE]
        p={**default_case(),**{k:v for k,v in p.items() if k not in LEGACY},'schema_version':SCHEMA}
    elif p.get('schema_version')==2 and not set(STIFFNESS_DEFAULTS)&set(p) and set(p)|set(STIFFNESS_DEFAULTS)==set(default_case()):
        notes.append(D070_NOTE)
        p={**p,**STIFFNESS_DEFAULTS,'schema_version':SCHEMA}
    if set(p)!=set(default_case()) or p['schema_version']!=SCHEMA: raise ValueError(f'Expected complete ring-wall schema version {SCHEMA}.')
    validate(p)
    return p,notes


def validate(p):
    for k,default in default_case().items():
        if k not in p: raise ValueError('Missing input: '+k)
        v=p[k]
        if type(default) is bool:
            if type(v) is not bool: raise ValueError(k+': expected true or false.')
        elif type(default) in (int,float):
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v): raise ValueError(k+': expected finite number.')
            if v<0 or (v==0 and k not in ZERO_ALLOWED): raise ValueError(k+': must be positive (tolerance and imposed rotation may be zero).')
            if type(default) is int and type(v) is not int: raise ValueError(k+': expected integer.')
        elif not isinstance(v,str): raise ValueError(k+': expected text.')
    if p['coating'] not in ('uncoated','epoxy','unknown'): raise ValueError('Invalid coating.')
    if p['grid_bar'] not in BAR: raise ValueError('Supported grid bars: #4 through #10.')
    if not 1<=p['pile_count']<=20 or not 1<=p['ring_count']<=40: raise ValueError('Study limits: 1–20 piles and 1–40 ring rows.')
    if p['schema_version']!=SCHEMA: raise ValueError(f'Expected schema version {SCHEMA}.')
    if p['imposed_rotation_rad']>.05: raise ValueError('Imposed wall rotation above 0.05 rad is outside the small-rotation model.')
    for k in ('phi_concrete','phi_plate','phi_weld','phi_shear_yield','phi_shear_rupture'):
        if p[k]>1: raise ValueError(k+': must not exceed 1.')
    if p['fc_ksi']>15 or p['fy_ksi']>75: raise ValueError('Normalweight concrete f′c ≤ 15 ksi; rebar fy ≤ 75 ksi.')
    if p['pile_od_in']>=p['thickness_in']: raise ValueError('Wall thickness must exceed pile diameter.')
    if p['pile_t_effective_in']>=p['pile_od_in']/2: raise ValueError('Pipe wall must be less than its radius.')
    if not p['ring_od_in']>p['ring_id_in']>p['pile_od_in']: raise ValueError('Require ring OD > ring ID > pile OD.')
    if p['length_in']<=(p['pile_count']-1)*p['pile_spacing_in']: raise ValueError('Pile centers must fit wall length.')
    last=p['first_ring_in']+(p['ring_count']-1)*p['ring_spacing_in']
    if p['first_ring_in']<=p['ring_t_in'] or last>=p['height_in']: raise ValueError('Ring top elevations must be inside wall, with plate thickness above bottom.')
    if p['ring_count']>1 and p['ring_spacing_in']<=p['ring_t_in']+2*p['weld_leg_in']: raise ValueError('Adjacent plates/welds overlap.')
    if 2*p['cover_in']+4*BAR[p['grid_bar']][0]>=min(p['thickness_in'],p['height_in'],p['length_in']): raise ValueError('Cover and face mats do not fit.')
    if p['weld_leg_in']<=(p['ring_id_in']-p['pile_od_in'])/2: raise ValueError('Weld leg must exceed radial root gap.')
    if p['pile_od_in']/2+p['weld_leg_in']>=p['ring_od_in']/2: raise ValueError('Top weld occupies all horizontal bearing width.')
    if p['ring_fu_ksi']<p['ring_fy_ksi'] or p['pile_fu_ksi']<p['pile_fy_ksi']: raise ValueError('Steel Fu must be at least Fy.')


def geometry(p):
    end=(p['length_in']-(p['pile_count']-1)*p['pile_spacing_in'])/2
    x=[end+i*p['pile_spacing_in'] for i in range(p['pile_count'])]
    z=[p['first_ring_in']+i*p['ring_spacing_in'] for i in range(p['ring_count'])]
    return dict(end=end,pile_x=x,ring_z=z,x_bounds=[0.]+[(a+b)/2 for a,b in zip(x,x[1:])]+[p['length_in']],
                z_bounds=[0.]+[(a+b)/2 for a,b in zip(z,z[1:])]+[p['height_in']])


def steel_layout(p):
    db,ab=BAR[p['grid_bar']];t,L,H=p['thickness_in'],p['length_in'],p['height_in']
    st_L=max(.11,min(.60,1.3*t*L/(2*(t+L)*p['fy_ksi'])))
    st_H=max(.11,min(.60,1.3*t*H/(2*(t+H)*p['fy_ksi'])))
    # Adopt the general wall/slab maximum as well as the thick-member limit.
    # This is deliberately no less restrictive than the surface-steel provision.
    required=max(st_L,st_H);code=min(1.5*t,12. if t>36 else 18.)
    limit=min(code,p['project_max_spacing_in']);raw=min(limit,12*ab/required)
    s=floor((raw+1e-10)/p['spacing_increment_in'])*p['spacing_increment_in'] if p['auto_grid_spacing'] else p['grid_spacing_in']
    if s<=0: raise ValueError('Spacing increment produces no positive bar spacing.')
    return dict(bar=p['grid_bar'],db=db,area=ab,st_L=st_L,st_H=st_H,required=required,
                code_limit=code,spacing_limit=limit,spacing=s,provided=12*ab/s)


def analyze(case=None):
    p,migration=upgrade_case(case);g=geometry(p);steel=steel_layout(p)
    nodes=[];v={};checks=[]
    # Only internally constructed expressions are evaluated. Case strings never enter expressions.
    def n(name,expr,unit='—',label=''):
        if name in v: raise ValueError('Duplicate equation '+name)
        value=float(eval(expr,{'__builtins__':{}},dict(v,min=min,max=max,abs=abs,sqrt=sqrt,IF=lambda a,b,c:b if a else c)))
        if not isfinite(value): raise ValueError('Nonfinite result '+name)
        v[name]=value;nodes.append(dict(name=name,expr=expr,value=value,unit=unit,label=label or name.replace('_',' ')))
        return value
    for k,value in p.items():
        if type(value) in (int,float): n(k,repr(value),'in' if k.endswith('_in') else 'ksi' if k.endswith('_ksi') else 'rad' if k.endswith('_rad') else 'kip/ft³' if k=='density_kcf' else '—')
    n('pi_value',repr(pi))
    def ck(key,title,d,c,unit,ref,note='',valid=True):
        ratio=v[d]/v[c] if v[c]>0 else None
        status=('PASS' if v[c]>0 and v[d]<=v[c]+1e-9 else 'FAIL') if valid else 'PENDING'
        checks.append(dict(id=key,title=title,demand=v[d],capacity=v[c],unit=unit,ratio=ratio,status=status,ref=ref,
                           note=note,demand_node=d,capacity_node=c))
    n('bar_diameter',repr(steel['db']),'in','Selected diameter; regenerate native sheet after bar-size changes')
    n('bar_area',repr(steel['area']),'in²')
    n('steel_L','max(0.11,min(0.60,1.3*thickness_in*length_in/(2*(thickness_in+length_in)*fy_ksi)))','in²/ft')
    n('steel_H','max(0.11,min(0.60,1.3*thickness_in*height_in/(2*(thickness_in+height_in)*fy_ksi)))','in²/ft')
    n('steel_required','max(steel_L,steel_H)','in²/ft','Both directions / each face; gross-section envelope')
    n('code_pitch','min(1.5*thickness_in,IF(thickness_in>36,12,18))','in','Conservative wall/slab and thick-member spacing envelope')
    n('pitch_limit','min(code_pitch,project_max_spacing_in)','in')
    n('selected_pitch',repr(steel['spacing']),'in','Adopted pitch; fixed input in distilled sheets')
    n('steel_provided','12*bar_area/selected_pitch','in²/ft')
    n('clear_required','max(1.5,1.5*bar_diameter,1.5*aggregate_in)','in')
    n('clear_provided','selected_pitch-bar_diameter','in')
    n('coating_factor',repr(1. if p['coating']=='uncoated' else 1.5))
    n('ld_basic','0.17*bar_diameter*(fy_ksi/(1.97*fc_ksi**0.25))**2','in','Normalweight; no confinement credit')
    n('ld_horizontal','max(12,ld_basic*min(1.7,1.3*coating_factor))','in','Conservative top-cast factor')
    n('ld_vertical','max(12,ld_basic*coating_factor)','in')
    n('lap_horizontal','1.3*ld_horizontal','in');n('lap_vertical','1.3*ld_vertical','in')
    n('bend_envelope','IF(grid_bar<=8,6,8)*bar_diameter+2*bar_diameter','in')
    n('u_width','thickness_in-2*cover_in','in')
    n('u_leg_available','length_in-2*cover_in-2*bar_diameter','in')
    n('vertical_available','height_in-2*cover_in-2*bar_diameter','in')
    steel.update(development_h=dict(ld=v['ld_horizontal'],lap_b=v['lap_horizontal']),development_v=dict(ld=v['ld_vertical'],lap_b=v['lap_vertical']))
    for key,title,d,c,unit,ref in [
        ('GRID-A','Minimum steel, both directions / each face','steel_required','steel_provided','in²/ft','LRFD 5.10.6-1/-2'),
        ('GRID-S','Grid center spacing','selected_pitch','pitch_limit','in','LRFD 5.10.3.2 / 5.10.6; conservative envelope; project cap'),
        ('GRID-CLEAR','Same-layer clear spacing','clear_required','clear_provided','in','LRFD 5.10.3.1.1'),
        ('COVER','Concrete clear cover','required_cover_in','cover_in','in','Entered project exposure/cover requirement'),
        ('U-LAP','End U-bar straight leg / Class B lap','lap_horizontal','u_leg_in','in','LRFD 5.10.8.2.1; 5.10.8.4.3'),
        ('U-FIT','U-bar leg fits wall','u_leg_in','u_leg_available','in','Geometric envelope'),
        ('U-BEND','U-bar bend fits thickness','bend_envelope','u_width','in','LRFD 5.10.2'),
        ('V-LAP','Vertical Class B lap allowance','lap_vertical','vertical_lap_in','in','LRFD 5.10.8.2.1; 5.10.8.4.3'),
        ('V-FIT','Vertical lap fits height','vertical_lap_in','vertical_available','in','Geometric envelope')]: ck(key,title,d,c,unit,ref)
    n('pipe_radius','pile_od_in/2','in');n('inner_radius','ring_id_in/2','in');n('outer_radius','ring_od_in/2','in')
    n('root_gap','inner_radius-pipe_radius','in')
    n('bearing_inner','max(inner_radius,pipe_radius+weld_leg_in)','in','Horizontal bearing excludes upper weld footprint')
    n('bearing_area','pi_value*(outer_radius**2-bearing_inner**2)','in²')
    n('bearing_inertia','pi_value*(outer_radius**4-bearing_inner**4)/4','in⁴')
    n('bearing_limit','phi_concrete*0.85*fc_ksi','ksi','No supporting-area enhancement; m = 1')
    n('plate_capacity','phi_plate*ring_fy_ksi*ring_t_in**2/6','kip-in/in','Elastic radial cantilever strip')
    n('plate_shear_capacity','phi_shear_yield*0.58*ring_fy_ksi*ring_t_in','kip/in')
    n('weld_throat','(weld_leg_in-root_gap)/sqrt(2)','in','Conservative fit-up allowance; WPS must permit gap')
    n('weld_capacity','phi_weld*0.6*weld_fexx_ksi*weld_throat','kip/in','One continuous fillet; no directional enhancement')
    n('thicker_part','max(ring_t_in,pile_t_effective_in)','in')
    n('minimum_thick_weld','IF(thicker_part<=0.75,0.25,0.3125)','in')
    n('minimum_mid_weld','IF(thicker_part<=0.5,0.1875,minimum_thick_weld)','in')
    n('minimum_table_weld','IF(thicker_part<=0.25,0.125,minimum_mid_weld)','in')
    n('weld_minimum','min(minimum_table_weld,ring_t_in,pile_t_effective_in)','in')
    n('weld_min_gap','weld_minimum+root_gap','in')
    n('weld_maximum','IF(ring_t_in<0.25,ring_t_in,ring_t_in-0.0625)','in','Ring edge limit; pipe is a face, not free edge')
    n('weld_length','2*pi_value*pipe_radius','in','Each of two continuous circumferential welds')
    n('weld_length_min','max(4*weld_leg_in,1.5)','in')
    n('ring_base_capacity','phi_shear_rupture*0.58*ring_fu_ksi*ring_t_in','kip/in')
    n('pipe_base_capacity','phi_shear_rupture*0.58*pile_fu_ksi*pile_t_effective_in','kip/in')
    n('pipe_yield_capacity','phi_shear_yield*0.58*pile_fy_ksi*pile_t_effective_in','kip/in')
    ck('WELD-MIN','Minimum fillet plus fit-up allowance','weld_min_gap','weld_leg_in','in','LRFD Table 6.13.3.4-1; conservative gap allowance')
    ck('WELD-MAX','Maximum fillet at ring edge','weld_leg_in','weld_maximum','in','LRFD 6.13.3.4')
    ck('WELD-LENGTH','Minimum effective weld length','weld_length_min','weld_length','in','LRFD 6.13.3.5')
    n('end_offset','(length_in-(pile_count-1)*pile_spacing_in)/2','in')
    n('end_clear','end_offset-outer_radius-placement_tolerance_in','in')
    n('face_clear','thickness_in/2-outer_radius-placement_tolerance_in','in')
    n('grid_gap','thickness_in/2-cover_in-2*bar_diameter-outer_radius-placement_tolerance_in','in')
    n('ring_grid_required','max(1,1.5*aggregate_in)','in')
    ck('RING-END','Ring edge / end cover at tolerance','required_cover_in','end_clear','in','Entered cover and tolerance')
    ck('RING-FACE','Ring edge / face cover at tolerance','required_cover_in','face_clear','in','Entered cover and tolerance')
    ck('RING-GRID','Ring clearance to inner face-grid layer','ring_grid_required','grid_gap','in','Placement envelope','Two orthogonal layers per face; no weaving credit.')
    n('bottom_ring_cover','first_ring_in-ring_t_in-weld_leg_in','in')
    n('top_ring_cover','height_in-first_ring_in-(ring_count-1)*ring_spacing_in-weld_leg_in','in')
    ck('RING-BOTTOM','Bottom weld / bottom cover','required_cover_in','bottom_ring_cover','in','Entered cover envelope')
    ck('RING-TOP','Top weld / top cover','required_cover_in','top_ring_cover','in','Entered cover envelope')
    if p['pile_count']>1:
        n('between_rings','pile_spacing_in-ring_od_in-2*placement_tolerance_in','in')
        ck('RING-SPACING','Adjacent pile rings / placement clearance','ring_grid_required','between_rings','in','Worst relative pile-placement tolerance')
    n('weight_density','density_kcf*thickness_in/1728','kip/in²','Gross concrete prism; no pipe/plate displacement deduction')
    n('factored_density','gamma_dc*weight_density','kip/in²')
    service=n('total_service','weight_density*length_in*height_in','kip')
    factored=n('total_factored','gamma_dc*total_service','kip')
    # D-070 compatibility basis: the rigid wall rotates on axial and rotational pile springs.
    n('pipe_inner_radius','pipe_radius-pile_t_effective_in','in','Effective pipe wall')
    n('pipe_area','pi_value*(pipe_radius**2-pipe_inner_radius**2)','in²')
    n('pipe_inertia','pi_value*(pipe_radius**4-pipe_inner_radius**4)/4','in⁴')
    n('pile_axial_stiffness','pipe_area*pile_e_ksi/pile_axial_length_in','kip/in','Axial spring over the entered effective length')
    n('pile_rotational_stiffness','4*pile_e_ksi*pipe_inertia/pile_free_length_in','kip-in/rad','Head translation restrained; bound of the fixed-base cantilever family')
    n('group_centroid','end_offset+(pile_count-1)*pile_spacing_in/2','in')
    n('group_second_moment','pile_spacing_in**2*pile_count*(pile_count**2-1)/12','in²','Equally spaced piles; zero for one pile')
    n('tolerance_rotation','total_factored*placement_tolerance_in/(pile_axial_stiffness*group_second_moment+pile_count*pile_rotational_stiffness)','rad','Pile group displaced by the tolerance relative to the wall centroid')
    n('wall_rotation','tolerance_rotation+imposed_rotation_rad','rad','Applied to every pile head')
    n('pile_head_moment','pile_rotational_stiffness*wall_rotation','kip-in','Compatibility moment at one pile head')
    n('ring_moment','pile_head_moment/ring_count','kip-in','Shared equally by the ring rows; no shaft-bearing credit')
    n('kern_limit','bearing_inertia/(bearing_area*outer_radius)','in','Equivalent eccentricity at which full contact is lost')
    rows=[];rings=[]
    for k,(z,lo,hi) in enumerate(zip(g['ring_z'],g['z_bounds'],g['z_bounds'][1:]),1):
        pre=f'row_{k}_'
        n(pre+'lo','0' if k==1 else f'first_ring_in+({k}-1.5)*ring_spacing_in','in')
        n(pre+'hi','height_in' if k==p['ring_count'] else f'first_ring_in+({k}-0.5)*ring_spacing_in','in')
        bh=n(pre+'height',pre+'hi-'+pre+'lo','in')
        n(pre+'share',pre+'height/height_in','—','Row tributary fraction of the wall height')
        rows.append(dict(row=k,z=z,lo=lo,hi=hi,height=bh,weight=v['factored_density']*bh*p['length_in'],service_weight=v['weight_density']*bh*p['length_in']))
        for j,(x,xlo,xhi) in enumerate(zip(g['pile_x'],g['x_bounds'],g['x_bounds'][1:]),1):
            a=f'ring_{k}_{j}_'
            n(a+'x',f'end_offset+({j}-1)*pile_spacing_in','in')
            n(a+'lo','0' if j==1 else f'end_offset+({j}-1.5)*pile_spacing_in','in')
            n(a+'hi','length_in' if j==p['pile_count'] else f'end_offset+({j}-0.5)*pile_spacing_in','in')
            n(a+'width',a+'hi-'+a+'lo','in')
            n(a+'volume',f'{a}width*{pre}height*thickness_in/1728','ft³')
            n(a+'service',f'density_kcf*{a}volume','kip');n(a+'force',f'gamma_dc*{a}service','kip')
            n(a+'eccentricity',f'({a}lo+{a}hi)/2-{a}x','in','Retained for whole-wall equilibrium; carried by the wall, not the ring')
            n(a+'superseded_moment',f'{a}force*(abs({a}eccentricity)+placement_tolerance_in)','kip-in','Superseded tributary-eccentricity basis (D-070); comparison only')
            n(a+'tolerance_force',f'{pre}share*pile_axial_stiffness*wall_rotation*abs({a}x-group_centroid)','kip','Rigid-body axial redistribution; sign taken to increase the ring force')
            n(a+'design_force',f'{a}force+{a}tolerance_force','kip')
            n(a+'equivalent_e',f'ring_moment/{a}design_force','in','Compare with the kern limit')
            n(a+'qavg',f'{a}design_force/bearing_area','ksi');n(a+'qmoment',f'ring_moment*outer_radius/bearing_inertia','ksi')
            n(a+'qmax',f'{a}qavg+{a}qmoment','ksi');n(a+'qmin',f'{a}qavg-{a}qmoment','ksi')
            n(a+'root_moment',f'{a}qmax*((outer_radius**3-bearing_inner**3)/(3*pipe_radius)-(outer_radius**2-bearing_inner**2)/2)','kip-in/in','Peak pressure over full radial strip')
            n(a+'root_shear',f'{a}qmax*(outer_radius**2-bearing_inner**2)/(2*pipe_radius)','kip/in')
            n(a+'thickness_bending',f'sqrt(6*{a}root_moment/(phi_plate*ring_fy_ksi))','in')
            n(a+'thickness_shear',f'{a}root_shear/(phi_shear_yield*0.58*ring_fy_ksi)','in')
            n(a+'thickness_required',f'max({a}thickness_bending,{a}thickness_shear,weld_leg_in+0.0625)','in','Bending, shear and conservative weld-edge allowance; revise/recalculate after selecting thickness')
            n(a+'weld_radial',f'{a}root_moment/ring_t_in','kip/in','Top/bottom weld couple separated conservatively by plate thickness')
            n(a+'weld_resultant',f'sqrt(({a}root_shear/2)**2+{a}weld_radial**2)','kip/in','Per fillet: half vertical shear + full radial couple force')
            n(a+'weld_strength_leg',f'root_gap+sqrt(2)*{a}weld_resultant/(phi_weld*0.6*weld_fexx_ksi)','in')
            n(a+'weld_required',f'max({a}weld_strength_leg,weld_min_gap)','in','Strength and minimum detailing; revise/recalculate after selecting weld')
            valid=v[a+'qmin']>=-1e-10;key=f'R{k}-P{j}'
            ck(key+'-CONTACT','Full annular compression contact',a+'qmoment',a+'qavg','ksi','Elastic annulus; qmin ≥ 0')
            for suffix,title,d,c,unit,ref in [
                ('BEAR','Concrete bearing',a+'qmax','bearing_limit','ksi','LRFD 5.6.5; 5.5.4.2, m = 1'),
                ('PLATE','Ring elastic bending',a+'root_moment','plate_capacity','kip-in/in','Radial cantilever mechanics; LRFD 6.5.4.2'),
                ('SHEAR','Ring shear yielding',a+'root_shear','plate_shear_capacity','kip/in','LRFD 6.13.5.2'),
                ('WELD','Each top/bottom continuous fillet',a+'weld_resultant','weld_capacity','kip/in','LRFD 6.13.3.2.4; 6.5.4.2'),
                ('RING-BASE','Ring base metal at weld',a+'weld_resultant','ring_base_capacity','kip/in','LRFD 6.13.5.3'),
                ('PIPE-YIELD','Pipe shear yielding at weld',a+'weld_resultant','pipe_yield_capacity','kip/in','LRFD 6.13.5.2; effective pipe wall'),
                ('PIPE-BASE','Pipe base metal at weld',a+'weld_resultant','pipe_base_capacity','kip/in','LRFD 6.13.5.3; effective pipe wall')]:
                ck(key+'-'+suffix,title,d,c,unit,ref,'' if valid else 'Full contact fails. Values are trial values; resolve partial contact before accepting bearing, plate or weld results.',valid)
            get=lambda s:v[a+s]
            rings.append(dict(row=k,pile=j,x=x,z=z,xlo=xlo,xhi=xhi,lo=lo,hi=hi,width=get('width'),height=bh,
                volume_ft3=get('volume'),service=get('service'),R=get('force'),e_nominal=get('eccentricity'),
                M_nominal=get('force')*get('eccentricity'),M_superseded=get('superseded_moment'),dR=get('tolerance_force'),R_design=get('design_force'),
                M=v['ring_moment'],e_equivalent=get('equivalent_e'),qmax=get('qmax'),qmin=get('qmin'),m_per_in=get('root_moment'),
                v_per_in=get('root_shear'),t_req=get('thickness_required'),t_bending_req=get('thickness_bending'),weld_demand=get('weld_resultant'),weld_capacity=v['weld_capacity'],
                weld_req=get('weld_required'),contact_ok=valid,bearing_ratio=get('qmax')/v['bearing_limit'],plate_ratio=get('root_moment')/v['plate_capacity'],weld_ratio=get('weld_resultant')/v['weld_capacity']))
    pending=[('SHARING','Midplane tributaries assign vertical force and the ring rows share the pile-head moment equally; all rings are assumed to engage. Concrete transfer (including concrete below rings), splitting/breakout and row compatibility need a separately substantiated load path.'),
        ('STIFFNESS','Ring moments follow pile-head rotational stiffness against the rigid-wall rotation (D-070). The free length to fixity and the axial spring length are entered values (defaults from the pier pile case with sand depth to fixity, LRFD 10.7.3.13.4; tip elevation pending). Lateral, thermal, unsymmetric and construction-stage rotations enter only through the imposed rotation input.'),
        ('SCOPE','Wall checks cover minimum shrinkage/temperature steel and detailing only. Wall flexure, shear, lateral loads, seismic and strength load paths are outside this calculation.'),
        ('CONNECTION','Local plate and double-fillet checks do not establish pipe-shell bending/ovalization, global pile interaction, ring-segment splices, fatigue, corrosion or WPS/fabrication adequacy.'),
        ('BASIS','Confirm geometry, exposure/cover, material grades, construction joints and bar anchorage routing. Starting dimensions are the earlier study snapshot, not a current CAD import.')]
    failed=sum(c['status']=='FAIL' for c in checks)
    return dict(case=p,migration=migration,geometry=g,grid=steel,rows=rows,rings=rings,checks=checks,nodes=nodes,pending=pending,
        totals=dict(service_weight=service,factored_weight=factored,force_error=sum(r['R'] for r in rings)-factored,
            moment_error=sum(r['R']*r['x']+r['M_nominal'] for r in rings)-factored*p['length_in']/2,
            wall_rotation=v['wall_rotation'],pile_head_moment=v['pile_head_moment'],ring_moment=v['ring_moment'],kern_limit=v['kern_limit']),
        overall=f'{failed} FAILED CHECKS · LIMITED SCOPE' if failed else 'NUMERICAL CHECKS SATISFIED · LIMITED SCOPE')
