# Verification record — 19 October 2026

The former ring-wall STM engine has been replaced by minimum wall steel/detailing and local annular-ring bearing, plate and double-fillet weld checks. Other notebook engines were not changed.

## Automated verification

`python -m unittest discover -s tests -p 'test_ring_wall*.py' -q` passes **28 tests** in both environments:

- Local ipywidgets **8.1.9**, Plotly **6.9.0**: 28 tests, 26.041 s.
- Colab-pinned ipywidgets **7.7.1**, Plotly **5.24.1**: 28 tests, 26.781 s.

Coverage includes midpoint tributaries and global force/moment equilibrium, 30 randomized geometries, single-pile and single-row boundaries, load-factor/density scaling, minimum steel independent of ring pitch, detailing failures, minimum weld table boundaries, invalid input rejection, and legacy-case migration without silently removing added gravity.

Independent numerical radial-strip integration checks plate shear and moment; weld force is checked against its separate force/couple calculation. Tests check bearing area, eccentricity/tolerance effects, failed-contact gating, a geometry with all numeric checks passing while scope items stay open, and report disclosures with escaped user text.

Both notebook code cells execute in order from the embedded source, with no startup exports. Exact embedded bytes, package checksum, case retention on rerun and saved-download preservation are checked. Widget tests navigate every panel, reuse figure objects after topology edits, clear stale results, block stale exports, exercise filters and atomically reject invalid saved cases.

The full export ZIP is checked against its SHA-256 manifest. HTML includes interactive Plotly code inline and has no external script dependency. Mathcad and Blockpad expressions are independently evaluated against every calculation value and status for default, edited, full-contact and single-pile cases. XML, expression order and worksheet width checks also pass. The default has **572 scalar values and 178 check statuses** in each native sheet. Status tolerances are shared with the Python checks.

Embedded package SHA-256:

`65ef112544a6daed3d78013e216542a834f4961cad01c015407b88b71be95b45`

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
