"""Build the project information-lineage graph (lineage/).

Reads the machine-readable project record and emits one graph that shows how
information flows from the project inputs to the deliverables, at three levels:

* nodes   - every source in project_current/source_register.csv, plus a few
            clearly tagged unregistered nodes (the RFQ placeholder, the native
            FB-MultiPier tool, the generated Mathcad cap sheets and their template)
* edges   - the register's depends_on relations, drawn in the direction of
            information flow (dependency -> dependent), plus derived edges from
            saved-case provenance and the coherence machine checks
* leaves  - parameters on nodes and edges: saved-case inputs with units and
            governing FBMP cases, backwall-case input sources, Mathcad input
            mappings (before/after values), geometry consistency checks,
            FBMP envelope tables on the XML nodes (role 'envelope' and
            'summary', with the XML's SHA-256 beside every row) and the cap
            notebook formula trace on the case nodes (role 'formula'), whose
            journal-module references become JOURNAL -> case edges

Decisions (D-###) and coherence items (COH-###) are attached to the nodes and
edges they reference. Machine-check statuses colour the nodes.

Verification sign-offs from the hand-edited sidecar lineage/signoff.json are
merged in as node.signoff / edge.signoff. Each is pinned to the register
SHA-256 hashes recorded when the person signed, and is marked stale when the
current hashes differ. The generator never writes a sign-off: a sign-off is a
statement by a named person, and only the sidecar holds it.

Two parameter sources reuse project code instead of parsing anew:

* FBMP envelopes come from the stdlib extractor embedded in
  FBMP_Envelope_Extractor.ipynb (its first code cell, up to the Colab
  interface), executed here and applied to every registered XML that is present.
* The formula trace comes from the pier_cap package (the cap notebook's engine):
  pier_cap.model.evaluate on each registered selected_case.json, then
  pier_cap.model.formula_trace. That needs the project .venv. The trace is what
  the working-tree package computes from the saved case today; it is not the
  registered report's own calculation. The trace content is part of the
  fingerprint, so the graph is stale whenever the package's answer changes.

Outputs:
    lineage/lineage.json   the graph
    lineage/index.html     lineage/viewer.html with the graph embedded

Rebuild after any register, decision, tracker, case, FBMP XML, Mathcad-export,
envelope-notebook or pier_cap change:
    .venv\\Scripts\\python.exe scripts\\build_lineage_graph.py
Check without writing:
    .venv\\Scripts\\python.exe scripts\\build_lineage_graph.py --check

Nothing here changes a source. Evaluating the cap package and the envelope
extractor only reads the saved cases and XML exports. The graph records what
the project files say about each other; it is not engineering acceptance.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

GENERATOR_VERSION = "1.2.0"

ROOT = Path(__file__).resolve().parents[1]
PC = ROOT / "project_current"
OUT_DIR = ROOT / "lineage"
TEMPLATE = OUT_DIR / "viewer.html"
OUT_JSON = OUT_DIR / "lineage.json"
OUT_HTML = OUT_DIR / "index.html"
SIGNOFF = OUT_DIR / "signoff.json"  # hand-edited verification sign-offs; merged, never written, by this script

REGISTER = PC / "source_register.csv"
DECISIONS = PC / "decisions.md"
ITEMS = PC / "coherence" / "items_snapshot.csv"
CHECKS = PC / "coherence" / "machine_checks.json"
MATHCAD_EXPORT = ROOT / "exports" / "cap-mathcad-20261017"
ENVELOPE_NOTEBOOK = ROOT / "FBMP_Envelope_Extractor.ipynb"
CAP_PACKAGE = ROOT / "pier_cap"

# Stage columns, left to right. Each register source is placed by STAGE_OF.
STAGES = [
    ("inputs", "Project inputs"),
    ("superstructure", "Superstructure"),
    ("geometry", "Geometry"),
    ("analysis", "Analysis (FBMP)"),
    ("design", "Cap and wall design"),
    ("reports", "Reports"),
    ("cad", "CAD model"),
    ("deliverables", "Deliverables"),
]
STAGE_OF = {
    "JOURNAL": "inputs", "ROADWAY": "inputs", "MSE-DETAIL-DXF": "inputs",
    "MCAD-DAT1": "superstructure", "MCAD-DAT2": "superstructure",
    "PSB-S1": "superstructure", "PSB-S2": "superstructure",
    "MCAD-S1": "superstructure", "MCAD-S2": "superstructure",
    "GEOMETRY": "geometry",
    "PIER-XML": "analysis", "PIER-MINTIP-XML": "analysis", "EB-XML": "analysis",
    "EB-MINTIP-XML": "analysis", "EB2-XML": "analysis",
    "CAP-TOOL": "design", "PIER-CASE": "design", "EB-CASE": "design", "EB2-CASE": "design",
    "BACKWALL-TOOL": "design", "BACKWALL-CASE": "design",
    "PIER-REPORT": "reports", "EB-REPORT": "reports", "EB2-REPORT": "reports",
    "BACKWALL-REPORT": "reports",
    "CAD-MODEL": "cad", "CAD-RUNTIME": "cad", "CAD-REPORT": "cad",
    "GEOMETRY-TABLES": "deliverables",
}
KIND_OF = {
    "GEOMETRY": "tool", "CAP-TOOL": "tool", "BACKWALL-TOOL": "tool",
    "PIER-CASE": "case", "EB-CASE": "case", "EB2-CASE": "case", "BACKWALL-CASE": "case",
    "PIER-REPORT": "report", "EB-REPORT": "report", "EB2-REPORT": "report", "BACKWALL-REPORT": "report",
    "PIER-XML": "analysis", "PIER-MINTIP-XML": "analysis", "EB-XML": "analysis",
    "EB-MINTIP-XML": "analysis", "EB2-XML": "analysis",
    "CAD-MODEL": "model", "CAD-RUNTIME": "model", "CAD-REPORT": "report",
    "GEOMETRY-TABLES": "deliverable",
}
CASE_FILES = {
    "PIER-CASE": PC / "cap_design" / "pier" / "selected_case.json",
    "EB-CASE": PC / "cap_design" / "end_bents" / "selected_case.json",
    "EB2-CASE": PC / "cap_design" / "end_bent_2" / "selected_case.json",
}
BACKWALL_CASE = PC / "cap_design" / "backwall" / "selected_case.json"
XML_OF_CASE = {"PIER-CASE": "PIER-XML", "EB-CASE": "EB-XML", "EB2-CASE": "EB2-XML"}
CASE_OF_XML = {xml: case for case, xml in XML_OF_CASE.items()}
GEOMETRY_CHECK_CASE = {"PIER": "PIER-CASE", "EB": "EB-CASE"}
MATHCAD_LABEL_CASE = {"End Bent 1": "EB-CASE", "End Bent 2": "EB2-CASE", "Pier Cap": "PIER-CASE"}

# Unregistered nodes that complete the stream. Each is tagged registered=false.
SUPPLEMENT_NODES = [
    {
        "id": "RFQ", "label": "RFQ / project brief", "kind": "external", "stage": "inputs",
        "status": "Not in repository",
        "notes": ("Placeholder for the originating request. It is not in source_register.csv; "
                  "add the document and a register row to replace this placeholder."),
        "feeds": [("JOURNAL", "originates")],
    },
    {
        "id": "FBMP-TOOL", "label": "FB-MultiPier analysis (native)", "kind": "tool", "stage": "analysis",
        "status": "Native software; model inputs not in repository",
        "notes": ("Only XML exports are registered. The native model files and run records behind the "
                  "selected reports have not been supplied (COH-013), and the final runs need the current "
                  "pile-head elevations (COH-028)."),
        "feeds": [("PIER-XML", "exports"), ("PIER-MINTIP-XML", "exports"), ("EB-XML", "exports"),
                  ("EB-MINTIP-XML", "exports"), ("EB2-XML", "exports")],
        "fed_by": [("GEOMETRY", "pile heads, cap geometry (COH-028)")],
    },
]

ISSUE_ROW_OFFSET = 8  # tracker row 9 holds COH-001

# A cap formula such as "b = BridgeGeometry_2Beam.PierCap_width to in" names a
# journal module and one of its variables.
JOURNAL_REF = re.compile(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b")
ENVELOPE_BASIS = ("Original XML element-local I/J end forces, enveloped per exact limit state and member by the "
                  "extractor embedded in FBMP_Envelope_Extractor.ipynb. FBMP OUTPUT_SUMMARY rows are copied "
                  "separately (role 'summary'). No signs are changed, no load factors or unit conversions applied, "
                  "no interior peaks inferred.")
TRACE_BASIS = ("pier_cap.model.formula_trace(evaluate(selected_case.json)) with the pier_cap package in the working "
               "tree at build time. Formulas are the cap tool's definitions (pier_cap/data/c005_formulas.json); "
               "values are the saved case evaluated by that package. This is not the registered report's own "
               "calculation and not engineering acceptance.")

# Decisions whose text names no register ID. Hand-mapped from their subject so
# they attach to the nodes they govern; recorded as refs.inferred in the graph.
DECISION_SOURCES = {
    "D-002": ["MCAD-S1", "MCAD-S2"],
    "D-003": ["PIER-REPORT", "PIER-CASE", "JOURNAL"],
    "D-004": ["EB-CASE", "EB2-CASE", "EB-REPORT", "EB2-REPORT"],
    "D-005": ["BACKWALL-TOOL", "BACKWALL-CASE", "CAD-MODEL"],
    "D-006": ["EB-REPORT", "EB-CASE"],
    "D-007": ["PIER-CASE", "EB-CASE", "EB2-CASE"],
    "D-008": ["PIER-REPORT", "EB-REPORT"],
    "D-009": ["PIER-XML", "EB-XML"],
    "D-010": ["JOURNAL"],
    "D-012": ["PIER-XML", "PIER-MINTIP-XML", "EB-XML", "EB-MINTIP-XML"],
    "D-013": ["CAD-MODEL", "CAD-RUNTIME"],
    "D-014": ["BACKWALL-TOOL", "BACKWALL-CASE"],
    "D-015": ["BACKWALL-TOOL", "BACKWALL-CASE"],
    "D-016": ["BACKWALL-TOOL", "BACKWALL-CASE"],
    "D-017": ["BACKWALL-TOOL", "BACKWALL-CASE", "CAD-MODEL"],
    "D-018": ["BACKWALL-TOOL", "BACKWALL-CASE"],
    "D-019": ["BACKWALL-TOOL", "BACKWALL-CASE", "CAD-MODEL"],
    "D-021": ["CAD-MODEL"],
    "D-024": ["CAD-MODEL"],
    "D-029": ["CAD-MODEL"],
    "D-030": ["CAD-MODEL"],
    "D-032": ["CAD-MODEL"],
}


# --------------------------------------------------------------------------- io
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def split_ids(text: str) -> list[str]:
    return [t.strip() for t in (text or "").split(";") if t.strip()]


def fmt_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


# ------------------------------------------------------------------ decisions
def parse_decisions(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| D-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        rows.append({"id": cells[0], "date": cells[1], "decision": cells[2], "basis": cells[3]})
    return rows


def find_refs(text: str, source_ids: list[str]) -> dict:
    """Return the source IDs, decision IDs and issue IDs named in text."""
    found_sources = []
    for sid in sorted(source_ids, key=len, reverse=True):
        if re.search(r"(?<![A-Z0-9-])" + re.escape(sid) + r"(?![A-Z0-9-])", text):
            found_sources.append(sid)
    decisions = sorted(set(re.findall(r"\bD-\d{3}\b", text)))
    issues = sorted(set(re.findall(r"\bCOH-\d{3}\b", text)))
    return {"sources": sorted(found_sources), "decisions": decisions, "issues": issues}


# ------------------------------------------------------- reused project code
def load_envelope_extractor(path: Path) -> dict:
    """Execute the stdlib extractor embedded in FBMP_Envelope_Extractor.ipynb.

    The notebook's first code cell defines read_fbmp, limit_state_table,
    native_envelopes, comparison and diagnostics before a Colab-only interface
    that needs pandas and ipywidgets. Only the part before that interface runs.
    """
    notebook = read_json(path)
    cell = next((c for c in notebook["cells"] if c.get("cell_type") == "code"
                 and "def read_fbmp" in "".join(c["source"])), None)
    if cell is None:
        raise ValueError(f"{path.name} has no code cell defining read_fbmp")
    core = "".join(cell["source"]).split('"""Colab notebook interface.', 1)[0]
    api = {"__name__": "fbmp_envelope_extractor"}
    exec(compile(core, str(path), "exec"), api)
    for name in ("read_fbmp", "limit_state_table", "native_envelopes", "comparison", "diagnostics"):
        if name not in api:
            raise ValueError(f"{path.name} extractor lacks {name}")
    return api


