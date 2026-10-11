"""Linked terrain spot annotations; preserve native geometry and never save."""
import hashlib
import json
import re
import traceback
from datetime import datetime, timezone

import FreeCAD as App
import Part
import numpy as np
from draftobjects.text import Text
from draftviewproviders.view_text import ViewProviderText

from . import bridge, mse
from .api import atomic, check_gui, compact, document, resolve
from .geometry import length, result
from .terrain_exchange import Terrain, US_FOOT_M

ROOT = bridge.ROOT


def triangles(source):
    if 'Mesh' not in source.PropertiesList:
        raise ValueError('Expected explicit terrain Mesh source')
    if not source.Placement.isIdentity():
        raise ValueError('Nonidentity terrain placement is not supported')
    values = np.array([[list(p) for p in f.Points] for f in source.Mesh.Facets])
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('Empty or nonfinite terrain')
    return values


def height(source, x, y):
    values = triangles(source)
    terrain = Terrain(values.reshape(-1, 3), np.arange(len(values) * 3).reshape(-1, 3))
    z = float(terrain.heights([[x, y]])[0])
    if not np.isfinite(z):
        raise ValueError('Point is outside the linked terrain; no extrapolation permitted')
    return z


class SpotProxy(Text):
    def mustExecute(self, obj):
        # App::FeaturePython annotations have no native geometry dirtiness check.
        # Refresh from the linked mesh whenever included in a document recompute.
        return 1

    def execute(self, obj):
        z = height(obj.Terrain, obj.LocalX.Value, obj.LocalY.Value)
        obj.MeasuredPoint = App.Vector(obj.LocalX.Value, obj.LocalY.Value, z)
        obj.Elevation = z + obj.VerticalOffset.Value
        obj.Text = [obj.PointID, f'EG EL {obj.Elevation.Value / (US_FOOT_M * 1000):.2f} US ft', obj.GeographicLocation]
        obj.Placement = App.Placement(obj.MeasuredPoint + obj.TextOffset, App.Rotation())


class LeaderProxy(mse.Serializable):
    def __init__(self, obj):
        obj.Proxy = self

    def mustExecute(self, obj):
        return 1

    def execute(self, obj):
        point = obj.Annotation.MeasuredPoint
        end = obj.Annotation.Placement.Base
        obj.Shape = Part.makeCompound([Part.Vertex(point), Part.makeLine(point, end)])


def mesh_state(doc):
    return {o.Name: hashlib.sha256(triangles(o).tobytes()).hexdigest()
            for o in doc.Objects if 'Mesh' in o.PropertiesList}


