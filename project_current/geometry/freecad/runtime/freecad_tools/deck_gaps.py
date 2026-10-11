"""Editable deck-end clearance with fixed PGL/front-face-of-backwall datums."""
import json,re,traceback
from datetime import datetime,timezone
import FreeCAD as App
import Part
from . import bridge
from .geometry import length,result
ROOT=bridge.ROOT;FT=bridge.FT;IN=bridge.IN

def measure(c,objects):
    """Measure actual end faces and solid separation, independent of labels."""
    m=bridge.model(c);wanted=c.DeckEndClearance.Value;tol=.0254
    checks=[];rows=[]
    for sid,dn,bn,end in [('EB1','BridgeDeckS1','BridgeBackwallEB1',False),('EB2','BridgeDeckS2','BridgeBackwallEB2',True)]:
        deck=bridge.local_shape(objects[dn]);back=bridge.local_shape(objects[bn])
        d=deck.BoundBox;b=back.BoundBox
        dx=d.XMax if end else d.XMin;bx=b.XMin if end else b.XMax
        gap=bx-dx if end else dx-bx
        distance=deck.distToShape(back)[0]
        datum=(m.end-m.start)*FT if end else 0.
        checks.append(result(sid+'_physical_deck_FFBW_gap',abs(gap-wanted)<=tol,actual_in=gap/IN,required_in=wanted/IN))
        checks.append(result(sid+'_solid_backwall_clearance',abs(distance-wanted)<=tol and deck.common(back).Volume==0,actual_in=distance/IN))
        checks.append(result(sid+'_FFBW_station',abs(bx-datum)<=tol,actual_station_ft=m.start+bx/FT))
        faces=[f for f in deck.Faces if abs(f.BoundBox.XMin-dx)<=tol and abs(f.BoundBox.XMax-dx)<=tol]
        checks.append(result(sid+'_full_width_deck_end_face',len(faces)==1 and abs(faces[0].BoundBox.YLength-c.DeckWidth.Value)<=tol))
        # Section the actual slab at its new centerline end: correct PGL level,
        # full slab thickness and grade are checked separately by bridge.validate.
        sec=deck.section(Part.makeLine(App.Vector(dx,0,-100000),App.Vector(dx,0,100000)))
        zs=sorted(v.Point.z for v in sec.Vertexes)
        checks.append(result(sid+'_deck_end_PGL_elevation',len(zs)==2 and abs(zs[-1]-float(m.pgl(m.start+dx/FT))*FT)<=tol))
        rows.append({'support':sid,'horizontal_gap_in':gap/IN,'solid_distance_in':distance/IN,
            'FFBW_station_ft':m.start+bx/FT,'deck_end_station_ft':m.start+dx/FT,
            'deck_end_centerline_elevation_ft':zs[-1]/FT if zs else None})
    first=bridge.local_shape(objects['BridgeDeckS1']).BoundBox
    second=bridge.local_shape(objects['BridgeDeckS2']).BoundBox
    checks.append(result('deck_pier_joint_unchanged',abs(first.XMax-(m.peak-m.start)*FT)<=tol and abs(second.XMin-first.XMax)<=tol))
    return {'checks':checks,'measurements':rows}

def scoped_recompute(doc,affected,rebuild_decks=True):
    # No pending user edits are permitted. Clearance changes only the two decks;
    # haunch/beam extents already stop at their independent beam-end clearance.
    for o in doc.Objects:
        if o.Name not in affected:o.purgeTouched()
    if rebuild_decks:
        # A deck Shape change touches linked haunches during recompute, even if
        # they were clean at the start. Recompute decks first, then clear those
        # irrelevant downstream touches before running the complete checker.
        doc.recompute([doc.getObject(n) for n in ['BridgeDeckS1','BridgeDeckS2']])
    for o in doc.Objects:
        if o.Name!='BridgeGeometryChecks':o.purgeTouched()
    doc.BridgeGeometryChecks.touch();doc.recompute([doc.BridgeGeometryChecks])
    # Result/label changes touch the parent groups. Finish those pending group
    # updates after all unchanged geometric dependencies have been kept clean.
    doc.recompute()

