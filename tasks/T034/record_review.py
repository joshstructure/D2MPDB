"""T034: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
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
review.update(reviewer='Claude (Fable 5.1) — bounded file-integrity verification only (tasks/T034/build_components.py; package build verifications of '
                       'scripts/build_journal_calc_bpads.py and scripts/build_ring_wall_bpad.py)',
              native_recalculation=False, native_visual_review=False, engineering_review=False, design_outcome='unreviewed',
              external_analysis_disposition='Pier wall geometry reconciled to the CAD model (D-075): gravity row 42, C006, C004 and C017 follow the CAD wall; '
                                            'the FBMP pier export is unchanged and its pile-row wall load (from the 114.7 kip wall) is recorded as an open '
                                            'assumption; FBMP not rerun.',
              external_analysis_status='unreviewed',
              inherited_issues_disposition='Unchanged: the five open scope items of C017 and its grid-clearance failure, the C006 fin-plate failure and open '
                                           'confirmations, and the undecided choice between the fin-plate and welded-ring support concepts stay in the modules.',
              evidence_files=[{'path': 'verification.json', 'sha256': hashlib.sha256((BUILD / 'verification.json').read_bytes()).hexdigest()}])
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('review recorded')
