"""T016 independent checks on the assembled candidate.

Does not reuse build_components.py or mse_eval.py: expected values are recomputed here with plain Python
from the project record (source_register.csv, the D-049 XMLs, the notebook CONFIG, a fresh wall extraction).
Usage: verify_task.py [candidate_folder]   (default generated/T016-coherence-01)
Writes tasks/T016/independent-checks.json (and a copy in the candidate folder).
"""
import csv
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TASK))
from tools.bpad_workflow import Journal, structural_issues  # noqa: E402
import extract_mse_layout  # noqa: E402

FOLDER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "generated" / "T016-coherence-01"
WRITES = ["BridgeGeometry_2Beam", "DecisionLog", "FBMPEndBent", "FBMPPier", "FoundationModeling", "MSEWallExclusion", "PedBridge", "PileProperties"]
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


def text_of(name):
    return cand.part(f"report:{name}").decode("utf-8")


# 1. scope: exactly the eight registered components differ; everything else byte identical; order unchanged
changed = [k for k in base.order if base.hashes[k] != cand.hashes.get(k)]
record("changed_components", set(changed) == {f"report:{n}" for n in WRITES} and base.order == cand.order and base.sha256 == current.sha256,
       {"changed": changed, "base_is_current": base.sha256 == current.sha256})
record("report_json_changed_set", set(report.get("changed_components", [])) == {f"report:{n}" for n in WRITES}
       and not report.get("deleted_components") and not report.get("added_components"), report.get("changed_components"))
record("structural", structural_issues(cand) == {} and report.get("candidate_cached_errors") == 0 and report.get("structural_delta") == "passed",
       {"issues": structural_issues(cand), "cached_errors": report.get("candidate_cached_errors")})

# 2. link targets inside the candidate resolve (#Report or #Report.Section)
sections = {}
for name, e in top.items():
    sections[name] = {s.get("name") for s in e.iter("section") if s.get("name")}
bad, new_links = [], 0
for n in WRITES:
    before = base.part(f"report:{n}").decode("utf-8")
    for link in E.fromstring(cand.part(f"report:{n}")).iter("link"):
        a = link.get("address", "")
        if not a.startswith("#") or f'address="{a}"' in before:      # only links this task added
            continue
        new_links += 1
        r, _, s = a[1:].split(";")[0].partition(".")
        if r not in top or (s and s not in sections[r]):
            bad.append((n, a))
record("links_resolve", not bad and new_links >= 5, {"new_links": new_links, "unresolved": bad})

# 3. identities in the text equal the register
reg = {row["source_id"]: row for row in csv.DictReader((ROOT / "project_current" / "source_register.csv").open(encoding="utf-8-sig", newline=""))}
ids = {"EB-XML": "c1a4afa138865b3f10cc968ce7daef767a4d96e8bc2ccf175c1a5ebd150d912d", "EB2-XML": "3543df298b92593ce9bac14f9228ffacf5b0ce7e76b5e1d887ae228ef811a90e",
       "PIER-XML": "bb73e6ada6cf35ebb80b512cee315075807fc8ccab7878406d81ff381ae40fe7", "EB-REPORT": "6a42c16b0595ac16070608abd5d129a6152803693cb06a870b3168685c52e7a1",
       "PIER-REPORT": "e49d579c0186e7c2617828d236cb982adb92122345493a097e7c352df2f3a701", "CAD-MODEL": "d0f053d5104498b984a7bf32cbcda6c594af65e0bd0aee9b29d36f828a7a81df"}
reg_ok = {k: reg[k]["sha256"] == v for k, v in ids.items()}
file_ok = {k: sha((ROOT / reg[k]["path"]).read_bytes()) == v for k, v in ids.items()}
whole = "".join(text_of(n) for n in WRITES)
record("register_identities", all(reg_ok.values()) and all(file_ok.values()) and all(v in whole for v in ids.values()),
       {"register": reg_ok, "files": file_ok, "in_text": {k: v in whole for k, v in ids.items()}})

# 4. facts read from the D-049 exports
def nodal_nodes(path):
    return {m for m in re.findall(r"<NODAL_LOAD case='\d+' AASHTO_load_type='(?:LL1|IM1|BR1|PL)' node_number='(\d+)'>", path.read_text(encoding="utf-8", errors="replace"))}
