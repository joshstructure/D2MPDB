"""T036: record only the integrity review actually performed in the candidate's review.json (rerunnable)."""
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
review.update(reviewer='Claude (Fable 5.1) — bounded file-integrity verification only (tasks/T036/build_components.py; scripts/build_cap_bpad.py and '
                       'scripts/build_pile_bpad.py build verifications)',
              native_recalculation=False, native_visual_review=False, engineering_review=False, design_outcome='unreviewed',
              external_analysis_disposition='The 22 October 2026 pier FBMP rerun (D-077, PIER-XML) is the registered analysis source; its only model change '
                                            'is the extent of the pier wall extra members (ending at the soil surface); the pier cap and pile cases were '
                                            'rerun from it and C010 / C013 are their regenerated editions. FBMP rerun by the user, not here.',
              external_analysis_status='unreviewed',
              inherited_issues_disposition='Unchanged: the cap detailing failures, the pile pending prerequisites (11 at the pier), COH-004 and COH-028 '
                                           'keep their recorded status; end-bent modules untouched.',
              evidence_files=[{'path': 'verification.json', 'sha256': hashlib.sha256((BUILD / 'verification.json').read_bytes()).hexdigest()}])
path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('review recorded')
