"""Apply a verified notebook camber export to a disposable native bridge file.

Uses existing parametric bridge/cage controllers and checks their output against
the notebook's exported polynomial geometry. Never edits an open working model.
"""
from pathlib import Path
import copy,hashlib,json,shutil,traceback
import FreeCAD as App
import Part
import numpy as np
from . import bridge,current_source,cap_cages,design_steel,native_archive
from .geometry import result
from .mse import prop

FT=304.8
IN=25.4

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_payload(path):
    data=json.loads(Path(path).read_text())
    expected=data.pop('payload_sha256')
    actual=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if actual!=expected or data['schema']!='d2mpdb.notebook-cad-geometry' or data['schema_version']!=1:
        raise ValueError('Notebook export identity/schema mismatch')
    data['payload_sha256']=expected
    return data

def parity(doc,payload):
    """Compare independent notebook coefficients with native engine and solids."""
    c=doc.BridgePGL;m=bridge.model(c);checks=[]
    def check(name,condition,**kw):checks.append(result(name,bool(condition),**kw))
    for index,piece in enumerate(payload['geometry']['pieces']):
        span=next(i for i,row in m.spans.iterrows() if row['id']==piece['span'])
        for t in (0.,.2113248654,.5,.7886751346,1.):
            s=piece['start']+t*(piece['end']-piece['start']);actual=m.evaluate([s],span)
            for key,co in piece['fields'].items():
                a,b,q=np.asarray(co);expected=a+b*t+q*t*t
                check(f'notebook_piece_{index}_{t}_{key}',np.allclose(actual[key][0],expected,rtol=0,atol=1e-9))
    check('notebook_support_drop',abs(m.support_drop-payload['support_drop_ft'])<1e-9)
    for support in payload['geometry']['supports']:
        sid={'Pier':'Pier','End Bent 1':'EB1','End Bent 2':'EB2'}[support['name']]
        row=bridge.support_data(c)[sid];cap=bridge.local_shape(doc.getObject('BridgeCap'+sid));bb=cap.BoundBox
        check(sid+'_native_cap_top_matches_notebook',abs(bb.ZMax/FT-support['top'])<1e-8)
        check(sid+'_native_cap_bottom_matches_notebook',abs(bb.ZMin/FT-(support['top']-support['depth']))<1e-8)
        check(sid+'_native_cap_station_matches_notebook',abs(m.start+(bb.XMin+bb.XMax)/2/FT-support['station'])<1e-8)
        for pile in support['solid_geometry']['piles']:
            native=bridge.local_shape(doc.getObject(f'BridgePile{sid}P{pile["number"]}')).BoundBox
            check(f'{sid}_pile_{pile["number"]}_native_cutoff',abs(native.ZMax/FT-pile['cutoff'])<1e-8)
    # Physical beam sections independently confirm the cambered solids.
    for span,(start,end) in enumerate(m.bearing_limits):
        for b in range(m.count):
            beam=bridge.local_shape(doc.getObject(f'BridgeBeamS{span+1}B{b+1}'))
            for t in (0.,.37,.5,.83,1.):
                station=start+(end-start)*t
                x=(station-m.start)*FT
                plane=Part.Face(Part.makePolygon([App.Vector(x,-5000,-30000),App.Vector(x,5000,-30000),App.Vector(x,5000,30000),App.Vector(x,-5000,30000),App.Vector(x,-5000,-30000)]))
                cut=beam.common(plane);expected=m.evaluate([station],span)
                check(f'beam_{span}_{b}_{t}_native_bottom',cut.Area>0 and abs(cut.BoundBox.ZMin/FT-expected['bottom'][0,b])<1e-8)
                check(f'beam_{span}_{b}_{t}_native_top',cut.Area>0 and abs(cut.BoundBox.ZMax/FT-expected['top'][0,b])<1e-8)
    return checks

