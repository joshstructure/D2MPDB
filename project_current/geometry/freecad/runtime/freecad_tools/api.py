"""JSON entry point. Modeling edits never save; native saves require explicit authorization."""
import json, math, os, re, uuid, traceback
from datetime import datetime,timezone
from pathlib import Path
import FreeCAD as App
from .geometry import length,display,solid_summary,box_checks,pair,box_cover,result
from . import mixed_cage
ROOT=Path(__file__).resolve().parent.parent
ALLOWED_CHECKS={'geometry','quantities','placement','clearance','cover','section','drawing_links'}

def document(name):
    if not isinstance(name,str) or name not in App.listDocuments(): raise ValueError('Explicit open document name required: '+str(name))
    return App.getDocument(name)

def resolve(doc,identifier):
    if isinstance(identifier,str):
        obj=doc.getObject(identifier)
        if obj is None: raise ValueError('Object Name not found: '+identifier)
        return obj
    if isinstance(identifier,dict) and set(identifier)=={'label'}:
        candidates=doc.getObjectsByLabel(identifier['label'])
        if len(candidates)!=1: raise ValueError('Label must be unique; candidates: '+str([o.Name for o in candidates]))
        return candidates[0]
    raise ValueError('Use an object Name or an explicit {label: ...} selector')

def scalar(obj,name):
    value=getattr(obj,name)
    return float(value.Value) if hasattr(value,'Value') else value

def atomic(path,data):
    tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8'); os.replace(tmp,path)

def compact(record):
    out={k:v for k,v in record.items() if k not in ('traceback','request')}
    out['checks']=[{k:v for k,v in c.items() if k!='details'} for c in record.get('checks',[])]
    if len(out['checks'])>12:
        counts={s:sum(c['status']==s for c in out['checks']) for s in ('PASS','FAIL','SKIPPED','NOT CONFIGURED')}
        out['check_summary']=counts; out['checks']=[c for c in out['checks'] if c['status']!='PASS'][:12]
    return out

def check_gui(doc):
    if getattr(App,'GuiUp',False):
        import FreeCADGui as Gui
        if Gui.activeDocument() and Gui.activeDocument().getInEdit(): raise ValueError('Finish current edit before mutation')
        if Gui.Control.activeDialog(): raise ValueError('Finish the active task dialog before mutation')
        from PySide import QtWidgets
        if QtWidgets.QApplication.activeModalWidget(): raise ValueError('Close the active modal dialog before mutation')
    active_transaction=App.getActiveTransaction()
    if active_transaction and active_transaction[1]: raise ValueError('An existing application transaction is active')
    pending=getattr(doc,'hasPendingTransaction',None)
    if callable(pending) and pending(): raise ValueError('An existing transaction is active')

def preflight(obj,params):
    expressions={str(path) for path,_ in getattr(obj,'ExpressionEngine',[])}
    for name in params:
        if any(path==name or path.startswith(name+'.') for path in expressions): raise ValueError('Expression-driven property cannot be overwritten: '+name)
        if obj.getEditorMode(name): raise ValueError('Read-only property: '+name)

def inspect(doc,objects):
    out=[]
    for obj in objects:
        item={'object':obj.Name,'label':obj.Label,'type':obj.TypeId,'dependencies':[o.Name for o in obj.OutList]}
        if 'Shape' in obj.PropertiesList and not obj.Shape.isNull(): item.update(solid_summary(obj))
        if obj.TypeId=='Part::Box': item['parameters']={k:display(scalar(obj,k)) for k in ('Length','Width','Height')}
        elif getattr(obj,'TestIdentifier',None)=='Rebar_Mixed_Cage_Test_v05' and 'HCount' in obj.PropertiesList and 'HBarNumber' in obj.PropertiesList:
            ref=mixed_cage.reference(0.0254); item['parameters']={r[0]:scalar(obj,r[0]) for r in ref['INPUTS']}; item['dimensional_units']='mm'; item['counts_and_bar_numbers']='integer'
        out.append(item)
    return {'status':'PASS','operation':'inspect','document':doc.Name,'objects':out}

