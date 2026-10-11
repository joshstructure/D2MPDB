"""Tested October 2 EndBent.dxf editable PGL-linked end-support revision.

Disposable fixture v5 and the forced-rollback/PGL-dependency test passed.
Working documents are never saved by this helper.
"""
import hashlib,json,re,traceback
from datetime import datetime,timezone
from pathlib import Path
import FreeCAD as App
import Part
from .geometry import length,result
from . import bridge
FT=bridge.FT;IN=bridge.IN;ROOT=bridge.ROOT

def revise_supports(c,m,rows):
    for row in rows:
        if row['id'] not in ['EB1','EB2']:continue
        end=row['id']=='EB2';s=m.end if end else m.start
        row.update(depth=bridge.ft(c,'EndCapDepth'),padthickness=bridge.ft(c,'EndPadThickness'),
                   pilekind='Square concrete',pilecount=4,pilespacing=bridge.ft(c,'EndPileSpacing'),
                   datum=s,top=float(m.pgl(s))-bridge.ft(c,'EndCapPGLDrop'))
        row['bottom']=row['top']-row['depth']
        row['piletop']=row['bottom']+bridge.ft(c,'EndPileEmbedment')
        if end:row['pedstart']=s-row['pedlength'];row['pedend']=s
        else:row['pedstart']=s;row['pedend']=s+row['pedlength']

def square_pile(c,m,row,offset):
    size=bridge.ft(c,'EndPileSize');length_ft=bridge.ft(c,'TrialPileLength')
    return Part.makeBox(size*FT,size*FT,length_ft*FT,
        App.Vector((row['station']-m.start-size/2)*FT,(offset-size/2)*FT,(row['piletop']-length_ft)*FT))

def cut_sockets(c,m,row,cap):
    # Deduct precisely the embedded portion from cap concrete so separate
    # concrete-pile components share an interface rather than duplicate volume.
    piles=[square_pile(c,m,row,(j-1.5)*row['pilespacing']) for j in range(4)]
    return cap.cut(Part.makeCompound(piles)).removeSplitter()

def wall_shape(c,m,row,kind,side):
    rear=row['station']-row['width']/2;front=row['station']+row['width']/2
    half=row['length']/2;cheek=bridge.ft(c,'EndCheekThickness')
    if kind=='Cheek':
        y=-half if side==0 else half-cheek
        top=float(m.pgl(row['datum']))+bridge.ft(c,'EndCheekAbovePGL')
        return Part.makeBox(row['width']*FT,cheek*FT,(top-row['top'])*FT,
            App.Vector((rear-m.start)*FT,y*FT,row['top']*FT))
    a,b=(rear,row['datum']) if row['id']=='EB1' else (row['datum'],front)
    left,right=-half+cheek,half-cheek
    top=lambda y:float(m.deck_top(row['datum'],y))-bridge.ft(c,'EndBackwallDrop')
    x=(a-m.start)*FT
    face=bridge.shapes.plane_polygon([(x,left*FT,row['top']*FT),(x,right*FT,row['top']*FT),
        (x,right*FT,top(right)*FT),(x,0,top(0)*FT),(x,left*FT,top(left)*FT)])
    return face.extrude(App.Vector((b-a)*FT,0,0))

