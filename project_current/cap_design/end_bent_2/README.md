# EB2 current cap design

The [17 October 2026 report](End%20Bent%202%20Cap%20Design%2010-17.html) is the
selected report (D-043). The supplied 14 October 2026 JSON case is selected under
D-027. `selected_case.json` is byte-identical to `End Bent 2 Cap Design 10-14.json`.
The earlier case is preserved under `archive/2026-10-12/`; earlier reports,
including the supplied 14 October report, remain beside it as historical files.

The 10-17 report was regenerated from the unchanged `selected_case.json` with the
current `pier_cap` package (`scripts/export_project_cap_reports.py --date 10-17`),
to carry the corrected equation drop-down schematics (commit 5cce568). Inputs,
the case and formula hashes, and all 248 check labels, statuses and D/C ratios equal
the 10-14 report. See the [receipt](../../coherence/evidence/2026-10-17-cap-report-export/source_receipt.json).

The 251 in design envelope includes the 235 in modeled cap and two 8 in cheek
webs. Concrete geometry is unchanged. The model contains 62 native cap bars,
including #6 transverse bars. Cheek steel coordination remains open in COH-024.

The report embedded case and supplied JSON are exactly equal when parsed as UTF-8.
Original supplied file bytes are preserved.
Required raw FBMP SHA-256: `56f78267b769a237ca0d0abfdb78464f6839c3a09033d27230c06c0a384b6a47`. This exact raw export was not supplied.
Structural, anchorage and fabrication acceptance remain separate from modeling.
