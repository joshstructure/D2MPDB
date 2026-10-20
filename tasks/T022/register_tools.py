"""T022: record the rebuilt notebook packages in the source register with a disposition (rerunnable, idempotent).

The three notebooks embed the generator scripts (scripts/bpad_sheet.py, scripts/build_cap_bpad.py, scripts/build_backwall_bpad.py,
pile_design/bpad.py), so the submission formatting changed their packages. No calculation code changed; the registered reports
and cases (D-051, D-054, D-057) remain the design records. The rows keep their depends_on, origin and hash basis.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import re

import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
TASK_ID = sys.argv[1] if len(sys.argv) > 1 else 'T022'          # a later task may re-register the notebooks the same way
TOOLS = {'CAP-TOOL': 'Cap_and_Pile_Design.ipynb', 'BACKWALL-TOOL': 'End_Bent_Backwall_Design.ipynb', 'PILE-TOOL': 'Pile_Design.ipynb'}


def lf_text_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def package_of(path):
    m = re.search(r'revision = \\?"([0-9a-f]{64})', path.read_text(encoding='utf-8'))      # JSON-escaped in the notebook source
    return m.group(1)[:12] if m else 'unknown'


reg = ROOT / 'project_current' / 'source_register.csv'
raw = reg.read_bytes()
lines = raw.decode('utf-8-sig').splitlines(keepends=True)
fields = next(csv.reader([lines[0]]))
done = {}
for i, line in enumerate(lines[1:], 1):
    row = dict(zip(fields, next(csv.reader([line]))))
    sid = row['source_id']
    if sid not in TOOLS:
        continue
    path = ROOT / row['path']
    assert path.name == TOOLS[sid] and row['hash_basis'] == 'lf_text', (sid, row['path'], row['hash_basis'])
    new = lf_text_sha(path)
    if row['sha256'] == new:
        done[sid] = 'already registered'
        continue
    note = (f'{TASK_ID} (20 October 2026): notebook rebuilt for the submission formatting of its Blockpad export (package {package_of(path)}): '
            f'the embedded generator scripts changed (numbered titles, hidden WorkingNotes, multiline table cells, no "distilled" wording); '
            f'no calculation code or input changed and the registered reports and cases remain the design records. Previous revision '
            f'{row["sha256"][:12]}. Historical basis: ')
    row.update(sha256=new, registered_on='2026-10-20')
    row['notes'] = note + row['notes']
    buf = io.StringIO(newline='')
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[f] for f in fields])
    lines[i] = buf.getvalue()
    done[sid] = new
assert set(done) == set(TOOLS), done
after = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + ''.join(lines).encode('utf-8')
before_rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
after_rows = list(csv.DictReader(io.StringIO(after.decode('utf-8-sig'))))
assert [r for r in before_rows if r['source_id'] not in TOOLS] == [r for r in after_rows if r['source_id'] not in TOOLS]
reg.write_bytes(after)
record = json.loads((TASK / 'adoption.json').read_text(encoding='utf-8')) if (TASK / 'adoption.json').is_file() else {}
record['tools'] = {sid: {'path': TOOLS[sid], 'sha256_lf_text': lf_text_sha(ROOT / TOOLS[sid]), 'package': package_of(ROOT / TOOLS[sid])} for sid in TOOLS}
(TASK / 'adoption.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(done, indent=2))