def construct_changes(doc,job):
    c=doc.BridgePGL
    for n,value in job['dimensions'].items():
        if n not in c.PropertiesList:bridge.prop(c,'App::PropertyLength',n,value,'Revised end bents')
        else:setattr(c,n,value)
    bridge.prop(c,'App::PropertyInteger','EndBentRevision',1,'Revised end bents')
    bridge.prop(c,'App::PropertyString','EndBentSource',job['source']['path'],'Source')
    bridge.prop(c,'App::PropertyString','EndBentSourceSHA256',job['source']['sha256'],'Source')
    c.SourceFiles=list(c.SourceFiles)+[job['source']['path']]
    c.SourceHashes=list(c.SourceHashes)+[job['source']['sha256']]
    obsolete=('End-bent pedestals','Type F bearing pads','End-cap transverse','Twelve 20-in','No backwalls')
    c.Assumptions=[s for s in c.Assumptions if not s.startswith(obsolete)]+job['assumptions']
    changed=[]
    for o in doc.BridgeGeometryChecks.Components:
        if o.SupportID not in ['EB1','EB2']:continue
        bridge.ComponentProxy(o);o.touch();changed.append(o)
        bridge.prop(o,'App::PropertyStringList','RevisionSourceHandles',job['source_handles'][o.ComponentKind],'Source')
        if o.ComponentKind=='Pile':
            o.Label=f'{o.SupportID} 18 in square concrete pile {o.PileIndex+1} — 90 ft trial length'
            bridge.prop(o,'App::PropertyString','MaterialDescription','Concrete','Material')
            bridge.color(o,(.66,.69,.71))
        elif o.ComponentKind=='Cap':o.Label=f'{o.SupportID} cap — 17 ft 6 in x 3 ft x 42 in'
        elif o.ComponentKind=='Pad':o.Label=f'{o.SupportID} bearing pad {o.BeamIndex+1} — 2.91 in drawn thickness'
        elif o.ComponentKind=='Pedestal':o.Label=f'{o.SupportID} pedestal {o.BeamIndex+1} — 2 ft x 42 in'
    group=doc.addObject('App::DocumentObjectGroup','BridgeEndBentWalls');group.Label='End-bent backwalls and cheek walls'
    doc.BridgeAssembly.addObject(group);new=[]
    for sid in ['EB1','EB2']:
        cap=doc.getObject('BridgeCap'+sid)
        for kind,b in [('Backwall',0),('Cheek',0),('Cheek',1)]:
            name='Bridge'+kind+sid+(str(b+1) if kind=='Cheek' else '')
            o=doc.addObject('Part::FeaturePython',name);o.Label=sid+' '+kind.lower()+(f' {b+1}' if kind=='Cheek' else '')
            bridge.prop(o,'App::PropertyLink','PGL',c,'Dependencies')
            bridge.prop(o,'App::PropertyLinkList','Sources',[cap],'Dependencies')
            bridge.prop(o,'App::PropertyString','ComponentKind',kind)
            bridge.prop(o,'App::PropertyString','SupportID',sid)
            for n,v in [('SpanIndex',0),('BeamIndex',b),('SeatIndex',0),('PileIndex',0)]:bridge.prop(o,'App::PropertyInteger',n,v)
            bridge.prop(o,'App::PropertyVolume','NetVolume',0,'Quantity');o.setEditorMode('NetVolume',1)
            bridge.prop(o,'App::PropertyStringList','RevisionSourceHandles',job['source_handles'][kind],'Source')
            bridge.ComponentProxy(o);bridge.initialize_display(o);group.addObject(o);new.append(o)
    checker=doc.BridgeGeometryChecks;checker.Components=list(checker.Components)+new
    bridge.CheckProxy(checker);checker.touch()
    # These allowlisted controls affect end bents only. Keep unchanged native
    # geometry intact, including the unvalidated hidden pier-wall reference.
    # No pending user edits are allowed by update(); all protected BReps are
    # independently compared after this scoped recompute.
    affected={o.Name for o in changed+new}|{checker.Name}
    for o in doc.Objects:
        if o.Name not in affected:o.purgeTouched()
    doc.recompute()
    return changed+new

