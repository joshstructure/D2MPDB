# Verification record — 21 October 2026 (ring moment basis, D-070)

The ring moment basis changed from the tributary-eccentricity convention `M = R (|e_n| + Δ_p)` to a pile-head compatibility moment: the rigid wall rotates on axial springs `k_v = A_p E_p / L_a` and rotational springs `k_θ = 4 E_p I_p / L_f` with the pile group displaced by the placement tolerance, every pile head carries `M_p = k_θ θ_w`, the ring rows share it equally, and the axial redistribution `ΔR` is added to each tributary reaction. Four schema 3 inputs were added (pipe E, free length to fixity, axial spring length, imposed rotation) with defaults from the pier pile case; schema 2 cases migrate with a visible notice. The superseded moment stays in the ledger as `M_s` for comparison. Decision D-070 in `project_current/decisions.md`; basis in [RING_WALL_STM.md](../RING_WALL_STM.md).

## Automated verification

`python -m unittest discover -s tests -p 'test_ring_wall*.py'` passes **31 tests** in 24.98 s locally (ipywidgets 8.1.9, Plotly 6.9.0). The Colab-pinned environment was not rerun for this revision. `tests/test_report_cards.py` (12 tests) passes with the rebuilt excerpt store, which now attributes LRFD 10.7.3.13.4 to `ring_wall/design.py` as well as the pile package.

New or changed coverage: an independent rigid-wall spring solution reproduces the wall rotation, ring moment, redistribution, design reaction, pressures, equivalent eccentricity and kern limit of the starting case; tolerance zero gives zero moment and redistribution with unchanged totals; one pile carries the whole `R_total Δ_p` in bending and, with one ring, reproduces the former tributary moment exactly; an imposed rotation of 0.002 rad fails contact at every ring and keeps the pending gate, trial labels and report warnings working; invalid inputs (negative or large imposed rotation, zero free length, a schema 2 label on a complete schema 3 case) are rejected; legacy and schema 2 cases migrate with the D-070 notice; the widget suite checks the new input card, the rings-panel note and the connection-figure contact title in both states. Equilibrium, randomized tributary, plate-integral, weld, detailing and export tests are unchanged.

The report now opens like the pile and backwall reports: a contents list, an **Overview** (objective, calculation flow, load path and what is outside the calculation), **Design basis and inputs** (code articles with citation cards, conventions, a case-input table with source/status and the check-status legend) and a **Result summary** with key results, ahead of the method index. It has **16 method sections, 111 equation explanations and 178 check-result rows** for the starting case (new family: pile-head compatibility moment and tolerance redistribution, with its own schematic; the kern limit joins the contact family). Every dropdown highlights its sketch element for the default, single-pile, imposed-rotation and widened-wall cases. Native Mathcad and Blockpad sheets carry **633 scalar values and 178 statuses** each, verified to 1e-9 for the default, widened-wall, imposed-rotation and single-pile cases.

Embedded package SHA-256:

`76a1480262aee166a2e5f878c0e7d4ef5166838eeb34d6db08a64a11daa97aa1`

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
