"""Transactional 90-degree end hooks for the illustrative beam's main bars."""
import json
import math
import re
import traceback
import uuid
from datetime import datetime, timezone

import FreeCAD as App
import Part
import Sketcher

from . import beam
from .geometry import length, bounds, result

TARGETS = ('BottomBars', 'TopBars')
PARAMETERS = ('BottomInsideBendDiameter', 'BottomTailLength',
              'TopInsideBendDiameter', 'TopTailLength')


def state(doc):
    """Small exact source/state snapshot; never serializes BRep."""
    i = doc.getObject('BeamInputs')
    objects = {}
    for name in ('ConcreteBeam', *beam.SETS):
        obj = doc.getObject(name)
        b = bounds(obj.Shape)
        item = {'volume_mm3':obj.Shape.Volume, 'bounds_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],
                'placement':str(obj.Placement), 'expressions':list(obj.ExpressionEngine), 'label':obj.Label}
        if name != 'ConcreteBeam':
            sk = obj.Base
            item.update({'base':sk.Name,'count':obj.Amount,'diameter_mm':obj.Diameter.Value,
                         'length_mm':obj.Length.Value,'base_placement':str(sk.Placement),
                         'base_expressions':list(sk.ExpressionEngine)})
            if sk.TypeId == 'Sketcher::SketchObject':
                item['geometry_count'] = sk.GeometryCount
                item['constraints'] = [str(c) for c in sk.Constraints]
        objects[name] = item
    return {'objects':objects,'input_properties':sorted(i.PropertiesList),
            'input_expressions':list(i.ExpressionEngine),'limitations':i.Limitations,
            'document_objects':sorted(o.Name for o in doc.Objects),'filename':doc.FileName}


def equivalent(before, after, tol):
    # Numerical shape tolerances are separate from exact source identity checks.
    a = json.loads(json.dumps(before))
    b = json.loads(json.dumps(after))
    okay = True
    for name in a['objects']:
        av = a['objects'][name].pop('volume_mm3')
        bv = b['objects'][name].pop('volume_mm3')
        okay &= abs(av-bv) <= max(1e-5,abs(av)*1e-7)
        ab = a['objects'][name].pop('bounds_mm')
        bb = b['objects'][name].pop('bounds_mm')
        okay &= max(abs(x-y) for x,y in zip(ab,bb)) <= tol
    return okay and a == b


def check_sources(doc):
    i = doc.getObject('BeamInputs')
    if i is None or i.AdapterIdentifier != beam.MARKER:
        raise ValueError('This operation requires the tested illustrative beam adapter')
    if 'MainEndHooks' in i.PropertiesList:
        raise ValueError('Main end hooks already configured; inspect before a different edit')
    for name in TARGETS:
        rb = doc.getObject(name)
        sk = doc.getObject(name+'Centerline')
        if rb is None or sk is None or rb.Base != sk or rb.Host != doc.getObject('ConcreteBeam'):
            raise ValueError('Unexpected main-bar source links: '+name)
        if sk.TypeId != 'Sketcher::SketchObject' or sk.GeometryCount != 1 or sk.ConstraintCount != 3:
            raise ValueError('Unsupported centerline topology; source must be inspected first: '+sk.Name)
        if [c.Type for c in sk.Constraints] != ['Horizontal','Coincident','Distance']:
            raise ValueError('Unsupported straight-bar constraints: '+sk.Name)
        if sk.Placement.Rotation.Angle != 0 or not rb.Placement.isIdentity():
            raise ValueError('Unexpected bar placement; preserve and inspect it before adaptation')
        expected = {'.Constraints.BarLength':'BeamInputs.BarLength',
                    '.Placement.Base.x':'BeamInputs.EndCover',
                    '.Placement.Base.y':'BeamInputs.CornerBarY',
                    '.Placement.Base.z':'BeamInputs.'+('Bottom' if name=='BottomBars' else 'Top')+'BarZ'}
        if dict(sk.ExpressionEngine) != expected:
            raise ValueError('Unexpected source expressions; refusing to overwrite: '+sk.Name)
    return i


def dimension(sk, kind, geometry, value, name, expr, point=None):
    constraint = Sketcher.Constraint(kind,geometry,value) if point is None else Sketcher.Constraint(kind,geometry,point,value)
    idx = sk.addConstraint(constraint)
    sk.renameConstraint(idx,name)
    sk.setExpression('Constraints.'+name,expr)


