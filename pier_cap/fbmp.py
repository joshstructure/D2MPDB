"""Reviewed FB-MultiPier 6.1 static pile-bent XML -> portable cap case.

See FBMP_IMPORT.md for supported geometry, I/J signs and station recovery.
This reader deliberately rejects unverified formats instead of guessing axes.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import math
from lxml import etree as ET
from .model import upgrade_case, default_case, evaluate, validate_case, GEOMETRY


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(node, path):
    value = node.findtext(path)
    _require(value is not None, f'Missing XML field: {path}.')
    return value.strip()


def _number(node, path, unit=None):
    child = node.find(path)
    _require(child is not None, f'Missing XML value: {path}.')
    if unit is not None:
        _require(child.get('units') == unit, f'{path}: expected {unit}, found {child.get("units")}.')
    value = float(child.text)
    _require(math.isfinite(value), f'{path}: nonfinite value.')
    return value


def _integer(node, path):
    value = _number(node, path)
    _require(value == int(value) and value > 0, f'{path}: expected positive integer.')
    return int(value)


def _xyz(node):
    return tuple(_number(node, axis, 'in') for axis in ('X', 'Y', 'Z'))


def _close(a, b, tolerance=.021):
    return abs(a-b) <= tolerance


def _section(segment):
    dims = segment.find('DIMENSIONS')
    _require(dims is not None and dims.get('type') == 'Rectangular', 'Cap must be rectangular.')
    _require(_number(dims, 'ORIENTATION') == 0 and _text(dims, 'VOID_TYPE') == 'None',
             'Rotated or hollow cap sections are not supported.')
    return dict(b=_number(dims, 'WIDTH', 'in'), h=_number(dims, 'DEPTH', 'in'),
                fc=_number(segment, 'MATERIAL_PROPS/FPC', 'ksi'),
                fy=_number(segment, 'MATERIAL_PROPS/FY_MILD', 'ksi'),
                Es=_number(segment, 'MATERIAL_PROPS/E_STEEL', 'ksi'))


def _moment_at(mi, mj, vi, vj, length_ft, t):
    # Quadratic uniform-load diagram anchored to both printed end moments.
    # vi/vj are dM/dx = -raw I shear / +raw J shear.
    return mi + (mj-mi)*t + .5*(vi-vj)*length_ft*t*(1-t)


def _moment_envelope(records, prefix):
    governing = {}
    for suffix, subset, sign in [('N',records,-1),('P',[r for r in records if r['pile_station']],1),('B',records,1)]:
        _require(bool(subset), f'Missing {prefix}_{suffix} stations.')
        winner = max(subset,key=lambda r:sign*r['moment'])
        # Recovered interior values are rounded outward to 0.01 kip-ft.
        value = math.ceil(max(0,sign*winner['moment'])*100-1e-7)/100
        governing[prefix+'_'+suffix] = dict(winner, adopted=value)
    return governing


def _strength_envelope(records, ends):
    governing = _moment_envelope(records, 'Mu')
    for key,field in [('Vu_G','shear'),('Tu','torque')]:
        winner = max(ends,key=lambda r:abs(r[field]))
        governing[key] = dict(winner, adopted=abs(winner[field]))
    return governing


def import_fbmp_xml(source, base=None, filename=None):
    """Return a proposed case without changing base or writing any files.

    Input is a path or uploaded bytes. All units are checked, not inferred from
    magnitude. The UI previews this case and requires an explicit Apply click.
    """
    if isinstance(source, (bytes, bytearray, memoryview)):
        raw = bytes(source)
        filename = filename or 'FB-MultiPier.xml'
    else:
        path = Path(source)
        _require(path.stat().st_size <= 25_000_000, 'XML exceeds the 25 MB import limit.')
        raw = path.read_bytes()
        filename = filename or path.name
    _require(len(raw) <= 25_000_000, 'XML exceeds the 25 MB import limit.')
    parser = ET.XMLParser(resolve_entities=False, no_network=True, remove_comments=True)
    root = ET.fromstring(raw, parser)
    _require(not root.getroottree().docinfo.doctype, 'DTD/entity declarations are not accepted.')
    _require(root.tag == 'FB-MULTIPIER_MODEL_DATA', 'Not an FB-MultiPier model/results XML.')
    version = _text(root, 'PROJECT_INFO/VERSION_NUMBER')
    _require(version == '6.1.0', f'FB-MultiPier {version}: only the reviewed 6.1.0 layout is supported.')
    _require(_text(root, 'CONTROL_INFO/UNITS') == 'English', 'This importer requires English-unit XML.')
    _require(_text(root, 'CONTROL_INFO/ANALYSIS') == 'Static', 'Only static results are supported.')
    _require(_integer(root, 'CONTROL_INFO/PIERS') == 1, 'Import currently supports one substructure per file.')
    _require(_text(root, 'CONTROL_INFO/DESIGN_CODE') == 'AASHTO-LRFD', 'Expected AASHTO-LRFD combinations.')
    subs = root.findall('MODEL_INFO/SUBSTRUCTURE')
    _require(len({s.get('number') for s in subs}) == 1, 'Substructure identifiers are inconsistent.')
    geometries = root.findall('.//PIER_GEOMETRY')
    _require(len(geometries) == 1, 'Expected one pier geometry block.')
    geometry = geometries[0]
    model = geometry.find('MODELING')
    _require(model is not None and _text(model, 'STRUCTURE_TYPE') == 'PILE BENT', 'Expected a PILE BENT model.')
    for tag in ('COLUMN_TAPER', 'CANTILEVER_TAPER', 'BEAM_TAPER'):
        _require(_text(model, tag).lower() == 'no', 'Tapered geometry is not supported.')
    for block in root.findall('.//LOAD_VALUES'):
        _require(all(n.tag == 'NODAL_LOAD' for n in block),
                 'Non-nodal load records require a separately verified member-load importer.')
    sections = geometry.findall('CROSS-SECTIONS/SEGMENT')
    _require(len(sections) >= 2, 'Missing bent cantilever/center section properties.')
    section = _section(sections[0])
    _require(section == _section(sections[1]), 'Cantilever and center sections/materials must match.')

    results = root.findall('.//LOAD_CASE_RESULTS/LOAD_CASE')
    _require(bool(results), 'No solved load-combination results. Export XML after analysis.')
    combinations = {}
    for combo in root.findall('MODEL_INFO/LOAD_COMBINATION'):
        key = combo.get('number')
        _require(key and key not in combinations, 'Duplicate/missing load-combination identifier.')
        combinations[key] = combo.get('limitstate', '').strip()
    _require(bool(combinations), 'No load-combination definitions.')
    seen = set()
    for result in results:
        key = result.get('combination')
        _require(key in combinations and key not in seen, 'Missing, duplicate or unrecognized combination results.')
        _require(result.get('limitstate', '').strip() == combinations[key], 'Combination/result limit states disagree.')
        _require(len(result.findall('TIME_STEP')) == 1, 'Expected one static time step per combination.')
        seen.add(key)
    _require(seen == set(combinations), 'Some defined load combinations have no results. Re-export a complete analysis.')
    states = set(combinations.values())
    _require(any(s.startswith('STRENGTH-') for s in states) and 'SERVICE-I' in states,
             'Both strength and SERVICE-I combination results are required.')

    pile_groups = root.findall('.//PILE_GROUP')
    _require(len(pile_groups) == 1, 'Expected one pile group.')
    group = pile_groups[0]
    piles = group.findall('PILE_COORDINATES/PILE')
    count = _integer(group, 'PILES')
    _require(len(piles) == count == _integer(model, 'NUM_COLUMNS') and count >= 2,
             'Pile count and bent column count disagree.')
    head_coordinates = {}
    for pile in piles:
        key = pile.get('number')
        point = pile.find("POINT[@number='1']")
        _require(key and key not in head_coordinates and point is not None, 'Ambiguous pile-head coordinates.')
        head_coordinates[key] = _xyz(point)
    nodes = {}
    for node in geometry.findall('NODAL_COORDINATES/NODE'):
        if node.get('location') == 'Pier':
            key = node.get('node_number')
            _require(key and key not in nodes, 'Duplicate cap node identifier.')
            nodes[key] = _xyz(node.find('COORDINATES'))
    head_nodes = {}
    for result in results:
        mapping = {}
        for pile in result.findall('TIME_STEP/PILE_DISPLACEMENTS/PILE'):
            head = pile.find("NODE[@number='1']")
            _require(head is not None, 'Missing pile-head result node.')
            mapping[pile.get('number')] = head.get('node_number')
        _require(set(mapping) == set(head_coordinates) and len(set(mapping.values())) == count,
                 'Pile-head results cannot be mapped to geometry.')
        _require(not head_nodes or mapping == head_nodes, 'Pile-head mapping changes between combinations.')
        head_nodes = mapping
    for key, node in head_nodes.items():
        xyz = head_coordinates[key]
        _require(node not in nodes or all(_close(a,b) for a,b in zip(nodes[node],xyz)), 'Conflicting pile-head/cap coordinates.')
        nodes[node] = xyz
    centers = sorted(xyz[0] for xyz in head_coordinates.values())
    reference = next(iter(head_coordinates.values()))
    _require(all(_close(xyz[1],reference[1]) and _close(xyz[2],reference[2]) for xyz in nodes.values()),
             'Cap must be straight, horizontal and parallel to global X, in a single pile row.')
    gaps = [b-a for a,b in zip(centers, centers[1:])]
    _require(min(gaps) > 0 and max(gaps)-min(gaps) < .021, 'Unequal pile spacing is not supported by this calculator.')
    pile_sections = root.findall('.//PILE_GEOMETRY/SEGMENT')
    _require(len(pile_sections) == 1, 'Multiple pile sections/sets require a reviewed geometry mapping.')
    pd = pile_sections[0].find('DIMENSIONS')
    _require(pd is not None and pd.get('type') in ('Circular','Rectangular'), 'Unsupported pile shape.')
    diameter = _number(pd, 'WIDTH', 'in')
    _require(diameter > 0 and _close(diameter,_number(pd,'DEPTH','in')) and _number(pd,'ORIENTATION') == 0,
             'Only round or unrotated square piles are supported.')
    cantilever = _number(model, 'CANTILEVER_LENGTH', 'ft')*12
    nc = _integer(model, 'NUM_ELEMENTS_PER_CANTILEVER')
    ns = _integer(model, 'NUM_ELEMENTS_PER_SPAN')
    cap_count = 2*nc+(count-1)*ns
    ordered = sorted(nodes, key=lambda key:nodes[key][0])
    _require(len(ordered) == cap_count+1, 'Cap node count does not match the bent mesh definition.')
    xs = [nodes[key][0] for key in ordered]
    _require(all(b-a > .001 for a,b in zip(xs,xs[1:])), 'Duplicate/reversed cap stations.')
    _require(_close(centers[0]-xs[0],cantilever) and _close(xs[-1]-centers[-1],cantilever),
             'Cap ends disagree with the specified symmetric cantilever length.')
    _require(all(_close(xs[nc+i*ns],x) for i,x in enumerate(centers)), 'Pile stations disagree with bent mesh ordering.')
    bearings = {n.get('node_number') for n in model.findall('BEARING_LOCATIONS/BEARING_LOCATION')}
    _require(bearings and bearings.issubset(nodes), 'Bearing nodes are missing from the cap mesh.')

    case = upgrade_case(base or default_case())
    validate_case(case)
    p = case['inputs']
    tolerance = evaluate(case).value('Tol_pile')
    nominal_extension = cantilever-diameter/2
    extra = nominal_extension-p['E_clear']-tolerance
    _require(extra >= -1e-8, 'Analyzed cap end is shorter than the current actual-clearance plus pile-tolerance allowance. Review end detailing before import.')
    p.update(section)
    p.update(N_pile=count, S_pile=sum(gaps)/len(gaps)/12, D_pile=diameter, E_detail=max(0,extra))
    # S_pile is feet in the portable case; all XML coordinates above are inches.
    end_records = []
    records = []
    excluded_counts = []
    pile_stations = [x+offset for x in centers for offset in (-diameter/2,0,diameter/2)]
    max_equilibrium_error = 0.
    for result in results:
        state = result.get('limitstate').strip()
        common = dict(load_case=result.get('number'), combination=result.get('combination'), state=state)
        elements = result.findall('TIME_STEP/STRUCTURE_INTERNAL_FORCES/PIER_CAP/ELEMENT')
        _require(len(elements) >= cap_count, 'Incomplete cap force table.')
        excluded_counts.append(len(elements)-cap_count)
        for i, element in enumerate(elements[:cap_count]):
            ei = element.find('STRUCTURE_ELEMENT_I_END')
            ej = element.find('STRUCTURE_ELEMENT_J_END')
            _require(ei is not None and ej is not None, 'Missing member-end force record.')
            _require(element.get('number') == str(i+1) and ei.get('node_i') == ordered[i] and ej.get('node_j') == ordered[i+1],
                     'Cap member connectivity/order differs from the reviewed bent mesh. Import stopped.')
            xi,xj = xs[i:i+2]
            length = (xj-xi)/12
            ends = []
            for side,end,node,x,sign in [('I',ei,ordered[i],xi,1),('J',ej,ordered[i+1],xj,-1)]:
                raw_m = _number(end,'MOMENT-3','kip-ft')
                raw_v = _number(end,'SHEAR-2','kip')
                record = dict(common, element=element.get('elem_number'), side=side, node=node, x_in=x,
                              moment=sign*raw_m, shear=-sign*raw_v, torque=_number(end,'TORQUE','kip-ft'),
                              raw_moment_3=raw_m, raw_shear_2=raw_v,
                              axial=_number(end,'AXIAL','kip'), weak_moment=_number(end,'MOMENT-2','kip-ft'),
                              lateral_shear=_number(end,'SHEAR-3','kip'),
                              station='member end', pile_station=any(_close(x,s) for s in pile_stations))
                end_records.append(record)
                records.append(record)
                ends.append(record)
            mi,mj = [r['moment'] for r in ends]
            vi,vj = [r['shear'] for r in ends]
            error = abs(mj-mi-(vi+vj)*length/2)
            # Printed coordinates/forces are rounded to .01 in / kip / kip-ft.
            bound = .02+.01*length+max(abs(vi),abs(vj))*.02/12
            _require(error <= bound, f'LC {common["load_case"]}, member {i+1}: end forces fail uniform-load equilibrium; station recovery is unsupported.')
            max_equilibrium_error = max(max_equilibrium_error,error)
            stations = [(x,'pile face / centerline',True) for x in pile_stations if xi+.021 < x < xj-.021]
            curvature = (vi-vj)*length
            if abs(curvature) > 1e-10:
                t = .5+(mj-mi)/curvature
                if 0 < t < 1:
                    stations.append((xi+t*(xj-xi),'interior moment extremum',False))
            for x,label,is_pile in stations:
                t = (x-xi)/(xj-xi)
                records.append(dict(common, element=element.get('elem_number'), side='interior', x_in=x,
                                    moment=_moment_at(mi,mj,vi,vj,length,t), station=label, pile_station=is_pile))

    # Independent check of cap selection, force axes and I/J signs against the
    # separate FB summary. Check signed moments/shears, magnitude-only torque.
    summaries = root.findall('.//OUTPUT_SUMMARY/STRUCTURE_PIER_CAP_MAX')
    _require(len(summaries) == 1, 'Missing independent cap maximum/minimum summary.')
    summary = {n.get('item'):n for n in summaries[0].findall('MAX_ITEM')}
    comparisons = {}
    for label,field,kind,unit in [('max moment about 3 axis','moment','max','kip-ft'),
                                  ('min moment about 3 axis','moment','min','kip-ft'),
                                  ('max shear in 2 direction','shear','max','kip'),
                                  ('min shear in 2 direction','shear','min','kip')]:
        _require(label in summary, f'Missing summary: {label}.')
        actual = (max if kind == 'max' else min)(r[field] for r in end_records)
        expected = _number(summary[label],'ITEM_VALUE',unit)
        _require(_close(actual,expected,.025), f'{label}: member forces disagree with the FB summary ({actual:g} vs {expected:g}).')
        comparisons[label] = dict(extracted=actual,summary=expected)
    _require('max torque' in summary and 'min torque' in summary, 'Missing torque summary.')
    torque = max(abs(r['torque']) for r in end_records)
    expected = max(abs(_number(summary[label],'ITEM_VALUE','kip-ft')) for label in ('max torque','min torque'))
    _require(_close(torque,expected,.025), 'Member torque disagrees with the FB summary.')
    comparisons['absolute torque'] = dict(extracted=torque,summary=expected)

    strength_records = [r for r in records if r['state'].startswith('STRENGTH-')]
    strength_ends = [r for r in end_records if r['state'].startswith('STRENGTH-')]
    governing = _strength_envelope(strength_records, strength_ends)
    governing.update(_moment_envelope([r for r in records if r['state'] == 'SERVICE-I'], 'MI'))
    for key,row in governing.items():
        p[key] = row['adopted']
    # Retain each limit state's envelope, including non-governing states. Use
    # the same recovered stations as the combined design envelope.
    strength_envelopes = {
        state: dict(combinations=[k for k,v in combinations.items() if v == state],
                    governing=_strength_envelope([r for r in strength_records if r['state'] == state],
                                                 [r for r in strength_ends if r['state'] == state]))
        for state in dict.fromkeys(r['state'] for r in strength_records)
    }
    p['Vu_L'] = p['Vu_G']
    governing['Vu_L'] = dict(governing['Vu_G'], basis='Global shear used until a low-shear zone is explicitly established.')
    for key in ('Ready_III','Ready_fatigue'):
        p[key] = False
    for key in p:
        if key.startswith(('MIII_','MDL_','DMLL_')):
            p[key] = 0
    digest = hashlib.sha256(raw).hexdigest()
    notes = [
        'Strength and Service I are independent envelopes, not concurrent force vectors.',
        'Pile-positive moments include both sides of pile centers and recovered pile faces. Bearing/span-positive inputs use the full-cap positive envelope, including interior extrema.',
        'Low-interval shear is set to global shear; no low-shear zone is inferred.',
        'Trial reinforcement, covers and design factors are retained. Service III and fatigue are reset to pending (STRENGTH-III is not SERVICE-III).',
        'End geometry is the analyzed nominal extension. Existing actual-clearance and 3 in tolerance allowances are retained; the remainder is extra end allowance.',
        'Axial force, weak-axis bending and lateral shear remain outside the existing sectional calculation; their maxima are recorded in the audit. Analysis convergence, anchorage and full design review remain separate.',
    ]
    case['name'] = Path(filename).stem+' — XML analysis'
    case['analysis'] = dict(id=f'{Path(filename).name} · SHA256 {digest[:12]}',
                            geometry={k:p[k] for k in GEOMETRY}, notes=' '.join(notes),
                            xml_audit=dict(filename=Path(filename).name,sha256=digest,version=version,
                                project=_text(root,'PROJECT_INFO/PROJECT_NAME'), combinations=combinations,
                                cap_element_count=cap_count,excluded_elements_per_case=excluded_counts,
                                cap_length_ft=(xs[-1]-xs[0])/12,nominal_end_extension_in=nominal_extension,
                                cantilever_centerline_in=cantilever,pile_centers_in=centers,
                                bearing_stations_in=sorted({nodes[n][0] for n in bearings}),
                                maximum_equilibrium_residual_kip_ft=max_equilibrium_error,
                                summary_checks=comparisons,governing=governing,
                                strength_envelopes=strength_envelopes,notes=notes,
                                outside_calc_maxima={field:max(abs(r[field]) for r in end_records) for field in ('axial','weak_moment','lateral_shear')},
                                end_records=end_records))
    case.pop('section_study',None)
    validate_case(case)
    evaluated = evaluate(case)
    _require(_close(evaluated.value('L_cap'),xs[-1]-xs[0]), 'Imported cap length does not match analyzed geometry.')
    return case
