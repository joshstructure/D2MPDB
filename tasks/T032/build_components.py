"""T032: write the eight registered component files (rerunnable, byte-surgical).

* CapDesignPier and PileDesignPier: the regenerated journal editions (`cap_bpad/journal/CapDesignPier.xml`,
  `pile_bpad/journal/PileDesignPier.xml`), checked against their verification records (fragment hash, the D-073 export
  identity, live stamp / coherence gate) and against the base modules: every dynexp formula, cached result and canvas
  formula identical; only paragraph text differs (recorded).
* PileProperties, FBMPPier, FoundationModeling, BridgeGeometry_2Beam, PedBridge: exact-substring surgery on the
  paragraphs that name the pier export, its material or the pier reports (every anchor must occur exactly once; CRLF kept).
* PedBridge: one revision paragraph before the T028 note. DecisionLog: one section appended inside the report.
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
NEW_XML = '8be45bb889f5c955d0547ce6a538118bbce87600d40a65b094255e6b9b76e3b6'
OLD_XML = 'bb73e6ada6cf35ebb80b512cee315075807fc8ccab7878406d81ff381ae40fe7'
OLD_OLD_XML = 'a992aa331e11b4eb9bc426a3f811938a8f71b22b3300bae3431eb2931eaff9d8'
OLD_REPORT = 'e49d579c0186e7c2617828d236cb982adb92122345493a097e7c352df2f3a701'
OLD_OLD_REPORT = '7a9f48ce08bdc29f22a1b6717432dc363f0c2d8cec02ffbfc0a36bb7da39dee2'


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
assert register['PIER-XML']['sha256'] == NEW_XML and register['PIER-XML']['registered_on'] == '2026-10-21'
cap_receipt = json.loads((ROOT / 'project_current/coherence/evidence/2026-10-21-cap-rerun/source_receipt.json').read_text(encoding='utf-8'))
pile_receipt = json.loads((ROOT / 'project_current/coherence/evidence/2026-10-21-pile-reports/source_receipt.json').read_text(encoding='utf-8'))
NEW_REPORT = cap_receipt['run']['files']['report']['sha256']
assert register['PIER-REPORT']['sha256'] == NEW_REPORT and register['PIER-REPORT']['path'].endswith('Pier Cap Design 10-21.html')
assert cap_receipt['run']['inputs_changed'] == {} and cap_receipt['run']['check_changes'] == []
pile_run = pile_receipt['reports'][0]
assert pile_run['support'] == 'Pier' and pile_run['fbmp_export']['sha256'] == NEW_XML
PILE_REPORT = pile_run['files']['report']['sha256']
assert register['PILE-PIER-REPORT']['sha256'] == PILE_REPORT
PILE_PENDING = pile_run['check_register']['pending_items']
PILE_DC = pile_run['check_register']['strength_dc']

base = Journal.load(TASK / 'base.bpad')
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
assert set(mapping) == {'report:CapDesignPier', 'report:PileDesignPier', 'report:PileProperties', 'report:FBMPPier', 'report:FoundationModeling',
                        'report:BridgeGeometry_2Beam', 'report:PedBridge', 'report:DecisionLog'}, sorted(mapping)
out, record = {}, {}

dyn = lambda el: Counter(d.get('formula') for d in el.iter('dynexp'))
cel = lambda el: Counter(e.get('formula') for e in el.iter() if e.tag in ('c', 'planecontainer', 'lineardim', 'plot') and e.get('formula'))
caches = lambda el: Counter((d.get('formula'), (d.findtext('expresult') or '').strip()) for d in el.iter('dynexp'))
texts = lambda el: Counter(' '.join(''.join(p.itertext()).split()) for p in el.iter('paragraph'))


def adopt_edition(name, folder, verification, expect):
    """Copy a regenerated journal edition after checking it against its verification record and the base module."""
    data = strip_nl((folder / f'{name}.xml').read_bytes())
    assert sha(data) == verification['fragment_sha256'], f'{name}: fragment differs from its verification record; rebuild the edition'
    assert verification['fbmp_sha256'] == NEW_XML and verification['fbmp_file'] == 'Pier_Fixed.XML', name
    assert verification['status'] == '✓ All Checks Pass', (name, verification['status'])
    for key, value in expect.items():
        assert verification[key] == value, (name, key, verification[key], value)
    root, old = E.fromstring(data), base.elements[f'report:{name}']
    assert root.tag == 'report' and root.get('name') == name and root.get('title') == old.get('title'), (name, root.get('title'))
    assert dyn(old) == dyn(root), f'{name}: definitions differ'
    assert caches(old) == caches(root), f'{name}: cached results differ'
    assert cel(old) == cel(root), f'{name}: canvas or cell formulas differ'
    removed, added = list((texts(old) - texts(root)).elements()), list((texts(root) - texts(old)).elements())
    assert removed and added and len(removed) == len(added), (name, len(removed), len(added))
    assert all(OLD_XML[:12] in t or '10-19' in t or '16 pending' in t or '16 PENDING' in t or '0.29' in t for t in removed), (name, removed)
    assert not any(OLD_XML[:12] in t for t in added) and any(NEW_XML[:12] in t for t in added), (name, added)
    for el, text in bs.visible_text_elements(root):
        m = bs.SUBMISSION_FORBIDDEN.search(text)
        assert not m, f'{name}: working language {m.group(0)!r}: {text[:100]}'
    out[f'report:{name}'] = data
    record[name] = {'source': str(folder.relative_to(ROOT).as_posix()) + f'/{name}.xml', 'fragment_sha256': verification['fragment_sha256'],
                    'fbmp_sha256': verification['fbmp_sha256'], 'definitions_unchanged': sum(dyn(root).values()), 'caches_unchanged': True,
                    'canvases_unchanged': True, 'paragraphs_removed': removed, 'paragraphs_added': added}


cap_v = next(r for r in json.loads((ROOT / 'cap_bpad/journal/verification.json').read_text(encoding='utf-8'))['reports'] if r['report_name'] == 'CapDesignPier')
adopt_edition('CapDesignPier', ROOT / 'cap_bpad' / 'journal', cap_v, {'report_file': 'Pier Cap Design 10-21.html', 'literals_kept': []})
pile_v = next(r for r in json.loads((ROOT / 'pile_bpad/journal/verification.json').read_text(encoding='utf-8')) if r['report_name'] == 'PileDesignPier')
adopt_edition('PileDesignPier', ROOT / 'pile_bpad' / 'journal', pile_v, {'stamp': 'live', 'support': 'Pier'})
assert any(f'{PILE_PENDING} pending item' in t for t in record['PileDesignPier']['paragraphs_added']), record['PileDesignPier']['paragraphs_added']

# --- PileProperties ---
text = base.part('report:PileProperties').decode('utf-8')
text = swap(text,
            'The 19 October 2026 fixed-run pier model (Pier_Fixed.XML, D-049) uses a 20-in circular steel section with a 0.48-in shell, A = 29.14 in², I = 1389.26 in⁴, E = 29000 ksi and Fy = 60 ksi: to the model’s precision',
            'The 21 October 2026 fixed-run pier model (Pier_Fixed.XML, D-073; the 19 October model, D-049, differed only in its 60 ksi shell steel) uses a 20-in circular steel section with a 0.48-in shell, A = 29.14 in², I = 1389.26 in⁴, E = 29000 ksi and Fy = 45 ksi: to the model’s precision',
            'PileProperties model paragraph')
text = swap(text,
            'PileDesignPier (D-054) reads the model section (D_out 20 in, t_wall 0.48 in) with no further corrosion allowance (t_corr 0; LRFD 10.7.5 and the FDOT environment classification are pending) and Fy = 45 ksi (Specification 962, ASTM A252 Grade 3) against 60 ksi in the FBMP model. The pipe steel grade and corrosion allowance are pending reconciliation; the sacrificial-thickness basis of this module is not changed here.',
            'PileDesignPier (D-054; rerun 21 October 2026, D-073) reads the model section (D_out 20 in, t_wall 0.48 in) with no further corrosion allowance (t_corr 0; LRFD 10.7.5 and the FDOT environment classification are pending) and Fy = 45 ksi (Specification 962, ASTM A252 Grade 3), the Fy of the 21 October FBMP model: the Fy reconciliation is closed by the registered export (source-backed steel_grade prerequisite), while the grade selection and the corrosion allowance remain design inputs. The sacrificial-thickness basis of this module is not changed here.',
            'PileProperties reconciliation paragraph')
E.fromstring(text.encode('utf-8'))
out['report:PileProperties'] = text.encode('utf-8')
record['PileProperties'] = {'source': 'base.bpad + two paragraphs (45 ksi model material; Fy reconciliation closed)'}

# --- FBMPPier ---
text = base.part('report:FBMPPier').decode('utf-8')
text = swap(text,
            'Geometry source: Pier Cap Design 10-19.html (D-051; supersedes Pier Cap Design 10-9.html generated 2026-10-09T22:19:21+00:00); case Pier_Fixed — XML analysis. Pile design: PileDesignPier (D-054).',
            'Geometry source: Pier Cap Design 10-21.html (D-073: the 10-19 report, D-051, rerun on the 21 October 2026 export with every force envelope, ratio and status unchanged; supersedes Pier Cap Design 10-9.html generated 2026-10-09T22:19:21+00:00); case Pier_Fixed — XML analysis. Pile design: PileDesignPier (D-054; rerun D-073).',
            'FBMPPier geometry source')
text = swap(text,
            f'Report SHA-256: {OLD_REPORT} (Pier Cap Design 10-19.html; the 10-9 report was {OLD_OLD_REPORT})',
            f'Report SHA-256: {NEW_REPORT} (Pier Cap Design 10-21.html; the 10-19 report was {OLD_REPORT} and the 10-9 report {OLD_OLD_REPORT})',
            'FBMPPier report hash')
text = swap(text,
            f'Report-identified Pier_Fixed.XML SHA-256: {OLD_XML} (D-049, 19 October 2026, held in project_current/fbmp/pier/; the 10-9 report identified {OLD_OLD_XML})',
            f'Report-identified Pier_Fixed.XML SHA-256: {NEW_XML} (D-073, 21 October 2026, held in project_current/fbmp/pier/; the 10-19 report identified {OLD_XML}, D-049, now archived under fbmp/pier/archive/2026-10-19/, and the 10-9 report {OLD_OLD_XML})',
            'FBMPPier XML hash')
text = swap(text,
            'the +10.14-in value belonged only to the superseded Pier_MinTip.XML. Full input currency of the model against the current journal loads is not asserted.</paragraph>',
            'the +10.14-in value belonged only to the superseded Pier_MinTip.XML. Full input currency of the model against the current journal loads is not asserted. '
            '21 October 2026 (D-073): the user’s rerun Pier_Fixed.XML changes only the pipe pile material (Fy 45 ksi in place of 60 ksi); the pier cap case rerun from it keeps every force envelope, ratio and status, and the pier pile demands are unchanged.</paragraph>',
            'FBMPPier resolved note')
E.fromstring(text.encode('utf-8'))
out['report:FBMPPier'] = text.encode('utf-8')
record['FBMPPier'] = {'source': 'base.bpad + geometry source, report and XML identities, resolved note'}

# --- FoundationModeling ---
text = base.part('report:FoundationModeling').decode('utf-8')
text = swap(text, '<heading level="1" keepwithnext="True">Current model sources — 19 October 2026</heading>',
            '<heading level="1" keepwithnext="True">Current model sources — 19 and 21 October 2026</heading>', 'FoundationModeling heading')
text = swap(text,
            f'and Pier_Fixed.XML (SHA-256 {OLD_XML}), held in project_current/fbmp/. The 19 October cap reports and cases (D-051: CapDesignEndBentOne, CapDesignEndBentTwo, CapDesignPier) and pile reports (D-054: PileDesignEndBentOne, PileDesignEndBentTwo, PileDesignPier) read these exports.',
            f'and, for the pier, the 21 October 2026 rerun Pier_Fixed.XML selected under D-073 (SHA-256 {NEW_XML}; pipe pile material Fy 45 ksi in place of the 60 ksi of the 19 October export {OLD_XML}, now archived; nodal loads, geometry, pile section and soil unchanged), held in project_current/fbmp/. '
            'The 19 October end-bent cap reports and cases (D-051: CapDesignEndBentOne, CapDesignEndBentTwo) and pile reports (D-054: PileDesignEndBentOne, PileDesignEndBentTwo) read the end-bent exports; the pier cap and pile calculations (CapDesignPier, PileDesignPier) were rerun on the 21 October export (D-073) with no change to any force envelope, demand, ratio or status.',
            'FoundationModeling current models')
E.fromstring(text.encode('utf-8'))
out['report:FoundationModeling'] = text.encode('utf-8')
record['FoundationModeling'] = {'source': 'base.bpad + heading and current-model paragraph'}

# --- BridgeGeometry_2Beam ---
text = base.part('report:BridgeGeometry_2Beam').decode('utf-8')
text = swap(text,
            'The current analysis force exports are the 19 October 2026 fixed-run FB-MultiPier models (D-049: End Bent 1_Fixed.XML, End Bent 2_Fixed.XML, Pier_Fixed.XML), which model the 36-in caps;',
            'The current analysis force exports are the 19 October 2026 fixed-run FB-MultiPier end-bent models (D-049: End Bent 1_Fixed.XML, End Bent 2_Fixed.XML) and the 21 October 2026 pier model (D-073: Pier_Fixed.XML, pipe pile material 45 ksi; loads and geometry as the 19 October model), which model the 36-in caps;',
            'BridgeGeometry analysis exports')
text = swap(text,
            'Pier Cap Design 10-19.html (D-051, built on the 19 October 2026 fixed-run Pier_Fixed.XML, D-049; previously Pier Cap Design 10-9.html) confirms',
            'Pier Cap Design 10-21.html (D-073, rerun on the 21 October 2026 fixed-run Pier_Fixed.XML with every value unchanged from Pier Cap Design 10-19.html, D-051, which was built on the 19 October export, D-049; previously Pier Cap Design 10-9.html) confirms',
            'BridgeGeometry pier report')
E.fromstring(text.encode('utf-8'))
out['report:BridgeGeometry_2Beam'] = text.encode('utf-8')
record['BridgeGeometry_2Beam'] = {'source': 'base.bpad + two sentences (pier export, pier cap report); no value, cache or figure changed'}

# --- PedBridge ---
text = base.part('report:PedBridge').decode('utf-8')
nl = nl_of(text)
text = swap(text,
            'Analysis: the 19 October 2026 fixed-run FB-MultiPier exports (D-049). Design records: the 10-19 cap design reports (D-051), pile design reports (D-054)',
            'Analysis: the 19 October 2026 fixed-run FB-MultiPier end-bent exports (D-049) and the 21 October 2026 pier export (D-073). Design records: the 10-19 end-bent and 10-21 pier cap design reports (D-051, D-073), pile design reports (D-054, D-073)',
            'PedBridge summary')
text = swap(text, '>Current model sources (D-049 exports)</link>', '>Current model sources (D-049 and D-073 exports)</link>', 'PedBridge sources link')
REVISION_NOTE = (f'Revision: 21 October 2026, pier modules follow the 21 October FBMP rerun (T032, D-073): the user’s rerun Pier_Fixed.XML (SHA-256 {NEW_XML[:12]}…) changes only '
                 'the pipe pile material, ASTM A252 Grade 3 at Fy 45 ksi in place of 60 ksi; nodal loads, geometry, pile section, soil and load combinations are those of the 19 October '
                 'export. C010 Pier Cap Design and C013 Pier Pile Design are replaced by their regenerated journal editions (the cap edition from the 10-21 report with every force '
                 f'envelope, ratio and status unchanged; the pile edition with every demand and resistance unchanged, structural D/C {PILE_DC:.3f}, and the steel-grade prerequisite '
                 f'source-backed by the export, {PILE_PENDING} pending items in place of 16). Pile Section Properties, FBMP Entry - Pier, Foundations and FBMP Modeling and Bridge Geometry '
                 'record the new export identity and the 45 ksi material. End-bent modules unchanged. Native recalculation, appearance and engineering reviews not performed; '
                 'no existing definition or cached value changed.')
anchor = ' ' * 8 + '<paragraph fontfamily="Times New Roman" fontsize="10" spacingafter="6" leftindent="0">Revision: 21 October 2026, C017 Pier Wall, Annular Pile Rings added (T028):'
once(text, anchor, 'PedBridge T028 revision paragraph')
note = ' ' * 8 + f'<paragraph fontfamily="{TNR}" fontsize="10" spacingafter="6" leftindent="0">{REVISION_NOTE}</paragraph>'
text = text.replace(anchor, note + nl + anchor)
E.fromstring(text.encode('utf-8'))
out['report:PedBridge'] = text.encode('utf-8')
record['PedBridge'] = {'source': 'base.bpad + summary sentence, sources link text, revision note'}

# --- DecisionLog ---
text = base.part('report:DecisionLog').decode('utf-8')
nl = nl_of(text)
DECISION_SECTION = 'PierFbmpRerun20261021'
DECISION_HEADING = '2026-10-21 - Pier FBMP rerun with the 45 ksi pile material; pier cap and pile calculations rerun (T032)'
DECISION = ('User direction of 21 October 2026 (a new FBMP run of the pier; update the whole project flow with it; project decision D-073): the rerun Pier_Fixed.XML '
            f'(SHA-256 {NEW_XML}) replaces the 19 October export (D-049) as the current pier analysis source. Compared element by element, the only model change is the pipe pile '
            'material, ASTM A252 Grade 3 at Fy 45 ksi in place of 60 ksi (FY_SHELL and its stress-strain curve); nodal loads, geometry, pile section, soil and the four load combinations '
            'are identical; the cap member forces differ only by solver noise below 1e-7 kip; the export’s own pile failure ratios and interaction diagram follow the 45 ksi material. '
            'The pier cap case was rerun from the export (scripts/apply_fbmp_to_cap_case.py): every force envelope, check ratio and status unchanged, analysis identity refreshed; '
            f'C010 is its regenerated journal edition. The pier pile case was rerun (scripts/export_project_pile_reports.py): demands unchanged, structural D/C {PILE_DC:.3f}; the pile '
            'package records the agreement between the export’s pile material Fy and the design Fy as source-backed evidence for the steel-grade prerequisite (withdrawn if Fy is edited; '
            f'the grade and the corrosion allowance remain design inputs), so {PILE_PENDING} pending items remain in place of 16; C013 is its regenerated journal edition. Pile Section '
            'Properties, FBMP Entry - Pier, Foundations and FBMP Modeling and Bridge Geometry name the new export and material. End-bent exports, cases, reports and modules are '
            'unchanged. FBMP was rerun by the user, not here; native recalculation, appearance and engineering reviews not performed; no existing definition or cached value changed.')
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

# every edited module keeps its definitions, caches and canvases
for key, blob in out.items():
    if key in ('report:CapDesignPier', 'report:PileDesignPier'):
        continue
    new, old = E.fromstring(blob), base.elements[key]
    assert dyn(old) == dyn(new) and caches(old) == caches(new) and cel(old) == cel(new), f'{key}: a definition, cache or canvas changed'

components = TASK / 'components'
for key, blob in out.items():
    (components / mapping[key]).write_bytes(blob)
(TASK / 'verification.json').write_text(json.dumps({'task': 'T032', 'base_sha256': base.sha256, 'decision': 'D-073', 'pier_xml_sha256': NEW_XML,
                                                    'pier_cap_report_sha256': NEW_REPORT, 'pier_pile_report_sha256': PILE_REPORT,
                                                    'components': record, 'status': 'PASS',
                                                    'reviews': {'native_recalculation': False, 'native_visual_review': False, 'engineering_review': False}},
                                                   indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'task': 'T032', 'components': {k: {'file': mapping[k], 'bytes': len(v), 'sha256': sha(v)[:12]} for k, v in sorted(out.items())}}, indent=1))
