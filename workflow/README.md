# BPAD journal workflow

The working repository is `C:\github\D2MPDB`. The canonical file is
`journal/D2_I95_Project_Journal.bpad`. It is an exact copy of the supplied journal
version 36. All calculations, formatting and embedded images remain native BPAD.
The imported baseline has not been declared numerically or visually validated.

The workflow supports isolated task copies, bounded whole-component edits,
three-way checks and a single integration path. The current journal stays
available while tasks run. Each candidate is built from the current journal plus
that task's permitted changes. Long tasks cannot silently overwrite newer work.

## Start here

Tell Codex, for example:

> Create a task order to update C006 pier wall and fin calculations. Identify
> dependencies and downstream effects. Plan only.

Or, when ready:

> Plan and execute the requested C006 changes in an isolated task copy, then
> build a candidate for Blockpad review.

Use `prompts/create-task-order.md` for the full planner instructions. T000 records
the bootstrap. T001 relocates only the 31 PDF paths; its candidate is ready for
native review. It makes no engineering changes.

## Layout and ownership

| Location | Role |
| --- | --- |
| `journal/D2_I95_Project_Journal.bpad` | Current project baseline; replaced only through reviewed promotion |
| `journal/References/` | 31 source PDFs; move with the journal |
| `standards/` | Exact local copies of the existing formatting and GetRefs guides |
| `workflow/baseline.json` | Source identity, hashes and import status |
| `workflow/dependencies.json` | Reviewed module dependency declarations; empty initially |
| `workflow/assumptions/`, `workflow/external/` | Non-numerical dependency and analysis-provenance records |
| `workflow/registry/` | Frozen task scopes and input fingerprints |
| `tasks/<ID>/` | Isolated native working copy, task contract, assigned fragments and submission |
| `generated/` | Rebuildable indexes, round trip and review candidates; ignored by Git |
| `workflow/history/`, `workflow/completed/` | Promotion records and evidence; local previous-journal backups |

Git retains source history when you commit. Nothing is committed or pushed by the
helpers. The repository's existing remote is used only when you choose to push.
`.gitattributes` prevents Git from changing BPAD line endings. Large task copies
and generated builds are ignored; contracts, source PDFs and validation records
are tracked. Each assembly saves a bounded `tasks/<ID>/proposal/` change package
for Git. Prior journal backups are local; commit the journal after promotion
to retain its history remotely. Task fragments are disposable local working data.

## Commands

Run from the repository root. These helpers need Python 3.10+ and no additional
packages. This machine already has `.venv\Scripts\python.exe`; use that in place
of `python` if Python is not on your path.

```powershell
.\.venv\Scripts\python.exe tools/bpad_workflow.py inspect
.\.venv\Scripts\python.exe tools/bpad_workflow.py roundtrip --output generated/fresh-roundtrip
.\.venv\Scripts\python.exe tools/bpad_workflow.py prepare T002 --objective "Describe the requested change" --write PierWallFins
.\.venv\Scripts\python.exe tools/bpad_workflow.py check T002
.\.venv\Scripts\python.exe tools/bpad_workflow.py assemble T002 --output generated/T002-review-01
```

`prepare` creates `base.bpad`, `working.bpad`, References, `order.json`,
`submission.json`, and small editable fragments under `components/`. Every task
has a full journal so native scopes and upstream definitions remain available.
Repeat `--write` for multiple permitted components. Exact keys such as
`report:PierWallFins`, `xref:ReferencePDF01` or `resource:Resource32` are supported.

Two authoring paths are available:

- Edit assigned fragments, then run `import-components T002`. It refuses to
  overwrite a working journal that has already been edited. For another fragment
  pass, create a fresh task or continue editing/importing the full working copy.
- Edit a task copy in Blockpad, then run `import-native T002 path/to/saved.bpad`.
  It validates the saved journal before replacing the task working copy. A native
  save may alter caches outside the permitted modules or serialize the whole file
  differently; those changes are rejected. Inspect them and prepare a correctly
  scoped task instead of bypassing the guard. General native-save normalization
  is not implemented in this pilot.

Additional helpers:

```powershell
.\.venv\Scripts\python.exe tools/bpad_workflow.py import-references 'path\to\References'
.\.venv\Scripts\python.exe tools/bpad_workflow.py relocate-references T001
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_bpad_workflow.py -v
```

