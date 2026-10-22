# Verification record — 22 October 2026 (ring plate 1/2 in, D-078)

The annular ring plate of the starting case is **1/2 in** thick in place of 3/4 in, by user direction ("Lets update the design to 1/2 thick plate") after the question of the thinnest ring with no check above 0.95 of its limit. The answer, from sweeping `ring_t_in` through the engine with every other input held: the strength checks (plate bending, shear, fillets, base metal, bearing, contact) reach 0.95 of capacity only at about 0.17 in (row-5 plate bending); with the 5/16-in fillet held, the maximum fillet at the ring edge (leg ≤ plate thickness − 1/16 in, LRFD 6.13.3.4) governs, so 7/16 in is the thinnest standard plate (0.83) and 3/8 in sits at exactly 1.00. The 3/4-in plate was never strength-governed (plate bending 0.05 of capacity). No equation changed; the default, the BASIS scope text, the design-basis table rows and the notebook text changed. Decision D-078 in `project_current/decisions.md`; second project export of the day under label `10-22b` (`scripts/export_project_pier_wall_report.py --date 10-22b --decision D-078`, which now accepts a trailing letter for a same-day export). The CAD rings added under D-076 are 3/4 in thick until the model is reconciled.

## Automated verification

`python -m unittest discover -s tests -p 'test_ring_wall*.py'` passes **31 tests** locally (ipywidgets 8.1.9, Plotly 6.9.0); two assertions that pinned the 3/4-in plate's weld minimum were updated (at 1/2 in the thicker-part table gives 3/16 in, so a 1/4-in fillet is the trial leg with the gap allowance; the 3/4-in case is still asserted explicitly). `tests.test_report_cards` passes (12 tests). The Colab-pinned environment and native application recalculation were not rerun. The journal edition verified **673 values and 178 statuses** to 1e-9 (fragment `6cea494ef70b`).

Embedded package SHA-256:

`2e3c858380b1af9ef6e96fd3856ae6569e69882f8b607dff7c1e26eb4816f274`

## Starting-case results (22 October 2026, 1/2-in plate)

- Wall, piles, ring diameters, fillets, tolerance and stiffness inputs unchanged from the D-075 record below, so the service weight (**133.359 kip**), wall rotation (**1.547 × 10⁻⁵ rad**), pile-head moment (**26.983 kip-in**), ring moment (**5.397 kip-in**), largest equivalent eccentricity (**1.105 in** against the **5.187-in** kern), contact and bearing results are identical.
- Largest ring strength ratios: contact **0.213** (R1-P1), plate bending **0.112** (R5-P2; 0.050 at 3/4 in), ring shear 0.018, fillet **0.081** (0.057 at 3/4 in), ring base metal 0.032, pipe shear yielding 0.035, pipe base metal 0.034, bearing 0.060.
- Weld detailing: the minimum fillet of the thicker-part table is 3/16 in at 1/2 in (1/4 in with the 1/16-in gap allowance), so the 5/16-in fillet reads **0.80** of the minimum check and **0.71** of the ring-edge maximum (7/16 in); the largest trial leg is 1/4 in. The bottom ring cover rises to 5.1875 in (0.58 of the check).
- Grid unchanged: **#5 at 11 in each way each face**.
- **1 failed check** (RING-GRID, unchanged); no pending strength check; five scope items open.

# Verification record — 22 October 2026 (CAD wall geometry, D-075)

The starting case now follows the CAD pier wall: length 219 in (18 ft 3 in, 19.5 in from each wall end to the outer pile), thickness 36 in, height 194.8625 in (bottom 1 ft below terrain at EL 24.5264 ft, top at the cap bottom EL 40.76494 ft), and the pile free length to fixity 92.4 in measured from that bottom (110.7 in sand depth to fixity below the pile-case ground EL 26.05 less 18.3 in of wall below it). The former 213 × 36 × 172.375 in snapshot and the 127-in free length (taken from the pile cutoff) were not tied to any registered elevation. No equation changed; the defaults, the BASIS scope text and the design-basis table caption changed. Decision D-075 in `project_current/decisions.md`.

## Automated verification

`python -m unittest discover -s tests -p 'test_ring_wall*.py'` passes **31 tests** locally (ipywidgets 8.1.9, Plotly 6.9.0); the tests that pinned the former geometry (weight, grid, tributary bounds, nominal eccentricity, end distance, the end-cover failure) were updated, and the end-cover failure is now exercised on a 213-in case. The Colab-pinned environment and native application recalculation were not rerun.

## Starting-case results (22 October 2026)

- Service weight **133.359023438 kip**; factored **166.698779297 kip**.
- Wall rotation **1.547 × 10⁻⁵ rad**; pile-head moment **26.983 kip-in**; **5.397 kip-in** per ring.
- Largest equivalent eccentricity **1.105 in** (row 1, end piles) against the **5.187-in** kern; all twenty rings in full contact.
- Grid unchanged: **#5 at 11 in each way each face** (0.338182 in²/ft against 0.334941 in²/ft required).
- **1 failed check** (RING-GRID); RING-END passes with 5.0 in of end cover at tolerance against 3.0 in required; no pending strength check; five scope items open.

