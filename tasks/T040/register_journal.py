"""T040: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (idempotent)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T039', 'T040')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T040']['journal_sha256'], (actual, completed['T040']['journal_sha256'])
assert completed['T040']['previous_sha256'] == completed['T039']['journal_sha256']
previous = completed['T039']['journal_sha256']
NOTE = ('T040 / D-082 (22 October 2026): C006 Pier Wall, Hairpins and Fin Plates (PierWallFins) deleted from the journal and kept in the repository '
        'under sequestered/ for revival; calculation numbers are permanent (C005 and C006 retired, nothing renumbered); C017 regenerated from its '
        'unchanged case with identical definitions and caches (working notes and one scope sentence record the withdrawal); PedBridge index entry '
        'removed and revision note; DecisionLog entry. Native recalculation, appearance and engineering reviews not performed. '
        'See tasks/T040/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
status = row['status'] + '; C006 withdrawn, numbers permanent (D-082)'
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-22', 'status': status, 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-082', task='T040', date='2026-10-22', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n',
                                    encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered', 'row_status': written['JOURNAL']['status']}))
