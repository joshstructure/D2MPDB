# T035 — C006 and C004 journal editions name the T034 journal as their value source

**Objective.** T034 (D-075) edited the gravity sheet row 42 and regenerated C006 and C004 with the new pier wall
values, but the two packages still named the T027 journal (feb1bb31…) as the journal whose values their inputs equal
(`data/sources.json`, the case name and the hidden provenance sentence). The packages now name the T034 journal
(82e7d3e1…) and their import snapshots carry the former modules' formulas re-evaluated with its values
(scripts/refresh_journal_import_values.py), so the journal editions are regenerated once more:

- `report:PierWallFins` (C006) and `report:SuperstructureUplift` (C004): replaced by the regenerated journal editions
  (`<package>/bpad/journal/<Report>.xml`, built against the current journal through their coherence gates). Every
  dynexp formula, cached result and canvas formula is identical to the T034 modules; only hidden working-notes text
  differs (the case name and the provenance sentence).

**Exclusions.** No other module. No formula, cache, unit, figure, resource or engineering value changes.

**Base journal.** The current journal at `prepare` time (the T034 revision; hash recorded in `order.json`).

**Read dependencies.** All-component fallback (no reviewed declaration).

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 16 October).
