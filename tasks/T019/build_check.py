"""Bounded native Bearing Pads addition; source results retain explicit provenance."""
import hashlib
import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal

NS = {"w": "http://schemas.mathsoft.com/worksheet30", "m": "http://schemas.mathsoft.com/math30"}
SHA = ["a6b0f967d271c193591d477e219ac66f98b72309d19958a04c6cd08e575a8dcd",
       "182e3471f169d3a379c437ad12f359d567813bd4631bcc0b82e78ad860fa91b8"]
sources = []
for i in (1, 2):
    p = ROOT / f"project_current/mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span{i}.xmcd"
    data = p.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == SHA[i - 1]
    tree = E.fromstring(data)
    matrix = tree.find('.//w:region[@region-id="202056"]//m:result/m:matrix', NS)
    assert matrix.attrib == {"rows": "10", "cols": "5"}
    cells = list(matrix)
    assert cells[30].text == "Slope at End (deg)"
    assert cells[20].text == "ΔL @ Beam Bot. (in)"
    vals = {k: float(cells[j].text) for k, j in {
        "release_deg": 31, "day30_deg": 32, "day60_deg": 33, "day90_deg": 34,
        "day120_deg": 35, "day240_deg": 36, "nc_deg": 37, "comp_deg": 38,
        "live_deg": 39, "bottom120_in": 25, "bottom240_in": 26}.items()}
    assert vals["release_deg"] < vals["day30_deg"] < vals["day60_deg"] < vals["day90_deg"] < vals["day120_deg"] < vals["day240_deg"]
    assert vals["nc_deg"] < 0 and vals["comp_deg"] < 0 and vals["live_deg"] < 0
    net = tree.find('.//w:region[@region-id="202051"]//m:result//m:real', NS)
    vals["net_camber_in"] = float(net.text)
    sources.append({"path": p.relative_to(ROOT).as_posix(), "sha256": digest,
                    "matrix_region": "202056", "matrix_storage": "column-major",
                    "native_recalculation": False, "values": vals})

base = Journal.load(TASK / "base.bpad")
key = "report:BearingDesign"
raw = base.part(key).decode("utf-8")
assert "BP_static_limit" not in raw
NL = "\r\n" if "\r\n" in raw else "\n"
parts = []
defs = []
fmt = 'fontfamily="Times New Roman" fontsize="11"'

def p(text, **attrs):
    a = " ".join(f"{k}={quoteattr(str(v))}" for k, v in attrs.items())
    parts.append(f'<paragraph {fmt} spacingafter="5" {a}>{escape(text)}</paragraph>')

def link(url, text):
    parts.append(f'<paragraph {fmt} spacingafter="5"><link address={quoteattr(url)}>{escape(text)}</link></paragraph>')

def eq(formula, caption):
    defs.append(formula)
    parts.append(f'<paragraph {fmt} spacingbefore="5" spacingafter="0" keepwithnext="True"><dynexp formula={quoteattr(formula)} mathlayout="on" showsteps="False"><expbody>{escape(formula)}</expbody></dynexp></paragraph>')
    p(caption, fontweight="bold")

def table(name, heads, rows, widths, digits=6):
    last = chr(64 + len(heads))
    parts.append(f'<embed spacingbefore="8" spacingafter="10"><table name="{name}" capture="False" colwidths="{widths}">')
    parts.append(f'<stylerule range="A1:{last}{len(rows)+1}" {fmt} fontsizeXXX="11" valueformat="RoundedNumber({digits}, {digits}, {{PriorityUnits: []}})" border="Border(&quot;AllSides&quot;, &quot;Solid&quot;, 0.6, &quot;#7189A6&quot;);" />'.replace(' fontsizeXXX="11"', ''))
    parts.append(f'<stylerule range="A1:{last}1" fontweight="bold" background="#DCE7F3" />')
    parts.append("<row>" + "".join(f'<c capture="False"><textvalue>{escape(x)}</textvalue></c>' for x in heads) + "</row>")
    for row in rows:
        parts.append("<row>")
        for x in row:
            if isinstance(x, tuple):
                parts.append(f'<c capture="False" formula={quoteattr(x[0])} />')
            else:
                parts.append(f'<c capture="False"><textvalue>{escape(x)}</textvalue></c>')
        parts.append("</row>")
    parts.append("</table></embed>")

