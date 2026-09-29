# D2MPDB notebooks

## Pier-cap design notebook

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/joshstructure/D2MPDB/blob/main/Pier_Cap_Design_Optimizer.ipynb)

**From GitHub:** click **Open in Colab**, connect to a runtime, then choose **Runtime → Run all**. The first cell downloads this repository's `main` branch, installs the notebook's Colab dependencies and enables its custom widgets. Push the notebook, `pier_cap/` and `requirements-pier-cap-colab.txt` together before using the link. A standard CPU runtime is sufficient.

Open **[Pier_Cap_Design_Optimizer.ipynb](Pier_Cap_Design_Optimizer.ipynb)** in JupyterLab or VS Code, select the project `.venv` Python kernel, and **Run All**. The notebook contains the live calculator, input widgets, reinforcement sections, pile/hoop drawings, capacity/stress plots, D/C register, bounded steel search, and case exports.

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

1. Load a saved `selected_case.json`, or start with the supplied four-pile example.
2. Review force-source geometry, loads, materials, assumptions and pending actions.
3. Change bar counts/sizes/spacing and inspect the live drawings, stress plots and D/C register.
4. Run **Search steel layouts**. The default list evaluates 1,944 combinations and retains **all 324 passing layouts**, each rechecked with units. Search is deterministic code and uses no AI calls.
5. Set **Max D/C** (for example, `0.90`). The workbench defaults to **Strength checks only** for this margin target; choose **All available checks** if you also want to tighten spacing and other detailing ratios. Browse with **Page / Previous / Next** and **Per page** (20, 50 or 100). Filtering and ranking reuse the finished search. **Apply selected layout** loads the selected candidate ID into the live drawings/checks. Service III/fatigue and other unresolved scope remain explicit.
6. Export the case/checks and optionally a new Blockpad C005 review copy. Recalculate that copy in Blockpad and reconcile narrative/source notes before final review.

The initial JSON bundle and all input units are documented in `pier_cap/data/default_case.json` and `c005_formulas.json`. It carries analysis provenance with the force data. Changes to analysis geometry invalidate the force match and block the steel search until a corresponding analysis is supplied. An explicit manual analysis-record action is available after entering updated forces.

### D/C margin and browsing all layouts

The search results are steel layouts for the current force case, not additional analysis load combinations. The table and selection dropdown show one page; every passing result is retained. Candidate IDs stay fixed within a search even when the filter or ranking changes. The comparison plot includes every filter match, with the candidate ID and controlling check in its hover label.

**All available checks** applies the target to the largest available ratio, including spacing, minimum reinforcement, strain and service criteria. **Strength checks only** applies it to flexure, shear, combined shear/torsion steel and longitudinal steel; every remaining available check must still pass at its original limit. The table displays both the filter D/C and all-check D/C so these targets cannot be confused. **Largest margin** ranks the selected scope.

For the starting case and default search choices, **no layouts meet an all-check target of 0.90**: transverse hoop-leg spacing sets a minimum overall ratio of about **0.9821**. **210 layouts meet the strength-only target of 0.90**, while their other available checks still pass. The empty-results message reports the best available ratio and controlling check; it never silently relaxes your target. Filtering does not complete pending Service III/fatigue inputs.

At a **0.97** target, **306** layouts meet the strength target and **zero** meet the all-check target. The live summary now separates **Strength D/C** from **All-check utilization**, and the search shows both match counts. The **Plots** tab breaks hoop spacing into its along-cap and across-cap components. See [the focused D/C floor review](DC_RATIO_REVIEW.md) for the original Mathcad trace and the explicit `41.25 / 42 = 0.98214` spacing calculation. A strength target is not a general multiplier for how much the loads can be increased.

Programmatically, `filter_candidates(result, max_dc=0.90, scope="strength")` returns zero-based indices into the complete `result.candidates` list; `candidate_case(result, index)` retrieves one. Displayed candidate IDs are those indices plus one. The old `SearchConfig.keep` cap has been removed; use list slicing only for your own previews.

### Cap cross-section study

Notebook **Section 5** adds a width/depth grid around the existing steel search, a clickable section heatmap, concrete/steel tradeoff plot, all-cage selection, live previews, local grid refinement and study exports. The starting ranges are widths **44–52 in by 4 in** and depths **36–60 in by 6 in**. Change the strength target and optional unit rates without repeating calculations. Exact repeated section searches are cached within the runtime.

