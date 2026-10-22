# T040 — C006 Pier Wall, Hairpins and Fin Plates withdrawn from the journal; calculation numbers permanent (D-082)

**Objective.** The user directed on 22 October 2026: "Lets sequester the pier wall fin and hairpin calc from the project.
Dont delete it but lets make it an unused unreferenced calc unless we need to revive it later", and "Lets actually give
each calc a unique number so we dont have to keep renumbering them". Project decision D-082: the fin-plate and hairpin
hanger calculation (journal module `PierWallFins`, title `C006 - Pier Wall, Hairpins and Fin Plates`; package
`pier_wall_fins/`, notebook `Pier_Wall_Fins.ipynb`) is withdrawn from the project and kept intact under
`sequestered/` for revival. The project carries the welded annular-ring concept (C017, the CAD model's concept under
D-076 and D-079). Calculation numbers are permanent identifiers from now on: C006 retires like C005, nothing is
renumbered, and a new calculation takes the next unused number (C018, the pier cap cheek walls of T038, is the last
in use).

- delete: `report:PierWallFins` (no other module reads a `PierWallFins.` name; the only native link into it is the
  index entry).
- `report:PedBridge`: the C006 index paragraph removed; the "Calculations C001 to C018" heading stays (numbers are
  permanent); one revision paragraph before the newest revision note.
- `report:PierWallRings` (C017): replaced by the rebuilt journal edition `ring_wall/bpad/journal/PierWallRings.xml`
  from the unchanged D-078 starting case (same definitions, values, caches and canvases; only the hidden working
  notes and the "Outside this calculation" sentence no longer present C006 as the undecided alternative).
- `report:DecisionLog`: one section appended.

**Exclusions.** Every other module. No formula, cache, unit, value, figure or resource changes. The stylerules
`C006 Heading1..3` are global styles and stay (resources and styles are retained by the deletion path). The gravity
sheet row 42, C004 and C002 are unchanged. C018 (T038, T039) is unchanged. The CAD model is unchanged.

**Base journal.** The current journal at `prepare` time (the T039 revision; hash recorded in `order.json`).

**Read dependencies.** All-component fallback (no reviewed declaration).

**Acceptance.** `check` passes (no remaining native link into the deleted module; no published name lost; no new
stored error); the C017 fragment matches its verification record (673 values and 178 statuses verified to 1e-9
against the package) and keeps every definition and cache of the base module; the visible-text rule holds.

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 16 October).
Bounded file-integrity verification only; no engineering value changed.
