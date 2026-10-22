# Pier Wall Design

[Open in Colab](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Pier_Wall_Design.ipynb). The 19 October 2026 revision replaces the former strut-and-tie and cone-transfer study with minimum wall reinforcement, detailing and local annular-ring connection checks. The 21 October 2026 revision (decision D-070) changes the ring moment basis: tributaries assign vertical force only, the placement tolerance redistributes the pile-group reactions, and the ring moment follows the pile-head rotational stiffness against the rigid-wall rotation. The superseded basis is kept in the ledger for comparison. The 22 October 2026 revision (decision D-075) reconciles the starting wall to the CAD pier wall: 219 × 36 in, bottom 1 ft below terrain at EL 24.5264 ft and top at the cap bottom (194.8625 in high), with the pile free length to fixity measured from that bottom (92.4 in).

## Workflow and drawings

Choose **Runtime → Run all**, edit the amber inputs, and click **Recalc**. Input edits update live geometry, clear calculated results and disable new exports. Saved downloads remain available as the previous export. Green **Calc done** means the calculation matches the inputs; each check retains its own status.

Seven panels show dimensioned plan/elevation, a rotatable 3D cage with view buttons and hideable components, tributary loads, a ring/weld section and pressure distribution, wall reinforcement, a filterable check register with equation/value disclosures, and ring-spacing comparisons. The cage shows two orthogonal layers per broad face, end returns, end-face vertical bars, pipes and annular plates. It is a centerline schematic; final bends, splices, joints and anchorage routing require detailing.

Units are inches, kip and ksi, except density in kip/ft³ and rotations in radians. Ring elevations locate the **plate top above the wall bottom**. Effective pipe thickness is an explicit input and also sets the pipe section used for the pile stiffness. The connection has two continuous fillets, above and below every ring; a single-sided weld is not modeled.

## Basis and scope

