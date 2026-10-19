"""Pile section resistance: prestressed concrete square piles and steel pipe piles.

Pure numpy/math numerical routines (inch, kip, ksi; moments in kip-ft unless a
name says kip-in). Nothing here uses the unit-aware Engine; model.py reproduces
the closed-form pieces as Engine formulas and the tests prove both agree.

Prestressed concrete (LRFD 10th ed., 2024)
  5.6.4.4-2   Pn,max = 0.85[kc f'c (Ag - Aps) - Aps (fpe - Ep ecu)]   (spiral, Ast = 0)
  5.6.4.5     biaxial flexure with compression (Eqs. 5.6.4.5-1, -2, -3)
  5.6.2.1/5.5.4.2  phi from the net tensile strain, 0.75 -> 1.00 for 0.002 -> 0.005
  5.6.6.1 / 5.8.2.4.1-1  tension: Pn = Aps min(fpy, fpe + 60 ksi) when Ast = 0
  5.7.3.3, 5.7.3.4.2  shear, general procedure (Eqs. 5.7.3.4.2-1 to -4, -7)
  5.9.2.3.2a/b service stress limits
Steel pipe
  6.9.4.1.1, 6.9.4.1.2, 6.9.4.2.2c  axial compression, local buckling
  6.12.2.2.3 flexure of circular tubes, 6.9.2.2.1 combined axial and flexure
  6.12.1.2.3b shear of round tubes, 6.8.2.1-1 tension, 10.7.3.13.4 depth to fixity
"""
import math
import numpy as np

EPS_CU = 0.003          # LRFD 5.6.2.1 concrete crushing strain
EPS_CL = 0.002          # compression-controlled strain limit, 5.6.2.1
EPS_TL = 0.005          # tension-controlled strain limit, 5.6.2.1
PI = math.pi


# --------------------------------------------------------------------------- strands
def strand_layout(D, n_strands, d_edge):
    """Strand centers (x, y) [in] about the pile centroid, FDOT Standard Plans pattern.

    One strand at each corner and the remaining strands equally spaced between
    corner strands on each face; the pattern is concentric. With N strands there
    are N/4 + 1 per face. Sorted by (y, x) for a deterministic order.
    """
    n = int(n_strands)
    if n < 4 or n % 4:
        raise ValueError('Strand count must be a multiple of 4 (one strand at each corner, equal spacing).')
    k = n // 4 + 1
    half = D / 2 - d_edge
    if half <= 0:
        raise ValueError('d_edge must be smaller than half the pile size.')
    grid = np.linspace(-half, half, k)
    points = {(round(float(grid[i]), 9), round(float(grid[j]), 9))
              for i in range(k) for j in range(k) if i in (0, k - 1) or j in (0, k - 1)}
    assert len(points) == n, (len(points), n)
    return sorted(points, key=lambda p: (p[1], p[0]))


def concrete_modulus(fc, wc=0.150, K1=1.0):
    """LRFD 5.4.2.4-1: Ec = 120,000 K1 wc^2 f'c^0.33 (ksi, wc in kcf)."""
    return 120000.0 * K1 * wc ** 2 * fc ** 0.33


def beta1(fc):
    """LRFD 5.6.2.2: 0.85 - 0.05 (f'c - 4), kept in [0.65, 0.85]."""
    return min(0.85, max(0.65, 0.85 - 0.05 * (fc - 4.0)))


def kc_factor(fc):
    """LRFD 5.6.4.4: kc = 0.85 to 10 ksi, reduced 0.02 per ksi above, not below 0.75."""
    return min(0.85, max(0.75, 0.85 - 0.02 * max(fc - 10.0, 0.0)))


def psc_section(D, strands, fc, fpe, Ep=28500.0, wc=0.150, K1=1.0, d_void=0.0, fpu=270.0, fpy=243.0, Aps_each=None):
    """Gross properties and prestress state of a square pile (chamfers ignored).

    strands: list of (x, y, A) in, in, in^2, or (x, y) with Aps_each.
    """
    pts = [(s[0], s[1], s[2] if len(s) > 2 else Aps_each) for s in strands]
    x = np.array([p[0] for p in pts], float)
    y = np.array([p[1] for p in pts], float)
    A = np.array([p[2] for p in pts], float)
    Ag = D * D - PI / 4 * d_void ** 2
    Ig = D ** 4 / 12 - PI / 64 * d_void ** 4
    Aps = float(A.sum())
    Ec = concrete_modulus(fc, wc, K1)
    f_pc = fpe * Aps / Ag
    kc = kc_factor(fc)
    Po = kc * fc * (Ag - Aps) - Aps * (fpe - Ep * EPS_CU)
    return dict(D=D, d_void=d_void, x=x, y=y, A=A, Ag=Ag, Ig=Ig, S=Ig / (D / 2), r=math.sqrt(Ig / Ag), Aps=Aps,
                fc=fc, fpe=fpe, Ep=Ep, Ec=Ec, fpu=fpu, fpy=fpy, beta1=beta1(fc), kc=kc,
                eps_pe=fpe / Ep, f_pc=f_pc, eps_ce=f_pc / Ec, Po=Po, Pn_max=0.85 * Po)


