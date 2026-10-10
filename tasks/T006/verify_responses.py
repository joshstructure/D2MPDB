from pathlib import Path
import sys,json,hashlib,re,math
R=Path(__file__).resolve().parents[2];T=Path(__file__).parent
sys.path.insert(0,str(R));sys.stdout.reconfigure(encoding='utf8')
from tools.bpad_workflow import Journal,structural_issues
a=Journal.load(T/'base.bpad');b=Journal.load(T/'working.bpad');checks=[]
def ck(label,ok):
 assert ok,label
 checks.append(label)
contract=json.loads((T/'order.json').read_text());changed=set(a.changes(b))
ck('exactly nine registered components changed',changed==set(contract['writes']))
ck('261 other components byte-identical',all(a.part(k)==b.part(k) for k in a.order if k not in changed))
ck('C005 completely byte-identical',a.part('report:PierCapDesign')==b.part('report:PierCapDesign'))
ck('all embedded resources and reference paths byte-identical',all(a.part(k)==b.part(k) for k in a.order if k.startswith(('resource:','xref:'))))
ck('all three inherited link errors repaired; no structural issues',len(structural_issues(b))==0 and sum(structural_issues(a).values())==3)
ck('zero stored errors',not list(b.root.iter('error')))
for k in changed:
 old=[n.get('formula') for n in a.elements[k].iter() if n.get('formula')]
 new=[n.get('formula') for n in b.elements[k].iter() if n.get('formula')]
 expected=[f.replace('Pier_windFace_width = 19 ft 3 in','Pier_windFace_width = PierCap_length to in') for f in old]
 ck(k+' formulas preserved except authorized width alias',expected==new)
i=json.loads((T/'sources/updated-case.json').read_text())['inputs']
ck('report geometric inputs retained',i['b']==48 and i['h']==36 and i['D_pile']==20 and i['N_pile']==4 and i['S_pile']==5)
ck('cap length and volume',3*60+20+2*15==230 and 48*36*230/1728==230)
ck('current source hash recorded',b'7a9f48ce08bdc29f22a1b6717432dc363f0c2d8cec02ffbfc0a36bb7da39dee2' in b.part('report:FBMPPier'))
ck('raw XML verification limitation explicit',b'matching Pier_Fixed.XML is not available' in b.part('report:FBMPPier'))
ck('historical sketches explicitly labeled',b'HISTORICAL' in b.part('spreadsheet:QauntitiesBridge'))
ck('user response workbook archived exact', (T/'sources/Pier_Cap_Coherence_Review_Responses.xlsx').read_bytes()==Path('C:/Users/joshs/Desktop/D2 MPDB/outputs/pier-coherence-20261009/Pier_Cap_Coherence_Review_Responses.xlsx').read_bytes())
ck('all nine response dispositions recorded',len(json.loads((T/'response-disposition.json').read_text(encoding='utf8')))==9)
t=json.loads((T/'sources/updated-tables.json').read_text(encoding='utf8'))
ck('updated N reference values preserved externally','Required 4.237 in²' in t[30][3][3] and 'shortfall 1.157 in²' in t[30][3][3])
ck('deferred steel not inserted into BPAD',all(b.data.count(v)<=a.data.count(v) for v in [b'4.237',b'1.157',b'field bent',b'field-bent']))
old_iii=21.023822491151112;old_si=5.979164497151999
area_old=old_iii/0.05998547925187175
expected={'wind_width_in':230,'projected_area_ft2':area_old*230/231,'longitudinal_III_kip':old_iii*230/231,'longitudinal_SI_kip':old_si*230/231,'cap_volume_ft3':230}
ck('wind area and bounds reduce by 230/231',math.isclose(expected['projected_area_ft2']*.01705984,expected['longitudinal_SI_kip'],rel_tol=1e-12))
out={'working_sha256':b.sha256,'checks_passed':len(checks),'checks':checks,'expected_native_values':expected,'C005_sha256':hashlib.sha256(b.part('report:PierCapDesign')).hexdigest(),'scope':'Bookkeeping and geometry coherence; native validation recorded separately; structural adequacy excluded.'}
(T/'source-checks.json').write_text(json.dumps(out,indent=2),encoding='utf8');print(json.dumps(out,indent=2))
