"""Audited STEP export; never edits or saves source documents."""
import hashlib
import json
import re
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import FreeCAD as App
import Import
import Part
from .geometry import length, result

ROOT = Path(__file__).resolve().parent.parent
BBOX_KEYS = ('XMin', 'YMin', 'ZMin', 'XMax', 'YMax', 'ZMax')
MM_PER_UNIT = {'mm': 1.0, 'ft': 304.8, 'us-ft': 1200000.0 / 3937.0}


def state(doc):
    return {o.Name: {
        'type': o.TypeId, 'label': o.Label,
        'expressions': list(getattr(o, 'ExpressionEngine', [])),
        'dependencies': [v.Name for v in o.OutList],
        'placement': str(getattr(o, 'Placement', None)),
        'visible': getattr(o.ViewObject, 'Visibility', None),
        'brep': hashlib.sha256(o.Shape.exportBrepToString().encode()).hexdigest()
            if 'Shape' in o.PropertiesList else None,
    } for o in doc.Objects}


def box(s):
    # Round solids may retain coarse display triangulations. BoundBox can use
    # that mesh and understate the analytic diameter; measure native geometry.
    b = s.optimalBoundingBox(False, False)
    return [getattr(b, k) for k in BBOX_KEYS]


def top_grades(shape):
    faces = [f for f in shape.Faces if abs(f.normalAt(0, 0).z) > .5]
    if not faces:
        raise ValueError('No walking face found')
    face = max(faces, key=lambda f: f.CenterOfMass.z)
    normal = face.normalAt(0, 0)
    return [-normal.x / normal.z * 100, -normal.y / normal.z * 100]


def survey_foot_units(path):
    """Declare the exact survey-foot conversion for already converted coordinates."""
    content = path.read_text(encoding='utf-8')
    records = dict(re.findall(r'#(\d+)\s*=\s*(.*?);', content, re.S))
    units_found = re.findall(r"CONVERSION_BASED_UNIT\(\s*'FOOT'\s*,\s*#(\d+)\s*\)", content)
    if not units_found:raise ValueError('Expected FOOT unit records')
    for key in set(units_found):
        body = re.sub(r'\s+', '', records[key])
        match = re.fullmatch(r'LENGTH_MEASURE_WITH_UNIT\(304\.8,#(\d+)\)', body)
        if not match or 'SI_UNIT(.MILLI.,.METRE.)' not in re.sub(r'\s+', '', records[match.group(1)]):
            raise ValueError('Unexpected FOOT conversion record')
        replacement = '#%s = LENGTH_MEASURE_WITH_UNIT(%.17g,#%s);' % (key, MM_PER_UNIT['us-ft'], match.group(1))
        content, count = re.subn(r'#' + key + r'\s*=\s*.*?;', lambda m: replacement, content, count=1, flags=re.S)
        if count != 1:raise ValueError('Unit record replacement failed')
    content = re.sub(r"CONVERSION_BASED_UNIT\(\s*'FOOT'", "CONVERSION_BASED_UNIT('US_SURVEY_FOOT'", content)
    path.write_text(content, encoding='utf-8', newline='\n')


