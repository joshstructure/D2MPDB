# D2MPDB notebooks

## Native Blockpad journal workflow

The journal workflow is documented in [workflow/README.md](workflow/README.md).
It preserves the supplied version 36 BPAD and supports isolated task copies,
dependency and conflict checks, lossless assembly, and evidence-gated promotion.
Use [the task-order prompt](prompts/create-task-order.md) to begin a journal task.
The initial reference-path candidate awaits native Blockpad review; the imported
journal has not been represented as a validated engineering revision.

## Standalone FBMP envelope extractor

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/FBMP_Envelope_Extractor.ipynb)

Open **[FBMP_Envelope_Extractor.ipynb](FBMP_Envelope_Extractor.ipynb)**, choose **Runtime → Run all**, and upload an analyzed FB-MultiPier XML. The tool extracts moment M2/M3, shear V2/V3, and torsion envelopes with governing cases, member filters, plots, and CSV/ZIP downloads. All code is embedded in this notebook.

**Strength and Service tables appear directly in the notebook after upload**, with each exact limit state kept separate. They show minimum, maximum, absolute maximum, units, and governing case/combination for all five components. Separate **Download Strength CSV** and **Download Service CSV** buttons export the same rows. The supplied XML includes **Service I: load case 11, combination 4**.

The reported FBMP summary and original XML element-end envelopes remain separately labeled, with source discrepancies flagged. See [the extractor guide](FBMP_ENVELOPE_EXTRACTOR.md). The Colab link becomes available after the notebook is pushed to `main`.

## Cap and pile design notebook

**Portable one-file edition:** [Cap_and_Pile_Design.ipynb](Cap_and_Pile_Design.ipynb) includes the calculation package. Open it in Colab and choose **Runtime → Run all**.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Cap_and_Pile_Design.ipynb)

The notebook now handles the shared sectional workflow for **pier and end-bent caps on a single pile row**. A new **FBMP pile review** section sits above the reinforcement controls and includes pile-head compression/uplift, governing results by limit state, displacement/force/D/C/stress profiles, section properties, minimum-tip trial review and a geotechnical handoff. Upload the XML once: pile results load immediately, and the cap preview is applied with **Apply XML inputs**. Check multiple piles to overlay their profiles with consistent colors. An optional separate pile upload is available for a different run. Minimum-tip trial history is pasted separately, with or without Excel column headings; the button reports success or a specific input error. See [Pile review](PILE_REVIEW.md) for the workbook mapping, supported geometry, calculation basis, downloads and limitations.

When supporting code changes, run `python scripts/build_portable_notebook.py` to refresh the portable notebook before pushing. Use `--preserve-outputs` to retain a saved run and widget state; this does not rerun calculations or refresh its saved figures.

**Reading the reinforcement views:** Plan looks down on the bottom bars; side elevation looks along the pile row; cross sections look end-on through the cap. Purple dashed lines in elevation are a short hoop-pitch illustration. Actual first-hoop stations, spacing-zone boundaries and pile-head hoop details are not inputs in the current tool, so stationing remains pending. The hoop view includes a readable size/pitch table and side-elevation samples plus one end-on hoop outline. `#6 @ 9 in c/c` means a No. 6 hoop at 9-inch center spacing, not six hoops.

**Overall (G) and lower-shear interval (L)** are separate shear checks, not vertical positions. The XML importer uses overall shear for both until a lower-shear interval is established. Identical shear and pitch inputs share one sample drawing; differing inputs show two samples, without assigning them to cap stations.

**Additional bars, U legs and overrides:** Added between-pile bars supplement continuous bottom bars and include their drawn end hooks. Separate U-leg counts add steel area in the legacy calculation but have unresolved positions/development; do not count the added bars' hooks again as U legs. The advanced spacing checkbox changes longitudinal-bar spacing across the section, not along-cap hoop pitch. Inner leg spacing is used separately for more than one effective hoop loop; that topology remains unresolved.

**Repository-backed edition:**

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Pier_Cap_Design_Optimizer.ipynb)

**From GitHub:** click **Open in Colab**, connect to a runtime, then choose **Runtime → Run all**. The first cell downloads this repository's `main` branch, installs the notebook's Colab dependencies and enables its custom widgets. Push the notebook, `pier_cap/` and `requirements-pier-cap-colab.txt` together before using the link. A standard CPU runtime is sufficient.

