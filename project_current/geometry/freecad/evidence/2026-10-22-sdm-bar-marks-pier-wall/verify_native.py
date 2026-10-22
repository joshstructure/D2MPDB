"""D-083 cold reopen (run with freecadcmd): prior archive vs delivery, no recompute or save (as the D-042 and D-060 jobs)."""
from pathlib import Path
import sys, json, hashlib, re, traceback
sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = Path('C:/github/D2MPDB')
BASE = REPO/'project_current/geometry/freecad'
sys.path.insert(0, str(BASE/'runtime'))
sys.path.insert(0, str(REPO))
import FreeCAD as App
from freecad_tools import cap_cages, mse, bridge, drainage_trial, adopt_drainage, current_source, design_steel, pedestal_ubars, pedestal_edges, pedestal_contact, backwall_extensions, backwall_top, mse_revision, mse_corrections, mse_wall_tops, cheek_steel, lug_wwr, deck_edge_details, return_cheek_details, standard_chamfers, end_bent_closure, geotechnical_straps, cheek_hooks, pier_cheeks, level_seats, pier_wall_rings  # noqa: F401,E501
from substructure_drawings import freecad_marks
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
SKIP = {'Shape', 'Proxy', 'ExpressionEngine', 'Visibility', '_GroupTouched'}
TARGET = {'Mark', 'cells', 'ScheduleJSON', 'MarkStatus'}
STATUS_OBJECTS = ('CheekSteelChecks', 'CheekLugWWRChecks', 'WallSteelChecks', 'PedestalSteelChecks', 'CageEB1Checks',
                  'CagePierChecks', 'CageEB2Checks', 'PierWallSteelInputs')


def props(doc):
    out = {}
    for o in doc.Objects:
        rec = {}
        for p in o.PropertiesList:
            if p in SKIP:
                continue
            try:
                v = getattr(o, p)
                if hasattr(v, 'exportBrepToString'):  # shape-valued property: hash its BRep
                    rec[p] = hashlib.sha256(v.exportBrepToString().encode()).hexdigest()
                elif isinstance(v, list) and v and hasattr(v[0], 'Name'):
                    rec[p] = [x.Name for x in v]
                elif hasattr(v, 'Name') and hasattr(v, 'TypeId'):
                    rec[p] = v.Name
                else:
                    s = str(v)
                    rec[p] = ('<%s>' % type(v).__name__) if ' at 0x' in s or re.search(r' at [0-9A-F]{8,}', s) else s
            except Exception as exc:
                rec[p] = 'ERR ' + type(exc).__name__
        if o.TypeId == 'Spreadsheet::Sheet':
            rec['cells'] = {c: o.getContents(c) for c in o.getUsedCells()}
        out[o.Name] = rec
    return out


def snapshot(path):
    doc = App.openDocument(str(path))
    names = [o.Name for o in doc.Objects]
    return doc, dict(state=bridge.source_state(doc, names), props=props(doc),
                     proxies={o.Name: (type(o.Proxy).__module__, type(o.Proxy).__name__) for o in doc.Objects if 'Proxy' in o.PropertiesList},
                     invalid=sorted(o.Name for o in doc.Objects if 'Invalid' in o.State),
                     touched=sorted(o.Name for o in doc.Objects if 'Touched' in o.State),
                     status={n: (getattr(doc.getObject(n), 'Status', None), getattr(doc.getObject(n), 'GeometryStatus', None),
                                 getattr(doc.getObject(n), 'DetailingStatus', None), getattr(doc.getObject(n), 'EngineeringStatus', None))
                             for n in STATUS_OBJECTS if doc.getObject(n)})


report = {'status': 'PREPARED'}
try:
    pres = json.loads((OUT/'preservation.json').read_text())
    assert pres['status'] == 'PASS' and sha(OUT/'Delivery.FCStd') == pres['model_sha256']
    register = freecad_marks.load_register()
    old, before = snapshot(OUT/'Before.FCStd')
    pre_failures = freecad_marks.verify(old, register)
    App.closeDocument(old.Name)
    new, after = snapshot(OUT/'Delivery.FCStd')
    assert set(after['state']) == set(before['state'])
    assert after['state'] == before['state'], [n for n in before['state'] if before['state'][n] != after['state'][n]][:10]
    assert after['proxies'] == before['proxies']
    assert after['invalid'] == before['invalid'] and after['touched'] == before['touched']
    assert after['status'] == before['status'], (before['status'], after['status'])
    changed = {}
    for name, rec in before['props'].items():
        for k, v in rec.items():
            if after['props'][name].get(k) != v:
                # Sheets expose each cell as a property; only column-A mark cells may change.
                cell = name.endswith('Schedule') and re.fullmatch(r'A\d+', k)
                assert k in TARGET or cell, (name, k, v, after['props'][name].get(k))
                changed.setdefault('schedule cell A' if cell else k, []).append(name)
        assert set(after['props'][name]) == set(rec), name
    assert changed.get('MarkStatus') == ['PierWallSteelInputs'], changed.get('MarkStatus')
    failures = freecad_marks.verify(new, register)
    assert not failures, failures[:10]
    wwr = [o for o in new.Objects if o.Name.startswith('WWRCheek') and 'Mark' in o.PropertiesList]
    assert len(wwr) == 180 and all(before['props'][o.Name]['Mark'] == o.Mark for o in wwr)
    wall = freecad_marks.wall_bars(new, register)
    assert len(wall) == 124 and set(changed['Mark']) == set(wall), (len(wall), len(changed['Mark']))
    marks = sorted({o.Mark for o in new.Objects if o.Name in register})
    pier = sorted({o.Mark for o in new.Objects if o.Name in register and register[o.Name]['support'] == 'PIER'})
    wall_marks = {m: sum(1 for n in wall if new.getObject(n).Mark == m) for m in sorted({new.getObject(n).Mark for n in wall})}
    report = dict(status='PASS', model_sha256=pres['model_sha256'], previous_model_sha256=pres['before_sha256'],
                  objects=len(after['state']), bars_marked=len(register), distinct_marks=marks, pier_marks=pier,
                  pier_wall_marks=wall_marks, mark_status=new.getObject('PierWallSteelInputs').MarkStatus,
                  register_failures_before=len(pre_failures), register_failures_after=0,
                  changed_properties={k: len(v) for k, v in changed.items()},
                  changed_objects={k: sorted(v) for k, v in changed.items() if k != 'Mark'},
                  geometry_placements_expressions_dependencies_labels_preserved=True,
                  all_other_property_values_preserved=True, controller_types_preserved=True,
                  check_statuses=after['status'], invalid_objects=after['invalid'], touched_objects=after['touched'],
                  wwr_wire_marks_unchanged=len(wwr),
                  validation='Cold-opened the prior archive and the delivery in FreeCAD 1.1.3 with the pinned controllers. '
                             'Compared native shape hashes, placements, expressions, dependencies, labels, controller types, '
                             'check statuses and every other readable property value of all %d objects. No recompute or save.'
                             % len(after['state']))
    App.closeDocument(new.Name)
except Exception:
    report['status'] = 'FAIL'
    report['traceback'] = traceback.format_exc()
(OUT/'cold-reopen.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k not in ('traceback', 'changed_objects')}, indent=2))
if report['status'] != 'PASS':
    print(report.get('traceback', ''))
