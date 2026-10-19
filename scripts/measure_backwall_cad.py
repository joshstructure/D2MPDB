"""Measure the end-bent solids of the saved FreeCAD model for the backwall calculation (end_bent_walls).

Runs under FreeCAD's own Python (no document is opened, recomputed or saved): the saved BReps of the two caps,
two backwalls, four cheeks and two bridge landings are read from the .FCStd archive, moved into the BridgePGL
frame (x along the bridge, y transverse, z elevation; feet) and measured. The verified NetVolume properties are
read from Document.xml. The result is the `native_geometry` / `cad_updates` block of
end_bent_walls/data/project_evidence.json (same keys and conventions as the 16 October 2026 snapshot):

    & "C:\\Program Files\\FreeCAD 1.1\\bin\\python.exe" scripts\\measure_backwall_cad.py [--write]

Without --write the measurement is printed; with --write it replaces the two blocks in project_evidence.json
and the landing tributary length (L_slab) of the landing confirmation.
"""
import copy
import hashlib
import json
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / 'project_current' / 'geometry' / 'freecad' / 'B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd'
EVIDENCE = ROOT / 'end_bent_walls' / 'data' / 'project_evidence.json'
FT = 304.8
FT3 = FT ** 3
CAPS = {'EB1': 'BridgeCapEB1', 'EB2': 'BridgeCapEB2'}
BACKWALLS = {'EB1': 'BridgeBackwallEB1', 'EB2': 'BridgeBackwallEB2'}
CHEEKS = {'EB1': ('BridgeCheekEB11', 'BridgeCheekEB12'), 'EB2': ('BridgeCheekEB21', 'BridgeCheekEB22')}
LANDINGS = ('A_BridgeLandingAtReturns', 'B_BridgeLandingAtReturns')
OBJECTS = [CAPS['EB1'], CAPS['EB2'], BACKWALLS['EB1'], *CHEEKS['EB1'], BACKWALLS['EB2'], *CHEEKS['EB2'], *LANDINGS]
TOL = 1e-6


def records(doc):
    """{object name: {property name: element}} of Document.xml."""
    out = {}
    for obj in doc.find('ObjectData'):
        out[obj.get('name')] = {p.get('name'): p for p in obj.find('Properties')}
    return out


def placement(el):
    import FreeCAD as App
    p = el.find('PropertyPlacement')
    pos = App.Vector(float(p.get('Px')), float(p.get('Py')), float(p.get('Pz')))
    rot = App.Rotation(float(p.get('Q0')), float(p.get('Q1')), float(p.get('Q2')), float(p.get('Q3')))
    return App.Placement(pos, rot)


