"""Create and verify an illustrative beam using a native box and Arch rebars.

No model files are saved. Reinforcement is a demonstration, not a design.
The stirrup centerline uses the installed Reinforcement workbench's hook layout.
"""
import itertools
import json
import math
import re
import traceback
import uuid
from datetime import datetime, timezone

import FreeCAD as App
import Part
import Sketcher

from .geometry import length, bounds, box_checks, box_cover, pair, result

MARKER = 'CAD_AI_Illustrative_RC_Beam_v1'
SETS = ('BottomBars', 'TopBars', 'SideBarsLeft', 'SideBarsRight', 'Stirrups')
DEFAULTS = {
    'Length': '8 ft', 'Width': '24 in', 'Height': '36 in',
    'Cover': '1.5 in', 'EndCover': '1.5 in', 'StirrupCoverAllowance': '0.0625 in',
    'BottomBarNumber': 8, 'BottomCount': 4,
    'TopBarNumber': 6, 'TopCount': 4,
    'SideBarNumber': 4, 'SideCountPerFace': 4,
    'StirrupBarNumber': 4, 'StirrupSpacing': '6 in',
    'StirrupFirstDatum': '3 in', 'StirrupInsideBendDiameter': '2 in',
    'HookExtension': '3 in', 'AssemblyAllowance': '0.0625 in',
    'LongitudinalMinimumClearance': '1 in',
}


def prop(obj, kind, name, value=None, group='Beam', expression=None):
    obj.addProperty(kind, name, group)
    if value is not None:
        setattr(obj, name, value)
    if expression is not None:
        obj.setExpression(name, expression)
        obj.setEditorMode(name, 1)


def parsed_parameters(given):
    if not isinstance(given, dict) or set(given) - set(DEFAULTS):
        raise ValueError('Unsupported beam parameters')
    p = dict(DEFAULTS, **given)
    for name, val in p.items():
        if name.endswith('Number') or name.endswith('Count') or name == 'SideCountPerFace':
            if type(val) is not int:
                raise ValueError(name + ' requires an integer')
            low, high = (3, 8) if name.endswith('Number') else (2, 12)
            if not low <= val <= high:
                raise ValueError(name + ' outside supported range')
        else:
            length(val, positive=True)
    if length(p['Width']) < length('12 in') or length(p['Height']) < length('18 in'):
        raise ValueError('This illustrative adapter requires Width >= 12 in and Height >= 18 in')
    return p


class StirrupPathProxy:
    """Editable parameter-driven centerline; Arch supplies the swept solid."""
    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        from Stirrup import getpointsOfStirrup
        i = obj.Inputs
        d = i.StirrupDiameter.Value
        radius = i.StirrupCenterlineRadius.Value
        c = i.EffectiveStirrupCover.Value
        face_parameters = [(i.Width.Value, i.Height.Value),
                           App.Vector(i.StirrupFirstDatum.Value, i.Width.Value / 2,
                                      i.Height.Value / 2)]
        points = getpointsOfStirrup(face_parameters, c, c, c, c, 135,
                                   i.HookExtension.Value / d, d, radius / d,
                                   App.Vector(1, 0, 0))
        from DraftGeomUtils import filletWire
        obj.Shape = filletWire(Part.makePolygon(points), radius)
        obj.Length = obj.Shape.Length

    def dumps(self):
        return None

    def loads(self, state):
        return None


