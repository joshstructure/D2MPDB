"""T017 independent checks on the assembled candidate.

Does not reuse build_components.py: values are re-read from the candidate itself and from the project record.
Usage: verify_task.py [candidate_folder]   (default generated/T017-backwall-01)
Writes tasks/T017/independent-checks.json (and a copy in the candidate folder).
"""
import difflib
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal, MODULE_TAGS, structural_issues  # noqa: E402

FOLDER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "generated" / "T017-backwall-01"
ADDED = "EndBentBackwallDesign"
WRITES = ["BridgeGeometry_2Beam", "DecisionLog", "FoundationModeling", "PedBridge"]
FIVE = sorted([f"report:{ADDED}"] + [f"report:{n}" for n in WRITES])
EDITION = ROOT / "end_bent_walls" / "bpad" / "journal"
results = {}


def record(name, passed, detail):
    results[name] = {"passed": bool(passed), "detail": detail}


def sha(data):
    return hashlib.sha256(data).hexdigest()


cand_bytes = (FOLDER / "candidate.bpad").read_bytes()
cand = Journal(cand_bytes)
base = Journal.load(TASK / "base.bpad")
current = Journal.load(ROOT / "journal" / "D2_I95_Project_Journal.bpad")
report = json.loads((FOLDER / "report.json").read_text(encoding="utf-8"))
tree = E.fromstring(cand_bytes)
top = {e.get("name"): e for e in tree if isinstance(e.tag, str) and e.get("name")}
module_names = {n for n, e in top.items() if e.tag in MODULE_TAGS}


def defined(root):
    names = set()
    for e in root.iter():
        m = re.match(r"^\s*([^\W\d]\w*)\s*(?:\([^)]*\))?\s*=(?!=)", e.get("formula", ""))
        if m:
            names.add(m[1])
        if e.get("name"):
            names.add(e.get("name"))
    return names


def expression_texts(root):
    for e in root.iter():
        for attr in ("formula", "condition", "valuedef"):
            if e.get(attr):
                yield e.get(attr)
        if e.tag == "expbody" and e.text:
            yield e.text


REF = re.compile(r"(?<![\w.])(" + "|".join(sorted(map(re.escape, module_names), key=len, reverse=True)) + r")\.([^\W\d]\w*)")


def refs_in(root):
    return Counter(m.groups() for text in expression_texts(root) for m in REF.finditer(text))


def get_def(report_name, name):
    for e in top[report_name].iter():
        f = e.get("formula", "")
        if re.match(r"^\s*" + re.escape(name) + r"\s*(?:\([^)]*\))?\s*=(?!=)", f):
            cache = e.find("expresult")
            return f, (cache.text if cache is not None else None)
    return None, None


# --- 1. component list: base plus the added report, in order ----------------
record("component_list_is_base_plus_added_report", cand.order == base.order + [f"report:{ADDED}"],
       {"base_components": len(base.order), "candidate_components": len(cand.order), "appended": cand.order[len(base.order):]})

# --- 2. candidate vs current journal: only the five registered components ----
diff = sorted(k for k in cand.order if k not in current.hashes or current.hashes[k] != cand.hashes[k])
record("candidate_differs_from_current_only_in_five_registered", diff == FIVE and cand.shell == current.shell and not (set(current.order) - set(cand.order)),
       {"differing": diff, "shell_identical": cand.shell == current.shell, "current_matches_task_base": current.sha256 == base.sha256})

# --- 3. report.json ---------------------------------------------------------
record("report_changed_components_exactly_the_five", sorted(report["changed_components"]) == FIVE and report["added_components"] == [f"report:{ADDED}"]
       and not report["deleted_components"] and report["candidate_sha256"] == sha(cand_bytes),
       {"changed_components": report["changed_components"], "candidate_sha256": sha(cand_bytes), "detected_downstream_impact": report["detected_downstream_impact"]})

