# One-file FB-MultiPier import

Run the notebook, then use **Upload FBMP XML** in the live workbench. Select a solved XML, review the changed geometry/materials and governing force rows, and click **Apply XML inputs**. The drawings and checks update, and previous searches are invalidated. Rerun the steel/section search. Export a case JSON to preserve the inputs and complete import audit. The same upload control works without local Windows paths in Colab.

Changing the case after preview disables Apply. **Refresh preview** rebuilds the proposed import using the current trial reinforcement. Invalid uploads cannot leave an earlier valid import armed. Python users can call `pier_cap.fbmp.import_fbmp_xml(path_or_bytes, base=app.case)` and inspect its returned case before `app.load(...)`.

## Supported scope

The initial reader is verified against `Pier_MinTip.XML`, FB-MultiPier **6.1.0**, English units, static AASHTO-LRFD combinations, one straight horizontal pile bent along global +X. It supports an equal-spaced single row of identical round or unrotated square piles, equal end cantilevers, and a uniform solid rectangular cap. Both strength and Service I results are required. Different versions, unknown units, incomplete combinations, dynamic results, tapered sections, unequal spacing and ambiguous geometry stop import rather than supplying guessed inputs. Native `.out` parsing is not implemented.

The source's first two bent section records describe the cantilever and center cap properties; both must agree. Later property records are not substituted for the cap. Pile head result IDs connect the pile coordinates to the cap mesh. The expected cap chain has `2 × cantilever elements + (pile count − 1) × elements per span` members. Every selected I/J pair must match the increasing-X cap node chain in every combination. In this source, the `PIER_CAP` force container also includes 35 additional members; only the 19 validated cap members enter the envelopes. Their independent signed moment/shear extrema and torque magnitude must match the separate cap summary.

Only geometry, cap f′c/fy/Es and supported demands are replaced. Trial steel, covers, clear-spacing screen and design factors are retained. The analyzed cap dimensions become the source geometry; later edits continue to trigger the existing stale-force checks. The XML's modeled steel/stiffness is not a new reinforcement design. Changing trial steel does not rerun FB-MultiPier's stiffness analysis.

## Force conventions and recovery

The BSI-authored [FB-MultiPier manual, sections 4.2.5 and 4.13](https://studylib.net/doc/28088488/fb-multipier) distinguishes raw element forces in XML/OUT from the sign-adjusted design displays. For the validated +X cap chain, use `M_I = raw M3_I`, `M_J = −raw M3_J`, `V_I = −raw shear2_I`, `V_J = raw shear2_J`. Positive M means bottom tension. Torsion enters as magnitude only. The separate XML summary provides an additional source-specific cross-check; the older manual alone does not establish the 6.1 XML schema.

For each prismatic segment, a quadratic moment profile is reconstructed from the two end moments and shear difference. With `t = distance / length` and length L in feet:

`M(t) = Mi + (Mj − Mi)t + 0.5(Vi − Vj)L t(1 − t)`.

Before using this expression, `Mj − Mi = (Vi + Vj)L/2` must hold within printed-coordinate/force rounding tolerance. Only nodal input-load records and untapered members are supported; nonuniform member-load extensions need separate validation. The reconstruction does not interpolate across a nodal moment jump. Both member sides remain available at a pile or bearing. Interior zero-shear moment extrema are included, so an interior peak cannot disappear merely because XML reports end forces.

| Notebook input | XML mapping |
|---|---|
| Mu_N, MI_N | Largest negative moment magnitude over the whole cap, strength / Service I respectively |
| Mu_P, MI_P | Largest positive moment at either side of pile centers or recovered pile faces |
| Mu_B, MI_B | Full-cap positive envelope, including bearing nodes and interior peaks; deliberately covers more than bearing-only workbook rows |
| Vu_G | Largest absolute strength shear-2 |
| Vu_L | Same global strength shear until a low-shear interval is explicitly established |
| Tu | Largest absolute strength torque |

Recovered moments are rounded outward to 0.01 kip-ft. If a sign has no demand, its adopted envelope is zero. Combinations are already factored by FB-MultiPier; the importer does not apply load factors a second time. Strength envelopes are independent, not a simultaneous vector at one station. Only exact `SERVICE-I` labels supply Service I demands. `STRENGTH-III` never supplies Service III. Previous Service III/fatigue values are cleared and their readiness remains pending. Other result limit states are retained in the source audit but do not populate these checks.

Axial force, weak-axis bending and lateral shear are not mapped into this calculation's strong-axis flexure/shear/torsion method. Their envelope magnitudes are shown in the preview and audit. Full interaction, convergence, anchorage and the existing pending design checks still require review.

## Geometry in the supplied run

The XML describes a **48 × 36 in cap**, four **20 in piles at 5 ft centers**, and **6 ksi concrete**. Its two 2.12 ft cantilevers are measured from pile centerlines. Therefore the modeled cap is **19.24 ft long**, with **15.44 in nominal extension beyond the pile face**. This is an analyzed dimension, not a claim that FDOT requires 15.44 in.

The existing adopted actual clearance of 9 in and 3 in pile tolerance are preserved, leaving **3.44 in extra end allowance**. If a later XML end is shorter than the current clearance plus tolerance, import stops. It does not shrink the user's adopted clearance to make geometry fit.

| Demand | Strength | Service I | Units |
|---|---:|---:|---|
| Negative moment | 183.15 | 166.54 | kip-ft |
| Pile positive moment | 90.45 | 60.62 | kip-ft |
| Bearing/span positive moment | 287.44 | 254.81 | kip-ft |
| Global / adopted low-interval shear | 209.52 | — | kip |
| Torque magnitude | 34.16 | — | kip-ft |

Governing combination, load case, member, end/interior station, raw force signs and source SHA256 accompany the saved JSON. The representative fixture in `tests/fixtures/fbmp_610_cap.xml` is a reduced excerpt: it omits project personnel, soil and deep pile data while retaining printed cap geometry/forces and one extra member. The full user source was also imported locally. The earlier Excel files represent different geometry/forces; they are not a same-run numerical validation of recovered pile-face values. These values are checked by member equilibrium and independent test mechanics, but a same-run design-table spot check remains useful when extending the importer to new model families.
