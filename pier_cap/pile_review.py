"""Traceable FBMP pile results, elastic screening and lateral trial review.

Forces are retained at both ends of every pile element. Model D/C and reported
material stresses are never replaced by the elastic section approximation.
"""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import re
from lxml import etree as ET

FIELDS = {'axial': ('AXIAL', 'kip'), 'v2': ('SHEAR-2', 'kip'),
          'v3': ('SHEAR-3', 'kip'), 'm2': ('MOMENT-2', 'kip-ft'),
          'm3': ('MOMENT-3', 'kip-ft'), 'torque': ('TORQUE', 'kip-ft')}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(node, path, unit=None, optional=False):
    child = node.find(path)
    if child is None and optional:
        return None
    require(child is not None, f'Missing pile result/property: {path}.')
    require(unit is None or child.get('units') == unit,
            f'{path}: expected units {unit}; found {child.get("units")}.')
    value = float(child.text)
    require(math.isfinite(value), f'{path}: nonfinite value.')
    return value


def unique(nodes, attribute, context):
    result = {}
    for node in nodes:
        key = node.get(attribute)
        require(key and key not in result, f'Duplicate/missing {context} identifier.')
        result[key] = node
    return result


def section_from_xml(segment):
    """Use exported A and I, avoiding precision lost in printed dimensions."""
    dims = segment.find('DIMENSIONS')
    require(dims is not None, 'Missing pile section dimensions.')
    shape = dims.get('type', '')
    width, depth = (number(dims, k, 'in') for k in ('WIDTH', 'DEPTH'))
    require(width > 0 and depth > 0, 'Pile dimensions must be positive.')
    props = segment.find('GROSS_SECTION_PROPS')
    material = segment.find('MATERIAL_PROPS')
    require(props is not None and material is not None, 'Missing pile section properties.')
    area = number(props, 'AREA', 'in^2')
    i2 = number(props, 'INERTIA2', 'in^4')
    i3 = number(props, 'INERTIA3', 'in^4')
    modulus = number(props, 'EMODULUS', 'ksi')
    require(min(area, i2, i3, modulus) > 0, 'Pile A, I and modulus must be positive.')
    fc = number(material, 'FPC', 'ksi', True)
    shell = number(dims, 'SHELL_THICK', 'in', True) or 0
    concrete = fc is not None and fc > 0
    kind = 'concrete' if concrete else 'steel'
    fy = number(material, 'FY_SHELL' if shell > 0 else 'FY_HPILE', 'ksi', True)
    circular = shape == 'Circular'
    issues = []
    if number(dims, 'ORIENTATION') != 0:
        issues.append('Rotated section: supply verified local-axis elastic properties.')
    if dims.get('embed_hpile', 'no').lower() != 'no' or (concrete and shell > 0):
        issues.append('Composite section: homogeneous elastic screening is unavailable.')
    if shape not in ('Circular', 'Rectangular', 'H', 'H-Pile', 'H-pile'):
        issues.append(f'Unreviewed section shape {shape}: supply verified elastic properties.')
    if circular and not math.isclose(width, depth, abs_tol=.021):
        issues.append('Circular width and depth differ.')
    groups = []
    pp = 0.0
    prestress_moments = [0.0, 0.0]
    for g in segment.findall('STEEL_GROUPS/BAR_GROUP'):
        bars = number(g, 'BARS')
        a = number(g, 'BAR_AREA', 'in^2')
        prestress = number(g, 'PRESTRESS', 'ksi')
        c2, c3 = number(g, 'COORD_2', 'in'), number(g, 'COORD_3', 'in')
        layer = number(g, 'LAYER_DIA', 'in', True) or 0
        pp += bars*a*prestress
        orientation = number(g, 'ORIENTATION', optional=True)
        require(bars >= 1 and bars.is_integer(), 'Bar-group count must be a positive integer.')
        # FBMP uses starting coordinates, not the centroid of a rectangular
        # group: bars run uniformly to the opposite corner along axis 2 or 3.
        # See the FBMP manual, Full Cross Section / Custom Allocation Methods.
        points = []
        centroid = None
        if bars == 1 and layer == 0:
            points = [(c2, c3)]
            centroid = (c2, c3)
        elif layer > 0 and bars > 1:
            centroid = (0.0, 0.0)  # Uniform circular layer, centered on section.
        elif layer == 0 and bars > 1 and shape in ('Rectangular', 'Circular') and orientation in (2, 3):
            points = [(c2*(1-2*i/(bars-1)), c3) if orientation == 2 else
                      (c2, c3*(1-2*i/(bars-1))) for i in range(int(bars))]
            centroid = (0.0, c3) if orientation == 2 else (c2, 0.0)
        if prestress:
            if centroid is None:
                issues.append('Unknown prestressing group arrangement: supply verified elastic properties.')
            else:
                for axis in (0, 1):
                    prestress_moments[axis] += bars*a*prestress*centroid[axis]
        groups.append(dict(bars=bars, area=a, prestress=prestress, c2=c2, c3=c3, layer=layer,
                           orientation=orientation, points=points))
    if any(abs(moment) > .001 for moment in prestress_moments):
        issues.append('Eccentric prestress: confirm a concentric approximation or use a separate section analysis.')
    if not concrete and (fy is None or fy <= 0):
        issues.append('Steel Fy is unavailable; stress/Fy cannot be calculated.')
    curve = [(number(p, 'STRESS', 'ksi'), number(p, 'STRAIN'))
             for p in segment.findall('STRESS-STRAIN_CURVES/CONCRETE/POINT')]
    tensile = [(stress, strain) for stress, strain in curve if stress > 0 and strain > 0]
    peak = max((stress for stress, strain in tensile), default=None)
    peak_strain = min((strain for stress, strain in tensile if stress == peak), default=None)
    weight = number(props, 'UNIT_WEIGHT', 'k/in^3', True)
    return dict(kind=kind, shape=shape, width_in=width, depth_in=depth, shell_in=shell,
                area_in2=area, i2_in4=i2, i3_in4=i3, s2_in3=i2/(depth/2),
                s3_in3=i3/(width/2), modulus_ksi=modulus, fy_ksi=fy if not concrete else None,
                fc_ksi=fc, prestress_kip=pp, circular=circular, groups=groups,
                tensile_peak_ksi=peak, tensile_peak_strain=peak_strain,
                modeled_weight_lb_ft=weight*area*12000 if weight is not None else None,
                issues=issues, source='XML exported gross section properties')


