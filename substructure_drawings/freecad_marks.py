"""Write the SDM 4.3 bar marks into the FreeCAD model (run inside FreeCAD).

The marks come from ``output/bar_mark_register.csv``, which the DXF generator
derives from a snapshot of a specific model file (its SHA-256 is in
``output/manifest.json``).  Applying them keeps the drawings and the model on
one mapping.  Re-run after any controller regenerates bars (new bars are
created with the controllers' default ``<support>-<id>`` marks).

What changes, and nothing else:

* ``Mark`` of every listed native rebar (cap cages, backwall and cheek walls,
  pedestals, pier wall).  Lug WWR wires keep their fabric designation.
* Column A ("Mark") of each bar row in the matching schedule spreadsheet; the
  controllers copy the mark there as text when a schedule is written.
* ``ScheduleJSON`` of the three cap-cage quantity objects, refreshed by their
  own controller (it lists each bar's mark).
* ``MarkStatus`` of ``PierWallSteelInputs`` (D-076 wrote "drawing SDM marks
  pending" there; the bar list repeats it while the PW- identifiers stand).

Geometry is not recomputed: touched rebars are purged and only the edited
spreadsheets are recomputed.  Dated check snapshots are left as recorded.
"""
import csv
import json
from pathlib import Path

REGISTER = Path(__file__).resolve().parent / "output" / "bar_mark_register.csv"
# Schedule spreadsheets: <prefix><support>Schedule, listing the bars of the
# <prefix><support>Bars group by name (BarNames).  The pier wall controller
# (pier_wall_rings) keeps one PierWallSteelSchedule for its 124 bars.
SCHEDULE_PREFIXES = ("Cage", "SteelBridge", "PedSteel", "PierWallSteel")
WALL_INPUTS = "PierWallSteelInputs"
MARK_STATUS_WRITTEN = ("SDM drawing marks written from the DXF bar-mark register "
                       "(substructure_drawings/freecad_marks.py); PW- identifiers remain the bar object names")


def load_register(path=REGISTER):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    marks = {r["native_object"]: r for r in rows}
    if len(marks) != len(rows):
        raise ValueError("Duplicate native objects in the bar-mark register")
    return marks


def cell_text(sheet, cell):
    """Text of a schedule cell; FreeCAD stores literal text with a leading quote."""
    c = sheet.getContents(cell)
    return c[1:] if c.startswith("'") else c


def schedule_for(doc, bar):
    """The schedule spreadsheet listing ``bar`` (by its BarNames list)."""
    for o in bar.InList:
        if o.TypeId == "App::DocumentObjectGroup" and o.Name.endswith("Bars"):
            sheet = doc.getObject(o.Name[:-4] + "Schedule")
            if sheet is not None and bar.Name in list(getattr(sheet, "BarNames", [])):
                return sheet
    return None


def plan(doc, register):
    """Check preconditions and return the list of (bar, old, new) changes."""
    changes, errors = [], []
    for name, row in sorted(register.items()):
        bar = doc.getObject(name)
        if bar is None:
            errors.append("missing " + name)
            continue
        if "Mark" not in bar.PropertiesList:
            errors.append("no Mark on " + name)
            continue
        if bar.Mark not in (row["model_mark"], row["mark"]):
            errors.append("%s: Mark %r is neither the recorded %r nor %r" % (name, bar.Mark, row["model_mark"], row["mark"]))
            continue
        if "Mark" in dict(getattr(bar, "ExpressionEngine", [])):
            errors.append(name + ": Mark is expression-driven")
            continue
        if bar.Mark != row["mark"]:
            changes.append((bar, bar.Mark, row["mark"]))
    if errors:
        raise ValueError("Bar-mark preconditions failed:\n" + "\n".join(errors))
    return changes


