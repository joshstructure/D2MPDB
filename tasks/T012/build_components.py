"""T012: write the six registered component files from base.bpad.

Four new cap-design report modules are copied byte for byte from
cap_bpad/journal/. PedBridge and FBMPEndBent are edited by exact-string
surgery (every old string must occur exactly once). Nothing is re-serialized.
Rerunnable: every component file is rebuilt from base.bpad, never from itself.
Standard library plus lxml.
"""
from decimal import Decimal
from pathlib import Path
from lxml import etree as E
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402

FRAGMENTS = ROOT / "cap_bpad" / "journal"
ADDED = ["CapDesignBasis", "CapDesignEndBentOne", "CapDesignEndBentTwo", "CapDesignPier"]
OWNER = "CapDesignEndBentOne"
BASIS = "CapDesignBasis"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(text, old, label):
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly one occurrence, found {n}: {old[:90]!r}"
    return n


def replace_once(text, old, new, label):
    once(text, old, label)
    return text.replace(old, new)


# --------------------------------------------------------------------------
# Inputs: base journal, component mapping, fragments (checked against the build)
# --------------------------------------------------------------------------
base = Journal.load(TASK / "base.bpad")
mapping = json.loads((TASK / "components.json").read_text(encoding="utf-8"))
expected_keys = {f"report:{n}" for n in ADDED} | {"report:PedBridge", "report:FBMPEndBent"}
assert set(mapping) == expected_keys, f"unexpected component keys: {sorted(mapping)}"

missing = [n for n in ADDED if not (FRAGMENTS / f"{n}.xml").is_file()]
assert not missing and (FRAGMENTS / "coherence.json").is_file(), f"fragment folder incomplete: {missing}"
verification = json.loads((FRAGMENTS / "verification.json").read_text(encoding="utf-8"))
recorded = {verification["basis"]["report_name"]: verification["basis"]["fragment_sha256"]}
recorded.update({r["report_name"]: r["fragment_sha256"] for r in verification["reports"]})

fragments = {}
for name in ADDED:
    raw = (FRAGMENTS / f"{name}.xml").read_bytes()
    assert sha(raw) == recorded[name], f"{name}: fragment differs from verification.json (rebuild in progress?)"
    data = raw
    if data.endswith(b"\r\n"):
        data = data[:-2]
    elif data.endswith(b"\n"):
        data = data[:-1]
    root = E.fromstring(data)
    assert root.tag == "report" and root.get("name") == name, f"{name}: not a bare report element"
    assert f"report:{name}" not in base.spans, f"{name} already exists in the base journal"
    fragments[name] = (data, root)

# --------------------------------------------------------------------------
# Owner values, read from the fragments (not hard-coded)
# --------------------------------------------------------------------------
owner_root = fragments[OWNER][1]
literals = {}
for e in owner_root.iter():
    m = re.fullmatch(r"\s*([^\W\d]\w*)\s*=\s*(\d+)\s*", e.get("formula", ""))
    if m:
        literals.setdefault(m[1], []).append(int(m[2]))
need = ["n_N1", "Bar_N1", "n_P1", "Bar_P", "n_B1", "Bar_B", "n_skin", "Bar_skin"]
for name in need:
    assert len(literals.get(name, [])) == 1, f"{OWNER}.{name} must be defined exactly once as an integer literal"
v = {name: literals[name][0] for name in need}

area_table = None
for e in fragments[BASIS][1].iter():
    f = e.get("formula", "")
    if f.startswith("Ab(k)"):
        area_table = {int(k): Decimal(a) for k, a in re.findall(r"k == (\d+), ([0-9.]+) in\^2", f)}
assert area_table, "CapDesignBasis.Ab(k) table not found"
for bar in (v["Bar_N1"], v["Bar_P"], v["Bar_B"], v["Bar_skin"]):
    assert bar in area_table, f"bar #{bar} not in the shared bar table"


def fmt(d):
    return format(d.normalize(), "f")


area = {"top": area_table[v["Bar_N1"]], "bottom": area_table[v["Bar_P"]],
        "added": area_table[v["Bar_B"]], "skin": area_table[v["Bar_skin"]]}
As = {"AsTop": v["n_N1"] * area["top"], "AsPile": v["n_P1"] * area["bottom"]}
As["AsSpan"] = As["AsPile"] + v["n_B1"] * area["added"]
As["AsSkinSide"] = v["n_skin"] * area["skin"]
added_total = v["n_B1"] * area["added"]

# --------------------------------------------------------------------------
# PedBridge: four index paragraphs after the C005 link
# --------------------------------------------------------------------------
ped = base.part("report:PedBridge").decode("utf-8")
NL = "\r\n" if "\r\n" in ped else "\n"
assert ped.count("\n") == (ped.count("\r\n") if NL == "\r\n" else ped.count("\n")), "PedBridge has mixed line endings"
anchor = ('<link address="#PierCapDesign">C005 - Pier Cap Design</link>' + NL +
          " " * 8 + "</paragraph>")
