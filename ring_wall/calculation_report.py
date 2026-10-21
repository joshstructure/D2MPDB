"""Grouped check methods, ledger-derived MathML, sketches and complete result tables."""
from collections import Counter
import re
from .notation import dependencies, expression, fraction, math, number, stem, symbol, term
from .output import STYLE, SOURCES, WELD_SIZE_NODES, case_hash, esc, fmt, frac16, source_hash, table
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
 ('loads','Tributary self-weight',(),
  'Allocate the gross wall prism between pile/row midplanes and wall edges as vertical force. The centroid offset is retained for whole-wall equilibrium and shown against the superseded basis; the wall carries it, not the ring (D-070).',
  ['@width','$height','@volume','@service','@force','@eccentricity','@superseded_moment']),
 ('compatibility','Pile-head compatibility moment and tolerance redistribution',(),
  'Rotate the rigid wall on the axial and rotational springs of the pile heads with the pile group displaced by the placement tolerance. The pile-head moment is shared by the ring rows and the axial redistribution adds to each ring reaction.',
  ['pipe_inner_radius','pipe_area','pipe_inertia','pile_axial_stiffness','pile_rotational_stiffness','group_centroid','group_second_moment','tolerance_rotation','wall_rotation','pile_head_moment','ring_moment','$share','@tolerance_force','@design_force','@equivalent_e']),
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
  'Distribute the design reaction and the compatibility ring moment over the horizontal annulus. A negative minimum pressure invalidates the full-contact strength model.',
  ['pipe_radius','inner_radius','outer_radius','bearing_inner','bearing_area','bearing_inertia','kern_limit','@qavg','@qmoment','@qmax','@qmin']),
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
  ['root_gap','@weld_radial','@weld_resultant','weld_throat','weld_capacity','@weld_strength_leg','@weld_required','@weld_sixteenths','@weld_required_16']),
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
.box{border:1px solid;border-radius:3px;margin:8px 0 12px;padding:0}.box>.hd{padding:5px 10px;font:bold 13px Arial,sans-serif}.box>.bd{padding:8px 10px}.box>.bd>p{margin:6px 0}
.discussion{border-color:#7189a6;background:#f1f5fa}.discussion>.hd{background:#dce7f3}.inputs{border-color:#a78638;background:#fff8e9}.inputs>.hd{background:#f7e6b9}.outputs{border-color:#6a9075;background:#eff7f1}.outputs>.hd{background:#dcece0}
.flow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font:12px Arial,sans-serif;margin:8px 0}.flow span{border:1px solid #7189a6;background:#fff;border-radius:3px;padding:4px 7px}.flow b{color:#7189a6}
.contents{margin:18px 0;padding:10px 14px;background:#f1f5fa;border:1px solid #c9d3dc;border-radius:3px;font-family:Arial,sans-serif}.contents h2{margin:0 0 8px;font-size:16px}.contents ul{columns:2;column-gap:24px;list-style:none;margin:0;padding:0}.contents li{break-inside:avoid;margin:0 0 5px}.contents a{color:#245c85;text-decoration:none}
.check-family.front{border-top:2px solid #c1d1df}.check-family.front>summary{font-size:22px}.basis-table td:first-child{white-space:nowrap;font-weight:600}
@media(max-width:700px){main{margin:0;padding:22px 16px}.contents ul{columns:1}h1{font-size:26px}.toolbar span{display:none}.check-family>summary{font-size:19px}.equation-line math{font-size:16px}}
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
    if key in ('eccentricity','superseded_moment'):return 'eccentricity'
    if key in ('qavg','qmoment','qmax','qmin') or group=='bearing':return 'pressure'
    if group=='contact':return 'annulus'
    return {'loads':'tributary','compatibility':'compatibility','steel':'grid','spacing':'grid','cover':'clearance','development':'lap','bar-fit':'lap',
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
        example=next(a for a in r['rings'] if (a['row'],a['pile'])==tuple(map(int,match.groups()))) if match else max(r['rings'],key=lambda a:(a['e_equivalent'],a['R_design']))
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
        formula=expression(source);numeric=expression(source,self.values);weld=stem(name) in WELD_SIZE_NODES
        if not comparison:
            formula=symbol(name)+'<mo>=</mo>'+formula
            numeric=symbol(name)+'<mo>=</mo>'+numeric+'<mo>=</mo>'+(fraction(item['value']) if weld else number(item['value']))+'<mspace width="0.3em"/><mtext>'+esc(unit)+'</mtext>'
        operands=[]
        for dep in dependencies(source):
            n=self.nodes[dep]
            operands.append([math(symbol(dep)),esc(term(dep)[1]),frac16(n['value']) if stem(dep) in WELD_SIZE_NODES else fmt(n['value']),esc(n['unit'])])
        caption='Fixed units shown below; constants use the inch–kip–ksi convention. Values are rounded for display only; weld sizes are shown in sixteenths of an inch.'
        if comparison:
            result=badge(c['status'])+' · D/C '+fmt(c['ratio'])+(' · '+frac16(c['demand'])+' ≤ '+frac16(c['capacity'])+' in' if weld else '')
            if c['capacity']<=0:caption+=' Nonpositive available capacity/clearance: D/C is undefined and the check fails.'
            if c['status']=='PENDING':caption+=' Contact fails: the numerical inequality is trial only and cannot establish a pass.'
            reference='<p class="caption">'+esc(c['ref'])+'</p>'
        else:
            result=math(symbol(name)+'<mo>=</mo>'+(fraction(item['value']) if weld else number(item['value'])))+' '+esc(unit);reference=''
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
            show=frac16 if stem(c['demand_node']) in WELD_SIZE_NODES and stem(c['capacity_node']) in WELD_SIZE_NODES else fmt
            body.append('<tr data-check-id="'+esc(c['id'])+'"><td>'+esc(c['id'])+'</td><td>'+esc(c['title'])+'</td><td>'+show(c['demand'])+'</td><td>'+show(c['capacity'])+'</td><td>'+esc(c['unit'])+'</td><td>'+fmt(c['ratio'])+'</td><td>'+badge(c['status'])+'</td></tr>')
        return '<div class="table-scroll"><table class="result-table"><thead><tr>'+''.join('<th>'+x+'</th>' for x in ['Location / check','Check','Demand','Capacity','Unit','D/C','Status'])+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></div>'

    def family(self,g):
        example=g['example'];key=g['key'];checks=g['checks'];stats=Counter(c['status'] for c in checks)
        counts=' · '.join(f'{v} {k.lower()}' for k,v in stats.items()) or f'{len(self.r["rings"])} rings'
        pieces=['<details class="check-family" id="method-'+key+'"'+(' open' if key=='loads' else '')+'><summary>'+esc(g['title'])+'<small>'+esc(counts)+'</small></summary>',
            '<p class="objective">'+esc(g['idea'])+'</p>']
        if key in ('loads','compatibility','contact','bearing','plate','shear','weld','base','sizes'):
            label=f'Worked example: R{example["row"]} / P{example["pile"]}.'
            if g['representative']:
                label+=' Largest displayed D/C in this family (first in a tie); '+g['representative']['status']+'.'
            if not example['contact_ok']:label+=' Full contact fails here; local strength and sizing values are trial only.'
            label+=' Equations are shown once; every location is listed below.'
            pieces.append('<p class="worked">'+esc(label)+'</p>')
        if key in ('bearing','plate','shear','weld','base','sizes'):
            pieces.append('<p class="method-links">Upstream methods: <a href="#method-loads">tributary self-weight</a> · <a href="#method-compatibility">compatibility moment and redistribution</a> · <a href="#method-contact">contact pressure and annular geometry</a>. The operands below use this family’s labeled worked example.</p>')
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
            pieces.append('<div class="table-scroll">'+table(['Ring','b × h (in)','V (ft³)','W / R (kip)','e_n (in)','M_s superseded (kip-in)'],[
                [f'R{a["row"]}-P{a["pile"]}',fmt(a['width'])+' × '+fmt(a['height']),fmt(a['volume_ft3']),fmt(a['service'])+' / '+fmt(a['R']),fmt(a['e_nominal']),fmt(a['M_superseded'])] for a in self.r['rings']])+'</div>')
            pieces.append('<p>Force residual: '+fmt(self.r['totals']['force_error'])+' kip. Nominal moment residual: '+fmt(self.r['totals']['moment_error'])+' kip-in. The superseded column is the former R (|e_n| + Δ_p) ring moment, kept for comparison with the compatibility moment below (D-070).</p>')
        elif key=='compatibility':
            t=self.r['totals']
            pieces.append('<div class="table-scroll">'+table(['Ring','R (kip)','ΔR (kip)','R_d (kip)','M (kip-in)','e_eq (in)','e_k kern (in)','Contact'],[
                [f'R{a["row"]}-P{a["pile"]}',fmt(a['R']),fmt(a['dR']),fmt(a['R_design']),fmt(a['M']),fmt(a['e_equivalent']),fmt(t['kern_limit']),badge('PASS' if a['contact_ok'] else 'FAIL')] for a in self.r['rings']])+'</div>')
            pieces.append('<p>Wall rotation '+fmt(t['wall_rotation'])+' rad; pile-head moment '+fmt(t['pile_head_moment'])+' kip-in shared by '+str(self.r['case']['ring_count'])+' ring rows. ΔR is added with the sign that increases each ring reaction; whole-wall equilibrium is kept by the nominal tributary forces above.</p>')
        elif key=='sizes':
            pieces.append('<div class="table-scroll">'+table(['Ring','t from bending (in)','Trial t required (in)','Provided t (in)','Strength + minimum leg (in)','Trial weld, next 1/16 (in)','Provided weld (in)','Contact'],[
                [f'R{a["row"]}-P{a["pile"]}',fmt(a['t_bending_req']),fmt(a['t_req']),fmt(self.r['case']['ring_t_in']),fmt(a['weld_req_raw']),frac16(a['weld_req']),frac16(self.r['case']['weld_leg_in']),badge('PASS' if a['contact_ok'] else 'FAIL')] for a in self.r['rings']])+'</div>')
            pieces.append('<p class="scope">Sizes are not an acceptance summary. Weld legs are specified in sixteenths of an inch: the trial leg is the strength-plus-minimum value rounded up to the next 1/16 in. Contact must pass and all cover, clearance, steel, plate, weld and base-metal checks must be resolved before adoption.</p>')
        else:pieces.append(self.result_table(checks))
        for note in dict.fromkeys(c['note'] for c in checks if c['note']):pieces.append('<p class="scope">'+esc(note)+'</p>')
        if any(c['capacity']<=0 for c in checks):pieces.append('<p class="scope">Nonpositive available clearance/capacity fails; its D/C is shown as —.</p>')
        pieces.append('</details>')
        return ''.join(pieces)


def box(kind,title,body):return '<div class="box '+kind+'"><div class="hd">'+esc(title)+'</div><div class="bd">'+body+'</div></div>'


def front_section(key,title,body):
    return '<details class="check-family front" id="'+key+'" open><summary>'+esc(title)+'</summary>'+body+'</details>'


def overview_html(r):
    """Objective, load path and scope, in the form the pile and backwall reports open with."""
    p=r['case'];t=r['totals']
    flow=' <b>→</b> '.join('<span>'+s+'</span>' for s in ('Tributary self-weight','Pile-head compatibility moment','Annular contact','Bearing, plate, welds, base metal','Minimum wall steel and detailing','Check register'))
    objective=('<p>Design the welded annular pile rings that carry the self-weight of a '+fmt(p['length_in'])+' × '+fmt(p['thickness_in'])+' × '+fmt(p['height_in'])+' in concrete wall onto '
        +str(p['pile_count'])+' steel pipe piles of '+fmt(p['pile_od_in'])+' in diameter, and provide the minimum shrinkage/temperature reinforcement and detailing of the wall. '
        'Each pile carries '+str(p['ring_count'])+' rows of annular plates welded with continuous fillets above and below; the wall concrete bears on the plates. '
        'The calculation checks full annular compression contact, concrete bearing, plate bending and shear at the pipe face, both fillets and the adjacent ring and pipe base metal, then the wall grid area, spacing, cover, laps and bar fit.</p>'
        '<div class="flow">'+flow+'</div>'
        '<p><b>Load path.</b> The gross wall prism is divided at midplanes between piles and between ring rows, clipped at the wall edges, and each cell’s factored weight is the vertical force on its ring. '
        'The wall is a continuous stiff body, so the offset of a cell centroid from its pile is carried by the wall, not by the ring. The ring moment is the compatibility moment of the pile head: '
        'the rigid wall rotates on the axial and rotational springs of the pile heads when the pile group is displaced by the radial placement tolerance, every pile head carries '
        'k<sub>θ</sub> θ<sub>w</sub>, the ring rows share it equally, and the axial redistribution ΔR is added to each tributary reaction (decision D-070, 21 October 2026). '
        'The superseded basis, R (|e<sub>n</sub>| + Δ<sub>p</sub>) at every ring, is tabulated beside it for comparison only.</p>'
        '<p><b>Outside this calculation:</b> wall flexure, shear and lateral or seismic load paths; concrete splitting, breakout and the transfer below the lowest ring; pipe-shell bending and ovalization; '
        'global pile interaction, ring-segment splices, fatigue, corrosion and WPS or fabrication acceptance; confirmation of the pile stiffness lengths. These stay as open items in the register below.</p>'
        '<p>Equations are rendered from the evaluated ledger. Every equation has a <b>Numeric substitution and schematic</b> dropdown with a mechanics sketch, the current operands and the numbers substituted; '
        'hovering a symbol opens its definition card. This report is a calculation record, not engineering acceptance.</p>')
    return front_section('overview','Overview',box('discussion','Objective, method and scope',objective))


def basis_html(r):
    p=r['case'];t=r['totals']
    codes=('<p>AASHTO LRFD Bridge Design Specifications, 10th edition (2024): concrete bearing LRFD 5.6.5 with the resistance factor of 5.5.4.2 and no supporting-area enhancement (m = 1); '
        'minimum shrinkage and temperature reinforcement LRFD 5.10.6; bar spacing and clear spacing 5.10.3.1.1 and 5.10.3.2; bend diameter 5.10.2; development and Class B laps 5.10.8.2.1 and 5.10.8.4.3; '
        'fillet weld resistance, minimum and maximum size and length LRFD 6.13.3.2.4, 6.13.3.4 and 6.13.3.5; shear yielding and rupture of the adjacent ring and pipe metal 6.13.5.2 and 6.13.5.3; '
        'steel resistance factors LRFD 6.5.4.2; depth to fixity of the default pile free length LRFD 10.7.3.13.4. Project cover, grid pitch cap and exposure follow the entered values and the FDOT Structures Manual.</p>'
        '<p>Units are inches, kip and ksi; concrete density in kip/ft³; rotations in radians. Ring elevations locate the plate top above the wall bottom. Bearing excludes the footprint of the upper fillet; '
        'the peak pressure is applied over the whole radial cantilever strip; the two fillets form a couple over the plate thickness. A ring whose minimum pressure is negative loses full contact, and its bearing, plate, weld and base-metal checks are reported <b>PENDING</b> with trial values.</p>')
    phi=', '.join(f'{label} {p[key]:g}' for label,key in (('bearing φ<sub>b</sub>','phi_concrete'),('plate flexure φ<sub>f</sub>','phi_plate'),('weld φ<sub>w</sub>','phi_weld'),('shear yielding φ<sub>vy</sub>','phi_shear_yield'),('shear rupture φ<sub>vu</sub>','phi_shear_rupture')))
    rows=[['Wall',f'{p["length_in"]:g} in long × {p["thickness_in"]:g} in thick × {p["height_in"]:g} in high; concrete f′c {p["fc_ksi"]:g} ksi, {p["density_kcf"]:g} kcf, γ<sub>DC</sub> {p["gamma_dc"]:g}','Earlier study snapshot; confirm against current geometry (BASIS)'],
        ['Piles',f'{p["pile_count"]} pipe piles at {p["pile_spacing_in"]:g} in, OD {p["pile_od_in"]:g} in, effective wall {p["pile_t_effective_in"]:g} in, Fy {p["pile_fy_ksi"]:g} / Fu {p["pile_fu_ksi"]:g} ksi; radial placement tolerance {p["placement_tolerance_in"]:g} in','Entered'],
        ['Pile stiffness',f'E {p["pile_e_ksi"]:g} ksi; wall bottom to equivalent fixity {p["pile_free_length_in"]:g} in; axial spring length {p["pile_axial_length_in"]:g} in; imposed wall rotation {p["imposed_rotation_rad"]:g} rad','Defaults from the pier pile case (sand depth to fixity); tip elevation pending (STIFFNESS)'],
        ['Annular rings',f'{p["ring_count"]} rows, first plate top {p["first_ring_in"]:g} in above the bottom at {p["ring_spacing_in"]:g} in pitch; OD {p["ring_od_in"]:g} / ID {p["ring_id_in"]:g} in × {p["ring_t_in"]:g} in; Fy {p["ring_fy_ksi"]:g} / Fu {p["ring_fu_ksi"]:g} ksi','Trial sizes; recalculate after selection'],
        ['Fillet welds',f'two continuous fillets per ring, leg {frac16(p["weld_leg_in"])} in, F<sub>EXX</sub> {p["weld_fexx_ksi"]:g} ksi; radial root gap {frac16((p["ring_id_in"]-p["pile_od_in"])/2)} in','Trial size in sixteenths of an inch; WPS must accept the radial root gap'],
        ['Wall reinforcement',f'#{p["grid_bar"]} grid each way on each broad face, fy {p["fy_ksi"]:g} ksi, {p["coating"]} bars; cover {p["cover_in"]:g} in provided / {p["required_cover_in"]:g} in required; aggregate {p["aggregate_in"]:g} in; project pitch cap {p["project_max_spacing_in"]:g} in; U leg {p["u_leg_in"]:g} in, vertical lap allowance {p["vertical_lap_in"]:g} in','Pitch '+('selected automatically' if p['auto_grid_spacing'] else f'entered as {p["grid_spacing_in"]:g} in')],
        ['Resistance factors',phi,'LRFD 5.5.4.2 and 6.5.4.2; visible inputs']]
    inputs='<div class="table-scroll"><table class="basis-table"><thead><tr><th>Item</th><th>Current case</th><th>Source / status</th></tr></thead><tbody>'+''.join('<tr><td>'+a+'</td><td>'+b+'</td><td>'+c+'</td></tr>' for a,b,c in rows)+'</tbody></table></div>'
    legend='<p><span class="badge PASS">PASS</span> demand ≤ capacity · <span class="badge FAIL">FAIL</span> demand exceeds capacity or the available clearance is not positive · <span class="badge PENDING">PENDING</span> the ring has lost full contact, so the local strength value is a trial and cannot establish a pass.</p>'
    return front_section('basis','Design basis and inputs',box('discussion','Codes, assumptions and conventions',codes)+box('inputs','Case inputs',inputs+'<p class="caption">The complete input list with every value is at the end of the report.</p>')+box('discussion','Check status',legend))


def results_html(r):
    from . import plots as V
    p=r['case'];t=r['totals'];rings=r['rings'];checks=r['checks'];stats=Counter(c['status'] for c in checks)
    worst=max(rings,key=lambda a:a['e_equivalent']);qring=max(rings,key=lambda a:a['qmax']);qR=next(n['value'] for n in r['nodes'] if n['name']=='bearing_limit')
    rows=[['Factored wall self-weight',fmt(t['factored_weight'])+' kip (service '+fmt(t['service_weight'])+' kip); force and nominal moment residuals '+fmt(t['force_error'])+' kip, '+fmt(t['moment_error'])+' kip-in'],
        ['Wall rotation and pile-head moment',fmt(t['wall_rotation'])+' rad; '+fmt(t['pile_head_moment'])+' kip-in per pile head; '+fmt(t['ring_moment'])+' kip-in per ring'],
        ['Full contact',f'largest equivalent eccentricity {fmt(worst["e_equivalent"])} in at R{worst["row"]}/P{worst["pile"]} against the {fmt(t["kern_limit"])}-in kern; '+str(sum(not a['contact_ok'] for a in rings))+' of '+str(len(rings))+' rings lose contact'],
        ['Peak bearing',f'q<sub>max</sub> {fmt(qring["qmax"])} ksi at R{qring["row"]}/P{qring["pile"]} against q<sub>R</sub> {fmt(qR)} ksi'],
        ['Largest design ring load',fmt(max(a['R_design'] for a in rings))+' kip (tributary '+fmt(max(a['R'] for a in rings))+' kip plus redistribution up to '+fmt(max(a['dR'] for a in rings))+' kip)'],
        ['Weld leg',f'{frac16(p["weld_leg_in"])} in provided; largest trial requirement {frac16(max(a["weld_req"] for a in rings))} in (next sixteenth above {fmt(max(a["weld_req_raw"] for a in rings))} in)'],
        ['Wall reinforcement',f'#{r["grid"]["bar"]} at {r["grid"]["spacing"]:g} in each way on each face, {fmt(r["grid"]["provided"])} in²/ft provided against {fmt(r["grid"]["required"])} in²/ft required'],
        ['Check register',' · '.join(f'{v} {k}' for k,v in stats.items())+'; failures: '+(', '.join(c['id'] for c in checks if c['status']=='FAIL') or 'none')]]
    return front_section('results','Result summary',V.note(esc(r['overall']),True)+V.summary(r)+box('outputs','Key results',table(['Result','Current case'],rows)))


def render_report(r):
    from . import plots as V
    report=Report(r);groups=list(families(r))
    contents=[('overview','Overview'),('basis','Design basis and inputs'),('results','Result summary'),('methods','Check methods and result index'),('geometry','Geometry and reinforcement drawings'),('scope','Scope and unresolved design items'),('inputs','Case inputs and references')]
    pieces=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wall steel and annular rings — calculation report</title><style>'+CSS+'</style></head><body>',
        '<nav class="toolbar" aria-label="Report controls"><a href="#overview">Overview</a><a href="#basis">Design basis</a><a href="#methods">Check methods</a><a href="#geometry">Geometry</a><button id="expand-methods">Expand methods</button><button id="expand-equations">Expand schematics</button><button id="collapse-details">Collapse details</button><button id="print-report">Print / save PDF</button><span>Offline calculation report</span></nav><main>',
        '<p class="eyebrow">D2 DESIGN NOTEBOOK · WALL STEEL / ANNULAR PILE RINGS</p><h1>'+esc(r['case']['title'])+'</h1>',
        '<p class="lead">Read the overview and design basis first, understand each check once, then review every location. Open an equation’s dropdown for its schematic, current operands and numerical substitution.</p>',
        '<nav class="contents" aria-label="Table of contents"><h2>Contents</h2><ul>'+''.join('<li><a href="#'+k+'">'+esc(v)+'</a></li>' for k,v in contents)+'</ul></nav>',
        overview_html(r),basis_html(r),results_html(r),
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
    pieces.extend(['</details><h2 id="scope">Scope and unresolved design items</h2>',table(['Item','Required follow-through'],[[esc(k),esc(v)] for k,v in r['pending']]),
        '<details class="check-family" id="inputs"><summary>Case inputs and references</summary>',table(['Input','Value'],[[esc(k),esc(v)] for k,v in r['case'].items()]),
        '<p>'+'; '.join('<a href="'+url+'">'+esc(label)+'</a>' for label,url in SOURCES)+'</p></details>',
        '<p class="footer-note">Equations are rendered directly from the evaluated calculation ledger; native MathML and SVG need no network connection. Schematics explain mechanics and are not fabrication drawings. Native worksheets retain the exported topology and labeled scalar units; formula parity is not native application recalculation or engineering acceptance.</p>',
        '<p class="footer-note">Case SHA-256: '+case_hash(r)+'<br>Source SHA-256: '+source_hash()+'</p></main><script>'+JS+'</script>'])
    body=''.join(pieces)
    # Definition cards for every data-var symbol; citation cards for the code references in the check captions.
    return body+cards_html(cite_data(None,extra_pieces=prose_pieces(body)))+'</body></html>'
