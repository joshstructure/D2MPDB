"""T037: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
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
review.update(reviewer='Claude (Fable 5.1) — bounded file-integrity verification only (tasks/T037/build_components.py; scripts/build_ring_wall_bpad.py '
                       'build verification: 673 values and 178 statuses evaluated independently to 1e-9)',
              native_recalculation=False, native_visual_review=False, engineering_review=False, design_outcome='unreviewed',
              external_analysis_disposition='No external analysis changed: C017 reads the ring wall starting case only (ring plate 1/2 in, D-078); the FBMP '
                                            'exports, the pile and cap cases and their modules are untouched.',
              external_analysis_status='not_applicable',
              inherited_issues_disposition='Unchanged: the C017 grid-clearance failure (RING-GRID) and its five scope items, the undecided support concept '
                                           '(C006 fin plates or welded rings) and the 3/4-in CAD rings of D-076 (reconciliation pending) keep their recorded status.',
              evidence_files=[{'path': 'verification.json', 'sha256': hashlib.sha256((BUILD / 'verification.json').read_bytes()).hexdigest()}])
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('review recorded')
