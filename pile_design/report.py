"""Self-contained HTML calculation report for the pile analysis and design (offline MathML and Plotly).

Layout follows standards/BPAD_Ref_V5.txt section 16: project and scope, overview, result
summary, numbered technical sections with discussion (blue), input (amber) and output (green)
boxes, then the check register, pending items and the registered sources.
"""
from datetime import datetime, timezone
import html
import math
from pier_cap.engine import parse
from .model import SECTIONS, INPUTS, REFERENCES, SOURCES, CONFIRMATIONS, formula_trace
from .notation import symbol, mathml
from .reviews import review_html
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
@media print{.toolbar,.contents{display:none}details.report-section>summary{list-style:none}details.report-section>summary::-webkit-details-marker{display:none}svg{max-width:100%}}
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
    printState = Array.from(document.querySelectorAll('details'), d => [d, d.open]);
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

PSC_SECTIONS = ('geometry', 'psc_mat', 'psc_axial', 'psc_flex', 'psc_tension', 'psc_shear', 'psc_service', 'geotech')
PIPE_SECTIONS = ('geometry', 'pipe_sec', 'pipe_axial', 'pipe_flex', 'pipe_comb', 'pipe_tension', 'pipe_shear', 'geotech')

SECTION_TEXT = {
    'geometry': 'The pile layout comes from the FB-MultiPier (FBMP) export: pile count, spacing, cutoff elevation (pile head) and ground (top of soil layer 1). '
                'Spacing is checked against SDG 3.5.4 (3.0 diameters at and below the design ground). The drag load DR from downdrag is a nominal load per pile '
                'supplied by the geotechnical engineer; it is added to the FBMP axial force with the LRFD Table 3.4.1-1 load factor at every station (conservative below the neutral plane) '
                'and is excluded from the Factored Design Load of the Pile Data Table.',
    'psc_mat': 'The pile is one of the FDOT Standard Plans Index 455 square sections with the selected strand pattern. Prestress losses are an input fraction of the jacking force '
               '(calibrated to the FBMP prestress). Gross properties ignore the chamfers. The decompression strain of the concrete is added to the strand strain in the strain-compatibility sweep.',
    'psc_axial': 'Axial compression is limited to the maximum factored resistance of a spiral-reinforced prestressed member, Pr = φ Pn,max with Pn,max = 0.85 Po (LRFD 5.6.4.4).',
    'psc_flex': 'Combined axial load and bending is evaluated two ways and the larger ratio governs. (1) LRFD 5.6.4.5 for biaxial flexure using the uniaxial interaction curve '
                '(Eq. 5.6.4.5-1 when Pu is at least 0.10 φ f′c Ag, Eq. 5.6.4.5-3 otherwise). (2) The resultant moment against the strain-compatibility curve computed for the '
                'bending axis of the resultant moment, along the ray through the demand.',
    'psc_tension': 'Uplift is resisted by the prestressing strand alone (no nonprestressed steel). The check uses the largest strength uplift anywhere along the pile; the drag load does not relieve it. '
                   'The pile-to-cap connection for uplift is a separate prerequisite.',
    'psc_shear': 'Shear uses the LRFD 5.7.3.4.2 general procedure at the record with the largest Vu/φVn. The spiral crosses the shear plane twice. '
                 'Longitudinal strain εs is taken from Eq. 5.7.3.4.2-4 with the strand on the flexural tension half of the section.',
    'psc_service': 'Service I stresses are checked after losses on the section corner for the record with the largest compression and the record with the largest tension, '
                   'with the Service I axial force including the drag load at γ = 1.0.',
    'pipe_sec': 'Noncomposite steel pipe; open or plugged, but no concrete fill is assumed. Corrosion allowance reduces the design wall.',
    'pipe_axial': 'Axial compression follows LRFD 6.9.4.1.1 with the effective length K(Lu + Lfix); the depth to fixity is from LRFD C10.7.3.13.4. '
                  'FBMP’s nonlinear p-y analysis is the preferred second-order method; this column check is a cross-check.',
    'pipe_flex': 'Flexure of the round tube is classified by D/t against 0.07 E/Fy and 0.31 E/Fy (LRFD 6.12.2.2.3).',
    'pipe_comb': 'The combined axial load and flexure check is LRFD Eq. 6.9.2.2.1-1 / -2 with the resultant moment of the two bending axes (the section is axisymmetric). '
                 'For net uplift the matching axial resistance is the tension resistance.',
    'pipe_tension': 'Tension yielding of the gross section, Eq. 6.8.2.1-1. The largest strength uplift anywhere along the pile is used.',
    'pipe_shear': 'Shear buckling strength of a round tube per LRFD 6.12.1.2.3b, with the shear span taken as the length above ground unless edited.',
    'geotech': 'The Factored Design Load, downdrag and scour resistance give the required Nominal Bearing Resistance by SDG Eq. 3-1. The resistance factor is from SDG Table 3.5.7-1 '
               '(0.75 default for Pile Data Tables). For prestressed concrete piles the result is compared with the maximum driving resistance of Table 3.5.13-1.',
}

