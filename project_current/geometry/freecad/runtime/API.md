# Stable FreeCAD-side API, v0.1.0

## Current-source bridge copy and live cap cages (2026-10-10)

The user authorized repair/update of the latest saved Pond14D model against
`C:/github/D2MPDB/project_current`, retaining both saved cambers, and adding
parametric cages like the native concrete-beam example. The original file is
preserved. The updated file is `Models/B4 Pedestrian Bridge and Ramps - Pond14D -
Source Update 20261010.FCStd`. Open it through
`tools/Open_B4_Current_Source.FCMacro` to preload its project controllers.

`current_source.update(job)` is the tested later-revision adapter. It uses the
existing bridge/end-bent geometry builders and changes both end caps to
212 x 42 x 36 in, end pedestals to 30 x 42 in, end pads to 2.5625 in, and pier
pipe embedment to 12 in. Cap elevations use actual retained-camber bearing seats
and the source's six-inch pedestal-center minimum. Existing superstructure,
ramps and terrain are preserved. The unfilled pier pipe envelope is deducted
from cap concrete; its nominal 0.625 in wall remains distinct from the source's
effective corroded 0.48 in analysis wall. `CurrentSourceRevision` selects this
behavior without changing legacy models. Geometry and source comparisons use
0.001 in; coordination failures remain failures.

`cap_cages.add(job)` builds both end-bent cages and the pier cage from exact-hash
selected cases. It calls the tested native `beam.native_rebar` constructor and
the tested beam-example hoop path helper. The fixed project geometry snapshot
is in `freecad_tools/vendor_cap_20261010`; its fingerprints are recorded in the
update report folder. It computes drawing geometry only, not structural design.
Native Arch rebars have linked analytic centerlines, live quantities and native
spreadsheet schedules. Changes to input counts synchronize stable bar IDs;
source run/end-grid details are editable JSON properties. Curved source drawing
chords are rebuilt as analytic arcs with exact bend geometry. The source's
135-degree hoop closure dimensions are modeled at the top-left corner using
the beam-example layout; that location is an explicit modeling assumption.

Each `CageEB1`, `CagePier`, and `CageEB2` group contains Inputs, Paths, Bars,
Quantities, Schedule and Checks. Input bar counts and sizes, cover and row
spacing drive regeneration. Source JSON is retained separately. Detailed run
changes go through TransverseRunsJSON, EndGridJSON and AddedBarsJSON; preserve
their explicit `_in`/`_deg` schema units. Routine mutations must call a tested
helper, use explicit document Names, record a transaction, recompute and verify
the full cage. Do not directly repeat the original creation jobs.

Native per-bar Amount, Diameter, Length and TotalLength, physical nominal solid
volumes, and US nominal lb/ft factors feed the live schedules. Counts and weights
are modeled quantities, not fabrication cuts: anchorage, omitted laps and waste
are not approved. Cap net concrete deducts embedded pile envelopes, not rebar.
Live cage check objects retain physical cover/clash failures and the separate
source pile-placement envelope screen. Nominal pile clearance passing does not
close the source tolerance-envelope failure. No check is disabled.

Verification: `tests/current-source.py`, `tests/cap-cages.py`,
`tests/cap-cage-dependencies.py`, and `tests/cap-cage-rollback.py`; detailed
results under `reports/bridge-source-update-20261010`. The native GUI save runs
in an isolated hidden process with project-local preferences and cache, carrying
forward existing view data. This is a disk-copy update, not a live RPC edit.
The final report and cold-reopen verification identify the remaining failures.
Working models still require explicit save authorization; these helpers do not
save them themselves.

## Linked terrain spot annotation

`add_terrain_spot` calls the tested `freecad_tools.terrain_spot.add` helper. It adds a native Draft text feature and linked geometric leader to an explicit Mesh terrain object, retaining full measured precision. Inputs require explicit document/object Names, a unique request ID, unit-bearing local X/Y, vertical datum offset, independently obtained expected elevation, text offset, font size and tolerance; geographic location and coordinate basis are explicit provenance. This helper does not determine or assume a missing survey CRS. Its label reads existing-ground elevation in US survey feet and follows the physical linked mesh on recompute. Nonidentity terrain placements and points outside the linked mesh are rejected. No extrapolation, mesh replacement, model save, or existing-object changes occur.

`tests/terrain-spot.py` passed physical triangular-face distance, independent elevation, native links, full original shape/link/placement/visibility and mesh preservation, forced rollback, terrain dependency updates and coverage-gap rejection. Report: `reports/terrain-point-20261005/helper-tests.json`; final disposable transactions `TerrainSpotFixture94c5ec93-rollback` and `TerrainSpotFixture94c5ec93-success`. Earlier dependency-test failures remain in their transaction records; the proxy now requests execution when included in recompute. Production placement at latitude 30.277492, longitude -81.617842 remains pending survey-CRS confirmation. No production annotation has been created.

## Pond 14D terrain and orthogonal geotechnical sections

Drawing clarification, 2026-10-05: the existing renderer now adds viewing arrows perpendicular to each plan cut and a LOOKING bearing/grid-azimuth note plus LEFT/START and RIGHT/END labels on every section. Transverse views look S31.252degE (148.748deg); longitudinal views look S58.748degW (238.748deg). Direction is derived from survey endpoints: forward = UP cross START-to-END. Independent observer-right checks prevent mirrored views. All 170 DXF arrow shafts are read back; all 85 original section geometry polylines and both elevation/terrain CSVs were compared exactly with the archived issue. `tools/check_geotech_view_revision.py` records this issue-specific check in `view-direction-revision-20261005.json`. No live FreeCAD model was accessed. Prior PDF, package and render helpers are preserved under `output/Archive/pond-sections-before-view-directions-20261005`. The reusable renderer and package helper retain these direction labels for future refreshes.

`add_verified_terrain_reference` calls the tested `freecad_tools.geotech_sections.add_terrain`. Production `jobs/pond14d-reference.json` was applied to `B4_Pedestrian_Bridge_and_Ramps` as transaction `pond14d-reference-20261003-v1`; do not repeat it. `Pond14DTerrain` is a separate Mesh reference with all 692 original triangles. Actual coordinate error is 0.0078044 mm, below 0.001 in. Existing native model geometry, expressions, links, placements and visibility are exactly preserved. The helper verifies source/cache/placement hashes, scoped recompute, independent mesh coordinates, and injected exact rollback. It never saves the working FCStd. Tests: `tests/geotech-terrain.py`, report `reports/pond14d-sections-20261003/terrain-helper-tests.json`.

`capture_geotech_sections` calls the tested read-only `geotech_sections.capture` against an explicit document Name and a new project output directory. It snapshots all 46 finished MSE concrete native BReps, source properties, slab boundary/PGL keys and wall profile breaks while checking exact live preservation. Bridge components are outside this ramp-specific capture. Do not use stale saved FCStd geometry for current terrain studies.

`freecad_tools.geotech_section_engine.generate(job)` is the tested disk-only engine. `jobs/pond14d-sections.json` points to the latest verified live snapshot, original terrain caches and verified survey placement. Explicit dimensions are `25 us-ft` spacing, `100 us-ft` pond-side extension, `25 us-ft` other context, `0.001 in` curve/plane tolerance. Original TIN edges are intersected, never retriangulated; coverage gaps remain gaps and inconsistent/degenerate intersecting triangles fail. Key cuts and maximum spacing are checked. Native solid sections preserve the adopted curved slab surfaces; export approximation error is independently bounded. `tools/check_geotech_sections.py` independently tests all top labels against native BReps, all terrain profile points against original triangles, and the current B5/B8/B9 top/thickness baseline. All 46 components have top labels.

`Refresh_B4_Pond_Sections.ps1` is the tested no-AI launcher: capture current explicit main, generate, independently validate, draw PDF/DXF/CSV and package. `-UseExistingSnapshot` skips live capture. It uses pinned MCP and existing runtime dependencies only, performs no model save/edit and has no retry loop. Current baseline guards B5/B8/B9 at 22.172 international ft and six-inch thickness. Any future design change to that baseline requires an explicit revised validation job, not bypassed checks. PDF plan tables support up to 24 cuts per ramp/family and fail if exceeded; a larger plan requires a pagination adapter. Render/review each regenerated PDF before issue.

