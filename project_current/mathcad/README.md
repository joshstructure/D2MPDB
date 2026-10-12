# Mathcad

The two beam runs supplied on **12 October 2026** are selected as current by
D-022. Their bytes are unchanged from the supplied files. The previous selected
worksheets are preserved under [archive/2026-10-09/](archive/2026-10-09/).
Exact old/new fingerprints and the bounded comparison are in the
[beam source receipt](../coherence/evidence/2026-10-12-beams/source_receipt.json).

## Saved worksheet values

These values were read from the worksheets' saved results with their stored
units. No native Mathcad recalculation was performed.

| Quantity | Span 1 previous | Span 1 current | Span 2 previous | Span 2 current |
| --- | ---: | ---: | ---: | ---: |
| Beam length, `L_beam` (ft) | 107.350 | 106.975 | 104.900 | 104.525 |
| Beam-end bearing distance (in) | 8 | 9 | 8 | 9 |
| Bearing span, `Span_beam` (ft) | 106.016667 | 105.475000 | 103.566667 | 103.025000 |
| Saved 120-day `NetCamber` (in) | 0.030455439 | 0.124592744 | 0.483095417 | 0.567171463 |
| Pedestrian load, `q_PL` (psf) | 90 | 90 | 90 | 90 |

## Downstream review

Under the subsequent D-023 user follow-up, the geometry notebook and
`bridge_geometry/camber_sources.json` now use these saved cambers and exact
worksheet fingerprints. Its existing physical beam lengths and 9-in bearing
setbacks match the new worksheets. The notebook and saved CAD model pass the
[geometry verification](../geometry/freecad/evidence/2026-10-12-cambers/update-summary.json).
Existing COH-017 and COH-018 retain the broader native calculation, load and
journal comparison scope; this geometry update does not close those items.

The backwall source record also retains the prior Span 1 fingerprint. Its cited
pedestrian load is unchanged at 90 psf, but the source record and embedded
notebook provenance need review during a calculation update. This source receipt
does not rerun the journal, backwall notebook or design reports.

The worksheets still name `PedestrianBridge2Beam_Span1.dat` and
`PedestrianBridge2Beam_Span2.dat`. Neither file exists at its registered repository
path, and no PSBeam package is selected in the register. The tracker retains the
user's existing Closed / Added responses for COH-015 and COH-016 unchanged;
those responses do not supply a matching file fingerprint or native run record.
Native recalculation and the full project geometry/load comparison remain open.
