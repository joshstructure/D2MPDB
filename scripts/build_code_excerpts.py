"""Build the code-excerpt store that the report citation cards embed.

    .venv\\Scripts\\python.exe scripts\\build_code_excerpts.py            # rebuild every cited provision
    .venv\\Scripts\\python.exe scripts\\build_code_excerpts.py --status   # report what is stale, build nothing
    .venv\\Scripts\\python.exe scripts\\build_code_excerpts.py --only "SDM 12.3.F"

Citation pieces come from every source listed in ``code_excerpts/library.json``: a
calculation's ``references.json`` (``code`` + ``article`` entries, split on "; " exactly
as the reports render them) or Python files scanned for prose references such as
"LRFD 5.7.3.3". For each piece the provision is located in the code PDF (bookmarks for
articles, caption text for tables and equations, line scanning for SDG/SDM lettered
items), highlighted line by line and written as

    code_excerpts/pages/<slug>_crop.png   context crop at 120 dpi (embedded in reports)
    code_excerpts/pages/<slug>_full.png   full page at 100 dpi (embedded once per page)
    code_excerpts/References/<label>.pdf  one-page PDF with highlight annotations (not tracked)
    code_excerpts/excerpts.json           the store; ``inputs_sha256`` lets tests detect staleness

Hand entries (scanned pages, journal GetRefs excerpts, pieces to skip) live in
``code_excerpts/overrides.json``. Needs PyMuPDF and the code library folder, which stays
outside the repository.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from report_cards import CODE_RE, pieces as reference_pieces, prose_pieces  # noqa: E402

STORE = ROOT / 'code_excerpts'
BUILDER_VERSION = '1.0.0'
NUM_RE = re.compile(r'\d+(?:\.\d+)+(?:\.[A-Z](?:\.\d+)?)?')
ID_RE = re.compile(r'(?:\d+(?:\.\d+)+)?-\d+')
FULL_DPI, CROP_DPI = 100, 120


def load_config():
    library = json.loads((STORE / 'library.json').read_text(encoding='utf-8'))
    overrides = json.loads((STORE / 'overrides.json').read_text(encoding='utf-8'))
    return library, overrides


def library_dir(library) -> Path:
    env = os.environ.get('D2MPDB_CODE_LIBRARY')
    return Path(env) if env else (ROOT / library['library_dir']).resolve()


def collect_pieces(library) -> dict[str, list[str]]:
    """piece -> the sources that cite it."""
    found: dict[str, list[str]] = {}
    for src in library['citation_sources']:
        if 'references' in src:
            refs = json.loads((ROOT / src['references']).read_text(encoding='utf-8'))
            for piece in reference_pieces(refs):
                found.setdefault(piece, []).append(src['references'])
        for pattern in src.get('scan', []):
            for path in sorted(ROOT.glob(pattern)):
                for piece in prose_pieces(path.read_text(encoding='utf-8', errors='replace')):
                    rel = path.relative_to(ROOT).as_posix()
                    found.setdefault(piece, [])
                    if rel not in found[piece]:
                        found[piece].append(rel)
    return found


def inputs_digest(library, overrides, found) -> str:
    payload = json.dumps({'version': BUILDER_VERSION, 'codes': library['codes'], 'overrides': overrides,
                          'pieces': sorted(found)}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def status(library, overrides, found) -> tuple[bool, str]:
    """(current, message) without touching the PDFs."""
    path = STORE / 'excerpts.json'
    if not path.is_file():
        return False, 'code_excerpts/excerpts.json is missing'
    store = json.loads(path.read_text(encoding='utf-8'))
    if store.get('inputs_sha256') != inputs_digest(library, overrides, found):
        new = sorted(p for p in found if p not in store.get('cites', {}))
        return False, 'citations or overrides changed' + (f'; new pieces: {new}' if new else '')
    missing = [pg[k] for e in store['cites'].values() for pg in e.get('pages', []) for k in ('crop', 'full')
               if pg.get(k) and not (STORE / pg[k]).is_file()]
    if missing:
        return False, f'{len(missing)} page images missing, e.g. {missing[0]}'
    return True, 'current'


# ---------------------------------------------------------------- PDF work (PyMuPDF only below)

class Builder:
    def __init__(self, library, overrides):
        import pymupdf
        self.pymupdf = pymupdf
        self.library, self.overrides = library, overrides
        self.lib_dir = library_dir(library)
        self.docs, self.tocs = {}, {}
        (STORE / 'pages').mkdir(parents=True, exist_ok=True)
        (STORE / 'References').mkdir(parents=True, exist_ok=True)

    # -- documents and bookmarks
    def spec(self, code):
        return self.library['codes'][code]

    def doc(self, code):
        file = self.spec(code)['file']
        if file not in self.docs:
            self.docs[file] = self.pymupdf.open(str(self.lib_dir / file))
        return self.docs[file]

    def source_hashes(self):
        out = {}
        for code, spec in self.library['codes'].items():
            path = self.lib_dir / spec['file']
            if path.is_file():
                out[spec['file']] = hashlib.sha256(path.read_bytes()).hexdigest()
        return out

    def toc(self, code):
        if code not in self.tocs:
            d = self.doc(code)
            lo, hi = self.spec(code).get('pages', (0, d.page_count))
            idx = {}
            for _lvl, title, page in d.get_toc():
                if not (lo <= page - 1 < hi):
                    continue
                t = title.strip().replace('\n', ' ')
                m = re.match(r'^(\d+(?:\.\d+)*)\s*[—-]?\s*(.*)$', t)
                if m and m.group(1) not in idx:
                    idx[m.group(1)] = (page - 1, t)
            self.tocs[code] = idx
        return self.tocs[code]

    @staticmethod
    def lines_on(page):
        out = []
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                text = ''.join(s['text'] for s in line['spans']).strip()
                if text:
                    out.append((text, line['bbox']))
        return out

    # -- parsing a piece
    @staticmethod
    def parse(rest):
        """'3.4.1, Tables 3.4.1-1 and 3.4.1-2' -> articles, tables, equations."""
        articles, tables, eqs = [], [], []
        for seg in [s.strip() for s in rest.split(',')]:
            ids = ID_RE.findall(seg)
            if re.match(r'^Tables?\b', seg) or re.match(r'^Eqs?\.', seg):
                full = []
                for i in ids:
                    if i.startswith('-') and full:
                        i = full[-1].rsplit('-', 1)[0] + i
                    full.append(i)
                (tables if seg.startswith('Table') else eqs).extend(full)
            else:
                # "3.13.2.I.1 and Table 2.2-1": the 2.2 inside the table id is not an article.
                articles.extend(n for n in NUM_RE.findall(seg) if f'{n}-' not in seg)
                if 'Table' in seg:
                    tables.extend(ids)
        return articles, tables, eqs

    # -- locating provisions
    def find_article(self, code, number):
        R = self.pymupdf.Rect
        d, idx = self.doc(code), self.toc(code)
        base, letter, sub = number, None, None
        m = re.match(r'^(\d+(?:\.\d+)+)\.([A-Z])(?:\.(\d+))?$', number)
        if m:
            base, letter, sub = m.group(1), m.group(2), m.group(3)
        if base in idx:
            page0, title = idx[base]
        else:
            page0, title = None, number
            lo, hi = self.spec(code).get('pages', (0, d.page_count))
            for p in range(lo, hi):
                for text, bbox in self.lines_on(d[p]):
                    if re.match(rf'^{re.escape(base)}\s*[—-]\s*[A-Z]', text):
                        page0, title = p, text
                        break
                if page0 is not None:
                    break
            if page0 is None:
                return None
        hits = []
        if letter:
            state = 'seek'
            stop = re.compile(r'^([A-Z]\.\s|\d+\.\d+\s+[A-Z]|Commentary:|Modification for)')
            for p in range(page0, min(page0 + 12, d.page_count)):
                found = []
                for text, bbox in self.lines_on(d[p]):
                    rect = R(bbox)
                    if state == 'seek':
                        if re.match(rf'^{letter}\.\s', text):
                            if sub:
                                state = 'sub'
                            else:
                                state, found = 'collect', [rect]
                    elif state == 'sub':
                        if re.match(rf'^{sub}\.\s', text):
                            state, found = 'collect', [rect]
                        elif re.match(r'^[A-Z]\.\s', text):
                            state = 'seek'
                    elif stop.match(text) or (sub and re.match(r'^\d+\.\s', text)) or len(found) >= 16:
                        break
                    else:
                        found.append(rect)
                if found:
                    hits.append((p, found))
                    break
            if not hits:
                hits.append((page0, []))
            item = f'item {letter}' + (f'.{sub}' if sub else '')
            return dict(title=f'{idx.get(base, (0, base))[1]} · {item}', hits=hits)
        page = d[page0]
        rects = page.search_for(title) or page.search_for(title.split('—')[0] + '—') or page.search_for(base)
        hits.append((page0, [rects[0]] if rects else []))
        return dict(title=title, hits=hits)

    def find_label(self, code, kind, ident):
        """Caption line of a table, or the label line of an equation, near its article's bookmark."""
        R = self.pymupdf.Rect
        d, idx = self.doc(code), self.toc(code)
        article = ident.rsplit('-', 1)[0]
        start, probe = None, article
        while probe and start is None:
            if probe in idx:
                start = idx[probe][0]
            probe = probe.rsplit('.', 1)[0] if '.' in probe else ''
        if start is None:
            return None
        lo, hi = max(start - 1, 0), min(start + 12, d.page_count)
        if kind == 'table':
            for pattern in (rf'^Table {re.escape(ident)}\s*[—-]', rf'^Table {re.escape(ident)}\s+[A-Z]'):
                for p in range(lo, hi):
                    for text, bbox in self.lines_on(d[p]):
                        if re.match(pattern, text):
                            return (p, R(bbox))
            return None
        for p in range(lo, hi):
            for text, bbox in self.lines_on(d[p]):
                if f'({ident})' in text:
                    return (p, R(bbox))
            rects = d[p].search_for(f'({ident})')
            if rects:
                return (p, rects[0])
        return None

    @staticmethod
    def printed_page(page):
        R = page.rect
        top = page.get_text('text', clip=(0, 0, R.width, 60))
        bottom = page.get_text('text', clip=(0, R.height - 60, R.width, R.height))
        m = re.search(r'\b(\d{1,2}-\d{1,3})\b', top) or re.search(r'\b(\d{1,2}-\d{1,3})\b', bottom)
        return m.group(1) if m else ''

    # -- rendering
    @staticmethod
    def slug(text):
        return re.sub(r'[^A-Za-z0-9.]+', '_', text).strip('_')

    @staticmethod
    def shrink(path):
        """Palette-quantize a rendered page (text plus highlight): about a third of the 24-bit size."""
        from PIL import Image
        with Image.open(path) as im:
            q = im.convert('RGB').quantize(colors=48, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            q.save(path, 'PNG', optimize=True)

    @staticmethod
    def safe_name(text):
        return re.sub(r'[\\/:*?"<>|]', '-', text).strip()

    def render(self, page, rects, name, label, annot_rects=None):
        R = self.pymupdf.Rect
        annot_rects = rects if annot_rects is None else annot_rects
        for r in annot_rects:
            page.add_highlight_annot(r)
        full = STORE / 'pages' / f'{name}_full.png'
        page.get_pixmap(dpi=FULL_DPI).save(str(full))
        pr = page.rect
        if rects:
            u = R(rects[0])
            for r in rects[1:]:
                u = u | R(r)
            y0, y1 = max(pr.y0, u.y0 - 70), min(pr.y1, u.y1 + 90)
            if y1 - y0 < 260:
                pad = (260 - (y1 - y0)) / 2
                y0, y1 = max(pr.y0, y0 - pad), min(pr.y1, y1 + pad)
            clip = R(pr.x0 + 36, y0, pr.x1 - 36, y1)
        else:
            clip = R(pr.x0 + 36, pr.y0 + 40, pr.x1 - 36, pr.y0 + 420)
        crop = STORE / 'pages' / f'{name}_crop.png'
        page.get_pixmap(dpi=CROP_DPI, clip=clip).save(str(crop))
        self.shrink(full); self.shrink(crop)
        out = self.pymupdf.open()
        out.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
        for r in annot_rects:
            out[0].add_highlight_annot(r)
        pdf = STORE / 'References' / f'{self.safe_name(label)}.pdf'
        out.save(str(pdf), garbage=3, deflate=True)
        out.close()
        return dict(crop=f'pages/{crop.name}', full=f'pages/{full.name}', pdf=f'References/{pdf.name}')

    def yellow_bbox(self, page):
        """Bounding box of baked yellow highlights on a journal excerpt page (page points)."""
        pix = page.get_pixmap(dpi=50)
        s, n, w = pix.samples, pix.n, pix.width
        xs, ys = [], []
        for y in range(pix.height):
            row = y * pix.stride
            for x in range(w):
                i = row + x * n
                r, g, b = s[i], s[i + 1], s[i + 2]
                if r > 225 and g > 205 and b < 190 and r - b > 45:
                    xs.append(x); ys.append(y)
        if not xs:
            return None
        k = 72 / 50
        return self.pymupdf.Rect(min(xs) * k, min(ys) * k, max(xs) * k, max(ys) * k)

    def journal_pages(self, files):
        R = self.pymupdf.Rect
        folder = ROOT / self.library.get('journal_references', 'journal/References')
        pages = []
        for f in files:
            d = self.pymupdf.open(str(folder / f))
            page = d[0]
            box = self.yellow_bbox(page)
            pr = page.rect
            if box:
                clip = R(pr.x0 + 36, max(pr.y0, box.y0 - 60), pr.x1 - 36, min(pr.y1, box.y1 + 60))
            else:
                clip = R(pr.x0 + 36, pr.y0 + 40, pr.x1 - 36, pr.y0 + 420)
            name = self.slug(f[:-4])
            full = STORE / 'pages' / f'{name}_full.png'
            crop = STORE / 'pages' / f'{name}_crop.png'
            page.get_pixmap(dpi=FULL_DPI).save(str(full))
            page.get_pixmap(dpi=CROP_DPI, clip=clip).save(str(crop))
            self.shrink(full); self.shrink(crop)
            (STORE / 'References' / f).write_bytes((folder / f).read_bytes())
            pages.append(dict(label=f[:-4], printed=self.printed_page(page), page=1, crop=f'pages/{crop.name}',
                              full=f'pages/{full.name}', pdf=f'References/{f}', source='journal References (GetRefs excerpt)'))
            d.close()
        return pages

    # -- one piece
    def build(self, piece, default_code):
        R = self.pymupdf.Rect
        ov = self.overrides
        m = CODE_RE.match(piece)
        code, rest = (m.group(1), m.group(2)) if m else (default_code, piece)
        entry = dict(code=code, edition=self.library['codes'].get(code, {}).get('edition', ''), title='', pages=[], missing='')
        if piece in ov.get('skip', {}):
            entry['missing'] = ov['skip'][piece]
            return entry
        if piece in ov.get('journal', {}):
            entry['pages'] = self.journal_pages(ov['journal'][piece])
            entry['title'] = 'Excerpt from the project journal References'
            return entry
        if piece in ov.get('manual', {}):
            man = ov['manual'][piece]
            mcode = man.get('code', code)
            entry['code'], entry['edition'], entry['title'] = mcode, self.library['codes'][mcode]['edition'], man.get('title', rest)
            page = self.doc(mcode)[man['page']]
            shown = [R(*man['rect'])] if man.get('rect') else []
            label = f'{piece} ({mcode} p. {man.get("printed", man["page"] + 1)})'
            info = self.render(page, shown, self.slug(f'{mcode}_{rest}_p{man["page"] + 1}'), label,
                               annot_rects=[r * page.derotation_matrix for r in shown])
            info.update(label=label, printed=man.get('printed', ''), page=man['page'] + 1,
                        source=self.spec(mcode)['file'] + ' (manual page entry)')
            entry['pages'].append(info)
            return entry
        if code not in self.library['codes']:
            entry['missing'] = f'No code library entry for "{code}".'
            return entry
        articles, tables, eqs = self.parse(rest)
        hits: dict[int, list] = {}
        titles = []

        def add(found):
            titles.append(found['title'])
            for p, rects in found['hits']:
                hits.setdefault(p, []).extend(rects)
        for a in articles:
            found = self.find_article(code, a)
            if found:
                add(found)
        for t in tables:
            h = self.find_label(code, 'table', t)
            if h:
                hits.setdefault(h[0], []).append(h[1])
                titles.append(f'Table {t}')
        for e in eqs:
            h = self.find_label(code, 'eq', e)
            if h:
                hits.setdefault(h[0], []).append(h[1])
            else:
                sub = e.rsplit('-', 1)[0]
                found = self.find_article(code, sub) if sub not in articles else None
                if found:
                    add(found)
        if not hits:
            entry['missing'] = 'Provision not located automatically; add a manual entry in code_excerpts/overrides.json.'
            return entry
        entry['title'] = titles[0] if titles else rest
        d = self.doc(code)
        for p in sorted(hits):
            page = d[p]
            printed = self.printed_page(page)
            label = f'{piece} ({code} p. {printed or p + 1})'
            info = self.render(page, hits[p], self.slug(f'{code}_{rest}_p{p + 1}'), label)
            info.update(label=label, printed=printed, page=p + 1, source=self.spec(code)['file'])
            entry['pages'].append(info)
        return entry


def default_code_for(piece, found, library):
    """A bare piece such as '14.7.5.2' inherits the code of the reference it came from."""
    for src in found.get(piece, []):
        if src.endswith('.json'):
            refs = json.loads((ROOT / src).read_text(encoding='utf-8'))
            for ref in refs.values():
                if piece in [p.strip() for p in f"{ref['code']} {ref['article']}".split('; ')]:
                    return ref['code']
    return 'LRFD'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--status', action='store_true', help='report staleness only')
    ap.add_argument('--only', help='build a single piece and merge it into the store')
    args = ap.parse_args(argv)
    library, overrides = load_config()
    found = collect_pieces(library)
    if args.status:
        ok, msg = status(library, overrides, found)
        print(('current' if ok else 'stale') + ': ' + msg + f' ({len(found)} citation pieces)')
        return 0 if ok else 1
    b = Builder(library, overrides)
    path = STORE / 'excerpts.json'
    store = json.loads(path.read_text(encoding='utf-8')) if (args.only and path.is_file()) else \
        {'version': BUILDER_VERSION, 'cites': {}}
    targets = [args.only] if args.only else sorted(found)
    for piece in targets:
        entry = b.build(piece, default_code_for(piece, found, library))
        entry['cited_by'] = found.get(piece, [])
        store['cites'][piece] = entry
        where = entry['missing'] or ' '.join(f'p.{pg["printed"] or pg["page"]}' for pg in entry['pages'])
        print(f'{piece:55s} {where}')
    store.update(version=BUILDER_VERSION, built=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                 inputs_sha256=inputs_digest(library, overrides, found), sources=b.source_hashes(),
                 library={k: v['edition'] for k, v in library['codes'].items()})
    path.write_text(json.dumps(store, indent=1, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    n_pages = sum(len(e['pages']) for e in store['cites'].values())
    n_missing = sum(1 for e in store['cites'].values() if e['missing'])
    print(f'{len(store["cites"])} citation pieces, {n_pages} excerpt pages, {n_missing} without excerpt -> {path.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
