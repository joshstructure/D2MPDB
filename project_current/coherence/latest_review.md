# Latest project coherence review

Checked at 2026-10-22T15:39:58.776115+00:00. **14 outstanding items remain.**

The [workbook](Coherence_Tracker.xlsx) owns item status and responses. This report is a generated view.
The initial findings were carried forward from the latest adopted pier/end-bent reviews plus source-inventory gaps.
Previously resolved decisions were excluded. This run did not perform native calculations or a complete engineering review.

Registered sources: 43. Tracker items: 28.
Automatic results: 9 error, 68 match, 4 missing, 9 review.

## Files and relationships needing attention

| Check | Status | Finding |
| --- | --- | --- |
| SOURCE:MCAD-DAT1 | MISSING | Registered file is absent. |
| SOURCE:PSB-S1 | MISSING | No source file has been selected. |
| SOURCE:MCAD-DAT2 | MISSING | Registered file is absent. |
| SOURCE:PSB-S2 | MISSING | No source file has been selected. |
| DEP:MCAD-S1:MCAD-DAT1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S1:PSB-S1 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:MCAD-DAT2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| DEP:MCAD-S2:PSB-S2 | REVIEW | A registered dependency is missing, changed or awaiting adoption. Review the consumer. |
| TRACKER:10 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:11 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:15 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:16 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:19 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:20 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:23 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:24 | ERROR | Closed / not-applicable item requires resolution evidence. |
| TRACKER:28 | ERROR | Closed / not-applicable item requires resolution evidence. |
| ASSUMPTION:A-003 | REVIEW | Basis moved in the register (JOURNAL); re-judge the entry and record new basis hashes. |
| ASSUMPTION:A-005 | REVIEW | Basis moved in the register (JOURNAL); re-judge the entry and record new basis hashes. |
| ASSUMPTION:A-008 | REVIEW | Basis moved in the register (JOURNAL); re-judge the entry and record new basis hashes. |
| ASSUMPTION:A-010 | REVIEW | Basis moved in the register (JOURNAL); re-judge the entry and record new basis hashes. |
| ASSUMPTION:A-011 | REVIEW | Basis moved in the register (PILE-EB1-CASE, PILE-EB2-CASE, PILE-PIER-CASE); re-judge the entry and record new basis hashes. |

## Outstanding items

| ID | Status | Subject | Next action |
| --- | --- | --- | --- |
| COH-004 | Open | Complete model load comparison | Compare the exact current model loading with T006 and document needed reruns and convergence evidence. |
| COH-005 | Open | Wind and wall geometry | Establish remaining wall/fin geometry and compare current model wind loads with the T006 basis. |
| COH-010 | Deferred | Backwall and cheek-wall quantities | Supply final wall details, then reconcile quantities and dead loads. |
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

## Assumptions and gaps

The [register](assumptions.json) records 13 entries: **3 open** (pending disposition) and **5 stale** (basis moved in the source register since the judgment).
Open and stale entries are listed below; accepted entries stay in the register and in the design atlas. This check never re-judges an entry.

