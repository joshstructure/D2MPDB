"""Record only the integrity review actually performed."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[2];TASK=Path(__file__).resolve().parent
BUILD=ROOT/'generated/T021-level-seats'
qa=ROOT/'project_current/geometry/freecad/evidence/2026-10-20-level-bearing-seats/adoption-summary.json'
assert json.loads(qa.read_text())['status']=='ADOPTED_AS_CAST_GEOMETRY_FINAL_FIT_OPEN'
for src in [TASK/'verification.json',qa]:shutil.copy2(src,BUILD/src.name)
p=BUILD/'review.json';r=json.loads(p.read_text())
r.update(reviewer='Codex — bounded file-integrity and native CAD geometry verification only',
 design_outcome='unreviewed',
 external_analysis_disposition='Documentary user geometry override only; no external analysis rerun or final bearing adequacy claim. Existing T019 conditional pier scope and source/load limitations remain.',
 external_analysis_status='unreviewed',
 inherited_issues_disposition='Existing bearing calculations/caches and other journal components preserved. D-064 explicitly superseded. CAD final pad/beam fit remains FAIL for the as-cast stock; final grinding/seat setting, cover, contact and engineering checks remain open.',
 evidence_files=[{'path':src.name,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()} for src in [BUILD/'verification.json',BUILD/qa.name]])
p.write_text(json.dumps(r,indent=2)+'\n')
