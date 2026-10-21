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

The public hosted copy is a published snapshot. Source-changing agents must run
the deterministic refresh gate and complete the publication workflow in
[UPDATE_WORKFLOW.md](UPDATE_WORKFLOW.md), as required by the root AGENTS.md.
`python -m design_atlas.refresh status` compares source hashes to the last
confirmed publication; `prepare` builds only when needed. The local scheduled
fallback uses the same gate. A plain local build is **not** a publication.
The existing site is
`https://d2-pier-cap-design-atlas.ochrebee15.chatgpt.site`.

## Explore

- Select any node and use **Download document** at the top of **02 / Isolated
  trace**. Journal modules offer **Download journal**, which saves the full journal
  containing that module. Downloads also sit beside exact-source links. Filenames
  and formats are preserved. Missing or unlinked documents say **Document unavailable**.
  Files follow the latest registered sources in each atlas update; verified public
  repository revisions host larger documents without duplicating them in the Site.

- The numbered calculations of the journal (**C001** to **C016**: wind, fence
  wind, temperature movement, uplift, pier wall and fins, cap design basis and
  the three cap designs, the three pile designs, the end-bent backwall, the MSE
  wall exclusion and the bearings) are the **Design** column of the default
  layout, each carrying its number; they are the calculations that will be
  issued as separate review documents. Search for a number such as **C011**
  to open one. Current named calculation reports and numeric or
  formula spreadsheet cells are discovered inside the registered journal.
  Geometry, materials, wind, movement, uplift and other calculations appear on
  the same map. Archived modules are excluded.
- Each calculation parameter shows its literal input or saved result, native
  formula, and exact XML source. **Inputs referenced by this formula** lets you
  inspect each unambiguous input and its source, including intermediate values
  within the same module. Received inputs follow explicit qualified references;
  derived formulas remain local. Missing results are never calculated, repeated
  definitions remain unresolved, and cell ranges are not expanded. Equal values
  alone do not create a link to a report or analysis run.

- Drag the full map to pan; use the wheel or +/- controls to zoom. **Clear
  selection** undims every node without moving the map. The **dashed-square
  Fit map** button fits every source without changing the selection. The atlas
  opens with no assumed topic. The source directory is also keyboard accessible.
- The workspace fills the browser on desktop monitors. A larger window reveals
  more map at the same zoom. Pane **02** folds into a side rail; pane **03** folds
  into a bottom bar, returning that space to the map. Select a node to reopen
  both panes, or use **View parameters** to reopen pane 03. Collapsing preserves
  the selected value and filters; **Back** restores the pane state too.
- The **Arrange map** buttons reposition the same complete map and fit it to
  the canvas. **Default**, leftmost, restores alphabetical stage columns:
  **Basis**, **Analysis**, **Design**, **Detailing**, **Deliverables**.
  **Component × stage** uses component rows and stage columns; **File role**
  groups journals, inputs, tools, models, cases and reports; **Evidence gaps**
  groups the recorded source statuses, with gaps first; **Assumptions** groups
  sources by their assumptions-and-gaps register entries, stale basis first,
  then open entries, then accepted entries, then sources with none.
- **Assumptions & gaps** come from the hand-edited register
  `project_current/coherence/assumptions.json` (see
  [Assumptions-and-gaps register](#assumptions-and-gaps-register)). Each entry
  appears as a card in pane 02's **Node details** tab, in the source
  directory's **Assumptions & gaps** group, and in **Coverage & sources**. A
  card badge counts the open or stale entries at that source. **Inspect record**
  opens the entry with its recorded and current basis hashes. **Draft
  assumption** opens a form that emits a JSON entry with the current register
  hashes filled in; the page cannot write the file, so paste the entry into the
  register and rebuild.
- Pane **02** has **Source flow** and **Node details** tabs. Node details uses
  the pane's full reading area for status, assumptions, gaps and source notes,
  including while tracing an individual value. Stale and open entries appear
  first; the tab badge counts them. Switching tabs preserves the selection and
  each tab's scroll position. Use Left/Right arrow keys to switch focused tabs.
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
- the current coherence workbook, without changing any cells;
- the assumptions-and-gaps register, compared with the current register hashes.
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

## Assumptions-and-gaps register

`project_current/coherence/assumptions.json` (schema `d2mpdb.assumptions-register`,
version 1) is the one place for small engineering gaps, placeholders,
assumptions and judgments that used to be scattered across decision prose,
notebook pending lists, journal text and tracker rows. It is hand-edited and
committed; nothing generates it. An entry records:

- `id` (stable `A-###`), `kind` (`assumption`, `gap`, `placeholder` or `judgment`);
- `statement` and `where` it bites (journal module, model, report);
- `nodes`: the atlas node ids the entry is pinned to;
- `magnitude`: `value`, `unit` and `sized_by`, the one quantity the judgment
  rests on. Engineering values the journal owns are not duplicated here;
- `disposition`: `status` (`accepted-negligible`, `pending` or `closed`), the
  decision reference `D-0xx` and the date; `owner`;
- `coherence_items`: related `COH-###` ids; `references`: repository paths;
- `basis`: register source ids mapped to the SHA-256 each was judged against.

`build.py` attaches the entries to their nodes, counts open or stale entries on
each node, and marks an entry **stale** when the source register now adopts a
different revision of any basis source (the current register hash differs from
the recorded one). A stale badge means the basis moved, never that the judgment
was re-made; re-check the entry and record the new hashes. A file on disk that
differs from its registered revision is reported by the source checks, not by
the register. `tools/project_coherence.py` validates the file (unique ids,
kinds, dispositions, registered basis sources with 64-hex hashes, known COH ids)
and lists open and stale entries in `latest_review.md`. The register is a
refresh-gate input: editing it makes the hosted atlas `refresh_required`. The
build rejects entries that name atlas nodes it cannot find.

## Validation

```powershell
.venv\Scripts\python.exe -m unittest tests.test_design_atlas -v
.venv\Scripts\python.exe -m unittest tests.test_project_coherence tests.test_atlas_refresh -v
node --check design_atlas/web/atlas.js
node --check design_atlas/web/layouts.js
node tests/test_atlas_layouts.js
.venv\Scripts\python.exe -m unittest tests.test_end_bent_atlas -v
```

The browser app is buildless and uses no external network requests. Generated
`dist/` and browser QA outputs are ignored by Git. The source data is a dated
snapshot; it cannot observe local file changes from a hosted browser.
