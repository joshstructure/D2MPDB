"""Evidence for source/data coherence; does not certify native recalculation."""
from pathlib import Path
import sys, re, json, math, hashlib
from collections import Counter
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.bpad_workflow import Journal, structural_issues
from pier_cap.engine import Engine, Q, parse
from pier_cap.io import load_case
from pier_cap.model import evaluate, estimate_weight
from pier_cap.transverse import scheduled_bars
TASK=Path(__file__).parent
base=Journal.load(TASK/'base.bpad'); j=Journal.load(TASK/'working.bpad')
case=load_case(TASK/'sources/end_bent_1_report_case.json'); ev=evaluate(case)
results=[]
def check(label,actual,expected,tol=1e-8):
    assert abs(actual-expected)<=tol,(label,actual,expected)
    results.append({'check':label,'actual':actual,'expected':expected,'tolerance':tol,'status':'PASS'})

# Evaluate the actual journal formulas (inch/kip dimensional engine), importing
# only untouched journal source values. This is independent of Blockpad.
g=j.elements['report:BridgeGeometry_2Beam']
forms={}
for e in g.iter('dynexp'):
    m=re.match(r'^\s*(\w+)\s*=\s*(?!=)(.*)$',e.get('formula',''))
    if m: forms[m[1]]=m[1]+' = '+m[2]
names=[n for n in forms if n.startswith('EndBent')]
names += ['Beam_spacing','Pedestal_ht','Bearing_pad_thickness','Bearing_separatePlateThickness','BeamEnd_backwallClear_min','Backwall_thickness_shown','BeamEnd_bearingCL','BeamEnd_padEdge','Bearing_pad_length']
selected=[{'formula':forms[n]} for n in names]
for item in selected:
    item['formula']=re.sub(r'(\d+(?:\.\d+)? ft) (\d+(?:\.\d+)? in)',r'\1+\2',item['formula'])
# Upstream unit weight is stored as a literal in the unchanged gravity sheet.
weight_row=j.elements['spreadsheet:PedBridgeWeights_2Beams'].findall('row')[28]
weight_cell=list(weight_row)[8]
weight_text=''.join(weight_cell.itertext()).strip()
assert weight_text=='150 pcf',weight_text
engine=Engine(selected,externals={'PedBridgeWeights_2Beams.I29':Q(.150/1728,(-3,1,0))})
for n,unit,want in [('EndBentCap_width','in',42),('EndBentCap_depth','in',36),('EndBentCap_length','in',212),('EndBent_pileWidth','in',18),('EndBent_pileSpacing','in',54),('EndBent_endFace','in',16),('EndBent_endCenter','in',25),('EndBent_pileClearSpacing','in',36),('EndBent_pileCL_fromRear','in',21),('EndBent_bearingCL_fromRear','in',24),('EndBent_bearingOffset','in',3),('EndBent_padFrontClear','in',13),('EndBentCap_area','ft^2',10.5),('EndBentCap_volume','ft^3',185.5),('EndBentCaps_volume','ft^3',371),('EndBentCap_DC','kip',27.825),('EndBent_BearingPlane_CapCG','in',26.5625)]:
    unitq=engine.eval(parse('1 '+unit),{})
    v=engine.get(n);v.same(unitq);check(n+' ('+unit+')',v.v/unitq.v,want)
for i,station in enumerate([25,79,133,187],1):check('Pile center '+str(i),engine.get(f'EndBent_P{i}_station').v,station)
steel=[]
for e in j.elements['report:FBMPEndBent'].iter('dynexp'):
    if e.get('formula','').startswith('EBSteel_'):steel.append({'formula':e.get('formula')})
se=Engine(steel)
for n,want in [('EBSteel_AsTop',1.76),('EBSteel_AsPile',1.58),('EBSteel_AsSpan',2.20),('EBSteel_AsSkinSide',1.4)]:check(n+' (in^2)',se.get(n).v,want)
schedule=scheduled_bars(case)
count=Counter(x['kind'] for x in schedule)
check('Closed hoops',count['hoop'],19);check('Open bottom U bars',count['pile_u'],16);check('Transverse bars',len(schedule),35)
check('Pitch between every adjacent station (in)',max(b['station_in']-a['station_in'] for a,b in zip(schedule,schedule[1:])),6)
check('Report gross reinforcing estimate (lb)',estimate_weight(ev),616.259,0.0005)
check('Report maximum available ratio',ev.max_dc,.966155,.0000005)
check('Pending / conditional report checks',sum('PENDING' in x.status or 'CONDITIONAL' in x.status for x in ev.checks),48)
check('Failed scalar checks',sum('FAIL' in x.status for x in ev.checks),0)
assert [x['id'] for x in case['transverse_detail']['runs'] if x['kind']=='pile_u']==['R2','R4','R6','R8']
assert structural_issues(j)==structural_issues(base)
assert len(base.changes(j))==7
unchanged=[k for k in base.order if base.hashes[k]==j.hashes[k]]
assert len(unchanged)==268
assert all(base.hashes[k]==j.hashes[k] for k in base.order if k.startswith('resource:'))
assert Counter(''.join(x.itertext()) for x in base.root.iter('error'))==Counter(''.join(x.itertext()) for x in j.root.iter('error'))
new_names=[]
for key in base.changes(j):
    bnames={x.get('name') for x in base.elements[key].iter() if x.get('name')}
    current=[x.get('name') for x in j.elements[key].iter() if x.get('name')]
    assert not [n for n,c in Counter(current).items() if c>1 and n not in bnames]
    new_names+=list(set(current)-bnames)
qrows=j.elements['spreadsheet:QauntitiesBridge'].findall('row')
assert len(qrows)==160
assert list(qrows[103])[2].get('formula')=='BridgeGeometry_2Beam.EndBentCap_area to ft^2'
assert list(qrows[103])[3].get('formula')=='BridgeGeometry_2Beam.EndBentCap_volume to ft^3'
assert list(qrows[105])[4].get('formula')=='BridgeGeometry_2Beam.EndBent_count*D104 to ft^3'
payload={'candidate_sha256':j.sha256,'checks':results,'unchanged_components':len(unchanged),'changed_components':base.changes(j),'resource_bytes':'all preserved','inherited_error_count':sum(1 for x in j.root.iter('error')),'structural_issues':dict(structural_issues(j)),'new_native_names':sorted(new_names),'source_case_status':ev.status,'source_issues':ev.issues,'native_recalculation':'NOT established by this script'}
(TASK/'coherence_checks.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'checks_passed':len(results),'unchanged_components':len(unchanged),'candidate_sha256':j.sha256,'source_status':ev.status},indent=2))
