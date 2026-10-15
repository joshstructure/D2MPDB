"""Dependency-guarded D-032 cleanup; native source geometry remains editable.

Only the audited, superseded boolean stages below may be removed. This helper
never discovers arbitrary deletions, saves the model, or changes engineering status.
"""
import json,re
from pathlib import Path
from datetime import datetime,timezone
from . import bridge,deck_edge_details

OBSOLETE = ('BarrierA7ContactTools', 'BarrierA7Coordinated', 'BarrierB7ContactTools', 'BarrierB7Coordinated', 'BarrierB8ContactTools', 'BarrierB8Coordinated', 'BarrierDeckS1LContactTools', 'BarrierDeckS1LCoordinated', 'BarrierDeckS1RContactTools', 'BarrierDeckS1RCoordinated', 'BarrierDeckS2LContactTools', 'BarrierDeckS2LCoordinated', 'BarrierDeckS2RContactTools', 'BarrierDeckS2RCoordinated', 'BarrierReturnEB2RContactTools', 'BarrierReturnEB2RCoordinated', 'CopingA2ContactFinal', 'CopingA2ContactTools', 'CopingA2Coordinated', 'CopingA7ContactTools', 'CopingA7Coordinated', 'CopingB3ContactTools', 'CopingB3Coordinated', 'CopingB4ContactTools', 'CopingB4Coordinated', 'CopingB7ContactTools', 'CopingB7Coordinated', 'CopingB8ContactTools', 'CopingB8Coordinated', 'PlinthReturnEB2RContactFinal', 'PlinthReturnEB2RContactTools', 'PlinthReturnEB2RCoordinated', 'WallA6Finished', 'WallA6JointTools', 'WallA7FinishedBentJoint', 'WallB2BentJoint', 'WallB5Finished', 'WallB5JointTools', 'WallB6BentJoint', 'WallB7FinishedBentJoint', 'WallB8Finished', 'WallB8JointTools')
HIDDEN_SOURCES = ('BridgePierWallEnvelope','CompletePGLTrace')


def plan(doc):
    pending={n for n in OBSOLETE if doc.getObject(n)}
    physical=deck_edge_details.physical_objects(doc)
    if pending.intersection(physical):
        raise ValueError('Cleanup list includes current physical geometry')
    for obj in doc.Objects:
        if obj.Name in pending: continue
        # Group membership is allowed to change; all other links are protected,
        # including custom link lists on DocumentObjectGroup (FinishedDetails).
        for prop in obj.PropertiesList:
            if prop=='Group' and obj.TypeId=='App::DocumentObjectGroup': continue
            typ=obj.getTypeIdOfProperty(prop)
            if typ.startswith('App::PropertyLink'):
                value=getattr(obj,prop)
                def names(v):
                    if hasattr(v,'Name'):return {v.Name}
                    if isinstance(v,(list,tuple)):return set().union(*(names(x) for x in v)) if v else set()
                    return set()
                hits=names(value).intersection(pending)
                if hits:raise ValueError(f'Current dependency {obj.Name}.{prop}: {sorted(hits)}')
            if typ in ('App::PropertyString','App::PropertyStringList'):
                for name in pending:
                    if re.search(r'(?<![A-Za-z0-9_])'+re.escape(name)+r'(?![A-Za-z0-9_])',str(getattr(obj,prop))):
                        raise ValueError(f'Current name reference {obj.Name}.{prop}: {name}')
    order=[]
    while pending:
        ready=sorted(n for n in pending if not any(p.Name in pending for p in doc.getObject(n).InList))
        if not ready:raise ValueError('Cyclic obsolete object dependencies')
        order.extend(ready);pending.difference_update(ready)
    return order


