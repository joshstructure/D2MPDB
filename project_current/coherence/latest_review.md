# Latest project coherence review

Checked at 2026-10-15T00:48:43.405354+00:00. **12 outstanding items remain.**

The [workbook](Coherence_Tracker.xlsx) owns item status and responses. This report is a generated view.
The initial findings were carried forward from the latest adopted pier/end-bent reviews plus source-inventory gaps.
Previously resolved decisions were excluded. This run did not perform native calculations or a complete engineering review.

Registered sources: 27. Tracker items: 24.
Automatic results: 6 changed, 9 error, 37 match, 5 missing, 10 review.

## Files and relationships needing attention

| Check | Status | Finding |
| --- | --- | --- |
| SOURCE:JOURNAL | CHANGED | File differs from the registered revision; review its consumers before adoption. |
| SOURCE:CAP-TOOL | CHANGED | File differs from the registered revision; review its consumers before adoption. |
| SOURCE:MCAD-DAT1 | MISSING | Registered file is absent. |
| SOURCE:PSB-S1 | MISSING | No source file has been selected. |
| SOURCE:MCAD-DAT2 | MISSING | Registered file is absent. |
| SOURCE:PSB-S2 | MISSING | No source file has been selected. |
| SOURCE:BACKWALL-TOOL | CHANGED | File differs from the registered revision; review its consumers before adoption. |
| SOURCE:EB2-XML | MISSING | Registered file is absent. |
| DEP:GEOMETRY:JOURNAL | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S1:MCAD-DAT1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S1:PSB-S1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:MCAD-DAT2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:PSB-S2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:CAD-MODEL:JOURNAL | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:BACKWALL-TOOL:JOURNAL | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:EB2-REPORT:EB2-XML | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:EB2-CASE:EB2-XML | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:BACKWALL-REPORT:BACKWALL-TOOL | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| PIER:analysis-identity | CHANGED | Raw XML does not match the case analysis fingerprint. |
| EB:analysis-identity | CHANGED | Raw XML does not match the case analysis fingerprint. |
| GEOMETRY:EB:length | CHANGED | Notebook 212 in; source audit 251 in. Comparison tolerance 0.01 in for printed coordinates. |
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
| COH-013 | Awaiting source | Matching raw analysis export | Supply the matching new End Bent 1 XML and native run record; do not substitute the older export. |
| COH-014 | Open | Common controlling design basis | Document how the revised End Bent 1 actions bound both end bents. |
| COH-017 | Open | Mathcad / project comparison | Recalculate with the companion data and compare inputs/outputs. Review the repeated 107.35-ft PSBeam narrative in the Span 2 sheet. |
| COH-018 | Open | Complete notebook comparison | Reconcile complete saved geometry and derived schedules with accepted T006, documenting conventions. |
| COH-019 | Open | End-face U-grid pile clearance | Review and revise the end-face U-grid detail against pile envelopes and fabrication tolerances; regenerate and verify the report. |
| COH-021 | Open | Unregistered tool revisions | Identify the report-generating tool revision, review its changes and consumers, then record an explicit adoption. |
| COH-022 | Open | Current cap source references | Refresh journal source references through the bounded BPAD workflow when directed; preserve C005 and distinguish selected sources from accepted calculations. |
| COH-023 | Open | Reconcile adopted MSE and cheek revision | Reconcile cap/wall calculations, loads and quantities with adopted CAD. Review anchorage, lug steel and strap interfaces before issuing details. |
| COH-024 | Open | Coordinate cap and cheek steel | Review the four 12 3/8 in horizontal spacings. Other cover, pile-clearance, cap and backwall steel findings remain open. |

## Verified scope

- Present-source identity is compared with the source register. Only registered notebook CRLF/LF endings are normalized; native/report files use exact bytes.
- Current journal identity is compared with its existing acceptance receipt; that receipt keeps its original scope.
- Saved cap cases are compared with their report JSON, and raw XML with the analysis fingerprint.
- Selected notebook cap widths, depths, pile counts/sizes/spacings, embedment and lengths are compared with saved cases.
- Mathcad XML readability is checked. Its formulas and external inputs are not recalculated.
- Tracker IDs, statuses, required descriptions and closure evidence are checked.
- Detailed results and exact source/tracker fingerprints are in [machine_checks.json](machine_checks.json).

Automatic matches do not resolve the outstanding workbook items. Responses and original source documents are unchanged.
