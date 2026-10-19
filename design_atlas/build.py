"""Build a portable, read-only atlas from selected project files.

Only the output directory is written. No native solver is executed. A matching
fingerprint or input transfer never implies engineering approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from tools.project_coherence import report_case, source_checks, read_tracker
from design_atlas.origins import classify
from design_atlas.journal import extract_journal
from design_atlas.journal_calcs import extract_calculations

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).parent / 'web'
EXPORT = 'exports/cap-mathcad-20261017/'
CASE = 'project_current/cap_design/pier/selected_case.json'
REPORT = 'project_current/cap_design/pier/Pier Cap Design 10-12.html'
SHEET = EXPORT + 'Pier Cap - Cap Design.xmcd'
MAPPING = EXPORT + 'Pier Cap - Input Mapping.csv'
RECEIPT = EXPORT + 'Source and verification record.json'
REGISTRY = 'project_current/source_register.csv'
TRACKER = 'project_current/coherence/Coherence_Tracker.xlsx'

LABELS = {
    'Mu_N':'Negative design moment', 'Mu_P':'Positive moment at piles',
    'Mu_B':'Positive moment in span', 'Vu_G':'Global design shear',
    'Vu_L':'Low-interval design shear', 'Tu':'Design torsion',
    'MI_N':'Service I negative moment', 'MI_P':'Service I pile moment',
    'MI_B':'Service I span moment', 'b':'Cap width', 'h':'Cap depth',
    'fc':'Concrete strength', 'fy':'Reinforcing yield strength',
    'Es':'Steel elastic modulus', 'N_pile':'Pile count', 'S_pile':'Pile spacing',
    'D_pile':'Pile diameter', 'C_t':'Top cover', 'C_b':'Bottom cover',
    'C_s':'Side cover', 'Pile_embed':'Pile embedment', 'E_clear':'Pile end clearance',
    'E_detail':'Pile placement allowance', 'Bar_v':'Dormant scalar stirrup size',
    's_G':'Dormant scalar global pitch', 's_L':'Dormant scalar low-region pitch',
    'Bar_P':'Continuous bottom bar size', 'Bar_B':'Added span bar size',
    'Bar_N1':'Top bar size, row 1', 'n_N1':'Top bar count, row 1',
    'n_P1':'Bottom bar count, row 1', 'Bar_skin':'Side-face bar size',
    'n_skin':'Side-face bars per side', 'phi_f':'Flexural resistance factor',
    'phi_v':'Shear resistance factor', 'theta':'Compression-field angle',
    'Ready_III':'Service III readiness', 'Ready_fatigue':'Fatigue readiness'
}
LOADS = {'Mu_N','Mu_P','Mu_B','Vu_G','Vu_L','Tu','MI_N','MI_P','MI_B'}
GEOMETRY = {'b','h','C_t','C_b','C_s','N_pile','S_pile','D_pile','E_clear','E_detail','Pile_embed','C_pile'}
FACTORS = {'phi_f','phi_v','gamma_e','gamma_fat','beta_v','theta','alpha_v','Ao_factor'}
# Unit factors normalize to inches, kips and degrees. Only literal scalar
# definitions are evaluated, never worksheet formulas or native caches.
UNITS = {'unitless':(1,(0,0,0)), 'in':(1,(1,0,0)),
         'ft':(12,(1,0,0)), 'kip':(1,(0,1,0)),
         'psi':(.001,( -2,1,0)), 'ksi':(1,(-2,1,0)),
         'deg':(1,(0,0,1)), 'kip*ft':(12,(1,1,0))}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(root, path):
    return json.loads((root / path).read_text(encoding='utf-8-sig'))


def local_name(node):
    return node.tag.rsplit('}',1)[-1]


def quantity(node):
    """Evaluate only literal, dimensioned scalar MathML, failing closed."""
    tag = local_name(node)
    if tag == 'real':
        value = float(node.text)
        if not math.isfinite(value): raise ValueError('Non-finite literal')
        return value, (0,0,0)
    if tag == 'id' and (node.text or '').strip() in UNITS:
        return UNITS[node.text.strip()]
    children = list(node)
    if tag == 'apply' and len(children) == 3:
        op = local_name(children[0])
        a, da = quantity(children[1]); b, db = quantity(children[2])
        if op == 'mult': return a*b, tuple(x+y for x,y in zip(da,db))
        if op == 'div': return a/b, tuple(x-y for x,y in zip(da,db))
    raise ValueError('Unsupported expression: '+tag)


def sheet_definition(region, expected, unit):
    definitions = [n for n in region.iter() if local_name(n)=='define']
    if len(definitions)!=1 or len(definitions[0])!=2:
        return {'status':'unsupported','detail':'Expected one scalar definition.'}
    try:
        val, dim = quantity(definitions[0][1]); factor, target_dim = UNITS[unit]
        if dim != target_dim:
            return {'status':'mismatch','detail':'Worksheet dimensions differ from case units.'}
        converted = val/factor
        match = math.isclose(converted,float(expected),rel_tol=1e-10,abs_tol=1e-9)
        return {'status':'match' if match else 'mismatch','value':converted,'unit':unit,
                'detail':'Literal worksheet input equals the case value after unit conversion.' if match else 'Literal worksheet input differs from the case value.'}
    except (ValueError,KeyError,ZeroDivisionError,OverflowError) as exc:
        return {'status':'unsupported','detail':str(exc)}


def expression_text(node):
    """Display a bounded subset of native MathML; never evaluate formulas."""
    tag = local_name(node)
    if tag == 'id':
        return (node.text or '').strip() + ('[' + node.get('subscript') + ']' if node.get('subscript') else '')
    if tag == 'real': return (node.text or '').strip()
    children = list(node)
    if tag == 'parens' and len(children) == 1: return '(' + expression_text(children[0]) + ')'
    if tag == 'apply' and len(children) >= 2:
        op = local_name(children[0]); args = [expression_text(n) for n in children[1:]]
        if op in {'plus','mult','minus','div','pow'} and len(args)==2:
            return '(' + {'plus':' + ','mult':' × ','minus':' − ','div':' / ','pow':' ^ '}[op].join(args) + ')'
        if op == 'indexer' and len(args) == 2: return args[0] + '[' + args[1] + ']'
    raise ValueError('Unsupported display expression: ' + tag)


def category(key):
    if key in LOADS or key.startswith(('MIII','MDL','DMLL')): return 'Loads'
    if key in GEOMETRY: return 'Geometry'
    if key in {'fc','fy','Es','fpc'}: return 'Materials'
    if key in FACTORS: return 'Factors'
    if key.startswith('Ready'): return 'Readiness'
    return 'Reinforcement'


def stage(key):
    if key in {'JOURNAL','ROADWAY','MSE-DETAIL-DXF'} or key.startswith(('MCAD-DAT','PSB-')): return 'Basis'
    if key in {'GEOMETRY','MCAD-S1','MCAD-S2'} or 'XML' in key: return 'Analysis'
    if key.endswith('CASE') or key.endswith('TOOL'): return 'Design'
    if key in {'CAD-MODEL','CAD-RUNTIME','GEOMETRY-TABLES'}: return 'Detailing'
    return 'Deliverables'


def build_data(root=ROOT):
    root = Path(root)
    with (root / REGISTRY).open(encoding='utf-8-sig',newline='') as f:
        register = list(csv.DictReader(f))
    registered={row['source_id']:row for row in register}
    # Follow the selected records when the register advances to a newer report.
    CASE=registered['PIER-CASE']['path']
    REPORT=registered['PIER-REPORT']['path']
    checks = {c['check_id'][7:]:c for c in source_checks(root,register) if c['check_id'].startswith('SOURCE:')}
    nodes=[]; edges=[]; documents={}; fingerprints={}

    def document(path, basis='exact_bytes'):
        if path in documents: return documents[path]
        p=(root/path).resolve()
        if not p.is_relative_to(root.resolve()): raise ValueError('Source path outside repository')
        entry={'path':path,'exists':p.is_file(),'sha256':sha(p) if p.is_file() else None,'hash_basis':'exact_bytes'}
        documents[path]=entry
        if p.is_file(): fingerprints[path]=entry['sha256']
        return entry

    def evidence(path, locator, value, note=''):
        document(path)
        return {'path':path,'locator':locator,'excerpt':value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2),'note':note}

    def node(key,title,path='',status='recorded',detail='',stage_name=None,**extra):
        n={'id':key,'title':title,'path':path,'stage':stage_name or stage(key),
           'status':status,'detail':detail,'review':'Engineering review not inferred',**extra}
        if path: n['document']=document(path)
        nodes.append(n);return n

    def edge(a,b,status,label,basis,proof=None,kind='flow'):
        e={'id':f'{a}--{b}--{len(edges)}','source':a,'target':b,'status':status,
           'label':label,'basis':basis,'kind':kind,'evidence':proof or []}
        edges.append(e);return e

    for row in register:
        c=checks[row['source_id']]
        node(row['source_id'],row['topic'],row['path'],c['status'].lower(),
             row['scope'],registered_status=row['status'],registered_sha256=row['sha256'],
             fingerprint_basis=row.get('hash_basis') or 'exact_bytes',
             fingerprint_detail=c['detail'],notes=row['notes'],
             evidence=[evidence(REGISTRY,'source_id = '+row['source_id'],row)])
        for dep in filter(None,row['depends_on'].split(';')):
            edge(dep.strip(),row['source_id'],'declared','Registered dependency',
                 'Source-register dependency; does not prove a particular parameter transfer.',
                 [evidence(REGISTRY,'source_id = '+row['source_id'],{'depends_on':row['depends_on']})],kind='dependency')
    case=read_json(root,CASE);audit=case['analysis']['xml_audit']
    embedded=report_case(root/REPORT)
    same = case==embedded
    required_hash=audit['sha256']
    registered_xml=next(n for n in nodes if n['id']=='PIER-XML')
    xml_match=registered_xml['document']['sha256']==required_hash
    node('REQUIRED-PIER-XML','Report-matching FBMP run',registered_xml['path'] if xml_match else '',status='match' if xml_match else 'missing',
         detail='Exact analysis export required by the selected case. '+('The registered XML fingerprint matches.' if xml_match else 'A retained audit is available; a different registered XML is not substituted.'),
         stage_name='Analysis',expected_sha256=required_hash,
         evidence=[evidence(CASE,'/analysis/xml_audit/sha256',required_hash)])
    node('PIER-AUDIT','Retained analysis audit',CASE,'recorded',
         'Governing combinations, member stations, source fingerprint and raw end forces retained inside the selected case. Not re-extracted from an available matching XML.',
         stage_name='Analysis',evidence=[evidence(CASE,'/analysis/xml_audit',{k:v for k,v in audit.items() if k not in {'end_records','strength_envelopes','governing'}})])
    for e in edges:
        if e['source']=='PIER-XML' and e['target'] in {'PIER-CASE','PIER-REPORT'}:
            e.update(status='match' if xml_match else 'mismatch',label='Required source differs' if not xml_match else 'Source identity matches',
                     basis='Required SHA-256 '+required_hash+'; registered XML SHA-256 '+registered_xml['document']['sha256'])
    edge('REQUIRED-PIER-XML','PIER-AUDIT','recorded' if xml_match else 'missing','Retained source record',
         'The case records this exact source identity. Raw-file verification is unavailable unless the fingerprint matches.',
         [evidence(CASE,'/analysis/xml_audit/sha256',required_hash)])
    edge('PIER-AUDIT','PIER-CASE','recorded','Recorded import',case['analysis']['notes'])
    case_report=next(e for e in edges if e['source']=='PIER-CASE' and e['target']=='PIER-REPORT')
    case_report.update(status='match' if same else 'mismatch',label='Embedded case agrees' if same else 'Embedded case differs',
                       basis='Parsed saved case '+('equals' if same else 'differs from')+' the case embedded in the selected report.',kind='flow')

    # Generated Mathcad is explicitly distinct from source-register adoption.
    rows=[]; regions={}; receipt=None; receipt_ok=False
    if (root/RECEIPT).is_file():
        receipt=next((r for r in read_json(root,RECEIPT) if r.get('label')=='Pier Cap'),None)
    if (root/SHEET).is_file():
        tree=ET.parse(root/SHEET)
        regions={n.get('region-id'):n for n in tree.iter() if local_name(n)=='region'}
    if (root/MAPPING).is_file():
        with (root/MAPPING).open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    if receipt and regions:
        receipt_ok=receipt.get('case_sha256')==sha(root/CASE) and receipt.get('output_sha256')==sha(root/SHEET)
    node('PIER-MATHCAD','Pier-cap Mathcad sheet',SHEET,'recorded' if receipt_ok else 'missing' if not regions else 'mismatch',
         'Generated worksheet; not selected in the project source register. Native recalculation is not recorded.',stage_name='Detailing',
         registered_status='Unregistered generated output',native_recalculation=receipt.get('native_mathcad_recalculation') if receipt else None,
         evidence=[evidence(RECEIPT,'label = Pier Cap',receipt or {'missing':True})])
    edge('PIER-CASE','PIER-MATHCAD','match' if receipt_ok else 'mismatch','Generated input handoff',
         'Receipt case/output fingerprints '+('match the actual files.' if receipt_ok else 'are missing or differ from actual files.'),
         [evidence(RECEIPT,'label = Pier Cap',receipt or {'missing':True})])
    manual=read_json(root,'design_atlas/manual_links.json')
    for n in manual['nodes']:
        node(n['id'],n['title'],status=n['status'],detail=n['detail'],stage_name=n['stage'])
    for e in manual['edges']:
        edge(e['source'],e['target'],e['status'],e['label'],e['basis'],
             [evidence('design_atlas/manual_links.json','edges',e)],kind='context' if e['status']=='context' else 'flow')

    journal_path=registered['JOURNAL']['path']
    journal_modules=extract_journal(root,journal_path,evidence) if (root/journal_path).is_file() else []
    journal_confirmation=evidence('design_atlas/manual_links.json','journal_handoff',manual['journal_handoff'])
    for module in journal_modules:
        node(module['id'],module['title'],journal_path,'recorded',
             'Node coordinates, identities and load-entry values saved inside the project journal. Cached results are not recalculated; exact-run transfer is not verified.',
             stage_name='Basis',module=module['module'],
             short_title='Pier node data' if module['module']=='FBMPPier' else 'End-bent node data',
             evidence=[module['evidence']])
        edge('JOURNAL',module['id'],'recorded','Journal contains FBMP entry data',
             'Native journal module and its saved node-entry tables were inspected.',[module['evidence']])
        targets=['PIER-XML','PIER-MINTIP-XML','REQUIRED-PIER-XML'] if module['module']=='FBMPPier' else ['EB-XML','EB-MINTIP-XML','EB2-XML']
        for target in targets:
            if target not in {n['id'] for n in nodes}: continue
            edge(module['id'],target,'recorded','Journal node-data handoff',
                 'User confirms the journal supplied FBMP node data. The current entry module is available; the exact journal revision and cell-by-cell transfer into this run are not verified.',
                 [journal_confirmation,module['evidence']])

    calculation_modules, calculation_values, calculation_links = extract_calculations(root,journal_path,evidence,journal_modules) if (root/journal_path).is_file() else ([],[],{})
    for module in calculation_modules:
        existing=next((n for n in nodes if n['id']==module['id']),None)
        if existing:
            existing['detail']+=' Native definitions and their explicit formula references are also indexed.'
            continue
        node(module['id'],module['title'],journal_path,'recorded',
             'Calculation module inside the registered journal. Literal definitions and saved results are inspected without native recalculation.',
             stage_name=module['stage'],module=module['module'],short_title=module['short_title'],
             component=module['component'],evidence=[module['evidence']])
        edge('JOURNAL',module['id'],'recorded','Journal contains calculation module',
             'Containment in the source document; this does not establish a calculation dependency.',[module['evidence']],kind='context')
    for (source,target),link in calculation_links.items():
        edge(source,target,'recorded','Explicit journal formula references',
             'Native formulas reference '+', '.join(sorted(link['references']))+'. Saved results are not recalculated or asserted to agree.',link['evidence'])

    values=[]
    def step(title,node_id,path,locator,value,status='recorded',note='',unit=''):
        return {'title':title,'node':node_id,'value':value,'unit':unit,'status':status,
                'evidence':evidence(path,locator,value,note),'note':note}

    def append_mathcad(v,row,expected,unit):
        region=regions.get(row['region'])
        result=sheet_definition(region,expected,unit) if region is not None else {'status':'missing','detail':'Worksheet region absent.'}
        v['sheet_status']=result['status'];v['sheet_region']=row['region']
        v['steps'].append(step('Mathcad input definition','PIER-MATHCAD',SHEET,
            '//region[@region-id="'+row['region']+'"]',result.get('value'),result['status'],
            result['detail']+' '+('The handoff receipt matches.' if receipt_ok else 'Handoff identity is not confirmed.'),unit))
        v['steps'][-1]['evidence']['excerpt']=ET.tostring(region,encoding='unicode') if region is not None else 'Region absent'
        v['steps'][-1]['mapping']=evidence(MAPPING,'region = '+row['region'],row)
        v['sheet_receipt_status']='match' if receipt_ok else 'mismatch'

    by_input={}
    for row in rows:
        m=re.fullmatch(r'Selected case inputs\.(\w+)',row['basis'])
        if m: by_input.setdefault(m.group(1),[]).append(row)
    governing=audit.get('governing',{})
    for key,val in case['inputs'].items():
        unit=case['units'].get(key,'unitless')
        v={'id':'inputs.'+key,'key':key,'label':LABELS.get(key,key),'value':val,'unit':unit,
           'category':category(key),'node_ids':['PIER-CASE','PIER-REPORT'],'steps':[],
           'source_status':'retained audit' if key in governing or key in case['analysis']['geometry'] else 'case input; upstream unlinked',
           'sheet_status':'not mapped'}
        if key in governing:
            gov=governing[key]
            v['node_ids'][:0]=['REQUIRED-PIER-XML','PIER-AUDIT']
            v['governing']=gov
            if any(m['id']=='JOURNAL-PIER-ENTRY' for m in journal_modules):
                v['upstream_context']={'node_ids':['JOURNAL','JOURNAL-PIER-ENTRY'],
                    'detail':'The journal supplies node data to the FBMP analysis. This result is produced by the analysis; it is not the same quantity as a journal node input. The exact journal revision used for the run is unconfirmed.'}
            v['steps'].append(step('Recorded governing source','PIER-AUDIT',CASE,
                '/analysis/xml_audit/governing/'+key,gov,'recorded',
                'Retained audit only. '+('Source identity matches, but the value was not independently re-extracted.' if xml_match else 'Matching raw XML is not present in the selected source register.')))
            field='shear' if key.startswith('V') else 'torque' if key=='Tu' else 'moment'
            v['transform']='Absolute magnitude / envelope selection; adopted value retained in audit.'
            if gov.get('side')=='interior':v['transform']='Recovered interior moment, then outward rounding to 0.01 kip-ft; see retained governing station.'
            if field in gov: v['raw_value']=gov[field]
            if 'adopted' in gov: v['audit_agrees']=math.isclose(float(gov['adopted']),float(val),abs_tol=1e-9)
        elif key in case['analysis']['geometry']:
            local_allowance=key in {'E_clear','E_detail'}
            if local_allowance: v['source_status']='retained local allowance'
            v['steps'].append(step('Retained local allowance' if local_allowance else 'Recorded analysis geometry','PIER-AUDIT',CASE,
                '/analysis/geometry/'+key,case['analysis']['geometry'][key],'recorded',
                'Saved local allowance retained during import; see /analysis/notes.' if local_allowance else 'Saved analysis geometry; not independently re-extracted from XML.',unit))
            v['node_ids'].insert(0,'PIER-AUDIT')
        if key=='Vu_L':
            v['transform']='Set equal to global shear; no low-shear interval is established by this import.'
            v['steps'].append(step('Global shear policy','PIER-CASE',CASE,'/inputs/Vu_G',case['inputs']['Vu_G'],'recorded',audit['notes'][2],unit))
        if v.get('audit_agrees') is False:
            v['source_status']='audit differs from case input'
        v['steps'].append(step('Selected case input','PIER-CASE',CASE,'/inputs/'+key,val,
            'mismatch' if v.get('audit_agrees') is False else 'recorded',
            'Retained adopted demand differs from the selected input.' if v.get('audit_agrees') is False else '',unit))
        v['steps'].append(step('Selected report embedded input','PIER-REPORT',REPORT,
            'embedded case /inputs/'+key,embedded['inputs'].get(key),
            'match' if val==embedded['inputs'].get(key) else 'mismatch','Parsed directly from the report’s embedded JSON.',unit))
        if case.get('transverse_detail',{}).get('enabled') and key in {'Bar_v','s_G','s_L'}:
            v['source_status']='dormant scalar'
            v['note']='Actual enabled transverse runs govern the generated sheet. This scalar is retained, not the active run setting.'
        for row in by_input.get(key,[]):
            append_mathcad(v,row,val,unit); v['node_ids'].append('PIER-MATHCAD')
        values.append(v)

    runs=case.get('transverse_detail',{}).get('runs',[])
    active=bool(case.get('transverse_detail',{}).get('enabled'))
    if runs and active:
        bars=sorted({r['bar'] for r in runs}); maxpitch=max(r['pitch_in'] for r in runs)
        for key,label,val,unit,region,selector in [
            ('active_bar','Active transverse bar size',bars[0] if len(bars)==1 else bars,'unitless','38734','bar'),
            ('active_pitch','Maximum active run pitch',maxpitch,'in','36547','pitch_in')]:
            v={'id':key,'key':key,'label':label,'value':val,'unit':unit,'category':'Active runs',
               'node_ids':['PIER-CASE','PIER-MATHCAD'],'source_status':'enabled runs',
               'sheet_status':'not mapped','steps':[step('Enabled transverse runs','PIER-CASE',CASE,
                 '/transverse_detail/runs/*/'+selector,{r['id']:r[selector] for r in runs},'recorded',
                 'Active runs take precedence over dormant scalar settings.')],
               'transform':'Common bar size across enabled runs.' if key=='active_bar' else 'Maximum pitch among enabled transverse runs.'}
            mapping=next((r for r in rows if r['region']==region),None)
            if mapping and not isinstance(val,list): append_mathcad(v,mapping,val,unit)
            values.append(v)
    for idx,run in enumerate(runs):
        for key in ['bar','pitch_in','first_in','end_in','development_confirmed']:
            if key not in run:continue
            unit='in' if key.endswith('_in') else 'unitless'
            values.append({'id':f'run.{run["id"]}.{key}','key':run['id']+'.'+key,
                'label':run['id']+' · '+key.replace('_',' '),'value':run[key],'unit':unit,
                'category':'Run details','source_status':'enabled run' if active else 'disabled run',
                'node_ids':['PIER-CASE','PIER-REPORT'],'sheet_status':'not mapped',
                'steps':[step('Saved transverse run','PIER-CASE',CASE,f'/transverse_detail/runs/{idx}',run),
                         step('Report embedded transverse run','PIER-REPORT',REPORT,f'embedded case /transverse_detail/runs/{idx}',embedded.get('transverse_detail',{}).get('runs',[])[idx] if idx < len(embedded.get('transverse_detail',{}).get('runs',[])) else None)]})

    # A bounded first set of locally defined worksheet formulas, with exact
    # region evidence. These are expressions, never invented numerical results.
    for region_id,label in [('41023','Provided top reinforcement area'),
                            ('39756','Provided bottom reinforcement area at piles'),
                            ('40442','Provided bottom reinforcement area in span'),
                            ('38058','Provided side-face reinforcement area')]:
        region=regions.get(region_id)
        if region is None: continue
        definitions=[n for n in region.iter() if local_name(n)=='define']
        if len(definitions)!=1 or len(definitions[0])!=2: continue
        try:
            symbol=expression_text(definitions[0][0]); expression=expression_text(definitions[0][1])
        except ValueError: continue
        proof=step('Worksheet formula definition','PIER-MATHCAD',SHEET,
                   '//region[@region-id="'+region_id+'"]',symbol+' := '+expression)
        proof['evidence']['excerpt']=ET.tostring(region,encoding='unicode')
        values.append({'id':'formula.'+region_id,'key':symbol,'label':label,'value':'Not evaluated',
                       'unit':'','value_kind':'expression','expression':symbol+' := '+expression,
                       'category':'Worksheet formulas','node_ids':['PIER-MATHCAD'],'steps':[proof],
                       'source_status':'formula defined in worksheet','sheet_status':'not applicable'})

    # Add native XML facts from the preserved prior run without assigning them
    # to the report-matching run. Read exact elements rather than a filename guess.
    prior_path=registered_xml['path']
    if (root/prior_path).is_file():
        native=ET.parse(root/prior_path)
        prior_nodes=[]
        for n in native.iter():
            if local_name(n)=='NODE' and n.get('location')=='Pier':
                coords=next((x for x in n if local_name(x)=='COORDINATES'),None)
                z=next((x for x in coords if local_name(x)=='Z'),None) if coords is not None else None
                if z is not None: prior_nodes.append((n,z))
        if prior_nodes:
            zvals=sorted({float(z.text) for _,z in prior_nodes})
            # Retain the stable ID so saved links survive source-register changes.
            values.append({'id':'prior.pile_head_z','key':'Z','label':('Selected' if xml_match else 'Prior')+' XML pile-head Z','value':zvals,'unit':'in',
                'category':'Selected XML' if xml_match else 'Prior XML','node_ids':['PIER-XML'],'source_status':'direct XML; '+('matching selected run' if xml_match else 'prior run'),
                'sheet_status':'not applicable','steps':[step('Registered XML nodes','PIER-XML',prior_path,
                '//NODE[@location="Pier"]/COORDINATES/Z',zvals,'recorded','Registered XML fingerprint matches the selected case.' if xml_match else 'This prior file does not match the selected cap report.') ]})
    issues=read_tracker(root/TRACKER);document(TRACKER)
    for issue in issues:
        refs=issue.get('Source references','')
        issue['node_ids']=[n['id'] for n in nodes if re.search(r'(?<![\w-])'+re.escape(n['id'])+r'(?![\w-])',refs)]
    # Freshness is computed at every build; the app is an explicitly dated snapshot.
    generated=datetime.now(timezone.utc).isoformat()
    try:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):commit=None
    receipt_proof=evidence(RECEIPT,'label = Pier Cap',receipt) if receipt else None
    for v in values: v['origins']=classify(v,case,same,receipt_ok,receipt_proof)
    for module in journal_modules: values.extend(module['values'])
    values.extend(calculation_values)
    for n in nodes: n['value_count']=sum(n['id'] in v['node_ids'] for v in values)
    result={'schema_version':1,'title':'D2 Design Atlas','generated_at':generated,
        'repository_revision':commit,'nodes':nodes,'edges':edges,'values':values,
        'documents':documents,'issues':issues,'fingerprints':fingerprints,
        'checks':{'report_case_equal':same,'required_xml_present':xml_match,
                  'mathcad_receipt_matches':receipt_ok,'sheet_comparisons':dict(Counter(v['sheet_status'] for v in values))},
        'coverage':{'map':'All registered sources, named current journal calculation modules, and explicitly identified pier-cap gaps.',
                    'values':'Pier and End Bent 1 trails, mapped Mathcad inputs, and the registered journal’s named calculation definitions, saved spreadsheet cells, and FBMP entry tables. Journal literals and saved results are read without recalculation. Formula inputs link to unambiguous native definitions.',
                    'limits':['No native solver was run.',('The matching pier XML and issued PDF remain unlinked.' if not xml_match else 'No issued PDF is linked; the retained audit is not independently re-extracted.'),
                              'Registered dependencies describe relationships, not proven parameter transfers.',
                              'Journal-to-FBMP provenance is user-confirmed; exact journal revision and per-cell run transfers remain unverified.',
                              'Archived journal modules are excluded. Repeated definitions and unextracted or nested references stay unresolved. Journal calculations are not assumed to generate an external report merely because values agree.',
                              'Current calculation-tool revision is not attributed to the historical report run.',
                              'This is a read-only snapshot. Rebuild to capture changed project files.']}}
    # Detect concurrent edits during ingestion instead of publishing mixed bytes.
    from design_atlas.end_bent import extend_end_bent
    extend_end_bent(result, root, LABELS, category)
    changed=[p for p,digest in fingerprints.items() if not (root/p).is_file() or sha(root/p)!=digest]
    if changed: raise RuntimeError('Sources changed during atlas build: '+', '.join(changed))
    validate(result)
    return result


def validate(data):
    ids=[n['id'] for n in data['nodes']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate node IDs')
    for edge in data['edges']:
        if edge['source'] not in ids or edge['target'] not in ids:raise ValueError('Unresolved edge '+edge['id'])
    value_ids=[v['id'] for v in data['values']]
    if len(value_ids)!=len(set(value_ids)):raise ValueError('Duplicate value IDs')
    for v in data['values']:
        for item in v.get('inputs',[]):
            if item.get('node') and item['node'] not in ids: raise ValueError('Unresolved formula input node')
            if item.get('value_id') and item['value_id'] not in value_ids: raise ValueError('Unresolved formula input value')
        if any(n not in ids for n in v['node_ids']):raise ValueError('Unresolved value source')
        if any(n not in ids for n in v.get('upstream_context',{}).get('node_ids',[])):raise ValueError('Unresolved upstream context')
        if not v['steps']:raise ValueError('Value has no source evidence')
        for s in v['steps']:
            if s['evidence']['path'] not in data['documents']:raise ValueError('Untracked evidence file')
        if set(v['origins']) != set(v['node_ids']): raise ValueError('Missing node-relative origin')
        for origin in v['origins'].values():
            if origin['kind'] not in {'received','defined','derived','unknown'}: raise ValueError('Unknown origin role')
            if origin.get('from_node') and origin['from_node'] not in ids: raise ValueError('Unresolved origin source')
            if any(e['path'] not in data['documents'] for e in origin['evidence']): raise ValueError('Untracked origin evidence')
    json.dumps(data,allow_nan=False)


def write_atlas(data,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name in ['index.html','atlas.css','layouts.js','atlas.js']:
        shutil.copyfile(ASSETS/name,output/name)
    encoded=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    (output/'dataset.js').write_text('window.ATLAS_DATA = '+encoded+';\n',encoding='utf-8')
    (output/'atlas-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,default=ROOT/'design_atlas'/'dist')
    args=parser.parse_args()
    data=build_data(args.root);write_atlas(data,args.output)
    print(json.dumps({'output':str(args.output),'nodes':len(data['nodes']),'edges':len(data['edges']),
                      'values':len(data['values']),'checks':data['checks']},indent=2))


if __name__=='__main__':main()