eb1 = ROOT / reg["EB-XML"]["path"]
eb2 = ROOT / reg["EB2-XML"]["path"]
pier = (ROOT / reg["PIER-XML"]["path"]).read_text(encoding="utf-8", errors="replace")
ys = re.findall(r"<Y units='in'>(-?10\.\d+)</Y>", pier)
shell = re.search(r"<SHELL_THICK units='in'>([\d.]+)</SHELL_THICK>", pier)
fy = re.search(r"<FY units='ksi'>([\d.]+)</FY>", pier)
record("xml_facts", nodal_nodes(eb1) == {"15", "34"} and nodal_nodes(eb2) == {"15", "34"} and sorted(set(ys)) == ["-10.50", "10.50"]
       and shell and abs(float(shell[1]) - 0.48) < 1e-9,
       {"eb1_nodes": sorted(nodal_nodes(eb1)), "eb2_nodes": sorted(nodal_nodes(eb2)), "pier_bearing_Y": sorted(set(ys)),
        "pier_shell_in": shell[1] if shell else None, "pier_fy_ksi": fy[1] if fy else None})

# 5. notebook backwall drop and cambers
nb = (ROOT / "Bridge_Geometry_2 Beam_V2.ipynb").read_text(encoding="utf-8")
geom = text_of("BridgeGeometry_2Beam")
record("notebook_values", "CONFIG['end_bents']['start']['backwall_drop_in'] = 4.25" in nb and "CONFIG['end_bents']['end']['backwall_drop_in'] = 4.25" in nb
       and "<expbody>EndBent_backwallDrop = 4.25 in</expbody>" in geom
       and re.search(r"Abs\(Beam_camber_1-0\.124592744006574 in\)", geom) and "<expbody>Beam_camber_1 = 0.124592744006574 in</expbody>" in geom
       and re.search(r"Abs\(Beam_camber_2-0\.5671714630550072 in\)", geom) and "<expbody>Beam_camber_2 = 0.5671714630550072 in</expbody>" in geom
       and "= MATCHES NOTEBOOK BUILD e9b41b8eaf (2026-10-19)</expresult>" in geom and "INPUTS CHANGED - RECONCILE NOTEBOOK</expresult>" not in geom,
       "backwall drop 4.25 in both CONFIG entries; check compares the camber literals of the report; cache MATCHES")

# 6. MSE: wall literals equal a fresh extraction; gaps recomputed in plain python
layout = extract_mse_layout.extract()
mse = text_of("MSEWallExclusion")
lits = dict(re.findall(r'<dynexp formula="(Bent\dW\d(?:x|y|len|tx|ty|nx|ny)) = ([^"]+)"', mse))
expected, gaps = {}, {}
for bi, b in enumerate(layout["bents"], 1):
    flip = 1 if bi == 1 else -1
    for wi, wid in enumerate(["A5", "A6", "A7"] if bi == 1 else ["B1", "B6", "B7"], 1):
        w = layout["walls"][wid]
        x, y = w["start"][0] - b["center"][0], (w["start"][1] - b["center"][1]) * flip
        nx, ny = -w["outward"][0], -w["outward"][1] * flip
        expected[f"Bent{bi}W{wi}x"], expected[f"Bent{bi}W{wi}y"], expected[f"Bent{bi}W{wi}len"] = f"{x:.15g} ft", f"{y:.15g} ft", f"{w['length']:.15g} ft"
        for s, v in (("tx", w["tangent"][0]), ("ty", w["tangent"][1] * flip), ("nx", nx), ("ny", ny)):
            expected[f"Bent{bi}W{wi}{s}"] = str(float(v))
        # gap from the nominal pile faces (plain geometry, inches): min over the four piles of the normal distance minus the half width
        faces = []
        for j in range(4):
            px = (j - 1.5) * 54 * abs(__import__("math").sin(__import__("math").radians(layout["frame_angle_deg"])))
            py = flip * (j - 1.5) * 54 * __import__("math").cos(__import__("math").radians(layout["frame_angle_deg"]))
            faces.append((px - x * 12) * nx + (py - y * 12) * ny - 9)
        gaps[f"Bent{bi}W{wi}"] = min(faces)
