# Pier current pile design

The [19 October report](Pier%20Pile%20Design%2010-19.html) and [dated JSON](Pier%20Pile%20Design%2010-19.json) are selected under D-054.
`selected_case.json` is byte-identical to the dated JSON. The [check register](Pier%20Pile%20Design%2010-19%20checks.csv)
and [Pile Data Table](Pier%20Pile%20Data%20Table%2010-19.xlsx) come from the same case.

The pile analysis and design package (`pile_design`, revision `32d46a79afd4f631`, the engine of
`Pile_Design.ipynb`) evaluated its preset case for Pier: 20 in x 0.48 in steel pipe piles (noncomposite), no downdrag. The FB-MultiPier export is
`Pier_Fixed.XML` (PIER-XML, SHA-256 `bb73e6ada6cf35ebb80b512cee315075807fc8ccab7878406d81ff381ae40fe7`), the D-049 fixed run; the case's receipt records that it
matches the register. No input was changed by hand.

Results: all numerical checks pass. The largest structural demand/capacity ratio is 0.457; the largest
ratio of any check is 1.00 (the pile spacing check, exactly 3 diameters). Nominal Bearing Resistance
149.75 tons (150 in the Pile Data Table) for a Factored Design Load of
112.31 tons. The register holds 22 entries: 7 PASS (of which 6 rest on an unconfirmed prerequisite),
10 PENDING, 5 INFO and 0 FAIL.

The report counts 16 pending entries: 10 PENDING and 6 PASS entries that rest on an unconfirmed
prerequisite. Open prerequisites: environment classification, pile-to-cap connection, pipe steel grade, corrosion allowance, downdrag source documentation, FBMP export currency, minimum tip elevation, scour resistance and elevations, drivability. Other pending checks: Pile Data Table completeness (SDM 11.4).
The report's section 13 lists them. Selection is not engineering acceptance.

The Blockpad edition of this report is in the journal under task T015
(`pile_bpad/Pier Pile Design.bpad`). Regenerate with `scripts/export_project_pile_reports.py --date 10-19`; the report
embeds its generation time, so a rerun gives new bytes. `--check` regenerates the report from the saved case and compares.
Calculation, source and preservation checks are in the
[receipt](../../coherence/evidence/2026-10-19-pile-reports/source_receipt.json).
