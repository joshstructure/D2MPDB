"""Bounded source-record update; no native capacity model is invented."""
from pathlib import Path
import sys,json,re,html,hashlib,shutil,ast,math
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[2]; TASK=Path(__file__).parent
OUT=Path('C:/Users/joshs/Desktop/D2 MPDB/outputs/pier-coherence-20261009')
sys.path.insert(0,str(ROOT));sys.stdout.reconfigure(encoding='utf8')
from tools.bpad_workflow import Journal
helpers=ast.parse((ROOT/'tasks/T002/update_journal.py').read_text(encoding='utf8'))
exec(compile(ast.Module(body=[n for n in helpers.body if isinstance(n,ast.FunctionDef) and n.name in ('para','heading','section','eq','link','f','table','xml')],type_ignores=[]),'presentation helpers','exec'))
base=Journal.load(TASK/'base.bpad')
assert base.sha256=='4cdc73c485443fd22aaa77eff17ea1faeec30f9ba143be881b5d6c9676189625'
contract=json.loads((TASK/'order.json').read_text())
parts={k:base.part(k).decode('utf8') for k in contract['writes']}
G='report:BridgeGeometry_2Beam';C='report:PierCapDesign';F='report:FBMPPier';M='report:FoundationModeling';Q='spreadsheet:QauntitiesBridge';P='report:PedBridge';D='report:DecisionLog'
log=[]
def rep(k,a,b,n=1):
 assert parts[k].count(a)==n,(k,a[:100],parts[k].count(a),n)
 parts[k]=parts[k].replace(a,b);log.append([k,a[:180],b[:180],n])
def append(k,e):rep(k,'</'+k.split(':')[0]+'>','\n'+xml(e)+'\n</'+k.split(':')[0]+'>')
def insert_start(k,e):
 pos=parts[k].index('>')+1;parts[k]=parts[k][:pos]+'\n'+xml(e)+parts[k][pos:]
def page(p,title):heading(p,title,1).set('pagebreakbefore','break')
src=TASK/'sources';src.mkdir(exist_ok=True)
report=Path('C:/Users/joshs/Downloads/Pier Cap Design 10-9.html');model=Path('C:/Users/joshs/Downloads/Pier_MinTip.XML')
rh=hashlib.sha256(report.read_bytes()).hexdigest();mh=hashlib.sha256(model.read_bytes()).hexdigest()
assert rh=='806a47bb50962827f5fd3e6fdd4c42c8b41851bddd23ff3948f377fe6a48b7b2'
assert mh=='cb094424ed16e60b16957ed84a62aea21533fb61671c58a27ca73a997eaf70e4'
for p in (report,model):shutil.copy2(p,src/p.name)
for name in ('report-case-0.json','report-tables.json'):shutil.copy2(OUT/name,src/name)
case=json.loads((src/'report-case-0.json').read_text(encoding='utf8'));tables=json.loads((src/'report-tables.json').read_text(encoding='utf8'))
assert case['analysis']['xml_audit']['sha256']==mh
(src/'provenance.json').write_text(json.dumps({'report_file':report.name,'report_sha256':rh,'analysis_xml_file':model.name,'analysis_xml_sha256':mh,'local_xml_matches_report':True,'scope':'Pier only; source snapshot and geometry/steel bookkeeping; no final design approval or FBMP rerun'},indent=2),encoding='utf8')

