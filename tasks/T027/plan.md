# T027 — C001–C004, C006, C015 and C016 replaced by their notebook-generated journal editions

User request (21 October 2026): every journal calculation without a Colab notebook gets a notebook of the same build type
as the cap, pile and backwall notebooks (embedded package, calculation report with definition and citation cards, case /
checks / report / distilled Blockpad exports), is run with the journal's input values, and its distilled Blockpad edition
replaces the hand-authored journal module.

Packages (calc_common framework): `wind_superstructure` (C001), `fence_wind` (C002), `bridge_movement` (C003),
`superstructure_uplift` (C004), `pier_wall_fins` (C006), `mse_wall_exclusion` (C015), `bearing_design` (C016).
Each was imported from the journal module (`scripts/import_journal_calc.py`), its definitions evaluated independently
from the journal file and reproduced by the notebook engine to 1 part in 10⁹ (697 definitions; the eleven superseded
D-064/D-065 status strings of C016 moved into the hidden working notes), and its journal edition written by
`scripts/build_journal_calc_bpads.py --journal`.

- Base journal: the T026 revision (`feb1bb31…`).
- Permitted components: `report:C001WindLoadOnPedBridgeSuperstructure`, `report:FenceWind`, `report:BridgeMovement`,
  `report:SuperstructureUplift`, `report:PierWallFins`, `report:MSEWallExclusion`, `report:BearingDesign` (copied from
  `<package>/bpad/journal/<Report>.xml` after their verification records are checked), `report:PedBridge` (revision
  note) and `report:DecisionLog` (entry).
- Each replacement keeps the report name, the C-number title, every name other journal modules read (live references
  re-evaluated by the coherence gate), the native figures (canvases copied from the module), the design-basis prose with
  its anchor ids and the inbound links' section names. Equation notes, step navigation and the echoed hidden
  value displays are distilled out of the journal; they stay in the notebook reports.
- Conservative all-component dependency fallback. No prerequisite task. Native recalculation, appearance and
  engineering reviews not performed. No engineering value changes; FBMP not rerun. C015 keeps its two knife-edge
  SHORTFALL rows (journal model coordinates 0.0002 in short of 24 in), so its Status reads "⊗ There are FAILURES" as the
  journal's rows do.
