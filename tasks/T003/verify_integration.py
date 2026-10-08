"""Verify final integration bytes and evidence relationships; no native claim."""
from pathlib import Path
import hashlib, json, sys, shutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal, external_refs, structural_issues

folder = ROOT/'generated/T003-end-bent-review-03'
prior_folder = ROOT/'generated/T003-end-bent-review-02'
candidate = Journal.load(folder/'candidate.bpad')
prior = Journal.load(prior_folder/'candidate.bpad')
base = Journal.load(ROOT/'tasks/T002/base.bpad')
authored = Journal.load(ROOT/'tasks/T002/working.bpad')
evidence = folder/'evidence'
evidence.mkdir(exist_ok=True)
expected = 'a45256fbdd3c27444bb3b93ffc327353efcfdc366a126aff35f809a853635d72'
assert candidate.sha256 == expected
assert prior.changes(candidate) == ['spreadsheet:QauntitiesBridge']
assert base.order == candidate.order and base.shell == candidate.shell
changed = base.changes(authored)
assert len(changed) == 7
assert all(authored.part(k) == candidate.part(k) for k in changed)
unchanged = [k for k in base.order if base.part(k) == candidate.part(k)]
assert len(unchanged) == 237
resources = [k for k in base.order if k.startswith('resource:')]
assert all(base.part(k) == candidate.part(k) for k in resources)
assert structural_issues(candidate) == structural_issues(base)
refs = external_refs(candidate, folder)
assert len(refs) == 31
for ref in refs:
    assert ref['exists'] and not ref['absolute']
    destination = ROOT/'journal'/ref['path'].replace('\\','/')
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == ref['sha256']
source = ROOT/'tasks/T002/sources/End bent 1 Cap Design Report_10-8.html'
assert hashlib.sha256(source.read_bytes()).hexdigest() == '42120857965352febea29e4a672b2ba93f45199430360a89f8e1e529d2df50ef'
checks = json.loads((ROOT/'tasks/T002/coherence_checks.json').read_text(encoding='utf8'))
assert checks['candidate_sha256'] == authored.sha256
assert len(checks['checks']) == 33 and all(x['status'] == 'PASS' for x in checks['checks'])
assert checks['inherited_error_count'] == 110
rows = candidate.elements['spreadsheet:QauntitiesBridge'].findall('row')
assert 'PROVISIONAL' in ''.join(rows[124].itertext())
assert 'legacy cheek-wall geometry' in ''.join(rows[124].itertext())

# Earlier native screens are explicitly attributed to revision 02. All their
# reviewed report components are byte-identical in the final revision 03.
old_screens = evidence/'review-02-unchanged-reports'
old_screens.mkdir(exist_ok=True)
for p in prior_folder.joinpath('evidence').glob('native-*.jpg'):
    shutil.copy2(p, old_screens/p.name)
shutil.copy2(ROOT/'tasks/T002/coherence_checks.json', evidence/'independent_checks.json')
shutil.copy2(ROOT/'tasks/T003/coherence-review.md', evidence/'coherence-review.md')
payload = {
    'candidate_sha256':candidate.sha256,
    'authoring_sha256':authored.sha256,
    'prior_native_review_sha256':prior.sha256,
    'changes_since_prior_native_review':['spreadsheet:QauntitiesBridge'],
    'quantity_delta':'Provisional cheek-wall note in empty row 125; D104 display-format attribute; formulas unchanged.',
    't002_module_bytes_identical':changed,
    'unchanged_baseline_components':len(unchanged),
    'embedded_resources_preserved':len(resources),
    'portable_reference_hashes_verified':refs,
    'native_report_component_hashes':{k:candidate.hashes[k] for k in changed if k.startswith('report:')},
    'independent_checks_passed':33,
    'inherited_errors_preserved':110,
    'inherited_link_issues_preserved':dict(structural_issues(candidate)),
}
(evidence/'integration-check.json').write_text(json.dumps(payload,indent=2),encoding='utf8')
print(json.dumps({'candidate_sha256':candidate.sha256,'independent_checks':33,'portable_references':31,'unchanged_components':237,'review_delta':'quantity display and provisional note only'}))
