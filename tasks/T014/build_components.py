"""T014: write the 25 registered component files from base.bpad (rerunnable, byte-surgical).

Existing components are edited by exact-substring surgery (every anchor must occur exactly the stated
number of times); nothing is re-serialized except the new ProjectInfo report and the inserted project
stamp blocks, which are built with lxml and spliced in at a computed byte offset. Line endings are kept
as found (the journal is CRLF; new fragments are LF like T012).

    build_components.py                  every component except the four cap reports (they stay base copies)
    build_components.py --cap-reports    additionally build tasks/T014/preview-journal.bpad, run
                                         scripts/build_cap_bpad.py --journal on it and copy the four fragments

Every refreshed cache of BridgeGeometry_2Beam comes from geom_eval.py, which must first reproduce all the
current caches it is asked to refresh. Standard library plus lxml.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TASK))
from tools.bpad_workflow import Journal  # noqa: E402
import geom_eval as G  # noqa: E402
from scripts.bpad_sheet import project_stamp_table  # noqa: E402
from scripts.build_cap_bpad import PROJECT_STAMP  # noqa: E402

NBSP = " "
CAP_REPORTS = ["CapDesignBasis", "CapDesignEndBentOne", "CapDesignEndBentTwo", "CapDesignPier"]
STAMPED = ["Materials", "BridgeGeometry_2Beam", "AccessGeometry", "BearingDesign", "PileProperties", "GeneralLoads",
           "PedBridgeWind", "C001WindLoadOnPedBridgeSuperstructure", "FenceWind", "BridgeMovement",
           "SuperstructureUplift", "LoadCombinations", "FBMPPier", "FBMPEndBent", "FoundationModeling",
           "PierWallFins", "MSEWallExclusion"]
ALL_KEYS = {"AccessGeometry", "BearingDesign", "BridgeGeometry_2Beam", "BridgeMovement",
            "C001WindLoadOnPedBridgeSuperstructure", "CapDesignBasis", "CapDesignEndBentOne", "CapDesignEndBentTwo",
            "CapDesignPier", "DecisionLog", "FBMPEndBent", "FBMPPier", "FenceWind", "FoundationModeling", "GeneralLoads",
            "LoadCombinations", "MSEWallExclusion", "Materials", "PedBridge", "PedBridgeWind", "PierCapDesign",
            "PierWallFins", "PileProperties", "ProjectInfo", "SuperstructureUplift"}

TODAY = "19 October 2026"
NOTEBOOK = "geometry notebook (model e9b41b8eaf, 19 October 2026, D-036)"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def count(text, old):
    return text.count(old)


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


# --------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------
base = Journal.load(TASK / "base.bpad")
mapping = json.loads((TASK / "components.json").read_text(encoding="utf-8"))
assert {k.split(":", 1)[1] for k in mapping} == ALL_KEYS and len(mapping) == 25, "unexpected component keys"
assert "report:PierCapDesign" in base.spans and "report:ProjectInfo" not in base.spans


def part(name):
    return base.part(f"report:{name}").decode("utf-8")


edits = []          # every changed formula / link / text, for definitions.json
cache_log = []      # every refreshed cache: report, name, formula, was, now


# --------------------------------------------------------------------------------------------
# Shared builders
# --------------------------------------------------------------------------------------------
def stamp_lines(indent):
    """The project stamp as an indented block of lines (LF-free): pretty-printed by lxml, 2 -> 4 space steps."""
    holder = E.Element("report")
    project_stamp_table(holder, PROJECT_STAMP, live=True)
    embed = holder[0]
    assert embed.tag == "embed" and len(holder) == 1
    raw = E.tostring(embed, pretty_print=True, encoding="unicode").rstrip("\n")
    out = []
    for line in raw.split("\n"):
        lead = len(line) - len(line.lstrip(" "))
        out.append(indent + " " * (lead * 2) + line.lstrip(" "))
    return out


def insert_stamp(name):
    """Splice the stamp block in before the first content child; the rest of the component is untouched."""
    def apply(text):
        nl = nl_of(text, name)
        assert 'name="ProjectStamp"' not in text, f"{name}: already has a ProjectStamp"
        root = E.fromstring(text.encode("utf-8"))
        first = next(c for c in root if isinstance(c.tag, str) and c.tag not in ("stylerule", "include", "float"))
        lines = text.split("\n")
        offset = sum(len(x) + 1 for x in lines[:first.sourceline - 1])
        indent = re.match(r" *", lines[first.sourceline - 1]).group(0)
        assert text[offset:].startswith(indent + "<" + first.tag), f"{name}: first content child not at line start"
        block = nl.join(stamp_lines(indent)) + nl
        return text[:offset] + block + text[offset:], first.tag, first.sourceline
    return apply


def amber_par(indent, formula, caption, nl, amber=True, cache=None):
    """Input/derived definition + caption in the BridgeGeometry_2Beam layout (indent = paragraph indent)."""
    i = " " * indent
    style = ' style="Required Input"' if amber else ""
    lines = [f'{i}<paragraph fontfamily="Times New Roman" fontsize="11" leftindent="0" spacingafter="2" spacingbefore="4" keepwithnext="True">',
             f'{i}    <dynexp formula="{attr(formula)}" mathlayout="on" showsteps="False" seplines="False"{style}>',
             f'{i}        <expbody>{escape(formula)}</expbody>']
    if cache is not None:
        lines.append(f"{i}        <expresult>{NBSP}= {cache}</expresult>")
    lines += [f"{i}    </dynexp>", f"{i}</paragraph>",
              f'{i}<paragraph fontfamily="Times New Roman" fontsize="10" leftindent="0" spacingafter="7">{escape(caption)}</paragraph>']
    return nl.join(lines)


# --------------------------------------------------------------------------------------------
# 1. ProjectInfo (new report, lxml)
# --------------------------------------------------------------------------------------------
def build_project_info():
    TNR = "Times New Roman"
    r = E.Element("report", name="ProjectInfo", title="Project Information", unit="in", pagesize="816,1056",
                  margin="48,48,48,48", bordermargin="0,0,0,0", collapsemargins="False")
    E.SubElement(r, "stylerule", type="AnyEquation", name="Required Input", texthighlight="#F7E6B9")

    def p(text="", **kw):
        a = {"fontfamily": TNR, "fontsize": "11", "spacingafter": "6"}
        a.update({k: str(v) for k, v in kw.items()})
        el = E.SubElement(r, "paragraph", **a)
        el.text = text
        return el

    p("D2 I-95 PEDESTRIAN BRIDGE", fontsize=16, fontweight="bold", spacingafter=2)
    p("PROJECT INFORMATION", fontsize=14, fontweight="bold", spacingafter=6)
    p("Project identification used by every calculation report; edit here, not in the reports.", background="#F1F5FA")
    fields = [
        ("Firm", PROJECT_STAMP["Firm"], "Firm name shown in the project stamp of every calculation report."),
        ("Address", PROJECT_STAMP["Address"], "Firm address."),
        ("Project", PROJECT_STAMP["Project"], "Project title."),
        ("JobNo", PROJECT_STAMP["JobNo"], "Job number (blank until assigned)."),
        ("DesignedBy", PROJECT_STAMP["DesignedBy"], "Designer initials."),
        ("DesignDate", PROJECT_STAMP["DesignDate"], "Date of design."),
        ("CheckedBy", PROJECT_STAMP["CheckedBy"], "Checker initials."),
        ("CheckDate", PROJECT_STAMP["CheckDate"], "Date of check (blank until checked)."),
    ]
    for name, value, caption in fields:
        formula = f'{name} = "{value}"'
        holder = E.SubElement(r, "paragraph", fontfamily=TNR, fontsize="11", spacingafter="1", spacingbefore="4", keepwithnext="True")
        d = E.SubElement(holder, "dynexp", formula=formula, mathlayout="on", showformula="True", showresult="False",
                         showsteps="False", style="Required Input")
        E.SubElement(d, "expbody").text = formula
        p(caption, fontsize=10, spacingafter=5, textcolor="#43505C")
    p("PROJECT STAMP (as placed at the top of each calculation report)", fontweight="bold", spacingbefore=8, keepwithnext="True")
    project_stamp_table(r, PROJECT_STAMP, live=True)
    return E.tostring(r, encoding="utf-8", pretty_print=True).rstrip()


# --------------------------------------------------------------------------------------------
# 2. Materials
# --------------------------------------------------------------------------------------------
def edit_materials():
    text = part("Materials")
    nl = nl_of(text, "Materials")
    old = (' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + nl + ' ' * 12 +
           '<link address="#PierCapDesign">Concrete and reinforcing properties used by C005</link>' + nl + ' ' * 8 + '</paragraph>' + nl)
    items = [
        ("Substructure_fc = 5.5 ksi", "Class IV concrete, C.I.P. substructure: caps, pier wall and backwalls (min. 28-day strength, table above)."),
        ("Deck_fc = 4.5 ksi", "Class II concrete, bridge deck (min. 28-day strength, table above)."),
        ("Beam_fc = 8.5 ksi", "Class VI concrete, prestressed beams (min. 28-day strength, table above)."),
        ("Railing_fc = 3.4 ksi", "Class II concrete, railings (min. 28-day strength, table above)."),
        ("Rebar_fy = 60 ksi", "Reinforcing steel yield strength, ASTM A615 Grade 60."),
        ("Rebar_Es = 29000 ksi", "Reinforcing steel modulus of elasticity, LRFD 5.4.3.2."),
    ]
    i = " " * 8
    lines = [i + '<paragraph fontfamily="Times New Roman" fontsize="11" fontweight="bold" spacingbefore="6" spacingafter="6" leftindent="0">'
             "MATERIAL PROPERTIES USED BY THE CALCULATIONS</paragraph>"]
    for formula, caption in items:
        lines += [i + '<paragraph fontfamily="Times New Roman" fontsize="11" leftindent="0" spacingafter="1" spacingbefore="4" keepwithnext="True">',
                  i + f'    <dynexp formula="{attr(formula)}" mathlayout="on" showformula="True" showresult="False" showsteps="False" seplines="False" style="Required Input">',
                  i + f"        <expbody>{escape(formula)}</expbody>", i + "    </dynexp>", i + "</paragraph>",
                  i + f'<paragraph fontfamily="Times New Roman" fontsize="10" leftindent="0" spacingafter="7">{escape(caption)}</paragraph>']
        edits.append({"report": "Materials", "formula": formula, "change": "amber input added (moved from C005)"})
    text = rep(text, old, nl.join(lines) + nl, "Materials C005 link")
    edits.append({"report": "Materials", "link": "#PierCapDesign", "change": "link to deleted C005 removed"})
    return text


# --------------------------------------------------------------------------------------------
# 3. BridgeGeometry_2Beam
# --------------------------------------------------------------------------------------------
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


def name_tokens(rhs):
    return set(re.findall(r"(?<![\w.])[^\W\d]\w*", rhs))


EXTERNAL = {("PedBridgeWeights_2Beams", "I29"): G.Q.of(150, "pcf")}      # concrete unit weight cell, 150 pcf
SEEDS = ["EndBent_endDetail", "Beam_camber_1", "Beam_camber_2"]
CAMBER = {"Beam_camber_1": "0.124592744006574 in", "Beam_camber_2": "0.5671714630550072 in"}
NEW_ENDDETAIL = "EndBent_pileEndClear-EndBent_edgeClear-EndBent_pileTolerance to in"


def check_notebook_quantity(rep_new):
    ok = abs(rep_new.V("Haunch_totalVolume").v / 1728.0 - 185.836666666667) < 1e-6   # deck area unchanged (checked below)
    return "MATCHES 2026-09-29 NOTEBOOK" if ok else "INPUTS CHANGED - RECONCILE NOTEBOOK"


def edit_geometry():
    global edits
    text = part("BridgeGeometry_2Beam")
    nl = nl_of(text, "BridgeGeometry_2Beam")
    root = E.fromstring(text.encode("utf-8"))
    defs, caches = report_defs(root)

    new_defs = dict(defs)
    new_defs.update({"EndBent_pileEndClear": "27.5 in", "EndBent_endDetail": NEW_ENDDETAIL,
                     "EndBent_cheekThickness": "8 in", "EndBent_lugProjection": "6 in", "EndBent_lugWidth": "5.5 in",
                     "EndBent_mseJoint": "0.5 in",
                     "EndBentCage_envelope": "EndBentCap_length+2*EndBent_cheekThickness to in",
                     "PierCap_coverTop": "3 in", "PierCap_coverBottom": "3 in", "PierCap_coverSide": "3 in"})
    new_defs.update(CAMBER)
    old_rep, new_rep = G.Report(defs, EXTERNAL), G.Report(new_defs, EXTERNAL)

    # dependents of the four changed inputs (token scan over the current formulas of this report)
    closure = set(SEEDS)
    grew = True
    while grew:
        grew = False
        for name, rhs in defs.items():
            if name not in closure and name_tokens(rhs) & closure:
                closure.add(name)
                grew = True
    dependents = sorted(closure - set(SEEDS))

    special = {"Check_notebook_quantity": check_notebook_quantity}
    refreshed = {}
    for name in dependents:
        old_cache = clean(caches[name])
        assert old_cache, f"{name}: dependent without a cached result"
        frac = "/" in old_cache
        if name in special:
            old_text, new_text = old_cache, special[name](new_rep)
            assert old_text == special[name](old_rep), f"{name}: evaluator does not reproduce the current cache"
        else:
            old_text, new_text = old_rep.text(name, fraction=frac), new_rep.text(name, fraction=frac)
            assert old_text == old_cache, f"{name}: evaluator gives {old_text!r}, journal cache is {old_cache!r}"
        refreshed[name] = (old_cache, new_text)

    # --- cached results of definitions ---------------------------------------------------
    for name, (old_text, new_text) in refreshed.items():
        if old_text == new_text:
            continue
        pat = re.compile(r"(<expbody>" + re.escape(name) + r" = [^<]*</expbody>\r?\n\s*<expresult>" + NBSP + r"= )" + re.escape(old_text) + r"(</expresult>)")
        assert len(pat.findall(text)) == 1, f"{name}: cached definition not found exactly once"
        text = pat.sub(lambda m, t=new_text: m.group(1) + t + m.group(2), text)
        cache_log.append({"report": "BridgeGeometry_2Beam", "name": name, "formula": f"{name} = {defs[name]}",
                          "was": f"{NBSP}= {old_text}".replace(NBSP, " "), "now": f"= {new_text}"})
    # --- cached results of table cells --------------------------------------------------------
    cells = 0
    for c in root.iter("c"):
        f = c.get("formula")
        num = c.find("num")
        if not f or num is None or "=" in f.replace("==", ""):
            continue
        if not (name_tokens(split_rhs(f)) & closure):
            continue
        old_text, new_text = old_rep.eval_cell(f), new_rep.eval_cell(f)
        assert old_text == num.text, f"cell {f}: evaluator gives {old_text!r}, journal cache is {num.text!r}"
        if old_text != new_text:
            old = f'formula="{attr(f)}"><num>{num.text}</num>'
            text = rep(text, old, f'formula="{attr(f)}"><num>{new_text}</num>', f"cell {f}")
            cache_log.append({"report": "BridgeGeometry_2Beam", "cell": f, "was": old_text, "now": new_text})
            cells += 1
    assert cells == 12, f"expected 12 refreshed pile-table cells, got {cells}"

    # --- (a) EndBent_pileEndClear / EndBent_endDetail -------------------------------------------
    anchor_old = (amber_par(12, "EndBent_endDetail = 4 in", "Additional nominal end allowance.", nl, amber=True))
    anchor_new = (amber_par(12, "EndBent_pileEndClear = 27.5 in",
                            "Clear distance from the outer pile face to the cap end; notebook CONFIG end_bents.*.pile_end_clear_in (D-026 235-in cap)", nl)
                  + nl +
                  amber_par(12, "EndBent_endDetail = " + NEW_ENDDETAIL,
                            "Additional end allowance derived from the notebook pile end clearance; the previous 4-in input gave a 16-in pile end clearance and a 212-in cap.",
                            nl, amber=False, cache=new_rep.text("EndBent_endDetail")))
    text = rep(text, anchor_old, anchor_new, "EndBent_endDetail block")
    edits += [{"report": "BridgeGeometry_2Beam", "formula": "EndBent_pileEndClear = 27.5 in", "change": "amber input added (notebook pile end clearance)"},
              {"report": "BridgeGeometry_2Beam", "formula": "EndBent_endDetail = " + NEW_ENDDETAIL, "was": "EndBent_endDetail = 4 in",
               "change": "amber literal replaced by a derived value; cached 15.5 in"}]

    # Source row of the context table
    text = rep(text, "End bent 1 Cap Design Report_10-8.html, generated 8 October 2026; current saved case.",
               "Geometry notebook, model e9b41b8eaf, 19 October 2026 (decision D-036); mirrored in project_current/geometry/tables/B4_Geometry_CAD_Tables.xlsx. "
               "Replaces the End bent 1 Cap Design Report_10-8.html geometry (4-in end detail, 212-in cap).", "Source row")
    edits.append({"report": "BridgeGeometry_2Beam", "text": "EndBentCurrentGeometry Source row", "change": "names the geometry notebook (e9b41b8eaf, D-036)"})

    # --- (b) cheek/lug/joint inputs and the cage envelope after EndBentCap_length ----------------
    cap_len_caption = ' ' * 12 + '<paragraph fontfamily="Times New Roman" fontsize="10" leftindent="0" spacingafter="7">Overall cap length along the pile row.</paragraph>'
    extra = [
        amber_par(12, "EndBent_cheekThickness = 8 in", "Cheek web thickness outside each cap end; notebook CONFIG end_bents.*.cheek_thickness_in (D-026)", nl),
        amber_par(12, "EndBent_lugProjection = 6 in", "Bottom and rear lug projection; notebook CONFIG end_bents.*.lug_projection_in (D-026 DXF)", nl),
        amber_par(12, "EndBent_lugWidth = 5.5 in", "Lug width on the cheek outer face; notebook CONFIG end_bents.*.lug_width_in (D-026 DXF)", nl),
        amber_par(12, "EndBent_mseJoint = 0.5 in", "MSE panel joint to cheek and lug faces; notebook CONFIG end_bents.*.mse_joint_in (D-026)", nl),
        amber_par(12, "EndBentCage_envelope = " + new_defs["EndBentCage_envelope"],
                  "Out-to-out of the cap with both cheek webs; the cap cages and the cap design reports use this 251-in envelope (D-027)",
                  nl, amber=False, cache=new_rep.text("EndBentCage_envelope")),
    ]
    text = rep(text, cap_len_caption, cap_len_caption + nl + nl.join(extra), "EndBentCap_length caption")
    edits += [{"report": "BridgeGeometry_2Beam", "formula": f, "change": "added"} for f in
              ["EndBent_cheekThickness = 8 in", "EndBent_lugProjection = 6 in", "EndBent_lugWidth = 5.5 in", "EndBent_mseJoint = 0.5 in",
               "EndBentCage_envelope = " + new_defs["EndBentCage_envelope"]]]

    # --- (c) pier cap covers after EndBent_coverSide ------------------------------------------
    cover_caption = ' ' * 12 + '<paragraph fontfamily="Times New Roman" fontsize="10" leftindent="0" spacingafter="7">Clear cover to outside of transverse reinforcement.</paragraph>'
    side_block = amber_par(12, "EndBent_coverSide = 3 in", "Clear cover to outside of transverse reinforcement.", nl)
    covers = [amber_par(12, f"PierCap_cover{s} = 3 in", f"Clear cover to the hoop, pier cap, {w}; moved here from C005 (removed 19 October 2026).", nl)
              for s, w in (("Top", "top"), ("Bottom", "bottom"), ("Side", "sides"))]
    text = rep(text, side_block, side_block + nl + nl.join(covers), "EndBent_coverSide block")
    edits += [{"report": "BridgeGeometry_2Beam", "formula": f"PierCap_cover{s} = 3 in", "change": "added (moved from C005)"} for s in ("Top", "Bottom", "Side")]

    # --- (d) camber inputs ----------------------------------------------------------------------
    for n, (span, key) in {"Beam_camber_1": (1, 0), "Beam_camber_2": (2, 1)}.items():
        old_f, new_f = f"{n} = 1 in", f"{n} = {CAMBER[n]}"
        text = rep(text, f'<dynexp formula="{old_f}"', f'<dynexp formula="{new_f}"', f"{n} formula")
        text = rep(text, f"<expbody>{old_f}</expbody>", f"<expbody>{new_f}</expbody>", f"{n} expbody")
        old_c = f"Upward parabolic camber in span {span}, zero at idealized supports."
        text = rep(text, f">{old_c}</paragraph>",
                   f">{old_c} Net camber at 120 days, Mathcad NetCamber for span {span}; notebook CONFIG spans[{key}].camber_in.</paragraph>", f"{n} caption")
        edits.append({"report": "BridgeGeometry_2Beam", "formula": new_f, "was": old_f, "change": "placeholder replaced by the notebook net camber"})

    # --- (e) support drop ---------------------------------------------------------------------
    # The existing formula is kept (formula and attributes unchanged); with the notebook cambers it equals the notebook drop.
    assert abs(new_rep.V("Beam_support_drop").v / 12 - 3.7147642885879173) < 1e-12, "formula no longer reproduces the notebook support drop"
    old_cap = "Common downward offset from the profile support chord. Valid for the selected centered crowned section and tangent profiles within each span."
    text = rep(text, f">{old_cap}</paragraph>",
               f">{old_cap} Equals the notebook common support drop 3.7148 ft (model e9b41b8eaf) with the notebook net cambers.</paragraph>",
               "Beam_support_drop caption")
    edits.append({"report": "BridgeGeometry_2Beam", "formula": f"Beam_support_drop = {defs['Beam_support_drop']}",
                  "change": "formula and attributes kept; caption extended; cached result refreshed 3.751 -> 3.715 ft (equals the notebook 3.7147642885879173 ft)"})

    # --- (f) text mentions of C005 / stale station numbers ----------------------------------------
    pier_note = "Report additional end allowance; C005 retains 3.44 in and is unchanged by user direction."
    text = rep(text, pier_note,
               "Report additional end allowance (3 in; 15-in pile end clearance, as the notebook pier.pile_end_clear_in); C005 was removed from the journal on 19 October 2026 (T014).",
               "PierCap_endDetail caption")
    text = rep(text, "regenerate the structural analysis forces before final use of C005.",
               "regenerate the structural analysis forces before final use of the pier cap design (CapDesignPier).", "C005 note in notebook section")
    text = rep(text, "correspond to 54.50 and 157.49 in from the cap end.", "correspond to 66.00 and 168.99 in from the cap end (36.5-in first pile center).", "audit stations")
    edits += [{"report": "BridgeGeometry_2Beam", "text": "PierCap_endDetail caption", "change": "C005 sentence replaced"},
              {"report": "BridgeGeometry_2Beam", "text": "NotebookGeometryUpdate20260929 note", "change": "C005 mention replaced by CapDesignPier"},
              {"report": "BridgeGeometry_2Beam", "text": "bearing audit stations paragraph", "change": "54.50/157.49 in -> 66.00/168.99 in (endCenter 25 -> 36.5 in)"}]
    return text, closure, refreshed


def split_rhs(formula):
    return G.split_to(formula)[0]


# evaluate a table-cell formula (no assignment) with the display unit
def _eval_cell(self, formula):
    expr, unit = G.split_to(formula)
    return G.fmt(self.eval_formula(expr), unit)


G.Report.eval_cell = _eval_cell


# --------------------------------------------------------------------------------------------
# 4. FBMPEndBent / PierWallFins / FBMPPier
# --------------------------------------------------------------------------------------------
def edit_fbmp_endbent():
    text = part("FBMPEndBent")
    nl = nl_of(text, "FBMPEndBent")
    for name, old_val, new_rhs, cache, cap_old, cap_new in [
        ("EBSteel_fc", "5.5 ksi", "Materials.Substructure_fc to ksi", "5.5 ksi",
         "Cap concrete strength in the report; this is not a pile concrete material definition.",
         "Cap concrete strength in the report, live from Materials; this is not a pile concrete material definition."),
        ("EBSteel_fy", "60 ksi", "Materials.Rebar_fy to ksi", "60 ksi", "Reinforcing yield strength.", "Reinforcing yield strength, live from Materials."),
        ("EBSteel_Es", "29000 ksi", "Materials.Rebar_Es to ksi", "29000 ksi", "Reinforcing modulus.", "Reinforcing modulus, live from Materials."),
    ]:
        old_tag = f'<dynexp formula="{name} = {old_val}" mathlayout="on" showsteps="False" seplines="False" style="Required Input">'
        new_tag = f'<dynexp formula="{name} = {new_rhs}" mathlayout="on" showsteps="False" seplines="False">'
        text = rep(text, old_tag, new_tag, f"{name} dynexp")
        text = rep(text, f"<expbody>{name} = {old_val}</expbody>",
                   f"<expbody>{name} = {new_rhs}</expbody>" + nl + " " * 20 + f"<expresult>{NBSP}= {cache}</expresult>", f"{name} expbody")
        # the caption is the paragraph that follows the definition paragraph
        i = text.index(new_tag)
        j = text.index("</paragraph>", i)
        k = text.index(f">{cap_old}</paragraph>", j)
        assert k - j < 200, f"{name}: caption not adjacent"
        text = text[:k] + f">{cap_new}</paragraph>" + text[k + len(f">{cap_old}</paragraph>"):]
        edits.append({"report": "FBMPEndBent", "formula": f"{name} = {new_rhs}", "was": f"{name} = {old_val}",
                      "change": "amber literal replaced by live reference to Materials; Required Input style dropped; cached result unchanged"})
    return text


def edit_pierwallfins():
    text = part("PierWallFins")
    for old, new in [("f_c = PierCapDesign.fc to ksi", "f_c = Materials.Substructure_fc to ksi"),
                     ("f_y = PierCapDesign.fy to ksi", "f_y = Materials.Rebar_fy to ksi"),
                     ("E_s = PierCapDesign.Es to ksi", "E_s = Materials.Rebar_Es to ksi"),
                     ("c_w = PierCapDesign.C_s to in", "c_w = BridgeGeometry_2Beam.PierCap_coverSide to in")]:
        text = rep(text, old, new, old, n=2)
        edits.append({"report": "PierWallFins", "formula": new, "was": old, "change": "consumer moved off C005; cached result unchanged"})
    for old, new in [("Class IV concrete strength from the active pier-cap calculation.", "Class IV concrete strength, live from Materials."),
                     ("Reinforcing yield strength from the active pier-cap calculation.", "Reinforcing yield strength, live from Materials."),
                     ("Reinforcing elastic modulus.", "Reinforcing elastic modulus, live from Materials.")]:
        text = rep(text, f">{old}</paragraph>", f">{new}</paragraph>", old)
    m = re.search(r"c_w = BridgeGeometry_2Beam\.PierCap_coverSide to in</expbody>\s*<expresult>[^<]*</expresult>\s*</dynexp>\s*</paragraph>\s*<paragraph [^>]*>([^<]*)</paragraph>", text)
    assert m, "c_w caption not found"
    edits.append({"report": "PierWallFins", "text": f"c_w caption (unchanged): {m.group(1)}"})
    return text


def edit_fbmp_pier():
    text = part("FBMPPier")
    text = rep(text, "User direction remains: C005 is completely unchanged.",
               "C005 was removed from the journal on 19 October 2026 (T014); the pier cap design record is CapDesignPier.", "FBMPPier user direction")
    text = rep(text, "C005 retains its earlier 3.44-in input.", "the former C005 (removed 19 October 2026) used an earlier 3.44-in input.", "FBMPPier 3.44 in")
    edits.append({"report": "FBMPPier", "text": "two C005 sentences replaced (removal note)"})
    return text


# --------------------------------------------------------------------------------------------
# 5. PedBridge / DecisionLog
# --------------------------------------------------------------------------------------------
def edit_pedbridge():
    global edits
    text = part("PedBridge")
    nl = nl_of(text, "PedBridge")
    par_open = ' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">'
    c005 = par_open + nl + ' ' * 12 + '<link address="#PierCapDesign">C005 - Pier Cap Design</link>' + nl + ' ' * 8 + '</paragraph>' + nl
    text = rep(text, c005, "", "PedBridge C005 link paragraph")
    heading = '<heading level="1" keepwithnext="True">Project basis and geometry</heading>'
    link = par_open + nl + ' ' * 12 + '<link address="#ProjectInfo">Project information and stamp</link>' + nl + ' ' * 8 + '</paragraph>'
    text = rep(text, heading, heading + nl + link, "PedBridge heading")
    old_s = "C005 is completely unchanged and reinforcement remains separate."
    new_s = "The former C005 (removed 19 October 2026) was left unchanged in that revision and reinforcement remains separate."
    s0 = text.index(old_s)
    context = text[text.rfind("The matching raw XML", 0, s0):s0 + len(old_s)]
    text = rep(text, old_s, new_s, "PedBridge C005 sentence")
    edits += [{"report": "PedBridge", "link": "#PierCapDesign", "change": "link paragraph removed"},
              {"report": "PedBridge", "link": "#ProjectInfo", "text": "Project information and stamp", "change": "index link added"},
              {"report": "PedBridge", "text": new_s, "was": old_s}]
    return text, context + " => " + new_s


DECISION = ("C005 (PierCapDesign) removed from the journal by user direction; CapDesignPier is the pier cap record. Material properties moved to Materials; "
            "pier cap covers to Bridge Geometry. End-bent cap geometry aligned with the geometry notebook (D-026/D-036: 27.5-in pile end clearance, 235-in cap, "
            "251-in cage envelope with 8-in cheek webs); beam cambers and the support drop taken from the notebook build e9b41b8eaf. ProjectInfo added and a live "
            "project stamp placed on every calculation report. Journal task T014.")


def edit_decisionlog():
    text = part("DecisionLog")
    nl = "\r\n" if text.endswith("</section>\r\n    </report>") else "\n"   # file has a few LF-only lines; follow the tail
    tail =' ' * 8 + '</section>' + nl + ' ' * 4 + '</report>'
    assert text.endswith(tail), "DecisionLog does not end with a section inside the report"
    once(text, '<section name="RampSlabBackwallDecision20261016" capture="False" hide="false">', "latest entry")
    entry = nl.join([' ' * 8 + '<section name="CoherenceDecision20261019" capture="False" hide="false">',
                     ' ' * 12 + '<heading level="1" keepwithnext="True">2026-10-19 - C005 removed; geometry aligned with the notebook; project stamp</heading>',
                     ' ' * 12 + f'<paragraph fontfamily="Times New Roman" fontsize="11" leftindent="0" spacingafter="7">{escape(DECISION)}</paragraph>',
                     ' ' * 8 + '</section>'])
    text = text[:-len(' ' * 4 + '</report>') - len(nl)] + nl + entry + nl + ' ' * 4 + '</report>'
    edits.append({"report": "DecisionLog", "text": DECISION, "change": "entry appended (19 October 2026)"})
    return text


# --------------------------------------------------------------------------------------------
# Phase A: all components except the cap reports
# --------------------------------------------------------------------------------------------
def build_all():
    out = {}
    out["report:ProjectInfo"] = build_project_info()
    geometry, closure, refreshed = edit_geometry()
    texts = {"Materials": edit_materials(), "BridgeGeometry_2Beam": geometry, "FBMPEndBent": edit_fbmp_endbent(),
             "FBMPPier": edit_fbmp_pier(), "PierWallFins": edit_pierwallfins()}
    ped, ped_sentence = edit_pedbridge()
    out["report:PedBridge"] = ped.encode("utf-8")
    out["report:DecisionLog"] = edit_decisionlog().encode("utf-8")
    placements = {}
    for name in STAMPED:
        text = texts.get(name) or part(name)
        text, tag, line = insert_stamp(name)(text)
        out[f"report:{name}"] = text.encode("utf-8")
        placements[name] = {"before": tag, "line": line}
    out["report:PierCapDesign"] = b""
    for name in CAP_REPORTS:
        out[f"report:{name}"] = base.part(f"report:{name}")
    assert set(out) == set(mapping), f"component set mismatch: {sorted(set(mapping) ^ set(out))}"
    # every other component file is a base copy
    return out, placements, refreshed, ped_sentence


def write_components(out):
    for key, data in out.items():
        (TASK / "components" / mapping[key]).write_bytes(data)


# --------------------------------------------------------------------------------------------
# Phase B: cap reports from the generator, run against a preview journal
# --------------------------------------------------------------------------------------------
def cap_phase(out):
    readme = (ROOT / "cap_bpad" / "README.md").read_text(encoding="utf-8")
    assert "EndBentCage_envelope" in readme, "the cap generator is not ready (cap_bpad/README.md does not mention EndBentCage_envelope)"
    repl = {k: v for k, v in out.items() if k not in {f"report:{n}" for n in CAP_REPORTS}}
    repl.update({k: b"" for k in ("report:PierCapDesign",)})
    adds = ["report:ProjectInfo"]
    preview = base.replace({k: v for k, v in repl.items() if k != "report:ProjectInfo"} | {"report:ProjectInfo": out["report:ProjectInfo"]}, adds)
    (TASK / "preview-journal.bpad").write_bytes(preview)
    j = Journal(preview)
    assert "report:PierCapDesign" not in j.spans and "report:ProjectInfo" in j.spans
    cmd = [str(ROOT / ".venv" / "Scripts" / "python.exe"), str(ROOT / "scripts" / "build_cap_bpad.py"), "--journal", str(TASK / "preview-journal.bpad")]
    done = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    (TASK / "cap-build.log").write_text(done.stdout + "\n--- stderr ---\n" + done.stderr, encoding="utf-8")
    assert done.returncode == 0, f"build_cap_bpad.py failed (see tasks/T014/cap-build.log): {done.stderr[-800:]}"
    frag = ROOT / "cap_bpad" / "journal"
    verification = json.loads((frag / "verification.json").read_text(encoding="utf-8"))
    recorded = {verification["basis"]["report_name"]: verification["basis"]["fragment_sha256"]}
    recorded.update({r["report_name"]: r["fragment_sha256"] for r in verification["reports"]})
    for name in CAP_REPORTS:
        raw = (frag / f"{name}.xml").read_bytes()
        assert sha(raw) == recorded[name], f"{name}: fragment differs from verification.json"
        data = raw[:-2] if raw.endswith(b"\r\n") else raw[:-1] if raw.endswith(b"\n") else raw
        root = E.fromstring(data)
        assert root.tag == "report" and root.get("name") == name
        assert data.count(b'name="ProjectStamp"') == 1, f"{name}: stamp table not exactly once"
        out[f"report:{name}"] = data
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap-reports", action="store_true", help="also build the preview journal and refresh the four cap reports")
    args = ap.parse_args()
    out, placements, refreshed, ped_sentence = build_all()
    if args.cap_reports:
        out = cap_phase(out)
    write_components(out)
    changed = sorted(k for k, v in out.items() if k not in base.spans or base.part(k) != v)
    (TASK / "definitions.json").write_text(json.dumps(
        {"edited": edits, "refreshed_caches": cache_log, "stamp_placement": placements,
         "pedbridge_sentence": ped_sentence, "cap_reports_refreshed": bool(args.cap_reports)}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"changed_component_files": changed, "refreshed_cache_count": len(cache_log),
                      "stamp_placements": placements, "cap_reports_refreshed": bool(args.cap_reports)}, indent=2))
    print("\nrefreshed caches:")
    for c in cache_log:
        print("  ", c.get("name") or c.get("cell"), "|", c["was"], "->", c["now"])
    print("\nPedBridge sentence:", ped_sentence)


if __name__ == "__main__":
    main()
