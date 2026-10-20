"""Lossless, bounded BPAD task packages. Standard library only; no math evaluator.

Run from any directory: python tools/bpad_workflow.py --help
The registry, dependencies and evidence are reviewable project files, not a
security boundary against someone deliberately modifying the repository.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from xml.parsers import expat

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = "journal/D2_I95_Project_Journal.bpad"
MODULE_TAGS = {"report", "spreadsheet", "drawing"}


class WorkflowError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise WorkflowError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def promotion_policy(root):
    path = root / "workflow/promotion_policy.json"
    policy = read_json(path) if path.exists() else {"reviews_required": True}
    require(isinstance(policy, dict) and type(policy.get("reviews_required")) is bool,
            "Promotion policy must specify a boolean reviews_required.")
    return policy


def write_json(path, value):
    atomic_write(Path(path), (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".bpad-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def within(root, relative):
    root = Path(root).resolve()
    p = (root / relative).resolve()
    require(p.is_relative_to(root) and p != root, f"Path escapes its folder: {relative}")
    return p


@contextmanager
def writer_lock(root):
    p = Path(root) / "workflow/integration.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise WorkflowError("Integration is locked. Check the recorded process before removing a stale lock.")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({"pid": os.getpid(), "created": stamp()}, f)
        yield
    finally:
        p.unlink()


class Journal:
    """Use Expat byte offsets for surgery; never serialize the source tree."""

    def __init__(self, data):
        self.data = data
        self.sha256 = digest(data)
        self.spans = {}
        self.order = []
        parser = expat.ParserCreate()
        stack = []
        counts = Counter()
        current = None

        def start(tag, attrs):
            nonlocal current
            offset = parser.CurrentByteIndex
            if len(stack) == 1:
                counts[tag] += 1
                key = f"{tag}:{attrs.get('name') or '@' + str(counts[tag])}"
                require(key not in self.spans, f"Duplicate top-level identity: {key}")
                # Scan the start tag while respecting quoted greater-than signs.
                quote = None
                end = offset
                while end < len(data):
                    char = data[end]
                    if quote:
                        if char == quote:
                            quote = None
                    elif char in (34, 39):
                        quote = char
                    elif char == 62:
                        break
                    end += 1
                current = (key, offset, end + 1, data[offset:end].rstrip().endswith(b"/"))
            stack.append(tag)

        def end(tag):
            nonlocal current
            if len(stack) == 2:
                key, begin, start_end, empty = current
                finish = start_end if empty else data.index(b">", parser.CurrentByteIndex) + 1
                self.spans[key] = (begin, finish)
                self.order.append(key)
                current = None
            stack.pop()

        def forbid(*args):
            raise WorkflowError("DTD and entity declarations are not supported in task journals.")

        parser.StartElementHandler = start
        parser.EndElementHandler = end
        parser.StartDoctypeDeclHandler = forbid
        parser.EntityDeclHandler = forbid
        parser.ExternalEntityRefHandler = forbid
        try:
            parser.Parse(data, True)
            self.root = ET.fromstring(data)
        except (expat.ExpatError, ET.ParseError) as e:
            raise WorkflowError(f"Invalid XML: {e}") from e
        require(self.root.tag == "document", "Expected a native BPAD document root.")
        self.elements = dict(zip(self.order, self.root))
        require(len(self.elements) == len(self.root), "Unsupported top-level XML topology.")
        self.hashes = {key: digest(self.part(key)) for key in self.order}
        self.shell = self.replace({key: b"" for key in self.order})

    @classmethod
    def load(cls, path):
        return cls(Path(path).read_bytes())

    def part(self, key):
        require(key in self.spans, f"Unknown component: {key}")
        begin, end = self.spans[key]
        return self.data[begin:end]

    def replace(self, replacements, allowed_additions=()):
        require(set(replacements) <= self.spans.keys() | set(allowed_additions), "Adding components requires a separate topology change.")
        parts = []
        cursor = 0
        for key in self.order:
            begin, end = self.spans[key]
            parts.extend((self.data[cursor:begin], replacements.get(key, self.data[begin:end])))
            cursor = end
        # Append registered modules without changing the original document shell.
        parts.extend(replacements[k] for k in allowed_additions if k in replacements and k not in self.spans)
        parts.append(self.data[cursor:])
        return b"".join(parts)

    def resolve(self, name):
        if name in self.spans:
            return name
        matches = [k for k, e in self.elements.items() if e.get("name") == name]
        require(len(matches) == 1, f"Use an exact component key for {name!r}; found {matches}")
        return matches[0]

    def reorder(self, order):
        """The same bytes with the components placed in `order` (a registered permutation): every inter-component gap, the
        document wrapper and every component's bytes are kept; only which component sits in which slot changes."""
        require(sorted(order) == sorted(self.order), "A registered order must be a permutation of the current components.")
        is_module = lambda key: key.split(":", 1)[0] in MODULE_TAGS
        require(all(is_module(a) == is_module(b) for a, b in zip(self.order, order)),
                "A registered order may only permute modules among module slots; resources, styles, includes and references keep their slots.")
        gaps, cursor = [], 0
        for key in self.order:
            begin, end = self.spans[key]
            gaps.append(self.data[cursor:begin])
            cursor = end
        parts = []
        for gap, key in zip(gaps, order):
            parts.extend((gap, self.part(key)))
        parts.append(self.data[cursor:])
        return b"".join(parts)

    def changes(self, other, allowed_deletions=(), allowed_additions=(), order=None):
        removed = set(self.order) - set(other.order)
        added = set(other.order) - set(self.order)
        sequence = list(order) if order else self.order
        require(removed <= set(allowed_deletions) and added <= set(allowed_additions) and
                other.order == [key for key in sequence if key not in removed] + [key for key in allowed_additions if key in added],
                "Component addition/removal/reordering requires a registered deletion, appended module addition or registered order; "
                "unregistered reordering is unsupported.")
        require(all(other.elements[k].tag in MODULE_TAGS for k in added), "Only registered modules may be added.")
        require(self.shell == other.shell, "Document wrapper or inter-component whitespace changed outside scope.")
        return [k for k in self.order if k in removed or self.hashes[k] != other.hashes[k]] + [k for k in allowed_additions if k in added]


