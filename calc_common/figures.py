"""Figures of a journal calculation: the native journal canvases rendered as SVG, prose blocks, and the ratio chart.

The canvases, content boxes and design-basis paragraphs come from ``data/journal_blocks.xml`` (copied from the
journal module once, see scripts/import_journal_calc.py and scripts/build_journal_calc_data.py). They are rendered
with the independent preview renderer (scripts/bpad_preview.py) over the values of the current evaluation, so the
figures in the report follow the case exactly as the live canvases follow the Blockpad edition.
"""
import html
import re

import plotly.graph_objects as go
from lxml import etree as ET

from pier_cap.engine import Q

QUALIFIED = re.compile(r'\b([A-Za-z_][A-Za-z_0-9]*)\.([A-Za-z_Ͱ-Ͽ][A-Za-z_0-9Ͱ-Ͽ]*)')


def theme(fig, title, height=460):
    fig.update_layout(title=dict(text=title, font=dict(size=14)), height=height, margin=dict(l=40, r=20, t=50, b=40),
                      paper_bgcolor='#ffffff', plot_bgcolor='#fbfcfd', font=dict(family='Arial, sans-serif', size=11, color='#213649'),
                      legend=dict(orientation='h', y=-0.18))
    return fig


def ratios_figure(e):
    checks = [c for c in e.checks if isinstance(c.ratio, (int, float))]
    if not checks:
        return None
    labels = [f'{c.group} · {c.label}' for c in checks]
    values = [min(c.ratio, 3.0) for c in checks]
    colors = ['#bb3e39' if c.ratio > 1 else '#17633b' for c in checks]
    fig = go.Figure(go.Bar(x=values, y=labels, orientation='h', marker_color=colors, hovertext=[f'{c.ratio:.3f} · {c.status}' for c in checks],
                           hoverinfo='text'))
    fig.add_vline(x=1.0, line=dict(color='#c8372d', dash='dot'))
    fig.update_layout(xaxis_title='Demand / capacity (clipped at 3)', yaxis=dict(autorange='reversed'))
    return theme(fig, 'Check ratios', height=max(300, 40 + 26 * len(checks)))


class BlockRenderer:
    """Renders the journal blocks (canvases, prose paragraphs, content tables) for the HTML report."""

    def __init__(self, spec, e):
        self.spec, self.e = spec, e
        self.blocks = {}
        if spec.blocks_xml:
            root = ET.fromstring(spec.blocks_xml)
            for block in root:
                self.blocks[block.get('id')] = block
        self._ctx = None

    def ctx(self):
        if self._ctx is None:
            from scripts import bpad_preview as pv
            doc = ET.Element('document')
            rep = ET.SubElement(doc, 'report', name=self.spec.name)
            self._ctx = pv.Ctx(doc, self.spec.name)
            self._ctx.report = self.spec.name
            ev = self._ctx.evaluator
            for name in list(self.e.units) + list(self.spec.inputs):
                v = self.e.engine.get(name)
                ev.vars[f'{self.spec.name}.{name}'] = v.v if isinstance(v, Q) else v
            for name, d in self.spec.inputs.items():
                if d.get('journal'):
                    v = self.e.engine.get(name)
                    ev.vars[d['journal']] = v.v if isinstance(v, Q) else v
        return self._ctx

    def render(self, block):
        kind = block['kind']
        if kind == 'canvas':
            el = self.blocks.get(block['id'])
            if el is None:
                return ''
            canvas = el.find('canvas')
            from scripts import bpad_preview as pv
            html_svg = pv.render_canvas(self.ctx(), canvas)
            return f'<div class="figure">{html_svg}</div>'
        if kind in ('prose', 'prose_section'):
            ids = block.get('ids') or [block['id']]
            out = []
            for bid in ids:
                el = self.blocks.get(bid)
                if el is None:
                    continue
                for child in el:
                    out.append(self.prose_html(child))
            if block.get('title'):
                return f'<h3 class="subhead">{html.escape(block["title"])}</h3>' + ''.join(out)
            return ''.join(out)
        return ''

    def text_of(self, el):
        parts = []

        def rec(node):
            if node.tag == 'dynexp':
                f = node.get('formula') or ''
                parts.append(self.inline_value(f))
                return
            if node.tag == 'link':
                parts.append(html.escape(node.text or ''))
                return
            if node.text:
                parts.append(html.escape(node.text))
            for c in node:
                rec(c)
                if c.tail:
                    parts.append(html.escape(c.tail))
        rec(el)
        return ' '.join(' '.join(p.split()) for p in parts if p and p.strip())

    def inline_value(self, formula):
        name = formula.strip()
        if '=' in name:
            name = name.split('=', 1)[0].strip()
        local = QUALIFIED.sub(lambda m: m.group(2) if m.group(1) == self.spec.name else m.group(0), name)
        if local in self.e.units:
            return f'<b>{html.escape(local)}</b> = {html.escape(self.e.text(local))}'
        return f'<b>{html.escape(local)}</b>'

    def prose_html(self, el):
        if el.tag == 'paragraph':
            text = self.text_of(el)
            if not text:
                return ''
            bullet = text.startswith('•')
            bold = el.get('fontweight') == 'bold'
            cls = 'prose bullet' if bullet else 'prose'
            return f'<p class="{cls}">{"<b>" + text + "</b>" if bold else text}</p>'
        if el.tag == 'heading':
            return f'<h3 class="subhead">{self.text_of(el)}</h3>'
        if el.tag == 'table':
            rows = []
            for row in el.findall('row'):
                cells = [f'<td>{self.text_of(cell)}</td>' for cell in row]
                rows.append('<tr>' + ''.join(cells) + '</tr>')
            return f'<div class="notebox"><table>{"".join(rows)}</table></div>'
        if el.tag == 'embed':
            return ''.join(self.prose_html(c) for c in el)
        return ''


def block_renderer(spec, e):
    return BlockRenderer(spec, e)
