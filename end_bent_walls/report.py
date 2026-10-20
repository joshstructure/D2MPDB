"""Self-contained HTML calculation report (offline MathML and Plotly).

Layout follows standards/BPAD_Ref_V5.txt §16: project and scope, overview,
result summary, numbered technical sections with discussion (blue), input
(amber) and output (green) boxes, then the check register.
"""
from datetime import datetime, timezone
import html
from pier_cap.engine import parse
from .model import (SECTIONS, INPUTS, COMBINATIONS, STRENGTH, SERVICE, REFERENCES, SOURCES, CONFIRMATIONS,
                    COMBINATION_DATA, EXTERNAL_CAPTIONS, formula_trace, strap_table)
from .notation import symbol, mathml
from .reviews import review_html
from .schematics import schematic, meaning
from pier_cap.engine import UNITS
from . import visuals

STYLE = '''
:root{color-scheme:light}html{background:#ffffff}
body{font-family:"Times New Roman",serif;font-size:11pt;color:#1f2a36;background:#ffffff;max-width:1100px;margin:24px auto;padding:0 18px;line-height:1.35}
h1{font-size:16pt;margin:4px 0}h2{font-size:13pt;margin:26px 0 8px;border-bottom:2px solid #7189a6;padding-bottom:3px}
h3{font-size:11.5pt;margin:16px 0 6px}
.box{border:1px solid;border-radius:3px;margin:8px 0 12px;padding:0}.box>.hd{padding:5px 10px;font-weight:bold}.box>.bd{padding:8px 10px}
.discussion{border-color:#7189a6;background:#f1f5fa}.discussion>.hd{background:#dce7f3}
.inputs{border-color:#a78638;background:#fff8e9}.inputs>.hd{background:#f7e6b9}
.outputs{border-color:#6a9075;background:#eff7f1}.outputs>.hd{background:#dcece0}
table{border-collapse:collapse;width:100%;font-size:10pt;margin:4px 0}td,th{border:1px solid #c9d3dc;padding:4px 6px;text-align:left;vertical-align:top}
th{background:rgba(0,0,0,.05)}.num{text-align:right;font-variant-numeric:tabular-nums}
.eq{margin:6px 0 12px;overflow-x:auto}.eq math{font-size:12.5pt}.cap{color:#485969;font-size:9.5pt;margin:0 0 2px}
.ref{color:#7a2e2e;font-size:9pt}.PASS{color:#17633b;font-weight:bold}.FAIL{color:#bb3e39;font-weight:bold}
.PENDING{color:#a06500;font-weight:bold}.INFO,.CONFIRMED{color:#245674;font-weight:bold}
details>summary{cursor:pointer;color:#245c85}.toolbar{position:sticky;top:0;background:#fff;padding:6px 0;border-bottom:1px solid #dce5ec;z-index:5}
.toolbar button{margin-right:6px}.flow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:10pt}
.contents{margin:18px 0;padding:10px 14px;background:#f1f5fa;border:1px solid #c9d3dc;border-radius:3px}
.contents h2{margin:0 0 8px;border:0}.contents ul{columns:2;column-gap:24px;list-style:none;margin:0;padding:0}
.contents li{break-inside:avoid;margin:0 0 5px}.contents a{color:#245c85;text-decoration:none}.contents a:hover{text-decoration:underline}
details.report-section{margin:24px 0;scroll-margin-top:7rem}
details.report-section>summary{padding:6px 0;border-bottom:2px solid #7189a6;color:#1f2a36;font-weight:bold}
details.report-section>summary h2{display:inline;margin:0;padding:0;border:0;font-size:13pt}
details.report-section>summary:focus-visible,.contents a:focus-visible{outline:2px solid #245c85;outline-offset:4px}
.section-body{padding-top:8px}
@media(max-width:650px){.contents ul{columns:1}.toolbar button{margin-bottom:4px}}
.flow span{border:1px solid #7189a6;background:#fff;border-radius:3px;padding:4px 7px}.flow b{color:#7189a6}
.ebw-review{margin:4px 0;padding:4px 6px;background:#fff3d6;border-left:3px solid #805600;font-size:9.5pt}
details.qc{margin:-6px 0 14px;border-left:3px solid #a4bdce;background:#f7fafc;padding:3px 8px}
details.qc>summary{color:#1f2a36;font-size:10pt;list-style-position:outside}
details.qc>summary b{color:#245c85}details.qc[open]{background:#f1f5fa}
.qc-body{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;padding:8px 0 4px}
.qc-body figure{margin:0;flex:0 1 760px}.qc-body figcaption{font-size:9pt;color:#485969;margin-top:2px}
.qc-terms{flex:1 1 320px}.qc-terms table{font-size:9pt}.qc-terms td{padding:2px 5px}.qc-terms math{font-size:11pt}
.qc-note{font-size:9pt;color:#485969;margin:4px 0}
@media print{.toolbar,.contents{display:none}details.report-section>summary{list-style:none}details.report-section>summary::-webkit-details-marker{display:none}details.qc{break-inside:avoid}svg{max-width:100%}}
'''