def scan(journal):
    """Heuristic candidates only. An unresolved grammar never implies independence."""
    names = {e.get("name"): k for k, e in journal.elements.items() if e.get("name")}
    pattern = re.compile(r"(?<![\w])(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?=\.|$)") if names else None
    rows = []
    for key, elem in journal.elements.items():
        deps = set()
        definitions = []
        expressions = []
        for e in elem.iter():
            for attr in ("formula", "condition", "target", "source", "valuedef"):
                value = e.get(attr)
                if value:
                    expressions.append({"tag": e.tag, "attribute": attr, "value": value})
                    if pattern:
                        deps.update(names[match.group(1)] for match in pattern.finditer(value))
            formula = e.get("formula", "")
            match = re.match(r"^\s*([^=<>!]+?)\s*=(?!=)", formula)
            if match:
                definitions.append({"candidate_name": match[1].strip(), "formula": formula})
        rows.append({"key": key, "kind": elem.tag, "title": elem.get("title"),
                     "sha256": journal.hashes[key], "bytes": len(journal.part(key)),
                     "formula_count": sum(1 for e in elem.iter() if "formula" in e.attrib),
                     "candidate_dependencies": sorted(deps - {key}),
                     "candidate_definitions": definitions, "expressions": expressions,
                     "cached_errors": ["".join(e.itertext()) for e in elem.iter("error")]})
    return {"journal_sha256": journal.sha256, "dependency_discovery": "partial; reviewed declarations or all-component fallback required",
            "components": rows}


def structural_issues(journal):
    issues = Counter()
    names = {e.get("name"): e for e in journal.root if e.get("name")}
    all_names = [e.get("name") for e in journal.root if e.get("name")]
    for name, count in Counter(all_names).items():
        if count > 1:
            issues[f"duplicate top-level name: {name}"] += count - 1
    for key, mod in journal.elements.items():
        if mod.tag not in MODULE_TAGS:
            continue
        ids = Counter(e.get("id") for e in mod.iter() if e.get("id"))
        for ident, count in ids.items():
            if count > 1:
                issues[f"{key}: duplicate id {ident}"] += count - 1
        for e in mod.iter():
            if e.tag == "image" and e.get("source"):
                target = e.get("source").split(".")[0]
                if target not in names:
                    issues[f"{key}: unresolved image {e.get('source')}"] += 1
            address = e.get("address", "")
            if address.startswith("#"):
                path, _, fragment = address[1:].partition(";")
                chain = path.split(".")
                target = names.get(chain[0])
                for section in chain[1:]:
                    candidates = [] if target is None else [x for x in target.iter() if x is not target and x.get("name") == section]
                    target = candidates[0] if len(candidates) == 1 else None
                if target is None:
                    issues[f"{key}: unresolved link {address}"] += 1
                elif fragment and fragment not in {x.get("id") for x in target.iter()}:
                    issues[f"{key}: unresolved link fragment {address}"] += 1
    return issues


