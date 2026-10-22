# T038 — C018 Pier Cap Cheek Wall Design added to the journal

User direction (22 October 2026, relayed by the coordinating session): select the pier cap cheek wall calculation as a
current project source and add it to the project journal as calculation C018. The calculation (`pier_cheek_wall/`, D-080)
had no journal module; its journal edition is added as its own calculation module. Project decision D-081 registers the
same starting case as CHEEK-TOOL, CHEEK-REPORT and CHEEK-CASE (`scripts/export_project_pier_cheek_wall_report.py`).

- Base journal: the T037 revision (`ceeb8ebb…`).
- Added module: `report:PierCheekWalls` (title `C018 - Pier Cap Cheek Wall Design`), copied from
  `pier_cheek_wall/bpad/journal/PierCheekWalls.xml`, the journal edition written by `scripts/build_pier_cheek_wall.py
  --journal` from the starting case of the `pier_cheek_wall` package (the engine of `Pier_Cheek_Wall_Design.ipynb`,
  calc_common framework): every definition (183, of which 174 values are compared with the notebook to 1 part in 10⁹) is
  a native definition evaluated independently by the Blockpad-syntax evaluator; the five C001 wind inputs (V_III, V_V,
  V_SI, K_Z_gov as K_Z_III, G_fac as G_f) are live references to `C001WindLoadOnPedBridgeSuperstructure` passed through
  the coherence gate (journal value equal to the case value); live project stamp (`Stamp_<Key> = ProjectInfo.<Key>`);
  hidden working notes; visible-text rule of `scripts/bpad_sheet.py`. Wind per LRFD 3.8.1.2.1 and 3.8.1.2.3b with the C002
  substructure drag coefficient; the wall as a cantilever from the cap top with the D-059/D-061 CAD mat.
- Permitted components: `report:PierCheekWalls` (added), `report:PedBridge` (index: C018 link after C017, heading
  "Calculations C001 to C018", revision note), `report:DecisionLog` (entry).
- The addition path appends the module after the last component; T039 moves it after `report:PierWallRings` with a
  registered order (an order cannot be combined with an addition).
- No other module reads the new module; it reads C001 (five values) and ProjectInfo. Conservative all-component
  dependency fallback (registered topology addition). No prerequisite task. Native recalculation, appearance and
  engineering reviews not performed. No engineering value of any existing module changes; FBMP not rerun. C014 (end-bent
  backwall and cheek walls) is unchanged: the pier cheek walls are a different element.
- Project record: `project_current/pier_cheek_wall/` (report, case, check register; D-081), registered as CHEEK-TOOL,
  CHEEK-REPORT and CHEEK-CASE; receipt `project_current/coherence/evidence/2026-10-22-pier-cheek-wall-selection/`.
- Note: this file was overwritten at 11:01 local time by a sibling session's plan for a different task (the C006
  sequestering, now D-082 / T040) and rewritten from this task's own record; `order.json` and
  `workflow/registry/T038.json` carried the C018 objective throughout.