def add(job):
    doc = document(job['document'])
    check_gui(doc)
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):
        raise ValueError('Pending model edits')
    source = resolve(doc, job['terrain'])
    rid, name = job['request_id'], job['object_name']
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', rid) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]+', name):
        raise ValueError('Invalid request ID or object Name')
    report = ROOT / 'reports/transactions' / (rid + '.json')
    if report.exists():
        raise ValueError('Inspect existing transaction before retry')
    if doc.getObject(name) or doc.getObject(name + 'Leader'):
        raise ValueError('Annotation object already exists')
    if not job.get('coordinate_basis'):
        raise ValueError('Explicit coordinate basis required')
    tol = length(job['tolerance'], True)
    x, y = length(job['local_x']), length(job['local_y'])
    offset = length(job['vertical_offset'])
    expected = length(job['expected_elevation'])
    text_offset = App.Vector(*[length(v) for v in job['text_offset']])
    font = length(job['font_size'], True)
    z = height(source, x, y)
    if abs(z + offset - expected) > tol:
        raise ValueError('Physical terrain disagrees with independent source elevation')
    before = bridge.source_state(doc, [o.Name for o in doc.Objects])
    meshes = mesh_state(doc)
    rec = {'operation': 'add_terrain_spot', 'document': doc.Name,
           'transaction_id': rid, 'request': job,
           'timestamp': datetime.now(timezone.utc).isoformat(), 'status': 'PREPARED',
           'checks': [], 'errors': [], 'rollback': 'NOT NEEDED', 'model_saved': False,
           'report_path': str(report),
           'warnings': ['Existing model coordination failures are unchanged. This annotation does not rerun structural, cover or clearance checks.']}
    atomic(report, rec)
    doc.openTransaction(rid)
    try:
        obj = doc.addObject('App::FeaturePython', name)
        SpotProxy(obj)
        ViewProviderText(obj.ViewObject)
        for prop_name, typ, value in [
            ('Terrain', 'App::PropertyLink', source),
            ('LocalX', 'App::PropertyDistance', x),
            ('LocalY', 'App::PropertyDistance', y),
            ('VerticalOffset', 'App::PropertyDistance', offset),
            ('CoordinateBasis', 'App::PropertyString', job['coordinate_basis']),
            ('GeographicLocation', 'App::PropertyString', job['geographic_location']),
            ('PointID', 'App::PropertyString', job['point_id']),
            ('TextOffset', 'App::PropertyVector', text_offset),
            ('MeasuredPoint', 'App::PropertyVector', App.Vector()),
            ('Elevation', 'App::PropertyDistance', 0),
            ('Provenance', 'App::PropertyString', json.dumps(job.get('provenance', {}), sort_keys=True))]:
            mse.prop(obj, typ, prop_name, value, 'Terrain spot')
        for prop_name in ['MeasuredPoint', 'Elevation']:
            obj.setEditorMode(prop_name, 1)
        obj.Label = job['point_id'] + ' | Existing-ground elevation'
        obj.ViewObject.FontSize = font
        obj.ViewObject.DisplayMode = 'World'
        obj.ViewObject.TextColor = (0.80, 0.12, 0.08)
        leader = doc.addObject('Part::FeaturePython', name + 'Leader')
        mse.prop(leader, 'App::PropertyLink', 'Annotation', obj, 'Source')
        LeaderProxy(leader)
        bridge.initialize_display(leader)
        leader.ViewObject.LineColor = (0.80, 0.12, 0.08)
        leader.ViewObject.LineWidth = 2.0
        leader.ViewObject.PointSize = 7.0
        doc.recompute([obj, leader])
        point = obj.MeasuredPoint
        # Physical triangular face distance is independent of barycentric interpolation.
        tri = triangles(source)
        candidates = tri[(tri[:, :, 0].min(1) <= x) & (tri[:, :, 0].max(1) >= x)
                         & (tri[:, :, 1].min(1) <= y) & (tri[:, :, 1].max(1) >= y)]
        distances = []
        for t in candidates:
            vertices = [App.Vector(*p) for p in t]
            face = Part.Face(Part.makePolygon(vertices + vertices[:1]))
            distances.append(face.distToShape(Part.Vertex(point))[0])
        actual_distance = min(distances) if distances else float('inf')
        rec['checks'] = [
            result('point_on_physical_terrain_face', actual_distance <= tol, distance_mm=actual_distance),
            result('independent_source_elevation', abs(obj.Elevation.Value - expected) <= tol,
                   difference_mm=obj.Elevation.Value - expected),
            result('leader_anchored_on_terrain', min(v.Point.distanceToPoint(point) for v in leader.Shape.Vertexes) <= tol),
            result('native_links', obj.Terrain == source and leader.Annotation == obj),
            result('label_matches_measured_elevation', obj.Text[1] == f'EG EL {obj.Elevation.Value / (US_FOOT_M * 1000):.2f} US ft'),
            result('annotation_geometry_valid', leader.Shape.isValid()),
            result('annotation_states_valid', not any(s in ['Invalid', 'Touched'] for o in [obj, leader] for s in o.State)),
            result('original_native_geometry_links_placements_visibility_exact', bridge.source_state(doc, list(before)) == before),
            result('original_terrain_meshes_exact', mesh_state(doc) == meshes)]
        rec['new_objects'] = [obj.Name, leader.Name]
        rec['measured_point_mm'] = list(point)
        rec['elevation_us_ft'] = obj.Elevation.Value / (US_FOOT_M * 1000)
        rec['text'] = obj.Text
        if any(c['status'] == 'FAIL' for c in rec['checks']):
            raise ValueError('Terrain annotation validation failed')
        if job.get('test_failure'):
            raise ValueError('Deliberate rollback test')
        rec['status'] = 'VALIDATED'
        atomic(report, rec)
        doc.commitTransaction()
        rec['status'] = 'PASS'
    except Exception as exc:
        rec['status'] = 'FAIL'
        rec['errors'] = [str(exc)]
        rec['traceback'] = traceback.format_exc()
        doc.abortTransaction()
        rec['rollback'] = 'VERIFIED' if (set(o.Name for o in doc.Objects) == set(before)
                           and bridge.source_state(doc, list(before)) == before
                           and mesh_state(doc) == meshes) else 'FAILED'
    atomic(report, rec)
    with (ROOT / 'reports/change-journal.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({k: rec[k] for k in ['operation', 'document', 'transaction_id', 'status', 'rollback', 'model_saved', 'report_path']}) + '\n')
    return compact(rec)