# --- 4. structure: issues and stored errors ---------------------------------
new_issues = structural_issues(cand) - structural_issues(current)
err = lambda j, key: Counter("".join(e.itertext()) for e in j.elements[key].iter("error")) if key in j.elements else Counter()
new_errors = {k: dict(err(cand, k) - err(current, k)) for k in FIVE if err(cand, k) - err(current, k)}
record("no_new_structural_issues_or_stored_errors", not new_issues and not new_errors and
       report["candidate_cached_errors"] == sum(e.tag == "error" for e in current.root.iter()),
       {"new_structural_issues": dict(new_issues), "new_stored_errors": new_errors, "candidate_cached_errors": report["candidate_cached_errors"]})

# --- 5. every qualified reference of the new report resolves ----------------
defs_of = {n: defined(top[n]) for n in module_names}
refs = refs_in(top[ADDED])
unresolved = sorted(f"{r}.{name}" for (r, name) in refs if name not in defs_of.get(r, set()))
owners = sorted({r for r, _ in refs})
record("every_reference_of_the_new_report_resolves", not unresolved and owners == sorted([ADDED, "BridgeGeometry_2Beam", "Materials", "ProjectInfo"]),
       {"references_checked": sum(refs.values()), "owners": owners, "unresolved": unresolved,
        "foreign_names": sorted({f"{r}.{n}" for (r, n) in refs if r != ADDED})})
record("links_and_images_resolve", not new_issues, {"new_unresolved": dict(new_issues)})

# --- 6. the journal values the report reads equal the coherence rows and the case -------------
coherence = json.loads((EDITION / "coherence.json").read_text(encoding="utf-8"))[ADDED]
case = json.loads((ROOT / "project_current" / "cap_design" / "backwall" / "selected_case.json").read_text(encoding="utf-8-sig"))
checks, ok = [], True
for row in coherence:
    owner, _, name = row["owner"].partition(".")
    formula, _ = get_def(owner, name)
    present = formula is not None
    ok &= present
    checks.append({"input": row["input"], "owner": row["owner"], "status": row["status"], "defined_in_candidate": present,
                   "journal_value": row["journal_value"], "case_value": row["case_value"]})
# the case values of the reference rows equal the registered selected case (the sheet shows each input in the case unit)
case_inputs = case["inputs"]
mismatch = []
for row in coherence:
    if row["status"] != "reference":
        continue
    key = row["input"].replace("φ", "phi").replace("γ", "gamma")
    if key in case_inputs and abs(float(case_inputs[key]) - row["case_value"]) > 1e-9 * max(abs(row["case_value"]), 1e-12):
        mismatch.append({"input": key, "case": case_inputs[key], "row": row["case_value"]})
record("coherence_rows_match_the_candidate_and_the_selected_case", ok and not mismatch and len(coherence) >= 22,
       {"rows": len(coherence), "references": sum(r["status"] == "reference" for r in coherence), "mismatch": mismatch, "checks": checks})