links = [("CapDesignBasis", "Cap design basis - shared factors (19 October 2026)"),
         ("CapDesignEndBentOne", "Cap design - End Bent 1 (distilled, 19 October 2026 case)"),
         ("CapDesignEndBentTwo", "Cap design - End Bent 2 (distilled, 19 October 2026 case)"),
         ("CapDesignPier", "Cap design - Pier (distilled, 19 October 2026 case)")]
for target, _ in links:
    assert f'address="#{target}"' not in ped, f"PedBridge already links {target}"
insertion = "".join(
    NL + " " * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + NL +
    " " * 12 + f'<link address="#{target}">{text}</link>' + NL + " " * 8 + "</paragraph>"
    for target, text in links)
ped_new = replace_once(ped, anchor, anchor + insertion, "PedBridge anchor")

# --------------------------------------------------------------------------
# FBMPEndBent: edits confined to section EBCurrentDesignRecord
# --------------------------------------------------------------------------
fb = base.part("report:FBMPEndBent").decode("utf-8")
FNL = "\r\n" if "\r\n" in fb else "\n"
assert fb.count("\n") == (fb.count("\r\n") if FNL == "\r\n" else fb.count("\n")), "FBMPEndBent has mixed line endings"
s_open = '<section name="EBCurrentDesignRecord"'
once(fb, s_open, "section open")
s0 = fb.index(s_open)
s1 = fb.index("</section>", s0) + len("</section>")
sec = fb[s0:s1]
assert sec.count("<section") == 1 and sec.count("</section>") == 1, "unexpected nested sections"

# -- intro paragraph under the level-0 heading -----------------------------
H0 = '<heading level="0" keepwithnext="True" pagebreakbefore="break">Current end-bent cap design record — 8 October 2026</heading>'
intro = ("Block 2 (longitudinal reinforcement) is live from CapDesignEndBentOne, the 19 October 2026 case "
         "selected under D-051. Blocks 1 and 3 remain the 8 October record pending refresh.")
intro_xml = (FNL + " " * 12 + '<paragraph fontfamily="Times New Roman" fontsize="11" leftindent="0" '
             f'spacingafter="7" background="#FFF8E9">{intro}</paragraph>')
sec = replace_once(sec, H0, H0 + intro_xml, "level-0 heading")

# -- block 2 ---------------------------------------------------------------
H2 = '<heading level="1" keepwithnext="True" pagebreakbefore="break">2. Current longitudinal reinforcement</heading>'
H3 = '<heading level="1" keepwithnext="True" pagebreakbefore="break">3. Actual transverse schedule</heading>'
once(sec, H2, "block 2 heading")
once(sec, H3, "block 3 heading")
b0, b1 = sec.index(H2), sec.index(H3)
assert b0 < b1
block = sec[b0:b1]
orig_block = block

inputs = [
    # name, old rhs, new rhs, old caption, new caption, cached result
    ("EBSteel_topCount", "4", f"{OWNER}.n_N1",
     "Continuous #6 top bars; one row.",
     f"Continuous top bars, row 1; live from the current cap design ({OWNER}).",
     f" = {v['n_N1']}"),
    ("EBSteel_topAreaEach", "0.44 in^2", f"{BASIS}.Ab({OWNER}.Bar_N1) to in^2",
     "Source area for one #6 bar.",
     "Area of one top bar from the shared bar table.",
     f" = {fmt(area['top'])} in^2"),
    ("EBSteel_bottomCount", "2", f"{OWNER}.n_P1",
     "Continuous #8 bottom bars at piles and between piles.",
     f"Continuous bottom bars at piles and between piles, row 1; live from {OWNER}.",
     f" = {v['n_P1']}"),
    ("EBSteel_bottomAreaEach", "0.79 in^2", f"{BASIS}.Ab({OWNER}.Bar_P) to in^2",
     "Source area for one #8 bar.",
     "Area of one continuous bottom bar.",
     f" = {fmt(area['bottom'])} in^2"),
    ("EBSteel_addedCount", "2", f"{OWNER}.n_B1",
     "Additional #5 bottom bars between piles, beyond the two continuous #8 bars; 90-degree hooked ends.",
     f"Added span bars between piles, row 1, beyond the continuous bottom bars; hooked ends; live from {OWNER}.",
     f" = {v['n_B1']}"),
    ("EBSteel_addedAreaEach", "0.31 in^2", f"{BASIS}.Ab({OWNER}.Bar_B) to in^2",
     "Source area for one #5 bar.",
     "Area of one added span bar.",
     f" = {fmt(area['added'])} in^2"),
    ("EBSteel_skinEachSide", "7", f"{OWNER}.n_skin",
     "Continuous #4 skin bars on each side, excluding top and bottom main bars.",
     f"Skin bars on each side, excluding top and bottom main bars; live from {OWNER}.",
     f" = {v['n_skin']}"),
    ("EBSteel_skinAreaEach", "0.20 in^2", f"{BASIS}.Ab({OWNER}.Bar_skin) to in^2",
     "Source area for one #4 bar.",
     "Area of one skin bar.",
     f" = {fmt(area['skin'])} in^2"),
]
definitions = []
for name, old, new, cap_old, cap_new, cache in inputs:
    tag_old = (f'<dynexp formula="{name} = {old}" mathlayout="on" showsteps="False" seplines="False" '
               'style="Required Input">')
    tag_new = f'<dynexp formula="{name} = {new}" mathlayout="on" showsteps="False" seplines="False">'
    block = replace_once(block, tag_old, tag_new, f"{name} dynexp")
    body_old = f"<expbody>{name} = {old}</expbody>"
    body_new = f"<expbody>{name} = {new}</expbody>" + FNL + " " * 20 + f"<expresult>{cache}</expresult>"
    block = replace_once(block, body_old, body_new, f"{name} expbody")
    block = replace_once(block, f">{cap_old}</paragraph>", f">{cap_new}</paragraph>", f"{name} caption")
    definitions.append({"report": "FBMPEndBent", "formula": f"{name} = {new}", "was": f"{name} = {old}",
                        "change": "amber literal replaced by live reference to the new owner"})