Latest issue: 85 sections, 91 PDF pages, 2,112 key callouts. 16 cuts intersect Pond 14D; B-T09 through B-T11 include EL 9.000 ft. All cuts have complete existing-ground coverage and at least 100 ft pond-side footing extension. Geometry/DXF checks PASS; existing 12 bridge/MSE clashes remain FAIL. Soil layers, groundwater and structural design are NOT CONFIGURED. Source coordinate datum is unnamed in the pond XML; no independent datum shift is assumed. See `docs/B4-POND-SECTIONS.txt` and the session checkpoint for paths and exact results.

## B4 footing elevation and terrain reference

`update_b4_footings_terrain` uses the tested `freecad_tools.footing_terrain.update` helper. Job `jobs/footing-terrain-b5-b8-b9.json` was applied successfully to live `B4_Pedestrian_Bridge_and_Ramps` in transaction `footings-B5-B8-B9-terrain-20261003-v1`; do not repeat creation. It levels native B5 to its existing full-precision upper bench (22.172 international ft), raises B8 and B9 to that level, updates their native wall-base profiles, and adds the verified 5,239-facet local LandXML terrain mesh. Inputs require units. Terrain cache, LandXML and placement hashes are checked. The working model is unsaved.

Three native junction cuts remove overlaps created by the raise: B5/B6, B8/B5 and B9/B2. Original extrusions, profiles, expressions, placements and nominal links remain editable. Finished component references and fill dependencies follow the new cuts. The legacy bridge checker is excluded from recompute because its common operations mutate protected slab caches; bridge/MSE overlap checks run independently on deep BRep copies. Existing bridge geometry is unchanged, and its 12 coordination clashes remain FAIL.

`tests/footing-terrain.py` and `tests/footing-terrain-gui.py` passed 43 geometry, cover, quantity, link, precision and preservation checks, plus injected failure with exact rollback. GUI fixtures preserve neighboring footing visibility and restore group/member visibility in dependency order. Reports: `reports/footing-terrain-tests.json`, transactions `footing-terrain-test-b3e6ad39-rollback` and `footing-terrain-test-b3e6ad39-success`. Unsuccessful development fixtures are retained. No check tolerance was increased; face-to-face contact is measured directly because solid Boolean common excludes zero-volume contact faces.

The update never saves a working document. Terrain is a reference mesh, excluded from concrete quantities and solid OBM export. This adapter supports the prepared three-wall revision only; it rejects repeated creation and unexpected state. Do not reuse the production request ID for a changed job. See `reports/footing-terrain-session-checkpoint.json` for the current live state. Actual minimum cover to footing top is B5 2.2850657165, B8 2.4556112069, B9 2.4075411885 US survey ft. The original saved file has a verified byte-copy backup in Models/Archive. Previous PDF/DXF wall profiles and the OBM package still describe pre-update geometry.

### Missing project proxies after a recovered session

`restore_missing_project_proxies` uses `freecad_tools.restore_proxies.restore`. It restores only missing proxies for an explicit document from an exact-hash project FCStd archive. The fixed class allowlist supports only the known project classes with null serialized state; it does not unpickle external code or change application security settings. It checks all native nonproxy property contents, shapes, links, placements and visibility exactly and does not recompute geometry. Disposable tests in `tests/restore-proxies.py` verify success and forced rollback; report `reports/restore-proxies-tests.json`. Live recovery transaction `restore-b4-live-proxies-20261003-v1` restored 280 controls while preserving all other contents. Other recovered duplicate documents were left untouched. `tools/Open_B4_With_Connection.FCMacro` now imports the model modules before opening a saved model to prevent this startup failure.

## Read-only terrain / footing wall profiles

`analyze_terrain_wall_profiles` calls `freecad_tools.terrain_analysis.analyze(job)` against explicit saved source paths. This is a disk-model analysis exception to the live-document requirement: it does not open or alter the active FreeCAD document, and can run through the pinned FreeCAD Python without a GUI. Tested job: `jobs/terrain-wall-elevations-20261003.json`. Unit-bearing criteria are `2 us-ft` cover to footing top, `1 us-ft` increments, and `0.001 in` registration tolerance. No minimum tread is imposed. Physical model geometry, source triangle connectivity, full-precision coordinates and coverage are checked independently. Actual burial failures remain FAIL. The separate PDF/DXF wrappers draw only the resulting checked data. See `docs/B4-TERRAIN-PROFILES.txt` for limits and the no-AI launcher.

Import `freecad_tools` inside FreeCAD. Add `C:\Users\joshs\Desktop\CAD_AI` to `sys.path` once. Then use `freecad_tools.run(job_dict)` or `freecad_tools.run_file(absolute_json_path)`. An external system Python cannot execute these helpers. The external MCP interpreter is deliberately separate.

## Operations

| operation | targets | parameters / input |
|---|---|---|
| inspect_document | omitted | explicit document Name; returns count and identity only |
| inspect | explicit list | concise supported parameter and shape summaries |
| update_box | one Part::Box Name | Length, Width, Height; unit-bearing positive lengths |
| update_mixed_cage | one observed MixedCageInputs Name | allowlisted inputs below |
| validate | box or mixed-cage input Names | requested checks; full report stored locally |
| check_pair | two shape object Names | minimum_clearance, e.g. 1 in |
| check_cover | shape then native box host Names | minimum_cover, e.g. 3 in |
| create_rc_beam | omitted | new document Name; unit-bearing beam parameters; no save |
| add_beam_end_hooks | BottomBars, TopBars | 90-degree main-bar hooks at both ends; explicit bend diameters and straight tail lengths |
| add_beam_drawings | BeamQuantities | two native 17 x 11 in sheets and a live FreeCAD schedule; preserves physical geometry |
| refresh_beam_drawings | BeamAssemblySheet, BeamDetailSheet | reapply tested sheet layout, recompute and validate without changing model geometry |
| add_beam_fdot_sheets | BeamQuantities | add symbolic R-03/R-04 views, live nominal weights and FDOT bar marks; preserve original model and views |
| refresh_beam_fdot_sheets | BeamFdotAssemblySheet, BeamFdotDetailSheet | regenerate linked symbolic views and check quantities, marks and cut symbols |
| export_beam_dxf | all four sheet Names, in R-01 through R-04 order | units: ft; fourteen 1:1 individual view DXFs plus two combined files in a new project directory; never saves the model |
| create_mse_ramps | omitted | new document Name, unit-bearing wall/slab/footing inputs, linked slope planes and explicit source handles; tested on a disposable document and B4_MSE_Ramps; no save |

All operations require `document`. Name lookup is exact; `{ "label": "..." }` is available only if precisely one object matches. Tolerance defaults to 0.001 in, must be a positive length, and is independent of display rounding and kernel precision. Volume comparisons use separate small absolute/relative numerical criteria. Do not increase tolerances to hide failures.

## PGL-controlled pedestrian bridge

`add_pgl_bridge` in `freecad_tools.bridge` adds a new `BridgeAssembly` to an explicitly named existing document, or creates and closes a disposable fixture when `disposable` is true. The tested production input is `jobs/bridge-production-v1.json`; it has already run against `B4_MSE_Ramps`. Never repeat creation or reuse its request ID for a different job. No working model is saved. Dimensional job values require explicit units.

`BridgePGL` exposes the PGL station/elevation inputs, deck dimensions, confirmed net cambers, bearing geometry, support dimensions and provisional foundation inputs. Native Python features retain links and regenerate editable BReps; `BridgeGeometryChecks` independently checks physical sections, slopes, cambers, haunches, counts, interfaces and original MSE connections. The engine preserves the user's notebook calculations, with a separately tested physical-bearing layout adapter. End stations are front faces of backwalls. Quadratic camber is anchored at actual bearing centerlines. The exact FIB36 profile, including curved fillets, follows the verified section.

The creation helper aborts invalid bridge geometry or changed existing source objects. This is also a coordination-model operation: valid bridge geometry from conflicting sources is retained with an explicit `BUILT — COORDINATION FAIL` result if bridge/MSE interfaces fail. Those failures are not waived or changed to PASS. The live check object and report preserve every positive overlap and landing gap. Existing MSE geometry is never auto-trimmed. Trial pile lengths, unconfigured pile embedment and inferred pier-wall thickness remain provisional.

