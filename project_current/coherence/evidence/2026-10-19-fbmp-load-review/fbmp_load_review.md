# FBMP nodal-load review against the journal, 19 October 2026

Question (user): do the FB-MultiPier nodal loads need updating for the 19 October
geometry (notebook build e9b41b8eaf, D-053 backwall tops, D-055 model, D-059 pier
cheek walls), and therefore every report that reads the exports?

Decision (user, 19 October 2026): no change. The differences are negligible; the
end-bent bearing eccentricity and longitudinal-wind moments are carried by the
tie-back straps of the backwall design (D-057), not by the pile row. Recorded as
decision D-062.

## Exports read

| Export | SHA-256 | Loaded nodes |
| --- | --- | --- |
| `fbmp/end_bents/End Bent 1_Fixed.XML` (EB-XML, D-049) | c1a4afa138865b3f10cc968ce7daef767a4d96e8bc2ccf175c1a5ebd150d912d | DC/PL/WS at 15 and 34; DC 3.00 kip at 7 and 4 |
| `fbmp/end_bents/End Bent 2_Fixed.XML` (EB2-XML, D-049) | 3543df298b92593ce9bac14f9228ffacf5b0ce7e76b5e1d887ae228ef811a90e | identical to End Bent 1 |
| `fbmp/pier/Pier_Fixed.XML` (PIER-XML, D-049) | bb73e6ada6cf35ebb80b512cee315075807fc8ccab7878406d81ff381ae40fe7 | bearing loads L/R rows 1 and 2; DC 3.00 at 5/44, 4.05 at 33/16; WS at 49, 117, 83 |

Journal compared: revision 542fba20 (T018, natively recalculated) for the post-T014
values; the exports were entered from the pre-T014 tables (revision 033bf8ff and
earlier), which they equal to export precision.

## Export values against the journal entry tables

End bents, per bearing (nodes 15 and 34). Journal values in parentheses are the
T018 recalculated values; the exports equal the earlier cached values.

| Row | Export | Journal FBMPEndBent |
| --- | --- | --- |
| DC FZ | 92.07 kip | 92.069 (now 92.473) kip |
| PL FZ | 28.98 kip | 28.984 kip |
| WS1 FX / FY / FZ | 13.17 / -3.29 / -18.49 kip | 13.167 / -3.292 / -18.492 (now 13.169 / -18.494) |
| WS1 MY / MZ | -29.15 / -6.58 kip-ft | -29.146 / -3.292 per node (-6.584 sum) |
| WS1 MX | 0 | -31.750 / -22.504 kip-ft (bearing eccentricity + longitudinal-wind arm) |
| DC / PL MX | 0 | 23.017 / 7.246 kip-ft (3-in bearing eccentricity) |
| WS2, WS3 forces | match | match; MX again 0 in the export |

The transverse-axis moments (MX) in the journal table are absent from both end-bent
exports; nodes 15/34 sit at y = 0 on the centered pile line (cap case audit). They
are taken by the backwall straps per the user's decision.

Pier. Bearing rows: DC 92.07 / 89.97 kip, PL 28.98 / 28.32 kip, WS1 13.17 / 3.29 /
-18.49 kip with MX 27.13 and MY -29.15 kip-ft equal FE_DC_B1..B4, FE_PL_B1..B4 and the
FE_*_W1 rows. Pedestal weights 4.05 kip at nodes 33/16 equal 2 x FE_DCbelow 2.023 kip.
Direct wind: 4.37 kip transverse at node 49 and 2 x 10.51 kip longitudinal at nodes
117/83 equal FE_DirectT_W1 4.369 (now 4.378) kip and FE_DirectLBound_W1 20.933 (now
20.979) kip; WS3 1.24 and 2 x 2.99 kip equal the Service I values.

## Geometry changes since the exports were entered

| Change | Effect on the loads |
| --- | --- |
| T014 support drop with the notebook net cambers | Exposure height +0.43 in (K_Z +0.02%); pier face area 349.0 to 349.7 ft2 (direct wind +0.01 kip T, +0.05 kip L); cap elevations +0.036 ft (pile cutoffs 0.04 ft higher than the model) |
| T014 haunch volumes | Bearing DC +0.40 kip at End Bent 1 (92.069 to 92.473), -0.38 kip at End Bent 2, net +0.03 kip at the pier |
| End-bent cap 212 to 235 in with 8-in cheek webs (D-026/D-036) | Already in the exports: cap modeled as the 251-in envelope, first pile center 44.5 in from each end |
| D-059 pier cheek walls, 48 x 48 x 12 in at each cap end, 4 ft above the cap top | New exposed area outside the 230-in face: 2 x 16 ft2 transverse, 2 x 4 ft2 longitudinal at p_sub_III = 0.060 ksf: +1.92 kip transverse (direct-pier term 4.4 to 6.3 kip; about +3% of the 56.5 kip total transverse wind on the pier), +0.48 kip longitudinal (20.98 to 21.46 kip). Weight 2.34 kip each (31.26 ft3 total) within the 3.00 kip placeholders at nodes 5/44 |
| D-053 backwall tops, landings | Never modeled: backwall self-weight 77.77 ft3 x 0.150 = 11.67 kip per end bent; landing weights 111.5 / 88.6 ft3 (16.7 / 13.3 kip) with 50% bearing on the backwalls (D-016); the strap pile-head equilibrium force of the backwall report. The 3.00 kip DC loads at nodes 7 and 4 are the only unmodeled-concrete entries (one is on pile 4's head, BACKWALL_DESIGN.md) |
| End-bent direct wind | Never modeled (the journal entry table says it needs end-bent geometry). Fully exposed cap front and backwall faces would be about 60 + 78 ft2, about 8 kip longitudinal at Strength III; the closure slab and the deck end cover most of that strip and the MSE returns shield the ends |
| D-053 ramp slab thickening, D-055 and D-060/D-061 reinforcement, fence, deck | No load change on the bridge substructure |
| End Bent 2 export carrying the End Bent 1 bearing loads | 2.3% conservative against the journal's span-2 tributary (89.967 / 28.323 kip) |

## Disposition

- FBMP models and exports unchanged; cap reports (D-051), pile reports (D-054) and the
  backwall report (D-057) unchanged.
- Items that remain open elsewhere: COH-004 (model load comparison, this review is its
  evidence), COH-005 (wind and wall geometry), COH-013 (report-matching exports),
  COH-028 (rerun with current pile heads). The unmodeled backwall and landing gravity
  and the end-bent direct wind are judged negligible for the pile group by the user;
  the pier cheek-wall wind (+1.9 kip transverse) likewise.
- Method: loads parsed from the exports (NODAL_LOAD and BEARING_LOAD elements) and
  compared with the journal's FBMPEndBent, FBMPPier, FenceWind and C001 definitions;
  areas from the D-059 adoption summary (48-in height, top EL 47.765 ft) and the
  D-057 backwall case; pressures from FenceWind p_sub_III (q_III 0.0375 ksf x C_D 1.6).