The basis is [AASHTO LRFD BDS, 10th edition (2024)](https://store.transportation.org/Item/PublicationDetail?ID=5377), with visible resistance factors, required cover and a project spacing cap. Relevant provisions are 5.10.6 (minimum reinforcement), 5.10.2/5.10.3/5.10.8 (detailing and development), 5.6.5 (bearing), 6.13.3 (fillet welds) and 6.13.5 (adjacent steel shear). Review project requirements against the [FDOT Structures Manual](https://www.fdot.gov/Structures/StructuresManual/CurrentRelease).

Public supporting examples are [FHWA GEC 10, Chapter 12](https://www.fhwa.dot.gov/engineering/geotech/nhi18024.pdf) for bearing and [Caltrans Bridge Design Practice 6.2](https://dot.ca.gov/-/media/dot-media/programs/engineering/documents/bridge-design-practices/202210bdpchapter62steelplategirdersa11y.pdf) for AASHTO fillet welds. These examples do not establish this wall's load transfer.

Five open items remain in every result:

- Tributary sharing assigns vertical force, and the ring rows share the pile-head moment equally; all rings are assumed to engage. Concrete transfer, including material below a ring, splitting/breakout and row compatibility need a separately substantiated load path.
- Ring moments follow pile-head rotational stiffness against the rigid-wall rotation (D-070). The free length to fixity and the axial spring length are entered values whose defaults come from the pier pile case (sand depth to fixity, LRFD C10.7.3.13.4; tip elevation pending). Lateral, thermal, unsymmetric and construction-stage rotations enter only through the imposed rotation input.
- Wall checks cover minimum shrinkage/temperature steel and detailing, not wall flexure, shear, lateral/seismic resistance or strength load paths.
- Local plate, weld and adjacent-metal checks do not establish pipe-shell bending/ovalization, global pile interaction, segment splices, fatigue, corrosion or WPS/fabrication adequacy.
- Confirm exposure/cover, materials, joints and anchorage routing. The starting dimensions follow the CAD pier wall (D-075); the geometry notebook does not yet own the pier wall, so a notebook-owned wall remains a reconciliation item.

## Tributary concrete weight

Boundaries lie at midpoints between adjacent piles and ring rows, clipped at wall edges. For cell width `b`, height `h`, wall thickness `t` and density `γc`:

`V = b h t / 1728 ft³`; `W = γc V`; `R = γDC W`.

The gross concrete prism is retained conservatively without subtracting pipe or plate displacement. No additional gravity or steel self-weight is included. Ring pitch and count are independent; the top row takes the remaining height. The spacing study changes row count to fit each trial pitch and reports failures.

With cell centroid `xc` and nominal pile center `xp`, the nominal eccentricity `en = xc − xp` is retained for equilibrium only: sum `R` recovers total weight; sum `R xp + R en` recovers its moment about the wall end. The continuous wall carries that centroid offset internally; it does not load the ring. The former local moment `Ms = R (|en| + Δp)` is still evaluated and tabulated as the **superseded basis** for comparison (D-070).

## Pile-head compatibility moment and tolerance redistribution

The wall is treated as a rigid body on `np` equally spaced pile heads, each with an axial spring `kv = Ap Ep / La` and a rotational spring `kθ = 4 Ep Ip / Lf`, where `Ap` and `Ip` are the effective pipe section, `La` is the entered axial spring length and `Lf` the entered length from the wall bottom to the equivalent point of fixity. The `4EI/L` form (head translation restrained) bounds the fixed-base cantilever family.

The radial placement tolerance displaces the pile group by `Δp` relative to the wall centroid. Moment equilibrium of the rigid wall gives the rotation

`θΔ = Rtotal Δp / (kv Sx + np kθ)`, with `Sx = sp² np (np² − 1) / 12`, the sum of squared pile offsets from the group centroid `x̄`.

The total wall rotation `θw = θΔ + θimp` adds an imposed rotation input (zero by default) for actions outside this calculation. Every pile head then carries `Mp = kθ θw`, shared equally by the ring rows: `M = Mp / nr`. The axial redistribution `ΔR = η kv θw |xp − x̄|`, with `η = h / H` the row share, is added to each ring's tributary reaction with the sign that increases it: `Rd = R + ΔR`. For one pile `Sx = 0`, so the pile carries the whole `Rtotal Δp` in bending and `M` reduces to the former tributary moment.

The equivalent eccentricity `eeq = M / Rd` is compared with the annulus kern `ek = I / (A ro)`; full contact needs `eeq ≤ ek`.

## Minimum steel and detailing

For `b,h` in inches and `fy` in ksi, minimum area per face and direction is `As = clamp[1.3 b h / (2(b+h)fy), 0.11, 0.60] in²/ft`. Both gross sections `(t,L)` and `(t,H)` are evaluated; the larger requirement is applied each way on both broad faces, with matching end returns.

Automatic pitch rounds **down** to the entered increment from the area-derived spacing and spacing envelope. The conservative envelope is the minimum of `1.5t`, 18 in (12 in for thickness over 36 in), and the project cap, initially 12 in. It does not use ring spacing or former STM band depth. Manual pitch can fail.

Checks cover area, center spacing, clear spacing `max(1.5 in, 1.5db, 1.5 aggregate)`, entered cover, Class B laps, U straight-leg fit and bend diameter. Normalweight development uses `ldb = 0.17db [fy/(1.97 f′c^0.25)]²`, conservative horizontal top-cast factor 1.3, coating factor 1 or 1.5, top/coating product capped at 1.7, and 12-in minimum. Class B lap is `1.3ld`. No confinement or excess-steel reduction is taken. Unknown coating uses the epoxy factor. Supported bars are #4–#10, `f′c ≤ 15 ksi` and rebar `fy ≤ 75 ksi`.

Lap inputs are allowances, not an actual splice schedule. U-bend inside diameter is 6db through #8 and 8db for #9/#10; the fit envelope adds two bar diameters. Ring-end and face cover, inner-grid clearance, vertical cover and adjacent-pile ring clearance are also checked at tolerance.

## Annular bearing, plate and weld

Let `rp` = pipe radius, `ri` = ring inside radius, `ro` = ring outside radius, and `w` = weld leg. Bearing excludes the upper fillet footprint: `rb = max(ri,rp+w)`, `A = π(ro²−rb²)`, `I = π(ro⁴−rb⁴)/4`.

Elastic full-contact pressures are `qmax,min = Rd/A ± M ro/I`. Full compression requires `qmin ≥ 0`. Failure makes bearing, plate, weld and adjacent-metal checks for that ring **PENDING**. Displayed strength/sizing values are trial values. No reduced-contact factor or partial-contact solver is applied.

Bearing resistance is `φb 0.85 f′c`, initially `φb = 0.70`, with no supporting-area enhancement (`m = 1`). Peak pressure is conservatively applied over the whole radial cantilever strip:

`v = qmax (ro²−rb²)/(2rp)`; `m = qmax [(ro³−rb³)/(3rp) − (ro²−rb²)/2]`.

Plate elastic resistance per unit circumference is `φf Fy tp²/6`; shear yielding is `φvy 0.58 Fy tp`. Required thickness includes bending, shear and conservative weld-edge allowance `w + 1/16 in`. Recalculate after selecting thickness because weld demand and minimum size depend on it.

Each fillet takes half vertical shear plus the radial force from the moment couple: `Fw = sqrt[(v/2)² + (m/tp)²]`. The couple arm `tp` is conservative relative to weld-centroid separation. For radial gap `g = ri−rp`, effective throat is `(w−g)/√2`; resistance is `φw 0.60 FEXX throat`, initially `φw = 0.80`. No directional enhancement is used. WPS acceptance of the gap remains required; the deduction is an analysis allowance.

Minimum weld size follows the thicker-part table (1/8, 3/16, 1/4, 5/16 in at the 1/4, 1/2, 3/4-in boundaries), capped at the thinner part, with gap allowance added. The ring free-edge maximum and minimum continuous weld length are checked. Required leg is the greater of strength and minimum detailing, rounded up to the next sixteenth of an inch: `n16 = round(16 wreq)`, `w16 = (n16 if n16 ≥ 16 wreq else n16 + 1) / 16`. The provided leg is entered in sixteenths (1/8 to 1 in) and weld sizes display as fractions throughout the workbench, report and native sheets. Ring/pipe shear rupture uses `φvu 0.58 Fu t`; pipe shear yielding also uses its effective thickness. These do not replace pipe-shell analysis.

## Starting case

The wall is the CAD pier wall (D-075): 219 × 36 × 194.8625 in (bottom 1 ft below terrain at EL 24.5264 ft, top at the cap bottom EL 40.76494 ft) with four 20-in piles at 60 in, 19.5 in from each wall end; five rows start 6 in above bottom at 36-in pitch. Rings are 23-in OD × 20.125-in ID × 3/4-in thick with two 5/16-in E70 fillets. Radial pile tolerance is 3 in. Pile stiffness inputs: E 29,000 ksi, 92.4 in from the wall bottom to fixity (110.7 in sand depth to fixity below the pile-case ground EL 26.05 less the 18.3 in of wall below that ground), 600-in axial spring length (tip elevation pending), no imposed rotation.

- Service weight **133.359023438 kip**; factored **166.698779297 kip** (gross prism; the pile bores are not deducted).
- Wall rotation **1.547 × 10⁻⁵ rad**; pile-head moment **26.98 kip-in**; ring moment **5.397 kip-in** per ring.
- Largest equivalent eccentricity **1.105 in** (row 1, end piles) against the **5.187-in** kern: all twenty rings keep full contact.
- Minimum grid **#5 at 11 in each way each face**, providing 0.338182 in²/ft against 0.334941 in²/ft required.
- **1 failed check:** grid clearance (the inner face-grid layer meets the 23-in ring). The ring end cover passes with the 19.5-in end distance (it failed at 2 in with the former 213-in wall). No local strength check is pending; five scope items remain open.

Default failures have not been tuned away. Increasing ring diameter also affects end/grid clearance; a changed pile layout needs coordinated geometry review. Entering an imposed rotation of 0.002 rad reproduces the former full-contact failures across all rings, which shows the contact gate still operates.

Until 22 October 2026 the starting wall was the earlier study snapshot, 213 × 36 × 172.375 in (16.5 in from the wall end to the outer pile), with the free length 127 in taken from the pile cutoff rather than the wall bottom; those dimensions were not tied to any registered elevation. The CAD wall is 6 in longer and 22.5 in taller, so the service weight rises from 114.737 to 133.359 kip; the gravity sheet of the journal, C006 and this calculation now agree with the CAD model and the drawings.

## Superseded basis (D-070)

Until 21 October 2026 each ring carried `M = R (|en| + Δp)`: the tributary cell's own weight at the offset of its centroid from the nominal pile center plus the radial tolerance. That convention failed full contact at the ten end-pile rings of the 213-in wall of the time (equivalent eccentricity 9.75 in against the 5.19-in kern) and made their 70 local strength checks pending. It was replaced because the wall is a continuous stiff body that carries the centroid offset internally, while the flexible pile head follows the wall, so the ring sees only the compatibility moment. Plate ductility does not relieve the former statics demand; the basis, not the ring, was the issue. The superseded moment stays in the ledger, the report table and the native sheets as `Ms` for comparison, and the decision is recorded in `project_current/decisions.md`.

## Exports and reproducibility

The HTML calculation report groups repeated checks into **16 method sections**. Each method states its physical purpose, shows the equations once, identifies its worked example, and includes a table with every applicable check/location. There are **113 equation explanations and 178 check-result rows** for the starting case. Each equation has its own **Numeric substitution and schematic** dropdown with an inline SVG mechanics sketch, current operands, units and numerical substitution. Symbols and fractions are rendered as native MathML directly from the evaluated ledger, rather than copied into a separate calculation implementation.

Use the method index to jump to a check, **Expand methods** to compare equations and result tables, or **Expand schematics** to open all explanations. **Print / save PDF** expands the report for printing and restores the previous expansion state afterward. The HTML remains usable offline. The report opens with an overview, the design basis and inputs, a result summary and the geometry and reinforcement drawings (open by default), followed by the method families. Repeated tables preserve original statuses; a worked example with failed contact stays visibly marked as a trial, even when its numerical strength ratio is small. This report presentation does not change the calculation engine or the formula-based native worksheet format.

Optional exports: offline interactive HTML; case JSON; checks and ring-load CSV; formula-based Mathcad 15 `.xmcd` and Blockpad `.bpad`; source ZIP; full ZIP with results, spacing comparison, formula verification and SHA-256 manifest. Both native sheets contain editable expressions. Every numeric value and check status is independently evaluated in both expression dialects before export.

Native sheets use **labeled fixed scalar units**, not native dimensional quantities. They preserve exported topology, selected bar/coating and adopted pitch. Regenerate after changing those choices. Formula parity and XML checks are not native-application recalculation or engineering acceptance.

Schema-free legacy cases migrate shared geometry/materials, discard STM/cone inputs and add new weld/detail defaults with a visible notice. Nonzero added gravity is rejected to avoid silently dropping a load. Schema 2 cases (19 October revision) gain the four pile stiffness inputs at their defaults with a D-070 notice. New cases use complete schema version 3.

Code is in `ring_wall/`. Export helpers are vendored from the commit in `ring_wall/_native/PROVENANCE.json`, isolating portable exports from unrelated shared-helper changes. The builder embeds exact source bytes and verifies extraction.

## Project record and journal edition

The run of the starting case is a selected project source (decision D-071 on 21 October 2026; the 22 October 2026 rerun on the CAD wall under D-075 replaced it): `project_current/pier_wall/` holds the report, the dated and selected case, the check register and the ring forces, registered as PIER-WALL-TOOL, PIER-WALL-REPORT and PIER-WALL-CASE by `scripts/export_project_pier_wall_report.py` (`--date`, `--decision`, `--register [--replace]`, `--check`). The journal edition is calculation **C017 - Pier Wall, Annular Pile Rings** (report `PierWallRings`), written by `scripts/build_ring_wall_bpad.py` to `ring_wall/bpad/journal/` with every ledger value and check status as a native definition, the live project stamp and hidden working notes, verified against the package to 1e-9 (`--check` compares the committed fragment with a fresh build); tasks T028 (addition), T029 (order after C016), T030 (caption corrections) and T034 (CAD wall geometry) put it in the journal. The notebook's lost-contact status PENDING reads NO CONTACT in the journal edition. C006 (fin plates and hairpins) remains in the journal: the choice of pier-wall support concept is undecided.

Rebuild with `.venv\Scripts\python.exe scripts\build_ring_wall_notebook.py`; regenerate examples with `.venv\Scripts\python.exe scripts\build_ring_wall_examples.py`; rebuild the journal edition with `.venv\Scripts\python.exe scripts\build_ring_wall_bpad.py` (a changed fragment needs a new journal task). Run `.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_ring_wall*.py' -v`. See [validation](ring_wall/VALIDATION.md) and the [example report](ring_wall/examples/ring_wall_report.html).
