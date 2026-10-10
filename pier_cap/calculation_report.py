"""Self-contained, reviewable cap calculation report using the live evaluation.

Layout follows standards/BPAD_Ref_V5.txt §16: objective / inputs / output,
strategy → execution, visible equation captions, and distinct input/discussion/
output tables. Native MathML and embedded Plotly require no network connection.
"""
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from .output_labels import number_tables

from .engine import Q, parse
from .model import DEFINITIONS, evaluate, bar_positions, BAR_AREA, BAR_DIAMETER, steel_quantity_components
from .math_notation import mathml, expression, symbol, quantity, tag
from .force_audit import force_basis, strength_audit
from .transverse import enabled as actual_transverse

BY_NAME = {d['name']:d for d in DEFINITIONS}
# Boundaries are stable definition names, not positions in the source file.
SECTIONS = [
    ('basis', 'Geometry, materials and design basis', 'b',
     'Establish the cap section, pile geometry, materials and adopted factors.',
     'Geometry and materials in the current case', 'Dimensions and assumptions for sectional checks'),
    ('loads', 'Design actions and analysis provenance', 'Mu_N',
     'Identify strength and service demands and their source.',
     'Imported envelopes or edited load inputs', 'Adopted actions, governing combinations and source limitations'),
    ('steel', 'Reinforcement, coordinates and effective depths', 'Bar_N1',
     'Locate the continuous and additional bars and calculate their area-weighted centroids.',
     'Bar sizes, counts, cover and transverse detail', 'Steel areas, row coordinates, effective depths and spacings'),
    ('flexure', 'Flexural strength and minimum reinforcement', 'alpha_1',
     'Compare factored moments with resistance and minimum reinforcement targets.',
     'Actions from step 2 and effective sections from step 3', 'Resistance, strain applicability and demand/capacity ratios'),
    ('service', 'Service I and Service III crack control', 'Ec',
     'Calculate cracked-section steel stresses and permissible bar spacing.',
     'Service moments, section properties and exposure factor', 'Steel stresses and spacing checks; missing Service III remains pending'),
    ('fatigue', 'Fatigue stress range', 'fmin_N',
     'Compare the factored live-load stress range with the straight-bar threshold.',
     'Permanent moment, fatigue range and adopted factor', 'Fatigue ratios only when applicability and loads are confirmed'),
    ('shear', 'Shear and transverse spacing', 'dv',
     'Determine concrete and transverse-steel resistance and spacing limits.',
     'Shear envelope, effective depth and entered hoop/U-bar schedule', 'Sectional shear checks and conditional actual-station checks'),
    ('torsion', 'Torsion and longitudinal equilibrium', 'Ao_factor',
     'Screen torsion and the associated transverse and longitudinal reinforcement.',
     'Torque envelope, shear and reinforcement geometry', 'Torsion threshold, required steel and outstanding closure/development review'),
    ('details', 'Skin steel, shrinkage, quantities and detailing', 'Skin_required',
     'Check face reinforcement and record quantities and remaining detailing requirements.',
     'Section, steel inventory and spacing', 'Face-steel checks, concrete volume, steel estimate and detailing register'),
]

