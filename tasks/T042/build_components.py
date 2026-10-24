"""T042: write the eight registered component files (rerunnable, byte-surgical).

* C001-C004, C015, C016: the rebuilt journal editions `<package>/bpad/journal/<Report>.xml` (inputs placed in their own
  sections, D-087), each checked against its verification record and the base module: same name and title, the same
  multiset of formulas and of (formula, cached value) pairs, only the order of definitions changes.
* PedBridge: one revision paragraph before the newest revision note. DecisionLog: one section appended.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402

TNR = 'Times New Roman'
DECISION_ID = 'D-087'
PACKAGES = {'C001WindLoadOnPedBridgeSuperstructure': 'wind_superstructure', 'FenceWind': 'fence_wind', 'BridgeMovement': 'bridge_movement',
            'SuperstructureUplift': 'superstructure_uplift', 'MSEWallExclusion': 'mse_wall_exclusion', 'BearingDesign': 'bearing_design'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))
order = lambda el: [d.get('formula') for d in el.iter('dynexp')]

base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {f'report:{n}' for n in PACKAGES} | {'report:PedBridge', 'report:DecisionLog'}, sorted(mapping)
out, record = {}, {}

# --- the six calculation editions ---
for name, package in PACKAGES.items():
    folder = ROOT / package / 'bpad' / 'journal'
    v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))
    v = v[0] if isinstance(v, list) else v
    data = strip_nl((folder / f'{name}.xml').read_bytes())
    assert sha(data) == v['fragment_sha256'], f'{name}: fragment differs from its verification record'
    root = E.fromstring(data)
    old = E.fromstring(base.part(f'report:{name}'))
    assert root.get('name') == name == old.get('name') and root.get('title') == old.get('title'), name
    assert data != base.part(f'report:{name}'), f'{name}: unchanged'
    assert dyn(root) == dyn(old), f'{name}: a formula changed'
    assert caches(root) == caches(old), f'{name}: a cached value changed'
    # no visible text is new (wording the base already carries, e.g. the RFQ 'Task' citation in C002, is not this task's)
    text_of = lambda el: Counter(t for _, t in bs.visible_text_elements(el))
    added = text_of(root) - text_of(old)
    assert not added, f'{name}: visible text changed: {list(added)[:3]}'
    a, b = order(old), order(root)
    moved = sum(1 for x, y in zip(a, b) if x != y)
    out[f'report:{name}'] = data
    record[name] = {'source': f'{package}/bpad/journal/{name}.xml', 'fragment_sha256': v['fragment_sha256'], 'case_sha256': v['case_sha256'],
                    'title': root.get('title'), 'definitions': sum(dyn(root).values()), 'formulas_and_caches_unchanged': True,
                    'definition_positions_changed': moved}

# --- PedBridge: the revision note ---
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
REVISION_NOTE = ('Revision: 23 October 2026, inputs placed in their own sections (T042): C001 Wind Load on Ped Bridge Superstructure, C002 Fence Wind, '
                 'C003 Bridge Temperature Movement, C004 Superstructure Uplift, C015 MSE Wall Exclusion and C016 Bearings and Support Details now list '
                 'each input under the section it belongs to (for example C001 1.2 Wind speed and exposure, which was empty, and the C004 pier weights '
                 'under Permanent-load sources at the pier) instead of beside its first use or at the end. Only the position of input definitions '
                 'changed: every formula and value is that of the previous revision. Native recalculation, appearance and engineering reviews not '
                 'performed.')
m = re.search(r'^( {8}<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: )', text, re.M)
assert m, 'PedBridge revision paragraph anchor'
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
assert REVISION_NOTE[:60] not in text
text = text[:m.start()] + note + nl + text[m.start():]
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + revision note'}

# --- DecisionLog ---
text = base.part('report:DecisionLog').decode('utf-8')
nl = nl_of(text)
DECISION_SECTION = 'InputPlacement20261023'
DECISION_HEADING = '2026-10-23 - Inputs placed in their own sections in C001 to C004, C015 and C016 (T042)'
DECISION = ('User direction of 23 October 2026 (project decision D-087): the user asked why section 1.2 of C001 had nothing under it. The calculation '
            'generator placed an input under a section only when its group equalled the section title exactly; the groups are written as the bare '
            'heading (Wind speed and exposure) and the titles carry their number (1.2 Wind speed and exposure), so every input sat beside its first '
            'use and section 1.2 stayed empty, and inputs no equation reads (values behind tables, names other calculations read) were listed only '
            'at the end. Groups now match titles without the number and each such input has a named home section: C001 sections 1.1 to 1.3, C002 '
            'Step 2, C003 2.2, the C004 deck, span, eccentricity, permanent-load and datum sections, C015 section 2 and C016 sections 3, 4 and 6. '
            'The six modules are regenerated; only the position of input definitions changed, every formula and cached value is that of the '
            'previous revision. Native recalculation, appearance and engineering reviews not performed; selection is not engineering acceptance.')
tail = ' ' * 8 + '</section>' + nl + ' ' * 4 + '</report>'
assert text.endswith(tail), 'DecisionLog does not end with a section inside the report'
assert f'name="{DECISION_SECTION}"' not in text
entry = nl.join([' ' * 8 + f'<section name="{DECISION_SECTION}" capture="False" hide="false">',
                 ' ' * 12 + f'<heading level="1" keepwithnext="True">{DECISION_HEADING}</heading>',
                 ' ' * 12 + f'<paragraph fontfamily="{TNR}" fontsize="11" leftindent="0" spacingafter="7">{DECISION}</paragraph>',
                 ' ' * 8 + '</section>'])
text = text[:-len(' ' * 4 + '</report>') - len(nl)] + nl + entry + nl + ' ' * 4 + '</report>'
E.fromstring(text.encode('utf-8'))
out['report:DecisionLog'] = text.encode('utf-8')
record['DecisionLog'] = {'source': 'base.bpad + decision entry'}

for key in ('report:PedBridge', 'report:DecisionLog'):
    new, old = E.fromstring(out[key]), base.elements[key]
    assert dyn(old) == dyn(new) and caches(old) == caches(new), f'{key}: a definition or cache changed'

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T042', 'base_sha256': base.sha256, 'decision': DECISION_ID, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T042', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())},
                  'moved': {n: r['definition_positions_changed'] for n, r in record.items() if n in PACKAGES}}, indent=1))
