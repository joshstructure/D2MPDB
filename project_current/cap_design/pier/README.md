# Pier current cap design

The [21 October report](Pier%20Cap%20Design%2010-21.html) and [dated JSON](Pier%20Cap%20Design%2010-21.json) are selected under D-073.
`selected_case.json` is byte-identical to the dated JSON.

`scripts/apply_fbmp_to_cap_case.py` loaded the previously selected case, applied the registered
`Pier_Fixed.XML` (PIER-XML, SHA-256 `8be45bb889f5c955d0547ce6a538118bbce87600d40a65b094255e6b9b76e3b6`) with the cap package's XML importer,
recalculated and wrote the report. Geometry, reinforcement, covers and design factors are unchanged
(geometry and reinforcement preserved: True). Imported force envelopes that changed: none.
Analysis provenance is refreshed; the report's embedded case equals the saved JSON and its analysis SHA-256 equals the registered XML.

Check statuses: 0 register entries changed ratio or status (0 status changes).
2 FAIL entries (including the aggregate summary) and 67 pending/conditional entries remain.
See the report's complete check register; source selection does not close those findings.

The previous selected case is [archived](archive/2026-10-21-before-fbmp-rerun/selected_case.json).
Earlier reports remain as historical snapshots. Calculation, source and preservation checks are in the
[receipt](../../coherence/evidence/2026-10-21-cap-rerun/source_receipt.json).
