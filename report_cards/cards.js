/* Definition and citation cards for calculation reports (report_cards, version in CARDS_VERSION).
 *
 * Variables: every <mi>/<msub> that the generator tagged with data-var gets a card showing
 * where and how the symbol is defined (first block equation "symbol = ..."), or its input row.
 * Citations: text in .ref elements and prose "LRFD 5.7.3.3" style references get a card with
 * the highlighted code excerpt from the embedded cite-data JSON (built by scripts/build_code_excerpts.py).
 * Hover opens a card; pin by clicking the glyph, the Pin button or dragging; hovering inside a
 * card opens the next card; closing a card leaves its children; Esc closes all.
 */
(() => {
  const CARDS_VERSION = '1.0.0';
  const MML = 'http://www.w3.org/1998/Math/MathML';
  const isUnit = el => el.getAttribute('mathvariant') === 'normal';
  const FN = /^(min|max|sin|cos|tan|cot|abs|sqrt)$/;

  // ---- 1. Variable glyphs: generator-tagged data-var, or inferred from the MathML when untagged ----
  function keyOf(el) {
    const n = el.localName;
    if (n === 'msub') {
      const a = el.children[0], b = el.children[1];
      if (!a || !b || a.localName !== 'mi' || b.localName !== 'mtext' || isUnit(a)) return null;
      return a.textContent + '_' + b.textContent;
    }
    if (n === 'mi') {
      if (isUnit(el)) return null;
      const p = el.parentElement;
      if (p && p.localName === 'msub' && el === p.firstElementChild) return null;
      const t = el.textContent.trim();
      return !t || FN.test(t) ? null : t;
    }
    return null;
  }
  if (!document.querySelector('math [data-var]')) {
    document.querySelectorAll('math mi, math msub').forEach(el => { const k = keyOf(el); if (k) el.setAttribute('data-var', k); });
  }

  // ---- 2. Index definitions, input rows and legend rows ----
  const defs = new Map(), inputs = new Map(), legend = new Map(), usedIn = new Map();
  let seq = 0;
  const headings = [...document.querySelectorAll('h2')];
  const text = el => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');
  const sectionOf = el => {
    const s = el.closest('details.report-section, details.section');
    if (s) return text(s.querySelector('summary'));
    let last = '';
    for (const h of headings) { if (h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) last = text(h); else break; }
    return last;
  };
  const lhsOf = math => {
    // "<math><mrow>symbol = ...</mrow></math>" (backwall, pile) or "<math>symbol <mo>=</mo> ...</math>" (cap).
    const row = math.children.length === 1 && math.firstElementChild.localName === 'mrow' ? math.firstElementChild : math;
    const lhs = row.children[0], eq = row.children[1];
    if (!lhs || !eq || eq.localName !== 'mo' || eq.textContent !== '=' || !lhs.hasAttribute('data-var')) return null;
    return lhs;
  };
  document.querySelectorAll('math[display="block"]').forEach(math => {
    const lhs = lhsOf(math);
    if (!lhs || math.closest('.var-pop')) return;
    const k = lhs.getAttribute('data-var');
    const container = math.closest('article.equation') || math.closest('div.eq') || math.parentElement;
    if (defs.has(k)) {
      const d = defs.get(k);
      if (container === d.target && !d.maths.includes(math)) d.maths.push(math);
      return;
    }
    if (!container.id) container.id = 'def-' + (++seq);
    const prev = container.previousElementSibling;
    const cap = prev && prev.matches('p.cap') ? text(prev) : text(container.querySelector('p.caption, .caption, h4, h3'));
    const qc = container.nextElementSibling && container.nextElementSibling.matches('details.qc') ? container.nextElementSibling : null;
    const meaning = qc ? text(qc.querySelector('summary')).replace(/^What it represents:\s*/, '') : '';
    const result = container.querySelector('.result');
    defs.set(k, {target: container, maths: [math], lhs, caption: cap, meaning, result: text(result), section: sectionOf(container)});
    math.querySelectorAll('[data-var]').forEach(el => {
      const u = el.getAttribute('data-var');
      if (el === lhs || u === k) return;
      if (!usedIn.has(u)) usedIn.set(u, new Set());
      usedIn.get(u).add(k);
    });
  });
  document.querySelectorAll('tr').forEach(tr => {
    const td = tr.children;
    if (td.length < 3 || td[0].localName !== 'td') return;
    const sym = td[0].querySelector('[data-var]');
    if (!sym || td[0].querySelectorAll('[data-var]').length !== 1) return;
    const k = sym.getAttribute('data-var');
    if (tr.closest('.qc-terms')) {
      if (!legend.has(k)) legend.set(k, {lhs: sym, meaning: text(td[1]), value: text(td[2]), source: text(td[3])});
      return;
    }
    if (inputs.has(k)) return;
    if (!tr.id) tr.id = 'in-' + (++seq);
    // Input tables list [symbol, value, meaning, basis] or [symbol, meaning, value, basis]; pick the value cell by content.
    const looksValue = c => !!c.querySelector('math, .badge, .PENDING, .PASS, .FAIL') || /^[-+#]?\d/.test(text(c));
    const valueCell = looksValue(td[1]) || !looksValue(td[2]) ? td[1] : td[2];
    const meaningCell = valueCell === td[1] ? td[2] : td[1];
    inputs.set(k, {target: tr, lhs: sym, value: text(valueCell), meaning: text(meaningCell), source: text(td[3]), section: sectionOf(tr)});
  });

  // ---- 3. Citations: wrap pieces of .ref elements and prose references that have an excerpt entry ----
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const data = (() => { const s = document.getElementById('cite-data'); try { return s ? JSON.parse(s.textContent) : {}; } catch (e) { return {}; } })();
  const CITES = data.cites || {}, PAGES = data.pages || {};
  document.querySelectorAll('.ref').forEach(ref => {
    if (ref.querySelector('.cite')) return;
    let t = ref.textContent.trim();
    const paren = t.startsWith('(') && t.endsWith(')');
    if (paren) t = t.slice(1, -1);
    const pieces = t.split('; ');
    if (!pieces.some(p => CITES[p])) return;
    ref.textContent = '';
    if (paren) ref.appendChild(document.createTextNode('('));
    pieces.forEach((p, i) => {
      if (i) ref.appendChild(document.createTextNode('; '));
      if (CITES[p]) { const s = el('span', 'cite', p); s.setAttribute('data-cite', p); ref.appendChild(s); }
      else ref.appendChild(document.createTextNode(p));
    });
    if (paren) ref.appendChild(document.createTextNode(')'));
  });
  const PROSE = /\b(LRFD|SDG|SDM|AASHTO Guide Spec\. Pedestrian Bridges)\s+(?:(Tables?|Eqs?\.|Figures?|Fig\.|Articles?|Art\.)\s+)?(\d+(?:\.\d+)+(?:\.[A-Z](?:\.\d+)?)?(?:-\d+)?)/g;
  // Bare ids after a citation ("LRFD 5.10.3.2 / 5.10.6", "5.10.8.2.1; 5.10.8.4.3", "5.10.6-1/-2") inherit its code.
  const CONT = /^(\s*(?:\/|;|,|&|\band\b|\bor\b)\s*)(?:(Tables?|Eqs?\.)\s+)?(\d+(?:\.\d+)+(?:\.[A-Z](?:\.\d+)?)?(?:-\d+)?|-\d+)\b/;
  const canonical = (code, kind, id) => {
    const k = kind ? kind.replace(/s\b/, '').replace('Eq.', 'Eq.').replace('Figure', 'Fig.') : '';
    if (!k || /^Art/.test(k)) return code + ' ' + id;
    return code + ' ' + (k === 'Eqs.' ? 'Eq.' : k) + ' ' + id;
  };
  if (Object.keys(CITES).length) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: n => (!n.parentElement || n.parentElement.closest('script, style, math, .var-pop, .cite, .ref, a, button, svg, .toolbar')) ? NodeFilter.FILTER_REJECT
        : (PROSE.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP)
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(n => {
      const frag = document.createDocumentFragment();
      let last = 0, m, any = false;
      PROSE.lastIndex = 0;
      const s = n.nodeValue;
      while ((m = PROSE.exec(s))) {
        const piece = canonical(m[1], m[2], m[3]);
        let pos = m.index + m[0].length, ident = m[3];
        if (CITES[piece]) {
          frag.appendChild(document.createTextNode(s.slice(last, m.index)));
          const span = el('span', 'cite', m[0]); span.setAttribute('data-cite', piece); frag.appendChild(span);
          last = pos; any = true;
        }
        let c;
        while ((c = CONT.exec(s.slice(pos)))) {
          ident = c[3].startsWith('-') ? ident.replace(/-\d+$/, '') + c[3] : c[3];
          const cont = canonical(m[1], c[2], ident);
          const start = pos + c[1].length;
          if (CITES[cont]) {
            frag.appendChild(document.createTextNode(s.slice(last, start)));
            const span = el('span', 'cite', c[0].slice(c[1].length)); span.setAttribute('data-cite', cont); frag.appendChild(span);
            last = pos + c[0].length; any = true;
          }
          pos += c[0].length;
        }
        PROSE.lastIndex = Math.max(PROSE.lastIndex, pos);
      }
      if (!any) return;
      frag.appendChild(document.createTextNode(s.slice(last)));
      n.parentNode.replaceChild(frag, n);
    });
  }
  const GLYPH = '[data-var],[data-cite]';
  const keyFor = g => g.hasAttribute('data-var') ? g.getAttribute('data-var') : 'cite:' + g.getAttribute('data-cite');
  console.log('report-cards ' + CARDS_VERSION + ': ' + defs.size + ' definitions, ' + inputs.size + ' inputs, ' + legend.size + ' legend terms, ' + Object.keys(CITES).length + ' citations');

  // ---- 4. Navigation: open ancestors, scroll, flash; Back returns to where you were ----
  function reveal(target) {
    for (let d = target.parentElement; d; d = d.parentElement) if (d.localName === 'details') d.open = true;
    target.scrollIntoView({block: 'center'});
    target.classList.remove('var-flash'); void target.offsetWidth; target.classList.add('var-flash');
  }
  function go(target) {
    history.replaceState({y: window.scrollY}, '');
    history.pushState({y: null}, '', '#' + target.id);
    reveal(target);
  }
  window.addEventListener('popstate', e => { if (e.state && typeof e.state.y === 'number') window.scrollTo(0, e.state.y); });

  // ---- 5. Cards ----
  const clean = node => { node.querySelectorAll('.var-hl, .var-src').forEach(x => x.classList.remove('var-hl', 'var-src')); node.querySelectorAll('[id]').forEach(x => x.removeAttribute('id')); return node; };
  const inlineMath = (node, live) => {
    const m = document.createElementNS(MML, 'math'); m.setAttribute('display', 'inline');
    const c = clean(node.cloneNode(true));
    if (!live) { c.removeAttribute('data-var'); c.querySelectorAll('[data-var]').forEach(x => x.removeAttribute('data-var')); }
    m.appendChild(c); return m;
  };
  const jump = (txt, target) => { const a = el('a', null, txt); a.href = '#' + target.id; a.addEventListener('click', e => { e.preventDefault(); go(target); }); return a; };
  const pops = [];
  let hoverEl = null, openTimer = null, sweepTimer = null, hlKey = null, zTop = 50;

  function controls(pop) {
    const right = el('span', 'vp-sec');
    const pinBtn = el('button', 'vp-btn vp-pin', '📌 Pin'); pinBtn.title = 'Keep this card open (or click the reference, or drag the card)';
    pinBtn.addEventListener('click', e => { e.stopPropagation(); pin(pop); });
    const close = el('button', 'vp-close', '×'); close.title = 'Close this card';
    close.addEventListener('click', e => { e.stopPropagation(); remove(pop); });
    return {right, finish: () => { right.appendChild(pinBtn); right.appendChild(close); }};
  }

  function openInTab(src) {
    if (!src.startsWith('data:')) { window.open(src, '_blank'); return; }
    fetch(src).then(r => r.blob()).then(b => { window.open(URL.createObjectURL(b), '_blank'); });
  }

  function buildCite(piece, anchor) {
    const c = CITES[piece]; if (!c) return null;
    const pop = el('div', 'var-pop cite-pop');
    const head = el('div', 'vp-head'), title = el('span', 'vp-title');
    title.appendChild(el('span', null, piece));
    if (c.title && c.title !== piece) title.appendChild(document.createTextNode(' · ' + c.title));
    head.appendChild(title);
    const {right, finish} = controls(pop);
    right.appendChild(document.createTextNode(c.edition || c.code || '')); finish();
    head.appendChild(right); pop.appendChild(head);
    if (c.governs && c.governs.length) pop.appendChild(el('p', 'vp-meaning', 'Governs: ' + c.governs.join(' · ')));
    if (c.missing) pop.appendChild(el('p', 'vp-note', c.missing));
    (c.pages || []).forEach(pg => {
      const full = pg.full && PAGES[pg.full] ? PAGES[pg.full] : pg.full;
      const box = el('div', 'vp-page'), bar = el('div', 'vp-pagebar');
      bar.appendChild(el('span', null, (pg.printed ? 'page ' + pg.printed : 'PDF page ' + pg.page) + (pg.source ? ' · ' + pg.source : '')));
      if (pg.crop) {
        const imgbox = el('div', 'vp-imgbox'), img = el('img', 'vp-crop');
        img.src = pg.crop; img.alt = pg.label || piece;
        if (full) {
          const toggle = el('button', 'vp-btn', 'Show full page');
          const setFull = f => { box.classList.toggle('full', f); img.src = f ? full : pg.crop; toggle.textContent = f ? '← Back to excerpt' : 'Show full page'; img.title = f ? 'Click to return to the excerpt' : 'Click to show the full page'; };
          setFull(false);
          toggle.addEventListener('click', e => { e.stopPropagation(); setFull(!box.classList.contains('full')); });
          img.addEventListener('click', e => { e.stopPropagation(); setFull(!box.classList.contains('full')); });
          const tab = el('button', 'vp-btn', 'Open page in new tab ↗'); tab.title = 'The highlighted page as an image in a new tab';
          tab.addEventListener('click', e => { e.stopPropagation(); openInTab(full); });
          bar.appendChild(toggle); bar.appendChild(tab);
        }
        if (pg.pdf) { const pdf = el('a', null, 'PDF ↗'); pdf.href = pg.pdf; pdf.target = '_blank'; pdf.title = 'One-page PDF with the highlight as an annotation'; bar.appendChild(pdf); }
        box.appendChild(bar); imgbox.appendChild(img); box.appendChild(imgbox);
      } else {
        box.appendChild(bar);
        box.appendChild(el('p', 'vp-note', 'Excerpt image not included in this build of the report.'));
      }
      pop.appendChild(box);
    });
    const foot = el('div', 'vp-foot');
    foot.appendChild(el('span', null, 'click the excerpt (or the button) to switch between excerpt and full page · pin to keep · drag by the header'));
    pop.appendChild(foot);
    return pop;
  }

  function build(k, anchor) {
    if (k.startsWith('cite:')) return buildCite(k.slice(5), anchor);
    const d = defs.get(k), i = inputs.get(k), l = legend.get(k);
    if (!d && !i && !l) return null;
    const pop = el('div', 'var-pop');
    const head = el('div', 'vp-head'), title = el('span', 'vp-title');
    title.appendChild(inlineMath(anchor, false));
    title.appendChild(document.createTextNode(d ? d.caption : (i ? i.meaning : l.meaning)));
    head.appendChild(title);
    const {right, finish} = controls(pop);
    right.appendChild(document.createTextNode(d ? ('calculated · ' + d.section) : (i ? ('input · ' + i.section) : l.source)));
    finish();
    head.appendChild(right);
    pop.appendChild(head);
    if (d) {
      if (d.meaning && d.meaning !== d.caption) pop.appendChild(el('p', 'vp-meaning', d.meaning));
      d.maths.forEach(m => { const eq = el('div', 'vp-eq'); eq.appendChild(clean(m.cloneNode(true))); pop.appendChild(eq); });
      if (d.result) pop.appendChild(el('p', 'vp-result', d.result));
    } else {
      const t = el('table'), tr = el('tr');
      tr.appendChild(el('td', 'num', i ? i.value : l.value)); tr.appendChild(el('td', null, i ? i.source : l.source));
      t.appendChild(tr); pop.appendChild(t);
    }
    const foot = el('div', 'vp-foot');
    if (d || i) foot.appendChild(jump(d ? 'Go to definition ↗' : 'Go to inputs table ↗', (d || i).target));
    const users = usedIn.get(k);
    if (users && users.size) {
      const u = el('span', 'vp-used', 'Used in: ');
      users.forEach(name => {
        const t = defs.get(name); if (!t) return;
        const m = inlineMath(t.lhs, true); m.title = t.caption;
        u.appendChild(m); u.appendChild(document.createTextNode(' '));
      });
      foot.appendChild(u);
    }
    foot.appendChild(el('span', null, 'hover a variable here for its card · pin to keep · drag by the header'));
    pop.appendChild(foot);
    return pop;
  }

  const containerOf = node => node ? node.closest('.var-pop') : null;
  function chain(pop) { const s = new Set(); for (let p = pop; p; p = p._parent) s.add(p); return s; }
  function clamp(pop, left, top) {
    const w = pop.offsetWidth;
    const maxLeft = window.scrollX + document.documentElement.clientWidth - w - 12;
    left = Math.max(window.scrollX + 8, Math.min(left, maxLeft));
    top = Math.max(window.scrollY + 8, top);
    pop.style.left = left + 'px'; pop.style.top = top + 'px';
  }
  function place(pop, anchor) {
    document.body.appendChild(pop);
    pop.style.zIndex = ++zTop;
    const parent = pop._parent;
    if (parent) {
      const pr = parent.getBoundingClientRect();
      clamp(pop, pr.left + window.scrollX + 36, pr.bottom + window.scrollY - 12);
    } else {
      const r = anchor.getBoundingClientRect(), h = pop.offsetHeight;
      let top = r.bottom + window.scrollY + 4;
      if (r.bottom + 4 + h > window.innerHeight && r.top - h - 4 > 0) top = r.top + window.scrollY - h - 4;
      clamp(pop, r.left + window.scrollX, top);
    }
  }
  function remove(pop) {
    pops.forEach(p => { if (p._parent === pop) p._parent = pop._parent; });
    if (pop._anchor) pop._anchor.classList.remove('var-src');
    pop.remove();
    const i = pops.indexOf(pop); if (i >= 0) pops.splice(i, 1);
  }
  function pin(pop) { pop._pinned = true; pop.classList.add('pinned'); pop._anchor.classList.add('var-src'); pop.style.zIndex = ++zTop; }
  function closeAll() { clearTimeout(openTimer); pops.slice().forEach(remove); }
  function open(k, anchor) {
    const existing = pops.find(p => p._anchor === anchor);
    if (existing) return existing;
    const parent = containerOf(anchor);
    const keep = chain(parent);
    pops.filter(p => !p._pinned && !keep.has(p)).forEach(remove);
    const pop = build(k, anchor); if (!pop) return null;
    pop._anchor = anchor; pop._key = k; pop._parent = parent; pop._pinned = false;
    place(pop, anchor); pops.push(pop);
    return pop;
  }
  function sweep() {
    const warm = new Set();
    pops.forEach(p => { if (hoverEl && (p.contains(hoverEl) || p._anchor.contains(hoverEl))) chain(p).forEach(q => warm.add(q)); });
    pops.filter(p => !p._pinned && !warm.has(p)).forEach(remove);
  }
  function highlight(k) {
    if (hlKey) document.querySelectorAll('.var-hl').forEach(x => x.classList.remove('var-hl'));
    hlKey = k;
    if (!k) return;
    const sel = k.startsWith('cite:') ? '[data-cite="' + CSS.escape(k.slice(5)) + '"]' : '[data-var="' + CSS.escape(k) + '"]';
    document.querySelectorAll(sel).forEach(x => x.classList.add('var-hl'));
  }

  let drag = null;
  document.addEventListener('pointerdown', e => {
    const t = e.target instanceof Element ? e.target : null; if (!t) return;
    const pop = containerOf(t); if (!pop) return;
    pop.style.zIndex = ++zTop;
    const head = t.closest('.vp-head'); if (!head || t.closest('button') || e.button !== 0) return;
    if (!pop._pinned) pin(pop);
    drag = {pop, dx: e.pageX - pop.offsetLeft, dy: e.pageY - pop.offsetTop};
    pop.classList.add('dragging'); head.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  document.addEventListener('pointermove', e => {
    if (!drag) return;
    const maxLeft = document.documentElement.clientWidth - drag.pop.offsetWidth - 4;
    drag.pop.style.left = Math.max(0, Math.min(e.pageX - drag.dx, maxLeft)) + 'px';
    drag.pop.style.top = Math.max(0, e.pageY - drag.dy) + 'px';
  });
  document.addEventListener('pointerup', () => { if (drag) { drag.pop.classList.remove('dragging'); drag = null; } });

  document.addEventListener('mouseover', e => {
    const t = e.target instanceof Element ? e.target : null; if (!t) return;
    hoverEl = t;
    clearTimeout(sweepTimer); sweepTimer = setTimeout(sweep, 320);
    const glyph = t.closest(GLYPH);
    clearTimeout(openTimer);
    if (!glyph) return;
    const k = keyFor(glyph);
    if (k !== hlKey) highlight(k);
    if (pops.some(p => p._anchor === glyph)) return;
    openTimer = setTimeout(() => open(k, glyph), 140);
  });
  document.addEventListener('mouseout', e => {
    const t = e.target instanceof Element ? e.target : null; if (!t) return;
    if (t.closest(GLYPH)) { highlight(null); clearTimeout(openTimer); }
    hoverEl = e.relatedTarget instanceof Element ? e.relatedTarget : null;
    clearTimeout(sweepTimer); sweepTimer = setTimeout(sweep, 320);
  });
  document.addEventListener('click', e => {
    const t = e.target instanceof Element ? e.target : null; if (!t) return;
    if (t.closest('a') || t.closest('button')) return;
    const glyph = t.closest(GLYPH); if (!glyph) return;
    e.preventDefault();
    clearTimeout(openTimer);
    const pop = open(keyFor(glyph), glyph);
    if (pop) pin(pop);
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAll(); });

  const bar = document.querySelector('.toolbar');
  if (bar) {
    const b = el('button', 'var-close-all', 'Close cards'); b.addEventListener('click', closeAll); bar.appendChild(b);
    bar.appendChild(el('span', 'var-hint', 'Hover a variable for its definition card, or a code reference for its highlighted excerpt · pin (click, 📌, or drag) · hover inside a card for the next card · Esc closes all'));
  }
})();