def external_refs(journal, folder):
    refs = []
    for elem in journal.root.findall("xref"):
        value = elem.get("path", "")
        win = PureWindowsPath(value)
        absolute = win.is_absolute() or Path(value).is_absolute()
        path = Path(value) if absolute else Path(folder) / Path(value.replace("\\", "/"))
        exists = path.is_file()
        refs.append({"name": elem.get("name"), "path": value, "absolute": absolute,
                     "exists": exists, "sha256": digest(path.read_bytes()) if exists else None})
    return refs


def snapshot_files(root):
    files = {}
    for folder in ("standards", "journal/References", "workflow/assumptions", "workflow/external"):
        for path in sorted((root / folder).rglob("*")):
            if path.is_file():
                files[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    for name in ("dependencies.json", "reference_sources.json"):
        p = root / "workflow" / name
        if p.exists():
            files[p.relative_to(root).as_posix()] = digest(p.read_bytes())
    return files


def import_references(root, source):
    """Copy only the exact referenced filenames. No PDF rewriting or inference."""
    source = Path(source).resolve()
    with writer_lock(root):
        journal = Journal.load(root / JOURNAL)
        entries = []
        for elem in journal.root.findall("xref"):
            filename = PureWindowsPath(elem.get("path", "")).name
            src = within(source, filename)
            require(src.is_file(), f"Missing reference: {src}")
            data = src.read_bytes()
            require(data.startswith(b"%PDF-"), f"Not a PDF file: {src}")
            dest = within(root / "journal/References", filename)
            require(not dest.exists() or dest.read_bytes() == data, f"Existing reference differs: {filename}; review and register a resource revision explicitly.")
            entries.append({"name": elem.get("name"), "filename": filename, "sha256": digest(data), "source": str(src)})
        # Validate the entire set before copying anything.
        for entry in entries:
            atomic_write(root / "journal/References" / entry["filename"], (source / entry["filename"]).read_bytes())
        write_json(root / "workflow/reference_sources.json", {"imported": stamp(), "files": entries})
        return {"references_copied": len(entries), "source": str(source)}


def inspect(root, path, output):
    j = Journal.load(path)
    index = scan(j)
    index.update({"structural_issues": dict(structural_issues(j)), "external_references": external_refs(j, Path(path).parent),
                  "native_recalculation": "not performed", "native_visual_review": "not performed"})
    write_json(output, index)
    return {"journal_sha256": j.sha256, "modules": sum(e.tag in MODULE_TAGS for e in j.root),
            "formulas": sum("formula" in e.attrib for e in j.root.iter()),
            "cached_errors": sum(e.tag == "error" for e in j.root.iter()), "report": str(output)}


def roundtrip(path, out):
    j = Journal.load(path)
    out = Path(out)
    require(not out.exists(), "Round-trip output already exists; choose a fresh folder.")
    out.mkdir(parents=True)
    entries = []
    for i, key in enumerate(j.order):
        filename = f"{i:04d}.xml"
        (out / filename).write_bytes(j.part(key))
        entries.append({"key": key, "file": filename, "sha256": j.hashes[key]})
    rebuilt = j.replace({entry["key"]: (out / entry["file"]).read_bytes() for entry in entries})
    require(rebuilt == j.data, "No-change rebuild did not preserve every byte.")
    (out / "roundtrip.bpad").write_bytes(rebuilt)
    result = {"source_sha256": j.sha256, "rebuilt_sha256": digest(rebuilt), "byte_identical": True,
              "components": entries, "native_evaluation": "not performed"}
    write_json(out / "manifest.json", result)
    return {"byte_identical": True, "sha256": j.sha256, "components": len(entries)}


def task_dependencies(root, j, writes):
    config_path = root / "workflow/dependencies.json"
    contracts = read_json(config_path).get("modules", {}) if config_path.exists() else {}
    detected = {r["key"]: r["candidate_dependencies"] for r in scan(j)["components"]}
    reads = set()
    modes = {}
    seen = set()

    def visit(key):
        if key in seen:
            return
        seen.add(key)
        decl = contracts.get(key, {})
        if not (decl.get("reviewed_by") and decl.get("rationale") and decl.get("complete") is True):
            reads.update(j.order)
            modes[key] = "all components: dependency coverage has not been reviewed"
            return
        modes[key] = "reviewed declaration plus detected references"
        dependencies = {j.resolve(x) for x in decl.get("reads", [])} | set(detected[key])
        reads.update(dependencies)
        for dep in dependencies:
            if j.elements[dep].tag in MODULE_TAGS:
                visit(dep)

    for key in writes:
        visit(key)
    # Document-wide styles, includes and xrefs may affect every calculation.
    reads.update(k for k, e in j.elements.items() if e.tag not in MODULE_TAGS and k not in writes)
    return sorted(reads - set(writes)), modes


def prepare(root, task_id, objective, write_names, prerequisites=(), delete_names=(), add_names=(), order_names=None):
    require(re.fullmatch(r"T[0-9]{3,}[A-Za-z0-9_-]*", task_id), "Use a task ID such as T001.")
    with writer_lock(root):
        package = root / "tasks" / task_id
        registry = root / "workflow/registry" / f"{task_id}.json"
        plan_only = package.is_dir() and {p.name for p in package.iterdir()} <= {"plan.md"}
        require((not package.exists() or plan_only) and not registry.exists(), "Task already exists; use a new task ID.")
        j = Journal.load(root / JOURNAL)
        adds = sorted(set(add_names))
        order = None
        if order_names is not None:
            require(not adds and not delete_names, "A registered order cannot be combined with module additions or deletions.")
            order = [j.resolve(x) for x in order_names]
            require(order != j.order, "The registered order equals the current order.")
            j.reorder(order)                        # validates the permutation and the module slots
        existing_names = {el.get("name") for el in j.root if el.get("name")}
        for key in adds:
            match = re.fullmatch(r"(report|spreadsheet|drawing):([A-Za-z_][A-Za-z0-9_]*)", key)
            require(match is not None, "Use an exact new module key such as report:NewCalc; resources and styles cannot be added here.")
            require(key not in j.spans and match[2] not in existing_names, f"Added module identity already exists: {key}")
        require(len({key.split(":", 1)[1] for key in adds}) == len(adds), "Added module names must be unique across module types.")
        deletes = sorted({j.resolve(x) for x in delete_names})
        require(all(j.elements[k].tag in MODULE_TAGS for k in deletes),
                "Only explicitly named report, spreadsheet or drawing modules may be deleted; resources and styles remain protected.")
        writes = sorted({j.resolve(x) for x in write_names} | set(deletes) | set(adds))
        require(writes or order, "A task needs an explicit write scope.")
        if adds:
            reads, modes = sorted(set(j.order) - set(writes)), {key: "all components: registered topology addition" for key in writes}
        else:
            reads, modes = task_dependencies(root, j, writes)
        for prerequisite in prerequisites:
            require(re.fullmatch(r"T[0-9]{3,}[A-Za-z0-9_-]*", prerequisite), "Invalid prerequisite ID.")
            require((root / "workflow/registry" / f"{prerequisite}.json").is_file(), f"Unknown prerequisite: {prerequisite}")
        record = {"schema": 1, "id": task_id, "created": stamp(), "objective": objective,
                  "base_journal_sha256": j.sha256, "writes": writes, "deletes": deletes, "adds": adds, "reads": reads,
                  "order": order, "dependency_modes": modes, "prerequisites": list(prerequisites),
                  "component_hashes": j.hashes, "source_files": snapshot_files(root),
                  "exclusions": ["No unassigned components or document wrapper changes; topology changes limited to registered appended modules and deletions", "No automatic engineering approval"],
                  "output_contract": "Retain existing published names and scopes; describe units, signs, cases and any interface change in submission.json.",
                  "acceptance": ["bounded changes", "unchanged dependencies", "structural delta review", "Blockpad recalculation", "native visual review", "engineering and external-analysis review"],
                  "stop_conditions": ["Missing inputs or reference sources", "Required change outside assigned scope", "Changed upstream inputs", "Unresolved engineering assumptions"]}
        package.mkdir(parents=True, exist_ok=True)
        (package / "base.bpad").write_bytes(j.data)
        (package / "working.bpad").write_bytes(j.data)
        components = {}
        (package / "components").mkdir()
        for index, key in enumerate(writes):
            filename = f"{index:03d}.xml"
            tag, name = key.split(":", 1)
            fragment = f'<{tag} name="{name}" />'.encode() if key in adds else j.part(key)
            (package / "components" / filename).write_bytes(fragment)
            components[key] = filename
        write_json(package / "components.json", components)
        shutil.copytree(root / "journal/References", package / "References", dirs_exist_ok=True)
        write_json(package / "order.json", record)
        write_json(package / "submission.json", {"summary": "", "published_outputs": [], "assumptions_and_conventions": [],
                                                    "downstream_impact": [], "external_analysis": "not assessed", "checks_performed": [], "open_items": []})
        write_json(registry, record)
        return {"task": task_id, "writes": writes, "deletes": deletes, "adds": adds, "reordered": bool(order), "reads": len(reads),
                "package": str(package)}


def load_task(root, task_id):
    require(re.fullmatch(r"T[0-9]{3,}[A-Za-z0-9_-]*", task_id), "Invalid task ID.")
    record = read_json(root / "workflow/registry" / f"{task_id}.json")
    package = root / "tasks" / task_id
    require(read_json(package / "order.json") == record, "Task order changed after registration; create a new scoped task.")
    base = Journal.load(package / "base.bpad")
    require(base.sha256 == record["base_journal_sha256"], "Task base was modified.")
    require(base.hashes == record["component_hashes"], "Registered component fingerprints do not match the base.")
    return record, package, base


def check(root, task_id, proposed_data=None):
    record, package, base = load_task(root, task_id)
    current = Journal.load(root / JOURNAL)
    proposed = Journal(proposed_data) if proposed_data is not None else Journal.load(package / "working.bpad")
    adds = record.get("adds", [])
    changed = base.changes(proposed, record.get("deletes", []), adds)
    deleted = [key for key in changed if key not in proposed.elements]
    base.changes(current)  # Verify topology and document envelope compatibility.
    require(set(changed) <= set(record["writes"]), f"Out-of-scope edits: {sorted(set(changed) - set(record['writes']))}")
    conflicts = [k for k in record["writes"] if base.hashes.get(k) != current.hashes.get(k)]
    require(not conflicts, f"Conflicting owned components: {conflicts}")
    stale = [k for k in record["reads"] if base.hashes[k] != current.hashes[k]]
    require(not stale, f"Stale upstream dependencies: {stale}")
    require(snapshot_files(root) == record["source_files"], "Standards, references, assumptions, dependency declarations or analysis records changed since task preparation.")
    # Task copies of external resources are context, not an alternate write path.
    expected = {k.removeprefix("journal/References/"): v for k, v in record["source_files"].items() if k.startswith("journal/References/")}
    actual = {p.relative_to(package / "References").as_posix(): digest(p.read_bytes()) for p in (package / "References").rglob("*") if p.is_file()}
    require(expected == actual, "Task reference resources changed outside the registered scope.")
    for prerequisite in record["prerequisites"]:
        require((root / "workflow/completed" / f"{prerequisite}.json").exists(), f"Prerequisite has not been promoted: {prerequisite}")
    candidate = Journal(current.replace({key: proposed.part(key) if key not in deleted else b"" for key in changed}, adds))
    order = record.get("order")
    if order:                                        # a registered permutation of the modules, applied at assembly
        require(sorted(order) == sorted(current.order), "The registered order no longer matches the current components; create a new task.")
        candidate = Journal(candidate.reorder(order))
        require(current.shell == candidate.shell and all(current.part(k) == candidate.part(k) for k in current.order if k not in changed),
                "Reordering changed bytes outside the registered scope.")
    for key in deleted:
        owner = current.elements[key].get("name")
        if not owner:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(owner) + r"(?=\.|$)")
        consumers = [other for other, el in candidate.elements.items()
                     if any(pattern.search(e.get(attr, "")) for e in el.iter()
                            for attr in ("formula", "condition", "source", "target", "valuedef"))]
        require(not consumers, f"Deleted module {owner} still referenced by {consumers}")
    for key in changed:
        if key in deleted or key in adds:
            continue
        owner = current.elements[key].get("name")
        if current.elements[key].tag not in MODULE_TAGS or not owner:
            continue
        def defined(j):
            result = set()
            for e in j.elements[key].iter():
                m = re.match(r"^\s*([^\W\d]\w*)\s*=(?!=)", e.get("formula", ""))
                if m:
                    result.add(m.group(1))
                if e.get("name"):
                    result.add(e.get("name"))
            return result
        for removed in defined(current) - defined(candidate):
            pattern = re.compile(r"(?<!\w)" + re.escape(owner + "." + removed) + r"(?!\w)")
            consumers = [other for other, el in candidate.elements.items() if other != key
                         and any(pattern.search(e.get("formula", "")) for e in el.iter())]
            require(not consumers, f"Removed published name {owner}.{removed} still used by {consumers}")
    introduced = structural_issues(candidate) - structural_issues(current)
    require(not introduced, f"New structural issues: {dict(introduced)}")
    new_errors = []
    for key in changed:
        if key in deleted:
            continue
        errors = lambda j: Counter("".join(e.itertext()) for e in j.elements[key].iter("error")) if key in j.elements else Counter()
        new_errors.extend({"component": key, "message": e, "count": n} for e, n in (errors(candidate) - errors(current)).items())
    require(not new_errors, f"New stored native errors: {new_errors}")
    detected = {r["key"]: r["candidate_dependencies"] for r in scan(candidate)["components"]}
    watched = set(record["reads"]) | set(record["writes"])
    additional = sorted({d for key in changed if key in detected for d in detected[key] if d not in watched})
    require(not additional, f"New dependencies need a new task contract: {additional}")
    affected = set(changed)
    while True:
        next_set = affected | {key for key, deps in detected.items() if set(deps) & affected}
        if next_set == affected:
            break
        affected = next_set
    report = {"task": task_id, "base_sha256": base.sha256, "current_sha256": current.sha256,
              "candidate_sha256": candidate.sha256, "changed_components": changed, "deleted_components": deleted,
              "added_components": [k for k in adds if k in candidate.elements],
              "reordered": bool(order), "component_order": candidate.order if order else None,
              "detected_downstream_impact": sorted(affected - set(changed)),
              "impact_coverage": "partial; all external results require review if any component changed",
              "inherited_structural_issues": dict(structural_issues(current)),
              "candidate_structural_issues": dict(structural_issues(candidate)),
              "candidate_cached_errors": sum(e.tag == "error" for e in candidate.root.iter()),
              "structural_delta": "passed", "numerical_currency": "not verified",
              "native_visual_review": "not performed", "engineering_review": "not performed",
              "external_analysis_currency": "review required" if changed else "not established",
              "source_files": record["source_files"], "submission_sha256": digest((package / "submission.json").read_bytes())}
    return candidate, report


