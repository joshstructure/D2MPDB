"""Offline mathematical notation for the calculation ledger, not a second solver."""
import ast
from html import escape
import re


# Symbol, physical meaning. Ring/row indices belong to the worked-example caption.
TERMS = {
 'length_in':('L','Wall length'), 'height_in':('H','Wall height'), 'thickness_in':('t_w','Wall thickness'),
 'pile_count':('n_p','Number of piles'), 'pile_spacing_in':('s_p','Pile center spacing'),
 'pile_od_in':('D_p','Pipe outside diameter'), 'pile_t_effective_in':('t_eff','Effective pipe wall thickness'),
 'placement_tolerance_in':('Δ_p','Radial pile-placement tolerance'), 'first_ring_in':('z_1','First plate-top elevation'),
 'pile_e_ksi':('E_p','Pipe steel modulus'), 'pile_free_length_in':('L_f','Pile length from the wall bottom to the equivalent point of fixity'),
 'pile_axial_length_in':('L_a','Effective axial spring length of one pile'),
 'imposed_rotation_rad':('θ_imp','Imposed wall rotation from actions outside this calculation'),
 'pipe_inner_radius':('r_pi','Pipe inside radius using the effective wall'), 'pipe_area':('A_p','Effective pipe cross-section area'),
 'pipe_inertia':('I_p','Effective pipe moment of inertia'), 'pile_axial_stiffness':('k_v','Axial stiffness of one pile'),
 'pile_rotational_stiffness':('k_θ','Rotational stiffness of one pile head against the wall'),
 'group_centroid':('x̄','Pile-group centroid along the wall'), 'group_second_moment':('S_x','Sum of squared pile offsets from the group centroid'),
 'tolerance_rotation':('θ_Δ','Rigid-wall rotation with the pile group displaced by the tolerance'),
 'wall_rotation':('θ_w','Total wall rotation applied to every pile head'),
 'pile_head_moment':('M_p','Compatibility moment at one pile head'), 'ring_moment':('M','Moment assigned to each ring'),
 'kern_limit':('e_k','Equivalent eccentricity at which full annular contact is lost'),
 'row_share':('η','Row tributary fraction of the wall height'), 'tolerance_force':('ΔR','Axial redistribution assigned to one ring'),
 'design_force':('R_d','Design reaction on one ring'), 'equivalent_e':('e_eq','Equivalent eccentricity of the ring actions, M / R_d'),
 'superseded_moment':('M_s','Superseded tributary-eccentricity moment (D-070), comparison only'),
 'ring_count':('n_r','Number of ring rows'), 'ring_spacing_in':('s_r','Vertical ring pitch'),
 'ring_id_in':('D_i','Ring inside diameter'), 'ring_od_in':('D_o','Ring outside diameter'), 'ring_t_in':('t_p','Plate thickness'),
 'cover_in':('c','Provided concrete clear cover'), 'required_cover_in':('c_req','Required project cover'),
 'aggregate_in':('d_agg','Maximum aggregate size'), 'fc_ksi':('f′_c','Concrete compressive strength'),
 'fy_ksi':('f_y','Reinforcing steel yield strength'), 'density_kcf':('γ_c','Concrete unit weight in kip/ft³'),
 'gamma_dc':('γ_DC','Concrete self-weight load factor'), 'ring_fy_ksi':('F_y,p','Ring plate yield strength'),
 'ring_fu_ksi':('F_u,p','Ring plate tensile strength'), 'pile_fy_ksi':('F_y,pipe','Pipe yield strength'),
 'pile_fu_ksi':('F_u,pipe','Pipe tensile strength'), 'weld_fexx_ksi':('F_EXX','Weld electrode strength'),
 'weld_leg_in':('w','Provided fillet weld leg'), 'phi_concrete':('φ_b','Concrete bearing resistance factor'),
 'phi_plate':('φ_f','Plate flexure resistance factor'), 'phi_weld':('φ_w','Weld resistance factor'),
 'phi_shear_yield':('φ_vy','Shear-yielding resistance factor'), 'phi_shear_rupture':('φ_vu','Shear-rupture resistance factor'),
 'grid_bar':('N_bar','Selected bar number'), 'bar_diameter':('d_b','Selected bar diameter'), 'bar_area':('A_b','One bar area'),
 'selected_pitch':('s','Selected grid center spacing'), 'project_max_spacing_in':('s_project','Project maximum grid pitch'),
 'u_leg_in':('l_U','Provided straight U-bar lap leg'), 'vertical_lap_in':('l_v,prov','Provided vertical lap allowance'),
 'pi_value':('π','Circle constant'), 'steel_L':('A_s,L','Minimum per face using the thickness–length section'),
 'steel_H':('A_s,H','Minimum per face using the thickness–height section'),
 'steel_required':('A_s,req','Larger section minimum, adopted each way on each face'),
 'steel_provided':('A_s,prov','Grid steel area per foot, per direction and face'),
 'code_pitch':('s_code','Conservative wall/slab and thick-member spacing envelope'),
 'pitch_limit':('s_lim','Governing maximum grid pitch including the project cap'),
 'clear_required':('a_req','Required clear space for bars and aggregate'), 'clear_provided':('a','Space between adjacent bar surfaces'),
 'coating_factor':('ψ_e','Coating multiplier; unknown coating uses the epoxy value'),
 'ld_basic':('l_db','Basic normalweight tension development length, without confinement credit'),
 'ld_horizontal':('l_d,h','Horizontal development with conservative top-cast factor'),
 'ld_vertical':('l_d,v','Vertical development length'), 'lap_horizontal':('l_B,h','Required horizontal Class B lap'),
 'lap_vertical':('l_B,v','Required vertical Class B lap'), 'bend_envelope':('B_U','Outside envelope of the U bend'),
 'u_width':('B_avail','Thickness available inside concrete cover'), 'u_leg_available':('l_U,avail','Available length for a straight U-bar leg'),
 'vertical_available':('l_v,avail','Available height for a vertical lap'),
 'pipe_radius':('r_p','Pipe outside radius and cantilever root'), 'inner_radius':('r_i','Ring inside radius'),
 'outer_radius':('r_o','Ring outside radius'), 'root_gap':('g','Radial fit-up gap between plate and pipe'),
 'bearing_inner':('r_b','Start of horizontal concrete bearing, outside the upper weld'),
 'bearing_area':('A','Horizontal annular bearing area'), 'bearing_inertia':('I','Second moment of bearing area about a diameter'),
 'bearing_limit':('q_R','Factored concrete bearing resistance; no area enhancement'),
 'plate_capacity':('m_R','Elastic plate bending resistance per unit root circumference'),
 'plate_shear_capacity':('v_R','Plate shear-yield resistance per unit root circumference'),
 'weld_throat':('a_w','Effective fillet throat after the conservative gap allowance'),
 'weld_capacity':('F_R,w','Resistance per unit length of one continuous fillet'),
 'thicker_part':('t_max','Thicker joined part, controlling minimum weld size'),
 'minimum_thick_weld':('w_table,3','Upper thickness branches of the minimum weld table'),
 'minimum_mid_weld':('w_table,2','Middle thickness branches of the minimum weld table'),
 'minimum_table_weld':('w_table','Minimum weld leg from the thicker-part table'),
 'weld_minimum':('w_min','Table minimum capped at the thinner joined part'),
 'weld_min_gap':('w_min,g','Minimum provided leg including fit-up allowance'),
 'weld_maximum':('w_max','Maximum fillet at the ring free edge'),
 'weld_length':('l_w','Length of each continuous circumferential weld'),
 'weld_length_min':('l_w,min','Minimum effective weld length'),
 'ring_base_capacity':('F_R,ring','Ring base-metal shear-rupture resistance per unit weld length'),
 'pipe_base_capacity':('F_R,pipe','Pipe base-metal shear-rupture resistance per unit weld length'),
 'pipe_yield_capacity':('F_Y,pipe','Pipe base-metal shear-yield resistance per unit weld length'),
 'end_offset':('x_end','Nominal distance from wall end to outer pile center'),
 'end_clear':('c_end','Ring-to-end clearance after radial placement tolerance'),
 'face_clear':('c_face','Ring-to-broad-face clearance after radial placement tolerance'),
 'grid_gap':('a_grid','Clearance from ring edge to inner face-grid layer at tolerance'),
 'ring_grid_required':('a_ring,req','Required ring/grid or adjacent-ring construction clearance'),
 'bottom_ring_cover':('c_bottom','Cover below the lowest plate and bottom weld'),
 'top_ring_cover':('c_top','Cover above the highest plate and top weld'),
 'between_rings':('a_rings','Minimum gap between adjacent-pile rings at opposing tolerances'),
 'weight_density':('ω','Service wall weight per square inch of elevation'),
 'factored_density':('ω_u','Factored wall weight per square inch of elevation'),
 'total_service':('W_total','Gross service concrete weight'), 'total_factored':('R_total','Factored concrete weight'),
 'row_lo':('z_−','Lower clipped tributary boundary'), 'row_hi':('z_+','Upper clipped tributary boundary'),
 'row_height':('h','Vertical tributary band height'), 'x':('x_p','Nominal pile center'),
 'lo':('x_−','Left clipped tributary boundary'), 'hi':('x_+','Right clipped tributary boundary'),
 'width':('b','Horizontal tributary width'), 'volume':('V','Gross concrete volume assigned to one ring'),
 'service':('W','Service self-weight assigned to one ring'), 'force':('R','Factored reaction assigned to one ring'),
 'eccentricity':('e_n','Signed offset of tributary centroid from nominal pile center; carried by the wall'),
 'qavg':('q_0','Uniform pressure component from the design reaction'),
 'qmoment':('q_M','Extreme pressure component from the ring moment'),
 'qmax':('q_max','Maximum elastic annular pressure'), 'qmin':('q_min','Minimum elastic annular pressure; negative means contact is lost'),
 'root_moment':('m','Radial plate bending demand per unit root circumference'),
 'root_shear':('v','Vertical plate shear demand per unit root circumference'),
 'thickness_bending':('t_b','Plate thickness required by elastic bending'),
 'thickness_shear':('t_v','Plate thickness required by shear yielding'),
 'thickness_required':('t_req','Trial thickness including bending, shear and weld-edge allowance'),
 'weld_radial':('H_w','Radial force in each fillet forming the plate-moment couple'),
 'weld_resultant':('F_w','Resultant force per unit length of each top/bottom fillet'),
 'weld_strength_leg':('w_strength','Fillet leg required by strength including the gap'),
 'weld_required':('w_req','Trial weld leg including strength and minimum detailing'),
}