def validate_revision(doc):
    if getattr(doc.BridgePGL,'CurrentSourceRevision',0):
        from .current_source import validate_supports
        return validate_supports(doc)
    c=doc.BridgePGL;m=bridge.model(c);data=bridge.support_data(c);checks=[];rows=[];tol=.0254
    for sid in ['EB1','EB2']:
        row=data[sid];cap=bridge.local_shape(doc.getObject('BridgeCap'+sid))
        gross=row['width']*row['length']*row['depth'];embed=bridge.ft(c,'EndPileSize')**2*bridge.ft(c,'EndPileEmbedment')*4
        checks.append(result(sid+'_net_cap_volume',abs(cap.Volume-(gross-embed)*FT**3)<=cap.Volume*1e-8,net_ft3=cap.Volume/FT**3,gross_ft3=gross))
        expected_top=43.2094 if sid=='EB1' else 43.2214
        checks.append(result(sid+'_written_cap_elevation',abs(cap.BoundBox.ZMax-expected_top*FT)<=tol,actual_ft=cap.BoundBox.ZMax/FT))
        centers=[]
        for j in range(4):
            pile=bridge.local_shape(doc.getObject(f'BridgePile{sid}P{j+1}'));bb=pile.BoundBox
            centers.append((bb.YMin+bb.YMax)/2)
            checks.append(result(f'{sid}_pile{j+1}_embedment',abs(bb.ZMax-cap.BoundBox.ZMin-12*IN)<=tol,actual_in=(bb.ZMax-cap.BoundBox.ZMin)/IN))
            checks.append(result(f'{sid}_pile{j+1}_square_section',len(pile.Faces)==6 and all(abs(s-18*IN)<=tol for s in [bb.XLength,bb.YLength])))
        checks.append(result(sid+'_pile_center_spacing',all(abs(b-a-54*IN)<=tol for a,b in zip(centers[:-1],centers[1:]))))
        edge_clear=min(centers[0]-9*IN-cap.BoundBox.YMin,cap.BoundBox.YMax-centers[-1]-9*IN)
        checks.append(result(sid+'_pile_face_end_clearance',abs(edge_clear-15*IN)<=tol,actual_in=edge_clear/IN))
        back=bridge.local_shape(doc.getObject('BridgeBackwall'+sid));bb=back.BoundBox
        checks.append(result(sid+'_backwall_thickness',abs(bb.XLength-12*IN)<=tol))
        checks.append(result(sid+'_backwall_PGL_drop',abs(float(m.pgl(row['datum']))*FT-bb.ZMax-4*IN)<=tol))
        for j in range(2):
            cheek=bridge.local_shape(doc.getObject(f'BridgeCheek{sid}{j+1}'));cb=cheek.BoundBox
            checks.append(result(f'{sid}_cheek{j+1}_dimensions',abs(cb.YLength-8*IN)<=tol and abs(cb.XLength-36*IN)<=tol))
            ped=bridge.local_shape(doc.getObject(f'BridgePedestal{sid}B{j+1}'))
            span,s=row['seats'][0];plane=bridge.supports.bearing_plane(m,span,j,s,bridge.ft(c,'PadLength'))
            x=(s-m.start)*FT;y=m.offsets[j]*FT
            zs=sorted(v.Point.z for v in ped.section(Part.makeLine(App.Vector(x,y,-100000),App.Vector(x,y,100000))).Vertexes)
            expected=(plane(s)-row['padthickness']-row['top'])*FT
            height=(zs[-1]-zs[0])/IN if len(zs)==2 else -1
            checks.append(result(f'{sid}_pedestal{j+1}_physical_seat_height',len(zs)==2 and abs((zs[-1]-zs[0])-expected)<=tol,actual_in=height,expected_in=expected/IN))
            pad=bridge.local_shape(doc.getObject(f'BridgePad{sid}S{span+1}B{j+1}'))
            pad_z=sorted(v.Point.z for v in pad.section(Part.makeLine(App.Vector(x,y,-100000),App.Vector(x,y,100000))).Vertexes)
            checks.append(result(f'{sid}_pedestal{j+1}_physical_support_contact',len(zs)==2 and len(pad_z)==2 and abs(zs[0]-cap.BoundBox.ZMax)<=tol and abs(zs[-1]-pad_z[0])<=tol))
            rows.append({'support':sid,'beam':j+1,'seat_height_in':height,'drawing_nominal_in':6,'difference_in':height-6})
            checks.append(result(f'{sid}_pedestal{j+1}_backwall_clearance',ped.common(back).Volume==0))
    return {'checks':checks,'pedestal_height_differences':rows}

