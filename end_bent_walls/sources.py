"""Read registered project sources into backwall inputs, with provenance receipts.

Uploads are compared with the source register fingerprints. A differing file is
still readable, but its receipt says so; nothing silently replaces the record.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from .model import SOURCES

MM_PER_FT = 304.8


def _receipt(source_id, filename, content, notes=()):
    digest = hashlib.sha256(content).hexdigest()
    registered = SOURCES['sources'][source_id]['sha256']
    return dict(source_id=source_id, filename=filename, sha256=digest, registered=registered,
                matches_register=digest == registered, notes=list(notes),
                loaded_utc=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'))


def read_end_bent_case(content, filename='selected_case.json'):
    data = json.loads(bytes(content).decode('utf-8-sig'))
    if 'inputs' not in data or 'analysis' not in data:
        raise ValueError('This is not a cap case JSON. Choose project_current/cap_design/end_bents/selected_case.json.')
    p, audit = data['inputs'], data['analysis'].get('xml_audit', {})
    updates = {'b_cap': float(p['b']), 'h_cap': float(p['h']), 'embed_pile': float(p['Pile_embed']),
               'fc': float(p['fc']), 'fy': float(p['fy']), 'Es': float(p['Es']),
               'N_pile': int(p['N_pile']), 'S_pile': float(p['S_pile']), 'D_pile': float(p['D_pile'])}
    label = f'EB-CASE {filename}'
    sources = {name: f'{label} inputs.{key}' for name, key in (
        ('b_cap', 'b'), ('h_cap', 'h'), ('embed_pile', 'Pile_embed'), ('fc', 'fc'), ('fy', 'fy'), ('Es', 'Es'),
        ('N_pile', 'N_pile'), ('S_pile', 'S_pile'), ('D_pile', 'D_pile'))}
    if audit.get('cap_length_ft'):
        updates['L_cap'] = round(float(audit['cap_length_ft']) * 12, 3)
        sources['L_cap'] = label + ' analysis.xml_audit.cap_length_ft'
    stations = audit.get('bearing_stations_in') or []
    if len(stations) >= 2:
        updates['s_brg'] = round(float(stations[-1]) - float(stations[0]), 3)
        updates['N_brg'] = len(stations)
        sources['s_brg'] = sources['N_brg'] = label + ' analysis.xml_audit.bearing_stations_in'
    notes = [f'Cap case {data.get("name", "")}'.strip()]
    if data.get('cap_type') != 'End-bent pile cap':
        notes.append(f'Cap type is "{data.get("cap_type")}", not an end-bent cap.')
    return updates, sources, _receipt('EB-CASE', filename, bytes(content), notes)


def read_fbmp_xml(content, filename='End Bent 1_Fixed.XML'):
    root = ET.fromstring(bytes(content))
    locations, coords = {}, {}
    for node in root.iter('NODE'):
        c = node.find('COORDINATES')
        if c is not None and node.get('node_number'):
            locations[node.get('node_number')] = node.get('location', '')
            coords[node.get('node_number')] = {k.tag: float(k.text) for k in c}
    bearings = [n for n, loc in locations.items() if loc.startswith('Bearing')]
    pier = [n for n, loc in locations.items() if loc == 'Pier']
    if len(bearings) < 1:
        raise ValueError('No bearing nodes were found. Choose the End Bent FB-MultiPier XML export.')
    loads = {}
    for load in root.iter('NODAL_LOAD'):
        values = {child.tag: float(child.text) for child in load}
        loads.setdefault(load.get('AASHTO_load_type'), []).append((load.get('node_number'), values))

    def at_bearings(kind, key):
        return [v.get(key, 0.0) for n, v in loads.get(kind, []) if n in bearings]
    dc, pl = at_bearings('DC', 'FZ'), at_bearings('PL', 'FZ')
    if not dc:
        raise ValueError('No DC bearing loads were found in the XML.')
    n = len(bearings)
    updates = {'N_brg': n, 'P_DC': round(sum(dc) / n, 3), 'P_PL': round(sum(pl) / n, 3) if pl else 0.0}
    for case in ('WS1', 'WS2', 'WS3'):
        fy, fz = at_bearings(case, 'FY'), at_bearings(case, 'FZ')
        updates['FY_' + case] = round(max((abs(v) for v in fy), default=0.0), 3)
        updates['FZ_' + case] = round(sum(fz), 3)
    xs = sorted(coords[b]['X'] for b in bearings)
    if len(xs) >= 2:
        updates['s_brg'] = round(xs[-1] - xs[0], 3)
    if pier:
        pier_x = [coords[p]['X'] for p in pier]
        updates['L_cap'] = round(max(pier_x) - min(pier_x), 3)
    label = f'EB-XML {filename}'
    sources = {key: label + ' bearing nodal loads' for key in updates}
    if 'L_cap' in updates:
        sources['L_cap'] = label + ' cap node extents'
    notes = []
    for node, values in loads.get('DC', []):
        if node not in bearings and abs(values.get('FZ', 0.0)) > 0 and locations.get(node) != 'Pier':
            notes.append(f'DC load {values["FZ"]:g} kip is applied at node {node}, which is not a cap node '
                         '(likely a pile head). Confirm the intended cap-end location.')
    return updates, sources, _receipt('EB-XML', filename, bytes(content), notes)


def _brep_points(text):
    return [tuple(float(v) for v in m.groups()) for m in
            re.finditer(r'\nVe\n\s*[-0-9.eE+]+\n\s*([-0-9.eE+]+) ([-0-9.eE+]+) ([-0-9.eE+]+)', text)]


def read_freecad(content, filename='bridge.FCStd'):
    archive = zipfile.ZipFile(io.BytesIO(bytes(content)))
    names = set(archive.namelist())
    if 'Document.xml' not in names:
        raise ValueError('This is not a FreeCAD FCStd file.')
    doc = archive.read('Document.xml').decode('utf-8', 'replace')

    def points(obj):
        name = obj + '.Shape.brp'
        if name not in names:
            raise ValueError(f'The model does not contain {obj}. Choose the registered bridge model.')
        return [(x / MM_PER_FT, y / MM_PER_FT, z / MM_PER_FT) for x, y, z in _brep_points(archive.read(name).decode('latin-1'))]
    heights, edges, lengths = [], [], []
    for eb in ('EB1', 'EB2'):
        cap = points('BridgeCap' + eb)
        wall = points('BridgeBackwall' + eb)
        cap_top = max(z for _, _, z in cap)
        crown = max(z for _, _, z in wall)
        ys = [y for _, y, _ in wall]
        edge = max(z for _, y, z in wall if abs(abs(y) - max(abs(v) for v in ys)) < 1e-6)
        heights.append(crown - cap_top)
        edges.append(edge - cap_top)
        lengths.append((max(ys) - min(ys)) * 12)
    cheek = points('BridgeCheekEB11')
    cap = points('BridgeCapEB1')
    updates = {
        'H_bw': round(max(heights), 4), 'H_bw_edge': round(min(edges), 4), 'L_bw': round(max(lengths), 3),
        'H_ck': round(max(z for *_, z in cheek) - max(z for *_, z in cap), 4),
        't_ck': round((max(y for _, y, _ in cheek) - min(y for _, y, _ in cheek)) * 12, 3),
        'w_ck': round((max(x for x, _, _ in cheek) - min(x for x, _, _ in cheek)) * 12, 3),
        'L_cap': round((max(y for _, y, _ in cap) - min(y for _, y, _ in cap)) * 12, 3),
        'h_cap': round((max(z for *_, z in cap) - min(z for *_, z in cap)) * 12, 3),
    }
    match = re.search(r'<Object name="MSEInputs"[^>]*>.*?<Property name="SlabThickness"[^>]*>\s*<Float value="([-0-9.eE+]+)"', doc, re.S)
    if match:
        updates['t_slab'] = round(float(match.group(1)) / 25.4, 3)
    label = f'CAD-MODEL {filename}'
    sources = {key: label + ' BRep extents' for key in updates}
    sources['H_bw'] = label + ' max backwall crown height, EB1/EB2 (D-019)'
    if 't_slab' in updates:
        sources['t_slab'] = label + ' MSEInputs.SlabThickness'
    notes = [f'Backwall crown heights EB1 / EB2: {heights[0]:.4f} / {heights[1]:.4f} ft; design uses the larger.',
             'Wall geometry remains provisional under D-005.']
    return updates, sources, _receipt('CAD-MODEL', filename, bytes(content), notes)


READERS = {'EB-CASE': read_end_bent_case, 'EB-XML': read_fbmp_xml, 'CAD-MODEL': read_freecad}


def apply_source(case, source_id, content, filename):
    updates, sources, receipt = READERS[source_id](content, filename)
    case['inputs'].update(updates)
    for name, text in sources.items():
        case['sources'][name] = {'source': text, 'status': 'project source' if receipt['matches_register'] else 'differs from register'}
    case.setdefault('receipts', {})[source_id] = dict(receipt, applied=sorted(updates))
    return updates, receipt
