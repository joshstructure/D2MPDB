# Current verification · 2026-09-30

Independent positive regions add bar sizes, areas, centroids and physical pile-head geometry. The 103-test suite passed; 16 focused regional and notebook-rerun checks also passed with Colab's ipywidgets 7.7.1 / Plotly 5.24.1. The clean four-cell notebook executed successfully. In local JupyterLab, a native numeric-input change to seven pile bars updated the pile drawing while the between-pile drawing stayed at eight. All delivered outputs remain cleared. Legacy arithmetic regressions explicitly use a non-protruding pile fixture; their historical passing counts below are not the current project search results. Project pile embedment/clearance remain unconfirmed.

The full supplied C005 journal export preserves every other report. Export checks cover independent table sizes/areas, removal of stale numeric caches, regional native graphics, the pile envelope, and repeat exports without duplication. Native Blockpad recalculation of the new regional graphics has not yet been verified. Bottom shrinkage spacing now explicitly follows original Mathcad region 38146 (`SP[2]`, between piles); pile-region service spacing remains checked across its actual central gap.

The following records describe earlier revisions, including examples and saved previews since removed from the delivered notebook.

# Delivery verification · 2026-09-29

## Calculation and workflow

- Port contains 324 C005 source definitions: 319 variable expressions and five helper functions. All baseline variable results agree with the saved current C005 reference; the three original linked journal externals are explicit notebook inputs.
- Independent scalar mechanics reproduce 43 reference quantities. Twenty-two engineering scenarios exercise load failures, zero demand, changed geometry, multiple rows, cover changes, U-leg area, service/fatigue readiness, failed fatigue thresholds, shear bounds, mass-concrete trigger and pending status.
- Unit-aware and scalar engines agree across 12 changed reinforcement/service cases. Retained search candidates are each rechecked with units.
- The 35-row register retains all 27 D/C expressions, including applicability/zero-denominator guards and pending values. The starting maximum available D/C is 0.985119 (transverse hoop-leg spacing).
- Geometry provenance gates block a steel search with changed pile count/spacing/width, section dimensions or cap end allowances. JSON import rejects wrong units, unsupported inputs and malformed values.
- Cage geometry responds to bar count/size changes, checks the hoop interior and trial clear spacing, and flags unresolved multiple-loop / U-leg positions.
- Widget callbacks cover edit → recalculate, invalid input → clear stale results, search → apply → export, and invalidation of search alternatives after changing inputs.

## Default search

All 1,944 listed combinations are evaluated; 324 pass the available calculation checks and trial cage screen. **All 324 are retained and unit-checked**; the UI pages them in groups of 20, 50 or 100. The leading least-gross-steel option within this list is six #6 top bars, eight #6 bottom bars, #4 hoops at 6 in, and seven #5 skin bars per side. Its comparison weight is approximately 1,025 lb versus 1,461 lb for the starting trial, with maximum available D/C 0.988095. This remains provisional with Service III/fatigue pending; it is not a released reinforcement design or a complete takeoff.

The new margin filter finds zero default-search layouts at all-check D/C ≤ 0.90 (best overall D/C 0.982142857, governed by hoop spacing), and 210 at strength-only D/C ≤ 0.90. Tests cover inclusive numerical boundaries, invalid targets, reranking, selection beyond candidate 20, empty matches, page-size changes, all-match plot counts, clearing stale results, and full/filtered CSV exports across every page. Changing a filter never reruns the search or drops candidates from its complete population. The strength scope excludes service/minimum/detailing ratios from the margin target while retaining their original pass requirements.

The focused 0.97-floor review reproduces 306 strength matches at 0.97 and zero all-check matches; minimum strength D/C is 0.547068640. An independent geometry check confirms that adding main bars or tightening successive hoops leaves the across-cap leg distance unchanged. Widget checks confirm the default strength scope, separate strength/all-check values, match counts, and the selected plot axis. The source equations and eligibility conditions are unchanged; see `DC_RATIO_REVIEW.md`.

## Files and presentation