parts.append('<section name="PierLevelSeatCheck" capture="False" hide="false">')
parts.append('<heading level="2">Level pier bearing seats — rotation check</heading>')
p("Evaluate level tops at the four pier bearings, B1/B2 for Span 1 and B3/B4 for Span 2. This check uses the selected Type F pads and the saved beam-end rotations. It does not change pedestal geometry or approve the end-bent seats.")
link("https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/design/standardplans/2027/spi/spi-400-510.pdf",
     "FDOT SPI 400-510, FY 2026–27, pp. 1–2 — Type F limits and level-seat allowance")
link("https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/structures/structuresmanual/currentrelease/2026/2026-fdot-structures-manual.pdf",
     "FDOT Structures Design Guidelines, January 2026, §6.5.1.D — bearing seats and rotations")
p("SDG's general detailing rule uses level seats below 0.5% grade and seats parallel to the beam from 0.5% to 2%. SPI 400-510 additionally permits level seats where the combined grade, camber and dead-load rotation remains within its static limit. The specific combined-rotation allowance is evaluated here. No beveled plate is required by the longitudinal grade alone; the standard embedded beam plate remains part of the beam detail.")
table("BPContext", ["Item", "Basis"], [
    ["Objective", "Determine whether the selected pads can accommodate level pier seats."],
    ["Inputs", "Live profile/pad/thermal inputs and selected Mathcad saved end rotations."],
    ["Output", "Pier rotation, direction and longitudinal movement screens; explicit remaining checks."]],
    "1:85, 2:435", 3)
p("Positive beam slope rises with increasing station. Saved Mathcad camber slopes are positive at the left end; downward DL/LL slopes are negative. Reverse their signs at the right end of Span 1 (pier); retain them at the left end of Span 2 (pier). Beam self-weight is already included in the camber result. The 2% deck crossfall is taken in the haunch; transverse beam tilt is assumed zero and must be maintained in detailing.")
p("The selected 12 October 2026 Span 1/Span 2 Mathcad worksheets supply Slope&Defl, region 202056, in degrees and inches. These are saved external analysis results, not a new native Mathcad run. Exact fingerprints and independent arithmetic are retained with task T019. Refresh these source inputs if either beam analysis changes. Direct end rotations govern; 4 × net midspan camber / span would discard the actual curvature distribution.")
for i, s in enumerate(sources, 1):
    p(f"Span {i}: {Path(s['path']).name}; SHA-256 {s['sha256']}.", fontsizeXXX="9")
# Remove the extra authoring attribute, retaining the established font size.
parts = [s.replace(' fontsizeXXX="9"', '') for s in parts]

p("1. Source inputs and limits", fontweight="bold", textcolor="#1766A0", keepwithnext="True")
eq("BP_static_limit = 0.0125 rad", "SPI maximum static rotation for the standard pad.")
eq("BP_cyclic_limit = 0.004 rad", "SPI maximum cyclic rotation, opposite the static rotation.")
eq("BP_transverse_slope = 0", "Detailing assumption: level beam bottom across the pad width.")
parts.append('<section name="BPSourceInputs" capture="False" hide="true">')
for i, source in enumerate(sources, 1):
    for field, caption in [
        ("release_deg", "Bare-beam release end slope, including beam self-weight"),
        ("day120_deg", "Bare-beam 120-day end slope, including beam self-weight"),
        ("day240_deg", "Bare-beam 240-day end slope, including beam self-weight"),
        ("nc_deg", "Superimposed noncomposite dead-load end rotation"),
        ("comp_deg", "Composite dead-load end rotation"),
        ("live_deg", "Full-span pedestrian live-load end rotation"),
        ("bottom120_in", "Bottom-fiber shortening at 120 days"),
        ("bottom240_in", "Bottom-fiber shortening at 240 days")]:
        unit = "deg" if field.endswith("_deg") else "in"
        name = field.rsplit("_", 1)[0]
        eq(f"BP_{name}_{i} = {source['values'][field]:.17g} {unit}", f"Span {i}: {caption}; saved Mathcad result.")