def import_pile_xml(source, filename=None):
    if isinstance(source, (bytes, bytearray, memoryview)):
        raw = bytes(source)
        filename = filename or 'FB-MultiPier.xml'
    else:
        path = Path(source)
        require(path.stat().st_size <= 25_000_000, 'XML exceeds 25 MB.')
        raw, filename = path.read_bytes(), filename or path.name
    require(len(raw) <= 25_000_000, 'XML exceeds 25 MB.')
    root = ET.fromstring(raw, ET.XMLParser(resolve_entities=False, no_network=True))
    require(not root.getroottree().docinfo.doctype, 'DTD/entity declarations are not accepted.')
    require(root.tag == 'FB-MULTIPIER_MODEL_DATA', 'Not an FB-MultiPier XML.')
    require((root.findtext('PROJECT_INFO/VERSION_NUMBER') or '').strip() == '6.1.0', 'Pile review currently supports FBMP 6.1.0 XML.')
    require((root.findtext('CONTROL_INFO/UNITS') or '').strip() == 'English', 'Pile review requires English-unit XML.')
    require((root.findtext('CONTROL_INFO/ANALYSIS') or '').strip() == 'Static', 'Pile review requires static results.')
    groups = root.findall('.//PILE_GROUP')
    require(len(groups) == 1, 'Pile review currently supports one pile group per XML.')
    group = groups[0]
    geometries = root.findall('.//PILE_GEOMETRY/SEGMENT')
    require(len(geometries) == 1, 'Pile review currently requires one homogeneous pile section.')
    section = section_from_xml(geometries[0])
    pile_nodes = unique(group.findall('PILE_COORDINATES/PILE'), 'number', 'pile')
    require(len(pile_nodes) == number(group, 'PILES') > 0, 'Pile count disagrees with coordinate records.')
    coords, distances = {}, {}
    for pile, p in pile_nodes.items():
        points = unique(p.findall('POINT'), 'number', 'pile point')
        require(set(points) == {str(i) for i in range(1, len(points)+1)} and len(points) > 1,
                f'Pile {pile}: point sequence is incomplete.')
        xyz = [tuple(number(points[str(i)], a, 'in') for a in ('X', 'Y', 'Z')) for i in range(1, len(points)+1)]
        length = [0.0]
        for a, b in zip(xyz, xyz[1:]):
            step = math.dist(a, b)/12
            require(step > 0, f'Pile {pile}: duplicate coordinate stations.')
            length.append(length[-1]+step)
        coords[pile], distances[pile] = xyz, length
    definitions = unique(root.findall('MODEL_INFO/LOAD_COMBINATION'), 'number', 'combination')
    require(bool(definitions), 'No load combinations in XML.')
    results = root.findall('.//LOAD_CASE_RESULTS/LOAD_CASE')
    require(results, 'No solved pile results. Export XML after analysis.')
    seen, forces, displacements, reported = set(), [], [], []
    for result in results:
        combo, state = result.get('combination'), result.get('limitstate')
        require(combo in definitions and combo not in seen, 'Duplicate or unrecognized combination results.')
        require(state == definitions[combo].get('limitstate'), 'Combination/result limit states disagree.')
        seen.add(combo)
        steps = result.findall('TIME_STEP')
        require(len(steps) == 1, 'Expected one static time step per combination.')
        step = steps[0]
        common = dict(combination=combo, state=state, load_case=result.get('number'))
        disp_piles = unique(step.findall('PILE_DISPLACEMENTS/PILE'), 'number', 'displacement pile')
        force_piles = unique(step.findall('PILE_INTERNAL_FORCES/PILE'), 'number', 'force pile')
        require(set(disp_piles) == set(force_piles) == set(coords), 'Incomplete pile force/displacement coverage.')
        for pile in coords:
            nodes = unique(disp_piles[pile].findall('NODE'), 'number', 'displacement node')
            require(set(nodes) == {str(i) for i in range(1, len(coords[pile])+1)}, f'Pile {pile}: incomplete displacement stations.')
            global_nodes = {}
            for local, node in nodes.items():
                key = node.get('node_number')
                require(key and key not in global_nodes, 'Duplicate/missing global pile node.')
                idx = int(local)-1
                global_nodes[key] = idx
                d = {a.lower(): number(node, a, 'in') for a in ('DX', 'DY', 'DZ')}
                displacements.append(dict(common, pile=pile, node=key, point=int(local),
                    distance_ft=distances[pile][idx], vertical_ft=(coords[pile][idx][2]-coords[pile][0][2])/12,
                    lateral_in=math.hypot(d['dx'], d['dy']), **d))
            elems = unique(force_piles[pile].findall('ELEMENT'), 'number', 'pile element')
            require(set(elems) == {str(i) for i in range(1, len(coords[pile]))}, f'Pile {pile}: incomplete element ends.')
            for local, element in elems.items():
                for side, idx in [('I', int(local)-1), ('J', int(local))]:
                    end = element.find(f'PILE_ELEMENT_{side}_END')
                    require(end is not None, 'Missing pile element end.')
                    node = end.get('node_'+side.lower())
                    require(global_nodes.get(node) == idx, 'Pile force connectivity does not match displacement/coordinate order.')
                    data = {k: number(end, tag, unit) for k, (tag, unit) in FIELDS.items()}
                    dc = number(end, 'FAILURE-RATIO', optional=True)
                    # I-end axial is tension positive; J-end must be reversed.
                    forces.append(dict(common, pile=pile, element=element.get('elem_number') or local,
                        local_element=int(local), side=side, node=node, distance_ft=distances[pile][idx],
                        vertical_ft=(coords[pile][idx][2]-coords[pile][0][2])/12,
                        axial_tension_kip=data['axial']*(1 if side == 'I' else -1),
                        model_dc=dc if dc is not None and dc >= 0 else None, **data))
        pending = None
        for item in step.findall('PILE_STRAINS/MAX_ITEM'):
            name = item.get('item', '')
            if 'strain in ' in name:
                pending = item
            elif name == 'corresponding stress' and pending is not None:
                pile = item.findtext('PILE')
                if pile in coords:  # Pile 0 denotes an absent material, not zero stress.
                    require(pending.findtext('PILE') == pile and pending.findtext('SEGMENT') == item.findtext('SEGMENT'),
                            'Reported strain and corresponding stress refer to different locations.')
                    reported.append(dict(common, pile=pile, description=pending.get('item').replace('strain', 'stress'),
                        strain=number(pending, 'ITEM_VALUE', 'in/in'),
                        stress_ksi=number(item, 'ITEM_VALUE', 'ksi'), segment=item.findtext('SEGMENT')))
                pending = None
    require(seen == set(definitions), 'Some defined combinations have no pile results.')
    summary = []
    for item in root.findall('.//OUTPUT_SUMMARY/PILE_MAX/MAX_ITEM'):
        value = item.find('ITEM_VALUE')
        if value is not None:
            summary.append(dict(item=item.get('item'), value=number(item, 'ITEM_VALUE'), units=value.get('units'),
                                combination=item.findtext('COMBINATION'), load_case=item.findtext('LOAD_CASE'), pile=item.findtext('PILE')))
    return dict(schema_version=1, filename=Path(filename).name, sha256=hashlib.sha256(raw).hexdigest(),
        project=root.findtext('PROJECT_INFO/PROJECT_NAME') or '', version='6.1.0', section=section,
        combinations={k: v.get('limitstate') for k, v in definitions.items()},
        piles={p: dict(length_ft=distances[p][-1], head_xyz_in=coords[p][0], tip_xyz_in=coords[p][-1]) for p in coords},
        forces=forces, displacements=displacements, reported_stresses=reported, reported_summary=summary,
        notes=['Force values are original XML element-end values; axial stress reverses the J-end axial sign.',
               'Distances follow actual pile nodes. Elevation requires a project cutoff datum; XML Z is not labeled as project elevation.',
               'Model D/C is the FBMP interaction result. Elastic stress/Fy is a separate screening ratio.',
               'XML does not establish convergence, OUT cracking warnings, or the minimum-tip trial sequence.'])


