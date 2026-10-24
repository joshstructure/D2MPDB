# T042 — Inputs placed in their own sections in C001–C004, C015 and C016 (D-087)

**Objective.** The user asked on 23 October 2026 why section 1.2 of C001 had nothing under it. The calculation
packages (`calc_common`) matched an input's group against the section title exactly, but the groups are written as
the bare heading ("Wind speed and exposure") and the titles carry their number ("1.2 Wind speed and exposure"), so
every input was placed beside its first use and section 1.2 stayed empty. Inputs no equation reads (values behind
tables, published names) had no home at all in the HTML report. The user directed the fix (commits 3809637 and
dc19137): groups now match titles without the number, and `sections.json` places the unread inputs with
`extra_inputs`; project decision D-087. The journal follows:

- `report:C001WindLoadOnPedBridgeSuperstructure`, `report:FenceWind`, `report:BridgeMovement`,
  `report:SuperstructureUplift`, `report:MSEWallExclusion`, `report:BearingDesign`: replaced by the rebuilt journal
  editions `<package>/bpad/journal/<Report>.xml`. Only the position of input definitions changes: every formula and
  cached value is the same multiset as in the base module.
- `report:PedBridge`: one revision paragraph before the newest revision note.
- `report:DecisionLog`: one section appended.

**Exclusions.** Every other module, including C006 (sequestered), C017 and C018; no values, formulas, checks, cases or
external analyses change.

**Base journal.** The current journal at `prepare` time (the T041 revision; hash recorded in `order.json`).

**Read dependencies.** All-component fallback (no reviewed declaration).

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 16 October).