def apply(doc, report_path):
    report_path=Path(report_path)
    if report_path.exists():raise ValueError('Report already exists; inspect prior outcome before retry')
    bad=[o.Name for o in doc.Objects if any(s in o.State for s in ('Touched','Invalid'))]
    if bad:raise ValueError('Pending model changes: '+str(bad))
    order=plan(doc);before=bridge.source_state(doc,[o.Name for o in doc.Objects])
    remaining=sorted(set(before)-set(order))
    groups=[o for o in doc.Objects if o.TypeId=='App::DocumentObjectGroup' and o.Name.endswith('Paths')]
    paths=[o for g in groups for o in g.Group]
    assert len(paths)==610 and len(groups)==19, 'Unexpected current reinforcement inventory'
    for path in paths:
        bars={o.Name for o in path.InList if 'Diameter' in o.PropertiesList and 'Base' in o.PropertiesList and o.Base==path}
        assert len(bars)==1, 'Unmatched reinforcement path '+path.Name
    hide={o.Name for o in paths+groups}|set(HIDDEN_SOURCES)
    physical=set(deck_edge_details.physical_objects(doc))
    record={'transaction_id':'model-cleanup-20261015-'+doc.Name,
            'timestamp':datetime.now(timezone.utc).isoformat(),'document':doc.Name,
            'status':'PREPARED','removed':order,'hidden':sorted(hide),'model_saved':False}
    def write():report_path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    write();doc.openTransaction('Remove superseded stages and hide construction paths')
    try:
        for name in order:doc.removeObject(name)
        doc.recompute()
        # Native Cut deletion may reveal its base. Restore all retained display
        # states, groups first, before applying only the requested source cleanup.
        if bridge.App.GuiUp:
            for is_group in (True,False):
                for name in remaining:
                    obj=doc.getObject(name)
                    if (obj.TypeId=='App::DocumentObjectGroup')==is_group:
                        if obj.ViewObject.Visibility!=before[name]['visibility']:
                            obj.ViewObject.Visibility=before[name]['visibility']
            for name in hide:
                view=doc.getObject(name).ViewObject
                if view.Visibility:view.Visibility=False
        after=bridge.source_state(doc,remaining);changed=[]
        for name in remaining:
            expected=dict(before[name]);expected['dependencies']=[n for n in expected['dependencies'] if n not in order]
            if name in hide and bridge.App.GuiUp:expected['visibility']=False
            if expected!=after[name]:changed.append(name)
        record['unexpected_changes']={n:{k:{'before':before[n][k],'after':after[n][k]} for k in before[n] if before[n][k]!=after[n][k]} for n in changed}
        assert not changed, 'Unexpected native changes: '+str(changed)
        assert set(deck_edge_details.physical_objects(doc))==physical
        assert not [o.Name for o in doc.Objects if any(s in o.State for s in ('Touched','Invalid'))]
        assert all(not doc.getObject(n).ViewObject.Visibility for n in hide) if bridge.App.GuiUp else True
        record.update(status='PASS',objects_before=len(before),objects_after=len(after),
                      preserved_native_shapes=sum(v['shape'] is not None for v in after.values()),
                      preserved_physical_objects=len(physical),preserved_reinforcement=610,
                      preserved_wwr=doc.CheekLugWWRQuantities.WireCount,
                      path_groups_hidden=len(groups),paths_hidden=len(paths),
                      checks='All retained native BReps, placements, expressions, labels and non-group dependencies exactly preserved; physical visibility preserved.',
                      clash_review='Not rerun: all current physical geometry is exact; prior findings and deferrals remain.')
        doc.commitTransaction();write()
    except Exception as exc:
        doc.abortTransaction()
        if bridge.App.GuiUp:
            for is_group in (True,False):
                for name,state in before.items():
                    obj=doc.getObject(name)
                    if obj and (obj.TypeId=='App::DocumentObjectGroup')==is_group:obj.ViewObject.Visibility=state['visibility']
        record.update(status='FAIL',error=str(exc));write();raise
    with (report_path.parent/'change-journal.jsonl').open('a',encoding='utf-8') as out:
        out.write(json.dumps({k:record[k] for k in ('transaction_id','timestamp','document','status','model_saved')})+'\n')
    return record


def preserve_archive(source, candidate, destination, report):
    """Preserve native precision through save; only groups and visibility differ.

FreeCAD cold-open/save renormalizes BRep direction vectors and element-map
serialization. Reuse the established native archive preserver, then make only
this cleanup's audited group-list and native visibility edits. Candidate GUI
views retain the tested cleanup state and existing colors.
"""
    import zipfile,xml.etree.ElementTree as ET
    from . import native_archive
    source,candidate,destination=map(Path,(source,candidate,destination))
    with zipfile.ZipFile(candidate) as z:
        names=[o.get('name') for o in ET.fromstring(z.read('Document.xml')).find('ObjectData')]
    stage=destination.with_name(destination.stem+'-preserved.FCStd')
    native_archive.preserve(source,candidate,stage,names,native_archive.sha(source),keep_candidate_views=True)
    with zipfile.ZipFile(stage) as z:files={n:z.read(n) for n in z.namelist()}
    root=ET.fromstring(files['Document.xml']);removed=set(report['removed']);hidden=set(report['hidden'])
    with zipfile.ZipFile(source) as z:
        original_root=ET.fromstring(z.read('Document.xml'))
    root.find("Properties/Property[@name='Label']/String").set('value',original_root.find("Properties/Property[@name='Label']/String").get('value'))
    for obj in root.find('ObjectData'):
        group=obj.find("Properties/Property[@name='Group']/LinkList")
        if group is not None:
            for link in list(group):
                if link.get('value') in removed:group.remove(link)
            group.set('count',str(len(group)))
        if obj.get('name') in hidden:
            visible=obj.find("Properties/Property[@name='Visibility']/Bool")
            if visible is not None:visible.set('value','false')
    files['Document.xml']=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    if destination.exists():raise ValueError('Use a fresh cleanup destination')
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return {'sha256':native_archive.sha(destination),'preserved_records':len(names)}