def strand_stress(eps, Ep=28500.0, fpu=270.0):
    """PCI power formula for 270 ksi low-relaxation strand.

    fps = Ep e [0.025 + 0.975 / (1 + (118 e)^10)^0.1] <= fpu for e >= 0; Ep e for
    compression (no correction for displaced concrete: stated simplification).
    """
    eps = np.asarray(eps, float)
    pos = np.maximum(eps, 0.0)
    tension = np.minimum(Ep * pos * (0.025 + 0.975 / (1.0 + (118.0 * pos) ** 10) ** 0.1), fpu)
    return np.where(eps > 0, tension, Ep * eps)


def phi_flexure(eps_t, phi_c=0.75, phi_t=1.0):
    """LRFD 5.5.4.2 / 5.6.2.1: linear from phi_c at 0.002 to phi_t at 0.005 (bonded prestressed)."""
    eps_t = np.asarray(eps_t, float)
    return np.clip(phi_c + (phi_t - phi_c) * (eps_t - EPS_CL) / (EPS_TL - EPS_CL), phi_c, phi_t)


# --------------------------------------------------------------------------- polygon helpers
def _clip(poly, nx, ny, s0):
    """Sutherland-Hodgman clip of a convex polygon to the half plane n.p >= s0."""
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        sp, sq = nx * p[0] + ny * p[1] - s0, nx * q[0] + ny * q[1] - s0
        if sp >= 0:
            out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def _area_centroid(poly):
    if len(poly) < 3:
        return 0.0, 0.0, 0.0
    a = cx = cy = 0.0
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        w = p[0] * q[1] - q[0] * p[1]
        a += w
        cx += (p[0] + q[0]) * w
        cy += (p[1] + q[1]) * w
    a *= 0.5
    if abs(a) < 1e-12:
        return 0.0, 0.0, 0.0
    return a, cx / (6 * a), cy / (6 * a)


def _segment(r, h):
    """Circular segment on the far side of a chord at distance h >= 0 from the center.

    Returns (area, area * centroid distance from the center)."""
    if h >= r:
        return 0.0, 0.0
    th = math.acos(h / r)
    area = r * r * (th - math.sin(th) * math.cos(th))
    return area, 2.0 / 3.0 * r ** 3 * math.sin(th) ** 3


def _void_in_block(r, s_cut):
    """Void area and first moment (about the centroid, toward +s) inside the half plane s >= s_cut."""
    if r <= 0 or s_cut >= r:
        return 0.0, 0.0
    if s_cut <= -r:
        return PI * r * r, 0.0
    if s_cut >= 0:
        return _segment(r, s_cut)
    a, m = _segment(r, -s_cut)      # removed piece lies on the negative side
    return PI * r * r - a, m


def depth_axis(angle):
    """Unit vector toward the compression face for a bending axis at `angle` (rad)."""
    return -math.sin(angle), math.cos(angle)


