# D2 Design Atlas

A read-only hybrid atlas: the full project source register, explicitly curated
missing handoffs, and a detailed pier-cap value trail. It reads existing files;
it never changes the register, coherence tracker, journal, cases or native models.

## Open or refresh

Run `Start-DesignAtlas.ps1` from the repository. It rebuilds the local snapshot
and opens `design_atlas/dist/index.html`; no web server or external JavaScript
dependencies are needed. Use `-NoOpen` to rebuild only.

Equivalent command, from the repository root:

```powershell
.venv\Scripts\python.exe -m design_atlas.build
```

The private hosted copy is a published snapshot. A local refresh does **not**
automatically update that publication. Publish the rebuilt `dist/` directory
through the same Sites project to refresh it. The initial site is
`https://d2-pier-cap-design-atlas.ochrebee15.chatgpt.site`.

## Explore

- Drag the full map to pan; use the wheel or +/- controls to zoom. **Fit full
  map** includes every registered source. **Pier-cap trail** returns to the
  first detailed lane. The source directory is also keyboard accessible.
- Select a component to isolate inputs, outputs or both. Wider registered
  dependencies are optional; recorded cycles are handled without recursion.
- Select a value to focus the graph and trace pane on its actual evidence path.
  The inspector shows saved values, governing audit records, transformations,
  report inputs and supported literal Mathcad definitions.
- **View exact source** opens the locator, excerpt and exact-byte fingerprint.
  When opened locally from `design_atlas/dist/`, it also links to the original
  repository file. Hosted copies show the embedded evidence snapshot.
- **Coverage & sources** includes current pier-related tracker records, read
  directly from the workbook, and the boundaries of each check.

## What is automatic

`build.py` reads all rows/dependencies in `project_current/source_register.csv`,
checks registered fingerprints (including the specified LF-normalized notebook
basis), and records separate exact-byte hashes for evidence files. It checks
that sources remain unchanged throughout ingestion.

The detailed adapter reads:

- the selected pier JSON and its retained FBMP audit;
- the selected report's embedded case, compared structurally to the JSON;
- the preserved prior XML's pile-head node Z values;
- the generated 17 October pier Mathcad file, mapping CSV and provenance receipt;
- the current coherence workbook, without changing any cells.

Mathcad checks evaluate **literal scalar input definitions only**, with explicit
dimensions and units. Worksheet formulas, cached output values and native solver
execution are not treated as independently verified results. Unsupported
expressions remain unsupported. Only explicit mapping rows are compared.

The enabled transverse runs take precedence over dormant scalar `Bar_v`, `s_G`
and `s_L` inputs. Individual run settings and development flags are inspectable.

## What is curated

`manual_links.json` declares the unmapped RFQ handoff, missing issued PDF and
current-tool context. Each edge carries its stated basis. Extend that file for
documented manual relationships; do not imply adoption or evidence from a
filename. New parameter mappings belong in the bounded adapter with tests.

At initial capture, the selected pier case requires XML SHA-256 `c8420fad…`,
while the registered prior XML is `a992aa33…`. The atlas preserves that conflict.
The generated Mathcad sheet is an unregistered output, and its receipt records
no native recalculation. No issued PDF is connected. Matching inputs do not
establish design approval or validate unlinked source history.

## Validation

```powershell
.venv\Scripts\python.exe -m unittest tests.test_design_atlas -v
node --check design_atlas/web/atlas.js
```

The browser app is buildless and uses no external network requests. Generated
`dist/` and browser QA outputs are ignored by Git. The source data is a dated
snapshot; it cannot observe local file changes from a hosted browser.
