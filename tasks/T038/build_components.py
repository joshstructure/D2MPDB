"""T038: write the three registered component files (rerunnable).

* PierCheekWalls: the journal edition `pier_cheek_wall/bpad/journal/PierCheekWalls.xml` (scripts/build_pier_cheek_wall.py --journal),
  checked against its verification record (fragment hash, journal file, live stamp, the registered case), the module identity (new name,
  C018 title), the visible-text rule of scripts/bpad_sheet.py, the hidden working-notes section, and its outbound references (five C001
  definitions that exist once in the base journal, plus the ProjectInfo stamp); no other module reads it, no inbound links exist;
* PedBridge: the C018 index link after the C017 one, the calculations heading, and one revision paragraph before the newest revision note
  (exact-substring surgery, CRLF kept);
* DecisionLog: one section appended inside the report.
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

NAME, TITLE = 'PierCheekWalls', 'C018 - Pier Cap Cheek Wall Design'
TNR = 'Times New Roman'
DECISION_ID = 'D-081'
REVISION_NOTE = ('Revision: 22 October 2026, C018 Pier Cap Cheek Wall Design added (T038): the two pier cap cheek walls of the CAD model '
                 '(48 x 48 x 12 in with the recessed panel; centred #4 mat at 10 in each way, verticals developed 12 in straight into the cap) '
                 'enter the journal as their own calculation, generated from the Pier Cheek Wall Design notebook package (pier_cheek_wall, '
                 'calc_common framework) by scripts/build_pier_cheek_wall.py on its starting case: wind directly on the walls per LRFD 3.8.1.2.1 '
                 'and 3.8.1.2.3b with the C001 wind speeds, exposure coefficient and gust factor as live references and the C002 substructure '
                 'drag coefficient; the wall as a cantilever from the cap top checked for flexure, minimum flexure, shear, interface shear, '
                 'crack control, straight development, shrinkage and temperature steel, spacing, cover and thickness. 183 native definitions, '
                 '174 values compared with the notebook to 1 part in 10⁹, live project stamp and hidden working notes. Every numerical check '
                 'passes; the development and the cover sit exactly at their limits and the one-centred-mat shrinkage and temperature convention '
                 'is pending confirmation. The project record selects the same run as CHEEK-TOOL, CHEEK-REPORT and CHEEK-CASE (D-081). The module '
                 'is appended here and moved after C017 by T039. Native recalculation, appearance and engineering reviews not performed; no '
                 'existing value changed.')
DECISION_SECTION = 'PierCheekWalls20261022'
DECISION_HEADING = '2026-10-22 - C018 Pier Cap Cheek Wall Design added from the Pier Cheek Wall Design notebook (T038, T039)'
DECISION = ('User direction of 22 October 2026 (select the pier cap cheek wall calculation as a current project source and add it to the journal '
            'as C018; project decision D-081): the pier cap cheek walls are added as calculation C018 (report PierCheekWalls), the journal edition '
            'of the pier_cheek_wall package on its starting case (the D-059 walls and D-061 straight cap embedment of the CAD model, the C001 wind '
            'values, the C002 substructure drag coefficient and the pier cap materials). The calculation applies the LRFD 3.8.1.2.1 design wind '
            'pressure with the C001 speeds, exposure coefficient and gust factor and the 1.6 drag coefficient of C002 normal to the broad face of '
            'each wall (LRFD 3.8.1.2.3b; the full pressure governs every skew, the edge force is reported for the pier), with WS = 1.0 in Strength '
            'III, Strength V and Service I; treats the wall as a 48-in-wide cantilever from the cap top at the cap-top section and the recessed '
            'panel section; and checks flexure, minimum flexural resistance, shear, interface shear at the construction joint, crack control, '
            'the straight development of the verticals into the cap, shrinkage and temperature steel, bar spacing, clear spacing, cover and the '
            'SDM minimum thickness. Starting case: Strength III pressure 0.0600 ksf, 0.96 kip transverse and 0.24 kip longitudinal per wall, '
            'cantilever moment 1.920 kip-ft and shear 0.960 kip at the cap top; every numerical check passes (flexure 0.07 of capacity); the '
            '12-in straight development (the LRFD 5.10.8.2.1a floor once the excess-reinforcement factor applies; 12.28 in for full yield without '
            'it) and the 2-in cover sit exactly at their limits; the shrinkage and temperature steel (0.73) carries both face requirements in the '
            'one centred mat, pending confirmation of that convention as for the end bents. The project record selects the same run as CHEEK-TOOL, '
            'CHEEK-REPORT and CHEEK-CASE. C014 (end-bent backwall and cheek walls) is unchanged. Native recalculation, appearance and engineering '
            'reviews not performed; no existing journal value changed; FBMP not rerun; selection is not engineering acceptance.')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def once(text, old, label):
    found = text.count(old)
    assert found == 1, f'{label}: expected 1 occurrence, found {found}: {old[:90]!r}'


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))

base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {f'report:{NAME}', 'report:PedBridge', 'report:DecisionLog'}, sorted(mapping)
assert f'report:{NAME}' not in base.elements and not any(el.get('name') == NAME for el in base.root), 'module already exists'
out, record = {}, {}

# --- C018: the generated journal edition ---
folder = ROOT / 'pier_cheek_wall' / 'bpad' / 'journal'
v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))[0]
data = strip_nl((folder / f'{NAME}.xml').read_bytes())
assert v['report_name'] == NAME and v['journal_file'] == 'journal/D2_I95_Project_Journal.bpad'
assert sha(data) == v['fragment_sha256'], 'fragment differs from its verification record; rebuild the journal edition'
assert v['project_stamp']['owner'] == bs.PROJECT_INFO and v['literals_kept'] == [], (v['project_stamp'], v['literals_kept'])
# the registered case (CHEEK-CASE, D-081) is the case the edition was built from
from calc_common.bpad import case_sha  # noqa: E402
from calc_common.model import evaluate  # noqa: E402
from pier_cheek_wall.model import SPEC  # noqa: E402
from pier_cheek_wall.exports import load_case  # noqa: E402
case_bytes = (ROOT / 'project_current' / 'pier_cheek_wall' / 'selected_case.json').read_bytes()
receipt = json.loads((ROOT / 'project_current/coherence/evidence/2026-10-22-pier-cheek-wall-selection/source_receipt.json').read_text(encoding='utf-8'))
assert receipt['decision'] == DECISION_ID and receipt['files']['selected_case']['sha256'] == sha(case_bytes)
e = evaluate(SPEC, load_case(case_bytes))
assert v['case_sha256'] == case_sha(e) == receipt['generator']['case_sha256'], 'C018 edition was not built from the registered case'
assert v['package_revision'] == receipt['generator']['package_revision'], 'package revision differs from the registered export'
assert not [c.key for c in e.checks if 'FAIL' in c.status] and v['status'] == e.blockpad_status, (v['status'], e.blockpad_status)
root = E.fromstring(data)
assert root.tag == 'report' and root.get('name') == NAME and root.get('title') == TITLE == SPEC.full_title, (root.tag, root.get('name'), root.get('title'))
defined = {bs.split_definition(d.get('formula'))[0] for d in root.iter('dynexp')} - {None}
for el, text in bs.visible_text_elements(root):
    m = bs.SUBMISSION_FORBIDDEN.search(text)
    assert not m, f'{NAME}: working language {m.group(0)!r}: {text[:100]}'
assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
externals = {m.group(0) for d in root.iter('dynexp') for m in re.finditer(r'\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b', d.get('formula'))}
allowed = {f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS} | set(v['references'])
assert externals <= allowed, f'unexpected references to other modules: {sorted(externals - allowed)}'
assert set(v['references']) <= externals, f'verified references missing from the module: {sorted(set(v["references"]) - externals)}'
for qualified in v['references']:                      # each referenced definition exists exactly once in the base journal
    owner, name = qualified.split('.', 1)
    defs = [d for d in base.elements[f'report:{owner}'].iter('dynexp') if bs.split_definition(d.get('formula'))[0] == name]
    assert len(defs) == 1, f'{qualified}: {len(defs)} definitions in the base journal'
qual = re.compile(r'\b' + re.escape(NAME) + r'\.')
for key, el in base.elements.items():
    for node in el.iter():
        for text in (node.get('formula'), node.text if node.tag == 'expbody' else None):
            assert not (text and qual.search(text)), f'{key} already reads {NAME}'
        assert not (node.tag == 'link' and (node.get('address') or '').startswith('#' + NAME)), f'{key} already links to {NAME}'
out[f'report:{NAME}'] = data
record[NAME] = {'source': f'pier_cheek_wall/bpad/journal/{NAME}.xml', 'fragment_sha256': v['fragment_sha256'], 'definitions': len(defined),
                'dynexp_count': sum(dyn(root).values()), 'tool_comparisons': v['tool_comparisons'], 'case_sha256': v['case_sha256'],
                'package_revision': v['package_revision'], 'status': v['status'], 'journal_references': v['journal_references'],
                'reads': sorted(externals), 'failed_checks': [], 'pending_checks': sorted(c.key for c in e.checks if 'PENDING' in c.status),
                'checks_at_limit': sorted(c.key for c in e.checks if isinstance(c.ratio, float) and abs(c.ratio - 1.0) < 1e-9),
                'title': TITLE, 'added': True}

# --- PedBridge: index link, heading, revision note ---
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
c017 = (' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + nl
        + ' ' * 12 + '<link address="#PierWallRings">C017 - Pier Wall, Annular Pile Rings (21 October 2026 case)</link>' + nl + ' ' * 8 + '</paragraph>')
once(text, c017, 'PedBridge C017 index paragraph')
c018 = (' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + nl
        + ' ' * 12 + f'<link address="#{NAME}">{TITLE} (22 October 2026 case)</link>' + nl + ' ' * 8 + '</paragraph>')
assert f'#{NAME}' not in text
text = text.replace(c017, c017 + nl + c018)
heading_old, heading_new = '<heading level="1" keepwithnext="True">Calculations C001 to C017</heading>', '<heading level="1" keepwithnext="True">Calculations C001 to C018</heading>'
once(text, heading_old, 'PedBridge calculations heading')
text = text.replace(heading_old, heading_new)
m = re.search(r'^( {8}<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: )', text, re.M)
assert m, 'PedBridge revision paragraph anchor'
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
assert REVISION_NOTE[:60] not in text
text = text[:m.start()] + note + nl + text[m.start():]
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + C018 index link, heading C001 to C018, revision note'}

# --- DecisionLog: the entry ---
text = base.part('report:DecisionLog').decode('utf-8')
nl = nl_of(text)
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

# PedBridge and DecisionLog keep every definition and cache
for key in ('report:PedBridge', 'report:DecisionLog'):
    new, old = E.fromstring(out[key]), base.elements[key]
    assert dyn(old) == dyn(new) and caches(old) == caches(new), f'{key}: a definition or cache changed'

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T038', 'base_sha256': base.sha256, 'decision': DECISION_ID, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T038', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
