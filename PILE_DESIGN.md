# Pile analysis and design: prestressed concrete and steel pipe

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Pile_Design.ipynb)

[Pile_Design.ipynb](Pile_Design.ipynb) analyzes and designs the piles of the D2 I-95 pedestrian bridge: square prestressed concrete (PSC) piles at the two end bents and noncomposite steel pipe piles at the pier. It follows AASHTO LRFD Bridge Design Specifications, 10th edition (2024), with the FDOT Structures Design Guidelines (SDG) and Structures Detailing Manual (SDM) of January 2026 and FDOT Standard Plans Index 455 (FY 2026-27). Loads are read from the FB-MultiPier (FBMP) 6.1.0 XML exports, so every load value traces to a registered or uploaded file. The calculation package is `pile_design/`. It shares the unit-aware formula engine, MathML report and D/C register used by the cap and backwall notebooks.

## Scope

**In scope**

- Square prestressed concrete piles with the strand-pattern options of Standard Plans Index 455-014, 455-018, 455-024 and 455-030.
- Noncomposite steel pipe piles of ASTM A252 Grade 3 or API 5L, as permitted by FDOT Specification 455-8.2 and Table 962-11.
- Structural strength and service checks: axial compression, combined axial and biaxial flexure, shear, service stresses, and pile size and spacing policy.
- Geotechnical nominal bearing resistance (SDG 3.5.13, Eq. 3-1) and the Pile Data Table (SDM 11.4).
- Drag load DR from the 18-ton downdrag on the end bent piles.

**Out of scope**

- **Composite CFST.** The FBMP model shows no concrete fill, so the pier pipe is analyzed as noncomposite.
- **Drivability and driving stresses** (LRFD 10.7.8; Spec 455 driving limits). These are listed as pending and are not computed.
- **Minimum tip elevation** (SDG 3.5.9). This stays in `Cap_and_Pile_Design.ipynb`. Pile_Design.ipynb takes the minimum tip as an input from that handoff.
- **Pile-to-cap connection design.** The moment transfer at the 12-in embedment is reported and kept pending.
- **Scour computation.** Scour resistance enters as an input and stays pending.
- **Lateral p-y and P-Δ analysis.** FBMP performs it. This notebook reports the LRFD column check with its own inputs beside the FBMP demands.
- **Battered piles** (SDG 3.5.8; not used) and **test pile length** (entered as N/A).

## Basis

| Subject | Basis |
| --- | --- |
| Sources | FBMP exports registered in `project_current/source_register.csv` (EB-XML, EB2-XML, PIER-XML and the minimum-tip variants); cap cases `project_current/cap_design/*/selected_case.json`; downdrag from the geotechnical engineer; Standard Plans Index 455; Specifications 455 and 962. |
| Decisions | D-004 common end-bent basis; D-049 selects the latest fixed-run FBMP XMLs as raw analysis sources; D-050 adopts this notebook and the 18-ton downdrag. Selection and adoption are not engineering acceptance. |
| Codes | AASHTO LRFD BDS 10th edition (2024); FDOT SDG and SDM January 2026; FDOT Standard Plans Index 455 (FY 2026-27); FDOT Specifications 455, 931, 933 and 962 as cited. |
| Combinations | Strength I, Strength III (FBMP WS1 and WS2) and Service I (FBMP WS3). The exports contain no Strength IV, Strength V or Extreme Event combinations. |

## Sources and load records

**FBMP exports.** The three fixed-run exports were registered in commit 976a4e8 (D-049). `End Bent 1_Fixed.XML` (EB-XML, sha c1a4afa1…) and `End Bent 2_Fixed.XML` (EB2-XML, sha 3543df29…) describe 18-in square PSC piles, four per bent at 54 in. Each End Bent has its own export and preset. `Pier_Fixed.XML` (PIER-XML, sha bb73e6ad…) describes 20-in steel pipe piles, four per bent at 60 in. All three files are read with `pier_cap.pile_review.import_pile_xml`. Pile head forces are element-end records at local element 1, I end. FBMP Z increases downward, so the cutoff elevation is −Z_head/12 ft. Ground is the top of soil layer 1. Axial force is tension-positive in the import and is reversed to compression-positive in the demand records. A saved case keeps the demand records, so it recalculates without the XML. The three registered exports are embedded in the portable notebook. Uploading a newer XML replaces the embedded copy and records a register receipt.

**Cap cases.** `N_pile`, `S_pile`, `D_pile` and `Pile_embed` (12 in) come from `selected_case.json`. The notebook records the source of each value.

**Downdrag.** The geotechnical engineer gives 18 tons per pile on the end bent piles, supplied by the user on 19 October 2026. The pier carries 0 tons. The downdrag appears on the plans as SDG 3.5.6 requires. SDG 3.5.6 defines downdrag as ultimate skin friction above the neutral point plus dynamic resistance above it minus live load, and it prohibits discounting scourable layers. The value is an input with its source text, so a revised value from the geotechnical engineer replaces it without code changes.

**Standard Plans Index 455.** The strand options, spiral details and dowels in the prestressed pile method below are taken from the FY 2026-27 sheets (last revision 11/01/25).

## Loads

