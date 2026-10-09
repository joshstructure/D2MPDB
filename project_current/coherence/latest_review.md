# Latest project coherence review

Checked at 2026-10-09T21:20:56.164175+00:00. **18 outstanding items remain.**

The [workbook](Coherence_Tracker.xlsx) owns item status and responses. This report is a generated view.
The initial findings were carried forward from the latest adopted pier/end-bent reviews plus source-inventory gaps.
Previously resolved decisions were excluded. This run did not perform native calculations or a complete engineering review.

Registered sources: 16. Tracker items: 18.
Automatic results: 31 match, 6 missing, 6 review.

## Files and relationships needing attention

| Check | Status | Finding |
| --- | --- | --- |
| SOURCE:EB-XML | MISSING | Registered file is absent. |
| SOURCE:MCAD-DAT1 | MISSING | Registered file is absent. |
| SOURCE:PSB-S1 | MISSING | No source file has been selected. |
| SOURCE:MCAD-DAT2 | MISSING | Registered file is absent. |
| SOURCE:PSB-S2 | MISSING | No source file has been selected. |
| DEP:EB-REPORT:EB-XML | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:EB-CASE:EB-XML | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S1:MCAD-DAT1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S1:PSB-S1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:MCAD-DAT2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:PSB-S2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| EB:analysis-identity | MISSING | Exact XML required by the case is absent: 739f44c1d542464cfd536493ce1ed6cb240f98a75ed3e1188c6f6812742d6fe2 |

## Outstanding items

| ID | Status | Subject | Next action |
| --- | --- | --- | --- |
| COH-001 | Open | Right bearing-row offset | Choose the intended offset, then reconcile the model/journal and affected load transfers. |
| COH-002 | Open | U-bar / pile conflicts | Provide or develop the pier hook detail and check clearance, development and anchorage. |
| COH-003 | Open | Longitudinal tension reference | Evaluate the actual cage/load path or document the disposition of the reference check. |
| COH-004 | Open | Complete model load comparison | Compare the adopted load inputs and document any corrections and required rerun. |
| COH-005 | Open | Wind and wall geometry | Establish the wall/wind dimensions and update only the affected loads and quantities. |
| COH-006 | Open | Historical quantity sketches | Update or explicitly label the historical sketches without changing current calculation records. |
| COH-007 | Open | Remaining design checks | Separate the remaining checks into actionable items and document applicable criteria and completion evidence. |
| COH-008 | Open | Spacing and fabrication takeoff | Confirm tolerance/spacing allowance and complete the fabrication takeoff if required. |
| COH-009 | Open | Three reference links | Identify and repair the intended references through the existing journal workflow. |
| COH-010 | Deferred | Backwall and cheek-wall quantities | Supply final wall details, then reconcile quantities and dead loads. |
| COH-011 | Open | Revised U-bar hooks | Document the adjusted detail and verify clearance/development/anchorage. |
| COH-012 | Open | Remaining design checks | Record a disposition and evidence for each applicable outstanding design check. |
| COH-013 | Awaiting source | Matching raw analysis export | Add the exact matching XML and its native input/run record. Expected hash is in source_register.csv. |
| COH-014 | Open | Common controlling design basis | Document how End Bent 1 bounds the relevant End Bent 2 actions and conditions. |
| COH-015 | Awaiting source | Mathcad companion data | Add the matching .dat files and verify the worksheets load the intended project inputs. |
| COH-016 | Awaiting source | PSBeam run packages | Add each span input/run file and matching output report, with software version and run date. |
| COH-017 | Open | Mathcad / project comparison | Recalculate with the companion data and compare inputs/outputs. Review the repeated 107.35-ft PSBeam narrative in the Span 2 sheet. |
| COH-018 | Open | Complete notebook comparison | Reconcile the complete saved geometry inputs and derived schedules with the current journal, documenting agreed conventions. |

## Verified scope

- Present-source identity is compared with the source register. Only registered notebook CRLF/LF endings are normalized; native/report files use exact bytes.
- Current journal identity is compared with its existing acceptance receipt; that receipt keeps its original scope.
- Saved cap cases are compared with their report JSON, and raw XML with the analysis fingerprint.
- Selected notebook cap widths, depths, pile counts/sizes/spacings, embedment and lengths are compared with saved cases.
- Mathcad XML readability is checked. Its formulas and external inputs are not recalculated.
- Tracker IDs, statuses, required descriptions and closure evidence are checked.
- Detailed results and exact source/tracker fingerprints are in [machine_checks.json](machine_checks.json).

Automatic matches do not resolve the outstanding workbook items. Responses and original source documents are unchanged.
