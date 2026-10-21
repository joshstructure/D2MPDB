"""Grouped check methods, ledger-derived MathML, sketches and complete result tables."""
from collections import Counter
import re
from .notation import dependencies, expression, math, number, stem, symbol, term
from .output import STYLE, SOURCES, case_hash, esc, fmt, source_hash, table
from .schematics import schematic
try:
    from report_cards import cards_html, cite_data, prose_pieces
except ImportError:  # portable package built without the cards module
    def cards_html(cites=None):
        return ''

    def cite_data(references=None, extra_pieces=(), **_):
        return None

    def prose_pieces(text):
        return []


# Each check belongs to exactly one method. Repeated ring checks share one example.
GROUPS = [
 ('loads','Tributary self-weight and eccentricity',(),
  'Allocate the gross wall prism between pile/row midplanes and wall edges; carry its centroid offset into the local connection.',
  ['@width','$height','@volume','@service','@force','@eccentricity','@design_e','@moment']),
 ('steel','Minimum wall reinforcement',('GRID-A',),
  'Calculate the minimum area from both gross wall sections and provide the larger amount each way on each face.',
  ['steel_L','steel_H','steel_required','steel_provided']),
 ('spacing','Grid spacing and aggregate clearance',('GRID-S','GRID-CLEAR'),
  'Limit bar center spacing and leave enough clear space between neighboring bars for placement.',
  ['code_pitch','pitch_limit','clear_required','clear_provided']),
 ('cover','Concrete cover',('COVER',),
  'Compare the provided cover with the entered project exposure requirement.',[]),
 ('development','Development and Class B laps',('U-LAP','V-LAP'),
  'Develop bar force through the surrounding concrete and provide the corresponding horizontal/vertical lap allowance.',
  ['ld_basic','ld_horizontal','ld_vertical','lap_horizontal','lap_vertical']),
 ('bar-fit','U-bar and vertical-lap fit',('U-FIT','U-BEND','V-FIT'),
  'Fit the selected straight legs, lap allowance and bend envelope within the concrete cover lines.',
  ['u_leg_available','bend_envelope','u_width','vertical_available']),
 ('clearances','Ring cover and cage clearance',('RING-END','RING-FACE','RING-GRID','RING-BOTTOM','RING-TOP','RING-SPACING'),
  'Check the ring and fillets against wall surfaces, face reinforcement and neighboring rings at the entered placement tolerance.',
  ['end_offset','end_clear','face_clear','grid_gap','ring_grid_required','bottom_ring_cover','top_ring_cover','between_rings']),
 ('weld-detail','Fillet weld detailing',('WELD-MIN','WELD-MAX','WELD-LENGTH'),
  'Select a fabricable weld leg and continuous length using joined-part thickness, free-edge and fit-up allowances.',
  ['thicker_part','minimum_thick_weld','minimum_mid_weld','minimum_table_weld','weld_minimum','weld_min_gap','weld_maximum','weld_length','weld_length_min']),
 ('contact','Annular area and full compression contact',('CONTACT',),
  'Distribute reaction and eccentric moment over the horizontal annulus. A negative minimum pressure invalidates the full-contact strength model.',
  ['pipe_radius','inner_radius','outer_radius','bearing_inner','bearing_area','bearing_inertia','@qavg','@qmoment','@qmax','@qmin']),
 ('bearing','Concrete bearing strength',('BEAR',),
  'Compare the peak compressive pressure with factored concrete bearing resistance, without supporting-area enhancement.',
  ['bearing_limit']),
 ('plate','Ring plate bending',('PLATE',),
  'Treat the radial projection as an elastic cantilever. Apply the peak pressure along the full bearing width conservatively.',
  ['@root_moment','plate_capacity','@thickness_bending']),
 ('shear','Ring plate shear',('SHEAR',),
  'Integrate the vertical load over the radial strip and check yielding through the plate thickness at the pipe face.',
  ['@root_shear','plate_shear_capacity','@thickness_shear']),
 ('weld','Top and bottom fillet weld strength',('WELD',),
  'Split vertical shear between two fillets and use their radial force couple to resist plate-root moment. Check the resultant in each weld.',
  ['root_gap','@weld_radial','@weld_resultant','weld_throat','weld_capacity','@weld_strength_leg','@weld_required']),
 ('base','Adjacent ring and pipe base metal',('RING-BASE','PIPE-YIELD','PIPE-BASE'),
  'Compare the force transferred by each fillet with adjacent ring/pipe shear resistance. Local pipe-shell bending remains outside this check.',
  ['ring_base_capacity','pipe_yield_capacity','pipe_base_capacity']),
 ('sizes','Trial plate and weld sizes',(),
  'Collect the controlling strength and detailing sizes. Recalculate after selecting dimensions; contact and fit failures still prevent adoption.',
  ['@thickness_required']),
]