**Demand records.** The notebook builds one record for each combination, pile and element-end station. Each record carries the FBMP axial force, shear, moments and resultant moment, plus the factored compression with drag:

P_u = P_FBMP + γ_DR · DD

where DD is the downdrag in kips. DD is applied at every station. This is conservative, and the notebook states that choice.

**Head envelope.** For each limit state the notebook reports the largest compression and the largest uplift at the pile head, with concurrent moments.

- **Factored Design Load (FDL)** is the largest strength-limit head compression without downdrag. SDM 11.4 column I uses it, and downdrag is shown separately in column J.
- **Tension resistance** is the largest strength-limit head uplift, or 0 when no uplift occurs.

**Drag load factors.** LRFD Table 3.4.1-1 gives the drag load DR these factors. Section 10.7.1.6.2 requires DR to be evaluated for the structural limit states and set to zero for the geotechnical strength limit state. Section 10.7.3.7 requires the pile to be designed structurally for drag plus structure loads at all structural limit states, with the toe fixed.

| Limit state | γDR | Use in this notebook |
| --- | --- | --- |
| Structural strength (Strength I, II, III, V) | 1.10 | P_u for structural checks |
| Service I | 1.00 | P_u for service stresses |
| Geotechnical strength | 0.00 | Downdrag enters Eq. 3-1 instead |

Strength IV does not include DR, and no Strength IV combination appears in the exports.

**Nominal bearing resistance.** SDG 3.5.13, Eq. 3-1 gives the required resistance:

R_n ≥ (Factored Design Load + Net Scour Resistance + Downdrag) / φ

The nominal bearing resistance (NBR) is the value in column C of the Pile Data Table. φ comes from SDG Table 3.5.7-1, with 0.75 as the default. Self-weight of the pile is neglected (SDG 3.5.1.H). All piles in a bent receive the same required driving resistance (SDG 3.5.13.E). Net scour resistance defaults to 0 and stays pending.

## Resistance factors

**Structural (LRFD Article 5 and 6).**

| Item | Factor | Article |
| --- | --- | --- |
| Prestressed concrete, compression-controlled (spiral) | φ = 0.75 | 5.5.4.2 |
| Prestressed concrete, tension-controlled (bonded strand) | φ = 1.00 | 5.5.4.2 |
| Transition between the two | linear between net tensile strain 0.002 and 0.005 | 5.5.4.2, 5.6.2.1 |
| Prestressed concrete shear | φv = 0.90 (input default) | 5.5.4.2 |
| Resistance during pile driving | φ = 1.00 | 5.5.4.2, 6.5.4.2 |
| Steel pipe axial, severe driving (tip needed) | φc = 0.60 | 6.5.4.2 |
| Steel pipe axial, good driving, no tip | φc = 0.70 (input default) | 6.5.4.2 |
| Steel pipe combined axial and flexure, undamaged pile | φc = 0.80; φf = 1.00 | 6.5.4.2 |
| Steel pipe shear | φv = 1.00 | 6.12.1.2.3b |

**Geotechnical (SDG Table 3.5.7-1, which replaces LRFD 10.5.5.2.3-1).** Lateral analysis uses φ = 1.00 for FBPier (SDG 3.4).

| Test condition (driven piles, compression, Davisson) | Compression φ | Uplift φ |
| --- | --- | --- |
| 100% dynamic testing, PDA signal matching | 0.75 | 0.60 |
| 100% dynamic testing, EDC top and tip | 0.80 | 0.65 |
| 100% dynamic testing, plus static load test | 0.85 | 0.65 |
| 100% dynamic testing, plus Statnamic | 0.80 | Not in the build specification; to be transcribed |
| At least 5% dynamic testing | 0.65, 0.75, 0.70 (rows to be mapped) | 0.55, 0.60 (rows to be mapped) |

The default `phi_geo` is 0.75, the PDA row. Footnote 7 of the table states that Pile Data Tables use the default 0.75. The mapping of the 5% dynamic-testing values to their rows is pending transcription from SDG 3.5.7.

## Prestressed concrete pile method

### Section and strand options

Standard Plans Index 455 places one strand at each corner. The remaining strands are spaced equally between the corner strands, and the pattern is concentric. All strands are Grade 270 low-relaxation strand (LRS). Jacking force is given per strand in kips.

| Index | Size and void | Spiral | Dowels (splice) | Strand options (count ~ diameter @ jacking kip) |
| --- | --- | --- | --- | --- |
| 455-014 | 14 in square | W3.4 at 6 in full length; ends 16 turns at 3 in and 5 turns at 1 in | 4 ~ #10 | 8 ~ 0.6 in @ 33; 8 ~ ½ in (Special) @ 31; 8 ~ ½ in @ 31; 12 ~ 7/16 in @ 21; 16 ~ 3/8 in @ 16 |
| 455-018 | 18 in square | W3.4 as above | 8 ~ #10 | 12 ~ 0.6 in @ 35; 12 ~ ½ in (Special) @ 34; 16 ~ ½ in @ 26; 20 ~ 7/16 in @ 21; 24 ~ 3/8 in @ 17 |
| 455-024 | 24 in square | W3.4 as above | 12 ~ #10 | 16 ~ 0.6 in @ 44; 20 ~ ½ in (Special) @ 34; 24 ~ ½ in @ 31 |
| 455-030 | 30 in, with an 18 in diameter void; solid sections 11 ft 0 in at head and tip | W4.0; the section note gives 6 in pitch full length, the elevation shows 2 in pitch with 4 turns at 1½ in at the ends (both recorded, flagged for verification) | 12 ~ #10 | 20 ~ 0.6 in @ 41; 24 ~ ½ in (Special) @ 34; 28 ~ ½ in @ 29 |

