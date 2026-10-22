"""Set the pier wall end U return legs to the selected D-084 case (27 in, 72 in before).

Headless FreeCAD 1.1 run on a disposable copy of the current model, after the
D-079 job (evidence/2026-10-22-ring-plate-half-inch/build_candidate.py). Inputs
come from environment variables (D2_SNAPSHOT: engine snapshot of the selected
case; D2_OUT: scratch folder). The live input ULeg changes and the controller's
regenerate() rebuilds the wall steel: only the 38 end U returns change shape
(their paths and bars), the quantities, the schedule and the source provenance;
the face and end-face bars, the ring plates, the wall, the piles and every
unrelated object are left as they are. The authoritative model file is never
written here.
"""
from pathlib import Path
import sys, json, os, traceback, zipfile, hashlib, copy, xml.etree.ElementTree as E
sys.dont_write_bytecode = True
ROOT = Path('C:/github/D2MPDB'); MAIN = ROOT / 'project_current/geometry/freecad'
OUT = Path(os.environ.get('D2_OUT', str(ROOT / '.validation/pier-wall-u-leg'))); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(MAIN / 'runtime'))
import FreeCAD as App, Part  # noqa: E402
from freecad_tools import bridge, native_archive, pier_wall_rings as pw  # noqa: E402
IN = pw.IN


def dump(p, v): p.write_text(json.dumps(v, indent=2) + '\n')


def equal_shapes(a, b, tol=1e-5): return abs(a.cut(b).Volume) < tol and abs(b.cut(a).Volume) < tol


def bar_metrics(rb):
    b = rb.Shape.optimalBoundingBox(True, False)
    return dict(length_in=rb.Length.Value / IN, mark=str(rb.Mark), label=rb.Label, family=str(rb.Base.Family),
                bbox_in=[round(v / IN, 4) for v in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)], weight_lb=rb.NominalWeightLb)


