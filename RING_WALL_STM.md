# Pier Wall Design

[Open in Colab](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Pier_Wall_Design.ipynb). The 19 October 2026 revision replaces the former strut-and-tie and cone-transfer study with minimum wall reinforcement, detailing and local annular-ring connection checks.

## Workflow and drawings

Choose **Runtime → Run all**, edit the amber inputs, and click **Recalc**. Input edits update live geometry, clear calculated results and disable new exports. Saved downloads remain available as the previous export. Green **Calc done** means the calculation matches the inputs; each check retains its own status.

Seven panels show dimensioned plan/elevation, a rotatable 3D cage with view buttons and hideable components, tributary loads, a ring/weld section and pressure distribution, wall reinforcement, a filterable check register with equation/value disclosures, and ring-spacing comparisons. The cage shows two orthogonal layers per broad face, end returns, end-face vertical bars, pipes and annular plates. It is a centerline schematic; final bends, splices, joints and anchorage routing require detailing.

Units are inches, kip and ksi, except density in kip/ft³. Ring elevations locate the **plate top above the wall bottom**. Effective pipe thickness is an explicit input. The connection has two continuous fillets, above and below every ring; a single-sided weld is not modeled.

## Basis and scope

The basis is [AASHTO LRFD BDS, 10th edition (2024)](https://store.transportation.org/Item/PublicationDetail?ID=5377), with visible resistance factors, required cover and a project spacing cap. Relevant provisions are 5.10.6 (minimum reinforcement), 5.10.2/5.10.3/5.10.8 (detailing and development), 5.6.5 (bearing), 6.13.3 (fillet welds) and 6.13.5 (adjacent steel shear). Review project requirements against the [FDOT Structures Manual](https://www.fdot.gov/Structures/StructuresManual/CurrentRelease).

Public supporting examples are [FHWA GEC 10, Chapter 12](https://www.fhwa.dot.gov/engineering/geotech/nhi18024.pdf) for bearing and [Caltrans Bridge Design Practice 6.2](https://dot.ca.gov/-/media/dot-media/programs/engineering/documents/bridge-design-practices/202210bdpchapter62steelplategirdersa11y.pdf) for AASHTO fillet welds. These examples do not establish this wall's load transfer.

Four open items remain in every result:

- Tributary sharing assumes all rings engage. Concrete transfer, including material below a ring, splitting/breakout and row compatibility need a separately substantiated load path.
- Wall checks cover minimum shrinkage/temperature steel and detailing, not wall flexure, shear, lateral/seismic resistance or strength load paths.
- Local plate, weld and adjacent-metal checks do not establish pipe-shell bending/ovalization, global pile interaction, segment splices, fatigue, corrosion or WPS/fabrication adequacy.
- Confirm geometry, exposure/cover, materials, joints and anchorage routing. Defaults remain the earlier study snapshot, not a current CAD import.

## Tributary concrete weight

Boundaries lie at midpoints between adjacent piles and ring rows, clipped at wall edges. For cell width `b`, height `h`, wall thickness `t` and density `γc`:

`V = b h t / 1728 ft³`; `W = γc V`; `R = γDC W`.

The gross concrete prism is retained conservatively without subtracting pipe or plate displacement. No additional gravity or steel self-weight is included. Ring pitch and count are independent; the top row takes the remaining height. The spacing study changes row count to fit each trial pitch and reports failures.

With cell centroid `xc` and nominal pile center `xp`, nominal eccentricity is `en = xc − xp`; local design eccentricity is `ed = |en| + radial pile tolerance`; `M = R ed`. The signed nominal eccentricity is retained separately for equilibrium: sum `R` recovers total weight; sum `R xp + R en` recovers its moment about the wall end. Placement tolerance is a local envelope, not a simultaneous global displaced-pile geometry.

## Minimum steel and detailing

For `b,h` in inches and `fy` in ksi, minimum area per face and direction is `As = clamp[1.3 b h / (2(b+h)fy), 0.11, 0.60] in²/ft`. Both gross sections `(t,L)` and `(t,H)` are evaluated; the larger requirement is applied each way on both broad faces, with matching end returns.

Automatic pitch rounds **down** to the entered increment from the area-derived spacing and spacing envelope. The conservative envelope is the minimum of `1.5t`, 18 in (12 in for thickness over 36 in), and the project cap, initially 12 in. It does not use ring spacing or former STM band depth. Manual pitch can fail.

Checks cover area, center spacing, clear spacing `max(1.5 in, 1.5db, 1.5 aggregate)`, entered cover, Class B laps, U straight-leg fit and bend diameter. Normalweight development uses `ldb = 0.17db [fy/(1.97 f′c^0.25)]²`, conservative horizontal top-cast factor 1.3, coating factor 1 or 1.5, top/coating product capped at 1.7, and 12-in minimum. Class B lap is `1.3ld`. No confinement or excess-steel reduction is taken. Unknown coating uses the epoxy factor. Supported bars are #4–#10, `f′c ≤ 15 ksi` and rebar `fy ≤ 75 ksi`.

Lap inputs are allowances, not an actual splice schedule. U-bend inside diameter is 6db through #8 and 8db for #9/#10; the fit envelope adds two bar diameters. Ring-end and face cover, inner-grid clearance, vertical cover and adjacent-pile ring clearance are also checked at tolerance.

## Annular bearing, plate and weld

Let `rp` = pipe radius, `ri` = ring inside radius, `ro` = ring outside radius, and `w` = weld leg. Bearing excludes the upper fillet footprint: `rb = max(ri,rp+w)`, `A = π(ro²−rb²)`, `I = π(ro⁴−rb⁴)/4`.

Elastic full-contact pressures are `qmax,min = R/A ± M ro/I`. Full compression requires `qmin ≥ 0`. Failure makes bearing, plate, weld and adjacent-metal checks for that ring **PENDING**. Displayed strength/sizing values are trial values. No reduced-contact factor or partial-contact solver is applied.

Bearing resistance is `φb 0.85 f′c`, initially `φb = 0.70`, with no supporting-area enhancement (`m = 1`). Peak pressure is conservatively applied over the whole radial cantilever strip:

`v = qmax (ro²−rb²)/(2rp)`; `m = qmax [(ro³−rb³)/(3rp) − (ro²−rb²)/2]`.

Plate elastic resistance per unit circumference is `φf Fy tp²/6`; shear yielding is `φvy 0.58 Fy tp`. Required thickness includes bending, shear and conservative weld-edge allowance `w + 1/16 in`. Recalculate after selecting thickness because weld demand and minimum size depend on it.

Each fillet takes half vertical shear plus the radial force from the moment couple: `Fw = sqrt[(v/2)² + (m/tp)²]`. The couple arm `tp` is conservative relative to weld-centroid separation. For radial gap `g = ri−rp`, effective throat is `(w−g)/√2`; resistance is `φw 0.60 FEXX throat`, initially `φw = 0.80`. No directional enhancement is used. WPS acceptance of the gap remains required; the deduction is an analysis allowance.

Minimum weld size follows the thicker-part table (1/8, 3/16, 1/4, 5/16 in at the 1/4, 1/2, 3/4-in boundaries), capped at the thinner part, with gap allowance added. The ring free-edge maximum and minimum continuous weld length are checked. Required leg is the greater of strength and minimum detailing. Ring/pipe shear rupture uses `φvu 0.58 Fu t`; pipe shear yielding also uses its effective thickness. These do not replace pipe-shell analysis.

## Starting case

The retained wall is 213 × 36 × 172.375 in with four 20-in piles at 60 in; five rows start 6 in above bottom at 36-in pitch. Rings are 23-in OD × 20.125-in ID × 3/4-in thick with two 5/16-in E70 fillets. Radial pile tolerance is 3 in.

- Service weight **114.737109375 kip**; factored **143.421386719 kip**.
- Maximum ring reaction **9.462890625 kip**.
- Minimum grid **#5 at 11 in each way each face**, providing 0.338182 in²/ft against 0.333614 in²/ft required.
- **12 failed checks:** end cover, grid clearance and full contact at ten end-pile rings. Their 70 local strength checks remain pending, with four scope items open.

Default failures have not been tuned away. Increasing ring diameter also affects end/grid clearance; changed pile layout or eccentricity needs coordinated geometry review.

## Exports and reproducibility

The HTML calculation report groups repeated checks into **15 method sections**. Each method states its physical purpose, shows the equations once, identifies its worked example, and includes a table with every applicable check/location. There are **96 equation explanations and 178 check-result rows** for the starting case. Each equation has its own **Numeric substitution and schematic** dropdown with an inline SVG mechanics sketch, current operands, units and numerical substitution. Symbols and fractions are rendered as native MathML directly from the evaluated ledger, rather than copied into a separate calculation implementation.

Use the method index to jump to a check, **Expand methods** to compare equations and result tables, or **Expand schematics** to open all explanations. **Print / save PDF** expands the report for printing and restores the previous expansion state afterward. The HTML remains usable offline. Geometry plots sit in a separate expandable section. Repeated tables preserve original statuses; a worked example with failed contact stays visibly marked as a trial, even when its numerical strength ratio is small. This report presentation does not change the calculation engine or the formula-based native worksheet format.

Optional exports: offline interactive HTML; case JSON; checks and ring-load CSV; formula-based Mathcad 15 `.xmcd` and Blockpad `.bpad`; source ZIP; full ZIP with results, spacing comparison, formula verification and SHA-256 manifest. Both native sheets contain editable expressions. Every numeric value and check status is independently evaluated in both expression dialects before export.

Native sheets use **labeled fixed scalar units**, not native dimensional quantities. They preserve exported topology, selected bar/coating and adopted pitch. Regenerate after changing those choices. Formula parity and XML checks are not native-application recalculation or engineering acceptance.

Schema-free legacy cases migrate shared geometry/materials, discard STM/cone inputs and add new weld/detail defaults with a visible notice. Nonzero added gravity is rejected to avoid silently dropping a load. New cases use complete schema version 2.

Code is in `ring_wall/`. Export helpers are vendored from the commit in `ring_wall/_native/PROVENANCE.json`, isolating portable exports from unrelated shared-helper changes. The builder embeds exact source bytes and verifies extraction.

Rebuild with `.venv\Scripts\python.exe scripts\build_ring_wall_notebook.py`; regenerate examples with `.venv\Scripts\python.exe scripts\build_ring_wall_examples.py`. Run `.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_ring_wall*.py' -v`. See [validation](ring_wall/VALIDATION.md) and the [example report](ring_wall/examples/ring_wall_report.html).