def make_inputs(doc, p):
    i = doc.addObject('App::FeaturePython', 'BeamInputs')
    i.Label = 'Beam dimensions and illustrative reinforcement'
    for name, val in p.items():
        prop(i, 'App::PropertyInteger' if type(val) is int else 'App::PropertyLength', name, val)
    prop(i, 'App::PropertyString', 'AdapterIdentifier', MARKER, 'Identity')
    prop(i, 'App::PropertyString', 'DesignStatus', 'DEMONSTRATION ONLY - structural design not performed', 'Basis')
    prop(i, 'App::PropertyString', 'LengthDefinition', 'Overall concrete length; support geometry not modeled', 'Basis')
    prop(i, 'App::PropertyString', 'MaterialAssumptions', 'Illustrative normal-weight 4000 psi concrete; Grade 60 reinforcing steel', 'Basis')
    prop(i, 'App::PropertyString', 'Limitations', 'No load analysis, deep-beam/strut-and-tie design, anchorage, bearing, seismic or fabrication approval. Straight longitudinal ends are schematic.', 'Basis')
    prop(i, 'App::PropertyString', 'AssemblyNote', 'Nominal round bar envelopes; ribs and tie wires omitted; 1/16 in stirrup cover reserve and 1/16 in allowance between longitudinal bars and transverse legs.', 'Basis')
    for prefix in ('Bottom', 'Top', 'Side', 'Stirrup'):
        prop(i, 'App::PropertyLength', prefix + 'Diameter', group='Derived',
             expression=prefix + 'BarNumber * (0.125 in)')
    derived = {
        'BarLength': 'Length - 2 * EndCover',
        'StirrupCenterlineRadius': '(StirrupInsideBendDiameter + StirrupDiameter) / 2',
        'EffectiveStirrupCover': 'Cover + StirrupCoverAllowance',
        'CornerBarY': 'EffectiveStirrupCover + StirrupDiameter / 2 + StirrupCenterlineRadius',
        'MainDistribution': 'Width - 2 * CornerBarY',
        'BottomBarZ': 'EffectiveStirrupCover + StirrupDiameter + BottomDiameter / 2 + AssemblyAllowance',
        'TopBarZ': 'Height - EffectiveStirrupCover - StirrupDiameter - TopDiameter / 2 - AssemblyAllowance',
        'SideBarY': 'EffectiveStirrupCover + StirrupDiameter + SideDiameter / 2 + AssemblyAllowance',
        'SideFirstZ': 'Height / (SideCountPerFace + 2) * 1.5',
        'SideDistribution': 'Height - 2 * SideFirstZ',
        'StirrupDistribution': '(StirrupCount - 1) * StirrupSpacing',
    }
    prop(i, 'App::PropertyInteger', 'StirrupCount', group='Derived',
         expression='floor((Length - 2 * StirrupFirstDatum) / StirrupSpacing) + 1')
    for name, expr in derived.items():
        prop(i, 'App::PropertyLength', name, group='Derived', expression=expr)
    doc.recompute()
    if i.StirrupCount < 2 or i.StirrupCount > 80 or i.MainDistribution.Value <= 0:
        raise ValueError('Beam dimensions give unsupported reinforcement arrangement')
    if i.HookExtension.Value < max(6 * i.StirrupDiameter.Value, length('3 in')):
        raise ValueError('Illustrative hook extensions require at least 6 diameters and 3 in')
    return i


def native_rebar(doc, name, base, diameter, amount):
    # FreeCAD 1.1 Arch.makeRebar's name argument sets only Label. Instantiate
    # the same native proxy explicitly so all source links use stable Names.
    import ArchRebar
    rb = doc.addObject('Part::FeaturePython', name)
    ArchRebar._Rebar(rb)
    if App.GuiUp:
        ArchRebar._ViewProviderRebar(rb.ViewObject)
    rb.Base = base
    rb.Diameter = diameter
    rb.Amount = amount
    rb.OffsetStart = 0
    rb.OffsetEnd = 0
    rb.CustomSpacing = ''
    return rb