def elastic_profile(review, section=None):
    s = section or review['section']
    if s.get('issues'):
        return []
    require(s['kind'] in ('steel', 'concrete'), 'Choose steel or concrete for elastic screening.')
    for key in ('area_in2', 's2_in3', 's3_in3'):
        require(math.isfinite(s[key]) and s[key] > 0, f'{key} must be positive.')
    pp = s.get('prestress_kip', 0)
    require(math.isfinite(pp) and pp >= 0, 'Prestress force must be nonnegative.')
    rows = []
    for r in review['forces']:
        bending2, bending3 = 12*r['m2']/s['s2_in3'], 12*r['m3']/s['s3_in3']
        bending = math.hypot(bending2, bending3) if s['circular'] else abs(bending2)+abs(bending3)
        axial = (r['axial_tension_kip']-(pp if s['kind'] == 'concrete' else 0))/s['area_in2']
        low, high = axial-bending, axial+bending
        fy = s.get('fy_ksi')
        rows.append(dict(r, stress_min_ksi=low, stress_max_ksi=high,
            elastic_yield_ratio=max(abs(low), abs(high))/fy if s['kind'] == 'steel' and fy and fy > 0 else None,
            resultant_moment_kip_ft=math.hypot(r['m2'], r['m3']), resultant_shear_kip=math.hypot(r['v2'], r['v3'])))
    return rows


