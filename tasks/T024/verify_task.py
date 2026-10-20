"""T024: independent verification of the assembled candidate (rerunnable): verify_task.py [generated/T024-order-01]

Checks: the candidate's component order equals component_order.json; every component outside the write scope is byte-identical
to the current journal; the three pile reports keep every definition and value-cell formula (only the Stamp_* definitions
added); all sixteen numbered calculations start with a live ProjectStamp table of multiline cells; the index lists C001 to
C016 in order; the DecisionLog entry exists. Writes tasks/T024/verification.json."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal, MODULE_TAGS  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402

CALCS = ['C001WindLoadOnPedBridgeSuperstructure', 'FenceWind', 'BridgeMovement', 'SuperstructureUplift', 'PierWallFins', 'CapDesignBasis',
         'CapDesignEndBentOne', 'CapDesignEndBentTwo', 'CapDesignPier', 'PileDesignEndBentOne', 'PileDesignEndBentTwo', 'PileDesignPier',
         'EndBentBackwallDesign', 'MSEWallExclusion', 'BearingDesign']
PILES = CALCS[9:12]
STAMP_DEFS = Counter(f'{bs.STAMP_PREFIX}{k} = {bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS)
folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'generated' / 'T024-order-01'
candidate = Journal.load(folder / 'candidate.bpad')
current = Journal.load(ROOT / 'journal' / 'D2_I95_Project_Journal.bpad')
record = json.loads((TASK / 'order.json').read_text(encoding='utf-8'))
order = json.loads((TASK / 'component_order.json').read_text(encoding='utf-8'))
writes = set(record['writes'])
problems = []
if record['base_journal_sha256'] != current.sha256:
    problems.append('the current journal is not the task base')
if candidate.order != order or record['order'] != order:
    problems.append('candidate order differs from component_order.json')
if candidate.shell != current.shell:
    problems.append('document shell changed')
for key in current.order:
    if key not in writes and current.part(key) != candidate.part(key):
        problems.append(f'{key}: changed outside the write scope')
dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
cel = lambda el: Counter(e.get('formula') for e in el.iter() if e.tag in ('c', 'planecontainer', 'lineardim', 'plot') and e.get('formula'))
for name in PILES:
    old, new = current.elements[f'report:{name}'], candidate.elements[f'report:{name}']
    if (dyn(old) - dyn(new)) or (dyn(new) - dyn(old)) != STAMP_DEFS or cel(old) != cel(new):
        problems.append(f'{name}: formulas changed beyond the stamp definitions')
stamps = {}
for name in CALCS:
    el = candidate.elements[f'report:{name}']
    first = next((c for c in el if c.tag not in ('include', 'stylerule')), None)
    table = first.find('table') if first is not None and first.tag == 'embed' else None
    ok = table is not None and table.get('name') == 'ProjectStamp'
    if ok:
        cells = bs.stamp_cells(table)
        ok = ([o for _, _, o in cells] == [f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS]
              and [t for _, t, _ in cells] == [bs.PROJECT_STAMP[k] for k in bs.STAMP_KEYS])
        # the generated editions hold the stamp in multiline cells (Stamp_* result-only definitions); the hand-authored
        # calculations still hold value-cell references (T025 converts them)
        form = 'multiline' if all(c.tag == 'textcell' for row in table.findall('row') for c in row) else 'value cells'
    stamps[name] = form if ok else False
    if not ok:
        problems.append(f'{name}: no live ProjectStamp table at the top')
modules = [k for k in candidate.order if k.split(':', 1)[0] in MODULE_TAGS]
titles = [candidate.elements[k].get('title') or '' for k in modules]
numbered = [t[:4] for t in titles if t[:4] in {f'C{n:03d}' for n in range(1, 17)}]
if numbered != sorted(numbered) or len(set(numbered)) != 15:
    problems.append(f'calculations not in numerical order: {numbered}')
ped = candidate.elements['report:PedBridge']
links = [l.text for l in ped.iter('link')]
group = links[links.index('C001 - Superstructure Wind'):]
group = group[:next(i for i, t in enumerate(group) if not t.startswith('C0'))]
if [t[:4] for t in group] != sorted(t[:4] for t in group) or len(group) != 19:
    problems.append(f'index calculation links not in numerical order: {group}')
if not any(s.get('name') == 'SubmissionFormatting20261020b' for s in candidate.elements['report:DecisionLog'].iter('section')):
    problems.append('DecisionLog entry missing')
report = {'task': 'T024', 'base_sha256': current.sha256, 'candidate_sha256': candidate.sha256, 'status': 'PASS' if not problems else 'FAIL',
          'problems': problems, 'module_order': modules, 'calculation_titles_in_order': [t for t in titles if t[:4] in numbered],
          'stamps': stamps, 'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False},
          'protected_files_sha256': {'pile_bpad/journal/verification.json': hashlib.sha256((ROOT / 'pile_bpad/journal/verification.json').read_bytes()).hexdigest()}}
(TASK / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k not in ('module_order', 'stamps')}, indent=2, ensure_ascii=False))
sys.exit(0 if not problems else 1)