- The supplied moment, shear and torsion workbooks were read through the converter. It reproduces all nine force inputs and the four-pile / 5 ft spacing configuration. Source hashes and governing worksheet rows are recorded by the importer.
- JSON round trips, non-overwriting exports and the Blockpad C005 patch are tested. An export of the full live journal preserves every non-C005 root element. This notebook's generated review copy has **not** been independently recalculated in native Blockpad; opening/recalculating the exported copy remains part of the documented handoff.
- The notebook executes from top to bottom with zero error outputs. Static figure output is retained for GitHub preview; widget state is intentionally excluded from the saved file. Run All in Jupyter recreates the interactive controls.
- A browser session in local JupyterLab confirmed that the workbench renders, changing top row 2 from zero to four draws four new bars in both region views, and the cage-fit status updates. The static preview was rendered and visually inspected.
- The local Python environment is prepared. The launcher scopes Jupyter runtime/configuration to this project, and Git ignores environment/runtime/export data. Existing bridge-geometry notebooks are unchanged.
- Colab setup regression tests use disposable local Git remotes and actual shallow clones. They cover a fresh/repeated setup; updating an old checkout after its missing filter API has already been imported; preserving exports, tracked edits and local commits; failed fetches; wrong branches; and non-repository folders. Only Colab widget registration and dependency installation are simulated. Setup now refreshes supporting files, clears cached package imports, and checks the required search API before reporting readiness. These tests do not exercise GitHub authentication or the hosted Colab frontend.

## Width/depth study

Ten additional tests cover preservation of force-source geometry through screening, selection and export; unchanged ordinary-search blocking; equivalence at the original section; the adopted width screen and single-hoop failure for wider sections; missing/conflicting/stale analysis cases; actual use of supplied new forces; cache invalidation and view-only filtering; independent quantity/cost and Pareto-dominance calculations; explicit partial budgets; and widget selection, application, refinement, exports and stale-view invalidation.

The complete notebook executed successfully with the new nine-section fixed-force example: 17,496 candidates evaluated, with six sections containing cages at strength D/C ≤ 0.90. Its static heatmap/frontier figure was visually inspected. In a live local JupyterLab browser session, clicking the 48 × 48 map point changed the section selector, and choosing a later cage updated the summary and drawing to eight top and eight bottom bars. A smaller 64-cage-per-section grid was used for that UI interaction check; the saved notebook example uses the full 1,944-cage grid at each section.

Reproduce the automated checks with `python -m unittest discover -s tests -v`. The suite contains 41 tests plus their parameterized cases/reference comparisons. Colab and VS Code frontend behavior have not been separately verified.

## Cost breakdown and plot colors

The 41-test suite passed after adding component costs, ranks and premiums. Independent synthetic quantities verify that increasing the steel rate can reverse the preferred section, equal totals retain tied first ranks, missing prices do not imply costs, invalid/extreme prices are rejected, and displayed bar components sum to the reported total. Tests also cover heatmap quantities and component labels, hover costs, excluded zero-rate items, selections beyond the first ten chart rows, repricing without a new search, preservation of a selected heavier cage, bar-click selection and CSV component/rank exports. The focused 12-test section suite passed again after final chart sizing changes.

The full 18-cell notebook executed successfully with the final moment/shear palette and regenerated saved previews. Additional direct checks confirmed distinct blue moment and purple shear palettes in demand/capacity and D/C charts, with failed ratios remaining red. No engineering formulas or capacity values changed.

A local JupyterLab session rendered the live comparison with sample UI-test rates and a nine-depth, 64-cage-per-section grid. The concrete/steel/forms cell-label control and full cost breakdown were visually checked; clicking the 48 × 54 in cell selected that section and its cost premium. The stacked cost chart, lowest-cost summary, labels and separate moment/shear color families were visually checked at desktop width. These sample rates are not project rates and were not written into the delivered notebook defaults.

## Direct FB-MultiPier XML import

The full supplied `Pier_MinTip.XML` (6.1.0) imported successfully. Selected member-end extrema agree exactly with its independent cap summary: M3 +287.44/−183.15 kip-ft, shear-2 +209.52/−208.47 kip and absolute torque 34.16 kip-ft. The importer selects 19 cap members and excludes 35 additional members in the same container. It recovers the 48 × 36 in section, four 20 in piles at 5 ft, 19.24 ft cap length, 15.44 in nominal face extension, and 6 ksi concrete. Maximum uniform-load equilibrium residual is 0.07146 kip-ft, within printed-coordinate/force rounding tolerance. See `FBMP_IMPORT.md` for pile-face recovery and the broader positive-span envelope.