Nominal strand areas are 0.085 in² (3/8 in), 0.115 in² (7/16 in), 0.153 in² (½ in), 0.167 in² (½ in Special) and 0.217 in² (0.6 in). The strand properties are f_pu = 270 ksi, f_py = 0.9 f_pu = 243 ksi and E_p = 28,500 ksi.

Strand coordinates are generated from the option. Each strand sits `d_edge` from each face, with `d_edge` = 3.5 in by default. This matches the ±5.5-in strand coordinates of the FBMP end bent XML on the 18-in pile. Index 455-001 requires 3 in clear cover to the spiral. The gross area is A_g = D², with the chamfers ignored. The contractor may cast the 455-030 pile solid, with a strand configuration that gives 1,000 psi net prestress after losses.

Concrete strength is f'c = 6.5 ksi by default, read from the FBMP export FPC. That value is FDOT Class V (Specification 346). 6.0 ksi is only a synthetic test case. Index 455-001 requires Class V concrete, with Class VI for the high-moment Index 455-031 pile, and strength at transfer of at least 4,000 psi.

### Prestress and losses

The effective prestress uses the jacking force and the loss fraction:

f_pe = (P_jack / A_strand) · (1 − loss_frac)

with loss_frac = 0.20 by default. For the 18-in pile, 12 strands × 0.6 in at 35 kip give P_jack = 420 kip and P_e = 336 kip, which is the prestress carried by the FBMP model. The effective prestress is f_pc,eff = P_e / A_g. Standard Plans piles are designed for about 1,000 psi uniform compression after losses. The notebook checks f_pc,eff ≥ 0.7 ksi (LRFD 5.12.9.4.3) and reports it against the 1.0 ksi FDOT basis as information.

**Mechanical splice.** FDOT Specification 455-7.8 Table 455-2 gives the splice bending strength: 245 kip-ft for 18 in, 600 kip-ft for 24 in and 950 kip-ft for 30 in. The splice must develop the pile, so the table value is shown as information beside the computed pure-bending φM_n at P = 0. It is not a check on the pile itself.

### Strain compatibility and interaction

The interaction diagram comes from strain compatibility at each neutral-axis depth c:

- Concrete crushing strain ε_cu = 0.003. The stress block depth is a = β1 c, with β1 = 0.85 − 0.05(f'c − 4) limited to the range 0.65 to 0.85 (LRFD 5.6.2.2), clipped at the section depth. For bending about an axis parallel to a face, the block is a rectangle D × a. For other angles the compressed polygon is clipped from the square.
- Strand strain ε_i = ε_pe + ε_ce + ε_cu (d_i − c) / c, where ε_pe = f_pe / E_p and ε_ce = f_pc,eff / E_c.
- Concrete modulus E_c = 120,000 K_1 w_c² f'c^0.33 with w_c in kcf (LRFD 5.4.2.4-1). K_1 = 1.0 and w_c = 0.150 kcf by default.
- Strand stress from the PCI power formula for 270-ksi low-relaxation strand: f_ps = E_p ε [0.025 + 0.975 / (1 + (118 ε)^10)^0.1], limited to f_pu. For compressive strain the stress is E_p ε, with no concrete-displacement correction, and the notebook states that choice.
- Nominal axial resistance P_n = 0.85 f'c A_block − Σ A_ps,i f_ps,i. The cap P_n ≤ P_n,max applies, with P_n,max = 0.85[0.85 f'c (A_g − A_ps) − A_ps (f_pe − E_p ε_cu)] per LRFD 5.6.4.4-2 with no mild steel.
- Net tensile strain ε_t = ε_cu (d_t − c) / c, where d_t is the depth of the extreme tension strand. Net strain excludes prestress (LRFD C5.6.2.1).
- Factored resistances P_r = φP_n and M_r = φM_n, with φ from the strain as in the resistance factor table.

The c grid runs geometrically from 0.02 D to 4 D and includes the pure-compression point. The pure-tension point P_n = −A_ps f_py has φ = 1.00 (LRFD 5.6.6.1) and is included for completeness. The demand eccentricity e = M/P locates the capacity on the curve by linear interpolation between adjacent sweep points.

### Biaxial flexure

For a square section the uniaxial curve applies about both axes. Two routes are computed, and the larger ratio governs as the conservative value.

- **LRFD route (5.6.4.5).** If P_u ≥ 0.10 φ f'c A_g, the reciprocal load equation applies: 1 / P_rxy = 1 / P_rx + 1 / P_ry − 1 / (φP_o). Otherwise the moment interaction applies: M_ux / M_rx + M_uy / M_ry ≤ 1. P_rx and P_ry are taken where the rays of eccentricity e_y = M_ux / P_u and e_x = M_uy / P_u meet the φ-curve; M_rx = M_ry is the uniaxial φM_n at P = 0 (conservative for the low axial loads of this route). The resultant-axis route below supplies the refined value, and the larger ratio governs.
- **Resultant-axis route.** The interaction curve is computed along the angle atan2(M_uy, M_ux), and M_r(P_u) is compared with the resultant moment.

