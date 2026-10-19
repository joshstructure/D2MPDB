"""T015: write the four registered component files from base.bpad.

Three new pile-design report modules are copied byte for byte from
pile_bpad/fragments/. PedBridge is edited by exact-string surgery (the anchor
must occur exactly once). Nothing is re-serialized. Rerunnable: every component
file is rebuilt from base.bpad, never from itself. Standard library plus lxml.
"""
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
from pile_design.mathcad import package_revision  # noqa: E402

PILE = ROOT / "pile_bpad"
FRAGMENTS = PILE / "fragments"
ADDED = ["PileDesignEndBentOne", "PileDesignEndBentTwo", "PileDesignPier"]
DOCUMENTS = {"PileDesignEndBentOne": "End Bent 1 Pile Design.bpad", "PileDesignEndBentTwo": "End Bent 2 Pile Design.bpad",
             "PileDesignPier": "Pier Pile Design.bpad"}
LINKS = [("PileDesignEndBentOne", "Pile design - End Bent 1 (distilled, 19 October 2026 case)"),
         ("PileDesignEndBentTwo", "Pile design - End Bent 2 (distilled, 19 October 2026 case)"),
         ("PileDesignPier", "Pile design - Pier (distilled, 19 October 2026 case)")]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new, label):
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly one occurrence, found {n}: {old[:90]!r}"
    return text.replace(old, new)


def shape(el):
    """An element reduced to what Blockpad reads: tags, attributes and text, ignoring the indentation between elements."""
    return (el.tag, sorted(el.attrib.items()), (el.text or "").strip(), [shape(c) for c in el], (el.tail or "").strip())


# --------------------------------------------------------------------------
# Inputs: base journal, component mapping, fragments (checked against the build)
# --------------------------------------------------------------------------
base = Journal.load(TASK / "base.bpad")
mapping = json.loads((TASK / "components.json").read_text(encoding="utf-8"))
expected_keys = {f"report:{n}" for n in ADDED} | {"report:PedBridge"}
assert set(mapping) == expected_keys, f"unexpected component keys: {sorted(mapping)}"

verification = {r["report_name"]: r for r in json.loads((PILE / "verification.json").read_text(encoding="utf-8"))}
assert set(verification) == set(ADDED), f"verification.json reports: {sorted(verification)}"
revision = package_revision()
fragments = {}
for name in ADDED:
    v = verification[name]
    assert v["package_revision"] == revision, f"{name}: verification.json is for another package revision (rebuild: scripts/build_pile_bpad.py)"
    assert v["status"] == "✓ All Checks Pass", f"{name}: unexpected status {v['status']!r}"
    document = (PILE / DOCUMENTS[name]).read_bytes()
    assert sha(document) == v["bpad_sha256"], f"{name}: {DOCUMENTS[name]} differs from verification.json"
    raw = (FRAGMENTS / f"{name}.xml").read_bytes()
    data = raw
    if data.endswith(b"\r\n"):
        data = data[:-2]
    elif data.endswith(b"\n"):
        data = data[:-1]
    root = E.fromstring(data)
    assert root.tag == "report" and root.get("name") == name, f"{name}: not a bare report element"
    assert f"report:{name}" not in base.spans, f"{name} already exists in the base journal"
    doc_report = E.fromstring(Journal(document).part(f"report:{name}"))
    assert shape(doc_report) == shape(root), f"{name}: the fragment differs from the report in {DOCUMENTS[name]}"
    fragments[name] = (data, root)

# --------------------------------------------------------------------------
# PedBridge: three index paragraphs after the CapDesignPier link
# --------------------------------------------------------------------------
ped = base.part("report:PedBridge").decode("utf-8")
NL = "\r\n" if "\r\n" in ped else "\n"
assert ped.count("\n") == (ped.count("\r\n") if NL == "\r\n" else ped.count("\n")), "PedBridge has mixed line endings"
anchor = ('<link address="#CapDesignPier">Cap design - Pier (distilled, 19 October 2026 case)</link>' + NL +
          " " * 8 + "</paragraph>")
for target, _ in LINKS:
    assert f'address="#{target}"' not in ped, f"PedBridge already links {target}"
insertion = "".join(
    NL + " " * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + NL +
    " " * 12 + f'<link address="#{target}">{text}</link>' + NL + " " * 8 + "</paragraph>"
    for target, text in LINKS)
ped_new = replace_once(ped, anchor, anchor + insertion, "PedBridge anchor")

# --------------------------------------------------------------------------
# Write the component files named by components.json
# --------------------------------------------------------------------------
out = {f"report:{n}": fragments[n][0] for n in ADDED}
out["report:PedBridge"] = ped_new.encode("utf-8")
components = TASK / "components"
for key, data in out.items():
    (components / mapping[key]).write_bytes(data)


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
edits = [{"report": "PedBridge", "link": f"#{t}", "text": text, "change": "index link added"} for t, text in LINKS]
(TASK / "definitions.json").write_text(json.dumps({"edited_formulas": edits, "derived_cache_refreshes": {}, "added_reports": added_defs},
                                                  indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({
    "task": "T015", "package_revision": revision,
    "components": {key: {"file": mapping[key], "bytes": len(data), "sha256": sha(data)} for key, data in sorted(out.items())},
    "fragment_sha256": {n: sha(fragments[n][0]) for n in ADDED},
    "added_definitions": {d["report"]: d["definitions"] for d in added_defs},
    "definitions_file": "definitions.json", "edited_formulas": len(edits)}, indent=2, ensure_ascii=False))
