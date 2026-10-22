# T036 — Pier modules follow the 22 October 2026 FBMP rerun (D-077)

**Objective.** The user supplied a rerun fixed pier export (`Pier_Fixed.XML`, 22 October 2026) after finding that
the pier wall extra members had followed the soil elevation changes. Compared with the 21 October export (D-073),
the only model change is the extent of the four vertical 36 x 60 in wall members between the pile nodes: pile
points 2 to 11 (EL 40.20 to the soil surface EL 26.05, 169.8 in, 127.3 kip in all) in place of points 2 to 13
(EL 19.72, 245.8 in, 184.4 kip); nodal and bearing loads, geometry, pile section and material, soil and the four
load combinations are identical. The project record selected it under D-077 (register row PIER-XML), rerun the
pier cap case (nine force inputs moved, 62 ratios changed, no status changes) and the three pile cases (pier
demands follow the export; End Bent cases re-exported for package currency with identical checks). The journal
follows:

- `report:CapDesignPier` (C010): replaced by the regenerated journal edition `cap_bpad/journal/CapDesignPier.xml`
  (scripts/build_cap_bpad.py --journal on the 22 October case: the force envelopes, ratios and the hidden
  provenance paragraph change; geometry, reinforcement and references unchanged).
- `report:PileDesignPier` (C013): replaced by the regenerated journal edition `pile_bpad/journal/PileDesignPier.xml`
  (scripts/build_pile_bpad.py on the preset case read from the new export).
- `report:FBMPPier`: geometry source, report and XML identities move to the 10-22 report and the D-077 export; the
  RESOLVED note gains the 22 October rerun (exact-substring surgery).
- `report:FoundationModeling`: the current-model paragraph names the 22 October pier export (exact-substring surgery).
- `report:BridgeGeometry_2Beam`: the two sentences that name the pier analysis export and the pier cap report
  move to the 22 October export and the 10-22 report (exact-substring surgery; no value, cache or figure changes).
- `report:PedBridge`: one revision paragraph before the newest revision note.
- `report:DecisionLog`: one section appended.

**Exclusions.** End-bent exports and modules (C008, C009, C011, C012, C014, the FBMP end-bent entry), Pile Section
Properties (material unchanged) and every other module. No formula, cache, unit, figure or resource of any other
module changes.

**Base journal.** The current journal at `prepare` time (the T035 revision; hash recorded in `order.json`).

**Read dependencies.** All-component fallback (no reviewed declaration). The two calculation editions are regenerated
by their generators against the base journal through their coherence gates.

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 16 October).
FBMP was rerun by the user, not here.