def import_components(root, task_id):
    record, package, base = load_task(root, task_id)
    mapping = read_json(package / "components.json")
    require(set(mapping) == set(record["writes"]), "Component mapping must match the registered write scope.")
    working = Journal.load(package / "working.bpad")
    # Avoid overwriting direct native edits with older extracted components.
    require(working.data == base.data, "Working journal already edited. Use import-native or create a fresh task before importing component fragments.")
    data = base.replace({k: within(package / "components", v).read_bytes() for k, v in mapping.items()}, record.get("adds", []))
    _, report = check(root, task_id, data)
    atomic_write(package / "working.bpad", data)
    return {"task": task_id, "changed_components": report["changed_components"]}


def import_native(root, task_id, path):
    data = Path(path).read_bytes()
    _, report = check(root, task_id, data)
    atomic_write(root / "tasks" / task_id / "working.bpad", data)
    return {"task": task_id, "changed_components": report["changed_components"]}


def relocate_references(root, task_id):
    record, package, base = load_task(root, task_id)
    working = Journal.load(package / "working.bpad")
    replacements = {}
    for key, elem in working.elements.items():
        if elem.tag != "xref":
            continue
        require(key in record["writes"], f"Reference relocation needs write permission for {key}")
        filename = PureWindowsPath(elem.get("path", "")).name
        require((package / "References" / filename).is_file(), f"Missing packaged reference: {filename}")
        from xml.sax.saxutils import quoteattr
        path_attr = ("path=" + quoteattr("References/" + filename)).encode()
        replacements[key] = re.sub(rb'''\bpath\s*=\s*(?:"[^"]*"|'[^']*')''', lambda _: path_attr, working.part(key), count=1)
    data = working.replace(replacements)
    _, report = check(root, task_id, data)
    atomic_write(package / "working.bpad", data)
    return {"task": task_id, "relocated": len(replacements), "changed_components": report["changed_components"]}


