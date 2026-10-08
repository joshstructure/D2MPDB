# Native and data-record review — 8 October 2026

Reviewer: Codex, using the installed Blockpad application for native observations
and source/XML inspection for data coherence. No human engineering sign-off is
represented by this record.

Final candidate: `generated/T003-end-bent-review-03/candidate.bpad`, SHA-256
`a45256fbdd3c27444bb3b93ffc327353efcfdc366a126aff35f809a853635d72`.

## Native observations

The final candidate was opened in Blockpad. The application completed its
dependency-resolution operation. The final index, quantity cells, provisional
cheek-wall note, pile applicability note, foundation-model note and dated
decision entry were visually inspected. They render without clipped new text.
The underlying cap volume is 185.5 ft³, displayed by the existing quantity-sheet
style as 186 ft³; both caps display 371 ft³. The new formulas have no manufactured
native caches and are evaluated by Blockpad on opening.

The preceding revision 02 was also opened and reviewed in Blockpad. It differs
from the final candidate only in the quantity component: the final revision
adds a provisional cheek-wall note and a D104 display-format attribute, without
changing any calculation. Its six reviewed report components, all resources,
styles and references are byte-identical to the final revision. This equality
is asserted in `verify_integration.py`; earlier screenshots are labeled as
revision 02 evidence rather than presented as final-candidate screenshots.

Native observations on those identical report components include:

- 42-in cap width, 36-in depth, four 18-in square piles, 54-in center spacing,
  12-in physical embedment and 3-in covers.
- 17-ft-8-in cap length; pile centers 25, 79, 133 and 187 in; 36-in clear spacing;
  10.5-ft² cap section; 185.5-ft³ and 371-ft³ volumes; 27.825-kip cap self-weight.
- 21-in pile line, 24-in bearing line, 3-in offset and 13-in pad-front clearance.
  The existing live section drawing reflects the width and pile embedment.
- Native steel areas 1.76, 1.58, 2.20 and 1.40 in². All nine transverse runs,
  fitted-coordinate and source-force tables, material inputs and unresolved-item
  tables render readably. The schedule and open-item tables remain together on
  their pages. The source-screen status and clashes are clearly identified.
- The entry module displays the required model/node warning and a recalculated
  0.25-ft longitudinal bearing offset. Existing entry forces remain provisional
  until the exact external model, application nodes and loads are reconciled.

No native save was needed: accepting the XML-authored bytes preserves unrelated
components and avoids a whole-journal serialization. The exact on-disk candidate
hash was checked after native review. All 31 PDF references resolve by relative
path to unchanged files; this file-identity check is not a claim of new review of
the referenced code provisions. Inherited errors were not repaired or certified.

## Accepted scope and exclusions

Engineering review here is limited to source transcription, dimensions, units,
station origins, steel areas/counts, quantity scope, dependent bearing geometry,
analysis provenance and clear identification of incompatible or missing data.
The 33 independent checks supplement the native observations. The journal data
record is consistent with the supplied cap/cage snapshot and the user's
confirmation that it applies to both end bents.

Design outcome: **not applicable to this data-record update**. No new adequacy
claim is accepted. The source has four U-bar/pile conflicts and 48 pending or
conditional checks. Its zero failed scalar checks are not final design approval.
The 48-in pedestal, backwall and legacy cheek-wall quantities, End Bent 2 forces,
exact analysis XML and legacy node mapping remain unresolved. External analysis
results are explicitly excluded from accepted current engineering results.

All 110 inherited stored errors and three unresolved LoadCombinations links are
preserved, identified in the journal and excluded from this bounded acceptance.
Full project coherence therefore remains open as listed in `coherence-review.md`.

The user requested XML-first work and minimum application use. All authoring and
consistency checks were performed in XML; native interaction was used to satisfy
the repository's recalculation/appearance promotion requirement. No commit or
push is part of this task.