# Verification record — 21 October 2026 (ring moment basis, D-070)

The ring moment basis changed from the tributary-eccentricity convention `M = R (|e_n| + Δ_p)` to a pile-head compatibility moment: the rigid wall rotates on axial springs `k_v = A_p E_p / L_a` and rotational springs `k_θ = 4 E_p I_p / L_f` with the pile group displaced by the placement tolerance, every pile head carries `M_p = k_θ θ_w`, the ring rows share it equally, and the axial redistribution `ΔR` is added to each tributary reaction. Four schema 3 inputs were added (pipe E, free length to fixity, axial spring length, imposed rotation) with defaults from the pier pile case; schema 2 cases migrate with a visible notice. The superseded moment stays in the ledger as `M_s` for comparison. Decision D-070 in `project_current/decisions.md`; basis in [RING_WALL_STM.md](../RING_WALL_STM.md).

## Automated verification

`python -m unittest discover -s tests -p 'test_ring_wall*.py'` passes **31 tests** in 24.98 s locally (ipywidgets 8.1.9, Plotly 6.9.0). The Colab-pinned environment was not rerun for this revision. `tests/test_report_cards.py` (12 tests) passes with the rebuilt excerpt store, which now attributes LRFD 10.7.3.13.4 to `ring_wall/design.py` as well as the pile package.

New or changed coverage: an independent rigid-wall spring solution reproduces the wall rotation, ring moment, redistribution, design reaction, pressures, equivalent eccentricity and kern limit of the starting case; tolerance zero gives zero moment and redistribution with unchanged totals; one pile carries the whole `R_total Δ_p` in bending and, with one ring, reproduces the former tributary moment exactly; an imposed rotation of 0.002 rad fails contact at every ring and keeps the pending gate, trial labels and report warnings working; invalid inputs (negative or large imposed rotation, zero free length, a schema 2 label on a complete schema 3 case) are rejected; legacy and schema 2 cases migrate with the D-070 notice; the widget suite checks the new input card, the rings-panel note and the connection-figure contact title in both states. Equilibrium, randomized tributary, plate-integral, weld, detailing and export tests are unchanged.

The report now opens like the pile and backwall reports: a contents list, an **Overview** (objective, calculation flow, load path and what is outside the calculation), **Design basis and inputs** (code articles with citation cards, conventions, a case-input table with source/status and the check-status legend), a **Result summary** with key results, and the **Geometry and reinforcement drawings** (plan/elevation, 3D cage, ring connection, reaction heatmap, open by default), all ahead of the method index. It has **16 method sections, 113 equation explanations and 178 check-result rows** for the starting case (new family: pile-head compatibility moment and tolerance redistribution, with its own schematic; the kern limit joins the contact family; the weld family gains the nearest-sixteenth count and the trial leg rounded up to the next 1/16 in). Every dropdown highlights its sketch element for the default, single-pile, imposed-rotation and widened-wall cases. Native Mathcad and Blockpad sheets carry **673 scalar values and 178 statuses** each, verified to 1e-9 for the default, widened-wall, imposed-rotation and single-pile cases; the sixteenth rounding uses the two-argument `round` both evaluators and native applications provide.

Weld sizes (provided leg, minimum table values, gap allowances, maximum at the ring edge, throat and the trial leg) display as fractions in sixteenths of an inch in the workbench tables and summary cards, the connection drawing, the report equations, operand tables, check rows and sizes table. The provided leg is a dropdown of sixteenths from 1/8 to 1 in; a case whose leg is not a whole number of sixteenths is rejected with a clear message. Tests check the rounding (next sixteenth at or above the raw leg, never a full sixteenth above), the exact 3/8-in result for a 1/4-in leg, the rejection of a 0.3-in leg and the dropdown options.

Embedded package SHA-256:

`e58b4fcb64c8d8f327a7b0f4263e66c1790ea3037bb209c7ff5091512a65abf9`

## Starting-case results (21 October 2026)

- Service weight **114.737109375 kip**; factored **143.42138671875 kip**; force and nominal moment residuals zero.
- Wall rotation **1.414 × 10⁻⁵ rad**; pile-head moment **17.945 kip-in**; **3.589 kip-in** per ring (superseded end-pile value 42.504 kip-in in row 1).
- Largest tolerance redistribution **0.420 kip** (top row, end piles); largest equivalent eccentricity **0.779 in** against the **5.187-in** kern; all twenty rings in full contact.
- Grid unchanged: **#5 at 11 in each way each face**.
- **2 failed checks** (RING-END, RING-GRID); no pending strength check; five scope items open.

