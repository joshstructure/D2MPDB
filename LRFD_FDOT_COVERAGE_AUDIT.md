# Cap notebook LRFD and FDOT check coverage audit

Reviewed October 10, 2026 against repository revision `cf03619`.

The notebook covers much of the ordinary rectangular cap section design, but it does not yet close the local load paths at bearings and piles, all service and construction conditions, or several FDOT detailing requirements. Several of these omissions already produce a pending status. Others are recorded only as model information or are not represented in the D/C register.

This is a coverage audit of the notebook, not a determination that the bridge fails these omitted checks. A missing check needs a calculation, a referenced external calculation, or a documented finding that it does not apply. No calculation code or notebook inputs were changed by this audit.

## Design basis and scope

The basis is AASHTO LRFD Bridge Design Specifications, 10th edition, 2024, with the September 2025 errata, and the January 2026 FDOT Structures Manual, principally Volume 1 Structures Design Guidelines (SDG) and Volume 2 Structures Detailing Manual (SDM). This follows the edition identified in the project's existing validation record. The contract's adopted editions, project classification, and approved variations remain controlling.

The review concerns the supported solid, rectangular, cast-in-place, nonprestressed pier/bent cap and its interfaces. Foundation checks are listed separately because the notebook also contains a pile review and minimum-tip workflow. Prestressed caps, inverted-T ledges, footing-type pile caps, and special seismic systems need their own applicability branches.