def pile_heads(review):
    return [dict(r, compression_kip=max(0, -r['axial_tension_kip']), uplift_kip=max(0, r['axial_tension_kip']),
                 compression_ton=max(0, -r['axial_tension_kip'])/2)
            for r in review['forces'] if r['local_element'] == 1 and r['side'] == 'I']


def governors(review):
    """Return actual source rows, retaining concurrent components and ties."""
    heads = pile_heads(review)
    result = []
    for state in dict.fromkeys(review['combinations'].values()):
        for label, rows, key, transform in [
            ('Head compression (kip)', heads, 'compression_kip', lambda v: v),
            ('Head uplift (kip)', heads, 'uplift_kip', lambda v: v),
            ('Any-depth compression (kip)', review['forces'], 'axial_tension_kip', lambda v: max(0, -v)),
            ('Model D/C', review['forces'], 'model_dc', lambda v: v),
            ('Lateral X (in)', review['displacements'], 'dx', abs),
            ('Lateral Y (in)', review['displacements'], 'dy', abs),
            ('Lateral resultant (in)', review['displacements'], 'lateral_in', lambda v: v)]:
            candidates = [r for r in rows if r['state'] == state and r[key] is not None]
            if not candidates:
                result.append(dict(state=state, metric=label, value=None, records=[]))
                continue
            peak = max(transform(r[key]) for r in candidates)
            result.append(dict(state=state, metric=label, value=peak,
                               records=[r for r in candidates if math.isclose(transform(r[key]), peak, abs_tol=1e-9)]))
    return result


