# T032 — Pier modules follow the 21 October 2026 FBMP rerun (D-073)

**Objective.** The user supplied a new fixed-run pier export (`Pier_Fixed.XML`, 21 October 2026) and asked
for the whole project flow to follow it. The export differs from the 19 October one (D-049) only in the pipe
pile material: ASTM A252 Grade 3, Fy 45 ksi, in place of 60 ksi. Nodal loads, geometry, pile section, soil and
load combinations are identical; cap member forces differ only by solver noise. The project record selected it
under D-073 (register row PIER-XML), rerun the pier cap case (every envelope, ratio and status unchanged; analysis
identity refreshed) and the pier pile case (demands unchanged; the `steel_grade` prerequisite is now source-backed
because the model Fy equals the design Fy). The journal follows:

- `report:CapDesignPier` (C010): replaced by the regenerated journal edition `cap_bpad/journal/CapDesignPier.xml`
  (scripts/build_cap_bpad.py --journal on the 21 October case; the same definitions, caches and references; only
  the hidden provenance paragraph names the 10-21 report and the new XML identity).
- `report:PileDesignPier` (C013): replaced by the regenerated journal edition `pile_bpad/journal/PileDesignPier.xml`
  (scripts/build_pile_bpad.py on the preset case read from the new export: the FBMP source line, the steel-grade
  prerequisite (confirmed, source-backed) and the pending count change; every demand and resistance value unchanged).
- `report:PileProperties`: the two paragraphs that describe the 60 ksi model material and the pending Fy
  reconciliation now record the 45 ksi material and its closure (exact-substring surgery).
- `report:FBMPPier`: geometry source, report and XML identities move to the 10-21 report and the D-073 export; the
  RESOLVED note gains the 21 October rerun (exact-substring surgery).
- `report:FoundationModeling`: the current-model paragraph names the 21 October pier export (exact-substring surgery).
- `report:BridgeGeometry_2Beam`: the two sentences that name the pier analysis export and the pier cap report
  move to the 21 October export and the 10-21 report (exact-substring surgery; no value, cache or figure changes).
- `report:PedBridge`: the current-sources heading and summary name the D-073 pier export; one revision paragraph.
- `report:DecisionLog`: one section appended.

**Exclusions.** End-bent exports, cases and reports are unchanged, so C008, C009, C011, C012, C014 and the FBMP
end-bent entry are not touched. No formula, cache, unit, figure or resource of any other module changes. No
engineering value changes anywhere: the cap and pile editions reproduce the same numbers.

**Base journal.** The current journal at `prepare` time (hash recorded in `order.json`).

**Read dependencies.** All-component fallback (no reviewed declaration). The two calculation editions are regenerated
by their generators against the base journal through their coherence gates (every journal-owned input equal to the case).

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 16 October).
FBMP was rerun by the user, not here.
