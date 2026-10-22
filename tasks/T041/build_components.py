"""T041: write the three registered component files (rerunnable, byte-surgical).

* PierWallRings (C017): the rebuilt journal edition `ring_wall/bpad/journal/PierWallRings.xml` (LRFD 10th edition
  development, 27-in U legs, D-084), checked against its verification record, the registered case (u_leg_in 27, the
  wall, rings and fillets as T037) and the base module (same name and title; the ledger gained c_b and lambda_rc).
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
DECISION_ID = 'D-084'


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
assert (case['ring_t_in'], case['ring_od_in'], case['ring_id_in'], case['weld_leg_in'], case['u_leg_in']) == (0.5, 23.0, 20.125, 0.3125, 27.0), case
receipt = json.loads((ROOT / 'project_current/coherence/evidence/2026-10-22c-pier-wall/source_receipt.json').read_text(encoding='utf-8'))
assert receipt['decision'] == DECISION_ID and receipt['files']['selected_case']['sha256'] == sha((ROOT / 'project_current/pier_wall/selected_case.json').read_bytes())
from ring_wall.output import case_hash  # noqa: E402
from ring_wall.model import analyze  # noqa: E402
result = analyze(case)
assert v['case_sha256'] == case_hash(result) == receipt['generator']['case_sha256'], 'C017 edition was not built from the registered case'
values = {n['name']: n['value'] for n in result['nodes']}
ratios = {c['id']: c['ratio'] for c in result['checks']}
assert abs(values['ld_basic'] - 2.4 * 0.625 * 60 / 5.5 ** 0.5) < 1e-9 and values['lambda_rc'] == 0.4, (values['ld_basic'], values['lambda_rc'])
assert abs(values['lap_horizontal'] - 1.3 * 1.3 * 0.4 * values['ld_basic']) < 1e-9 and abs(ratios['U-LAP'] - values['lap_horizontal'] / 27.0) < 1e-12
root = E.fromstring(data)
old = E.fromstring(base.part(f'report:{NAME}'))
assert root.get('name') == NAME == old.get('name') and root.get('title') == TITLE == old.get('title')
names_new = {bs.split_definition(d.get('formula'))[0] for d in root.iter('dynexp')} - {None}
names_old = {bs.split_definition(d.get('formula'))[0] for d in old.iter('dynexp')} - {None}
assert names_new - names_old == {'cb_in', 'lambda_rc'} and not (names_old - names_new), sorted(names_new ^ names_old)
assert sum(dyn(root).values()) == sum(dyn(old).values()) + 2, 'C017: definition count'
for el, t in bs.visible_text_elements(root):
    m = bs.SUBMISSION_FORBIDDEN.search(t)
    assert not m, f'{NAME}: working language {m.group(0)!r}: {t[:100]}'
assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
changed_defs = [f for f, _ in (caches(root) - caches(old)).elements()]
old_values = {bs.split_definition(d.get('formula'))[0]: (d.findtext('expresult') or '').strip().lstrip('= ') for d in old.iter('dynexp')}
new_values = {bs.split_definition(d.get('formula'))[0]: (d.findtext('expresult') or '').strip().lstrip('= ') for d in root.iter('dynexp')}
assert old_values['u_leg_in'].startswith('72') and new_values['u_leg_in'].startswith('27'), (old_values['u_leg_in'], new_values['u_leg_in'])
assert old_values['ld_basic'].startswith('42.0') and new_values['ld_basic'].startswith('38.3'), (old_values['ld_basic'], new_values['ld_basic'])
for key in ('ring_t_in', 'ring_od_in', 'ring_id_in', 'length_in', 'height_in', 'weld_leg_in', 'ring_moment', 'wall_rotation', 'kern_limit', 'total_factored'):
    assert old_values[key] == new_values[key], (key, old_values[key], new_values[key])
out[f'report:{NAME}'] = data
record[NAME] = {'source': f'ring_wall/bpad/journal/{NAME}.xml', 'fragment_sha256': v['fragment_sha256'], 'case_sha256': v['case_sha256'],
                'definitions': sum(dyn(root).values()), 'status': v['status'], 'failed_checks': v['failed_checks'],
                'definitions_with_changed_formula_or_cache': len(set(changed_defs)), 'added_definitions': ['cb_in', 'lambda_rc'],
                'u_leg_in': (72.0, 27.0), 'ld_basic_in': (42.0, round(values['ld_basic'], 2)), 'class_b_lap_in': round(values['lap_horizontal'], 2)}

# --- PedBridge: the revision note ---
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
REVISION_NOTE = ('Revision: 22 October 2026, pier wall tension development on LRFD 10th edition 5.10.8.2.1 and 27-in end U return legs (T041): by user '
                 'direction after the question why the U returns of the pier wall were 6 ft long, C017 Pier Wall, Annular Pile Rings develops the bars with '
                 'the basic length 2.4 db fy / sqrt(f\'c) (38.4 in for the #5 bars), the reinforcement location factor 1.3 and the confinement factor 0.4 '
                 '(no transverse reinforcement credited), so the Class B lap is 26.0 in in place of the 71.0 in the former basic length without confinement '
                 'credit asked, and the end U return legs are 27 in (2 ft 3 in) in place of 72 in. Two ledger values were added (c_b and lambda_rc); the wall, '
                 'rings, fillets, forces, rotation, ring moment, contact and bearing values are unchanged from the previous revision; 1 failed check, grid '
                 'clearance, as before. The CAD model legs follow under a decision of their own. Native recalculation, appearance and engineering reviews not '
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
DECISION_SECTION = 'PierWallDevelopmentLrfd20261022'
DECISION_HEADING = '2026-10-22 - Pier wall tension development on LRFD 10th edition 5.10.8.2.1; 27-in end U return legs (T041)'
DECISION = ('User direction of 22 October 2026 (project decision D-084): the pier wall ring calculation develops its bars by LRFD 10th edition 5.10.8.2.1 '
            'and the end U returns get 27-in (2 ft 3 in) legs. The user asked why the U returns were 6 ft long and whether that was the LRFD lap. It was '
            'not: the first editions used a basic length 0.17 db [fy / (1.97 f\'c^1/4)]^2 without confinement credit (42.0 in for the #5 bars, 54.6 in with '
            'the 1.3 top-bar factor, a 71.0-in Class B lap), and the 72-in leg input was set to clear that check. The code gives the basic length 2.4 db fy '
            '/ sqrt(f\'c) = 38.4 in (5.10.8.2.1a), the reinforcement location factor 1.3 for horizontal bars with more than 12 in of concrete cast below '
            'them (5.10.8.2.1b), and the confinement factor db / (cb + ktr) floored at 0.4 with cb = 3.3125 in (the cover to the bar center; half the '
            '11-in pitch is larger) and no transverse reinforcement credited (5.10.8.2.1c): ld = 20.0 in and the Class B lap (5.10.8.4.3) 26.0 in. The '
            'vertical lap allowance stays 60 in against a 20.0-in Class B lap; the verticals are continuous in the model. C017 is regenerated from the third '
            '22 October 2026 starting case of the Pier Wall Design notebook with two ledger values added (cb and lambda_rc); the wall, ring plates, fillets, '
            'forces, rotation, ring moment, contact and bearing results are those of the previous revision, and the grid-clearance failure remains. The CAD '
            'model (its U legs) and the substructure drawings follow under their own records. Native recalculation, appearance and engineering reviews not '
            'performed; selection is not engineering acceptance.')
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
(TASK / 'verification.json').write_text(json.dumps({'task': 'T041', 'base_sha256': base.sha256, 'decision': DECISION_ID, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T041', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