Use `bridge.final_report('B4_MSE_Ramps')` for the tested read-only end check, including actual MSE walking-face grades and all 24 DXF slope annotations. It writes `reports/bridge/Bridge-model-check-report.txt` and `final-geometry-checks.json`. Tests are `tests/bridge-shapes.py`, `tests/bridge-superstructure.py`, `tests/bridge-integration.py`, and the disposable bridge fixture jobs. The dependency test verifies that a camber change propagates through beams, haunches, bearings, pedestals, caps, piles and pier wall while leaving the PGL deck unchanged, then restores the original geometry exactly.

After a future FreeCAD restart, load the project helper package as described at the top of this API before opening a model containing its Python features. Current bridge state and known conflicts are in `reports/bridge/session-checkpoint.json`.

### October 2 end-bent revision

`update_end_bents` dispatches to the tested `freecad_tools.end_bents.update` helper. Production job `jobs/end-bents-production-v1.json` has run successfully in `B4_MSE_Ramps`; do not repeat creation or reuse that request ID for another edit. It keeps the existing end-component object Names and native Python proxies, adds separate backwalls and cheek walls, and changes end piles to 18 in square concrete. Pier piles remain steel pipes. Working models are never saved.

Inputs are an allowlisted complete set of explicit unit-bearing end-support dimensions, plus the source DXF path/hash, source handles, assumptions, document Name and request ID. The helper rejects pending edits and checks the DXF hash. An end-only recompute preserves unrelated native geometry; all protected BReps, placements, links, labels and expressions are compared exactly. Only native Shape properties are hashed: FreeCAD 1.1 folders expose synthetic aggregate Shape attributes that create display caches when read. Folder membership is still checked through dependencies and all physical child shapes are hashed.

Tests: `tests/end-bents.py` / `fixture-test-v5.json` passed 277 checks; `tests/end-bents-rollback.py` / `rollback-and-dependency-test.json` confirmed exact rollback of native geometry, all PGL control contents, property names and object count after a deliberately injected failure. A 1 in PGL rise propagated to all 47 linked shapes, with the pier-wall bottoms retained at the fixed ground datum and their tops following the cap. Earlier failed development records are retained.

`bridge.final_report('B4_MSE_Ramps')` recognizes this revision and writes `reports/end-bent-20261002/revised/Bridge-model-check-report.txt` and `final-geometry-checks.json`. The final physical audit also measures pedestal seat heights and pad/cap contact. Production geometry passes; bridge-to-MSE coordination remains FAIL, including positive cap/cheek-wall overlaps and the existing landing gaps/elevation offsets. These failures are not waived or auto-trimmed. Pile tips remain provisional (90 ft trial lengths). Current revision state is in `reports/end-bent-20261002/revised/session-checkpoint.json`.

### Deck-end clearance at fixed backwall faces

`set_deck_end_clearance` uses `freecad_tools.deck_gaps.set_clearance`. The production job `jobs/deck-end-gap-production-v2.json` has run in `B4_MSE_Ramps`: the prior 0 in clearance is now 3 in at both ends. Front faces remain at stations 1593.22 and 1805.47 ft; deck ends are 1593.47 and 1805.22 ft. Only the two native deck solids change. PGL/support datums, backwalls, beams, haunches and MSE geometry remain fixed. `BridgePGL.DeckEndClearance` is editable, and `BridgeGeometryChecks.DeckBackwallClearances` displays measured gaps.

Jobs require explicit `document`, `request_id` and unit-bearing `clearance`. The current adapter supports positive gaps no greater than `BeamEndClearance`; larger gaps would need separate haunch/support treatment. It reuses the existing crowned PGL deck-solid helper. Decks recompute first; irrelevant downstream haunch touches are cleared before complete geometry/clash checks. Native geometry, placements, expressions, links and labels of all protected objects are compared exactly. Aborted edits restore native Shape properties directly, then refresh checks without regenerating unrelated geometry. No save is performed.

`tests/deck-end-gap.py` and `reports/deck-gap-20261002/fixture-v3.json` verify physical full-width end faces, 3 in horizontal and closest-solid gaps, fixed FFBW datums, deck-end PGL elevations, unchanged pier joint, preservation, and deliberate failed-edit rollback including control contents. Production v1 failed preservation and exact rollback after unnecessary dependent regeneration; that failure record is retained. The corrected staged update and fixture v3 passed, and production v2 passed 254 geometry/preservation checks. Final full audit: 294 bridge checks PASS, 3 coordination checks FAIL, 5 NOT CONFIGURED; MSE 236 PASS, 0 FAIL, 6 NOT CONFIGURED. All 12 actual ramp surfaces and 24 labels were checked. Nine positive bridge/MSE overlaps and the existing landing discrepancies remain explicit.

The final report now goes to `reports/deck-gap-20261002/Bridge-model-check-report.txt` and `final-geometry-checks.json`. Landing checks measure actual shortened deck ends and explicitly compare the horizontal opening against the requested 3 in joint. Larger MSE landing offsets and elevation mismatches remain failures; they are not waived by the intentional deck/backwall clearance.

Box checks always measure validity, physical dimensions in the object's local frame, volume, and transformed center. Assembly-specific checks are NOT CONFIGURED for standalone boxes. `validate` stores detailed checks and returns a short summary with report_path. For pair checks, any positive common volume is OVERLAP. Otherwise distance at/below tolerance is CONTACT / NEAR CONTACT; other pairs are SEPARATED. Required clearance is checked separately. Cover is measured in the box host's coordinate frame and includes solid containment; arbitrary non-box hosts are unsupported.

### Ramp slab centerline extension

`add_ramp_pgl_trace` dispatches to `freecad_tools.ramp_trace.add`. The production job `jobs/ramp-pgl-trace-production-v1.json` has run in `B4_MSE_Ramps`, adding `CompletePGLTrace` under `BridgeAssembly`. Do not repeat creation or reuse its request ID. It is a linked reference, not a physical concrete component, and does not save the model.

The helper requires exact PGL and ordered slab Names, a new object Name, a unique request ID, and unit-bearing tolerance. The current adapter supports this axis-aligned two-ramp layout with four A slabs and eight B slabs. Straight run centerlines turn square through landing centers; final landing legs align with the existing bridge PGL in plan. Every point is lifted onto the actual native slab-top face, not rounded metadata. The result contains three wires: 7 A-ramp edges, the existing 2-edge bridge PGL, and 14 B-ramp edges. Existing endpoint gaps/elevation offsets are retained without fabricated connectors. Source links regenerate the trace when slabs or PGL change; unsupported discontinuous ramp tops cause an error.

All 73 production checks passed: physical top-face containment, segment slopes, route positions, junction continuity, source links, rendering, existing bridge-PGL geometry, exact preservation of existing native BReps/placements/expressions/dependencies/visibility, and expected assembly membership. Tests in `tests/ramp-pgl-trace.py` / `reports/ramp-pgl-trace-20261002/fixture-v3.json` also verified deliberately failed-edit rollback, a 1 in source-elevation change propagating to the A trace only, and exact production preservation. Earlier fixture failures are retained: comparing copied versus uncopied child shapes introduced differing location/validation representations. The corrected test compares equally validated copies and retains exact serialization equality; no tolerance or preservation check was weakened.

Current trace results and unchanged interface discrepancies are in `reports/ramp-pgl-trace-20261002/Ramp-PGL-trace-report.txt` and `reports/transactions/ramp-pgl-trace-production-20261002-v1.json`. Existing bridge/MSE coordination failures remain in the separate full-model audit; passing reference checks do not resolve those failures.

### Reversible drainage trial

`create_drainage_trial` dispatches to `freecad_tools.drainage_trial.create`. The tested review job `jobs/drainage-trial-review-v1.json` has run once, creating the unsaved `B4_Drainage_Trial` from the current native `B4_MSE_Ramps` document. The original is exactly preserved and remains open. Discard the trial to roll back; never repeat the creation request ID. No save or source-model update is performed.

