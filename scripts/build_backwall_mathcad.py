"""Build End_Bent_Backwall_Design.xmcd, a Mathcad 15 edition of the backwall notebook.

The worksheet is written from the compact equation list in SHEET below. Each
expression is parsed once and used two ways: emitted as Mathcad worksheet XML,
and evaluated here with unit checking so every result can be compared with the
notebook model before the file is written (`verify`).

    python scripts/build_backwall_mathcad.py                 # write the .xmcd
    python scripts/build_backwall_mathcad.py --render-figures # redraw the PNGs (needs Edge)
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from end_bent_walls.model import evaluate, COMBINATIONS, INPUTS as INPUT_SPEC  # noqa: E402
from scripts import mathcad_sheet  # noqa: E402
from scripts.mathcad_sheet import (  # noqa: E402,F401
    LEFT, BUL, D, E, EQ, F, FIG, H1, H2, INPUTS, N, P, R, ROW, S, V, Block, Item, U, UnitError,
    _to, check_names, check_order, document, ev, mc_name, parse, run)

OUTPUT = 'End_Bent_Backwall_Design.xmcd'
FIGURES = ROOT / 'end_bent_walls' / 'mathcad'
KEYS = [c['key'] for c in COMBINATIONS]
MEMBERS = ['FF', 'SF', 'CK']


def layout(blocks):
    """The shared layout with this worksheet's figure folder."""
    return mathcad_sheet.layout(blocks, FIGURES)


# ----------------------------------------------------------------------------- the worksheet
def I(name, expr, caption):                      # input (highlighted); value, unit and caption come from the notebook
    spec = INPUT_SPEC[name]
    unit = spec['unit']
    expr = repr(spec['value']) + (('*(' + unit.replace('^', '**') + ')') if unit not in (None, 'bar') else '')
    return Item('input', name, expr, caption=spec['caption'])