def psc_interaction(sec, c_values=None, angle=0.0, n_points=121, phi_c=0.75, phi_t=1.0):
    """Nominal and factored P-M interaction by strain compatibility (LRFD 5.6.4.5, C5.6.2.1).

    Bending is about the centroidal axis at `angle` (0 = parallel to a face; the
    compression face is +y at 0). Concrete: rectangular stress block a = beta1 c on
    the actual compressed polygon (square clipped by the line at depth a; the void,
    if any, is subtracted). Strand strain = eps_pe + eps_ce + ecu (d - c)/c.

    Arrays run from pure compression (c = inf, Pn = Pn,max) to pure tension
    (c = 0, Pn = -Aps fpy, phi 1.0): c [in], Pn [kip], Mn [kip-ft], eps_t,
    phi, Pr = phi min(Pn, Pn,max), Mr = phi Mn. eps_t of the end points are -ecu and inf.
    """
    D, h = sec['D'], sec['D'] / 2
    nx, ny = depth_axis(angle)
    square = [(-h, -h), (h, -h), (h, h), (-h, h)]
    s_max = max(nx * p[0] + ny * p[1] for p in square)
    H = 2 * s_max
    d_i = s_max - (nx * sec['x'] + ny * sec['y'])        # depth of each strand from the compression fiber
    s_i = nx * sec['x'] + ny * sec['y']                  # coordinate toward the compression face
    dt = float(d_i.max())
    fc, b1, Ep, fpu = sec['fc'], sec['beta1'], sec['Ep'], sec['fpu']
    if c_values is None:
        c_values = np.geomspace(0.02 * H, 4.0 * H, int(n_points))
    c_values = np.sort(np.asarray(c_values, float))[::-1]
    r_void = sec['d_void'] / 2
    P, M = [], []
    for c in c_values:
        a = min(b1 * c, H)
        s_cut = s_max - a
        poly = _clip(square, nx, ny, s_cut)
        area, cx, cy = _area_centroid(poly)
        va, vm = _void_in_block(r_void, s_cut)
        net, moment = area - va, area * (nx * cx + ny * cy) - vm
        eps = sec['eps_pe'] + sec['eps_ce'] + EPS_CU * (d_i - c) / c
        force = -sec['A'] * strand_stress(eps, Ep, fpu)            # tension reduces compression
        P.append(0.85 * fc * net + float(force.sum()))
        M.append((0.85 * fc * moment + float((force * s_i).sum())) / 12.0)
    P, M = np.array(P), np.array(M)
    eps_t = EPS_CU * (dt - c_values) / c_values
    c = np.concatenate([[np.inf], c_values, [0.0]])
    T_max = sec['Aps'] * sec['fpy']       # tension limit Aps fpy (LRFD 5.6.6.1); strain-compatible points are held to it
    Pn = np.concatenate([[sec['Pn_max']], np.clip(P, -T_max, sec['Pn_max']), [-T_max]])
    Mn = np.concatenate([[0.0], M, [0.0]])
    et = np.concatenate([[-EPS_CU], eps_t, [np.inf]])
    phi = phi_flexure(np.where(np.isfinite(et), et, 1.0), phi_c, phi_t)
    return dict(c=c, Pn=Pn, Mn=Mn, eps_t=et, phi=phi, Pr=phi * Pn, Mr=phi * Mn, angle=float(angle), d_t=dt,
                Pn_max=sec['Pn_max'], Pr_max=phi_c * sec['Pn_max'])


# --------------------------------------------------------------------------- curve queries
def ray_capacity(curve, P, M):
    """Point of the phi-curve on the ray through the demand (P kip, M kip-ft >= 0).

    Returns (ratio, Pr, Mr): ratio = |demand| / |capacity point| along the ray.
    """
    Pr, Mr = curve['Pr'], curve['Mr']
    M = abs(M)
    if M < 1e-9:
        cap = Pr[0] if P >= 0 else -Pr[-1]
        return (float(abs(P) / cap) if cap > 0 else math.inf), float(Pr[0] if P >= 0 else Pr[-1]), 0.0
    g = Mr * P - Pr * M
    idx = np.nonzero(g >= 0)[0]
    k = int(idx[0]) if len(idx) else len(g) - 1
    if k == 0:
        pc, mc = float(Pr[0]), float(Mr[0])
    else:
        t = -g[k - 1] / (g[k] - g[k - 1]) if g[k] != g[k - 1] else 0.0
        pc, mc = Pr[k - 1] + t * (Pr[k] - Pr[k - 1]), Mr[k - 1] + t * (Mr[k] - Mr[k - 1])
    lam = (P * pc + M * mc) / (P * P + M * M)
    return (float(1.0 / lam) if lam > 0 else math.inf), float(pc), float(mc)


def capacity_at_eccentricity(curve, e):
    """(Pr, Mr) where the ray M = e P meets the phi-curve; e in inches, e >= 0 (5.6.4.5)."""
    e = abs(e)
    if not math.isfinite(e):
        return 0.0, moment_capacity_at_axial(curve, 0.0)
    _, p, m = ray_capacity(curve, 1.0, e / 12.0)
    return p, m


