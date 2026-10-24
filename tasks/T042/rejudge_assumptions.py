"""T042: re-judge the assumptions whose JOURNAL basis is the T041 revision against the T042 journal (line surgery; the
register is hand-formatted JSON, so it is never round-tripped). Idempotent."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = 'd8b814ad940258e321bb29b0af69424771a524bb359d4efd0952da33bea567b0'
NEW = hashlib.sha256((ROOT / 'journal' / 'D2_I95_Project_Journal.bpad').read_bytes()).hexdigest()
assert NEW == json.loads((ROOT / 'workflow' / 'completed' / 'T042.json').read_text(encoding='utf-8'))['journal_sha256']
SENTENCE = (' Re-judged 23 October 2026 against the T042 journal (C001-C004, C015 and C016 list each input under its own section, D-087; '
            'only the position of input definitions changed, every formula and value is that of the T041 revision).')
path = ROOT / 'project_current' / 'coherence' / 'assumptions.json'
raw = path.read_bytes().decode('utf-8')
nl = '\r\n' if '\r\n' in raw else '\n'
lines = raw.split(nl)
done = []
entry_start = None
for i, line in enumerate(lines):
    if line.strip().startswith('"id": "A-'):
        entry_start = i
    if f'"JOURNAL": "{OLD}"' in line:
        statement = next(j for j in range(entry_start, i) if lines[j].strip().startswith('"statement": '))
        assert lines[statement].endswith('",'), lines[statement][-40:]
        if SENTENCE not in lines[statement]:
            lines[statement] = lines[statement][:-2] + SENTENCE + '",'
        lines[i] = line.replace(OLD, NEW)
        done.append(lines[entry_start].strip())
text = nl.join(lines)
json.loads(text)
path.write_bytes(text.encode('utf-8'))
print('re-judged:', done)
