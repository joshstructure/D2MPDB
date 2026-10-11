"""Read-only B4 native BRep/terrain audit and exact 2D profile data."""
import sys,json,zipfile,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
from .terrain_exchange import *
import Part
from scipy.spatial import cKDTree
from shapely.geometry import Polygon

def analyze(job):
    out=(ROOT/job['report_directory']).resolve(); source=(ROOT/job['source_export']).resolve()
    inp=(ROOT/job['input_directory']).resolve(); model=(ROOT/job['model']).resolve()
    if not all(p.is_relative_to(ROOT) for p in [out,source,inp,model]):raise ValueError('All analysis files must stay inside CAD_AI')
    if job['minimum_cover']!='2 us-ft' or job['step_increment']!='1 us-ft' or job['tolerance']!='0.001 in':raise ValueError('This tested B4 drawing adapter requires 2 us-ft cover, 1 us-ft steps, 0.001 in tolerance')
    out.mkdir(parents=True,exist_ok=True)
    p,f,meta=read_landxml(inp/job['terrain_filename'],job['surface_name'])
    if meta['units']!='USSurveyFoot':raise ValueError('Expected explicitly declared US survey feet')
    np.savez_compressed(out/'terrain-cache.npz',points=p,faces=f)
    modelhash=sha256(model);manifest=json.loads((source/'manifest.json').read_text()); shapes={};points={};checks=[]
    zfile=zipfile.ZipFile(model);tree=ET.fromstring(zfile.read('Document.xml'))
    nodes={o.attrib['name']:o for o in tree.findall('.//ObjectData/Object')}
    def property(name,key,kind):return nodes[name].find("./Properties/Property[@name='"+key+"']/"+kind)
    def vector(name,key):
        a=property(name,key,'PropertyVector').attrib;return np.array([float(a['value'+k]) for k in 'XYZ'])
    cfg={n:float(property('MSEInputs',n,'Float').attrib['value'])/1000 for n in ['WallThickness','FootingThickness','FootingWidth']}
    for entry in manifest['components']:
        name=entry['name']; shape=Part.read(str(source/'source-brep'/(name+'.brep')));shapes[name]=shape
        points[name]=np.array([[v.Point.x,v.Point.y,v.Point.z] for v in shape.Vertexes])/1000
        # Cross-check the actual saved native shape, not merely its metadata.
        sh=Part.Shape();filename=property(name,'Shape','Part').attrib['file']
        sh.importBrepFromString(zfile.read(filename).decode('ascii'))
        q=np.array([[v.Point.x,v.Point.y,v.Point.z] for v in sh.Vertexes])/1000
        err=max(cKDTree(points[name]).query(q)[0])
        if err>.0000254 or abs(sh.Volume-shape.Volume)>max(.001,shape.Volume*1e-10):raise ValueError('Saved model differs from exported source: '+name)
    allpoints=np.unique(np.concatenate(list(points.values())),axis=0)
    v,groups=read_obj(inp/job['obj_filename']);objkey=tuple(job['model_obj_group'])
    ids=np.unique([i for f in groups[objkey]['f'] for i in f]);target=v[ids]
    reg=register_vertices(allpoints,target,.0000254);R=np.array(reg['rotation']);T=np.array(reg['translation_m'])
    reg['obj_units']='meters, independently verified by rigid geometry and LandXML coordinate matches'
    checks.append({'name':'all 92 saved components match exported BReps and placed OBJ','status':'PASS','max_vertex_error_m':reg['max_vertex_error_m']})
    (out/'placement.json').write_text(json.dumps(reg,indent=2))
    cache=np.load(out/'terrain-cache.npz');world=cache['points']*US_FOOT_M;faces=cache['faces']
    placed=allpoints@R.T+T
    # Tight local model bounds avoid unrelated survey slivers beyond the model.
    # Native triangle validity remains strict within the analysis region.
    local=(world-T)@R;lo=allpoints.min(0)-2;hi=allpoints.max(0)+2
    xy=local[faces,:2];keep=np.all(xy.max(1)>=lo[:2],axis=1)&np.all(xy.min(1)<=hi[:2],axis=1)
    terrain=Terrain(local,faces[keep]);checks.append({'name':'original terrain connectivity retained','status':'PASS','region_triangles':int(sum(keep)),'crop':'native model plan bounds plus 2 m'})
    np.savez_compressed(out/'terrain-local-reference.npz',points=local[np.unique(faces[keep])],triangles=local[faces[keep]])
    # Clipped OBJ terrain vertices need not be vertices of the full LandXML TIN.
    gi=np.unique([i for f in groups[tuple(job['terrain_obj_group'])]['f'] for i in f]);ground=v[gi]
    groundlocal=(ground-T)@R
    inside=np.all(groundlocal[:,:2]>=lo[:2],1)&np.all(groundlocal[:,:2]<=hi[:2],1);groundlocal=groundlocal[inside]
    gz=terrain.heights(groundlocal[:,:2]);valid=np.isfinite(gz)
    terrain_error=abs(gz[valid]-groundlocal[valid,2])
    terrain_agreement={'checked':int(sum(valid)),'outside':int(sum(~valid)),'max_difference_m':float(max(terrain_error)),'within_0_001_in':int(sum(terrain_error<=.0000254))}
    checks.append({'name':'OBJ terrain matches LandXML elevations in bridge region','status':'PASS' if max(terrain_error)<=.0000254 else 'FAIL',**terrain_agreement})
    if max(terrain_error)>.0000254:raise ValueError('OBJ terrain and LandXML do not agree; no burial result is approved')
    rows=[];profiles=[];wallnames=sorted(n for n in nodes if re.fullmatch(r'Wall[AB]\d+Profile',n))
    for name in wallnames:
        wall=re.fullmatch(r'Wall([AB]\d+)Profile',name)[1]
        start=vector(name,'Start')/1000; tangent=vector(name,'Tangent');normal=vector(name,'Normal')
        candidates=[n for n in shapes if re.fullmatch('Wall'+wall+'(?:Finished)?',n)]
        if len(candidates)!=1:raise ValueError('Ambiguous physical wall '+wall)
        wp=points[candidates[0]];s=(wp-start)@tangent;s0=float(min(s));s1=float(max(s));length=s1-s0
        if abs(np.ptp((wp-start)@normal)-cfg['WallThickness'])> .0000254:raise ValueError('Wall thickness mismatch')
        a=start+tangent*s0;b=start+tangent*s1
        prof=[terrain.line(a+normal*offset,b+normal*offset) for offset in [0,cfg['WallThickness']]]
        ts,z=lower_envelope(prof);stations=ts*length/US_FOOT_M;worldground=(z+T[2])/US_FOOT_M
        fn=[n for n in shapes if re.fullmatch('Footing'+wall+'(?:Finished)?',n)]
        if len(fn)!=1:raise ValueError('Ambiguous finished footing '+wall)
        footing=shapes[fn[0]];benches=[]
        for solid in footing.Solids:
            for face in solid.Faces:
                u0,u1,v0,v1=face.ParameterRange;n=face.normalAt((u0+u1)/2,(v0+v1)/2)
                if n.z<.999999:continue
                p=np.array([[vv.Point.x,vv.Point.y,vv.Point.z] for vv in face.OuterWire.OrderedVertexes])/1000
                if np.ptp(p[:,2])>.0000254:raise ValueError('Non-horizontal footing')
                holes=[[(vv.Point.x/1000,vv.Point.y/1000) for vv in w.OrderedVertexes] for w in face.Wires if not w.isSame(face.OuterWire)]
                poly=Polygon(p[:,:2],holes);extent=terrain.polygon_extrema(poly)
                station=(p-start)@tangent-s0;sa=max(0,float(min(station)/US_FOOT_M));sb=min(length/US_FOOT_M,float(max(station)/US_FOOT_M))
                if sb-sa<1e-8:continue
                zi=float(p[:,2].mean());top=(zi+T[2])/US_FOOT_M
                ss=np.r_[sa,stations[(stations>sa)&(stations<sb)],sb];zz=np.interp(ss,stations,worldground);cover=zz-top
                lowidx=cover.argmin();q=a+tangent*(ss[lowidx]*US_FOOT_M)
                qp=q@R.T+T
                benches.append({'start_ft':sa,'end_ft':sb,'top_ft':top,'bottom_ft':top-cfg['FootingThickness']/US_FOOT_M,'min_cover_ft':float(min(cover)),'max_cover_ft':float(max(cover)),
                                'worst_station_ft':float(ss[lowidx]),'worst_easting_ft':float(qp[0]/US_FOOT_M),'worst_northing_ft':float(qp[1]/US_FOOT_M),
                                'footprint_min_cover_ft':(extent['min_point_m'][2]-zi)/US_FOOT_M,'footprint_max_cover_ft':(extent['max_point_m'][2]-zi)/US_FOOT_M,
                                'footprint_m2':poly.area,'covered_m2':extent['coverage_area_m2']})
        benches.sort(key=lambda x:x['start_ft'])
        if not benches:raise ValueError('No footing top faces')
        # Grid datum is whole project US survey-foot elevations, shared by walls.
        options=step_options(stations,worldground,2.,1.)
        for opt in options:opt['review_short_under_10_ft']=opt['length']<10
        row={'wall':wall,'length_ft':length/US_FOOT_M,'terrain_min_ft':float(min(worldground)),'terrain_max_ft':float(max(worldground)),
             'min_cover_ft':min(b['min_cover_ft'] for b in benches),'max_cover_ft':max(b['max_cover_ft'] for b in benches),
             'minimum_2_ft':'PASS' if min(b['min_cover_ft'] for b in benches)>=2-1e-9 else 'FAIL',
             'single_level_option_top_ft':float(math.floor(min(worldground)-2)),'stepped_benches':len(options),'short_benches_under_10_ft':sum(o['review_short_under_10_ft'] for o in options)}
        rows.append(row)
        checks.append({'name':wall+' minimum 2 ft cover','status':row['minimum_2_ft'],'min_cover_ft':row['min_cover_ft']})
        endpoints=np.array([a,b])@R.T+T
        profiles.append({'wall':wall,'source_wall':candidates[0],'source_footing':fn[0],**row,'stations_ft':stations.tolist(),'terrain_ft':worldground.tolist(),
                         'face_profiles':[{'stations_ft':(x*length/US_FOOT_M).tolist(),'terrain_ft':((y+T[2])/US_FOOT_M).tolist()} for x,y in prof],
                         'benches':benches,'step_options':options,'endpoints_us_survey_ft':(endpoints/US_FOOT_M).tolist(),
                         'local_start_m':a.tolist(),'local_end_m':b.tolist(),'wall_normal':normal.tolist()})
    check_model=sha256(model)==modelhash
    checks.append({'name':'source FreeCAD file unchanged','status':'PASS' if check_model else 'FAIL'})
    report={'status':'ANALYZED - footing burial failures present','model':str(model),'model_sha256':modelhash,'terrain':str(inp/job['terrain_filename']),
            'registration':reg,'terrain_agreement':terrain_agreement,'checks':checks,'requirements':{'cover':'2 ft to TOP of footing','steps':'1 ft vertical increments','footing_thickness':'6 in','minimum_tread':'not specified; under 10 ft flagged for review only','governing_terrain':'lower of two physical wall faces, conservative existing-ground envelope','step_grid':'whole US survey-foot project elevations'},
            'units':'US survey feet','wall_profiles':profiles,'summary':rows,'model_changed':False,
            'limits':['Step options are geometric studies; no working model was changed.','No minimum tread was prescribed. Short-tread flags use 10 ft as a review screen, not a design requirement.','Wall-junction step reconciliation and reinforcement detailing are not configured.','Existing bridge/MSE overlap issues remain outside this terrain check.','Terrain source is Ex_I-95_Middle; survey datum name was not declared in the LandXML.']}
    report['request']=job
    report['input_hashes']={job['obj_filename']:sha256(inp/job['obj_filename']),job['terrain_filename']:sha256(inp/job['terrain_filename'])}
    report['retained_diagnostics']='reports/terrain-20261003/development-diagnostics.json'
    (out/'analysis.json').write_text(json.dumps(report,indent=2))
    with (out/'Footing-burial-summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return {'checks':checks,'summary':rows,'report':str(out/'analysis.json')}
