# T001 — Portable reference paths

Objective: make the supplied journal's existing 31 PDF references portable using
the exact reference set the user confirmed from version 30.

Permitted changes: only `path` attributes in the 31 document-level `xref`
components listed in order.json. Write them as `References/<existing filename>`.

Read dependencies: all other 244 top-level components, both standing guides,
all reference PDFs, dependency declarations and the assumptions/analysis registers.
Their fingerprints are frozen in order.json and the workflow registry.

Exclusions: no formulas, cached values, published variables, scopes, narrative,
report layouts, resource bytes, code excerpts or engineering assumptions change.
The inherited citation-link and cached-error issues are recorded separately.

Output contract: one working BPAD plus an adjacent References folder. Existing
reference names, source filenames and PDF content remain unchanged. No new
engineering outputs or assumptions are introduced.

Prerequisites: the user has confirmed the PDF set. No calculation task is needed.
Native PDF display, navigation and print review remain acceptance gates.

Checks completed: baseline preservation; all 31 PDF filenames found; source and
copied PDF hashes match; exactly 31 xref components changed; all other components
remain byte-identical; every candidate PDF path is relative and resolves locally.

Candidate: `generated/T001-portable-references-final/candidate.bpad`.
Status: ready for native Blockpad review; not promoted. The canonical journal
remains the exact user-supplied version 36 file.
