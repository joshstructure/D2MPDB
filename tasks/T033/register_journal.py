"""T033: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (idempotent)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T032', 'T033')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T033']['journal_sha256'], (actual, completed['T033']['journal_sha256'])
assert completed['T033']['previous_sha256'] == completed['T032']['journal_sha256']
previous = completed['T032']['journal_sha256']
NOTE = ('T033 (21 October 2026): C008 and C009 replaced by their regenerated journal editions naming the registered 10-20 End Bent cap reports (D-068); every '
        'definition, cached value and canvas identical; PedBridge revision note and DecisionLog entry; no engineering value changed; native recalculation, appearance '
        'and engineering reviews not performed. See tasks/T033/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-21', 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(task='T033', date='2026-10-21', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n', encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered'}))
