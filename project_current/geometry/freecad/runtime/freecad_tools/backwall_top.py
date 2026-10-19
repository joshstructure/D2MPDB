"""D-053: two planar backwall tops with local ramp slab thickening."""
import json
import FreeCAD as App
from . import bridge, mse_revision as rev, return_cheek_details as returns
from . import landing_quantities, cheek_hooks, backwall_extensions, cheek_steel, design_steel
from .mse import Serializable
FT=304.8; IN=25.4

def upward_faces(shape):
    return [f for f in shape.Faces if f.normalAt(sum(f.ParameterRange[:2])/2,
            sum(f.ParameterRange[2:])/2).z>.5]

class BackwallTopProxy(Serializable):
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        c=obj.PGL;m=bridge.model(c);r=bridge.support_data(c)[obj.SupportID]
        a,b=(r['station']-r['width']/2,r['datum']) if obj.SupportID=='EB1' else (r['datum'],r['station']+r['width']/2)
        half=c.EndCapLength.Value/2;x=(a-m.start)*FT
        top=lambda y:float(m.deck_top(r['datum'],y/FT))*FT-obj.TopDrop.Value
        face=rev.closed_face([App.Vector(x,-half,r['top']*FT),App.Vector(x,half,r['top']*FT),
            App.Vector(x,half,top(half)),App.Vector(x,0,top(0)),App.Vector(x,-half,top(-half))])
        shape=face.extrude(App.Vector((b-a)*FT,0,0));shape.Placement=c.Frame
        if not shape.isValid() or len(shape.Solids)!=1:raise ValueError('Invalid simple backwall '+obj.Name)
        obj.Shape=shape;obj.NetVolume=shape.Volume
        obj.Label=obj.SupportID+' backwall - two planar top slopes'

def thicken(original,wall,depth):
    # Project the actual trimmed walking faces downward. Intersecting those
    # prisms with the two upward backwall-top prisms preserves the slab footprint
    # and all walking faces; only the underside over the backwall changes.
    roof=upward_faces(wall.Shape);tops=upward_faces(original)
    if len(roof)>2 or not roof or not tops:raise ValueError('Expected at most two backwall top planes')
    regions=[f.extrude(App.Vector(0,0,depth)) for f in roof]
    reaches=[f.extrude(App.Vector(0,0,-depth)) for f in tops]
    a=regions[0].multiFuse(regions[1:]) if len(regions)>1 else regions[0]
    b=reaches[0].multiFuse(reaches[1:]) if len(reaches)>1 else reaches[0]
    fill=a.common(b).removeSplitter()
    shape=original.fuse(fill).removeSplitter()
    if not shape.isValid() or len(shape.Solids)!=1:raise ValueError('Invalid thickened landing '+wall.Name)
    if abs(shape.common(wall.Shape).Volume)>1e-7:raise ValueError('Backwall top intrudes into landing slab')
    return shape

class LandingTopProxy(returns.ReturnLandingProxy):
    def execute(self,obj):
        super().execute(obj)
        obj.Shape=thicken(obj.Shape,obj.BackwallTopSource,max(2*obj.Thickness.Value,2*obj.BackwallTopSource.TopDrop.Value))
        landing_quantities.update(obj)

def apply(doc,model_id):
    """Apply in a caller-owned transaction; never save a document."""
    if any('TopDrop' in doc.getObject('BridgeBackwall'+s).PropertiesList for s in ['EB1','EB2']):
        raise ValueError('Simple tops are already installed; edit their native controls instead of repeating installation')
    changed=[]
    for sid,side in [('EB1','A'),('EB2','B')]:
        wall=doc.getObject('BridgeBackwall'+sid)
        rev.setprop(wall,'App::PropertyLength','TopDrop','4.25 in','Backwall top')
        rev.setprop(wall,'App::PropertyString','TopRuleSource','D-053: two straight transverse slopes following the FFBW deck crossfall, level through thickness; local ramp slab thickening.','Backwall top')
        rev.setprop(wall,'App::PropertyString','TopNotebookModelID',model_id,'Backwall top')
        BackwallTopProxy(wall);wall.Proxy.execute(wall);changed.append(wall.Name)
        slab=doc.getObject(side+'_BridgeLandingAtReturns')
        rev.setprop(slab,'App::PropertyLink','BackwallTopSource',wall,'Backwall connection')
        LandingTopProxy(slab);slab.Proxy.execute(slab);changed.append(slab.Name)
        inp=doc.getObject('SteelBridgeBackwall'+sid+'Inputs')
        settings=json.loads(inp.HorizontalLevelAdjustmentsJSON)
        settings.update(F1H05='-0.375 in',F2H05='-0.375 in')
        inp.HorizontalLevelAdjustmentsJSON=json.dumps(settings)
        cheek_hooks.refresh(inp)
        changed += [inp.Name,inp.Prefix+'Quantities',inp.Prefix+'Schedule']
        changed += [inp.Prefix+i+t for i in ['F1H05','F2H05'] for t in ['','Path']]
    # Lower MH09 and the next row together: retain the two EB1 standard hooks
    # while keeping every horizontal spacing at or below the selected 10 in.
    for index in [1,2]:
        inp=doc.getObject('SteelBridgeCheekEB1'+str(index)+'Inputs')
        labels={bar.Name:(bar.Label,bar.Mark) for bar in doc.getObject(inp.Prefix+'Quantities').Bars}
        rows=json.loads(inp.LayoutJSON);z0=cheek_steel.web_limits(inp)[4]
        levels=json.loads(inp.HorizontalStationOverridesJSON or '{}')
        for ident in ['MH09','MH10']:
            offset=rows[ident]['points'][0][2]-z0/IN-.625
            levels[ident]=format(offset,'.15g')+' in'
        inp.HorizontalStationOverridesJSON=json.dumps(levels)
        cheek_hooks.refresh(inp)
        for bar in doc.getObject(inp.Prefix+'Quantities').Bars:bar.Label,bar.Mark=labels[bar.Name]
        design_steel.write_wall_schedule(inp,doc.getObject(inp.Prefix+'Schedule'),doc.getObject(inp.Prefix+'Quantities').Bars)
        changed += [inp.Name,inp.Prefix+'Quantities',inp.Prefix+'Schedule']
        changed += [inp.Prefix+i+t for i in ['MH09','MH10'] for t in ['','Path']]
    for obj in doc.Objects:obj.purgeTouched()
    sheets=[doc.BridgeConcreteSchedule]+[doc.getObject('SteelBridgeCheekEB1'+str(i)+'Schedule') for i in [1,2]]
    for sheet in sheets:sheet.touch()
    doc.recompute(sheets)
    changed.append('BridgeConcreteSchedule')
    return changed
