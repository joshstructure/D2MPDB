from pathlib import Path
import sys,json,hashlib,shutil
R=Path(__file__).resolve().parents[2];T=Path(__file__).parent;sys.path.insert(0,str(R))
from tools.bpad_workflow import Journal,check
folder=R/'generated/T006-pier-responses-02';ev=folder/'evidence';prior=R/'generated/T006-pier-responses-01'
j=Journal.load(folder/'candidate.bpad');old=Journal.load(prior/'candidate.bpad');base=Journal.load(T/'base.bpad')
assert j.sha256=='8902a6a2faa284f371518ec5f99b9979b480a2f940de007318a643f724d43351'
rebuilt,report=check(R,'T006');assert rebuilt.data==j.data
assert j.part('report:PierCapDesign')==base.part('report:PierCapDesign')
assert set(old.changes(j))=={'report:LoadCombinations','spreadsheet:QauntitiesBridge'}
# The revision changes only two prose labels. Numerical review views came from
# identical native components and are identified honestly by their prior revision.
bindings={}
for name,component in [('native-wind-geometry.png','report:BridgeGeometry_2Beam'),('native-wind-handoff.png','report:FBMPPier')]:
 assert old.part(component)==j.part(component)
 dest=ev/('revision01-'+name);shutil.copy2(prior/'evidence'/name,dest)
 bindings[dest.name]={'observed_candidate_sha256':old.sha256,'final_candidate_sha256':j.sha256,'component':component,'component_sha256':hashlib.sha256(j.part(component)).hexdigest(),'component_and_all_numerical_inputs_identical':True}
for name in ['native-index-final.png','native-reference-final.png','native-quantity-final.png','native-decisions-final.png','native-foundation-final.png','native-source-final.png']:assert (ev/name).is_file()
for name in ['source-checks.json','change-log.json','response-disposition.json']:shutil.copy2(T/name,ev/name)
(ev/'integration-check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
(ev/'native-view-bindings.json').write_text(json.dumps(bindings,indent=2),encoding='utf8')
note='''# T006 final review — pier responses

Final candidate: generated/T006-pier-responses-02/candidate.bpad
SHA256: 8902a6a2faa284f371518ec5f99b9979b480a2f940de007318a643f724d43351

The final candidate was opened in installed Blockpad and its native opening /
dependency calculation completed. The final index, current source page, foundation
source note, dated decision entry, load-combination reference layout and cap
quantity annotation were inspected in the application. The final quantity sheet
displayed 12 ft2 and 230 ft3; its compact historical note is fully visible.
The corrected guide link label fits alongside its unchanged embedded excerpt.
No native save or content edit was performed. On-disk candidate bytes remained
unchanged throughout review.

Revision 01 native geometry displayed width 230 in and projected area 348.965 ft2;
its downstream pier table displayed longitudinal face-normal bounds 20.933 kip
(Strength III) and 5.953 kip (Service I). These values match independent 230/231
scaling of the former width/area/force chain. The geometry, wind and FBMP components
and every numerical input are byte-identical in the final candidate. Only the
quantity note and one guide-link label were shortened between revisions; both
final versions were separately viewed. Revision-01 numeric screenshots are
explicitly named and tied to matching final component hashes in the evidence
manifest, rather than misrepresented as final-revision captures.

25 source, geometry, link, formula-interface and preservation checks passed.
There are zero stored errors and zero detected structural issues/broken links.
The full nine-component update preserves the other 261 components byte-for-byte,
including all C005 contents, all embedded resources and all 31 reference paths.
The three link repairs point to two verified existing sources: the embedded
Pedestrian Guide section 3.7 excerpt in LoadCombinations and the existing
General References page for LRFD Table 3.4.1-1. Link resolution was checked from
the native XML names/IDs; this is not a claim of GUI activation of each link.

The replacement report and user workbook are archived byte-exact. The report
identifies Pier_Fixed.XML but the matching raw XML was not available. Journal
bearing offsets remain symmetric +/-10.50 in; the older +10.14-in right-row model
record is clearly historical. Full model-input currency, the offset correction,
model convergence and final structural adequacy remain excluded. The shared
wind-width change also requires comparison against any current analysis model.

This is acceptance of geometry/source bookkeeping and faithful execution of
the response scope, not structural design approval. New reinforcement findings,
field-bending direction and the N uniform-reference explanation remain external.
Remaining engineering checks and shop-detailing items are deferred as requested.
Separate wall/fin quantities remain because their geometry is not established
by the cap report. No commit or push is performed.
'''
(T/'final-review.md').write_text(note,encoding='utf8');(ev/'final-review.md').write_text(note,encoding='utf8')
review={'candidate_sha256':j.sha256,'reviewer':'Codex — source/geometry data review and actual native Blockpad observations; no human engineering sign-off','native_recalculation':True,'native_visual_review':True,'engineering_review':True,'design_outcome':'not_applicable','external_analysis_status':'excluded_from_accepted_scope','external_analysis_disposition':'Replacement Pier_Fixed report archived exactly. Matching raw XML unavailable; offset correction and full current model-input currency remain unverified. No model rerun or structural adequacy approval. Acceptance limited to geometry/source records, user-directed wind-width linkage and reference repairs.','inherited_issues_disposition':'All three inherited broken links repaired with verified existing targets; zero stored errors and structural issues. C005 remains byte-identical by user direction. Historical cap sketches labeled. Separate wall/fin quantities and deferred steel/design checks remain explicitly outside acceptance.','evidence_files':[{'path':p.relative_to(folder).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(ev.rglob('*')) if p.is_file()]}
(folder/'review.json').write_text(json.dumps(review,indent=2),encoding='utf8')
print(json.dumps({'candidate_sha256':j.sha256,'native_review':'completed with explicit revision/component binding','C005_unchanged':True,'evidence_files':len(review['evidence_files'])},indent=2))