REPORT_SCRIPT = '''
<script>
(() => {
  const sections = () => document.querySelectorAll('details.report-section');
  function resizePlots(root) {
    if (!window.Plotly) return;
    root.querySelectorAll('.js-plotly-plot').forEach(plot => {
      if (plot.getClientRects().length && plot._fullLayout) Plotly.Plots.resize(plot);
    });
  }
  window.setReportSections = open => {
    sections().forEach(section => { section.open = open; });
    if (open) requestAnimationFrame(() => resizePlots(document));
  };
  function revealSection(hash) {
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch (_) { return; }
    const section = document.getElementById(id);
    if (!section || !section.matches('details.report-section')) return;
    section.open = true;
    requestAnimationFrame(() => {
      resizePlots(section);
      section.querySelector('summary').focus({preventScroll: true});
      section.scrollIntoView({block: 'start'});
    });
  }
  document.querySelector('.contents').addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    revealSection(link.hash);
  });
  window.addEventListener('hashchange', () => revealSection(location.hash));
  document.addEventListener('toggle', event => {
    if (event.target.matches('details.report-section') && event.target.open)
      requestAnimationFrame(() => resizePlots(event.target));
  }, true);
  let printState;
  window.addEventListener('beforeprint', () => {
    if (printState) return;
    printState = Array.from(document.querySelectorAll('details:not(.qc)'), d => [d, d.open]);
    printState.forEach(([detail]) => { detail.open = true; });
    resizePlots(document);
  });
  window.addEventListener('afterprint', () => {
    if (printState) printState.forEach(([detail, open]) => { detail.open = open; });
    printState = null;
  });
  if (location.hash) revealSection(location.hash);
})();
</script>
'''

QC_NOTE = ('Under every equation: <b>What it represents</b> is always visible. Open it for a schematic drawn from the current case, '
           'with the defined quantity in red, and a legend of every term with its value and source.')