Reference import checks every expected filename, copies its bytes unchanged and
records provenance. Import before preparing tasks. Changed standards, PDFs,
assumptions, analysis records or dependency declarations invalidate prepared tasks.

After cloning, `restore-task T001` recreates ignored working files from the tracked
proposal and the exact base journal. If the canonical journal has advanced, supply
`--base path/to/historical.bpad` from Git history; its hash must match the original
task. Supporting-file fingerprints must also match. Existing working copies are
never overwritten. Restore is not a rebase: run `check` to detect stale inputs.

## What the checks establish

The extractor uses an XML parser's byte offsets, preserving every untouched byte,
including inline whitespace, embedded resources, formulas and cached displays.
The no-change test extracts all 275 top-level components and reassembles them.
No tree serialization or pretty-print pass touches the journal.

Integration rejects changed task contracts/bases, edits outside scope, conflicting
owned components, changed upstream components, changed supporting files, changed
resource copies, unmet prerequisites, new detected broken native links/images,
duplicate IDs, new stored errors, and removal of simple published names still used
by qualified formulas. It preserves unrelated accepted updates. New modules,
deleted/reordered components and wrapper changes are deliberately unsupported.

The expression index is a partial reference inventory, not a complete Blockpad
language interpreter. Arbitrary symbol/scope resolution, complex function exports,
external library internals and physical engineering assumptions still require
native and engineering review. No-dependency declarations must never be inferred
solely from an empty regex result. Until a complete declaration is reviewed, a
task watches **all other components**. This permits concurrent authoring but may
require refreshing a task after another change is accepted.

For a reviewed declaration, reads are combined with detected dependencies and
followed transitively. Unknown upstream coverage reverts to the broad fallback.
Global resources/styles/includes remain protected inputs. File provenance records
cover assumptions, conventions and external analysis. The initial analysis
register has no verified input/output pairs; every change requires a currency
disposition. Detected downstream impacts are hints, not proof of complete coverage.

## Native review and promotion

Open `generated/<build>/candidate.bpad` in Blockpad with its References folder.
Recalculate and inspect the affected calculations, schematics, links and print
layout. Review inherited errors and analysis provenance. If Blockpad must save
changed content/caches, import that saved copy through the task, rebuild, and
review the resulting exact bytes. Do not edit the candidate behind its report.

The candidate folder has `report.json`, `submission.json` and `review.json`.
Complete review fields only for checks actually performed. Set a separate design
outcome (`passes`, `fails`, or `not_applicable`): coherent calculations can show a
failed design. For external analysis, use `verified_current`,
`excluded_from_accepted_scope` or `not_applicable`, with a substantive disposition.
Record how inherited issues were resolved or excluded; a sentence cannot turn an
unreviewed result into a valid one. Add evidence files inside the candidate folder
and record their relative paths and SHA-256 hashes in `evidence_files`.

```powershell
.\.venv\Scripts\python.exe tools/bpad_workflow.py promote generated/T002-review-01
```

Promotion rechecks the exact candidate, current journal, task inputs, portable
reference files and evidence. It archives the previous journal and review record,
then atomically replaces the canonical BPAD under a single-writer lock. Review
evidence is a recorded human/native attestation, not something the helper can
independently certify. The JSON files protect against workflow mistakes; they are
not tamper-proof signatures against someone editing the registry itself.

After a crash during promotion, compare the canonical journal hash with the
archived `workflow/history/<candidate-hash>/report.json` before doing more work.
The journal replacement is atomic; companion receipt writes are separate.
Do not remove an integration lock until its recorded process has stopped.

## Current bootstrap limits

No engineering inputs or formulas were changed. The 110 stored error entries in
the supplied file remain visible in the index and bootstrap report. The tool does
not evaluate BPAD formulas, run FB-MultiPier, or establish native pagination.
Those gates remain pending. A no-change byte match proves preservation, not that
the source journal was correct. Read `workflow/T000-report.md` for actual checks.

Formatting for new calculations comes from the existing guide, especially
sections 16.5 and 16.9. Reuse small native presentation blocks with fresh names;
the pilot preserves established formatting and does not regenerate whole reports.
