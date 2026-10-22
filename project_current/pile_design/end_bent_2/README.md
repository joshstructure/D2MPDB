# End Bent 2 current pile design

The [22 October report](End%20Bent%202%20Pile%20Design%2010-22.html) and [dated JSON](End%20Bent%202%20Pile%20Design%2010-22.json) are selected under D-077.
`selected_case.json` is byte-identical to the dated JSON. The [check register](End%20Bent%202%20Pile%20Design%2010-22%20checks.csv)
and [Pile Data Table](End%20Bent%202%20Pile%20Data%20Table%2010-22.xlsx) come from the same case.

The pile analysis and design package (`pile_design`, revision `0b518b6fa963e083`, the engine of
`Pile_Design.ipynb`) evaluated its preset case for End Bent 2: 18 in square prestressed concrete piles (Standard Plans Index 455-018, 12 x 0.6 in strands) with 18 tons of downdrag per pile. The FB-MultiPier export is
`End Bent 2_Fixed.XML` (EB2-XML, SHA-256 `3543df298b92593ce9bac14f9228ffacf5b0ce7e76b5e1d887ae228ef811a90e`), the D-049 fixed run; the case's receipt records that it
matches the register. No input was changed by hand.

Results: all numerical checks pass. The largest structural demand/capacity ratio is 0.557; the largest
ratio of any check is 1.00 (the pile spacing check, exactly 3 diameters). Nominal Bearing Resistance
89.74 tons (90 in the Pile Data Table) for a Factored Design Load of
49.30 tons. The register holds 26 entries: 12 PASS (of which 6 rest on an unconfirmed prerequisite),
9 PENDING, 5 INFO and 0 FAIL.

The report counts 15 pending entries: 9 PENDING and 6 PASS entries that rest on an unconfirmed
prerequisite. Open prerequisites: environment classification, pile-to-cap connection, downdrag source documentation, FBMP export currency, minimum tip elevation, scour resistance and elevations, drivability. Other pending checks: Pile-to-cap moment transfer (embedment below 48 in); Pile Data Table completeness (SDM 11.4).
The report's section 13 lists them. Selection is not engineering acceptance.

The Blockpad edition of this report is the journal module written by `scripts/build_pile_bpad.py`
(`pile_bpad/journal/`, standalone copy `pile_bpad/End Bent 2 Pile Design.bpad`). Regenerate with
`scripts/export_project_pile_reports.py --date 10-22 --support "End Bent 2" --decision D-077 --xml-decision D-049`; the report
embeds its generation time, so a rerun gives new bytes. `--check` regenerates the report from the saved case and compares.
Calculation, source and preservation checks are in the
[receipt](../../coherence/evidence/2026-10-22-pile-reports/source_receipt.json).