# -- derived definitions: formulas unchanged, caches refreshed -------------
cache_changes = {}
for name in ("AsTop", "AsPile", "AsSpan", "AsSkinSide"):
    pattern = re.compile(r"(<expbody>EBSteel_" + name + r" = [^<]*</expbody>\r?\n\s*<expresult>)([^<]*)(</expresult>)")
    hits = pattern.findall(block)
    assert len(hits) == 1, f"EBSteel_{name}: expected one cached definition, found {len(hits)}"
    new_cache = f" = {fmt(As[name])} in^2"
    cache_changes[f"EBSteel_{name}"] = {"was": hits[0][1], "now": new_cache}
    block = pattern.sub(lambda m, c=new_cache: m.group(1) + c + m.group(3), block)

# -- summary table ---------------------------------------------------------
t_open = '<table name="EBLongitudinalSummary"'
once(block, t_open, "summary table")
t0 = block.index(t_open)
t1 = block.index("</table>", t0) + len("</table>")
old_table = block[t0:t1]
style_line = re.search(r"<stylerule range=\"A1:C5\"[^\r\n]*", old_table).group(0)
assert style_line.endswith("/>")
assert old_table.count('range="A1:C5"') == 1 and old_table.count('range="A1:C1"') == 1 and old_table.count('range="A2:C5"') == 1
new_style = style_line.replace('range="A1:C5"', 'range="A1:D6"')
head_style = re.search(r"<stylerule range=\"A1:C1\"[^\r\n]*", old_table).group(0).replace('range="A1:C1"', 'range="A1:D1"')
body_style = re.search(r"<stylerule range=\"A2:C5\"[^\r\n]*", old_table).group(0).replace('range="A2:C5"', 'range="A2:D6"')
i20, i24 = " " * 20, " " * 24


def cell_text(text):
    return f'<c capture="False"><textvalue>{text}</textvalue></c>'


def cell_formula(formula, num):
    return f'<c capture="False" formula="{formula}"><num>{num}</num></c>'


rows = [
    [cell_text("Family"), cell_text("Bars (live)"), cell_text("Bar no. (live)"), cell_text("Area (live)")],
    [cell_text("Top"), cell_formula(f"{OWNER}.n_N1", v["n_N1"]), cell_formula(f"{OWNER}.Bar_N1", v["Bar_N1"]),
     cell_formula("EBSteel_AsTop to in^2", f"{fmt(As['AsTop'])} in^2")],
    [cell_text("Bottom at piles (continuous)"), cell_formula(f"{OWNER}.n_P1", v["n_P1"]),
     cell_formula(f"{OWNER}.Bar_P", v["Bar_P"]), cell_formula("EBSteel_AsPile to in^2", f"{fmt(As['AsPile'])} in^2")],
    [cell_text("Added span bars"), cell_formula(f"{OWNER}.n_B1", v["n_B1"]), cell_formula(f"{OWNER}.Bar_B", v["Bar_B"]),
     cell_formula("EBSteel_addedCount*EBSteel_addedAreaEach to in^2", f"{fmt(added_total)} in^2")],
    [cell_text("Bottom between piles (total)"), cell_text("continuous + added"), cell_text("—"),
     cell_formula("EBSteel_AsSpan to in^2", f"{fmt(As['AsSpan'])} in^2")],
    [cell_text("Skin, each side"), cell_formula(f"{OWNER}.n_skin", v["n_skin"]), cell_formula(f"{OWNER}.Bar_skin", v["Bar_skin"]),
     cell_formula("EBSteel_AsSkinSide to in^2", f"{fmt(As['AsSkinSide'])} in^2")],
]
lines = ['<table name="EBLongitudinalSummary" capture="False" colwidths="1:150, 2:90, 3:90, 4:120">',
         i20 + new_style, i20 + head_style, i20 + body_style]
