"""T016: write the eight registered component files from base.bpad (rerunnable, byte-surgical).

Journal coherence with the 19 October 2026 calculations and CAD model. Existing components are
edited by exact-substring surgery (every anchor must occur exactly the stated number of times);
nothing is re-serialized. Line endings are kept as found (CRLF). Every refreshed cached value
comes from an evaluator that first reproduces the current caches it is asked to refresh:
tasks/T014/geom_eval.py is not needed here; the MSE module uses tasks/T016/mse_eval.py and
the two cap-volume cells of FBMPEndBent take the values already cached in BridgeGeometry_2Beam.

    build_components.py          rebuild tasks/T016/components/*.xml and definitions.json
"""
import hashlib
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TASK))
from tools.bpad_workflow import Journal  # noqa: E402
import mse_eval as M  # noqa: E402

NBSP = " "
TODAY = "19 October 2026"

# --- project record identities (project_current/source_register.csv, decisions D-049, D-051, D-054, D-055) ---
XML = {"EB1": ("End Bent 1_Fixed.XML", "c1a4afa138865b3f10cc968ce7daef767a4d96e8bc2ccf175c1a5ebd150d912d"),
       "EB2": ("End Bent 2_Fixed.XML", "3543df298b92593ce9bac14f9228ffacf5b0ce7e76b5e1d887ae228ef811a90e"),
       "PIER": ("Pier_Fixed.XML", "bb73e6ada6cf35ebb80b512cee315075807fc8ccab7878406d81ff381ae40fe7")}
REPORT = {"EB1": ("End Bent 1 Cap Design 10-19.html", "6a42c16b0595ac16070608abd5d129a6152803693cb06a870b3168685c52e7a1"),
          "EB2": ("End Bent 2 Cap Design 10-19.html", "3405297e0d4c410b28be90f86f4fbcee1f3ea7db065e2851377a9435a6425605"),
          "PIER": ("Pier Cap Design 10-19.html", "e49d579c0186e7c2617828d236cb982adb92122345493a097e7c352df2f3a701")}
PILE_REPORT = {"EB1": ("End Bent 1 Pile Design 10-19.html", "470bc14a2027d66e25e298080aa3482bf6ca92d37ab8fd716167ce69ff570e42"),
               "EB2": ("End Bent 2 Pile Design 10-19.html", "e9d0253756825f015971a3d54645ba66a4d6b2538faf76daa8e1ced403947591"),
               "PIER": ("Pier Pile Design 10-19.html", "e3880f74db02b4bc997a4efc92688d6b8439360f3cf116c830a8cb0de1701a59")}
OLD_PIER_REPORT_SHA = "7a9f48ce08bdc29f22a1b6717432dc363f0c2d8cec02ffbfc0a36bb7da39dee2"
OLD_PIER_XML_SHA = "a992aa331e11b4eb9bc426a3f811938a8f71b22b3300bae3431eb2931eaff9d8"
OLD_EB_REPORT_SHA = "42120857965352febea29e4a672b2ba93f45199430360a89f8e1e529d2df50ef"
OLD_EB_XML_SHA = "739f44c1d542464cfd536493ce1ed6cb240f98a75ed3e1188c6f6812742d6fe2"
CAD_SHA = "d0f053d5104498b984a7bf32cbcda6c594af65e0bd0aee9b29d36f828a7a81df"      # D-055 model
OLD_CAD_SHA = "7368774487c1456238df13c80e33ddf3871907982ff91938e1ae1b4eebf52676"  # 13 October snapshot
# 19 October 2026 End Bent 1 case (D-051, selected_case.json inputs; same governing members as 8 October)
EB1_FORCES = {"Mu_N": "79.30", "Mu_P": "67.16", "Mu_B": "182.09", "Vu_G": "91.77", "Tu": "3.09", "MI": "53.30 / 49.33 / 138.47"}
CAMBER_1, CAMBER_2 = "0.124592744006574", "0.5671714630550072"
BACKWALL_DROP = "4.25"      # notebook CONFIG end_bents.*.backwall_drop_in (D-053)

