"""Raise the low end-bent MSE panels into the cheek-wall lug recess."""
import json
import FreeCAD as App,Part
from . import mse,mse_revision as rev,mse_corrections as fix,drainage_trial as dt
IN=25.4;FT=304.8
WALLS={'EB1':['A5','A6','A7'],'EB2':['B1','B6','B7']}

class EndBentProfileProxy(rev.WallProfileProxy):
    def execute(self,o):
        bottom=min(c.WallBottomElevation.Value for c in o.CheekSources)
        target=bottom-o.VerticalJointGap.Value
        o.EndBentTopElevation=target
        o.TopControls=[App.Vector(p.x,p.y,target if not n else p.z) for p,n in zip(o.TopControls,o.TopSourceNames)]
        super().execute(o)

def apply(doc,vertical_gap='0.5 in',horizontal_gap='0.5 in'):
    gap=App.Units.Quantity(vertical_gap).Value;hgap=App.Units.Quantity(horizontal_gap).Value
    if abs(gap-.5*IN)>1e-9 or abs(hgap-.5*IN)>1e-9:raise ValueError('This detail requires the user-specified half-inch gaps')
    if abs(doc.BridgePGL.MSEJointGap.Value-hgap)>1e-9:raise ValueError('Horizontal lug clearance differs from requested gap')
    rows=[];profiles=[]
    for sid,names in WALLS.items():
        cheeks=[doc.getObject('BridgeCheek'+sid+str(j)) for j in [1,2]]
        for name in names:
            w=doc.getObject('Wall'+name+'Profile');old=[p.z for p,n in zip(w.TopControls,w.TopSourceNames) if not n]
            rev.setprop(w,'App::PropertyLinkList','CheekSources',cheeks,'End-bent tuck')
            rev.setprop(w,'App::PropertyLength','VerticalJointGap',vertical_gap,'End-bent tuck')
            rev.setprop(w,'App::PropertyLength','HorizontalLugGap',horizontal_gap,'End-bent tuck')
            rev.setprop(w,'App::PropertyLength','EndBentTopElevation','0 ft','End-bent tuck')
            EndBentProfileProxy(w);w.Proxy.execute(w);profiles.append(w)
            rows.append({'wall':name,'end_bent':sid,'old_top_ft':old[0]/FT,'new_top_ft':w.EndBentTopElevation.Value/FT,'raise_in':(w.EndBentTopElevation.Value-old[0])/IN})
    # Rebuild only the changed wall solids and their finished mitres. Walking
    # surfaces, coping/barrier paths, piles and reinforcement are not altered.
    raws=[doc.getObject(w.Name[:-7]) for w in profiles]
    for o in doc.Objects:o.purgeTouched()
    for o in raws:o.touch()
    doc.recompute(raws)
    for w in profiles:
        s=doc.getObject(w.Name[:-7]+'MitredSource');s.Proxy.execute(s)
    remaining=[o for o in doc.MSEAssembly.FinishedConcrete if o.Name.startswith('Wall')]
    while remaining:
        ready=[o for o in remaining if not any(t in remaining for t in o.ContactSources)]
        if not ready:raise ValueError('Wall contact dependency cycle')
        for o in ready:o.Proxy.execute(o);remaining.remove(o)
    annotations=[]
    for w in profiles:
        host=doc.getObject(w.Name[:-7]+'Mitred');name='DXFWallTopElevation'+w.Name[4:-7]
        o=doc.addObject('App::FeaturePython',name);dt.ElevationProxy(o)
        spec={'kind':'wall_under_cheek','source':host.Name,'profile':w.Name}
        for typ,n,v in [('App::PropertyString','PointDefinitions',json.dumps([spec])),('App::PropertyString','PointID','MSE-'+w.Name[4:-7]+'-TOP'),('App::PropertyLinkList','Sources',[host,w]),('App::PropertyVector','MeasuredPoint',App.Vector()),('App::PropertyLength','Elevation','0 ft'),('App::PropertyVector','TextOffset',w.Normal*3*FT+App.Vector(0,0,6*IN))]:rev.setprop(o,typ,n,v,'End-bent top annotation')
        o.Label=o.PointID+' - half inch below cheek';doc.SlabElevations.addObject(o);o.Proxy.execute(o)
        lead=doc.addObject('Part::FeaturePython',name+'Leader');mse.prop(lead,'App::PropertyLink','Annotation',o);dt.LeaderProxy(lead);lead.Proxy.execute(lead);doc.SlabElevations.addObject(lead);annotations.append(o.Name)
    for o in doc.SlabElevations.Group:
        if 'PointDefinitions' in o.PropertiesList:o.Proxy.execute(o)
    doc.BridgeGeometryChecks.Proxy.execute(doc.BridgeGeometryChecks)
    for o in doc.Objects:o.purgeTouched()
    return {'wall_changes':rows,'new_annotations':annotations,'vertical_gap_in':gap/IN,'horizontal_gap_in':hgap/IN}
