# Pier wall (annular pile rings) current calculation

The [22 October report](Pier%20Wall%20Design%2010-22.html) and [dated JSON](Pier%20Wall%20Design%2010-22.json) are selected under D-075.
`selected_case.json` is byte-identical to the dated JSON. The [check register](Pier%20Wall%20Design%2010-22%20checks.csv) and
[ring forces](Pier%20Wall%20Design%2010-22%20ring%20forces.csv) come from the same case.

The ring_wall package (case SHA-256 `bcca7f0914179905`, package source SHA-256 `2b8da8c397160e68`, the engine of
`Pier_Wall_Design.ipynb`) evaluated its starting case: a 219 × 36 × 194.863 in wall on
4 pipe piles of 20 in at 60 in, 5 rows of 23/20.125 × 0.75 in
annular plates with two 5/16 in fillets, radial placement tolerance 3 in. The ring moment basis is
D-070 (pile-head compatibility moment; tolerance as pile-group redistribution); the pile stiffness lengths default to the
pier pile case (PILE-PIER-CASE), free length 92.4 in. No input was changed by hand.
The starting dimensions follow the CAD pier wall (D-075): 219 × 36 in, bottom 1 ft below terrain at EL 24.5264 ft, top at the cap bottom EL 40.76494 ft (194.8625 in high), 19.5 in from each wall end to the outer pile; the free length to fixity (92.4 in) is measured from that bottom (110.7 in sand depth to fixity below the pile-case ground EL 26.05 less the 18.3 in of wall below it). The journal gravity sheet row, C006 and this case agree with the CAD model and the drawings.

Results: 1 failed checks · limited scope. Wall rotation 1.547e-05 rad; pile-head moment 26.983 kip-in;
5.397 kip-in per ring; largest equivalent eccentricity 1.105 in at
R1-P1 against the 5.187 in kern; 0 rings without full contact. Largest
design ring load 14.944 kip; peak bearing 0.1964 ksi. Grid #5 at 11 in each way each face. Weld leg
5/16 in provided against a largest trial requirement of 5/16 in. The register holds 178 entries:
{'FAIL': 1, 'PASS': 177}. Failed: RING-GRID. Pending: 0.

Open scope items (SHARING, STIFFNESS, SCOPE, CONNECTION, BASIS) stay in every result; selection is not engineering acceptance. The Blockpad
edition of this report is journal module C017 (PierWallRings, task T028). Regenerate with
`scripts/export_project_pier_wall_report.py --date 10-22`; the report embeds random figure ids, so a rerun gives new bytes.
`--check` regenerates the report from the saved case and compares. Calculation, source and preservation checks are in the
[receipt](../coherence/evidence/2026-10-22-pier-wall/source_receipt.json).
