"""Create native GUI view providers, retaining original object and view records."""
from pathlib import Path
import sys,os,json,traceback,copy,zipfile,hashlib,xml.etree.ElementTree as E
sys.dont_write_bytecode=True
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad';OUT=ROOT/'.validation/pier-wall'
sys.path.insert(0,str(MAIN/'runtime'))
import FreeCAD as App,FreeCADGui as Gui
from PySide import QtCore,QtWidgets
Gui.showMainWindow();Gui.getMainWindow().hide()
from freecad_tools import cap_cages,mse,bridge,drainage_trial,adopt_drainage,current_source,design_steel,pedestal_ubars,pedestal_edges,pedestal_contact,backwall_extensions,backwall_top,mse_revision,mse_corrections,mse_wall_tops,cheek_steel,lug_wwr,deck_edge_details,return_cheek_details,standard_chamfers,end_bent_closure,geotechnical_straps,cheek_hooks,pier_cheeks,level_seats,native_archive,pier_wall_rings as pw

def preserve_views(source,candidate):
    with zipfile.ZipFile(source) as z:old={n:z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(candidate) as z:data={n:z.read(n) for n in z.namelist()}
    original=E.fromstring(old['GuiDocument.xml']);gui=E.fromstring(data['GuiDocument.xml']);vp=gui.find('ViewProviderData')
    oldviews={o.get('name'):o for o in original.find('ViewProviderData')}
    for o in list(vp):
        name=o.get('name')
        if name in oldviews:
            new=copy.deepcopy(oldviews[name])
            for el in new.iter():
                ref=el.get('file')
                if ref:
                    content=old[ref];dest='view_'+hashlib.sha256(content).hexdigest();data[dest]=content;el.set('file',dest)
            index=list(vp).index(o);vp.remove(o);vp.insert(index,new)
    for el in gui.iter():
        ref=el.get('file')
        if ref:
            content=data[ref];dest='view_'+hashlib.sha256(content).hexdigest();data[dest]=content;el.set('file',dest)
    data['GuiDocument.xml']=E.tostring(gui,encoding='utf-8',xml_declaration=True)
    with zipfile.ZipFile(candidate,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in data.items():z.writestr(n,b)

def run():
    report={};doc=None
    try:
        source=MAIN/json.loads((MAIN/'manifest.json').read_text())['model']['path'];sourcehash=native_archive.sha(source)
        print('Opening original GUI model',flush=True)
        doc=App.openDocument(str(source));protected=[o.Name for o in doc.Objects if o.Name!='BridgeAssembly']
        before=bridge.source_state(doc,protected)
        print('Creating native GUI steel and ring views',flush=True)
        snapshot=json.loads((ROOT/'.validation/pier-wall-source.json').read_text())
        inp=pw.create(doc,snapshot,snapshot['sha256'],'project_current/pier_wall/selected_case.json')
        for o in doc.PierWallSteelQuantities.Rings:
            bridge.initialize_display(o);o.ViewObject.ShapeColor=(.2,.37,.52);o.ViewObject.LineWidth=1
        for o in doc.PierWallSteelQuantities.Bars:
            o.ViewObject.ShapeColor=(.14,.45,.29) if 'vertical' in o.Base.Family else (.71,.42,.16)
        doc.PierWallSteelPaths.ViewObject.Visibility=False
        assert before==bridge.source_state(doc,protected),'GUI creation changed original object state'
        for o in doc.Objects:o.purgeTouched()
        print('Saving GUI model',flush=True)
        raw=OUT/'native-gui.FCStd';candidate=OUT/'candidate-v5.FCStd';doc.saveAs(str(raw))
        archive=native_archive.preserve(source,raw,candidate,protected,sourcehash,keep_candidate_views=True)
        preserve_views(source,candidate)
        App.closeDocument(doc.Name);doc=None
        print('Cold opening GUI candidate',flush=True)
        doc=App.openDocument(str(candidate))
        assert before==bridge.source_state(doc,protected),'GUI cold reopen changed originals'
        inp=doc.PierWallSteelInputs
        check=pw.validate(inp,False);assert check['status']=='PASS',check
        print('Checking ordinary native dependency recompute',flush=True)
        for o in doc.Objects:o.purgeTouched()
        thick=inp.RingThickness.Value;inp.RingThickness=thick+pw.IN/4;doc.recompute()
        s=doc.PierWallRingP1R1.Shape.copy();s.Placement=inp.PGL.Frame.inverse().multiply(s.Placement)
        assert abs(s.optimalBoundingBox(False,False).ZLength-thick-pw.IN/4)<1e-6
        inp.RingThickness=thick;doc.recompute()
        assert before==bridge.source_state(doc,protected),'Ordinary recompute changed originals'
        report=dict(status='PASS',candidate=str(candidate),candidate_sha256=native_archive.sha(candidate),
                    source_sha256=sourcehash,protected_objects=len(protected),native_gui_views=True,
                    ordinary_native_recompute=True,cold_gui_reopen=True,objects=len(doc.Objects),
                    validation=check,archive=archive)
        assert native_archive.sha(source)==sourcehash
    except Exception:report=dict(status='FAIL',error=traceback.format_exc());traceback.print_exc()
    finally:
        if doc:App.closeDocument(doc.Name)
        (OUT/'gui-build.json').write_text(json.dumps(report,indent=2))
        QtCore.QTimer.singleShot(100,QtWidgets.QApplication.instance().quit)
QtCore.QTimer.singleShot(500,run);QtWidgets.QApplication.instance().exec();os._exit(0)