def sheet(rev):
    v_strength = ', '.join(f'{{x}}[{i}]' for i in range(1, 5))
    s4 = lambda x: v_strength.format(x=x)
    return [
        Block('title', 'End Bent 1 — Backwall, Cheek Walls and Tie-Back Straps'),
        P('Project: D2 I-95 Pedestrian Bridge · common end-bent design (D-004).'),
        P(f'Mathcad edition of End_Bent_Backwall_Design.ipynb (calculation package {rev}). Same inputs, equations and '
          'load combinations as the notebook; results should match its exported report (Section 12 lists the notebook values).'),
        P('Codes: AASHTO LRFD Bridge Design Specifications, 10th edition (2024); FDOT Structures Design Guidelines (SDG) and '
          'Structures Detailing Manual (SDM), January 2026.'),
        P('Status: adopted CAD geometry reconciled 16 October; single centered #4 cheek mat at 10 in each way. Prerequisites remain pending (Section 12). Inputs are '
          'highlighted yellow; values for the plans are boxed.'),

        H1('1. Design basis'),
        BUL(['Tie-back straps in the backwall extend into the MSE fill and resist the end-bent horizontal load and overturning '
             '(D-014). Attachment requires total settlement of the soil above the cap bottom of 2 in or less (SDG 3.13.2.N.3).',
             'The single pile row is effectively pinned (FBMP fixity 0.10), so moments are taken about the pile top O. The strap '
             'force is F = max(H, M / y_strap); the piles supply M / y_strap − H at O.',
             'Vertical-load arms are measured from the pile line shifted 3 in toward the fill (placement tolerance, SDG 3.13.2.N.3). '
             'Permanent loads take the maximum factor on an overturning arm and the minimum on a stabilizing arm; live load and '
             'wind uplift take no stabilizing credit.',
             'Pedestrian load only (D-015): 90 psf live-load surcharge. Backfill φ = 30°, δ = 0, γ = 115 pcf, active Coulomb pressure (D-016).',
             'The landing slab bears on the backwall (D-017): 50 % of its load goes to gravity design with no stabilizing credit; '
             'its weight on the fill acts as an earth surcharge ES.',
             'The cheek walls retain no fill: wind only (D-018). The backwall is designed at the crown height with the strap '
             '1.5 ft above the cap top (D-019).',
             'Backwall states: strap slack, soil causes fill-face tension; strap engaged, the strap pull causes span-face tension. Both are designed.']),

        H1('2. Inputs'),
        INPUTS('Adopted CAD geometry and centered cheek mat', [
            *[I(n, '', '') for n in ('single_ck', 'L_load', 'V_cap', 'V_bw', 'V_ck', 'dx_ck')]]),
        INPUTS('Geometry (D-026/D-033 native CAD snapshot)', [
            I('b_cap', '42*in', 'cap width, along the bridge'), I('h_cap', '36*in', 'cap depth'),
            I('L_cap', '212*in', 'cap length'), I('embed_pile', '12*in', 'pile embedment (pile top above soffit)'),
            I('tol_pile', '3*in', 'pile placement tolerance, toward fill'), I('t_bw', '12*in', 'backwall thickness'),
            I('L_bw', '196*in', 'backwall length between cheek walls'), I('H_bw', '4.083*ft', 'backwall height at the crown'),
            I('H_bw_edge', '3.9196*ft', 'backwall height at the cheek walls'), I('e_brg', '3*in', 'bearing offset from pile line'),
            I('s_brg', '102.99*in', 'bearing spacing along the cap'), I('h_ped', '6*in', 'pedestal height'),
            I('L_ped', '30*in', 'pedestal length along the beam'), I('B_ped', '42*in', 'pedestal width'),
            I('t_pad', '2.5625*in', 'bearing pad thickness'), I('t_ck', '8*in', 'cheek wall thickness'),
            I('w_ck', '42*in', 'cheek wall length'), I('H_ck', '5.4097*ft', 'cheek wall height above cap')]),
        INPUTS('Soil and surcharge (D-015, D-016, D-017)', [
            I('phi_soil', '30*deg', 'backfill friction angle'), I('delta_w', '0*deg', 'wall friction (neglected)'),
            I('theta_w', '90*deg', 'back face angle'), I('beta_f', '0*deg', 'backfill slope'),
            I('gamma_s', '0.115*kip/ft**3', 'backfill unit weight'), I('q_PL', '0.090*ksf', 'pedestrian live load'),
            I('t_slab', '4*in', 'landing slab thickness'), I('L_slab', '17.33*ft', 'landing slab length'),
            I('share_slab', '0.5', 'slab share on the backwall')]),
        INPUTS('Bearings and superstructure (EB-XML End Bent 1_Fixed; journal pad data)', [
            I('N_brg', '2', 'bearings'), I('P_DC', '92.07*kip', 'DC reaction per bearing'),
            I('P_PL', '28.98*kip', 'pedestrian reaction per bearing'), I('FY_WS1', '3.29*kip', 'long. wind per bearing, WS1'),
            I('FZ_WS1', '-36.98*kip', 'vertical wind, both bearings, WS1'), I('FY_WS2', '0*kip', 'long. wind per bearing, WS2'),
            I('FZ_WS2', '-14.58*kip', 'vertical wind, both bearings, WS2'), I('FY_WS3', '1.63*kip', 'long. wind per bearing, Service'),
            I('FZ_WS3', '0*kip', 'vertical wind, both bearings, Service'), I('G_pad', '0.110*ksi', 'elastomer shear modulus'),
            I('G_fac', '1.15', 'upper-bound G factor'), I('L_pad', '10*in', 'pad length'), I('W_pad', '32*in', 'pad width'),
            I('n_int', '3', 'internal layers'), I('t_int', '0.5*in', 'internal layer thickness'),
            I('t_cov', '0.25*in', 'cover layer thickness'), I('alpha_t', '6.0*10**-6', 'thermal coefficient, per °F'),
            I('dT', '35', 'temperature fall, °F'), I('L_exp', '107.35*ft', 'expansion length'),
            I('eps_sh', '7.3*10**-5', 'beam shrinkage strain (pending)')]),
        INPUTS('Tie-back strap and cheek-wall wind', [
            I('z_strap', '1.5*ft', 'strap above the cap top (D-019)'), I('V_III', '130', 'Strength III wind speed, mph'),
            I('V_SER', '70', 'Service I wind speed, mph'), I('K_Z_III', '1.0', 'Strength III Kz (pending)'),
            I('K_Z_SER', '1.0', 'Service I Kz'), I('G_w', '0.85', 'gust factor'), I('C_D', '1.6', 'drag coefficient')]),
        INPUTS('Reinforcement (trial) and cover (SDG Table 1.4.2-1)', [
            I('cv_bw', '3*in', 'backwall cover'), I('cv_ck', '2*in', 'cheek wall cover'),
            I('bar_FF', '5', 'backwall vertical bar, fill face'), I('s_FF', '12*in', 'spacing, fill face'),
            I('bar_SF', '5', 'backwall vertical bar, span face'), I('s_SF', '12*in', 'spacing, span face'),
            I('bar_HZ', '4', 'backwall horizontal bar'), I('s_HZ', '12*in', 'horizontal spacing'),
            I('bar_CK', '5', 'cheek wall vertical bar'), I('s_CK', '12*in', 'cheek vertical spacing'),
            I('bar_CKH', '4', 'cheek wall horizontal bar'), I('s_CKH', '12*in', 'cheek horizontal spacing')]),
        INPUTS('Materials and resistance factors', [
            I('fc', '5.5*ksi', 'concrete strength'), I('fy', '60*ksi', 'steel yield strength'),
            I('Es', '29000*ksi', 'steel modulus'), I('w_c', '0.150*kip/ft**3', 'reinforced concrete weight'),
            I('w_cE', '0.1455*kip/ft**3', 'concrete weight for Ec'), I('K_1', '1.0', 'aggregate factor'),
            I('lambda_c', '1.0', 'density factor'), I('phi_f', '0.9', 'flexure φ'), I('phi_v', '0.9', 'shear φ'),
            I('gamma_e', '1.0', 'crack-control exposure (Class 1)'), I('fss_ratio', '0.8', 'service stress limit / fy'),
            I('gamma_1', '1.6', 'cracking variability'), I('gamma_3', '0.67', 'yield / ultimate ratio'),
            I('beta_v', '2.0', 'simplified shear β'), I('c_if', '0.075*ksi', 'interface cohesion'),
            I('mu_if', '0.6', 'interface friction'), I('K1_if', '0.2', 'interface K1'), I('K2_if', '0.8*ksi', 'interface K2')]),
        EQ(D('A_bar', 'tr(row(0, 0, 0, 0.11, 0.20, 0.31, 0.44, 0.60, 0.79, 1.00, 1.27, 1.56))*in**2', 'bar area; index = bar number'),
           D('d_bar', 'tr(row(0, 0, 0, 0.375, 0.500, 0.625, 0.750, 0.875, 1.000, 1.128, 1.270, 1.410))*in', 'bar diameter; index = bar number')),

        H1('3. Geometry and overturning arms'),
        FIG('section', 'Figure 1. End-bent section. Arms are measured from O, the pile top on the pile line shifted 3 in toward '
                       'the fill; x is positive toward the span and y is the height above O.'),
        EQ(E('b_s', '12*in', 'in', 'design strip width'),
           E('y_top', 'h_cap - embed_pile', 'ft', 'cap top above O'),
           E('H_ret', 'H_bw + h_cap', 'ft', 'retained height, soffit to crown'),
           E('H_bw_avg', 'IF(V_bw > 0*ft**3, V_bw/(t_bw*L_bw), (H_bw + H_bw_edge)/2)', 'ft', 'average backwall height'),
           E('y_brg', 'y_top + h_ped + t_pad', 'ft', 'top of pad above O'),
           E('y_strap', 'y_top + z_strap', 'ft', 'strap above O'),
           E('x_brg', 'e_brg + tol_pile', 'in', 'bearing arm'),
           E('x_cap', 'tol_pile', 'in', 'cap arm (cap centered on nominal pile)'),
           E('x_ped', 't_bw + L_ped/2 - b_cap/2 + tol_pile', 'in', 'pedestal arm'),
           E('x_ck', 'dx_ck + tol_pile', 'in', 'cheek wall arm'),
           E('x_bw', 't_bw/2 - b_cap/2 + tol_pile', 'in', 'backwall arm (negative = stabilizing)')),

        H1('4. Loads'),
        H2('4.1 Earth pressure and surcharges (LRFD 3.11.5.3 Coulomb; 3.11.6.1 uniform surcharge)'),
        EQ(E('Gamma_c', '(1 + sqrt(sin(phi_soil + delta_w)*sin(phi_soil - beta_f)/(sin(theta_w - delta_w)*sin(theta_w + beta_f))))**2', None, 'Coulomb Γ'),
           E('k_a', 'sin(theta_w + phi_soil)**2/(Gamma_c*sin(theta_w)**2*sin(theta_w - delta_w))', None, 'active pressure coefficient'),
           E('p_EH', 'k_a*gamma_s*H_ret', 'psf', 'EH pressure at the cap soffit'),
           E('F_EH', '0.5*k_a*gamma_s*H_ret**2*L_load', 'kip', 'EH resultant'),
           E('y_EH', 'H_ret/3 - embed_pile', 'ft', 'EH height above O'),
           E('p_LS', 'k_a*q_PL', 'psf', 'pedestrian surcharge pressure'),
           E('F_LS', 'p_LS*H_ret*L_load', 'kip', 'LS resultant'),
           E('y_LS', 'H_ret/2 - embed_pile', 'ft', 'LS height above O'),
           E('q_ES', 't_slab*w_c', 'psf', 'landing slab weight on the fill'),
           E('p_ES', 'k_a*q_ES', 'psf', 'slab surcharge pressure'),
           E('F_ES', 'p_ES*H_ret*L_load', 'kip', 'ES resultant'),
           E('y_ES', 'H_ret/2 - embed_pile', 'ft', 'ES height above O')),
        H2('4.2 Bearing and superstructure actions (FBMP reactions; LRFD 14.6.3.1 pad shear with upper-bound G)'),
        EQ(E('A_pad', 'L_pad*W_pad', 'in**2', 'pad plan area'),
           E('h_rt', 'n_int*t_int + 2*t_cov', 'in', 'elastomer thickness'),
           E('K_pad', 'G_fac*G_pad*A_pad/h_rt', 'kip/in', 'pad shear stiffness'),
           E('Delta_TU', 'alpha_t*dT*L_exp', 'in', 'temperature fall shortening'),
           E('F_TU', 'N_brg*K_pad*Delta_TU', 'kip', 'pad shear, toward the span'),
           E('Delta_SH', 'eps_sh*L_exp', 'in', 'shrinkage shortening'),
           E('F_SH', 'N_brg*K_pad*Delta_SH', 'kip', 'pad shear, toward the span'),
           E('W_DCb', 'N_brg*P_DC', 'kip', 'superstructure DC'),
           E('W_PLb', 'N_brg*P_PL', 'kip', 'pedestrian load'),
           E('H_WS1', 'N_brg*FY_WS1', 'kip', 'longitudinal wind, Strength III dir. 1'),
           E('H_WS2', 'N_brg*FY_WS2', 'kip', 'longitudinal wind, Strength III dir. 2'),
           E('H_WS3', 'N_brg*FY_WS3', 'kip', 'longitudinal wind, Service I')),
        H2('4.3 Dead loads'),
        EQ(E('W_cap', 'IF(V_cap > 0*ft**3, V_cap, b_cap*h_cap*L_cap)*w_c', 'kip', 'cap'),
           E('W_ped', 'N_brg*L_ped*B_ped*h_ped*w_c', 'kip', 'pedestals'),
           E('W_bw', 't_bw*H_bw_avg*L_bw*w_c', 'kip', 'backwall'),
           E('W_ck', 'IF(V_ck > 0*ft**3, V_ck, 2*t_ck*w_ck*H_ck)*w_c', 'kip', 'cheek walls, both'),
           E('w_sl_DC', 'share_slab*L_slab*t_slab*w_c', 'klf', 'slab DC on the backwall (gravity only)'),
           E('w_sl_PL', 'share_slab*L_slab*q_PL', 'klf', 'slab PL on the backwall (gravity only)')),

        H1('5. Overturning about the pile top and tie-back force'),
        P('Vectors hold the five combinations in this order: Service I, Strength I, Strength III wind 1, Strength III wind 2, '
          'Strength IV (LRFD Tables 3.4.1-1 and 3.4.1-2). TU and SH share one factor. Wind takes γWS = 1.0 where it applies; '
          'vertical wind counts only when it increases overturning.'),
        ROW(R('i', 0, 4)),
        EQ(D('Combo', 'tr(row("Service I", "Strength I", "Strength III-1", "Strength III-2", "Strength IV"))')),
        ROW(D('gamma_EH', 'tr(row(1.0, 1.5, 1.5, 1.5, 1.5))'), D('gamma_ES', 'tr(row(1.0, 1.5, 1.5, 1.5, 1.5))')),
        ROW(D('gamma_LS', 'tr(row(1.0, 1.75, 0, 0, 0))'), D('gamma_TU', 'tr(row(1.0, 0.5, 0.5, 0.5, 0.5))')),
        ROW(D('gamma_DCmax', 'tr(row(1.0, 1.25, 1.25, 1.25, 1.5))'), D('gamma_DCmin', 'tr(row(1.0, 0.9, 0.9, 0.9, 0.9))')),
        ROW(D('gamma_PL', 'tr(row(1.0, 1.75, 0, 0, 0))')),
        EQ(D('H_W', 'tr(row(H_WS3, 0*kip, H_WS1, H_WS2, 0*kip))', 'longitudinal wind in each combination'),
           D('FZ_W', 'tr(row(FZ_WS3, 0*kip, FZ_WS1, FZ_WS2, 0*kip))', 'vertical wind in each combination (+ down)')),
        N('Factor on each vertical load, chosen by the sign of its arm:'),
        ROW(D('gamma_brg', 'IF(x_brg > 0*in, gamma_DCmax, gamma_DCmin)'), D('gamma_cap', 'IF(x_cap > 0*in, gamma_DCmax, gamma_DCmin)')),
        ROW(D('gamma_ped', 'IF(x_ped > 0*in, gamma_DCmax, gamma_DCmin)'), D('gamma_ck', 'IF(x_ck > 0*in, gamma_DCmax, gamma_DCmin)')),
        ROW(D('gamma_bw', 'IF(x_bw > 0*in, gamma_DCmax, gamma_DCmin)'), D('gamma_PLb', 'IF(x_brg > 0*in, gamma_PL, 0*gamma_PL)')),
        EQ(V('M_WV', 'i', 'IF(FZ_W[i]*x_brg > 0*kip*in, FZ_W[i]*x_brg, 0*kip*in)', 'kip*ft', 'vertical wind, overturning only'),
           S('tr(Combo)'),
           D('H_T', 'gamma_EH*F_EH + gamma_ES*F_ES + gamma_LS*F_LS + gamma_TU*(F_TU + F_SH) + H_W'), S('tr(H_T)', 'kip', 'horizontal force toward the span'),
           D('M_H', 'gamma_EH*F_EH*y_EH + gamma_ES*F_ES*y_ES + gamma_LS*F_LS*y_LS + (gamma_TU*(F_TU + F_SH) + H_W)*y_brg'),
           S('tr(M_H)', 'kip*ft', 'moment of the horizontal loads about O'),
           D('M_Vb', 'gamma_brg*W_DCb*x_brg + gamma_PLb*W_PLb*x_brg + gamma_ped*W_ped*x_ped'),
           S('tr(M_Vb)', 'kip*ft', 'superstructure and pedestals'),
           D('M_Vs', 'gamma_cap*W_cap*x_cap + gamma_ck*W_ck*x_ck + gamma_bw*W_bw*x_bw'),
           S('tr(M_Vs)', 'kip*ft', 'cap, cheek walls and backwall'),
           D('M_OT', 'M_H + M_Vb + M_Vs + M_WV'), S('tr(M_OT)', 'kip*ft', 'overturning moment about O'),
           V('e_res', 'i', 'M_OT[i]/H_T[i]', 'ft', 'resultant height above O'),
           D('F_eq', 'M_OT/y_strap'), S('tr(F_eq)', 'kip', 'strap force for moment equilibrium'),
           V('F_str', 'i', 'max(H_T[i], F_eq[i])', 'kip', 'design strap force'),
           D('f_str', 'F_str/L_bw'), S('tr(f_str)', 'klf', 'strap load per foot of backwall'),
           D('V_pile', 'F_eq - H_T'), S('tr(V_pile)', 'kip', 'pile-head force at O (+ toward span)'),
           E('f_str_u', f'max({s4("f_str")})', 'klf', 'factored strap load for the plans', key=True),
           E('f_str_s', 'f_str[0]', 'klf', 'service strap load for the plans', key=True),
           E('F_str_u', 'f_str_u*L_bw', 'kip', 'factored, whole backwall'),
           E('F_str_s', 'f_str_s*L_bw', 'kip', 'service, whole backwall')),

        H1('6. Backwall demands per 1-ft strip'),
        FIG('strip', 'Figure 2. Backwall strip above the construction joint. Strap slack: the soil bends the wall toward the span '
                     '(fill-face tension). Strap engaged: the strap pull exceeds the soil moment (span-face tension).'),
        EQ(E('V_EH_bw', '0.5*k_a*gamma_s*H_bw**2*b_s', 'kip', 'earth pressure on the strip'),
           E('M_EH_bw', 'V_EH_bw*H_bw/3', 'kip*ft', 'EH moment at the joint'),
           E('V_LS_bw', 'p_LS*H_bw*b_s', 'kip', 'pedestrian surcharge'),
           E('M_LS_bw', 'V_LS_bw*H_bw/2', 'kip*ft', 'LS moment at the joint'),
           E('V_ES_bw', 'p_ES*H_bw*b_s', 'kip', 'slab surcharge'),
           E('M_ES_bw', 'V_ES_bw*H_bw/2', 'kip*ft', 'ES moment at the joint'),
           D('M_sl', 'gamma_EH*M_EH_bw + gamma_ES*M_ES_bw + gamma_LS*M_LS_bw'), S('tr(M_sl)', 'kip*ft', 'strap slack: moment, fill-face tension'),
           D('V_sl', 'gamma_EH*V_EH_bw + gamma_ES*V_ES_bw + gamma_LS*V_LS_bw'), S('tr(V_sl)', 'kip', 'strap slack: joint shear'),
           D('M_en', 'f_str*b_s*z_strap - M_sl'), S('tr(M_en)', 'kip*ft', 'strap engaged: moment, span-face tension'),
           D('V_en', 'f_str*b_s - V_sl'), S('tr(V_en)', 'kip', 'strap engaged: joint shear'),
           E('M_u_FF', f'max({s4("M_sl")})', 'kip*ft', 'factored moment, fill face'),
           E('M_s_FF', 'M_sl[0]', 'kip*ft', 'service moment, fill face'),
           E('M_u_SF', f'max({s4("M_en")}, 0*kip*ft)', 'kip*ft', 'factored moment, span face'),
           E('M_s_SF', 'max(M_en[0], 0*kip*ft)', 'kip*ft', 'service moment, span face'),
           E('V_u_bw', f'max({s4("V_sl")}, ' + ', '.join(f'abs(V_en[{i}])' for i in range(1, 5)) + ')', 'kip', 'factored joint shear, both states')),

        H1('7. Cheek walls: wind only (D-018; LRFD 3.8.1.2.1)'),
        EQ(E('P_Z_III', '2.56*10**-6*V_III**2*K_Z_III*G_w*C_D*ksf', 'psf', 'Strength III pressure'),
           E('P_Z_SER', '2.56*10**-6*V_SER**2*K_Z_SER*G_w*C_D*ksf', 'psf', 'Service I pressure'),
           E('V_u_CK', 'P_Z_III*H_ck*b_s', 'kip', 'factored base shear, 1-ft strip'),
           E('M_u_CK', 'P_Z_III*H_ck**2/2*b_s', 'kip*ft', 'factored base moment'),
           E('M_s_CK', 'P_Z_SER*H_ck**2/2*b_s', 'kip*ft', 'service base moment')),

        H1('8. Materials (LRFD 5.4.2, 5.6.2.2; SDG 3.10.F)'),
        EQ(E('beta_1', 'min(0.85, max(0.65, 0.85 - 0.05*(fc - 4*ksi)/ksi))', None, 'stress block factor'),
           E('E_c', '120000*K_1*(w_cE/(kip/ft**3))**2*(fc/ksi)**0.33*ksi', 'ksi', 'concrete modulus'),
           E('n_m', 'Es/E_c', None, 'modular ratio'),
           E('f_r', '0.24*lambda_c*sqrt(fc/ksi)*ksi', 'ksi', 'modulus of rupture'),
           E('f_ss_lim', 'fss_ratio*fy', 'ksi', 'service steel stress limit')),

        H1('9. Flexure, crack control and shear: 1-ft strips (LRFD 5.6, 5.7)'),
        P('Index j: 0 = backwall fill face (strap slack), 1 = backwall span face (strap engaged), 2 = cheek wall (either face).'),
        ROW(R('j', 0, 2), D('Member', 'tr(row("Backwall fill face", "Backwall span face", "Cheek wall"))')),
        ROW(D('h_w', 'tr(row(t_bw, t_bw, t_ck))'), D('c_v', 'tr(row(cv_bw, cv_bw, cv_ck))')),
        ROW(D('n_b', 'tr(row(bar_FF, bar_SF, bar_CK))'), D('s_w', 'tr(row(s_FF, s_SF, s_CK))')),
        ROW(D('M_u', 'tr(row(M_u_FF, M_u_SF, M_u_CK))'), D('M_s', 'tr(row(M_s_FF, M_s_SF, M_s_CK))')),
        EQ(V('A_b', 'j', 'A_bar[n_b[j]]', 'in**2', 'bar area'),
           V('d_b', 'j', 'd_bar[n_b[j]]', 'in', 'bar diameter'),
           V('d', 'j', 'IF(j == 2, IF(single_ck == 1, t_ck/2 - d_bar[bar_CKH]/2, h_w[j] - c_v[j] - d_b[j]/2), h_w[j] - c_v[j] - d_b[j]/2)', 'in', 'effective depth'),
           V('A_s', 'j', 'A_b[j]*b_s/s_w[j]', 'in**2', 'steel in the strip'),
           V('a', 'j', 'A_s[j]*fy/(0.85*fc*b_s)', 'in', 'stress block depth'),
           V('c', 'j', 'a[j]/beta_1', 'in', 'neutral axis depth'),
           V('eps_t', 'j', '0.003*(d[j] - c[j])/c[j]', None, 'net tensile strain'),
           V('phi', 'j', 'IF(eps_t[j] >= 0.005, phi_f, IF(eps_t[j] <= 0.002, 0.75, 0.75 + 0.15*(eps_t[j] - 0.002)/0.003))', None, 'flexure φ (LRFD 5.5.4.2)'),
           V('M_n', 'j', 'A_s[j]*fy*(d[j] - a[j]/2)', 'kip*ft', 'nominal moment'),
           V('M_r', 'j', 'phi[j]*M_n[j]', 'kip*ft', 'factored resistance'),
           V('A_req', 'j', '0.85*fc*b_s*d[j]/fy*(1 - sqrt(max(1 - 2*M_u[j]/(0.85*phi_f*fc*b_s*d[j]**2), 0)))', 'in**2', 'steel required for Mu'),
           V('S_c', 'j', 'b_s*h_w[j]**2/6', 'in**3', 'section modulus'),
           V('M_cr', 'j', 'gamma_3*gamma_1*f_r*S_c[j]', 'kip*ft', 'cracking moment (LRFD 5.6.3.3)'),
           V('M_min', 'j', 'min(M_cr[j], 1.33*M_u[j])', 'kip*ft', 'minimum flexural resistance'),
           V('rho', 'j', 'A_s[j]/(b_s*d[j])', None, 'reinforcement ratio'),
           V('k_cr', 'j', 'sqrt(2*rho[j]*n_m + (rho[j]*n_m)**2) - rho[j]*n_m', None, 'cracked neutral axis ratio'),
           V('j_cr', 'j', '1 - k_cr[j]/3', None, 'lever arm ratio'),
           V('f_ss', 'j', 'M_s[j]/(A_s[j]*j_cr[j]*d[j])', 'ksi', 'service steel stress'),
           V('d_c', 'j', 'h_w[j] - d[j]', 'in', 'cover to bar center'),
           V('beta_s', 'j', '1 + d_c[j]/(0.7*(h_w[j] - d_c[j]))', None, 'strain ratio'),
           V('s_cr', 'j', 'IF(f_ss[j] > 0*ksi, 700*gamma_e/(beta_s[j]*f_ss[j]/ksi)*in - 2*d_c[j], 99*in)', 'in', 'crack-control spacing (LRFD 5.6.7)'),
           V('d_v', 'j', 'max(d[j] - a[j]/2, 0.9*d[j], 0.72*h_w[j])', 'in', 'shear depth'),
           V('V_c', 'j', '0.0316*beta_v*lambda_c*sqrt(fc/ksi)*ksi*b_s*d_v[j]', 'kip', 'concrete shear'),
           V('V_n', 'j', 'min(V_c[j], 0.25*fc*b_s*d_v[j])', 'kip', 'nominal shear'),
           V('V_r', 'j', 'phi_v*V_n[j]', 'kip', 'factored shear resistance')),

        H1('10. Construction joints and distribution steel (LRFD 5.7.4, 5.10.3.2, 5.10.6; SDG 1.15)'),
        EQ(E('V_r_bw', 'min(V_r[0], V_r[1])', 'kip', 'backwall shear resistance'),
           E('A_cv_bw', 'min(d_v[0], d_v[1])*b_s', 'in**2', 'interface area, dv strip'),
           E('A_vf_bw', 'min(A_s[0], A_s[1])', 'in**2', 'steel across the joint, one face'),
           E('V_ni_bw', 'min(c_if*A_cv_bw + mu_if*A_vf_bw*fy, K1_if*fc*A_cv_bw, K2_if*A_cv_bw)', 'kip', 'nominal interface shear, Pc = 0'),
           E('V_ri_bw', 'phi_v*V_ni_bw', 'kip', 'factored interface shear'),
           E('A_vfmin_bw', '0.05*ksi*A_cv_bw/fy', 'in**2', 'minimum interface steel'),
           E('A_cv_ck', 'd_v[2]*b_s', 'in**2', 'cheek wall interface area'),
           E('V_ni_ck', 'min(c_if*A_cv_ck + mu_if*A_s[2]*fy, K1_if*fc*A_cv_ck, K2_if*A_cv_ck)', 'kip', 'cheek wall interface shear'),
           E('V_ri_ck', 'phi_v*V_ni_ck', 'kip', 'factored'),
           E('s_max_bw', 'min(1.5*t_bw, 18*in)', 'in', 'max primary spacing, backwall'),
           E('s_max_ck', 'min(1.5*t_ck, 18*in)', 'in', 'max primary spacing, cheek wall'),
           E('b_ts_bw', 'min(H_bw, L_bw)', 'in', 'least backwall width'),
           E('A_ts0_bw', '1.30*b_ts_bw*t_bw/(2*(b_ts_bw + t_bw)*fy)*ksi*in/ft', 'in**2/ft', 'LRFD 5.10.6-1 (b, h in in, fy in ksi)'),
           E('A_ts_bw', 'min(max(A_ts0_bw, 0.11*in**2/ft), 0.60*in**2/ft)', 'in**2/ft', 'S&T steel each backwall face, 0.11 to 0.60'),
           E('s_ts_bw', 'min(3*t_bw, 18*in)', 'in', 'max S&T spacing'),
           E('b_ts_ck', 'min(H_ck, w_ck)', 'in', 'least cheek wall width'),
           E('A_ts0_ck', '1.30*b_ts_ck*t_ck/(2*(b_ts_ck + t_ck)*fy)*ksi*in/ft', 'in**2/ft', 'LRFD 5.10.6-1'),
           E('A_ts_ck', 'IF(single_ck == 1, 2, 1)*min(max(A_ts0_ck, 0.11*in**2/ft), 0.60*in**2/ft)', 'in**2/ft', 'S&T steel, both face requirements combined for the single cheek mat'),
           E('s_ts_ck', 'min(3*t_ck, 18*in)', 'in', 'max S&T spacing'),
           E('A_pr_FF', 'A_b[0]/s_FF', 'in**2/ft', 'provided, fill face'),
           E('A_pr_SF', 'A_b[1]/s_SF', 'in**2/ft', 'provided, span face'),
           E('A_pr_HZ', 'A_bar[bar_HZ]/s_HZ', 'in**2/ft', 'provided, backwall horizontal'),
           E('A_pr_CK', 'A_b[2]/s_CK', 'in**2/ft', 'provided, cheek vertical'),
           E('A_pr_CKH', 'A_bar[bar_CKH]/s_CKH', 'in**2/ft', 'provided, cheek horizontal')),

        H1('11. Cap torsion screen (LRFD 5.7.2.1; not in the FBMP cap model)'),
        P('The strap restraint is spread along the backwall and balances the overturning moment, so the torque along the cap '
          'closes to zero at both ends. Uniform torques: soil and cap self-weight over the cap length, backwall and strap over '
          'the backwall length. Point torques: bearing-level loads at the two bearings, cheek walls at the cap ends.'),
        EQ(E('A_cp', 'b_cap*h_cap', 'in**2', 'cap gross area'),
           E('p_cp', '2*(b_cap + h_cap)', 'in', 'cap perimeter'),
           E('T_cr', '0.126*sqrt(fc/ksi)*ksi*A_cp**2/p_cp', 'kip*ft', 'cracking torque'),
           E('T_lim', '0.25*phi_v*T_cr', 'kip*ft', 'torsion may be neglected below this'),
           D('t_u', '(gamma_EH*F_EH*y_EH + gamma_ES*F_ES*y_ES + gamma_LS*F_LS*y_LS)/L_load', 'uniform torque, whole cap'),
           D('t_cap', 'gamma_cap*W_cap*x_cap/L_cap', 'uniform torque over the core cap only'),
           D('t_b', '(gamma_bw*W_bw*x_bw - M_OT)/L_bw', 'uniform torque over the backwall, with the strap'),
           D('P_b', '((gamma_TU*(F_TU + F_SH) + H_W)*y_brg + M_Vb + M_WV)/N_brg', 'torque at each bearing'),
           D('P_c', 'gamma_ck*W_ck*x_ck/2', 'torque at each cheek wall'),
           E('x_w0', '(L_load - L_bw)/2', 'in', 'backwall start'),
           E('x_b1', '(L_load - s_brg)/2', 'in', 'bearing 1'),
           E('x_b2', '(L_load + s_brg)/2', 'in', 'bearing 2'),
           F('L_core', ['x'], 'min(max(x - (L_load - L_cap)/2, 0*in), L_cap)', 'core cap length left of x'),
           F('L_w', ['x'], 'min(max(x - x_w0, 0*in), L_bw)', 'backwall length left of x'),
           F('N_b', ['x'], 'IF(x >= x_b1, 1, 0) + IF(x >= x_b2, 1, 0)', 'bearings at or left of x'),
           F('N_c', ['x'], 'IF(x >= t_ck/2, 1, 0) + IF(x >= L_load - t_ck/2, 1, 0)', 'cheek walls at or left of x'),
           F('T_c', ['x', 'r'], 't_u[r]*x + t_cap[r]*L_core(x) + t_b[r]*L_w(x) + P_b[r]*N_b(x) + P_c[r]*N_c(x)', 'torque at x, combination r'),
           D('X_T', 'tr(row(0*in, t_ck/2, x_w0, x_b1, x_b2, L_load - x_w0, L_load - t_ck/2, L_load))', 'stations where the torque changes slope or jumps'),
           ),
        ROW(R('k', 0, 7), R('r', 1, 4, 'strength combinations')),
        EQ(V('T_A', ('k', 'r'), 'abs(T_c(X_T[k], r))', None, 'torque at each station'),
           V('T_B', ('k', 'r'), 'abs(T_c(X_T[k] - 0.001*in, r))', None, 'torque just before each station'),
           E('T_u', 'max(T_A, T_B)', 'kip*ft', 'largest factored torque, strength combinations')),

        H1('12. Summary of checks'),
        P('Demand / capacity ratios; 1.0 or less passes. Rows j as in Section 9.'),
        EQ(D('s_max', 'tr(row(s_max_bw, s_max_bw, s_max_ck))', 'maximum spacing for each strip'),
           S('tr(Member)', None),
           V('DC_flex', 'j', 'M_u[j]/M_r[j]', None, 'flexure, Mu / φMn'),
           V('DC_min', 'j', 'M_min[j]/M_r[j]', None, 'minimum steel, min(Mcr, 1.33Mu) / φMn'),
           V('DC_eps', 'j', '0.005/eps_t[j]', None, 'tension-controlled, 0.005 / εt'),
           V('DC_crk', 'j', 'max(f_ss[j]/f_ss_lim, IF(f_ss[j] > 0*ksi, s_w[j]/s_cr[j], 0))', None, 'crack control, max(fss / 0.8fy, s / s_cr)'),
           V('DC_sp', 'j', 's_w[j]/s_max[j]', None, 'maximum bar spacing'),
           E('DC_V_bw', 'V_u_bw/V_r_bw', None, 'backwall shear'),
           E('DC_Vi_bw', 'V_u_bw/V_ri_bw', None, 'backwall interface shear (SDG 1.15)'),
           E('DC_Avf', 'A_vfmin_bw/A_vf_bw', None, 'minimum interface steel'),
           E('DC_ts_v', 'max(A_ts_bw/min(A_pr_FF, A_pr_SF), max(s_FF, s_SF)/s_ts_bw)', None, 'backwall S&T, vertical'),
           E('DC_ts_h', 'max(A_ts_bw/A_pr_HZ, s_HZ/s_ts_bw)', None, 'backwall S&T, horizontal'),
           E('DC_V_ck', 'V_u_CK/V_r[2]', None, 'cheek wall shear'),
           E('DC_Vi_ck', 'V_u_CK/V_ri_ck', None, 'cheek wall interface shear'),
           E('DC_ts_ck', 'max(A_ts_ck/min(A_pr_CK, A_pr_CKH), max(s_CK, s_CKH)/s_ts_ck)', None, 'cheek wall S&T'),
           E('DC_cov', 'max(3*in/cv_bw, IF(single_ck == 1, cv_ck, 2*in)/IF(single_ck == 1, (t_ck - d_bar[bar_CK] - d_bar[bar_CKH])/2, cv_ck))', None, 'cover, 3 in backwall and specified cheek requirement (legacy minimum 2 in)'),
           E('DC_thk', 'max(12*in/t_bw, 8*in/t_ck)', None, 'thickness, SDM 12.6.B'),
           E('DC_strap', 'z_strap/H_bw_edge', None, 'strap within the backwall height'),
           E('DC_T', 'T_u/T_lim', None, 'cap torsion screen'),
           E('DC_strips', 'max(DC_flex, DC_min, DC_eps, DC_crk, DC_sp)', None, 'largest strip ratio'),
           E('DC_joints', 'max(DC_V_bw, DC_Vi_bw, DC_Avf, DC_ts_v, DC_ts_h, DC_V_ck, DC_Vi_ck, DC_ts_ck)', None, 'largest joint and S&T ratio'),
           E('DC_max', 'max(DC_strips, DC_joints, DC_cov, DC_thk, DC_strap, DC_T)', None, 'largest ratio'),
           E('Status', 'IF(DC_max <= 1, "PASS", "FAIL")', None, 'all numerical checks', key=True)),
        H2('Tie-back loads for the plans (SDM 12.3.F)'),
        EQ(S('f_str_s', 'klf', 'service load per foot of backwall', key=True),
           S('f_str_u', 'klf', 'factored load per foot of backwall', key=True)),
        N('Plan note (SDM 12.3.F): "The soil reinforcement attached to the backwall shall be designed by a Specialty Engineer for '
          'the service and factored loads as shown using the design criteria for permanent MSE walls. Cost of furnishing and '
          'installing the soil reinforcement is considered incidental to the cost of the end bent." Also add the SDG 1.15 note '
          'requiring the construction joints to be intentionally roughened to a 1/4 in amplitude.'),
        N('Pending before final design: geotechnical confirmation of 2 in maximum settlement above the cap bottom (SDG 3.13.2.N.3); '
          'strap elevation at an MSE reinforcement level; beam shrinkage strain; environment for the covers; matching current '
          'bearing-load analyses; cheek mat development and cap/lug load path. Geometry, journal Kz and landing basis are reconciled. The pile-head force V_pile is not in the '
          'FBMP model; raise the strap toward e_res or confirm the piles carry it.'),
    ]


