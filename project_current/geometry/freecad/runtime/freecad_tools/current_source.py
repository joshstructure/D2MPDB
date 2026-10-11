"""2026-10 source revision. Existing geometry builders remain authoritative.

Native model mutation is transactional and never saves. Source conflicts and
coordination failures remain separate from geometric construction validity.
"""
import hashlib,json,math,re,traceback
from pathlib import Path
from datetime import datetime,timezone
import FreeCAD as App
import Part
from . import bridge
from .geometry import length,result
ROOT=bridge.ROOT;IN=bridge.IN;FT=bridge.FT

def revise_supports(c,m,rows):
    for row in rows:
        if row['id'] in ('EB1','EB2'):
            row['top']=min(bridge.supports.bearing_plane(m,i,b,s,bridge.ft(c,'PadLength'))(s)
                -row['padthickness'] for i,s in row['seats'] for b in range(m.count))-bridge.ft(c,'MinimumPedestalHeight')
            row['bottom']=row['top']-row['depth']
            row['piletop']=row['bottom']+bridge.ft(c,'EndPileEmbedment')
        else:row['piletop']=row['bottom']+bridge.ft(c,'PierPileEmbedment')

def pier_sockets(c,m,row,cap):
    # Selected pipe section is unfilled. Deduct its entire outside envelope;
    # steel occupies the annulus, and the bore remains void through embedment.
    bores=[Part.makeCylinder(c.PileDiameter.Value/2,c.PierPileEmbedment.Value,
        App.Vector((row['station']-m.start)*FT,(j-1.5)*c.PileSpacing.Value,row['bottom']*FT)) for j in range(4)]
    return cap.cut(Part.makeCompound(bores)).removeSplitter()

def validate_supports(doc):
    c=doc.BridgePGL;m=bridge.model(c);checks=[];rows=[];tol=.0254
    for sid in ('EB1','Pier','EB2'):
        cap=bridge.local_shape(doc.getObject('BridgeCap'+sid));bb=cap.BoundBox
        end=sid!='Pier';wanted=(42,212,36) if end else (48,230,36)
        checks.append(result(sid+'_source_cap_section_and_length',all(abs(v-w*IN)<=tol for v,w in zip((bb.XLength,bb.YLength,bb.ZLength),wanted)),actual_in=[bb.XLength/IN,bb.YLength/IN,bb.ZLength/IN],expected_in=wanted))
        removed=4*(18**2 if end else math.pi*10**2)*12/1728
        checks.append(result(sid+'_net_concrete_excludes_embedded_piles',abs(cap.Volume/FT**3-(math.prod(wanted)/1728-removed))<=1e-7,net_ft3=cap.Volume/FT**3,gross_ft3=math.prod(wanted)/1728))
        centers=[]
        for j in range(4):
            pile=bridge.local_shape(doc.getObject(f'BridgePile{sid}P{j+1}'));pb=pile.BoundBox
            centers.append((pb.YMin+pb.YMax)/2)
            checks.append(result(f'{sid}_pile{j+1}_12in_embedment',abs(pb.ZMax-bb.ZMin-12*IN)<=tol,actual_in=(pb.ZMax-bb.ZMin)/IN))
            if not end:
                cylinders=[f.Surface.Radius/IN for f in pile.Faces if isinstance(f.Surface,Part.Cylinder)]
                checks.append(result(f'{sid}_pile{j+1}_nominal_pipe_wall',len(cylinders)==2 and abs(max(cylinders)-min(cylinders)-.625)<=.001,wall_in=max(cylinders)-min(cylinders)))
        clearance=min(centers[0]-(9 if end else 10)*IN-bb.YMin,bb.YMax-centers[-1]-(9 if end else 10)*IN)
        checks.append(result(sid+'_pile_end_clearance',abs(clearance-(16 if end else 15)*IN)<=tol,actual_in=clearance/IN))
        checks.append(result(sid+'_pile_spacing',all(abs(b-a-(54 if end else 60)*IN)<=tol for a,b in zip(centers,centers[1:]))))
        row=bridge.support_data(c)[sid]
        for b in range(2):
            ped=bridge.local_shape(doc.getObject(f'BridgePedestal{sid}B{b+1}'))
            for span,sta in row['seats']:
                x=(sta-m.start)*FT;y=m.offsets[b]*FT
                line=Part.makeLine(App.Vector(x,y,-100000),App.Vector(x,y,100000))
                zs=sorted(v.Point.z for v in ped.section(line).Vertexes)
                pad=bridge.local_shape(doc.getObject(f'BridgePad{sid}S{span+1}B{b+1}'))
                pz=sorted(v.Point.z for v in pad.section(line).Vertexes)
                checks.append(result(f'{sid}_{b+1}_{span}_seat_contacts',len(zs)==2 and len(pz)==2 and abs(zs[0]-bb.ZMax)<=tol and abs(zs[-1]-pz[0])<=tol))
                checks.append(result(f'{sid}_{b+1}_{span}_source_pad_thickness',len(pz)==2 and abs(pz[-1]-pz[0]-2.5625*IN)<=tol))
                rows.append(dict(support=sid,beam=b+1,span=span+1,seat_height_in=(zs[-1]-zs[0])/IN))
                if end:
                    checks.append(result(f'{sid}_{b+1}_six_in_seat_center',abs(zs[-1]-zs[0]-6*IN)<=tol))
                    checks.append(result(f'{sid}_{b+1}_three_in_bearing_offset',abs(abs(x-(bb.XMin+bb.XMax)/2)-3*IN)<=tol))
        if end:
            back=bridge.local_shape(doc.getObject('BridgeBackwall'+sid))
            checks.append(result(sid+'_backwall_nominal_thickness',abs(back.BoundBox.XLength-12*IN)<=tol))
    return {'checks':checks,'pedestal_height_differences':rows}

