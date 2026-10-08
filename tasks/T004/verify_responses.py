"""Independent source/quantity checks, not a substitute for native review."""
from pathlib import Path
import hashlib, json, re, sys
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[2]; TASK=Path(__file__).parent
sys.path.insert(0,str(ROOT))
from tools.bpad_workflow import Journal, structural_issues
from pier_cap.engine import Engine, Q, parse
base=Journal.load(TASK/'base.bpad'); j=Journal.load(TASK/'working.bpad')
order=json.loads((TASK/'order.json').read_text()); results=[]
def check(label,condition,value=None):
    assert condition,(label,value)
    results.append({'check':label,'status':'PASS','value':value})
def forms(mod):
    return {m[1]:e.get('formula') for e in mod.iter('dynexp')
            if (m:=re.match(r'^\s*(\w+)\s*=(?!=)',e.get('formula','')))}
g=forms(j.elements['report:BridgeGeometry_2Beam']); bg=forms(base.elements['report:BridgeGeometry_2Beam'])
needed={n for n in g if n.startswith(('EndBent','Pedestal'))} | {'Beam_spacing','Beam_count','PierCap_width','Bearing_pad_thickness','Bearing_separatePlateThickness','BeamEnd_backwallClear_min','Backwall_thickness_shown','BeamEnd_bearingCL','BeamEnd_padEdge','Bearing_pad_length'}
engine=Engine([{'formula':re.sub(r'(\d+(?:\.\d+)? ft) (\d+(?:\.\d+)? in)',r'\1+\2',re.sub(r'\s*=\s*(?!=)',' = ',g[n],count=1))} for n in needed],
              externals={'PedBridgeWeights_2Beams.I29':Q(.150/1728,(-3,1,0))})
expected=[('EndBentCap_width','in',42),('EndBentCap_depth','in',36),('EndBentCap_length','in',212),
 ('EndBent_endCenter','in',25),('EndBent_pileSpacing','in',54),('EndBent_pileWidth','in',18),
 ('EndBentPedestal_fromRear','in',12),('Pedestal_length_endBent','in',30),
 ('EndBentPedestal_ht','in',6),('EndBentPedestal_width','in',42),('EndBentPedestal_chamfer','in',.75),
 ('EndBentPedestal_area','ft^2',1.74609375),('Pedestal_volume_endBent','ft^3',17.4609375),
 ('Pedestal_length_pier','in',48),('Pedestal_volume_pier','ft^3',13.96875),
 ('EndBent_bearingOffset','in',3),('EndBent_BearingPlane_CapCG','in',26.5625),
 ('EndBentCap_volume','ft^3',185.5),('EndBentCaps_volume','ft^3',371)]
for name,unit,want in expected:
    u=engine.eval(parse('1 '+unit),{}); v=engine.get(name);v.same(u)
    check(name+' ['+unit+']',abs(v.v/u.v-want)<1e-8,v.v/u.v)
for n in ['Pedestal_ht','Pedestal_width','Pedestal_chamfer','Pedestal_area','Pedestal_length_pier','Pedestal_count_pier','Pedestal_volume_pier']:
    check('Unchanged pier formula: '+n,g[n]==bg[n])
f=forms(j.elements['report:FBMPEndBent']); bf=forms(base.elements['report:FBMPEndBent'])
check('New node identities',f['EB_Node_near']=='EB_Node_near = 15' and f['EB_Node_far']=='EB_Node_far = 34')
check('All source steel definitions preserved',{k:v for k,v in f.items() if k.startswith('EBSteel_')}=={k:v for k,v in bf.items() if k.startswith('EBSteel_')})
ext={
 'BridgeGeometry_2Beam.EndBentPedestal_area':engine.get('EndBentPedestal_area'),
 'BridgeGeometry_2Beam.Pedestal_length_endBent':engine.get('Pedestal_length_endBent'),
 'EB_gammaConcrete':Q(.150/1728,(-3,1,0))}
fe=Engine([{'formula':f['EB_PedestalDC']}],externals=ext)
check('Pedestal dead weight [kip]',abs(fe.get('EB_PedestalDC').v-.65478515625)<1e-9,fe.get('EB_PedestalDC').v)
case=json.loads((ROOT/'tasks/T002/sources/end_bent_1_report_case.json').read_text())
audit=case['analysis']['xml_audit']
for node,station in [('15',29.50),('34',132.49)]:
    records=[x for x in audit['end_records'] if x.get('node')==node]
    check('Report station at node '+node, bool(records) and all(abs(x['x_in']-station)<1e-8 for x in records),station)
check('Datum conversion', [round(x+engine.get('EndBent_endCenter').v,2) for x in audit['bearing_stations_in']]==[54.5,157.49])
q=j.elements['spreadsheet:QauntitiesBridge'].findall('row');bq=base.elements['spreadsheet:QauntitiesBridge'].findall('row')
check('Takeoff row count preserved',len(q)==len(bq)==160)
check('Pier takeoff bytes unchanged',all(E.tostring(q[n])==E.tostring(bq[n]) for n in [140,142]))
check('End-bent takeoff uses separate area',list(q[155])[2].get('formula')=='BridgeGeometry_2Beam.EndBentPedestal_area')
changed=base.changes(j,order['deletes']); check('Exactly registered changes',set(changed)==set(order['writes']))
check('All 264 other components preserved',sum(base.hashes[k]==j.hashes.get(k) for k in base.order)==264)
check('Every resource preserved',all(base.hashes[k]==j.hashes.get(k) for k in base.order if k.startswith('resource:')))
check('110 errors removed with modules',len(list(base.root.iter('error')))==110 and len(list(j.root.iter('error')))==0)
check('Only inherited reference issues',structural_issues(j)==structural_issues(base),dict(structural_issues(j)))
check('All five requested modules removed',all(k not in j.elements for k in order['deletes']))
for k in ('report:FBMPEndBent','report:FoundationModeling','report:PedBridge'):
    text=' '.join(j.elements[k].itertext())
    check('No stale active node labels: '+k, not re.search(r'(?:nodes?\s+(?:12|19)(?!\d)|LEGACY NODE MAP|REMAP REQUIRED)',text,re.I))
check('Old 36 by 36 end-bent cap note removed','Cap is 36 in × 36 in' not in j.part('report:FBMPEndBent').decode('utf8'))
for k in (G:='report:BridgeGeometry_2Beam',F:='report:FBMPEndBent'):
    mod=j.elements[k];names=[e.get('name') for e in mod.iter() if e.get('name')]
    check('No duplicate native names: '+k,len(names)==len(set(names)))
check('Report bytes preserved',hashlib.sha256((ROOT/'tasks/T002/sources/End bent 1 Cap Design Report_10-8.html').read_bytes()).hexdigest()=='42120857965352febea29e4a672b2ba93f45199430360a89f8e1e529d2df50ef')
payload={'candidate_sha256':j.sha256,'checks':results,'native_recalculation':'Not established by this script','analysis_rerun':False}
(TASK/'response_checks.json').write_text(json.dumps(payload,indent=2),encoding='utf8')
print(json.dumps({'checks_passed':len(results),'candidate_sha256':j.sha256},indent=2))
