# End-bent backwall, cheek walls and tie-back straps

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/End_Bent_Backwall_Design.ipynb)

[End_Bent_Backwall_Design.ipynb](End_Bent_Backwall_Design.ipynb) replaces the template Mathcad sheet *3.End Bent 1 Backwall Design* (I-4 Bridge 920232, FC 02/2025) with a calculation built on this project's registered sources. It shares the cap notebook's unit-aware formula engine, MathML notation, Recalc control and widget/Plotly compatibility layers. The calculation package is `end_bent_walls/`.

## Basis

| Subject | Basis |
| --- | --- |
| Sources | EB-CASE, EB-XML and CAD-MODEL from `project_current`, checked against `source_register.csv` on upload; journal values for the Type F pad, temperature, span and wind; MCAD-S1 for the 90 psf pedestrian load |
| Decisions | D-004 common end-bent design; D-005 provisional walls; D-014 tie-back straps into the MSE fill; D-015 pedestrian load only; D-016 φ = 30°, γ = 115 pcf; D-017 landing slab on the backwall; D-018 cheek walls for wind only; D-019 maximum backwall height and strap near the resultant |
| Codes | AASHTO LRFD 10th edition (2024); Guide Specifications for Pedestrian Bridges; FDOT Structures Manual January 2026 (SDG and SDM) |
| Combinations | Service I, Strength I, Strength III (FBMP WS1 and WS2), Strength IV. Strength V is not required for this pedestrian bridge. TU/SH use the force-effect factor. |

## Method

1. **Loads on the end bent.** Active Coulomb earth pressure acts over the cap and backwall height (cap soffit to backwall crown, 7.08 ft) along the cap. The pedestrian load (LS) and the 4 in landing slab weight (ES) act as uniform surcharges. Bearing-level forces: temperature fall and beam shrinkage through the elastomeric pads (G × 1.15, hrt = 2.0 in, L_exp = 107.35 ft to the pier) and FBMP longitudinal wind. Vertical loads: FBMP bearing DC and PL, cap, pedestals, cheek walls and backwall.
2. **Overturning about the pile top.** SDG 3.13.2.N.3 requires the strap loading to include pile placement tolerance. Vertical-load arms therefore use the pile line shifted 3 in toward the fill. Each vertical item takes the maximum or minimum permanent-load factor according to the sign of its arm. Live load and wind uplift take no stabilizing credit. The landing slab reaction is excluded from overturning (D-017).
3. **Tie-back force.** The single pile row is effectively pinned (FBMP fixity 0.10). The design strap force is `max(H, M / y_strap)`; `M / y_strap − H` is the force the piles must supply at the pile top. The template reported ΣH under an `M/y` label; this calculation shows both and designs for the larger. Loads are reported per foot of **backwall** with the SDM 12.3.F plan note.
4. **Backwall.** The backwall is a 1-ft vertical cantilever at the cap construction joint. *Strap slack:* soil pressure causes fill-face tension. *Strap engaged:* the strap pull at its elevation exceeds the backwall soil moment and causes span-face tension. Both faces are designed:
   - flexure with the exact required-steel quadratic
   - minimum reinforcement
   - tension-controlled strain
   - crack control at fss ≤ 0.80 fy (SDG 3.10.F)
   - spacing and shrinkage/temperature steel
   - shear (β = 2)
   - interface shear (SDG 1.15)
5. **Cheek walls.** No retained fill (D-018). Strength III and Service I wind act on a 1-ft vertical strip (V = 130 / 70 mph, G = 0.85, C_D = 1.6). Cover is 2 in per SDG Table 1.4.2-1.
6. **Cap supplement.** Torsion and weak-axis bending along the cap come from discrete bearing actions against uniform strap restraint. Torsion is screened against 0.25 φ Tcr. These actions are not in the FBMP cap model.

## Differences from the template Mathcad

- Discrete two-bearing, 17'-8" cap actions replace loads spread over a 111 ft cap with 15 bearings. Skew terms drop out (0°).
- Pedestrian surcharge replaces the HL-93 equivalent height. Braking, wind on live load and vehicular surcharge are not applicable.
- The pile placement tolerance (SDG January 2026) and every dead-load arm enter the overturning sum.
- The backwall is designed for the engaged-strap reversal. The template ignored the strap load in backwall design, which is unconservative for the span face and the joint.
- Required steel uses the exact quadratic. The template's `Find` held the stress-block depth at its provided-steel value: 0.2197 in² against the exact 0.2185 in².
- The crack-control stress limit is 0.80 fy (SDG 3.10.F), not 0.6 fy.

## Results with the registered defaults (12 October 2026)

| Item | Value |
| --- | --- |
| Tie-back load per foot of backwall | 3.62 kip/ft service · 4.33 kip/ft factored (Strength I) |
| Strength I resultant | 5.81 ft above the pile top; strap at 3.50 ft |
| Pile-head force for equilibrium | up to 28.1 kip (Strength I); not in the FBMP model |
| Backwall φMn, #5 @ 12 in each face | 11.89 kip-ft per ft; demand 1.30 (fill face) and 5.19 (span face) |
| Cap torsion screen | 50.8 kip-ft vs 0.25 φ Tcr = 81.2 kip-ft |
| Check register | All numerical checks pass; prerequisites remain pending |

The resultant sits high because the toleranced bearing eccentricity (6 in) carries about 45% of the overturning. Raising the strap toward the resultant (for example 3.0 ft above the cap top: 3.03 kip/ft factored, 6.9 kip pile force) reduces both the strap load and the pile force. The final elevation needs MSE vendor coordination.

## Pending before final design

- SDG 3.13.2.N.3: geotechnical confirmation that settlement of the soil above the cap bottom will not exceed 2 in.
- Strap elevation aligned with an MSE reinforcement level.
- Final wall geometry (D-005).
- FIB-36 shrinkage strain (the template value is a placeholder; the Span 1 `.dat` file is missing).
- Strength III K_Z for the cheek walls.
- Landing slab length.
- Environmental classification for the covers.
- **FBMP source audit.** In `End Bent 1_Fixed.XML` one 3.0 kip DC end load is on node 4, which is pile 4's head, not the right cap end (node 44).

## Use and maintenance

Run all cells in Colab. Cell 1 re-reads registered files and records confirmations. Cell 2 holds inputs, drawings, overturning tables, the D/C register with *Equation & values*, reviews and exports:
- case JSON
- HTML report
- checks CSV
- MSE strap handoff workbook

After changing `end_bent_walls/` or the shared `pier_cap/` modules, run `python scripts/build_backwall_notebook.py`. Then run `python -m unittest tests.test_end_bent_walls`. The tests reproduce the template's flexure, crack-control and shear values with its own inputs, pin the project statics, and verify that the embedded package matches the repository files.