def assemble(root, task_id, output):
    with writer_lock(root):
        candidate, report = check(root, task_id)
        output = Path(output).resolve()
        require(output.is_relative_to((root / "generated").resolve()), "Candidates must be under generated/.")
        require(not output.exists(), "Candidate output already exists; use a new build folder.")
        output.mkdir(parents=True)
        atomic_write(output / "candidate.bpad", candidate.data)
        # Store a small, Git-trackable proposal; full working copies are ignored.
        proposal = root / "tasks" / task_id / "proposal"
        components = {}
        for index, key in enumerate(report["changed_components"]):
            if key in report["deleted_components"]:
                base = Journal.load(root / "tasks" / task_id / "base.bpad")
                components[key] = {"deleted": True, "before_sha256": base.hashes[key]}
                continue
            filename = f"{index:03d}.xml"
            data = candidate.part(key)
            atomic_write(proposal / filename, data)
            components[key] = {"file": filename, "sha256": digest(data)}
        write_json(proposal / "manifest.json", {"task": task_id, "base_sha256": report["base_sha256"], "components": components})
        shutil.copytree(root / "journal/References", output / "References", dirs_exist_ok=True)
        report["external_references"] = external_refs(candidate, output)
        write_json(output / "report.json", report)
        template = {"candidate_sha256": candidate.sha256, "reviewer": "", "native_recalculation": False,
                    "native_visual_review": False, "engineering_review": False,
                    "design_outcome": "unreviewed", "external_analysis_disposition": "",
                    "external_analysis_status": "unreviewed", "inherited_issues_disposition": "", "evidence_files": []}
        write_json(output / "review.json", template)
        shutil.copy2(root / "tasks" / task_id / "submission.json", output / "submission.json")
        return {"candidate": str(output / "candidate.bpad"), "changed": report["changed_components"],
                "native_review": "pending" if promotion_policy(root)["reviews_required"] else "optional; not performed"}


