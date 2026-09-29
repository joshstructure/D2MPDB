"""Portable case bundles, traceable workbook imports and review-copy exports."""
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timezone
import csv
import hashlib
import io
import json
import re
from .model import INPUTS,GEOMETRY,validate_case,evaluate,default_case,formula_trace

def load_case(source):
    if isinstance(source,(bytes,bytearray,memoryview)):data=json.loads(bytes(source).decode('utf-8-sig'))
    else:data=json.loads(Path(source).read_text(encoding='utf-8-sig'))
    validate_case(data)
    evaluate(data)
    return data

def write_case(case,path):
    validate_case(case);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(case,f,indent=2,ensure_ascii=False,allow_nan=False)
    return path

def input_formula(name,value):
    if isinstance(value,bool):rhs=str(value).lower()
    else:rhs=f'{value:.12g}'+(' '+INPUTS[name]['unit'] if INPUTS[name]['unit'] else '')
    return name+' = '+rhs

def export_bundle(case,root='exports',search_result=None):
    e=evaluate(case)
    path=Path(root)/datetime.now(timezone.utc).strftime('case-%Y%m%d-%H%M%S-%f')
    path.mkdir(parents=True,exist_ok=False)
    write_case(case,path/'selected_case.json')
    with (path/'checks.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['Check','Status','D/C','Basis'])
        for c in e.checks:w.writerow([c.label,c.status,c.ratio,c.basis])
    (path/'blockpad_inputs.txt').write_text('\n'.join(input_formula(k,v) for k,v in case['inputs'].items())+'\n',encoding='utf-8')
    (path/'formula_trace.json').write_text(json.dumps(formula_trace(e),indent=2,ensure_ascii=False),encoding='utf-8')
    manifest={'status':e.status,'cage_issues':e.issues,'stale_geometry':e.stale,'max_dc':e.max_dc,'estimated_gross_steel_lb':e.weight_lb,
        'limitations':'Sectional checks only. Service III/fatigue readiness, D-regions, anchorage, pile-head and full code/detail review remain explicit. Gross steel excludes hooks/laps/waste; hoops conservatively use tighter spacing over the full cap.',
        'case_sha256':hashlib.sha256((path/'selected_case.json').read_bytes()).hexdigest()}
    if search_result:
        manifest['search']={k:getattr(search_result,k) for k in ('config','total','evaluated','passed','elapsed','exhaustive','rejection_counts')}
        with (path/'alternatives.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f);w.writerow(['Rank','Layout','Estimated gross steel (lb)','Maximum D/C','Complexity score'])
            for i,c in enumerate(search_result.candidates,1):w.writerow([i,c.label,c.weight_lb,c.max_dc,c.complexity])
    (path/'review.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    return path

def export_blockpad(source,case,destination):
    """Patch only C005 in a new copy; do not overwrite the user's project file."""
    from lxml import etree as E
    validate_case(case);e=evaluate(case);source=Path(source);destination=Path(destination)
    if destination.exists() or source.resolve()==destination.resolve():raise ValueError('Choose a new output filename; originals are never overwritten.')
    parser=E.XMLParser(resolve_entities=False,no_network=True)
    tree=E.parse(str(source),parser);root=tree.getroot();report=tree.find("report[@name='PierCapDesign']")
    if report is None:raise ValueError('This exporter requires the C005 Live Design journal with report name PierCapDesign.')
    other=[E.tostring(n) for n in root if n is not report]
    found={}
    for el in report.iter('dynexp'):
        f=el.get('formula','')
        if ' = ' in f:found[f.split(' = ')[0]]=el
    missing=set(INPUTS)-set(found)
    if missing:raise ValueError('C005 input definitions missing: '+', '.join(sorted(missing)))
    def replace(name,formula):
        el=found[name];el.set('formula',formula)
        for child in list(el):el.remove(child)
        E.SubElement(el,'expbody').text=formula
    for name,value in case['inputs'].items():replace(name,input_formula(name,value))
    g=case['analysis']['geometry']
    def source_test(names):
        terms=[]
        for n in names:
            unit=INPUTS[n]['unit'];u=(' '+unit) if unit else ''
            terms.append(f'Abs({n}-{g[n]:.12g}{u}) < 0.000001{u}')
        return 'And('+','.join(terms)+')'
    replace('Status_layout','Status_layout = If('+source_test(('N_pile','S_pile','D_pile','E_clear','E_detail'))+',"SOURCE PILE LAYOUT","REIMPORT ANALYSIS FORCES")')
    replace('Status_section','Status_section = If('+source_test(('b','h'))+',"SOURCE SECTION","RECHECK MODEL SELF-WEIGHT / FORCES")')
    note=E.Element('paragraph',fontfamily='Times New Roman',fontsize='11',background='#FFF5DE')
    note.text=f'NOTEBOOK REVIEW COPY — {case["name"]}. Analysis: {case["analysis"]["id"]}. {e.status}. C005 inputs now come from the exported case; other project sections are unchanged. Recalculate in Blockpad. Earlier narrative examples/source notes may describe the original model; reconcile them before finalizing.'
    report.insert(0,note)
    assert other==[E.tostring(n) for n in root if n is not report]
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as f:tree.write(f,encoding='utf-8',xml_declaration=True)
    return destination

def import_workbooks(moment,shear,torsion,base=None,analysis_id=None,low_interval_labels=None):
    """Strict reader for the supplied Max_PierCap_*_Design workbook family.

    Independent envelopes are retained, not represented as concurrent actions.
    Rejects unknown headers, missing caches, unequal pile spacing and mismatched
    station lists. Geometry b/h/nominal pile width remains user-declared.
    """
    import openpyxl
    case=deepcopy(base or default_case());audit={};datasets={};coordinate_lists=[]
    for kind,source in [('Moment',moment),('Shear',shear),('Torsion',torsion)]:
        path=Path(source);wb=openpyxl.load_workbook(path,read_only=True,data_only=True)
        try:
            name='Max_PierCap_'+kind+'_Design'
            if name not in wb.sheetnames or 'Coords' not in wb.sheetnames:raise ValueError(f'{path.name}: unsupported workbook layout.')
            rows=list(wb[name].values);header=None
            for i,row in enumerate(rows):
                if len(row)>6 and str(row[1]).strip()=='LOCATION' and str(row[6]).strip()=='AASHTO-LRFD':header=i;break
            if header is None:raise ValueError(f'{path.name}: missing expected headers.')
            expected={10:'M33'} if kind=='Moment' else {9:'F22',13:'TORSION'}
            if any(str(rows[header][i]).strip()!=v for i,v in expected.items()):raise ValueError(f'{path.name}: force-axis headers differ.')
            records=[];locations=[]
            for index,row in enumerate(rows[header+2:],header+3):
                label=str(row[1] or '').strip();state=str(row[6] or '').strip().upper()
                if not re.match(r'^(Pil|Brg)\s+\d',label) or not (state.startswith('STRENGTH') or state.startswith('SERVICE')):continue
                axis=10 if kind=='Moment' else 9 if kind=='Shear' else 13
                value=row[axis]
                if not isinstance(value,(int,float)):raise ValueError(f'{path.name}: row {index} has no cached numeric force; recalculate and save in Excel.')
                records.append({'location':label,'state':state,'value':float(value),'row':index,'combination':row[5]})
                if label not in locations:locations.append(label)
            datasets[kind]=records
            audit[kind]={'filename':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sheet':name,'records':len(records)}
            # Moment Coords has one coordinate per station in the first block.
            coords=[];started=False
            for row in wb['Coords'].values:
                v=row[0]
                if isinstance(v,(int,float)):coords.append(float(v));started=True
                elif started:break
            coordinate_lists.append(coords)
            if kind=='Moment':moment_locations=locations
        finally:wb.close()
    # Shear/torsion contain separate L/R rows at a station. Compare unique coordinates.
    reference=sorted(set(coordinate_lists[0]))
    for coords in coordinate_lists[1:]:
        if sorted(set(coords))!=reference:raise ValueError('Workbook coordinate sets differ; use all three exports from the same analysis run.')
    if len(moment_locations)!=len(coordinate_lists[0]):raise ValueError('Cannot map moment stations to Coords unambiguously.')
    pairs=list(zip(moment_locations,coordinate_lists[0]));centers=[]
    for label,x in pairs:
        if re.fullmatch(r'Pil\s+\d+\s+CL',label):centers.append(x)
    if len(centers)<2:raise ValueError('At least two labeled pile centerlines are needed.')
    gaps=[b-a for a,b in zip(centers,centers[1:])]
    if min(gaps)<=0 or max(gaps)-min(gaps)>.01:raise ValueError('Unequal pile spacing requires an expanded geometry model.')
    p=case['inputs'];p['N_pile']=len(centers);p['S_pile']=sum(gaps)/len(gaps)
    def envelope(kind,predicate,key,absolute=True):
        group=[r for r in datasets[kind] if predicate(r)]
        if not group:raise ValueError(f'Missing {key} envelope in {kind} workbook.')
        winner=max(group,key=lambda r:abs(r['value']) if absolute else r['value'])
        p[key]=abs(winner['value']) if absolute else winner['value'];audit[key]=winner
    for prefix,state in [('Mu','STRENGTH'),('MI','SERVICE-I')]:
        def state_ok(r):return r['state'].startswith(state) if state=='STRENGTH' else r['state']=='SERVICE-I'
        envelope('Moment',lambda r:state_ok(r) and r['value']<0,prefix+'_N')
        envelope('Moment',lambda r:state_ok(r) and r['location'].startswith('Pil') and r['value']>=0,prefix+'_P')
        envelope('Moment',lambda r:state_ok(r) and r['location'].startswith('Brg') and r['value']>=0,prefix+'_B')
    envelope('Shear',lambda r:r['state'].startswith('STRENGTH'),'Vu_G')
    envelope('Torsion',lambda r:r['state'].startswith('STRENGTH'),'Tu')
    if low_interval_labels:
        labels=set(low_interval_labels)
        if not labels.issubset({r['location'] for r in datasets['Shear']}):raise ValueError('Low interval labels were not found in this export.')
        envelope('Shear',lambda r:r['state'].startswith('STRENGTH') and r['location'] in labels,'Vu_L')
    else:p['Vu_L']=p['Vu_G']
    for k in ('Ready_III','Ready_fatigue'):p[k]=False
    for k in p:
        if k.startswith(('MIII_','MDL_','DMLL_')):p[k]=0
    case['analysis']={'id':analysis_id or Path(moment).stem,'geometry':{k:p[k] for k in GEOMETRY},'workbook_audit':audit,
        'notes':'b/h, nominal pile width and end allowances are user-declared. Workbook coordinate matching cannot prove files share a run; confirm analysis ID. Independent design envelopes, not concurrent actions. Low interval defaults to global shear unless explicit labels are supplied.'}
    case['name']=case['analysis']['id'];validate_case(case);evaluate(case)
    return case
