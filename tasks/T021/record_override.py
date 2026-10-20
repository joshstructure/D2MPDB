"""Bounded D-065 adoption note; retain all pre-existing bearing calculations."""
import hashlib,json,re,sys
from pathlib import Path
from xml.sax.saxutils import escape,quoteattr
ROOT=Path(__file__).resolve().parents[2];TASK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from tools.bpad_workflow import Journal
CAD=Path('C:/Users/joshs/Desktop/CAD_AI/reports/level-seats-20261020/build-v3.json')
qa=json.loads(CAD.read_text());assert qa['status']=='GEOMETRY_PASS_FINAL_FIT_OPEN'
base=Journal.load(TASK/'base.bpad')
assert base.sha256=='1a890d58c67ffba2edd60b3ab6ea14bbf7c7ad49c6e427451f2c32b97ebc262c'
key='report:BearingDesign';raw=base.part(key)
assert b'AllLevelSeatOverride' not in raw
start=raw.index(b'<section name="PierLevelSeatOverride"')
depth=0
for m in re.finditer(rb'<(/?)section\b[^>]*>',raw[start:]):
 depth+=-1 if m[1] else (0 if m[0].endswith(b'/>') else 1)
 if depth==0:end=start+m.end();break
old=raw[start:end];historical=old
replacements={
 b'Adopted override D-064: level pier pedestal tops':b'Superseded override D-064: original pier-only direction',
 b'D-064: ADOPT LEVEL PIER PEDESTAL TOPS':b'D-064 SUPERSEDED BY D-065: ORIGINAL PIER-ONLY DIRECTION',
 b'PENDING IMPLEMENTATION: bridge geometry notebook, B4 geometry tables, CAD and drawings':b'SUPERSEDED BY D-065: CAD implemented for all supports; notebook, B4 tables and drawings pending',
 b'No new numeric top elevation selected; reconcile one common top elevation per pedestal and pad/beam interfaces in the geometry update':b'SUPERSEDED BY D-065: numeric maximum elevations adopted below; final bearing fit remains open',
}
for a,b in replacements.items():
 assert a in historical
 historical=historical.replace(a,b)
fmt='fontfamily="Times New Roman" fontsize="11" spacingafter="7"'
notice=f'<paragraph {fmt}>Historical D-064 record: superseded by D-065 below. The original scope and implementation narrative are retained as history; the AllLevelSeatOverride section is the current direction.</paragraph>'.encode()
pos=historical.index(b'</heading>')+len(b'</heading>')
historical=historical[:pos]+notice+historical[pos:]
parts=['<section name="AllLevelSeatOverride" capture="False" hide="false">',
 '<heading level="2">Adopted override D-065: level as-cast bearing seats at all supports</heading>']
def para(text):parts.append(f'<paragraph {fmt}>{escape(text)}</paragraph>')
definitions={
 'BP_all_seat_override':'"D-065: LEVEL AS-CAST TOPS AT PRIOR MAXIMUM ELEVATIONS"',
 'BP_all_seat_scope':'"Six pedestals and eight pads: both end bents and the pier"',
 'BP_all_seat_longitudinal_slope':'0',
 'BP_all_seat_transverse_slope':'0',
 'BP_EB1_level_seat_elevation':'43.74578111249233 ft',
 'BP_pier_level_seat_elevation':'44.26686320063029 ft',
 'BP_EB2_level_seat_elevation':'43.75994652287092 ft',
 'BP_all_seat_pad_thickness':'2.5625 in',
 'BP_all_seat_CAD_status':'"IMPLEMENTED: native editable level pedestals and linked level pads; steel elevations preserved"',
 'BP_all_seat_final_fit_status':'"FAIL IN UNDEFORMED MODEL: as-cast stock overlaps unchanged beams; final setting and grinding remain open"',
 'BP_all_seat_downstream_status':'"Notebook, B4 geometry table and drawings pending reconciliation to D-065"',
}
def define(name):
 formula=name+' = '+definitions[name]
 parts.append(f'<paragraph {fmt}><dynexp formula={quoteattr(formula)} mathlayout="on" showsteps="False"><expbody>{escape(formula)}</expbody></dynexp></paragraph>')