def restore_task(root, task_id, base_path=None):
    require(re.fullmatch(r"T[0-9]{3,}[A-Za-z0-9_-]*", task_id), "Invalid task ID.")
    with writer_lock(root):
        record = read_json(root / "workflow/registry" / f"{task_id}.json")
        package = root / "tasks" / task_id
        require(not (package / "working.bpad").exists(), "Task already has a working copy; it will not be overwritten.")
        require(not (package / "order.json").exists() or read_json(package / "order.json") == record, "Tracked task order differs from the registry.")
        base = Journal.load(base_path or root / JOURNAL)
        require(base.sha256 == record["base_journal_sha256"], "Supply --base from the exact historical journal revision for this task.")
        require(snapshot_files(root) == record["source_files"], "Restore matching supporting files before restoring this task.")
        replacements = {}
        manifest_path = package / "proposal/manifest.json"
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            require(manifest["base_sha256"] == base.sha256 and manifest["task"] == task_id, "Proposal belongs to a different base/task.")
            require(set(manifest["components"]) <= set(record["writes"]), "Proposal exceeds registered scope.")
            for key, item in manifest["components"].items():
                if item.get("deleted"):
                    require(key in record.get("deletes", []), f"Unregistered proposal deletion: {key}")
                    require(item.get("before_sha256") == base.hashes[key], f"Deleted component fingerprint changed: {key}")
                    replacements[key] = b""
                    continue
                data = within(package / "proposal", item["file"]).read_bytes()
                require(digest(data) == item["sha256"], f"Proposal component changed: {key}")
                replacements[key] = data
        proposed = Journal(base.replace(replacements, record.get("adds", [])))
        require(set(base.changes(proposed, record.get("deletes", []), record.get("adds", []))) <= set(record["writes"]), "Restored proposal exceeds scope.")
        atomic_write(package / "base.bpad", base.data)
        atomic_write(package / "working.bpad", proposed.data)
        shutil.copytree(root / "journal/References", package / "References", dirs_exist_ok=True)
        write_json(package / "order.json", record)
        return {"task": task_id, "restored_components": sorted(replacements), "next": "Run check before further integration."}