def moment_capacity_at_axial(curve, Pu):
    """Mr (kip-ft) at the factored axial load Pu (compression +): the outer boundary of the curve."""
    Pr, Mr = curve['Pr'], curve['Mr']
    best = 0.0
    for i in range(len(Pr) - 1):
        lo, hi = sorted((Pr[i], Pr[i + 1]))
        if lo - 1e-12 <= Pu <= hi + 1e-12:
            if Pr[i + 1] == Pr[i]:
                m = max(Mr[i], Mr[i + 1])
            else:
                m = Mr[i] + (Pu - Pr[i]) / (Pr[i + 1] - Pr[i]) * (Mr[i + 1] - Mr[i])
            best = max(best, float(m))
    return best


def psc_biaxial_dc(curve, Pu, Mux, Muy, phi_Po, P_limit):
    """LRFD 5.6.4.5 for a square pile using the uniaxial curve about either axis.

    P_limit = 0.10 phi f'c Ag. At or above it, Eq. 5.6.4.5-1: 1/Prxy = 1/Prx + 1/Pry - 1/(phi Po),
    with Prx, Pry at ey = Mux/Pu, ex = Muy/Pu (already limited to phi Pn,max by the curve), ratio Pu/Prxy.
    Below it, Eq. 5.6.4.5-3: Mux/Mrx + Muy/Mry <= 1 with Mrx = Mry = the uniaxial factored flexural
    resistance at P = 0 (pure-flexure point of the phi-curve; conservative for Pu < 0.10 phi f'c Ag).
    For net tension (Pu < 0) the smaller of that and Mr at Pu is used.
    """
    Mux, Muy = abs(Mux), abs(Muy)
    if Pu >= P_limit and Pu > 0:
        ey, ex = Mux * 12.0 / Pu, Muy * 12.0 / Pu
        Prx, Mrx = capacity_at_eccentricity(curve, ey)
        Pry, Mry = capacity_at_eccentricity(curve, ex)
        Prxy = 1.0 / (1.0 / Prx + 1.0 / Pry - 1.0 / phi_Po)
        return dict(method='5.6.4.5-1', ratio=Pu / Prxy, Prx=Prx, Pry=Pry, Prxy=Prxy, ex=ex, ey=ey)
    Mr = moment_capacity_at_axial(curve, 0.0)         # uniaxial factored flexural resistance, pure flexure (conservative for Pu >= 0)
    if Pu < 0:
        Mr = min(Mr, moment_capacity_at_axial(curve, Pu))
    ratio = (Mux + Muy) / Mr if Mr > 0 else math.inf
    return dict(method='5.6.4.5-3', ratio=ratio if (Mux + Muy) > 0 else 0.0, Mrx=Mr, Mry=Mr)


def psc_tension_side(sec, angle=0.0):
    """Strand area on the flexural tension half-depth and its effective depth d_e.

    5.7.3.4.2: Aps is the prestressing on the flexural tension side (half depth);
    d_e is measured from the extreme compression fiber to the centroid of that steel.
    """
    nx, ny = depth_axis(angle)
    h = sec['D'] / 2
    s_max = max(nx * px + ny * py for px, py in ((-h, -h), (h, -h), (h, h), (-h, h)))
    s = nx * sec['x'] + ny * sec['y']
    mask = s < -1e-9
    A = sec['A'][mask]
    Aps_t = float(A.sum())
    d_e = float(s_max - (A * s[mask]).sum() / Aps_t)
    return Aps_t, d_e


