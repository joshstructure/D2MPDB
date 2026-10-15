"""Coordinate selected end hoops and cheek verticals on a disposable native copy."""
from pathlib import Path
import json,traceback
from datetime import datetime,timezone
from . import bridge,cap_cages as cap,cheek_steel as cheek,design_steel as steel
from .mse import prop
from .geometry import length,pair

def update(doc,job):
    out=Path(job['output']);out.mkdir(exist_ok=True);record=out/'transaction.json'
    if record.exists():raise ValueError('Inspect recorded outcome before retry')
    if Path(doc.FileName).resolve()!=Path(job['disposable_copy']).resolve():raise ValueError('Disposable copy required')
    if length(job['tolerance'])!=.0254:raise ValueError('Existing 0.001 in tolerance required')
    mutable={'WallSteelChecks','CheekSteelChecks'}
    for host in cheek.HOSTS:
        prefix='Steel'+host
        mutable.update(prefix+s for s in ['Inputs','Quantities','Schedule','Paths','Bars','MV01','MV01Path','MV04','MV04Path','MV05','MV05Path'])
    for sid in ['EB1','EB2']:
        mutable.update('Cage'+sid+s for s in ['Inputs','Quantities','Schedule','Checks','Trans_R1_1','Trans_R1_1Path','Trans_R9_4','Trans_R9_4Path'])
    protected=[o.Name for o in doc.Objects if o.Name not in mutable]
    before=bridge.source_state(doc,protected)
    rec=dict(transaction_id=job['request_id'],status='PREPARED',timestamp=datetime.now(timezone.utc).isoformat(),request=job,protected=protected,changes=[])
    record.write_text(json.dumps(rec,indent=2))
    try:
        for sid in ['EB1','EB2']:
            inp=doc.getObject('Cage'+sid+'Inputs');raw=inp.SourceCaseJSON
            prop(inp,'App::PropertyString','TransverseStationOverridesJSON',json.dumps(job['hoop_stations']),'CAD coordination')
            prop(inp,'App::PropertyString','CoordinationBasis','User 2026-10-14: end hoop inward of cheek mat; remaining transverse stations and supplied source case unchanged.','CAD coordination')
            inp.Proxy.execute(inp)
            for ident in job['hoop_stations']:
                bar=doc.getObject('Cage'+sid+ident);bar.Base.Proxy.execute(bar.Base);bar.Proxy.execute(bar)
                rec['changes'].append(dict(object=bar.Name,station=job['hoop_stations'][ident]))
            q=doc.getObject('Cage'+sid+'Quantities');q.Proxy.execute(q)
            assert inp.SourceCaseJSON==raw
        for host in cheek.HOSTS:
            inp=doc.getObject('Steel'+host+'Inputs')
            prop(inp,'App::PropertyString','VerticalStationsJSON',json.dumps(job['vertical_stations']),'CAD coordination')
            prop(inp,'App::PropertyString','CoordinationBasis','User 2026-10-14: remove MV05 of the close pair; move MV01/MV04 just inside cap longitudinal bars. Contact permitted, positive solid overlap prohibited.','CAD coordination')
            inp.ScheduleNote='SINGLE CENTERED MAT: #4 each way; four verticals at explicit editable stations, <=12 in spacing. Horizontal bars unchanged. Anchorage and lug reinforcement not detailed.'
            inp.Proxy.execute(inp)
            for ident in ['MV01','MV04']:
                bar=doc.getObject(inp.Prefix+ident);bar.Base.Proxy.execute(bar.Base);bar.Proxy.execute(bar)
            q=doc.getObject(inp.Prefix+'Quantities');q.Proxy.execute(q)
            steel.write_wall_schedule(inp,doc.getObject(inp.Prefix+'Schedule'),q.Bars)
            assert doc.getObject(inp.Prefix+'MV05') is None
            rec['changes'].append(dict(wall=host,removed='MV05',vertical_stations=job['vertical_stations']))
        for o in doc.Objects:o.purgeTouched()
        sheets=[doc.getObject('Cage'+sid+'Schedule') for sid in ['EB1','EB2']]+[doc.getObject('Steel'+h+'Schedule') for h in cheek.HOSTS]
        for sheet in sheets:sheet.touch()
        doc.recompute(sheets)
        # The established wall synchronizer reassigns duplicate display labels.
        # Restore every untouched object's original label before exact checks.
        renamed=[n for n in protected if doc.getObject(n).Label!=before[n]['label']]
        for n in renamed:doc.getObject(n).Label='CoordinationRestore_'+n
        for n in renamed:doc.getObject(n).Label=before[n]['label']
        rec['restored_display_labels']=renamed
        rec['geometry']={sid:cap.geometry_checks(doc.getObject('Cage'+sid+'Inputs')) for sid in ['EB1','EB2']}
        assert all(c['status']=='PASS' for g in rec['geometry'].values() for c in g['checks'])
        after=bridge.source_state(doc,protected)
        rec['preservation_differences']=[n for n in protected if before[n]!=after[n]]
        assert not rec['preservation_differences'],rec['preservation_differences']
        rec['targeted_clearances']=[]
        for sid in ['EB1','EB2']:
            allcap=list(doc.getObject('Cage'+sid+'Quantities').Bars)
            for host in [h for h in cheek.HOSTS if sid in h]:
                allwall=list(doc.getObject('Steel'+host+'Quantities').Bars)
                changed=[doc.getObject('Steel'+host+s) for s in ['MV01','MV04']]
                first=doc.getObject('Cage'+sid+('Trans_R1_1' if host.endswith('1') else 'Trans_R9_4'))
                for a,b in [(a,b) for a in changed for b in allcap]+[(first,b) for b in allwall]:
                    c=pair(a.Shape.copy(),b.Shape.copy(),0.,.0254);c.update(a=a.Name,b=b.Name);rec['targeted_clearances'].append(c)
        assert all(c['status']=='PASS' for c in rec['targeted_clearances']),[c for c in rec['targeted_clearances'] if c['status']=='FAIL']
        print('Targeted bar clearances and native geometry pass; refreshing all affected checks.',flush=True)
        rec['detailing']={}
        for sid in ['EB1','EB2']:
            checker=doc.getObject('Cage'+sid+'Checks');checker.Proxy.execute(checker)
            rec['detailing'][sid]=json.loads(checker.ReportJSON)['detailing']
        rec['cheek']=cheek.validate(doc)
        nonclash=[c for c in rec['cheek']['failures'] if c['name']!='cheek_mat_internal_and_other_wall_cap_bar_clashes']
        assert not nonclash,nonclash
        doc.CheekSteelChecks.ReportJSON=json.dumps(rec['cheek']);doc.CheekSteelChecks.Status='FAIL' if rec['cheek']['failures'] else 'PASS'
        detail=rec['cheek']['all_wall_detailing'];doc.WallSteelChecks.ReportJSON=json.dumps(detail);doc.WallSteelChecks.Status='FAIL' if any(c['status']=='FAIL' for c in detail['checks']) else 'PASS'
        for check in [doc.CheekSteelChecks,doc.WallSteelChecks]:check.SnapshotBasis='14 October 2026: explicit cheek vertical positions and inward end hoops. Remaining physical overlaps are failures; contact allowed.'
        assert not [o.Name for o in doc.Objects if 'Invalid' in o.State]
        for o in doc.Objects:o.purgeTouched()
        rec['status']='UPDATED_WITH_REMAINING_FINDINGS'
    except Exception:
        rec['status']='FAIL';rec['traceback']=traceback.format_exc();raise
    finally:
        record.write_text(json.dumps(rec,indent=2)+'\n')
    return rec
