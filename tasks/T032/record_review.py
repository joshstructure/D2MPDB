"""T032: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
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
review.update(reviewer='Claude (Fable 5.1) — bounded file-integrity verification only (tasks/T032/build_components.py; scripts/build_cap_bpad.py --journal and '
                       'scripts/build_pile_bpad.py build verification)',
              native_recalculation=False, native_visual_review=False, engineering_review=False, design_outcome='unreviewed',
              external_analysis_disposition='Pier FBMP export rerun by the user with the 45 ksi pipe pile material (D-073); C010 and C013 replaced by regenerated editions '
                                            'with every definition, cached value and canvas identical to the base modules (text only); the pier source paragraphs name the '
                                            'new export; no engineering value changed; FBMP not rerun here.',
              external_analysis_status='unreviewed',
              inherited_issues_disposition='End-bent modules untouched. The pier cap check failures and pending checks and the pier pile pending items (now 11) remain as '
                                           'recorded in their editions; COH-004, COH-013 and COH-028 keep their status.',
              evidence_files=[{'path': 'verification.json', 'sha256': hashlib.sha256((BUILD / 'verification.json').read_bytes()).hexdigest()}])
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('review recorded')
