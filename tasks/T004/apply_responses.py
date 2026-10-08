"""Apply designated workbook responses with bounded, lossless component edits."""
from pathlib import Path
import ast, hashlib, html, json, re, shutil, sys
import xml.etree.ElementTree as E

sys.stdout.reconfigure(encoding='utf8')
TASK = Path(__file__).parent
REPO = TASK.parents[1]
sys.path.insert(0, str(REPO))
from tools.bpad_workflow import Journal

# Reuse presentation builders only; never execute T002's authoring operations.
tree = ast.parse((REPO/'tasks/T002/update_journal.py').read_text(encoding='utf8'))
builders = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in
            {'para','heading','section','eq','link','f','table','xml'}]
exec(compile(ast.Module(body=builders, type_ignores=[]), '<native presentation builders>', 'exec'))

base = Journal.load(TASK/'base.bpad')
assert base.sha256 == 'a45256fbdd3c27444bb3b93ffc327353efcfdc366a126aff35f809a853635d72'
contract = json.loads((TASK/'order.json').read_text())
parts = {k:base.part(k).decode('utf8') for k in contract['writes'] if k not in contract['deletes']}
G='report:BridgeGeometry_2Beam'; F='report:FBMPEndBent'; Q='spreadsheet:QauntitiesBridge'
P='report:PedBridge'; M='report:FoundationModeling'; D='report:DecisionLog'
changes=[]
def rep(k, old, new, count=1):
    assert parts[k].count(old)==count, (k,old,parts[k].count(old),count)
    parts[k]=parts[k].replace(old,new)
    changes.append({'component':k,'old':old,'new':new,'count':count})
def formula(k, old, new):
    rep(k, 'formula="'+html.escape(old,quote=True)+'"', 'formula="'+html.escape(new,quote=True)+'"')
    rep(k, '<expbody>'+html.escape(old,quote=False)+'</expbody>', '<expbody>'+html.escape(new,quote=False)+'</expbody>')
def append(k, e):
    tag=k.split(':')[0]
    rep(k, '</'+tag+'>', '\n'+xml(e)+'\n</'+tag+'>')

src=TASK/'sources'; src.mkdir(exist_ok=True)
response=Path('C:/Users/joshs/Desktop/D2 MPDB/outputs/coherence-response-20261008/End_Bent_Coherence_Review_Responses.xlsx')
shutil.copy2(response,src/response.name)
shutil.copy2(response.parent/'received-responses.json',src/'received-responses.json')
(src/'provenance.json').write_text(json.dumps({
    'workbook_original':str(response),'workbook_sha256':hashlib.sha256(response.read_bytes()).hexdigest(),
    'instructions':'User-designated response cells in items 01–09, read under See my responses request',
    'report_provenance':'tasks/T002/sources/provenance.json',
    'report_currency':'User confirms the report has the latest FBMP model; use the report where data differs',
    'scope':'Both end bents follow the controlling bent; no separate End Bent 2 actions invented',
},indent=2,ensure_ascii=False),encoding='utf8')