SECTION_TEXT = {
    'geometry': 'Arms are measured about the pile top. Vertical-load arms use the pile line shifted 3 in toward the fill, as SDG 3.13.2.N.3 requires the strap loading to include pile placement tolerance; that shift increases overturning toward the span.',
    'earth': 'Active Coulomb pressure acts on the full retained height from the cap soffit to the backwall crown over the cap length. The pedestrian load and the landing slab weight act as uniform surcharges (LRFD 3.11.6.1). No vehicular surcharge applies (D-015).',
    'bearing': 'DC, PL and wind at the bearings come from the selected FBMP export. Temperature fall and beam shrinkage pull the bearing tops toward the span through the elastomeric pads (upper-bound shear modulus), adding to the earth pressure.',
    'dead': 'Self-weights of the cap, pedestals, cheek walls and backwall enter the overturning sum with the maximum or minimum factor according to their arm. The landing slab reaction is counted for gravity design only (D-017).',
    'strap': 'The single pile row is effectively pinned (FBMP fixity 0.10), so straps attached to the backwall resist the overturning moment about the pile top. The design strap force is the larger of the total horizontal force and the moment-equilibrium force M / y_strap. When M / y_strap exceeds H, the piles supply the difference at the pile top.',
    'bw_load': 'The backwall is a vertical cantilever from the construction joint. Strap slack: soil pressure causes fill-face tension. Strap engaged: the strap pull at z above the joint exceeds the soil moment and causes span-face tension. Both states are designed.',
    'materials': 'Material constants for the rectangular 1-ft strip design.',
    'bw_FF': 'Fill-face vertical steel resists the cantilever soil moment (strap slack).',
    'bw_SF': 'Span-face vertical steel resists the reversed moment when the strap carries the end-bent horizontal load.',
    'bw_joint': 'Shear, interface shear across the cap/backwall construction joint (SDG 1.15 factors), and distribution steel.',
    'ck': 'The cheek walls retain no fill (D-018). They are designed for transverse wind as 1-ft vertical cantilever strips. With the single-mat option, tangent vertical/horizontal bars have their combined envelope centered; the weaker wind direction controls effective depth and shrinkage steel includes both face requirements. Anchorage and lug load-path checks remain pending.',
    'ck_sec': 'Cheek wall strip design for wind acting in either direction. The selected reinforcement layout is shown in Figure B8.',
    'cap': 'Actions created by the walls, eccentric bearings and straps are not in the FBMP cap model. Torsion is screened against the LRFD threshold below which it may be neglected.',
}

FIGURE_AFTER = {'geometry': ['section', 'plan'], 'strap': ['waterfall', 'strap'], 'bw_load': ['backwall'],
                'bw_joint': ['reinforcement'], 'ck': ['cheek'], 'cap': ['cap']}


def _box(kind, title, body):
    return f'<div class="box {kind}"><div class="hd">{html.escape(title)}</div><div class="bd">{body}</div></div>'


def _report_section(key, title, body):
    return (f'<details class="report-section" id="section-{key}" open>'
            f'<summary><h2>{html.escape(title)}</h2></summary>'
            f'<div class="section-body">{body}</div></details>')


def _names(ast, out):
    if ast[0] == 'name':
        out.add(ast[1])
    elif ast[0] in ('bin',):
        _names(ast[2], out); _names(ast[3], out)
    elif ast[0] == 'unary':
        _names(ast[2], out)
    elif ast[0] == 'call':
        for a in ast[2]:
            _names(a, out)
    return out


def _refs(keys):
    return '; '.join(f'{REFERENCES[k]["code"]} {REFERENCES[k]["article"]}' for k in keys if k in REFERENCES)