Nine added tests cover I/J signs and governing stations; a zero-end-moment segment with a governing interior peak; exclusion of large extra-member forces; missing combinations and summary/equilibrium mismatches; unsupported units/versions/geometry; DTD/entities and nonfinite data; insufficient end allowance; exact Service I state matching and readiness reset; and preview/apply/stale-preview behavior while retaining trial reinforcement. The reduced fixture retains source cap values and one extra member without soil/project-personnel data. A JSON export of the complete source import round-tripped without loss of case or audit information.

All **50 tests** passed. The focused nine-test importer suite passed again after final preview formatting and unchanged-data notification handling. The complete 18-cell notebook executed without error. A default 1,944-layout search on the newly imported case found **260** layouts passing available checks, of which **205** met strength D/C ≤ 0.90. Service III/fatigue and the existing full-design scope remain pending. These counts apply to the default search choices and adopted global low-interval shear.

The import preview was rendered and visually inspected in local JupyterLab. The actual file chooser uploaded the full XML and enabled its preview. Applying the import updated the displayed case ID, 48 × 36 in live cage, 19.240 ft length and 15.44 in nominal extension. Hosted Colab was not exercised; `.out` parsing is not implemented.

## Import confirmation and repeated notebook execution

Import controls now distinguish reading, preview-not-applied, successful application and failure beside the upload button. Both calculators display the active source, analyzed section and current strength M/V/T inputs. Success receipts retain the file/time, survive reinforcement-only changes, and change state when imported loads/geometry are edited. Upload-envelope errors are handled visibly, including sequence and legacy named-dictionary payload formats. Analysis-library receipts explicitly distinguish adding a case from replacing the active loads.

The workbench cell previously recreated the default case whenever it ran. It now preserves the active case, receipt and search selections in the same runtime, disposes of the previous workbench, and reconnects a displayed section study. Earlier study instances without the new rebind method are closed once and recreated by the study cell. Runtime termination still requires saving/reloading a case.

The full 55-test suite passed with the confirmation and preservation changes. The final six-test feedback suite also passed, including an additional live-version-upgrade regression. These tests drive FileUpload values, visible success/error states, old-study invalidation, source summaries, reinforcement/load edits, and the actual notebook workbench/study cell source. The full 18-cell notebook executed without errors; the final older-instance compatibility branch was subsequently exercised by the focused cell-source regression. This update does not change engineering formulas or search acceptance.

The supplied skin-steel screenshot was independently reproduced using the old workbook source, a 48 × 36 in trial section, five #6 top/eight #6 bottom bars, #6 hoops at 12 in, and seven #6 bars per side. It gives 1,106.447 lb and strength D/C 0.947808, matching the screenshot. Reducing to six skin bars per side fails longitudinal tension checks. With the latest XML and the same cage, strength D/C is 0.981341. The screenshot therefore describes the old force case rather than a completed XML-based section study.

## Zero and smaller side-bar searches · 2026-09-30

The old controls offered only 4–10 side bars and defaulted to 5–7. The default now includes 0–7. Zero is evaluated once per remaining cage, irrespective of the unused side-bar size; that size also contributes no complexity penalty. Total steel weight still sets the least-steel ranking, and the section cost map retains its lightest matching cage basis. No engineering equations or acceptance gates changed.

Six additional tests cover the expanded domain, duplicate-free zero-side trials, section-study budgets, smaller passing cages, unused-size weight/complexity, the side-steel explanation, and live notebook migration. In a 48 × 36 in trial using the starting workbook forces and the original mechanics fixture with no protruding pile head, four #4 bars per side weigh less than every cage from the former 5–7 range; three #5 per side also pass. The depth-based skin rule is inactive in this trial, but zero side bars fail shrinkage area and spacing: side area rate is zero against 0.222857 in²/ft required, and the side spacing is 27.75 in against 12 in allowed. These are regression inputs, not a selected project design. Side steel changes longitudinal-tension utilization without changing flexural resistance in the current equations.

All **109 tests passed**. A further **12 widget/import tests passed** with the local Colab-compatible ipywidgets 7.7.1 / Plotly 5.24.1 libraries, including migration from the old side-count options and preservation of later deliberate choices. The clean four-cell notebook executed with zero error outputs. No saved outputs or examples were added. The hosted Colab frontend was not exercised for this change.