| ID | Kind | State | Statement | Magnitude | Decision |
| --- | --- | --- | --- | --- | --- |
| A-010 | judgment | stale: JOURNAL / open | The MSE exclusion side walls re-extracted from the D-055 model sit at the 24-in criterion within 0.0002 in, so two of four side-wall rows read SHORTFALL by their last digits (T016). Re-judged 22 October 2026 against the D-079 CAD model (pier wall ring plates 1/2 in; the MSE wall lines and the end-bent pile rows are unchanged, so the 114-in offsets and the last-digit shortfall stand). Re-judged 22 October 2026 against the D-083 CAD model (pier wall SDM bar marks 5G1/5G2/5G3 written on the 124 wall bars; naming only, no geometry, quantity or exposed face changed, so the judgment stands). | 0.0002 in | pending D-056 2026-10-19 |
| A-011 | gap | stale: PILE-EB1-CASE, PILE-EB2-CASE, PILE-PIER-CASE / open | The 19 October pile design reports carry pending prerequisites: the downdrag source documentation, scour, the minimum tip elevation and the pile-to-cap connection (with pipe steel grade, corrosion allowance, drivability and environment classification). | not sized | pending D-054 2026-10-19 |
| A-003 | judgment | stale: JOURNAL | The end-bent bearing eccentricity and longitudinal-wind moments about the transverse axis (MX = 0 in both end-bent exports; 23.0 kip-ft DC, 7.2 kip-ft PL and up to 31.8 kip-ft wind per bearing in the journal entry table) are carried by the backwall tie-back straps of the backwall design (D-057), not by the pile row. | 31.8 kip*ft | accepted-negligible D-062 2026-10-19 |
| A-005 | gap | stale: JOURNAL | End-bent direct wind is not modeled; the journal entry table notes it needs end-bent geometry. A fully exposed cap front and backwall face (about 60 + 78 ft2) would give about 8 kip longitudinal at Strength III, but the closure slab and deck end cover most of that strip and the MSE returns shield the ends. | 8 kip | accepted-negligible D-062 2026-10-19 |
| A-008 | gap | stale: JOURNAL | The End Bent 2 export carries the End Bent 1 bearing loads (92.07 / 28.98 kip) instead of the journal's span-2 tributary values (89.967 / 28.323 kip), which is 2.3% conservative. | 2.3 % | accepted-negligible D-062 2026-10-19 |
| A-012 | assumption | open | The pier FBMP export (Pier_Fixed.XML, D-077, 22 October 2026) models the pier wall as extra members hung between pile nodes: four vertical 36 x 60 in concrete members (library section 5, 150 pcf), one per pile, from pile point 2 (EL 40.20, 18.9 in below the cap axis) to pile point 11 at the soil surface (EL 26.05), 169.8 in long, 31.83 kip each (127.3 kip in all), plus 30 weightless 36 x 20.52 in ties (section 4, 1 pcf) between adjacent piles at ten levels; direct wind is applied at the mid-height wall nodes 49, 83 and 117. The 21 October export (D-073) had the members running to pile point 13 (EL 19.72, 184.4 kip), 6 ft below the soil surface, because they had followed earlier soil elevation changes; the user reran the model to correct them. Against the CAD wall (219 x 36 x 194.86 in, EL 24.53 to 40.76, 133.4 kip): the model wall is 240 in long, 6.1 kip lighter (4.6%), its top 6.8 in below the cap bottom and its bottom 18.3 in above the CAD wall bottom. Traced down each pile the axial drops below the head (the wall members take the load) and returns at point 11 with the wall weight; the pier pile structural checks govern there (Pu 252.0 kip, Strength III, pile 4, element 11), while the Factored Design Load of the Pile Data Table is the pile-head compression (226.1 kip, Strength I), which excludes the wall weight that enters below the head (the pile-head sums balance only the applied loads plus the cap self-weight). Re-judged 22 October 2026 against the D-078 ring wall case (ring plate 1/2 in; wall, forces and free length unchanged) and the T037 journal. Re-judged the same day against the D-079 CAD model (ring plates 1/2 in; the CAD wall concrete, 133.4 kip, is unchanged, and the ring steel, 276 lb in place of 414 lb, is in neither weight, so the 6.1 kip gap stands). Re-judged 22 October 2026 against the T039 journal (C018 Pier Cap Cheek Wall Design added after C017 under D-081; every other module byte-identical to the T037 revision). Re-judged 22 October 2026 against the T040 journal (C006 Pier Wall, Hairpins and Fin Plates withdrawn under D-082; C017 regenerated with identical values; every other module byte-identical to the T039 revision). Re-judged 22 October 2026 against the D-083 CAD model (pier wall SDM bar marks 5G1/5G2/5G3 written on the 124 wall bars; naming only, no geometry, quantity or exposed face changed, so the judgment stands). | 6.1 kip | pending D-075 2026-10-22 |

## Verified scope

- Present-source identity is compared with the source register. Only registered notebook CRLF/LF endings are normalized; native/report files use exact bytes.
- Current journal identity is compared with its existing acceptance receipt; that receipt keeps its original scope.
- Saved cap cases are compared with their report JSON, and raw XML with the analysis fingerprint.
- Selected notebook cap widths, depths, pile counts/sizes/spacings, embedment and lengths are compared with saved cases.
- Mathcad XML readability is checked. Its formulas and external inputs are not recalculated.
- Tracker IDs, statuses, required descriptions and closure evidence are checked.
- Assumptions-register entries are validated (stable IDs, kinds, dispositions, registered basis sources, tracker references) and their recorded basis hashes are compared with the current register. A moved basis is reported for re-judgment, never re-judged here.
- Detailed results and exact source/tracker fingerprints are in [machine_checks.json](machine_checks.json).

Automatic matches do not resolve the outstanding workbook items. Responses and original source documents are unchanged.
