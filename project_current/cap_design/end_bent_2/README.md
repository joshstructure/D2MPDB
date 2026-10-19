# End Bent 2 current cap design

The [19 October report](End%20Bent%202%20Cap%20Design%2010-19.html) and
[dated JSON](End%20Bent%202%20Cap%20Design%2010-19.json) are selected under D-051.
`selected_case.json` is byte-identical to the dated JSON.

The portable cap notebook loaded the previously selected case, applied the latest
`End Bent 2_Fixed.XML`, recalculated, and used its built-in report export.
Geometry, reinforcement, covers and design factors are unchanged. Imported forces
and analysis provenance are refreshed. The report's embedded case equals the saved
JSON, and its analysis SHA-256 equals the registered XML.

Check statuses are unchanged from the prior case evaluated with the same package:
6 FAIL entries (including the aggregate summary) and 47
pending/conditional entries remain. See the report's complete check register;
source selection does not close those findings.

The previous selected case is [archived](archive/2026-10-19-before-fbmp-rerun/selected_case.json).
The [17 October report](End%20Bent%202%20Cap%20Design%2010-17.html) and earlier
reports remain as historical snapshots. Calculation, source and preservation
checks are in the [receipt](../../coherence/evidence/2026-10-19-cap-rerun/source_receipt.json).