def qc_blocks(e):
    """Collapsible QC row for every formula: meaning (always visible), schematic and term legend."""
    defs = {d['name']: d for d in e.definitions}
    titles = dict(SECTIONS)
    blocks = {}
    for d in e.definitions:
        svg, drawing = schematic(e, d['name'])
        rows = []
        names = []
        for n in sorted(_names(parse(d['expr']), set())):
            if n not in UNITS and n not in names:
                names.append(n)
        for n in names:
            value = e.text(n, 4) if n in e.units else ''
            if n in INPUTS:
                src = e.case['sources'].get(n, {})
                what, where = INPUTS[n]['caption'], f'input · {src.get("source", INPUTS[n]["source"])} ({src.get("status", INPUTS[n]["status"])})'
            elif n in defs:
                what, where = defs[n]['caption'], f'calculated · {titles[defs[n]["section"]]}'
            else:
                what, where = EXTERNAL_CAPTIONS.get(n, ''), 'AASHTO M31 nominal bar dimensions'
            rows.append(f'<tr><td>{mathml(symbol(n))}</td><td>{html.escape(what)}</td><td class="num">{html.escape(value)}</td>'
                        f'<td>{html.escape(where)}</td></tr>')
        legend = ('<div class="qc-terms"><table><tr><th>Term</th><th>Meaning</th><th>Value</th><th>Source</th></tr>'
                  + ''.join(rows) + '</table></div>') if rows else '<div class="qc-terms"><p class="qc-note">Constant; no input terms.</p></div>'
        text = meaning(d['name']) or d['caption']
        caption = f'<figcaption>{html.escape(drawing)}</figcaption>' if drawing and drawing != text else ''
        figure = f'<figure>{svg}{caption}</figure>' if svg else ''
        blocks[d['name']] = (f'<details class="qc"><summary><b>What it represents:</b> {html.escape(text)}</summary>'
                             f'<div class="qc-body">{figure}{legend}</div></details>')
    return blocks


def _input_rows(e, names):
    rows = []
    for name in sorted(names, key=lambda n: list(INPUTS).index(n)):
        spec = INPUTS[name]
        src = e.case['sources'].get(name, {})
        unit = spec['unit'] if spec['unit'] not in (None, 'bar') else ''
        value = e.case['inputs'][name]
        value = f'#{int(value)}' if spec['unit'] == 'bar' else f'{value:g}'
        rows.append(f'<tr><td>{mathml(symbol(name))}</td><td class="num">{value} {html.escape(unit)}</td>'
                    f'<td>{html.escape(spec["caption"])}</td><td>{html.escape(src.get("source", spec["source"]))}'
                    f' <i>({html.escape(src.get("status", spec["status"]))})</i></td></tr>')
    return ('<table><tr><th>Symbol</th><th>Value</th><th>Meaning</th><th>Source / basis</th></tr>' + ''.join(rows) + '</table>') if rows else ''


def _status_cell(status):
    css = 'FAIL' if 'FAIL' in status else 'PENDING' if 'PENDING' in status else 'PASS' if 'PASS' in status else status.split()[0]
    return f'<span class="{css}">{html.escape(status)}</span>'


def strap_table_html(e, combo):
    rows = strap_table(e, combo['key'])
    body = ''.join(
        f'<tr><td>{html.escape(r["label"])}</td><td>{"Horizontal" if r["kind"] == "H" else "Vertical"}</td>'
        f'<td class="num">{r["force_kip"]:.2f}</td><td class="num">{r["arm_ft"]:.3f}</td><td class="num">{r["moment"]:.2f}</td>'
        f'<td class="num">{r["factor"]:g}</td><td class="num">{r["factored_force"]:.2f}</td><td class="num">{r["factored_moment"]:.2f}</td>'
        f'<td>{html.escape(r["basis"])}</td></tr>' for r in rows)
    k = combo['key']
    total = (f'<tr><th colspan="6">Totals</th><th class="num">H = {e.value("H_" + k):.2f}</th><th class="num">M = {e.value("M_" + k):.2f}</th>'
             f'<th>e = {e.value("e_" + k):.3f} ft; F = max(H, M/y) = {e.value("F_str_" + k):.2f} kip; {e.value("f_str_" + k):.3f} klf</th></tr>')
    return ('<table><tr><th>Load</th><th>Direction</th><th>Force (kip)</th><th>Arm (ft)</th><th>Moment (kip-ft)</th>'
            '<th>γ</th><th>γ·H (kip)</th><th>γ·M (kip-ft)</th><th>Factor basis</th></tr>' + body + total + '</table>')


