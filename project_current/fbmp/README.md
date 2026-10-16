# Current FBMP analysis sources

The user supplied these four XML exports on 10 October 2026. Files are preserved
byte-for-byte. Fixed and minimum-tip labels follow the supplied filenames; their
boundary conditions and controlling envelope have not been independently reviewed.

| Component | Fixed export | Minimum-tip export | Current cap-report relationship |
| --- | --- | --- | --- |
| Pier | [Pier_Fixed.XML](pier/Pier_Fixed.XML) | [Pier_MinTip.XML](pier/Pier_MinTip.XML) | Prior export; the 12 October report names `c8420fad…` |
| End Bent 1 | [End Bent 1_Fixed.XML](end_bents/End%20Bent%201_Fixed.XML) | [End Bent 1_Min_tip.XML](end_bents/End%20Bent%201_Min_tip.XML) | Prior export; the 14 October report names `23bb3afc…` |
| End Bent 2 | Not supplied | Not supplied | The 14 October report names `56f78267…` |

These exports matched the 10 October reports. The selected 12 and 14 October
reports were produced from exports that are not in this folder. Minimum-tip
variants are registered separately. The superseded pier minimum-tip export is
retained in [the archive](pier/archive/2026-10-09/Pier_MinTip.XML).

## Open items

- **COH-013 (awaiting source):** submit the exact exports behind the final
  selected cap reports. On 16 October the user supplied the report-matching
  pier export for comparison only and left the submittal open.
- **COH-028 (open):** rerun the final pier and end-bent FBMP analyses with
  pile heads at the current notebook cutoffs. The report-matching pier export
  puts them at EL 41.7717 ft. That is the cutoff from before the 12 October
  camber update (D-023), 0.081 in high.

| Support | Notebook pile cutoff (ft) | FBMP node Z (in) |
| --- | --- | --- |
| Pier | 41.764940 | -501.18 |
| End Bent 1 | 41.237692 | -494.85 |
| End Bent 2 | 41.249692 | -495.00 |

The measurements are in the
[pile-head record](../coherence/evidence/2026-10-16-fbmp-pile-heads/pile_heads.json).
Exact source identities from the original import are in
[the receipt](../coherence/evidence/2026-10-10-fbmp/source_receipt.json).
