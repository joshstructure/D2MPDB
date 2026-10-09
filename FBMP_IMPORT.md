# Fixed-depth cap XML import

Run the notebook, then use **Fixed-depth cap XML** in **Cell 2 · Fixed-depth cap design**. In Colab, click **Choose Files** when it appears. Select the solved fixed-depth XML, review the changed geometry/materials and governing force rows, and click **Apply XML inputs**. The drawings and checks update, and previous searches are invalidated. Rerun the steel/section search. Cap import never replaces the separate minimum-tip study or its handoff source. The internal geotech reaction margin does not change cap demands. Colab uses its native file transfer; local Jupyter uses the standard widget upload.

**Cell 1 · Minimum-tip study and geotech handoff** has a separate **Minimum-tip XML** input and trial-table input. **Save both sections** produces `notebook_state.json`, restored through **Load notebook / case**; it includes both sources, minimum-tip controls, the reaction margin and cap inputs. Separate cap and pile JSON files remain supported. A full cap export also includes the combined state when a pile study is loaded. The importer identifies the uploaded source, but does not infer the model's intended role from its filename or verify its toe-resistance assumptions.

Colab compatibility uses ipywidgets 7.7.1, Plotly 5.24.1 and a tab-title bridge. Setup stops if loaded and installed versions disagree. When upgrading a previous session, save the case and any unsaved notebook edits, restart the session, reload the browser page, and Run all. Restarting Python alone can leave stale browser widget views. The Colab XML upload, preview and Apply sequence was verified in Chrome with `Pier_MinTip.XML` on 2026-09-29.

Changing the case after preview disables Apply. **Refresh preview** rebuilds the proposed import using the current trial reinforcement. Invalid uploads cannot leave an earlier valid import armed. Python users can call `pier_cap.fbmp.import_fbmp_xml(path_or_bytes, base=app.case)` and inspect its returned case before `app.load(...)`.

The cap uploader shows each stage beside the button: **READING XML**, yellow **PREVIEW READY — NOT APPLIED**, then green **XML APPLIED** and **LOADS IMPORTED SUCCESSFULLY** after Apply. The receipt identifies the file and import time. The adjacent **ACTIVE FORCE SOURCE** card lists the analyzed dimensions and current strength M/V/T values. Errors in both the upload payload and XML parsing appear in red here. A file-count badge alone is not confirmation that the inputs were applied.

The section-study controls repeat the active force summary. Applying XML or loading JSON clears earlier study results and requires **Run section study**. The optional analysis-library uploader confirms additions separately: it does not replace the main force case in fixed-force mode. Rerunning the main workbench cell preserves the current case, receipt and search choices in the same runtime, and reconnects an existing study to the new workbench instance. **Reset starting case** intentionally returns to the example. Save a JSON before ending or deleting a Colab runtime; in-memory preservation is not durable storage.

## Supported scope

The initial reader is verified against `Pier_MinTip.XML`, FB-MultiPier **6.1.0**, English units, static AASHTO-LRFD combinations, one straight horizontal pile bent along global +X. It supports an equal-spaced single row of identical round or unrotated square piles, equal end cantilevers, and a uniform solid rectangular cap. Both strength and Service I results are required. Different versions, unknown units, incomplete combinations, dynamic results, tapered sections, unequal spacing and ambiguous geometry stop import rather than supplying guessed inputs. Native `.out` parsing is not implemented.

The source's first two bent section records describe the cantilever and center cap properties; both must agree. Later property records are not substituted for the cap. Pile head result IDs connect the pile coordinates to the cap mesh. The expected cap chain has `2 × cantilever elements + (pile count − 1) × elements per span` members. Every selected I/J pair must match the increasing-X cap node chain in every combination. In this source, the `PIER_CAP` force container also includes 35 additional members; only the 19 validated cap members enter the envelopes. Their independent signed moment/shear extrema and torque magnitude must match the separate cap summary.

Only geometry, cap f′c/fy/Es and supported demands are replaced. Trial steel, covers, clear-spacing screen and design factors are retained. The analyzed cap dimensions become the source geometry; later edits continue to trigger the existing stale-force checks. The XML's modeled steel/stiffness is not a new reinforcement design. Changing trial steel does not rerun FB-MultiPier's stiffness analysis.

**Cantilever export rounding:** FBMP 6.1 can print a 25-in cantilever as `2.08 ft`, while its cap-end and pile-center coordinates retain `25.00 in`. The importer uses the node offsets for geometry and checks the printed length with a precision-specific tolerance: half its printed increment (at most 0.005 ft), plus 0.01 in for the two coordinate rounding errors, with the existing 0.021-in coordinate-check floor. Thus the usual two-decimal foot label has a 0.07-in comparison bound. Left/right symmetry is checked separately at 0.021 in; genuine geometry conflicts are still rejected. The audit preserves both the printed length and the adopted node offsets. The corrected 25-in geometry imports as 15-in pile-face clearance and a 230-in cap, not as the 229.92-in length implied by taking `2.08 ft` literally. The regression fixture `tests/fixtures/fbmp_610_cap_rounded_cantilever.xml` retains a reduced, anonymized excerpt of that solved export.

## Force conventions and recovery

### Diagrams over the analyzed cap

The live workbench's **Force diagrams** tab aligns moment (blue), signed shear (purple), and torsion magnitude (orange) with an elevation of the analyzed cap, pile centers, and bearings. The plot menu selects an individual combination, one limit-state envelope, or the combined strength envelope. Horizontal distances start at the left cap edge. Pile lengths are schematic.

The curves use the retained XML member ends, the verified moment recovery below, linear member shear, and member torsion magnitudes. Interior moment extrema and intersections between combination curves are included. Separate member sides remain separate at force jumps; hover text identifies the governing combination, member, and raw end moment where available. No continuous force diagram is inferred from the older scalar workbook envelopes.

Trial geometry, reinforcement, and manual scalar-load edits do not rerun or alter the imported analysis curves. A notice identifies geometry/load differences. Review bundles include an offline interactive `force_diagrams.html` with the same selections.

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

### Strength I versus the combined strength envelope

Every imported `STRENGTH-*` combination participates in the design envelope. The notebook preview, active-source card and section-study source card show each strength limit state's envelope, the combined envelope, and the current calculator inputs. Expand the governing-source table to see the combination and member/station for each demand. Manually edited demands are marked as edited rather than attributed to the old source.

For the supplied `Pier_MinTip.XML`, combination 1 is Strength I; combinations 2 and 3 are Strength III; combination 4 is Service I:

| Limit state | M− magnitude (kip-ft) | M+ pile (kip-ft) | M+ bearing/span (kip-ft) | Shear magnitude (kip) | Torque magnitude (kip-ft) |
|---|---:|---:|---:|---:|---:|
| Strength I | 182.10 | 90.45 | 287.44 | 209.52 | 4.75 |
| Strength III | 183.15 | 50.61 | 279.73 | 168.62 | 34.16 |
| Combined design envelope | 183.15 | 90.45 | 287.44 | 209.52 | 34.16 |

Strength I was already included; these labels and audit tables do not change the adopted forces or equations. The calculation does **not** run separate simultaneous-force checks for each combination. Blockpad review copies contain the same source tables as a clearly dated-by-export snapshot; subsequent edits in Blockpad do not rewrite that snapshot. Review bundles also contain `strength_loads.csv` and `strength_governing.csv`. Older saved JSON cases retain their governing records but need their XML reimported to populate the per-state table; states or non-governing values are never inferred from the combined maxima.

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