### Shear

Nominal shear is V_n = min(V_c + V_s + V_p, 0.25 f'c b_v d_v + V_p) (LRFD 5.7.3.3), with

- V_c = 0.0316 β λ √f'c b_v d_v
- V_s = A_v f_y d_v cot θ / s
- d_v = max(0.9 d_e, 0.72 h) (LRFD 5.7.2.8)
- A_v,min = 0.0316 λ √f'c b_v s / f_y (LRFD 5.7.2.5)

The general procedure of LRFD 5.7.3.4.2 gives β and θ from the longitudinal strain:

ε_s = (|M_u| / d_v + 0.5 N_u + |V_u − V_p| − A_ps f_po) / (E_s A_s + E_p A_ps), with f_po = 0.7 f_pu

where N_u is positive in tension. Where A_v ≥ A_v,min, β = 4.8 / (1 + 750 ε_s) and θ = 29 + 3500 ε_s. Otherwise β = 4.8 / (1 + 750 ε_s) × 51 / (39 + s_xe), where s_xe = s_x · 1.38 / (a_g + 0.63) is limited to the range 12 to 80 in. The negative-strain branch of the 2024 text is pending transcription. The spiral contributes two legs of W3.4 (0.034 in² each), so A_v = 0.068 in² at 6-in pitch. The spiral yield strength is an input, with a default of 70 ksi (ASTM A1064 wire). The 60-ksi alternative is an input the user can select. The shear φ is 0.90.

### Service stresses

The Service I checks follow LRFD 5.9.2.3.2 with the SDG 3.5.1.A environment:

- **Compression:** 0.60 φ_w f'c under all loads (φ_w = 1 for a solid section). The limit 0.45 f'c under permanent plus prestress needs DC-only forces, so it is reported as information and stays pending.
- **Tension:** 0.19 λ √f'c (ksi) where the bonded reinforcement is not worse than moderate corrosion. Where SDG 3.5.1.A applies the severe-corrosion limit for Extremely Aggressive substructure environments, the limit is 0.0948 λ √f'c.

Stresses are σ = P/A ± M/S, with the properties of the uncracked section after losses.

### Policy checks

- **Minimum size (SDG Table 3.5.1-1).** Pedestrian bridges use 14 in as the minimum square pile, or 18 in with carbon-steel strand in Extremely Aggressive chloride environments. Vehicular bridges require 24 in in Extremely Aggressive chloride environments and 18 in elsewhere. The minimum is an input (`min_size_policy`).
- **Material (SDG 3.5.1.F).** Carbon steel strand (Specification 933) and spiral (Specification 931) apply outside Extremely Aggressive chloride exposure. CFRP or stainless steel applies otherwise.
- **Spacing (SDG 3.5.4).** Center-to-center spacing at and below design ground is at least 3.0 pile diameters. The end bents give 54/18 = 3.0 and the pier 60/20 = 3.0.
- **Head connection (SDG 3.5.1.C).** For standard FDOT square piles of 12 to 30 in, 48 in of embedment into the cap develops full bending capacity, and the pile must be solid for at least 8 ft (4 ft embedded and 4 ft below). The caps embed 12 in. The notebook therefore reports the FBMP head moment and keeps `head_connection` pending unless the entered embedment is at least 48 in.
- **Driving resistance (SDG Table 3.5.13-1).** Maximum driving resistance for prestressed piles is 200 tons for 14 in, 300 tons for 18 in, 450 tons for 24 in and 600 tons for 30 in.

## Steel pipe pile method

### Section and material

The pipe section uses D = 20 in and t = 0.48 in from the XML. The inside diameter is d = D − 2t = 19.04 in, and the closed forms are:

- A = π (D² − d²) / 4 and I = π (D⁴ − d⁴) / 64
- S = I / (D / 2), Z = (D³ − d³) / 6, r = √(I / A), and D/t

The yield strength default is F_y = 45 ksi, the value for ASTM A252 Grade 3 in Specification 962 Table 962-11. The FBMP pier model uses F_y = 60 ksi. The notebook keeps the 45-ksi default with the source note "reconcile", and `steel_grade` stays pending. API 5L grades X46 to X70 (PSL1 and PSL2) are alternatives. E_s = 29,000 ksi.

**Corrosion.** The corrosion allowance `t_corr` defaults to 0 in and stays pending under `corrosion`. LRFD 5.12.9.5.2 deducts 0.06 in from shells in corrosive environments, and the environment classification under SDG 1.4 governs.

**Composite behavior.** No concrete fill appears in the FBMP model, so the section is noncomposite.

### Axial compression

- **Slenderness (LRFD 6.9.4.2.1).** A circular tube is nonslender if D/t ≤ 0.11 E/F_y, which gives 70.9 for F_y = 45 ksi. The pier D/t = 41.67 is nonslender.
- **Effective area (LRFD 6.9.4.2.2c).** A_eff = A_g if D/t ≤ 0.11 E/F_y. Otherwise A_eff = [0.038 E/(F_y D/t) + 2/3] A_g, for D/t ≤ 0.45 E/F_y.
- **Yield and elastic loads.** P_o = F_y A_g, or F_y A_eff for a slender section. P_e = π² E A_g / (KL/r)² (LRFD 6.9.4.1.2).
- **Column curve (LRFD 6.9.4.1.1).** P_n = 0.658^(P_o/P_e) P_o when P_o/P_e ≤ 2.25, and P_n = 0.877 P_e otherwise.
- **Slenderness limit.** KL/r ≤ 120 for main members (LRFD 6.9.3).
- **Effective length (LRFD 10.7.3.13.4).** The effective length is K(L_u + L_fix), where L_u is the unsupported length in air and L_fix is the depth to fixity. For clay, L_fix = 1.4 (E_p I_w / E_s)^0.25 with E_s = 0.465 S_u (ksi). For sand, L_fix = 1.8 (E_p I_w / n_h)^0.2 with I_w in ft⁴, E_p in ksi and n_h in ksi/ft (Table C10.4.6.3-2). The default n_h is the Table C10.4.6.3-2 row for medium sand, submerged (0.556 ksi/ft in `inputs.json`); the value and its source are entered with the case. The units of the sand expression are to be verified when the code is written.
- **Nonlinear analysis.** FBMP's P-Δ analysis with p-y soil is the preferred method (C10.7.3.13.1). The LRFD column check with K(L_u + L_fix) is reported beside it.

Axial resistance is P_r = φc P_n, with φc = 0.70 by default (good driving, no tip) or 0.60 (severe driving, tip needed).

### Flexure

Circular tube flexure follows LRFD 6.12.2.2.3 with the classes defined by (D/t)(F_y/E):

- **Compact,** (D/t)(F_y/E) ≤ 0.07: M_n = M_p = F_y Z. The pier gives D/t = 41.67 and 0.07 E/F_y = 45.1 for F_y = 45 ksi, so the pier is compact in flexure. M_p = 45 Z / 12 kip-ft in these units.
- **Noncompact,** 0.07 < (D/t)(F_y/E) ≤ 0.31: M_n = (0.021 E / (D/t) + F_y) S.
- **Slender,** otherwise: M_n = F_cr S with F_cr = 0.33 E / (D/t).

The limit D/t ≤ 0.45 E/F_y also applies. Flexural resistance is M_r = φf M_n with φf = 1.00.

### Combined axial and flexure

LRFD 6.9.2.2.1 governs the interaction. With P_r = φc P_n (φc = 0.80 for undamaged piles in combined action), the ratio is:

- Pu/(2Pr) + (Mux/Mrx + Muy/Mry) ≤ 1.0 when Pu/Pr < 0.2
- Pu/Pr + (8/9)(Mux/Mrx + Muy/Mry) ≤ 1.0 when Pu/Pr ≥ 0.2 for a compact section

For a round pipe the resultant moment √(M_ux² + M_uy²) is compared with M_r, since the section is axisymmetric.

### Shear

Round HSS shear follows LRFD 6.12.1.2.3b. Nominal shear is V_n = 0.5 F_cr A_g, where

F_cr = max( 1.60 E / (√(L_v / D) (D/t)^1.25), 0.78 E / (D/t)^1.5 ), limited to 0.58 F_y

and φv = 1.00. The shear span L_v defaults to the unsupported length and is shown as information.

## Geotechnical resistance and the Pile Data Table

- **Nominal bearing resistance.** The required NBR follows SDG 3.5.13, Eq. 3-1, with the factored design load, net scour resistance and downdrag divided by φ. For prestressed piles the NBR is compared with the Table 3.5.13-1 driving limit. For steel pipe piles it is shown as information only.
- **Load-transfer multiplier.** Table 3.5.5-1 gives the P-multiplier for each row of piles. A single row gives 1.0, reported as information.
- **Minimum tip.** `EL_min_tip` is an input from the cap notebook handoff and stays pending.
- **Rounding (SDG 3.5.15).** Loads round up to the nearest ton. Minimum tip elevations round down, and pile lengths round up, each to the nearest foot. Cutoff elevations are given to 0.1 ft.

**Pile Data Table (SDM 11.4).** The Excel export keeps columns A to Q in SDM order. Columns are never deleted, and "N/A" appears where a column does not apply.

| Column | Content | Basis or rounding |
| --- | --- | --- |
| A | Pier or bent | Support label |
| B | Pile size and type ("18" Sq. Prestr. Conc.", "20" Ø Pipe") | Section |
| C | Nominal bearing resistance, tons | SDG Eq. 3-1, rounded up to the ton |
| D | Tension resistance, tons | Head-only strength uplift, rounded up to the ton; N/A for all three supports at present |
| E | Minimum tip elevation, ft | Rounded down to a whole foot |
| F | Test pile length or pile order length, ft | Rounded up to a whole foot |
| G | Required jet elevation | N/A unless entered |
| H | Required preform elevation | N/A unless entered |
| I | Factored design load, tons | Excludes downdrag |
| J | Downdrag, tons | 18 end bents; 0 pier |
| K | Total scour resistance, tons | Input, pending |
| L | Net scour resistance, tons | Input, pending |
| M | 100-year scour elevation | Input, N/A if none |
| N | Design scour (temporary bridges) | N/A |
| O | Long-term scour elevation | Input, N/A if none |
| P | Resistance factor | φ from the geotechnical table |
| Q | Pile cutoff elevation, ft | 0.1 ft |

A second sheet, "Basis", records the NBR equation, FDL, downdrag and its source, the resistance factor, the XML identity and the note that downdrag is excluded from the FDL.

## Exports

The notebook writes each export to `exports/pile-YYYYMMDD-HHMMSS/`.

- `pile_case.json`, the case with its demand records, confirmations and receipts
- `pile_calculation_report.html`, the calculation report with equations, substitutions and figures
- `pile_checks.csv`, the D/C register
- `pile_data_table.xlsx`, the SDM 11.4 Pile Data Table with its Basis sheet
- `pile_design.xmcd`, the distilled Mathcad worksheet for the current case
- `End Bent 1 Pile Design.bpad` (named after the support: End Bent 1, End Bent 2, Pier), the distilled Blockpad document for the current case, with a `verification.json` of its comparison counts and hashes
- `pile_bundle.zip`, the full set

**Distilled Mathcad.** `scripts/build_pile_mathcad.py` writes two Mathcad 15 worksheets from the shared generator `pile_design/mathcad.py`: `pile_mathcad/End Bent 1 Pile Design.xmcd` (23 pages, 2,370 values) and `pile_mathcad/Pier Pile Design.xmcd` (10 pages, 84 values). The notebook's "Distilled Mathcad .xmcd" export uses the same generator. Each sheet is titled "End Bent 1 Pile Design" or "Pier Pile Design". The worksheet holds the basis, inputs, section properties, demands, resistances, the interaction sweep as live vectors, the service and shear checks, the closed-form pipe checks, the Eq. 3-1 bearing check and a summary of the D/C ratios. In the End Bent 1 worksheet, 2,370 values match the notebook to 1 part in 10⁹, and the solved neutral-axis comparison at c_gov is approximate (2%). The worksheet is generated, so edits made in Mathcad are lost at the next rebuild. The curve points are live vectors in the worksheet. A live X-Y plot needs a Mathcad-saved template that this build does not have, so the interaction diagram in the sheet is a static picture.

**Distilled Blockpad.** `scripts/build_pile_bpad.py` writes three Blockpad documents (End Bent 1, End Bent 2, Pier) into `pile_bpad/` from `pile_design/bpad.py`, which walks the Mathcad block list; the notebook's "Export distilled Blockpad (.bpad)" button uses the same generator. Blockpad has no vector variables, so the records and the strands become numbered scalars and the 121-point interaction sweep is not written as formulas: Figure 2 is a picture of the notebook's curve, while the check at the solved neutral-axis depth c_gov, the demands, the 5.6.4.5 route and every ratio are live. The few values that need a search over the sweep are amber inputs read from the notebook. Every formula is read back and compared with the notebook and the Mathcad sheet before the file is written (see [pile_bpad/README.md](pile_bpad/README.md)). Nothing has been recalculated in Blockpad itself.

## Check register and results

The evaluation runs the checks below and reports two values. `strength_dc` is the largest structural ratio, and `max_ratio` is the largest ratio over all checks. The register is `pile_checks.csv`.

**Prestressed concrete**

- `psc_axial`: axial compression, the largest P_u over P_r,max.
- `psc_flex_bi`: combined axial and biaxial flexure. Eq. 5.6.4.5-1 applies when P_u ≥ 0.10 φ f'c A_g. Otherwise Eq. 5.6.4.5-3 applies, with M_rx = M_ry = the uniaxial φM_n at P = 0.
- `psc_flex_res`: the resultant-axis route. Strain compatibility at the demand's resultant bending angle, with the ray to the φ-curve. The larger of the two routes governs.
- `psc_shear`: general procedure, Eq. 5.7.3.4.2-2, because the W3.4 spiral gives A_v < A_v,min.
- `psc_tension`: P_n = A_ps · min(f_py, f_pe + 60 ksi) (LRFD 5.6.6.1, Eq. 5.8.2.4.1-1), with φ = 1.0.
- `psc_svc_comp`: Service I compression, 0.60 f'c.
- `psc_svc_tens`: Service I tension, 0.19√f'c ≤ 0.6 ksi, or 0.0948√f'c ≤ 0.3 ksi for Extremely Aggressive.
- `psc_prestress`: effective prestress ≥ 0.7 ksi.
- `psc_fc_driving`: concrete strength for driving, ≥ 5.0 ksi (LRFD 5.12.9.4).
- `psc_min_size`: minimum pile size (SDG Table 3.5.1-1).
- `psc_head`: head connection, PENDING below 48 in of embedment.
- `psc_splice`: splice moment against Table 455-2, INFO.

**Steel pipe**

- `pipe_slender`: slenderness class, D/t against 0.11 E/F_y.
- `pipe_klr`: KL/r ≤ 120.
- `pipe_axial`: axial compression, the largest P_u over φc,axial P_n.
- `pipe_comb`: combined axial and flexure, LRFD 6.9.2.2.1 (Eq. 6.9.2.2.1-1 in the current run).
- `pipe_flex_class`: flexure class, compact or not.
- `pipe_shear`: round HSS shear, LRFD 6.12.1.2.3b.
- `pipe_tension`: P_r = 0.95 F_y A_g (LRFD Eq. 6.8.2.1-1).

**Both families**

- `spacing`: center-to-center spacing ≥ 3.0 pile diameters (SDG 3.5.4).
- `nbr`: required bearing resistance, Eq. 3-1, against Table 3.5.13-1. For pipe piles the value is INFO only, since Table 3.5.13-1 has no pipe limit.
- `data_table`: Pile Data Table completeness. PENDING for the N/A inputs (minimum tip, scour, test pile length).
- `downdrag_plans`: downdrag shown on the plans, INFO.
- `phi_geo`: resistance-factor selection, INFO.
- `fbmp_dc`: the FBMP D/C for comparison, INFO.

**Results of the 19 October 2026 run.** These come from the registered exports. They are calculation results, not acceptance.

- End Bent 1: `strength_dc` 0.550, from Service I compression. Biaxial flexure 0.474 and 0.398 for the two routes. Shear 0.074. NBR 89.9 tons against the 300-ton driving limit, from the unrounded FDL of 49.4 tons (98.9 kip) plus 18 tons downdrag at φ = 0.75; the Pile Data Table rounds the FDL up to 50 tons and the NBR to 90 tons. 15 items pending.
- End Bent 2: `strength_dc` 0.557. Biaxial flexure 0.519 and 0.444. NBR 90 tons.
- Pier: combined 0.457 (Eq. 6.9.2.2.1-1). Axial 0.324. KL/r 43.4. Uplift 11.81 kip at depth, ratio 0.009. FDL 113 tons. NBR 150 tons. FBMP D/C 0.29.
- All numerical checks pass. The pile spacing is exactly 3.0 diameters (ratio 1.00).

## Verification targets

The tests pin these values from closed-form hand checks. The P_n,max target uses f'c = 6 ksi, a synthetic test case rather than the 6.5-ksi default.

| Quantity | Target |
| --- | --- |
| A_ps for 12 × 0.6 in strands | 2.604 in² |
| P_e with loss_frac 0.20 | 336.0 kip |
| f_pc,eff | 1.0370 ksi |
| f_pe | 129.03 ksi |
| P_n,max | 0.85[0.85·6·(324 − 2.604) − 2.604·(129.03 − 28,500·0.003)] = 1296.9 kip |
| P_r,max | 972.7 kip (tolerance 1e-6) |
| Pure-bending φM_n at P = 0 | within 15% of the Table 455-2 value of 245 kip-ft (sanity check, not a code check) |
| Pipe 20 × 0.48 in, A | 29.44 in² |
| Pipe D/t and class | 41.67 against 0.11 E/F_y = 70.9 (axial nonslender) and 0.07 E/F_y = 45.1 (compact in flexure) |

## Pending items and confirmations

**Prerequisite confirmations.** `exposure` (environment classification, SDG 1.4; default "Moderately aggressive"), `head_connection` (12-in embedment against SDG 3.5.1.C), `steel_grade` (Fy 45 ksi against the FBMP 60 ksi), `corrosion` (pipe allowance), `downdrag_source` (geotechnical report reference for 18 tons), `analysis_current` (the FBMP export matches the selected cap case and the final rerun, COH-013 and COH-028), `min_tip` (cap notebook handoff), `scour` (net and total scour resistance, scour elevations) and `drivability` (LRFD 10.7.8 and Spec 455 driving stresses, not evaluated).

**Analysis items.**

- **Pile head elevations (COH-028).** The registered exports give pile cutoffs of 41.2375 ft (End Bent 1), 41.2567 ft (End Bent 2) and 41.7717 ft (Pier), against plan cutoffs of 41.237692 ft, 41.249692 ft and 41.764940 ft. Each agrees within 0.02 ft (End Bent 1 within 0.0002 ft). The ground elevations (top of soil layer 1) are 24.01 ft, 23.59 ft and 26.05 ft. The XML head is used for forces, and both values are shown.
- **Analysis currency.** The fixed-run XMLs selected on 19 October 2026 (D-049) differ from the hashes recorded in the selected cap-report cases. The `analysis_current` confirmation stays pending until the downstream cases are reconciled.
- **Steel strength.** The notebook uses F_y = 45 ksi for ASTM A252 Grade 3. The FBMP model uses 60 ksi. Reconciliation is pending (D-050).

**Input confirmations.**

- Spiral yield strength (70 ksi default, or 60 ksi).
- Concrete strength (6.5 ksi default from FPC, FDOT Class V).
- Index 455-030 spiral pitch (6-in section note against the 2-in elevation).
- Table 3.5.7-1 rows not yet transcribed (Statnamic uplift; mapping of the 5% dynamic-testing values).
- Minimum tip elevation (`EL_min_tip`, from the cap notebook).
- Pipe moment of inertia. The build specification gives 1403.1 in⁴. The closed form π(D⁴ − d⁴)/64 with d = 19.04 in gives 1402.8 in⁴. The code uses the closed form, and the specification value is to be rechecked.
- Equation transcriptions to be checked against the LRFD pages before release: LRFD 5.6.4.4, the negative-strain branch of 5.7.3.4.2, 6.12.1.2.3b, the 6.9.4.1.1 threshold and the units of the sand term in C10.7.3.13.4.

**Other pending items.** Head moment transfer at 12-in embedment (SDG 3.5.1.C; SDM 11.6). Pile driving stresses and drivability (LRFD 10.7.8). Table 3.5.13-1 has no limit for pipe piles, so the pipe NBR is shown as information only.

## References

**AASHTO LRFD Bridge Design Specifications, 10th edition (2024)**

| Article | Governs |
| --- | --- |
| 3.4.1, Table 3.4.1-1 | Load factors for DR (γDR = 1.10 strength, 1.00 Service I, 0.00 geotechnical) |
| 3.11.8 | Drag load and downdrag |
| 5.4.2.4, Eq. 5.4.2.4-1 | Concrete modulus E_c |
| 5.5.4.2 | Resistance factors for compression, tension and shear |
| 5.6.2.1, 5.6.2.2 | Net tensile strain limits, β1 |
| 5.6.4.4, Eqs. 5.6.4.4-1, -2 | Axial resistance and P_n,max |
| 5.6.4.5 | Biaxial flexure |
| 5.6.6.1 | Pure-tension resistance |
| 5.7.2.5, 5.7.2.8 | Minimum transverse reinforcement and d_v |
| 5.7.3.3, 5.7.3.4.2 | Shear resistance and the general procedure |
| 5.9.2.3.2 | Service stress limits |
| 5.12.9.4, 5.12.9.4.3 | Driving strength; effective prestress ≥ 0.7 ksi |
| 5.12.9.5.2 | Corrosion deduction for shells |
| 6.5.4.2 | Pile resistance factors |
| 6.9.2.2.1 | Combined axial and flexure |
| 6.9.3 | Slenderness limit KL/r ≤ 120 |
| 6.9.4.1.1, 6.9.4.1.2 | Column curve and P_e |
| 6.9.4.2.1, 6.9.4.2.2c | Slenderness class and effective area |
| 6.12.1.2.3b | Round HSS shear |
| 6.12.2.2.3 | Round HSS flexure |
| 10.7.1.6.2 | Drag load for geotechnical and structural limit states |
| 10.7.3.7 | Structural design with drag load, toe fixed |
| 10.7.3.13.1, 10.7.3.13.2, 10.7.3.13.4 | Steel and prestressed pile methods; effective length |
| 10.7.5, 10.7.6, 10.7.8 | Corrosion, minimum penetration, drivability (pending) |
| C5.6.2.1 | Net tensile strain |
| C10.4.6.3-2 | Subgrade modulus n_h |
| C10.7.3.13.4 | Depth to fixity (clay and sand expressions) |

**FDOT Structures Design Guidelines, January 2026, Section 3.5 (Piles) and related items:** 3.4 (lateral resistance factor 1.00); 3.5.1.A (environment and corrosion limits); 3.5.1.C (head connection); 3.5.1.F and Table 3.5.1-1 (minimum size and material); 3.5.1.H (self-weight); 3.5.4 (spacing); 3.5.5 and Table 3.5.5-1 (P-multipliers); 3.5.6 (downdrag); 3.5.7 and Table 3.5.7-1 (geotechnical resistance factors); 3.5.8 (battered piles, not used); 3.5.9 (minimum tip, in the cap notebook); 3.5.13 and Eq. 3-1, with Table 3.5.13-1 (driving resistance); 3.5.15 (Pile Data Table rounding); 1.4 (environment classification).

**FDOT Structures Detailing Manual, January 2026:** 11.4 (Pile Data Table columns A to Q); 11.6 (pile-to-cap connection).

**FDOT Standard Plans Index 455 (FY 2026-27, last revision 11/01/25):** 455-001 (general notes, cover and concrete class); 455-014, 455-018, 455-024 and 455-030 (strand options); 455-031 (high-moment piles).

**FDOT Standard Specifications:** 455-7.8 and Table 455-2 (splice bending strength); 455-8.2 (steel pipe piling); 346 (concrete Class V); 931 (spiral); 933 (strand); 962 and Table 962-11 (ASTM A252 Grade 3 and API 5L).

**Project records:** `project_current/source_register.csv` (EB-XML, EB2-XML, PIER-XML, EB-MINTIP-XML, PIER-MINTIP-XML); `project_current/cap_design/*/selected_case.json`; `project_current/decisions.md` (D-004, D-049, D-050); `project_current/coherence/` (COH-013, COH-028); downdrag value from the geotechnical engineer, supplied by the user on 19 October 2026.

## Use and maintenance

Run all cells in Colab. Cell 1 reads the project sources and records confirmations. Cell 2 holds the inputs, the demands, the interaction diagram, the checks and the exports. The notebook reads FBMP XML uploads at run time, so an updated export replaces the registered one without a code change.

After changing `pile_design/`, rebuild the notebook and the Mathcad worksheets and run the tests:

```
.venv\Scripts\python.exe scripts\build_pile_notebook.py
.venv\Scripts\python.exe scripts\build_pile_mathcad.py
python -m unittest tests.test_pile_design tests.test_pile_design_notebook tests.test_pile_mathcad -v
```

The notebook and Mathcad tests fail when the committed notebook or worksheet is out of date. Both files are generated, so edit the generator, not the output.
