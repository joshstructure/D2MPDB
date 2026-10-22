"""Engine snapshot of the selected D-084 case for the CAD transfer (as the D-079 job's case-snapshot.json)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(r'C:\github\D2MPDB')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from ring_wall.design import analyze  # noqa: E402

case_path = ROOT / 'project_current/pier_wall/selected_case.json'
case = json.loads(case_path.read_text(encoding='utf-8-sig'))
r = analyze(case)
assert r['case'] == case and case['u_leg_in'] == 27.0
snap = {'case': case, 'grid': r['grid'], 'failed_checks': [c for c in r['checks'] if c['status'] == 'FAIL'],
        'sha256': hashlib.sha256(case_path.read_bytes()).hexdigest()}
(OUT / 'case-snapshot.json').write_text(json.dumps(snap, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'sha256': snap['sha256'], 'u_leg_in': case['u_leg_in'], 'failed': [c['id'] for c in snap['failed_checks']],
                  'lap_b_h': r['grid']['development_h']['lap_b']}, indent=1))
