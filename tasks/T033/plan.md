# T033 — C008 and C009 journal editions follow the 20 October End Bent cap reports (D-068)

**Objective.** The registered End Bent 1 and End Bent 2 cap reports were re-exported on 20 October 2026
(D-068, definition and citation cards; the 10-20 reports) from their unchanged cases, and the cap Blockpad
journal editions `cap_bpad/journal/CapDesignEndBentOne.xml` and `CapDesignEndBentTwo.xml` were regenerated
from them, but the journal modules C008 and C009 still carry the 10-19 report provenance. T032 brought the pier
module (C010) to its regenerated edition; this task does the same for the two end-bent modules so every
calculation module equals its committed fragment again (`tests/test_cap_bpad.py`,
`test_review_document_and_fragments_are_journal_compatible`).

- `report:CapDesignEndBentOne` (C008) and `report:CapDesignEndBentTwo` (C009): replaced by the committed journal
  editions. Every dynexp formula, cached result and canvas formula is identical to the base module; only the hidden
  provenance paragraph differs (10-20 report and its generation time; same case and formula hashes).
- `report:PedBridge`: one revision paragraph before the T032 note.
- `report:DecisionLog`: one section appended.

**Exclusions.** No other module. No formula, cache, unit, figure, resource or engineering value changes.

**Base journal.** The current journal at `prepare` time (the T032 revision; hash recorded in `order.json`).

**Read dependencies.** All-component fallback (no reviewed declaration).

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 16 October).
