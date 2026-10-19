# Current FBMP analysis sources

The three fixed-run XML exports supplied on **19 October 2026** are selected
under D-049 and preserved byte-for-byte. The two minimum-tip variants remain
the 10 October sources.

| Component | Current fixed export | Minimum-tip export | Selected cap-report relationship |
| --- | --- | --- | --- |
| Pier | [Pier_Fixed.XML](pier/Pier_Fixed.XML) | [Pier_MinTip.XML](pier/Pier_MinTip.XML) | Exact match to the 19 October report and saved case |
| End Bent 1 | [End Bent 1_Fixed.XML](end_bents/End%20Bent%201_Fixed.XML) | [End Bent 1_Min_tip.XML](end_bents/End%20Bent%201_Min_tip.XML) | Exact match to the 19 October report and saved case |
| End Bent 2 | [End Bent 2_Fixed.XML](end_bents/End%20Bent%202_Fixed.XML) | Not supplied | Exact match to the 19 October report and saved case |

The cap notebook was subsequently rerun with all three fixed XMLs under D-051.
The selected 19 October reports/cases now match these sources exactly. Existing
detailing findings, backwall input reconciliation and minimum-tip review remain.
See the [cap rerun receipt](../coherence/evidence/2026-10-19-cap-rerun/source_receipt.json).
Fixed/minimum-tip labels follow the supplied filenames.

## Pile-head comparison

The following compares XML node coordinates with the notebook cutoff targets
recorded on 16 October. Elevation in feet is minus node Z in inches divided by 12.

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
records exact hashes, report comparisons, archived sources and verification.
The prior fixed exports are retained in the [pier archive](pier/archive/2026-10-10/Pier_Fixed.XML)
and [End Bent 1 archive](end_bents/archive/2026-10-10/End%20Bent%201_Fixed.XML).
The older pier minimum-tip export remains in its [9 October archive](pier/archive/2026-10-09/Pier_MinTip.XML).