def update_file(source,output_dir,payload_file,expected_source_hash,request_id):
    source=Path(source).resolve();out=Path(output_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    payload=read_payload(payload_file)
    if sha(source)!=expected_source_hash:raise ValueError('Source changed before candidate preparation')
    working=out/'CamberWorking.FCStd';raw=out/'CamberNativeCandidate.FCStd';final=out/'CamberVerifiedCandidate.FCStd'
    if any(p.exists() for p in (working,raw,final,out/'transaction.json')):raise ValueError('Inspect existing transaction/candidate before retry')
    rec={'transaction_id':request_id,'operation':'notebook_camber_file_update','status':'PREPARED','source':str(source),'source_sha256':expected_source_hash,'payload_sha256':payload['payload_sha256'],'notebook_model_id':payload['model_id'],'checks':[]}
    def save_record():(out/'transaction.json').write_text(json.dumps(rec,indent=2,default=float)+'\n')
    save_record();shutil.copy2(source,working);doc=App.openDocument(str(working))
    try:
        c=doc.BridgePGL
        before=bridge.source_state(doc,[o.Name for o in doc.Objects])
        components=list(doc.BridgeGeometryChecks.Components)
        mutable={c.Name,'BridgeGeometryChecks','BridgeConcreteSchedule','BridgeSources','WallSteelChecks'}
        mutable.update(o.Name for o in components if o.ComponentKind!='Deck')
        mutable.update(o.Name for o in doc.Objects if o.Name.startswith(('Cage','SteelBridge')))
        protected=set(before)-mutable
        rec['retained_objects']=sorted(protected)
        rec['before_state']=before
        rec['old_cambers_in']=[c.Span1Camber.Value/IN,c.Span2Camber.Value/IN]
        c.NotebookConfiguration=json.dumps(payload['configuration'])
        for i in (0,1):setattr(c,f'Span{i+1}Camber',str(payload['configuration']['spans'][i]['camber_in'])+' in')
        prop(c,'App::PropertyString','NotebookGeometryPayloadSHA256',payload['payload_sha256'],'Source')
        prop(c,'App::PropertyString','NotebookGeometryModelID',payload['model_id'],'Source')
        prop(c,'App::PropertyString','NotebookGeometryExport','evidence/2026-10-12-cambers/notebook-geometry.json','Source')
        old_hashes=['b514ba288a859054bae7e8556ce978bcf1c4310bc6820517759d1ed73300a76f','fa6693a473770e088665283631b099a0b61a0cabecac1f577ee9473b3569585b']
        new_hashes=[v['source_sha256'] for v in payload['configuration']['camber_basis']]
        c.SourceHashes=[new_hashes[old_hashes.index(h)] if h in old_hashes else h for h in c.SourceHashes]
        c.Assumptions=[s for s in c.Assumptions if 'camber' not in s.lower()]+['Cambers updated from the 12 October Mathcad saved results through the geometry notebook; native Mathcad analysis not rerun.']
        # Execute tested controllers in dependency order; avoid unrelated ramp rebuilds.
        c.Proxy.execute(c)
        for o in components:
            if o.ComponentKind!='Deck':o.Proxy.execute(o)
        for sid in ('EB1','Pier','EB2'):
            inp=doc.getObject('Cage'+sid+'Inputs');inp.Proxy.execute(inp)
            q=doc.getObject('Cage'+sid+'Quantities')
            for b in q.Bars:b.Base.Proxy.execute(b.Base);b.Proxy.execute(b)
            q.Proxy.execute(q)
        walls=[o for o in doc.Objects if isinstance(getattr(o,'Proxy',None),design_steel.WallInputsProxy)]
        for inp in walls:
            inp.Proxy.execute(inp);q=doc.getObject(inp.Prefix+'Quantities')
            for b in q.Bars:b.Base.Proxy.execute(b.Base);b.Proxy.execute(b)
            q.Proxy.execute(q)
        for o in doc.Objects:
            if o.Name in protected or o.Name in mutable:o.purgeTouched()
        sheets=[doc.getObject('BridgeConcreteSchedule')]+[doc.getObject('Cage'+s+'Schedule') for s in ('EB1','Pier','EB2')]+[doc.getObject(o.Prefix+'Schedule') for o in walls]
        for sheet in sheets:sheet.touch()
        doc.recompute(sheets)
        doc.BridgeGeometryChecks.Proxy.execute(doc.BridgeGeometryChecks)
        rec['geometry']=doc.BridgeGeometryChecks.Proxy.last_qa
        rec['coordination']=doc.BridgeGeometryChecks.Proxy.last_integration
        rec['checks']+=rec['geometry']['checks']+parity(doc,payload)
        for sid in ('EB1','Pier','EB2'):
            inp=doc.getObject('Cage'+sid+'Inputs')
            rec['checks']+=cap_cages.geometry_checks(inp)['checks']
            doc.getObject('Cage'+sid+'Checks').Proxy.execute(doc.getObject('Cage'+sid+'Checks'))
        for inp in walls:rec['checks']+=design_steel.wall_geometry_checks(inp)
        rec['wall_detailing']=design_steel.wall_detail_checks(doc,walls)
        # Preserve the original snapshot as historical, explicitly mark its currency.
        if doc.getObject('WallSteelChecks'):
            prop(doc.WallSteelChecks,'App::PropertyString','CamberUpdateReview',json.dumps(rec['wall_detailing']),'12 October camber update')
        rec['checks'].append(result('protected_geometry_links_placements_exact',bridge.source_state(doc,sorted(protected))=={n:before[n] for n in sorted(protected)}))
        rec['checks'].append(result('native_object_names_preserved',set(before)=={o.Name for o in doc.Objects}))
        rec['new_cambers_in']=[c.Span1Camber.Value/IN,c.Span2Camber.Value/IN]
        if any(x['status']=='FAIL' for x in rec['checks']):raise ValueError('Candidate geometry/parity/preservation check failed')
        for o in doc.Objects:o.purgeTouched()
        doc.saveAs(str(raw));rec['status']='NATIVE_CANDIDATE_BUILT'
    except Exception:
        rec['status']='FAIL';rec['traceback']=traceback.format_exc()
    finally:
        App.closeDocument(doc.Name);rec['source_unchanged']=sha(source)==expected_source_hash;save_record()
    if rec['status']=='FAIL':return rec
    rec['native_preservation']=native_archive.preserve(source,raw,final,rec['retained_objects'],expected_source_hash)
    rec['candidate']=str(final);rec['candidate_sha256']=sha(final);rec['status']='STAGED_FOR_COLD_REOPEN';save_record()
    return rec
