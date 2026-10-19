# T014 - Journal coherence: geometry notebook alignment, C005 removal, ProjectInfo and project stamp

Base journal SHA-256 `0384f0280175c2d597aa75ce9cf33fae1eb602ee2dcf581eaa30f11454442d07` (T013).

## Objective

1. Align `BridgeGeometry_2Beam` with the geometry notebook (decision D-036; notebook model e9b41b8eaf, 19 October 2026, mirrored in `project_current/geometry/tables/B4_Geometry_CAD_Tables.xlsx`).
2. Delete C005 (`report:PierCapDesign`) after moving every consumer to a new owner (`Materials` for strengths, `BridgeGeometry_2Beam` for the pier cap covers, `CapDesignPier` as the pier cap record).
3. Add a `ProjectInfo` report and a live project stamp (a table reading `ProjectInfo.*`) to every calculation report.
4. Refresh the four cap design reports from the generator (`scripts/build_cap_bpad.py --journal`), now reading the new owners.

User direction of 19 October 2026 supersedes D-003 (preserve C005 unchanged): C005 is removed. Journal history (DecisionLog) keeps the old entries.

## Registered scope (`prepare T014`)

`--add report:ProjectInfo --delete report:PierCapDesign` and `--write` for PedBridge, Materials, BridgeGeometry_2Beam, FBMPEndBent, FBMPPier, PierWallFins, DecisionLog, AccessGeometry, BearingDesign, PileProperties, GeneralLoads, PedBridgeWind, C001WindLoadOnPedBridgeSuperstructure, FenceWind, BridgeMovement, SuperstructureUplift, LoadCombinations, FoundationModeling, MSEWallExclusion, CapDesignBasis, CapDesignEndBentOne, CapDesignEndBentTwo, CapDesignPier (25 components; all other components are watched as dependencies, registered topology addition). `prepare` accepted the mixed add/delete scope.

## Notebook values adopted (source: notebook CONFIG as mirrored in the workbook, sheet `Inputs`, `Camber & Haunch`, `Substructure`)

| Journal input | Before | After | Notebook source |
| --- | --- | --- | --- |
| `EndBent_pileEndClear` (new) | - | 27.5 in | `end_bents.*.pile_end_clear_in` |
| `EndBent_endDetail` | 4 in (amber) | `EndBent_pileEndClear-EndBent_edgeClear-EndBent_pileTolerance` = 15.5 in | derived |
| `EndBent_cheekThickness`, `_lugProjection`, `_lugWidth`, `_mseJoint` (new) | - | 8, 6, 5.5, 0.5 in | `end_bents.*.cheek_thickness_in`, `lug_projection_in`, `lug_width_in`, `mse_joint_in` (D-026) |
| `EndBentCage_envelope` (new) | - | `EndBentCap_length+2*EndBent_cheekThickness` = 251 in | D-027 |
| `Beam_camber_1`, `Beam_camber_2` | 1 in, 1 in | 0.124592744006574 in, 0.5671714630550072 in | `spans[n].camber_in` (Mathcad NetCamber, 120 days) |
| `Beam_support_drop` | closed-form formula, 3.751 ft (placeholder cambers) | formula kept unchanged; evaluates to 3.7147642885879173 ft with the notebook cambers (cache 3.715 ft) | `Camber & Haunch` common support drop D |
| `PierCap_coverTop/Bottom/Side` (new) | in C005 | 3 in each | moved from C005 |

Note: with the new cambers the existing closed-form formula (`... +Max(Beam_camber_1,Beam_camber_2)`) evaluates to the notebook 3.7147642885879173 ft (44.01 in + 0.56717 in). By coordinator direction the formula is NOT replaced by a typed value (that would repeat a derived parameter); only its caption names the equality and its cache is refreshed.

## Edits (byte-surgical; every anchor asserted; line endings kept)

