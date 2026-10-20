"""Record this promoted journal revision; preserve every other source and tracker."""
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
tracker = ROOT / "project_current/coherence/Coherence_Tracker.xlsx"
tracker_sha = hashlib.sha256(tracker.read_bytes()).hexdigest()
assert tracker_sha == "58210442277fc31e92a18ab60d375990c631cd951318a93df53b3c8dfcc10aad"
receipt = json.loads((ROOT / "workflow/completed/T019.json").read_text())
journal_sha = hashlib.sha256((ROOT / "journal/D2_I95_Project_Journal.bpad").read_bytes()).hexdigest()
assert journal_sha == receipt["journal_sha256"]
register = ROOT / "project_current/source_register.csv"
before = register.read_bytes()
rows = list(csv.DictReader(io.StringIO(before.decode("utf-8-sig"))))
row = next(r for r in rows if r["source_id"] == "JOURNAL")
assert row["sha256"] == "d3aa9a62939cd82634196c97361ea85d2b8abf2d4fce1c72ab0b86a2510c9b50"
old = row.copy()
row.update(
    sha256=journal_sha,
    registered_on="2026-10-20",
    status="Current - bounded check; engineering review retained",
    notes=(
        "D-063. T019 adds the conditional level pier bearing-seat check under BearingDesign / Bearing Pads. "
        "Native Blockpad recalculation and independent arithmetic agree: static 0.009624091 rad <= 0.0125 rad, "
        "cyclic 0.002470058 rad <= 0.004 rad, conservative longitudinal thermal/creep movement 0.983620672 in <= 1 in. "
        "Uses selected MCAD-S1/S2 saved end slopes and shortenings, live profile/pad/thermal inputs; "
        "source solver currency/load reconciliation, combined lateral shear, uplift/contact and final details remain open. "
        "No pedestal geometry or end-bent approval. COH-017/018 and all workbook statuses/responses are preserved. "
        "Inherits accepted T018 native full-journal recalculation (542fba20): it exposed FBMPPier.NB_checkUplift "
        "and FBMPEndBent.EB_CheckGravity failures; those and all other existing results remain byte exact. "
        "T018 is a native cache refresh, not external-analysis rerun or engineering acceptance. "
        "Exact T019 evidence: tasks/T019/native-verification.json, independent-check.json and workflow/completed/T019.json. "
        "Prior selected revision T017 and its source/authority history: D-058, workflow/completed/T017.json. "
        "Only BearingDesign changes from T018; prior journal resources and all other components are preserved."
    ),
)
row["depends_on"] = old["depends_on"] + ";MCAD-S1;MCAD-S2"
# Change just this one CSV record's bytes, leaving other records and formatting exact.
lines = before.decode("utf-8-sig").splitlines(keepends=True)
start = next(i for i, line in enumerate(lines) if line.startswith('"JOURNAL",'))
assert start == 1  # Existing register has one physical line per CSV record.
assert len(next(csv.reader([lines[start]]))) == len(old)
buf = io.StringIO(newline="")
writer = csv.DictWriter(buf, fieldnames=list(old), quoting=csv.QUOTE_ALL, lineterminator="\r\n" if lines[start].endswith("\r\n") else "\n")
writer.writerow(row)
lines[start] = buf.getvalue()
after = "".join(lines).encode("utf-8")
reparsed = list(csv.DictReader(io.StringIO(after.decode())))
assert [r for r in reparsed if r["source_id"] != "JOURNAL"] == [r for r in rows if r["source_id"] != "JOURNAL"]

decisions = ROOT / "project_current/decisions.md"
dec_before = decisions.read_bytes()
assert not re.search(rb"\| D-063 \|", dec_before)
lines_d = dec_before.decode("utf-8").splitlines(keepends=True)
last = max(i for i, s in enumerate(lines_d) if re.match(r"\| D-\d+ \|", s))
nl = "\r\n" if lines_d[last].endswith("\r\n") else "\n"
new = ("| D-063 | 2026-10-20 | Add the requested level pier bearing-seat check to the journal and record its inherited T018 recalculation. | "
       "User requested the FDOT check under Bearings and Support Details / Bearing Pads. T019 changes only BearingDesign; "
       "native Blockpad results match independent arithmetic. Static 0.009624091 rad and cyclic 0.002470058 rad are below "
       "SPI 400-510 limits; the conservative longitudinal thermal/creep bound is 0.983620672 in. "
       "Conditional on saved selected beam results and zero transverse tilt; combined lateral shear, uplift/contact, "
       "source currency/load reconciliation and final details remain open. No geometry change or end-bent approval. "
       "T018 native cache refresh and its exposed consistency failures are preserved. All tracker responses/statuses remain unchanged. "
       "See [verification](../tasks/T019/native-verification.json) and [calculation evidence](../tasks/T019/independent-check.json). |" + nl)
lines_d.insert(last + 1, new)
evidence = {
    "decision": "D-063", "date": "2026-10-20", "task": "T019",
    "previous_registered_journal_sha256": old["sha256"],
    "immediate_base_journal_sha256": receipt["previous_sha256"],
    "current_journal_sha256": journal_sha,
    "register_before_sha256": hashlib.sha256(before).hexdigest(),
    "register_after_sha256": hashlib.sha256(after).hexdigest(),
    "tracker_sha256_unchanged": tracker_sha,
    "tracker_dispositions_read": {"COH-015": "Closed / Added", "COH-016": "Closed / Added",
                                  "COH-017": "Open; review L_Beam assumptions", "COH-018": "Open"},
    "other_source_records_unchanged": True,
    "adoption_scope": row["notes"],
}
register.write_bytes(after)
decisions.write_bytes("".join(lines_d).encode("utf-8"))
assert hashlib.sha256(tracker.read_bytes()).hexdigest() == tracker_sha
(TASK / "source-adoption.json").write_text(json.dumps(evidence, indent=2) + "\n")
print(json.dumps({"decision": "D-063", "journal_sha256": journal_sha, "tracker_unchanged": True}, indent=2))
