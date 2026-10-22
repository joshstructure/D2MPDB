"""Set the pier wall annular ring plate thickness to the selected D-078 case (1/2 in).

Headless FreeCAD 1.1 run on a disposable copy of the current model. Inputs come
from environment variables (D2_SNAPSHOT: engine snapshot of the selected case;
D2_OUT: scratch folder). The ring tops, diameters, fillets, bars and every
unrelated object are left untouched; only the ring plate thickness input, the
twenty ring solids, the live quantities and the source provenance change. The
authoritative model file is never written here.
"""
from pathlib import Path
import sys,json,os,traceback,zipfile,hashlib,copy,xml.etree.ElementTree as E
sys.dont_write_bytecode=True
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad'
OUT=Path(os.environ.get('D2_OUT',str(ROOT/'.validation/pier-wall-half-inch')));OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(MAIN/'runtime'))
import FreeCAD as App,Part
from freecad_tools import bridge,native_archive,pier_wall_rings as pw
IN=pw.IN
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def equal_shapes(a,b,tol=1e-5):return abs(a.cut(b).Volume)<tol and abs(b.cut(a).Volume)<tol
def ring_metrics(inp,r):
    s=r.Shape.copy();s.Placement=inp.PGL.Frame.inverse().multiply(s.Placement);b=s.optimalBoundingBox(False,False)
    return dict(top_mm=b.ZMax,bottom_mm=b.ZMin,thickness_in=b.ZLength/IN,od_in=b.XLength/IN,volume_in3=s.Volume/IN**3,
                top_above_wall_bottom_in=r.TopAboveWallBottom.Value/IN,weight_lb=r.NominalWeightLb,weld=r.WeldDetail)

