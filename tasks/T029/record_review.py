"""T029: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
BUILD = Path(sys.argv[1])
assert json.loads((TASK / 'verification.json').read_text(encoding='utf-8'))['status'] == 'PASS'
shutil.copy2(TASK / 'verification.json', BUILD / 'verification.json')
path = BUILD / 'review.json'
review = json.loads(path.read_text(encoding='utf-8'))
review.update(reviewer='Claude (Fable 5.1) — bounded file-integrity verification only (tasks/T029/verify_order.py)',
              native_recalculation=False, native_visual_review=False, engineering_review=False, design_outcome='unreviewed',
              external_analysis_disposition='Registered module order only: report:PierWallRings (C017, added by T028) moved after report:BearingDesign (C016); '
                                            'every component byte unchanged; FBMP not rerun.',
              external_analysis_status='unreviewed',
              inherited_issues_disposition='No component content changed; the open items of every module remain as recorded.',
              evidence_files=[{'path': 'verification.json', 'sha256': hashlib.sha256((BUILD / 'verification.json').read_bytes()).hexdigest()}])
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('review recorded')