Open **[Pier_Cap_Design_Optimizer.ipynb](Pier_Cap_Design_Optimizer.ipynb)** in JupyterLab or VS Code, select the project `.venv` Python kernel, and **Run All**. The notebook contains only brief instructions, setup, the live workbench, and the cap study. It has no automatic example searches, snapshots, saved outputs, or embedded repair modules. The workbench contains the live calculator, input widgets, reinforcement sections, pile/hoop drawings, capacity/stress plots, D/C register, bounded steel search, and case exports.

On this computer the project environment is prepared. Run `Start-PierCap-Notebook.ps1` from PowerShell to launch JupyterLab. If your script execution policy prevents the launcher, use the direct command below; changing system policy is unnecessary.

```powershell
cd C:\github\D2MPDB
.\.venv\Scripts\python.exe -m jupyterlab Pier_Cap_Design_Optimizer.ipynb
```

For a fresh checkout, use Python 3.12 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-pier-cap.txt
.\.venv\Scripts\python.exe -m jupyterlab Pier_Cap_Design_Optimizer.ipynb
```

Keep the `pier_cap/` package beside the notebook. Supporting files organize reusable calculations; normal design iteration happens inside the notebook. The three preexisting bridge geometry notebooks are unchanged.

### Recommended workflow

1. Import the current FB-MultiPier XML or load a saved `selected_case.json`.
2. Review the force source and dimensions. Under **Geometry → Pile head**, enter physical embedment and required clear gap, confirm the dimensions.
3. Set continuous bottom steel under **Steel → Continuous bottom steel · at piles**, and extra bars under **ADDITIONAL steel · between piles**. Between-pile counts mean added bars, never totals; zero adds no steel. Inspect both cross sections, stress plots and the D/C register.
4. Select the independent top, pile and between-pile sizes/counts, then run **Search steel layouts**. Every retained layout is rechecked with units. The search reports its evaluated and total combinations; a case limit samples the full grid reproducibly. It uses no AI calls.
5. Set **Max D/C** (for example, `0.90`). The workbench defaults to **Strength checks only** for this margin target; choose **All available checks** if you also want to tighten spacing and other detailing ratios. Browse with **Page / Previous / Next** and **Per page** (20, 50 or 100). Filtering and ranking reuse the finished search. **Apply selected layout** loads the selected candidate ID into the live drawings/checks. Service III/fatigue and other unresolved scope remain explicit.
6. Export the case/checks and optionally a new Blockpad C005 review copy. Recalculate that copy in Blockpad and reconcile narrative/source notes before final review.

The initial JSON bundle and all input units are documented in `pier_cap/data/default_case.json` and `c005_formulas.json`. It carries analysis provenance with the force data. Changing **cap width or depth** lets you run **Search steel layouts** again with the current forces held constant. The notebook labels these as trial-size results, preserves the original analyzed geometry, and supports filtering, applying and exporting the layouts. Changes to self-weight and stiffness need an updated FBMP analysis for the final size. Changes to pile layout or cap ends still require matching analysis forces before searching. An explicit manual analysis-record action is available after entering updated forces.

### D/C margin and browsing all layouts

The search results are steel layouts for the current force case, not additional analysis load combinations. The table and selection dropdown show one page; every passing result is retained. Candidate IDs stay fixed within a search even when the filter or ranking changes. The comparison plot includes every filter match, with the candidate ID and controlling check in its hover label.

Editing bars or reinforcement spacing in the live calculator keeps the completed steel search and section study, including filters, page, selections and plots. Their candidate checks still describe the saved layouts; the live calculator checks your edited cage separately. Apply a candidate to restore its saved reinforcement and spacing. Changes to loads, geometry, materials, readiness or the clear-spacing screen require a new search. Review exports include `search_base_case.json` alongside the edited `selected_case.json` so the completed search's assumptions remain traceable.

**All available checks** applies the target to the largest available ratio, including spacing, minimum reinforcement, strain and service criteria. **Strength checks only** applies it to flexure, shear, combined shear/torsion steel and longitudinal steel; every remaining available check must still pass at its original limit. The table displays both the filter D/C and all-check D/C so these targets cannot be confused. **Largest margin** ranks the selected scope.

An empty-results message reports the best available ratio and governing check without relaxing the target. Spacing checks can control even when strength ratios are low. The **Plots** tab separates along-cap hoop spacing from across-cap leg spacing. Filtering does not complete pending Service III/fatigue inputs.

Programmatically, `filter_candidates(result, max_dc=0.90, scope="strength")` returns zero-based indices into the complete `result.candidates` list; `candidate_case(result, index)` retrieves one. Displayed candidate IDs are those indices plus one. The old `SearchConfig.keep` cap has been removed; use list slicing only for your own previews.

### Cap cross-section study

The notebook’s **Cap section and steel study** adds a width/depth grid around the existing steel search, a clickable section heatmap, concrete/steel tradeoff plot, all-cage selection, live previews, local grid refinement and study exports. The starting ranges are widths **44–52 in by 4 in** and depths **36–60 in by 6 in**. Change the strength target and optional unit rates without repeating calculations. Exact repeated section searches are cached within the runtime.

Heatmap cells show **concrete volume and steel weight together**, or their separate costs using the cell-label control. Entering comparison rates enables a **lowest-cost section summary**, a map of **percentage above the cheapest explored match**, a ranked stacked concrete/steel/forms cost chart and a complete ranked table. Hover shows the material and cost differences from the cheapest section. All costs use your entered rates; zero-rate items are labeled as excluded. The selected cage has its own cost comparison, even when it is heavier than the cage used for the map.

Moment demand/capacity plots use blue shades; shear uses purple shades. The numerical D/C chart uses the same family colors, with orange for combined shear/torsion, gray for other checks, and red overriding the family color for a failed check. Values, labels and limits remain visible independently of color.

Default **fixed-force sensitivity** keeps imported forces constant and retains their original source geometry. **Analysis-matched mode** uses uploaded case JSON files for the corresponding sections and leaves missing analyses visible. This does not run FB-MultiPier. Applying a width/depth trial to the main calculator also lets you continue its steel search with the current forces; a matching analysis is still needed for the final size. Read [SECTION_STUDY.md](SECTION_STUDY.md) for force provenance, geometry screens, quantities, limits and exports.

### Search and drawing limits

The automatic family uses independently selected top, pile-positive and between-pile positive bar sizes and counts, one row of continuous and added bottom bars, one closed hoop and uniform spacing. Additional rows remain manual inputs. The study uses the same independent choices. A bounded search does not establish an optimum outside the explored combinations.

**Side bars:** the search includes zero through seven bars per side by default; select counts through ten in **Bars / side**. Zero is evaluated once per remaining layout, regardless of the unused side-bar size. **Least steel** includes main, side and hoop steel in its weight. The live cage and section-study preview show whether the depth-based skin rule applies and which side-steel checks fail with zero side bars. In the current calculation, shrinkage/temperature area is required on each face even when the depth-based skin rule does not apply; side bars also contribute to the longitudinal-tension checks, but not flexural resistance. The search keeps these checks active. Rerunning an older workbench expands its former default side counts to include the smaller choices; later deliberate selections are preserved.

The pile-region cross section reserves the nominal centered pile width plus the existing horizontal placement allowance. Obstructed bottom rows split beside that envelope. Row elevations retain the source cover, hoop diameter, bar diameter and row separation; a second row that clears the head can extend across the section. The between-pile section retains every continuous bar at the same transverse position, then adds the requested span bars into the available gaps. Its effective depth uses the combined area-weighted centroid. The central gap remains in pile-region service spacing checks. Bottom shrinkage spacing uses the between-pile row, matching original Mathcad `Spa.shrink.bot := SP[2]`; top, side and hoop spacing remain included.

Pile embedment and bar-to-pile clearance are required project inputs: Mathcad and the FBMP XML do not establish them. Their zero placeholders are unconfirmed, and searches stop until they are confirmed. Existing saved cases migrate their common positive bar size into both regions and preserve their loads. The source Mathcad has separate positive-region counts and between-pile U-bars; the explicit obstruction screen and independent sizes extend that calculation.

Weight counts continuous bars once over the clear cap length and adds every drawn span bar, including its 90-degree hook bends and 12db tails. End anchorage, laps, hoop bends and waste remain outside the comparison estimate. The screen checks drawn longitudinal bars against the hoop interior, minimum clear bar spacing and the pile envelope. The hoop outline is a cross-section guide; actual hoop stations around pile heads remain a detailing task. Multiple loops and U-leg positions remain unresolved.

### Imports and exports

- **One-file reuse:** load the case JSON through the workbench upload control.
- **Three-workbook converter:** `import_workbooks` reads the supplied `Max_PierCap_*_Design` layouts, checks coordinates/headers and records governing rows/hashes. Confirm all exports belong to the same run. Nominal pile width and section dimensions remain declared project data.
- **New loads from one XML:** use **Upload FBMP XML → review preview → Apply XML inputs** in the live workbench, then rerun the search. Supports the reviewed FB-MultiPier 6.1.0 static, English-unit, uniform pile-bent layout. Geometry/materials and strength/Service I envelopes come from the same source; trial steel is retained. See [FBMP_IMPORT.md](FBMP_IMPORT.md) for supported models, force signs, station recovery and audit details. `.out` parsing remains unsupported.
- **Review exports:** saved in timestamped `exports/` subfolders; originals are not overwritten. `alternatives.csv` includes every passing layout. `filtered_alternatives.csv` includes every current filter match, across all pages, with stable candidate IDs; `review.json` records the target, scope and matching count. For Blockpad, use **Upload Blockpad journal → Choose Files (Colab) → Export a Blockpad review copy**. Wait for **JOURNAL READY** before exporting. Colab downloads the new `.bpad`; **Download last .bpad copy** retries the download. Windows paths are only usable by a notebook running on Windows. The exporter uses the current main calculator case, modifies only C005 in a new review copy, and preserves other project data.

After an import, look for **LOADS IMPORTED SUCCESSFULLY** and verify the file name, analyzed section and M/V/T values in **ACTIVE FORCE SOURCE**. An XML preview is explicitly **NOT APPLIED** until Apply is clicked. The section study repeats its active source above Run and clears older plots after new loads. Rerunning the workbench cell preserves imported inputs/search choices within the same runtime and reconnects the study; use **Reset starting case** for an intentional reset. A fresh/deleted Colab runtime still needs a saved case loaded again.

When setup refreshes the calculation package, the workbench rebuilds any study still using the previous package version. It preserves section ranges, D/C target, cost rates, view settings and uploaded analysis cases, and clears old search results. Cleanup does not evaluate the old case. This prevents the retained study from raising `Expected case schema_version 1` after the workbench has migrated to independent positive-region inputs. Push the notebook and supporting files together, then run the updated cells from the top; this repair does not require deleting the runtime.

GitHub renders saved static notebook output, not running widgets. The Colab badge opens the notebook, and its setup cell obtains the supporting files automatically. Local Windows paths must be replaced with uploaded files. Download your case exports from Colab's Files panel before ending the runtime; they are stored in the temporary Colab environment. Each setup run refreshes a clean Colab checkout from the configured GitHub branch and clears cached calculation imports. Run all after refreshing so the controls use the updated code. Refresh preserves exports and untracked files; tracked edits, local-only commits, a wrong branch or an update obstruction stop setup with recovery instructions. Local Jupyter execution does not fetch or update Git. If you use another branch or fork, update the badge target and the setup cell's `REPO_URL` / `REPO_REF` together. Private repositories require an authenticated checkout accessible to the Colab runtime. The Colab XML upload, preview and Apply flow was verified in Chrome on 2026-09-29. Colab uses its native uploader (Upload FBMP XML → Choose Files), ipywidgets 7.7.1 and Plotly 5.24.1. Setup detects mixed runtime versions; save your case and notebook edits, restart the session, reload the browser page and Run all when upgrading an old session.

**Recovering from `cannot import name 'filter_candidates'`:** the older setup cell reused its first download, so an updated notebook could still load supporting revision `da6a342`. Push the notebook and the entire `pier_cap/` folder together, then reopen the notebook from GitHub. The updated setup refreshes the supporting code automatically. If you are still using the old setup cell, download any case/exports first, choose **Runtime → Disconnect and delete runtime**, reconnect and **Run all**. A plain session restart can leave `/content/D2MPDB` unchanged. The setup checks the required search functions and reports an incomplete publication clearly instead of failing later at an import.

### Validation and Git

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Regression checks cover the original Mathcad mechanics, independent positive regions, pile clearance, independent mechanics, force/geometry gates, invalid inputs, unit-aware vs. scalar search, cage geometry, imports/exports and widgets. The notebook is also executed from top to bottom during delivery verification. See `VALIDATION.md` for recorded results.

Commit the notebook, `pier_cap/`, tests, requirements, launcher and documentation together. `.gitignore` excludes the environment, exports, caches and runtime data. No commit or push is performed automatically.

Limited steel searches use a repeatable sample across the full selected grid; complete searches still evaluate every combination. Enabling cost comparison with incomplete rates keeps the study cages and quantity plots visible until valid rates are entered. XML import opens the Force diagrams tab automatically.


### Rebar continuity and minimum spacing (October 2026)

**Between-pile counts are ADDITIONAL.** Four continuous #8 bars plus four added
#7 bars means eight bars in the span, with combined area `4 × 0.79 + 4 × 0.60`.
Changing a continuous bar changes both pile and span capacity. Zero added bars
keeps the continuous cage everywhere. The inputs, tooltips, search labels and live
summary all state this convention. Schema-1/2 saved cases convert former total
counts once by crediting continuous steel area per row and rounding any remaining
area up to whole additional bars, with a visible migration notice. Review the combined area for mixed sizes or smaller former span totals.
The old common-cage programmatic search uses zero added bars; independent
`span_counts` now always means additional counts.

Minimum-spacing checks use actual diameters and drawn positions, report actual
and required clear distance and fail crowded cages in both the live register and
steel search. The AASHTO cast-in-place same-layer minimum is the greatest of
1.5 bar diameters, 1.5 times maximum coarse aggregate size, and 1.5 in. Multilayer
clearance uses the larger of one bar diameter and 1 in, with vertical alignment
checked when layer clearance is at most 6 in. A larger entered project minimum
also applies. The 0.75 in aggregate placeholder is **unconfirmed** until changed
or confirmed from the mix design; its pending status remains visible.

Basis: AASHTO LRFD BDS 5.10.3.1.1 and 5.10.3.1.3, referenced by
[FDOT 2026 Structures Detailing Manual 4.3.2](https://www.fdot.gov/Structures/StructuresManual/CurrentRelease).
SDM 4.3.4 calls for fit/clearance calculations and drawings; 4.3.7 covers section
representation. General 90-degree hook geometry follows LRFD 5.10.2: 6db inside
bend diameter through #8, 8db for #9–11, and a 12db straight tail. Applicable
contract criteria, fabrication tolerances, cover and full FDOT detailing review
remain project responsibilities. The notebook does not apply drilled-shaft
spacing rules to a cast-in-place cap.

The plan and elevation share the section coordinates. Blue steel is continuous;
orange steel is additional in each clear span, turning up outside the pile
placement/clearance envelope. Hook fit and clashes with the continuous cage and
other hook tails are screened. **Standard bend geometry is not proof of
anchorage:** required development from the critical section, cutoff extension,
end development and splices remain pending. Multiple loops and U-leg topology
remain unresolved. Pile embedment is drawn to the entered height above the cap
underside; the below-cap pile length is schematic.

The hoop plot separates along-cap center pitch and clear gap from across-cap leg
spacing, with numerical limits. Global and low-shear samples are not an invented
station schedule: interval boundaries and first-hoop station are unavailable.
Full-depth hoops through an embedded pile head conflict geometrically, so a
separate pile-head hoop arrangement remains pending. A manual leg-spacing
number cannot override the actual outer-hoop width check.

Case exports include `rebar_clear_spacing.csv` and a self-contained interactive
`reinforcement_detail.html`. Blockpad review copies contain current numerical
formulas and a clearly labeled cage-position snapshot; re-export the geometry
after changing inputs there. Notebook-only spacing/hook checks must also be
rerun; native Blockpad engineering review is not implied by an export.
