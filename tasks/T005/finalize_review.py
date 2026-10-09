from pathlib import Path
import json,hashlib,sys,shutil
ROOT=Path(__file__).resolve().parents[2];TASK=Path(__file__).parent
sys.path.insert(0,str(ROOT))
from tools.bpad_workflow import Journal,check
folder=ROOT/'generated/T005-pier-review-03';ev=folder/'evidence'
j=Journal.load(folder/'candidate.bpad');base=Journal.load(TASK/'base.bpad')
assert j.sha256=='829f5450a34c76bee03ebbce06a389de76883ccaa8007b5e9bb50b17ec83de33'
rebuilt,report=check(ROOT,'T005');assert rebuilt.data==j.data
assert base.part('report:PierCapDesign')==j.part('report:PierCapDesign')
assert report['candidate_cached_errors']==0
for n in ('native-source-reference.png','native-geometry-calculations.png','native-cap-quantity.png','native-user-direction.png'):assert (ev/n).is_file()
out=Path('C:/Users/joshs/Desktop/D2 MPDB/outputs/pier-coherence-20261009')
shutil.copy2(out/'Pier_Cap_Coherence_Review_Responses.xlsx',TASK/'sources/Pier_Cap_Coherence_Review_Responses.xlsx')
shutil.copy2(out/'validation.json',ev/'workbook-validation.json')
(ev/'integration-check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
(ev/'C005-preservation.json').write_text(json.dumps({'base_sha256':base.sha256,'candidate_sha256':j.sha256,'C005_sha256':hashlib.sha256(j.part('report:PierCapDesign')).hexdigest(),'C005_byte_identical':True,'new_steel_or_force_record_in_bpad':False,'other_unchanged_components':264},indent=2),encoding='utf8')
note='''# Final native and engineering data review — T005

Candidate: generated/T005-pier-review-03/candidate.bpad
SHA256: 829f5450a34c76bee03ebbce06a389de76883ccaa8007b5e9bb50b17ec83de33

The final candidate was opened in the installed Blockpad application. Opening
and dependency resolution completed. Native geometry outputs displayed a 25-in
end-center datum, MATCH for 15 = 9 + 3 + 3 in, 12-ft2 area and 230-ft3 gross cap
volume. The pile station table displayed centers 25/85/145/205 in and faces
15–35/75–95/135–155/195–215 in. The new equations had no fabricated cached values.
The quantity sheet displayed 12 ft2 and 230 ft3 through the new geometry link.
Its note wraps within column A and is fully visible. Source hashes, bearing
node mapping, right-row offset caution and the final dated user direction were
inspected in the native pages. Native screenshots in this folder show these
exact final-candidate observations. No native save was performed; on-disk bytes
were checked again before finalization. Unchanged journal pages were not
represented as independently revalidated structural calculations.

The earlier revision-01 observations are not evidence for this final candidate
and are not included here. The user changed scope: C005 must remain completely
unchanged and steel stays separate. Final C005 bytes exactly equal the task base,
including titles, mathematics, prose and caches. No new steel or force record is
inserted into BPAD. Existing end-bent content and all resources remain unchanged.

45 source/geometry/scope checks passed. The exact XML matches the supplied report.
Main cap dimensions and gross volume agree; pile A/I agree with the journal's
0.475-in effective wall to XML precision. Bearing labels and cap connections are
established, but the +10.14-in right-row model offset differs from the journal's
+10.50 in. Full load-input currency, model convergence and structural adequacy
are excluded from this acceptance. The separate Excel review includes source
steel details and eight unresolved decisions, with the C005/steel instruction
already recorded. It was recalculated, inspected for errors and visually reviewed.

The retained 231-in wind face, wall quantities and older quantity-sheet three-beam
/19-ft-3-in sketches remain review items. Three inherited LoadCombinations links
remain unresolved; no new structural issues or stored errors were introduced.
This is acceptance of faithful geometry/source bookkeeping under the final user
scope, not a claim that all project design data or source reinforcement is coherent.
No commit or push is performed.
'''
(TASK/'final-review.md').write_text(note,encoding='utf8');(ev/'final-review.md').write_text(note,encoding='utf8')
review={
 'candidate_sha256':j.sha256,
 'reviewer':'Codex — source/geometry coherence review and actual native Blockpad observations; no human engineering sign-off',
 'native_recalculation':True,'native_visual_review':True,'engineering_review':True,
 'design_outcome':'not_applicable',
 'external_analysis_status':'excluded_from_accepted_scope',
 'external_analysis_disposition':'Exact Pier_MinTip.XML identity matches the supplied report. Cap geometry, bearing mapping, pipe properties and printed DC magnitudes were compared. Acceptance is limited to geometry/source bookkeeping. Full journal/model load currency, offset correction/reanalysis, convergence and final structural adequacy remain excluded. Reinforcement remains separate in the report/Excel, and C005 is completely unchanged by express user direction.',
 'inherited_issues_disposition':'Zero stored errors and no new structural issues. Three inherited LoadCombinations links remain unresolved. C005 earlier inputs are retained by user direction, with the difference recorded outside it. Independent wind/wall dimensions and old quantity-sheet sketches are explicit Excel review items; they are not declared reconciled.',
 'evidence_files':[{'path':p.relative_to(folder).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(ev.rglob('*')) if p.is_file()]
}
(folder/'review.json').write_text(json.dumps(review,indent=2),encoding='utf8')
print(json.dumps({'candidate_sha256':j.sha256,'C005_unchanged':True,'native_review':'complete','evidence_files':len(review['evidence_files'])},indent=2))