# Independent pedestal interfaces, retaining the established section inputs.
e=E.Element('holder')
heading(e,'End-bent pedestals — separate from pier')
for value,caption in [
 ('EndBentPedestal_ht = 6 in','Established end-bent height; independent of the pier pedestal input.'),
 ('EndBentPedestal_width = 42 in','Established transverse width, measured across the beam.'),
 ('EndBentPedestal_chamfer = 3/4 in','Established two top chamfers, retaining the quantity convention.'),
 ('EndBentPedestal_area = EndBentPedestal_width*EndBentPedestal_ht-EndBentPedestal_chamfer^2 to ft^2','End-bent transverse area; pier quantities retain Pedestal_area.'),
 ('EndBentPedestal_fromRear = EndBent_rearFaceInset+Backwall_thickness_shown to in','Pedestal starts at the backwall front; 12 in from the cap rear face.'),
]: eq(e,value,caption)
insertion='\n'.join(xml(x) for x in e)
pattern=re.compile(r'<paragraph\b[^>]*(?<!/)>\s*<dynexp formula="Pedestal_length_endBent = 4 ft".*?</paragraph>',re.S)
matches=list(pattern.finditer(parts[G])); assert len(matches)==1
m=matches[0]; parts[G]=parts[G][:m.start()]+insertion+'\n'+parts[G][m.start():]
formula(G,'Pedestal_length_endBent = 4 ft','Pedestal_length_endBent = EndBentCap_width-EndBentPedestal_fromRear to in')
rep(G,'Retained end-bent pedestal length for quantities — verify.','User response: 42-in cap less 12-in backwall gives 30 in along the beam. The pier pedestal remains 48 in.')
formula(G,'Pedestal_volume_endBent = Pedestal_count_endBent*Pedestal_area*Pedestal_length_endBent to ft^3','Pedestal_volume_endBent = Pedestal_count_endBent*EndBentPedestal_area*Pedestal_length_endBent to ft^3')
formula(G,'EndBent_BearingPlane_CapCG = EndBentCap_depth/2+Pedestal_ht+Bearing_pad_thickness+Bearing_separatePlateThickness to ft in','EndBent_BearingPlane_CapCG = EndBentCap_depth/2+EndBentPedestal_ht+Bearing_pad_thickness+Bearing_separatePlateThickness to ft in')
rep(G,'Bearing plane above the end-bent cap centroid, using the existing 6-in pedestal and Type F pad.','Bearing plane above the end-bent cap centroid, using the separate 6-in end-bent pedestal and Type F pad.')
rep(G,'Checks the pad dimension chain only. The retained 48-in pedestal footprint exceeds the current cap width and remains unresolved; this check does not establish pedestal fit.','Checks the pad dimension chain only. The end-bent pedestal occupies the remaining 30 in between the backwall front and cap front; the pier pedestal remains 48 in.')
rep(G,'* Pedestal outline is illustrative. Its retained 48-in longitudinal footprint exceeds the current 42-in cap width. The bearing-offset calculation uses the pad and backwall chain, not that unresolved footprint. Rear backwall face remains adopted flush with cap rear face.','End-bent pedestal: 30 in along the beam, from the 12-in backwall front to the 42-in cap front. Rear backwall face is adopted flush with the cap rear face. Vertical drawing proportions are schematic; live dimensions govern.')
rep(G,'Both end bents: geometry and entered reinforcement. Forces and analysis provenance: End Bent 1 only.','Both end bents follow the controlling End Bent 1 geometry and reinforcement by user direction. Source forces are from End Bent 1.')

# Node renumbering preserves the physical near/far identities and sign selections.
formula(F,'EB_Node_near = 12','EB_Node_near = 15')
formula(F,'EB_Node_far = 19','EB_Node_far = 34')
for old,new in [('Toward node 19','Toward node 34'),('Toward node 12','Toward node 15'),
                ('Node 12 is','Node 15 is'),('node 19 is','node 34 is'),
                ('nodes 12 and 19','nodes 15 and 34'),('numbers remain 12 and 19','numbers remain 15 and 34')]:
    rep(F,old,new,parts[F].count(old))
rep(F,'END BENT 1 | SPAN 1 | LEGACY NODE MAP — VERIFY BEFORE ENTRY','END BENT 1 | SPAN 1 | NODES 15 AND 34')
rep(F,'MODEL COHERENCE OPEN: the load-entry tables retain legacy nodes 12/19. The report audit places the bearing force stations at nodes 15/34. Confirm node mapping, axes, node elevation, longitudinal eccentricity and load inputs against the exact analyzed model before using these tables. The report XML fingerprint differs from the available same-named XML.',
    'CURRENT MODEL BASIS: the user confirms the cap report contains the latest FBMP model. Loaded nodes are 15 and 34; added model nodes changed their numbering. Physical axes, node-line choice, elevation and load-transfer conventions are retained. Both end bents follow the controlling End Bent 1 design. The different same-named Downloads XML is not the report source.')
