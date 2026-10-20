"""T022: independent verification of the assembled candidate against the current journal (rerunnable).

    verify_task.py [generated/T022-submission-01]      -> tasks/T022/verification.json

Checks: every component outside the write scope is byte-identical to the current journal; every changed module keeps every
dynexp formula string (the only additions are the eight Stamp_* definitions of the live project stamp in the seven stamped
reports) and every value-cell formula except the eight stamp cells those definitions replace; the ten numbered titles; no
static text value cell remains in the fifteen calculation modules; the visible-text rule of scripts/bpad_sheet.py holds for
them (the RFQ term "Task Work Order" accepted); the index links name the numbers; the DecisionLog entry exists.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TASK))
from tools.bpad_workflow import Journal  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402
import build_components as bc  # noqa: E402  (runs the component build again: rerunnable, and keeps the two in step)
import submission_format as sf  # noqa: E402

folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'generated' / 'T022-submission-01'
candidate = Journal.load(folder / 'candidate.bpad')
current = Journal.load(ROOT / 'journal' / 'D2_I95_Project_Journal.bpad')
order = json.loads((TASK / 'order.json').read_text(encoding='utf-8'))
writes = set(order['writes'])
assert order['base_journal_sha256'] == current.sha256 == bc.base.sha256, 'the current journal is not the task base'
report = {'task': 'T022', 'base_sha256': current.sha256, 'candidate_sha256': candidate.sha256, 'candidate': str(folder / 'candidate.bpad'),
          'protected_components': 0, 'changed': {}, 'problems': []}
problems = report['problems']

for key in current.order:
    if key not in writes:
        if current.hashes[key] != candidate.hashes[key]:
            problems.append(f'{key}: changed outside the write scope')
        else:
            report['protected_components'] += 1
assert candidate.order == current.order, 'component order changed'

stamped = set(bc.CAPS) | {bc.BACKWALL}
for key in sorted(writes):
    name = key.split(':', 1)[1]
    old, new = current.elements[key], candidate.elements[key]
    entry = {'title': new.get('title')}
    old_d, new_d = bc.dynexp_formulas(old), bc.dynexp_formulas(new)
    lost, added = old_d - new_d, new_d - old_d
    if lost:
        problems.append(f'{name}: definitions lost: {list(lost.elements())[:5]}')
    if added != (bc.STAMP_DEFS if name in stamped else Counter()):
        problems.append(f'{name}: unexpected new definitions: {list(added.elements())[:8]}')
    old_c, new_c = bc.cell_formulas(old), bc.cell_formulas(new)
    if (old_c - new_c) != (bc.STAMP_CELLS if name in stamped else Counter()) or (new_c - old_c):
        problems.append(f'{name}: value-cell formulas changed')
    if name in bc.TITLES and new.get('title') != bc.TITLES[name]:
        problems.append(f'{name}: title {new.get("title")!r}')
    if name in bc.CALCS:
        remaining = bc.static_value_cells(new)
        if remaining:
            problems.append(f'{name}: {len(remaining)} static value cells remain')
        found = bc.leftovers(new, name)
        if found:
            problems.append(f'{name}: visible working language: {found[:3]}')
        entry['static_cells_converted'] = len(bc.static_value_cells(old)) - len(remaining)
        entry['hidden_sections'] = sum(1 for s in new.iter('section') if (s.get('hide') or '').lower() == 'true')
        entry['hidden_sections_before'] = sum(1 for s in old.iter('section') if (s.get('hide') or '').lower() == 'true')
    entry['definitions'] = sum(new_d.values())
    entry['sha256_before'] = current.hashes[key]
    entry['sha256_after'] = candidate.hashes[key]
    report['changed'][name] = entry

ped = candidate.elements['report:PedBridge']
labels = {l.text for l in ped.iter('link')}
for target, _, new_label in sf.INDEX_LABELS:
    if new_label not in labels:
        problems.append(f'PedBridge: index label missing: {new_label}')
if not any(sf.REVISION_NOTE in ''.join(p.itertext()) for p in ped.iter('paragraph')):
    problems.append('PedBridge: revision note missing')
log = candidate.elements['report:DecisionLog']
if not any(s.get('name') == sf.DECISION_SECTION for s in log.iter('section')):
    problems.append('DecisionLog: entry missing')
report['titles'] = {n: candidate.elements[f'report:{n}'].get('title') for n in bc.CALCS}
report['status'] = 'PASS' if not problems else 'FAIL'
report['reviews'] = {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}
report['protected_files_sha256'] = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in
                                    ('cap_bpad/journal/verification.json', 'end_bent_walls/bpad/journal/verification.json', 'pile_bpad/verification.json')}
(TASK / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'changed'}, indent=2, ensure_ascii=False))
sys.exit(0 if not problems else 1)
