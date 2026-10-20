"""Register the promoted D-064 decision while preserving other source records."""
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
verification = json.loads((TASK / "verification.json").read_text(encoding="utf-8"))
receipt = json.loads((ROOT / "workflow/completed/T020.json").read_text(encoding="utf-8"))
sha = hashlib.sha256((ROOT / "journal/D2_I95_Project_Journal.bpad").read_bytes()).hexdigest()
assert sha == receipt["journal_sha256"] == verification["candidate_sha256"]
for rel, expected in verification["protected_files_sha256"].items():
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected, rel

register = ROOT / "project_current/source_register.csv"
before = register.read_bytes()
rows = list(csv.DictReader(io.StringIO(before.decode("utf-8-sig"))))
row = next(r for r in rows if r["source_id"] == "JOURNAL")
old = row.copy()
assert old["sha256"] == verification["base_sha256"]
note = (
    "D-064 / T020 (20 October 2026): user adopts level tops for the two pier pedestals, "
    "zero longitudinal and transverse slope, based on the conditional T019 check. "
    "Recorded under Bearing Pads / PierLevelSeatOverride. "
    "Notebook, B4 geometry table, CAD and drawings are unchanged and pending coordinated "
    "implementation; no new numeric top elevation is selected. Reconcile a common top "
    "elevation per pedestal and pad/beam interfaces. End bents excluded. "
    "Existing calculation, all cached results and other journal components preserved exactly; "
    "combined shear, uplift/contact, analysis currency/load reconciliation and final details "
    "remain open. No new native recalculation, visual or engineering review. "
    "See tasks/T020/verification.json and workflow/completed/T020.json. Prior calculation basis: "
)
row.update(sha256=sha, registered_on="2026-10-20",
           status="Current - adopted pier override; geometry implementation pending",
           notes=note + old["notes"])
lines = before.decode("utf-8-sig").splitlines(keepends=True)
index = next(i for i, line in enumerate(lines) if line.startswith('"JOURNAL",'))
assert len(next(csv.reader([lines[index]]))) == len(old)
buf = io.StringIO(newline="")
writer = csv.DictWriter(buf, fieldnames=list(old), quoting=csv.QUOTE_ALL,
                        lineterminator="\r\n" if lines[index].endswith("\r\n") else "\n")
writer.writerow(row)
lines[index] = buf.getvalue()
after = "".join(lines).encode("utf-8")
assert [r for r in csv.DictReader(io.StringIO(after.decode())) if r["source_id"] != "JOURNAL"] == [r for r in rows if r["source_id"] != "JOURNAL"]

decisions = ROOT / "project_current/decisions.md"
original = decisions.read_bytes()
assert b"| D-064 |" not in original
dlines = original.decode("utf-8").splitlines(keepends=True)
last = max(i for i, line in enumerate(dlines) if re.match(r"\| D-\d+ \|", line))
nl = "\r\n" if dlines[last].endswith("\r\n") else "\n"
dlines.insert(last + 1,
    "| D-064 | 2026-10-20 | Adopt level pier pedestal tops and record the override in the journal and atlas. | "
    "User direction; two pier pedestals, zero longitudinal and transverse slope, based on the conditional "
    "D-063/T019 rotation and movement check. T020 adds PierLevelSeatOverride under Bearing Pads. "
    "End bents excluded. Notebook, B4 geometry table, CAD and drawings remain unchanged and pending "
    "coordinated implementation; common top elevation per pedestal and pad/beam interfaces still require "
    "reconciliation. No numeric elevation selected by this decision. Existing bearing checks and all "
    "source/load, combined shear, uplift/contact and final-detail limitations remain. All prior journal "
    "content and tracker responses/statuses preserved. Documentary addition: no new native recalculation "
    "or engineering acceptance. See [verification](../tasks/T020/verification.json). |" + nl)
register.write_bytes(after)
decisions.write_bytes("".join(dlines).encode("utf-8"))
evidence = {
    "decision": "D-064", "task": "T020", "date": "2026-10-20",
    "previous_journal_sha256": old["sha256"], "journal_sha256": sha,
    "register_before_sha256": hashlib.sha256(before).hexdigest(),
    "register_after_sha256": hashlib.sha256(after).hexdigest(),
    "other_source_records_unchanged": True,
    "protected_files_sha256": verification["protected_files_sha256"],
    "adoption": note.removesuffix(" Prior calculation basis: "),
}
(TASK / "source-adoption.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"decision": "D-064", "journal_sha256": sha, "geometry_and_tracker_unchanged": True}, indent=2))
