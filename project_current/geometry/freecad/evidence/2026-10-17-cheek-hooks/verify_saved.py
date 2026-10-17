from pathlib import Path
import sys,json,zipfile,copy,hashlib,xml.etree.ElementTree as ET,traceback
sys.dont_write_bytecode=True
OUT=Path(__file__).parent;BASE=Path('C:/github/D2MPDB/project_current/geometry/freecad')
installed='--installed' in sys.argv
sys.path.insert(0,str((BASE if installed else OUT)/'runtime'))
import FreeCAD as App
from freecad_tools import cheek_hooks as hooks,cheek_steel as cheek,bridge,native_archive
build=json.loads((OUT/'build-report.json').read_text());assert build['status']=='PASS'
path=BASE/'B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd' if installed else Path(build['model'])
result=dict(status='STARTED',model=str(path),sha256=native_archive.sha(path))
def records(path,member,section):
 with zipfile.ZipFile(path) as z:
  out={}
  for obj in ET.fromstring(z.read(member)).find(section):
   obj=copy.deepcopy(obj)
   for el in obj.iter():
    if el.get('file'):el.set('file',hashlib.sha256(z.read(el.get('file'))).hexdigest())
   out[obj.get('name')]=ET.tostring(obj)
  return out
try:
 assert result['sha256']==build['sha256']
 old=records(OUT/'Before.FCStd','Document.xml','ObjectData');new=records(path,'Document.xml','ObjectData')
 assert len(old)==len(new)==2093
 assert all(old[n]==new[n] for n in build['protected'])
 oldv=records(OUT/'Before.FCStd','GuiDocument.xml','ViewProviderData');newv=records(path,'GuiDocument.xml','ViewProviderData')
 assert oldv==newv
 d=App.openDocument(str(path))
 for h in cheek.HOSTS:
  inp=d.getObject('Steel'+h+'Inputs');assert isinstance(inp.Proxy,hooks.InputsProxy)
 assert not [o.Name for o in d.Objects if 'Invalid' in o.State or 'Touched' in o.State]
 # The installed file must be byte-identical to the cold-verified candidate.
 # Repeat native loading/link checks, not the same expensive geometry audit.
 if installed:
  cold=json.loads((OUT/'cold-reopen.json').read_text());assert cold['status']=='PASS' and cold['sha256']==result['sha256']
  for w in cold['geometry']['measurements']:
   q=d.getObject('Steel'+w['wall']+'Quantities')
   assert q.TotalBars==w['bars'] and abs(q.TotalSteelLength.Value/304.8-w['length_ft'])<1e-8
  result['geometry_basis']='Exact SHA-256 match to cold-verified file; native installed controllers/links/quantities loaded successfully.'
 else:
  result['geometry']=hooks.validate(d);assert not result['geometry']['failures']
  result['native_geometry_cover_clearance_and_schedule']='PASS'
 result.update(status='PASS',objects=len(d.Objects),retained_native_records=len(build['protected']),retained_view_records=len(oldv),native_reopen='PASS')
 App.closeDocument(d.Name)
except Exception:
 result.update(status='FAIL',error=traceback.format_exc());raise
finally:
 (OUT/('installed-reopen.json' if installed else 'cold-reopen.json')).write_text(json.dumps(result,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k!='geometry'}),flush=True)
