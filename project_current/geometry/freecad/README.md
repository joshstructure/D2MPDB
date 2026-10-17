# Current FreeCAD bridge model

The bridge now omits modeled **3/4-in standard chamfers** on its decks, FIB
beam bottom corners and pedestals for square 2D drawing edges. Nominal chamfer
inputs remain recorded; `BridgePGL.OmitStandardChamfers` controls the convention.
Ramp and barrier geometry, V grooves, larger section breaks and fillets are retained.

Both end bents now have low MSE-wall copings and **4-in closure slabs rising
at 2% toward the cap face**. Front coping and slab tops coincide; side coping tops
follow the same sloping plane. Expand **End-bent MSE copings and rain closure
slabs** for the editable dimensions, links and live quantity schedule.
The eight new solids total 123.684362 ft3. Native slope/thickness/contact checks
pass, with no positive overlaps in 197 affected pairs. See
[D-044 evidence](evidence/2026-10-17-square-edges-and-closure/update-summary.json).

Each backwall now has one editable **2-in-wide geotechnical strap reference**
connected to its fill-side face **18 in above the cap top**, following the
selected backwall calculation's trial level. The 6-ft projection is illustrative.
These zero-thickness reference faces show no design spacing or connection hardware
and add no steel quantity. Expand **Geotechnical backwall straps - schematic**
to edit width, projection, offset or elevation. Final strap and connection design
remain with the MSE supplier. Closure reinforcement and weather-seal/joint details
remain unspecified; calculation reconciliation stays under COH-023.

All 454 end-bent and pier rebars now carry FDOT SDM 4.3 bar marks in their
**Mark** property (for example 6A1, 5B2, 4F3), matching the generated FDOT
[end bent and pier DXF](../../../substructure_drawings/README.md) and its bar-mark
register. The cage, wall and pedestal schedules show the same marks. Controllers
still give newly regenerated bars their default marks; rerun
`substructure_drawings/freecad_marks.py` after a regeneration.
See [D-042 evidence](evidence/2026-10-16-sdm-bar-marks/update-summary.json).

The four bridge-deck railings are grouped under **PGL-controlled bridge
components → Bridge railing**. Their existing PGL links and geometry are
preserved. Ramp and end-return barriers keep their prior groups.
See [D-040 evidence](evidence/2026-10-16-railing-group/update-summary.json).

The cheek steel now matches the selected 16 October backwall/cheek report:
one centered #4 mat at **10 in maximum each way**, 64 bars total. All 342 cheek
checks pass, including cover, spacing, native geometry and cap-bar clearance.
The 180 lug WWR wires also pass the affected review. Native saved-file reopen,
live controls and schedules are verified. Shorter local bays clear retained steel.
See [D-039 evidence](evidence/2026-10-16-cheek-steel/update-summary.json).

All four cheek tops now meet the return barrier bases. The transverse return
bottom bands extend to the slab, the return-to-ramp notches are removed, and
copings stop at the outer rear lug faces. The taller cheeks now have 64 mat bars
and 180 lug WWR wires. No new affected clashes; existing concrete overlaps are
logged in COH-026. Both 4-inch landing slabs now continue into the four return
voids, and the barrier lower legs meet them. All finished faces retain the viewing
palette. Curved-landing quantities are corrected under D-034; COH-027 is closed. See [D-033 evidence](evidence/2026-10-15-return-cheeks/adoption-summary.json).

The two finished landing slabs now have verified **NetVolume** values:
**A = 111.481112 ft3 (4.128930 yd3)** and **B = 88.556269 ft3 (3.279862 yd3)**.
Select **A/B landing slab - continued beneath returns** and read **NetVolume**;
**VolumeStatus** should say **Verified**. The native controller maintains these
quantities on rebuild. FreeCAD's built-in `Shape.Volume` remains inaccurate for
these two curved solids. Geometry, reinforcement, colors and visibility are
unchanged. See [D-034 evidence](evidence/2026-10-15-landing-quantities/update-summary.json).

The four shared height controls are under **Bridge assembly → Return and cheek
connection controls**. Existing construction sources remain necessary and hidden.

The model was cleaned under D-032: 42 unused superseded wall/detail objects
were removed. Necessary rebar construction paths are hidden, along with the
nominal pier envelope and duplicate complete PGL source. All current physical
geometry and reinforcement remain unchanged. Keep each reinforcement **Paths**
group hidden; **Bars**, **Bottom** and **Side** contain the physical steel.
See [cleanup evidence](evidence/2026-10-15-model-cleanup/adoption-summary.json).

