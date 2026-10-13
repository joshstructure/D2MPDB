# T009 - Front-wall strap clearance and fixed side-wall offsets

Authorized: retain the one MSEWallExclusion journal module, set alpha to 15 degrees,
evaluate strap clearance for the front wall only, adopt 24-inch minimum clear from
nominal end-pile faces to the back of each side wall, and regenerate the DXFs.
The earlier instruction to exclude pile placement tolerance remains in effect.
Use nominal 18-inch pile width and retain the existing 2-inch trial strap and
zero added edge gap. Either skew direction may be used; the calculation screens
the centered nominal pile, not the complete reinforcement route.

Only report:MSEWallExclusion may change. The existing index link and all other
components stay byte-identical to the current saved journal, including the user's
native save. No source model, shared geometry, loads or structural analysis edits.
Watch all other components as dependencies. The current base SHA256 is
01e52e58171e3b92c7a00eb23090a1cc1679f3159ff0ad204be6f8874d6d98c5.

Inputs come from BridgeGeometry_2Beam for pile size/count/spacing and cap size.
Wall locations and frame orientation remain the fingerprinted saved CAD snapshot.
The front-wall exact minimum is S=(h*cos(alpha)+w/2+c)/sin(alpha), h=pile width/2.
Round upward to 0.25 inch for front layout. SideClear=24 inches is a separate
specified layout criterion; no side-wall strap feasibility check is performed.
All clearances run from nominal pile faces to BACK OF FACING. Positive extra
setback means the current wall needs an outward parallel move to meet that criterion.
Front cap-to-facing 24-inch check remains separate. FDOT SDG 3.13.2.N.2 assigns
24 inches to cap/front-facing and battered-pile/leveling-pad measurements; do not
mislabel the user's side pile/facing criterion as a universal code strap clearance.

Draw open three-sided limits (front and two returns), with no rear-wall requirement.
Dimensions must distinguish computed front clear from specified side clear.
Preserve one native module; update all narratives, input validity, tables and
drawings consistently. Keep published front MinClear/LayoutClear names; register
SideClear and direction-specific extents. No existing formula consumer depends on
the prior square box names (confirm before removal).

Acceptance: independent tangent geometry in both skew directions, sensitivities,
zero pile-tolerance dependence of setbacks, CAD center checks, separate front/side
wall shortfalls, native Blockpad recalculation and visual review, exact candidate
fingerprints and untouched component preservation. Reopen/audit both DXFs and
verify dimension entities and original-coordinate overlay geometry. Stop for
unexpected upstream edits or native errors in the changed report. Full strap route,
vendor details, construction tolerances, stability and external analysis remain
outside this bounded nominal-geometry task. No overall design approval is implied.