formula(F,'EB_CheckSpan = "REMAP REQUIRED - LEGACY 12 / 19; REPORT BEARING STATIONS AT 15 / 34"',
          'EB_CheckSpan = If(EB_SpanNumber == 1,"END BENT 1 - NODES 15 / 34","SPAN SELECTION CHANGED - REMAP NODES")')
formula(F,'EB_CheckFootprint = If(BridgeGeometry_2Beam.Pedestal_length_endBent <= BridgeGeometry_2Beam.EndBentCap_width,"FOOTPRINT FITS CAP WIDTH","REVISE LEGACY 4-FT PEDESTAL FOOTPRINT")',
          'EB_CheckFootprint = If(And(BridgeGeometry_2Beam.Pedestal_length_endBent > 0 in,BridgeGeometry_2Beam.EndBentPedestal_fromRear+BridgeGeometry_2Beam.Pedestal_length_endBent <= BridgeGeometry_2Beam.EndBentCap_width),"FITS AVAILABLE CAP WIDTH","REVISE END-BENT FOOTPRINT")')
formula(F,'EB_PedestalDC = BridgeGeometry_2Beam.Pedestal_area*BridgeGeometry_2Beam.Pedestal_length_endBent*EB_gammaConcrete to kip',
          'EB_PedestalDC = BridgeGeometry_2Beam.EndBentPedestal_area*BridgeGeometry_2Beam.Pedestal_length_endBent*EB_gammaConcrete to kip')
rep(F,'Below-pad weights belong to the end bent, not the pier. The following provisional quantities use one end-bent pedestal and one end-bent cheek wall per bearing from the existing journal. They are excluded from the master DC rows.',
    'Below-pad weights belong to the end bent. Each bearing uses the separate 30-in end-bent pedestal. The cheek-wall quantity remains provisional and is deferred by the user. These local weights are excluded from the master superstructure DC rows.')
rep(F,'The legacy end-bent pedestal quantity uses a 4-ft longitudinal length, longer than the new 3-ft cap width. Its weight remains a provisional source quantity until the footprint is reconciled. Enter the confirmed length in Bridge Geometry; the quantity and these loads will update together. Apply local dead weights once at their actual centroids. The table lists magnitudes only; centroid eccentricities and transfer moments for these provisional below-pad weights are not established.',
    'The end-bent pedestal length is 30 in = 42-in cap minus 12-in backwall. Its concrete quantity and dead weight follow the live end-bent geometry. The longitudinal centroid is 27 in from the cap rear face, 6 in toward the span from the centered pile line. The table lists gravity magnitudes only: apply local weights once at their own centroids and include the corresponding moment if transferring to another line. Cheek-wall geometry and centroid remain deferred. The report analysis has not been rerun by this journal update.')
rep(F,'Geometry link: rear-face inset + backwall thickness + adopted beam-end gap + bearing setback − half the cap width. Pile line is centered; bearing line is toward the span. The pedestal outline is illustrative pending the existing footprint correction.',
    'Geometry link: rear-face inset + backwall thickness + beam-end gap + bearing setback minus half the cap width. Pile line is centered; bearing line is toward the span. The pedestal occupies 30 in from the backwall front to the cap front; vertical proportions are schematic.')
rep(F,'Use FBMP modeled self-weight once. Cap is 36 in × 36 in; cap length is a separate model input.',
    'Use FBMP modeled self-weight once. Current cap: 42 in wide × 36 in deep × 17 ft 8 in long, linked to Bridge Geometry. Keep unmodeled local concrete weights separate.')
# Native review exposed clipping in this inherited text table. Wrap its prose
# without changing calculations, row/column positions or named interfaces.
tm=re.search(r'<table name="EBUnresolvedApplications".*?</table>',parts[F],re.S)
assert tm
wrapped=re.sub(r'<c capture="False"><textvalue>(.*?)</textvalue></c>',
    lambda m:'<textcell capture="False"><paragraph fontfamily="Times New Roman" fontsize="9.5" leftindent="0" spacingafter="3">'+m[1]+'</paragraph></textcell>',tm[0],flags=re.S)