CSS = STYLE + '''
*{box-sizing:border-box}html{scroll-behavior:smooth}body{max-width:none;margin:0;padding:0;background:#eaf0f5;font:15px/1.55 Georgia,"Times New Roman",serif}
main{max-width:1180px;margin:24px auto;padding:32px 44px;background:#fff;box-shadow:0 3px 24px #21364918}
h1{font-size:32px;margin:6px 0 12px}h2{font-size:23px}h3{font-size:19px}.eyebrow,.toolbar,.badge,.method-index,figcaption,.caption{font-family:Arial,sans-serif}
.eyebrow{font-size:11px;letter-spacing:.14em;color:#5e7489}.lead{font-size:18px;max-width:850px}.caption,figcaption{font-size:12px;color:#526b80}
.toolbar{position:sticky;top:0;z-index:20;display:flex;gap:8px;flex-wrap:wrap;background:#213649;padding:10px 20px;color:white;font-size:12px}.toolbar button,.toolbar a{padding:7px 12px;border:1px solid #b5c6d4;border-radius:4px;background:#fff;color:#213649;font:13px Arial,sans-serif;text-decoration:none;cursor:pointer}.toolbar span{margin:auto 0 auto auto}
.badge{font-size:11px;display:inline-block;border-radius:3px;padding:3px 6px;background:#edf3f8}.badge.PASS{background:#e8f4ed}.badge.FAIL{background:#ffedeb}.badge.PENDING{background:#fff1d5}
.check-family{margin:24px 0;border-top:2px solid #c1d1df;border-bottom:0;padding:12px 0;scroll-margin-top:76px}.check-family>summary{font-size:22px;font-weight:bold;color:#244d70;padding:6px 0}.check-family>summary small{display:inline-block;font:12px Arial,sans-serif;margin-left:12px;color:#526b80}
.objective{background:#edf3f8;border-left:4px solid #7899b4;padding:12px 16px}.worked{padding:9px 12px;border-left:3px solid #b47b31;background:#fff7e8;font:13px/1.5 Arial,sans-serif}
.equation{padding:13px 0;border-bottom:1px solid #e0e8ee;scroll-margin-top:78px}.equation h4{margin:0;font:600 14px Arial,sans-serif;color:#315d82}.equation-line{overflow-x:auto;padding:12px 4px}.equation-line math{font-size:19px}.equation-number{float:right;font:11px Arial,sans-serif;color:#637e94}
math{font-family:"Cambria Math","STIX Two Math",math}math[display=block]{text-align:left;width:max-content;max-width:none;margin:0}.equation-working{border-left:3px solid #9db7ce;margin:2px 0 5px;padding:4px 0 4px 14px;border-bottom:0}.equation-working>summary{font:13px Arial,sans-serif;padding:5px 0}
.equation-sketch{margin:12px 0;max-width:900px}.equation-sketch svg{display:block;width:100%;height:auto}.equation-sketch figcaption{margin:6px 0}.operand-table{max-width:920px}.operand-table table{font-size:12px}.operand-table td{background:#fff8e9}.operand-table th{background:#f7e6b9}
.equation-result{background:#eff7f1;border-left:3px solid #8aaa94;padding:7px 12px;display:flex;align-items:center;gap:10px;font-size:13px}.equation-result.trial{background:#fff7e8;border-color:#b57820}.result-table td{background:#f4faf6}.result-table th{background:#dfede3}.table-scroll{overflow-x:auto}th,td{overflow-wrap:anywhere}.method-index td:first-child{font-weight:600}table{font-family:Arial,sans-serif}summary:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid #d79934;outline-offset:3px}.method-links{font:12px Arial,sans-serif;line-height:1.8}.scope{border-left:4px solid #b57820;background:#fff7e8;padding:10px 16px}.footer-note{font:12px/1.5 Arial,sans-serif;overflow-wrap:anywhere}
@media(max-width:700px){main{margin:0;padding:22px 16px}h1{font-size:26px}.toolbar span{display:none}.check-family>summary{font-size:19px}.equation-line math{font-size:16px}}
@media print{body{background:#fff}main{margin:0;padding:0;box-shadow:none}.toolbar{display:none}.check-family{break-inside:auto}.equation{break-inside:auto}details::details-content{display:block!important;content-visibility:visible!important}.equation-sketch{break-inside:avoid}.equation-line{overflow:visible}.equation-line math{font-size:13px}.table-scroll{overflow:visible}thead{display:table-header-group}tr{break-inside:avoid}th,td,.objective,.equation-result{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
'''

