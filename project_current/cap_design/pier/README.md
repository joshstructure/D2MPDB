# Pier current cap design

The [22 October report](Pier%20Cap%20Design%2010-22.html) and [dated JSON](Pier%20Cap%20Design%2010-22.json) are selected under D-077.
`selected_case.json` is byte-identical to the dated JSON.

`scripts/apply_fbmp_to_cap_case.py` loaded the previously selected case, applied the registered
`Pier_Fixed.XML` (PIER-XML, SHA-256 `420e614aa8b9784b5f0e8160689f90d7480fec7dc3541ee7c687c5eadfd355e6`) with the cap package's XML importer,
recalculated and wrote the report. Geometry, reinforcement, covers and design factors are unchanged
(geometry and reinforcement preserved: True). Imported force envelopes that changed: Mu_N 39.12 to 40.32, Mu_P 158.98 to 152.68, Mu_B 365.84 to 361.01, Vu_G 218.96 to 220.46, Vu_L 218.96 to 220.46, Tu 26.55 to 26.15, MI_N 21.91 to 26.31, MI_P 121.97 to 118.04, MI_B 312.22 to 309.28.
Analysis provenance is refreshed; the report's embedded case equals the saved JSON and its analysis SHA-256 equals the registered XML.

Check statuses: 62 register entries changed ratio or status (0 status changes).
2 FAIL entries (including the aggregate summary) and 67 pending/conditional entries remain.
See the report's complete check register; source selection does not close those findings.

The previous selected case is [archived](archive/2026-10-22-before-fbmp-rerun/selected_case.json).
Earlier reports remain as historical snapshots. Calculation, source and preservation checks are in the
[receipt](../../coherence/evidence/2026-10-22-cap-rerun/source_receipt.json).
