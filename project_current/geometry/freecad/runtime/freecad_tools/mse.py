"""Editable MSE ramp adapter. Native extrusions and source-linked profiles.

No document is saved. Grades are independently measured from physical faces.
All job dimensions must carry units. Source discrepancies remain explicit.
"""
import json, math, re, traceback, uuid
from datetime import datetime, timezone
from pathlib import Path
import FreeCAD as App
import Part
from .geometry import length, result
ROOT=Path(__file__).resolve().parent.parent

def prop(o,typ,name,value=None,group='MSE'):
    o.addProperty(typ,name,group)
    if value is not None:setattr(o,name,value)

def vector(values):return App.Vector(*[length(v) for v in values])
def grade(value):
    if not isinstance(value,str) or not re.fullmatch(r'-?\d+(\.\d+)?\s*%',value):raise ValueError('Slope requires explicit percent')
    return float(value.replace('%',''))

def height(o,x,y):
    evaluator=getattr(getattr(o,'Proxy',None),'surface_height',None)
    if evaluator:return evaluator(o,x,y)
    a=o.AnchorPoint
    h=height(o.DatumSurface,a.x,a.y) if o.DatumSurface else o.AnchorElevation.Value
    return h+(x-a.x)*o.GradeX/100+(y-a.y)*o.GradeY/100

def wire(points):
    clean=[]
    for p in points:
        if not clean or p.distanceToPoint(clean[-1])>1e-8:clean.append(p)
    if clean[-1].distanceToPoint(clean[0])>1e-8:clean.append(clean[0])
    return Part.makePolygon(clean)

class Serializable:
    def dumps(self):return None
    def loads(self,state):return None

class SurfaceProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        o.PlanCorners=[App.Vector(o.XMin.Value,o.YMin.Value,0),App.Vector(o.XMax.Value,o.YMin.Value,0),App.Vector(o.XMax.Value,o.YMax.Value,0),App.Vector(o.XMin.Value,o.YMax.Value,0)]
        pts=[App.Vector(p.x,p.y,height(o,p.x,p.y)) for p in o.PlanCorners]
        o.Shape=wire(pts)
        o.ComputedCorners=pts

class WallProfileProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        sources={s.Name:s for s in o.SurfaceSources}
        top=[]
        for i,p in enumerate(o.TopControls):
            h=p.z
            if o.TopSourceNames[i]:
                q=o.TopSamplePoints[i];h=height(sources[o.TopSourceNames[i]],q.x,q.y)+o.Inputs.WallUpstand.Value
            top.append(o.Start+o.Tangent*p.x+App.Vector(0,0,h))
        bottom=[o.Start+o.Tangent*p.x+App.Vector(0,0,p.z) for p in o.BaseControls]
        o.Shape=wire(top+list(reversed(bottom)))
        o.ComputedTop=[App.Vector(p.x,0,v.z) for p,v in zip(o.TopControls,top)]

class FootingProfileProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        w=o.WallProfile;cfg=w.Inputs
        shift=w.Normal*(cfg.WallThickness.Value/2-cfg.FootingWidth.Value/2)
        faces=[]
        for a,b in zip(w.BaseControls,w.BaseControls[1:]):
            if b.x-a.x<=1e-8:continue
            if abs(a.z-b.z)>1e-5:raise ValueError('Footing pads require horizontal benches')
            p=w.Start+shift+w.Tangent*a.x+App.Vector(0,0,a.z)
            q=w.Start+shift+w.Tangent*b.x+App.Vector(0,0,b.z)
            dz=App.Vector(0,0,-cfg.FootingThickness.Value)
            faces.append(Part.Face(wire([p,q,q+dz,p+dz])))
        o.Shape=Part.makeCompound(faces) if len(faces)>1 else faces[0]

class FillProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        s=o.Surface;dz=o.Inputs.SlabThickness.Value
        top=[App.Vector(p.x,p.y,height(s,p.x,p.y)-dz) for p in s.PlanCorners]
        bottom=[App.Vector(p.x,p.y,o.BaseElevation.Value) for p in top]
        raw=Part.makeLoft([wire(bottom),wire(top)],True,True)
        tools=[v.Shape for v in o.ConcreteSources if not v.Shape.isNull() and raw.BoundBox.intersect(v.Shape.BoundBox)]
        o.Shape=raw.cut(Part.makeCompound(tools)).removeSplitter() if tools else raw
        o.EnvelopeVolume=raw.Volume
        o.RemovedConcreteVolume=raw.Volume-o.Shape.Volume

class SlopeCheckProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        rows=[];errors=[]
        for slab,expected in zip(o.Slabs,o.RequiredGrades):
            if slab.Shape.isNull():continue
            face=max([f for f in slab.Shape.Faces if abs(f.normalAt(0,0).z)>.5],key=lambda f:f.CenterOfMass.z)
            n=face.normalAt(0,0);gx=-n.x/n.z*100;gy=-n.y/n.z*100
            tx,ty=[float(v) for v in expected.split(',')]
            ok=abs(gx-tx)<1e-7 and abs(gy-ty)<1e-7
            rows.append(slab.Label+': measured X '+format(gx,'.6f')+'%, Y '+format(gy,'.6f')+'% — '+('PASS' if ok else 'FAIL'))
            if not ok:errors.append(slab.Name)
        o.MeasuredSlopes=rows;o.Status='FAIL: '+', '.join(errors) if errors else 'PASS'
        o.Label='Actual surface slopes — '+o.Status

def make_extrusion(doc,name,profile,direction,length_expression):
    o=doc.addObject('Part::Extrusion',name)
    o.Base=profile;o.DirMode='Custom';o.Dir=direction;o.Solid=True
    o.setExpression('LengthFwd',length_expression)
    return o

def color(o,rgb,transparency=0):
    if App.GuiUp:
        o.ViewObject.ShapeColor=rgb;o.ViewObject.LineColor=(.24,.25,.27);o.ViewObject.Transparency=transparency