class CheckProxy(bridge.CheckProxy):
    def execute(self,o):
        super().execute(o)
        extra=validate_supports(o.Document)
        self.last_qa['checks'].extend(extra['checks'])
        o.GeometryStatus='FAIL' if any(r['status']=='FAIL' for r in self.last_qa['checks']) else 'PASS'
        o.Label='Bridge checks - geometry '+o.GeometryStatus+'; coordination '+o.CoordinationStatus

def update(job):
    from .api import document,check_gui,preflight,atomic,compact
    doc=document(job['document']);check_gui(doc);c=doc.BridgePGL
    rid=job['request_id'];path=ROOT/'reports/transactions'/(rid+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    if path.exists():raise ValueError('Inspect existing transaction; do not repeat')
    if getattr(c,'CurrentSourceRevision',0):raise ValueError('Source revision already installed')
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Pending model state')
    if not doc.UndoMode:raise ValueError('Undo required')
    allowed={'EndCapWidth','EndCapDepth','EndCapLength','EndPedestalLength','EndPadThickness','PierPileEmbedment'}
    if set(job['dimensions'])!=allowed:raise ValueError('Unexpected revision controls')
    for value in job['dimensions'].values():length(value,positive=True)
    preflight(c,{n:v for n,v in job['dimensions'].items() if n in c.PropertiesList})
    for src in job['sources']:
        p=Path(src['path']);raw=p.read_bytes()
        if src['hash_basis']=='lf_text':raw=raw.replace(b'\r\n',b'\n')
        if hashlib.sha256(raw).hexdigest()!=src['sha256']:raise ValueError('Source changed: '+str(p))
    targets=[o for o in doc.BridgeGeometryChecks.Components if o.SupportID in ('EB1','EB2') or (o.SupportID=='Pier' and o.ComponentKind in ('Cap','Pile'))]
    changed={o.Name for o in targets}|{'BridgePGL','BridgeGeometryChecks'}
    protected=[o.Name for o in doc.Objects if o.Name not in changed]
    before=bridge.source_state(doc,protected);all_before=bridge.source_state(doc,[o.Name for o in doc.Objects])
    native_shapes={n:doc.getObject(n).dumpPropertyContent('Shape') for n in changed if 'Shape' in doc.getObject(n).PropertiesList}
    camber=[c.Span1Camber.Value,c.Span2Camber.Value]
    proxies={o.Name:o.Proxy for o in targets+[doc.BridgeGeometryChecks]}
    rec=dict(operation='update_bridge_from_current_sources',document=doc.Name,transaction_id=rid,request=job,
        timestamp=datetime.now(timezone.utc).isoformat(),status='PREPARED',report_path=str(path),model_saved=False,
        old_parameters={n:str(getattr(c,n)) if n in c.PropertiesList else None for n in allowed},new_parameters=job['dimensions'],checks=[],errors=[],rollback='NOT NEEDED')
    atomic(path,rec);doc.openTransaction(rid)
    try:
        for n,v in job['dimensions'].items():
            if n not in c.PropertiesList:bridge.prop(c,'App::PropertyLength',n,v,'Current sources')
            else:setattr(c,n,v)
        bridge.prop(c,'App::PropertyInteger','CurrentSourceRevision',1,'Current sources')
        bridge.prop(c,'App::PropertyString','CurrentSourceManifest',json.dumps(job['sources']),'Source')
        bridge.prop(c,'App::PropertyString','SourceRevisionTransaction',rid,'Source')
        bridge.prop(c,'App::PropertyString','SourceExceptions',json.dumps(job['exceptions']),'Source')
        c.NotebookConfiguration=json.dumps(job['notebook_configuration'])
        c.SourceFiles=[s['path'] for s in job['sources']];c.SourceHashes=[s['sha256'] for s in job['sources']]
        c.Assumptions=job['assumptions']
        c.setEditorMode('EndCapPGLDrop',1)
        for o in targets:bridge.ComponentProxy(o);o.touch()
        CheckProxy(doc.BridgeGeometryChecks)
        # The selected source alters supports only. Preserve the retained camber,
        # existing superstructure, curved ramps, terrain and their controls.
        for o in doc.Objects:
            if o.Name not in {t.Name for t in targets}:o.purgeTouched()
        doc.recompute(targets)
        for o in doc.Objects:o.purgeTouched()
        for sid in ('EB1','EB2'):
            doc.getObject('BridgeCap'+sid).Label=sid+' cap - 212 x 42 x 36 in'
            for b in (1,2):doc.getObject(f'BridgePedestal{sid}B{b}').Label=f'{sid} pedestal {b} - 30 x 42 in'
            for o in targets:
                if o.SupportID==sid and o.ComponentKind=='Pad':o.Label=sid+' Type F bearing pad - 2.5625 in'
        doc.BridgeGeometryChecks.touch();doc.recompute([doc.BridgeGeometryChecks])
        for o in doc.Objects:o.purgeTouched()
        qa=doc.BridgeGeometryChecks.Proxy.last_qa;rec['checks']=qa['checks']
        rec['geometry']=qa
        after=bridge.source_state(doc,protected)
        rec['preservation_differences']={n:{k:[v,after[n][k]] for k,v in row.items() if v!=after[n][k]} for n,row in before.items() if row!=after[n]}
        rec['checks']+= [result('protected_native_geometry_links_expressions_exact',before==after),result('both_camber_controls_exact',camber==[c.Span1Camber.Value,c.Span2Camber.Value])]
        if any(r['status']=='FAIL' for r in rec['checks']):raise ValueError('Revision geometry or preservation failed')
        if job.get('test_failure'):raise ValueError('Deliberate rollback test')
        rec['coordination']=doc.BridgeGeometryChecks.Proxy.last_integration
        rec['checks']+=rec['coordination']['checks'];rec['status']='VALIDATED';atomic(path,rec)
        doc.commitTransaction();rec['status']='UPDATED - COORDINATION FAIL' if rec['coordination']['clashes'] else 'UPDATED'
        rec['changed_objects']=sorted(changed)
    except Exception as exc:
        rec.update(status='FAIL',errors=[str(exc)],traceback=traceback.format_exc());doc.abortTransaction()
        for n,p in proxies.items():doc.getObject(n).Proxy=p
        for n,raw in native_shapes.items():doc.getObject(n).restorePropertyContent('Shape',raw)
        for o in doc.Objects:o.purgeTouched()
        restored=bridge.source_state(doc,list(all_before))
        rec['rollback_differences']={n:{k:[v,restored[n][k]] for k,v in row.items() if v!=restored[n][k]} for n,row in all_before.items() if row!=restored[n]}
        rec['rollback']='VERIFIED' if restored==all_before else 'FAILED'
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ('operation','transaction_id','document','status','report_path','rollback')})+'\n')
    out=compact(rec)
    for key in ('geometry','coordination'):out.pop(key,None)
    return out
