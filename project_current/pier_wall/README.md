# Pier wall (annular pile rings) current calculation

The [21 October report](Pier%20Wall%20Design%2010-21.html) and [dated JSON](Pier%20Wall%20Design%2010-21.json) are selected under D-071.
`selected_case.json` is byte-identical to the dated JSON. The [check register](Pier%20Wall%20Design%2010-21%20checks.csv) and
[ring forces](Pier%20Wall%20Design%2010-21%20ring%20forces.csv) come from the same case.

The ring_wall package (case SHA-256 `5778a133d8f058b0`, package source SHA-256 `1c7f2db62e90c2bf`, the engine of
`Pier_Wall_Design.ipynb`) evaluated its starting case: a 213 × 36 × 172.375 in wall on
4 pipe piles of 20 in at 60 in, 5 rows of 23/20.125 × 0.75 in
annular plates with two 5/16 in fillets, radial placement tolerance 3 in. The ring moment basis is
D-070 (pile-head compatibility moment; tolerance as pile-group redistribution); the pile stiffness lengths default to the
pier pile case (PILE-PIER-CASE). No input was changed by hand.

Results: 2 failed checks · limited scope. Wall rotation 1.414e-05 rad; pile-head moment 17.945 kip-in;
3.589 kip-in per ring; largest equivalent eccentricity 0.779 in at
R1-P1 against the 5.187 in kern; 0 rings without full contact. Largest
design ring load 9.603 kip; peak bearing 0.1265 ksi. Grid #5 at 11 in each way each face. Weld leg
5/16 in provided against a largest trial requirement of 5/16 in. The register holds 178 entries:
{'FAIL': 2, 'PASS': 176}. Failed: RING-END, RING-GRID. Pending: 0.

Open scope items (SHARING, STIFFNESS, SCOPE, CONNECTION, BASIS) stay in every result; selection is not engineering acceptance. The Blockpad
edition of this report is journal module C017 (PierWallRings, task T028). Regenerate with
`scripts/export_project_pier_wall_report.py --date 10-21`; the report embeds random figure ids, so a rerun gives new bytes.
`--check` regenerates the report from the saved case and compares. Calculation, source and preservation checks are in the
[receipt](../coherence/evidence/2026-10-21-pier-wall/source_receipt.json).
