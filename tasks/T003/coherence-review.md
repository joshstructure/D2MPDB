# End-bent journal coherence review — 8 October 2026

The journal update records the supplied end-bent cap geometry and current cage
for **both end bents**, as confirmed by the user. End Bent 1 force results remain
an identified source snapshot. This review checks the consistency of that data
record; it does not approve the cage or establish a current foundation analysis.

| Item | Updated journal basis |
| --- | --- |
| Rectangular cap | 17 ft 8 in long × 42 in wide × 36 in deep |
| Piles per cap | Four 18-in square piles at 54-in centers |
| Centers from left cap end | 25, 79, 133, 187 in |
| Nominal end-to-pile face | 16 in = 9-in edge allowance + 3-in tolerance + 4-in detail allowance |
| Embedment / cover | 12-in pile embedment; 3-in top, bottom and side cover |
| Clearance inputs | 1-in pile-to-bar gap; separate 2-in bar-to-bar minimum |
| Top steel | 4 #6 continuous; 1.76 in² |
| Bottom at piles | 2 #8 continuous; 1.58 in² |
| Bottom between piles | 2 #8 continuous + 2 additional #5 hooked bars; 2.20 in² |
| Side steel | 7 #4 per side; 1.40 in² per side |
| Actual transverse steel | 19 closed #4 hoops + 16 open-bottom #4 U-bars; nine runs, 6-in pitch |
| Gross cap concrete | 185.5 ft³ each; 371 ft³ for both; backwalls/pedestals excluded |
| Cap self-weight | 27.825 kip each at the existing 150-pcf project density |
| Source reinforcing estimate | 616.259 lb each; excludes laps, closures, undrawn anchorage and waste |

The existing backwall/beam/bearing chain retains its 24-in bearing line from the
rear cap face. The centered pile line moves to 21 in, giving a 3-in spanward
bearing offset and 13-in pad-front clearance. Native formulas propagate the
offset into the existing DC/PL/DW and wind moment transfers; stale dependent
display caches are omitted for Blockpad recalculation. This geometric chain is
not proof of the coordinates or load inputs in the analyzed XML.

The obsolete 14.3592-ft² × 19-ft-3-in combined cap/backwall quantity is replaced
by clearly labeled cap-only quantities. No backwall volume was invented or set
to zero as a completed quantity. The quantity sheet explicitly excludes it
pending the applicable detail. The 20-in pipe-pile section calculations and
group-spacing discussion are explicitly identified as pier calculations.

## Coherence findings that remain open

1. **Pedestal footprint:** the journal retains a 48-in longitudinal footprint on
   a 42-in cap. A revised dimension was requested; none has been supplied.
   Pedestal quantities and related below-pad dead weights remain provisional.
2. **Backwall and cheek walls:** the cap-only report does not establish a
   complete backwall quantity or revise the legacy cheek-wall takeoff. The
   quantity sheet excludes backwalls from the cap total and marks cheek walls
   provisional. Confirm geometry and dead load separately.
3. **Source XML identity:** the report records SHA-256
   `739f44c1d542464cfd536493ce1ed6cb240f98a75ed3e1188c6f6812742d6fe2`.
   `Downloads/End Bent 1.XML` instead hashes to
   `744048c5c0dfa398ddc50f9cf14e51fca2d2a3a985a6c0e73680a35cce2d5811`.
   That same-named file was not substituted for the source analysis.
4. **Node mapping:** the entry module retains historical nodes 12/19, while the
   report audit places the bearing force stations at nodes 15/34. The entry
   module now prominently requires remapping and model verification. This
   evidence does not establish the complete application-node transformation.
5. **Reference station:** report geometry/cage stations start at the cap end;
   audit force stations start at the first pile center. Add 25 in to convert.
   Audit bearing separation is 102.99 in versus the journal's 103 in, consistent
   with the source's displayed precision rather than an exact equality.
6. **Cage conflicts:** R2, R4, R6 and R8 intersect pile/clearance envelopes.
   The recorded 0 failed scalar checks does not negate these conflicts.
7. **Design completion:** 48 pending/conditional checks remain, including
   Service III, fatigue, development and anchorage. Code/exposure basis,
   force-zone applicability, D-regions and excluded action components remain
   unclosed. Independent action maxima are not simultaneous forces.
8. **End Bent 2:** shared geometry and current steel are user-confirmed;
   its own design actions, analysis identity and adequacy are not supplied.
9. **Inherited journal defects:** 110 stored errors (4 in FBMPMinTip and 106 in
   FeetintoDecimalFeet) and three unresolved LoadCombinations reference links
   are preserved and excluded from this bounded update. They prevent a claim
   that the entire project is error-free.

## Verification and preservation

`tasks/T002/coherence_checks.json` records 33 passing independent checks of the
actual changed formulas, source geometry, steel areas, all transverse stations,
source gross steel estimate, maximum available ratio and pending-check count.
The checks use a dimensional evaluator and the existing project cap engine;
they do not claim to be Blockpad recalculation or code approval.

T003 carries exactly the seven T002 module changes plus 31 relative reference
paths. Every other top-level component, embedded resource, PDF and the document
wrapper is preserved. The three inherited broken links and 110 stored errors
have no new additions. The full HTML and embedded case are retained under
`tasks/T002/sources/`, with provenance hashes. Existing unrelated notebook/code
edits in the working tree are not part of this task.

Native review included the geometry inputs and results, live end-bent section,
bearing dimension chain, steel areas, nine-run transverse schedule, source
forces, open-item tables, quantity sheet and dated notes. The final candidate
was opened in Blockpad and its dependency resolution completed. Native results
include 185.5 ft³ per cap, 371 ft³ for both and a 3-in bearing offset. The existing
quantity-sheet display rounds the single-cap value to 186 ft³; the underlying
formula and geometry report retain 185.5 ft³.

The reviewed revision is SHA-256
`a45256fbdd3c27444bb3b93ffc327353efcfdc366a126aff35f809a853635d72`.
Detailed evidence and scope dispositions are retained with the promotion
receipt. This accepts the updated data record with explicitly unresolved
items, not a completed design or an error-free project.