def promote(root, folder):
    folder = Path(folder).resolve()
    require(folder.is_relative_to((root / "generated").resolve()), "Use a generated candidate folder.")
    with writer_lock(root):
        policy = promotion_policy(root)
        report = read_json(folder / "report.json")
        review = read_json(folder / "review.json")
        candidate = Journal.load(folder / "candidate.bpad")
        current = Journal.load(root / JOURNAL)
        require(current.sha256 == report["current_sha256"], "Accepted journal changed after assembly; rebuild and review again.")
        rebuilt, fresh = check(root, report["task"])
        require(rebuilt.data == candidate.data, "Candidate changed after assembly. Import edits through the task working copy and reassemble.")
        require(candidate.sha256 == report["candidate_sha256"] == review["candidate_sha256"], "Review does not match these exact candidate bytes.")
        require(fresh["submission_sha256"] == report["submission_sha256"], "Submission changed after assembly.")
        review_fields = ("native_recalculation", "native_visual_review", "engineering_review")
        if policy["reviews_required"]:
            require(review.get("reviewer") and all(review.get(k) is True for k in review_fields), "Native evaluation, appearance and engineering reviews must be explicitly completed.")
        else:
            require(review.get("reviewer") and all(type(review.get(k)) is bool for k in review_fields),
                    "Record the responsible author and each review's actual completion status.")
        design_outcomes = ("passes", "fails", "not_applicable") + (() if policy["reviews_required"] else ("unreviewed",))
        require(review.get("design_outcome") in design_outcomes, "Record design outcome separately from coherence.")
        require(review.get("external_analysis_disposition"), "Review external-analysis currency; stale results cannot be called current.")
        analysis_statuses = ("verified_current", "excluded_from_accepted_scope", "not_applicable") + (() if policy["reviews_required"] else ("unreviewed",))
        require(review.get("external_analysis_status") in analysis_statuses, "Resolve or explicitly exclude stale external results before promotion.")
        require(review.get("inherited_issues_disposition"), "Record how inherited errors and broken links were addressed or excluded.")
        evidence = review.get("evidence_files", [])
        require(evidence, "Attach review evidence files and their SHA-256 hashes.")
        for item in evidence:
            path = within(folder, item["path"])
            require(path.is_file() and digest(path.read_bytes()) == item["sha256"], "Missing or changed review evidence.")
        refs = external_refs(candidate, folder)
        require(all(r["exists"] and not r["absolute"] for r in refs), "Promotion requires all reference files to resolve through portable relative paths.")
        for ref in refs:
            source = within(folder, ref["path"].replace("\\", "/"))
            destination = within(root / "journal", ref["path"].replace("\\", "/"))
            require(destination.is_file() and digest(destination.read_bytes()) == digest(source.read_bytes()), "Candidate reference differs from the journal resource; register it separately before preparing a task.")
        history = root / "workflow/history" / candidate.sha256
        require(not history.exists(), "This exact journal revision is already archived.")
        history.mkdir(parents=True)
        atomic_write(history / "previous.bpad", current.data)
        write_json(history / "report.json", report)
        write_json(history / "review.json", review)
        write_json(history / "promotion_policy.json", policy)
        for item in evidence:
            target = within(history, "evidence/" + item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(within(folder, item["path"]), target)
        # All integrity checks and the current review policy pass before replacement.
        atomic_write(root / JOURNAL, candidate.data)
        receipt = {"task": report["task"], "journal_sha256": candidate.sha256, "previous_sha256": current.sha256,
                   "promoted": stamp(), "review": review, "promotion_policy": policy,
                   "history": history.relative_to(root).as_posix()}
        write_json(root / "workflow/accepted.json", receipt)
        write_json(root / "workflow/completed" / f"{report['task']}.json", receipt)
        return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("inspect", help="Inventory exact journal revision; does not evaluate math")
    p.add_argument("--journal", type=Path)
    p.add_argument("--output", type=Path)
    p = commands.add_parser("roundtrip", help="Extract and reassemble every component without changing bytes")
    p.add_argument("--journal", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("prepare", help="Create an isolated folder and registered task contract")
    p.add_argument("id")
    p.add_argument("--objective", required=True)
    p.add_argument("--write", action="append", default=[])
    p.add_argument("--add", action="append", default=[], help="Register a new module key (for example report:NewCalc) to append; protects all existing components")
    p.add_argument("--delete", action="append", default=[], help="Explicitly authorize removal of an existing module; include affected link/consumer modules in --write")
    p.add_argument("--prerequisite", action="append", default=[])
    p.add_argument("--order", type=Path, help="JSON list of every component key in the registered new order (modules permuted among module slots; applied at assembly)")
    p = commands.add_parser("import-references", help="Copy verified reference filenames without modifying PDFs or journal")
    p.add_argument("source", type=Path)
    p = commands.add_parser("import-components", help="Assemble edited native component fragments into a fresh task working copy")
    p.add_argument("id")
    p = commands.add_parser("import-native", help="Check and import a Blockpad-saved task copy within its existing scope")
    p.add_argument("id")
    p.add_argument("journal", type=Path)
    p = commands.add_parser("relocate-references", help="Change only authorized xref paths to References/filename")
    p.add_argument("id")
    p = commands.add_parser("restore-task", help="Recreate ignored task copies from a tracked proposal and exact base")
    p.add_argument("id")
    p.add_argument("--base", type=Path)
    p = commands.add_parser("check", help="Reject scope violations, conflicts and stale dependencies")
    p.add_argument("id")
    p = commands.add_parser("assemble", help="Build a review candidate using the CURRENT journal")
    p.add_argument("id")
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("promote", help="Promote an exact candidate under the current review policy; archives prior journal")
    p.add_argument("folder", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "inspect":
            result = inspect(root, args.journal or root / JOURNAL, args.output or root / "generated/index.json")
        elif args.command == "roundtrip":
            result = roundtrip(args.journal or root / JOURNAL, args.output)
        elif args.command == "prepare":
            order = read_json(args.order) if args.order else None
            result = prepare(root, args.id, args.objective, args.write, args.prerequisite, args.delete, args.add, order)
        elif args.command == "import-references":
            result = import_references(root, args.source)
        elif args.command == "import-components":
            result = import_components(root, args.id)
        elif args.command == "import-native":
            result = import_native(root, args.id, args.journal)
        elif args.command == "relocate-references":
            result = relocate_references(root, args.id)
        elif args.command == "restore-task":
            result = restore_task(root, args.id, args.base)
        elif args.command == "check":
            _, result = check(root, args.id)
        elif args.command == "assemble":
            result = assemble(root, args.id, args.output)
        else:
            result = promote(root, args.folder)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (WorkflowError, OSError, KeyError, json.JSONDecodeError) as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
