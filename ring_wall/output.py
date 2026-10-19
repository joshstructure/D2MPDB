"""Shared calculation disclosures, offline report, native sheets and export bundle."""
import ast
import csv
import hashlib
from html import escape
import io
import json
from pathlib import Path
import re
import zipfile

STYLE='''body{font:14px/1.5 Arial,sans-serif;color:#213649;margin:32px auto;max-width:1200px;padding:0 20px}h1,h2,h3{color:#244d70}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0}th,td{border:1px solid #cad5df;padding:7px;text-align:left;vertical-align:top}th{background:#e9eff5}details{padding:6px;border-bottom:1px solid #dfe6ec}summary{cursor:pointer;color:#245c85}.ring-note{background:#edf3f8;padding:12px;border-left:4px solid #567e9c;margin:10px 0}.ring-status{background:#fff3d9;padding:12px;border-left:4px solid #b57820;margin:10px 0}.PASS{color:#18754f}.FAIL{color:#b53333}.PENDING{color:#98600d}.check-formula,.check-values{display:block;overflow-wrap:anywhere;font-family:Consolas,monospace;font-size:12px}.check-values{color:#43644b}.ring-cards{display:flex;gap:10px;flex-wrap:wrap}.ring-card{background:#eff7f1;border:1px solid #a8c4af;padding:10px;flex:1;min-width:160px}.ring-card b{display:block;font-size:22px}@media print{details{break-inside:avoid}summary{font-weight:bold}.plotly-graph-div{break-inside:avoid}}'''
EQUATION_STYLE=STYLE
def esc(s): return escape(str(s))
def fmt(v): return '—' if v is None else f'{v:.4g}' if isinstance(v,(int,float)) else esc(v)
def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'


def check_steps(r,check):
    ledger={n['name']:n for n in r['nodes']};seen=set();out=[]
    def visit(name):
        if name in seen or name not in ledger:return
        seen.add(name);item=ledger[name]
        for token in ast.walk(ast.parse(item['expr'],mode='eval')):
            if isinstance(token,ast.Name):visit(token.id)
        out.append(item)
    visit(check['demand_node']);visit(check['capacity_node'])
    return out


def check_details(r,c):
    values={n['name']:n['value'] for n in r['nodes']}
    parts=['<details><summary>Equation &amp; values</summary>']
    for item in check_steps(r,c):
        sub=re.sub(r'\b[A-Za-z_]\w*\b',lambda m:'('+format(values[m[0]],'.9g')+')' if m[0] in values else m[0],item['expr'])
        parts.append('<p>'+esc(item['label'])+'<span class="check-formula">'+esc(item['name']+' = '+item['expr'])+'</span><span class="check-values">'+esc(sub)+' = '+fmt(item['value'])+' '+esc(item['unit'])+'</span></p>')
    parts.append('<b>Demand '+fmt(c['demand'])+' / capacity '+fmt(c['capacity'])+' '+esc(c['unit'])+'; D/C '+fmt(c['ratio'])+'</b>')
    if c['capacity']<=0:parts.append('<p>Nonpositive available capacity/clearance: D/C is undefined; check fails.</p>')
    parts.append('<p>'+esc(c['ref'])+' · '+esc(c['note'])+'</p></details>')
    return ''.join(parts)


SOURCES=[('AASHTO LRFD BDS, 10th edition (2024)','https://store.transportation.org/Item/PublicationDetail?ID=5377'),
 ('FDOT Structures Manual, current release','https://www.fdot.gov/Structures/StructuresManual/CurrentRelease'),
 ('FHWA GEC 10: concrete bearing (Chapter 12)','https://www.fhwa.dot.gov/engineering/geotech/nhi18024.pdf'),
 ('Caltrans Bridge Design Practice 6.2: AASHTO fillet welds','https://dot.ca.gov/-/media/dot-media/programs/engineering/documents/bridge-design-practices/202210bdpchapter62steelplategirdersa11y.pdf')]


def render_report(r):
    from .calculation_report import render_report as grouped_report
    return grouped_report(r)


def case_hash(r):return hashlib.sha256(json.dumps(r['case'],sort_keys=True,allow_nan=False).encode()).hexdigest()
def source_files():
    root=Path(__file__).resolve().parents[1]
    files=list(Path(__file__).parent.rglob('*.py'))
    files += [Path(__file__).parent/'_native'/'PROVENANCE.json']
    return sorted(files)
def source_hash():
    root=Path(__file__).resolve().parents[1];h=hashlib.sha256()
    for path in source_files():h.update(path.relative_to(root).as_posix().encode()+b'\0'+path.read_bytes())
    return h.hexdigest()