g=section('PierCurrentGeometry')
heading(g,'Current pier cap geometry — 9 October 2026',0)
para(g,'Pier Cap Design 10-9.html confirms the existing 48-in by 36-in cap and four 20-in pipe piles at 60-in centers. The live project geometry above remains the owner. The new record below completes the cap-end datum, physical embedment and gross quantity definitions. Pier pedestals remain 48 in long by the user’s prior direction.')
for form,caption in [
 ('PierCap_edgeClear = 9 in','Entered pile-face edge-clearance allowance.'),
 ('PierCap_pileTolerance = 3 in','Horizontal pile placement tolerance.'),
 ('PierCap_endDetail = 3 in','Report additional end allowance; C005 retains 3.44 in and is unchanged by user direction.'),
 ('PierCap_pileEmbed = 12 in','Physical embedment above cap underside; not an analysis elevation.'),
 ('PierCap_endCenter = PierCap_endClear+Pier_pile_diameter/2 to in','25-in cap-end to first pile-center datum shift.'),
 ('PierCap_endCheck = If(Abs(PierCap_endClear-PierCap_edgeClear-PierCap_pileTolerance-PierCap_endDetail) < 0.000001 in,"MATCH","RECONCILE END ALLOWANCES")','Checks 15 = 9 + 3 + 3 in against the existing shared end-face distance.'),
 ('PierCap_area = PierCap_width*PierCap_ht to ft^2','Gross rectangular cap area, 12 ft².'),
 ('PierCap_volume = PierCap_area*PierCap_length to ft^3','Gross cap concrete, 230 ft³; no pile deductions, walls or pedestals.'),
 ]:eq(g,form,caption)
table(g,'PierCurrentStations',['Pile','Center from cap end','Face nearest left end','Face nearest right end'],[[str(i),f(f'PierCap_endCenter+{i-1}*Pile_spacing to in'),f(f'PierCap_endCenter+{i-1}*Pile_spacing-Pier_pile_diameter/2 to in'),f(f'PierCap_endCenter+{i-1}*Pile_spacing+Pier_pile_diameter/2 to in')] for i in range(1,5)],[50,170,170,170],'output')
para(g,'Model cap X coordinates run from -25 to +205 in relative to the first pile center. Add 25 in for cap-end stations. Bearing cap nodes 16/33 at X = 38.50/141.49 in therefore lie at 63.50/166.49 in from the cap end. Separation 102.99 in agrees with the journal’s 103 in to printed XML precision. The right bearing row has a separate 0.36-in offset conflict recorded in the coherence review.')
link(g,'Report and matching model source; bearing offset review','#FBMPPier.PierSourceModelRecord')
append(G,g)

# User steering: C005 must remain byte-identical. The source record belongs in
# FBMP Entry - Pier, following the earlier end-bent record convention.

# Reinforcement and design results stay in the separate report / Excel review.
fr=section('PierSourceModelRecord');heading(fr,'Pier source model reconciliation — 9 October 2026',0)
para(fr,'Geometry source: Pier Cap Design 10-9.html. Report SHA-256: '+rh,fontsize='9')
para(fr,'Exact matching Pier_MinTip.XML SHA-256: '+mh,fontsize='9')
para(fr,'User direction: geometry and source references only in BPAD. Reinforcement details and their coherence findings remain in the separate report and Excel review. C005 is completely unchanged, including its earlier steel, forces and 3.44-in end-detail input; the current geometry record uses the report’s 3-in end-detail allowance.')
table(fr,'PierSourceBearingMap',['Bearing label','Bearing node','Cap node','XML X (in)','XML Y (in)'],[
 ['1L','181','16','38.50','-10.50'],['2L','182','33','141.49','-10.50'],['1R','183','16','38.50','+10.14'],['2R','184','33','141.49','+10.14'],
 ],[120,110,110,160,160])