def measure(model=MODEL):
    import FreeCAD as App  # noqa: F401
    import Part
    data = model.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    z = zipfile.ZipFile(model)
    doc = ET.fromstring(z.read('Document.xml'))
    props = records(doc)
    frame = placement(props['BridgePGL']['Frame'])
    inverse = frame.inverse()
    slab_mm = float(props['MSEInputs']['SlabThickness'].find('Float').get('value'))
    top_drop_in = {k: float(props[n]['TopDrop'].find('Float').get('value')) / 25.4 for k, n in BACKWALLS.items()}
    objects = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name in OBJECTS:
            file = props[name]['Shape'].find('Part').get('file')
            path = Path(tmp) / file
            path.write_bytes(z.read(file))
            shape = Part.Shape()
            shape.importBrep(str(path))
            shape.Placement = inverse.multiply(shape.Placement)      # saved BReps carry their global placement
            bb = shape.BoundBox
            c = shape.Solids[0].CenterOfMass if shape.Solids else shape.CenterOfMass
            rec = {'bounds_ft': [bb.XMin / FT, bb.XMax / FT, bb.YMin / FT, bb.YMax / FT, bb.ZMin / FT, bb.ZMax / FT],
                   'centroid_ft': [c.x / FT, c.y / FT, c.z / FT], 'volume_ft3': shape.Volume / FT3, 'valid': shape.isValid(),
                   'shape_file': file}
            if name in BACKWALLS.values():
                zmax = bb.ZMax
                top = [v.Point for v in shape.Vertexes if v.Point.z > bb.ZMin + 0.5 * (zmax - bb.ZMin)]
                rec['top_vertices_ft'] = [[p.x / FT, p.y / FT, p.z / FT] for p in top]
                # the top faces: every face whose normal points up; their lowest and highest vertices
                tops = [f for f in shape.Faces if f.normalAt(0.5, 0.5).z > 0.5]
                zs = [v.Point.z for f in tops for v in f.Vertexes]
                rec['sampled_top_range_ft'] = [min(zs) / FT, max(zs) / FT]
                # the top at the two ends of the wall (edge heights): vertices on the top faces at the extreme y
                ymin, ymax = bb.YMin, bb.YMax
                edge = [v.Point.z for f in tops for v in f.Vertexes if abs(v.Point.y - ymin) < 0.1 or abs(v.Point.y - ymax) < 0.1]
                rec['edge_top_min_ft'] = min(edge) / FT
            net = props[name].get('NetVolume')
            rec['net_volume_ft3'] = float(net.find('Float').get('value')) / FT3 if net is not None else rec['volume_ft3']
            objects[name] = rec
    # derived inputs (same conventions as the 16 October 2026 snapshot)
    cap = {k: objects[n] for k, n in CAPS.items()}
    bw = {k: objects[n] for k, n in BACKWALLS.items()}
    ck = {k: [objects[n] for n in pair] for k, pair in CHEEKS.items()}
    cap_top = {k: cap[k]['bounds_ft'][5] for k in cap}
    inch = lambda ft: ft * 12
    b_cap = {k: inch(cap[k]['bounds_ft'][1] - cap[k]['bounds_ft'][0]) for k in cap}
    h_cap = {k: inch(cap[k]['bounds_ft'][5] - cap[k]['bounds_ft'][4]) for k in cap}
    L_cap = {k: inch(cap[k]['bounds_ft'][3] - cap[k]['bounds_ft'][2]) for k in cap}
    t_bw = {k: inch(bw[k]['bounds_ft'][1] - bw[k]['bounds_ft'][0]) for k in bw}
    L_bw = {k: inch(bw[k]['bounds_ft'][3] - bw[k]['bounds_ft'][2]) for k in bw}
    L_load = {k: inch(max(c['bounds_ft'][3] for c in ck[k]) - min(c['bounds_ft'][2] for c in ck[k])) for k in ck}
    t_ck = {k: inch(max(c['bounds_ft'][3] - c['bounds_ft'][2] for c in ck[k])) for k in ck}
    H_bw = {k: bw[k]['sampled_top_range_ft'][1] - cap_top[k] for k in bw}
    H_bw_edge = {k: bw[k]['edge_top_min_ft'] - cap_top[k] for k in bw}
    H_ck = {k: max(c['bounds_ft'][5] for c in ck[k]) - cap_top[k] for k in ck}
    V_ck = {k: sum(c['net_volume_ft3'] for c in ck[k]) for k in ck}
    pile_line = {k: cap[k]['bounds_ft'][0] + b_cap[k] / 2 / 12 for k in cap}
    # cheek centroid offset from the nominal pile line, positive toward the span (+x at End Bent 1, -x at End Bent 2)
    toward_span = {'EB1': 1.0, 'EB2': -1.0}
    dx_ck = {k: toward_span[k] * inch(sum(c['centroid_ft'][0] for c in ck[k]) / 2 - pile_line[k]) for k in ck}
    same = lambda d, tol=1e-6: max(d.values()) - min(d.values()) <= tol
    for label, d in (('b_cap', b_cap), ('h_cap', h_cap), ('L_cap', L_cap), ('t_bw', t_bw), ('L_bw', L_bw), ('L_load', L_load), ('t_ck', t_ck)):
        if not same(d):
            raise SystemExit(f'{label} differs between the end bents: {d}')
    updates = {
        'L_cap': round(L_cap['EB1'], 9), 'L_bw': round(L_bw['EB1'], 9), 'L_load': round(L_load['EB1'], 9),
        'b_cap': round(b_cap['EB1'], 9), 'h_cap': round(h_cap['EB1'], 9), 't_bw': round(t_bw['EB1'], 9),
        'H_bw': max(H_bw.values()), 'H_bw_edge': min(H_bw_edge.values()), 't_ck': round(t_ck['EB1'], 9),
        'w_ck': 42.0,                                   # 8 x 42 in web; the 48-in bounding length includes the 6-in rear lug
        'H_ck': max(H_ck.values()),
        'V_cap': max(c['net_volume_ft3'] for c in cap.values()), 'V_bw': min(w['net_volume_ft3'] for w in bw.values()),
        'V_ck': max(V_ck.values()),                      # the heavier pair, with its lugs
        'dx_ck': max(dx_ck.values()),                    # the centroid nearest the span (largest overturning arm)
        't_slab': round(slab_mm / 25.4, 9),
    }
    per_bent = {'cap_top_ft': cap_top, 'H_bw_ft': H_bw, 'H_bw_edge_ft': H_bw_edge, 'H_ck_ft': H_ck, 'V_ck_ft3': V_ck, 'dx_ck_in': dx_ck,
                'top_drop_in': top_drop_in, 'backwall_top_elevations_ft': {k: [bw[k]['edge_top_min_ft'], bw[k]['sampled_top_range_ft'][1]] for k in bw}}
    landing = {n: objects[n]['net_volume_ft3'] for n in LANDINGS}
    L_slab = max(landing.values()) / (updates['t_slab'] / 12) / (updates['L_bw'] / 12)
    native = {'source_sha256': digest,
              'method': 'Native saved BReps read with OpenCascade (FreeCAD 1.1 Python, scripts/measure_backwall_cad.py), transformed to '
                        'BridgePGL.Frame. No document open, recompute or save. NetVolume properties read from Document.xml.',
              'objects': objects, 'per_bent': per_bent, 'landing_net_volume_ft3': landing, 'L_slab_ft': L_slab}
    return native, updates


def write(native, updates):
    evidence = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    evidence['native_geometry'] = native
    evidence['cad_updates'] = updates
    geometry = evidence['confirmations']['geometry']
    geometry['inputs'] = {k: updates[k] for k in geometry['inputs'] if k in updates}
    landing = evidence['confirmations']['landing']
    landing['inputs']['L_slab'] = native['L_slab_ft']
    landing['inputs']['t_slab'] = updates['t_slab']
    landing['inputs']['L_bw'] = updates['L_bw']
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    native, updates = measure()
    print(json.dumps({'source_sha256': native['source_sha256'], 'cad_updates': updates, 'per_bent': native['per_bent'],
                      'landing_net_volume_ft3': native['landing_net_volume_ft3'], 'L_slab_ft': native['L_slab_ft']}, indent=1))
    if '--write' in sys.argv:
        write(native, updates)
        print('wrote', EVIDENCE)