FIGURE_AFTER = {'geometry': ['section', 'elevation']}


def _box(kind, title, body):
    return f'<div class="box {kind}"><div class="hd">{html.escape(title)}</div><div class="bd">{body}</div></div>'


def _report_section(key, title, body):
    return (f'<details class="report-section" id="section-{key}" open>'
            f'<summary><h2>{html.escape(title)}</h2></summary>'
            f'<div class="section-body">{body}</div></details>')


def _names(ast, out):
    if ast[0] == 'name':
        out.add(ast[1])
    elif ast[0] == 'bin':
        _names(ast[2], out)
        _names(ast[3], out)
    elif ast[0] == 'unary':
        _names(ast[2], out)
    elif ast[0] == 'call':
        for a in ast[2]:
            _names(a, out)
    return out


def _refs(keys):
    return '; '.join(f'{REFERENCES[k]["code"]} {REFERENCES[k]["article"]}' for k in keys if k in REFERENCES)


def _status_cell(status):
    css = 'FAIL' if 'FAIL' in status else 'PENDING' if 'PENDING' in status else 'PASS' if 'PASS' in status else status.split()[0]
    return f'<span class="{css}">{html.escape(status)}</span>'


def _input_rows(e, names):
    rows = []
    for name in sorted(names, key=lambda n: list(INPUTS).index(n)):
        spec = INPUTS[name]
        src = e.case['sources'].get(name, {})
        unit = visuals.unit_label(spec['unit']) if spec['unit'] not in (None, 'bar') else ''
        value = visuals.input_text(name, e.case['inputs'].get(name))
        rows.append(f'<tr><td>{mathml(symbol(name))}</td><td class="num">{html.escape(value)} {html.escape(unit)}</td>'
                    f'<td>{html.escape(spec["caption"])}</td><td>{html.escape(src.get("source", spec["source"]))}'
                    f' <i>({html.escape(src.get("status", spec["status"]))})</i></td></tr>')
    return ('<table><tr><th>Symbol</th><th>Value</th><th>Meaning</th><th>Source / basis</th></tr>' + ''.join(rows) + '</table>') if rows else ''


def _equations(subset):
    return ''.join(f'<p class="cap">{html.escape(t["caption"])}' + (f' <span class="ref">({html.escape(_refs(t["refs"]))})</span>' if t['refs'] else '')
                   + f'</p><div class="eq">{t["mathml"]}</div>' for t in subset)


def checks_html(e):
    trace = {t['name']: t for t in formula_trace(e)}
    rows = []
    for c in e.checks:
        ratio = f'{c.ratio:.3f}' if isinstance(c.ratio, (int, float)) else '—'
        details = ''.join(f'<div class="eq">{trace[n]["mathml"]}</div>' for n in c.names if n in trace)
        refs = _refs(c.refs)
        body = (f'<p>{html.escape(c.basis)}</p>' + (f'<p class="ref">{html.escape(refs)}</p>' if refs else '') + details
                + (f'<p><i>{html.escape(c.note)}</i></p>' if c.note else ''))
        rows.append(f'<tr><td>{html.escape(c.group)}</td><td>{html.escape(c.label)}{review_html(c)}<details><summary>Equation &amp; values</summary>{body}</details></td>'
                    f'<td>{html.escape(c.demand)}</td><td>{html.escape(c.capacity)}</td><td class="num">{ratio}</td><td>{_status_cell(c.status)}</td></tr>')
    return ('<table><tr><th>Group</th><th>Check</th><th>Demand / required</th><th>Capacity / limit</th><th>Ratio</th><th>Status</th></tr>'
            + ''.join(rows) + '</table>')


