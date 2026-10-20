"""T025: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
BUILD = Path(sys.argv[1])
verification = json.loads((TASK / 'verification.json').read_text(encoding='utf-8'))
assert verification['status'] == 'PASS'
evidence = []
for src in (TASK / 'verification.json', TASK / 'definitions.json'):
    shutil.copy2(src, BUILD / src.name)
    evidence.append({'path': src.name, 'sha256': hashlib.sha256((BUILD / src.name).read_bytes()).hexdigest()})
path = BUILD / 'review.json'
review = json.loads(path.read_text(encoding='utf-8'))
review.update(reviewer='Claude (Fable 5.1) — bounded file-integrity verification only (tasks/T025/build_components.py)',
              native_recalculation=False, native_visual_review=False, engineering_review=False, design_outcome='unreviewed',
              external_analysis_disposition='Presentation only (stamp cells); no value changed; FBMP not rerun.',
              external_analysis_status='unreviewed',
              inherited_issues_disposition='Each report minus its eight stamp cells is byte-identical; other components untouched. Nothing opened natively.',
              evidence_files=evidence)
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('review recorded')
