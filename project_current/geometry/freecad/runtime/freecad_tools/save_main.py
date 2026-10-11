"""Explicitly authorized native save with separate rollback and disk history."""
import hashlib,json,re,shutil,traceback,zipfile
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from . import bridge
from .geometry import result

ROOT=bridge.ROOT

def checked_path(value):
    p=Path(value).resolve()
    if not p.is_relative_to(ROOT) or p.suffix.lower()!='.fcstd':
        raise ValueError('Native model paths must remain inside CAD_AI')
    return p

def archive_info(path,doc=None):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise ValueError('Archive integrity failure: '+str(path))
        xml=ET.fromstring(z.read('Document.xml'))
        objects=xml.find('Objects')
        names={o.attrib['name'] for o in objects.findall('Object')}
        if len(names)!=int(objects.attrib['Count']):raise ValueError('Archive object count mismatch')
        if doc is not None and names!={o.Name for o in doc.Objects}:
            raise ValueError('Saved object names differ from live document')
        return {'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'objects':len(names),'archive_integrity':'PASS'}

def save(job):
    from .api import document,check_gui,atomic,compact
    if job.get('authorization')!='Save main model with rollback backup':
        raise ValueError('Explicit user save authorization required')
    rid=job['request_id']
    if not re.fullmatch('[A-Za-z0-9_-]{8,80}',rid):raise ValueError('Invalid request ID')
    report=ROOT/'reports/transactions'/(rid+'.json')
    if report.exists():
        old=json.loads(report.read_text(encoding='utf-8'))
        if old['request']!=job:raise ValueError('Request ID reused for different job')
        if old['status']!='SAVED':raise ValueError('Inspect prior save stage and actual files before retrying')
        return compact(old)
    main=document(job['document']);previous=document(job['rollback_document'])
    if main==previous:raise ValueError('Main and rollback documents must differ')
    paths={k:checked_path(job[k]) for k in ['main_path','rollback_path','disk_backup_path']}
    if len(set(paths.values()))!=3:raise ValueError('Save destinations must differ')
    if any(paths[k].exists() for k in ['rollback_path','disk_backup_path']):raise ValueError('Backup destinations already exist')
    if not paths['main_path'].is_file():raise ValueError('Expected existing main disk file is missing')
    if Path(previous.FileName).resolve()!=paths['main_path']:raise ValueError('Previous document does not own the expected main path')
    for doc in [main,previous]:
        check_gui(doc)
        if any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects):raise ValueError('Resolve pending objects before save')
    before={d.Name:bridge.source_state(d,[o.Name for o in d.Objects]) for d in [main,previous]}
    oldfiles={d.Name:d.FileName for d in [main,previous]}
    rec={'operation':'save_main_with_rollback','transaction_id':rid,'timestamp':datetime.now(timezone.utc).isoformat(),'document':main.Name,'request':job,'report_path':str(report),'status':'PREPARED','stage':'PREPARED','model_saved':False,'checks':[],'errors':[],'previous_files':oldfiles,'files':{}}
    atomic(report,rec)
    try:
        for p in paths.values():p.parent.mkdir(parents=True,exist_ok=True)
        original_hash=hashlib.sha256(paths['main_path'].read_bytes()).hexdigest()
        shutil.copy2(paths['main_path'],paths['disk_backup_path'])
        rec['files']['disk_backup']=archive_info(paths['disk_backup_path'])
        if rec['files']['disk_backup']['sha256']!=original_hash:raise ValueError('Disk-history backup hash mismatch')
        rec['stage']='DISK_BACKUP_VERIFIED';atomic(report,rec)
        previous.saveAs(str(paths['rollback_path']))
        rec['files']['rollback']=archive_info(paths['rollback_path'],previous)
        if Path(previous.FileName).resolve()!=paths['rollback_path']:raise ValueError('Rollback document path was not reassigned')
        rec['stage']='ROLLBACK_SAVED_AND_VERIFIED';atomic(report,rec)
        main.saveAs(str(paths['main_path']))
        rec['model_saved']=True;rec['stage']='MAIN_SAVED';atomic(report,rec)
        rec['files']['main']=archive_info(paths['main_path'],main)
        for doc in [main,previous]:
            rec['checks'].append(result(doc.Name+'_native_geometry_links_expressions_preserved',bridge.source_state(doc,list(before[doc.Name]))==before[doc.Name]))
            rec['checks'].append(result(doc.Name+'_no_pending_objects',not any('Touched' in o.State or 'Invalid' in o.State for o in doc.Objects)))
        rec['checks'].append(result('main_file_assignment',Path(main.FileName).resolve()==paths['main_path']))
        rec['checks'].append(result('rollback_file_assignment',Path(previous.FileName).resolve()==paths['rollback_path']))
        if any(c['status']=='FAIL' for c in rec['checks']):raise ValueError('Save preservation check failed')
        rec['status']='SAVED';rec['stage']='ALL_FILES_VERIFIED'
    except Exception as exc:
        rec['status']='FAIL — INSPECT FILES BEFORE RETRY';rec['errors'].append(str(exc));rec['traceback']=traceback.format_exc()
    atomic(report,rec)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({k:rec[k] for k in ['operation','transaction_id','timestamp','document','status','stage','model_saved','report_path']})+'\n')
    return compact(rec)