CSS = r'''
:root{color-scheme:light;--ink:#233548;--blue:#1766a0;--line:#cbd5df}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#e9edf1;color:var(--ink);font:11pt/1.5 "Times New Roman",serif}
main{max-width:1140px;margin:24px auto;background:white;padding:38px 48px;box-shadow:0 4px 28px #20304018}
h1{font-size:24pt;line-height:1.15;margin:12px 0}h2{font-size:16pt}h3{font-size:14pt}h4{font-size:12pt}h1,h2,h3,h4,summary{break-after:avoid}
p{margin:10px 0}a{color:#1766a0}.eyebrow,.step,.toolbar,button,.badge{font-family:Arial,sans-serif}.eyebrow{letter-spacing:.12em;font-size:9pt;color:#52697e}
.toolbar{position:sticky;top:0;z-index:10;background:#233548;color:white;padding:10px 20px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
button,.toolbar a{border:1px solid #becbd7;border-radius:4px;padding:8px 14px;background:white;color:#233548;cursor:pointer;font-size:10pt}.toolbar a{text-decoration:none}button:focus-visible,summary:focus-visible,.toolbar a:focus-visible{outline:3px solid #dba62b;outline-offset:2px}
.toolbar span{margin-left:auto;font-size:9pt}.lead{font-size:13pt}.muted,figcaption,.caption{color:#536575}.caption{font-size:10pt;margin:0 0 8px}.step{color:var(--blue);background:#edf3f8;padding:5px 10px;font-size:9pt;display:inline-block}
details.section{border-top:2px solid var(--line);margin:24px 0;padding-top:12px;scroll-margin-top:70px}summary{cursor:pointer;font-weight:bold;padding:8px 0}details.section>summary{font-size:16pt}details.region>summary{font-size:13pt}
.section-body{padding:4px 0 12px}details.region,details.working{border-left:3px solid #dce7f3;padding:0 0 0 16px;margin:14px 0}details.working>summary{font-size:10pt}
.geometry-gallery,.geometry-view{scroll-margin-top:80px}.geometry-links{display:flex;flex-wrap:wrap;gap:8px 18px;padding:0;list-style:none;font:10pt Arial,sans-serif}
table{border-collapse:collapse;width:100%;font-size:10pt;margin:14px 0}th,td{border:1px solid #cbd5df;text-align:left;padding:8px 10px;vertical-align:top;overflow-wrap:anywhere}thead{display:table-header-group}tr{break-inside:avoid}th{background:#dce7f3}
.table-wrap{overflow-x:auto}.inputs td{background:#fff8e9}.inputs th{background:#f7e6b9}.inputs td,.inputs th{border-color:#a78638}.discussion td{background:#f1f5fa}.discussion th{background:#dce7f3}.discussion td,.discussion th{border-color:#7189a6}.output td{background:#eff7f1}.output th{background:#dcece0}.output td,.output th{border-color:#6a9075}
.badge{display:inline-block;padding:3px 7px;border-radius:3px;font-size:9pt;font-weight:600;background:#edf1f5;white-space:normal}.pass{color:#1d6844;background:#e3f1e8}.fail{color:#952c2c;background:#ffe7e5}.pending{color:#805413;background:#fff0cf}.reference{color:#4c5c70;background:#e8edf3}
.notice{border-left:4px solid #a78638;background:#fff8e9;padding:12px 16px;margin:16px 0}.flow{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0}.flow li{background:#edf3f8;padding:8px 12px}.flow li:not(:last-child)::after{content:' →';color:#7189a6}
.equation{border-bottom:1px solid #e5e9ee;padding:14px 0;scroll-margin-top:70px}.equation-line{overflow-x:auto;padding:10px 4px;max-width:100%}math{font-family:"Cambria Math","STIX Two Math",math;font-size:12pt}math[display=block]{text-align:left;margin:0;width:max-content;max-width:none}.equation-id{font:9pt Arial,sans-serif;color:#65788a;float:right}.result{border-left:3px solid #6a9075;background:#eff7f1;padding:8px 12px;margin-top:8px}
figure{margin:20px 0;break-inside:avoid}.plot{width:100%;min-height:420px}figcaption{font-size:10pt;border-bottom:1px solid #dce5ec;padding:7px 0}.meta{font-size:9pt;overflow-wrap:anywhere}.links{columns:2}.compact{font-size:9pt}noscript{display:block;background:#fff0cf;padding:14px}
@media(max-width:700px){main{margin:0;padding:22px 16px}h1{font-size:20pt}.links{columns:1}.toolbar span{display:none}th,td{padding:6px}.plot{min-height:360px}}
@page{size:letter;margin:.5in}
@media print{body{background:white;font-size:11pt}main{margin:0;padding:0;max-width:none;box-shadow:none}.toolbar,.backlink{display:none}h1{font-size:16pt}details.section>summary{font-size:14pt}h3,details.region>summary{font-size:12pt}details{display:block!important}details.raw-source{display:none!important}details>summary{list-style:none}details::details-content{display:block!important;content-visibility:visible!important}.table-wrap,.equation-line{overflow:visible}.equation-line math{font-size:10pt;max-width:100%;width:auto}details.section{break-before:auto}figure{break-inside:auto}.plot{min-height:0}a{color:inherit;text-decoration:none}.notice,.result,th,td{-webkit-print-color-adjust:exact;print-color-adjust:exact}.equation{break-inside:auto}}
'''