The user confirmed: crown fully removed by each PGL turn; a plane falling 1% toward the upper run; B landing extended to the fixed FFBW, retaining the 3 in deck joint; lower entrances held, allowing first-run grades to reduce. Actual upper PGL grades are -4.739879913576069% A and -4.825106600169804% B. The trial keeps the existing 1% transverse fall independently. A 120 ft blend limits upper-run longitudinal edge grades to below 5%; its transverse grade varies. Native source surfaces become editable B-spline patches while the slab extrusions, cuts, source links and thickness expressions remain native. `mse.height` dispatches only custom surfaces to their proxy evaluator; ordinary original surfaces retain the prior equation.

`DrainageTrial` exposes the toward-ramp `LandingSlope` and `RunBlendLength`. Plan positions and fixed lower-end datums are captured in `BaselineParameters`; legacy planar properties on the four trial surfaces are source history, not supported trial controls. Source-linked elevation objects use actual solid/vertical-line intersections. Seventy-two callouts cover all 48 ramp corners, 12 deck corner/crown points, and key PGL/transition points. Shared locations have combined IDs. Display precision is 0.001 ft; internal precision and 0.001 in geometry tolerance remain separate.

Review-build checks: 244 PASS, 0 geometry/annotation/preservation FAIL. The final disposable source-change/discard test passed 255 checks. One initial dependency test exposed a real 0.075 in lower-end corner step when the landing slope inadvertently changed the retained crossfall; the correction decouples those controls and retains every test/tolerance. Prior diagnostic records remain. Twelve bridge/MSE concrete overlap pairs remain FAIL (three new pairs), and no finished MSE/MSE pairs overlap. Curved landing geometry uses its dedicated validator; the original plane-only landing checks and modified DXF slope notes are explicitly superseded only in the trial. Hydraulic capacity, accessibility/code compliance, structural design and reinforcement are NOT CONFIGURED.

Report and checkpoint: `reports/drainage-trial-20261002/Drainage-trial-report.txt` and `session-checkpoint.json`. Elevations: `Elevation-schedule.csv`. Do not silently adopt this trial or auto-trim its clashes.

### Adopted main model, refreshed ramp PGLs and individual corner labels

`adopt_drainage` in `freecad_tools.adopt_drainage` is tested and registered. `jobs/adopt-drainage-main-v2.json` has run successfully. The current MAIN document is internally named `B4_Drainage_Trial` and visibly labeled `B4 Pedestrian Bridge and Ramps — MAIN`. The prior `B4_MSE_Ramps` document is labeled as the rollback configuration. This designation does not itself save either model. Consult `reports/drainage-adoption-20261002/session-checkpoint.json` for the subsequent explicit save decision.

The operation explicitly binds the tested curve updater, aligns both ramp endpoints to the actual bridge PGL, and adds separately selectable `RampAPGL` / `RampBPGL` references. The combined source remains native and linked, but is hidden to avoid double rendering. Twelve formerly shared ramp corner annotations are split, giving 84 callouts total and one callout for each of the 48 physical ramp slab top corners. Existing elevations, source links and full precision remain; layout and contrast are improved.

Adoption passed 289 checks, including exact preservation of all physical geometry, placements, links and expressions from the approved configuration. The first live attempt rolled back with verification after its older in-memory proxy class retained the prior Ramp B endpoint. The corrected helper explicitly binds the current tested class; the fixture reproduces this older-class condition. Do not repeat successful creation or reuse its request ID. Twelve bridge/MSE overlap pairs remain FAIL; no MSE/MSE pairs overlap. Main-model report and elevation schedule are in `reports/drainage-adoption-20261002`.

## Observed mixed cage

The adapter is intentionally narrow. It identifies the quantity object by its known TestIdentifier and explicit Inputs link, validates same-document source links and Arch Rebar proxies, and uses the supplied v0.5.1 source's geometry inspection functions. The copied reference macro is read as definitions only; its `main()` never runs. Changes go through the helper transaction API, never through the source macro's rebuild path.

Integer inputs: HBarNumber/LBarNumber (3–8); HCount/LCount (1–12).

Positive dimensional inputs: HInsideBendDiameter, HLeftLegLength, HRightLegLength, HSpacing, LSpacing, LLength, PlateWidth, PlateThickness, PlateHeight.

Signed dimensional inputs: HSetCenterY, HairpinX, HBendCenterZ, LSetCenterX, LBarZ, PlateOffsetX, PlateOffsetY, PlateBottomZ.

Derived properties and expressions cannot be overwritten. Minimum-clearance/cover thresholds and SectionY are not writable through this adapter. The existing observed cage thresholds are demonstration values, not code-derived requirements.

Core checks always reconcile native counts, nominal diameter, centerline path lengths, volume-derived lengths, physical solid centers, spacing/span, totals and live quantity fields. Optional checks: clearance (all reinforcement/reinforcement and reinforcement/plate pairs), cover, section (true intersections of straight-bar solids with the section plane), drawing_links. All are enabled by default for cage mutations. If the user explicitly requests a geometry-only study, specify checks `["geometry","quantities","placement"]`; omitted assembly checks are visibly NOT CONFIGURED. Do not silently select that reduced list to make a clashing design pass. Drawing links do not certify layout, annotation placement or drawing correctness.

## Results and recovery

Mutation results include status, document, targets, operation, changed properties with old/new values and units, recompute state, checks, warnings, transaction_id, rollback and report_path. FAIL includes errors; NO CHANGE avoids unnecessary model writes. Full records include requested inputs, timestamp, helper/FreeCAD version and diagnostics. Internal storage stays in millimeters and full precision; measured dimensions are also returned in decimal inches. The inspection formatter adds nearest-1/16-inch display values.

The helper refuses active edit/task/modal states and application transactions. It opens its own FreeCAD transaction, recomputes affected dependencies, validates, then commits. Failure aborts and independently verifies restoration. It never saves documents. An interrupted PREPARED/VALIDATED record is not proof of failure. Inspect the model before retry. An identical completed request_id returns its recorded result to avoid duplicate execution; this is request deduplication, not proof that later model changes did not occur. Journal files are not a model backup. Unexpected external save/export side effects cannot be undone by a transaction.

No-AI launcher: `freecad_tools.launcher.launch(path)` or Run_JSON_Job.FCMacro with its file picker. Both call run_file. Future thin tools can map inspect/update/check jobs directly onto run without duplicating logic. A custom MCP server/workbench and general-purpose drawing generator are outside this setup; the observed beam has the dedicated sheet adapter below.

## Illustrative reinforced-concrete beam creation

`create_rc_beam` creates a new document only and refuses to modify any existing document. See `jobs/beam-24x36x96.json` for all parameters and units. Use a new document Name and request ID for a genuinely new model. The default layout is an illustrative 24 in wide by 36 in high, 8 ft overall beam: four #8 bottom bars, four #6 top bars, four #4 horizontal bars on each side face, and sixteen #4 stirrups at 6 in spacing. Concrete is a native Part::Box, straight-bar centerlines are constrained sketches, and all bar solids use the native Arch Rebar proxy. The stirrup centerline is a parameter-driven feature with tangent arcs derived from the installed Reinforcement workbench's 135-degree-hook geometry. It is not a static replacement solid.

The `BeamInputs` object holds dimensions, counts, bar numbers, a 1.5 in minimum cover, a 1/16 in stirrup cover reserve, and a 1/16 in nominal assembly allowance. `BeamQuantities` has live source links and expressions. Supports, load design, development lengths, bearing, fabrication approval, and construction drawings are not configured. Straight longitudinal ends are schematic. With these short/deep proportions, a real design requires consideration of deep-beam behavior; this model does not establish adequacy.

Creation recomputes, checks physical BRep dimensions, diameters, volumes, counts, bar spacing, six-face cover/containment, all reinforcement pairs, and live quantities. Disjoint BRep bounds may prove minimum pair separation; other pairs use the shared exact distance/common-volume checker. Transverse bars may contact longitudinal bars but any positive overlap fails. Longitudinal bars have an explicit 1 in minimum clearance for this illustrative model. The check tolerance remains 0.001 in. Failure closes only the new document and retains its diagnostic transaction report. No model is saved.

Inspect with `inspect` targeting `ConcreteBeam`, `BottomBars`, `TopBars`, `SideBarsLeft`, `SideBarsRight`, and `Stirrups`; validate with `validate` targeting `BeamInputs`. Beam validation always runs all implemented checks, even when a reduced check list is supplied. Beam parameter mutation through this adapter is not yet exposed as a routine operation. The helper lives in `freecad_tools/beam.py`; the disposable regression is `tests/beam.py` and never saves test documents.

