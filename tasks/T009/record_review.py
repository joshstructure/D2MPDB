"""Record the completed native and bounded geometry review for exact candidate bytes."""
from pathlib import Path
import sys,json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2]
TASK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from bpad_workflow import Journal
from verify_module import native,checks

folder=ROOT/'generated/T009-front-side-final'
candidate=Journal.load(folder/'candidate.bpad')
base=Journal.load(TASK/'base.bpad')
saved=Journal.load(TASK/'native-reviewed.bpad')
assert candidate.data==saved.data
assert candidate.sha256=='4b1770533d7b91cfb1efbcd96b0eb2c3a73328b90f88b2b50bca15388f07cd82'
assert base.changes(candidate)==['report:MSEWallExclusion']
result=checks()
result['native']=native(folder/'candidate.bpad')
(TASK/'independent-checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(TASK/'independent-checks.json',folder/'independent-checks.json')
(folder/'native-reviewed-module.xml').write_bytes(saved.part('report:MSEWallExclusion'))
evidence={
 'candidate_sha256':candidate.sha256,
 'native_saved_file_sha256':saved.sha256,
 'entire_candidate_matches_native_save':True,
 'module_sha256':candidate.hashes['report:MSEWallExclusion'],
 'native_application':'Blockpad desktop',
 'reviewed_date':'2026-10-13',
 'native_review':'Opened, recalculated and saved first candidate in Blockpad. Inspected all five pages. Imported only assigned native component, assembled final candidate, and verified entire final file identical to reviewed native save. Reopened exact final candidate and inspected its index and MSE summary.',
 'native_pages':[
  'Page 1: 37.452 in exact / 37.5 in adopted front, 24 in sides, alpha 15 deg, 2 in strap, VALID; open U sketch dimensioned 24/24/37.5',
  'Page 2: live nominal pile inputs and tangent-clearance derivation; no pile tolerance term',
  'Page 3: End Bent 1 native plan and front-pile/wall shortfall tables, readable and unclipped',
  'Page 4: End Bent 2 native plan and front-pile/wall shortfall tables, readable and unclipped',
  'Page 5: separate cap PASS results, ordinary 15-degree skew basis, explicit front/side scope and provenance'
 ],
 'native_module_errors':0,
 'native_table_and_dimension_values_compared':74,
 'preserved_other_components':len(base.order)-1,
 'preserved_shell':base.shell==candidate.shell,
 'engineering_disposition':'Bounded centered-strap tangent screen on nominal 18-inch square piles, 2-inch trial strap, zero gap, alpha 15 deg, either skew direction, front only. Side 24-inch offset is separately specified; side strap routing and rear walls are not evaluated. Current six wall locations show shortfalls; separate cap/front-wall gaps pass 24 inches. No complete wall design acceptance.',
 'source_model_sha256':json.loads((ROOT/'mse_strap_check/layout_snapshot.json').read_text())['model_sha256'],
 'dxf_preview':'Both DXFs reopened without audit errors/fixes. Eight front limits, four side limits and source coordinate positions checked; 18 editable dimension entities rendered. Dimensioned drawing preview inspected.'
}
(folder/'native-review-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
review=json.loads((folder/'review.json').read_text())
review.update({
 'reviewer':'Codex - bounded nominal geometry, formula and native appearance review',
 'native_recalculation':True,'native_visual_review':True,'engineering_review':True,
 'design_outcome':'fails',
 'external_analysis_status':'excluded_from_accepted_scope',
 'external_analysis_disposition':'Saved CAD model fingerprint and all eight pile centers checked. Source geometry and structural analysis unchanged. Full reinforcement routing, vendor details, elevation, foundation loads and wall stability are outside this nominal clearance review.',
 'inherited_issues_disposition':'The current user-saved base, 270 unassigned components, existing index link and document shell are preserved exactly. Revised MSE module has zero native errors; 74 table/dimension outputs agree with independent equations. No acceptance of unrelated calculations or overall project design is implied.',
 'evidence_files':[{'path':name,'sha256':hashlib.sha256((folder/name).read_bytes()).hexdigest()} for name in ['native-review-evidence.json','independent-checks.json','native-reviewed-module.xml']]
})
(folder/'review.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'candidate_sha256':candidate.sha256,'native_values_compared':74,'preserved_components':len(base.order)-1},indent=2))
