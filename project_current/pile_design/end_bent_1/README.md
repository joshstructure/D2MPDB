# End Bent 1 current pile design

The [21 October report](End%20Bent%201%20Pile%20Design%2010-21.html) and [dated JSON](End%20Bent%201%20Pile%20Design%2010-21.json) are selected under D-073.
`selected_case.json` is byte-identical to the dated JSON. The [check register](End%20Bent%201%20Pile%20Design%2010-21%20checks.csv)
and [Pile Data Table](End%20Bent%201%20Pile%20Data%20Table%2010-21.xlsx) come from the same case.

The pile analysis and design package (`pile_design`, revision `37cc843d9daa690b`, the engine of
`Pile_Design.ipynb`) evaluated its preset case for End Bent 1: 18 in square prestressed concrete piles (Standard Plans Index 455-018, 12 x 0.6 in strands) with 18 tons of downdrag per pile. The FB-MultiPier export is
`End Bent 1_Fixed.XML` (EB-XML, SHA-256 `c1a4afa138865b3f10cc968ce7daef767a4d96e8bc2ccf175c1a5ebd150d912d`), the D-049 fixed run; the case's receipt records that it
matches the register. No input was changed by hand.

Results: all numerical checks pass. The largest structural demand/capacity ratio is 0.550; the largest
ratio of any check is 1.00 (the pile spacing check, exactly 3 diameters). Nominal Bearing Resistance
89.92 tons (90 in the Pile Data Table) for a Factored Design Load of
49.44 tons. The register holds 26 entries: 12 PASS (of which 6 rest on an unconfirmed prerequisite),
9 PENDING, 5 INFO and 0 FAIL.

The report counts 15 pending entries: 9 PENDING and 6 PASS entries that rest on an unconfirmed
prerequisite. Open prerequisites: environment classification, pile-to-cap connection, downdrag source documentation, FBMP export currency, minimum tip elevation, scour resistance and elevations, drivability. Other pending checks: Pile-to-cap moment transfer (embedment below 48 in); Pile Data Table completeness (SDM 11.4).
The report's section 13 lists them. Selection is not engineering acceptance.

The Blockpad edition of this report is the journal module written by `scripts/build_pile_bpad.py`
(`pile_bpad/journal/`, standalone copy `pile_bpad/End Bent 1 Pile Design.bpad`). Regenerate with
`scripts/export_project_pile_reports.py --date 10-21 --support "End Bent 1" --decision D-073 --xml-decision D-049`; the report
embeds its generation time, so a rerun gives new bytes. `--check` regenerates the report from the saved case and compares.
Calculation, source and preservation checks are in the
[receipt](../../coherence/evidence/2026-10-21-pile-reports/source_receipt.json).
