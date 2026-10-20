"""T022: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
BUILD = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'generated' / 'T022-submission-01'
verification = json.loads((TASK / 'verification.json').read_text(encoding='utf-8'))
assert verification['status'] == 'PASS' and not verification['problems']
assert verification['candidate_sha256'] == hashlib.sha256((BUILD / 'candidate.bpad').read_bytes()).hexdigest()
evidence = []
for src in (TASK / 'verification.json', TASK / 'independent-checks.json', TASK / 'definitions.json'):
    shutil.copy2(src, BUILD / src.name)
    evidence.append({'path': src.name, 'sha256': hashlib.sha256((BUILD / src.name).read_bytes()).hexdigest()})
path = BUILD / 'review.json'
review = json.loads(path.read_text(encoding='utf-8'))
review.update(
    reviewer='Claude (Fable 5.1) — bounded file-integrity verification only (tasks/T022/verify_task.py)',
    native_recalculation=False, native_visual_review=False, engineering_review=False,
    design_outcome='unreviewed',
    external_analysis_disposition='Presentation only: no input, formula or cache value changed; FBMP not rerun. Existing analysis limitations and open items of every calculation remain as recorded in their hidden working notes.',
    external_analysis_status='unreviewed',
    inherited_issues_disposition='Every existing definition, value-cell formula, canvas and resource preserved (multiset checks); the T018 native caches of the generated reports are superseded by generator caches of the same values (result-only cells without the "= " prefix). The multiline cells and the Stamp_* result-only definitions have not been opened natively.',
    evidence_files=evidence)
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'review': str(path), 'evidence': evidence}, indent=2))
