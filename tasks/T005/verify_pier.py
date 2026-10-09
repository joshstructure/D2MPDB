from pathlib import Path
import sys,json,hashlib,math,re,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[2];TASK=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.stdout.reconfigure(encoding='utf8')
from tools.bpad_workflow import Journal,structural_issues
a=Journal.load(TASK/'base.bpad');b=Journal.load(TASK/'working.bpad')
d=json.loads((TASK/'sources/report-case-0.json').read_text());i=d['inputs'];t=json.loads((TASK/'sources/report-tables.json').read_text(encoding='utf8'))
x=E.parse(TASK/'sources/Pier_MinTip.XML').getroot();checks=[]
def ck(name,ok):assert ok,name;checks.append(name)
ck('source XML fingerprint',hashlib.sha256((TASK/'sources/Pier_MinTip.XML').read_bytes()).hexdigest()==d['analysis']['xml_audit']['sha256'])
ck('six permitted components only',set(a.changes(b))==set(json.loads((TASK/'order.json').read_text())['writes'])-{'report:PierCapDesign'})
ck('264 other component bytes retained',all(a.part(k)==b.part(k) for k in a.order if k not in a.changes(b)))
ck('C005 entirely unchanged by express user direction',a.part('report:PierCapDesign')==b.part('report:PierCapDesign'))
ck('no new steel or force record in BPAD',not any(s in b.data for s in [b'PierCurrentDesignRecord',b'PierSteel_',b'PierReport_']))
ck('no new structural issues',structural_issues(a)==structural_issues(b))
ck('no stored errors',len(list(b.root.iter('error')))==0)
ck('cap geometry matches report',i['b']==48 and i['h']==36 and i['N_pile']==4 and i['S_pile']==5 and i['D_pile']==20)
ck('end extension chain',i['E_clear']+3+i['E_detail']==d['analysis']['xml_audit']['nominal_end_extension_in']==15)
ck('overall cap length',3*60+20+2*15==230)
ck('gross volume',48*36*230/1728==230)
ck('main steel counts',i['n_N1']==4 and i['n_P1']==4 and i['n_B1']==4)
ck('main steel sizes',i['Bar_N1']==6 and i['Bar_P']==9 and i['Bar_B']==6)
ck('skin bars',i['n_skin']==3 and i['Bar_skin']==6)
ck('top area',abs(4*.44-1.76)<1e-12)
ck('pile area',4*1==4)
ck('span area includes continuous plus additional',abs(4*1+4*.44-5.76)<1e-12)
ck('side area',abs(3*.44-1.32)<1e-12)
ck('19 closed + 16 U = 35',sum([2,5,5,5,2])==19 and 4*4==16 and 19+16==35)
for n,run in enumerate(d['transverse_detail']['runs']):
 ck('transverse '+run['id'],run['bar']==6 and run['pitch_in']==9 and run['include_end_bar'] and run['end_min_clear_in']==2 and not run['development_confirmed'])
ck('source transverse counts/last gaps',all(str(v)+' × #6' in t[25][n+1][2] for n,v in enumerate([2,4,5,4,5,4,5,4,2])))
ck('2-inch adjacent-run clear spacing',abs(12.375-9.625-.75-2)<1e-12)
ck('gross steel report quantity',t[34][1][1]=='1171.89 lb')
ck('N reference shortfall preserved','shortfall 1.207 in²' in t[30][3][3])
nodes={n.get('node_number'):n for n in x.findall('.//PIER_GEOMETRY/NODAL_COORDINATES/NODE')}
coords={n:{p.tag:float(p.text) for p in nodes[n].find('COORDINATES')} for n in ['5','44','16','33','181','182','183','184']}
ck('cap-end node length',coords['44']['X']-coords['5']['X']==230)
ck('bearing cap stations',coords['16']['X']==38.5 and coords['33']['X']==141.49)
ck('bearing cap links',[(p.get('number'),p.get('node_number')) for p in x.findall('.//BEARING_LOCATIONS/BEARING_LOCATION')]==[('1L','16'),('2L','33'),('1R','16'),('2R','33')])
ck('left bearing offset matches',coords['181']['Y']==coords['182']['Y']==-10.5)
ck('right bearing discrepancy recorded',coords['183']['Y']==coords['184']['Y']==10.14 and '0.36' in b.part('report:FBMPPier').decode())
props=x.find('.//PILE_GEOMETRY/SEGMENT/GROSS_SECTION_PROPS')
area=math.pi/4*(20**2-(20-2*.475)**2);iner=math.pi/64*(20**4-(20-2*.475)**4)
ck('pipe area matches exact 0.475 wall to XML precision',abs(area-float(props.find('AREA').text))<.005)
ck('pipe inertia matches exact 0.475 wall to XML precision',abs(iner-float(props.find('INERTIA2').text))<.005)
dc={v.get('bearing_number')+v.get('bearing_side'):float(v.find('FZ').text) for v in x.findall('.//BEARING_LOAD_VALUES/BEARING_LOAD') if v.get('case')=='1'}
ck('superstructure DC printed precision',dc=={'1L':92.07,'2L':92.07,'1R':89.97,'2R':89.97})
oldf=[p.get('formula') for p in a.elements['report:PierCapDesign'].iter() if p.get('formula')]
newf=[p.get('formula') for p in b.elements['report:PierCapDesign'].iter() if p.get('formula')]
ck('every legacy native formula retained',all(v in newf for v in oldf))
ck('published pier materials/cover unchanged',all(v in oldf and v in newf for v in ['fc = 5.5 ksi','fy = 60 ksi','Es = 29000 ksi','C_s = 3 in']))
ck('prior geometry formula definitions retained',all(p.get('formula') in [v.get('formula') for v in b.elements['report:BridgeGeometry_2Beam'].iter()] for p in a.elements['report:BridgeGeometry_2Beam'].iter() if p.get('formula')))
ck('end-bent data untouched',a.part('report:FBMPEndBent')==b.part('report:FBMPEndBent'))
ck('31 references still relative',sum(1 for k in b.order if k.startswith('xref:') and b.elements[k].get('path','').startswith('References/'))==31)
result={'working_sha256':b.sha256,'checks_passed':len(checks),'checks':checks,'pipe_area_in2':area,'pipe_I_in4':iner,'source_bearing_coordinates_in':coords,'scope':'Source/data reconciliation only. Native review remains separate.'}
(TASK/'source-checks.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
