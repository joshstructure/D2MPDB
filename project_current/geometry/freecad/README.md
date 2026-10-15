# Current FreeCAD bridge model

**Current model: 14 October 2026, decision D-028.** This is the authoritative
editable bridge geometry and modeled-quantity source. The established native
filename is retained for existing links; its date is not the current revision date.

Open `Open_Current_Bridge.FCMacro` in a fresh FreeCAD 1.1.3 session with the
existing Reinforcement v0.6 workbench, then execute the macro. Keep the entire
folder and `runtime` together. The opener loads the matching controllers and
the adjacent [main model](B4%20Pedestrian%20Bridge%20and%20Ramps%20-%20Pond14D%20-%20Source%20Update%2020261010.FCStd).
If different bridge controllers are already loaded, save wanted work and restart
FreeCAD before running this opener. `Show_Elevations.FCMacro` displays the 170
source-linked elevation labels. Intentional model edits remain native and editable.

## Adopted details

- DXF concrete copings and pedestrian barriers on the ramps and bridge deck.
- Extended 235 in end caps, 8 in cheek webs, 6 in rear/bottom lugs, revised MSE
  offsets and landing transitions, 12 mitred wall corners and level barrier returns.
- Raised end-bent MSE tops with 0.5 in vertical and horizontal cheek/lug joints.
- One centered mat of #4 bars each way in all four cheeks at 12 in maximum spacing.
  Each cheek has four vertical and eight horizontal bars. Live schedules are inside
  the cheek reinforcement groups. The bars are visible through translucent concrete.
- All 12 piles and the prior notebook cambers and 72 pedestal U-bars are retained.
  Main down ramps remain at or below 5%; the short landing transition exception
  follows the user's direction.

## Evidence and remaining review

[Adoption summary](evidence/2026-10-14-mse-and-cheek/adoption-summary.json),
[current report](evidence/Model-update-report.txt), and
[source DXF](../details/B4%20Pedestrian%20Bridge%20-%20Working.dxf).
The prior D-026 cheek-steel revision passed 282 geometry/cover/clash/schedule checks.
Its retained geometry is tied to 621 prior geometry checks and 110 route-grade checks.
Physical model checks do not constitute engineering or fabrication acceptance.

The cap cages are now 62/90/62 bars under D-027. Backwalls retain 72 bars and cheeks now have
48 bars. Eight cap/cheek and 33 backwall/cap bar intersections and cap detailing
findings remain open. Anchorage, development, laps, lug reinforcement and strap
details remain unresolved. COH-023 tracks reconciliation of the adopted CAD with
the geometry notebook, cap calculations and backwall report. Those calculation
sources keep their recorded authority and are not silently updated by this adoption.
Older external drawing/export packages have not been regenerated.

## Backup and source maintenance

The previous main model is in
[`archive/B4-before-MSE-and-cheek-revision-20261014.FCStd`](archive/B4-before-MSE-and-cheek-revision-20261014.FCStd).
Its matching controllers and former manifest/docs are in
[`archive/B4-before-MSE-and-cheek-runtime-20261014.zip`](archive/B4-before-MSE-and-cheek-runtime-20261014.zip).
Earlier 10/12 October evidence remains in the evidence folder as history.

Keep the model, opener and runtime together. Record later deliberate revisions
in the source register, decisions and tracker, then update the manifest after
verification. Existing check objects are dated snapshots; rerun affected checks
after editing. Do not replay historical creation transactions on the main model.

## Updated end-cap cages (D-027)

The 251 in cage envelope includes the 235 in cap plus two 8 in cheek webs.
At D-027, concrete and the centered cheek mats were unchanged. The supplied cases
produce 62 cap bars each, including #6 transverse bars. See the [D-027 review](evidence/2026-10-14-end-caps/update-summary.json)
and [clash views](evidence/2026-10-14-end-caps/views/EB1-cheek2-clashes.png).
Blue is cap steel, orange is cheek steel and red marks intersections. COH-024
tracks discussion and repair. Clashes remain visible and failed checks remain FAIL.

The former main model and matching runtime are preserved in the dated
`archive/B4-before-end-cap-steel-20261014.FCStd` and runtime ZIP. Headless native
reopen and preservation checks pass. Full-model GUI reopen could not be verified
by the standalone graphical loader, which also fails on the unchanged baseline.
The review screenshots use volume-checked exports of the exact native solids.

## Cap and cheek coordination (D-028)

The extra MV05 vertical is removed from each cheek. Outer verticals MV01/MV04
sit 5.25 in from the web edges, just inside the cap bars. End hoops are inward of
the complete mat envelopes; the other hoop stations and all horizontal cheek
bars are unchanged. Cap counts remain 62/90/62 and cheek count is 48.

[Current review](evidence/2026-10-14-cap-cheek-coordination/update-summary.json)
and [revised view](evidence/2026-10-14-cap-cheek-coordination/views/EB1-cheek2-clashes.png).
Requested changes pass 544 clearance checks and 724 cold-reopen geometry checks.
Eight intersections remain at the third horizontal cheek bars; COH-024 stays open.
Original supplied design cases remain unchanged; explicit editable CAD overrides
record this coordination. Contact is allowed and positive overlaps remain FAIL.
The immediately previous model and matching runtime are in
`archive/B4-before-cap-cheek-coordination-20261014.FCStd` and its runtime ZIP.