# ----------------------------------------------------------------------------- verification against the notebook
def comparisons(env, e):
    """(label, mathcad value, notebook value) for every quantity both calculations hold."""
    out = []
    nb_units = e.units
    for name in ('b_s', 'y_top', 'H_ret', 'H_bw_avg', 'y_brg', 'y_strap', 'x_brg', 'x_cap', 'x_ped', 'x_ck', 'x_bw',
                 'Gamma_c', 'k_a', 'p_EH', 'F_EH', 'y_EH', 'p_LS', 'F_LS', 'y_LS', 'q_ES', 'p_ES', 'F_ES', 'y_ES',
                 'A_pad', 'h_rt', 'K_pad', 'Delta_TU', 'F_TU', 'Delta_SH', 'F_SH', 'W_DCb', 'W_PLb', 'H_WS1', 'H_WS2', 'H_WS3',
                 'W_cap', 'W_ped', 'W_bw', 'W_ck', 'w_sl_DC', 'w_sl_PL', 'f_str_u', 'f_str_s', 'F_str_u', 'F_str_s',
                 'V_EH_bw', 'M_EH_bw', 'V_LS_bw', 'M_LS_bw', 'V_ES_bw', 'M_ES_bw', 'M_u_FF', 'M_s_FF', 'M_u_SF', 'M_s_SF', 'V_u_bw',
                 'P_Z_III', 'P_Z_SER', 'V_u_CK', 'M_u_CK', 'M_s_CK', 'beta_1', 'E_c', 'n_m', 'f_r', 'f_ss_lim',
                 'V_r_bw', 'A_cv_bw', 'A_vf_bw', 'V_ni_bw', 'V_ri_bw', 'A_vfmin_bw', 'A_cv_ck', 'V_ni_ck', 'V_ri_ck',
                 's_max_bw', 's_max_ck', 'b_ts_bw', 'A_ts_bw', 's_ts_bw', 'b_ts_ck', 'A_ts_ck', 's_ts_ck',
                 'A_pr_FF', 'A_pr_SF', 'A_pr_HZ', 'A_pr_CK', 'A_pr_CKH', 'A_cp', 'p_cp', 'T_cr', 'T_lim'):
        unit = nb_units.get(name)
        unit = None if unit is None else unit.replace('^', '**')
        out.append((name, _to(env[name], unit), e.value(name)))
    for i, key in enumerate(KEYS):
        for mc, nb in (('H_T', 'H'), ('M_OT', 'M'), ('e_res', 'e'), ('F_eq', 'F_eq'), ('F_str', 'F_str'),
                       ('f_str', 'f_str'), ('V_pile', 'V_pile'), ('M_sl', 'M_sl'), ('V_sl', 'V_sl'), ('M_en', 'M_en'), ('V_en', 'V_en')):
            unit = nb_units[f'{nb}_{key}'].replace('^', '**')
            out.append((f'{mc}[{i}] · {key}', _to(env[mc][i], unit), e.value(f'{nb}_{key}')))
    for j, member in enumerate(MEMBERS):
        for part in ('d', 'A_s', 'a', 'c', 'eps_t', 'phi', 'M_n', 'M_r', 'A_req', 'S_c', 'M_cr', 'M_min', 'rho',
                     'f_ss', 'd_c', 'beta_s', 's_cr', 'd_v', 'V_c', 'V_n', 'V_r'):
            nb = f'{part}_{member}'
            unit = nb_units[nb]
            unit = None if unit is None else unit.replace('^', '**')
            out.append((f'{part}[{j}] · {member}', _to(env[part][j], unit), e.value(nb)))
        out.append((f'k_cr[{j}]', env['k_cr'][j].v, e.value(f'k_{member}')))
        out.append((f'j_cr[{j}]', env['j_cr'][j].v, e.value(f'j_{member}')))
    out.append(('T_u', _to(env['T_u'], 'kip*ft'), e.cap['torsion_max']))
    ratio = {c.key: c.ratio for c in e.checks}
    for j, member in enumerate(MEMBERS):
        for mc, key in (('DC_flex', 'flex'), ('DC_min', 'min'), ('DC_eps', 'strain'), ('DC_crk', 'crack'), ('DC_sp', 'spacing')):
            out.append((f'{mc}[{j}]', env[mc][j].v, ratio[f'{key}_{member}']))
    for mc, key in (('DC_V_bw', 'shear_bw'), ('DC_Vi_bw', 'interface_bw'), ('DC_Avf', 'interface_min_bw'), ('DC_ts_v', 'ts_vert'),
                    ('DC_ts_h', 'ts_horiz'), ('DC_V_ck', 'shear_CK'), ('DC_Vi_ck', 'interface_CK'), ('DC_ts_ck', 'ts_CK'),
                    ('DC_strap', 'strap_height'), ('DC_T', 'cap_torsion')):
        out.append((mc, env[mc].v, ratio[key]))
    out.append(('DC_cov', env['DC_cov'].v, max(ratio['cover_bw'], ratio['cover_CK'])))
    out.append(('DC_thk', env['DC_thk'].v, max(ratio['thickness_bw'], ratio['thickness_CK'])))
    numeric = [r for r in ratio.values() if isinstance(r, (int, float))]
    out.append(('DC_max', env['DC_max'].v, max(numeric)))
    return out


