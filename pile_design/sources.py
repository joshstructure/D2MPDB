"""Read FB-MultiPier exports and cap cases into pile-design inputs, with provenance receipts.

The FBMP XML is parsed by pier_cap.pile_review.import_pile_xml (one parser for the project). The
upload is compared with every registered export by SHA-256; a differing file is still readable, but
its receipt says so and nothing silently replaces the record. The demand records extracted from the
XML are stored in the case (analysis.records) so a saved case recalculates without the file.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from . import loads
from .model import SOURCES, STANDARD_PLANS, edit_input, select_psc, reconcile_confirmations

ROOT = Path(__file__).resolve().parent.parent
XML_IDS = ('EB-XML', 'EB2-XML', 'PIER-XML', 'EB-MINTIP-XML', 'PIER-MINTIP-XML')
_REVIEW_CACHE = {}


def registered_path(source_id):
    return ROOT / SOURCES['sources'][source_id]['path']


def _receipt(source_id, filename, content, registered_id, notes=()):
    digest = hashlib.sha256(content).hexdigest()
    registered = SOURCES['sources'][registered_id]['sha256'] if registered_id else None
    return dict(source_id=registered_id or source_id, registered_id=registered_id, filename=filename, sha256=digest,
                registered=registered, matches_register=registered == digest, notes=list(notes),
                loaded_utc=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'))


def _spacing_ft(piles):
    xy = [(p['head_xyz_in'][0], p['head_xyz_in'][1]) for p in piles.values()]
    gaps = [math.dist(a, b) / 12.0 for i, a in enumerate(xy) for b in xy[i + 1:]]
    return min(gaps) if gaps else None


def _expected_prestress(case):
    plan = STANDARD_PLANS['indexes'].get(case.get('psc', {}).get('index'))
    if not plan:
        return None
    option = next((o for o in plan['options'] if o['id'] == case['psc'].get('pattern')), None)
    if not option:
        return None
    loss = case['inputs'].get('loss_frac', 0.2)
    return option, option['count'] * option['jacking_kip'] * (1.0 - loss)


def read_fbmp_xml(content, filename='End Bent 1_Fixed.XML', case=None):
    """Return (input updates, source texts, receipt); the receipt carries the demand analysis."""
    from pier_cap.pile_review import import_pile_xml, require
    content = bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    if (digest, filename) not in _REVIEW_CACHE:         # parsed exports are read-only; reuse them
        _REVIEW_CACHE[(digest, filename)] = import_pile_xml(content, filename)
    review = _REVIEW_CACHE[(digest, filename)]
    registered_id = next((k for k, v in SOURCES['sources'].items() if k in XML_IDS and v['sha256'] == digest), None)
    inputs = (case or {}).get('inputs', {})
    DD_kip = 2.0 * float(inputs.get('DD_tons') or 0.0)
    g_str, g_ser = float(inputs.get('gamma_DR_str', 1.10)), float(inputs.get('gamma_DR_ser', 1.00))
    records = loads.demands_from_xml(review, DD_kip, g_str, g_ser)
    section, piles = review['section'], review['piles']
    require(piles, 'The export has no piles.')
    heads = {round(-p['head_xyz_in'][2] / 12.0, 6) for p in piles.values()}
    notes = []
    cutoff = min(heads)
    if len(heads) > 1:
        notes.append('Pile heads are at different elevations; the lowest cutoff is used.')
    tops = review.get('soil_top_elevations_ft') or {}
    ground = next(iter(tops.values()), None)
    if len(set(round(v, 6) for v in tops.values())) > 1:
        notes.append('Soil sets have different top elevations; the first set is used. Edit EL_ground if needed.')
    updates = {'N_pile': len(piles)}
    spacing = _spacing_ft(piles)
    if spacing:
        updates['S_pile'] = round(spacing, 6)
    updates['EL_cutoff'] = round(cutoff, 6)
    if ground is not None:
        updates['EL_ground'] = round(ground, 6)
        updates['L_unsupported'] = round(cutoff - ground, 6)
        updates['L_v'] = updates['L_unsupported']
    kind = section['kind']
    family = 'psc' if kind == 'concrete' else 'pipe'
    label = f'{registered_id or "FBMP-XML upload"} {filename}'
    evidence = {}
    if kind == 'concrete':
        updates['D_pile'] = section['width_in']
        updates['fc'] = section['fc_ksi']
        groups = section['groups']
        strands = int(sum(g['bars'] for g in groups))
        expected = _expected_prestress(case or {})
        text = (f'FBMP section: {section["width_in"]:g} in square, f\'c {section["fc_ksi"]:g} ksi, {strands} strands x '
                f'{groups[0]["area"]:g} in2 at {groups[0]["prestress"]:g} ksi = {section["prestress_kip"]:.1f} kip prestress.')
        if expected:
            option, force = expected
            text += (f' Standard Plans option {option["label"]}: {option["count"]} strands, '
                     f'{force:.1f} kip after {inputs.get("loss_frac", 0.2):.0%} losses.')
            if abs(force - section['prestress_kip']) > 0.01 * section['prestress_kip']:
                notes.append('FBMP prestress differs from the selected Standard Plans option by more than 1%.')
        notes.append(text)
    else:
        updates['D_pile'] = updates['D_out'] = section['width_in']
        updates['t_wall'] = section['shell_in']
        notes.append(f'FBMP pipe: {section["width_in"]:g} in diameter, shell {section["shell_in"]:g} in, A {section["area_in2"]:g} in2, '
                     f'I {section["i3_in4"]:g} in4, Fy {section["fy_ksi"]:g} ksi in the model.')
        design_fy = float(inputs.get('Fy', 45.0))
        if section.get('fy_ksi') and abs(section['fy_ksi'] - design_fy) > 1e-9:
            notes.append(f'FBMP model Fy = {section["fy_ksi"]:g} ksi; the design Fy input ({design_fy:g} ksi, '
                         'Spec 962 Table 962-11 A252 Gr 3) is not overwritten. Reconcile (confirmation steel_grade).')
        elif section.get('fy_ksi') and registered_id:
            # The registered export models the pile with the design yield strength: the Fy half of the
            # steel_grade prerequisite is source-backed. reconcile_confirmations withdraws it if Fy is edited.
            evidence = {'steel_grade': {
                'note': (f'FBMP pile material Fy {section["fy_ksi"]:g} ksi equals the design Fy {design_fy:g} ksi (Spec 962 Table 962-11, ASTM A252 '
                         f'Grade 3) in the registered export {registered_id} {filename} (SHA-256 {digest[:12]}). The grade itself remains the design input.'),
                'inputs': {'Fy': design_fy}, 'source': f'{registered_id} {filename}', 'stale': False}}
    if not registered_id:
        notes.append('Not a registered export - new upload. Record it in the source register before relying on the results.')
    elif registered_id.endswith('MINTIP-XML'):
        notes.append('Minimum-tip variant of the analysis; the fixed-run export is the design basis.')
    sources = {k: f'{label}: ' + {'N_pile': 'PILE_GROUP piles', 'S_pile': 'pile head coordinates', 'EL_cutoff': 'minus pile-head Z / 12',
                                  'EL_ground': 'top of soil layer 1', 'L_unsupported': 'cutoff - ground', 'L_v': 'cutoff - ground (default shear span)',
                                  'D_pile': 'section WIDTH', 'fc': 'FPC', 'D_out': 'section WIDTH', 't_wall': 'SHELL_THICK'}[k] for k in updates}
    if evidence:
        # The design Fy is not overwritten, but its source now names the export whose pile material carries the same value.
        sources['Fy'] = f'Spec 962 Table 962-11, ASTM A252 Gr 3; {label} pile material FY_SHELL {section["fy_ksi"]:g} ksi equals this value'
    dc_value, dc_record = loads.model_dc_max(records)
    analysis = dict(filename=review['filename'], sha256=digest, registered_id=registered_id, matches_register=registered_id is not None,
                    project=review['project'], family=family, combinations=review['combinations'],
                    combination_factors=review['combination_factors'], piles=len(piles),
                    section={k: section[k] for k in ('kind', 'shape', 'width_in', 'depth_in', 'shell_in', 'area_in2', 'i2_in4', 'i3_in4',
                                                     'modulus_ksi', 'fy_ksi', 'fc_ksi', 'prestress_kip')},
                    soil_top_elevations_ft=tops, cutoff_ft=cutoff, model_dc_max=dc_value, records=records)
    receipt = _receipt('FBMP-XML', filename, content, registered_id, notes)
    receipt['analysis'] = analysis
    if evidence:
        receipt['confirmation_evidence'] = evidence
    return updates, sources, receipt


def read_cap_case(content, filename='selected_case.json', case=None):
    data = json.loads(bytes(content).decode('utf-8-sig'))
    if 'inputs' not in data or 'analysis' not in data:
        raise ValueError('This is not a cap case JSON. Choose project_current/cap_design/<support>/selected_case.json.')
    p = data['inputs']
    updates = {'N_pile': int(p['N_pile']), 'S_pile': float(p['S_pile']), 'D_pile': float(p['D_pile']), 'embed_cap': float(p['Pile_embed'])}
    registered = next((k for k, v in SOURCES['sources'].items() if k.endswith('-CASE') and v['sha256'] == hashlib.sha256(bytes(content)).hexdigest()), None)
    sid = registered or 'EB-CASE'
    label = f'{sid} {filename}'
    sources = {name: f'{label} inputs.{key}' for name, key in (('N_pile', 'N_pile'), ('S_pile', 'S_pile'), ('D_pile', 'D_pile'), ('embed_cap', 'Pile_embed'))}
    notes = [f'Cap case {data.get("name", "")}'.strip()]
    audit = data['analysis'].get('xml_audit', {})
    if audit.get('sha256'):
        notes.append(f'The cap case used FBMP analysis {audit["sha256"][:8]}.')
    receipt = _receipt('CAP-CASE', filename, bytes(content), registered, notes)
    if case and case.get('analysis') and audit.get('sha256') and audit['sha256'] != case['analysis'].get('sha256'):
        receipt['notes'].append('The cap case analysis differs from the loaded FBMP export: confirm analysis_current.')
    return updates, sources, receipt


READERS = {sid: read_fbmp_xml for sid in XML_IDS}
READERS.update({'FBMP-XML': read_fbmp_xml, 'EB-CASE': read_cap_case, 'EB2-CASE': read_cap_case, 'PIER-CASE': read_cap_case})


def apply_source(case, source_id, content, filename):
    """Apply an upload to the case; returns (updates, receipt)."""
    updates, sources, receipt = READERS[source_id](content, filename, case)
    analysis = receipt.pop('analysis', None)
    if analysis:
        case['family'] = analysis['family']
        if analysis['family'] == 'psc':
            plan = STANDARD_PLANS['indexes'].get(case['psc']['index'])
            if not plan or abs(plan['size_in'] - updates['D_pile']) > 1e-6:
                index = next((k for k, v in STANDARD_PLANS['indexes'].items() if abs(v['size_in'] - updates['D_pile']) < 1e-6), None)
                if index is None:
                    raise ValueError(f'No FDOT Standard Plans square pile of {updates["D_pile"]:g} in is tabulated (14, 18, 24, 30 in).')
                select_psc(case, index)
                receipt['notes'].append(f'Standard Plans Index {index} selected to match the {updates["D_pile"]:g} in pile.')
        case['analysis'] = analysis
    for name, value in updates.items():
        edit_input(case, name, value)
    for key, record in receipt.pop('confirmation_evidence', {}).items():
        # Source-backed confirmation: the evidence names the registered export and the inputs it rests on.
        case.setdefault('confirmation_evidence', {})[key] = dict(record)
        case['confirmations'][key] = True
    status = 'project source' if receipt['matches_register'] else 'differs from register'
    for name, text in sources.items():
        case['sources'][name] = {'source': text, 'status': status}
    case.setdefault('receipts', {})[receipt['source_id']] = dict(receipt, applied=sorted(updates))
    reconcile_confirmations(case)
    return updates, receipt