TNR = "Times New Roman"
KEYS = ["BridgeGeometry_2Beam", "DecisionLog", "FBMPEndBent", "FBMPPier", "FoundationModeling", "MSEWallExclusion", "PedBridge", "PileProperties"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(text, old, label, n=1):
    found = text.count(old)
    assert found == n, f"{label}: expected {n} occurrence(s), found {found}: {old[:100]!r}"


def rep(text, old, new, label, n=1):
    once(text, old, label, n)
    return text.replace(old, new)


def nl_of(text, label):
    nl = "\r\n" if "\r\n" in text else "\n"
    if nl == "\r\n":
        assert text.count("\n") == text.count("\r\n"), f"{label}: mixed line endings"
    return nl


def attr(s):
    return escape(s, {'"': "&quot;"})


base = Journal.load(TASK / "base.bpad")
mapping = json.loads((TASK / "components.json").read_text(encoding="utf-8"))
assert {k.split(":", 1)[1] for k in mapping} == set(KEYS) and len(mapping) == 8, "unexpected component keys"


def part(name):
    return base.part(f"report:{name}").decode("utf-8")


edits = []          # every changed formula / link / text, for definitions.json
cache_log = []      # every refreshed cache: report, name/cell, was, now


def para(indent, text, size="11", after="7", **extra):
    a = "".join(f' {k}="{v}"' for k, v in extra.items())
    return f'{" " * indent}<paragraph fontfamily="{TNR}" fontsize="{size}" leftindent="0" spacingafter="{after}"{a}>{escape(text)}</paragraph>'


def link_para(indent, address, text):
    i = " " * indent
    return [f'{i}<paragraph fontfamily="{TNR}" fontsize="10" leftindent="0" spacingafter="7">',
            f'{i}    <link address="{attr(address)}">{escape(text)}</link>', f"{i}</paragraph>"]


def amber_par(indent, formula, caption, amber=True, cache=None):
    """Input/derived definition + caption in the BridgeGeometry_2Beam layout (as T014)."""
    i = " " * indent
    style = ' style="Required Input"' if amber else ""
    lines = [f'{i}<paragraph fontfamily="{TNR}" fontsize="11" leftindent="0" spacingafter="2" spacingbefore="4" keepwithnext="True">',
             f'{i}    <dynexp formula="{attr(formula)}" mathlayout="on" showsteps="False" seplines="False"{style}>',
             f'{i}        <expbody>{escape(formula)}</expbody>']
    if cache is not None:
        lines.append(f"{i}        <expresult>{NBSP}= {cache}</expresult>")
    lines += [f"{i}    </dynexp>", f"{i}</paragraph>",
              f'{i}<paragraph fontfamily="{TNR}" fontsize="10" leftindent="0" spacingafter="7">{escape(caption)}</paragraph>']
    return lines


def section_block(indent, name, heading, paragraphs, links=()):
    i = " " * indent
    lines = [f'{i}<section name="{name}" capture="False" hide="false">',
             f'{i}    <heading level="1" keepwithnext="True">{escape(heading)}</heading>']
    for text in paragraphs:
        lines.append(para(indent + 4, text))
    for address, text in links:
        lines += link_para(indent + 4, address, text)
    lines.append(f"{i}</section>")
    return lines


# ============================================================================================
# 1. BridgeGeometry_2Beam
# ============================================================================================
def edit_geometry():
    global edits
    name = "BridgeGeometry_2Beam"
    text = part(name)
    nl = nl_of(text, name)
    # (a) notebook section heading and basis paragraph
    text = rep(text, "<heading>Coordinated notebook geometry — 29 September 2026</heading>",
               "<heading>Coordinated notebook geometry — 29 September 2026, aligned with the notebook build e9b41b8eaf on 19 October 2026</heading>",
               "notebook heading")
    old = ("Current project basis: Bridge_Geo_2_Beam_Reorganized, intersecting-tangent profile, centered two-beam crowned deck, zero beam raises "
           "and parabolic span cambers.")
    new = ("Current project basis: the geometry notebook Bridge_Geometry_2 Beam_V2.ipynb (model e9b41b8eaf, 19 October 2026; decisions D-036 and "
           "D-053), which supersedes Bridge_Geo_2_Beam_Reorganized as the geometry owner; the CAD model (D-055) and the CAD tables are built from it. "
           "Intersecting-tangent profile, centered two-beam crowned deck, zero beam raises and parabolic span cambers.")
    text = rep(text, old, new, "notebook basis")
    edits.append({"report": name, "text": "NotebookGeometryUpdate20260929 heading and basis paragraph", "change": "names the current notebook build e9b41b8eaf (D-036, D-053) and the CAD model D-055"})
    # (b) haunch caption
    text = rep(text, ">Full bridge haunch volume, 185.8366667 ft³ at the selected notebook inputs. The pier tributary",
               ">Full bridge haunch volume with the notebook build e9b41b8eaf net cambers (the 29 September 2026 snapshot was 185.8366667 ft³ with "
               "the 1-in placeholder cambers). The pier tributary", "haunch caption")
    # (c) Check_notebook_quantity retargeted to the notebook build inputs
    old_f = ('Check_notebook_quantity = If(And(Beam_count == 2, Abs(Deck_area-6.79166666666667 ft^2)<0.000001 ft^2, '
             'Abs(Haunch_totalVolume-185.836666666667 ft^3)<0.000001 ft^3), "MATCHES 2026-09-29 NOTEBOOK", "INPUTS CHANGED - RECONCILE NOTEBOOK")')
    new_f = ('Check_notebook_quantity = If(And(Beam_count == 2, Abs(Deck_area-6.79166666666667 ft^2)<0.000001 ft^2, '
             f'Abs(Beam_camber_1-{CAMBER_1} in)<0.000001 in, Abs(Beam_camber_2-{CAMBER_2} in)<0.000001 in, Abs(Haunch_min-0.5 in)<0.000001 in, '
             'Abs(Beam_topFlange_width-48 in)<0.000001 in), "MATCHES NOTEBOOK BUILD e9b41b8eaf (2026-10-19)", "INPUTS CHANGED - RECONCILE NOTEBOOK")')
    text = rep(text, f'<dynexp formula="{attr(old_f)}"', f'<dynexp formula="{attr(new_f)}"', "Check_notebook_quantity formula")
    text = rep(text, f"<expbody>{escape(old_f)}</expbody>", f"<expbody>{escape(new_f)}</expbody>", "Check_notebook_quantity expbody")
    m = re.search(r"<expresult>([^<]*?)= INPUTS CHANGED - RECONCILE NOTEBOOK</expresult>", text)
    assert m and text.count("= INPUTS CHANGED - RECONCILE NOTEBOOK</expresult>") == 1, "Check_notebook_quantity cache not found once"
    text = text.replace(m.group(0), f"<expresult>{m.group(1)}= MATCHES NOTEBOOK BUILD e9b41b8eaf (2026-10-19)</expresult>")
    # the camber definitions the check compares with
    once(text, f'<expbody>Beam_camber_1 = {CAMBER_1} in</expbody>', "Beam_camber_1 literal")
    once(text, f'<expbody>Beam_camber_2 = {CAMBER_2} in</expbody>', "Beam_camber_2 literal")
    once(text, "<expbody>Haunch_min = 0.5 in</expbody>", "Haunch_min literal")
    once(text, "<expbody>Beam_topFlange_width = 48 in</expbody>", "Beam_topFlange_width literal")
    once(text, "<expbody>Deck_area = Deck_out2out*Thickness_slab_peak to ft^2</expbody>", "Deck_area definition")
    text = rep(text, ">Snapshot reconciliation check. Future input changes",
               ">Snapshot reconciliation check against the geometry notebook build e9b41b8eaf (19 October 2026, D-036): deck area, net cambers, "
               "minimum haunch and flange width, the inputs that drive the haunch volume (that notebook build publishes no haunch volume; the "
               "29 September check compared a notebook haunch volume of 185.8366667 ft³). Future input changes", "Check caption")
    edits.append({"report": name, "formula": new_f, "was": old_f,
                  "change": "snapshot retargeted from the 29 September notebook haunch volume to the e9b41b8eaf build inputs; cache INPUTS CHANGED - RECONCILE NOTEBOOK -> MATCHES NOTEBOOK BUILD e9b41b8eaf (2026-10-19)"})
    cache_log.append({"report": name, "name": "Check_notebook_quantity", "was": "= INPUTS CHANGED - RECONCILE NOTEBOOK", "now": "= MATCHES NOTEBOOK BUILD e9b41b8eaf (2026-10-19)"})
    # (d) analysis-export note in the notebook section
    text = rep(text, "Existing analysis force exports predate the revised 36-in cap and revised deck dead load; regenerate the structural analysis "
                     "forces before final use of the pier cap design (CapDesignPier).",
               "The current analysis force exports are the 19 October 2026 fixed-run FB-MultiPier models (D-049: End Bent 1_Fixed.XML, End Bent "
               "2_Fixed.XML, Pier_Fixed.XML), which model the 36-in caps; the cap design reports (D-051) and pile design reports (D-054) read them. "
               "Their currency against the current haunch dead load, wind heights and the backwall and cheek geometry is not asserted (see Foundation "
               "Modeling, current model sources).", "analysis export note")
    # (e) end-bent geometry basis
    text = rep(text, "Current geometry for both end bents: cap and pile dimensions follow the 8 October 2026 End Bent 1 cap report; applicability to "
                     "both end bents is confirmed by the user.",
               "Current geometry for both end bents: cap and pile dimensions follow the geometry notebook (model e9b41b8eaf, D-036) and the 19 October "
               "2026 fixed-run FB-MultiPier models (D-049: 251-in cap envelope with the 8-in cheek webs, four 18-in square piles at 54-in centers, "
               "44.5 in from each envelope end to the first pile center, 36.5 in from each 235-in cap-body end); applicability to both end bents is "
               "confirmed by the user (D-004), and End Bent 2 has its own export, case and reports since 19 October 2026.", "end-bent geometry basis")
    # (f) pier record
    text = rep(text, "Current pier cap geometry — 9 October 2026</heading>", "Current pier cap geometry — 19 October 2026 (record opened 9 October 2026)</heading>", "pier heading")
    text = rep(text, "Pier Cap Design 10-9.html confirms the existing 48-in by 36-in cap and four 20-in pipe piles at 60-in centers.",
               "Pier Cap Design 10-19.html (D-051, built on the 19 October 2026 fixed-run Pier_Fixed.XML, D-049; previously Pier Cap Design 10-9.html) "
               "confirms the existing 48-in by 36-in cap and four 20-in pipe piles at 60-in centers, 15 in from each outer pile face to the cap end as the "
               "notebook pier.pile_end_clear_in.", "pier paragraph")
    edits += [{"report": name, "text": "NotebookGeometryUpdate20260929 analysis-export note", "change": "D-049 exports named as current; currency not asserted"},
              {"report": name, "text": "EndBentGeometry basis paragraph", "change": "8 October report -> notebook e9b41b8eaf and D-049 models"},
              {"report": name, "text": "PierCurrentGeometry heading and paragraph", "change": "10-9 report -> 10-19 report (D-051) on the D-049 XML"}]
    # (g) backwall top drop (D-053) after the MSE joint input
    joint_caption = (' ' * 12 + f'<paragraph fontfamily="{TNR}" fontsize="10" leftindent="0" spacingafter="7">MSE panel joint to cheek and lug faces; '
                     'notebook CONFIG end_bents.*.mse_joint_in (D-026)</paragraph>')
    formula = f"EndBent_backwallDrop = {BACKWALL_DROP} in"
    block = amber_par(12, formula,
                      "Top of each backwall below the deck-top line at the front face of backwall; the top follows two straight 2% slopes (the deck "
                      "crossfall) down from the PGL and is level across the 12-in thickness; notebook CONFIG end_bents.*.backwall_drop_in (D-053; "
                      "CAD model D-053/D-055). Backwall design and quantities remain separate (16 October 2026 backwall report, D-037).")
    text = rep(text, joint_caption, joint_caption + nl + nl.join(block), "EndBent_mseJoint caption")
    edits.append({"report": name, "formula": formula, "change": "amber input added (notebook backwall drop, D-053)"})
    return text


# ============================================================================================
# 2. FBMPEndBent
# ============================================================================================
def edit_fbmp_endbent():
    global cache_log
    name = "FBMPEndBent"
    text = part(name)
    eb1, eb2 = XML["EB1"], XML["EB2"]
    text = rep(text, "CURRENT MODEL BASIS: the user confirms the cap report contains the latest FBMP model. Loaded nodes are 15 and 34; added model nodes "
                     "changed their numbering. Physical axes, node-line choice, elevation and load-transfer conventions are retained. Both end bents follow "
                     "the controlling End Bent 1 design. The different same-named Downloads XML is not the report source.",
               f"CURRENT MODEL BASIS ({TODAY}): the fixed-run FB-MultiPier exports selected under D-049 are the current end-bent models, {eb1[0]} "
               f"(SHA-256 {eb1[1][:12]}…) and {eb2[0]} (SHA-256 {eb2[1][:12]}…): 251-in cap (the cage envelope with the 8-in cheek webs), four 18-in "
               "square piles at 54-in centers, first pile center 44.5 in from each cap end. The 19 October cap design reports (D-051; "
               "CapDesignEndBentOne, CapDesignEndBentTwo) and pile design reports (D-054; PileDesignEndBentOne, PileDesignEndBentTwo) read these exports. "
               "Loaded nodes 15 and 34 carry the DC, LL, IM, BR and PL node loads in both exports. Physical axes, node-line choice, elevation and "
               "load-transfer conventions are retained. Both end bents share the End Bent 1 geometry and cage (D-004); End Bent 2 has its own export, "
               "case and reports. This entry table is the journal's tributary load set and was not re-derived from the exports.", "CURRENT MODEL BASIS")
    text = rep(text, "Current cap: 42 in wide × 36 in deep × 17 ft 8 in long, linked to Bridge Geometry.",
               "Current cap: 42 in wide × 36 in deep × 19 ft 7 in long (235 in; 251 in over the 8-in cheek webs, as modeled in the D-049 exports), "
               "linked to Bridge Geometry.", "cap self-weight cell")
    text = rep(text, "The cheek-wall quantity remains provisional and is deferred by the user.",
               "The cheek-wall geometry is defined by the geometry notebook and the CAD model (8-in webs, D-036; tops D-053); the cheek-wall quantity "
               "cell below remains the earlier provisional entry until the quantity sheets are updated.", "cheek quantity note")
    text = rep(text, "Cheek-wall geometry and centroid remain deferred. The report analysis has not been rerun by this journal update.",
               "Cheek-wall geometry is defined by the notebook and CAD (D-036, D-053); its quantity and centroid in this entry remain the earlier "
               "provisional values. The analysis was not rerun by this journal update.", "cheek centroid note")
    # design record
    text = rep(text, "Current end-bent cap design record — 8 October 2026</heading>",
               "Current end-bent cap design record — 19 October 2026 (record opened 8 October 2026)</heading>", "record heading")
    text = rep(text, "Block 2 (longitudinal reinforcement) is live from CapDesignEndBentOne, the 19 October 2026 case selected under D-051. Blocks 1 and 3 "
                     "remain the 8 October record pending refresh.",
               "Blocks 1, 2, 5 and 6 record the 19 October 2026 case (D-051, built on the D-049 fixed-run export); block 2 is live from "
               "CapDesignEndBentOne. Block 3 keeps the 8 October transverse schedule as history: the current transverse reinforcement (#6 stirrups, one "
               "closed loop, 9-in pitch) is in CapDesignEndBentOne.", "record note")
    text = rep(text, "Latest model per user: End Bent 1 controls the common design. Independent envelope maxima are not a concurrent action vector.",
               f"{eb1[0]}, the 19 October 2026 fixed-run export (D-049), for this record; End Bent 2 has its own export, case and report "
               "(CapDesignEndBentTwo). Independent envelope maxima are not a concurrent action vector.", "Analysis row")
    text = rep(text, "Original report: 0 failed scalar checks, 48 pending/conditional checks. Current dispositions below exclude Service III and record "
                     "field-adjusted U hooks; source results have not been rerun.",
               "19 October 2026 report (D-051): check ratios refreshed from the D-049 export with no status change versus the 8 October report; the "
               "existing detailing failures and pending checks remain, and CapDesignEndBentOne.Status reads ⊗ There are FAILURES for them. Current "
               "dispositions below exclude Service III and record field-adjusted U hooks.", "Design status row")
    text = rep(text, "End bent 1 Cap Design Report_10-8.html; generated 2026-10-08T15:27:00+00:00.",
               f"{REPORT['EB1'][0]} (D-051; supersedes End bent 1 Cap Design Report_10-8.html of 2026-10-08T15:27:00+00:00).", "Source row")
    text = rep(text, f"Source report SHA-256: {OLD_EB_REPORT_SHA}", f"Source report SHA-256: {REPORT['EB1'][1]} ({REPORT['EB1'][0]})", "report sha")
    text = rep(text, f"Recorded analysis XML SHA-256: {OLD_EB_XML_SHA}",
               f"Recorded analysis XML SHA-256: {eb1[1]} ({eb1[0]}, D-049; {eb2[0]} {eb2[1]})", "xml sha")
    # block 3 (historical)
    text = rep(text, ">3. Actual transverse schedule</heading>", ">3. Transverse schedule — 8 October 2026 record (historical)</heading>", "block 3 heading")
    text = rep(text, ">All stations are inches from the left cap end. Each run uses #4 bars at 6-in pitch,",
               ">Historical 8 October 2026 record; the 19 October 2026 case (CapDesignEndBentOne) uses #6 stirrups, one closed loop, at 9-in pitch. "
               "All stations are inches from the left cap end. Each run of this record uses #4 bars at 6-in pitch,", "block 3 paragraph")
    # block 5 (forces of the 19 October case; same governing members as 8 October)
    text = rep(text, ">5. End Bent 1 analysis snapshot</heading>", ">5. End Bent 1 analysis snapshot — 19 October 2026 case (D-051)</heading>", "block 5 heading")
    for old, new in [("67.13 kip-ft", f"{EB1_FORCES['Mu_N']} kip-ft"), ("75.96 kip-ft", f"{EB1_FORCES['Mu_P']} kip-ft"),
                     ("190.92 kip-ft", f"{EB1_FORCES['Mu_B']} kip-ft"), ("91.79 kip", f"{EB1_FORCES['Vu_G']} kip"),
                     ("2.93 kip-ft", f"{EB1_FORCES['Tu']} kip-ft")]:
        text = rep(text, f"<textvalue>{old}</textvalue>", f"<textvalue>{new}</textvalue>", f"force {old}")
    text = rep(text, ">45.82 / 57.50 / 146.82 kip-ft</paragraph>", f">{EB1_FORCES['MI']} kip-ft</paragraph>", "Service I moments")
    text = rep(text, "Original source summary: maximum available D/C = 0.966155 for B row spacing / shrinkage, with 48 pending/conditional checks. This "
                     "historical count is unchanged because no source calculation was rerun.",
               f"The values above are the 19 October 2026 case (D-051, {eb1[0]}), live in CapDesignEndBentOne (Mu_N, Mu_P, Mu_B and the Service I "
               "moments), with the same governing members as the 8 October report. Historical 8 October summary: maximum available D/C = 0.966155 for B "
               "row spacing / shrinkage, with 48 pending/conditional checks.", "block 5 summary")
    # block 6: cached cap volumes follow the T014 BridgeGeometry caches
    text = rep(text, 'formula="BridgeGeometry_2Beam.EndBentCap_volume to ft^3"><num>185.5 ft^3</num>',
               'formula="BridgeGeometry_2Beam.EndBentCap_volume to ft^3"><num>205.625 ft^3</num>', "cap volume cell")
    text = rep(text, 'formula="BridgeGeometry_2Beam.EndBentCaps_volume to ft^3"><num>371 ft^3</num>',
               'formula="BridgeGeometry_2Beam.EndBentCaps_volume to ft^3"><num>411.25 ft^3</num>', "caps volume cell")
    cache_log += [{"report": name, "cell": "BridgeGeometry_2Beam.EndBentCap_volume to ft^3", "was": "185.5 ft^3", "now": "205.625 ft^3"},
                  {"report": name, "cell": "BridgeGeometry_2Beam.EndBentCaps_volume to ft^3", "was": "371 ft^3", "now": "411.25 ft^3"}]
    # coherence rows
    text = rep(text, "Shared dimensions and cap-only quantities aligned with the supplied report. Existing pier pipe-pile calculations remain pier-only.",
               "Shared dimensions follow the geometry notebook (D-036: 235-in cap, 251-in envelope) and the D-049 models; cap-only quantities are live. "
               "The end-bent piles are designed in PileDesignEndBentOne and PileDesignEndBentTwo (D-054); the pipe-pile calculations remain pier-only.",
               "layout row")
    text = rep(text, "Loaded nodes updated to 15/34 following the user-confirmed model renumbering.",
               "Loaded nodes 15/34 carry the DC, LL, IM, BR and PL node loads in both 19 October 2026 exports (D-049).", "nodes row")
    text = rep(text, "Deferred by user. Cap volume remains separate; backwall and cheek-wall final quantities remain open.",
               "Backwall and cheek geometry is defined (D-036, D-053: 12-in backwall with its top 4.25 in below the deck-top line on two 2% slopes; "
               "8-in cheek webs) and modeled (D-055); cap volume remains separate, and the backwall and cheek-wall quantity entries remain the earlier "
               "provisional values.", "backwall row")
    text = rep(text, "User confirms the report contains the latest FBMP model. Its recorded hash identifies the accepted source; the different Downloads "
                     "XML was not substituted. Both end bents use the controlling End Bent 1 configuration; no separate End Bent 2 action vector is claimed.",
               "The 19 October 2026 fixed-run exports (D-049) are the current models; their hashes are recorded above and in Foundation Modeling. Both "
               "end bents use the controlling End Bent 1 configuration (D-004); End Bent 2 has its own export, case and reports (D-051, D-054), which "
               "are not folded into this entry table.", "provenance row")
    edits.append({"report": name, "text": "model basis, cap cell, cheek notes, design record (heading, note, context rows, hashes, block 3 heading and note, block 5 heading and values, block 5 summary, coherence rows)",
                  "change": "8 October record -> 19 October 2026 case and D-049 exports; 8 October transverse schedule marked historical"})
    return text


# ============================================================================================
# 3. FBMPPier
# ============================================================================================
def edit_fbmp_pier():
    name = "FBMPPier"
    text = part(name)
    text = rep(text, "Current pier source — response reconciliation, 9 October 2026</heading>",
               "Current pier source — 19 October 2026 (response reconciliation 9 October 2026)</heading>", "pier source heading")
    text = rep(text, "Geometry source: Pier Cap Design 10-9.html, generated 2026-10-09T22:19:21+00:00; case Pier_Fixed — XML analysis.",
               f"Geometry source: {REPORT['PIER'][0]} (D-051; supersedes Pier Cap Design 10-9.html generated 2026-10-09T22:19:21+00:00); case "
               "Pier_Fixed — XML analysis. Pile design: PileDesignPier (D-054).", "pier source paragraph")
    text = rep(text, f"Report SHA-256: {OLD_PIER_REPORT_SHA}",
               f"Report SHA-256: {REPORT['PIER'][1]} ({REPORT['PIER'][0]}; the 10-9 report was {OLD_PIER_REPORT_SHA})", "pier report sha")
    text = rep(text, f"Report-identified Pier_Fixed.XML SHA-256: {OLD_PIER_XML_SHA}",
               f"Report-identified Pier_Fixed.XML SHA-256: {XML['PIER'][1]} (D-049, {TODAY}, held in project_current/fbmp/pier/; the 10-9 report "
               f"identified {OLD_PIER_XML_SHA})", "pier xml sha")
    text = rep(text, "SOURCE LIMIT: the matching Pier_Fixed.XML is not available locally. The report identifies the revised analysis, but its bearing-row "
                     "offsets and full input currency have not been independently verified. Retain the journal’s symmetric +/-10.50-in offsets pending the "
                     "matching raw model.",
               f"RESOLVED {TODAY}: the exact Pier_Fixed.XML (D-049) is in project_current and matches the 19 October report and case (D-051). Its "
               "bearing-row nodes carry Y = -10.50 and +10.50 in, as the journal’s symmetric offsets; the +10.14-in value belonged only to the superseded "
               "Pier_MinTip.XML. Full input currency of the model against the current journal loads is not asserted.", "SOURCE LIMIT")
    edits.append({"report": name, "text": "PierSourceModelRecord heading, source, hashes and source-limit paragraphs", "change": "10-9 report -> 10-19 report (D-051), D-049 XML recorded, ±10.50-in rows confirmed"})
    return text


# ============================================================================================
# 4. PileProperties
# ============================================================================================
def edit_pile_properties():
    name = "PileProperties"
    text = part(name)
    nl = nl_of(text, name)
    text = rep(text, "The pipe section formulas below apply to the pier’s 20-in pipe piles. Both end bents use the current 18-in square pile envelope recorded "
                     "in Bridge Geometry. Do not apply these pipe thickness, steel area, stiffness or corrosion allowances to the end-bent piles; their "
                     "material, reinforcement, section properties and foundation checks require the applicable pile design/model.",
               "The pipe section formulas below apply to the pier’s 20-in pipe piles. Both end bents use the 18-in square prestressed concrete piles "
               "recorded in Bridge Geometry and designed in PileDesignEndBentOne and PileDesignEndBentTwo (19 October 2026, D-054: Standard Plans Index "
               "455-018, 12 x 0.6-in strands, 18 tons of downdrag per pile). Do not apply these pipe thickness, steel area, stiffness or corrosion "
               "allowances to the end-bent piles. The pier piles are designed in PileDesignPier (D-054).", "applicability paragraph")
    anchor = (' ' * 8 + '</section>' + nl + ' ' * 8 + '<heading level="1">Sacrificial Thickness</heading>')
    section = section_block(8, "PileDesignRecords20261019", "Pile design records and section reconciliation — 19 October 2026", [
        f"The 19 October 2026 fixed-run pier model ({XML['PIER'][0]}, D-049) uses a 20-in circular steel section with a 0.48-in shell, A = 29.14 in², "
        "I = 1389.26 in⁴, E = 29000 ksi and Fy = 60 ksi: to the model’s precision this is the effective section A_eff and I_x below (0.475-in "
        "effective wall from the 5/8-in pipe less the 0.15-in allowance).",
        "PileDesignPier (D-054) reads the model section (D_out 20 in, t_wall 0.48 in) with no further corrosion allowance (t_corr 0; LRFD 10.7.5 and "
        "the FDOT environment classification are pending) and Fy = 45 ksi (Specification 962, ASTM A252 Grade 3) against 60 ksi in the FBMP model. "
        "The pipe steel grade and corrosion allowance are pending reconciliation; the sacrificial-thickness basis of this module is not changed here.",
        "The end-bent piles (18-in square prestressed concrete, Index 455-018) are designed in PileDesignEndBentOne and PileDesignEndBentTwo from the "
        "D-049 end-bent exports with the D-050 downdrag; their structural demand/capacity ratios are 0.550 and 0.557 and the pier’s 0.457 at the 19 "
        "October cases. Pending in all three: downdrag source documentation, pile-to-cap connection (12-in embedment), minimum tip elevation, scour, "
        "drivability, environment classification and FBMP export currency."],
        links=[("#PileDesignEndBentOne", "Pile design - End Bent 1 (distilled, 19 October 2026 case)"),
               ("#PileDesignEndBentTwo", "Pile design - End Bent 2 (distilled, 19 October 2026 case)"),
               ("#PileDesignPier", "Pile design - Pier (distilled, 19 October 2026 case)")])
    text = rep(text, anchor, ' ' * 8 + '</section>' + nl + nl.join(section) + nl + ' ' * 8 + '<heading level="1">Sacrificial Thickness</heading>', "section anchor")
    edits.append({"report": name, "text": "applicability paragraph; section PileDesignRecords20261019 added", "change": "pile design reports (D-054) and the pipe shell/grade reconciliation recorded"})
    return text


# ============================================================================================
# 5. FoundationModeling
# ============================================================================================
def edit_foundation_modeling():
    name = "FoundationModeling"
    text = part(name)
    nl = nl_of(text, name)
    text = rep(text, '<heading level="1" keepwithnext="True">End-bent model reconciliation</heading>',
               '<heading level="1" keepwithnext="True">End-bent model reconciliation — 8 October 2026 (model sources superseded by the 19 October 2026 record below)</heading>',
               "EB reconciliation heading")
    anchor = (' ' * 8 + '</section>' + nl + ' ' * 8 + '<heading level="0">Current Files</heading>')
    e1, e2, p = XML["EB1"], XML["EB2"], XML["PIER"]
    section = section_block(8, "ModelSources20261019", "Current model sources — 19 October 2026", [
        f"Current FB-MultiPier models are the 19 October 2026 fixed-run exports selected under D-049 (FB-MultiPier 6.1.0): {e1[0]} (SHA-256 {e1[1]}), "
        f"{e2[0]} (SHA-256 {e2[1]}) and {p[0]} (SHA-256 {p[1]}), held in project_current/fbmp/. The 19 October cap reports and cases (D-051: "
        "CapDesignEndBentOne, CapDesignEndBentTwo, CapDesignPier) and pile reports (D-054: PileDesignEndBentOne, PileDesignEndBentTwo, PileDesignPier) "
        "read these exports.",
        "End-bent models: 251-in cap (the cage envelope with the 8-in cheek webs), 42 x 36 in, four 18-in square prestressed piles at 54-in centers, "
        "first pile center 44.5 in from each cap end (36.5 in from the 235-in cap-body end recorded in Bridge Geometry); loaded nodes 15 and 34 carry "
        "the DC, LL, IM, BR and PL node loads. Pier model: 230-in cap, 48 x 36 in, four 20-in x 0.48-in steel pipe piles at 60-in centers, bearing rows "
        "at Y = -10.50 and +10.50 in. Pile cutoff and ground elevations in the pile reports come from these exports.",
        "Currency of these models against the current journal loads (haunch weights with the notebook cambers, wind heights, backwall and cheek "
        "geometry of D-053/D-055) is not asserted; FBMP was not rerun for this record. The 16 October 2026 backwall report (D-037) predates these "
        "exports and the D-053 geometry and is not in the journal."],
        links=[("#FBMPEndBent.EBCurrentDesignRecord", "Current end-bent design and coherence record"),
               ("#FBMPPier.PierSourceModelRecord", "Current pier source record"),
               ("#PileProperties.PileDesignRecords20261019", "Pile design records and section reconciliation")])
    text = rep(text, anchor, ' ' * 8 + '</section>' + nl + nl.join(section) + nl + ' ' * 8 + '<heading level="0">Current Files</heading>', "section anchor")
    text = rep(text, "The matching raw XML remains required to verify the right-row offset correction.",
               f"The matching raw XML (D-049, {TODAY}) now confirms symmetric ±10.50-in bearing rows.", "pier raw XML sentence")
    edits.append({"report": name, "text": "section ModelSources20261019 added; EB heading dated; pier raw-XML sentence", "change": "D-049 exports recorded as the current model sources"})
    return text


# ============================================================================================
# 6. PedBridge
# ============================================================================================
def edit_pedbridge():
    name = "PedBridge"
    text = part(name)
    nl = nl_of(text, name)
    anchor = ' ' * 8 + '<section name="CurrentEndBentRecord" capture="False" hide="false">'
    section = section_block(8, "CurrentRecord20261019", "Current project record — 19 October 2026", [
        "Geometry: the geometry notebook build e9b41b8eaf (D-036; backwall tops D-053) owns the bridge geometry; the CAD model (D-055) and the CAD "
        "tables are built from it. Analysis: the 19 October 2026 fixed-run FB-MultiPier exports (D-049). Design records: the 10-19 cap design reports "
        "(D-051) and pile design reports (D-054), distilled in the journal. The 16 October 2026 backwall report (D-037) is separate and predates "
        "D-049 and D-053. Journal tasks T014 to T016."],
        links=[("#FoundationModeling.ModelSources20261019", "Current model sources (D-049 exports)"),
               ("#FBMPEndBent.EBCurrentDesignRecord", "Current end-bent design and coherence record"),
               ("#FBMPPier.PierSourceModelRecord", "Current pier source record"),
               ("#PileProperties.PileDesignRecords20261019", "Pile design records and section reconciliation"),
               ("#MSEWallExclusion", "MSE wall exclusion boxes (D-055 wall lines)")])
    text = rep(text, anchor, nl.join(section) + nl + anchor, "CurrentEndBentRecord anchor")
    text = rep(text, ">Current end-bent data — 8 October 2026</heading>", ">End-bent data — 8 October 2026 (superseded by the 19 October 2026 record above)</heading>", "8 October heading")
    rev_old = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">Revision: 8 October 2026, coherence responses.'
    rev_new = (' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">Revision: 19 October 2026, coherence with the 19 October '
               'calculations and CAD model (T016): D-049 exports, D-051 cap reports and D-054 pile reports recorded as current; end-bent design record '
               'refreshed; MSE exclusion wall lines re-extracted from the D-055 model; notebook check retargeted to build e9b41b8eaf.</paragraph>')
    text = rep(text, rev_old, rev_new + nl + rev_old, "Revision paragraph")
    text = rep(text, "The matching raw XML is still needed to verify the offset correction.",
               f"The matching raw Pier_Fixed.XML (D-049, {TODAY}) is now in project_current and confirms the symmetric ±10.50-in bearing rows.", "pier raw XML sentence")
    edits.append({"report": name, "text": "section CurrentRecord20261019 added; 8 October heading; revision paragraph; pier sentence", "change": "19 October 2026 record indexed"})
    return text


# ============================================================================================
# 7. DecisionLog
# ============================================================================================
DECISION = ("Journal aligned with the 19 October 2026 calculations and CAD model (task T016). The D-049 fixed-run FB-MultiPier exports (End Bent 1, End "
            "Bent 2, Pier) are recorded as the current model sources in Foundation Modeling and both FBMP entry modules, with the D-051 cap reports and the "
            "D-054 pile reports as the current design records. The end-bent design record is refreshed to the 19 October case (forces, status, report and "
            "XML identities; the 8 October transverse schedule kept as history). The pier source record names the 10-19 report and the D-049 XML, whose "
            "bearing rows are ±10.50 in. Pile Section Properties notes the pile design reports and the pipe reconciliation (FBMP 0.48-in shell at 60 ksi; "
            "PileDesignPier 0.48 in at 45 ksi, grade and corrosion pending). The notebook reconciliation check is retargeted to build e9b41b8eaf and the "
            "D-053 backwall top drop (4.25 in) is recorded. The MSE exclusion wall lines are re-extracted from the D-055 model: at both end bents the front "
            "wall back of facing is 46.5 in from the pile row (37.5-in strap clearance met; cap face 25.5 in from the facing) and the side walls are "
            "114 in from the pile row, at the 24-in criterion within 0.0002 in, so one side-wall row at each end bent reads MEETS CLEAR and the other "
            "SHORTFALL by the last digits; the cap caches follow the 235-in cap. The 16 October backwall report (D-037) predates the D-049 exports "
            "and the D-053 geometry and is not in the journal. Native recalculation not performed; FBMP not rerun.")


def edit_decisionlog():
    name = "DecisionLog"
    text = part(name)
    nl = "\r\n" if text.endswith("</section>\r\n    </report>") else "\n"
    tail = ' ' * 8 + '</section>' + nl + ' ' * 4 + '</report>'
    assert text.endswith(tail), "DecisionLog does not end with a section inside the report"
    once(text, '<section name="CoherenceDecision20261019" capture="False" hide="false">', "latest entry")
    assert 'name="CoherenceDecision20261019b"' not in text
    entry = nl.join([' ' * 8 + '<section name="CoherenceDecision20261019b" capture="False" hide="false">',
                     ' ' * 12 + '<heading level="1" keepwithnext="True">2026-10-19 - Journal aligned with the 19 October calculations and CAD model (T016)</heading>',
                     ' ' * 12 + f'<paragraph fontfamily="{TNR}" fontsize="11" leftindent="0" spacingafter="7">{escape(DECISION)}</paragraph>',
                     ' ' * 8 + '</section>'])
    text = text[:-len(' ' * 4 + '</report>') - len(nl)] + nl + entry + nl + ' ' * 4 + '</report>'
    edits.append({"report": name, "text": DECISION, "change": "entry appended (19 October 2026, T016)"})
    return text


# ============================================================================================
# 8. MSEWallExclusion: wall lines from the D-055 model, caches refreshed
# ============================================================================================
def report_defs(root):
    defs, caches = {}, {}
    for e in root.iter():
        m = re.match(r"^\s*([^\W\d]\w*)\s*=(?!=)\s*(.*)$", e.get("formula", ""), re.S)
        if m and m[1] not in defs:
            defs[m[1]] = m[2]
            r = e.find("expresult")
            caches[m[1]] = r.text if r is not None else None
    return defs, caches


def clean(cache):
    return (cache or "").replace(NBSP, "").lstrip("=").strip()


def wall_literals(layout):
    """The 42 wall-line definitions exactly as tasks/T009/build_module.py writes them."""
    out = {}
    for bi, b in enumerate(layout["bents"], 1):
        pre, flip = f"Bent{bi}", 1 if bi == 1 else -1
        for wi, wid in enumerate(["A5", "A6", "A7"] if bi == 1 else ["B1", "B6", "B7"], 1):
            w = layout["walls"][wid] if isinstance(layout["walls"], dict) else next(x for x in layout["walls"] if x["id"] == wid)
            wp = f"{pre}W{wi}"
            for suffix, value, unit in [("x", w["start"][0] - b["center"][0], True), ("y", (w["start"][1] - b["center"][1]) * flip, True),
                                        ("len", w["length"], True), ("tx", w["tangent"][0], False), ("ty", w["tangent"][1] * flip, False),
                                        ("nx", -w["outward"][0], False), ("ny", -w["outward"][1] * flip, False)]:
                out[f"{wp}{suffix}"] = f"{value:.15g} ft" if unit else str(float(value))
    return out


def edit_mse():
    name = "MSEWallExclusion"
    text = part(name)
    nl = nl_of(text, name)
    root = E.fromstring(text.encode("utf-8"))
    defs, caches = report_defs(root)
    old_layout = json.loads((ROOT / "mse_strap_check" / "layout_snapshot.json").read_text(encoding="utf-8"))
    new_layout = json.loads((TASK / "mse_layout_20261019.json").read_text(encoding="utf-8"))
    model = ROOT / "project_current/geometry/freecad/B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd"
    assert new_layout["model_sha256"] == CAD_SHA == sha(model.read_bytes()), "mse_layout_20261019.json is not the extraction of the current (D-055) model"
    assert old_layout["model_sha256"] == OLD_CAD_SHA
    old_lits, new_lits = wall_literals(old_layout), wall_literals(new_layout)
    for k, v in old_lits.items():
        assert defs[k] == v, f"{k}: journal literal {defs[k]!r} is not the 13 October snapshot value {v!r}"

    def ext(cap_length_in):
        return {("BridgeGeometry_2Beam", "EndBent_pileWidth"): M.Q.length(18, "in"), ("BridgeGeometry_2Beam", "EndBent_pileSpacing"): M.Q.length(54, "in"),
                ("BridgeGeometry_2Beam", "EndBent_pileCount"): M.Q(4), ("BridgeGeometry_2Beam", "EndBentCap_width"): M.Q.length(42, "in"),
                ("BridgeGeometry_2Beam", "EndBentCap_length"): M.Q(cap_length_in, "len", "ftin")}
    old_rep = M.Report(defs, ext(212))
    new_defs = dict(defs)
    new_defs.update(new_lits)
    new_rep = M.Report(new_defs, ext(235))

    # --- validate: every cached definition result is reproduced from the current formulas and literals
    checked = 0
    for n, c in caches.items():
        if c is None:
            continue
        got = old_rep.text(n)
        assert got == clean(c), f"{n}: evaluator gives {got!r}, journal cache is {clean(c)!r}"
        checked += 1
    assert checked >= 120, f"only {checked} caches validated"
    # --- validate every formula table cell (num and textvalue)
    cells = []
    for c in root.iter("c"):
        f = c.get("formula")
        if not f or f.startswith("ProjectInfo."):      # the project stamp reads another report
            continue
        num, tv = c.find("num"), c.find("textvalue")
        got = old_rep.cell(f)
        if num is not None:
            m1, m2 = re.match(r"(-?[\d.eE+-]+) (\w+)$", got), re.match(r"(-?[\d.eE+-]+) (\w+)$", num.text)
            assert m1 and m2 and m1[2] == m2[2] and abs(float(m1[1]) - float(m2[1])) <= 1e-9 * max(1.0, abs(float(m2[1]))), f"cell {f}: {got!r} vs {num.text!r}"
            cells.append((f, "num", num.text, got == num.text))
        elif tv is not None:
            assert got == tv.text, f"cell {f}: {got!r} vs {tv.text!r}"
            cells.append((f, "textvalue", tv.text, True))
    exact = sum(1 for c in cells if c[3])
    assert len(cells) >= 50 and exact >= len(cells) - 8, f"cells validated {len(cells)}, exact text {exact}"

    # --- wall literals
    changed_lits = 0
    for k, v in new_lits.items():
        if v == old_lits[k]:
            continue
        text = rep(text, f'<dynexp formula="{k} = {old_lits[k]}"', f'<dynexp formula="{k} = {v}"', f"{k} formula")
        text = rep(text, f"<expbody>{k} = {old_lits[k]}</expbody>", f"<expbody>{k} = {v}</expbody>", f"{k} expbody")
        edits.append({"report": name, "formula": f"{k} = {v}", "was": f"{k} = {old_lits[k]}", "change": "wall line re-extracted from the D-055 model"})
        changed_lits += 1
    assert 12 <= changed_lits <= 18, f"expected the x, y, len literals of six walls to change (12-18), got {changed_lits}"
    # --- refreshed definition caches
    refreshed = 0
    for n, c in caches.items():
        if c is None:
            continue
        old_t, new_t = old_rep.text(n), new_rep.text(n)
        if old_t == new_t:
            continue
        pat = re.compile(r"(<expbody>" + re.escape(n) + r" = [^<]*</expbody>\r?\n\s*<expresult>" + NBSP + r"= )" + re.escape(old_t) + r"(</expresult>)")
        assert len(pat.findall(text)) == 1, f"{n}: cached definition not found exactly once"
        text = pat.sub(lambda m, t=new_t: m.group(1) + t + m.group(2), text)
        cache_log.append({"report": name, "name": n, "formula": f"{n} = {defs[n]}", "was": f"= {old_t}", "now": f"= {new_t}"})
        refreshed += 1
    # --- refreshed cells
    for f, kind, was, _ in cells:
        now = new_rep.cell(f)
        if now == was:
            continue
        old = f'formula="{attr(f)}"><{kind}>{was}</{kind}>'
        new = f'formula="{attr(f)}"><{kind}>{now}</{kind}>'
        k = text.count(old)
        assert k >= 1, f"cell {f}: not found"
        text = text.replace(old, new)
        cache_log.append({"report": name, "cell": f, "was": was, "now": now, "occurrences": k})
    assert refreshed >= 30, f"only {refreshed} definition caches refreshed"
    # --- narrative and provenance
    text = rep(text, ">Both end bents | 13 October 2026 | Front strap check; specified side offsets<",
               ">Both end bents | 19 October 2026 (first issued 13 October 2026) | Front strap check; specified side offsets<", "title line")
    text = rep(text, ">Shared pile size and spacing are live journal references. Use nominal pile width only, without a placement envelope. Wall positions "
                     "remain the saved CAD snapshot.<",
               ">Shared pile size, spacing and cap dimensions are live journal references (235-in cap since 19 October 2026, D-036). Use nominal pile "
               "width only, without a placement envelope. Wall positions are the saved CAD snapshot of 19 October 2026 (D-055 model); the 8-in cheek webs "
               "outside the cap ends are not part of this screen. In that model the side walls stand 114 in from the pile row, at the 24-in criterion "
               "within 0.0002 in: the side-wall rows below read MEETS CLEAR or SHORTFALL only by the last digits of the saved coordinates.<", "inputs note")
    text = rep(text, f"Saved model SHA-256: {OLD_CAD_SHA}",
               f"Saved model SHA-256: {CAD_SHA} (19 October 2026, D-055). Wall lines re-extracted from the saved WallProfile properties on 19 October 2026 "
               f"(journal task T016, tasks/T016/mse_layout_20261019.json); the 13 October 2026 lines came from model {OLD_CAD_SHA} and were superseded "
               "when the walls moved with the 235-in caps and cheek webs (D-026/D-036).", "model sha")
    summary = {k: new_rep.text(k) for k in ["CapLength", "CapX", "Bent1W1Gap", "Bent1W2Gap", "Bent1W3Gap", "Bent1CapGap", "Bent1W1Status", "Bent1W2Status",
                                             "Bent1W3Status", "Bent1CapStatus", "Bent2W1Gap", "Bent2W2Gap", "Bent2W3Gap", "Bent2CapGap", "Bent2W1Status",
                                             "Bent2W2Status", "Bent2W3Status", "Bent2CapStatus"]}
    return text, {"caches_validated": checked, "cells_validated": len(cells), "cells_exact_text": exact, "definition_caches_refreshed": refreshed,
                  "wall_literals_changed": changed_lits, "summary": summary}


# ============================================================================================
def main():
    out = {"report:BridgeGeometry_2Beam": edit_geometry(), "report:FBMPEndBent": edit_fbmp_endbent(), "report:FBMPPier": edit_fbmp_pier(),
           "report:PileProperties": edit_pile_properties(), "report:FoundationModeling": edit_foundation_modeling(),
           "report:PedBridge": edit_pedbridge(), "report:DecisionLog": edit_decisionlog()}
    mse_text, mse_info = edit_mse()
    out["report:MSEWallExclusion"] = mse_text
    assert set(out) == set(mapping)
    for key, data in out.items():
        E.fromstring(data.encode("utf-8"))           # well-formed
        (TASK / "components" / mapping[key]).write_bytes(data.encode("utf-8"))
    (TASK / "definitions.json").write_text(json.dumps({"edited": edits, "cache_refreshes": cache_log, "mse": mse_info}, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    print(json.dumps({"task": "T016", "components": {k: {"file": mapping[k], "bytes": len(v), "sha256": sha(v.encode('utf-8'))} for k, v in sorted(out.items())},
                      "edits": len(edits), "cache_refreshes": len(cache_log), "mse": mse_info}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