def update(job):
    from .api import atomic,compact,check_gui,preflight
    rid=job['request_id'];path=ROOT/'reports/transactions'/(rid+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    if path.exists():
        old=json.loads(path.read_text())
        if old['request']!=job:raise ValueError('Request ID reused for different job')
        if old['status'] in ['PREPARED','VALIDATED']:raise RuntimeError('Unknown earlier outcome; inspect before retry')
        return compact(old)
    if hashlib.sha256(Path(job['source']['path']).read_bytes()).hexdigest()!=job['source']['sha256']:raise ValueError('DXF changed since extraction')
    for v in job['dimensions'].values():length(v,positive=True)
    doc=App.getDocument(job['document']);check_gui(doc);c=doc.BridgePGL
    allowed={'EndCapLength','EndCapWidth','EndPedestalLength','EndCapDepth','EndPadThickness',
        'EndCapPGLDrop','EndPileSize','EndPileSpacing','EndPileEmbedment',
        'EndCheekThickness','EndCheekAbovePGL','EndBackwallDrop'}
    if set(job['dimensions'])!=allowed:raise ValueError('Only the complete end-bent revision parameter set is supported')
    pending=[o.Name for o in doc.Objects if 'Touched' in o.State or 'Invalid' in o.State]
    if pending:raise ValueError('Resolve pre-existing pending recomputes before updating: '+str(pending))
    preflight(c,{n:v for n,v in job['dimensions'].items() if n in c.PropertiesList})
    if getattr(c,'EndBentRevision',0):raise ValueError('This revision already exists; inspect before a later revision')
    targets=[o for o in doc.BridgeGeometryChecks.Components if o.SupportID in ['EB1','EB2']]
    protected=[o.Name for o in doc.Objects if o.Name not in [x.Name for x in targets]+['BridgePGL','BridgeGeometryChecks'] and o.TypeId!='App::DocumentObjectGroup']
    protected_state=bridge.source_state(doc,protected);all_before=bridge.source_state(doc,[o.Name for o in doc.Objects])
    old_proxies={o.Name:o.Proxy for o in targets+[doc.BridgeGeometryChecks]};old_names=set(o.Name for o in doc.Objects)
    rec={'operation':'update_end_bents','document':doc.Name,'request':job,'transaction_id':rid,
         'timestamp':datetime.now(timezone.utc).isoformat(),'status':'PREPARED','report_path':str(path),
         'model_saved':False,'checks':[],'errors':[],'warnings':job['assumptions'],
         'old_parameters':{n:str(getattr(c,n)) if n in c.PropertiesList else None for n in job['dimensions']},
         'new_parameters':job['dimensions'],'rollback':'NOT NEEDED'}
    atomic(path,rec);doc.openTransaction(rid)
    try:
        changed=construct_changes(doc,job)
        qa=doc.BridgeGeometryChecks.Proxy.last_qa
        rec.update(qa);extra=validate_revision(doc)
        rec['checks'].extend(extra['checks']);rec['pedestal_height_differences']=extra['pedestal_height_differences']
        after=bridge.source_state(doc,protected)
        rec['preservation_differences']={n:{k:[v,after[n][k]] for k,v in row.items() if v!=after[n][k]} for n,row in protected_state.items() if row!=after[n]}
        rec['checks'].append(result('unaffected_model_preserved',after==protected_state))
        rec['checks'].append(result('end_bent_rendering',all(not bridge.display_state(o)['render_bounds_empty'] for o in changed)))
        if any(r['status']=='FAIL' for r in rec['checks']):raise ValueError('End-bent geometry check failed')
        rec['coordination']=doc.BridgeGeometryChecks.Proxy.last_integration
        rec['checks'].extend(rec['coordination']['checks'])
        rec['status']='VALIDATED';atomic(path,rec)
        doc.commitTransaction();rec['status']='UPDATED — COORDINATION FAIL' if doc.BridgeGeometryChecks.CoordinationStatus=='FAIL' else 'PASS WITH PROVISIONAL PILE LENGTHS'
        rec['geometry_status']='PASS';rec['coordination_status']=doc.BridgeGeometryChecks.CoordinationStatus
        rec['changed_objects']=[o.Name for o in changed]
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc()
        doc.abortTransaction()
        for n,p in old_proxies.items():
            if doc.getObject(n):doc.getObject(n).Proxy=p
        # Abort restores parameters and links. Rebuild the restored PGL first,
        # then only components affected by this end-bent transaction. Rebuilding
        # unrelated shapes needlessly changes their OCC cache state.
        doc.recompute([c])
        affected={o.Name for o in targets}|{'BridgeGeometryChecks'}
        for o in doc.Objects:
            if o.Name not in affected:o.purgeTouched()
        doc.BridgeGeometryChecks.touch();doc.recompute()
        after=bridge.source_state(doc,list(all_before))
        rec['rollback_differences']={n:{k:[v,after[n][k]] for k,v in row.items() if v!=after[n][k]} for n,row in all_before.items() if row!=after[n]}
        rec['rollback']='VERIFIED' if after==all_before and set(o.Name for o in doc.Objects)==old_names else 'FAILED'
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({k:rec[k] for k in ['timestamp','operation','transaction_id','document','status','report_path','model_saved','rollback']})+'\n')
    out=compact(rec)
    for key in ['component_details','contacts','changed_objects']:out.pop(key,None)
    return out