manifest=json.loads((MAIN/'manifest.json').read_text());source=MAIN/manifest['model']['path']
snapshot=json.loads(Path(os.environ['D2_SNAPSHOT']).read_text());new_case=snapshot['case']
record={'status':'STARTED','source_sha256':native_archive.sha(source),'snapshot_sha256':snapshot['sha256']}
report=OUT/'build.json';doc=None
try:
    assert record['source_sha256']==manifest['model']['sha256'],'Model differs from the manifest'
    print('Opening source',flush=True);doc=App.openDocument(str(source))
    inp=doc.PierWallSteelInputs;q=doc.PierWallSteelQuantities;rings=list(q.Rings);bars=list(q.Bars)
    assert len(rings)==20 and len(bars)==124
    changed={inp.Name,q.Name,*[r.Name for r in rings]}
    protected=[o.Name for o in doc.Objects if o.Name not in changed]
    record['protected_objects']=len(protected);record['changed_objects']=sorted(changed)
    before=bridge.source_state(doc,protected)
    # Native recompute re-serializes the pier wall bar BReps (same geometry);
    # those records are restored byte-for-byte from the source by the staging
    # step. Every other protected record must stay exactly equal.
    wall_steel={o.Name:o.Shape.copy() for o in doc.Objects if o.Name.startswith('PierWallSteel') and 'Shape' in o.PropertiesList and o.Name not in changed}
    def unchanged(label):
        now=bridge.source_state(doc,protected);drift=[]
        for n in protected:
            if now[n]==before[n]:continue
            keys=[k for k in before[n] if before[n][k]!=now[n][k]]
            # The D-076 controller re-labels its bars on every sync (FreeCAD's
            # unique-label suffixes shift); labels and re-serialized BReps are
            # in-memory only here and are restored from the source on staging.
            if n in wall_steel and set(keys)<={'label','shape'} and equal_shapes(doc.getObject(n).Shape,wall_steel[n]):continue
            drift.append((n,keys))
        assert not drift,(label,drift[:10])
        record.setdefault('state_checks',[]).append(dict(step=label,exact=now==before,
            wall_steel_reserialized=sorted(n for n in wall_steel if now[n]['shape']!=before[n]['shape']),
            wall_steel_relabelled=sorted(n for n in wall_steel if now[n]['label']!=before[n]['label'])))
    old_case=json.loads(inp.SourceCaseJSON)
    diff=[k for k in new_case if new_case[k]!=old_case.get(k)]
    assert diff==['ring_t_in'] and set(new_case)==set(old_case),diff
    assert abs(inp.RingThickness.Value-old_case['ring_t_in']*IN)<1e-9
    old_rings={r.Name:dict(shape=r.Shape.copy(),**ring_metrics(inp,r)) for r in rings}
    record['before']=dict(ring_thickness_in=inp.RingThickness.Value/IN,ring_weight_lb=q.RingWeightLb,ring_volume_in3=q.RingVolume.Value/IN**3,
                          rings={n:{k:v for k,v in m.items() if k!='shape'} for n,m in old_rings.items()})
    d=pw.dimensions(inp)
    # Ordinary native edit: change the live input and recompute the document.
    print('Setting ring thickness and recomputing',flush=True)
    inp.RingThickness=f"{new_case['ring_t_in']} in";doc.recompute()
    bad=[o.Name for o in doc.Objects if 'Invalid' in o.State]
    assert not bad,bad
    unchanged('native recompute at 1/2 in')
    expected_vol=3.141592653589793/4*(inp.RingOD.Value**2-inp.RingID.Value**2)*inp.RingThickness.Value
    after={}
    for r in rings:
        m=ring_metrics(inp,r);o=old_rings[r.Name]
        assert abs(m['thickness_in']-new_case['ring_t_in'])<1e-9,(r.Name,m)
        assert abs(m['top_mm']-o['top_mm'])<1e-6 and abs(m['top_above_wall_bottom_in']-o['top_above_wall_bottom_in'])<1e-9,(r.Name,'top moved')
        assert abs(m['bottom_mm']-(o['bottom_mm']+(old_case['ring_t_in']-new_case['ring_t_in'])*IN))<1e-6,(r.Name,'bottom')
        assert abs(m['od_in']-new_case['ring_od_in'])<1e-9 and m['weld']==o['weld']
        assert abs(m['top_mm']-(d['bottom']*IN+inp.FirstRingTop.Value+(r.Row-1)*inp.RingSpacing.Value))<1e-6
        # The thinner plate lies inside the former plate, sharing its top face.
        s=r.Shape.copy()
        assert abs(s.cut(o['shape']).Volume)<1e-6 and abs(o['shape'].cut(s).Volume-(expected_vol*(old_case['ring_t_in']/new_case['ring_t_in']-1)))<1e-3,(r.Name,'containment')
        after[r.Name]={k:v for k,v in m.items() if k!='shape'}
    record['after']=dict(ring_thickness_in=inp.RingThickness.Value/IN,ring_weight_lb=q.RingWeightLb,ring_volume_in3=q.RingVolume.Value/IN**3,rings=after)
    assert abs(q.RingVolume.Value-20*expected_vol)<1e-5 and q.TotalRings==20
    print('Validating geometry, cover and steel intersections',flush=True)
    record['validation']=pw.validate(inp);dump(report,record)
    assert record['validation']['status']=='PASS',[c for c in record['validation']['checks'] if c['status']!='PASS']
    # Native edit round trip: the former thickness reproduces the former solids.
    print('Testing native edit round trip',flush=True)
    inp.RingThickness=f"{old_case['ring_t_in']} in";doc.recompute()
    for r in rings:assert equal_shapes(r.Shape,old_rings[r.Name]['shape']),r.Name
    inp.RingThickness=f"{new_case['ring_t_in']} in";doc.recompute()
    for r in rings:assert abs(ring_metrics(inp,r)['thickness_in']-new_case['ring_t_in'])<1e-9
    record['native_edit_restore']=True
    unchanged('native edit round trip')
    # Provenance: the immutable case snapshot now names the selected D-078 case.
    inp.SourceCaseJSON=json.dumps(new_case);inp.SourceCaseSHA256=snapshot['sha256']
    inp.SourceFailuresJSON=json.dumps(snapshot['failed_checks'])
    inp.SourcePath='project_current/pier_wall/selected_case.json (D-078, 22 October 2026)'
    inp.EngineeringStatus='CAD ring plates 1/2 in match the selected D-078 case; wall dimensions match D-075 within 0.001 in; RING-GRID tolerance failure remains; engineering acceptance open'
    assert inp.Limitations==pw.LIMITS and inp.ScheduleNote==pw.LIMITS
    raw=OUT/'native.FCStd';candidate=OUT/'candidate.FCStd'
    for p in (raw,candidate):
        if p.exists():p.unlink()
    for o in doc.Objects:o.purgeTouched()
    print('Saving candidate',flush=True);doc.saveAs(str(raw))
    record['archive']=native_archive.preserve(source,raw,candidate,protected,record['source_sha256'])
    # Keep the exact original GUI document and its view resources (no view
    # provider changes); drop the duplicate view copies the staging step adds.
    with zipfile.ZipFile(source) as z:original={n:z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(candidate) as z:updated={n:z.read(n) for n in z.namelist()}
    gui=E.fromstring(original['GuiDocument.xml'])
    for el in gui.iter():
        ref=el.get('file')
        if ref:updated[ref]=original[ref]
    updated['GuiDocument.xml']=original['GuiDocument.xml']
    docrefs={el.get('file') for el in E.fromstring(updated['Document.xml']).iter() if el.get('file')}
    guirefs={el.get('file') for el in gui.iter() if el.get('file')}
    keep={n:b for n,b in updated.items() if n in original or n in docrefs or n in guirefs or n in ('Document.xml','GuiDocument.xml')}
    assert docrefs<=set(keep) and guirefs<=set(keep)
    candidate.unlink()
    with zipfile.ZipFile(candidate,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in keep.items():z.writestr(n,b)
    with zipfile.ZipFile(candidate) as z:assert z.testzip() is None
    record['dropped_unreferenced_entries']=sorted(set(updated)-set(keep))
    # File-level preservation: every record except the changed objects is canonical-identical.
    def canonical(node,data):
        node=copy.deepcopy(node)
        for el in node.iter():
            path=el.get('file')
            if path:el.set('file','sha256:'+hashlib.sha256(data[path]).hexdigest())
        return E.tostring(node)
    with zipfile.ZipFile(candidate) as z:final={n:z.read(n) for n in z.namelist()}
    def nodes(data,filename,path):return {o.get('name'):o for o in E.fromstring(data[filename]).find(path)}
    old,new=nodes(original,'Document.xml','ObjectData'),nodes(final,'Document.xml','ObjectData')
    assert set(old)==set(new)
    changed_records=sorted(n for n in old if canonical(old[n],original)!=canonical(new[n],final))
    assert set(changed_records)<=changed,changed_records
    assert final['GuiDocument.xml']==original['GuiDocument.xml']
    for ref in guirefs:assert final[ref]==original[ref]
    record['file_preservation']=dict(status='PASS',changed_records=changed_records,gui_document_byte_identical=True,
                                     existing_records_preserved=len(old)-len(changed_records))
    App.closeDocument(doc.Name);doc=None
    print('Cold reopening candidate',flush=True);doc=App.openDocument(str(candidate))
    assert before==bridge.source_state(doc,protected),'Cold reopen changed existing model'
    inp=doc.PierWallSteelInputs;q=doc.PierWallSteelQuantities
    assert abs(inp.RingThickness.Value-new_case['ring_t_in']*IN)<1e-9 and inp.SourceCaseSHA256==snapshot['sha256']
    assert json.loads(inp.SourceCaseJSON)==new_case
    for r in q.Rings:
        m=ring_metrics(inp,r);assert abs(m['thickness_in']-new_case['ring_t_in'])<1e-9 and abs(m['top_mm']-old_rings[r.Name]['top_mm'])<1e-6
    record['cold_reopen_validation']=pw.validate(inp)
    assert record['cold_reopen_validation']['status']=='PASS'
    assert type(inp.Proxy).__name__=='InputsProxy' and type(doc.PierWallRingP1R1.Proxy).__name__=='RingProxy'
    # Ordinary native recompute after reopen (the user's workflow) keeps the plates.
    inp.RingThickness=f"{new_case['ring_t_in']+0.25} in";doc.recompute()
    assert abs(ring_metrics(inp,doc.PierWallRingP4R5)['thickness_in']-new_case['ring_t_in']-0.25)<1e-9
    inp.RingThickness=f"{new_case['ring_t_in']} in";doc.recompute()
    assert abs(ring_metrics(inp,doc.PierWallRingP4R5)['thickness_in']-new_case['ring_t_in'])<1e-9
    unchanged('ordinary recompute after cold reopen')
    record.update(status='VERIFIED',ordinary_native_recompute=True,cold_reopen=True,objects=len(doc.Objects),
                  candidate=str(candidate),candidate_sha256=native_archive.sha(candidate),candidate_bytes=candidate.stat().st_size,
                  source_unchanged=native_archive.sha(source)==record['source_sha256'])
    assert record['source_unchanged'];dump(report,record)
    print(json.dumps({k:v for k,v in record.items() if k not in ('validation','cold_reopen_validation','before','after')},indent=2),flush=True)
    code=0
except Exception:
    record.update(status='FAIL',error=traceback.format_exc());dump(report,record);traceback.print_exc();code=1
finally:
    if doc:App.closeDocument(doc.Name)
sys.stdout.flush();sys.stderr.flush();os._exit(code)