# --- 7. PedBridge: one link, the two paragraphs, nothing else ----------------
ped = cand.part("report:PedBridge").decode("utf-8")
base_ped = base.part("report:PedBridge").decode("utf-8")
sm = difflib.SequenceMatcher(None, base_ped.splitlines(True), ped.splitlines(True), autojunk=False)
ops = [(t, i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]
positions = [ped.index(f'address="#{n}"') for n in ["PileDesignPier", ADDED]]
record("pedbridge_one_link_after_pile_pier_and_two_paragraph_edits", ped.count(f'address="#{ADDED}"') == 1 and positions == sorted(positions)
       and "T014 to T017" in ped and "is separate and predates D-049 and D-053" not in ped and "end-bent backwall report added (T017)" in ped
       and len(ops) == 3 and sorted(t for t, _, _ in ops) == ["insert", "insert", "replace"],
       {"link_count": ped.count(f'address="#{ADDED}"'), "diff_ops": ops})

# --- 8. the other text edits ------------------------------------------------
bg = cand.part("report:BridgeGeometry_2Beam").decode("utf-8")
fm = cand.part("report:FoundationModeling").decode("utf-8")
dl = cand.part("report:DecisionLog").decode("utf-8")
record("geometry_foundation_and_decisionlog_name_the_report",
       bg.count(ADDED) == 1 and "16 October 2026 backwall report, D-037" not in bg
       and fm.count(ADDED) == 1 and "is not in the journal" not in fm
       and dl.count('name="CoherenceDecision20261019c"') == 1 and dl.count(ADDED) >= 1 and "D-057" in dl,
       {"geometry_mentions": bg.count(ADDED), "foundation_mentions": fm.count(ADDED), "decisionlog_entry": dl.count('name="CoherenceDecision20261019c"')})
stale = {n: [m.start() for m in re.finditer(r"is not in the journal|is separate and predates D-049", cand.part(f"report:{n}").decode("utf-8"))]
         for n in ["PedBridge", "BridgeGeometry_2Beam", "FoundationModeling"]}
record("no_sentence_says_the_backwall_report_is_outside_the_journal", not any(stale.values()), stale)

# --- 9. fragment: bytes, committed edition and verification.json ------------
sys.path.insert(0, str(ROOT))
from scripts.build_backwall_mathcad import notebook_revision  # noqa: E402
from end_bent_walls.model import evaluate  # noqa: E402

verification = json.loads((EDITION / "verification.json").read_text(encoding="utf-8"))[0]
part = cand.part(f"report:{ADDED}")
fragment = (EDITION / f"{ADDED}.xml").read_bytes()
names = defined(top[ADDED])
info = {"bytes": len(part), "sha256": sha(part), "equals_fragment_file": part == fragment.rstrip(b"\r\n"),
        "fragment_sha256_equals_verification_json": sha(part) == verification["fragment_sha256"],
        "verification_package_revision_is_current": verification["package_revision"] == notebook_revision(),
        "stored_errors": len(list(top[ADDED].iter("error"))), "definitions": len(names),
        "DC_names": sum(1 for x in names if x.startswith("DC_")), "Chk_names": sum(1 for x in names if x.startswith("Chk_")),
        "journal_references": verification["journal_references"], "literals_kept": verification["literals_kept"],
        "context_references": verification["context_references"]}
record("new_report_matches_fragment_and_verification_json", all(info[k] for k in ("equals_fragment_file", "fragment_sha256_equals_verification_json",
       "verification_package_revision_is_current")) and info["stored_errors"] == 0 and info["DC_names"] > 0 and info["Chk_names"] > 0, info)

# --- 10. Status equals the notebook; the stamp is live ----------------------
e = evaluate()
notebook = "✓ All Checks Pass" if not any("FAIL" in c.status for c in e.checks) else "⊗ There are FAILURES"
formula, cache = get_def(ADDED, "Status")
printed = cache.strip().lstrip("=").strip() if cache else None
stamp = next((t for t in top[ADDED].iter("table") if t.get("name") == "ProjectStamp"), None)
stamp_cells = [c.get("formula") for c in stamp.iter("c") if c.get("formula")] if stamp is not None else []
record("status_equals_the_notebook_and_the_stamp_is_live", printed == notebook == verification["status"] == "✓ All Checks Pass"
       and len(stamp_cells) == 8 and all(f.startswith("ProjectInfo.") for f in stamp_cells),
       {"notebook": notebook, "report_cache": printed, "verification_json": verification["status"], "formula": formula, "stamp_cells": stamp_cells,
        "notebook_failed_checks": sum("FAIL" in c.status for c in e.checks), "notebook_pending_checks": sum("PENDING" in c.status for c in e.checks)})

# --- write ------------------------------------------------------------------
out = {"candidate": str(FOLDER / "candidate.bpad"), "candidate_sha256": sha(cand_bytes), "all_passed": all(r["passed"] for r in results.values()),
       "checks": results}
text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
(TASK / "independent-checks.json").write_text(text, encoding="utf-8")
shutil.copyfile(TASK / "independent-checks.json", FOLDER / "independent-checks.json")
print(json.dumps({"all_passed": out["all_passed"], "candidate_sha256": out["candidate_sha256"],
                  "checks": {k: r["passed"] for k, r in results.items()}}, indent=2))
sys.exit(0 if out["all_passed"] else 1)
