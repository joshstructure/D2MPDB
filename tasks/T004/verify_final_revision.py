"""Tie the final prose correction to the previously observed native calculations."""
from pathlib import Path
import json,re,sys,shutil
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.bpad_workflow import Journal
a=ROOT/'generated/T004-response-review-01';b=ROOT/'generated/T004-response-review-02'
old=Journal.load(a/'candidate.bpad');new=Journal.load(b/'candidate.bpad')
assert old.changes(new)==['report:FBMPEndBent']
pattern=rb'<table name="EBUnresolvedApplications".*?</table>'
assert re.sub(pattern,b'',old.part('report:FBMPEndBent'),flags=re.S)==re.sub(pattern,b'',new.part('report:FBMPEndBent'),flags=re.S)
assert [(e.tag,e.get('formula')) for e in old.root.iter() if e.get('formula')]==[(e.tag,e.get('formula')) for e in new.root.iter() if e.get('formula')]
out=b/'evidence';out.mkdir(exist_ok=True)
shutil.copytree(a/'evidence',out/'revision-01-observations',dirs_exist_ok=True)
shutil.copy2(ROOT/'tasks/T004/response_checks.json',out/'response_checks.json')
(out/'revision-comparison.json').write_text(json.dumps({'final_sha256':new.sha256,'previous_sha256':old.sha256,'only_change':'EBUnresolvedApplications table: correct obsolete cap prose; wrap text cells','all_formulas_identical':True,'other_269_components_byte_identical':True,'earlier_screenshots':'revision-01-observations: original observations, not relabeled as final screenshots'},indent=2),encoding='utf8')
print(new.sha256)
