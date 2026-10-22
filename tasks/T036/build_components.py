"""T036: write the seven registered component files (rerunnable, byte-surgical).

* CapDesignPier and PileDesignPier: the regenerated journal editions (`cap_bpad/journal/CapDesignPier.xml`,
  `pile_bpad/journal/PileDesignPier.xml`), checked against their verification records (fragment hash, the D-077 export
  identity, live stamp / coherence gate) and against the base modules: same report name, title and definition names.
  The cap values change (force envelopes, ratios); the pile values change (demands); recorded.
* FBMPPier, FoundationModeling, BridgeGeometry_2Beam: exact-substring surgery on the paragraphs that name the pier
  export or the pier cap report (every anchor must occur exactly once; CRLF kept); definitions, caches and canvases
  of these modules must be unchanged.
* PedBridge: one revision paragraph before the newest revision note. DecisionLog: one section appended.
"""
import csv
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
NEW_XML = '420e614aa8b9784b5f0e8160689f90d7480fec7dc3541ee7c687c5eadfd355e6'
OLD_XML = '8be45bb889f5c955d0547ce6a538118bbce87600d40a65b094255e6b9b76e3b6'
OLD_OLD_XML = 'bb73e6ada6cf35ebb80b512cee315075807fc8ccab7878406d81ff381ae40fe7'
OLD_REPORT = '216c26dd78b4394451c0726b3246bc29fafb646a1b06dc6e73607ca445a0eed2'
OLD_OLD_REPORT = 'e49d579c0186e7c2617828d236cb982adb92122345493a097e7c352df2f3a701'
OLD_OLD_OLD_REPORT = '7a9f48ce08bdc29f22a1b6717432dc363f0c2d8cec02ffbfc0a36bb7da39dee2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_nl(raw):
    return raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw


def once(text, old, label):
    found = text.count(old)
    assert found == 1, f'{label}: expected 1 occurrence, found {found}: {old[:90]!r}'


def swap(text, old, new, label):
    once(text, old, label)
    assert new not in text, f'{label}: replacement text already present'
    return text.replace(old, new)


def nl_of(text):
    return '\r\n' if '\r\n' in text else '\n'


# --- project record identities (register, receipts) ---
with (ROOT / 'project_current' / 'source_register.csv').open(newline='', encoding='utf-8-sig') as f:
    register = {r['source_id']: r for r in csv.DictReader(f)}
assert register['PIER-XML']['sha256'] == NEW_XML and register['PIER-XML']['registered_on'] == '2026-10-22'
cap_receipt = json.loads((ROOT / 'project_current/coherence/evidence/2026-10-22-cap-rerun/source_receipt.json').read_text(encoding='utf-8'))
pile_receipt = json.loads((ROOT / 'project_current/coherence/evidence/2026-10-22-pile-reports/source_receipt.json').read_text(encoding='utf-8'))
NEW_REPORT = cap_receipt['run']['files']['report']['sha256']
assert cap_receipt['run']['xml']['sha256'] == NEW_XML and cap_receipt['run']['previous_case_sha256'] != cap_receipt['run']['files']['selected_case']['sha256']
assert register['PIER-REPORT']['sha256'] == NEW_REPORT and register['PIER-REPORT']['path'].endswith('Pier Cap Design 10-22.html')
CAP_CHANGED = cap_receipt['run']['inputs_changed']
assert set(CAP_CHANGED) == {'Mu_N', 'Mu_P', 'Mu_B', 'Vu_G', 'Vu_L', 'Tu', 'MI_N', 'MI_P', 'MI_B'}, sorted(CAP_CHANGED)
assert not any(c.get('status_before') != c.get('status_after') for c in cap_receipt['run']['check_changes'] if isinstance(c, dict))
pile_run = next(r for r in pile_receipt['reports'] if r['support'] == 'Pier')
assert pile_run['fbmp_export']['sha256'] == NEW_XML
PILE_REPORT = pile_run['files']['report']['sha256']
assert register['PILE-PIER-REPORT']['sha256'] == PILE_REPORT
PILE_PENDING = pile_run['check_register']['pending_items']
PILE_DC = pile_run['check_register']['strength_dc']

base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {'report:CapDesignPier', 'report:PileDesignPier', 'report:FBMPPier', 'report:FoundationModeling',
                        'report:BridgeGeometry_2Beam', 'report:PedBridge', 'report:DecisionLog'}, sorted(mapping)
out, record = {}, {}

dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
cel = lambda el: Counter(e.get('formula') for e in el.iter() if e.tag in ('c', 'planecontainer', 'lineardim', 'plot') and e.get('formula'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))
texts = lambda el: Counter(' '.join(''.join(p.itertext()).split()) for p in el.iter('paragraph'))
names_of = lambda el: {bs.split_definition(d.get('formula'))[0] for d in el.iter('dynexp')} - {None}


def adopt_edition(name, folder, verification, expect):
    """Copy a regenerated journal edition after checking it against its verification record and the base module."""
    data = strip_nl((folder / f'{name}.xml').read_bytes())
    assert sha(data) == verification['fragment_sha256'], f'{name}: fragment differs from its verification record; rebuild the edition'
    assert verification['fbmp_sha256'] == NEW_XML and verification['fbmp_file'] == 'Pier_Fixed.XML', name
    for key, value in expect.items():
        assert verification[key] == value, (name, key, verification[key], value)
    root, old = E.fromstring(data), base.elements[f'report:{name}']
    assert root.tag == 'report' and root.get('name') == name and root.get('title') == old.get('title'), (name, root.get('title'))
    assert names_of(root) == names_of(old), f'{name}: definition names differ: {sorted(names_of(root) ^ names_of(old))[:20]}'
    assert sum(dyn(root).values()) == sum(dyn(old).values()), f'{name}: definition count differs'
    changed = len(set((caches(root) - caches(old)).elements()))
    for el, text in bs.visible_text_elements(root):
        m = bs.SUBMISSION_FORBIDDEN.search(text)
        assert not m, f'{name}: working language {m.group(0)!r}: {text[:100]}'
    assert not any(OLD_XML[:12] in t for t in texts(root)) and any(NEW_XML[:12] in t for t in texts(root)), f'{name}: export identity text'
    out[f'report:{name}'] = data
    record[name] = {'source': str(folder.relative_to(ROOT).as_posix()) + f'/{name}.xml', 'fragment_sha256': verification['fragment_sha256'],
                    'fbmp_sha256': verification['fbmp_sha256'], 'status': verification['status'], 'definitions': sum(dyn(root).values()),
                    'definitions_with_changed_formula_or_cache': changed, 'canvases_unchanged': cel(old) == cel(root)}


cap_v = next(r for r in json.loads((ROOT / 'cap_bpad/journal/verification.json').read_text(encoding='utf-8'))['reports'] if r['report_name'] == 'CapDesignPier')
adopt_edition('CapDesignPier', ROOT / 'cap_bpad' / 'journal', cap_v, {'report_file': 'Pier Cap Design 10-22.html', 'literals_kept': []})
pile_v = next(r for r in json.loads((ROOT / 'pile_bpad/journal/verification.json').read_text(encoding='utf-8')) if r['report_name'] == 'PileDesignPier')
adopt_edition('PileDesignPier', ROOT / 'pile_bpad' / 'journal', pile_v, {'stamp': 'live', 'support': 'Pier'})

WALL = ('the four vertical 36 x 60 in pier wall members between the pile nodes now span pile points 2 to 11 (EL 40.20 to the soil surface EL 26.05, '
        '169.8 in, 127.3 kip in all) in place of points 2 to 13 (EL 19.72, 245.8 in, 184.4 kip in all); nodal and bearing loads, geometry, pile '
        'section and material, soil and the four load combinations are identical')

# --- FBMPPier ---
text = base.part('report:FBMPPier').decode('utf-8')
text = swap(text,
            'Geometry source: Pier Cap Design 10-21.html (D-073: the 10-19 report, D-051, rerun on the 21 October 2026 export with every force envelope, ratio and status unchanged; supersedes Pier Cap Design 10-9.html generated 2026-10-09T22:19:21+00:00); case Pier_Fixed — XML analysis. Pile design: PileDesignPier (D-054; rerun D-073).',
            'Geometry source: Pier Cap Design 10-22.html (D-077: the 10-21 report, D-073, rerun on the 22 October 2026 export, nine force inputs moved and no status changed; the 10-19 report was D-051; supersedes Pier Cap Design 10-9.html generated 2026-10-09T22:19:21+00:00); case Pier_Fixed — XML analysis. Pile design: PileDesignPier (D-054; reruns D-073 and D-077).',
            'FBMPPier geometry source')
text = swap(text,
            f'Report SHA-256: {OLD_REPORT} (Pier Cap Design 10-21.html; the 10-19 report was {OLD_OLD_REPORT} and the 10-9 report {OLD_OLD_OLD_REPORT})',
            f'Report SHA-256: {NEW_REPORT} (Pier Cap Design 10-22.html; the 10-21 report was {OLD_REPORT}, the 10-19 report {OLD_OLD_REPORT} and the 10-9 report {OLD_OLD_OLD_REPORT})',
            'FBMPPier report hash')
