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
        pass  # Analysis envelope includes cheeks; physical cap length belongs to CAD.
    stations = audit.get('bearing_stations_in') or []
    if len(stations) >= 2:
        updates['s_brg'] = round(float(stations[-1]) - float(stations[0]), 3)
        updates['N_brg'] = len(stations)
        sources['s_brg'] = sources['N_brg'] = label + ' analysis.xml_audit.bearing_stations_in'
    notes = [f'Cap case {data.get("name", "")}'.strip(), 'Analysis length is the combined cap/cheek envelope; physical cap geometry is supplied by CAD.']
    if audit.get('sha256') != SOURCES['sources']['EB-XML']['sha256']:
        notes.append('Selected case analysis does not match available EB-XML; bearing-load currency remains pending.')
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
        pass  # Historical analysis cap extent must not overwrite adopted CAD geometry.
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
    """Use native measurements bound to the exact reviewed complex solid bytes.

    BRep text vertices are not a bounding box: placements, Boolean fragments and
    spline extrema made the former parser silently produce impossible sizes.
    """
    from .model import PROJECT_EVIDENCE
    digest = hashlib.sha256(bytes(content)).hexdigest()
    evidence = PROJECT_EVIDENCE['native_geometry']
    if digest != evidence['source_sha256']:
        raise ValueError('This CAD revision has no reviewed native measurement snapshot. Measure the saved solids in the BridgePGL frame and review the dimensions before importing; no inputs changed.')
    updates = dict(PROJECT_EVIDENCE['cad_updates'])
    sources = {key: f'CAD-MODEL {filename}; native saved-solid measurements, D-053/D-055 (notebook build e9b41b8eaf)' for key in updates}
    notes = ['235 in core cap and backwall; 251 in overall cap/cheek envelope.',
             'Two planar 2% backwall tops 4.25 in below the deck-top line (D-053). Maximum heights and minimum backwall edge/weight '
             'envelope both ends. Cheek weight includes rear/bottom lugs.',
             'Geometry adoption is separate from pending connection and fabrication acceptance.']
    return updates, sources, _receipt('CAD-MODEL', filename, bytes(content), notes)


READERS = {'EB-CASE': read_end_bent_case, 'EB-XML': read_fbmp_xml, 'CAD-MODEL': read_freecad}


def apply_source(case, source_id, content, filename):
    updates, sources, receipt = READERS[source_id](content, filename)
    from .model import edit_input
    for name, value in updates.items():
        edit_input(case, name, value)
    for name, text in sources.items():
        case['sources'][name] = {'source': text, 'status': 'project source' if receipt['matches_register'] else 'differs from register'}
    case.setdefault('receipts', {})[source_id] = dict(receipt, applied=sorted(updates))
    from .model import reconcile_confirmations
    reconcile_confirmations(case)
    return updates, receipt
