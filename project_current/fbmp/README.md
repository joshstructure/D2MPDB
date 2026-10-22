# Current FBMP analysis sources

The pier fixed-run export supplied on **21 October 2026** is selected under D-073;
the two end-bent fixed exports supplied on **19 October 2026** remain selected under
D-049. All are preserved byte-for-byte. The two minimum-tip variants remain the
10 October sources.

| Component | Current fixed export | Minimum-tip export | Selected cap-report relationship |
| --- | --- | --- | --- |
| Pier | [Pier_Fixed.XML](pier/Pier_Fixed.XML) (21 October, D-073) | [Pier_MinTip.XML](pier/Pier_MinTip.XML) | Exact match to the 21 October report and saved case |
| End Bent 1 | [End Bent 1_Fixed.XML](end_bents/End%20Bent%201_Fixed.XML) | [End Bent 1_Min_tip.XML](end_bents/End%20Bent%201_Min_tip.XML) | Exact match to the 19 October report and saved case |
| End Bent 2 | [End Bent 2_Fixed.XML](end_bents/End%20Bent%202_Fixed.XML) | Not supplied | Exact match to the 19 October report and saved case |

## 21 October pier rerun (D-073)

The 21 October pier export differs from the 19 October one in the pipe pile
material only: the shell steel is ASTM A252 Grade 3, Fy 45 ksi, in place of
60 ksi (FY_SHELL and its stress-strain curve). Nodal loads, geometry, pile
section, soil and the four load combinations are identical; the cap member
forces differ only by solver noise below 1e-7 kip; the export's pile failure
ratios, interaction diagram and output summary follow the 45 ksi material.

The pier cap case was rerun from it with `scripts/apply_fbmp_to_cap_case.py`
(every force envelope, ratio and status unchanged; analysis identity refreshed)
and the pier pile case with `scripts/export_project_pile_reports.py` (demands
unchanged; the `steel_grade` prerequisite is now source-backed because the
model Fy equals the 45 ksi design Fy). See the
[21 October receipt](../coherence/evidence/2026-10-21-fbmp/source_receipt.json),
the [cap rerun receipt](../coherence/evidence/2026-10-21-cap-rerun/source_receipt.json)
and the [pile export receipt](../coherence/evidence/2026-10-21-pile-reports/source_receipt.json).
The 19 October pier export is retained in the
[pier archive](pier/archive/2026-10-19/Pier_Fixed.XML).

## 19 October selection (D-049, D-051)

The cap notebook was rerun with all three 19 October fixed XMLs under D-051.
Existing detailing findings, backwall input reconciliation and minimum-tip
review remain. See the
[cap rerun receipt](../coherence/evidence/2026-10-19-cap-rerun/source_receipt.json).
Fixed/minimum-tip labels follow the supplied filenames.

## Pile-head comparison

The following compares XML node coordinates with the notebook cutoff targets
recorded on 16 October. Elevation in feet is minus node Z in inches divided by 12.
The 21 October pier export keeps the same node coordinates.

| Support | Supplied node Z (in) | Recorded target Z (in) | Elevation above recorded cutoff (in) |
| --- | ---: | ---: | ---: |
| Pier | -501.26 | -501.18 | 0.080720 |
| End Bent 1 | -494.85 | -494.85 | -0.002304 |
| End Bent 2 | -495.08 | -495.00 | 0.083696 |

End Bent 1 matches the target at the XML's printed precision. Pier and End Bent 2
remain about 0.08 in above the recorded cutoffs. COH-013 and COH-028 remain open
in the tracker; their existing responses and statuses are preserved. Native run
records, remaining pile/soil inputs and downstream calculation updates still
require review.

The [19 October receipt](../coherence/evidence/2026-10-19-fbmp/source_receipt.json)
records the hashes, report comparisons, archived sources and verification of that
selection. The earlier fixed exports are retained in the
[pier archive](pier/archive/2026-10-10/Pier_Fixed.XML)
and [End Bent 1 archive](end_bents/archive/2026-10-10/End%20Bent%201_Fixed.XML).
The older pier minimum-tip export remains in its [9 October archive](pier/archive/2026-10-09/Pier_MinTip.XML).