record("mse_wall_literals", all(lits.get(k) == v for k, v in expected.items()) and len(lits) == 42 and layout["model_sha256"] == ids["CAD-MODEL"],
       {"mismatch": {k: (lits.get(k), v) for k, v in expected.items() if lits.get(k) != v}, "model_sha256": layout["model_sha256"]})
statuses = dict(re.findall(r'<expbody>(Bent\dW\dStatus) = [^<]*</expbody>\s*<expresult>[^=]*= ([^<]*)</expresult>', mse))
expect_status = {k: ("MEETS CLEAR" if g >= (37.5 if k.endswith("W1") else 24.0) else "SHORTFALL") for k, g in gaps.items()}
record("mse_gaps_and_statuses", all(statuses.get(k + "Status") == v for k, v in expect_status.items())
       and all(abs(gaps[k] - (37.5 if k.endswith("W1") else 24.0)) < 0.01 for k in gaps),
       {"gaps_in": {k: round(v, 6) for k, v in gaps.items()}, "status": statuses, "expected": expect_status})
cap = re.search(r"<expbody>CapLength = BridgeGeometry_2Beam.EndBentCap_length</expbody>\s*<expresult>[^=]*= ([^<]*)</expresult>", mse)
record("mse_cap_cache", cap and cap[1] == "19 ft 7 in" and "Saved model SHA-256: " + ids["CAD-MODEL"] in mse, cap[1] if cap else None)

# 7. superseded identities only in historical mentions; stale phrases gone
stale = {"17 ft 8 in long": whole.count("17 ft 8 in long"), "INPUTS CHANGED cache": whole.count("= INPUTS CHANGED - RECONCILE NOTEBOOK</expresult>"),
         "matching raw XML is still needed": whole.count("matching raw XML is still needed"), "SOURCE LIMIT": whole.count("SOURCE LIMIT:"),
         "185.5 ft^3 cell": whole.count("<num>185.5 ft^3</num>"), "old EB xml sha as current": whole.count("Recorded analysis XML SHA-256: 739f44c1")}
record("stale_text_removed", all(v == 0 for v in stale.values()), stale)
fb = text_of("FBMPEndBent")
record("endbent_forces", all(f"<textvalue>{v}</textvalue>" in fb for v in ["79.30 kip-ft", "67.16 kip-ft", "182.09 kip-ft", "91.77 kip", "3.09 kip-ft"])
       and ">53.30 / 49.33 / 138.47 kip-ft</paragraph>" in fb and "<num>205.625 ft^3</num>" in fb and "<num>411.25 ft^3</num>" in fb,
       "19 October End Bent 1 case values present (selected_case.json inputs Mu_N 79.3, Mu_P 67.16, Mu_B 182.09, Vu_G 91.77, Tu 3.09, MI 53.3/49.33/138.47)")
case = json.loads((ROOT / reg["EB-CASE"]["path"]).read_text(encoding="utf-8"))["inputs"]
record("endbent_case_values", [case["Mu_N"], case["Mu_P"], case["Mu_B"], case["Vu_G"], case["Tu"], case["MI_N"], case["MI_P"], case["MI_B"]]
       == [79.3, 67.16, 182.09, 91.77, 3.09, 53.3, 49.33, 138.47] and case["Bar_v"] == 6 and case["s_G"] == 9.0 and case["n_loop"] == 1,
       {k: case[k] for k in ["Mu_N", "Mu_P", "Mu_B", "Vu_G", "Tu", "MI_N", "MI_P", "MI_B", "Bar_v", "s_G", "n_loop"]})
record("new_sections", all(s in sections[r] for r, s in [("PileProperties", "PileDesignRecords20261019"), ("FoundationModeling", "ModelSources20261019"),
                                                        ("PedBridge", "CurrentRecord20261019"), ("DecisionLog", "CoherenceDecision20261019b")]), "four dated sections present")

out = {"candidate_sha256": cand.sha256, "base_sha256": base.sha256, "all_passed": all(r["passed"] for r in results.values()), "checks": results}
(TASK / "independent-checks.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
shutil.copy(TASK / "independent-checks.json", FOLDER / "independent-checks.json")
print(json.dumps({k: v["passed"] for k, v in results.items()}, indent=2), "\nALL PASSED" if out["all_passed"] else "\nFAILURES", file=sys.stdout)
sys.exit(0 if out["all_passed"] else 1)
