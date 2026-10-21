# T028 — C017 Pier Wall, Annular Pile Rings added to the journal

User request (21 October 2026): run the Pier Wall Design notebook and update the calculation report and the Blockpad
calculation in the journal. The journal had no module for the welded annular-ring support concept (C006 covers the
fin-plate and hairpin concept of the same wall), so the ring calculation is added as its own calculation module.

- Base journal: the T027 revision (`0fc5dcfa…`).
- Added module: `report:PierWallRings` (title `C017 - Pier Wall, Annular Pile Rings`), copied from
  `ring_wall/bpad/journal/PierWallRings.xml`, the journal edition written by `scripts/build_ring_wall_bpad.py` from the
  starting case of the `ring_wall` package (the engine of `Pier_Wall_Design.ipynb`): every ledger value (673) and every
  check status (178) is a native definition evaluated independently by the Blockpad-syntax evaluator and compared with
  the package to 1 part in 10⁹; live project stamp (`Stamp_<Key> = ProjectInfo.<Key>`, gate against the journal's
  ProjectInfo strings); hidden working notes; visible-text rule of `scripts/bpad_sheet.py` (the notebook's PENDING status
  reads NO CONTACT in the edition). Ring moment basis D-070; pile stiffness defaults from PILE-PIER-CASE.
- Permitted components: `report:PierWallRings` (added), `report:PedBridge` (index: C017 link after C016, heading
  "Calculations C001 to C017", revision note), `report:DecisionLog` (entry).
- The addition path appends the module after the last component; T029 moves it after `report:BearingDesign` with a
  registered order (an order cannot be combined with an addition).
- No other module reads the new module; it reads only ProjectInfo. Conservative all-component dependency fallback
  (registered topology addition). No prerequisite task. Native recalculation, appearance and engineering reviews not
  performed. No engineering value of any existing module changes; FBMP not rerun. C006 is not superseded: which
  pier-wall support concept governs is undecided.
- Project record: `project_current/pier_wall/` (report, case, check register, ring forces; D-071), registered as
  PIER-WALL-TOOL, PIER-WALL-REPORT and PIER-WALL-CASE by `scripts/export_project_pier_wall_report.py`.
