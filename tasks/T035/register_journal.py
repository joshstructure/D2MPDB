"""T035: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (idempotent)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T034', 'T035')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T035']['journal_sha256'], (actual, completed['T035']['journal_sha256'])
assert completed['T035']['previous_sha256'] == completed['T034']['journal_sha256']
previous = completed['T034']['journal_sha256']
NOTE = ('T035 (22 October 2026): C006 and C004 replaced by their regenerated journal editions naming the T034 journal (82e7d3e1) as the journal whose '
        'values their inputs equal (case name and provenance sentence in the hidden notes); every definition, cached value and canvas identical to the '
        'T034 modules; no engineering value changed; native recalculation, appearance and engineering reviews not performed. See tasks/T035/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-22', 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-075', task='T035', date='2026-10-22', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n',
                                    encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered'}))
