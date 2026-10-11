"""Cap-only signed axial provenance. Pile axial conventions are independent."""
import math

CONVENTION = 'fbmp-6.1.0-cap-global-X-Iminus-Jplus-v1'
SCHEMA = 1
NUMERICAL_ZERO_KIP = 1e-10
PRINTED_EQUILIBRIUM_KIP = .010000001
PRINTED_SUMMARY_KIP = .010000001


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def upgrade_axial(case):
    """Never guess the meaning of an unversioned legacy field named axial.

    Such cases remain readable, with their original records intact; reimporting
    the matching XML against this case preserves its geometry/detailing inputs.
    Explicit raw-end provenance can be migrated exactly once.
    """
    audit = case.get('analysis', {}).get('xml_audit', {})
    if not audit.get('end_records'):
        return
    convention = audit.get('axial_convention')
    if convention == CONVENTION and audit.get('axial_schema_version') == SCHEMA:
        return
    if convention == 'fbmp-6.1.0-raw-end' and audit.get('orientation') == 'straight-horizontal-increasing-global-X':
        rows = audit['end_records']
        if audit.get('version') == '6.1.0' and audit.get('sha256') and all(
                r.get('side') in ('I', 'J') and finite(r.get('axial')) for r in rows):
            for r in rows:
                r['raw_axial'] = r['axial']
                r['axial'] = (-1 if r['side'] == 'I' else 1) * r['raw_axial']
                r['axial_convention'] = CONVENTION
            audit.update(axial_convention=CONVENTION, axial_schema_version=SCHEMA)
            audit['axial_status'] = 'migrated; independent signed summary validation required'
            return
    audit['axial_status'] = 'unresolved: legacy axial meaning/orientation not established; reimport the solved XML'


def validate_axial(audit):
    if audit.get('version')!='6.1.0' or len(audit.get('sha256',''))!=64:
        return 'Unsupported saved FBMP version or missing source identity; reimport the solved XML'
    if audit.get('axial_schema_version') != SCHEMA or audit.get('axial_convention') != CONVENTION:
        return audit.get('axial_status', 'Unresolved signed cap axial data; reimport the solved XML')
    if audit.get('orientation') != 'straight-horizontal-increasing-global-X':
        return 'Unsupported saved cap orientation; reimport the solved XML'
    pairs = {}
    for r in audit.get('end_records', []):
        if r.get('side') not in ('I', 'J') or not all(finite(r.get(k)) for k in ('axial', 'raw_axial')):
            return 'Missing signed/raw axial member end; reimport the solved XML'
        expected = (-1 if r['side'] == 'I' else 1) * r['raw_axial']
        if abs(r['axial'] - expected) > NUMERICAL_ZERO_KIP:
            return 'Saved axial sign/provenance mismatch; reimport the solved XML'
        key = (r.get('combination'), r.get('element'))
        pair = pairs.setdefault(key, {})
        if r['side'] in pair:
            return 'Duplicate axial member end; reimport the solved XML'
        pair[r['side']] = r
    for pair in pairs.values():
        if set(pair) != {'I', 'J'} or abs(pair['I']['raw_axial'] + pair['J']['raw_axial']) > PRINTED_EQUILIBRIUM_KIP:
            return 'Axial end-force equilibrium unresolved; reimport the solved XML'
    rows = audit.get('end_records', [])
    for label, fn in [('max axial force', max), ('min axial force', min)]:
        check = audit.get('summary_checks', {}).get(label, {})
        if not rows or not finite(check.get('summary')) or abs(fn(r['axial'] for r in rows)-check['summary']) > PRINTED_SUMMARY_KIP:
            return 'Independent signed axial summary unresolved; reimport the solved XML'
    return ''
