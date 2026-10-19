# Refresh and publish the design atlas

This is the fixed handoff for any agent working with the D2 sources. The root
AGENTS.md makes it a completion requirement after source changes. A local
scheduled follow-up in the atlas chat provides a fallback for edits made outside
an agent session. This static site cannot watch the computer from the browser.

## Deterministic decision

From the repository root, use its virtual-environment Python:

```powershell
.venv\Scripts\python.exe -m design_atlas.refresh status
.venv\Scripts\python.exe -m design_atlas.refresh prepare
```

`current` requires no publication. `ready_to_publish` gives a validated candidate
under `design_atlas/.refresh/`. Repeating prepare on the same inputs reuses its
exact bytes, including its capture time. `deployment_pending` means reconcile
the stored deployment before starting another. A failed command is never a
successful refresh; keep the last successful publication.

`publication_in_progress` protects a staged candidate while its agent is using
Sites. Do not prepare or stage another candidate over it. If the original run
was interrupted, read pending.json's staged checkout and artifacts, open that
checkout with the Sites helper, reconcile versions/deployments for its pushed
commit, then resume steps 3–5 below with the same candidate. Never assume a
missing local deployment ID proves publication did not start. The guard persists
across process crashes; a later source save waits until this publication resolves.

The inventory hashes the current register and every path it selects (including
absent files), coherence workbook, explicitly selected generated Mathcad files,
manual links, and parser/UI code. It detects additions, removals and byte changes.
It excludes generated output, publication receipts, Git HEAD and unrelated files.
It never chooses a file because its filename or modification time looks newer.
Unregistered new sources need explicit selection or a documented adapter change.

The journal adapter discovers named current calculation reports and saved
spreadsheet cells within the already registered journal file. New modules in
that file are included automatically on its next hash change. Formula parsing,
literal extraction, reference resolution and exact source locations are fixed
code; no AI mapping or native recalculation runs during refresh. Archived
modules, ambiguous definitions and unexpanded ranges are not silently adopted.

Preparation verifies all evidence paths are watched, hashes inputs before and
after ingestion, validates source IDs and origins, checks JavaScript, and tests
all layouts against the candidate graph. A changing source aborts preparation;
retry after the source-writing task finishes. Missing optional evidence and
engineering disagreements stay visible; malformed required input fails closed.
No native calculation or engineering approval is implied.

## Publish the exact prepared candidate

Use the installed Sites skill and its supported source helper. Preserve the
Site ID and audience from `design_atlas/site.json`. Do not create a new Site.
The current source checkout on this computer is
`C:/Users/joshs/Desktop/D2 MPDB/outputs/pier-cap-atlas-site`; open it with the Sites
helper before changing it. If unavailable, open a clean checkout using the same
Site identity. Fetch fresh credentials with the native tool, retain in memory
and pass only through the helper's hidden stdin. Never save credentials.

1. Run `get_site` and `create_source_repository_write_credential`; verify owner
   access and preserve the existing audience. Open the source helper without
   `archivePath` and retain its full returned opening object.
2. Run the fixed staging command against that opened checkout:

   ```powershell
   .venv\Scripts\python.exe -m design_atlas.refresh stage --checkout 'C:/Users/joshs/Desktop/D2 MPDB/outputs/pier-cap-atlas-site'
   ```

   It refuses a wrong Site or changed candidate, copies the six verified assets,
   verifies their hashes, preserves exact bytes in Git using a scoped
   `.gitattributes` rule, and updates the local viewer. Do not edit generated
   values or assets afterward. Add this workflow and site.json to the hosting
   source checkout as maintenance context, outside dist/.
3. Run the Sites source helper with the opening object, credential,
   `commands: []`, and an absolute archive path. Use its verified pushed commit
   and archive with `save_version_and_deploy_private` for the owner-private Site.
   If the Windows portable helper pushes successfully but packaging cannot start,
   read the Sites troubleshooting guidance, reopen the helper to obtain the
   verified pushed commit, and use the documented remote-build fallback. Do not
   invent endpoints or bypass authenticated tools. Respect any changed audience.
4. Save only the structured deployment response (no access tokens) to
   `design_atlas/.refresh/deployment-result.json`, then record it immediately:

   ```powershell
   .venv\Scripts\python.exe -m design_atlas.refresh record-deployment --checkout 'C:/Users/joshs/Desktop/D2 MPDB/outputs/pier-cap-atlas-site' --commit '<returned full source commit>' --result design_atlas/.refresh/deployment-result.json
   ```

   This checks both working files and committed Git blobs against the candidate.
   If publication's outcome was unknown before it could be recorded, inspect
   Sites versions/deployments for that exact pushed commit before retrying.
5. Poll the existing deployment only while pending/building/publishing. Save its
   terminal structured response in the same result file and run:

   ```powershell
   .venv\Scripts\python.exe -m design_atlas.refresh finish --result design_atlas/.refresh/deployment-result.json
   ```

   Only a matching successful deployment advances `design_atlas/publication.json`.
   Failed deployments leave the last successful receipt intact and allow retry.
   If sources changed while publishing, finish records what actually went live
   and returns `refresh_required`; repeat the workflow for the newer sources.
6. Retain the updated publication receipt with the completed task's files. This
   refresh does not authorize unrelated commits, resets, or pushes. If GitHub
   delivery is blocked, report it separately from verified Sites publication.

## Scheduled fallback

Run status first, without a build or publication when current. Use the same
prepare/stage/publish/finish path after changes. Do not broaden a routine refresh
into source adoption, repairs to engineering data, or new parameter mappings.
Keep the computer on and the desktop app running for local scheduled checks.
Report a meaningful published change or actionable failure; stay quiet when
nothing changed. Agent-driven source edits should refresh immediately at task
completion rather than waiting for the next scheduled check.

## Verification after workflow changes

```powershell
.venv\Scripts\python.exe -m unittest tests.test_atlas_refresh tests.test_design_atlas tests.test_end_bent_atlas tests.test_journal_calcs -v
```

The refresh state lock is held during each local operation and releases on a
crash. Pending deployment IDs survive interruption. The published receipt is
tracked; candidates and temporary tool responses are ignored. No automatic
cleanup removes evidence needed to reconcile an interrupted publication.
