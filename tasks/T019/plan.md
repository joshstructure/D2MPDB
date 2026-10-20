# T019 — Level pier bearing-seat check

User request (20 October 2026): check whether the pier pedestals may be level and
add the calculation under Bearings and Support Details → Bearing Pads.

## Scope and dependencies

- Base journal: `542fba20a8efa3fe75c6210901d77b0a4e9bcfc8f075ef934c6e8a0add6ceff5`.
- Sole permitted component: `report:BearingDesign`. Preserve existing calculations,
  resources and all other components. Add a bounded subsection below Bearing Pads.
- Read live geometry, pad properties and profile from BridgeGeometry_2Beam;
  gravity checks already in BearingDesign; thermal inputs from BridgeMovement.
- Selected external sources: MCAD-S1/S2, the unchanged 12 October Mathcad
  worksheets; saved `Slope&Defl` matrix (region 202056), NetCamber and span results.
  Capture exact hashes and source units. No solver currency is implied.
- Conservative all-component dependency fallback. No prerequisite task.

## Engineering basis and outputs

FDOT 2026 SDG 6.5.1.D and FY 2026–27 SPI 400-510 pp. 1–2:
level seats are permitted when combined grade, camber and dead-load rotation
does not exceed 0.0125 rad. Standard pads allow 0.004-rad cyclic rotation,
opposite static rotation. Type F, G=110 psi, zero skew, 10 × 32 × 2.5625 in
is the existing selection. General grade-based detailing and the specific
combined-rotation allowance must both be explained.

Use the saved beam-end slopes, not a parabolic approximation from net midspan
camber. Positive slope rises toward increasing station. At the pier, reverse
the Span 1 left-end camber/deflection signs; retain Span 2 signs. Evaluate bare,
noncomposite and full-dead-load stages at 120 days; also 240-day full load.
Conservatively bound static rotations using release/240-day camber with zero/full
superimposed DL. Check service LL magnitude and direction at 120 and 240 days.
Beam self-weight is already included in saved camber. Do not add it twice.
Apply full-unit thermal movement and both full 120–240-day bottom shortenings
as a deliberately conservative longitudinal movement screen; no load factors.
Zero transverse beam tilt is a detailing assumption, distinct from deck crossfall.

Outputs: native unit-bearing inputs from cited saved external results, live
geometry/thermal references, signed stage rotations, static/cyclic ratios,
opposition checks, longitudinal thermal/creep screen and conditional conclusion.
Preserve unresolved wind/shear/uplift and external-analysis currency limitations.
No end-bent approval, pedestal geometry change, bearing capacity certification,
source solver rerun, tracker closure or unrelated design change.

## Acceptance and delivery

Verify exact source hashes/units/matrix positions; independently calculate all
reported rotations and movement; check formulas and native reference resolution.
Compare all original formula strings and protected components byte exactly.
Use native Blockpad recalculation if available, importing only authorized content
after authored-expression comparison. Optional native appearance/engineering
reviews remain honestly recorded; missing optional review is not a blocker.
Stop on stale dependencies, changed sources or structural/reference errors.
Promote through the BPAD workflow; record journal source disposition without
closing existing tracker issues. Refresh the existing public atlas under the
user's prior publication authorization and commit/push only completed task files.
