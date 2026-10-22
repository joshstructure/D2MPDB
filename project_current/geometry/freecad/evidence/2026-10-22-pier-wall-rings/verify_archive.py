from pathlib import Path
import copy,hashlib,json,zipfile,xml.etree.ElementTree as E
import FreeCAD
import Part
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad';OUT=ROOT/'.validation/pier-wall'
source=MAIN/json.loads((MAIN/'manifest.json').read_text())['model']['path'];candidate=OUT/'candidate-v5.FCStd'
def contents(p):
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        return {n:z.read(n) for n in z.namelist()}
a,b=contents(source),contents(candidate)
def canonical(node,data):
    node=copy.deepcopy(node)
    for el in node.iter():
        path=el.get('file')
        if path:el.set('file','sha256:'+hashlib.sha256(data[path]).hexdigest())
    return E.tostring(node)
def nodes(data,filename,path):return {o.get('name'):o for o in E.fromstring(data[filename]).find(path)}
old,new=nodes(a,'Document.xml','ObjectData'),nodes(b,'Document.xml','ObjectData')
changed=[n for n,o in old.items() if canonical(o,a)!=canonical(new[n],b)]
assert changed==['BridgeAssembly'],changed
ov,nv=nodes(a,'GuiDocument.xml','ViewProviderData'),nodes(b,'GuiDocument.xml','ViewProviderData')
viewchanges=[n for n,o in ov.items() if canonical(o,a)!=canonical(nv[n],b)]
assert not viewchanges,viewchanges
# New geometry must be exactly the independently checked headless geometry.
c=contents(OUT/'candidate-v2.FCStd');prior=nodes(c,'Document.xml','ObjectData');geometry=[]
for n,o in new.items():
    if n not in old:
        shape=o.find('./Properties/Property[@name="Shape"]')
        if shape is not None:
            previous=prior[n].find('./Properties/Property[@name="Shape"]')
            # Shape maps may change during GUI serialization; compare BRep bytes.
            sn=shape.find('Part').get('file');pn=previous.find('Part').get('file')
            if b[sn]!=c[pn]:
                current=Part.Shape();previous_shape=Part.Shape()
                current.importBrepFromString(b[sn].decode('ascii'))
                previous_shape.importBrepFromString(c[pn].decode('ascii'))
                assert current.isValid() and previous_shape.isValid(),n
                assert abs(current.cut(previous_shape).Volume)<1e-6 and abs(previous_shape.cut(current).Volume)<1e-6,n
            geometry.append(n)
report=dict(status='PASS',existing_native_objects_preserved=len(old)-1,existing_views_preserved=len(ov),
            only_existing_record_changed='BridgeAssembly: add PierWallSteel group',
            new_shapes_geometrically_equal_to_checked_candidate=len(geometry),
            view_resource_payloads_byte_identical=True,candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest())
(OUT/'archive-preservation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