def parse_trials(text):
    """Header CSV/TSV or the workbook's five pasted columns; no row caps."""
    lines = [line for line in text.strip('\r\n ').splitlines() if line.strip()]
    require(lines, 'Paste trial rows first.')
    delimiter = '\t' if '\t' in lines[0] else ','
    rows = list(csv.reader(lines, delimiter=delimiter))
    aliases = {'trial': 'trial', 'trialnumber': 'trial', 'loadcomb': 'combination', 'loadcombination': 'combination',
               'combination': 'combination', 'pile': 'pile', 'pilenumber': 'pile',
               'embedmentft': 'embedment_ft', 'displacementin': 'displacement_in'}
    header = [aliases.get(re.sub(r'[^a-z0-9]', '', c.lower()), c.strip().lower()) for c in rows[0]]
    has_header = 'embedment_ft' in header
    if has_header:
        require(len(set(header)) == len(header), 'Trial table contains duplicate column headers.')
        require({'trial', 'combination', 'pile', 'embedment_ft', 'displacement_in'} <= set(header),
                'Required headers: trial, combination, pile, embedment_ft, displacement_in.')
        data = [dict(zip(header, r)) for r in rows[1:]]
        require(all(len(r) == len(header) for r in rows[1:]), 'Trial CSV has an incomplete/extra field.')
    else:
        require(all(len(r) == 5 for r in rows), 'Paste five columns: trial, combination, pile, embedment_ft, displacement_in; or use the CSV template.')
        data = [dict(zip(['trial', 'combination', 'pile', 'embedment_ft', 'displacement_in'], r)) for r in rows]
    result = []
    for row_index, row in enumerate(data, 2 if has_header else 1):
        for key in ('trial', 'combination', 'pile'):
            require(bool(row.get(key, '').strip()), f'Missing trial {key}.')
        parsed = {k: row[k].strip() for k in ('trial', 'combination', 'pile')}
        parsed.update(series=row.get('series', 'Envelope').strip() or 'Envelope')
        for key in ('embedment_ft', 'displacement_in', 'dc', 'dx_in', 'dy_in', 'iterations', 'tolerance_kip'):
            value = row.get(key, '').strip()
            try:
                parsed[key] = float(value) if value else None
            except ValueError:
                raise ValueError(f'Row {row_index}: {key} must be a number; found {value!r}. Paste the five trial columns, with or without their headers.') from None
            require(parsed[key] is None or math.isfinite(parsed[key]), f'Trial {key} must be finite.')
        require(parsed['embedment_ft'] is not None and parsed['embedment_ft'] > 0 and parsed['displacement_in'] is not None,
                'Each trial needs positive embedment and a displacement.')
        require(parsed['displacement_in'] >= 0, 'displacement_in is a maximum magnitude and must be nonnegative; use dx_in/dy_in for signed components.')
        for key in ('dc', 'iterations', 'tolerance_kip'):
            require(parsed[key] is None or parsed[key] >= 0, f'Trial {key} cannot be negative.')
        converged = row.get('converged', '').strip().lower()
        require(converged in ('', 'yes', 'no', 'true', 'false', '1', '0'), 'converged must be yes/no or blank.')
        parsed['converged'] = None if not converged else converged in ('yes', 'true', '1')
        result.append(parsed)
    require(result, 'No trial data rows.')
    return result