## Main-bar end hooks

`add_beam_end_hooks` in `freecad_tools/beam_hooks.py` adapts the observed beam's two straight main-bar sketches in place. It retains the original Sketcher objects, geometry-0 main lines, named length constraints, native Arch Rebar objects, source links, and live quantities. Necessary constraint and placement changes are recorded in the transaction. It refuses unexpected source topology, placements, or expressions instead of overwriting user customization.

The operation supports US #3 through #8 bars. Both ends receive 90-degree hooks; bottom tails turn up and top tails turn down. Explicit dimensional inputs are `BottomInsideBendDiameter`, `BottomTailLength`, `TopInsideBendDiameter`, and `TopTailLength`, all with units. Minimum inside bend diameter is 6db and minimum straight tail is 12db. The adapter reads the current actual bar sizes and verifies nominal diameter. The example `jobs/beam-main-end-hooks.json` reflects the observed #8 bottom / #5 top configuration, which differs from the original #6-top creation layout.

For clearance where the hook legs cross the side-bar elevations, the main-bar arrays move inward only as far as required by the existing longitudinal-clearance threshold plus assembly allowance. Concrete, side bars and stirrups are checked for unchanged physical geometry and source state. All prior beam checks remain active. Additional checks measure the two quarter-circle bends, straight tails, physical toroidal bend surfaces, total path lengths, and fully constrained sketches. Standard hook geometry does not establish development length or structural adequacy.

This mutation is transactional, writes a journal/report, supports identical-request deduplication, verifies source/geometry restoration after rollback, and never saves. Already-hooked sketches require inspection before a different edit; rerunning the same completed request only retrieves its report. Disposable regression: `tests/beam-hooks.py`.

## Beam sheets and visible quantities

`add_beam_drawings` creates `BeamAssemblySheet`, `BeamDetailSheet`, and `BeamSchedule` through the tested adapter in `freecad_tools/beam_drawings.py`. It reads the existing hooked beam. It does not run either supplied legacy macro, create replacement physical geometry, or save the model. The operation refuses duplicate sheet/schedule objects.

The assembly sheet contains original-source elevation, plan, and a native unfused transverse section at half the beam length. Concrete dimensions reference only the original host's edges. The detail sheet projects the original bottom, top, side-bar, and stirrup centerlines; native dimensions measure main-bar hook tails, centerline bend radii, and side-bar length. A linked `TechDraw::DrawViewSpreadsheet` displays the live schedule.

Visible schedule columns give bar mark, US size, physical count, nominal diameter, each centerline length, combined centerline length, and spacing. Summary rows show member dimensions, gross concrete, cover, and hook dimensions. Full-precision numeric source formulas remain in raw columns J:M; visible D:G cells only round presentation values to 0.001. Totals use original model quantities rather than sums of rounded display cells. Bar lengths describe modeled centerlines and are not approved fabrication cuts.

Creation recomputes the document and checks original shape identity, source preservation, independent physical quantity agreement, native dimension measurements, sheet frames, source links, physical plane cuts and drawn section circles. Sheet-layout review uses native SVG export and PNG previews under `reports/drawings`, not model saving. Numeric checks and visual review are reported separately. Geometry/code approval remains outside scope.

The native FreeCAD GUI requires pages to be shown and its event queue processed for threaded projection results. The adapter handles this without changing tolerance or disabling checks. Existing pages and spreadsheet formulas recompute with the model; a major model change may require a new layout review. Beam validation includes drawing checks whenever both sheets exist and fails an incomplete pair. Creation job: `jobs/beam-drawings.json`. Disposable test: `tests/beam-drawings.py`.

## FDOT symbolic beam presentation

`freecad_tools/beam_fdot.py` implements `add_beam_fdot_sheets` and `refresh_beam_fdot_sheets`. The observed hooked beam and both original sheets must exist. These operations never save. `jobs/beam-fdot-sheets.json` is the production request. `tests/beam-fdot.py` develops/checks the adapter on a disposable copy of the pre-FDOT document.

The source is the January 2026 FDOT Structures Detailing Manual, Sections 4.3, 4.3.7 and 4.3.10 (PDF pages 454-458), plus FY2026-27 Specification 415-7.2. The reference PDF is retained in `reports/references`. The implementation follows the requested drafting conventions, not the entire FDOT CADD-delivery or construction-document standard. Structural, development, bearing/support and fabrication approval remain NOT CONFIGURED.

R-03 adds source-linked symbolic elevation, plan, and mid-length section. R-04 adds symbolic bar details and an editable live weight schedule. Scale is 3/8 in = 1 ft (1:32), below the SDM threshold for single-line bars. Graphics use native ArchRebar centerlines and unbroken strokes. End-on straight segments become filled circles. Coincident strokes merge in projection. First/last stirrups represent the array in plan/elevation; the callout provides actual count/spacing. The section shows every longitudinal bar at the actual mid-length cut and projects the nearest stirrup, explicitly noted on the sheet. Section-dot locations are independently compared to circles cut from original solid geometry.

The v2 elevation uses the requested stirrup convention: one vertical stroke at each shown stirrup's nominal station and filled circles at both native centerline height limits. Tagged roles are `stirrup-elevation-line` and `stirrup-elevation-end`; plan, section, bar details and longitudinal projections retain their existing shapes. Checks independently compare the two strokes and four endpoints with physical stirrup solid bounds minus nominal bar radius, and confirm longitudinal projection preservation. `jobs/beam-fdot-stirrup-elevation.json` refreshes an older open document without saving it.

Source-linked App::FeaturePython generators produce SVG strings on recompute. Native TechDraw::DrawViewSymbol objects reference those strings by expressions; source geometry is neither replaced nor flattened. Display tessellation affects only SVG curves, never the model. The installed DrawViewSymbolPython wrapper cannot be passed to page.addView, so it is not used. Symbolic dimensions measure original physical out-to-out extents and display inch values; exact geometry remains unchanged.

Native rebar `Mark` expressions combine current US bar number with A (bottom), B (top), C (both identical side patterns), D (stirrups). With the present sizes these are 8A, 5B, 4C and 4D. Native object Names and labels stay unchanged. The side sets retain their separate objects and are combined only in the FDOT schedule. Original `BeamSchedule` column A now references live native marks, column H shows model weight, and original detail headings are size-independent.

`BeamQuantities` contains per-set nominal lb/ft factors, full-precision modeled weight, nearest-inch listed lengths/weights, and `TotalRebarWeightLb` / `TotalListedRebarWeightLb`. Weight factors for #3-#8 are 0.376, 0.668, 1.043, 1.502, 2.044 and 2.670 lb/ft. Unsupported sizes fail checks. Factors update with size; model weights use original full-precision centerline lengths; listed weights use each length rounded to the nearest inch. Display cells round only after totals are evaluated. There is no waste, coating or tie-wire allowance. These are nominal calculated quantities, not weighed material or approved payment quantities.

Checks include exact analytic BRep/source preservation (excluding the authorized Mark expressions), independent volume-derived centerline quantities, native centerline sample containment, physical section/dot correspondence, mark/weight/rounding formulas, source links and paper geometry bounds. Full beam validation also includes FDOT checks when both new sheets exist. Incomplete page pairs fail. No existing cover or clearance check is disabled. Visual layout review and live count/size update tests are recorded separately.

## Beam DXF handoff

`export_beam_dxf` requires explicit targets `["BeamAssemblySheet", "BeamDetailSheet", "BeamFdotAssemblySheet", "BeamFdotDetailSheet"]` and `units: "ft"`. The adapter currently supports these observed orthographic, unrotated views. Run `jobs/beam-dxf-feet.json` through the shared JSON launcher. Optional `output_directory` must be a new directory inside CAD_AI; otherwise a new directory is generated. Existing output folders are never overwritten. Optional `include_previews: true` adds SVG/PNG renders and can take several minutes for dense hidden geometry. It defaults to false. All DXF validation remains enabled regardless of preview selection.