The compatibility and superseded schematics, the report front matter and the compatibility method section were reviewed as headless browser screenshots; the remaining sections, the Colab runtime and native application recalculation were not exercised for this revision.

# Verification record — 19 October 2026

The former ring-wall STM engine has been replaced by minimum wall steel/detailing and local annular-ring bearing, plate and double-fillet weld checks. Other notebook engines were not changed.

## Automated verification

`python -m unittest discover -s tests -p 'test_ring_wall*.py' -q` passes **28 tests** in both environments:

- Local ipywidgets **8.1.9**, Plotly **6.9.0**: 28 tests, 26.041 s.
- Colab-pinned ipywidgets **7.7.1**, Plotly **5.24.1**: 28 tests, 26.781 s.

After renaming the notebook to `Pier_Wall_Design.ipynb` and its visible title to **Pier Wall Design**, the same 28 tests passed locally in 19.993 s. The builder, Colab links and portable-notebook test use the new filename; export source records were regenerated. The pinned environment was not rerun for this name-only change.

Coverage includes midpoint tributaries and global force/moment equilibrium, 30 randomized geometries, single-pile and single-row boundaries, load-factor/density scaling, minimum steel independent of ring pitch, detailing failures, minimum weld table boundaries, invalid input rejection, and legacy-case migration without silently removing added gravity.

Independent numerical radial-strip integration checks plate shear and moment; weld force is checked against its separate force/couple calculation. Tests check bearing area, eccentricity/tolerance effects, failed-contact gating, a geometry with all numeric checks passing while scope items stay open, and report disclosures with escaped user text.

Both notebook code cells execute in order from the embedded source, with no startup exports. Exact embedded bytes, package checksum, case retention on rerun and saved-download preservation are checked. Widget tests navigate every panel, reuse figure objects after topology edits, clear stale results, block stale exports, exercise filters and atomically reject invalid saved cases.

The full export ZIP is checked against its SHA-256 manifest. HTML includes interactive Plotly code inline and has no external script dependency. Mathcad and Blockpad expressions are independently evaluated against every calculation value and status for default, edited, full-contact and single-pile cases. XML, expression order and worksheet width checks also pass. The default has **572 scalar values and 178 check statuses** in each native sheet. Status tolerances are shared with the Python checks.

Embedded package SHA-256:

`b7e2888b4e5e86d88a5fb72ee0ee1c8c40ecc86efed699734712264f3d54169a`

The rebuilt HTML exporter has **15 method sections, 96 equation explanations and 178 check-result rows**. Tests verify that every check appears exactly once with its original status for default, single-ring and full-contact cases; new unassigned check types fail closed. Each equation has native MathML, a schematic and current operands. Both conditional branches and mathematical grouping are preserved; rendered expressions come directly from the current ledger. Reports retain pending/trial warnings and escape case/check text without mutating results.

## Browser and review limits

Local JupyterLab browser review rendered the workbench and clicked all seven result panels. The 3D cage, annular-ring section, pressure plot, tables and navigation rendered. A typed radial-tolerance edit cleared calculated results; manual Recalc was exercised. Standalone report, cage view buttons and ring connection drawing were also visually reviewed.

The rebuilt report was reviewed in the browser: method-index navigation, individual equation dropdowns, method expansion, all 96 schematic expansions, collapse controls and all 178 result rows were checked. Weld, radial plate and contact-pressure equations/sketches were visually inspected. Expanded SVG labels stayed within their drawing bounds, with no browser errors. Printing preparation is included; a native print/PDF save was not exercised.

The Google-hosted Colab runtime and downloads were not directly exercised. Its pinned Python widget/chart versions passed the same automated suite. Native Mathcad/Blockpad application recalculation and native page appearance were not performed. Formula parity, XML parsing and cached values do not establish native execution or engineering acceptance. Native sheets use fixed scalar units with labels and the exported topology, as described in the guide.

## Starting-case results

- Service concrete self-weight: **114.737109375 kip**.
- Factored concrete self-weight: **143.42138671875 kip**.
- Maximum ring reaction: **9.462890625 kip**.
- Global force and nominal moment residuals are zero to displayed precision.
- Selected grid: **#5 at 11 in each way each face**, providing **0.338181818 in²/ft** against **0.333614458 in²/ft** required.
- **12 failed checks:** RING-END, RING-GRID and ten end-pile full-contact checks. Their 70 local strength checks are pending. Four scope items remain open.

Defaults remain the earlier study geometry. Minimum steel and local connections do not establish wall strength, concrete splitting/breakout, row engagement or local pipe-shell behavior. See [the full basis](../RING_WALL_STM.md) and regenerated [example report](examples/ring_wall_report.html).

Reproduce with `scripts/build_ring_wall_notebook.py` and `scripts/build_ring_wall_examples.py`. Exact source/case/output hashes are in the example export manifest and worksheet verification JSON. Vendored worksheet helper provenance is recorded in `_native/PROVENANCE.json`.