def summary_html(e):
    gov = max(STRENGTH, key=lambda c: e.value('f_str_' + c['key']))
    plan = (f'<table><tr><th>Soil reinforcement attached to the backwall</th><th>Service</th><th>Factored</th></tr>'
            f'<tr><td>Load per foot along the backwall (SDM 12.3.F)</td><td class="num"><b>{e.value("f_str_s"):.2f} kip/ft</b></td>'
            f'<td class="num"><b>{e.value("f_str_u"):.2f} kip/ft</b> ({html.escape(gov["label"])})</td></tr>'
            f'<tr><td>Total for the {e.value("L_bw", "ft"):.2f} ft backwall</td><td class="num">{e.value("F_str_s"):.1f} kip</td>'
            f'<td class="num">{e.value("F_str_u"):.1f} kip</td></tr>'
            f'<tr><td>Strap elevation</td><td colspan="2">{e.value("z_strap", "ft"):.2f} ft above the cap top '
            f'({e.value("y_strap", "ft"):.2f} ft above the pile top)</td></tr></table>'
            '<p><b>Plan note (SDM 12.3.F):</b> The soil reinforcement attached to the backwall shall be designed by a Specialty Engineer '
            'for the service and factored loads as shown using the design criteria for permanent MSE walls. Cost of furnishing and '
            'installing the soil reinforcement is considered incidental to the cost of the end bent.</p>'
            '<p><b>Plan note (SDG 1.15):</b> Intentionally roughen the backwall and cheek-wall construction joints to a minimum '
            '1/4-inch amplitude.</p>')
    numeric = [c for c in e.checks if isinstance(c.ratio, (int, float))]
    top = sorted(numeric, key=lambda c: -c.ratio)[:6]
    rows = ''.join(f'<tr><td>{html.escape(c.group)} · {html.escape(c.label)}</td><td class="num">{c.ratio:.3f}</td><td>{_status_cell(c.status)}</td></tr>' for c in top)
    pending = [c for c in e.checks if 'PENDING' in c.status]
    pend = ''.join(f'<li>{html.escape(c.label)}</li>' for c in pending)
    finding = ''
    worst = max(COMBINATIONS, key=lambda c: e.value('V_pile_' + c['key']))
    if e.value('V_pile_' + worst['key']) > 0.5:
        finding = (f'<p><b>Strap location:</b> the resultant lies {e.value("e_" + gov["key"], "ft"):.2f} ft above the pile top, above the '
                   f'strap at {e.value("y_strap", "ft"):.2f} ft, so moment equilibrium governs the strap load and the piles supply up to '
                   f'{e.value("V_pile_" + worst["key"]):.1f} kip ({html.escape(worst["label"])}) toward the span. Raising the strap toward '
                   'the resultant reduces both. The pile-tolerance shift required by SDG 3.13.2.N.3 is the main contributor.</p>')
    return (_box('outputs', 'Result summary · tie-back loads for the plans', plan + finding) +
            _box('outputs', 'Largest check ratios', f'<p>{html.escape(e.status)}</p><table><tr><th>Check</th><th>Ratio</th><th>Status</th></tr>{rows}</table>'
                 + (f'<p><b>Pending items</b></p><ul>{pend}</ul>' if pend else '')))


def checks_html(e, qc=None):
    trace = {t['name']: t for t in formula_trace(e)}
    qc = qc or {}
    rows = []
    for c in e.checks:
        ratio = f'{c.ratio:.3f}' if isinstance(c.ratio, (int, float)) else '—'
        details = ''.join(f'<div class="eq">{trace[n]["mathml"]}</div>{qc.get(n, "")}' for n in c.names if n in trace)
        refs = _refs(c.refs)
        body = (f'<p>{html.escape(c.basis)}</p>' + (f'<p class="ref">{html.escape(refs)}</p>' if refs else '') + details
                + (f'<p><i>{html.escape(c.note)}</i></p>' if c.note else ''))
        rows.append(f'<tr><td>{html.escape(c.group)}</td><td>{html.escape(c.label)}{review_html(c)}<details><summary>Equation &amp; values</summary>{body}</details></td>'
                    f'<td>{html.escape(c.demand)}</td><td>{html.escape(c.capacity)}</td><td class="num">{ratio}</td><td>{_status_cell(c.status)}</td></tr>')
    return ('<table><tr><th>Group</th><th>Check</th><th>Demand / required</th><th>Capacity / limit</th><th>Ratio</th><th>Status</th></tr>'
            + ''.join(rows) + '</table>')