def summary_html(e):
    v, p = e.value, e.case['inputs']
    family = 'Square prestressed concrete pile' if e.family == 'psc' else 'Steel pipe pile'
    g, m = visuals.structural_governing_check(e), visuals.max_ratio_check(e)
    strength_dc = getattr(e, 'strength_dc', 0.0)
    max_ratio = getattr(e, 'max_ratio', strength_dc)
    nbr = f'{v("NBR_tons"):.1f} tons required'
    if e.family == 'psc':
        nbr += f' against the Table 3.5.13-1 maximum of {v("R_drive_tons"):.0f} tons ({v("NBR_tons") / v("R_drive_tons"):.2f})'
    else:
        nbr += ' (Table 3.5.13-1 covers prestressed concrete piles only)'
    plan = (f'<table><tr><th>Item</th><th>Result</th></tr>'
            f'<tr><td>Support and pile</td><td>{html.escape(e.case["support"])} · {html.escape(family)} · {e.data_table["Pile Size & Type"]}</td></tr>'
            f'<tr><td>Governing structural check</td><td><b>{strength_dc:.3f}</b>' + (f' · {html.escape(g.group)} · {html.escape(g.label)}' if g else '') + '</td></tr>'
            f'<tr><td>Largest ratio of any check</td><td>{max_ratio:.3f}' + (f' · {html.escape(m.label)}' if m else '') + '</td></tr>'
            f'<tr><td>Nominal Bearing Resistance (SDG Eq. 3-1)</td><td>{html.escape(nbr)}</td></tr>'
            f'<tr><td>Downdrag used</td><td>{p["DD_tons"]:g} tons per pile = {v("DD"):.1f} kip; factored drag load {v("DR_str"):.1f} kip at the strength limit states '
            f'(γ<sub>DR</sub> = {p["gamma_DR_str"]:g}) and {v("DR_ser"):.1f} kip at Service I; excluded from the Factored Design Load</td></tr>'
            f'<tr><td>Factored Design Load (Pile Data Table, column I)</td><td>{v("FDL_tons"):.1f} tons</td></tr></table>')
    numeric = [c for c in e.checks if isinstance(c.ratio, (int, float)) and c.group != 'Prerequisites']
    top = sorted(numeric, key=lambda c: -c.ratio)[:8]
    rows = ''.join(f'<tr><td>{html.escape(c.group)} · {html.escape(c.label)}</td><td class="num">{c.ratio:.3f}</td><td>{_status_cell(c.status)}</td></tr>' for c in top)
    return (_box('outputs', 'Result summary', plan) +
            _box('outputs', 'Largest check ratios', f'<p>{html.escape(e.status)}</p><table><tr><th>Check</th><th>Ratio</th><th>Status</th></tr>{rows}</table>'))


def curve_table_html(curve, title):
    def cell(value, places):
        return '∞' if not math.isfinite(value) else f'{value:.{places}f}'
    rows = ''.join(
        f'<tr><td class="num">{cell(c, 2)}</td><td class="num">{pn:.1f}</td><td class="num">{mn:.1f}</td><td class="num">{ph:.3f}</td><td class="num">{pr:.1f}</td><td class="num">{mr:.1f}</td></tr>'
        for c, pn, mn, ph, pr, mr in zip(curve['c'], curve['Pn'], curve['Mn'], curve['phi'], curve['Pr'], curve['Mr']))
    return (f'<details><summary>{html.escape(title)} · {len(curve["c"])} points</summary>'
            '<table><tr><th>c (in)</th><th>P<sub>n</sub> (kip)</th><th>M<sub>n</sub> (kip-ft)</th><th>φ</th><th>P<sub>r</sub> = φP<sub>n</sub> (kip)</th>'
            f'<th>M<sub>r</sub> = φM<sub>n</sub> (kip-ft)</th></tr>{rows}</table></details>')


