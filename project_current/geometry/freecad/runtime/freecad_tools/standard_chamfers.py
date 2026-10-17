"""Opt-in square bridge edges for drawing clarity; barriers/ramps are excluded.

Nominal 3/4-in chamfers remain documented as assumed standard details per the
user's FDOT convention. This helper makes no design or policy-compliance claim.
"""
import json
from pathlib import Path
import FreeCAD as App
from . import bridge, deck_edge_details

TARGETS = (['BridgeDeckS1', 'BridgeDeckS2'] +
           [f'BridgeBeamS{s}B{b}' for s in (1,2) for b in (1,2)] +
           [f'BridgePedestal{s}B{b}' for s in ('EB1','Pier','EB2') for b in (1,2)])
NOTE = ('Standard 3/4-in bridge chamfers are assumed per the user-directed FDOT '
        'drawing convention and omitted from modeled geometry for square 2D '
        'outlines. Barriers and ramp components are excluded. Nominal detail '
        'dimensions remain recorded; larger breaks, fillets and drip grooves remain.')


def rebuild(doc):
    """Rebuild only affected native solids; caller must have a clean document."""
    for name in TARGETS:
        obj = doc.getObject(name)
        if obj is None or obj.PGL != doc.BridgePGL or obj.Proxy is None:
            raise ValueError('Missing linked native component '+name)
        obj.Proxy.execute(obj)
    # The convention does not change any dependency's geometric datum. Avoid
    # regenerating existing bars (and replacing their accepted SDM marks).
    for obj in doc.Objects:
        obj.purgeTouched()
    doc.BridgeConcreteSchedule.touch()
    doc.recompute([doc.BridgeConcreteSchedule])
    for obj in doc.Objects:
        obj.purgeTouched()


def apply(doc, report_path, request_id):
    """Transaction, scoped rebuild, physical checks and journal; never saves."""
    path = Path(report_path)
    if path.exists():
        raise ValueError('Existing transaction report: inspect before repeating')
    pending = [o.Name for o in doc.Objects if 'Touched' in o.State or 'Invalid' in o.State]
    if pending:
        raise ValueError('Pre-existing pending model work: '+str(pending))
    c = doc.BridgePGL
    if getattr(c,'OmitStandardChamfers',False):
        raise ValueError('Square bridge convention is already enabled')
    names = [o.Name for o in doc.Objects]
    before = bridge.source_state(doc,names)
    volumes = {n:doc.getObject(n).Shape.Volume for n in TARGETS}
    allowed = set(TARGETS+['BridgePGL','BridgeConcreteSchedule'])
    record = dict(transaction_id=request_id,document=doc.Name,status='PREPARED',
                  targets=TARGETS,model_saved=False,assumption=NOTE)
    def write():
        path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    write()
    doc.openTransaction(request_id)
    try:
        bridge.prop(c,'App::PropertyBool','OmitStandardChamfers',True,'Drawing representation')
        bridge.prop(c,'App::PropertyString','StandardChamferConvention',NOTE,'Drawing representation')
        rebuild(doc)
        record['deck_details'] = deck_edge_details.measure(doc)
        assert record['deck_details']['pass'], 'Deck profile/groove check failed'
        record['bridge_checks'] = bridge.validate(c,{o.Name:o for o in doc.BridgeGeometryChecks.Components},check_pairs=False)
        record['geometry_failures'] = [r for r in record['bridge_checks']['checks'] if r['status']=='FAIL']
        assert not record['geometry_failures'],record['geometry_failures']
        after = bridge.source_state(doc,names)
        record['protected_differences'] = [n for n in names if n not in allowed and before[n]!=after[n]]
        assert not record['protected_differences'],record['protected_differences']
        assert names==[o.Name for o in doc.Objects]
        assert all(o.Proxy is not None for o in [doc.getObject(n) for n in TARGETS])
        record['protected_objects'] = len(names)-len(allowed)
        record['volume_added_in3'] = {n:(doc.getObject(n).Shape.Volume-volumes[n])/bridge.IN**3 for n in TARGETS}
        record['status'] = 'PASS'
        doc.commitTransaction()
    except Exception as exc:
        doc.abortTransaction()
        record.update(status='FAIL',error=str(exc),rollback_verified=bridge.source_state(doc,names)==before)
        write()
        raise
    write()
    with path.with_name('change-journal.jsonl').open('a',encoding='utf-8') as journal:
        journal.write(json.dumps({k:record[k] for k in ('transaction_id','document','status','targets','model_saved')})+'\n')
    return record