rep(F,tm[0],wrapped)

# Both active elevation drawings use the same physical pedestal footprint.
old='[1.3+.07*BridgeGeometry_2Beam.EndBent_bearingCL_fromRear/(1 in)-.48,1.3+.07*BridgeGeometry_2Beam.EndBent_bearingCL_fromRear/(1 in)+.48,1.3+.07*BridgeGeometry_2Beam.EndBent_bearingCL_fromRear/(1 in)+.48,1.3+.07*BridgeGeometry_2Beam.EndBent_bearingCL_fromRear/(1 in)-.48,1.3+.07*BridgeGeometry_2Beam.EndBent_bearingCL_fromRear/(1 in)-.48]'
left='1.3+.07*BridgeGeometry_2Beam.EndBentPedestal_fromRear/(1 in)'
right='1.3+.07*(BridgeGeometry_2Beam.EndBentPedestal_fromRear+BridgeGeometry_2Beam.Pedestal_length_endBent)/(1 in)'
for k in (G,F):
    rep(k,old,'['+','.join([left,right,right,left,left])+']')
    rep(k,'6-in pedestal*','6-in pedestal')
    rep(k,'origin="4.2,2.76,0"','origin="4.65,2.76,0"')
    rep(k,'[1.3+.07*BridgeGeometry_2Beam.EndBent_bearingCL_fromRear/(1 in)+.48,4.1],[2.96,2.82]',f'[{right},4.55],[2.96,2.82]')
# Bring the duplicated FBMP schematic's pile outline into line with shared geometry.
old='[1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.28,1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)+.28,1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)+.28,1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.28,1.3+.07*BridgeGeometry_2Beam.EndBent_pileCL_fromRear/(1 in)-.28],[0.7,0.7,1.55,1.55,0.7]'
new=old.replace('.28','.035*BridgeGeometry_2Beam.EndBent_pileWidth/(1 in)').replace('[0.7,0.7,1.55,1.55,0.7]','[0.7,0.7,1.55+1.3*BridgeGeometry_2Beam.EndBent_pileEmbed/BridgeGeometry_2Beam.EndBentCap_depth,1.55+1.3*BridgeGeometry_2Beam.EndBent_pileEmbed/BridgeGeometry_2Beam.EndBentCap_depth,0.7]')
rep(F,old,new)

rep(F,'Geometry / cage','Common end-bent design')
rep(F,'Applies to both end bents by user confirmation. Shared dimensions are in Bridge Geometry.','Both end bents follow the controlling End Bent 1 configuration by user direction; shared dimensions are in Bridge Geometry.')
rep(F,'End Bent 1 only. Independent envelopes; maximum moment, shear and torque are not a concurrent action vector.','Latest model per user: End Bent 1 controls the common design. Independent envelope maxima are not a concurrent action vector.')
rep(F,'DETAILING SCREEN: 0 failed scalar checks; 48 pending/conditional checks; U-bar conflicts at R2, R4, R6 and R8.','Original report: 0 failed scalar checks, 48 pending/conditional checks. Current dispositions below exclude Service III and record field-adjusted U hooks; source results have not been rerun.')
rep(F,'All stations below are inches from the left cap end. Each run uses #4 bars at 6-in pitch, global shear basis G. Nineteen closed hoops plus sixteen open-bottom U-bars give 35 transverse bars. Development is unconfirmed for every run. U ends use 90-degree bends, 6-in straight tails and 3-in inside bend diameter; these ends conflict with pile/clearance envelopes in the source.',
    'All stations are inches from the left cap end. Each run uses #4 bars at 6-in pitch, global shear basis G: 19 closed hoops and 16 open-bottom U-bars. The source uses 90-degree U ends, 6-in tails and 3-in inside bend diameter. User direction: field bend the potentially interfering hooks to provide pile clearance. The table retains the original as-drawn screening; revised hook coordinates and development checks are not supplied.')