def _demands_section(e, figures):
    p, v = e.case['inputs'], e.value
    if not e.records:
        return _box('discussion', 'FBMP demands', '<p>No FBMP results are loaded in this case. Upload the pile XML in Cell 1 and recalculate.</p>')
    analysis = e.case.get('analysis') or {}
    intro = _box('discussion', 'Purpose',
                 '<p>Every element-end record of the FBMP export is carried into the checks: axial force (compression positive, J-end already reversed), '
                 'resultant shear and resultant moment. The drag load is added to the axial force: P<sub>u</sub> = P<sub>FBMP</sub> + γ<sub>DR</sub>·DD with '
                 f'DD = {v("DD"):.1f} kip, γ<sub>DR</sub> = {p["gamma_DR_str"]:g} at the strength limit states and {p["gamma_DR_ser"]:g} at Service I '
                 '(LRFD Table 3.4.1-1; 10.7.1.6.2 sets DR = 0 for the geotechnical limit state).</p>'
                 f'<p>Source: <b>{html.escape(analysis.get("filename", ""))}</b>, {analysis.get("piles", "?")} piles, {len(e.records)} records '
                 f'({e.details["strength_records"]} strength, {e.details["service_records"]} service).</p>')
    carried = visuals.quantity_table_html(e, list(e.external_meta), css='', symbols=True).replace('<table class="">', '<table>')
    return (intro
            + _box('outputs', 'Governing records', visuals.governing_table_html(e, css=''))
            + _box('outputs', 'Envelope by combination (all piles and stations)', visuals.combination_envelope_html(e, css=''))
            + _box('outputs', 'Pile-head records (element 1, I-end)', visuals.records_table_html([r for r in e.records if r['head']], css=''))
            + figures['profile'].to_html(full_html=False, include_plotlyjs=False)
            + _box('outputs', 'Numerical results carried into the formulas', carried))


def _interaction_section(e, figures):
    if not e.records:
        return _box('discussion', 'Interaction', '<p>No FBMP results are loaded.</p>')
    v = e.value
    if e.family == 'psc':
        bi = e.details['biaxial']
        text = ('<p>The interaction curve is computed by strain compatibility for bending about a face axis (angle 0) and about the governing resultant axis. Concrete uses the '
                'rectangular stress block on the compressed part of the square; strand stress follows the PCI power formula for Grade 270 low-relaxation strand; the strand strain '
                'includes the effective prestrain and the concrete decompression strain. φ varies linearly from the compression-controlled to the tension-controlled value '
                '(LRFD 5.5.4.2). Pure compression is limited to φPn,max.</p>'
                f'<p>LRFD 5.6.4.5 route: Eq. {bi["method"]}, ratio {bi["ratio"]:.3f}. Resultant-axis route: ratio {v("DC_rs"):.3f} at {v("alpha_rs", "deg"):.1f}°. '
                f'Splice reference: φMn at P = 0 is {v("M_r_P0"):.1f} kip-ft.</p>')
        tables = curve_table_html(e.curve, 'Interaction curve, bending parallel to a face') + curve_table_html(
            e.curve['resultant'], f'Interaction curve, bending axis at {e.curve["resultant_angle_deg"]:.1f}° (governing resultant)')
    else:
        Prc, Prt, Mr = v('P_r_comb'), v('P_r_t'), v('M_r')
        text = ('<p>The envelope is LRFD Eq. 6.9.2.2.1-1 and -2 with the resultant moment. Pr is the combined-loading axial resistance φc Pn for compression and φy Fy Ag for uplift; '
                'Mr = φf Mn.</p>')
        rows = [('Pure compression', 0.0, Prc), ('Pu/Pr = 0.2 (compression)', 0.9 * Mr, 0.2 * Prc), ('Pure bending', Mr, 0.0),
                ('Pu/Pr = 0.2 (tension)', 0.9 * Mr, -0.2 * Prt), ('Pure tension', 0.0, -Prt)]
        tables = ('<table><tr><th>Vertex</th><th>M (kip-ft)</th><th>P (kip, compression +)</th></tr>'
                  + ''.join(f'<tr><td>{n}</td><td class="num">{m:.1f}</td><td class="num">{p:.1f}</td></tr>' for n, m, p in rows) + '</table>')
    return _box('discussion', 'Method', text) + figures['interaction'].to_html(full_html=False, include_plotlyjs=False) + _box('outputs', 'Curve data', tables)


