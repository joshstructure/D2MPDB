# T031 — Retire the C001–C004 code-reference modules; citations stay as plain text

**Objective.** The four journal modules `CodeReferencesC001` … `CodeReferencesC004` ("C00x - References": GetRefs code
excerpts for C001 to C004) are removed. The calculation reports built from the notebook packages now carry every
citation as a card with the highlighted provision (report_cards / code_excerpts), so the journal keeps only the
distilled calculation editions. Every native link into the four modules is retired: the index entries in
`PedBridge`, the catalogue entries and cross-links in `CodeReferencesGeneral`, and the citation links inside the
C001–C004 editions (they become plain text, written by the generator from the same package data).

**Exclusions.** `CodeReferencesGeneral` stays (its own pages 10, 11, 14 and 16 are read by GeneralLoads,
LoadCombinations and FBMPPier); only its links into the deleted modules change. The `xref:ReferencePDF*` registrations
and the References folder stay. No formula, cache, unit, value, figure or resource changes. C006, C015 and C016 hold no
links into the deleted modules and are not registered. Nothing else in the journal is touched.

**Base journal.** The current journal at `prepare` time (hash recorded in `order.json`).

**Permitted components.**
- delete: `report:CodeReferencesC001`, `report:CodeReferencesC002`, `report:CodeReferencesC003`, `report:CodeReferencesC004`
- write: `report:PedBridge` (drop the four "C00x - References" index paragraphs; revision note),
  `report:CodeReferencesGeneral` (links into the deleted modules become plain text; the intro paragraph says where the
  excerpts live now), `report:C001WindLoadOnPedBridgeSuperstructure`, `report:FenceWind`, `report:BridgeMovement`,
  `report:SuperstructureUplift` (rebuilt journal editions: `scripts/build_journal_calc_bpads.py --journal` with
  `calc_common/bpad.py` unwrapping every `#CodeReferences…` link and dropping the "Reference packet:" pointer
  paragraphs), `report:DecisionLog` (one entry).

**Read dependencies.** All-component fallback (no reviewed declaration). The four calc editions are regenerated from
their packages against the base journal through the coherence gate (every journal-owned input equal to the case).

**Source documents.** The calculation reports under `<package>/report/` (citation cards) are the home of the excerpts
from now on; `code_excerpts/excerpts.json` and `code_excerpts/pages/` hold the crops.

**Output contract.** Unchanged: the published names of C001–C004 (read by other modules as live references) are
defined exactly as before; no numerical output changes.

**Downstream.** None numerical. The lineage graph and atlas re-read the journal hash (register JOURNAL row).

**Acceptance.** `check` passes (no remaining native link into a deleted module; no published name lost; no new stored
error); every name another module reads from C001–C004 is still defined; every inbound link target from the surviving
modules is still present; the visible-text rule holds; the fragments match their verification records.

**Reviews.** Native recalculation, appearance and engineering reviews not performed (promotion policy of 2026-10-16).
Bounded file-integrity verification only.

**Stop conditions.** A remaining link into a deleted module outside the registered components; a published name
lost; a changed base journal between prepare and check.