rep(F,'PILE CLASH / development pending','As drawn: clash; field-adjust hooks',4)
rep(F,'Service III / fatigue','Original Service III / fatigue')
rep(F,'Stored zero placeholders are not verified actions','Original placeholders only. Current Service III: N/A; fatigue remains pending.')
rep(F,'Source check summary: largest available D/C = 0.966155 for B actual row spacing / shrinkage. This passing scalar ratio does not close the 48 pending/conditional checks. Axial force, weak-axis bending and lateral shear are outside the sectional calculation. End Bent 2 demands and model currency require separate verification.',
    'Original source summary: maximum available D/C = 0.966155 for B row spacing / shrinkage, with 48 pending/conditional checks. This historical count is unchanged because no source calculation was rerun. Current user basis: Service III is not applicable to the nonprestressed substructure; Strength III and Service I remain applicable. Fatigue and remaining detailing/load-path checks retain their separate status. Axial force, weak-axis bending and lateral shear remain outside the source sectional calculation. Both end bents follow the controlling End Bent 1 design by user direction.')
for old,new in [
 ('Live journal chain updates with 42-in width. Verify actual XML offsets and node mapping before model entry.','Loaded nodes updated to 15/34 following the user-confirmed model renumbering. The live 42-in cap bearing chain and existing physical axes/elevation conventions are retained.'),
 ('48-in retained longitudinal footprint exceeds the 42-in cap; revised footprint not supplied. Related pedestal dead weight remains provisional.','Resolved: separate 30-in end-bent pedestal, 42-in cap less 12-in backwall. Live quantities and local pedestal weight updated. Pier pedestal remains 48 in.'),
 ('Legacy combined cap/backwall allowance is superseded. Cap volume is separated; backwall volume is unresolved by this cap-only report.','Deferred by user. Cap volume remains separate; backwall and cheek-wall final quantities remain open.'),
 ('R2/R4/R6/R8 pile conflicts; development, cutoff, anchorage and closure checks remain open.','User directs field adjustment of U hooks at potential pile conflicts. Original R2/R4/R6/R8 clash flags describe the as-drawn cage; revised geometry, development, anchorage and closure verification remain open.'),
 ('Service III, fatigue, code/exposure basis, force zones, D-regions and omitted force components remain open.','Service III is N/A for the current nonprestressed substructure per user. Strength III is retained. Fatigue, code/exposure basis, force zones, D-regions and omitted action components remain separate open checks.'),
 ('Report snapshot has its own XML identity. Available same-named XML differs; no verified current model/input pair. End Bent 2 forces are not provided.','User confirms the report contains the latest FBMP model. Its recorded hash identifies the accepted source; the different Downloads XML was not substituted. Both end bents use the controlling End Bent 1 configuration; no separate End Bent 2 action vector is claimed.'),
 ('110 stored errors in FBMPMinTip and FeetintoDecimalFeet; three broken LoadCombinations reference links. Unchanged and outside this data update.','Retired FBMP Min Tip, Feet and Inches, Metric to Inches, Scratch and CAD modules removed by user direction, including their 110 stored errors. Three preexisting LoadCombinations reference links remain unresolved.'),
]: rep(F,old,new)

# Only the end-bent area cell and its downstream caches change in the takeoff.
rowpat=re.compile(r'<row(?:\s[^>]*)?\s*/>|<row(?:\s[^>]*)?>.*?</row>',re.S)
rows=list(rowpat.finditer(parts[Q])); assert len(rows)==160
for index in (158,156):
    rows=list(rowpat.finditer(parts[Q])); m=rows[index-1]; row=m.group()
    if index==156:
        assert row.count('BridgeGeometry_2Beam.Pedestal_area')==1
        row=row.replace('BridgeGeometry_2Beam.Pedestal_area','BridgeGeometry_2Beam.EndBentPedestal_area')
    row=re.sub(r'(<c\b[^>]*formula="[^"]*"[^>]*(?<!/)>)(.*?)(</c>)',lambda x:x[1]+re.sub(r'<(num|textvalue|error)\b[^>]*>.*?</\1>','',x[2],flags=re.S)+x[3],row,flags=re.S)
    parts[Q]=parts[Q][:m.start()]+row+parts[Q][m.end():]