def straight_set(doc, inputs, host, name, prefix, count_expr, yexpr, zexpr,
                 span_expr, direction, color):
    import Arch
    sk = doc.addObject('Sketcher::SketchObject', name + 'Centerline')
    sk.addGeometry(Part.LineSegment(App.Vector(), App.Vector(inputs.BarLength.Value, 0, 0)), False)
    sk.addConstraint(Sketcher.Constraint('Horizontal', 0))
    sk.addConstraint(Sketcher.Constraint('Coincident', 0, 1, -1, 1))
    index = sk.addConstraint(Sketcher.Constraint('Distance', 0, inputs.BarLength.Value))
    sk.renameConstraint(index, 'BarLength')
    sk.setExpression('Constraints.BarLength', 'BeamInputs.BarLength')
    for axis, expr in [('x', 'BeamInputs.EndCover'), ('y', yexpr), ('z', zexpr)]:
        sk.setExpression('Placement.Base.' + axis, expr)
    doc.recompute()
    if sk.solve() != 0:
        raise ValueError('Straight-bar sketch solver failed: ' + sk.Name)
    rb = native_rebar(doc, name, sk, getattr(inputs, prefix + 'Diameter').Value, 2)
    if rb is None or rb.Name != name:
        raise ValueError('Native rebar creation failed: ' + name)
    rb.Host = host
    rb.Mark = name
    rb.Direction = App.Vector(*direction)
    rb.Rounding = 0
    rb.setExpression('Amount', count_expr)
    rb.setExpression('Diameter', 'BeamInputs.' + prefix + 'Diameter')
    rb.setExpression('Distance', span_expr)
    rb.ViewObject.ShapeColor = color
    rb.ViewObject.LineColor = color
    sk.Visibility = False
    return rb


def build(doc, parameters):
    import Arch
    i = make_inputs(doc, parameters)
    host = doc.addObject('Part::Box', 'ConcreteBeam')
    host.Label = 'Concrete - 24 in wide x 36 in high x 8 ft overall'
    for key in ('Length', 'Width', 'Height'):
        host.setExpression(key, 'BeamInputs.' + key)
    host.ViewObject.ShapeColor = (0.78, 0.79, 0.80)
    host.ViewObject.Transparency = 82
    doc.recompute()
    straight_set(doc, i, host, 'BottomBars', 'Bottom', 'BeamInputs.BottomCount',
                 'BeamInputs.CornerBarY', 'BeamInputs.BottomBarZ',
                 'BeamInputs.MainDistribution', (0, 1, 0), (0.80, 0.23, 0.15))
    straight_set(doc, i, host, 'TopBars', 'Top', 'BeamInputs.TopCount',
                 'BeamInputs.CornerBarY', 'BeamInputs.TopBarZ',
                 'BeamInputs.MainDistribution', (0, 1, 0), (0.88, 0.51, 0.10))
    for name, yexpr in [('SideBarsLeft', 'BeamInputs.SideBarY'),
                        ('SideBarsRight', 'BeamInputs.Width - BeamInputs.SideBarY')]:
        straight_set(doc, i, host, name, 'Side', 'BeamInputs.SideCountPerFace', yexpr,
                     'BeamInputs.SideFirstZ', 'BeamInputs.SideDistribution', (0, 0, 1), (0.18, 0.52, 0.28))
    path = doc.addObject('Part::FeaturePython', 'StirrupCenterline')
    prop(path, 'App::PropertyLink', 'Inputs', i)
    prop(path, 'App::PropertyLength', 'Length', group='Measured')
    path.setEditorMode('Length', 1)
    StirrupPathProxy(path)
    doc.recompute()
    st = native_rebar(doc, 'Stirrups', path, i.StirrupDiameter.Value, i.StirrupCount)
    if st is None or st.Name != 'Stirrups':
        raise ValueError('Native stirrup creation failed')
    st.Host = host
    st.Mark = 'S1'
    st.Direction = App.Vector(1, 0, 0)
    st.setExpression('Amount', 'BeamInputs.StirrupCount')
    st.setExpression('Diameter', 'BeamInputs.StirrupDiameter')
    st.setExpression('Distance', 'BeamInputs.StirrupDistribution')
    # The centerline already contains true tangent arcs; do not fillet twice.
    st.Rounding = 0
    st.ViewObject.ShapeColor = (0.16, 0.34, 0.73)
    st.ViewObject.LineColor = (0.16, 0.34, 0.73)
    path.Visibility = False
    doc.recompute()
    for name, label in [('BottomBars', 'B1 - 4 #8 bottom bars'), ('TopBars', 'T1 - 4 #6 top bars'),
                        ('SideBarsLeft', 'W1 - 4 #4 left face bars'), ('SideBarsRight', 'W2 - 4 #4 right face bars'),
                        ('Stirrups', 'S1 - 16 #4 stirrups at 6 in; 135-degree hooks')]:
        doc.getObject(name).Label = label
    q = doc.addObject('App::FeaturePython', 'BeamQuantities')
    q.Label = 'Live beam quantities - illustrative only'
    prop(q, 'App::PropertyLink', 'Inputs', i, 'Sources')
    for name in ('ConcreteBeam', *SETS):
        prop(q, 'App::PropertyLink', name, doc.getObject(name), 'Sources')
    prop(q, 'App::PropertyInteger', 'TotalBars', group='Quantities',
         expression=' + '.join(n + '.Amount' for n in SETS))
    prop(q, 'App::PropertyLength', 'TotalSteelLength', group='Quantities',
         expression=' + '.join(n + '.TotalLength' for n in SETS))
    prop(q, 'App::PropertyVolume', 'GrossConcreteVolume', group='Quantities',
         expression='ConcreteBeam.Length * ConcreteBeam.Width * ConcreteBeam.Height')
    doc.Label = 'RC BEAM 24 x 36 in x 8 ft - DEMONSTRATION'
    doc.UnitSystem = 5
    doc.recompute()
    host.Visibility = True
    return i