for row in rows:
    lines.append(i20 + "<row>")
    lines.extend(i24 + c for c in row)
    lines.append(i20 + "</row>")
lines.append(" " * 16 + "</table>")
new_table = FNL.join(lines)
block = block[:t0] + new_table + block[t1:]
definitions.extend({"report": "FBMPEndBent", "table": "EBLongitudinalSummary", "formula": f}
                   for f in [f"{OWNER}.n_N1", f"{OWNER}.Bar_N1", f"{OWNER}.n_P1", f"{OWNER}.Bar_P", f"{OWNER}.n_B1",
                             f"{OWNER}.Bar_B", f"{OWNER}.n_skin", f"{OWNER}.Bar_skin", "EBSteel_AsTop to in^2",
                             "EBSteel_AsPile to in^2", "EBSteel_addedCount*EBSteel_addedAreaEach to in^2",
                             "EBSteel_AsSpan to in^2", "EBSteel_AsSkinSide to in^2"])

# -- closing paragraph -----------------------------------------------------
closing_pattern = re.compile(r">Additional top rows, second bottom rows and longitudinal U tension-leg counts are zero\.[^<]*</paragraph>")
assert len(closing_pattern.findall(block)) == 1, "closing paragraph not found exactly once"
closing = (">Additional top rows and second bottom rows are zero in the current case. The transverse schedule below is the "
           "8 October record; the current actual station schedule is in the cap design report of CapDesignEndBentOne.</paragraph>")
block = closing_pattern.sub(lambda m: closing, block)

sec = sec[:b0] + block + sec[b1:]
fb_new = fb[:s0] + sec + fb[s1:]

# Nothing outside the section moved.
assert fb_new[:s0] == fb[:s0] and fb_new[s0 + len(sec):] == fb[s1:]
# The three materials inputs remain literal Required Input owners.
for name, val in (("EBSteel_fc", "5.5 ksi"), ("EBSteel_fy", "60 ksi"), ("EBSteel_Es", "29000 ksi")):
    once(fb_new, f'<dynexp formula="{name} = {val}" mathlayout="on" showsteps="False" seplines="False" style="Required Input">', name)

# --------------------------------------------------------------------------
# Write the component files named by components.json
# --------------------------------------------------------------------------
out = {f"report:{n}": fragments[n][0] for n in ADDED}
out["report:PedBridge"] = ped_new.encode("utf-8")
out["report:FBMPEndBent"] = fb_new.encode("utf-8")
components = TASK / "components"
for key, data in out.items():
    (components / mapping[key]).write_bytes(data)

summary = {
    "task": "T012",
    "owner_values": v,
    "bar_areas_in2": {k: fmt(a) for k, a in area.items()},
    "steel_areas_in2": {k: fmt(a) for k, a in As.items()},
    "added_bars_total_in2": fmt(added_total),
    "cache_changes": cache_changes,
    "components": {key: {"file": mapping[key], "bytes": len(data), "sha256": sha(data)} for key, data in sorted(out.items())},
    "added_fragment_sha256": {n: sha(fragments[n][0]) for n in ADDED},
}

# definitions.json: every formula introduced or changed.
def defined_names(root):
    names = []
    for e in root.iter():
        m = re.match(r"^\s*([^\W\d]\w*(?:\([^)]*\))?)\s*=(?!=)", e.get("formula", ""))
        if m:
            names.append(m[1])
    return names


added_defs = []
for n in ADDED:
    root = fragments[n][1]
    names = defined_names(root)
    added_defs.append({"report": n, "added_module": True, "formula_bearing_elements": sum(1 for e in root.iter() if "formula" in e.attrib),
                       "definitions": len(names), "defined_names": names})
for target, text in links:
    definitions.append({"report": "PedBridge", "link": f"#{target}", "text": text, "change": "index link added"})
write = {"edited_formulas": definitions, "derived_cache_refreshes": cache_changes, "added_reports": added_defs}
(TASK / "definitions.json").write_text(json.dumps(write, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({**summary, "definitions_file": "definitions.json", "edited_formulas": len(definitions),
                  "added_definitions": {d["report"]: d["definitions"] for d in added_defs}}, indent=2, ensure_ascii=False))