def add_to_sketch(doc, rb, prefix):
    """Retain the original Sketcher object, main line, and named length constraint."""
    i = doc.BeamInputs
    sk = rb.Base
    radius = getattr(i,prefix+'HookRadius').Value
    tail = getattr(i,prefix+'HookTail').Value
    diameter = rb.Diameter.Value
    width = i.Length.Value-2*i.EndCover.Value-diameter
    run = width-2*radius
    if run <= 0:
        raise ValueError('Beam too short for requested hooks')
    # The original line is retained as geometry 0. Its length now means the
    # straight run between hook tangencies instead of the full end-to-end span.
    sk.delConstraint(1)  # Origin coincidence is replaced by the bend-radius offset.
    sk.setExpression('Constraints.BarLength','BeamInputs.'+prefix+'HookRun')
    sk.addConstraint(Sketcher.Constraint('PointOnObject',0,1,-1))
    dimension(sk,'DistanceX',0,radius,'HookStartX','BeamInputs.'+prefix+'HookRadius',point=1)
    doc.recompute()
    arc_left = sk.addGeometry(Part.ArcOfCircle(Part.Circle(App.Vector(radius,radius,0),App.Vector(0,0,1),radius),math.pi,1.5*math.pi),False)
    leg_left = sk.addGeometry(Part.LineSegment(App.Vector(0,radius+tail,0),App.Vector(0,radius,0)),False)
    arc_right = sk.addGeometry(Part.ArcOfCircle(Part.Circle(App.Vector(width-radius,radius,0),App.Vector(0,0,1),radius),1.5*math.pi,2*math.pi),False)
    leg_right = sk.addGeometry(Part.LineSegment(App.Vector(width,radius,0),App.Vector(width,radius+tail,0)),False)
    sk.addConstraint(Sketcher.Constraint('Tangent',arc_left,2,0,1))
    sk.addConstraint(Sketcher.Constraint('Tangent',leg_left,2,arc_left,1))
    sk.addConstraint(Sketcher.Constraint('Vertical',leg_left))
    sk.addConstraint(Sketcher.Constraint('Tangent',0,2,arc_right,1))
    sk.addConstraint(Sketcher.Constraint('Tangent',arc_right,2,leg_right,1))
    sk.addConstraint(Sketcher.Constraint('Vertical',leg_right))
    for idx,side in ((arc_left,'Left'),(arc_right,'Right')):
        dimension(sk,'Radius',idx,radius,side+'HookRadius','BeamInputs.'+prefix+'HookRadius')
    for idx,side in ((leg_left,'Left'),(leg_right,'Right')):
        dimension(sk,'Distance',idx,tail,side+'HookTail','BeamInputs.'+prefix+'HookTail')
    sk.Placement.Rotation = App.Rotation(App.Vector(1,0,0),90 if prefix=='Bottom' else -90)
    sk.setExpression('Placement.Base.x','BeamInputs.EndCover + BeamInputs.'+prefix+'Diameter / 2')
    sk.setExpression('Placement.Base.y','BeamInputs.'+('MainHookFirstY' if prefix=='Bottom' else 'TopHookFirstY'))
    rb.setExpression('Distance','BeamInputs.'+('MainHookDistribution' if prefix=='Bottom' else 'TopHookDistribution'))
    doc.recompute()
    if sk.solve()!=0 or sk.FullyConstrained is not True:
        raise ValueError('Hook sketch not fully constrained: '+sk.Name)
    rb.Label = '{} - {} #{} {} bars - 90-degree hooks both ends'.format(
        'B1' if prefix=='Bottom' else 'T1',rb.Amount,getattr(i,prefix+'BarNumber'),prefix.lower())
    sk.Visibility=False


