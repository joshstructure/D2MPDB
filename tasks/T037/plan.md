# T037 — Pier wall ring plate 1/2 in (D-078)

**Objective.** The user asked on 22 October 2026 what the thinnest annular ring plate can be with no check above
0.95 of its limit, then directed "Lets update the design to 1/2 thick plate". Sweeping the plate thickness through
the ring_wall engine with every other input held: the strength checks reach 0.95 of capacity only at about 0.17 in
(row-5 plate bending); with the 5/16-in fillet held, the maximum fillet at the ring edge (leg at most the plate
thickness less 1/16 in, LRFD 6.13.3.4) governs and gives 7/16 in (0.83) as the thinnest standard plate, 3/8 in
sitting at 1.00. The 3/4-in plate of the first editions was not strength-governed (plate bending 0.05 of
capacity). Project decision D-078; the ring wall package default and its project export (PIER-WALL-REPORT /
PIER-WALL-CASE, second 22 October run, label 10-22b) were updated first. The journal follows:

- `report:PierWallRings` (C017): replaced by the rebuilt journal edition `ring_wall/bpad/journal/PierWallRings.xml`
  (the 1/2-in plate starting case: 673 values and 178 statuses verified to 1e-9; 1 failed check, RING-GRID, as
  before; the ring diameters, fillets, forces, rotation, moment, contact and bearing values are those of T034;
  the plate, shear, weld and base-metal demands and ratios and the minimum/maximum fillet checks change).
- `report:PedBridge`: one revision paragraph before the T036 note.
- `report:DecisionLog`: one section appended.

**Exclusions.** The CAD model (its D-076 rings are 3/4 in thick; reconciliation pending), C006 (fin-plate concept;
the support concept is still undecided), the gravity sheet, C004, the FBMP exports, the pile and cap modules and
every other module.

**Base journal.** The current journal at `prepare` time (the T036 revision; hash recorded in `order.json`).

**Read dependencies.** All-component fallback (no reviewed declaration).

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 16 October).
