"""Portable Mathcad-style HTML report: no web scripts or plotting dependencies."""
import csv
import hashlib
import html
import io
import json
from pathlib import Path
from .model import BAR, analyze
from .equations import check_steps, number

EQUATION_STYLE='''
.check-equations .check-step{margin:10px 0;padding:8px 10px;border-left:3px solid #a8c4af;background:#f5f9f6;line-height:1.5;overflow-wrap:anywhere}
.check-equations .check-formula{font-family:"Cambria Math","Times New Roman",serif;font-size:14px;margin:4px 0}
.check-equations .check-values{font-variant-numeric:tabular-nums;color:#213649}
.check-equations .check-ratio{padding:8px 0;font-weight:bold}
'''

STYLE='''
:root{color-scheme:light}body{font-family:"Times New Roman",serif;font-size:11pt;color:#1f2a36;background:#fff;max-width:1100px;margin:24px auto;padding:0 18px;line-height:1.38}
h1{font-size:19pt;margin:4px 0}h2{font-size:14pt;margin:28px 0 8px;border-bottom:2px solid #7189a6;padding-bottom:4px}h3{font-size:12pt;margin:14px 0 6px}
.eyebrow{font-family:Arial,sans-serif;color:#61758a;font-size:9pt;letter-spacing:1.5px}.box{border:1px solid;border-radius:3px;margin:8px 0 12px}.hd{padding:6px 10px;font-weight:bold}.bd{padding:9px 11px}
.discussion{border-color:#7189a6;background:#f1f5fa}.discussion>.hd{background:#dce7f3}.inputs{border-color:#a78638;background:#fff8e9}.inputs>.hd{background:#f7e6b9}.outputs{border-color:#6a9075;background:#eff7f1}.outputs>.hd{background:#dcece0}
table{border-collapse:collapse;width:100%;font-size:10pt;margin:7px 0}th,td{border:1px solid #c9d3dc;padding:5px 7px;text-align:left;vertical-align:top}th{background:#e9eef3}td.num{text-align:right;font-variant-numeric:tabular-nums}
.PASS{color:#17633b;font-weight:bold}.FAIL{color:#b53333;font-weight:bold}.PENDING{color:#98600d;font-weight:bold}.ref{color:#7a2e2e;font-size:9pt}.subtle{color:#586777;font-size:9.5pt}.eq{padding:8px 0;font-size:12pt;overflow-x:auto}details{margin:5px 0}summary{cursor:pointer;color:#245c85}.toolbar{background:#fff;padding:8px 0;border-bottom:1px solid #dce5ec}.toolbar button{margin-right:8px;padding:7px 12px}.cards{display:flex;gap:12px;flex-wrap:wrap}.card{flex:1;min-width:170px;padding:12px;border:1px solid #bac8d4;background:#f8fafc}.card b{font-size:17pt;display:block}.status{border-left:5px solid #a56d15;background:#fff4d9;padding:10px 14px;margin:14px 0}.plot{background:#fff;border:1px solid #c9d3dc;padding:10px;margin:12px 0}svg{max-width:100%;height:auto}code{font-size:9pt}a{color:#245c85}
@media print{body{max-width:none;margin:0;font-size:10pt}.toolbar{display:none}h2{break-after:avoid}.box,.plot{break-inside:avoid}details{display:block}details>*{display:block}th{background:#eee}}
'''
STYLE+=EQUATION_STYLE


