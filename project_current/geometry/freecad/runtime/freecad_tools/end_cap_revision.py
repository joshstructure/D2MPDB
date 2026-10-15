"""Apply selected end-cap cases on an explicitly disposable native copy.

The user's 251-in cage spans the 235-in cap and two 8-in cheek webs.
Uses established native cage builders; never changes concrete or wall steel.
"""
from pathlib import Path
import json,hashlib,traceback
from datetime import datetime,timezone
from . import bridge,cap_cages as cap,cheek_steel,design_steel
from .mse import prop
from .geometry import result,length

def update(doc,job):
    out=Path(job['output']);out.mkdir(exist_ok=True)
    path=out/'transaction.json'
    if path.exists():raise ValueError('Inspect existing transaction before retry')
    if Path(doc.FileName).resolve()!=Path(job['disposable_copy']).resolve():raise ValueError('Disposable copy required')
    if length(job['tolerance'])!=.0254:raise ValueError('Fixed 0.001 in tolerance required')
    names=[o.Name for o in doc.Objects]
    protected=[n for n in names if not n.startswith(('CageEB1','CageEB2')) and n not in ['WallSteelChecks','CheekSteelChecks']]
    before=bridge.source_state(doc,protected)
    rec=dict(transaction_id=job['request_id'],timestamp=datetime.now(timezone.utc).isoformat(),status='PREPARED',request=job,protected=protected)
    path.write_text(json.dumps(rec,indent=2))
    try:
        rec['before']={sid:cap.geometry_checks(doc.getObject('Cage'+sid+'Inputs'))['totals'] for sid in ['EB1','EB2']}
        for sid in ['EB1','EB2']:
            src=job['cases'][sid];raw=Path(src['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=src['sha256']:raise ValueError('Source changed')
            case=json.loads(raw);inp=doc.getObject('Cage'+sid+'Inputs');old=cap.live_case(inp)
            for k in ['b','h','D_pile','S_pile','Pile_embed']:
                if abs(case['inputs'][k]-old['inputs'][k])>1e-10:raise ValueError('Unexpected concrete/pile input change '+k)
            hosts=[inp.Cap,doc.getObject('BridgeCheek'+sid+'1'),doc.getObject('BridgeCheek'+sid+'2')]
            bb=[bridge.local_shape(h).BoundBox for h in hosts]
            total=(max(b.YMax for b in bb)-min(b.YMin for b in bb))/25.4
            if abs(total-cap.geometry_evaluation(case).value('L_cap'))>.001:raise ValueError('Out-to-out dimension differs from case')
            inp.AutoSync=False
            inp.SourceCaseJSON=raw.decode('utf-8');inp.SourceSHA256=src['sha256'];inp.SourcePath=src['case_relative']
            for k in cap.PARAMS:setattr(inp,k,int(case['inputs'][k]) if k.startswith(('Bar_','n_')) else str(case['inputs'][k])+' in')
            inp.TransverseRunsJSON=json.dumps(case['transverse_detail']);inp.EndGridJSON=json.dumps(case['end_face_grid']);inp.AddedBarsJSON=json.dumps(case['added_bar_layout'])
            prop(inp,'App::PropertyLinkList','CoverConcrete',hosts,'Cage sources')
            prop(inp,'App::PropertyString','ConcreteExtentBasis','User clarified 2026-10-14: 235 in cap plus two 8 in cheek webs = 251 in overall. Concrete unchanged; check cover on the fused physical envelope.','Cage sources')
            inp.AutoSync=True;inp.Proxy.execute(inp)
        # Native expressions, paths, bars, quantities and schedules only.
        for o in doc.Objects:
            if not o.Name.startswith(('CageEB1','CageEB2')):o.purgeTouched()
        affected=[o for o in doc.Objects if o.Name.startswith(('CageEB1','CageEB2')) and not o.Name.endswith('Checks')]
        for _ in range(2):doc.recompute(affected)
        rec['geometry']={sid:cap.geometry_checks(doc.getObject('Cage'+sid+'Inputs')) for sid in ['EB1','EB2']}
        checks=[c for g in rec['geometry'].values() for c in g['checks']]
        for sid in ['EB1','EB2']:
            sh=doc.getObject('Cage'+sid+'Schedule');q=doc.getObject('Cage'+sid+'Quantities');r=str(sh.TotalRow)
            checks.append(result(sid+'_schedule_totals',float(sh.get('D'+r))==q.TotalBars and abs(float(sh.get('G'+r))-q.TotalSteelLength.Value/304.8)<1e-7 and abs(float(sh.get('H'+r))-q.NominalSteelWeightLb)<1e-7))
        after=bridge.source_state(doc,protected)
        rec['preservation_differences']=[n for n in protected if before[n]!=after[n]]
        checks.append(result('concrete_cheek_steel_pier_pedestals_and_other_objects_preserved',not rec['preservation_differences']))
        rec['checks']=checks
        if any(c['status']=='FAIL' for c in checks):raise ValueError('Geometry, schedule or preservation failure')
        print('Native cap geometry and preservation checks passed; checking physical clashes',flush=True)
        rec['detailing']={}
        for sid in ['EB1','EB2']:
            checker=doc.getObject('Cage'+sid+'Checks');checker.Proxy.execute(checker)
            rec['detailing'][sid]=json.loads(checker.ReportJSON)['detailing']
        rec['cheek']=cheek_steel.validate(doc)
        doc.CheekSteelChecks.ReportJSON=json.dumps(rec['cheek']);doc.CheekSteelChecks.Status='FAIL' if rec['cheek']['failures'] else 'PASS'
        detail=rec['cheek']['all_wall_detailing']
        doc.WallSteelChecks.ReportJSON=json.dumps(detail);doc.WallSteelChecks.Status='FAIL' if any(c['status']=='FAIL' for c in detail['checks']) else 'PASS'
        doc.WallSteelChecks.SnapshotBasis='14 October 2026 updated end cap cases, unchanged centered cheek mats. Positive overlaps remain failures.'
        doc.CheekSteelChecks.SnapshotBasis=doc.WallSteelChecks.SnapshotBasis
        invalid=[o.Name for o in doc.Objects if 'Invalid' in o.State]
        if invalid:raise ValueError('Invalid native objects '+str(invalid))
        for o in doc.Objects:o.purgeTouched()
        rec['status']='UPDATED_WITH_DETAILING_FINDINGS'
    except Exception:
        rec['status']='FAIL';rec['traceback']=traceback.format_exc();raise
    finally:
        path.write_text(json.dumps(rec,indent=2)+'\n')
        with (out/'change-journal.jsonl').open('a') as f:f.write(json.dumps({k:rec[k] for k in ['transaction_id','timestamp','status']})+'\n')
    return rec
