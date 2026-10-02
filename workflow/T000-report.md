# T000 — Bootstrap validation

The first working journal workflow is installed in `C:\github\D2MPDB`.
The supplied version 36 journal is preserved exactly. No engineering values,
equations, assumptions, module scopes or established formatting were changed.

## Results

| Check | Result |
| --- | --- |
| Original source vs canonical imported journal | Byte-identical |
| Extract/rebuild of every top-level component | Byte-identical; 275 components |
| Native report/spreadsheet inventory | 36 modules |
| Formula attributes retained | 4,497 |
| Embedded resource components retained | 184 |
| External reference PDFs copied | 31; user-confirmed version 30 set |
| Portable-reference candidate | All 31 relative paths resolve |
| Changes in portable candidate | Exactly 31 xref components; everything else byte-identical |
| Workflow tests | 34 passed |
| Blockpad recalculation and native rendering | Not performed |
| Engineering review and FB-MultiPier provenance | Not performed |
| Candidate promotion, Git commit, remote push | Not performed |

The behavioral tests exercise independent tasks without lost updates, stale
upstream rejection, same-component conflicts, unauthorized edits, tampered bases
and task orders, changed standards/references/analysis records, broken links,
removed published names, new native errors, prerequisites, promotion evidence,
missing PDFs, exact candidate identity, and recovery from tracked proposals.
Independent-task tests use explicit dependency declarations in synthetic fixtures;
they do not certify independence of the project's engineering modules.

The real journal's round trip checks all original bytes, including caches and
layout data. That proves preservation, not that the original calculations pass.

## Inherited issues

There are 110 stored error entries: 106 in `FeetintoDecimalFeet` and four in
`FBMPMinTip`. These are cached source-file entries; they have not been reevaluated.

The structural inventory also found three inherited citation-link occurrences
in `LoadCombinations`: two to
`#CodeReferences.CodePage42;paragraphcoderef42` and one to
`#CodeReferences.CodePage14;paragraphcoderef14`. That old report name is absent.
No replacement destination was guessed.

The original 31 PDF paths pointed into a missing Downloads/References folder.
The user confirmed the folder in `Downloads/Old/D2_I95 (30)/References` is the
correct source set. T001 changes only those paths in a separate candidate.

## Files to use

- `journal/D2_I95_Project_Journal.bpad`: unchanged imported baseline.
- `generated/T001-portable-references-final/candidate.bpad`: portable working
  journal to open in Blockpad; keep its References folder beside it.
- `tasks/T001/order.json` and `tasks/T001/proposal/`: frozen task scope and a
  compact change package that can be retained in Git.
- `workflow/README.md`: everyday workflow and command reference.
- `prompts/create-task-order.md`: reusable task-generation prompt.
- `workflow/T000-validation.json`: hashes and detailed verification evidence.
- `workflow/T000-tests.txt`: actual test output.

The next gate for T001 is native review. A future engineering request can already
be planned and developed in a separate task folder. Because reviewed project
dependency declarations have not yet been established, new tasks conservatively
watch the entire journal until the relevant dependency review is completed.

## Identity

Imported journal and no-change rebuild SHA-256:

`5611bee7a1b517f798521029bb9965f3c756941e564280fd8a37d09f81b7dfcd`

Portable reference candidate SHA-256:

`33050217f4160823ad7e5aa2a49d848a1d1e4f423d803eba449c70e820c0e93b`
