# Pier wall (annular pile rings) current calculation

The [22 October report](Pier%20Wall%20Design%2010-22c.html) and [dated JSON](Pier%20Wall%20Design%2010-22c.json) are selected under D-084.
`selected_case.json` is byte-identical to the dated JSON. The [check register](Pier%20Wall%20Design%2010-22c%20checks.csv) and
[ring forces](Pier%20Wall%20Design%2010-22c%20ring%20forces.csv) come from the same case.

The ring_wall package (case SHA-256 `73184c71272af3a1`, package source SHA-256 `30d46e56fff658e2`, the engine of
`Pier_Wall_Design.ipynb`) evaluated its starting case: a 219 × 36 × 194.863 in wall on
4 pipe piles of 20 in at 60 in, 5 rows of 23/20.125 × 0.5 in
annular plates with two 5/16 in fillets, radial placement tolerance 3 in. The ring moment basis is
D-070 (pile-head compatibility moment; tolerance as pile-group redistribution); the pile stiffness lengths default to the
pier pile case (PILE-PIER-CASE), free length 92.4 in. No input was changed by hand.
The starting dimensions follow the CAD pier wall (D-075: 219 × 36 × 194.8625 in; free length to fixity 92.4 in) with the 1/2-in ring plate of D-078 (in the CAD model since D-079). The tension development length is LRFD 10th edition 5.10.8.2.1 (Eq. 5.10.8.2.1a-2 with the location, coating and confinement factors; the basic length of the first editions, 0.17 d_b (f_y / 1.97 f′c^¼)² without confinement credit, is withdrawn) and the end U return legs are 27 in (2 ft 3 in) against the 26-in Class B lap, in place of 72 in. Every other input is unchanged.

Results: 1 failed checks · limited scope. Wall rotation 1.547e-05 rad; pile-head moment 26.983 kip-in;
5.397 kip-in per ring; largest equivalent eccentricity 1.105 in at
R1-P1 against the 5.187 in kern; 0 rings without full contact. Largest
design ring load 14.944 kip; peak bearing 0.1964 ksi. Grid #5 at 11 in each way each face. Weld leg
5/16 in provided against a largest trial requirement of 4/16 in. The register holds 178 entries:
{'FAIL': 1, 'PASS': 177}. Failed: RING-GRID. Pending: 0.

Open scope items (SHARING, STIFFNESS, SCOPE, CONNECTION, BASIS) stay in every result; selection is not engineering acceptance. The Blockpad
edition of this report is journal module C017 (PierWallRings, task T028). Regenerate with
`scripts/export_project_pier_wall_report.py --date 10-22c`; the report embeds random figure ids, so a rerun gives new bytes.
`--check` regenerates the report from the saved case and compares. Calculation, source and preservation checks are in the
[receipt](../coherence/evidence/2026-10-22c-pier-wall/source_receipt.json).