def evaluate_trials(rows, tolerance=.1, extension=5, fraction=.2, mode='fixed', reference_elevation=None,
                    cutoff_elevation=None, accepted_embedment=None, round_feet=False):
    """Match Min Tip Paste: min embedment whose next shallower Δ <= limit.

    The default required embedment is Lcrit + 5 ft. Legacy percentage methods
    remain explicit options. A ground/scour datum is needed only for elevation.
    accepted_embedment is retained only for callers of the older Python API;
    notebook controls always use the automatic calculation.
    """
    for value, label in [(tolerance, 'Displacement tolerance'), (extension, 'Extension'), (fraction, 'Fraction')]:
        require(math.isfinite(value) and value >= 0, f'{label} must be nonnegative.')
    require(mode in ('fixed', 'fraction', 'lesser'), 'Choose fixed, percentage, or the lesser extension.')
    for value in (reference_elevation, cutoff_elevation):
        require(value is None or math.isfinite(value), 'Elevations must be finite.')
    require(bool(rows), 'Paste trial rows first.')
    grouped = defaultdict(list)
    for r in rows:
        grouped[r['series']].append(r)
    details, groups = [], []
    for name, data in grouped.items():
        ordered = sorted(data, key=lambda r: -r['embedment_ft'])
        require(len({r['embedment_ft'] for r in ordered}) == len(ordered),
                f'{name}: duplicate embedments. Separate independent studies with the series column.')
        stable = True
        candidate = None
        for i, original in enumerate(ordered):
            r = dict(original)
            shallower = ordered[i+1] if i+1 < len(ordered) else None
            delta = abs(abs(r['displacement_in'])-abs(shallower['displacement_in'])) if shallower else None
            valid = r['converged'] is not False and (shallower is None or shallower['converged'] is not False)
            valid = valid and (r['dc'] is None or r['dc'] <= 1) and (shallower is None or shallower['dc'] is None or shallower['dc'] <= 1)
            # The spreadsheet selects by displacement change alone. Supplied
            # D/C and convergence remain separate review results, not a hidden
            # change to its L-critical equation.
            passes = delta is not None and (delta <= tolerance or math.isclose(delta, tolerance, rel_tol=0, abs_tol=1e-12))
            stable = stable and passes
            if passes:
                candidate = r['embedment_ft']
            r.update(delta_in=delta, passes=passes, stable_from_deepest=stable,
                     analysis_ok=valid, next_embedment_ft=shallower['embedment_ft'] if shallower else None,
                     next_displacement_in=shallower['displacement_in'] if shallower else None,
                     interval_ft=r['embedment_ft']-shallower['embedment_ft'] if shallower else None)
            details.append(r)
        groups.append(dict(series=name, candidate_ft=candidate, points=len(ordered),
                           governing=next((r for r in ordered if r['embedment_ft'] == candidate), None)))
    proposed = max(g['candidate_ft'] for g in groups) if groups and all(g['candidate_ft'] is not None for g in groups) else None
    if accepted_embedment is not None:
        require(math.isfinite(accepted_embedment) and accepted_embedment > 0, 'Accepted critical embedment must be positive.')
    critical = proposed if accepted_embedment is None else accepted_embedment
    added = None if critical is None else (extension if mode == 'fixed' else
            fraction*critical if mode == 'fraction' else min(extension, fraction*critical))
    required = None if critical is None else critical+added
    tip = None if required is None or reference_elevation is None else reference_elevation-required
    length = None if tip is None or cutoff_elevation is None else cutoff_elevation-tip
    if length is not None:
        require(length > 0, 'Cutoff elevation must be above the required tip.')
    if round_feet:
        tip = math.floor(tip) if tip is not None else None
        # Compute the whole-foot length to the adopted rounded tip, so the two
        # displayed quantities remain compatible with a fractional cutoff datum.
        length = math.ceil(cutoff_elevation-tip) if length is not None else None
    for r in details:
        r['critical_trial'] = r['embedment_ft'] == critical
    return dict(rows=details, groups=groups, proposed_embedment_ft=proposed, accepted_embedment_ft=critical,
                critical_embedment_ft=critical, selection_mode='automatic' if accepted_embedment is None else 'legacy override',
                extension_mode=mode, tolerance_in=tolerance,
                extension_ft=added, required_embedment_ft=required, tip_elevation_ft=tip, total_length_ft=length,
                basis=f'Shallowest trial with absolute displacement change to the next shallower trial <= {tolerance:g} in; '
                      'maximum critical embedment across separate series.')