The helper recomputes, runs the existing full physical/drawing validation, then writes fourteen individual views plus two combined model-space DXFs. Native `getVisibleEdges(False)` and `getHiddenEdges(False)` return paper-scaled, Y-down projection edges in the installed FreeCAD version. The helper removes each view's scale, reverses Y, converts millimeters to international feet, and translates each view's lower-left bounds to the origin. It preserves LINE/ARC/CIRCLE/ELLIPSE/SPLINE geometry. This avoids the extra edges observed in the installed standard TechDraw DXF writer. The symbolic adapter reads only explicitly tagged geometry from the linked SVG, removes its 1:32 scale, and writes the existing centerline polylines, concrete outlines and filled-circle symbols. No sheet furniture or dimensions are exported.

DXF R2010 uses `$INSUNITS=2`, decimal `$LUNITS=2`, zero insertion base and Z=0. Concrete uses `BeamConc` / `BeamConc_h`; reinforcement uses `Rebar` / `Rebar_h`. These exact names are verified against the October 25, 2023 FDOT level workbook; provenance is in `reports/references/fdot-dxf-levels.json`. Combined files retain the same names without prefixes; `CAD_AI` XDATA stores material, visibility, view and role, and the manifest records view offsets. Apply receiving FDOT workspace symbology in OBM: DXF color/weight indices are not Bentley indices. End-on circles use a solid HATCH plus matching CIRCLE boundary. Original R-02 bar details are centerlines and remain so in the full-geometry set.

Native material classification is restricted to the observed concrete Part::Box and verified orthographic axes. It checks the physical concrete rectangle against the native projection, including four visible and four coincident hidden concrete edges in elevation/plan (four visible in section). Other projected edges must be strictly inside that rectangle and are reinforcement; full physical cover checks also remain enabled. No native edge is discarded. The classifier avoids `projectPoint` and `getGeometricCenter`, which changed serialized source BRep state during development on FreeCAD 1.1.3. Exact source-preservation checks remain enabled at their original threshold.

Every written file is read back and audited without repairs. Native curves are compared with original projected BRep edges in physical millimeters, including endpoints, at the unchanged job tolerance. Filled-circle boundaries, counts, units, model-space flatness and original source/BRep preservation are checked. The manifest includes entity counts/types, layers, extents, offsets and SHA-256 hashes. DXFs are dated snapshots, so rerun after changing a model. No model save occurs. Transaction logs are under `reports/transactions` and the shared change journal.

`beam_dxf.queue_package_previews(directory)` provides optional asynchronous GUI-loop rendering of an existing verified package. It checks DXF hashes and writes `preview-status.json`. Poll that file; do not repeat a QUEUED/RUNNING request. It accesses only exported files, not model documents. Use this for previews longer than the MCP response limit. A GUI timeout during an ordinary helper call is still an unknown outcome: inspect the recorded transaction and actual files before retrying.

Development validation: `tests/beam-dxf.py` exports a disposable copy and restores the active document. `tests/beam-dxf-handoff.py` independently parses the delivered ASCII DXFs and verifies nominal 8 x 2 x 3 ft fixture sizes, units, filled symbols and manifest hashes. A separate attempted preview-reuse comparison at 1e-10 ft failed because independently recomputed HLR projections were not identical; the failed test and diagnostic are retained. Production previews were therefore rendered directly from the production files, with no tolerance change. See `docs/DXF-OBM.md` for handoff instructions. Bentley import itself is NOT CONFIGURED.

The v2 fixture is `tests/beam-dxf-fdot-v2.py`; independent delivery checks are `tests/beam-dxf-fdot-handoff.py`. Production symbolic refresh passed 57 checks, and export passed 261 checks with zero failures and four design/fabrication checks NOT CONFIGURED. Reports retain the earlier development failures and successful final disposable test. Native geometry and quantities were preserved exactly across the production refresh/export, excluding the authorized symbolic SVG change.


## Verified STEP export for the MSE ramps

`export_step` in `freecad_tools/step_export.py` exports explicit object Names into a new directory inside CAD_AI. Use `jobs/mse-concrete-step-survey-feet.json` as the completed example. Repeated exports require new request IDs and output directories. Export `MSEAssembly.FinishedConcrete`, not whole-document groups that include duplicate source geometry.

Supported unit identifiers are `mm`, `ft` (international feet), and `us-ft` (U.S. survey feet). The installed OCCT 7.8 writer was measured to emit unchanged millimeter numbers tagged as INCH, causing a 25.4-fold size error. Stored preference changes alone did not change cached runtime units. The helper temporarily sets runtime units explicitly, then restores them. Feet exports compensate for the observed writer behavior on detached export snapshots; U.S. survey feet explicitly declare 1200000/3937 mm per unit. No geometry coordinates are text-edited. The editable source model is never rescaled or saved.

AP214 files are independently read back as physical BReps. Checks reconcile solid counts, validity, unique matches, bounds, vertices, volumes, areas, all twelve walking-face grades, and each horizontal pad's 6-inch thickness. Source BRep hashes, native types, expressions, dependencies, placements, labels and visibility must remain unchanged. Different writer behavior must fail validation rather than be assumed compatible. Fixtures: `tests/step-mm.py` and `tests/step-feet.py` (the latter checks U.S. survey feet).

Transaction `mse-concrete-step-survey-feet-v2-20261001` passed 84 checks, zero failures. Bentley import remains NOT CONFIGURED. Import at 1:1 into the U.S. survey-foot 3D DGN and measure a footing: exactly 6 international inches equals 0.499999 U.S. survey feet. Coordinates retain the existing local model frame; project survey placement has not been applied.

Optional schematic fill is excluded. The preceding combined export failed to reconcile a nearly zero-width solid in `B_MiddleRunFill`. Diagnostic `mse-step-survey-feet-v1-20261001` is retained. No tolerance was changed or failed check waived. Existing design/modeling limitations remain in the MSE production report.

## Explicitly authorized native main-model save

`save_main_with_rollback` in `freecad_tools.save_main` is tested on disposable native objects and expressions. It requires explicit authorization, exact open document Names, three distinct native FCStd destinations within CAD_AI and a new request ID. It copies the prior disk file byte-for-byte, saves the previous live configuration to a new rollback file, then saves MAIN to the authorized main path. It verifies archive integrity/object names and exact live geometry, placements, links and expressions, with staged file journaling. Unknown or failed save outcomes must be inspected before retrying; saves cannot be rolled back with a document transaction. Other modeling helpers still never save.

`jobs/save-drainage-main-v1.json` has run successfully after explicit user approval. MAIN is saved in `Models/B4 Pedestrian Bridge and Ramps.FCStd`; the previous configuration and original disk backup are in `Models/Archive`. Reopening a disposable copy verified all 386 objects, 271 native shape properties and 280 editable Python proxies, with no pending objects. See `reports/drainage-adoption-20261002/session-checkpoint.json` for exact paths. Do not repeat the successful save job.

## Ramp PGL curve/display refresh

`refresh_ramp_pgl` recomputes existing adopted ramp references through their tested proxies and sets native display tessellation using explicit percentage and angle strings. It audits the visible native curves against physical slab tops, measures rendered chord deviation, checks protected native geometry/annotations exactly, and journals without saving. `jobs/refresh-ramp-pgl-v1.json` passed 40 checks in B4_Drainage_Trial; do not repeat it. Before refresh, the curves were geometrically correct but rendered as straight landing chords; display settings are now 0.01% and 1 deg. Native top mismatch is below 0.001 in, independently of display approximation. Disposable success and forced rollback tests passed. Exact rollback retains original native wrappers, avoiding Shape.copy location-table normalization. Current report: `reports/drainage-adoption-20261002/Ramp-PGL-refresh-report.txt`. Latest refresh is unsaved.

## Reusable B4 OBM package export

`export_obm_package` uses tested `freecad_tools.obm_export.export`. The no-AI entry point is `Export_B4_To_OBM.FCMacro`; it explicitly targets the active document Name and checks all required B4 objects. Each omitted request_id/output_directory is generated uniquely. Production `jobs/b4-obm-package-v1.json` passed 269 checks; the full disposable fixture also passed, preserving its working source. See `docs/OBM-EXPORT.txt` and `reports/obm-export-20261002/session-checkpoint.json`.