JS = r'''
const details=[...document.querySelectorAll('details')];
const plots=[...document.querySelectorAll('.plot')];
const waiting=new Map();
function visible(node){return !node.closest('details:not([open])');}
async function renderPlots(all=false){
  const pending=plots.filter(p=>all||visible(p)).map(p=>{
    if(waiting.has(p)) return waiting.get(p);
    if(p.dataset.rendered) return Plotly.Plots.resize(p);
    const figure=JSON.parse(document.getElementById(p.dataset.figure).textContent);
    const promise=Plotly.newPlot(p,figure.data,figure.layout,{responsive:true,displaylogo:false,scrollZoom:false})
      .then(()=>{p.dataset.rendered='true';waiting.delete(p);})
      .catch(error=>{waiting.delete(p);p.textContent='Plot could not render: '+error.message;});
    waiting.set(p,promise);return promise;
  });
  await Promise.all(pending);
}
let renderScheduled=false;
function scheduleRender(){if(renderScheduled)return;renderScheduled=true;requestAnimationFrame(()=>{renderScheduled=false;renderPlots();});}
function setSections(open){details.forEach(d=>d.open=open);scheduleRender();}
document.getElementById('expand-all').addEventListener('click',()=>setSections(true));
document.getElementById('collapse-all').addEventListener('click',()=>setSections(false));
document.addEventListener('toggle',scheduleRender,true);
function revealTarget(id){const node=document.getElementById(id);if(!node)return;
  for(let p=node;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
  requestAnimationFrame(()=>{node.scrollIntoView();renderPlots();});}
function revealHash(){revealTarget(decodeURIComponent(location.hash.slice(1)));}
window.addEventListener('hashchange',revealHash);
document.addEventListener('click',event=>{const link=event.target.closest('a[href^="#"]');
  if(link)revealTarget(decodeURIComponent(link.getAttribute('href').slice(1)));});
let savedOpen=null;
function preparePrint(){if(!savedOpen)savedOpen=details.map(d=>d.open);details.forEach(d=>d.open=true);return renderPlots(true);}
window.addEventListener('beforeprint',preparePrint);
window.addEventListener('afterprint',()=>{if(savedOpen){details.forEach((d,i)=>d.open=savedOpen[i]);savedOpen=null;renderPlots();}});
document.getElementById('print-report').addEventListener('click',async()=>{await preparePrint();await new Promise(requestAnimationFrame);window.print();});
renderPlots();revealHash();
'''


def table(headers, rows, kind='discussion', raw=False):
    cell = (lambda x:str(x)) if raw else (lambda x:escape(str(x)))
    return '<div class="table-wrap"><table class="'+kind+'"><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+cell(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def badge(status):
    status = str(status)
    kind = 'fail' if 'FAIL' in status else 'reference' if 'REFERENCE' in status else 'pass' if 'PASS' in status else 'pending'
    if status=='PASS':status='✓ PASS'
    if status=='FAIL':status='⊗ FAIL'
    return '<span class="badge '+kind+'">'+escape(status)+'</span>'


def context(objective, inputs, output):
    return '<table class="discussion"><tbody>'+''.join('<tr><th scope="row">'+label+'</th><td>'+escape(text)+'</td></tr>' for label,text in [('Objective',objective),('Inputs',inputs),('Output',output)])+'</tbody></table>'


def pending(name, e):
    return (not e.case['inputs']['Ready_III'] and ('III' in name)) or (
        not e.case['inputs']['Ready_fatigue'] and name.startswith(('MDL_', 'DMLL_', 'fmin_', 'Df_', 'FTH_', 'DC_fat_', 'Chk_fat_', 'Status_fatigue')))


def groups():
    result = {s[0]:[] for s in SECTIONS}
    starts = {s[2]:s[0] for s in SECTIONS}
    current = None
    for definition in DEFINITIONS:
        name=definition['name']
        if name in starts:current=starts[name]
        if current:result[current].append(definition)
    if any(not ds for ds in result.values()):raise ValueError('Calculation report section boundary missing.')
    return result