def esc(x): return html.escape(str(x))
def fmt(x,n=3): return f'{x:,.{n}f}' if isinstance(x,(int,float)) else '—' if x is None else esc(x)
def box(kind,title,body): return f'<div class="box {kind}"><div class="hd">{title}</div><div class="bd">{body}</div></div>'
def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+esc(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
def eq(formula,values,ref):
    return f'<div class="eq">{formula}<br><span class="subtle">{values}</span><br><span class="ref">{ref}</span></div>'


def check_details(r, check):
    """Shared derivation display: symbolic equation, substitution, result, unit."""
    out=[f'<details class="check-equations" data-check-id="{esc(check["id"])}">'
         '<summary>Equation &amp; values</summary>',
         '<p class="ref">'+esc(check['ref'])+'</p>']
    for item in check_steps(r, check):
        out.append('<div class="check-step"><b>'+esc(item['label'])+'</b>'
                   '<div class="check-formula">'+esc(item['formula'])+'</div>'
                   '<div class="check-values">= '+esc(item['substitution'])+'<br>= <b>'
                   +esc(number(item['value']))+' '+esc(item['unit'])+'</b></div></div>')
    if check['capacity'] > 0:
        ratio=f'D/C = {number(check["demand"])} / {number(check["capacity"])} = {number(check["ratio"])}'
    else:
        ratio='D/C is undefined: the available resistance / dimension is nonpositive. This check fails.'
    out.append('<div class="check-ratio">'+esc(ratio)+' · <span class="'+check['status']+'">'+check['status']+'</span></div>')
    if check['note']:out.append('<p>'+esc(check['note'])+'</p>')
    out.append('</details>')
    return ''.join(out)


def cone_section(r):
    c=r['cone'];p=r['case']
    if not c['enabled']:
        return box('discussion','Support model','Original pile-center, ring-level STM. Cone geometry is available in the workbench for comparison; it does not change this calculation.')
    text=box('discussion','ACI-style envelope and broad-face transfer trial',
        'The CCD sketch uses 1.5 horizontal to 1 vertical, labeled approximately 35°. '
        'The exact angle of that projection is 33.69°. Applying it from an annular ring perimeter is an explicit study assumption, '
        'not an ACI provision establishing ring bearing or breakout strength. '
        'The first broad-face intersections define the base elevation of the trial STM node region. '
        'Its centroid is raised by the entered tie offset. At first contact x remains at the pile center, so the bay span is unchanged. '
        'No external support or rigid cone is introduced. The existing ring reactions and end couples remain the external support actions. '
        '<a href="'+esc(c['source'])+'">ACI reference, slide 2</a>.')
    text+=eq('r(z) = r<sub>o</sub> + s(z−z<sub>ring</sub>); &nbsp; h<sub>face</sub> = (t/2−r<sub>o</sub>)/s',
             f's = {c["slope_hv"]:g} H:1 V; angle from horizontal = {c["angle_deg"]:.3f}°; '
             f'hface = ({p["thickness_in"]/2:g}−{c["ring_radius_in"]:g})/{c["slope_hv"]:g} = {c["face_rise_in"]:.3f} in. '
             f'Near/far face reaches at ±{p["placement_tolerance_in"]:g}-in transverse pile offset: '
             f'{c["near_face_rise_in"]:.3f} / {c["far_face_rise_in"]:.3f} in.',
             'Geometry adapted from the ACI 318-19 CCD breakout sketch; finite interior nodes and ring applicability remain unverified.')
    text+=table(['Row','Ring top (in)','First face contact (in)','Trial node centroid (in)','Bay span (in)'],[
        [a['row'],fmt(a['z']),fmt(a['node_base_z']),fmt(a['node_base_z']+p['tie_offset_in']),fmt(p['pile_spacing_in'])] for a in r['rows']])
    text+=box('discussion','Wall edges and actual connection',
        ('The outer-pile envelope reaches a wall end before the broad faces: end reach '
         f'{c["end_first_rise_in"]:.3f} in above the ring versus face reach {c["face_rise_in"]:.3f} in. '
         if c['end_truncated'] else 'The nominal first-face envelope does not reach a wall end first. ')+
        'Projection onto a free surface does not create bearing capacity. Reference nodes need finite area and cover inside the wall. '
        'The transverse tie shown as a resultant must be routed and anchored around the hollow pipe. '
        'Offset piles, end truncation, interacting rows, nodal strength and breakout resistance require a 3-D connection model.')
    text+=eq('V<sub>face</sub> = R/2; &nbsp; T<sub>trans</sub> = (R/2) Δy/Δz; &nbsp; C = √[(R/2)² + T<sub>trans</sub>²]',
             f'Δy = {max(0,c["radial_gap_in"]):.3f} in; Δz = {c["face_rise_in"]+p["tie_offset_in"]:.3f} in; '
             'As,req = Ttrans/(ϕt fy). No existing grid or transverse bar is automatically credited.',
             'Symmetric ring-to-face force equilibrium only; longitudinal end moments remain separate.')
    text+=table(['Row / pile','V per face (kip)','Transfer C (kip)','Transverse tie (kip)','Additional As,req (in²)'],[
        [f'{a["row"]}/{a["pile"]}',fmt(a['face_vertical_kip']),fmt(a['link_compression_kip']),fmt(a['transverse_tie_kip']),fmt(a['transverse_area_req_in2'],4)] for a in r['rings']])
    return text


def elevation(r):
    p=r['case']; L=p['length_in']; H=p['height_in']; sc=min(820/L,470/H)
    ox,oy=60,525
    def xy(x,z):return ox+x*sc,oy-z*sc
    def line(x1,z1,x2,z2,color,width=2,dash=''):
        a,b=xy(x1,z1);c,d=xy(x2,z2)
        return f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>'
    s=['<svg viewBox="0 0 950 610" role="img" aria-label="Wall elevation with piles, rings, parabolic compression polygons and dedicated ties">',
       '<rect width="950" height="610" fill="white"/>']
    x,y=xy(0,H)
    s+=[f'<rect x="{x}" y="{y}" width="{L*sc}" height="{H*sc}" fill="#f6f7f8" stroke="#8b9eae"/>']
    for xp in r['pile_x']:
        x,y=xy(xp-p['pile_od_in']/2,H)
        s.append(f'<rect x="{x}" y="{y}" width="{p["pile_od_in"]*sc}" height="{H*sc+10}" fill="#d5dce3" opacity=".75"/>')
    for b in r['geometry']['bounds'][1:-1]:s.append(line(0,b,L,b,'#aebac6',1,'5 5'))
    for row in r['rows']:
        zr=row['z']; base=row.get('node_base_z',zr)+p['tie_offset_in']
        for xp in r['pile_x']:
            s.append(line(xp-p['ring_od_in']/2,zr,xp+p['ring_od_in']/2,zr,'#263e54',4))
            s.append(line(xp,zr,xp,base,'#258875',3))
        for xp in r['pile_x'][:-1]:
            a=row['arch'];s.append(line(xp,base,xp+p['pile_spacing_in'],base,'#bf6c2d',2.5))
            for seg in a['segments']:
                s.append(line(xp+seg['x1'],base+seg['y1'],xp+seg['x2'],base+seg['y2'],'#258875',3))
            for xx,yy in zip(a['x'][1:-1],a['y'][1:-1]):
                s.append(line(xp+xx,row['lo']+1,xp+xx,base+yy,'#77539c',1.5))
        xx,yy=xy(L+3,zr)
        s.append(f'<text x="{xx}" y="{yy+4}" font-size="12" fill="#263e54">R{row["row"]} · {zr:g}″</text>')
    s.append('<text x="60" y="552" font-family="Arial" font-size="12">Elevation · inches · pile-center spacing retained · equivalent 2-D paths</text>')
    s.append('<text x="60" y="576" font-family="Arial" font-size="12" fill="#258875">Compression struts</text>')
    s.append('<text x="230" y="576" font-family="Arial" font-size="12" fill="#bf6c2d">ADDED horizontal ties</text>')
    s.append('<text x="425" y="576" font-family="Arial" font-size="12" fill="#77539c">ADDED collectors</text>')
    s.append('<text x="615" y="576" font-family="Arial" font-size="12">Dashed: assigned band limits</text></svg>')
    return ''.join(s)


def plan(r):
    p=r['case'];g=r['grid'];end=r['end'];sc=6.0; ox,oy=58,195
    xmax=min(p['length_in'],end+p['ring_od_in']/2+18)
    def xy(x,y):return ox+x*sc,oy-y*sc
    def line(x1,y1,x2,y2,color,width=2,dash=''):
        a,b=xy(x1,y1);c,d=xy(x2,y2)
        return f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>'
    s=['<svg viewBox="0 0 900 365" role="img" aria-label="Wall end plan, ring envelope, face bars and matching U-bar"><rect width="900" height="365" fill="white"/>']
    x,y=xy(0,p['thickness_in']/2)
    s.append(f'<rect x="{x}" y="{y}" width="{xmax*sc}" height="{p["thickness_in"]*sc}" fill="#f6f7f8" stroke="#8b9eae"/>')
    x,y=xy(end,0)
    for radius,color,dash in [(p['ring_od_in']/2+p['placement_tolerance_in'],'#c44b3d','5 4'),(p['ring_od_in']/2,'#4a6b85',''),(p['pile_od_in']/2,'#727f8b','')]:
        s.append(f'<circle cx="{x}" cy="{y}" r="{radius*sc}" stroke="{color}" fill="none" stroke-width="2" stroke-dasharray="{dash}"/>')
    ybar=p['thickness_in']/2-p['cover_in']-g['db']/2
    xbar=p['cover_in']+g['db']/2
    s += [line(xbar,ybar,xmax,ybar,'#c57a22',3),line(xbar,-ybar,xmax,-ybar,'#c57a22',3),line(xbar,-ybar,xbar,ybar,'#c57a22',3)]
    s.append('<text x="445" y="84" font-family="Arial" font-size="14" fill="#263e54">Wall-end U-bar, plan</text>')
    labels=[f'#{g["bar"]} at {g["spacing"]:g}″ vertical pitch, both ends',
            f'Matches horizontal face-grid size and spacing',
            f'Outside width: {g["u_width"]:g}″; inside bend ≥ {g["u_inside_bend"]:g}″',
            f'Straight legs: {p["u_leg_in"]:g}″ from bend tangents',
            f'Class B lap allowance: {g["development_h"]["lap_b"]:.2f}″',
            'Dashed red: ring + pile-placement envelope',
            'Bends shown schematically; leg ends cropped',
            'Tie anchorage and clash resolution remain open']
    for i,label in enumerate(labels):s.append(f'<text x="445" y="{111+24*i}" font-family="Arial" font-size="12">{esc(label)}</text>')
    s.append('</svg>');return ''.join(s)


def render_report(r):
    p=r['case'];g=r['grid'];tot=r['totals'];geo=r['geometry'];rows=r['rows']
    case_id=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:12]
    out=['<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
         '<title>Ring-supported pier wall — strut-and-tie calculation</title><style>'+STYLE+'</style></head><body>',
         '<div class="toolbar"><button onclick="window.print()">Print / save PDF</button><span class="subtle">Standalone calculation report · values in inches, kips and ksi</span></div>',
         '<div class="eyebrow">D2 I-95 PEDESTRIAN BRIDGE · RING WALL STUDY</div>',
         '<h1>'+esc(p['title'])+'</h1>',
         f'<p class="subtle">AASHTO LRFD BDS, 10th edition (2024) · case {case_id} · calculation revision 2026-10-12</p>',
         f'<div class="status"><b>{r["overall"]}</b><br>Gravity study with explicit open connection checks. Individual PASS results apply only to the named checks.</div>']
    out.append(box('discussion','Purpose and load path',
        'Design the initial steel cage, then investigate ring-supported wall bands using an equilibrated tied arch between each pair of piles. '
        'Concrete carries compression; dedicated horizontal ties close arch thrust; dedicated vertical collectors lift tributary concrete weight into the arch. '
        'The ring is a finite steel bearing surface. The optional ACI-style envelope defines a trial face-transfer elevation; it does not shorten the pile-center span or establish breakout capacity. '
        'The wall-end strips deliver vertical force and a couple to the outer rings and require their own local load-path verification.'))
    out.append('<div class="cards">'+''.join(f'<div class="card">{a}<b>{b}</b>{c}</div>' for a,b,c in [
        ('Wall gravity',fmt(tot['service_weight'])+' kip','Unfactored, gross wall volume'),
        ('Factored gravity',fmt(tot['factored_weight'])+' kip','DC and entered added gravity factors'),
        ('Uniform face grid',f'#{g["bar"]} @ {g["spacing"]:g}″','Each way, each broad face'),
        ('Ring layout',f'{p["ring_count"]} rows @ {p["ring_spacing_in"]/12:g} ft',f'{p["pile_count"]*p["ring_count"]} trial rings')])+'</div>')
    out.append('<h2>1 · Minimum wall steel and matching end U-bars</h2>')
    out.append(box('discussion','Required starting cage',
        'Use the greater of shrinkage/temperature reinforcement and STM crack-control reinforcement. '
        'The 0.003 STM ratio is total steel across the wall thickness; half is assigned to each broad face. '
        'Evaluate both orthogonal gross S&amp;T sections and use their envelope in both directions. '
        'This is a conservative cage rule for this study, not a reduction for the hollow piles. '
        'The crack-control grid is not credited a second time as primary STM tie steel.'))
    out.append(box('inputs','Geometry and reinforcement inputs',table(
        ['Input','Value','Basis'],[
            ['Wall L × t × H',f'{p["length_in"]:g} × {p["thickness_in"]:g} × {p["height_in"]:g} in','C006 wall snapshot; confirm current geometry'],
            ['Concrete / steel',f'f′c = {p["fc_ksi"]:g} ksi; fy = {p["fy_ksi"]:g} ksi','Normalweight; no prestress'],
            ['Clear cover / aggregate',f'{p["cover_in"]:g} / {p["aggregate_in"]:g} in','Entered project assumptions'],
            ['Shallowest band / effective depth',f'{min(x["height"] for x in rows):.3f} / {g["d"]:.3f} in','Band height − cover − db/2'],
            ['Bar coating',esc(p['coating']),'Unknown uses adverse epoxy development factor']
        ])))
    equations=eq('A<sub>s,ST</sub> = clamp[1.30 b h / {2(b+h) f<sub>y</sub>}, 0.11, 0.60]',
        f'L-section = {g["st_L"]:.4f}; H-section = {g["st_H"]:.4f}; use {g["st"]:.4f} in²/ft per face, each way.',
        'LRFD 5.10.6-1 and -2; fy capped at 75 ksi')
    equations+=eq('A<sub>s,STM,face</sub> = 0.003 t (12) / 2',
        f'= 0.003 × {p["thickness_in"]:g} × 12 / 2 = {g["stm"]:.4f} in²/ft per face, each way.',
        'LRFD 5.8.2.6-1 and -2')
    equations+=eq('s ≤ min(12, d / 4); &nbsp; A<sub>s,prov</sub> = 12 A<sub>b</sub> / s',
        f's ≤ {g["spacing_limit"]:.3f} in; selected #{g["bar"]} @ {g["spacing"]:g} in provides {g["provided"]:.4f} in²/ft.',
        'LRFD 5.8.2.6; discrete spacing rounded down to entered increment')
    out.append(box('outputs','Equations and selected steel',equations))
    out.append(table(['Candidate','Largest allowed trial spacing','As / face','Placement feasible'],[
        [f'#{a["bar"]}',f'{a["spacing"]:g} in',f'{a["provided"]:.4f} in²/ft','Yes' if a['feasible'] else 'No'] for a in g['candidates']]))
    out.append(box('outputs','Initial reinforcement schedule',table(['Mark','Location','Trial provision'],[
        ['WH / WV','Both broad faces',f'#{g["bar"]} @ {g["spacing"]:g} in each way; horizontal bars outermost'],
        ['WU','Both wall ends',f'#{g["bar"]} U-bars @ {g["spacing"]:g} in vertically; one leg laps each face horizontal bar'],
        ['WE','Vertical steel across each narrow end face',f'{g["end_vertical_count"]}–#{g["bar"]}, equally spaced at {g["end_vertical_pitch"]:.3f} in; same cover'],
        ['WT','Through-thickness ties',f'#{p["transverse_bar"]} at {p["transverse_spacing_in"]:g} × {p["transverse_spacing_in"]:g} in trial grid; route around pipe; no strength credit'],
        ['ST-H','ADDITIONAL horizontal primary ties',f'{p["primary_bars_per_face"]}–#{p["primary_bar"]} per face at each ring tier, centered {p["tie_offset_in"]:g} in above the trial node-region base'],
        ['ST-V','ADDITIONAL vertical collectors',f'{p["hanger_bars_per_face"]}–#{p["primary_bar"]} per face at each arch joint and pile node; end-region layout and all anchorage remain open'],
    ])))
    out.append('<div class="plot">'+plan(r)+'</div>')
    out.append(eq('ℓ<sub>db</sub> = 0.17 d<sub>b</sub> [f<sub>y</sub> / (1.97 λ f′<sub>c</sub><sup>0.25</sup>)]²; &nbsp; ℓ<sub>d</sub> = max(12, ℓ<sub>db</sub> λ<sub>rl</sub> λ<sub>cf</sub> λ<sub>rc</sub>)',
        f'Grid horizontal: basic {g["development_h"]["basic"]:.3f} in; applied factor {g["development_h"]["factor"]:.2f}; ℓd = {g["development_h"]["ld"]:.3f} in; '
        f'Class B = 1.3 ℓd = {g["development_h"]["lap_b"]:.3f} in. Entered U-leg = {p["u_leg_in"]:g} in.',
        'LRFD 5.10.8.2.1a/b; 5.10.8.4.3. Full yield, Fh = 0, density = 1, confinement factor = 1. Top-bar factor 1.3; coating product capped at 1.7.'))
    out.append(box('discussion','U-bars and STM anchorage are separate checks',
        'Matching U-bars close the face cage and provide straight lap legs. The displayed bend width and lap allowance do not prove '
        'anchorage of the arch tie into an extended nodal zone. Locate the critical development section where the tie exits that zone. '
        'Check bend bearing, noncontact lap spacing, stagger, bar collisions and the actual available development length. '
        f'Additional primary tie straight development: horizontal {r["steel"]["primary_dev_h"]["ld"]:.3f} in; vertical {r["steel"]["primary_dev_v"]["ld"]:.3f} in.'))
    out.append('<h2>2 · Ring rows, tributary bands and gravity</h2>')
    out.append(box('inputs','Layout and load assumptions',table(['Input','Value'],[
        ['Piles',f'{p["pile_count"]} × {p["pile_od_in"]:g}-in OD at {p["pile_spacing_in"]:g}-in centers; end distance {r["end"]:g} in'],
        ['Ring top elevations',', '.join(f'{x["z"]:g}' for x in rows)+' in above wall bottom'],
        ['Density / load factors',f'{p["density_kcf"]:g} kcf; γDC = {p["gamma_dc"]:g}; γadditional = {p["gamma_additional"]:g}'],
        ['Additional gravity on wall elevation',f'{p["additional_service_ksf"]:g} ksf, service magnitude'],
        ['Support assumptions','No pipe bond/friction; no soil support; no suspension from cap; no deduction for pipe voids in weight']
    ])))
    out.append(eq('w<sub>u,j</sub> = [γ<sub>DC</sub> γ<sub>c</sub> (t/12) + γ<sub>add</sub> q<sub>add</sub>] h<sub>j</sub> / 144',
        'w in kip/in; t and band height h in inches, density in kip/ft³, additional gravity in kip/ft² of wall elevation.',
        'Assigned horizontal bands bounded by wall edges and midpoints between successive rings'))
    out.append(table(['Row','Ring top (in)','Band bottom–top (in)','Height (in)','wu (kip/in)','Factored wall-band weight (kip)'],[
        [a['row'],fmt(a['z']),f'{a["lo"]:.3f}–{a["hi"]:.3f}',fmt(a['height']),fmt(a['w'],5),fmt(a['weight'])] for a in rows]))
    out.append(box('discussion','Compatibility and lower-wall suspension',
        'The band assignment partitions all wall weight exactly once. It is a proposed strength load path, not a prediction of actual row load sharing. '
        'Rings may engage differently because of settlement, shrinkage, concrete cracking, pile deformation or erection sequence. '
        'The lowest band includes all concrete below the lowest ring: collectors must carry that weight upward and be anchored into the compression field. '
        'A support cone or equal division by the number of rings cannot establish compatibility.'))
    out.append('<h2>3 · Equilibrated tied arches between piles</h2>')
    out.append(cone_section(r))
    out.append('<div class="plot">'+elevation(r)+'</div>')
    out.append(box('discussion','Discrete distributed-load model',
        f'Each bay uses {p["arch_panels"]} straight compression segments on a parabolic polygon. '
        'Tributary column loads act at each joint, with half-width columns at the two endpoints. '
        'Moving self-weight vertically to these joints preserves external moments but requires an internal collector path: '
        'full tributary column weight is conservatively assigned as vertical tie demand at interior joints. '
        'Do not move the whole bay load to one crown without those collectors. '
        'Horizontal base ties are centered on the entered reinforcement elevation and resist thrust independently in every bay; '
        'no cancellation between neighboring arches or lateral pile fixity is credited.'))
    out.append(eq('y(x) = 4 h<sub>a</sub> x(L−x) / L²; &nbsp; T = w L² / (8 h<sub>a</sub>); &nbsp; C<sub>i</sub> = √[T² + {T Δy<sub>i</sub>/Δx}²]',
        f'L = {p["pile_spacing_in"]:g} in; rise = {p["arch_rise_in"]:g} in; Δx = {p["pile_spacing_in"]/p["arch_panels"]:g} in. Interior joint load = w Δx.',
        'Joint and external equilibrium; LRFD 5.8.2.2 modeling principles'))
    out.append(eq('ϕP<sub>n,tie</sub> = ϕ<sub>t</sub> f<sub>y</sub> A<sub>st</sub>',
        f'Horizontal capacity = {r["steel"]["tie_capacity"]:.3f} kip; vertical collector capacity = {r["steel"]["hanger_capacity"]:.3f} kip. Both faces combined; dedicated steel only.',
        'LRFD 5.5.4.2; 5.8.2.4.1 and .4.2'))
    out.append(table(['Row','T (kip)','Cmax (kip)','Collector (kip)','Angle min (°)','Bay reaction (kip)','Service V / Vcr'],[
        [a['row'],fmt(a['arch']['tie']),fmt(a['arch']['max_C']),fmt(a['arch']['hanger']),fmt(a['arch']['minimum_angle'],2),fmt(a['arch']['reaction']),f'{a["service_arch"]["reaction"]:.3f} / {a["vcr"]:.3f}'] for a in rows]))
    out.append(eq('ϕP<sub>n,node</sub> = ϕ<sub>c</sub> (m ν f′<sub>c</sub>) b<sub>eq</sub> [ℓ<sub>b</sub> sin θ + h<sub>n</sub> cos θ]',
        f'ϕc = {p["phi_concrete"]:g}; m = 1; ν = 0.45; beq = {p["node_width_in"]:g} in ≤ t−D = {p["thickness_in"]-p["pile_od_in"]:g} in; '
        f'ℓb = η Aannulus / (2 beq). Nodal height = {p["node_height_in"]:g} in.',
        'LRFD 5.8.2.5.1 through .5.3; planar area mapping is an explicit screening assumption'))
    out.append(box('discussion','Finite nodes and the hollow pile',
        'The planar diagram passes through the pile center only as an equivalent representation. Actual compression must flow around the hollow steel pipe. '
        'The entered equivalent concrete width is bounded by wall thickness minus pipe OD. Half of the reduced annular bearing area is assigned to each adjacent bay. '
        'This mapping needs a three-dimensional node model; it is not an established effective area. The conservative ν = 0.45 avoids claiming higher node efficiency '
        'while local tie directions and confinement are unresolved. Every concrete strength result is therefore labeled SCREEN.'))
    out.append('<h2>4 · Ring reactions and preliminary connection sizing</h2>')
    out.append(box('inputs','Trial ring section',table(['Quantity','Value'],[
        ['Inside / outside diameter',f'{p["ring_id_in"]:g} / {p["ring_od_in"]:g} in'],
        ['Thickness / radial plate width',f'{p["ring_t_in"]:g} / {(p["ring_od_in"]-p["ring_id_in"])/2:.4f} in'],
        ['Plate yield / elastic screening factor',f'{p["ring_fy_ksi"]:g} ksi / {p["phi_plate"]:g}'],
        ['Assumed effective bearing fraction η',fmt(p['bearing_fraction'],2)+' — sensitivity input, not verified contact'],
        ['Pile tolerance / effective pipe wall',f'{p["placement_tolerance_in"]:g} / {p["pile_t_effective_in"]:g} in'],
        ['Ring-to-wall end / face cover at tolerance',f'{geo["edge_clear"]:.3f} / {geo["face_clear"]:.3f} in'],
        ['Ring-to-inner face grid clearance at tolerance',f'{geo["grid_gap"]:.3f} in'],
    ])))
    out.append(eq('R<sub>int</sub> = wL; &nbsp; R<sub>end</sub> = w(L/2 + e); &nbsp; M<sub>end</sub> = ± w e²/2',
        'The wall overhang e contributes weight and an explicit support couple. End strip tie demand = |Mend| / entered arch rise, for preliminary force sizing only.',
        'Gravity equilibrium including the full wall length'))
    out.append(eq('q<sub>max,min</sub> = R/(ηA) ± |M|r<sub>o</sub>/(ηI); &nbsp; A = π(r<sub>o</sub>²−r<sub>i</sub>²); &nbsp; I = π(r<sub>o</sub>⁴−r<sub>i</sub>⁴)/4',
        f'A = {geo["ring_area"]:.3f} in²; I = {geo["ring_I"]:.3f} in⁴. Negative qmin invalidates the assumed full-contact pressure shape.',
        'Elastic pressure screen; reduction of both A and I assumes a distributed effective fraction'))
    out.append(eq('m<sub>root</sub> = q<sub>max</sub> [(r<sub>o</sub>³−r<sub>i</sub>³)/(3r<sub>p</sub>) − (r<sub>o</sub>²−r<sub>i</sub>²)/2]; &nbsp; t<sub>req</sub> = √[6m<sub>root</sub>/(ϕ<sub>s</sub>F<sub>y</sub>)]',
        'Radial cantilever strip per unit pipe circumference. Ring-ID fit gap is included in the lever arm. qmax is applied over the full radial width.',
        'Elastic plate-yield screen; no claim of complete annular plate or bridge steel connection design'))
    out.append(table(['Row/pile','Ru (kip)','Mu (kip-in)','qmax (ksi)','qmin (ksi)','Plate treq (in)','Weld vpeak (kip/in)'],[
        [f'{a["row"]}/{a["pile"]}',fmt(a['R']),fmt(a['M']),fmt(a['qmax']),fmt(a['qmin']),fmt(a['t_req']),fmt(a['weld_vertical_per_in'])] for a in r['rings']]))
    out.append(box('discussion','Force handoff to connection design',
        'Weld vpeak = R/(2πrp) + |M|/(πrp²) includes direct vertical shear and the global end moment only. '
        'The separate radial strip root moment must also be transferred by the weld/ring/pile-shell system; do not size a weld from vpeak alone. '
        'The exported ring table includes that root moment and pipe membrane stress for the next analysis. '
        'No weld, split-ring splice, pipe-shell or concrete breakout capacity is assigned here. Stock/fabricator availability is not established by these trial dimensions.'))
    out.append('<h2>5 · Equilibrium verification and ring-spacing study</h2>')
    out.append(box('outputs','Numerical equilibrium',table(['Quantity','Residual / result'],[
        ['Σ ring reactions − factored wall weight',f'{tot["force_error"]:.3e} kip'],
        ['Σ(Rx + M) − total gravity moment',f'{tot["moment_error"]:.3e} kip-in'],
        ['Maximum arch-joint vector residual',f'{tot["joint_error"]:.3e} kip'],
        ['Σ factored ring reactions',f'{tot["ring_reactions"]:.6f} kip']
    ])))
    out.append(box('discussion','How to study rings at different vertical spacings',
        'Change ring count, first ring elevation and spacing together, then rerun. The notebook regenerates all band heights and checks shallow top/bottom bands, '
        'minimum bar spacing, arch fit, angles and ring forces. Increasing spacing raises per-ring gravity and may provide more arch depth. '
        'Adding rows does not by itself prove that their reactions share equally. A short terminal band can govern the entire uniform cage.'))
    out.append('<h2>6 · Check register</h2>')
    out.append('<p class="subtle">CHECK / STRENGTH: equation results for the stated model. SCREEN: additional modeling assumptions remain open. FIT: entered geometry and tolerance only.</p>')
    out.append(table(['ID / scope','Check','Demand','Resistance / limit','D/C','Result'],[
        [esc(c['id'])+'<br><span class="subtle">'+esc(c['scope'])+'</span>',
         esc(c['title'])+check_details(r,c),
         f'{c["demand"]:.4f} {esc(c["unit"])}',f'{c["capacity"]:.4f} {esc(c["unit"])}',fmt(c['ratio']),f'<span class="{c["status"]}">{c["status"]}</span>'] for c in r['checks']]))
    out.append('<h2>7 · Open design items and source basis</h2>')
    out.append(table(['Item','Required resolution'],[[f'<span class="PENDING">{a}</span>',esc(b)] for a,b in r['pending']]))
    out.append(box('discussion','Project and code provenance',
        '<p>Geometry starts from the earlier C006 wall study: 213 × 36 × 172.375 in, four 20-in piles at 60-in centers, '
        'f′c 5.5 ksi and fy 60 ksi. These are editable study inputs, not an automatic import of the current CAD wall. '
        'The October 12 repository pier-cap selected case confirms pile count/diameter/spacing and material strengths; '
        'its 3-in pile tolerance is adopted here instead of the earlier wall trial’s 2 in.</p>'
        '<p>Equation basis: AASHTO LRFD Bridge Design Specifications, 10th edition (2024), '
        '5.5.4.2; 5.8.2.2 through 5.8.2.6; 5.10.2; 5.10.3.1.1; 5.10.6; 5.10.8.2.1; 5.10.8.4.3. '
        'The supplied code was checked for the 0.003 total grid ratio, d/4 spacing, compression/tension factors and the revised 10th-edition development equation.</p>'
        '<p>Background examples: <a href="https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf">FHWA-NHI-17-071, Strut-and-Tie Modeling for Concrete Structures</a> '
        '(2017; older-edition examples, not the equation authority for this calculation). '
        '<a href="https://www.fdot.gov/structures/structuresmanual/currentrelease">FDOT Structures Manual</a>: confirm applicable contract edition and project modifications.</p>'
        '<p>Formatting follows the project cap/end-wall calculations: blue discussion, amber inputs, green results, numbered sections and a D/C register. '
        'This file requires no internet to display or print. No complete code text is reproduced.</p>'))
    out.append('</body></html>');return ''.join(out)


def export_results(r,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    paths=[]
    for name,data in [('ring_wall_case.json',r['case']),('ring_wall_results.json',r)]:
        path=folder/name;path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8');paths.append(path)
    path=folder/'ring_wall_report.html';path.write_text(render_report(r),encoding='utf-8');paths.append(path)
    for name,items in [('ring_wall_checks.csv',r['checks']),('ring_wall_ring_forces.csv',r['rings'])]:
        path=folder/name
        with path.open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)
        paths.append(path)
    return paths
