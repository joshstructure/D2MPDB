"""T032: after promotion, move the JOURNAL row of project_current/source_register.csv to the promoted revision (idempotent)."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

completed = {t: json.loads((ROOT / 'workflow' / 'completed' / f'{t}.json').read_text(encoding='utf-8')) for t in ('T031', 'T032')}
actual = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert actual == completed['T032']['journal_sha256'], (actual, completed['T032']['journal_sha256'])
assert completed['T032']['previous_sha256'] == completed['T031']['journal_sha256']
previous = completed['T031']['journal_sha256']
NOTE = ('T032 / D-073 (21 October 2026): pier modules follow the 21 October FBMP rerun (pipe pile material Fy 45 ksi in place of 60 ksi; loads and geometry '
        'unchanged): C010 Pier Cap Design and C013 Pier Pile Design replaced by their regenerated journal editions with every definition, cached value and '
        'canvas identical to the prior modules (text only: new export identity, 11 pending pile items in place of 16 with the steel-grade prerequisite '
        'source-backed); Pile Section Properties, FBMP Entry - Pier, Foundations and FBMP Modeling, Bridge Geometry and the index name the D-073 export; '
        'DecisionLog entry. End-bent modules unchanged; no engineering value changed; FBMP rerun by the user, not here; native recalculation, appearance '
        'and engineering reviews not performed. See tasks/T032/verification.json.')
row = read_rows()['JOURNAL']
if row['sha256'] == actual:
    print('JOURNAL row already registered')
    raise SystemExit(0)
assert row['sha256'] == previous, row['sha256']
status = row['status'].replace('calculations C001-C017 in order with project stamps', 'calculations C001-C017 in order with project stamps; pier modules on the D-073 export')
written = update_rows({'JOURNAL': {'sha256': actual, 'registered_on': '2026-10-21', 'status': status, 'notes': NOTE}}, prepend_notes=True)
(TASK / 'adoption.json').write_text(json.dumps(dict(decision='D-073', task='T032', date='2026-10-21', journal_sha256=actual, previous_sha256=previous), indent=2) + '\n',
                                    encoding='utf-8')
print(json.dumps({'journal_sha256': actual, 'status': 'registered', 'row_status': written['JOURNAL']['status']}))