para(fr,'The existing four bearing labels are consistent with the XML. Cap nodes 16 and 33 are connections, not substitutes for the four bearing application identities. XML X starts at the first pile; add 25 in for cap-end stations. Global XML Z = -497.01 in and the journal’s local zero elevation use different datums; no equality is assumed.')
para(fr,'OPEN OFFSET CONFLICT: the journal uses symmetric +/-10.50-in longitudinal offsets. XML right bearings are +10.14 in, 0.36 in closer to the cap centerline. Existing load-transfer calculations and offsets are retained pending the user’s Excel response. Source gravity magnitudes agree at printed precision; this does not verify the full wind/dead-load/model pair.',fontweight='bold',background='#FFF8E9')
link(fr,'Current pier cap geometry','#BridgeGeometry_2Beam.PierCurrentGeometry')
insert_start(F,fr)
mr=section('PierSourceReconciliation');heading(mr,'Pier model source — 9 October 2026',1)
para(mr,'The current pier record uses the exact Pier_MinTip.XML matching Pier Cap Design 10-9.html (SHA256 '+mh+'). Cap section, 230-in length, four 20-in pipes, 60-in spacing, 103-in bearing separation and effective pipe-section properties reconcile to displayed precision. Actual right bearing offset +10.14 in differs from the journal +10.50 in. Full load application, independent wall/wind envelopes and structural adequacy remain outside this source-data acceptance; no FBMP rerun is claimed.')
link(mr,'Bearing map and offset conflict','#FBMPPier.PierSourceModelRecord');append(M,mr)
pr=section('PierJournalRevision20261009');heading(pr,'Pier revision — 9 October 2026',1)
para(pr,'The 9 October pier geometry is recorded in Bridge Geometry; report and matching XML references are in FBMP Entry - Pier. C005 remains completely unchanged by the user’s express direction. Reinforcement stays separate in the report and Excel review. Gross cap quantity remains 230 ft³; pier pedestals remain 48 in. Open geometry/model decisions are identified in the companion Excel response workbook.')
link(pr,'Current pier cap geometry','#BridgeGeometry_2Beam.PierCurrentGeometry');append(P,pr)
dr=section('PierDecision20261009');heading(dr,'2026-10-09 — current pier cap source record',1)
para(dr,'User direction: do not update calc C005; keep steel separate; geometry and source references only in BPAD. Retain the 48 × 36 × 230-in cap, four 20-in pipes at 60-in centers, 15-in face extension and 48-in pedestals. Record the 12-in physical embedment, 25-in cap-end/pile-center datum shift and 3-in end-detail allowance from the new report. C005 remains completely unchanged; its retained 3.44-in allowance and earlier inputs are not silently reconciled. Historical 6D/34-ft-2-in directions remain chronological history and are superseded for current shared geometry.')
para(dr,'Exact matching model identity is verified. The +10.14 versus +10.50-in right-row offset and independent wind/wall geometry await Excel responses. Full journal/model load currency and final structural adequacy are not claimed. Reinforcement details, source checks and steel findings remain only in the separate report and Excel review; no new steel record is inserted into BPAD.')
link(dr,'Current pier cap geometry','#BridgeGeometry_2Beam.PierCurrentGeometry');append(D,dr)

# Quantity is already correct. Link its owner directly and annotate the scope.
rep(Q,'formula="PedBridgeWeights_2Beams.H37"','formula="BridgeGeometry_2Beam.PierCap_volume to ft^3"')
rows=list(re.finditer(r'<row(?:\s[^>]*)?\s*/>|<row(?:\s[^>]*)?>.*?</row>',parts[Q],re.S));row=rows[49]
assert not 'formula=' in row.group() and not 'textvalue' in row.group()
note='<row><textcell capture="False"><paragraph fontfamily="Times New Roman" fontsize="10">Current pier cap only: 230 ft³ gross; no pile deduction, wall or pedestal. Geometry source: Pier Cap Design 10-9.html. Reinforcement remains in the separate report/review.</paragraph></textcell></row>'
parts[Q]=parts[Q][:row.start()]+note+parts[Q][row.end():]
data=base.replace({k:v.encode('utf8') for k,v in parts.items()})
(TASK/'working.bpad').write_bytes(data)
new=Journal.load(TASK/'working.bpad')
assert new.part(C)==base.part(C),'C005 must remain exactly unchanged'
(TASK/'change-log.json').write_text(json.dumps(log,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'working_sha256':new.sha256,'changed':base.changes(new),'source_match':True},indent=2))
