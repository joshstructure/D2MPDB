"""T042: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
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
review.update(reviewer='Claude (Opus 5.5) — bounded file-integrity verification only (tasks/T042/build_components.py: the six regenerated modules '
                       'keep the formula and cached-value multisets and the visible text of the base modules; scripts/build_journal_calc_bpads.py '
                       '--journal build verification against the packages)',
              native_recalculation=False, native_visual_review=False, engineering_review=False, design_outcome='unreviewed',
              external_analysis_disposition='No external analysis changed: only the position of input definitions in C001-C004, C015 and C016 moves '
                                            '(D-087); values, formulas, checks, cases and the FBMP exports are untouched.',
              external_analysis_status='not_applicable',
              inherited_issues_disposition='Unchanged: the C015 knife-edge side-wall failures and every other recorded status keep their state.',
              evidence_files=[{'path': 'verification.json', 'sha256': hashlib.sha256((BUILD / 'verification.json').read_bytes()).hexdigest()}])
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('review recorded')
