"""Restore only missing, known project proxies without rebuilding geometry."""
import base64,hashlib,io,json,re,traceback,zipfile
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
import FreeCAD as App
from . import bridge,mse,drainage_trial,adopt_drainage
from .geometry import result
ROOT=bridge.ROOT
CLASSES={m.__name__+'.'+n:getattr(m,n) for m,names in [
    (mse,['SurfaceProxy','WallProfileProxy','FootingProfileProxy','FillProxy']),
    (bridge,['PGLProxy','ComponentProxy']),
    (drainage_trial,['SurfaceProxy','FillProxy','SlopeProxy','BridgeCheckProxy','TraceProxy','ControlProxy','ElevationProxy','LeaderProxy']),
    (adopt_drainage,['RampPGLProxy'])] for n in names}

def specs(path,digest):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Saved model source hash changed')
    with zipfile.ZipFile(path) as z:xml=ET.fromstring(z.read('Document.xml'))
    rows={}
    for o in xml.findall('./ObjectData/Object'):
        p=o.find('./Properties/Property[@name="Proxy"]/Python')
        if p is None or not p.get('module'):continue
        key=p.get('module')+'.'+p.get('class')
        if key not in CLASSES or json.loads(base64.b64decode(p.get('value')).decode()) is not None:raise ValueError('Unsupported proxy or state: '+key)
        rows[o.get('name')]=key
    return rows

def controls(doc):
    out={}
    for o in doc.Objects:
        for p in o.PropertiesList:
            if p in ['Proxy','Shape']:continue
            raw=o.dumpPropertyContent(p)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                out[o.Name+'.'+p]=hashlib.sha256(b''.join(n.encode()+z.read(n) for n in sorted(z.namelist()))).hexdigest()
    return out

def restore(job):
    from .api import document,check_gui,atomic,compact
    doc=document(job['document']);check_gui(doc)
    if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Pending model edits')
    path=(ROOT/job['source']).resolve()
    if not path.is_relative_to(ROOT):raise ValueError('Source outside project')
    targets=specs(path,job['source_sha256']);missing=[]
    for n,key in targets.items():
        o=doc.getObject(n)
        if o is None or 'Proxy' not in o.PropertiesList:raise ValueError('Missing expected object '+n)
        if o.Proxy is None:missing.append(n)
        elif type(o.Proxy) is not CLASSES[key]:raise ValueError('Unexpected existing proxy '+n)
    rid=job['request_id']
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Bad request ID')
    report=ROOT/'reports/transactions'/(rid+'.json')
    if report.exists():raise ValueError('Inspect previous recovery transaction instead of retrying')
    before=bridge.source_state(doc,[o.Name for o in doc.Objects]);props=controls(doc)
    affected=set(missing)
    for n in missing:affected.update(o.Name for o in doc.getObject(n).InListRecursive)
    rec={'operation':'restore_missing_project_proxies','transaction_id':rid,'request':job,'document':doc.Name,'timestamp':datetime.now(timezone.utc).isoformat(),'report_path':str(report),'status':'PREPARED','model_saved':False,'restored_count':len(missing),'checks':[],'errors':[],'rollback':'NOT NEEDED'}
    atomic(report,rec);doc.openTransaction(rid)
    try:
        for n in missing:
            cls=CLASSES[targets[n]];proxy=cls.__new__(cls);proxy.loads(None);doc.getObject(n).Proxy=proxy
        for n in affected:doc.getObject(n).purgeTouched()
        rec['checks']=[result('all_geometry_links_placements_and_views_exact',bridge.source_state(doc,list(before))==before),result('all_nonproxy_native_properties_exact',controls(doc)==props),result('all_expected_proxies_available',all(type(doc.getObject(n).Proxy) is CLASSES[k] for n,k in targets.items())),result('no_pending_objects',not any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects))]
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Proxy restoration preservation failure')
        if job.get('test_failure'):raise ValueError('Deliberate rollback test')
        rec['status']='VALIDATED';atomic(report,rec);doc.commitTransaction();rec['status']='PASS'
    except Exception as exc:
        rec['status']='FAIL';rec['errors']=[str(exc)];rec['traceback']=traceback.format_exc();doc.abortTransaction()
        for n in missing:doc.getObject(n).Proxy=None
        for n in affected:doc.getObject(n).purgeTouched()
        rec['rollback']='VERIFIED' if bridge.source_state(doc,list(before))==before and controls(doc)==props and all(doc.getObject(n).Proxy is None for n in missing) else 'FAILED'
    atomic(report,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','document','status','model_saved','rollback','report_path']})+'\n')
    return compact(rec)