The DXF deck-edge correction retains its 1.5 in barrier setback and nominal
0.75 in chamfer inputs (solid cuts omitted under D-044), with 1 x 0.5 in V grooves centered
3 in along the soffit from the virtual outside corner. Both spans retain their
PGL, crown, six-inch vertical thickness, end gaps and cambers. Clear width between
barrier faces is 12 ft. The component/reinforcement viewing palette is also saved.
See [adoption evidence](evidence/2026-10-15-deck-edges/adoption-summary.json).
On each deck, use the **Deck edge details** properties; the four original deck
barrier objects have **DeckEdgeSetback**. The opener loads their native controllers.

**Current model: 17 October 2026, decision D-044.** This is the authoritative
editable bridge geometry and modeled-quantity source. The established native
filename is retained for existing links; its date is not the current revision date.

On Windows, double-click **Open Current Bridge.cmd** in this folder to start
FreeCAD 1.1 and execute the opening macro automatically. A local **Open Current
Bridge** shortcut is also available in `C:\Users\joshs\Desktop\CAD_AI`; it opens
the same macro directly, without a command window. The launcher does not save
the model. Close a copy opened without its controllers before using the launcher;
do not save that failed-load copy over the current model.

Alternatively, open `Open_Current_Bridge.FCMacro` in a fresh FreeCAD 1.1.3 session with the
existing Reinforcement v0.6 workbench, then execute the macro. Keep the entire
folder and `runtime` together. The opener loads the matching controllers and
the adjacent [main model](B4%20Pedestrian%20Bridge%20and%20Ramps%20-%20Pond14D%20-%20Source%20Update%2020261010.FCStd).
If different bridge controllers are already loaded, save wanted work and restart
FreeCAD before running this opener. `Show_Elevations.FCMacro` displays the 168
source-linked elevation labels. Intentional model edits remain native and editable.

## Adopted details

- DXF concrete copings and pedestrian barriers on the ramps and bridge deck.
- Extended 235 in end caps, 8 in cheek webs, 6 in rear/bottom lugs, revised MSE
  offsets and landing transitions, 12 mitred wall corners and level barrier returns.
- Raised end-bent MSE tops with 0.5 in vertical and horizontal cheek/lug joints.
- One centered mat of #4 bars at 10 in maximum each way in all four cheeks.
  D-039 resolves the four D-029 spacing findings. Each cheek has five vertical
  and eleven horizontal bars. Live schedules are inside
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

The cap cages are now 62/90/62 bars under D-027. Backwalls retain 104 bars and cheeks now have
64 bars. Cheek spacing and cap/cheek intersections are resolved.
33 backwall/cap bar intersections and cap detailing findings remain open.
Lug WWR is modeled under D-030. Anchorage, development, fabrication and strap
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


## Horizontal cheek-bar coordination (D-029)

MH03 is lowered 3/8 in at each cheek, resolving all eight cap/cheek intersections.
End stirrups remain at D-028 stations 6 and 245.875 in; every other bar and all
concrete are unchanged. Counts remain 62/90/62 cap bars and 48 cheek bars.
The user elected to move only MH03: the four resulting 12 3/8 in spacings exceed
the existing 12 in maximum and remain flagged under open item COH-024.
Native checks pass for geometry and clearance; the spacing findings remain FAIL.
The supplied design cases are unchanged. This revision remains local.

[Latest review](evidence/2026-10-14-horizontal-cheek/update-summary.json) and [updated view](evidence/2026-10-14-horizontal-cheek/views/EB1-cheek2-clashes.png).


## Cheek lug welded wire reinforcement (D-030)

The accepted **4x4 W1.4xW1.4** layout is installed on all four cheeks: eight
separate sheets and 172 editable native wires. The bottom sheet folds beneath
the cap steel and extends **8 7/8 in into the cap**; the side sheet laps the cheek
steel by **8 1/8 in**. Both include two full 4 in squares. Wire diameter is 0.134 in,
centerline fold radius is 1 in, and minimum measured cover is 2 1/8 in.

Expand `CheekLugWWR` for per-cheek Inputs, Bottom and Side sheets, live quantities,
and `CheekLugWWRSchedule`. All 172 wires match the accepted trial and pass the new
clash/cover review. Existing concrete and steel are unchanged. The 14 existing
U-bar/hoop overlap pairs remain **Deferred in COH-025**, with [location and close-up
views](evidence/2026-10-14-lug-wwr/stirrup-review/stirrup-overlap-locations.png).
The four cheek spacing findings remain Open in COH-024; other findings persist.

See the [WWR adoption evidence](evidence/2026-10-14-lug-wwr/update-summary.json).
The prior model and runtime are archived as `B4-before-lug-WWR-20261014.FCStd`
and `B4-before-lug-WWR-runtime-20261014.zip`. The user authorized publication of
this source update; the previous D-029 revision was also subsequently published.
