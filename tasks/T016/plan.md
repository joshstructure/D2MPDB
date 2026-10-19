# T016 - Journal coherence with the 19 October 2026 calculations and CAD model

Base journal SHA-256 `033bf8ff64ca83f0cb9dd38aa5f43bb0c427852b8e2111623cb2123b8fa0f49d` (T015).

## Objective

Make the journal's records agree with the project's current calculations and CAD model as
recorded in `project_current` on 19 October 2026:

1. Model sources: the D-049 fixed-run FB-MultiPier exports (`End Bent 1_Fixed.XML`
   c1a4afa1…, `End Bent 2_Fixed.XML` 3543df29…, `Pier_Fixed.XML` bb73e6ad…) replace the
   8 and 9 October records as the current models; the 10-19 cap reports (D-051) and pile
   reports (D-054) are the design records that read them.
2. End-bent design record (`FBMPEndBent`): the 19 October case (forces, status, report and XML
   identities, 235-in / 251-in cap); the 8 October transverse schedule kept as history.
3. Pier source record (`FBMPPier`, `FoundationModeling`, `PedBridge`): 10-19 report, D-049 XML,
   bearing rows ±10.50 in confirmed in the raw model (the earlier "matching raw XML not
   available" limit is resolved).
4. `PileProperties`: the pile design reports and the pipe-section reconciliation (FBMP 0.48-in
   shell at 60 ksi equals the module's 0.475-in effective section; PileDesignPier 45 ksi pending).
5. `BridgeGeometry_2Beam`: notebook basis named (build e9b41b8eaf, D-036/D-053, CAD D-055);
   `Check_notebook_quantity` retargeted from the 29 September haunch-volume snapshot to the
   e9b41b8eaf build inputs; the D-053 backwall top drop recorded as `EndBent_backwallDrop`.
6. `MSEWallExclusion`: the wall back-face lines re-extracted from the D-055 model (they moved
   with the 235-in caps and cheek webs; the module carried the 13 October 2026 lines of model
   7368774487…); cap caches follow the 235-in cap.
7. `PedBridge` index record and `DecisionLog` entry.

## Registered scope (`prepare T016`)

`--write` BridgeGeometry_2Beam, FBMPEndBent, FBMPPier, PileProperties, FoundationModeling,
PedBridge, DecisionLog, MSEWallExclusion (8 components); all other components are watched as
dependencies (all-component fallback). No addition, deletion, resource, style or shell change.

## Sources

- `project_current/source_register.csv` and `decisions.md` (D-049, D-051, D-053, D-054, D-055):
  report, case and XML identities; `project_current/cap_design/*/selected_case.json` (19 October
  forces and governing members); `project_current/pile_design/*/selected_case.json` (pile inputs
  and sources); the three D-049 XMLs (nodal loads on nodes 15 and 34; pier bearing rows ±10.50 in;
  pier section 20 in x 0.48 in, Fy 60 ksi).
- Geometry notebook `Bridge_Geometry_2 Beam_V2.ipynb` CONFIG (`backwall_drop_in` 4.25 for both
  end bents; cambers, minimum haunch and flange width as T014).
- The saved FreeCAD model (D-055, SHA-256 d0f053d5…): `tasks/T016/extract_mse_layout.py` reads
  the native `WallProfile` properties (same reading as `mse_strap_check/extract_layout.py`) into
  `tasks/T016/mse_layout_20261019.json`; bent centres from the 13 October snapshot (frame and
  support stations unchanged, asserted).

## Edits (byte-surgical; every anchor asserted; CRLF kept)

`tasks/T016/build_components.py` rebuilds all eight component files from `base.bpad`.
`mse_eval.py` evaluates the MSEWallExclusion definitions with Blockpad's display units and must
reproduce every current cached result (126) and formula table cell (59) before it refreshes
any; the refreshed values are logged in `definitions.json`. The two cap-volume cells of
FBMPEndBent take the T014 BridgeGeometry caches (205.625 / 411.25 ft³).

## Exclusions

- No other component changes; no stale-cache refresh outside MSEWallExclusion and the two
  FBMPEndBent cells (the wind chain, BearingDesign, PierWallFins and the quantity sheets still
  await native recalculation, as left by T014).
- No FBMP re-run, no Mathcad or notebook change, no native Blockpad recalculation.
- The 16 October backwall report (D-037) is not added: it predates the D-049 exports and the
  D-053 geometry; the journal records that.
- `project_current` is not edited by this task; the register and decisions are updated after
  promotion by the coherence process.

## Output contract

- `BridgeGeometry_2Beam.Check_notebook_quantity` reads `MATCHES NOTEBOOK BUILD e9b41b8eaf
  (2026-10-19)` while Deck_area, the two cambers, Haunch_min and Beam_topFlange_width equal the
  build; `EndBent_backwallDrop = 4.25 in` (amber input).
- `MSEWallExclusion`: wall literals `Bent{1,2}W{1,2,3}{x,y,len,tx,ty,nx,ny}` from the D-055
  model; at both end bents the front wall back of facing is 46.5 in from the pile row (gap to the
  pile face 37.5 in, MEETS CLEAR) and the side walls 114 in (gap 24 in, at the criterion within
  0.0002 in: one side of each bent reads MEETS CLEAR and the other SHORTFALL by the last digits);
  cap face to front facing 25.5 in, PASS.
- Text records as listed under Objective; the DecisionLog entry `CoherenceDecision20261019b`.

## Downstream

No formula consumer of the changed names outside the changed components (the check lists the
usual all-component impact hints). FBMP models unchanged; currency not asserted.

## Acceptance

`check` and `assemble` pass with no new structural issue or stored error; `verify_task.py`
confirms the component set, byte identity of every other component, link targets, the register
hashes in the text, the XML facts (nodes 15/34, ±10.50 in, pier section), the notebook backwall
drop, the MSE wall literals against a fresh extraction and plain-python gap values, and that no
superseded identity remains outside the historical mentions.

## Optional reviews (not required by the promotion policy)

Native Blockpad: recalculate MSEWallExclusion (canvases redraw from the new wall lines) and
BridgeGeometry_2Beam; confirm the new sections render. Engineering: the side-wall rows at the
24-in limit, the pipe-pile grade reconciliation, and whether the backwall report is to be rerun
on the D-049 export and D-053 geometry.

## Stop conditions

Changed upstream components, an assertion failure in the build (anchor counts, cache
reproduction), a check rejection, or a model hash other than d0f053d5… for the MSE extraction.