def construct(doc,job):
    cfg=doc.addObject('App::FeaturePython','MSEInputs');cfg.Label='MSE controls, source and assumptions'
    for k,v in job['parameters'].items():prop(cfg,'App::PropertyLength',k,v,'Dimensions')
    prop(cfg,'App::PropertyLength','WallUpstand','9 in','Dimensions')
    prop(cfg,'App::PropertyString','SourceFile',job['source']['path'],'Provenance')
    prop(cfg,'App::PropertyString','SourceSHA256',job['source']['sha256'],'Provenance')
    prop(cfg,'App::PropertyLength','SurveyEasting',job['coordinate_system']['origin_easting'],'Coordinates')
    prop(cfg,'App::PropertyLength','SurveyNorthing',job['coordinate_system']['origin_northing'],'Coordinates')
    prop(cfg,'App::PropertyAngle','LocalXAxisBearing',job['coordinate_system']['local_x_bearing'],'Coordinates')
    prop(cfg,'App::PropertyStringList','Assumptions',job['assumptions'],'Provenance')
    prop(cfg,'App::PropertyString','ModelStatus','GEOMETRY STUDY; exact labeled grades govern. Review source discrepancies.','Provenance')
    groups={}
    for ramp in ['A','B']:
        g=doc.addObject('App::DocumentObjectGroup','Ramp'+ramp);g.Label='Ramp '+ramp
        groups[ramp]={}
        for key in ['Walls','Footings','WalkingSlabs','Fill','Sources']:
            child=doc.addObject('App::DocumentObjectGroup','Ramp'+ramp+key);child.Label=key if key!='Fill' else 'Schematic retained fill'
            g.addObject(child);groups[ramp][key]=child
    surfaces={};slabs={}
    # Job is supplied in dependency order, checked rather than guessed.
    pending=list(job['surfaces'])
    while pending:
        before=len(pending)
        for sd in pending[:]:
            parent=sd.get('datum_surface')
            if parent and parent not in surfaces:continue
            name=sd['name'];s=doc.addObject('Part::FeaturePython',name+'Surface');SurfaceProxy(s)
            pts=[vector(pt) for pt in sd['corners']]
            prop(s,'App::PropertyVectorList','PlanCorners',[App.Vector(p.x,p.y,0) for p in pts],'Editable geometry')
            for pn,pv in [('XMin',min(p.x for p in pts)),('XMax',max(p.x for p in pts)),('YMin',min(p.y for p in pts)),('YMax',max(p.y for p in pts))]:prop(s,'App::PropertyDistance',pn,pv,'Editable geometry')
            s.setEditorMode('PlanCorners',1)
            prop(s,'App::PropertyVector','AnchorPoint',vector(sd['anchor']),'Editable geometry')
            prop(s,'App::PropertyLength','AnchorElevation',sd['anchor'][2],'Editable geometry')
            prop(s,'App::PropertyFloat','GradeX',grade(sd['grades'][0]),'Grades (%)')
            prop(s,'App::PropertyFloat','GradeY',grade(sd['grades'][1]),'Grades (%)')
            prop(s,'App::PropertyLink','DatumSurface',surfaces.get(parent),'Source links')
            prop(s,'App::PropertyVectorList','ComputedCorners',[],'Measured geometry');s.setEditorMode('ComputedCorners',1)
            prop(s,'App::PropertyVectorList','ReferenceSpotCorners',[vector(pt) for pt in sd['reference_corners']],'Provenance')
            prop(s,'App::PropertyStringList','DXFHandles',sd['source_handles'],'Provenance')
            surfaces[name]=s;groups[name[0]]['Sources'].addObject(s)
            slab=make_extrusion(doc,name+'Slab',s,App.Vector(0,0,-1),'MSEInputs.SlabThickness')
            slab.Label=name.replace('_',' ')+' | '+sd['grades'][0]+' X, '+sd['grades'][1]+' Y'
            groups[name[0]]['WalkingSlabs'].addObject(slab);color(slab,(.59,.72,.79));slabs[name]=slab
            pending.remove(sd)
        if len(pending)==before:raise ValueError('Cyclic or missing surface datum links')
    walls={};footings={};profiles={}
    for wd in job['walls']:
        name=wd['name'];w=doc.addObject('Part::FeaturePython','Wall'+name+'Profile');WallProfileProxy(w)
        start=App.Vector(length(wd['start'][0]),length(wd['start'][1]),0)
        tangent=App.Vector(1,0,0) if wd['axis']=='x' else App.Vector(0,1,0)
        normal=App.Vector(0,wd['outward'],0) if wd['axis']=='x' else App.Vector(wd['outward'],0,0)
        prop(w,'App::PropertyLink','Inputs',cfg,'Source links')
        prop(w,'App::PropertyVector','Start',start,'Editable geometry')
        if name in ['A2','A3']:
            # Resolve micrometre-scale DXF endpoint disagreement with an exact
            # shared nominal face. No tolerance or dimension is enlarged.
            w.setExpression('Start.y','A_ApproachSurface.YMin - MSEInputs.WallThickness')
            prop(w,'App::PropertyLength','OriginalDXFStartY',start.y,'Provenance')
        prop(w,'App::PropertyVector','Tangent',tangent,'Editable geometry')
        prop(w,'App::PropertyVector','Normal',normal,'Editable geometry')
        prop(w,'App::PropertyVectorList','TopControls',[App.Vector(length(t),0,length(z)) for t,z in wd['top']],'Editable geometry')
        prop(w,'App::PropertyVectorList','BaseControls',[App.Vector(length(t),0,length(z)) for t,z in wd['base']],'Editable geometry')
        mappings=wd['top_surface_mapping'];names=[m['surface']+'Surface' if m else '' for m in mappings]
        prop(w,'App::PropertyStringList','TopSourceNames',names,'Source links')
        prop(w,'App::PropertyVectorList','TopSamplePoints',[App.Vector(length(m['point'][0]),length(m['point'][1]),0) if m else App.Vector() for m in mappings],'Source links')
        prop(w,'App::PropertyLinkList','SurfaceSources',list({surfaces[m['surface']] for m in mappings if m}),'Source links')
        prop(w,'App::PropertyVectorList','ComputedTop',[],'Measured geometry');w.setEditorMode('ComputedTop',1)
        prop(w,'App::PropertyStringList','DXFHandles',wd['source_handles'],'Provenance')
        prop(w,'App::PropertyString','Interpretation',wd['notes'],'Provenance')
        panel=make_extrusion(doc,'Wall'+name,w,normal,'MSEInputs.WallThickness');panel.Label='MSE wall '+name
        color(panel,(.78,.78,.73));groups[name[0]]['Walls'].addObject(panel);walls[name]=panel;profiles[name]=w
        fp=doc.addObject('Part::FeaturePython','Footing'+name+'Profile');FootingProfileProxy(fp)
        prop(fp,'App::PropertyLink','WallProfile',w,'Source links')
        footing=make_extrusion(doc,'Footing'+name,fp,normal,'MSEInputs.FootingWidth');footing.Label=name+' | 6 in leveling footing'
        color(footing,(.47,.48,.46));groups[name[0]]['Footings'].addObject(footing);footings[name]=footing
        groups[name[0]]['Sources'].addObject(w);groups[name[0]]['Sources'].addObject(fp)
    doc.recompute()
    # Join intersections with native, source-linked cuts, retaining every
    # original extrusion. Finished parts partition the same material union.
    ordered=[(n[0],'Footings',o) for n,o in footings.items()]+[(n[0],'Walls',o) for n,o in walls.items()]+[(n[0],'WalkingSlabs',o) for n,o in slabs.items()]
    finished=[];nominal=[];final_by_source={}
    for ramp,group,raw in ordered:
        intersecting=[]
        for previous in finished:
            if raw.Shape.BoundBox.intersect(previous.Shape.BoundBox) and raw.Shape.common(previous.Shape).Volume>0:
                intersecting.append(previous)
        final=raw
        if intersecting:
            tool=doc.addObject('Part::Compound',raw.Name+'JointTools');tool.Links=intersecting
            final=doc.addObject('Part::Cut',raw.Name+'Finished');final.Base=raw;final.Tool=tool;final.Refine=True
            final.Label=raw.Label
            groups[ramp][group].removeObject(raw);groups[ramp]['Sources'].addObject(raw);groups[ramp]['Sources'].addObject(tool)
            groups[ramp][group].addObject(final)
            doc.recompute()
            color(final,(.47,.48,.46) if group=='Footings' else ((.78,.78,.73) if group=='Walls' else (.59,.72,.79)))
        nominal.append(raw);finished.append(final);final_by_source[raw.Name]=final
    assembly=doc.addObject('App::FeaturePython','MSEAssembly');assembly.Label='Concrete source and joint relationships'
    prop(assembly,'App::PropertyLinkList','NominalConcrete',nominal,'Source links')
    prop(assembly,'App::PropertyLinkList','FinishedConcrete',finished,'Source links')
    concrete=finished
    sc=doc.addObject('App::FeaturePython','MSESlopeChecks');SlopeCheckProxy(sc)
    prop(sc,'App::PropertyLinkList','Slabs',[final_by_source[sd['name']+'Slab'] for sd in job['surfaces']],'Source links')
    prop(sc,'App::PropertyStringList','RequiredGrades',[','.join(str(grade(v)) for v in sd['grades']) for sd in job['surfaces']],'Checks')
    prop(sc,'App::PropertyStringList','MeasuredSlopes',[],'Checks');sc.setEditorMode('MeasuredSlopes',1)
    prop(sc,'App::PropertyString','Status','NOT RUN','Checks');sc.setEditorMode('Status',1)
    fills={}
    for name,s in surfaces.items():
        f=doc.addObject('Part::FeaturePython',name+'Fill');FillProxy(f)
        prop(f,'App::PropertyLink','Surface',s,'Source links');prop(f,'App::PropertyLink','Inputs',cfg,'Source links')
        prop(f,'App::PropertyLength','BaseElevation','21.708 ft' if name.startswith('A') else '21.172 ft','Envelope')
        prop(f,'App::PropertyLinkList','ConcreteSources',[v for v in concrete if v.Name.startswith('Wall'+name[0]) or v.Name.startswith('Footing'+name[0])],'Source links')
        prop(f,'App::PropertyVolume','EnvelopeVolume',0,'Quantities');prop(f,'App::PropertyVolume','RemovedConcreteVolume',0,'Quantities')
        prop(f,'App::PropertyString','Limitation','Schematic envelope only; no geotechnical reinforcement, excavation or terrain model.','Provenance')
        groups[name[0]]['Fill'].addObject(f);f.Label=name.replace('_',' ')+' fill envelope';color(f,(.72,.57,.37),60);fills[name]=f
    doc.recompute()
    if App.GuiUp:
        for g in groups.values():
            for o in g['Sources'].Group:o.ViewObject.Visibility=False
        for o in finished+list(fills.values()):o.ViewObject.Visibility=True
    return {'inputs':cfg,'walls':walls,'profiles':profiles,'footings':footings,'surfaces':surfaces,'slabs':slabs,'fills':fills}

