# Pier cap cheek wall current calculation

The [22 October report](Pier%20Cheek%20Wall%20Design%2010-22.html) and [dated JSON](Pier%20Cheek%20Wall%20Design%2010-22.json) are selected under D-081.
`selected_case.json` is byte-identical to the dated JSON. The [check register](Pier%20Cheek%20Wall%20Design%2010-22%20checks.csv) comes from the same case.

The pier_cheek_wall package (case SHA-256 `a7ca0109a0c8fe58`, package revision `646e1010c4a05a92`, the engine of
`Pier_Cheek_Wall_Design.ipynb`) evaluated its starting case: the two D-059 pier cap cheek walls, 48 × 48 × 12 in
with the 0.75-in recessed panel, each with its centred mat of 6 #4 verticals at 10 in (developed 12 in
straight into the cap, D-061) and 6 #4 horizontals at 10 in, 2 in cover; wind directly on the walls per
LRFD 3.8.1.2.1 and 3.8.1.2.3b with the C001 journal values (V 130 / 80 / 70 mph, K_Z 1.0197 for Strength III,
G 0.85) and the C002 substructure drag coefficient 1.6; concrete 5.5 ksi and Grade 60 steel from the pier cap case.
No input was changed by hand (D-080 starting case).

Results: all numerical checks pass · 2 pending item(s) remain. Strength III pressure 0.0600 ksf; 0.96 kip transverse and
0.24 kip longitudinal per wall (1.92 / 0.48 kip for both). Cantilever moment at the
cap top 1.920 kip-ft, shear 0.960 kip; flexure 0.072 of capacity. The straight development of the
verticals (1.00; the 12-in LRFD floor once the excess-reinforcement factor applies, 12.28 in for full yield
without it) and the cover sit exactly at their limits. The register holds 20 entries: {'PASS': 18, 'PASS · PENDING INPUT': 2}. Failed:
none. Pending: temp_v, temp_h (the one-centred-mat shrinkage and temperature convention
awaits confirmation, as for the end bents under D-039).

The journal-owned inputs (C001 wind values) are literal in this case and live references in the journal edition; the case
names the journal revision whose values they equal (`sources` in the case). Selection is not engineering acceptance. The
Blockpad edition of this report is journal module C018 (PierCheekWalls). Regenerate with
`scripts/export_project_pier_cheek_wall_report.py --date 10-22 --decision D-081`; the report embeds its generation time and
random figure ids, so a rerun gives new bytes. `--check` regenerates the report from the saved case and compares. Calculation,
source and preservation checks are in the [receipt](../coherence/evidence/2026-10-22-pier-cheek-wall-selection/source_receipt.json).
