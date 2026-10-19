"""T017: write the five registered component files from base.bpad (rerunnable, byte-surgical).

The distilled end-bent backwall report (EndBentBackwallDesign, journal edition with live references) is copied byte for
byte from end_bent_walls/bpad/journal/ after its verification record is checked against the current notebook package.
PedBridge, BridgeGeometry_2Beam, FoundationModeling and DecisionLog are edited by exact-substring surgery (every anchor
must occur exactly once); nothing is re-serialized and CRLF line endings are kept. Standard library plus lxml.

    build_components.py          rebuild tasks/T017/components/*.xml and definitions.json
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
from tools.bpad_workflow import Journal  # noqa: E402
from scripts.build_backwall_mathcad import notebook_revision  # noqa: E402

JOURNAL_EDITION = ROOT / "end_bent_walls" / "bpad" / "journal"
ADDED = "EndBentBackwallDesign"
LINK_TEXT = "End-bent backwall, cheek walls and tie-back straps (distilled, 19 October 2026 case, live references)"
TNR = "Times New Roman"
TODAY = "19 October 2026"
KEYS = ["BridgeGeometry_2Beam", "DecisionLog", ADDED, "FoundationModeling", "PedBridge"]
REPORT = ("Backwall Design 10-19.html", "6ed9ebb7bd2d2b536cddd289b04bbfcb1e8b566858239e40d88a2a7fb9d74768")   # D-057
CASE_SHA = "01e76c5a263af986e0d7e154039cec4c351bea29403dd9bfd2cbee7b16bab597"                               # selected_case.json


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(text, old, label, n=1):
    found = text.count(old)
    assert found == n, f"{label}: expected {n} occurrence(s), found {found}: {old[:100]!r}"


def rep(text, old, new, label):
    once(text, old, label)
    return text.replace(old, new)


def nl_of(text, label):
    nl = "\r\n" if "\r\n" in text else "\n"
    if nl == "\r\n":
        assert text.count("\n") == text.count("\r\n"), f"{label}: mixed line endings"
    return nl


def shape(el):
    return (el.tag, sorted(el.attrib.items()), (el.text or "").strip(), [shape(c) for c in el], (el.tail or "").strip())


base = Journal.load(TASK / "base.bpad")
mapping = json.loads((TASK / "components.json").read_text(encoding="utf-8"))
assert {k.split(":", 1)[1] for k in mapping} == set(KEYS) and len(mapping) == 5, f"unexpected component keys: {sorted(mapping)}"
edits = []


def part(name):
    return base.part(f"report:{name}").decode("utf-8")


# --------------------------------------------------------------------------
# 1. The added report: the journal-edition fragment, checked against its verification record
# --------------------------------------------------------------------------
verification = json.loads((JOURNAL_EDITION / "verification.json").read_text(encoding="utf-8"))[0]
revision = notebook_revision()
assert verification["report_name"] == ADDED
assert verification["package_revision"] == revision, (f"verification.json is for package {verification['package_revision']}, the notebook "
                                                       f"holds {revision} (rebuild: scripts/build_backwall_bpad.py --journal)")
assert verification["status"] == "✓ All Checks Pass", f"unexpected status {verification['status']!r}"
assert verification["literals_kept"] == ["s_brg"] and verification["context_references"] == ["drop_bw"]
assert verification["journal_references"] >= 20
raw = (JOURNAL_EDITION / f"{ADDED}.xml").read_bytes()
data = raw[:-2] if raw.endswith(b"\r\n") else raw[:-1] if raw.endswith(b"\n") else raw
assert sha(data) == verification["fragment_sha256"], "the fragment differs from verification.json (rebuild the journal edition)"
root = E.fromstring(data)
assert root.tag == "report" and root.get("name") == ADDED, "not a bare report element"
assert f"report:{ADDED}" not in base.spans, f"{ADDED} already exists in the base journal"
coherence = json.loads((JOURNAL_EDITION / "coherence.json").read_text(encoding="utf-8"))[ADDED]
owners = {row["owner"].partition(".")[0] for row in coherence}
assert owners == {"BridgeGeometry_2Beam", "Materials"}, owners
for row in coherence:                               # every referenced definition exists exactly once in the base journal
    owner, _, name = row["owner"].partition(".")
    report = base.elements[f"report:{owner}"]
    found = [d for d in report.iter("dynexp") if re.match(rf"\s*{re.escape(name)}\s*=(?!=)", d.get("formula") or "")]
    assert len(found) == 1, f"{row['owner']} is defined {len(found)} times in the base journal"
    if row["status"] in ("reference", "reference_context"):
        assert abs(row["journal_value"] - row["case_value"]) <= 1e-9 * max(abs(row["case_value"]), 1e-12), row
stamp = next(t for t in root.iter("table") if t.get("name") == "ProjectStamp")
for cell in stamp.iter("c"):
    if cell.get("formula"):
        key = cell.get("formula").partition(".")[2]
        assert cell.get("formula").startswith("ProjectInfo."), cell.get("formula")
        found = [d for d in base.elements["report:ProjectInfo"].iter("dynexp") if re.match(rf"\s*{re.escape(key)}\s*=(?!=)", d.get("formula") or "")]
        assert len(found) == 1, f"ProjectInfo.{key} is defined {len(found)} times"
fragment_defs = []
for e in root.iter():
    m = re.match(r"^\s*([^\W\d]\w*(?:\([^)]*\))?)\s*=(?!=)", e.get("formula", ""))
    if m:
        fragment_defs.append(m[1])

# --------------------------------------------------------------------------
# 2. PedBridge: index link after the PileDesignPier link; current-record paragraph; revision paragraph
# --------------------------------------------------------------------------
def edit_pedbridge():
    name = "PedBridge"
    text = part(name)
    nl = nl_of(text, name)
    anchor = ('<link address="#PileDesignPier">Pile design - Pier (distilled, 19 October 2026 case)</link>' + nl + " " * 8 + "</paragraph>")
    assert f'address="#{ADDED}"' not in text, f"PedBridge already links {ADDED}"
    insertion = (nl + " " * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + nl +
                 " " * 12 + f'<link address="#{ADDED}">{escape(LINK_TEXT)}</link>' + nl + " " * 8 + "</paragraph>")
    text = rep(text, anchor, anchor + insertion, "PedBridge index anchor")
    text = rep(text, "Design records: the 10-19 cap design reports (D-051) and pile design reports (D-054), distilled in the journal. The 16 October "
                     "2026 backwall report (D-037) is separate and predates D-049 and D-053. Journal tasks T014 to T016.",
               "Design records: the 10-19 cap design reports (D-051), pile design reports (D-054) and the 19 October end-bent backwall, cheek-wall and "
               "tie-back strap report (D-057; rerun on the D-049 export and the D-053/D-055 geometry, superseding the 16 October report D-037), all "
               "distilled in the journal; the backwall report reads the end-bent geometry, bearing pad data, Span 1 length and material strengths as "
               "live references to Bridge Geometry and Materials. Journal tasks T014 to T017.", "current-record paragraph")
    rev_old = (' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">Revision: 19 October 2026, coherence with the 19 October '
               'calculations and CAD model (T016):')
    rev_new = (' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">Revision: 19 October 2026, end-bent backwall report '
               f'added (T017): {ADDED}, the distilled 19 October 2026 backwall, cheek-wall and tie-back strap case (D-057) with live references to '
               'BridgeGeometry_2Beam, Materials and ProjectInfo.</paragraph>')
    text = rep(text, rev_old, rev_new + nl + rev_old, "Revision paragraph")
    edits.append({"report": name, "link": f"#{ADDED}", "text": LINK_TEXT, "change": "index link added after PileDesignPier; current-record paragraph and revision paragraph name the backwall report"})
    return text


# --------------------------------------------------------------------------
# 3. BridgeGeometry_2Beam: the backwall-drop caption names the report that reads it
# --------------------------------------------------------------------------
def edit_geometry():
    name = "BridgeGeometry_2Beam"
    text = part(name)
    text = rep(text, "Backwall design and quantities remain separate (16 October 2026 backwall report, D-037).</paragraph>",
               f"The backwall design report {ADDED} (19 October 2026 case, D-057; task T017) references this drop beside the backwall heights it "
               "measured from the D-055 model and reads the end-bent cap, backwall thickness, cheek thickness, pedestal, bearing pad and Span 1 "
               "values of this report as live references; backwall quantities remain separate.</paragraph>", "backwall drop caption")
    edits.append({"report": name, "text": "EndBent_backwallDrop caption", "change": "names EndBentBackwallDesign (D-057, T017) as the reader of the end-bent inputs"})
    return text


# --------------------------------------------------------------------------
# 4. FoundationModeling: the backwall report is current and in the journal
# --------------------------------------------------------------------------
def edit_foundation_modeling():
    name = "FoundationModeling"
    text = part(name)
    text = rep(text, "The 16 October 2026 backwall report (D-037) predates these exports and the D-053 geometry and is not in the journal.",
               "The end-bent backwall, cheek-wall and tie-back strap calculation was rerun on End Bent 1_Fixed.XML (its bearing actions equal the "
               f"earlier values) and the D-053/D-055 geometry on {TODAY} (D-057, superseding the 16 October report D-037) and is in the journal as "
               f"{ADDED} (task T017).", "backwall sentence")
    edits.append({"report": name, "text": "ModelSources20261019 currency paragraph", "change": "backwall report rerun (D-057) and in the journal (T017)"})
    return text


# --------------------------------------------------------------------------
# 5. DecisionLog: entry appended
# --------------------------------------------------------------------------
DECISION = (f"End-bent backwall, cheek-wall and tie-back strap calculation added to the journal (task T017) as {ADDED}, the Blockpad edition of the "
            f"19 October 2026 notebook case (D-057: report {REPORT[0]}, SHA-256 {REPORT[1][:12]}…; case SHA-256 {CASE_SHA[:12]}…). The notebook "
            "package was reconciled with the register (End Bent 1_Fixed.XML of D-049 with the D-051 case that records it; the D-053/D-055 CAD model "
            "measured natively: two planar 2% backwall tops 4.25 in below the deck-top line, crown 4.0691 ft and edges 3.8733 ft above the cap top, "
            "backwall volume 77.770 ft3, landing tributary length 17.155 ft; the T016 journal) and rerun: bearing actions unchanged, strap loads "
            "3.089 kip/ft service and 3.737 kip/ft factored (16 October: 3.094 / 3.746), all numerical checks pass, nine check entries pending across "
            "the six unconfirmed prerequisites (settlement, strap elevation, exposure, shrinkage, analysis confirmation, cheek anchorage); decisions "
            "D-014 to D-019 unchanged. In the journal edition the end-bent cap, backwall thickness, cheek thickness, pedestal, bearing pad and Span 1 "
            "values are live references to Bridge Geometry, the material strengths to Materials and the project stamp to ProjectInfo (23 references, "
            "each equal to the case; the bearing spacing stays the 102.99-in analysis value against the 103-in journal beam spacing); drop_bw "
            "references EndBent_backwallDrop beside the measured heights. Indexed in PedBridge; Bridge Geometry and Foundation Modeling name the report. "
            "Distilled numerical checks only, not design acceptance; native recalculation not performed; FBMP not rerun.")


def edit_decisionlog():
    name = "DecisionLog"
    text = part(name)
    nl = "\r\n" if text.endswith("</section>\r\n    </report>") else "\n"
    tail = " " * 8 + "</section>" + nl + " " * 4 + "</report>"
    assert text.endswith(tail), "DecisionLog does not end with a section inside the report"
    once(text, '<section name="CoherenceDecision20261019b" capture="False" hide="false">', "latest entry")
    assert 'name="CoherenceDecision20261019c"' not in text
    entry = nl.join([" " * 8 + '<section name="CoherenceDecision20261019c" capture="False" hide="false">',
                     " " * 12 + '<heading level="1" keepwithnext="True">2026-10-19 - End-bent backwall report rerun and added to the journal (T017)</heading>',
                     " " * 12 + f'<paragraph fontfamily="{TNR}" fontsize="11" leftindent="0" spacingafter="7">{escape(DECISION)}</paragraph>',
                     " " * 8 + "</section>"])
    text = text[:-len(" " * 4 + "</report>") - len(nl)] + nl + entry + nl + " " * 4 + "</report>"
    edits.append({"report": name, "text": DECISION, "change": "entry appended (19 October 2026, T017)"})
    return text


# --------------------------------------------------------------------------
# Write the component files named by components.json
# --------------------------------------------------------------------------
out = {f"report:{ADDED}": data, "report:PedBridge": edit_pedbridge().encode("utf-8"), "report:BridgeGeometry_2Beam": edit_geometry().encode("utf-8"),
       "report:FoundationModeling": edit_foundation_modeling().encode("utf-8"), "report:DecisionLog": edit_decisionlog().encode("utf-8")}
components = TASK / "components"
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
for key in ("report:PedBridge", "report:BridgeGeometry_2Beam", "report:FoundationModeling", "report:DecisionLog"):
    E.fromstring(out[key])                           # still well-formed
(TASK / "definitions.json").write_text(json.dumps({
    "edited_formulas": edits, "derived_cache_refreshes": {},
    "added_reports": [{"report": ADDED, "added_module": True, "formula_bearing_elements": sum(1 for e in root.iter() if "formula" in e.attrib),
                       "definitions": len(fragment_defs), "defined_names": fragment_defs,
                       "journal_references": verification["journal_references"], "literals_kept": verification["literals_kept"],
                       "context_references": verification["context_references"], "references": verification["references"]}]},
    indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"task": "T017", "package_revision": revision,
                  "components": {key: {"file": mapping[key], "bytes": len(blob), "sha256": sha(blob)} for key, blob in sorted(out.items())},
                  "fragment_sha256": sha(data), "added_definitions": len(fragment_defs), "edited": len(edits)}, indent=2, ensure_ascii=False))
