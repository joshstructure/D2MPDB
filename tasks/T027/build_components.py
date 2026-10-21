"""T027: write the nine registered component files from the notebook-generated journal editions and two surgical edits (rerunnable).

* the seven calculations: `<package>/bpad/journal/<Report>.xml` (scripts/build_journal_calc_bpads.py --journal), each checked
  against its verification record (fragment hash, journal file, live stamp), against the base module (same report name and
  C-number title; every name another journal module reads from it still defined; every inbound native link target — the
  anchored paragraph ids and the named sections — still present) and against the visible-text rule of scripts/bpad_sheet.py;
* PedBridge: one revision paragraph inserted before the T024 note (exact-substring surgery, CRLF kept);
* DecisionLog: one section appended inside the report.
"""
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree as E

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402

PACKAGES = {'C001WindLoadOnPedBridgeSuperstructure': 'wind_superstructure', 'FenceWind': 'fence_wind', 'BridgeMovement': 'bridge_movement',
            'SuperstructureUplift': 'superstructure_uplift', 'PierWallFins': 'pier_wall_fins', 'MSEWallExclusion': 'mse_wall_exclusion',
            'BearingDesign': 'bearing_design'}
ACCEPTED = {'FenceWind': ('Task Work Order',), 'SuperstructureUplift': ('Task Work Order',)}
TNR = 'Times New Roman'
REVISION_NOTE = ('Revision: 21 October 2026, notebook editions of C001 to C004, C006, C015 and C016 (T027): the seven calculations that had no '
                 'Colab notebook are now generated from their notebooks (packages wind_superstructure, fence_wind, bridge_movement, '
                 'superstructure_uplift, pier_wall_fins, mse_wall_exclusion and bearing_design on the shared calc_common framework). '
                 'Each notebook was run with the journal values; every definition of the former hand-authored module was evaluated '
                 'independently from the journal file and reproduced by the notebook to 1 part in 10⁹ before its journal edition was written. '
                 'The editions keep the report names, the C-number titles, the names other modules read (as live references passed through '
                 'the coherence gate), the native figures, the design-basis prose with its anchors and the live project stamp; the per-equation '
                 'notes, step navigation and echoed value displays are distilled out (they remain in the notebook reports). C016 omits the '
                 'eleven superseded D-064/D-065 status strings (recorded in its working notes); C015 keeps its two knife-edge SHORTFALL rows. '
                 'Native recalculation, appearance and engineering reviews not performed; no engineering value changed.')
DECISION_SECTION = 'NotebookCalculations20261021'
DECISION_HEADING = '2026-10-21 - C001 to C004, C006, C015 and C016 generated from Colab notebooks (T027)'
DECISION = ('User direction of 21 October 2026: every journal calculation without a Colab notebook gets a notebook of the same build type as the '
            'cap, pile and backwall notebooks, is run with the journal input values, and its distilled Blockpad edition replaces the hand-authored '
            'module. The seven packages (wind_superstructure C001, fence_wind C002, bridge_movement C003, superstructure_uplift C004, '
            'pier_wall_fins C006, mse_wall_exclusion C015, bearing_design C016) share the calc_common framework: one definition list evaluated by '
            'the unit-aware engine drives the notebook, the calculation report (definition and citation cards, equation notes, native figures), '
            'the case / checks / report / Blockpad exports and the journal edition with live references. The journal values they were run with '
            'are the values the journal holds for the inputs each module reads from Bridge Geometry, Materials, the gravity sheet, Pile Section '
            'Properties and the other calculations; the literal inputs of each module (wind speeds, temperatures, factors, trial details, the '
            'saved beam-worksheet rotations, the CAD wall lines) are carried as amber inputs with their provisions. Independent evaluation of the '
            'former modules reproduced 697 definitions to 1 part in 10⁹. The eleven superseded D-064/D-065 status strings of C016 are not '
            'definitions of the new edition; the adopted level seat elevations and pad thickness remain inputs. C015 keeps its knife-edge side-wall '
            'rows (model coordinates 0.0002 in short of 24 in), so its Status reads as failures exactly as the former rows did. Native '
            'recalculation, appearance and engineering reviews not performed; FBMP not rerun; no engineering value changed.')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def once(text, old, label):
    found = text.count(old)
    assert found == 1, f'{label}: expected 1 occurrence, found {found}: {old[:90]!r}'


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


