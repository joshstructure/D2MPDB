from pathlib import Path
import sys,os,json,traceback
sys.dont_write_bytecode=True
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad';OUT=ROOT/'.validation/pier-wall'
sys.path.insert(0,str(MAIN/'runtime'))
import FreeCAD as App,FreeCADGui as Gui
from PySide import QtCore,QtWidgets
Gui.showMainWindow();Gui.getMainWindow().hide()
from pivy import coin
from freecad_tools import pier_wall_rings as pw,native_archive,bridge
from freecad_tools import cap_cages,mse,drainage_trial,adopt_drainage,current_source,design_steel,pedestal_ubars,pedestal_edges,pedestal_contact,backwall_extensions,backwall_top,mse_revision,mse_corrections,mse_wall_tops,cheek_steel,lug_wwr,deck_edge_details,return_cheek_details,standard_chamfers,end_bent_closure,geotechnical_straps,cheek_hooks,pier_cheeks,level_seats

def render():
    doc=None;result={}
    try:
        path=OUT/'candidate-v5.FCStd';digest=native_archive.sha(path)
        doc=App.openDocument(str(path));App.setActiveDocument(doc.Name)
        inp=doc.PierWallSteelInputs
        gui_check=json.loads((OUT/'gui-build.json').read_text())
        assert gui_check['status']=='PASS' and gui_check['candidate_sha256']==digest
        result['ordinary_native_recompute']=gui_check['ordinary_native_recompute']
        for obj in doc.Objects:
            if obj.TypeId=='App::DocumentObjectGroup':obj.ViewObject.Visibility=True
        for obj in doc.Objects:
            if obj.TypeId!='App::DocumentObjectGroup':obj.ViewObject.Visibility=False
        for n in ['BridgeCapPier','BridgePierWallSolid',*[f'BridgePilePierP{k}' for k in range(1,5)]]:
            o=doc.getObject(n);o.ViewObject.Visibility=True;o.ViewObject.Transparency=85 if n=='BridgePierWallSolid' else 60
            o.ViewObject.ShapeColor=(.74,.78,.81);o.ViewObject.LineColor=(.3,.35,.4)
            o.ViewObject.DisplayMode='Flat Lines';o.ViewObject.LineWidth=1.
        for o in [*doc.PierWallSteelQuantities.Bars,*doc.PierWallSteelQuantities.Rings]:
            o.ViewObject.Visibility=True;o.ViewObject.Transparency=0
            if o.Name.startswith('PierWallRing'):color=(.2,.37,.52)
            else:color=(.14,.45,.29) if 'vertical' in o.Base.Family else (.71,.42,.16)
            o.ViewObject.ShapeColor=color;o.ViewObject.LineColor=color;o.ViewObject.DisplayMode='Flat Lines'
        d=pw.dimensions(inp)
        target=doc.BridgePGL.Frame.multVec(App.Vector(d['center_x']*25.4,0,(d['bottom']+d['height']/2)*25.4))
        view=Gui.activeDocument().activeView();view.setCameraType('Orthographic')
        for name,rot,height in [
          ('Pier_Wall_Steel_Isometric.png',App.Rotation(App.Vector(0,1,0),App.Vector(-.5,0,1),App.Vector(1,-.65,.4),'ZXY'),270),
          ('Pier_Wall_Steel_Elevation.png',App.Rotation(App.Vector(0,1,0),App.Vector(0,0,1),App.Vector(1,0,0),'ZXY'),245)]:
            rot=doc.BridgePGL.Frame.Rotation.multiply(rot);direction=rot.multVec(App.Vector(0,0,-1));distance=200000.
            cam=view.getCameraNode();cam.orientation.setValue(coin.SbRotation(*rot.Q));cam.position.setValue(*list(target-direction*distance))
            cam.focalDistance.setValue(distance);cam.height.setValue(height*25.4);cam.nearDistance.setValue(1.);cam.farDistance.setValue(500000.)
            Gui.updateGui();view.saveImage(str(OUT/name),1800,1400,'White')
        assert native_archive.sha(path)==digest
        result.update(status='PASS',native_render=True,model_unchanged=True)
    except Exception:result.update(status='FAIL',error=traceback.format_exc())
    finally:
        if doc:App.closeDocument(doc.Name)
        (OUT/'native-render.json').write_text(json.dumps(result,indent=2)+'\n')
        QtCore.QTimer.singleShot(100,QtWidgets.QApplication.instance().quit)
QtCore.QTimer.singleShot(500,render)
QtWidgets.QApplication.instance().exec()
os._exit(0)