def set_clearance(job):
    from .api import document,check_gui,preflight,atomic,compact
    rid=job['request_id'];path=ROOT/'reports/transactions'/(rid+'.json')
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    if path.exists():
        previous=json.loads(path.read_text(encoding='utf-8'))
        if previous['request']!=job:raise ValueError('Request ID reused for another job')
        if previous['status'] in ['PREPARED','VALIDATED']:raise RuntimeError('Unknown prior outcome; inspect before retry')
        return compact(previous)
    gap=length(job['clearance'],positive=True)
    doc=document(job['document']);check_gui(doc);c=doc.BridgePGL;checker=doc.BridgeGeometryChecks
    if not getattr(c,'EndBentRevision',0):raise ValueError('Measured end-bent backwalls are required')
    if doc.UndoMode==0:raise ValueError('Undo must be enabled for this transactional edit')
    pending=[o.Name for o in doc.Objects if 'Touched' in o.State or 'Invalid' in o.State]
    if pending:raise ValueError('Pre-existing pending recomputes: '+str(pending))
    if gap>c.BeamEndClearance.Value+1e-9:raise ValueError('Clearance beyond the existing beam ends would require a separate haunch/support revision')
    if 'DeckEndClearance' in c.PropertiesList:preflight(c,{'DeckEndClearance':job['clearance']})
    decks=[doc.getObject(n) for n in ['BridgeDeckS1','BridgeDeckS2']]
    if any(o is None or o.ComponentKind!='Deck' or o.PGL!=c for o in decks):raise ValueError('Explicit deck targets do not match')
    protected=[o.Name for o in doc.Objects if o.Name not in [d.Name for d in decks]+[checker.Name]]
    before=bridge.source_state(doc,protected)
    all_before=bridge.source_state(doc,[o.Name for o in doc.Objects])
    names=set(all_before);old_proxies={o.Name:o.Proxy for o in decks+[checker]}
    old_gap=c.DeckEndClearance.Value/IN if 'DeckEndClearance' in c.PropertiesList else 0.
    old_volumes={o.Name:o.Shape.Volume for o in decks}
    rec={'operation':'set_deck_end_clearance','document':doc.Name,'request':job,'transaction_id':rid,
        'timestamp':datetime.now(timezone.utc).isoformat(),'status':'PREPARED','report_path':str(path),
        'model_saved':False,'old_gap_in':old_gap,'new_gap_in':gap/IN,'checks':[],'errors':[],'rollback':'NOT NEEDED',
        'warnings':['Existing bridge/MSE coordination failures remain explicit; no automatic trimming.']}
    atomic(path,rec);doc.openTransaction(rid)
    try:
        if 'DeckEndClearance' in c.PropertiesList:c.DeckEndClearance=job['clearance']
        else:bridge.prop(c,'App::PropertyLength','DeckEndClearance',job['clearance'],'Bridge dimensions')
        if 'DeckGapTransaction' in c.PropertiesList:c.DeckGapTransaction=rid
        else:bridge.prop(c,'App::PropertyString','DeckGapTransaction',rid,'Source')
        note=f'Deck end clearance: {job["clearance"]} inward from the fixed front faces of backwalls; PGL/support datums, beam ends and haunches unchanged.'
        c.Assumptions=[s for s in c.Assumptions if not s.startswith('Deck end clearance:')]+[note]
        if 'DeckBackwallClearances' not in checker.PropertiesList:
            bridge.prop(checker,'App::PropertyStringList','DeckBackwallClearances',[],'Results');checker.setEditorMode('DeckBackwallClearances',1)
        for o in decks:bridge.ComponentProxy(o);o.touch()
        bridge.CheckProxy(checker);checker.touch()
        scoped_recompute(doc,{o.Name for o in decks+[checker]})
        qa=checker.Proxy.last_qa;rec['checks']=qa['checks'].copy()
        after=bridge.source_state(doc,protected)
        rec['preservation_differences']={n:{k:[v,after[n][k]] for k,v in row.items() if v!=after[n][k]} for n,row in before.items() if row!=after[n]}
        rec['checks'].append(result('backwalls_PGL_supports_haunches_and_MSE_preserved',after==before))
        rec['checks'].append(result('object_count_and_names_preserved',set(o.Name for o in doc.Objects)==names))
        rec['checks'].append(result('deck_rendering',all(not bridge.display_state(o)['render_bounds_empty'] for o in decks)))
        rec['checks'].append(result('no_pending_recomputes',not any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects)))
        rec['measurements']=qa['deck_backwall_gaps'];rec['longitudinal_grades_percent']=qa['longitudinal_grades_percent']
        rec['deck_volume_change_ft3']={o.Name:(o.Shape.Volume-old_volumes[o.Name])/FT**3 for o in decks}
        if any(r['status']=='FAIL' for r in rec['checks']):raise ValueError('Deck clearance or preservation check failed')
        rec['coordination']=checker.Proxy.last_integration;rec['checks'].extend(rec['coordination']['checks'])
        rec['status']='VALIDATED';atomic(path,rec);doc.commitTransaction()
        rec['geometry_status']='PASS';rec['coordination_status']=checker.CoordinationStatus
        rec['status']='UPDATED — COORDINATION FAIL' if checker.CoordinationStatus=='FAIL' else 'PASS'
    except Exception as exc:
        rec['status']='FAIL';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc()
        doc.abortTransaction()
        for n,p in old_proxies.items():doc.getObject(n).Proxy=p
        # Undo has restored the exact native Shape properties. Do not rebuild
        # them: the PGL never changed, and only the live results need refresh.
        scoped_recompute(doc,{checker.Name},rebuild_decks=False)
        after=bridge.source_state(doc,list(all_before))
        rec['rollback_differences']={n:{k:[v,after[n][k]] for k,v in row.items() if v!=after[n][k]} for n,row in all_before.items() if row!=after[n]}
        rec['rollback']='VERIFIED' if after==all_before and set(o.Name for o in doc.Objects)==names else 'FAILED'
    atomic(path,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({k:rec[k] for k in ['timestamp','operation','transaction_id','document','status','report_path','model_saved','rollback']})+'\n')
    out=compact(rec);out.pop('coordination',None)
    return out