def validate(doc, tol):
    i = doc.getObject('BeamInputs')
    if i is None or i.AdapterIdentifier != MARKER:
        raise ValueError('Not an illustrative beam from this adapter')
    host = doc.getObject('ConcreteBeam')
    checks = box_checks(host, tol)
    invalid = [o.Name for o in doc.Objects if any('Invalid' in str(s) or 'Error' in str(s) for s in o.State)]
    checks.append(result('dependency_state', not invalid, invalid_objects=invalid))
    physical = []
    all_lengths = 0.0
    rows = []
    for name in SETS:
        rb = doc.getObject(name)
        s = rb.Shape
        solids = list(s.Solids)
        checks.append(result(name + '.native_geometry', getattr(rb.Proxy, 'Type', None) == 'Rebar'
                             and s.isValid() and len(solids) == rb.Amount and all(x.isValid() for x in solids),
                             measured_count=len(solids), expected_count=rb.Amount))
        cylinders = [f.Surface.Radius for f in s.Faces if isinstance(f.Surface, Part.Cylinder)]
        checks.append(result(name + '.nominal_diameter', bool(cylinders)
                             and max(abs(2 * r - rb.Diameter.Value) for r in cylinders) <= tol,
                             measured_diameters_in=sorted(set(round(2*r/25.4, 8) for r in cylinders))))
        wires, radius = rb.Proxy.getRebarData(rb)
        path_length = sum(w.Length for w in wires)
        expected_volume = math.pi * radius ** 2 * path_length
        checks.append(result(name + '.physical_volume_and_lengths',
                             abs(s.Volume - expected_volume) <= max(1e-5, expected_volume * 1e-7)
                             and abs(rb.TotalLength.Value - path_length) <= tol,
                             measured_volume_in3=s.Volume/25.4**3,
                             native_total_length_ft=rb.TotalLength.Value/304.8,
                             volume_derived_length_ft=s.Volume/(math.pi*radius**2)/304.8,
                             centerline_length_ft=path_length/304.8))
        expected_span = rb.Distance.Value
        axis = 'x' if name == 'Stirrups' else ('z' if name.startswith('Side') else 'y')
        centers = sorted(getattr(solid.CenterOfMass, axis) for solid in solids)
        gaps = [b-a for a,b in zip(centers, centers[1:])]
        target_spacing = expected_span / (rb.Amount-1)
        checks.append(result(name + '.spacing', bool(gaps)
                             and max(abs(g - target_spacing) for g in gaps) <= tol,
                             measured_spacing_in=[v/25.4 for v in gaps]))
        if name != 'Stirrups':
            measured_bounds = [bounds(solid) for solid in solids]
            checks.append(result(name + '.longitudinal_extents', all(
                abs(b.XMin-i.EndCover.Value) <= tol and abs(b.XMax-(i.Length.Value-i.EndCover.Value)) <= tol
                for b in measured_bounds)))
        cv = box_cover(s, host, i.Cover.Value, tol)
        cv['name'] = name + '.cover'
        checks.append(cv)
        checks.append(result(name + '.source_links', rb.Host == host and rb.Base is not None
                             and rb.Base.Document == doc and bool(rb.ExpressionEngine)))
        for index, solid in enumerate(solids, 1):
            physical.append((name, index, solid))
        all_lengths += path_length
        rows.append({'object':name, 'bar_number':getattr(i, ('Stirrup' if name == 'Stirrups' else 'Side' if name.startswith('Side') else 'Bottom' if name == 'BottomBars' else 'Top')+'BarNumber'),
                     'count':len(solids), 'diameter_in':rb.Diameter.Value/25.4,
                     'each_length_ft':path_length/rb.Amount/304.8, 'spacing_in':target_spacing/25.4})
    # Use the shared physical nominal-solid checker, including positive-volume overlap.
    pair_rows = []
    for (an, ai, a), (bn, bi, b) in itertools.combinations(physical, 2):
        minimum = 0.0 if 'Stirrups' in (an, bn) else i.LongitudinalMinimumClearance.Value
        # Disjoint axis-aligned boxes prove separation; exact booleans are needed
        # only when their boxes overlap. The lower bound also proves clearance.
        ab, bb = bounds(a), bounds(b)
        lower = math.sqrt(sum(max(0, getattr(ab,ax+'Min')-getattr(bb,ax+'Max'),
                                  getattr(bb,ax+'Min')-getattr(ab,ax+'Max'))**2 for ax in 'XYZ'))
        if lower > minimum + tol:
            pr = {'status':'PASS', 'classification':'SEPARATED', 'lower_bound_in':lower/25.4,
                  'method':'disjoint BRep bounds prove required clearance', 'minimum_in':minimum/25.4}
        else:
            pr = pair(a,b,minimum,tol)
        pair_rows.append({'a':f'{an}:{ai}', 'b':f'{bn}:{bi}', **pr})
    failures = [r for r in pair_rows if r['status'] == 'FAIL']
    checks.append(result('reinforcement_clearance', not failures, checked_pairs=len(pair_rows),
                         overlap_pairs=sum(r.get('classification') == 'OVERLAP' for r in pair_rows),
                         failures=failures, details=pair_rows,
                         policy='At least 1 in between longitudinal bars; transverse ties may contact but never overlap.'))
    q = doc.getObject('BeamQuantities')
    checks.append(result('live_quantities', q.TotalBars == len(physical)
                         and abs(q.TotalSteelLength.Value-all_lengths) <= tol
                         and abs(q.GrossConcreteVolume.Value-host.Shape.Volume) <= 1e-5,
                         physical_bars=len(physical), total_length_ft=all_lengths/304.8,
                         gross_concrete_ft3=host.Shape.Volume/304.8**3))
    checks.extend({'name':n,'status':'NOT CONFIGURED'} for n in
                  ('structural_design', 'anchorage_development', 'bearing_and_supports',
                   'fabrication_detailing'))
    pages=[doc.getObject(n) for n in ('BeamAssemblySheet','BeamDetailSheet')]
    if all(pages):
        from .beam_drawings import checks as drawing_checks
        checks.extend(drawing_checks(doc,tol))
    elif any(pages):
        checks.append(result('drawing_links',False,reason='The two-sheet set is incomplete'))
    else:
        checks.append({'name':'drawing_links','status':'NOT CONFIGURED'})
    fdot_pages=[doc.getObject(n) for n in ('BeamFdotAssemblySheet','BeamFdotDetailSheet')]
    if all(fdot_pages):
        from .beam_fdot import checks as fdot_checks
        checks.extend(fdot_checks(doc,tol))
    elif any(fdot_pages):
        checks.append(result('fdot_drawing_links',False,reason='The two-sheet FDOT set is incomplete'))
    if 'MainEndHooks' in i.PropertiesList:
        from .beam_hooks import hook_checks
        checks.extend(hook_checks(doc,tol))
    return checks, rows