class Report:
    def __init__(self, e):
        self.e=e
        self.figures=[]
        self.checks={c.key:c for c in e.checks}
        self.actual=actual_transverse(e.case)
        self.equation_count=0

    def plot(self, figure, caption):
        # All geometry and data are from the current evaluated case.
        figure.update_layout(autosize=True, width=None, font=dict(family='Arial',size=12))
        index=len(self.figures)+1
        key=f'figure-data-{index}'
        payload=figure.to_json().replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
        self.figures.append('<script type="application/json" id="'+key+'">'+payload+'</script>')
        height=figure.layout.height or 520
        reference = figure.layout.meta['reference']
        return f'<figure><div class="plot" id="plot-{index}" data-figure="{key}" style="height:{height}px"></div><figcaption>{reference}. {escape(caption)}</figcaption></figure>'

    def result(self, name):
        if pending(name,self.e):return badge('PENDING — inputs / applicability not confirmed')
        if name in self.checks:return badge(self.checks[name].status)
        return mathml(quantity(self.e.engine.get(name),self.e.engine,BY_NAME[name]['unit']))

    def equation(self, d):
        name=d['name']
        # The actual-cage module supersedes these uniform-cage calculations.
        # Its equations and substitutions are printed in the LRFD working section.
        if self.actual and (name in ('Av','S_leg') or name.startswith(('Vs_','Vr_','s_strength_','s_minsteel','s_allow_','s_suggest_','DC_shear_','At_','Av_shear_','Acomb_','F_vt','F_long_','As_add_','DC_long_','Ash_hoop','Ash_prov','s_shrink'))):return ''
        if d['input'] or '(' in name:return ''
        # Aggregate/status checks are shown through the authoritative check register,
        # never the historic hard-coded source-layout test or an unqualified collector.
        if name.startswith(('Chk_','Status_','Group_')) or name in ('Known_checks_ok','Pending_checks_ok'):return ''
        self.equation_count+=1
        caption=d['caption'] or name.replace('_',' ')
        output='<article class="equation" id="eq-'+name+'"><span class="equation-id">('+str(self.equation_count)+')</span><p class="caption">'+escape(caption)+'</p>'
        override=name in self.e.engine.overrides
        if override:
            output+=('<p>Maximum spacing between adjacent continuous and added bar centers in the displayed span row; see the coordinate table above.</p>' if name in (self.e.spacing_values or {}) else
                '<p>Derived from the actual longitudinal coordinates and the common envelope of the entered transverse shapes; see the coordinate table above. Includes the fitted row translation.</p>')
            output+='<div class="equation-line">'+mathml(symbol(name)+'<mo>=</mo>'+quantity(self.e.engine.get(name),self.e.engine,d['unit']),True)+'</div>'
        else:
            ast=self.e.engine.defs[name]
            output+='<div class="equation-line">'+mathml(symbol(name)+'<mo>=</mo>'+expression(ast),True)+'</div>'
            if not pending(name,self.e):
                output+='<details class="working"><summary>Numeric substitution</summary><div class="equation-line">'+mathml(symbol(name)+'<mo>=</mo>'+expression(ast,self.e.engine,BY_NAME,substitute=True),True)+'</div><p class="caption">Operands are rounded for display; the calculation retains full precision. Conditional expressions use the active branch.</p></details>'
        reference=self.actual and (name in ('Av','S_leg') or name.startswith(('Vs_','Vr_','s_strength_','s_minsteel','s_allow_','s_suggest_','DC_shear_','At_','Av_shear_','Acomb_','F_vt','F_long_','As_add_','DC_long_','Ash_hoop','Ash_prov','s_shrink')))
        output+='<div class="result">'+('Uniform-cage reference: ' if reference else 'Result: ')+self.result(name)+'</div></article>'
        return output

    def inputs(self, definitions):
        rows=[]
        # Captions with historical numerical examples are not current input provenance.
        meanings={'b':'Cap cross-section width','h':'Cap depth','N_pile':'Number of equally spaced piles',
                  'S_pile':'Pile center-to-center spacing','D_pile':'Nominal pile width along the cap',
                  'E_end':'Nominal extension beyond the outer pile face','L_cap':'Cap length along the pile row'}
        for d in definitions:
            if not d['input']:continue
            if d['name'] in ('Bar_U','n_PU','n_BU'):continue
            n=d['name'];caption=meanings.get(n,d['caption'])
            source='Current case input / adopted assumption'
            if self.actual and n in ('beta_v','theta','alpha_v','Ao_factor'):
                source='Uniform-mode input only; actual-cage value is derived in the LRFD calculation working.'
            if n.startswith(('Mu_','MI_','MIII_','MDL_','DMLL_','Vu_')) or n=='Tu':
                caption={'Mu':'Factored strength moment magnitude','MI':'Service I moment magnitude',
                         'MIII':'Service III moment magnitude','MDL':'Signed permanent moment; tension positive',
                         'DMLL':'Fatigue live-load moment range','Vu':'Factored shear magnitude'}.get(n.split('_')[0],'Factored torque magnitude')
                source=force_basis(self.e.case,n) if not pending(n,self.e) else 'Pending; stored placeholder is not a verified design action'
            if pending(n,self.e):value=badge('PENDING')
            else:value=self.result(n)
            if n.startswith('SP_detail_') and not self.e.case['inputs']['Manual_spacing']:source+='; dormant spacing override'
            rows.append([mathml(symbol(n)),escape(caption),value,escape(source)])
        return table(['Symbol','Input / meaning','Value and units','Basis'],rows,'inputs',True) if rows else ''

    def checks_table(self, checks, criteria=False):
        rows=[]
        for c in checks:
            ratio=f'{c.ratio:.6g}' if isinstance(c.ratio,(int,float)) else str(c.ratio)
            basis=escape(c.basis).replace('\n','<br>')
            from .lrfd_checks import REPLACED_PREFIXES,REPLACED_KEYS
            replaced=self.actual and (c.key.startswith(REPLACED_PREFIXES) or c.key in REPLACED_KEYS)
            if criteria and not replaced and c.key in self.e.engine.defs and c.key not in self.e.engine.overrides and c.status!='REFERENCE':
                basis+='<details class="working"><summary>Check criterion</summary><div class="equation-line">'+mathml(expression(self.e.engine.defs[c.key]),True)+'</div></details>'
            rows.append([escape(c.label),badge(c.status),escape(ratio),basis])
        return table(['Check / region','Status','D/C','Basis / application'],rows,'output',True)

    def coordinates(self):
        e=self.e
        rows=[]
        for region in 'PB':
            for i,bar in enumerate(bar_positions(e,region),1):
                rows.append([region,i,bar['kind'],'#'+str(bar['bar']),f"{bar['x']:.6g}",f"{bar['y']:.6g}",f"{bar['diameter']:.6g}",'Additional' if bar['additional'] else 'Continuous'])
        note='<p>Coordinates: x across the cap from its left face; y above its underside. N uses top tension steel, P the continuous bottom steel at piles, and B continuous plus additional bottom steel between piles. Top-row equation coordinates are measured downward from the top face. Side steel is not counted in flexural area.</p>'
        if e.longitudinal_layout:
            fit=e.longitudinal_layout
            note+='<p><b>Actual cage fit:</b> '+('fitted' if fit['fitted'] else 'unresolved / failed trial')+f". Top family translation {fit['top_shift']:.6g} in; bottom family translation {fit['bottom_shift']:.6g} in. Maximum center spacing is obtained from adjacent sorted bar coordinates; the pile gap is retained.</p>"
        return note+'<details class="region"><summary>Bar coordinates and source of fitted row values</summary>'+table(['Region','Bar','Layer / kind','Size','x (in)','y (in)','Diameter (in)','Inventory'],rows,'inputs')+'</details>'

    def geometry(self):
        from . import visuals as v
        from .cage_3d import layout_3d
        from .geometry_dimensions import dimensions_figure,dimensions_html
        e=self.e
        views=[
            ('dimensions','Dimensioned plan and pile cross section',dimensions_figure,
             'Current cap length, width, depth, pile spacing and end distances. Hover dimension lines for feet and inches.'),
            ('elevation','Cap elevation',v.elevation_figure,
             'Cap elevation, pile stations and reinforcement; below-cap pile lengths are schematic.'),
            ('pile-section','Reinforcement cross section at a pile',lambda e:v.section_figure(e,'P'),
             'Pile-region cross section and continuous reinforcement.'),
            ('span-section','Reinforcement cross section between piles',lambda e:v.section_figure(e,'B'),
             'Between-pile cross section, retaining continuous bars and showing additional steel.'),
            ('reinforcement-plan','Reinforcement plan',v.reinforcement_plan_figure,
             'Reinforcement plan and cap stations for the current configuration.'),
            ('3d','Interactive three-dimensional cage',layout_3d,
             'Rotate to review the entered cage, pile clearances and open-bottom U-bars. Bar lines show centerlines; display thickness is schematic.'),
        ]
        content=('<section class="geometry-gallery" id="geometry"><h3>Geometry plots and dimensions</h3>'
                 '<p>Drawings and dimension tables use the current case at export. Open a view below to pan, zoom or hover for values. '
                 'Print / save PDF includes all views and the dimension tables. Regenerate the report after changing inputs.</p>'
                 '<ul class="geometry-links">'+''.join('<li><a href="#geometry-'+key+'">'+escape(title)+'</a></li>' for key,title,_,_ in views)+'</ul>')
        for key,title,draw,caption in views:
            content+='<details class="region geometry-view" id="geometry-'+key+'"'+(' open' if key=='dimensions' else '')+'><summary>'+escape(title)+'</summary>'
            content+=self.plot(draw(e),caption)
            if key=='dimensions':content+=dimensions_html(e)
            content+='</details>'
        return content+('<p>These are engineering schematics, not construction drawings. Development, anchorage and congestion remain separate checks. '
                        'See the reinforcement calculation for <a href="#steel">bar coordinates and effective depths</a>.</p></section>')

    def technical_content(self,key):
        from . import visuals as v
        e=self.e
        if key=='basis':
            return ('<p>Basis: the notebook’s C005 sectional equations and project assumptions, with the code references recorded beside their checks. '
                    'The actual-cage LRFD module uses AASHTO LRFD 10th edition (2024) for longitudinal tension, shear/torsion, face reinforcement and development. '
                    'Its settings, applicability limits and numerical working are recorded in the LRFD section. '
                    'Other inherited checks retain their stated basis. D-regions and a new structural analysis are outside this sectional model.</p>'+
                    self.geometry()+
                    table(['Analyzed geometry','Current geometry','Analysis consistency'],[[str(e.case['analysis']['geometry']),
                          ', '.join(f'{n} = {e.case["inputs"][n]:g}' for n in e.case['analysis']['geometry'] if n in e.case['inputs']),
                          'Changed: '+', '.join(e.stale) if e.stale else 'Current geometry matches the recorded analysis geometry']], 'discussion'))
        if key=='loads':
            audit=strength_audit(e.case)
            result=''.join('<p>'+escape(n)+'</p>' for n in audit['notes'])+table(audit['headers'],audit['rows'])+table(audit['provenance_headers'],audit['provenance'])
            if e.case['analysis'].get('xml_audit',{}).get('end_records'):
                from .force_diagrams import cap_force_figure,diagram_notice
                figure=cap_force_figure(e.case,show_resistance=True,evaluation=e)
                result+='<p>'+escape(diagram_notice(e.case))+'</p><p>'+escape(figure.layout.meta['resistance_notice'])+'</p>'+self.plot(figure,'Imported demands and current sectional resistances; use the load-state selector. Strength overlays are hidden for service demands. Click resistance legend entries to hide/show them.')
            else:result+='<p>No source member-end records were saved; a force diagram cannot be reconstructed from scalar envelopes.</p>'
            return result
        if key=='steel':
            content=v.reinforcement_summary_html(e)+('<p>View the <a href="#geometry-pile-section">pile-region section</a>, '
                '<a href="#geometry-span-section">between-pile section</a>, <a href="#geometry-reinforcement-plan">reinforcement plan</a> '
                'and <a href="#geometry-3d">three-dimensional cage</a> in Geometry plots and dimensions.</p>')
            content+=self.coordinates()
            rows=[[k,f'{BAR_DIAMETER[k]:g}',f'{BAR_AREA[k]:g}'] for k in BAR_AREA]
            content+=table(['US bar number','Diameter (in)','Area (in²)'],rows,'inputs')+'<p>Bar properties are the notebook’s source worksheet lookup. Ab(k) returns area and Db(k) returns diameter; unsupported sizes fail validation. ValidBar requires integer sizes 3–11; ValidCount requires nonnegative integers.</p>'
            return content
        if key=='flexure':return self.plot(v.results_figure(e),'Regional moment demand / resistance and service stress; transverse plots follow the selected actual/reference cage mode.')
        if key=='service':
            params,ast=e.engine.functions['S_allow']
            return ('<p>Cracked transformed rectangular section. N = negative/top tension; P = positive at piles; B = positive between piles. Service I is evaluated; Service III is evaluated only when its inputs are confirmed.</p>'
                    '<p class="caption">Allowable crack-control spacing function, inherited from the source sectional calculation.</p><div class="equation-line">'+
                    mathml(tag('mi','S_allow')+'<mo>(</mo>'+ '<mo>,</mo>'.join(symbol(p) for p in params)+'<mo>)</mo><mo>=</mo>'+expression(ast),True)+'</div>'+self.plot(v.optional_service_figure(e),'Service III and fatigue results or explicit pending status.'))
        if key=='fatigue':return '<p>Applicability, permanent stress, live-load range and load factor must be established. Unconfirmed placeholders do not establish zero demand or a passing check.</p>'
        if key=='shear':
            if self.actual:
                from .transverse_visuals import schedule_html,response_figure
                return '<p>Actual stations and member-segment action bounds govern. See <a href="#lrfd-actual">LRFD regions and calculation working</a> for equations, force combinations, development, anchorage and applicability. A pending anchorage result is not an accepted resistance.</p>'+schedule_html(e)+self.plot(response_figure(e),'Actual adjacent-station LRFD shear and sectional flexural response.')
            return v.hoop_explanation_html(e)+self.plot(v.hoop_figure(e),'Uniform reference hoop section; actual stationing is unresolved.')+v.spacing_html(e)
        if key=='torsion':return ('<p>Actual closed paths, combined shear/torsion reinforcement and longitudinal interaction are calculated in <a href="#lrfd-actual">LRFD regions and calculation working</a>. Open U-bars receive no closed-path torsion credit. Source member combinations are preserved, with conservative action bounds within each segment.</p>' if self.actual else '<p>Independent force maxima are combined conservatively; they are not a concurrent load case. The adopted effective torsion-area factor is explicit.</p>')
        if key=='details':
            components=steel_quantity_components(e)
            working='<h3>Reinforcing steel quantity</h3><p>Inventory estimate from the same drawn paths used by the notebook. Continuous volume = total continuous area × clear length; added volume sums each bar area × its straight, bend and tail lengths; transverse volume sums each entered shape area × centerline length × count (or the uniform reference hoop count when actual layout is disabled).</p>'
            working+=table(['Component','Steel volume (in³)'],[['Continuous bars',f'{components["continuous_in3"]:.6g}'],['Additional hooked span bars',f'{components["additional_in3"]:.6g}'],['Transverse bars',f'{components["transverse_in3"]:.6g}']], 'output')
            working+='<div class="equation-line">'+mathml(expression(parse('W_steel == (V_cont+V_add+V_trans)*490/1728')),True)+'</div><p class="caption">Volumes in in³; steel density 490 lb/ft³; 1 ft³ = 1728 in³. Result in lb.</p>'
            working+='<div class="equation-line">'+mathml(expression(parse(f'W_steel == ({components["continuous_in3"]:.12g}+{components["additional_in3"]:.12g}+{components["transverse_in3"]:.12g})*490/1728')),True)+'</div>'
            return v.side_steel_html(e)+v.clear_spacing_html(e)+working+table(['Quantity','Evaluated result','Basis'],[
                ['Estimated gross reinforcing steel',f'{e.weight_lb:.6g} lb','Drawn continuous bars and hooked additions; actual hoop/U outlines when enabled. Excludes laps, hoop closure extensions, end anchorage not drawn, and waste.'],
                ['Concrete volume',f'{e.value("V_cap","ft^3"):.6g} ft³','Gross rectangular cap, without pile deductions.']], 'output')
        return ''

    def section(self,s,definitions,index):
        key,title,_,purpose,inputs,output=s
        content=f'<details class="section" id="{key}"'+(' open' if index==1 else '')+f'><summary>{index}. {escape(title)}</summary><div class="section-body"><span class="step">STEP {index} OF {len(SECTIONS)}</span> <a class="backlink" href="#strategy">Back to calculation strategy</a>'
        content+=context(purpose,inputs,output)
        content+=self.technical_content(key)+self.inputs(definitions)
        # Repeated regional working is grouped, with the first region available
        # immediately and the other regions one click away.
        regional=key in ('flexure','service','fatigue')
        common=[d for d in definitions if not (regional and d['name'].endswith(('_N','_P','_B')))]
        content+=''.join(self.equation(d) for d in common)
        if regional:
            for region,label in [('N','Negative bending / top steel'),('P','Positive bending at piles'),('B','Positive bending between piles')]:
                content+='<details class="region"'+(' open' if region=='N' else '')+'><summary>'+region+' · '+label+'</summary>'
                content+=''.join(self.equation(d) for d in definitions if d['name'].endswith('_'+region))+'</details>'
        checks=[self.checks[d['name']] for d in definitions if d['name'] in self.checks and not d['name'].startswith('Status_overall')]
        if checks:content+='<h3>Results and application</h3>'+self.checks_table(checks,True)
        return content+'</div></details>'


