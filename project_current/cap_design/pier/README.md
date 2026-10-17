# Pier current cap design

The [17 October 2026 report](Pier%20Cap%20Design%2010-17.html) is the selected
report (D-043). `selected_case.json` is the 12 October case selected under D-020,
extracted exactly from the supplied `Pier Cap Design 10-12.html`. The earlier case
is preserved under `archive/2026-10-10/`; earlier reports, including the 12 October
report, remain beside it as historical files.

The 10-17 report was regenerated from the unchanged `selected_case.json` with the
current `pier_cap` package (`scripts/export_project_cap_reports.py --date 10-17`),
to carry the corrected equation drop-down schematics (commit 5cce568). Inputs and
the case and formula hashes equal the 10-12 report. Its check register is not
identical, because the 12 October export predates two package fixes: it gains
nine PASS end-cover rows (fdf327c) and eight lower minimum-shear-steel ratios,
all PASS (9deb443). FAIL, PENDING and the governing check are unchanged. See the
[receipt](../../coherence/evidence/2026-10-17-cap-report-export/source_receipt.json).

The report embedded case and `selected_case.json` are exactly equal when parsed as
UTF-8. The current raw FBMP analysis hash differs from the registered `Pier_Fixed.XML`;
native rerun, anchorage and detailing remain unverified.