def verify(blocks, e, tol=1e-9):
    env = run(blocks)
    bad = [(n, a, b) for n, a, b in comparisons(env, e) if abs(a - b) > tol * max(1.0, abs(b))]
    if bad:
        raise AssertionError('Mathcad equations differ from the notebook:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b in bad))
    return env


def check_inputs(blocks, e):
    """Every worksheet input equals the notebook input, converted to its unit."""
    env = {}
    for block in blocks:
        if block.kind == 'inputs':
            for item in block.payload:
                env[item.name] = ev(item.tree, env)
                spec = INPUT_SPEC[item.name]
                unit = None if spec['unit'] in (None, 'bar') else spec['unit'].replace('^', '**')
                mine = _to(env[item.name], unit) if unit else env[item.name].v
                assert abs(mine - e.case['inputs'][item.name]) < 1e-12, (item.name, mine, e.case['inputs'][item.name])
    missing = set(INPUT_SPEC) - set(env) - {'N_pile', 'S_pile', 'D_pile'}
    assert not missing, f'notebook inputs missing from the worksheet: {sorted(missing)}'


# ----------------------------------------------------------------------------- figures
def figures(e):
    """SVG markup for the two worksheet figures (symbols only, no numbers)."""
    from end_bent_walls.schematics import Svg, Frame, _geometry, sym, HL, BLUE, STRAP, GREY, FAINT, CONC, SOIL, SLAB, PAD, INK

    class Fig(Svg):
        def tag(self, x, y, markup, color=INK, anchor='middle'):
            self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="12.5" fill="{color}" text-anchor="{anchor}" font-weight="bold" '
                              f'font-family="Arial, sans-serif" stroke="#ffffff" stroke-width="3.5" paint-order="stroke">{markup}</text>')

    g = _geometry(e)
    rear, front, tol, b, h, tb, H = g['rear'], g['front'], g['tol'], g['b'], g['h'], g['tb'], g['H']
    top = h + max(H + g['ts'], g['Hck'])
    s1 = Fig('End-bent section with loads, arms and the shifted pile line.', 640, 600)
    f = Frame(rear - 4.1, front + 2.6, -2.1, top + 0.35, 8, 8, 624, 584)
    s1.rect(f.X(rear - 4.1), f.Y(h + H), f.L(4.1), f.L(h + H), fill=SOIL, stroke='none')
    s1.tag(f.X(rear - 1.3), f.Y(0.25), 'MSE fill', '#8a7340', 'middle')
    s1.rect(f.X(rear - 4.1), f.Y(h + H + g['ts']), f.L(4.1 + tb), f.L(g['ts']), fill=SLAB, stroke=GREY, sw=0.8)
    s1.tag(f.X(rear - 3.7), f.Y(h + H + g['ts']) - 5, 'landing slab', GREY, 'start')
    s1.rect(f.X(g['ebrg'] - 0.4), f.Y(top + 0.3), f.L(front + 2.6 - g['ebrg'] + 0.4), f.L(top + 0.3 - g['pad_top']), fill='#f7f9fb', stroke=FAINT)
    s1.tag(f.X(front + 1.6), f.Y(top - 0.4), 'beam', GREY)
    s1.rect(f.X(rear), f.Y(h + g['Hck']), f.L(g['wck']), f.L(g['Hck']), stroke=GREY, dash='4 3')
    s1.tag(f.X(rear) - 6, f.Y(h + g['Hck']) + 5, 'cheek wall (behind)', GREY, 'end')
    s1.rect(f.X(-g['dp'] / 2), f.Y(g['emb']), f.L(g['dp']), f.L(g['emb'] + 2.0), fill='#d3dbe2', stroke=GREY)
    s1.rect(f.X(rear), f.Y(h), f.L(b), f.L(h), fill=CONC, stroke=INK)
    s1.rect(f.X(rear), f.Y(h + H), f.L(tb), f.L(H), fill=CONC, stroke=INK)
    s1.rect(f.X(rear + tb), f.Y(h + g['hped']), f.L(b - tb), f.L(g['hped']), fill='#eef2f5', stroke=INK, sw=0.8)
    s1.rect(f.X(g['ebrg'] - g['lpad'] / 2), f.Y(g['pad_top']), f.L(g['lpad']), f.L(g['tpad']), fill=PAD, stroke=PAD)
    s1.tag(f.X(rear + 0.5), f.Y(h * 0.55), 'cap', GREY)
    s1.tag(f.X(rear + tb / 2), f.Y(h + H * 0.92), 'backwall', GREY)
    # pile lines and O
    s1.line(f.X(rear - 4.1), f.Y(g['emb']), f.X(front + 2.6), f.Y(g['emb']), GREY, 0.9, '2 3')
    s1.tag(f.X(front + 2.5), f.Y(g['emb']) - 5, 'pile top', GREY, 'end')
    s1.line(f.X(-tol), f.Y(-2.05), f.X(-tol), f.Y(h + 0.1), BLUE, 1.1, '6 3')
    s1.line(f.X(0), f.Y(-2.05), f.X(0), f.Y(-0.1), GREY, 0.8, '1 3')
    s1.circle(f.X(-tol), f.Y(g['emb']), 5, fill='#ffffff', stroke=BLUE, sw=2)
    s1.tag(f.X(-tol) - 9, f.Y(g['emb']) - 7, 'O', BLUE, 'end')
    s1.tag(f.X(-tol) - 6, f.Y(-1.95), 'shifted pile line', BLUE, 'end')
    s1.tag(f.X(0) + 5, f.Y(-1.95), 'pile', GREY, 'start')
    # horizontal loads on the retained face and at the pads
    for y, label in ((h + H) / 3, sym('F_EH')), ((h + H) / 2, sym('F_ES') + ', ' + sym('F_LS')):
        s1.arrow(f.X(rear - 1.35), f.Y(y), f.X(rear) - 1, f.Y(y), HL, 2.6)
        s1.tag(f.X(rear - 1.4), f.Y(y) - 7, label, HL, 'start')
    ys = h + g['zs']
    s1.arrow(f.X(rear), f.Y(ys), f.X(rear - 1.5), f.Y(ys), STRAP, 3.2)
    s1.tag(f.X(rear - 1.45), f.Y(ys) - 8, sym('F_str') + ' (strap)', STRAP, 'start')
    xr = f.X(g['ebrg'] + g['lpad'] / 2) + 2
    s1.arrow(xr, f.Y(g['pad_top']) - 3, xr + 58, f.Y(g['pad_top']) - 3, HL, 2.6)
    s1.tag(xr + 4, f.Y(g['pad_top']) - 14, sym('F_TU') + ', ' + sym('F_SH') + ', ' + sym('H_WS'), HL, 'start')
    # gravity loads
    s1.arrow(f.X(g['ebrg']), f.Y(top + 0.2), f.X(g['ebrg']), f.Y(g['pad_top']), HL, 2.6)
    s1.tag(f.X(g['ebrg']) + 6, f.Y(top + 0.05), sym('W_DCb') + ', ' + sym('W_PLb'), HL, 'start')
    for x, y, label, dx, dy, anchor in ((0.0, h / 2, 'W_cap', 6, -16, 'start'),
                                        (rear + tb + (b - tb) / 2, h + g['hped'] / 2, 'W_ped', 8, 16, 'start'),
                                        (rear + tb / 2, h + H / 2, 'W_bw', 6, -16, 'start'),
                                        (e.value('dx_ck', 'ft'), h + g['Hck'] * 0.62, 'W_ck', -6, -16, 'end')):
        s1.circle(f.X(x), f.Y(y), 2.6, fill=HL)
        s1.arrow(f.X(x), f.Y(y) - 30, f.X(x), f.Y(y), HL, 2.2)
        s1.tag(f.X(x) + dx, f.Y(y) + dy, sym(label), HL, anchor)
    # arms from the shifted pile line (labels to the right of each short dimension)
    for level, x, name, label in ((-0.4, rear + tb / 2, 'x_bw', sym('x_bw')),
                                  (-0.7, e.value('dx_ck', 'ft'), 'x_ck', sym('x_ck')), (-1.0, 0.0, 'x_cap', sym('x_cap')),
                                  (-1.3, g['ebrg'], 'x_brg', sym('x_brg')), (-1.6, rear + tb + (b - tb) / 2, 'x_ped', sym('x_ped'))):
        s1.line(f.X(x), f.Y(level - 0.12), f.X(x), f.Y(-0.02), BLUE, 0.7, '3 2')
        s1.dim(f.X(-tol), f.Y(level), f.X(x), f.Y(level), '', BLUE)
        if x < -tol:
            s1.tag((f.X(x) + f.X(-tol)) / 2, f.Y(level) - 7, label, BLUE)
        else:
            s1.tag(max(f.X(x), f.X(-tol)) + 7, f.Y(level) + 5, label, BLUE, 'start')
    # heights above O
    for x, y, name in ((rear - 1.85, (h + H) / 3, 'y_EH'), (rear - 2.4, (h + H) / 2, 'y_ES'), (rear - 2.95, ys, 'y_strap')):
        s1.line(f.X(x) - 6, f.Y(y), f.X(rear), f.Y(y), BLUE, 0.6, '3 2')
        s1.dim(f.X(x), f.Y(g['emb']), f.X(x), f.Y(y), sym(name), BLUE, side=-1)
    s1.dim(f.X(rear - 3.75), f.Y(0), f.X(rear - 3.75), f.Y(h + H), sym('H_ret'), BLUE, side=1)
    s1.line(f.X(rear - 3.9), f.Y(0), f.X(rear), f.Y(0), BLUE, 0.6, '3 2')
    s1.dim(f.X(front + 0.75), f.Y(g['emb']), f.X(front + 0.75), f.Y(g['pad_top']), sym('y_brg'), BLUE)
    s1.dim(f.X(front + 1.9), f.Y(h), f.X(front + 1.9), f.Y(h + H), sym('H_bw'), BLUE)
    s1.line(f.X(rear + tb), f.Y(h + H), f.X(front + 2.05), f.Y(h + H), BLUE, 0.6, '3 2')

    s2 = Fig('Backwall 1-ft strip in the strap-slack and strap-engaged states.', 640, 330)
    for panel, (x0, engaged) in enumerate(((0, False), (320, True))):
        f = Frame(-2.4, 2.3, -0.9, H + 0.75, x0 + 6, 28, 308, 296)
        s2.text(x0 + 160, 20, 'Strap engaged' if engaged else 'Strap slack', 13, INK, 'middle', 'bold')
        s2.rect(f.X(-0.6), f.Y(0), f.L(2.2), f.L(0.75), fill='#eef2f5', stroke=GREY)
        s2.tag(f.X(1.3), f.Y(-0.45), 'cap', GREY)
        s2.line(f.X(-0.6), f.Y(0), f.X(1.75), f.Y(0), GREY, 1, '4 2')
        s2.tag(f.X(1.8), f.Y(0) + 4, 'joint', GREY, 'start')
        s2.rect(f.X(0), f.Y(H), f.L(1.0), f.L(H), fill=CONC, stroke=INK)
        s2.poly([(f.X(0), f.Y(H)), (f.X(0), f.Y(0)), (f.X(-1.9), f.Y(0)), (f.X(-0.55), f.Y(H))], fill='#c77d16', op=0.3, stroke='#c77d16')
        s2.tag(f.X(-1.1), f.Y(H + 0.3), 'soil + surcharges', '#8a5a10')
        face = 1.0 if engaged else 0.0
        s2.line(f.X(face), f.Y(0), f.X(face), f.Y(1.3), HL, 4.5)
        if engaged:
            s2.tag(f.X(1.05), f.Y(2.3), 'tension face', HL, 'start')
            s2.arrow(f.X(0), f.Y(g['zs']), f.X(-1.6), f.Y(g['zs']), STRAP, 3)
            s2.tag(f.X(-1.55), f.Y(g['zs']) - 9, sym('f_str') + '·' + sym('b_s'), STRAP, 'start')
            s2.dim(f.X(1.35), f.Y(0), f.X(1.35), f.Y(g['zs']), sym('z_strap'), BLUE)
            s2.arc(f.X(0.5), f.Y(0), 22, 30, 150, HL)
            s2.tag(f.X(0.5), f.Y(0) - 30, sym('M_en'), HL)
        else:
            s2.arrow(f.X(-1.2), f.Y(H * 0.4), f.X(0) - 1, f.Y(H * 0.4), HL, 2.4)
            s2.tag(f.X(-1.25), f.Y(H * 0.4) - 7, sym('V_sl'), HL, 'start')
            s2.tag(f.X(0) - 6, f.Y(0.45), 'tension face', HL, 'end')
            s2.dim(f.X(-2.2), f.Y(0), f.X(-2.2), f.Y(H), sym('H_bw'), BLUE, side=1)
            s2.arc(f.X(0.5), f.Y(0), 22, 150, 30, HL)
            s2.tag(f.X(0.5), f.Y(0) - 30, sym('M_sl'), HL)
    return {'section': s1.render(), 'strip': s2.render()}


