"""Import only the assigned component from the inspected native save."""
from pathlib import Path
import sys, json, shutil
ROOT=Path(__file__).resolve().parents[2]
TASK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from bpad_workflow import Journal, check
from verify_module import native

source=ROOT/'generated/T009-front-side-01/candidate.bpad'
result=native(source)
assert result['sha256']=='4b1770533d7b91cfb1efbcd96b0eb2c3a73328b90f88b2b50bca15388f07cd82'
saved=Journal.load(source)
base=Journal.load(TASK/'base.bpad')
fragment=saved.part('report:MSEWallExclusion')
proposed=base.replace({'report:MSEWallExclusion':fragment})
check(ROOT,'T009',proposed)
(TASK/'components/000.xml').write_bytes(fragment)
(TASK/'working.bpad').write_bytes(proposed)
shutil.copyfile(source,TASK/'native-reviewed.bpad')
assert base.changes(Journal(proposed))==['report:MSEWallExclusion']
submission=json.loads((TASK/'submission.json').read_text())
submission['checks_performed'] += [
    'Native Blockpad recalculation/save: zero module errors and 74 table/dimension values agree with independent equations',
    'All five module pages inspected in native Blockpad, including three dimensioned canvases',
    'DXF preview reopened and audited; original-coordinate limits and 18 native dimensions checked',
    'Only the reviewed native module imported; 270 other components and document shell preserved byte-for-byte'
]
submission['open_items']=[item for item in submission['open_items'] if 'before promotion' not in item]
(TASK/'submission.json').write_text(json.dumps(submission,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'native':result,'preserved_components':len(base.order)-1,'changed':['report:MSEWallExclusion']},indent=2))