The official [FDOT release page](https://www.fdot.gov/Structures/StructuresManual/CurrentRelease) identifies the 2026 manual. [SDB 25-03](https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/structures/bulletins/2025/sdb-25-03.pdf?sfvrsn=f453619c_1) gives its implementation policy. The [current Structures bulletins index](https://www.fdot.gov/structures/Memos/currentbulletins.shtm), checked for this audit, lists SDB 25-03, 25-02, and 25-01. The relevant [September 2025 AASHTO errata](https://store.transportation.org/Common/DownloadContentFiles?id=2562) include corrections to the bend table and development-length notation; the reviewed errata do not introduce a new ordinary reinforced-cap check family.

## Findings for the saved cap case

The saved `Pier_Cap_CRSI_Standard_Hooks.json` case was evaluated with the current package. It represents a 48 by 36 inch cap, four 20 inch piles at 5 foot centers, 5.5 ksi concrete, Grade 60 reinforcement, 3 inch entered cover, and 12 inch pile embedment. Its source is `Pier_Fixed.XML`, SHA prefix `a992aa331e11`.

- The case has 270 displayed checks and an overall check-failure status. Existing failures are separate from the missing coverage identified here.
- Service III and fatigue are both pending. The imported combinations are Strength I, two Strength III combinations, and Service I. **Strength III does not supply Service III.**
- The import records absolute maxima of 18.63 kip axial force, 12.31 kip-ft weak-axis moment, and 3.83 kip lateral shear outside the original section calculation. These are separate maxima, not a concurrent design vector. The actual-cage shear/longitudinal procedure uses an axial-force bound, but this does not establish combined axial and biaxial flexural resistance or weak-direction shear resistance.
- Local D-region design, cap-end anchorage, added-bar cutoff detailing, and the general shear strain range remain pending. The direct-loading evidence field is blank; all 15 classified moment domains use full interaction rather than a direct-loading exemption.
- Three inch cover is consistent with the FDOT table for formed substructure surfaces outside water in slightly or moderately aggressive conditions. The notebook has no exposure classification to establish that those conditions apply.

This case is a saved workspace example; it does not establish the current values in an independently running Colab session.

## Checks to add or complete first

Priority 1 items can change the structural conclusion or prevent a required limit state from being evaluated. Priority 2 items close owner-policy and detailing coverage. The priorities are implementation recommendations, not categories assigned by the specifications.

| ID | Priority | Check family | Current coverage |
| --- | --- | --- | --- |
| C01 | 1 | Bearing and pile D-regions | Pending notice; no numerical local model |
| C02 | 1 | Concrete bearing and pedestal load transfer | Missing numerical check |
| C03 | 1 | Pile-to-cap connection and embedment | Geometry and user classification only |
| C04 | 1 | Combined axial/biaxial flexure and lateral shear | Partly imported; not checked as a complete section |
| C05 | 1 | Service III and construction-stage cracking | Service III exists but is pending; construction check missing |
| C06 | 1 | Bar termination, support extensions, and splices | Development lengths calculated; detailing remains partial |
| C07 | 1 | Required load cases and extreme-event coverage | No completeness register; flexure excludes extreme events |
| C08 | 2 | FDOT cover, concrete class, and reinforcement policy | Positive input/fit checks; no policy comparison |
| C09 | 2 | FDOT bar-size limits | Generic supported-size check only |
| C10 | 2 | Construction-joint interface shear | Missing; applicable where separate pours transfer force |
| C11 | 2 | Local torsion detailing | Strength and closed-path calculations exist; distribution review incomplete |
| C12 | 2 | Bearing-seat geometry and placement tolerances | Pile/cage screens exist; complete seat/pedestal check absent |
| C13 | 2 | Deflection, rotation, and stability evidence | Imported analysis does not establish acceptance criteria |
| C14 | 2 | Mass-concrete designation | Ordinary size trigger exists only in formula trace |

### C01 Bearing and pile D-regions

Replace the broad pending notice with identified regions around each bearing, pile reaction, cap end, and geometric discontinuity. Select and document an applicable LRFD method. Where strut-and-tie design is used, check equilibrium, strut and node resistance, ties and tie anchorage, bearing footprints, and required crack-control reinforcement. Ordinary shear stirrups and shrinkage steel do not automatically demonstrate compliance with the selected local model.

LRFD 5.5.1.2.3 and 5.7.1.2 permit applicable D-region methods; 5.8.2 contains the STM checks. Section 5.8.2.6 has its own orthogonal crack-control requirements where its specified efficiency-factor basis applies, including reinforcement ratios of 0.003 and a spacing limit of the smaller of d/4 and 12 inches, subject to the article's scope and exceptions. Do not label STM as the only permitted method for every beam end.

**Needed:** bearing footprints, individual reactions, support faces, connection conditions, and a local reinforcement/load-path model. Current evidence: `Status_actual_review` and `Status_lrfd_end_regions` in `pier_cap/lrfd_checks.py`. LRFD printed pages 5-28, 5-61, 5-88 onward, and 5-101.

### C02 Concrete bearing and pedestal load transfer

Add a bearing check at each loaded concrete contact using actual loaded area, available supporting area, load distribution, concrete strength, and the appropriate resistance factor. Check pedestal-to-cap transfer and local splitting through the chosen D-region model. The existing B-region positive flexure check is not a concrete-bearing check.

**Basis:** LRFD 5.6.5, printed 5-56 to 5-57; FDOT SDG 3.11.4A. **Needed:** bearing-pad and pedestal dimensions, reactions and eccentricities, concrete classes, and whether the pedestal is cast monolithically.

### C03 Pile-to-cap connection and embedment

Check the connection against the axial force, lateral force, moment, and uplift that the analysis assigns to it. Verify local transfer, confinement/splitting where applicable, and anchorage into both connected components. A selection of “pinned” or “moment” is an analysis assumption, not a connection resistance calculation.

Add the detail-dependent minimum pile projection and side-clearance checks from LRFD 10.7.1.2. That article distinguishes pile caps from cast-in-place beam bent caps and distinguishes embedded piles from connections using developed reinforcement. For concrete pile anchorage, apply LRFD 5.12.9.1, including its reinforcement and development provisions where applicable. Include the FDOT tension-pile detail when uplift requires it.

**Basis:** LRFD 10.7.1.2, 5.12.9.1 and, for moment-resisting joints, 5.10.8.1.2d; FDOT SDM 11.6.1–11.6.2. **Needed:** pile-head force vectors, actual cut-off and embedment, pile reinforcement/strand or dowel details, and the adopted connection mechanism. `Ready_pile` currently confirms dimensions; it does not perform these strength checks.

### C04 Combined axial/biaxial flexure and lateral shear

Use simultaneous signed section actions to check axial force with both bending components and shear in the other direction, or retain a documented external calculation covering them. Include axial tension in service steel stresses. The current axial bound used in longitudinal shear/torsion equilibrium cannot substitute for section equilibrium and strain compatibility under combined loading.

**Basis:** LRFD 5.6.2, 5.6.4.5, 5.6.6.2, 5.6.7, and applicable 5.7 provisions. **Evidence:** `outside_calc_maxima` in `pier_cap/fbmp.py`; `source_members()` in `pier_cap/lrfd_checks.py`; moment-only flexural and service equations in `c005_formulas.json`. This item is relevant to the saved case because the omitted action components are nonzero. Their significance must be calculated.

### C05 Service III and construction-stage cracking

Complete the existing Service III outer-layer steel-stress check with the proper load combination. Add a separate construction-stage strength/service review, including FDOT's 24 ksi outer-layer tension limit under construction loading. A completed Service I check does not close either item. Construction stages may have different reactions, partial deck loading, concrete age/strength, and restraint.

**Basis:** FDOT SDG 3.10A, LRFD 3.4.2, and applicable FDOT SDG 2.4.3 and 2.13. FDOT 3.10A specifies the Service III live-load factor of 0.8. **Needed:** Service III actions and governing erection/deck-placement stage actions. Current `Status_III` is already an explicit pending check; the construction branch is absent.

### C06 Bar termination, support extensions, and splices

Complete station-based checks of the added-bar ends and continuing bars against the moment/force envelope. Check extensions beyond theoretical need, the amount and adjacency of bars terminated at one section, positive steel extending through supports, and negative steel extending beyond inflection points. Check hook confinement and actual available anchorage at end supports. For splices, record location, class/type, length or qualified mechanical capacity, staggering, cover, and spacing.

**Basis:** LRFD 5.10.8.1.2a–d and 5.10.8.4; FDOT SDM 4.3.5–4.3.8. Examples of separate requirements include the general extension of at least max(d, 15db, clear span/20), with stated exceptions, and the restriction against terminating adjacent bars or more than half the reinforcement at one section. Calculated development length alone does not establish those conditions.

**Evidence:** `Status_hook_development` expressly leaves cutoff/extension and confinement pending. `Status_continuous_anchorage` records splice state but does not design a splice. **Needed:** a bar schedule and critical stations, including actual hook-end geometry and support details.

### C07 Required load cases and extreme-event coverage

Add a project applicability register for strength, service, fatigue, construction, and relevant extreme events, with evidence for included cases and justified exclusions. Applicable collision, hydraulic/scour, wind, seismic, temperature/restraint, braking, and construction effects belong in the upstream model and its accepted combinations.

There is also a specific implementation gap: `fbmp.py` builds cap flexural demands from `STRENGTH-*` records only, whereas the actual-cage routine includes both strength and extreme-event member records for its checks. An extreme-event upload therefore does not establish matching flexural coverage. The saved case contains no extreme-event combinations; applicability must be resolved before calling this a design failure.

**Basis:** LRFD 3.4.1–3.4.2 and 5.5.5; FDOT SDG Chapter 2, especially 2.12 and 2.13. **Needed:** the project load-case matrix, analysis assumptions, and action/resistance-factor treatment by limit state.

### C08 FDOT cover and materials

Add face-by-face comparisons to FDOT cover requirements using component type, environmental classification, and earth/water exposure. Validate concrete class, specified design strength, corrosion protection, and approved reinforcement type/grade. Numerical positivity and a cage fitting inside the entered cover do not establish these requirements.

For example, FDOT Table 1.4.2-1 gives formed substructure surfaces outside water 3 inch cover in slightly/moderately aggressive environments and 4 inches in extremely aggressive environments. Earth-cast or water-contact surfaces have different values. FDOT SDG 1.4.1B–D also controls steel grades, prohibits epoxy-coated reinforcement, and addresses lightweight concrete approval. The software currently offers coating/density assumptions for development without establishing FDOT acceptance.

**Basis:** FDOT SDG 1.3, 1.4.1–1.4.3; SDM 4.3.3. **Needed:** exposure, face conditions, concrete class, steel specification, and any documented owner variation.

### C09 FDOT bar-size limits

Add explicit policy checks for the entered bars and every actual transverse run. FDOT SDM 4.3.11 specifies #4 as the smallest bar for cast-in-place bridge components and gives pier/bent caps a maximum #11 main bar and #6 stirrup. The current model accepts #3 through #11 generally; the anchorage routine's ability to calculate #7/#8 stirrups does not establish that FDOT permits their use in a cap.

The supported longitudinal layout already limits top steel to three rows and bottom steel to two, so the FDOT 3.10B four-layer limit is not an additional missing check for these current layouts. Bundling is not a supported design branch; if added, include the FDOT two-bar bundle limit and the associated LRFD rules.

### C10 Construction-joint interface shear

Where force crosses a separate concrete pour, add shear-friction/interface resistance, reinforcement crossing the interface, development, and surface-preparation requirements. FDOT's nonredundant-component rule uses a different design assumption from the specified roughening detail; do not automatically claim roughened-surface resistance for every joint.

**Basis:** LRFD 5.7.1.3 and 5.7.4; FDOT SDG 1.15. **Needed:** pour/joint locations, redundancy classification, shear and normal force, interface area, reinforcement, and surface condition. Mark this not applicable only where the connection is actually monolithic or separately verified by an applicable mechanism.

### C11 Torsion detailing

Keep the existing torsion threshold, combined transverse steel, longitudinal force, and closed-path checks. Complete the local check that longitudinal bars occupy the required stirrup corners and that the adopted longitudinal torsion reinforcement is properly distributed and developed around the perimeter. Review closure and continuity through pile interruptions. A global hook-engagement confirmation is not a check of each torsion-resisting corner.

**Basis:** LRFD 5.7.2.4, 5.7.3.6.3 and commentary, 5.10.8.2.6; FDOT SDM 4.3.7G and SDG 4.1.4B. This is partial coverage, not a missing torsion calculation. Apply it where torsion requires investigation.

### C12 Bearing-seat geometry and tolerances

Add pedestal height, bearing edge distance, cap width for the actual bearing arrangement/skew, and the complete pile-placement tolerance plus cage envelope. Existing nominal pile spacing, end allowance, bar fit, and pile clash checks cover parts of this problem. They do not include bearing-pad geometry or the full SDM cap-width construction.

**Basis:** FDOT SDG 3.11.4A; SDM 12.5A, E, F and I and Figures 12.5-1 through 12.5-5; SDM 4.3.4. In particular, Figure 12.5-3 combines pile width, placement tolerance, reinforcement width, and cover. Nonmonolithic pedestal heights have the 4 inch minimum and 15 inch maximum, with stated exceptions. **Needed:** pad/seat/pedestal geometry, skew, pile/shaft placement tolerances, and fabrication/placement allowances.

### C13 Deformation and stability evidence

Record acceptance of cap deflection/rotation and foundation movements, including relevant sustained/time-dependent effects, bearing accommodation, and construction conditions. Retain the required global stability and second-order analysis evidence where applicable. Do not insert a generic span/800 cap limit without establishing that the relevant provision and owner criteria apply.

**Basis:** LRFD 5.5.2, 5.5.4.3 and 5.6.3.5; FDOT SDG 3.11.1A for reduced stiffness when refined slenderness analysis is used. **Needed:** accepted displacement/rotation limits and results, cracked stiffness assumptions, and the relevant global analysis reference.

### C14 Mass concrete

Expose the existing ordinary-component mass-concrete trigger as an applicability/detailing item in D/C checks and exports. Its ordinary criterion correctly requires both minimum dimension greater than 3 feet and volume/surface ratio greater than 1 foot. The trigger is currently outside the D/C register and overall check grouping.

Add the separate straddle/integral-cap branch only if those cap types are supported: FDOT has a strength-based trigger above 6,500 psi and a volume/surface criterion for lower strengths. A trigger should request the required designation, thermal-control/construction evidence, and reinforcement/joint review rather than display a fictitious strength D/C.

**Basis:** FDOT SDG 1.4.4C–D. The saved ordinary cap is 36 inches deep, so it does not exceed the ordinary minimum-dimension trigger.

## Existing calculations needing closer definition

These are implementation limitations within existing check families, not additional independent code checks.

| Item | Finding and required resolution |
| --- | --- |
| Service I for multiple layers | The formulas use the combined steel centroid for `dc`, `bs`, and Service I steel stress. LRFD 5.6.7 defines cover and strain ratio using the reinforcement layer nearest the tension face. Use a consistent outer-layer calculation and actual spacing for multirow cases, including axial tension where present. The effects of changing both stress and cover must be evaluated; this audit does not assume the current error is always in one direction. |
| Skin steel for deep multirow caps | `Skin_required` and required area use the main-steel centroid depth. LRFD 5.6.7 uses the extreme tension steel depth dℓ. Check the actual side bars within the required tension-side dℓ/2 zone, including spacing and development, rather than relying only on half the total side area. This does not trigger skin reinforcement for the saved 36 inch deep case, but matters for deeper options. |
| Fatigue stress definition | The straight-bar threshold is present, but `fmin` currently comes from the entered dead-load moment alone. LRFD 5.5.3.2 includes minimum live-load stress and the applicable permanent/shrinkage/creep stress combination. Establish correct fatigue range, minimum stress, critical bar/layer, cracked-section applicability, and the equation's 60–100 ksi substitution limits. Add splice-specific thresholds if mechanical or welded splices exist under repetitive loading, per 5.5.3.4. |
| Resistance factors and calculation domain | The fixed 0.005 strain screen and fixed flexural factor are an intentionally narrow design path. Establish or enforce the supported material/strain domain under LRFD 5.5.4.2 and 5.6.2 rather than permitting arbitrary factor/material inputs to imply code acceptance. For multiple layers, distinguish extreme-bar strain from steel-centroid strain. |

## Conditional checks outside ordinary beam-cap calculations

- **Footing or slab-type pile caps:** classify first, then check applicable one-way and two-way/punching shear and critical perimeters under LRFD 5.7.1.4 and 5.12.8.6. Do not label punching as universally mandatory for this one-row beam bent cap without resolving its local behavior and chosen D-region method.
- **Ledges, corbels, inverted-T caps, anchor bolts, or restrainers:** provide the applicable LRFD 5.8.4 local component and 5.13 anchorage checks and FDOT 3.11.4B details when these features are present. The rectangular cap model does not represent them.
- **Compression reinforcement relied upon in strength:** check transverse restraint under LRFD 5.10.5 and 5.10.4. The current simple rectangular flexural resistance does not credit compression steel; any expanded section solver must address this explicitly.
- **Prestressing or special seismic details:** require the relevant LRFD 5.9/5.11 provisions and project seismic/owner criteria. They are outside the present nonprestressed cap domain.

## Pile and minimum-tip checks requiring an external handoff

The pile review retains model interaction D/C and provides useful force, displacement, and elastic stress screens. Those are not a complete independent pile/foundation design. Add explicit references or pending items for:

1. Pile structural axial/biaxial strength, shear, service stresses/cracking, lateral stability and second-order effects, and pile splice/anchorage resistance. Basis: LRFD 10.7.3.13 and applicable Section 5 provisions for concrete piles. Preserve the model D/C with its analysis settings; an elastic stress ratio cannot replace it.
2. Geotechnical compression/uplift and group resistance, settlement, lateral movement, scour, downdrag, and other site-dependent minimum penetration. Basis: LRFD 10.7.1.5 and 10.7.6; FDOT SDG 3.5.9. The existing critical-embedment plus 5 foot workflow is one part of this determination. FDOT also requires the greater penetration needed by the other criteria and confirmation of service lateral deflection; the second-zero-deflection review alone does not close these requirements.
3. Drivability, handling, construction testing, and consistency between the chosen resistance factor and field verification. Basis: LRFD 10.7.8 and 5.12.9.1; FDOT SDG 3.5.7 and 3.5.12. [SDB 25-02](https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/structures/bulletins/2025/sdb-25-02.pdf?sfvrsn=baf2e8dc_1) updates pile dynamic-testing policy. The [2026 Soils and Foundations Handbook announcement](https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/materials/administration/resources/library/materialsbulletins/topics/2026/sfh-announcement-bulletin-%284-23-26%29.pdf?Status=Master&sfvrsn=cae0a0aa_1) establishes the current handbook release. These are foundation handoff requirements, not new cap section formulas.

## Checks already represented

The current implementation already includes rectangular major-axis flexure, minimum flexural reinforcement, a tension-strain screen, Service I stress/spacing, pending Service III and fatigue, shear strength and section limit, minimum shear steel, along-cap and across-leg spacing, combined shear/torsion steel, longitudinal shear/torsion equilibrium, actual moving-window stirrup counts, development-length calculations and partial anchorage checks, shrinkage steel by face/direction, skin-steel screening, clear spacing, layer alignment, pile/cage fit, and analysis-geometry consistency.

Two apparent omissions should not be introduced as new requirements:

- FDOT SDG 3.10F and 4.1.8A expressly modify the Service I steel-stress limit to 0.80Fy for Fy below 75 ksi. Replacing it with AASHTO's unmodified 0.60Fy would discard the applicable FDOT modification.
- LRFD 5.10.3.2's generic 18 inch maximum is scoped to walls and slabs; it is not a blanket new main-bar spacing limit for every beam cap. Applicable crack-control, skin, shrinkage, torsion, and local-region detailing still govern.

## Recommended notebook implementation

First add explicit coverage/applicability rows for C01–C14 so a numerical section result cannot be mistaken for completed cap design. Each row should show one of calculated pass/fail, pending inputs, external calculation reference, or not applicable with a reason. Keep the requested equation/details dropdowns collapsed initially; where no numerical calculation exists, show the governing requirement and missing evidence rather than an invented D/C.

Then implement the direct owner-policy checks for cover, material/bar limits, embedment, and pedestal geometry, and repair the existing stress/depth definitions. Complete the Service III, construction, fatigue, and full-action load import before accepting additional strength results. Local bearing, pile connections, and D-regions require the actual details and force vectors and should be implemented against those inputs or linked to a separate reviewed calculation.

## Traceability

Repository evidence was read in `pier_cap/model.py`, `pier_cap/lrfd_checks.py`, `pier_cap/fbmp.py`, `pier_cap/detailing.py`, `pier_cap/placement.py`, `pier_cap/added_steel.py`, `pier_cap/sections.py`, `pier_cap/pile_review.py`, `pier_cap/data/c005_formulas.json`, and `pier_cap/data/dc_ratio_spec.json`, together with the existing scope and validation records. A read-only case evaluation produced `outputs/lrfd-fdot-audit-20261010/work/case-checks.json` in the Desktop D2 MPDB workspace. No new software tests were necessary because executable code was unchanged.

The local source PDFs used were:

- `C:\Users\joshs\Downloads\AASHTO LRFD Bridge Design Specifications 10th Ed 2024_Bookmarked.pdf`. Printed page numbers in this audit refer to the book, not the PDF index. The official September 2025 errata were checked separately.
- `C:\Users\joshs\Desktop\D2 MPDB\tmp\pdfs\FDOT_Structures_Manual_2026.pdf`. Relevant SDG printed pages include 1-9 to 1-21, 1-51, 2-27 to 2-28, 3-13, 3-16 to 3-17, 3-34 to 3-35, 3-42, and 4-2 to 4-5. Relevant SDM pages include 4-2 to 4-6, 11-8 to 11-9, and 12-6 to 12-10.

The cover table, FDOT bar-size table, cap-width detail, LRFD crack-control equation/definitions, and LRFD cutoff detail were also visually checked against the PDF pages.