def _pending_section(e):
    pending = [c for c in e.checks if 'PENDING' in c.status]
    unconfirmed = [(k, t) for k, t in CONFIRMATIONS.items() if not e.case['confirmations'].get(k) and not (e.family != 'pipe' and k in ('steel_grade', 'corrosion'))]
    items = ''.join(f'<li><b>{html.escape(c.label)}</b> ({html.escape(c.group)}): {html.escape(c.note or c.basis)}</li>' for c in pending)
    conf = ''.join(f'<li>{html.escape(t)}</li>' for _, t in unconfirmed)
    return (_box('discussion', 'What is still open', '<p>Items below are not closed by this calculation. A confirmation is recorded in the notebook with dated evidence; '
                 'source consistency alone does not close connection, driving or fabrication review.</p>')
            + _box('outputs', f'Pending checks ({len(pending)})', f'<ul>{items}</ul>' if items else '<p>None.</p>')
            + _box('outputs', f'Unconfirmed prerequisites ({len(unconfirmed)})', f'<ul>{conf}</ul>' if conf else '<p>All prerequisites are confirmed.</p>'))


def _sources_section(e):
    receipts = ''.join(f'<tr><td>{html.escape(r["source_id"])}</td><td>{html.escape(r["filename"])}</td><td><code>{r["sha256"][:16]}…</code></td>'
                       f'<td>{"matches register" if r["matches_register"] else "<b>differs from register</b>"}</td><td>{html.escape("; ".join(r["notes"]))}</td></tr>'
                       for r in e.case.get('receipts', {}).values())
    conf = ''.join(f'<li>{"Confirmed" if e.case["confirmations"].get(k) else "<b>Pending</b>"}: {html.escape(text)}<br>'
                   f'<small>{html.escape(e.case.get("confirmation_evidence", {}).get(k, {}).get("note", "No project evidence recorded."))}</small></li>'
                   for k, text in CONFIRMATIONS.items() if not (e.family != 'pipe' and k in ('steel_grade', 'corrosion')))
    registered = ''.join(f'<tr><td>{html.escape(k)}</td><td>{html.escape(s["label"])}</td><td><code>{html.escape(s["path"])}</code></td><td><code>{s["sha256"][:16]}…</code></td></tr>'
                         for k, s in SOURCES['sources'].items())
    return _box('inputs', 'Registered sources and decisions',
                f'<p>Decisions: {", ".join(SOURCES["decisions"])} (project_current/decisions.md). {html.escape(SOURCES["editions"])}.</p>'
                + (f'<table><tr><th>Source</th><th>File</th><th>SHA-256</th><th>Register</th><th>Notes</th></tr>{receipts}</table>' if receipts else
                   '<p>No file receipt is stored in this case.</p>')
                + f'<details><summary>Source register</summary><table><tr><th>Id</th><th>Source</th><th>Path</th><th>SHA-256</th></tr>{registered}</table></details>'
                + f'<ul>{conf}</ul>')


