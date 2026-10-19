# T018 — Recalculate the current journal in Blockpad

The user requests opening the latest journal, rerunning its calculations and saving
the updated results to the source. The controlling file is
`journal/D2_I95_Project_Journal.bpad`, accepted revision T017, SHA-256
`d3aa9a62939cd82634196c97361ea85d2b8abf2d4fce1c72ab0b86a2510c9b50`.

Register all 40 existing report/spreadsheet/drawing modules for native result-cache
updates because a full recalculation can refresh every module. Watch all remaining
components and all supporting files using the conservative dependency fallback.
Preserve all formulas, numerical inputs, units, names, scope, source references,
embedded resources and document styles. Do not run external solvers or modify
notebooks, analysis models or engineering assumptions.

Open the isolated working copy with its References folder in installed Blockpad;
invoke full recalculation and save the native output. Inspect differences, stored
errors and representative refreshed results. If native serialization changes the
document wrapper or unassigned components, retain their original bytes and import
only explicitly registered modules, with an audit against the native save. Do not
rewrite native mathematical results with another evaluator.

The output contract retains every existing published name, meaning, unit, sign,
reference point, factor and case. Dependencies include shared ProjectInfo,
Materials and BridgeGeometry_2Beam, wind and movement reports, FBMP load tables,
cap/pile/backwall reports, and quantities. Native recalculation updates downstream
saved displays, not the external FB-MultiPier analysis. Existing analysis currency
and engineering gaps remain unresolved unless separately verified.

Acceptance: native full recalculation observed; exact native saved results carried
into the candidate; expression/input preservation audited; reference/resource and
scope checks pass; no new stored errors; check, assemble and promote using the
current workflow and evidence. Native visual review is limited to inspected views;
full appearance review and engineering acceptance are not asserted. Stop promotion
if recalculation reveals errors, unexplained expression/input changes, conflicting
source updates or missing references. Keep the recalculated copy and explain any
blocker rather than concealing native errors. Complete the required atlas refresh
gate and Git delivery after successful source promotion.
