# T006 — apply pier coherence responses and replacement report

Execute the user's completed Excel responses and replacement 9 October pier
report against journal SHA256
829f5450a34c76bee03ebbce06a389de76883ccaa8007b5e9bb50b17ec83de33.

## Scope and exclusions

- Keep C005 byte-identical, including cached results. Keep new steel data and
  design findings outside BPAD. No notebook, model, end-bent design, commit or push.
- Use the report's 230-in cap length for the shared direct-pier wind width;
  preserve native live formulas and invalidate only affected cached results.
  Wall/fin volume geometry cannot be inferred from this cap length alone.
- Record the new Pier_Fixed report as current. Preserve old report/model evidence
  as history. Verify any matching raw XML supplied; otherwise explicitly leave
  the right-row offset and full model-input currency unverified.
- Label retained old quantity illustrations as historical; preserve image bytes.
- Repair three LoadCombinations links using verified existing embedded sources.
- Preserve the user's completed workbook and record item-by-item dispositions.
  Field-bending direction and deferred reinforcement checks remain external.

## Permitted components

report:BridgeGeometry_2Beam; report:FBMPPier; report:FoundationModeling;
report:PedBridge; report:DecisionLog; spreadsheet:QauntitiesBridge;
report:LoadCombinations; report:FenceWind; report:PedBridgeWind.

## Dependencies and interfaces

Use all-component read fallback. Inspected current module index, 3,800 formula
expressions, named references, current geometry, force paths and source records.
BridgeGeometry_2Beam owns PierCap_length, Pier_windFace_width, Pier_wall_area and
the unchanged terrain-to-cap-top height. Updated width equals PierCap_length;
area = width times height in ft2. FenceWind F_wall_L_III and F_wall_L_SI are
pressure times that area in kip, unfactored face-normal bounds, not a concurrent
pair with transverse wind. PedBridgeWind.Wind_perpPierWall and FBMPPier
FE_DirectLBound_W1/W2/W3 and display tables consume them. They do not change
actual selected transverse wall cases or bearing load-transfer equations.
No additional symbol consumers were found after reviewing all native modules.
Cap volume remains 230 ft3 gross; pier pedestals remain 48 in. C005, resource
bytes, reference PDFs, styles and all other components remain protected.

## Sources and conventions

User response workbook at outputs/pier-coherence-20261009 and updated report at
Downloads/Pier Cap Design 10-9.html are archived byte-exact before edits. The new
report hash is 7a9f48ce08bdc29f22a1b6717432dc363f0c2d8cec02ffbfc0a36bb7da39dee2;
it identifies Pier_Fixed.XML SHA256
a992aa331e11b4eb9bc426a3f811938a8f71b22b3300bae3431eb2931eaff9d8.
Report geometry: 48 x 36 x 230 in; four 20-in pipes at 60-in centers. Report
cap X starts at first pile center; add 25 in to express cap-end stations.
Existing local/global elevation datums remain distinct. Model forces are source
records only; source independent maxima are not concurrent actions.

## Acceptance and stop conditions

Prerequisite T005 is incorporated in current journal. Verify source hashes,
unchanged source geometry, user response preservation, exact C005/resource/other
component preservation, 0 stored errors and 0 broken native links after repairs.
Check affected symbol/cache closure and 230/231 area/force ratio; do not invent
cached native results. Check and assemble through workflow helper. Open exact
candidate for required native recalculation and appearance checks of changed
geometry, source record, link targets, quantity annotation and wind results.
Accept faithful geometry/source bookkeeping only; design outcome not_applicable.
Full FBMP load-input currency, convergence and structural adequacy stay excluded.
Promote only exact reviewed bytes; if native evaluation fails or another task
changes protected inputs, repair/reassemble/review or report the limitation.