def csv_text(rows):
    if not rows:
        return ''
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()})
    return output.getvalue()


def validate_saved_review(review):
    """Validate the portable review before replacing an active UI source."""
    require(isinstance(review, dict) and review.get('schema_version') == 1, 'Unsupported pile result schema.')
    require(isinstance(review.get('filename'), str) and isinstance(review.get('sha256'), str) and len(review['sha256']) == 64,
            'Missing pile file provenance.')
    require(isinstance(review.get('combinations'), dict) and bool(review['combinations']), 'Missing combinations.')
    require(all(isinstance(k, str) and isinstance(v, str) and v for k,v in review['combinations'].items()), 'Invalid combination labels.')
    require(isinstance(review.get('piles'), dict) and bool(review['piles']), 'Missing pile geometry.')
    for key in ('reported_stresses', 'reported_summary', 'notes'):
        require(isinstance(review.get(key), list), f'Missing {key}.')
    for collection, fields in [('forces', ['distance_ft','vertical_ft','axial_tension_kip',*FIELDS]),
                               ('displacements', ['distance_ft','vertical_ft','dx','dy','dz','lateral_in'])]:
        require(isinstance(review.get(collection), list) and bool(review[collection]), f'Missing {collection}.')
        for row in review[collection]:
            require(isinstance(row, dict) and row.get('combination') in review['combinations'] and row.get('pile') in review['piles'],
                    f'{collection}: unknown pile or combination.')
            require(row.get('state') == review['combinations'][row['combination']], 'Result limit state mismatch.')
            for key in fields:
                v=row.get(key)
                require(type(v) in (int,float) and math.isfinite(v), f'{collection}: invalid {key}.')
            require(isinstance(row.get('node'),str), 'Missing result node.')
            if collection == 'forces':
                require(row.get('side') in ('I','J') and isinstance(row.get('local_element'),int), 'Invalid element end.')
                dc=row.get('model_dc')
                require(dc is None or (type(dc) in (int,float) and math.isfinite(dc) and dc>=0), 'Invalid model D/C.')
    section=review.get('section')
    require(isinstance(section,dict) and section.get('kind') in ('steel','concrete') and isinstance(section.get('issues'),list), 'Invalid pile section.')
    for key in ('area_in2','i2_in4','i3_in4','s2_in3','s3_in3','width_in','depth_in','modulus_ksi'):
        value=section.get(key)
        require(type(value) in (int,float) and math.isfinite(value) and value>0, f'Invalid section {key}.')
    for key in ('tensile_peak_ksi', 'tensile_peak_strain'):
        value = section.get(key)
        require(value is None or (type(value) in (int, float) and math.isfinite(value) and value > 0), f'Invalid section {key}.')
    for row in review['reported_stresses']:
        require(row.get('combination') in review['combinations'] and row.get('pile') in review['piles'],
                'Reported stress has an unknown pile or combination.')
        for key in ('stress_ksi', 'strain'):
            value = row.get(key)
            require((key == 'strain' and value is None) or
                    (type(value) in (int, float) and math.isfinite(value)), f'Invalid reported {key}.')
    return review
