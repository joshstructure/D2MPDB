# D2MPDB notebooks

## Pier-cap design notebook

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
4. Run **Search steel layouts**. The default list evaluates 1,944 combinations. Adjust allowed values and ranking objective as needed. Search is deterministic code and uses no AI calls.
5. **Apply selected layout**. Every retained candidate is rechecked by the unit-aware calculator. Service III/fatigue and other unresolved scope remain explicit.
6. Export the case/checks and optionally a new Blockpad C005 review copy. Recalculate that copy in Blockpad and reconcile narrative/source notes before final review.

The initial JSON bundle and all input units are documented in `pier_cap/data/default_case.json` and `c005_formulas.json`. It carries analysis provenance with the force data. Changes to analysis geometry invalidate the force match and block the steel search until a corresponding analysis is supplied. An explicit manual analysis-record action is available after entering updated forces.

### Search and drawing limits

The automatic family uses one continuous top row and bottom row, a common main bar size, the same bottom layout at pile/bearing regions, one closed hoop and uniform spacing. Other layouts can be investigated manually. Bounded enumeration reports the evaluated/total counts and whether the list was exhausted; it does not claim a global optimum outside those choices.

Weight is a gross comparison estimate, excluding hooks, laps, anchorage, bends and waste. The cage-fit screen checks drawn bar positions against the hoop interior and an editable trial clear spacing. It is not a complete detailing check. Multiple loops and U-leg positions are unresolved in the source inputs and cannot silently pass the search.

### Imports and exports

- **One-file reuse:** load the case JSON through the workbench upload control.
- **Three-workbook converter:** notebook section 5 reads the supplied `Max_PierCap_*_Design` layouts, checks coordinates/headers and records governing rows/hashes. Confirm all exports belong to the same run. Nominal pile width and section dimensions remain declared project data.
- **Direct FB-MultiPier `.out`/`.xml`:** not implemented without a representative source file and verified mapping.
- **Review exports:** saved in timestamped `exports/` subfolders; originals are not overwritten. The Blockpad exporter modifies only C005 in a new review copy, not other project data.

GitHub renders saved static notebook output, not running widgets. In Colab, clone/download the whole repository and install requirements first, then run from the repository directory. Local Windows paths must be replaced with uploaded files. Colab execution has not been independently verified for this delivery.

### Validation and Git

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Regression checks cover the 324 imported definitions, independent mechanics, force/geometry gates, invalid inputs, unit-aware vs. scalar search, cage geometry, imports/exports and widgets. The notebook is also executed from top to bottom during delivery verification. See `VALIDATION.md` for recorded results.

Commit the notebook, `pier_cap/`, tests, requirements, launcher and documentation together. `.gitignore` excludes the environment, exports, caches and runtime data. No commit or push is performed automatically.