def load_cap_package() -> tuple[dict | None, str]:
    """Import the cap notebook's engine from pier_cap/. Returns (api, reason-if-missing)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from pier_cap.model import evaluate, formula_trace, upgrade_case, validate_case
    except Exception as exc:  # noqa: BLE001 - any import failure means "not available here"
        return None, f"pier_cap could not be imported: {type(exc).__name__}: {exc}"
    return {"evaluate": evaluate, "formula_trace": formula_trace, "upgrade_case": upgrade_case,
            "validate_case": validate_case}, ""


def package_fingerprint(package: Path) -> dict:
    """Content hash of every file in the package, so the graph records which code produced a trace."""
    files = sorted(p for p in package.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(package).as_posix().encode("utf-8") + b"\0" + sha256_file(p).encode("ascii") + b"\n")
    return {"path": rel(package), "files": len(files), "sha256": h.hexdigest()}


def envelope_rows(api: dict, xml_path: Path, digest: str) -> tuple[list[dict], dict]:
    """Strength/service envelope rows and FBMP summary rows for one XML, plus a source summary."""
    result = api["read_fbmp"](xml_path.read_bytes(), xml_path.name)
    table = api["limit_state_table"](result)
    native = api["native_envelopes"](result)
    compare = {(c["Member_type"], c["Component"], c["Unit"]): c for c in api["comparison"](result)}
    rows = []
    for r in table:
        member = r["Member"] if r["Member"] != "all" else r["Member_type"]
        row = {"name": f"{member}: {r['Component']} {r['Limit_state']}", "role": "envelope", "member": member,
               "limit_state": r["Limit_state"], "family": r["Limit_state_family"], "component": r["Component"],
               "unit": r["Unit"]}
        for prefix, key in (("min", "Min"), ("max", "Max"), ("abs_max", "Abs_max")):
            row[prefix] = r[key]
            if key == "Abs_max":
                row["abs_max_signed"] = r["Abs_max_signed"]
            row[prefix + "_load_case"] = r[key + "_Load_case"]
            row[prefix + "_combination"] = r[key + "_Combination"]
            row[prefix + "_element"] = r[key + "_Element"]
            row[prefix + "_end"] = r[key + "_End"]
        row["records"] = r["Available_records"]
        row["xml_sha256"] = digest
        rows.append(row)
    for r in native:
        c = compare.get((r["Member_type"], r["Component"], r["Unit"]), {})
        rows.append({
            "name": f"{r['Member_type']}: {r['Component']} FBMP summary", "role": "summary",
            "member": r["Member_type"], "component": r["Component"], "unit": r["Unit"],
            "min": r["Min"], "min_load_case": r["min_Load_case"], "min_combination": r["min_Combination"],
            "min_limit_state": r["min_Limit_state"],
            "max": r["Max"], "max_load_case": r["max_Load_case"], "max_combination": r["max_Combination"],
            "max_limit_state": r["max_Limit_state"], "abs_max": r["Abs_max"],
            "status": c.get("Comparison", r["Status"]),
            "detail": (f"OUTPUT_SUMMARY |max| {fmt_value(c.get('Reported_abs_max'))} vs all exported element ends "
                       f"|max| {fmt_value(c.get('All_exported_ends_abs_max'))}" if c else r["Status"]),
            "xml_sha256": digest,
        })
    meta = result["metadata"]
    load_cases = sorted({(c["Limit_state"], c["Load_case"], c["Combination"]) for c in result["cases"]})
    summary = {
        "extractor": f"{ENVELOPE_NOTEBOOK.name} embedded extractor {api.get('VERSION', '')}",
        "basis": ENVELOPE_BASIS, "fbmp_version": meta["fbmp_version"], "project": meta["project"],
        "analysis": meta["analysis"], "unit_system": meta["unit_system"],
        "load_cases": [{"limit_state": s, "load_case": lc, "combination": cb} for s, lc, cb in load_cases],
        "members": sorted({r["member"] for r in rows if r["role"] == "envelope"}),
        "envelope_rows": len(table), "summary_rows": len(native), "end_force_records": meta["raw_end_rows"],
        "diagnostics": api["diagnostics"](result),
    }
    return rows, summary


# ------------------------------------------------------------------- building
class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple, dict] = {}
        self.inputs: list[Path] = []

    def use(self, path: Path):
        if path.exists() and path not in self.inputs:
            self.inputs.append(path)

    def node(self, nid: str) -> dict:
        return self.nodes[nid]

    def add_edge(self, src: str, dst: str, kind: str, label: str) -> dict:
        key = (src, dst)
        if key not in self.edges:
            self.edges[key] = {
                "id": f"{src}->{dst}", "source": src, "target": dst, "kind": kind, "label": label,
                "parameters": [], "checks": [], "flags": [],
            }
        return self.edges[key]

    def edge(self, src: str, dst: str) -> dict | None:
        return self.edges.get((src, dst))


# ------------------------------------------------------------ parameter links
# A saved-case force input and the FBMP envelope component it is taken from:
# (component, extremum of that component's envelope row, or None when the input
# is an interior extremum the envelope row does not list).
FORCE_COMPONENT = {
    "Mu_N": ("M3", "min"), "Mu_P": ("M3", None), "Mu_B": ("M3", "max"),
    "Vu_G": ("V2", "abs_max"), "Vu_L": ("V2", "abs_max"), "Tu": ("T", "abs_max"),
    "MI_N": ("M3", "min"), "MI_P": ("M3", None), "MI_B": ("M3", "max"),
}
CHECK_VALUES = re.compile(r"^Notebook (.+?); (?:saved case|source audit) (.+?)\.(?: |$)")
# The case audit's own OUTPUT_SUMMARY line for a force input, when it has one.
CASE_SUMMARY_KEY = {
    "Mu_N": "min moment about 3 axis", "Mu_B": "max moment about 3 axis", "Tu": "absolute torque",
    "Vu_G": ("max shear in 2 direction", "min shear in 2 direction"),
    "Vu_L": ("max shear in 2 direction", "min shear in 2 direction"),
}
INPUT_REF = re.compile(r"\binputs\.([A-Za-z_]\w*)")
VALUE_TOLERANCE = 0.011  # printed values are rounded to 0.01


def _number(text: str):
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(text or ""))
    return float(m.group(1)) if m else None


def _cap_member(node: dict) -> str:
    members = (node.get("envelope_source") or {}).get("members") or []
    caps = [m for m in members if not m.upper().startswith("PILE")]
    caps.sort(key=lambda m: (0 if "CAP" in m.upper() else 1, m))
    return caps[0] if caps else ""


def derive_links(g: Graph) -> list[dict]:
    """One record per parameter crossing an edge, named on both sides.

    Edge parameters come in five shapes (governing FBMP case, Mathcad input
    mapping, cap formula naming a journal variable, geometry consistency check,
    backwall input naming its source). Each becomes a link
    {edge, source, target, kind, source_name, source_value, target_name,
    target_value, unit, detail, status, index} so a viewer can follow one
    quantity from node to node by matching (node, name). The same four name and
    value keys are also written back onto the edge parameter. A link whose
    source side cannot be named (a derived Mathcad region, a backwall input
    described in prose) keeps source_name empty and says why in detail.
    """
    links = []
    for e in g.edges.values():
        src, dst = g.node(e["source"]), g.node(e["target"])
        src_inputs = {p["name"]: p for p in src["parameters"] if p.get("role") == "input"}
        envelope = {(p.get("component"), p.get("limit_state")): p
                    for p in src["parameters"] if p.get("role") == "envelope" and p.get("member") == _cap_member(src)}
        for i, p in enumerate(e["parameters"]):
            link = {"edge": e["id"], "source": e["source"], "target": e["target"], "index": i,
                    "source_name": "", "source_value": "", "target_name": p.get("name", ""),
                    "target_value": "", "unit": p.get("unit", ""), "detail": "", "status": ""}
            if "load_case" in p and "state" in p:
                link["kind"] = "governing"
                link["target_value"] = p.get("value", "")
                comp, extremum = FORCE_COMPONENT.get(p["name"], (None, None))
                row = envelope.get((comp, p.get("state"))) if comp else None
                where = (f"{p.get('state', '')} load case {p.get('load_case', '')}, combination "
                         f"{p.get('combination', '')}, element {p.get('element', '')}, x = {p.get('x_in', '')} in")
                if row is None:
                    link["detail"] = where + ("; no envelope row for this component in the registered XML"
                                              if comp else "; component not mapped")
                    if not src["parameters"]:
                        link["detail"] = where + "; registered XML not present, no envelope to compare"
                elif extremum is None:
                    link["source_name"] = row["name"]
                    link["detail"] = where + "; interior extremum inside the pile region, not the envelope row's min/max"
                else:
                    link["source_name"] = row["name"]
                    link["source_value"] = fmt_value(row.get(extremum))
                    a, b = _number(link["source_value"]), _number(link["target_value"])
                    same = a is not None and b is not None and abs(abs(a) - abs(b)) <= VALUE_TOLERANCE
                    link["status"] = "MATCH" if same else "DIFFERS"
                    link["detail"] = f"{extremum} of that envelope row ({row.get('unit', '')}) vs the case input; " + where
                    # What the case's own export summary said for this quantity, so a
                    # DIFFERS verdict can be read as "different file", not "wrong row".
                    summary = e.get("fbmp_summary") or {}
                    keys = CASE_SUMMARY_KEY.get(p["name"])
                    keys = keys if isinstance(keys, tuple) else ((keys,) if keys else ())
                    own = [abs(float(summary[k]["summary"])) for k in keys
                           if k in summary and isinstance(summary[k].get("summary"), (int, float))]
                    if own:
                        link["case_export_value"] = fmt_value(max(own))
                        own_same = b is not None and abs(max(own) - abs(b)) <= VALUE_TOLERANCE
                        link["detail"] += (f"; the case's own export summary gives {link['case_export_value']}"
                                           + (" = this input" if own_same else ""))
                    if not same:
                        link["detail"] += "; the registered XML is a different export than the one the case was built from"
            elif "region" in p and "after" in p:
                link["kind"] = "mapping"
                lhs, _, rhs = p["after"].partition(":=")
                link["target_name"], link["target_value"] = lhs.strip(), rhs.strip()
                if p.get("basis", "").startswith("Selected case inputs."):
                    link["source_name"] = p["name"]
                    link["source_value"] = src_inputs.get(p["name"], {}).get("value", "")
                    link["unit"] = src_inputs.get(p["name"], {}).get("unit", "")
                    link["detail"] = f"Mathcad region {p['region']}"
                else:
                    link["detail"] = f"Mathcad region {p['region']}; derived from the case: {p.get('basis', '')}"
                link["status"] = "CHANGED" if p.get("changed") else "UNCHANGED"
            elif "module" in p and "variable" in p:
                link["kind"] = "formula"
                link["source_name"] = f"{p['module']}.{p['variable']}"
                link["target_value"] = p.get("value", "")
                link["detail"] = p.get("formula", "")
                if p.get("module_in_journal") is False or p.get("variable_in_journal") is False:
                    link["status"] = "NAME NOT IN JOURNAL"
                if p.get("analysis_geometry"):
                    link["detail"] += f"; FBMP import set this input to {p['analysis_geometry']} from the XML cap section"
            elif "source_text" in p:
                link["kind"] = "source"
                link["target_value"] = p.get("value", "")
                m = INPUT_REF.search(p.get("source_text", ""))
                if m:
                    link["source_name"] = m.group(1)
                    link["source_value"] = src_inputs.get(m.group(1), {}).get("value", "")
                link["detail"] = p.get("source_text", "")
                link["status"] = p.get("status", "")
            elif "status" in p and "detail" in p and "value" not in p:
                link["kind"] = "check"
                link["source_name"] = p["name"]
                m = CHECK_VALUES.match(p.get("detail", ""))
                if m:
                    link["source_value"], link["target_value"] = m.group(1), m.group(2)
                link["detail"] = p.get("detail", "")
                link["status"] = p.get("status", "")
            else:
                continue
            for key in ("source_name", "source_value", "target_name", "target_value"):
                p[key] = link[key]
            links.append(link)
    return links


# ------------------------------------------------------ verification sign-offs
SIGNOFF_SCHEMA = "d2mpdb.lineage-signoff"
SIGNOFF_KEYS = {"id", "by", "on", "basis", "hashes"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def rel_or_abs(path: Path) -> str:
    try:
        return rel(path)
    except ValueError:
        return path.as_posix()


def load_signoffs(path: Path) -> dict:
    """Read and validate the sign-off sidecar.

    Returns {"present", "note", "entries"} with every entry normalised to
    {id, by, on, basis, hashes}. A missing file is an empty sidecar. A malformed
    file stops the build naming the offending entry: a sign-off that cannot be
    read must not vanish from the record silently.

    Entry shape: id is a node id or a "source->target" edge id; by and basis are
    non-empty text; on is an ISO date; hashes is {"node": sha256} for a node or
    {"source": sha256, "target": sha256} for an edge (empty strings are allowed
    where the register has no hash, e.g. unregistered nodes).
    """
    if not path.exists():
        return {"present": False, "note": "", "entries": []}

    def fail(msg: str):
        raise SystemExit(f"{rel_or_abs(path)}: {msg}")

    data = read_json(path)
    if not isinstance(data, dict) or data.get("schema") != SIGNOFF_SCHEMA:
        fail(f'the top level must be an object with "schema": "{SIGNOFF_SCHEMA}"')
    entries = data.get("signoffs")
    if not isinstance(entries, list):
        fail('"signoffs" must be a list')
    out = []
    for i, entry in enumerate(entries, start=1):
        where = f"signoffs[{i}]"
        if not isinstance(entry, dict):
            fail(f"{where} is not an object")
        unknown = sorted(set(entry) - SIGNOFF_KEYS)
        if unknown:
            fail(f"{where} has unknown keys {unknown}; allowed keys are {sorted(SIGNOFF_KEYS)}")
        for key in ("id", "by", "on", "basis"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                fail(f"{where}.{key} must be non-empty text")
        if not DATE_RE.match(entry["on"]):
            fail(f"{where}.on must be an ISO date YYYY-MM-DD, got {entry['on']!r}")
        try:
            datetime.date.fromisoformat(entry["on"])
        except ValueError:
            fail(f"{where}.on is not a calendar date: {entry['on']!r}")
        hashes = entry.get("hashes")
        if not isinstance(hashes, dict):
            fail(f"{where}.hashes must be an object")
        expected = {"source", "target"} if "->" in entry["id"] else {"node"}
        if set(hashes) != expected:
            fail(f"{where}.hashes must have exactly the keys {sorted(expected)} for id {entry['id']!r}")
        for key, value in hashes.items():
            if not isinstance(value, str) or (value and not SHA256_RE.match(value)):
                fail(f"{where}.hashes.{key} must be a lowercase hex SHA-256, or empty where the register has none")
        out.append({"id": entry["id"].strip(), "by": entry["by"].strip(), "on": entry["on"],
                    "basis": entry["basis"].strip(), "hashes": {k: hashes[k] for k in sorted(hashes)}})
    return {"present": True, "note": str(data.get("note", "")), "entries": out}


def merge_signoffs(g: Graph, sidecar: dict, path: Path) -> dict:
    """Attach each sign-off to its node or edge; mark it stale when the register hashes moved on.

    One sign-off per id is effective: the latest `on` date, file order breaking
    ties. Earlier ones stay under signoff.previous. Entries naming an id that is
    not in the graph are listed as orphans rather than dropped. Returns the
    summary block stored at the graph root; nodes and edges without a sign-off
    gain no key at all.
    """
    grouped: dict[str, list] = {}
    for order, entry in enumerate(sidecar["entries"]):
        grouped.setdefault(entry["id"], []).append((entry["on"], order, entry))
    orphans, signed_nodes, signed_edges, stale = [], 0, 0, 0
    for sid, items in grouped.items():
        items.sort(key=lambda t: (t[0], t[1]))
        effective, previous = items[-1][2], [t[2] for t in items[:-1]]
        if "->" in sid:
            src, _, dst = sid.partition("->")
            target = g.edge(src, dst)
            if target is None:
                orphans.append(sid)
                continue
            current = {"source": g.node(src)["sha256"], "target": g.node(dst)["sha256"]}
            signed_edges += 1
        else:
            target = g.nodes.get(sid)
            if target is None:
                orphans.append(sid)
                continue
            current = {"node": target["sha256"]}
            signed_nodes += 1
        changed = [k for k in current if effective["hashes"].get(k, "") != current[k]]
        record = dict(effective)
        record.update({
            "current": current, "stale": bool(changed),
            "stale_detail": "; ".join(f"{k} hash changed since the sign-off" for k in changed),
            "pinned": all(current.values()),
            "previous": [{"by": p["by"], "on": p["on"], "basis": p["basis"]} for p in previous],
        })
        target["signoff"] = record
        stale += int(record["stale"])
    return {
        "schema": SIGNOFF_SCHEMA, "schema_version": 1, "path": rel_or_abs(path), "present": sidecar["present"],
        "note": sidecar["note"], "entries": sidecar["entries"], "signed_nodes": signed_nodes,
        "signed_edges": signed_edges, "stale": stale, "orphans": sorted(orphans),
    }


def build(signoff_path: Path | None = None) -> dict:
    """Build the graph. signoff_path overrides the sidecar (tests point it at a temp copy)."""
    g = Graph()
    # The generator is an input to its own outputs: editing it must show as stale.
    for p in (Path(__file__).resolve(), REGISTER, DECISIONS, ITEMS, CHECKS):
        g.use(p)

    # -- register nodes -----------------------------------------------------
    register = read_csv(REGISTER)
    for row in register:
        sid = row["source_id"]
        g.nodes[sid] = {
            "id": sid, "label": row["topic"], "kind": KIND_OF.get(sid, "source"),
            "stage": STAGE_OF.get(sid, "inputs"), "registered": True,
            "path": row["path"], "status": row["status"], "scope": row["scope"],
            "sha256": row["sha256"], "registered_on": row["registered_on"],
            "depends_on": split_ids(row["depends_on"]), "origin": row["origin"],
            "notes": row["notes"], "hash_basis": row["hash_basis"],
            "health": "NONE", "checks": [], "decisions": [], "issues": [], "parameters": [],
        }
    source_ids = list(g.nodes)
    for sid in source_ids:
        for dep in g.node(sid)["depends_on"]:
            if dep in g.nodes:
                g.add_edge(dep, sid, "depends_on", "feeds")

    # -- supplement nodes ---------------------------------------------------
    for spec in SUPPLEMENT_NODES:
        g.nodes[spec["id"]] = {
            "id": spec["id"], "label": spec["label"], "kind": spec["kind"], "stage": spec["stage"],
            "registered": False, "path": "", "status": spec["status"], "scope": "", "sha256": "",
            "registered_on": "", "depends_on": [], "origin": "", "notes": spec["notes"], "hash_basis": "",
            "health": "NONE", "checks": [], "decisions": [], "issues": [], "parameters": [],
        }
    for spec in SUPPLEMENT_NODES:
        for target, label in spec.get("feeds", []):
            if target in g.nodes:
                e = g.add_edge(spec["id"], target, "supplement", label)
                e["flags"].append("unregistered")
        for src, label in spec.get("fed_by", []):
            if src in g.nodes:
                e = g.add_edge(src, spec["id"], "supplement", label)
                e["flags"].append("unregistered")

    # -- machine checks -----------------------------------------------------
    checks = read_json(CHECKS)
    for chk in checks["checks"]:
        entry = {"check_id": chk["check_id"], "status": chk["status"], "detail": chk.get("detail", "")}
        ids = [s for s in chk.get("source_ids", []) if s in g.nodes]
        for sid in ids:
            g.node(sid)["checks"].append(entry)
        if chk["check_id"].startswith("SOURCE:") and len(ids) == 1:
            g.node(ids[0])["health"] = chk["status"]
        gm = re.match(r"^GEOMETRY:(PIER|EB):(\w+)$", chk["check_id"])
        m = re.match(r"^DEP:([A-Z0-9-]+):([A-Z0-9-]+)$", chk["check_id"])
        if gm:
            # Notebook-vs-case consistency checks become one derived edge whose
            # parameters are the checked quantities.
            case_id = GEOMETRY_CHECK_CASE[gm.group(1)]
            e = g.add_edge("GEOMETRY", case_id, "check", "geometry consistency checks")
            e["parameters"].append({"name": gm.group(2), "status": chk["status"], "detail": chk.get("detail", "")})
            e["checks"].append(entry)
        elif m and g.edge(m.group(2), m.group(1)):
            e = g.edge(m.group(2), m.group(1))
            e["checks"].append(entry)
            e["flags"].append("review")
        elif len(ids) == 2:
            e = g.edge(ids[0], ids[1]) or g.edge(ids[1], ids[0])
            if e is not None:
                e["checks"].append(entry)
                if chk["status"] == "CHANGED":
                    e["flags"].append("identity-mismatch")

    # -- saved cap cases: inputs, governing FBMP cases, analysis identity ---
    for case_id, path in CASE_FILES.items():
        if not path.exists():
            continue
        g.use(path)
        case = read_json(path)
        node = g.node(case_id)
        inputs = case.get("inputs", {})
        units = case.get("units", {})
        audit = (case.get("analysis") or {}).get("xml_audit") or {}
        governing = audit.get("governing") or {}
        for name, value in inputs.items():
            param = {"name": name, "value": fmt_value(value), "unit": units.get(name) or "", "role": "input"}
            gov = governing.get(name)
            if isinstance(gov, dict):
                param["governing"] = (f"{gov.get('state', '')} load case {gov.get('load_case', '')}, "
                                      f"combination {gov.get('combination', '')}, element {gov.get('element', '')} "
                                      f"side {gov.get('side', '')}, x = {gov.get('x_in', '')} in")
                param["source"] = XML_OF_CASE[case_id]
            node["parameters"].append(param)
        node["case_name"] = case.get("name", "")
        node["analysis_id"] = (case.get("analysis") or {}).get("id", "")
        xml_id = XML_OF_CASE[case_id]
        e = g.edge(xml_id, case_id)
        if e is not None:
            for name, gov in governing.items():
                if name in inputs and isinstance(gov, dict):
                    e["parameters"].append({
                        "name": name, "value": fmt_value(inputs[name]), "unit": units.get(name) or "",
                        "state": gov.get("state", ""), "load_case": gov.get("load_case", ""),
                        "combination": gov.get("combination", ""), "element": gov.get("element", ""),
                        "x_in": gov.get("x_in", ""),
                    })
            audit_sha = audit.get("sha256", "")
            reg_sha = g.node(xml_id)["sha256"]
            e["analysis_identity"] = {
                "case_requires_sha256": audit_sha, "registered_sha256": reg_sha,
                "match": bool(audit_sha) and audit_sha == reg_sha,
                "file_present": g.node(xml_id)["health"] not in ("MISSING",),
            }
            if audit_sha and audit_sha != reg_sha and "identity-mismatch" not in e["flags"]:
                e["flags"].append("identity-mismatch")
            if "summary_checks" in audit:
                e["fbmp_summary"] = {k: v for k, v in audit["summary_checks"].items()}
            for key in ("version", "cap_length_ft", "pile_centers_in", "bearing_stations_in", "combinations"):
                if key in audit:
                    e.setdefault("fbmp", {})[key] = audit[key]

    # -- backwall case: every input names its source ------------------------
    if BACKWALL_CASE.exists():
        g.use(BACKWALL_CASE)
        case = read_json(BACKWALL_CASE)
        node = g.node("BACKWALL-CASE")
        node["case_name"] = case.get("name", "")
        inputs = case.get("inputs", {})
        units = case.get("units", {})
        sources = case.get("sources", {})
        for name, value in inputs.items():
            src = sources.get(name) or {}
            param = {"name": name, "value": fmt_value(value), "unit": units.get(name) or "", "role": "input",
                     "source_text": src.get("source", ""), "source_status": src.get("status", "")}
            refs = find_refs(src.get("source", ""), source_ids)
            if refs["sources"]:
                param["source"] = refs["sources"][0]
                for sid in refs["sources"]:
                    e = g.edge(sid, "BACKWALL-CASE") or g.add_edge(sid, "BACKWALL-CASE", "parameter", "supplies inputs")
                    e["parameters"].append({"name": name, "value": param["value"], "unit": param["unit"],
                                            "source_text": src.get("source", ""), "status": src.get("status", "")})
            node["parameters"].append(param)
        node["confirmations"] = case.get("confirmations", {})

    # -- FBMP XML envelopes: the notebook extractor on every registered XML present
    envelope_api = None
    if ENVELOPE_NOTEBOOK.exists():
        g.use(ENVELOPE_NOTEBOOK)
        envelope_api = load_envelope_extractor(ENVELOPE_NOTEBOOK)
    for node in g.nodes.values():
        if node["kind"] != "analysis" or not node["path"] or not (ROOT / node["path"]).exists():
            continue
        if envelope_api is None:
            node["envelope_source"] = {"available": False, "reason": f"{rel(ENVELOPE_NOTEBOOK)} is not present"}
            continue
        xml_path = ROOT / node["path"]
        g.use(xml_path)
        digest = sha256_file(xml_path)
        rows, summary = envelope_rows(envelope_api, xml_path, digest)
        case_id = CASE_OF_XML.get(node["id"], "")
        e = g.edge(node["id"], case_id) if case_id else None
        required = ((e or {}).get("analysis_identity") or {}).get("case_requires_sha256", "")
        register_match = digest == node["sha256"]
        case_match = (digest == required) if required else None
        if required:
            verdict = (f"{'MATCH' if case_match else 'MISMATCH'}: {case_id} requires {required[:12]}…, "
                       f"this file is {digest[:12]}…")
        else:
            verdict = "VARIANT: no saved case names this export"
        if not register_match:
            verdict += "; file differs from the registered hash"
        identity = {"name": "XML identity (SHA-256)", "role": "identity", "value": digest, "status": verdict,
                    "detail": f"registered {node['sha256']}" + (f"; {case_id} requires {required}" if required else ""),
                    "xml_sha256": digest}
        node["parameters"] = [identity] + rows + node["parameters"]
        node["envelope_source"] = {
            "available": True, "filename": xml_path.name, "sha256": digest, "registered_sha256": node["sha256"],
            "register_match": register_match, "case_id": case_id, "case_requires_sha256": required,
            "case_match": case_match, **summary,
        }

    # -- cap formula trace: the pier_cap engine on each registered saved case
    cap_api, cap_reason = load_cap_package()
    cap_package = (package_fingerprint(CAP_PACKAGE) if CAP_PACKAGE.exists()
                   else {"path": rel(CAP_PACKAGE), "files": 0, "sha256": ""})
    journal_bytes = b""
    journal_path = ROOT / g.node("JOURNAL")["path"] if g.nodes.get("JOURNAL", {}).get("path") else None
    if journal_path is not None and journal_path.exists():
        g.use(journal_path)
        journal_bytes = journal_path.read_bytes()
    derived = []
    for case_id, path in CASE_FILES.items():
        if not path.exists():
            continue
        node = g.node(case_id)
        if cap_api is None:
            node["formula_trace"] = {"available": False, "reason": cap_reason, "basis": TRACE_BASIS}
            continue
        try:
            case = cap_api["upgrade_case"](read_json(path))
            cap_api["validate_case"](case)
            evaluation = cap_api["evaluate"](case)
            trace = cap_api["formula_trace"](evaluation)
        except Exception as exc:  # noqa: BLE001 - record the failure; never guess a trace
            node["formula_trace"] = {"available": False, "reason": f"{type(exc).__name__}: {exc}", "basis": TRACE_BASIS}
            continue
        digest = hashlib.sha256(json.dumps(trace, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        derived.append({"id": f"formula-trace:{case_id}", "sha256": digest, "package_sha256": cap_package["sha256"]})
        analysis_geometry = (case.get("analysis") or {}).get("geometry") or {}
        journal_rows = []
        for entry in trace:
            node["parameters"].append({"name": entry["name"], "role": "formula", "value": entry["value"],
                                       "formula": entry["formula"], "note": entry["note"]})
            m = JOURNAL_REF.search(entry["formula"])
            if not m:
                continue
            module, variable = m.group(1), m.group(2)
            row = {"name": entry["name"], "role": "formula", "value": entry["value"], "formula": entry["formula"],
                   "note": entry["note"], "module": module, "variable": variable}
            if journal_bytes:
                row["module_in_journal"] = module.encode("utf-8") in journal_bytes
                row["variable_in_journal"] = variable.encode("utf-8") in journal_bytes
            if entry["name"] in analysis_geometry:
                row["analysis_geometry"] = fmt_value(analysis_geometry[entry["name"]])
            journal_rows.append(row)
        if journal_rows and "JOURNAL" in g.nodes:
            e = g.add_edge("JOURNAL", case_id, "parameter", "journal variables named by cap formulas")
            e["parameters"].extend(journal_rows)
            e["basis"] = (TRACE_BASIS + " Each row's formula is the tool definition that names a journal module and "
                          "variable; its value is the saved case input. module_in_journal and variable_in_journal "
                          "record whether those names occur in the registered journal file. Where analysis_geometry "
                          "is shown, FBMP import set that input from the XML cap section.")
        node["formula_trace"] = {
            "available": True, "basis": TRACE_BASIS, "entries": len(trace), "journal_references": len(journal_rows),
            "package_status": getattr(evaluation, "status", ""), "sha256": digest, "package_sha256": cap_package["sha256"],
        }

    # -- Mathcad cap sheets (generated deliverables) ------------------------
    record_path = MATHCAD_EXPORT / "Source and verification record.json"
    verification_path = MATHCAD_EXPORT / "Verification.json"
    if record_path.exists():
        g.use(record_path)
        records = read_json(record_path)
        verification = {}
        if verification_path.exists():
            g.use(verification_path)
            verification = {v["label"]: v for v in read_json(verification_path)}
        template_sha = next((r.get("template_sha256", "") for r in records), "")
        g.nodes["MCAD-CAP-TEMPLATE"] = {
            "id": "MCAD-CAP-TEMPLATE", "label": "Cap Mathcad template (End Bent 1_10-8.xmcd)", "kind": "external",
            "stage": "inputs", "registered": False, "path": "", "status": "Supplied template; not registered",
            "scope": "Classic Mathcad worksheet the cap sheets are generated from", "sha256": template_sha,
            "registered_on": "", "depends_on": [], "origin": "User-supplied", "notes":
            "Generated cap sheets keep this worksheet's equations and replace its input regions from the selected cases.",
            "hash_basis": "exact_bytes", "health": "NONE", "checks": [], "decisions": [], "issues": [], "parameters": [],
        }
        for rec in records:
            label = rec["label"]
            case_id = next((n for n in g.nodes.values() if n.get("sha256") == rec.get("case_sha256")), None)
            case_id = case_id["id"] if case_id else MATHCAD_LABEL_CASE.get(label)
            nid = "MCAD-CAP-" + re.sub(r"[^A-Z0-9]+", "", label.upper().replace("END BENT", "EB").replace("PIER CAP", "PIER"))
            out_path = MATHCAD_EXPORT / rec["output"]
            ver = verification.get(label, {})
            node = {
                "id": nid, "label": f"{label} Mathcad cap sheet", "kind": "deliverable", "stage": "deliverables",
                "registered": False, "path": rel(out_path) if out_path.exists() else rec["output"],
                "status": "Generated 17 October 2026; native Mathcad recalculation not performed",
                "scope": "Printable classic Mathcad worksheet with the selected case's inputs",
                "sha256": rec.get("output_sha256", ""), "registered_on": rec.get("date", ""), "depends_on": [case_id] if case_id else [],
                "origin": rel(MATHCAD_EXPORT), "notes": (
                    f"Independent checks: {ver.get('checks_passed', '?')} passed over {ver.get('definition_count', '?')} "
                    f"definitions and {ver.get('unit_checks', '?')} unit checks. Native recalculation: "
                    f"{'yes' if rec.get('native_mathcad_recalculation') else 'no'}."),
                "hash_basis": "exact_bytes", "health": "EMULATED" if not rec.get("native_mathcad_recalculation") else "MATCH",
                "checks": [], "decisions": [], "issues": [], "parameters": [],
            }
            for name, value in (ver.get("snapshot") or {}).items():
                node["parameters"].append({"name": name, "value": fmt_value(value) if not isinstance(value, list)
                                           else ", ".join(fmt_value(v) for v in value), "unit": "", "role": "output"})
            g.nodes[nid] = node
            te = g.add_edge("MCAD-CAP-TEMPLATE", nid, "supplement", "equations and layout")
            te["flags"].append("unregistered")
            if case_id:
                e = g.add_edge(case_id, nid, "mapping", "input mapping")
                e["case_identity"] = {"mapping_case_sha256": rec.get("case_sha256", ""),
                                      "registered_sha256": g.node(case_id)["sha256"],
                                      "match": rec.get("case_sha256") == g.node(case_id)["sha256"]}
                if not e["case_identity"]["match"]:
                    e["flags"].append("identity-mismatch")
                mapping_path = MATHCAD_EXPORT / f"{label} - Input Mapping.csv"
                if mapping_path.exists():
                    g.use(mapping_path)
                    for row in read_csv(mapping_path):
                        basis = row["basis"]
                        if basis.startswith("Selected case inputs."):
                            name = basis.split(".", 1)[1]
                        else:
                            name = row["after"].split(":=", 1)[0].strip()
                        e["parameters"].append({"name": name, "region": row["region"], "before": row["before"],
                                                "after": row["after"], "basis": basis,
                                                "changed": row["before"] != row["after"]})

    # -- parameter links: every edge parameter named on both sides ------------
    links = derive_links(g)

    # -- decisions and issues ------------------------------------------------
    all_ids = list(g.nodes)
    decisions = parse_decisions(DECISIONS)
    for d in decisions:
        refs = find_refs(d["decision"] + " " + d["basis"], all_ids)
        refs["inferred"] = [sid for sid in DECISION_SOURCES.get(d["id"], [])
                            if sid in g.nodes and sid not in refs["sources"]]
        refs["sources"] = sorted(set(refs["sources"]) | set(refs["inferred"]))
        d["refs"] = refs
        for sid in refs["sources"]:
            g.node(sid)["decisions"].append(d["id"])
    # register notes also cite decisions
    for row in register:
        for did in re.findall(r"\bD-\d{3}\b", row["notes"] + " " + row["scope"]):
            node = g.node(row["source_id"])
            if did not in node["decisions"]:
                node["decisions"].append(did)
            d = next((x for x in decisions if x["id"] == did), None)
            if d is not None and row["source_id"] not in d["refs"]["sources"]:
                d["refs"]["sources"].append(row["source_id"])
    for d in decisions:
        d["refs"]["sources"].sort()

    issues = []
    for i, row in enumerate(read_csv(ITEMS), start=1):
        refs = find_refs(row.get("Source references", "") + " " + row.get("Finding", ""), all_ids)
        item = {
            "id": row["Item ID"], "status": row["Status"], "area": row["Area"], "item": row["Item"],
            "finding": row["Finding"], "next_action": row["Next action"], "response": row.get("Your response", ""),
            "resolution": row.get("Resolution / evidence", ""), "references": row.get("Source references", ""),
            "last_reviewed": row.get("Last reviewed", ""), "refs": refs, "checks": [], "tracker_row": i + ISSUE_ROW_OFFSET,
        }
        issues.append(item)
        for sid in refs["sources"]:
            g.node(sid)["issues"].append(item["id"])
    for chk in checks["checks"]:
        tm = re.match(r"^TRACKER:(\d+)$", chk["check_id"])
        if tm:
            item = next((x for x in issues if x["tracker_row"] == int(tm.group(1))), None)
            if item is not None:
                item["checks"].append({"check_id": chk["check_id"], "status": chk["status"], "detail": chk.get("detail", "")})

    for node in g.nodes.values():
        node["decisions"] = sorted(set(node["decisions"]))
        node["issues"] = sorted(set(node["issues"]))
        node["open_issues"] = [i for i in node["issues"]
                               if next(x for x in issues if x["id"] == i)["status"] not in ("Closed",)]
    for e in g.edges.values():
        e["flags"] = sorted(set(e["flags"]))

    # -- verification sign-offs: merge the hand-edited sidecar -------------
    signoff_file = SIGNOFF if signoff_path is None else Path(signoff_path)
    signoff = merge_signoffs(g, load_signoffs(signoff_file), signoff_file)
    if signoff_file.exists() and rel_or_abs(signoff_file) != signoff_file.as_posix():
        g.use(signoff_file)  # under the repo: the sidecar joins the fingerprint, so editing it makes the outputs stale

    inputs = sorted(g.inputs, key=rel)
    input_records = [{"path": rel(p), "sha256": sha256_file(p)} for p in inputs]
    derived.sort(key=lambda d: d["id"])
    # The formula traces are computed, not read, so their content joins the
    # fingerprint: the graph is stale whenever the cap package's answer changes.
    fingerprint = hashlib.sha256(
        (GENERATOR_VERSION + "\n" + "\n".join(f"{r['path']} {r['sha256']}" for r in input_records)
         + "".join(f"\nderived:{d['id']} {d['sha256']}" for d in derived)).encode("utf-8")
    ).hexdigest()

    return {
        "schema": "d2mpdb.lineage-graph", "schema_version": 1, "generator_version": GENERATOR_VERSION,
        "fingerprint": fingerprint, "inputs": input_records, "derived": derived,
        "cap_package": cap_package, "cap_trace": {"available": cap_api is not None, "reason": cap_reason},
        "checked_at_utc": checks.get("checked_at_utc", ""),
        "stages": [{"id": sid, "label": label} for sid, label in STAGES],
        "nodes": sorted(g.nodes.values(), key=lambda n: n["id"]),
        "edges": sorted(g.edges.values(), key=lambda e: e["id"]),
        "links": sorted(links, key=lambda l: (l["edge"], l["index"])),
        "decisions": decisions, "issues": issues, "signoff": signoff,
        "health_legend": {
            "MATCH": "Registered bytes or text match", "CHANGED": "File differs from the registered revision",
            "MISSING": "Registered file absent or no source selected", "EMULATED": "Generated; native recalculation not performed",
            "NONE": "No machine check (unregistered or placeholder)",
        },
    }


def render_html(graph: dict) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    marker = "/*__LINEAGE_DATA__*/"
    if marker not in template:
        raise SystemExit(f"{TEMPLATE} lacks the {marker} marker")
    return template.replace(marker, payload, 1)


def current_outputs_match(graph: dict) -> tuple[bool, str]:
    if not OUT_JSON.exists() or not OUT_HTML.exists():
        return False, "outputs missing"
    try:
        existing = read_json(OUT_JSON)
    except json.JSONDecodeError:
        return False, "lineage.json unreadable"
    if existing.get("fingerprint") != graph["fingerprint"]:
        return False, "fingerprint differs"
    if render_html(existing) != OUT_HTML.read_text(encoding="utf-8"):
        return False, "index.html does not embed lineage.json with the current viewer"
    return True, "current"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report whether lineage/ is current; write nothing")
    args = ap.parse_args(argv)
    graph = build()
    ok, why = current_outputs_match(graph)
    if args.check:
        print(f"lineage/: {why}")
        return 0 if ok else 1
    OUT_DIR.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(graph, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT_HTML.write_text(render_html(graph), encoding="utf-8")
    n_params = sum(len(n["parameters"]) for n in graph["nodes"]) + sum(len(e["parameters"]) for e in graph["edges"])
    kinds = {}
    for link in graph["links"]:
        kinds[link["kind"]] = kinds.get(link["kind"], 0) + 1
    print(f"wrote {rel(OUT_JSON)} and {rel(OUT_HTML)}: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
          f"{n_params} parameters, {len(graph['links'])} links ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))}), "
          f"{len(graph['decisions'])} decisions, {len(graph['issues'])} issues; fingerprint {graph['fingerprint'][:12]}")
    envelopes = [n["id"] for n in graph["nodes"] if (n.get("envelope_source") or {}).get("available")]
    traced = [n["id"] for n in graph["nodes"] if (n.get("formula_trace") or {}).get("available")]
    untraced = [f"{n['id']} ({n['formula_trace']['reason']})" for n in graph["nodes"]
                if n.get("formula_trace") and not n["formula_trace"]["available"]]
    print(f"FBMP envelopes: {', '.join(envelopes) or 'none'}; formula traces: {', '.join(traced) or 'none'}"
          + (f"; no trace for {', '.join(untraced)}" if untraced else ""))
    so = graph["signoff"]
    print(f"sign-offs ({so['path']}{'' if so['present'] else ', absent'}): {so['signed_nodes']} nodes, "
          f"{so['signed_edges']} edges, {so['stale']} stale"
          + (f"; unknown ids: {', '.join(so['orphans'])}" if so["orphans"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