parts.append("</section>")
table("BPSavedInputs", ["Saved beam result", "Span 1", "Span 2"], [
    [label, (f"BP_{name}_1 to {unit}",), (f"BP_{name}_2 to {unit}",)]
    for name, label, unit in [
        ("release", "Release camber slope (deg)", "deg"),
        ("day120", "120-day camber slope (deg)", "deg"),
        ("day240", "240-day camber slope (deg)", "deg"),
        ("nc", "Noncomposite DL rotation (deg)", "deg"),
        ("comp", "Composite DL rotation (deg)", "deg"),
        ("live", "Pedestrian LL rotation (deg)", "deg")]],
    "1:260, 2:130, 3:130")

p("2. Signed pier rotations and stage envelope", fontweight="bold", textcolor="#1766A0", keepwithnext="True")
eq("BP_grade_1 = (BridgeGeometry_2Beam.PGL_pier_elev-BridgeGeometry_2Beam.PGL_start_elev)/BridgeGeometry_2Beam.Span_1",
   "Span 1 profile grade, using the shared profile elevations and station span.")
eq("BP_grade_2 = (BridgeGeometry_2Beam.PGL_end_elev-BridgeGeometry_2Beam.PGL_pier_elev)/BridgeGeometry_2Beam.Span_2",
   "Span 2 profile grade; negative toward End Bent 2.")
eq("BP_angle_1 = Atan(BP_grade_1) to rad", "Span 1 profile angle at a level seat.")
eq("BP_angle_2 = Atan(BP_grade_2) to rad", "Span 2 profile angle at a level seat.")
parts.append('<section name="BPStageEquations" capture="False" hide="true">')
for i, sign in [(1, "-"), (2, "+")]:
    for stage, val, caption in [
        ("bare120", f"BP_day120_{i}", "120-day bare beam"),
        ("nc120", f"BP_day120_{i}+BP_nc_{i}", "120-day beam with noncomposite DL"),
        ("full120", f"BP_day120_{i}+BP_nc_{i}+BP_comp_{i}", "120-day full static service state"),
        ("full240", f"BP_day240_{i}+BP_nc_{i}+BP_comp_{i}", "240-day full static service state"),
        ("bare240", f"BP_day240_{i}", "240-day bare beam bounding case"),
        ("release_full", f"BP_release_{i}+BP_nc_{i}+BP_comp_{i}", "Release camber with full DL bounding case")]:
        eq(f"BP_{stage}_{i} = BP_angle_{i}{sign}({val}) to rad", f"Span {i} at pier: {caption}.")
    eq(f"BP_static_max_{i} = Max(Abs(BP_bare240_{i}),Abs(BP_release_full_{i})) to rad",
       f"Span {i}: conservative envelope over release–240-day camber and zero–full superimposed DL.")
    eq(f"BP_live_pier_{i} = {'-' if i == 1 else ''}BP_live_{i} to rad", f"Span {i}: signed cyclic rotation at the pier.")
    eq(f'BP_opposite_{i} = If(And(BP_full120_{i}*BP_live_pier_{i} <= 0 rad^2,BP_full240_{i}*BP_live_pier_{i} <= 0 rad^2),"PASS","REVIEW DIRECTION")',
       f"Span {i}: check live load opposes both 120-day and 240-day full-static rotations.")
parts.append("</section>")
p("Bare camber increases monotonically in the saved release, 30, 60, 90, 120 and 240-day results. The envelope includes the most adverse corners of that camber range and zero–full superimposed DL, even where the paired stages are not simultaneous construction cases. Service direction checks use the actual full-static combinations at 120 and 240 days.")
table("BPStageResults", ["Signed rotation (rad)", "Span 1 at pier", "Span 2 at pier"], [
    [label, (f"BP_{name}_1 to rad",), (f"BP_{name}_2 to rad",)]
    for name, label in [
        ("bare120", "120-day bare beam"), ("nc120", "120-day + noncomposite DL"),
        ("full120", "120-day + all static DL"), ("full240", "240-day + all static DL"),
        ("static_max", "Absolute static envelope"), ("live_pier", "Cyclic pedestrian LL")]],
    "1:260, 2:130, 3:130")
