# Verification record — 2026-10-12

The completed gravity calculation was retained and extended with a live notebook
workbench and the broad-face cone-transfer trial. Cap and end-wall engines were
not changed.

- **21 targeted tests passed** with Python 3.12.14 on Windows, using
  `python -m unittest discover -s tests -p "test_ring_wall*.py" -v`.
- Both notebook code cells executed in order. Tests verify no exports on startup,
  exact embedded-source bytes, current-result export gates, case preservation on
  rerun, separate export folders and preservation of earlier saved downloads.
- Embedded package SHA-256:
  `1df50430b7a8b931feadad51488166001c46698f0de7b24f5d92d12377c5fc65`.
- The final notebook build also executed in a real local JupyterLab browser with
  ipywidgets 8.1.9 and Plotly 6.9.0. Live geometry, the reaction heatmap and table,
  and the 3-D cone rendered. Browser interactions verified row filtering, a typed
  cone-slope edit, stale-result clearing, Recalc, and the optional report button.
  New exports were disabled after edits while the saved-report button remained
  enabled. A report was generated from the current default case. The displayed
  face rise changed from 4.333 in to 4.062 in at 1.6 H:1 V (unrounded: 4.0625 in).
- Google-hosted Colab UI/download behavior was not directly exercised. Its setup
  follows the cap notebook's pinned ipywidgets 7.7.1 / Plotly 5.24.1 runtime and
  custom-widget-manager registration. Local browser checks do not substitute
  for a hosted Colab check.
- Default gravity: 114.737109375 kip service; 143.421386719 kip factored.
  Ring reaction sum: 143.421386719 kip. Global force and moment residuals and
  arch-joint residuals were zero to the displayed precision.
- Default cage: #5 at 5 in each way each broad face, matching end U-bars.
  Required 0.648 in²/ft per face; provided 0.744. Governing spacing limit 5.171875 in.
- Manual #6 at 8 in passes minimum area but fails the assigned-band spacing
  limit; this boundary was tested.
- The default has **six failed checks**: RING-END (2-in available end cover
  against 3 in), RING-GRID (−0.75-in clearance at pile tolerance), and R1-FIT
  through R4-FIT (raised arches exceed their assigned bands). **Nine design items
  remain open**, including the added cone-transfer connection check.
- Independent tests covered funicular force equivalence to beam moments, 30
  randomized whole-wall layouts, load and bearing-area scaling, numerical
  integration of the radial plate strip, invalid inputs and stale export rejection.
- Widget tests cover live plot data, changed row/pile counts, filters, case
  loading and failed-calculation handling.
- Cone tests check the 1.5 H:1 V face intersection, tolerance reaches, wall-end
  truncation, unchanged gravity/reactions/span, shifted arch-fit elevations,
  symmetric transfer-link equilibrium and additional transverse-tie demand.
  Saved cases without cone fields retain the original ring-level model.
- Default first face contact is 4.333333 in above the ring; near/far reaches at
  ±3-in transverse pile tolerance are 2.333333 / 6.333333 in. The outer-pile
  envelope reaches the wall end first, at 3.333333 in above the ring.

The 1.5 H:1 V envelope is adapted from the ACI CCD breakout sketch. Its use at an
annular ring is an explicit geometric extrapolation, not verified breakout
resistance or a compression-spread provision. Free-surface intersection creates
no external support or span reduction. The trial face references need finite
interior nodes with cover, and the transverse ties need routing and anchorage
around the hollow pipe. These tests do not validate that connection, row
compatibility, wall-end topology, anchorage, or complete project code compliance.