text = swap(text,
            f'Report-identified Pier_Fixed.XML SHA-256: {OLD_XML} (D-073, 21 October 2026, held in project_current/fbmp/pier/; the 10-19 report identified {OLD_OLD_XML}, D-049, now archived under fbmp/pier/archive/2026-10-19/, and the 10-9 report',
            f'Report-identified Pier_Fixed.XML SHA-256: {NEW_XML} (D-077, 22 October 2026, held in project_current/fbmp/pier/; the 10-21 report identified {OLD_XML}, D-073, now archived under fbmp/pier/archive/2026-10-22/, the 10-19 report {OLD_OLD_XML}, D-049, archived under fbmp/pier/archive/2026-10-19/, and the 10-9 report',
            'FBMPPier XML hash')
text = swap(text,
            'the pier cap case rerun from it keeps every force envelope, ratio and status, and the pier pile demands are unchanged.</paragraph>',
            'the pier cap case rerun from it keeps every force envelope, ratio and status, and the pier pile demands are unchanged. '
            f'22 October 2026 (D-077): the user’s rerun Pier_Fixed.XML corrects the pier wall extra members, which had followed the soil elevation changes: {WALL}. '
            'The pier cap case rerun from it moves nine force inputs (largest: Mu_B 365.84 to 361.01 kip-ft, Vu 218.96 to 220.46 kip) with no status change; the pier pile demands follow the export.</paragraph>',
            'FBMPPier resolved note')
E.fromstring(text.encode('utf-8'))
out['report:FBMPPier'] = text.encode('utf-8')
record['FBMPPier'] = {'source': 'base.bpad + geometry source, report and XML identities, resolved note'}

# --- FoundationModeling ---
text = base.part('report:FoundationModeling').decode('utf-8')
text = swap(text, '<heading level="1" keepwithnext="True">Current model sources — 19 and 21 October 2026</heading>',
            '<heading level="1" keepwithnext="True">Current model sources — 19 and 22 October 2026</heading>', 'FoundationModeling heading')
text = swap(text,
            f'and, for the pier, the 21 October 2026 rerun Pier_Fixed.XML selected under D-073 (SHA-256 {OLD_XML}; pipe pile material Fy 45 ksi in place of the 60 ksi of the 19 October export {OLD_OLD_XML}, now archived; nodal loads, geometry, pile section and soil unchanged), held in project_current/fbmp/.',
            f'and, for the pier, the 22 October 2026 rerun Pier_Fixed.XML selected under D-077 (SHA-256 {NEW_XML}; {WALL}; the 21 October export {OLD_XML}, D-073, which had introduced the 45 ksi pipe pile material, and the 19 October export {OLD_OLD_XML}, D-049, are archived), held in project_current/fbmp/.',
            'FoundationModeling current models')
text = swap(text,
            'the pier cap and pile calculations (CapDesignPier, PileDesignPier) were rerun on the 21 October export (D-073) with no change to any force envelope, demand, ratio or status.',
            'the pier cap and pile calculations (CapDesignPier, PileDesignPier) were rerun on the 21 October export (D-073) with no change to any force envelope, demand, ratio or status, and again on the 22 October export (D-077), where nine cap force inputs moved with no status change and the pile demands follow the corrected wall members.',
            'FoundationModeling rerun sentence')
E.fromstring(text.encode('utf-8'))
out['report:FoundationModeling'] = text.encode('utf-8')
record['FoundationModeling'] = {'source': 'base.bpad + heading and current-model paragraph'}

# --- BridgeGeometry_2Beam ---
text = base.part('report:BridgeGeometry_2Beam').decode('utf-8')
text = swap(text,
            'and the 21 October 2026 pier model (D-073: Pier_Fixed.XML, pipe pile material 45 ksi; loads and geometry as the 19 October model), which model the 36-in caps;',
            'and the 22 October 2026 pier model (D-077: Pier_Fixed.XML, pier wall members ending at the soil surface; pipe pile material 45 ksi since D-073; loads and geometry as the 19 October model), which model the 36-in caps;',
            'BridgeGeometry analysis exports')
