"""Record integrity checks without claiming native or engineering review."""
from pathlib import Path
import json
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal, digest, promotion_policy, write_json

folder = ROOT / 'generated/T010-ramp-slab-decision-final'
base = Journal.load(TASK / 'base.bpad')
candidate = Journal.load(folder / 'candidate.bpad')
key = 'report:DecisionLog'
assert base.changes(candidate) == [key]
assert base.shell == candidate.shell
assert all(base.part(k) == candidate.part(k) for k in base.order if k != key)
fragment = candidate.part(key)
marker = b'        <section name="RampSlabBackwallDecision20261016"'
assert fragment.count(marker) == 1
start = fragment.index(marker)
end = fragment.index(b'</section>\n', start) + len(b'</section>\n')
assert fragment[:start] + fragment[end:] == base.part(key)
entry = ET.fromstring(fragment[start:end])
assert entry.find('heading').text == '2026-10-16 - Ramp slab-to-backwall connection'
assert entry.find('paragraph').text == ('Per Matt, the ramp slab will not be tied to the backwall with dowels, '
    'due to concern about transferring bridge deflections to the MSE wall ramps.')
assert not any('formula' in element.attrib or element.tag == 'dynexp' for element in entry.iter())
report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
assert report['structural_delta'] == 'passed'
assert not report['candidate_structural_issues']
assert report['candidate_cached_errors'] == 0
policy = promotion_policy(ROOT)
assert policy['reviews_required'] is False
evidence = {
    'candidate_sha256': candidate.sha256,
    'base_sha256': base.sha256,
    'changed_components': [key],
    'preserved_components': len(base.order) - 1,
    'document_shell_preserved': True,
    'all_existing_decision_log_bytes_preserved': True,
    'new_entries': 1,
    'decision_date': '2026-10-16',
    'decision_text': entry.find('paragraph').text,
    'structural_delta': 'passed',
    'candidate_cached_errors': 0,
    'new_formulas': 0,
    'native_recalculation': False,
    'native_visual_review': False,
    'engineering_review': False,
    'policy': policy,
    'review_disposition': 'User made native and engineering reviews optional on 16 October 2026. Only the requested narrative decision is added; all numerical content is preserved.',
    'workflow_tests': '52 tests passed, including optional review promotion, reinstatement of required reviews, and preservation of integrity checks. Tests used a writable workspace temporary directory because the sandbox default temporary directory was inaccessible.'
}
write_json(folder / 'integrity-evidence.json', evidence)
shutil.copyfile(ROOT / 'generated/T010-workflow-tests.txt', folder / 'workflow-tests.txt')
review = json.loads((folder / 'review.json').read_text(encoding='utf-8'))
review.update({
    'reviewer': 'Codex - narrative and file-integrity checks only',
    'native_recalculation': False,
    'native_visual_review': False,
    'engineering_review': False,
    'design_outcome': 'not_applicable',
    'external_analysis_status': 'not_applicable',
    'external_analysis_disposition': 'Narrative record of the user-supplied decision only; no analysis inputs, outputs, formulas or geometry are changed or validated.',
    'inherited_issues_disposition': 'All 270 other components, all existing Decision Log bytes and the document shell are preserved. Structural check passed with zero stored errors; no new claim of engineering adequacy or native validation.',
    'evidence_files': [{'path': name, 'sha256': digest((folder / name).read_bytes())}
                       for name in ['integrity-evidence.json', 'workflow-tests.txt']]
})
write_json(folder / 'review.json', review)
print(json.dumps(evidence, indent=2))
