"""Self-contained HTML calculation report of a journal calculation (offline MathML and Plotly; the backwall layout).

Project and scope, overview, result summary, the numbered sections (purpose box, amber inputs box, equations with
their 'What it represents' blocks, result tables, the journal's native figures rendered as SVG), the check register
and the sources section; definition and citation cards appended before </body>.
"""
from datetime import datetime, timezone
import html
import re

from pier_cap.engine import parse, UNITS
from .model import formula_trace, names_in, evaluate_expression, UNIT_LABELS
from .notation import Notation
from .reviews import review_html
from .schematics import schematic, meaning
from . import figures as fig

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
.prose{margin:6px 0}.prose.bullet{margin-left:14px}.figure{margin:10px 0}.figure .canvas-title{font-size:10pt;color:#485969;margin:0 0 4px}
.figure svg{max-width:100%;height:auto;border:1px solid #dce5ec;background:#fff}.subhead{font-size:11.5pt;margin:16px 0 4px;color:#1f2a36}
.notebox{border-left:3px solid #7189a6;background:#f1f5fa;padding:6px 10px;margin:8px 0;font-size:10pt}
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

QC_NOTE = ('Under every equation: <b>What it represents</b> is always visible. Open it for a term diagram drawn from the current case, '
           'with the defined quantity in red, and a legend of every term with its value and source.')


def _box(kind, title, body):
    return f'<div class="box {kind}"><div class="hd">{html.escape(title)}</div><div class="bd">{body}</div></div>'


def _report_section(key, title, body):
    return (f'<details class="report-section" id="section-{key}" open><summary><h2>{html.escape(title)}</h2></summary>'
            f'<div class="section-body">{body}</div></details>')


def _status_cell(status):
    css = 'FAIL' if 'FAIL' in status else 'PENDING' if 'PENDING' in status else 'PASS' if 'PASS' in status else status.split()[0]
    return f'<span class="{css}">{html.escape(status)}</span>'


class ReportBuilder:
    def __init__(self, spec, e):
        self.spec, self.e = spec, e
        self.n = Notation(spec)
        self.trace = {t['name']: t for t in formula_trace(e)}
        self.qc = self.qc_blocks()
        self.blocks = fig.block_renderer(spec, e)
        self.used_inputs = set()

    # ---------------------------------------------------------------- pieces
    def mathml(self, body):
        return f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="inline">{body}</math>'

    def qc_blocks(self):
        spec, e = self.spec, self.e
        titles = spec.section_titles
        blocks = {}
        for d in e.definitions:
            if 'function' in d:
                blocks[d['name']] = ''
                continue
            svg, drawing = schematic(spec, e, d['name'])
            rows = []
            for name in sorted(names_in(parse(d['expr']))):
                if name not in e.units and name not in spec.inputs:
                    continue
                value = e.text(name, 4) if name in e.units else str(e.engine.get(name))
                if name in spec.inputs:
                    src = e.case['sources'].get(name, {})
                    what = spec.inputs[name]['caption']
                    where = f'input · {src.get("source", spec.inputs[name]["source"])} ({src.get("status", spec.inputs[name]["status"])})'
                else:
                    dd = spec.definition(name)
                    what, where = dd.get('caption', ''), f'calculated · {titles[dd["section"]]}'
                rows.append(f'<tr><td>{self.mathml(self.n.symbol(name))}</td><td>{html.escape(what)}</td><td class="num">{html.escape(value)}</td>'
                            f'<td>{html.escape(where)}</td></tr>')
            legend = ('<div class="qc-terms"><table><tr><th>Term</th><th>Meaning</th><th>Value</th><th>Source</th></tr>' + ''.join(rows)
                      + '</table></div>') if rows else '<div class="qc-terms"><p class="qc-note">Constant; no input terms.</p></div>'
            text = meaning(spec, d['name']) or d['caption']
            caption = f'<figcaption>{html.escape(drawing)}</figcaption>' if drawing and drawing != text else ''
            figure = f'<figure>{svg}{caption}</figure>' if svg else ''
            blocks[d['name']] = (f'<details class="qc"><summary><b>What it represents:</b> {html.escape(text)}</summary>'
                                 f'<div class="qc-body">{figure}{legend}</div></details>')
        return blocks

    def input_rows(self, names):
        spec, e = self.spec, self.e
        rows = []
        order = [d['name'] for d in spec.input_spec]
        for name in sorted(names, key=order.index):
            d = spec.inputs[name]
            src = e.case['sources'].get(name, {})
            value = e.case['inputs'][name]
            unit = UNIT_LABELS.get(d.get('unit'), d.get('unit') or '')
            shown = f'{value:g}' if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
            rows.append(f'<tr><td>{self.mathml(self.n.symbol(name))}</td><td class="num">{html.escape(shown)} {html.escape(unit)}</td>'
                        f'<td>{html.escape(d["caption"])}</td><td>{html.escape(src.get("source", d["source"]))} '
                        f'<i>({html.escape(src.get("status", d["status"]))})</i></td></tr>')
        return ('<table><tr><th>Symbol</th><th>Value</th><th>Meaning</th><th>Source / basis</th></tr>' + ''.join(rows) + '</table>') if rows else ''

    def equations(self, defs):
        out = []
        for d in defs:
            t = self.trace[d['name']]
            refs = self.spec.refs_text(t['refs'])
            out.append(f'<p class="cap">{html.escape(t["caption"])}' + (f' <span class="ref">({html.escape(refs)})</span>' if refs else '')
                       + f'</p><div class="eq">{t["mathml"]}</div>{self.qc.get(t["name"], "")}')
        return ''.join(out)

    def table_html(self, table):
        e = self.e
        rows = []
        for row in table['rows']:
            cells = []
            for j, cell in enumerate(row):
                if isinstance(cell, dict):
                    if 'v' in cell:
                        text = e.text(cell['v'], cell.get('places', 3), cell.get('unit')) if cell['v'] in e.units else str(e.engine.get(cell['v']))
                    elif 'f' in cell:
                        text = evaluate_expression(e, cell['f'], cell.get('unit'))[1]
                    else:
                        text = cell.get('t', '')
                    cells.append(f'<td class="num">{html.escape(text)}</td>')
                else:
                    cells.append(f'<td>{html.escape(str(cell))}</td>' if j == 0 else f'<td class="num">{html.escape(str(cell))}</td>')
            rows.append('<tr>' + ''.join(cells) + '</tr>')
        head = ''.join(f'<th>{html.escape(h)}</th>' for h in table['headers'])
        title = f'<p class="cap"><b>{html.escape(table["title"])}</b></p>' if table.get('title') else ''
        return f'{title}<table><tr>{head}</tr>{"".join(rows)}</table>'

    def block_html(self, block):
        kind = block['kind']
        if kind == 'table':
            return self.table_html(self.spec.table_by_name[block['name']])
        return self.blocks.render(block)

    def section_html(self, section):
        spec, e = self.spec, self.e
        key = section['key']
        defs = [d for d in e.definitions if d['section'] == key]
        names = set()
        for d in defs:
            if 'function' not in d:
                names_in(parse(d['expr']), names)
        titles = {s['title'] for s in spec.sections} | {s['key'] for s in spec.sections}
        inputs = [n for n in names if n in spec.inputs and n not in self.used_inputs and spec.inputs[n].get('group') not in titles]
        inputs += [d['name'] for d in spec.input_spec if d.get('group') in (section['title'], key) and d['name'] not in self.used_inputs and d['name'] not in inputs]
        order = [d['name'] for d in spec.input_spec]
        inputs.sort(key=order.index)
        self.used_inputs.update(inputs)
        parts = []
        if section.get('text'):
            parts.append(_box('discussion', 'Purpose', ''.join(f'<p>{html.escape(t)}</p>' for t in ([section['text']] if isinstance(section['text'], str) else section['text']))))
        blocks = section.get('blocks', [])
        parts += [self.block_html(b) for b in blocks if b.get('at', 'start') == 'start']
        if inputs:
            parts.append(_box('inputs', 'Inputs', self.input_rows(inputs)))
        after = {}
        for b in blocks:
            if b.get('at') not in ('start', 'end', None):
                after.setdefault(b['at'], []).append(b)
        visible = [d for d in defs if not d['hidden']]
        hidden = [d for d in defs if d['hidden']]
        for d in visible:
            parts.append(self.equations([d]))
            for b in after.get(d['name'], []):
                parts.append(self.block_html(b))
        if hidden:
            parts.append(f'<details><summary><b>{html.escape(section.get("hidden_title", "Working rows"))}</b> · {len(hidden)} equations</summary>'
                         + self.equations(hidden) + '</details>')
        parts += [self.block_html(b) for b in blocks if b.get('at') == 'end']
        return ''.join(parts)

    def summary_html(self):
        e, spec = self.e, self.spec
        numeric = [c for c in e.checks if isinstance(c.ratio, (int, float))]
        top = sorted(numeric, key=lambda c: -c.ratio)[:8]
        rows = ''.join(f'<tr><td>{html.escape(c.group)} · {html.escape(c.label)}</td><td class="num">{c.ratio:.3f}</td><td>{_status_cell(c.status)}</td></tr>' for c in top)
        pending = ''.join(f'<li>{html.escape(c.label)}</li>' for c in e.checks if 'PENDING' in c.status)
        results = ''.join(self.table_html(spec.table_by_name[name]) for name in spec.text.get('summary_tables', []) if name in spec.table_by_name)
        key_results = spec.text.get('key_results', [])
        if key_results:
            results = ('<table><tr><th>Result</th><th>Value</th></tr>' + ''.join(
                f'<tr><td>{html.escape(r["label"])}</td><td class="num">{html.escape(e.text(r["name"], r.get("places", 3), r.get("unit")) if r["name"] in e.units else str(e.engine.get(r["name"])))}</td></tr>'
                for r in key_results) + '</table>') + results
        parts = [_box('outputs', 'Result summary', results or f'<p>{html.escape(e.status)}</p>')]
        if numeric or pending:
            parts.append(_box('outputs', 'Largest check ratios', f'<p>{html.escape(e.status)}</p>'
                              + (f'<table><tr><th>Check</th><th>Ratio</th><th>Status</th></tr>{rows}</table>' if rows else '')
                              + (f'<p><b>Pending items</b></p><ul>{pending}</ul>' if pending else '')))
        return ''.join(parts)

    def checks_html(self):
        rows = []
        for c in self.e.checks:
            ratio = f'{c.ratio:.3f}' if isinstance(c.ratio, (int, float)) else '—'
            details = ''.join(f'<div class="eq">{self.trace[n]["mathml"]}</div>{self.qc.get(n, "")}' for n in c.names if n in self.trace)
            refs = self.spec.refs_text(c.refs)
            body = (f'<p>{html.escape(c.basis)}</p>' + (f'<p class="ref">{html.escape(refs)}</p>' if refs else '') + details
                    + (f'<p><i>{html.escape(c.note)}</i></p>' if c.note else ''))
            rows.append(f'<tr><td>{html.escape(c.group)}</td><td>{html.escape(c.label)}{review_html(c)}<details><summary>Equation &amp; values</summary>{body}</details></td>'
                        f'<td>{html.escape(c.demand)}</td><td>{html.escape(c.capacity)}</td><td class="num">{ratio}</td><td>{_status_cell(c.status)}</td></tr>')
        return ('<table><tr><th>Group</th><th>Check</th><th>Demand / required</th><th>Capacity / limit</th><th>Ratio</th><th>Status</th></tr>'
                + ''.join(rows) + '</table>')

    # ---------------------------------------------------------------- document
    def build(self, title=None):
        import plotly.offline
        spec, e = self.spec, self.e
        title = title or spec.full_title
        toggle = lambda sel, state: f"document.querySelectorAll('{sel}').forEach(d=>d.open={state})"
        parts = ['<div class="toolbar"><button onclick="setReportSections(true)">Expand sections</button>'
                 '<button onclick="setReportSections(false)">Collapse sections</button>'
                 f'<button onclick="{toggle("details.qc", "true")}">Open all QC blocks</button>'
                 f'<button onclick="{toggle("details.qc", "false")}">Close all QC blocks</button>'
                 '<button title="Prints all sections, equations and tables; QC blocks print as currently shown" onclick="window.print()">Print / save PDF</button></div>',
                 f'<p><b>D2 I-95 Pedestrian Bridge · FDOT District 2</b></p><h1>{html.escape(title)}</h1>',
                 f'<p>{html.escape(e.case["name"])}<br>Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} · {html.escape(spec.sources.get("editions", ""))}</p>']
        flow = ' <b>→</b> '.join(f'<span>{html.escape(s)}</span>' for s in spec.text.get('flow', []))
        n_sections = sum(1 for s in spec.sections if s.get('level', 0) == 0)
        contents = [('overview', 'Overview'), ('results', 'Result summary')] + [(s['key'], s['title']) for s in spec.sections] + \
                   [('checks', f'{n_sections + 1}. Check register'), ('sources', f'{n_sections + 2}. Sources, decisions and confirmations')]
        parts.append('<nav class="contents" aria-label="Table of contents"><h2>Contents</h2><ul>'
                     + ''.join(f'<li><a href="#section-{key}">{html.escape(heading)}</a></li>' for key, heading in contents) + '</ul></nav>')
        overview = ''.join(f'<p>{html.escape(p)}</p>' for p in spec.text.get('overview', []))
        parts.append(_report_section('overview', 'Overview', _box('discussion', 'Objective, method and scope', overview
                     + (f'<div class="flow">{flow}</div>' if flow else '')
                     + (f'<p>Outside this calculation: {html.escape(spec.text["outside"])}</p>' if spec.text.get('outside') else '')
                     + f'<p>{QC_NOTE}</p>')))
        parts.append(_report_section('results', 'Result summary', self.summary_html()))
        for section in spec.sections:
            parts.append(_report_section(section['key'], section['title'], self.section_html(section)))
        ratios = fig.ratios_figure(e)
        parts.append(_report_section('checks', f'{n_sections + 1}. Check register',
                                     (ratios.to_html(full_html=False, include_plotlyjs=False) if ratios else '') + self.checks_html()))
        conf = ''.join(f'<li>{"Confirmed" if e.case["confirmations"].get(k) else "<b>Pending</b>"}: {html.escape(v["text"])}</li>'
                       for k, v in spec.text.get('confirmations', {}).items())
        sources = ''.join(f'<tr><td>{html.escape(sid)}</td><td>{html.escape(s["label"])}</td><td><code>{html.escape(s.get("path", ""))}</code></td></tr>'
                          for sid, s in spec.sources.get('sources', {}).items())
        parts.append(_report_section('sources', f'{n_sections + 2}. Sources, decisions and confirmations', _box('inputs', 'Registered sources and decisions',
                     f'<p>{html.escape(spec.sources.get("note", ""))}</p>'
                     + (f'<p>Decisions: {html.escape(", ".join(spec.sources["decisions"]))} (project_current/decisions.md).</p>' if spec.sources.get('decisions') else '')
                     + (f'<table><tr><th>Source</th><th>Role</th><th>File</th></tr>{sources}</table>' if sources else '')
                     + (f'<ul>{conf}</ul>' if conf else ''))))
        body = ''.join(parts) + REPORT_SCRIPT
        try:
            from report_cards import cards_html, cite_data, prose_pieces
        except ImportError:  # portable package built without the cards module
            pass
        else:
            body += cards_html(cite_data(spec.references, extra_pieces=prose_pieces(body)))
        script = f'<script type="text/javascript">{plotly.offline.get_plotlyjs()}</script>'
        return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{html.escape(title)}</title><style>{STYLE}</style>{script}</head><body>{body}</body></html>')


def build_report(spec, e, title=None):
    return ReportBuilder(spec, e).build(title)


def write_report(spec, e, path):
    from pathlib import Path
    Path(path).write_text(build_report(spec, e), encoding='utf-8')
    return Path(path)
