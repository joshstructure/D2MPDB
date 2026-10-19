# Latest project coherence review

## 19 October backwall/ramp geometry update

D-053 updates both backwall tops in the notebook, B4 spreadsheet and native CAD.
The two 2% top slopes are level through the wall thickness; the ramp slabs
thicken locally to them while keeping their walking faces. Both connections
have at least 4 in of slab at the checked points. Native solids, contact, cover,
spacing and new-overlap checks pass; the spreadsheet recalculates without errors.
See the [verified source receipt](evidence/2026-10-19-simple-backwall-tops/source_receipt.json).

The former EB1 curved-seat rebuild action is superseded by this completed
geometry revision. COH-023 and other broader calculation/detailing items remain
open; tracker statuses and responses are unchanged. The D-052 interactive report
is retained as a **prior geometry snapshot**, not the current backwall detail.
The dated baseline and earlier receipts below remain historical.

## 19 October geometry report source receipt

The supplied interactive geometry report is registered as GEOMETRY-REPORT
under D-052, with its original bytes preserved. It matches notebook model
622e5ca1bf: 19,494 numeric values agree within 1e-9. All four registered
input fingerprints match. See the [source receipt](evidence/2026-10-19-geometry-report/source_receipt.json).
This bounded source addition leaves the tracker and the dated project-wide
check below unchanged; it does not close existing engineering items.

## 19 October cap notebook rerun

D-051 selects three new cap reports and saved cases recalculated from the
D-049 fixed XMLs. All three report/case/XML fingerprints match; EB2 is checked
explicitly in the [receipt](evidence/2026-10-19-cap-rerun/source_receipt.json).
Geometry and reinforcement are preserved. Check ratios are refreshed with no
status changes or new failures: Pier retains 2 FAIL entries including its summary;
each end bent retains 6. Pending and detailing reviews remain.

COH-013's report/raw-source fingerprint gap is resolved. Its existing tracker
status/responses are preserved for native-run documentation and disposition.
COH-028 pile-head review remains: EB1 matches the recorded target at printed
precision; Pier and EB2 remain about 0.08 in above the recorded cutoffs.
The workbook below retains its existing findings and next actions as historical
unamended entries. This update does not assert full-project engineering approval.

## Automatic check and existing tracker view

Checked at 2026-10-19T14:41:13.951970+00:00. **15 outstanding items remain.**

The [workbook](Coherence_Tracker.xlsx) owns item status and responses. This report is a generated view.
The initial findings were carried forward from the latest adopted pier/end-bent reviews plus source-inventory gaps.
Previously resolved decisions were excluded. This run did not perform native calculations or a complete engineering review.

Registered sources: 29. Tracker items: 28.
Automatic results: 2 changed, 9 error, 44 match, 4 missing, 7 review.

## Files and relationships needing attention

| Check | Status | Finding |
| --- | --- | --- |
| SOURCE:JOURNAL | CHANGED | File differs from the registered revision; review its consumers before adoption. |
| SOURCE:CAP-TOOL | CHANGED | File differs from the registered revision; review its consumers before adoption. |
| SOURCE:MCAD-DAT1 | MISSING | Registered file is absent. |
| SOURCE:PSB-S1 | MISSING | No source file has been selected. |
| SOURCE:MCAD-DAT2 | MISSING | Registered file is absent. |
| SOURCE:PSB-S2 | MISSING | No source file has been selected. |
| DEP:GEOMETRY:JOURNAL | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S1:MCAD-DAT1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S1:PSB-S1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:MCAD-DAT2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:PSB-S2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:CAD-MODEL:JOURNAL | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:BACKWALL-TOOL:JOURNAL | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| TRACKER:10 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:11 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:15 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:16 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:19 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:20 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:23 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:24 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:28 | ERROR | Closed / not-applicable item requires resolution evidence. |

## Outstanding items

| ID | Status | Subject | Next action |
| --- | --- | --- | --- |
| COH-004 | Open | Complete model load comparison | Compare the exact current model loading with T006 and document needed reruns and convergence evidence. |
| COH-005 | Open | Wind and wall geometry | Establish remaining wall/fin geometry and compare current model wind loads with the T006 basis. |
| COH-010 | Deferred | Backwall and cheek-wall quantities | Supply final wall details, then reconcile quantities and dead loads. |
| COH-013 | Awaiting source | Report-matching FBMP exports | Submit the exact XML exports behind the final selected cap reports, with their native run records. After the COH-028 pile-head reruns these are the rerun exports and regenerated reports. Do not substitute older exports. |
| COH-014 | Open | Common controlling design basis | Document how the revised End Bent 1 actions bound both end bents. |
| COH-017 | Open | Mathcad / project comparison | Recalculate with the companion data and compare inputs/outputs. Review the repeated 107.35-ft PSBeam narrative in the Span 2 sheet. |
| COH-018 | Open | Complete notebook comparison | Reconcile complete saved geometry and derived schedules with accepted T006, documenting conventions. |
| COH-019 | Open | End-face U-grid pile clearance | Review and revise the end-face U-grid detail against pile envelopes and fabrication tolerances; regenerate and verify the report. |
| COH-021 | Open | Unregistered tool revisions | Identify the report-generating tool revision, review its changes and consumers, then record an explicit adoption. |
| COH-022 | Open | Current cap source references | Refresh journal source references through the bounded BPAD workflow when directed; preserve C005 and distinguish selected sources from accepted calculations. |
| COH-023 | Open | Reconcile adopted MSE and cheek revision | Reconcile cap/wall calculations, loads and quantities with adopted CAD. Review anchorage, lug steel and strap interfaces before issuing details. |
| COH-024 | Open | Coordinate cap and cheek steel | Review remaining cap/backwall cover, pile clearance, anchorage and fabrication findings. Cheek spacing and cap/cheek overlap findings are resolved. Keep the separate COH-025 U-bar/hoop deferral. |
| COH-025 | Deferred | End-bent U-bar / hoop overlaps | Review the U-bar / hoop intersections later and agree revisions. Recheck affected steel, cover, spacing, piles and WWR before closing. Leave current stirrups and U-bars unchanged. |
| COH-026 | Open | Coping and MSE wall overlaps | Agree concrete ownership and trim the coping/wall interfaces. Recheck concrete quantities and contact geometry. |
| COH-028 | Open | Rerun final FBMP with current pile heads | Rerun the final pier, End Bent 1 and End Bent 2 FBMP analyses with pile-head nodes at the notebook cutoffs: pier 41.764940 ft (Z -501.18 in), EB1 41.237692 ft (Z -494.85 in), EB2 41.249692 ft (Z -495.00 in). Confirm pile length, tip and soil inputs, and rerun minimum-tip variants still in use. Regenerate the cap reports and cases, then submit the exports under COH-013. |

## Verified scope

- Present-source identity is compared with the source register. Only registered notebook CRLF/LF endings are normalized; native/report files use exact bytes.
- Current journal identity is compared with its existing acceptance receipt; that receipt keeps its original scope.
- Saved cap cases are compared with their report JSON, and raw XML with the analysis fingerprint.
- Selected notebook cap widths, depths, pile counts/sizes/spacings, embedment and lengths are compared with saved cases.
- Mathcad XML readability is checked. Its formulas and external inputs are not recalculated.
- Tracker IDs, statuses, required descriptions and closure evidence are checked.
- Detailed results and exact source/tracker fingerprints are in [machine_checks.json](machine_checks.json).

Automatic matches do not resolve the outstanding workbook items. Responses and original source documents are unchanged.
