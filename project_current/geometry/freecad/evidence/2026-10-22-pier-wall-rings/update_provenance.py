"""Link the unchanged CAD details to the concurrently selected D-075 calculation."""
from pathlib import Path
import sys,json,os,zipfile,xml.etree.ElementTree as E,copy,hashlib
sys.dont_write_bytecode=True
ROOT=Path('C:/github/D2MPDB');MAIN=ROOT/'project_current/geometry/freecad';OUT=ROOT/'.validation/pier-wall'
sys.path.insert(0,str(MAIN/'runtime'))
import FreeCAD as App
from freecad_tools import bridge,pier_wall_rings as pw,native_archive
source=OUT/'candidate-v5.FCStd';candidate=OUT/'candidate-final.FCStd'
data=json.loads((ROOT/'.validation/pier-wall-current-source.json').read_text())
doc=App.openDocument(str(source));inp=doc.PierWallSteelInputs
before=bridge.source_state(doc,[o.Name for o in doc.Objects])
old=json.loads(inp.SourceCaseJSON);new=data['case']
changed=[k for k in new if new[k]!=old[k]]
assert set(changed)=={'length_in','height_in','pile_free_length_in'},changed
assert data['grid']['spacing']==inp.MaximumSpacing.Value/25.4
d=pw.dimensions(inp)
assert all(abs(d[a]-new[b])<.001 for a,b in [('length','length_in'),('thickness','thickness_in'),('height','height_in')])
inp.SourceCaseJSON=json.dumps(new);inp.SourceCaseSHA256=data['sha256']
inp.SourceFailuresJSON=json.dumps(data['failed_checks'])
inp.SourcePath='project_current/pier_wall/selected_case.json (D-075, 22 October 2026)'
inp.Limitations=pw.LIMITS;inp.ScheduleNote=pw.LIMITS
inp.EngineeringStatus='CAD dimensions match D-075 within 0.001 in; RING-GRID tolerance failure remains; engineering acceptance open'
sh=doc.PierWallSteelSchedule;sh.set('A'+str(sh.TotalRow+2),pw.LIMITS)
# The sole sheet edit is literal note text. Do not rebuild dependent geometry
# while changing provenance; the model has already passed native regeneration.
validation=pw.validate(inp,False);assert validation['status']=='PASS'
after=bridge.source_state(doc,list(before))
assert before==after,'Metadata update changed geometry, links or view state'
for o in doc.Objects:o.purgeTouched()
raw=OUT/'native-provenance.FCStd';doc.saveAs(str(raw));App.closeDocument(doc.Name)
# Preserve all original candidate records except these two metadata owners,
# including exact original GUI bytes (no new view providers are needed).
protected=[n for n in before if n not in ('PierWallSteelInputs','PierWallSteelSchedule')]
native_archive.preserve(source,raw,candidate,protected,native_archive.sha(source))
with zipfile.ZipFile(source) as z:original={n:z.read(n) for n in z.namelist()}
with zipfile.ZipFile(candidate) as z:updated={n:z.read(n) for n in z.namelist()}
gui=E.fromstring(original['GuiDocument.xml'])
for el in gui.iter():
    ref=el.get('file')
    if ref:updated[ref]=original[ref]
updated['GuiDocument.xml']=original['GuiDocument.xml']
with zipfile.ZipFile(candidate,'w',zipfile.ZIP_DEFLATED) as z:
    for n,b in updated.items():z.writestr(n,b)
doc=App.openDocument(str(candidate));assert doc.PierWallSteelInputs.SourceCaseSHA256==data['sha256']
assert before==bridge.source_state(doc,list(before))
report=dict(status='PASS',candidate=str(candidate),candidate_sha256=native_archive.sha(candidate),
            previous_case_sha256=json.loads((ROOT/'.validation/pier-wall-source.json').read_text())['sha256'],
            current_case_sha256=data['sha256'],case_changes=changed,details_unchanged=True,
            all_shapes_links_views_preserved=True,cold_reopen=True,validation=validation)
(OUT/'provenance-update.json').write_text(json.dumps(report,indent=2)+'\n')
App.closeDocument(doc.Name);print(json.dumps({k:v for k,v in report.items() if k!='validation'},indent=2))
sys.stdout.flush();os._exit(0)
