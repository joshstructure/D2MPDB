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
- A check mark in a node label and a double border mean the node has a recorded sign-off (amber border when it is stale). Signed edges carry the check mark in their label. See [Verification sign-offs](#verification-sign-offs).
- With a node selected, **Verification walk** steps through everything that feeds it, one relation at a time.
- The **As of** slider shows the record as it stood on a date. See [Time scrubber](#time-scrubber).

## What is in the graph

The graph has three levels.

1. **Nodes.** Every registered source, placed in a stage column. The stage columns are Project inputs, Superstructure, Geometry, Analysis (FBMP), Cap and wall design, Reports, CAD model and Deliverables.
2. **Edges.** The `depends_on` relations in the source register, drawn in the direction of information flow. The generator also derives these edges:
   - FBMP export to saved case: the governing load case for each force input, and a comparison of the analysis identity hash.
   - Saved case to generated Mathcad cap sheet: 58 input-mapping rows, each with before and after values.
   - Sources to backwall case: each backwall input names its source.
   - Geometry notebook to cap cases: machine geometry consistency checks.
   - Journal to cap cases: the cap formulas that name a journal module (`BridgeGeometry_2Beam`, `PedBridge`), with the saved case value. See [Cap formula traces](#cap-formula-traces).
3. **Parameters.** Values carried on nodes and edges. Each parameter has a `role`:

| Role | Where | What it is |
| --- | --- | --- |
| `input` | Case nodes | A saved-case input with its unit, and the governing FBMP load case where the case records one |
| `identity` | FBMP XML nodes | The file's SHA-256 against the register and against the hash the saved case requires |
| `envelope` | FBMP XML nodes | One row per member, exact limit state and force component (M2, M3, V2, V3, T): signed minimum and maximum, absolute maximum, governing load case, combination, element and end |
| `summary` | FBMP XML nodes | The XML's own `OUTPUT_SUMMARY` extremes, with a magnitude comparison against the element-end rows |
| `formula` | Case nodes, journal edges | One row per cap formula definition: name, formula, evaluated value, note |
| `output` | Mathcad sheet nodes | Verification snapshot values |

The generator reads these files:

| Input | Contributes |
| --- | --- |
| `project_current/source_register.csv` | Nodes and `depends_on` edges |
| `project_current/decisions.md` | D-### decisions |
| `project_current/coherence/items_snapshot.csv` | COH-### items |
| `project_current/coherence/machine_checks.json` | Health statuses |
| `project_current/cap_design/{pier,end_bents,end_bent_2,backwall}/selected_case.json` | Inputs with units, governing FBMP load cases, backwall input sources; the cap cases are also evaluated for the formula trace |
| `project_current/fbmp/**/*.XML` (every registered export that is present) | Envelope and summary rows on the XML node |
| `FBMP_Envelope_Extractor.ipynb` | The embedded, stdlib-only extractor that computes the envelopes |
| `pier_cap/` (the cap notebook's package, via the project `.venv`) | The formula trace; the package content hash is recorded as `cap_package` |
| `journal/D2_I95_Project_Journal.bpad` | Whether each journal module and variable named by a cap formula occurs in the journal |
| `exports/cap-mathcad-20261017/` (when present) | Source and verification record, `Verification.json`, the three Input Mapping CSVs |
| `lineage/signoff.json` | Verification sign-offs, merged as `node.signoff` and `edge.signoff` |

At the time of writing the build has 35 nodes, 67 edges, 1989 parameters, 42 decisions and 28 coherence items.

### FBMP envelopes

Each registered FB-MultiPier XML that is present (PIER-XML, PIER-MINTIP-XML, EB-XML, EB-MINTIP-XML; EB2-XML is missing) carries the full strength and service envelope tables as parameters. They are computed by the same code as the standalone [FBMP_Envelope_Extractor.ipynb](../FBMP_Envelope_Extractor.ipynb): the generator executes the notebook's first code cell up to its Colab interface and calls `read_fbmp`, `limit_state_table`, `native_envelopes` and `comparison`. The rows use the XML's original element-local I/J end-force signs for each exact limit state and member (the cap and each pile); no signs are changed, no load factors or unit conversions are applied, and no interior peaks are inferred.

The first parameter on each XML node is its identity row, and every envelope row repeats the file's SHA-256 in `xml_sha256`. The registered pier and End Bent 1 exports are not the exports the selected reports name, so their identity rows read `MISMATCH: PIER-CASE requires c8420fad…` and `MISMATCH: EB-CASE requires 23bb3afc…`. Those envelopes therefore describe the preserved earlier analyses, not the analyses behind the current cap cases, and the FBMP-export-to-case edge keeps its governing rows and `identity-mismatch` flag. The minimum-tip variants have no saved case and read `VARIANT`. The node's `envelope_source` records the extractor version, FBMP version, load cases, members and the extractor's diagnostics: for both pier exports the `OUTPUT_SUMMARY` M2 and V3 magnitudes differ from the exported element ends, which the `summary` rows show as `DIFFERENT MAGNITUDE`.

### Cap formula traces

Each registered cap case (PIER-CASE, EB-CASE, EB2-CASE) carries the cap notebook's formula trace as `formula` parameters: one row per definition in `pier_cap/data/c005_formulas.json`, with the formula, the value the package evaluates from the saved case, and the definition's note. The generator imports `pier_cap.model` from the working tree, runs `evaluate` on `selected_case.json` and calls `formula_trace`, exactly as the notebook's own export does. The 1 October case export under `exports/` is not used; it belongs to an older case.

Read the trace for what it is: the working-tree package's evaluation of the saved case at build time. It is not the registered report's own calculation (the register notes that existing reports were not regenerated with the current tool), and the package status it records (`formula_trace.package_status`) is not engineering acceptance. Where the package replaces a sectional row with an actual-cage LRFD check, the row's formula is that check's basis text and its value the check status and D/C ratio.

The five formulas that name a journal module (`b`, `h` from `BridgeGeometry_2Beam`; `C_t`, `C_b`, `C_s` from `PedBridge`) also appear on a journal-to-case edge, with `module_in_journal` and `variable_in_journal` recording whether those names occur in the registered journal file, and `analysis_geometry` showing the value FBMP import wrote from the XML cap section where the case records one. The formula is the tool's definition; the value is the saved input. The graph does not compare it with the journal's live value.

If the package cannot evaluate a case (missing dependencies, a case that fails validation), the case node records `formula_trace.available = false` with the reason, the journal edge is omitted, and nothing is guessed. At the time of writing all three cases trace without user input.

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

## Verification sign-offs

[`signoff.json`](signoff.json) is the QC record beside the graph. It is hand-edited and committed. Each entry is a statement by a named person that a node or a relation was checked:

```json
{
  "id": "EB-XML->EB-CASE",
  "by": "J. Doe",
  "on": "2026-10-17",
  "basis": "Governing cases read against the FBMP summary table",
  "hashes": {
    "source": "<SHA-256 of EB-XML in the register at the time>",
    "target": "<SHA-256 of EB-CASE in the register at the time>"
  }
}
```

- `id` is a node id or a `source->target` edge id from the graph.
- `by`, `on` (ISO date) and `basis` are required. `basis` says what was checked and against what.
- `hashes` is `{"node": ...}` for a node and `{"source": ..., "target": ...}` for an edge. They are the register SHA-256 hashes when the person signed. An empty string is allowed where the register has no hash, such as the unregistered placeholder nodes; such a sign-off is shown as not hash-pinned.

The generator validates the file and stops with the offending entry named if it is malformed. It merges each entry into `node.signoff` or `edge.signoff` and marks it **stale** when the recorded hashes no longer equal the current register hashes. When one id has several entries, the latest `on` date is the effective one and the others are kept under `previous`. Entries that name an id not in the graph are listed under `signoff.orphans`. The sidecar is a fingerprint input, so editing it makes the outputs stale until the next rebuild.

In the viewer, each node and relation pane has a **Sign-off** section with the recorded statement, the recorded and current hashes and the stale state. **Verification walk** on a node lists the hops of its upstream cone in information-flow order (every edge, ordered so that a hop's source has been reached before it) and shows each hop's checks, flags, identity comparisons, parameters and sign-off state, with counts of signed, unsigned and stale hops.

The page is static, so it cannot write the sidecar. **Draft sign-off** on a node, relation or hop opens a form for the name, date and basis, then produces the JSON entry with the current hashes filled in, with a Copy button. Paste it into the `signoffs` list of `signoff.json` and rebuild. **Keep for download** holds the draft in the page until **Download signoff.json** writes the recorded entries plus the kept drafts as a complete sidecar.

The graph never asserts engineering acceptance by itself. Nothing creates or ticks a sign-off except a person editing `signoff.json`.

## Time scrubber

The **As of** slider in the top bar spans the dates found in `registered_on`, the decision dates and the coherence items' `Last reviewed`. Moving it back fades the nodes registered after the chosen date (and their edges), hides later decisions and coherence items in their tabs, and adds an **As of** section to the Overview listing the sources registered, decisions recorded and coherence items reviewed between the previous date on the slider and the chosen one. **Latest** returns to the newest date, where nothing is filtered. Sign-offs are not filtered by the slider.

## Rebuild and check

```powershell
.venv\Scripts\python.exe scripts\build_lineage_graph.py
.venv\Scripts\python.exe scripts\build_lineage_graph.py --check
.venv\Scripts\python.exe -m unittest tests.test_lineage_graph -v
```

The first command rewrites `lineage.json` and `index.html`. `--check` reports whether they are stale without writing anything. [`scripts/build_lineage_graph.py`](../scripts/build_lineage_graph.py) is the generator. A build takes about half a minute, most of it evaluating the three cap cases, and needs the project `.venv` because the formula trace imports `pier_cap`.

[`tests/test_lineage_graph.py`](../tests/test_lineage_graph.py) fails until the outputs are rebuilt after a source change.

The fingerprint covers every file the generator reads plus the content of the three formula traces (`derived` in `lineage.json`), so the graph is stale whenever the cap package's answer for a saved case changes, not whenever any package file is edited. `cap_package.sha256` records the package content at the last build.

Rebuild after any change to the source register, decisions, the coherence tracker, saved cases, FBMP XML exports, the envelope notebook, the cap package, Mathcad exports or `signoff.json`. Rebuild after editing `viewer.html` too, because `index.html` is generated from it.

## Limits

The graph records what the project files say about each other. It is not engineering acceptance. The only calculations it runs are the two reused project extractors described above, on the saved cases and XML exports as they are; it changes no source. The EMULATED Mathcad sheets have not been recalculated natively, and the formula traces are the current package's evaluation, not the registered reports'. A sign-off in `signoff.json` is the signer's statement, not the graph's; the graph only reports whether the hashes it was pinned to still hold.