# --------------------------------------------------------------------------- shear
def psc_shear(Vu, Mu, Pu, D, bv, Aps_t, d_e, Ag, Ec, fc, Av, s, fy, a_g, fpu=270.0, Ep=28500.0,
              lam=1.0, phi_v=0.9):
    """General procedure shear resistance, LRFD 5.7.3.3 and 5.7.3.4.2 (Vp = 0, As = 0).

    Vu kip, Mu kip-in (not kip-ft), Pu kip (compression +); lengths in inches, stresses in ksi.

    5.7.3.4.2-4: eps_s = (|Mu|/dv + 0.5 Nu + |Vu - Vp| - Aps fpo) / (Es As + Ep Aps), Nu positive in
    tension (Nu = -Pu), Mu not less than Vu dv, fpo = 0.7 fpu. If eps_s is negative it is recomputed
    with Ec Act added to the denominator (Act = half the gross area) and kept >= -0.40e-3.
    -1 with Av >= Av,min (5.7.2.5): beta = 4.8/(1 + 750 eps_s); -2 otherwise:
    beta = 4.8/(1 + 750 eps_s) 51/(39 + sxe), sxe = sx 1.38/(ag + 0.63) in [12, 80] in, sx = dv;
    -3 theta = 29 + 3500 eps_s degrees. Vc = 0.0316 beta lam sqrt(f'c) bv dv; Vs = Av fy dv cot(theta)/s;
    Vn = min(Vc + Vs, 0.25 f'c bv dv).
    """
    dv = max(0.9 * d_e, 0.72 * D)
    Mu_v = max(abs(Mu), abs(Vu) * dv)
    Nu = -Pu
    fpo = 0.7 * fpu
    num = Mu_v / dv + 0.5 * Nu + abs(Vu) - Aps_t * fpo
    eps0 = num / (Ep * Aps_t)
    eps1 = num / (Ep * Aps_t + Ec * Ag / 2.0)
    eps_s = max(eps1 if eps0 < 0 else eps0, -0.0004)
    Av_min = 0.0316 * lam * math.sqrt(fc) * bv * s / fy
    sxe = min(80.0, max(12.0, dv * 1.38 / (a_g + 0.63)))
    base = 4.8 / (1.0 + 750.0 * eps_s)
    beta = base if Av >= Av_min else base * 51.0 / (39.0 + sxe)
    theta = 29.0 + 3500.0 * eps_s
    Vc = 0.0316 * beta * lam * math.sqrt(fc) * bv * dv
    Vs = Av * fy * dv / (math.tan(math.radians(theta)) * s)
    Vn = min(Vc + Vs, 0.25 * fc * bv * dv)
    return dict(dv=dv, Mu_v=Mu_v, eps_s0=eps0, eps_s=eps_s, Av_min=Av_min, Av_ok=Av >= Av_min, sxe=sxe,
                beta=beta, theta=theta, Vc=Vc, Vs=Vs, Vn=Vn, Vr=phi_v * Vn, ratio=abs(Vu) / (phi_v * Vn))


def psc_tension(Aps, fpe, fpy=243.0, phi=1.0, fy_nominal=60.0):
    """LRFD 5.6.6.1 with Pn from 5.8.2.4.1-1: Pn = fy Ast + Aps (fpe + fy), (fpe + fy) <= fpy.

    With no nonprestressed steel fy is taken as 60 ksi (C5.8.2.4.1); Pr = phi Pn, phi from 5.5.4.2.
    Returns (Pn, Pr)."""
    Pn = Aps * min(fpy, fpe + fy_nominal)
    return Pn, phi * Pn


def psc_service_stress(P_service, Mx, My, f_pc_eff, Ag, S):
    """Corner stresses (ksi, compression +) at Service I after losses (5.9.2.3.2).

    sigma = f_pc + P/Ag +- (|Mx| + |My|)/S with moments in kip-ft; the biaxial corner uses the sum
    of the component moments (square section). Returns (sigma_max, sigma_min)."""
    flex = (abs(Mx) + abs(My)) * 12.0 / S
    base = f_pc_eff + P_service / Ag
    return base + flex, base - flex


def service_tension_limit(fc, severe, lam=1.0):
    """LRFD Table 5.9.2.3.2b-1: 0.19 lam sqrt(f'c) <= 0.6 ksi; severe corrosion 0.0948 lam sqrt(f'c) <= 0.3 ksi."""
    if severe:
        return min(0.3, 0.0948 * lam * math.sqrt(fc))
    return min(0.6, 0.19 * lam * math.sqrt(fc))


# --------------------------------------------------------------------------- steel pipe
def pipe_section(D, t):
    """Gross properties of a circular tube: A, I, S, Z, r, D/t."""
    Di = D - 2 * t
    A = PI / 4 * (D * D - Di * Di)
    I = PI / 64 * (D ** 4 - Di ** 4)
    return dict(D=D, t=t, Di=Di, A=A, I=I, S=I / (D / 2), Z=(D ** 3 - Di ** 3) / 6.0, r=math.sqrt(I / A), D_t=D / t)


def depth_to_fixity(Ep, Iw_ft4, soil_type, nh=None, Su=None):
    """LRFD C10.7.3.13.4 (ft). Clay: 1.4 [Ep Iw/Es]^0.25, Es = 0.465 Su (ksi, Su in ksf);
    sand: 1.8 [Ep Iw/nh]^0.2 with nh in ksi/ft (Table C10.4.6.3-2). Ep in ksi, Iw in ft^4."""
    if soil_type in ('clay', 1):
        if not Su or Su <= 0:
            raise ValueError('Clay depth to fixity needs Su > 0.')
        return 1.4 * (Ep * Iw_ft4 / (0.465 * Su)) ** 0.25
    if not nh or nh <= 0:
        raise ValueError('Sand depth to fixity needs nh > 0.')
    return 1.8 * (Ep * Iw_ft4 / nh) ** 0.2