def native_sheets(r):
    """Real formula-based XMCD and BPAD, independently evaluated before export.

Scalar values use the explicitly declared fixed units shown in every caption;
no unit-aware/native-app validation is claimed. Short identifiers fit the page.
"""
    from ._native import mathcad_sheet as ms, bpad_sheet as bs
    aliases={item['name']:f'v_{i:04d}' for i,item in enumerate(r['nodes'],1)}
    def expr(s):return re.sub(r'\b[A-Za-z_]\w*\b',lambda m:aliases.get(m[0],m[0]),s)
    title='Wall steel and annular pile rings'
    intro=('Fixed scalar units: inches, kip, ksi, with density in kip/ft^3 and areas per foot as labeled. '
        'Units are labels, not native dimensional quantities. This sheet recomputes the exported topology. '
        'Regenerate after changing pile/row counts, bar size/coating, automatic spacing, or contact assumptions. '
        'Two continuous top/bottom fillets. Values are not design acceptance. Case '+case_hash(r)[:12]+'.')
    blocks=[ms.H1(title),ms.P(intro)]
    doc=bs.new_document();rep=bs.new_report(doc,'WallRingDesign',title);bs.heading(rep,title);bs.note(rep,intro)
    for key,text in r['pending']:blocks.append(ms.P(key+': '+text));bs.note(rep,key+': '+text)
    for item in r['nodes']:
        name=aliases[item['name']];expression=expr(item['expr']);caption=item['label']+' ['+item['unit']+']'
        blocks.append(ms.EQ(ms.E(name,expression,caption=caption)))
        bs.equation(rep,name+' = '+bs.bp_formula(ms.parse(expression)),caption)
    # Native statuses explicitly gate local strength checks on the matching contact check.
    for i,c in enumerate(r['checks']):
        d,cap=aliases[c['demand_node']],aliases[c['capacity_node']]
        rawname=f'raw_{i:04d}'
        rawstatus=f'IF({cap}>0,IF({d}<={cap}+1e-9,"PASS","FAIL"),"FAIL")'
        blocks.append(ms.EQ(ms.E(rawname,rawstatus,caption=c['id']+' numerical comparison')))
        bs.equation(rep,rawname+' = '+bs.bp_formula(ms.parse(rawstatus)),c['id']+' numerical comparison')
        status=rawname
        match=re.match(r'R(\d+)-P(\d+)-',c['id'])
        if match and not c['id'].endswith('-CONTACT'):
            qmin=aliases[f'ring_{match[1]}_{match[2]}_qmin']
            status=f'IF({qmin}>=-1e-10,{rawname},"PENDING")'
        name=f'check_{i:04d}';blocks.append(ms.EQ(ms.E(name,status,caption=c['id']+' · '+c['title']+' · '+c['ref'])))
        bs.equation(rep,name+' = '+bs.bp_formula(ms.parse(status)),c['id']+' · '+c['title']+' · '+c['ref'])
    env=ms.run(blocks);engine=bs.BpEngine(report='WallRingDesign')
    for dyn in rep.iter('dynexp'):engine.add(dyn.get('formula'))
    engine.all()
    for item in r['nodes']:
        name=aliases[item['name']];want=item['value']
        for got in (env[name].v,engine.get(name).v):
            if abs(got-want)>1e-9*max(1,abs(want)):raise AssertionError('Native formula mismatch: '+item['name'])
    for i,c in enumerate(r['checks']):
        if env[f'check_{i:04d}']!=c['status'] or engine.get(f'check_{i:04d}')!=c['status']:
            raise AssertionError('Native status mismatch: '+c['id'])
    bs.write_caches(rep,engine,'WallRingDesign')
    xmcd=ms.document(blocks,title=title,description=intro,seed=987124,figures_dir=Path(__file__).parent,check_width=True).encode()
    bpad=bs.serialize(doc)
    verification=dict(case_sha256=case_hash(r),source_sha256=source_hash(),numeric_values=len(r['nodes']),check_statuses=len(r['checks']),
        tolerance=1e-9,mathcad_sha256=hashlib.sha256(xmcd).hexdigest(),bpad_sha256=hashlib.sha256(bpad).hexdigest(),
        native_application_recalculation=False,units='Fixed scalar units, labeled; not dimensionally evaluated',status='FORMULA PARITY VERIFIED')
    return {'ring_wall_design.xmcd':xmcd,'Ring Supported Wall Design.bpad':bpad,
        'ring_wall_sheet_verification.json':json.dumps(verification,indent=2).encode()}


def csv_bytes(rows):
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return out.getvalue().encode('utf-8-sig')


def export_results(r,folder):
    from .study import spacing_study
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    def js(obj):return json.dumps(obj,indent=2,allow_nan=False,ensure_ascii=False).encode()
    data={'ring_wall_case.json':js(r['case']),'ring_wall_results.json':js(r),'ring_wall_checks.csv':csv_bytes(r['checks']),
        'ring_wall_ring_forces.csv':csv_bytes(r['rings']),'ring_wall_report.html':render_report(r).encode(),
        'ring_spacing_study.json':js(spacing_study(r['case']))}
    data.update(native_sheets(r))
    root=Path(__file__).resolve().parents[1];source=io.BytesIO()
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for path in source_files():z.write(path,path.relative_to(root).as_posix())
        z.writestr('README.txt','Calculation source snapshot. Python dependencies: ipywidgets, plotly, anywidget (Plotly 6), lxml. Load ring_wall_case.json and call ring_wall.model.analyze(case).')
    data['ring_wall_source.zip']=source.getvalue()
    data['ring_wall_export_manifest.json']=js(dict(case_sha256=case_hash(r),source_sha256=source_hash(),files={k:hashlib.sha256(v).hexdigest() for k,v in data.items()}))
    for name,content in data.items():(folder/name).write_bytes(content)
    with zipfile.ZipFile(folder/'Ring_Wall_Design_Exports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,content in data.items():z.writestr(name,content)
    return [folder/name for name in data]+[folder/'Ring_Wall_Design_Exports.zip']