def calculation_report(case=None, *, evaluation=None, search_result=None, search_filter=None, generated_at=None):
    """Return offline HTML for a fresh case (or an already evaluated bundle snapshot)."""
    e=evaluation if evaluation is not None else evaluate(case)
    r=Report(e)
    source=json.dumps(e.case,sort_keys=True,ensure_ascii=False,allow_nan=False)
    case_hash=sha256(source.encode()).hexdigest()
    formula_hash=sha256(json.dumps(DEFINITIONS,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    stamp=generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    title='Cap design calculation report'
    parts=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+title+' · '+escape(e.case['name'])+'</title><style>'+CSS+'</style></head><body>',
           '<nav class="toolbar" aria-label="Report controls"><a href="#geometry">Geometry plots</a><button id="expand-all">Expand all</button><button id="collapse-all">Collapse all</button><button id="print-report">Print / save PDF</button><span>Offline calculation snapshot</span></nav><main>',
           '<div class="eyebrow">ENGINEERING CALCULATIONS · CAP &amp; PILE DESIGN NOTEBOOK</div><h1>'+title+'</h1><p class="lead">'+escape(e.case['name'])+'</p>',
           '<p>Analysis: '+escape(str(e.case['analysis']['id']))+'<br>Generated: '+escape(str(stamp))+'</p>',
           context('Review cap sectional resistance, service behavior and reinforcement detailing.',
                 'Current saved case, imported force provenance, adopted factors and entered cage.',
                 'Equations, evaluated results, drawings and a complete check register.'),
           '<h2>Result summary</h2><p>'+badge(e.status)+'</p>',
           '<p>Region N: negative bending / top tension. Region P: positive bending at piles. Region B: positive bending between piles. G/L identify entered global/lower shear zones.</p>']
    ratios=[c for c in e.checks if isinstance(c.ratio,(int,float)) and c.status!='REFERENCE']
    governor=max(ratios,key=lambda c:c.ratio) if ratios else None
    parts.append(table(['Summary item','Snapshot result'],[
        ['Largest available D/C',f'{governor.ratio:.6g} — {governor.label} ({governor.status})' if governor else 'No available numerical ratio'],
        ['Failed checks',sum('FAIL' in c.status for c in e.checks)],
        ['Pending / conditional checks',sum('PENDING' in c.status or 'CONDITIONAL' in c.status for c in e.checks)],
        ['Cage mode','Actual hoop/U-bar station schedule' if r.actual else 'Uniform-cage reference'],
        ['Force basis',e.lrfd['source_notice'] if e.lrfd else 'Independent envelopes; not concurrent actions'],
        ['Analysis consistency','Geometry changed: '+', '.join(e.stale) if e.stale else 'Recorded analysis geometry matches current inputs']], 'output'))
    if e.issues:parts.append('<div class="notice"><b>Detailing findings</b><ul>'+''.join('<li>'+escape(issue)+'</li>' for issue in e.issues)+'</ul></div>')
    parts.append('<p>Available ratios do not close pending Service III, fatigue, anchorage, force-zone or detailing reviews. Green result tables identify outputs; only an explicit PASS denotes a passed check.</p>')
    parts.append('<h2 id="strategy">Calculation strategy</h2><ol class="links">'+''.join('<li><a href="#'+s[0]+'">'+escape(s[1])+'</a> — '+escape(s[3])+'</li>' for s in SECTIONS)+'</ol><ul class="flow"><li>Geometry &amp; actions</li><li>Steel coordinates</li><li>Section resistance</li><li>Service &amp; fatigue</li><li>Shear &amp; torsion</li><li>Detail review</li></ul>')
    parts.append('<noscript>Equations, results and tables work without JavaScript. Interactive plots and expand-all controls require JavaScript enabled in your browser.</noscript>')
    grouped=groups()
    for i,s in enumerate(SECTIONS,1):parts.append(r.section(s,grouped[s[0]],i))
    if e.lrfd:
        from .lrfd_views import working_html
        parts.append('<details class="section" id="lrfd-actual" open><summary>LRFD regions and calculation working · actual cage</summary>'+working_html(e,full=True)+'</details>')
    from .visuals import ratios_figure
    parts.append('<details class="section" id="register"><summary>Complete check register</summary><p>Authoritative statuses from this evaluation, including coordinate-based spacing, anchorage and actual-station checks. D/C is demand/resistance or the stated screening ratio; pending and reference entries are not successful design checks.</p>'+r.plot(ratios_figure(e),'All available check ratios; see the register for status and applicability.')+r.checks_table(e.checks)+'</details>')
    if search_result is not None:
        from .optimizer import same_design_basis,filter_candidates
        from .visuals import alternatives_figure
        if not same_design_basis(search_result.base_case,e.case):raise ValueError('Search inputs no longer match; run the search again before reporting alternatives.')
        options=search_filter or {'max_dc':1.0,'scope':'all','objective':search_result.config['objective']}
        indices=filter_candidates(search_result,**options)
        parts.append('<details class="section"><summary>Search alternatives · separate completed search</summary><p>Candidate results describe the completed search layouts, not subsequent manual cage edits. Force mode: '+escape(search_result.force_mode)+'. '+('Forces held unchanged; changed stiffness and self-weight were not reanalyzed.' if search_result.force_mode=='fixed' else 'Recorded analysis geometry matched.')+'</p>'+table(['Evaluated','Retained','Current filter matches','Exhaustive'],[[search_result.evaluated,len(search_result.candidates),len(indices),search_result.exhaustive]])+r.plot(alternatives_figure(search_result,indices=indices,dc_scope=options['scope'],max_dc=options['max_dc']),'Completed steel search alternatives under the selected filter.')+'</details>')
    parts.append('<details class="section" id="provenance"><summary>Snapshot provenance and calculation basis</summary><p>This cap report uses the notebook’s C005 formula set and current coordinate/detailing checks. It is not a recalculation by Mathcad or Blockpad. The imported pile analysis and minimum-tip review, when loaded, are exported separately in the full bundle.</p><p>Formula captions and check bases identify inherited source relations and adopted assumptions. The actual-cage LRFD module identifies its verified 10th-edition articles and FDOT 2026 criteria separately; this does not verify every inherited C005 relation against that edition. Displayed values use six significant figures; comparisons use full precision.</p><p class="meta">Case SHA-256 (canonical JSON): '+case_hash+'<br>Formula definition SHA-256: '+formula_hash+'</p><p>Report formatting basis: BPAD_Ref_V5.txt, §16 (guide v11). Snapshot is fixed at export; regenerate after editing the notebook inputs.</p><details class="working raw-source"><summary>Current case inputs and source record (omitted from print)</summary><pre class="meta">'+escape(json.dumps(e.case,indent=2,ensure_ascii=False))+'</pre></details></details>')
    from plotly.offline import get_plotlyjs
    body = number_tables('\n'.join(parts), report=True)
    return body+'\n'+'\n'.join(['</main>',*r.figures,'<script>'+get_plotlyjs()+'</script>','<script>'+JS+'</script></body></html>'])


def write_calculation_report(case, path, **kwargs):
    path=Path(path)
    markup=calculation_report(case,**kwargs)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(markup,encoding='utf-8')
    return path