rep(Q,'PROVISIONAL: 48-in pedestal length exceeds 42-in cap. Revise footprint before final quantities.','Confirmed end-bent length: 30 in = 42-in cap less 12-in backwall; separate 6-in-high section. Pier pedestal remains 48 in.')
rep(Q,'PROVISIONAL: legacy cheek-wall geometry; update with the end-bent detail.','DEFERRED BY USER: legacy cheek-wall quantity remains provisional until the end-bent wall detail is supplied.')

rep(M,'Both end bents use the shared square-pile geometry in Bridge Geometry. The p-multiplier discussion below remains for pier pipe piles. The End Bent 1 report confirms its recorded cap geometry but does not establish a current journal-to-analysis input pair. Verify the exact XML identity, bearing nodes, axes, eccentricities, pedestal/backwall dead loads and convergence before relying on transferred results.',
    'Both end bents follow the controlling End Bent 1 configuration by user direction. The user confirms the cap report contains the latest FBMP model; loaded nodes are 15 and 34 after model refinement. Shared square-pile geometry and the separate 30-in end-bent pedestal are recorded in Bridge Geometry. The p-multiplier discussion below remains for pier pipe piles. The different same-named Downloads XML is not the source model. This update does not rerun FBMP or verify raw input loads absent from the report; backwall and cheek-wall quantities remain deferred.')
rep(M,'End-bent load entry: nodes 12 and 19','End-bent load entry: nodes 15 and 34')
parts[M],n=re.subn(r'<heading level="0" keepwithnext="True">Minimum Tip</heading>\s*<heading level="1">\s*See\s*<link address="#FBMPMinTip">sheet</link>\s*</heading>','',parts[M]); assert n==1
for key in contract['deletes']:
    name=key.split(':')[1]
    pat=re.compile(r'<paragraph\b[^>]*(?<!/)>\s*<link address="#'+re.escape(name)+r'">.*?</link>\s*</paragraph>',re.S)
    parts[P],n=pat.subn('',parts[P]); assert n==1,(name,n)
rep(P,'FBMP Entry - End Bent (legacy node map; review required)','FBMP Entry - End Bent (15 / 34)')
rep(P,'Revision: 30 September 2026. End-bent input uses the user-specified nodes 12 and 19, existing bearing spacing and a 36-in × 36-in cap. The end-bent module lists its remaining local geometry and quantity assumptions explicitly.',
    'Revision: 8 October 2026, coherence responses. End-bent input uses loaded nodes 15 and 34, 103-in bearing spacing and a 42-in-wide by 36-in-deep cap. Both end bents follow the controlling configuration. End-bent pedestals are 30 in long; pier pedestals remain 48 in. Deferred wall quantities and remaining design checks are identified in the current record.')
rep(P,'Geometry and current cage are recorded for both end bents. Open design, pedestal/backwall and analysis-provenance items remain listed in the design record.',
    'Both end bents follow the controlling End Bent 1 configuration. User responses applied: 30-in end-bent pedestals, nodes 15/34, latest report model, field-adjusted U hooks and Service III N/A. Wall quantities are deferred; remaining design checks are listed in the record.')

