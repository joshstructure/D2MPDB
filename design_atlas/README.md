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

- Drag the full map to pan; use the wheel or +/- controls to zoom. **Clear
  selection** undims every node without moving the map. The **dashed-square
  Fit map** button fits every source without changing the selection. The atlas
  opens with no assumed topic. The source directory is also keyboard accessible.
- The **Arrange map** buttons reposition the same complete map and fit it to
  the canvas. **Default**, leftmost, restores alphabetical stage columns:
  **Basis**, **Analysis**, **Design**, **Detailing**, **Deliverables**.
  **Component × stage** uses component rows and stage columns; **File role**
  groups journals, inputs, tools, models, cases and reports; **Evidence gaps**
  groups the recorded source statuses, with gaps first.
- **Flow** orders all non-context relationships from source to use, keeping
  feedback cycles in the same column. **Impact** groups the number of distinct
  downstream sources reachable through those relationships; this is connectivity,
  not engineering risk. **Neighborhood** arranges upstream, selected, downstream,
  feedback and other sources around the selected node. With no node selected it
  keeps the default arrangement and prompts for a selection. Shared sources
  appear only once in every view; no separate pier-cap group is restored.
- Layout changes preserve the selected node, parameter, filters and trace state.
  The layout is included in shareable links and restored by **Back**. Selecting
  a trail highlights nodes in place, except in **Neighborhood**, which rearranges
  around each new selection. Lines route through the gaps between cards.
- Find **Project journal** in the search or source directory. It connects to
  its **FBMP Entry — Pier** module in the same map.
  **FBMP Entry — End Bent** also connects to the registered end-bent runs.
  Select either module to inspect saved node identities, coordinates and loads.
- **End-bent cap report** now opens its own saved inputs and transverse-run
  settings. Its trace includes the end-bent journal entry, required FBMP run,
  retained audit and saved case. The required run and registered XML remain
  distinct when their fingerprints differ. End-bent value IDs are scoped to
  that component so a pier parameter with the same symbol cannot be substituted.
  Components without extracted values show a coverage message and a source-record
  action; registered-only connections can be opened directly in pane 02.
  For analysis results such as negative moment, the journal appears under
  **Model inputs upstream of this result**; it is not labeled as the source of
  an identical moment value.
- Select a component to isolate upstream sources, downstream uses or both. Wider registered
  dependencies are optional; recorded cycles are handled without recursion.
  The trace starts collapsed as a narrow sidebar. Select any source to reopen it,
  or use the sidebar chevron to expand or collapse it manually. Collapsing keeps
  the selected node and map zoom; **Clear selection** collapses it again. On
  small screens the collapsed trace becomes a compact bar below the map.
  The isolated trace orders sources by their connections and draws directional
  arrows for actual relationships. Separate branches keep their own lines;
  dashed lines are registered dependencies. The selected component is marked
  **You are here**. Recorded feedback links retain their actual direction.
- **View parameters** opens values at the selected node. **Received inputs**
  shows values with a documented upstream handoff. **Defined / derived here**
  includes retained local settings and formulas. **Origin unconfirmed** means
  the captured files do not establish the origin. A retained local setting is
  not proof of first-ever authorship. These roles are node-relative: a case
  setting can become a received input at the Mathcad node.
- Each role includes its basis and exact source evidence. Formula extraction
  currently covers four provided-reinforcement-area definitions; numerical
  results are explicitly unevaluated. The active bar/pitch summaries are
  derived by the atlas from saved runs and labeled as summaries.
- **Back** (or browser Back) restores the previous selection, parameter filters
  and map position. **Overview** clears filters and fits the full map. Selecting
  a different source resets its parameter filters so stale filters cannot hide
  that node’s inputs. **How to use** opens a short guide.
- Select a value to focus the graph and trace pane on its actual evidence path.
  The inspector shows saved values, governing audit records, transformations,
  report inputs and supported literal Mathcad definitions.
- **View exact source** opens the locator, excerpt and exact-byte fingerprint.
  When opened locally from `design_atlas/dist/`, it also links to the original
  repository file. Hosted copies show the embedded evidence snapshot.
- **Show on map**, beside each exact-source button, selects and centers that
  step's component and returns to the map. **Back** restores the previous value
  trail and scroll position.
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
- the native journal’s `FBMPPier` and `FBMPEndBent` node-entry tables, including
  cell formulas, saved results, unit definitions and exact table/cell locators.

Journal values are read from native saved cells without recalculation. Mixed
feet/inches strings and historical node mappings remain as recorded. Journal
handoffs are user-confirmed workflow provenance; exact journal revision and
per-cell transfer into each FBMP run remain unverified. The source-register
journal fingerprint status is retained. No native journal file is edited.
The selected pier case and report paths follow the current source register.

Mathcad checks evaluate **literal scalar input definitions only**, with explicit
dimensions and units. Worksheet formulas, cached output values and native solver
execution are not treated as independently verified results. Unsupported
expressions remain unsupported. Only explicit mapping rows are compared.

The enabled transverse runs take precedence over dormant scalar `Bar_v`, `s_G`
and `s_L` inputs. Individual run settings and development flags are inspectable.

## What is curated

`manual_links.json` records the user-confirmed journal-to-FBMP workflow and
declares the unmapped RFQ handoff, missing issued PDF and
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
node --check design_atlas/web/layouts.js
node tests/test_atlas_layouts.js
.venv\Scripts\python.exe -m unittest tests.test_end_bent_atlas -v
```

The browser app is buildless and uses no external network requests. Generated
`dist/` and browser QA outputs are ignored by Git. The source data is a dated
snapshot; it cannot observe local file changes from a hosted browser.
