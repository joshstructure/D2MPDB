"""T012 independent checks on the assembled candidate.

Does not reuse build_components.py: values are re-read from the candidate itself.
Usage: verify_task.py [candidate_folder]   (default generated/T012-cap-journal-01)
Writes tasks/T012/independent-checks.json (and a copy in the candidate folder).
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

FOLDER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "generated" / "T012-cap-journal-01"
ADDED = ["CapDesignBasis", "CapDesignEndBentOne", "CapDesignEndBentTwo", "CapDesignPier"]
SIX = sorted(f"report:{n}" for n in ADDED) + ["report:FBMPEndBent", "report:PedBridge"]
SEC = "EBCurrentDesignRecord"
OWNER = "CapDesignEndBentOne"
DECLARED_READS = {
    "CapDesignBasis": set(),
    "CapDesignEndBentOne": {"BridgeGeometry_2Beam", "FBMPEndBent", "CapDesignBasis"},
    "CapDesignEndBentTwo": {"BridgeGeometry_2Beam", "FBMPEndBent", "CapDesignBasis"},
    "CapDesignPier": {"BridgeGeometry_2Beam", "PierCapDesign", "CapDesignBasis"},
}

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
            return f, (cache.text if cache is not None else None), e
    return None, None, None


NUM = re.compile(r"(-?\d+(?:\.\d+)?)\s*(in\^2|ft|in|ksi)?")


def to_number(text):
    """Journal literal or cache text to a number (ft+in summed to inches)."""
    t = re.sub(r"\s+to\s+.*$", "", text.strip().lstrip("=").strip())
    assert re.fullmatch(r"(?:\s*-?\d+(?:\.\d+)?\s*(?:ft|in\^2|in|ksi)?)+", t), f"cannot parse {text!r}"
    total = 0.0
    for num, unit in NUM.findall(t):
        total += float(num) * (12.0 if unit == "ft" else 1.0)
    return total


def value_of(report_name, name):
    formula, cache, _ = get_def(report_name, name)
    assert formula is not None, f"{report_name}.{name} has no definition"
    if cache is not None:
        return to_number(cache)
    return to_number(formula.split("=", 1)[1])


# --- 1. component list -------------------------------------------------------
expected_order = base.order + [f"report:{n}" for n in ADDED]
record("component_list_is_base_plus_four_added_in_order", cand.order == expected_order,
       {"base_components": len(base.order), "candidate_components": len(cand.order), "appended": cand.order[len(base.order):]})

# --- 2. candidate vs current journal: only the six registered components ----
diff = sorted(k for k in cand.order if k not in current.hashes or current.hashes[k] != cand.hashes[k])
record("candidate_differs_from_current_only_in_six_registered", diff == sorted(SIX) and cand.shell == current.shell and
       not (set(current.order) - set(cand.order)),
       {"differing": diff, "shell_identical": cand.shell == current.shell,
        "current_matches_task_base": current.sha256 == base.sha256})

# --- 3. report.json ---------------------------------------------------------
record("report_changed_components_exactly_the_six", sorted(report["changed_components"]) == sorted(SIX) and
       len(report["changed_components"]) == 6 and sorted(report["added_components"]) == sorted(f"report:{n}" for n in ADDED)
       and not report["deleted_components"] and report["candidate_sha256"] == sha(cand_bytes),
       {"changed_components": report["changed_components"], "candidate_sha256": sha(cand_bytes),
        "detected_downstream_impact": report["detected_downstream_impact"]})

# --- 4. structure: issues and stored errors ---------------------------------
new_issues = structural_issues(cand) - structural_issues(current)
err = lambda j, key: Counter("".join(e.itertext()) for e in j.elements[key].iter("error")) if key in j.elements else Counter()
new_errors = {k: dict(err(cand, k) - err(current, k)) for k in SIX if err(cand, k) - err(current, k)}
record("no_new_structural_issues_or_stored_errors", not new_issues and not new_errors and
       report["candidate_cached_errors"] == sum(e.tag == "error" for e in current.root.iter()),
       {"new_structural_issues": dict(new_issues), "new_stored_errors": new_errors,
        "candidate_cached_errors": report["candidate_cached_errors"]})

# --- 5. cross-reference resolution ------------------------------------------
sec = next(e for e in top["FBMPEndBent"].iter("section") if e.get("name") == SEC)
scopes = {n: top[n] for n in ADDED}
scopes["FBMPEndBent[EBCurrentDesignRecord]"] = sec
unresolved = {}
foreign = {}
counts = {}
cache_of_defs = {n: defined(top[n]) for n in module_names}
for label, root in scopes.items():
    refs = refs_in(root)
    counts[label] = sum(refs.values())
    foreign[label] = sorted({r for r, _ in refs})
    bad = sorted(f"{r}.{n}" for (r, n) in refs if n not in cache_of_defs[r])
    if bad:
        unresolved[label] = bad
record("every_report_name_reference_resolves", not unresolved and all(c for k, c in counts.items() if k != "CapDesignBasis"),
       {"references_checked": counts, "unresolved": unresolved})
# links and images in the new reports and PedBridge resolve exactly as in the current journal (same rule as `check`)
record("links_and_images_resolve", not new_issues, {"new_unresolved": dict(new_issues)})

# --- 6. new reports read only the declared owners ---------------------------
undeclared = {n: sorted(set(foreign[n]) - DECLARED_READS[n] - {n}) for n in ADDED if set(foreign[n]) - DECLARED_READS[n] - {n}}
record("new_reports_read_only_declared_owners", not undeclared,
       {"read": {n: foreign[n] for n in ADDED}, "undeclared": undeclared})

# --- 7. coherence.json versus the owner definitions in the candidate --------
coherence = json.loads((ROOT / "cap_bpad" / "journal" / "coherence.json").read_text(encoding="utf-8"))
rows, bad = [], []
for rep, entries in coherence.items():
    for ent in entries:
        owner_rep, owner_name = ent["owner"].split(".", 1)
        owner_value = value_of(owner_rep, owner_name)
        formula, cache, _ = get_def(rep, ent["input"])
        assert formula is not None, f"{rep}.{ent['input']} not defined"
        own_value = to_number(cache) if cache is not None else to_number(formula.split("=", 1)[1])
        ok = abs(owner_value - ent["journal_value"]) <= 1e-9 * max(1, abs(owner_value))
        if ent["status"] == "reference":
            rhs = re.sub(r"\s+to\s+\S+$", "", formula.split("=", 1)[1].strip())
            ok = ok and rhs == ent["owner"] and abs(own_value - ent["case_value"]) <= 1e-6 * max(1, abs(own_value)) \
                and ent["case_value"] == ent["journal_value"]
        else:  # literal kept because the journal value is incoherent with the case
            ok = ok and ent["status"] == "literal_incoherent_journal" and re.fullmatch(r"\s*L_cap\s*=\s*251 in\s*", formula) \
                is not None and own_value == ent["case_value"] == 251.0 and owner_value == ent["journal_value"] == 212.0
        rows.append({"report": rep, "input": ent["input"], "owner": ent["owner"], "owner_value": owner_value,
                     "journal_value": ent["journal_value"], "report_value": own_value, "status": ent["status"], "ok": bool(ok)})
        if not ok:
            bad.append(rows[-1])
record("owner_values_equal_coherence_json", not bad and len(rows) == 45,
       {"entries": len(rows), "mismatches": bad,
        "recorded_incoherence": [r for r in rows if r["status"] != "reference"]})

# --- 8. EBSteel_As* caches = count x area from the cap report literals ------
lit = {n: value_of(OWNER, n) for n in ("n_N1", "Bar_N1", "n_P1", "Bar_P", "n_B1", "Bar_B", "n_skin", "Bar_skin")}
ab_formula, _, _ = get_def("CapDesignBasis", "Ab")
areas = {int(k): float(a) for k, a in re.findall(r"k == (\d+), ([0-9.]+) in\^2", ab_formula)}
a = lambda bar: areas[int(lit[bar])]
want = {"EBSteel_topCount": lit["n_N1"], "EBSteel_topAreaEach": a("Bar_N1"), "EBSteel_bottomCount": lit["n_P1"],
        "EBSteel_bottomAreaEach": a("Bar_P"), "EBSteel_addedCount": lit["n_B1"], "EBSteel_addedAreaEach": a("Bar_B"),
        "EBSteel_skinEachSide": lit["n_skin"], "EBSteel_skinAreaEach": a("Bar_skin")}
want["EBSteel_AsTop"] = want["EBSteel_topCount"] * want["EBSteel_topAreaEach"]
want["EBSteel_AsPile"] = want["EBSteel_bottomCount"] * want["EBSteel_bottomAreaEach"]
want["EBSteel_AsSpan"] = want["EBSteel_AsPile"] + want["EBSteel_addedCount"] * want["EBSteel_addedAreaEach"]
want["EBSteel_AsSkinSide"] = want["EBSteel_skinEachSide"] * want["EBSteel_skinAreaEach"]
repoint = {"EBSteel_topCount": f"{OWNER}.n_N1", "EBSteel_topAreaEach": f"CapDesignBasis.Ab({OWNER}.Bar_N1) to in^2",
           "EBSteel_bottomCount": f"{OWNER}.n_P1", "EBSteel_bottomAreaEach": f"CapDesignBasis.Ab({OWNER}.Bar_P) to in^2",
           "EBSteel_addedCount": f"{OWNER}.n_B1", "EBSteel_addedAreaEach": f"CapDesignBasis.Ab({OWNER}.Bar_B) to in^2",
           "EBSteel_skinEachSide": f"{OWNER}.n_skin", "EBSteel_skinAreaEach": f"CapDesignBasis.Ab({OWNER}.Bar_skin) to in^2"}
problems = []
got = {}
for name, expect in want.items():
    formula, cache, el = None, None, None
    for e in sec.iter("dynexp"):
        if re.match(r"^" + name + r" =", e.get("formula", "")):
            formula, cache, el = e.get("formula"), e.find("expresult").text, e
            break
    got[name] = {"formula": formula, "cache": cache}
    if name in repoint:
        if formula != f"{name} = {repoint[name]}" or el.get("style") is not None:
            problems.append(f"{name}: formula/style {formula!r} {el.get('style')!r}")
    if cache is None or abs(to_number(cache) - expect) > 1e-9:
        problems.append(f"{name}: cache {cache!r} != {expect}")
table = next(t for t in sec.iter("table") if t.get("name") == "EBLongitudinalSummary")
cells = [[(c.get("formula"), "".join(c.itertext()).strip()) for c in row] for row in table.iter("row")]
expected_cells = [
    ("Top", f"{OWNER}.n_N1", lit["n_N1"], f"{OWNER}.Bar_N1", lit["Bar_N1"], "EBSteel_AsTop to in^2", want["EBSteel_AsTop"]),
    ("Bottom at piles (continuous)", f"{OWNER}.n_P1", lit["n_P1"], f"{OWNER}.Bar_P", lit["Bar_P"], "EBSteel_AsPile to in^2", want["EBSteel_AsPile"]),
    ("Added span bars", f"{OWNER}.n_B1", lit["n_B1"], f"{OWNER}.Bar_B", lit["Bar_B"],
     "EBSteel_addedCount*EBSteel_addedAreaEach to in^2", want["EBSteel_addedCount"] * want["EBSteel_addedAreaEach"]),
    ("Bottom between piles (total)", None, "continuous + added", None, "—", "EBSteel_AsSpan to in^2", want["EBSteel_AsSpan"]),
    ("Skin, each side", f"{OWNER}.n_skin", lit["n_skin"], f"{OWNER}.Bar_skin", lit["Bar_skin"], "EBSteel_AsSkinSide to in^2", want["EBSteel_AsSkinSide"]),
]
if [c[1] for c in cells[0]] != ["Family", "Bars (live)", "Bar no. (live)", "Area (live)"] or len(cells) != 6:
    problems.append(f"table header/rows: {cells[0]}, {len(cells)} rows")
else:
    for row, (label, f1, v1, f2, v2, f3, v3) in zip(cells[1:], expected_cells):
        if row[0][1] != label or row[1][0] != f1 or row[2][0] != f2 or row[3][0] != f3:
            problems.append(f"table row {label}: formulas {[c[0] for c in row]}")
        for cell, val in ((row[1], v1), (row[2], v2), (row[3], v3)):
            if isinstance(val, str):
                if cell[1] != val:
                    problems.append(f"table row {label}: text {cell[1]!r}")
            elif abs(to_number(cell[1]) - val) > 1e-9:
                problems.append(f"table row {label}: cache {cell[1]!r} != {val}")
inputs_left = [e.get("formula") for e in sec.iter("dynexp") if e.get("style") == "Required Input"]
materials_ok = sorted(f.split(" =")[0] for f in inputs_left if f.startswith("EBSteel_")) == \
    ["EBSteel_Es", "EBSteel_aggregate", "EBSteel_barClear", "EBSteel_fc", "EBSteel_fy"]
if not materials_ok:
    problems.append(f"Required Input owners left in the section: {inputs_left}")
record("EBSteel_caches_equal_count_times_area", not problems,
       {"cap_literals": lit, "expected": want, "problems": problems, "found": got})

# --- 9. PedBridge: four links once each, nothing else -----------------------
ped = cand.part("report:PedBridge").decode("utf-8")
base_ped = base.part("report:PedBridge").decode("utf-8")
links = {n: ped.count(f'address="#{n}"') for n in ADDED}
sm = difflib.SequenceMatcher(None, base_ped.splitlines(True), ped.splitlines(True), autojunk=False)
ops = [(t, i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]
positions = [ped.index(f'address="#{n}"') for n in ["PierCapDesign"] + ADDED]
record("pedbridge_four_links_once_each_and_nothing_else", all(c == 1 for c in links.values()) and
       ops == [("insert", 0, 12)] and positions == sorted(positions) and ped.count('address="#PierCapDesign"') == 1,
       {"link_counts": links, "diff_ops": ops, "in_order_after_C005": positions == sorted(positions)})

# --- 10. FBMPEndBent: edits confined to the intro paragraph and block 2 ------
fb = cand.part("report:FBMPEndBent").decode("utf-8")
base_fb = base.part("report:FBMPEndBent").decode("utf-8")
bl, cl = base_fb.splitlines(True), fb.splitlines(True)
lo = next(i for i, l in enumerate(bl) if 'Current end-bent cap design record' in l and "<heading" in l)
hi = next(i for i, l in enumerate(bl) if "3. Actual transverse schedule</heading>" in l)
sm = difflib.SequenceMatcher(None, bl, cl, autojunk=False)
outside = [(t, i1, i2) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal" and not (lo <= i1 and i2 <= hi)]
changed_lines = sum(max(i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal")
tail_equal = bl[hi:] == cl[len(cl) - (len(bl) - hi):]
record("fbmp_edits_confined_to_intro_and_block_2", not outside and tail_equal and bl[:lo] == cl[:lo],
       {"changed_lines": changed_lines, "outside_ops": outside, "base_range_lines": [lo + 1, hi + 1],
        "new_heading_follow": "Block 2 (longitudinal reinforcement) is live from CapDesignEndBentOne" in fb})

# --- 11. new reports: Status, DC names, no stored errors, fragment bytes ----
fragment_ok, info = True, {}
verification = json.loads((ROOT / "cap_bpad" / "journal" / "verification.json").read_text(encoding="utf-8"))
recorded = {verification["basis"]["report_name"]: verification["basis"]["fragment_sha256"]}
recorded.update({r["report_name"]: r["fragment_sha256"] for r in verification["reports"]})
for n in ADDED:
    part = cand.part(f"report:{n}")
    names = defined(top[n])
    status = get_def(n, "Status")[1]
    info[n] = {"bytes": len(part), "sha256": sha(part), "matches_verification_json": sha(part) == recorded[n],
               "DC_names": sum(1 for x in names if x.startswith("DC_")), "has_Status": "Status" in names,
               "Status_cache": status.strip().lstrip("=").strip() if status else None, "stored_errors": len(list(top[n].iter("error")))}
    fragment_ok &= info[n]["matches_verification_json"] and info[n]["stored_errors"] == 0
    if n != "CapDesignBasis":
        fragment_ok &= info[n]["has_Status"] and info[n]["DC_names"] > 0
record("new_reports_match_fragments_and_have_status", fragment_ok, info)

# --- write ------------------------------------------------------------------
out = {"candidate": str(FOLDER / "candidate.bpad"), "candidate_sha256": sha(cand_bytes), "all_passed": all(r["passed"] for r in results.values()),
       "checks": results}
text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
(TASK / "independent-checks.json").write_text(text, encoding="utf-8")
shutil.copyfile(TASK / "independent-checks.json", FOLDER / "independent-checks.json")
print(json.dumps({"all_passed": out["all_passed"], "candidate_sha256": out["candidate_sha256"],
                  "checks": {k: r["passed"] for k, r in results.items()}}, indent=2))
sys.exit(0 if out["all_passed"] else 1)
