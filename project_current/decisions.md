# Adopted decisions

Record a dated decision here when source authority or a project assumption
changes. Numerical values belong to their designated source, not a second input
database in this file. Coherence responses remain in the working spreadsheet.

| ID | Date | Decision | Basis and limits |
| --- | --- | --- | --- |
| D-001 | 2026-10-09 | Use `project_current` as the project entry point and source register. | User request in this chat. Existing journal/notebook locations remain the working copies. |
| D-002 | 2026-10-09 | Use the supplied Span 1 and Span 2 Mathcad sheets as the current sheets. | User explicitly selected both named files. This selects the sources; it does not assert a native rerun. |
| D-003 | 2026-10-09 | Keep pier reinforcement and force results in the separate cap report/case. Preserve C005 unchanged. | Recorded user direction and adopted T005 review; see [pier final review](coherence/evidence/pier_final_review.md). |
| D-004 | 2026-10-08 | Use the controlling End Bent 1 configuration for both end bents. | [Recorded responses](coherence/evidence/end_bent_received_responses.json), item 08. Verification that its actions bound the other end remains open. |
| D-005 | 2026-10-08 | Defer final backwall and cheek-wall geometry/quantities. | Recorded response item 02. Deferred quantities are not zero or complete. |
| D-006 | 2026-10-08 | Record field adjustment of interfering end-bent U-bar hooks. | Recorded response item 06. This does not close revised geometry/anchorage checks or decide the pier detail. |
| D-007 | 2026-10-08 | Treat Service III as not applicable to the current nonprestressed substructure. | Recorded response item 07. Other pending checks retain their individual status. |
| D-008 | 2026-10-10 | Select the supplied `Pier Cap Design 10-10.html` and `End Bent 1 Cap Design 10-10.html`, with their embedded cases, as current cap sources. | User request to update project_current with these files. Exact bytes preserved. Selection does not close reported failures or pending engineering checks. See [source update](coherence/evidence/2026-10-10/source_update.json). |
| D-009 | 2026-10-10 | Select exact-hash `Pier_Fixed.XML` as the pier analysis export. Update the missing end-bent XML identity to the new report requirement. | Pier XML hash matches the supplied report. Available End Bent 1.XML matches only the superseded report and is not substituted. |
| D-010 | 2026-10-10 | Reconcile the register and tracker to the already accepted T006 journal and its recorded human responses. | Journal and all receipt evidence hashes match. Close corrected bearing coordinates, historical-sketch labels and repaired reference links with evidence. Preserve field-bending direction and design/shop deferrals. No new BPAD edit or acceptance is performed. |
| D-011 | 2026-10-10 | Retain the registered CAP-TOOL fingerprint pending tool revision review. | Both GitHub and local notebook revisions differ from the register. Do not reset the expected hash to clear the finding. COH-021 records the remaining review. |
| D-012 | 2026-10-10 | Register all four user-supplied fixed/minimum-tip FBMP XMLs in project_current. Use the exact-hash fixed files for the existing report links and preserve minimum-tip files as separate current variants. | User explicitly supplied the newest XMLs. End Bent 1_Fixed.XML resolves the missing report-matching export; Pier_Fixed.XML is unchanged. The older pier minimum-tip export is archived. No report/case change, controlling envelope selection or new design acceptance. See [receipt](coherence/evidence/2026-10-10-fbmp/source_receipt.json). |
| D-013 | 2026-10-10 | Select `geometry/freecad/` as the authoritative home of the current editable FreeCAD bridge geometry and modeled quantities. | User requested adding the verified model to GitHub project_current as a source of truth. Native bytes preserved; controllers and opening macro included. Both cambers remain for later user update. Recorded detailing/coordination failures remain open. Adopted journal and selected cases retain their engineering authority; registration is not design acceptance. See [model receipt](geometry/freecad/manifest.json) and [scope](geometry/freecad/README.md). |

The current journal at setup matches the T005 acceptance receipt. That review
accepted geometry/source bookkeeping. Full analysis currency, convergence,
unresolved offsets, detailing and structural adequacy remain outside that scope.
See [acceptance at setup](coherence/evidence/journal_acceptance_at_setup.json).

The 10 October reconciliation verifies that the current journal matches T006,
whose acceptance remains limited to geometry/source bookkeeping, the user-directed
230-in wind width, historical labels and reference repairs. Its source notes
still identify the prior pier report (COH-022). New cap calculations remain in
the separate selected reports/cases and C005 remains unchanged.