def pipe_axial(p, Fy, E, KL, phi_axial=0.70, phi_comb=0.80):
    """LRFD 6.9.4.1.1 and 6.9.4.1.2 with the 6.9.4.2.2c effective area for slender tubes.

    p: pipe_section dict; KL effective length in inches. Pn = 0.658^(Po/Pe) Po if Pe/Po >= 0.44
    else 0.877 Pe; Pe = pi^2 E Ag/(KL/r)^2; Po = Fy Aeff."""
    Dt = p['D_t']
    lam_r = 0.11 * E / Fy
    Aeff = p['A'] if Dt <= lam_r else (0.038 * E / (Fy * Dt) + 2.0 / 3.0) * p['A']
    Po = Fy * Aeff
    KLr = KL / p['r']
    Pe = PI ** 2 * E * p['A'] / KLr ** 2
    Pn = 0.658 ** (Po / Pe) * Po if Pe / Po >= 0.44 else 0.877 * Pe
    return dict(lam_r=lam_r, slender=Dt > lam_r, within_limit=Dt <= 0.45 * E / Fy, Aeff=Aeff, Po=Po, KLr=KLr, Pe=Pe,
                Pe_Po=Pe / Po, branch='inelastic (0.658)' if Pe / Po >= 0.44 else 'elastic (0.877 Pe)', Pn=Pn,
                Pr_axial=phi_axial * Pn, Pr_comb=phi_comb * Pn)


def pipe_flexure(p, Fy, E, phi_f=1.0):
    """LRFD 6.12.2.2.3 circular tubes: compact D/t <= 0.07E/Fy, Mn = Mp = Fy Z; noncompact to 0.31E/Fy,
    Mn = (0.021E/(D/t) + Fy) S (not above Mp); slender Mn = 0.33E/(D/t) S. D/t <= 0.45E/Fy. kip-ft."""
    Dt = p['D_t']
    Mp = Fy * p['Z'] / 12.0
    if Dt <= 0.07 * E / Fy:
        cls, Mn = 'compact', Mp
    elif Dt <= 0.31 * E / Fy:
        cls, Mn = 'noncompact', min(Mp, (0.021 * E / Dt + Fy) * p['S'] / 12.0)
    else:
        cls, Mn = 'slender', 0.33 * E / Dt * p['S'] / 12.0
    return dict(cls=cls, Mp=Mp, Mn=Mn, Mr=phi_f * Mn, within_limit=Dt <= 0.45 * E / Fy)


def pipe_interaction_dc(Pu, Pr, Mu_res, Mr):
    """LRFD 6.9.2.2.1: Pu/Pr >= 0.2 -> Pu/Pr + 8/9 M/Mr (-1); else Pu/(2 Pr) + M/Mr (-2).
    The round pipe uses the resultant moment against Mr (axisymmetric). Pu is the magnitude of the axial
    force and Pr the matching compression or tension resistance."""
    ratio_p = abs(Pu) / Pr
    m = Mu_res / Mr
    if ratio_p >= 0.2:
        return dict(branch='6.9.2.2.1-1', ratio=ratio_p + 8.0 / 9.0 * m, Pu_Pr=ratio_p)
    return dict(branch='6.9.2.2.1-2', ratio=ratio_p / 2.0 + m, Pu_Pr=ratio_p)


def pipe_shear(p, Fy, E, Lv, phi_v=1.0):
    """LRFD 6.12.1.2.3b: Vn = 0.5 Fcr Ag; Fcr = larger of 1.60E/[sqrt(Lv/D)(D/t)^1.25] and 0.78E/(D/t)^1.5,
    not above 0.58 Fy; Lv in inches (distance between maximum and zero shear)."""
    Dt = p['D_t']
    f1 = 1.60 * E / (math.sqrt(Lv / p['D']) * Dt ** 1.25)
    f2 = 0.78 * E / Dt ** 1.5
    Fcr = min(max(f1, f2), 0.58 * Fy)
    Vn = 0.5 * Fcr * p['A']
    return dict(Fcr1=f1, Fcr2=f2, Fcr=Fcr, Vn=Vn, Vr=phi_v * Vn)


def pipe_tension(Fy, Ag, phi_y=0.95):
    """LRFD 6.8.2.1-1: Pr = phi_y Fy Ag (yielding on the gross section)."""
    return phi_y * Fy * Ag