def polygon_area(points):
    return abs(sum(a.x*b.z-b.x*a.z for a,b in zip(points,points[1:]+points[:1])))/2

def validate(doc,job,objects=None):
    cfg=doc.MSEInputs;tol=length(job.get('tolerance','0.001 in'));checks=[];slope_rows=[];spot_rows=[]
    solids=[]
    for wd in job['walls']:
        n=wd['name'];w=doc.getObject('Wall'+n);p=doc.getObject('Wall'+n+'Profile');f=doc.getObject('Footing'+n)
        shape=w.Shape;fshape=f.Shape
        checks.append(result(n+'_wall_valid',shape.isValid() and len(shape.Solids)==1 and shape.Volume>0))
        boundary=list(p.ComputedTop)+list(reversed(p.BaseControls))
        expected=polygon_area(boundary)*cfg.WallThickness.Value
        checks.append(result(n+'_wall_volume',abs(shape.Volume-expected)<=max(1e-5,expected*1e-9),measured_mm3=shape.Volume,expected_mm3=expected))
        cross=[App.Vector(v.Point).dot(p.Normal) for v in shape.Vertexes]
        checks.append(result(n+'_wall_thickness',abs(max(cross)-min(cross)-cfg.WallThickness.Value)<=tol,measured_in=(max(cross)-min(cross))/25.4))
        benches=[(a,b) for a,b in zip(p.BaseControls,p.BaseControls[1:]) if b.x>a.x+1e-8]
        volume=sum((b.x-a.x)*cfg.FootingWidth.Value*cfg.FootingThickness.Value for a,b in benches)
        checks.append(result(n+'_footing_valid',fshape.isValid() and len(fshape.Solids)==len(benches),solids=len(fshape.Solids),benches=len(benches)))
        checks.append(result(n+'_footing_volume',abs(fshape.Volume-volume)<=max(1e-5,volume*1e-9)))
        for i,solid in enumerate(fshape.Solids):
            bb=solid.BoundBox
            cross=[v.Point.dot(p.Normal) for v in solid.Vertexes]
            checks.append(result(n+'_footing_'+str(i)+'_dimensions',abs(bb.ZLength-cfg.FootingThickness.Value)<=tol and abs(max(cross)-min(cross)-cfg.FootingWidth.Value)<=tol,thickness_in=bb.ZLength/25.4,width_in=(max(cross)-min(cross))/25.4))
        solids.extend([w,f])
    assembly=doc.MSEAssembly
    finished_map={raw.Name:final for raw,final in zip(assembly.NominalConcrete,assembly.FinishedConcrete)}
    for sd in job['surfaces']:
        n=sd['name'];s=doc.getObject(n+'Surface');slab=finished_map[n+'Slab'];shape=slab.Shape
        checks.append(result(n+'_slab_valid',shape.isValid() and len(shape.Solids)==1 and shape.Volume>0))
        # Select a planar top BRep face by geometry, not by stored slope labels.
        faces=[f for f in shape.Faces if abs(f.normalAt(0,0).z)>.5]
        top=max(faces,key=lambda f:f.CenterOfMass.z)
        normal=top.normalAt(0,0);gx=-normal.x/normal.z*100;gy=-normal.y/normal.z*100
        wantx,wanty=[grade(v) for v in sd['grades']]
        grade_ok=abs(gx-wantx)<1e-7 and abs(gy-wanty)<1e-7
        checks.append(result(n+'_physical_slopes',grade_ok,actual_x_percent=gx,actual_y_percent=gy,required_x_percent=wantx,required_y_percent=wanty))
        verts=[v.Point for v in top.Vertexes]
        xlen=max(p.x for p in verts)-min(p.x for p in verts);ylen=max(p.y for p in verts)-min(p.y for p in verts)
        slope_rows.append({'surface':n,'status':'PASS' if grade_ok else 'FAIL','longitudinal_axis':'X' if abs(wantx)==5 else ('Y' if abs(wanty)==5 else 'Landing'),'actual_x_percent':gx,'actual_y_percent':gy,'required_x_percent':wantx,'required_y_percent':wanty,'horizontal_run_x_ft':xlen/304.8,'physical_rise_x_ft':xlen*gx/100/304.8,'horizontal_run_y_ft':ylen/304.8,'physical_rise_y_ft':ylen*gy/100/304.8,'method':'Physical top-face plane normal and BRep vertex horizontal extents'})
        plan_area=xlen*ylen;expected=plan_area*cfg.SlabThickness.Value
        nominal=doc.getObject(n+'Slab').Shape
        checks.append(result(n+'_slab_volume_thickness',abs(nominal.Volume-expected)<=max(1e-5,expected*1e-9),vertical_thickness_in=nominal.Volume/plan_area/25.4))
        # Face plane, independently queried above, provides actual model elevations.
        refpoint=verts[0]
        for i,q in enumerate(s.ReferenceSpotCorners):
            measured=refpoint.z-(normal.x*(q.x-refpoint.x)+normal.y*(q.y-refpoint.y))/normal.z
            delta=measured-q.z
            spot_rows.append({'surface':n,'corner':i,'reference_ft':q.z/304.8,'physical_ft':measured/304.8,'delta_in':delta/25.4,'status':'PASS' if abs(delta)<=tol else 'DIFFERS - exact labeled slope governs'})
        fill=doc.getObject(n+'Fill')
        checks.append(result(n+'_fill_valid',fill.Shape.isValid() and fill.Shape.Volume>0,solid_count=len(fill.Shape.Solids)))
        solids.append(slab)
    # Check shared slab-edge continuity using independent top BRep vertices.
    for sd in job['surfaces']:
        if not sd.get('datum_surface'):continue
        a=doc.getObject(sd['name']+'Slab').Shape;b=doc.getObject(sd['datum_surface']+'Slab').Shape
        dist=a.distToShape(b)[0]
        checks.append(result(sd['name']+'_landing_contact',dist<=tol,distance_in=dist/25.4))
    state_bad=[o.Name for o in doc.Objects if any('Error' in str(v) or 'Invalid' in str(v) for v in o.State)]
    checks.append(result('object_states',not state_bad,invalid_objects=state_bad))
    checks.extend({'name':n,'status':'NOT CONFIGURED'} for n in ['structural_design','reinforcement_cover','geotechnical_reinforcement','terrain_and_excavation','code_compliance','drawing_sheets'])
    # Shared footing junctions are intended intersecting concrete. Report their
    # volume explicitly instead of presenting summed volume as a net quantity.
    interfaces=[]
    for i,a in enumerate(solids):
        for b in solids[i+1:]:
            if not a.Shape.BoundBox.intersect(b.Shape.BoundBox):continue
            common=a.Shape.common(b.Shape).Volume
            if common>0:interfaces.append({'a':a.Name,'b':b.Name,'overlap_in3':common/25.4**3})
    final_clashes=[]
    for i,a in enumerate(assembly.FinishedConcrete):
        checks.append(result(a.Name+'_finished_valid',a.Shape.isValid() and a.Shape.Volume>0))
        for b in assembly.FinishedConcrete[i+1:]:
            if not a.Shape.BoundBox.intersect(b.Shape.BoundBox):continue
            volume=a.Shape.common(b.Shape).Volume
            if volume>0:final_clashes.append({'a':a.Name,'b':b.Name,'overlap_in3':volume/25.4**3})
    checks.append(result('finished_concrete_no_positive_overlap',not final_clashes,clashes=final_clashes))
    annotation_rows=[]
    measured={r['surface']:r for r in slope_rows}
    for annotation in job.get('slope_annotations',[]):
        r=measured[annotation['surface']];values=[abs(r['actual_'+axis.lower()+'_percent']) for axis in annotation['axes']]
        ok=all(abs(v-annotation['required_percent'])<1e-7 for v in values)
        annotation_rows.append(dict(annotation,measured_percent=values,status='PASS' if ok else 'FAIL'))
        checks.append(result('DXF_slope_'+annotation['handle'],ok,source_text=annotation['text'],surface=annotation['surface'],axes=annotation['axes'],measured_percent=values))
    checks.append(result('all_24_source_slope_annotations_checked',len(annotation_rows)==24,checked=len(annotation_rows)))
    return {'checks':checks,'slopes':slope_rows,'source_slope_annotations':annotation_rows,'spot_elevation_differences':spot_rows,'concrete_intersections':interfaces,'finished_concrete_clashes':final_clashes,'unconfigured':'No imposed minimum structural clearance. Raw junction intersections are resolved by editable native cuts; finished visible concrete is checked independently.'}