def apply(doc, register):
    """Apply the register marks; returns a JSON-serialisable change record."""
    changes = plan(doc, register)
    sheets, cells, quantities = {}, [], set()
    for bar, old, new in changes:
        bar.Mark = new
        sheet = schedule_for(doc, bar)
        if sheet is None:
            raise ValueError("No schedule lists " + bar.Name)
        row = list(sheet.BarNames).index(bar.Name) + 2
        current = cell_text(sheet, "A%d" % row)
        if current not in (old, new):
            raise ValueError("%s A%d holds %r, expected %r" % (sheet.Name, row, current, old))
        if current != new:
            # As the controllers write it: plain text, stored by FreeCAD as '<text>.
            sheet.set("A%d" % row, "'" + new)
            cells.append((sheet.Name, "A%d" % row, old, new))
        sheets[sheet.Name] = sheet
        q = getattr(bar, "CageInputs", None)
        if q is not None and q.Name.startswith("Cage"):
            quantities.add(q.Name[:-len("Inputs")] + "Quantities")
    for name in sorted(quantities):
        q = doc.getObject(name)
        q.Proxy.execute(q)
    status_changed = wall_mark_status(doc, register)
    # Marks and quantity text do not drive geometry: no rebar/cap recompute.
    for o in doc.Objects:
        o.purgeTouched()
    for s in sheets.values():
        s.touch()
    if sheets:
        doc.recompute(list(sheets.values()))
    # Recomputing a sheet marks its parent groups; plain groups have nothing to
    # execute, so clear them rather than trigger a wider recompute.
    groups = [o for o in doc.Objects if o.TypeId == "App::DocumentObjectGroup" and "Touched" in o.State]
    for g in groups:
        g.purgeTouched()
    pending = [o.Name for o in doc.Objects if "Touched" in o.State or "Invalid" in o.State]
    return {
        "bars_changed": len(changes),
        "bars_already_marked": len(register) - len(changes),
        "schedule_cells_changed": len(cells),
        "schedules": sorted(sheets),
        "quantities_refreshed": sorted(quantities),
        "groups_untouched": sorted(g.Name for g in groups),
        "pending_objects_after": pending,
        "mark_status": status_changed,
        "changes": [{"object": b.Name, "old": o, "new": n} for b, o, n in changes],
    }


def wall_bars(doc, register):
    """The pier wall bars of the register (those listed by PierWallSteelSchedule)."""
    sheet = doc.getObject("PierWallSteelSchedule")
    names = set(getattr(sheet, "BarNames", [])) if sheet is not None else set()
    return sorted(n for n in register if n in names)


def wall_mark_status(doc, register):
    """Set MarkStatus on the pier wall inputs once every wall bar carries its
    SDM mark; returns {object, old, new} or None when nothing changed."""
    inp = doc.getObject(WALL_INPUTS)
    bars = wall_bars(doc, register)
    if inp is None or "MarkStatus" not in inp.PropertiesList or not bars:
        return None
    if "MarkStatus" in dict(getattr(inp, "ExpressionEngine", [])):
        raise ValueError(WALL_INPUTS + ": MarkStatus is expression-driven")
    if any(doc.getObject(n).Mark != register[n]["mark"] for n in bars):
        return None
    if inp.MarkStatus == MARK_STATUS_WRITTEN:
        return None
    old = inp.MarkStatus
    inp.MarkStatus = MARK_STATUS_WRITTEN
    return {"object": inp.Name, "old": old, "new": MARK_STATUS_WRITTEN}


def verify(doc, register):
    """Independent check that model marks, schedules and quantities agree."""
    failures = []
    inp = doc.getObject(WALL_INPUTS)
    if inp is not None and wall_bars(doc, register) and inp.MarkStatus != MARK_STATUS_WRITTEN:
        failures.append("%s MarkStatus %r" % (WALL_INPUTS, inp.MarkStatus))
    for name, row in register.items():
        bar = doc.getObject(name)
        if bar.Mark != row["mark"]:
            failures.append("%s Mark %r != %r" % (name, bar.Mark, row["mark"]))
        sheet = schedule_for(doc, bar)
        r = list(sheet.BarNames).index(name) + 2
        shown = str(sheet.get("A%d" % r))
        if cell_text(sheet, "A%d" % r) != row["mark"] or shown != row["mark"]:
            failures.append("%s A%d %r / %r != %r" % (sheet.Name, r, sheet.getContents("A%d" % r), shown, row["mark"]))
    for q in (o for o in doc.Objects if o.Name.startswith("Cage") and o.Name.endswith("Quantities")):
        for item in json.loads(q.ScheduleJSON):
            if item["object"] in register and item["mark"] != register[item["object"]]["mark"]:
                failures.append("%s lists %s as %r" % (q.Name, item["object"], item["mark"]))
    return failures
