# T008 — MSE wall exclusion boxes

User-authorized work: reverse the prior centered-strap clearance check to solve
minimum wall setback from pile faces, show dimensioned exclusion boxes for both
end bents in one native report, and integrate that report into the current journal.

Topology scope: append report:MSEWallExclusion. Edit report:PedBridge only to add
an index link. All other components, resources and the document shell are protected.
The workflow now supports explicitly registered appended modules; use its normal
prepare/check/assemble/promote path. Watch every existing component as a dependency.

Read dependencies: BridgeGeometry_2Beam owns end-bent square pile size, spacing,
pile count, pile tolerance, cap length and cap width. Reuse those live references.
MSE back-face coordinates and bridge frame angle come from the existing registered
FreeCAD snapshot in mse_strap_check/layout_snapshot.json, with model fingerprint.
The source model and external analysis outputs are not modified. Current journal
base SHA-256: a78dbced339445d0e7b2403e069b1da4dc12db890516fd997f757dc9a05a83fa.

Engineering model: straight finite-width strap starts at the perpendicular
projection of a pile center on the back of facing. Maximum ordinary plan skew is
15 degrees (FDOT 2026 SDG 3.13.2.K.8). A conservative square plan envelope covers
the slight source rotation and the journal's 3-inch coordinate placement allowance.
Use the allowance in both normal and tangential directions. Strip width 2 inches
and extra required edge clearance 0 inches remain explicit trial inputs.

Let h be nominal projected pile half-width, t the coordinate allowance, r=w/2+c,
and alpha the allowed skew. Solve S=t+((h+t)cos(alpha)+r)/sin(alpha), measured from
the nominal pile face to the back of facing. Report the exact minimum and a
quarter-inch-up layout value. A square box centered on each pile extends h+S
in each direction; the enclosing row box is conservative where boxes overlap.
Show nominal zero-tolerance S as a separate reference, not the adopted layout.

Outputs: unfactored plan lengths in inches/feet, live face setback and box sizes,
both bent sketches with four pile boxes, cap, current facing and dimensions;
current front/return wall shortfalls. Positive shortfall means wall encroachment.
The exclusion applies to the assumed aligned, axis-parallel wall/strap arrangement.
Outside-box location alone does not certify the entire reinforcement route.
Cap/facing 24-inch front clearance remains a separate check. Battered-pile/pad,
elevation routing, vendor connection/development and structural stability remain
outside the accepted geometry scope. No overall project design approval is claimed.

Validation: tangent identity; independent corner-to-ray distance at and just below
the boundary; sensitivity to width, allowance and skew; geometric bounds and
quarter-inch rounding; both source wall/pile layouts; native recalculation and
dimension-label review in Blockpad. Native saved results must agree with independent
calculations. Integration must preserve all unassigned components byte for byte,
show only the new report plus index edit, and exclude inherited journal errors
from this bounded review. Record exact candidate hash and review evidence.

Stop conditions: changed source or shared geometry, new out-of-scope changes,
native errors in the new module, invalid skew/input ranges, or scope incompatibility.
