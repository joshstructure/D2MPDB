from pathlib import Path
import sys,json,os,traceback,copy,zipfile,xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad';OUT=ROOT/'.validation/pier-wall'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(MAIN/'runtime'))
import FreeCAD as App
from freecad_tools import bridge,native_archive,pier_wall_rings as pw

def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n')

def new_views(source,candidate):
    # Assign native Part/Rebar view records from actual existing counterparts.
    # Existing view records/resources are kept by native_archive.preserve.
    with zipfile.ZipFile(source) as z:old=ET.fromstring(z.read('GuiDocument.xml'))
    with zipfile.ZipFile(candidate) as z:data={n:z.read(n) for n in z.namelist()}
    gui=ET.fromstring(data['GuiDocument.xml']);vp=gui.find('ViewProviderData')
    oldviews={x.get('name'):x for x in old.find('ViewProviderData')}
    for o in list(vp):
        name=o.get('name')
        if name in oldviews:continue
        props=o.find('Properties')
        visibility=props.find("Property[@name='Visibility']/Bool")
        if visibility is not None:visibility.set('value','false' if name.endswith(('Path','Paths')) else 'true')
        color=props.find("Property[@name='ShapeColor']/PropertyColor")
        if color is not None:
            # FreeCAD serializes RGBA as unsigned 0xRRGGBBAA.
            rgb=0x315D82FF if name.startswith('PierWallRing') else 0x24734BFF if 'V' in name[-5:] else 0xB46A29FF
            color.set('value',str(rgb))
        tr=props.find("Property[@name='Transparency']/Integer")
        if tr is not None:tr.set('value','0')
    data['GuiDocument.xml']=ET.tostring(gui,encoding='utf-8',xml_declaration=True)
    with zipfile.ZipFile(candidate,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in data.items():z.writestr(n,b)

manifest=json.loads((MAIN/'manifest.json').read_text());source=MAIN/manifest['model']['path']
snapshot=json.loads((ROOT/'.validation/pier-wall-source.json').read_text())
version=sys.argv[1] if len(sys.argv)>1 else 'v1';record={'status':'STARTED','source_sha256':native_archive.sha(source)}
report=OUT/f'build-{version}.json';doc=None
try:
    assert record['source_sha256']==manifest['model']['sha256']
    print('Opening source',flush=True);doc=App.openDocument(str(source))
    protected=[o.Name for o in doc.Objects if o.Name!='BridgeAssembly']
    before=bridge.source_state(doc,protected);record['protected_objects']=len(protected)
    oldgroup=[o.Name for o in doc.BridgeAssembly.Group]
    print('Creating native steel',flush=True)
    inp=pw.create(doc,snapshot,snapshot['sha256'],'project_current/pier_wall/selected_case.json')
    print('Checking solids and intersections',flush=True)
    record['validation']=pw.validate(inp);dump(report,record)
    assert record['validation']['status']=='PASS',record['validation']
    assert before==bridge.source_state(doc,protected),'Existing model changed'
    assert [o.Name for o in doc.BridgeAssembly.Group]==oldgroup+[pw.PREFIX]
    # Test native input/dependency edits, including count and ring-height changes.
    print('Testing native edits',flush=True)
    original={o.Name:o.Shape.copy() for o in doc.Objects if 'Shape' in o.PropertiesList and o.Name.startswith(('PierWallSteel','PierWallRing'))}
    oldpitch=inp.MaximumSpacing.Value;oldring=inp.FirstRingTop.Value
    inp.MaximumSpacing='10 in';inp.FirstRingTop=oldring+pw.IN;pw.regenerate(inp)
    assert doc.PierWallSteelQuantities.TotalBars>record['validation']['bar_count']
    assert abs(doc.PierWallRingP1R1.TopAboveWallBottom.Value-oldring-pw.IN)<1e-6
    inp.MaximumSpacing=oldpitch;inp.FirstRingTop=oldring;pw.regenerate(inp)
    for n,s in original.items():
        t=doc.getObject(n).Shape
        assert abs(s.cut(t).Volume)<1e-5 and abs(t.cut(s).Volume)<1e-5,n
    record['native_edit_restore']=True
    assert before==bridge.source_state(doc,protected),'Existing model changed on regeneration'
    raw=OUT/f'native-{version}.FCStd';candidate=OUT/f'candidate-{version}.FCStd'
    for o in doc.Objects:o.purgeTouched()
    print('Saving candidate',flush=True);doc.saveAs(str(raw))
    record['archive']=native_archive.preserve(source,raw,candidate,protected,record['source_sha256'])
    new_views(source,candidate)
    App.closeDocument(doc.Name);doc=None
    print('Cold reopening',flush=True);doc=App.openDocument(str(candidate))
    assert before==bridge.source_state(doc,protected),'Cold reopen changed existing model'
    inp=doc.PierWallSteelInputs
    record['cold_reopen_validation']=pw.validate(inp,False)
    assert record['cold_reopen_validation']['status']=='PASS'
    assert type(inp.Proxy).__name__=='InputsProxy'
    assert type(doc.PierWallRingP1R1.Proxy).__name__=='RingProxy'
    assert type(doc.PierWallSteelF1H01.Proxy).__name__=='RebarProxy'
    record.update(status='VERIFIED_CAD_CALCULATION_RECONCILIATION_PENDING',cold_reopen=True,
                  objects=len(doc.Objects),candidate=str(candidate),candidate_sha256=native_archive.sha(candidate),
                  source_unchanged=native_archive.sha(source)==record['source_sha256'])
    assert record['source_unchanged'];dump(report,record)
    print(json.dumps({k:v for k,v in record.items() if k not in ('validation','cold_reopen_validation')},indent=2),flush=True)
    code=0
except Exception:
    record.update(status='FAIL',error=traceback.format_exc());dump(report,record);traceback.print_exc();code=1
finally:
    if doc:App.closeDocument(doc.Name)
sys.stdout.flush();sys.stderr.flush();os._exit(code)
