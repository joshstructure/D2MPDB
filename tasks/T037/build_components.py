"""T037: write the three registered component files (rerunnable, byte-surgical).

* PierWallRings (C017): the rebuilt journal edition `ring_wall/bpad/journal/PierWallRings.xml` (1/2-in ring plate starting
  case, D-078), checked against its verification record, the registered case (ring_t_in 0.5, same wall and diameters as
  T034) and the base module (same name, title and definition names; values differ).
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
DECISION_ID = 'D-078'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))

base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {'report:PierWallRings', 'report:PedBridge', 'report:DecisionLog'}, sorted(mapping)
out, record = {}, {}

# --- C017 ---
NAME, TITLE = 'PierWallRings', 'C017 - Pier Wall, Annular Pile Rings'
folder = ROOT / 'ring_wall' / 'bpad' / 'journal'
v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))[0]
data = strip_nl((folder / f'{NAME}.xml').read_bytes())
assert v['report_name'] == NAME and v['title'] == TITLE and sha(data) == v['fragment_sha256'], 'C017 fragment differs from its verification record'
case = json.loads((ROOT / 'project_current' / 'pier_wall' / 'selected_case.json').read_text(encoding='utf-8-sig'))
assert (case['length_in'], case['thickness_in'], case['height_in'], case['pile_free_length_in']) == (219.0, 36.0, 194.8625, 92.4), case
assert (case['ring_t_in'], case['ring_od_in'], case['ring_id_in'], case['weld_leg_in']) == (0.5, 23.0, 20.125, 0.3125), case
receipt = json.loads((ROOT / 'project_current/coherence/evidence/2026-10-22b-pier-wall/source_receipt.json').read_text(encoding='utf-8'))
assert receipt['decision'] == DECISION_ID and receipt['files']['selected_case']['sha256'] == sha((ROOT / 'project_current/pier_wall/selected_case.json').read_bytes())
from ring_wall.output import case_hash  # noqa: E402
from ring_wall.model import analyze  # noqa: E402
result = analyze(case)
assert v['case_sha256'] == case_hash(result) == receipt['generator']['case_sha256'], 'C017 edition was not built from the registered case'
ratios = {c['id']: c['ratio'] for c in result['checks']}
assert ratios['WELD-MAX'] == 0.3125 / (0.5 - 0.0625) and abs(ratios['WELD-MIN'] - 0.8) < 1e-12, (ratios['WELD-MAX'], ratios['WELD-MIN'])
PLATE_RATIO = max(c['ratio'] for c in result['checks'] if c['id'].endswith('-PLATE'))
WELD_RATIO = max(c['ratio'] for c in result['checks'] if c['id'].endswith('-WELD'))
root = E.fromstring(data)
old = E.fromstring(base.part(f'report:{NAME}'))
assert root.get('name') == NAME == old.get('name') and root.get('title') == TITLE == old.get('title')
names_new = {bs.split_definition(d.get('formula'))[0] for d in root.iter('dynexp')} - {None}
names_old = {bs.split_definition(d.get('formula'))[0] for d in old.iter('dynexp')} - {None}
assert names_new == names_old and sum(dyn(root).values()) == sum(dyn(old).values()), 'C017: definition names or count differ'
for el, t in bs.visible_text_elements(root):
    m = bs.SUBMISSION_FORBIDDEN.search(t)
    assert not m, f'{NAME}: working language {m.group(0)!r}: {t[:100]}'
assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
changed_defs = [f for f, _ in (caches(root) - caches(old)).elements()]
# the base module (T034) carried the 3/4-in plate; the wall, diameters, forces and moment must be the same definitions and caches
same = {'ring_t_in': '0.75', 'ring_od_in': '23', 'ring_id_in': '20.125', 'length_in': '219', 'height_in': '194.8625'}
old_values = {bs.split_definition(d.get('formula'))[0]: (d.findtext('expresult') or '').strip().lstrip('= ') for d in old.iter('dynexp')}
new_values = {bs.split_definition(d.get('formula'))[0]: (d.findtext('expresult') or '').strip().lstrip('= ') for d in root.iter('dynexp')}
assert old_values['ring_t_in'].startswith('0.75') and new_values['ring_t_in'].startswith('0.5'), (old_values['ring_t_in'], new_values['ring_t_in'])
for key in ('ring_od_in', 'ring_id_in', 'length_in', 'height_in', 'weld_leg_in', 'ring_moment', 'wall_rotation', 'kern_limit', 'total_factored'):
    assert old_values[key] == new_values[key], (key, old_values[key], new_values[key])
out[f'report:{NAME}'] = data
record[NAME] = {'source': f'ring_wall/bpad/journal/{NAME}.xml', 'fragment_sha256': v['fragment_sha256'], 'case_sha256': v['case_sha256'],
                'definitions': sum(dyn(root).values()), 'status': v['status'], 'failed_checks': v['failed_checks'],
                'definitions_with_changed_formula_or_cache': len(set(changed_defs)), 'ring_t_in': (0.75, 0.5),
                'largest_plate_bending_ratio': PLATE_RATIO, 'largest_fillet_ratio': WELD_RATIO}

# --- PedBridge: the revision note ---
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
REVISION_NOTE = ('Revision: 22 October 2026, pier wall ring plate 1/2 in (T037): by user direction the annular pile-ring plate of C017 Pier Wall, Annular '
                 'Pile Rings is 1/2 in thick in place of 3/4 in. The thicker plate was not strength-governed (plate bending 0.05 of capacity); the '
                 'thinnest standard plate with every check at or under 0.95 of its limit is 7/16 in, set by the maximum fillet at the ring edge with the '
                 '5/16-in fillet, and the user selected 1/2 in. C017 is regenerated from the second 22 October starting case: ring diameters, fillets, '
                 f'wall, forces, rotation, ring moment, contact and bearing unchanged from the previous revision; plate bending {PLATE_RATIO:.2f} and the '
                 f'fillet {WELD_RATIO:.2f} of capacity; 1 failed check, grid clearance, as before. The CAD model rings are 3/4 in until reconciled. '
                 'Native recalculation, appearance and engineering reviews not performed.')
m = re.search(r'^( {8}<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: )', text, re.M)
assert m, 'PedBridge revision paragraph anchor'
anchor_line_start = m.start()
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
assert REVISION_NOTE[:60] not in text
text = text[:anchor_line_start] + note + nl + text[anchor_line_start:]
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + revision note'}

# --- DecisionLog ---
text = base.part('report:DecisionLog').decode('utf-8')
nl = nl_of(text)
DECISION_SECTION = 'PierWallRingPlate20261022'
DECISION_HEADING = '2026-10-22 - Pier wall annular ring plate 1/2 in (T037)'
DECISION = ('User direction of 22 October 2026 (project decision D-078): the annular pile-ring plate of the pier wall is 1/2 in thick in place of the '
            '3/4 in of the first editions. The user asked what the thinnest ring can be with no check above 0.95 of its limit; sweeping the plate '
            'thickness through the calculation with every other input held, the strength checks (plate bending, shear, fillets, base metal, bearing, '
            'contact) reach 0.95 of capacity only at about 0.17 in, while with the 5/16-in fillet the maximum fillet at the ring edge (leg at most the '
            'plate thickness less 1/16 in, LRFD 6.13.3.4) governs: 7/16 in is the thinnest standard plate (0.83), 3/8 in sits at 1.00, and the user '
            'chose 1/2 in. C017 is regenerated from the second 22 October 2026 starting case of the Pier Wall Design notebook (219 × 36 × 194.8625 in '
            'wall, 23 / 20.125 in rings, two 5/16-in fillets, free length to fixity 92.4 in): wall rotation 1.547e-5 rad, 5.397 kip-in per ring, '
            'largest equivalent eccentricity 1.105 in against the 5.187 in kern and all rings in full contact, as before; the largest plate bending ratio '
            f'is {PLATE_RATIO:.3f} and the largest fillet ratio {WELD_RATIO:.3f}; at 1/2 in the minimum fillet of the thicker-part table is 3/16 in '
            '(1/4 in with the gap allowance), so the 5/16-in fillet reads 0.80 of the minimum and 0.71 of the ring-edge maximum; 1 failed check, the '
            'inner face-grid clearance to the 23-in ring, as before. Not changed: the CAD model (its rings of 22 October are 3/4 in thick; reconciliation '
            'pending), C006 (the support concept, fin plates or welded rings, is still undecided), the gravity sheet, C004, the FBMP exports and the '
            'pile and cap calculations. Native recalculation, appearance and engineering reviews not performed; selection is not engineering acceptance.')
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

# PedBridge and DecisionLog keep every definition and cache (their prose names the task, as the T034 and T036 notes do)
for key in ('report:PedBridge', 'report:DecisionLog'):
    new, old = E.fromstring(out[key]), base.elements[key]
    assert dyn(old) == dyn(new) and caches(old) == caches(new), f'{key}: a definition or cache changed'

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T037', 'base_sha256': base.sha256, 'decision': DECISION_ID, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T037', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