def run(job):
    if not isinstance(job,dict): raise ValueError('Job must be a JSON object')
    if job.get('operation')=='add_terrain_spot':
        from .terrain_spot import add
        return add(job)
    if job.get('operation')=='add_verified_terrain_reference':
        from .geotech_sections import add_terrain
        return add_terrain(job)
    if job.get('operation')=='capture_geotech_sections':
        from .geotech_sections import capture
        return capture(job)
    if job.get('operation')=='restore_missing_project_proxies':
        from .restore_proxies import restore
        return restore(job)
    if job.get('operation')=='update_b4_footings_terrain':
        from .footing_terrain import update
        return update(job)
    if job.get('operation')=='analyze_terrain_wall_profiles':
        from .terrain_analysis import analyze
        return analyze(job)
    if job.get('operation')=='export_obm_package':
        from .obm_export import export
        return export(job)
    if job.get('operation')=='refresh_ramp_pgl':
        from .refresh_ramp_pgl import refresh
        return refresh(job)
    if job.get('operation')=='save_main_with_rollback':
        from .save_main import save
        return save(job)
    if job.get('operation')=='adopt_drainage':
        from .adopt_drainage import adopt
        return adopt(job)
    if job.get('operation')=='create_drainage_trial':
        from .drainage_trial import create
        return create(job)
    if job.get('operation')=='add_ramp_pgl_trace':
        from .ramp_trace import add
        return add(job)
    if job.get('operation')=='set_deck_end_clearance':
        from .deck_gaps import set_clearance
        return set_clearance(job)
    if job.get('operation')=='update_end_bents':
        from .end_bents import update
        return update(job)
    if job.get('operation')=='add_pgl_bridge':
        from .bridge import add
        return add(job)
    if job.get('operation') in ('export_step_mm', 'export_step'):
        from .step_export import export
        return export(job)
    if job.get('operation')=='create_mse_ramps':
        from .mse import create
        return create(job)
    if job.get('operation')=='create_rc_beam':
        from .beam import create
        return create(job)
    if job.get('operation')=='add_beam_end_hooks':
        from .beam_hooks import update
        return update(job)
    if job.get('operation')=='add_beam_drawings':
        from .beam_drawings import add
        return add(job)
    if job.get('operation')=='add_beam_fdot_sheets':
        from .beam_fdot import add
        return add(job)
    if job.get('operation')=='refresh_beam_fdot_sheets':
        from .beam_fdot import refresh
        return refresh(job)
    if job.get('operation')=='refresh_beam_drawings':
        from .beam_drawings import refresh
        return refresh(job)
    if job.get('operation')=='export_beam_dxf':
        from .beam_dxf import export
        return export(job)
    op=job.get('operation'); doc=document(job.get('document'))
    if op=='inspect_document':
        return {'status':'PASS','document':doc.Name,'label':doc.Label,'object_count':len(doc.Objects),'filename':doc.FileName,'freecad_version':App.Version()[:3]}
    targets=job.get('targets',[])
    if not isinstance(targets,list) or not targets: raise ValueError('Nonempty explicit targets list required')
    objects=[resolve(doc,t) for t in targets]
    if len({o.Name for o in objects})!=len(objects): raise ValueError('Duplicate targets')
    if op=='inspect': return inspect(doc,objects)
    tol=length(job.get('tolerance','0.001 in'),positive=True)
    names=job.get('checks',['geometry','quantities','placement','clearance','cover','section','drawing_links'])
    if not isinstance(names,list) or not set(names)<=ALLOWED_CHECKS: raise ValueError('Unsupported check names')
    if op=='check_pair':
        if len(objects)!=2: raise ValueError('check_pair requires exactly two targets')
        minimum=length(job['minimum_clearance'])
        if minimum<0: raise ValueError('Clearance cannot be negative')
        checks=[pair(objects[0].Shape,objects[1].Shape,minimum,tol)]
        return {'status':checks[0]['status'],'document':doc.Name,'checks':checks}
    if op=='check_cover':
        if len(objects)!=2: raise ValueError('check_cover targets are bar then box host')
        minimum=length(job['minimum_cover'])
        if minimum<0: raise ValueError('Cover cannot be negative')
        checks=[box_cover(objects[0].Shape,objects[1],minimum,tol)]
        return {'status':checks[0]['status'],'document':doc.Name,'checks':checks}
    if op=='validate':
        checks=[]
        for obj in objects:
            if obj.TypeId=='Part::Box': checks.extend(box_checks(obj,tol))
            elif getattr(obj,'AdapterIdentifier',None)=='CAD_AI_Illustrative_RC_Beam_v1':
                from .beam import validate
                beam_checks,_=validate(doc,tol); checks.extend(beam_checks)
            else: checks.extend(mixed_cage.checks(mixed_cage.resolve(doc,obj),names,tol))
        report={'status':'FAIL' if any(c['status']=='FAIL' for c in checks) else 'PASS','document':doc.Name,'operation':'validate','checks':checks}
        path=ROOT/'reports'/('validation-'+uuid.uuid4().hex+'.json')
        report['report_path']=str(path); atomic(path,report)
        return compact(report)
    if op not in ('update_box','update_mixed_cage'): raise ValueError('Unsupported operation: '+str(op))
    if len(objects)!=1: raise ValueError('Updates require one explicit parameter object')
    obj=objects[0]; request_id=job.get('request_id',str(uuid.uuid4()))
    if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',request_id): raise ValueError('Invalid request_id')
    report_dir=Path(job.get('report_directory',ROOT/'reports/transactions')).resolve()
    if not report_dir.is_relative_to(ROOT): raise ValueError('Reports must stay inside CAD_AI')
    report_dir.mkdir(parents=True,exist_ok=True); path=report_dir/(request_id+'.json')
    if path.exists():
        prior=json.loads(path.read_text(encoding='utf-8'))
        if prior.get('request')!=job: raise ValueError('request_id already used with different parameters')
        if prior['status'] in ('PREPARED','VALIDATED'): raise RuntimeError('Prior outcome uncertain; inspect model before retry')
        return compact(prior)
    record={'timestamp':datetime.now(timezone.utc).isoformat(),'helper_version':'0.1.0','freecad_version':App.Version()[:3],'document':doc.Name,'targets':[obj.Name],'operation':op,'request':job,'transaction_id':request_id,'status':'PREPARED','changes':{},'units':'mm internally; decimal inches for display','recompute':'NOT RUN','checks':[],'warnings':['Geometry checks do not constitute structural design or code compliance approval.'],'errors':[],'rollback':'NOT NEEDED','report_path':str(path)}
    with path.open('x',encoding='utf-8') as stream: json.dump(record,stream,indent=2)
    opened=False; committed=False; undo_mode=doc.UndoMode; old={}; q=None
    try:
        check_gui(doc)
        params=job.get('parameters')
        if not isinstance(params,dict) or not params: raise ValueError('Nonempty parameters object required')
        if op=='update_box':
            if obj.TypeId!='Part::Box' or not set(params)<={'Length','Width','Height'}: raise ValueError('Box supports Length, Width, Height only')
            parsed={k:length(v,positive=True) for k,v in params.items()}
            affected=[obj,*obj.InListRecursive]
        else:
            q=mixed_cage.resolve(doc,obj); parsed=mixed_cage.parse(obj,params,tol)
            affected=[obj,*obj.InListRecursive]
            record['warnings'].append('Drawing layouts and dated check snapshots are not refreshed by parameter edits.')
        preflight(obj,parsed)
        old={k:scalar(obj,k) for k in parsed}
        record['dependencies']=[o.Name for o in affected if o!=obj]
        for key,new in parsed.items():
            if old[key]!=new: record['changes'][key]={'old':old[key],'new':new,'unit':'count/bar number' if type(new)==int else 'mm','requested':params[key]}
        def validate():
            state_errors=[o.Name for o in affected if any('Invalid' in str(s) or 'Error' in str(s) for s in o.State)]
            checks=[result('dependency_state',not state_errors,invalid_objects=state_errors)]
            checks.extend(box_checks(obj,tol) if q is None else mixed_cage.checks(q,names,tol))
            if q is None:
                checks.extend({'name':n,'status':'NOT CONFIGURED'} for n in ('clearance','cover','section','drawing_links'))
            return checks
        if not record['changes']:
            record['checks']=validate(); record['status']='FAIL' if any(c['status']=='FAIL' for c in record['checks']) else 'NO CHANGE'
        else:
            if undo_mode==0: doc.UndoMode=1
            doc.openTransaction('CAD_AI '+request_id); opened=True
            for key,new in parsed.items(): setattr(obj,key,new)
            doc.recompute(); record['recompute']='DONE'
            record['checks']=validate()
            if any(c['status']=='FAIL' for c in record['checks']): raise ValueError('Validation failed; see checks')
            record['status']='VALIDATED'; atomic(path,record)
            doc.commitTransaction(); opened=False; committed=True; record['status']='PASS'
    except Exception as exc:
        record['status']='FAIL'; record['errors'].append(str(exc)); record['traceback']=traceback.format_exc()
        if opened:
            try:
                doc.abortTransaction(); opened=False; doc.recompute()
                restored=all(scalar(obj,k)==v for k,v in old.items())
                checks=box_checks(obj,tol) if q is None else mixed_cage.checks(q,['geometry','quantities','placement'],tol)
                restored=restored and not any(c['status']=='FAIL' for c in checks)
                record['rollback']='COMPLETE' if restored else 'INCOMPLETE'
            except Exception as rollback_error: record['rollback']='FAILED'; record['errors'].append(str(rollback_error))
        elif committed: record['rollback']='NOT POSSIBLE: transaction already committed; inspect model'
        else: record['rollback']='NOT NEEDED: rejected before mutation'
    finally:
        if undo_mode==0: doc.UndoMode=0
    atomic(path,record)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as stream: stream.write(json.dumps(compact(record),allow_nan=False)+'\n')
    return compact(record)

def run_file(path):
    file=Path(path).resolve()
    if not file.is_relative_to(ROOT): raise ValueError('Jobs must be inside CAD_AI')
    return run(json.loads(file.read_text(encoding='utf-8-sig')))