para('User direction adopted 20 October 2026. This decision supersedes D-064, extends the override to both end bents, and selects numerical as-cast pedestal elevations. Maximum means the highest point of each original pedestal top, not the highest support elevation across the bridge. Each pedestal is a solid with one horizontal top face; pads are uniform thickness and level on that face.')
for n in list(definitions)[:8]:define(n)
para('Elevations use the existing model datum and are stored at native precision; both pedestals at a support share the listed value. Prior source model SHA-256: '+qa['source_sha256']+'. Caps, beam profile/camber, deck and all other geometry are unchanged. The pad thickness is retained; no taper, compression or beveled plate is invented.')
for n in list(definitions)[8:]:define(n)
para('Reinforcement: retain all '+str(qa['steel_bars_preserved'])+' pedestal bars at their prior elevations, with their native links and adopted marks. A separate pre-grinding reference prevents later regeneration from lifting the cages into the grinding allowance. Verify cover against the final approved ground surface. The prior D-047 compression-only disposition and retained tension-development diagnostics are unchanged.')
fits=qa['cold_reopen_validation']['bearing_fit_checks']
by_support={s:max(max(f['required_lowering_at_pad_start_center_end_in']) for f in fits if ('BridgePad'+s) in f['name']) for s in ['EB1','Pier','EB2']}
para('Independent undeformed CAD fit: every pad has positive-volume interference with its unchanged beam. Maximum sampled vertical differences at pad ends/centers are EB1 '+f"{by_support['EB1']:.6f}"+' in, Pier '+f"{by_support['Pier']:.6f}"+' in, and EB2 '+f"{by_support['EB2']:.6f}"+' in. These measurements describe the current rigid geometry; they are not specified grinding depths or an elastic bearing response. Final fit remains FAIL until an accepted support detail resolves the interface.')
para('Construction intent: cast level stock at the listed maximum elevations and establish any required grinding plane and final seat elevation before final pad setting. Recheck remaining pedestal thickness, reinforcement cover, surface flatness, support contact and erection/service conditions. Grinding is not an automatic approval to remove arbitrary depth or to modify a loaded support.')
para('Bearing basis: retain T019 / D-063 PierLevelSeatCheck and its signed rotations, saved analysis assumptions and limitations. Its conditional pier rotation/movement result does not approve the end bents or close combined shear, uplift/contact, load/source currency, final bearing detailing or construction-stage checks. This is a geometry override, not final bearing acceptance.')
para('Verification: six valid single-solid level pedestals, eight uniform level pads with pedestal contact, native elevation edit/restore and cage regeneration, protected original geometry/marks and saved-file reopen were checked. Native Blockpad recalculation, appearance review and engineering acceptance were not performed for this documentary addition. See T021 verification and CAD evidence/2026-10-20-level-bearing-seats.')
parts.append('</section>')
addition=('\r\n'+'\r\n'.join(parts)).encode()
updated=raw[:start]+historical+addition+raw[end:]
assert updated.replace(historical+addition,old,1)==raw
candidate=Journal(base.replace({key:updated}))
assert candidate.shell==base.shell and candidate.order==base.order
assert all(candidate.part(k)==base.part(k) for k in base.order if k!=key)
assert len(list(candidate.root.iter('error')))==len(list(base.root.iter('error')))==0
assert len(list(candidate.root.iter('dynexp')))==len(list(base.root.iter('dynexp')))+len(definitions)
for name in definitions:assert sum(x.get('formula','').startswith(name+' = ') for x in candidate.root.iter('dynexp'))==1
(TASK/'working.bpad').write_bytes(candidate.data)
protected={rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in [
 'Bridge_Geometry_2 Beam_V2.ipynb','project_current/geometry/tables/B4_Geometry_CAD_Tables.xlsx','project_current/coherence/Coherence_Tracker.xlsx']}
evidence=dict(task='T021',decision='D-065',date='2026-10-20',base_sha256=base.sha256,candidate_sha256=candidate.sha256,
 changed_component=key,protected_components_byte_exact=len(base.order)-1,existing_calculations_and_caches_byte_exact=True,
 historical_D064_disposition='Marked superseded; literal status strings updated, original direction retained as history',
 new_literal_definitions=definitions,stored_errors=0,native_recalculation=False,native_visual_review=False,engineering_review=False,
 CAD_verification_sha256=hashlib.sha256(CAD.read_bytes()).hexdigest(),CAD_candidate_sha256=qa['candidate_sha256'],
 protected_files_sha256=protected,final_bearing_fit='FAIL - as-cast stock',maximum_sampled_fit_difference_in=by_support)
(TASK/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
submission=dict(summary='D-065: all six level as-cast pedestal tops at their previous maxima and eight level uniform pads. CAD implemented; final bearing fit remains open.',
 published_outputs=['BearingDesign.'+n for n in definitions],
 assumptions_and_conventions=['As-cast elevations use source model datum and each individual pedestal maximum.','Preserve reinforcement heights and all beam/cap/profile geometry.','Supersede D-064; T019 remains a conditional pier calculation.'],
 downstream_impact=['Notebook, B4 geometry table and drawings need reconciliation.'],
 external_analysis='No rerun or final analysis currency claim; prior T019 limitations remain.',
 checks_performed=['Bounded journal byte preservation','Native CAD single-solid/level/quantity/contact checks','Native edit/restore, cage regeneration and cold reopen','Actual beam/pad interference retained as FAIL'],
 open_items=['Final seat/ground surface, cover and contact','Construction stages and final bearing adequacy','T019 combined shear/uplift and source/load reconciliation','Native journal appearance and engineering review not performed'])
(TASK/'submission.json').write_text(json.dumps(submission,indent=2)+'\n')
print(json.dumps({'journal_sha256':candidate.sha256,'protected_components':len(base.order)-1,'definitions':len(definitions)}))