def build_report(e, title=None):
    import plotly.offline
    family_name = 'Prestressed Concrete' if e.family == 'psc' else 'Steel Pipe'
    title = title or f'Pile Analysis and Design · {e.case["support"]} · {family_name} Piles'
    trace = formula_trace(e)
    figures = {name: fn(e) for name, fn in visuals.FIGURES}
    toggle = lambda state: f"document.querySelectorAll('details').forEach(d=>d.open={state})"
    parts = ['<div class="toolbar"><button onclick="setReportSections(true)">Expand sections</button>'
             '<button onclick="setReportSections(false)">Collapse sections</button>'
             f'<button onclick="{toggle("true")}">Open all disclosures</button>'
             f'<button onclick="{toggle("false")}">Close all disclosures</button>'
             '<button onclick="window.print()">Print / save PDF</button></div>',
             f'<p><b>D2 I-95 Pedestrian Bridge · FDOT District 2</b></p><h1>{html.escape(title)}</h1>',
             f'<p>{html.escape(e.case["name"])}<br>Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} · {html.escape(SOURCES["editions"])}</p>']
    keys = PSC_SECTIONS if e.family == 'psc' else PIPE_SECTIONS
    technical = [(k, h) for k, h in SECTIONS if k in keys]
    tail = [('demands', '9. FBMP demands and governing records'),
            ('interaction', '10. Interaction diagram and curve table' if e.family == 'psc' else '10. Interaction envelope'),
            ('datatable', '11. Pile Data Table'), ('checks', '12. Check register'), ('pending', '13. Pending items'),
            ('sources', '14. Sources, decisions and confirmations')]
    flow = ' <b>→</b> '.join(f'<span>{s}</span>' for s in (
        'FBMP records', 'Drag load DR', 'Section properties', 'Interaction / resistance', 'Combined, shear, tension', 'Service I' if e.family == 'psc' else 'Fixity and slenderness',
        'Geotechnical resistance', 'Pile Data Table', 'Checks'))
    contents = [('overview', 'Overview'), ('results', 'Result summary'), *technical, *tail]
    parts.append('<nav class="contents" aria-label="Table of contents"><h2>Contents</h2><ul>'
                 + ''.join(f'<li><a href="#section-{key}">{html.escape(heading)}</a></li>' for key, heading in contents) + '</ul></nav>')
    parts.append(_report_section('overview', 'Overview', _box('discussion', 'Objective, method and scope',
        f'<p>Analyze and design the {e.case["inputs"]["N_pile"]:.0f} piles of {html.escape(e.case["support"])}: '
        + ('square prestressed concrete piles with the FDOT Standard Plans Index 455 strand patterns' if e.family == 'psc'
           else 'noncomposite steel pipe piles (ASTM A252 Grade 3 / API 5L, Specification 455-8.2)')
        + ', using the FB-MultiPier pile forces, AASHTO LRFD Bridge Design Specifications 10th edition (2024) and the FDOT Structures Design Guidelines and Structures Detailing Manual '
          'of January 2026. Downdrag is carried as a drag load. The Nominal Bearing Resistance and the SDM 11.4 Pile Data Table follow SDG Section 3.5.</p>'
        f'<div class="flow">{flow}</div>'
        '<p>Outside this calculation: composite concrete-filled pipe, drivability and driving stresses (LRFD 10.7.8), pile-to-cap connection design, '
        'minimum tip elevation and scour (geotechnical handoff).</p>')))
    parts.append(_report_section('results', 'Result summary', summary_html(e)))
    by_section = {}
    for t in trace:
        by_section.setdefault(t['section'], []).append(t)
    for key, heading in technical:
        items = by_section.get(key, [])
        names = set()
        for d in e.definitions:
            if d['section'] == key:
                _names(parse(d['expr']), names)
        inputs = [n for n in names if n in INPUTS]
        section = [_box('discussion', 'Purpose', f'<p>{html.escape(SECTION_TEXT.get(key, ""))}</p>')]
        if inputs:
            section.append(_box('inputs', 'Inputs', _input_rows(e, inputs)))
        section.append(_equations(items))
        for name in FIGURE_AFTER.get(key, []):
            section.append(figures[name].to_html(full_html=False, include_plotlyjs=False))
        parts.append(_report_section(key, heading, ''.join(section)))
    parts.append(_report_section('demands', tail[0][1], _demands_section(e, figures)))
    parts.append(_report_section('interaction', tail[1][1], _interaction_section(e, figures)))
    parts.append(_report_section('datatable', tail[2][1], _box('discussion', 'SDM 11.4 and SDG 3.5.15',
        '<p>Loads are rounded up to the nearest ton, minimum tip elevations down and pile lengths up to the nearest foot, and cut-off elevations to 0.1 ft. '
        '“N/A” marks entries that are not applicable or not yet received; no column is removed. Column I excludes the downdrag, which is column J.</p>')
        + _box('outputs', 'Pile Data Table', visuals.data_table_html(e, css=''))))
    parts.append(_report_section('checks', tail[3][1], figures['ratios'].to_html(full_html=False, include_plotlyjs=False) + checks_html(e)))
    parts.append(_report_section('pending', tail[4][1], _pending_section(e)))
    parts.append(_report_section('sources', tail[5][1], _sources_section(e)))
    body = ''.join(parts) + REPORT_SCRIPT
    script = f'<script type="text/javascript">{plotly.offline.get_plotlyjs()}</script>'
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{STYLE}</style>{script}</head><body>{body}</body></html>')


def write_report(e, path):
    from pathlib import Path
    Path(path).write_text(build_report(e), encoding='utf-8')
    return Path(path)
