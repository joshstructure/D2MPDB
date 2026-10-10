"""Apply explicit pier review responses without reserializing native components."""
from pathlib import Path
import sys,re,json,hashlib,shutil,ast,html,base64
import xml.etree.ElementTree as E
R=Path(__file__).resolve().parents[2]; T=Path(__file__).parent
O=Path('C:/Users/joshs/Desktop/D2 MPDB/outputs/pier-coherence-20261009')
sys.path.insert(0,str(R));sys.stdout.reconfigure(encoding='utf8')
from tools.bpad_workflow import Journal
helpers=ast.parse((R/'tasks/T002/update_journal.py').read_text(encoding='utf8'))
exec(compile(ast.Module(body=[n for n in helpers.body if isinstance(n,ast.FunctionDef) and n.name in ('para','heading','section','eq','link','f','table','xml')],type_ignores=[]),'presentation helpers','exec'))
b=Journal.load(T/'base.bpad');assert b.sha256=='829f5450a34c76bee03ebbce06a389de76883ccaa8007b5e9bb50b17ec83de33'
parts={k:b.part(k).decode('utf8') for k in json.loads((T/'order.json').read_text())['writes']}
G='report:BridgeGeometry_2Beam'; F='report:FBMPPier'; M='report:FoundationModeling';P='report:PedBridge';D='report:DecisionLog';Q='spreadsheet:QauntitiesBridge';L='report:LoadCombinations'
log=[]
def rep(k,a,z,n=1):
 assert parts[k].count(a)==n,(k,a[:100],parts[k].count(a),n)
 parts[k]=parts[k].replace(a,z);log.append({'component':k,'old':a[:200],'new':z[:200],'count':n})
def replace_section(k,name,node):
 # Locate exact balanced section without reformatting neighboring XML.
 start=parts[k].index('<section name="'+name+'"');depth=0
 for m in re.finditer(r'<section\b[^>]*>|</section>',parts[k][start:]):
  depth+= -1 if m.group()=='</section>' else 1
  if depth==0:
   end=start+m.end();parts[k]=parts[k][:start]+xml(node)+parts[k][end:];return
 raise AssertionError(name)
def append(k,node):rep(k,'</'+k.split(':')[0]+'>','\n'+xml(node)+'\n</'+k.split(':')[0]+'>')

src=T/'sources';src.mkdir(exist_ok=True)
report=Path('C:/Users/joshs/Downloads/Pier Cap Design 10-9.html');rh=hashlib.sha256(report.read_bytes()).hexdigest()
assert rh=='7a9f48ce08bdc29f22a1b6717432dc363f0c2d8cec02ffbfc0a36bb7da39dee2'
for path in (report,O/'Pier_Cap_Coherence_Review_Responses.xlsx',O/'received-responses.json',O/'updated-case.json',O/'updated-tables.json'):
 target=src/path.name
 if target.exists():assert target.read_bytes()==path.read_bytes(),str(path)+' changed during task'
 else:shutil.copy2(path,target)
case=json.loads((src/'updated-case.json').read_text(encoding='utf8'));audit=case['analysis']['xml_audit'];mh=audit['sha256']
assert mh=='a992aa331e11b4eb9bc426a3f811938a8f71b22b3300bae3431eb2931eaff9d8'
responses=json.loads((src/'received-responses.json').read_text(encoding='utf8'))['rows'][1:]
assert len(responses)==9 and responses[5][5]=='Use the cap length from the report' and responses[8][5]=='repair now'
model=Path(sys.argv[1]) if len(sys.argv)>1 else Path('C:/Users/joshs/Downloads/Pier_Fixed.XML')
verified=model.exists()
nodes=[]
if verified:
 assert hashlib.sha256(model.read_bytes()).hexdigest()==mh,'Raw XML does not match replacement report'
 shutil.copy2(model,src/'Pier_Fixed.XML')
 root=E.parse(model).getroot()
 for n in root.findall('.//PIER_GEOMETRY/NODAL_COORDINATES/NODE'):
  if n.get('location','').startswith('Bearing'):nodes.append({'attributes':n.attrib,'coordinates':{c.tag:c.text for c in n.find('COORDINATES')}})
 # Matching identity alone does not infer corrected offsets: explicitly inspect supplied nodes.
 (src/'model-bearing-nodes.json').write_text(json.dumps(nodes,indent=2),encoding='utf8')
 assert not verified,'Inspect matching model bearings and adapt source record before applying.'

