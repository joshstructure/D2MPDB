# T022 — Calculation numbering C007–C016 and submission formatting

User request (20 October 2026): prepare the journal's design and analysis
calculations for submission as a finished product.

1. Number the calculation modules `CXXX`, continuing the existing C001–C004 and
   C006 series (C005 stays retired: it was the deleted live pier cap module and
   the repository still names its formula set by that number).
2. Move the internal working language (how a calculation was produced, its tool
   status, pending-item bookkeeping, decision and task identifiers, package and
   file hashes) into hidden sections. A reviewer sees the calculation only.
3. Table text goes in multiline cells (`<textcell>`) instead of value cells
   (`<c>`), which clip long text natively. Formula cells (numbers, PASS/FAIL
   strings with conditional colour) stay value cells.
4. The word "distilled" leaves the visible text and the titles.

## Numbering

| Module | New title |
| --- | --- |
| CapDesignBasis | C007 - Cap Design Basis (shared factors) |
| CapDesignEndBentOne | C008 - End Bent 1 Cap Design |
| CapDesignEndBentTwo | C009 - End Bent 2 Cap Design |
| CapDesignPier | C010 - Pier Cap Design |
| PileDesignEndBentOne | C011 - End Bent 1 Pile Design |
| PileDesignEndBentTwo | C012 - End Bent 2 Pile Design |
| PileDesignPier | C013 - Pier Pile Design |
| EndBentBackwallDesign | C014 - End Bent 1 Backwall, Cheek Walls and Tie-Back Straps |
| MSEWallExclusion | C015 - MSE Wall Exclusion - Both End Bents |
| BearingDesign | C016 - Bearings and Support Details |

C001–C004 and C006 keep their titles. Basis modules (Materials, Bridge Geometry,
Pile Section Properties, loads, FBMP entry records, Foundation Modeling) are not
calculations and are not numbered.

## Scope and dependencies

- Base journal: `39674378a62fa24184f43176914b2cca538cb64de015345cb29d911fc80747ce` (T021).
- Permitted components (all `report:`): PedBridge (index labels, revision note),
  DecisionLog (entry), CapDesignBasis, CapDesignEndBentOne, CapDesignEndBentTwo,
  CapDesignPier, PileDesignEndBentOne, PileDesignEndBentTwo, PileDesignPier,
  EndBentBackwallDesign, MSEWallExclusion, BearingDesign,
  C001WindLoadOnPedBridgeSuperstructure, FenceWind, BridgeMovement,
  SuperstructureUplift, PierWallFins.
- Generated modules (caps, basis, piles, backwall) are rebuilt by their
  generators (`scripts/build_cap_bpad.py --journal`, `scripts/build_pile_bpad.py`,
  `scripts/build_backwall_bpad.py --journal`) so the staleness tests keep
  passing; the task copies the fragments. Hand-authored modules are edited by
  `tasks/T022/submission_format.py` (byte-surgical, rerunnable).
- Report names, every formula, every cache, every canvas and every resource are
  unchanged; only titles, prose, section hiding and table cell kinds change.
  Conservative all-component dependency fallback. No prerequisite task.

## Acceptance

- Every dynexp/formula string of each edited module is unchanged (multiset
  equality against the base); no `<c>` static-text cell remains in the
  calculation modules; titles carry the numbers; the index links name them.
- No visible paragraph or cell of the calculation modules matches the
  working-language markers (distill, notebook, tool, journal, D-nnn, Tnnn, .py,
  .ipynb, SHA-256, pending, task, Codex); the generators enforce this at build.
- Workflow `check` and `assemble` pass; promotion under the current policy.
  Native recalculation, appearance and engineering review are not performed and
  are recorded as such. No engineering value changes; FBMP not rerun.