d=section('EndBentResponses20261008'); h=heading(d,'2026-10-08 — coherence responses applied',0); h.set('pagebreakbefore','break')
for text in [
 'This entry supersedes the open pedestal, node-number and model-currency statements in the earlier 8 October entry. Source: the user-completed End_Bent_Coherence_Review_Responses.xlsx, items 01–09; exact workbook and hash retained with T004.',
 '01 — End-bent pedestal: 30 in along the beam, starting at the front of the 12-in backwall on a 42-in cap. Separate end-bent section inputs retain 6-in height, 42-in transverse width and 3/4-in chamfers. Quantities and local dead weights update live. Pier pedestal remains 48 in.',
 '02 — Backwall and cheek-wall final quantities deferred by the user.',
 '03–04 — The report contains the latest FBMP model per user. Loaded node numbers change from 12/19 to 15/34 following additional model nodes. The physical near/far identities, axes and load-transfer conventions remain the same. The different Downloads XML is not substituted.',
 '05 — Station explanation: cap-end station = report audit station + 25 in. Bearing stations 29.50/132.49 become 54.50/157.49 in; 102.99-in spacing agrees with 103 in to displayed precision. This changes the measurement origin, not the geometry.',
 '06 — U-bar hooks at potential pile interference may be field bent to provide clearance per user direction. Original as-drawn clash results are retained as source evidence; revised hook geometry and anchorage have not been checked in this update.',
 '07 — Service III is not applicable to the current nonprestressed, non-post-tensioned substructure per user. Strength III, Service I and fatigue remain distinct. Original 48 pending/conditional source checks are historical, not a new recalculated count.',
 'D-region discussion: concentrated bearing loads and pile reactions disturb ordinary beam stress distributions. The cap depth is 36 in, pile spacing is 54 in and the bearing-to-nearest-pile distance is about 24.5 in. Local load-path, nodal-zone and tie anchorage checks are separate from ordinary section moment/shear checks; this issue does not depend on prestressing. No strut-and-tie design is performed here.',
 '08 — Both end bents follow the controlling End Bent 1 design, since their principal difference is the modest adjacent-span length difference. End Bent 1 is beside the 107.35-ft span versus 104.90 ft at the other end. No independent End Bent 2 forces are created.',
 '09 — Removed unused FBMP Min Tip, Feet and Inches, Metric to Inches, Scratch and CAD modules and their navigation links. Their 110 stored errors are removed with those modules. Three inherited LoadCombinations reference links remain open; no numerical consumer of a removed module remains.',
]: para(d,text)
link(d,'FHWA strut-and-tie modeling reference — D-regions, Chapter 2','https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf')
link(d,'Current design and coherence register','#FBMPEndBent.EBCurrentDesignRecord')
append(D,d)

# Clear only caches whose formulas depend on the changed interfaces or node names.
changed={'Pedestal_length_endBent','Pedestal_volume_endBent','EndBent_BearingPlane_CapCG','EB_Node_near','EB_Node_far','EB_AxisTChoice','EB_Tdirection','EB_CheckSpan','EB_CheckFootprint','EB_PedestalDC'}
forms=[e.get('formula') for k in (G,F) for e in E.fromstring(parts[k]).iter() if e.get('formula')]
for _ in range(100):
    more=set(changed)
    for form in forms:
        m=re.match(r'^\s*(\w+)\s*=(?!=)',form)
        if m and any(re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',form.split('=',1)[1]) for n in changed): more.add(m[1])
    if more==changed:break
    changed=more
cleared=[]
pat=re.compile(r'<(?P<tag>dynexp|c|planecontainer)\b[^>]*\bformula="(?P<formula>[^"]*)"[^>]*(?<!/)>.*?</(?P=tag)>',re.S)
for k in (G,F):
    def clear(m):
        form=html.unescape(m['formula'])
        if not any(re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',form) for n in changed):return m[0]
        new=re.sub(r'<(expresult|expstep|num|textvalue|bool)\b[^>]*>.*?</\1>','',m[0],flags=re.S)
        if new!=m[0]:cleared.append({'component':k,'formula':form})
        return new
    parts[k]=pat.sub(clear,parts[k])

for k,data in parts.items():E.fromstring(data)
replacements={k:v.encode('utf8') for k,v in parts.items()}
replacements.update({k:b'' for k in contract['deletes']})
(TASK/'working.bpad').write_bytes(base.replace(replacements))
(TASK/'changes.json').write_text(json.dumps({'replacements':changes,'deleted_modules':contract['deletes'],'invalidated_cached_expressions':cleared,'dependency_names':sorted(changed)},indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'changed_components':list(parts),'deleted_modules':contract['deletes'],'cleared_caches':len(cleared)},indent=2))
