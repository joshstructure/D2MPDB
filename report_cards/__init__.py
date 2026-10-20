"""Definition and citation cards for the calculation reports.

Any report that renders MathML through a ``symbol()`` tagging ``data-var`` gets
hover/pin/drag cards showing where and how each variable is defined. Reports
that cite code provisions (``REFERENCES`` entries of ``code`` + ``article``, or
prose such as "LRFD 5.7.3.3") get cards with the highlighted excerpt from the
``code_excerpts`` store built by ``scripts/build_code_excerpts.py``.

Usage in a report builder::

    from report_cards import cards_html, cite_data
    body += cards_html(cite_data(REFERENCES))

``cite_data`` returns ``None`` when no excerpt store is available (portable
notebook builds without the page images); the cards then show titles only.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STORE = ROOT / 'code_excerpts'
CARDS_VERSION = '1.0.0'
CODE_RE = re.compile(r'^(LRFD|SDM|SDG|AASHTO Guide Spec\. Pedestrian Bridges)\s+(.*)$')
PROSE_RE = re.compile(r'\b(LRFD|SDG|SDM|AASHTO Guide Spec\. Pedestrian Bridges)\s+'
                      r'(?:(Tables?|Eqs?\.|Figures?|Fig\.|Articles?|Art\.)\s+)?'
                      r'(\d+(?:\.\d+)+(?:\.[A-Z](?:\.\d+)?)?(?:-\d+)?)')


def assets() -> tuple[str, str]:
    """(css, js) of the card system."""
    return (HERE / 'cards.css').read_text(encoding='utf-8'), (HERE / 'cards.js').read_text(encoding='utf-8')


def pieces(references: dict) -> list[str]:
    """Citation pieces exactly as the reports render them: ``'CODE article'`` split on '; '."""
    out = []
    for ref in references.values():
        for piece in f"{ref['code']} {ref['article']}".split('; '):
            piece = piece.strip()
            if piece and piece not in out:
                out.append(piece)
    return out


def canonical(code: str, kind: str | None, ident: str) -> str:
    """Prose reference -> store key ('LRFD Table 3.4.1-1', 'SDG 3.13.2.N.3')."""
    if not kind or kind.startswith('Art'):
        return f'{code} {ident}'
    kind = {'Tables': 'Table', 'Eqs.': 'Eq.', 'Figures': 'Fig.', 'Figure': 'Fig.'}.get(kind, kind)
    return f'{code} {kind} {ident}'


def prose_pieces(text: str) -> list[str]:
    """Citation pieces found in free text (for reports without a REFERENCES table)."""
    out = []
    for m in PROSE_RE.finditer(text):
        piece = canonical(m.group(1), m.group(2), m.group(3))
        if piece not in out:
            out.append(piece)
    return out


def load_store(store: Path | None = None) -> dict | None:
    store = store or STORE
    path = store / 'excerpts.json'
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    data['_dir'] = store
    return data


def _data_uri(path: Path) -> str | None:
    if not path.is_file():
        return None
    return 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def cite_data(references: dict | None = None, extra_pieces=(), *, store: Path | None = None,
              embed_full_pages: bool = True, pdf_dir: str | None = None) -> dict | None:
    """Card data for the pieces a report cites: crops embedded, full pages embedded once each.

    ``pdf_dir`` (a path relative to the exported report) adds one-page PDF links when the
    export script copies ``code_excerpts/References`` beside the report.
    """
    data = load_store(store)
    if data is None:
        return None
    wanted = list(extra_pieces)
    governs: dict[str, list[str]] = {}
    for ref in (references or {}).values():
        for piece in f"{ref['code']} {ref['article']}".split('; '):
            piece = piece.strip()
            if piece and piece not in wanted:
                wanted.append(piece)
            if ref.get('governs') and ref['governs'] not in governs.setdefault(piece, []):
                governs[piece].append(ref['governs'])
    cites, pages = {}, {}
    for piece in wanted:
        entry = data['cites'].get(piece)
        if not entry:
            continue
        card = {k: entry.get(k, '') for k in ('code', 'edition', 'title', 'missing')}
        card['governs'] = governs.get(piece, [])
        card['pages'] = []
        for pg in entry.get('pages', []):
            item = {k: pg.get(k) for k in ('page', 'printed', 'label', 'source')}
            item['crop'] = _data_uri(data['_dir'] / pg['crop']) if pg.get('crop') else None
            full = pg.get('full')
            if full and embed_full_pages:
                if full not in pages:
                    uri = _data_uri(data['_dir'] / full)
                    if uri:
                        pages[full] = uri
                item['full'] = full if full in pages else None
            else:
                item['full'] = None
            item['pdf'] = f'{pdf_dir}/{Path(pg["pdf"]).name}' if pdf_dir and pg.get('pdf') else None
            card['pages'].append(item)
        cites[piece] = card
    return {'cites': cites, 'pages': pages, 'version': data.get('version', ''), 'built': data.get('built', '')}


def cards_html(cites: dict | None = None) -> str:
    """The HTML to append before ``</body>``: citation data (if any), stylesheet and script."""
    css, js = assets()
    parts = []
    if cites:
        payload = json.dumps(cites, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
        # Not "application/json": report tests and viewers treat those blocks as Plotly figures.
        parts.append(f'<script id="cite-data" type="application/report-cards+json">{payload}</script>')
    parts.append(f'<style id="report-cards-style">{css}</style>')
    parts.append(f'<script id="report-cards-script">{js}</script>')
    return '\n'.join(parts)
