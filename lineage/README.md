# Information lineage graph

The graph shows how the project's registered sources, saved cases, generated Mathcad cap sheets and deliverables depend on one another, and which parameters pass across each dependency. It is built from the project files and shows where they agree, have changed or are missing.

[`lineage.json`](lineage.json) is the graph. [`index.html`](index.html) is a single-file interactive viewer with the graph embedded. The hand-written viewer template is [`viewer.html`](viewer.html), and `index.html` is generated from it.

## Open it

Double-click [`index.html`](index.html) to open it in a browser. The viewer loads Cytoscape 3.30.4 from cdnjs, so it needs an internet connection the first time it is opened. Everything else is embedded.

- Click a node to isolate its upstream and downstream stream. The other nodes fade. The **Isolate** checkbox removes them instead.
- Click an edge to see the parameters that cross it.
- Search matches names, paths, parameter names, decisions and issues.
- The health chips filter the graph by health status.
- The decision and coherence tabs list the D-### decisions and COH-### items and highlight the nodes they reference.

## What is in the graph

The graph has three levels.

1. **Nodes.** Every registered source, placed in a stage column. The stage columns are Project inputs, Superstructure, Geometry, Analysis (FBMP), Cap and wall design, Reports, CAD model and Deliverables.
2. **Edges.** The `depends_on` relations in the source register, drawn in the direction of information flow. The generator also derives these edges:
   - FBMP export to saved case: the governing load case for each force input, and a comparison of the analysis identity hash.
   - Saved case to generated Mathcad cap sheet: 58 input-mapping rows, each with before and after values.
   - Sources to backwall case: each backwall input names its source.
   - Geometry notebook to cap cases: machine geometry consistency checks.
3. **Parameters.** Values carried on nodes and edges.

The generator reads these files:

| Input | Contributes |
| --- | --- |
| `project_current/source_register.csv` | Nodes and `depends_on` edges |
| `project_current/decisions.md` | D-### decisions |
| `project_current/coherence/items_snapshot.csv` | COH-### items |
| `project_current/coherence/machine_checks.json` | Health statuses |
| `project_current/cap_design/{pier,end_bents,end_bent_2,backwall}/selected_case.json` | Inputs with units, governing FBMP load cases, backwall input sources |
| `exports/cap-mathcad-20261017/` (when present) | Source and verification record, `Verification.json`, the three Input Mapping CSVs |

At the time of writing the build has 35 nodes, 64 edges, 619 parameters, 42 decisions and 28 coherence items.

### Unregistered nodes

Unregistered nodes have `registered=false` and are drawn dashed.

| Node | What it is |
| --- | --- |
| RFQ | Placeholder root. Not in the repository |
| FBMP-TOOL | The native FB-MultiPier analysis. Only its XML exports are registered (COH-013, COH-028) |
| MCAD-CAP-TEMPLATE | The supplied End Bent 1_10-8.xmcd template |
| MCAD-CAP-EB1, MCAD-CAP-EB2, MCAD-CAP-PIER | The three generated Mathcad cap sheets |

### Health colors

Node colors come from `machine_checks.json`.

| Status | Meaning |
| --- | --- |
| MATCH | Registered bytes or text match the file |
| CHANGED | The file differs from the registered revision |
| MISSING | The file is absent, or no source is selected |
| EMULATED | Generated Mathcad sheet. Native recalculation has not been performed |
| NONE | No machine check. Unregistered or placeholder |

### Edge flags

| Flag | Meaning |
| --- | --- |
| identity-mismatch | A case names a different raw FBMP export hash than the registered XML |
| review | A DEP machine check marks the dependency as missing, changed or awaiting adoption |
| unregistered | The edge involves an unregistered node |

## Rebuild and check

```powershell
.venv\Scripts\python.exe scripts\build_lineage_graph.py
.venv\Scripts\python.exe scripts\build_lineage_graph.py --check
.venv\Scripts\python.exe -m unittest tests.test_lineage_graph -v
```

The first command rewrites `lineage.json` and `index.html`. `--check` reports whether they are stale without writing anything. [`scripts/build_lineage_graph.py`](../scripts/build_lineage_graph.py) is the generator.

[`tests/test_lineage_graph.py`](../tests/test_lineage_graph.py) fails until the outputs are rebuilt after a source change.

Rebuild after any change to the source register, decisions, the coherence tracker, saved cases or Mathcad exports. Rebuild after editing `viewer.html` too, because `index.html` is generated from it.

## Limits

The graph records what the project files say about each other. It is not engineering acceptance, and it does not rerun any calculation. The EMULATED Mathcad sheets have not been recalculated natively.

## Not yet built

- A time scrubber over `registered_on` and decision dates.
- A verification sign-off sidecar, so the graph doubles as the QC record.
- FBMP envelope extraction and a cap notebook formula trace as further parameter sources.