rep(G,'Pier_windFace_width = 19 ft 3 in','Pier_windFace_width = PierCap_length to in',2)
rep(G,'Retained broad-face projected pier width — verify.','Broad-face projected pier width — current cap length.')
rep(G,'Width of the existing gross direct-pier wind rectangle. Verify the exposed silhouette against the pier section; this is not substituted for the cap or wall concrete volume widths.','Use the report cap length, 230 in, as the gross direct-pier wind width per coherence response 06. Width remains a live link to the shared cap geometry. Separate wall/fin concrete quantities retain their own dimensions.')
rep(G,'The right bearing row has a separate 0.36-in offset conflict recorded in the coherence review.','The earlier model had a 0.36-in right-row offset conflict. The replacement report identifies Pier_Fixed.XML; its bearing offsets remain unverified until that exact XML is supplied.')
fr=section('PierSourceModelRecord');heading(fr,'Current pier source — response reconciliation, 9 October 2026',0)
para(fr,'Geometry source: Pier Cap Design 10-9.html, generated 2026-10-09T22:19:21+00:00; case Pier_Fixed — XML analysis.',fontsize='10')
para(fr,'Report SHA-256: '+rh,fontsize='9')
para(fr,'Report-identified Pier_Fixed.XML SHA-256: '+mh,fontsize='9')
para(fr,'The replacement report supersedes the earlier Pier_MinTip report. Cap geometry remains 48 × 36 × 230 in with four 20-in pipes at 60-in centers. The report is archived in tasks/T006/sources; the earlier exact report/model pair remains in tasks/T005/sources.')
para(fr,'SOURCE LIMIT: the matching Pier_Fixed.XML is not available locally. The report identifies the revised analysis, but its bearing-row offsets and full input currency have not been independently verified. Retain the journal’s symmetric +/-10.50-in offsets pending the matching raw model.',fontweight='bold',background='#FFF8E9')
para(fr,'User direction remains: C005 is completely unchanged. BPAD contains geometry and source references; reinforcement details and design findings remain in the separate report and Excel review. The current cap-end detail allowance is 3 in; C005 retains its earlier 3.44-in input.')
heading(fr,'Earlier verified model — historical comparison',1)
para(fr,'The following bearing mapping belongs only to the superseded Pier_MinTip.XML (SHA-256 cb094424ed16e60b16957ed84a62aea21533fb61671c58a27ca73a997eaf70e4). Its right-row Y = +10.14 in differed from the journal +10.50 in by 0.36 in; this is the typo identified for correction in response 02.')
oldsec=b.elements[F].find("section[@name='PierSourceModelRecord']")
fr.append(E.fromstring(E.tostring(oldsec.find('embed'))))
para(fr,'Cap nodes 16/33 are the connections of the four bearing identities. Cap X starts at the first pile; add 25 in for cap-end stations. The old global XML Z = -497.01 in and the journal local zero use different datums. No equivalence with the revised XML is assumed.')
link(fr,'Current pier cap geometry','#BridgeGeometry_2Beam.PierCurrentGeometry');replace_section(F,'PierSourceModelRecord',fr)
mr=section('PierSourceReconciliation');heading(mr,'Current pier model source — 9 October 2026',1)
para(mr,'The replacement Pier Cap Design 10-9.html identifies Pier_Fixed.XML, SHA-256 '+mh+'. The reported cap layout remains 48 × 36 × 230 in, with four 20-in pipes at 60-in centers. The matching raw XML remains required to verify the right-row offset correction. The prior Pier_MinTip mapping is retained only as historical evidence. Full journal/model load-input currency and structural adequacy remain outside this source-record acceptance; no FBMP rerun is claimed.')
link(mr,'Current source and historical bearing comparison','#FBMPPier.PierSourceModelRecord');replace_section(M,'PierSourceReconciliation',mr)
pr=section('PierJournalRevision20261009');heading(pr,'Pier revision — responses applied, 9 October 2026',1)
para(pr,'Current pier geometry and source references use the replacement Pier_Fixed report. The shared cap length and gross direct-pier wind width are both 230 in; gross cap volume remains 230 ft³ and pier pedestals remain 48 in. The matching raw XML is still needed to verify the offset correction. C005 is completely unchanged and reinforcement remains separate. Completed Excel responses and source snapshots are archived under tasks/T006/sources.')
link(pr,'Current pier cap geometry','#BridgeGeometry_2Beam.PierCurrentGeometry');link(pr,'Current report source','#FBMPPier.PierSourceModelRecord');replace_section(P,'PierJournalRevision20261009',pr)
dr=section('PierResponses20261009');heading(dr,'2026-10-09 — pier coherence responses applied',1)
para(dr,'This entry supersedes the initial 9 October source and wind-width assumptions above. Use the replacement Pier_Fixed report as current; keep C005 entirely unchanged and steel separate. Use the report’s 230-in cap length as the shared direct-pier wind width. The native projected area and dependent wind-force bounds follow that live width. Cap volume remains 230 ft³; pier pedestals remain 48 in. Separate wall/fin quantities are retained because the cap report does not establish their geometry.')
para(dr,'Repair the three inherited load-combination links using the existing embedded guide excerpt and general reference page. Retain old quantity-sheet cap sketches as historical. Matching raw Pier_Fixed.XML is still needed to verify the reported model correction and full input currency. Other user dispositions are preserved in the separate response record; no reinforcement detail is added here.')
link(dr,'Current pier report and model identity','#FBMPPier.PierSourceModelRecord');append(D,dr)
rep(Q,'Current pier cap only: 230 ft³ gross; no pile deduction, wall or pedestal. Geometry source: Pier Cap Design 10-9.html. Reinforcement remains in the separate report/review.','Current cap: 230 in long; 230 ft³ gross. Adjacent three-beam / 19-ft-3-in cap sketches are HISTORICAL. Use the live quantity above.')
rep(L,'#CodeReferences.CodePage42;paragraphcoderef42','#LoadCombinations;paragraphpedguide37excerpt',2)
rep(L,'<paragraph>\r\n            <image source="Resource175"','<paragraph id="paragraphpedguide37excerpt">\r\n            <image source="Resource175"')
rep(L,'>LRFD Pedestrian Bridge Guide §3.7</link>','>Pedestrian Guide §3.7 — embedded excerpt</link>')
rep(L,'#CodeReferences.CodePage14;paragraphcoderef14','#CodeReferencesGeneral.CodePage14;paragraphprojectcoderef14General')