The exporter calls `export_step` with `writer: native_units`, then independently reads the STEP and 3D DXF. The native STEP adapter uses `tools/native_step_writer.py` in the existing bundled FreeCAD Python, isolated from the GUI, and preserves component product names. Do not use the older downscaled-shape route for cambered beams/pedestals: the retained development file failed validity despite matching gross dimensions. Do not instantiate XDE/OCAF inside FreeCAD: the development test reset the document session. Main and rollback were reopened and the latest unsaved PGL display restored through the tested helper. Source colors are recorded in the manifest.

Validation measures analytic bounds with triangulation disabled, solid count/validity, physical dimensions/volume/area/vertices, 6-inch footing thickness, curved slab grids, actual PGL-to-top-face distances, exact 3D spline roundtrips, annotation text and coordinates, and source preservation. No tolerance was loosened; the same 0.001 in limit applies. The imported curved landing had a spurious vertical-ray intersection exactly at a spline knot; its actual upward-face distance was near zero. Direct physical face distance is therefore used. Geometry/annotations passed; Bentley import itself remains NOT CONFIGURED, and the 12 existing overlaps remain explicit. Current exports use local model coordinates and US survey feet. Neither the editable model nor project placement is changed or saved.


## Notebook camber file update (12 October 2026)

`notebook_update.update_file` is a file-only adapter. It verifies the notebook
export fingerprint, updates a disposable copy through the existing bridge and
reinforcement controllers, compares the native engine with the exported
polynomials and saved solid sections, and preserves unrelated native records.
It does not modify a live working document or install its candidate. Cold reopen
and exact source/candidate checks precede installation with `file_install.install`.
Geometry validation and detailing/coordination failures remain separate.
`native_archive.preserve` now accepts an already restored WallRebarProxy and
continues rejecting unknown wall controllers.


## Pedestal U-bar grids (12 October 2026)

`freecad_tools.pedestal_ubars` controls the six `PedSteel*Inputs` objects and
their native paths, rebars, live quantities and schedules. Dimensions require
explicit units. Signed local placement controls use PropertyDistance. Spacing
is the mean each-way pitch; user-authorized local intervals may differ by up
to one inch while retaining the mean. Current intervals are 5.25 to 6.75 in.

For an editable disposable copy, call `regenerate(inputs)` after an input edit,
then `validate(inputs)` for physical geometry, spacing, cover and development,
and `clash_check(document, all_six_inputs)` for all new bars against existing
steel and piles. Any positive common volume fails; surface contact is allowed.
`PedestalSteelChecks` is a dated snapshot and must be rerun after edits.
The adapter supports the documented #4, uncoated Grade 60, normal-weight,
straight tension development basis. Unsupported materials/detailing reject.
`prepare_file` only creates a disposable native candidate; it does not overwrite
the authoritative model. Intentional main-file saves require authorization.


## Adopted DXF/MSE and centered cheek reinforcement (14 October 2026)

The matching mse_revision, mse_corrections and mse_wall_tops controllers retain
editable copings, barriers, level returns, cheek webs/lugs, mitres and top-step
interfaces. The selected source DXF is ../details/B4 Pedestrian Bridge - Working.dxf
relative to the freecad folder. Historical creation jobs are not live-edit commands.

cheek_steel.InputsProxy controls the four single centered cheek mats. Use the
existing native paths/rebars and linked schedules; refresh(inputs) resynchronizes
the mat, and validate(document) checks physical solids, cover, centering, spacing,
quantities and wall/cap-steel clashes. CheekSteelChecks and WallSteelChecks are
dated snapshots. Rerun checks after edits. Anchorage/laps/lug steel are not detailed.
The cap cages retain the selected cases' length and remain centered when concrete
caps are widened; their engineering redesign is a separate unresolved item.


## End cap / cheek combined envelope (14 October 2026, D-027)

end_cap_revision.update(doc, job) uses the existing cage inputs/synchronizer on
an explicit disposable file copy, with checked source hashes and 0.001 in
tolerance. The native file-copy preservation and cold-reopen workflow is required
before installing a candidate. It does not move concrete or cheek bars, and
does not save the main model. Detailing failures remain recorded.

CoverConcrete links the cap and both cheek solids; the cover checker requires
one connected valid union and measures the actual envelope. Pile sockets retain
separate C_pile checks, distinct from exterior concrete cover. Cage paths remain
native and all source-case, schedule and quantity dependencies remain editable.


## User-directed cap / cheek coordination (D-028)

`cap_cheek_coordination.update(doc, job)` requires a disposable file copy, a new
request ID, explicit unit-bearing stations and the existing 0.001 in tolerance.
`VerticalStationsJSON` defines stable cheek MV IDs and centerline offsets from the
web's local X minimum. Omitted IDs are removed through the existing synchronizer.
`TransverseStationOverridesJSON` maps existing hoop IDs to cap-length stations.
The original `SourceCaseJSON` and `TransverseRunsJSON` are preserved. Overrides are
applied by the native cap layout controller and are separate from selected cases.
For future case replacement, review these deliberate CAD overrides explicitly.

The exact original records of other objects are retained with `native_archive`.
Full nominal-solid checks are required because the hooked hoop projects beyond
its nominal station. The helper never installs the main model or suppresses
remaining overlap/cover/pile findings. Verified dependency tests exercise hoop
station movement and removal/restoration of native cheek bars on a discarded copy.


## Horizontal cheek station overrides (D-029)

`HorizontalStationOverridesJSON` maps existing MH IDs to unit-bearing heights
above the main web bottom. The native layout, path and rebar controllers apply
these editable overrides. All other rows keep their generated positions.
Covered-web limits remain enforced; full physical and spacing checks are still
required. D-029 intentionally records four 12.375 in spacing failures against
the existing 12 in maximum, as directed by the user. No limit is relaxed.


## Cheek lug WWR (D-030, 14 October 2026)

`lug_wwr.add(doc)` creates the accepted 4x4 W1.4xW1.4 layout once in an explicit
document. Do not replay it on the current model. Four linked Inputs objects drive
eight separate Bottom/Side groups, 172 native Arch wires, analytic editable paths,
live sheet quantities and the CheekLugWWRSchedule. Each input is linked to its
existing cheek, cap and cage frame. Length dimensions require units; signed local
Z coordinates use native Distance properties. Wire diameter is nominal 0.134 in.

The bottom mesh has a 1 in centerline fold radius, extends 8.875 in into the cap,
and uses the accepted 0.625 in along-fold / 0.875 in across-sheet grid offsets.
Side mesh laps 8.125 in past the outer cheek vertical. Both include two full
4 in squares. Minimum cover is 2 in; measured minimum is 2.125 in. Nominal
weight uses W1.4 area 0.014 in^2 and 490 pcf; length excludes fabrication waste.

After a deliberate parameter edit, recompute the WWR objects and run
`lug_wwr.validate(doc)`. It checks nominal solids against existing steel, piles,
the combined cap/cheek exterior and other sheets. Factory-welded crossings
within one sheet are identified separately. Check objects are dated snapshots;
changed geometry requires fresh physical checks. No existing steel is moved.
All 1677 prior native object/view records are preserved. Cold reopen restores
all wire controllers; changing bottom extension by 0.25 in changes ten wire
lengths and the live schedule total by 2.5 in. This is modeled geometry, not
development, weld, bend, fabrication or structural design approval.

The 14 U-bar/hoop overlap pairs remain Deferred in COH-025. The four 12.375 in
cheek spacings stay Open in COH-024; cap/backwall and other findings remain.
# Deck edges and barrier setback — 15 October 2026

`freecad_tools.deck_edge_details` provides opt-in native `DeckEdgeProxy` and
`DeckBarrierProxy` controllers. The DXF source hash and exact native properties
are stored on the two decks and four original deck barriers. These controllers
retain source links, PGL and end limits; the final barrier contact objects retain
their existing deck cuts. The existing controllers are unchanged for objects
without these properties. Bridge quantity validation deducts the independent
analytic section area of four chamfers and two V grooves, at the prior tolerance.

