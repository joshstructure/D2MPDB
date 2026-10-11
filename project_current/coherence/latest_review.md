# Latest project coherence review

Checked at 2026-10-11T01:16:33.458869+00:00. **19 outstanding items remain.**

The [workbook](Coherence_Tracker.xlsx) owns item status and responses. This report is a generated view.
The initial findings were carried forward from the latest adopted pier/end-bent reviews plus source-inventory gaps.
Previously resolved decisions were excluded. This run did not perform native calculations or a complete engineering review.

Registered sources: 18. Tracker items: 22.
Automatic results: 1 changed, 34 match, 4 missing, 4 review.

## FBMP source receipt

Four current XML variants are registered. Both fixed exports exactly match their
current cap reports/cases. The end-bent raw XML is now present. Workbook statuses
are preserved: COH-013 still carries its prior action pending native-run
documentation and workbook disposition. See the
[source receipt](evidence/2026-10-10-fbmp/source_receipt.json).

## Files and relationships needing attention

| Check | Status | Finding |
| --- | --- | --- |
| SOURCE:CAP-TOOL | CHANGED | File differs from the registered revision; review its consumers before adoption. |
| SOURCE:MCAD-DAT1 | MISSING | Registered file is absent. |
| SOURCE:PSB-S1 | MISSING | No source file has been selected. |
| SOURCE:MCAD-DAT2 | MISSING | Registered file is absent. |
| SOURCE:PSB-S2 | MISSING | No source file has been selected. |
| DEP:MCAD-S1:MCAD-DAT1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S1:PSB-S1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:MCAD-DAT2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:PSB-S2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |

## Outstanding items

| ID | Status | Subject | Next action |
| --- | --- | --- | --- |
| COH-002 | Open | U-bar / pile conflicts | Verify the revised U-bar clearance, development and engagement. Separate end-face U-grid failure is COH-019. |
| COH-003 | Open | Longitudinal tension reference | Resolve developed-steel and load-path prerequisites and document actual-cage acceptance. |
| COH-004 | Open | Complete model load comparison | Compare the exact current model loading with T006 and document needed reruns and convergence evidence. |
| COH-005 | Open | Wind and wall geometry | Establish remaining wall/fin geometry and compare current model wind loads with the T006 basis. |
| COH-007 | Deferred | Remaining design checks | Retain the recorded deferral. Resolve individual checks when directed; address new end-grid failure under COH-019. |
| COH-008 | Deferred | Spacing and fabrication takeoff | Complete the tolerance and fabrication takeoff review at shops, preserving the deferral. |
| COH-010 | Deferred | Backwall and cheek-wall quantities | Supply final wall details, then reconcile quantities and dead loads. |
| COH-011 | Open | Revised U-bar hooks | Verify revised hook clearance, development and engagement. Separate end-face U-grid failure is COH-020. |
| COH-012 | Open | Remaining design checks | Record evidence/disposition for remaining fatigue, anchorage, shear prerequisites, face reinforcement, D-regions and exposure checks. |
| COH-013 | Awaiting source | Matching raw analysis export | Supply the matching new End Bent 1 XML and native run record; do not substitute the older export. |
| COH-014 | Open | Common controlling design basis | Document how the revised End Bent 1 actions bound both end bents. |
| COH-015 | Awaiting source | Mathcad companion data | Add the matching .dat files and verify the worksheets load the intended project inputs. |
| COH-016 | Awaiting source | PSBeam run packages | Add each span input/run file and matching output report, with software version and run date. |
| COH-017 | Open | Mathcad / project comparison | Recalculate with the companion data and compare inputs/outputs. Review the repeated 107.35-ft PSBeam narrative in the Span 2 sheet. |
| COH-018 | Open | Complete notebook comparison | Reconcile complete saved geometry and derived schedules with accepted T006, documenting conventions. |
| COH-019 | Open | End-face U-grid pile clearance | Review and revise the end-face U-grid detail against pile envelopes and fabrication tolerances; regenerate and verify the report. |
| COH-020 | Open | End-face U-grid pile clearance | Review and revise the end-face U-grid detail and verify it for both ends; regenerate and verify the report. |
| COH-021 | Open | Unregistered tool revisions | Identify the report-generating tool revision, review its changes and consumers, then record an explicit adoption. |
| COH-022 | Open | Current cap source references | Refresh journal source references through the bounded BPAD workflow when directed; preserve C005 and distinguish selected sources from accepted calculations. |

## Verified scope

- Present-source identity is compared with the source register. Only registered notebook CRLF/LF endings are normalized; native/report files use exact bytes.
- Current journal identity is compared with its existing acceptance receipt; that receipt keeps its original scope.
- Saved cap cases are compared with their report JSON, and raw XML with the analysis fingerprint.
- Selected notebook cap widths, depths, pile counts/sizes/spacings, embedment and lengths are compared with saved cases.
- Mathcad XML readability is checked. Its formulas and external inputs are not recalculated.
- Tracker IDs, statuses, required descriptions and closure evidence are checked.
- Detailed results and exact source/tracker fingerprints are in [machine_checks.json](machine_checks.json).

Automatic matches do not resolve the outstanding workbook items. Responses and original source documents are unchanged.
