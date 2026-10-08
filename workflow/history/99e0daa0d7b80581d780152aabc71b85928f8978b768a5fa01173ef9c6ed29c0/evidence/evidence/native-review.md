# Native and engineering data review — T004

Final candidate: `generated/T004-response-review-02/candidate.bpad`, SHA-256
`99e0daa0d7b80581d780152aabc71b85928f8978b768a5fa01173ef9c6ed29c0`.
Reviewer: Codex, source/data-coherence review and actual Blockpad observations;
no human engineering sign-off is represented.

Both revision 01 and the final revision 02 were opened in the installed Blockpad
application. Dependency resolution completed. Final revision 02 displays nodes
15/34 throughout the entry rows, 0.655-kip local pedestal DC at each node,
the FITS AVAILABLE CAP WIDTH result, and recalculated force/moment balance PASS
results. The corrected load-application prose reads 42 × 36 in by 17 ft 8 in,
and its text cells now wrap instead of clipping. The last row continues onto
the next page; all text is readable.

On revision 01, native review also observed:

- Separate pedestal section inputs and calculations: 30-in end-bent length,
  17.461-ft³ total end-bent volume, unchanged 4-ft pier length and 13.969-ft³
  pier volume. New XML formulas had no fabricated caches.
- Quantity cells: 4.37 ft³ per end-bent pedestal, 17.5 ft³ rounded total; pier
  quantity remains 14.0 ft³ rounded total. Confirmed/deferred notes are visible.
- Current source/model note, both node direction controls and live plan at
  nodes 15/34. Physical axis consistency displays PASS — RIGHT-HANDED.
- Corrected pedestal footprint in the end-bent elevation, 42-in cap width,
  3-in bearing offset and pile embedment. Labels are readable.
- Updated index, coherent response register, foundation-source context and
  complete dated response decision entry. Retired modules are absent from
  navigation. Service III disposition and field hook direction are explicit.

The final revision differs only in the EBUnresolvedApplications prose table.
`revision-comparison.json` proves that all formulas and all other 269 components
are byte-identical to revision 01, and that the FBMPEndBent component is also
identical outside that table. Earlier screenshots retain their revision-01
labeling; they are not relabeled as final captures. Final screenshots document
the changed table and the surrounding native loads and checks.

No native save or journal-wide serialization was performed. The candidate's
on-disk hash is checked after review. XML parsing and independent arithmetic
are supporting evidence, not substituted for these native observations.

Engineering acceptance is limited to the user's directed data reconciliation,
pedestal geometry/quantity bookkeeping, node renumbering, source provenance,
explicit design dispositions and removal of unused modules. Design outcome is
not applicable to this record update. The user confirms source currency and
common controlling-bent applicability, but this task does not independently
rerun FBMP, audit absent raw inputs, design revised hooks or certify structural
adequacy. Existing design and wall-quantity exclusions are documented in
response-review.md and the current journal. Three inherited reference links
remain; there are no new structural issues or stored calculation errors.