JS = '''
const reportDetails=[...document.querySelectorAll('main details')];
function resizePlots(){if(!window.Plotly)return Promise.resolve();return Promise.all([...document.querySelectorAll('.plotly-graph-div')].filter(p=>!p.closest('details:not([open])')).map(p=>Plotly.Plots.resize(p)));}
document.getElementById('expand-methods').onclick=()=>document.querySelectorAll('.check-family[id^="method-"]').forEach(d=>d.open=true);
document.getElementById('expand-equations').onclick=()=>{document.querySelectorAll('.check-family[id^="method-"],.equation-working').forEach(d=>d.open=true);};
document.getElementById('collapse-details').onclick=()=>reportDetails.forEach(d=>d.open=false);
document.addEventListener('toggle',()=>requestAnimationFrame(resizePlots),true);
function reveal(){const el=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(!el)return;for(let p=el;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;requestAnimationFrame(()=>el.scrollIntoView());}
window.addEventListener('hashchange',reveal);reveal();
let savedOpen=null;
function preparePrint(){if(!savedOpen)savedOpen=reportDetails.map(d=>d.open);reportDetails.forEach(d=>d.open=true);return resizePlots();}
window.addEventListener('beforeprint',preparePrint);
window.addEventListener('afterprint',()=>{if(savedOpen){reportDetails.forEach((d,i)=>d.open=savedOpen[i]);savedOpen=null;}});
document.getElementById('print-report').onclick=async()=>{await preparePrint();await new Promise(requestAnimationFrame);window.print();};
'''


def check_type(c):return re.sub(r'^R\d+-P\d+-','',c['id'])


def badge(status):return '<span class="badge '+esc(status)+'">'+esc(status)+'</span>'


def sketch_kind(name,group):
    key=stem(name)
    if key in ('eccentricity','design_e','moment'):return 'eccentricity'
    if key in ('qavg','qmoment','qmax','qmin') or group=='bearing':return 'pressure'
    if group=='contact':return 'annulus'
    return {'loads':'tributary','steel':'grid','spacing':'grid','cover':'clearance','development':'lap','bar-fit':'lap',
            'clearances':'clearance','weld-detail':'weld-detail','plate':'plate','shear':'plate','weld':'weld','base':'base','sizes':'plate'}[group]


