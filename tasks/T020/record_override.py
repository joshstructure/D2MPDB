"""Record D-064 in a bounded journal task without changing existing calculations."""
import hashlib
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal

base = Journal.load(TASK / "base.bpad")
assert base.sha256 == "515256c187b7cac03afb47c6f92153441fdbb441ac6ef55799104ea85405de05"
key = "report:BearingDesign"
raw = base.part(key)
assert b'PierLevelSeatOverride' not in raw
check_start = raw.index(b'<section name="PierLevelSeatCheck"')
depth = 0
for match in re.finditer(rb'<(/?)section\b[^>]*>', raw[check_start:]):
    depth += -1 if match[1] else (0 if match[0].endswith(b"/>") else 1)
    if depth == 0:
        check_end = check_start + match.end()
        break
else:
    raise AssertionError("Missing existing calculation boundary")

parts = ['<section name="PierLevelSeatOverride" capture="False" hide="false">',
         '<heading level="2">Adopted override D-064: level pier pedestal tops</heading>']
fmt = 'fontfamily="Times New Roman" fontsize="11" spacingafter="7"'

def paragraph(text):
    parts.append(f'<paragraph {fmt}>{escape(text)}</paragraph>')

definitions = {
    "BP_pier_seat_override": '"D-064: ADOPT LEVEL PIER PEDESTAL TOPS"',
    "BP_pier_seat_longitudinal_slope": "0",
    "BP_pier_seat_transverse_slope": "0",
    "BP_pier_seat_override_scope": '"Pier only: two pedestals serving bearings B1/B2 and B3/B4"',
    "BP_pier_seat_override_basis": '"T019 / D-063: BearingDesign.PierLevelSeatCheck; conditional on its live checks and stated assumptions"',
    "BP_pier_seat_geometry_status": '"PENDING IMPLEMENTATION: bridge geometry notebook, B4 geometry tables, CAD and drawings"',
    "BP_pier_seat_elevation_status": '"No new numeric top elevation selected; reconcile one common top elevation per pedestal and pad/beam interfaces in the geometry update"',
}

def definition(name, caption):
    formula = f"{name} = {definitions[name]}"
    parts.append(f'<paragraph {fmt}><dynexp formula={quoteattr(formula)} '
                 f'mathlayout="on" showsteps="False"><expbody>{escape(formula)}'
                 '</expbody></dynexp></paragraph>')
    paragraph(caption)

paragraph("Adopted by user direction on 20 October 2026. Record this exception in the journal and carry it into the design atlas. It changes the design direction for the pier pedestal tops; this documentary update does not modify the geometry files.")
definition("BP_pier_seat_override", "Design decision: detail each pier pedestal top as one horizontal plane, including both bearing areas and the intervening top surface.")
definition("BP_pier_seat_longitudinal_slope", "Adopted longitudinal rise/run = 0, equivalent to 0%.")
definition("BP_pier_seat_transverse_slope", "Adopted transverse rise/run = 0, equivalent to 0%; maintain the zero transverse beam-tilt assumption of the bearing check.")
definition("BP_pier_seat_override_scope", "Apply to the two pier pedestals and all four pier bearings. End-bent pedestal elevations and slopes are outside this override.")
definition("BP_pier_seat_override_basis", "The preceding native rotation and longitudinal movement calculation remains the calculation authority. Standard Type F pads accommodate the checked beam rotations; this decision does not introduce a tapered pad or establish final combined bearing adequacy.")
paragraph("Constructability basis: replace the small calculated pier seat slopes with level tops under the level-seat allowance evaluated in the preceding check. The adopted zero slopes supersede the calculated sloped pier-top geometry for detailing. This is a recorded engineering exception, not a change to the bridge profile, beam camber or source analysis.")
definition("BP_pier_seat_geometry_status", "The existing Bridge_Geometry_2 Beam_V2.ipynb and B4_Geometry_CAD_Tables.xlsx still contain the calculated sloped seats. Retain them as source evidence until a coordinated update applies this override; the atlas must show the adoption separately from implementation status.")
definition("BP_pier_seat_elevation_status", "When implementing, reconcile the pedestal elevation schedule to a common top plane for each pedestal and verify pad thickness, beam seating, cap geometry, reinforcement cover and clearances. No existing sloped corner elevation is silently reclassified as an adopted level elevation.")
paragraph("Applicability and remaining checks: retain the selected saved beam-design results, standard pad construction and zero transverse beam tilt used in T019. Recheck after changes to grade, camber/end rotations, loads, pad geometry or support details. Combined wind/lateral shear, uplift/contact, external-analysis currency/load reconciliation and final support/plate detailing remain open. No end-bent approval or final bearing acceptance is recorded here.")
parts.append('</section>')
addition = ("\r\n" + "\r\n".join(parts)).encode("utf-8")
updated = raw[:check_end] + addition + raw[check_end:]
assert updated.replace(addition, b"", 1) == raw
candidate = Journal(base.replace({key: updated}))
assert candidate.shell == base.shell and candidate.order == base.order
assert all(candidate.part(k) == base.part(k) for k in base.order if k != key)
assert len(list(candidate.root.iter("error"))) == len(list(base.root.iter("error"))) == 0
assert len(list(candidate.root.iter("dynexp"))) == len(list(base.root.iter("dynexp"))) + len(definitions)
for name in definitions:
    assert sum(1 for x in candidate.root.iter("dynexp")
               if x.get("formula", "").startswith(name + " = ")) == 1
