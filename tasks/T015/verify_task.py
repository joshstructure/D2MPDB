"""T015 independent checks on the assembled candidate.

Does not reuse build_components.py: values are re-read from the candidate itself.
Usage: verify_task.py [candidate_folder]   (default generated/T015-review-01)
Writes tasks/T015/independent-checks.json (and a copy in the candidate folder).
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

FOLDER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "generated" / "T015-review-01"
ADDED = ["PileDesignEndBentOne", "PileDesignEndBentTwo", "PileDesignPier"]
FOUR = sorted([f"report:{n}" for n in ADDED] + ["report:PedBridge"])
SUPPORT = {"PileDesignEndBentOne": "End Bent 1", "PileDesignEndBentTwo": "End Bent 2", "PileDesignPier": "Pier"}
DOCUMENT = {"PileDesignEndBentOne": "End Bent 1 Pile Design.bpad", "PileDesignEndBentTwo": "End Bent 2 Pile Design.bpad",
            "PileDesignPier": "Pier Pile Design.bpad"}

results = {}


def record(name, passed, detail):
    results[name] = {"passed": bool(passed), "detail": detail}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def shape(el):
    return (el.tag, sorted(el.attrib.items()), (el.text or "").strip(), [shape(c) for c in el], (el.tail or "").strip())


cand_bytes = (FOLDER / "candidate.bpad").read_bytes()
cand = Journal(cand_bytes)
base = Journal.load(TASK / "base.bpad")
current = Journal.load(ROOT / "journal" / "D2_I95_Project_Journal.bpad")
report = json.loads((FOLDER / "report.json").read_text(encoding="utf-8"))
tree = E.fromstring(cand_bytes)
top = {e.get("name"): e for e in tree if isinstance(e.tag, str) and e.get("name")}
module_names = {n for n, e in top.items() if e.tag in MODULE_TAGS}


def elems(root):
    return root.iter("*")


def defined(root):
    names = set()
    for e in elems(root):
        m = re.match(r"^\s*([^\W\d]\w*)\s*(?:\([^)]*\))?\s*=(?!=)", e.get("formula", ""))
        if m:
            names.add(m[1])
        if e.get("name"):
            names.add(e.get("name"))
    return names


def expression_texts(root):
    for e in elems(root):
        for attr in ("formula", "condition", "valuedef"):
            if e.get(attr):
                yield e.get(attr)
        if e.tag == "expbody" and e.text:
            yield e.text


REF = re.compile(r"(?<![\w.])(" + "|".join(sorted(map(re.escape, module_names), key=len, reverse=True)) + r")\.([^\W\d]\w*)")


def refs_in(root):
    return Counter(m.groups() for text in expression_texts(root) for m in REF.finditer(text))


def get_def(report_name, name):
    """The first defining element of `name` in a report: (formula, cache text or None)."""
    for e in elems(top[report_name]):
        f = e.get("formula", "")
        if re.match(r"^\s*" + re.escape(name) + r"\s*(?:\([^)]*\))?\s*=(?!=)", f):
            cache = e.find("expresult")
            return f, (cache.text if cache is not None else None)
    return None, None


# --- 1. component list -------------------------------------------------------
expected_order = base.order + [f"report:{n}" for n in ADDED]
record("component_list_is_base_plus_three_added_in_order", cand.order == expected_order,
       {"base_components": len(base.order), "candidate_components": len(cand.order), "appended": cand.order[len(base.order):]})

# --- 2. candidate vs current journal: only the four registered components ----
diff = sorted(k for k in cand.order if k not in current.hashes or current.hashes[k] != cand.hashes[k])
record("candidate_differs_from_current_only_in_four_registered", diff == FOUR and cand.shell == current.shell and
       not (set(current.order) - set(cand.order)),
       {"differing": diff, "shell_identical": cand.shell == current.shell,
        "current_matches_task_base": current.sha256 == base.sha256})

# --- 3. report.json ---------------------------------------------------------
record("report_changed_components_exactly_the_four", sorted(report["changed_components"]) == FOUR and
       sorted(report["added_components"]) == sorted(f"report:{n}" for n in ADDED) and not report["deleted_components"]
       and report["candidate_sha256"] == sha(cand_bytes),
       {"changed_components": report["changed_components"], "candidate_sha256": sha(cand_bytes),
        "detected_downstream_impact": report["detected_downstream_impact"]})

# --- 4. structure: issues and stored errors ---------------------------------
new_issues = structural_issues(cand) - structural_issues(current)
err = lambda j, key: Counter("".join(e.itertext()) for e in j.elements[key].iter("error")) if key in j.elements else Counter()
new_errors = {k: dict(err(cand, k) - err(current, k)) for k in FOUR if err(cand, k) - err(current, k)}
record("no_new_structural_issues_or_stored_errors", not new_issues and not new_errors and
       report["candidate_cached_errors"] == sum(e.tag == "error" for e in current.root.iter()),
       {"new_structural_issues": dict(new_issues), "new_stored_errors": new_errors,
        "candidate_cached_errors": report["candidate_cached_errors"]})

# --- 5. every PileDesign*.Name reference resolves in its own report ----------
cache_of_defs = {n: defined(top[n]) for n in module_names}
unresolved, counts, foreign = {}, {}, {}
for n in ADDED:
    refs = refs_in(top[n])
    counts[n] = sum(refs.values())
    foreign[n] = sorted({r for r, _ in refs} - {n})
    bad = sorted(f"{r}.{name}" for (r, name) in refs if r == n and name not in cache_of_defs[r])
    if bad:
        unresolved[n] = bad
record("every_report_name_reference_resolves", not unresolved and all(counts.values()),
       {"references_checked": counts, "unresolved": unresolved})
record("links_and_images_resolve", not new_issues, {"new_unresolved": dict(new_issues)})

# --- 6. the new reports read no other module; no other module reads them -----
readers = {}
for name in module_names - set(ADDED):
    hit = sorted({r for r, _ in refs_in(top[name]) if r in ADDED})
    if hit:
        readers[name] = hit
record("new_reports_read_no_other_module_and_no_module_reads_them", not any(foreign.values()) and not readers,
       {"foreign_reads": foreign, "existing_modules_reading_new_reports": readers})

# --- 7. PedBridge: three links once each, nothing else ----------------------
ped = cand.part("report:PedBridge").decode("utf-8")
base_ped = base.part("report:PedBridge").decode("utf-8")
links = {n: ped.count(f'address="#{n}"') for n in ADDED}
sm = difflib.SequenceMatcher(None, base_ped.splitlines(True), ped.splitlines(True), autojunk=False)
ops = [(t, i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]
positions = [ped.index(f'address="#{n}"') for n in ["CapDesignPier"] + ADDED]
record("pedbridge_three_links_once_each_and_nothing_else", all(c == 1 for c in links.values()) and
       ops == [("insert", 0, 9)] and positions == sorted(positions) and ped.count('address="#CapDesignPier"') == 1,
       {"link_counts": links, "diff_ops": ops, "in_order_after_CapDesignPier": positions == sorted(positions)})

# --- 8. fragments: bytes, committed sheets and verification.json ------------
sys.path.insert(0, str(ROOT))
from pile_design.mathcad import package_revision  # noqa: E402
from pile_design.model import default_case, evaluate  # noqa: E402

verification = {r["report_name"]: r for r in json.loads((ROOT / "pile_bpad" / "verification.json").read_text(encoding="utf-8"))}
revision = package_revision()
info, ok = {}, True
for n in ADDED:
    part = cand.part(f"report:{n}")
    fragment = (ROOT / "pile_bpad" / "fragments" / f"{n}.xml").read_bytes()
    document = (ROOT / "pile_bpad" / DOCUMENT[n]).read_bytes()
    v = verification[n]
    names = defined(top[n])
    info[n] = {"bytes": len(part), "sha256": sha(part), "equals_fragment_file": part == fragment.rstrip(b"\r\n"),
               "document_sha256_equals_verification_json": sha(document) == v["bpad_sha256"],
               "same_structure_as_report_in_committed_sheet": shape(E.fromstring(part)) == shape(E.fromstring(Journal(document).part(f"report:{n}"))),
               "verification_package_revision_is_current": v["package_revision"] == revision,
               "stored_errors": len(list(top[n].iter("error"))), "definitions": len(names),
               "DC_names": sum(1 for x in names if x.startswith("DC_")), "Chk_names": sum(1 for x in names if x.startswith("Chk_"))}
    ok &= all(info[n][k] for k in ("equals_fragment_file", "document_sha256_equals_verification_json",
                                   "same_structure_as_report_in_committed_sheet", "verification_package_revision_is_current"))
    ok &= info[n]["stored_errors"] == 0 and info[n]["DC_names"] > 0 and info[n]["Chk_names"] > 0
record("new_reports_match_fragments_sheets_and_verification_json", ok, info)

# --- 9. Status strings equal the notebook -----------------------------------
status, ok = {}, True
for n in ADDED:
    e = evaluate(default_case(SUPPORT[n]))
    notebook = "✓ All Checks Pass" if (not any("FAIL" in c.status for c in e.checks) and e.max_ratio <= 1.0) else "⊗ There are FAILURES"
    formula, cache = get_def(n, "Status")
    printed = cache.strip().lstrip("=").strip() if cache else None
    status[n] = {"notebook": notebook, "report_cache": printed, "verification_json": verification[n]["status"],
                 "formula": formula, "notebook_max_ratio": e.max_ratio, "notebook_strength_dc": round(e.strength_dc, 6),
                 "notebook_failed_checks": sum("FAIL" in c.status for c in e.checks)}
    ok &= printed == notebook == verification[n]["status"] == "✓ All Checks Pass"
record("status_strings_equal_the_notebook", ok, status)

# --- write ------------------------------------------------------------------
out = {"candidate": str(FOLDER / "candidate.bpad"), "candidate_sha256": sha(cand_bytes), "all_passed": all(r["passed"] for r in results.values()),
       "checks": results}
text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
(TASK / "independent-checks.json").write_text(text, encoding="utf-8")
shutil.copyfile(TASK / "independent-checks.json", FOLDER / "independent-checks.json")
print(json.dumps({"all_passed": out["all_passed"], "candidate_sha256": out["candidate_sha256"],
                  "checks": {k: r["passed"] for k, r in results.items()}}, indent=2))
sys.exit(0 if out["all_passed"] else 1)