def families(r):
    all_types={check_type(c) for c in r['checks']}
    covered=[t for g in GROUPS for t in g[2] if t in all_types]
    if len(covered)!=len(set(covered)) or set(covered)!=all_types:
        raise ValueError('Report check-family coverage is incomplete or duplicated.')
    for key,title,types,idea,names in GROUPS:
        checks=[c for c in r['checks'] if check_type(c) in types]
        if types and not checks:continue
        representative=max(checks,key=lambda c:c['ratio'] if c['ratio'] is not None else float('inf')) if checks else None
        match=re.match(r'R(\d+)-P(\d+)-',representative['id']) if representative else None
        example=next(a for a in r['rings'] if (a['row'],a['pile'])==tuple(map(int,match.groups()))) if match else max(r['rings'],key=lambda a:a['M'])
        prefix=f'ring_{example["row"]}_{example["pile"]}_';row=f'row_{example["row"]}_'
        yield dict(key=key,title=title,types=types,idea=idea,checks=checks,representative=representative,example=example,
                   names=[n.replace('@',prefix).replace('$',row) for n in names])


class Report:
    def __init__(self,r):
        self.r=r;self.nodes={n['name']:n for n in r['nodes']};self.values={k:n['value'] for k,n in self.nodes.items()};self.count=0

    def equation(self,name,group,example,comparison=None):
        if comparison:
            c=comparison;source=c['demand_node']+' <= '+c['capacity_node'];meaning=c['title']+' — demand ≤ capacity';unit=c['unit']
        else:
            item=self.nodes[name];source=item['expr'];meaning=term(name)[1];unit=item['unit']
        self.count+=1;key='eq-'+group+'-'+(check_type(comparison) if comparison else stem(name))
        formula=expression(source);numeric=expression(source,self.values)
        if not comparison:
            formula=symbol(name)+'<mo>=</mo>'+formula
            numeric=symbol(name)+'<mo>=</mo>'+numeric+'<mo>=</mo>'+number(item['value'])+'<mspace width="0.3em"/><mtext>'+esc(unit)+'</mtext>'
        operands=[]
        for dep in dependencies(source):
            n=self.nodes[dep]
            operands.append([math(symbol(dep)),esc(term(dep)[1]),fmt(n['value']),esc(n['unit'])])
        caption='Fixed units shown below; constants use the inch–kip–ksi convention. Values are rounded for display only.'
        if comparison:
            result=badge(c['status'])+' · D/C '+fmt(c['ratio'])
            if c['capacity']<=0:caption+=' Nonpositive available capacity/clearance: D/C is undefined and the check fails.'
            if c['status']=='PENDING':caption+=' Contact fails: the numerical inequality is trial only and cannot establish a pass.'
            reference='<p class="caption">'+esc(c['ref'])+'</p>'
        else:
            result=math(symbol(name)+'<mo>=</mo>'+number(item['value']))+' '+esc(unit);reference=''
        trial=not comparison and name.startswith('ring_') and group in ('contact','plate','shear','weld','base','sizes') and not example['contact_ok']
        if trial:result='Contact failed · trial value: '+result
        return ('<article class="equation" id="'+key+'" data-node="'+esc(name)+'"><span class="equation-number">('+str(self.count)+')</span><h4>'+esc(meaning)+'</h4>'
            '<div class="equation-line">'+math(formula,True)+'</div><details class="equation-working"><summary>Numeric substitution and schematic</summary>'
            +schematic(sketch_kind(name,group),name,self.r,example)+'<div class="equation-line">'+math(numeric,True)+'</div><p class="caption">'+caption+'</p>'
            '<div class="operand-table table-scroll">'+table(['Symbol','What it represents','Current value','Unit'],operands)+'</div></details>'
            '<div class="equation-result'+(' trial' if trial else '')+'">'+result+'</div>'+reference+'</article>')

    def result_table(self,checks):
        body=[]
        for c in checks:
            body.append('<tr data-check-id="'+esc(c['id'])+'"><td>'+esc(c['id'])+'</td><td>'+esc(c['title'])+'</td><td>'+fmt(c['demand'])+'</td><td>'+fmt(c['capacity'])+'</td><td>'+esc(c['unit'])+'</td><td>'+fmt(c['ratio'])+'</td><td>'+badge(c['status'])+'</td></tr>')
        return '<div class="table-scroll"><table class="result-table"><thead><tr>'+''.join('<th>'+x+'</th>' for x in ['Location / check','Check','Demand','Capacity','Unit','D/C','Status'])+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></div>'

    def family(self,g):
        example=g['example'];key=g['key'];checks=g['checks'];stats=Counter(c['status'] for c in checks)
        counts=' · '.join(f'{v} {k.lower()}' for k,v in stats.items()) or f'{len(self.r["rings"])} rings'
        pieces=['<details class="check-family" id="method-'+key+'"'+(' open' if key=='loads' else '')+'><summary>'+esc(g['title'])+'<small>'+esc(counts)+'</small></summary>',
            '<p class="objective">'+esc(g['idea'])+'</p>']
        if key in ('loads','contact','bearing','plate','shear','weld','base','sizes'):
            label=f'Worked example: R{example["row"]} / P{example["pile"]}.'
            if g['representative']:
                label+=' Largest displayed D/C in this family (first in a tie); '+g['representative']['status']+'.'
            if not example['contact_ok']:label+=' Full contact fails here; local strength and sizing values are trial only.'
            label+=' Equations are shown once; every location is listed below.'
            pieces.append('<p class="worked">'+esc(label)+'</p>')
        if key in ('bearing','plate','shear','weld','base','sizes'):
            pieces.append('<p class="method-links">Upstream methods: <a href="#method-loads">tributary actions</a> · <a href="#method-contact">contact pressure and annular geometry</a>. The operands below use this family’s labeled worked example.</p>')
        for name in g['names']:
            if name in self.nodes:pieces.append(self.equation(name,key,example))
            elif name!='between_rings':raise ValueError('Report equation missing: '+name)
        # One acceptance equation per subtype; no per-ring equation repetition.
        for typ in g['types']:
            matches=[c for c in checks if check_type(c)==typ]
            if not matches:continue
            c=next((c for c in matches if c['id'].startswith(f'R{example["row"]}-P{example["pile"]}-')),matches[0])
            pieces.append(self.equation(c['demand_node'],key,example,c))
        pieces.append('<h3>All results · '+esc(g['title'])+'</h3>')
        if key=='loads':
            pieces.append('<div class="table-scroll">'+table(['Ring','b × h (in)','V (ft³)','W / R (kip)','e_n / e_d (in)','M (kip-in)'],[
                [f'R{a["row"]}-P{a["pile"]}',fmt(a['width'])+' × '+fmt(a['height']),fmt(a['volume_ft3']),fmt(a['service'])+' / '+fmt(a['R']),fmt(a['e_nominal'])+' / '+fmt(a['e_design']),fmt(a['M'])] for a in self.r['rings']])+'</div>')
            pieces.append('<p>Force residual: '+fmt(self.r['totals']['force_error'])+' kip. Nominal moment residual: '+fmt(self.r['totals']['moment_error'])+' kip-in. Radial tolerance is a separate local envelope.</p>')
        elif key=='sizes':
            pieces.append('<div class="table-scroll">'+table(['Ring','t from bending (in)','Trial t required (in)','Provided t (in)','Trial weld required (in)','Provided weld (in)','Contact'],[
                [f'R{a["row"]}-P{a["pile"]}',fmt(a['t_bending_req']),fmt(a['t_req']),fmt(self.r['case']['ring_t_in']),fmt(a['weld_req']),fmt(self.r['case']['weld_leg_in']),badge('PASS' if a['contact_ok'] else 'FAIL')] for a in self.r['rings']])+'</div>')
            pieces.append('<p class="scope">Sizes are not an acceptance summary. Contact must pass and all cover, clearance, steel, plate, weld and base-metal checks must be resolved before adoption.</p>')
        else:pieces.append(self.result_table(checks))
        for note in dict.fromkeys(c['note'] for c in checks if c['note']):pieces.append('<p class="scope">'+esc(note)+'</p>')
        if any(c['capacity']<=0 for c in checks):pieces.append('<p class="scope">Nonpositive available clearance/capacity fails; its D/C is shown as —.</p>')
        pieces.append('</details>')
        return ''.join(pieces)