def inbound(base, name):
    """(names other components read from `name`, inbound link addresses) in the base journal."""
    qual = re.compile(r'\b' + re.escape(name) + r'\.([A-Za-z_Ͱ-Ͽ][A-Za-z_0-9Ͱ-Ͽ]*)')
    names, links = set(), set()
    for key, el in base.elements.items():
        if key.split(':', 1)[1] == name:
            continue
        for node in el.iter():
            for text in (node.get('formula'), node.text if node.tag == 'expbody' else None):
                if text:
                    names.update(m.group(1) for m in qual.finditer(text))
            if node.tag == 'link' and (node.get('address') or '').startswith('#' + name):
                links.add(node.get('address'))
    return names, links


def link_targets_present(root, name, links):
    ids = {n.get('id') for n in root.iter() if n.get('id')}
    sections = {s.get('name') for s in root.iter('section')}
    missing = []
    for addr in sorted(links):
        m = re.match(r'#' + re.escape(name) + r'(?:\.([A-Za-z0-9_]+))?(?:;([A-Za-z0-9_]+))?$', addr)
        if not m:
            missing.append(addr)
            continue
        section, pid = m.group(1), m.group(2)
        if section and section not in sections:
            missing.append(addr)
        elif pid and pid not in ids:
            missing.append(addr)
    return missing


base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert {k.split(':', 1)[1] for k in mapping} == set(PACKAGES) | {'PedBridge', 'DecisionLog'}, sorted(mapping)
out, record = {}, {}
for name, package in PACKAGES.items():
    folder = ROOT / package / 'bpad' / 'journal'
    v = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))[0]
    raw = (folder / f'{name}.xml').read_bytes()
    data = strip_nl(raw)
    assert v['report_name'] == name and v['journal_file'] == 'journal/D2_I95_Project_Journal.bpad', name
    assert sha(data) == v['fragment_sha256'], f'{name}: fragment differs from its verification record; rebuild the journal edition'
    assert v['project_stamp']['owner'] == bs.PROJECT_INFO
    root = E.fromstring(data)
    old = base.elements[f'report:{name}']
    assert root.get('name') == name and root.get('title') == old.get('title'), (name, root.get('title'), old.get('title'))
    defined = {bs.split_definition(d.get('formula'))[0] for d in root.iter('dynexp')} - {None}
    names, links = inbound(base, name)
    missing_names = sorted(names - defined)
    assert not missing_names, f'{name}: names other modules read are no longer defined: {missing_names}'
    missing_links = link_targets_present(root, name, links)
    assert not missing_links, f'{name}: inbound link targets missing: {missing_links}'
    for el, text in bs.visible_text_elements(root):
        m = bs.SUBMISSION_FORBIDDEN.search(text)
        assert not m or any(a in text for a in ACCEPTED.get(name, ())), f'{name}: working language {m.group(0)!r}: {text[:100]}'
    assert [s.get('name') for s in root.iter('section') if s.get('name') == bs.WORKING_NOTES] == [bs.WORKING_NOTES]
    out[f'report:{name}'] = data
    record[name] = {'source': f'{package}/bpad/journal/{name}.xml', 'fragment_sha256': v['fragment_sha256'], 'definitions': len(defined),
                    'journal_references': v['journal_references'], 'status': v['status'], 'names_read_by_other_modules': sorted(names),
                    'inbound_links': len(links), 'title': root.get('title'), 'definitions_before': len({bs.split_definition(d.get('formula'))[0] for d in old.iter('dynexp')} - {None})}

# PedBridge: the revision note
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
anchor = ' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: 20 October 2026, project stamp and module order (T024):'
once(text, anchor, 'PedBridge T024 revision paragraph')
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
text = text.replace(anchor, note + nl + anchor)
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + revision note'}

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
(TASK / 'verification.json').write_text(json.dumps({'task': 'T027', 'base_sha256': base.sha256, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T027', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