eq("BP_static_max = Max(BP_static_max_1,BP_static_max_2) to rad", "Governing static rotation at the four pier bearings.")
eq("BP_cyclic_max = Max(Abs(BP_live_pier_1),Abs(BP_live_pier_2)) to rad", "Governing cyclic rotation magnitude.")
eq("BP_static_ratio = BP_static_max/BP_static_limit", "Static rotation demand / limit.")
eq("BP_cyclic_ratio = BP_cyclic_max/BP_cyclic_limit", "Cyclic rotation demand / limit.")
eq("BP_transverse_difference = Abs(BP_transverse_slope)*BridgeGeometry_2Beam.Bearing_pad_width to in", "Transverse height difference across the pad; SDG detailing trigger is 1/8 in.")
eq('BP_rotation_check = If(And(BP_static_ratio <= 1,BP_cyclic_ratio <= 1,BP_opposite_1 == "PASS",BP_opposite_2 == "PASS",BP_transverse_difference < 1/8 in),"PASS","REVIEW")',
   "Pier level-seat rotation screen, including the standard's cyclic-direction assumption.")

p("3. Longitudinal movement screen and disposition", fontweight="bold", textcolor="#1766A0", keepwithnext="True")
eq("BP_thermal = BridgeMovement.α_T*0.65*(BridgeMovement.T_high-BridgeMovement.T_low)*BridgeGeometry_2Beam.TotalSpan to in",
   "SPI thermal movement using the entire bridge length at one pad as a conservative bound; no 1.20 TU factor.")
eq("BP_creep = Abs(BP_bottom240_1-BP_bottom120_1)+Abs(BP_bottom240_2-BP_bottom120_2) to in",
   "Conservative sum of both full bottom-fiber creep/shrinkage shortenings from 120 to 240 days.")
eq("BP_movement = BP_thermal+BP_creep to in", "Longitudinal thermal plus creep/shrinkage movement bound.")
eq("BP_movement_ratio = BP_movement/BridgeGeometry_2Beam.Bearing_pad_shearLimit", "Longitudinal movement demand / selected Type F shear-deflection limit.")
eq('BP_movement_check = If(BP_movement_ratio <= 1,"PASS","FAIL")', "Thermal/creep movement screen; wind-induced or other lateral shear is additional.")
eq('BP_type_check = If(And(BridgeGeometry_2Beam.Bearing_pad_type == "F",BridgeGeometry_2Beam.Bearing_pad_G == 110 psi,BridgeGeometry_2Beam.Bearing_pad_length == 10 in,BridgeGeometry_2Beam.Bearing_pad_width == 32 in,BridgeGeometry_2Beam.Bearing_pad_thickness == 2.5625 in,BridgeGeometry_2Beam.Bearing_pad_skew == 0 deg),"PASS","REVIEW PAD")',
   "Confirm the pad selection and orientation used by this check.")
eq('BP_level_seat_result = If(And(BP_type_check == "PASS",BP_rotation_check == "PASS",BP_movement_check == "PASS",Check_TypeF_B1 == "✓ PASS",Check_TypeF_B2 == "✓ PASS",Check_TypeF_B3 == "✓ PASS",Check_TypeF_B4 == "✓ PASS"),"LEVEL PIER SEATS - SCREEN PASSES","LEVEL PIER SEATS - REVIEW REQUIRED")',
   "Conditional seat-slope disposition for the selected saved beam results and stated transverse assumption.")
table("BPCheckSummary", ["Check", "Demand", "Limit / result"], [
    ["Static rotation (rad)", ("BP_static_max to rad",), ("BP_static_limit to rad",)],
    ["Cyclic rotation (rad)", ("BP_cyclic_max to rad",), ("BP_cyclic_limit to rad",)],
    ["Span 1 cyclic direction", ("BP_opposite_1",), "Opposite static"],
    ["Span 2 cyclic direction", ("BP_opposite_2",), "Opposite static"],
    ["Thermal + creep (in)", ("BP_movement to in",), ("BridgeGeometry_2Beam.Bearing_pad_shearLimit to in",)],
    ["Pier seat rotation", ("BP_rotation_check",), "SPI 400-510"],
    ["Disposition", ("BP_level_seat_result",), "Conditional screen"]],
    "1:180, 2:220, 3:120")
