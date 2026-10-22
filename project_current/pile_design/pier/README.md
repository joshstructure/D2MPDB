# Pier current pile design

The [21 October report](Pier%20Pile%20Design%2010-21.html) and [dated JSON](Pier%20Pile%20Design%2010-21.json) are selected under D-073.
`selected_case.json` is byte-identical to the dated JSON. The [check register](Pier%20Pile%20Design%2010-21%20checks.csv)
and [Pile Data Table](Pier%20Pile%20Data%20Table%2010-21.xlsx) come from the same case.

The pile analysis and design package (`pile_design`, revision `37cc843d9daa690b`, the engine of
`Pile_Design.ipynb`) evaluated its preset case for Pier: 20 in x 0.48 in steel pipe piles (noncomposite), no downdrag. The FB-MultiPier export is
`Pier_Fixed.XML` (PIER-XML, SHA-256 `8be45bb889f5c955d0547ce6a538118bbce87600d40a65b094255e6b9b76e3b6`), the D-073 fixed run; the case's receipt records that it
matches the register. No input was changed by hand.
Source-backed confirmations in the preset case:
- `steel_grade`: FBMP pile material Fy 45 ksi equals the design Fy 45 ksi (Spec 962 Table 962-11, ASTM A252 Grade 3) in the registered export PIER-XML Pier_Fixed.XML (SHA-256 8be45bb889f5). The grade itself remains the design input.


Results: all numerical checks pass. The largest structural demand/capacity ratio is 0.457; the largest
ratio of any check is 1.00 (the pile spacing check, exactly 3 diameters). Nominal Bearing Resistance
149.75 tons (150 in the Pile Data Table) for a Factored Design Load of
112.31 tons. The register holds 22 entries: 7 PASS (of which 2 rest on an unconfirmed prerequisite),
9 PENDING, 5 INFO and 0 FAIL.

The report counts 11 pending entries: 9 PENDING and 2 PASS entries that rest on an unconfirmed
prerequisite. Open prerequisites: environment classification, pile-to-cap connection, corrosion allowance, downdrag source documentation, FBMP export currency, minimum tip elevation, scour resistance and elevations, drivability. Other pending checks: Pile Data Table completeness (SDM 11.4).
The report's section 13 lists them. Selection is not engineering acceptance.

The Blockpad edition of this report is the journal module written by `scripts/build_pile_bpad.py`
(`pile_bpad/journal/`, standalone copy `pile_bpad/Pier Pile Design.bpad`). Regenerate with
`scripts/export_project_pile_reports.py --date 10-21 --support "Pier" --decision D-073 --xml-decision D-073`; the report
embeds its generation time, so a rerun gives new bytes. `--check` regenerates the report from the saved case and compares.
Calculation, source and preservation checks are in the
[receipt](../../coherence/evidence/2026-10-21-pile-reports/source_receipt.json).