manifest = json.loads((MAIN / 'manifest.json').read_text()); source = MAIN / manifest['model']['path']
snapshot = json.loads(Path(os.environ['D2_SNAPSHOT']).read_text()); new_case = snapshot['case']
record = {'status': 'STARTED', 'source_sha256': native_archive.sha(source), 'snapshot_sha256': snapshot['sha256']}
report = OUT / 'build.json'; doc = None
try:
    assert record['source_sha256'] == manifest['model']['sha256'], 'Model differs from the manifest'
    print('Opening source', flush=True); doc = App.openDocument(str(source))
    inp = doc.PierWallSteelInputs; q = doc.PierWallSteelQuantities; sh = doc.PierWallSteelSchedule
    rings = list(q.Rings); bars = list(q.Bars)
    assert len(rings) == 20 and len(bars) == 124
    u_bars = [rb for rb in bars if 'U return' in str(rb.Base.Family)]
    assert len(u_bars) == 38, len(u_bars)
    changed = {inp.Name, q.Name, sh.Name, *[rb.Name for rb in u_bars], *[rb.Base.Name for rb in u_bars]}
    protected = [o.Name for o in doc.Objects if o.Name not in changed]
    record['protected_objects'] = len(protected); record['changed_objects'] = sorted(changed)
    before = bridge.source_state(doc, protected)
    # regenerate() re-executes every wall bar and every ring plate: the
    # unchanged ones come back with the same geometry (re-serialized BReps,
    # shifted unique-label suffixes), restored byte-for-byte from the source
    # by the staging step.
    wall_steel = {o.Name: o.Shape.copy() for o in doc.Objects if o.Name.startswith(('PierWallSteel', 'PierWallRing'))
                  and 'Shape' in o.PropertiesList and o.Name not in changed}

    def unchanged(label):
        now = bridge.source_state(doc, protected); drift = []
        for n in protected:
            if now[n] == before[n]: continue
            keys = [k for k in before[n] if before[n][k] != now[n][k]]
            if n in wall_steel and set(keys) <= {'label', 'shape'} and equal_shapes(doc.getObject(n).Shape, wall_steel[n]): continue
            if n.startswith('PierWallSteel') and n.endswith('Path') and set(keys) <= {'label', 'shape'}: continue
            drift.append((n, keys))
        assert not drift, (label, drift[:10])
        record.setdefault('state_checks', []).append(dict(step=label, exact=now == before,
            wall_steel_reserialized=sorted(n for n in wall_steel if now[n]['shape'] != before[n]['shape']),
            wall_steel_relabelled=sorted(n for n in wall_steel if now[n]['label'] != before[n]['label'])))
    old_case = json.loads(inp.SourceCaseJSON)
    diff = [k for k in new_case if new_case[k] != old_case.get(k)]
    assert diff == ['u_leg_in'] and set(new_case) == set(old_case), diff
    assert abs(inp.ULeg.Value - old_case['u_leg_in'] * IN) < 1e-9 and abs(inp.RingThickness.Value - new_case['ring_t_in'] * IN) < 1e-9
    marks_before = {rb.Name: str(rb.Mark) for rb in bars}
    old_u = {rb.Name: dict(shape=rb.Shape.copy(), **bar_metrics(rb)) for rb in u_bars}
    record['before'] = dict(u_leg_in=inp.ULeg.Value / IN, total_steel_length_in=q.TotalSteelLength.Value / IN, steel_weight_lb=q.NominalSteelWeightLb,
                            u_returns={n: {k: v for k, v in m.items() if k != 'shape'} for n, m in old_u.items()})
    # Ordinary native edit: change the live input and regenerate the wall steel.
    print('Setting the U leg and regenerating', flush=True)
    inp.ULeg = f"{new_case['u_leg_in']} in"; pw.regenerate(inp); doc.recompute()
    bad = [o.Name for o in doc.Objects if 'Invalid' in o.State]
    assert not bad, bad
    unchanged('regenerate at 27 in')
    assert [rb.Name for rb in q.Bars] == [rb.Name for rb in bars], 'bar set changed'
    assert {rb.Name: str(rb.Mark) for rb in q.Bars} == marks_before, 'a bar mark changed'
    after = {}
    delta = (old_case['u_leg_in'] - new_case['u_leg_in']) * IN
    for rb in u_bars:
        m = bar_metrics(rb); o = old_u[rb.Name]
        # two straight legs each shortened by the leg difference
        assert abs((o['length_in'] - m['length_in']) * IN - 2 * delta) < 1e-6, (rb.Name, o['length_in'], m['length_in'])
        # the new U lies inside the former one (same bend, same faces, shorter legs)
        s = rb.Shape.copy()
        assert abs(s.cut(o['shape']).Volume) < 1e-6, (rb.Name, 'containment')
        after[rb.Name] = {k: v for k, v in m.items() if k != 'shape'}
    for rb in q.Bars:
        if rb.Name not in old_u:
            assert equal_shapes(rb.Shape, wall_steel[rb.Name]), (rb.Name, 'a non-U bar changed')
    record['after'] = dict(u_leg_in=inp.ULeg.Value / IN, total_steel_length_in=q.TotalSteelLength.Value / IN, steel_weight_lb=q.NominalSteelWeightLb, u_returns=after)
    assert abs((record['before']['total_steel_length_in'] - record['after']['total_steel_length_in']) - 38 * 2 * (old_case['u_leg_in'] - new_case['u_leg_in'])) < 1e-6
    print('Validating geometry, cover and steel intersections', flush=True)
    record['validation'] = pw.validate(inp); dump(report, record)
    assert record['validation']['status'] == 'PASS', [c for c in record['validation']['checks'] if c['status'] != 'PASS']
    # Native edit round trip: the former leg reproduces the former U returns.
    print('Testing native edit round trip', flush=True)
    inp.ULeg = f"{old_case['u_leg_in']} in"; pw.regenerate(inp); doc.recompute()
    for rb in u_bars: assert equal_shapes(rb.Shape, old_u[rb.Name]['shape']), rb.Name
    inp.ULeg = f"{new_case['u_leg_in']} in"; pw.regenerate(inp); doc.recompute()
    for rb in u_bars: assert abs((old_u[rb.Name]['length_in'] - rb.Length.Value / IN) * IN - 2 * delta) < 1e-6
    assert {rb.Name: str(rb.Mark) for rb in q.Bars} == marks_before
    record['native_edit_restore'] = True
    unchanged('native edit round trip')
    # Provenance: the immutable case snapshot now names the selected D-084 case.
    inp.SourceCaseJSON = json.dumps(new_case); inp.SourceCaseSHA256 = snapshot['sha256']
    inp.SourceFailuresJSON = json.dumps(snapshot['failed_checks'])
    inp.SourcePath = 'project_current/pier_wall/selected_case.json (D-084, 22 October 2026)'
    inp.EngineeringStatus = ('CAD end U return legs 27 in and ring plates 1/2 in match the selected D-084 case (LRFD 10th 5.10.8.2.1 development, '
                             '26-in Class B lap); wall dimensions match D-075 within 0.001 in; RING-GRID tolerance failure remains; engineering acceptance open')
    assert inp.Limitations == pw.LIMITS and inp.ScheduleNote == pw.LIMITS
    raw = OUT / 'native.FCStd'; candidate = OUT / 'candidate.FCStd'
    for p in (raw, candidate):
        if p.exists(): p.unlink()
    for o in doc.Objects: o.purgeTouched()
    print('Saving candidate', flush=True); doc.saveAs(str(raw))
    record['archive'] = native_archive.preserve(source, raw, candidate, protected, record['source_sha256'])
    with zipfile.ZipFile(source) as z: original = {n: z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(candidate) as z: updated = {n: z.read(n) for n in z.namelist()}
    gui = E.fromstring(original['GuiDocument.xml'])
    for el in gui.iter():
        ref = el.get('file')
        if ref: updated[ref] = original[ref]
    updated['GuiDocument.xml'] = original['GuiDocument.xml']
    docrefs = {el.get('file') for el in E.fromstring(updated['Document.xml']).iter() if el.get('file')}
    guirefs = {el.get('file') for el in gui.iter() if el.get('file')}
    keep = {n: b for n, b in updated.items() if n in original or n in docrefs or n in guirefs or n in ('Document.xml', 'GuiDocument.xml')}
    assert docrefs <= set(keep) and guirefs <= set(keep)
    candidate.unlink()
    with zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in keep.items(): z.writestr(n, b)
    with zipfile.ZipFile(candidate) as z: assert z.testzip() is None
    record['dropped_unreferenced_entries'] = sorted(set(updated) - set(keep))

    def canonical(node, data):
        node = copy.deepcopy(node)
        for el in node.iter():
            path = el.get('file')
            if path: el.set('file', 'sha256:' + hashlib.sha256(data[path]).hexdigest())
        return E.tostring(node)
    with zipfile.ZipFile(candidate) as z: final = {n: z.read(n) for n in z.namelist()}

    def nodes(data, filename, path): return {o.get('name'): o for o in E.fromstring(data[filename]).find(path)}
    old, new = nodes(original, 'Document.xml', 'ObjectData'), nodes(final, 'Document.xml', 'ObjectData')
    assert set(old) == set(new)
    changed_records = sorted(n for n in old if canonical(old[n], original) != canonical(new[n], final))
    assert set(changed_records) <= changed, sorted(set(changed_records) - changed)
    assert final['GuiDocument.xml'] == original['GuiDocument.xml']
    for ref in guirefs: assert final[ref] == original[ref]
    record['file_preservation'] = dict(status='PASS', changed_records=changed_records, gui_document_byte_identical=True,
                                       existing_records_preserved=len(old) - len(changed_records))
    App.closeDocument(doc.Name); doc = None
    print('Cold reopening candidate', flush=True); doc = App.openDocument(str(candidate))
    assert before == bridge.source_state(doc, protected), 'Cold reopen changed existing model'
    inp = doc.PierWallSteelInputs; q = doc.PierWallSteelQuantities
    assert abs(inp.ULeg.Value - new_case['u_leg_in'] * IN) < 1e-9 and inp.SourceCaseSHA256 == snapshot['sha256']
    assert json.loads(inp.SourceCaseJSON) == new_case
    assert {rb.Name: str(rb.Mark) for rb in q.Bars} == marks_before
    for rb in q.Bars:
        if rb.Name in old_u: assert abs((old_u[rb.Name]['length_in'] - rb.Length.Value / IN) * IN - 2 * delta) < 1e-6, rb.Name
    record['cold_reopen_validation'] = pw.validate(inp)
    assert record['cold_reopen_validation']['status'] == 'PASS'
    assert type(inp.Proxy).__name__ == 'InputsProxy' and type(doc.PierWallRingP1R1.Proxy).__name__ == 'RingProxy'
    # Ordinary native regenerate after reopen (the user's workflow) keeps the legs.
    inp.ULeg = f"{new_case['u_leg_in'] + 6} in"; pw.regenerate(inp); doc.recompute()
    assert abs((doc.PierWallSteelE1U01.Length.Value - old_u['PierWallSteelE1U01']['length_in'] * IN) - 2 * (6 - (old_case['u_leg_in'] - new_case['u_leg_in'])) * IN) < 1e-6
    inp.ULeg = f"{new_case['u_leg_in']} in"; pw.regenerate(inp); doc.recompute()
    assert abs((old_u['PierWallSteelE1U01']['length_in'] - doc.PierWallSteelE1U01.Length.Value / IN) * IN - 2 * delta) < 1e-6
    unchanged('ordinary regenerate after cold reopen')
    record.update(status='VERIFIED', ordinary_native_recompute=True, cold_reopen=True, objects=len(doc.Objects),
                  candidate=str(candidate), candidate_sha256=native_archive.sha(candidate), candidate_bytes=candidate.stat().st_size,
                  source_unchanged=native_archive.sha(source) == record['source_sha256'])
    assert record['source_unchanged']; dump(report, record)
    print(json.dumps({k: v for k, v in record.items() if k not in ('validation', 'cold_reopen_validation', 'before', 'after')}, indent=2), flush=True)
    code = 0
except Exception:
    record.update(status='FAIL', error=traceback.format_exc()); dump(report, record); traceback.print_exc(); code = 1
finally:
    if doc: App.closeDocument(doc.Name)
sys.stdout.flush(); sys.stderr.flush(); os._exit(code)