`tasks/T014/build_components.py` rebuilds all 25 component files from `base.bpad`. `geom_eval.py` (unit-aware evaluator of the report's own formulas) must first reproduce every current dependent cache (34) before it refreshes them. Every refreshed cache is logged with old and new text in `definitions.json`. Cheek, lug and MSE-joint values are inputs only (`EndBentCap_length` stays the 235-in cap body).

- `ProjectInfo` (added): eight amber string inputs and the stamp table (preview).
- `Materials`: six amber inputs (`Substructure_fc`, `Deck_fc`, `Beam_fc`, `Railing_fc`, `Rebar_fy`, `Rebar_Es`) replace the C005 link; PileProperties link kept.
- `BridgeGeometry_2Beam`: items above; 35 dependent caches and 12 pile-table cells refreshed (including `Check_notebook_quantity`, which now reads `INPUTS CHANGED - RECONCILE NOTEBOOK` because the haunch total no longer equals the 29 September snapshot); Source row names the notebook; C005 text mentions replaced; audit-station sentence updated (66.00 / 168.99 in).
- `FBMPEndBent`: `EBSteel_fc/fy/Es` read `Materials.*` (live, `Required Input` style dropped). `PierWallFins`: `f_c`, `f_y`, `E_s` read `Materials.*`, `c_w` reads `BridgeGeometry_2Beam.PierCap_coverSide` (caches unchanged). `FBMPPier`: C005 sentences replaced.
- `PedBridge`: C005 link removed, `#ProjectInfo` link added first under "Project basis and geometry". `DecisionLog`: 19 October 2026 entry appended; older entries kept as history.
- Project stamp: inserted (lxml-built `project_stamp_table(..., live=True)` block, spliced at the byte offset before the first content child) in 17 reports: Materials, BridgeGeometry_2Beam, AccessGeometry, BearingDesign, PileProperties, GeneralLoads, PedBridgeWind, C001, FenceWind, BridgeMovement, SuperstructureUplift, LoadCombinations, FBMPPier, FBMPEndBent, FoundationModeling, PierWallFins, MSEWallExclusion. The four cap reports carry the stamp from the generator; the helper's own `<embed spacingbefore="5" spacingafter="8">` is used unchanged so all 22 stamps are identical.
- Cap reports: preview journal (all edits applied, C005 removed, ProjectInfo added) -> `scripts/build_cap_bpad.py --journal` -> four fragments copied unchanged.

## Exclusions

- Spreadsheets (PedBridgeWeights_2Beams/3Beams, quantities), reference/archive reports (CodeReferencesGeneral, Notes, BridgeGeometry_3Beam, VoidPedBridge, ...), PedBridge (index) and DecisionLog (log) get no stamp.
- No other component, resource, style, include or document-shell change. No FBMP re-run, no Mathcad or notebook change, no native recalculation.
- Stale caches in unregistered or unrefreshed consumers (see submission.json) are not edited here.
- `scripts/`, `tests/`, `pier_cap/`, `project_current/` and the journal itself are not edited.

## Read dependencies and downstream effects

All other components are watched (registered addition). Consumers of changed values: the wind chain (`Wind_clearHeight` and `Wind_exposureHeight` into C001, FenceWind, PedBridgeWind, SuperstructureUplift, FBMPPier, FBMPEndBent), `BearingDesign` (`CapTop_aboveTerrain`), `MSEWallExclusion` (cap length), haunch volumes into `PedBridgeWeights_2Beams` and the quantity sheets. Exposure height rises 0.43 in (K_Z +0.023 percent). FBMP models and results are unchanged and not re-run.

## Acceptance

`check` passes (no out-of-scope edits, no new structural issues or stored errors, no remaining qualified reference to `PierCapDesign`, deleted-module consumer check clean); `report.json` `deleted_components == ['report:PierCapDesign']`; `tasks/T014/verify_task.py` passes (22 stamps equal `PROJECT_STAMP`, every new reference resolves, geometry chain 27.5 / 36.5 / 235 / 251 in and every refreshed cache equal to the independent recomputation, `coherence.json` has no `literal_incoherent_journal` row and `L_cap` is owned by `EndBentCage_envelope`).

## Optional reviews (not required by the promotion policy)

Native Blockpad recalculation: string inputs and `ProjectInfo.*` references in table cells, the stamp block before section elements, amber definitions with `showresult="False"`, `Check_notebook_quantity` text, wind chain values after recalculation. Engineering: the support-drop equivalence and the pier-cap cover move.

## Stop conditions

Changed upstream components, an assertion failure in the build script, a fragment that differs from `cap_bpad/journal/verification.json`, a check rejection, or any reference to `PierCapDesign` left in the preview or candidate.
