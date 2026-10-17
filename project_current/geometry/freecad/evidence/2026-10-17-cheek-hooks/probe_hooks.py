from pathlib import Path
import sys,json,traceback
sys.dont_write_bytecode=True
OUT=Path(__file__).parent;sys.path.insert(0,str(OUT/'runtime'))
import FreeCAD as App
from freecad_tools import cheek_hooks as hooks,cheek_steel as cheek
from freecad_tools.geometry import bounds
d=App.openDocument(str(OUT/'Before.FCStd'));objects=hooks.steel_objects(d)
report=dict(status='STARTED',walls=[])
try:
 for name in cheek.HOSTS:
    inp=d.getObject('Steel'+name+'Inputs');hooks.configure(inp,{})
    rows=cheek.layout(inp);host=hooks.envelope(inp);cb=bounds(hooks.local(inp.Cap.Shape,inp.CageFrame))
    back=bounds(hooks.local(inp.Backwall.Shape,inp.CageFrame));chosen={};trials=[]
    for ident,row in rows.items():
      if not ident.startswith('MH'):continue
      z=row['points'][0][2]*25.4
      for end in ('start','end'):
        rear=(end=='start')==(inp.Host.SupportID=='EB1')
        receiver=inp.Cap if cb.ZMin+3.25*25.4<=z<=cb.ZMax-3.25*25.4 else inp.Backwall if rear and z>cb.ZMax else None
        if receiver is None:
          trials.append(dict(id=ident,end=end,status='NO_RECEIVER',reason='No adjacent cap/backwall with required cover at retained mat elevation'));continue
        for offset in (['3.25 in','4.25 in','4.75 in','5.25 in'] if receiver==inp.Cap else ['2.25 in','3.25 in','4.25 in']):
          spec=dict(offset=offset,receiver=receiver.Name,receiver_kind='cap' if receiver==inp.Cap else 'backwall')
          shape=hooks.swept(hooks.bent_row(inp,row,{end:spec}),inp.CageFrame)
          cover=hooks.solid_cover(shape,host,inp.CageFrame);clash,nearest=hooks.collisions(shape,objects,inp.Prefix+ident,inp.CageFrame)
          embedded=hooks.local(shape,inp.CageFrame).common(hooks.local(receiver.Shape,inp.CageFrame)).Volume/25.4**3
          ok=cover['status']=='PASS' and not clash and embedded>0
          trial=dict(id=ident,end=end,status='PASS' if ok else 'DOES_NOT_FIT',spec=spec,cover=cover,clashes=clash,nearest=nearest,embedded_in3=embedded)
          trials.append(trial)
          if ok:
            chosen.setdefault(ident,{})[end]=spec
            break
    report['walls'].append(dict(host=name,backwall_bounds={k:getattr(back,k)/25.4 for k in ('XMin','XMax','YMin','YMax','ZMin','ZMax')},hooks=chosen,trials=trials))
    (OUT/'hook-fit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(host=name,hooks=chosen)),flush=True)
 report['status']='COMPLETE'
except Exception:report.update(status='FAIL',error=traceback.format_exc());raise
finally:(OUT/'hook-fit.json').write_text(json.dumps(report,indent=2))
App.closeDocument(d.Name)