def stem(name):
    return re.sub(r'^row_\d+_', 'row_', re.sub(r'^ring_\d+_\d+_', '', name))


def term(name):
    return TERMS.get(stem(name), (name, name.replace('_', ' ')))


def symbol(name):
    label = term(name)[0]
    base, sep, sub = label.partition('_')
    attr = ' data-var="'+escape(name)+'"'  # report_cards hooks
    if sep:
        return '<msub'+attr+'><mi>'+escape(base)+'</mi><mtext>'+escape(sub)+'</mtext></msub>'
    return '<mi'+attr+'>'+escape(base)+'</mi>'


def number(value):
    text = format(value, '.6g')
    if 'e' in text:
        base, exponent = text.split('e')
        return '<mrow><mn>'+base+'</mn><mo>×</mo><msup><mn>10</mn><mn>'+str(int(exponent))+'</mn></msup></mrow>'
    return '<mn>'+text+'</mn>'


def fence(body):
    return '<mrow><mo>(</mo>'+body+'<mo>)</mo></mrow>'


def expression(source, values=None):
    """Render the actual AST with grouping preserved; numeric view keeps both IF branches."""
    def draw(node):
        if isinstance(node, ast.Constant): return number(node.value)
        if isinstance(node, ast.Name):
            return number(values[node.id]) if values is not None else symbol(node.id)
        if isinstance(node, ast.UnaryOp): return '<mrow><mo>−</mo>'+fence(draw(node.operand))+'</mrow>'
        if isinstance(node, ast.BinOp):
            a, b = draw(node.left), draw(node.right)
            if isinstance(node.op, ast.Div): return '<mfrac>'+a+b+'</mfrac>'
            if isinstance(node.op, ast.Pow):
                base=fence(a) if isinstance(node.left,(ast.BinOp,ast.UnaryOp)) else a
                return '<msup>'+base+b+'</msup>'
            op = {ast.Add:'+',ast.Sub:'−',ast.Mult:'·'}[type(node.op)]
            additive=lambda n:isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub))
            if isinstance(node.op,ast.Mult) and additive(node.left):a=fence(a)
            if isinstance(node.op,(ast.Mult,ast.Sub)) and additive(node.right):b=fence(b)
            return '<mrow>'+a+'<mo>'+op+'</mo>'+b+'</mrow>'
        if isinstance(node, ast.Compare):
            ops={ast.Gt:'>',ast.GtE:'≥',ast.Lt:'<',ast.LtE:'≤',ast.Eq:'='}
            return '<mrow>'+draw(node.left)+''.join('<mo>'+escape(ops[type(op)])+'</mo>'+draw(right) for op,right in zip(node.ops,node.comparators))+'</mrow>'
        if isinstance(node, ast.Call):
            args=[draw(a) for a in node.args];name=node.func.id
            if name=='sqrt':return '<msqrt>'+args[0]+'</msqrt>'
            if name=='abs':return '<mrow><mo>|</mo>'+args[0]+'<mo>|</mo></mrow>'
            if name=='IF':
                return '<mrow><mo>{</mo><mtable><mtr><mtd>'+args[1]+'</mtd><mtd><mtext>if </mtext>'+args[0]+'</mtd></mtr><mtr><mtd>'+args[2]+'</mtd><mtd><mtext>otherwise</mtext></mtd></mtr></mtable></mrow>'
            return '<mrow><mi mathvariant="normal">'+escape(name)+'</mi>'+fence('<mo>,</mo>'.join(args))+'</mrow>'
        raise ValueError('Unsupported report expression: '+ast.dump(node))
    return draw(ast.parse(source, mode='eval').body)


def math(body, block=False):
    return '<math xmlns="http://www.w3.org/1998/Math/MathML"'+(' display="block"' if block else '')+'>'+body+'</math>'


def dependencies(source):
    functions={'min','max','IF','abs','sqrt'}
    return list(dict.fromkeys(n.id for n in ast.walk(ast.parse(source, mode='eval')) if isinstance(n,ast.Name) and n.id not in functions))
