"""T028: write the three registered component files (rerunnable).

* PierWallRings: the journal edition `ring_wall/bpad/journal/PierWallRings.xml` (scripts/build_ring_wall_bpad.py), checked against
  its verification record (fragment hash, journal file, live stamp), the module identity (new name, C017 title), the visible-text
  rule of scripts/bpad_sheet.py and the hidden working-notes section; no other module reads it, no inbound links exist;
* PedBridge: the C017 index link after the C016 one, the calculations heading, and one revision paragraph before the T027 note
  (exact-substring surgery, CRLF kept);
* DecisionLog: one section appended inside the report.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402

NAME, TITLE = 'PierWallRings', 'C017 - Pier Wall, Annular Pile Rings'
TNR = 'Times New Roman'
REVISION_NOTE = ('Revision: 21 October 2026, C017 Pier Wall, Annular Pile Rings added (T028): the welded annular-ring support concept of the pier '
                 'wall (minimum wall steel and detailing; full annular contact, concrete bearing, plate bending and shear, two continuous fillets and '
                 'adjacent base metal at every ring) enters the journal as its own calculation, generated from the Pier Wall Design notebook '
                 'package (ring_wall) by scripts/build_ring_wall_bpad.py on its starting case: 673 ledger values and 178 check statuses as native '
                 'definitions, each evaluated independently and compared with the notebook to 1 part in 10⁹, with the live project stamp and hidden '
                 'working notes. Ring moment basis D-070 (pile-head compatibility moment; placement tolerance as pile-group redistribution; the '
                 'former tributary-eccentricity moment kept for comparison); pile stiffness defaults from the pier pile case. C006 (fin plates and '
                 'hairpins) is unchanged; which support concept governs is undecided. The module is appended here and moved after C016 by T029. '
                 'Native recalculation, appearance and engineering reviews not performed; no existing value changed.')
DECISION_SECTION = 'PierWallRings20261021'
DECISION_HEADING = '2026-10-21 - C017 Pier Wall, Annular Pile Rings added from the Pier Wall Design notebook (T028, T029)'
DECISION = ('User direction of 21 October 2026 (run the pier wall notebook, update its calculation report and its Blockpad calculation in the journal; '
            'project decision D-071): the pier wall on welded annular pile rings is added as calculation C017 (report PierWallRings), the journal '
            'edition of the ring_wall package on its starting case. The calculation assigns the gross wall self-weight to the rings as vertical force '
            'by midplane tributaries, takes the ring moment as the pile-head compatibility moment of the rigid wall rotating on the axial and '
            'rotational springs of the pile heads with the pile group displaced by the radial placement tolerance (D-070; the former tributary-'
            'eccentricity moment is tabulated for comparison), and checks full annular contact, concrete bearing, plate bending and shear, the two '
            'continuous fillets and the adjacent ring and pipe base metal at every ring, then the minimum shrinkage and temperature steel, spacing, '
            'cover, laps and bar fit of the wall. Starting case: 2 failed checks (ring end cover and inner-grid clearance of the 23-in ring trial), no '
            'ring without full contact, 3.589 kip-in per ring against a 5.187 in kern. The project record selects the same run as PIER-WALL-TOOL, '
            'PIER-WALL-REPORT and PIER-WALL-CASE. C006 (fin plates and hairpins) stays; the choice of support concept is undecided. Native '
            'recalculation, appearance and engineering reviews not performed; no existing journal value changed; FBMP not rerun.')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def once(text, old, label):
    found = text.count(old)
    assert found == 1, f'{label}: expected 1 occurrence, found {found}: {old[:90]!r}'


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {f'report:{NAME}', 'report:PedBridge', 'report:DecisionLog'}, sorted(mapping)
assert f'report:{NAME}' not in base.elements and not any(el.get('name') == NAME for el in base.root), 'module already exists'
out, record = {}, {}

# PierWallRings: the generated journal edition
folder = ROOT / 'ring_wall' / 'bpad' / 'journal'
v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))[0]
data = strip_nl((folder / f'{NAME}.xml').read_bytes())
assert v['report_name'] == NAME and v['journal_file'] == 'journal/D2_I95_Project_Journal.bpad' and v['title'] == TITLE
assert sha(data) == v['fragment_sha256'], 'fragment differs from its verification record; rebuild the journal edition'
assert v['project_stamp']['owner'] == bs.PROJECT_INFO and v['project_stamp']['live']
root = E.fromstring(data)
assert root.tag == 'report' and root.get('name') == NAME and root.get('title') == TITLE, (root.tag, root.get('name'), root.get('title'))
defined = {bs.split_definition(d.get('formula'))[0] for d in root.iter('dynexp')} - {None}
for el, text in bs.visible_text_elements(root):
    m = bs.SUBMISSION_FORBIDDEN.search(text)
    assert not m, f'{NAME}: working language {m.group(0)!r}: {text[:100]}'
assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
externals = {m.group(0) for d in root.iter('dynexp') for m in re.finditer(r'\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b', d.get('formula'))}
assert externals <= {f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS}, f'unexpected references to other modules: {sorted(externals)}'
qual = re.compile(r'\b' + re.escape(NAME) + r'\.')
for key, el in base.elements.items():
    for node in el.iter():
        for text in (node.get('formula'), node.text if node.tag == 'expbody' else None):
            assert not (text and qual.search(text)), f'{key} already reads {NAME}'
        assert not (node.tag == 'link' and (node.get('address') or '').startswith('#' + NAME)), f'{key} already links to {NAME}'
out[f'report:{NAME}'] = data
record[NAME] = {'source': f'ring_wall/bpad/journal/{NAME}.xml', 'fragment_sha256': v['fragment_sha256'], 'definitions': len(defined),
                'ledger_values_compared': v['ledger_values_compared'], 'check_statuses_compared': v['check_statuses_compared'],
                'case_sha256': v['case_sha256'], 'source_sha256': v['source_sha256'], 'status': v['status'], 'status_words': v['status_words'],
                'journal_references': v['journal_references'], 'reads': sorted(externals), 'title': TITLE, 'added': True}

# PedBridge: index link, heading, revision note
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
c016 = (' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + nl
        + ' ' * 12 + '<link address="#BearingDesign">C016 - Bearings and Support Details</link>' + nl + ' ' * 8 + '</paragraph>')
once(text, c016, 'PedBridge C016 index paragraph')
c017 = (' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">' + nl
        + ' ' * 12 + f'<link address="#{NAME}">{TITLE} (21 October 2026 case)</link>' + nl + ' ' * 8 + '</paragraph>')
assert f'#{NAME}' not in text
text = text.replace(c016, c016 + nl + c017)
heading_old, heading_new = '<heading level="1" keepwithnext="True">Calculations C001 to C016</heading>', '<heading level="1" keepwithnext="True">Calculations C001 to C017</heading>'
once(text, heading_old, 'PedBridge calculations heading')
text = text.replace(heading_old, heading_new)
anchor = ' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: 21 October 2026, notebook editions of C001 to C004, C006, C015 and C016 (T027):'
once(text, anchor, 'PedBridge T027 revision paragraph')
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
text = text.replace(anchor, note + nl + anchor)
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + C017 index link, heading C001 to C017, revision note'}

# DecisionLog: the entry
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

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T028', 'base_sha256': base.sha256, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T028', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