def write_native_units(objects, path, output_units):
    """Isolated native OCCT conversion avoids downscaling small BRep features.

    Uses pythonocc shipped with the verified FreeCAD installation; no install
    or dependency resolution. Source shapes enter as millimeter BRep snapshots.
    Preserves component Names; colors are recorded in the manifest. Only the exact length-unit record
    is changed for US survey feet; geometry coordinates are never text-edited.
    """
    import subprocess
    runtime=Path(App.getHomePath())/'bin/python.exe'
    if not runtime.is_file():raise ValueError('Verified bundled FreeCAD Python is missing')
    stage=path.parent/'source-brep';stage.mkdir(exist_ok=True)
    rows=[]
    for obj in objects:
        filename=stage/(obj.Name+'.brep')
        filename.write_text(obj.Shape.exportBrepToString(),encoding='ascii')
        rows.append({'name':obj.Name,'path':str(filename),'color':list(obj.ViewObject.ShapeColor[:3])})
    manifest=stage/(path.stem+'-writer.json')
    manifest.write_text(json.dumps({'objects':rows,'path':str(path),'units':output_units}),encoding='utf-8')
    completed=subprocess.run([str(runtime),str(ROOT/'tools/native_step_writer.py'),str(manifest)],cwd=str(ROOT),capture_output=True,text=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    (stage/(path.stem+'-writer.log')).write_text(completed.stdout+'\n'+completed.stderr,encoding='utf-8')
    if completed.returncode!=0:raise ValueError('Isolated STEP writer failed; inspect retained writer.log')
    if output_units=='us-ft':survey_foot_units(path)


def write_step(objects, path, output_units):
    """Export detached snapshots so the STEP writer cannot alter source BReps.

    The installed Import writer uses OCCT runtime units, not updated preferences.
    It is therefore necessary to set the runtime explicitly and restore it.
    """
    units = Part.exportUnits()
    # OCCT 7.8 in this installation changes the unit tag without converting
    # coordinates. The feet adapter compensates on isolated export snapshots.
    # Roundtrip comparison against original physical BReps guards this behavior.
    mm_per_unit = MM_PER_UNIT[output_units]
    prior = App.ActiveDocument.Name if App.ActiveDocument else None
    staging = None
    try:
        staging = App.newDocument('CAD_AI_STEP_' + uuid.uuid4().hex[:10])
        staged = []
        for source in objects:
            obj = staging.addObject('Part::Feature', source.Name)
            obj.Label = source.Name
            shape = Part.Shape()
            shape.importBrepFromString(source.Shape.exportBrepToString())
            if mm_per_unit != 1.0:
                shape.scale(1.0 / mm_per_unit, App.Vector(0, 0, 0))
            obj.Shape = shape
            obj.ViewObject.ShapeColor = source.ViewObject.ShapeColor
            staged.append(obj)
        staging.recompute()
        Part.setStaticValue('write.step.unit', 'MM' if output_units == 'mm' else 'FT')
        Import.export(staged, str(path), exportHidden=False, legacy=False, keepPlacement=True)
        if output_units == 'us-ft':
            # OCCT offers FT, but no US survey foot preset. Define the conversion
            # explicitly in the STEP unit records, whose coordinates were already
            # converted above. No geometry/entity coordinates are text-edited.
            content = path.read_text(encoding='utf-8')
            records = dict(re.findall(r'#(\d+)\s*=\s*(.*?);', content, re.S))
            units_found = re.findall(r"CONVERSION_BASED_UNIT\(\s*'FOOT'\s*,\s*#(\d+)\s*\)", content)
            if not units_found:
                raise ValueError('Expected FOOT unit records for survey-foot conversion')
            for key in set(units_found):
                body = re.sub(r'\s+', '', records[key])
                match = re.fullmatch(r'LENGTH_MEASURE_WITH_UNIT\(304\.8,#(\d+)\)', body)
                if not match or 'SI_UNIT(.MILLI.,.METRE.)' not in re.sub(r'\s+', '', records[match.group(1)]):
                    raise ValueError('Unexpected FOOT conversion record')
                replacement = '#%s = LENGTH_MEASURE_WITH_UNIT(%.17g,#%s);' % (key, mm_per_unit, match.group(1))
                content, count = re.subn(r'#' + key + r'\s*=\s*.*?;', lambda m: replacement, content, count=1, flags=re.S)
                if count != 1:
                    raise ValueError('Unit record replacement failed')
            content = re.sub(r"CONVERSION_BASED_UNIT\(\s*'FOOT'", "CONVERSION_BASED_UNIT('US_SURVEY_FOOT'", content)
            path.write_text(content, encoding='utf-8', newline='\n')
    finally:
        for key, value in units.items():
            Part.setStaticValue(key, value)
        if staging:
            App.closeDocument(staging.Name)
        if prior:
            App.setActiveDocument(prior)


def check_file(objects, path, tol, output_units):
    text = path.read_text(encoding='utf-8')
    records = {k: re.sub(r'\s+', '', v) for k, v in re.findall(r'#(\d+)\s*=\s*(.*?);', text, re.S)}
    factors = []
    unit_names = []
    for body in records.values():
        match = re.search(r'GLOBAL_UNIT_ASSIGNED_CONTEXT\(\((.*?)\)\)', body, re.S)
        if not match:
            continue
        for key in re.findall(r'#(\d+)', match.group(1)):
            unit = records[key]
            if 'LENGTH_UNIT()' not in unit:
                continue
            conversion = re.search(r"CONVERSION_BASED_UNIT\('([^']+)',#(\d+)\)", unit)
            if conversion:
                measure = re.search(r'LENGTH_MEASURE_WITH_UNIT\(([^,]+),#(\d+)\)', records[conversion.group(2)])
                if not measure or 'SI_UNIT(.MILLI.,.METRE.)' not in records[measure.group(2)]:
                    raise ValueError('Unsupported STEP unit definition')
                factors.append(float(measure.group(1)))
                unit_names.append(conversion.group(1))
            elif 'SI_UNIT(.MILLI.,.METRE.)' in unit:
                factors.append(1.0)
                unit_names.append('MILLIMETER')
            else:
                raise ValueError('Unsupported STEP length unit')
    expected_factor = MM_PER_UNIT[output_units]
    unit_ok = bool(factors) and all(abs(v - expected_factor) < 1e-10 for v in factors)
    checks = [result('STEP_length_units_' + output_units, unit_ok,
                     declared_names=sorted(set(unit_names)), mm_per_unit=sorted(set(factors)))]
    checks.append(result('STEP_schema_AP214', 'AUTOMOTIVE_DESIGN' in text))
    restored = Part.read(str(path))
    source = [(o.Name, i, s) for o in objects for i, s in enumerate(o.Shape.Solids)]
    imported = restored.Solids
    checks.append(result('STEP_solid_count', len(source) == len(imported),
                         expected=len(source), actual=len(imported)))
    checks.append(result('STEP_all_solids_valid', all(s.isValid() for s in imported)))
    if len(source) != len(imported):
        raise ValueError('STEP solid count differs: %s versus %s' % (len(imported), len(source)))
    remaining = set(range(len(imported)))
    # Measure each analytic BRep once; repeated mass integrations inside the
    # matching loop are unnecessary and expensive for cambered spline solids.
    imported_metrics={j:(box(s),s.Volume,s.CenterOfMass) for j,s in enumerate(imported)}
    matched = {}
    rows = []
    for name, index, shape in source:
        source_bounds=box(shape);source_volume=shape.Volume;source_center=shape.CenterOfMass
        candidates = []
        for j in remaining:
            other = imported[j]
            other_bounds,other_volume,other_center=imported_metrics[j]
            error = max(abs(a - b) for a, b in zip(source_bounds, other_bounds))
            volume_error = abs(other_volume - source_volume) / source_volume
            if error <= tol and volume_error <= 1e-8 and source_center.distanceToPoint(other_center) <= tol:
                candidates.append((j, error, volume_error))
        if len(candidates) != 1:
            raise ValueError('Cannot uniquely match exported solid %s[%s]: %s candidates; mm_units=%s; source_bounds=%s; imported_bounds=%s' %
                             (name, index, len(candidates), unit_ok, box(shape), [box(imported[j]) for j in remaining]))
        j, error, volume_error = candidates[0]
        remaining.remove(j)
        other = imported[j]
        aa = [v.Point for v in shape.Vertexes]
        bb = [v.Point for v in other.Vertexes]
        vertex_error = max(max(min(p.distanceToPoint(q) for q in bb) for p in aa),
                           max(min(p.distanceToPoint(q) for q in aa) for p in bb))
        area_error = abs(shape.Area - other.Area) / shape.Area
        ok = vertex_error <= tol and area_error <= 1e-8
        checks.append(result(name + '_solid_' + str(index), ok,
                             bounds_error_mm=error, vertex_error_mm=vertex_error,
                             relative_volume_error=volume_error, relative_area_error=area_error))
        matched.setdefault(name, []).append(other)
        rows.append({'object': name, 'solid_index': index, 'STEP_solid_index': j,
                     'bounds_mm': box(other), 'volume_mm3': other.Volume})
    return checks, matched, rows


def export(job):
    from .api import atomic, compact, check_gui, document, resolve
    rid = job['request_id']
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}', rid):
        raise ValueError('Invalid request ID')
    report = ROOT / 'reports/transactions' / (rid + '.json')
    if report.exists():
        old = json.loads(report.read_text())
        if old['request'] != job:
            raise ValueError('Request ID reused for different job')
        if old['status'] == 'PREPARED':
            raise RuntimeError('Prior outcome unknown; inspect files and source before retrying')
        return compact(old)
    doc = document(job['document'])
    check_gui(doc)
    tol = length(job['tolerance'], positive=True)
    if job['units'] not in MM_PER_UNIT:
        raise ValueError('This exporter supports mm, ft and us-ft')
    dest = (ROOT / job['output_directory']).resolve()
    if not dest.is_relative_to(ROOT) or dest == ROOT or dest.exists():
        raise ValueError('Use a new output directory inside CAD_AI')
    packages = []
    for item in job['files']:
        if not re.fullmatch('[A-Za-z0-9_-]+\.stp', item['filename']):
            raise ValueError('Expected a simple .stp filename')
        objects = [resolve(doc, name) for name in item['targets']]
        if not objects or len(set(o.Name for o in objects)) != len(objects):
            raise ValueError('Targets must be nonempty and unique')
        if any(o.Shape.isNull() or not o.Shape.copy().isValid() or not o.Shape.Solids for o in objects):
            raise ValueError('Export requires valid source solids')
        if any('Touched' in o.State or 'Error' in o.State for o in objects):
            raise ValueError('Recompute or resolve source errors before export')
        packages.append((item, objects))
    before = state(doc)
    rec = {'timestamp': datetime.now(timezone.utc).isoformat(), 'operation': job['operation'],
           'request': job, 'transaction_id': rid, 'document': doc.Name, 'status': 'PREPARED',
           'report_path': str(report), 'model_saved': False, 'checks': [], 'errors': [], 'files': []}
    atomic(report, rec)
    try:
        dest.mkdir(parents=True)
        for item, objects in packages:
            path = dest / item['filename']
            if job.get('writer')=='native_units':write_native_units(objects,path,job['units'])
            else:write_step(objects, path, job['units'])
            checks, matched, rows = check_file(objects, path, tol, job['units'])
            rec['checks'].extend(checks)
            for name, expected in item.get('slopes', {}).items():
                actual = top_grades(Part.makeCompound(matched[name]))
                want = [float(s.replace('%', '')) for s in expected]
                rec['checks'].append(result(name + '_physical_STEP_slopes',
                    all(abs(a-b) < 1e-7 for a, b in zip(actual, want)),
                    measured_percent=actual, required_percent=want))
            for name, thickness in item.get('footing_thicknesses', {}).items():
                expected = length(thickness, positive=True)
                actual = [s.BoundBox.ZLength for s in matched[name]]
                rec['checks'].append(result(name + '_physical_STEP_thickness',
                    all(abs(v-expected) <= tol for v in actual),
                    measured_inches=[v/25.4 for v in actual],
                    measured_output_units=[v/MM_PER_UNIT[job['units']] for v in actual],
                    output_units=job['units'], required=thickness))
            rec['files'].append({'path': str(path), 'units': job['units'], 'schema': 'AP214',
                'objects': len(objects), 'solids': len(rows), 'mapping': rows,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        rec['checks'].append(result('source_geometry_and_links_unchanged', state(doc) == before))
        rec['checks'].append({'name': 'Bentley_import_validation', 'status': 'NOT CONFIGURED'})
        if any(c['status'] == 'FAIL' for c in rec['checks']):
            raise ValueError('Export verification failed; see retained diagnostics')
        rec['status'] = 'PASS'
    except Exception as exc:
        rec['status'] = 'FAIL'
        rec['errors'].append(str(exc))
        rec['traceback'] = traceback.format_exc()
        rec['source_preserved_after_error'] = state(doc) == before
    atomic(report, rec)
    out = compact(rec)
    out['files'] = [{k: v for k, v in f.items() if k != 'mapping'} for f in rec['files']]
    with (ROOT / 'reports/change-journal.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(out) + '\n')
    return out
