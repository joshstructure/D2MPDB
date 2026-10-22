"""T038: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
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
review.update(reviewer='Claude (Fable 5.1) — bounded file-integrity verification only (tasks/T038/build_components.py; scripts/build_pier_cheek_wall.py '
                       '--journal build verification: 174 values compared with the notebook to 1e-9, five C001 references through the coherence gate)',
              native_recalculation=False, native_visual_review=False, engineering_review=False, design_outcome='unreviewed',
              external_analysis_disposition='No external analysis involved: C018 reads the pier cheek wall starting case (CAD walls and mats, D-080/D-081), '
                                            'five C001 wind values and ProjectInfo; the FBMP exports, the pile and cap cases and their modules are untouched.',
              external_analysis_status='not_applicable',
              inherited_issues_disposition='New module; no existing module value changed. Its own open items (development and cover exactly at their limits, '
                                           'one-centred-mat shrinkage and temperature convention pending confirmation) are recorded in its hidden notes and '
                                           'the project record; C014 (end-bent backwall and cheek walls) keeps its recorded status.',
              evidence_files=[{'path': 'verification.json', 'sha256': hashlib.sha256((BUILD / 'verification.json').read_bytes()).hexdigest()}])
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('review recorded')
