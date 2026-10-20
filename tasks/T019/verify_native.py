"""Verify and import only the registered report from the actual Blockpad save."""
from pathlib import Path
import hashlib
import json
import math
import sys
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal, check

key = "report:BearingDesign"
base = Journal.load(TASK / "base.bpad")
auth = Journal.load(TASK / "authored.bpad")
native_path = TASK / "native-recalculated.bpad"
if not native_path.exists():
    native_path.write_bytes((TASK / "working.bpad").read_bytes())
native = Journal.load(native_path)
assert native.sha256 != auth.sha256
assert base.order == auth.order
assert set(base.order) == set(native.order)
assert not list(native.elements[key].iter("error"))

def authored(e):
    omitted = {"expbody", "expresult", "expstep", "error"} if e.tag == "dynexp" and "formula" in e.attrib else {"num", "textvalue", "error"} if "formula" in e.attrib else set()
    text = (e.text or "").strip()
    if e.tag == "paragraph":
        text = " ".join(text.split())
    return (e.tag, tuple(sorted(e.attrib.items())), text,
            tuple((authored(c), (c.tail or "").strip()) for c in e if c.tag not in omitted))

assert authored(auth.elements[key]) == authored(native.elements[key]), "Native save changed authored content"
old_forms = [e.get("formula") for e in base.elements[key].iter() if "formula" in e.attrib]
new_forms = [e.get("formula") for e in native.elements[key].iter() if "formula" in e.attrib and not e.get("formula").startswith("BP_")]
# New qualified table references add one occurrence of the pad movement limit.
assert new_forms.count("BridgeGeometry_2Beam.Bearing_pad_shearLimit to in") == old_forms.count("BridgeGeometry_2Beam.Bearing_pad_shearLimit to in") + 1
ix = new_forms.index("BridgeGeometry_2Beam.Bearing_pad_shearLimit to in", new_forms.index("BridgeGeometry_2Beam.Bearing_pad_shearLimit to in")+1)
del new_forms[ix]
assert old_forms == new_forms, "An original formula changed"

ind = json.loads((TASK / "independent-check.json").read_text())
checks = []
def native_num(formula):
    cells = [c for c in native.elements[key].iter("c") if c.get("formula") == formula]
    assert len(cells) >= 1
    nums = [float(c.findtext("num").split()[0]) for c in cells]
    assert max(nums) == min(nums)
    return nums[0]

for row in ind["spans"]:
    i = row["span"]
    for field, var in [("bare120_rad", "bare120"), ("nc120_rad", "nc120"),
                       ("full120_rad", "full120"), ("full240_rad", "full240"),
                       ("static_max_rad", "static_max"), ("live_rad", "live_pier")]:
        actual = native_num(f"BP_{var}_{i} to rad")
        expected = row[field]
        assert math.isclose(actual, expected, abs_tol=1e-12), (field, actual, expected)
        checks.append({"quantity": f"BP_{var}_{i}", "native_rad": actual, "independent_rad": expected})
assert math.isclose(native_num("BP_movement to in"), ind["movement_in"], abs_tol=1e-12)
for name, expected in [("BP_rotation_check", "PASS"), ("BP_opposite_1", "PASS"),
                       ("BP_opposite_2", "PASS"), ("BP_level_seat_result", "LEVEL PIER SEATS - SCREEN PASSES")]:
    found = [c.findtext("textvalue") for c in native.elements[key].iter("c") if c.get("formula") == name]
    assert found == [expected], (name, found)

# Keep the original module bytes outside the addition, avoiding unrelated native normalization.
# Take only the actual recalculated inserted section from the native report. Its table
# caches are native, and original report formulas/caches remain byte exact.
native_report = native.part(key)
start = native_report.index(b'<section name="PierLevelSeatCheck"')
el = native.elements[key].find('.//section[@name="PierLevelSeatCheck"]')
# Locate matching section boundary with XML streaming offsets via a local depth scanner.
import re
depth = 0
end = None
for match in re.finditer(rb'<(/?)section\b[^>]*>', native_report[start:]):
    if match.group(1):
        depth -= 1
    elif not match.group(0).endswith(b'/>'):
        depth += 1
    if depth == 0:
        end = start + match.end()
        break
assert end is not None
new_section = native_report[start:end]
E.fromstring(new_section)
auth_report = auth.part(key)
astart = auth_report.index(b'<section name="PierLevelSeatCheck"')
depth = 0
for match in re.finditer(rb'<(/?)section\b[^>]*>', auth_report[astart:]):
    depth += -1 if match.group(1) else (0 if match.group(0).endswith(b'/>') else 1)
    if depth == 0:
        aend = astart + match.end()
        break
merged_report = auth_report[:astart] + new_section + auth_report[aend:]
merged = Journal(base.replace({key: merged_report}))
assert merged.shell == base.shell and merged.order == base.order
assert all(merged.part(k) == base.part(k) for k in base.order if k != key)
assert not list(merged.root.iter("error"))
assert authored(merged.elements[key]) == authored(auth.elements[key])
_, report = check(ROOT, "T019", merged.data)
(TASK / "working.bpad").write_bytes(merged.data)
evidence = {
    "base_sha256": base.sha256, "authored_sha256": auth.sha256,
    "native_save_sha256": native.sha256, "candidate_sha256": merged.sha256,
    "native_actions": "Blockpad Formulas > Update All, File > Save, 20 October 2026.",
    "native_recalculation": True, "native_visual_review": False,
    "new_section_matches_native_save_exactly": True,
    "authored_content_preserved": True, "original_formulas_and_caches_preserved": True,
    "protected_components_byte_exact": len(base.order) - 1,
    "stored_errors": 0, "rotation_comparisons": checks,
    "movement_native_in": native_num("BP_movement to in"),
    "independent_movement_in": ind["movement_in"],
    "engineering_acceptance": "Not performed; conditional screen and all inherited findings retained.",
}
(TASK / "native-verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
submission = {
    "summary": "Add a natively recalculated conditional pier level-seat rotation/movement check within Bearing Pads; correct the existing SPI link.",
    "published_outputs": ["BearingDesign.BP_level_seat_result", "BP_static_max", "BP_cyclic_max", "BP_movement"],
    "assumptions_and_conventions": [
        "Saved selected Mathcad end slopes, not a new beam solver run; exact source hashes recorded.",
        "Positive slope rises with station; Span 1 pier is the right end, Span 2 pier is the left end.",
        "Zero transverse beam tilt; full-unit thermal movement and both full bottom shortenings form a conservative bound."
    ],
    "downstream_impact": ["Supports level pier seat detailing subject to stated conditions; geometry and end-bent approval unchanged."],
    "external_analysis": "Mathcad and FBMP were not rerun. Beam source currency/load reconciliation, combined lateral shear and uplift/contact remain outside the accepted check.",
    "checks_performed": ["FDOT primary-source verification", "Exact external input extraction and provenance",
                         "Independent rotation/movement arithmetic", "Native Blockpad recalculation",
                         "Native numeric cache comparison", "Original formulas/caches and protected bytes preserved",
                         "Scope/dependency/reference checks"],
    "open_items": ["Final combined bearing actions and support/plate details", "External beam-analysis currency and load reconciliation",
                   "Transverse zero-tilt detailing assumption", "Separate end-bent seat checks", "Native pagination/appearance not fully reviewed"]
}
(TASK / "submission.json").write_text(json.dumps(submission, indent=2) + "\n")
print(json.dumps({"candidate_sha256": merged.sha256, "native_comparisons": len(checks),
                  "movement_in": native_num("BP_movement to in"), "stored_errors": 0}, indent=2))
