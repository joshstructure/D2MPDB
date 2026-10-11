# 10 October 2026 cap source update and coherence review

The two user-supplied HTML reports are selected as current. Their bytes are
unchanged, and their embedded saved cases were extracted without changing values.
Prior reports, prior XML and existing evidence remain historical. Machine-readable
identities, prior/current register rows, input changes, geometry and quantities
are in [source_update.json](source_update.json). Complete reported check inventories
are in [pier-report-checks.csv](pier-report-checks.csv) and
[eb-report-checks.csv](eb-report-checks.csv).

## Report results

| Snapshot | Check rows | PASS | Pending entries | FAIL entries | Gross steel | Gross cap concrete |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pier, generated 10 October 2026 at 7:49:35 p.m. EDT | 297 | 219 | 67 | 2 | 1260.94 lb | 230 ft3 |
| End Bent 1, generated 10 October 2026 at 8:34:23 p.m. EDT | 229 | 168 | 50 | 2 | 907.865 lb | 185.5 ft3 |

Each inventory also has seven NOT REQUIRED and two source-layout/section entries.
Counts above were reconciled to each report's result summary. Each report has
one specific failed check, **End U grid - pile envelope clearance**, and a second
FAIL entry for the aggregate actual-cage summary. The displayed value 2 is a
failure flag, not a physical utilization ratio. COH-019 and COH-020 track the
distinct pier and end-bent detailing findings. The cap code's `end_grid.checks`
uses the flag for detected pile conflicts; no capacity recalculation was performed.

The actual longitudinal-tension entries remain PENDING. Pier N/P/B ratios are
0.946947 / 0.776624 / 0.863733, and end-bent ratios are 0.758624 / 0.399353 /
0.393185. Low ratios do not establish the unresolved developed-steel or load-path
prerequisites. Both reports still print Service III as pending; the recorded
D-007 not-applicable disposition is preserved rather than reopening that design
question or editing the source HTML. The gross steel values exclude fabrication
allowances listed in the reports.

## Source and geometry findings

- `Pier_Fixed.XML` was located locally and copied byte-for-byte. Its SHA-256 is
  exactly the new pier report's analysis fingerprint. Its bearing node Y offsets
  are -10.50 in for 181/182 and +10.50 in for 183/184. This closes the earlier
  0.36-in coordinate discrepancy (COH-001); full loading/convergence stays open.
- The new End Bent 1 report requires a different XML fingerprint. The available
  same-named file matches the superseded report only. COH-013 remains awaiting
  source. No current raw end-bent XML was fabricated from embedded audit data.
- Selected geometry agrees with the existing notebook: pier 230 x 48 x 36 in,
  four 20-in piles at 60-in spacing; end bent 212 x 42 x 36 in, four 18-in piles
  at 54-in spacing. Width, depth, count, size, spacing, embedment and length are
  checked by the existing coherence command. This does not cover all elevations,
  loading assumptions or boundary conditions.
- Reinforcement/settings and demands changed. Examples: pier additional span
  bars changed from #6 to #5, and actual transverse runs changed from #6 at 9 in
  to #5 at 6 in; end-bent actual runs now use #5 at 9 in. Both include trial
  50-degree U-hook rotations and enabled end-face grids. The report cases
  retain their actual run schedules, separate from legacy nominal inputs.

## Accepted journal and tracker reconciliation

The source register was still tied to T005 while the repository already contains
accepted T006. Current journal identity and all 14 receipt evidence files were
verified against `workflow/accepted.json`. The expected journal fingerprint was
updated only after that documented disposition. This is reliance on the existing
acceptance and review evidence, not a new native review.

COH-006 (historical-sketch labels) and COH-009 (three reference links) are closed
using accepted T006 evidence. COH-005 records partial resolution of wind width
while retaining wall/fin and current model-load review. Previously blank response
cells received the exact archived T006 human responses. Existing nonblank
responses were preserved. COH-007 and COH-008 are Deferred per those responses.

The tracker now has 22 stable IDs: 19 outstanding (13 Open, three Awaiting source,
three Deferred) and three Closed. COH-019 through COH-022 are new. The workbook
remains the authoritative issue log; generated CSV/Markdown are views.

## Remaining limitations and downstream work

CAP-TOOL differs from the registered revision on GitHub and in the local working
copy. The expected hash is deliberately retained; COH-021 requires identification
and review of the report-generating tool revision. The published machine check
is run against the committed repository files, excluding unrelated local code
edits. The local tool hash is separately recorded in source_update.json.

T006's journal source notes still point to the prior pier snapshot. COH-022
requires a separately bounded journal-reference update. C005, journal bytes,
native analysis files, notebooks and unrelated code were not edited by this task.
Mathcad companion data, PSBeam run packages, remaining end-bent bounding evidence,
full model-load/convergence checks and pending engineering reviews remain open.

No native application was rerun and no structural adequacy approval is implied.
The existing command's nonzero result is retained when unresolved sources or
changed fingerprints remain. See [latest review](../../latest_review.md).