def create(job):
    from .api import atomic,compact,check_gui
    name=job.get('document');rid=job.get('request_id',uuid.uuid4().hex)
    if not isinstance(name,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',name):raise ValueError('Explicit document Name required')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    path=ROOT/'reports/transactions'/(rid+'.json')
    if path.exists():
        old=json.loads(path.read_text())
        if old['request']!=job:raise ValueError('Request ID reused for different job')
        if old['status'] in ['PREPARED','VALIDATED']:raise RuntimeError('Prior outcome unknown; inspect state before retry')
        return compact(old)
    if name in App.listDocuments():raise ValueError('Creation requires a new document')
    for value in job['parameters'].values():length(value,positive=True)
    rec={'timestamp':datetime.now(timezone.utc).isoformat(),'operation':'create_mse_ramps','request':job,'transaction_id':rid,'document':name,'status':'PREPARED','report_path':str(path),'checks':[],'warnings':job['assumptions'],'model_saved':False,'errors':[],'rollback':'NOT NEEDED'}
    atomic(path,rec);doc=None;prior=App.ActiveDocument.Name if App.ActiveDocument else None
    try:
        if App.ActiveDocument:check_gui(App.ActiveDocument)
        doc=App.newDocument(name);doc.Label='B4 MSE ramps - editable geometry study';doc.UndoMode=1;doc.openTransaction(rid)
        objects=construct(doc,job)
        qa=validate(doc,job,objects);rec.update(qa)
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Physical geometry or slope validation failed')
        rec['status']='VALIDATED';atomic(path,rec)
        doc.commitTransaction();rec['status']='PASS WITH SOURCE DISCREPANCIES'
        rec['object_count']=len(doc.Objects);rec['wall_count']=len(job['walls']);rec['slab_count']=len(job['surfaces'])
        rec['footing_solid_count']=sum(len(o.Shape.Solids) for o in objects['footings'].values())
        rec['max_spot_elevation_difference_in']=max(abs(v['delta_in']) for v in qa['spot_elevation_differences'])
        rec['concrete_intersection_count']=len(qa['concrete_intersections'])
        if App.GuiUp:
            import FreeCADGui as Gui
            Gui.activeDocument().activeView().viewAxonometric();Gui.activeDocument().activeView().fitAll()
        if job.get('disposable'):
            App.closeDocument(name)
            if prior:App.setActiveDocument(prior)
            rec['disposable_closed']=True
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc()
        if doc and name in App.listDocuments():
            App.closeDocument(name);rec['rollback']='NEW DOCUMENT CLOSED'
            if prior:App.setActiveDocument(prior)
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:v for k,v in compact(rec).items() if k not in ['slopes','spot_elevation_differences','concrete_intersections']})+'\n')
    out=compact(rec)
    for k in ['slopes','source_slope_annotations','spot_elevation_differences','concrete_intersections','finished_concrete_clashes','unconfigured']:out.pop(k,None)
    return out