def build_report(e, title=None):
    import plotly.offline
    title = title or 'End Bent Backwall, Cheek Walls and Tie-Back Straps'
    trace = formula_trace(e)
    qc = qc_blocks(e)
    figures = {name: fn(e) for name, fn in visuals.FIGURES}
    toggle = lambda sel, state: f"document.querySelectorAll('{sel}').forEach(d=>d.open={state})"
    parts = ['<div class="toolbar"><button onclick="setReportSections(true)">Expand sections</button>'
             '<button onclick="setReportSections(false)">Collapse sections</button>'
             f'<button onclick="{toggle("details.qc", "true")}">Open all QC schematics</button>'
             f'<button onclick="{toggle("details.qc", "false")}">Close all QC schematics</button>'
             '<button title="Prints all sections, equations and tables; QC schematics print as currently shown" '
             'onclick="window.print()">Print / save PDF</button></div>',
             f'<p><b>D2 I-95 Pedestrian Bridge · FDOT District 2</b></p><h1>{html.escape(title)}</h1>',
             f'<p>{html.escape(e.case["name"])}<br>Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} · '
             f'{html.escape(SOURCES["editions"])}</p>']
    flow = ' <b>→</b> '.join(f'<span>{s}</span>' for s in (
        'Geometry &amp; arms', 'Earth pressure &amp; surcharges', 'Bearing actions', 'Dead loads', 'Combinations',
        'Overturning about the pile top', 'Tie-back strap load', 'Backwall · slack &amp; engaged', 'Cheek walls (wind)', 'Cap supplement', 'Checks'))
    contents = [('overview', 'Overview'), ('results', 'Result summary'), *SECTIONS,
                ('checks', '14. Check register'), ('sources', '15. Sources, decisions and confirmations')]
    parts.append('<nav class="contents" aria-label="Table of contents"><h2>Contents</h2><ul>'
                 + ''.join(f'<li><a href="#section-{key}">{html.escape(heading)}</a></li>' for key, heading in contents)
                 + '</ul></nav>')
    parts.append(_report_section('overview', 'Overview', _box('discussion', 'Objective, method and scope',
        '<p>Determine the tie-back strap loads for the end bents and design the backwall and cheek walls. This replaces the template '
        'Mathcad backwall/strap calculation with project data: two FIB-36 bearings on a 17\'-8" cap, four 18 in square piles (effectively pinned), '
        'a 4 in MSE landing slab on the backwall, pedestrian loading only and FDOT January 2026 criteria.</p>'
        f'<div class="flow">{flow}</div>'
        '<p>Outside this calculation: strap/pullout design (Specialty Engineer), revised FBMP analysis, final wall geometry (D-005) and detailing.</p>'
        f'<p>{QC_NOTE}</p>')))
    parts.append(_report_section('results', 'Result summary', summary_html(e)))
    by_section = {}
    for t in trace:
        by_section.setdefault(t['section'], []).append(t)
    for key, heading in SECTIONS:
        items = by_section.get(key, [])
        names = set()
        for d in e.definitions:
            if d['section'] == key:
                _names(parse(d['expr']), names)
        inputs = [n for n in names if n in INPUTS]
        section = [_box('discussion', 'Purpose', f'<p>{html.escape(SECTION_TEXT.get(key, ""))}</p>')]
        if inputs:
            section.append(_box('inputs', 'Inputs', _input_rows(e, inputs)))
        def equations(subset):
            return ''.join(f'<p class="cap">{html.escape(t["caption"])}' + (f' <span class="ref">({html.escape(_refs(t["refs"]))})</span>' if t['refs'] else '')
                           + f'</p><div class="eq">{t["mathml"]}</div>{qc.get(t["name"], "")}' for t in subset)
        if key in ('strap', 'bw_load'):
            if key == 'strap':
                tables = ''.join(f'<details{" open" if c["key"] == "STRI" else ""}><summary><b>{html.escape(c["label"])}</b> overturning table</summary>'
                                 f'{strap_table_html(e, c)}</details>' for c in COMBINATIONS)
                section.append(_box('outputs', 'Overturning tables by combination', '<p>' + html.escape(COMBINATION_DATA['basis']) + '</p>' + tables))
            grouped = [t for t in items if not any(t['name'].endswith('_' + c['key']) for c in COMBINATIONS)]
            if key == 'bw_load':
                section.append(equations([t for t in grouped if t['name'].endswith('_bw') and not t['name'].startswith('V_u')]))
            for c in COMBINATIONS:
                subset = [t for t in items if t['name'].endswith('_' + c['key'])]
                section.append(f'<details{" open" if c["key"] == "STRI" else ""}><summary><b>{html.escape(c["label"])}</b> · '
                               f'{len(subset)} equations</summary>{equations(subset)}</details>')
            section.append(equations([t for t in grouped if not (key == 'bw_load' and t['name'].endswith('_bw') and not t['name'].startswith('V_u'))]))
        else:
            section.append(equations(items))
        for name in FIGURE_AFTER.get(key, []):
            section.append(figures[name].to_html(full_html=False, include_plotlyjs=False))
        parts.append(_report_section(key, heading, ''.join(section)))
    parts.append(_report_section('checks', '14. Check register',
                 figures['ratios'].to_html(full_html=False, include_plotlyjs=False) + checks_html(e, qc)))
    conf = ''.join(f'<li>{"Confirmed" if e.case["confirmations"][k] else "<b>Pending</b>"}: {html.escape(text)}<br><small>{html.escape(e.case.get("confirmation_evidence", {}).get(k, {}).get("note", "No project evidence recorded."))}</small></li>' for k, text in CONFIRMATIONS.items())
    receipts = ''.join(f'<tr><td>{html.escape(r["source_id"])}</td><td>{html.escape(r["filename"])}</td><td><code>{r["sha256"][:16]}…</code></td>'
                       f'<td>{"matches register" if r["matches_register"] else "<b>differs from register</b>"}</td><td>{html.escape("; ".join(r["notes"]))}</td></tr>'
                       for r in e.case.get('receipts', {}).values())
    parts.append(_report_section('sources', '15. Sources, decisions and confirmations', _box('inputs', 'Registered sources and decisions',
        f'<p>Decisions: {", ".join(SOURCES["decisions"])} (project_current/decisions.md).</p>'
        + (f'<table><tr><th>Source</th><th>File</th><th>SHA-256</th><th>Register</th><th>Notes</th></tr>{receipts}</table>' if receipts else
           '<p>Inputs use the 16 October reviewed project snapshot embedded in the notebook. The available FBMP XML predates the selected cap cases. Current journal bytes match accepted T009 but differ from the older source-register entry. These limitations remain visible below.</p>')
        + f'<ul>{conf}</ul>')))
    body = ''.join(parts) + REPORT_SCRIPT
    try:
        from report_cards import cards_html, cite_data, prose_pieces
    except ImportError:  # portable package built without the cards module
        pass
    else:
        body += cards_html(cite_data(REFERENCES, extra_pieces=prose_pieces(body)))
    script = f'<script type="text/javascript">{plotly.offline.get_plotlyjs()}</script>'
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{STYLE}</style>{script}</head><body>{body}</body></html>')


def write_report(e, path):
    from pathlib import Path
    Path(path).write_text(build_report(e), encoding='utf-8')
    return Path(path)
