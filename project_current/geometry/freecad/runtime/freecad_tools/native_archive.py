"""Preserve unchanged native object records and views in a new FCStd candidate.

This file-only step copies original native records, BReps and view resources;
it never flattens an editable object or edits the authoritative source file.
"""
from pathlib import Path
import copy,hashlib,json,zipfile,xml.etree.ElementTree as ET

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def preserve(source,candidate,destination,retained,source_hash):
    source=Path(source);candidate=Path(candidate);destination=Path(destination)
    if sha(source)!=source_hash:raise ValueError('Authoritative source changed')
    if destination.exists() or destination in [source,candidate]:raise ValueError('Use a fresh disposable output')
    with zipfile.ZipFile(source) as z:original={n:z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(candidate) as z:updated={n:z.read(n) for n in z.namelist()}
    old=ET.fromstring(original['Document.xml']);new=ET.fromstring(updated['Document.xml'])
    olddata={o.get('name'):o for o in old.find('ObjectData')};ndata=new.find('ObjectData')
    newdata={o.get('name'):o for o in ndata};retained=set(retained)
    if not retained<=set(olddata)&set(newdata):raise ValueError('Missing retained object')
    # The wall-specific Arch subclass prevents a later steel count edit from
    # touching/rebuilding its concrete host. Native shape and links are unchanged.
    for name,node in newdata.items():
        if name.startswith('SteelBridge') and node.find('./Properties/Property[@name="CageInputs"]') is not None:
            proxy=node.find('./Properties/Property[@name="Proxy"]/Python')
            if proxy is None or proxy.get('module')!='freecad_tools.cap_cages' or proxy.get('class')!='RebarProxy':raise ValueError('Unexpected new wall bar controller')
            proxy.set('module','freecad_tools.design_steel');proxy.set('class','WallRebarProxy')
    candidate_refs={el.get('file') for n,o in newdata.items() if n not in retained for el in o.iter() if el.get('file')}
    copied=[]
    for name in sorted(retained):
        node=copy.deepcopy(olddata[name]);index=list(ndata).index(newdata[name])
        for el in node.iter():
            filename=el.get('file')
            if not filename:continue
            if filename not in original:raise ValueError('Missing original native resource '+filename)
            destname=filename
            if filename in candidate_refs and filename in updated and updated[filename]!=original[filename]:
                destname='preserved_'+hashlib.sha256(original[filename]).hexdigest()[:16]+'_'+filename
                el.set('file',destname)
            updated[destname]=original[filename];copied.append(destname)
        ndata.remove(newdata[name]);ndata.insert(index,node)
    # Keep native object Names, Links, Expressions and controller classes. Only
    # removed cap grid objects and added wall steel differ from the old graph.
    newnames={o.get('name') for o in new.findall('./Objects/Object')}
    if newnames!={o.get('name') for o in ndata}:raise ValueError('Native name table mismatch')
    gui=ET.fromstring(original['GuiDocument.xml']);vp=gui.find('ViewProviderData')
    views={v.get('name'):v for v in vp};types={o.get('name'):o.get('type') for o in new.findall('./Objects/Object')}
    for child in list(vp):vp.remove(child)
    for name in sorted(newnames):
        if name in views:node=copy.deepcopy(views[name])
        else:
            typ=types[name]
            template='CageEB1' if typ=='App::DocumentObjectGroup' else 'CageEB1Schedule' if typ=='Spreadsheet::Sheet' else 'CageEB1Inputs' if typ=='App::FeaturePython' else 'CageEB1Long01Path' if name.endswith('Path') else 'CageEB1Long01'
            if typ not in ['App::DocumentObjectGroup','Spreadsheet::Sheet','App::FeaturePython','Part::FeaturePython']:raise ValueError('Unsupported new view type '+typ)
            node=copy.deepcopy(views[template]);node.set('name',name)
        for el in node.iter():
            filename=el.get('file')
            if filename:
                if filename not in original:raise ValueError('Missing native view resource '+filename)
                destname='retained_view_'+filename
                el.set('file',destname);updated[destname]=original[filename]
        vp.append(node)
    vp.set('Count',str(len(newnames)))
    updated['Document.xml']=ET.tostring(new,encoding='utf-8',xml_declaration=True)
    updated['GuiDocument.xml']=ET.tostring(gui,encoding='utf-8',xml_declaration=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in updated.items():z.writestr(name,data)
    with zipfile.ZipFile(destination) as z:
        if z.testzip():raise ValueError('Native archive integrity failure')
    if sha(source)!=source_hash:raise ValueError('Source bytes changed during staging')
    return dict(status='STAGED',source_sha256=source_hash,output_sha256=sha(destination),retained_objects=len(retained),native_resources_copied=len(copied),view_count=len(newnames),source_unchanged=True)