`configure(doc)` installs 0.75 in chamfers, a 1 in wide / 0.5 in deep groove at
3 in along the soffit, and 1.5 in horizontal barrier setback. It is restricted
to the expected B4 objects and does not save. `refresh(doc)` updates affected
physical elevations, leaders and the live concrete schedule. Call only in a
clean document and a caller-owned transaction/disposable copy; it clears touches
generated by these edits to preserve unchanged haunch and reinforcement Shapes.
`measure(doc)` checks physical sections, volume deductions and barrier offsets;
`overlaps(doc)` checks positive-volume intersections involving the six final
changed solids against finished concrete, barriers and native reinforcement.
Existing unrelated engineering and reinforcement findings remain in force.


# Model cleanup — D-032, 15 October 2026

`model_cleanup.apply(doc, report_path)` removes only the explicit 42 audited
superseded boolean stages, after checking native links, current physical
selections, string references and dependency order. It hides 610 retained
reinforcement paths in 19 groups plus the nominal pier envelope and duplicate
complete PGL source. It does not save or change physical geometry, engineering
status, colors, native controllers or source inputs. A report path cannot be
reused. Transaction failures roll back and retain diagnostics.

Native BReps, placements, expressions and retained dependencies are compared
exactly. Avoid writing unchanged group visibility: FreeCAD can rebuild a group
shape cache and alter shared source flags. `preserve_archive` uses the existing
native archive helper to preserve original resource precision through save,
changing only audited group memberships and visibility. Test in a disposable
copy, verify exact native records and a cold reopen, then adopt with a backup.


# Return and cheek connections - D-033, 15 October 2026

`return_cheek_details.configure(doc)` installs four shared editable controls,
raised native cheek controllers, deep return lower bands and native coping
stop/contact wrappers. Use once on a disposable copy. `refresh_dependents(doc)`
updates the cheek mats, lug WWR, affected labels and live schedules. It retires
the duplicated B7 labels and empty return plinth shapes. No save is performed.
`inspect(doc)` reports affected concrete intersections without suppressing
existing coping/wall overlaps. Shared BaseElevation avoids a cheek/wall/return
dependency cycle. CopingStopBasis is the outer rear lug face. Physical
reinforcement checks use the existing cheek_steel and lug_wwr validators.

`return_cheek_details.close_return_voids(doc)` adds two editable landing
wrappers and deepens the four outer return legs. It continues the original
4-inch surface, preserves the original slab material, and trims shared concrete
against existing walls, copings and the adjacent slab. Run on a disposable copy.
`refine_void_contacts(doc)` rebuilds those explicit ownership cuts. Native spline
trim edges are retained where unification produces invalid topology.
`viewing_palette.apply(doc)` colors each face of the 750 finished physical
objects, preserving geometry, visibility and transparency.
D-034 corrects the finished landing NetVolume fields; COH-027 is closed.
The default Shape.Volume for those two solids remains unsuitable for quantities.

# Curved landing quantities - D-034, 15 October 2026

`landing_quantities.measure(shape)` validates a closed solid and returns the
verified quantity plus integration evidence without modifying its geometry.
It uses the PythonOCC bundled with FreeCAD 1.1.3; its OCCT version must match
FreeCAD (tested 7.8.1 / PythonOCC 7.8.1.1). Missing or mismatched dependencies
fail explicitly; no package installation or fallback to raw Volume occurs.
`update(obj)` maintains read-only NetVolume, VolumeMethod and VolumeStatus,
with hidden VolumeCheckJSON evidence. ReturnLandingProxy calls it after each
shape rebuild. Status is Needs review until successful integration.
`refresh(doc)` updates only A_BridgeLandingAtReturns and B_BridgeLandingAtReturns
in one transaction, verifies unchanged BRep strings, and returns a receipt.
It does not save. The caller records the receipt with the project change journal.
Use NetVolume, not Shape.Volume, for those two finished landing quantities.


## D-044 square bridge edges and end-bent weather closure

`standard_chamfers.apply(doc, report_path, request_id)` updates only the two decks, four beam bottom-corner sections and six pedestals, retaining nominal chamfer inputs. `BridgePGL.OmitStandardChamfers` controls omission of exactly 3/4-in standard cuts. Use the tested scoped rebuild; avoid blanket reinforcement regeneration that resets SDM marks.

`end_bent_closure.add(doc, thickness="4 in", slope="2 %")` creates the new closure once in a caller-owned transaction or disposable document. It does not save. Existing closure inputs are edited natively; do not repeat creation. `ClosureEB1Inputs` and `ClosureEB2Inputs` link to the cap, PGL and three wall profiles. Slab thickness is vertical; DrainageSlope is numeric percent. Front coping top equals slab low top, side coping tops follow the slab plane, and coping seats remain on the panels. Native quantity schedule uses the eight NetVolume properties. Validate actual BRep thickness, slope, panel seating, cap/coping contacts and affected interferences after changes. No strap, joint or reinforcement design is inferred.

`geotechnical_straps.add(doc, width="2 in", projection="6 ft", elevation_above_cap="18 in")` creates one zero-thickness reference face per backwall in a caller-owned transaction. It uses the actual vertical fill-side backwall face (not the EB1 landing-seat bounding box), cap top and PGL frame. No save, steel quantity or design spacing is inferred. Native Width, Projection, ElevationAboveCap and LateralOffset remain editable. Full attachment-edge lengths use BRep section; face/solid common omits the lower-dimensional touching boundary.

D-045: `geotechnical_straps.match_report_layout(doc, offsets, source_sha256)` applies the seven unit-bearing lateral offset strings extracted from selected Figure B2, retaining the existing central reference Names. Native LateralOffset uses signed App::PropertyDistance; App::PropertyLength clamps negative offsets. The helper adds only missing reference faces and refuses duplicate creation. Final supplier layout/design remains separate. All reference dimensions and full attachment edges are independently verified after save/reopen.


## D-046 horizontal cheek hooks

`cheek_hooks.configure(inp, settings)` installs the native hook input proxy on a disposable copy. HorizontalHooksJSON selects start/end hooks with unit-bearing centerline offsets from the cap end face and explicit receiving object names. HookInsideDiameter and HookTailLength are native editable lengths; #4 minima are 3 in and 6 in. Call `cheek_hooks.refresh(inp)` to rebuild changed native paths/bars and refresh quantities/schedules while retaining unchanged bar BReps, then `cheek_steel.validate(doc)` and `lug_wwr.validate(doc)`. The same retained straight mat layout controls spacing/elevations. The validator measures actual analytic arcs, straight tails, receiver penetration, combined concrete cover and intersections against all existing rebar/WWR. Boolean cover operations use the PGL frame to avoid large-coordinate kernel failures. Cap hook tails also retain at least 3-in end/top/bottom cover. Standard hook geometry does not prove required development or connection capacity. Existing unrelated failures are retained. New hook shapes have distinct SDM marks; existing DXF must be regenerated.


## Pedestal edge/contact controls (17 October 2026)

`pedestal_edges` adds native maximum-spacing station lists; `pedestal_contact`
uses the existing native paths/bars for specified embedment and horizontal layer
contact. `UseSpecifiedEmbedment` selects the `SpecifiedEmbedment` length (12 in);
`LayerClearance` is 0 in. Prior computed-embedment documents remain compatible.
`pedestal_ubars.validate`, `pedestal_contact.detail_checks`, and
`pedestal_edges.alignment_checks` validate the physical detail. `clash_check`
rejects every positive common volume. The inherited `development` calculation
and `DevelopmentStatus` are tension-based diagnostic results. User acceptance
and compression-only action are recorded in D-047 and the adoption disposition;
compression development has not been recalculated by these helpers.


## Backwall extensions (D-048, 17 October 2026)

`backwall_extensions` controls both backwall input objects. The two explicit
`ReceiverCheeks` links drive the outer faces; `ExtensionEndCover` is 3 in.
`AddEndVerticals` adds one #5 per face at each end, using the adjacent native
vertical length and bar mark. `HorizontalLevelAdjustmentsJSON` lowers EB2
F1H05/F2H05 by 0.125 in for cover. `BaseLayoutJSON` retains the selected analytic
mat geometry; original material/grid controls are guarded against silent changes
and require an explicit rebase. Native bar paths and quantities remain editable.
Use `cheek_hooks.refresh(inputs)` and `backwall_extensions.validate(inputs,
before_shapes)` after edits. Cover is measured to the combined backwall/cap/cheek
concrete. Positive overlap is rejected; unchanged historical overlaps, if any,
are reported separately. External drawings are not automatically regenerated.
