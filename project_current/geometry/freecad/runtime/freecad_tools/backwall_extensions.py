"""Native backwall horizontals extended through adjoining cheek-wall webs."""
import copy,json,math
import FreeCAD as App
from . import design_steel as steel,bridge,cap_cages as cap,cheek_hooks as hooks
from .mse import Serializable
from .pedestal_edges import prop
from .geometry import bounds,length,result
IN=25.4;TOL=.0254

def envelope(inp):
    return hooks.local(inp.Host.Shape,inp.CageFrame).multiFuse([hooks.local(o.Shape,inp.CageFrame) for o in [inp.Cap]+list(inp.ReceiverCheeks)]).removeSplitter()

def limits(inp):
    bs=sorted([bounds(hooks.local(o.Shape,inp.CageFrame)) for o in inp.ReceiverCheeks],key=lambda b:b.YMin)
    if len(bs)!=2:raise ValueError('Two explicit receiver cheeks required')
    return bs[0].YMin+inp.ExtensionEndCover.Value,bs[-1].YMax-inp.ExtensionEndCover.Value

def layout(inp):
    if inp.Host.ComponentKind!='Backwall':raise ValueError('Backwall extension adapter requires a backwall')
    # Keep the selected mat's native analytic source rows. The EB1 concrete roof
    # changed in a previous adopted revision; rebuilding that old grid here would
    # silently move unrelated verticals. Explicit changes to its original grid
    # controls require a separate rebase, rather than silently ignoring them.
    selected=json.loads(inp.SelectedGridInputsJSON)
    for name,value in selected.items():
        actual=getattr(inp,name)
        if (actual.Value if hasattr(actual,'Value') else actual)!=value:raise ValueError('Selected base mat changed: rebase '+name+' explicitly')
    rows=json.loads(inp.BaseLayoutJSON);lo,hi=limits(inp);adjust=json.loads(inp.HorizontalLevelAdjustmentsJSON)
    for ident,row in rows.items():
        if row['kind']!='wall_horizontal':continue
        pts=[list(pt) for pt in row['points']]
        pts[0][1]=lo/IN;pts[1][1]=hi/IN
        shift=length(adjust.get(ident,'0 in'))/IN
        for pt in pts:pt[2]+=shift
        row['points']=pts;row['family']+='; extended into cheeks'
    if inp.AddEndVerticals:
        for face in [1,2]:
            vertical=[row for k,row in rows.items() if k.startswith('F'+str(face)+'V')]
            for end,station in [('L',lo+cap.BAR_DIAMETER[inp.VerticalBar]*IN/2),('R',hi-cap.BAR_DIAMETER[inp.VerticalBar]*IN/2)]:
                nearest=min(vertical,key=lambda row:abs(row['points'][0][1]*IN-station))
                spacing=abs(nearest['points'][0][1]*IN-station)
                if spacing<2*cap.BAR_DIAMETER[inp.VerticalBar]*IN or spacing>inp.VerticalSpacing.Value+TOL:raise ValueError('Added vertical does not fit the retained spacing')
                ident='F'+str(face)+'VE'+end;row=copy.deepcopy(nearest)
                row.update(id=ident,family='Face '+str(face)+' added end vertical; into cheek',points=[(p[0],station/IN,p[2]) for p in nearest['points']],matching_bar_id=nearest['id'])
                rows[ident]=row
    return rows

class InputsProxy(Serializable):
    def __init__(self,o):o.Proxy=self
    def execute(self,o):
        q=o.Document.getObject(o.Prefix+'Quantities')
        labels={} if q is None else {b.Name:b.Label for b in q.Bars}
        o.CageFrame=o.PGL.Frame;o.LayoutJSON=json.dumps(layout(o))
        if o.AutoSync:
            steel.sync_wall(o)
            for name,label in labels.items():
                bar=o.Document.getObject(name)
                if bar is not None:bar.Label=label
            rows=json.loads(o.LayoutJSON);q=o.Document.getObject(o.Prefix+'Quantities')
            sh=o.Document.getObject(o.Prefix+'Schedule')
            for index,bar in enumerate(q.Bars,2):
                matching=rows[bar.Base.BarID].get('matching_bar_id')
                if matching:
                    bar.Mark=o.Document.getObject(o.Prefix+matching).Mark
                    if sh:sh.set('A'+str(index),"'"+bar.Mark)

