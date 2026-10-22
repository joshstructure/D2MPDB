# T041 — Pier wall ring calculation on LRFD 10th edition development, 27-in U legs (D-084)

**Objective.** The user asked on 22 October 2026 why the end U returns of the pier wall are 6 ft long and whether
that is the LRFD lap splice. They were not: the Pier Wall Design notebook developed the bars with a basic length
`0.17 db [fy / (1.97 f'c^1/4)]^2` without confinement credit (42.0 in for the #5 bars; 71.0-in Class B lap with the
1.3 top-bar factor), and the 72-in U leg input was set to clear that check. By LRFD 10th edition 5.10.8.2.1 the basic
length is 2.4 db fy / sqrt(f'c) = 38.4 in, the location factor 1.3, the confinement factor 0.4 (cb 3.3125 in, no
transverse reinforcement credited), so ld = 20.0 in and the Class B lap 26.0 in. The user directed the notebook onto
the LRFD provisions with 27-in (2 ft 3 in) legs; project decision D-084. The ring wall package and its project export
(PIER-WALL-REPORT / PIER-WALL-CASE, third 22 October run, label 10-22c) were updated first. The journal follows:

- `report:PierWallRings` (C017): replaced by the rebuilt journal edition `ring_wall/bpad/journal/PierWallRings.xml`
  (675 values and 178 statuses verified to 1e-9; two ledger values added, c_b and lambda_rc; the U leg 27 in; the
  wall, rings, fillets, forces, rotation, moment, contact and bearing values unchanged from T037; 1 failed check,
  RING-GRID, as before).
- `report:PedBridge`: one revision paragraph before the newest revision note.
- `report:DecisionLog`: one section appended.

**Exclusions.** The CAD model (its U legs follow under a decision of its own), the substructure drawings, the gravity
sheet, C004, C018, the FBMP exports, the pile and cap modules and every other module.

**Base journal.** The current journal at `prepare` time (the T040 revision; hash recorded in `order.json`).

**Read dependencies.** All-component fallback (no reviewed declaration).

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 16 October).