def render_report(r):
    from . import plots as V
    report=Report(r);groups=list(families(r))
    pieces=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wall steel and annular rings — calculation report</title><style>'+CSS+'</style></head><body>',
        '<nav class="toolbar" aria-label="Report controls"><a href="#methods">Check methods</a><a href="#geometry">Geometry</a><button id="expand-methods">Expand methods</button><button id="expand-equations">Expand schematics</button><button id="collapse-details">Collapse details</button><button id="print-report">Print / save PDF</button><span>Offline calculation report</span></nav><main>',
        '<p class="eyebrow">D2 DESIGN NOTEBOOK · WALL STEEL / ANNULAR PILE RINGS</p><h1>'+esc(r['case']['title'])+'</h1>',
        '<p class="lead">Understand each check once, then review every location. Open an equation’s dropdown for its schematic, current operands and numerical substitution.</p>',
        V.note(esc(r['overall']),True),V.summary(r),
        '<p>Concrete self-weight only; two face mats; two continuous top/bottom fillets. Gross volume retains pipe/plate displacement. No STM analysis or supporting-area bearing enhancement is used.</p>',
        '<h2 id="methods">Check methods and result index</h2><p class="caption">Each check appears in one family table. Largest D/C may be a trial value where contact fails; the status column controls.</p>']
    index=[]
    for g in groups:
        stats=Counter(c['status'] for c in g['checks']);ratios=[c['ratio'] for c in g['checks'] if c['ratio'] is not None]
        index.append(['<a href="#method-'+g['key']+'">'+esc(g['title'])+'</a>',len(g['checks']) or 'Load / sizing table',fmt(max(ratios)) if ratios else '—',
                      ' · '.join(badge(k)+' '+str(v) for k,v in stats.items()) or 'Reference values'])
    pieces.append('<div class="method-index table-scroll">'+table(['Method','Checks','Largest D/C','Results'],index)+'</div>')
    pieces.extend(report.family(g) for g in groups)
    pieces.append('<details class="check-family" id="geometry"><summary>Geometry and reinforcement drawings</summary>')
    for title,fig in [('Wall layout',V.layout_figure(r['case'])),('Reinforcement and rings',V.cage_figure(r['case'])),('Ring connection',V.connection_figure(r)),('Ring tributary reactions',V.reaction_figure(r))]:
        pieces.extend(['<h3>'+title+'</h3>',fig.to_html(full_html=False,include_plotlyjs=True if title=='Wall layout' else False,config={'responsive':True,'displaylogo':False})])
    pieces.extend(['</details><h2>Scope and unresolved design items</h2>',table(['Item','Required follow-through'],[[esc(k),esc(v)] for k,v in r['pending']]),
        '<details class="check-family" id="inputs"><summary>Case inputs and references</summary>',table(['Input','Value'],[[esc(k),esc(v)] for k,v in r['case'].items()]),
        '<p>'+'; '.join('<a href="'+url+'">'+esc(label)+'</a>' for label,url in SOURCES)+'</p></details>',
        '<p class="footer-note">Equations are rendered directly from the evaluated calculation ledger; native MathML and SVG need no network connection. Schematics explain mechanics and are not fabrication drawings. Native worksheets retain the exported topology and labeled scalar units; formula parity is not native application recalculation or engineering acceptance.</p>',
        '<p class="footer-note">Case SHA-256: '+case_hash(r)+'<br>Source SHA-256: '+source_hash()+'</p></main><script>'+JS+'</script>'])
    body=''.join(pieces)
    # Definition cards for every data-var symbol; citation cards for the code references in the check captions.
    return body+cards_html(cite_data(None,extra_pieces=prose_pieces(body)))+'</body></html>'