def configure(inp,cheek_names,end_cover='3 in',add_verticals=True,level_adjustments=None):
    length(end_cover,positive=True)
    inp.AutoSync=False
    if 'BaseLayoutJSON' not in inp.PropertiesList:
        prop(inp,'App::PropertyString','BaseLayoutJSON',inp.LayoutJSON,'Selected base mat')
        selected={}
        for name in ['VerticalBar','HorizontalBar','VerticalSpacing','HorizontalSpacing','Cover','SchematicEmbedment']:
            value=getattr(inp,name);selected[name]=value.Value if hasattr(value,'Value') else value
        prop(inp,'App::PropertyString','SelectedGridInputsJSON',json.dumps(selected),'Selected base mat')
    prop(inp,'App::PropertyLinkList','ReceiverCheeks',[inp.Document.getObject(n) for n in cheek_names],'Backwall extensions')
    prop(inp,'App::PropertyLength','ExtensionEndCover',end_cover,'Backwall extensions')
    prop(inp,'App::PropertyBool','AddEndVerticals',add_verticals,'Backwall extensions')
    prop(inp,'App::PropertyString','HorizontalLevelAdjustmentsJSON',json.dumps(level_adjustments or {}),'Backwall extensions')
    prop(inp,'App::PropertyString','ExtensionBasis','2026-10-17 user direction: extend horizontal backwall steel into cheeks to the cover limit; add matching end verticals where spacing and physical fit permit.','Backwall extensions')
    InputsProxy(inp);inp.AutoSync=True
    hooks.refresh(inp)
    q=inp.Document.getObject(inp.Prefix+'Quantities');rows=json.loads(inp.LayoutJSON)
    for bar in q.Bars:
        row=rows[bar.Base.BarID]
        if 'matching_bar_id' in row:bar.Mark=inp.Document.getObject(inp.Prefix+row['matching_bar_id']).Mark
    steel.write_wall_schedule(inp,inp.Document.getObject(inp.Prefix+'Schedule'),q.Bars)
    inp.Document.recompute([inp.Document.getObject(inp.Prefix+'Schedule')])

def validate(inp,before_shapes=None):
    doc=inp.Document;checks=steel.wall_geometry_checks(inp);rows=json.loads(inp.LayoutJSON);q=doc.getObject(inp.Prefix+'Quantities')
    env=envelope(inp);lo,hi=limits(inp);objects=hooks.steel_objects(doc);measurements=[];clashes=[];historical=[]
    before_shapes=before_shapes or {}
    changed=[b for b in q.Bars if rows[b.Base.BarID]['kind']=='wall_horizontal' or 'matching_bar_id' in rows[b.Base.BarID]]
    for bar in changed:
        sl=hooks.local(bar.Shape,inp.CageFrame);bb=bounds(sl);row=rows[bar.Base.BarID]
        cv=hooks.solid_cover(sl,env,minimum=inp.Cover.Value);cv['name']=bar.Name+'_combined_concrete_cover';checks.append(cv)
        if row['kind']=='wall_horizontal':
            checks.append(result(bar.Name+'_physical_end_cover_limit',abs(bb.YMin-lo)<TOL and abs(bb.YMax-hi)<TOL,start_in=bb.YMin/IN,end_in=bb.YMax/IN))
        else:
            partner=doc.getObject(inp.Prefix+row['matching_bar_id']);pb=bounds(hooks.local(partner.Shape,inp.CageFrame));spacing=abs(bb.Center.y-pb.Center.y)
            checks.append(result(bar.Name+'_added_vertical_spacing',spacing>=bar.Diameter.Value-TOL and spacing<=inp.VerticalSpacing.Value+TOL,centers_in=spacing/IN,clear_in=(spacing-bar.Diameter.Value)/IN))
        failures,nearest=hooks.collisions(bar.Shape,objects,bar.Name,inp.CageFrame)
        new_failures=[]
        for failure in failures:
            other=doc.getObject(failure['other']);old=before_shapes.get(bar.Name)
            prior=0. if old is None else abs(old.common(before_shapes.get(other.Name,other.Shape)).Volume)
            actual=failure['common_volume_in3']*IN**3
            if prior>0 and abs(actual-prior)<=max(1e-7,prior*1e-7):historical.append(dict(bar=bar.Name,**failure,prior_common_mm3=prior))
            else:new_failures.append(failure)
        if new_failures:clashes.extend(dict(bar=bar.Name,**f) for f in new_failures)
        checks.append(result(bar.Name+'_no_new_steel_overlap',not new_failures,failures=new_failures))
        measurements.append(dict(bar=bar.Name,kind=row['kind'],added='matching_bar_id' in row,length_in=bar.Length.Value/IN,minimum_cover_in=cv['cover_in'],nearest=nearest))
    sh=doc.getObject(inp.Prefix+'Schedule')
    checks.append(result(inp.Prefix+'_live_schedule',sh.BarNames==[b.Name for b in q.Bars] and float(sh.get('D'+str(sh.TotalRow)))==q.TotalBars and abs(float(sh.get('G'+str(sh.TotalRow)))-q.TotalSteelLength.Value/(12*IN))<1e-7 and all(sh.get('A'+str(i+2))==b.Mark for i,b in enumerate(q.Bars))))
    return dict(checks=checks,failures=[c for c in checks if c['status']!='PASS'],new_clashes=clashes,retained_existing_clashes=historical,measurements=measurements,bars=q.TotalBars)