p("Level longitudinal pier seats satisfy the checks when the live disposition above passes. This is conditional on the selected saved beam-design results, level transverse beam bottoms and the existing standard pad construction. Span 1's 120-day static slope is close to zero; confirm the rotation sign after any grade or beam-analysis revision. Native beam-analysis currency and current load reconciliation remain open. Complete combined wind/lateral shear, uplift/contact and final support/plate detailing before final bearing acceptance. The movement screen alone does not establish combined shear adequacy.")
p("The same conclusion is not extended to the end bents: the beam grade adds to upward camber there, whereas it partially cancels camber at this pier. Retain separate end-bent checks.")
parts.append("</section>")
block = (NL + "        ").join(parts)
anchor = '            <paragraph fontfamily="Times New Roman" fontsize="11" spacingafter="5">Design scope: the Type F gravity screening'
assert raw.count(anchor) == 1
updated = raw.replace(anchor, "        " + block + NL + anchor)
# Correct an existing link whose label says SPI but whose destination was the drawing.
old = '<link address="https://fdotwww.blob.core.windows.net/sitefinity/docs/default-source/design/standardplans/2027/idx/400-510.pdf">FDOT SPI 400-510'
new = old.replace('/idx/', '/spi/').replace('/400-510.pdf', '/spi-400-510.pdf')
assert updated.count(old) == 1
updated = updated.replace(old, new)
E.fromstring(updated.encode())
mapping = json.loads((TASK / "components.json").read_text())
(TASK / "components" / mapping[key]).write_bytes(updated.encode())
(TASK / "source-results.json").write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
(TASK / "definitions.json").write_text(json.dumps(defs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# Independent arithmetic: use actual shared literal profile inputs, not rounded display caches.
bg = base.elements["report:BridgeGeometry_2Beam"]
def literal(name):
    fs = [e.get("formula") for e in bg.iter() if "=" in e.get("formula", "") and e.get("formula", "").split("=")[0].strip() == name]
    assert len(fs) == 1
    return float(fs[0].split("=")[1].strip().split()[0])
l1 = literal("CLPier_station") - literal("BeginBridge_station")
l2 = literal("EndBridge_station") - literal("CLPier_station")
z1, z2 = literal("PGL_start_elev"), literal("PGL_end_elev")
zp = (z1 + literal("PGL_nominalGrade") * l1 + z2 + literal("PGL_nominalGrade") * l2) / 2
grades = [(zp - z1) / l1, (z2 - zp) / l2]
checks = []
for i, (s, g, sense) in enumerate(zip(sources, grades, [-1, 1]), 1):
    v = s["values"]
    a = math.atan(g)
    def rot(c, dl=0):
        return a + sense * math.radians(c + dl)
    dl = v["nc_deg"] + v["comp_deg"]
    result = {
        "span": i, "grade": g,
        "bare120_rad": rot(v["day120_deg"]),
        "nc120_rad": rot(v["day120_deg"], v["nc_deg"]),
        "full120_rad": rot(v["day120_deg"], dl),
        "full240_rad": rot(v["day240_deg"], dl),
        "static_max_rad": max(abs(rot(v["day240_deg"])), abs(rot(v["release_deg"], dl))),
        "live_rad": sense * math.radians(v["live_deg"]),
    }
    result["opposite"] = all(result[k] * result["live_rad"] <= 0 for k in ["full120_rad", "full240_rad"])
    checks.append(result)
thermal = 6e-6 * 0.65 * (105 - 35) * (l1 + l2) * 12
creep = sum(abs(s["values"]["bottom240_in"] - s["values"]["bottom120_in"]) for s in sources)
evidence = {
    "base_sha256": base.sha256, "sources": sources, "spans": checks,
    "static_limit_rad": 0.0125, "cyclic_limit_rad": 0.004,
    "thermal_in": thermal, "creep_in": creep, "movement_in": thermal + creep,
    "new_definition_count": len(defs),
    "limits": "Saved Mathcad results, not rerun. Transverse zero-tilt assumption. No combined lateral bearing approval or end-bent approval.",
}
assert max(c["static_max_rad"] for c in checks) <= .0125
assert max(abs(c["live_rad"]) for c in checks) <= .004
assert all(c["opposite"] for c in checks)
assert thermal + creep <= 1
(TASK / "independent-check.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"definitions": len(defs), "spans": checks, "movement_in": thermal + creep}, indent=2))
