"""Package completed native observations and scoped engineering review."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[2];TASK=Path(__file__).parent
sys.path.insert(0,str(ROOT))
from tools.bpad_workflow import Journal,check
folder=ROOT/'generated/T004-response-review-02';evidence=folder/'evidence'
j=Journal.load(folder/'candidate.bpad')
assert j.sha256=='99e0daa0d7b80581d780152aabc71b85928f8978b768a5fa01173ef9c6ed29c0'
rebuilt,report=check(ROOT,'T004');assert rebuilt.data==j.data
assert report['candidate_cached_errors']==0
assert (evidence/'final-native-application-table.jpg').is_file()
assert (evidence/'final-native-entry-weights.jpg').is_file()
for name in ['response-review.md','native-review.md']:
    shutil.copy2(TASK/name,evidence/name)
(evidence/'integration-check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
review={
 'candidate_sha256':j.sha256,
 'reviewer':'Codex — source/data-coherence review with actual native Blockpad observations; no human engineering sign-off',
 'native_recalculation':True,'native_visual_review':True,'engineering_review':True,
 'design_outcome':'not_applicable',
 'external_analysis_status':'excluded_from_accepted_scope',
 'external_analysis_disposition':'The user confirms that the supplied report contains the latest FBMP model and directs both end bents to follow controlling End Bent 1. The journal records that current source basis and its exact report/XML hashes; loaded nodes are 15/34. Acceptance covers faithful data reconciliation and pedestal geometry/quantity bookkeeping. Independent raw-input verification, FBMP rerun, separate End Bent 2 action verification, revised hook design, D-region/anchorage and final structural adequacy are outside this task. Source check counts remain historical; no rerun result is invented.',
 'inherited_issues_disposition':'Removed the five explicitly retired modules and their links; all 110 inherited stored errors were confined to those removed modules. No new errors or structural issues. The three inherited LoadCombinations links remain unresolved and are expressly outside this bounded response update. Wall quantities are deferred by the user; remaining design checks retain the dispositions in the current record.',
 'evidence_files':[{'path':p.relative_to(folder).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(evidence.rglob('*')) if p.is_file()]
}
(folder/'review.json').write_text(json.dumps(review,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'candidate_sha256':j.sha256,'evidence_files':len(review['evidence_files']),'native_review':'completed','engineering_scope':'directed source/data reconciliation'},indent=2))
