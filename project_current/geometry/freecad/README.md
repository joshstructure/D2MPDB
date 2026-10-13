Current file update: **12 October 2026**. The dated native filename is retained for existing links. See [current update report](evidence/Model-update-report.txt) and [latest verification](evidence/2026-10-12-pedestal-ubars/adoption-summary.json).

# Current FreeCAD bridge model

This folder is the authoritative home of the **current editable FreeCAD bridge
geometry and modeled quantities**, selected by the user on 10 October 2026.
The native model is an exact copy of the verified CAD_AI delivery. Use this
repository copy for subsequent model work; the Desktop CAD_AI copy is the delivery
baseline. A filename date identifies this selected issue, not design approval.

[Download the native model](B4%20Pedestrian%20Bridge%20and%20Ramps%20-%20Pond14D%20-%20Source%20Update%2020261010.FCStd) (keep this folder and its runtime together).

## Open and use

1. Keep this entire folder together in a local repository checkout or downloaded
   repository ZIP. Downloading only the FCStd file omits its editable controllers.
2. Use FreeCAD 1.1.3 with the existing Reinforcement v0.6 workbench. No MCP server
   or AI connection is required. Other versions have not been verified.
3. In FreeCAD, open `Open_Current_Bridge.FCMacro`, then use **Macro ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Execute**
   (or the macro editor's Execute button). It opens the adjacent model using the
   adjacent `runtime` controllers. If another controller copy is already loaded,
   save any wanted work, restart FreeCAD and run this macro first.
4. Expand **PGL-controlled bridge components**. Double-click **LIVE bridge
   component quantities** for volumes. Inside the EB1, Pier and EB2 reinforcement
   groups, double-click **EB1 LIVE bar schedule**, **Pier LIVE bar schedule** or
   **EB2 LIVE bar schedule** for bar counts, sizes, lengths and nominal weights.

The controls, analytic rebar paths, expressions, quantities and check objects
remain native and editable. Save intentionally after reviewed edits. GitHub
represents the last committed model; local edits do not upload automatically.

## Authority and current limits

This model records what is modeled and its derived quantities. The adopted
journal and selected engineering cases remain the authorities for their inputs,
design decisions and calculations. Differences require reconciliation; this
registration does not override them or close coherence items.

- Both saved cambers now follow the 12 October notebook update: 0.1245927440 in and 0.5671714631 in.
- The three cap cages contain 204 native bars with live schedules, plus 184 trial wall bars and 72 pedestal U-bars.
- Cover failures, bar overlaps, bridge/MSE clashes, landing-level differences
  and source pile-envelope conflicts remain recorded FAIL.
- Final wall details, pile tips, anchorage, fabrication quantities and omitted
  superstructure reinforcement remain provisional, deferred or outside scope.
- Earlier CAD_AI drawing/export packages have not been regenerated for this issue.

See [the original update report](evidence/Model-update-report.txt) for exact scope,
quantities, assumptions and failures. Historical evidence retains its original
local paths; the adjacent model and this opening macro are now the working paths.

## Maintain this source

Keep the FCStd, opening macro and pinned runtime together. Record deliberate
changes in `../../source_register.csv`, `../../decisions.md` and the
authoritative coherence workbook where applicable; preserve existing responses.
Update `manifest.json` and register fingerprints only after recording the change
and its checks. Commit the reviewed model and matching support files together.
Do not rerun historical creation transactions to edit this model.

The bundled [API guide](runtime/API.md) describes tested modeling helpers. It is
a pinned copy of the CAD_AI guide, whose historical examples retain their original
paths. No dependency upgrade is performed by the opening macro. The bundled
cap geometry code is pinned to the original source update; it is not a replacement
for the current calculation notebook or engineering review.

## Package verification

The copied model passed 1,546 reopen, geometry, controller, schedule and hook-dependency checks; five broader design checks remain not configured. The native model bytes are unchanged. The automated offscreen GUI launch could not complete, so no new visual or GUI-opener review is claimed. See the package verification evidence.

## 12 October reinforcement update

Both end-bent cap grids are disabled, reducing their cages to 57 bars each. Pier steel stays at 90 bars. Backwall/cheekwall Figure B8 adds 184 trial bars with editable source inputs and live schedules. All concrete and cambers are unchanged. Existing cheekwall dimensions already match the report. The new dated wall-check object is a snapshot; rerun its check after edits. Dowels are schematic, and cover/clash failures remain open. Current native-file verification is in evidence/2026-10-12; earlier verification above describes the preserved 10 October revision.

The new adapter is qualified only for disposable file-copy preparation followed by exact native-record preservation and cold-reopen verification. Its failed live undo test is retained in CAD_AI diagnostics; do not invoke it on an authoritative open document.

## 12 October notebook camber update

The current saved model now follows the updated geometry notebook under D-023.
Its physical beam lengths and bearing setbacks already matched the new beam
runs; changed cambers update beams, haunches, bearings, pedestals, cap elevations,
pile heads and dependent wall geometry/reinforcement through native controllers.
Ramps, terrain and decks are preserved. The prior model is saved in
[archive/B4-before-camber-update-20261012.FCStd](archive/B4-before-camber-update-20261012.FCStd).

All ten notebook code cells execute and 36 geometry tests pass. The saved model
passes 8,255 cold-reopen checks, and 93 independent native support-section cuts
match the notebook. Existing native controls, links, expressions, schedules and
view records remain editable. No native GUI visual review is claimed.

See the [interactive geometry report](evidence/2026-10-12-cambers/Bridge_Geometry_Report.html),
[notebook geometry export](evidence/2026-10-12-cambers/notebook-geometry.json), and
[verification summary](evidence/2026-10-12-cambers/update-summary.json).
There are 11 bridge/MSE overlap pairs and 27 wall-to-wall/cap-steel overlap pairs
in the current checks. Cap-cage detailing and landing discrepancies remain FAIL.
Final pile tips, anchorage, fabrication and final wall design remain outside this
geometry update. Prior cap/backwall reports and drawing packages were not rerun.


## 12 October pedestal reinforcement adoption

Under D-024, the user selected the reviewed model with 72 native #4 U-bars on
all six pedestals. Mean spacing is 6 in each way, with local 5.25-6.75 in
intervals resolving six intersections. Physical pedestal/cap cover and LRFD
straight development checks pass. End-bent embedment is 12 in; Pier B1/B2
embedments are 17/13 in. No new U-bar-to-U-bar or U-bar-to-existing-steel solid
overlaps remain, and pile clearance passes. Surface contact is allowed.

Use the usual opening macro. The `PedestalReinforcement` group contains editable
inputs, native bars and paths, and six live schedules. All 1,230 prior native
objects, existing cambers and geometry are preserved. Prior cap/wall/bridge
issues retain their status; previous drawing exports have not been regenerated.

The [adoption evidence](evidence/2026-10-12-pedestal-ubars/adoption-summary.json)
records the exact selected bytes and 398 passing native checks. The previous
main model is preserved in
[archive/B4-before-pedestal-ubars-20261012.FCStd](archive/B4-before-pedestal-ubars-20261012.FCStd).