text = swap(text,
            'Pier Cap Design 10-21.html (D-073, rerun on the 21 October 2026 fixed-run Pier_Fixed.XML with every value unchanged from Pier Cap Design 10-19.html, D-051, which was built on the 19 October export, D-049; previously Pier Cap Design 10-9.html) confirms',
            'Pier Cap Design 10-22.html (D-077, rerun on the 22 October 2026 fixed-run Pier_Fixed.XML with nine force inputs moved and no status changed from Pier Cap Design 10-21.html, D-073, itself unchanged in value from Pier Cap Design 10-19.html, D-051, built on the 19 October export, D-049; previously Pier Cap Design 10-9.html) confirms',
            'BridgeGeometry pier report')
E.fromstring(text.encode('utf-8'))
out['report:BridgeGeometry_2Beam'] = text.encode('utf-8')
record['BridgeGeometry_2Beam'] = {'source': 'base.bpad + two sentences (pier export, pier cap report); no value, cache or figure changed'}

# --- PedBridge ---
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
REVISION_NOTE = (f'Revision: 22 October 2026, pier modules follow the 22 October FBMP rerun (T036, D-077): the user’s rerun Pier_Fixed.XML (SHA-256 {NEW_XML[:12]}…) '
                 f'corrects the pier wall extra members, which had followed the soil elevation changes: {WALL}. C010 Pier Cap Design and C013 Pier Pile '
                 'Design are replaced by their regenerated journal editions (the cap edition from the 10-22 report with nine force inputs moved and no '
                 f'status change; the pile edition with the demands of the new export, structural D/C {PILE_DC:.3f}, {PILE_PENDING} pending items). FBMP Entry - Pier, '
                 'Foundations and FBMP Modeling and Bridge Geometry record the new export identity. End-bent modules unchanged. Native recalculation, '
                 'appearance and engineering reviews not performed.')
m = re.search(r'^( {8}<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: )', text, re.M)
assert m, 'PedBridge revision paragraph anchor'
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
assert REVISION_NOTE[:70] not in text
text = text[:m.start()] + note + nl + text[m.start():]
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + revision note'}

# --- DecisionLog ---
text = base.part('report:DecisionLog').decode('utf-8')
nl = nl_of(text)
DECISION_SECTION = 'PierFbmpRerun20261022'
DECISION_HEADING = '2026-10-22 - Pier FBMP rerun with the pier wall members ending at the soil surface; pier cap and pile calculations rerun (T036)'
DECISION = ('User direction of 22 October 2026 (a rerun of the pier FBMP model after the pier wall extra members were found to have followed the soil '
            f'elevation changes; project decision D-077): the rerun Pier_Fixed.XML (SHA-256 {NEW_XML}) replaces the 21 October export (D-073) as the '
            f'current pier analysis source. Compared element by element, {WALL}. Against the CAD pier wall of D-075 (219 x 36 in from EL 24.53 to the '
            'cap bottom EL 40.76, 133.4 kip) the model wall is 6.1 kip lighter, its top 6.8 in below the cap bottom and its bottom 18.3 in above the '
            'CAD wall bottom. The pier cap case was rerun from the export (scripts/apply_fbmp_to_cap_case.py): nine force inputs moved (largest Mu_B '
            '365.84 to 361.01 kip-ft and Vu 218.96 to 220.46 kip), 62 check ratios changed, no status changed; C010 is its regenerated journal edition. '
            f'The pier pile case was rerun (scripts/export_project_pile_reports.py): structural D/C {PILE_DC:.3f}, governing below the wall at pile '
            f'element 11, {PILE_PENDING} pending items; C013 is its regenerated journal edition; the End Bent pile cases were re-exported with identical '
            'checks for package currency. FBMP Entry - Pier, Foundations and FBMP Modeling and Bridge Geometry name the new export. End-bent exports, '
            'cases, reports and modules are unchanged. FBMP was rerun by the user, not here; native recalculation, appearance and engineering reviews '
            'not performed.')
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

# every edited prose module keeps its definitions, caches and canvases
for key, blob in out.items():
    if key in ('report:CapDesignPier', 'report:PileDesignPier'):
        continue
    new, old = E.fromstring(blob), base.elements[key]
    assert dyn(old) == dyn(new) and caches(old) == caches(new) and cel(old) == cel(new), f'{key}: a definition, cache or canvas changed'

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T036', 'base_sha256': base.sha256, 'decision': 'D-077', 'pier_xml_sha256': NEW_XML,
                                                    'pier_cap_report_sha256': NEW_REPORT, 'pier_pile_report_sha256': PILE_REPORT,
                                                    'cap_inputs_changed': CAP_CHANGED, 'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T036', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