(TASK / "working.bpad").write_bytes(candidate.data)
(TASK / "override-section.xml").write_bytes(addition.strip())
protected = {}
for rel in [
    "Bridge_Geometry_2 Beam_V2.ipynb",
    "project_current/geometry/tables/B4_Geometry_CAD_Tables.xlsx",
    "project_current/geometry/freecad/B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd",
    "project_current/coherence/Coherence_Tracker.xlsx",
]:
    protected[rel] = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
evidence = {
    "task": "T020", "decision": "D-064", "date": "2026-10-20",
    "base_sha256": base.sha256, "candidate_sha256": candidate.sha256,
    "changed_component": key, "protected_components_byte_exact": len(base.order) - 1,
    "original_report_restored_by_removing_addition": True,
    "existing_formulas_and_caches_byte_exact": True,
    "new_literal_design_definitions": definitions, "new_stored_errors": 0,
    "native_recalculation": False, "native_visual_review": False,
    "engineering_review": False, "geometry_implementation": "pending",
    "protected_files_sha256": protected,
    "calculation_basis": {
        "task": "T019",
        "native_verification_sha256": hashlib.sha256((ROOT / "tasks/T019/native-verification.json").read_bytes()).hexdigest(),
        "independent_check_sha256": hashlib.sha256((ROOT / "tasks/T019/independent-check.json").read_bytes()).hexdigest(),
    },
}
(TASK / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
submission = {
    "summary": "Record user-adopted D-064 level pier pedestal tops under Bearing Pads; explicitly distinguish adopted slopes from pending geometry implementation.",
    "published_outputs": ["BearingDesign." + n for n in definitions],
    "assumptions_and_conventions": ["Zero rise/run in both directions; pier only.", "No new top elevation selected; geometry files remain unchanged.", "Existing T019 live checks and limitations govern applicability."],
    "downstream_impact": ["Notebook, B4 CAD table, native CAD model and drawings require coordinated implementation and elevation/interface reconciliation."],
    "external_analysis": "No external rerun. Inherit T019 selected saved analysis and all its unresolved conditions; no final bearing acceptance.",
    "checks_performed": ["Exact-byte preservation of all existing journal content", "Unique literal definitions and no new stored errors", "Protected geometry/workbook fingerprints"],
    "open_items": ["Geometry implementation and final elevation reconciliation", "T019 combined shear, uplift/contact, source/load reconciliation and final details", "Native appearance and engineering review not performed for this documentary addition"],
}
(TASK / "submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"candidate_sha256": candidate.sha256, "protected_components": len(base.order) - 1, "new_definitions": len(definitions)}, indent=2))
