"""Append the authorized narrative decision without reserializing existing XML."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal

base = Journal.load(TASK / 'base.bpad')
assert base.sha256 == '4b1770533d7b91cfb1efbcd96b0eb2c3a73328b90f88b2b50bca15388f07cd82'
key = 'report:DecisionLog'
original = base.part(key)
assert b'RampSlabBackwallDecision20261016' not in original
assert original.count(b'</report>') == 1
entry = b'''        <section name="RampSlabBackwallDecision20261016" capture="False" hide="false">
            <heading level="1" keepwithnext="True">2026-10-16 - Ramp slab-to-backwall connection</heading>
            <paragraph fontfamily="Times New Roman" fontsize="11" leftindent="0" spacingafter="7">Per Matt, the ramp slab will not be tied to the backwall with dowels, due to concern about transferring bridge deflections to the MSE wall ramps.</paragraph>
        </section>
'''
# Insert before the closing report indentation; all original bytes remain intact.
at = original.rfind(b'</report>')
line_start = original.rfind(b'\n', 0, at) + 1
assert not original[line_start:at].strip()
revised = original[:line_start] + entry + original[line_start:]
assert revised.replace(entry, b'', 1) == original
working = Journal(base.replace({key: revised}))
assert base.changes(working) == [key]
assert working.shell == base.shell
assert all(working.part(k) == base.part(k) for k in base.order if k != key)
assert b'formula=' not in entry and b'<dynexp' not in entry
(TASK / 'working.bpad').write_bytes(working.data)
mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8'))
(TASK / 'components' / mapping[key]).write_bytes(revised)
submission = {
    'summary': 'Record the 16 October 2026 ramp slab/backwall dowel decision, per Matt.',
    'published_outputs': ['One dated narrative entry in Decision Log.'],
    'assumptions_and_conventions': ['2026-10-16, America/New_York; attribution and rationale supplied by the user.'],
    'downstream_impact': ['Decision informs future ramp/backwall detailing; no calculation or geometry changes in this task.'],
    'external_analysis': 'Not applicable to this narrative record; all analyses and numerical assumptions remain unchanged.',
    'checks_performed': ['Date, decision, rationale and attribution checked against the user request.', 'All original Decision Log bytes preserved; one section appended.', '270 other components and document shell are byte-identical.', 'No formulas, resources, caches or links added or changed.'],
    'open_items': [],
    'reviews_not_performed': ['Native recalculation, appearance review and engineering review were not performed; the user made these optional on 16 October 2026.']
}
(TASK / 'submission.json').write_text(json.dumps(submission, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'changed': base.changes(working), 'preserved_components': len(base.order)-1, 'working_sha256': working.sha256}, indent=2))