def apply(doc, params):
    i = doc.BeamInputs
    beam.prop(i,'App::PropertyString','MainEndHooks','90 degrees at both ends; bottom up, top down','Main hooks')
    beam.prop(i,'App::PropertyLength','MainHookFirstY',group='Main hooks',expression=
              'max(CornerBarY, SideBarY + (max(BottomDiameter, TopDiameter) + SideDiameter) / 2 + LongitudinalMinimumClearance + AssemblyAllowance)')
    beam.prop(i,'App::PropertyLength','MainHookDistribution',group='Main hooks',expression='Width - 2 * MainHookFirstY')
    # Put the entire top-bar plane beyond the farthest stirrup-tail envelope.
    # For the installed 135-degree layout the far tail centerline reaches
    # c+d/2+R+(R+tail)/sqrt(2). Add both nominal radii and assembly allowance;
    # this also clears the curved main-bar ends, not only their straight runs.
    beam.prop(i,'App::PropertyLength','TopHookFirstY',group='Main hooks',expression=
              'max(MainHookFirstY, EffectiveStirrupCover + StirrupDiameter + StirrupCenterlineRadius + (StirrupCenterlineRadius + HookExtension) / sqrt(2) + TopDiameter / 2 + AssemblyAllowance)')
    beam.prop(i,'App::PropertyLength','TopHookDistribution',group='Main hooks',expression='Width - 2 * TopHookFirstY')
    for prefix in ('Bottom','Top'):
        beam.prop(i,'App::PropertyLength',prefix+'HookInsideDiameter',params[prefix+'InsideBendDiameter'],'Main hooks')
        beam.prop(i,'App::PropertyLength',prefix+'HookTail',params[prefix+'TailLength'],'Main hooks')
        beam.prop(i,'App::PropertyLength',prefix+'HookRadius',group='Main hooks',expression=
                  '('+prefix+'HookInsideDiameter + '+prefix+'Diameter) / 2')
        beam.prop(i,'App::PropertyLength',prefix+'HookRun',group='Main hooks',expression=
                  'Length - 2 * EndCover - '+prefix+'Diameter - 2 * '+prefix+'HookRadius')
    doc.recompute()
    for prefix in ('Bottom','Top'):
        add_to_sketch(doc,doc.getObject(prefix+'Bars'),prefix)
    i.Limitations='No load analysis, deep-beam/strut-and-tie design, anchorage development, bearing, seismic or fabrication approval. Main bars have standard hook geometry; side-bar ends remain schematic.'
    doc.recompute()


def hook_checks(doc, tol):
    i = doc.BeamInputs
    if 'MainEndHooks' not in i.PropertiesList:
        return []
    checks=[]
    for prefix in ('Bottom','Top'):
        rb=doc.getObject(prefix+'Bars')
        sk=rb.Base
        d=rb.Diameter.Value
        radius=getattr(i,prefix+'HookRadius').Value
        tail=getattr(i,prefix+'HookTail').Value
        arcs=[e for e in sk.Shape.Edges if isinstance(e.Curve,Part.Circle)]
        straight=[e for e in sk.Shape.Edges if isinstance(e.Curve,Part.Line)]
        vertical=[e for e in straight if abs(abs(e.tangentAt(e.FirstParameter).z)-1)<1e-9]
        angle_ok=len(arcs)==2 and all(abs(e.Length/e.Curve.Radius-math.pi/2)<1e-8 for e in arcs)
        inside=[2*e.Curve.Radius-d for e in arcs]
        tail_lengths=[e.Length for e in vertical]
        checks.append(result(prefix+'.standard_90_hook_geometry',angle_ok
                             and len(vertical)==2 and len(straight)==3
                             and all(abs(v-radius*2+d)<=tol and v+tol>=6*d for v in inside)
                             and all(abs(v-tail)<=tol and v+tol>=12*d for v in tail_lengths),
                             measured_inside_diameters_in=[v/25.4 for v in inside],
                             measured_tails_in=[v/25.4 for v in tail_lengths],
                             measured_angles_deg=[e.Length/e.Curve.Radius*180/math.pi for e in arcs]))
        toruses=[f.Surface for f in rb.Shape.Faces if isinstance(f.Surface,Part.Toroid)]
        checks.append(result(prefix+'.physical_bends',len(toruses)==rb.Amount*2
                             and all(abs(t.MajorRadius-radius)<=tol and abs(t.MinorRadius-d/2)<=tol for t in toruses),
                             measured_bend_surfaces=len(toruses)))
        expected=getattr(i,prefix+'HookRun').Value+math.pi*radius+2*tail
        checks.append(result(prefix+'.hooked_length',abs(sk.Shape.Length-expected)<=tol
                             and abs(rb.Length.Value-expected)<=tol,
                             measured_each_length_in=rb.Length.Value/25.4,expected_each_length_in=expected/25.4))
        checks.append(result(prefix+'.editable_sketch',sk.TypeId=='Sketcher::SketchObject'
                             and sk.FullyConstrained and sk.GeometryCount==5 and len(sk.ExpressionEngine)>=8))
    return checks


