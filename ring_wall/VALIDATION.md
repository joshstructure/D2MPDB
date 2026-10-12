# Verification record — 2026-10-12

The new ring-wall package was checked independently of the existing cap and
end-wall modules. No existing calculation engine was changed.

- **10 targeted tests passed** with Python 3.12.14 on Windows.
- Every code cell in `Ring_Supported_Wall_STM.ipynb` executed in order, including
  package extraction, inputs, analysis, report, spacing study and ZIP exports.
  The local run used the non-IPython display fallback; the Google-hosted Colab
  form/download UI was not directly exercised.
- Embedded package SHA-256:
  `6df3b600991af482afe57d9449ebd21b41681692a9f193a198fd8c4faec5d25d`.
  Every embedded source byte matched the maintained package in the notebook test.
- The standalone HTML report was opened in headless Chrome at 1350 × 1100.
  Title, minimum-steel section, STM elevation and check register were visually
  inspected. Two SVG diagrams and seven numbered sections rendered; no horizontal
  page overflow was detected. Default cover/grid failures were visible.
- Default gravity: 114.737109375 kip service; 143.421386719 kip factored.
  Ring reaction sum: 143.421386719 kip. Global force and moment residuals and
  arch-joint residuals were zero to the displayed precision.
- Default cage: #5 at 5 in each way each broad face, matching end U-bars.
  Required 0.648 in²/ft per face; provided 0.744. Governing spacing limit 5.171875 in.
- Manual #6 at 8 in passes minimum area but fails the assigned-band spacing
  limit; this boundary was tested.
- Default trial ring fit failures: 2-in end cover against 3-in input; −0.75-in
  clearance to the inner face-grid steel at pile-placement tolerance.
- Independent tests covered funicular force equivalence to beam moments, 30
  randomized whole-wall layouts, load and bearing-area scaling, numerical
  integration of the radial plate strip, invalid inputs and stale export rejection.

These checks verify the implemented calculation and its presentation. They do
not validate ring-row compatibility, the 3-D concrete/ring/pile connection,
anchorage, wall-end topology, or complete project code compliance. Those items
remain open in every report.