def render_figures(e, scale=2.5):
    edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    if not edge.exists():
        raise SystemExit('Microsoft Edge is needed to redraw the figures.')
    FIGURES.mkdir(parents=True, exist_ok=True)
    for name, svg in figures(e).items():
        w = int(re.search(r'width="(\d+)"', svg).group(1)); h = int(re.search(r'height="(\d+)"', svg).group(1))
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / f'{name}.html'
            page.write_text(f'<html><head><meta charset="utf-8"><style>body{{margin:0;background:#fff}}</style></head><body>{svg}</body></html>',
                            encoding='utf-8')
            subprocess.run([str(edge), '--headless=new', '--disable-gpu', '--hide-scrollbars', f'--force-device-scale-factor={scale}',
                            f'--screenshot={FIGURES / (name + ".png")}', f'--window-size={w},{h}', page.as_uri()],
                           capture_output=True, timeout=90, check=False)
        print('drew', FIGURES / f'{name}.png')


# ----------------------------------------------------------------------------- build
def notebook_revision():
    import json
    nb = json.loads((ROOT / 'End_Bent_Backwall_Design.ipynb').read_text(encoding='utf-8'))
    source = ''.join(next(c for c in nb['cells'] if c.get('id') == 'e3b0a7c1')['source'])
    return source.split('revision = "', 1)[1][:12]