# Complete native symbol closure for the one changed shared input. Preserve
# every formula and remove only results invalidated by the changed width.
affected={'BridgeGeometry_2Beam':{'Pier_windFace_width'}}
def uses(form,module):
 for mod,names in affected.items():
  for name in names:
   if re.search(r'(?<![\w.])'+re.escape(mod+'.'+name)+r'(?!\w)',form):return True
   if module==mod and re.search(r'(?<![\w.])'+re.escape(name)+r'(?!\w)',form):return True
 return False
changed=True
while changed:
 changed=False
 for k,e in b.elements.items():
  if e.tag not in ('report','spreadsheet'):continue
  mod=k.split(':')[1]
  for n in e.iter():
   form=n.get('formula','');m=re.match(r'^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=(?!=)',form)
   if m and uses(form.split('=',1)[1],mod) and m[1] not in affected.get(mod,set()):affected.setdefault(mod,set()).add(m[1]);changed=True
cache_edits=[]
for k,e in b.elements.items():
 if e.tag not in ('report','spreadsheet'):continue
 mod=k.split(':')[1]
 for n in e.iter():
  if uses(n.get('formula',''),mod):assert k in parts,('Unexpected consumer outside registered writes',k,n.attrib)
for k,s in parts.copy().items():
 mod=k.split(':')[1]
 def strip(m):
  form=html.unescape(m[2])
  if not uses(form,mod):return m[0]
  new=re.sub(r'<(?:expresult|num|textvalue|bool)\b[^>]*>.*?</(?:expresult|num|textvalue|bool)>','',m[0],flags=re.S)
  if new!=m[0]:cache_edits.append({'component':k,'formula':form})
  return new
 parts[k]=re.sub(r'<(dynexp|c)\b[^>]*\bformula="([^"]*)"[^>]*>.*?</\1>',strip,s,flags=re.S)

(T/'working.bpad').write_bytes(b.replace({k:v.encode('utf8') for k,v in parts.items()}));j=Journal.load(T/'working.bpad')
assert j.part('report:PierCapDesign')==b.part('report:PierCapDesign')
changes=b.changes(j);assert set(changes)<=set(parts)
provenance={'report_file':report.name,'report_sha256':rh,'report_generated_utc':'2026-10-09T22:19:21+00:00','analysis_xml_file':'Pier_Fixed.XML','analysis_xml_sha256':mh,'matching_raw_xml_available':False,'response_workbook_sha256':hashlib.sha256((src/'Pier_Cap_Coherence_Review_Responses.xlsx').read_bytes()).hexdigest(),'base_journal_sha256':b.sha256}
(src/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf8')
(T/'change-log.json').write_text(json.dumps({'replacements':log,'affected_symbols':{k:sorted(v) for k,v in affected.items()},'invalidated_caches':cache_edits,'changed_components':changes},indent=2,ensure_ascii=False),encoding='utf8')
dispositions=[
 'Applied: C005 byte-identical; no new reinforcement details in BPAD.',
 'Replacement report received; raw Pier_Fixed.XML still needed to verify right-row offset. Journal offsets retained.',
 'Recorded externally: user permits field bending of U-bar tails for potential clashes. No revised drawing, bend geometry or anchorage verification is inferred.',
 'Explained in chat. Updated uniform-reference N check requires 4.237 in², credits 3.080 in², shortfall 1.157 in². Actual cage verification remains open.',
 'Replacement report archived and adopted as current source. Full model-input currency remains unverified; geometry width change may require corresponding model update.',
 'Applied 230-in cap length to shared wind width and dependent native area/force bounds. Old cap sketches labeled historical. Separate wall quantities retained.',
 'Deferred as requested; no additional engineering checks completed.',
 'Deferred to shop detailing as requested; no fabrication allowances or spacing change made.',
 'Repaired all three links: two to verified existing embedded §3.7 excerpt; one to existing general-reference LRFD Table 3.4.1-1 page.'
]
(T/'response-disposition.json').write_text(json.dumps([{'item':r[0],'decision':r[4],'user_instruction':r[5],'disposition':d} for r,d in zip(responses,dispositions)],indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'sha256':j.sha256,'changes':changes,'invalidated_cached_results':len(cache_edits),'affected_symbols':{k:sorted(v) for k,v in affected.items()},'C005_unchanged':True},indent=2))