def create(job):
    from .api import ROOT, atomic, compact, check_gui
    if set(job) - {'operation','document','parameters','tolerance','request_id'}:
        raise ValueError('Unknown create_rc_beam job fields')
    name = job.get('document')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name):
        raise ValueError('Explicit valid new document Name required')
    p = parsed_parameters(job.get('parameters', {}))
    tol = length(job.get('tolerance', '0.001 in'), positive=True)
    request_id = job.get('request_id', 'beam-'+uuid.uuid4().hex)
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', request_id):
        raise ValueError('Invalid request_id')
    path = ROOT/'reports/transactions'/(request_id+'.json')
    if path.exists():
        prior = json.loads(path.read_text(encoding='utf-8'))
        if prior['request'] != job:
            raise ValueError('request_id belongs to a different job')
        if prior['status'] in ('PREPARED','VALIDATED'):
            raise RuntimeError('Unknown prior outcome; inspect document and transaction')
        return compact(prior)
    if name in App.listDocuments():
        raise ValueError('Document already exists; refusing to modify it')
    check_gui(App.ActiveDocument)
    prior_doc = App.ActiveDocument.Name if App.ActiveDocument else None
    r = {'timestamp':datetime.now(timezone.utc).isoformat(), 'helper_version':'beam-1',
         'freecad_version':App.Version()[:3], 'operation':'create_rc_beam','document':name,
         'transaction_id':request_id,'request':job,'status':'PREPARED','checks':[],
         'changes':{'new_document':{'old':None,'new':name},'parameters':p},
         'warnings':['Illustrative reinforcement only; no structural design or code-compliance approval.',
                     '8 ft is the overall modeled length, not a verified clear span.',
                     'Straight longitudinal ends are schematic; development and support anchorage are not designed.'],
         'errors':[], 'recompute':'NOT RUN','rollback':'NOT NEEDED', 'saved':False,'report_path':str(path)}
    atomic(path,r)
    doc = None
    opened = False
    committed = False
    try:
        doc = App.newDocument(name)
        doc.UndoMode = 1
        doc.openTransaction('CAD_AI '+request_id)
        opened = True
        build(doc,p)
        r['recompute'] = 'DONE'
        r['checks'], r['reinforcement'] = validate(doc,tol)
        if any(c['status']=='FAIL' for c in r['checks']):
            raise ValueError('Physical geometry validation failed; see report')
        r['status'] = 'VALIDATED'
        atomic(path,r)
        doc.commitTransaction()
        opened = False
        committed = True
        r['status'] = 'PASS'
        if App.GuiUp:
            import FreeCADGui as Gui
            Gui.activeDocument().activeView().viewAxonometric()
            Gui.activeDocument().activeView().fitAll()
    except Exception as exc:
        r['status'] = 'FAIL'
        r['errors'].append(str(exc))
        r['traceback'] = traceback.format_exc()
        if opened:
            doc.abortTransaction()
            opened = False
        if doc is not None and not committed:
            App.closeDocument(name)
            r['rollback'] = 'COMPLETE' if name not in App.listDocuments() else 'INCOMPLETE'
            if prior_doc:
                App.setActiveDocument(prior_doc)
        elif committed:
            r['rollback'] = 'NOT POSSIBLE: committed; inspect document'
    atomic(path,r)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(compact(r),allow_nan=False)+'\n')
    return compact(r)
