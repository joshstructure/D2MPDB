# Calculation scope and assumptions

This is a port of the C005 live Blockpad calculation built from the original `20. Cap Design.xmcd`. It is not an independent certification of that method or an update to every current design-code provision. The source journal hash and conversion date are in `pier_cap/data/provenance.json`.

## Starting case

- Cap cross section: 48 × 48 in; cover: 3 in to the outside of the hoop.
- Four nominal 20 in piles at 5 ft centers. Cap length is `(N−1)S + D + 2E` = 224 in.
- Nominal end extension: 12 in, from adopted 9 in actual pile-face clearance plus 3 in location tolerance. C005 uses `min(3 in, D/6)` for tolerance and an editable extra detailing allowance. This is not a universal FDOT fixed end distance. Confirm governing project criteria and development/pile-head requirements.
- Concrete 5.5 ksi; reinforcing yield strength 60 ksi; modulus 29,000 ksi. Strength reduction factors and source shear-method parameters remain editable and visible.
- Strength moments: N 169.44, P 143.56, B 337.61 kip-ft. Service I moments: N 148.19, P 103.46, B 293.70 kip-ft.
- Global / low-interval shear: 205.11 / 43.73 kip; torque: 33.83 kip-ft. These are independent worksheet envelopes. The interaction approach does not establish concurrency of actions.
- Service III and fatigue remain pending until applicability and the actual corresponding loads are established. Zero placeholders are not supplied analyses.

N denotes negative/top tension; P denotes the pile-positive region; B denotes the bearing-positive region. Global and low-interval shear checks remain separate. The converter defaults low shear to global if explicit interval stations are not supplied. Drawings do not invent interval extents or continuous force distributions.

## Preserved source method

The 324 definitions retain rectangular flexure, minimum reinforcement, tension strain, transformed cracked-section stresses/crack-control spacing, Service III and fatigue checks, sectional shear and spacing, torsion and combined steel, longitudinal tension, skin/shrinkage reinforcement and the mass-concrete trigger. Five definitions are helper functions. All equations/captions and their calculation units are included in the repository and notebook trace.

The two `Floor` expressions normalize to inches, use a unitless multiplier, then restore inches. Notebook analysis-source comparisons are bound to the loaded case rather than permanently tied to four piles / 48 in dimensions. These substitutions are explicit in `model.py`; a Blockpad export writes corresponding comparisons into the review copy.

## Additional notebook screens

The unit-aware evaluator rejects incompatible dimensions, unsupported bars, malformed quantities and invalid values. The fast scalar search uses the same parsed expressions in inch/kip/radian units, and every retained candidate is rechecked by the unit-aware evaluator. The JSON importer accepts data, not executable formulas.

The drawing uses computed row locations and bar diameters. A separate screen catches geometric overlap, bars outside the hoop interior and clear spacing below an editable trial threshold (initially 2 in). This threshold is a trial input, not a represented code minimum. Confirm governing bar-spacing, aggregate and construction requirements. Multiple-loop and U-leg topology are flagged as unresolved.

Search candidates can only be described as passing **available checks and the trial cage screen**. A candidate does not complete D-region/strut-and-tie applicability, pile heads, anchorage/development, splices, hooks, axial/biaxial force interaction, confinement, construction tolerances, fatigue applicability, independent force concurrency, or final project/code review.

The optional D/C margin filter has two explicit scopes. The all-check scope takes the maximum of all available numerical register ratios. The strength-only scope takes the maximum of flexural strength, shear strength/section bound, combined shear/torsion area and longitudinal steel ratios. It does not apply the tighter target to minimum reinforcement, tension strain, spacing, service/fatigue, skin or shrinkage ratios; those checks still retain their original pass requirements, and pending inputs stay pending. Ratios are filtered before display rounding. The scope and target are recorded with exported results.

The workbench defaults to the strength target and labels the combined maximum **All-check utilization** to distinguish a spacing/detailing ratio from strength D/C. Both remain visible. The Python filter API retains its existing default all-check scope. The across-cap spacing floor and the original worksheet trace are documented in `DC_RATIO_REVIEW.md`; this presentation correction does not change engineering equations or approve the underlying source assumptions.

The scalar engine and calculation port are tested against known mechanics and the saved C005 baseline. That validates the implementation, not the adequacy of every source engineering assumption.

## Section studies

The width/depth study has a dedicated fixed-force path that evaluates sectional screens without rewriting or clearing analysis-source geometry. Its retained cages can remain ineligible in the ordinary calculator because their section is stale. The ordinary steel search continues to reject stale geometry. The alternative analysis-matched mode evaluates only supplied, compatible section cases and never falls back to fixed forces.

Pile-layout changes are outside this geometry study. Width is screened using the adopted nominal pile-edge allowance and any larger entered project minimum. Single-outer-hoop geometry remains a search limitation. The material frontier and optional entered-rate costs describe only explored candidates and gross quantities. No self-weight/stiffness rerun, new detailing method or automated FB-MultiPier analysis is introduced. Full behavior and export provenance are documented in `SECTION_STUDY.md`.
