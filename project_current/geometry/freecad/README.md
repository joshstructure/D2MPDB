# Current FreeCAD bridge model

## D-055: backwall vertical coordination, 19 October 2026

Four doubled #5 verticals removed; one end bar per face moved inside each cheekwall hook. Small station adjustments clear the cap stirrups with 12-in maximum spacing. Each backwall now has 44 verticals and 10 horizontals. All 88 verticals pass physical overlap and cover checks; native edits and cold reopen verified. See [saved-file verification](evidence/2026-10-19-backwall-vertical-coordination/adoption-summary.json). Existing unrelated findings and downstream calculation/drawing review remain.

## D-053: simple backwall tops and ramp connections, 19 October 2026

Both backwall tops have two straight 2% slopes down from the PGL, level
through their 12-in thickness. Each top lies 4-1/4 in below its FFBW
deck-top line. EB1 top elevations are 47.111000 / 47.306833 / 47.111000 ft;
EB2 elevations are 47.123000 / 47.318833 / 47.123000 ft (left / PGL / right).
The ramp slabs thicken locally to these tops; their walking faces and footprints
are preserved. Checked thicknesses are 4.119-4.954 in at EB1 and
4.047-4.954 in at EB2. Both wall and landing solids are valid and meet without
positive overlap; adjacent finished concrete gains no overlaps.

Four top backwall horizontals move down for 3-in cover: 3/8 in at EB1 and
an additional 1/4 in at EB2. EB1 cheek rows MH09/MH10 move down 5/8 in
on both sides, preserving their standard hooks and the 10-in maximum spacing.
Bar counts, marks, other steel and all 2,100 unrelated native objects remain.
Both backwalls retain 56 bars. Native cover, changed-bar intersections,
walking faces, live controls, quantities and saved-file reopening are checked.
The verified landing quantities are now A = 111.987035 ft3 and
B = 89.038401 ft3. TopDrop and BackwallTopSource are editable native controls.

Notebook model e9b41b8eaf and the B4 workbook carry the same wall geometry.
The earlier interactive report (622e5ca1bf) is a retained prior snapshot.
Backwall/slab calculations, load takeoffs and drawing exports require their
normal downstream refresh; existing tracker statuses/responses are preserved.
See [source receipt](../../coherence/evidence/2026-10-19-simple-backwall-tops/source_receipt.json).

## D-048: backwall bars extended into cheeks, 17 October 2026

All 20 #4 backwall horizontal bars now extend **8-1/4 in at each end**, to the
**3-in clear-cover limit** of the adjoining cheeks. Their new length is 245 in.
Eight matching #5 verticals were added: one per face at each end of both
backwalls. They are 8 in from the adjacent backwall verticals (7-3/8 in clear).
The two top horizontals at End Bent 2 were lowered 1/8 in to retain full cover.

The saved revision passed 367 checks: affected bar geometry, physical cover,
no new overlaps, live schedules, native control edits, and exact preservation
of all 2,067 unrelated native objects. Both backwalls now contain 56 bars each.
The D-047 pedestal revision is preserved. See [adoption and verification](evidence/2026-10-17-backwall-extensions/adoption-summary.json).
Existing unrelated findings remain; downstream drawings and calculation
exports must be refreshed through their normal workflows.

## D-047: pedestal edge reinforcement, 17 October 2026

All six pedestals now contain 84 editable #4 U-bars (12 added) at **6 in maximum**
each way, with **2 in pedestal cover**, **3 in cap cover**, **12 in cap embedment**
and contacting horizontal layers. The near-face longitudinal legs share the
actual cap-stirrup vertical planes. Outer transverse bars shifted locally to
clear upper bends and cap steel. Live paths, bar marks, quantities and schedules remain.

The selected model passed 1,103 geometry/editability/reporting checks after cold
reopening. All 874 potentially conflicting pairs involving pedestal steel passed:
zero positive overlaps and no retained 1 in pile-clearance failures. All 1,911
unrelated native objects are preserved.

The user clarified that these bars are **compression only**, accepted the detail,
and directed the model push. The stored 16 development flags and schedule values
come from the earlier **tension** calculation; they are retained as historical
diagnostics and do not represent compression-check failures. No new compression
calculation is claimed. See [user disposition](evidence/2026-10-17-pedestal-edges/user-disposition.json)
and [adoption verification](evidence/2026-10-17-pedestal-edges/adoption-summary.json).
Existing unrelated review items remain. Downstream drawings and calculation
exports require their normal refresh against the new selected model.

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

Each backwall now has **seven editable 2-in-wide geotechnical strap references**,
matching Figure B2 of the selected backwall report: **33.571429 in spacing**
and **16.785714 in end offsets** along each 235-in backwall. They connect to the
fill-side face **18 in above the cap top**. The 6-ft projection remains illustrative.
These zero-thickness reference faces add no physical steel quantity. The report
labels this arrangement schematic and assigns final layout to the Specialty Engineer.
Expand **Geotechnical backwall straps - schematic** to edit native width,
projection, signed offset or elevation. See
[D-045 correction and checks](evidence/2026-10-17-strap-report-layout/update-summary.json).
Final strap/connection design and closure reinforcement/weather-seal details remain
unresolved; calculation reconciliation stays under COH-023.

All 454 end-bent and pier rebars now carry FDOT SDM 4.3 bar marks in their
**Mark** property (for example 6A1, 5B2, 4F3), with new cheek hook shapes
marked 4E3/4E4. The generated FDOT
[end bent and pier DXF](../../../substructure_drawings/README.md) and its bar-mark
register predate D-046 and require regeneration for these hook shapes.
The native schedules match the current model marks. Controllers
still give newly regenerated bars their default marks; rerun
`substructure_drawings/freecad_marks.py` after a regeneration.
See [D-042 evidence](evidence/2026-10-16-sdm-bar-marks/update-summary.json).

The four bridge-deck railings are grouped under **PGL-controlled bridge
components → Bridge railing**. Their existing PGL links and geometry are
preserved. Ramp and end-return barriers keep their prior groups.
See [D-040 evidence](evidence/2026-10-16-railing-group/update-summary.json).

The cheek mats retain **64 #4 bars at 10 in maximum each way**. D-046 now
adds **42 standard 90-degree hooks on 30 horizontal bars**: 24 hooks enter the
caps and 18 enter the backwalls. Each hook has a 3-in inside bend and 6-in
straight tail. The lower row and the rows above the available backwall retain
straight ends; End Bent 2 row MH09 also lacks the required top cover.
Cap hooks are set inward to clear retained hoops. All affected geometry,
cover, steel-intersection, schedule, lug-mesh and saved-reopen checks pass.
Native **Horizontal hooks** properties remain editable. Required development
and connection design remain unverified; existing unrelated findings remain.
See [D-046 evidence](evidence/2026-10-17-cheek-hooks/update-summary.json).
The [D-039 mat revision](evidence/2026-10-16-cheek-steel/update-summary.json)
records the unchanged bar spacing basis.

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

**Current model: 17 October 2026, decision D-046.** This is the authoritative
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