Heatmap cells show **concrete volume and steel weight together**, or their separate costs using the cell-label control. Entering comparison rates enables a **lowest-cost section summary**, a map of **percentage above the cheapest explored match**, a ranked stacked concrete/steel/forms cost chart and a complete ranked table. Hover shows the material and cost differences from the cheapest section. All costs use your entered rates; zero-rate items are labeled as excluded. The selected cage has its own cost comparison, even when it is heavier than the cage used for the map.

Moment demand/capacity plots use blue shades; shear uses purple shades. The numerical D/C chart uses the same family colors, with orange for combined shear/torsion, gray for other checks, and red overriding the family color for a failed check. Values, labels and limits remain visible independently of color.

Default **fixed-force sensitivity** keeps imported forces constant and retains their original source geometry. **Analysis-matched mode** uses uploaded case JSON files for the corresponding sections and leaves missing analyses visible. This does not run FB-MultiPier. Ordinary changed-geometry checks still require matching force inputs. Read [SECTION_STUDY.md](SECTION_STUDY.md) for force provenance, geometry screens, quantities, limits and exports.

### Search and drawing limits

The automatic family uses one continuous top row and bottom row, a common main bar size, the same bottom layout at pile/bearing regions, one closed hoop and uniform spacing. Other layouts can be investigated manually. Bounded enumeration reports the evaluated/total counts and whether the list was exhausted; it does not claim a global optimum outside those choices.

Weight is a gross comparison estimate, excluding hooks, laps, anchorage, bends and waste. The cage-fit screen checks drawn bar positions against the hoop interior and an editable trial clear spacing. It is not a complete detailing check. Multiple loops and U-leg positions are unresolved in the source inputs and cannot silently pass the search.

### Imports and exports

- **One-file reuse:** load the case JSON through the workbench upload control.
- **Three-workbook converter:** notebook section 6 reads the supplied `Max_PierCap_*_Design` layouts, checks coordinates/headers and records governing rows/hashes. Confirm all exports belong to the same run. Nominal pile width and section dimensions remain declared project data.
- **Direct FB-MultiPier `.out`/`.xml`:** not implemented without a representative source file and verified mapping.
- **Review exports:** saved in timestamped `exports/` subfolders; originals are not overwritten. `alternatives.csv` includes every passing layout. `filtered_alternatives.csv` includes every current filter match, across all pages, with stable candidate IDs; `review.json` records the target, scope and matching count. The Blockpad exporter modifies only C005 in a new review copy, not other project data.

GitHub renders saved static notebook output, not running widgets. The Colab badge opens the notebook, and its setup cell obtains the supporting files automatically. Local Windows paths must be replaced with uploaded files. Download your case exports from Colab's Files panel before ending the runtime; they are stored in the temporary Colab environment. Each setup run refreshes a clean Colab checkout from the configured GitHub branch and clears cached calculation imports. Run all after refreshing so the controls use the updated code. Refresh preserves exports and untracked files; tracked edits, local-only commits, a wrong branch or an update obstruction stop setup with recovery instructions. Local Jupyter execution does not fetch or update Git. If you use another branch or fork, update the badge target and the setup cell's `REPO_URL` / `REPO_REF` together. Private repositories require an authenticated checkout accessible to the Colab runtime. Hosted Colab execution has not been independently verified.

**Recovering from `cannot import name 'filter_candidates'`:** the older setup cell reused its first download, so an updated notebook could still load supporting revision `da6a342`. Push the notebook and the entire `pier_cap/` folder together, then reopen the notebook from GitHub. The updated setup refreshes the supporting code automatically. If you are still using the old setup cell, download any case/exports first, choose **Runtime → Disconnect and delete runtime**, reconnect and **Run all**. A plain session restart can leave `/content/D2MPDB` unchanged. The setup checks the required search functions and reports an incomplete publication clearly instead of failing later at an import.

### Validation and Git

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Regression checks cover the 324 imported definitions, independent mechanics, force/geometry gates, invalid inputs, unit-aware vs. scalar search, cage geometry, imports/exports and widgets. The notebook is also executed from top to bottom during delivery verification. See `VALIDATION.md` for recorded results.

Commit the notebook, `pier_cap/`, tests, requirements, launcher and documentation together. `.gitignore` excludes the environment, exports, caches and runtime data. No commit or push is performed automatically.
