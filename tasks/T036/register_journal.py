"""T036: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (idempotent)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T035', 'T036')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T036']['journal_sha256'], (actual, completed['T036']['journal_sha256'])
assert completed['T036']['previous_sha256'] == completed['T035']['journal_sha256']
previous = completed['T035']['journal_sha256']
NOTE = ('T036 / D-077 (22 October 2026): pier modules follow the 22 October FBMP rerun (pier wall extra members ending at the soil surface; loads, '
        'geometry, section, material and soil unchanged): C010 Pier Cap Design and C013 Pier Pile Design replaced by their regenerated journal editions '
        '(cap: nine force inputs moved, no status change; pile: demands of the new export); FBMP Entry - Pier, Foundations and FBMP Modeling, Bridge '
        'Geometry and the index name the D-077 export; DecisionLog entry. End-bent modules unchanged; FBMP rerun by the user, not here; native '
        'recalculation, appearance and engineering reviews not performed. See tasks/T036/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
status = row['status'].replace('pier modules on the D-073 export', 'pier modules on the D-077 export')
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-22', 'status': status, 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-077', task='T036', date='2026-10-22', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n',
                                    encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered', 'row_status': written['JOURNAL']['status']}))