def update(job):
    from .api import ROOT, document, atomic, compact, check_gui
    if set(job)-{'operation','document','targets','parameters','tolerance','request_id'}:
        raise ValueError('Unsupported hook operation fields')
    doc=document(job.get('document'))
    if job.get('targets')!=list(TARGETS):
        raise ValueError('Targets must be explicit BottomBars and TopBars in that order')
    params=job.get('parameters')
    if not isinstance(params,dict) or set(params)!=set(PARAMETERS):
        raise ValueError('Explicit bend diameters and tail lengths with units are required')
    values={k:length(v,positive=True) for k,v in params.items()}
    tol=length(job.get('tolerance','0.001 in'),positive=True)
    req=job.get('request_id','hooks-'+uuid.uuid4().hex)
    if not isinstance(req,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',req):
        raise ValueError('Invalid request_id')
    path=ROOT/'reports/transactions'/(req+'.json')
    if path.exists():
        prior=json.loads(path.read_text(encoding='utf-8'))
        if prior['request']!=job:
            raise ValueError('request_id already used for a different job')
        if prior['status'] in ('PREPARED','VALIDATED'):
            raise RuntimeError('Previous outcome unknown; inspect actual state before retry')
        return compact(prior)
    check_gui(doc)
    i=check_sources(doc)
    for prefix in ('Bottom','Top'):
        n=getattr(i,prefix+'BarNumber')
        d=doc.getObject(prefix+'Bars').Diameter.Value
        if not 3<=n<=8 or abs(d-n*length('0.125 in'))>tol:
            raise ValueError('Supported standard hooks require matching US #3 through #8 nominal bars')
        if values[prefix+'InsideBendDiameter']+tol<6*d or values[prefix+'TailLength']+tol<12*d:
            raise ValueError('90-degree main-bar hooks require inside bend >=6db and straight tail >=12db')
    before=state(doc)
    record={'timestamp':datetime.now(timezone.utc).isoformat(),'helper_version':'beam-hooks-1',
            'freecad_version':App.Version()[:3],'operation':job['operation'],'document':doc.Name,
            'targets':list(TARGETS),'request':job,'transaction_id':req,'status':'PREPARED',
            'changes':{},'checks':[],'errors':[],'warnings':['Standard hook geometry is not verification of anchorage development or structural adequacy.'],
            'rollback':'NOT NEEDED','saved':False,'recompute':'NOT RUN','report_path':str(path),
            'before':before}
    atomic(path,record)
    opened=False
    old_undo=doc.UndoMode
    try:
        if not old_undo:
            doc.UndoMode=1
        doc.openTransaction('CAD_AI '+req)
        opened=True
        apply(doc,params)
        record['recompute']='DONE'
        record['checks'],record['reinforcement']=beam.validate(doc,tol)
        record['after']=state(doc)
        unchanged=all(equivalent({'objects':{n:before['objects'][n]}}, {'objects':{n:record['after']['objects'][n]}},tol)
                      for n in ('ConcreteBeam','SideBarsLeft','SideBarsRight','Stirrups'))
        record['checks'].append(result('unrequested_geometry_preserved',unchanged))
        for prefix in ('Bottom','Top'):
            name=prefix+'Bars'
            record['changes'][name]={'shape':{'old':'straight','new':'90-degree hooks at both ends'},
                'bar_number':getattr(i,prefix+'BarNumber'),'count':doc.getObject(name).Amount,
                'inside_bend_diameter_in':values[prefix+'InsideBendDiameter']/25.4,
                'straight_tail_in':values[prefix+'TailLength']/25.4,
                'each_length_in':{'old':before['objects'][name]['length_mm']/25.4,'new':doc.getObject(name).Length.Value/25.4}}
        record['changes']['first_bar_center_y_in']={'old':i.CornerBarY.Value/25.4,
            'new_bottom':i.MainHookFirstY.Value/25.4,'new_top':i.TopHookFirstY.Value/25.4,
            'reason':'Maintain side-bar clearance at hook crossings and avoid the stirrup closure tails'}
        if any(c['status']=='FAIL' for c in record['checks']):
            raise ValueError('Validation failed; see physical checks')
        record['status']='VALIDATED'
        atomic(path,record)
        doc.commitTransaction()
        opened=False
        record['status']='PASS'
    except Exception as exc:
        record['status']='FAIL'
        record['errors'].append(str(exc))
        record['traceback']=traceback.format_exc()
        if opened:
            try:
                doc.abortTransaction()
                opened=False
                doc.recompute()
                restored=equivalent(before,state(doc),tol)
                record['rollback']='COMPLETE' if restored else 'INCOMPLETE'
            except Exception as rollback_exc:
                record['rollback']='FAILED'
                record['errors'].append(str(rollback_exc))
    finally:
        if not old_undo:
            doc.UndoMode=old_undo
    atomic(path,record)
    output=compact({k:v for k,v in record.items() if k not in ('before','after')})
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(output,allow_nan=False)+'\n')
    return output