def notebook_values_note(env):
    f = lambda name, unit: _to(env[name], unit)
    return (f'Notebook values for comparison: f_str,s = {f("f_str_s", "klf"):.3f} klf; f_str,u = {f("f_str_u", "klf"):.3f} klf; '
            f'M_u,FF = {f("M_u_FF", "kip*ft"):.3f} kip-ft; M_u,SF = {f("M_u_SF", "kip*ft"):.3f} kip-ft; V_u,bw = {f("V_u_bw", "kip"):.3f} kip; '
            f'T_u = {f("T_u", "kip*ft"):.2f} kip-ft; largest D/C = {env["DC_max"].v:.3f}.')


def build(repo=ROOT, info=None):
    """The worksheet XML. `info`, when given, receives page_fills: points used on each page (no region crosses a page)."""
    e = evaluate()
    rev = notebook_revision()
    blocks = sheet(rev)
    check_names(blocks)
    check_inputs(blocks, e)
    env = verify(blocks, e)
    blocks.append(N(notebook_values_note(env)))
    text = document(blocks, title='End Bent 1 Backwall, Cheek Walls and Tie-Back Straps',
                    description=f'Written by scripts/build_backwall_mathcad.py from the D2MPDB end_bent_walls notebook (package {rev}).',
                    seed=int(rev, 16), figures_dir=FIGURES)
    fills = layout(blocks).check_pages()            # no text, math or picture region straddles a page
    if info is not None:
        info['page_fills'] = [round(f) for f in fills]
    return text


def main():
    if '--render-figures' in sys.argv:
        render_figures(evaluate())
    info = {}
    text = build(info=info)
    (ROOT / OUTPUT).write_text(text, encoding='utf-8', newline='\n')
    fills = info['page_fills']
    print(f'Wrote {OUTPUT}: {len(text) // 1024} KB; every Mathcad expression matches the notebook; '
          f'{len(fills)} pages, fullest {max(fills)} of {mathcad_sheet.PAGE_H:g} pt.')


if __name__ == '__main__':
    main()