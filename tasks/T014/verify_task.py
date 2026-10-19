"""T014 independent checks on the assembled candidate.

Does not reuse build_components.py or geom_eval.py: expected values are recomputed here with plain Python
from literals read out of the candidate itself.
Usage: verify_task.py [candidate_folder]   (default generated/T014-journal-coherence-01)
Writes tasks/T014/independent-checks.json (and a copy in the candidate folder).
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
from scripts.build_cap_bpad import PROJECT_STAMP  # noqa: E402

FOLDER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "generated" / "T014-journal-coherence-01"
NBSP = " "
CAPS = ["CapDesignBasis", "CapDesignEndBentOne", "CapDesignEndBentTwo", "CapDesignPier"]
STAMPED17 = ["Materials", "BridgeGeometry_2Beam", "AccessGeometry", "BearingDesign", "PileProperties", "GeneralLoads",
             "PedBridgeWind", "C001WindLoadOnPedBridgeSuperstructure", "FenceWind", "BridgeMovement",
             "SuperstructureUplift", "LoadCombinations", "FBMPPier", "FBMPEndBent", "FoundationModeling",
             "PierWallFins", "MSEWallExclusion"]
STAMP_REPORTS = STAMPED17 + CAPS + ["ProjectInfo"]
PURE_INSERT = [n for n in STAMPED17 if n not in ("Materials", "BridgeGeometry_2Beam", "FBMPPier", "FBMPEndBent", "PierWallFins")]
WRITES = sorted(f"report:{n}" for n in set(STAMP_REPORTS) | {"PedBridge", "DecisionLog", "PierCapDesign"})
REF_TARGETS = ("Materials", "BridgeGeometry_2Beam", "ProjectInfo", "CapDesignBasis", "CapDesignEndBentOne")

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
definitions = json.loads((TASK / "definitions.json").read_text(encoding="utf-8"))
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


def texts(root):
    for e in root.iter():
        for attr in ("formula", "condition", "valuedef", "address", "source", "target"):
            if e.get(attr):
                yield e.get(attr)
        if e.tag == "expbody" and e.text:
            yield e.text


def get_def(rep, name):
    for e in top[rep].iter():
        if re.match(r"^\s*" + re.escape(name) + r"\s*(?:\([^)]*\))?\s*=(?!=)", e.get("formula", "")):
            r = e.find("expresult")
            return e.get("formula"), (r.text if r is not None else None), e
    return None, None, None


# ---------------------------------------------------------------------------------------------------------
# 1. component scope
# ---------------------------------------------------------------------------------------------------------
diff = sorted(k for k in set(cand.order) | set(current.order) if cand.hashes.get(k) != current.hashes.get(k))
record("candidate_differs_from_current_only_in_registered_scope", diff == WRITES and cand.shell == current.shell,
       {"differing": diff, "expected": WRITES, "shell_identical": cand.shell == current.shell,
        "current_matches_task_base": current.sha256 == base.sha256})
record("report_json_changed_and_deleted_components",
       sorted(report["changed_components"]) == WRITES and report["deleted_components"] == ["report:PierCapDesign"]
       and report["added_components"] == ["report:ProjectInfo"] and report["candidate_sha256"] == sha(cand_bytes)
       and report["candidate_cached_errors"] == 0,
       {"changed": len(report["changed_components"]), "deleted": report["deleted_components"], "added": report["added_components"],
        "detected_downstream_impact": report["detected_downstream_impact"], "candidate_sha256": sha(cand_bytes)})
new_issues = structural_issues(cand) - structural_issues(current)
record("no_new_structural_issues_or_stored_errors", not new_issues and sum(e.tag == "error" for e in tree.iter()) == 0,
       {"new_issues": dict(new_issues), "candidate_structural_issues": dict(structural_issues(cand))})

# ---------------------------------------------------------------------------------------------------------
# 2. C005 gone
# ---------------------------------------------------------------------------------------------------------
leftovers = {}
for name, el in top.items():
    if el.tag not in MODULE_TAGS:
        continue
    hits = [t for t in texts(el) if "PierCapDesign" in t]
    if hits:
        leftovers[name] = hits[:3]
record("no_PierCapDesign_report_link_or_formula", "PierCapDesign" not in top and "report:PierCapDesign" not in cand.spans and not leftovers,
       {"report_present": "PierCapDesign" in top, "references_left": leftovers})
c005_text = {}
for name, el in top.items():
    if el.tag in MODULE_TAGS:
        n = sum("C005" in "".join(p.itertext()) for p in el.iter("paragraph"))
        if n:
            c005_text[name] = n
record("remaining_C005_mentions_are_history_or_cap_provenance", set(c005_text) <= set(CAPS) | {"DecisionLog", "PedBridge", "FBMPPier", "BridgeGeometry_2Beam", "FBMPEndBent"},
       {"paragraphs_mentioning_C005": c005_text})

# ---------------------------------------------------------------------------------------------------------
# 3. qualified references resolve
# ---------------------------------------------------------------------------------------------------------
REF = re.compile(r"(?<![\w.])(" + "|".join(REF_TARGETS) + r")\.([^\W\d]\w*)")
def_cache = {n: defined(top[n]) for n in REF_TARGETS}
bad, used = {}, Counter()
for name, el in top.items():
    if el.tag not in MODULE_TAGS:
        continue
    for t in texts(el):
        if t.startswith("#"):
            continue
        for rep_name, ident in REF.findall(t):
            used[f"{rep_name}.{ident}"] += 1
            if ident not in def_cache[rep_name]:
                bad.setdefault(name, set()).add(f"{rep_name}.{ident}")
record("every_Materials_Geometry_ProjectInfo_CapBasis_CapOne_reference_resolves", not bad and used,
       {"distinct_references": len(used), "unresolved": {k: sorted(v) for k, v in bad.items()},
        "sample": dict(list(used.most_common(8)))})
expect_refs = {"Materials.Substructure_fc", "Materials.Rebar_fy", "Materials.Rebar_Es", "BridgeGeometry_2Beam.PierCap_coverTop",
               "BridgeGeometry_2Beam.PierCap_coverBottom", "BridgeGeometry_2Beam.PierCap_coverSide", "BridgeGeometry_2Beam.EndBentCage_envelope",
               "ProjectInfo.Firm", "ProjectInfo.CheckDate"}
record("new_owners_are_used", expect_refs <= set(used), {"missing": sorted(expect_refs - set(used))})

# ---------------------------------------------------------------------------------------------------------
# 4. project stamp
# ---------------------------------------------------------------------------------------------------------
stamp_detail, stamp_ok = {}, True
for name in STAMP_REPORTS:
    tables = [t for t in top[name].iter("table") if t.get("name") == "ProjectStamp"]
    ok = len(tables) == 1
    seen = {}
    if ok:
        for c in tables[0].iter("c"):
            f = c.get("formula")
            if f:
                tv = c.find("textvalue")
                seen[f] = tv.text if tv is not None and tv.text else ""
        ok = seen == {f"ProjectInfo.{k}": v for k, v in PROJECT_STAMP.items()}
    stamp_detail[name] = {"tables": len(tables), "cells_equal_PROJECT_STAMP": ok}
    stamp_ok &= ok
total_stamps = sum(1 for n, el in top.items() if el.tag in MODULE_TAGS for t in el.iter("table") if t.get("name") == "ProjectStamp")
record("stamp_table_exactly_once_in_22_reports_with_PROJECT_STAMP_cells", stamp_ok and total_stamps == 22 and len(STAMP_REPORTS) == 22,
       {"reports_checked": len(STAMP_REPORTS), "stamp_tables_in_journal": total_stamps, "per_report": stamp_detail})
pi_values = {}
for key in PROJECT_STAMP:
    f, _, _ = get_def("ProjectInfo", key)
    m = re.fullmatch(key + r' = "(.*)"', f or "")
    pi_values[key] = m.group(1) if m else None
record("ProjectInfo_inputs_equal_PROJECT_STAMP", pi_values == PROJECT_STAMP, {"projectinfo": pi_values})
pure = {}
for name in PURE_INSERT:
    a, b = base.part(f"report:{name}").decode("utf-8").splitlines(True), cand.part(f"report:{name}").decode("utf-8").splitlines(True)
    ops = [(t, i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if t != "equal"]
    pure[name] = ops
record("stamp_is_a_single_insertion_in_unedited_reports", all(len(v) == 1 and v[0][0] == "insert" for v in pure.values()), pure)

# ---------------------------------------------------------------------------------------------------------
# 5. geometry chain recomputed with plain Python
# ---------------------------------------------------------------------------------------------------------
BG = "BridgeGeometry_2Beam"


def lit(name, rep=BG):
    f, _, _ = get_def(rep, name)
    assert f is not None, f"{rep}.{name} not defined"
    rhs = f.split("=", 1)[1].strip()
    total = 0.0
    m = re.fullmatch(r"(\d+)'\s*(\d+(?:\.\d+)?)\"", rhs)          # 7'1"
    if m:
        return int(m[1]) * 12 + float(m[2])
    parts = re.findall(r"(-?\d+(?:\.\d+)?)\s*(ft|in|ksi|kip)?", rhs)
    for num, unit in parts:
        total += float(num) * (12.0 if unit == "ft" else 1.0)
    return total


def cache_value(rep, name, unit):
    """Cached text of a definition converted to `unit` (in, ft, ft^2, ft^3, kip, or the raw string)."""
    f, c, _ = get_def(rep, name)
    assert c is not None, f"{name} has no cache"
    return parse_text(clean(c), unit)


def clean(c):
    return c.replace(NBSP, "").lstrip("=").strip()


def parse_text(t, unit):
    if unit == "text":
        return t
    if unit in ("ft^2", "ft^3", "kip"):
        assert t.endswith(" " + unit), t
        return float(t[: -len(unit) - 1])
    inches, matched = 0.0, False
    for m in re.finditer(r"(?:(-?\d+(?:\.\d+)?)\s*ft)|(?:(?:(\d+)\s+)?(\d+)/(\d+)\s*in)|(?:(-?\d+(?:\.\d+)?)\s*in)", t):
        matched = True
        if m.group(1) is not None:
            inches += float(m.group(1)) * 12
        elif m.group(3) is not None:
            inches += float(m.group(2) or 0) + int(m.group(3)) / int(m.group(4))
        else:
            inches += float(m.group(5))
    assert matched, t
    return inches / 12 if unit == "ft" else inches


edge, tol, width, spacing, pcount = (lit(n) for n in ("EndBent_edgeClear", "EndBent_pileTolerance", "EndBent_pileWidth", "EndBent_pileSpacing", "EndBent_pileCount"))
pile_end_clear = lit("EndBent_pileEndClear")
cheek = lit("EndBent_cheekThickness")
cap_w, cap_d = lit("EndBentCap_width"), lit("EndBentCap_depth")
end_detail = pile_end_clear - edge - tol
end_face = edge + tol + end_detail
end_center = end_face + width / 2
cap_len = (pcount - 1) * spacing + 2 * end_center
envelope = cap_len + 2 * cheek
area_ft2 = cap_w * cap_d / 144
vol = area_ft2 * cap_len / 12
c1, c2 = lit("Beam_camber_1"), lit("Beam_camber_2")
hmin, xfall, flange, nbeam = lit("Haunch_min"), 0.02, lit("Beam_topFlange_width"), 2.0
def station(name):
    return float(re.search(r"=\s*([\d.]+)", get_def(BG, name)[0])[1])


span1 = (station("CLPier_station") - station("BeginBridge_station")) * 12
span2 = (station("EndBridge_station") - station("CLPier_station")) * 12
mx = max(c1, c2)
avg1 = hmin + mx - 2 * c1 / 3 + xfall * flange / 2
avg2 = hmin + mx - 2 * c2 / 3 + xfall * flange / 2
v1 = nbeam * span1 * flange * avg1 / 1728
v2 = nbeam * span2 * flange * avg2 / 1728
# support drop (inches) recomputed from its original closed-form inputs: slab + beam + crossfall over the flange edge + haunch + larger camber
drop = lit("Thickness_slab_peak") + lit("Beam_depth") + xfall * (lit("Beam_spacing") / 2 + flange / 2) + hmin + mx
NOTEBOOK_DROP_IN = 3.7147642885879173 * 12
pgl_start, pgl_end = lit("PGL_start_elev"), lit("PGL_end_elev")
grade = float(re.search(r"=\s*([\d.]+)", get_def(BG, "PGL_nominalGrade")[0])[1])
pgl_pier = (pgl_start + grade * span1 + pgl_end + grade * span2) / 2
plane = lit("Pedestal_ht") + lit("Bearing_pad_thickness") + lit("Bearing_separatePlateThickness")
terrain, cap_ht, depth_super = lit("Terrain_elev"), lit("PierCap_ht"), lit("Depth_SuperStr")
fence_ht = parse_text(clean(get_def(BG, "Fence_ht")[1]), "in")           # cached in 1/64 in; not changed by T014
soffit = pgl_pier - drop
cap_top = soffit - plane
cap_top_at = cap_top - terrain
wind_clear = cap_top_at + plane
pier_len = parse_text(clean(get_def(BG, "Pier_windFace_width")[1]), "in")
expected = {   # name: (value in the display unit, unit)
    "EndBent_endFace": (end_face, "in"), "EndBent_endCenter": (end_center, "in"), "EndBentCap_length": (cap_len / 12, "ft"),
    "EndBentCap_volume": (vol, "ft^3"), "EndBentCaps_volume": (2 * vol, "ft^3"), "EndBentCap_DC": (vol * 0.150, "kip"),
    **{f"EndBent_P{i + 1}_station": (end_center + i * spacing, "in") for i in range(4)},
    "Haunch_average_1": (avg1, "in"), "Haunch_average_2": (avg2, "in"), "Haunch_volume_span1": (v1, "ft^3"), "Haunch_volume_span2": (v2, "ft^3"),
    "Haunch_totalVolume": (v1 + v2, "ft^3"), "Haunch_volume_perBeam": ((v1 + v2) / 2, "ft^3"),
    "Beam_bottom_start": ((pgl_start - drop) / 12, "ft"), "Beam_bottom_pier": (soffit / 12, "ft"), "Beam_bottom_end": ((pgl_end - drop) / 12, "ft"),
    "BO_LowBeam": (soffit / 12, "ft"), "Bearing_soffit_elev": (soffit / 12, "ft"), "CapTop_elev": (cap_top / 12, "ft"),
    "CapCG_elev": ((cap_top - cap_ht / 2) / 12, "ft"), "CapBottom_elev": ((cap_top - cap_ht) / 12, "ft"),
    "CapTop_aboveTerrain": (cap_top_at, "in"), "CapCG_aboveTerrain": (cap_top_at - cap_ht / 2, "in"), "CapBottom_aboveTerrain": (cap_top_at - cap_ht, "in"),
    "PierCap_ht_toTop": (cap_top_at, "in"), "Pile_ht_exposed": ((cap_top_at - cap_ht / 2) / 12, "ft"),
    "Pier_wall_area": (pier_len / 12 * cap_top_at / 12, "ft^2"), "Wind_clearHeight": (wind_clear, "in"),
    "Concrete_top_aboveGround": (wind_clear + depth_super, "in"), "Wind_exposureHeight": (wind_clear + depth_super + fence_ht, "in"),
    "Beam_support_drop": (drop / 12, "ft"), "EndBent_endDetail": (end_detail, "in"), "EndBentCage_envelope": (envelope, "in"),
}
rows, bad_rows = [], []
for name, (value, unit) in expected.items():
    got = cache_value(BG, name, unit)
    tolerance = 1 / 128 if "/" in clean(get_def(BG, name)[1]) else 0.00051 * (12 if unit == "ft" else 1)
    tol_unit = tolerance / 12 if unit == "ft" else tolerance
    ok = abs(got - value) <= max(tol_unit, 0.00051 if unit != "in" else tolerance)
    rows.append({"name": name, "recomputed": round(value, 6), "cache": clean(get_def(BG, name)[1]), "ok": bool(ok)})
    if not ok:
        bad_rows.append(rows[-1])
exact = {"EndBent_endFace": 27.5, "EndBent_endCenter": 36.5, "EndBentCap_length": 235.0, "EndBentCage_envelope": 251.0}
exact_ok = (end_face, end_center, cap_len, envelope) == (27.5, 36.5, 235.0, 251.0) and cache_value(BG, "EndBentCap_length", "in") == 235.0 \
    and cache_value(BG, "EndBentCage_envelope", "in") == 251.0 and clean(get_def(BG, "EndBentCap_length")[1]) == "19 ft 7 in"
record("geometry_chain_endbent_27p5_36p5_235_251", exact_ok, {"endFace": end_face, "endCenter": end_center, "capLength": cap_len, "envelope": envelope,
                                                              "cache_EndBentCap_length": clean(get_def(BG, "EndBentCap_length")[1])})
refreshed_names = {c["name"] for c in definitions["refreshed_caches"] if "name" in c}
unchecked = sorted(refreshed_names - set(expected) - {"Check_notebook_quantity"})
check_f, check_c, _ = get_def(BG, "Check_notebook_quantity")
record("every_refreshed_geometry_cache_equals_recomputed_value", not bad_rows and not unchecked
       and clean(check_c) == ("INPUTS CHANGED - RECONCILE NOTEBOOK" if abs(v1 + v2 - 185.836666666667) > 1e-6 else "MATCHES 2026-09-29 NOTEBOOK"),
       {"compared": len(rows), "mismatches": bad_rows, "refreshed_without_expectation": unchecked, "Check_notebook_quantity": clean(check_c)})
cells = {}
for row in [t for t in top[BG].iter("table") if t.get("name") == "EBCurrentPileStations"][0].iter("row"):
    vals = [("".join(c.itertext()).strip()) for c in row]
    if re.fullmatch(r"P\d", vals[0]):
        cells[vals[0]] = vals[1:]
want = {f"P{i + 1}": [f"{end_center + i * spacing:g} in", f"{end_center + i * spacing - width / 2:g} in", f"{end_center + i * spacing + width / 2:g} in"] for i in range(4)}
record("pile_table_cells_equal_recomputed_centers_and_faces", cells == want, {"table": cells, "expected": want})
literals_ok = (clean(get_def(BG, "Beam_camber_1")[0].split("=", 1)[1]) == "0.124592744006574 in" and get_def(BG, "Beam_camber_2")[0].endswith("0.5671714630550072 in")
               and get_def(BG, "Beam_support_drop")[0] == ("Beam_support_drop = Thickness_slab_peak+Beam_depth+Deck_crossfall*(Beam_spacing/2+Beam_topFlange_width/2)"
                                                           "+Haunch_min+Max(Beam_camber_1,Beam_camber_2) to ft")      # original formula kept
               and get_def(BG, "Beam_support_drop")[2].get("style") is None
               and abs(drop - NOTEBOOK_DROP_IN) < 1e-9 and clean(get_def(BG, "Beam_support_drop")[1]) == "3.715 ft"
               and "Equals the notebook common support drop 3.7148 ft (model e9b41b8eaf) with the notebook net cambers." in cand.part("report:BridgeGeometry_2Beam").decode("utf-8")
               and get_def(BG, "EndBent_endDetail")[0] == "EndBent_endDetail = EndBent_pileEndClear-EndBent_edgeClear-EndBent_pileTolerance to in"
               and get_def(BG, "EndBent_endDetail")[2].get("style") is None
               and all(get_def(BG, n)[2].get("style") == "Required Input" for n in ("EndBent_pileEndClear", "EndBent_cheekThickness", "EndBent_lugProjection",
                                                                                     "EndBent_lugWidth", "EndBent_mseJoint", "PierCap_coverTop", "PierCap_coverBottom", "PierCap_coverSide"))
               and (pile_end_clear, cheek, lit("EndBent_lugProjection"), lit("EndBent_lugWidth"), lit("EndBent_mseJoint")) == (27.5, 8.0, 6.0, 5.5, 0.5)
               and all(lit(n) == 3 for n in ("PierCap_coverTop", "PierCap_coverBottom", "PierCap_coverSide")))
record("notebook_literals_present_with_expected_styles", literals_ok, {})

# ---------------------------------------------------------------------------------------------------------
# 6. materials, consumers, index, decision log
# ---------------------------------------------------------------------------------------------------------
want_mat = {"Substructure_fc": 5.5, "Deck_fc": 4.5, "Beam_fc": 8.5, "Railing_fc": 3.4, "Rebar_fy": 60, "Rebar_Es": 29000}
got_mat = {}
for n in want_mat:
    f, _, e = get_def("Materials", n)
    got_mat[n] = (f, e.get("style"), e.get("showresult"))
mat_ok = all(got_mat[n][0] == f"{n} = {v:g} ksi" and got_mat[n][1] == "Required Input" and got_mat[n][2] == "False" for n, v in want_mat.items())
mt = top["Materials"]
mat_ok &= "PierCapDesign" not in cand.part("report:Materials").decode() and 'address="#PileProperties"' in cand.part("report:Materials").decode()
record("Materials_six_amber_inputs_and_C005_link_gone", mat_ok, got_mat)
cons = {}
for rep_name, name, rhs in [("FBMPEndBent", "EBSteel_fc", "Materials.Substructure_fc to ksi"), ("FBMPEndBent", "EBSteel_fy", "Materials.Rebar_fy to ksi"),
                            ("FBMPEndBent", "EBSteel_Es", "Materials.Rebar_Es to ksi"), ("PierWallFins", "f_c", "Materials.Substructure_fc to ksi"),
                            ("PierWallFins", "f_y", "Materials.Rebar_fy to ksi"), ("PierWallFins", "E_s", "Materials.Rebar_Es to ksi"),
                            ("PierWallFins", "c_w", "BridgeGeometry_2Beam.PierCap_coverSide to in")]:
    f, c, e = get_def(rep_name, name)
    cons[f"{rep_name}.{name}"] = {"formula": f, "style": e.get("style"), "cache": clean(c) if c else None}
record("consumers_redirected_with_unchanged_caches",
       all(v["formula"].endswith(" = " + r) and v["style"] is None for (k, v), r in zip(cons.items(), [x[2] for x in [
           (0, 0, "Materials.Substructure_fc to ksi"), (0, 0, "Materials.Rebar_fy to ksi"), (0, 0, "Materials.Rebar_Es to ksi"),
           (0, 0, "Materials.Substructure_fc to ksi"), (0, 0, "Materials.Rebar_fy to ksi"), (0, 0, "Materials.Rebar_Es to ksi"),
           (0, 0, "BridgeGeometry_2Beam.PierCap_coverSide to in")]]))
       and [v["cache"] for v in cons.values()] == ["5.5 ksi", "60 ksi", "29000 ksi", "5.5 ksi", "60 ksi", "29000 ksi", "3 in"], cons)
ped = cand.part("report:PedBridge").decode("utf-8")
first_link = [m.group(1) for m in re.finditer(r'<link address="#([^"]+)"', ped[ped.index("Project basis and geometry"):])][0]
record("PedBridge_links", 'address="#PierCapDesign"' not in ped and ped.count('address="#ProjectInfo"') == 1 and first_link == "ProjectInfo"
       and all(ped.count(f'address="#{n}"') == 1 for n in CAPS[1:]), {"first_link_under_project_basis": first_link})
log = cand.part("report:DecisionLog").decode("utf-8")
record("DecisionLog_entry_appended_history_kept", "2026-10-19 - C005 removed" in log and "RampSlabBackwallDecision20261016" in log
       and log.count("C005 remains completely unchanged") == 1 and log.endswith("</section>" + ("\r\n" if "</section>\r\n    </report>" in log else "\n") + "    </report>"), {})

# ---------------------------------------------------------------------------------------------------------
# 7. cap reports and coherence.json
# ---------------------------------------------------------------------------------------------------------
coherence = json.loads((ROOT / "cap_bpad" / "journal" / "coherence.json").read_text(encoding="utf-8"))
statuses = Counter(e["status"] for v in coherence.values() for e in v)
l_cap = {k: next(e["owner"] for e in v if e["input"] == "L_cap") for k, v in coherence.items()}
verification = json.loads((ROOT / "cap_bpad" / "journal" / "verification.json").read_text(encoding="utf-8"))
recorded = {verification["basis"]["report_name"]: verification["basis"]["fragment_sha256"]}
recorded.update({r["report_name"]: r["fragment_sha256"] for r in verification["reports"]})
frag = {}
for n in CAPS:
    part = cand.part(f"report:{n}")
    frag[n] = {"bytes": len(part), "sha256": sha(part), "matches_fragment": sha(part + b"\n") == recorded[n] or sha(part) == recorded[n] or sha(part + b"\r\n") == recorded[n]}
record("cap_reports_match_generator_and_coherence_has_no_incoherent_rows",
       "literal_incoherent_journal" not in statuses and l_cap["CapDesignEndBentOne"] == "BridgeGeometry_2Beam.EndBentCage_envelope"
       and l_cap["CapDesignEndBentTwo"] == "BridgeGeometry_2Beam.EndBentCage_envelope" and all(v["matches_fragment"] for v in frag.values()),
       {"statuses": dict(statuses), "L_cap_owner": l_cap, "fragments": frag})
cap_refs_pier_c005 = any("PierCapDesign" in t for n in CAPS for t in texts(top[n]))
record("cap_reports_do_not_read_deleted_C005", not cap_refs_pier_c005, {})

# ---------------------------------------------------------------------------------------------------------
out = {"candidate": str(FOLDER / "candidate.bpad"), "candidate_sha256": sha(cand_bytes), "all_passed": all(r["passed"] for r in results.values()), "checks": results}
text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
(TASK / "independent-checks.json").write_text(text, encoding="utf-8")
shutil.copyfile(TASK / "independent-checks.json", FOLDER / "independent-checks.json")
print(json.dumps({"all_passed": out["all_passed"], "candidate_sha256": out["candidate_sha256"], "checks": {k: r["passed"] for k, r in results.items()}}, indent=2))
sys.exit(0 if out["all_passed"] else 1)
